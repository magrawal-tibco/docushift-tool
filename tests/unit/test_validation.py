"""Unit tests for Stage 8 -- the linter over a published tree (`validate`).

Every test here is a fixture directory, because that is the shape the checkers
were written for: `links.check`, `artifacts.check` and `csh.check` take a folder
and return findings, and hold no catalog, no store and no findings run. Nothing
below constructs a `CatalogManager`, which is §7.1's boundary asserted by
construction rather than by a comment.

The cases that look arbitrary are the measured ones. A reference on a four-space
indented line is checked and one inside a fence is not (953 references and 0
references, respectively, in the sample tree of 2026-09-16); a link whose first
raw segment names a published tree resolves against the target root (121 of that
tree's 123 "broken" links); a missing anchor is a warning and a missing file is an
error (1,626 against 11.6%). Each of those numbers is in `planning.md` Phase 7b
and in the module docstring of the thing it decided.
"""

from pathlib import Path

import pytest
from click.testing import CliRunner

from docushift.cli import main
from docushift.reporting.findings import REGISTRY, Severity
from docushift.validation import Validator, walk
from docushift.validation import csh as csh_mod
from docushift.validation import references as refs
from docushift.validation.links import FolderIndex, LinkContext, check, check_external
from docushift.validation.tree import VersionFolder

TREE = "en-us-tib-general-userdocs"
RESOURCES = "en-us-tib-general-userdocs-resources"
SLUG = "widget"

METADATA = 'csg-version: "1.0.0"\n'
PRODUCT_METADATA = 'csg-product: "widget"\n'


# -- fixtures -------------------------------------------------------------------


def publish(
    target: Path,
    files: dict[str, str] | None = None,
    *,
    tree: str = TREE,
    slug: str = SLUG,
    doc_class: str = "online-help",
    segment: str = "1-0-0",
    metadata: str | None = METADATA,
    product_metadata: str | None = PRODUCT_METADATA,
) -> Path:
    """One published version folder on disk, laid out the way `sync` lays it out."""
    product = target / tree / "en-us" / slug
    folder = product / doc_class / segment if segment else product / doc_class
    folder.mkdir(parents=True, exist_ok=True)
    if metadata is not None:
        (folder / "metadata.yml").write_text(metadata, encoding="utf-8")
    if product_metadata is not None and not tree.endswith("-resources"):
        (product / "metadata.yml").write_text(product_metadata, encoding="utf-8")
    for name, body in (files or {}).items():
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return folder


def only(target: Path) -> VersionFolder:
    """The one version folder in a single-product fixture tree."""
    found = [folder for entry in walk(target) for folder in entry.versions]
    assert len(found) == 1, found
    return found[0]


def links_of(target: Path, folder: VersionFolder | None = None):
    folder = folder if folder is not None else only(target)
    context = LinkContext(target=target, trees={p.name for p in target.iterdir()})
    return check(folder, context), context


def codes(findings) -> list[str]:
    return [finding.code for finding in findings]


# -- the reader: references.py ---------------------------------------------------


def test_a_reference_on_an_indented_line_is_checked_and_one_in_a_fence_is_not() -> None:
    """The extractor's deliberate non-conformance, both halves, one fixture.

    Four-space indentation in converted help is list continuation, not a code
    block: honouring CommonMark here would silently stop checking 953 real
    references in the sample. A fence is masked, and that direction found 0
    references in 79,497 lines -- kept as insurance against an engine that starts
    emitting sample HTML.
    """
    text = (
        "- item\n"
        "\n"
        "    ![shot](media/indented.png)\n"
        "\n"
        "```html\n"
        '<a href="media/fenced.png">no</a>\n'
        "```\n"
        "\n"
        "Inline `[not](media/span.png)` too.\n"
    )

    found = {reference.raw for reference in refs.references(text)}

    assert found == {"media/indented.png"}


def test_frontmatter_is_masked_so_a_yaml_value_is_not_read_as_a_link() -> None:
    text = '---\ntitle: "[a](b.md)"\n---\n\n[real](c.md)\n'

    assert [r.raw for r in refs.references(text)] == ["c.md"]


def test_html_attributes_spanning_newlines_are_still_found() -> None:
    """`<img>` attributes wrap in converted help; a line-oriented match undercounts."""
    text = '<img\n  alt="a very long description"\n  src="media/wrapped.png" />\n'

    found = refs.references(text)

    assert [(r.raw, r.syntax) for r in found] == [("media/wrapped.png", "html")]


def test_line_numbers_survive_masking() -> None:
    """Masking writes spaces, not deletions, so a finding names the real line."""
    text = "```\nfence\n```\n\n[a](b.md)\n"

    assert [r.line for r in refs.references(text)] == [5]


def test_anchors_come_from_headings_and_from_explicit_html_attributes() -> None:
    """11,887 `id=`/`name=` attributes in the sample: the HTML is load-bearing."""
    text = '# My Heading\n\n<a name="legacyTarget"></a>\n\n## My Heading\n'

    assert refs.anchors(text) == {"my-heading", "my-heading-1", "legacytarget"}


def test_bracket_text_inside_an_html_block_is_not_a_link() -> None:
    """The one `LINK_BROKEN` on the `ems` tree was a printf format string.

    `<p>Pulsar: [%s](%s:%d): %s</p>` is in the source HTML character for
    character, inside a table too irregular for GFM. CommonMark does not parse
    inline Markdown inside an HTML block, so nothing there points anywhere --
    and the `<a href>` beside it still does.
    """
    text = (
        "[real](real.md)\n\n"
        "<table><tr><td>\n"
        "<p>Pulsar: [%s](%s:%d): %s</p>\n"
        '<a href="kept.md">kept</a>\n'
        "</td></tr></table>\n"
    )

    found = refs.references(text)

    assert [(r.raw, r.syntax) for r in found] == [("real.md", "markdown"), ("kept.md", "html")]


def test_an_inline_tag_opening_a_line_starts_no_html_block() -> None:
    """`a`, `b`, `span` are not in CommonMark's type-6 list, and that is the point.

    Masking on any tag would stop checking the links in every paragraph that
    happens to begin with emphasis -- and every anchor target Stage 5 now emits
    ahead of the prose it labels.
    """
    text = '<a id="ID-7B"></a>See [the guide](guide.md).\n'

    assert [r.raw for r in refs.references(text)] == ["guide.md"]
    assert refs.anchors(text) == {"id-7b"}


