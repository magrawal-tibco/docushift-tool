"""Unit tests for the engine-neutral transforms (design.md §6.4, §9.3-§9.5).

Everything here is a pure function or a per-unit object over a directory: no
catalog, no engine, no `state.db`. That is the point of the seam -- the rules
these tests pin are the ones all four engines share, and each one of them is a
corpus measurement rather than a convention.
"""

from pathlib import Path, PurePosixPath

import pytest
from bs4 import BeautifulSoup

from docushift.engines.csh import CshEntry, CshFormat, CshSource, CshStatus
from docushift.models import SourceEngine
from docushift.transforms import callouts, code, csh, links, markdown, tables
from docushift.transforms.assets import AssetCopier, AssetOutcome
from tests.unit.test_extractor import build_tree, page

# -- links (§6.4 step 3, points 1-3) ------------------------------------------


@pytest.mark.parametrize(
    ("raw", "kind"),
    [
        ("images/a.png", links.ReferenceKind.RELATIVE),
        ("https://docs.example/a", links.ReferenceKind.ABSOLUTE),
        ("mailto:support@example.com", links.ReferenceKind.ABSOLUTE),
        ("data:image/png;base64,AAA", links.ReferenceKind.ABSOLUTE),
        ("//cdn.example/a.js", links.ReferenceKind.ABSOLUTE),
        ("/shared/a.png", links.ReferenceKind.ROOTED),
        ("#section", links.ReferenceKind.FRAGMENT),
        ("   ", links.ReferenceKind.EMPTY),
    ],
)
def test_every_reference_lands_in_exactly_one_kind(raw: str, kind) -> None:
    assert links.classify(raw).kind is kind


def test_normalization_strips_the_fragment_decodes_and_fixes_slashes() -> None:
    """1,872 WebWorks references are 'missing' without this: 1,224 encoded, 648 `\\`."""
    reference = links.classify(r"..\Images\My%20Image.png?v=2#top")

    assert reference.path == "../Images/My Image.png"
    assert reference.fragment == "top"
    assert reference.query == "v=2"


def test_a_percent_encoded_hash_in_a_filename_is_not_the_fragment_separator() -> None:
    """The split happens before the decode, which is the whole reason for the order."""
    assert links.classify("a%23b.png").path == "a#b.png"


def test_a_climbing_reference_survives_as_a_leading_dotdot() -> None:
    """`Path.resolve()` would consult the disk and erase the escape (§6.4 step 3.5)."""
    resolved = links.resolve(PurePosixPath("Content"), "../../pdf/guide.pdf")

    assert str(resolved) == "../pdf/guide.pdf"
    assert links.escapes(resolved)


def test_a_literal_percent_is_escaped_before_anything_else() -> None:
    """104 corpus filenames already contain a `%`; the wrong order gives `%2520`."""
    assert links.encode("img/100%20done.png") == "img/100%2520done.png"
    assert links.encode("img/a b.png") == "img/a%20b.png"


def test_a_same_directory_sibling_is_emitted_bare() -> None:
    source = PurePosixPath("Content/topics/install.md")

    assert links.relative_to(source, PurePosixPath("Content/topics/config.md")) == "config.md"
    assert links.relative_to(source, PurePosixPath("Content/img/a.png")) == "../img/a.png"


def test_only_topic_suffixes_become_markdown() -> None:
    assert str(links.to_markdown("a/b.HTM")) == "a/b.md"
    assert str(links.to_markdown("a/b.png")) == "a/b.png"


# -- callouts -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("label", "alert"),
    [
        ("Note", callouts.Alert.NOTE),
        ("tip", callouts.Alert.TIP),
        ("Danger", callouts.Alert.CAUTION),
        ("attention", callouts.Alert.IMPORTANT),
        ("Warning:", callouts.Alert.WARNING),
    ],
)
def test_source_labels_map_to_the_five_github_alerts(label: str, alert) -> None:
    assert callouts.alert_for(label) is alert


def test_an_unmapped_label_is_not_silently_a_note() -> None:
    """The caller reports it; the vocabulary never grows a guess."""
    assert callouts.alert_for("Editorial Comment") is None


def test_every_body_line_including_blanks_is_quoted() -> None:
    rendered = callouts.render(callouts.Alert.WARNING, "first\n\nsecond")

    assert rendered == "> [!WARNING]\n> first\n>\n> second"


