"""Unit tests for Stage 4's second half: the one walk (design.md §6.2, §6.3, §6.4).

Split out of `test_extractor.py` rather than appended to it. That file is about
unpacking and identifying a package; this one is about measuring it, and the two
have different fixtures -- most of what follows needs a tree and no catalog at
all, because the predicate and the walk are pure functions over a directory.

Every case here is one of the findings the corpus surveys paid for. The rule they
all pin, and the one this phase exists to enforce: **a marker decides, a name
never does** -- `api-exchange-gateway/` is a product name with 15,677 files of
ordinary documentation, and the predecessor's substring test swept it up along
with 186,856 others including the WebWorks `ctx/` CSH source.
"""

from pathlib import Path

import pytest

from docushift.apiref import find_api_roots, is_api_reference, looks_like_api_name
from docushift.catalog import CatalogManager
from docushift.config import ConfigManager
from docushift.engines import CshFormat, CshStatus, find_output_roots
from docushift.extractor import ExtractOutcome, PackageExtractor, inventory_tree
from docushift.models import Product, ProductVersion, SourceEngine

# The fixtures are `tests/conftest.py`'s; only the tree-building helpers come
# from the other half of Stage 4, so that both halves build a package the same
# way.
from tests.unit.test_extractor import FLARE_PACKAGE, build_tree, page, place_package


def walk(tmp_path: Path, members: dict[str, str], engine=SourceEngine.FLARE, name: str = "tree"):
    """Builds a tree and measures it the way `PackageExtractor.measure` does."""
    tree = build_tree(tmp_path / name, members)
    return tree, inventory_tree(tree, engine, find_output_roots(tree, engine))


# -- the API-reference predicate (design.md §6.3, §6.3.1) ---------------------


def test_a_javadoc_tree_is_classified_by_its_marker_not_its_name(tmp_path: Path) -> None:
    """`hawk/6.2.2/console-api/` is Javadoc, and nothing about the name says so."""
    tree = build_tree(tmp_path / "hawk", {
        "html/console-api/allclasses-frame.html": page(),
        "html/console-api/com/tibco/Agent.html": page(),
        "html/topic.htm": page(),
    })

    roots = find_api_roots(tree)

    assert roots == [tree / "html" / "console-api"]
    assert is_api_reference(tree / "html" / "console-api" / "com" / "tibco" / "Agent.html", roots)
    assert not is_api_reference(tree / "html" / "topic.htm", roots)


def test_a_product_named_api_is_not_an_api_reference(tmp_path: Path) -> None:
    """`api-exchange-gateway/` is 15,677 files of ordinary documentation."""
    tree = build_tree(tmp_path / "aeg", {
        "api-exchange-gateway/html/install.htm": page(),
        "api-exchange-gateway/html/Skins/x.css": "",
    })

    assert find_api_roots(tree) == []
    assert not looks_like_api_name("api-exchange-gateway")


def test_a_directory_named_with_a_space_is_classified_by_its_marker(tmp_path: Path) -> None:
    tree = build_tree(tmp_path / "loyalty", {
        "api reference/annotated.html": page(),
        "api reference/tibrv_8h.html": page(),
    })

    assert find_api_roots(tree) == [tree / "api reference"]
    assert looks_like_api_name("api reference")


def test_a_nested_generator_tree_is_counted_once_through_its_outermost_root(tmp_path: Path) -> None:
    """§6.3.1 Finding 4: `api-reference/javascript/` is JSDoc inside its own parent."""
    tree = build_tree(tmp_path / "eftl", {
        "html/api-reference/styles/jsdoc-default.css": "",
        "html/api-reference/javascript/styles/jsdoc-default.css": "",
        "html/api-reference/javascript/eFTL.html": page(),
    })

    assert find_api_roots(tree) == [tree / "html" / "api-reference"]


@pytest.mark.parametrize("segment", ["API", "api", "JavaDoc", "javadoc", "Java_API", "C", "c"])
def test_api_ish_names_are_compared_case_insensitively(segment: str) -> None:
    """Finding 3. Paths fold case; §9.1's identifiers never do."""
    assert looks_like_api_name(segment)


