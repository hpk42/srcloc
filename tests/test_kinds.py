import textwrap
from pathlib import Path

import pytest

from srcloc.kinds import (
    cstyle_line_kinds,
    line_kinds,
    python_line_kinds,
    rust_test_rows,
)
from srcloc.langs import file_lang, in_testdata, is_test_path


def python_kinds(source):
    return python_line_kinds(textwrap.dedent(source))


def rust_kinds(source):
    kind_codes = cstyle_line_kinds(textwrap.dedent(source))
    kinds = [kind for kind, _ in kind_codes]
    for row in rust_test_rows(kind_codes):
        if kinds[row] != "empty":
            kinds[row] = "test"
    return kinds


def config_kinds(name, source):
    return line_kinds(Path(name), textwrap.dedent(source))


class TestPythonKinds:
    def test_code_comment_empty(self):
        kinds = python_kinds("""\
            # a comment
            x = 1

            y = 2  # trailing comment counts as code
        """)
        assert kinds == ["comment", "code", "empty", "code"]

    def test_docstrings_are_comments(self):
        kinds = python_kinds('''\
            """module

            docstring"""
            title = "a string statement is not a docstring"

            def f():
                "function docstring"
                return 1
        ''')
        assert kinds == [
            "comment",
            "empty",
            "comment",
            "code",
            "empty",
            "code",
            "comment",
            "code",
        ]

    def test_hash_inside_string_is_code(self):
        kinds = python_kinds("""\
            x = '''
            # not a comment
            '''
        """)
        assert kinds == ["code", "code", "code"]

    def test_syntax_error_falls_back_to_hash_comments(self):
        kinds = python_kinds("""\
            # a comment
            def broken(:
        """)
        assert kinds == ["comment", "code"]


class TestRustKinds:
    def test_code_comment_empty(self):
        kinds = rust_kinds("""\
            // a comment
            /// a doc comment
            fn main() {

                println!("hi"); // trailing comment counts as code
            }
        """)
        assert kinds == ["comment", "comment", "code", "empty", "code", "code"]

    def test_block_comments_nest(self):
        kinds = rust_kinds("""\
            /* one
            /* nested */
            still a comment */
            fn f() {}
        """)
        assert kinds == ["comment", "comment", "comment", "code"]

    def test_comment_markers_in_strings_are_code(self):
        kinds = rust_kinds("""\
            let url = "https://example.org";
            let raw = r#"multi {
            // not a comment
            }"#;
        """)
        assert kinds == ["code"] * 4

    def test_inline_test_mod(self):
        kinds = rust_kinds("""\
            fn shipped() {}

            #[cfg(test)]
            mod tests {
                use super::*;

                #[test]
                fn t() {
                    let brace = '{';
                    assert!(true, "{}", "}");
                }
            }

            fn also_shipped() {}
        """)
        assert kinds == ["code", "empty"] + ["test"] * 3 + ["empty"] + ["test"] * 6 + [
            "empty",
            "code",
        ]

    def test_test_items_end_at_semicolon_or_brace(self):
        kinds = rust_kinds("""\
            #[cfg(test)]
            mod chat_tests;
            fn shipped() {}
            #[cfg(test)]
            pub(crate) fn helper(x: u32) -> u32 {
                x + 1
            }
            fn also_shipped() {}
        """)
        assert kinds == ["test", "test", "code", "test", "test", "test", "test", "code"]

    def test_cfg_not_test_is_code(self):
        kinds = rust_kinds("""\
            #[cfg(not(test))]
            fn shipped() {}
        """)
        assert kinds == ["code", "code"]


class TestJsKinds:
    def js_kinds(self, name, source):
        return line_kinds(Path(name), textwrap.dedent(source))

    def test_code_comment_strings(self):
        kinds = self.js_kinds(
            "app.ts",
            """\
            // a comment
            const url = 'https://example.org';
            /* block
            comment */
            const raw = `template {
            // not a comment
            }`;
            """,
        )
        assert kinds == ["comment", "code", "comment", "comment"] + ["code"] * 3

    def test_test_file_conventions(self):
        assert self.js_kinds("src/app.test.ts", "it('works');\n") == ["test"]
        assert self.js_kinds("__tests__/app.jsx.js", "x\n") == ["test"]