# -- the walk: tree.py -----------------------------------------------------------


def test_a_part_folder_is_residue_and_is_never_walked(tmp_path: Path) -> None:
    """A failed sync's staging sibling must not become findings a re-run cures."""
    target = tmp_path / "target"
    publish(target)
    residue = target / TREE / "en-us" / SLUG / "online-help" / "1-1-0.part"
    residue.mkdir(parents=True)
    (residue / "broken.md").write_text("[gone](nowhere.md)\n", encoding="utf-8")

    entry = walk(target)[0]

    assert [f.segment for f in entry.versions] == ["1-0-0"]
    assert entry.residue == [residue]


def test_archives_is_one_unit_with_no_version_segment(tmp_path: Path) -> None:
    target = tmp_path / "target"
    publish(target, tree=RESOURCES, doc_class="archives", segment="")

    folder = only(target)

    assert (folder.doc_class, folder.segment) == ("archives", "")
    assert folder.relative.as_posix() == f"{RESOURCES}/en-us/{SLUG}/archives"


def test_a_doc_class_directory_nobody_recognizes_is_skipped(tmp_path: Path) -> None:
    target = tmp_path / "target"
    publish(target)
    (target / TREE / "en-us" / SLUG / "scratch" / "1-0-0").mkdir(parents=True)

    assert [f.doc_class for f in walk(target)[0].versions] == ["online-help"]


@pytest.mark.parametrize("selector", ["1.0.0", "1-0-0"])
def test_the_version_selector_accepts_the_dotted_and_the_dashed_form(
    tmp_path: Path, selector: str
) -> None:
    """The dashed form is on disk and the dotted form is in somebody's hand."""
    target = tmp_path / "target"
    publish(target)
    publish(target, segment="2-0-0")

    found = [f.segment for entry in walk(target, version=selector) for f in entry.versions]

    assert found == ["1-0-0"]


# -- links.py --------------------------------------------------------------------


def test_a_reference_to_a_file_that_is_not_there_is_an_error(tmp_path: Path) -> None:
    target = tmp_path / "target"
    publish(target, {"a.md": "# A\n\n![shot](media/missing.png)\n"})

    report, _ = links_of(target)

    assert codes(report.findings) == ["LINK_BROKEN"]
    assert REGISTRY["LINK_BROKEN"].severity is Severity.ERROR
    assert "media/missing.png is not in this version folder" in report.findings[0].message
    assert report.findings[0].path.endswith("a.md:3")


def test_a_reference_differing_only_in_case_is_broken_and_the_message_names_the_file(
    tmp_path: Path,
) -> None:
    """On Windows this resolves; on the Linux the tree is published to it 404s.

    The defect class the linter exists for, and the one that caught Stage 6
    writing a generated container page over `install/Installation.md`.
    """
    target = tmp_path / "target"
    publish(target, {"a.md": "[b](Topic.md)\n", "topic.md": "# Topic\n"})

    report, _ = links_of(target)

    assert codes(report.findings) == ["LINK_BROKEN"]
    assert "differs only in case from topic.md" in report.findings[0].message


def test_a_reference_climbing_out_of_the_version_folder_is_broken(tmp_path: Path) -> None:
    target = tmp_path / "target"
    publish(target, {"a.md": "[up](../../../etc/passwd)\n"})

    report, _ = links_of(target)

    assert codes(report.findings) == ["LINK_BROKEN"]
    assert "climbs out" in report.findings[0].message


def test_a_host_less_tree_rooted_link_resolves_against_the_target_root(tmp_path: Path) -> None:
    """The highest-value rule in the phase: 121 of the sample's 123 without it.

    With `publish_base_url` empty -- the shipped state -- a rewritten API link is
    a tree-rooted path with no host, which `classify()` rightly calls relative.
    Resolved against the citing page's directory it lands nowhere; resolved
    against the target root it lands on the API tree, and proves it was synced.
    """
    target = tmp_path / "target"
    api = publish(target, tree=RESOURCES, doc_class="api-references", segment="1-0-0")
    (api / "index.html").write_text("<html></html>", encoding="utf-8")
    reference = f"{RESOURCES}/en-us/{SLUG}/api-references/1-0-0/index.html"
    publish(target, {"html/guide.md": f"[api]({reference})\n"})

    report, _ = links_of(target, only_docs(target))

    assert report.findings == []
    assert report.tree_rooted == 1


def test_the_same_link_is_broken_once_the_api_tree_is_moved_aside(tmp_path: Path) -> None:
    """The other direction. A skip and a resolve are indistinguishable when
    everything is present, so the rule is only proven by taking the target away."""
    target = tmp_path / "target"
    api = publish(target, tree=RESOURCES, doc_class="api-references", segment="1-0-0")
    (api / "index.html").write_text("<html></html>", encoding="utf-8")
    reference = f"{RESOURCES}/en-us/{SLUG}/api-references/1-0-0/index.html"
    publish(target, {"html/guide.md": f"[api]({reference})\n"})
    (api / "index.html").unlink()

    report, _ = links_of(target, only_docs(target))

    assert codes(report.findings) == ["LINK_BROKEN"]
    assert "names a published tree this target does not hold" in report.findings[0].message
    assert report.tree_rooted == 1


def only_docs(target: Path) -> VersionFolder:
    """The `online-help` folder of a fixture that also publishes an API tree."""
    found = [
        folder
        for entry in walk(target)
        for folder in entry.versions
        if folder.doc_class == "online-help"
    ]
    assert len(found) == 1, found
    return found[0]


def test_a_missing_anchor_is_a_warning_and_the_page_it_is_on_is_not(tmp_path: Path) -> None:
    """11.6% of the sample's fragments do not resolve. An 11.6% rate cannot gate."""
    target = tmp_path / "target"
    publish(target, {"a.md": "[x](b.md#nope)\n[y](b.md#yes)\n", "b.md": "# Yes\n"})

    report, _ = links_of(target)

    assert codes(report.findings) == ["ANCHOR_MISSING"]
    assert REGISTRY["ANCHOR_MISSING"].severity is Severity.WARNING
    assert (report.fragments, report.anchors_matched) == (2, 1)


