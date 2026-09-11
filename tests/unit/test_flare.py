"""Unit tests for the MadCap Flare engine (planning.md Phase 5b).

Every fixture here is a miniature output root -- `Data/HelpSystem.xml`, a TOC in
JavaScript, and a handful of topics -- because that is the unit the engine works
in and because most of §5.1's rules are only visible at that scale: which file is
a topic depends on the TOC, which page is the landing page depends on the
manifest, and whether a cross-reference becomes a link depends on what the rest
of the root turned out to contain.

The assertions are on the *corpus's* rules, not on MadCap's markup in general.
Each one is a claim `architecture.md` §5.1 makes with a number attached, and the
tests that look oddly specific -- the `t[0]` label alignment, the two roots
sharing a path, the support page picked from the TOC rather than by name -- are
the ones where the tempting implementation is wrong on real input.
"""

import json
from collections.abc import Mapping
from pathlib import Path, PurePosixPath

import pytest

from docushift.engines.base import ConversionContext, Unit
from docushift.engines.flare import (
    CONTENT_SELECTOR,
    FlareEngine,
    autonum_label,
)
from docushift.engines.flare_toc import parse_define, read_manifest, read_toc, tree_files
from docushift.engines.roots import find_output_roots
from docushift.models import SourceEngine
from docushift.reporting.findings import FindingsRun
from docushift.transforms.assets import AssetCopier
from docushift.transforms.markdown import parse

# -- fixtures in the small ------------------------------------------------------


def build(directory: Path, files: Mapping[str, str]) -> Path:
    for name, text in files.items():
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return directory


def define(payload: object) -> str:
    """One AMD module. `json` emits a valid JavaScript object literal."""
    return f"define({json.dumps(payload)});\n"


def manifest(toc: str = "Data/Tocs/Default.js", default_url: str = "", alias: str = "") -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        f'<CatapultHelpSystem Toc="{toc}" DefaultUrl="{default_url}" Alias="{alias}" />\n'
    )


def toc_files(tree: list, entries: Mapping[str, dict], name: str = "Default") -> dict[str, str]:
    """A tree file and its single chunk payload, as every corpus root ships them."""
    return {
        f"Data/Tocs/{name}.js": define(
            {"tree": {"n": tree}, "numchunks": 1, "prefix": f"{name}_Chunk"}
        ),
        f"Data/Tocs/{name}_Chunk0.js": define(dict(entries)),
    }


def topic(title: str, body: str = "<p>Body.</p>") -> str:
    """One MadCap topic: the container, inside it the layout wrapper, then content."""
    return (
        f"<html><head><title>{title} - truncated by MadCap</title></head><body>"
        f"<div role='main' id='mc-main-content'>"
        f"<div class='topic-frame'><h1>{title}</h1>{body}</div>"
        f"<div id='feedback-survey'><a href='javascript:void(0);'>Was this helpful?</a></div>"
        "</div></body></html>"
    )


def page(body: str) -> str:
    """A page with the container and nothing else in it."""
    return f"<html><body><div role='main' id='mc-main-content'>{body}</div></body></html>"


# Past the hero furniture a landing page is *rich* in 351 of 676 roots and *light*
# in 270; only the 55 hero-only ones get a stub. So the fixture's prose has to be
# real prose -- a one-line placeholder would trip the hero-only branch and every
# landing test would be testing the stub instead.
LANDING_PROSE = (
    "<p>Everything you need to install, configure and operate the server is "
    "collected here, starting with the release notes and the installation guide.</p>"
)


# -- running one tree -----------------------------------------------------------


class Run:
    """One conversion of one extracted tree, with its units and its findings."""

    def __init__(self, units: list[Unit], findings: FindingsRun, tree: Path,
                 context: ConversionContext):
        self.units = units
        self.findings = findings
        self.tree = tree
        self.context = context

    @property
    def unit(self) -> Unit:
        return self.units[0]

    def document(self, relative: str, unit: Unit | None = None):
        target = unit or self.unit
        for document in target.documents:
            if str(document.relative) == relative:
                return document
        raise AssertionError(f"{relative} not among {[str(d.relative) for d in target.documents]}")

    def body(self, relative: str, unit: Unit | None = None) -> str:
        return self.document(relative, unit).body

    def codes(self) -> dict[str, int]:
        tally: dict[str, int] = {}
        for finding in self.findings.all:
            tally[finding.code] = tally.get(finding.code, 0) + finding.count
        return tally


def run(tmp_path: Path, files: Mapping[str, str], *, api_roots: tuple[str, ...] = (),
        product_name: str = "") -> Run:
    """Converts every output root in a tree, the way the driver does."""
    tree = build(tmp_path / "tree", files)
    output = tmp_path / "out"
    findings = FindingsRun("convert")
    context = ConversionContext(
        tree=tree,
        output=output,
        engine=SourceEngine.FLARE,
        slug="prod",
        version="1.0.0",
        product_name=product_name,
        api_roots=[tree / name for name in api_roots],
        output_roots=find_output_roots(tree, SourceEngine.FLARE),
        findings=findings,
    )
    engine = FlareEngine()
    units = []
    for root in engine.units(context):
        name = root.relative_to(tree).as_posix()
        context.assets = AssetCopier(root, SourceEngine.FLARE, output / name if name else output)
        units.append(engine.convert_unit(context, root))
    return Run(units, findings, tree, context)