# -- code fences --------------------------------------------------------------


def test_a_fence_outgrows_the_longest_backtick_run_it_contains() -> None:
    """API documentation quotes Markdown at itself; a 3-backtick fence ends early."""
    assert code.fence("a ``` b").startswith("````\n")
    assert code.fence("plain").startswith("```\n")


def test_a_fence_is_emitted_bare_unless_a_language_was_declared() -> None:
    assert code.fence("x") == "```\nx\n```"
    assert code.fence("x", "xml") == "```xml\nx\n```"


def test_inline_code_pads_when_the_body_touches_a_backtick() -> None:
    assert code.inline("`") == "`` ` ``"
    assert code.inline("a  b") == "`a b`"


# -- tables -------------------------------------------------------------------


def soup(html: str):
    return BeautifulSoup(html, "html.parser").find("table")


def test_a_spanned_table_is_not_gfm_safe() -> None:
    """GFM has no rowspan; converting anyway reads as a plausible, wrong table."""
    model = tables.read(soup("<table><tr><td colspan='2'>a</td></tr></table>"))

    assert tables.unsafe_reason(model) is tables.Unsafe.SPAN


def test_a_nested_tables_rows_belong_to_the_nested_table() -> None:
    """Counting them here would make every parent look ragged."""
    model = tables.read(soup(
        "<table><tr><td><table><tr><td>x</td><td>y</td></tr></table></td></tr></table>"
    ))

    assert len(model.rows) == 1
    assert tables.unsafe_reason(model) is tables.Unsafe.NESTED


def test_a_cell_wrapped_in_one_paragraph_is_safe_and_two_are_not() -> None:
    single = tables.read(soup("<table><tr><td><p>a</p></td><td><p>b</p></td></tr></table>"))
    double = tables.read(soup("<table><tr><td><p>a</p><p>b</p></td><td>c</td></tr></table>"))

    assert tables.is_gfm_safe(single)
    assert tables.unsafe_reason(double) is tables.Unsafe.MULTI_BLOCK


def test_a_th_first_row_is_the_header_without_being_told() -> None:
    model = tables.read(soup("<table><tr><th>a</th><th>b</th></tr><tr><td>1</td><td>2</td></tr></table>"))

    assert model.header_row == 0
    rendered = tables.to_pipe(model, lambda cell: cell.get_text())
    assert rendered.splitlines()[0] == "| a | b |"


def test_a_headerless_table_gets_an_empty_header_not_a_promoted_row() -> None:
    """Promoting a data row relabels the column with a value."""
    model = tables.read(soup("<table><tr><td>1</td><td>2</td></tr></table>"))

    lines = tables.to_pipe(model, lambda cell: cell.get_text()).splitlines()
    assert lines == ["|  |  |", "| --- | --- |", "| 1 | 2 |"]


def test_a_pipe_and_a_newline_survive_a_cell() -> None:
    assert tables.escape("a | b\nc") == r"a \| b c"


# -- the markdown walk (§5.1, invariant 13) -----------------------------------


def render(html: str, renderer: markdown.Renderer | None = None) -> str:
    return (renderer or markdown.Renderer()).render(markdown.parse(html).body)


def test_a_cdata_section_survives_the_parser_as_its_own_text() -> None:
    """`lxml` deletes `<![CDATA[...]]>` outright -- CDATA is not a thing in HTML.

    130 files of a 3,411-file sample carry 300 sections and 170 of them hold only
    the space between a word and the `<span>` after it, so the parser's answer is
    "ensure that thelibjvm library".
    """
    assert render("<p>ensure that the<![CDATA[ ]]><span>libjvm</span> library</p>") == (
        "ensure that the libjvm library"
    )


def test_markup_inside_a_cdata_section_stays_text() -> None:
    """None of the 300 sampled sections hold markup, and an unsampled one is text.

    Only the `<` is escaped: a bare `>` mid-line starts nothing, and one that leads
    a line is `escape_leading`'s to catch.
    """
    assert render("<p><![CDATA[<b>literal</b>]]></p>") == r"\<b>literal\</b>"


