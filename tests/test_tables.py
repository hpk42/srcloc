import io
import re
from collections import Counter
from pathlib import Path

import pytest

from srcloc.langs import CATEGORIES
from srcloc.tables import show_table
from srcloc.views import (
    print_counts,
    print_diff_counts,
    print_files,
    print_shares,
)


class Tty(io.StringIO):
    def isatty(self):
        return True


ANSI = re.compile(r"\x1b\[[0-9;]*m")

CATS = list(CATEGORIES)


def rows(out):
    """Table lines as token lists, the share padding collapsed."""
    return [re.sub(r"\[ +", "[", line).split() for line in out.splitlines()]


def rendered(call):
    """The plain and the terminal rendering of one table."""
    plain, colored = io.StringIO(), Tty()
    call(plain)
    call(colored)
    return plain.getvalue(), colored.getvalue()


class TestShowTable:
    def test_widths_from_data_and_left_columns(self):
        out = io.StringIO()
        show_table(
            [
                [("h1", "bold"), ("h2", "bold"), ("file", "bold")],
                None,
                ["10", [("2", ""), ("/50%", "dim")], "a.py"],
                ["5", ("-", "dim"), "some/longer/path.rs"],
            ],
            out,
            left={2},
        )
        assert out.getvalue() == (
            "h1    h2     file\n"
            "--   -----   -------------------\n"
            "10   2/50%   a.py\n"
            " 5       -   some/longer/path.rs\n"
        )

    def test_share_padding_keeps_brackets_stable(self):
        out = io.StringIO()
        show_table(
            [
                [("h", "bold")],
                [[("1707", ""), (" [10%]", "dim")]],
                [[("10984", ""), (" [9%]", "dim")]],
                [[("6", ""), (" [100%]", "dim")]],
            ],
            out,
        )
        assert out.getvalue() == "     h\n 1707 [ 10%]\n10984 [  9%]\n    6 [100%]\n"


COUNTS = Counter(
    {
        ("python", "files"): 2,
        ("python", "code"): 3,
        ("python", "comment"): 1,
        ("python", "test"): 2,
        ("python", "empty"): 2,
        ("markdown", "files"): 1,
        ("markdown", "doc"): 4,
        ("unknown", "files"): 1,
    }
)

PER_FILE = [(Path("a.md"), Path("a.md"), Counter({"doc": 2, "empty": 1}))]

ADDED = Counter({("python", "code"): 3, ("python", "empty"): 1})

REMOVED = Counter({("python", "code"): 5})


class TestColor:
    @pytest.fixture(autouse=True)
    def clear_no_color(self, monkeypatch):
        monkeypatch.delenv("NO_COLOR", raising=False)

    @pytest.mark.parametrize(
        "call",
        [
            lambda out: print_counts(COUNTS, CATS, out),
            lambda out: print_files(PER_FILE, CATS, out),
            lambda out: print_diff_counts(ADDED, REMOVED, CATS, out),
            lambda out: print_shares("language", ["code"], [("py", [3])], out),
        ],
    )
    def test_color_never_shifts_columns(self, call):
        plain, colored = rendered(call)
        assert "\x1b[" in colored
        assert ANSI.sub("", colored) == plain

    def test_counts_bold_headers_and_dim_rules(self):
        _, colored = rendered(lambda out: print_counts(COUNTS, CATS, out))
        assert "\x1b[1mlanguage" in colored
        assert "\x1b[2m---" in colored  # rules
        assert "\x1b[2m." in colored  # nothing-cells

    def test_reference_shares_are_bold(self):
        _, colored = rendered(lambda out: print_counts(COUNTS, CATS, out, "row"))
        assert "\x1b[1m [100%]\x1b[0m" in colored  # the reference marker

    def test_diff_colors_only_the_net_column(self):
        _, colored = rendered(lambda out: print_diff_counts(ADDED, REMOVED, CATS, out))
        assert "\x1b[31m-2" in colored
        assert "\x1b[32m+1" in colored
        assert "\x1b[2m-0" in colored
        assert "\x1b[32m+3" not in colored
        assert "\x1b[31m-5" not in colored

    def test_no_color_wins_over_tty(self, monkeypatch):
        monkeypatch.setenv("NO_COLOR", "1")
        plain, colored = rendered(lambda out: print_counts(COUNTS, CATS, out))
        assert colored == plain
