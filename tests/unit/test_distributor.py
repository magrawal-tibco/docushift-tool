"""Stage 6b's distributor: the publishing form, the swap boundary, the drop-down.

The scoped-run tests are the point of the file. `sync` takes `--version`, so the
dangerous bug here is not a copy that fails -- it is a copy that succeeds and
quietly unlinks the thirty-seven versions the run did not touch.
"""

import os
import shutil
import time
from pathlib import Path

import pytest
import yaml

from docushift.config import ConfigManager
from docushift.models import Product, ProductVersion
from docushift.reporting.findings import FindingsRun
from docushift.sync import (
    ONLINE_HELP,
    REFERENCE_DOCUMENTS,
    RELEASE_INFORMATION,
    USER_GUIDES,
    SyncOutcome,
    WorkspaceDistributor,
)

TREE = "en-us-tibco-messaging-userdocs"
#: The served prefix: no repository segment, and `en-us` region-first as the
#: platform serves it. Phase 29 -- see `sync/redirects.py`.
SERVED = "us/en"


@pytest.fixture
def product() -> Product:
    return Product(
        slug="tibco-ems",
        product_code="ems",
        display_name="TIBCO Enterprise Message Service™",
        bu="tibco",
        family="messaging",
        versions={
            "10.4.0": ProductVersion(slug="tibco-ems", version="10.4.0", release_date="2026-02-06"),
            "10.3.1": ProductVersion(slug="tibco-ems", version="10.3.1", release_date="2025-08-11"),
        },
    )


@pytest.fixture
def target(tmp_path: Path) -> Path:
    path = tmp_path / "workspace"
    path.mkdir()
    return path


@pytest.fixture
def distributor(config: ConfigManager, catalog) -> WorkspaceDistributor:
    return WorkspaceDistributor(config, catalog)


def convert_output(config: ConfigManager, product: Product, number: str, **files: str) -> Path:
    """Writes a converted tree where `sync` expects to find one."""
    root = config.output_path(product.bu, product.family, product.slug, number)
    root.mkdir(parents=True, exist_ok=True)
    for name, body in ({"index.md": f"# {number}\n", "toc.yml": "nodes: []\n"} | files).items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return root


