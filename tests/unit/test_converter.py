"""Unit tests for Stage 5's spine (planning.md Phase 5a).

The spine is proven two ways, and both survive 5b's real engine. With no handler
registered for the version's generator, the version reports `ENGINE_UNKNOWN` --
the honest state, and the one §7.5 already has a code for. With an in-process
fake engine registered by the test and never shipped, the driver runs end to end:
five reference branches, a build-and-swap, an output map, a flat `csh.yml`,
frontmatter in the topic's first write, and the findings.

The fake engine is still the smallest thing that satisfies the contract, and it
stays that way now that `FlareEngine` exists: these tests are about the *driver*,
and asserting on MadCap output here would make a driver failure look like an
engine failure. `test_flare.py` is where the engine is tested.
"""

import re
from pathlib import Path, PurePosixPath
from types import SimpleNamespace

import pytest
import yaml
from click.testing import CliRunner

from docushift.catalog import CatalogManager
from docushift.cli import main
from docushift.config import ConfigManager
from docushift.converter import ConvertOutcome, DocumentConverter
from docushift.engines.base import (
    BaseEngine,
    ConversionContext,
    Document,
    NavNode,
    Unit,
    engine_for,
    register,
    registered_engines,
    unregister,
)
from docushift.engines.roots import find_output_roots
from docushift.extractor import ExtractOutcome, PackageExtractor
from docushift.models import ConversionStatus, EngineSource, Product, ProductVersion, SourceEngine
from docushift.reporting.findings import FindingsRun, Severity
from docushift.transforms import csh
from docushift.utils import textfile
from tests.unit.test_extractor import place_package

ALIAS = """<?xml version="1.0" encoding="utf-8"?>
<CatapultAliasFile>
  <Map Name="install" Link="Content/topic.htm" ResolvedId="1000" />
  <Map Name="1234" Link="Content/gone.htm" ResolvedId="1001" />
</CatapultAliasFile>
"""

TOPIC = """<html><body>
<img src="images/shot.png" />
<img src="images/missing.png" />
<img src="../Skins/Default/logo.gif" />
<img src="../../pdf/guide.pdf" />
<img src="https://docs.example/remote.png" />
</body></html>
"""

# One Flare-shaped package: an output root, a topic exercising all five branches
# of §6.4 step 3, an alias file, an orphan, and a PDF outside the root.
PACKAGE = {
    "guide/Output.mcwebhelp": "",
    "guide/Data/HelpSystem.xml": "<x/>",
    "guide/Data/Alias.xml": ALIAS,
    "guide/Content/topic.htm": TOPIC,
    "guide/Content/second.htm": "<html><body><img src='images/shot.png'/></body></html>",
    "guide/Content/images/shot.png": "png",
    "guide/Content/images/orphan.png": "png",
    "guide/Skins/Default/logo.gif": "gif",
    "pdf/guide.pdf": "pdf",
}

_SRC = re.compile(r"""src=["'](?P<url>[^"']+)["']""")


class FakeEngine(BaseEngine):
    """The smallest engine that satisfies `engines/base.py`. Tests only.

    It resolves every `src` **while emitting the body**, which is the one thing
    invariant 13 requires of a real engine and the one thing a stub could get
    wrong without anybody noticing.
    """

    engine = SourceEngine.FLARE
    # What the driver handed the engine on the last run. Asserted by the
    # `--input` test, because `api_roots` is otherwise invisible from outside.
    seen_api_roots: list[Path] = []
    # And where the driver said each of them will be published (6e), for the same
    # reason: the map is the whole of what conversion knows about the layout.
    seen_api_urls: dict[Path, str] = {}

    def convert_unit(self, context: ConversionContext, root: Path) -> Unit:
        FakeEngine.seen_api_roots = list(context.api_roots)
        FakeEngine.seen_api_urls = dict(context.api_urls)
        # Through the context, exactly as the four real engines do. Deriving the
        # name here instead is what a stub can get wrong without anybody noticing:
        # the driver names the asset destination from the same call, and two
        # derivations put a page and its images in different subtrees.
        unit = Unit(root=root, name=context.subtree_name(root))
        for html in sorted(root.rglob("*.htm")):
            relative = PurePosixPath(html.relative_to(root).as_posix()).with_suffix(".md")
            lines = []
            for match in _SRC.finditer(html.read_text(encoding="utf-8")):
                resolution = context.assets.resolve(html, relative, match.group("url"))
                if resolution.emits:
                    lines.append(f"![]({resolution.url})")
            unit.documents.append(
                Document(source=html, relative=relative, title=html.stem, body="\n".join(lines))
            )
        # A flat node list and a landing page: the least an engine can report and
        # still have Stage 6a something to synthesize. Reporting nothing at all
        # would let the driver write an empty `toc.yml` and look correct.
        unit.nav = [
            NavNode(label=document.title, document=document.relative)
            for document in unit.documents
        ]
        unit.landing = unit.documents[0].relative if unit.documents else None
        unit.skip("frameset", 1)
        return unit


@pytest.fixture
def fake_engine():
    """Swaps in the fake handler for one test, then puts the real one back.

    Save-and-restore rather than register-and-unregister: since 5b there *is* a
    registered Flare engine, and unregistering it would leave every later test in
    the session dispatching to nothing -- silently, as `ENGINE_UNKNOWN`.
    """
    previous = engine_for(SourceEngine.FLARE)
    register(FakeEngine)
    yield FakeEngine
    unregister(SourceEngine.FLARE)
    if previous is not None:
        register(previous)


@pytest.fixture
def extracted(
    config: ConfigManager, catalog: CatalogManager, product: Product, version: ProductVersion
) -> Path:
    """A version that has been through `extract`, exactly as Stage 5 expects one.

    Run through `PackageExtractor` rather than hand-built, because the driver
    reads back `output_roots`, `api_roots`, the CSH inventory and
    `extract_zip_checksum` -- all of them Stage 4's answers, and a hand-built tree
    would let this suite pass with a seam that does not join up.
    """
    place_package(config, product, version, PACKAGE)
    outcome = PackageExtractor(config, catalog).extract_one(product, version)
    # Asserted in the fixture, not left to the test: a silently failed extract
    # would make every downstream assertion here fail for the wrong reason.
    assert outcome.outcome is ExtractOutcome.EXTRACTED, outcome.message
    return config.extract_path(product.bu, product.family, product.slug, version.version)


def convert(config, catalog, product, version, **kwargs):
    findings = FindingsRun("convert")
    result = DocumentConverter(config, catalog, findings=findings).convert_one(
        product, version, **kwargs
    )
    return result, findings


# -- with no engine registered for the version's generator ---------------------


def test_importing_the_package_registers_every_written_engine() -> None:
    """A handler that is written but not imported is a handler that does not exist."""
    assert registered_engines() == [
        SourceEngine.DITA, SourceEngine.DOCBOOK, SourceEngine.FLARE, SourceEngine.WEBWORKS,
    ]
    # All four convertible engines are written as of Phase 5e, so the engine with
    # no handler is now a *named, unconvertible* one. The dispatch path being
    # tested is the same one an unwritten fifth converter would take.
    assert engine_for(SourceEngine.ROBOHELP) is None


def test_a_version_reports_engine_unknown_when_nothing_is_registered(
    config, catalog, product, version, extracted
) -> None:
    version.engine = SourceEngine.ROBOHELP
    result, findings = convert(config, catalog, product, version)

    assert result.outcome is ConvertOutcome.ENGINE_UNKNOWN
    assert [f.code for f in findings.all] == ["ENGINE_UNKNOWN"]
    assert findings.all[0].severity is Severity.WARNING


def test_auto_and_an_unhandled_engine_are_one_path_and_one_code(
    config, catalog, product, version, extracted
) -> None:
    """Invariant 7: never guess. Three conditions, one action, one finding."""
    version.engine = SourceEngine.AUTO
    auto, _ = convert(config, catalog, product, version)
    version.engine = SourceEngine.ROBOHELP
    unhandled, _ = convert(config, catalog, product, version)

    assert auto.outcome is unhandled.outcome is ConvertOutcome.ENGINE_UNKNOWN
    assert "auto" in auto.message
    assert "robohelp" in unhandled.message


