# Project Context & Living Ledger: DocuShift Tool

> **Last Updated:** 2026-09-03  
> **Status:** Architecture & Scaffolding Phase (Phase 1 ~70% complete)  
> **Primary Runtime:** Python 3.11+ (Active: Python 3.13)  
> **Business Scope:** TIBCO & IBI Documentation Migration (~250 Products) to AEM on GitHub

---

## 1. Project Overview & Business Mission
**DocuShift** is an enterprise-grade documentation migration, transformation, and sync pipeline built to transition ~250 products across two major Business Units (**TIBCO** and **IBI**) from legacy docsite publishing (`docs.tibco.com`) into modern **Adobe Experience Manager (AEM)** documentation repositories hosted on **GitHub**.

### The 7 Core Pipeline Pillars
1. **Catalog & Discovery (On-Demand & Additive)**:
   - Queries `docs.tibco.com/a_z_products` and underlying APIs (`/api/a_to_z`, `/api/products/{slug}`, `/api/products/archive/{slug}`, `/api/product_list_by_suites`).
   - Discovers **Active Versions** (with "Download All Docs" ZIP endpoints) and **Archived Versions** ("Other Versions" archive index).
   - **Conversion Policy**: Active versions are flagged `convert_eligible: true` by default; archived versions are captured for full inventory (`is_archived: true`, `convert_eligible: false` by default, convertable only if explicitly marked).
   - **Smart Merge**: Additive snapshot-based 3-way merge into `config/products.csv` and `config/versions.csv` that preserves manual user edits without requiring a manual override flag.
2. **Taxonomy & Family Mapping**: Categorize products into structured Product Families (e.g., Messaging, Integration, Analytics, WebFOCUS, Omni, Data Management). Per-product assignment lives in `config/products.csv` (bulk-editable); `config/taxonomy.yaml` holds family definitions and keyword inference rules only. Classification is majority-manual — the docsite's own category data covers only a minority of products.
3. **Package Downloader & Cache**: Resumable downloader with checksumming and rate-limiting to download doc ZIPs into local `cache/downloads/`.
4. **Extraction & Asset Cataloger**: Unzip packages, discover HTML docs, Context-Sensitive Help (CSH) maps, and binary/document assets (`PDF`, `DOC`, `XLS`, `TXT`, `PNG`, `SVG`, `ZIP`).
5. **Multi-Engine Conversion to GFM**: Convert HTML (primarily MadCap Flare + DITA/WebWorks/DocBook) into clean GitHub-Flavored Markdown tailored for AEM.
6. **AEM Navigation & Architecture Synthesis**: Generate AEM-required navigation trees (`toc.yml`, `nav.yml`, `meta.yml`), landing pages, and frontmatter.
7. **Git Sync & Distribution**: Organize converted output into target GitHub repository structures ready for branching, review, and pushing.

---

## 2. Directory Structure Standards