# A root that most tests start from: three topics, a TOC that files two of them,
# and a landing page in `_templates/`.
def basic() -> dict[str, str]:
    files = {
        "html/Data/HelpSystem.xml": manifest(default_url="_templates/Home.htm"),
        "html/_templates/Home.htm": topic("Product", LANDING_PROSE),
        "html/Content/intro.htm": topic("Introduction"),
        "html/Content/guide/deep.htm": topic("Deep dive"),
    }
    declared = toc_files(
        [{"i": 1}, {"i": 2}],
        {
            "Content/intro.htm": {"i": [1], "t": ["Intro"], "b": [""]},
            "Content/guide/deep.htm": {"i": [2], "t": ["Deep"], "b": ["section"]},
        },
    )
    files.update({f"html/{name}": text for name, text in declared.items()})
    return files


# -- the TOC reader (§5.1.4) ----------------------------------------------------


def test_the_toc_is_parsed_as_a_literal_and_never_executed() -> None:
    """Single quotes, unquoted keys and `\\u0027` escapes -- and no JS engine."""
    text = (
        "require(['jquery']);\n"
        "define({tree:{n:[{i:1,n:[{i:2}]}]},'numchunks':1,name:'Author\\u0027s guide'});"
    )

    assert parse_define(text) == {
        "tree": {"n": [{"i": 1, "n": [{"i": 2}]}]},
        "numchunks": 1,
        "name": "Author's guide",
    }


def test_a_file_that_is_not_an_amd_module_reads_as_nothing() -> None:
    assert parse_define("window.toc = {a: 1};") is None
    assert parse_define("define(") is None


def test_the_kth_id_takes_the_kth_label(tmp_path: Path) -> None:
    """`i`/`t`/`b` are parallel arrays; `t[0]` for every id relabels 60 corpus nodes."""
    build(tmp_path, toc_files(
        [{"i": 1}, {"i": 2}, {"i": 3}],
        {"Content/shared.htm": {"i": [1, 2, 3],
                                "t": ["First position", "Second position", "Third"],
                                "b": ["", "later", ""]}},
    ))

    toc = read_toc(tmp_path / "Data/Tocs/Default.js")

    assert [node.entry.label for node in toc.nodes] == [
        "First position", "Second position", "Third",
    ]
    assert [node.entry.anchor for node in toc.nodes] == ["", "later", ""]
    assert {node.entry.path for node in toc.nodes} == {"Content/shared.htm"}


def test_a_ragged_array_and_an_unmatched_id_are_counted(tmp_path: Path) -> None:
    """0 of 37,598 sampled entries are ragged, so a ragged one is news."""
    build(tmp_path, toc_files(
        [{"i": 1}, {"i": 2}, {"i": 99}],
        {"Content/a.htm": {"i": [1, 2], "t": ["Only one"], "b": []}},
    ))

    toc = read_toc(tmp_path / "Data/Tocs/Default.js")

    assert toc.ragged == 1
    assert toc.unmatched == 1
    assert [node.entry.label for node in toc.nodes] == ["Only one", "", ""]


def test_a_headless_node_keeps_its_label_and_loses_its_path(tmp_path: Path) -> None:
    build(tmp_path, toc_files(
        [{"i": 1, "n": [{"i": 2}]}],
        {"___": {"i": [1], "t": ["Concepts"], "b": [""]},
         "Content/a.htm": {"i": [2], "t": ["A"], "b": [""]}},
    ))

    toc = read_toc(tmp_path / "Data/Tocs/Default.js")

    assert toc.nodes[0].entry.label == "Concepts"
    assert toc.nodes[0].entry.path == ""
    assert toc.nodes[0].children[0].entry.path == "Content/a.htm"


def test_a_bare_tree_array_reads_the_same_as_a_wrapped_one(tmp_path: Path) -> None:
    build(tmp_path, {
        "Data/Tocs/Default.js": define({"tree": [{"i": 1}], "numchunks": 1,
                                        "prefix": "Default_Chunk"}),
        "Data/Tocs/Default_Chunk0.js": define({"Content/a.htm": {"i": [1], "t": ["A"], "b": [""]}}),
    })

    toc = read_toc(tmp_path / "Data/Tocs/Default.js")

    assert [node.entry.label for node in toc.nodes] == ["A"]


def test_a_malformed_toc_reads_as_an_empty_one_rather_than_raising(tmp_path: Path) -> None:
    build(tmp_path, {"Data/Tocs/Default.js": "define({tree:{n:[{i:1},"})

    toc = read_toc(tmp_path / "Data/Tocs/Default.js")

    assert toc.nodes == []
    assert read_toc(tmp_path / "Data/Tocs/Absent.js").nodes == []