def test_a_version_with_no_extracted_tree_is_a_report_line_not_an_abort(
    config, catalog, product, version
) -> None:
    result, findings = convert(config, catalog, product, version)

    assert result.outcome is ConvertOutcome.NO_TREE
    assert "docushift extract" in result.message
    assert findings.all == []


# -- with the fake engine registered ------------------------------------------


def test_the_spine_converts_a_unit_end_to_end(
    config, catalog, product, version, extracted, fake_engine
) -> None:
    result, _ = convert(config, catalog, product, version)

    assert result.outcome is ConvertOutcome.CONVERTED
    assert result.units == 1
    assert result.documents == 2
    output = config.output_path(product.bu, product.family, product.slug, version.version)
    assert (output / "Content" / "topic.md").is_file()
    assert result.skipped == {"frameset": 1}


def test_the_version_gets_its_toc_and_metadata_inside_the_build(
    config, catalog, product, version, extracted, fake_engine
) -> None:
    """Stage 6a runs before the swap, so the artifacts arrive with the topics.

    Asserted here and not only in `test_navigation.py` because the seam is the
    point: the node list exists only while the units are in hand, and a
    synthesizer that ran after `swap()` would write into a directory that no
    longer exists.
    """
    result, _ = convert(config, catalog, product, version)

    output = config.output_path(product.bu, product.family, product.slug, version.version)
    toc = yaml.safe_load((output / "toc.yml").read_text(encoding="utf-8"))
    # The landing page first, and every path relative to the version root rather
    # than to the unit the engine reported it from.
    assert [item["url"] for item in toc["docs"]] == [
        "Content/second.md", "Content/topic.md",
    ]
    assert result.nav_nodes == 2
    assert result.generated == 0
    assert yaml.safe_load((output / "metadata.yml").read_text(encoding="utf-8")) == {
        "csg-version": "10.4.0"
    }


def test_a_relative_link_exists_exactly_when_the_asset_was_copied(
    config, catalog, product, version, extracted, fake_engine
) -> None:
    """Invariant 13, asserted on the output rather than on the copier."""
    result, _ = convert(config, catalog, product, version)

    output = config.output_path(product.bu, product.family, product.slug, version.version)
    body = (output / "Content" / "topic.md").read_text(encoding="utf-8")
    assert "![](images/shot.png)" in body
    assert (output / "Content" / "images" / "shot.png").is_file()
    # The dangling, skin and escaping references emit nothing at all...
    assert "missing.png" not in body
    assert "logo.gif" not in body
    assert "guide.pdf" not in body
    # ...and the external one is emitted unchanged and never copied.
    assert "![](https://docs.example/remote.png)" in body
    assert result.counts.resolved == 2
    assert result.counts.dangling == 1
    assert result.counts.skin == 1
    assert result.counts.escaped == 1
    assert result.counts.external == 1


def test_an_orphan_is_reported_and_never_copied(
    config, catalog, product, version, extracted, fake_engine
) -> None:
    result, findings = convert(config, catalog, product, version)

    output = config.output_path(product.bu, product.family, product.slug, version.version)
    assert not (output / "Content" / "images" / "orphan.png").exists()
    # Two: the unreferenced image, and `Output.mcwebhelp`. The build marker is not
    # in the skin table -- which lists directory prefixes -- and it is genuinely an
    # unreferenced file inside the root, so counting it is the honest answer.
    assert result.counts.orphan_files == 2
    orphaned = [f for f in findings.all if f.code == "ASSET_ORPHANED"]
    assert orphaned and orphaned[0].severity is Severity.NOTE


def test_dangling_references_are_grouped_by_top_segment_in_the_register(
    config, catalog, product, version, extracted, fake_engine
) -> None:
    _, findings = convert(config, catalog, product, version)

    unresolved = [f for f in findings.all if f.code == "REFERENCE_UNRESOLVED"]
    assert [f.path for f in unresolved] == ["Content"]
    assert unresolved[0].severity is Severity.ERROR


def test_the_output_map_is_recorded_for_the_csh_resolver(
    config, catalog, product, version, extracted, fake_engine
) -> None:
    convert(config, catalog, product, version)

    mapping = catalog.state.get_output_map("tibco-ems", "10.4.0")
    assert mapping["guide/Content/topic.htm"] == "Content/topic.md"


def test_csh_yml_is_flat_quoted_and_omits_what_did_not_resolve(
    config, catalog, product, version, extracted, fake_engine
) -> None:
    result, findings = convert(config, catalog, product, version)

    output = config.output_path(product.bu, product.family, product.slug, version.version)
    assert (output / "csh.yml").read_text(encoding="utf-8") == '"install": "Content/topic.md"\n'
    # The unresolved digit-only identifier is not in the file and is not lost.
    assert [entry.identifier for entry in result.csh.unresolved] == ["1234"]
    assert [f.code for f in findings.all if f.code == "CSH_UNRESOLVED"] == ["CSH_UNRESOLVED"]


def test_every_text_file_convert_writes_has_lf_line_endings(
    config, catalog, product, version, extracted, fake_engine
) -> None:
    """X2-07, X3-10. Topics, `toc.yml`, `metadata.yml` and `csh.yml` were written
    CRLF on Windows, and only the pages the fragment pass rewrote came out LF, so
    a tree's line endings depended on which pass wrote each file last."""
    convert(config, catalog, product, version)

    output = config.output_path(product.bu, product.family, product.slug, version.version)
    written = [path for path in output.rglob("*") if path.suffix in {".md", ".yml"}]
    assert {path.name for path in written} >= {"topic.md", "toc.yml", "metadata.yml", "csh.yml"}
    assert [path.name for path in written if b"\r" in path.read_bytes()] == []


def test_the_shared_writer_folds_carriage_returns_already_in_the_text(tmp_path: Path) -> None:
    """A `\\r\\n` carried in from a source `<pre>` block came out `\\r\\r\\n` through a
    CRLF translation. Every CR is folded, so the file is LF whatever it holds."""
    path = tmp_path / "page.md"

    textfile.write_text(path, "a\r\nb\rc\n")

    assert path.read_bytes() == b"a\nb\nc\n"


def test_identifiers_reach_the_topics_first_and_only_write(
    config, catalog, product, version, extracted, fake_engine
) -> None:
    """§9.5. There is no second pass, so a missing key here can never be repaired."""
    convert(config, catalog, product, version)

    output = config.output_path(product.bu, product.family, product.slug, version.version)
    owner = (output / "Content" / "topic.md").read_text(encoding="utf-8")
    other = (output / "Content" / "second.md").read_text(encoding="utf-8")
    assert 'csh: ["install"]' in owner
    assert "csh:" not in other


def test_a_version_with_no_csh_gets_no_file(
    config, catalog, product, version, fake_engine
) -> None:
    """An empty map file is indistinguishable from a failed run (§9.4)."""
    package = {name: text for name, text in PACKAGE.items() if not name.endswith("Alias.xml")}
    place_package(config, product, version, package)
    PackageExtractor(config, catalog).extract_one(product, version)

    result, _ = convert(config, catalog, product, version)

    output = config.output_path(product.bu, product.family, product.slug, version.version)
    assert result.outcome is ConvertOutcome.CONVERTED
    assert not (output / "csh.yml").exists()


def test_the_output_is_built_and_swapped_never_written_over(
    config, catalog, product, version, extracted, fake_engine
) -> None:
    """A re-convert over a live directory keeps a guide that was dropped upstream."""
    output = config.output_path(product.bu, product.family, product.slug, version.version)
    output.mkdir(parents=True, exist_ok=True)
    (output / "yesterday.md").write_text("stale", encoding="utf-8")

    convert(config, catalog, product, version)

    assert not (output / "yesterday.md").exists()
    assert not output.with_name(output.name + ".part").exists()


def test_an_unchanged_tree_is_current_and_force_reconverts(
    config, catalog, product, version, extracted, fake_engine
) -> None:
    first, _ = convert(config, catalog, product, version)
    again, _ = convert(config, catalog, product, version)
    forced, _ = convert(config, catalog, product, version, force=True)

    assert first.outcome is ConvertOutcome.CONVERTED
    assert again.outcome is ConvertOutcome.CURRENT
    assert again.documents == 0
    assert forced.outcome is ConvertOutcome.CONVERTED


