"""The command line: argument parsing and the two main modes."""

import argparse
import contextlib
import json
import os
import shlex
import subprocess
import sys
from collections import Counter

from .collect import count_changed, count_file, discover, looks_like_diff, parse_diff
from .langs import CATEGORIES, LANGS, file_lang
from .views import (
    counts_json,
    diff_json,
    print_category_counts,
    print_counts,
    print_diff_counts,
    print_diff_files,
    print_files,
    print_language_counts,
    print_share_files,
    print_unknown,
)

BASH_COMPLETION = """\
_srcloc() {{
    local cur=${{COMP_WORDS[COMP_CWORD]}}
    COMPREPLY=()
    if [[ $cur == -* ]]; then
        COMPREPLY=($(compgen -W "{flags}" -- "$cur"))
    fi
}}
complete -o default -o bashdefault -F _srcloc srcloc"""


def output_pager():
    """A git-like pager on a terminal:
    $PAGER, defaulting to less, which quits
    by itself when one screen suffices (-F)."""
    if not getattr(sys.stdout, "isatty", lambda: False)():
        return None
    command = shlex.split(os.environ.get("PAGER") or "less")
    if command in ([], ["cat"]):
        return None
    env = dict(os.environ)
    env.setdefault("LESS", "FRX")
    try:
        return subprocess.Popen(command, stdin=subprocess.PIPE, text=True, env=env)
    except OSError:
        return None


class Paged:
    """stdout writing into the pager, still a terminal
    to the styler so colors survive into less -R."""

    def __init__(self, proc):
        self.proc = proc

    def write(self, text):
        return self.proc.stdin.write(text)

    def flush(self):
        self.proc.stdin.flush()

    def isatty(self):
        return True


def read_stdin():
    if sys.stdin is None or sys.stdin.isatty():
        return ""
    try:
        return sys.stdin.read()
    except OSError:
        return ""


def selected_cats(args):
    return [cat for cat in CATEGORIES if getattr(args, cat)]


def shown_cats(args):
    """Those a flag chose, else all but empty, which needs --with-empty."""
    return selected_cats(args) or [
        cat for cat in CATEGORIES if cat != "empty" or args.with_empty
    ]


def share_mode(args):
    return "row" if args.rows else "col" if args.columns else None


def selected_langs(args):
    return [lang for lang in LANGS if getattr(args, f"lang_{lang}", False)]


def diff_main(text, args, out):
    added = Counter()
    removed = Counter()
    unknown = []
    per_file = []
    cats = shown_cats(args)
    langs = selected_langs(args)
    for old_path, new_path, old_doc, new_doc in parse_diff(text.splitlines()):
        rel = new_path or old_path
        lang = file_lang(rel)
        if lang is None:
            unknown.append(str(rel))
            continue
        if langs and lang not in langs:
            continue
        file_added = Counter()
        file_removed = Counter()
        if old_path is not None:
            count_changed(old_path, old_doc, file_removed)
        if new_path is not None:
            count_changed(new_path, new_doc, file_added)
        added.update(file_added)
        removed.update(file_removed)
        if args.verbose:
            per_file.append((str(rel), file_added, file_removed))
    if args.json:
        print(
            json.dumps(diff_json(added, removed, per_file, unknown, cats, args)),
            file=out,
        )
        return
    if per_file and print_diff_files(per_file, cats, out):
        print(file=out)
    print_diff_counts(added, removed, cats, out)
    if args.verbose > 1 and unknown:
        print_unknown(unknown, "unknown files in diff", out)


def count_main(args, out):
    counts = Counter()
    unknown = []
    per_file = []
    selected = selected_cats(args)
    cats = shown_cats(args)
    langs = selected_langs(args)
    for path, rel in discover(args.paths or ["."]):
        kinds = count_file(path, rel, counts)
        if kinds is None:
            unknown.append(str(path))
        elif args.verbose and (not langs or file_lang(rel) in langs):
            per_file.append((path, rel, kinds))
    if args.json:
        print(json.dumps(counts_json(counts, per_file, unknown, cats, args)), file=out)
        return
    if per_file:
        shown = (
            print_share_files(per_file, cats, out)
            if selected
            else print_files(per_file, cats, out, share_mode(args))
        )
        if shown:
            print(file=out)
    if langs:
        print_language_counts(counts, langs, cats, out)
    elif selected:
        print_category_counts(counts, cats, out)
    else:
        print_counts(counts, cats, out, share_mode(args))
    if args.verbose > 1 and unknown:
        print_unknown(unknown, "unknown files", out)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="srcloc",
        description="count doc, comment, config, testdata, test and code"
        " lines in source trees",
        epilog="a git diff piped on stdin is compared instead of counted;"
        " every language row name is a flag too: --python, --rust,"
        " --toml, ... shows that language with the categories as rows",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        metavar="PATH",
        help="files or directories to count (default: current directory);"
        " directories under git only count versioned and new files",
    )
    for cat in CATEGORIES:
        parser.add_argument(
            f"--{cat}",
            action="store_true",
            help=f"show only the {cat} distribution across languages",
        )
    for lang in LANGS:
        if lang != "json":  # --json is the output mode
            parser.add_argument(
                f"--{lang}",
                dest=f"lang_{lang}",
                action="store_true",
                help=argparse.SUPPRESS,
            )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print one JSON object instead of tables; schema in the README",
    )
    shares = parser.add_mutually_exclusive_group()
    shares.add_argument(
        "-r",
        "--rows",
        action="store_true",
        help="show each count's percent of its row's SUM",
    )
    shares.add_argument(
        "-c",
        "--columns",
        action="store_true",
        help="show each count's percent of its column's total",
    )
    parser.add_argument(
        "--with-empty",
        action="store_true",
        help="count empty lines as an own category",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="show more: -v the per-file table, -vv also the unknown files",
    )
    parser.add_argument(
        "--completion",
        action="store_true",
        help='print the bash completion script; eval "$(srcloc --completion)"',
    )
    args = parser.parse_args(argv)
    pager = None
    try:
        if args.completion:
            flags = [f for action in parser._actions for f in action.option_strings]
            print(BASH_COMPLETION.format(flags=" ".join(flags)))
            sys.stdout.flush()
            return
        text = "" if args.paths else read_stdin()
        if text.strip() and not looks_like_diff(text):
            raise SystemExit(
                "srcloc: stdin is not a git diff; pass PATH arguments to count files"
            )
        pager = output_pager()
        out = Paged(pager) if pager else sys.stdout
        if text.strip():
            diff_main(text, args, out)
        else:
            count_main(args, out)
        out.flush()
        if pager:
            pager.stdin.close()
            pager.wait()
    except BrokenPipeError:
        if pager is not None:
            # quitting the pager early is a clean exit
            with contextlib.suppress(BrokenPipeError):
                pager.stdin.close()
            pager.wait()
            return
        # `srcloc | head` closes stdout early; exit like other tools do.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        raise SystemExit(1) from None
