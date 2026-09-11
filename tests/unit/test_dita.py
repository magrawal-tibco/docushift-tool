"""Unit tests for the SDL DITA engine (planning.md Phase 5c).

Every fixture is a miniature doc-set -- a flat directory of `GUID-*.html` plus
`suitehelp_topic_list.html` -- because that is the unit the engine works in and
because most of §5.2's rules are only visible at that scale: which slug a topic
gets depends on what else is in the doc-set, whether an anchor survives depends on
whether anything else points at it, and whether two files become one page depends
on their identifiers rather than on their names.

The assertions are on the *corpus's* rules, not on DITA in general, and the tests
that look oddly specific are the ones where the tempting implementation is wrong
on real input:

- `sectiontitle` stays `##`, because §5.2.5's own table says `###` and the tag
  disagrees with the table 926 times;
- `wintitle` survives, because the label spans this engine deletes all end in
  `title` and one of them is content;
- a republished duplicate is paired by *identifier*, because its filename ends in
  a bare digit that matches no `_unique` pattern;
- `DC.Relation` builds no hierarchy, because it is the one metadata field that
  looks exactly like a parent pointer and is not.
"""

from collections.abc import Mapping
from pathlib import Path

import pytest

from docushift.engines.base import ConversionContext, Unit
from docushift.engines.dita import CONTENT_SELECTOR, DitaEngine, read_toc
from docushift.engines.roots import find_output_roots
from docushift.models import SourceEngine
from docushift.reporting.findings import FindingsRun
from docushift.transforms.assets import AssetCopier

# -- fixtures in the small ------------------------------------------------------


def build(directory: Path, files: Mapping[str, str]) -> Path:
    for name, text in files.items():
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return directory


def topic(guid: str, title: str, body: str = "<p>Body.</p>", *,
          identifier: str = "", relation: str = "") -> str:
    """One SuiteHelp topic: the XML prologue, the `DC.*` head, one `<article>`.

    The prologue is real -- every corpus topic starts `<?xml …?>` -- and it is
    here because it is what makes lxml warn when the file is parsed as HTML, which
    `transforms/markdown.py` does deliberately.
    """
    relation_meta = f'<meta name="DC.Relation" scheme="URI" content="{relation}" />' if relation else ""
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<html><head>"
        '<meta name="DC.Type" content="topic" />'
        f'<meta name="DC.Identifier" content="{identifier or guid}" />'
        f'<meta name="DC.Title" content="{title}" />'
        f"{relation_meta}"
        f"<title>{title}</title>"
        "</head><body>"
        f'<article role="article" aria-labelledby="ariaid-title1">'
        f'<h1 class="topictitle1" id="ariaid-title1">{title}</h1>'
        f"{body}"
        f'<div class="familylinks"><div class="linklist">'
        f'<strong>Parent topic:</strong> <a href="GUID-ROOT.html">Overview</a></div></div>'
        f'<div id="copyright"><p>Copyright &copy; 2026 Cloud Software Group.</p></div>'
        "</article></body></html>"
    )


def homepage(guid: str = "GUID-HOME") -> dict[str, str]:
    return {f"{guid}-homepage.html": (
        "<html><body><article>"
        '<div class="titles">'
        '<div class="publication-title">Spotfire Server</div>'
        '<div class="release-version">14.2.0</div>'
        '<div class="release-date">March 2026</div>'
        "</div></article></body></html>"
    )}


def toc(items: str, name: str = "suitehelp_topic_list.html") -> dict[str, str]:
    return {name: f"<html><body><ul>{items}</ul></body></html>"}


def node(guid: str, label: str, children: str = "") -> str:
    """One TOC `<li>`, with `data-audience` -- `NONE` in 4,994 of 4,994, not a filter."""
    nested = f"<ul>{children}</ul>" if children else ""
    return (
        f'<li id="toc-{guid}" data-audience="NONE">'
        f'<a href="{guid}.html">{label}</a>{nested}</li>'
    )


# -- running one tree -----------------------------------------------------------


class Run:
    """One conversion of one extracted tree, with its units and its findings."""

    def __init__(self, units: list[Unit], findings: FindingsRun, tree: Path):
        self.units = units
        self.findings = findings
        self.tree = tree

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

    def names(self, unit: Unit | None = None) -> list[str]:
        return sorted(str(d.relative) for d in (unit or self.unit).documents)

    def codes(self) -> dict[str, int]:
        tally: dict[str, int] = {}
        for finding in self.findings.all:
            tally[finding.code] = tally.get(finding.code, 0) + finding.count
        return tally

    def messages(self, code: str) -> list[str]:
        return [f.message for f in self.findings.all if f.code == code]


