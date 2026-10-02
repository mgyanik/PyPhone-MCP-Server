import time
from src.core.pool import map_concurrent
from src.tools.read_file import read_files

def test_map_concurrent_ordering_and_speed():
    def task(n: int) -> int:
        time.sleep(0.02)
        return n * 2

    inputs = list(range(10))
    start = time.time()
    outputs = map_concurrent(task, inputs)
    duration = time.time() - start

    assert outputs == [n * 2 for n in inputs]
    # 10 个 0.02s 任务，并发执行应远小于 0.2s 串行时间
    assert duration < 0.15

def test_read_files_high_concurrency(tmp_path):
    # 创建 20 个临时小文件并测试并发读取
    paths = []
    for i in range(20):
        f = tmp_path / f"file_{i}.txt"
        f.write_text(f"content_{i}", encoding="utf-8")
        paths.append(str(f))

    res = read_files(paths)
    assert res["status"] == "success"
    assert res["total_files"] == 20
    assert len(res["results"]) == 20
    for i, r in enumerate(res["results"]):
        assert r["status"] == "success"
        assert r["content"] == f"content_{i}"
