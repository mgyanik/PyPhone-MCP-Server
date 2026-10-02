"""任务存储模块：管理长时间异步任务的状态、子进程句柄与生命周期。"""

from __future__ import annotations

import os
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from src import logging as structured_logging
from src import policy

# Termux 环境变量配置，保持与 Node.js 现有环境一致
TERMUX_PREFIX = "/data/data/com.termux/files/usr"
TERMUX_HOME = "/data/data/com.termux/files/home"

DEFAULT_ENV = {
    **os.environ,
    "HOME": TERMUX_HOME,
    "PREFIX": TERMUX_PREFIX,
    "PATH": f"{TERMUX_PREFIX}/bin:{TERMUX_PREFIX}/bin/applets:{os.environ.get('PATH', '')}:/system/bin:/system/xbin",
    "TMPDIR": f"{TERMUX_PREFIX}/tmp",
    "LANG": "C.UTF-8",
    "TERM": "xterm-256color",
}

SHELL_BIN = (
    f"{TERMUX_PREFIX}/bin/bash"
    if os.path.exists(f"{TERMUX_PREFIX}/bin/bash")
    else (
        f"{TERMUX_PREFIX}/bin/sh"
        if os.path.exists(f"{TERMUX_PREFIX}/bin/sh")
        else "/system/bin/sh"
    )
)


@dataclass
class Task:
    task_id: str
    command: str
    cwd: str
    status: str  # "running" | "done" | "failed" | "canceled" | "denied"
    start_time: float
    end_time: float | None = None
    exit_code: int | None = None
    output: str = ""
    error: str = ""
    process: subprocess.Popen | None = None

    @property
    def duration(self) -> float:
        if self.end_time is not None:
            return round(self.end_time - self.start_time, 3)
        return round(time.time() - self.start_time, 3)

    def to_dict(self, include_output: bool = True) -> dict[str, Any]:
        data: dict[str, Any] = {
            "task_id": self.task_id,
            "command": self.command,
            "cwd": self.cwd,
            "status": self.status,
            "duration": self.duration,
            "exit_code": self.exit_code,
        }
        if include_output:
            data["output"] = self.output
            if self.error:
                data["error"] = self.error
        return data


class TaskStore:
    """线程安全的异步长任务存储器。"""

    def __init__(self, completed_ttl: float = 3600.0) -> None:
        self._tasks: dict[str, Task] = {}
        self._lock = threading.Lock()
        self.completed_ttl = completed_ttl  # 已完成任务在内存中保留的秒数

    def _cleanup_expired_locked(self) -> None:
        """内部方法：清理过期的已完成/失败任务。"""
        now = time.time()
        to_delete = []
        for tid, t in self._tasks.items():
            if t.status in ("done", "failed", "canceled", "denied") and t.end_time:
                if (now - t.end_time) > self.completed_ttl:
                    to_delete.append(tid)
        for tid in to_delete:
            del self._tasks[tid]
            structured_logging.structured("task_cleaned", task_id=tid, reason="ttl_expired")

    def spawn(self, command: str, cwd: str = ".") -> Task:
        """异步启动一个命令长任务，立即返回 Task 对象。
        
        禁止阻塞调用方，使用独立线程读取输出和监控退出状态。
        """
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        now = time.time()

        # 调用 policy.evaluate(command) 进行安全审查
        pol_res = policy.evaluate(command)
        if pol_res.is_denied:
            task = Task(
                task_id=task_id,
                command=command,
                cwd=cwd,
                status="denied",
                start_time=now,
                end_time=now,
                error=f"安全策略拒绝: {pol_res.reason}",
            )
            with self._lock:
                self._cleanup_expired_locked()
                self._tasks[task_id] = task
            structured_logging.structured("task_policy_denied", task_id=task_id, command=command, reason=pol_res.reason)
            return task

        if pol_res.requires_confirmation:
            structured_logging.structured(
                "task_policy_ask_executed",
                task_id=task_id,
                command=command,
                reason=pol_res.reason,
            )

        # ALLOW 与 ASK 状态继续正常启动
        task = Task(
            task_id=task_id,
            command=command,
            cwd=cwd,
            status="running",
            start_time=now,
        )

        with self._lock:
            self._cleanup_expired_locked()
            self._tasks[task_id] = task

        structured_logging.structured(
            "task_started",
            task_id=task_id,
            command=command,
            cwd=cwd,
            status="running",
        )

        try:
            target_cwd = cwd if os.path.isabs(cwd) else os.path.join(TERMUX_HOME, cwd)
            if not os.path.exists(target_cwd):
                target_cwd = TERMUX_HOME

            proc = subprocess.Popen(
                [SHELL_BIN, "-c", command],
                cwd=target_cwd,
                env=DEFAULT_ENV,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            task.process = proc
        except Exception as e:
            with self._lock:
                task.status = "failed"
                task.end_time = time.time()
                task.exit_code = -1
                task.error = str(e)
            structured_logging.structured(
                "task_spawn_failed",
                task_id=task_id,
                command=command,
                error=str(e),
            )
            return task

        # 启动后台守护线程等待进程结束并回收输出，不阻塞主线程
        def _monitor_process() -> None:
            try:
                stdout_data, stderr_data = proc.communicate()
            except Exception as e:
                stdout_data = ""
                stderr_data = f"Communication error: {e}"

            exit_code = proc.returncode
            end_t = time.time()
            output = stdout_data.strip()
            if stderr_data.strip():
                if output:
                    output += "\n---stderr---\n" + stderr_data.strip()
                else:
                    output = stderr_data.strip()

            with self._lock:
                # 如果已被外部取消，则不覆写 canceled 状态
                if task.status != "canceled":
                    task.status = "done" if exit_code == 0 else "failed"
                task.end_time = end_t
                task.exit_code = exit_code
                task.output = output

            structured_logging.structured(
                "task_finished",
                task_id=task_id,
                command=command,
                status=task.status,
                exit_code=exit_code,
                duration=task.duration,
            )

        monitor_thread = threading.Thread(
            target=_monitor_process,
            name=f"task-monitor-{task_id}",
            daemon=True,
        )
        monitor_thread.start()

        return task

    def get(self, task_id: str) -> Task | None:
        """获取指定 ID 的任务状态对象。"""
        with self._lock:
            self._cleanup_expired_locked()
            return self._tasks.get(task_id)

    def list(self, status: str | None = None) -> list[Task]:
        """列出所有任务，可按状态筛选。"""
        with self._lock:
            self._cleanup_expired_locked()
            tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        return tasks

    def cancel(self, task_id: str) -> bool:
        """取消进行中的任务。如果任务不存在或已结束返回 False。"""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task or task.status != "running":
                return False

            task.status = "canceled"
            task.end_time = time.time()
            proc = task.process

        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass
            try:
                proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                try:
                    proc.kill()
                    proc.wait(timeout=1.0)
                except Exception:
                    pass

        structured_logging.structured(
            "task_canceled",
            task_id=task_id,
            command=task.command,
        )
        return True

    def clear(self) -> None:
        """清空所有任务记录（主要用于测试重置）。"""
        with self._lock:
            self._tasks.clear()


# 全局统一 TaskStore 实例
task_store = TaskStore()
