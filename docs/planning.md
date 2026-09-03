# DocuShift Master Planning & Roadmap

> **Document Status:** Active Roadmap  
> **Last Updated:** 2026-09-03  
> **Target:** Multi-Stage Documentation Migration Pipeline (TIBCO & IBI -> AEM)

---

## 1. Modular Phase Breakdown

### Phase 1: Architecture, Living Docs & Project Scaffolding
**Status: COMPLETE.** Implemented and verified 2026-09-03 — 54 tests pass, `ruff check src tests` is clean.
- [x] Living documentation system (`CONTEXT.md`, `architecture.md`, `user-guide.md`, `planning.md`).
- [x] Multi-engine 7-stage pipeline design with additive catalog and active/archived version handling.
- [x] Verified `docs.tibco.com` API endpoints (`/api/a_to_z`, `/api/products/{slug}`, `/api/products/archive/{slug}`).
- [x] Create initial `config/taxonomy.yaml`.
- [x] `pyproject.toml` authored; `jinja2` added as a dependency for the AEM templates; `[tool.ruff]` added with an explicitly pinned rule set (`E,F,I,UP,B,SIM`, line length 120) so linting does not drift with the ruff version.
- [x] **Working environment** — `.venv` created, `pip install -e ".[dev]"` succeeded on Python 3.13.7. The console script `docushift` installs and runs.
- [x] **Directory layout** — all 9 subpackages created (`discovery/`, `downloader/`, `extractor/`, `engines/`, `transforms/`, `aem/`, `sync/`, `reporting/`, `utils/`), each a real package with a docstring naming its stage and phase. `config/aem_templates/` populated with Jinja templates for `toc.yml`, `nav.yml`, `meta.yml`, and `index.md`.
- [x] **`cli.py`** — Click command tree matching the surface in `user-guide.md`: `catalog {fetch,list,show,enable,set,import,triage}`, `download`, `extract`, `convert`, `sync`, `validate`, `status`, `report`, `doctor`. `doctor` is functional; every stage command raises a `ClickException` naming its implementing phase, so an unbuilt stage exits non-zero instead of silently succeeding.
- [x] **`pytest` framework** — `tests/{conftest.py,unit/,integration/,fixtures/}`, **54 passing tests**. Real coverage of `ConfigManager`, the additive catalog merge, the CLI surface, and Phase 1 layout guards (subpackage imports, console-script entrypoint, shipped config contents, `.gitignore`).
- [x] **`.gitignore`** — now covers `output/`, `*.db`, `.venv/`, `__pycache__/`, build and test caches.
- [x] `config/docsite.yaml` — endpoints, ZIP URL templates, crawl politeness settings, and the active/archived conversion defaults. Loaded via `ConfigManager.load_docsite()`.

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
  - [x] CLI operations: `catalog list`, `show`, `enable`, `set`, `import`, `triage` are wired up. `catalog fetch` remains pending on the Phase 3 crawler — only its input is missing.
- [x] SQLite State Store (`src/docushift/state.py`):
  - [x] `product_snapshot` / `version_snapshot` tables backing the 3-way merge. Deliberately carry no engine columns: the detector owns those, not discovery, so a fetch cannot reset a detected engine.
  - [x] Volatile fields evicted from the catalog: `zip_etag`, `zip_size`, checksums, paths, per-stage status, free-form product/version metadata.
  - [x] Lifecycle status per `(product, version)`, with `versions_with_status()` and `status_counts()` for the Phase 7 dashboard.
  - [x] `engine_folder_map` so a bundle that genuinely mixes generators stays visible rather than flattened into the one CSV column.
  - [x] Batch slice helper for phased runs across ~250 products.
- [x] Unit tests for Catalog merger and State engine (`tests/unit/test_catalog.py`, `tests/unit/test_state.py`, `tests/unit/test_csvio.py`), including CSV round-trip fidelity and Excel-mangling regression cases (`TRUE`/`FALSE` booleans, `11/4/2025` dates, `1.10` → `1.1` version keys, BOM loss, stray columns).