def run(tmp_path: Path, files: Mapping[str, str]) -> Run:
    """Converts every doc-set in a tree, the way the driver does."""
    tree = build(tmp_path / "tree", files)
    output = tmp_path / "out"
    findings = FindingsRun("convert")
    context = ConversionContext(
        tree=tree,
        output=output,
        engine=SourceEngine.DITA,
        slug="prod",
        version="1.0.0",
        product_name="Spotfire Server",
        api_roots=[],
        output_roots=find_output_roots(tree, SourceEngine.DITA),
        findings=findings,
    )
    engine = DitaEngine()
    units = []
    for root in engine.units(context):
        name = root.relative_to(tree).as_posix()
        context.assets = AssetCopier(root, SourceEngine.DITA, output / name if name else output)
        units.append(engine.convert_unit(context, root))
    return Run(units, findings, tree)


# -- the unit of work (§5.2.1) --------------------------------------------------


def test_the_doc_set_is_located_by_its_guid_filenames(tmp_path: Path) -> None:
    """`GUID-*.html` *is* the definition of a SuiteHelp doc-set, so no sniffing."""
    result = run(tmp_path, {
        "doc/html/GUID-AAA1.html": topic("GUID-AAA1", "Getting Started"),
        **{f"doc/html/{k}": v for k, v in toc(node("GUID-AAA1", "Getting Started")).items()},
    })
    assert [unit.name for unit in result.units] == ["doc/html"]
    assert result.names() == ["getting-started.md"]


def test_a_file_named_doc_set_is_reported_and_never_converted(tmp_path: Path) -> None:
    """The §5.2.1 guard: ~55 versions ship `article` with no GUID filenames.

    Every product publishing that flavour is on the §3.10 exclusion list, so this
    can only fire if one is readmitted. Without it, a bare-`article` tree would run
    the SuiteHelp path and emit plausible-looking wrong output instead of a line.
    """
    result = run(tmp_path, {
        "html/topics/administrator_roles.html":
            "<html><head><meta name='DC.type' content='topic'/></head>"
            "<body><article role='article'><h1>Roles</h1><p>Body.</p></article></body></html>",
    })
    assert result.units == []
    assert "DOCSET_SKIPPED" in result.codes()
    assert any("file-named" in message for message in result.messages("DOCSET_SKIPPED"))


def test_only_the_root_s_own_topics_are_enumerated(tmp_path: Path) -> None:
    """The doc-set is flat in 297 of 353, and the one subdirectory is `static/`.

    An API tree bundled inside a doc-set is a subdirectory, so flat enumeration
    excludes it by construction -- which is why no API predicate runs in §5.2.
    """
    result = run(tmp_path, {
        "html/GUID-AAA1.html": topic("GUID-AAA1", "Getting Started"),
        "html/javadoc/index.html": "<html><body><article><h1>All Classes</h1></article></body></html>",
        "html/static/skin.css": "body { margin: 0 }",
        **{f"html/{k}": v for k, v in toc(node("GUID-AAA1", "Getting Started")).items()},
    })
    assert result.names() == ["getting-started.md"]


def test_non_topic_html_beside_the_topics_is_counted_not_silent(tmp_path: Path) -> None:
    result = run(tmp_path, {
        "html/GUID-AAA1.html": topic("GUID-AAA1", "Getting Started"),
        "html/index.html": '<html><head><meta name="redirectUrl" content="GUID-HOME-homepage.html"/>'
                           "</head><body></body></html>",
        **{f"html/{k}": v for k, v in toc(node("GUID-AAA1", "Getting Started")).items()},
    })
    # `index.html` and the TOC file itself: consumed or discarded, counted either way.
    assert result.unit.skipped["not-a-topic"] == 2


# -- content extraction (§5.2.4) ------------------------------------------------


def test_content_is_the_article_and_chrome_inside_it_comes_out(tmp_path: Path) -> None:
    """`<article>` matches 3,742 of 3,742, and the chrome lives *inside* it."""
    result = run(tmp_path, {
        "html/GUID-AAA1.html": topic("GUID-AAA1", "Getting Started"),
        **{f"html/{k}": v for k, v in toc(node("GUID-AAA1", "Getting Started")).items()},
    })
    body = result.body("getting-started.md")
    assert body.startswith("# Getting Started")
    assert "Body." in body
    # `div.familylinks` is publisher-generated navigation that `toc.yml` reproduces,
    # and `div#copyright` is the footer. Neither survives.
    assert "Parent topic" not in body
    assert "Cloud Software Group" not in body


def test_a_topic_with_no_article_is_reported_and_not_converted(tmp_path: Path) -> None:
    result = run(tmp_path, {
        "html/GUID-AAA1.html": topic("GUID-AAA1", "Getting Started"),
        "html/GUID-BBB2.html": "<html><body><div id='content'><h1>Stray</h1></div></body></html>",
        **{f"html/{k}": v for k, v in toc(node("GUID-AAA1", "Getting Started")).items()},
    })
    assert result.names() == ["getting-started.md"]
    assert result.codes()["CONTENT_MISSING"] == 1
    assert result.unit.skipped["no-content-container"] == 1
    assert CONTENT_SELECTOR == "article"


