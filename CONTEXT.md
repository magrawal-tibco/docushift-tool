# Project Context & Living Ledger: DocuShift Tool

> **Last Updated:** 2026-09-03  
> **Status:** Phases 1-2 complete and verified; Phase 4's selection model and path contract landed ahead of the I/O (203 tests pass, lint clean); Phase 3 (docsite discovery crawler) next  
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
3. **Package Acquisition & Cache**: Resumable downloader with checksumming and rate-limiting, writing doc ZIPs into the per-family workspace `families/{locale}-{bu}-{family}/downloads/`. Selection is `convert_eligible` (policy) narrowed by `convert_batch` (which run), so a POC converts three versions without touching the other ~1,500 rows. Where discovery yields no usable `zip_url`, a hand-obtained ZIP is ingested with `--from-file` and pinned `zip_source=manual` — it lands at the same canonical path and converts through the same code path as a downloaded one.
4. **Extraction & Asset Cataloger**: Unzip into `families/{...}/extracted/{product}/{version}/`, discover HTML docs, Context-Sensitive Help (CSH) maps, and binary/document assets (`PDF`, `DOC`, `XLS`, `TXT`, `PNG`, `SVG`, `ZIP`). Runs over the same selection as the downloader, so archived versions are neither fetched nor unpacked.
5. **Multi-Engine Conversion to GFM**: Convert HTML (primarily MadCap Flare + DITA/WebWorks/DocBook) into clean GitHub-Flavored Markdown tailored for AEM. The engine is a **per-version** property detected from package contents — the same product commonly spans generators across its version history.
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
│       └── utils/          # Shared helpers
│           ├── csvio.py    # CSV round-trip hygiene (BOM, bools, dates, natural sort)
│           └── slug.py     # slugify() + family_folder() -> `en-us-tibco-messaging`
├── tests/                  # Automated Test Suite
│   ├── conftest.py         # Test fixtures
│   ├── unit/               # Unit tests per stage (catalog, discovery, parser, transforms, state)
│   ├── integration/        # End-to-end multi-product conversion tests
│   └── fixtures/           # Sample Flare zips, CSH maps, HTML docs, assets
├── cache/                  # (Git-ignored) state.db and scratch
├── families/               # (Git-ignored) Per-family working set — the download/extract target
│   └── en-us-tibco-messaging/      # {locale}-{bu}-{family}; doubles as the publishing repo name
│       ├── downloads/              # ems-10.4.0.zip  ({product_code}-{version}.zip)
│       ├── extracted/ems/10.4.0/   # version keeps its dots; dashes are a Stage 6 concern
│       └── archive/                # only via `docushift archive download`
└── output/                 # (Git-ignored) Final converted GFM output organized by BU/Family
```

Per-family folders are created on demand by the downloader, not at startup: pre-creating one per declared family would make an empty workspace look like a started migration.

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
| 2026-09-03 | Engine Model | **`engine` moves from product-level to version-level** (`products.csv` → `versions.csv`; `Product.engine` → `ProductVersion.engine`). | Confirmed by user: the source toolchain varies across a product's version history — an older release may be DITA or FrameMaker/WebWorks while the latest is Flare. A product-level engine would apply the wrong converter to every older version. |
| 2026-09-03 | Engine Model | **Engine is detected, not declared.** Default changes from `flare` to `auto`; `engines/detector.py` resolves it from extracted content and writes back to `versions.csv`. New `engine_source` provenance (`manual` > `detected` > `auto`). Versions left at `auto` are skipped with a warning, never guessed. | Hand-assigning across 1,500-4,000 versions is infeasible. The old `SourceEngine.FLARE` default was silently destructive — a WebWorks set fed to the Flare engine yields plausible-looking but wrong Markdown with no error. Detection signals verified against the cached `dsp_gridserver` 7.1.1 sample: all six Flare marker paths present, `MadCap` reference in 197/197 `admin-guide` files. |
| 2026-09-03 | Pipeline | Catalog becomes a **mid-pipeline write target**: `engine` cannot be known at Stage 1 (Discovery) and is written back after Stage 4 (Extraction). | Engine resolution requires the package contents, so discovery can only leave it `auto`. Stage 5 reads the value to select a converter. |
| 2026-09-03 | Taxonomy | `taxonomy.yaml` keyword rules assign `bu`/`family` **only** — engine assertions removed. | Per-version engine variance makes any product-level engine rule wrong by construction. The existing `rendezvous`/`streambase`/`iprocess` → `docbook` mappings in `taxonomy.yaml` are product-level assertions that must be dropped. |
| 2026-09-03 | Process | Standardised commit messages via `.gitmessage` (Conventional Commits subject + **User Requests** / **Changes** / **Technical Details** sections). Requires two local settings: `git config --local commit.template .gitmessage` and `git config --local core.commentChar ';'`. | The **User Requests** section preserves the intent behind each change — in AI-assisted work the originating ask, and especially the mid-course correction, is the context most easily lost. The pre-commit checklist enforces the living-docs discipline at the point where drift would otherwise be introduced. |
| 2026-09-03 | CLI | Full command tree declared in `cli.py`, matching the surface already documented in `user-guide.md`. Stage commands are scaffolded but **fail loudly** — each raises a `ClickException` naming its implementing phase rather than being omitted or no-op'ing. New `docushift doctor` (paths + artifact presence) is the only functional command in Phase 1; `status` stays reserved for the Phase 7 delta dashboard the user guide describes. | `[project.scripts]` already promised `docushift.cli:main`, so the module had to exist. A `convert` that exits 0 while converting nothing is worse than one that doesn't exist: it makes the pipeline look further along than it is — the same failure mode the Phase 1 audit found in `pytest` exiting green on zero tests. |
| 2026-09-03 | Dependencies | Added `jinja2` to `pyproject.toml` dependencies. | `config/aem_templates/` ships Jinja templates for the Stage 6 synthesizer; a template directory with no template engine behind it is incoherent. |
| 2026-09-03 | Tooling | Added `[tool.ruff]` to `pyproject.toml` with an explicitly pinned rule set (`E,F,I,UP,B,SIM`, line length 120). Fixed the 47 findings this surfaced in the pre-existing `models.py` / `config.py` / `catalog.py`, including two unused imports, an unused variable, and `str, Enum` → `StrEnum`. | `ruff` was a declared dev dependency with no configuration, so its rule set was whatever the installed version defaulted to — the lint result would have silently changed on upgrade. All 47 findings were in code written before the environment existed; none were in the Phase 1 additions, which is what running the linter for the first time was meant to establish. |
| 2026-09-03 | Merge Implementation | The 3-way decision reduces to one predicate: take the fetched value only if the CSV value still equals the recorded snapshot (`CatalogManager._take_theirs`). With **no** snapshot, the fallback is to keep the CSV value — except where it is empty. | Field-by-field, not row-by-row: an edited `display_name` must not freeze the `slug` next to it. The no-snapshot fallback is the conservative direction — inventing a base would silently overwrite edits made before the state DB existed. |
| 2026-09-03 | Merge Scope | Discovery owns only `display_name`, `slug`, `is_archived`, `convert_eligible`, `release_date`, `zip_url`. `engine`/`engine_source` are excluded from the merge **and from `version_snapshot` entirely**; `family` is merged by provenance rank, not by snapshot comparison. | The engine columns are written by the detector after extraction, so a fetch has nothing true to say about them — omitting the columns from the snapshot table makes that structural rather than a rule someone can forget. Family needs ranking because two automated sources disagree with different confidence. |
| 2026-09-03 | Merge Safety | Deletion detection is scoped to the products present in the current fetch. | Otherwise `catalog fetch --product ems` would read every other product's absence as a deletion and abort — or, with `--allow-deletes`, wipe the catalog. |
| 2026-09-03 | Testing | `tests/` became a package (`__init__.py` at each level) and `pythonpath` gained `"."`, so suites can share `make_product` / `make_version` builders from `tests.conftest`. | Merge tests need to construct discovery-shaped products inline; fixtures cannot be called with arguments, and duplicating the builders across `test_catalog.py`, `test_state.py`, and `test_cli.py` would let them drift apart. |
| 2026-09-03 | Taxonomy | Docsite category data (`/product/categories`, `/api/bu_category_products`) is **advisory only, never authoritative**. Added `family_source` provenance column (`manual` > `taxonomy_rule` > `docsite_category` > `unclassified`, first wins). | Confirmed by user: the majority of products carry no docsite category, so classification is a majority-manual triage job. Provenance distinguishes "triaged and genuinely general" from "never looked at" and makes triage progress a reportable metric. |
| 2026-09-03 | Selection | New **`convert_batch`** column in `versions.csv` — a free-text run label (`poc-1`, `wave-2`), empty by default, **opt-in**. Kept separate from `convert_eligible`; the two compose and eligibility is the hard gate. `--batch` is a selector on `catalog fetch/list`, `download`, `extract`, `convert`, `sync`, plus `catalog batches` and `catalog set --batch`. | Confirmed by user: conversion is frequently partial (POCs, waves). With only `convert_eligible` — which defaults to `true` — scoping a three-version POC means flipping ~1,497 rows to `false`, and "deliberately out of scope" becomes indistinguishable from "not in this wave". Opt-in inverts the cost: three cells, not the whole sheet. Structurally excluded from `version_snapshot` for the same reason as the engine columns — no automated stage writes it, so a fetch has nothing true to say about it. |
| 2026-09-03 | Workspace | Downloads and extractions move out of `cache/{downloads,extracted}/` into a per-family workspace: **`families/{locale}-{bu}-{family}/{downloads,extracted,archive}/`**. `ConfigManager` is the sole owner of the contract (`family_dir`, `downloads_dir`, `extracted_dir`, `archive_dir`, `download_path`, `extract_path`); `utils/slug.py` is the sole owner of the name. Per-family folders are created on demand, not at startup. | Requested by user. The name matches the predecessor `html-to-md` project, where `en-us-<bu>-<family>` doubles as the **publishing repository name** — so the working tree already mirrors its destination. `downloads/` and `extracted/` split at the top of the family so reclaiming disk after an extract is one `rmtree`, not a glob. Versions deliberately keep their dots (`10.4.0`, not `10-4-0`): this path is keyed by the catalog and must round-trip to a `versions.csv` key, which `6-2-3` cannot. Dots-to-dashes is a Stage 6 (publishing path) concern. Trademark symbols are stripped *before* the NFKD fold, since NFKD decomposes `™` into the literal letters "TM". |
| 2026-09-03 | Archive Policy | Archived versions are **never downloaded and never extracted** by the pipeline — extraction now runs over the same selection as download. On-demand access is a separate utility: `docushift archive list` / `docushift archive download [--extract]`, writing to `families/<family>/archive/`. | User chose the separate-utility option over the presets offered. Closes an asymmetry the audit found: `convert_eligible` was documented as the *download* filter with nothing said about extraction. `archive/` sits outside `downloads/` deliberately — a reference ZIP in the pipeline's working set would look to Stage 4 like a package awaiting conversion. |
| 2026-09-03 | Package Source | **Manually supplied ZIPs are a first-class package source.** New `zip_source` column in `versions.csv` (`auto` \| `manual`); `docushift download --from-file <zip>` and `docushift archive download --from-file <zip>` copy a hand-obtained package to the canonical `download_path()` / new `archive_path()`, validate it with `zipfile.is_zipfile`, and pin the row. `validate()` exempts `manual` rows from the *convert-eligible with no `zip_url`* problem; `zip_source` joins the structural merge exclusions. Design only — see `architecture.md` §3.8. | Requested by user: discovery will not always resolve a usable `zip_url` (products with no download-all bundle, non-composable `folder_path`, stale archive `zipPath`), and the ZIP is often obtainable another way. The file goes to the location the pipeline already reads, so Stage 4 needs no second code path. The provenance must be a **CSV column, not a filesystem check**: `families/` is git-ignored, so a validator that stats disk would call every hand-supplied row broken on any machine that has not downloaded yet. The local path is deliberately **not** stored — `D:\downloads\x.zip` is valid on one machine, whereas `(bu, family, product_code, version)` derives the location anywhere. `zip_url` stays merged while only the supply decision is pinned, which makes "discovery has since found a real URL" a computable warning. |
| 2026-09-03 | Process | Implementation order returns to **Phase 3 (discovery crawler)**; the Phase 4 work already landed is design-only (a CSV column and a path contract, no network dependency). The `zip_source` schema/merge/validate half is filed under Phase 3, not Phase 4. | User flagged that Phase 4 implementation had run ahead of Phase 3. The `zip_source` split is not arbitrary: the merge exclusion has to exist *before* the first real `catalog fetch`, or a fetch could overwrite a hand-supplied row. |
| 2026-09-03 | Taxonomy | A `family` value not declared in `taxonomy.yaml` is **auto-registered with a warning**, never rejected. `CatalogManager.warnings()` is separate from `validate()`: problems block the write, warnings do not. The warning names the folder that will be created. | User chose warn-once over rejection: families are user-extensible by design, and a hard failure would make `catalog import` unusable mid-triage. Naming the resulting `families/en-us-tibco-streaming-analytics` is what makes the warning also catch the other case — a typo (`mesaging`) about to become its own folder. |

---

## 4. Active Workstreams & Next Steps

### Verified state as of 2026-09-03
Audited against the filesystem, not against checkboxes:
- [x] Verified `docs.tibco.com` API endpoints and active/archived version models
- [x] `pyproject.toml`, `config/taxonomy.yaml` created
- [x] **Phase 1 scaffolding closed**: all 9 subpackages created; `cli.py` command tree written (so `[project.scripts]` now resolves); `tests/` with `conftest.py`, unit and integration suites, and a documented `fixtures/` plan; `config/docsite.yaml` and `config/aem_templates/` (Jinja `toc.yml`/`nav.yml`/`meta.yml`/`index.md`) added; `.gitignore` extended to `output/`, `*.db`, `.venv/`, and build/test caches
- [x] **Environment created and code executed for the first time** — `.venv` on Python 3.13.7, `pip install -e ".[dev]"`, `ruff check src tests` clean, and the `docushift` console script runs. Setup from the repo root:
  ```
  python -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev]" && .venv/Scripts/python -m pytest
  ```
- [x] **Phase 2 closed**: `models.py` reshaped (per-version engine, `family_source`, volatile fields evicted); `utils/csvio.py`, `state.py`, and a CSV-backed `catalog.py` with the snapshot 3-way merge written; `config.py` switched to `products_path`/`versions_path` and rule-driven classification; `taxonomy.yaml` reshaped to families + rules; `config/catalog.json` removed; the `catalog` CLI group wired up apart from `fetch`. **157/157 tests pass**, lint clean.
- [x] **Phase 4's two design halves landed early** (the halves that are decisions, not I/O): the `convert_batch` selection model and the families-workspace path contract. `utils/slug.py`, `ConfigManager` path methods, `CatalogManager.iter_versions(batch=…, eligible_only=…)` / `batches()` / `warnings()`, `--batch` on every stage command, `catalog batches`, and the `archive` group (`list` functional, `download` pending Phase 4 I/O). **203/203 tests pass**, `ruff check src tests` clean; the CLI was exercised end to end against a demo catalog in `C:\tmp\dsdemo`.

### Next steps
Implementation order is **Phase 3 before any further Phase 4 code** — the two Phase 4 items above were design decisions with no network dependency, and running further ahead is not intended.

- [ ] **Phase 3 — Docsite Discovery Crawler** (`src/docushift/discovery/crawler.py`) for active + archived versions, wiring `catalog fetch` to `CatalogManager.merge_fetch_results()` — the only piece missing from that command
- [ ] **Phase 3 — `zip_source` catalog half** (`auto` | `manual`): model + column + round-trip, `catalog set --zip-source`, structural merge exclusion, `validate()` exemption, `warnings()` rule. Must land with the crawler, not after it, so the first real fetch cannot overwrite a hand-supplied row
- [ ] **Phase 4 — acquisition I/O** against the settled contract: resumable downloader into `downloads_dir()`, ZIP extractor into `extract_path()`, `docushift archive download`, `--from-file` ingestion plus `ConfigManager.archive_path()`, and the per-version path/checksum/status writes into `state.db`
- [ ] **Phase 5** — MadCap Flare Engine + CSH Mapper with `pytest` unit test suite
