"""Unit tests for Stage 4's first half: unpack, then identify (design.md §6.1, §7).

Trees are built on disk from a dict of `path -> text`, the same reasoning as
`test_downloader.py`'s in-memory ZIPs: a committed fixture tree tells the next
reader nothing about which marker it is there to exercise, whereas
`{"help/Skins/x.css": ""}` says it in one line.

The headline case is `test_a_webworks_tree_with_a_skins_directory_is_not_flare`.
`Skins/` and `Data/` were dropped from the Flare marker list on 2026-09-08
because they account for all 94 false positives the seven-marker list produced
over 1,822 versions, and 17 of those are WebWorks. This is the regression that
survey paid for.
"""

import io
import zipfile
from pathlib import Path

import pytest

from docushift.catalog import CatalogManager
from docushift.config import ConfigManager
from docushift.engines import detect_version, find_output_roots, owning_root
from docushift.extractor import ExtractOutcome, PackageExtractor
from docushift.models import (
    ConversionStatus,
    EngineSource,
    Product,
    ProductVersion,
    SourceEngine,
)
from tests.conftest import make_product, make_version

# -- helpers -----------------------------------------------------------------


def build_tree(root: Path, members: dict[str, str]) -> Path:
    """Writes `path -> text` under `root`. A trailing `/` makes an empty directory."""
    for name, text in members.items():
        if name.endswith("/"):
            (root / name).mkdir(parents=True, exist_ok=True)
            continue
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def zip_bytes(members: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, text in members.items():
            archive.writestr(name, text)
    return buffer.getvalue()


def detect(tmp_path: Path, members: dict[str, str], name: str = "tree"):
    return detect_version(build_tree(tmp_path / name, members))


# Enough of a page for pass 2 and 3 to have something to read.
def page(head: str = "", body: str = "text") -> str:
    return f"<html><head>{head}</head><body>{body}</body></html>"


# -- pass 1: layout markers (design.md §7.1) ---------------------------------


@pytest.mark.parametrize(
    ("members", "engine"),
    [
        ({"help/Output.mcwebhelp": "", "help/index.html": page()}, SourceEngine.FLARE),
        ({"help/csh.js": "", "help/index.html": page()}, SourceEngine.FLARE),
        ({"help/build.mclog": ""}, SourceEngine.FLARE),
        ({"help/MicroContent/x.htm": page()}, SourceEngine.FLARE),
        ({"help/_globalpages/x.htm": page()}, SourceEngine.FLARE),
        # `wwhdata/` alone carries the WebWorks row: 195 of 195 versions, zero
        # false positives and zero false negatives. 17 versions are stripped to
        # `wwhdata/files.htm` and have no `wwhelp/` at all.
        ({"book/wwhdata/files.htm": page()}, SourceEngine.WEBWORKS),
        ({"book/wwhelp/wwhimpl/x.js": ""}, SourceEngine.WEBWORKS),
        ({"topics/GUID-1234-ABCD.html": page()}, SourceEngine.DITA),
        ({"static/head.js": "", "static/body.js": "", "a.html": page()}, SourceEngine.DITA),
        ({"lib/snext.css": ""}, SourceEngine.R_HELP),
        ({"lib/snextchm.css": ""}, SourceEngine.R_HELP),
    ],
)
def test_a_layout_marker_decides_the_engine(
    tmp_path: Path, members: dict[str, str], engine: SourceEngine
) -> None:
    result = detect(tmp_path, members)

    assert result.engine is engine
    assert result.decided_by == 1


def test_a_webworks_tree_with_a_skins_directory_is_not_flare(tmp_path: Path) -> None:
    """The regression the 2026-09-08 survey paid for (§7.1).

    Under the old seven-marker list this detected as Flare, and Flare outranks
    WebWorks, so the wrong converter would have run silently on 17 real versions.
    """
    result = detect(
        tmp_path,
        {
            "book/Skins/Default/skin.css": "",
            "book/Data/toc.js": "",
            "book/wwhdata/files.htm": page(),
        },
    )

    assert result.engine is SourceEngine.WEBWORKS


def test_a_bare_data_directory_is_not_a_flare_signal(tmp_path: Path) -> None:
    """`Data/` is 88.0% precise on its own -- 36 versions ship one with no Flare runtime."""
    result = detect(tmp_path, {"guide/Data/notes.xml": "<x/>", "guide/index.html": page()})

    assert result.engine is SourceEngine.AUTO


def test_flare_outranks_webworks_in_a_mixed_bundle(tmp_path: Path) -> None:
    """19 corpus versions carry both -- a Flare output with a WebWorks tree beside it."""
    result = detect(
        tmp_path,
        {"guide/Output.mcwebhelp": "", "legacy/wwhdata/files.htm": page()},
    )

    assert result.engine is SourceEngine.FLARE
    # And the ambiguity survives into the map rather than being flattened away.
    assert result.folders == {"guide": SourceEngine.FLARE, "legacy": SourceEngine.WEBWORKS}


# -- pass 2: content signatures ----------------------------------------------


def test_docbook_is_found_only_by_content(tmp_path: Path) -> None:
    """DocBook's flat HTML output has no distinctive layout at all."""
    result = detect(
        tmp_path, {"ch01.html": page("<!-- Generated by DocBook XSL Stylesheets v1.79 -->")}
    )

    assert result.engine is SourceEngine.DOCBOOK
    assert result.decided_by == 2


def test_the_madcap_namespace_identifies_flare_without_a_marker(tmp_path: Path) -> None:
    result = detect(tmp_path, {"t.htm": '<html xmlns:MadCap="http://www.madcapsoftware.com/">x</html>'})

    assert result.engine is SourceEngine.FLARE


@pytest.mark.parametrize("marker", ["DC.Type", "DC.type", "dc.identifier"])
def test_the_dc_meta_tags_are_matched_case_insensitively(tmp_path: Path, marker: str) -> None:
    """A case-sensitive match drops all 66 versions of the lowercase flavour (§7.2).

    It did exactly that once during the survey and produced a confident, wrong
    correction of 371 down to 316.
    """
    result = detect(tmp_path, {"t.html": page(f'<meta name="{marker}" content="topic"/>')}, name=marker)

    assert result.engine is SourceEngine.DITA


def test_r_help_is_found_by_its_classes(tmp_path: Path) -> None:
    result = detect(tmp_path, {"fn.html": page(body='<h1 class="RdTitle">fn</h1>')})

    assert result.engine is SourceEngine.R_HELP


# -- pass 3: the generator tag -----------------------------------------------


@pytest.mark.parametrize(
    ("generator", "engine"),
    [
        ("Adobe RoboHelp 11", SourceEngine.ROBOHELP),
        ("Microsoft FrontPage 6.0", SourceEngine.FRONTPAGE),
        ("Help &amp; Manual", SourceEngine.OTHER),
        ("mkdocs-material", SourceEngine.MKDOCS),
        ("Docusaurus v2.4.1", SourceEngine.DOCUSAURUS),
        ("Apache Maven Doxia Site Renderer", SourceEngine.DOXIA),
        ("WebWorks ePublisher Pro", SourceEngine.WEBWORKS),
    ],
)
def test_the_generator_tag_names_the_long_tail(
    tmp_path: Path, generator: str, engine: SourceEngine
) -> None:
    result = detect(
        tmp_path, {"p.html": page(f'<meta name="generator" content="{generator}">')}, name=engine
    )

    assert result.engine is engine
    assert result.decided_by == 3


def test_an_unmapped_generator_is_other_and_keeps_its_raw_string(tmp_path: Path) -> None:
    """`other` alone is unactionable; the string is what a human triages from."""
    result = detect(tmp_path, {"p.html": page('<meta name="generator" content="Whizzy Docs 3">')})

    assert result.engine is SourceEngine.OTHER
    assert result.generator_raw == "whizzy docs 3"


# -- never guess (§7.3 step 1) -----------------------------------------------


def test_a_tree_matching_nothing_stays_auto(tmp_path: Path) -> None:
    """A wrong engine does not fail -- it produces silently wrong Markdown."""
    result = detect(tmp_path, {"readme.html": page(), "notes/a.html": page()})

    assert result.engine is SourceEngine.AUTO
    assert result.decided_by == 0
    assert not result.sample_exhausted


def test_an_exhausted_sample_is_distinguishable_from_an_empty_one(tmp_path: Path) -> None:
    """"We stopped looking" and "there was nothing there" are different report lines."""
    members = {f"topics/t{index}.html": page() for index in range(260)}

    result = detect(tmp_path, members)

    assert result.engine is SourceEngine.AUTO
    assert result.sample_exhausted
    assert result.html_files == 260


def test_the_folder_map_records_every_guide_folder(tmp_path: Path) -> None:
    """One version's ZIP commonly bundles nine sibling guide folders (§7.3 step 4)."""
    members = {f"guide{index}/Output.mcwebhelp": "" for index in range(9)}

    result = detect(tmp_path, members)

    assert len(result.folders) == 9
    assert set(result.folders.values()) == {SourceEngine.FLARE}


# -- output roots (design.md §7.1, architecture.md §5.1.1) -------------------


def test_flare_roots_are_found_by_content_and_nest(tmp_path: Path) -> None:
    """51 of 595 versions ship more than one root, and 153 roots nest inside another."""
    tree = build_tree(
        tmp_path / "flare",
        {
            "admin/Data/HelpSystem.xml": "<x/>",
            "admin/sub/Data/HelpSystem.xml": "<x/>",
            "admin/sub/topic.htm": page(),
            "user/Data/HelpSystem.xml": "<x/>",
        },
    )

    roots = find_output_roots(tree, SourceEngine.FLARE)

    assert [root.relative_to(tree).as_posix() for root in roots] == ["admin", "user", "admin/sub"]
    # The innermost root owns the file; getting this backwards attributes a
    # sub-guide's topics to its parent.
    assert owning_root(tree / "admin" / "sub" / "topic.htm", roots) == tree / "admin" / "sub"


def test_dita_roots_sit_at_no_fixed_depth(tmp_path: Path) -> None:
    tree = build_tree(
        tmp_path / "dita",
        {"GUID-AAA.html": page(), "deep/nested/GUID-BBB.html": page(), "deep/other.html": page()},
    )

    roots = find_output_roots(tree, SourceEngine.DITA)

    assert [root.relative_to(tree).as_posix() for root in roots] == [".", "deep/nested"]


def test_a_webworks_root_is_the_parent_of_wwhdata(tmp_path: Path) -> None:
    tree = build_tree(tmp_path / "ww", {"book/wwhdata/files.htm": page()})

    roots = find_output_roots(tree, SourceEngine.WEBWORKS)

    assert roots == [tree / "book"]


def test_an_engine_with_no_root_rule_reports_none(tmp_path: Path) -> None:
    """Empty means "no rule applies", which callers read as "the tree is the unit"."""
    tree = build_tree(tmp_path / "db", {"ch01.html": page()})

    assert find_output_roots(tree, SourceEngine.DOCBOOK) == []
    assert find_output_roots(tree, SourceEngine.AUTO) == []


# -- extraction (design.md §6.1) ---------------------------------------------


@pytest.fixture
def product(catalog: CatalogManager) -> Product:
    built = make_product("tibco-ems", product_code="ems", family="messaging")
    built.versions = {"10.4.0": make_version("tibco-ems", "10.4.0", zip_url="https://docs.example/ems.zip")}
    catalog.merge_fetch_results([built])
    return catalog.get_product("tibco-ems")


@pytest.fixture
def version(product: Product) -> ProductVersion:
    return product.versions["10.4.0"]


def place_package(config: ConfigManager, product: Product, version: ProductVersion, members: dict) -> Path:
    """Files a ZIP where `download` would have left it."""
    target = config.download_path(product.bu, product.family, product.slug, version.version)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(zip_bytes(members))
    return target


def extract_dir(config: ConfigManager, product: Product, version: ProductVersion) -> Path:
    return config.extract_path(product.bu, product.family, product.slug, version.version)


FLARE_PACKAGE = {"guide/Output.mcwebhelp": "", "guide/Data/HelpSystem.xml": "<x/>", "guide/a.htm": "<html/>"}


def test_extract_unpacks_to_the_canonical_path_and_records_it(
    config: ConfigManager, catalog: CatalogManager, product: Product, version: ProductVersion
) -> None:
    place_package(config, product, version, FLARE_PACKAGE)
    target = extract_dir(config, product, version)

    result = PackageExtractor(config, catalog).extract_one(product, version)

    assert result.outcome is ExtractOutcome.EXTRACTED
    assert result.files == 3
    assert (target / "guide" / "a.htm").is_file()
    state = catalog.state.get_version_state("tibco-ems", "10.4.0")
    assert state["status"] == str(ConversionStatus.EXTRACTED)
    assert state["extract_path"] == str(target)


def test_an_unchanged_package_is_a_no_op(
    config: ConfigManager, catalog: CatalogManager, product: Product, version: ProductVersion
) -> None:
    place_package(config, product, version, FLARE_PACKAGE)
    extractor = PackageExtractor(config, catalog)
    extractor.extract_one(product, version)
    # A file nobody's ZIP contains: a second extract would sweep it away.
    (extract_dir(config, product, version) / "sentinel.txt").write_text("kept", encoding="utf-8")

    result = extractor.extract_one(product, version)

    assert result.outcome is ExtractOutcome.CURRENT
    assert (extract_dir(config, product, version) / "sentinel.txt").is_file()


def test_force_re_extracts_an_unchanged_package(
    config: ConfigManager, catalog: CatalogManager, product: Product, version: ProductVersion
) -> None:
    place_package(config, product, version, FLARE_PACKAGE)
    extractor = PackageExtractor(config, catalog)
    extractor.extract_one(product, version)
    (extract_dir(config, product, version) / "sentinel.txt").write_text("swept", encoding="utf-8")

    result = extractor.extract_one(product, version, force=True)

    assert result.outcome is ExtractOutcome.EXTRACTED
    assert not (extract_dir(config, product, version) / "sentinel.txt").exists()


def test_a_re_extract_does_not_leave_the_previous_packages_files_behind(
    config: ConfigManager, catalog: CatalogManager, product: Product, version: ProductVersion
) -> None:
    """The reason extraction stages into `.part/` and swaps rather than unpacking in place.

    Unpacking over a live directory leaves a guide that was deleted upstream on
    disk forever -- and it converts, and nothing in the report says why.
    """
    place_package(config, product, version, {**FLARE_PACKAGE, "guide/dropped.htm": "<html/>"})
    extractor = PackageExtractor(config, catalog)
    extractor.extract_one(product, version)
    assert (extract_dir(config, product, version) / "guide" / "dropped.htm").is_file()

    place_package(config, product, version, FLARE_PACKAGE)
    extractor.extract_one(product, version)

    assert not (extract_dir(config, product, version) / "guide" / "dropped.htm").exists()
    assert (extract_dir(config, product, version) / "guide" / "a.htm").is_file()


def test_a_leftover_part_directory_is_swept_before_the_next_run(
    config: ConfigManager, catalog: CatalogManager, product: Product, version: ProductVersion
) -> None:
    """The swap is not atomic on Windows, so an interrupted run can leave one."""
    place_package(config, product, version, FLARE_PACKAGE)
    target = extract_dir(config, product, version)
    staging = target.with_name(target.name + ".part")
    staging.mkdir(parents=True)
    (staging / "half-written.htm").write_text("", encoding="utf-8")

    PackageExtractor(config, catalog).extract_one(product, version)

    assert not staging.exists()
    assert not (target / "half-written.htm").exists()


def test_a_missing_package_is_a_report_line_not_a_failure(
    config: ConfigManager, catalog: CatalogManager, product: Product, version: ProductVersion
) -> None:
    result = PackageExtractor(config, catalog).extract_one(product, version)

    assert result.outcome is ExtractOutcome.NO_PACKAGE
    assert "docushift download" in result.message


def test_an_escaping_member_is_refused_and_leaves_nothing_behind(
    config: ConfigManager, catalog: CatalogManager, product: Product, version: ProductVersion
) -> None:
    """Counted apart from `failed`: a retry will not fix it, a human has to look."""
    place_package(config, product, version, {"docs/a.htm": "<html/>", "../escape.txt": "pwned"})
    target = extract_dir(config, product, version)

    result = PackageExtractor(config, catalog).extract_one(product, version)

    assert result.outcome is ExtractOutcome.REFUSED
    assert not target.exists()
    assert not target.with_name(target.name + ".part").exists()
    assert not (target.parent.parent / "escape.txt").exists()


def test_a_package_that_is_not_a_zip_is_a_recorded_failure(
    config: ConfigManager, catalog: CatalogManager, product: Product, version: ProductVersion
) -> None:
    source = config.download_path(product.bu, product.family, product.slug, version.version)
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"<html>sign in to continue</html>")

    result = PackageExtractor(config, catalog).extract_one(product, version)

    assert result.outcome is ExtractOutcome.FAILED
    assert catalog.state.get_version_state("tibco-ems", "10.4.0")["status"] == str(ConversionStatus.ERROR)


