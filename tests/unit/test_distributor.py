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
    assert "- [Release Notes](tib_ems_relnotes.pdf)" in index
    toc = yaml.safe_load(folder.joinpath("toc.yml").read_text(encoding="utf-8"))
    assert [row["path"] for row in toc["items"]] == ["tib_ems_relnotes.pdf", "readme.txt"]
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
