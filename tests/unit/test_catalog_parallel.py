"""Two `docushift` runs saving the catalog at once keep each other's rows (2026-11-14).

Each run reads the whole CSV pair and used to write it all back, so the later save
put the earlier run's rows back as they were. `save` now re-reads the sheets under
`config/.catalog.lock` and lays on only the cells this run changed.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from docushift.catalog import LOCK_NAME, CatalogManager
from docushift.models import Product, SourceEngine
from docushift.utils.csvio import read_rows
from docushift.utils.filelock import LockTimeout, exclusive
from tests.conftest import make_product, make_version


def _again(catalog: CatalogManager) -> CatalogManager:
    return CatalogManager(catalog.products_path, catalog.versions_path, catalog.state)


def _seeded(catalog: CatalogManager, discovered_products: list[Product]) -> list[tuple[str, str]]:
    catalog.merge_fetch_results(discovered_products)
    return [(r["slug"], r["version"]) for r in read_rows(catalog.versions_path)]


def _cells(catalog: CatalogManager) -> dict[tuple[str, str], dict[str, str]]:
    return {(r["slug"], r["version"]): r for r in read_rows(catalog.versions_path)}


def test_two_runs_on_different_versions_both_keep_their_changes(catalog, discovered_products) -> None:
    keys = _seeded(catalog, discovered_products)
    (slug_a, ver_a), (slug_b, ver_b) = keys[0], keys[-1]
    a, b = _again(catalog), _again(catalog)
    a.load().products[slug_a].versions[ver_a].md_files = 111
    b.load().products[slug_b].versions[ver_b].out_files = 222
    b.load().products[slug_b].versions[ver_b].engine = SourceEngine.FLARE

    a.save()
    b.save()

    rows = _cells(catalog)
    assert rows[(slug_a, ver_a)]["_md_files"] == "111"
    assert (rows[(slug_b, ver_b)]["_out_files"], rows[(slug_b, ver_b)]["engine"]) == ("222", "flare")
    assert list(rows) == keys


def test_a_row_another_run_added_is_kept_and_one_this_run_added_is_written(catalog, discovered_products) -> None:
    _seeded(catalog, discovered_products)
    a, b = _again(catalog), _again(catalog)
    a.load()
    b.load().products["zz-new"] = make_product("zz-new", versions={"1.0": make_version("zz-new", "1.0")})
    a.load().products[discovered_products[0].slug].versions["0.0.1"] = make_version(
        discovered_products[0].slug, "0.0.1")

    b.save()
    a.save()
    a.save()  # a second save from the same run must not drop b's rows either

    rows = _cells(catalog)
    assert ("zz-new", "1.0") in rows and (discovered_products[0].slug, "0.0.1") in rows
    assert "zz-new" in {r["slug"] for r in read_rows(catalog.products_path)}


def test_the_same_cell_takes_the_later_save(catalog, discovered_products) -> None:
    slug, ver = _seeded(catalog, discovered_products)[3]
    a, b = _again(catalog), _again(catalog)
    a.load().products[slug].versions[ver].md_files = 1
    b.load().products[slug].versions[ver].md_files = 2

    a.save()
    b.save()

    assert _cells(catalog)[(slug, ver)]["_md_files"] == "2"


def test_merged_sheets_are_byte_for_byte_what_one_run_would_write(catalog, discovered_products) -> None:
    """BOM, CRLF, quoting, column order and sort: the two-run result is the file a
    single run making both changes writes."""
    keys = _seeded(catalog, discovered_products)
    (slug_a, ver_a), (slug_b, ver_b) = keys[5], keys[-5]
    original = (catalog.products_path.read_bytes(), catalog.versions_path.read_bytes())
    one = _again(catalog)
    one.load().products[slug_a].versions[ver_a].md_files = 7
    one.load().products[slug_b].versions[ver_b].convert_batch = "wave-2"
    one.save()
    expected = (catalog.products_path.read_bytes(), catalog.versions_path.read_bytes())
    catalog.products_path.write_bytes(original[0])
    catalog.versions_path.write_bytes(original[1])

    a, b = _again(catalog), _again(catalog)
    a.load().products[slug_a].versions[ver_a].md_files = 7
    b.load().products[slug_b].versions[ver_b].convert_batch = "wave-2"
    a.save()
    b.save()

    assert (catalog.products_path.read_bytes(), catalog.versions_path.read_bytes()) == expected
    assert expected[1].startswith(b"\xef\xbb\xbfslug,version,") and b"\r\n" in expected[1]


def test_a_save_with_no_change_rewrites_nothing(catalog, discovered_products) -> None:
    _seeded(catalog, discovered_products)
    before = (catalog.products_path.read_bytes(), catalog.versions_path.read_bytes())

    _again(catalog).save()

    assert (catalog.products_path.read_bytes(), catalog.versions_path.read_bytes()) == before


def test_many_threads_saving_at_once_keep_every_change(catalog, discovered_products) -> None:
    keys = _seeded(catalog, discovered_products)[:8]
    managers = [_again(catalog) for _ in keys]
    for n, (manager, (slug, ver)) in enumerate(zip(managers, keys, strict=True)):
        manager.load().products[slug].versions[ver].md_files = 1000 + n
    start = threading.Barrier(len(managers))
    errors: list[BaseException] = []

    def run(manager: CatalogManager) -> None:
        try:
            start.wait()
            manager.save()
        except BaseException as exc:  # noqa: BLE001 - reported below
            errors.append(exc)

    threads = [threading.Thread(target=run, args=(m,)) for m in managers]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    rows = _cells(catalog)
    assert [rows[key]["_md_files"] for key in keys] == [str(1000 + n) for n in range(len(keys))]


def test_a_save_waits_for_the_lock(catalog, discovered_products, monkeypatch) -> None:
    keys = _seeded(catalog, discovered_products)
    lock = catalog.products_path.parent / LOCK_NAME
    run = _again(catalog)
    run.load().products[keys[0][0]].versions[keys[0][1]].md_files = 5
    held, saved = threading.Event(), threading.Event()
    early: list[bool] = []

    def other() -> None:
        with exclusive(lock):
            held.set()
            early.append(saved.wait(0.3))  # the save cannot finish while the lock is held

    thread = threading.Thread(target=other)
    thread.start()
    held.wait()
    run.save()
    saved.set()
    thread.join()

    assert early == [False]
    assert _cells(catalog)[keys[0]]["_md_files"] == "5"


def test_a_lock_held_too_long_is_a_timeout(tmp_path: Path) -> None:
    lock = tmp_path / "x.lock"
    with exclusive(lock), pytest.raises(LockTimeout), exclusive(lock, timeout=0.2):
        pass