def test_a_comment_is_not_prose() -> None:
    """`Comment` is a `NavigableString` subclass, so the obvious isinstance is true.

    Corpus topics carry commented-out markup beside their content; emitting it is
    the difference between a paragraph and a paragraph followed by a stylesheet.
    """
    assert markdown.is_text(BeautifulSoup("<p>x</p>", "html.parser").p.string)
    assert render("<p>kept<!-- .style { color: red } --></p>") == "kept"


def test_a_passthrough_table_gets_its_references_resolved() -> None:
    """Invariant 13 does not stop at the edge of a pipe table.

    43% of Flare's tables cannot be a GFM one, and their HTML would otherwise ship
    `src="images/x.png"` -- a path in the *source* layout -- in the one branch
    where no hook was consulted.
    """

    class Resolving(markdown.Renderer):
        def image(self, tag):
            return "/assets/x.png"

        def link(self, tag):
            return None if tag.get("href") == "gone.htm" else "/docs/there.md"

    rendered = render(
        "<table><tr><td colspan='2'><img src='images/x.png'/>"
        "<a href='there.htm'>here</a><a href='gone.htm'>orphan</a></td></tr></table>",
        Resolving(),
    )

    assert 'src="/assets/x.png"' in rendered
    assert 'href="/docs/there.md"' in rendered
    # The text was authored and stays; only the claim that it leads somewhere goes.
    assert "gone.htm" not in rendered
    assert ">orphan<" in rendered


# -- assets (§6.4 steps 3-7, invariant 13) ------------------------------------


def flare_unit(tmp_path: Path) -> Path:
    """A Flare output root with one of each of the five step-3 branches in it."""
    return build_tree(tmp_path / "tree", {
        "guide/Data/HelpSystem.xml": "<x/>",
        "guide/Content/topic.htm": page(),
        "guide/Content/images/shot.png": "png",
        "guide/Content/images/Cased.PNG": "png",
        "guide/Skins/Default/logo.gif": "gif",
        "guide/Content/images/never-referenced.png": "orphan",
        "pdf/guide.pdf": "pdf",
    }) / "guide"


def copier_for(tmp_path: Path) -> tuple[AssetCopier, Path]:
    root = flare_unit(tmp_path)
    return AssetCopier(root, SourceEngine.FLARE, tmp_path / "out" / "guide"), root


def test_a_resolved_reference_produces_a_link_and_a_copy_from_one_call(tmp_path: Path) -> None:
    """Invariant 13: the copy set *is* what the Markdown references."""
    copier, root = copier_for(tmp_path)

    resolution = copier.resolve(
        root / "Content" / "topic.htm", PurePosixPath("Content/topic.md"), "images/shot.png"
    )

    assert resolution.outcome is AssetOutcome.RESOLVED
    assert resolution.url == "images/shot.png"
    assert resolution.target == PurePosixPath("Content/images/shot.png")
    assert copier.copy() == 1
    assert (tmp_path / "out" / "guide" / "Content" / "images" / "shot.png").is_file()


def test_a_dangling_reference_emits_neither_link_nor_copy_and_is_counted(tmp_path: Path) -> None:
    copier, root = copier_for(tmp_path)

    resolution = copier.resolve(
        root / "Content" / "topic.htm", PurePosixPath("Content/topic.md"), "images/gone.png"
    )

    assert resolution.outcome is AssetOutcome.DANGLING
    assert not resolution.emits
    assert copier.copy_set == {}
    # Grouped by top segment, not just totalled: 2,706 of Flare's 2,905 come
    # from one tree that is broken in its own source.
    assert copier.counts.dangling_by_segment == {"Content": 1}


def test_chrome_is_dropped_before_it_can_be_reported_missing(tmp_path: Path) -> None:
    """Skin is checked first; otherwise 76.2% of WebWorks goes in the failure column."""
    copier, root = copier_for(tmp_path)

    present = copier.resolve(
        root / "Content" / "topic.htm", PurePosixPath("Content/topic.md"), "../Skins/Default/logo.gif"
    )
    absent = copier.resolve(
        root / "Content" / "topic.htm", PurePosixPath("Content/topic.md"), "../Skins/Default/gone.gif"
    )

    assert present.outcome is AssetOutcome.SKIN
    assert absent.outcome is AssetOutcome.SKIN
    assert copier.counts.dangling == 0
    assert copier.counts.skin == 2