def test_a_same_page_fragment_is_checked_against_the_page_it_is_on(tmp_path: Path) -> None:
    target = tmp_path / "target"
    publish(target, {"a.md": "# Top\n\n[here](#top)\n[there](#gone)\n"})

    report, _ = links_of(target)

    assert codes(report.findings) == ["ANCHOR_MISSING"]
    assert (report.fragments, report.anchors_matched) == (2, 1)


def test_percent_encoded_and_backslash_references_decode_before_they_resolve(
    tmp_path: Path,
) -> None:
    """§5.5.6 measured the cost of skipping this: 1,872 WebWorks references
    reported missing that are not. One resolution, two callers."""
    target = tmp_path / "target"
    publish(
        target,
        {
            "a.md": "[a](sub/One%20Two.md)\n[b](sub\\One%20Two.md)\n",
            "sub/One Two.md": "# One Two\n",
        },
    )

    report, _ = links_of(target)

    assert report.findings == []
    assert report.references == 2


def test_absolute_urls_are_counted_collected_and_never_requested(tmp_path: Path) -> None:
    """No network without the flag, asserted as a property rather than promised."""
    target = tmp_path / "target"
    publish(target, {"a.md": "[s](https://example.com/a)\n[t](mailto:x@example.com)\n"})

    report, context = links_of(target)

    assert report.findings == []
    assert report.absolute == 2
    assert context.external == {"https://example.com/a", "mailto:x@example.com"}


def test_the_external_pass_requests_each_url_once_and_skips_non_http_schemes() -> None:
    calls: list[str] = []

    def fetch(url: str) -> bool:
        calls.append(url)
        return url.endswith("/ok")

    findings = check_external({"https://a/ok", "https://a/dead", "mailto:x@y"}, fetch)

    assert calls == ["https://a/dead", "https://a/ok"]
    assert codes(findings) == ["LINK_EXTERNAL_DEAD"]
    assert REGISTRY["LINK_EXTERNAL_DEAD"].severity is Severity.WARNING


# -- artifacts.py ----------------------------------------------------------------


def test_a_version_folder_with_no_metadata_is_an_error(tmp_path: Path) -> None:
    target = tmp_path / "target"
    publish(target, metadata=None)

    findings = artifacts_of(target)

    assert codes(findings) == ["METADATA_INVALID"]
    assert REGISTRY["METADATA_INVALID"].severity is Severity.ERROR


@pytest.mark.parametrize(
    ("body", "detail"),
    [
        ("other: 1\n", "has no csg-version"),
        ('csg-version: ""\n', "csg-version is empty"),
        ("- a list\n", "is not a YAML mapping"),
    ],
)
def test_metadata_field_checks(tmp_path: Path, body: str, detail: str) -> None:
    target = tmp_path / "target"
    publish(target, metadata=body)

    findings = artifacts_of(target)

    assert codes(findings) == ["METADATA_INVALID"]
    assert detail in findings[0].message


def test_an_archives_folder_is_asked_for_the_product_key_not_the_version_key(
    tmp_path: Path,
) -> None:
    """The folder is the product's whole history, not one version of it."""
    target = tmp_path / "target"
    publish(target, tree=RESOURCES, doc_class="archives", segment="", metadata=PRODUCT_METADATA)

    assert artifacts_of(target) == []


def test_an_unparseable_artifact_is_reported_once_and_no_field_check_runs(
    tmp_path: Path,
) -> None:
    """The action is different, and continuing would make every further finding
    about the folder unsound."""
    target = tmp_path / "target"
    publish(target, metadata="csg-version: [unclosed\n")

    findings = artifacts_of(target)

    assert codes(findings) == ["ARTIFACT_UNPARSED"]
    assert REGISTRY["ARTIFACT_UNPARSED"].severity is Severity.ERROR


def test_an_unparseable_toc_is_reported_and_its_paths_are_not_checked(tmp_path: Path) -> None:
    target = tmp_path / "target"
    publish(target, {"toc.yml": "items:\n  - title: [unclosed\n"})

    assert codes(artifacts_of(target)) == ["ARTIFACT_UNPARSED"]


def test_a_toc_path_that_resolves_to_nothing_is_a_link_broken(tmp_path: Path) -> None:
    """A `toc.yml` path is a link. Giving the TOC its own code would mean a
    `report --code LINK_BROKEN` that misses half the broken links."""
    target = tmp_path / "target"
    publish(
        target,
        {
            "toc.yml": 'items:\n  - title: "A"\n    path: "html/a.md"\n'
                       '    children:\n      - title: "B"\n        path: "html/b.md#nope"\n',
            "html/b.md": "# B\n",
        },
    )

    findings = artifacts_of(target)

    assert codes(findings) == ["LINK_BROKEN", "ANCHOR_MISSING"]
    assert "html/a.md is not in this version folder" in findings[0].message


def test_a_toc_path_differing_only_in_case_is_the_defect_that_lost_three_topics(
    tmp_path: Path,
) -> None:
    """`tibco-patterns` 6.2.0 shipped exactly this, and the cause was worse than a
    404: `navigation._free` tested case-sensitively, so the generated container
    page was written *into* the converted `install/Installation.md`."""
    target = tmp_path / "target"
    publish(
        target,
        {
            "toc.yml": 'items:\n  - title: "Installation"\n'
                       '    path: "html/install/installation.md"\n',
            "html/install/Installation.md": "# Installation\n",
        },
    )

    findings = artifacts_of(target)

    assert codes(findings) == ["LINK_BROKEN"]
    assert "differs only in case from html/install/Installation.md" in findings[0].message


def test_archives_toc_rows_pointing_at_absolute_urls_are_left_alone(tmp_path: Path) -> None:
    target = tmp_path / "target"
    publish(
        target,
        {"toc.yml": 'items:\n  - version: "1.0.0"\n    path: "https://example.com/a.zip"\n'},
        tree=RESOURCES,
        doc_class="archives",
        segment="",
        metadata=PRODUCT_METADATA,
    )

    assert artifacts_of(target) == []


def artifacts_of(target: Path):
    from docushift.validation import artifacts

    folder = only(target)
    return artifacts.check(folder, FolderIndex(folder.path))


# -- index.md, the reverse direction (Phase 10b) ----------------------------------