def extract_tree(config: ConfigManager, product: Product, number: str, **files: str) -> Path:
    """Writes an extracted tree where 6c's router expects to find one.

    Keys are slash-separated relative paths, because where a file sits is half of
    what §10.4 routes on -- `pdf/x.pdf` and `doc/pdf/x.pdf` are different facts.
    """
    root = config.extract_path(product.bu, product.family, product.slug, number)
    for name, body in files.items():
        path = root.joinpath(*name.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    root.mkdir(parents=True, exist_ok=True)
    return root


def published(target: Path, number: str = "10-4-0", doc_class: str = ONLINE_HELP) -> Path:
    return target / TREE / "en-us" / "tibco-ems" / doc_class / number


# -- one version -----------------------------------------------------------------


def test_a_converted_version_lands_in_the_publishing_form(config, distributor, product, target) -> None:
    """`{target}/{docs-tree}/{locale}/{slug}/online-help/{segment}/` (§6.1)."""
    convert_output(config, product, "10.4.0", **{"topics/a.md": "a\n"})

    result = distributor.sync_one(product, product.versions["10.4.0"], target)

    assert result.outcome is SyncOutcome.SYNCED
    assert result.path == published(target)
    assert (published(target) / "index.md").read_text(encoding="utf-8") == "# 10.4.0\n"
    assert (published(target) / "topics" / "a.md").exists()
    assert result.files == 3


def test_the_dots_become_dashes_only_here(config, distributor, product, target) -> None:
    """The working tree keeps its dots so a segment round-trips to a catalog key."""
    source = convert_output(config, product, "10.4.0")

    result = distributor.sync_one(product, product.versions["10.4.0"], target)

    assert source.name == "10.4.0"
    assert result.segment == "10-4-0"


def test_a_version_with_no_converted_tree_is_an_outcome_not_an_abort(distributor, product, target) -> None:
    """Over a partially converted corpus this is the normal state, not an error."""
    result = distributor.sync_one(product, product.versions["10.4.0"], target)

    assert result.outcome is SyncOutcome.NO_OUTPUT
    assert "docushift convert" in result.message
    assert not published(target).exists()


def test_a_version_string_that_names_no_folder_is_skipped_and_named(config, distributor, product, target) -> None:
    """The analogue of `convert`'s `ENGINE_UNKNOWN`: reported, never guessed at."""
    version = ProductVersion(slug="tibco-ems", version="™")
    product.versions["™"] = version
    convert_output(config, product, "™")

    result = distributor.sync_one(product, version, target)

    assert result.outcome is SyncOutcome.SKIPPED
    assert "no publishable folder name" in result.message


def test_an_unchanged_tree_reports_current_on_the_second_run(config, distributor, product, target) -> None:
    """Compared against the target, not against a recorded hash (§6.6)."""
    convert_output(config, product, "10.4.0")
    distributor.sync_one(product, product.versions["10.4.0"], target)

    result = distributor.sync_one(product, product.versions["10.4.0"], target)

    assert result.outcome is SyncOutcome.CURRENT
    assert result.path == published(target)


def test_an_edited_target_is_not_current(config, distributor, product, target) -> None:
    """A stored fingerprint would claim currency for a tree nobody can vouch for."""
    convert_output(config, product, "10.4.0")
    distributor.sync_one(product, product.versions["10.4.0"], target)
    (published(target) / "index.md").write_text("# edited by hand, at length\n", encoding="utf-8")

    assert distributor.sync_one(product, product.versions["10.4.0"], target).outcome is SyncOutcome.SYNCED


def test_force_re_copies_a_tree_that_already_matches(config, distributor, product, target) -> None:
    convert_output(config, product, "10.4.0")
    distributor.sync_one(product, product.versions["10.4.0"], target)

    result = distributor.sync_one(product, product.versions["10.4.0"], target, force=True)

    assert result.outcome is SyncOutcome.SYNCED


def test_a_topic_deleted_upstream_does_not_survive_the_re_sync(config, distributor, product, target) -> None:
    """Wholesale replacement, not a merge: a guide dropped upstream must go."""
    source = convert_output(config, product, "10.4.0", **{"gone.md": "x\n"})
    distributor.sync_one(product, product.versions["10.4.0"], target)
    (source / "gone.md").unlink()

    distributor.sync_one(product, product.versions["10.4.0"], target)

    assert not (published(target) / "gone.md").exists()
    assert (published(target) / "index.md").exists()


# -- the swap boundary ------------------------------------------------------------


def test_the_replacement_reaches_neither_a_sibling_version_nor_the_drop_down(
    config, distributor, product, target
) -> None:
    """A swap scoped to the doc-class would delete the versions this run skipped."""
    convert_output(config, product, "10.4.0")
    convert_output(config, product, "10.3.1")
    distributor.sync_many([(product, product.versions[n]) for n in ("10.4.0", "10.3.1")], target)

    distributor.sync_one(product, product.versions["10.4.0"], target, force=True)

    assert published(target, "10-3-1").is_dir()
    assert (published(target).parent / "version.yml").is_file()
    assert (published(target).parent.parent / "metadata.yml").is_file()


def test_no_staging_directory_survives_the_run(config, distributor, product, target) -> None:
    convert_output(config, product, "10.4.0")
    distributor.sync_one(product, product.versions["10.4.0"], target)

    assert [child.name for child in published(target).parent.iterdir()] == ["10-4-0"]


# -- the product level -------------------------------------------------------------


def test_the_product_metadata_carries_the_display_name(config, distributor, product, target) -> None:
    convert_output(config, product, "10.4.0")

    distributor.sync_many([(product, product.versions["10.4.0"])], target)

    loaded = yaml.safe_load((target / TREE / "en-us" / "tibco-ems" / "metadata.yml").read_text(encoding="utf-8"))
    assert loaded == {"csg-product": "TIBCO Enterprise Message Service™"}


def test_a_product_that_published_nothing_gets_no_folder(distributor, product, target) -> None:
    """A product folder holding a `metadata.yml` and no content is a dead entry."""
    stats = distributor.sync_many([(product, product.versions["10.4.0"])], target)

    assert stats.products == 0
    assert not (target / TREE).exists()


# -- the drop-down -----------------------------------------------------------------


def test_the_drop_down_lists_what_is_on_disk_newest_first(config, distributor, product, target) -> None:
    convert_output(config, product, "10.4.0")
    convert_output(config, product, "10.3.1")

    distributor.sync_many([(product, product.versions[n]) for n in ("10.3.1", "10.4.0")], target)

    loaded = yaml.safe_load((published(target).parent / "version.yml").read_text(encoding="utf-8"))
    assert loaded["versions"] == [
        {"title": "10.4.0 (Feb 2026)", "path": "/10-4-0"},
        {"title": "10.3.1 (Aug 2025)", "path": "/10-3-1"},
    ]


def test_a_scoped_run_does_not_truncate_the_drop_down(config, distributor, product, target) -> None:
    """The bug this rule exists for: `--version 10.4.0` over a product with two
    published versions must not unlink the other one and report success."""
    convert_output(config, product, "10.4.0")
    convert_output(config, product, "10.3.1")
    distributor.sync_many([(product, product.versions[n]) for n in ("10.4.0", "10.3.1")], target)

    distributor.sync_many([(product, product.versions["10.4.0"])], target)

    loaded = yaml.safe_load((published(target).parent / "version.yml").read_text(encoding="utf-8"))
    assert [row["path"] for row in loaded["versions"]] == ["/10-4-0", "/10-3-1"]


def test_a_hand_written_row_survives_a_re_sync(config, distributor, product, target) -> None:
    convert_output(config, product, "10.4.0")
    distributor.sync_many([(product, product.versions["10.4.0"])], target)
    path = published(target).parent / "version.yml"
    path.write_text(
        'versions:\n- title: "Latest"\n  path: "https://docs.example/latest"\n'
        '- title: "10.4.0 (Feb 2026)"\n  path: "/10-4-0"\n',
        encoding="utf-8",
    )

    distributor.sync_many([(product, product.versions["10.4.0"])], target, force=True)

    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert [row["path"] for row in loaded["versions"]] == ["https://docs.example/latest", "/10-4-0"]


def test_an_unparseable_drop_down_is_left_alone_and_named(config, distributor, product, target) -> None:
    """Overwriting it would destroy the only copy of whatever a human put there."""
    convert_output(config, product, "10.4.0")
    distributor.sync_many([(product, product.versions["10.4.0"])], target)
    path = published(target).parent / "version.yml"
    path.write_text("versions:\n- title: [unclosed\n", encoding="utf-8")

    stats = distributor.sync_many([(product, product.versions["10.4.0"])], target, force=True)

    assert path.read_text(encoding="utf-8") == "versions:\n- title: [unclosed\n"
    assert stats.unparsed == [str(path)]
    assert stats.dropdowns == 0


# -- the document doc-classes (6c) --------------------------------------------------

# One package's non-converted shipment, in the shape 1,123 of 1,822 versions use.
SHIPMENT = {
    "pdf/tib_ems_users_guide.pdf": "a user guide\n",
    "pdf/tib_ems_relnotes.pdf": "release notes\n",
    "doc/readme.txt": "a readme\n",
    "doc/tib_ems_licenses.txt": "a licence\n",
}


def test_the_documents_land_beside_the_help_in_their_own_doc_classes(
    config, distributor, product, target
) -> None:
    """Four doc-classes from one version, and the folder decides three of them."""
    convert_output(config, product, "10.4.0")
    extract_tree(config, product, "10.4.0", **SHIPMENT)

    distributor.sync_many([(product, product.versions["10.4.0"])], target)

    def names(doc_class: str) -> set[str]:
        return {child.name for child in published(target, doc_class=doc_class).iterdir()}

    assert (published(target) / "index.md").is_file()
    assert names(USER_GUIDES) == {"tib_ems_users_guide.pdf", "index.md", "toc.yml", "metadata.yml"}
    assert names(RELEASE_INFORMATION) >= {"tib_ems_relnotes.pdf", "readme.txt"}
    assert names(REFERENCE_DOCUMENTS) >= {"tib_ems_licenses.txt"}


def test_a_doc_class_folder_is_indexed_because_nothing_synthesizes_its_navigation(
    config, distributor, product, target
) -> None:
    """`online-help` gets a TOC from its source TOC; a folder of PDFs has none."""
    extract_tree(config, product, "10.4.0", **SHIPMENT)

    distributor.sync_many([(product, product.versions["10.4.0"])], target)

    folder = published(target, doc_class=RELEASE_INFORMATION)
    index = folder.joinpath("index.md").read_text(encoding="utf-8")
    assert yaml.safe_load(index.split("---\n")[1]) == {
        "title": "TIBCO Enterprise Message Service™ 10.4.0 Release Information",
        "doc_class": "release-information",
        "generated": True,
    }
    # The artifacts are the index's list (Phase 9), and both are still named here.
    assert "- [Release Notes](tib_ems_relnotes.pdf)" in index
    assert "(readme.txt)" in index
    toc = yaml.safe_load(folder.joinpath("toc.yml").read_text(encoding="utf-8"))
    assert toc == {
        "docs_list_title": "Release Information",
        "docs": [
            {"title": "TIBCO Enterprise Message Service™ 10.4.0 Release Information",
             "url": "index.md"},
        ],
    }
    metadata = yaml.safe_load(folder.joinpath("metadata.yml").read_text(encoding="utf-8"))
    assert metadata == {"csg-version": "10.4.0"}


def test_a_version_that_never_converted_still_publishes_its_pdfs(
    config, distributor, product, target
) -> None:
    """The reason the documents read `extract_path` and not `output_path`: one
    version can be `NO_OUTPUT` for `online-help` and `SYNCED` for `user-guides`."""
    extract_tree(config, product, "10.4.0", **SHIPMENT)

    stats = distributor.sync_many([(product, product.versions["10.4.0"])], target)

    outcomes = {r.doc_class: r.outcome for r in stats.results}
    assert outcomes[ONLINE_HELP] is SyncOutcome.NO_OUTPUT
    assert outcomes[USER_GUIDES] is SyncOutcome.SYNCED
    assert not published(target).exists()
    assert (published(target, doc_class=USER_GUIDES) / "tib_ems_users_guide.pdf").is_file()


def test_an_extracted_tree_that_routes_nothing_gets_no_row_at_all(
    config, distributor, product, target
) -> None:
    """156 of 1,822 versions. Reporting them would put 156 recoverable-looking
    failures in every full run, and none of them is recoverable or a failure."""
    convert_output(config, product, "10.4.0")
    extract_tree(config, product, "10.4.0", **{"html/index.html": "<html></html>"})

    stats = distributor.sync_many([(product, product.versions["10.4.0"])], target)

    assert [r.doc_class for r in stats.results] == [ONLINE_HELP]


def test_a_second_run_reports_current_for_every_doc_class(config, distributor, product, target) -> None:
    """Compared before anything is staged -- `online-help`'s copy-then-compare shape
    would re-copy the PDFs and re-read every one of them to answer this."""
    extract_tree(config, product, "10.4.0", **SHIPMENT)
    distributor.sync_many([(product, product.versions["10.4.0"])], target)

    stats = distributor.sync_many([(product, product.versions["10.4.0"])], target)

    documents = [r for r in stats.results if r.doc_class in (USER_GUIDES, RELEASE_INFORMATION, REFERENCE_DOCUMENTS)]
    assert [r.outcome for r in documents] == [SyncOutcome.CURRENT] * 3
    assert all(r.path is not None for r in documents)


def test_force_rebuilds_a_doc_class_that_already_matches(config, distributor, product, target) -> None:
    """The one thing the cheap currency check cannot see is a template change."""
    extract_tree(config, product, "10.4.0", **SHIPMENT)
    distributor.sync_many([(product, product.versions["10.4.0"])], target)

    stats = distributor.sync_many([(product, product.versions["10.4.0"])], target, force=True)

    assert {r.outcome for r in stats.results if r.doc_class == USER_GUIDES} == {SyncOutcome.SYNCED}


def test_a_document_dropped_upstream_leaves_the_folder_and_the_index(
    config, distributor, product, target
) -> None:
    source = extract_tree(config, product, "10.4.0", **SHIPMENT)
    distributor.sync_many([(product, product.versions["10.4.0"])], target)
    (source / "doc" / "readme.txt").unlink()

    distributor.sync_many([(product, product.versions["10.4.0"])], target)

    folder = published(target, doc_class=RELEASE_INFORMATION)
    assert not (folder / "readme.txt").exists()
    assert "readme" not in folder.joinpath("index.md").read_text(encoding="utf-8")


def test_each_doc_class_carries_its_own_drop_down(config, distributor, product, target) -> None:
    """They will legitimately disagree: `user-guides` holds versions that shipped no
    converted help. That is the shape of the corpus, not a pair to reconcile."""
    convert_output(config, product, "10.4.0")
    convert_output(config, product, "10.3.1")
    extract_tree(config, product, "10.4.0", **SHIPMENT)

    distributor.sync_many([(product, product.versions[n]) for n in ("10.4.0", "10.3.1")], target)

    def rows(doc_class: str) -> list[str]:
        path = published(target, doc_class=doc_class).parent / "version.yml"
        return [row["path"] for row in yaml.safe_load(path.read_text(encoding="utf-8"))["versions"]]

    assert rows(ONLINE_HELP) == ["/10-4-0", "/10-3-1"]
    assert rows(USER_GUIDES) == ["/10-4-0"]


def test_a_scoped_document_run_does_not_unlink_its_sibling_version(
    config, distributor, product, target
) -> None:
    """The 6b rule, and 6c rides on it unchanged: the swap is one directory deep."""
    extract_tree(config, product, "10.4.0", **SHIPMENT)
    extract_tree(config, product, "10.3.1", **SHIPMENT)
    distributor.sync_many([(product, product.versions[n]) for n in ("10.4.0", "10.3.1")], target)

    distributor.sync_many([(product, product.versions["10.4.0"])], target, force=True)

    assert published(target, "10-3-1", USER_GUIDES).is_dir()
    assert (published(target, doc_class=USER_GUIDES).parent / "version.yml").is_file()
    assert [child.name for child in published(target, doc_class=USER_GUIDES).parent.iterdir()] == [
        "10-3-1", "10-4-0", "version.yml",
    ]


def test_a_pdf_that_will_not_read_is_published_and_noted(config, catalog, product, target) -> None:
    """A note, not a warning: the file ships and is titled from its filename. It
    earns a code by being rare -- 7 of the corpus's 5,007 PDFs, in 4 filenames."""
    extract_tree(config, product, "10.4.0", **{"pdf/tib_ems_users_guide.pdf": "not a PDF\n"})
    findings = FindingsRun("sync")

    WorkspaceDistributor(config, catalog, findings=findings).sync_many(
        [(product, product.versions["10.4.0"])], target
    )

    assert [f.code for f in findings.all] == ["DOCUMENT_UNREADABLE"]
    assert "tib_ems_users_guide.pdf" in findings.all[0].message
    folder = published(target, doc_class=USER_GUIDES)
    assert (folder / "tib_ems_users_guide.pdf").is_file()
    assert "- [tib ems users guide](tib_ems_users_guide.pdf)" in folder.joinpath("index.md").read_text(
        encoding="utf-8"
    )


# -- the register ------------------------------------------------------------------


def test_a_non_numeric_version_is_published_and_reported(config, catalog, product, target) -> None:
    """Sorted last in the drop-down, and named -- in 16 of 20 cases the report line
    is the only signal, because the artifact is the product's only version."""
    version = ProductVersion(slug="tibco-ems", version="Cloud™", release_date="2026-02-06")
    product.versions["Cloud™"] = version
    convert_output(config, product, "Cloud™")
    findings = FindingsRun("sync")
    distributor = WorkspaceDistributor(config, catalog, findings=findings)

    distributor.sync_many([(product, version)], target)

    assert published(target, "cloud").is_dir()
    assert [f.code for f in findings.all] == ["VERSION_NOT_NUMERIC"]


def test_an_undated_version_is_noted(config, catalog, product, target) -> None:
    product.versions["10.4.0"].release_date = ""
    convert_output(config, product, "10.4.0")
    findings = FindingsRun("sync")
    distributor = WorkspaceDistributor(config, catalog, findings=findings)

    distributor.sync_many([(product, product.versions["10.4.0"])], target)

    assert [f.code for f in findings.all] == ["VERSION_UNDATED"]
    loaded = yaml.safe_load((published(target).parent / "version.yml").read_text(encoding="utf-8"))
    assert loaded["versions"] == [{"title": "10.4.0", "path": "/10-4-0"}]


# -- the run -------------------------------------------------------------------------


def test_the_run_reports_five_outcomes_over_a_partial_corpus(config, distributor, product, target) -> None:
    """One converted version, one not, and neither of them ever extracted.

    Counted per doc-class since 6c: the `online-help` rows are the 6b contract and
    are unchanged, and each version contributes one more `NO_OUTPUT` for its
    documents because its *extracted* tree is a separate absence from its converted
    one. Both are recoverable and both name the command that recovers them.
    """
    convert_output(config, product, "10.4.0")

    stats = distributor.sync_many([(product, product.versions[n]) for n in ("10.4.0", "10.3.1")], target)

    help_rows = [r for r in stats.results if r.doc_class == ONLINE_HELP]
    assert sum(1 for r in help_rows if r.outcome is SyncOutcome.SYNCED) == 1
    assert sum(1 for r in help_rows if r.outcome is SyncOutcome.NO_OUTPUT) == 1
    document_rows = [r for r in stats.results if r.doc_class == ""]
    assert [r.outcome for r in document_rows] == [SyncOutcome.NO_OUTPUT] * 2
    assert all("docushift extract" in r.message for r in document_rows)
    assert stats.products == 1
    assert stats.dropdowns == 1


def test_sync_writes_nothing_back_into_output(config, distributor, product, target) -> None:
    """Stage 7 reads the converted tree; it does not annotate it."""
    source = convert_output(config, product, "10.4.0")
    before = sorted(path.name for path in source.rglob("*"))

    distributor.sync_many([(product, product.versions["10.4.0"])], target)

    assert sorted(path.name for path in source.rglob("*")) == before


# -- the -resources tree (6d) --------------------------------------------------------


RESOURCES = "en-us-tibco-messaging-userdocs-resources"


def javadoc_tree(config: ConfigManager, product: Product, number: str, *relatives: str) -> Path:
    """An extracted tree carrying one or more API trees `apiref` recognises."""
    root = config.extract_path(product.bu, product.family, product.slug, number)
    for n, relative in enumerate(relatives):
        folder = root.joinpath(*relative.split("/"))
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "index-all.html").write_text("<html></html>", encoding="utf-8")
        (folder / "index.html").write_text(f"<html>{relative}</html>", encoding="utf-8")
        (folder / "Class.html").write_text("c" * (10 + n), encoding="utf-8")
    root.mkdir(parents=True, exist_ok=True)
    return root


