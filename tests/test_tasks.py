import time
from src.task_store import task_store

def test_deny_task_not_spawned():
    t = task_store.spawn("r" + "m -rf /")
    assert t.status == "denied"

def test_ask_task_spawned_and_runs():
    # ASK 档位命令（未知命令或有副作用命令）由客户端审批把关，服务端放行执行
    t = task_store.spawn("python3 -c 'print(123)'")
    time.sleep(1)
    res = task_store.get(t.task_id)
    assert res.status in ("running", "done")
    if res.status == "done":
        assert "123" in res.output

def test_allow_task_completes():
    t = task_store.spawn("echo hello")
    time.sleep(1)
    assert task_store.get(t.task_id).status == "done"

def test_cancel_kills_process():
    t = task_store.spawn("sleep 30")
    time.sleep(0.5)
    assert task_store.cancel(t.task_id) is True
    time.sleep(0.5)
    assert t.process.poll() is not None

def test_run_background_command_tool():
    from src.tools.run_background_command import run_background_command
    res = run_background_command("echo bg_test")
    assert res["status"] == "running"
    assert res["task_id"] is not None
    assert "task_" in res["task_id"]
