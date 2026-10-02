"""Stage 6b: the gate, the TOC adapter seam, the policy, the packer and the swap.

Three layers, tested at three grains. The gate and the swap are about what the
stage refuses to do -- touch a non-Flare set, guess at a navigation it does not
recognise, write to its input. The packer is pure: it decides layout from a dict of
word counts and never opens a file, so R1's boundary rules are asserted against
hand-built TOC trees rather than against a corpus. The renderer and the audit sit
between them, and every one of requirements §6's acceptance checks is pinned here
by making it fail.

Where a test exists because a real doc set broke, the doc set is named. Those are
the cases nobody would have invented: a topic listed under two guides, a topic on
disk that the TOC never mentions, a filename whose natural slug already ends in
`-2`.
"""

from pathlib import Path, PurePosixPath

import pytest
import yaml

from docushift.config import ConfigManager
from docushift.models import SourceEngine
from docushift.reframe import ReframeOutcome, Reframer, policy_for
from docushift.reframe import csh as csh_map
from docushift.reframe.audit import audit
from docushift.reframe.packer import (
    UNNAVIGATED,
    Page,
    Topic,
    assign,
    carry,
    layout_of,
    pack,
    project,
    relocate,
)
from docushift.reframe.pages import (
    LinkCounts,
    render,
    rewrite_links,
    shift_headings,
    split_frontmatter,
    title_of,
)
from docushift.reframe.policy import ReframePolicy
from docushift.reframe.review import QUEUEING, branches, inspect, rows
from docushift.reframe.toc import (
    DocsUrlSubfolderlist,
    ItemsPathChildren,
    TocEntry,
    registered_schemas,
    retarget,
    schema_for,
)
from docushift.reporting.findings import FindingsRun, Severity
from docushift.utils import csvio
from tests.conftest import make_product, make_version

TOC = """\
docs_list_title: "Online Help"
docs:
  - title: "Installation"
    url: "installation/installation-2.md"
    subfolderlist:
      - title: "Installation Overview"
        url: "installation/installation-overvie.md"
  - title: "User Guide"
    url: "users-guide/user-guide.md"
"""

#: The same tree in the dialect Stage 6a wrote before Phase 36. A converted tree
#: still on disk in it must keep reframing until it is reconverted.
OLD_TOC = """\
items:
  - title: "Installation"
    path: "installation/installation-2.md"
    children:
      - title: "Installation Overview"
        path: "installation/installation-overvie.md"
  - title: "User Guide"
    path: "users-guide/user-guide.md"
"""


def all_codes(findings) -> list[str]:
    return [finding.code for finding in findings]


def codes(findings) -> list[str]:
    """Every code except the origin map's, which fire on almost every run by design.

    An undeclared origin template is the expected state for sixteen of seventeen
    products, so the warning rides along with every merge in this file and says
    nothing about the condition under test. Filtering it here rather than in each
    assertion keeps the rest of the file about what it was about; the tests that
    are about the origin map use `all_codes`.
    """
    return [code for code in all_codes(findings) if code not in ROUTINE_ORIGIN_CODES]


#: No declaration and no cached sitemap is this file's default state (Phase 33).
ROUTINE_ORIGIN_CODES = {"ORIGIN_TEMPLATE_UNDECLARED", "ORIGIN_SITEMAP_MISSING"}


@pytest.fixture
def flare(catalog):
    """A catalogued Flare product with one eligible version."""
    built = make_product("tibco-flare-docs", product_code="flaredocs", family="messaging")
    built.versions = {
        "10.5.1": make_version("tibco-flare-docs", "10.5.1", engine=SourceEngine.FLARE),
    }
    catalog.merge_fetch_results([built])
    return catalog.get_product("tibco-flare-docs")


def converted_tree(config: ConfigManager, product, number: str, toc: str = TOC) -> Path:
    """A minimal Stage 6a output tree: a `toc.yml` and the files it names."""
    tree = config.output_path(product.bu, product.family, product.slug, number)
    tree.mkdir(parents=True, exist_ok=True)
    (tree / "toc.yml").write_text(toc, encoding="utf-8")
    def write(node: dict) -> None:
        page = tree / (node.get("url") or node["path"])
        page.parent.mkdir(parents=True, exist_ok=True)
        # The body's H1 is the node's **title**, not its path. Since Phase 29 the
        # anchor a topic gets is the platform's slug of its rendered heading, so a
        # fixture whose H1 was a file path would assert against
        # `installationinstallation-2md` and teach nothing about the real rule.
        page.write_text(f"# {node['title']}\n", encoding="utf-8")
        for child in node.get("subfolderlist") or node.get("children") or []:
            write(child)

    loaded = yaml.safe_load(toc)
    for row in loaded.get("docs") or loaded.get("items") or []:
        write(row)
    return tree


# -- the gate (C1/C2) ---------------------------------------------------------


def test_a_non_flare_version_is_counted_and_never_read(config, catalog, product, version):
    """The `product` fixture is `auto`, and the gate must not need a tree to decide.

    Deliberately asserted with no output tree on disk: C2 puts the gate at the top
    of the stage, so a DocBook set selected by `--all` is a counted row rather than
    a `NO_OUTPUT` row about a merge that was never going to happen.
    """
    result = Reframer(config, catalog).reframe_one(product, version)

    assert result.outcome is ReframeOutcome.NOT_FLARE
    assert result.path is None
    assert not config.reframed_dir.exists()


def test_the_gate_holds_on_the_standalone_path(config, catalog, product, version, tmp_path):
    """`--input` is the invocation the selection cannot filter -- requirements C2.

    A hand-pointed folder plus a `--product` naming a DocBook row is the concrete
    wrong-doc-set mistake, and the gate is checked before `source` is looked at.
    """
    source = tmp_path / "somebody-elses-tree"
    source.mkdir()
    (source / "toc.yml").write_text(TOC, encoding="utf-8")

    result = Reframer(config, catalog).reframe_one(
        product, version, source=source, output=tmp_path / "out"
    )

    assert result.outcome is ReframeOutcome.NOT_FLARE
    assert not (tmp_path / "out").exists()


def test_flare_is_the_only_reframable_engine(config, catalog, flare):
    from docushift.reframe import REFRAMABLE_ENGINES

    assert REFRAMABLE_ENGINES == (SourceEngine.FLARE,)
    assert flare.versions["10.5.1"].engine in REFRAMABLE_ENGINES


def test_a_flare_version_with_no_conversion_is_named_not_failed(config, catalog, flare):
    result = Reframer(config, catalog).reframe_one(flare, flare.versions["10.5.1"])

    assert result.outcome is ReframeOutcome.NO_OUTPUT
    assert "docushift convert" in result.message


# -- the merge, end to end -----------------------------------------------------


def test_a_flare_set_merges_into_fewer_pages_and_says_so(config, catalog, flare):
    """The stage's whole visible behaviour, asserted at the grain the report uses.

    Two top-level rows are two hard boundaries (R1.1), so three topics under a cap
    nothing comes near become exactly two pages -- not one, however much room is
    left. That is R1.2 stated as an outcome rather than as a rule.
    """
    converted_tree(config, flare, "10.5.1")

    result = Reframer(config, catalog).reframe_one(flare, flare.versions["10.5.1"])

    assert result.outcome is ReframeOutcome.REFRAMED
    assert result.toc_schema == "docs-url-subfolderlist"
    assert (result.topics, result.pages) == (3, 2)
    written = sorted(p.relative_to(result.path).as_posix() for p in result.path.rglob("*") if p.is_file())
    assert written == [
        "installation.md",
        "redirects.yml",
        "reframe.yml",
        "rename-map.csv",
        "review-queue.csv",
        "toc.yml",
        "user-guide.md",
    ]


def test_an_absorbed_topic_becomes_an_anchored_section_under_its_parents_h1(
    config, catalog, flare
):
    """R2, R2.1 and R7 on one page: frontmatter, an H1, then the child at H2.

    This is the test the Phase 28 repack was aimed at. It used to assert
    `body.count("\\n## ") == 2` and `"\\n# " not in body` -- two topics side by side
    as sibling `##` sections and no H1 anywhere, because a page was a run of
    topics rather than a subtree. Now the page *is* the Installation subtree, so
    Installation supplies the page's one H1 and its child nests beneath it.
    """
    converted_tree(config, flare, "10.5.1")

    result = Reframer(config, catalog).reframe_one(flare, flare.versions["10.5.1"])
    text = (result.path / "installation.md").read_text(encoding="utf-8")
    matter, body = split_frontmatter(text)

    assert yaml.safe_load(matter.strip("-\r\n")) == {
        "title": "Installation", "guide": "Installation", "merged_from": 2,
    }
    # No `<a id>` anywhere since Phase 29: the platform slugs the heading itself.
    assert "<a id=" not in body
    assert body.count("\n# ") == 1
    assert body.count("\n## ") == 1
    # The H1 is the parent's, not the absorbed child's.
    assert "\n# Installation\n" in body
    assert "\n## Installation Overview\n" in body


def test_the_toc_points_absorbed_topics_at_a_fragment_and_leaders_at_a_page(
    config, catalog, flare
):
    """R3. The merge has to be invisible to a reader following the navigation."""
    converted_tree(config, flare, "10.5.1")

    result = Reframer(config, catalog).reframe_one(flare, flare.versions["10.5.1"])
    document = yaml.safe_load((result.path / "toc.yml").read_text(encoding="utf-8"))

    assert document == MERGED_TOC


#: What R3 writes for `TOC`, from either input dialect: html-to-md's keys
#: (Phase 36), with the merged section's fragment carried in `url`.
MERGED_TOC = {
    "docs_list_title": "Online Help",
    "docs": [
        {
            "title": "Installation",
            "url": "installation.md",
            "subfolderlist": [
                {
                    "title": "Installation Overview",
                    "url": "installation.md#installation-overview",
                }
            ],
        },
        {"title": "User Guide", "url": "user-guide.md"},
    ],
}


def test_a_tree_still_in_the_old_dialect_reframes_into_the_new_one(config, catalog, flare):
    """Phase 36. `output/` keeps `items`/`path`/`children` until it is reconverted,
    and failing Reframe on it in the meantime would buy nothing: the old dialect
    is read, the new one is written, and the merge is the same merge."""
    converted_tree(config, flare, "10.5.1", OLD_TOC)

    result = Reframer(config, catalog).reframe_one(flare, flare.versions["10.5.1"])
    document = yaml.safe_load((result.path / "toc.yml").read_text(encoding="utf-8"))

    assert document == MERGED_TOC


def test_every_source_topic_gets_a_redirect_with_its_anchor(config, catalog, flare):
    """R5. One 301 per topic, anchored even for the topic that leads its page.

    A reader arriving from an old URL named a topic, not a page, and dropping them
    at the top of a merged page is a worse answer than one redundant fragment.
    """
    converted_tree(config, flare, "10.5.1")

    result = Reframer(config, catalog).reframe_one(flare, flare.versions["10.5.1"])
    document = yaml.safe_load((result.path / "redirects.yml").read_text(encoding="utf-8"))

    assert document["redirects"] == [
        {"from": "installation/installation-2.md",
         # `#installation`, not `#installation-2`: the anchor is the platform's
         # slug of the heading, so the file's `-2` disambiguator does not leak
         # into a reader's address bar (Phase 29).
         "to": "installation.md#installation", "status": 301},
        {"from": "installation/installation-overvie.md",
         "to": "installation.md#installation-overview", "status": 301},
        {"from": "users-guide/user-guide.md",
         "to": "user-guide.md#user-guide", "status": 301},
    ]


def test_two_runs_over_one_input_produce_identical_bytes(config, catalog, flare):
    """C5, and §6's last row. Determinism is what makes the merge reviewable at all.

    A `--force` re-run rather than a second `reframe_one`, because currency would
    otherwise short-circuit the thing under test.
    """
    converted_tree(config, flare, "10.5.1")
    reframer = Reframer(config, catalog)

    first = reframer.reframe_one(flare, flare.versions["10.5.1"])
    once = {p.relative_to(first.path).as_posix(): p.read_bytes() for p in first.path.rglob("*") if p.is_file()}
    second = reframer.reframe_one(flare, flare.versions["10.5.1"], force=True)

    assert {
        p.relative_to(second.path).as_posix(): p.read_bytes()
        for p in second.path.rglob("*") if p.is_file()
    } == once


def test_a_toc_path_naming_no_file_fails_before_anything_is_written(config, catalog, flare):
    """Requirements §10's third POC defect, at the only point it can be refused.

    There, the missing entry sized as zero words, packed silently, and crashed the
    write pass -- *after* the previous output had already been deleted.
    """
    tree = converted_tree(config, flare, "10.5.1")
    (tree / "installation/installation-overvie.md").unlink()
    findings = FindingsRun("reframe")

    result = Reframer(config, catalog, findings=findings).reframe_one(
        flare, flare.versions["10.5.1"]
    )

    assert result.outcome is ReframeOutcome.FAILED
    assert codes(findings.all) == ["REFRAME_SELF_CHECK_FAILED"]
    assert "installation/installation-overvie.md" in findings.all[0].message
    target = config.reframed_path(flare.bu, flare.family, flare.slug, "10.5.1")
    assert not target.exists()
    assert not target.with_name(target.name + ".part").exists()