def test_chunk_payloads_are_not_tree_files(tmp_path: Path) -> None:
    build(tmp_path, {
        "Data/Tocs/Default.js": "", "Data/Tocs/Default_Chunk0.js": "",
        "Data/Tocs/_HTML_gateway.js": "", "Data/Tocs/notes.txt": "",
    })

    # A set, not a list: `Path` sorts case-insensitively on Windows and not on
    # Linux, and the ordering that matters -- declared tree first -- is the
    # engine's, applied to this list rather than expressed by it.
    assert {path.name for path in tree_files(tmp_path)} == {"Default.js", "_HTML_gateway.js"}


def test_the_manifest_is_read_by_attribute_and_forward_slashed(tmp_path: Path) -> None:
    build(tmp_path, {"Data/HelpSystem.xml": (
        '<?xml version="1.0"?><CatapultHelpSystem Toc="Data\\Tocs\\Default.js" '
        'DefaultUrl="/_templates/Home.htm" Alias="Data\\Alias.xml" />'
    )})

    found = read_manifest(tmp_path)

    assert found is not None
    assert (found.toc, found.default_url, found.alias) == (
        "Data/Tocs/Default.js", "_templates/Home.htm", "Data/Alias.xml",
    )
    assert found.complete


def test_an_absent_or_unparseable_manifest_is_none(tmp_path: Path) -> None:
    assert read_manifest(tmp_path) is None
    build(tmp_path, {"Data/HelpSystem.xml": "<CatapultHelpSystem"})
    assert read_manifest(tmp_path) is None


# -- the unit of work (§5.1.1) --------------------------------------------------


def test_a_flare_tree_with_no_manifest_is_reported_and_not_converted(tmp_path: Path) -> None:
    """The 5 partial outputs: MadCap topics, no runtime, so no root boundary."""
    result = run(tmp_path, {"html/Content/intro.htm": topic("Introduction")})

    assert result.units == []
    assert "OUTPUT_ROOT_MISSING" in result.codes()


def test_the_innermost_output_root_owns_its_files(tmp_path: Path) -> None:
    """153 corpus roots nest; stopping at the first drops 22,456 topics."""
    files = {
        "html/Data/HelpSystem.xml": manifest(),
        "html/Content/outer.htm": topic("Outer"),
        "html/Subsystems/admin/Data/HelpSystem.xml": manifest(),
        "html/Subsystems/admin/Content/inner.htm": topic("Inner"),
    }
    files.update({f"html/{k}": v for k, v in toc_files([], {}).items()})

    result = run(tmp_path, files)
    outer, inner = result.units

    assert [str(d.relative) for d in outer.documents] == ["Content/outer.md"]
    assert [str(d.relative) for d in inner.documents] == ["Content/inner.md"]
    assert outer.skipped["nested-output-root"] == 1


def test_two_roots_sharing_a_relative_path_both_convert_it(tmp_path: Path) -> None:
    """30,736 paths are shared between two roots of one version; ~15% differ."""
    files = {}
    for name, release in (("html", "9.3.1"), ("html2", "9.3.2")):
        files[f"{name}/Data/HelpSystem.xml"] = manifest()
        files[f"{name}/release-notes/new-features.htm"] = topic(f"New in {release}")
        files.update({f"{name}/{k}": v for k, v in toc_files([], {}).items()})

    result = run(tmp_path, files)
    first, second = result.units

    assert (first.name, second.name) == ("html", "html2")
    assert result.document("release-notes/new-features.md", first).title == "New in 9.3.1"
    assert result.document("release-notes/new-features.md", second).title == "New in 9.3.2"


def test_output_mirrors_the_source_tree_so_colliding_stems_survive(tmp_path: Path) -> None:
    """Stems collide 6.0% inside one root, so flat output loses topics."""
    files = {
        "html/Data/HelpSystem.xml": manifest(),
        "html/Content/install/setup.htm": topic("Install setup"),
        "html/Content/config/setup.htm": topic("Config setup"),
    }
    files.update({f"html/{k}": v for k, v in toc_files([], {}).items()})

    result = run(tmp_path, files)

    assert sorted(str(d.relative) for d in result.unit.documents) == [
        "Content/config/setup.md", "Content/install/setup.md",
    ]


# -- what is a topic (§5.1.9) ---------------------------------------------------


def test_generated_directories_and_runtime_stubs_are_skipped_but_home_is_not(
    tmp_path: Path,
) -> None:
    """The predecessor's `skip_filenames`, minus its `Home.htm` entry."""
    files = basic()
    files["html/Resources/frame.htm"] = topic("Frame")
    files["html/_globalpages/global.htm"] = topic("Global")
    files["html/Content/Default.htm"] = topic("Stub")
    files["html/Content/Default_CSH.htm"] = topic("Stub")

    result = run(tmp_path, files)

    assert result.unit.skipped["generated-directory"] == 2
    assert result.unit.skipped["runtime-stub"] == 2
    assert result.unit.landing == PurePosixPath("_templates/Home.md")
    assert result.document("_templates/Home.md").title == "Product"


