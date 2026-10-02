> Archived from `docs/planning.md` on 2026-10-02. Status: **Complete, 2026-09-03**. Kept verbatim; a heading that says *Planned* was built later in this same section.
> Index of every phase: [`docs/planning.md`](../../planning.md#finished-phases).

### Phase 2: Catalog Migration to CSV, Catalog Manager & State Engine
**Status: COMPLETE.** Implemented and verified 2026-09-03 — 157 tests pass, `ruff check src tests` is clean.
- [x] **Migrate catalog storage from JSON to CSV** (decided 2026-09-03, see `architecture.md` §3):
  - [x] Split into `config/products.csv` + `config/versions.csv`, normalized on `product_code`; `config/catalog.json` retired (it held no data, so no migration path was needed).
  - [x] Reshape `taxonomy.yaml` to family definitions + a top-level `rules:` list; the hardcoded ibi/webfocus/omni/iway heuristics are gone from `config.py:resolve_product_info()`, which is now purely rule-driven. The 21 former per-product classifications were preserved as keyword rules rather than dropped.
  - [x] Add `family_source` provenance (`manual` > `taxonomy_rule` > `docsite_category` > `unclassified`). The merge ranks these, so a lower-confidence source can never downgrade a higher one.
  - [x] **Move `engine` from product-level to version-level.** `Product.engine` deleted; `ProductVersion.engine` + `engine_source` added, defaulting to `AUTO`.
  - [x] Product-level engine plumbing removed from `catalog.py` and `config.py`.
  - [x] Engine stripped from `taxonomy.yaml` — both BU `default_engine` keys and all per-product `engine:` keys, including the `rendezvous` / `streambase` / `iprocess` `docbook` assertions.
  - [x] CSV round-trip hygiene in `utils/csvio.py`: `utf-8-sig`, permissive boolean/date parsing, ISO/lowercase normalized writes, fixed column order, natural-version stable sort.
- [x] Additive Catalog Engine (`src/docushift/catalog.py`):
  - [x] Load/save the CSV pair, with `_bu`/`_family` denormalized into `versions.csv` for filtering and regenerated on every write.
  - [x] Active (`convert_eligible: true`) vs Archived (`convert_eligible: false`) version model.
  - [x] **Snapshot-based 3-way merge** (base = last fetch from `state.db`, theirs = new fetch, mine = current CSV), replacing flag-based protection. With no snapshot the merge falls back to the conservative reading: the CSV value is the user's.
  - [x] Deletion safety: disappearing version keys abort the merge unless `--allow-deletes`, and the check is scoped to the products actually fetched, so `--product ems` can never threaten another product's rows.
  - [x] CLI operations: `catalog list`, `show`, `enable`, `set`, `import`, `triage` are wired up; `catalog fetch` joined them in Phase 3.
- [x] SQLite State Store (`src/docushift/state.py`):
  - [x] `product_snapshot` / `version_snapshot` tables backing the 3-way merge. Deliberately carry no engine columns: the detector owns those, not discovery, so a fetch cannot reset a detected engine.
  - [x] Volatile fields evicted from the catalog: `zip_etag`, `zip_size`, checksums, paths, per-stage status, free-form product/version metadata.
  - [x] Lifecycle status per `(product, version)`, with `versions_with_status()` and `status_counts()` for the Phase 7 dashboard.
  - [x] `engine_folder_map` so a bundle that genuinely mixes generators stays visible rather than flattened into the one CSV column.
  - [x] Batch slice helper for phased runs across ~250 products.
- [x] Unit tests for Catalog merger and State engine (`tests/unit/test_catalog.py`, `tests/unit/test_state.py`, `tests/unit/test_csvio.py`), including CSV round-trip fidelity and Excel-mangling regression cases (`TRUE`/`FALSE` booleans, `11/4/2025` dates, `1.10` → `1.1` version keys, BOM loss, stray columns).
