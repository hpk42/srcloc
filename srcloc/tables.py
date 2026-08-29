"""Aligned, styled terminal tables built from plain cells."""

import os
import re

SHARE_TAIL = re.compile(r"^ \[(<?\d+)%\]$")

# A cell with nothing to say: a dim dot keeps the row readable.
DOT = (".", "dim")


def styler(out):
    """Painter for styles like "bold" or "bold green".

    A no-op off a terminal. Only attributes and the palette's own red
    and green are used, so light and dark themes both stay readable.
    """
    if os.environ.get("NO_COLOR") or not getattr(out, "isatty", lambda: False)():
        return lambda text, style: text
    codes = {"bold": "1", "dim": "2", "red": "31", "green": "32"}

    def paint(text, style):
        if not style:
            return text
        nums = ";".join(codes[name] for name in style.split())
        return f"\x1b[{nums}m{text}\x1b[0m"

    return paint


def show_table(rows, out, left=()):
    """Print rows of cells aligned, the widths taken from the data.

    A cell is a string, a (text, style) pair, or a list of pairs;
    row 0 is the header, a None row prints a dim rule, the columns
    in left are left-aligned. Bracketed shares widen to the column's
    widest so that the counts before them stay aligned.
    """

    def cell_text(cell):
        return "".join(part for part, _ in cell)

    def fragments(cell):
        if isinstance(cell, str):
            return [(cell, "")]
        if isinstance(cell, tuple):
            return [cell]
        return cell

    rows = [row if row is None else [fragments(cell) for cell in row] for row in rows]
    data = [row for row in rows if row is not None]
    for column in zip(*data):
        shares = [
            (cell, match) for cell in column if (match := SHARE_TAIL.match(cell[-1][0]))
        ]
        if not shares:
            continue
        width = max(len(match.group(1)) for _, match in shares)
        for cell, match in shares:
            cell[-1] = (f" [{match.group(1):>{width}}%]", cell[-1][1])
    widths = [max(len(cell_text(cell)) for cell in column) for column in zip(*data)]
    paint = styler(out)
    rule = paint("   ".join("-" * width for width in widths), "dim")
    for number, row in enumerate(rows):
        if row is None:
            print(rule, file=out)
            continue
        parts = []
        for i, cell in enumerate(row):
            pad = widths[i] - len(cell_text(cell))
            painted = "".join(paint(part, style) for part, style in cell)
            if i in left:
                parts.append(painted + " " * pad)
            elif number == 0:
                parts.append(" " * (pad // 2) + painted + " " * (pad - pad // 2))
            else:
                parts.append(" " * pad + painted)
        print("   ".join(parts).rstrip(), file=out)


def count_cell(count, style=""):
    """A plain count, a dim dot for nothing."""
    return (str(count), style) if count else DOT


def share_cell(count, total, style=""):
    """A count with its rounded share; what rounds away shows as <1%,
    nothing as a dim dot; bold cells carry a bold share."""
    if not count:
        return DOT
    share = round(100 * count / total)
    return [(str(count), style), (f" [{share or '<1'}%]", style or "dim")]


def diff_row(plus, minus, style=""):
    """Added, removed and net cells, only the net one colored."""
    cells = [f"{plus:+}", f"-{minus}", f"{plus - minus:+}"]
    styles = ["dim" if cell in ("+0", "-0") else "" for cell in cells[:-1]]
    styles.append("dim" if plus == minus else "green" if plus > minus else "red")
    return [(cell, f"{style} {own}".strip()) for cell, own in zip(cells, styles)]