def test_a_published_file_the_index_never_names_is_a_note(tmp_path: Path) -> None:
    """The direction nothing checked. A link with no file is `LINK_BROKEN`; a file
    with no link is unreachable and, until now, reported by nobody."""
    target = tmp_path / "target"
    publish(
        target,
        {
            "index.md": "# Release Information\n\n- [Release Notes](relnotes.pdf)\n",
            "relnotes.pdf": "pdf",
            "readme.txt": "txt",
        },
        doc_class="release-information",
    )

    findings = artifacts_of(target)

    assert codes(findings) == ["INDEX_UNLINKED"]
    assert findings[0].severity is Severity.NOTE
    assert "readme.txt" in findings[0].message


def test_an_index_naming_every_file_is_silent(tmp_path: Path) -> None:
    """The expected state, and the one `render_index` produces by construction --
    it is handed the same routed list that decides what gets copied."""
    target = tmp_path / "target"
    publish(
        target,
        {
            "index.md": "# Release Information\n\n- [Notes](relnotes.pdf)\n- [Readme](readme.txt)\n",
            "relnotes.pdf": "pdf",
            "readme.txt": "txt",
        },
        doc_class="release-information",
    )

    assert artifacts_of(target) == []


def test_a_percent_encoded_link_names_the_file_it_encodes(tmp_path: Path) -> None:
    """`mft platform server v7.1 ... .pdf` is a real filename, and the index has to
    encode the spaces to link it at all. Comparing the raw target would report
    every such file as unlinked -- so this resolves through the same
    `transforms/links.py` the rest of the checker uses."""
    target = tmp_path / "target"
    publish(
        target,
        {
            "index.md": "# Guides\n\n- [Users Guide](mft%20server%20v7.1%20guide.pdf)\n",
            "mft server v7.1 guide.pdf": "pdf",
        },
        doc_class="user-guides",
    )

    assert artifacts_of(target) == []


def test_online_help_is_not_checked_because_its_index_is_not_a_manifest(
    tmp_path: Path,
) -> None:
    """Its navigation is `toc.yml` and its `index.md` -- in 2 of the sample's 17
    folders -- is a landing page. Checking it here would report every topic and
    every image in a converted tree as unlinked."""
    target = tmp_path / "target"
    publish(
        target,
        {
            "index.md": "# Help\n\n- [Install](install.md)\n",
            "install.md": "# Install\n",
            "orphan.md": "# Nobody links me\n",
        },
    )

    assert artifacts_of(target) == []


def test_the_generated_furniture_is_never_reported_as_unlinked(tmp_path: Path) -> None:
    """`toc.yml`, `metadata.yml` and `csh.yml` are the page's furniture, not
    artifacts the index is supposed to link."""
    target = tmp_path / "target"
    publish(
        target,
        {
            "index.md": "# Release Information\n\n- [Notes](relnotes.pdf)\n",
            "relnotes.pdf": "pdf",
            "csh.yml": '"install": "relnotes.pdf"\n',
        },
        doc_class="release-information",
    )

    assert artifacts_of(target) == []


# -- version.yml -----------------------------------------------------------------


VERSION_YML = 'versions:\n- title: "2.0.0"\n  path: "/2-0-0"\n- title: "1.0.0"\n  path: "/1-0-0"\n'


def dropdown_of(target: Path, body: str):
    from docushift.validation import artifacts

    entry = walk(target)[0]
    doc_class = entry.path / "online-help"
    (doc_class / "version.yml").write_text(body, encoding="utf-8")
    return artifacts.check_dropdown(entry, doc_class)


def test_a_consistent_drop_down_is_silent(tmp_path: Path) -> None:
    target = tmp_path / "target"
    publish(target)
    publish(target, segment="2-0-0")

    assert dropdown_of(target, VERSION_YML) == []


def test_a_drop_down_row_naming_no_folder_is_a_warning(tmp_path: Path) -> None:
    """A warning, not an error: `sync` preserves rows it does not own, and failing
    a run over somebody's hand-edit is how a tool teaches people to stop running it."""
    target = tmp_path / "target"
    publish(target)

    findings = dropdown_of(target, VERSION_YML)

    assert codes(findings) == ["DROPDOWN_INCONSISTENT"]
    assert REGISTRY["DROPDOWN_INCONSISTENT"].severity is Severity.WARNING
    assert "row /2-0-0 names no folder" in findings[0].message


def test_a_published_folder_with_no_row_is_a_warning(tmp_path: Path) -> None:
    target = tmp_path / "target"
    publish(target)
    publish(target, segment="2-0-0")
    publish(target, segment="3-0-0")

    findings = dropdown_of(target, VERSION_YML)

    assert codes(findings) == ["DROPDOWN_INCONSISTENT"]
    assert "3-0-0/ is published but has no drop-down row" in findings[0].message


def test_rows_out_of_numeric_order_are_named(tmp_path: Path) -> None:
    """`10.4.0` precedes `9.3.0`, which string ordering gets backwards."""
    target = tmp_path / "target"
    publish(target, segment="9-3-0")
    publish(target, segment="10-4-0")
    body = 'versions:\n- title: "9.3.0"\n  path: "/9-3-0"\n- title: "10.4.0"\n  path: "/10-4-0"\n'

    findings = dropdown_of(target, body)

    assert codes(findings) == ["DROPDOWN_INCONSISTENT"]
    assert "not newest-first" in findings[0].message


def test_a_hand_written_row_pointing_outside_the_doc_class_is_not_ours(tmp_path: Path) -> None:
    """`sync/versions.merge` excludes these from what it owns; so does the linter."""
    target = tmp_path / "target"
    publish(target)
    body = (
        'versions:\n- title: "Older"\n  path: "https://example.com/old"\n'
        '- title: "1.0.0"\n  path: "/1-0-0"\n'
    )

    assert dropdown_of(target, body) == []


# -- csh.py ----------------------------------------------------------------------


def csh_of(target: Path):
    folder = only(target)
    return csh_mod.check(folder, FolderIndex(folder.path))


def test_a_csh_value_pointing_at_a_deleted_topic_is_a_link_broken(tmp_path: Path) -> None:
    """CSH is checked as link integrity, because that is what it is."""
    target = tmp_path / "target"
    publish(target, {"csh.yml": 'help_1: "html/gone.md"\n'})

    findings = csh_of(target)

    assert codes(findings) == ["LINK_BROKEN"]
    assert "help_1 -> html/gone.md is not in this version folder" in findings[0].message