### Phase 3: Docsite Discovery Engine (`docs.tibco.com` API Client)
**Next up.** The merge target is already built and tested; this phase supplies its input and unblocks `catalog fetch`.
- [ ] API client for `docs.tibco.com` (`/api/a_to_z`, `/api/products/{slug}`, `/api/products/archive/{slug}`, `/api/product_list_by_suites`).
- [ ] Automated ZIP URL generator (`/pub/{folder_path}/doc/zip/tib_{...}_doc.zip` and archive `zipPath`).
- [ ] Category ingestion (`/api/bu_category_products`, `/product/categories`) as an **advisory** family hint only — most products are uncategorized, so it may only promote `unclassified` rows.
- [ ] Additive merge into Catalog Manager and State DB.
- [ ] Unit & mock tests in `tests/unit/test_discovery.py`.

### Phase 4: Package Downloader & Extractor
- [ ] Resumable async/threaded downloader with checksum verification into `cache/downloads/`.
- [ ] Filter by `convert_eligible: true`.
- [ ] ZIP extraction and asset cataloger in `cache/extracted/`.
- [ ] CSH map file extractor (`Alias.xml`, `CSH.js`, WebWorks maps).
- [ ] Asset discovery (PDF, Word, Excel, TXT, images, ZIP).

### Phase 5: Multi-Engine HTML -> GFM Conversion & Transforms
- [ ] **Engine Detector** (`engines/detector.py`) — resolve the generator per version from extracted content and write it back to `versions.csv`:
  - Marker-file pass first (cheapest, least ambiguous): Flare `*.mcwebhelp`/`*.mclog`/`Skins/`/`Data/`/`MicroContent/`; WebWorks `wwhelp/`/`wwhdata/`; DITA `*.dita` remnants.
  - Content-signature pass as corroboration and as the sole means of identifying DocBook (`DocBook XSL Stylesheets` generator comment), which has no distinctive layout.
  - Never guess: leave `auto` and skip conversion with a warning if no signature matches.
  - Record the per-guide-folder map in `state.db` to surface any genuinely mixed bundle.
- [ ] MadCap Flare Engine (dropdown unrolling, proxy stripping, table text, breadcrumbs).
- [ ] DITA, WebWorks, DocBook engine handlers.
- [ ] Callouts to GFM alerts (`> [!NOTE]`, `> [!WARNING]`, etc.).
- [ ] HTML Table to clean GFM Pipe Table normalizer.
- [ ] Cross-document link and anchor re-writer (`.html` -> `.md`).
- [ ] CSH alias to Markdown anchor mapper.
- [ ] Asset copier and relative link re-pointer.
- [ ] Exhaustive unit tests with fixtures in `tests/unit/`.

### Phase 6: AEM Architecture Synthesis & Git Sync
- [ ] AEM navigation builder (`toc.yml`, `nav.yml`, `meta.yml`).
- [ ] Frontmatter injector and landing page (`index.md`) generator.
- [ ] Git workspace distributor (copies to `{target_git}/{bu}/{family}/{product}/{version}/`).

### Phase 7: CLI, Reporting & Verification Dashboard
- [ ] Click CLI with full command tree (`catalog`, `status`, `download`, `convert`, `sync`, `report`).
- [ ] Rich terminal dashboard and exportable Markdown/HTML migration reports.
- [ ] Broken link and missing asset linter.
- [ ] End-to-end integration test suite.

---

## 2. Validation & Testing Criteria
- **Catalog Merge Fidelity**: 100% preservation of manual edits and toggle states when fetching updates — *without* requiring the user to have flagged them.
- **CSV Round-Trip Fidelity**: A load-then-save cycle with no changes produces a byte-identical file (stable sort, fixed columns, normalized booleans/dates). No diff churn on repeat fetches.
- **Active vs Archive Segregation**: Archived versions are never auto-converted unless explicitly flagged.
- **Unit Test Coverage**: >90% coverage on core transforms, engines, catalog, and state management.
- **Link & Asset Integrity**: Zero broken relative links or missing referenced assets in converted output.