def test_the_localized_subtree_is_skipped_and_counted(tmp_path: Path) -> None:
    """8,004 files, and the corpus's only localized tree."""
    files = basic()
    files["html/ja/Content/intro.htm"] = topic("はじめに")

    result = run(tmp_path, files)

    assert result.unit.skipped["localized-subtree"] == 1
    assert result.codes()["LOCALIZED_TREE_SKIPPED"] == 1


def test_an_api_tree_is_skipped_by_the_marker_predicate_and_not_by_its_name(
    tmp_path: Path,
) -> None:
    """The same `is_api_reference()` Stage 4 counted with -- 8,078 files, 56 versions."""
    files = basic()
    files["html/api/javadoc/index-all.html"] = "<html><body>Javadoc</body></html>"
    files["html/api/javadoc/Foo.html"] = "<html><body>class Foo</body></html>"

    skipped = run(tmp_path, files, api_roots=("html/api/javadoc",))
    assert skipped.unit.skipped["api-reference"] == 2
    assert "CONTENT_MISSING" not in skipped.codes()

    # Without the recorded roots the same files are a *report line*, never a guess:
    # the name `javadoc` decides nothing here, which is the whole point of §6.3.
    unrecorded = run(tmp_path, files)
    assert unrecorded.codes()["CONTENT_MISSING"] == 2
    assert unrecorded.unit.skipped["no-content-container"] == 2


def test_a_template_is_converted_when_the_toc_points_at_it(tmp_path: Path) -> None:
    """1,737 TOC entries across 660 of 676 roots point into `_templates/`."""
    files = basic()
    files["html/_templates/Legal.htm"] = topic("Legal and Third-Party Notices")
    files["html/_templates/Unused.htm"] = topic("Unused")
    files.update({f"html/{k}": v for k, v in toc_files(
        [{"i": 1}, {"i": 2}],
        {"Content/intro.htm": {"i": [1], "t": ["Intro"], "b": [""]},
         "_templates/Legal.htm": {"i": [2], "t": ["Legal"], "b": [""]}},
    ).items()})

    result = run(tmp_path, files)

    assert result.document("_templates/Legal.md").title == "Legal and Third-Party Notices"
    assert result.unit.skipped["unreferenced-template"] == 1


# -- content, chrome and titles (§5.1.6) ---------------------------------------


def test_there_is_one_content_selector_and_a_miss_is_a_report_line(tmp_path: Path) -> None:
    """4,656 of 4,660; the predecessor's fallbacks convert non-Flare files instead."""
    files = basic()
    files["html/Content/other.htm"] = "<html><body><div id='content'><h1>Other</h1></div></body></html>"

    result = run(tmp_path, files)

    assert [str(d.relative) for d in result.unit.documents if d.relative.name == "other.md"] == []
    assert result.unit.skipped["no-content-container"] == 1
    assert result.codes()["CONTENT_MISSING"] == 1


def test_the_title_is_the_h1_and_the_nav_label_is_the_tocs(tmp_path: Path) -> None:
    """`<title>` is the truncated one in ~10% of topics; the labels differ in 83 of 2,512."""
    result = run(tmp_path, basic())

    assert result.document("Content/intro.md").title == "Introduction"
    assert result.unit.nav[0].label == "Intro"


def test_the_feedback_survey_goes_before_any_link_is_read(tmp_path: Path) -> None:
    """95% of topics, 47.7% of every raw href -- all of them `javascript:void(0)`."""
    body = result_body = run(tmp_path, basic()).body("Content/intro.md")

    assert "helpful" not in result_body
    assert "javascript" not in body
    assert body == "# Introduction\n\nBody."


def test_a_comment_inside_the_container_is_not_prose(tmp_path: Path) -> None:
    """bs4 makes `Comment` a `NavigableString`, so the naive walk emits its text."""
    files = basic()
    files["html/Content/intro.htm"] = topic(
        "Introduction", "<!-- TODO: rewrite this --><p>Visible.</p>"
    )

    assert "TODO" not in run(tmp_path, files).body("Content/intro.md")


# -- `data-mc-autonum` (§5.1.8) -------------------------------------------------


def test_a_note_div_carrying_a_warning_autonum_is_a_warning(tmp_path: Path) -> None:
    """The class is ambiguous and the label is not: `div.note` + `Warning:` is one."""
    files = basic()
    files["html/Content/intro.htm"] = topic(
        "Introduction",
        "<div class='note' data-mc-autonum='Warning: '><p>Data is lost.</p></div>",
    )

    assert "> [!WARNING]\n> Data is lost." in run(tmp_path, files).body("Content/intro.md")