def test_a_csh_anchor_that_is_not_on_the_page_is_a_warning(tmp_path: Path) -> None:
    """33 of the sample's 47, against 0 missing file parts: the half
    `transforms/csh.py` controls is perfect and the half that depends on anchor
    emission is not."""
    target = tmp_path / "target"
    publish(
        target,
        {
            "csh.yml": 'help_1: "html/a.md#gone"\n',
            "html/a.md": "---\ncsh: help_1\n---\n\n# A\n",
        },
    )

    assert codes(csh_of(target)) == ["ANCHOR_MISSING"]


def test_a_frontmatter_identifier_missing_from_csh_yml_is_a_mismatch(tmp_path: Path) -> None:
    """The map and the frontmatter are written in one pass, so a disagreement is a
    regression -- but it breaks one Help button, not the page."""
    target = tmp_path / "target"
    publish(
        target,
        {
            "csh.yml": 'help_1: "html/a.md"\n',
            "html/a.md": "---\ncsh:\n  - help_1\n  - help_2\n---\n\n# A\n",
        },
    )

    findings = csh_of(target)

    assert codes(findings) == ["CSH_FRONTMATTER_MISMATCH"]
    assert REGISTRY["CSH_FRONTMATTER_MISMATCH"].severity is Severity.WARNING
    assert "frontmatter claims help_2" in findings[0].message


def test_a_page_claiming_six_lost_identifiers_is_one_row_not_six(tmp_path: Path) -> None:
    target = tmp_path / "target"
    claimed = "\n".join(f"  - help_{n}" for n in range(6))
    publish(target, {"html/a.md": f"---\ncsh:\n{claimed}\n---\n\n# A\n"})

    assert len(csh_of(target)) == 1


def test_a_csh_entry_whose_page_does_not_claim_it_is_the_other_half(tmp_path: Path) -> None:
    target = tmp_path / "target"
    publish(target, {"csh.yml": 'help_1: "html/a.md"\n', "html/a.md": "# A\n"})

    findings = csh_of(target)

    assert codes(findings) == ["CSH_FRONTMATTER_MISMATCH"]
    assert "whose frontmatter does not list it" in findings[0].message


def test_a_folder_with_no_csh_yml_is_not_a_finding(tmp_path: Path) -> None:
    """13 of the sample's 17 online-help folders have none: the source shipped no
    help mapping, and §9.4 gives an empty map no file rather than an empty one."""
    target = tmp_path / "target"
    publish(target, {"html/a.md": "# A\n"})

    assert csh_of(target) == []


def test_an_unparseable_csh_yml_is_reported_as_an_unparsed_artifact(tmp_path: Path) -> None:
    target = tmp_path / "target"
    publish(target, {"csh.yml": "help_1: [unclosed\n"})

    assert codes(csh_of(target)) == ["ARTIFACT_UNPARSED"]


# -- csh.py, §7.6: the cross-version regression ----------------------------------


def product_of(target: Path):
    """The one product folder in a multi-version fixture tree."""
    found = walk(target)
    assert len(found) == 1, found
    return found[0]


def shelf(target: Path, maps: dict[str, str | None], *, doc_class: str = "online-help") -> Path:
    """Several published versions of one product, `{segment -> csh.yml body}`.

    `None` publishes the folder with no map at all, which is the common case:
    13 of the sample's 17 `online-help` folders have none.
    """
    for segment, body in maps.items():
        files = {} if body is None else {"csh.yml": body}
        publish(target, files, doc_class=doc_class, segment=segment)
    return target


def test_an_identifier_the_version_below_had_and_this_one_does_not_is_a_drop(
    tmp_path: Path,
) -> None:
    """The one defect that cannot be seen from inside a version.

    1-0-0's map is correct and 2-0-0's map is correct, and the Help button for
    `help_2` still breaks on upgrade. 51 of the corpus's 317 comparable pairs
    (16.1%) look like this.
    """
    target = tmp_path / "target"
    shelf(target, {
        "1-0-0": 'help_1: "html/a.md"\nhelp_2: "html/b.md"\n',
        "2-0-0": 'help_1: "html/a.md"\n',
    })

    findings = csh_mod.check_regression(product_of(target))

    assert codes(findings) == ["CSH_IDENTIFIER_DROPPED"]
    assert REGISTRY["CSH_IDENTIFIER_DROPPED"].severity is Severity.WARNING
    assert findings[0].version == "2-0-0"
    assert findings[0].count == 1
    assert findings[0].message == "1 of 1-0-0's 2: help_2"
    assert findings[0].path.endswith("2-0-0/csh.yml")


def test_a_map_that_did_not_lose_anything_reports_nothing(tmp_path: Path) -> None:
    """The control. A check that fires on every pair is not a check."""
    target = tmp_path / "target"
    shelf(target, {
        "1-0-0": 'help_1: "html/a.md"\n',
        "2-0-0": 'help_1: "html/a.md"\nhelp_2: "html/b.md"\n',
    })

    assert csh_mod.check_regression(product_of(target)) == []


def test_a_single_version_product_is_not_compared_against_anything(tmp_path: Path) -> None:
    """§7.6 asked for a note on "no prior version"; its intent was *do not fail a
    first conversion*, and 150 of the corpus's products would have earned one
    against 51 real findings."""
    target = tmp_path / "target"
    shelf(target, {"1-0-0": 'help_1: "html/a.md"\n'})

    assert csh_mod.check_regression(product_of(target)) == []


def test_a_predecessor_with_no_map_gives_nothing_to_regress_against(tmp_path: Path) -> None:
    target = tmp_path / "target"
    shelf(target, {"1-0-0": None, "2-0-0": 'help_1: "html/a.md"\n'})

    assert csh_mod.check_regression(product_of(target)) == []


def test_a_vanished_map_fires_once_and_not_in_every_version_after_it(tmp_path: Path) -> None:
    """The predecessor is the immediate next-lower folder and nothing cleverer.

    Skipping back to the last version that *had* a map sounds more thorough and
    turns one defect into an unbounded row count: 3-0-0 and 4-0-0 would each
    report 1-0-0's identifiers again, and the version that actually lost them
    would stop being identifiable.
    """
    target = tmp_path / "target"
    shelf(target, {
        "1-0-0": 'help_1: "html/a.md"\nhelp_2: "html/b.md"\n',
        "2-0-0": None,
        "3-0-0": None,
        "4-0-0": None,
    })

    findings = csh_mod.check_regression(product_of(target))

    assert [(f.version, f.count) for f in findings] == [("2-0-0", 2)]


