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
- [ ] **Migrate catalog storage from JSON to CSV** (decided 2026-09-03, see `architecture.md` §3):
  - Split into `config/products.csv` + `config/versions.csv`, normalized on `product_code`; retire `config/catalog.json`.
  - Reshape `taxonomy.yaml` to family definitions + keyword rules; move the hardcoded heuristics out of `config.py:resolve_product_info()` into YAML data.
  - Add `family_source` provenance (`manual` > `taxonomy_rule` > `docsite_category` > `unclassified`).
  - **Move `engine` from product-level to version-level.** Concretely: delete `Product.engine` (`models.py:51`, currently defaulting to `SourceEngine.FLARE`) and add `engine` + `engine_source` to `ProductVersion`, which has no engine field today. Default becomes `AUTO`, not `FLARE`.
  - Remove the now-dead product-level engine plumbing: `catalog.py:78` (`product.engine = existing.engine`) and the three return sites in `config.py:resolve_product_info()` (lines 64, 74, 82).
  - Strip engine from `taxonomy.yaml`: the two BU-level `default_engine: "flare"` keys (lines 9, 88) and all 21 per-product `engine:` keys — including the three non-default `docbook` assertions for `rendezvous` (line 42), `streambase` (line 55), and `iprocess` (line 81), which are exactly the products most likely to have switched toolchains across versions.
  - CSV round-trip hygiene: `utf-8-sig`, permissive boolean/date parsing, ISO/lowercase normalized writes, fixed column order, natural-version stable sort.
- [ ] Additive Catalog Engine (`src/docushift/catalog.py`):
  - Load/save the CSV pair.
  - Active (`convert_eligible: true`) vs Archived (`convert_eligible: false`) version model.
  - **Snapshot-based 3-way merge** (base = last fetch from `state.db`, theirs = new fetch, mine = current CSV). Replaces the current flag-based protection.
  - Deletion safety: orphaned version keys abort the import unless `--allow-deletes`.
  - CLI operations (`catalog fetch`, `catalog list`, `catalog enable`, `catalog set`, `catalog triage`).
- [ ] SQLite State Store (`src/docushift/state.py`):
  - Last-fetch snapshot table backing the 3-way merge.
  - Volatile fields evicted from the catalog: `zip_etag`, `zip_size`, checksums, free-form metadata.
  - Tracks lifecycle stages `(bu, family, product, version)`.
  - Delta querying and batch slice helpers.
- [ ] Unit tests for Catalog merger and State engine (`tests/unit/test_catalog.py`, `tests/unit/test_state.py`), including CSV round-trip fidelity and Excel-mangling regression cases.

### Phase 3: Docsite Discovery Engine (`docs.tibco.com` API Client)
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
