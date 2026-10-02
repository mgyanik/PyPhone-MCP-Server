from src.tools.run_command import run_command, start_task

def test_realtime_task_success():
    res = run_command("echo 'realtime test'")
    assert res["status"] == "success"
    assert "realtime test" in res["output"]
    assert res["exit_code"] == 0
    assert "summary" not in res  # summary completely removed

def test_realtime_task_denied():
    res = run_command("r" + "m -rf /")
    assert res["status"] == "denied"
    assert "Blocked by policy" in res["error"]
    assert "summary" not in res

def test_realtime_task_timeout():
    res = run_command("sleep 2", timeout=0.2)
    assert res["status"] == "timeout"
    assert res["exit_code"] == -1
    assert "summary" not in res

def test_start_task_alias_compatible():
    res = start_task("echo 'alias'")
    assert res["status"] == "success"
    assert "alias" in res["output"]
