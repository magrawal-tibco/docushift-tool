# DocuShift Master Planning & Roadmap

> **Document Status:** Active Roadmap  
> **Last Updated:** 2026-09-02  
> **Target:** Multi-Stage Documentation Migration Pipeline (TIBCO & IBI -> AEM)

---

## 1. Modular Phase Breakdown

### Phase 1: Architecture, Living Docs & Project Scaffolding
- [x] Living documentation system (`CONTEXT.md`, `architecture.md`, `user-guide.md`, `planning.md`).
- [x] Multi-engine 7-stage pipeline design with additive catalog and active/archived version handling.
- [x] Verified `docs.tibco.com` API endpoints (`/api/a_to_z`, `/api/products/{slug}`, `/api/products/archive/{slug}`).
- [ ] Initialize Python package (`pyproject.toml`), directory layout, and `pytest` framework.
- [ ] Create initial `config/taxonomy.yaml` and `config/catalog.json`.

### Phase 2: Additive Catalog Manager & State Tracking Engine
- [ ] Additive Catalog Engine (`src/docushift/catalog.py`):
  - Load/save `config/catalog.json`.
  - Active (`convert_eligible: true`) vs Archived (`convert_eligible: false`) version model.
  - Smart 3-way merge logic (new tool fetch + existing catalog + manual user overrides).
  - CLI operations (`catalog fetch`, `catalog list`, `catalog enable`, `catalog set`).
- [ ] SQLite State Store (`src/docushift/state.py`):
  - Tracks lifecycle stages `(bu, family, product, version)`.
  - Delta querying and batch slice helpers.
- [ ] Unit tests for Catalog merger and State engine (`tests/unit/test_catalog.py`, `tests/unit/test_state.py`).

### Phase 3: Docsite Discovery Engine (`docs.tibco.com` API Client)
- [ ] API client for `docs.tibco.com` (`/api/a_to_z`, `/api/products/{slug}`, `/api/products/archive/{slug}`, `/api/product_list_by_suites`).
- [ ] Automated ZIP URL generator (`/pub/{folder_path}/doc/zip/tib_{...}_doc.zip` and archive `zipPath`).
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
- **Catalog Merge Fidelity**: 100% preservation of manual overrides and toggle states when fetching updates.
- **Active vs Archive Segregation**: Archived versions are never auto-converted unless explicitly flagged.
- **Unit Test Coverage**: >90% coverage on core transforms, engines, catalog, and state management.
- **Link & Asset Integrity**: Zero broken relative links or missing referenced assets in converted output.
