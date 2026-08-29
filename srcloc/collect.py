"""Input gathering: tree walking, file counting and diff parsing."""

import os
import re
import subprocess
from collections import Counter
from pathlib import Path

from .kinds import line_kinds
from .langs import MEDIA, file_lang

DIFF_HEADER = re.compile(r"^diff --git a/(.+) b/(.+)$")


def count_file(path, rel, counts):
    """Count one file, None when it stays uncounted."""
    lang = file_lang(rel)
    if lang is None:
        counts["unknown", "files"] += 1
        return None
    if lang in MEDIA:
        counts[lang, "files"] += 1
        return Counter()
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        counts["unknown", "files"] += 1
        return None
    counts[lang, "files"] += 1
    kinds = Counter(line_kinds(rel, text))
    counts.update({(lang, kind): count for kind, count in kinds.items()})
    return kinds


def excluded(
    rel,
    names=frozenset(
        {"venv", "env", "node_modules", "target", "build", "dist", "__pycache__"}
    ),
):
    """Ephemeral state, never counted, also where a repository
    tracks it; of the dot directories only .github counts."""
    return any(
        part in names
        or (part.startswith(".") and part != ".github")
        or part.endswith(".egg-info")
        for part in rel.parts
    )


def iter_dir(directory):
    """Yield paths relative to directory, from git where it answers.

    ls-files also reports untracked but unignored files,
    so work in progress counts while ignored state does not.
    """
    ls_files = "ls-files -z --cached --others --exclude-standard".split()
    try:
        listed = subprocess.run(
            ["git", "-C", str(directory), *ls_files],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        listed = None
    if listed and not listed.returncode:
        for name in listed.stdout.split("\0"):
            if name:
                yield Path(name)
        return
    for parent, dirnames, filenames in os.walk(directory):
        rel_parent = Path(parent).relative_to(directory)
        dirnames[:] = sorted(
            name for name in dirnames if not excluded(rel_parent / name)
        )
        for name in sorted(filenames):
            yield rel_parent / name


def seems_file(path):
    """stat may be forbidden, as on TLS keys in a root-only directory;
    keep such paths and let the failing read count them as unknown."""
    try:
        return path.is_file()
    except OSError:
        return True


def discover(targets):
    """Yield (path on disk, path for classification) pairs."""
    for target in targets:
        top = Path(target)
        if seems_file(top):
            yield top, Path(top.name) if top.is_absolute() else top
        elif top.is_dir():
            for rel in iter_dir(top):
                path = top / rel
                if not excluded(rel) and seems_file(path):
                    yield path, rel
        else:
            raise SystemExit(f"srcloc: no such file or directory: {target}")


def parse_diff(lines):
    """Split a unified diff into per-file old and new documents.

    Yields (old path, new path, old doc, new doc),
    where a doc pairs each line with a changed flag:
    the context plus one side's changed lines in order,
    so the classifiers see each version as a whole.
    """

    def strip_prefix(name):
        if name in ("/dev/null", ""):
            return None
        if name.startswith(("a/", "b/")):
            name = name[2:]
        return Path(name)

    header = old_path = new_path = None
    old_doc = []
    new_doc = []
    in_hunk = False

    def flush():
        old, new = old_path, new_path
        if old is None and new is None and header is not None:
            match = DIFF_HEADER.match(header)  # an entry without hunks, binary say
            if match:
                old, new = Path(match.group(1)), Path(match.group(2))
        if old is not None or new is not None:
            yield old, new, old_doc, new_doc

    for line in lines:
        if line.startswith("diff "):
            yield from flush()
            header = line
            old_path = new_path = None
            old_doc = []
            new_doc = []
            in_hunk = False
        elif line.startswith("--- ") and not in_hunk:
            old_path = strip_prefix(line[4:].split("\t")[0])
        elif line.startswith("+++ ") and not in_hunk:
            new_path = strip_prefix(line[4:].split("\t")[0])
        elif line.startswith("@@"):
            in_hunk = True
        elif in_hunk and (not line or line.startswith(" ")):
            old_doc.append((line[1:], False))
            new_doc.append((line[1:], False))
        elif in_hunk and line.startswith("-"):
            old_doc.append((line[1:], True))
        elif in_hunk and line.startswith("+"):
            new_doc.append((line[1:], True))
        elif in_hunk and line.startswith("\\"):
            pass  # "No newline at end of file"
        else:
            in_hunk = False
    yield from flush()


def count_changed(rel, doc, counts):
    """Add the document's changed lines to counts."""
    kinds = line_kinds(rel, "\n".join(line for line, _ in doc))
    kinds += ["empty"] * (len(doc) - len(kinds))  # the join lost trailing empties
    lang = file_lang(rel)
    counts.update((lang, kind) for kind, (_, changed) in zip(kinds, doc) if changed)


def looks_like_diff(text):
    """Whether piped input is a unified diff:
    a git per-file header, or the ---/+++ pair
    a headerless `diff -u` opens with."""
    lines = text.splitlines()[:400]
    return any(
        line.startswith("diff ")
        or (line.startswith("--- ") and later.startswith("+++ "))
        for line, later in zip(lines, lines[1:] + [""])
    )