def test_a_topic_the_toc_never_lists_is_carried_through_and_named(config, catalog, flare):
    """Runtime Agent 5.13.0 has two, and one of them is the target of a live link.

    Stage 7 publishes the whole tree, so an untocked topic is *already* published.
    Dropping it would make Reframe delete live content as a side effect of a
    navigation gap -- so it is carried through as its own page, and warned about.
    """
    tree = converted_tree(config, flare, "10.5.1")
    (tree / "users-guide/stray.md").write_text(
        "---\ntitle: A Stray Topic\n---\n\n# A Stray Topic\n", encoding="utf-8"
    )
    findings = FindingsRun("reframe")

    result = Reframer(config, catalog, findings=findings).reframe_one(
        flare, flare.versions["10.5.1"]
    )

    assert result.outcome is ReframeOutcome.REFRAMED
    assert codes(findings.all) == ["REFRAME_TOPIC_UNTOCKED"]
    assert findings.all[0].severity is Severity.WARNING
    # Named from its own frontmatter title, like every other page (Phase 29).
    carried = result.path / "users-guide/a-stray-topic.md"
    assert carried.is_file()
    assert yaml.safe_load(split_frontmatter(carried.read_text(encoding="utf-8"))[0].strip("-\r\n")) == {
        "title": "A Stray Topic", "guide": UNNAVIGATED, "merged_from": 1,
    }
    # ...and it stays out of the navigation, because R3 only promises to preserve
    # what was in it. Carrying it through is not the same as inventing a TOC row.
    document = yaml.safe_load((result.path / "toc.yml").read_text(encoding="utf-8"))
    assert "stray" not in yaml.safe_dump(document)


def test_an_asset_of_any_shape_is_copied_through(config, catalog, flare):
    """The POC allowlisted two directory names and silently dropped the rest.

    Every reference into anything else was repathed onto a file that was not there,
    and counted as a rewritten link. The rule has to be structural: not a topic,
    not a regenerated sidecar, therefore an asset.
    """
    tree = converted_tree(config, flare, "10.5.1")
    (tree / "odd-place").mkdir()
    (tree / "odd-place/diagram.svg").write_bytes(b"<svg/>")
    (tree / "metadata.yml").write_text("version: 10.5.1\n", encoding="utf-8")

    result = Reframer(config, catalog).reframe_one(flare, flare.versions["10.5.1"])

    assert (result.path / "odd-place/diagram.svg").read_bytes() == b"<svg/>"
    assert (result.path / "metadata.yml").read_text(encoding="utf-8") == "version: 10.5.1\n"


# -- the input and the swap (C4) ----------------------------------------------


def test_the_input_tree_is_never_written_to(config, catalog, flare):
    """C4. The rule the stage's reversibility rests on, asserted on mtimes and bytes."""
    source = converted_tree(config, flare, "10.5.1")
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in sorted(source.rglob("*")) if p.is_file()}

    Reframer(config, catalog).reframe_one(flare, flare.versions["10.5.1"])

    assert {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in sorted(source.rglob("*")) if p.is_file()} == before


def test_a_stale_page_from_a_previous_merge_does_not_survive(config, catalog, flare):
    """The reason the build goes through `.part` and a swap rather than into place.

    A boundary rule that moves leaves the old page behind on a merge-in-place, so
    one topic ends up covered by two pages and both look current.
    """
    converted_tree(config, flare, "10.5.1")
    target = config.reframed_path(flare.bu, flare.family, flare.slug, "10.5.1")
    target.mkdir(parents=True)
    (target / "page-from-an-older-boundary.md").write_text("stale\n", encoding="utf-8")

    result = Reframer(config, catalog).reframe_one(flare, flare.versions["10.5.1"])

    assert result.outcome is ReframeOutcome.REFRAMED
    assert not (target / "page-from-an-older-boundary.md").exists()
    assert not target.with_name(target.name + ".part").exists()


# -- currency -----------------------------------------------------------------


def test_a_policy_edit_invalidates_an_otherwise_current_merge(config, catalog, flare):
    """Keying on the input alone is the failure this stage would hit constantly.

    The boundary rules exist to be tuned, so a `reframe.yaml` edit that left every
    tree reporting `current` would make the tuning loop silently a no-op.
    """
    converted_tree(config, flare, "10.5.1")
    catalog.state.set_version_metadata("tibco-flare-docs", "10.5.1", "convert_source_checksum", "abc123")
    reframer = Reframer(config, catalog)

    assert reframer.reframe_one(flare, flare.versions["10.5.1"]).outcome is ReframeOutcome.REFRAMED
    assert reframer.reframe_one(flare, flare.versions["10.5.1"]).outcome is ReframeOutcome.CURRENT

    config.reframe_path.write_text("defaults:\n  max_words: 6000\n", encoding="utf-8")
    config._reframe_cache = None
    tuned = Reframer(config, catalog)

    assert tuned.reframe_one(flare, flare.versions["10.5.1"]).outcome is ReframeOutcome.REFRAMED


def test_force_re_merges_a_current_version(config, catalog, flare):
    converted_tree(config, flare, "10.5.1")
    catalog.state.set_version_metadata("tibco-flare-docs", "10.5.1", "convert_source_checksum", "abc123")
    reframer = Reframer(config, catalog)
    reframer.reframe_one(flare, flare.versions["10.5.1"])

    assert reframer.reframe_one(flare, flare.versions["10.5.1"], force=True).outcome is (
        ReframeOutcome.REFRAMED
    )


def test_a_version_with_no_recorded_conversion_is_never_current(config, catalog, flare):
    """An empty checksum must not compare equal to an empty checksum.

    A standalone `--input` run records nothing, so both sides of the currency test
    are `""` -- and a stage that called that "unchanged" would refuse to run twice.
    """
    converted_tree(config, flare, "10.5.1")
    reframer = Reframer(config, catalog)

    assert reframer.reframe_one(flare, flare.versions["10.5.1"]).outcome is ReframeOutcome.REFRAMED
    assert reframer.reframe_one(flare, flare.versions["10.5.1"]).outcome is ReframeOutcome.REFRAMED


# -- the merged inventory (architecture.md §3.9.3, planning.md Phase 24) ------


def test_a_merge_records_what_the_merged_tree_holds(config, catalog, flare):
    """The third measurement across the row, and the one the stage exists to move."""
    converted_tree(config, flare, "10.5.1")
    target = config.reframed_path(flare.bu, flare.family, flare.slug, "10.5.1")

    result = Reframer(config, catalog).reframe_one(flare, flare.versions["10.5.1"])

    on_disk = [p for p in target.rglob("*") if p.is_file()]
    assert result.reframed_files == len(on_disk)
    assert result.reframed_md_files == len([p for p in on_disk if p.suffix == ".md"])
    version = catalog.get_version("tibco-flare-docs", "10.5.1")
    assert version.reframed_md_files == result.reframed_md_files
    assert version.reframed_files == result.reframed_files


def test_the_merged_markdown_count_is_the_page_count(config, catalog, flare):
    """Every merged page is one `.md` and nothing else in the tree writes one."""
    converted_tree(config, flare, "10.5.1")

    result = Reframer(config, catalog).reframe_one(flare, flare.versions["10.5.1"])

    assert result.reframed_md_files == result.pages


def test_the_total_exceeds_the_pages_by_the_artifacts_beside_them(config, catalog, flare):
    """Why the count is walked and not `len(built)` plus a constant."""
    converted_tree(config, flare, "10.5.1")

    result = Reframer(config, catalog).reframe_one(flare, flare.versions["10.5.1"])

    assert result.reframed_files > result.pages


def test_a_current_version_still_reports_its_merged_counts(config, catalog, flare):
    """Phase 24's whole complaint: the second run reported nothing where the first
    reported every page, which reads as "the merge produced nothing"."""
    converted_tree(config, flare, "10.5.1")
    catalog.state.set_version_metadata("tibco-flare-docs", "10.5.1", "convert_source_checksum", "abc123")
    reframer = Reframer(config, catalog)
    built = reframer.reframe_one(flare, flare.versions["10.5.1"])

    again = reframer.reframe_one(flare, flare.versions["10.5.1"])

    assert again.outcome is ReframeOutcome.CURRENT
    assert again.reframed_md_files == built.reframed_md_files
    assert again.reframed_files == built.reframed_files


def test_a_current_version_with_blank_columns_is_walked_anyway(config, catalog, flare):
    """A version merged before these columns existed reports `current` forever, so
    without the backfill it would stay blank for good -- §3.9.2's rule, third time.
    """
    converted_tree(config, flare, "10.5.1")
    catalog.state.set_version_metadata("tibco-flare-docs", "10.5.1", "convert_source_checksum", "abc123")
    reframer = Reframer(config, catalog)
    built = reframer.reframe_one(flare, flare.versions["10.5.1"])
    catalog.clear_reframe_inventory("tibco-flare-docs", "10.5.1")

    again = reframer.reframe_one(flare, flare.versions["10.5.1"])

    assert again.outcome is ReframeOutcome.CURRENT
    assert again.reframed_md_files == built.reframed_md_files
    version = catalog.get_version("tibco-flare-docs", "10.5.1")
    assert version.reframed_md_files == built.reframed_md_files
    assert version.reframed_files == built.reframed_files


# -- the TOC adapter seam -----------------------------------------------------


def test_the_shipped_schema_reads_what_stage_6a_writes():
    schema = DocsUrlSubfolderlist()
    document = yaml.safe_load(TOC)

    assert schema.matches(document)
    rows = [row for top in schema.parse(document) for row in top.walk()]
    assert [row.title for row in rows] == [
        "Installation", "Installation Overview", "User Guide",
    ]
    assert str(rows[1].path) == "installation/installation-overvie.md"


def test_a_fragment_round_trips_in_the_raw_form_the_toc_was_written_in():
    """`navigation._target` appends the anchor unencoded and case-preserved.

    Reframe rewrites this file, so reading it in any other form would re-emit 12.1%
    of Flare's TOC entries pointing somewhere subtly different.
    """
    document = yaml.safe_load('items:\n  - title: "T"\n    path: "a/b.md#Client-Credentials"\n')
    row = ItemsPathChildren().parse(document)[0]

    assert str(row.path) == "a/b.md"
    assert row.fragment == "Client-Credentials"
    assert row.target == "a/b.md#Client-Credentials"


def test_a_row_with_no_page_keeps_its_title_and_targets_nothing():
    document = yaml.safe_load('items:\n  - title: "Container"\n    children: []\n')
    row = ItemsPathChildren().parse(document)[0]

    assert row.path is None
    assert row.target == ""


def test_the_html_to_md_dialect_reads_url_and_subfolderlist_with_their_fragment():
    """Phase 36's reader: the same tree as the old one, under html-to-md's keys."""
    document = yaml.safe_load(
        'docs_list_title: "Online Help"\ndocs:\n  - title: "T"\n    url: "a/b.md"\n'
        '    subfolderlist:\n      - title: "S"\n        url: "a/b.md#Client-Credentials"\n'
    )
    schema = schema_for(document)
    row = schema.parse(document)[0]

    assert isinstance(schema, DocsUrlSubfolderlist)
    assert str(row.path) == "a/b.md"
    assert row.children[0].fragment == "Client-Credentials"
    assert row.children[0].target == "a/b.md#Client-Credentials"


def test_each_dialect_declines_the_other():
    """Neither reader half-reads the other's file: detection is by list key."""
    new = yaml.safe_load(TOC)
    old = yaml.safe_load(OLD_TOC)

    assert not ItemsPathChildren().matches(new)
    assert not DocsUrlSubfolderlist().matches(old)
    assert isinstance(schema_for(old), ItemsPathChildren)


def test_detection_declines_a_foreign_shape_rather_than_half_reading_it():
    assert schema_for({"toc": [{"label": "x"}]}) is None
    assert schema_for(None) is None
    assert registered_schemas() == ["docs-url-subfolderlist", "items-path-children"]


def test_a_configured_schema_that_is_not_registered_does_not_fall_back():
    """Detection would have matched this document. A wrong pin must still be loud."""
    assert schema_for(yaml.safe_load(TOC), "some-other-dialect") is None


def test_an_unreadable_toc_fails_the_version_and_names_it(config, catalog, flare):
    tree = config.output_path(flare.bu, flare.family, flare.slug, "10.5.1")
    tree.mkdir(parents=True)
    (tree / "toc.yml").write_text("navigation:\n  - label: Installation\n", encoding="utf-8")
    findings = FindingsRun("reframe")

    result = Reframer(config, catalog, findings=findings).reframe_one(
        flare, flare.versions["10.5.1"]
    )

    assert result.outcome is ReframeOutcome.FAILED
    assert codes(findings.all) == ["REFRAME_TOC_SCHEMA_UNKNOWN"]
    assert findings.all[0].severity is Severity.ERROR
    assert not config.reframed_path(flare.bu, flare.family, flare.slug, "10.5.1").exists()


def test_malformed_yaml_is_a_finding_and_not_a_traceback(config, catalog, flare):
    tree = config.output_path(flare.bu, flare.family, flare.slug, "10.5.1")
    tree.mkdir(parents=True)
    (tree / "toc.yml").write_text("items:\n  - title: [unclosed\n", encoding="utf-8")
    findings = FindingsRun("reframe")

    result = Reframer(config, catalog, findings=findings).reframe_one(
        flare, flare.versions["10.5.1"]
    )

    assert result.outcome is ReframeOutcome.FAILED
    assert codes(findings.all) == ["REFRAME_TOC_SCHEMA_UNKNOWN"]


# -- policy and R1.4 pinning --------------------------------------------------


def test_a_product_block_overrides_one_key_and_inherits_the_rest():
    reframe = {"defaults": {"max_words": 3000}, "products": {"tibco-flare-docs": {"pin_layout_to": "10.5.1"}}}
    policy = policy_for(reframe, "tibco-flare-docs")

    assert policy.max_words == 3000
    assert policy.pin_layout_to == "10.5.1"
    assert policy_for(reframe, "other").pin_layout_to == ""