```
docushift-tool/
├── .gitignore              # Ignored caches, downloads, output, state DBs
├── .gitmessage             # Commit message template (User Requests / Changes / Technical Details)
├── CONTEXT.md              # Living state & decision ledger (This file)
├── README.md               # Repository landing page & quickstart
├── pyproject.toml          # Python package manifest, dependencies, test config
├── docs/                   # Living Project Documentation
│   ├── architecture.md     # Full 7-stage pipeline architecture, additive catalog, data schemas
│   ├── user-guide.md       # CLI reference, batch workflows, manual catalog editing
│   └── planning.md         # Master roadmap, milestones, validation criteria
├── config/                 # Configurations, Taxonomies & Catalog
│   ├── products.csv        # Master Product registry (one row per product; bulk-editable in Excel)
│   ├── versions.csv        # Master Version registry (one row per version; convert_eligible toggles)
│   ├── taxonomy.yaml       # Family definitions per BU + keyword inference rules (no per-product rows)
│   ├── docsite.yaml        # docs.tibco.com discovery endpoints & crawling rules
│   └── aem_templates/      # YAML/Markdown templates for AEM toc.yml, nav.yml, and landing pages
├── src/                    # Source code
│   └── docushift/
│       ├── __init__.py
│       ├── cli.py          # Click CLI entrypoint (catalog, download, convert, sync, report)
│       ├── config.py       # Configuration & taxonomy manager
│       ├── catalog.py      # Additive Catalog Manager (CSV read/write + snapshot 3-way merge)
│       ├── state.py        # State engine (SQLite: fetch snapshots, etags, sizes, per-stage status)
│       ├── discovery/      # Stage 1: docs.tibco.com API crawler (Active & Archived versions)
│       ├── downloader/     # Stage 3: Resumable package downloader & cache manager
│       ├── extractor/      # Stage 4: ZIP extractor & asset/CSH analyzer
│       ├── engines/        # Stage 5: HTML Profile Extractors
│       │   ├── base.py     # BaseEngine interface
│       │   ├── detector.py # Profile auto-detector
│       │   ├── flare.py    # MadCap Flare handler (CSH, dropdowns, proxies)
│       │   ├── dita.py     # SDL DITA CMS handler
│       │   ├── webworks.py # WebWorks handler
│       │   └── docbook.py  # DocBook handler
│       ├── transforms/     # GFM Transformations
│       │   ├── callouts.py # Note/Warning/Tip to GFM alerts
│       │   ├── tables.py   # Table normalizer
│       │   ├── code.py     # Code syntax highlighter
│       │   ├── links.py    # Cross-document & anchor link resolver
│       │   ├── csh.py      # Context-Sensitive Help mapper (alias to MD anchor)
│       │   └── assets.py   # Asset re-linker & copier
│       ├── aem/            # Stage 6: AEM Navigation & Architecture generator (TOC/YAML)
│       ├── sync/           # Stage 7: GitHub workspace folder sync & distributor
│       ├── reporting/      # Logging, metrics dashboard, audit generation
│       └── utils/          # Shared helpers (network, file, slug, DOM)
├── tests/                  # Automated Test Suite
│   ├── conftest.py         # Test fixtures
│   ├── unit/               # Unit tests per stage (catalog, discovery, parser, transforms, state)
│   ├── integration/        # End-to-end multi-product conversion tests
│   └── fixtures/           # Sample Flare zips, CSH maps, HTML docs, assets
├── cache/                  # (Git-ignored) Downloaded ZIPs and extracted working sets
│   ├── downloads/
│   └── extracted/
└── output/                 # (Git-ignored) Final converted GFM output organized by BU/Family
```

---

## 3. Current State & Decision Ledger

