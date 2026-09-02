# Project Context & Living Ledger: DocuShift Tool

> **Last Updated:** 2026-09-02  
> **Status:** Architecture & Scaffolding Phase  
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
   - **Smart Merge**: Additive updates that preserve existing data and manual user overrides in `config/catalog.json`.
2. **Taxonomy & Family Mapping**: Categorize products and versions into structured Product Families (e.g., Messaging, Integration, Analytics, WebFOCUS, Omni, Data Management) with support for manual rule overrides in `config/taxonomy.yaml`.
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
├── CONTEXT.md              # Living state & decision ledger (This file)
├── README.md               # Repository landing page & quickstart
├── pyproject.toml          # Python package manifest, dependencies, test config
├── docs/                   # Living Project Documentation
│   ├── architecture.md     # Full 7-stage pipeline architecture, additive catalog, data schemas
│   ├── user-guide.md       # CLI reference, batch workflows, manual catalog editing
│   └── planning.md         # Master roadmap, milestones, validation criteria
├── config/                 # Configurations, Taxonomies & Catalog
│   ├── catalog.json        # Master Additive Product/Version Catalog (tool + manual editable)
│   ├── taxonomy.yaml       # BU, Product Family, and Product Code mapping definitions
│   ├── docsite.yaml        # docs.tibco.com discovery endpoints & crawling rules
│   └── aem_templates/      # YAML/Markdown templates for AEM toc.yml, nav.yml, and landing pages
├── src/                    # Source code
│   └── docushift/
│       ├── __init__.py
│       ├── cli.py          # Click CLI entrypoint (catalog, download, convert, sync, report)
│       ├── config.py       # Configuration & taxonomy manager
│       ├── catalog.py      # Additive Catalog Manager (merges tool fetch + manual edits)
│       ├── state.py        # State tracking engine (SQLite/JSON ledger for delta operations)
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
| 2026-09-02 | Catalog | **Optional & Additive Catalog** (`catalog.py` & `config/catalog.json`) | Product version fetching is purely on-demand; fetches do additive smart-merges preserving manual user edits and overrides. |
| 2026-09-02 | Scope | Expanded scope to 7-Stage End-to-End Pipeline for ~250 products (TIBCO & IBI) | Covers complete lifecycle from `docs.tibco.com` discovery to GitHub/AEM sync. |
| 2026-09-02 | State Tracking | Built-in State Tracking Engine (`state.py`) | Essential for batching ~250 products, delta fetching, resume-on-failure, and progress metrics. |

---

## 4. Active Workstreams & Next Steps
- [x] Verified `docs.tibco.com` API endpoints and active/archived version models
- [ ] Initialize Python package (`pyproject.toml`) and directory scaffolding
- [ ] Implement Additive Catalog Manager (`src/docushift/catalog.py`) & State Engine (`src/docushift/state.py`)
- [ ] Implement Docsite Discovery Crawler (`src/docushift/discovery/crawler.py`) for active + archived versions
- [ ] Implement Resumable Downloader & Extractor (`src/docushift/downloader/`)
- [ ] Implement MadCap Flare Engine + CSH Mapper with `pytest` unit test suite