# -- callouts (§5.2.5) ----------------------------------------------------------


def test_a_callout_loses_its_label_span_because_gfm_draws_the_label(tmp_path: Path) -> None:
    """1:1 in every kind measured -- 364 `span.notetitle` for 364 `div.note`.

    Left in, the output reads `> [!NOTE]` and then `**Note:** Note: Save first.`
    """
    result = run(tmp_path, {
        "html/GUID-AAA1.html": topic("GUID-AAA1", "Getting Started",
            '<div class="note note"><span class="notetitle">Note:</span> Save first.</div>'),
        **{f"html/{k}": v for k, v in toc(node("GUID-AAA1", "Getting Started")).items()},
    })
    body = result.body("getting-started.md")
    assert "> [!NOTE]" in body
    assert "> Save first." in body
    assert "Note:" not in body


@pytest.mark.parametrize(
    ("kind", "alert"),
    [("tip", "TIP"), ("important", "IMPORTANT"), ("warning", "WARNING"), ("caution", "CAUTION")],
)
def test_each_alert_kind_maps_to_its_own_admonition(tmp_path: Path, kind: str, alert: str) -> None:
    result = run(tmp_path, {
        "html/GUID-AAA1.html": topic("GUID-AAA1", "Getting Started",
            f'<div class="note {kind}"><span class="{kind}title">{kind.title()}:</span> Mind this.</div>'),
        **{f"html/{k}": v for k, v in toc(node("GUID-AAA1", "Getting Started")).items()},
    })
    assert f"> [!{alert}]" in result.body("getting-started.md")


@pytest.mark.parametrize(
    ("kind", "alert", "label"),
    [("remember", "NOTE", "Remember:"), ("attention", "IMPORTANT", "Attention:"),
     ("restriction", "IMPORTANT", "Restriction:")],
)
def test_a_collapsed_kind_keeps_its_authored_label(tmp_path: Path, kind: str,
                                                   alert: str, label: str) -> None:
    """GitHub has five alerts and DITA has eight. The collapse loses the rendering,
    not the word: `remember` becomes a NOTE whose first bolded run says Remember."""
    result = run(tmp_path, {
        "html/GUID-AAA1.html": topic("GUID-AAA1", "Getting Started",
            f'<div class="note {kind}"><span class="{kind}title">{label}</span> Mind this.</div>'),
        **{f"html/{k}": v for k, v in toc(node("GUID-AAA1", "Getting Started")).items()},
    })
    body = result.body("getting-started.md")
    assert f"> [!{alert}]" in body
    assert f"> **{label}** Mind this." in body


def test_a_window_title_is_content_and_survives_the_label_sweep(tmp_path: Path) -> None:
    """The `[class$='title']` trap. Every callout label span ends in `title` --
    and so do the 265 `span.wintitle` in the same sample, which name windows."""
    result = run(tmp_path, {
        "html/GUID-AAA1.html": topic("GUID-AAA1", "Getting Started",
            '<p>Open the <span class="wintitle">Data Sources</span> dialog.</p>'),
        **{f"html/{k}": v for k, v in toc(node("GUID-AAA1", "Getting Started")).items()},
    })
    assert "**Data Sources**" in result.body("getting-started.md")


def test_a_dtd_kind_this_corpus_lacks_is_still_mapped_by_the_shared_vocabulary(
    tmp_path: Path,
) -> None:
    """`fastpath` is in the DITA DTD and not in this corpus's eight observed kinds.

    It is recognized by its own label span rather than by the class list, so it is
    seen rather than swallowed -- and `transforms/callouts.py` already knows it,
    which is the whole reason the alert vocabulary is shared across engines instead
    of each engine keeping its own table.
    """
    result = run(tmp_path, {
        "html/GUID-AAA1.html": topic("GUID-AAA1", "Getting Started",
            '<div class="note fastpath"><span class="fastpathtitle">Fastpath:</span> Skip ahead.</div>'),
        **{f"html/{k}": v for k, v in toc(node("GUID-AAA1", "Getting Started")).items()},
    })
    body = result.body("getting-started.md")
    assert "> [!TIP]" in body
    assert "> **Fastpath:** Skip ahead." in body
    assert "ALERT_LABEL_UNMAPPED" not in result.codes()


def test_a_kind_the_vocabulary_has_never_seen_is_reported_once(tmp_path: Path) -> None:
    """A project-defined type outside both the DTD and the vocabulary: NOTE, its
    authored label kept, and **one** row per distinct label rather than per
    occurrence. This is what keeps `ALERT_LABEL_UNMAPPED` reachable in §5.2."""
    result = run(tmp_path, {
        "html/GUID-AAA1.html": topic("GUID-AAA1", "Getting Started",
            '<div class="note bestpractice"><span class="bestpracticetitle">Best practice:</span>'
            " Use a proxy.</div>"
            '<div class="note bestpractice"><span class="bestpracticetitle">Best practice:</span>'
            " And again.</div>"),
        **{f"html/{k}": v for k, v in toc(node("GUID-AAA1", "Getting Started")).items()},
    })
    body = result.body("getting-started.md")
    assert "> [!NOTE]" in body
    assert "> **Best practice:** Use a proxy." in body
    assert result.codes()["ALERT_LABEL_UNMAPPED"] == 1


