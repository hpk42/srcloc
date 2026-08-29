from collections import Counter

import pytest

from srcloc.collect import count_changed, count_file, discover, parse_diff
from srcloc.langs import file_lang
from tests.conftest import DIFF, git, make_tree


def run_counts(targets):
    counts = Counter()
    unknown = []
    for path, rel in discover(targets):
        if count_file(path, rel, counts) is None:
            unknown.append(str(path))
    return counts, unknown


def count_diff(text):
    """The added and the removed lines of a whole diff."""
    added = Counter()
    removed = Counter()
    for old_path, new_path, old_doc, new_doc in parse_diff(text.splitlines()):
        if file_lang(new_path or old_path) is None:
            continue
        if old_path is not None:
            count_changed(old_path, old_doc, removed)
        if new_path is not None:
            count_changed(new_path, new_doc, added)
    return added, removed


class TestDiscovery:
    def test_plain_directory(self, tmp_path):
        make_tree(tmp_path)
        counts, unknown = run_counts([str(tmp_path)])
        assert counts["python", "comment"] == 1
        assert counts["python", "code"] == 1
        assert counts["python", "empty"] == 1
        assert counts["python", "test"] == 2
        assert counts["rust", "code"] == 1
        assert counts["rust", "test"] == 2
        assert counts["markdown", "doc"] == 2
        assert counts["markdown", "empty"] == 1
        assert unknown == [str(tmp_path / "data.bin")]

    def test_git_directory_skips_ignored(self, tmp_path):
        make_tree(tmp_path)
        (tmp_path / ".gitignore").write_text("venv/\n")
        git("init", "-q", str(tmp_path))
        git("-C", str(tmp_path), "add", "pkg.py", "lib.rs")
        counts, _ = run_counts([str(tmp_path)])
        assert counts["python", "files"] == 2  # tracked and untracked, not the venv
        assert counts["rust", "files"] == 1
        assert counts["markdown", "files"] == 1

    def test_venv_never_counts_even_when_tracked(self, tmp_path):
        make_tree(tmp_path)
        git("init", "-q", str(tmp_path))
        git("-C", str(tmp_path), "add", "-f", ".")
        counts, _ = run_counts([str(tmp_path)])
        assert counts["python", "files"] == 2

    def test_single_file_target(self, tmp_path):
        make_tree(tmp_path)
        counts, _ = run_counts([str(tmp_path / "pkg.py")])
        assert counts["python", "files"] == 1
        assert counts["python", "code"] == 1

    def test_unreadable_file_is_unknown(self, tmp_path):
        make_tree(tmp_path)
        private = tmp_path / "private"
        private.mkdir()
        (private / "tls.key").write_text("secret\n")
        git("init", "-q", str(tmp_path))
        git("-C", str(tmp_path), "add", ".")
        private.chmod(0)
        try:
            counts, unknown = run_counts([str(tmp_path)])
        finally:
            private.chmod(0o755)
        assert counts["unknown", "files"] == 2
        assert str(private / "tls.key") in unknown

    def test_missing_target(self):
        with pytest.raises(SystemExit):
            list(discover(["no-such-path"]))


class TestDiff:
    def test_categories(self):
        added, removed = count_diff(DIFF)
        assert added["rust", "code"] == 1
        assert added["rust", "comment"] == 1
        assert added["rust", "test"] == 2
        assert added["python", "code"] == 1
        assert removed["rust", "code"] == 1
        assert removed["python", "code"] == 1

    def test_every_entry_is_parsed(self):
        parsed = parse_diff(DIFF.splitlines())
        assert [str(new) for _, new, _, _ in parsed] == [
            "src/lib.rs",
            "tool.py",
            "logo.png",
        ]

    def test_prose_changes(self):
        added, removed = count_diff("""\
diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1,2 +1,3 @@
 # title
-old sentence
+new sentence
+
""")
        assert added["markdown", "doc"] == 1
        assert added["markdown", "empty"] == 1
        assert removed["markdown", "doc"] == 1

    def test_config_changes(self):
        added, _ = count_diff("""\
diff --git a/doveauth.service.f b/doveauth.service.f
--- a/doveauth.service.f
+++ b/doveauth.service.f
@@ -1,2 +1,4 @@
 [Unit]
+# restart policy
+Restart=always
+
""")
        assert added["systemd", "config"] == 1
        assert added["systemd", "comment"] == 1
        assert added["systemd", "empty"] == 1

    def test_deleted_file(self):
        diff = """\
diff --git a/gone.py b/gone.py
deleted file mode 100644
--- a/gone.py
+++ /dev/null
@@ -1,1 +0,0 @@
-x = 1
"""
        ((old_path, new_path, _, _),) = parse_diff(diff.splitlines())
        assert str(old_path) == "gone.py"
        assert new_path is None
        _, removed = count_diff(diff)
        assert removed["python", "code"] == 1