class TestMarkupAndDataKinds:
    def test_json_is_config_without_comments(self):
        kinds = line_kinds(Path("package.json"), '{\n  "a": 1\n}\n')
        assert kinds == ["config", "config", "config"]

    def test_sql_dashes_comment_code(self):
        kinds = line_kinds(Path("schema.sql"), "-- users\nSELECT 1;\n")
        assert kinds == ["comment", "code"]

    def test_css_block_comments(self):
        kinds = line_kinds(
            Path("custom.css"),
            "/* head\n   still */\nbody { color: red; }  /* trailing */\n",
        )
        assert kinds == ["comment", "comment", "config"]

    def test_xml_and_svg_markup(self):
        kinds = line_kinds(
            Path("logo.svg"),
            "<!-- generated\n  by hand -->\n<svg>\n</svg>\n",
        )
        assert kinds == ["comment", "comment", "config", "config"]

    def test_scripts_comment_and_code(self):
        assert line_kinds(Path("auth.lua"), "-- luadoc\nlocal x = 1\n") == [
            "comment",
            "code",
        ]
        assert line_kinds(Path("Makefile"), "# build\nall: test\n") == [
            "comment",
            "code",
        ]

    def test_c_string_and_char_literals(self):
        kinds = line_kinds(Path("main.c"), "char c = 'x';  /* trailing */\n// only\n")
        assert kinds == ["code", "comment"]

    def test_go_raw_string_is_code(self):
        kinds = line_kinds(Path("x.go"), "q := `\n// not a comment\n`\n")
        assert kinds == ["code", "code", "code"]

    def test_man_page_is_doc(self):
        assert line_kinds(Path("dovecot.conf.5"), ".TH X\n") == ["doc"]

    def test_svtest_is_a_test_file(self):
        assert line_kinds(Path("x.svtest"), 'test "t" {\n}\n') == [
            "test",
            "test",
        ]

    def test_eml_and_asc_are_testdata(self):
        kinds = line_kinds(Path("msg.eml"), "From: a@b\n\nhi\n")
        assert kinds == ["testdata", "empty", "testdata"]
        assert line_kinds(Path("key.asc"), "xsBNBF\n") == ["testdata"]


class TestConfigKinds:
    def test_systemd_unit(self):
        kinds = config_kinds(
            "chatmail-expire.service",
            """\
            # started by chatmail-expire.timer
            ; semicolons comment too
            [Unit]

            ExecStart=/usr/bin/chatmail-expire
            """,
        )
        assert kinds == ["comment", "comment", "config", "empty", "config"]

    def test_conf_semicolon_is_not_a_comment(self):
        kinds = config_kinds(
            "main.cf",
            """\
            # postfix comment
            smtpd_banner = $myhostname ESMTP
            ; not a comment in postfix
            """,
        )
        assert kinds == ["comment", "config", "config"]

    @pytest.mark.parametrize(
        "name,source,kind",
        [
            ("run.sh", "#!/bin/sh\nset -e\n", "code"),
            ("Cargo.toml", "# c\n[package]\n", "config"),
            ("ci.yml", "# c\njobs:\n", "config"),
            ("chatmail.ini", "; c\n[params]\n", "config"),
        ],
    )
    def test_comment_prefixes(self, name, source, kind):
        assert config_kinds(name, source) == ["comment", kind]


