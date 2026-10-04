# Project Context: DocuShift Tool

> **Last Updated:** 2026-10-02
> **Primary Runtime:** Python 3.11+ (Active: Python 3.13)
> **Business Scope:** TIBCO & IBI Documentation Migration (~250 Products) to AEM on GitHub — DocuShift produces the repo-shaped trees; publishing them is a separate step

**Read this first, and usually only this.** It says what the tool is, where it stands,
and where to look. It does not record history: decisions and measurements live in the
phase that made them (`docs/planning.md` while open, `docs/history/phases/` once done).

---

## 1. Project Overview & Business Mission
**DocuShift** is an enterprise-grade documentation migration, transformation, and sync pipeline built to transition ~250 products across two major Business Units (**TIBCO** and **IBI**) from legacy docsite publishing (`docs.tibco.com`) into modern **Adobe Experience Manager (AEM)** documentation repositories hosted on **GitHub**.

### The 7 Core Pipeline Pillars
1. **Catalog & Discovery (On-Demand & Additive)**:
   - Queries `docs.tibco.com/a_z_products` and underlying APIs (`/api/a_to_z`, `/api/products/{slug}`, `/api/products/archive/{slug}`, `/api/product_list_by_suites`).
   - Discovers **Active Versions** (with "Download All Docs" ZIP endpoints) and **Archived Versions** ("Other Versions" archive index).
   - **Product Scope**: 61 EBX/Spotfire products are permanently excluded from conversion via `config/scope.yaml`, matched by exact docsite slug and recorded as `in_scope=false` in `products.csv`. They stay fully catalogued — excluded is not absent (`architecture.md` §3.10).
   - **End-of-Support**: support's retirement report is committed under `config/eos/` and re-applied by `catalog eos`, which resolves `release_status` / `retirement_date` / `release_status_source` onto each version row. A `retired` version is skipped by every working command; **only `retired` gates** — a dated retirement *announcement* still converts, and a version with no row is `unknown`, never retired (`architecture.md` §3.11).
   - **Conversion Policy**: Active versions are flagged `convert_eligible: true` by default; archived versions are captured for full inventory (`is_archived: true`, `convert_eligible: false` by default, convertable only if explicitly marked).
   - **Smart Merge**: Additive snapshot-based 3-way merge into `config/products.csv` and `config/versions.csv` that preserves manual user edits without requiring a manual override flag.
2. **Taxonomy & Family Mapping**: Categorize products into structured Product Families (e.g., Messaging, Integration, Analytics, WebFOCUS, Omni, Data Management). Per-product assignment lives in `config/products.csv` (bulk-editable); `config/taxonomy.yaml` holds family definitions and keyword inference rules only. Classification is majority-manual — the docsite's own category data covers only a minority of products.
3. **Package Acquisition & Cache**: Resumable downloader with checksumming and rate-limiting, writing doc ZIPs into the per-family workspace `families/{locale}-{bu}-{family}/downloads/`. Selection is `convert_eligible` (policy) narrowed by `convert_batch` (which run), so a POC converts three versions without touching the other ~1,500 rows. Where discovery yields no usable `zip_url`, a hand-obtained ZIP is ingested with `--from-file` and pinned `zip_source=manual` — it lands at the same canonical path and converts through the same code path as a downloaded one.
4. **Extraction & Asset Cataloger**: Unzip into `families/{...}/extracted/{product}/{version}/`, discover HTML docs, Context-Sensitive Help (CSH) maps, and assets. Assets are inventoried **by category and by destination, never by an extension allow-list** — the corpus holds 100 extensions, and what a file *is* for is decided by which tree it sits in, not by its suffix (`architecture.md` §5.5). Runs over the same selection as the downloader, so archived versions are neither fetched nor unpacked.
5. **Multi-Engine Conversion to GFM**: Convert HTML (primarily MadCap Flare + DITA/WebWorks/DocBook) into clean GitHub-Flavored Markdown tailored for AEM. The engine is a **per-version** property detected from package contents — the same product commonly spans generators across its version history. Conversion also emits the version's **context-sensitive help map** (`csh.yml`) and stamps the matching identifiers into topic frontmatter, so a product's Help button still resolves after migration.
6. **AEM Navigation & Architecture Synthesis**: Generate AEM-required navigation trees (`toc.yml`, `metadata.yml`, `version.yml`), landing pages, and frontmatter.
7. **Publishing Layout Assembly**: Organize converted output into repo-shaped directory trees on disk, named and laid out exactly as the target GitHub repositories are. **Git operations are out of scope** — branching, committing, review and pushing are picked up separately (`architecture.md` §6.0).