def resources(target: Path, *parts: str) -> Path:
    return target.joinpath(RESOURCES, "en-us", "tibco-ems", *parts)


def test_the_api_trees_go_to_the_sibling_tree_not_to_a_fifth_doc_class(
    config, distributor, product, target
) -> None:
    """`{resources-tree}/{locale}/{slug}/api-references/{version}/{name}/` (§6.3)."""
    javadoc_tree(config, product, "10.4.0", "html/api-docs/java", "html/api-docs/c")

    (result,) = distributor.sync_api_references(product, product.versions["10.4.0"], target)

    assert result.outcome is SyncOutcome.SYNCED
    assert result.doc_class == "api-references"
    folder = resources(target, "api-references", "10-4-0")
    assert result.path == folder
    assert sorted(child.name for child in folder.iterdir() if child.is_dir()) == ["c", "java"]
    assert (folder / "java" / "index.html").read_text(
        encoding="utf-8"
    ) == "<html>html/api-docs/java</html>"
    # The docs tree is untouched: this is a repository boundary, not a folder.
    assert not (target / TREE / "en-us" / "tibco-ems" / "api-references").exists()


def test_the_api_reference_copy_is_verbatim_with_no_index_of_its_own(
    config, distributor, product, target
) -> None:
    """All 165 in-scope roots ship their own `index.html`; a second entry competes."""
    javadoc_tree(config, product, "10.4.0", "html/api-docs/java")

    distributor.sync_api_references(product, product.versions["10.4.0"], target)

    tree = resources(target, "api-references", "10-4-0", "java")
    assert sorted(child.name for child in tree.iterdir()) == [
        "Class.html", "index-all.html", "index.html",
    ]
    assert not (tree / "index.md").exists()
    assert not (tree / "metadata.yml").exists()


def test_the_version_folder_carries_the_version_even_though_the_roots_do_not(
    config, distributor, product, target
) -> None:
    """`metadata.yml` describes the folder, not the content -- 6c's rule, one tree over."""
    javadoc_tree(config, product, "10.4.0", "html/api-docs/java")

    distributor.sync_api_references(product, product.versions["10.4.0"], target)

    loaded = yaml.safe_load(
        resources(target, "api-references", "10-4-0", "metadata.yml").read_text(encoding="utf-8")
    )
    assert loaded == {"csg-version": "10.4.0"}


def test_a_version_with_no_api_tree_reports_no_row_at_all(
    config, distributor, product, target
) -> None:
    """409 of the 422 products a full sync selects. A row each would bury the 13."""
    extract_tree(config, product, "10.4.0", **{"pdf/guide.pdf": "x"})

    assert distributor.sync_api_references(product, product.versions["10.4.0"], target) == []
    assert not (target / RESOURCES).exists()


def test_a_placed_api_tree_reports_current_on_the_second_run(
    config, distributor, product, target
) -> None:
    """Compared before staging: 1.39 GiB corpus-wide, and `copy2` already answered."""
    javadoc_tree(config, product, "10.4.0", "html/api-docs/java")
    version = product.versions["10.4.0"]
    distributor.sync_api_references(product, version, target)

    (again,) = distributor.sync_api_references(product, version, target)

    assert again.outcome is SyncOutcome.CURRENT
    (forced,) = distributor.sync_api_references(product, version, target, force=True)
    assert forced.outcome is SyncOutcome.SYNCED


def test_a_recorded_root_is_read_back_rather_than_re_walked(
    config, catalog, product, target
) -> None:
    """§6.3: Stages 4, 5 and 7 share one answer. The record narrows what 7 publishes.

    The tree holds two API trees and Stage 4 recorded one; publishing both would
    mean Stage 7 disagreeing with the file counts already in `versions.csv`.
    """
    javadoc_tree(config, product, "10.4.0", "html/api-docs/java", "html/api-docs/c")
    catalog.state.set_version_metadata("tibco-ems", "10.4.0", "api_roots", "html/api-docs/java\n")

    (result,) = WorkspaceDistributor(config, catalog).sync_api_references(
        product, product.versions["10.4.0"], target
    )

    folder = resources(target, "api-references", "10-4-0")
    assert [child.name for child in folder.iterdir() if child.is_dir()] == ["java"]
    assert result.files == 3