def test_a_converted_version_records_its_status_and_source_checksum(
    config, catalog, product, version, extracted, fake_engine
) -> None:
    convert(config, catalog, product, version)

    state = catalog.state.get_version_state("tibco-ems", "10.4.0")
    metadata = catalog.state.get_version_metadata("tibco-ems", "10.4.0")
    assert state["status"] == str(ConversionStatus.CONVERTED)
    assert metadata["convert_source_checksum"] == metadata["extract_zip_checksum"]


def test_a_standalone_folder_converts_without_a_catalog_extract(
    config, catalog, product, version, tmp_path, fake_engine
) -> None:
    """`--input`/`--output`: the same code path, not a second one."""
    from tests.unit.test_extractor import build_tree

    tree = build_tree(tmp_path / "loose", PACKAGE)
    destination = tmp_path / "loose-output"
    version.engine = SourceEngine.FLARE

    result, _ = convert(config, catalog, product, version, tree=tree, output=destination)

    assert result.outcome is ConvertOutcome.CONVERTED
    # The CSH sources were located rather than read back, because nothing recorded them.
    assert (destination / "csh.yml").is_file()


def test_api_roots_are_located_when_no_extract_recorded_them(
    config, catalog, product, version, tmp_path, fake_engine
) -> None:
    """The same `--input` fallback, for the answer §6.3 usually reads back.

    An engine skips an API tree by asking `is_api_reference(path, api_roots)`, so
    an empty list on a standalone folder means every generated reference page is
    offered to the converter as prose. Located, never re-located: a tree that has
    a recorded answer keeps it.
    """
    from tests.unit.test_extractor import build_tree

    # `index-all.html` is the marker, not the generator comment: a marker decides
    # and a name never does (`apiref.py`).
    javadoc = "<html><head><!-- Generated by javadoc --></head><body>x</body></html>"
    tree = build_tree(tmp_path / "loose", {**PACKAGE, "guide/Content/api/index-all.html": javadoc})
    version.engine = SourceEngine.FLARE

    convert(config, catalog, product, version, tree=tree, output=tmp_path / "loose-output")

    assert [str(root.relative_to(tree)) for root in FakeEngine.seen_api_roots] == [
        str(Path("guide") / "Content" / "api")
    ]


# -- the output tree is counted (planning.md Phase 13) -------------------------


def _walk(tree: Path) -> tuple[int, int]:
    """What the columns should say, counted independently of the code under test."""
    files = [path for path in tree.rglob("*") if path.is_file()]
    return sum(1 for path in files if path.suffix == ".md"), len(files)


def test_the_output_tree_is_counted_after_the_swap(
    config, catalog, product, version, extracted, fake_engine
) -> None:
    """Two columns, from one walk of the tree that will actually be published."""
    result, _ = convert(config, catalog, product, version)

    md_files, out_files = _walk(result.path)
    assert (result.md_files, result.out_files) == (md_files, out_files)
    row = catalog.get_version("tibco-ems", "10.4.0")
    assert (row.md_files, row.out_files) == (md_files, out_files)


def test_the_artifact_count_is_measured_and_never_assumed(
    config, catalog, product, version, extracted, fake_engine
) -> None:
    """`csh.yml` exists only for a non-empty map, so the root artifacts are 3 or 2.

    This is the whole reason the columns come out of a walk rather than out of
    `documents + generated + assets + 3`: the derivation is wrong by one on every
    version whose help map yields no identifiers, which is the majority of the
    corpus rather than an edge of it.
    """
    with_csh, _ = convert(config, catalog, product, version)
    assert (with_csh.path / "csh.yml").is_file()
    artifacts = with_csh.out_files - with_csh.md_files - with_csh.assets
    assert artifacts == 3

    # The same package with its alias file emptied -- `_csh_names=0`, which 55% of
    # the Flare corpus ships.
    (extracted / "guide" / "Data" / "Alias.xml").write_text(
        "<CatapultAliasFile />", encoding="utf-8"
    )
    without_csh, _ = convert(config, catalog, product, version, force=True)

    assert not (without_csh.path / "csh.yml").exists()
    assert without_csh.out_files - without_csh.md_files - without_csh.assets == 2


def test_a_version_that_did_not_convert_leaves_the_columns_blank(
    config, catalog, product, version, fake_engine
) -> None:
    """Blank-not-zero: a version that did not convert is not one that converted to nothing."""
    result, _ = convert(config, catalog, product, version)

    assert result.outcome is ConvertOutcome.NO_TREE
    row = catalog.get_version("tibco-ems", "10.4.0")
    assert row.md_files is None
    assert row.out_files is None


def test_a_current_version_with_blank_columns_is_walked_and_filled(
    config, catalog, product, version, extracted, fake_engine
) -> None:
    """Phase 12's lesson, applied before it can bite: a no-op must still count.

    Without this the six versions converted before the columns existed would
    report `current` on every future run and stay blank permanently -- exactly the
    state `extract --measure-only` had to be written to get out of.
    """
    first, _ = convert(config, catalog, product, version)
    before = {
        path.relative_to(first.path): path.read_bytes()
        for path in first.path.rglob("*") if path.is_file()
    }
    catalog.clear_convert_inventory("tibco-ems", "10.4.0")

    again, _ = convert(config, catalog, product, version)

    assert again.outcome is ConvertOutcome.CURRENT
    assert (again.md_files, again.out_files) == (first.md_files, first.out_files)
    row = catalog.get_version("tibco-ems", "10.4.0")
    assert (row.md_files, row.out_files) == (first.md_files, first.out_files)
    # A measurement must not touch what it measures.
    assert {
        path.relative_to(again.path): path.read_bytes()
        for path in again.path.rglob("*") if path.is_file()
    } == before


def test_a_current_version_that_is_already_counted_is_not_walked_again(
    config, catalog, product, version, extracted, fake_engine
) -> None:
    """The backfill is for blank rows only; re-walking a counted tree buys nothing."""
    convert(config, catalog, product, version)

    again, _ = convert(config, catalog, product, version)

    assert again.outcome is ConvertOutcome.CURRENT
    assert (again.md_files, again.out_files) == (0, 0)


def test_two_documents_on_one_path_are_reported_rather_than_silently_lost(
    config, catalog, product, version, extracted, fake_engine
) -> None:
    """The 7b defect, turned into arithmetic.

    `navigation._free` compared a generated page's path case-sensitively, so on
    Windows the page was written *over* a converted topic and three versions
    shipped with the topic gone. Nothing in the run said so, because each write
    succeeded. Counting the tree is what makes the second write visible.
    """
    class CollidingEngine(FakeEngine):
        def convert_unit(self, context, root):
            unit = super().convert_unit(context, root)
            # Two distinct sources resolving to one output path, which is what a
            # case-insensitive filesystem did to `navigation._free`. The map keeps
            # both rows; the disk keeps one file.
            unit.documents[1].relative = unit.documents[0].relative
            return unit

    register(CollidingEngine)
    try:
        result, findings = convert(config, catalog, product, version)
    finally:
        unregister(SourceEngine.FLARE)
        register(FakeEngine)

    assert result.md_files == result.documents + result.generated - 1
    mismatch = [f for f in findings.all if f.code == "OUTPUT_COUNT_MISMATCH"]
    assert len(mismatch) == 1
    assert mismatch[0].count == 1


def test_findings_are_flushed_per_version(
    config, catalog, product, version, extracted, fake_engine
) -> None:
    findings = FindingsRun("convert", store=catalog.state).start()
    DocumentConverter(config, catalog, findings=findings).convert_one(product, version)

    rows = catalog.state.get_findings(findings.run_id)
    # ORIGIN_SITEMAP_MISSING: this fixture has no declaration and no cached sitemap (Phase 35).
    assert {row["code"] for row in rows} == {
        "REFERENCE_UNRESOLVED", "ASSET_ORPHANED", "CSH_UNRESOLVED", "ORIGIN_SITEMAP_MISSING"}
    assert findings.pending == []


# -- the origin map (Phase 35) ---------------------------------------------------

LIVE = "https://docs.tibco.com/pub/ems/10.4.0/doc"


def cache_sitemap(config, product, version, urls: list[str]) -> None:
    """What `catalog sitemap` leaves in `cache/coveo/` for one version."""
    from docushift.discovery.sitemap import SitemapCache, leaf_stem

    stem = leaf_stem(product.slug, version.version)
    cache = SitemapCache(config.cache_dir / "coveo")
    body = "".join(f"<url><loc>{url}</loc></url>" for url in urls)
    cache.write(f"{stem}.xml", f"<urlset>{body}</urlset>".encode())
    cache.save_manifest({"files": {}, "products": {product.slug: [stem]}})