def test_the_admonition_family_class_never_wins_over_its_type(tmp_path: Path) -> None:
    """DITA-OT writes `class="note tip"`. Picking the first class in any fixed
    order renders `tip` and `warning` as plain NOTEs and leaves `caution` correct,
    which is the shape of bug that looks like it works."""
    result = run(tmp_path, {
        "html/GUID-AAA1.html": topic("GUID-AAA1", "Getting Started",
            '<div class="note warning"><span class="warningtitle">Warning:</span> Careful.</div>'),
        **{f"html/{k}": v for k, v in toc(node("GUID-AAA1", "Getting Started")).items()},
    })
    assert "> [!WARNING]" in result.body("getting-started.md")


# -- the class vocabulary (§5.2.5, corrected) -----------------------------------


def test_a_section_heading_keeps_the_level_its_tag_states(tmp_path: Path) -> None:
    """§5.2.5's table maps `sectiontitle` to `###`. The corpus emits it on an `h2`
    922 times and an `h3` four times, so honouring the table would demote every
    section heading in the corpus and break the four that were already right."""
    result = run(tmp_path, {
        "html/GUID-AAA1.html": topic("GUID-AAA1", "Getting Started",
            '<h2 class="sectiontitle">Prerequisites</h2><p>First.</p>'
            '<h3 class="sectiontitle">Detail</h3><p>Second.</p>'),
        **{f"html/{k}": v for k, v in toc(node("GUID-AAA1", "Getting Started")).items()},
    })
    body = result.body("getting-started.md")
    assert "## Prerequisites" in body
    assert "### Detail" in body


def test_the_class_overrides_the_tag_where_the_two_disagree(tmp_path: Path) -> None:
    """`varname` is a `<var>`, which the shared walk italicizes; DITA means code."""
    result = run(tmp_path, {
        "html/GUID-AAA1.html": topic("GUID-AAA1", "Getting Started",
            '<p>Set <var class="varname">SERVER_HOME</var> in '
            '<span class="filepath">/etc/profile</span> and click '
            '<span class="uicontrol">Apply</span>.</p>'),
        **{f"html/{k}": v for k, v in toc(node("GUID-AAA1", "Getting Started")).items()},
    })
    body = result.body("getting-started.md")
    assert "`SERVER_HOME`" in body
    assert "`/etc/profile`" in body
    assert "**Apply**" in body


def test_a_menu_cascade_is_not_bolded_around_its_bolded_children(tmp_path: Path) -> None:
    """2,618 of 2,619 `menucascade` hold at least one `uicontrol`, which is already
    bold. Mapping the wrapper too emits `** **File** > **Save** **`."""
    result = run(tmp_path, {
        "html/GUID-AAA1.html": topic("GUID-AAA1", "Getting Started",
            '<p>Choose <span class="menucascade"><span class="uicontrol">File</span>'
            ' &gt; <span class="uicontrol">Save</span></span>.</p>'),
        **{f"html/{k}": v for k, v in toc(node("GUID-AAA1", "Getting Started")).items()},
    })
    body = result.body("getting-started.md")
    assert "**File**" in body
    assert "**Save**" in body
    assert "** **" not in body


def test_a_code_block_is_fenced_without_a_language(tmp_path: Path) -> None:
    """255 `pre.codeblock` and 6 `pre.msgblock`, and not one carries a language."""
    result = run(tmp_path, {
        "html/GUID-AAA1.html": topic("GUID-AAA1", "Getting Started",
            '<pre class="pre codeblock">server start --port 8080</pre>'),
        **{f"html/{k}": v for k, v in toc(node("GUID-AAA1", "Getting Started")).items()},
    })
    assert "```\nserver start --port 8080\n```" in result.body("getting-started.md")


def test_a_figure_caption_becomes_italic_prose(tmp_path: Path) -> None:
    result = run(tmp_path, {
        "html/GUID-AAA1.html": topic("GUID-AAA1", "Getting Started",
            '<div class="fignone"><div class="figcap">Figure 1. The console</div>'
            '<p>Diagram.</p></div>'),
        **{f"html/{k}": v for k, v in toc(node("GUID-AAA1", "Getting Started")).items()},
    })
    assert "*Figure 1. The console*" in result.body("getting-started.md")


# -- cross-references (§5.2.6) --------------------------------------------------