def test_publishing_an_api_tree_with_no_host_configured_is_reported_not_failed(
    config, catalog, product, target
) -> None:
    """Empty is the shipped state; failing would make `sync --all` unrunnable for the
    sake of 13 products. The links stay relative and somebody is told so."""
    javadoc_tree(config, product, "10.4.0", "html/api-docs/java")
    findings = FindingsRun("sync")

    (result,) = WorkspaceDistributor(config, catalog, findings=findings).sync_api_references(
        product, product.versions["10.4.0"], target
    )

    assert result.outcome is SyncOutcome.SYNCED
    assert [f.code for f in findings.all] == ["PUBLISH_BASE_URL_UNSET"]


def test_a_localized_run_gets_no_resources_tree_at_all(
    project_root: Path, catalog, product, target
) -> None:
    """The `loc-` tree carries every language; an API reference has none (§6.3)."""
    cfg = ConfigManager(root_dir=project_root, locale="ja-jp")
    javadoc_tree(cfg, product, "10.4.0", "html/api-docs/java")

    distributor = WorkspaceDistributor(cfg, catalog)

    assert distributor.sync_api_references(product, product.versions["10.4.0"], target) == []
    assert distributor.sync_archives(product, target) is None


# -- the archived history (6d) ---------------------------------------------------------


def test_the_archive_index_is_built_from_the_catalog_not_from_the_disk(
    distributor, product, target
) -> None:
    """0 archived ZIPs are on disk against 1,270 reachable rows; indexing the disk
    would publish an empty history that reads as a complete one."""
    product.versions["9.1.0"] = ProductVersion(
        slug="tibco-ems", version="9.1.0", is_archived=True, release_date="2021-05-04",
        zip_url="https://docs.example/ems-9.1.0.zip",
    )

    result = distributor.sync_archives(product, target)

    assert result.outcome is SyncOutcome.SYNCED
    assert result.doc_class == "archives"
    # No version segment: the folder is the history, not a version of it.
    folder = resources(target, "archives")
    assert result.path == folder
    assert sorted(child.name for child in folder.iterdir()) == [
        "index.md", "metadata.yml", "toc.yml",
    ]
    assert "- [9.1.0](https://docs.example/ems-9.1.0.zip) -- May 2021" in (
        folder / "index.md"
    ).read_text(encoding="utf-8")


def test_the_archive_row_carries_no_version_because_the_folder_spans_all_of_them(
    distributor, product, target
) -> None:
    product.versions["9.1.0"] = ProductVersion(slug="tibco-ems", version="9.1.0", is_archived=True)

    result = distributor.sync_archives(product, target)

    assert result.version == ""
    assert result.segment == ""
    loaded = yaml.safe_load(
        resources(target, "archives", "metadata.yml").read_text(encoding="utf-8")
    )
    assert loaded == {"csg-product": "TIBCO Enterprise Message Service™"}


def test_a_product_with_no_archived_rows_gets_no_archives_folder(
    distributor, product, target
) -> None:
    """43% of in-scope products, and an empty index is a claim about the product."""
    assert distributor.sync_archives(product, target) is None
    assert not resources(target, "archives").exists()


def test_a_retired_version_appearing_since_the_last_sync_is_not_reported_current(
    distributor, product, target
) -> None:
    """The file set never changes while nothing is downloaded, so the index is compared."""
    product.versions["9.1.0"] = ProductVersion(slug="tibco-ems", version="9.1.0", is_archived=True)
    distributor.sync_archives(product, target)

    assert distributor.sync_archives(product, target).outcome is SyncOutcome.CURRENT

    product.versions["9.2.0"] = ProductVersion(slug="tibco-ems", version="9.2.0", is_archived=True)
    result = distributor.sync_archives(product, target)

    assert result.outcome is SyncOutcome.SYNCED
    assert "9.2.0" in resources(target, "archives", "index.md").read_text(encoding="utf-8")


def test_a_downloaded_zip_is_copied_in_beside_the_index(
    config, distributor, product, target
) -> None:
    product.versions["9.1.0"] = ProductVersion(
        slug="tibco-ems", version="9.1.0", is_archived=True,
        zip_url="https://docs.example/ems-9.1.0.zip",
    )
    archive = config.archive_path("tibco", "messaging", "tibco-ems", "9.1.0")
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.write_bytes(b"PK" * 32)

    result = distributor.sync_archives(product, target)

    folder = resources(target, "archives")
    assert (folder / "tibco-ems-9.1.0.zip").read_bytes() == b"PK" * 32
    assert result.bytes == 64
    assert "- [9.1.0](tibco-ems-9.1.0.zip)" in (folder / "index.md").read_text(encoding="utf-8")


# -- both trees in one run ---------------------------------------------------------------


def test_one_run_writes_both_trees_and_places_the_api_refs_first(
    config, distributor, product, target
) -> None:
    """The order was chosen for a sync-time link rewrite that moved to conversion
    (§6.4.2); it is kept, and pinned, so the two trees are written in one known order."""
    convert_output(config, product, "10.4.0")
    javadoc_tree(config, product, "10.4.0", "html/api-docs/java")
    product.versions["9.1.0"] = ProductVersion(slug="tibco-ems", version="9.1.0", is_archived=True)

    stats = distributor.sync_many([(product, product.versions["10.4.0"])], target)

    classes = [r.doc_class for r in stats.results]
    assert classes.index("api-references") < classes.index(ONLINE_HELP)
    assert "archives" in classes
    assert published(target).is_dir()
    assert resources(target, "api-references", "10-4-0", "java").is_dir()
    assert resources(target, "archives", "index.md").is_file()
    # No `version.yml` beside `api-references`: the drop-down is an AEM page
    # control, and these folders are copied Javadoc rather than AEM pages.
    assert not resources(target, "api-references", "version.yml").exists()


# -- the package wrapper, and the ceiling (Phase 15) --------------------------------------