| Date | Category | Decision / Update | Rationale / Note |
| :--- | :--- | :--- | :--- |
| 2026-09-02 | Discovery | Verified `docs.tibco.com` APIs (`/api/a_to_z`, `/api/products/{slug}`, `/api/products/archive/{slug}`) | Discovered exact JSON structures for Active versions ("Download All Docs" ZIP) and Archived versions ("Other Versions" ZIPs). |
| 2026-09-02 | Archive Policy | Default `convert_eligible: false` for archived versions | Captures complete product history while preventing unnecessary conversion of deprecated versions unless explicitly flagged. |
| 2026-09-02 | Catalog | **Optional & Additive Catalog** (`catalog.py` & `config/catalog.json`) ~~JSON storage~~ *(storage format superseded 2026-09-03; the on-demand/additive principle stands)* | Product version fetching is purely on-demand; fetches do additive smart-merges preserving manual user edits and overrides. |
| 2026-09-02 | Scope | Expanded scope to 7-Stage End-to-End Pipeline for ~250 products (TIBCO & IBI) | Covers complete lifecycle from `docs.tibco.com` discovery to GitHub/AEM sync. |
| 2026-09-02 | State Tracking | Built-in State Tracking Engine (`state.py`) | Essential for batching ~250 products, delta fetching, resume-on-failure, and progress metrics. |
| 2026-09-03 | Catalog Format | **CSV replaces JSON** as catalog source of truth: `config/products.csv` + `config/versions.csv`, normalized on `product_code`. `config/catalog.json` retired. | ~250 products x 5-15 versions = 1,500-4,000 rows. Dominant human edits are column operations (bulk-toggle `convert_eligible`, reassign `family`) — trivial in Excel, hostile in nested JSON. CSV also yields 1-line git diffs per new version vs. 10-line nested inserts. |
| 2026-09-03 | Catalog Schema | Volatile machine state (`zip_etag`, `zip_size`, checksums, per-stage status, `metadata` dict) moved out of the catalog into `state.db`. | Keeps the CSVs stable enough to leave open in Excel — `catalog fetch` should only touch them when discovery finds a genuinely new product or version. Prevents save conflicts and diff churn. |
| 2026-09-03 | Merge Strategy | Replaced flag-based protection with **snapshot-based 3-way merge**: `state.db` stores the last-fetched values; any CSV field differing from that snapshot is inferred to be a human edit and is protected automatically. `custom_override` demoted to an explicit whole-row pin. | Requiring the user to remember `custom_override=true` on each edited row of a 4,000-row sheet guarantees silent data loss. This also makes the merge genuinely 3-way (base + theirs + mine), matching what `architecture.md` already claimed. |
| 2026-09-03 | Taxonomy | `taxonomy.yaml` demoted to **family definitions + keyword inference rules only**; per-product `bu`/`family` assignment moves to `config/products.csv`. Hardcoded ibi/webfocus/omni/iway heuristics in `config.py` become YAML data. | Scaling 250 hand-classified products in 4-level nested YAML recreates the exact editing pain CSV was chosen to avoid. |
| 2026-09-03 | Process | Standardised commit messages via `.gitmessage` (Conventional Commits subject + **User Requests** / **Changes** / **Technical Details** sections). Wired up with `git config --local commit.template .gitmessage`. | The **User Requests** section preserves the intent behind each change — in AI-assisted work the originating ask, and especially the mid-course correction, is the context most easily lost. The pre-commit checklist enforces the living-docs discipline at the point where drift would otherwise be introduced. |
| 2026-09-03 | Taxonomy | Docsite category data (`/product/categories`, `/api/bu_category_products`) is **advisory only, never authoritative**. Added `family_source` provenance column (`manual` > `taxonomy_rule` > `docsite_category` > `unclassified`, first wins). | Confirmed by user: the majority of products carry no docsite category, so classification is a majority-manual triage job. Provenance distinguishes "triaged and genuinely general" from "never looked at" and makes triage progress a reportable metric. |

---

## 4. Active Workstreams & Next Steps

### Verified state as of 2026-09-03
Audited against the filesystem, not against checkboxes:
- [x] Verified `docs.tibco.com` API endpoints and active/archived version models
- [x] `pyproject.toml`, `config/taxonomy.yaml` created
- [x] `models.py`, `config.py`, `catalog.py` written — **but never executed** (no venv, `pydantic` not installed, `import docushift` fails)
- [ ] **Scaffolding gap**: no `tests/` directory (so `pytest` collects nothing and exits green); all 9 subpackages missing (`discovery/`, `downloader/`, `extractor/`, `engines/`, `transforms/`, `aem/`, `sync/`, `reporting/`, `utils/`); `cli.py` missing while `[project.scripts]` declares `docushift = "docushift.cli:main"`, so the console script installs broken; `state.py`, `config/docsite.yaml`, `config/aem_templates/` missing
- [ ] **`.gitignore` gap**: contains only `cache/`, but `ConfigManager.__init__` unconditionally creates `output/`, and `state.db` needs ignoring

### Next steps
- [ ] Close Phase 1: venv + `pip install -e ".[dev]"`, subpackage stubs, `cli.py` command tree, `tests/` with real coverage of the merge logic, `.gitignore` fixes
- [ ] Migrate catalog to CSV: rewrite `catalog.py` load/save, split `config.py` paths, delete `config/catalog.json`, reshape `taxonomy.yaml`
- [ ] Implement State Engine (`src/docushift/state.py`) incl. last-fetch snapshot table backing the 3-way merge
- [ ] Implement Docsite Discovery Crawler (`src/docushift/discovery/crawler.py`) for active + archived versions
- [ ] Implement Resumable Downloader & Extractor (`src/docushift/downloader/`)
- [ ] Implement MadCap Flare Engine + CSH Mapper with `pytest` unit test suite
