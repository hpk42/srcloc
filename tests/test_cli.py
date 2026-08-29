import io
import json

import pytest

from srcloc.cli import main
from tests.conftest import DIFF, make_tree, rows


class TestCount:
    def test_summary(self, tree, run):
        out = run()
        assert "data.bin" not in out  # unknown files list only with -vv
        table = {row[0]: row for row in rows(out)}
        assert table["language"] == list(
            ("language", "NUMFILES", "doc", "comment", "test", "code", "SUM")
        )
        assert table["python"] == ["python", "2", ".", "1", "2", "1", "4"]
        assert table["markdown"] == ["markdown", "1", "2", ".", ".", ".", "2"]
        assert table["unknown"] == ["unknown", "1", ".", ".", ".", ".", "."]
        assert table["total"] == ["total", "5", "2", "1", "4", "2", "9"]

    def test_vv_lists_unknown_files(self, tree, run):
        out = run("-vv")
        assert "unknown files:" in out
        assert "data.bin" in out

    def test_with_empty(self, tree, run):
        table = {row[0]: row for row in rows(run("--with-empty")) if row}
        assert table["language"] == list(
            ("language", "NUMFILES", "empty", "doc", "comment", "test", "code", "SUM")
        )
        assert table["python"] == ["python", "2", "1", ".", "1", "2", "1", "5"]
        assert table["total"] == ["total", "5", "2", "2", "1", "4", "2", "11"]

    def test_v_adds_file_rows(self, tree, run):
        listing = rows(run("-v"))
        assert listing[0] == ["doc", "comment", "test", "code", "SUM", "file"]
        assert listing[2] == [".", ".", "2", "1", "3", "lib.rs"]
        assert listing[3] == ["2", ".", ".", ".", "2", "README.md"]
        assert listing[4] == [".", "1", ".", "1", "2", "pkg.py"]
        assert listing[5] == [".", ".", "2", ".", "2", "tests/test_pkg.py"]
        assert listing[6] == []
        assert listing[7][0] == "language"

    def test_default_is_the_summary_alone(self, tree, run):
        out = run()
        assert out.startswith("language")
        assert "pkg.py" not in out

    def test_categories_without_lines_are_left_out(self, tmp_path, monkeypatch, run):
        (tmp_path / "pkg.py").write_text("x = 1\n")
        monkeypatch.chdir(tmp_path)
        assert rows(run())[0] == ["language", "NUMFILES", "code", "SUM"]

    def test_nothing_cells_show_a_dot(self, tree, run):
        out = run("-v")
        line = next(line for line in out.splitlines() if line.endswith("README.md"))
        # markdown knows only doc lines; a dot holds the other columns
        assert line == "  2         .      .      .     2   README.md"

    def test_rows_sorted_by_sum(self, tree, run):
        listing = [row[0] for row in rows(run()) if row]
        assert (
            listing.index("python") < listing.index("rust") < listing.index("markdown")
        )

    def test_row_shares(self, tree, run):
        table = {row[0]: row for row in rows(run("-r"))}
        # the row's SUM is the reference and reads [100%]
        assert table["python"] == list(
            (
                "python",
                "2",
                ".",
                "1",
                "[25%]",
                "2",
                "[50%]",
                "1",
                "[25%]",
                "4",
                "[100%]",
            )
        )
        # the total row is no row like the others and stays raw
        assert table["total"] == ["total", "5", "2", "1", "4", "2", "9"]

    def test_column_shares(self, tree, run):
        table = {row[0]: row for row in rows(run("-c"))}
        # the column totals are the reference
        # and the SUM column stays raw
        assert table["markdown"] == list(
            ("markdown", "1", "2", "[100%]", ".", ".", ".", "2")
        )
        assert table["total"] == list(
            (
                "total",
                "5",
                "2",
                "[100%]",
                "1",
                "[100%]",
                "4",
                "[100%]",
                "2",
                "[100%]",
                "9",
            )
        )

    def test_file_rows_with_row_shares(self, tree, run):
        listing = rows(run("-v", "-r"))
        assert listing[2] == [
            ".",
            ".",
            "2",
            "[67%]",
            "1",
            "[33%]",
            "3",
            "[100%]",
            "lib.rs",
        ]

    def test_rows_and_columns_exclude_each_other(self, run, capsys):
        with pytest.raises(SystemExit):
            run("-r", "-c")

    def test_media_files_are_counted_never_read(self, tmp_path, monkeypatch, run):
        (tmp_path / "logo.png").write_bytes(b"\x89PNG binary")
        (tmp_path / "app.py").write_text("x = 1\n")
        monkeypatch.chdir(tmp_path)
        out = run("-vv")
        assert "unknown" not in out
        assert ["python", "1", "1", "1"] in rows(out)
        assert ["png", "1", ".", "."] in rows(out)

    def test_github_workflows_are_counted(self, tmp_path, monkeypatch, run):
        (tmp_path / ".github/workflows").mkdir(parents=True)
        (tmp_path / ".github/workflows/ci.yml").write_text("# ci\njobs:\n")
        (tmp_path / ".hidden").mkdir()
        (tmp_path / ".hidden/skip.py").write_text("x = 1\n")
        monkeypatch.chdir(tmp_path)
        listing = rows(run("-v"))
        assert listing[2] == ["1", "1", "2", ".github/workflows/ci.yml"]
        assert listing[6] == ["yaml", "1", "1", "1", "2"]
        assert not any("skip.py" in " ".join(row) for row in listing)

    def test_empty_directory(self, tmp_path, monkeypatch, run):
        monkeypatch.chdir(tmp_path)
        assert run() == "no counted files\n"

    def test_paths_win_over_stdin(self, tmp_path, run):
        make_tree(tmp_path)
        out = run(str(tmp_path), stdin=DIFF)
        assert "language" in out
        assert "added" not in out


