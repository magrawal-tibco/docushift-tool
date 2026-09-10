"""Unit tests for ConfigManager path resolution, YAML loading, and taxonomy rules.

`resolve_product_info` is rule-driven rather than product-driven: per-product
bu/family assignment lives in config/products.csv, so the taxonomy only declares
which families exist and how to guess one. See docs/architecture.md §3.3.
"""

from pathlib import Path

import pytest

from docushift.config import ConfigManager
from docushift.models import FamilySource, ReleaseStatus

RULES_YAML = (
    "business_units:\n"
    "  tibco:\n"
    "    name: TIBCO\n"
    "    families:\n"
    "      messaging: {name: Messaging}\n"
    "      general: {name: General}\n"
    "  ibi:\n"
    "    name: ibi\n"
    "    families:\n"
    "      webfocus: {name: WebFOCUS}\n"
    "rules:\n"
    '  - match: ["ems", "enterprise message service"]\n'
    "    bu: tibco\n"
    "    family: messaging\n"
    '  - match: ["webfocus"]\n'
    "    bu: ibi\n"
    "    family: webfocus\n"
)


def test_creates_working_directories(project_root: Path) -> None:
    ConfigManager(root_dir=project_root)

    assert (project_root / "cache").is_dir()
    assert (project_root / "families").is_dir()
    assert (project_root / "output").is_dir()


def test_family_workspace_paths(config: ConfigManager, project_root: Path) -> None:
    families = project_root / "families" / "en-us-tibco-data-management"

    assert config.family_workspace_name("tibco", "data_management") == "en-us-tibco-data-management"
    assert config.family_dir("tibco", "data_management") == families
    assert config.downloads_dir("tibco", "data_management") == families / "downloads"
    assert config.extracted_dir("tibco", "data_management") == families / "extracted"
    assert config.archive_dir("tibco", "data_management") == families / "archive"


def test_download_and_extract_paths_are_keyed_by_the_catalog(config: ConfigManager) -> None:
    """Both paths derive from `slug` + `version`, so state.db can round-trip them."""
    family = config.family_dir("tibco", "messaging")
    slug = "tibco-enterprise-message-service"

    assert config.download_path("tibco", "messaging", slug, "10.4.0") == family / "downloads" / f"{slug}-10.4.0.zip"
    # Dots survive in the working tree; dots-to-dashes is a Stage 6 output concern.
    assert config.extract_path("tibco", "messaging", slug, "10.4.0") == family / "extracted" / slug / "10.4.0"


def test_two_products_sharing_a_code_do_not_share_a_path(config: ConfigManager) -> None:
    """The reason the paths take the slug: `product_code` is not unique.

    Both of these carry `product_code=clarity-dt` and both live in the same family,
    so a code-named ZIP would put two different products' packages at one path and
    a code-named extract directory would interleave two trees.
    """
    one = "tibco-clarity"
    two = "tibco-clarity-enterprise-edition"

    assert config.download_path("tibco", "data_management", one, "3.1.0") != config.download_path(
        "tibco", "data_management", two, "3.1.0"
    )
    assert config.extract_path("tibco", "data_management", one, "3.1.0") != config.extract_path(
        "tibco", "data_management", two, "3.1.0"
    )


def test_locale_prefix_is_configurable(project_root: Path) -> None:
    cfg = ConfigManager(root_dir=project_root, locale="fr-fr")

    assert cfg.family_workspace_name("tibco", "messaging") == "fr-fr-tibco-messaging"


def _write_publishing(project_root: Path, body: str) -> None:
    (project_root / "config" / "publishing.yaml").write_text(body, encoding="utf-8")


PUBLISHING_TAXONOMY = (
    "business_units:\n"
    "  tibco:\n"
    "    name: TIBCO\n"
    "    repo_slug: tib\n"
    "    families:\n"
    "      messaging: {name: Messaging}\n"
    "      data_management: {name: Data Management, repo_slug: mdm}\n"
    "  ibi:\n"
    "    name: ibi\n"
    "    families:\n"
    "      webfocus: {name: WebFOCUS}\n"
    "rules: []\n"
)


@pytest.fixture
def publishing_config(project_root: Path) -> ConfigManager:
    """A ConfigManager over a taxonomy that exercises `repo_slug` on both levels."""
    (project_root / "config" / "taxonomy.yaml").write_text(PUBLISHING_TAXONOMY, encoding="utf-8")
    return ConfigManager(root_dir=project_root)