def test_the_policy_key_tracks_every_field_that_changes_the_output():
    base = ReframePolicy()

    assert base.key == ReframePolicy().key
    assert base.key != ReframePolicy(max_words=4000).key
    assert base.key != ReframePolicy(pin_layout_to="10.5.1").key
    assert base.key != ReframePolicy(toc_schema="items-path-children").key


def test_the_policy_key_tracks_the_packer_algorithm_and_not_only_the_config():
    """Phase 28. The digest is built from config fields, and a code change that
    moves every page boundary touches none of them -- so without the algorithm
    constant every merged tree on disk reports CURRENT and keeps its old layout
    for good, re-cut only by a `--force` somebody happens to remember."""
    from docushift.reframe import policy as policy_module

    base = ReframePolicy().key
    original = policy_module._ALGORITHM
    try:
        policy_module._ALGORITHM = original + 1
        assert ReframePolicy().key != base
    finally:
        policy_module._ALGORITHM = original
    assert ReframePolicy().key == base


def test_a_shipped_config_reproduces_the_measured_baseline(repo_root):
    """`config/reframe.yaml` is documentation as much as configuration.

    The cap is the value requirements §6 was measured at, so a change here that is
    not a deliberate re-baselining moves 113 pages without anybody deciding to.
    """
    shipped = ConfigManager(root_dir=repo_root).load_reframe()

    assert shipped["defaults"]["max_words"] == 3000
    assert shipped["products"]["tibco-enterprise-message-service"]["pin_layout_to"] == "10.5.1"


def test_one_eligible_version_needs_no_pin(config, catalog, flare):
    converted_tree(config, flare, "10.5.1")
    findings = FindingsRun("reframe")

    Reframer(config, catalog, findings=findings).reframe_one(flare, flare.versions["10.5.1"])

    assert codes(findings.all) == []


def test_two_eligible_versions_with_no_pin_are_warned_about(config, catalog, flare):
    """R1.4, and the reference product is the case: EMS has six eligible versions.

    Counted off the catalog rather than off disk, because the second version not
    being converted yet is exactly when pinning is still cheap to decide.
    """
    flare.versions["10.5.0"] = make_version("tibco-flare-docs", "10.5.0", engine=SourceEngine.FLARE)
    catalog.merge_fetch_results([flare])
    reloaded = catalog.get_product("tibco-flare-docs")
    converted_tree(config, reloaded, "10.5.1")
    findings = FindingsRun("reframe")

    Reframer(config, catalog, findings=findings).reframe_one(
        reloaded, reloaded.versions["10.5.1"]
    )

    assert codes(findings.all) == ["REFRAME_LAYOUT_UNPINNED"]
    assert findings.all[0].severity is Severity.WARNING


def test_a_pinned_product_is_not_warned_about(config, catalog, flare):
    flare.versions["10.5.0"] = make_version("tibco-flare-docs", "10.5.0", engine=SourceEngine.FLARE)
    catalog.merge_fetch_results([flare])
    reloaded = catalog.get_product("tibco-flare-docs")
    converted_tree(config, reloaded, "10.5.1")
    config.reframe_path.parent.mkdir(parents=True, exist_ok=True)
    config.reframe_path.write_text(
        'products:\n  tibco-flare-docs:\n    pin_layout_to: "10.5.1"\n', encoding="utf-8"
    )
    findings = FindingsRun("reframe")

    Reframer(config, catalog, findings=findings).reframe_one(
        reloaded, reloaded.versions["10.5.1"]
    )

    assert codes(findings.all) == []


# -- the selection ------------------------------------------------------------


def test_a_mixed_selection_reports_both_outcomes_and_merges_only_flare(
    config, catalog, flare, product, version
):
    converted_tree(config, flare, "10.5.1")

    stats = Reframer(config, catalog).reframe_many(
        [(flare, flare.versions["10.5.1"]), (product, version)]
    )

    assert stats.count(ReframeOutcome.REFRAMED) == 1
    assert stats.count(ReframeOutcome.NOT_FLARE) == 1
    assert stats.topics == 3
    assert stats.failures == []


def test_toc_entry_walk_is_depth_first_in_document_order():
    tree = TocEntry("a", children=[TocEntry("b", children=[TocEntry("c")]), TocEntry("d")])

    assert [entry.title for entry in tree.walk()] == ["a", "b", "c", "d"]


# -- R1: the packer ------------------------------------------------------------
#
# The packer never opens a file, so every rule below is asserted against a TOC tree
# and a dict of word counts. That separation is the point: a boundary that moved
# because a renderer changed would be a bug nobody could locate.


def node(title: str, path: str | None = None, *children: TocEntry) -> TocEntry:
    return TocEntry(title, PurePosixPath(path) if path else None, children=list(children))


def sized(**words: int):
    """`words_of` over a `{a__b: count}` mapping -- `__` is `/`, `_` is `-`."""
    by_path = {name.replace("__", "/").replace("_", "-") + ".md": count for name, count in words.items()}
    return lambda path: by_path[str(path)]


def layout(pages) -> list[list[str]]:
    return [[str(topic.source) for topic in page.topics] for page in pages]


def test_a_subtree_that_fits_under_the_cap_becomes_one_page():
    roots = [node("Guide", "g/a.md", node("Child", "g/b.md"), node("Other", "g/c.md"))]

    pages = pack(roots, sized(g__a=10, g__b=10, g__c=10), 3000)

    assert layout(pages) == [["g/a.md", "g/b.md", "g/c.md"]]
    assert pages[0].guide == "Guide"


def test_top_level_items_are_hard_boundaries_however_much_room_is_left():
    """R1.1. Two guides under a 3000-word cap holding 20 words between them.

    The cap is a cap and never a target (R1.2), so there is no pressure anywhere in
    the packer to fill a page -- which is what keeps a merged page comprehensible
    rather than merely large.
    """
    roots = [node("First", "g/a.md"), node("Second", "g/b.md")]

    pages = pack(roots, sized(g__a=10, g__b=10), 3000)

    assert layout(pages) == [["g/a.md"], ["g/b.md"]]
    assert [page.guide for page in pages] == ["First", "Second"]


def test_the_cap_refuses_a_join_and_the_run_carries_on_after_it():
    roots = [node("Guide", "g/a.md", node("B", "g/b.md"), node("C", "g/c.md"))]

    pages = pack(roots, sized(g__a=60, g__b=60, g__c=10), 100)

    assert layout(pages) == [["g/a.md"], ["g/b.md", "g/c.md"]]


def test_a_topic_bigger_than_the_cap_becomes_an_oversized_page_of_its_own():
    """R1.3 forbids splitting a topic body, so the cap has to yield here.

    Requirements §6's reference baseline records a 3,533-word page under a 3,000
    cap for exactly this reason; a packer that "fixed" it would be splitting prose
    at a word offset.
    """
    roots = [node("Guide", "g/a.md", node("B", "g/big.md"), node("C", "g/c.md"))]

    pages = pack(roots, sized(g__a=10, g__big=5000, g__c=10), 100)

    assert layout(pages) == [["g/a.md"], ["g/big.md"], ["g/c.md"]]
    assert pages[1].words == 5000


def test_a_page_never_spans_two_source_directories():
    """R4.2, enforced at the join rather than checked afterwards.

    Both topics fit the cap with room to spare, so only the directory rule can be
    what separates them. It matters because R4.1 puts the page in its first topic's
    directory, and every relative asset path on it resolves from there.
    """
    roots = [node("Guide", "g/a.md", node("B", "h/b.md"))]

    pages = pack(roots, sized(g__a=10, h__b=10), 3000)

    assert layout(pages) == [["g/a.md"], ["h/b.md"]]


def test_a_page_closed_inside_a_subtree_keeps_its_place_in_reading_order():
    """The proof-of-concept's ordering defect, pinned.

    It appended to one shared list as the recursion unwound, so an overflowing
    child subtree's pages landed *before* the page holding their own parent's
    topic -- which reads earlier. The sections of a guide then jumped around it,
    which is precisely the thing a reader notices.
    """
    roots = [node("Guide", "g/a.md", node("B", "g/b.md", node("C", "g/c.md")), node("D", "g/d.md"))]

    pages = pack(roots, sized(g__a=10, g__b=90, g__c=90, g__d=10), 100)

    assert layout(pages) == [["g/a.md"], ["g/b.md"], ["g/c.md"], ["g/d.md"]]


def test_a_topic_listed_under_two_guides_gets_a_copy_in_each():
    """GridServer 7.2.0 lists `Typographical_Conventions.md` three times.

    This used to be packed once, with the later rows pointing at the first
    guide's page. That was right while a URL was a file path -- one file, one
    address, two ways to navigate to it. Phase 29 made the URL the TOC chain, so
    the second guide's row then resolved to an address sitting under the *first*
    guide, and a reader who navigated through B was told they were in A. A copy
    per guide is the only shape the new model can express.

    Measured corpus-wide: 36 extra copies, 32 of them DataSynapse (out of scope),
    so 4 pages in scope -- EMS 10.4.0 and 10.4.1.
    """
    roots = [
        node("First", "g/a.md", node("Shared", "g/s.md")),
        node("Second", "g/b.md", node("Shared", "g/s.md")),
    ]

    pages = pack(roots, sized(g__a=10, g__b=10, g__s=10), 3000)
    placements: dict[int, tuple] = {}
    located = assign(pages, None, placements)
    relocate(pages, roots)

    assert layout(pages) == [["g/a.md", "g/s.md"], ["g/b.md", "g/s.md"]]

    merged = retarget(roots, located, placements)
    # Each guide's row resolves to that guide's own copy, not to the other's.
    assert merged["docs"][0]["subfolderlist"] == [{"title": "Shared", "url": "first.md#shared"}]
    assert merged["docs"][1]["subfolderlist"] == [{"title": "Shared", "url": "second.md#shared"}]


def test_a_topic_listed_twice_inside_one_guide_is_still_packed_once():
    """Within a guide the second listing is a cross-reference rather than a
    second placement: one page, and the later row points at it."""
    roots = [node("Guide", "g/a.md", node("Shared", "g/s.md"), node("Again", "g/s.md"))]

    pages = pack(roots, sized(g__a=10, g__s=10), 3000)
    placements: dict[int, tuple] = {}
    located = assign(pages, None, placements)

    assert layout(pages) == [["g/a.md", "g/s.md"]]
    assert retarget(roots, located, placements)["docs"][0]["subfolderlist"] == [
        {"title": "Shared", "url": "g/guide.md#shared"},
        {"title": "Again", "url": "g/guide.md#shared"},
    ]


def levels(pages) -> list[list[int]]:
    return [[topic.level for topic in page.topics] for page in pages]


def test_an_overflowing_parent_stands_alone_rather_than_taking_some_children():
    """Phase 28's discriminator, and the whole reason for the repack.

    Under the greedy rule this was `[a, b] | [c]` -- a page holding a parent and
    one of its two children, with the other child stranded on a page of its own.
    Nothing about that page could be given an H1, because no topic on it was the
    thing the page was about. Now the parent stands alone and the children, which
    are siblings of each other, share a page.
    """
    roots = [node("Guide", "g/a.md", node("B", "g/b.md"), node("C", "g/c.md"))]

    pages = pack(roots, sized(g__a=10, g__b=10, g__c=10), 25)

    assert layout(pages) == [["g/a.md"], ["g/b.md", "g/c.md"]]


def test_a_page_is_whole_subtrees_of_one_parent_and_never_a_cut_across_siblings():
    """The invariant the repack exists to establish, stated directly.

    Measured before it: 27 of ActiveSpaces' 46 merged pages and 67 of EMS' 124
    held topics from more than one parent. The check is on the page's *roots* --
    its topics at the shallowest level -- because a page that is one whole subtree
    legitimately holds a node and its own children, which is the point.
    """
    roots = [node(
        "Guide", "g/root.md",
        node("Left", "g/left.md", node("L1", "g/l1.md"), node("L2", "g/l2.md")),
        node("Right", "g/right.md", node("R1", "g/r1.md")),
    )]
    parent = {"g/l1.md": "g/left.md", "g/l2.md": "g/left.md", "g/r1.md": "g/right.md",
              "g/left.md": "g/root.md", "g/right.md": "g/root.md", "g/root.md": None}

    pages = pack(roots, sized(g__root=10, g__left=40, g__l1=40, g__l2=40,
                              g__right=40, g__r1=40), 100)

    assert layout(pages) == [
        ["g/root.md"], ["g/left.md"], ["g/l1.md", "g/l2.md"], ["g/right.md", "g/r1.md"],
    ]
    for page in pages:
        top = min(topic.level for topic in page.topics)
        rooted = [topic for topic in page.topics if topic.level == top]
        assert len({parent[str(topic.source)] for topic in rooted}) == 1


def test_a_subtree_that_fits_but_spans_two_directories_falls_to_the_second_rule():
    """R4.2 has to be part of "may this be one page", not a check afterwards.

    Words alone would collapse this whole subtree into one page, and
    `audit._directories` would then discard the entire merged tree.
    """
    roots = [node("Guide", "g/a.md", node("B", "h/b.md"), node("C", "h/c.md"))]

    pages = pack(roots, sized(g__a=10, h__b=10, h__c=10), 3000)

    assert layout(pages) == [["g/a.md"], ["h/b.md", "h/c.md"]]


def test_heading_level_follows_toc_depth_within_a_page():
    roots = [node("Guide", "g/a.md",
                  node("B", "g/b.md", node("C", "g/c.md", node("D", "g/d.md"))))]

    pages = pack(roots, sized(g__a=10, g__b=10, g__c=10, g__d=10), 3000)

    assert layout(pages) == [["g/a.md", "g/b.md", "g/c.md", "g/d.md"]]
    assert levels(pages) == [[1, 2, 3, 4]]