def test_losing_more_than_ninety_percent_is_named_a_re_key_in_the_message(
    tmp_path: Path,
) -> None:
    """15 of the corpus's 51 dropping pairs did, two of them losing 188 of 188.

    It changes nothing about the finding -- same code, same severity -- which is
    why it is a sentence in the message rather than a second code.
    """
    target = tmp_path / "target"
    before = "".join(f'help_{n}: "html/a.md"\n' for n in range(11))
    target = shelf(target, {"1-0-0": before, "2-0-0": 'help_0: "html/a.md"\n'})

    findings = csh_mod.check_regression(product_of(target))

    assert findings[0].count == 10
    assert findings[0].message.startswith("10 of 1-0-0's 11 -- the map was re-keyed: ")


def test_the_message_names_five_and_counts_the_rest(tmp_path: Path) -> None:
    """The register carries the magnitude in `count`; `csh report --since` carries
    the detail. The message is the bridge and it is bounded."""
    target = tmp_path / "target"
    before = "".join(f'help_{n}: "html/a.md"\n' for n in range(8))
    shelf(target, {"1-0-0": before, "2-0-0": 'help_0: "html/a.md"\n'})

    findings = csh_mod.check_regression(product_of(target))

    assert findings[0].count == 7
    assert findings[0].message.endswith(
        "help_1, help_2, help_3, help_4, help_5 and 2 more"
    )


def test_an_identifier_that_moved_to_another_page_is_carried_and_never_reported(
    tmp_path: Path,
) -> None:
    """1,084 of 8,425 survivors (12.9%) retarget between adjacent versions, in 81
    of 317 pairs. That is pages being renamed, and the Help button still works."""
    target = tmp_path / "target"
    shelf(target, {
        "1-0-0": 'help_1: "html/old.md"\n',
        "2-0-0": 'help_1: "doc/new.md"\n',
    })
    entry = product_of(target)

    assert csh_mod.check_regression(entry) == []
    assert csh_mod.coverage(entry).diffs[0].retargeted == ("help_1",)


def test_versions_are_ordered_numerically_so_ten_comes_after_nine(tmp_path: Path) -> None:
    """`natural_version_key` over the dashed published segment: it splits on digit
    runs and compares them numerically, so `10-4-0` sorts above `9-3-0`. Sorted as
    strings the pair would invert and the drop would be blamed on the older
    folder."""
    target = tmp_path / "target"
    shelf(target, {
        "9-3-0": 'help_1: "html/a.md"\nhelp_2: "html/b.md"\n',
        "10-4-0": 'help_1: "html/a.md"\n',
    })

    findings = csh_mod.check_regression(product_of(target))

    assert [f.version for f in findings] == ["10-4-0"]


def test_two_doc_classes_are_two_sequences_and_never_compared_across(
    tmp_path: Path,
) -> None:
    """A product's `user-guides` 2-0-0 is not the successor of its `online-help`
    1-0-0. They are different documents that happen to share a slug."""
    target = tmp_path / "target"
    publish(target, {"csh.yml": 'help_1: "html/a.md"\n'}, doc_class="online-help",
            segment="1-0-0")
    publish(target, {"csh.yml": 'help_2: "html/b.md"\n'}, doc_class="user-guides",
            segment="2-0-0")

    entry = product_of(target)

    assert csh_mod.pairs(entry) == []
    assert csh_mod.check_regression(entry) == []


def test_coverage_counts_the_shelf_without_a_terminal(tmp_path: Path) -> None:
    """What `csh report` prints, computed where it can be tested."""
    target = tmp_path / "target"
    shelf(target, {
        "1-0-0": 'help_1: "html/a.md#top"\nhelp_2: "html/b.md"\n',
        "2-0-0": 'help_1: "html/a.md"\n',
        "3-0-0": None,
    })

    found = csh_mod.coverage(product_of(target))

    assert (found.published, found.mapped) == (3, 2)
    # The union across versions, and the distinct pages they open, anchors off.
    assert (found.identifiers, found.pages) == (2, 2)
    # Both pairs are comparable -- 2-0-0 carries a map, so 3-0-0 losing it counts
    # -- and between them they lose help_2 and then help_1.
    assert (found.comparable, found.dropped) == (2, 2)


# -- driver.py -------------------------------------------------------------------


def test_an_api_reference_folder_is_checked_for_metadata_and_nothing_else(
    tmp_path: Path,
) -> None:
    """Copied Javadoc. 496 of 499 ship their own frame set, and walking them would
    dominate a run to report defects in somebody else's generator."""
    target = tmp_path / "target"
    folder = publish(target, tree=RESOURCES, doc_class="api-references")
    (folder / "index.html").write_text('<a href="gone.html">x</a>\n', encoding="utf-8")
    (folder / "stray.md").write_text("[gone](nowhere.md)\n", encoding="utf-8")

    result = Validator(target).check_folder(only(target))

    assert result.findings == []
    assert result.report.files == 0


def test_a_part_folder_yields_one_note_and_no_other_finding(tmp_path: Path) -> None:
    """However broken its contents -- the swap deliberately refused to publish it."""
    target = tmp_path / "target"
    publish(target)
    residue = target / TREE / "en-us" / SLUG / "online-help" / "1-1-0.part"
    residue.mkdir(parents=True)
    (residue / "a.md").write_text("[gone](nowhere.md)\n", encoding="utf-8")

    collected: list = []
    validator = Validator(target)
    validator._record = collected.extend  # type: ignore[method-assign]
    stats = validator.run()

    assert codes(collected) == ["SYNC_RESIDUE"]
    assert REGISTRY["SYNC_RESIDUE"].severity is Severity.NOTE
    assert stats.residue == 1


