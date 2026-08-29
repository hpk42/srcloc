import io
import subprocess

import pytest

from srcloc.cli import main


def make_tree(root):
    (root / "pkg.py").write_text("# comment\nx = 1\n\n")
    (root / "lib.rs").write_text("fn f() {}\n#[cfg(test)]\nmod tests;\n")
    (root / "README.md").write_text("hello\n\nworld\n")
    (root / "data.bin").write_text("{}\n")
    (root / "tests").mkdir()
    (root / "tests/test_pkg.py").write_text("def test_x():\n    assert True\n")
    (root / "venv").mkdir()
    (root / "venv/ignored.py").write_text("x = 1\n")


def git(*args):
    subprocess.run(["git", *args], check=True)


DIFF = """\
diff --git a/src/lib.rs b/src/lib.rs
index 111..222 100644
--- a/src/lib.rs
+++ b/src/lib.rs
@@ -1,5 +1,6 @@
 fn f() {
-    old();
+    new();
+    // explain why
 }
 #[cfg(test)]
 mod tests {
+    #[test]
+    fn t() {}
 }
diff --git a/tool.py b/tool.py
--- a/tool.py
+++ b/tool.py
@@ -1,2 +1,2 @@
 x = 1
-y = 2
+y = 3
diff --git a/logo.png b/logo.png
Binary files a/logo.png and b/logo.png differ
"""


def rows(out):
    """Table lines as token lists, the share padding collapsed."""
    import re

    return [re.sub(r"\[ +", "[", line).split() for line in out.splitlines()]


@pytest.fixture
def run(capsys, monkeypatch):
    def run(*args, stdin=""):
        monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
        main(list(args))
        return capsys.readouterr().out

    return run


@pytest.fixture
def tree(tmp_path, monkeypatch):
    make_tree(tmp_path)
    monkeypatch.chdir(tmp_path)
    return tmp_path
