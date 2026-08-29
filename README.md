# srcloc: line counting for source trees

srcloc counts how a tree splits into doc,
comment, config, testdata, test and code lines.

## Install

    uv tool install srcloc

## Examples

### Comparing a git diff

    chatmail/core$ git diff main.. | srcloc
    category          added   removed   net
    ---------------   -----   -------   ----
    comment  rust      +100        -7    +93
    testdata eml        +15        -0    +15
    test     python     +37        -0    +37
    test     rust      +432       -16   +416
    code     rust      +379      -133   +246
    ---------------   -----   -------   ----
    total              +963      -156   +807

### One category across the files

    chatmail/srcloc$ srcloc --test -v
       test      file
    ----------   ---------------------
    339 [ 35%]   tests/test_cli.py
    337 [ 35%]   tests/test_kinds.py
    132 [ 14%]   tests/test_collect.py
    109 [ 11%]   tests/test_tables.py
     57 [  6%]   tests/conftest.py
    ----------   ---------------------
    974 [100%]   total

    language      test
    --------   ----------
    python     974 [100%]
    --------   ----------
    total      974 [100%]

### Counting a source tree

    chatmail/filtermail$ srcloc
    language   NUMFILES   doc   comment   config   testdata   test   code   SUM
    --------   --------   ---   -------   ------   --------   ----   ----   ----
    rust             21     .       464        .          .    670   2746   3880
    eml              14     .         .        .        513      .      .    513
    markdown          2   331         .        .          .      .      .    331
    yaml              3     .         4      176          .      .      .    180
    toml              2     .        41      108          .      .      .    149
    unknown          13     .         .        .          .      .      .      .
    --------   --------   ---   -------   ------   --------   ----   ----   ----
    total            55   331       509      284        513    670   2746   5053


### Per-file counts, columns as percentages

    chatmail/srcloc$ srcloc -v -c
       doc        comment       config        test         code       SUM    file
    ----------   ----------   ----------   ----------   -----------   ----   -----------------------------
             .            .            .   339 [ 35%]             .    339   tests/test_cli.py
             .            .            .   337 [ 35%]             .    337   tests/test_kinds.py
             .    23 [ 15%]            .            .    231 [ 23%]    254   srcloc/kinds.py
             .     9 [  6%]            .            .    233 [ 23%]    242   srcloc/cli.py
             .    20 [ 13%]            .            .    195 [ 19%]    215   srcloc/views.py
    191 [ 99%]            .            .            .             .    191   README.md
             .    14 [  9%]            .            .    165 [ 16%]    179   srcloc/langs.py
             .    21 [ 14%]            .            .    134 [ 13%]    155   srcloc/collect.py
             .            .            .   132 [ 14%]             .    132   tests/test_collect.py
             .            .            .   109 [ 11%]             .    109   tests/test_tables.py
             .    24 [ 16%]    60 [ 44%]            .             .     84   cliff.toml
             .    16 [ 11%]            .            .     64 [  6%]     80   srcloc/tables.py
             .            .            .    57 [  6%]             .     57   tests/conftest.py
             .    22 [ 15%]    24 [ 18%]            .             .     46   .github/workflows/release.yml
             .            .    37 [ 27%]            .             .     37   pyproject.toml
             .     1 [  1%]    15 [ 11%]            .             .     16   .github/workflows/ci.yml
      2 [  1%]            .            .            .             .      2   CHANGELOG.md
             .     1 [  1%]            .            .             .      1   srcloc/__init__.py
             .            .            .            .             .      .   tests/__init__.py
    ----------   ----------   ----------   ----------   -----------   ----   -----------------------------
    193 [100%]   151 [100%]   136 [100%]   974 [100%]   1022 [100%]   2476   total

    language   NUMFILES      doc        comment       config        test         code       SUM
    --------   --------   ----------   ----------   ----------   ----------   -----------   ----
    python           13            .   104 [ 69%]            .   974 [100%]   1022 [100%]   2100
    markdown          2   193 [100%]            .            .            .             .    193
    toml              2            .    24 [ 16%]    97 [ 71%]            .             .    121
    yaml              2            .    23 [ 15%]    39 [ 29%]            .             .     62
    unknown           2            .            .            .            .             .      .
    --------   --------   ----------   ----------   ----------   ----------   -----------   ----
    total            21   193 [100%]   151 [100%]   136 [100%]   974 [100%]   1022 [100%]   2476

## JSON

`--json` prints one JSON object instead of the tables, for jq
and other postprocessing. Zero counts are left out everywhere,
like the tables' dot cells; the category, language
and `--with-empty` flags filter as usual.

Counting:

    {
      "languages": {"python": {"files": 2, "comment": 69, "code": 681},
                    "markdown": {"files": 2, "doc": 126}},
      "total": {"files": 4, "doc": 126, "comment": 69, "code": 681},
      "unknown_files": 1
    }

- `languages`:
  per language the file count and its counted lines per category.