@pytest.mark.parametrize("segment", ["api-exchange-gateway", "common", "css", "ctx", "contents"])
def test_the_name_test_is_whole_segment_and_never_a_substring(segment: str) -> None:
    """Finding 2: the predecessor's `/c` matched 186,856 files, `ctx/` among them."""
    assert not looks_like_api_name(segment)


# -- the one walk (design.md §6.3, §6.4) -------------------------------------


def test_the_walk_partitions_api_files_from_everything_else(tmp_path: Path) -> None:
    tree, inventory = walk(tmp_path, {
        "guide/Data/HelpSystem.xml": "<x/>",
        "guide/a.htm": page(),
        "guide/apidocs/index-all.html": page(),
        "guide/apidocs/com/Thing.html": page(),
    })

    assert inventory.api_files == 2
    assert inventory.doc_files == 2  # directories are not counted
    assert inventory.total_files == 4
    assert inventory.api_roots == [tree / "guide" / "apidocs"]


def test_an_api_tree_inside_an_output_root_is_counted_once_as_api(tmp_path: Path) -> None:
    """API wins the destination race: counted in both, the totals would double."""
    _tree, inventory = walk(tmp_path, {
        "guide/Data/HelpSystem.xml": "<x/>",
        "guide/apidocs/index-all.html": page(),
    })

    rows = inventory.rows()

    assert {destination for _r, _c, destination, _f, _b in rows} == {"api-reference", "output-root"}
    assert sum(files for _r, _c, d, files, _b in rows if d == "api-reference") == 1


def test_a_gif_in_the_skin_directory_is_chrome_and_one_beside_a_topic_is_an_image(
    tmp_path: Path,
) -> None:
    """Skin is a *location*: 76.2% of WebWorks reference traffic is chrome."""
    _tree, inventory = walk(tmp_path, {
        "guide/Data/HelpSystem.xml": "<x/>",
        "guide/Skins/Default/callout.gif": "x",
        "guide/images/diagram.gif": "y",
    })

    by_category = {category: files for _r, category, _d, files, _b in inventory.rows()}

    # The callout, and `HelpSystem.xml` -- `Data/` is a Flare skin prefix too.
    assert by_category["skin"] == 2
    assert by_category["image"] == 1


def test_the_skin_prefix_is_a_whole_segment(tmp_path: Path) -> None:
    """`Skinsuite/` is not `Skins/` -- the rule Finding 2 imposes on API paths."""
    _tree, inventory = walk(tmp_path, {
        "guide/Data/HelpSystem.xml": "<x/>",
        "guide/Skinsuite/callout.gif": "x",
    })

    assert {c: f for _r, c, _d, f, _b in inventory.rows()}["image"] == 1


def test_the_document_router_claims_a_top_level_pdf_folder(tmp_path: Path) -> None:
    """9,133 of the corpus's 10,800 PDFs are here; only 10 sit in an output root."""
    _tree, inventory = walk(tmp_path, {
        "guide/Data/HelpSystem.xml": "<x/>",
        "pdf/user-guide.pdf": "%PDF",
        "doc/readme.txt": "hi",
    })

    router = {
        (category, files)
        for _r, category, destination, files, _b in inventory.rows()
        if destination == "document-router"
    }

    assert router == {("document", 2)}
    assert inventory.unclaimed == {}


def test_the_unclaimed_residue_is_grouped_by_top_segment(tmp_path: Path) -> None:
    """§5.5.2's 62,525 fall-through files. Silence here is how a tree goes missing."""
    _tree, inventory = walk(tmp_path, {
        "guide/Data/HelpSystem.xml": "<x/>",
        "components-api/a.html": page(),
        "components-api/deep/b.html": page(),
        "loose.txt": "x",
    })

    assert inventory.unclaimed["components-api"].files == 2
    # A file at the tree root has no segment above it, and says so rather than
    # borrowing its own name as a group.
    assert inventory.unclaimed["."].files == 1


def test_an_unmarked_api_candidate_is_reported_and_its_files_stay_documentation(
    tmp_path: Path,
) -> None:
    """The flag is how the marker list grows from evidence -- never a classification."""
    _tree, inventory = walk(tmp_path, {
        "guide/Data/HelpSystem.xml": "<x/>",
        "html/api-docs/index.html": page(),
        "html/api-docs/c/x.html": page(),
        "html/api-docs/dotnet/y.html": page(),
    })

    assert inventory.api_files == 0
    assert inventory.doc_files == 4
    # Every API-ish name is a line, nested ones included -- `api-docs/` and the
    # `c/` inside it are two candidates a human may answer differently. `dotnet/`
    # is not one: the name test is a fixed vocabulary, not a guess.
    assert inventory.triage == [("html/api-docs", 3), ("html/api-docs/c", 1)]