def two_topics(body: str) -> dict[str, str]:
    return {
        "html/GUID-AAA1.html": topic("GUID-AAA1", "Getting Started", body),
        "html/GUID-BBB2.html": topic(
            "GUID-BBB2", "Installing",
            '<p id="GUID-BBB2__STEP_ONE">Unpack the archive.</p>'
            '<p><a name="GUID-BBB2__LEGACY"></a>Then run the installer.</p>'),
        **{f"html/{k}": v for k, v in toc(
            node("GUID-AAA1", "Getting Started", node("GUID-BBB2", "Installing"))).items()},
    }


def test_a_guid_reference_becomes_a_link_to_the_target_s_slug(tmp_path: Path) -> None:
    result = run(tmp_path, two_topics('<p>See <a href="GUID-BBB2.html">Installing</a>.</p>'))
    assert "[Installing](installing.md)" in result.body("getting-started.md")


def test_an_extensionless_guid_reference_still_resolves(tmp_path: Path) -> None:
    """Matched on the GUID and never on the suffix: an extensionless href is rare
    -- 4 of 43,353 in the large scan -- and a suffix-keyed rewriter drops it silently."""
    result = run(tmp_path, two_topics('<p>See <a href="GUID-BBB2">Installing</a>.</p>'))
    assert "[Installing](installing.md)" in result.body("getting-started.md")


def test_a_fragment_naming_the_target_topic_itself_is_dropped(tmp_path: Path) -> None:
    """73% of all fragments are this: `GUID-X.html#GUID-X` names the whole page."""
    result = run(tmp_path, two_topics('<p>See <a href="GUID-BBB2.html#GUID-BBB2">Installing</a>.</p>'))
    assert "[Installing](installing.md)" in result.body("getting-started.md")
    assert "installing.md#" not in result.body("getting-started.md")


@pytest.mark.parametrize("anchor", ["GUID-BBB2__STEP_ONE", "GUID-BBB2__LEGACY"])
def test_a_real_sub_anchor_survives_at_both_ends(tmp_path: Path, anchor: str) -> None:
    """The id half is not optional: 8,056 id-bearing elements pair with an
    `<a name>` and **7,377 do not**, so reading `<a>` alone keeps under half."""
    result = run(tmp_path, two_topics(f'<p>See <a href="GUID-BBB2.html#{anchor}">step</a>.</p>'))
    assert f"[step](installing.md#{anchor})" in result.body("getting-started.md")
    assert f'<a id="{anchor}"></a>' in result.body("installing.md")


def test_an_unreferenced_anchor_is_not_emitted(tmp_path: Path) -> None:
    """~8.6 anchors per topic exist and 2,192 of 27,990 are ever pointed at."""
    result = run(tmp_path, two_topics("<p>Nothing points anywhere.</p>"))
    body = result.body("installing.md")
    assert "<a id=" not in body
    assert "Unpack the archive." in body


def test_a_dangling_bookmark_keeps_the_link_and_loses_the_anchor(tmp_path: Path) -> None:
    """27 of 34 dangling fragments carry SDL's own `missing-elem-id` marker: the
    publisher declaring a cross-reference it could not resolve. A source defect,
    so the file link survives and only the bookmark is dropped."""
    result = run(tmp_path, two_topics(
        '<p>See <a href="GUID-BBB2.html#GUID-BBB2__missing-elem-id--GUID-CCC3">step</a>.</p>'))
    assert "[step](installing.md)" in result.body("getting-started.md")
    assert result.codes()["TOPIC_LINK_DANGLING"] == 1
    assert any("bookmark dropped" in m for m in result.messages("TOPIC_LINK_DANGLING"))


def test_a_reference_to_an_absent_topic_is_reported_and_unlinked(tmp_path: Path) -> None:
    result = run(tmp_path, two_topics('<p>See <a href="GUID-ZZZ9.html">Gone</a>.</p>'))
    body = result.body("getting-started.md")
    assert "Gone" in body
    assert "](" not in body
    assert result.codes()["TOPIC_LINK_DANGLING"] == 1


def test_a_cross_repo_html_link_is_reported_rather_than_copied(tmp_path: Path) -> None:
    """`javadoc/index.html` is a link into the `-resources` tree this run does not
    produce. Handed to the asset copier it would resolve, and an HTML page would be
    copied into the Markdown output -- the predecessor's Javadoc leak, by another door."""
    result = run(tmp_path, two_topics('<p>See <a href="javadoc/index.html">the API</a>.</p>'))
    assert result.codes()["TOPIC_LINK_DANGLING"] == 1


def test_an_absolute_url_is_left_exactly_as_written(tmp_path: Path) -> None:
    result = run(tmp_path, two_topics('<p>See <a href="https://example.com/x">docs</a>.</p>'))
    assert "[docs](https://example.com/x)" in result.body("getting-started.md")


