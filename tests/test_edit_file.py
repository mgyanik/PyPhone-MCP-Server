import os
import tempfile
from src.tools.edit_file import edit_file

def test_edit_file_create_and_overwrite():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = os.path.join(tmpdir, "test.txt")
        # 1. create_if_missing
        res = edit_file(target, new_text="hello world\n", create_if_missing=True)
        assert res["status"] == "success"
        assert res["action"] == "created"
        assert os.path.exists(target)

        with open(target, "r") as f:
            assert f.read() == "hello world\n"

        # 2. overwrite when line numbers and old_text are None
        res = edit_file(target, new_text="new content\n")
        assert res["status"] == "success"
        assert res["action"] == "overwritten"

        with open(target, "r") as f:
            assert f.read() == "new content\n"


def test_edit_file_line_range_replacement():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = os.path.join(tmpdir, "test.txt")
        initial_lines = "\n".join(f"Line {i}" for i in range(1, 11)) + "\n"
        with open(target, "w") as f:
            f.write(initial_lines)

        # 1. 替换第 3 到第 5 行 (3, 4, 5)
        res = edit_file(target, start_line=3, end_line=5, new_text="Replaced 3to5\n")
        assert res["status"] == "success"
        assert res["action"] == "line_replaced"
        assert res["start_line"] == 3
        assert res["end_line"] == 5
        assert res["lines_replaced"] == 3

        with open(target, "r") as f:
            lines = [l.strip() for l in f.readlines()]
        assert lines[0] == "Line 1"
        assert lines[1] == "Line 2"
        assert lines[2] == "Replaced 3to5"
        assert lines[3] == "Line 6"

        # 2. 单行替换 (省略 end_line 时自动等于 start_line)
        res_single = edit_file(target, start_line=1, new_text="First Line Header")
        assert res_single["status"] == "success"
        assert res_single["lines_replaced"] == 1
        with open(target, "r") as f:
            first_l = f.readline().strip()
        assert first_l == "First Line Header"

        # 3. 行号前插入模式 (end_line < start_line)
        res_insert = edit_file(target, start_line=2, end_line=1, new_text="Inserted Before Line 2")
        assert res_insert["status"] == "success"
        assert res_insert["action"] == "inserted"
        assert res_insert["lines_replaced"] == 0
        with open(target, "r") as f:
            all_l = [l.strip() for l in f.readlines()]
        assert all_l[1] == "Inserted Before Line 2"
        assert all_l[2] == "Line 2"


def test_edit_file_line_range_errors():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = os.path.join(tmpdir, "test.txt")
        with open(target, "w") as f:
            f.write("Line 1\nLine 2\n")

        # start_line < 1 报错
        res_zero = edit_file(target, start_line=0, new_text="foo")
        assert res_zero["status"] == "error"
        assert "must be >= 1" in res_zero["error"]

        # start_line 超出总行数报错
        res_over = edit_file(target, start_line=10, new_text="bar")
        assert res_over["status"] == "error"
        assert "exceeds" in res_over["error"]


def test_edit_file_legacy_text_replacement():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = os.path.join(tmpdir, "test.txt")
        with open(target, "w") as f:
            f.write("alpha beta gamma")

        res = edit_file(target, old_text="beta", new_text="delta")
        assert res["status"] == "success"
        assert res["action"] == "edited"
        assert res["replacements"] == 1

        with open(target, "r") as f:
            assert f.read() == "alpha delta gamma"


def test_edit_file_not_found():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = os.path.join(tmpdir, "test.txt")
        with open(target, "w") as f:
            f.write("foo bar")

        res = edit_file(target, old_text="non_existent", new_text="baz")
        assert res["status"] == "error"
        assert "not found" in res["error"]


def test_edit_file_multiple_occurrences_fails():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = os.path.join(tmpdir, "test.txt")
        with open(target, "w") as f:
            f.write("repeat and repeat")

        res = edit_file(target, old_text="repeat", new_text="once")
        assert res["status"] == "error"
        assert "must be unique" in res["error"]