- `total`:
  the same summed over the languages;
  the unknown files are not part of it.

- `unknown_files`: how many files stayed uncounted, when any.

- `-v` adds `files`:
  per path the language and the counted lines per category.

- `-vv` adds `unknown`: the uncounted paths.

A diff carries `added` and `removed` instead,
each language to counted lines per category,
and `total` sums both sides over the shown categories:

    {
      "added": {"rust": {"comment": 100, "test": 432, "code": 379}},
      "removed": {"rust": {"comment": 7, "test": 16, "code": 133}},
      "total": {"added": 963, "removed": 156}
    }

`-v` adds `files`: per path its added and removed line counts.

## Counting rules

Every line lands in one category, the tables
running from the least to the most important:

- **test**:
  whole test files (`conftest.py`, `test_*.py`,
  `*.test.ts`, `*.spec.js`, `tests/` directories,
  Rust `tests.rs`, `*_tests.rs`, `test_*.rs`, `tests/` crates)
  and `#[cfg(test)]` regions inside regular Rust modules.

- **testdata**:
  every line of a file under a `test-data`,
  `test_data`, `testdata` or `fixtures` directory,
  and of the data formats eml and pgp wherever they live.

- **code**:
  every other non-empty line.
  A line holding code and a trailing comment counts as code.

- **config**:
  every non-comment line of a config format.
  Shell scripts execute, so their lines count as code.

- **doc**:
  every non-empty line of a prose file, the only category prose knows.

- **comment**:
  comment-only lines outside test code. Python docstrings count here;
  Rust `//`, `///` and nested `/* */` are recognized,
  comment markers inside literals are not.

Empty lines count only with `--with-empty`;
a zero count shows as a dim dot, and a category
without any lines drops out of the table.

The languages:

- C-style code -- **javascript** (also `.jsx`), **typescript**,
  **c** (`.c`/`.h`), **cpp**, **java**, **kotlin**, **swift**,
  **go**, **qml**, **gradle** -- read like Rust:
  `//` and `/* */` comments and string literals
  are recognized, backtick strings included.

- Script formats -- **shell**, **sql**, **lua**, **sieve**,
  **make** (`.mk`/`.am`, `Makefile`), **docker** (`Dockerfile`):
  line comments (`#`, in sql and lua `--`), plain lines count as code,
  they execute; `.svtest` files are sieve tests.

- Config formats -- **systemd** (the unit suffixes),
  **conf** (`.conf`/`.cf`), **ini** (`.ini`/`.cfg`),
  **toml**, **yaml**, **json**, **nix**, **m4** (`.m4`/`.ac`),
  **zone**, **po**, **strings**, **cmake** (`CMakeLists.txt`):
  line comments (json knows none), plain lines count as config.

- Markup -- **css** (also `.scss`/`.sass`),
  **xml** (also `.plist` and friends) and **svg**:
  `/* */` and `<!-- -->` block comments, plain lines count as config.

- Prose -- **markdown**, **rst**, **txt**, **html**,
  **man** (`.1` through `.9`): doc lines only.

- Data -- **eml**, **pgp** (`.asc`/`.pem`): pure testdata lines.

- Media -- **png**, **jpg**, **gif**, **webp**, **ico**,
  **font** (`.woff`/`.ttf` and kin), **pdf**, **xdc**:
  one row per type, counted as files, never read.

- **unknown**:
  everything else -- binaries and generated lock
  files (`Cargo.lock`, `package-lock.json`, ...)
  among them -- is counted, never read; `-vv` lists the paths.

A `.f` (str.format), `.j2` (jinja2) or `.in`
(autoconf) template suffix is stripped first,
so `doveauth.service.f` is a systemd unit and `Makefile.in` a makefile.

Fine print:

- Outside git, ephemeral directories (`venv`, `target`,
  `node_modules`, `build`, `dist`, `__pycache__`, dot-directories,
  `*.egg-info`) are skipped, also where a repository tracks them.

- Changed lines are classified with the context the diff carries;
  pipe `git diff -U999999` when Rust test regions far
  from a change must be attributed exactly.

## Development

    uv venv venv
    uv pip install -e . --python venv/bin/python
    venv/bin/python -m pytest

Code must pass `ruff check .` and `ruff format --check .`.

## CI and releasing

CI and releases follow the shared
[chatmail/workflows](https://github.com/chatmail/workflows) standards:
every push runs the reusable py-checks flow (ruff lint and format
at a centrally pinned version, `uv build`, a twine metadata check
and pytest), and pushing a `vX.Y.Z` tag runs the same checks
and then publishes the built distributions to PyPI.

Publishing uses PyPI trusted publishing (OIDC):
the release workflow authenticates as this repository against
the `pypi` environment, so no long-lived token exists anywhere.
The version derives from the git tag (setuptools-git-versioning)
and the changelog from the commit messages (git-cliff, `cliff.toml`).