class TestCategoryViews:
    def test_one_category(self, tree, run):
        listing = rows(run("--code"))
        assert listing[0] == ["language", "code"]
        assert listing[2] == ["python", "1", "[50%]"]
        assert listing[3] == ["rust", "1", "[50%]"]
        assert listing[-1] == ["total", "2", "[100%]"]

    def test_several_categories(self, tree, run):
        listing = rows(run("--test", "--code"))
        assert listing[0] == ["language", "test", "code"]
        assert listing[2] == ["python", "2", "[50%]", "1", "[50%]"]
        assert listing[-1] == ["total", "4", "[100%]", "2", "[100%]"]

    def test_files_without_the_category_are_left_out(self, tree, run):
        listing = rows(run("--test", "-v"))
        assert listing[0] == ["test", "file"]
        assert listing[2] == ["2", "[50%]", "lib.rs"]
        assert listing[3] == ["2", "[50%]", "tests/test_pkg.py"]
        assert listing[4] == []
        assert not any("pkg.py" == row[-1] for row in listing if row)

    def test_language_view(self, tree, run):
        out = run("--python", "-v")
        listing = rows(out)
        assert listing[0] == ["comment", "test", "code", "SUM", "file"]
        assert listing[2] == ["1", ".", "1", "2", "pkg.py"]
        assert "lib.rs" not in out
        assert listing[5] == ["category", "python"]
        assert listing[7] == ["comment", "1", "[25%]"]
        assert listing[8] == ["test", "2", "[50%]"]
        assert listing[-1] == ["total", "4", "[100%]"]

    def test_language_and_category(self, tree, run):
        listing = rows(run("--python", "--test", "-v"))
        assert listing[0] == ["test", "file"]
        assert listing[2] == ["2", "[100%]", "tests/test_pkg.py"]
        assert listing[4] == ["category", "python"]
        assert listing[6] == ["test", "2", "[100%]"]

    def test_language_without_the_category(self, tree, run):
        assert run("--markdown", "--test") == "no counted lines\n"


class TestJson:
    def test_counts(self, tree, run):
        data = json.loads(run("--json"))
        assert data["languages"]["python"] == {
            "files": 2,
            "comment": 1,
            "test": 2,
            "code": 1,
        }
        # zero categories are left out, like the dot cells
        assert data["languages"]["markdown"] == {"files": 1, "doc": 2}
        assert data["total"] == {
            "files": 4,
            "doc": 2,
            "comment": 1,
            "test": 4,
            "code": 2,
        }
        assert data["unknown_files"] == 1
        assert "files" not in data

    def test_verbosity_adds_files_and_unknown(self, tree, run):
        data = json.loads(run("--json", "-vv"))
        assert data["files"]["pkg.py"] == {
            "language": "python",
            "comment": 1,
            "code": 1,
        }
        assert data["unknown"] == ["data.bin"]

    def test_with_empty_and_category_filters_apply(self, tree, run):
        data = json.loads(run("--json", "--with-empty"))
        assert data["languages"]["python"]["empty"] == 1
        data = json.loads(run("--json", "--test"))
        assert data["languages"]["python"] == {"files": 2, "test": 2}

    def test_diff(self, run):
        data = json.loads(run("--json", stdin=DIFF))
        assert data["added"]["rust"] == {"comment": 1, "test": 2, "code": 1}
        assert data["removed"] == {"python": {"code": 1}, "rust": {"code": 1}}
        assert data["total"] == {"added": 5, "removed": 2}
        assert "files" not in data
        data = json.loads(run("--json", "-v", stdin=DIFF))
        assert data["files"]["src/lib.rs"] == {"added": 4, "removed": 1}