def listed_urls(catalog, product, version) -> list[str]:
    """Each converted topic's live URL, by the EMS shape: wrapper dropped, under `/doc`."""
    output_map = catalog.state.get_output_map(product.slug, version.version)
    return [f"{LIVE}/{source.split('/', 1)[1]}" for source in output_map]


def test_the_converted_tree_carries_its_origin_map(
    config, catalog, product, version, extracted, fake_engine
) -> None:
    """`sync` publishes `output/` for every product that does not publish merged,
    so the map has to be in it; nothing has moved, so `to` is the output path."""
    convert(config, catalog, product, version)
    urls = listed_urls(catalog, product, version)
    cache_sitemap(config, product, version, urls + [f"{LIVE}/api/index.html"])

    result, findings = convert(config, catalog, product, version, force=True)

    redirects = yaml.safe_load((result.path / "301.yml").read_text(encoding="utf-8"))["redirects"]
    output_map = catalog.state.get_output_map(product.slug, version.version)
    assert sorted(row["from"] for row in redirects) == sorted(urls)
    assert sorted(row["to"] for row in redirects) == sorted(output_map.values())
    origin_codes = [f.code for f in findings.all if f.code.startswith("ORIGIN_")]
    assert origin_codes == ["ORIGIN_PAGE_UNMAPPED"]


def test_no_sitemap_and_no_declaration_writes_no_origin_map(
    config, catalog, product, version, extracted, fake_engine
) -> None:
    result, findings = convert(config, catalog, product, version)

    assert not (result.path / "301.yml").exists()
    assert "ORIGIN_SITEMAP_MISSING" in [f.code for f in findings.all]


def test_a_sitemap_that_confirms_no_mapping_writes_no_origin_map(
    config, catalog, product, version, extracted, fake_engine
) -> None:
    cache_sitemap(config, product, version, [f"{LIVE}/unrelated.htm"])

    result, findings = convert(config, catalog, product, version)

    assert not (result.path / "301.yml").exists()
    assert "ORIGIN_TEMPLATE_UNDECLARED" in [f.code for f in findings.all]


# -- the command ---------------------------------------------------------------


def test_convert_reports_engine_unknown_and_still_exits_zero(
    config, catalog, product, version, extracted, tmp_path
) -> None:
    """One unconvertible version does not stop a 200-version batch.

    The engine is named by hand because the fixture package is Flare, which has
    converted since 5b: left as detected, this version *fails* (nothing converted),
    and since Phase 34 (R12-06) a failed version exits 1. An engine with no
    converter is a report line and still exits 0.
    """
    catalog.set_version_field(product.slug, version.version, "engine", "robohelp")
    runner = CliRunner()

    result = runner.invoke(
        main,
        ["--root", str(config.root_dir), "convert", "--product", "tibco-ems", "--version", "10.4.0"],
    )

    assert result.exit_code == 0, result.output
    assert "Engine unknown" in result.output
    # The table label prints either way; the named line is what says which row it was.
    assert "! tibco-ems@10.4.0" in result.output
    assert "nothing converted" not in result.output


def test_convert_dry_run_writes_nothing(
    config, catalog, product, version, extracted, fake_engine
) -> None:
    runner = CliRunner()

    result = runner.invoke(
        main,
        ["--root", str(config.root_dir), "convert", "--product", "tibco-ems", "--dry-run"],
    )

    output = config.output_path(product.bu, product.family, product.slug, version.version)
    assert result.exit_code == 0, result.output
    assert "Would convert" in result.output
    assert not output.exists()


def test_convert_needs_input_and_output_together(config, catalog, product, version) -> None:
    runner = CliRunner()

    result = runner.invoke(
        main,
        ["--root", str(config.root_dir), "convert", "--product", "tibco-ems", "--input", str(config.root_dir)],
    )

    assert result.exit_code != 0
    assert "--input and --output" in result.output


def test_the_flat_csh_writer_and_the_driver_agree_on_the_file_name(
    config, catalog, product, version, extracted, fake_engine
) -> None:
    """One name, checked from both sides, because Phase 6 reads it by name."""
    result, _ = convert(config, catalog, product, version)
    output = config.output_path(product.bu, product.family, product.slug, version.version)

    assert result.outcome is ConvertOutcome.CONVERTED, result.message
    assert csh.render(result.csh.entries) == (output / "csh.yml").read_text(encoding="utf-8")


# -- the cross-boundary URL map and its currency key (6e) -----------------------

JAVADOC_PAGE = "<html><head><!-- Generated by javadoc --></head><body>x</body></html>"


@pytest.fixture
def extracted_with_api(
    config: ConfigManager, catalog: CatalogManager, product: Product, version: ProductVersion
) -> Path:
    """`extracted`, plus one API tree for the driver to build a URL map from."""
    place_package(config, product, version, {
        **PACKAGE,
        "apidocs/index-all.html": JAVADOC_PAGE,
        "apidocs/index.html": JAVADOC_PAGE,
    })
    outcome = PackageExtractor(config, catalog).extract_one(product, version)
    assert outcome.outcome is ExtractOutcome.EXTRACTED, outcome.message
    return config.extract_path(product.bu, product.family, product.slug, version.version)


def set_host(config: ConfigManager, host: str) -> None:
    """Sets `publish_base_url` the way an operator would, and drops the cache."""
    path = config.root_dir / "config" / "publishing.yaml"
    body = path.read_text(encoding="utf-8") if path.exists() else ""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{body}\npublish_base_url: {host}\n", encoding="utf-8")
    config._publishing_cache = None


def test_the_driver_hands_the_engine_a_url_per_api_tree(
    config, catalog, product, version, extracted_with_api, fake_engine
) -> None:
    """Conversion is *told* the publishing layout, never asked to work it out.

    Which is what keeps §10.7's rationale true after the rewrite moved into Stage
    5: the engines still know nothing about repositories, locales or version
    segments -- the driver resolved all three before `convert_unit` was called.
    """
    set_host(config, "https://docs.example.com")

    convert(config, catalog, product, version)

    assert list(FakeEngine.seen_api_urls.values()) == [
        "https://docs.example.com/en-us-tibco-messaging-userdocs-resources"
        "/en-us/tibco-ems/api-references/10-4-0/apidocs"
    ]


def test_a_version_with_no_api_tree_gets_no_map_and_no_prefix(
    config, catalog, product, version, extracted, fake_engine
) -> None:
    """409 of the 422 products a full sync selects are in this state."""
    set_host(config, "https://docs.example.com")

    convert(config, catalog, product, version)

    assert FakeEngine.seen_api_urls == {}
    assert catalog.state.get_version_metadata("tibco-ems", "10.4.0")["convert_api_prefix"] == ""


def test_setting_the_host_reconverts_the_version_whose_links_it_changes(
    config, catalog, product, version, extracted_with_api, fake_engine
) -> None:
    """The one trap in the phase, and it is a silent-partial-success (§7.5).

    Currency is keyed on the *package's* checksum, and the package does not change
    when `publishing.yaml` does. Without the second key, filling in the AEM host
    would leave every converted tree reporting CURRENT with host-less API links
    baked in -- and the run would say so cheerfully.
    """
    first, _ = convert(config, catalog, product, version)
    unchanged, _ = convert(config, catalog, product, version)
    set_host(config, "https://docs.example.com")
    after_host, _ = convert(config, catalog, product, version)
    settled, _ = convert(config, catalog, product, version)

    assert first.outcome is ConvertOutcome.CONVERTED
    assert unchanged.outcome is ConvertOutcome.CURRENT
    assert after_host.outcome is ConvertOutcome.CONVERTED
    assert settled.outcome is ConvertOutcome.CURRENT


def test_a_version_with_no_api_tree_is_not_reconverted_when_the_host_changes(
    config, catalog, product, version, extracted, fake_engine
) -> None:
    """Or setting one value would reconvert 1,822 versions to change the output of 41."""
    convert(config, catalog, product, version)
    set_host(config, "https://docs.example.com")

    again, _ = convert(config, catalog, product, version)

    assert again.outcome is ConvertOutcome.CURRENT


