"""Stage 6d's archived-version index (`design.md` §10.6, `architecture.md` §6.2.3).

The whole file rests on one measured fact: **0 of the corpus's 1,270 reachable
archived rows have a ZIP on disk.** Every rule the module follows -- build from
the catalog, list a row with no URL anyway, compare the rendered index rather than
the file set -- is downstream of that, so the tests assert the empty-handed case
first and the downloaded one as the exception it is.
"""

from pathlib import Path

import pytest
import yaml

from docushift.models import Product, ProductVersion
from docushift.sync import archives


@pytest.fixture
def product() -> Product:
    """Six archived rows and one live one, in deliberately unhelpful insertion order."""
    def version(number: str, **kwargs) -> ProductVersion:
        return ProductVersion(slug="tibco-ems", version=number, **kwargs)

    return Product(
        slug="tibco-ems",
        product_code="ems",
        display_name="TIBCO Enterprise Message Service™",
        bu="tibco",
        family="messaging",
        versions={
            "8.5.0": version("8.5.0", is_archived=True, release_date="2019-11-14",
                             zip_url="https://docs.example/ems-8.5.0.zip"),
            "10.1.0": version("10.1.0", is_archived=True, release_date="2024-02-11",
                              zip_url="https://docs.example/ems-10.1.0.zip"),
            "8.10.0": version("8.10.0", is_archived=True, release_date="1638316800000",
                              zip_url="https://docs.example/ems-8.10.0.zip"),
            # No `zip_url` and no date: 14 of the corpus's 2,100 rows, 6 undated.
            "7.0.1": version("7.0.1", is_archived=True),
            "ga": version("ga", is_archived=True, zip_url="https://docs.example/ems-ga.zip"),
            "10.4.0": version("10.4.0", release_date="2026-02-06"),
        },
    )


# -- what goes in the list, and in what order -----------------------------------


def test_only_archived_rows_are_listed_newest_version_first(product: Product) -> None:
    """Version descending, not date. The two disagree for 38% of multi-archived products."""
    entries = archives.entries_for(product)

    assert [entry.version for entry in entries] == ["10.1.0", "8.10.0", "8.5.0", "7.0.1", "ga"]


def test_a_non_numeric_version_sorts_last_rather_than_heading_the_history(product: Product) -> None:
    """`version.yml`'s rule: these are upstream parse artifacts, not versions."""
    assert archives.entries_for(product)[-1].version == "ga"


def test_the_released_column_is_the_month_both_date_shapes_render_to(product: Product) -> None:
    """1,785 rows are `YYYY-MM-DD` and 309 are epoch milliseconds; 6 are empty.

    `release_month` already parses both, and the month is what `version.yml`'s
    drop-down publishes -- so the two places a date reaches published output agree.
    The day-level precision the catalog actually holds is recorded in §6.2.3 rather
    than rendered, which is a decision and not an oversight.
    """
    released = {entry.version: entry.released for entry in archives.entries_for(product)}

    assert released["10.1.0"] == "Feb 2024"
    assert released["8.10.0"] == "Dec 2021"
    assert released["7.0.1"] == ""


def test_a_product_with_no_archived_rows_gets_no_entries_and_so_no_folder() -> None:
    """43% of in-scope products. An empty index claims a product has no history."""
    live = Product(slug="x", product_code="x", display_name="X", bu="tibco", family="messaging",
                   versions={"1.0": ProductVersion(slug="x", version="1.0")})

    assert archives.entries_for(live) == []


# -- where a reader is sent ------------------------------------------------------


def test_the_url_is_the_catalogs_zip_url_untouched(product: Product) -> None:
    """2,086 of 2,100 are already absolute; there is no base URL to compose."""
    entries = {entry.version: entry for entry in archives.entries_for(product)}

    assert entries["10.1.0"].url == "https://docs.example/ems-10.1.0.zip"
    assert entries["10.1.0"].link == "https://docs.example/ems-10.1.0.zip"
    assert not entries["10.1.0"].available