def test_the_note_prefix_comes_off_the_class_before_the_vocabulary_sees_it(
    tmp_path: Path,
) -> None:
    files = basic()
    files["html/Content/intro.htm"] = topic(
        "Introduction", "<div class='noteCaution'><p>Careful.</p></div>"
    )

    assert "> [!CAUTION]\n> Careful." in run(tmp_path, files).body("Content/intro.md")


def test_an_unmapped_callout_falls_back_to_note_and_is_reported_once(tmp_path: Path) -> None:
    """Detection is wider than the mapping, so an unknown kind is a NOTE and a finding.

    Reported once per distinct label rather than per occurrence: the point of the
    row is *which* word was seen, and the corpus's own vocabulary is closed at six
    class names, so the row means a project stylesheet the survey did not cover.
    """
    files = basic()
    files["html/Content/intro.htm"] = topic(
        "Introduction", "<div class='noteBestPractice'><p>Prefer this.</p></div>"
    )
    files["html/Content/guide/deep.htm"] = topic(
        "Deep dive", "<div class='noteBestPractice'><p>And this.</p></div>"
    )

    result = run(tmp_path, files)

    assert "> [!NOTE]\n> Prefer this." in result.body("Content/intro.md")
    assert [f.code for f in result.findings.all].count("ALERT_LABEL_UNMAPPED") == 1


def test_an_autonum_label_carrying_markup_arrives_as_text() -> None:
    """5 of 2,174 sampled topics; left alone the label emits HTML into the prose."""
    tag = parse(
        '<p data-mc-autonum=\'<b><span class="mcFormatSize">Note: </span></b>\'>x</p>'
    ).find("p")

    assert autonum_label(tag) == "Note:"


def test_a_task_label_runs_in_before_prose_and_stands_alone_before_a_list(
    tmp_path: Path,
) -> None:
    """Task structure survives only as autonum values: `Procedure` 702, `Result` 88."""
    files = basic()
    files["html/Content/intro.htm"] = topic(
        "Introduction",
        "<p data-mc-autonum='{b}Before you begin{/b}'>Install the server.</p>"
        "<div data-mc-autonum='{b}Procedure{/b}'><ol><li>Open the console.</li></ol></div>",
    )

    body = run(tmp_path, files).body("Content/intro.md")

    assert "**Before you begin** Install the server." in body
    assert "**Procedure**\n\n1. Open the console." in body


def test_the_rendered_autonumber_span_is_dropped_so_the_label_is_not_doubled(
    tmp_path: Path,
) -> None:
    files = basic()
    files["html/Content/intro.htm"] = topic(
        "Introduction",
        "<p data-mc-autonum='{b}Result{/b}'>"
        "<span class='autonumber'><span style='font-weight: bold;'>Result </span></span>"
        "The server starts.</p>",
    )

    assert run(tmp_path, files).body("Content/intro.md").count("Result") == 1


# -- the span vocabulary (§5.1.10, inherited) ----------------------------------


@pytest.mark.parametrize(
    ("markup", "expected"),
    [
        ("<span class='uicontrol'>OK</span>", "**OK**"),
        ("<span class='wintitle'>Console</span>", "**Console**"),
        ("<span class='filepath'>/etc/hosts</span>", "`/etc/hosts`"),
        ("<span class='varname'>name</span>", "*name*"),
        ("<span class='menucascade'>File &gt; Save</span>", "**File > Save**"),
        ("<code class='CodeItalic'>value</code>", "*value*"),
    ],
)
def test_the_span_vocabulary_maps_to_markdown(tmp_path: Path, markup: str, expected: str) -> None:
    files = basic()
    files["html/Content/intro.htm"] = topic("Introduction", f"<p>Click {markup} now.</p>")

    assert f"Click {expected} now." in run(tmp_path, files).body("Content/intro.md")


# -- lists that are tables (§5.1.7) --------------------------------------------


def test_an_autonumber_table_is_a_list_and_the_last_cell_is_the_item(
    tmp_path: Path,
) -> None:
    """1,321 in 7% of sampled topics; as a table each is a one-column pipe table."""
    files = basic()
    files["html/Content/intro.htm"] = topic(
        "Introduction",
        "<table class='TableStyle-AutoNumber_p_Bullet'>"
        "<tr><td>·</td><td><p>First</p></td></tr>"
        "<tr><td>·</td><td><p>Second</p></td></tr>"
        "</table>",
    )

    body = run(tmp_path, files).body("Content/intro.md")

    assert "- First\n- Second" in body
    assert "|" not in body


def test_the_autonum_decides_ordered_not_the_class_name(tmp_path: Path) -> None:
    """`Step` and `Bullet` both appear with and without numbering."""
    files = basic()
    files["html/Content/intro.htm"] = topic(
        "Introduction",
        "<table class='TableStyle-AutoNumber_p_Bullet'>"
        "<tr><td data-mc-autonum='{n+}. '><p>First</p></td></tr>"
        "</table>",
    )

    assert "1. First" in run(tmp_path, files).body("Content/intro.md")