def test_a_same_page_fragment_resolves_against_this_topic_s_own_anchors(tmp_path: Path) -> None:
    result = run(tmp_path, {
        "html/GUID-AAA1.html": topic("GUID-AAA1", "Getting Started",
            '<p>Jump to <a href="#GUID-AAA1__LATER">the end</a>.</p>'
            '<p id="GUID-AAA1__LATER">The end.</p>'),
        **{f"html/{k}": v for k, v in toc(node("GUID-AAA1", "Getting Started")).items()},
    })
    body = result.body("getting-started.md")
    assert "[the end](#GUID-AAA1__LATER)" in body
    assert '<a id="GUID-AAA1__LATER"></a>' in body


# -- images (§5.2.6) ------------------------------------------------------------


def test_a_content_image_keeps_its_source_filename_and_is_copied(tmp_path: Path) -> None:
    """92% of images carry no `alt`, so the predecessor's alt-derived rename falls
    back to the GUID almost always and is abandoned rather than inherited."""
    files = {
        "html/GUID-AAA1.html": topic("GUID-AAA1", "Getting Started",
            '<p><img src="GUID-9F1B-low.png" /></p>'),
        **{f"html/{k}": v for k, v in toc(node("GUID-AAA1", "Getting Started")).items()},
    }
    tree = build(tmp_path / "tree", files)
    (tree / "html" / "GUID-9F1B-low.png").write_bytes(b"\x89PNG\r\n")
    result = run(tmp_path, files)
    assert "![](GUID-9F1B-low.png)" in result.body("getting-started.md")


# -- identity and slugs (§5.2.2) ------------------------------------------------


def test_a_republished_duplicate_becomes_one_page_at_two_toc_positions(tmp_path: Path) -> None:
    """The `_unique_N` collapse, and the filename trap with it.

    `GUID-AAA1_unique_1` lives in `GUID-AAA11.html` -- the counter lands on the
    *identifier* and the filename merely gains a bare digit. Pairing on the
    filename puts both halves in the originals map, where the second silently
    overwrites the first and the collapse never happens.
    """
    result = run(tmp_path, {
        "html/GUID-AAA1.html": topic("GUID-AAA1", "Getting Started"),
        "html/GUID-AAA11.html": topic("GUID-AAA11", "Getting Started",
                                      identifier="GUID-AAA1_unique_1"),
        **{f"html/{k}": v for k, v in toc(
            node("GUID-AAA1", "Getting Started")
            + node("GUID-AAA11", "Getting Started (again)")).items()},
    })
    assert result.names() == ["getting-started.md"]
    assert result.unit.skipped["republished-duplicate"] == 1
    # Two positions, one file -- which is the point of the collapse.
    assert [str(n.document) for n in result.unit.nav] == ["getting-started.md"] * 2


def test_a_link_into_a_duplicate_lands_on_the_original_with_its_anchor(tmp_path: Path) -> None:
    """The duplicate's ids carry `_unique_1` and the file that gets written is the
    original's, whose do not -- so the bookmark is de-uniqued along with the target."""
    result = run(tmp_path, {
        "html/GUID-AAA1.html": topic("GUID-AAA1", "Getting Started",
            '<p>See <a href="GUID-BBB21.html#GUID-BBB2_unique_1__STEP_ONE">step one</a>.</p>'),
        "html/GUID-BBB2.html": topic("GUID-BBB2", "Installing",
            '<p id="GUID-BBB2__STEP_ONE">Unpack.</p>'),
        "html/GUID-BBB21.html": topic("GUID-BBB21", "Installing",
            '<p id="GUID-BBB2_unique_1__STEP_ONE">Unpack.</p>',
            identifier="GUID-BBB2_unique_1"),
        **{f"html/{k}": v for k, v in toc(node("GUID-AAA1", "Getting Started")).items()},
    })
    assert "[step one](installing.md#GUID-BBB2__STEP_ONE)" in result.body("getting-started.md")
    assert '<a id="GUID-BBB2__STEP_ONE"></a>' in result.body("installing.md")


def test_colliding_titles_break_by_guid_and_not_by_iteration_order(tmp_path: Path) -> None:
    """A title collision is a property of the doc-set, not of the corpus -- 6 of 30
    in one re-sample and 15 of 22 in another -- so every doc-set is treated as
    colliding. The tie-break is the GUID so that two runs agree, including across
    machines whose `pathlib` sorts case differently."""
    result = run(tmp_path, {
        "html/GUID-ZZZ9.html": topic("GUID-ZZZ9", "Overview"),
        "html/GUID-AAA1.html": topic("GUID-AAA1", "Overview"),
        **{f"html/{k}": v for k, v in toc(node("GUID-AAA1", "Overview")).items()},
    })
    assert result.names() == ["overview-2.md", "overview.md"]
    assert str(result.document("overview.md").source.name) == "GUID-AAA1.html"


