"""全局高并发任务池：常驻复用线程池，避免频繁创建/销毁线程的系统开销。"""

from __future__ import annotations

import atexit
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Iterable, TypeVar

from src.config import MAX_WORKERS

T = TypeVar("T")
R = TypeVar("R")

# 全局共享工作池
_executor: ThreadPoolExecutor | None = None


def get_executor() -> ThreadPoolExecutor:
    """获取全局常驻线程池单例。"""
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(
            max_workers=MAX_WORKERS,
            thread_name_prefix="mcp-worker",
        )
    return _executor


def map_concurrent(
    fn: Callable[[T], R],
    items: Iterable[T],
    max_workers: int | None = None,
) -> list[R]:
    """并发执行批处理任务并保持输入顺序返回结果。"""
    item_list = list(items)
    if not item_list:
        return []

    # 少量任务时单线程直接执行，避免线程调度损耗
    if len(item_list) == 1:
        return [fn(item_list[0])]

    executor = get_executor()
    futures = [executor.submit(fn, item) for item in item_list]
    return [future.result() for future in futures]


@atexit.register
def _shutdown_executor() -> None:
    global _executor
    if _executor is not None:
        _executor.shutdown(wait=False, cancel_futures=True)
        _executor = None