def test_the_rewrite_is_reported_once_with_a_count(
    config, catalog, product, version, extracted_with_api, fake_engine
) -> None:
    """A version with an API tree and zero rewritten links is the thing to look at.

    It is either a product whose help genuinely never references its API -- 8 of
    the 49 in-scope versions -- or a predicate that stopped matching, and only the
    count tells those apart. So the note fires at zero too.
    """
    set_host(config, "https://docs.example.com")

    _, findings = convert(config, catalog, product, version)

    rows = [f for f in findings.all if f.code == "API_LINK_REWRITTEN"]
    assert len(rows) == 1
    assert rows[0].count == 0
    assert "1 API tree(s)" in rows[0].message


# -- the homepage date cross-check (Phase 34, R1-05) ----------------------------


class _Recorder:
    """Stands in for `ConversionContext`: the check needs nothing but `record`."""

    def __init__(self) -> None:
        self.messages: list[str] = []

    def record(self, code: str, path: str = "", message: str = "", count: int = 1) -> None:
        self.messages.append(f"{code}: {message}")


def _year_check(homepage: str, catalog_date: str) -> list[str]:
    context = _Recorder()
    unit = SimpleNamespace(name="html", metadata={"release-date": homepage})
    version = ProductVersion(slug="p", version="1.4.0", release_date=catalog_date)
    DocumentConverter.__new__(DocumentConverter)._report_metadata(context, [unit], version)
    return context.messages


@pytest.mark.parametrize(
    ("homepage", "catalog_date"),
    [("June 2023", "2023-06-12"), ("May 2014", "1399420800000")],
)
def test_the_year_check_reads_a_month_name_and_an_epoch_date(homepage: str, catalog_date: str) -> None:
    """It sliced `[:4]`, so `June 2023` against `2023-06-12` read `June != 2023`."""
    assert _year_check(homepage, catalog_date) == []


def test_a_real_year_difference_is_still_reported() -> None:
    assert _year_check("June 2022", "2023-06-12") == [
        "METADATA_MISMATCH: homepage release-date 2022 != catalog 2023"
    ]


# -- localized output roots (Phase 34, R5-01) --------------------------------------


def _flare_roots(base: Path, *relatives: str) -> list[Path]:
    roots = []
    for relative in relatives:
        root = base / relative
        (root / "Data").mkdir(parents=True, exist_ok=True)
        (root / "Data" / "HelpSystem.xml").write_text("<x/>", encoding="utf-8")
        roots.append(root)
    return roots


def _units(tree: Path, engine_cls: type[BaseEngine] = FakeEngine) -> tuple[list[str], FindingsRun]:
    findings = FindingsRun("convert")
    context = ConversionContext(
        tree=tree, output=tree.parent / "out", engine=SourceEngine.FLARE,
        output_roots=find_output_roots(tree, SourceEngine.FLARE), findings=findings,
    )
    work = engine_cls().units(context)
    return [root.relative_to(tree).as_posix() for root in work], findings


def test_a_localized_output_root_is_skipped_and_named_with_its_locale(tmp_path: Path) -> None:
    """`wf-wf/9.3.5`: five sibling builds, one per locale, and the `ja-jp` one alone
    converted 2,779 Japanese topics into the English tree with no finding."""
    _flare_roots(tmp_path, "doc/en", *(f"doc/html/{tag}" for tag in
                                       ("de-de", "en-us", "es-es", "fr-fr", "ja-jp")))

    units, findings = _units(tmp_path)

    assert units == ["doc/en", "doc/html/en-us"]
    skipped = {f.path: f.message for f in findings.all if f.code == "LOCALIZED_ROOT_SKIPPED"}
    assert sorted(skipped) == ["doc/html/de-de", "doc/html/es-es", "doc/html/fr-fr", "doc/html/ja-jp"]
    assert "'ja-jp'" in skipped["doc/html/ja-jp"]


def test_a_nested_localized_root_cannot_convert_what_its_parent_skipped(tmp_path: Path) -> None:
    """`sfire-dsc/7.1.0`: the outer root skipped `ja/` and said so, while the nested
    root `doc/html/ja` converted the same files. Neither converts them now, and a
    root inside the skipped one goes with it."""
    _flare_roots(tmp_path, "doc/html", "doc/html/ja", "doc/html/ja/sub")

    units, findings = _units(tmp_path, engine_for(SourceEngine.FLARE))

    assert units == ["doc/html"]
    assert sorted(f.path for f in findings.all if f.code == "LOCALIZED_ROOT_SKIPPED") == [
        "doc/html/ja", "doc/html/ja/sub",
    ]


def test_a_folder_that_only_looks_like_a_language_is_converted(tmp_path: Path) -> None:
    _flare_roots(tmp_path, "doc/ui", "doc/html")

    units, findings = _units(tmp_path)

    assert units == ["doc/ui", "doc/html"] or units == ["doc/html", "doc/ui"]
    assert not findings.all


def test_a_skipped_localized_root_contributes_no_help_identifiers(
    config, catalog, product, version, fake_engine
) -> None:
    """Its `Alias.xml` would otherwise reach `csh.yml`'s resolver and report every
    identifier unresolved, since nothing of the root was converted."""
    place_package(config, product, version, {
        **PACKAGE,
        "guide/ja-jp/Data/HelpSystem.xml": "<x/>",
        "guide/ja-jp/Data/Alias.xml": ALIAS.replace("install", "jp-install"),
        "guide/ja-jp/Content/topic.htm": TOPIC,
    })
    assert PackageExtractor(config, catalog).extract_one(product, version).outcome is (
        ExtractOutcome.EXTRACTED
    )

    result, findings = convert(config, catalog, product, version)

    assert result.outcome is ConvertOutcome.CONVERTED
    assert "jp-install" not in result.csh.entries
    assert [f.message for f in findings.all if f.code == "CSH_UNRESOLVED"] == [
        "1234 -> Content/gone.htm matched no produced topic"
    ]
    assert [f.path for f in findings.all if f.code == "LOCALIZED_ROOT_SKIPPED"] == ["guide/ja-jp"]


# -- one engine per version (Phase 34, R4-02, R4-03) -------------------------------


class _RecordingWebWorks(BaseEngine):
    """Says which roots the driver handed it, and converts nothing."""

    engine = SourceEngine.WEBWORKS
    seen: list[Path] = []

    def units(self, context: ConversionContext) -> list[Path]:
        _RecordingWebWorks.seen = super().units(context)
        return _RecordingWebWorks.seen

    def convert_unit(self, context: ConversionContext, root: Path) -> Unit:  # pragma: no cover
        return Unit(root=root, name=context.subtree_name(root))


@pytest.fixture
def recording_webworks():
    previous = engine_for(SourceEngine.WEBWORKS)
    register(_RecordingWebWorks)
    yield _RecordingWebWorks
    unregister(SourceEngine.WEBWORKS)
    if previous is not None:
        register(previous)


def test_a_hand_corrected_engine_reconverts_and_ignores_the_old_engines_roots(
    config, catalog, product, version, extracted, fake_engine, recording_webworks
) -> None:
    """`engine_source=manual` is §3.4's remedy for a misdetected engine, and the
    next `convert` reported `current` and kept the old engine's tree; `--force`
    then handed the new engine the Flare roots Stage 4 had recorded (R4-03)."""
    first, _ = convert(config, catalog, product, version)
    assert first.outcome is ConvertOutcome.CONVERTED

    version.engine = SourceEngine.WEBWORKS
    version.engine_source = EngineSource.MANUAL
    second, _ = convert(config, catalog, product, version)

    assert second.outcome is not ConvertOutcome.CURRENT
    assert second.engine is SourceEngine.WEBWORKS
    # `guide` holds `Data/HelpSystem.xml` and no `wwhdata/`: a Flare root, and
    # nothing a WebWorks engine may be handed as a book.
    assert recording_webworks.seen == []