def test_each_step_is_its_own_table_and_they_merge_into_one_list(tmp_path: Path) -> None:
    """Un-merged, every step restarts at 1 and every code block falls out of it."""
    files = basic()
    files["html/Content/intro.htm"] = topic(
        "Introduction",
        "<table class='TableStyle-AutoNumber_p_Step'>"
        "<tr><td data-mc-autonum='{n+}. '><p>Run the build.</p></td></tr></table>"
        "<pre>make build</pre>"
        "<table class='TableStyle-AutoNumber_p_Step'>"
        "<tr><td data-mc-autonum='{n+}. '><p>Check the log.</p></td></tr></table>",
    )

    body = run(tmp_path, files).body("Content/intro.md")

    assert "1. Run the build." in body
    assert "2. Check the log." in body
    assert "make build" in body


def test_a_full_width_colspan_row_becomes_a_label_and_the_table_splits(
    tmp_path: Path,
) -> None:
    """One ragged table GFM cannot carry becomes a label and tables that it can."""
    files = basic()
    files["html/Content/intro.htm"] = topic(
        "Introduction",
        "<table>"
        "<tr><td colspan='2'>Connection settings</td></tr>"
        "<tr><td>host</td><td>The server name</td></tr>"
        "</table>",
    )

    body = run(tmp_path, files).body("Content/intro.md")

    assert "**Connection settings**" in body
    assert "| host | The server name |" in body
    assert "colspan" not in body


def test_a_table_that_gfm_cannot_carry_passes_through_with_its_links_resolved(
    tmp_path: Path,
) -> None:
    """Invariant 13 does not stop at the edge of a pipe table -- 43% take this branch."""
    files = basic()
    files["html/Content/shot.png"] = "png"
    files["html/Content/intro.htm"] = topic(
        "Introduction",
        "<table><tr><td rowspan='2'><img src='shot.png'/></td>"
        "<td><a href='guide/deep.htm'>Deep</a></td></tr>"
        "<tr><td><a href='gone.htm'>Gone</a></td></tr></table>",
    )

    result = run(tmp_path, files)
    body = result.body("Content/intro.md")

    assert "<table>" in body
    assert 'src="shot.png"' in body
    assert 'href="guide/deep.md"' in body
    # The dangling one keeps its text and loses the claim that it leads somewhere.
    assert "Gone</a>" not in body and "Gone" in body
    assert PurePosixPath("Content/shot.png") in result.context.assets.copy_set


# -- links and assets (§5.1.3, invariant 13) -----------------------------------


def test_a_cross_reference_becomes_a_relative_markdown_path(tmp_path: Path) -> None:
    files = basic()
    files["html/Content/guide/deep.htm"] = topic(
        "Deep dive", "<p>See <a href='../intro.htm#section'>the introduction</a>.</p>"
    )

    body = run(tmp_path, files).body("Content/guide/deep.md")

    assert "[the introduction](../intro.md#section)" in body


def test_a_reference_to_a_topic_this_run_did_not_produce_keeps_its_text(
    tmp_path: Path,
) -> None:
    """1.7% of the corpus's topic links already point at nothing in the source."""
    files = basic()
    files["html/Content/intro.htm"] = topic(
        "Introduction", "<p>See <a href='gone.htm'>the old page</a>.</p>"
    )

    result = run(tmp_path, files)

    assert "See the old page." in result.body("Content/intro.md")
    assert result.codes()["TOPIC_LINK_DANGLING"] == 1


@pytest.mark.parametrize(
    ("href", "expected"),
    [
        ("https://docs.example/x", "[here](https://docs.example/x)"),
        ("mailto:support@example.com", "[here](mailto:support@example.com)"),
        ("javascript:void(0);", "here"),
        ("#later", "[here](#later)"),
        ("/shared/x.htm", "[here](/shared/x.htm)"),
    ],
)
def test_references_that_are_not_topic_paths_are_emitted_verbatim_or_not_at_all(
    tmp_path: Path, href: str, expected: str
) -> None:
    files = basic()
    files["html/Content/intro.htm"] = topic("Introduction", f"<p>Look <a href='{href}'>here</a>.</p>")

    assert f"Look {expected}." in run(tmp_path, files).body("Content/intro.md")


def test_an_asset_is_resolved_and_copied_by_the_same_call_and_a_topic_is_not(
    tmp_path: Path,
) -> None:
    """The copy set is what the Markdown references, and it holds no HTML."""
    files = basic()
    files["html/Content/images/shot.png"] = "png"
    files["html/Content/files/guide.pdf"] = "pdf"
    files["html/Content/intro.htm"] = topic(
        "Introduction",
        "<p><img src='images/shot.png' alt='The console'/>"
        "<a href='files/guide.pdf'>The guide</a>"
        "<a href='guide/deep.htm'>Deep</a></p>",
    )

    result = run(tmp_path, files)
    body = result.body("Content/intro.md")

    assert "![The console](images/shot.png)" in body
    assert "[The guide](files/guide.pdf)" in body
    assert "[Deep](guide/deep.md)" in body
    assert set(result.context.assets.copy_set) == {
        PurePosixPath("Content/images/shot.png"), PurePosixPath("Content/files/guide.pdf"),
    }


