"""Stage 6b: the engine gate, the TOC adapter seam, the policy, and the swap.

Phase 20a builds no packer, so these tests are about the two things that have to be
right before one can be written: that the stage refuses to touch what is not Flare,
and that it refuses to guess at a navigation it does not recognise. The merge's own
acceptance checks (requirements §6) arrive with the merge.
"""

from pathlib import Path

import pytest
import yaml

from docushift.config import ConfigManager
from docushift.models import SourceEngine
from docushift.reframe import ReframeOutcome, Reframer, policy_for
from docushift.reframe.policy import ReframePolicy
from docushift.reframe.toc import ItemsPathChildren, TocEntry, registered_schemas, schema_for
from docushift.reporting.findings import FindingsRun, Severity
from tests.conftest import make_product, make_version

TOC = """\
items:
  - title: "Installation"
    path: "installation/installation-2.md"
    children:
      - title: "Installation Overview"
        path: "installation/installation-overvie.md"
  - title: "User Guide"
    path: "users-guide/user-guide.md"
"""


def codes(findings) -> list[str]:
    return [finding.code for finding in findings]


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
    for row in yaml.safe_load(toc).get("items") or []:
        for path in [row["path"], *[c["path"] for c in row.get("children") or []]]:
            page = tree / path
            page.parent.mkdir(parents=True, exist_ok=True)
            page.write_text(f"# {path}\n", encoding="utf-8")
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


# -- the passthrough and the swap (C4) ----------------------------------------


def test_a_flare_set_passes_through_byte_identical(config, catalog, flare):
    """Phase 20a's whole visible behaviour, and the baseline 20b diffs against."""
    source = converted_tree(config, flare, "10.5.1")
    before = {p.relative_to(source).as_posix(): p.read_bytes() for p in source.rglob("*") if p.is_file()}

    result = Reframer(config, catalog).reframe_one(flare, flare.versions["10.5.1"])

    assert result.outcome is ReframeOutcome.REFRAMED
    assert result.toc_schema == "items-path-children"
    assert result.topics == 3
    after = {p.relative_to(result.path).as_posix(): p.read_bytes() for p in result.path.rglob("*") if p.is_file()}
    assert after == before


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


# -- the TOC adapter seam -----------------------------------------------------


def test_the_shipped_schema_reads_what_stage_6a_writes():
    schema = ItemsPathChildren()
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


def test_detection_declines_a_foreign_shape_rather_than_half_reading_it():
    assert schema_for({"toc": [{"label": "x"}]}) is None
    assert schema_for(None) is None
    assert registered_schemas() == ["items-path-children"]


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