def test_a_book_of_another_engine_is_named_once_and_not_fed_to_this_one(
    config, catalog, product, version, tmp_path
) -> None:
    """BusinessConnect 7.4.0 detects as Flare, and its 83-page WebWorks book inside
    the Flare root came out as ~80 `CONTENT_MISSING` lines that read as a Flare
    markup defect (R4-02). One engine converts a version; every unit it cannot
    convert is one `ENGINE_ROOT_UNCONVERTED` line naming the engine and the root."""
    files = {
        "guide/Output.mcwebhelp": "",
        "guide/Data/HelpSystem.xml": "<x/>",
        "guide/Content/topic.htm": (
            "<html><body><div role='main' id='mc-main-content'><h1>T</h1></div></body></html>"
        ),
        "guide/apiref/wwhdata/common/files.js": "",
        **{f"guide/apiref/page{n}.htm": "<html><body><blockquote>x</blockquote></body></html>"
           for n in range(3)},
        "loose/wwhdata/common/files.js": "",
        "loose/page.htm": "<html><body><blockquote>x</blockquote></body></html>",
    }
    place_package(config, product, version, files)
    assert PackageExtractor(config, catalog).extract_one(product, version).outcome is (
        ExtractOutcome.EXTRACTED
    )

    result, findings = convert(config, catalog, product, version)

    unconverted = {f.path: f.message for f in findings.all if f.code == "ENGINE_ROOT_UNCONVERTED"}
    assert sorted(unconverted) == ["guide/apiref", "loose"]
    assert "webworks" in unconverted["loose"]
    assert not [f for f in findings.all if f.code == "CONTENT_MISSING"]
    assert result.skipped.get("other-engine-root") == 3


# -- `--input` and CSH consistency (Phase 34, R4-04, R4-05) -----------------------


def test_a_standalone_folder_never_reads_the_catalog_trees_record(
    config, catalog, product, version, extracted, fake_engine, tmp_path
) -> None:
    """The recorded roots, API roots and CSH paths describe the catalog's tree.
    Joined to an `--input` copy laid out under a wrapper, every one of them
    missed, and the run reported `converted` with 0 topics (R4-04). Nor does the
    catalog tree's checksum make the other folder `current`."""
    from tests.unit.test_extractor import build_tree

    first, _ = convert(config, catalog, product, version)
    assert first.outcome is ConvertOutcome.CONVERTED
    loose = build_tree(tmp_path / "loose", {f"wrapper/{k}": v for k, v in PACKAGE.items()})
    out = tmp_path / "loose-out"
    out.mkdir()

    result, _ = convert(config, catalog, product, version, tree=loose, output=out)

    assert result.outcome is ConvertOutcome.CONVERTED
    assert result.documents == 2
    assert (out / "csh.yml").is_file()


def _frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    return yaml.safe_load(text.split("---")[1]) if text.startswith("---") else {}


def test_frontmatter_carries_exactly_the_identifiers_csh_yml_resolves_to_the_page(
    config, catalog, product, version, fake_engine
) -> None:
    """§9.6: every identifier in a topic's frontmatter is in `csh.yml`, and the
    reverse. Frontmatter was keyed on the link inside its own doc-set, so an
    identifier the version-wide fallback rescued landed on no page, and the loser
    of an ambiguity kept it while `csh.yml` pointed elsewhere (R4-05)."""
    def alias(*maps: tuple[str, str]) -> str:
        rows = "".join(f'<Map Name="{name}" Link="{link}"/>' for name, link in maps)
        return f"<CatapultAliasFile>{rows}</CatapultAliasFile>"

    place_package(config, product, version, {
        "guide/Output.mcwebhelp": "",
        "guide/Data/HelpSystem.xml": "<x/>",
        "guide/Data/Alias.xml": alias(("ID_MAIN", "a.htm"), ("ID_BOTH", "a.htm")),
        "guide/a.htm": "<html><body>A</body></html>",
        "relnotes/Data/HelpSystem.xml": "<x/>",
        "relnotes/Data/Alias.xml": alias(("ID_RESCUED", "a.htm"), ("ID_BOTH", "r.htm")),
        "relnotes/r.htm": "<html><body>R</body></html>",
    })
    assert PackageExtractor(config, catalog).extract_one(product, version).outcome is (
        ExtractOutcome.EXTRACTED
    )

    result, _ = convert(config, catalog, product, version)

    output = config.output_path(product.bu, product.family, product.slug, version.version)
    assert result.csh.entries == {"ID_BOTH": "a.md", "ID_MAIN": "a.md", "ID_RESCUED": "a.md"}
    assert _frontmatter(output / "a.md")["csh"] == ["ID_BOTH", "ID_MAIN", "ID_RESCUED"]
    assert "csh" not in _frontmatter(output / "relnotes" / "r.md")


# -- nothing converted, or a crash (Phase 34, R4-06, R4-07, R4-08) ----------------


class _Empty(FakeEngine):
    """Finds its unit and converts nothing in it: a re-extract that lost every topic."""

    def convert_unit(self, context: ConversionContext, root: Path) -> Unit:
        return Unit(root=root, name=context.subtree_name(root))


class _Boom(FakeEngine):
    def convert_unit(self, context: ConversionContext, root: Path) -> Unit:
        raise ValueError("an engine bug on one real page")


@pytest.fixture
def swap_flare():
    """Registers a stand-in Flare engine for one test and puts the real one back."""
    previous = engine_for(SourceEngine.FLARE)

    def use(engine_cls: type[BaseEngine]) -> None:
        register(engine_cls)

    yield use
    unregister(SourceEngine.FLARE)
    if previous is not None:
        register(previous)


def test_a_run_that_converts_nothing_fails_and_keeps_the_previous_output(
    config, catalog, product, version, extracted, swap_flare
) -> None:
    """Zero documents was still `converted`, and the swap replaced a populated
    tree with an empty one under a green CLI line (R4-06)."""
    swap_flare(FakeEngine)
    convert(config, catalog, product, version)
    output = config.output_path(product.bu, product.family, product.slug, version.version)

    swap_flare(_Empty)
    result, _ = convert(config, catalog, product, version, force=True)

    assert result.outcome is ConvertOutcome.FAILED
    assert "nothing converted" in result.message
    assert (output / "Content" / "topic.md").is_file()
    assert not output.with_name(output.name + ".part").exists()


def test_an_engine_exception_fails_one_version_and_the_batch_goes_on(
    config, catalog, product, version, extracted, swap_flare
) -> None:
    """Only `OSError` was caught: a `ValueError` on one page stopped every
    remaining version, skipped `findings.finish()` and left `<version>.part`
    (R4-07)."""
    swap_flare(_Boom)
    converter = DocumentConverter(config, catalog, findings=FindingsRun("convert"))

    stats = converter.convert_many([(product, version), (product, version)])

    assert [r.outcome for r in stats.results] == [ConvertOutcome.FAILED] * 2
    assert "ValueError: an engine bug on one real page" in stats.results[0].message
    output = config.output_path(product.bu, product.family, product.slug, version.version)
    assert not output.with_name(output.name + ".part").exists()
    state = catalog.state.get_version_state(product.slug, version.version)
    assert state["status"] == ConversionStatus.ERROR


def test_bookkeeping_that_fails_after_the_swap_leaves_state_describing_the_new_tree(
    config, catalog, product, version, extracted, fake_engine, monkeypatch
) -> None:
    """The CSV write (Excel holding `versions.csv`) ran before `output_map` and the
    checksum, so a failure there left the new tree with the previous build's map,
    which Reframe reads (R4-08)."""
    def locked(*_args, **_kwargs):
        raise PermissionError("versions.csv is open in another program")

    monkeypatch.setattr(catalog, "record_convert_inventory", locked)

    result, _ = convert(config, catalog, product, version)

    assert result.outcome is ConvertOutcome.FAILED
    assert catalog.state.get_output_map(product.slug, version.version)["guide/Content/topic.htm"] == (
        "Content/topic.md"
    )
    metadata = catalog.state.get_version_metadata(product.slug, version.version)
    assert metadata["convert_source_checksum"] == metadata["extract_zip_checksum"]


# -- unit naming (Phase 34, R4-14) -----------------------------------------------


def test_a_root_the_subtree_lookup_does_not_know_is_refused(tmp_path: Path) -> None:
    """It answered `""` -- the version root -- for any root not exactly a key, so
    an engine deriving a root differently from the list it returned would have
    written its pages over the version root and said nothing."""
    context = ConversionContext(tree=tmp_path, output=tmp_path / "out", engine=SourceEngine.FLARE)
    context.subtrees = {tmp_path / "a": "", tmp_path / "b": "b"}

    assert context.subtree_name(tmp_path / "b") == "b"
    with pytest.raises(ValueError, match="not a unit"):
        context.subtree_name(tmp_path / "c")


# -- what the shared walk could not render (Phase 34, R8-13) ----------------------