---

## 2. Directory Structure Standards

```
docushift-tool/
├── .gitignore              # Ignored caches, downloads, output, state DBs
├── .gitmessage             # Commit message template (User Requests / Changes / Technical Details)
├── CONTEXT.md              # Current state and where to look (This file)
├── README.md               # Repository landing page & quickstart
├── pyproject.toml          # Python package manifest, dependencies, test config
├── docs/                   # Living Project Documentation
│   ├── quickstart.md       # One product, fetch to validate, in nine commands — the entry point
│   ├── architecture.md     # Full 7-stage pipeline architecture, additive catalog, data schemas
│   ├── design.md           # Logic & algorithms in standard English, marked Built vs Specified
│   ├── user-guide.md       # CLI reference, batch workflows, manual catalog editing
│   ├── planning.md         # Open phases in full; finished phases as a one-line index
│   ├── open-issues.md      # What is outstanding per product, and who owns it
│   ├── history/            # Archive, read on demand: ledger.md + phases/phase-NN.md
│   ├── REFRAME-REQUIREMENTS.md     # Stage 6b's requirements, numbered; the audit cites these
│   └── REFRAME-INTEGRATION-PLAN.md # How reframe was folded into the existing stage sequence
├── config/                 # Configurations, Taxonomies & Catalog
│   ├── products.csv        # Master Product registry (one row per product; bulk-editable in Excel)
│   ├── versions.csv        # Master Version registry (one row per version; convert_eligible toggles)
│   ├── taxonomy.yaml       # Family definitions per BU + keyword inference rules (no per-product rows)
│   ├── docsite.yaml        # docs.tibco.com discovery endpoints & crawling rules
│   ├── scope.yaml          # 61 products never converted, matched by exact docsite slug (§3.10)
│   ├── eos.yaml            # Points at the support report + 14 reviewed name aliases (§3.11)
│   ├── eos/                # Support's end-of-support report, committed as received
│   ├── docsite-migration.yaml # Points at the docsite team's export + its column mapping
│   ├── migration/          # The docsite team's migration export, committed as received
│   ├── reframe.yaml        # Editorial policy for Stage 6b: max_words cap, pin_layout_to
│   ├── origin-urls.yaml    # Per-product live URL shape; the only source for 301.yml, never guessed
│   ├── publishing.yaml     # Tree-naming tokens (docs_suffix, loc prefix); + publish_base_url in Phase 6
│   └── aem_templates/      # Jinja templates: toc.yml, metadata.yml, version.yml, landing pages
├── src/                    # Source code
│   └── docushift/
│       ├── __init__.py
│       ├── cli.py          # Click CLI entrypoint (catalog, download, extract, convert, reframe, sync, validate, csh, archive, status, report, doctor)
│       ├── config.py       # Configuration & taxonomy manager
│       ├── catalog.py      # Additive Catalog Manager (CSV read/write + snapshot 3-way merge)
│       ├── state.py        # State engine (SQLite: fetch snapshots, etags, sizes, per-stage status)
│       ├── discovery/      # Stage 1: docs.tibco.com API crawler (Active & Archived versions)
│       ├── downloader/     # Stage 3: Resumable package downloader & cache manager
│       │   └── fetcher.py  # PackageDownloader: resume, sha256-while-writing, atomic move, --from-file
│       ├── apiref.py      # Is a path an API reference? A marker decides, a name never does
│       ├── extractor/      # Stage 4: ZIP extractor & asset/CSH analyzer
│       │   ├── safe_unzip.py # Path-traversal refusal, checked before any member is written
│       │   ├── inventory.py # The one walk: API partition, asset category x destination, CSH
│       │   └── unpacker.py # PackageExtractor: .part/ swap, unchanged-ZIP skip, serial by design
│       ├── engines/        # Engine knowledge: detection (Stage 4), conversion (Stage 5)
│       │   ├── base.py     # The engine contract + document model; the registry; api_url()
│       │   ├── detector.py # Engine detection: layout markers, content signatures, generator tag
│       │   ├── roots.py    # Output-root location by content; innermost root owns a file
│       │   ├── csh.py      # The three help-map readers: Alias.xml, head.js, topics.js
│       │   ├── flare.py    # MadCap Flare handler: output roots, chrome, autonum, landing page, nav
│       │   ├── flare_toc.py # Flare's TOC: an AMD object literal, parsed and never executed
│       │   ├── dita.py     # SDL SuiteHelp handler: GUID doc-sets, one `<article>`, flat slugged output
│       │   ├── webworks.py # WebWorks handler: books, blockquote, tables-as-lists, popup links
│       │   ├── webworks_toc.py # WebWorks runtime: files.js, toc.js, books.xml, title.js
│       │   └── docbook.py  # DocBook handler: html/ by stylesheet, #mainContent, menu+toc+link graph
│       ├── converter/      # Stage 5: selection, dispatch, build-and-swap, per-version reporting
│       │   ├── driver.py   # ConversionDriver: engine lookup, unit loop, csh.yml, API urls, findings
│       │   └── navigation.py # Stage 6a: units -> one nav tree, toc.yml, metadata.yml, generated pages
│       ├── origins.py      # Where a topic is served today; the 301 row that replaces it
│       ├── reframe/        # Stage 6b: merge Flare topics into maintainable pages (Flare only)
│       │   ├── policy.py   # config/reframe.yaml: the cap, the layout pin, and their defaults
│       │   ├── packer.py   # R1/R2: which topics become one page — layout, and nothing else
│       │   ├── pages.py    # Writes the merged body: anchored ## sections, links retargeted
│       │   ├── toc.py      # The same navigation, repointed at page.md / page.md#anchor
│       │   ├── manifest.py # reframe.yml + redirects.yml: topic -> page -> anchor, and the policy
│       │   ├── renames.py  # rename-map.csv: the address each page was given, pinnable by a human
│       │   ├── csh.py      # Help identifiers carried onto the section that absorbed the topic
│       │   ├── review.py   # review-queue.csv: the pages a writer has to decide about, and why
│       │   ├── audit.py    # Requirements §6: self-validation; a failed check fails the stage
│       │   └── driver.py   # ReframeDriver: selection, Flare gate, build-and-swap, reporting
│       ├── validation/     # `validate`: does the published tree hold together?
│       │   ├── driver.py   # ValidationDriver: selection, target-dir walk, findings
│       │   ├── tree.py     # Folder shape: doc-classes, version segments, required artifacts
│       │   ├── artifacts.py # toc.yml / metadata.yml / version.yml parse and agree with the disk
│       │   ├── links.py    # Relative links resolve; absolute ones only with --check-external
│       │   ├── references.py # Asset references against the files actually placed
│       │   └── csh.py      # Every identifier in csh.yml still lands on a page that exists
│       ├── transforms/     # GFM Transformations (engine-neutral)
│       │   ├── callouts.py # Note/Warning/Tip to GFM alerts
│       │   ├── tables.py   # Table normalizer
│       │   ├── code.py     # Code syntax highlighter
│       │   ├── links.py    # Reference classification, resolution & percent-encoded emission
│       │   ├── csh.py      # CSH schema, resolver & flat csh.yml writer (engines supply readers)
│       │   ├── assets.py   # AssetCopier: one resolution, two outputs (invariant 13)
│       │   └── markdown.py # The HTML→GFM walk all engines share; vocabulary through four hooks
│       ├── sync/           # Stage 7: publishing-layout organizer (filesystem only, no git)
│       │   ├── distributor.py # WorkspaceDistributor: selection -> publishing form, .part/ swap
│       │   ├── redirects.py # Both sides of a redirect prefixed into published URLs
│       │   ├── router.py   # Shipped file -> doc-class: source folder first, then name; never \b
│       │   ├── documents.py # De-duplicate, title, order, render the flat index.md and toc.yml
│       │   ├── apirefs.py  # -resources: name each API tree, copy it, and url_map() its address
│       │   ├── archives.py # -resources: the history, built from the catalog and never the disk
│       │   └── versions.py # The drop-down: disk ∩ catalog, merged over what is already there
│       ├── reporting/      # Logging, metrics dashboard, audit generation
│       │   └── findings.py # The findings register: 41 codes, severity fixed once, never at the call site
│       └── utils/          # Shared helpers
│           ├── csvio.py    # CSV round-trip hygiene (BOM, bools, dates, natural sort)
│           ├── http.py     # Shared session builder + rate-limit floor (crawler and downloader)
│           ├── swap.py     # Build-and-swap with a retry: the Windows scanner loses ~1 rename in 7
│           ├── templating.py # The one Jinja environment every rendered artifact is built from
│           └── slug.py     # slugify(), workspace/tree names, and the publishing version segment
├── tests/                  # Automated Test Suite
│   ├── conftest.py         # Test fixtures
│   ├── unit/               # Unit tests per stage (catalog, discovery, parser, transforms, state)
│   ├── integration/        # End-to-end multi-product conversion tests
│   └── fixtures/           # Sample Flare zips, CSH maps, HTML docs, assets
├── cache/                  # (Git-ignored) state.db and scratch
├── families/               # (Git-ignored) Per-family working set — the download/extract target
│   └── en-us-tib-messaging/        # {locale}-{bu}-{family} over repo_slug tokens; NOT a repo name
│       ├── downloads/              # ems-10.4.0.zip  ({product_code}-{version}.zip)
│       ├── extracted/ems/10.4.0/   # version keeps its dots; dashes are a Stage 6 concern
│       └── archive/                # only via `docushift archive download`
├── output/                 # (Git-ignored) Final converted GFM output organized by BU/Family
│   └── …/<product>/<version>/
│       ├── csh.yml         # identifier -> topic map for this version (omitted when the package has none)
│       ├── toc.yml
│       └── <doc-set>/…     # converted topics, CSH identifiers stamped into frontmatter
├── reframed/               # (Git-ignored) Stage 6b output; a sibling of output/, never written over it
│   └── …/<product>/<version>/
│       ├── toc.yml         # the same navigation, retargeted to page.md / page.md#anchor
│       ├── metadata.yml
│       ├── reframe.yml     # which topic became which section of which page, plus the policy
│       ├── redirects.yml   # one anchored 301 per source topic, in this tool's coordinates
│       ├── 301.yml         # the cutover map, in live docs.tibco.com URLs; only where declared
│       ├── rename-map.csv  # the address each page was given; a human can pin one
│       ├── review-queue.csv # the pages a writer must decide about — the only file meant to be edited
│       ├── csh.yml         # carried through where the version had one
│       └── <doc-set>/…     # the merged pages, assets copied through untouched
├── reports/                # Generated analyses kept for reference (versions-analytics.html)
└── scratch/                # Throwaway investigation scripts; nothing here is imported
```