def test_the_external_pass_is_not_run_without_a_fetcher(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The external pass is reached only when a fetcher is handed over.

    Asserted by making the pass itself explode: the URLs are still collected and
    counted, which is the behaviour the report depends on, and nothing walks them.
    """
    target = tmp_path / "target"
    publish(target, {"a.md": "[s](https://example.com/a)\n"})

    def explode(urls, fetch):  # pragma: no cover - the assertion is that it is not called
        raise AssertionError(f"checked {urls} without --check-external")

    monkeypatch.setattr("docushift.validation.driver.links.check_external", explode)
    validator = Validator(target)
    stats = validator.run()

    assert stats.external_checked == 0
    assert validator.context.external == {"https://example.com/a"}


def test_the_flag_builds_the_only_http_session_there_is(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """"No network without the flag" as a property of the code, not a promise:
    with the flag off there is no session to make a call with."""
    target = tmp_path / "target"
    publish(target, {"html/a.md": "[s](https://example.com/a)\n"})
    built: list[str] = []

    def session(crawl, accept="*/*"):
        built.append(accept)
        raise AssertionError("a session was built")

    monkeypatch.setattr("docushift.utils.http.build_session", session)

    assert invoke(runner, tmp_path, target).exit_code == 0
    assert built == []


def test_a_clean_published_folder_produces_nothing(tmp_path: Path) -> None:
    target = tmp_path / "target"
    publish(
        target,
        {
            "toc.yml": 'items:\n  - title: "A"\n    path: "html/a.md"\n',
            "html/a.md": "# A\n\n![shot](media/s.png)\n\n[b](b.md#top)\n",
            "html/media/s.png": "x",
            "html/b.md": "# Top\n",
        },
    )

    result = Validator(target).check_folder(only(target))

    assert result.findings == []


def test_the_run_carries_the_drop_as_a_count_not_a_row_per_identifier(
    tmp_path: Path,
) -> None:
    """§7.6 is a product-level question -- it needs two version folders -- so the
    driver asks it beside the drop-down check rather than inside the per-folder
    pass, and sums the magnitude off the finding's `count`."""
    target = tmp_path / "target"
    shelf(target, {
        "1-0-0": 'help_1: "html/a.md"\nhelp_2: "html/b.md"\nhelp_3: "html/c.md"\n',
        "2-0-0": 'help_1: "html/a.md"\n',
    })

    collected: list = []
    validator = Validator(target)
    validator._record = collected.extend  # type: ignore[method-assign]
    stats = validator.run()

    assert "CSH_IDENTIFIER_DROPPED" in codes(collected)
    assert sum(1 for c in codes(collected) if c == "CSH_IDENTIFIER_DROPPED") == 1
    assert stats.dropped == 2


# -- the command -----------------------------------------------------------------


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def invoke(runner: CliRunner, root: Path, target: Path, *argv: str):
    return runner.invoke(
        main, ["--root", str(root), "validate", "--target-dir", str(target), *argv], color=False
    )


def test_validate_exits_zero_on_a_clean_tree_and_one_on_a_broken_one(
    runner: CliRunner, tmp_path: Path
) -> None:
    """The one gating command in the tool (§7.4)."""
    target = tmp_path / "target"
    publish(target, {"html/a.md": "# A\n"})

    assert invoke(runner, tmp_path, target).exit_code == 0

    (target / TREE / "en-us" / SLUG / "online-help" / "1-0-0" / "html" / "a.md").write_text(
        "# A\n\n![shot](media/missing.png)\n", encoding="utf-8"
    )
    result = invoke(runner, tmp_path, target)

    assert result.exit_code == 1
    assert "LINK_BROKEN" in result.output


def test_warnings_alone_do_not_change_the_exit_code(runner: CliRunner, tmp_path: Path) -> None:
    """1,626 unmatched anchors in the sample. An 11.6% rate cannot gate."""
    target = tmp_path / "target"
    publish(target, {"html/a.md": "# A\n\n[x](a.md#nope)\n"})

    result = invoke(runner, tmp_path, target)

    assert result.exit_code == 0
    assert "ANCHOR_MISSING" in result.output


def test_a_selection_that_matches_nothing_exits_one(runner: CliRunner, tmp_path: Path) -> None:
    """The same rule the four stage commands took in 7a."""
    target = tmp_path / "target"
    publish(target)

    result = invoke(runner, tmp_path, target, "--product", "not-a-product")

    assert result.exit_code == 1
    assert "No published version folders match" in result.output


def test_dry_run_lists_the_selection_and_reads_no_file(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "target"
    publish(target, {"html/a.md": "[gone](nowhere.md)\n"})

    def forbidden(*args, **kwargs):  # pragma: no cover - the assertion is the absence
        raise AssertionError("--dry-run read a file")

    monkeypatch.setattr(Path, "read_text", forbidden)
    result = invoke(runner, tmp_path, target, "--dry-run")

    assert result.exit_code == 0
    assert "Would validate (1)" in result.output


def test_report_run_last_reads_back_what_validate_wrote(
    runner: CliRunner, tmp_path: Path
) -> None:
    """The cross-check 7a closed on, and the reason 7b comes after it.

    Exported rather than read off the terminal: the console summary is a table
    that wraps, and the claim being made is that the *row* survived the round
    trip through `findings`, message and all.
    """
    target = tmp_path / "target"
    publish(target, {"html/a.md": "![shot](media/missing.png)\n"})
    export = tmp_path / "report.md"

    assert invoke(runner, tmp_path, target).exit_code == 1
    result = runner.invoke(
        main,
        ["--root", str(tmp_path), "report", "--run", "last", "--export", str(export)],
        color=False,
    )

    assert result.exit_code == 0
    written = export.read_text(encoding="utf-8")
    assert "LINK_BROKEN" in written
    assert "media/missing.png is not in this version folder" in written
    assert f"{TREE}/en-us/{SLUG}/online-help/1-0-0/html/a.md:1" in written


# -- the csh command group -------------------------------------------------------


def csh_cli(runner: CliRunner, root: Path, target: Path, *argv: str):
    return runner.invoke(
        main, ["--root", str(root), "csh", *argv, "--target-dir", str(target)], color=False
    )


def test_csh_list_prints_each_identifier_with_whether_its_target_is_there(
    runner: CliRunner, tmp_path: Path
) -> None:
    target = tmp_path / "target"
    publish(target, {"csh.yml": 'help_1: "a.md"\nhelp_2: "gone.md"\n', "a.md": "# A\n"})

    result = csh_cli(runner, tmp_path, target, "list")

    assert result.exit_code == 0
    assert "help_1" in result.output and "help_2" in result.output
    assert "yes" in result.output and "no" in result.output


def test_csh_list_by_identifier_names_the_versions_that_do_not_carry_it(
    runner: CliRunner, tmp_path: Path
) -> None:
    """The query the command exists for: "the Help button for X is broken in the
    new version" -- where did it go, across the whole shelf, in one call."""
    target = tmp_path / "target"
    shelf(target, {"1-0-0": 'help_1: "a.md"\n', "2-0-0": 'help_9: "a.md"\n'})

    result = csh_cli(runner, tmp_path, target, "list", "--identifier", "help_1")

    assert result.exit_code == 0
    assert "1-0-0" in result.output
    assert "does not carry help_1" in result.output


def test_csh_list_reports_a_case_only_near_miss_rather_than_matching_it(
    runner: CliRunner, tmp_path: Path
) -> None:
    """`GatewayInstances` and `gatewayInstances` are two live help targets in the
    corpus (§9.1). Folding them here is how one Help button answers for the other."""
    target = tmp_path / "target"
    publish(target, {"csh.yml": 'GatewayInstances: "a.md"\n', "a.md": "# A\n"})

    result = csh_cli(runner, tmp_path, target, "list", "--identifier", "gatewayinstances")

    assert result.exit_code == 0
    assert "differs only in case" in result.output


def test_csh_report_counts_coverage_and_the_drop(runner: CliRunner, tmp_path: Path) -> None:
    target = tmp_path / "target"
    shelf(target, {
        "1-0-0": 'help_1: "a.md"\nhelp_2: "b.md"\n',
        "2-0-0": 'help_1: "a.md"\n',
    })

    result = csh_cli(runner, tmp_path, target, "report")

    assert result.exit_code == 0
    assert "2 of 2 published version folder(s) carry a help map" in result.output
    # The summary line wraps at the console width, so the claim is made on the
    # halves rather than on a sentence that may have a newline through it.
    assert "1 comparable pair(s)" in result.output
    assert "identifier(s) dropped" in result.output


def test_csh_report_since_names_every_identifier_the_finding_only_counts(
    runner: CliRunner, tmp_path: Path
) -> None:
    """The register carries the magnitude, the command carries the detail --
    including the retargeting that is deliberately not a finding."""
    target = tmp_path / "target"
    shelf(target, {
        "1-0-0": 'help_1: "old.md"\nhelp_2: "b.md"\n',
        "2-0-0": 'help_1: "new.md"\nhelp_3: "c.md"\n',
    })

    result = csh_cli(runner, tmp_path, target, "report", "--since", "1.0.0")

    assert result.exit_code == 0
    assert "1 dropped" in result.output and "help_2" in result.output
    assert "1 added" in result.output and "help_3" in result.output
    assert "1 retargeted" in result.output


def test_csh_report_since_a_version_with_nothing_below_it_says_so(
    runner: CliRunner, tmp_path: Path
) -> None:
    target = tmp_path / "target"
    publish(target, {"csh.yml": 'help_1: "a.md"\n', "a.md": "# A\n"})

    result = csh_cli(runner, tmp_path, target, "report", "--since", "1.0.0")

    assert result.exit_code == 0
    assert "No published version in this selection has 1-0-0 directly below it" in result.output


def test_csh_validate_warns_on_a_drop_and_still_exits_zero(
    runner: CliRunner, tmp_path: Path
) -> None:
    """16% of the corpus's version upgrades drop at least one identifier. A gate
    that fails on that is a gate nobody runs."""
    target = tmp_path / "target"
    shelf(target, {
        "1-0-0": 'help_1: "a.md"\nhelp_2: "a.md"\n',
        "2-0-0": 'help_1: "a.md"\n',
    })
    for segment in ("1-0-0", "2-0-0"):
        publish(target, {"a.md": "---\ncsh:\n  - help_1\n  - help_2\n---\n\n# A\n"},
                segment=segment)

    result = csh_cli(runner, tmp_path, target, "validate")

    assert result.exit_code == 0
    assert "CSH_IDENTIFIER_DROPPED" in result.output


def test_csh_validate_gates_on_a_map_pointing_at_a_file_that_is_not_there(
    runner: CliRunner, tmp_path: Path
) -> None:
    """§7.4's one rule, unchanged: exit 1 if and only if an error was recorded."""
    target = tmp_path / "target"
    publish(target, {"csh.yml": 'help_1: "gone.md"\n'})

    result = csh_cli(runner, tmp_path, target, "validate")

    assert result.exit_code == 1
    assert "LINK_BROKEN" in result.output


def test_csh_validate_and_validate_cannot_disagree(runner: CliRunner, tmp_path: Path) -> None:
    """Both call `validation/csh.py`, which is the only thing in the tool that reads
    a help map or compares two. Asserted rather than commented."""
    target = tmp_path / "target"
    shelf(target, {
        "1-0-0": 'help_1: "a.md"\nhelp_2: "a.md"\n',
        "2-0-0": 'help_1: "a.md"\n',
    })
    for segment in ("1-0-0", "2-0-0"):
        publish(target, {"a.md": "---\ncsh:\n  - help_1\n  - help_2\n---\n\n# A\n"},
                segment=segment)

    both = csh_cli(runner, tmp_path, target, "validate")
    full = invoke(runner, tmp_path, target)

    assert both.exit_code == 0 and full.exit_code == 0
    assert "CSH_IDENTIFIER_DROPPED" in both.output
    assert "CSH_IDENTIFIER_DROPPED" in full.output


def test_a_csh_selection_that_matches_nothing_exits_one(
    runner: CliRunner, tmp_path: Path
) -> None:
    """The same rule the four stage commands took in 7a, and `validate` in 7b."""
    target = tmp_path / "target"
    publish(target)

    result = csh_cli(runner, tmp_path, target, "report", "--product", "not-a-product")

    assert result.exit_code == 1


def test_the_resources_tree_is_not_walked_for_a_help_map(
    runner: CliRunner, tmp_path: Path
) -> None:
    """`transforms/csh.py` writes `csh.yml` into the Markdown output root, which
    `sync` places in the docs tree and nowhere else. Walking the sibling would
    double `csh report`'s rows to print zeroes."""
    target = tmp_path / "target"
    publish(target, tree=RESOURCES, doc_class="api-references")

    result = csh_cli(runner, tmp_path, target, "report")

    assert result.exit_code == 1
    assert "docs tree" in result.output