class _Unrendering(FakeEngine):
    """Merges a renderer's count into the context, as the four real engines do."""

    def convert_unit(self, context: ConversionContext, root: Path) -> Unit:
        context.unrendered.update({"iframe": 2, "svg": 1})
        return super().convert_unit(context, root)


def test_media_the_walk_could_not_render_is_one_note_per_version_by_tag(
    config, catalog, product, version, extracted, swap_flare
) -> None:
    """An `<iframe>` of a video reached the output as nothing and nobody was told."""
    swap_flare(_Unrendering)

    result, findings = convert(config, catalog, product, version)

    assert result.outcome is ConvertOutcome.CONVERTED, result.message
    notes = [f for f in findings.all if f.code == "ELEMENT_UNRENDERED"]
    assert [(f.count, f.severity) for f in notes] == [(3, Severity.NOTE)]
    assert "iframe 2, svg 1" in notes[0].message


# -- Help buttons and encoded fragments land on a heading (Phase 34, R8-04, R8-08) --


class _Sections(FakeEngine):
    """Pages with targets part-way down: the marker-above-a-heading shape every
    real engine emits, and a link to a target whose name holds spaces."""

    def convert_unit(self, context: ConversionContext, root: Path) -> Unit:
        unit = super().convert_unit(context, root)
        for document in unit.documents:
            if document.relative.name == "a.md":
                document.body = (
                    "# Folder Reference\n\nIntro.\n\n<a id=\"1684753\"></a>\n\n"
                    "## Adapter Services Folder\n\nText.\n\n"
                    "<a id=\"tibdg proxy shed\"></a>\n\n## Proxy Shed\n\nMore.\n"
                )
            else:
                document.body = "# Methods\n\nSee [shedding](a.md#tibdg%20proxy%20shed).\n"
        return unit


def _alias(*maps: tuple[str, str]) -> str:
    rows = "".join(f'<Map Name="{name}" Link="{link}"/>' for name, link in maps)
    return f"<CatapultAliasFile>{rows}</CatapultAliasFile>"


def test_a_help_anchor_is_retargeted_onto_its_heading_like_every_other_fragment(
    config, catalog, product, version, swap_flare
) -> None:
    """TRA Runtime Agent 5.12.4's `aa.adapter.services.folder.helpurl` named marker
    1684753, which the platform ignores, so the Help button opened the top of
    "Folder Reference": 345 entries in all 7 TRA versions (R8-04). `csh.yml` was
    written before the fragment pass and never revisited."""
    place_package(config, product, version, {
        "guide/Output.mcwebhelp": "",
        "guide/Data/HelpSystem.xml": "<x/>",
        "guide/Data/Alias.xml": _alias(
            ("aa.adapter.services.folder.helpurl", "a.htm#1684753"),
            ("page.only", "a.htm"),
            ("gone", "a.htm#nowhere"),
        ),
        "guide/a.htm": "<html><body>A</body></html>",
        "guide/b.htm": "<html><body>B</body></html>",
    })
    assert PackageExtractor(config, catalog).extract_one(product, version).outcome is (
        ExtractOutcome.EXTRACTED
    )
    swap_flare(_Sections)

    result, findings = convert(config, catalog, product, version)

    output = config.output_path(product.bu, product.family, product.slug, version.version)
    assert result.csh.entries == {
        "aa.adapter.services.folder.helpurl": "a.md#adapter-services-folder",
        "gone": "a.md#nowhere",
        "page.only": "a.md",
    }
    assert csh.render(result.csh.entries) == (output / "csh.yml").read_text(encoding="utf-8")
    # The one it cannot place is left as written and counted, never guessed at.
    unplaced = [f for f in findings.all if f.code == "FRAGMENT_UNPLACEABLE"]
    assert [f.count for f in unplaced] == [1]
    # A percent-encoded fragment names the same marker as its decoded form, and
    # was left pointing at it and reported as having no heading (R8-08).
    assert "(a.md#proxy-shed)" in (output / "b.md").read_text(encoding="utf-8")


def test_a_locked_versions_csv_on_the_current_path_fails_the_row_not_the_run(
    config, catalog, product, version, extracted, fake_engine, monkeypatch
) -> None:
    """X2-05. A `current` version with blank columns writes them, and that write
    sat outside `_build`'s `try`: `versions.csv` open in Excel raised out of
    `convert_one` and stopped the selection."""
    from docushift.catalog import CatalogError

    convert(config, catalog, product, version)
    catalog.clear_convert_inventory("tibco-ems", "10.4.0")

    def locked(*_args, **_kwargs):
        raise CatalogError("Could not write versions.csv. It is usually open in Excel.")

    monkeypatch.setattr(catalog, "record_convert_inventory", locked)

    again, _ = convert(config, catalog, product, version)

    assert again.outcome is ConvertOutcome.FAILED
    assert "open in Excel" in again.message


# -- a tree that should be rebuilt is not reported current (XE) -------------------


def test_a_sitemap_arriving_after_conversion_makes_the_tree_stale(
    config, catalog, product, version, extracted, fake_engine
) -> None:
    """X3-05. Converted before `catalog sitemap`, the version had no `301.yml`
    and every later run said `current` and kept it that way."""
    first, _ = convert(config, catalog, product, version)
    assert not (first.path / "301.yml").exists()
    assert convert(config, catalog, product, version)[0].outcome is ConvertOutcome.CURRENT

    cache_sitemap(config, product, version, listed_urls(catalog, product, version))
    again, _ = convert(config, catalog, product, version)

    assert again.outcome is ConvertOutcome.CONVERTED
    assert (again.path / "301.yml").is_file()
    assert convert(config, catalog, product, version)[0].outcome is ConvertOutcome.CURRENT


def test_an_origin_template_edit_makes_the_tree_stale(
    config, catalog, product, version, extracted, fake_engine
) -> None:
    """X1-08. `origin-urls.yaml` shapes `301.yml` and was outside the key."""
    convert(config, catalog, product, version)
    (config.config_dir / "origin-urls.yaml").write_text(
        "products:\n  tibco-ems:\n    template: 'https://docs.tibco.com/pub/{folder_path}/doc/{path}'\n"
        "    drop_segments: 1\n", encoding="utf-8")
    config._origin_urls_cache = None

    assert convert(config, catalog, product, version)[0].outcome is ConvertOutcome.CONVERTED


def test_a_display_name_edit_makes_the_tree_stale(
    config, catalog, product, version, extracted, fake_engine
) -> None:
    """X3-07. The display name titles the version's `toc.yml`."""
    convert(config, catalog, product, version)
    renamed = catalog.get_product("tibco-ems")
    renamed.display_name = "Spotfire EMS"

    again, _ = convert(config, catalog, renamed, version)

    assert again.outcome is ConvertOutcome.CONVERTED
    assert "Spotfire EMS" in (again.path / "toc.yml").read_text(encoding="utf-8")


def test_a_template_edit_makes_the_tree_stale(
    config, catalog, product, version, extracted, fake_engine
) -> None:
    """X3-07. `config/aem_templates/` renders the generated pages and `toc.yml`."""
    convert(config, catalog, product, version)
    template = config.aem_templates_dir / "metadata.yml.j2"
    template.write_text(template.read_text(encoding="utf-8") + "\n# edited\n", encoding="utf-8")

    assert convert(config, catalog, product, version)[0].outcome is ConvertOutcome.CONVERTED


def test_a_converter_version_bump_makes_every_tree_stale(
    config, catalog, product, version, extracted, fake_engine, monkeypatch
) -> None:
    """X3-06. Reframe has `_ALGORITHM`; convert had nothing, so a converter fix
    reached a converted tree only through a `--force` somebody remembered."""
    from docushift.converter import driver

    convert(config, catalog, product, version)
    monkeypatch.setattr(driver, "_CONVERTER_VERSION", driver._CONVERTER_VERSION + 1)

    assert convert(config, catalog, product, version)[0].outcome is ConvertOutcome.CONVERTED


def test_every_build_records_a_new_identity_and_a_current_run_keeps_it(
    config, catalog, product, version, extracted, fake_engine
) -> None:
    """X3-04. What `reframe` keys on: the identity of the converted tree, which
    a `convert --force` changes even when the package does not."""
    def build_id() -> str:
        return catalog.state.get_version_metadata("tibco-ems", "10.4.0").get("convert_build_id", "")

    convert(config, catalog, product, version)
    first = build_id()
    convert(config, catalog, product, version)
    assert first and build_id() == first

    convert(config, catalog, product, version, force=True)

    assert build_id() and build_id() != first