def test_a_marked_tree_produces_no_triage_line(tmp_path: Path) -> None:
    _tree, inventory = walk(tmp_path, {"html/apidocs/index-all.html": page()})

    assert inventory.triage == []
    assert inventory.api_files == 1


def test_the_inventory_sums_to_the_file_count(tmp_path: Path) -> None:
    """The invariant the `topic` category exists to make checkable."""
    _tree, inventory = walk(tmp_path, {
        "guide/Data/HelpSystem.xml": "<x/>",
        "guide/a.htm": page(),
        "guide/Skins/x.css": "",
        "pdf/g.pdf": "%PDF",
        "stray/x.bin": "z",
        "html/apidocs/index-all.html": page(),
    })

    assert sum(files for _r, _c, _d, files, _b in inventory.rows()) == inventory.total_files == 6


# -- CSH source inventory (design.md §6.2, §9.2) -----------------------------

ALIAS = (
    "<CatapultAliasFile>"
    '<Map Name="GatewayInstances" Link="Gateway_Instances.htm" ResolvedId="1000"/>'
    '<Map Name="gatewayInstances" Link="Managing_Gateway_Instances.htm" ResolvedId="1000"/>'
    '<Map Name="1122" Link="config/Getting_Started.htm#adb.palette"/>'
    "</CatapultAliasFile>"
)


def test_a_flare_alias_file_is_located_parsed_and_attributed_to_its_root(tmp_path: Path) -> None:
    _tree, inventory = walk(tmp_path, {
        "guide/Data/HelpSystem.xml": "<x/>",
        "guide/Data/Alias.xml": ALIAS,
        "guide/Gateway_Instances.htm": page(),
    })

    (source,) = inventory.csh_sources

    assert source.fmt is CshFormat.FLARE_ALIAS
    assert source.status is CshStatus.OK
    assert source.doc_set == "guide"
    assert source.count == 3
    # Byte-exact: `GatewayInstances` and `gatewayInstances` are two live targets
    # in TIBCO BC 7.4/7.5, and with `ResolvedId` gone case is all that separates
    # them.
    assert inventory.csh_names == {"GatewayInstances", "gatewayInstances", "1122"}
    # 3% of Flare links carry a fragment, and it is part of the target.
    assert [e.anchor for e in source.entries if e.identifier == "1122"] == ["adb.palette"]


def test_resolved_id_is_parsed_and_discarded(tmp_path: Path) -> None:
    """It is not unique even inside one file: 29 of 196 reuse an id for another topic."""
    _tree, inventory = walk(tmp_path, {"guide/Data/Alias.xml": ALIAS})

    assert len(inventory.csh_names) == 3
    assert not any(hasattr(entry, "resolved_id") for entry in inventory.csh_sources[0].entries)


@pytest.mark.parametrize(
    ("text", "status", "name"),
    [
        ("<CatapultAliasFile />", CshStatus.EMPTY, "declared-empty"),
        ("", CshStatus.EMPTY, "zero-byte"),
        ("   ", CshStatus.EMPTY, "whitespace"),
        ("<CatapultAliasFile><Map Name=", CshStatus.UNPARSEABLE, "truncated"),
    ],
)
def test_empty_and_broken_alias_files_are_counted_and_never_raised(
    tmp_path: Path, text: str, status: CshStatus, name: str
) -> None:
    """476 of 863 Flare alias files are empty. Absent CSH is the *normal* case."""
    _tree, inventory = walk(tmp_path, {"guide/Data/Alias.xml": text}, name=name)

    (source,) = inventory.csh_sources

    assert source.status is status
    assert inventory.csh_names == set()
    # A located source counts whatever it parsed to: `_has_csh` records that a
    # file was *found*, which is why `true` with `_csh_names=0` is a real state.
    assert inventory.readable_csh_sources == 1


