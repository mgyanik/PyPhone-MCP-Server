import os
import subprocess
import sys
import tempfile
import time

from src.tools.get_file_info import get_file_info, file_info
from src.tools.find_process import find_process
from src.tools.get_device_status import get_device_status
from src.tools.kill_process import kill_process
from src.tools.manage_file import manage_file
from src.tools.read_file_lines import read_file_lines
from src.tools.run_command import run_command


def test_get_device_status():
    res = get_device_status()
    assert res["status"] == "success"
    assert "storage" in res
    assert "memory" in res
    assert "cpu" in res
    assert res["cpu"]["cores"] >= 1
    assert "battery" in res


def test_read_file_lines_pagination():
    with tempfile.NamedTemporaryFile("w+", encoding="utf-8", delete=False) as f:
        for i in range(1, 21):
            f.write(f"Line {i}\n")
        f_path = f.name

    try:
        # 读取第 5 行到第 9 行 (5 行)
        res = read_file_lines(f_path, start_line=5, line_count=5)
        assert res["status"] == "success"
        assert res["start_line"] == 5
        assert res["lines_retrieved"] == 5
        assert res["total_lines"] == 20
        assert res["has_more"] is True
        assert res["lines"] == [f"Line {i}" for i in range(5, 10)]
        assert "5 | Line 5" in res["content"]

        # 读取最后几行超出范围
        res_end = read_file_lines(f_path, start_line=18, line_count=10)
        assert res_end["status"] == "success"
        assert res_end["lines_retrieved"] == 3
        assert res_end["has_more"] is False
    finally:
        if os.path.exists(f_path):
            os.remove(f_path)


def test_read_file_lines_non_existent():
    res = read_file_lines("/non_existent_file_path_xyz")
    assert res["status"] == "error"
    assert "not found" in res["error"].lower()


def test_manage_file_lifecycle_and_safety():
    with tempfile.TemporaryDirectory() as tmpdir:
        src = os.path.join(tmpdir, "original.txt")
        with open(src, "w", encoding="utf-8") as f:
            f.write("test content")

        # 1. 复制文件
        dst_copy = os.path.join(tmpdir, "copied.txt")
        res_copy = manage_file("copy", src, dst_copy)
        assert res_copy["status"] == "success"
        assert os.path.exists(dst_copy)

        # 2. 移动文件
        dst_move = os.path.join(tmpdir, "moved.txt")
        res_move = manage_file("move", dst_copy, dst_move)
        assert res_move["status"] == "success"
        assert not os.path.exists(dst_copy)
        assert os.path.exists(dst_move)

        # 3. 删除文件
        res_rm = manage_file("remove", dst_move)
        assert res_rm["status"] == "success"
        assert not os.path.exists(dst_move)

        # 4. 删除目录 (递归与非递归)
        sub_dir = os.path.join(tmpdir, "subdir")
        os.makedirs(sub_dir)
        sub_file = os.path.join(sub_dir, "file.txt")
        with open(sub_file, "w") as f:
            f.write("inner")

        # 非递归删除非空目录应报错
        res_fail = manage_file("remove", sub_dir, recursive=False)
        assert res_fail["status"] == "error"

        # 递归删除
        res_rec = manage_file("remove", sub_dir, recursive=True)
        assert res_rec["status"] == "success"
        assert not os.path.exists(sub_dir)

        # 5. 安全拦截：禁止删除根目录或敏感目录
        res_safe = manage_file("remove", "/")
        assert res_safe["status"] == "error"
        assert "guardrail" in res_safe["error"].lower()


def test_file_info_query_and_hash():
    with tempfile.NamedTemporaryFile("w+", encoding="utf-8", delete=False) as f:
        f.write("hello mcp server")
        f_path = f.name

    try:
        # 带哈希校验
        info = file_info(f_path, compute_hash=True)
        assert info["status"] == "success"
        assert info["exists"] is True
        assert info["type"] == "file"
        assert info["size_bytes"] == len("hello mcp server")
        assert info["sha256"] is not None
        assert info["is_binary"] is False

        # 不存在的文件
        info_none = file_info(os.path.join(tempfile.gettempdir(), "non_existent_file_12345"))
        assert info_none["exists"] is False
        assert info_none["type"] == "not_found"
    finally:
        if os.path.exists(f_path):
            os.remove(f_path)


def test_find_process():
    # 查询当前 Python 进程
    res = find_process(name="python")
    assert res["status"] == "success"
    assert res["count"] >= 1
    pids = [p["pid"] for p in res["processes"]]
    assert os.getpid() in pids


def test_kill_process_safety_and_execution():
    # 1. 尝试自杀 MCP 自身进程应被拦截
    res_self = kill_process(os.getpid())
    assert res_self["status"] == "error"
    assert "cannot kill the mcp server process itself" in res_self["error"].lower()

    # 2. 尝试杀 PID 1 应被拦截
    res_root = kill_process(1)
    assert res_root["status"] == "error"
    assert "cannot kill init" in res_root["error"].lower()

    # 3. 正常终止一个测试子进程
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        pid = proc.pid
        time.sleep(0.1)
        res_kill = kill_process(pid, force=False, timeout=2.0)
        assert res_kill["status"] == "success"
        proc.wait(timeout=2.0)
        assert proc.poll() is not None
    finally:
        if proc.poll() is None:
            proc.kill()


def test_run_command_default_timeout_is_5s():
    import inspect
    sig = inspect.signature(run_command)
    assert sig.parameters["timeout"].default == 5.0

    # 验证超时执行被强制中断
    start_t = time.time()
    res = run_command("sleep 10", timeout=1.0)
    dur = time.time() - start_t
    assert res["status"] == "timeout"
    assert dur < 3.0


def test_fetch_url_local():
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import threading

    class TestHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/json":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"message": "pong"}')
            else:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"plain text response")

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), TestHandler)
    port = server.server_port
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    from src.tools.fetch_url import fetch_url
    try:
        # 测试 JSON 自动解析
        res_json = fetch_url(f"http://127.0.0.1:{port}/json")
        assert res_json["status"] == "success"
        assert res_json["status_code"] == 200
        assert res_json["json"] == {"message": "pong"}

        # 测试纯文本
        res_text = fetch_url(f"http://127.0.0.1:{port}/text")
        assert res_text["status"] == "success"
        assert "plain text response" in res_text["text"]
    finally:
        server.shutdown()
        server.server_close()

