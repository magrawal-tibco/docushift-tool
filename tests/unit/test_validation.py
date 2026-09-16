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
    from docushift.validation import csh

    folder = only(target)
    return csh.check(folder, FolderIndex(folder.path))


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