class TestDiffCli:
    def test_stdin_is_autodetected(self, run):
        out = run(stdin=DIFF)
        assert rows(out)[0] == ["category", "added", "removed", "net"]
        listing = rows(run("-v", stdin=DIFF))
        assert listing[0] == ["added", "removed", "net", "file"]
        assert listing[2] == ["+4", "-1", "+3", "src/lib.rs"]
        assert listing[3] == ["+1", "-1", "+0", "tool.py"]
        assert listing[5][0] == "category"
        assert listing[-1] == ["total", "+5", "-2", "+3"]

    def test_rows_grouped_by_category(self, run):
        listing = rows(run(stdin=DIFF))
        assert [row[:2] for row in listing[2:-2]] == [
            ["comment", "rust"],
            ["test", "rust"],
            ["code", "python"],
            ["code", "rust"],
        ]

    def test_headerless_diff_is_autodetected(self, run):
        headerless = "\n".join(
            line for line in DIFF.splitlines() if not line.startswith("diff ")
        )
        assert ["test", "rust"] in [row[:2] for row in rows(run(stdin=headerless))]

    def test_language_filter(self, run):
        out = run("--python", "-v", stdin=DIFF)
        assert rows(out)[2] == ["+1", "-1", "+0", "tool.py"]
        assert "lib.rs" not in out
        assert rows(out)[-1] == ["total", "+1", "-1", "+0"]

    def test_category_filter(self, run):
        out = run("--test", "-v", stdin=DIFF)
        listing = rows(out)
        assert listing[2] == ["+2", "-0", "+2", "src/lib.rs"]
        assert listing[6] == ["test", "rust", "+2", "-0", "+2"]
        assert listing[-1] == ["total", "+2", "-0", "+2"]
        assert "tool.py" not in out

    def test_config_rows(self, run):
        diff = """\
diff --git a/doveauth.service.f b/doveauth.service.f
--- a/doveauth.service.f
+++ b/doveauth.service.f
@@ -1,2 +1,3 @@
 [Unit]
+Restart=always
"""
        listing = rows(run(stdin=diff))
        assert listing[0] == ["category", "added", "removed", "net"]
        assert listing[2] == ["config", "systemd", "+1", "-0", "+1"]
        assert listing[-1] == ["total", "+1", "-0", "+1"]

    def test_empty_lines_need_with_empty(self, run):
        diff = """\
diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1,2 +1,4 @@
 # title
+
+new sentence
"""
        listing = rows(run(stdin=diff))
        assert listing[2] == ["doc", "markdown", "+1", "-0", "+1"]
        assert listing[-1] == ["total", "+1", "-0", "+1"]
        listing = rows(run("--with-empty", stdin=diff))
        assert listing[2] == ["empty", "markdown", "+1", "-0", "+1"]
        assert listing[3] == ["doc", "markdown", "+1", "-0", "+1"]
        assert listing[-1] == ["total", "+2", "-0", "+2"]

    def test_file_without_counted_changes_is_left_out(self, run):
        diff = """\
diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1,2 +1,3 @@
 # title
+
"""
        assert run(stdin=diff) == "no counted changes\n"

    def test_verbose_lists_unknown_files(self, run):
        out = run("-vv", stdin=DIFF.replace("logo.png", "blob.bin"))
        assert "unknown files in diff:" in out
        assert "blob.bin" in out

    def test_text_on_stdin_is_rejected(self, run):
        with pytest.raises(SystemExit, match="not a git diff"):
            run(stdin="just some text\n")


class TestPager:
    def test_tty_output_is_paged_with_styles(self, tree, monkeypatch):
        class Tty(io.StringIO):
            def isatty(self):
                return True

        monkeypatch.setenv("PAGER", "sh -c 'cat >paged.txt'")
        monkeypatch.setattr("sys.stdin", io.StringIO(""))
        monkeypatch.setattr("sys.stdout", Tty())
        main([])
        paged = (tree / "paged.txt").read_text()
        assert "language" in paged
        assert "\x1b[1m" in paged  # bold survives into the pager

    def test_pager_cat_and_pipes_stay_plain(self, tree, run, monkeypatch):
        monkeypatch.setenv("PAGER", "cat")
        out = run()
        assert "\x1b[" not in out  # capsys stdout is no tty: no pager, no color


class TestTerminal:
    def test_broken_pipe_exits_quietly(self, tree, monkeypatch):
        with open(tree / "sink", "w") as sink:

            class Broken:
                def write(self, text):
                    raise BrokenPipeError

                def flush(self):
                    raise BrokenPipeError

                def fileno(self):
                    return sink.fileno()

            monkeypatch.setattr("sys.stdin", io.StringIO(""))
            monkeypatch.setattr("sys.stdout", Broken())
            with pytest.raises(SystemExit) as exc:
                main([])
        assert exc.value.code == 1

    def test_bash_completion_script(self, run):
        out = run("--completion")
        assert "complete -o default -o bashdefault -F _srcloc srcloc" in out
        for flag in ("--code", "--doc", "--config", "--with-empty", "--help"):
            assert flag in out
