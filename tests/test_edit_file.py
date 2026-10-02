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

        # 2. overwrite when old_text is None
        res = edit_file(target, new_text="new content\n")
        assert res["status"] == "success"
        assert res["action"] == "overwritten"

        with open(target, "r") as f:
            assert f.read() == "new content\n"

def test_edit_file_single_replacement():
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