# -- identification, written back (design.md §7.3) ---------------------------


def test_the_detected_engine_is_written_back_with_its_provenance(
    config: ConfigManager, catalog: CatalogManager, product: Product, version: ProductVersion
) -> None:
    place_package(config, product, version, FLARE_PACKAGE)

    result = PackageExtractor(config, catalog).extract_one(product, version)

    assert result.engine is SourceEngine.FLARE
    assert result.engine_written
    assert version.engine is SourceEngine.FLARE
    assert version.engine_source is EngineSource.DETECTED


def test_a_manual_engine_is_never_overridden(
    config: ConfigManager, catalog: CatalogManager, product: Product, version: ProductVersion
) -> None:
    catalog.set_version_field("tibco-ems", "10.4.0", "engine", "dita")
    place_package(config, product, version, FLARE_PACKAGE)

    result = PackageExtractor(config, catalog).extract_one(product, version)

    assert version.engine is SourceEngine.DITA
    assert version.engine_source is EngineSource.MANUAL
    # And the reported engine is the one conversion will use, not this run's guess.
    assert result.engine is SourceEngine.DITA
    assert not result.engine_written


def test_a_failed_detection_does_not_clear_an_earlier_answer(
    config: ConfigManager, catalog: CatalogManager, product: Product, version: ProductVersion
) -> None:
    """Refusing to write `auto` is the other half of "never guess"."""
    place_package(config, product, version, FLARE_PACKAGE)
    extractor = PackageExtractor(config, catalog)
    extractor.extract_one(product, version)

    place_package(config, product, version, {"readme.html": "<html><body>x</body></html>"})
    result = extractor.extract_one(product, version)

    assert result.engine is SourceEngine.AUTO
    assert not result.engine_written
    assert version.engine is SourceEngine.FLARE


