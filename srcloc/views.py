"""The output views: count, share and diff tables, and their JSON."""

from collections import Counter

from .langs import LANGS, file_lang
from .tables import DOT, count_cell, diff_row, share_cell, show_table


def column_totals(rows, cats):
    """Per-category totals plus their overall sum, the -c references."""
    totals = Counter()
    for values in rows:
        totals.update({cat: values[cat] for cat in cats})
    totals["sum"] = sum(totals[cat] for cat in cats)
    return totals


def mode_cells(values, cats, totals, mode, style=""):
    """The category cells and the bold SUM cell of one row.

    -r turns the counts into shares of the row's SUM,
    which then reads [100%]; -c into shares
    of the column totals, and the SUM column stays raw.
    """
    lines = sum(values[cat] for cat in cats)
    if mode == "row":
        cells = [share_cell(values[cat], lines, style) for cat in cats]
        return [*cells, share_cell(lines, lines, "bold")]
    if mode == "col":
        cells = [share_cell(values[cat], totals[cat], style) for cat in cats]
    else:
        cells = [count_cell(values[cat], style) for cat in cats]
    return [*cells, count_cell(lines, "bold")]


def print_files(per_file, cats, out, mode=None):
    """Per-file counts, most lines first, the path last to keep them aligned."""
    cats = [cat for cat in cats if any(kinds[cat] for _, _, kinds in per_file)]
    totals = column_totals([kinds for _, _, kinds in per_file], cats)
    rows = []
    for path, _, kinds in per_file:
        total = sum(kinds[cat] for cat in cats)
        rows.append((total, str(path), mode_cells(kinds, cats, totals, mode)))
    rows.sort(key=lambda row: (-row[0], row[1]))
    header = [(name, "bold") for name in (*cats, "SUM", "file")]
    table = [header, None] + [[*cells, name] for _, name, cells in rows]
    total = mode_cells(totals, cats, totals, mode if mode == "col" else None, "bold")
    table += [None, [*total, ("total", "bold")]]
    show_table(table, out, left={len(header) - 1})
    return True


def print_share_files(per_file, cats, out):
    """Per-file shares of the chosen categories, files without them left out."""
    totals = Counter()
    for _, _, kinds in per_file:
        totals.update({cat: kinds[cat] for cat in cats})
    rows = []
    for path, _, kinds in per_file:
        if not any(kinds[cat] for cat in cats):
            continue
        cells = [share_cell(kinds[cat], totals[cat]) for cat in cats]
        rows.append((kinds[cats[0]], str(path), cells))
    if not rows:
        return False
    rows.sort(key=lambda row: (-row[0], row[1]))
    table = [[*((cat, "bold") for cat in cats), ("file", "bold")], None]
    table += [[*cells, name] for _, name, cells in rows]
    total = [share_cell(totals[cat], totals[cat], "bold") for cat in cats]
    table += [None, [*total, ("total", "bold")]]
    show_table(table, out, left={len(cats)})
    return True


def print_shares(head, cols, rows, out, sort=False):
    """A share table, every column summing to 100%."""
    if sort:
        rows = sorted(rows, key=lambda row: -row[1][0])
    totals = [sum(column) for column in zip(*(values for _, values in rows))]

    def cells(values, style=""):
        return [share_cell(value, total, style) for value, total in zip(values, totals)]

    table = [[(head, "bold"), *((col, "bold") for col in cols)], None]
    table += [[label, *cells(values)] for label, values in rows]
    table += [None, [("total", "bold"), *cells(totals, "bold")]]
    show_table(table, out, left={0})


def print_category_counts(counts, cats, out):
    """The chosen categories spread over the languages, largest first."""
    langs = [lang for lang in LANGS if any(counts[lang, cat] for cat in cats)]
    if not langs:
        print("no counted lines", file=out)
        return
    rows = [(lang, [counts[lang, cat] for cat in cats]) for lang in langs]
    print_shares("language", cats, rows, out, sort=True)


def print_language_counts(counts, langs, cats, out):
    """The chosen languages transposed, categories as rows."""
    langs = [lang for lang in langs if counts[lang, "files"]]
    cats = [cat for cat in cats if any(counts[lang, cat] for lang in langs)]
    if not cats:
        print("no counted lines", file=out)
        return
    rows = [(cat, [counts[lang, cat] for lang in langs]) for cat in cats]
    print_shares("category", langs, rows, out)