def test_a_dita_head_js_context_map_is_read(tmp_path: Path) -> None:
    head = 'var suitehelp={};suitehelp.contexts={"bwmarketo_palette":"GUID-3F0A.html","c2":"GUID-9.html"};'
    _tree, inventory = walk(tmp_path, {"ds/static/head.js": head}, engine=SourceEngine.DITA)

    (source,) = inventory.csh_sources

    assert source.fmt is CshFormat.DITA_HEAD_JS
    assert source.status is CshStatus.OK
    assert inventory.csh_names == {"bwmarketo_palette", "c2"}


def test_an_empty_dita_context_map_is_the_counterpart_of_an_empty_alias_file(
    tmp_path: Path,
) -> None:
    """38 of 418 `head.js` files assign `{}`, and they are counted identically."""
    _tree, inventory = walk(
        tmp_path, {"ds/static/head.js": "suitehelp.contexts={};"}, engine=SourceEngine.DITA
    )

    assert inventory.csh_sources[0].status is CshStatus.EMPTY
    assert inventory.readable_csh_sources == 1


TOPICS_JS = (
    "function  WWHBookData_MatchTopic(P)\n{\nvar C=null;\n"
    'if(P=="as400.palette.gettingstartedurl")C="adas400_gettingstarted.6.1.htm#1674528";\n'
    'if(P=="as400.instance.helpurl")C="adas400_instance.7.1.htm";\nreturn C;\n}\n'
)


def test_a_webworks_topics_js_dispatch_chain_is_read(tmp_path: Path) -> None:
    _tree, inventory = walk(
        tmp_path,
        {"book/wwhdata/common/topics.js": TOPICS_JS, "book/wwhdata/files.htm": page()},
        engine=SourceEngine.WEBWORKS,
    )

    (source,) = inventory.csh_sources

    assert source.fmt is CshFormat.WEBWORKS_TOPICS
    assert source.doc_set == "book"
    assert inventory.csh_names == {"as400.palette.gettingstartedurl", "as400.instance.helpurl"}
    # 43% of WebWorks targets carry a Frame-generated numeric anchor.
    assert sorted(entry.anchor for entry in source.entries) == ["", "1674528"]


def test_a_topics_js_that_returns_null_is_empty_not_broken(tmp_path: Path) -> None:
    """492 of 647 (76%) generate no cases at all."""
    empty = "function  WWHBookData_MatchTopic(P)\n{\nvar C=null;\nreturn C;\n}\n"
    _tree, inventory = walk(
        tmp_path, {"book/wwhdata/common/topics.js": empty}, engine=SourceEngine.WEBWORKS
    )

    assert inventory.csh_sources[0].status is CshStatus.EMPTY


def test_the_two_nearby_files_are_not_csh_sources(tmp_path: Path) -> None:
    """`ctx/` is generated *from* the map; `files.xml` is its lossy XML twin."""
    _tree, inventory = walk(
        tmp_path,
        {
            "book/wwhdata/xml/files.xml": '<x name="id" href="a.htm"/>',
            "ds/ctx/book1.htm": '<script>document.location="../index.htm?context=x"</script>',
        },
        engine=SourceEngine.WEBWORKS,
    )

    assert inventory.csh_sources == []


def test_a_head_js_outside_static_is_not_a_csh_source(tmp_path: Path) -> None:
    """Located by shape -- the file *and* its parent -- so a script folder is not swept in."""
    _tree, inventory = walk(tmp_path, {"guide/js/head.js": 'suitehelp.contexts={"a":"b"};'})

    assert inventory.csh_sources == []


def test_identifiers_are_deduplicated_version_wide(tmp_path: Path) -> None:
    """§9.3 merges version-wide, so the count has to as well."""
    alias = '<CatapultAliasFile><Map Name="shared" Link="a.htm"/></CatapultAliasFile>'
    _tree, inventory = walk(tmp_path, {
        "main/Data/HelpSystem.xml": "<x/>",
        "main/Data/Alias.xml": alias,
        "relnotes/Data/HelpSystem.xml": "<x/>",
        "relnotes/Data/Alias.xml": alias,
    })

    assert len(inventory.csh_sources) == 2
    assert inventory.csh_names == {"shared"}


# -- the five columns and `state.db` (architecture.md §3.9) -------------------


