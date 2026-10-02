import time
from src.task_store import task_store

def test_deny_task_not_spawned():
    t = task_store.spawn('rm -rf /')
    assert t.status == 'denied'

def test_ask_task_denied():
    t = task_store.spawn('some_unknown_cmd xyz')
    assert t.status == 'denied'
    assert '手动' in t.error

def test_allow_task_completes():
    t = task_store.spawn('echo hello')
    time.sleep(1)
    assert task_store.get(t.task_id).status == 'done'

def test_cancel_kills_process():
    t = task_store.spawn('sleep 30')
    time.sleep(0.5)
    assert task_store.cancel(t.task_id) is True
    time.sleep(0.5)
    assert t.process.poll() is not None
