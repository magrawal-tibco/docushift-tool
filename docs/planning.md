# DocuShift Master Planning & Roadmap

> **Document Status:** Active Roadmap  
> **Last Updated:** 2026-09-03  
> **Target:** Multi-Stage Documentation Migration Pipeline (TIBCO & IBI -> AEM)

---

## 1. Modular Phase Breakdown

### Phase 1: Architecture, Living Docs & Project Scaffolding
**Status: ~70% — design complete, scaffolding incomplete.** Audited against the filesystem 2026-09-03.
- [x] Living documentation system (`CONTEXT.md`, `architecture.md`, `user-guide.md`, `planning.md`).
- [x] Multi-engine 7-stage pipeline design with additive catalog and active/archived version handling.
- [x] Verified `docs.tibco.com` API endpoints (`/api/a_to_z`, `/api/products/{slug}`, `/api/products/archive/{slug}`).
- [x] Create initial `config/taxonomy.yaml`.
- [x] `pyproject.toml` authored.
- [ ] **Create a working environment** — venv + `pip install -e ".[dev]"`. Nothing is currently installed; `pydantic` is absent, so `models.py` / `config.py` / `catalog.py` have never been imported, let alone run.
- [ ] **Directory layout** — 9 subpackages missing (`discovery/`, `downloader/`, `extractor/`, `engines/`, `transforms/`, `aem/`, `sync/`, `reporting/`, `utils/`), plus `config/aem_templates/`.
- [ ] **`cli.py`** — absent, yet `[project.scripts]` declares `docushift = "docushift.cli:main"`, so the console script installs broken.
- [ ] **`pytest` framework** — no `tests/` directory at all, so `testpaths = ["tests"]` collects nothing and exits green. Misleading.
- [ ] **`.gitignore`** — contains only `cache/`; `ConfigManager.__init__` unconditionally creates `output/`, and `state.db` needs ignoring.
- [ ] `config/docsite.yaml`.

### Phase 2: Catalog Migration to CSV, Catalog Manager & State Engine
- [ ] **Migrate catalog storage from JSON to CSV** (decided 2026-09-03, see `architecture.md` §3):
  - Split into `config/products.csv` + `config/versions.csv`, normalized on `product_code`; retire `config/catalog.json`.
  - Reshape `taxonomy.yaml` to family definitions + keyword rules; move the hardcoded heuristics out of `config.py:resolve_product_info()` into YAML data.
  - Add `family_source` provenance (`manual` > `taxonomy_rule` > `docsite_category` > `unclassified`).
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