def test_a_missing_image_emits_neither_link_nor_copy(tmp_path: Path) -> None:
    files = basic()
    files["html/Content/intro.htm"] = topic(
        "Introduction", "<p><img src='images/gone.png' alt='Gone'/>Text.</p>"
    )

    result = run(tmp_path, files)

    assert "Gone" not in result.body("Content/intro.md")
    assert result.context.assets.copy_set == {}
    assert result.context.assets.counts.dangling == 1


# -- the landing page (§5.1.5) --------------------------------------------------


def test_the_landing_page_is_converted_and_named_even_when_the_toc_omits_it(
    tmp_path: Path,
) -> None:
    """`DefaultUrl` resolves in 676 of 676 roots and is in no TOC in 55 of 60."""
    result = run(tmp_path, basic())

    assert result.unit.landing == PurePosixPath("_templates/Home.md")
    assert "Everything you need to install" in result.body("_templates/Home.md")
    # It is not an orphan: the Unfiled node is for topics, not for the landing page.
    labels = [node.label for node in result.unit.nav]
    assert "_templates/Home.md" not in [
        str(child.document) for node in result.unit.nav for child in node.children
    ]
    assert labels[:2] == ["Intro", "Deep"]


def test_a_landing_page_with_no_container_falls_back_to_the_body(tmp_path: Path) -> None:
    """5 roots, all `statistica-lts-release/overview.htm`, 3,444 chars of real prose."""
    files = basic()
    files["html/_templates/Home.htm"] = (
        f"<html><body><h1>Overview</h1>{LANDING_PROSE}</body></html>"
    )

    result = run(tmp_path, files)

    assert result.document("_templates/Home.md").title == "Overview"
    assert "Everything you need to install" in result.body("_templates/Home.md")


def test_a_landing_title_falls_back_to_the_product_variable_then_the_catalog(
    tmp_path: Path,
) -> None:
    """24 landing pages have no `h1` and only 2 of those a usable `<title>`."""
    files = basic()
    files["html/_templates/Home.htm"] = page(
        "<span class='mc-variable productvar productName'>Acme Server</span>"
        "<p>Everything you need to run the server is here.</p>"
    )
    assert run(tmp_path, files).document("_templates/Home.md").title == "Acme Server"

    files["html/_templates/Home.htm"] = page("<p>Everything you need is here on this page.</p>")
    named = run(tmp_path, files, product_name="TIBCO Acme")
    assert named.document("_templates/Home.md").title == "TIBCO Acme"


def test_a_hero_only_landing_page_becomes_a_generated_stub(tmp_path: Path) -> None:
    """55 of 676 roots: a title and a version and nothing else."""
    files = basic()
    files["html/_templates/Home.htm"] = page(
        "<h1>Acme Server</h1><div id='release-info'>10.5.0</div>"
        "<div class='download-button'><a href='x.zip'>Download</a></div>"
    )

    result = run(tmp_path, files)
    landing = result.document("_templates/Home.md")

    assert landing.body == "# Acme Server"
    assert landing.frontmatter == {"generated": True}
    assert result.codes()["LANDING_PAGE_EMPTY"] == 1


def test_dropdowns_unroll_on_the_landing_page_and_nowhere_else(tmp_path: Path) -> None:
    """457 of the 459 files using the construct are this page; 1 content topic is."""
    dropdown = (
        "<div class='MCDropDown'>"
        "<div class='MCDropDownHead'><a href='javascript:void(0);'>Release Documents</a></div>"
        f"<div class='MCDropDownBody'>{LANDING_PROSE}</div>"
        "</div>"
    )
    files = basic()
    files["html/_templates/Home.htm"] = page(f"<h1>Acme Server</h1>{dropdown}")
    files["html/Content/intro.htm"] = topic("Introduction", dropdown)

    result = run(tmp_path, files)

    assert "## Release Documents" in result.body("_templates/Home.md")
    assert "## Release Documents" not in result.body("Content/intro.md")
    assert "Everything you need to install" in result.body("Content/intro.md")


# -- navigation (§5.1.4, §5.1.5) ------------------------------------------------


def test_a_topic_in_no_toc_entry_is_filed_under_unfiled_and_counted(tmp_path: Path) -> None:
    """Coverage is 85.9% corpus-wide, so 14% is normal and silence is not."""
    files = basic()
    files["html/Content/orphan.htm"] = topic("Orphan")

    result = run(tmp_path, files)

    unfiled = result.unit.nav[-1]
    assert unfiled.label == "Unfiled"
    assert [str(child.document) for child in unfiled.children] == ["Content/orphan.md"]
    assert result.codes()["TOC_ORPHAN"] == 1


