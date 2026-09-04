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
  - [x] CLI operations: `catalog list`, `show`, `enable`, `set`, `import`, `triage` are wired up; `catalog fetch` joined them in Phase 3.
- [x] SQLite State Store (`src/docushift/state.py`):
  - [x] `product_snapshot` / `version_snapshot` tables backing the 3-way merge. Deliberately carry no engine columns: the detector owns those, not discovery, so a fetch cannot reset a detected engine.
  - [x] Volatile fields evicted from the catalog: `zip_etag`, `zip_size`, checksums, paths, per-stage status, free-form product/version metadata.
  - [x] Lifecycle status per `(product, version)`, with `versions_with_status()` and `status_counts()` for the Phase 7 dashboard.
  - [x] `engine_folder_map` so a bundle that genuinely mixes generators stays visible rather than flattened into the one CSV column.
  - [x] Batch slice helper for phased runs across ~250 products.
- [x] Unit tests for Catalog merger and State engine (`tests/unit/test_catalog.py`, `tests/unit/test_state.py`, `tests/unit/test_csvio.py`), including CSV round-trip fidelity and Excel-mangling regression cases (`TRUE`/`FALSE` booleans, `11/4/2025` dates, `1.10` → `1.1` version keys, BOM loss, stray columns).

### Phase 3: Docsite Discovery Engine (`docs.tibco.com` API Client) — COMPLETE
`catalog fetch` is wired end to end and verified against the live docsite (2026-09-03): a scoped fetch of `tibco-enterprise-message-service` returns 33 versions, and the generated ZIP URLs answer HTTP 200 for both active and archived releases.
- [x] API client (`discovery/client.py`) for `/api/a_to_z`, `/api/products/{slug}`, `/api/products/archive/{slug}`, `/api/bu_category_products`, `/api/product_list_by_suites` — endpoints, templates and politeness read from `docsite.yaml`, urllib3 `Retry` on 429/5xx, and a hard minimum interval between requests rather than a token bucket.
- [x] Automated ZIP URL generator: `/pub/{folder_path}/doc/zip/tib_{folder_slug}_doc.zip` for active versions, the archive index's `zipPath` verbatim for archived ones.
- [x] Crawler (`discovery/crawler.py`) mapping payloads to `Product` records, **written against the API's verified real shape** (`architecture.md` §2.1): a `{"result": {"product": …}}` envelope, the detail object doubling as the current version with the rest under `siblings`, and `isArchive` splitting active from archived.
- [x] Category ingestion as an **advisory** family hint only — it may only promote `unclassified` rows, and a failure to reach it degrades triage rather than the crawl.
- [x] Partial-failure policy: an unreachable product is **excluded** from the result rather than returned empty, so a half-finished crawl can never trip deletion detection.
- [x] Pre-request filtering of the 70 (of 739) A-to-Z entries the docsite marks not publicly visible, which otherwise answer with an SSO page as HTTP 200.
- [x] `catalog fetch` wired to `CatalogManager.merge_fetch_results()` with `--allow-deletes`, `--dry-run`, a required scope, and `--product`/`--batch` resolved to crawl selectors so a three-product batch is three requests rather than 668.
- [x] Docsite ids and folder paths recorded in `state.db`, not in the CSVs.
- [x] **`zip_source` column** (`auto` | `manual`) in `versions.csv` — the catalog half of manually supplied packages (`architecture.md` §3.8). Landed here rather than in Phase 4 because the merge rule has to exist *before* the first real fetch runs, or a fetch could overwrite a hand-supplied row:
  - [x] `ProductVersion.zip_source` + `VERSION_COLUMNS` + round-trip; `catalog set --zip-source`.
  - [x] Excluded from `_MERGEABLE_VERSION_FIELDS` and from `version_snapshot`, alongside the engine columns and `convert_batch`. `zip_url` itself stays merged.
  - [x] `validate()`: exempt `zip_source=manual` from the *convert-eligible with no `zip_url`* problem.
  - [x] `warnings()`: flag `manual` rows that discovery has since found a `zip_url` for.
- [x] Unit & mock tests in `tests/unit/test_discovery.py` (38), plus `catalog fetch` wiring tests in `test_cli.py`. No network: a fake session serves payloads shaped like the real responses.

### Phase 4: Package Downloader & Extractor
The selection model and the on-disk layout this phase writes into are settled and tested (`architecture.md` §3.7 and §4); what remains is the I/O.

> **Sequencing note (2026-09-03).** The two `[x]` items below landed ahead of Phase 3. They are design decisions — a CSV column and a path contract — with no network dependency, and they were settled while answering how partial conversions and the families folder should work. Implementation order then returned to Phase 3, which is now complete; this phase is next.

- [x] **Selection model**: `convert_eligible` (policy) + `convert_batch` (scheduling), composed by `CatalogManager.iter_versions(batch=…, eligible_only=True)`. `--batch` is a selector on every stage command.
- [x] **Families workspace path contract** owned by `ConfigManager`: `family_dir`, `downloads_dir`, `extracted_dir`, `archive_dir`, `download_path`, `extract_path`, over `families/{locale}-{bu}-{family}/`.
- [ ] Resumable async/threaded downloader with checksum verification into `families/<family>/downloads/`, driven by `iter_versions(eligible_only=True)`. Skips rows pinned `zip_source=manual`.
- [ ] Record `download_path` / `extract_path` / `checksum` / status per version in `state.db` (columns already exist).
- [ ] ZIP extraction and asset cataloger into `families/<family>/extracted/<product>/<version>/`, over the **same** selection as download — archived versions must never be unpacked.
- [ ] `docushift archive download` — the on-demand escape hatch for a single archived ZIP, into `families/<family>/archive/`, outside the pipeline's working set.
- [ ] **`--from-file` ingestion** for manually supplied packages (`architecture.md` §3.8) — the I/O half of the `zip_source` work started in Phase 3:
  - [ ] `ConfigManager.archive_path()`, for symmetry with `download_path()`.
  - [ ] `docushift download --product X --version Y --from-file <zip>` — requires both selectors; validates with `zipfile.is_zipfile` before copying; copies (never moves) to `download_path()`; sets `zip_source=manual`; records sha256, size, status and the origin path in `state.db`.
  - [ ] `docushift archive download … --from-file <zip>` — same, to `archive_path()`; `--extract` unpacks within `archive/`, never into the pipeline's `extracted/`.
  - [ ] Unknown *version* on a known product is auto-added with a warning; unknown *product* is an error.
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
- [ ] **Decide the sync path shape** against a real AEM target repo: the nested form above, or the `html-to-md` publishing form `{locale}-{bu}-{family}/{locale}/{product}/{doc-class}/{version-dashed}/` with a sibling `-resources` repo. The family workspace name (§4.1) is already the publishing repo name, which argues for the latter. Deferred deliberately — see the note at the end of `architecture.md` §6.

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
- **Package Source Transparency**: A manually supplied ZIP converts through exactly the same path as a downloaded one — no downstream stage branches on provenance, and no machine-local path appears in either CSV.
- **Unit Test Coverage**: >90% coverage on core transforms, engines, catalog, and state management.
- **Link & Asset Integrity**: Zero broken relative links or missing referenced assets in converted output.