def test_an_escaping_reference_is_handed_on_with_its_resolved_source_path(tmp_path: Path) -> None:
    """§10.7: Stage 7 routes it; this stage does not emit it. 279 in the Flare sample."""
    copier, root = copier_for(tmp_path)

    resolution = copier.resolve(
        root / "Content" / "topic.htm", PurePosixPath("Content/topic.md"), "../../pdf/guide.pdf"
    )

    assert resolution.outcome is AssetOutcome.ESCAPED
    assert not resolution.emits
    assert copier.escaped[0][0] == root.parent / "pdf" / "guide.pdf"


def test_an_external_reference_is_emitted_unchanged_and_never_copied(tmp_path: Path) -> None:
    copier, root = copier_for(tmp_path)

    resolution = copier.resolve(
        root / "Content" / "topic.htm", PurePosixPath("Content/topic.md"), "https://docs.example/a.png"
    )

    assert resolution.outcome is AssetOutcome.EXTERNAL
    assert resolution.url == "https://docs.example/a.png"
    assert copier.copy_set == {}


def test_case_is_checked_and_not_corrected(tmp_path: Path) -> None:
    """Works on this Windows cache, 404s after publishing. 14 corpus-wide."""
    copier, root = copier_for(tmp_path)

    resolution = copier.resolve(
        root / "Content" / "topic.htm", PurePosixPath("Content/topic.md"), "images/cased.png"
    )

    assert resolution.outcome is AssetOutcome.RESOLVED
    assert resolution.case_mismatch
    # Not corrected: the reference's own spelling is what gets emitted.
    assert resolution.url == "images/cased.png"


def test_assets_keep_their_source_relative_path(tmp_path: Path) -> None:
    """Flattening collides 5,328 times inside one Flare root."""
    copier, root = copier_for(tmp_path)

    copier.resolve(root / "Content" / "topic.htm", PurePosixPath("Content/topic.md"), "images/shot.png")

    assert list(copier.copy_set) == [PurePosixPath("Content/images/shot.png")]


def test_orphans_are_reported_and_never_copied(tmp_path: Path) -> None:
    """54.6% of Flare's images. Chrome and topics are not orphans."""
    copier, root = copier_for(tmp_path)
    copier.resolve(root / "Content" / "topic.htm", PurePosixPath("Content/topic.md"), "images/shot.png")

    orphans = copier.orphans()

    names = [str(path) for path, _size in orphans]
    assert names == ["Content/images/Cased.PNG", "Content/images/never-referenced.png"]
    assert copier.copy() == 1


def test_one_asset_referenced_twice_is_copied_once(tmp_path: Path) -> None:
    copier, root = copier_for(tmp_path)

    copier.resolve(root / "Content" / "topic.htm", PurePosixPath("Content/topic.md"), "images/shot.png")
    copier.resolve(root / "Content" / "other.htm", PurePosixPath("Content/other.md"), "images/shot.png")

    assert len(copier.copy_set) == 1
    assert copier.counts.resolved == 2


# -- CSH (§9.3-§9.5) ----------------------------------------------------------


def source(doc_set: str, *entries: tuple[str, str, str], status=CshStatus.OK) -> CshSource:
    return CshSource(
        path=Path(doc_set) / "Data" / "Alias.xml",
        fmt=CshFormat.FLARE_ALIAS,
        status=status,
        entries=[CshEntry(identifier, link, anchor) for identifier, link, anchor in entries],
        doc_set=doc_set,
    )


def test_an_identifier_resolves_inside_its_own_doc_set_first() -> None:
    sources = [source("main", ("install", "topics/Install.htm", ""))]
    output = {"main/topics/Install.htm": "topics/Install.md"}

    resolved = csh.resolve(sources, output)

    assert resolved.entries == {"install": "topics/Install.md"}
    assert resolved.rescued == 0
    assert resolved.unresolved == []


def test_the_version_wide_fallback_rescues_a_relnotes_alias_that_resolves_at_zero() -> None:
    """22% of Flare links dangle in their own doc-set; 205 in one BW release-notes file."""
    sources = [
        source("main", ("a", "topics/A.htm", ""), ("b", "topics/B.htm", "")),
        source("relnotes", ("install", "topics/Install.htm", "")),
    ]
    output = {
        "main/topics/A.htm": "topics/A.md",
        "main/topics/B.htm": "topics/B.md",
        "main/topics/Install.htm": "topics/Install.md",
    }

    resolved = csh.resolve(sources, output)

    assert resolved.entries["install"] == "topics/Install.md"
    assert resolved.rescued == 1