def print_counts(counts, cats, out, mode=None):
    langs = [lang for lang in LANGS if counts[lang, "files"]]
    unknown = counts["unknown", "files"]
    if not langs and not unknown:
        print("no counted files", file=out)
        return
    cats = [cat for cat in cats if any(counts[lang, cat] for lang in langs)]
    values = {
        lang: {key: counts[lang, key] for key in ("files", *cats)} for lang in langs
    }
    totals = column_totals(values.values(), cats)
    rows = [(sum(row[cat] for cat in cats), lang, row) for lang, row in values.items()]
    rows.sort(key=lambda row: -row[0])
    rows = [
        [lang, count_cell(row["files"]), *mode_cells(row, cats, totals, mode)]
        for _, lang, row in rows
    ]
    if unknown:
        rows.append(["unknown", str(unknown), *[DOT] * (len(cats) + 1)])
    header = [(name, "bold") for name in ("language", "NUMFILES", *cats, "SUM")]
    table = [header, None, *rows]
    if len(langs) > 1:
        files = sum(row["files"] for row in values.values()) + unknown
        total_row = [
            ("total", "bold"),
            count_cell(files, "bold"),
            # the total row is the -c reference and shows [100%] there;
            # under -r it is no row like the others and stays raw
            *mode_cells(totals, cats, totals, mode if mode == "col" else None, "bold"),
        ]
        table += [None, total_row]
    show_table(table, out, left={0})


def changed_lines(changed, cats):
    """Changed lines of one file over the shown categories."""
    return sum(count for (_, cat), count in changed.items() if cat in cats)


def print_diff_files(per_file, cats, out):
    """Per-file added, removed and net, most changed lines first."""
    rows = []
    for name, file_added, file_removed in per_file:
        plus = changed_lines(file_added, cats)
        minus = changed_lines(file_removed, cats)
        if plus or minus:
            rows.append((plus + minus, name, diff_row(plus, minus)))
    if not rows:
        return False
    rows.sort(key=lambda row: (-row[0], row[1]))
    table = [[(name, "bold") for name in ("added", "removed", "net", "file")], None]
    table += [[*cells, name] for _, name, cells in rows]
    show_table(table, out, left={3})
    return True


def print_diff_counts(added, removed, cats, out):
    """Added, removed and net per category and language, the category
    first and padded so that the languages line up under each other."""
    rows = []
    total_plus = total_minus = 0
    for cat in cats:
        for lang in LANGS:
            plus, minus = added[lang, cat], removed[lang, cat]
            if not plus and not minus:
                continue
            total_plus += plus
            total_minus += minus
            rows.append((cat, lang, diff_row(plus, minus)))
    if not rows:
        print("no counted changes", file=out)
        return
    width = max(len(cat) for cat, _, _ in rows)
    table = [[(name, "bold") for name in ("category", "added", "removed", "net")], None]
    table += [[f"{cat:<{width}} {lang}", *cells] for cat, lang, cells in rows]
    table += [None, [("total", "bold"), *diff_row(total_plus, total_minus, "bold")]]
    show_table(table, out, left={0})


def print_unknown(unknown, label, out):
    print(f"\n{label}:", file=out)
    for name in unknown:
        print(f"  {name}", file=out)


def nonzero(counts, keys):
    """The nonzero entries, in key order;
    JSON leaves out what the tables render as a dot."""
    return {key: counts[key] for key in keys if counts[key]}


def counts_json(counts, per_file, unknown, cats, args):
    langs = [lang for lang in LANGS if counts[lang, "files"]]
    rows = {
        lang: {"files": counts[lang, "files"]}
        | nonzero({cat: counts[lang, cat] for cat in cats}, cats)
        for lang in langs
    }
    total = Counter()
    for row in rows.values():
        total.update(row)
    data = {"languages": rows, "total": nonzero(total, ("files", *cats))}
    if unknown:
        data["unknown_files"] = len(unknown)
    if args.verbose:
        data["files"] = {
            str(path): {"language": file_lang(rel)} | nonzero(kinds, cats)
            for path, rel, kinds in per_file
        }
    if args.verbose > 1 and unknown:
        data["unknown"] = unknown
    return data


def diff_json(added, removed, per_file, unknown, cats, args):
    def side(changed):
        rows = {
            lang: nonzero({cat: changed[lang, cat] for cat in cats}, cats)
            for lang in LANGS
        }
        return {lang: row for lang, row in rows.items() if row}

    data = {
        "added": side(added),
        "removed": side(removed),
        "total": {
            "added": changed_lines(added, cats),
            "removed": changed_lines(removed, cats),
        },
    }
    if args.verbose:
        data["files"] = {
            name: {
                "added": changed_lines(file_added, cats),
                "removed": changed_lines(file_removed, cats),
            }
            for name, file_added, file_removed in per_file
        }
    if args.verbose > 1 and unknown:
        data["unknown"] = unknown
    return data