def test_the_topic_and_not_the_toc_is_authoritative_for_a_title(tmp_path: Path) -> None:
    """`h1` equals `DC.Title` in 18,351 of 18,542, while the two TOC files disagree
    with each other on 4% of shared entries. So the slug and the heading come from
    the topic; the TOC label is kept separately, as the nav label."""
    result = run(tmp_path, {
        "html/GUID-AAA1.html": topic("GUID-AAA1", "Installing the Server"),
        **{f"html/{k}": v for k, v in toc(node("GUID-AAA1", "Install")).items()},
    })
    document = result.document("installing-the-server.md")
    assert document.title == "Installing the Server"
    assert result.unit.nav[0].label == "Install"


def test_dc_relation_is_related_links_and_builds_no_hierarchy(tmp_path: Path) -> None:
    """The tempting wrong answer. 42% of topics sit in a mutual `DC.Relation` pair
    and every doc-set tested contains a cycle, because it is DITA's *related-links*
    relation and not a parent pointer. Structure comes from the TOC alone."""
    result = run(tmp_path, {
        "html/GUID-AAA1.html": topic("GUID-AAA1", "Getting Started", relation="GUID-BBB2.html"),
        "html/GUID-BBB2.html": topic("GUID-BBB2", "Installing", relation="GUID-AAA1.html"),
        **{f"html/{k}": v for k, v in toc(
            node("GUID-AAA1", "Getting Started", node("GUID-BBB2", "Installing"))).items()},
    })
    assert [n.label for n in result.unit.nav] == ["Getting Started"]
    assert [n.label for n in result.unit.nav[0].children] == ["Installing"]


# -- navigation (§5.2.3) --------------------------------------------------------


def test_the_toc_is_a_forest_and_no_landing_page_is_synthesized(tmp_path: Path) -> None:
    """23 of 23 sampled doc-sets have 2 to 10 top-level entries and never one, and
    `index.html` redirects to the metadata homepage rather than to a topic. So
    there is nothing to hoist and Phase 6 synthesizes the version root."""
    result = run(tmp_path, {
        "html/GUID-AAA1.html": topic("GUID-AAA1", "Getting Started"),
        "html/GUID-BBB2.html": topic("GUID-BBB2", "Installing"),
        **{f"html/{k}": v for k, v in toc(
            node("GUID-AAA1", "Getting Started") + node("GUID-BBB2", "Installing")).items()},
    })
    assert [n.label for n in result.unit.nav] == ["Getting Started", "Installing"]
    assert result.unit.landing is None


def test_the_crawler_is_a_fallback_and_never_a_supplement(tmp_path: Path) -> None:
    """Where both files exist they disagree on 86 of 2,409 shared entries and the
    crawler is the stale one, so it is read only when the primary is absent."""
    entries = node("GUID-AAA1", "From the crawler")
    result = run(tmp_path, {
        "html/GUID-AAA1.html": topic("GUID-AAA1", "Getting Started"),
        **{f"html/{k}": v for k, v in toc(entries, name="toc_crawler.html").items()},
    })
    assert [n.label for n in result.unit.nav] == ["From the crawler"]


def test_topics_in_no_toc_entry_are_filed_and_counted(tmp_path: Path) -> None:
    """Coverage is 97% on average and complete in 2 of 314. A 3% orphan rate is
    normal here and must not read as a failure -- and must not be a silence."""
    result = run(tmp_path, {
        "html/GUID-AAA1.html": topic("GUID-AAA1", "Getting Started"),
        "html/GUID-BBB2.html": topic("GUID-BBB2", "Installing"),
        **{f"html/{k}": v for k, v in toc(node("GUID-AAA1", "Getting Started")).items()},
    })
    assert [n.label for n in result.unit.nav] == ["Getting Started", "Unfiled"]
    assert [n.label for n in result.unit.nav[-1].children] == ["Installing"]
    assert result.codes()["TOC_ORPHAN"] == 1


def test_a_node_with_no_page_and_no_children_is_dropped_and_counted(tmp_path: Path) -> None:
    result = run(tmp_path, {
        "html/GUID-AAA1.html": topic("GUID-AAA1", "Getting Started"),
        **{f"html/{k}": v for k, v in toc(
            node("GUID-AAA1", "Getting Started") + node("GUID-GONE", "Missing")).items()},
    })
    assert [n.label for n in result.unit.nav] == ["Getting Started"]
    assert result.codes()["NAV_NODE_DROPPED"] == 1


def test_a_container_node_does_not_borrow_its_child_s_target(tmp_path: Path) -> None:
    """A recursive `find` inside an `<li>` gives a label-only section the first
    page beneath it, which reads as a working link and points a section at one of
    its own topics."""
    entries = (
        '<li id="toc-section"><span>Reference</span>'
        f"<ul>{node('GUID-AAA1', 'Getting Started')}</ul></li>"
    )
    result = run(tmp_path, {
        "html/GUID-AAA1.html": topic("GUID-AAA1", "Getting Started"),
        **{f"html/{k}": v for k, v in toc(entries).items()},
    })
    assert result.unit.nav[0].label == "Reference"
    assert result.unit.nav[0].document is None
    assert [n.label for n in result.unit.nav[0].children] == ["Getting Started"]