def test_repo_slug_overrides_the_key_and_otherwise_slugifies_it(publishing_config: ConfigManager) -> None:
    assert publishing_config.repo_slug("tibco") == "tib"
    assert publishing_config.repo_slug("ibi") == "ibi"
    assert publishing_config.repo_slug("tibco", "data_management") == "mdm"
    assert publishing_config.repo_slug("tibco", "messaging") == "messaging"


def test_repo_slug_names_a_folder_for_an_undeclared_family(publishing_config: ConfigManager) -> None:
    """An auto-registered family (§4.2) still has to name a workspace folder."""
    assert publishing_config.family_workspace_name("tibco", "mesaging") == "en-us-tib-mesaging"


def test_workspace_and_tree_names_use_the_repo_slug(publishing_config: ConfigManager) -> None:
    assert publishing_config.family_workspace_name("tibco", "messaging") == "en-us-tib-messaging"
    assert publishing_config.docs_tree_name("tibco", "messaging") == "en-us-tib-messaging-userdocs"
    assert publishing_config.resources_tree_name("tibco", "messaging") == "en-us-tib-messaging-userdocs-resources"


def test_a_localized_run_publishes_to_loc_and_has_no_resources_tree(project_root: Path) -> None:
    (project_root / "config" / "taxonomy.yaml").write_text(PUBLISHING_TAXONOMY, encoding="utf-8")
    cfg = ConfigManager(root_dir=project_root, locale="ja-jp")

    assert cfg.family_workspace_name("tibco", "messaging") == "ja-jp-tib-messaging"
    assert cfg.docs_tree_name("tibco", "messaging") == "loc-tib-messaging-userdocs"
    assert not cfg.publishes_resources()
    with pytest.raises(ValueError, match="ja-jp"):
        cfg.resources_tree_name("tibco", "messaging")


def test_publishing_defaults_apply_with_no_file(config: ConfigManager) -> None:
    """Nothing publishes until Stage 7; a fresh checkout must still name a folder."""
    assert config.load_publishing() == {
        "docs_suffix": "userdocs",
        "resources_suffix": "resources",
        "localized_prefix": "loc",
        "primary_locale": "en-us",
    }


def test_a_partial_publishing_file_falls_back_key_by_key(project_root: Path) -> None:
    _write_publishing(project_root, "docs_suffix: docs\n")
    cfg = ConfigManager(root_dir=project_root)

    assert cfg.load_publishing()["docs_suffix"] == "docs"
    assert cfg.load_publishing()["resources_suffix"] == "resources"


def test_changing_the_suffix_moves_every_tree_name_together(project_root: Path) -> None:
    """The point of holding the suffix in config rather than in a literal."""
    (project_root / "config" / "taxonomy.yaml").write_text(PUBLISHING_TAXONOMY, encoding="utf-8")
    _write_publishing(project_root, "docs_suffix: docs\n")

    english = ConfigManager(root_dir=project_root)
    localized = ConfigManager(root_dir=project_root, locale="ja-jp")

    assert english.docs_tree_name("tibco", "messaging") == "en-us-tib-messaging-docs"
    assert english.resources_tree_name("tibco", "messaging") == "en-us-tib-messaging-docs-resources"
    assert localized.docs_tree_name("tibco", "messaging") == "loc-tib-messaging-docs"
    # The workspace is not a repo name and must not follow the suffix.
    assert english.family_workspace_name("tibco", "messaging") == "en-us-tib-messaging"


def test_publishing_problems_flags_a_duplicate_repo_slug_within_a_bu(project_root: Path) -> None:
    (project_root / "config" / "taxonomy.yaml").write_text(
        "business_units:\n"
        "  tibco:\n"
        "    name: TIBCO\n"
        "    families:\n"
        "      messaging: {name: Messaging, repo_slug: msg}\n"
        "      streaming: {name: Streaming, repo_slug: msg}\n"
        "rules: []\n",
        encoding="utf-8",
    )
    problems = ConfigManager(root_dir=project_root).publishing_problems()

    assert len(problems) == 1
    assert "'messaging' and 'streaming'" in problems[0]
    assert "repo_slug 'msg'" in problems[0]