def test_the_anchor_is_appended_to_the_path_under_the_flat_schema() -> None:
    sources = [source("main", ("palette", "topics/Start.htm", "adb.palette"))]

    resolved = csh.resolve(sources, {"main/topics/Start.htm": "topics/Start.md"})

    assert resolved.entries == {"palette": "topics/Start.md#adb.palette"}


def test_case_only_identifier_collisions_stay_two_entries() -> None:
    """`GatewayInstances` and `gatewayInstances` are two live targets in BC 7.4/7.5."""
    sources = [source("main", ("GatewayInstances", "a.htm", ""), ("gatewayInstances", "b.htm", ""))]

    resolved = csh.resolve(sources, {"main/a.htm": "a.md", "main/b.htm": "b.md"})

    assert resolved.entries == {"GatewayInstances": "a.md", "gatewayInstances": "b.md"}


def test_an_ambiguous_identifier_takes_the_doc_set_with_the_most_entries() -> None:
    """`also` has nowhere to go in a flat map, so the winner has to be deterministic."""
    sources = [
        source("zz-main", ("shared", "a.htm", ""), ("other", "b.htm", "")),
        source("aa-side", ("shared", "a.htm", "")),
    ]
    output = {
        "zz-main/a.htm": "zz-main/a.md",
        "zz-main/b.htm": "zz-main/b.md",
        "aa-side/a.htm": "aa-side/a.md",
    }

    resolved = csh.resolve(sources, output)

    # Two entries beats one, so the alphabetically earlier doc-set loses -- which
    # is the point: the main help output wins over a sidecar, not the first name.
    assert resolved.entries["shared"] == "zz-main/a.md"
    assert [entry.identifier for entry in resolved.ambiguous] == ["shared"]
    assert resolved.ambiguous[0].dropped == ("aa-side/a.md",)


def test_the_same_target_from_two_doc_sets_is_not_a_conflict() -> None:
    sources = [source("main", ("x", "a.htm", "")), source("side", ("x", "../main/a.htm", ""))]

    resolved = csh.resolve(sources, {"main/a.htm": "a.md"})

    assert resolved.entries == {"x": "a.md"}
    assert resolved.ambiguous == []


def test_an_identifier_matching_no_produced_topic_is_kept_not_dropped() -> None:
    """Invariant 10: dropping it makes a broken Help button unfindable."""
    sources = [source("main", ("gone", "topics/Gone.htm", ""))]

    resolved = csh.resolve(sources, {})

    assert resolved.entries == {}
    assert resolved.unresolved[0].identifier == "gone"
    assert resolved.tallies["main"] == (1, 0)


def test_an_unreadable_source_is_counted_and_skipped() -> None:
    sources = [source("main", ("x", "a.htm", ""), status=CshStatus.UNPARSEABLE)]

    resolved = csh.resolve(sources, {"main/a.htm": "a.md"})

    assert resolved.empty
    assert resolved.unusable == {"unparseable": 1}


def test_a_digit_only_identifier_survives_as_a_string() -> None:
    """834 of 11,054 Flare names are digit-only; YAML 1.1 turns `1234` into an int."""
    rendered = csh.render({"1234": "a.md", "6.2": "b.md"})

    assert rendered == '"1234": "a.md"\n"6.2": "b.md"\n'


def test_a_version_with_no_resolved_identifier_gets_no_file(tmp_path: Path) -> None:
    """An empty map file is indistinguishable from a failed run (§9.4)."""
    target = tmp_path / "csh.yml"
    target.write_text("stale", encoding="utf-8")

    assert csh.write(target, {}) is False
    assert not target.exists()


def test_frontmatter_is_always_a_list_of_quoted_strings() -> None:
    assert csh.frontmatter_value(["only"]) == '["only"]'
    assert csh.frontmatter_value(["a", "1234"]) == '["a", "1234"]'


def test_identifiers_are_owned_by_source_path_before_conversion_runs() -> None:
    """§9.5: they reach the topic's first and only write."""
    sources = [source("main", ("a", "topics/T.htm#x", ""), ("b", "topics/T.htm", ""))]

    owned = csh.identifiers_by_source(sources)

    assert owned == {"main/topics/T.htm": ["a", "b"]}
