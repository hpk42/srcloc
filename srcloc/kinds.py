"""Per-line classification: one category for every line of a file."""

import io
import re
import tokenize

from .langs import (
    BLOCK,
    CODE,
    CONFIG,
    DATA,
    PROSE,
    SCRIPTS,
    file_lang,
    in_testdata,
    is_test_path,
)

# cfg(any(test, ...)) stays unmatched: such items are not test-only.
RUST_TEST_ATTR = re.compile(
    r"^\s*#\s*\[\s*(?:cfg\s*\(\s*test\s*\)|(?:\w+\s*::\s*)*test\b)"
)

RUST_ATTR_START = re.compile(r"\s*#\s*\[")

RUST_RAW_STRING = re.compile(r'(?:b|c)?r(#*)"')

# A char literal holds one (escaped) char;
# a quote without one is a lifetime and never closes.
RUST_CHAR_LITERAL = re.compile(r"'(?:\\[^']*|[^'\\])'")

PLAIN_LINE = re.compile(r"[\"'`/]")


def python_line_kinds(text):
    """Per-line "code", "comment" or "empty" for Python source.

    Tokenizing keeps comment markers inside literals code
    and lets docstrings count as comments.
    """
    lines = text.splitlines()
    kinds = ["empty" if not line.strip() else None for line in lines]
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, SyntaxError, ValueError):
        return [
            kind or ("comment" if line.lstrip().startswith("#") else "code")
            for kind, line in zip(kinds, lines)
        ]
    code_rows = set()
    comment_rows = set()
    stmt_start = True
    pending_string = None
    for tok in tokens:
        rows = range(tok.start[0], tok.end[0] + 1)
        if tok.type == tokenize.COMMENT:
            comment_rows.update(rows)
        elif tok.type in (tokenize.NL, tokenize.ENDMARKER):
            pass
        elif tok.type in (tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT):
            if pending_string is not None:
                comment_rows.update(pending_string)  # a string statement: docstring
                pending_string = None
            stmt_start = True
        elif tok.type == tokenize.STRING and stmt_start:
            pending_string = rows
            stmt_start = False
        else:
            if pending_string is not None:
                code_rows.update(pending_string)  # the string was an expression
                pending_string = None
            code_rows.update(rows)
            stmt_start = False
    if pending_string is not None:
        comment_rows.update(pending_string)
    for row in comment_rows - code_rows:
        if kinds[row - 1] is None:
            kinds[row - 1] = "comment"
    return [kind or "code" for kind in kinds]


def cstyle_line_kinds(text, quotes='"', rust=True):
    """Per-line (kind, code) for Rust and JavaScript-family source.

    code is the line with comments and literal bodies blanked out,
    so braces and attributes in them cannot fool the test tracking.
    rust adds char literals, raw strings and nested block comments;
    quotes lists the string delimiters.
    """
    result = []
    block_depth = 0
    string_end = None
    for line in text.splitlines():
        if not line.strip():
            result.append(("empty", ""))
            continue
        if block_depth == 0 and string_end is None and not PLAIN_LINE.search(line):
            result.append(("code", line))
            continue
        code = []
        has_comment = block_depth > 0
        has_string = string_end is not None
        i = 0
        while i < len(line):
            if block_depth:
                if line.startswith("*/", i):
                    block_depth -= 1
                    i += 2
                elif rust and line.startswith("/*", i):
                    block_depth += 1  # Rust block comments nest
                    i += 2
                else:
                    i += 1
                continue
            if string_end is not None:
                if line.startswith(string_end, i):
                    i += len(string_end)
                    string_end = None
                    code.append('"')
                elif len(string_end) == 1 and line[i] == "\\":
                    i += 2
                else:
                    i += 1
                continue
            ch = line[i]
            if line.startswith("//", i):
                has_comment = True
                break
            if line.startswith("/*", i):
                block_depth = 1
                has_comment = True
                i += 2
                continue
            if ch in quotes:
                string_end = ch
                has_string = True
                code.append('"')
                i += 1
                continue
            if rust and ch in "brc":
                previous = line[i - 1 : i]
                match = RUST_RAW_STRING.match(line, i)
                if match and not (previous.isalnum() or previous == "_"):
                    string_end = '"' + "#" * len(match.group(1))
                    has_string = True
                    code.append('"')
                    i = match.end()
                    continue
            if rust and ch == "'":
                match = RUST_CHAR_LITERAL.match(line, i)
                if match:
                    has_string = True
                    i = match.end()
                else:
                    i += 1  # a lifetime, not a literal
                continue
            code.append(ch)
            i += 1
        code = "".join(code)
        kind = "comment" if has_comment and not (code.strip() or has_string) else "code"
        result.append((kind, code))
    return result