def wrapped(config: ConfigManager, product: Product, number: str, wrapper: str,
            **files: str) -> Path:
    """An extracted tree in the shape 46 of 50 sampled packages actually have."""
    root = config.extract_path(product.bu, product.family, product.slug, number)
    for name, body in files.items():
        path = root.joinpath(wrapper, *name.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return root


def test_documents_inside_a_package_wrapper_are_found(config, distributor, product, target) -> None:
    """Stage 7's first run against a downloaded package published no documents at
    all: `router.source_folders` reads `pdf/` from the version root, and a real
    package keeps it one level down (Phase 15a)."""
    wrapped(config, product, "10.4.0", "tibco-ems-10-4-0", **{
        "pdf/TIB_ems_10.4.0_user_guide.pdf": "%PDF-1.4",
        "pdf/TIB_ems_10.4.0_relnotes.pdf": "%PDF-1.4",
    })

    results = distributor.sync_documents(product, product.versions["10.4.0"], target)

    classes = {result.doc_class: result for result in results}
    assert classes[USER_GUIDES].outcome is SyncOutcome.SYNCED
    assert (published(target, doc_class=USER_GUIDES) / "TIB_ems_10.4.0_user_guide.pdf").is_file()
    assert (published(target, doc_class=RELEASE_INFORMATION)
            / "TIB_ems_10.4.0_relnotes.pdf").is_file()


def test_an_api_tree_is_not_named_after_the_wrapper_it_shipped_in(
    config, distributor, product, target
) -> None:
    """`tibco-ems-10-4-0-dotnetdoc` repeats the slug and version already two
    segments up the published path, and those characters are what put the longest
    file over the ceiling (Phase 15a)."""
    root = config.extract_path(product.bu, product.family, product.slug, "10.4.0")
    folder = root / "tibco-ems-10-4-0" / "html" / "api" / "dotnetdoc" / "html"
    folder.mkdir(parents=True)
    (folder / "index-all.html").write_text("<html></html>", encoding="utf-8")
    (folder / "index.html").write_text("<html>dotnet</html>", encoding="utf-8")

    (result,) = distributor.sync_api_references(product, product.versions["10.4.0"], target)

    assert result.outcome is SyncOutcome.SYNCED
    assert resources(target, "api-references", "10-4-0", "dotnetdoc").is_dir()


def test_a_published_path_over_the_ceiling_is_refused_and_named(
    config, distributor, product, target, monkeypatch
) -> None:
    """The error the wrapper fix removes the only known occurrence of. Refused
    *before* the copy, because `copytree` writes what fits and raises at the end,
    which publishes a partial API tree as though it were whole (Phase 15d)."""
    findings = FindingsRun("sync", store=None).start()
    distributor.findings = findings
    javadoc_tree(config, product, "10.4.0", "html/api-docs/java")
    monkeypatch.setattr("docushift.sync.distributor.PUBLISHED_PATH_LIMIT", 40)

    (result,) = distributor.sync_api_references(product, product.versions["10.4.0"], target)

    assert result.outcome is SyncOutcome.FAILED
    assert "over the 40" in result.message
    assert [f.code for f in findings.all] == ["PUBLISHED_PATH_TOO_LONG"]
    # Nothing half-written, and no staging tree left in a workspace we do not own.
    assert not resources(target, "api-references", "10-4-0").exists()
    assert not resources(target, "api-references", "10-4-0.part").exists()


def test_a_help_tree_over_the_ceiling_is_refused_and_named(
    config, distributor, product, target, monkeypatch
) -> None:
    """Phase 34, R1-01. Phase 29 put `long_path` on both ends of the help-tree copy
    to get past the `.part` overflow, and that also let a *final* path over the
    ceiling be written with no word said. The API trees were checked; this one
    was not."""
    findings = FindingsRun("sync", store=None).start()
    distributor.findings = findings
    convert_output(config, product, "10.4.0", **{"topics/a-deep-topic-name.md": "a\n"})
    limit = len(str(published(target))) + len("/index.md") + 2
    monkeypatch.setattr("docushift.sync.distributor.PUBLISHED_PATH_LIMIT", limit)

    result = distributor.sync_one(product, product.versions["10.4.0"], target)

    assert result.outcome is SyncOutcome.FAILED
    assert "a-deep-topic-name.md" in result.message
    assert [f.code for f in findings.all] == ["PUBLISHED_PATH_TOO_LONG"]
    assert not published(target).exists()
    assert not published(target, "10-4-0.part").exists()


def test_a_help_tree_already_published_over_the_ceiling_is_not_reported_current(
    config, distributor, product, target, monkeypatch
) -> None:
    """A tree an earlier run wrote over the line must not pass as `current` on
    every run after. It is left where it is, and named each time."""
    findings = FindingsRun("sync", store=None).start()
    convert_output(config, product, "10.4.0", **{"topics/a-deep-topic-name.md": "a\n"})
    distributor.sync_one(product, product.versions["10.4.0"], target)
    distributor.findings = findings
    limit = len(str(published(target))) + len("/index.md") + 2
    monkeypatch.setattr("docushift.sync.distributor.PUBLISHED_PATH_LIMIT", limit)

    result = distributor.sync_one(product, product.versions["10.4.0"], target)

    assert result.outcome is SyncOutcome.FAILED
    assert [f.code for f in findings.all] == ["PUBLISHED_PATH_TOO_LONG"]


def test_a_document_over_the_ceiling_is_refused_and_named(
    config, distributor, product, target, monkeypatch
) -> None:
    """The same rule for the document doc-classes (R1-01). Their files are flat in
    the version folder, so the longest name is the whole question."""
    findings = FindingsRun("sync", store=None).start()
    distributor.findings = findings
    long_name = "TIB_ems_10.4.0_user_guide_with_a_very_long_name.pdf"
    extract_tree(config, product, "10.4.0", **{f"pdf/{long_name}": "%PDF-1.4"})
    limit = len(str(published(target, doc_class=USER_GUIDES))) + len("/metadata.yml") + 2
    monkeypatch.setattr("docushift.sync.distributor.PUBLISHED_PATH_LIMIT", limit)

    (result,) = distributor.sync_documents(product, product.versions["10.4.0"], target)

    assert result.outcome is SyncOutcome.FAILED
    assert result.doc_class == USER_GUIDES
    assert long_name in result.message
    assert [f.code for f in findings.all] == ["PUBLISHED_PATH_TOO_LONG"]
    assert not published(target, doc_class=USER_GUIDES).exists()


def test_a_failed_placement_leaves_no_part_directory_behind(
    config, distributor, product, target, monkeypatch
) -> None:
    """`remove(staging)` runs on the way *in*, so before Phase 15c a failure left
    its half-copied tree in the published workspace until some later run."""
    javadoc_tree(config, product, "10.4.0", "html/api-docs/java")

    def explode(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("docushift.sync.distributor.shutil.copytree", explode)

    (result,) = distributor.sync_api_references(product, product.versions["10.4.0"], target)

    assert result.outcome is SyncOutcome.FAILED
    assert not resources(target, "api-references", "10-4-0.part").exists()


def test_a_copy_failure_reports_one_line_and_not_the_whole_triple_list(
    config, distributor, product, target, monkeypatch
) -> None:
    """`shutil.Error` carries every failed `(src, dst, why)`; printing it raw put
    several kilobytes into one table cell (Phase 15c)."""
    import shutil as shutil_module

    javadoc_tree(config, product, "10.4.0", "html/api-docs/java")
    failures = [(f"src/{n}.html", f"dst/{n}.html", "[WinError 3]") for n in range(200)]

    def explode(*args, **kwargs):
        raise shutil_module.Error(failures)

    monkeypatch.setattr("docushift.sync.distributor.shutil.copytree", explode)

    (result,) = distributor.sync_api_references(product, product.versions["10.4.0"], target)

    assert result.message == "200 file(s) could not be copied, the first 0.html: [WinError 3]"


# -- which tree gets published (Phase 20d) ----------------------------------------
#
# The one seam Reframe needed. Everything downstream of `_source` is a directory
# copy that does not care which tree it was handed, so these are the only tests in
# Stage 7 that have heard of Stage 6b.


def reframe_output(config: ConfigManager, product: Product, number: str, **files: str) -> Path:
    """A merged tree where `sync` looks for one when a product has opted in."""
    root = config.reframed_path(product.bu, product.family, product.slug, number)
    root.mkdir(parents=True, exist_ok=True)
    for name, body in ({"index.md": f"# merged {number}\n", "redirects.yml": "redirects: []\n"} | files).items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return root


def opt_in(config: ConfigManager, slug: str) -> None:
    config.reframe_path.write_text(
        f"defaults:\n  max_words: 3000\nproducts:\n  {slug}:\n    publish: true\n",
        encoding="utf-8",
    )


def current(catalog, slug: str, number: str, checksum: str = "abc123") -> None:
    """Both stages' recorded source checksums agreeing -- what `_stale` reads."""
    catalog.state.set_version_metadata(slug, number, "convert_source_checksum", checksum)
    catalog.state.set_version_metadata(slug, number, "reframe_source_checksum", checksum)


def test_a_product_that_has_not_opted_in_publishes_the_converted_tree(
    config, distributor, product, target
) -> None:
    """The default, and the state every product is in. A merged tree standing on
    disk from a tuning run must not reach the target on somebody's `sync --all`."""
    convert_output(config, product, "10.4.0")
    reframe_output(config, product, "10.4.0")

    result = distributor.sync_one(product, product.versions["10.4.0"], target)

    assert result.outcome is SyncOutcome.SYNCED
    assert not result.merged
    assert (result.path / "index.md").read_text(encoding="utf-8") == "# 10.4.0\n"


def test_an_opted_in_product_publishes_the_merged_tree_instead(
    config, catalog, distributor, product, target
) -> None:
    convert_output(config, product, "10.4.0")
    reframe_output(config, product, "10.4.0")
    opt_in(config, product.slug)
    current(catalog, product.slug, "10.4.0")

    result = distributor.sync_one(product, product.versions["10.4.0"], target)

    assert result.outcome is SyncOutcome.SYNCED
    assert result.merged
    assert (result.path / "index.md").read_text(encoding="utf-8") == "# merged 10.4.0\n"
    assert (result.path / "redirects.yml").is_file()


def test_an_opted_in_product_with_no_merged_tree_publishes_nothing_at_all(
    config, catalog, target, product
) -> None:
    """The refusal this phase exists for. Falling back to `output/` would republish
    the unmerged topics over URLs the merge already took -- un-merging live pages as
    a side effect of a merge that had simply not been re-run. Publishing nothing is
    recoverable; that is not.
    """
    convert_output(config, product, "10.4.0")
    opt_in(config, product.slug)
    findings = FindingsRun("sync")
    distributor = WorkspaceDistributor(config, catalog, findings=findings)

    result = distributor.sync_one(product, product.versions["10.4.0"], target)

    assert result.outcome is SyncOutcome.NO_OUTPUT
    assert "docushift reframe" in result.message
    assert [f.code for f in findings.all] == ["SYNC_MERGE_UNAVAILABLE"]
    assert not (target / TREE).exists()


def test_a_merged_tree_older_than_the_conversion_beneath_it_is_refused(
    config, catalog, target, product
) -> None:
    """The comparison `reframe` already makes for its own currency, read from the
    same version metadata -- so a merge `docushift reframe` would rebuild is one
    `sync` declines to publish, and the two stages cannot disagree about "current".
    """
    convert_output(config, product, "10.4.0")
    reframe_output(config, product, "10.4.0")
    opt_in(config, product.slug)
    catalog.state.set_version_metadata(product.slug, "10.4.0", "convert_source_checksum", "new")
    catalog.state.set_version_metadata(product.slug, "10.4.0", "reframe_source_checksum", "old")
    findings = FindingsRun("sync")
    distributor = WorkspaceDistributor(config, catalog, findings=findings)

    result = distributor.sync_one(product, product.versions["10.4.0"], target)

    assert result.outcome is SyncOutcome.NO_OUTPUT
    assert "older than the conversion" in result.message
    assert [f.code for f in findings.all] == ["SYNC_MERGE_UNAVAILABLE"]


def test_a_merge_with_no_recorded_checksum_cannot_claim_currency(
    config, catalog, target, product
) -> None:
    """No recorded provenance, no currency claim -- the rule `reframe` inherited
    from `convert`, and the safe direction. The six DataSynapse Flare versions have
    no `convert_source_checksum` at all and land here."""
    convert_output(config, product, "10.4.0")
    reframe_output(config, product, "10.4.0")
    opt_in(config, product.slug)
    findings = FindingsRun("sync")
    distributor = WorkspaceDistributor(config, catalog, findings=findings)

    result = distributor.sync_one(product, product.versions["10.4.0"], target)

    assert result.outcome is SyncOutcome.NO_OUTPUT
    assert "no source checksum" in result.message


def test_opting_in_does_not_re_merge_anything(config) -> None:
    """`publish` is the one policy field kept out of the currency digest. In it, a
    sign-off commit would re-merge the whole doc set -- and invalidate every tree
    already built, because a new field changes the digest of every policy."""
    from docushift.reframe import policy_for

    before = policy_for({"defaults": {"max_words": 3000}}, "tibco-ems")
    after = policy_for({"defaults": {"max_words": 3000, "publish": True}}, "tibco-ems")

    assert not before.publish
    assert after.publish
    assert before.key == after.key
    assert policy_for({"defaults": {"max_words": 2000}}, "tibco-ems").key != before.key


def test_the_documents_doc_classes_are_untouched_by_the_choice(
    config, catalog, distributor, product, target
) -> None:
    """`online-help` is the only doc-class Reframe produces. The PDFs come from the
    extracted tree and a merge has nothing to say about them."""
    extract_tree(config, product, "10.4.0", **{"doc/guide.pdf": "%PDF-1.4\n"})
    opt_in(config, product.slug)

    results = distributor.sync_documents(product, product.versions["10.4.0"], target)

    assert [r.outcome for r in results] == [SyncOutcome.SYNCED]
    assert not any(r.merged for r in results)


# -- the published redirect map (Phase 20d.1) -------------------------------------
#
# The transform is one line; the tests are about the assembly, because that is
# where the drop-down's bug lives and a 301 map has the same one. A scoped run
# that publishes a map for the version it touched and drops the other five is the
# failure mode, and it reports success.

REDIRECT_MAP = "redirects.yml"
MERGED = "redirects:\n- from: users-guide/old.md\n  to: users-guide/new.md#old\n  status: 301\n"


def published_map(target: Path, product: Product) -> dict:
    path = target / TREE / "en-us" / product.slug / ONLINE_HELP / REDIRECT_MAP
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def merged_version(config: ConfigManager, catalog, product: Product, number: str,
                   body: str = MERGED) -> None:
    """A version set up to publish merged, with a redirect map of its own."""
    convert_output(config, product, number)
    reframe_output(config, product, number, **{REDIRECT_MAP: body, "users-guide/new.md": "# new\n"})
    current(catalog, product.slug, number)


def test_the_published_map_carries_tree_rooted_urls_for_every_merged_version(
    config, catalog, distributor, product, target
) -> None:
    """Both sides transform, and both take the same prefix -- `from` is the
    pre-merge published path of a topic that lived in the same version folder."""
    opt_in(config, product.slug)
    for number in ("10.4.0", "10.3.1"):
        merged_version(config, catalog, product, number)

    distributor.sync_many([(product, v) for v in product.versions.values()], target)

    rows = published_map(target, product)["redirects"]
    assert [row["from"] for row in rows] == [
        f"{SERVED}/tibco-ems/online-help/10-3-1/users-guide/old.html",
        f"{SERVED}/tibco-ems/online-help/10-4-0/users-guide/old.html",
    ]
    assert rows[0]["to"] == f"{SERVED}/tibco-ems/online-help/10-3-1/users-guide/new.html#old"
    assert all(row["status"] == 301 for row in rows)


def test_no_row_carries_a_host_while_publish_base_url_is_empty(
    config, catalog, distributor, product, target
) -> None:
    """The shipped state and a deliberate one (6e): the path is the part this tool
    can derive, and a map missing only its prefix is a search-and-replace away."""
    opt_in(config, product.slug)
    merged_version(config, catalog, product, "10.4.0")

    distributor.sync_many([(product, product.versions["10.4.0"])], target)

    rows = published_map(target, product)["redirects"]
    assert rows and not any("://" in row["to"] for row in rows)
    assert all(row["to"].startswith(SERVED) for row in rows)


def test_a_configured_base_prefixes_every_row(
    config, catalog, distributor, product, target
) -> None:
    (config.config_dir / "publishing.yaml").write_text(
        'publish_base_url: "https://docs.example.com/"\n', encoding="utf-8"
    )
    opt_in(config, product.slug)
    merged_version(config, catalog, product, "10.4.0")

    distributor.sync_many([(product, product.versions["10.4.0"])], target)

    rows = published_map(target, product)["redirects"]
    assert rows[0]["from"] == (
        f"https://docs.example.com/{SERVED}/tibco-ems/online-help/10-4-0/users-guide/old.html"
    )


def test_a_scoped_run_leaves_the_other_versions_redirects_in_place(
    config, catalog, distributor, product, target
) -> None:
    """The bug this file exists for, in its 301 form. `sync --version 10.4.0`
    touches one folder out of six; a map assembled from the run's write list would
    publish redirects for that one and 404 the rest -- and report success."""
    opt_in(config, product.slug)
    for number in ("10.4.0", "10.3.1"):
        merged_version(config, catalog, product, number)
    distributor.sync_many([(product, v) for v in product.versions.values()], target)

    distributor.sync_many([(product, product.versions["10.4.0"])], target)

    segments = {row["from"].split("/")[4] for row in published_map(target, product)["redirects"]}
    assert segments == {"10-4-0", "10-3-1"}


def test_a_row_written_under_the_old_url_shape_is_replaced_not_duplicated(
    config, catalog, distributor, product, target
) -> None:
    """Phase 29's migration, and the reason it needs a test of its own.

    `prefix` is both what this tool writes *and* how `owned_prefixes` decides
    which rows it may replace. Correcting the served shape -- dropping the
    repository segment, `en-us` -> `us/en`, `.md` -> `.html` -- therefore
    orphaned the 17,252 rows already published: unrecognised, they would survive
    verbatim beside a full set of replacements and double every map, half of it
    pointing at URLs that never existed.

    Invisible until it has already happened, which is why it is pinned here.
    """
    opt_in(config, product.slug)
    merged_version(config, catalog, product, "10.4.0")
    distributor.sync_many([(product, product.versions["10.4.0"])], target)

    # Rewrite the published map the way a pre-Phase-29 run would have left it.
    path = target / TREE / "en-us" / product.slug / ONLINE_HELP / REDIRECT_MAP
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    legacy = f"{TREE}/en-us/tibco-ems/online-help/10-4-0/users-guide"
    document["redirects"] = [
        {"from": f"{legacy}/old.md", "to": f"{legacy}/new.md#old", "status": 301}
    ]
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")

    distributor.sync_many([(product, product.versions["10.4.0"])], target)

    rows = published_map(target, product)["redirects"]
    assert len(rows) == 1
    assert rows[0]["from"] == f"{SERVED}/tibco-ems/online-help/10-4-0/users-guide/old.html"


def test_a_locale_splits_region_first_because_that_is_how_it_is_served() -> None:
    """`publishing.yaml` stores language-region; the platform serves
    country-then-language. Getting it backwards is invisible in a diff and wrong
    in every row."""
    from docushift.sync.redirects import region_and_language

    assert region_and_language("en-us") == "us/en"
    assert region_and_language("ja-jp") == "jp/ja"
    # Nothing to split: left exactly as it is rather than guessed at.
    assert region_and_language("loc") == "loc"


def test_a_hand_added_redirect_survives_a_resync(
    config, catalog, distributor, product, target
) -> None:
    """`version.yml`'s rule, for its reason. A stale row is a wart `validate` can
    name; a deleted one is a URL that 404s with no record that it ever worked."""
    opt_in(config, product.slug)
    merged_version(config, catalog, product, "10.4.0")
    distributor.sync_many([(product, product.versions["10.4.0"])], target)
    path = target / TREE / "en-us" / product.slug / ONLINE_HELP / REDIRECT_MAP
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    document["redirects"].append({"from": "legacy/ems.html", "to": "https://elsewhere/", "status": 302})
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")

    distributor.sync_many([(product, product.versions["10.4.0"])], target)

    rows = published_map(target, product)["redirects"]
    assert {"from": "legacy/ems.html", "to": "https://elsewhere/", "status": 302} in rows
    assert len(rows) == 2


def test_a_product_that_publishes_nothing_merged_gets_no_map_at_all(
    config, distributor, product, target
) -> None:
    """Writing every product an empty map would put a 301 file into seventeen
    trees with no redirects to serve. Absence is the honest answer."""
    convert_output(config, product, "10.4.0")

    distributor.sync_many([(product, product.versions["10.4.0"])], target)

    assert (target / TREE / "en-us" / product.slug / ONLINE_HELP / "version.yml").is_file()
    assert not (target / TREE / "en-us" / product.slug / ONLINE_HELP / REDIRECT_MAP).exists()


def test_an_unparseable_published_map_is_left_alone_and_named(
    config, catalog, distributor, product, target
) -> None:
    opt_in(config, product.slug)
    merged_version(config, catalog, product, "10.4.0")
    folder = target / TREE / "en-us" / product.slug / ONLINE_HELP
    folder.mkdir(parents=True, exist_ok=True)
    (folder / REDIRECT_MAP).write_text("redirects: not-a-list\n", encoding="utf-8")

    stats = distributor.sync_many([(product, product.versions["10.4.0"])], target)

    assert (folder / REDIRECT_MAP).read_text(encoding="utf-8") == "redirects: not-a-list\n"
    assert any(REDIRECT_MAP in entry for entry in stats.unparsed)
    assert stats.redirect_maps == 0


def test_the_pdf_doc_classes_get_no_redirect_map(
    config, catalog, distributor, product, target
) -> None:
    """`online-help` is the only doc-class Reframe produces, and a PDF has no topic
    that moved."""
    opt_in(config, product.slug)
    merged_version(config, catalog, product, "10.4.0")
    extract_tree(config, product, "10.4.0", **{"doc/guide.pdf": "%PDF-1.4\n"})

    distributor.sync_many([(product, product.versions["10.4.0"])], target)

    root = target / TREE / "en-us" / product.slug
    written = sorted(p.parent.name for p in root.rglob(REDIRECT_MAP))
    assert written == ["10-4-0", ONLINE_HELP]


def test_the_per_version_map_is_published_unchanged_beside_it(
    config, catalog, distributor, product, target
) -> None:
    """Two files, two jobs. The version-root map stays relative -- it is Reframe's
    record, it is what `validate` resolves against the folder it sits in, and
    rewriting it in place would break the copy's own currency check."""
    opt_in(config, product.slug)
    merged_version(config, catalog, product, "10.4.0")

    distributor.sync_many([(product, product.versions["10.4.0"])], target)

    inner = target / TREE / "en-us" / product.slug / ONLINE_HELP / "10-4-0" / REDIRECT_MAP
    assert inner.read_text(encoding="utf-8") == MERGED


# -- the published origin map (Phase 22) ------------------------------------------
#
# Same assembly, same four rules, one asymmetry: `from` is an address on
# docs.tibco.com that this tool has never written, so it is not prefixed and
# entitlement is read off `to`. Both halves of that are load-bearing, and getting
# either wrong is silent -- a map that looks right and 301s nowhere.

ORIGIN_MAP = "301.yml"
ORIGINS = (
    "redirects:\n"
    "- from: https://docs.tibco.com/pub/ems/10.4.0/doc/html/users-guide/old.htm\n"
    "  to: users-guide/new.md#old\n"
    "  status: 301\n"
)


def published_origins(target: Path, product: Product) -> dict:
    path = target / TREE / "en-us" / product.slug / ONLINE_HELP / ORIGIN_MAP
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def origin_version(config: ConfigManager, catalog, product: Product, number: str) -> None:
    """A merged version carrying both maps, which is what Reframe now writes."""
    convert_output(config, product, number)
    reframe_output(config, product, number, **{
        REDIRECT_MAP: MERGED,
        ORIGIN_MAP: ORIGINS.replace("10.4.0", number),
        "users-guide/new.md": "# new\n",
    })
    current(catalog, product.slug, number)


def test_the_origin_map_prefixes_the_destination_and_leaves_the_live_url_alone(
    config, catalog, distributor, product, target
) -> None:
    """The one place this map differs from its sibling. `from` is already an
    absolute docsite URL; prefixing it would bury a live host in the middle of a
    published path, which is neither valid nor obviously wrong at a glance."""
    opt_in(config, product.slug)
    origin_version(config, catalog, product, "10.4.0")

    distributor.sync_many([(product, product.versions["10.4.0"])], target)

    rows = published_origins(target, product)["redirects"]
    assert [row["from"] for row in rows] == [
        "https://docs.tibco.com/pub/ems/10.4.0/doc/html/users-guide/old.htm"
    ]
    assert rows[0]["to"] == f"{SERVED}/tibco-ems/online-help/10-4-0/users-guide/new.html#old"
    assert rows[0]["status"] == 301


def test_a_scoped_run_leaves_the_other_versions_origin_rows_in_place(
    config, catalog, distributor, product, target
) -> None:
    opt_in(config, product.slug)
    for number in ("10.4.0", "10.3.1"):
        origin_version(config, catalog, product, number)
    distributor.sync_many([(product, v) for v in product.versions.values()], target)

    distributor.sync_many([(product, product.versions["10.4.0"])], target)

    rows = published_origins(target, product)["redirects"]
    assert {row["to"].split("/")[4] for row in rows} == {"10-4-0", "10-3-1"}


def test_the_origin_map_regenerates_its_own_rows_rather_than_duplicating_them(
    config, catalog, distributor, product, target
) -> None:
    """Entitlement on `to`, not `from`. Reading it off `from` would match no
    prefix this tool owns, so every run would append a second copy of every row
    and the map would grow without bound while every assertion above still held."""
    opt_in(config, product.slug)
    origin_version(config, catalog, product, "10.4.0")

    distributor.sync_many([(product, product.versions["10.4.0"])], target)
    distributor.sync_many([(product, product.versions["10.4.0"])], target)

    assert len(published_origins(target, product)["redirects"]) == 1


def test_a_hand_added_origin_row_survives_a_resync(
    config, catalog, distributor, product, target
) -> None:
    """A legacy URL a human mapped by hand points outside every version segment
    this tool publishes, so it is outside the entitled set and is carried
    through verbatim -- the drop-down's rule, in the file it matters most."""
    opt_in(config, product.slug)
    origin_version(config, catalog, product, "10.4.0")
    distributor.sync_many([(product, product.versions["10.4.0"])], target)
    path = target / TREE / "en-us" / product.slug / ONLINE_HELP / ORIGIN_MAP
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    hand = {"from": "https://docs.tibco.com/ems.html", "to": "https://elsewhere/", "status": 302}
    document["redirects"].append(hand)
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")

    distributor.sync_many([(product, product.versions["10.4.0"])], target)

    rows = published_origins(target, product)["redirects"]
    assert hand in rows
    assert len(rows) == 2


def test_a_product_with_no_declared_origin_template_gets_no_origin_map(
    config, catalog, distributor, product, target
) -> None:
    """Reframe writes no per-version `301.yml` for an undeclared product, so there
    is nothing to assemble. The alternative -- an empty file in seventeen trees --
    reads as "this product has no redirects" rather than "nobody said where it
    lives today", and only one of those is true."""
    opt_in(config, product.slug)
    merged_version(config, catalog, product, "10.4.0")

    distributor.sync_many([(product, product.versions["10.4.0"])], target)

    folder = target / TREE / "en-us" / product.slug / ONLINE_HELP
    assert (folder / REDIRECT_MAP).is_file()
    assert not (folder / ORIGIN_MAP).exists()


def test_an_unparseable_published_origin_map_is_left_alone_and_named(
    config, catalog, distributor, product, target
) -> None:
    opt_in(config, product.slug)
    origin_version(config, catalog, product, "10.4.0")
    folder = target / TREE / "en-us" / product.slug / ONLINE_HELP
    folder.mkdir(parents=True, exist_ok=True)
    (folder / ORIGIN_MAP).write_text("redirects: not-a-list\n", encoding="utf-8")

    stats = distributor.sync_many([(product, product.versions["10.4.0"])], target)

    assert (folder / ORIGIN_MAP).read_text(encoding="utf-8") == "redirects: not-a-list\n"
    assert any(ORIGIN_MAP in entry for entry in stats.unparsed)


# -- Phase 34 review: what publishing wrote wrong (R10) ------------------------------


def test_an_archived_version_marked_for_migration_is_listed_in_the_drop_down(
    config, catalog, product, target
) -> None:
    """R10-01. `sync` selects what `download` selects, which includes an archived
    row with `convert_eligible=true` -- 88 of them on 45 products. Placed and left
    out of `version.yml`, its folders were published with no page linking to them;
    for `tibco-designer` 5.10.0 that was the product's only content."""
    archived = ProductVersion(slug="tibco-ems", version="5.10.0", is_archived=True,
                              convert_eligible=True, release_date="")
    product.versions = {"5.10.0": archived}
    extract_tree(config, product, "5.10.0", **SHIPMENT)
    findings = FindingsRun("sync")

    WorkspaceDistributor(config, catalog, findings=findings).sync_many([(product, archived)], target)

    for doc_class in (USER_GUIDES, RELEASE_INFORMATION):
        path = published(target, "5-10-0", doc_class).parent / "version.yml"
        rows = yaml.safe_load(path.read_text(encoding="utf-8"))["versions"]
        assert [row["path"] for row in rows] == ["/5-10-0"]
    # Reported exactly when it is listed, like any other drop-down row. (The stub
    # PDFs are also noted as unreadable, which is not this test's business.)
    assert "VERSION_UNDATED" in [f.code for f in findings.all]


def test_setting_the_host_replaces_the_published_rows_instead_of_doubling_them(
    config, catalog, distributor, product, target
) -> None:
    """R10-02. Ownership was decided against prefixes built from the base set
    *now*, so the first sync after `publish_base_url` was filled in kept every
    host-less row as foreign and wrote a hosted copy beside it: 17,252 rows became
    34,504 on an EMS copy, and the run reported success."""
    opt_in(config, product.slug)
    origin_version(config, catalog, product, "10.4.0")
    distributor.sync_many([(product, product.versions["10.4.0"])], target)
    assert len(published_map(target, product)["redirects"]) == 1
    assert len(published_origins(target, product)["redirects"]) == 1

    def resync_under(base: str) -> None:
        # A fresh read of `publishing.yaml`, as the next `docushift sync` would do.
        (config.config_dir / "publishing.yaml").write_text(
            f'publish_base_url: "{base}"\n', encoding="utf-8"
        )
        config._publishing_cache = None
        distributor.sync_many([(product, product.versions["10.4.0"])], target)

    resync_under("https://docs.example.com")

    for rows in (published_map(target, product)["redirects"],
                 published_origins(target, product)["redirects"]):
        assert len(rows) == 1
        assert rows[0]["to"].startswith("https://docs.example.com/us/en/")

    # On to another host, or back to none: the path decides, not the host.
    resync_under("https://other.example.com")
    resync_under("")
    rows = published_origins(target, product)["redirects"]
    assert len(rows) == 1
    assert rows[0]["to"].startswith(f"{SERVED}/")


def test_a_leftover_staging_folder_is_not_published_into_the_doc_class_map(
    config, catalog, distributor, product, target
) -> None:
    """R10-03. A hard-killed run never reaches `_place`'s cleanup. The next run's
    map assembly read the staging folder's per-version `301.yml` like a published
    version's: 1,171 of 7,070 Streaming rows pointed into `11-1-0.part`."""
    opt_in(config, product.slug)
    origin_version(config, catalog, product, "10.4.0")
    distributor.sync_many([(product, product.versions["10.4.0"])], target)
    folder = target / TREE / "en-us" / product.slug / ONLINE_HELP
    leftover = folder / "10-3-1.part"
    leftover.mkdir()
    (leftover / ORIGIN_MAP).write_text(ORIGINS, encoding="utf-8")
    (leftover / REDIRECT_MAP).write_text(MERGED, encoding="utf-8")

    distributor.sync_many([(product, product.versions["10.4.0"])], target)

    for rows in (published_map(target, product)["redirects"],
                 published_origins(target, product)["redirects"]):
        assert not any(".part" in row["to"] for row in rows)
        assert len(rows) == 1


def test_a_failed_archive_placement_leaves_no_part_directory_behind(
    config, distributor, product, target, monkeypatch
) -> None:
    """R10-09. The other three placers remove their staging sibling on failure;
    this one left `archives.part` in the published tree until the next run."""
    product.versions["9.1.0"] = ProductVersion(slug="tibco-ems", version="9.1.0", is_archived=True)

    def explode(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("docushift.sync.distributor.swap", explode)

    result = distributor.sync_archives(product, target)

    assert result.outcome is SyncOutcome.FAILED
    assert not resources(target, "archives.part").exists()


def test_a_document_that_cannot_be_read_fails_its_row_rather_than_the_run(
    config, distributor, product, target, monkeypatch
) -> None:
    """R10-11. `sync_documents` says it never raises, but its currency check and
    its titling both read the source files outside the guard. An `OSError` there
    escaped `sync_many` and lost the run's findings with it."""
    extract_tree(config, product, "10.4.0", **SHIPMENT)

    def explode(files):
        raise PermissionError("locked")

    monkeypatch.setattr("docushift.sync.distributor.document_index.entries_for", explode)

    stats = distributor.sync_many([(product, product.versions["10.4.0"])], target)

    failed = {r.doc_class for r in stats.failures}
    assert failed == {USER_GUIDES, RELEASE_INFORMATION, REFERENCE_DOCUMENTS}
    assert all("locked" in r.message for r in stats.failures)


# -- Phase 34 review: published copies that went stale unseen (R10) -------------------


def test_a_doc_class_the_package_no_longer_feeds_is_withdrawn_and_reported(
    config, distributor, product, target
) -> None:
    """R10-05. The swap replaced a version folder only when its doc-class still
    routed something, so a re-extracted package that dropped its readme and release
    notes kept `release-information/10-4-0/`, its drop-down row, and no report row."""
    source = extract_tree(config, product, "10.4.0", **SHIPMENT)
    distributor.sync_many([(product, product.versions["10.4.0"])], target)
    (source / "doc" / "readme.txt").unlink()
    (source / "pdf" / "tib_ems_relnotes.pdf").unlink()

    stats = distributor.sync_many([(product, product.versions["10.4.0"])], target)

    (row,) = [r for r in stats.results if r.doc_class == RELEASE_INFORMATION]
    assert row.outcome is SyncOutcome.NO_OUTPUT
    assert "removed" in row.message
    assert not published(target, doc_class=RELEASE_INFORMATION).exists()
    dropdown = published(target, doc_class=RELEASE_INFORMATION).parent / "version.yml"
    assert not (yaml.safe_load(dropdown.read_text(encoding="utf-8")) or {}).get("versions")
    # The doc-classes the package still feeds are untouched by the withdrawal.
    assert published(target, doc_class=USER_GUIDES).is_dir()


def test_a_missing_extracted_tree_withdraws_nothing(config, distributor, product, target) -> None:
    """The other absence, and it stays recoverable: a tree that is gone says
    nothing about what the package ships, so the published folders are left."""
    source = extract_tree(config, product, "10.4.0", **SHIPMENT)
    distributor.sync_many([(product, product.versions["10.4.0"])], target)
    shutil.rmtree(source)

    distributor.sync_many([(product, product.versions["10.4.0"])], target)

    assert published(target, doc_class=RELEASE_INFORMATION).is_dir()
    assert published(target, doc_class=USER_GUIDES).is_dir()


def test_an_api_tree_the_package_no_longer_carries_is_withdrawn_and_reported(
    config, distributor, product, target
) -> None:
    """R10-05, in the `-resources` tree: `return []` once no API root remained
    left the old Javadoc published with no row."""
    source = javadoc_tree(config, product, "10.4.0", "html/api-docs/java")
    version = product.versions["10.4.0"]
    distributor.sync_api_references(product, version, target)
    shutil.rmtree(source / "html")

    (row,) = distributor.sync_api_references(product, version, target)

    assert row.outcome is SyncOutcome.NO_OUTPUT
    assert "removed" in row.message
    assert not resources(target, "api-references", "10-4-0").exists()


def test_a_merge_built_before_a_forced_re_conversion_is_refused(
    config, catalog, target, product
) -> None:
    """R10-06. Both recorded checksums are the *package's*, and `convert --force`
    leaves it unchanged, so a merge built from the previous conversion matched and
    was published as current. Which tree was built last is read off the trees."""
    opt_in(config, product.slug)
    merged_version(config, catalog, product, "10.4.0")
    later = time.time() + 60
    converted = config.output_path(product.bu, product.family, product.slug, "10.4.0")
    os.utime(converted / "index.md", (later, later))  # `convert --force`, after the merge
    findings = FindingsRun("sync")
    distributor = WorkspaceDistributor(config, catalog, findings=findings)

    result = distributor.sync_one(product, product.versions["10.4.0"], target)

    assert result.outcome is SyncOutcome.NO_OUTPUT
    assert "reframe --force" in result.message
    assert [f.code for f in findings.all] == ["SYNC_MERGE_UNAVAILABLE"]


def test_a_catalog_rename_is_not_reported_current_by_the_document_indexes(
    config, distributor, product, target
) -> None:
    """R10-10. The index title comes from `display_name`, not from the files, so a
    rename in `products.csv` left every copied file current and the three document
    indexes publishing the old name until `--force`."""
    extract_tree(config, product, "10.4.0", **SHIPMENT)
    distributor.sync_many([(product, product.versions["10.4.0"])], target)
    product.display_name = "Spotfire Enterprise Message Service"

    stats = distributor.sync_many([(product, product.versions["10.4.0"])], target)

    documents = [r for r in stats.results if r.doc_class == USER_GUIDES]
    assert [r.outcome for r in documents] == [SyncOutcome.SYNCED]
    folder = published(target, doc_class=USER_GUIDES)
    assert "Spotfire Enterprise Message Service 10.4.0" in (folder / "toc.yml").read_text(encoding="utf-8")
    assert "Spotfire Enterprise Message Service 10.4.0" in (folder / "index.md").read_text(encoding="utf-8")
    # And once rewritten, current again.
    again = distributor.sync_many([(product, product.versions["10.4.0"])], target)
    assert {r.outcome for r in again.results if r.doc_class == USER_GUIDES} == {SyncOutcome.CURRENT}
