"""The languages: which files are which, and what their lines can be."""

# Line categories, from least to most important.
CATEGORIES = ("empty", "doc", "comment", "config", "testdata", "test", "code")

PROSE = ("markdown", "rst", "txt", "html", "man")

# Inert fixture formats: every line is test data.
DATA = ("eml", "pgp")

# Languages the C-style scanner reads, next to Rust.
CSTYLE = (
    "javascript",
    "typescript",
    "c",
    "cpp",
    "java",
    "kotlin",
    "swift",
    "go",
    "qml",
    "gradle",
)

CODE = ("python", "rust", *CSTYLE)

# Comment prefixes of the line-comment formats, which know no tests.
CONFIG = {
    "shell": ("#",),
    "sql": ("--",),
    "lua": ("--",),
    "sieve": ("#",),
    "make": ("#",),
    "docker": ("#",),
    "systemd": ("#", ";"),
    "conf": ("#",),
    "ini": ("#", ";"),
    "toml": ("#",),
    "yaml": ("#",),
    "json": (),
    "nix": ("#",),
    "m4": ("#", "dnl"),
    "zone": (";",),
    "po": ("#",),
    "strings": ("//",),
    "cmake": ("#",),
}

# The line-comment formats that execute: plain lines count as code.
SCRIPTS = ("shell", "sql", "lua", "sieve", "make", "docker")

# Markup formats with block comments; plain lines count as config.
BLOCK = {"css": ("/*", "*/"), "xml": ("<!--", "-->"), "svg": ("<!--", "-->")}

# Media formats: counted as files, never read.
MEDIA = ("png", "jpg", "gif", "webp", "ico", "font", "pdf", "xdc")

LANGS = (*CODE, *CONFIG, *BLOCK, *PROSE, *DATA, *MEDIA)

TESTDATA_DIRS = frozenset(("test-data", "test_data", "testdata", "fixtures"))

# Versioned but machine-written: counted as files, never read.
GENERATED = frozenset(
    "Cargo.lock flake.lock uv.lock package-lock.json yarn.lock"
    " pnpm-lock.yaml poetry.lock composer.lock Gemfile.lock go.sum".split()
)

NAME_LANG = {
    "Makefile": "make",
    "makefile": "make",
    "GNUmakefile": "make",
    "Dockerfile": "docker",
    "Containerfile": "docker",
    "CMakeLists.txt": "cmake",
}

SUFFIX_LANG = {
    ".py": "python",
    ".rs": "rust",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".hh": "cpp",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".swift": "swift",
    ".go": "go",
    ".qml": "qml",
    ".gradle": "gradle",
    ".lua": "lua",
    ".sieve": "sieve",
    ".svtest": "sieve",
    ".mk": "make",
    ".am": "make",
    ".nix": "nix",
    ".m4": "m4",
    ".ac": "m4",
    ".zone": "zone",
    ".po": "po",
    ".pot": "po",
    ".strings": "strings",
    ".cmake": "cmake",
    ".md": "markdown",
    ".rst": "rst",
    ".txt": "txt",
    ".html": "html",
    ".htm": "html",
    ".sh": "shell",
    ".conf": "conf",
    ".cf": "conf",
    ".ini": "ini",
    ".cfg": "ini",
    ".toml": "toml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".sql": "sql",
    ".css": "css",
    ".scss": "css",
    ".sass": "css",
    ".xml": "xml",
    ".svg": "svg",
    ".plist": "xml",
    ".storyboard": "xml",
    ".xib": "xml",
    ".stringsdict": "xml",
    ".entitlements": "xml",
    ".xcscheme": "xml",
    ".xcworkspacedata": "xml",
    ".xcprivacy": "xml",
    ".eml": "eml",
    ".asc": "pgp",
    ".pem": "pgp",
    ".png": "png",
    ".jpg": "jpg",
    ".jpeg": "jpg",
    ".gif": "gif",
    ".webp": "webp",
    ".ico": "ico",
    ".woff": "font",
    ".woff2": "font",
    ".ttf": "font",
    ".otf": "font",
    ".pdf": "pdf",
    ".xdc": "xdc",
}

SUFFIX_LANG.update((f".{n}", "man") for n in range(1, 10))

SUFFIX_LANG.update(
    (suffix, "systemd")
    for suffix in (
        ".service .socket .timer .target .path .mount .automount"
        " .swap .slice .scope .network .netdev .link"
    ).split()
)

# doveauth.service.f is a systemd unit, Makefile.in a makefile;
# a marker over no known name or suffix stays unknown,
# so Fortran .f is not misread as a template.
TEMPLATE_SUFFIXES = (".f", ".j2", ".in")


def file_lang(path):
    if path.suffix in TEMPLATE_SUFFIXES:
        path = path.with_suffix("")
    if path.name in GENERATED:
        return None
    return NAME_LANG.get(path.name) or SUFFIX_LANG.get(path.suffix)


def is_test_path(path):
    """Whether every line of the file counts as test code."""
    if any(part in ("test", "tests", "__tests__") for part in path.parts[:-1]):
        return True
    stem = path.stem
    if path.suffix == ".py":
        return stem == "conftest" or stem.startswith("test_") or stem.endswith("_test")
    if path.suffix == ".rs":
        return (
            stem in ("test", "tests")
            or stem.startswith("test_")
            or stem.endswith(("_test", "_tests"))
        )
    if path.suffix in (".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx"):
        return stem.endswith((".test", ".spec"))
    return path.suffix == ".svtest"


def in_testdata(path):
    """Whether the file is fixture content under a test-data directory."""
    return any(part in TESTDATA_DIRS for part in path.parts[:-1])