def test_a_version_with_no_package_checksum_says_why_it_is_rebuilt(
    config, catalog, product, version, extracted, fake_engine
) -> None:
    """X3-08. Such a version is rebuilt on every run, correctly, under a plain
    `converted` line that never said why."""
    catalog.state.set_version_metadata("tibco-ems", "10.4.0", "extract_zip_checksum", "")

    first, _ = convert(config, catalog, product, version)
    again, _ = convert(config, catalog, product, version)

    assert [first.outcome, again.outcome] == [ConvertOutcome.CONVERTED] * 2
    assert "no package checksum" in again.message


def test_a_current_run_points_at_the_run_that_holds_the_trees_findings(
    config, catalog, product, version, extracted, fake_engine
) -> None:
    """X3-11. Run 1 "1 error, 10 warnings", run 2 nothing: `report --run last`
    stopped showing errors the tree still had. A note now names the run."""
    first = FindingsRun("convert", store=catalog.state).start()
    DocumentConverter(config, catalog, findings=first).convert_one(product, version)
    first.finish()
    assert first.counts()[Severity.ERROR]

    second = FindingsRun("convert", store=catalog.state).start()
    result = DocumentConverter(config, catalog, findings=second).convert_one(product, version)
    second.finish()

    assert result.outcome is ConvertOutcome.CURRENT
    (pointer,) = [f for f in second.all if f.code == "CONVERT_FINDINGS_IN_EARLIER_RUN"]
    assert f"run {first.run_id}" in pointer.message and "error" in pointer.message
    assert f"docushift report --run {first.run_id}" in pointer.message
# -- an interrupted stage is never current (Phase 34, X3-01, X3-03, X3-09) -----


def test_a_tree_from_an_unfinished_extract_is_refused_not_converted(
    config, catalog, product, version, extracted, fake_engine
) -> None:
    """X3-01. A blank checksum read as "no claim", so a convert after an
    interrupted re-extract converted the half-deleted tree -- a whole book gone --
    and a later good extract made that output `current` for good."""
    catalog.state.mark_building("tibco-ems", "10.4.0", "extract")

    result, _ = convert(config, catalog, product, version)

    assert result.outcome is ConvertOutcome.FAILED
    assert "extract that did not finish" in result.message
    assert not config.output_path(product.bu, product.family, product.slug, version.version).exists()


def test_a_version_still_marked_as_building_is_rebuilt_not_current(
    config, catalog, product, version, extracted, fake_engine
) -> None:
    """X3-03. A kill between the swap and the bookkeeping left checksums that
    still matched, and the next run called a partly replaced tree `current`."""
    first, _ = convert(config, catalog, product, version)
    assert first.outcome is ConvertOutcome.CONVERTED
    assert not catalog.state.is_building("tibco-ems", "10.4.0", "convert")
    catalog.state.mark_building("tibco-ems", "10.4.0", "convert")

    again, _ = convert(config, catalog, product, version)
    settled, _ = convert(config, catalog, product, version)

    assert again.outcome is ConvertOutcome.CONVERTED
    assert settled.outcome is ConvertOutcome.CURRENT


def test_a_current_run_sweeps_a_killed_builds_part(
    config, catalog, product, version, extracted, fake_engine
) -> None:
    """X3-09: a 163-file `5.12.2.part` outlived every `current` run."""
    convert(config, catalog, product, version)
    output = config.output_path(product.bu, product.family, product.slug, version.version)
    staging = output.with_name(output.name + ".part")
    staging.mkdir()
    (staging / "half.md").write_text("", encoding="utf-8")

    again, _ = convert(config, catalog, product, version)

    assert again.outcome is ConvertOutcome.CURRENT
    assert not staging.exists()


# -- Phase 43: orphans out of the TOC, into `unfiled/` ---------------------------------


class OrphanEngine(FakeEngine):
    """The fake engine with its last topic left out of the TOC, as the four real
    engines report one: under an "Unfiled" node."""

    def convert_unit(self, context: ConversionContext, root: Path) -> Unit:
        unit = super().convert_unit(context, root)
        *filed, orphan = unit.documents
        unit.nav = [NavNode(label=document.title, document=document.relative) for document in filed]
        unit.nav.append(NavNode(label="Unfiled", children=[
            NavNode(label=orphan.title, document=orphan.relative)]))
        return unit


@pytest.fixture
def orphan_engine():
    previous = engine_for(SourceEngine.FLARE)
    register(OrphanEngine)
    yield OrphanEngine
    unregister(SourceEngine.FLARE)
    if previous is not None:
        register(previous)


def test_a_converted_orphan_is_shelved_under_unfiled_and_mapped_there(
    config, catalog, product, version, extracted, orphan_engine
) -> None:
    result, _ = convert(config, catalog, product, version)

    output = config.output_path(product.bu, product.family, product.slug, version.version)
    assert result.outcome is ConvertOutcome.CONVERTED
    assert (output / "unfiled" / "Content" / "topic.md").is_file()
    assert not (output / "Content" / "topic.md").exists()
    assert "Unfiled" not in (output / "toc.yml").read_text(encoding="utf-8")
    # Its images still resolve from the new folder.
    body = (output / "unfiled" / "Content" / "topic.md").read_text(encoding="utf-8")
    assert "](../../Content/images/shot.png)" in body
    rows = catalog.state.get_output_map("tibco-ems", "10.4.0")
    assert rows == {"guide/Content/second.htm": "Content/second.md",
                    "guide/Content/topic.htm": "unfiled/Content/topic.md"}


def test_reshelving_a_tree_written_before_phase_43_stamps_it_current(
    config, catalog, product, version, extracted, fake_engine
) -> None:
    """The ~160 versions no longer unpacked are fixed from their output alone,
    and a tree that differs from a fresh build only by this pass is current."""
    from docushift.converter import driver

    convert(config, catalog, product, version)
    output = config.output_path(product.bu, product.family, product.slug, version.version)
    # Put the tree back the way converter version 2 wrote it.
    textfile.write_text(output / "toc.yml", (
        'docs_list_title: "Online Help"\ndocs:\n'
        '  - title: "second"\n    url: "Content/second.md"\n'
        '  - title: "Unfiled"\n    url: "Content/unfiled.md"\n    subfolderlist:\n'
        '      - title: "topic"\n        url: "Content/topic.md"\n'))
    textfile.write_text(output / "Content" / "unfiled.md",
                        '---\ntitle: "Unfiled"\ngenerated: true\n---\n\n# Unfiled\n\n- [topic](topic.md)\n')
    converter = DocumentConverter(config, catalog, findings=FindingsRun("convert"))
    old_key = converter._inputs_key(product, version, driver._CONVERTER_VERSION - 1)
    catalog.state.set_version_metadata("tibco-ems", "10.4.0", "convert_inputs_key", old_key)
    build = catalog.state.get_version_metadata("tibco-ems", "10.4.0")["convert_build_id"]

    result = converter.reshelve_one(product, version)

    assert result.outcome is ConvertOutcome.CONVERTED, result.message
    assert (output / "unfiled" / "Content" / "topic.md").is_file()
    metadata = catalog.state.get_version_metadata("tibco-ems", "10.4.0")
    assert metadata["convert_build_id"] != build
    assert catalog.state.get_output_map("tibco-ems", "10.4.0")["guide/Content/topic.htm"] == \
        "unfiled/Content/topic.md"
    again, _ = convert(config, catalog, product, version)
    assert again.outcome is ConvertOutcome.CURRENT
    assert converter.reshelve_one(product, version).outcome is ConvertOutcome.CURRENT


def test_convert_reshelve_orphans_runs_over_the_selection_and_refuses_force(
    config, catalog, product, version, extracted, orphan_engine
) -> None:
    convert(config, catalog, product, version)
    root = ["--root", str(config.root_dir), "convert", "--product", "tibco-ems"]

    refused = CliRunner().invoke(main, [*root, "--reshelve-orphans", "--force"])
    result = CliRunner().invoke(main, [*root, "--reshelve-orphans"])

    assert refused.exit_code == 2 and "--reshelve-orphans" in refused.output
    assert result.exit_code == 0, result.output
    assert "1 nothing to move" in result.output