def test_a_missing_toc_file_leaves_every_topic_unfiled(tmp_path: Path) -> None:
    """39 doc-sets ship neither file. Nothing is invented; everything is reported."""
    result = run(tmp_path, {"html/GUID-AAA1.html": topic("GUID-AAA1", "Getting Started")})
    assert result.names() == ["getting-started.md"]
    assert [n.label for n in result.unit.nav] == ["Unfiled"]
    assert result.codes()["TOC_ORPHAN"] == 1


def test_read_toc_never_raises_on_a_file_it_cannot_use(tmp_path: Path) -> None:
    assert read_toc(tmp_path / "absent.html") == []
    assert read_toc(build(tmp_path, {"t.html": "<html><body><p>No list.</p></body></html>"}) / "t.html") == []


# -- the tail and the homepage (§5.2.7) -----------------------------------------


def test_support_and_legal_are_matched_on_the_label_because_the_path_is_a_guid(
    tmp_path: Path,
) -> None:
    """A DITA filename carries no words at all, so unlike Flare the label is the
    only evidence -- and the brand is not in the test, because it is `TIBCO` in
    565 Flare roots, `ibi` in 49 and `Spotfire` in 45."""
    result = run(tmp_path, {
        "html/GUID-AAA1.html": topic("GUID-AAA1", "Getting Started"),
        "html/GUID-BBB2.html": topic("GUID-BBB2", "Documentation and Support"),
        "html/GUID-CCC3.html": topic("GUID-CCC3", "Legal and Third-Party Notices"),
        **{f"html/{k}": v for k, v in toc(
            node("GUID-AAA1", "Getting Started")
            + node("GUID-BBB2", "Spotfire Documentation and Support Services")
            + node("GUID-CCC3", "Legal and Third-Party Notices")).items()},
    })
    assert str(result.unit.support) == "documentation-and-support.md"
    assert str(result.unit.legal) == "legal-and-third-party-notices.md"


def test_a_missing_tail_page_is_reported_and_never_synthesized(tmp_path: Path) -> None:
    result = run(tmp_path, {
        "html/GUID-AAA1.html": topic("GUID-AAA1", "Getting Started"),
        **{f"html/{k}": v for k, v in toc(node("GUID-AAA1", "Getting Started")).items()},
    })
    assert result.unit.support is None and result.unit.legal is None
    assert result.codes()["TAIL_PAGE_MISSING"] == 2


def test_the_homepage_is_metadata_and_not_a_topic(tmp_path: Path) -> None:
    """All three keys are present in 314 of 314 doc-sets that ship one. They do not
    become `metadata.yml`, whose keys AEM fixed as `csg-*`; Phase 6 reads them as a
    cross-check against the catalog."""
    result = run(tmp_path, {
        "html/GUID-AAA1.html": topic("GUID-AAA1", "Getting Started"),
        **{f"html/{k}": v for k, v in homepage().items()},
        **{f"html/{k}": v for k, v in toc(node("GUID-AAA1", "Getting Started")).items()},
    })
    assert result.names() == ["getting-started.md"]
    assert result.unit.skipped["publication-homepage"] == 1
    assert result.unit.metadata == {
        "publication-title": "Spotfire Server",
        "release-version": "14.2.0",
        "release-date": "March 2026",
    }


def test_a_doc_set_with_no_homepage_reports_blank_and_not_zero(tmp_path: Path) -> None:
    """39 doc-sets ship none. Invariant 11: an unmeasured value is blank."""
    result = run(tmp_path, {
        "html/GUID-AAA1.html": topic("GUID-AAA1", "Getting Started"),
        **{f"html/{k}": v for k, v in toc(node("GUID-AAA1", "Getting Started")).items()},
    })
    assert result.unit.metadata == {}


# -- several doc-sets in one version (§5.2.1) -----------------------------------


def test_each_doc_set_converts_into_its_own_subtree(tmp_path: Path) -> None:
    """23 of 319 versions ship several, and each is its own unit of work."""
    result = run(tmp_path, {
        "html/GUID-AAA1.html": topic("GUID-AAA1", "Getting Started"),
        **{f"html/{k}": v for k, v in toc(node("GUID-AAA1", "Getting Started")).items()},
        "html_v3/GUID-BBB2.html": topic("GUID-BBB2", "Installing"),
        **{f"html_v3/{k}": v for k, v in toc(node("GUID-BBB2", "Installing")).items()},
    })
    assert sorted(unit.name for unit in result.units) == ["html", "html_v3"]
    assert result.names(result.units[0]) == ["getting-started.md"]
    assert result.names(result.units[1]) == ["installing.md"]
