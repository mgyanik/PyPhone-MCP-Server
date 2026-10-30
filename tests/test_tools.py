"""9 大核心工具的契约测试。临时文件统一落在沙箱内的 .mcp_test_tmp 目录。"""

import os
import shutil
import tempfile

import pytest

from src.config import TERMUX_HOME
from src.tools.edit_file import patch_file
from src.tools.find_process import find_process
from src.tools.get_file_info import inspect_file_meta
from src.tools.list_dir import list_directory
from src.tools.manage_file import move_or_delete_file
from src.tools.read_file import read_file_or_outline
from src.tools.search_text import search_codebase

TMP_ROOT = os.path.join(TERMUX_HOME, ".mcp_test_tmp")


@pytest.fixture()
def tmpdir():
    os.makedirs(TMP_ROOT, exist_ok=True)
    path = tempfile.mkdtemp(dir=TMP_ROOT)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _write(dir_path: str, name: str, content: str) -> str:
    path = os.path.join(dir_path, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def test_read_file_range_and_outline(tmpdir):
    path = _write(tmpdir, "a.py", "def foo():\n    pass\n\nclass Bar:\n    pass\n")
    res = read_file_or_outline(path, start_line=1, end_line=2)
    assert res["status"] == "success"
    assert res["content"] == "def foo():\n    pass"

    outline = read_file_or_outline(path, outline=True)
    assert outline["status"] == "success"
    assert "foo" in outline["content"]


def test_read_file_missing(tmpdir):
    res = read_file_or_outline(os.path.join(tmpdir, "nope.txt"))
    assert res["status"] == "error"


def test_patch_file_search_replace(tmpdir):
    path = _write(tmpdir, "b.txt", "alpha beta gamma\n")
    res = patch_file(path, old_text="beta", new_text="delta")
    assert res["ok"] is True
    assert res["no_change"] is False
    with open(path, encoding="utf-8") as f:
        assert f.read() == "alpha delta gamma\n"


def test_patch_file_no_change_reports(tmpdir):
    path = _write(tmpdir, "c.txt", "same\n")
    res = patch_file(path, old_text="same", new_text="same")
    assert res["ok"] is True
    assert res["no_change"] is True


def test_inspect_file_meta(tmpdir):
    path = _write(tmpdir, "d.txt", "hello")
    res = inspect_file_meta(path, compute_hash=True)
    assert res["status"] == "success"
    assert res["size"] == 5
    assert len(res["sha256"]) == 64


def test_list_directory_and_search(tmpdir):
    _write(tmpdir, "e.txt", "needle here\n")
    listing = list_directory(tmpdir)
    assert listing["status"] == "success"
    names = {e["name"] for e in listing["results"][0]["entries"]}
    assert "e.txt" in names

    found = search_codebase(tmpdir, query="needle")
    assert found["status"] == "success"
    assert found["total_matches"] == 1


def test_move_or_delete_file(tmpdir):
    src = _write(tmpdir, "f.txt", "x")
    dst = os.path.join(tmpdir, "g.txt")
    assert move_or_delete_file("copy", src, dst)["status"] == "success"
    assert os.path.exists(dst)
    assert move_or_delete_file("remove", dst)["status"] == "success"
    assert not os.path.exists(dst)


def test_move_or_delete_refuses_sandbox_root():
    res = move_or_delete_file("remove", TERMUX_HOME, recursive=True)
    assert res["status"] == "error"
    assert "sandbox root" in res["error"]


def test_sandbox_blocks_escape():
    res = read_file_or_outline("../../etc/passwd")
    assert res["status"] == "error"
    assert "sandbox" in res["error"]


def test_find_process_self():
    res = find_process(name="python")
    assert res["status"] == "success"
    assert os.getpid() in [p["pid"] for p in res["processes"]]