def test_a_headless_node_keeps_its_children_and_a_childless_one_is_dropped(
    tmp_path: Path,
) -> None:
    """165 headless nodes: 158 have children and 7 do not."""
    files = basic()
    files.update({f"html/{k}": v for k, v in toc_files(
        [{"i": 1, "n": [{"i": 2}]}, {"i": 3}],
        {"___": {"i": [1, 3], "t": ["Concepts", "Empty"], "b": ["", ""]},
         "Content/intro.htm": {"i": [2], "t": ["Intro"], "b": [""]}},
    ).items()})

    result = run(tmp_path, files)

    concepts = result.unit.nav[0]
    assert (concepts.label, concepts.document) == ("Concepts", None)
    assert [child.label for child in concepts.children] == ["Intro"]
    assert "Empty" not in [node.label for node in result.unit.nav]
    assert result.codes()["NAV_NODE_DROPPED"] == 1


def test_a_container_pointing_at_its_own_child_s_page_keeps_the_topic_once(
    tmp_path: Path,
) -> None:
    """30 corpus containers do this; both nodes would publish the same page twice."""
    files = basic()
    files.update({f"html/{k}": v for k, v in toc_files(
        [{"i": 1, "n": [{"i": 2}, {"i": 3}]}],
        {"Content/intro.htm": {"i": [1, 2], "t": ["Introduction", "Overview"], "b": ["", ""]},
         "Content/guide/deep.htm": {"i": [3], "t": ["Deep"], "b": [""]}},
    ).items()})

    result = run(tmp_path, files)
    parent = result.unit.nav[0]

    assert str(parent.document) == "Content/intro.md"
    assert [child.label for child in parent.children] == ["Deep"]


def test_the_bookmark_on_a_toc_entry_survives(tmp_path: Path) -> None:
    """12.1% carry one, and several entries routinely share a page."""
    result = run(tmp_path, basic())

    assert [(node.label, node.anchor) for node in result.unit.nav] == [
        ("Intro", ""), ("Deep", "section"),
    ]


def test_a_second_toc_tree_becomes_a_sibling_top_level_node(tmp_path: Path) -> None:
    """The declared tree covers 53 of 106 topics in `bctcm/6.2.0`."""
    files = basic()
    files.update({f"html/{k}": v for k, v in toc_files(
        [{"i": 1}],
        {"Content/guide/deep.htm": {"i": [1], "t": ["Deep"], "b": [""]}},
        name="_HTML_gateway_server",
    ).items()})

    result = run(tmp_path, files)

    assert [node.label for node in result.unit.nav] == ["Intro", "Deep", "gateway server"]
    assert [child.label for child in result.unit.nav[-1].children] == ["Deep"]


# -- the support and legal tail (§5.1.5) ---------------------------------------


def test_the_tail_pages_are_picked_by_the_toc_and_never_by_name(tmp_path: Path) -> None:
    """49 roots ship 2+ support pages and in all 54 the TOC references exactly one."""
    files = basic()
    files["html/_templates/Support.htm"] = topic("ibi Documentation and Support Services")
    files["html/_templates/Support_old.htm"] = topic("TIBCO Documentation and Support Services")
    files["html/_templates/Legal-and-Third-Party-Notices.htm"] = topic("Legal Notices")
    files["html/_templates/Legal_and_Third-Party_Notices.htm"] = topic("Legal Notices")
    files.update({f"html/{k}": v for k, v in toc_files(
        [{"i": 1}, {"i": 2}, {"i": 3}],
        {"Content/intro.htm": {"i": [1], "t": ["Intro"], "b": [""]},
         "_templates/Support.htm": {"i": [2],
                                    "t": ["ibi Documentation and Support Services"], "b": [""]},
         "_templates/Legal-and-Third-Party-Notices.htm": {"i": [3],
                                                          "t": ["Legal Notices"], "b": [""]}},
    ).items()})

    result = run(tmp_path, files)

    assert result.unit.support == PurePosixPath("_templates/Support.md")
    assert result.unit.legal == PurePosixPath("_templates/Legal-and-Third-Party-Notices.md")
    # The label is carried, never constanted: `ibi` in 49 roots, `Spotfire` in 45.
    assert result.document("_templates/Support.md").title.startswith("ibi ")
    assert "TAIL_PAGE_MISSING" not in result.codes()


def test_a_root_with_no_tail_pages_reports_their_absence_and_synthesizes_nothing(
    tmp_path: Path,
) -> None:
    """7 roots ship no legal page and 8 no support page."""
    result = run(tmp_path, basic())

    assert (result.unit.support, result.unit.legal) == (None, None)
    assert result.codes()["TAIL_PAGE_MISSING"] == 2


# -- the selector itself --------------------------------------------------------


def test_the_content_selector_is_one_selector(tmp_path: Path) -> None:
    """A guard on the rule, not on the string: a fallback chain is what §5.1.6 forbids."""
    assert "," not in CONTENT_SELECTOR