def test_the_output_roots_and_folder_map_are_recorded(
    config: ConfigManager, catalog: CatalogManager, product: Product, version: ProductVersion
) -> None:
    place_package(config, product, version, FLARE_PACKAGE)

    result = PackageExtractor(config, catalog).extract_one(product, version)

    assert result.roots == 1
    metadata = catalog.state.get_version_metadata("tibco-ems", "10.4.0")
    assert metadata["output_roots"] == "guide"
    assert catalog.state.get_engine_folder_map("tibco-ems", "10.4.0") == {"guide": "flare"}


def test_an_unmapped_generator_string_reaches_state(
    config: ConfigManager, catalog: CatalogManager, product: Product, version: ProductVersion
) -> None:
    place_package(
        config, product, version,
        {"p.html": '<html><head><meta name="generator" content="Whizzy Docs 3"></head></html>'},
    )

    result = PackageExtractor(config, catalog).extract_one(product, version)

    assert result.engine is SourceEngine.OTHER
    metadata = catalog.state.get_version_metadata("tibco-ems", "10.4.0")
    assert metadata["engine_generator_raw"] == "whizzy docs 3"


# -- a run -------------------------------------------------------------------


def test_extract_many_reports_every_outcome(
    config: ConfigManager, catalog: CatalogManager, product: Product
) -> None:
    """One missing package must not stop the rest of a batch."""
    catalog.add_version("tibco-ems", "10.3.0")
    catalog.add_version("tibco-ems", "10.2.0")
    reloaded = catalog.get_product("tibco-ems")
    place_package(config, reloaded, reloaded.versions["10.4.0"], FLARE_PACKAGE)
    place_package(
        config, reloaded, reloaded.versions["10.2.0"], {"docs/a.htm": "x", "../escape.txt": "pwned"}
    )
    pairs = [(reloaded, reloaded.versions[number]) for number in ("10.4.0", "10.3.0", "10.2.0")]
    seen: list[str] = []

    stats = PackageExtractor(config, catalog).extract_many(pairs, on_result=lambda r: seen.append(r.version))

    assert stats.count(ExtractOutcome.EXTRACTED) == 1
    assert stats.count(ExtractOutcome.NO_PACKAGE) == 1
    assert stats.count(ExtractOutcome.REFUSED) == 1
    assert stats.engine_tally() == {SourceEngine.FLARE: 1}
    # Serial, so the order is the selection's and a progress line can be trusted.
    assert seen == ["10.4.0", "10.3.0", "10.2.0"]


def test_an_empty_selection_is_not_an_error(config: ConfigManager, catalog: CatalogManager) -> None:
    stats = PackageExtractor(config, catalog).extract_many([])

    assert stats.results == []
    assert stats.files_written == 0