def test_the_same_repo_slug_in_two_business_units_is_fine(project_root: Path) -> None:
    """`general` exists under both BUs and the BU token keeps the trees apart."""
    (project_root / "config" / "taxonomy.yaml").write_text(
        "business_units:\n"
        "  tibco: {name: TIBCO, families: {general: {name: General}}}\n"
        "  ibi: {name: ibi, families: {general: {name: General}}}\n"
        "rules: []\n",
        encoding="utf-8",
    )
    assert ConfigManager(root_dir=project_root).publishing_problems() == []


@pytest.mark.parametrize("suffix", ["user-docs", "UserDocs", "user docs"])
def test_publishing_problems_flags_a_multi_token_suffix(project_root: Path, suffix: str) -> None:
    """A hyphen makes the family/suffix boundary unparseable."""
    _write_publishing(project_root, f"docs_suffix: '{suffix}'\n")
    problems = ConfigManager(root_dir=project_root).publishing_problems()

    assert len(problems) == 1
    assert "docs_suffix" in problems[0]


def test_the_shipped_publishing_config_is_valid(repo_root: Path) -> None:
    """The one test that would catch a bad token being shipped rather than typed."""
    cfg = ConfigManager(root_dir=repo_root)

    assert cfg.publishing_problems() == []
    assert cfg.load_publishing()["docs_suffix"] == "userdocs"
    assert cfg.repo_slug("tibco") == "tib"
    assert cfg.docs_tree_name("tibco", "messaging") == "en-us-tib-messaging-userdocs"


def test_family_folders_are_not_precreated(config: ConfigManager, project_root: Path) -> None:
    assert not config.family_dir("tibco", "messaging").exists()


def test_resolved_paths(config: ConfigManager, project_root: Path) -> None:
    assert config.taxonomy_path == project_root / "config" / "taxonomy.yaml"
    assert config.docsite_path == project_root / "config" / "docsite.yaml"
    assert config.aem_templates_dir == project_root / "config" / "aem_templates"
    assert config.state_db_path == project_root / "cache" / "state.db"


def test_catalog_paths_are_the_csv_pair(config: ConfigManager, project_root: Path) -> None:
    """The JSON catalog was retired in Phase 2 in favour of two CSVs."""
    assert config.products_path == project_root / "config" / "products.csv"
    assert config.versions_path == project_root / "config" / "versions.csv"
    assert not hasattr(config, "catalog_path")


def test_missing_taxonomy_yields_empty_structure(config: ConfigManager) -> None:
    assert config.load_taxonomy() == {"business_units": {}, "rules": []}


def test_missing_docsite_yields_empty_dict(config: ConfigManager) -> None:
    assert config.load_docsite() == {}


def test_taxonomy_is_cached(config: ConfigManager) -> None:
    config.taxonomy_path.write_text('business_units:\n  tibco:\n    name: "TIBCO"\n', encoding="utf-8")
    first = config.load_taxonomy()

    config.taxonomy_path.write_text("business_units: {}\n", encoding="utf-8")

    assert config.load_taxonomy() is first


def test_docsite_loads_endpoints(config: ConfigManager) -> None:
    config.docsite_path.write_text(
        'base_url: "https://docs.tibco.com"\nendpoints:\n  a_to_z: "/api/a_to_z"\n',
        encoding="utf-8",
    )

    assert config.load_docsite()["endpoints"]["a_to_z"] == "/api/a_to_z"


def test_families_are_listed_per_business_unit(config: ConfigManager) -> None:
    config.taxonomy_path.write_text(RULES_YAML, encoding="utf-8")

    assert set(config.families("tibco")) == {"messaging", "general"}
    assert set(config.families("ibi")) == {"webfocus"}
    assert config.families("nonexistent") == {}


def test_is_known_family_is_scoped_to_its_business_unit(config: ConfigManager) -> None:
    """`webfocus` is a real family, but not under `tibco`."""
    config.taxonomy_path.write_text(RULES_YAML, encoding="utf-8")

    assert config.is_known_family("ibi", "webfocus") is True
    assert config.is_known_family("tibco", "webfocus") is False


def test_resolve_product_info_matches_a_rule_by_product_code(config: ConfigManager) -> None:
    config.taxonomy_path.write_text(RULES_YAML, encoding="utf-8")

    info = config.resolve_product_info("ems", "TIBCO Enterprise Message Service")

    assert info["bu"] == "tibco"
    assert info["family"] == "messaging"
    assert info["family_source"] is FamilySource.TAXONOMY_RULE
    assert info["display_name"] == "TIBCO Enterprise Message Service"