def strip_rust_attrs(code):
    """Drop leading #[...] attributes to expose the item behind them."""
    i = 0
    while True:
        match = RUST_ATTR_START.match(code, i)
        if not match:
            return code[i:]
        i = match.end()
        depth = 1
        while i < len(code) and depth:
            if code[i] == "[":
                depth += 1
            elif code[i] == "]":
                depth -= 1
            i += 1


def rust_test_rows(kind_codes):
    """Indexes of the lines belonging to #[cfg(test)] / #[test] items.

    A region spans the attributes and the item behind them:
    a declaration up to its semicolon, a body up to its closing brace.
    """
    rows = set()
    state = None
    depth = 0
    for i, (kind, code) in enumerate(kind_codes):
        if state is None:
            if kind == "empty" or not RUST_TEST_ATTR.match(code):
                continue
            state = "attrs"
            depth = 0
        rows.add(i)
        if kind == "empty":
            continue
        if state == "attrs":
            rest = strip_rust_attrs(code)
            depth += rest.count("{") - rest.count("}")
            if "{" in rest:
                state = "body"
            elif rest.strip().endswith(";"):
                state = None
        else:
            depth += code.count("{") - code.count("}")
        if state == "body" and depth <= 0:
            state = None
    return rows


def block_comment_kinds(text, opener, closer):
    """Per-line kind for markup with block comments;
    a line is a comment when nothing outside comments remains on it."""
    kinds = []
    in_comment = False
    for line in text.splitlines():
        if not line.strip():
            kinds.append("empty")
            continue
        content = []
        i = 0
        while i < len(line):
            if in_comment:
                end = line.find(closer, i)
                if end < 0:
                    break
                in_comment = False
                i = end + len(closer)
            else:
                start = line.find(opener, i)
                if start < 0:
                    content.append(line[i:])
                    break
                content.append(line[i:start])
                in_comment = True
                i = start + len(opener)
        kinds.append("config" if "".join(content).strip() else "comment")
    return kinds


def line_kinds(rel, text):
    """Per-line categories for one file version,
    test and testdata buckets applied."""
    lang = file_lang(rel)
    lines = text.splitlines()
    if lang in PROSE:
        kinds = ["doc" if line.strip() else "empty" for line in lines]
    elif lang in DATA:
        kinds = ["testdata" if line.strip() else "empty" for line in lines]
    elif lang in CONFIG:
        prefixes = CONFIG[lang]
        kind = "code" if lang in SCRIPTS else "config"
        kinds = [
            "empty" if not bare else "comment" if bare.startswith(prefixes) else kind
            for bare in (line.strip() for line in lines)
        ]
    elif lang in BLOCK:
        kinds = block_comment_kinds(text, *BLOCK[lang])
    elif lang == "python":
        kinds = python_line_kinds(text)
    elif lang == "rust":
        kind_codes = cstyle_line_kinds(text)
        kinds = [kind for kind, _ in kind_codes]
        for row in rust_test_rows(kind_codes):
            if kinds[row] != "empty":
                kinds[row] = "test"
    else:  # the C-style family
        kinds = [kind for kind, _ in cstyle_line_kinds(text, "\"'`", rust=False)]
    if in_testdata(rel):
        return ["testdata" if kind != "empty" else kind for kind in kinds]
    if lang in (*CODE, *SCRIPTS) and is_test_path(rel):
        return ["test" if kind != "empty" else kind for kind in kinds]
    return kinds