def test_a_toc_row_that_contributes_no_topic_leaves_no_hole_in_the_levels():
    """Depth is counted in what is emitted, not in what the TOC happens to hold.

    A bare container row carries no topic of its own, and counting it anyway put
    EMS' `Appendix B` page at `#` followed by `####`. That is Phase 27's defect
    reintroduced one stage later, so it gets Phase 27's rule.
    """
    inner = node("Leaf", "g/leaf.md")
    container = TocEntry(title="Container", path=None, children=[inner])
    roots = [node("Guide", "g/a.md", container)]

    pages = pack(roots, sized(g__a=10, g__leaf=10), 3000)

    assert layout(pages) == [["g/a.md", "g/leaf.md"]]
    assert levels(pages) == [[1, 2]]


def test_a_chain_deeper_than_six_flattens_onto_h6_rather_than_overflowing():
    """GFM has no `h7`. Flattening repeats a level; it never *skips* one, so
    `design.md` invariant 14 survives. Measured need: 10 of ActiveSpaces' 324
    topics and 4 of EMS' 1,441."""
    deep = node("G", "g/1.md", node("2", "g/2.md", node("3", "g/3.md", node(
        "4", "g/4.md", node("5", "g/5.md", node("6", "g/6.md", node("7", "g/7.md")))))))

    pages = pack([deep], sized(**{f"g__{n}": 1 for n in range(1, 8)}), 3000)

    assert levels(pages) == [[1, 2, 3, 4, 5, 6, 6]]


def test_a_later_sibling_subtree_sits_one_level_below_the_first():
    """Two whole subtrees on one page cannot both be H1.

    The second drops a level, and its own children drop with it -- which is what
    stops a parent and its child arriving at the same level.
    """
    roots = [node("Guide", "g/root.md",
                  node("B", "g/b.md", node("B1", "g/b1.md")),
                  node("C", "g/c.md", node("C1", "g/c1.md")))]

    pages = pack(roots, sized(g__root=90, g__b=10, g__b1=10, g__c=10, g__c1=10), 100)

    assert layout(pages) == [["g/root.md"], ["g/b.md", "g/b1.md", "g/c.md", "g/c1.md"]]
    #        b=H1  b1=H2      c=H2  c1=H3
    assert levels(pages) == [[1], [1, 2, 2, 3]]


def test_carry_makes_one_single_topic_page_per_untocked_file():
    pages = carry([PurePosixPath("g/x.md")], lambda p: "Stray", lambda p: 7)

    assert layout(pages) == [["g/x.md"]]
    assert (pages[0].guide, pages[0].words) == (UNNAVIGATED, 7)


# -- R1.4: the pinned layout ---------------------------------------------------
#
# Phase 26. Every test here is the same shape: pack a reference, then project a
# version that differs from it, and assert the difference did not move a boundary.


def pinned(roots, words_of, max_words=3000, keep_separate=()):
    """The reference half of a pin: pack, name, and take the layout as `project` wants it."""
    pages = pack(roots, words_of, max_words, keep_separate)
    assign(pages)
    return layout_of(pages)


def test_a_projected_version_reuses_the_reference_grouping_and_not_its_own_sizes():
    """The defect Phase 26 exists for, at the smallest size that shows it.

    `g/b` grows past the cap between the two versions. Packed on its own the
    version would close a page early and every boundary after it would shift;
    projected, the grouping is the reference's and the page is simply oversized,
    which is the same thing R1.3 already does to a single large topic.
    """
    roots = [node("Guide", "g/a.md", node("B", "g/b.md"), node("C", "g/c.md"))]
    reference = pinned(roots, sized(g__a=10, g__b=10, g__c=10))

    pages = project(reference, roots, sized(g__a=10, g__b=9000, g__c=10), 3000)

    assert layout(pages) == [["g/a.md", "g/b.md", "g/c.md"]]
    assert pack(roots, sized(g__a=10, g__b=9000, g__c=10), 3000) != pages


def test_a_topic_the_reference_does_not_have_gets_its_own_page():
    """R1.4 covers topics missing *from* a version, and says nothing about new ones.

    Joining one onto a projected page would move that page's boundary and un-pin
    the version, so a new topic is packed by the normal rule and never reaches in.
    """
    reference = pinned([node("Guide", "g/a.md", node("C", "g/c.md"))], sized(g__a=10, g__c=10))
    roots = [node("Guide", "g/a.md", node("B", "g/b.md"), node("C", "g/c.md"))]

    pages = project(reference, roots, sized(g__a=10, g__b=10, g__c=10), 3000)

    assert layout(pages) == [["g/a.md", "g/c.md"], ["g/b.md"]]


def test_a_reference_page_whose_topics_are_all_absent_is_simply_omitted():
    reference = pinned(
        [node("First", "g/a.md"), node("Second", "g/b.md")], sized(g__a=10, g__b=10)
    )

    pages = project(reference, [node("First", "g/a.md")], sized(g__a=10), 3000)

    assert layout(pages) == [["g/a.md"]]


def test_a_projected_page_keeps_the_reference_name_when_its_first_topic_is_gone():
    """Otherwise R4.1 renames the page after the surviving second topic.

    Same topics, same grouping, different URL -- measured on ActiveSpaces as two
    pages per version, which is two broken cross-version links for no editorial
    reason. `assign` leaves a page `project` has already named.
    """
    roots = [node("Guide", "g/a.md", node("B", "g/b.md"))]
    reference = pinned(roots, sized(g__a=10, g__b=10))

    pages = project(reference, [node("Guide", "g/b.md")], sized(g__b=10), 3000)
    assign(pages)

    # The reference named this `g/guide.md` after its first topic's title; the
    # version that lost that topic keeps the name rather than being renamed
    # after "B".
    assert [str(page.path) for page in pages] == ["g/guide.md"]


def test_a_new_topic_cannot_take_a_name_a_projected_page_wants():
    """The pinned names are reserved before any of them is reached, not as they are.

    Without the pre-pass the new `g/a.md` page -- which sorts first in this
    version's reading order -- would claim `g/a.md` and push the projected page
    that owns that URL onto `g/a-2.md`.
    """
    reference = pinned([node("Guide", "g/a.md")], sized(g__a=10))
    # A topic new to this version, sorting first in its reading order.
    roots = [node("New", "g/new-topic.md"), node("Guide", "g/a.md")]

    pages = project(reference, roots, lambda path: 10, 3000)
    assign(pages)

    assert [str(page.path) for page in pages] == ["g/new.md", "g/guide.md"]


def test_projection_reads_in_this_versions_order_but_sections_in_the_references():
    """Two decisions at once, because they pull in opposite directions.

    A version that genuinely reordered its TOC should read in its own order, so the
    *pages* follow this version. Within a page the reference's order is kept, so two
    versions of one page correspond section by section rather than merely as a set.
    """
    reference = pinned(
        [node("First", "g/a.md", node("B", "g/b.md")), node("Second", "g/c.md")],
        sized(g__a=10, g__b=10, g__c=10),
    )
    roots = [node("Second", "g/c.md"), node("First", "g/b.md", node("A", "g/a.md"))]

    pages = project(reference, roots, sized(g__a=10, g__b=10, g__c=10), 3000)

    assert layout(pages) == [["g/c.md"], ["g/a.md", "g/b.md"]]


def test_keep_separate_still_takes_a_topic_out_of_a_projected_page():
    """20e is a writer's decision and outranks the pin, which is a diffability one."""
    roots = [node("Guide", "g/a.md", node("B", "g/b.md"))]
    reference = pinned(roots, sized(g__a=10, g__b=10))

    pages = project(reference, roots, sized(g__a=10, g__b=10), 3000, keep_separate=["g/b.md"])

    assert layout(pages) == [["g/a.md"], ["g/b.md"]]


# -- R2: names and anchors -----------------------------------------------------


def test_a_page_is_named_after_its_first_topics_title_and_placed_beside_it():
    """Phase 29: from the **title**, not the source stem, because the filename is
    the URL. MadCap truncates its own filenames at 20 characters, and 428 of
    1,700 merged pages published a name that disagreed with their own title."""
    pages = pack([node("Getting Started", "g/deep/gettin-started-2.md")], lambda p: 10, 3000)

    assign(pages)

    assert str(pages[0].path) == "g/deep/getting-started.md"


def test_a_page_falls_back_to_its_stem_when_the_title_is_really_a_filename():
    """`Know_the_Basics` as a TOC "title" is a stem somebody forgot to write out,
    and the stem is then the honest source -- with its edit history stripped."""
    pages = pack([node("Know_the_Basics", "g/1__Know_the_Basics_updated.md")], lambda p: 10, 3000)

    assign(pages)

    assert str(pages[0].path) == "g/know-the-basics.md"


def test_an_anchor_is_the_platforms_slug_of_the_heading_not_of_the_filename():
    """Phase 29. AEM ignores what we write and slugs the heading text itself.

    The old rule slugged `topic.source.stem`. Measured across the merged corpus,
    the two answers agreed for 7,153 of 18,657 anchors -- so ~11,500 fragments,
    out of the 94% of internal links that carry one, named something the platform
    was never going to create.
    """
    topics = [Topic("Configuring SSL", PurePosixPath("g/cfg_ssl_updated.md"), 10)]
    pages = [Page("Guide", topics)]

    assign(pages, lambda topic: ["Configuring SSL"])

    assert list(pages[0].anchors.values()) == ["configuring-ssl"]


def test_a_repeated_heading_is_numbered_the_way_the_platform_numbers_it():
    """First occurrence bare, later ones `-1`, `-2`, in document order.

    400 of 1,700 merged pages repeat a heading -- one has three "Location", three
    "Syntax" and three "Examples".
    """
    topics = [Topic(f"t{n}", PurePosixPath(f"g/t{n}.md"), 10) for n in range(3)]
    pages = [Page("Guide", topics)]

    assign(pages, lambda topic: ["Location"])

    assert list(pages[0].anchors.values()) == ["location", "location-1", "location-2"]


def test_a_sub_heading_competes_for_the_same_anchor_as_a_topic_heading():
    """Why `headings_of` returns every heading and not just the topic's own.

    The first topic's `## Location` takes `#location`, so the second topic's own
    `# Location` is the platform's *second* one and becomes `location-1`. Numbering
    only the topic headings would have predicted `location` and been wrong.
    """
    topics = [
        Topic("Install", PurePosixPath("g/install.md"), 10),
        Topic("Location", PurePosixPath("g/location.md"), 10),
    ]
    pages = [Page("Guide", topics)]
    rendered = {"g/install.md": ["Install", "Location"], "g/location.md": ["Location"]}

    assign(pages, lambda topic: rendered[str(topic.source)])

    assert list(pages[0].anchors.values()) == ["install", "location-1"]


def test_two_pages_with_one_title_are_told_apart_by_their_folder():
    """The spec asked for a doc-set-wide name and a parent prefix on every
    generic one, which was right when folders were flat. With the TOC chain
    restored as directories, `/installing/overview` and `/upgrading/overview`
    are already distinct addresses that read correctly -- and prefixing would
    publish `/installing/installing-overview`.
    """
    roots = [
        node("Installing", "g/a.md", node("Overview", "g/b.md")),
        node("Upgrading", "g/c.md", node("Overview", "g/d.md")),
    ]

    # A cap the parent-plus-child subtree exceeds, so each section splits into
    # its own page and its child's -- which is what puts two "Overview" pages in
    # one doc set.
    pages = pack(roots, lambda p: 10, 15)
    assign(pages)
    relocate(pages, roots)

    assert [str(page.path) for page in pages] == [
        "installing.md", "installing/overview.md",
        "upgrading.md", "upgrading/overview.md",
    ]


def test_a_collision_inside_one_folder_falls_back_to_a_number():
    """Same title, same parent, so the same folder: there is no prose left to
    tell them apart and nothing the chain can do about it."""
    roots = [node("Section", "g/s.md", node("Detail", "g/a.md"), node("Detail", "g/b.md"))]

    pages = pack(roots, lambda p: 10, 15)
    assign(pages)
    relocate(pages, roots)

    assert [str(page.path) for page in pages] == [
        "section.md", "section/detail.md", "section/detail-2.md",
    ]


# -- R2.1: the heading shift ---------------------------------------------------


def test_at_the_default_level_the_first_h1_becomes_the_anchored_h2():
    """The `level=2` default: what every caller with no tree to consult still
    gets -- `carry`'s untocked pages and `project`'s new topics."""
    body = "# Top\n\nprose\n\n## Sub\n\n### Deeper\n"

    shifted, added = shift_headings(body, "Ignored")

    assert shifted == "## Top\n\nprose\n\n### Sub\n\n#### Deeper\n"
    # Zero since Phase 29. The `<a id>` marker used to cost two tokens; moving a
    # heading costs none, because `#` and `######` are one token either way.
    assert added == 0


def test_a_topic_takes_the_level_its_page_gives_it_and_its_own_headings_follow():
    """Phase 28. A topic three deep in its page carries its own headings down
    with it, so the page reads as one document rather than as a flat list."""
    body = "# Top\n\nprose\n\n## Sub\n"

    shifted, added = shift_headings(body, "Ignored", 3)

    assert shifted == "### Top\n\nprose\n\n#### Sub\n"
    # Unchanged by the offset: `#` and `######` are one token either way, which is
    # what keeps `audit._words`' strict equality true at every level.
    assert added == 0