def test_resolve_product_info_matches_a_rule_by_display_name_substring(config: ConfigManager) -> None:
    config.taxonomy_path.write_text(RULES_YAML, encoding="utf-8")

    info = config.resolve_product_info("wf-client", "ibi WebFOCUS Client")

    assert (info["bu"], info["family"]) == ("ibi", "webfocus")


def test_resolve_product_info_is_case_insensitive(config: ConfigManager) -> None:
    config.taxonomy_path.write_text(RULES_YAML, encoding="utf-8")

    assert config.resolve_product_info("EMS", "EMS")["family"] == "messaging"


def test_unmatched_products_are_unclassified_not_guessed(config: ConfigManager) -> None:
    """Flagging a product for triage beats inventing a family for it."""
    config.taxonomy_path.write_text(RULES_YAML, encoding="utf-8")

    info = config.resolve_product_info("unknown-thing", "Some Unlisted Product")

    assert (info["bu"], info["family"]) == ("tibco", "general")
    assert info["family_source"] is FamilySource.UNCLASSIFIED


def test_resolve_product_info_never_returns_an_engine(config: ConfigManager) -> None:
    """Engine is a per-version property detected from the package, not a rule output."""
    config.taxonomy_path.write_text(RULES_YAML, encoding="utf-8")

    assert "engine" not in config.resolve_product_info("ems", "EMS")


# -- scope.yaml (architecture.md §3.10) --------------------------------------


def test_missing_scope_yields_no_exclusions(config: ConfigManager) -> None:
    """A fresh checkout with no scope.yaml excludes nothing, rather than erroring."""
    assert config.load_scope() == {}


def test_scope_loads_slug_to_reason(config: ConfigManager) -> None:
    config.scope_path.write_text(
        "out_of_scope:\n"
        '  - slug: ebx\n    display_name: "TIBCO EBX"\n    reason: "EBX is out of scope"\n'
        "  - slug: spotfire\n    reason: \"Spotfire is out of scope\"\n",
        encoding="utf-8",
    )

    assert config.load_scope() == {"ebx": "EBX is out of scope", "spotfire": "Spotfire is out of scope"}


def test_scope_accepts_a_bare_slug_with_no_reason(config: ConfigManager) -> None:
    config.scope_path.write_text("out_of_scope:\n  - ebx\n  - Spotfire-Server\n", encoding="utf-8")

    assert config.load_scope() == {"ebx": "", "spotfire-server": ""}