def test_a_clean_extract_writes_the_five_inventory_columns(
    config: ConfigManager, catalog: CatalogManager, product: Product, version: ProductVersion
) -> None:
    place_package(config, product, version, {
        **FLARE_PACKAGE,
        "guide/Data/Alias.xml": ALIAS,
        "guide/apidocs/index-all.html": "<html/>",
    })

    result = PackageExtractor(config, catalog).extract_one(product, version)

    row = catalog.get_version("tibco-ems", "10.4.0")
    assert result.inventory is not None
    assert (row.has_api_ref, row.api_files, row.doc_files) == (True, 1, 4)
    assert (row.has_csh, row.csh_names) == (True, 3)


def test_a_package_with_no_help_map_writes_zero_rather_than_blank(
    config: ConfigManager, catalog: CatalogManager, product: Product, version: ProductVersion
) -> None:
    """`0` means Stage 4 looked and found none; blank means nobody has looked."""
    place_package(config, product, version, FLARE_PACKAGE)

    PackageExtractor(config, catalog).extract_one(product, version)

    row = catalog.get_version("tibco-ems", "10.4.0")
    assert (row.has_csh, row.csh_names) == (False, 0)
    assert (row.has_api_ref, row.api_files) == (False, 0)


def test_a_failed_extract_leaves_all_five_blank(
    config: ConfigManager, catalog: CatalogManager, product: Product, version: ProductVersion
) -> None:
    """A failed run must not look like an empty package."""
    target = config.download_path(product.bu, product.family, product.slug, version.version)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"not a zip")

    result = PackageExtractor(config, catalog).extract_one(product, version)

    row = catalog.get_version("tibco-ems", "10.4.0")
    assert result.outcome is ExtractOutcome.FAILED
    assert (row.has_csh, row.csh_names, row.has_api_ref, row.api_files, row.doc_files) == (
        None, None, None, None, None,
    )


def test_the_inventory_reaches_state_db(
    config: ConfigManager, catalog: CatalogManager, product: Product, version: ProductVersion
) -> None:
    place_package(config, product, version, {**FLARE_PACKAGE, "guide/Data/Alias.xml": ALIAS})

    PackageExtractor(config, catalog).extract_one(product, version)

    sources = catalog.state.get_csh_sources("tibco-ems", "10.4.0")
    assets = catalog.state.get_asset_inventory("tibco-ems", "10.4.0")
    assert [(s["format"], s["entries"], s["status"]) for s in sources] == [("flare_alias", 3, "ok")]
    assert sources[0]["path"] == "guide/Data/Alias.xml"
    assert sum(row["files"] for row in assets) == 4


def test_a_re_walk_replaces_the_inventory_rather_than_adding_to_it(
    config: ConfigManager, catalog: CatalogManager, product: Product, version: ProductVersion
) -> None:
    """A package that dropped a help output must not leave the old source behind."""
    place_package(config, product, version, {**FLARE_PACKAGE, "guide/Data/Alias.xml": ALIAS})
    extractor = PackageExtractor(config, catalog)
    extractor.extract_one(product, version)
    place_package(config, product, version, FLARE_PACKAGE)

    extractor.extract_one(product, version)

    assert catalog.state.get_csh_sources("tibco-ems", "10.4.0") == []
    assert catalog.get_version("tibco-ems", "10.4.0").csh_names == 0


def test_a_current_tree_with_blank_columns_is_walked_anyway(
    config: ConfigManager, catalog: CatalogManager, product: Product, version: ProductVersion
) -> None:
    """A tree extracted before the walk existed must not stay unmeasured for good."""
    place_package(config, product, version, FLARE_PACKAGE)
    extractor = PackageExtractor(config, catalog)
    extractor.extract_one(product, version)
    catalog.clear_extract_inventory("tibco-ems", "10.4.0")

    result = extractor.extract_one(product, version)

    assert result.outcome is ExtractOutcome.CURRENT
    assert result.inventory is not None
    assert catalog.get_version("tibco-ems", "10.4.0").doc_files == 3


def test_a_measured_current_tree_is_not_walked_again(
    config: ConfigManager, catalog: CatalogManager, product: Product, version: ProductVersion
) -> None:
    place_package(config, product, version, FLARE_PACKAGE)
    extractor = PackageExtractor(config, catalog)
    extractor.extract_one(product, version)

    result = extractor.extract_one(product, version)

    assert result.outcome is ExtractOutcome.CURRENT
    assert result.inventory is None