def test_a_topic_at_the_deepest_level_flattens_rather_than_overflowing():
    shifted, added = shift_headings("# Top\n\n## Sub\n", "Ignored", 6)

    assert shifted == "###### Top\n\n###### Sub\n"
    assert added == 0


def test_a_synthesized_heading_is_written_at_the_topics_own_level():
    shifted, added = shift_headings("prose\n", "Two Words", 4)

    assert shifted == "#### Two Words\n\nprose\n"
    # The hashes (1) plus the title's own two tokens. One token at every level, so
    # this figure does not move with the offset either.
    assert added == 1 + 2


def test_a_heading_shift_stops_at_h6_rather_than_emitting_seven_hashes():
    """Not exercised by the reference corpus, which is H1-H4. A set that is deeper
    would otherwise emit `#######`, which GFM renders as literal hashes."""
    shifted, _ = shift_headings("# Top\n\n###### Deep\n", "Ignored")

    assert "\n###### Deep\n" in shifted
    assert "#######" not in shifted


def test_a_topic_with_no_h1_gets_one_synthesized_from_its_toc_title():
    shifted, added = shift_headings("just prose\n", "Release Notes")

    assert shifted == "## Release Notes\n\njust prose\n"
    assert added == 1 + 2  # the `##` and the two-word title


def test_a_hash_comment_inside_a_fence_is_not_a_heading():
    """Requirements §7's latent corruption in the POC, which scanned the raw body.

    The `# Install the broker` line precedes the real H1, so the POC would have
    anchored *it* -- the topic's identity would have become a line of shell. The
    reference corpus has zero of these, which is why the POC never showed it.
    """
    body = "```bash\n# Install the broker\nmake install\n```\n\n# Installation\n"

    shifted, _ = shift_headings(body, "Ignored")

    assert "```bash\n# Install the broker\n" in shifted
    assert "\n\n## Installation" in shifted


# -- R4: links and assets ------------------------------------------------------


@pytest.fixture
def linked():
    """Two pages over three topics, plus an asset and an unclaimed topic on disk."""
    here = Page("G", [Topic("A", PurePosixPath("g/a.md"), 10), Topic("B", PurePosixPath("g/b.md"), 10)])
    # `h/c.md` is deliberately the *second* topic of its page, so a rewritten
    # cross-page link is visibly not the path that was already there.
    there = Page("H", [Topic("Other Topics", PurePosixPath("h/other.md"), 10),
                       Topic("C", PurePosixPath("h/c.md"), 10)])
    located = assign([here, there])
    existing = frozenset(
        PurePosixPath(p)
        for p in ("g/a.md", "g/b.md", "h/other.md", "h/c.md", "g/img.png", "g/ghost.md")
    )
    return here, located, existing


def rewrite(body: str, linked, counts: LinkCounts) -> str:
    here, located, existing = linked
    return rewrite_links(body, PurePosixPath("g/a.md"), here.path, located, existing, counts)


def test_a_link_onto_the_same_merged_page_becomes_a_bare_fragment(linked):
    counts = LinkCounts()

    assert rewrite("see [B](b.md).", linked, counts) == "see [B](#b)."
    assert (counts.checked, counts.intra) == (1, 1)


def test_a_link_onto_another_page_is_repathed_and_keeps_an_anchor(linked):
    counts = LinkCounts()

    assert rewrite("see [C](../h/c.md).", linked, counts) == "see [C](../h/other-topics.md#c)."
    assert counts.inter == 1


def test_an_asset_reference_is_recomputed_from_the_new_page(linked):
    counts = LinkCounts()

    assert rewrite('<img src="img.png">', linked, counts) == '<img src="img.png">'
    assert counts.asset == 1


def test_a_target_that_was_already_missing_is_left_alone_and_tolerated(linked):
    """Requirements §8: the 92 `.html` references into a sibling resources tree.

    It pointed at nothing before the merge and points at the same nothing after, so
    repathing it would only move a broken link somewhere less obvious -- and failing
    on it would make Reframe fail on a defect Stage 6 introduced.
    """
    counts = LinkCounts()

    assert rewrite("see [X](../elsewhere/x.html).", linked, counts) == "see [X](../elsewhere/x.html)."
    assert (counts.unresolved, counts.orphaned) == (1, 0)


def test_a_topic_that_exists_but_belongs_to_no_page_is_newly_broken(linked):
    """The only breakage the merge itself can create, and what §6 is measured on."""
    counts = LinkCounts()

    rewrite("see [G](ghost.md).", linked, counts)

    assert (counts.orphaned, counts.unresolved) == (1, 0)


def test_external_rooted_and_fragment_references_are_never_touched(linked):
    counts = LinkCounts()
    body = "[a](https://example.com/x.md) [b](/rooted/x.md) [c](#section) [d](mailto:x@y.z)"

    assert rewrite(body, linked, counts) == body
    assert counts.checked == 0


def test_a_link_inside_a_fence_or_a_code_span_is_not_rewritten(linked):
    """The mask preserves offsets, so a match in the mask is a span in the original.

    A sample showing `[B](b.md)` is documentation *about* a link, and rewriting it
    to `#b` would make the sample wrong for every reader who copied it.
    """
    counts = LinkCounts()
    body = "literal `[B](b.md)` and\n\n```\n[B](b.md)\n```\n"

    assert rewrite(body, linked, counts) == body
    assert counts.checked == 0


def test_a_reference_definition_is_rewritten_like_an_inline_link(linked):
    counts = LinkCounts()

    assert rewrite("[ref]: b.md\n", linked, counts) == "[ref]: #b\n"


# -- R7: frontmatter, and C5 at the grain it is decided at ----------------------


def test_a_title_containing_a_quote_produces_valid_frontmatter():
    """The POC interpolated the title into `"..."` and produced an unparseable file."""
    page = Page("G", [Topic('The "Big" One', PurePosixPath("g/a.md"), 2)])
    located = assign([page])

    text, _ = render(
        page, lambda p: "# Heading\n", located, frozenset({PurePosixPath("g/a.md")}), LinkCounts()
    )

    assert yaml.safe_load(split_frontmatter(text)[0].strip("-\r\n")) == {
        "title": 'The "Big" One', "guide": "G", "merged_from": 1,
    }


def test_rendering_the_same_page_twice_produces_the_same_bytes():
    """C5. The stage-level statement of the same rule is the `--force` re-run."""
    page = Page("G", [Topic("A", PurePosixPath("g/a.md"), 2), Topic("B", PurePosixPath("g/b.md"), 2)])
    located = assign([page])
    existing = frozenset({PurePosixPath("g/a.md"), PurePosixPath("g/b.md")})
    read = {"g/a.md": "# A\n\n[B](b.md)\n", "g/b.md": "# B\n"}

    once = render(page, lambda p: read[str(p)], located, existing, LinkCounts())
    twice = render(page, lambda p: read[str(p)], located, existing, LinkCounts())

    assert once == twice


def test_a_carried_topic_takes_its_title_from_its_own_frontmatter():
    """The only place the body's metadata wins: there is no TOC row to ask."""
    assert title_of("---\ntitle: Stray\n---\n\nbody\n", "fallback") == "Stray"
    assert title_of("no frontmatter\n", "fallback") == "fallback"
    assert title_of("---\ntitle: [unclosed\n---\n", "fallback") == "fallback"


# -- §6: the acceptance checks -------------------------------------------------
#
# Every check is asserted by making it fail. A self-validation that has only ever
# been seen passing is a self-validation nobody has tested.


@pytest.fixture
def merged():
    """A clean two-topic merge: the pages, their `located` map, and the TOC."""
    pages = [
        Page("Guide", [Topic("A", PurePosixPath("g/a.md"), 10), Topic("B", PurePosixPath("g/b.md"), 10)])
    ]
    located = assign(pages)
    roots = [node("Guide", "g/a.md", node("B", "g/b.md"))]
    return pages, located, roots


def check(merged, **overrides) -> list[str]:
    pages, located, roots = merged
    kwargs = {"words_in": 20, "words_out": 24, "added": 4, "counts": LinkCounts()}
    kwargs.update(overrides)
    return audit(pages, located, roots, **kwargs)


def test_a_clean_merge_reports_nothing(merged):
    assert check(merged) == []


def test_word_conservation_is_an_equality_and_not_a_tolerance(merged):
    """One token adrift is content that moved or vanished. A tolerance hides that."""
    failures = check(merged, words_out=25)

    assert len(failures) == 1
    assert failures[0].startswith("word conservation:")
    assert "difference 1" in failures[0]


def test_a_repeated_anchor_on_one_page_is_caught(merged):
    pages, _, _ = merged
    pages[0].anchors[PurePosixPath("g/b.md")] = "a"

    assert any(f.startswith("anchors:") and "repeats a" in f for f in check(merged))


def test_a_page_spanning_two_source_directories_is_caught(merged):
    """The packer makes this unreachable, which is why the audit still asks."""
    pages, _, _ = merged
    pages[0].topics[1] = Topic("B", PurePosixPath("h/b.md"), 10)

    assert any(f.startswith("directory integrity:") for f in check(merged))


def test_a_toc_node_pointing_at_no_page_is_caught(merged):
    _, _, roots = merged
    roots.append(node("Lost", "g/lost.md"))

    assert any(f.startswith("TOC completeness:") for f in check(merged))


def test_a_page_nothing_navigates_to_is_caught_unless_it_was_never_navigated(merged):
    """Both directions, because either one alone passes a real failure.

    Completeness alone would accept a tree that also emitted pages nothing links
    to; reachability alone would accept a TOC that quietly lost a branch.
    """
    pages, located, _ = merged
    stray = Page(UNNAVIGATED, [Topic("X", PurePosixPath("g/x.md"), 0)])
    pages.append(stray)
    located.update(assign(pages))

    assert any(f.startswith("reachability:") for f in check(merged))
    assert check(merged, unnavigated=frozenset({stray.path})) == []


def test_only_a_newly_broken_link_fails_the_stage(merged):
    assert check(merged, counts=LinkCounts(unresolved=92)) == []
    assert [f[:6] for f in check(merged, counts=LinkCounts(orphaned=1))] == ["links:"]


def test_a_redirect_into_a_page_that_was_never_written_is_caught(merged):
    """Checked against the pages actually built, so a page lost between packing and
    writing surfaces here rather than as a reader following a 301 into a 404."""
    _, located, _ = merged
    ghost = Page("Guide", [Topic("C", PurePosixPath("g/c.md"), 0)], PurePosixPath("g/c.md"))
    located[PurePosixPath("g/c.md")] = (ghost, "c")

    assert any(f.startswith("redirects:") for f in check(merged))


# -- R6: the review queue ------------------------------------------------------
#
# The queue is the stage's one hand-off to a human, so the thing under test is not
# "does a flag compute" but "is the result something a writer can work". Two of
# R6's five conditions hold for every page in this implementation, and the tests
# that matter are the ones pinning that they annotate rather than queue.


def flagged(page, max_words=3000, ancestors=None):
    return [f.name for f in inspect(page, max_words, ancestors or {})]


def paged(*words: int, guide: str = "Guide", directory: str = "g") -> Page:
    page = Page(guide, [Topic(f"T{i}", PurePosixPath(f"{directory}/t{i}.md"), w) for i, w in enumerate(words)])
    assign([page])
    return page


def test_a_long_page_of_tiny_topics_is_a_reference_list():
    """R6's sharpest flag: 20+ topics averaging under 100 words is a table."""
    assert "reference-list" in flagged(paged(*[60] * 20))
    assert "reference-list" not in flagged(paged(*[60] * 19))
    assert "reference-list" not in flagged(paged(*[400] * 20))


def test_a_page_over_the_cap_is_flagged_rather_than_split():
    """R1.3 forbids splitting a topic body, so the cap yields and a human decides."""
    assert "oversized" in flagged(paged(5000))
    assert "oversized" not in flagged(paged(2999))


def test_a_page_spanning_two_toc_branches_is_heterogeneous():
    page = paged(10, 10)
    ancestors = {
        PurePosixPath("g/t0.md"): "Configuring",
        PurePosixPath("g/t1.md"): "Troubleshooting",
    }

    assert "heterogeneous" in flagged(page, ancestors=ancestors)
    assert "heterogeneous" not in flagged(page, ancestors=dict.fromkeys(ancestors, "Configuring"))


def test_a_guide_landing_topic_beside_its_own_branch_is_not_heterogeneous():
    """R6 says *depth-2* ancestor, and a top-level row's own topic has no such thing.

    Bucketing it under its own title instead makes a parent plus its single child
    branch read as spanning two branches, which is the one shape that obviously is
    not heterogeneous. Measured on EMS 10.5.1: 5 pages flag either way against 7,
    and the two dropped are exactly this false positive.
    """
    roots = [node("Installation", "g/a.md", node("Overview", "g/b.md", node("Deeper", "g/c.md")))]

    found = branches(roots)

    assert PurePosixPath("g/a.md") not in found
    assert found[PurePosixPath("g/b.md")] == "Overview"
    assert found[PurePosixPath("g/c.md")] == "Overview"
    assert "heterogeneous" not in flagged(paged(10, 10, 10), ancestors=found)


def test_the_two_universal_flags_annotate_and_never_queue_on_their_own():
    """Planning §20c, and R6's own sentence: "a queue containing every page is not
    a queue."

    `title-inherited` is "`n_topics > 1` and the page title equals its first
    topic's" -- but R7 *defines* the title as the first topic's, so the second
    clause is true by construction and it fires on 107 of EMS 10.5.1's 124 pages.
    `single-topic` fires on the other 17, and R6 itself calls it "usually fine".
    Applied literally the pair queues every page and the other three flags stop
    meaning anything.
    """
    assert flagged(paged(10, 10)) == ["title-inherited"]
    assert flagged(paged(10)) == ["single-topic"]
    assert not rows([paged(10, 10), paged(10)], {})
    assert set(QUEUEING) == {"reference-list", "oversized", "heterogeneous"}