def test_a_row_with_no_url_is_still_a_row(product: Product) -> None:
    """Invariant 10 applied to a whole version: an absence is reported, never faked."""
    entries = {entry.version: entry for entry in archives.entries_for(product)}

    assert entries["7.0.1"].url == ""
    assert not entries["7.0.1"].available

    rendered = archives.render_index(
        archives.entries_for(product), "T", _templates()
    )
    assert "- 7.0.1 (not available)" in rendered


def test_a_downloaded_zip_is_preferred_over_the_docsite(product: Product, tmp_path: Path) -> None:
    """A reader should not be sent back upstream for a file the publisher is hosting."""
    local = tmp_path / "tibco-ems-8.5.0.zip"
    local.write_bytes(b"PK" * 40)

    entries = {entry.version: entry for entry in archives.entries_for(product, tmp_path)}

    assert entries["8.5.0"].available
    assert entries["8.5.0"].url == "tibco-ems-8.5.0.zip"
    assert entries["8.5.0"].bytes == 80
    assert entries["8.5.0"].source == local
    # Every other row is untouched by one file arriving.
    assert entries["10.1.0"].url == "https://docs.example/ems-10.1.0.zip"


# -- the two rendered files ------------------------------------------------------


def _templates() -> Path:
    return Path(__file__).resolve().parents[2] / "config" / "aem_templates"


def test_the_index_writes_its_own_frontmatter_because_nothing_converts_this_folder(
    product: Product,
) -> None:
    rendered = archives.render_index(archives.entries_for(product), "EMS Archived Versions",
                                     _templates())

    assert rendered.startswith("---\n")
    assert "doc_class: archives" in rendered
    assert "# EMS Archived Versions" in rendered
    assert "- [10.1.0](https://docs.example/ems-10.1.0.zip) -- Feb 2024" in rendered


def test_the_toc_is_flat_and_says_what_can_actually_be_fetched(product: Product) -> None:
    parsed = yaml.safe_load(
        archives.render_toc(archives.entries_for(product), "T", _templates())
    )

    assert [item["version"] for item in parsed["items"]] == [
        "10.1.0", "8.10.0", "8.5.0", "7.0.1", "ga",
    ]
    assert all(item["available"] is False for item in parsed["items"])
    # No `path` key at all for the row with no URL, rather than an empty one.
    assert "path" not in parsed["items"][3]


def test_the_title_carries_no_version_because_the_folder_is_all_of_them() -> None:
    assert archives.index_title("TIBCO EMS") == "TIBCO EMS Archived Versions"


# -- currency, which cannot be a file comparison ---------------------------------


def test_currency_compares_the_rendered_index_not_just_the_files(
    product: Product, tmp_path: Path
) -> None:
    """The file set is identical for every state of a history nobody has downloaded.

    Retiring a version adds a row and changes nothing on disk, so a file-set check
    would report this folder current forever. The file is a few hundred bytes.
    """
    entries = archives.entries_for(product)
    index = archives.render_index(entries, "T", _templates())

    destination = tmp_path / "archives"
    destination.mkdir()
    for name in ("index.md", "toc.yml", "metadata.yml"):
        (destination / name).write_text(index if name == "index.md" else "x\n", encoding="utf-8")

    assert archives.current(entries, destination, index)

    product.versions["9.0.0"] = ProductVersion(
        slug="tibco-ems", version="9.0.0", is_archived=True,
        zip_url="https://docs.example/ems-9.0.0.zip",
    )
    grown = archives.entries_for(product)
    assert not archives.current(grown, destination, archives.render_index(grown, "T", _templates()))


def test_a_folder_that_is_not_there_is_not_current(product: Product, tmp_path: Path) -> None:
    entries = archives.entries_for(product)

    assert not archives.current(entries, tmp_path / "nothing", "")