def test_duplicate_scope_slug_is_an_error(config: ConfigManager) -> None:
    """Two entries for one product means two reasons, one of them about to vanish."""
    config.scope_path.write_text(
        'out_of_scope:\n  - slug: ebx\n    reason: "first"\n  - slug: ebx\n    reason: "second"\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate out_of_scope slug 'ebx'"):
        config.load_scope()


def test_shipped_scope_lists_the_ebx_and_spotfire_products(repo_root: Path) -> None:
    """A guard on the real config/scope.yaml, verified against the A-to-Z index."""
    rules = ConfigManager(root_dir=repo_root).load_scope()

    assert len(rules) == 61
    for slug in ("tibco-ebx", "spotfire", "spotfire-server", "spotfire-desktop", "tibco-spotfire-for-apple-ipad"):
        assert slug in rules
    # The look-alikes the exact-slug rule exists to protect -- see §3.10.
    for slug in ("tibco-businessconnect-ebxml-protocol", "spotfire-data-streams", "spotfire-statistics-services"):
        assert slug not in rules


# -- eos.yaml and the support report (architecture.md §3.11) -----------------


def _write_eos(config: ConfigManager, rows: str, aliases: str = "") -> None:
    """Writes a two-file end-of-support setup: the support CSV and our YAML.

    `rows` is the body of the report, without its header. The BOM and the trailing
    header comma are reproduced because the real report has both, and neither may
    be something the loader has to be shielded from.
    """
    report = config.config_dir / "eos" / "report.csv"
    report.parent.mkdir(parents=True, exist_ok=True)
    header = "Product Name,Version,Release Status,Retirement Date,Last Updated On,\n"
    report.write_text(header + rows, encoding="utf-8-sig")
    config.eos_path.write_text(f"report: eos/report.csv\n{aliases}", encoding="utf-8")


def test_missing_eos_yields_no_retirements(config: ConfigManager) -> None:
    """A fresh checkout with no eos.yaml retires nothing, rather than erroring."""
    report = config.load_eos()

    assert report.entries == {}
    assert report.status_for("tibco-ems", "8.6.0") is None


def test_a_report_row_is_keyed_by_the_slugified_name(config: ConfigManager) -> None:
    _write_eos(config, "TIBCO Enterprise Message Service,8.6.0,Retired,12-31-2024,01-05-2025,\n")

    assert config.load_eos().status_for("tibco-enterprise-message-service", "8.6.0") == (
        ReleaseStatus.RETIRED,
        "2024-12-31",
    )


def test_the_report_date_is_read_month_first(config: ConfigManager) -> None:
    """`03-04-2021` is 4 March. Read day-first it would silently become 3 April."""
    _write_eos(config, "TIBCO EMS,1.0.0,Retired,03-04-2021,01-05-2025,\n")

    assert config.load_eos().status_for("tibco-ems", "1.0.0") == (ReleaseStatus.RETIRED, "2021-03-04")


def test_an_unparseable_date_survives_verbatim(config: ConfigManager) -> None:
    """A format change from support must be visible in the sheet, not blanked."""
    _write_eos(config, "TIBCO EMS,1.0.0,Retired,Q3 2026,01-05-2025,\n")

    assert config.load_eos().status_for("tibco-ems", "1.0.0") == (ReleaseStatus.RETIRED, "Q3 2026")


def test_the_three_report_statuses_all_parse(config: ConfigManager) -> None:
    _write_eos(
        config,
        "TIBCO EMS,1.0.0,Retired,12-31-2024,01-05-2025,\n"
        "TIBCO EMS,2.0.0,Retirement Announced,12-31-2027,01-05-2025,\n"
        "TIBCO EMS,3.0.0,GA,12-31-2030,01-05-2025,\n",
    )

    report = config.load_eos()

    assert report.status_for("tibco-ems", "1.0.0")[0] is ReleaseStatus.RETIRED
    assert report.status_for("tibco-ems", "2.0.0")[0] is ReleaseStatus.RETIREMENT_ANNOUNCED
    assert report.status_for("tibco-ems", "3.0.0")[0] is ReleaseStatus.GA
    assert report.unknown_statuses == []


def test_an_unrecognized_status_is_reported_not_guessed_at(config: ConfigManager) -> None:
    """A new spelling from support must not silently read as "not retired"."""
    _write_eos(config, "TIBCO EMS,1.0.0,End of Life,12-31-2024,01-05-2025,\n")

    report = config.load_eos()

    assert report.status_for("tibco-ems", "1.0.0") is None
    assert report.unknown_statuses == ["end of life"]


def test_version_matching_is_exact_string_equality(config: ConfigManager) -> None:
    """`1.10` is not `1.1`, and `1.0` is not `1.0.0` -- the whole reason for the CSV layer."""
    _write_eos(config, "TIBCO EMS,1.10,Retired,12-31-2024,01-05-2025,\n")

    report = config.load_eos()

    assert report.status_for("tibco-ems", "1.10")[0] is ReleaseStatus.RETIRED
    assert report.status_for("tibco-ems", "1.1") is None


def test_a_trailing_zero_is_not_coerced(config: ConfigManager) -> None:
    _write_eos(config, "TIBCO EMS,10.4,Retired,12-31-2024,01-05-2025,\n")

    assert config.load_eos().status_for("tibco-ems", "10.4.0") is None


def test_an_alias_redirects_a_report_name_to_a_catalog_slug(config: ConfigManager) -> None:
    """The report carries no slug and no code, so a rename is only bridgeable by hand."""
    _write_eos(
        config,
        "TIBCO Data Streams,10.6.0,Retired,12-31-2024,01-05-2025,\n",
        aliases='aliases:\n  - report_name: "TIBCO Data Streams"\n    slug: spotfire-data-streams\n',
    )

    report = config.load_eos()

    assert report.status_for("spotfire-data-streams", "10.6.0")[0] is ReleaseStatus.RETIRED
    # The slugified name is not *also* populated: one row, one product.
    assert report.status_for("tibco-data-streams", "10.6.0") is None


def test_a_duplicate_alias_is_an_error(config: ConfigManager) -> None:
    """Two mappings for one report name means one of them is about to be discarded."""
    _write_eos(
        config,
        "TIBCO EMS,1.0.0,Retired,12-31-2024,01-05-2025,\n",
        aliases='aliases:\n  - report_name: "EBX"\n    slug: tibco-ebx\n'
        '  - report_name: "EBX"\n    slug: spotfire\n',
    )

    with pytest.raises(ValueError, match="duplicate alias report_name 'EBX'"):
        config.load_eos()


def test_an_alias_with_no_slug_is_an_error(config: ConfigManager) -> None:
    _write_eos(
        config,
        "TIBCO EMS,1.0.0,Retired,12-31-2024,01-05-2025,\n",
        aliases='aliases:\n  - report_name: "EBX"\n    note: "meant to fill this in"\n',
    )

    with pytest.raises(ValueError, match="alias 'EBX' has no slug"):
        config.load_eos()


def test_a_report_that_is_not_there_is_an_error(config: ConfigManager) -> None:
    """Silently retiring nothing is the one failure mode this file cannot afford."""
    config.eos_path.write_text("report: eos/gone.csv\n", encoding="utf-8")

    with pytest.raises(ValueError, match="not found"):
        config.load_eos()


def test_two_names_resolving_to_one_slug_and_disagreeing_is_an_error(config: ConfigManager) -> None:
    """The alias-is-wrong detector: picking one verdict silently is how that stays hidden."""
    _write_eos(
        config,
        "TIBCO EMS,1.0.0,Retired,12-31-2024,01-05-2025,\nEMS Classic,1.0.0,GA,12-31-2030,01-05-2025,\n",
        aliases='aliases:\n  - report_name: "EMS Classic"\n    slug: tibco-ems\n',
    )

    with pytest.raises(ValueError, match="disagree about version 1.0.0"):
        config.load_eos()


def test_a_repeated_row_with_the_same_verdict_is_harmless(config: ConfigManager) -> None:
    """The real report has two exact duplicates and zero conflicts over 5,948 rows."""
    _write_eos(
        config,
        "TIBCO EMS,1.0.0,Retired,12-31-2024,01-05-2025,\nTIBCO EMS,1.0.0,Retired,12-31-2024,01-05-2025,\n",
    )

    assert config.load_eos().status_for("tibco-ems", "1.0.0")[0] is ReleaseStatus.RETIRED


def test_an_alias_the_report_never_mentions_is_reported(config: ConfigManager) -> None:
    """The rename detector: the day support renames a product, the alias stops working."""
    _write_eos(
        config,
        "TIBCO EMS,1.0.0,Retired,12-31-2024,01-05-2025,\n",
        aliases='aliases:\n  - report_name: "Renamed Upstream"\n    slug: tibco-ebx\n',
    )

    assert config.load_eos().unmatched_aliases == ["Renamed Upstream"]


def test_the_shipped_eos_config_resolves_cleanly(repo_root: Path) -> None:
    """A guard on the real config/eos.yaml and the report it names."""
    report = ConfigManager(root_dir=repo_root).load_eos()

    assert len(report.report_names) == 528
    assert report.unmatched_aliases == []
    assert report.unknown_statuses == []
    # The reviewed rename, and the look-alike the review rejected: `Spotfire
    # Analytics` shares 0 of 7 versions with `tibco-analytics`, so it is not an alias.
    assert report.aliases["EBX"] == "tibco-ebx"
    assert "Spotfire Analytics" not in report.aliases
    assert report.status_for("tibco-ebx", "5.9.0") == (ReleaseStatus.RETIRED, "2024-06-30")


def test_shipped_taxonomy_rules_classify_known_products(repo_root: Path) -> None:
    """A guard on the real config/taxonomy.yaml, not a synthetic one."""
    cfg = ConfigManager(root_dir=repo_root)

    assert cfg.resolve_product_info("ems", "TIBCO Enterprise Message Service")["family"] == "messaging"
    assert cfg.resolve_product_info("spotfire", "TIBCO Spotfire")["family"] == "analytics"
    assert cfg.resolve_product_info("webfocus", "ibi WebFOCUS")["bu"] == "ibi"
    assert cfg.resolve_product_info("ebx", "TIBCO EBX")["family"] == "data_management"