Per-family folders are created on demand by the downloader, not at startup: pre-creating one per declared family would make an empty workspace look like a started migration.

---

## 3. Current State (2026-10-02)

- **Every pipeline stage is built**: catalog → download → extract → convert (Flare, DITA,
  WebWorks, DocBook) → navigation → reframe (Flare merge) → sync → validate. Phases 1–33,
  35 and 36 are finished; see the [index](docs/planning.md#finished-phases).
- **Catalog**: 669 products (604 in scope), 5,181 versions, in `config/products.csv` /
  `config/versions.csv`. Families are assigned by hand (Phase 32).
- **Converted**: four families in `output/` (activespaces, ems, streaming, tra), three of
  them merged in `reframed/` (activespaces, ems, tra). 27 published versions carry a
  `301.yml` cutover map (Phase 35), and `toc.yml` uses html-to-md's dialect (Phase 36).
- **Quality bar**: 1,932 tests, `ruff check src tests` clean, 76 finding codes in the
  register.
- **Branch**: `reframe-component`. Git push and publishing are out of scope (`architecture.md` §6.0).

## 4. Next Steps

1. **Phase 34, the whole-tool code review**, in progress (batch 4 fixing, cross-cutting passes running): twelve component units,
   then three cross-cutting passes, find first and fix after triage
   ([`planning.md` §1](docs/planning.md#1-active-phases)).
2. **Phase 37, one sheet for the family decision**, planned and awaiting approval: four
   read-only columns in `products.csv` (family name, description, size, rule suggestion)
   so families can be reviewed and reassigned in one place.
3. The two carried-forward technical items are confirmed or closed during Phase 34
   ([list](docs/planning.md#carried-forward-open-items)).
4. Product-level open issues, with owners: [`docs/open-issues.md`](docs/open-issues.md).

## 5. Where to Look

| question | file |
|---|---|
| How do I run it? | `docs/quickstart.md`, then `docs/user-guide.md` |
| Why is it shaped this way? | `docs/architecture.md` (sections are cited from code as §N.N) |
| What exactly does step X decide? | `docs/design.md` |
| What is being built now? | `docs/planning.md` §1 |
| When and why was X decided? | `grep -rn "X" docs/history`, then open the one phase file |
| What is broken for a product, and who owns it? | `docs/open-issues.md` |

## 6. Keeping the Docs

- **Write a fact once.** A decision and its measurement go in the phase that makes them.
  Other files link to it instead of restating it. `architecture.md` and `design.md` are
  updated in place when the design they describe changes.
- **This file stays short.** §3 and §4 are rewritten, not appended to, when the state
  changes.
- **A finished phase moves.** Its section goes verbatim to `docs/history/phases/`, and the
  index row in `planning.md` takes its place, in the same commit that finishes it.