class TestPathClassification:
    @pytest.mark.parametrize(
        "path",
        [
            "conftest.py",
            "test_srcloc.py",
            "pkg/tests/anything.py",
            "sub/test/helper.py",
            "src/tests.rs",
            "src/chat/chat_tests.rs",
            "src/test_utils.rs",
            "tests/integration.rs",
        ],
    )
    def test_test_paths(self, path):
        assert is_test_path(Path(path))

    @pytest.mark.parametrize(
        "path", ["srcloc.py", "src/chat.rs", "src/attestation.py", "protest.rs"]
    )
    def test_non_test_paths(self, path):
        assert not is_test_path(Path(path))

    @pytest.mark.parametrize(
        "path", ["src/app.test.ts", "util.spec.js", "__tests__/render.tsx"]
    )
    def test_js_test_paths(self, path):
        assert is_test_path(Path(path))

    @pytest.mark.parametrize(
        "path",
        [
            "test-data/message.py",
            "python/tests/fixtures/config.ini",
            "testdata/page.html",
        ],
    )
    def test_testdata_paths(self, path):
        assert in_testdata(Path(path))
        kinds = line_kinds(Path(path), "x\n\ny\n")
        assert kinds == ["testdata", "empty", "testdata"]

    @pytest.mark.parametrize(
        "name,lang",
        [
            ("x.py", "python"),
            ("x.rs", "rust"),
            ("x.md", "markdown"),
            ("x.rst", "rst"),
            ("x.txt", "txt"),
            ("run.sh", "shell"),
            ("main.cf", "conf"),
            ("dovecot.conf", "conf"),
            ("chatmail.ini", "ini"),
            ("setup.cfg", "ini"),
            ("Cargo.toml", "toml"),
            ("ci.yml", "yaml"),
            ("desired.yaml", "yaml"),
            ("doveauth.service", "systemd"),
            ("fcgiwrap.socket", "systemd"),
            ("tls-cert-reload.path", "systemd"),
            ("chatmail-expire.service.f", "systemd"),
            ("filtermail.service.j2", "systemd"),
            ("dovecot.conf.j2", "conf"),
            ("mta-sts.txt.j2", "txt"),
            ("auth.lua.j2", "lua"),
            ("Makefile.in", "make"),
            ("config.h.in", "c"),
            ("plain.f", None),
            ("release-date.in", None),
            ("app.js", "javascript"),
            ("mod.mjs", "javascript"),
            ("client.ts", "typescript"),
            ("View.tsx", "typescript"),
            ("package.json", "json"),
            ("schema.sql", "sql"),
            ("custom.css", "css"),
            ("DoxygenLayout.xml", "xml"),
            ("logo.svg", "svg"),
            ("spaces.html", "html"),
            ("issue.eml", "eml"),
            ("public.asc", "pgp"),
            ("main.c", "c"),
            ("chat.h", "c"),
            ("view.cpp", "cpp"),
            ("Api.kt", "kotlin"),
            ("App.java", "java"),
            ("Chat.swift", "swift"),
            ("relay.go", "go"),
            ("Page.qml", "qml"),
            ("build.gradle", "gradle"),
            ("auth.lua", "lua"),
            ("filter.sieve", "sieve"),
            ("extprograms.svtest", "sieve"),
            ("rules.mk", "make"),
            ("Makefile.am", "make"),
            ("Makefile", "make"),
            ("Dockerfile", "docker"),
            ("flake.nix", "nix"),
            ("configure.ac", "m4"),
            ("db.zone", "zone"),
            ("de.po", "po"),
            ("Localizable.strings", "strings"),
            ("CMakeLists.txt", "cmake"),
            ("main.scss", "css"),
            ("Info.plist", "xml"),
            ("App.entitlements", "xml"),
            ("dovecot.conf.5", "man"),
            ("chain.pem", "pgp"),
            ("Cargo.lock", None),
            ("package-lock.json", None),
            ("app.xdc", "xdc"),
            ("photo.png", "png"),
            ("shot.jpeg", "jpg"),
            ("inter.woff2", "font"),
            ("paper.pdf", "pdf"),
        ],
    )
    def test_file_lang(self, name, lang):
        assert file_lang(Path(name)) == lang