def test_an_annotation_still_rides_along_on_a_page_queued_for_another_reason():
    """Which is what makes narrowing the queue lossless rather than a measurement
    thrown away -- widening it later is a change to `QUEUEING` and nothing else."""
    page = paged(*[60] * 20)
    flags = inspect(page, 3000, {})
    queue = rows([page], {page.path: flags})

    assert queue[0]["flags"] == "reference-list;title-inherited"
    assert "20 topics" in queue[0]["detail"]


def test_a_queue_row_carries_the_numbers_the_decision_turns_on():
    page = paged(5000, guide="Reference")
    queue = rows([page], {page.path: inspect(page, 3000, {})})

    assert queue[0]["page_path"] == "g/t0.md"
    assert queue[0]["guide"] == "Reference"
    assert (queue[0]["n_topics"], queue[0]["words"]) == ("1", "5000")
    assert queue[0]["flags"] == "oversized;single-topic"
    assert "5,000 words over a 3,000 cap" in queue[0]["detail"]


def test_a_carried_topic_has_no_toc_branch_and_is_not_heterogeneous():
    """Its topics are absent from the ancestor map entirely, so the spread is empty."""
    page = Page(UNNAVIGATED, [Topic("X", PurePosixPath("g/x.md"), 10)])
    assign([page])

    assert flagged(page) == ["single-topic"]


def test_the_queue_is_written_in_reading_order_not_sorted_by_path():
    """A writer works a guide at a time, and reading order is already deterministic."""
    late = paged(5000, directory="z")
    early = paged(5000, directory="a")
    queue = rows([late, early], {p.path: inspect(p, 3000, {}) for p in (late, early)})

    assert [row["page_path"] for row in queue] == ["z/t0.md", "a/t0.md"]


def test_every_flag_is_recorded_for_every_page_even_when_nothing_is_queued(
    config, catalog, flare
):
    """`review-queue.csv` is a view over `reframe.yml`, not a separate measurement."""
    converted_tree(config, flare, "10.5.1")

    result = Reframer(config, catalog).reframe_one(flare, flare.versions["10.5.1"])
    document = yaml.safe_load((result.path / "reframe.yml").read_text(encoding="utf-8"))

    assert [page["flags"] for page in document["merged"]] == [["title-inherited"], ["single-topic"]]


def test_an_empty_queue_is_still_written_with_its_header(config, catalog, flare):
    """An absent file is indistinguishable from a merge that predates the queue."""
    converted_tree(config, flare, "10.5.1")
    findings = FindingsRun("reframe")

    result = Reframer(config, catalog, findings=findings).reframe_one(
        flare, flare.versions["10.5.1"]
    )
    written = (result.path / "review-queue.csv").read_text(encoding="utf-8-sig")

    assert result.queued == 0
    assert written.splitlines() == ["page_path,guide,n_topics,words,flags,detail"]
    assert "REFRAME_REVIEW_QUEUED" not in codes(findings.all)


def test_a_queued_page_is_reported_as_a_note_and_counted_on_the_result(
    config, catalog, flare
):
    """A note, not a warning. The queue is expected output of a *successful* merge,
    and a warning that fires on every version of every run stops being read."""
    toc = yaml.safe_load(TOC)
    toc["docs"][1]["subfolderlist"] = [
        {"title": f"Row {i}", "url": f"users-guide/row-{i}.md"} for i in range(20)
    ]
    converted_tree(config, flare, "10.5.1", yaml.safe_dump(toc))
    findings = FindingsRun("reframe")

    result = Reframer(config, catalog, findings=findings).reframe_one(
        flare, flare.versions["10.5.1"]
    )

    assert result.queued == 1
    assert "REFRAME_REVIEW_QUEUED" in codes(findings.all)
    note = next(f for f in findings.all if f.code == "REFRAME_REVIEW_QUEUED")
    assert note.severity is Severity.NOTE
    assert "1 of 2 page(s)" in note.message
    rows_written = (result.path / "review-queue.csv").read_text(encoding="utf-8-sig").splitlines()
    assert len(rows_written) == 2
    assert rows_written[1].startswith("user-guide.md,User Guide,21,")


def test_a_queue_naming_a_page_that_was_not_written_fails_the_stage(merged):
    """R6's own audit check, and the same class of bug `_redirects` catches.

    A writer opening the queue and finding a path that is not there loses the one
    thing the queue is for, and would reasonably conclude the file is stale.
    """
    ghost = [{"page_path": "g/nowhere.md", "guide": "Guide", "n_topics": "1",
              "words": "1", "flags": "oversized", "detail": ""}]

    assert any(f.startswith("review queue:") for f in check(merged, queue=ghost))
    assert check(merged, queue=[]) == []


# -- 20e: keep_separate, the writer's answer to the queue --------------------------
#
# The one setting that undoes a merge for part of a doc set. It only ever refuses a
# join -- there is no entry that makes a page bigger -- so the worst a wrong line in
# the config can do is return a subtree to the layout Stage 6 already publishes.


def test_a_named_topic_is_not_merged_with_anything():
    roots = [node("Guide", "g/a.md", node("B", "g/b.md"), node("C", "g/c.md"))]

    pages = pack(roots, sized(g__a=10, g__b=10, g__c=10), 3000, ["g/b.md"])

    assert layout(pages) == [["g/a.md"], ["g/b.md"], ["g/c.md"]]


def test_a_named_directory_keeps_its_whole_subtree_granular():
    """The 13-row case. A writer reading `21 topics averaging 61 words` names the
    directory rather than twenty-one paths."""
    roots = [node("Guide", "g/a.md", node("R1", "g/ref/one.md"), node("R2", "g/ref/two.md"))]

    pages = pack(roots, sized(g__a=10, g__ref__one=10, g__ref__two=10), 3000, ["g/ref"])

    assert layout(pages) == [["g/a.md"], ["g/ref/one.md"], ["g/ref/two.md"]]


def test_nothing_joins_a_separated_page_from_behind():
    """What makes the verb "granular" and not "split here". Closing only *before* a
    named topic would leave the last one of a named subtree absorbing whatever came
    next, which is the opposite of what the writer asked for."""
    roots = [node("Guide", "g/a.md", node("B", "g/b.md"), node("C", "g/c.md"))]

    pages = pack(roots, sized(g__a=10, g__b=10, g__c=10), 3000, ["g/b.md"])

    assert ["g/b.md", "g/c.md"] not in layout(pages)


def test_an_unlisted_subtree_still_collapses_around_a_listed_one():
    """Scoped to what it names. A writer taking one page out of the merge must not
    re-granularize the guide it sits in."""
    roots = [node("Guide", "g/a.md",
                  node("Keep", "g/keep/x.md", node("Y", "g/keep/y.md")),
                  node("Merged", "g/m/one.md", node("Two", "g/m/two.md")))]

    pages = pack(roots, sized(g__a=10, g__keep__x=10, g__keep__y=10, g__m__one=10, g__m__two=10),
                 3000, ["g/keep"])

    assert layout(pages) == [["g/a.md"], ["g/keep/x.md"], ["g/keep/y.md"],
                             ["g/m/one.md", "g/m/two.md"]]


def test_a_prefix_matches_on_path_segments_and_not_on_characters():
    """`g/mon` must not take `g/monitoring.md` out of the merge. Both shapes are in
    the corpus and a character-prefix rule would fail silently on them."""
    roots = [node("Guide", "g/mon.md", node("M", "g/monitoring.md"))]
    counts = sized(g__mon=10, g__monitoring=10)

    assert layout(pack(roots, counts, 3000, ["g/monitor"])) == [["g/mon.md", "g/monitoring.md"]]


def test_a_file_must_be_named_with_its_extension():
    """Nothing is guessed from a bare stem: `g/mon` would otherwise mean the file or
    the directory depending on what happened to be on disk. Getting it wrong is the
    case `REFRAME_KEEP_SEPARATE_UNMATCHED` exists to make loud."""
    roots = [node("Guide", "g/mon.md", node("M", "g/other.md"))]
    counts = sized(g__mon=10, g__other=10)

    assert layout(pack(roots, counts, 3000, ["g/mon"])) == [["g/mon.md", "g/other.md"]]
    assert layout(pack(roots, counts, 3000, ["g/mon.md"])) == [["g/mon.md"], ["g/other.md"]]


def test_an_empty_list_changes_no_boundary():
    roots = [node("Guide", "g/a.md", node("B", "g/b.md"))]
    counts = sized(g__a=10, g__b=10)

    assert layout(pack(roots, counts, 3000, [])) == layout(pack(roots, counts, 3000))


def test_keep_separate_is_normalized_and_sorted_before_it_is_digested():
    """Reordering the list, or writing a trailing slash, is not a layout change --
    and the currency key is what would otherwise re-merge the doc set to prove it."""
    one = policy_for({"products": {"x": {"keep_separate": ["b/c", "a/"]}}}, "x")
    two = policy_for({"products": {"x": {"keep_separate": ["/a", "b/c", "a"]}}}, "x")

    assert one.keep_separate == ("a", "b/c") == two.keep_separate
    assert one.key == two.key


def test_a_path_copied_in_with_a_leading_dot_slash_still_matches():
    """`./users-guide/x.md` is how a path arrives from a file explorer or a shell
    completion. Unnormalized it matches nothing, and the merge the writer meant to
    undo happens anyway -- the warning would say so, but only after the fact."""
    policy = policy_for({"products": {"x": {"keep_separate": ["./g/a.md", ".\\g\\b.md"]}}}, "x")

    assert policy.keep_separate == ("g/a.md", "g/b.md")


def test_a_string_is_taken_as_a_one_entry_list():
    """YAML makes `keep_separate: users-guide/x.md` easy to write and the intent is
    never ambiguous. Silently ignoring it would be the config lying."""
    assert policy_for({"products": {"x": {"keep_separate": "g/a.md"}}}, "x").keep_separate == ("g/a.md",)


def test_keep_separate_counts_in_the_currency_digest():
    """The opposite call to `publish`, for the opposite reason: this field changes
    every byte downstream, so a tuned list leaving trees `current` is exactly the
    silent no-op `reframe_policy_key` exists to prevent."""
    base = policy_for({"defaults": {"max_words": 3000}}, "x")
    tuned = policy_for({"defaults": {"max_words": 3000}, "products": {"x": {"keep_separate": ["g"]}}}, "x")

    assert base.key != tuned.key



def keep(config, slug: str, *paths: str) -> None:
    (config.config_dir / "reframe.yaml").write_text(
        "defaults:\n  max_words: 3000\nproducts:\n  " + slug + ":\n    keep_separate:\n"
        + "".join(f"      - {path}\n" for path in paths),
        encoding="utf-8",
    )


def test_a_writers_decision_reaches_the_tree_that_is_written(config, catalog, flare):
    """End to end, because every hop between `reframe.yaml` and a page boundary is
    somewhere the decision could be dropped silently."""
    converted_tree(config, flare, "10.5.1")
    keep(config, flare.slug, "installation")

    result = Reframer(config, catalog).reframe_one(flare, flare.versions["10.5.1"])

    assert result.outcome is ReframeOutcome.REFRAMED
    written = sorted(p.relative_to(result.path).as_posix() for p in result.path.rglob("*.md"))
    assert sorted(written) == ["installation.md",
                               "installation/installation-overview.md",
                               "user-guide.md"]


def test_the_same_doc_set_merges_those_two_topics_without_the_override(config, catalog, flare):
    """The control. Without it, `installation/` is one page of two topics."""
    converted_tree(config, flare, "10.5.1")

    result = Reframer(config, catalog).reframe_one(flare, flare.versions["10.5.1"])

    written = sorted(p.relative_to(result.path).as_posix() for p in result.path.rglob("*.md"))
    assert written == ["installation.md", "user-guide.md"]


def test_a_keep_separate_path_matching_no_topic_is_named(config, catalog, flare):
    """A typo does nothing and looks exactly like a decision that was applied. Per
    version, because a path right for 10.5.1 and absent from 10.4.0 is the drift
    worth naming."""
    converted_tree(config, flare, "10.5.1")
    keep(config, flare.slug, "installation", "users-guide/typo.md")
    findings = FindingsRun("reframe")

    result = Reframer(config, catalog, findings=findings).reframe_one(
        flare, flare.versions["10.5.1"]
    )

    assert result.outcome is ReframeOutcome.REFRAMED
    assert codes(findings.all) == ["REFRAME_KEEP_SEPARATE_UNMATCHED"]
    assert findings.all[0].severity is Severity.WARNING
    assert "users-guide/typo.md" in findings.all[0].message
    assert "installation" not in findings.all[0].message

# -- 20f: CSH survives the merge ---------------------------------------------------
#
# A Help button is the one link in the tree whose other end is compiled into a
# shipped application. It cannot be fixed by re-running anything here, which is why
# the audit refuses the merge rather than letting `validate` find it three stages on.


def placed(page_path: str, *topics: tuple[str, str]):
    """`located`, built by hand: `(source, anchor)` pairs on one page."""
    built = Page(
        "Guide",
        [Topic(source, PurePosixPath(source), 10) for source, _ in topics],
        path=PurePosixPath(page_path),
        anchors={PurePosixPath(source): anchor for source, anchor in topics},
    )
    return {PurePosixPath(source): (built, anchor) for source, anchor in topics}


