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

import pytest
from click.testing import CliRunner

from docushift.catalog import CatalogManager
from docushift.cli import main
from docushift.config import ConfigManager
from docushift.converter import ConvertOutcome, DocumentConverter
from docushift.engines.base import (
    BaseEngine,
    ConversionContext,
    Document,
    Unit,
    engine_for,
    register,
    registered_engines,
    unregister,
)
from docushift.extractor import ExtractOutcome, PackageExtractor
from docushift.models import ConversionStatus, Product, ProductVersion, SourceEngine
from docushift.reporting.findings import FindingsRun, Severity
from docushift.transforms import csh
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

    def convert_unit(self, context: ConversionContext, root: Path) -> Unit:
        unit = Unit(root=root, name=root.relative_to(context.tree).as_posix())
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
        SourceEngine.DITA, SourceEngine.FLARE, SourceEngine.WEBWORKS,
    ]
    assert engine_for(SourceEngine.DOCBOOK) is None


def test_a_version_reports_engine_unknown_when_nothing_is_registered(
    config, catalog, product, version, extracted
) -> None:
    version.engine = SourceEngine.DOCBOOK
    result, findings = convert(config, catalog, product, version)

    assert result.outcome is ConvertOutcome.ENGINE_UNKNOWN
    assert [f.code for f in findings.all] == ["ENGINE_UNKNOWN"]
    assert findings.all[0].severity is Severity.WARNING


def test_auto_and_an_unwritten_handler_are_one_path_and_one_code(
    config, catalog, product, version, extracted
) -> None:
    """Invariant 7: never guess. Three conditions, one action, one finding."""
    version.engine = SourceEngine.AUTO
    auto, _ = convert(config, catalog, product, version)
    version.engine = SourceEngine.DOCBOOK
    unwritten, _ = convert(config, catalog, product, version)

    assert auto.outcome is unwritten.outcome is ConvertOutcome.ENGINE_UNKNOWN
    assert "auto" in auto.message
    assert "docbook" in unwritten.message


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
    assert (output / "guide" / "Content" / "topic.md").is_file()
    assert result.skipped == {"frameset": 1}


def test_a_relative_link_exists_exactly_when_the_asset_was_copied(
    config, catalog, product, version, extracted, fake_engine
) -> None:
    """Invariant 13, asserted on the output rather than on the copier."""
    result, _ = convert(config, catalog, product, version)

    output = config.output_path(product.bu, product.family, product.slug, version.version)
    body = (output / "guide" / "Content" / "topic.md").read_text(encoding="utf-8")
    assert "![](images/shot.png)" in body
    assert (output / "guide" / "Content" / "images" / "shot.png").is_file()
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
    assert not (output / "guide" / "Content" / "images" / "orphan.png").exists()
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
    assert [f.path for f in unresolved] == ["guide/Content"]
    assert unresolved[0].severity is Severity.ERROR


def test_the_output_map_is_recorded_for_the_csh_resolver(
    config, catalog, product, version, extracted, fake_engine
) -> None:
    convert(config, catalog, product, version)

    mapping = catalog.state.get_output_map("tibco-ems", "10.4.0")
    assert mapping["guide/Content/topic.htm"] == "guide/Content/topic.md"


def test_csh_yml_is_flat_quoted_and_omits_what_did_not_resolve(
    config, catalog, product, version, extracted, fake_engine
) -> None:
    result, findings = convert(config, catalog, product, version)

    output = config.output_path(product.bu, product.family, product.slug, version.version)
    assert (output / "csh.yml").read_text(encoding="utf-8") == '"install": "guide/Content/topic.md"\n'
    # The unresolved digit-only identifier is not in the file and is not lost.
    assert [entry.identifier for entry in result.csh.unresolved] == ["1234"]
    assert [f.code for f in findings.all if f.code == "CSH_UNRESOLVED"] == ["CSH_UNRESOLVED"]


def test_identifiers_reach_the_topics_first_and_only_write(
    config, catalog, product, version, extracted, fake_engine
) -> None:
    """§9.5. There is no second pass, so a missing key here can never be repaired."""
    convert(config, catalog, product, version)

    output = config.output_path(product.bu, product.family, product.slug, version.version)
    owner = (output / "guide" / "Content" / "topic.md").read_text(encoding="utf-8")
    other = (output / "guide" / "Content" / "second.md").read_text(encoding="utf-8")
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


def test_findings_are_flushed_per_version(
    config, catalog, product, version, extracted, fake_engine
) -> None:
    findings = FindingsRun("convert", store=catalog.state).start()
    DocumentConverter(config, catalog, findings=findings).convert_one(product, version)

    rows = catalog.state.get_findings(findings.run_id)
    assert {row["code"] for row in rows} == {"REFERENCE_UNRESOLVED", "ASSET_ORPHANED", "CSH_UNRESOLVED"}
    assert findings.pending == []


# -- the command ---------------------------------------------------------------


def test_convert_reports_engine_unknown_and_still_exits_zero(
    config, catalog, product, version, extracted, tmp_path
) -> None:
    """One unconvertible version does not stop a 200-version batch."""
    runner = CliRunner()

    result = runner.invoke(
        main,
        ["--root", str(config.root_dir), "convert", "--product", "tibco-ems", "--version", "10.4.0"],
    )

    assert result.exit_code == 0, result.output
    assert "Engine unknown" in result.output


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
