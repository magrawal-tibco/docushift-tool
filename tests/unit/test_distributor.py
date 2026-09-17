"""Stage 6b's distributor: the publishing form, the swap boundary, the drop-down.

The scoped-run tests are the point of the file. `sync` takes `--version`, so the
dangerous bug here is not a copy that fails -- it is a copy that succeeds and
quietly unlinks the thirty-seven versions the run did not touch.
"""

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
    assert toc["items"] == [
        {"title": "TIBCO Enterprise Message Service™ 10.4.0 Release Information",
         "path": "index.md"},
    ]
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
    """The rewrite needs `-resources` on disk before the docs tree is staged (§6.4)."""
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