def test_a_csh_value_lands_on_the_section_because_its_own_anchor_is_unreachable():
    """It used to keep the identifier's own fragment, on the reasoning that an
    `<a id="help.a">` marker travelling in with the topic body was a more precise
    landing point than the section heading.

    Phase 29 measured that: the platform generates anchors from heading text and
    ignores markers, so **0 of 154 identifiers across the merged corpus
    resolved** -- every Help button landed nowhere. The section anchor is less
    precise than the help author asked for and is the whole of what the platform
    can express.
    """
    located = placed("g/merged.md", ("g/a.md", "a-section"), ("g/b.md", "b-section"))

    out = csh_map.retarget({"help.a": "g/a.md#help.a", "help.b": "g/b.md#help.b"}, located)

    assert out == {"help.a": "g/merged.md#a-section", "help.b": "g/merged.md#b-section"}


def test_a_value_with_no_fragment_lands_on_the_section_and_not_the_page_top():
    """18 of 108 in `tibco-runtime-agent@5.12.2`. Left bare, a Help button opens a
    twelve-section page at the top, which is the defect R5 exists to prevent."""
    located = placed("g/merged.md", ("g/a.md", "a-section"), ("g/b.md", "b-section"))

    assert csh_map.retarget({"help.b": "g/b.md"}, located) == {"help.b": "g/merged.md#b-section"}


def test_an_identifier_whose_topic_was_never_placed_is_left_exactly_as_it_was():
    """`toc.retarget`'s rule for the same condition. This module declines to invent a
    destination; the audit is what refuses the merge."""
    located = placed("g/merged.md", ("g/a.md", "a-section"))

    assert csh_map.retarget({"gone": "g/nowhere.md#gone"}, located) == {"gone": "g/nowhere.md#gone"}


def test_the_identifier_set_is_never_changed_by_a_retarget():
    """Design.md 9.6: a Help button may move and may never disappear. Asserted on the
    set rather than on values, because that is the invariant."""
    located = placed("g/merged.md", ("g/a.md", "a"), ("g/b.md", "b"))
    mapping = {"one": "g/a.md#one", "two": "g/b.md#two", "three": "g/gone.md#three"}

    assert set(csh_map.retarget(mapping, located)) == set(mapping)


def test_identifiers_are_grouped_under_their_topic_and_sorted():
    """Sorted because a merged page unions several topics' lists and C5 is byte
    determinism -- map order would make the frontmatter depend on how the converter
    happened to walk the source."""
    grouped = csh_map.by_topic({"z": "g/a.md#z", "a": "g/a.md#a", "m": "g/b.md#m"})

    assert grouped == {PurePosixPath("g/a.md"): ["a", "z"], PurePosixPath("g/b.md"): ["m"]}


def test_a_merged_page_mirrors_every_identifier_it_absorbed(tmp_path):
    """Design.md 9.5's mirror. Built from the `Page` alone it dropped all 154 in the
    corpus, which is a CSH_FRONTMATTER_MISMATCH per Help button once the paths are
    fixed -- and the path fix is what stops `validate` short-circuiting before it."""
    page = Page(
        "Guide",
        [Topic("A", PurePosixPath("g/a.md"), 2), Topic("B", PurePosixPath("g/b.md"), 2)],
        path=PurePosixPath("g/merged.md"),
        anchors={PurePosixPath("g/a.md"): "a", PurePosixPath("g/b.md"): "b"},
    )
    bodies = {"g/a.md": "# A\n\nword word\n", "g/b.md": "# B\n\nword word\n"}
    mirror = {PurePosixPath("g/a.md"): ["help.b", "help.a"], PurePosixPath("g/b.md"): ["help.c"]}

    text, _ = render(page, lambda p: bodies[str(p)], {}, frozenset(), LinkCounts(), mirror)

    assert yaml.safe_load(split_frontmatter(text)[0].strip("-\n"))["csh"] == [
        "help.a", "help.b", "help.c"
    ]


def test_a_page_with_no_identifiers_gets_no_csh_key():
    """An empty list in the frontmatter is a claim about context-sensitive help that
    the conversion never made."""
    page = Page("Guide", [Topic("A", PurePosixPath("g/a.md"), 2)],
                path=PurePosixPath("g/m.md"), anchors={PurePosixPath("g/a.md"): "a"})

    text, _ = render(page, lambda p: "# A\n\nword word\n", {}, frozenset(), LinkCounts(), {})

    assert "csh" not in yaml.safe_load(split_frontmatter(text)[0].strip("-\n"))


def test_the_audit_refuses_a_map_pointing_at_a_page_that_was_not_written():
    failures = audit(
        [], {}, [], words_in=0, words_out=0, added=0, counts=LinkCounts(),
        csh={"help.a": "g/gone.md#help.a"}, anchors={}, mirrored={},
    )

    assert any("not a merged page" in failure for failure in failures)


def test_the_audit_refuses_a_map_whose_anchor_did_not_survive_the_body_copy():
    page = PurePosixPath("g/merged.md")
    failures = audit(
        [], {}, [], words_in=0, words_out=0, added=0, counts=LinkCounts(),
        csh={"help.a": "g/merged.md#help.a"},
        anchors={page: frozenset({"something-else"})}, mirrored={page: frozenset({"help.a"})},
    )

    assert any("is not an anchor in" in failure for failure in failures)


def test_the_audit_refuses_a_map_the_frontmatter_does_not_mirror():
    page = PurePosixPath("g/merged.md")
    failures = audit(
        [], {}, [], words_in=0, words_out=0, added=0, counts=LinkCounts(),
        csh={"help.a": "g/merged.md#help.a"},
        anchors={page: frozenset({"help.a"})}, mirrored={page: frozenset()},
    )

    assert any("frontmatter" in failure for failure in failures)


def test_a_merge_with_no_csh_map_is_audited_as_before():
    assert audit([], {}, [], words_in=0, words_out=0, added=0, counts=LinkCounts()) == []


def test_a_csh_map_that_does_not_parse_fails_the_version_and_swaps_nothing(
    config, catalog, flare
):
    """Not a skip, for the reason an unrecognised `toc.yml` is not a skip. Writing
    nothing would delete every Help button from the merged tree with no record, and
    copying the file through would republish the pre-merge paths."""
    tree = converted_tree(config, flare, "10.5.1")
    (tree / "csh.yml").write_text("a: [unclosed\n", encoding="utf-8")
    findings = FindingsRun("reframe")

    result = Reframer(config, catalog, findings=findings).reframe_one(
        flare, flare.versions["10.5.1"]
    )

    assert result.outcome is ReframeOutcome.FAILED
    assert codes(findings.all) == ["REFRAME_SELF_CHECK_FAILED"]
    assert not config.reframed_path(
        flare.bu, flare.family, flare.slug, "10.5.1"
    ).exists()


def test_a_version_with_no_csh_map_gets_no_csh_file(config, catalog, flare):
    """A file the conversion never produced is a promise nobody made."""
    converted_tree(config, flare, "10.5.1")

    result = Reframer(config, catalog).reframe_one(flare, flare.versions["10.5.1"])

    assert result.outcome is ReframeOutcome.REFRAMED
    assert not (result.path / "csh.yml").is_file()


def test_the_written_map_and_the_written_frontmatter_agree_end_to_end(config, catalog, flare):
    """Every hop between the converted map and the merged tree, because the two halves
    are written by different modules and only agreeing matters."""
    tree = converted_tree(config, flare, "10.5.1")
    (tree / "csh.yml").write_text(
        "install.overview.helpurl: installation/installation-overvie.md#install.overview.helpurl\n",
        encoding="utf-8",
    )
    body = tree / "installation" / "installation-overvie.md"
    body.write_text(
        '# Installation Overview\n\n<a id="install.overview.helpurl"></a>\n\nWords here.\n',
        encoding="utf-8",
    )

    result = Reframer(config, catalog).reframe_one(flare, flare.versions["10.5.1"])

    assert result.outcome is ReframeOutcome.REFRAMED
    written = yaml.safe_load((result.path / "csh.yml").read_text(encoding="utf-8"))
    # The section's heading anchor, not the identifier's own `<a id>`: the marker
    # is in the body and the platform does not honour it (Phase 29).
    assert written == {
        "install.overview.helpurl":
            "installation.md#installation-overview"
    }
    page = (result.path / "installation.md").read_text(encoding="utf-8")
    assert yaml.safe_load(split_frontmatter(page)[0].strip("-\n"))["csh"] == [
        "install.overview.helpurl"
    ]


# -- the origin map (Phase 22) -------------------------------------------------
#
# The `301.yml` beside `redirects.yml`. Its whole reason to exist is that every
# other redirect artifact is expressed in coordinates this tool invented, and the
# `from` side of a cutover is an address on docs.tibco.com that it never wrote.
# It is written here rather than in `sync` because of 20d.1's `filecmp` trap: a
# per-version file written into the *published* folder after the copy makes every
# merged version re-copy on every run and takes `CURRENT` with it.

ORIGINS_CONFIG = """\
version: "1.0"
products:
  tibco-flare-docs:
    template: "https://docs.tibco.com/pub/{folder_path}/doc/{path}"
    drop_segments: 1
"""

ZIP_URL = "https://docs.tibco.com/pub/flaredocs/10.5.1/TIB_flaredocs_10.5.1_docs.zip"

SOURCES = [
    ("TIB_flaredocs_10.5.1/html/installation-2.htm", "installation/installation-2.md", "topic"),
    ("TIB_flaredocs_10.5.1/html/installation-overvie.htm",
     "installation/installation-overvie.md", "topic"),
    ("TIB_flaredocs_10.5.1/html/user-guide.htm", "users-guide/user-guide.md", "topic"),
]


@pytest.fixture
def declared(config, catalog):
    """A Flare product whose live URL shape somebody has actually checked."""
    (config.config_dir / "origin-urls.yaml").write_text(ORIGINS_CONFIG, encoding="utf-8")
    built = make_product("tibco-flare-docs", product_code="flaredocs", family="messaging")
    built.versions = {"10.5.1": make_version(
        "tibco-flare-docs", "10.5.1", engine=SourceEngine.FLARE, zip_url=ZIP_URL)}
    catalog.merge_fetch_results([built])
    product = catalog.get_product("tibco-flare-docs")
    product.versions["10.5.1"].zip_url = ZIP_URL
    catalog.state.record_output_map("tibco-flare-docs", "10.5.1", SOURCES)
    return product


def origin_rows(path: Path) -> list[dict]:
    return yaml.safe_load((path / "301.yml").read_text(encoding="utf-8"))["redirects"]


def test_every_converted_topic_gets_a_row_from_its_live_url(config, catalog, declared):
    """One row per `output_map` entry, not one per merged page. The reader who
    bookmarked an absorbed topic is the whole audience for this file."""
    converted_tree(config, declared, "10.5.1")

    result = Reframer(config, catalog).reframe_one(declared, declared.versions["10.5.1"])

    rows = origin_rows(result.path)
    assert [row["from"] for row in rows] == [
        "https://docs.tibco.com/pub/flaredocs/10.5.1/doc/html/installation-2.htm",
        "https://docs.tibco.com/pub/flaredocs/10.5.1/doc/html/installation-overvie.htm",
        "https://docs.tibco.com/pub/flaredocs/10.5.1/doc/html/user-guide.htm",
    ]
    assert all(row["status"] == 301 for row in rows)


def test_an_absorbed_topic_redirects_to_the_anchor_it_became(config, catalog, declared):
    """A leader keeps its own page and still gains an anchor, so it lands at
    `page.md#its-own-id` -- `redirects.yml`'s shape, for `redirects.yml`'s reason:
    the reader arrives at the section rather than at the top of a merged page."""
    converted_tree(config, declared, "10.5.1")

    result = Reframer(config, catalog).reframe_one(declared, declared.versions["10.5.1"])

    destinations = {row["from"].rsplit("/", 1)[1]: row["to"] for row in origin_rows(result.path)}
    assert destinations["installation-overvie.htm"] == (
        "installation.md#installation-overview")
    assert destinations["user-guide.htm"] == "user-guide.md#user-guide"


def test_the_origin_map_is_relative_to_its_own_folder_like_its_sibling(
    config, catalog, declared
):
    """The record, not the served form. `sync` prefixes the `to` side after the
    copy; prefixing it here would put a published URL inside the version folder
    and leave `validate` resolving it against the wrong root."""
    converted_tree(config, declared, "10.5.1")

    result = Reframer(config, catalog).reframe_one(declared, declared.versions["10.5.1"])

    assert not any("://" in row["to"] for row in origin_rows(result.path))


def test_the_origin_map_travels_with_the_merged_tree_rather_than_the_published_one(
    config, catalog, declared
):
    """20d.1's `filecmp` trap, asserted as a location. Written into staging it is
    copied like any other file and the shallow currency check stays true."""
    converted_tree(config, declared, "10.5.1")

    result = Reframer(config, catalog).reframe_one(declared, declared.versions["10.5.1"])

    written = sorted(p.name for p in result.path.iterdir() if p.is_file())
    assert written == ["301.yml", "installation.md", "redirects.yml", "reframe.yml",
                       "rename-map.csv", "review-queue.csv", "toc.yml", "user-guide.md"]


def test_an_undeclared_product_with_no_sitemap_gets_a_warning_and_no_file(config, catalog, flare):
    """No declaration and nothing on disk to derive one from. A guessed origin URL
    is a redirect to a page that never existed, and nothing downstream could tell."""
    converted_tree(config, flare, "10.5.1")
    findings = FindingsRun("reframe")

    result = Reframer(config, catalog, findings=findings).reframe_one(
        flare, flare.versions["10.5.1"])

    assert not (result.path / "301.yml").exists()
    named = [f for f in findings.all if f.code == "ORIGIN_SITEMAP_MISSING"]
    assert len(named) == 1 and "origin-urls.yaml" in named[0].message
    assert named[0].severity is Severity.WARNING
    assert "ORIGIN_TEMPLATE_UNDECLARED" not in all_codes(findings.all)


def test_a_zip_url_that_is_not_a_docsite_package_is_reported_rather_than_guessed(
    config, catalog, declared
):
    """An archived version's `zipPath` comes back from the API verbatim. Building
    a folder out of it would emit eight thousand rows pointing into a tree the
    docsite does not serve -- all of them plausible, none of them live."""
    declared.versions["10.5.1"].zip_url = "/archive/flaredocs/TIB_flaredocs_10.5.1_docs.zip"
    converted_tree(config, declared, "10.5.1")
    findings = FindingsRun("reframe")

    result = Reframer(config, catalog, findings=findings).reframe_one(
        declared, declared.versions["10.5.1"])

    assert not (result.path / "301.yml").exists()
    assert "not a /pub/ docsite package path" in [
        f.message for f in findings.all if f.code == "ORIGIN_TEMPLATE_UNDECLARED"][0]


def test_a_topic_the_merge_never_saw_still_gets_a_row(config, catalog, declared):
    """`output_map` is the authority, not the TOC. A topic converted and left
    unmerged still has a live URL that stops working at cutover, and it points at
    its own carried-through page."""
    catalog.state.record_output_map("tibco-flare-docs", "10.5.1", [
        *SOURCES, ("TIB_flaredocs_10.5.1/html/orphan.htm", "orphan.md", "topic")])
    converted_tree(config, declared, "10.5.1")

    result = Reframer(config, catalog).reframe_one(declared, declared.versions["10.5.1"])

    rows = {row["from"].rsplit("/", 1)[1]: row["to"] for row in origin_rows(result.path)}
    assert rows["orphan.htm"] == "orphan.md"


def test_folders_mirror_the_toc_so_the_path_is_the_published_url():
    """Phase 29. AEM builds an address from the TOC chain of filenames, so laying
    the directories out the same way makes the repo path and the URL one string.

    A page with child pages becomes a folder named after its own file, with the
    children inside it and its own page beside the folder.
    """
    roots = [node(
        "Installation", "src/a.md",
        node("Requirements", "src/b.md"),
        node("Installing", "src/c.md", node("On Windows", "src/d.md")),
    )]

    pages = pack(roots, lambda p: 10, 15)
    assign(pages)
    moved = relocate(pages, roots)

    assert [str(page.path) for page in pages] == [
        "installation.md",
        "installation/requirements.md",
        "installation/installing.md",
        "installation/installing/on-windows.md",
    ]
    assert moved == 4


def test_an_absorbed_topics_row_does_not_move_the_page_it_merged_into():
    """Only a page's *leading* topic places it. An absorbed topic is a section,
    and treating its TOC row as a location would push the whole page a level
    deeper than the node a reader navigated from."""
    roots = [node("Guide", "src/a.md", node("Absorbed", "src/b.md"))]

    pages = pack(roots, lambda p: 10, 3000)
    assign(pages)
    relocate(pages, roots)

    assert [str(page.path) for page in pages] == ["guide.md"]


def test_a_carried_page_is_left_where_it_was_because_no_toc_names_it():
    """`carry`'s pages were never in the navigation, so there is no chain to put
    them in -- and inventing one would give an unnavigated topic a more confident
    address than a navigated one."""
    roots = [node("Guide", "src/a.md")]
    pages = pack(roots, lambda p: 10, 3000) + carry(
        [PurePosixPath("odd/stray.md")], lambda p: "A Stray", lambda p: 10
    )
    assign(pages)
    relocate(pages, roots)

    assert [str(page.path) for page in pages] == ["guide.md", "odd/a-stray.md"]


# -- rename-map.csv (Phase 29) --------------------------------------------------


def test_a_name_a_human_kept_survives_a_title_change(config, catalog, flare):
    """The whole point of the map. A published URL must not move because somebody
    fixed a typo in a title -- requirements §1's "every layout decision is
    permanent", which no amount of care at the naming end can deliver on its own.
    """
    from docushift.reframe import renames

    converted_tree(config, flare, "10.5.1")
    result = Reframer(config, catalog).reframe_one(flare, flare.versions["10.5.1"])
    mapped = renames.load(result.path)
    assert mapped[PurePosixPath("users-guide/user-guide.md")] == PurePosixPath("user-guide.md")

    # A writer renames the page in the map, then somebody retitles the topic.
    rows_now = list(csvio.read_rows(result.path / renames.RENAME_MAP))
    for row in rows_now:
        if row["old_path"] == "users-guide/user-guide.md":
            row["new_path"] = "using-the-product.md"
    renames.write(result.path / renames.RENAME_MAP, rows_now)
    retitled = TOC.replace('title: "User Guide"', 'title: "User Guide (Revised)"')
    converted_tree(config, flare, "10.5.1", toc=retitled)

    again = Reframer(config, catalog).reframe_one(flare, flare.versions["10.5.1"], force=True)

    written = sorted(p.name for p in again.path.rglob("*.md"))
    assert "using-the-product.md" in written
    assert "user-guide-revised.md" not in written


def test_renormalize_is_how_a_writer_asks_for_the_names_back(config, catalog, flare):
    """Pinning has to be a decision rather than a trap."""
    from docushift.reframe import renames

    converted_tree(config, flare, "10.5.1")
    result = Reframer(config, catalog).reframe_one(flare, flare.versions["10.5.1"])
    rows_now = list(csvio.read_rows(result.path / renames.RENAME_MAP))
    for row in rows_now:
        if row["old_path"] == "users-guide/user-guide.md":
            row["new_path"] = "using-the-product.md"
    renames.write(result.path / renames.RENAME_MAP, rows_now)

    again = Reframer(config, catalog, renormalize=True).reframe_one(
        flare, flare.versions["10.5.1"], force=True
    )

    written = sorted(p.name for p in again.path.rglob("*.md"))
    assert "user-guide.md" in written
    assert "using-the-product.md" not in written


def test_the_map_records_the_address_a_reader_will_type(config, catalog, flare):
    """The one column `reframe.yml` cannot supply, and the one somebody checks
    when a link goes wrong. Through `sync.redirects.published`, not a second
    formula beside it."""
    from docushift.reframe import renames

    converted_tree(config, flare, "10.5.1")

    result = Reframer(config, catalog).reframe_one(flare, flare.versions["10.5.1"])

    rows_now = {r["old_path"]: r for r in csvio.read_rows(result.path / renames.RENAME_MAP)}

    # One row per *page*, keyed on the topic that leads it -- an absorbed topic
    # is a section, and `redirects.yml` is where it is accounted for.
    assert set(rows_now) == {"installation/installation-2.md", "users-guide/user-guide.md"}
    row = rows_now["installation/installation-2.md"]
    assert row["title"] == "Installation"
    assert row["toc_breadcrumb"] == "Installation"
    assert row["expected_aem_url"] == (
        "us/en/tibco-flare-docs/online-help/10-5-1/installation.html"
    )


def test_an_approved_name_another_page_already_holds_is_refused():
    """Two pages at one path is a page silently lost, and no record is worth that."""
    from docushift.reframe.packer import override

    roots = [node("First", "g/a.md"), node("Second", "g/b.md")]
    pages = pack(roots, lambda p: 10, 3000)
    assign(pages)
    relocate(pages, roots)

    pinned = override(pages, {PurePosixPath("g/b.md"): PurePosixPath("first.md")})

    assert pinned == 0
    assert [str(page.path) for page in pages] == ["first.md", "second.md"]


def test_an_asset_lands_in_a_lower_cased_folder_so_it_matches_the_page_tree():
    """ActiveSpaces has a source directory `Concepts/` and, since `relocate`, a
    page folder `concepts/`. On Windows the copy lands silently in whichever
    exists and every link in it reads `../Concepts/` against a directory spelled
    `concepts`; on Linux those are two directories and the image 404s.

    The file keeps its name byte-for-byte -- §6.4's rule. Only the folder moves,
    and only in case.
    """
    from docushift.reframe.packer import asset_destination

    assert str(asset_destination(PurePosixPath("Concepts/AS_Workflow_V-two.png"))) == (
        "concepts/AS_Workflow_V-two.png"
    )
    assert str(asset_destination(PurePosixPath("img/a.png"))) == "img/a.png"


def test_an_asset_link_is_written_against_where_the_asset_lands():
    """The copier and the rewriter through one function, because the whole
    failure was the two disagreeing."""
    here = Page("G", [Topic("A", PurePosixPath("Concepts/a.md"), 10)])
    here.path = PurePosixPath("concepts/a.md")
    located = {PurePosixPath("Concepts/a.md"): (here, "a")}
    existing = frozenset({PurePosixPath("Concepts/a.md"), PurePosixPath("Concepts/shot.png")})
    counts = LinkCounts()

    out = rewrite_links(
        "![s](shot.png)", PurePosixPath("Concepts/a.md"), here.path, located, existing, counts
    )

    assert out == "![s](shot.png)"
    assert counts.asset == 1


# -- the origin map, derived from the sitemap (Phase 33) --------------------------

LIVE = "https://docs.tibco.com/pub/flaredocs/10.5.1/doc/html"


def cache_sitemap(config, urls: list[str]) -> None:
    """What `catalog sitemap` leaves in `cache/coveo/` for one version."""
    from docushift.discovery.sitemap import SitemapCache

    cache = SitemapCache(config.cache_dir / "coveo")
    body = "".join(f"<url><loc>{url}</loc></url>" for url in urls)
    cache.write("tibco-flare-docs-10-5-1.xml", (
        "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9/sitemap.xsd'>"
        f"{body}</urlset>").encode())
    cache.save_manifest({"files": {}, "products": {"tibco-flare-docs": ["tibco-flare-docs-10-5-1"]}})


@pytest.fixture
def listed_flare(config, catalog, flare):
    flare.versions["10.5.1"].zip_url = ZIP_URL
    catalog.state.record_output_map("tibco-flare-docs", "10.5.1", SOURCES)
    return flare


def test_an_undeclared_product_takes_the_mapping_its_sitemap_confirms(config, catalog, listed_flare):
    """The declared EMS shape, found without the declaration."""
    cache_sitemap(config, [f"{LIVE}/{src.rsplit('/', 1)[1]}" for src, _, _ in SOURCES])
    converted_tree(config, listed_flare, "10.5.1")
    findings = FindingsRun("reframe")

    result = Reframer(config, catalog, findings=findings).reframe_one(
        listed_flare, listed_flare.versions["10.5.1"])

    assert [row["from"] for row in origin_rows(result.path)] == [
        f"{LIVE}/installation-2.htm", f"{LIVE}/installation-overvie.htm", f"{LIVE}/user-guide.htm"]
    assert not [c for c in all_codes(findings.all) if c.startswith("ORIGIN_")]


def test_a_derived_row_the_sitemap_does_not_list_is_withheld(config, catalog, listed_flare):
    """Ten sources, nine listed: the mapping clears 90%, the tenth row is not written."""
    sources = [(f"TIB_flaredocs_10.5.1/html/t{i}.htm", f"t{i}.md", "topic") for i in range(10)]
    catalog.state.record_output_map("tibco-flare-docs", "10.5.1", sources)
    cache_sitemap(config, [f"{LIVE}/t{i}.htm" for i in range(9)] + [f"{LIVE}/api.htm"])
    converted_tree(config, listed_flare, "10.5.1")
    findings = FindingsRun("reframe")

    result = Reframer(config, catalog, findings=findings).reframe_one(
        listed_flare, listed_flare.versions["10.5.1"])

    froms = [row["from"] for row in origin_rows(result.path)]
    assert len(froms) == 9 and f"{LIVE}/t9.htm" not in froms
    by_code = {f.code: f for f in findings.all if f.code.startswith("ORIGIN_")}
    assert set(by_code) == {"ORIGIN_URL_UNLISTED", "ORIGIN_PAGE_UNMAPPED"}
    assert by_code["ORIGIN_URL_UNLISTED"].severity is Severity.NOTE
    assert "withheld" in by_code["ORIGIN_URL_UNLISTED"].message
    assert "api.htm" in by_code["ORIGIN_PAGE_UNMAPPED"].message


def test_a_sitemap_that_confirms_no_mapping_writes_no_file(config, catalog, listed_flare):
    cache_sitemap(config, [f"{LIVE}/unrelated.htm"])
    converted_tree(config, listed_flare, "10.5.1")
    findings = FindingsRun("reframe")

    result = Reframer(config, catalog, findings=findings).reframe_one(
        listed_flare, listed_flare.versions["10.5.1"])

    assert not (result.path / "301.yml").exists()
    named = [f for f in findings.all if f.code == "ORIGIN_TEMPLATE_UNDECLARED"]
    assert len(named) == 1 and "0 of 3 topics placed" in named[0].message


def test_a_declared_template_writes_every_row_and_the_sitemap_only_counts(config, catalog, declared):
    """A human checked the declaration; the list disagreeing is a note, not a veto."""
    cache_sitemap(config, [f"{LIVE}/user-guide.htm"])
    converted_tree(config, declared, "10.5.1")
    findings = FindingsRun("reframe")

    result = Reframer(config, catalog, findings=findings).reframe_one(
        declared, declared.versions["10.5.1"])

    assert len(origin_rows(result.path)) == 3
    unlisted = [f for f in findings.all if f.code == "ORIGIN_URL_UNLISTED"]
    assert len(unlisted) == 1 and "written anyway" in unlisted[0].message
