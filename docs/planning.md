# DocuShift Master Planning & Roadmap

> **Document Status:** Active Roadmap  
> **Last Updated:** 2026-09-11  
> **Target:** Multi-Stage Documentation Migration Pipeline (TIBCO & IBI -> AEM)

---

## 1. Modular Phase Breakdown

### Phase 1: Architecture, Living Docs & Project Scaffolding
**Status: COMPLETE.** Implemented and verified 2026-09-03 — 54 tests pass, `ruff check src tests` is clean.
- [x] Living documentation system (`CONTEXT.md`, `architecture.md`, `user-guide.md`, `planning.md`; joined 2026-09-07 by `design.md`, the algorithm reference).
- [x] Multi-engine 7-stage pipeline design with additive catalog and active/archived version handling.
- [x] Verified `docs.tibco.com` API endpoints (`/api/a_to_z`, `/api/products/{slug}`, `/api/products/archive/{slug}`).
- [x] Create initial `config/taxonomy.yaml`.
- [x] `pyproject.toml` authored; `jinja2` added as a dependency for the AEM templates; `[tool.ruff]` added with an explicitly pinned rule set (`E,F,I,UP,B,SIM`, line length 120) so linting does not drift with the ruff version.
- [x] **Working environment** — `.venv` created, `pip install -e ".[dev]"` succeeded on Python 3.13.7. The console script `docushift` installs and runs.
- [x] **Directory layout** — all 9 subpackages created (`discovery/`, `downloader/`, `extractor/`, `engines/`, `transforms/`, `aem/`, `sync/`, `reporting/`, `utils/`), each a real package with a docstring naming its stage and phase. `config/aem_templates/` populated with Jinja templates for `toc.yml`, `nav.yml`, `meta.yml`, and `index.md`. *(Superseded 2026-09-10: AEM supplied the real artifact list — `nav.yml.j2` is deleted, `meta.yml.j2` becomes `metadata.yml.j2`, and `version.yml.j2` is added. See Phase 6's artifact contract.)*
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

### Phase 3.5: Product Scope Exclusions ✅
**Complete (2026-09-09).** Catalog work, not a pipeline stage, and it had to land **before the first full `catalog fetch`** — the same reason `zip_source` landed early in Phase 3. Once a fetch has populated 250 products and ~1,800 versions, the 61 excluded products are already in the sheet with `convert_eligible=true`, and the exclusion becomes a bulk edit to undo rather than a rule that was there first. Design: `architecture.md` §3.10, `design.md` §3.3.1 and §4. 30 new tests; suite at 327.

- [x] **`config/scope.yaml`** — `out_of_scope:` list of `{slug, display_name, reason}`, seeded with the 61 EBX/Spotfire slugs verified against the live A-to-Z index on 2026-09-09 (61/61 matched, 1:1, all public, 0 ambiguous). `ConfigManager.load_scope()` returns `{slug: reason}`; a duplicate slug is an error, not a silent overwrite.
- [x] **`Product.in_scope: bool = True` + `scope_source`** in `products.csv`, after `slug` and before `custom_override`. Ranked `manual` > `scope_rule` > `default`, resolved exactly the way `family_source` is.
- [x] **Excluded from `product_snapshot` and from the mergeable product fields.** Scope is a local policy call; the docsite has no value to three-way-merge, so there is nothing for a fetch to overwrite and no rule needed to say so.
- [x] **Resolution runs on every product the merge touches, new ones included** (`design.md` §3.3.1) — a product first discovered after the rule is written is excluded on arrival. Step 3 actively resets `scope_rule` → `default`, so deleting a slug from the YAML really does restore the product; `manual` short-circuits ahead of it and is never reset.
- [x] **`iter_versions(eligible_only=True)` skips out-of-scope products whole.** Gated on `eligible_only`, so reporting and inventory paths still see them: an excluded product is absent from the work, never from the books.
- [x] **Reporting** — `catalog fetch` prints the excluded count; `catalog triage` counts scope alongside family provenance; `catalog list --out-of-scope` lists them; `catalog set --in-scope/--out-of-scope` sets `scope_source=manual` for the one-off override.
- [x] **`warnings()`**: a batch tag on a version of an out-of-scope product, and a `scope.yaml` rule matching no product in the catalog. The second is the rename detector — the day a rule stops matching is the day the exclusion stops working, and silence would make that invisible.
- [x] **Tests.** Matching is by exact slug, and the two failure modes are regression cases with names: `tibco-businessconnect-ebxml-protocol` and `tibco-businessconnect-container-edition-ebxml-protocol` must stay in scope (a substring `ebx` rule sweeps both), and the 16 public in-scope `spotfire`-slugged products must survive (a substring `spotfire` rule sweeps all of them), as must `tibco-product-and-service-catalog-powered-by-tibco-ebx`. Plus: `manual` surviving a fetch that would exclude, a slug removed from the YAML returning to scope, a rule matching nothing reported, an excluded product still fully catalogued with all its versions, and `iter_versions` returning it under `eligible_only=False` but not under `True`.

### Phase 3.6: Re-key the Catalog on `slug`

**Planned 2026-09-10, blocking.** The first full `catalog fetch --all` was run on 2026-09-09 and **aborted before writing anything**: the deletion guard refused a merge that would have removed 38 version rows. The guard was right, and its diagnostic ("a version key was mangled") was wrong. The real cause is that **`product_code` is not unique**, and the catalog is normalized on it.

`_derive_code` takes the first segment of `folder_path`, which is correct for the ZIP URL and wrong as an identity: **rebranded products keep both their old and their new docsite entry listed, and both publish into the same folder.** Measured over the crawl (634 products, 4,462 versions, 0 errors — dump at `C:\tmp\crawl_all.json`): **10 codes are shared by 21 products.**

| code | products sharing it |
| :--- | :--- |
| `spotfire` | `spotfire` (1 version), `tibco-spotfire-general` (1), `tibco-spotfire-professional` (19) |
| `loglmi` | `tibco-loglogic` (1), `tibco-loglogic-log-management-intelligence` (20) |
| `clarity-dt` | `tibco-clarity` (14), `tibco-clarity-enterprise-edition` (4) |
| `stat-ext` | `spotfire-statistica-integration` (4), `tibco-data-science-for-tibco-spotfire-analyst` (6) |
| `stat-sts` | `spotfire-service-for-statistica` (4), `tibco-data-science-service-for-tibco-spotfire` (5) |
| `sfire-cloud` | `tibco-cloud-spotfire-14-6-0` (1), `tibco-cloud-spotfire-14-6-2` (1) |
| `sfire-dscpn` | `tibco-data-science-package-for-notebooks` (2), `tibco-spotfire-data-science-package-for-notebooks` (2) |
| `fsi` | `tibco-fulfillment-subscriber-inventory` (3), `tibco-product-and-service-inventory-2-1-0` (1) |
| `bwpluginedi-healthcare` | `…-plug-in-for-edi` (2), `…-plug-in-for-edi-healthcare-edition` (1) |
| `business-studio-analyst-edition` | `tibco-business-studio-analyst-edition` (4), `tibco-business-studio-for-analysts` (3) |

**The abort is the mild symptom.** The merge loop inserts the first product under the code, merges the second *into* it, and then reads every version unique to the first as deleted. But if the guard is bypassed with `--allow-deletes`, the two products become one row carrying **one** slug — and `_resolve_scope` matches on slug. **`stat-sts` is exactly that case**: `spotfire-service-for-statistica` is on the exclusion list and `tibco-data-science-service-for-tibco-spotfire` is not, so depending on merge order either 4 versions convert that never should, or 5 are dropped that should not be. Phase 3.5 is undermined by a bug one layer beneath it.

**The fix, chosen by the user on 2026-09-10: `slug` becomes the catalog key.** It is unique by construction in the source system (634 products, **0 duplicate slugs, 0 nulls**), stable across rebrands, and already what `scope.yaml` matches on — so the catalog key and the scope key stop being two different things that can disagree. `product_code` is kept as a short descriptive column and is **no longer required to be unique**. Rejected alternative: disambiguating the code with a fallback. It is a smaller change, but which product keeps the short code would depend on a tie-break over version counts, and a code that shifts between fetches reads to the snapshot merge as a new product — trading a loud failure for a quiet one.

- [x] **`Product.slug` becomes required** (`str`, not `str | None`) and the identity field; `product_code` stays as a plain column. A product with no slug is a discovery error, not a catalog row.
- [x] **`products.csv` keyed on `slug`; `versions.csv` joins on `slug`.** Column order puts `slug` first. Both files are currently absent, so there is no migration to write and no user edits to preserve — which is the reason this lands now rather than after the first successful fetch.
- [x] **`state.db`: all six primary keys move from `product_code` to `slug`** (`product_snapshot`, `version_snapshot`, per-version status, metadata, and the per-folder engine map). Schema change only; no database exists yet.
- [x] **Paths take the slug** — `extract_path()` → `…/extracted/<slug>/<version>/`, `download_path()` → `…/downloads/<slug>-<version>.zip`, and the §6.1 publishing segment `{locale}-{bu}-{family}/{locale}/<slug>/{doc-class}/{version-dashed}/`. **This is forced, not preferred**: 9 of the 10 colliding codes also share `bu` and `family`, so a code-named directory collides in the workspace *and* in the published tree. The cost is real and should be seen before it ships — slug length is median 39, p90 60, **max 95** (`premium-subscription-for-tibco-businessworks-container-edition-and-plug-ins-for-aws-marketplace`), against short codes like `ems`. Published AEM URLs inherit it.
- [x] **`--product` keeps resolving either spelling.** It already matches slug or code; with codes non-unique, a code that matches several products must list them and ask rather than pick the first.
- [x] **`validate()` gains a duplicate-slug check** on load. The invariant that just broke silently should fail loudly the next time something threatens it.
- [x] **`_derive_code` is unchanged and keeps its job** — it derives the ZIP-URL folder, which is what it was always right about. What changes is that nothing keys on its answer.
- [x] **Tests.** All 10 collisions become fixtures, `stat-sts` by name as the mixed-scope case (one slug excluded, one not, asserting each resolves independently). Plus: two products sharing a code round-tripping through both CSVs as separate rows; a duplicate slug rejected by `validate()`; `--product` on an ambiguous code; and a re-run of the merge over the full 634-product dump asserting **0 blocked deletions**.
- [x] **Docs in the same commit** — `architecture.md` §3.1/§3.2 (schema and key), §3.10 (scope now matches the key itself), §6.1 (publishing segment); `design.md` §1.5 path derivation, §2.6 code derivation, §3.1 load and join, §12 index; `CONTEXT.md` ledger.
- [x] **One transaction per fetch** (unplanned, found writing the full-dump test). `_record_snapshots` wrapped in a new `StateStore.transaction()`. Recording 634 products and 4,462 versions one `commit()` at a time is ~5,100 fsyncs: the two-merge regression test took **116 s** before and **0.75 s** after. It is also the more correct shape — a merge that dies halfway no longer leaves a partial base, every row of which the next fetch would read as an unflagged manual edit.

**Then re-run the fetch.** The crawl half is already proven — 634 products, 4,462 versions, 0 errors, and 60 of the 61 scope rules matched (845 versions belong to excluded products). The one unmatched rule, `tibco-spotfire-for-apple-ipad`, is the rename detector firing on its first real run and is chased separately.

### Phase 3.7: End-of-Support Exclusions

**Complete 2026-09-10.** Support publishes a retirement report, and **a retired version needs no conversion.** Latest drop: `cache/EOS Report-2026-09-10.csv` — 5,948 rows, 528 product names, columns `Product Name, Version, Release Status, Retirement Date, Last Updated On`. Statuses are `Retired` 5,642, `Retirement Announced` 291, `GA` 15. Two rows duplicate a `(name, version)` pair and **0 pairs carry conflicting statuses**, so the report is self-consistent and a plain last-wins read is safe.

Catalog work, not a pipeline stage, and it sits beside Phase 3.5 rather than inside it: scope is a *product*-level standing decision taken locally, retirement is a *version*-level fact reported upstream. Both answer "never convert this", and neither can be expressed as a cleared `convert_eligible` flag, for the same reason (§3.10) — the next fetch defaults new versions to eligible, so policy written as edited rows decays silently.

**Measured against the live catalog (634 products / 4,462 versions, 2026-09-10):**

| | all versions | in-scope **and** eligible |
| :--- | ---: | ---: |
| `Retired` | 1,751 | **128** |
| `Retirement Announced` | 192 | 94 |
| `GA` | 13 | 11 |
| no EOS row at all | 2,506 | 1,284 |
| **total** | **4,462** | **1,517** |

So the rule removes **128 versions from a working set of 1,517**, leaving 1,389. It looks small because it mostly *confirms* work already excluded: 1,560 of the 1,751 retired versions are already `is_archived=true` and `convert_eligible=false`. The value is not the 128 — it is that the exclusion now survives the next fetch instead of being re-enabled by it.

**Three decisions, taken by the user on 2026-09-10:**

1. **Only `Retired` gates conversion.** `Retirement Announced` (94 eligible versions, retiring 2027-04-30 and later) and `GA` still convert. The status is recorded either way, so a later report promotes them with no re-crawl.
2. **Absence means unknown, never retired.** 2,506 versions have no row: 2,050 because the product is absent from the report entirely, and of the remaining 456 the overwhelming majority are *newer* than anything the report lists for that product (`spotfire-data-science-workbench` 14.4.0/14.3.0/14.1.0 against an EOS maximum of 14.2.0). For a covered product absence reads as "not yet retired"; for an uncovered one it means nothing at all. Only an explicit `Retired` row is load-bearing.
3. **Exact-slug matching, plus a reviewed alias file.** The report offers no slug and no code — the display name is the only join key there is.

#### The join, and why it needs a reviewed alias file

`slugify(name)` against the catalog matches **237 of 528** report names exactly. A prefix-tolerant pass (iteratively stripping `tibco-`, `ibi-`, `spotfire-`, `jaspersoft-` from both sides) proposes 20 more with 0 ambiguities, and **271 names match nothing** — those are genuinely absent products, either undocumented on docs.tibco.com or named at a different granularity (EOS `DataSynapse GridServer` against catalog `…-gridserver-manager` and `…-gridserver-logviewer`).

The 20 proposals cannot ship unreviewed. **`Spotfire Analytics` → `tibco-analytics` is wrong**: the report lists 14.0.7–14.8.0 and the catalog holds 7.x and 10.x, **zero shared versions**. It is produced by stripping `spotfire-` from one side and `tibco-` from the other, which is exactly the looseness §3.10 already refused for scope rules.

Version-set overlap is the objective test, and it rejects **6** of the 20 (`Spotfire Analytics`, `Automation Services`, `DecisionSite`, `Developer`, `Miner`, `Operations Analytics`). It proves an alias; it does **not** disprove a match — 13 of the 237 *exact-slug* matches also share no version, and every one of those is plainly the right product whose report and docsite simply list different releases. The asymmetry is what makes the rule safe: since a version with no EOS row is never retired, **a zero-overlap alias changes nothing today**, so writing one is unverifiable speculation rather than a conservative default. Seed the file with the 14 provable aliases only; the totals are identical either way (1,751 / 128), because the 6 rejects contribute no rows by construction.

Rejected alternative: automatic fuzzy matching, no file. It covers the same products with no review step, and it is how `Spotfire Analytics` silently retires a live product the day either side gains a version.

#### The 11 products that lose everything

**11 in-scope products lose *every* remaining eligible version (25 versions).** Earlier arithmetic put this at 88, which counted products whose *newest catalog version* is retired; most of those are already archived and ineligible, so they are not a change. Restricted to what is actually in the working set today:

`tibco-auditsafe` (3), `tibco-businessworks-processmonitor` (9), `tibco-data-science-team-studio` (4), `tibco-silver-fabric-enabler-for-tibco-administrator-enterprise-edition` (2), and 7 more at one version each (`…-adapter-for-amdocs-crm`, `…-plug-in-for-twitter`, `…-cobol-copybook-plug-in`, `…-xa-transaction-manager`, `tibco-partnerexpress`, and two further Silver Fabric enablers).

These are fully dead products and dropping them is correct, but a rule that removes a product's entire documentation must say so out loud. **This gets its own report line**, not a warning buried among sixty others — it is the difference between "128 versions excluded" and "128 versions excluded, and 11 products now have nothing to convert".

- [x] **`config/eos/EOS-Report-2026-09-10.csv`** — the report committed under `config/`, not left in the git-ignored `cache/`. It is an input the catalog's contents depend on, exactly as `scope.yaml` is, and the exclusion has to be reproducible from a clean clone. Dated in the filename so the next drop is a *new file* whose effect is a reviewable diff, rather than an in-place overwrite that silently re-decides 128 rows. 445 KB, justified on the same grounds as the committed crawl fixture.
- [x] **`config/eos.yaml`** — the authored half: `report:` naming the active CSV, and `aliases:` as a list of `{report_name, slug, note}`. Seeded with the **14 verified aliases**, with the 6 rejected proposals present as commented-out candidates carrying their overlap figure, so the next reviewer inherits the evidence rather than re-deriving it. `ConfigManager.load_eos()` returns the parsed report indexed as `{slug: {version: (status, retirement_date)}}`; a duplicate `report_name`, an alias to an unknown slug, or a missing report file is an error, not a silent skip — the same contract `load_scope()` has.
- [x] **`ReleaseStatus`** StrEnum (`retired`, `retirement-announced`, `ga`, `unknown`) and **`ReleaseStatusSource`** (`manual` > `eos_report` > `unknown`). `CONVERTIBLE`-style set is unnecessary: exactly one value gates, and naming it in one predicate beats a frozenset of three.
- [x] **`ProductVersion.release_status`, `.retirement_date`, `.release_status_source`**, and the matching `versions.csv` columns placed immediately after `release_date` — GA date, retirement date and status read as one group. Un-prefixed, like `in_scope`/`scope_source` and unlike `_has_csh`: the leading underscore marks columns the tool owns outright, and these are hand-overridable.
- [x] **Excluded from `version_snapshot` and from `_MERGEABLE_VERSION_FIELDS`**, structurally rather than by rule — the docsite has no release-status value to three-way-merge against, so there is nothing for a fetch to overwrite.
- [x] **`_resolve_release_status()`, applied to every version the merge touches**, mirroring `_resolve_scope` (`design.md` §3.3.1) and ranked identically: `manual` short-circuits; a report hit sets status, date and `eos_report`; anything else **actively resets to `unknown`**, so removing an alias or shipping a corrected report really does restore the version. New versions included, so a release discovered after the report lands is classified on arrival.
- [x] **Version matching is exact string equality, with no normalization.** Trailing-`.0` coercion turned out to resolve exactly **one** of the 456 version-level misses, and any numeric coercion reintroduces the `1.10` → `1.1` hazard `csvio` exists to prevent (Phase 2). Unmatched versions are counted and reported, never guessed at.
- [x] **Normalize `Retirement Date` to ISO on read.** The report writes `MM-DD-YYYY` (`12-31-2025`); 2,782 of the retired rows carry one and the rest are blank. Verify `csvio`'s permissive date parsing handles the US ordering rather than assuming it — `01-15-2009` is unambiguous but `03-04-2021` is not, and getting it wrong is silent.
- [x] **The gate: `iter_versions(eligible_only=True)` skips `release_status=retired`.** It becomes the middle of four, composing outside in — scope (product policy) → retirement (upstream fact) → `convert_eligible` (local version policy) → `convert_batch` (scheduling). Conditioned on `eligible_only` for the §3.10 reason: a retired version is absent from the *work*, never from the *books*.
- [x] **`docushift catalog eos`** — re-resolve the status columns from the current report against the existing catalog and write the CSVs, without a fetch. A new report must not cost an hour-long crawl to apply.
- [x] **Reporting.** `catalog fetch` and `catalog eos` print the retired count **and the list of products left with nothing to convert**; `catalog triage` counts by release status beside family and scope provenance; `catalog list --retired`; `catalog set --release-status <value>` records `release_status_source=manual` for the one-off override.
- [x] **`warnings()`**: an alias whose `report_name` is absent from the active report (the rename detector, matching the unmatched-scope-rule warning); a retired version carrying a `convert_batch` tag, worded to distinguish a report verdict from a hand-set one exactly as the scope warning does. Both advisory, neither blocking.
- [x] **Tests.** The two regressions with names: `Spotfire Analytics` must **not** resolve to `tibco-analytics`, and `EBX` → `tibco-ebx` must (49 of 55 versions shared). Plus: `Retired` excluded and `Retirement Announced` / `GA` / no-row all still eligible; a version absent from the report on a product that *is* covered staying eligible; `release_status_source=manual` surviving a fetch that would retire it; an alias removed from the YAML restoring the version; a duplicate `report_name` rejected; an alias to an unknown slug rejected; `MM-DD-YYYY` round-tripping to ISO; a version string that must not be coerced (`1.10`); and the count assertion over the full 634-product dump — 128 eligible versions retired, 11 products emptied.
- [x] **Docs in the same commit** — `architecture.md` a new §3.11 for the report and the four-gate composition, with §3.7's gate list updated; `design.md` §1.1 (the status is not a key), a resolution section beside §3.3.1, and the §12 index; `user-guide.md` the new columns, `catalog eos`, and `--release-status`; `CONTEXT.md` ledger.

**Landed as measured.** `catalog eos` against the real catalog on 2026-09-10 retired exactly **128 in-scope eligible versions** across **11 emptied products**, with the report covering **251 of 634** catalogued products and **0 stale aliases**. 404 tests pass (55 new), lint clean. Two figures in the survey above were re-measured after the alias set was finalized and are corrected in place: absence-by-missing-product is 2,050 not 2,004, and trailing-`.0` coercion would have resolved 1 version rather than 14 — which strengthens the case for exact matching rather than weakening it.

**Not in this phase.** The 277 unmatched report names are left unmatched and unreported-on beyond a count — chasing them means deciding what `DataSynapse GridServer` maps to when the catalog splits it in two, which is product-knowledge work, not tool work. The report also carries `Last Updated On`, which nothing reads; it stays in the file and out of the model.

### Phase 3.8: Publishing-Name Rework — `-userdocs` Repositories

**Status: COMPLETE (2026-09-10).** The destination naming was corrected by the doc-platform owners. Everything below is a rename of *names*, not of *shapes*: the inner path `{locale}/{product}/{doc-class}/{version-dashed}` is unchanged, doc-class routing is unchanged, and the two-tree split is unchanged. It lands before Phase 4 because `family_dir` is the path contract Phase 4's downloader writes into, and renaming it after packages are on disk means a migration rather than an edit.

#### What changed

| | Old | New |
| :--- | :--- | :--- |
| Docs tree (English) | `en-us-tibco-messaging` | `en-us-tib-messaging-userdocs` |
| Docs tree (localized) | `ja-jp-tibco-messaging` | `loc-tib-messaging-userdocs` — **one tree for all non-English locales** |
| Resources tree | `en-us-tibco-messaging-resources` | `en-us-tib-messaging-userdocs-resources` — **English only** |
| Locale token | `en-us` (language-region) | **unchanged** — `en-us`, in the tree name *and* the inner segment |
| BU / family token | taxonomy key verbatim (`tibco`) | new `repo_slug` from `taxonomy.yaml` (`tib`) |

**The locale token flipped twice and landed where it started** (AEM, 2026-09-10). It was briefly specified as region-language (`us-en`) and is now confirmed as **language-region — `en-us` — in both the tree name and the inner segment**, which is what the codebase already does. `DEFAULT_LOCALE` therefore does not change, and the only surviving locale change in this rework is the `loc-` tree. Localized content gets **no** `-resources` sibling: API references and archives are English-only.

> **One example in the AEM note contradicts its own rule and is unresolved.** The rule is language-region, but the localized folders are given as `/jp-ja` and `/fr-fr` — `jp-ja` is *region*-language; language-region for Japanese is `ja-jp`. `fr-fr` is identical either way, so Japanese is the only observed case that distinguishes them. **This blocks nothing**: no mapping table exists (see below), so a locale folder is literally the locale string a run is given, and the question is which string to pass when localized migration starts. It is recorded here rather than guessed at, and English — the only locale in scope — is unaffected.

#### Decisions taken here

- **`repo_slug`, not a rename of the taxonomy.** `taxonomy.yaml` gains an optional `repo_slug` on each business unit and each family; `tibco` gets `tib`, everything else defaults to `slugify(key)` when the field is absent. Family keys, `products.csv` classification and the keyword rules are untouched — the short token is a *publishing* concern and does not get to reshape the catalog. The example that prompted this (`en-us-tib-bwplugins-userdocs`) implies a `bwplugins` family that does not exist yet; adding it is ordinary taxonomy triage, not part of this rework.
- **No locale mapping table; the locale string is used verbatim.** `DEFAULT_LOCALE` stays `en-us`. A table would have to be maintained for every locale the docsite might one day serve, and its only content is the value the caller already has. This is also what makes the `jp-ja` / `ja-jp` ambiguity above cheap: the folder name is the string that was passed in, so settling it later costs a config value, not a rename of a naming layer. If the docsite's own locale codes turn out to differ from AEM's, that mapping belongs at the discovery boundary where the codes are read.
- **The workspace folder keeps its shape but loses the repo identity**: `families/en-us-tib-messaging/` — new tokens, no `-userdocs` suffix. The old rule "the workspace folder *is* the repo name, so hand-off is a copy" is dead on arrival now that one family maps to two or three trees; there is no single repo name left to match. Keeping the locale prefix is still right — localized packages are different ZIPs and must not land on top of English ones. The Stage 7 hand-off becomes a copy *plus a name*, which is what `sync --target-dir` already computes.
- **`loc-` is derived, not configured.** A locale other than `en-us` selects the `loc-` docs tree and suppresses the resources tree. One predicate, in one place, so the two rules cannot disagree.
- **The `userdocs` suffix is a config value, not a literal** (decided 2026-09-10). `-docs` was proposed as the alternative. `userdocs` is kept as the default because it names the *audience*, and that is the distinction this pipeline is built on: Javadoc and the C / Go / `tibdg` trees are documentation too, which is why they route to a separate tree — a suffix meaning "documentation" cannot separate them, and `<product>-docs` is also what an engineering team names a README site sitting in the same org. `*-userdocs` therefore enumerates exactly the published docs trees and nothing else. The known cost is four characters on every published URL, on names that already carry a median-39 / max-95 product slug (§Phase 3.6). Holding the value in config is what makes that cost reversible: until the first publish it is a one-line edit, and the `-resources` name derives from the same string rather than being a second literal that can drift out of step.
  **Single token, not `-user-docs`.** Every other segment is hyphen-separated, so a two-word suffix makes the family/suffix boundary unparseable. Validation enforces it.

#### Work items

- [x] **New `config/publishing.yaml`, born here rather than in Phase 6.** It holds the naming tokens only — `docs_suffix: userdocs`, `resources_suffix: resources`, `localized_prefix: loc`, `primary_locale: en-us`. Phase 6 later adds `publish_base_url` and the doc-class-to-repo map to the same file (see that phase's item, which no longer creates it). The file arrives now because the tree names are computed now; deferring it would mean shipping the literal this decision exists to avoid.
- [x] **`utils/slug.py`** — retire `family_folder(locale, bu, family)` and replace it with four functions over the `repo_slug` tokens: `family_workspace_folder(locale, bu, family)` → `en-us-tib-messaging`; `docs_tree_name(locale, bu, family, *, suffix, localized_prefix)` → `en-us-tib-messaging-userdocs` or `loc-tib-messaging-userdocs`; `resources_tree_name(...)` → the `-userdocs-resources` name, **raising** for a non-English locale rather than returning a name nobody will publish; and `is_primary_locale(locale, primary)`. The suffixes arrive as arguments, never read from disk here: `slug.py` stays the sole owner of the name's **shape** and `publishing.yaml` becomes the sole owner of its **tokens**, which is the same split that already keeps `taxonomy.yaml` and `slug.py` from drifting. The empty-component guard carries over unchanged — it is the reason `en-us-tibco-` never got created, and `en-us-tib--userdocs` is the same bug with a longer name.
- [x] **`config/taxonomy.yaml`** — `repo_slug: tib` on the `tibco` BU; `repo_slug` on each of the 9 declared families where it differs from the key. `ibi` keeps `ibi`.
- [x] **`ConfigManager`** — `DEFAULT_LOCALE` stays `en-us` (the region-language flip was reverted); `family_folder_name` renamed to `family_workspace_name` and re-pointed; new `docs_tree_name` / `resources_tree_name` accessors that resolve `repo_slug` from the taxonomy **and the suffixes from `publishing.yaml`** before delegating to `slug.py`. `load_publishing()` follows the established cache-and-default pattern of `load_docsite()`, so a missing or partial file falls back to the documented defaults rather than failing a run that has not reached publishing yet. `repo_slug` resolution goes through `families()` / the BU accessor so an auto-registered family still names a folder (§Phase 2's warn-don't-reject rule).
- [x] **`validate()`** — two new blocking errors, both for the same reason: they publish two things into one repository, silently.
  - A duplicate `repo_slug` within a BU — exactly as the `product_code` collision would have (Phase 3.6). The one new failure mode the rework introduces.
  - A `docs_suffix` or `resources_suffix` that is not a single lowercase token — a hyphen in the suffix makes the family/suffix boundary unparseable, and an empty one silently produces the bare workspace name as a tree name.
- [x] **`catalog.py:930`** — the auto-registration warning names the new workspace folder.
- [x] **`cli.py`** — the `download` docstring and the `status` locale line.
- [x] **Tests** — `test_slug.py` and `test_config.py` re-expressed against the new names; new cases for the `loc-` tree, for `resources_tree_name` refusing a non-`en-us` locale, and for the two new validation errors. **One test sets `docs_suffix: docs` and asserts the whole family of names moves together** — docs tree, `loc-` tree and resources tree — which is the only thing that actually proves the value is reversible rather than merely stored in a file. `test_catalog.py:1381` and `test_cli.py:781` carry hardcoded folder names and follow.
- [x] **Docs in the same commit** — `architecture.md` §4.1 (workspace name and its rationale, which is the paragraph that changes most), §6.1 (the layout block and the sync-target template), §6.3–6.4 (the `-resources` name and the absolute-URL template), and the Stage 1 diagram at line 32; `design.md` §82, §758, §831; `user-guide.md` §365–382, the §499 layout block, and `publishing.yaml` in the config reference; `CONTEXT.md` tree at line 91 and a new ledger row recording both the rename and the `-userdocs` / `-docs` choice. Every literal `en-us-tibco-…` in prose is an example that now misleads.

**Landed as specified, with three notes.** 425 tests pass (21 new), lint clean.

- **`docs_tree_name` takes `primary_locale` as well.** The signature in the work item above omitted it, but the `loc-` branch cannot be decided without it and `slug.py` is not allowed to read config. All three tokens arrive as keyword arguments.
- **No family declares a `repo_slug`.** All 9 slugify onto themselves, so the field is documented in `taxonomy.yaml` and used by `tibco` -> `tib` alone. Adding one later is a one-line edit, and `test_config.py` exercises the family-level path against a fixture taxonomy so the code path is not untested merely because the shipped config does not need it.
- **The locale line lives in `doctor`, not `status`** -- `status` is a Phase 7 stub. `doctor` now prints the tree the current locale publishes to, and names the missing `-resources` tree for a localized run; `publishing.yaml` joins its artifact table.

Two things beyond the plan, both small: `ConfigManager.publishes_resources()`, so Stage 7 asks one question instead of re-deriving the predicate; and `publishing_problems()` living on `ConfigManager` with `CatalogManager.validate()` calling it, since the checks read config rather than CSVs and `validate()` is the gate that has to block on them.

#### Deliberately not in this rework

- **No `bwplugins` family.** Adding it re-cuts `integration` and reclassifies `products.csv` rows — product-knowledge work with its own review.
- **No locale mapping table**, per the decision above.
- **No migration of existing `families/` folders.** Nothing is downloaded yet (Phase 4 is unbuilt), so there is nothing on disk to rename. If that stops being true before this lands, the rename is a `git mv`-equivalent one-liner, not a code path worth keeping.

### Phase 4: Package Downloader & Extractor
The selection model and the on-disk layout this phase writes into are settled and tested (`architecture.md` §3.7 and §4). **Stage 4 is complete**: 4a (acquisition) on 2026-09-10, 4b-1 (extract and identify) and 4b-2 (measure) on 2026-09-11.

> **Sequencing note (2026-09-03).** The two `[x]` items below landed ahead of Phase 3. They are design decisions — a CSV column and a path contract — with no network dependency, and they were settled while answering how partial conversions and the families folder should work. Implementation order then returned to Phase 3, which is now complete; this phase is next.

- [x] **Selection model**: `convert_eligible` (policy) + `convert_batch` (scheduling), composed by `CatalogManager.iter_versions(batch=…, eligible_only=True)`. `--batch` is a selector on every stage command.
- [x] **Families workspace path contract** owned by `ConfigManager`: `family_dir`, `downloads_dir`, `extracted_dir`, `archive_dir`, `download_path`, `extract_path`, over `families/{locale}-{bu}-{family}/`.
> **Split into 4a and 4b (2026-09-10, user decision).** The phase holds two bodies of work that share nothing but a directory: acquiring bytes, and walking what is inside them. They are sequenced — 4b needs packages on disk — and 4a is reviewable on its own, so they land as two commits rather than one. 4b's items are unchanged below; only the heading is new.

#### Phase 4a: Acquisition I/O

Everything here ends with a ZIP at a path `ConfigManager` already computes. **No stage after this may accept a path from a caller** — the location is derived from `(bu, family, slug, version)` or it is wrong (`design.md` §5.1 step 1).

- [x] **`utils/http.py` — one session builder, two callers.** `DocsiteClient._build_session` is lifted out verbatim and parameterized on `Accept`, because the downloader needs the same `Retry` policy, the same `User-Agent` and the same `docsite.yaml` provenance while asking for `application/octet-stream` rather than JSON. A second copy of the retry configuration is how the crawler and the downloader end up disagreeing about what a 429 means. The shared `Throttle` moves here too — `DocsiteClient` keeps its behaviour and loses its private copy.
- [x] **`downloader/fetcher.py`** — `PackageDownloader`, implementing `design.md` §5.1 step by step. The seven rules that carry the correctness, each worth a test:
  - [x] **`zip_source=manual` short-circuits before anything else.** The package is already at the path; fetching would overwrite a hand-obtained file with whatever the stale URL now serves.
  - [x] **A present file with a matching recorded checksum is `DOWNLOADED` and returns.** This is what makes re-running a completed batch cheap, and it is the only thing standing between a resumed 1,500-version run and a full re-fetch.
  - [x] **Resume by `Range`, but only against a matching validator.** The partial lives at `<target>.part`; the recorded `zip_etag` (or last-modified) must still match before a byte is appended. A changed validator discards the partial and restarts — resuming across a changed file yields a corrupt archive that passes every length check there is.
  - [x] **sha256 is computed while writing**, not in a second pass. These are 100 MB–900 MB files.
  - [x] **`zipfile.is_zipfile` before the move.** The common real failure is an HTML error page served as 200 under a `.zip` name, and catching it here is a one-line message instead of a baffling Stage 4 failure.
  - [x] **`os.replace` into place**, so a killed run never leaves a truncated file at the canonical path where step 2 would later trust it.
  - [x] **On failure: status `ERROR` with the message, and the `.part` file is left alone** for the next resume. Deleting it turns a transient 503 into a re-download.
- [x] **Concurrency: `ThreadPoolExecutor` over versions, default width from `docsite.yaml`'s existing `crawl.max_concurrent_requests: 4`**, overridable with `--workers` (decided 2026-09-10; the alternative considered was `asyncio`+`httpx`). Streaming a ZIP to disk is I/O-bound, so threads cost nothing and the resume logic stays ordinary synchronous code with no async boundary anywhere else in the codebase to justify it. **The rate-limit floor is shared, not per worker** (`design.md` §2.1) — one `Throttle` instance behind a lock, and it governs *request initiation* only, since a transfer that runs for two minutes is not four requests a second by any reading. Reusing the value `docsite.yaml` already carries keeps politeness a config edit, which is the rule §2 exists to state.
- [x] **`state.db` per version**, all columns already present: `download_path`, `checksum`, `zip_etag`, `zip_size`, `status`, `error`. **The `--from-file` origin path goes to `version_metadata` under `zip_origin_path`**, not to a new column — it is audit detail for one row rather than a field every version has, and `version_metadata` is exactly the free-form store that exists so a fact like this costs no `SCHEMA_VERSION` bump.
- [x] **`ConfigManager.archive_path(bu, family, slug, version)`** — `families/<family>/archive/<slug>-<version>.zip`, for symmetry with `download_path()`.
- [x] **`CatalogManager.add_version(slug, version, …)`** — new, and needed only by `--from-file`: there is currently no way to create a version row outside a merge. Returns the row and a warning; refuses an unknown *product*.
- [x] **`extractor/safe_unzip.py`, landing in 4a rather than 4b.** `archive download --extract` needs it, and it is the one piece of extraction that is a safety rule rather than an inventory walk: **refuse any member whose resolved path escapes the target directory, and any absolute member path** (`design.md` §6.1 step 2). It lands early for the same reason `zip_source` landed in Phase 3 — the rule has to exist before the first thing that could violate it runs. 4b consumes it unchanged.
- [x] **`docushift download`** — wired to `iter_versions(eligible_only=True)` over the `_scope_options` selectors already declared. `--force` re-fetches a current file; `--workers N`; `--dry-run` prints the selection and writes nothing. A row that is eligible with no `zip_url` and no manual pin is a **report line, not an abort** — one unreachable product must not stop a 200-version batch. Summary table at the end: downloaded, already current, skipped (manual), failed.
- [x] **`docushift download --product X --version Y --from-file <zip>`** (`architecture.md` §3.8, `design.md` §5.2) — requires *both* selectors; validates with `zipfile.is_zipfile` **before** copying; **copies, never moves** (the user's own copy is not the tool's to consume); sets `zip_source=manual`; records sha256, size, status `DOWNLOADED` and `zip_origin_path`. Unknown *version* on a known product is auto-added with a warning (the user is holding a real package, which is stronger evidence than discovery's silence); unknown *product* is an error, because a typo'd code would seed a junk row nothing can distinguish later.
- [x] **`docushift archive download`** — the on-demand escape hatch for a single archived ZIP, into `families/<family>/archive/`, outside the pipeline's working set. Requires `--product` and `--version`; takes the archive `zip_url` verbatim (never templated — archived `folder_path` values are stale, §2.8); `--from-file` files a hand-obtained ZIP at `archive_path()` instead; `--extract` unpacks **within `archive/`**, never into `extracted/`.
- [x] **`warnings()` gains the last §3.8 check**, now that there is a workspace to look at: a `zip_source=manual` row whose expected file is absent **when the family directory exists locally**. The guard is the point — `families/` is git-ignored, so an unconditional check calls every manual row broken on a fresh clone, which is the exact failure §3.8 rejected filesystem-based provenance to avoid.
- [x] **Tests** — `tests/unit/test_downloader.py`, offline against a fake session, following the 38 discovery tests' pattern; ZIP fixtures built in-process rather than committed. Cases that pin the rules above: a manual row is never fetched; a matching checksum short-circuits; a resume appends against a matching etag and **restarts against a changed one**; a truncated transfer leaves a `.part` and no canonical file; an HTML error page under a `.zip` name is rejected before the move; a `../` member is refused by `safe_unzip`; `--from-file` copies rather than moves and leaves the source in place; `--from-file` on an unknown version adds the row and warns; on an unknown product it errors. Plus `test_config.py` for `archive_path()` and `test_catalog.py` for `add_version` and the new warning.
- [x] **Docs in the same commit** — `design.md` §5.1/§5.2 flip **Specified → Built** with the concurrency "Open" resolved, and their rows in the §12 index; `architecture.md` §3.8's `state.db` row names `zip_origin_path`; `user-guide.md`'s `download` and `archive` sections gain `--workers` / `--dry-run` / `--from-file`; `CONTEXT.md` status line and a ledger row for the concurrency decision and the 4a/4b split.

**Landed as specified** (2026-09-10), 465 tests passing (was 425). Two things the plan did not anticipate. `state.db`'s single SQLite connection was pinned to its creating thread, so the second version of every parallel run raised `SQLite objects created in a thread can only be used in that same thread` — the connection is now opened `check_same_thread=False` with a lock around the write path, which is a `state.py` change the pool forced and which has its own regression test. And the throttle now paces request *starts* rather than returns, because the old "since the previous request returned" reading would have had a 900 MB transfer hold the gate for its whole duration and collapse the pool back into one stream; `design.md` §2.1 was corrected to match.

**Deliberately not in 4a.** No `extract` command (4b). No disk-space preflight — the failure mode is a clear `OSError` at write time and a budget check would need a `Content-Length` for every selected version, which is 1,500 extra requests to answer a question `df` already answers. No mirror or proxy support.

#### Phase 4b: Extraction & Inventory

> **Split again into 4b-1 and 4b-2 (2026-09-11, user decision), and engine detection moves here from Phase 5.** Two dependencies the original checklist did not account for. §6.4's asset **destinations** ("inside an engine output root / under an API-reference root / unclaimed") and §6.2's **per-doc-set** CSH inventory both need the engine and its output roots — and `user-guide.md` has always said `docushift extract` detects engines, so `design.md` §7 was filed under the wrong phase rather than scheduled late. Meanwhile §6.3 and §6.4 both insist the API partition and the asset inventory happen in **one walk**, "so both describe one moment", which forbids splitting *those* across commits. The cut that satisfies both: **4b-1 unpacks and identifies** (extraction, detection, root location), **4b-2 measures** (the single walk, CSH, assets, the five columns). §7 keeps its section number and every measured figure in it; only its phase attribution changes.

##### Phase 4b-1: Extract & Identify

Ends with a package unpacked at `extract_path()`, its engine written back to `versions.csv`, and its output roots recorded — the three facts 4b-2's walk needs before it can classify anything.

- [x] **`extractor/unpacker.py`** — `PackageExtractor`, shaped like `PackageDownloader` deliberately: the same selection (`iter_versions(eligible_only=True)`, so an archived version is never unpacked), the same "**a failure is a returned outcome, never an exception**" rule, and the same five-count summary. Outcomes: extracted, already current, no package on disk, refused, failed.
  - [x] **Unpack through 4a's `safe_unzip`**, unchanged. This is the whole reason it landed early.
  - [x] **Extract to `<extract_path>.part/`, then swap.** A re-extract over a live directory leaves files from the *previous* package behind — a guide deleted upstream would survive forever and convert. The old tree is removed only once the new one is complete. Not atomic on Windows (a directory `os.replace` onto an existing target fails), so the sequence is build → remove old → rename, and the docs say that rather than implying a guarantee that is not there.
  - [x] **Skip a package already extracted from the same bytes.** The ZIP's sha256 at extract time goes to `version_metadata` under `extract_zip_checksum`; a re-run whose ZIP still hashes the same and whose tree still exists is `CURRENT` and does no work. `--force` overrides. Same mechanism as 4a's `zip_origin_path` and for the same reason — detail for the rows that have it, so no `SCHEMA_VERSION` bump.
  - [x] **Serial, not pooled — and stated, not defaulted into.** 4a's pool exists because HTTP transfers overlap; two 900 MB unzips onto one disk contend rather than overlap, and a pool would buy that contention plus a second answer to "how wide". Revisit only with a measurement.
  - [x] Record `extract_path` and status `EXTRACTED` per version in `state.db`. **A failed extract leaves the inventory columns blank** rather than zero — the catalog half already enforces it, and a failed run must not look like an empty package.
- [x] **`engines/detector.py`** — `design.md` §7, three passes, moved here from Phase 5 (it runs at extract time and always did).
  - [x] **Pass 1, layout markers**, from the §7.1 table: Flare `*.mcwebhelp` / `*.mclog` / `MicroContent/` / `_globalpages/` / `csh.js`; WebWorks `wwhelp/` / `wwhdata/`; DITA `GUID-*.html` or `static/head.js` + `static/body.js`; R help `snext.css` / `snextchm.css`. **Not `Skins/` or `Data/`** — 91.4% and 88.0% precise, all 94 corpus false positives come from those two and no other, and dropping them costs zero recall (`*.mcwebhelp` alone finds all 595). **Flare wins the 19 Flare+WebWorks bundles**; the per-folder map is what keeps that ambiguity visible instead of flattening it.
  - [x] **Passes 2 and 3 read content, and are bounded.** They run only where pass 1 found nothing, since that is the population they exist for — DocBook has no layout marker at all, and the pass-3 long tail is 19 versions. Bound: the first 8 KB of at most 200 HTML files per version, breadth-first. `<head>`, the generator comment and the `MadCap:` / `DC.*` markers all sit in that window, and an unbounded scan over a 400,000-file corpus is a different program. **The bound is a stated limit, so a version that exhausted it without matching is a report line rather than a silent `auto`.**
  - [x] **Never guess, never override a manual value, record the raw string.** No match stays `auto`; `record_detected_engine` already refuses an `engine_source=manual` row; an unrecognised `<meta name="generator">` becomes `other` with its raw value in `version_metadata` under `engine_generator_raw`, because `other` on its own is unactionable.
  - [x] **The per-guide-folder map** into `state.db`'s existing `engine_folder_map` — pass 1 re-run per top-level folder of the extracted tree. One version's ZIP commonly bundles nine sibling guide folders of a single Flare output; the map costs almost nothing and is the only thing that would surface a genuinely mixed bundle rather than flattening it into one CSV cell. Three are already known by name (`amx-bpm/4.2.0`, `amx-bpm/4.3.0`, `businessworks_plugin_mobile_integration/2.0.0-november-2013`).
- [x] **`engines/roots.py` — output-root location, per engine, by content and never by a configured path.** It lives in `engines/` rather than `extractor/` because it is engine-specific knowledge and Phase 5's converters locate their units of work with it — `architecture.md` §5.1.1 is explicit that root detection is a separate step from engine detection. One function, one answer, two callers.
  - [x] Flare: a directory holding `Data/HelpSystem.xml`. **The walk descends into nested roots and the innermost root owns a file** — 153 nested roots hold 22,456 files, so stopping at the first match drops them and not stopping converts them twice (`architecture.md` §5.1.1, §5.1.3).
  - [x] DITA: a directory holding `GUID-*.html`. Not at a fixed depth — `html` 201, `doc/html` 102, `html_v3` 16, `en-US` 10 (`architecture.md` §5.2.1).
  - [x] WebWorks: a directory holding `wwhdata/` — **195 of 195 versions, zero false positives and zero false negatives**, where `wwhelp/` misses the 17 books stripped to `wwhdata/files.htm` (`architecture.md` §5.3.2).
  - [x] Recorded per version in `version_metadata` under `output_roots`, relative to the extract path, so 4b-2 and Phase 5 read one recorded answer instead of each re-deriving it.
- [x] **`docushift extract`** — the same `_scope_options` selectors as `download`, plus `--force` and `--dry-run`. Report: the five outcomes; an engine tally; and **two named lists, not counts** — versions left `auto` (a detector bug worth investigating) and versions whose engine is identified but outside `CONVERTIBLE_ENGINES` (a scoping decision for a human). §7.3 turns on those being different facts, so they do not share a line.
- [x] **Tests** — `tests/unit/test_extractor.py`, offline, with extracted trees built in-process. The regression the survey paid for: **a WebWorks fixture that ships a `Skins/` directory must not detect as Flare.** Plus a Flare+WebWorks bundle resolving to Flare with both in the folder map; nested Flare roots yielding outer *and* inner; a DITA doc-set found at `doc/html` rather than a fixed depth; a WebWorks book carrying only `wwhdata/files.htm`; a re-extract removing a file the new package no longer ships; an unchanged ZIP short-circuiting and `--force` overriding it; a failed extract leaving the inventory columns blank; and `engine_source=manual` surviving a detection that disagrees.
- [x] **Docs in the same commit** — `design.md` §6.1 steps 1-3 and §7 flip **Specified → Built** with their §12 index rows, and §7's phase attribution changes from Phase 5 to 4b; `planning.md` Phase 5's detector block moves here; `user-guide.md`'s extract section; `CONTEXT.md` status, tree, and a ledger row for the 4b split and the §7 move.

**Deliberately not in 4b-1.** No inventory walk, no CSH, no assets, no five-column write-back — all 4b-2, and all one walk. No conversion. No disk-space preflight, for the reason 4a had none.

**Landed as specified** (2026-09-11), 521 tests passing (was 465). Three things the checklist did not anticipate, all small:

- **`refused` is its own outcome**, not a kind of `failed`. The five became extracted / current / no-package / **refused** / failed once the code existed: an archive that escapes its target directory is a statement about the *package* — a retry will not fix it and somebody has to open the ZIP — while a failed extract is a statement about this run. Summing them gives a number nobody can act on.
- **A pinned engine outranks the detector in the *report*, not just in the write-back.** `record_detected_engine` already refused to overwrite `engine_source=manual`, but the run was still reporting, and locating output roots for, the engine it had just detected rather than the one conversion will use. `ExtractResult.engine` is now the effective engine and `engine_written` says whether anything was recorded.
- **Refusing to write `auto` is the other half of "never guess".** §7.3 step 1 says an undetected version stays `auto`; the consequence nobody had written down is that a *later* failed detection must not clear an engine an earlier run got right. Covered by `test_a_failed_detection_does_not_clear_an_earlier_answer`.

`design.md` §7 moved from Phase 5 to 4b-1 with its section number and every measured figure unchanged, as agreed.

##### Phase 4b-2: Measure

Everything below happens in **one walk** of the extracted tree, per `design.md` §6.3 and §6.4 — the API partition, the asset categories and the destinations describe one moment or they describe nothing.

*(The extraction and `EXTRACTED`-status items that stood here moved up to 4b-1, where the code is.)*

**One walk, and it is `extractor/inventory.py`.** A single `os.scandir` descent of the extracted tree produces all of it: the API partition, the asset categories and destinations, and the *locations* of the CSH sources. Parsing the CSH sources happens after the walk, off the paths it collected, because a parse is not a traversal and interleaving them would make the walk's cost depend on how much help a product ships. Directories are not counted, symlinks are not followed (`follow_symlinks=False` on every test — §6.3's rule, and §6.1 already refuses escaping members).

- [x] **`apiref.py` — the predicate, at the top level beside `models.py` because it belongs to no single stage.** Stage 4 counts with it, Stage 5 skips with it, Stage 7 routes with it (`design.md` §6.3, §6.3.1); putting it under `extractor/` would have two later stages importing from the stage that happens to have needed it first.
  - [x] `find_api_roots(tree)` — a directory is a root if it holds a §6.3.1 Finding 5 marker: Javadoc `allclasses-frame.html` / `package-frame.html` / `index-all.html` / `class-use/`, Doxygen `annotated.html` / `*_8h.html`, JSDoc `styles/jsdoc-default.css`, godoc `lib/godoc/godocs.js`, Sandcastle `fti/FTI_*.json`. **The outermost match wins and the descent stops there** — a Javadoc tree inside a Doxygen tree is one artefact, and the nested `javascript/` JSDoc tree under `api-reference/` must count once (Finding 4).
  - [x] `is_api_reference(path, roots)` — pure, no I/O, so the three callers pass roots they already hold rather than each re-walking. Roots go to `version_metadata` under `api_roots`, the way 4b-1 recorded `output_roots`, for exactly that reason.
  - [x] `looks_like_api_name(segment)` — the **only** place a name is consulted, and only to raise the triage flag. **Whole segments, case-insensitively** (Finding 3: `API`/`api`, `C`/`c`, `JavaDoc`/`javadoc`, `Java_API`); never a substring, which is how the predecessor matched 186,856 files on `/c` alone including the WebWorks `ctx/` CSH source (Finding 2).
- [x] **CSH source inventory** — record every located source per `(product, version, doc_set)` in `state.db`: path, format (`flare_alias` \| `dita_head_js` \| `webworks_topics`), raw entry count, parse status. Design in `architecture.md` §5.4.
  - [x] **Located in the one walk, by shape rather than by root.** `Data/Alias.xml`, `static/head.js`, `wwhdata/common/topics.js` — matched on the file *and* its parent directory, at any depth, because 153 Flare alias files sit in a nested output root and a doc-set is not always a top-level folder. The `doc_set` recorded is the owning output root's path relative to the tree (`engines/roots.owning_root`), falling back to the source's own grandparent when no root claims it — which is the 5-in-a-partial-tree and 1-elsewhere case §5.4.1 measured.
  - [x] **The three readers land in `engines/csh.py`**, matching §9.2's split: an engine contributes a reader yielding `(identifier, link, anchor)`, while Phase 5's `transforms/csh.py` adds the schema, resolver and writer on top of them. Flare `Alias.xml` via `ElementTree`, one `Map` per entry keyed on `Name` (`ResolvedId` parsed and discarded, §9.1); DITA `static/head.js` by locating `suitehelp.contexts=` and handing the object to `json.loads`; WebWorks `topics.js` by regex over the `if(P=="<id>")C="<target>";` chain. The fragment split is applied uniformly — 3% of Flare links and 43% of WebWorks ones carry one. **Not** `<doc-set>/ctx/` (redirect stubs generated *from* the map) and **not** `wwhdata/xml/files.xml` (a lossy XML twin, absent from one observed book).
  - [x] Empty, zero-byte, and unparseable sources are **counted and skipped, never raised**, with a parse status of `ok` / `empty` / `unparseable` / `unreadable`. An empty map is the normal case in every format: Flare 476 of 863 (55%), WebWorks 492 of 647 (76%), DITA 38 of 418 (9%). A source that was located but could not be read still counts toward `_has_csh` and produces a triage line (`architecture.md` §5.4.4) — "help we could not read" and "no help" are different facts.
  - [x] `docushift extract` reports the tally (`CSH: 3 source(s), 561 identifier(s).`) so a version with no help map is visible before conversion, not after.
- [x] **Asset inventory, by category and destination** (`architecture.md` §5.5, `design.md` §6.4) — in the *same* walk, so both describe one moment. **Not an extension allow-list**: the corpus holds 100 extensions, and the nine the old plan named (`PDF, Word, Excel, TXT, images, ZIP`) miss 36.2% of its images while naming three that barely exist — `.doc` 0 files, `.docx` 1, `.xls` 3 in 2,204,598.
  - [x] Record counts and bytes per `(version, output_root, category, destination)` in `state.db`: image, media, document, archive, source-format, skin, other.
  - [x] **`skin` is a location, not an extension, and §6.4 says otherwise.** Every other category falls out of the extension; skin is decided by the engine's own prefix relative to the output root — Flare `Skins/`, `Resources/Scripts|Stylesheets|MasterPages|TemplateExtensions/`, `Data/`; DITA `static/`, `fonts/`; WebWorks `wwhdata/`, `wwhelp/`, `tpl/` (§5.5.4). It takes precedence over the extension, because a `.gif` in `Skins/` is chrome and not a picture — 48.7% of DITA and 76.2% of WebWorks reference traffic. **Whole segments, never a substring**, the same rule as the API names. `design.md` §6.4's "decided by extension" is corrected in the same commit.
  - [x] Record the **destination** each file has, in this precedence: under an API-reference root → inside an engine output root → directly inside a top-level `pdf/` or `doc/` (§10.4's router) → unclaimed. API wins over output root because generated reference trees sit *inside* one (`api-reference/` under `html/`), and a file counted in both would double the totals.
  - [x] **Report the unclaimed residue by top path segment** in `docushift extract`. 62,525 files across 243 rooted versions currently fall through, nearly all generated reference trees with no marker (`components-api/`, `tib_activespaces_*_api/`, `api/`). This is the same evidence loop as the API-reference triage line.
- [x] **`state.db` gains two tables, and no `SCHEMA_VERSION` bump.** `csh_source(slug, version, path, doc_set, format, entries, status)` and `asset_inventory(slug, version, output_root, category, destination, files, bytes)`, both replaced wholesale per version on each walk so a re-extract cannot accumulate a second copy. The v2 bump existed because a *column* was renamed and `CREATE TABLE IF NOT EXISTS` could not fix an existing file; two new tables are additive and an existing v2 database grows them on open.
- [x] **Extraction inventory columns in `versions.csv`** (`architecture.md` §3.9, `design.md` §6.3) — the five numbers a human needs before setting `convert_eligible` / `convert_batch` on a package nobody has opened. Everything the sheet already carries is discovery-time; none of it says what is *in* the ZIP. **The catalog half has landed; the predicate and the counting walk land with the extractor.**
  - [x] **`is_api_reference()` as a single shared predicate** — consumed here by the count, in Phase 5 by the conversion skip-list, and in Phase 7 by the doc-class router, so a file cannot be counted as documentation and published as an API reference. **A generator marker decides; a directory name never does** (`design.md` §6.3, grounded in a 2,201,528-file survey in §6.3.1). It lands in `apiref.py`, above.
  - [x] **Unmarked-candidate triage in the `extract` report** — a directory whose name looks API-ish but carries no known marker is *reported*, never auto-classified; its files stay in `_doc_files`. This is how the marker list grows from evidence, and why `api-exchange-gateway/` (a product name, 15,677 files) cannot be swept up by a name rule.
  - [x] **The walk runs on a tree this run built, and on a `current` tree whose columns are blank.** An unchanged package is already a no-op (4b-1's `extract_zip_checksum`), but a tree extracted before 4b-2 existed has no inventory at all, and re-running `extract` must fill it rather than report `current` over a blank row. `--force` always re-walks.
  - [x] **Written only on a clean extract.** `record_extract_inventory` refuses nothing, so the caller carries the rule: a `refused`, `failed` or `no-package` version leaves all five blank. A partial walk — an unreadable directory mid-descent — is reported and also leaves them blank, because a footprint measured over part of a tree is a wrong number rather than a small one.
  - [x] `ProductVersion` fields `has_csh`, `csh_names`, `has_api_ref`, `api_files`, `doc_files`, all **optional** (`bool | None` / `int | None`). Blank means never extracted; `0` means extracted and none found.
  - [x] `VERSION_COLUMNS` extended with `_has_csh`, `_csh_names`, `_has_api_ref`, `_api_files`, `_doc_files` after `_bu` / `_family`; `csvio` gains a nullable-int/bool round-trip that preserves the empty cell rather than defaulting it to `0` / `false`.
  - [x] Excluded from `_MERGEABLE_VERSION_FIELDS` and from `version_snapshot`, on the same structural grounds as the engine columns — Stage 4 writes them and discovery has never opened the package. Unlike `_bu` / `_family` they are **not** regenerated on write; they persist between extract runs.
  - [x] `CatalogManager.record_extract_inventory(product, version, …)` — one call sets all five, so the booleans cannot drift from the counts. Modelled on `record_detected_engine`.
  - [x] `warnings()`: a boolean disagreeing with the count beside it (hand-edit only; advisory, never blocks).
  - [x] Left blank on a failed or partial extract — a failed run must not look like an empty package.
  - [x] Catalog-half tests (23, in `test_csvio.py` and `test_catalog.py`): blank ≠ zero in both directions, Excel's `4,310` / `4310.0` renderings, a measured `0` surviving as `0`, `_has_csh=true` with `_csh_names=0` warning-free, a fetch over an extracted row leaving all five untouched, byte-identical rewrite, `clear_extract_inventory`, and the hand-edited-boolean warning that must not block a write.
  - [x] Predicate tests, with the extractor: a Javadoc tree under an unguessable name (`hawk/6.2.2/console-api/`) classified by its marker; `api-exchange-gateway/` **not** classified despite the name; `api reference/` (with a space) classified; nested `javascript/` under `api-reference/` counted once via its outermost root; `JavaDoc` vs `javadoc` casing; and an unmarked API-ish directory reported as triage while its files stay in `_doc_files`.
- [x] **`docushift extract` report gains four blocks**, in this order after the existing outcome and engine tables: the CSH tally; the asset summary per output root; the unclaimed residue by top segment; the API-reference triage list. All four are report lines about *this run's* versions, and each names its version rather than only totalling, for the reason §7.3 gave for the two engine lists — a total nobody can trace to a package is not actionable.
- [x] **Tests**, extending `tests/unit/test_extractor.py` and `test_cli.py`: the six predicate cases above; a `Data/Alias.xml` with `<Map>` entries, an empty `<CatapultAliasFile />`, a zero-byte file and a malformed one, all four distinguished in `csh_source` and only the malformed one triaged; a `head.js` whose `suitehelp.contexts` is `{}`; a `topics.js` returning `null` unconditionally; version-wide identifier dedup that keeps `GatewayInstances` and `gatewayInstances` apart; a `.gif` under `Skins/` categorised `skin` and one beside a topic categorised `image`; a file under an API root inside an output root counted once, as API; an unclaimed tree reported by its top segment; and a failed extract leaving all five columns blank while a clean one with no CSH writes `_has_csh=false, _csh_names=0`.
- [x] **Docs in the same commit** — `design.md` §6.1 steps 4-5, §6.2, §6.3's predicate half and §6.4 steps 1-2 flip **Specified → Built** with their §12 index rows; §6.4's "decided by extension" is corrected for `skin`; **§6.3's `_has_csh` row is corrected** — it still says a WebWorks source leaves it `false`, which is left over from the 2026-09-07 descoping that §5.4.4 and §9.2 reversed on 2026-09-08. `user-guide.md`'s extract section gains the four report blocks and drops the "does not yet inventory" caveat; `CONTEXT.md` status, tree, and a ledger row.

**Deliberately not in 4b-2.** No resolution — §9.3 runs after conversion, against Markdown that does not exist yet, so 4b-2 counts identifiers and never checks that a link points at anything. No `csh.yml`. No copying, no orphan count: §6.4 steps 3-7 are the converter's and need a topic parse. No new marker added to the API list on the strength of this corpus — the triage line exists so a human adds it with evidence.

**Landed as specified** (2026-09-11), 569 tests passing (was 521). Three things the checklist did not anticipate, none of them design changes:

- **A `topic` category was added**, so the asset rows sum to the file count. §6.4 listed six categories for non-HTML files, which leaves the inventory unbalanced against `_api_files + _doc_files` and un-checkable. With topics counted the total is an invariant, pinned by `test_the_inventory_sums_to_the_file_count`, and a bug in the destination precedence shows up as arithmetic rather than as a plausible-looking table.
- **The tests landed in a new `tests/unit/test_inventory.py`**, not appended to `test_extractor.py` as the checklist said. That file is about unpacking and identifying a package; this one is about measuring it, and most of it needs no catalog at all — the predicate and the walk are pure functions over a directory.
- **The `product` and `version` fixtures moved to `tests/conftest.py`.** Importing a pytest fixture across test modules is a redefinition as far as ruff is concerned (F811, twelve times), and both halves of Stage 4 assert against the same catalog row, so the fixture belongs where both can see it.

One item on the list turned out to describe output the tool does not produce: §6.3's triage sample names `html/api-docs/dotnet/` as a second candidate line, but `dotnet` is not in the name vocabulary, so it produces no line at all. The sample is corrected rather than the vocabulary widened — the flag is a fixed list of names we have actually seen, not a guess at what an API directory might be called.

### Phase 5: Multi-Engine HTML -> GFM Conversion & Transforms

> **Split into 5a–5e (2026-09-11, user decision), and the seam is engine-neutral vs. engine-specific.** Phase 5 as written is four converter engines, a CSH mapper, an asset copier and a `convert` command in one commit — larger than 4a, 4b-1 and 4b-2 put together, and none of it reviewable until all of it exists. The cut that the specs themselves suggest: **everything the four engines *share* lands first, on its own, proven against a fake engine** (5a), then each engine lands against a spine that is already fixed (5b Flare, 5c DITA, 5d WebWorks, 5e DocBook). Three reasons this is the right seam rather than "spine plus the first engine". The spine gets designed against **three already-specified consumers instead of one** — Flare recovers a callout label from an attribute while DITA deletes one from a span (§5.1.8 vs §5.2.5), and a contract written against either alone is a contract written against a coincidence. The overdue §7.7 obligation (`reporting/findings.py`) has to land here regardless, and Phase 5 carries 9 of the 20 rows in the §7.5 register — more than any other phase. And the invariant-13 asset rule is one algorithm with three engines' prefix tables in it (§6.4 step 4), so writing it once beside the fake engine is the only arrangement in which "one resolution, two outputs" is a property of the code rather than of three copies of it. **End of 5a: nothing converts yet.** With no real engine registered, every selected version reports `ENGINE_UNKNOWN` and the spine is proven by fixture alone — which is a legible review state, not a failure.

- [x] **Engine Detector — moved to Phase 4b-1** (2026-09-11, user decision). It resolves the generator from the *extracted* tree and writes it back to `versions.csv`, which is `docushift extract`'s job and always was; `design.md` §7 keeps its section number and every measured figure, and only its phase attribution changed. The full checklist, the marker rules and the coverage regression against the 2026-09-08 sweep (`design.md` §7.2: 68% → 98% of HTML-bearing versions) now live under Phase 4b-1. One half of it had already landed here:
  - [x] **`SourceEngine` carries the unconvertible generators as real values** — `r-help`, `robohelp`, `frontpage`, `help-and-manual`, `mkdocs`, `docusaurus`, `doxia`, `other` — beside a `CONVERTIBLE_ENGINES` frozenset; `warnings()` names any convert-eligible row whose engine has no handler; `catalog set --engine` offers the full list, taken from the enum so it cannot drift. This is what makes the detector's answer reviewable in `versions.csv` instead of collapsing into `auto`.
##### Phase 5a: The conversion spine

Everything the four engines share, and nothing that knows what a MadCap file looks like. Ends with `docushift convert` running the download's selection end to end over a real catalog and reporting `ENGINE_UNKNOWN` on every version, because no engine is registered yet — the honest state, and the one §7.5 already has a code for.

- [x] **`reporting/findings.py` and the code registry — §7.7's obligation, three phases overdue.** It was specified to land "at the start of Phase 4" and did not; `src/docushift/reporting/` is still a bare `__init__.py`. It lands now rather than slipping a second phase, because Phase 5 carries **9 of the 20 rows** in the §7.5 register and a converter that invents its own logging is what §7.7 exists to prevent.
  - [x] **`runs` and `findings` in `state.db`, and no `SCHEMA_VERSION` bump.** The two tables of §7.1 verbatim. Additive, so an existing v2 file grows them on open — the same rule 4b-2's two tables established.
  - [x] **Severity is a property of the code, fixed in one registry, never chosen at the call site** (§7.1). One `FINDINGS` table maps each code to its severity, stage and one-line obligation; `record()` takes a code and refuses an unregistered one. Two call sites reporting the same condition at different severities would make the exit code depend on which fired.
  - [x] **`code` is the contract, `message` is prose.** Tests assert on codes. All 20 rows of §7.5 are registered in 5a even though 5a can only emit three of them, because the register is the deliverable and a half-populated one cannot be audited.
  - [x] **Errors and warnings one row each; notes aggregated into one row with a `count`** (§7.1). Aggregation is by `(code, slug, version)` — a per-file note would write hundreds of thousands of rows for `ASSET_ORPHANED` alone.
  - [x] **Written inside the stage's existing `state.py:transaction`** (§7.1, §3.5), flushed per version rather than per run: a crash on version 200 must not discard the findings of the first 199, and a version that failed mid-write must leave none of its own. This is the same invariant-11 rule that leaves a partial inventory walk's columns blank.
  - [x] **No `report` command in 5a.** §7.3's three commands are Phase 7; what lands here is the table, the registry and `record()` — "perhaps 80 lines", as §7.7 puts it. A run prints its own findings summary at the end, which is what makes the codes visible before Phase 7 exists.
- [x] **`engines/base.py` — the engine contract and the document model.** The interface all four engines implement, written against three specified engines at once so that it is a contract rather than a generalization of whichever one was built first.
  - [x] **The unit of work is named by the engine, not by the driver.** Flare's is the output root (676 across 595 versions, nested and overlapping), DITA's is the doc-set, WebWorks' is the book (3.5 per version). One method answers "what are the units in this tree", defaulting to `engines/roots.find_output_roots` — which 4b-1 already built and recorded — and one converts a unit.
  - [x] **A `Document` is the single thing a topic becomes**: source path, output path relative to its unit, title, nav label, GFM body, anchors it defines, CSH identifiers it owns, and a frontmatter mapping. **Two title strings, both kept**, because all three engines have them and they differ — Flare's `h1` vs. its TOC label, DITA's `h1` == `DC.Title`, WebWorks' `files.js` label vs. its TOC label.
  - [x] **Navigation is a node list, not a rendered `toc.yml`.** The engine reports the tree, the landing page and the support/legal tail; §10's synthesizer applies the three node rules (landing page first, headless containers get a generated page, support and legal **move** to the tail). Phase 6 renders. An engine that wrote YAML would put three engine-neutral rules in four places.
  - [x] **A failure is a returned outcome, never an exception** — the same rule `PackageDownloader` and `PackageExtractor` already state, so the three stage drivers read alike.
  - [x] **An engine registry, and an empty one is a valid state.** `register()` / `engine_for()`, keyed on `SourceEngine`. Membership of `CONVERTIBLE_ENGINES` is not the test — **a registered handler is** — so 5a's "nothing converts" and Phase 5e's "DocBook has no handler yet" are the same code path rather than two.
- [x] Callouts to GFM alerts (`> [!NOTE]`, `> [!WARNING]`, etc.).
- [x] HTML Table to clean GFM Pipe Table normalizer.
- [x] Cross-document link and anchor re-writer (`.html` -> `.md`).
  - [x] **The three above are `transforms/{callouts,tables,code,links}.py`, and they are pure functions over parsed HTML.** No engine imports another engine to get them, and none of them opens a file. Two rules are corpus-measured and shared: **tables that are not GFM-safe pass through as HTML** rather than have a `rowspan` silently flattened (Flare 57% safe, WebWorks 50.5%), and **code fences are emitted bare** — 1,565 of Flare's ~1,600 `<pre>` carry no language, DITA has exactly one language attribute in 864 blocks, and WebWorks has no language attribute anywhere.
  - [x] **Alert-kind vocabulary in one place.** GitHub supports exactly five (`NOTE`, `TIP`, `IMPORTANT`, `WARNING`, `CAUTION`); each engine maps its own markup to that vocabulary and an unmapped kind falls back to `NOTE` **with a report line**, never to a silently dropped label.
- [x] **Context-Sensitive Help mapper** (`transforms/csh.py`) — **all three HTML engines: Flare, DITA and WebWorks** (settled 2026-09-08). Schema, resolver and writer stay engine-neutral. Full design in `architecture.md` §5.4, grounded in three corpus surveys: 863 Flare `Alias.xml` / 11,054 entries, 418 DITA `head.js`, and 647 WebWorks `topics.js` / 3,439 entries. **The three readers landed in 4b-2** (`engines/csh.py`); what lands here is everything above them.
  - [x] Source-HTML → output-Markdown mapping recorded per version in `state.db` by the converter, so CSH resolution cannot disagree with what conversion actually did. **A third additive table, `output_map`,** replaced wholesale per version on each conversion for the reason 4b-2's two are: a re-convert must not accumulate a second copy.
  - [x] **One string identifier per topic; no numeric key anywhere in the schema.** The Flare reader takes the `Map`'s `Name`; `ResolvedId` is parsed so a malformed entry still counts as an entry, then discarded. The DITA reader takes the key of the flat `suitehelp.contexts` JSON object in `static/head.js` (380 of 418 files carry one). The WebWorks reader takes the case label from each `if(P=="<id>")C="<file>#<anchor>";` in `wwhdata/common/topics.js` (155 of 647 files carry cases).
  - [x] Resolver: doc-set first, then version-wide fallback (this rescues the 22% of *Flare* links that dangle inside their own doc-set; WebWorks resolves at 100% and never reaches the fallback); merge by identifier; primary doc-set = most resolved entries, ties alphabetical; conflicts recorded under `also` (26 genuine cross-book conflicts in the WebWorks corpus).
  - [x] **Byte-exact, case-sensitive handling of identifiers throughout.** `GatewayInstances` and `gatewayInstances` are different live help targets in TIBCO BC 7.4/7.5 — with the integer gone, case is the only thing telling them apart.
  - [x] **Identifiers are always emitted double-quoted**, in `csh.yml` keys and in frontmatter. 834 of 11,054 Flare names (7.5%) are digit-only, and a YAML 1.1 loader turns an unquoted `1234` into an int and `6.2` into a float. WebWorks and DITA identifiers need none of this — the rule stays unconditional anyway, because a conditional quote is a branch that can be wrong. **Values are quoted too** under the flat schema below, since a path may carry a `#`.
  - [x] **`csh.yml` is a flat `"<identifier>": "<relative-path>"` map** (AEM contract, supplied 2026-09-10 — supersedes the `schema`/`sources`/`counts`/`topics`/`unresolved` document in `architecture.md` §5.4.2). One file per version at the Markdown output root; no file at all when the version has no CSH.
    - [x] **Anchors are appended to the path** (`config/start.md#adb-palette`) rather than carried as a sibling field. §5.4.2's argument for splitting them — the consumer chooses the fragment encoding — is void now that the consumer has specified a single string.
    - [x] **`doc_set` disappears without loss**: each output root is already the first segment of the relative path (`architecture.md` §1576), so the flat value carries it.
    - [x] **Ambiguity now needs a deterministic winner.** `also` has nowhere to go in a flat map, so an identifier claimed by two doc-sets resolves to the **first doc-set in the version's ordered doc-set list** — ordered, so a re-run picks the same one. 5 of 233 in the worst observed version.
    - [x] **`sources`, `counts`, ambiguity and `unresolved` move to the run report**, and none of them is dropped. This is what keeps `design.md` invariant 10 ("absence is reported, never faked") true: a Help identifier that resolves to nothing must stay countable somewhere, and after this change the report is the only somewhere left. **The report line is not optional polish — it is the entire remaining record.** With 5a's findings module landing in the same commit, that record is a `CSH_UNRESOLVED` row in `state.db` rather than a line of terminal scrollback.
    - [x] **`design.md` §9.4 and `architecture.md` §5.4.2 are corrected in this commit.** Both still specify the rich document the 2026-09-10 AEM contract replaced. A superseded spec that reads as current is worse than no spec, and this is the sub-phase that builds the writer.
  - [x] Frontmatter injection: `csh: ["id-a", "id-b"]` on topics that own identifiers, written in the topic's first pass rather than as a read-modify-write second pass.
- [x] **Asset copier and link writer — one resolution, two outputs** (`architecture.md` §5.5, `design.md` §6.4, invariant 13). The copy set is what the emitted Markdown references, computed in the pass that emits it. Never a second walk that re-derives a destination from a URL or a cache layout: that is precisely what breaks 7,231 of the predecessor's 23,172 image links, 7,223 of them in one product, silently (`architecture.md` §5.5.9).
  - [x] Normalize before resolving — strip `#fragment`/`?query`, percent-**decode**, `\` → `/`. Skipping this reports 1,872 WebWorks references as missing that are not.
  - [x] **Skin prefixes are whole-segment tests, never substrings** — Flare `Skins/` + `Resources/{Scripts,Stylesheets,MasterPages,TemplateExtensions}/` + `Data/`; DITA `static/`, `fonts/`; WebWorks `wwhdata/`, `wwhelp/`, `tpl/`. This branch takes 48.7% of DITA references and 76.2% of WebWorks ones, so it is the main path, not an edge case. **The table is 4b-2's `_SKIN_PREFIXES`, imported and not retyped** — the inventory's `skin` category and the converter's skin drop must be the same answer, or a file is chrome in one report and an asset in the other.
  - [x] **Assets keep their source-relative path**; each output root gets its own subtree. Flattening collides 5,328 times inside one Flare root and merges 112 WebWorks files that share a path across books but differ in bytes.
  - [x] **Percent-encode on emit**, with a literal `%` escaped *first*. 6,587 of 792,607 assets sit at a path that breaks a bare Markdown URL; 104 filenames already contain a `%`.
  - [x] A reference that will not resolve emits **neither** link nor copy, and is counted — grouped by top path segment, not just totalled. Flare's 12.9% dangling rate is 2,706 references from one tree that is broken in its own source; the rest is 0.37%.
  - [x] Report per output root: resolved, skin, escaped, dangling, case-mismatch, orphan. **Orphans are never copied** — 54.6% of Flare's images and 673 MB.
  - [x] References that escape the output root are handed to Phase 7 with their resolved source path, not emitted (`design.md` §10.7). 279 in the Flare sample, 0 in DITA and WebWorks.
- [x] **Conversion skip for API-reference trees** — the *same* `is_api_reference()` predicate Stage 4 counts with (`design.md` §6.3), not a second name list that can drift from it. Marker files decide; a name-only match is reported for triage and still converted. These trees are copied verbatim by Stage 7 into the `api-references` doc-class (`architecture.md` §6.2), never fed to an engine — Javadoc is not generator output and converting it yields broken Markdown from working HTML. Links from converted topics into these paths are left intact here and re-pointed at sync time, when the publishing layout and `publish_base_url` are known.
  - [x] **The roots are read back from `version_metadata['api_roots']`, which 4b-2 wrote** — never re-walked. §6.3 is explicit that Stages 4, 5 and 7 read one recorded answer; a second walk at conversion time could disagree with the counts already in `versions.csv`.
- [x] **`ConfigManager.output_path(bu, family, slug, version)`** — `output/<family-workspace>/<slug>/<version>/`, mirroring `extract_path()`. The version keeps its dots here for the same reason it does there: this is a working path keyed by the catalog, and the dots-to-dashes conversion belongs at Stage 6 where the AEM path is built. There is currently no output-path method at all, and letting the converter join strings would put the one contract Stage 6 and Stage 7 both read in three places.
- [x] **`docushift convert`** — the same `_scope_options` selectors as `download` and `extract`, plus `--force` and `--dry-run`, and `--input`/`--output` for a standalone extracted folder outside the catalog.
  - [x] **Selection is the download's, narrowed to what is extracted.** A version with no extracted tree is a report line (`no-tree`), not an abort — the same rule that keeps one unreachable product from stopping a 200-version batch.
  - [x] **Dispatch is on the registered handler for the version's engine.** `auto`, an engine outside `CONVERTIBLE_ENGINES`, and a convertible engine with no handler registered are all **`ENGINE_UNKNOWN`** — skipped, never guessed (invariant 7). In 5a that is every version, which is the sub-phase's whole visible behaviour.
  - [x] **Output is built at `<output_path>.part/` and swapped**, the same rule 4b-1 established for extraction and for the same reason: a re-convert over a live directory leaves the previous run's topics behind, so a guide dropped upstream survives in the output forever. Not atomic on Windows; stated rather than implied.
  - [x] **`--force` and an unchanged-input skip.** A version whose extracted tree has not changed since it was converted is `current` and does no work, keyed on `extract_zip_checksum` — the value 4b-1 already records — rather than on a hash of thousands of Markdown files.
  - [x] Report: the outcome counts, a per-version topic/asset tally, the CSH resolution summary, and the findings recorded by severity. Status `CONVERTED` per version in `state.db`.
- [x] Exhaustive unit tests with fixtures in `tests/unit/`, including the CSH cases the corpus survey turned up: case-only identifier collision, a digit-only identifier that must survive a YAML round-trip as a string, fragment in `Link`, an alias file that resolves 0%, a version with three doc-sets whose identifiers overlap, empty/zero-byte alias files, a `head.js` whose `suitehelp.contexts` is an empty object, and — for the WebWorks reader — a `topics.js` that returns `null` unconditionally, one carrying a `#anchor` target, and a book where `files.xml` disagrees with `topics.js` (the XML is not consulted, and a test should pin that).
  - [x] **The spine is tested against an in-process fake engine**, registered by the test and never shipped. It emits two topics, one asset reference that resolves, one that dangles, one skin reference and one that escapes the root — which exercises all five branches of §6.4 step 3 without a MadCap fixture. This is the arrangement that makes 5a reviewable on its own.
  - [x] **A registry test asserts every registered code is reachable and every emitted code is registered** — the §7.5 guarantee, written now rather than in Phase 7. It is allowed to pass with codes no code path reaches yet, and it names them, so the register stays a visible to-do list instead of a silent one.
- [x] **Docs in the same commit** — `design.md` §6.4 steps 3–7, §9.3, §9.5 and the `csh.yml` writer flip **Specified → Built** with their §12 index rows; **§9.4 is rewritten for the flat map** and `architecture.md` §5.4.2 with it; `design.md` gains §8.5 (findings and severity) early, since the module lands here rather than in Phase 7; `user-guide.md`'s `convert` section replaces its "not yet implemented" note; `CONTEXT.md` status line, directory tree and a ledger row.

**Deliberately not in 5a.** No engine — not even a small one. No `report` / `validate` / `csh` commands (Phase 7; the table and the registry land here, the commands that read them do not). No `toc.yml`, `nav.yml` or `metadata.yml` (Phase 6; the engine reports a node list and 5a carries it no further). No cross-version CSH regression (§7.6 — it needs two converted versions). No orphan-rise warning (`design.md` §6.4's Open — there is no baseline until Phase 5 has run twice).

**Landed as specified** (2026-09-11), 656 tests passing (was 569). Three things the checklist did not anticipate, and one measurement it could not have:

- **The skin table is `engines/roots.SKIN_PREFIXES`, not `extractor/inventory._SKIN_PREFIXES`.** The checklist said "imported and not retyped" and was right about the rule; it named the wrong module, and the difference matters in one direction only — `transforms/assets.py` importing from `extractor/` would make Stage 5 depend on Stage 4's *walk* to learn what chrome is. It already lived beside the root locator, where per-engine layout knowledge belongs, and 4b-2's inventory imports it from there too, so the one answer has one home and two readers.
- **`ConversionContext.assets` is the driver→engine hand-off, and it is per-unit state on a per-version object.** The checklist fixed *when* a reference is resolved (in the emitting pass, invariant 13) and never said *who owns the copier*. It has to be the driver's: an engine constructing its own would also be deriving the destination, which is exactly the second answer §6.4 exists to prevent. So the driver sets it before each `convert_unit` — deliberately mutable, and documented as such at the field.
- **The engine contract came out smaller than the checklist implied.** Two abstract methods, one of them defaulted. Everything else the four engines were expected to share turned out to be either already built (`engines/roots.py`, `engines/csh.py`) or engine-neutral enough to be a free function in `transforms/`, which is the result the "three specified consumers, not one" argument predicted.
- **`utils/swap.py` had to be written, and the number is worth keeping.** The build-and-swap directory rename lost a race with the Windows indexer/on-access scanner in roughly **one run in seven** of the Stage 5 suite — `PermissionError: [WinError 5]` on a **nine-file** tree that had been written correctly. Both tree swaps now retry five times with a growing delay; the downloader is deliberately excluded, because its single-file `os.replace` is atomic over an existing name and a delete-then-rename would weaken the guarantee that a killed run never leaves a truncated ZIP at the canonical path. The bug was found only because a test asserted its own fixture's success — the failure had been surfacing as an `AttributeError` three calls downstream, which is the shape of an intermittent test everyone learns to re-run.

##### Phase 5b: MadCap Flare Engine

The largest engine in the corpus by six times, and the first real consumer of 5a's contract.

- [x] **MadCap Flare Engine** (`engines/flare.py`) — full design in `architecture.md` §5.1, from a corpus survey on 2026-09-08 of **676 output roots / 595 versions / 208 products / 422,267 content topics / 307,394 images / 19.5 GB**. The largest engine in the corpus by six times. Sampled claims rest on 60 whole output roots (59 versions, 48 products, 43,753 files).
  - [x] **The output root is the unit of work, located by `Data/HelpSystem.xml`** — never by a configured path. The walk **descends into nested roots** (153 of them, 22,456 files, e.g. `tp/1.1.0/html/Subsystems/*`) and the innermost root owns a file; stopping at the first match drops 22,456 topics, not stopping converts them twice.
  - [x] **A version can ship several output roots (51 of 595), and they overlap — each converts independently.** The 30,736 shared relative paths are 40.3% byte-identical but **~15% genuinely different content** (`mdm/9.3.2 release-notes/new-features.htm` at a 0.019 token overlap: two different releases' notes at one path). No cross-root dedup; duplication in the output beats losing a release's notes. Worth a test that pins the 15% case.
  - [x] **Output mirrors the source tree.** Filename stems collide 6.0% within one root and title slugs 2.6%, so neither flat output nor a title slug is unique. 85% of topics sit one level down. Mirroring makes link rewriting a `.htm`→`.md` suffix substitution. *(Deliberately the opposite of §5.2.2's flat DITA output — Flare's source is structured and its TOC is not.)*
  - [x] **TOC from `Data/Tocs/<Name>.js` + `<Name>_Chunk<N>.js`** — AMD `define({…})` object literals, parsed with a targeted expression, never executed. Locate the tree via `HelpSystem.xml`'s `Toc=` attribute, not by globbing (3 roots ship two trees and alphabetical-first is wrong in all three); the declared tree is the root of `toc.yml` and any other trees in `Data/Tocs/` become sibling top-level nodes, since the declared one covers only 53 of 106 topics in `bctcm/6.2.0`.
  - [x] **Reconstruct the tree by index inversion.** `tree` is `{i,c,n}` integer ids with no titles or hrefs; the chunk file is `path → {i:[ids], t:[label], b:[anchor]}`. Parse chunks into `id → (path, label, anchor)`, then walk `tree` depth-first — sibling order in `n` is nav order. **`i`/`t`/`b` are parallel arrays** — the `k`th id is labelled by the `k`th title, so `t[0]` for every id silently relabels nodes (0 ragged arrays in 37,598 entries confirms the alignment). 3.7% of page entries sit at several TOC positions and **60 carry a different label at each**; keep `b`, a bookmark on 12.1% of entries. All 679 corpus TOC files are `numchunks:1`, so support sharding but expect not to exercise it.
  - [x] TOC coverage is **85.9% corpus-wide (median 92%); complete in 85 of 676 roots, below 50% in 59.** Orphans go to an explicit "Unfiled" node and are counted, as in DITA. **`data-mc-toc-path` must not be used** — 64% of values carry an unresolved `[%=System.LinkedHeader%]` template token.
  - [x] **Convert the landing page and make it the first `toc.yml` node** (`architecture.md` §5.1.5). `HelpSystem.xml`'s `DefaultUrl` resolves in **676 of 676 roots** (646 into `_templates/`, 30 at an ordinary topic), yet it is **not a TOC entry in 55 of 60 sampled roots** — it would land under "Unfiled" otherwise. Where it is already in the TOC, move that node to first rather than duplicating it.
  - [x] **Landing-page handling, four cases the scan found.** It is not boilerplate — 0 hits for `lorem`/`[Enter …]`/`TBD`/unexpanded `[%=…%]` across all 676; past the hero furniture (`.homepage-banner`, `#release-info`, `.download-button`) **351 are rich (≥400 chars), 270 light, 55 hero-only** — so the 55 get a generated stub and the rest convert. (a) 5 roots' landing pages have **no `#mc-main-content`** (all `statistica-lts-release/overview.htm`, 3,444 chars of real prose) — fall back to `<body>`. (b) **24 have no `h1`** and only 2 a usable `<title>` — fall back to `span.mc-variable.productvar.productName`, then the catalog name. (c) Of 9,061 links, **5,911 target `.pdf`/`.zip`/`.txt`** (often `../../../`, outside the root) and **3,698 are absolute `http(s)`** — neither is rewritten to `.md`; out-of-root assets are recorded as unresolved. (d) **Unroll `MCDropDown` here** — this is the one place the construct lives (`Release Documents` 454, `Related Product Documentation` 439, `Most Visited Topics` 408, `Downloadable PDF Guides` 388, `Key New Features` 325) — into `##` sections.
  - [x] **Generate a section page for every headless TOC node.** Walking the tree (not the flat path map) gives **7,388 container nodes; 7,223 (97.8%) have a real page** (median 1,276 chars) and **165 (2.2%) are headless** — the `'___'` sentinel key, a label and children and no file. **151 of the 165 are top level** and hold **1,357 children**; AEM treats a node with children and no page as a broken parent. Generate a page titled from the TOC label listing links to its immediate children, marked generated in frontmatter so a re-run replaces it. Also: **7 headless nodes have no children** — drop and count; **30 containers point at the same page as one of their children** — drop the child node, keep the topic once.
  - [x] **`_templates/` is partly converted, not skipped.** 2,797 files under 82 names (78 case-folded); beyond the landing page, **1,737 TOC entries across 660 of 676 roots** point into it — legal 657 (37.8%), support 649 (37.4%), what's new 381 (21.9%), home 32 (1.8%), other 18 (1.0%); median 3 per root, max 4. *(Supersedes the first sample's 162-in-59-of-60.)* Convert a `_templates/` file when the TOC references it or it is the `DefaultUrl`; skip it otherwise.
  - [x] **Report the support and legal pages as the two tail nodes** (`architecture.md` §5.1.5). The engine identifies them; §10's synthesizer moves them to second-last and last. Three things the engine must get right. **Pick by the TOC, not by name** — 49 roots ship 2+ support pages and 5 ship 2+ legal pages, and in **all 54 the TOC references exactly one**; `fsp_transactioninsight/5.5.0` picks `Legal_and_Third-Party_Notices.htm` and `6.0.0` picks `Legal-and-Third-Party-Notices.htm`, so name priority is wrong. **Carry the label, do not constant it** — support `h1` is `TIBCO …` 565, `ibi …` 49, `Spotfire …` 45, bare 4, malformed 5. **Convert per version** — 588 distinct legal bodies across 669 roots and 595 distinct support bodies across 668, so these are product content, not boilerplate. Absent in 7 and 8 roots respectively; report absence, generate nothing. Worth a test that pins the multi-candidate root.
  - [x] **Two title strings, both kept**: `h1` is the page title (`<title>` is the truncated one in ~10% of topics), the TOC label is the nav entry (equal to `h1` in 2,429 of 2,512; the rest are deliberate short labels).
  - [x] **Content is `div[role='main']#mc-main-content` — one selector, 4,656 of 4,660 MadCap topics (99.9%).** No fallback chain: the predecessor's fallbacks convert *non-Flare* files instead of reporting them, which is how a Javadoc page reaches the Markdown output. A miss is a report line.
  - [x] **Strip `#feedback-survey` before any link analysis.** It is in 95% of topics and accounts for **47.7% of every raw `href`** (`javascript:void(0)` buttons); measured after it, a topic averages 1.1 links. Then unwrap `div.topic-frame` (88% of topics — **absent from the predecessor's chrome list**), and remove `MCBreadcrumbsBox_0`, `MCMiniTocBox_0`, `topicToolbarProxy`, `p.MCWebHelpFramesetLink`.
  - [x] **`data-mc-autonum` is where Flare's semantics live** — the label is an attribute the skin's CSS renders, so the engine must *recover* it. (DITA is the mirror image: the label is already a `span` and must be *deleted*, §5.2.5.) Callouts `div.note*` → GFM alerts (Note 1,574, Warning 30, Tip 28, Important 21); task structure survives only as autonum values (`Procedure` 702, `Subtopics` 467, `Before you begin` 244, `What to do next` 137, `Result` 88).
  - [x] **MadCap emits lists as tables** — `AutoNumber_p_*` single-column tables, 1,321 in 7% of sampled topics (`Bullet` 753, `Step` 480, `ListDash` 82), against 1,809 real `<ul>` / 1,201 `<ol>`. `data-mc-autonum` on the content cell decides ordered vs bulleted; **the class name alone does not** — `Step` and `Bullet` both appear with and without numbering. Converting these as tables yields a one-column pipe table where a list belongs.
  - [x] Tables: 98% are `TableStyle-Table` (styling, no semantics); **57% are GFM-safe**, the rest pass through as HTML rather than have a `rowspan` silently flattened. Code fences bare — 1,565 of ~1,600 `<pre>` carry no language.
  - [x] **"Dropdown unrolling" moves from the topic converter to the landing-page converter.** A cache sweep for `MCDropDown`/`MCExpanding`/`MCToggler`/`MCSnippet` in HTML found 459 files, **457 of them the generated `_templates/Home.htm`**; exactly one content topic uses the construct (`tp/1.1.0/html/UserGuide/previous-versions-release-notes.htm`). 0 occurrences in 4,810 sampled content topics. The classes saturate every root's skin CSS and `MadCapAll.js`, which is what made it look ubiquitous. In a content topic: generic unwrap path, no special case. On the landing page — which §5.1.5 converts — the dropdowns carry the whole page structure and must be unrolled.
  - [x] Links: 78% relative `.htm`, **98.3% resolve on disk**; dangling ones emit as plain text and are counted. **Do not conflate this with CSH** — in-content links are 98.3% good while `Alias.xml` links are 22% dangling, so the two have different fallbacks (§5.4.1's version-wide resolution is for the alias case only).
  - [x] Skipped, all counted in the report: **2,339 HTML files in generated dirs** (`_globalpages/` 1,965, `MicroContent/` 295, `Resources/` 79 — `_templates/` is no longer among them); **1,295 `Default.htm`/`Default_CSH.htm` stubs**; **595 API/Javadoc directories, 8,078 files, concentrated in 56 versions** (by the shared `is_api_reference()` marker predicate, never by directory name); the **`ja` subtree, 8,004 files** — the corpus's only localized tree; authoring-source assets (1,160 `.vsd`, 818 `.vsdx`, 149 `.zip`, 127 `.xlsx`, 80 `.drawio`) — unreferenced by any topic, so inventoried and reported, never copied (`architecture.md` §5.5.3); and the **5 partial Flare outputs** (MadCap topics, no `Data/HelpSystem.xml`) reported for triage.
  - [x] **Detector correction, with a test**: drop `Skins/` and `Data/` from the Flare marker list. Over 1,822 cached versions the seven-marker list matches 689 against 595 real runtimes (`Skins/` 91.4% precise, `Data/` 88.0%), and **all 94 false positives come from those two markers and no other** (17 WebWorks, 3 DITA, 74 with no engine marker at all). They add **no recall** — `*.mcwebhelp` alone finds all 595, `csh.js` alone finds all 595. Fixture: a WebWorks tree shipping a `Skins/` directory, which detects as Flare under the old list. *(Casing note: exact-case matching would rescue `Skins/` — every non-Flare match is a lowercase `skins` — but not `Data/`, which 36 correctly-cased non-Flare versions ship. Opposite direction to §7.2's mandatory case-**in**sensitive `DC.*` rule.)*
  - [x] **Inherit from the predecessor deliberately, not wholesale** (`architecture.md` §5.1.10). Take: the 13-pass ordering in `scripts/lib/preprocessor.py`, `fake_list_tables()`, `split_colspan_tables()`, the `SPAN_TO_TAG` vocabulary, and `skip_filenames` **minus its `Home.htm` entry**. Reject: the `Home.htm` skip (it discards the landing page in 644 of 676 roots), the missing `div.topic-frame`, the four-selector fallback chain, and `skip_path_segments` — a hand-maintained mix of product and language names (`/javadoc/`, `/Java_API/`, `/golang/`, `/c/`, `/tibdg/`) that is the exact failure mode §6.3's marker predicate was specified to end.
  - [x] **Docs in the same commit** — `architecture.md` §5.1 and `design.md` §12's Flare row flip **Specified → Built**; `user-guide.md`'s `convert` section stops saying no engine is registered; `CONTEXT.md` status line and a ledger row; the eight new §7.5 register rows in `planning.md` §7.5 and `design.md` §8.5.

**Landed as specified** (2026-09-11), 721 tests passing (was 656). A batch over 25 sampled products — 17 output roots, 6,051 documents — completes with **0 exceptions and 0 dangling assets**: 1,541 references resolved, skips `api-reference` 664 / `nested-output-root` 684 / `generated-directory` 52 / `runtime-stub` 32 / `no-content-container` 6 / `unreferenced-template` 4, findings `TOC_ORPHAN` 720, `TOPIC_LINK_DANGLING` 11, `TAIL_PAGE_MISSING` 6, `CONTENT_MISSING` 6, `NAV_NODE_DROPPED` 5. Nine things the checklist did not anticipate:

- **Two modules, not one.** `transforms/markdown.py` holds the HTML→GFM walk and `engines/flare_toc.py` the AMD literal reader. 5a deliberately built the six *decisions* that differ by construct and no walker, because at that point nothing walked; leaving the walk in `flare.py` would have had DITA and WebWorks each write a third paragraph-and-list renderer, and their disagreements would surface as three Markdown dialects in one repo. The engine keeps the *vocabulary* through four hooks (`block_override`, `inline_override`, `link`, `image`) — which is exactly the seam the "three specified consumers, not one" argument predicted, arriving one sub-phase later than that argument did.
- **`markdownify` is gone from `pyproject.toml`.** Declared since the scaffold, never imported, and not named by any spec. The walk it would have done is the one place invariant 13 has to be enforced per element, so a library that resolves nothing and knows no engine vocabulary would have been wrapped until nothing of it was left.
- **The detector correction had already landed**, in Phase 4b-1 with its WebWorks-ships-`Skins/` fixture. Ticked here because the checklist item is satisfied, not because the commit contains it.
- **Two contract fields the spine was missing**: `NavNode.anchor`, because 12.1% of TOC entries carry a bookmark and dropping it makes 30 same-page child nodes indistinguishable from their parent; and `ConversionContext.product_name`, because §5.1.5(b)'s landing-page title fallback ends at the catalog name and the engine has no other way to reach it.
- **Link resolution is against the planned set, not the disk.** A link resolves only if its target is a topic this run actually converts, so a `.htm` that exists but was skipped as API reference or as a runtime stub emits as plain text rather than as a link into a file nothing wrote. The disk-based 98.3% is therefore a ceiling, and the measured 11 danglings over 6,051 documents is the figure that matters.
- **`lxml` deletes `<![CDATA[…]]>` outright**, because CDATA is not a thing in HTML — and MadCap uses it as a literal-text carrier. 130 files of a 3,411-file sample carry 300 sections: 170 hold only the space separating a word from the inline `<span>` after it, 130 hold plain text, **none hold markup**. So the section is unwrapped and escaped before parsing, text in and text out. Related and separate: `Comment`, `CData`, `Doctype` and `ProcessingInstruction` are all `NavigableString` subclasses in bs4, so the obvious `isinstance` check emits commented-out markup into the prose — hence one shared `markdown.is_text()`.
- **Invariant 13 does not stop at the edge of a pipe table.** 43% of Flare's tables pass through as HTML, and their source markup carries `src="images/x.png"` — a path in the *source* layout, in the one branch where no hook was consulted. `Renderer.rewrite()` resolves references inside a passthrough subtree before it is emitted, which is the difference between "one resolution, two outputs" being a property of the code and being a property of the pipe-table branch.
- **Callout detection is wider than the callout mapping**, and had to be. Matching the closed 12-name set made `ALERT_LABEL_UNMAPPED` unreachable — a registered code that could never fire. A scan of 2,174 sampled topics finds exactly six classes in use (`note`, `noteNote`, `noteImportant`, `noteCaution`, `noteTip`, `noteWarning`) and the vocabulary maps all six, but Flare's convention is `div.note<Kind>` where the kind is whatever the project stylesheet defines, so the set is open even though the corpus's own is closed. Prefix matching turns an unsampled `div.noteBestPractice` into a NOTE with a reported label instead of unmarked prose with its admonition silently lost. The same scan found **5 topics whose `data-mc-autonum` holds markup** (`<b><span class="mcFormatSize">Note: </span></b>`), so the label is parsed and its text taken — left alone it re-emits literal HTML inside a `**bold**` run.
- **One malformed `.js` must not abort a 200-version batch.** The TOC literal reader indexed past the end of a truncated file and raised `IndexError`, which escaped `parse_define`'s `except ValueError`. Every read now fails as `ValueError`, and `RecursionError` joins it for a tree nested past the interpreter's limit; both answers are the same empty `Toc` the caller already handles.

One measurement the checklist could not have: **the hero-only threshold holds.** §5.1.5 says 55 of 676 landing pages are hero-only; the implemented rule (100 visible characters past the furniture) stubs **4 of 88 sampled roots, 4.5%**, against the specified 8.1%, and the 10th percentile of the pages it converts is 259 visible characters — the line sits well below the crowd rather than through it.

##### Phase 5c: SDL DITA Engine

- [x] **SDL DITA Engine** (`engines/dita.py`) — full design in `architecture.md` §5.2, from a corpus survey on 2026-09-08 of 353 doc-sets / 319 versions / 136 products / 67,406 `GUID-*.html` topics. Targets **SDL SuiteHelp** output, not DITA-OT's; the detector made exactly that mistake and it hid 371 versions. Those 371 are two publishers — 316 SuiteHelp and ~55 file-named — and only SuiteHelp is specified here.
  - [x] Doc-set located by content (a directory holding `GUID-*.html`), never by configured path — the root sits at `html`, `doc/html`, `html_v3` or `en-US` depending on the product, and 23 of 319 versions ship several doc-sets.
  - [x] Content is `<article>` — present in 3,742 of 3,742 sampled topics and the only invariant across the corpus's two skins (Bootstrap 89%, legacy `#leftbar` 11%). Chrome *inside* it is then removed: `#copyright`, `<noscript>`, `#thumbnailDialog`, `.familylinks`.
  - [x] **Title from the topic, structure from `suitehelp_topic_list.html`.** `h1` == `DC.Title` in 100% of sampled topics; the TOC files disagree with each other on 4% of shared entries and `toc_crawler.html` is the stale one. Topics in neither list go to an "Unfiled" node and are counted, not dropped (complete TOC coverage exists in 36 of 353 doc-sets).
  - [x] **`DC.Relation` must not be used as a parent pointer** — 42% of topics sit in a mutual `a↔b` pair and all 65 doc-sets tested contain a cycle. Worth a test that pins this, since it is the tempting wrong answer.
  - [x] Deterministic slugs: 44% of doc-sets contain a title collision, so ties break by GUID with `-2`/`-3` suffixes; flat output within the doc-set, hierarchy carried by `toc.yml`.
  - [x] **`_unique_N` republished topics collapse to one file** — 2.7% of topics are the same content republished at a second TOC position, identical but for `_unique_N` on every id and anchor.
  - [x] Class-vocabulary mapping (`topictitle1`, `sectiontitle`, `shortdesc`, `codeblock`, `uicontrol`, `stepexpand`, `fignone`, …); **callouts to GFM alerts with the `span.*title` label span removed** — every one of the 1,764 observed callouts carries one, and leaving it duplicates the label; **code fences emitted bare** (the corpus has exactly one language attribute in 864 `<pre>` blocks).
  - [x] GUID link rewriter — 48% of hrefs are `GUID-….html` and 0.1% are extensionless, so match on the GUID not the suffix; drop the 84% of fragments that are redundant self-references; report the 6.1% that dangle.
  - [x] Content images keep their source filename — 91% of `<img>` carry no `alt` at all, so the predecessor's alt-text renaming strategy is abandoned; `static/` icons are never copied.
  - [x] `GUID-*-homepage.html` is parsed for `publication-title`, `release-version` and `release-date` (present in all 314 doc-sets that ship one) and is never converted as a topic. `index.html`, `search-index.sqlite`, `static/`, `fonts/` are skipped. *(Amended 2026-09-10: these three no longer feed `metadata.yml`, which AEM specified as `csg-*` keys only. They become a **cross-check** against the catalog's `display_name` and `release_date` — a mismatch is a report line, not a failure. Collection is unchanged; only the destination moved. See Phase 6's artifact contract.)*
  - [x] **Flavour detection, kept as a guard now that the file-named flavour is out of scope.** The detector's 371 DITA versions are **316 SDL SuiteHelp** (`GUID-*.html`, flat) plus **~55 file-named** (`topics/…/administrator_roles.html`, nested, lowercase `DC.*` — 132 doc-sets, ~6,215 topics, and 9 products that are all excluded as of 2026-09-09). `engines/dita.py` still branches on whether the doc-set holds `GUID-*.html`, implements SuiteHelp, and reports the rest rather than converting them — the branch can now only fire if a product is readmitted to scope, and without it a bare-`article` doc-set would run the SuiteHelp path and produce plausible wrong output instead of a report line.
  - [x] **`DC.*` detection must be case-insensitive** — SuiteHelp writes `DC.Type`, the file-named flavour `DC.type`. Worth a detector test with a lowercase fixture; a case-sensitive match drops 66 versions and looks like a clean result. Its live yield is zero today (all 66 belong to out-of-scope products, which are never extracted), and it stays regardless: one `re.I` is the difference between a readmitted product detecting as `dita` and it reading as `auto`.

> **File-named DITA Engine — dropped from Phase 5 (2026-09-09, user decision).** Every product that publishes this flavour is out of scope, so it has no population left to convert. Measured slug by slug against `config/scope.yaml` on 2026-09-09: `sf-pysrv` (27 versions), `sf-rsrv` (21), `enterprise-runtime-for-R` (11), `ebx-addon` (2), `sf_ipad`, `sf_ipad_deploykit`, `sfire-android`, `sfire-cloud`, `sfire_dev` — nine products, all on the 61-slug exclusion list, so it is Spotfire plus one EBX add-on rather than Spotfire alone. The measurements in `architecture.md` §5.2.1 stay on the page against a future scope change (the transform half of §5.2 transfers, the layout half does not, and `article[role='article']` is the content selector at 587 of 587); what is dropped is the build item, not the survey.
**Landed as specified** (2026-09-11), 773 tests passing (was 721). No new findings codes: 5b closed Stage 5's side of the register and every code §5.2 needs — `DOCSET_SKIPPED`, `CONTENT_MISSING`, `TOC_ORPHAN`, `TOPIC_LINK_DANGLING`, `NAV_NODE_DROPPED`, `TAIL_PAGE_MISSING`, `ALERT_LABEL_UNMAPPED` — was already registered and is exercised by a test here. Nine things the checklist did not anticipate, seven of them re-measurements that changed a decision:

- **§5.2.5's class table is mostly redundant, and honouring it would have been wrong.** SuiteHelp already emits the semantic tag: `topictitle1` is an `h1`, `sectiontitle` an `h2` (922) or `h3` (4), `codeph` a `<samp>`, `varname` a `<var>`, `userinput` a `<kbd>`, `codeblock` a `<pre>`, `stepexpand` an `<li>` inside a real `<ol>`. The table maps `sectiontitle` to `###`, which would demote every section heading in the corpus and break the four already at that level. So the **tag rules the level** and the implemented map covers only the classes whose tag carries no meaning — the `<span>`s and the callout `<div>`s. This is the one place the survey specified more than the source needed.
- **The admonition class is `note tip`, not `tip`** — DITA-OT writes the family and then the type, so `note` is on every admonition and picking the first class in any fixed order renders `tip` and `warning` as plain NOTEs while leaving `caution` correct. The kind is taken from its **label span** instead, which SDL emits 1:1 with the kind in every kind measured — so the markup that must be deleted is also the markup that says what to delete it as, and a type outside the DTD's eight is reported rather than swallowed. That is what keeps `ALERT_LABEL_UNMAPPED` reachable here, as prefix matching does in Flare.
- **A blanket `[class$='title']` sweep is a trap.** Every callout label ends in `title` — and so do the 265 `span.wintitle` in the same sample, which are content. Removal matches `span.<kind>title` against the callout div's own kind and nothing else.
- **Half the anchors are not `<a name>`.** 8,056 id-bearing elements pair with an `<a name>` of the same value and **7,377 do not**, so pruning by looking at `<a>` alone keeps under half the link targets in the corpus and turns the rest into dropped bookmarks. Where the pair is missing a marker is inserted, so the renderer has one thing to emit rather than two.
- **`menucascade` gets no mapping.** It holds at least one `uicontrol` in 2,618 of 2,619 observed and `uicontrol` is already bold, so mapping the wrapper too emits `** **File** > **Save** **`. Falling through to the shared walk is the correct answer, and the only class in §5.2.5's vocabulary that has one.
- **`_unique_N` pairs by identifier and never by filename.** `GUID-…ADE1E_unique_1` lives in `GUID-…ADE1E1.html` — the counter lands on the identifier and the filename merely gains a bare digit, which matches no `_unique` pattern. Pairing on the stem puts both halves of every pair in the originals map, where the second overwrites the first and the collapse silently never happens. 402 of 18,542 scanned topics (2.2%, against the survey's 2.7%) are republished, and in **402 of 402** the stripped identifier names another file in the same doc-set.
- **There is no landing page to hoist, and none is synthesized.** `index.html` redirects to the `-homepage.html` in 23 of 25 sampled — which §5.2.7 makes metadata, not a topic — and in 0 of 23 does it name the TOC's first node. The TOC is a **forest** of 2 to 10 top-level entries, never one. So `unit.landing` stays `None` as it does for WebWorks (§5.3.5) and Phase 6 synthesizes the version root. Not an absence to report: it is the engine's normal shape.
- **Both TOC files are the same shape**, nested `<ul><li id="toc-GUID-…"><a href="GUID-….html">`, so one reader serves the primary and the fallback and the choice between them is a file choice rather than a second parser. Two details the shape hides: a container `<li>` with no link of its own must not inherit its first child's `href` (a recursive `find` gives a section one of its own topics, and it reads as a working link), and `data-audience` is `NONE` in 4,994 of 4,994 — not a filter.
- **`_is_legal`/`_is_support` moved from `flare.py` into `engines/base.py`.** The second caller appeared here and a DITA filename carries no words at all, so the label is the only evidence and the `path` argument became optional. `Unit` owns the slots; the predicates that fill them belong beside it rather than in whichever engine was written first.

Four survey figures the larger re-scan moved, none of them changing a decision: extensionless GUID hrefs are **4 of 43,353** (0.01%) rather than 0.1% — still matched on the GUID, because a suffix-keyed rewriter drops them silently; redundant self-reference fragments are **73%** rather than 84%, and of the 3,648 that name a real sub-anchor **22% dangle** rather than 6.1% — with 27 of 34 in a doc-set-level sample carrying SDL's own `missing-elem-id` marker, so the dangling is a *declared* source defect concentrated in a few doc-sets rather than a rewriting failure; images without `alt` are **92%** rather than 91%; and `h1` equals `DC.Title` in **18,351 of 18,542 (99.0%)** rather than 100%, so the slug falls back to `<title>` where the meta is absent. A title collision appears in 6 of 30 doc-sets in one re-sample and 15 of 22 in another, against the survey's 44% of 140 — the rate is a property of the doc-set, so every doc-set is treated as colliding.

Run over the real corpus, as 5b was: 13 cache trees spanning 6 to 727 topics, **19 doc-sets and 3,364 documents, no exceptions**. 81 topics collapsed as `republished-duplicate` — 2.3% of what was enumerated, which is the measured 2.2% `_unique_N` rate arriving through the identifier-pairing fix rather than through the stem. 39 files skipped as `not-a-topic`, 18 as `publication-homepage` (18 units carried metadata, and every one of the 19 kept `landing` at `None`). 1,742 asset references resolved against 1 dangling and 0 orphans; 17 `TOPIC_LINK_DANGLING`, 18 `TOC_ORPHAN` and 19 `TAIL_PAGE_MISSING` across the batch.

##### Phase 5d: WebWorks Engine

- [x] **WebWorks Engine** (`engines/webworks.py`) — full design in `architecture.md` §5.3, from a corpus survey on 2026-09-09 of **691 books / 195 versions / 110 products / 38,818 HTML topics / 32,690 images / 1.49 GB**. The oldest engine (2004–2015) and the only one whose output contains no semantic HTML: 121 `<ul>`, 25 `<ol>`, 455 `<li>`, 60 `<pre>`, 107 `<th>` and 334 headings across 29,712 topics. Against that, its runtime metadata is the best of the three — TOC, file index, titles and CSH are all present and all machine-readable.
  - [x] **The book is the unit of work, located by a directory holding `wwhdata/`** — never by a configured path, and the book root sits 1–4 levels below the version. A version ships **3.5 books on average** (median 3, max 30; only 25 of 195 ship one), which is the reverse of Flare. Every book also ships a self-contained `wwhelp/`, so a `wwhelp/` parent is **not** a doc-set: a **collection** is a directory whose `wwhelp/books.xml` names a `<Book directory="X"/>` with X ≠ `.`. 157 collections declare 602 books; 89 are undeclared.
  - [x] **Percent-decode `<Book directory>` and every `files.js` href.** 22 declarations are `directory="TIBCO%20Product%20Documentation%20and%20Support%20Services"`; decoding takes declared-book resolution from 580 to **602 of 602** and corpus TOC coverage from 85.7% to 87.1%. One rule, two places. Worth a fixture: `ipe-oracle/11.8.1/…system_messages_guide` reads as 5.6% TOC-covered undecoded and complete decoded.
  - [x] **Preserve the `books.xml` order — it is authored, and it is not alphabetical in 112 of 157 collections (71%).** Book display names come from each book's own `wwhdata/common/title.js`; `<Book>` carries only `directory` and `encoding` and **no name attribute anywhere in the corpus**. Emit a `BookGroup` level only when a collection declares more than one (136 of 157 declare exactly one, usually named after the collection).
  - [x] **TOC from `wwhdata/js/toc.js`** — `X = Y.fN(title, l)` chains where **the receiver variable carries the nesting**; parsed with a targeted expression, never executed. 68,970 entries over 645 books, depth never beyond 4. `toc.xml` is a *faithful* twin (0 differences in 641 books) and `toc.js` still wins on coverage — worth noting beside §5.4.4's `files.xml`, which is a *lossy* twin from the same generator. Neither can be assumed from the other.
  - [x] **`l=` indexes `wwhdata/common/files.js`, not `wwhdata/files.htm`** — this is the predecessor's central bug. Resolving all 39,647 anchored entries both ways and checking the anchor is actually present: **`files.js` 99.28%, `files.htm` 88.87%**, with 86 books strictly worse and several resolving 0. `files.htm` is read only for the 45 stripped books that have nothing else. Worth a regression test on one of the 0% books.
  - [x] TOC coverage **87.1% over the convertible population** (median 100% per book; below 50% in 12 of 642, three of them Sandcastle trees) — measured after excluding API trees, 1,211 runtime stubs and 1,478 front/back-matter files; the naive figure is 74.8%. **961 genuine orphans (3.2%)** go to an explicit "Unfiled" node, as in Flare and DITA. Enumerate the disk, not the TOC.
  - [x] **Two titles**: the topic title is the `files.js` label, equal to the topic's own `<title>` in **28,723 of 29,188 (98.4%)** with all 465 differences pure `&nbsp;` padding; the TOC label names the nav entry. There is no `h1` to fall back to — the topic's heading is a `div.N1Heading`.
  - [x] **Generate the collection landing page.** WebWorks has no `DefaultUrl` and both root candidates (`index.htm`, `wwhelp/wwhimpl/js/html/wwhelp.htm`) are frameset stubs, so the first `toc.yml` node is synthesized from `books.xml`'s root `name`. §6.2's "children and no page" rule then covers the book node too — **the book TOC is a forest, not a tree** (584 of 645 books have several top-level nodes).
  - [x] **Support and legal arrive as whole books as well as as nodes** — 31 standalone books (six with percent-encoded directory names) beside 67 legal and 66 support top-level TOC nodes. A standalone book collapses to a single tail node; §6.2's move-don't-append rule is unchanged; the label is carried from `title.js`, never constanted. Drop `lof`/`lot`/`ix` and the `FigureTitleLOF`/`TableTitleLOT` pages with a report line — "Figures" or "Tables" is the *first* top-level node in 246 books. `copyrigh.htm` is real content and converts.
  - [x] **Content is `body > blockquote` — one selector, 29,594 of 29,712 topics (99.6%), never nested, never more than one per file.** Per book it is binary: 634 at 100%, 5 at 0%. **All chrome is outside it** — logo table, `div.WebWorks_Breadcrumbs` (32,928 files), `WWHUpdate()`, `WWHRelatedTopics` — which is the exact reverse of Flare, where chrome lives inside the container. The 118 misses are the 2004–2006 flavour below.
  - [x] **Vocabulary mapping, because nothing is semantic.** Headings `N1Heading`/`N2Heading`/`N3Heading` → `#`/`##`/`###` (the numeral *is* the level — the one place WebWorks is easier than Flare); `div.Body` → paragraph, `div.ListContinue` indented into the preceding item; spans `Code`/`CodeItalic`/`CodeBold`/`Command`/`URL` → inline code, `Bold`/`uicontrol`/`wintitle`/`option` → bold, `Italic`/`Emphasis` → italic, `RunIn` → a bold run-in label. Also `uicontrol`/`codeph`/`xref` — DITA class names leaking through a FrameMaker template, mapping as in §5.2.5.
  - [x] **Every list is a table, and the shape is an exact invariant**: `div.<Kind>_outer > table > tr > td[div.<Kind>_inner] × 2`, marker cell then content cell. The `_inner`:`_outer` ratio is **exactly 2.000** for Bullet (232,846/116,423), Step, ListDash and StepInd across the whole corpus, so the transform is a shape match rather than a heuristic. Same shape carries the `Action`/`Explanation`/`Source` message triple.
  - [x] **Coalesce consecutive `*CodeLine` siblings into one fence.** 104,896 `WCodeLine`/`CodeLine`/`CodeLineFirst` divs against **60 `<pre>` in the entire corpus**; `&nbsp;` runs become spaces, inline span formatting inside the fence flattens to text, and fences are **bare** — there is no language attribute anywhere to read.
  - [x] **Admonitions are `table.IconTable` (12,866) and the prose is in the *second* cell.** The kind comes from `div.Icon<Kind>` in cell 1 — which holds only a `.gif` and a `&nbsp;` — and the alert body is cell 2. Emitting the icon div's content, as the predecessor does, yields an empty alert followed by a loose paragraph, 12,866 times.
  - [x] **Table discrimination is by parent class, not by `role`.** Layout tables are those whose parent is a `div.*_outer` **or** which carry `role="presentation"`; `role` alone marks 149,326 and misses **86,702 identical wrappers from older output that predates the attribute**, each of which would become a one-column pipe table. Content tables are those with `div.CellHeading`/`div.CellBody` cells; they have **no `<th>`** (45 corpus-wide) and 98.5% put `CellHeading` in row 1. **50.5% are GFM-safe**; the rest pass through as HTML (multi-block cells 9,635, nested 3,815, spans 1,791). **Figure captions precede their figure** — 7,316 of 7,442 `div.FigureTitle` are followed by the sibling holding the image — while 97.4% of `div.TableTitle` are the last thing in a `<caption>`.
  - [x] **`javascript:WWHClickedPopup('<book>','<file>#<anchor>')` is 99.7% of in-content cross-references and both arguments are recoverable.** 89,125 of them, **every one anchored**; same-book resolves 100%, cross-book 52.6%, and **the §5.4.3 version-wide fallback rescues exactly 0** of the 711 that dangle — they name books the package does not ship, so a miss is a source defect, emitted as plain text and counted. `span.LiveLink` (85,719) is the wrapper and **must not be mapped to plain text**.
  - [x] **Emit an anchor only where something references it.** 1,319,510 `<a name>` inside the content (~43 per topic, 96.5% bare integers), of which **85,219 (6.46%)** are targeted by a TOC fragment, a CSH case or a popup; references resolve at **99.81%**, so a dangling one is reportable rather than expected. The generator wraps each block's *leading text* in the anchor, so an `<a>` without `href` is both anchor and text: keep the text in the block, put the name on the block. Unwrapping to text alone — the predecessor's `_inline()` — is silently right for the prose and destroys every link target in the corpus, CSH included.
  - [x] Content images keep their source filename; `tpl/` is skin and is **never copied** (14,467 references). **`alt` is a skin marker, not a caption** — the 22,126 `<img>` with no `alt` are precisely the 22,126 under `images/`, and all 14,467 `tpl/` icons have one, so captions come from the adjacent `div.FigureTitle`. Same finding as DITA's 91%-no-alt (`architecture.md` §5.2.6), and the predecessor's alt-text renaming fallback would fire on 100% of content images here.
  - [x] **Decode by the declared `charset`, defaulting to UTF-8.** Of 37,658 files, **213 fail a strict UTF-8 decode and all 213 declare `iso-8859-1`**; 36,215 declare `utf-8` and 1,123 declare nothing. In this corpus that rule is never wrong.
  - [x] **Skipped, all counted**: `wwhdata/`+`wwhelp/` (read, never emitted — prune the walk at both); 1,211 `index.htm`/`wwhsec.htm` framesets; `tpl/`; generated `lof`/`lot`/`ix`; and **two API-reference generators inside WebWorks books** — Javadoc under `api/javadoc/` (6 books, 4,508 files) and **Sandcastle** under `api/dotnet/Help/` (3 `activespaces_remote` books, 3,344 files). The Sandcastle tree is what makes 3 of the 12 sub-50%-coverage books; **§6.3's marker list needs the `Index.aspx` / `FillNode.aspx` + `Sandcastle Help File Builder` form added**, since `fti/` sits one level below and claims a narrower root.
  - [x] **45 stripped books convert content and produce no navigation** — `wwhdata/files.htm` only, 1,395 topics across 18 versions, 98.9% indexed. Reported, not skipped. They are also why `wwhdata/` beats `wwhelp/` as the detection marker.
  - [x] **A second markup flavour, 5 books and 118 topics**: `businessconnect_remote/5.0.0_july_2006/html/{host,install,user}`, `businessworks_integrationmanager_plugin/1.0.0_october_2004/html/im_pal`, `hawkjmx/2.1.0/html/usr` — 2004–2006 output with real `<h2>`/`<p class="pBody">`/`<pre>`, `<a name>` *preceding* each block, plain relative links and **no blockquote at all**. Detected by the container test and routed to the generic HTML path.
  - [x] **Detector corrections, with tests** (`design.md` §7.1–§7.2): `wwhdata/` alone is **100% precision and 100% recall over all 1,822 cached versions** (195, being the 176 WebWorks-only plus all 19 Flare+WebWorks bundles — on which *both* engines have work); `wwhelp/` is 91.3%; the predecessor's `wwhelp/books.htm` is **72.3%**; and the WebWorks **generator meta tag is 1.5% recall** — corroboration only, and a null result from it means nothing.
  - [x] **Inherit from the predecessor deliberately** (`architecture.md` §5.3.10). Take: `soup.find("blockquote")`, `_SKIP_FILENAMES` (plus `index.htm`/`wwhsec.htm`), the `N?Heading` numeral→level mapping, and `_SPAN_MAP` **minus `LiveLink`**. Reject: `read_files_index()` reading `files.htm`, `_inline()` dropping anchors, `LiveLink`→plain text, the icon-cell admonition dispatch, per-div code fences, `books.htm` detection, `is_version_level_books()` counting `/` in hrefs where `books.xml` answers exactly, and `build_csh_maps.py` entirely (superseded by `topics.js`, §5.4.4).

**Landed as specified** (2026-09-11), 840 tests passing (was 773). No new findings codes — the register closed at 5b and every code §5.3 needs was already there. Two modules again, on 5b's precedent: `engines/webworks.py` holds the transform and `engines/webworks_toc.py` the four runtime readers (`files.js`, `toc.js`, `books.xml`, `title.js`), which are JavaScript literal parsing and share nothing with the walk. Eight things the checklist did not anticipate:

- **A procedure survives being interrupted, and no class list predicts where.** Over 3,037 topics a run of `_outer` list items is broken **4,625 times**, and in **1,271** of those the next marker is the *successor* of the last one — the author numbered one procedure and set something between two of its steps. Rendering each fragment as a fresh list restarts a nine-step procedure at 1 three times over, which is what a run-of-adjacent-siblings reader does. The interrupters do not sort: `Body` breaks a run 890 times and continues it 24, `ListContinue` 1,302 and 586, `Anchor` 246 and 163, `FigureTitle` 240 and 153, `IconTable` 325 and 123, `CodeLineFirst` 107 and 80. The **marker** sorts them exactly — it is the generator writing down which list an item belongs to — so the run extends when the next `_outer` of the same kind carries the next ordinal and the interruption becomes content of the step before it. Both readings of an ambiguous marker are kept and compared within one scheme, so `h.` is followed by `i.` and `i.` by `ii.` and neither makes the other a successor. One guard overrides the numbers: a heading in the gap ends the list, because across `N2Heading`/`MinorHead`/`N3Heading` that gap occurs 987 times and the numbering continues through it **once**.
- **Re-parenting and run replacement are the same bug seen twice.** Swapping a run for the list it became extracted every member of the run — including the nodes just moved *into* an `<li>`, which pulled each of them back out and deleted it. It had been silently dropping all 1,302 `ListContinue` continuation paragraphs and every note set inside a procedure since the first draft; it only became visible once bridging started moving things. Replacement now removes only the members still sitting where the run was. Confirmed on the corpus by the totals moving the right way: 23,878,288 → 24,119,342 characters and 880 → 916 resolved asset references.
- **The `hr` above a code block is the box FrameMaker drew, not a thematic break.** The corpus has 7,585 `hr` (5,867 unclassed, 1,100 `Line`, 618 `WLine`) and almost all of them are chrome that the container test already discards. Of the ones that survive into emitted output, **44 of 44 abut a code fence**. The fence already draws the box, and a `---` between a paragraph and its example reads as a section change the page never made, so a rule adjacent to a coalesced fence is dropped.
- **`copyrigh.htm` is the legal page, and only the filename says so.** It ships in **101 of 120 sampled books** and is titled `Important Information` in **99** of them — the same licence/trademark/third-party boilerplate Flare files under `legal_notices.htm`. `is_legal_label` matched the 5 books with a spelled-out `copyright.htm` and none of the 101; matching on the *title* instead would take every topic a writer called "Important Information" with it. Adding the truncated `copyrigh` stem to the shared predicate in `engines/base.py` takes the batch from **2 units with a legal page to 57 of 70**, and `TAIL_PAGE_MISSING` from 31 to 18.
- **The tail pages are not in the TOC, so a TOC-only search cannot find them.** `copyrigh.htm` is the second-largest orphan group in the corpus (446 books ship it; 601 ship `title.htm`) and it is in the TOC of almost none of them. The tail search therefore falls back to the whole document set, sorted, so a book with two candidates answers the same way every run.
- **`Chapter_outer` is a heading, not a list.** It looks like every other `_outer` and it is not one: in **0 of 185** topics that contain it does an `N1Heading` also appear. It is how this generator writes the chapter title, so it renders as the topic's `#` rather than as a one-item bullet list — which is what a purely shape-driven reader produces.
- **The `_outer` shape is stronger than §5.3.7 claims, in the two ways that matter.** Every one of **10,252 sampled `_outer` tables has exactly two cells** — so the marker/content split needs no fallback — and **no `_outer` is ever nested inside another `_outer`**, nor does any marker cell carry a `width`. Nesting depth is carried entirely by the kind name (`ListDash` inside `Step`), which is why the transform can be a flat scan with a stack keyed on kind rather than a recursive descent.
- **Cross-reference classification has no residue.** Over 3 versions and 575 emitted documents the links come out as 663 same-book anchored, 188 image, 166 external, 88 cross-book `../`, 10 same-page and **0 unclassified** — so the predecessor's third bug (popup arguments read as one opaque string) is not reproduced, and the 4 `TOPIC_LINK_DANGLING` in the batch are the source defect §5.3.8 predicted rather than a rewriting failure.

Five survey figures the re-scan moved, none of them changing a decision. **`files.js` resolves 68,915 of 68,915 anchored TOC entries across all 691 books — 100.0000%**, against the survey's 99.28%; `files.htm` resolves **88.43%** with **98 books at zero**, so the gap the predecessor's bug opens is wider than measured, not narrower. The **45 stripped books ship no `toc.js` either**, which the checklist's phrasing implies is a `files.htm`-versus-`files.js` choice: there is no TOC to choose for, and "content but no navigation" is the whole of their behaviour. The `files.js` label equals the topic's `<title>` in **30,537 of 30,601 (99.8%)** rather than 98.4%, and the 64 differences are *not* all `&nbsp;` padding — most are `&amp;` entities and stray tabs, but a few are genuinely different cover titles, so the label still wins. The TOC is a forest in **583 of 645** books (391 of them with six or more top-level nodes, 61 single-root, 1 empty) and its **maximum depth is 3**, not 4, with only 258 entries that deep; 55 of 68,970 entries carry a non-integer `l`. And the charset rule holds on a different population than surveyed: over the **30,603 indexed topics** every file declares a charset (30,307 `utf-8`, 294 `iso-8859-1`) and 196 fail a strict UTF-8 decode — the survey's 1,123 files declaring nothing are files outside the index, which are not converted.

Run over the real corpus, as 5b and 5c were: **13 version trees, 70 books, 3,625 documents, 24.1 MB of Markdown, 0 exceptions** in 182 seconds. Every one of the 3,625 is titled; 15,326 anchors are emitted; 916 asset references resolve against **1 dangling and 0 orphans**, with 394 `tpl/` skin references correctly never copied. Skips: 124 `runtime-stub`, 24 `generated-list`, 4 `empty`. Findings: `TOC_ORPHAN` 244, `NAV_NODE_DROPPED` 28, `TAIL_PAGE_MISSING` 18, `CONTENT_MISSING` 4, `TOPIC_LINK_DANGLING` 4, `ALERT_LABEL_UNMAPPED` 1. `landing` is `None` in all 70, as §5.3.5 says it must be — Phase 6 synthesizes it.

##### Phase 5e: DocBook Engine

Last by dependency, not by priority: it was the only engine with no design, so it is the one whose survey benefited most from three converters already having run against the spine.

- [x] **DocBook Engine** (`engines/docbook.py`) — full design in `architecture.md` §5.6, from a corpus survey on 2026-09-11 of **10 versions / 2 products / 11,689 prose pages**. Scope confirmed exactly as scoped on 2026-09-09: `str` (**TIBCO Streaming**, 6 versions: 11.1.0–11.1.3, 11.2.0, 11.2.1) and `sfire-sfds` (**Spotfire Data Streams**, 4 versions: 10.6.5, 10.6.6, 11.1.0, 11.1.1). 38,178 HTML files and 865 MB, the largest per-version packages in the corpus, and the most uniform output of the four engines — one generator, one stylesheet, one class vocabulary, ten years apart.
  - [x] **The unit of work is the version, rooted at `html/`, and it is located by where the stylesheet link lands.** A `str` package ships up to eight **byte-identical duplicates** of a guide — the same tree at the version root and again under `html/` — and they hold DocBook pages, so a "holds a DocBook page" rule converts eight guides twice. The real root is the directory whose pages' `<link rel="stylesheet">` resolves *within* it; that selects exactly `html` in 10 of 10 versions and rejects all 42 duplicates. `SKIN_PREFIXES[DOCBOOK] = (("css",),)`.
  - [x] **`div#mainContent` is both the content container and the whole of the chrome removal** — present on 1,178 of 1,178 pages, with the header, `p#mainhelp-navmenu`, breadcrumbs and `div#footer` all *outside* it. The exact reverse of Flare and the same shape as WebWorks. There is deliberately **no `<body>` fallback**: it would emit the banner and breadcrumbs as prose, so a page without the container is a counted `CONTENT_MISSING`.
  - [x] **Navigation from three sources in one pass** (§5.6.5): the `p#mainhelp-navmenu` tab strip fixes the top-level order and names 13 of 24 guides; each guide's `div.toc` nests its pages (5,527 same-directory links, 16 self, **0 cross-directory**, so a guide's TOC never reaches outside it); and a **two-hop link graph** from the book page covers the three guides that ship no `div.toc` at all. Recursive TOC coverage is 100% in 21 of 24 guides; the graph takes unfiled from ~430 to **42 of 1,178 (3.6%)**, which go to the guide node in source order.
  - [x] **A part page's `div.toc` is a copy of the slice its book already placed.** The recursion is what reaches a section the book page never named; without a filed guard it emits every such section twice. A second sighting becomes an anchor node where the entry carries a fragment, and nothing otherwise.
  - [x] **`<title>` is the title, and a page that opens at `h2` has that heading promoted rather than joined.** `<title>` equals the titlepage heading on 1,094 of 1,178 pages; of the 921 pages corpus-wide whose first heading is not an `h1` — every `div.refentry` and every generated index — **921 of 921 have first-heading text exactly equal to `<title>`**, so it *is* the page title one level down. Prepending a `#` above it would give the page two titles.
  - [x] **Mapped spans are unwrapped before they are wrapped.** `span.bold` (3,145), `span.command` (2,088) and `span.keycap` (1,235) already contain a `strong`, and `**` around `**` renders `****`; 661 `span.emphasis` contain an `em`, which is why `emphasis` is never mapped at all. Admonitions are `div.note`/`tip`/`important`/`warning`/`caution` (535/52/211/33/239) with the printed label in a direct `h3.title` that GFM draws itself and so is deleted. Code is `pre.programlisting` (2,721), `screen` (177) and `synopsis` (61) — **bare fences, because nothing in the markup carries a language**.
  - [x] **1,126 `div.mediaobject > table` are layout** — one centred cell holding one image — and 192 `table.simplelist` are lists. Both are unwrapped; passing them through gives 1,318 one-column pipe tables. `div.figure`/`div.example` put their `p.title` caption *before* the content, as in WebWorks.
  - [x] **Anchors: 10,753 `a[name]` are defined and 5,539 are ever referenced; all 3,347 `a.ix` are dropped.** The index anchors' `name` is prose with spaces and **0 of 3,347** are targeted by anything. No fragment in the corpus resolves to an element `id` — 5,539 of 5,548 hit an `a[name]`, 9 hit nothing — so the anchor table is built from `a[name]` alone and the 9 are reported.
  - [x] **Tail pages come from `div#footer`, not from a title search.** `is_legal_label` matches "third party", and `apiguide/thirdpartylibs.html` — "Using Third-Party JARs and Native Libraries", a topic about packaging — sorts before the real notice. The footer declares both pages by `li` id on 100% of sampled pages, which is the source of truth used.
  - [x] **Four generators ship in one package, and the prose is a quarter of the files.** `html/apidocs` alone is 2,265–2,481 files. Skipped by generator marker as well as by Stage 4's recorded API roots, so a `--input` run with no recorded roots does not convert 2,400 Javadoc pages as prose: `javadoc`, `doxygen` and `doxia` are named and counted rather than silently dropped.
  - [x] Detection is unchanged and stays content-signature-only — the `DocBook XSL Stylesheets` generator comment, with no marker-file pass possible (`design.md` §7.1). It is the one engine pass 1 cannot see, and it was already correct: `decided_by=2` in all 10 versions.
  - [x] **No CSH reader** — DocBook ships none, in either product (`architecture.md` §5.4, `design.md` §9.2). The CSH mapper stays a three-reader component.

**Landed as specified** (2026-09-12), 871 tests passing (was 840). One module, `engines/docbook.py`: there is no runtime data format to read here, so the 5b/5c two-module split has nothing to split. No new findings codes — the register closed at 5b and every code §5.6 needs was already there. Five things the checklist did not anticipate, one of them a spine fix outside the engine:

- **The DITA heading rule is wrong for DocBook, and the corpus says so 921 times.** §5.6.6 was drafted from §5.2's rule — prepend `# <title>` when the body does not already open with one — which is right for SDL DITA and wrong here. Of 11,689 pages, 10,768 open at `h1` and **921 open at `h2`**: every `div.refentry` and every generated index. In **921 of 921** the heading's text is exactly `<title>`, so it *is* the page title one level down, and prepending would have told 921 pages they have two titles. The rule became promotion — `h1` leaves alone, a non-`h1` first heading is renamed, and only a container with no heading at all gets a prepended title, which no page in this corpus is. §5.6.6 was rewritten to match before the code was.
- **The `--input` path never saw an API root, and DocBook is where that finally hurt.** `ConversionContext.api_roots` was filled from Stage 4's record alone, so a `--input` run — no catalog, no extract — offered every generated reference tree to the converter as prose. Flare, DITA and WebWorks survived it because their own markers catch their own generators; a DocBook package's `html/apidocs/dotnet` is **1,466 Sandcastle pages** whose generator is in no marker list, so they fell into the generic `not-docbook` bucket and were named as "not this engine" rather than as API reference. `driver._api_roots` now returns the recorded roots **or** `find_api_roots(tree)`, mirroring the `_csh_sources` fallback one method below it; §6.3's rule that Stage 4's record wins is intact, because the fallback only runs when there is no record. It has its own driver test.
- **`TOC_ORPHAN` was counting half the orphans.** The link graph appends a page it reached but no TOC filed to that page's guide node, which is the right output and made the page invisible to the count — only the pages that reached *no* guide were reported. The engine's headline navigation figure was therefore understating itself by exactly the cases the graph fixed. Both populations now feed one record, which is why the batch's 286 is larger than the survey's 42-per-version reading and still 2.4% of 11,689.
- **The legal page is a different file in each product, and only the footer knows.** `str` files it as `welcome/legal-and-third-party-notices.html` and `sfire-sfds` 10.6.x as `welcome/copyright.html`. Reading `li` ids out of `div#footer` resolves legal *and* support in **10 of 10** versions with **0 `TAIL_PAGE_MISSING`** — the outcome §5.6.9 predicted, against a title search that would have taken `apiguide/thirdpartylibs.html` in `str` and found nothing at all in `sfire-sfds`.
- **A fragment that resolves to nothing is now reported rather than emitted.** 9 of 5,548 fragments hit no `a[name]`, and the first draft passed them through as live `#`-links into pages that have no such target. They are dropped and counted as `TOPIC_LINK_DANGLING`, which is the same treatment §5.1 gives a dangling topic link and the reason the batch's 780 is a source-defect figure rather than a rewriting one.

Run over the whole DocBook corpus, as 5b–5d were: **10 version trees, 10 units, 11,689 documents, 0 exceptions** in 1,066 seconds. That is 11,689 of 11,689 marked prose pages — 100% coverage — with 11,679 of them in the nav tree and the other 10 the hoisted landing pages. `landing` is real in 10 of 10, which no other engine manages: DocBook is the one generator that ships a book page. Findings: `TOC_ORPHAN` 286, `TOPIC_LINK_DANGLING` 780, `DOCSET_SKIPPED` 51, and nothing else. A deep pass on `str/11.2.1` with Stage 4's API roots supplied gives the per-version detail — 1,178 documents, all titled, 10.8 MB of Markdown, 5,554 anchors, **2,118 references resolved against 0 dangling and 0 skin**, 1,272 orphan assets of 2,630 candidates (48%, against Flare's 54.6%), skips `api-reference` 2,227 / `not-docbook` 48 / `foreign-generator` 45, in 62.6 seconds.

### Phase 6: AEM Architecture Synthesis & Publishing Layout

> **Scope boundary (2026-09-09, user decision).** **Git operations are out of scope for this tool.** `docushift sync` organizes the output into repo-shaped directory trees under `--target-dir` and stops; `git init` / `commit` / `push` / repository creation and every branch, review and PR policy are picked up separately, by whoever owns the publishing repositories. Nothing about the *layout* changes — the two-tree split, the doc-class routing and the absolute cross-tree links are all properties of what gets written (`architecture.md` §6.0). No GitHub credentials, no `gitpython`/`gh` dependency, and no repository state for this tool to get wrong.

> **Split into 6a–6d (2026-09-12), and the seam is "what makes the converted tree navigable" against "where it gets published".** Phase 6 as written is two stages in one checklist — Stage 6 synthesizes navigation into the output tree, Stage 7 distributes that tree plus four other doc-classes into two repo-shaped trees — and it is larger than 4a, 4b-1, 4b-2 and 5a put together. The cut follows the stage boundary the architecture already draws (§6.0 against §6.1), then splits the distributor by *what it moves*, because each kind needs a different thing that does not yet exist: `online-help` needs the tree naming and the dots-to-dashes boundary, the three document doc-classes need a router and `pypdf`, and `-resources` needs the catalog-driven archive index and both trees on disk before a link can cross between them. **6a is the only one that is not filesystem plumbing** — it is where the three engine-neutral node rules that four engines have been reporting into finally run.
>
> - **6a — Navigation synthesis.** The three node rules, the cross-unit assembly, `toc.yml`, generated container pages, the version `index.md`, and the `nav.yml` / `metadata.yml` template rework. Ends with the converted tree navigable on its own, before anything is published.
> - **6b — The distributor spine and `online-help`.** `docushift sync`, the tree names, the dots-to-dashes boundary, the per-doc-class replace-wholesale rule, product-level `metadata.yml` and per-doc-class `version.yml`.
> - **6c — The document doc-classes.** §10.4's router, the de-duplication, §10.5's `index.md` + `toc.yml`, and the `pypdf` title chain.
> - **6d — The `-resources` tree and the cross-boundary rewrite.** Verbatim `api-references`, §10.6's catalog-driven `archives/` index, §10.7's absolute-URL rewrite, and §8.4's real validation assertions. *(Landed 2026-09-15 without the last two: validation was deferred to Phase 7 as planned, and §10.7 followed it once the links turned out not to survive conversion — §6.4.2.)*
> - **6e — The cross-boundary rewrite, at conversion time.** Added 2026-09-15, after the deferral turned out to rest on an overstated cost. §10.7's class 1 only, and it is a Stage 5 edit: the rewrite cannot run in Stage 7 because the link is already gone by then, and it does not need to — the driver can hand the engines the published URL the same way it hands them `api_roots`.

#### The AEM artifact contract — supplied 2026-09-10, supersedes the placeholders

The 2026-09-09 placeholder decision is **closed**: AEM has named the artifacts. `nav.yml` is dropped outright, `meta.yml` becomes `metadata.yml` with a real two-key spec, and a new `version.yml` drives the version drop-down. `design.md` §10's "two of the four templates are placeholders" paragraph and its §12 index row go with it.

```
tibco-ems/                       <- product level
├── metadata.yml                 csg-product: TIBCO EMS
├── online-help/
│   ├── version.yml              the version drop-down, one per doc-class
│   └── 10-4-0/                  <- version level
│       ├── metadata.yml         csg-version: 10.4.0
│       ├── toc.yml
│       └── csh.yml
└── user-guides/
    ├── version.yml              lists only the versions THIS doc-class has
    └── 10-4-0/
        ├── metadata.yml
        └── toc.yml
```

#### Phase 6a — Navigation synthesis

**Closed 2026-09-12** (`converter/navigation.py`, wired into `converter/driver.py`; as-built in `architecture.md` §6.5). Two sub-items stay open on purpose: version-level `metadata.yml` for the three document doc-classes is 6c's to emit, and the docs-tree-only rule needs a `--target-dir`, which arrives in 6b.

**Grounded 2026-09-12 against the html-to-md cache.** Three things §10 does not say had to be measured before this could be a checklist, because §10's node rules were written when Flare was the only engine and a version was one output root. The `metadata.yml` template lands here and 6a emits it for `online-help`; the other doc-classes emit the same template in 6b and 6c.

- [x] **Synthesis runs inside the conversion build, before the swap** — it is a stage, not a command. `driver._build()` iterates `handler.units()`, writes each unit, resolves CSH and swaps staging over target; it never reads `unit.nav`, `unit.landing`, `unit.support` or `unit.legal`, so the node list four engines have been reporting is discarded today and nothing persists it. The alternative — write the nav to `state.db` and add a `docushift nav` command — stores a derived artifact whose only consumer runs milliseconds later, and forces a re-run to decide whether to trust it. Generated container pages are Markdown documents that must land in the staging tree, and writing them after `swap()` would write into a live tree.
- [x] **Cross-unit assembly: one unit contributes its nodes directly, several get a node each.** `toc.yml` is one file per *version*, but engines emit one `Unit` per output root / doc-set / book and nothing said how they combine. Measured over 500 versions: **WebWorks is multi-unit in 128 of 142 versions (90.1%)**, median 3 and up to 9; Flare 15 of 157 (9.6%), SuiteHelp 5 of 108 (4.6%), DocBook 0 of 2. Multi-unit is the normal case, not an edge. The rule mirrors §5.3.3's existing "emit a BookGroup level only when a collection declares more than one" — a lone unit must not gain a wrapper node naming the directory it happened to sit in.
- [x] **Unit order is the engine's order, never re-sorted.** WebWorks returns books in `books.xml` declaration order, which is non-alphabetical in 71% of collections; sorting here would undo 5d.
- [x] **A unit label needs a chain, because `Unit` has no title slot.** First hit wins: `unit.metadata` (`book_title` for WebWorks, which `_metadata()` already carries alongside `collection_name`, `book_group` and `book_order`; `publication-title` for SuiteHelp) → the unit's landing-page title → the directory stem with `[_.-]+` collapsed to spaces. Raw stems are unreadable as labels — `doc/relnotes`, `html/tib_adas400_concepts`. Add the `title` slot to `Unit` rather than inferring it in the synthesizer: the engine already knows, and a second guesser would drift from the first.
- [x] **The version-level support/legal tail is positional, not content-deduplicated.** §10's "one legal node, not two" assumed a one-root version. Measured over 400 versions: **105 multi-book versions carry a legal page in more than one book, and in 83 of them the copies are not byte-identical** — but diffing three 6,950-byte `copyrigh.htm` copies in `activematrix-adapter-for-peoplesoft/6.0.0-december-2009` shows the only difference is FrameMaker anchor ids (`<a name="113179">` against `<a name="113190">`); the prose is identical. A hash-based dedupe would therefore keep all nine copies. **The first unit in unit order supplies the version's support and legal nodes; the other units' copies are dropped from the version nav**, counted as `NAV_NODE_DROPPED`. The files stay converted on disk — a CSH identifier or an inbound link may still reach one.
- [x] **The three engine-neutral node rules** (`design.md` §10, `architecture.md` §5.1.5) run here, once, over the assembled version tree — after unit assembly, so "last two nodes" means last in the version and not last in each book.
  - [x] **First node is the version's landing page.** The engine reports it; if it is already a TOC node, move it to first, else insert it. It must never fall through to "Unfiled".
  - [x] **Generate a page for any node with children and no page.** Title from the node label, body a link list of its immediate children, `generated: true` in frontmatter so a re-run replaces it. Drop and count childless label-only nodes. Engine-neutral, but Flare alone produces 165 per 60 output roots (151 of them top level, 1,357 children).
  - [x] **Last two nodes are support then legal** — `Documentation and Support Services` second-last, `Legal and Third-Party Notices` last, both hoisted to top level. **Move, never append**: they are already TOC entries in 657 and 649 of 676 Flare roots, so appending duplicates the topic; and 18 legal nodes sit one level down and must be promoted. **One legal node, not two** — no separate third-party-notices page exists in the corpus (0 of 676) and the combined page has one `h1` and zero `h2`. Absent pages leave a shorter tail, with no generated stand-in. Tests: a root already support-then-legal last (610 of 676 — must come out unchanged), one with the support node first (4 roots), one with a nested legal node, one missing both, and a nine-book WebWorks version that must end with exactly one of each.
- [x] **No new finding codes.** `NAV_NODE_DROPPED`, `TAIL_PAGE_MISSING`, `TOC_ORPHAN` and `LANDING_PAGE_EMPTY` are already registered in `reporting/findings.py` with fixed severities, and 6a is the first code path to raise them. Needing a code that is not there means the rule is new, not that the table is short.
- [x] **`nav.yml` is deleted, not deferred.** Nothing consumes it, nothing implements it, and `toc.yml` was always the specified navigation artifact. Remove `config/aem_templates/nav.yml.j2`, its two references in the architecture diagrams (§lines 51, 1696), the §8.4 validation sentence that pairs it with `meta.yml`, and the `design.md` §12 index row. The Phase-1 scaffolding invented it; nothing since has needed it.
- [x] **`meta.yml` → `metadata.yml`, carrying only the `csg-*` keys.** `csg-product: <display name>` at product level, `csg-version: <catalog version>` at version level — **dotted, not dashed**: the folder carries the dashed form, and the metadata carries the version as the product names it. The ~11 invented fields in `meta.yml.j2` are **deleted rather than kept alongside** — they were marked in the file itself as measured against nothing, and shipping a guess beside a contract is what makes the guess look load-bearing. One level-parameterized `metadata.yml.j2` replaces the old template.
  - [ ] Version-level `metadata.yml` goes in **every doc-class version folder that receives a file**, joining the existing `index.md` + `toc.yml` rule (`architecture.md` §6.2.2). A folder that gets no file gets nothing.
  - [ ] Docs tree only. The `-resources` tree holds generated API trees and opaque ZIPs; neither is a product page and neither reads a `csg-product`.
  - [x] The grounded SuiteHelp input — `publication-title` / `release-version` / `release-date` from `GUID-*-homepage.html`, present in all 314 doc-sets that ship one — is **still collected but no longer emitted**. It becomes a cross-check against the catalog's `display_name` and `release_date` rather than a metadata source, since AEM named neither field. Phase 5's item is amended, not dropped.
- [x] **`toc.yml` for the version, and the version `index.md`.** One `toc.yml` per version folder, rendered from the assembled tree by `config/aem_templates/toc.yml.j2`; `index.md` is the landing page's own document, carrying the frontmatter the injector adds. A node whose document was never written is a `TOC_ORPHAN`; a landing page that converted to an empty body is `LANDING_PAGE_EMPTY`.
- [x] Frontmatter injector and landing page (`index.md`) generator.
- [x] **Docs in the same commit** — `architecture.md` §5.4.2 rewritten to the flat `csh.yml` (its six field rules reduce to three; the anchor and `also` rules are replaced, not deleted, so the reasoning that produced them stays readable), §5.4.5–5.4.6 validation, the two Mermaid diagram nodes naming `nav.yml`/`meta.yml` (lines 51, 1696), and §6.1's layout block gaining the product level and the per-doc-class `version.yml`; `design.md` §8.4, §9.4, the §10 placeholder paragraph, and the §12 index rows for 9.4 and 10; `user-guide.md` line 474 and the §499 layout block; `CONTEXT.md` a ledger row. **The Phase-1 template inventory at line 19 is annotated rather than rewritten** — it records what was true when it was written.

#### Phase 6b — The distributor spine and `online-help`

**Nothing here is navigation.** 6b moves the tree 6a made navigable into the publishing form and writes the two artifacts that live *above* a version folder. It is the first sub-phase with a `--target-dir` and the first that may write a dashed version string.

**Landed 2026-09-15** as `sync/distributor.py`, `sync/versions.py` and `config/aem_templates/version.yml.j2`, verified against the real catalog (`architecture.md` §6.6). Two items below stay open and both are 6d's: `publishing.yaml` gains `publish_base_url` and the doc-class-to-repo map when the cross-boundary rewrite needs them, and 6b writes no file that reads either. `[~]` marks the one bullet 6b completes only in part — the three document doc-classes are 6c's.

**Re-grounded 2026-09-15 against `config/versions.csv` and `config/products.csv`.** Every figure the 2026-09-10 pass measured reproduces unchanged: 1,377 ISO / 372 epoch-millisecond / 13 empty `release_date` over 1,762 active rows; 280 of 458 products multi-version against 178 single; 38 active versions on the largest (`spotfire-server`); 20 non-numeric version strings; 6 multi-version products carrying an undated version. Two corrections and three additions came out of the re-measure, and each of them changes a rule rather than a number:

- **The 20 non-numeric rows sit on 20 *distinct* products, one each — only 4 of those products are multi-version.** The checklist read as though 20 rows crowded 4 drop-downs; in fact 16 of them are the *only* row their product has, so in 16 drop-downs the artifact is the entire list. "Sorts last" is therefore almost never the visible behaviour, and the run report is the only place those 16 surface.
- **`convert_eligible` and "active" are the same 1,762 rows on the same 458 products**, exactly, today. The `version.yml` rule says active-only and the distributor walks convert-eligible; nothing distinguishes them at present, so the two must not be conflated in code — the moment a row is eligible but archived, or active but ineligible, a shared predicate would put a version in a drop-down that points at no folder.
- **Dots-to-dashes is injective on this corpus: 0 products have two active versions that collapse to one folder name.** So the boundary conversion needs no disambiguation rule — but the check is cheap and belongs in validation, because a future `6-2` alongside `6.2` publishes one version on top of another silently.
- **Two active version strings cannot be a path segment at all** — `Cloud™` (`tibco-cloud`) and `(iPaaS)` (`tibco-cloud-integration-ipaas`). Both are convert-eligible, both in scope, both the product's only active version. Dashing them changes nothing; they still carry a trademark glyph and a bracket pair into a directory name and a public URL. See the folder-segment rule below.
- **Nine `bu`/`family` pairs carry active versions**, so a full sync writes nine docs trees (and, in 6d, nine `-resources` siblings). The largest is `tibco`/`general` at 707 versions, which is what the run report has to stay readable at.

- [x] **The folder segment is `slugify(dashed version)`, and it is only ever computed at this boundary.** `10.4.0` → `10-4-0` unchanged for 1,760 of 1,762 rows; `Cloud™` → `cloud` and `(iPaaS)` → `ipaas` for the two that need it. Passing the raw string through would put a `™` in a public URL path and parentheses in a directory name; refusing to publish them instead would drop two in-scope products entirely, which contradicts the standing rule that a parse artifact is reported and not silently discarded. **The same predicate that fires `VERSION_NOT_NUMERIC` catches both**, so this needs no new code and no second definition of "looks like a version" — a row that is not `N(.N)*` is named in the report whether it was reshaped or merely sorted last.
- [x] **New `version.yml`, one per doc-class folder** (AEM, 2026-09-10 — it sits beside the version folders, not above the doc-classes). The version drop-down. Lists **active versions only** (archived ones live in the `-resources` archives tree), highest version first.
  ```yaml
  versions:
  - title: 10.4.0 (Feb 2026)
    path: /10-4-0
  - title: 10.3.1 (Aug 2025)
    path: /10-3-1
  ```
  - [x] **`title` is the catalog version verbatim**, plus the release date in `(%b %Y)`. No trimming to a marketing two-part form: `10.4.0` and `10.4.1` are routinely both active, and both would render as `10.4`.
  - [x] **`path` is the bare dashed version**, exactly as AEM's example shows — the file now lives inside the doc-class, so the doc-class segment would be wrong rather than merely redundant.
  - [x] **Each doc-class lists only its own versions.** *This deletes a rule rather than adding one:* the product-level placement needed a precedence chain (`online-help` → `user-guides` → …) to pick one doc-class per version, and a version with PDFs but no converted help was mis-filed by it. Per-doc-class files have no such choice to make, and a version missing from one doc-class is simply absent from that drop-down.
  - [x] **The list is the catalog's active rows intersected with the folders on disk — never the run's own write list.** `sync` takes the same `--product` / `--version` scope options as `convert`, so "what sync actually wrote" is the wrong source: a `--version 10.4.0` run over a product with 38 published versions would rewrite the drop-down down to one entry and unlink the other 37, and the tool would report success. The file is therefore rebuilt by *reading the doc-class directory after the copy*, so a version synced last month keeps its row and a version whose folder was removed loses it. This is the same "the disk is the record, not the run" reasoning §6.2.3 applies to `archives/` in reverse: there the disk is incomplete so the catalog wins, here the catalog is a superset so the disk wins.
  - [x] **The schema permits a hand-written entry with an absolute URL** (`path: https://…`), per the supplied example. DocuShift generates only the catalog-derived rows; it must not delete or reorder a row it did not write, or the first re-sync silently drops whatever a human added. **Mechanically this means `version.yml` is read before it is written** — a row whose `path` does not resolve to a directory this product's doc-class holds is carried through verbatim, in its original position relative to the generated block. A file that cannot be parsed is left alone entirely and named in the report; overwriting it would destroy the only copy of whatever a human put there.
  - [x] **`release_date` needs a third parser — epoch milliseconds.** Measured over the 1,762 active versions on 2026-09-10: **1,377 ISO dates, 372 epoch-millisecond strings, 13 empty**. The two formats currently documented (`architecture.md` §6.2.3: `November 2022` and ISO-datetime) were measured on *archived* `GA_date` and do not cover this column. 372 rows would render as garbage on a naive parse. **An undated version keeps its title without the bracket** — 6 of the 280 multi-version products have one.
  - [x] **Sorting is numeric-descending over the dotted components, not lexical.** `10.4.0` must outrank `9.3.0`, which string sort gets backwards, and the largest product carries **38 active versions**.
  - [x] **20 active rows carry a non-numeric version string** — `Server`, `Desktop`, `Edition`, `Services`, `Professional`, `10.x`, `Cloud™`, `(iPaaS)` and similar. These are upstream parse artifacts, not versions. They **sort last and are named in the run report**; they are not silently dropped, because the folder they name does get published and a missing drop-down entry would be unreachable. Re-measured 2026-09-15: the 20 rows are on **20 distinct products, one each**, and only **4** of those products are multi-version (`spotfire-desktop`, `spotfire-enterprise-runtime-for-r-server-edition`, `spotfire-server`, `spotfire-statistics-services`). In the other 16 the artifact is the product's only active version, so it is the whole drop-down and "sorts last" never shows — the report line is the only signal, which is why it is a `WARNING` and not a note.
  - [x] 280 of 458 products with active versions have more than one; the other 178 have exactly one. A one-entry `version.yml` is still written — its absence and its presence must not mean different things to AEM. Per-doc-class placement multiplies the file count by the number of doc-classes a product fills (up to four), and **the drop-downs will legitimately disagree with each other** — `user-guides` carries versions that shipped no converted help. That is the point of the move, not a defect to reconcile.
- [x] Workspace distributor — publishing form `{target_dir}/{docs-tree}/{locale}/{product}/{doc-class}/{version-dashed}/`, where the tree name comes from `ConfigManager.docs_tree_name()` (Phase 3.8); layout fixed in `architecture.md` §6.1. **Filesystem only** — it writes the trees and reports what it wrote; it does not publish them.
  - [~] Docs tree: `online-help/` (converted tree + navigation + `csh.yml`), `user-guides/` (PDFs), `release-information/` (relnotes + readme), `reference-documents/` (VPAT, licence, reminder notice, rest of `doc/`). **6b places `online-help` only** — the other three need 6c's router, and the spine must be provable before four doc-classes ride on it.
  - [x] **The source is `ConfigManager.output_path()`, and a version with no converted tree is an outcome, not an abort.** `sync` gets the same five-outcome table `convert` and `download` end with — synced / already current / no converted tree / skipped / failed — because it runs over the same selection and a partial corpus is the normal state, not an error. Stage 5 established the shape; reusing it means a `sync --all` over a corpus where 400 versions have been converted reports 400 and 1,362, rather than failing on the first gap.
  - [x] **Product-level `metadata.yml` is written per product, not per version**, at `{tree}/{locale}/{slug}/metadata.yml` with `csg-product: <display_name>` — the same level-parameterized `metadata.yml.j2` 6a shipped. All 458 products with an active version have a non-empty `display_name`, so the fallback chain 6a needed for page titles has no counterpart here; a blank would be a catalog defect and is a validation assertion rather than a silent blank file.
- [x] Dots-to-dashes version conversion at this boundary only (`10.4.0` → `10-4-0`); nothing upstream may see a dashed version. Verified 2026-09-15: injective over the whole catalog — **0 products have two active versions that dash to the same segment** — so no disambiguation is needed, only the assertion that keeps it true.
- [ ] **Extend `config/publishing.yaml`** — created in Phase 3.8 with the naming tokens; this phase adds `publish_base_url` plus the doc-class-to-repo map. The AEM host must not be compiled into the distributor; a staging target is a config edit. One path-template function serves both the file copy and the link rewrite, so the two cannot disagree — and it composes the tree name from the same `docs_suffix` the trees were written with, so a link cannot point at a repo name that was never created.
- [x] **Re-run behaviour is the only idempotency question**, and it is a filesystem one: a second sync over the same `--target-dir` must produce the same tree, replacing a version's doc-class folder wholesale rather than merging into it, so a topic deleted upstream does not survive as a stale file. No git state is consulted.
  - [x] **The wholesale replacement is exactly one directory deep, and naming what it must *not* reach is the whole rule.** `{product}/{doc-class}/{version-dashed}/` is built in a staging sibling and swapped over the target with `utils/swap.py` — the same build-and-swap the converter uses, for the same virus-scanner reason. It must not reach `{product}/{doc-class}/version.yml`, `{product}/metadata.yml`, or any sibling version folder; a swap scoped to the doc-class instead of the version would delete the 37 versions this run did not touch, which is the partial-sync failure again one level up.
  - [x] **Sync writes no `output/`-side state and reads no `state.db` record to decide what is current.** "Already current" is a content comparison against the target, not a recorded hash: the target directory is outside this tool's control — a human may have edited it, and 6b's own `version.yml` rule assumes they have — so a stored fingerprint would claim currency for a tree that no longer matches it.
- [x] **No new finding codes.** `VERSION_NOT_NUMERIC` (warning) and `VERSION_UNDATED` (note) are already registered against `Stage.SYNC` in `reporting/findings.py` and 6b is the first path to raise them; the folder-segment reshaping deliberately reuses the first rather than adding a third. Needing a code that is not there means the rule is new, not that the table is short — the same test 6a was held to.
- [ ] Only value still to supply: the `publish_base_url` string itself, once the AEM host is known. Deployment configuration, not design — nothing waits on it. **6b needs it for no file it writes** — the absolute-URL rewrite is 6d's — so its absence blocks nothing here.
- [x] **Docs in the same commit** — `architecture.md` §6.6 (new: the distribution mechanics, the `version.yml` assembly rule and the swap boundary), `design.md` §10.3 (new: step 1) and its §12 index rows, `user-guide.md` gaining a real `sync` section in place of the "Phase 6" stub, and a `CONTEXT.md` ledger row.

#### Phase 6c — The document doc-classes

**The three doc-classes that hold files DocuShift never converted.** Everything here routes and indexes what Stage 3 downloaded as-is — PDFs, readmes, licences — so it needs the router, `pypdf`, and its own templates, and none of it touches the converted tree. It is also the first sub-phase whose **source is the extracted tree rather than the converted one**: a version that never converted can still have eight PDFs to publish, so 6c's work is not a subset of 6b's, and one version can be `NO_OUTPUT` for `online-help` and `SYNCED` for `user-guides` in the same run.

**Re-grounded 2026-09-15 against the extracted cache** (1,822 versions under `html-to-md/cache/pub`; the `/Title` pass re-read all 5,007 PDFs). The 2026-09-07 and 2026-09-08 surveys reproduce almost exactly: 1,822 versions, 1,123 carrying `pdf/` and `doc/` at the root and 373 nesting them, 25 versions with both PDF folders sharing **178** filenames, **156** versions routing nothing, the 91 / 386 / 1,189 split across one, two and three doc-classes, **5,007** de-duplicated `user-guides` PDFs, a `user-guides` residue of exactly **4** files (`special-notes` ×2, `LiveViewWeb_NewNote` ×2, all genuine guides that merely contain the word "note"), and a title histogram of **70.8% usable / 27.9% blank** to the decimal. Six things the re-measure changed, and each of them changes a rule rather than a number:

- **The nested layout's document folder is `V/doc/doc`, and §10.4 locates only `V/doc`.** §6.2.1 has always said the pair nests as `doc/pdf/` **and `doc/doc/`**; §10.4 carried the shift for the PDF folder and dropped it for the document folder. Measured cost of the omission: **676 files in 346 versions go unrouted** — 376 `release-information`, 300 `reference-documents`, 0 `user-guides` (the nested PDFs were already reached through `doc/pdf/`). They are overwhelmingly `.txt` readmes and reminder notices, across **120 distinct products**. `V/doc` is *empty* in 346 of the 370 versions that have `V/doc/doc`, and in the other 24 it holds the same filenames one level up, which the existing de-duplication rule already resolves root-first. The locator becomes symmetric: **the PDF folder is `V/pdf` or `V/doc/pdf`, the document folder is `V/doc` or `V/doc/doc`, root winning in both pairs.**
- **The `\b` trap is twice the size §6.2.1 recorded, because the survey counted only one of the two folders.** 1,813 files in a PDF folder match the release-note pattern but not a `\b`-anchored one (1,743 after de-duplication, against the recorded 1,753) — and a further **1,108 in a document folder**, where the same miss sends a readme to `reference-documents` instead of `release-information`. Total exposure **2,921 files**, not 1,753. The rule is unchanged; the regression test is worth more than the survey implied.
- **11,633 was the pre-de-duplication count.** Routing the corpus under §10.4 as written yields **11,454** files after the §10.5 de-duplication (5,007 / 3,530 / 2,917), and **12,130** with the `doc/doc` fix (5,007 / 3,830 / 3,293) — **12,124 as built**, once the owning-root skip below hands `flogo-oracledb/1.2.1`'s six Flare files back to the converter. None of the 156 empty versions gains a doc-class from the fix and the 91 / 386 / 1,189 histogram is unchanged — the correction adds files to folders that already exist, and creates no folder.
- **"Only files directly inside these folders" costs exactly one in-scope file.** 117 document-extension files sit one level below a `pdf/` or `doc/` folder in a directory that is not `pdf`, `doc` or `html`: **116 of them are `ebx-addon`**, out of scope since Phase 3.5, and the 117th is a single file in `stat`. Separately, `doc/relnotes/` exists in 12 versions and holds no documents at all — `Default.htm`, `csh.js`, `.mcwebhelp`, `.mclog`: it is a **Flare output root**, which is Stage 5's business exactly as the rule says. The rule stands, measured rather than assumed.
- **A file the converter already claims must not be routed, and the corpus makes the case in one product.** `flogo-oracledb/1.2.1` ships its Flare help *as* `doc/`, so `doc/Default.htm`, `csh.js`, `Default.mcwebhelp` and `tp-html.mclog` are output-root files sitting exactly where the router looks. `find_output_roots` already identifies that directory as a root and `owning_root` already answers the question, so the router gains one guard and no new knowledge. It removes 6 of the 22 non-document files the corpus would otherwise publish; the remaining **6 genuine strays** (`context.xml`, `t1.aspx` ×2, and `rtview`'s chrome pages) land in `reference-documents`, which §6.2.1 already describes as the catch-all. Publishing 6 stray files across 1,822 versions is the price of not adding an extension deny-list — which would also have dropped the corpus's **5 genuine HTML release notes** and a `license.htm`.
- **The unreadable PDF is not one file, it is seven, and they do not all raise the same exception.** §10.5 records a single `PdfStreamError` on `TIB_mftcc_8.4.4_user_guide.pdf`; re-reading all 5,007 with `pypdf` 6.18.1 raises on **7 files across 4 distinct names** — that one `PdfStreamError`, plus **6 `ValueError`s** on `TIB_smap_1.0.0_install_guide.pdf` and on `silver-mobile`'s user and install guides, which recur across that product's versions. So the guard must catch `Exception` rather than a `pypdf` error type, and 7 is small enough to justify a finding code (see below). The junk count also moves slightly: **59 files (1.2%) in 35 distinct values**, not 65 in 37 — same filter, same conclusion.

- [x] **Document router** (`design.md` §10.4, settled 2026-09-07, corrected 2026-09-15) — source folder first, then name. `pdf/` defaults to `user-guides`, with release-note / VPAT / licence / reminder-notice pulled out; `doc/` defaults to `reference-documents`, with only the readme pulled out. New module `sync/router.py`.
  - [x] **Locate both folders at both depths** — `V/pdf` or `V/doc/pdf`, `V/doc` or `V/doc/doc`. 373 of 1,822 versions use the nested form, and 346 of them would otherwise publish none of their 676 readmes and notices.
  - [x] **Skip a file an engine output root owns**, using `engines.roots.owning_root` against `find_output_roots` — the same precedence Stage 4's inventory already applies in `_count_file`, so a file cannot be an output-root file in the inventory and a published document in the router.
  - [x] Pattern tests written against the **observed** spellings, not the expected ones: `tib_ems_relnotes.pdf`, `mft platform server v7.1 for windows release notes.pdf` (spaces), `tib_nimbus_9.1.0_licencing_doc.pdf` (`licencing`), `tib_ebx-addon_remindernotice.txt`, and `special-notes.pdf` which must stay in `user-guides`.
  - [x] Regression test for the `\b` trap in **both** folders: `_relnotes` must reach `release-information` from `pdf/` and from `doc/`. A word-boundary anchor misroutes 2,921 corpus files because `_` is a word character.
- [x] **Document doc-class index** (`design.md` §10.5, `architecture.md` §6.2.2, settled 2026-09-08) — `user-guides/`, `release-information/` and `reference-documents/` each get a flat `index.md`, a `toc.yml` and a `metadata.yml`. A copied PDF with no index is unreachable. New module `sync/documents.py`.
  - [x] **De-duplicate by lower-cased filename within each doc-class before copying**, root folder over nested. 25 versions carry both PDF folders and share 178 filenames; 24 versions carry the same readme in `doc/` and `doc/doc/`. Without this the same file is copied and listed twice.
  - [x] **A doc-class with no files gets no folder, no index and no `version.yml` row.** 156 of 1,822 versions route nothing at all; an index linking to nothing is a published dead end.
  - [x] **Title chain, first hit wins**: canonical kind name (adding `(^|[\s_.-])rtu([\s_.-]|$)` → Right to Use Terms, for titling only — it changes no routing) → PDF Info-dictionary `/Title` → filename stem with `[_.-]+` collapsed to spaces. Reproduced 2026-09-15: the kind name alone covers **100% of `release-information` and 97.7% of `reference-documents`** before a PDF is ever opened, and the `/Title` read supplies **70.8%** of `user-guides`.
  - [x] **Add `pypdf` to `pyproject.toml`** and read `/Title` with it — **never a byte regex**, which returns outline bookmarks (`'Basic Tab'`, `'Table of contents'`) while claiming 57% success. Verified 2026-09-09 against pymupdf over all 5,007 PDFs: byte-identical titles on the 5,006 both read, 4× faster. pymupdf is AGPL, pypdf is BSD-3-Clause.
  - [x] **Wrap the read in `except Exception`, not in a `pypdf` error type.** Measured 2026-09-15 over the 5,007: **7 files raise, and only one of them raises `PdfStreamError`** — the other six raise a bare `ValueError` from inside the parser. A failed read must fall through to the filename fallback exactly as a blank `/Title` does, so a damaged PDF is published and titled rather than skipped.
  - [x] **Junk filter**, falling through to the fallback: `untitled` case-insensitively, any title ending `.book`/`.fm`/`.doc`/`.docx`/`.pdf`/`.indd`/`.mif`, any beginning `Microsoft Word - `. All **59** junk titles in the corpus (1.2%, 35 distinct values) are the authoring tool's source filename.
  - [x] **Do not strip vendor, product or version tokens from the fallback stem.** A pass that did produced `'adix 2'`, `'dqid 3'`, `'1 0 0 installation'` — 82.9% of 3,352 derived titles were one-offs.
  - [x] **One kind-rank table, not one per doc-class.** VPAT, License Agreement, Reminder Notice, Right to Use Terms, Release Notes, Readme, then the unranked, ordered by title within a rank. Each doc-class holds a subset of the kinds, so a single list gives `release-information` its release notes first and `reference-documents` its VPAT first without a branch.
  - [x] New Jinja templates in `config/aem_templates/`: `documents_index.md.j2` and `documents_toc.yml.j2`. The existing `index.md.j2` is **body-only** — the converter's `_render` writes its frontmatter — and `toc.yml.j2` carries `children` and a precomputed indent for a nested tree; neither is reusable, and the document index must write its own frontmatter because no converter runs over it. Item shape: `title`, `path`, `type`, `bytes`.
  - [x] **The version folder gets a `metadata.yml` here too**, `csg-version: <dotted version>`, from the same level-parameterized `metadata.yml.j2` 6a shipped. This is the open sub-item under 6a's metadata bullet, and without it three of a product's four doc-classes would ship version folders carrying no version metadata — an asymmetry that would be an artifact of which stage happened to write the folder.
- [x] **The distributor places them** — `sync/distributor.py` gains `sync_documents`, beside 6b's `sync_one`. Same `--target-dir`, same `.part/` staging and `swap()`, same five outcomes, same one-directory-deep swap boundary.
  - [x] **`SyncResult` gains a `doc_class` field** and a run reports one row per (version, doc-class) that has something to say. `sync_one` keeps its signature and its meaning — `online-help` — so 6b's contract and its 20 tests are unchanged.
  - [x] **The two absences are different and are reported differently.** A version whose **extracted tree is gone** is one `NO_OUTPUT` row naming `docushift extract`, because it is recoverable; a version whose tree is present but **routes nothing** gets no row at all, because that is a fact about the package and 156 of 1,822 are in that state. Aggregating them would report 156 recoverable failures on every full run.
  - [x] **Currency is compared before staging, not after.** The copied files are compared against their sources by size and mtime (`filecmp.cmp(shallow=True)`, sound because the copy uses `copy2`) and the three rendered files by content, which is deterministic. 6b's shape — `copytree` into `.part/` and then compare — would re-copy every PDF on every run to answer a question the metadata already answers, and `user-guides` is the one folder in this pipeline where that is measured in hundreds of megabytes.
  - [x] **`finish_product` generalizes to every doc-class present** instead of returning early when `online-help` is absent, writing one `version.yml` per doc-class folder. 6b's assembly rule needs no change: it already takes `present` from the directory listing, which is exactly what lets the drop-downs legitimately disagree.
- [x] **One new finding code: `DOCUMENT_UNREADABLE`** (note, `Stage.SYNC`), raised when a PDF's `/Title` read raises. The file is still published and titled from its filename, so the note is the only signal that a shipped deliverable is damaged. **7 files in 5,007 raise** — single figures, which is what makes it a code rather than a rule; a note that fired hundreds of times would be describing the corpus, not a defect. A **blank** `/Title` is explicitly not reported: 27.9% of the corpus is blank, and that is the normal state. `DOC_REFERENCE_MISSING` and `ARCHIVE_ALSO_LIVE` stay 6d's, and `REACHABLE_IN_PHASE_6C` extends 6b's frozenset by the one code. *(6d then **deleted** `ARCHIVE_ALSO_LIVE` as unreachable and left `DOC_REFERENCE_MISSING` outstanding with §10.7.)*
- [x] **Docs in the same commit** — `architecture.md` §6.2.1 and §6.2.2 corrected in place (the nested document folder, the two-folder `\b` figure, the pre- and post-de-duplication counts, the seven unreadable files) plus a new §6.7 as-built; `design.md` §10.4 and §10.5 to **Built** with their §12 index rows; `user-guide.md` §4 gaining the three doc-classes beside `online-help`; a `CONTEXT.md` ledger row.

#### Phase 6d — The `-resources` tree and the cross-boundary rewrite

**The second tree, and the only work that needs both trees on disk.** A link cannot be rewritten to point at `-resources` until `-resources` exists, so this comes last. Everything 6b and 6c place is *derived* from the package; everything here is the package **verbatim** — Javadoc and Doxygen output copied byte-for-byte, and ZIPs that are not on disk at all.

**Re-grounded 2026-09-15** against the committed catalog (4,462 rows, 2,100 archived) and the extracted cache (1,822 versions; `apiref.find_api_roots` run over every one of them, 12-way, ~8 minutes). The 2026-09-09 figures behind §10.6 came from a **60-product sample of the live archive API** and the api-reference figures came from the predecessor's whole cache including products cut in Phase 3.5. Neither is the best evidence available now, and **ten things the re-measure changed are rules, not numbers**:

- **`-resources` is 13 products, not the corpus.** Corpus-wide there are 1,701 API roots in 158 versions across 29 products, but 1,190 of those roots are `ebx` and `ebx-addon`, out of scope since Phase 3.5. **In scope: 165 roots in 49 versions across 13 products — 45,427 files, 1.39 GiB** (`amx-bpm`, `bcce-edi`, `bcedi`, `bex`, `eftl`, `ems`, `ftl`, `msg-akd-repo`, `rtview`, `sfire-sfds`, `tea`, `tpm-rest`, `tps`). 45 of the 47 matching catalog rows are `convert_eligible`, so this is live work, not archaeology.
- **The folder list `{c,java,golang,tibdg}` is not what the corpus ships.** Observed leaf names, in scope: `lib` ×34, `java` ×27, `javadoc` ×20, `c` ×19, `dotnet` ×18, `sample` ×12, `html` ×10, `javadocs` ×9, `javascript` ×8, `cpp` ×4, `jsdoc` ×2, `web_client_javadoc` ×2. **There is no `golang` and no `tibdg` in scope**, and the two commonest names — `lib` and `sample` — are not language names at all but the two halves of a Javadoc pair (`api/java/lib`, `api/java/sample`). A fixed enumeration of folder names cannot survive contact with this corpus; the placement name has to be derived.
- **The leaf name cannot be the folder name. The relative path can.** Leaf names collide within a version in **16 of 49 versions** — `tps/6.2.0` has four roots named `lib` — while the relative path from the version root collides in **0 of 49**. Uniqueness is therefore free; readability is what costs.
- **19 of the 165 roots are copies of another root in the same version.** The extracts self-nest: `rtview/5.9.1-august-2011` contains itself four times over (`5.9.1-august-2011/tibco-rtview-5-9-1/5.9.1-august-2011/…`), `tps/6.0.0` carries `api/api/java/lib` beside `api/java/lib`, and `ftl` 7.1.2 and 7.2.0 ship `c`, `dotnet` and `java` both at the version root and again under `html/api-docs/`. Dropping a root whose `(file count, byte total, leaf name)` matches a shallower root in the same version takes **165 → 146** and removes **10 of the 11** remaining name collisions with them. Without it `rtview` publishes the same Javadoc five times.
- **All 165 roots ship their own `index.html`** — not 496 of 499. "No index for `api-references/`" is not a 99% rule with three exceptions, it is unconditional.
- **133 of 165 roots sit *inside* an engine output root**, so the api-reference copy is not a separate tree beside the help tree — it is carved out of the middle of it. The copy source must be the **extracted** tree, and the converter's existing skip is the only thing stopping Stage 5 and Stage 6d from both claiming those 45,427 files.
- **The api-root skip is currently costing 2,989 pages, in 5 versions, and 6d is where that surfaces.** `ftl` 7.0.0, 7.0.1 and 7.1.1 dump Doxygen's `annotated.html` directly into `html/`, which *is* the Flare output root — so `html` matches the api marker, `is_api_reference` is true for everything beneath it, and **746 + 757 + 816 = 2,319 `.htm` Flare topics are never converted**. `bex` 1.3.5 and 1.3.6 have the same shape one level down: `doc/html` is the DocBook root with a Javadoc mixed into it, and of its 803 HTML files **335 are DocBook pages** (`adminguide`, `architectsguide`, `developersguide`, `sizingguide`, `tuningguide`, `TIB_bex_installation`, `tib_be_extreme_getting_started`) — 670 pages across the two versions. This is a live Stage 5 defect that only an api-reference phase would ever look for.
- **The modern-Javadoc marker gap is real but not in scope.** `_MARKER_FILES` knows the frame-based layout and JDK 11+ emits none of it, which is why `ebx-addon/6.2.0` fragments into 80 package-level roots. Widening the list with `allclasses-index.html`, `allpackages-index.html`, `overview-summary.html` and `element-list` changes the in-scope count by **nothing: 165 → 165**. So 6d does **not** touch `apiref.py`'s marker set — the change would be all blast radius (Stages 4 and 5 both read it) and no benefit.
- **`release_date` on archived rows is neither of the two formats §6.2.3 documents.** Not one archived row is spelled `November 2022`. The 2,100 are **1,785 plain `YYYY-MM-DD` days** (31 distinct day-of-month values; `-01` is only 3%, so the days are real and not month-padding), **309 epoch-millisecond strings** across 138 products, and 6 empty. Normalising to `YYYY-MM` would throw away precision the catalog actually has, and the stated reason for doing so — "month is the precision the majority has" — is false for this column. `versions.release_month()` already parses both shapes; it is the *rendering* that has to change, not the parser.
- **`zip_url` is already absolute and the cross-link rule is dead.** 2,086 of 2,100 archived rows carry a full absolute URL and 14 carry none, so there is no `{base_url}{zipPath}` left to compose. And the cross-link: **0 of 2,100 archived versions are also live** — the catalog keys `product.versions` by version string, so one version being both is unrepresentable — and **0 archived rows are `convert_eligible`** (1,195 are RETIRED), so no archived version is ever published to `online-help/` for a link to point at. `ARCHIVE_ALSO_LIVE` cannot fire from any code path that exists.

Two further corrections to the sample's arithmetic, which change the shape of the phase rather than a rule: **43% of in-scope products have no archived rows** (sample said 28%) and **38% of multi-archived products disagree on version-order vs date-order** (sample said 28%). And the reach is smaller than "every product with history": a full sync selects 422 products, of which **178 have archived rows** (1,270 rows, across 9 `-resources` trees) — **150 in-scope products with archived history are never selected at all**, so their history is unreachable no matter what this phase writes.

**Landed 2026-09-15** as `sync/apirefs.py`, `sync/archives.py`, `config/aem_templates/archives_{index.md,toc.yml}.j2` and two new methods on `WorkspaceDistributor`, plus the Stage 5 containment fix in `apiref.py`. **1046 tests pass** (+48), lint clean. All four decisions the plan flagged were taken as recommended. **Two bullets below are `[~]` and one is `[ ]`, and none of the three is an oversight** — the rewriter turned out to need a converter-side change that does not exist (§6.4.2), so it moved to Phase 7 whole; `bex/1.3.5`'s half of the acceptance criterion fails for a reason in `engines/roots.py` rather than in `apiref.py`; and validation was deferred as recommended.

- [x] **`-resources` is a separate tree per family, a sibling of the docs tree** (`architecture.md` §6.3) — `ConfigManager.resources_tree_name()` already returns it (Phase 3.8), non-primary locales get none. Sync creates the directory; it does not create or push the repository. Both trees are written under the same `--target-dir` in one run, and the API references are placed **before** the docs tree so the ordering the rewrite would have needed is already true.
- [x] **`api-references/` placement** — `{resources-tree}/{locale}/{slug}/api-references/{version-dashed}/{name}/`, the same `{doc-class}/{version}` shape 6b and 6c use, so `utils/swap.py` keeps the identical one-directory-deep boundary and a version can be replaced without touching its siblings. (The spec's `api-references/{c,java,…}/` has no version segment; `ftl` publishes eight versions of its C API and they are not the same API.)
  - [x] **Roots come from `state.db`, with a locate-only-if-no-record fallback** — `version_metadata.api_roots`, written by Stage 4's inventory. The read itself moved to `apiref.recorded_roots()` when Stage 7 needed the same answer Stage 5 already had: §6.3 says the three stages share **one** record, and two functions parsing it is the first step towards two records. `_has_api_ref` is **0 for all 4,462 catalog rows**, so the catalog cannot be the source.
  - [x] **De-duplicate before naming**: sort by depth, drop a root whose `(files, bytes, leaf name)` matches one already kept. 165 → 146, and `rtview/5.9.1-august-2011` stops publishing five copies of one Javadoc.
  - [x] **Name from the relative path, with container segments dropped** — and dropped **wherever they sit, not only at the front**, which the plan did not say and the corpus required: `ems` ships its .NET tree at `html/api/dotnetdoc/html`, whose only informative segment is in the middle. Where *every* segment is a container (`html/apidocs`) the leaf is kept, because a nameless folder is not a folder. **Decision taken: (a)** — a collision demotes the **whole version** to full dashed paths, so one version's names are internally consistent.
  - [x] **Copied verbatim from the extracted tree, never converted.** Javadoc and Doxygen are not engine output; converting them turns working HTML into broken Markdown. No frontmatter, no rewriting, no index — the copy is the deliverable.
  - [x] **No `index.md`, no `toc.yml`, no `metadata.yml` inside a root** — all 165 ship their own `index.html`. The `api-references/{version}/` folder itself gets the version-level `metadata.yml` 6c writes; there is **no `version.yml`** either, because the drop-down is an AEM page control and these are copied Javadoc rather than AEM pages.
  - [x] **Currency by size and mtime, compared before staging** — folder names plus `(files, bytes)`, for 6c's reason at ten times the volume: 1.39 GiB re-copied per run to answer a question `copy2` already answered.
- [~] **The api-root / output-root conflict is a Stage 5 defect and 6d fixes it.** **Decision taken: inside 6d.** `apiref.swallows_output_root()` is the containment test and `find_api_roots(tree, output_roots=…)` applies it: when an api root is, or contains, an engine output root, the output root wins and the marker is re-tested below it. **The bullet's claim about `bex` was wrong** — "the DocBook engine's own `is_docbook_page` already rejects all 468 Javadoc pages, so the api skip is redundant there" is true and irrelevant, because `bex` never reaches the skip.
  - [~] **Acceptance is measured, not asserted.** `ftl/7.1.1` **passes**: api roots go from `["c", "html", "java"]` to `["c", "java", "html/api-docs/c", "html/api-docs/java", "html/api-docs/dotnet/html"]`, converted pages from **1 to 813** (the plan predicted 816), all `.htm`, **0** `class_`-prefixed and **0** `annotated.html`. `bex/1.3.5` **fails, at 0 pages, and the fix is not here**: it has **no output roots at all**, so the guard has nothing to protect, and `_is_docbook_root` rejects `doc/html` one level earlier because it requires `is_docbook_page(page) and _links_stylesheet_within(page, directory)` and **no `bex` guide page links a stylesheet** — 248 pages across four guide directories, zero `<link rel="stylesheet">`; the package's only `.css` is Javadoc's. **Carried forward, not fixed here** (decided 2026-09-15): the conjunct is §5.6.3's duplicate-guide defence, relaxing it changes `find_output_roots` for every DocBook version, and that wants its own corpus measurement rather than a ride on an api-reference phase.
- [x] **`archives/` index** (`design.md` §10.6, `architecture.md` §6.2.3) — `{resources-tree}/{locale}/{slug}/archives/` with `index.md` + `toc.yml` + `metadata.yml`, **no version segment**, built from the **catalog's archived rows, not from the directory**.
  - [x] Each item: `version` (from the catalog — never parsed out of the ZIP filename), `released`, `available`, and `url`.
  - [x] **Decision taken: `release_month()` as-is**, so `Feb 2026`, and the two places a date reaches published output call one function. The day-level precision 85% of rows carry is recorded in `architecture.md` §6.2.3 rather than acted on.
  - [x] **`url` is the catalog's `zip_url` verbatim**, and a local ZIP — if `archive download` ever pulled one — wins over the docsite. The 14 rows with no URL get `available: false`, no `path` key in `toc.yml` at all, and render as `- 7.0.1 (not available)`.
  - [x] **Order by version descending, not by date**, with the non-numeric strings last — `version.yml`'s rule, for `version.yml`'s reason.
  - [x] **A product with no archived rows gets no folder and no index.**
  - [x] **Currency compares the rendered `index.md` as text** — not in the plan, and required: the folder's three filenames never change while nothing is downloaded, so a file-set check would report the history current forever and a version retired since the last sync would never appear.
  - [x] **Retire `ARCHIVE_ALSO_LIVE`** from `reporting/findings.py`. The first code the project removes. `CONTEXT.md` register count 29 → 28, and `test_findings.py` asserts it is gone rather than merely unlisted. **As built the count did not fall**: `PUBLISH_BASE_URL_UNSET` was added in the same phase, so 6d netted 29 → 29 and 6e's `API_LINK_REWRITTEN` takes it to 30.
- [x] **Extend `config/publishing.yaml` with `publish_base_url`** — `ConfigManager.publish_base_url()` reads it, `apirefs.published_url()` composes the path after it from the same template that placed the file, and `test_config.py` pins the default to `""`.
  - [x] **Decision taken: (a)** — the rewrite is skipped, links left relative, and the run reports **`PUBLISH_BASE_URL_UNSET`** once per product. A warning rather than an error because empty is the shipped state; rather than a note because it is a human decision pending, not a property of the corpus.
- [x] **Cross-repo link rewriter** (`architecture.md` §6.4) — **moved to Phase 7 on 2026-09-15, because it cannot be built where it was planned.** The targets are real: **3,183 source links resolve into an API root, in 38 of 49 sampled versions** (`amx-bpm` 4.2.0/4.3.0 at 1,289 each, `ems` 89 per version, `sfire-sfds` 35–36, `rtview` 10, `tps` 8), out of 1,528,192 relative references in non-API pages. **None of them reaches Markdown.** A link into an API root is a topic-looking `.html` that is not in `self.topics`, so `engines/flare.py:link()` fires `dangling_link` and returns `None` — text kept, link gone; a non-topic reference gets `Resolution(AssetOutcome.ESCAPED)` from `AssetCopier.resolve()` with no `url`, and `_asset` returns `.url or None`. `AssetCopier.escaped` holds them in memory with the comment "Stage 7 routes these (§10.7)" but nothing persists them and the anchor position is gone. So "runs after both trees are placed, over the docs tree's Markdown" would scan files with nothing to find and report success — the §5.5.9 failure mode with the sign flipped. Making it possible means **changing what all four engines emit**, which reopens Stage 5's link path and every link test it has. Recorded in `architecture.md` §6.4.2; `DOC_REFERENCE_MISSING` stays the registered `Stage.SYNC` code no shipped path raises, and is the marker for it.
  - [x] **The link targets are the 146 placed roots, matched by resolved path** — still the right rule when the rewriter is built; `apirefs.published_url()` already composes the destination.
  - [x] **The rewrite breaks 6b/6c's currency comparison and has to be sequenced around it** — still true, and still the reason it must happen in the staging directory before the swap.
  - [x] **A link into an api root that was de-duplicated away must follow the survivor.**
- [x] **Validation: deferred to Phase 7**, as recommended. `validate` is still a `_pending` stub owned by §7.3/§7.4, and the assertions are about files 6b and 6c write.
- [x] **Docs in the same commit** — `architecture.md` §6.2.3 rewritten (the archived-date shapes, the absolute `zip_url`, the dead cross-link) with new §6.3.2 (naming), §6.3.3 (output root beats api marker) and §6.4.1/§6.4.2 (the unset host, and why the rewriter moved); `design.md` §10.6 to **Built**, §10.7 marked reassigned, four §12 index rows; `user-guide.md` §4 gaining the `-resources` tree, the real placement shape and the two link bullets; a `CONTEXT.md` ledger row and the register count change.

#### Phase 6e — The cross-boundary link rewrite, moved to conversion time

**6d placed the API references and could not link to them.** The trees are in `-resources` and `apirefs.published_url()` knows their address, but the help topics that point at them lost their links during conversion — so the phase closed with §10.7 handed to Phase 7 and `DOC_REFERENCE_MISSING` left outstanding. 6e is that work, and it is a separate phase rather than a 6d amendment because **it is not Stage 7 work at all**: the rewrite has to happen while the engine is emitting Markdown, which is a Stage 5 change wearing a Stage 6 phase's clothes.

**Two corrections to what 6d recorded, both mine and both in the direction of "smaller than I said" (2026-09-15):**

- **It is not an engine rewrite.** 6d's ledger says building this "means changing what four engines emit", which overstates it. The engines keep emitting exactly what they emit now; **one branch that currently returns `None` returns a URL instead**, in four places that are the same four lines.
- **Nothing needs inventing for the URL.** `ConversionContext` already carries `api_roots` (`engines/base.py:190`), `slug` and `version`; the driver already holds the `ConfigManager` that knows `resources_tree_name()` and `publish_base_url()`; and `sync/apirefs.py:published_url()`, written and tested in 6d, already composes the address. What is missing is only that the two halves have never been introduced.

**And one thing that got *easier* by moving.** The old plan's sub-bullet — "the rewrite breaks 6b/6c's currency comparison and has to be sequenced around it", rewrite in the staging directory, compare currency against the rewritten copy rather than against `output/` — **disappears entirely**. When conversion writes the URL, the converted tree on disk already contains it, so `sync` copies a finished file and its size-and-mtime comparison is untouched. The complexity the rewrite was going to add to Stage 7 was an artifact of doing it in the wrong stage.

##### Measured 2026-09-15, through the shipped classifiers

`links.classify`, `links.is_topic`, `links.escapes`, `roots.owning_root` and `apiref.find_api_roots` with 6d's output-root guard, over the 13 in-scope products (`C:\tmp\probe_6e_branches.py`). **This supersedes the 3,183-in-38-versions figure in 6d's ledger**, which was an ad-hoc pass that resolved paths differently; the numbers below come from the code that will do the work.

- **3,194 relative references resolve into an API root, in 41 of 49 in-scope versions.**
- **All 3,194 take one branch, and it is not the one I named in 6d.** Every single reference is a *topic-suffixed* target that resolves **inside the engine's own output root** and is dropped because it is not a converted topic. **`links.escapes()` fires 0 times. `AssetCopier` sees 0 of them.** This is 6d's "133 of 165 API roots sit inside an engine output root" showing up on the link side: `amx-bpm`'s roots are `bpmhelp/{jsdoc,javadoc,web_client_javadoc}` inside the DITA root `bpmhelp/`, and `ftl`'s are `html/api-docs/…` inside the Flare root `html/`. One shape, not two.
- **So touchpoint B is not built.** The plan for this phase previously carried a second change in `AssetCopier.resolve()`'s escape branch for non-topic references — PDFs and diagrams inside a Javadoc tree. There are none. Building for 0 measured traffic is what the marker-set widening was rejected for in 6d (165 → 165) and what `ARCHIVE_ALSO_LIVE` was deleted for; the same rule applies to me. `AssetCopier.escaped`'s "Stage 7 routes these (§10.7)" comment stays, because class 2 still needs it.
- **All four convertible engines carry traffic, and the distribution is nothing like the version counts:**

  | Engine | Links | Versions | Heaviest |
  | :--- | ---: | ---: | :--- |
  | SDL DITA | 2,581 | 3 | `amx-bpm` 4.2.0 / 4.3.0, 1,290 each |
  | Flare | 456 | 30 | `ems` ×4 at 89; `tps`, `eftl`, `ftl`, `msg-akd-repo`, `bcedi` |
  | DocBook | 142 | 4 | `sfire-sfds` 10.6.5 / 10.6.6 at 36 |
  | WebWorks | **1** | 1 | `bcedi/6.10.0` |

  **DITA is 81% of the traffic in 7% of the versions, and WebWorks is one link.** Both facts are worth stating rather than averaging away: the phase is justified by `amx-bpm` alone, and the WebWorks change earns its place only because the predicate is shared and the edit is one line — if it needed its own logic it would not be worth making.
- **A further 14 links, in 3 `rtview` versions, are unreachable and are not counted above as work.** `rtview` detects as **FrontPage**, which is not in `CONVERTIBLE_ENGINES`, so those topics never become Markdown and have no link to rewrite. **This invalidates one acceptance test I had drafted** — `rtview/5.9.1-august-2011` was going to prove that a link into a de-duplicated root follows the survivor, and it cannot, because it never converts. That case moves to a unit test.
- **Backslashes are already handled.** `amx-bpm` ships `…/calendar\SaveCalendar.html` in real hrefs, and `links.classify` normalizes `\` and `%5C` to `/` at line 87. No work — recorded because the raw sample looks like it needs some.

##### The design

- [x] **The driver injects a resolved map; the engines never compose a URL.** `ConversionContext` gains the version's API roots paired with the published URL prefix each one got, and one accessor — `api_url(absolute, fragment) -> str | None`. **This is what keeps §10.7's stated rationale true.** The rewrite was assigned to Stage 7 because "conversion does not know the publishing layout", and it still does not: it is *told* the answer, exactly as it is already told `api_roots` rather than walking for them.
  - [x] **The map is built by calling `apirefs.select()`** — the same function `sync_api_references` calls — so the folder Stage 7 writes and the URL Stage 5 emits come from one de-duplication, one naming rule and one collision fallback. Anything less and `tps/6.0.0`, whose whole version demotes to dashed paths, gets links to folders that were never created.
  - [x] **Every root is a key, including the 19 de-duplicated away**, each mapping to its *survivor's* URL. Proven by unit test rather than by corpus run, because the corpus's self-nesting case is `rtview` and `rtview` does not convert.
- [x] **One touchpoint: the four engine `link()` methods**, one line before the existing `dangling_link` call — `flare.py:297`, `dita.py:247`, `docbook.py:245`, `webworks.py:340`. The check goes **before the whole `if`**, not inside either arm: `escapes()` fires 0 times today, but a rewrite that only handles the arm the corpus currently uses is one repackaging away from silently dropping links again.
- [x] **A fragment survives the rewrite.** Javadoc links are `#method-summary`-heavy and a class page without its anchor is the wrong answer to the question the topic asked. `links.emit(url, fragment)` already does this for every other link kind.
- [x] **A target that is not on disk stays dangling.** The test is "resolves inside an API root **and** exists", not "the path looks like one" — `apiref.py`'s rule that a marker decides and a name never does, applied to the link side. Emitting a URL for a page the copy will not contain trades a reported failure for a silent 404.
- [x] **An unset `publish_base_url` emits the tree-rooted path with no scheme or host** — `en-us-tib-messaging-userdocs-resources/en-us/ems/api-references/10-4-0/java/index.html` — and the prefix goes on when the host is known. **Decision taken 2026-09-15**, over two alternatives: dropping the link until a host exists delivers nothing and loses the same data as today, and a server-absolute `/en-us-…` would be clickable immediately **only if** AEM serves both repos from one host at content paths matching the repo names, which nobody has confirmed — that is this option plus an assumption about someone else's infrastructure, and it fails silently if the assumption is wrong. The path is the part that is actually derivable; a missing prefix is a search-and-replace, a dropped link is not recoverable at all.
- [x] **The convert-currency key must include the URL prefix, or setting the host later changes nothing.** `driver.py:183` keys currency on the *package's* checksum, which is right for its stated reason and wrong for this one: the package does not change when `publishing.yaml` does, so filling in `publish_base_url` would leave every converted tree reporting `CURRENT` with host-less links baked in, and the run would say so cheerfully. **Record the prefix beside `convert_source_checksum` in `version_metadata` and compare both.** This is the one bullet in the phase that is a trap rather than a feature, and it is exactly the silent-partial-success shape §7.5 exists to catch.
- [x] **One new finding code, a note with a count: `API_LINK_REWRITTEN`.** Notes aggregate into a single row with a `count` (§7.1), which is the right shape — nobody acts on one rewritten link, everybody wants the magnitude. It matters because the failure here is silent: a version with an API tree and **zero** rewritten links is either a product whose help genuinely never references its API (8 of the 49 in-scope versions) or a predicate that stopped matching, and without the count those are indistinguishable. Register 29 → 30.
- [x] **What stays out, named rather than omitted.** §10.7's **class 2** — the 279 Flare references that escape into `doc/`, `pdf/` and the version root, bound for the document doc-classes — is *not* in 6e. Its destination is a relative path across doc-classes inside the same repository, which needs §10.4's router, and the router's answer is Stage 7 knowledge that conversion does not have and cannot be handed cheaply. `DOC_REFERENCE_MISSING` stays outstanding for it. Class 3 shipped in 6d.

##### Acceptance

- [x] **Measured through the shipped converter, not asserted.** Convert the 38 reachable versions and count links in the **output Markdown** pointing at the resources tree: expect **3,180** less those whose target is absent from disk, against a before figure of **0**. And **0** remaining `dangling_link` findings whose resolved path lands inside an API root.
- [x] **One version per engine must pass, because the edit is in four files:** `amx-bpm/4.2.0` (DITA, 1,290), `ems/10.4.0` (Flare, 89), `sfire-sfds/10.6.5` (DocBook, 36) and `bcedi/6.10.0` (WebWorks, **1**). The WebWorks case is a single link and is the one most likely to be quietly skipped.
- [x] **A link into a de-duplicated root follows the survivor** — unit test, since `rtview` is FrontPage and never converts.
- [x] **The other in-scope versions and the whole non-API corpus produce byte-identical output to today.** This touches a branch every link in the corpus passes through, so "changed nothing else" is the assertion that matters most, and it is the reason the phase is not simply a patch.
- [x] **Docs in the same commit** — `architecture.md` §6.4.2 rewritten from "why this cannot be built" into how it is, with the cost correction stated plainly; `design.md` §10.7 to **Built** for classes 1 and 3 with class 2 still Phase 7, plus its §12 row; `user-guide.md` §4's two link bullets replaced; a `CONTEXT.md` ledger row and the register count 29 → 30.

**Result, 2026-09-15: 2,854 of 3,180 rewritten in 38 versions, and the remainder reconciles exactly.** Every convertible in-scope version with an API tree was converted twice, with the map and with an empty one. `TOPIC_LINK_DANGLING` falls by **exactly 2,854**, which is the check the first bullet was really asking for — the counted-links figure it named undercounts, because 6 of `sfire-sfds`'s land inside a table the walk keeps as raw HTML, where the URL is in an `href` rather than after a `](`. Per engine: DITA `amx-bpm/4.2.0` **1,289 of 1,290**, DocBook `sfire-sfds/10.6.5` **36 of 36**, WebWorks `bcedi/6.10.0` **1 of 1**, Flare `ems/10.4.0` **8 of 89**.

**Two things the acceptance found that the plan had not predicted, one trivial and one worth its own change.** **2 of the 3,180** point at a file the package does not ship and stay dangling, which is the designed behaviour and is the whole of the "less those whose target is absent from disk" allowance. And **324 never reach `link()` at all**: `transforms/markdown.py` renders `code`/`tt`/`kbd`/`samp` from their *text*, so `<code><a href="../api/javadoc/…">MessageListener</a></code>` is flattened to a bare code span before any engine sees the anchor. All 324 are in `ems`, whose developer guide writes every API cross-reference that way, and **320 of the 324** are the anchor alone inside the span — the case GFM expresses by inverting the nesting. It is **not** 6e's code and not in 6e: the walk it lives in is shared by all four engines and by every link in the corpus, so recovering those links is a change with a much wider blast radius than the API-link path, and it is recorded here and in `architecture.md` §6.4.2 rather than folded in quietly.

### Phase 7: CLI, Reporting & Verification Dashboard

**Design settled 2026-09-10.** The reframe that drives everything below: **this phase is not a dashboard, it is where a dozen earlier decisions come due.** At least fifteen rules across Stages 1–6 end in "…is a report line", "counted and named", or "reported rather than dropped" — and since `csh.yml` lost its `unresolved` key (Phase 6 contract), the report is now the *only* surviving record that a Help identifier resolved to nothing. Built as a summary screen, every one of those obligations quietly becomes nothing, and `design.md` invariant 10 ("absence is reported, never faked") becomes untrue in a way no test would catch.

**Split into three sub-phases, 2026-09-16**, on the same rule Phases 5 and 6 were split by — what can be *accepted* on its own, not what is the same size. **7a is the read layer and the writers it reveals are missing**: `report`, `status`, and a `FindingsRun` in the three stage commands that record nothing today. **7b is `validate`** — §7.4's link, asset and AEM-artifact integrity, the first command that reads the published tree rather than the database. **7c is the `csh` group and §7.6's cross-version regression.** The order is not arbitrary: 7b and 7c both *write* findings and neither has a reader, so building either first means accepting it by inspecting a SQLite file. 7a also ends with the §7.5 register at three outstanding rows instead of nine, which is what makes "is this code reachable yet" a question the later two sub-phases can answer with a number.

#### 7.1 The findings table

Findings persist in `state.db`, written by the stage that discovers them and queried by `report`. Not in-memory: a record that dies with the terminal buffer cannot be the only copy of a broken Help button.

```sql
runs(run_id, command, batch, started_at, finished_at, exit_code)
findings(id, run_id, stage, severity, code, slug, version, path, message, count)
```

- [ ] **`code` is the contract; `message` is prose.** Tests assert on codes, so a message can be reworded without breaking anything, and an obligation that exists only as an English sentence becomes an enumerable thing. This is the single design decision that makes §7.5 auditable.
- [ ] **Severity is a property of the code, fixed in one registry — never chosen at the call site.** Two call sites reporting the same condition at different severities makes the exit code a matter of which one fired.
- [ ] **Errors and warnings get one row each; notes are aggregated into a single row with a `count`.** You act on an error individually and only need the magnitude of a note — and a per-file note would write hundreds of thousands of rows for the orphan-image case alone. The list behind a note is regenerable by re-running the stage.
- [ ] **Findings are written inside the stage's existing transaction** (`state.py:transaction`, §3.5). A failed stage leaves none, which is what keeps invariant 11 true — a failed run must not write partial measurements.
- [ ] Retained across runs, so §7.6 is a query rather than a re-parse. `report --prune --keep N` for the day that matters.

#### 7.2 Severity, and what gates

| Severity | Meaning | Exit effect |
| :--- | :--- | :--- |
| `error` | The output is wrong or unpublishable | `validate` exits **1** |
| `warning` | The run succeeded; a human decision is pending | Printed and counted; exit 0 |
| `note` | Normal for this corpus, recorded so a change in magnitude is visible | Counted only; exit 0 |

- [ ] **Only `validate` gates.** A `convert` that finishes 99 of 100 versions and reports one error has done its job; failing it would make partial progress impossible and tempt everyone to pass a skip flag. **But invariant 10 still binds**: a stage command that did nothing at all exits non-zero, which is a different condition from having found problems.
- [ ] **`note` exists so that `warning` stays worth reading.** 54.6% of Flare's images are orphans by the authoring tool's design; filed as warnings, they would bury the six that matter.

#### 7.3 Command surface

Three commands, split by the question each answers — the current `status`/`report` pair has no stated boundary and would otherwise converge.

- [ ] **`docushift status` — *where is everything now?*** A standing snapshot over the catalog, needing no run: counts per stage (discovered → in scope → eligible → downloaded → extracted → converted → synced), family workspaces, locale, batch tags. Extends what `status` already prints.
- [ ] **`docushift report` — *what happened?*** Findings from a run. `--run last|<id>`, `--stage`, `--severity`, `--code`, `--slug`, `--explain <CODE>`, `--export <file.md>`.
- [x] **`docushift validate` — *is the output correct?*** Runs §7.4 against `--target-dir`, writes findings, gates on errors. **Built, Phase 7b.**
- [x] `docushift csh {list,report,validate}` — per-version identifier listing, coverage, integrity checking. `csh report --since <version>` is §7.6. **Built, Phase 7c**, with one deliberate override: **coverage is across the published tree, not across a batch.** A batch is a `versions.csv` column, and `docushift report --run last --code CSH_UNRESOLVED` already answers the batch question from the run's own findings; the shelf had no reader at all. So the group takes `--target-dir` like `validate` and opens the catalog nowhere (`architecture.md` §7.6).
- [ ] **Markdown export only** (decided 2026-09-10 — no JSON, no HTML). One file: run header, then errors, warnings and notes grouped by stage then code. **Consequence: tests assert against the `findings` table, never by parsing the Markdown.** With no JSON there is no machine format to assert on, and a test that greps report prose pins the wording of every message in the tool.

#### 7.4 Link, asset and AEM-artifact integrity

- [x] Broken link and missing asset linter, including the CSH checks in `architecture.md` §5.4.6.
  - [x] **Classify before checking**: relative links resolve on the filesystem and a miss is an error; absolute URLs are external — which after Stage 7 means every API-reference link — and are skipped by default, HTTP-checked only under `validate --check-external`.
  - [x] **Percent-decode before resolving**, so the linter compares what a renderer would.
  - [x] **An unreferenced asset is not an error.** Orphans are a Phase 5 report line, not a lint failure — 54.6% of Flare's images are unreferenced by the authoring tool's design (`architecture.md` §5.5.7).
  - [x] A broken asset link here is a **regression against `design.md` invariant 13**, not a discovery: Phase 5 resolves the copy and the link together, so the count should be zero and the test exists to prove it stays zero.
- [x] **The AEM artifacts get field-level checks**, replacing `design.md` §8.4's "existence and well-formedness only" rule, which was justified by their shapes being guesses (both grounds gone — Phase 6 contract): `metadata.yml` carries its required `csg-*` key, non-empty; every `version.yml` `path` resolves to a sibling directory and every version directory has exactly one entry, ordered numeric-descending; every `csh.yml` value's file part exists and its anchor is present in that file.

#### 7.5 The obligation register

The concrete deliverable of §7.1: every deferred "report line" in the three documents, given a code. **A test asserts that every code emitted is registered and every registered code is reachable** — which is how a promise made in prose three phases earlier stops being able to quietly evaporate.

**Eight rows were added by Phase 5b** (marked ⁵ᵇ). They are the report lines `architecture.md` §5.1 asked for in prose and this table had not yet given a code; the reachability half of that test is what forced the last of them — `ALERT_LABEL_UNMAPPED` was unreachable against a closed callout vocabulary, and rather than delete the code the detection was widened to the open `div.note<Kind>` convention it was written for.

**Stage 6 netted two** (⁶ᶜ, ⁶ᵈ, ⁶ᵉ) — three added and `ARCHIVE_ALSO_LIVE` removed as unreachable once `sync/archives.py` was built and the condition turned out not to arise. **Phase 7b added seven** (⁷ᵇ), which is the largest single jump and not the register growing loosely: `validate` is the first command whose entire job is to raise findings, so its §7.4 and `design.md` §9.6 obligations had no codes for the plain reason that nothing had ever been written to emit them. **Phase 7c added none** (⁷ᶜ marks the row it *reached*, not a row it created) and took `NOT_YET_EMITTED` from two to **one**: `CSH_IDENTIFIER_DROPPED` fires, and only `DOC_REFERENCE_MISSING` is left, waiting on §10.7's class 2. A phase that closes a debt without opening one is the register working the way it was meant to. Four more followed one at a time — `CODE_LINK_FLATTENED` (⁸), `INDEX_UNLINKED` (¹⁰ᵇ), `WHATS_NEW_PLACEHOLDER` (¹¹ᵃ) and `OUTPUT_COUNT_MISMATCH` (¹³) — and **the table is now 43 rows**. The forty-second is `ZIP_URL_UNRESOLVED` (¹⁴ᵃ) — the register's **first `download` row**, in the phase that discovered the stage had never successfully run — and the forty-third `PUBLISHED_PATH_TOO_LONG` (¹⁵ᵈ), `sync`'s **first error**, added one phase later and deliberately at the opposite severity: the download code names a condition a user can fix with `--from-file`, and this one names a path nothing downstream can open. Three of those four were added to the code and not to this table, and the drift stood until Phase 13 came looking: `test_the_register_carries_every_row_of_7_5` pins the register's size against itself, which cannot see a missing row here. `test_the_published_table_carries_every_registered_code` now reads this file and asserts every registered code appears in it, so the next omission fails a test rather than waiting to be noticed.

| Code | Sev | Stage | Obligation | Specified in |
| :--- | :--- | :--- | :--- | :--- |
| `SCOPE_RULE_UNMATCHED` | warn | catalog | A `scope.yaml` rule matching no product | `design.md` §8.2.5 |
| `EOS_ALIAS_STALE` | warn | catalog | An alias naming a product the active report lacks | `design.md` §8.2 |
| `EOS_PRODUCT_EMPTIED` | warn | catalog | Retirement left a product with nothing to convert (11 products) | Phase 3.7 |
| `BATCH_NOT_ELIGIBLE` | warn | catalog | Tagged into a batch but not eligible | `design.md` §8.2.2 |
| `ZIP_URL_UNRESOLVED`¹⁴ᵃ | warn | download | No ZIP endpoint could be derived for an active version (7 of 35 sampled products); supply it with `--from-file` | Phase 14a |
| `PUBLISHED_PATH_TOO_LONG`¹⁵ᵈ | error | sync | A file's published path would exceed 260 characters; the tree is skipped rather than half-copied | Phase 15d |
| `CSH_SOURCE_EMPTY` | note | extract | CSH source present but empty — no `csh.yml` written | `architecture.md` §5.4.2 |
| `CSH_SOURCE_UNPARSED` | warn | extract | Source located but failed to parse; `_has_csh` still set | `design.md` §6.2 |
| `ENGINE_UNKNOWN` | warn | convert | `auto`, or a named engine with no handler — skipped, not guessed | invariant 7 |
| `DOCSET_SKIPPED` | warn | convert | A file-named doc-set reaching the engine guard | `architecture.md` §5.2 |
| `NAV_NODE_DROPPED` | note | convert | A node with no page and no children — DITA's `lof`/`lot`/`ix` (first top-level node in 246 books), Flare's 7 childless headless nodes and 30 same-page children | Phase 5 |
| `OUTPUT_ROOT_MISSING`⁵ᵇ | warn | convert | Engine detected, no unit of work found — the 5 partial Flare outputs | `architecture.md` §5.1.1 |
| `CONTENT_MISSING`⁵ᵇ | warn | convert | A topic with no content container — reported, never guessed at | `architecture.md` §5.1.6 |
| `TOC_ORPHAN`⁵ᵇ | note | convert | Converted topics in no TOC entry, filed under Unfiled — 14.1% for Flare | `architecture.md` §5.1.4 |
| `TOPIC_LINK_DANGLING`⁵ᵇ | note | convert | A cross-reference to a topic this run did not produce; text kept, link dropped | `architecture.md` §5.1.3 |
| `ALERT_LABEL_UNMAPPED`⁵ᵇ | warn | convert | An admonition label outside the five GitHub renders; rendered as NOTE | `transforms/callouts.py` |
| `ANCHOR_DROPPED`¹⁹ | warn | convert | A referenced anchor the engine kept and then did not emit; its links now dangle | `planning.md` Phase 19 |
| `LANDING_PAGE_EMPTY`⁵ᵇ | note | convert | A landing page with nothing past its hero — a stub was generated (4.5% measured) | `architecture.md` §5.1.5 |
| `TAIL_PAGE_MISSING`⁵ᵇ | warn | convert | No support or no legal page in the TOC — nothing is synthesized | `architecture.md` §5.1.5 |
| `LOCALIZED_TREE_SKIPPED`⁵ᵇ | note | convert | A localized subtree inside an English unit, not converted | `architecture.md` §5.1.9 |
| `ASSET_ORPHANED` | note | convert | Unreferenced asset — 54.6% is normal for Flare | `architecture.md` §5.5.7 |
| `REFERENCE_UNRESOLVED` | **error** | convert | A reference producing neither link nor copy | invariant 13 |
| `CSH_UNRESOLVED` | warn | convert | Identifier matched no produced topic | Phase 6 contract |
| `CSH_AMBIGUOUS` | note | convert | Identifier claimed by 2+ doc-sets; first ordered doc-set wins | Phase 6 contract |
| `DOC_REFERENCE_MISSING` | warn | sync | Flare escape pointing at a document the ZIP never shipped (152) | `architecture.md` §5.5.8 |
| `VERSION_NOT_NUMERIC` | warn | sync | Non-numeric version string sorted last in `version.yml` (20 rows) | Phase 6 contract |
| `VERSION_UNDATED` | note | sync | Active version with no `release_date`; title loses its bracket (13) | Phase 6 contract |
| `METADATA_MISMATCH` | warn | convert | SuiteHelp `release-version` / `release-date` disagreeing with the catalog | Phase 6 contract |
| `DOCUMENT_UNREADABLE`⁶ᶜ | note | sync | PDF whose Info dictionary would not parse; titled from its filename | `design.md` §10.5 |
| `PUBLISH_BASE_URL_UNSET`⁶ᵈ | warn | sync | `api-references` placed with no `publish_base_url`; cross-tree links have no host | `architecture.md` §6.4 |
| `API_LINK_REWRITTEN`⁶ᵉ | note | convert | Link into an api-reference tree pointed at its published `-resources` URL | `design.md` §10.7 |
| `LINK_BROKEN` | **error** | validate | Relative link resolving to nothing | `design.md` §8.4 |
| `ANCHOR_MISSING`⁷ᵇ | warn | validate | A `#fragment` naming no heading and no `id=` in the file it resolves to | §7.4 |
| `LINK_EXTERNAL_DEAD`⁷ᵇ | warn | validate | An absolute URL that did not respond, under `--check-external` | §7.4 |
| `CSH_FRONTMATTER_MISMATCH`⁷ᵇ | warn | validate | `csh.yml` and a topic's frontmatter disagree about an identifier | `design.md` §9.6 |
| `METADATA_INVALID`⁷ᵇ | **error** | validate | `metadata.yml` missing, unshaped, or with an empty `csg-product`/`csg-version` | `architecture.md` §6.2 |
| `DROPDOWN_INCONSISTENT`⁷ᵇ | warn | validate | `version.yml` disagrees with the version folders beside it | `architecture.md` §6.6 |
| `ARTIFACT_UNPARSED`⁷ᵇ | **error** | validate | An AEM YAML artifact that would not parse; its field checks were skipped | §7.4 |
| `SYNC_RESIDUE`⁷ᵇ | note | validate | A `.part` staging folder left by a sync that did not finish | §7.4 |
| `CSH_IDENTIFIER_DROPPED`⁷ᶜ | warn | validate | Present in the prior version, absent here (§7.6). One row per version; `count` is how many | this phase |
| `CODE_LINK_FLATTENED`⁸ | note | convert | Link inside a code block kept its words and lost its target; a GFM fence cannot hold one | Phase 8 |
| `INDEX_UNLINKED`¹⁰ᵇ | note | sync | A published document no `index.md` links to — the reverse of `LINK_BROKEN` | Phase 10b |
| `WHATS_NEW_PLACEHOLDER`¹¹ᵃ | note | convert | What's New shipped as the unfilled MadCap template (167 of 648 roots); not published | Phase 11a |
| `OUTPUT_COUNT_MISMATCH`¹³ | warn | convert | Fewer Markdown files on disk than documents converted; two writes landed on one path | Phase 13 |
| `REFRAME_TOC_SCHEMA_UNKNOWN`²⁰ᵃ | error | reframe | No TOC adapter matches this version's `toc.yml`; refusing to merge a partly-understood tree | `REFRAME-INTEGRATION-PLAN.md` §4 Phase 0 |
| `REFRAME_LAYOUT_UNPINNED`²⁰ᵃ | warn | reframe | More than one eligible version of this doc set and no pinned layout; versions may not correspond | `REFRAME-REQUIREMENTS.md` R1.4 |
| `REFRAME_SELF_CHECK_FAILED`²⁰ᵇ | error | reframe | A §6 acceptance check failed; the merged tree was discarded rather than swapped in | `REFRAME-REQUIREMENTS.md` §6 |
| `REFRAME_LINK_UNRESOLVED`²⁰ᵇ | warn | reframe | Relative references pointing outside the converted tree, left as written; present before the merge | `REFRAME-REQUIREMENTS.md` R4, §8 |
| `REFRAME_TOPIC_UNTOCKED`²⁰ᵇ | warn | reframe | Topics absent from `toc.yml`, carried through unmerged and unreachable from navigation | `REFRAME-REQUIREMENTS.md` R3 |
| `REFRAME_REVIEW_QUEUED`²⁰ᶜ | note | reframe | Merged pages needing an editorial decision, listed in `review-queue.csv` | `REFRAME-REQUIREMENTS.md` R6 |
| `SYNC_MERGE_UNAVAILABLE`²⁰ᵈ | warn | sync | A product set to publish merged has no current reframed tree; it publishes nothing rather than falling back | §20d |
| `REDIRECT_SHADOWED`²⁰ᵈ | warn | validate | A redirect whose source path still exists in the published tree; a 301 loop where the two differ only in case | `REFRAME-REQUIREMENTS.md` R5 |
| `REFRAME_KEEP_SEPARATE_UNMATCHED`²⁰ᵉ | warn | reframe | A `keep_separate` path matches no topic in this version; the merge a writer meant to undo still happened | §20e |
| `ORIGIN_TEMPLATE_UNDECLARED`²² | warn | reframe | No verified docsite URL template for this product, so no `301.yml` was written; a guessed origin URL redirects to a page that never existed | Phase 22 |

#### 7.6 Cross-version CSH regression

A dropped identifier is a Help button that breaks on upgrade, and it is invisible from inside a single version.

- [x] **The comparison target is the next-lower *converted* version of the same product**, by `natural_version_key` (§1.3, already built) — not "the previous run", which is a scheduling accident and would compare 10.4.0 against whatever happened to be converted last Tuesday. **Built, Phase 7c**, with the rule tightened by measurement: the predecessor is the immediate next-lower folder *in the same doc-class*, and if that folder has no map there is no finding. Skipping back to the last version that had one turns a vanished map into a row in every version after it.
- [x] **Read the prior version's `csh.yml` from the output tree**, not the findings table. That file is what actually shipped; the database records what the tool meant to ship, and the difference between those two is exactly the class of defect this check exists to find. **Built** — and the tree is the *published* one rather than the converter's output, for §7.3's reason above.
- [x] ~~A missing prior tree is a `note`, not a failure~~ **— refused on a number, Phase 7c.** The intent was *do not fail on a first conversion*, which writing no row honours. Writing one would add **150 rows** over the cache to a check that produces 51 real ones. The absence is a property of every product's oldest version, and it shows in `csh report`'s coverage table, which is a column rather than a finding.

#### 7.7 Sequencing: the findings module cannot wait for Phase 7

- [x] ~~**`reporting/findings.py` and the code registry land at the start of Phase 4**~~ **— slipped, and landed in Phase 5a instead** (2026-09-11), even though every command that reads them lands here. Phase 4 is the first stage that produces findings, and Phases 4–6 each carry several rows of the §7.5 register. If the module arrives last, those five phases each invent their own logging and Phase 7 becomes a rewrite of working code rather than a read layer over it. The table, the registry and a `record()` call are perhaps 80 lines; the commands are the phase.

  **What the slip cost, recorded rather than tidied away.** Phases 4a, 4b-1 and 4b-2 shipped without it, so Stage 4's two register rows (`CSH_SOURCE_EMPTY`, `CSH_SOURCE_UNPARSED`) exist today only as terminal output from `docushift extract` — the exact failure mode this section was written to prevent, arriving in the section that predicted it. It was caught while planning Phase 5, which carries **9 of the 20 rows**, and moved into 5a rather than deferred a second time. **Still owed after 5a**: both codes are *registered* and neither is *emitted* — `docushift extract` still prints its unreadable-source lines and writes no rows. That is the register working as designed (the reachability test names them, so the gap is visible rather than assumed closed), and it stays a small follow-on rather than a rewrite, because the report blocks already compute the counts.

- [ ] End-to-end integration test suite.
- [ ] **Docs in the same commit** — `design.md` gains §8.5 (findings and severity), §8.6 (the obligation register), §8.7 (cross-version CSH), with §8.4 rewritten for the AEM artifacts and §12 index rows for each; `architecture.md` §7 for the command surface; `user-guide.md` the `report` / `validate` / `csh` surfaces and the severity table; `CONTEXT.md` a ledger row. *(Split across the three sub-phases: §8.5 and §8.6 and `architecture.md` §7 land with 7a, §8.4's rewrite with 7b, §8.7 with 7c.)*

#### Phase 7a — The read layer, and the three stages that write no findings — **Complete (2026-09-16)**

**The phase this splits off is the one that makes the other two acceptable.** `report` is not the payoff of the register — it is the instrument every later sub-phase is measured with, and it is also where the register's own debt becomes visible as a number rather than as a paragraph in §7.7.

##### Measured 2026-09-16, against the shipped code and the real catalog

- **Nine of the thirty registered codes appear nowhere in `src/`** — a literal scan of every module except `findings.py` itself. By stage: **catalog** `SCOPE_RULE_UNMATCHED`, `EOS_ALIAS_STALE`, `EOS_PRODUCT_EMPTIED`, `BATCH_NOT_ELIGIBLE`; **extract** `CSH_SOURCE_EMPTY`, `CSH_SOURCE_UNPARSED`; **sync** `DOC_REFERENCE_MISSING`; **validate** `LINK_BROKEN`, `CSH_IDENTIFIER_DROPPED`. **An earlier count of twenty was wrong and the correction is the interesting part**: it came from grepping for `record("CODE"`, which misses every call whose code arrives on a continuation line or through a variable. That grep is also the obvious way to write a static reachability test, so the false positives it produces are recorded here rather than discovered by a test that fails on working code.
- **Two of the seven stage commands open a `FindingsRun` at all** — `convert` (`cli.py:1116`) and `sync` (`cli.py:1296`). `catalog`, `download` and `extract` write no rows, so a `report` built today could only ever show two stages of a seven-stage pipeline, and §7.7's "still owed" is wider than the two CSH codes it names.
- **The catalog already computes every figure its four codes need, and prints them.** `unmatched_scope_rules()` → **1** (`tibco-spotfire-for-apple-ipad`, the rename detector that has been firing since the first full crawl), `unmatched_eos_aliases()` → **0**, `triage_summary()` → **128 versions retired across 11 fully-retired products**, which is §3.11's published figure recomputed from the catalog rather than remembered from the run that wrote it. What is missing is not a measurement. It is a row.
- **`BATCH_NOT_ELIGIBLE` has no corpus traffic**: **0 of 4,462** version rows carry a `convert_batch`. It is reachable and it is a unit test, and recording the zero now is what stops a later reader diagnosing it as a defect.
- **CSH emptiness is the majority case, so its code has to aggregate**: 476 of 863 Flare alias files, 492 of 647 WebWorks `topics.js`, 38 of 418 DITA `head.js` (§5.4.1). One row per source would file roughly a thousand rows of *normal*. `CSH_SOURCE_EMPTY` is a note, notes fold on `(code, slug, version)` (§7.1), so it is one row per version carrying a count — the same shape `ASSET_ORPHANED` was given for the same reason.
- **The reader side of `state.db` is two methods** — `get_findings(run_id)` and `last_run(command)`. No run list, no filtered query, no delete. The write side has been complete since 5a: `runs`, `findings`, the `findings_by_run` index, `start_run` / `finish_run` / `record_findings`.
- **Findings volume is wildly skewed, which is what the filters and `--prune` are for.** Measured by converting 51 in-scope versions and counting what they recorded (48 minutes): **1,712 rows carrying 8,304 occurrences**, of which Flare contributes 1,690. The median version writes **2** rows and the 90th percentile writes **4** — but `tps/6.0.0` alone writes **1,005**, 59% of the sample, and the next three are all `ftl` at ~200. So a report is either two lines or a thousand, with almost nothing in between: `--code` and `--slug` are not conveniences, and a corpus-wide convert is the run that makes retention a question. The longest message recorded is 197 characters, so the export's table cells are not the constraint.
- **`runs.exit_code` is `0` on every row ever written**, because both callers call `finish()` with its default. And a stage command whose selection matches nothing prints a yellow line and returns **0** — so the "Exit-code Discipline" criterion (§2) is specified, twice, and implemented nowhere.

##### The design

- [x] **`docushift report` — what happened.** `--run last|<id>`, filters `--stage` / `--severity` / `--code` / `--slug`, plus `--explain <CODE>`, `--export <file.md>` and `--prune --keep N`. The stub's `--format terminal|markdown|html` **goes**: §7.3 settled Markdown export only on 2026-09-10, and a `--format` flag whose non-default values do not exist is the same lie as a `convert` that exits 0 having converted nothing.
  - [x] **`--engines` moves from `report` to `status`.** Engine resolution is a standing property of the catalog, not a record of a run, and it is the one flag on the current stub that answers the other command's question. `user-guide.md` §6 is updated with it.
  - [x] **Grouped by stage, then by code; errors, then warnings, then notes**, with a note's `count` beside it. The grouping is the register's own shape, so a reader who has seen §7.5 can find a row without being taught a second layout.
  - [x] **`--explain <CODE>` prints the register row** — severity, stage, obligation, and `specified_in`. That last field has been carried on `Code` since 5a with no reader; this is the reader it was written for, and it is what makes a finding traceable to the sentence that promised it.
  - [x] **`report` never gates.** Whatever it prints, it exits 0; only `validate` does otherwise (§7.2). It exits 1 for a run id that does not exist and for an `--export` path it cannot write — failures of the command, not of the run it is reporting on.
  - [x] **Tests assert against the `findings` table, never by parsing the report** (§7.3), with one stated refinement: an export test may assert that a **code** appears in the file. The code is the contract and the message is prose, so pinning a code pins nothing a reword should be free to change.
- [x] **`docushift status` — where is everything now.** A standing snapshot needing no run: the funnel (catalogued → in scope → not retired → eligible → downloaded → extracted → converted), engine resolution and what is still `auto`, family workspaces, batch tags, locale. `--bu` / `--family` narrow it.
  - [x] **There is no `synced` column unless `--target-dir` is given**, and then it is counted off the disk. 6b decided that sync currency is *compared and never recorded*, because a fingerprint in `state.db` would claim currency for a tree an editor had since changed — so the database cannot answer "is this version published" and a column that guessed would answer it wrongly for exactly the versions somebody had edited. The same direction 6b's drop-down takes: about the target, the disk is the truth.
- [x] **The three stages that write nothing get a `FindingsRun`**, in the shape `convert` and `sync` already use — constructed in `cli.py`, handed to the worker, flushed inside the stage's transaction.
  - [x] **`catalog fetch` and `catalog eos`** record the four catalog codes from the values `warnings()`, `unmatched_scope_rules()`, `unmatched_eos_aliases()` and `triage_summary()` already return. The rule is §7.1's: the stage that *discovers* the condition writes it, and both of these commands recompute it as part of doing their job.
  - [x] **`extract` records the two CSH codes**, and they are recorded by `extractor/inventory.py`, not by the CLI's report block. The walk is what knows a source was empty or would not parse; the CLI only prints what it is handed, and a finding written from the printout would be a second derivation of the same fact.
  - [x] **`download` opens no run, named rather than omitted.** It has no registered code, and a run row that can only ever hold zero findings is worse than no row: `report --run last` would select it, and the last thing a user did before asking what happened is frequently a download.
- [x] **The exit-code discipline is implemented where it was specified.** A stage command whose selection matches nothing exits **1** — `download`, `extract`, `convert`, `sync` — while one that did its work and found errors still exits 0. This is a **behaviour change to four shipped commands** and is called out as one: a `--batch poc-1` that matches no row currently looks exactly like a successful run in a script, which is the shape of failure §7.2 was written against. `--dry-run` is unaffected, because listing what *would* happen is the work.
- [x] **The §7.5 reachability test gains a static half and loses the phase chain.** The eight `REACHABLE_IN_PHASE_*` unions collapse into one `NOT_YET_EMITTED` frozenset, asserted **equal** to the registry's unreached set so that both directions fail — closing a code without updating the set breaks the test, and so does registering one and walking away. The new half is a literal scan of `src/` for each registered code, which catches "registered and never written down" cheaply. **It proves a code is written, not that it fires**, which is exactly why the curated set stays rather than being replaced by the scan.
- [x] **`report --prune --keep N`** deletes the findings of all but the N most recent runs, keeping the `runs` rows — §7.1's retention, and the reason `run_id` is an explicit column rather than a rowid alias. Cheap now, and the alternative is discovering the need for it on the day the database is already too big to query.
- [x] **What stays out, named rather than omitted.** `validate` and §7.4 are **7b**; the `csh` group and §7.6 are **7c**; `DOC_REFERENCE_MISSING` stays unemitted until §10.7's class 2 has §10.4's router answer, and it is the one of the three remaining debts that belongs to no sub-phase yet. `status` does not read the findings table and `report` does not read the catalog — the boundary §7.3 exists to defend is worth more than the one line of convenience that would break it.

##### Acceptance

- [x] **The unemitted set is exactly three, by test**: `LINK_BROKEN`, `CSH_IDENTIFIER_DROPPED` and `DOC_REFERENCE_MISSING`, each named to 7b, 7c and §10.7 class 2 respectively. Nine → three is the phase's headline number and it is asserted, not counted by hand.
- [x] **`catalog eos` against the real catalog writes 12 rows** — 1 `SCOPE_RULE_UNMATCHED` and 11 `EOS_PRODUCT_EMPTIED` — and they are the *same* 11 slugs the command already prints in red. The test that matters is not that rows exist but that the printed figure and the stored figure are one figure.
- [x] **An extract over a sample with known CSH statuses writes one row per version, not one per source**, with the count matching §5.4.1's ratio for the engine in question.
- [x] **`report --run last` over a full in-scope convert prints the same tally the convert run printed** on its own `Findings:` line. The write layer and the read layer agreeing about one run is the whole of what this phase claims.
- [x] **`report --explain` resolves for all 30 codes** — iterated over `REGISTRY`, so a code added later without an obligation line fails here.
- [x] **`--prune --keep 1` leaves one run's findings and no orphan rows**, with the `runs` rows intact.
- [x] **Docs in the same commit** — `architecture.md` gains **§7, the command surface** (the document has no §7 today and stops at §6.7); `design.md` §8.5 is updated to 30 codes and gains the read side, and §8.6 records the register as an auditable list with its §12 row; `user-guide.md` §4's "View Status & Delta Dashboard" is replaced with the real `status` and `report` surfaces and the severity table, and §6's `report --engines` becomes `status --engines`; `CONTEXT.md` a ledger row and the register count.

##### As built, where it differs from the design above

- **Extract's findings are recorded in `extractor/unpacker.py`'s `measure()`, not in `extractor/inventory.py`.** The design named `inventory.py` on the principle that the walk is what knows a source was empty, and the principle holds — but `inventory_tree()` is a pure function over a directory and does not know the slug or the version a finding has to be filed under. `measure()` is its immediate caller, holds both, and already owns the "write what this walk found to `state.db`" step. Putting the finding there keeps the walk free of the run and keeps the derivation single, which is what the bullet was actually protecting.
- **`PackageExtractor` takes an optional `findings=`.** Optional so a unit test and a `--dry-run` construct the extractor exactly as a run does, which is the same reason `FindingsRun` tolerates a `None` store.
- **`status` prints a footnote when `converted` exceeds `extracted`.** Measured against the real catalog on the day it was built: 4 converted, 0 downloaded, 0 extracted — every one of them a `convert --input` run over the `html-to-md` cache. The funnel is right and reads like a bug, so the command says which it is.
- **The `of eligible` share is suppressed on all four gate rows**, not just the first three. Convert-eligible is the denominator, and printing `100%` against it is noise.
- **`report --runs`** was added: the run list the `--run <id>` picker needs, since no other command lists run ids.

##### Verified against the real catalog, 2026-09-16

- **`catalog eos` wrote exactly 12 rows** — 1 `SCOPE_RULE_UNMATCHED` (`tibco-spotfire-for-apple-ipad`) and 11 `EOS_PRODUCT_EMPTIED`, the same 11 slugs the command prints in red, read back with `report --run 8`. The predicted figure and the stored figure are one figure.
- **`status` over the whole catalog**: 4,462 catalogued → 3,617 in scope → 2,294 not retired → 1,389 convert-eligible, with 1,291 versions still `auto`.
- **1,125 tests pass** (+64), lint clean.

#### Phase 7b — `validate` — **Complete (2026-09-16)**

§7.4 in full: the link, asset and AEM-artifact linter over `--target-dir`, `LINK_BROKEN`, and the one command in the tool that gates on what it finds. It is second because it is the first command that reads the *published* tree rather than the database, and because 7a's `report` is how its findings become legible. `design.md` §8.4 is rewritten with it.

**The reframe: almost everything `validate` looks for should not be there.** Stage 5 resolves the copy and the link in one pass (`design.md` invariant 13), so a broken relative asset link is not a discovery about the corpus — it is a regression in this tool. A linter written to *find* problems would be tuned for recall and would ship with a noisy baseline; this one is written to **stay** near zero, which means every gating check has to be one whose clean answer is knowable in advance. Where a check cannot make that claim — an anchor that depends on an emission convention no engine guarantees, an external URL that depends on the network — it is a warning and it does not gate. The measurement below is what turned that from a slogan into a specification: it found **two** broken links in 37,800, and it found them only after three classification rules were fixed that would otherwise have reported 121 correct links as broken and 1,626 warnings as errors.

##### Measured 2026-09-16, against a real published tree

Nothing in the checkout had ever been published, so one was built: 21 cached versions across all four engines (flare 15, docbook 4, webworks 1, dita 1) staged into a throwaway root, `convert --all` over the 19 the catalog accepted, `sync --all` into a throwaway target. That target is **6 trees, 91 published version folders, 10,190 Markdown files, 25,068 files and 728 MB**, and a prototype of the walk below was run over it.

- **40,054 references, of which 2,520 (6.3%) are raw HTML inside the Markdown** — `<a href>` and `<img src>` in the passthrough the engines emit for tables GFM cannot express — concentrated in 366 files. A linter reading only `[](…)` and `![](…)` would call the tree clean while those images 404. Separately, **11,887 `<a id=|name=>` anchor targets in 2,036 files**: the HTML is load-bearing in both directions.
- **121 of the 123 broken links were the linter's own bug, not the tree's.** With `publish_base_url` empty — the shipped state — a rewritten API-reference link is a tree-rooted path with no host (`architecture.md` §6.4.2), which `links.classify()` correctly calls RELATIVE. Resolve it against the citing page's directory and you get `html/apiguide/en-us-tib-analytics-userdocs-resources/…`, which exists nowhere. Detect it on the **raw** path instead and resolve it against `--target-dir`, and **121 of 121 resolve** — proving the link *and* that the API tree it names was actually synced.
- **That leaves 2 genuinely broken links**, the same reference in the same file in two versions of `tibco-eftl-enterprise-edition`: `api-reference/python/connection.md`, which the source package does not ship. Upstream authoring, not this tool — and still an error, because a 404 is a 404. The headline is therefore **not** zero: it is *zero from us, two from the publisher*, which is the number the acceptance criteria are written against.
- **Zero references live inside code.** Across 79,497 fenced lines and 928,552 characters of inline code span, the extractor dropped **0** links — the false-positive baseline that justified fence-stripping does not exist. The real trap is the opposite one: **787 HTML and 166 Markdown references sit on lines indented four spaces**, which is list continuation in converted help, not a code block. A CommonMark-correct extractor that honours indented code blocks would silently stop checking 953 references.
- **Anchors cannot gate.** 14,055 references carry a fragment onto a file that resolves; **12,429 match and 1,626 (11.6%) do not** — and spot-checking says these are real. `hocon-sb-JMSAdapter.md#mapsUsageNote` is cited six times in the file that should define it and the anchor is not there; `docker-create.md#docker-create_dockernotes` does not occur in `docker-create.md` at all. So the finding is worth raising — it is an unmeasured Stage 5/6 defect in its own right — and 1,626 of them cannot be allowed to fail a run.
- **`csh.yml`: 4 files, 215 entries, 0 missing file parts, and 33 of the 47 anchors missing.** The same split, from the other direction: the half `transforms/csh.py` controls is perfect, the half that depends on anchor emission is not.
- **Required artifacts are per doc-class, not global.** `online-help` has 19 `toc.yml` but only **2** `index.md` and **4** `csh.yml`; `api-references` has `metadata.yml` and nothing else (§6.2.1); the three document doc-classes have all three of `metadata.yml`, `toc.yml`, `index.md`. A single required-set would report 60 findings against correct output.
- **All 10 `-resources` product directories have no product `metadata.yml`**, because `sync` writes one per product in the docs tree only. That is as-built and undocumented either way, so it is *not* checked — see the open question below.
- **`sync` leaves `.part` directories behind when it fails.** Two online-help folders failed the copy (a Windows `MAX_PATH` overrun under `C:\tmp`, an artefact of the throwaway location) and left `1-5-0.part` and `1-6-0.part` on the shelf. The atomic swap did its job — no half-published folder — but a walk that enumerates directories counted them as two extra versions and found two extra broken links in them.
- **Cost: 93 folders and 10,190 files in 84 seconds.** Roughly a second per 120 files, single-threaded, with anchors cached per file. Extrapolated to 1,389 convert-eligible versions that is a run measured in hours, which is why the selectors are not a convenience.

##### The design

- [x] **`docushift validate` — is the output correct?** `--target-dir` (required), `--product` / `--version` / `--doc-class` to narrow, `--check-external` to verify absolute URLs over HTTP, `--dry-run` to list what would be walked. Writes findings, prints them grouped the way `report` does, and **exits 1 if and only if it recorded at least one `error`** (§7.2). The one gating command in the tool.

- [x] **It reads the disk, and the catalog is not its source of truth.** §7.1's table already says so; the consequence worth writing down is that the selectors filter *directory names*, not catalog rows. A published tree outlives the row that produced it — a product retired last week still has help on the shelf, and that is exactly when somebody wants to know whether it is intact. `validate` therefore works against a target another machine synced, with no `versions.csv` agreement required. It opens `state.db` to write its run, which is the 7a instrument being used rather than a second source of truth.

- [x] **One walk, three checkers, each a pure function over one version folder.** `validation/tree.py` enumerates `(tree, locale, slug, doc-class, segment)` from the disk; `validation/links.py`, `validation/artifacts.py` and `validation/csh.py` take a folder and return findings. None of them takes a `CatalogManager`, a `StateStore` or a `FindingsRun` — the driver records what they return. That is what makes each one testable against a fixture directory in three lines, and it is the same separation `sync/` already has between `router.py` and `distributor.py`.

- [x] **The walk skips `.part`.** A failed sync leaves its staging sibling on the shelf, and the measurement walked straight into two of them. Reporting findings about a folder the swap deliberately refused to publish is reporting on a file nobody can reach; worse, it makes a failed `sync` produce `validate` errors that a successful re-run silently cures, which trains people to ignore the gate. The presence of a `.part` is itself worth one note per folder, because it is litter from a failure that may have gone unnoticed. **New code: `SYNC_RESIDUE` (note).**

- [x] **Reference extraction reads Markdown *and* the HTML inside it.** Inline links, images, reference definitions and autolinks, plus `<a href>`, `<img src>`, `<source>` and `<iframe>` in the passthrough HTML — 2,520 of 40,054 references measured, 6.3%, in 366 files. An `<img>` in one of those is a link a renderer follows.
  - [x] **Fenced blocks and inline code spans are excluded, and indented lines are not.** The measurement found 0 references inside 79,497 fenced lines, so the exclusion buys nothing today and is kept only because a future engine emitting sample HTML inside a fence would otherwise break the gate. Treating four-space indentation as a code block, on the other hand, would stop checking **953 real references** sitting in nested list items — so the extractor is deliberately *not* CommonMark-correct here, and the reason is written into the code.
  - [x] **The extractor is multiline-aware.** `<img>` attributes in converted help span newlines; a line-oriented regex undercounts. Cheap to get right once, invisible when wrong.

- [x] **Classification and decoding reuse `transforms/links.py`.** `classify()` already strips the fragment and the query, percent-decodes and fixes backslashes, in that order — and §5.5.6 measured what skipping it costs: **1,872 WebWorks references reported missing that are not**, 1,224 percent-encoded and 648 backslash-separated. The linter has to decode exactly the way the emitter encoded or it reports the emitter's own correct output as broken. One resolution, two callers.

- [x] **A reference whose raw first segment names a tree in `--target-dir` is a host-less published URL, and it resolves against the target root.** This is the single highest-value rule in the phase: **121 of the sample's 123 broken links are what happens without it**, and `design.md` §9.6 already promised the behaviour ("§8.4 classifies these as external and does not resolve them against the filesystem") without saying where the classification happens. It happens on the *raw* path, before `resolve()` — after resolution the tree name is buried behind the citing page's own directory and the rule cannot fire. Resolving rather than merely skipping is the bonus: it catches help that links into an API tree nobody synced, which nothing else in the tool would notice. A dangling one is a `LINK_BROKEN`.

- [x] **Resolution is case-sensitive, on every platform.** The target is published to Linux. A link that differs from its file only in case resolves on the developer's Windows machine and 404s in production, which is precisely the defect class a linter is for. Where a case-insensitive match exists the message names the file that is actually there, so the fix is one rename rather than a search. It is a `LINK_BROKEN` like any other, because on the platform that matters it *is* broken. **This rule caught a data-loss bug on its first run** — see below; it is the reason the rule is in the phase rather than in a backlog.

- [x] **A missing file is an error; a missing anchor is a warning.** 1,626 unmatched fragments against 12,429 matched settles it arithmetically: an 11.6% rate cannot gate. It is still worth raising — the spot-checks say these are anchors the conversion genuinely dropped, not slug-algorithm disagreement, which makes this the first measurement of a Stage 5/6 defect nobody had counted. Explicit `id=` and `name=` attributes in passthrough HTML count as anchors alongside computed heading slugs, since the engines emit 11,887 of them. **New code: `ANCHOR_MISSING` (warning).**

- [x] **Absolute URLs are skipped by default and counted; `--check-external` checks them over HTTP.** 1,676 in the sample, and after §10.7 every link into an API reference on a configured host is one of these, so checking by default would put the API surface of every product on the wire on every run. Under the flag: deduplicated per URL across the whole run, `HEAD` with a `GET` fallback, the `discovery/client.py` request policy for rate and retry. **New code: `LINK_EXTERNAL_DEAD` (warning)** — a proxy, an outage or a host that dislikes `HEAD` is not a defect in the output, and an exit code that depends on the network is an exit code nobody trusts.

- [x] **CSH is checked as link integrity, because that is what it is** (§5.4.6, §9.6). A `csh.yml` value whose file part is absent is a `LINK_BROKEN` (0 in the sample); its anchor half is an `ANCHOR_MISSING` (33 of 47); an identifier in a topic's frontmatter that is not in `csh.yml`, or the reverse, is **new code `CSH_FRONTMATTER_MISMATCH` (warning)** — the two are written in one pass by `transforms/csh.py`, so a disagreement is a regression, but it breaks one Help button rather than the page, and §7.6's harder question is 7c's.

- [x] **The AEM artifacts get field-level checks**, replacing `design.md` §8.4's "existence and well-formedness only" rule — both of whose grounds are gone, since the shapes stopped being guesses when the AEM contract landed (2026-09-10).
  - [x] **Which artifacts are required is a per-doc-class table, not a global set.** Measured: `online-help` reliably has `toc.yml` and `metadata.yml` but `index.md` in 2 of 19 and `csh.yml` in 4 of 19; the three document doc-classes have all three (§6.2.2); `api-references` has `metadata.yml` alone (§6.2.1); `archives` has `index.md` and `toc.yml` and no version segment. One global set would raise ~60 findings against correct output. The table lives beside the doc-class constants it keys on, so adding a doc-class cannot forget it.
  - [x] **`metadata.yml`**: `csg-product` at product level and `csg-version` at version level, present and non-empty, and no version folder without one. **New code: `METADATA_INVALID` (error).**
  - [x] **`version.yml`**: every row DocuShift is entitled to own resolves to a sibling directory, every version directory has exactly one row, and the rows are in numeric-descending order. **New code: `DROPDOWN_INCONSISTENT` (warning)** — a warning, not an error, because `sync` deliberately preserves rows it does not own (`sync/versions.py`) and failing a run over somebody's intentional hand-edit is how a tool teaches people to stop running it.
  - [x] **`toc.yml`**: every `path` resolves to a file in the version folder. That is a link, so it is a `LINK_BROKEN`, and its `#anchor` half an `ANCHOR_MISSING`; giving the TOC its own code would mean two codes for one condition and a `report --code LINK_BROKEN` that misses half the broken links.
  - [x] **Any of the four YAML artifacts failing to parse is separate from any of them being wrong.** **New code: `ARTIFACT_UNPARSED` (error)** — the action is different (the file is unreadable, so no field check ran at all) and, more to the point, an unparseable file makes every other finding about that folder unsound. Reported once and the folder's remaining artifact checks are skipped.

- [x] **The `-resources` tree is walked, and `api-references/` is not link-checked.** `archives/`'s generated `index.md` and `toc.yml` are DocuShift's output and are checked like any other. The API trees are copied Javadoc — not this tool's output, not fixable from here, and 496 of 499 ship their own frame set. Walking them would dominate the run's wall-clock to report defects in somebody else's generator. Their `metadata.yml` is still checked, because that file *is* ours.

- [x] **`validate` writes nothing into the target.** The one command that reads the published tree is the one command with no business changing it; there is no `--fix`. Stated because a linter that can rewrite is the obvious next request and the answer wants to be on the record: the published tree is regenerated by `sync`, and a repair applied here would be silently reverted by the next run.

- [x] **The selectors are load-bearing, and the walk is measured.** 84 seconds for 91 folders extrapolates to hours over 1,389, so `--product` / `--version` / `--doc-class` are how the command is actually used and `--dry-run` says what a selection covers before it costs anything. Anchors are computed once per file and cached for the run; no file is read twice.

- [x] **Exit codes, all three rules in one command** (§7.4). Errors → 1. A selection that matched no version folder → 1, the same rule the four stage commands took in 7a. Anything else → 0, warnings and notes included.

- [x] **The register goes 30 → 37 and `NOT_YET_EMITTED` goes 3 → 2.** `LINK_BROKEN` starts firing and leaves the set by hand, as 7a's equality assertion requires. The six new codes are the §7.4 and §9.6 obligations that had no code because nothing had ever been written to raise them; `CSH_IDENTIFIER_DROPPED` stays outstanding for 7c and `DOC_REFERENCE_MISSING` for §10.7's class 2.

**One open question, carried rather than guessed.** No `-resources` product directory has a product `metadata.yml`, in all 10 cases, because `sync` writes that file in the docs tree only. Nothing in `architecture.md` §6.2 says whether AEM wants one there. `validate` therefore does not check it, and the phase records the gap instead of inventing a rule — a gating command that enforces a guess about someone else's contract is worse than one that stays quiet.

##### What the first run found — a Stage 6 defect, and it was losing text

The prototype read page links. The finished checker also reads `toc.yml`, and on its first run over the same tree it returned **five** errors rather than the two that were measured. The three extra were case-only: `toc.yml` said `html/install/installation.md` where the folder held `Installation.md`, in `tibco-patterns` 6.1.2 and 6.2.0 and `tibco-businessconnect-edi-protocol-powered-by-instream` 6.11.0.

The 404 was the symptom. `_slug` lower-cases a TOC container's label, and `navigation._free` tested the resulting path against the taken set **case-sensitively** — so with a converted `install/Installation.md` already on disk, `install/installation.md` looked free. On Windows it is not a second file: the generated container page was written straight into the converted topic, and `Installation.htm`'s text left the corpus without a single finding anywhere in the run. Three topics, silently, across three versions.

`_free` now folds case, the three container pages land on `installation-2.md`, and the three topics come back — the sample's file count goes 9,460 → 9,463. The measured baseline is unchanged at two errors, which is why the acceptance criterion below still reads two: the fix is what puts it back there. The general lesson is the one the reframe already claimed and this makes concrete — a check whose clean answer is knowable in advance is worth having precisely because the first thing it reports is real.

##### Acceptance

- [x] **The sample tree validates to exactly two errors, both named** — the `tibco-eftl-enterprise-edition` `python/connection.md` references in 7.1.2 and 7.2.0, exit 1. Not "clean": the measured truth, asserted as the number, so that a regression that adds a third is visible and a fix upstream that removes both is too. It reached two by way of five: see above.
- [x] **A TOC container whose slug collides with an existing topic in another case gets its own page** — `navigation._free` folds case, with a test that would have caught the three topics this lost.
- [x] **The 121 host-less API links produce no findings**, and moving the `api-references` folder aside turns all 121 into `LINK_BROKEN` — the rule tested in both directions, because a skip and a resolve are indistinguishable when everything is present.
- [x] **Deleting one asset from a published version turns exit 0 into exit 1**, with exactly one `LINK_BROKEN` row naming the file and the topic that points at it.
- [x] **Renaming a published asset to differ only in case is also a `LINK_BROKEN`**, on Windows, with the actual filename in the message.
- [x] **A `.part` folder yields one `SYNC_RESIDUE` note and no other findings**, however broken its contents.
- [x] **A reference on a four-space-indented line is checked; one inside a fence is not** — the two halves of the extractor's deliberate non-conformance, each with a fixture.
- [x] **Corrupting each of the four YAML artifacts in turn yields `ARTIFACT_UNPARSED` and no field-level findings for that folder** — the skip is asserted, not assumed.
- [x] **A `csh.yml` value pointing at a deleted topic is a `LINK_BROKEN`; a frontmatter identifier missing from `csh.yml` is a `CSH_FRONTMATTER_MISMATCH`** — the two halves of §9.6, distinguishable by code.
- [x] **`--check-external` makes no network call without the flag**, asserted by a test whose fake fetcher raises if called.
- [x] **`report --run last` reads back what `validate` just wrote**, which is the same cross-check 7a closed on and the reason 7b comes after it.
- [x] **Docs in the same commit** — `design.md` §8.4 rewritten and flipped to **Built** with its §12 row; `architecture.md` §7 gains **§7.5, what `validate` walks and what it refuses to do**, and its header stops calling `validate` unbuilt; `user-guide.md`'s `validate` block loses "not yet built" and gains the severity/exit-code paragraph and `--check-external`; `planning.md` §7.4's checkboxes and the §7.5 register's seven new rows; `CONTEXT.md` a ledger row and the register count 30 → 37.

##### Verified against the real published tree, 2026-09-16

- **The sample tree validates to exactly two errors, and they are the two that were predicted** — `tibco-eftl-enterprise-edition` 7.1.2 and 7.2.0, both citing `html/api-reference/python/connection.md`, which the source package does not ship. It reached two by way of five: the three case-only `toc.yml` rows the checker found on its first run were a real Stage 6 defect, fixed in `navigation._free`.
- **121 tree-rooted references, zero findings.** The highest-value rule, confirmed in the direction that matters: every host-less API link in the tree resolves against `--target-dir`, which also proves the `-resources` trees they name were synced.
- **9,463 files, 39,328 references, 2,418 of them HTML, 1,777 absolute, 12,440 of 14,3xx fragments matched.** The three recovered topics are the file count's move from 9,460.
- **3,006 `ANCHOR_MISSING` warnings and 1 `SYNC_RESIDUE` note over 2 `.part` folders** — exit 0 would have been wrong and exit 1 on either of them would have been worse. The gate fires on the two errors and on nothing else.
- **1,184 tests pass** (+59), lint clean.

#### Phase 7c — `csh {list,report,validate}` and the cross-version regression

The per-version identifier listing, coverage across the shelf, and §7.6's comparison against the next-lower published version, which is what `CSH_IDENTIFIER_DROPPED` is for. Last because it is the only part that needs two converted versions of one product on disk, and because a dropped identifier is a regression — something you check once the thing it regresses against is being produced routinely. `design.md` gains §8.7.

**The reframe: a dropped Help identifier is the one defect in this tool that cannot be seen from inside a version.** Every other check the tool runs is a statement about one artifact — this link resolves, this anchor is there, this `metadata.yml` has its key. §7.6's question is about two, and neither of them is wrong on its own: 6.10.0's map is correct and 6.11.0's map is correct, and the product's **Help** button still breaks on upgrade. That is why the comparison earns a command rather than a flag, and it is also why it cannot gate — the corpus says a map changes between releases far too often for "changed" to mean "broken".

##### Measured 2026-09-16, against the whole `html-to-md` cache

Every `Alias.xml`, `static/head.js` and `wwhdata/common/topics.js` under `cache/pub`, identifiers unioned per `(product, version)`, then each version compared with its next-lower one by `natural_version_key`. Script: `C:\tmp\csh_7c.py`.

| Measured | Number | What it decides |
| :--- | ---: | :--- |
| Products carrying CSH / versions carrying CSH | **153 / 470** | §7.6 is not a curiosity. A third of the catalogued products have a help map. |
| Products with ≥ 2 CSH-bearing versions | **104** | The comparison has something to compare on two thirds of them. |
| **Comparable adjacent pairs** | **317** | The population every rate below is over. |
| Pairs dropping ≥ 1 identifier | **51 (16.1%)** | `CSH_IDENTIFIER_DROPPED` fires on a sixth of upgrades. **It cannot gate.** |
| …of those, same-major upgrades | **35 of 294 (11.9%)** | Even restricted to the case that is unambiguously an upgrade, one in eight. |
| …of those, cross-major upgrades | **16 of 23 (69.6%)** | A major bump re-keys the map. That is a redesign, not a regression, and the finding says which kind it was by naming both versions. |
| Identifiers dropped in total | **784** (492 same-major) | The row count a per-identifier finding would write. |
| Median drop per affected pair | **4** (same-major: 2) | The interesting case is small. |
| Pairs losing > 90% of the prior map | **15 of 51** (same-major: 5) | Two pairs lose 188 of 188. **A per-identifier row buries the median case under the wholesale one** — 784 rows, of which 376 are two pairs. |
| Surviving identifiers that changed target | **1,084 of 8,425 (12.9%)**, in 81 of 317 pairs | **Retargeting is not a finding.** Pages get renamed between releases; the Help button still works. It is shown by `csh report --since` and never recorded. |
| Products whose oldest version has no predecessor | **150** | §7.6's "a missing prior tree is a note" would write 150 rows to say nothing happened — 32% of everything the check produces. Not written; see the refusals. |

**And the sample tree already contains one.** `tibco-businessconnect-edi-protocol-powered-by-instream` publishes 6-10-0 and 6-11-0 side by side in `C:/tmp/7b_target`, and **6.11.0's map has 28 identifiers where 6.10.0's had 123 — 95 dropped, 0 added**. The same 95 show in the cache's source alias files, so this is upstream authoring rather than a conversion defect, and it is the second time in two sub-phases that the first real run has found a genuine break in the published corpus. It means acceptance has a live finding to assert on rather than a fixture.

##### The design

**The `csh` group reads the published tree, and it takes `--target-dir` exactly as `validate` does.** This is the phase's load-bearing decision and it overrides §7.3's "coverage across a batch". A batch is a `versions.csv` column, so a batch-scoped `csh report` would have to read the catalog — and `docushift report --run last --code CSH_UNRESOLVED` already answers "did CSH come through for the batch I just converted", from the run's own findings. Building a second answer to that question is exactly the convergence §7.1's boundary exists to prevent. What has *no* reader is the shelf: which identifiers are published, where they point, and what changed since the version before. Three further consequences make it the right tree rather than merely the consistent one — the published tree is cumulative, so the predecessor is always there even when it was converted months and several runs ago; it is the upgrade path a customer actually travels; and it needs no `versions.csv` agreement, so a shelf another machine synced can be asked the question.

**One checker, three surfaces.** `validation/csh.py` gains `diff(prior, current)` and `check_regression(...)`, and nothing else computes a CSH difference. `validate` calls it in the product-folder pass it already runs `_dropdowns` in; `csh validate` calls the same functions scoped to CSH; `csh report --since` calls the same `diff` and **prints** instead of recording. The 7b ledger row is the reason the rule is written down rather than assumed: two implementations of one decoding rule is how a linter reports the emitter's own correct output as broken.

- [x] **`docushift csh list --target-dir T`** — every identifier in the selection, with its target and whether that target is on disk. Scoped by `--product` / `--version` / `--doc-class`, the same three selectors `validate` takes. **`--identifier <name>` is the query worth building the command for**: it looks one identifier up across *every* published version and prints the versions that have it and where each points, which is the question a support engineer arrives with — *the Help button for `Gateway.BusinessAgreements` is broken in 6.11.0, where did it go?* Without it the command is `cat csh.yml` with extra steps.
- [x] **`docushift csh report --target-dir T`** — coverage across the shelf: one row per product, with versions published, versions carrying a map, identifiers, distinct target pages, and identifiers dropped against the prior version. `--since <version>` narrows to one product and prints the §7.6 diff **in full** — dropped, added and retargeted, with every identifier named — which is where the 95 that the finding can only count are actually listed.
- [x] **`docushift csh validate --target-dir T`** — the §9.6 rules and the §7.6 regression, findings recorded, gating on `error` by §7.4's one rule. It is **not** `validate --product X`: it skips the link, anchor, asset and artifact passes, so it reads 4 `csh.yml` files and the pages they name instead of 9,463 files. That is the whole of its independent value and the phase does not claim more for it.
- [x] **`validate` gains §7.6** in the same commit. The gate's report has to be complete, and a warning it cannot fail on still belongs in it.

**The comparison target is the immediate next-lower version folder in the same doc-class, and nothing cleverer.** Sorted by `natural_version_key` over the **dashed published segment**, which orders correctly among segments because the key splits on digit runs and compares them numerically — `10-4-0` above `9-3-0`, measured, and the dashed form's failure to round-trip back to a dotted version (§4.1) does not touch ordering. **If the predecessor has no `csh.yml` there is nothing to compare and no finding is written.** The alternative — skip back to the last version that *had* a map — sounds more thorough and is worse: a product whose map vanishes in 6.11.0 would then report the same 123 identifiers again in 6.12.0, 6.13.0 and every version after, so one defect becomes an unbounded row count and the version that actually lost the map stops being identifiable. Under the rule as written, a vanished map fires exactly once, on the version that vanished it, with `count` equal to the predecessor's whole total.

**One warning row per version, with the magnitude in `count` and a sample in the message.** §7.1 says errors and warnings get a row each and only notes fold — and that rule is intact here, because the condition being reported is *this version dropped identifiers relative to its predecessor*, which is one condition per version and not one per identifier. The measurement is what forbids the other reading: 784 per-identifier rows, of which 376 come from two pairs, would bury the 30 pairs that dropped between one and five — and those are the ones that are actually a regression rather than a re-key. The message names the predecessor and the first few identifiers and says how many more there are; `csh report --since` is where the full list lives. The split is deliberate and it is the same one 7a made for notes: **the finding carries the magnitude, the command carries the detail.**

**No new codes, and that is worth stating after a phase that added seven.** `CSH_IDENTIFIER_DROPPED` has been registered and unemitted since 5a and this is the phase that reaches it. The register stays at **37** and `NOT_YET_EMITTED` goes **2 → 1**, leaving only `DOC_REFERENCE_MISSING`, which belongs to §10.7's class 2 and to no sub-phase yet.

##### What is deliberately not built, each with its number

- [x] **No note for "no prior version".** §7.6's third bullet asks for one; its intent was *do not fail on a first conversion*, and not writing a row honours that. Writing one would add **150 rows** to a check that produces 51 real ones — the absence is a property of every product's oldest version, and `csh report`'s coverage table shows it in the column where it belongs.
- [x] **Retargeting is not reported.** **1,084 of 8,425 surviving identifiers (12.9%) change target** between adjacent versions. That is authoring, not breakage: the identifier still opens a page. `csh report --since` prints it.
- [x] **No comparison against the *source* alias files.** The check is between two published maps. Comparing a published map against the ZIP it came from would be a second derivation of resolution, and §9.3 already rejected that for the same reason.
- [x] **No `--fix`, no rewriting of `csh.yml`**, for 7b's reason: a linter that edits the thing it is measuring cannot be trusted about either.
- [x] **`csh` does not read the catalog**, so it cannot say whether a version *should* have had a map. `status` and `report` own that question.

##### Acceptance

- [x] `docushift csh list`, `csh report` and `csh validate` run against `C:/tmp/7b_target`, and `csh list --identifier Gateway.BusinessAgreements` prints 6-10-0 with its target and nothing for 6-11-0.
- [x] **`csh validate` finds exactly one `CSH_IDENTIFIER_DROPPED`** on the sample tree — `tibco-businessconnect-edi-protocol-powered-by-instream`, 6-11-0, `count` 95, the message naming 6-10-0 — and **exits 0**, because it is a warning and the tree has no CSH error.
- [x] **A zero-drop control**, built — and the attempt to build it where the box said found a platform defect instead. Re-syncing `tibco-businessconnect-container-edition-edi-protocol-powered-by-instream` into `C:/tmp/7b_target` fails with `[WinError 3]`: the destination path is **268 characters**, past Windows' 260-character `MAX_PATH`, which is also why 7b left two `.part` folders there. Synced instead to the short root `C:/t7c` (1,005 files, 56.1 MB), where the product publishes 8 folders, 2 of them mapped, carrying the same 32 identifiers across 1 comparable pair: **0 dropped, `csh validate` reports "Findings: none" and exits 0.** A check that only ever fires has not been shown to be selective. The `MAX_PATH` failure is recorded as an Open below rather than fixed here.
- [x] `validate` over the whole tree still reports **two errors and no more**, now with the one new warning beside its 3,006 `ANCHOR_MISSING`.
- [x] `report --run last --code CSH_IDENTIFIER_DROPPED --export` reads the row back with its count.
- [x] **`NOT_YET_EMITTED` is `frozenset({"DOC_REFERENCE_MISSING"})`**, asserted equal, and the register is still 37.
- [x] Tests for the diff itself are fixture directories, as 7b's are, and none of them constructs a `CatalogManager`.
- [x] **Docs in the same commit** — `design.md` gains **§8.7 (cross-version CSH)** with its §12 index row and §9.6's fourth bullet flips from owed to built; `architecture.md` §5.4.6's last bullet and a **§7.6** for what the `csh` group reads; `user-guide.md` a CSH section; `planning.md` §7.3's three boxes and §7.6's; `CONTEXT.md` a ledger row and the status line.

##### What the acceptance run actually said

Against `C:/tmp/7b_target` — 101 version folders, 9,463 files, 39,328 references:

| | |
| :--- | :--- |
| `CSH_IDENTIFIER_DROPPED` rows | **1** — `tibco-businessconnect-edi-protocol-powered-by-instream` 6-11-0, `count` 95, message `95 of 6-10-0's 123: Gateway.BusinessAgreements, … and 90 more` |
| `csh validate` exit code | **0** — 34 warnings, no error |
| `validate` exit code and errors | unchanged: 2 errors, 3,007 warnings, 1 note |
| Zero-drop control (`C:/t7c`) | 8 published, 2 mapped, 32 identifiers, 24 pages, 1 compared, **0 dropped**; "Findings: none" |
| Register | 37 codes, `NOT_YET_EMITTED == {"DOC_REFERENCE_MISSING"}` |

`csh report --since 6.10.0` showed the shape of the failure the finding can only count: of the 123 identifiers 6.10.0 published, 95 are gone and the surviving 28 **all retargeted**, from `html/TIB_bcedi_edifact/edft.5.*.md` to `doc/html/edifact-config/*.md`. The product reorganised its help output between releases and took most of its identifiers with it — which is exactly the case the `wholesale` sentence exists to let a reader recognise without opening either file.

**Open, found here and not fixed: a `sync` destination path over 260 characters fails with `[WinError 3]` and leaves a `.part` folder behind.** Windows `MAX_PATH`. It is not a 7c defect — `sync` is Stage 7 and the two residue folders in `7b_target` predate this phase — but it is the first time the cause was identified rather than observed, and it will recur for any product whose slug, doc-class and version segment are long enough. The fixes are a shorter target root (what this phase did), the `\\?\` extended-length prefix on the destination, or enabling long paths in the registry; choosing between them is Stage 7's call, not this one's.

---

### Phase 8: The Code-Span Link Swallow

Phase 7 closed the last numbered stage, so what is left are the Opens the earlier phases named rather than fixed. This is the largest of them, and it is not a stage: it is one behaviour in the walk that every engine shares, and it silently loses more links than any defect the tool has found so far.

**The defect, in one sentence.** `transforms/markdown.py` renders a code span from its *text*, so an `<a>` inside one never reaches `link()` — the engine hook that resolves references, copies assets and records `TOPIC_LINK_DANGLING`. `<code><a href="tibems-status.htm">tibems_status</a></code>` becomes `` `tibems_status` `` and the reference is gone before any engine sees it. It is invisible in the findings register in both directions: no URL is emitted, and no dangling link is raised either, because the reference is never *classified* rather than dropped. 6e named it and left it, because it is a change to the walk every engine runs and 6e's scope was the API-link rewrite.

##### The measurement

**It is six sites, not one.** This is the first thing the measurement found and it is the reason the phase is bigger than 6e's paragraph implied. Every engine's `inline_override` maps a *class* to code and renders it the same flattening way, and `<pre>` renders a fence from the same call:

| Site | What it swallows |
| :--- | :--- |
| `transforms/markdown.py:303` | `code`, `tt`, `kbd`, `samp` — the shared inline path |
| `transforms/markdown.py:211` | `pre` — the shared **block** path, a fence |
| `engines/flare.py:276` | `span.filepath`, `span.codeph`, `span.userinput` |
| `engines/dita.py:238` | *any* tag classed `codeph`, `msgph`, `filepath`, `varname`, `parmname`, `cmdname`, `apiname`, `userinput`, `sysout`, `option` |
| `engines/docbook.py:238` | `span.command` |
| `engines/webworks.py:317` | `span.Code`, `span.CodeItalic`, `span.CodeBold`, `span.Command`, `span.URL`, `span.ErrorVariable`, `span.codeph` |

6e's published figure — **7,999 of 931,715 relative anchors, 7,761 of them alone in the span** — counted the first row only. Re-measured over all six (`C:\tmp\codespan_shape.py`, `lxml`, API roots excluded, 2026-09-16), over **all 13 in-scope products, 88,691 files**:

| | Links | |
| :--- | ---: | :--- |
| **Swallowed relative anchors** | **13,126** | Two thirds again the published figure, because the published figure counted one site of six. |
| …inside a `<pre>` | **4,964 (37.8%)** | A fence cannot hold a link. A different problem, below. |
| …in an inline span | **8,162 (62.2%)** | The fixable half. |
| **…of those, the anchor is the span's whole content** | **7,863 (96.3%)** | Invertible to ``[`text`](url)``. |
| …and the anchor is the span's **direct** child | **7,645**, with **218 wrapped** | All 218 are DocBook, which nests the anchor inside another element. The test is therefore on the *text*, not on the child list — a direct-childness check would have silently skipped every DocBook case. |
| …the anchor shares the span | **299 (3.7%)** | Needs its own answer; GFM has none. |
| …spans holding more than one anchor | **68** | The pathological case is 68 spans. |
| By engine | Flare **12,386**, DocBook **597**, DITA **143**, WebWorks **0** | DITA's 143 against 6e's 79, and DocBook's 597 against 224, is the class sites showing up. DocBook's split is `span.command` 269, `<code>` 174, `<pre>` 104, `<tt>` 50 — four of the six sites in one engine. WebWorks' 0 is only its *relative* anchors: its cross-references are `javascript:WWHClickedPopup(...)` and the scan cannot classify them, which is why the acceptance run below still finds 30 to recover there. |

**The shapes, sampled from `ems`.** The `<pre>` cases are C API signatures whose return type links to the type page — `<pre><a href="tibems-status.htm">tibems_status</a> tibems_GetAllowCloseInCallback(...)</pre>` — repeated across a reference guide. The shared spans are short and regular: `<code><a href="overflowpolicy.htm">overflowPolicy</a>=rejectIncoming</code>`, `<code>mode=<a href="stores.conf_Parameters.htm#mode">sync</a></code>`, `<code><a href="commit.htm">commit</a> and <a href="autocommit.htm">autocommit</a></code>`. None of them is a link that happens to be in a code span; all of them are a code token one *part* of which is a link.

**Two facts verified before designing, because both could have sunk a branch.** `validation/references.py` reads **both** candidate output forms with no change to it: `mask_code` blanks a backtick span but preserves offsets, so ``[`MessageListener`](../api/x.html)`` still matches `_MD_INLINE`, and a raw `<code>…<a href="b.md">…</a></code>` is not masked at all — `_CODE_SPAN` matches backticks, not tags — so `_HTML_REF` finds it and reports it with `syntax="html"`. Stage 8 will check whatever this phase emits. And `link()` **has side effects**: Flare's calls `self.engine.dangling_link(...)` and `self._asset(...)`, which copies files. Reaching it for 8,162 anchors that never reached it before will move `TOPIC_LINK_DANGLING` volumes and may copy assets nothing copied before. That is the fix working, not a regression, but it has to be measured rather than discovered.

##### The design

**One shared helper, called from all five inline sites.** `Renderer.code_span(tag)` in `transforms/markdown.py` replaces every `code_transform.inline(markdown.text_of(tag))` in the four engines and the one in the shared walk. The rule that four engines each re-implement is the rule that four engines each get wrong differently — the 7b ledger row on two implementations of one decoding rule applies here unchanged, and this time there are four.

- [x] **The anchor alone in the span inverts the nesting.** One anchor, whose text is the span's whole text, and `self.link(anchor)` returns a URL: emit ``[`text`](url)``. The URL comes from the hook, never from `href`, so §5.4's invariant 13 holds and API rewriting, asset copying and dangling-link recording all happen for the first time on these references. CommonMark binds a code span tighter than a link, so a `]` inside the backticks does not close the link text — asserted rather than assumed.
- [x] **`link()` returning `None` keeps today's output exactly.** A `javascript:` skin button or an unresolvable target renders as the plain code span it renders as now. The fix adds links; it never removes a code span.
- [x] **A span sharing its content with an anchor is emitted as raw HTML** — `<code>` with the anchors rewritten through the existing `Renderer.rewrite`, which already resolves `href` and `src` inside a subtree and unwraps a dead link while keeping its words. This is `_KEEP_AS_HTML`'s precedent and `tables.passthrough`'s, both of them the same sentence: GFM has no syntax for this and dropping it changes what the text says. It is **299 spans**, it is validated by Stage 8 unchanged, and the alternative — splitting `mode=sync` into `` `mode=` `` followed by ``[`sync`](url)`` — invents two code tokens where the author wrote one.
- [x] **Nothing is emitted from source attributes.** The raw-HTML branch rebuilds `<code>` from the subtree's text and its rewritten anchors rather than dumping the source tag, so `class="memberNameLink"` and friends do not reach the output.

##### What is deliberately not built, each with its number

- [x] **`<pre>` keeps its fence and its links stay lost — 4,964 of the 13,126 (37.8%), and this is the one call in the phase worth arguing with.** A GFM fence cannot contain a link at all, so the only way to keep these is to emit the whole block as passthrough HTML, and that trades a correct, portable, copy-pasteable code block for an HTML blob in every one of ~4,964 blocks to recover a decorative type cross-reference in a function signature. The reader of a C signature loses more than they gain. **The alternative is one line of code** — `_block`'s `pre` arm calling `tables_transform.passthrough(self.rewrite(tag))` when the block holds a link, exactly as `table` already does — so this is a preference, not a limit, and it can be flipped at approval.
- [x] **A new note code, `CODE_LINK_FLATTENED`, records the residue.** Register **37 → 38**, `NOT_YET_EMITTED` stays at 1. If `<pre>` stays out of scope then the phase ends with thousands of links still silently dropped, and *silently* is the word this phase exists to delete. A note, folded on `(code, slug, version)` with a `count`, is what §7.5 already does for magnitude-without-action; it makes the residue a number in the run report instead of a paragraph in a design document. If `<pre>` is brought in scope instead, the code still earns its place for the handful the fence branch cannot take.
- [x] **No change to `validation/references.py`.** Verified above: it already reads both forms.
- [x] **No language inference on the fences it touches.** `transforms/code.py`'s docstring forbids it and nothing here revisits that.

##### Acceptance

- [x] **The count is completed over the remaining ~64 trees** — msg-akd-repo, rtview, sfire-sfds, tea, tpm-rest, tps and the rest of amx-bpm — so the phase's headline number is the corpus's, not a third of it.
- [x] **One version per engine converted before and after, and the two runs reconcile**, as 6e's did: links emitted go up by exactly the number of anchors the new branch resolved, and nothing else moves except `TOPIC_LINK_DANGLING` and the asset count, both of which are named with their deltas rather than absorbed.
- [x] **`ems/10.4.0` is the acceptance case.** 6e measured 8 of its 89 API references rewritten, the other 81 lost to this defect; after the fix that number is the count of API references whose target resolves, and the shortfall paragraph in `architecture.md` §6.4 is rewritten rather than left standing.
- [x] **`validate` over the sample published tree still reports two errors and no more**, with the new links checked and any new dangling ones named.
- [x] Unit tests in `tests/unit/test_transforms.py`'s markdown-walk section, using its `render()` helper: the inversion, the `link()`-returns-`None` passthrough, the `]`-inside-backticks case, the shared-span HTML, the multi-anchor span, and a `<pre>` holding a link asserting today's fence — a test that pins the decision rather than the accident.
- [x] **Docs in the same commit** — `design.md` §5.1's walk gains the rule and §12 an index row; `architecture.md` §6.4's shortfall paragraph and the §7.5 register row; `user-guide.md` if the output form is visible to a reader; `CONTEXT.md` a ledger row and the status line.

##### What the acceptance run actually said

One version per engine, converted twice in one process — once with `Renderer.code_span` and once with it monkeypatched back to the flattening it replaced, which is exactly the five inline sites' old behaviour (`C:\tmp\acc_p8.py`, 1,073s, 2026-09-16):

| Version | Engine | References emitted | API URLs | `TOPIC_LINK_DANGLING` | HTML spans | Flattened |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: |
| `ems/10.4.0` | Flare | 1,178 → **2,795** (+1,617) | 6 → **86** | 1 → 2 | 406 | 1,179 |
| `sfire-sfds/10.6.5` | DocBook | 15,093 → **15,163** (+70) | 30 → 30 | 39 → 39 | 10 | 2 |
| `amx-bpm/4.2.0` | DITA | 17,654 → **17,680** (+26) | 696 → 696 | 2,328 → 2,328 | 16 | 49 |
| `bcedi/6.10.0` | WebWorks | 1,180 → **1,210** (+30) | 1 → 1 | 0 → 0 | 0 | 0 |

**The reconciliation holds in all four.** References go up and nothing goes down. `TOPIC_LINK_DANGLING` moves once, by one, in `ems` — a link that was never classified now is, and it does not resolve, which is the finding appearing for the first time rather than a regression. The other three do not move it at all.

**`ems` is the acceptance case and it is the one that mattered.** 6e measured 8 of its 89 API references rewritten and named the other 81 as lost to this defect; the fix takes it to **86**, and the three that remain are `<pre>` residue, which is the trade the phase made on purpose. The 1,617 recovered references are 1,617 links that reached `link()` for the first time — resolved, asset-copied and classified — against 1,179 the fence still flattens.

**WebWorks scored 0 in the static scan and recovers 30 here**, which is the scan's limit rather than the engine's: its cross-references are `javascript:WWHClickedPopup(...)`, which `links.classify` cannot call relative, so the count never saw them. The engine's own `link()` resolves them.

**DITA's 26 against a swallowed count of 143** is the class-site arithmetic: most of `amx-bpm`'s are inside `<pre>`, and its 49 flattened says so.

---

### Phase 9: A Generated `toc.yml` Points at Pages, Not at Artifacts

Found on the first real `sync` of a family (`datasynapse`, 2026-09-17), by reading the shelf rather than by a check. `release-information/7-2-0/toc.yml` lists the release-notes PDF and the readme TXT as two navigation items; `user-guides/` and `reference-documents/` do the same, and `archives/` lists forty ZIPs. **None of those is a page.** AEM's `toc.yml` is the reader's navigation, so every item in it is a promise that there is somewhere to land, and a PDF is a download. Each of these folders has exactly one page — the `index.md` §6.2.2 already generates — and it already carries the file list as links.

This is a **spec change, not a bug fix**: `architecture.md` §6.2.2 currently says, in as many words, "`toc.yml` is flat … with one item per file carrying `title`, `path`, `type` and `bytes`." The code does what it was told. So the doc moves first and the template follows it.

**The rule, stated once for all four generated TOCs:** a generated `toc.yml` contains exactly one item, pointing at the `index.md` beside it, titled as that index titles itself. The per-artifact list does not disappear — it stays in `index.md`, which is where a list of downloads belongs.

| Doc-class | `toc.yml` before | `toc.yml` after |
| :--- | :--- | :--- |
| `user-guides` | one item per PDF | one item → `index.md` |
| `release-information` | one item per relnotes/readme | one item → `index.md` |
| `reference-documents` | one item per licence/VPAT/doc file | one item → `index.md` |
| `archives` | one item per catalog archived row | one item → `index.md` |
| `online-help` | **unchanged** — a real nav tree of real pages | unchanged |

**`archives/` is in scope, decided rather than assumed.** Its entries are the one case with an argument for staying: they are catalog rows, not files in the folder, and most have no local file at all — so unlike a PDF they were never implying a page-per-entry. It collapses anyway, on the ground that *one* rule for generated TOCs is worth more than a defensible exception. Its `index.md` keeps the complete version history and its ZIP links, which is the part §6.2.3 actually argues for.

**The entry carries `title` and `path` only.** `type` and `bytes` described the artifact; `index.md` is not one, and publishing `type: "md"` beside `bytes: 412` for a generated page is noise that invites something downstream to branch on it.

##### What changes

| File | Change |
| :--- | :--- |
| `docs/architecture.md` §6.2.2, §6.2.3 | Rewrite "Shape of the generated files" — the per-file `toc.yml` rule becomes the single-entry rule; state the page-vs-artifact reason so it is not re-litigated |
| `docs/design.md` §10.5 | The `toc.yml` step of the document-index algorithm |
| `config/aem_templates/documents_toc.yml.j2` | Loop over `entries` → one item; drop `type`/`bytes` |
| `config/aem_templates/archives_toc.yml.j2` | Same |
| `sync/documents.py:render_toc` | Takes the title, not the entries; the docstring's "flat — these doc-classes have no hierarchy" is now the wrong reason for the right shape |
| `sync/archives.py:render_toc` | Same |
| `tests/unit/test_documents.py:277`, `test_archives.py:145` | Assert one item at `index.md`, and assert the artifact list is still complete **in `index.md`** — the point is that it moved, not that it went |

##### What this is expected *not* to touch

- **`online-help/toc.yml`** — built by `converter/navigation.py`, a genuine tree of converted pages. Out of scope, and the rule above says why.
- **`validation/artifacts.py`** — it walks every `path` in a `toc.yml` and raises `LINK_BROKEN`. It needs no change: `index.md` is a sibling and resolves. The check gets *weaker*, though, because the artifact paths it used to verify are no longer in the TOC. Whether `validate` should follow `index.md`'s links instead is a real question and is **deliberately left open** rather than folded in here.
- **`sync/archives.py:151`'s currency check** compares the published file set against `expected | {"index.md", "toc.yml", "metadata.yml"}` — a set of filenames, not of TOC entries, so it is unaffected. Confirmed by reading, not assumed.

##### Acceptance

Re-sync `datasynapse` to a scratch shelf and read the four doc-classes: each `toc.yml` has exactly one item at `index.md`, each `index.md` still lists every artifact the old TOC did, and `validate` reports no new `LINK_BROKEN`. Then the full suite.

---

### Phase 10: A Version With One Output Root Publishes At Its Version Root

Two items, raised together, that turn out to be one measurement and one correction.

#### 10a. The `doc/html/` prefix is the corpus's normal case, not a staging accident

`online-help/7-2-0/` contains `doc/`, `metadata.yml`, `toc.yml` — every converted page sits under `doc/html/`, and every one of the 1,196 `toc.yml` paths is prefixed with it. This was previously written off as an artifact of staging `datasynapse` from the crawl cache's website-mirror root. **It is not.** Measured over the cache on 2026-09-17, by walking for `Data/HelpSystem.xml`:

| | |
|---|---|
| Flare output roots | 888 |
| version trees carrying them | 611 |
| **single-root version trees** | **491** |
| of those, root sitting *at* the version root | **0** |
| where it sits instead | `html/` (257), `doc/html/` (203), 31 others (`doc/adswift/html`, `doc/mi/html`, `users-guide`, …) |

So the rule in `architecture.md` §5.1.3 — a unit converts into a subtree "named from the root's path relative to the version" — puts **80.4% of Flare versions one or two directories below where the published contract says their content lives**. `datasynapse` is not the exception; it is the ordinary case, and it is only visible now because it is the first family read end-to-end since `validate` landed.

**The rule, in three cases.**

1. **One unit of work** → its subtree name is empty; output goes at the version root. 491 Flare versions.
2. **Several units, none nested inside another** → the **shallowest** root (ties broken by path, which is `find_output_roots`' existing order) takes the version root, and every other root becomes a folder named by its **last segment only**. `doc/html` + `doc/relnotes` publishes as the version root plus `relnotes/`. 93 versions.
3. **Several units with a nested pair, or a name clash in case 2** → today's full relative name, unchanged. 32 + 1 versions.

Case 3 is not a hedge, it is a measurement. Flattening every root onto the version root — the naive reading of "remove the `html` segment" — was tried against the cache and collides in **125 of 125 multi-root versions, 155,647 colliding paths**; BusinessWorks 6.10.0 alone collides 7,101, because separate Flare builds reuse the same `_templates/` chrome and overlapping topic filenames. Case 2 avoids that by giving each non-primary root a folder of its own; it is safe because the only thing that can collide is the folder name against the primary's own top-level entries, which was measured across all 93 and clashes **once** (`stat` 14.4.0, which ships two roots with the same last segment). Nested roots cannot use case 2 at all: the inner root's files are already inside the outer one, so naming the inner root as a sibling folder does not separate them.

The single-root case cannot collide with itself — there is one subtree, so there is nothing to collide with.

The combined `toc.yml` needs no new merging logic: a version folder already has exactly one `toc.yml` covering every unit, so `doc/html/install.md` and `doc/relnotes/notes.md` already sit in the same file. Only their prefixes change.

**The one real conflict, and why it resolves itself.** Collapsing lifts the root's own top-level files up beside the generated `csh.yml`/`toc.yml`/`metadata.yml`. Measured across the 495 single-root roots: no root ships a `toc.yml`, `metadata.yml`, `csh.yml` or `version.yml`, and **38 ship an `index.htm`/`index.html` that converts to `index.md`**. That last one is not a collision to prevent — it is the landing page `architecture.md` §6.1 wants at the version root, arriving on its own. `navigation._free` already tests case-insensitively against the converted set (Phase 8's lesson), so a synthesized container labelled "Index" is given another name rather than written over it. Confirmed by reading `navigation.py:291`, not assumed.

##### What changes

| File | Change |
|---|---|
| `converter/driver.py:261` | `unit_name = _relative(tree, root)` → the shared helper; `handler.units(context)` is materialized to a list first, because the name of the *first* unit now depends on how many there are |
| `engines/roots.py` | new `subtree_names(tree, roots) -> dict[Path, str]` — the three cases above, decided once for the whole version and returned as a lookup. A per-root function could not see the clash in case 2 |
| `engines/base.py` | `unit_name(context, root)` reads that lookup. One definition, because the driver's asset path and the engine's `Unit.name` must agree or assets and pages land in different subtrees |
| `engines/flare.py:388`, `dita.py:556`, `docbook.py:411`, `webworks.py:993` | all four already call `_relative(context.tree, root)`; each becomes the shared helper |
| `converter/base.py` (`ConversionContext`) | carries the unit count the helper reads |
| `architecture.md` §5.1.3, `design.md` | the rule, the 0-of-491 measurement, and the multi-root refusal |

Everything downstream is derived from `unit.name` and follows without edit: the output map, `csh.yml`'s paths, the synthesized `toc.yml`, cross-reference resolution. That is the argument for changing the name in one place rather than rewriting paths at the end.

##### What this is expected *not* to touch

- **Nested-root versions** — 32 Flare version trees, plus the 1 name clash, keep today's full relative names.
- **`online-help`'s missing `index.md` in the general case.** Collapsing hands 38 versions a real one and puts `datasynapse`'s landing page (`_templates/Home.md`) at the version root, but it does not *synthesize* an index where the source has none. Still open, still separate.
- **The `_templates/` directory** appearing in published output. Noted here as an open chrome question; **closed 2026-09-17 as correct behaviour, not a leak** — see Phase 11's note below.

#### 10b. `validate` already follows `index.md`'s links — the recorded gap is wrong

Phase 9 recorded that dropping artifact paths from `toc.yml` weakened `validate`, because `validation/artifacts.py` now sees only `index.md`. **Tested rather than reasoned about:** renaming `TIB_dsp_gridserver_7.2.0_relnotes.pdf` in the scratch shelf and re-running `validate` produced exactly `LINK_BROKEN 1 row(s), 1 occurrence(s)`, `1 error`. `index.md` is a Markdown page, the reference checker walks every Markdown page, and it therefore checks the artifact list wherever that list lives. Nothing was lost. The claim is corrected in `CONTEXT.md` §3 and `architecture.md` §6.2.2.

What is genuinely absent is the **opposite** direction — a file sitting in a published doc-class folder that `index.md` links to nowhere. There is no published-tree orphan check at all (`ASSET_ORPHANED` is a Stage 4 note about the extracted tree, not this), so this is a new check and not a restored one: one function in `validation/artifacts.py` taking the files present, minus the generated four, minus what `index.md` links to.

**It is expected to find nothing, and that is the point.** `render_index` is given the same routed list that decides what gets copied, so every published artifact is linked by construction. The requirement "all files should be linked in `index.md`" is therefore already met; what is missing is anything that would *notice* if a future change stopped meeting it. Hence `INDEX_UNLINKED`, at note severity — a gate that fires on correct output teaches people to skip it (§8.4's rule), and a silent invariant is one refactor away from being false.

##### Acceptance

Re-convert and re-sync `datasynapse` to a clean shelf: `online-help/7-2-0/` lists the converted pages directly, no `doc/` segment anywhere in it, and its `toc.yml` paths carry no prefix. `validate` on that shelf reports no `LINK_BROKEN` — which is the real test of the change, because every one of 1,196 TOC paths and every cross-reference moved at once — and no `INDEX_UNLINKED`. A multi-root version is converted and read: the primary at the version root, the secondary in its own folder, both in one `toc.yml`. A nested-root version is confirmed unchanged. Then the full suite.

---

### Phase 11: The Landing Page Keeps Its Product, Loses Its Portal

`online-help` is navigated by `toc.yml` and needs no `index.md` — Phase 10b's `INDEX_UNLINKED` already excludes it, and Phase 10's note that `online-help`'s missing index is "still open" is hereby **closed as not-a-gap** rather than left pending.

Two changes to what that navigation and its landing page contain, both of them subtractive in spirit: the What's New topic becomes the first topic in `toc.yml` when it says something, and `_templates/Home.md` stops carrying the doc-portal blocks that only make sense on `docs.tibco.com`.

#### 11a. What's New first, unless it is still the template

**Measured over 903 Flare roots.** 797 carry `_templates/`; 648 carry a What's New file. The filename is not stable — `Whats-New.htm` dominates, with `Whats-New.html` (12), `What_s-New.htm` (9), `Whats_New.htm` (6), `What's-New.htm` (5) and per-component variants (`-client`, `-server`, `-old`) behind it — so the file is found by a normalized-name match inside `_templates/`, not by one literal.

**481 of the 648 are real; 167 are not.** The 167 are the authoring template shipped unfilled, and its main content is verbatim:

> What's New \[Provide list of update made to the product documentation. You can either provide list or categorize in sections of different features and components. You can also provide links to the topics which are updated.] \[Feature Name] \[Use sections with h2 styles to further categorize new features.]

**The detection rule needs no threshold, and that is why it is trustworthy.** Take the main content's text, drop every `[...]` span, drop the "open topic with navigation" chrome, drop the leading "What's New" heading, strip all non-alphanumerics, and count what is left. Across 654 files the residue is **0 for 167 files, 60+ for 467, 20–59 for 20 — and never between 1 and 19.** The twenty in the middle are genuine short releases ("No new features have been added in this release."). A gap that wide is not a tuned cutoff; `residue == 0` *is* the rule, and the 167 split as 5 empty main content and 162 unfilled stub.

| | versions | what changes |
|---|---|---|
| Real, already in the source TOC | 407 | entry **moves** to the front |
| Real, not in the source TOC | 74 | newly injected; today `_rejection()` discards these as `unreferenced-template` |
| Placeholder, in the source TOC | 4 | entry **removed** from nav |
| Placeholder, not in the source TOC | 163 | unchanged — already discarded today |

The 4 in row three are the only versions that lose an existing navigation entry, and they lose a page whose entire body is bracketed instructions to the writer.

**Position: second, after `_templates/Home.md`.** Home is the landing page and stays the entry point.

```
before                        after
- Home                        - Home
- Installation Guide          - What's New
  - What's New                - Installation Guide
- Administration Guide        - Administration Guide
```

The 74 injections also mean `_rejection()` can no longer treat an unreferenced What's New as chrome: the TOC builder decides it is referenced, so the rejection rule has to be asked *after* that decision rather than before it.

#### 11b. `Home.md` keeps the product, drops the portal

The converted landing page today ends with blocks that belong to the documentation website, not to a published version folder — and because their links were external or dropped, most of them render as bare text lists:

```
## Release Documents            ## Downloadable PDF Guides
- Readme                        - Installation Guide
- Release Notes                 - Introducing Grid Server
- License Agreement             - Administration Guide
...                             ...
```

Keep the overview and Key New Features; cut from the first portal block onward. The blocks are a **closed, measured set** — `Release Documents` (545), `Related Product Documentation` (537), `Most Visited Topics` (482), `Downloadable PDF Guides` (457), `Videos` (49), `Key Guides` (27), `Recommended Topics` (18), plus the `Related Products Documentation` and `Downloadable PDF Guide` spelling variants — so truncation is at the first of those labels rather than at "the section after Key New Features".

**Why the label list and not the Key-New-Features anchor.** 421 of 778 Homes have a Key New Features section and 351 do not; anchoring on it would leave a third of the corpus untrimmed. More importantly, 10 versions carry *genuine* feature subsections after it (`Server Improvements`, `Security`, `Governance & Security`, …), and anchoring would delete them. Truncating at the first portal label keeps those.

Run over all 778 Home files: **688 trimmed, 90 untouched** (no portal block present), and **0 in which a Key New Features section would be cut**. The headings kept before the cut are 2 for 446 files, 1 for 193, 3 for 31.

The h1/h2 lens is not enough on its own — `datasynapse`'s Home has exactly one `h1` and no `h2`, yet converts to a page with `## Key New Features`, because Flare styles these labels with classes rather than heading tags. The detector therefore reads the *converted Markdown* headings, which is the form the rule is actually stated about.

#### 11c. `_templates/` in the published tree is content, and stays

Phase 10 left open whether the `_templates/` segment surviving into `online-help/<version>/` was chrome leaking out of the Flare build. **It is not.** The directory is where a Flare project keeps the pages that are common to the whole product rather than to one guide, and the corpus's own TOCs treat them as topics: **1,737 `_templates/` paths are TOC entries across 660 of 676 roots** — legal 657, support 649, what's new 381, home 32, other 18. A rule that stripped the directory would be stripping a reader's landing page, legal notice and support page.

So the exclusions stand exactly as already defined, and no new one is added:

- a `_templates/` file no TOC entry reaches and that is not the `DefaultUrl` is not converted (`unreferenced-template`, §5.1.5);
- a What's New page still holding the authoring template is not converted even where a TOC entry *does* reach it (`placeholder-template`, 11a above).

Everything else under `_templates/` publishes where the source put it. The directory name is a Flare convention showing through into the output tree, and that is the same trade every other source directory name gets: the path is the source's, the content is the product's.

##### Acceptance

Re-convert and re-sync `datasynapse`. `logviewer 1.0.0`, `manager 7.1.1`, `manager 7.2.0` and `hpc-cloud-adapter 2.2.0` each show What's New as the second `toc.yml` entry; `hpc-cloud-adapter 2.0.0` and `2.1.0` show none, and no `Whats-New.md` is published for them. Every `Home.md` on the shelf ends at Key New Features with no `Release Documents` or `Downloadable PDF Guides` block. `validate` reports no new `LINK_BROKEN` — the trim removes links, so the risk is an anchor elsewhere pointing into a cut section. Then the full suite.

---

### Phase 12: An Extracted Tree Can Be Measured Without Its Package

Stage 4 writes five columns for one version — `_has_csh`, `_csh_names`, `_has_api_ref`, `_api_files`, `_doc_files` — from one walk, in `record_extract_inventory` (`catalog.py:798`, called from `unpacker.measure`). Nothing else writes them: convert reads the extracted tree and produces Markdown, and `convert_batch` beside them is an *input* label set by `catalog set --batch`, not an output. So a version whose columns are blank has never been measured, whatever else has happened to it.

Six versions on disk are in exactly that state, and they are the six that have been converted:

| | |
|---|---|
| extracted version trees in `families/*/extracted/` | **6** (all DataSynapse) |
| of those, matching a catalog row | 6 |
| of those, **blank inventory columns** | **6** |
| trees extracted | 2026-05-29 … 2026-07-27 |
| `record_extract_inventory` landed (`b094ed1`) | **2026-09-11** |
| converted output written | 2026-09-17 |

The trees predate the writer by two to four months. `engine=flare` on those rows is not evidence of a run that could have measured them — `engine_source=manual` on both `gridserver-manager` rows; it was set by hand.

#### The branch that already exists, and the two guards that stop it

`unpacker.extract_one` **already** handles this. Its unchanged-package fast path is deliberately not a pure no-op:

> *"An unchanged package is a no-op unless nobody has measured it. A tree extracted before the inventory walk existed has blank columns, and reporting `current` over a blank row would leave it blank for good."* (`unpacker.py:186-193`)

It runs `identify` + `measure` over the tree already on disk and writes the five columns without unpacking anything. That is the behaviour wanted here; it simply cannot be reached:

1. **`source.is_file()` at `unpacker.py:168`** returns `NO_PACKAGE` first. There are **0 ZIPs** anywhere under `families/*/downloads/` — the 249M on disk is extracted trees. `--force` fails at the same line, so *neither* route to `measure` is reachable.
2. **The checksum test at `unpacker.py:179`** cannot pass even after a re-download: `state.db` holds **0 rows** with `extract_zip_checksum`, out of 3,453 `version_metadata` rows. That key is written only after a successful unpack, and these unpacks predate it too. A re-download therefore buys a full re-extract, not a measurement.

The package is wanted for one thing — a checksum, for the *currency* test. `measure()` takes a tree and walks it; it has no use for the archive.

#### What changes

| File | Change |
|---|---|
| `extractor/unpacker.py` | a `measure_cached(product, version)` route: `target.is_dir()` and the inventory columns blank is sufficient; it runs `identify` + `measure` and returns a new `ExtractOutcome.MEASURED`. The existing `source.is_file()` guard stays exactly where it is on the unpack path |
| `cli.py` (`extract`) | `--measure-only`, taking the same selection flags. Mutually exclusive with `--force`, which means the opposite thing |
| `extractor/unpacker.py` (`extract_many`) | reports `MEASURED` separately from `EXTRACTED` and `CURRENT`, so a run that touched no archive says so |
| `architecture.md` §3.9 | the five columns can be written from a cached tree, and what that does and does not assert |

#### What it deliberately does not do

- **It does not write `extract_zip_checksum`.** There is no package to hash, and a fabricated key would make the next real `extract` think the tree is current. The row stays "measured but not checksummed", which is the truth.
- **It does not claim the tree is current.** The columns describe what is on disk. This satisfies the rule the stage is built on — never write a number you did not just measure — but it cannot assert the tree was built from today's upstream ZIP. `--measure-only` is opt-in for that reason; the default path keeps demanding the package.
- **It does not backfill zeros.** `measure` already refuses to write columns for a partial walk (`unpacker.py:307`), and that refusal carries over unchanged: a blank row after a `--measure-only` run is a signal, not a failure of the flag.
- **It does not re-detect a manual engine.** `identify` refuses to overwrite `engine_source=manual` (§7.3 step 3), so the two `gridserver-manager` rows keep `flare` whatever detection says — and the run report should say when detection disagreed, rather than silently agreeing.

##### Acceptance

`extract --product tibco-datasynapse-gridserver-manager --measure-only` with `downloads/` still empty: outcome `MEASURED`, no network, no `.part` directory created, and `_has_csh`, `_csh_names`, `_has_api_ref`, `_api_files`, `_doc_files` filled on `7.1.1` and `7.2.0`. Byte-compare the extracted tree before and after — a measurement must not touch it. Re-run the same command: the rows are no longer blank, so it reports nothing to do. Then `--measure-only` over all six, and check the two booleans against their counts — `_has_csh=true` with `_csh_names=0` is legal and expected (55% of the corpus ships an empty help map), `_has_csh=false` with `_csh_names>0` is the contradiction `catalog import` already gates on (`catalog.py:1078`). Finally `extract --product … --measure-only --force` is refused with a message rather than doing something surprising, and the full suite.

---

### Phase 13: The Output Tree Is Counted Too

Five columns describe the package going **in** — `_has_csh`, `_csh_names`, `_has_api_ref`, `_api_files`, `_doc_files`, all written by Stage 4's one walk. Nothing describes what came **out**. `convert` counts topics, generated pages and assets while it runs and prints them (`cli.py:1253`), and those numbers die with the process: `report` reads findings, `status` reads `version_state`, and neither can answer "how big is the Markdown for this version" for a run that finished last week. The catalog is where a per-version number lives, and on the output side it holds none.

#### Why the API count is not repeated

Because it is the same number at both ends, and storing it twice would be storing it twice. The converter **skips** API-reference trees (`flare.py:562`, on `apiref.is_api_reference`), so no API file is ever written into `output/`; Stage 7 copies those trees **verbatim** out of the *extracted* tree into `{resources-tree}/…/api-references/…` (§10.6). A Javadoc tree that arrives as 1,466 files is published as 1,466 files, and `_api_files` already says so.

So the before/after pair to read across a row is **`_doc_files` → `_out_files`**, and `_api_files` sits outside both ends of it, unchanged by construction.

#### Two columns, measured rather than derived

| Column | Meaning |
|---|---|
| `_md_files` | Markdown files in the version's output tree — converted topics **and** the pages Stage 6a generated |
| `_out_files` | **Every** file in that tree: the Markdown, the assets that were copied, and the `toc.yml` / `metadata.yml` / `csh.yml` artifacts |

Assets get no column of their own: they are `_out_files - _md_files` minus the artifacts, and the subtraction carries no nuance the way `_has_csh` against `_csh_names` does.

**Both come from one walk of the output tree, not from the run's counters** — and that is not ceremony. The obvious derivation, `documents + generated + assets + 3`, is already wrong by one on **every** version on disk today: `csh.yml` is written only when the map is non-empty (`transforms/csh.py:275`), and all six converted versions have `_csh_names=0`, so all six have **two** root artifacts, not three. A constant that is already false on 6 of 6 is not a constant.

#### What the corpus says, walked by hand on 2026-09-19

| version | `_doc_files` (in) | `_out_files` | `_md_files` | assets | out/in |
|---|---|---|---|---|---|
| `gridserver-logviewer` 1.0.0 | 345 | 46 | 27 | 17 | 13% |
| `gridserver-manager` 7.1.1 | 1,458 | 981 | 930 | 49 | 67% |
| `gridserver-manager` 7.2.0 | 1,552 | 1,050 | 1,000 | 48 | 68% |
| `hpc-cloud-adapter` 2.0.0 | 290 | 25 | 20 | 3 | 9% |
| `hpc-cloud-adapter` 2.1.0 | 313 | 29 | 24 | 3 | 9% |
| `hpc-cloud-adapter` 2.2.0 | 314 | 31 | 25 | 4 | 10% |
| **total** | **4,272** | **2,162** | **2,026** | **124** | **51%** |

Two things fall out that no existing column can show. **The output is 94% Markdown** — 124 asset files out of 2,162 — because a Flare package's file count is dominated by skin chrome and orphan images, neither of which is copied (§6.4 step 7: 54.6% of Flare's images are orphans). And **the ratio is not stable**: two products of the same generator land at 67% and 9%. A 9% survival rate is either correct or a conversion that quietly lost a guide, and today nothing in the catalog lets anyone ask which.

All six carry `_api_files=0`, so the "API files are unchanged" claim above is not demonstrated by this slice — it rests on the converter's skip and Stage 7's verbatim copy, which is where it should rest.

#### The invariant it buys

`_md_files` must equal `documents + generated`. When it does not, two writes landed on one path — which is not hypothetical: Phase 7b found `navigation._free` comparing a generated container page's path case-sensitively, so on Windows the page was written **over** a converted topic and three versions shipped with content silently replaced. That defect is arithmetic once the tree is counted. A new `warn` code, `OUTPUT_COUNT_MISMATCH`, carries the difference (register **40 → 41**); it is separable if the register is to stay put, but the check is the cheapest part of the phase and it catches the one failure mode that has already shipped once.

#### What changes

| File | Change |
|---|---|
| `models.py` | `ProductVersion.md_files`, `.out_files`, both `int \| None` — blank and `0` are different answers, as on the extract side |
| `catalog.py` | `VERSION_COLUMNS` gains `_md_files`, `_out_files` after `_doc_files`; `_INVENTORY_COLUMNS` splits into an extract tuple and a convert tuple; `parse_optional_int` / `format_optional_int` round-trips; `record_convert_inventory(slug, version, md_files, out_files)` and `clear_convert_inventory` |
| `converter/driver.py` | `_measure_output(path)` — one walk, two counts — called **after the swap** in `_build`, and on the `CURRENT` fast path when the columns are blank; `ConvertResult.md_files` / `.out_files` |
| `cli.py` (`convert`) | the per-version line and the run summary report files on disk beside topics and assets |
| `reporting/findings.py` | `OUTPUT_COUNT_MISMATCH`, warn, Stage.CONVERT |
| `architecture.md` §3.9, `design.md` §6.4, `user-guide.md` §2 | the two columns, who writes them, and the `_doc_files` → `_out_files` reading |

Nothing is needed in `version_snapshot`: discovery has no value for these, and the snapshot carries only fields discovery owns, so the merge exclusion is structural rather than a rule (`catalog.py:129`).

#### The `CURRENT` fast path is not optional here

Phase 12 exists because a column shipped that a no-op left blank forever. `convert_one`'s unchanged-input fast path (`driver.py:205`) returns `CURRENT` without building anything, and a version converted before this phase would report `CURRENT` on every future run and never be counted. So the same rule 4b-1 wrote into `extract_one` applies: **`CURRENT` with blank output columns walks the target tree anyway.** It is a directory walk against a conversion, which is free.

This is also why `convert` gets no `--measure-only` twin. `extract` needed one because its fast path was gated behind a ZIP that no longer exists; `convert`'s is gated on a checksum and the output tree itself, both of which are on disk.

#### What it deliberately does not do

- **It does not count the published tree.** `_out_files` describes `output/<family>/<slug>/<version>/`, which is Stage 5's. What Stage 7 placed into a target workspace is `validate`'s question, answered against the target with no `versions.csv` agreement required (§7b), and a catalog column claiming to know it would be claiming to know another machine's disk.
- **It does not count what was skipped.** Topics dropped as `runtime-stub` or `empty`, orphan assets, dangling references — all already findings with codes, and folding them into a footprint column would make a healthy version and a broken one read the same.
- **It does not write on a failure.** `NO_TREE`, `ENGINE_UNKNOWN` and `FAILED` leave both columns exactly as they were, on §6.3's blank-not-zero rule: a version that did not convert is not a version that converted to nothing.
- **It does not add a boolean.** `_has_api_ref` is the one derivable column in the set and it is justified as a filtering convenience; `_out_files > 0` needs no second spelling.
- **It does not special-case `--input`/`--output`.** A conversion through overridden paths already writes `output_map` and `version_state` unconditionally (`driver.py:301`), and branching the catalog write on provenance would make the columns mean two things.

#### Tests

Round-trip: blank survives as blank in both directions, a measured `0` survives as `0`, an Excel `1,050` parses. A `FAILED` convert leaves both blank; a clean one with no assets writes `_md_files == _out_files - 2`. A version whose `csh.yml` **is** written lands on `- 3`, pinning the artifact count as measured rather than assumed. `CURRENT` over a blank row walks and fills; `CURRENT` over a filled row does not walk. `_md_files != documents + generated` emits `OUTPUT_COUNT_MISMATCH`, and the collision that produces it — two documents resolving to one path — is constructed rather than mocked. `clear_convert_inventory` blanks both and leaves the five extract columns alone.

One test here is not about output files at all. Registering the 41st code turned up three earlier ones — `CODE_LINK_FLATTENED`, `INDEX_UNLINKED`, `WHATS_NEW_PLACEHOLDER` — that were in `findings.py` and missing from §7.5, because the only test guarding that table compared the register's size to a literal and could not see the document. `test_the_published_table_carries_every_registered_code` reads this file and asserts every registered code appears as a row in it.

##### Acceptance

`convert --product tibco-datasynapse-gridserver-manager --force` and read the row back: `_md_files=930` and `_out_files=981` on `7.1.1`, `1000` / `1050` on `7.2.0`, matching the hand walk above. Re-run without `--force`: no re-conversion, no change to the columns. Then blank the two columns on one row by hand and re-run — the `CURRENT` path fills them without rewriting the tree, and the output tree is byte-identical before and after. Convert all six and check the totals against the table: **2,026 Markdown files, 2,162 files**, and `OUTPUT_COUNT_MISMATCH` emitted **0** times. Finally the full suite and `ruff`.

**Verified, 2026-09-19.** All six converted and every row read back matches the hand walk to the file: 930/981 and 1000/1050 on the two `manager` versions, 27/46 on `logviewer`, 20/25, 24/29 and 25/31 on the three `hpc` versions — **4,272 in, 2,162 out, 2,026 Markdown, 124 assets**. `findings` holds **0** `OUTPUT_COUNT_MISMATCH` rows, ever. **1,270 tests pass**, `ruff` clean.

One clause of the acceptance could not be run, for the reason Phase 12 found: none of these six carries an `extract_zip_checksum`, so `convert_one`'s `checksum` is empty and the `CURRENT` branch is unreachable for them — a second run reconverts rather than reporting `Already current`. The backfill on that branch is covered by two unit tests instead (walks a blank row and fills it, leaving the tree byte-identical; does not walk a filled one), and it will be exercised on the corpus the first time a version is converted from a package that is actually on disk.

---

### Phase 14: The Download Leg Has Never Run — **Built, 2026-09-19**

Three defects on one path — catalog row → ZIP → extracted tree — all found in one attempt to convert the `ems` family, and none of them reachable from the test suite: each needs either the live docsite or a real package deep enough to hurt.

The three compound. `zip_url` is wrong, so nothing downloads; nothing downloads, so `extract` never runs on a real package; `extract` never runs, so the path-length ceiling under `.part/` has never been hit. Every extracted tree in this repo arrived by hand-copy from the predecessor's cache, which is why Phase 12 was needed at all — and why `status` has reported `Downloaded 0%` on every family since the column existed.

#### 14a. Every active `zip_url` in the catalog is wrong

| | |
|---|---|
| products sampled (newest eligible version each) | 35 |
| stored `zip_url` returns a ZIP | **0** |
| landing-page pattern returns a ZIP | **28** |
| neither pattern resolves | 7 |
| `ems` eligible versions, stored `zip_url` | 0 of 7 |
| `ems` eligible versions, landing-page pattern | **7 of 7** |

It went unnoticed because **the docsite answers a missing `/pub/` path with HTTP 200 and an empty body**. The 2026-09-03 ledger row recording "33 EMS versions, 4 spot-checked URLs all HTTP 200" was checking the status code, and the status code is not the signal. `downloader/fetcher.py` already catches this correctly at download time — *"did not return a readable ZIP (most often an error or sign-in page served as HTTP 200)"* — so the defect was always going to surface here rather than in discovery.

The real pattern is not guessed. It is read out of `html/Resources/Scripts/landing-page.js`, a MadCap Flare file shipped **inside the package**, which reproduces the product's docsite landing page and builds its own Download Help link:

```js
finalSlug = slugify(productName) + "-" + version.split(".").join("-")
baseUrl   = location.href.split("doc/html")[0]      // -> /pub/{code}/{version}/
download  = baseUrl + finalSlug + "_documentation.zip"
```

Two things follow. The ZIP sits at the **version root**, not under `doc/zip/`; and its name carries the *dashed* version a second time. `finalSlug` is re-derivable from the display name, but need not be: the docsite API already publishes it as the per-version `slug` (`tibco-ebx-add-ons-6-2-3`), and in every case measured it equals the catalog's `slug` plus the dashed version. Re-implementing the JS `[^\w\s]` fold would be a second slugifier to keep in agreement with `utils/slug.py`, for no gain.

| File | Change |
|---|---|
| `config/docsite.yaml` | `active_template` becomes `/pub/{folder_path}/{slug}-{version_dashed}_documentation.zip`. The old template stays as a commented `legacy_template` with its measured 0-of-35 beside it, so the next person does not re-derive it |
| `discovery/client.py` | `active_zip_url(folder_path, slug, version)` — two new tokens, same `None`-rather-than-malformed contract |
| `discovery/crawler.py:309` | passes the slug and version it already holds |
| `downloader/fetcher.py` | derives through the same function rather than trusting the column |

**Precedence is the crux**, because the column is not empty — all 4,462 rows hold a confidently wrong string, so a plain `row.zip_url or template(...)` would never once reach the template. Stored wins only where it is a human override or an upstream-given fact:

1. `zip_source=manual` — the row is pinned by hand (§3.8). Stored wins.
2. archived — the stored value is the archive index's `zipPath`, given verbatim by upstream, never templated (`crawler.py:309` already refuses to guess one). Stored wins. `download` never fetches these anyway.
3. otherwise, active and `auto` — **derive**. The stored value is discovery output, and discovery output is known wrong catalog-wide.

That is what holds the catalog diff at **0 rows**. The residual untidiness is worth stating rather than hiding: for active rows `zip_url` keeps a stale string that nothing reads, until the next `catalog fetch` rewrites it through the corrected template. It is not blanked, because a 4,462-row deletion commit to remove data the next fetch regenerates is churn, and a blank column cannot be distinguished from "discovery found nothing".

The 7-of-35 residue is **reported, not chased**. Its shape is a directory-segment problem rather than a filename one — `businessworks_integrationmanager_plugin` publishes under `1.0.0_october_2004` while its catalog version is `1.0` — and each case looks bespoke. A new **`ZIP_URL_UNRESOLVED`** (warning) names the version and points at `--from-file`, which exists for exactly this. Register **41 → 42**.

#### 14b. The `.part` staging suffix pushes extraction over Windows MAX_PATH

All six EMS packages failed identically, on the deepest file in the `.NET` API tree:

| | |
|---|---|
| failing path, under `.part/` | **262** chars |
| the same path after the swap | **257** chars |
| Windows limit without opt-in | 260 |
| `HKLM\…\FileSystem\LongPathsEnabled` on this machine | `0x0` |

The tree is legal at its destination and illegal only while being built. The build-and-swap that exists to make extraction atomic is what makes it fail — `.part` costs 5 characters and the margin was 3. This is not an EMS quirk: `dotnetdoc`/`javadoc` trees across the corpus generate names like `class_t_i_b_c_o_1_1_e_m_s_1_1_a_d_m_i_n_1_1_detailed_transaction_info_1_1_producer_message.html`, and the real ZIP adds a wrapper directory (below) that the cache trees never had.

Shortening the suffix is rejected: it buys 4 characters against a ceiling that deeper trees will clear anyway, and it would trade a loud failure for a rarer one. **The fix is the `\\?\` extended-length prefix on write**, verified in isolation — a 278-character path fails on the plain form and succeeds on the prefixed one. It needs no administrator, no registry change, and no per-machine setup, which matters because the next person to run this has a different checkout depth.

| File | Change |
|---|---|
| `utils/` (new helper) | `long_path(p)` — on Windows, return `\\?\` + the absolutized, normalized path; elsewhere return it unchanged. One owner, because a second copy is how two writers end up disagreeing |
| `extractor/safe_unzip.py` | member writes and `makedirs` go through it. The traversal refusal stays **before** it and unchanged — prefixing must not become a way to escape the target |
| `utils/swap.py` | the rename pair, which is where a 262-char source still has to be addressable |

`\\?\` disables path normalization, so it must be applied to an already-absolute, already-normalized path — which is also why it belongs in one helper rather than at each call site.

**Built as `utils/longpath.py`, and it cost one more change than the table says.** `ZipFile.extract` joins the member onto a target it builds itself, so handing it a prefixed directory puts the limit straight back; `safe_extract` now opens each member and copies it to a destination it computes, which is also the point at which the already-proven-safe member name is the only sanitization being given up. The scope is deliberately the two *writers* of a staged tree and nothing downstream: a **final** extracted path over 260 characters would still be unreadable to every consumer, and that is a condition to report rather than to paper over one call site at a time. EMS does not reach it — 257 is the deepest — but a corpus-wide run may, and prefixing the whole pipeline would be a much larger change made on no evidence.

The control matters as much as the test: the deep-extract case was run against the pre-fix code path and raised `FileNotFoundError: [WinError 206] The filename or extension is too long`, so it is a regression test rather than a test that happens to pass.

#### 14c. A download worker pool trips SQLite

`download --family ems` with the default 4 workers: 5 of 6 succeeded and `10.4.3` failed with `InterfaceError: bad parameter or other API misuse`. Re-run alone, the same version downloaded cleanly. A SQLite error on a network stage, non-deterministic, and cured by serialising, is a connection crossing a thread boundary — the downloader's shared pool writing progress into `state.db`. It needs the connection made thread-local or the writes funnelled through one owner; which of the two is a reading of `state.py`, not a decision to take here.

This one is scoped to diagnosis in this phase: **reproduce it deliberately** (a wider pool over a family with more versions), then fix. A 1-in-6 silent failure on a stage that is about to run over ~1,500 versions for the first time is not something to leave until it shows up as a gap in the output.

**Reproduced, and it is neither of the two guesses.** The connection is already shared deliberately and `check_same_thread=False` makes that legal (`state.py:209`, written for Stage 3's pool). What was missing is narrower: **every write took the lock and no read took it at all.** Writes go through `_tx()`, which holds `self._lock`; the twenty-three read sites called `self.connect().execute(...)` directly, so one worker's `commit()` could land while another was mid-statement on the same connection.

Eight threads doing read → write → read, 400 rounds each, raised on 2–3 of every 3,200 rounds, on every one of three runs — and **one of those was an `IndexError: tuple index out of range`, not an `InterfaceError`**: a row coming back malformed rather than an exception. That is the half of the race worth the most, because it is the half that does not announce itself, and it is why the fix is a lock rather than a retry. Two helpers, `_one` and `_all`, take `self._lock` and **materialize inside it** — returning a live cursor would hand the caller a statement to step after the lock was dropped, which is the same bug with an extra step. Zero failures across four re-runs after the change.

#### 14d. The real package is shaped differently from the cached tree

The ZIP unpacks to `tibco-enterprise-message-service-10-5-1/{html,doc,pdf,…}` — one wrapper directory that `html-to-md/cache/pub/ems/10.5.1/` does not have. `roots.py` locates output roots by content and `apiref.py` decides by marker, so both should absorb an extra level; that is a claim to **check, not assume**, and it means the three versions already converted in this session came from a tree shaped unlike the one the pipeline will see from now on. They are re-extracted and re-converted as part of the acceptance below, and the output compared.

##### Acceptance

`docushift download --family ems` with the six hand-set `zip_url` values **reverted first**, so the derivation is what is under test rather than the override: 6 of 6 downloaded, each a real ZIP by magic number. Then `extract --family ems` on a checkout deep enough to reproduce 262 characters: 6 of 6 extracted, no `FileNotFoundError`, no `.part` left behind, and the deepest file present at its full name. Then `convert --family ems`: 6 of 6, and the three already converted from cache trees reconcile against their earlier output — a wrapper directory must not change the Markdown. `status --family ems` finally reads `Downloaded 6`, `Extracted 6`, `Converted 6`, the first time any family has.

For the URL change specifically: a `zip_source=manual` row keeps its stored URL untouched, an archived row keeps its `zipPath`, and an active row ignores the stale column. `ZIP_URL_UNRESOLVED` fires on `businessworks_integrationmanager_plugin@1.0` and not on anything that resolves. For the path change: a unit test that writes past 260 characters through `safe_unzip`, and the traversal-refusal tests unchanged and still passing — the prefix must not have opened a hole. For 14c: the pool reproduces the error before the fix and does not after. Then the full suite and `ruff`.

##### Met, 2026-09-19

The six `zip_url` values were reverted to the wrong template before the run, so every URL below was derived and none read.

| | |
|---|---|
| `download --family ems` | **6 of 6**, ~200 MB, every file a real ZIP; a second run reports 6 `Already current` |
| `extract --family ems --force` | **6 of 6**, 20,024 files, `flare` on all six, **no `.part` left behind** |
| `convert --family ems --force` | **6 of 6**, 8,613 topics, 8,847 files, **0 failures**, 38 findings and every one a note |
| `status --family ems` | Downloaded **6**, Extracted **6**, Converted **6** — 100% at every step, the first time any family has read that |

**14d is answered by arithmetic, not by inspection.** The three versions converted earlier in the session from the predecessor's wrapper-free cache trees produced 4,326 topics in 4,445 files. Re-converted from the real ZIP, with its `tibco-enterprise-message-service-10-5-1/` wrapper directory in the way, 10.5.0 + 10.4.1 + 10.4.0 produce 1,437 + 1,437 + 1,452 = **4,326 topics** in 1,476 + 1,475 + 1,494 = **4,445 files**. `roots.py` and `apiref.py` absorb the extra level exactly as claimed, and the claim is now a number rather than a reading.

**14d's scope, corrected 2026-09-19.** The arithmetic above is about *counts*, and it holds. It is not a statement that the wrapper is harmless: it was measured over Stage 5, which is the only stage that had run. Stage 7 had not, and the wrapper breaks two of its steps outright — see Phase 15.

The suite went 1,270 → **1,285** (+15, 2 skipped: the `\\?\` assertions are Windows-only and skip elsewhere), `ruff` clean. One test changed premise rather than being added: `test_a_version_with_no_url_is_a_report_line` asserted that blanking `zip_url` stops a download, which after the inversion means nothing — it is now two tests, one that a blank column no longer stops anything and one for the condition that genuinely remains, a version with no folder to build a path from. `tests/conftest.py`'s `project_root` copies the shipped `docsite.yaml` in for the same reason it already copied the AEM templates: a root without it now downloads nothing, which is a condition no installation is in.

---

### Phase 15: The Package Wrapper Is Not the Version Root — **Built, 2026-09-19**

Phase 14 got the `ems` family through download, extract and convert. `sync --family ems --target-dir C:\github\tibco-docs-aem` is the first Stage 7 run against a package this tool actually fetched, and it publishes **one doc-class of four**:

| doc-class | result |
|---|---|
| `online-help` | **6 of 6**, 8,849 files |
| `archives` | index written, 28 archived versions |
| `api-references` | **0 of 6**, every version failed |
| `user-guides`, `release-information`, `reference-documents` | **0 files**, over 30 shipped PDFs |

One cause under all three failures. A downloaded EMS package unpacks to a **single child directory** — `tibco-enterprise-message-service-10-4-0/`, the name the ZIP carries — with `doc/ html/ javadoc/ pdf/` inside *it*. Every hand-copied tree in this repo came from the predecessor's cache, which has no such level, so every step written against those trees assumes content sits at the version root.

#### 15a. Two Stage 7 steps read the version root directly

`sync/router.py:source_folders` returns `tree/pdf`, `tree/doc/pdf`, `tree/doc` and `tree/doc/doc`. Against a wrapped tree all four are absent, `route()` returns nothing, and the three document doc-classes publish an empty set without reporting anything — the run says `-` in the Documents column, which reads as "this version ships no PDFs" rather than "this version's PDFs were not found". 10.4.0 ships five.

`sync/apirefs.py:display_name` names a published API folder from the tree's path relative to the version root, dropping known container segments (`doc`, `html`, `api`, …). The wrapper is not a container, so it survives into the name:

```
tibco-enterprise-message-service-10-4-0/html/api/dotnetdoc/html
  -> tibco-enterprise-message-service-10-4-0-dotnetdoc      (48 chars)
  -> dotnetdoc, once the wrapper is the root                 (9 chars)
```

Those 39 characters are pure repetition — the slug and the version are already two segments up the published path. They are also what pushes the longest published file past the ceiling:

| | |
|---|---|
| longest published path, as named today | **267** |
| the same path while staged as `10-4-0.part` | **272** |
| Windows ceiling, `LongPathsEnabled = 0x0` | 260 |
| the same path with the wrapper as root | **228** |

**This is not §4.4's transient overflow, and must not be fixed with `\\?\`.** 267 is the *final* path — a published tree no reader outside this tool could open. Architecture §4.4 draws that line deliberately, and this is the first case to land on the far side of it. The fix is the name, which is wrong on its own terms; the length is the symptom that made it visible.

#### 15b. A content root, resolved once at extract time

**Not a strip during extraction.** Unpacking the child's contents into the version directory would make the tree match what every step assumes, with no consumer changes — but it rewrites the layout on disk, invalidates every recorded `extract_path`, and means the extracted tree no longer matches the package it came from. When an upstream ZIP and our copy of it disagree about structure, the next defect of this kind is unfalsifiable.

**Not a patch to the two callers**, either. The assumption is "content is at the version root", and it is written in more than two places; fixing the two that failed leaves the rest waiting for a package that reaches them.

So: `extract` resolves a **content root** per version and records it in `state.db`, and Stage 5/6/7 derive from it instead of from the version directory. The rule has to survive the corpus, and the corpus already contains the counter-example:

| shape | versions on disk | single child | the child |
|---|---|---|---|
| `ems` packages | 6 | yes | `tibco-enterprise-message-service-10-4-0` |
| `datasynapse` packages | 5 | yes | `doc` |
| `gridserver-manager/7.1.1` | 1 | no (5 children) | — |

**"One child" is therefore not the rule.** `doc/` is a single child too, and it is *content* — `source_folders` looks for `doc/pdf` and `doc/doc` by name. A rule that descended into it would break the five versions that work today. The rule is: descend through a single child **only when that child is not itself a known content segment**.

##### Measured, 2026-09-19: 60 versions across 24 families, read over HTTP Range

A ZIP's central directory is a few kilobytes at the end of the file, so the shape of a package can be read without downloading it. 60 eligible versions, one per product, spread across every family that had one; three requests and roughly 40 KB apiece instead of ~200 MB.

| | |
|---|---|
| endpoints that returned a ZIP | **50** |
| one wrapper directory, named exactly `{slug}-{version_dashed}` | **46** |
| flat — `doc/`, `html/`, `pdf/` at the root | 4 |
| a single child that *is* content | **0** |
| endpoints that returned no ZIP | 10 |

**The wrapper is the dominant shape, at 46 of 50**, and its name was the package stem in every one of the 46 — `tibco-iprocess-workspace-windows-11-10-0`, `spotfire-data-science-for-life-science-operations-2-2-0`. The 4 flat packages are the shape every step in this tool was written against.

The 10 failures are all the known `ZIP_URL_UNRESOLVED` class and **not a third shape**: 3 return a gzipped HTML error page of about 7 KB and 7 return the empty HTTP 200 of §2.2, with no `Content-Length` at all. Nothing in the sample is a package this tool cannot describe.

**The `doc/`-only counter-example does not come from a ZIP.** No package in the sample unpacks to a lone content directory; the five DataSynapse trees that do were hand-copied from the predecessor's cache, which stores `doc/` as the top level. They are still trees `extract`'s consumers read, so the content-segment exclusion stays — it is just not defending against a package shape, it is defending against the cache's.

**The name match is corroboration, not the rule.** Matching `{slug}-{version_dashed}` would be exact on all 46 and would refuse anything else, but the sample reached no archived package and none of the 10 products whose endpoint is unknown, so the shapes it has not seen are precisely the ones a stem test would reject. "A single child directory that is not a known content segment" accepts those and costs nothing when it is wrong: descending into a mis-identified directory finds no `doc/` or `pdf/`, which is what happens today anyway.

#### 15c. A failed publish leaves its staging tree behind, and says so illegibly

`_place` and `_place_api_references` call `remove(staging)` on the way *in*, not on the way out, so six `10-4-x.part/` trees with 6,146 files in them were left sitting in the published workspace. A `.part` directory is this tool's private vocabulary; in a target directory it does not own, it is litter that the next reader has no way to interpret.

The failure also arrives as `shutil.Error`'s full list — every failed `(src, dst, why)` triple, several kilobytes of it, printed raw — and the run **exits 0**, because the per-version catch turns it into a `FAILED` row and `sync`'s exit rule is about findings, not rows.

Three changes: stage cleanup in a `finally`, a one-line message with the count and the first offender, and a new register code.

#### 15d. `PUBLISHED_PATH_TOO_LONG`

The register's 43rd row, and `sync`'s first `error`. `sync` measures the destination path before it copies, skips the root that would overflow, and names it with the length and the path. A published path over the ceiling is not a warning: unlike `ZIP_URL_UNRESOLVED`, whose remedy is a hand-supplied file, there is nothing a user can do at run time and nothing downstream can read what was written.

The code stays after 15b removes its only known occurrence. The ceiling is a property of the target filesystem and the publishing root the user chooses — `C:\github\tibco-docs-aem` is 24 characters, and a deeper one puts other products over the line with no wrapper involved.

#### 15e. The ceiling is on the **read** side, and `rglob` hides it

15a–15d built and run, `sync --family ems --target-dir C:\github\tibco-docs-aem`:

| | before 15 | after 15a–15d |
|---|---|---|
| document doc-classes | 0 files | **8,886 files, 128.2 MB**, all four classes |
| `api-references` | 0 of 6, kilobytes of raw `shutil.Error` | 0 of 6, **one line apiece** |
| `.part` trees left behind | 6, 6,146 files | **none** |
| Stage 5 counts | 8,613 topics / 8,847 files | **unchanged** |

The wrapper diagnosis was right and the documents prove it. But `api-references` still fails 6 of 6, and the remaining cause is the mirror image of what 15a assumed:

```
C:\github\docushift-tool\families\en-us-tib-ems\extracted\...
  \tibco-enterprise-message-service-10-5-1\html\api\dotnetdoc\html
  \class_t_i_b_c_o_1_1_..._consumer_message-members.html      265 chars, the SOURCE
C:\github\tibco-docs-aem\...\api-references\10-5-1\dotnetdoc\html\...
  \class_t_i_b_c_o_1_1_..._consumer_message.html              190 chars, the DESTINATION
```

**`PUBLISHED_PATH_TOO_LONG` is silent because the published path is fine.** 190 of 260. What cannot be opened is the file this tool extracted: `safe_extract` wrote it through `long_path` (§4.4), and nothing on the read side lifts the prefix back. `copytree` gets the name from `scandir` and fails to open it — `[WinError 3] The system cannot find the path specified`, 3 files per version, 12 files over 260 across the six ems trees.

This is **not** the far side of §4.4's line. That line separates paths this tool *publishes* from paths it *owns*; 267 in 15a was a published path and a defect, 265 here is inside our own extracted workspace, and what it publishes to is 190. The prefix is the right instrument for exactly this.

**And `Path.rglob` omits the offending files without saying so.** For 10.5.1's `dotnetdoc`: 798 entries plain, **801 prefixed**. Three consequences, all measured:

- `over_limit` walks with `rglob`, so the check written in 15d cannot see the three files that then break the copy. It is not wrong about the ceiling; it is blind to the paths that reach it.
- `apirefs.measure` walks with `rglob`, so every root's `files`/`bytes` are 3 low.
- `apirefs.current` compares `measure(destination)` — short paths, full count — against that low source total, so a successfully published API tree would compare unequal and be re-copied on **every** run.

Second defect, independent of the ceiling. `sync` **exited 0** with six `FAILED` rows on screen. `validate` raises `Exit(1)` when it records an error; `sync` calls `findings.finish()` with no exit code and never raises. A batch driver reading the exit status of that run is told six failures were a success.

Two changes:

1. **Read the extracted tree through `long_path`** at the three places Stage 7 touches it: `_place_api_references`'s `copytree` source, `over_limit`'s walk, and `apirefs.measure`. The destination stays unprefixed — it is short by construction, and 15d's check is what keeps it so.
2. **`sync` exits 1** when any version failed or any error finding was recorded, the same rule `validate` uses.

##### Acceptance

##### Measured, 2026-09-19 — `sync --family ems --target-dir C:\github\tibco-docs-aem`

| criterion | result |
|---|---|
| all four doc-classes publish | **6 of 6** `api-references` (6,218 files, 115.6 MB), 6 of 6 each of `online-help`, `user-guides`, `release-information`, `reference-documents` |
| the 30 shipped PDFs routed, an index apiece | **30** — 18 `user-guides`, 6 `release-information`, 6 `reference-documents`; 6 `index.md` in each class |
| API folders named for the tree, not the wrapper | `dotnetdoc`, `javadoc` |
| no `.part` survives any run | none, after the successful runs **and** after the forced failure |
| a second `sync` re-copies nothing | **31 already current, 0 copied** — `measure` now counts the same files on both sides |
| a forced over-limit destination | a 70-character target root: **6 `PUBLISHED_PATH_TOO_LONG`**, one line apiece naming the file and **278**, 0 files written, exit **1** |
| Stage 5's counts unchanged | **8,613 topics in 8,847 files** |

The forced run is also 15e proving 15d: the file it names, at 278, is the 265-character source `rglob` could not see. The check and the copy now walk the same tree.

**`validate --target-dir` is not clean, and not because of Phase 15.** 8,658 files and 17,214 references walked: **1 `LINK_BROKEN`** and **1,763 `ANCHOR_MISSING`**, all of them in `online-help`, which Stage 7 published unchanged by this phase. The broken link is `users-guide/%s:%d`, a printf format string in the source text. Both are left for their own phase rather than folded in here; naming them is the point of the register. (Phase 16 measured both: the anchors are Stage 5's, and the broken link turned out to be the *validator's* — see 16c.)
- No `.part` directory survives any run, successful or failed.
- `validate --target-dir` reads the published tree clean.
- The API folders are named `dotnetdoc`, `javadoc` — not slug-and-version-prefixed.
- A forced over-limit destination produces one `PUBLISHED_PATH_TOO_LONG` line, a skipped root, a non-zero exit, and no residue.
- Stage 5's counts are unchanged: 8,613 topics in 8,847 files, which is the check that the content root resolved to the same tree the converter was already finding.

---

### Phase 16: The Converter Deletes the Targets Its Own Links Point At

`validate --target-dir` over the published `ems` tree walks 8,658 files and 17,214 references and reports **1 `LINK_BROKEN`** and **1,763 `ANCHOR_MISSING`**. Phase 15 left both on the table deliberately: they are Stage 5's, and folding a converter fix into a sync phase would have made neither measurable. This is that phase.

Phase 7b already predicted the shape of it — *"spot-checks say these are anchors the conversion genuinely dropped rather than slug-algorithm disagreement, which makes `ANCHOR_MISSING` the first measurement of a defect nobody had counted."* The spot-check is now a count.

#### 16a. Measured, 2026-09-19: 1,679 of 1,763 targets exist upstream and are deleted in conversion

Each finding's target file was resolved back through `output_map` to the HTML it was converted from, and the fragment looked up in that source:

| | |
|---|---|
| `ANCHOR_MISSING`, run 52 | **1,763** |
| target present in the source as `<a name=>` | **1,679** (95.2%) |
| target present as `id=` only | **0** |
| target genuinely absent upstream | 84 (4.8%) |

Where the surviving 1,679 sit in the source DOM — which is the same question as *which converter branch drops them*:

| location | findings |
|---|---|
| inside a `<table>` | **1,092** |
| inside an `<h1>`–`<h6>` | **424** |
| in ordinary prose | 163 |

Two lines of `transforms/markdown.py` account for all three. In `rewrite()`, the raw-HTML table path:

```python
for anchor in tag.find_all("a"):
    url = self.link(anchor)
    if url:
        anchor["href"] = url
    else:
        anchor.unwrap()          # <a name="ID-2FC4B4A1"></a> ceases to exist
```

and in `_anchor()`, the inline path every heading and paragraph goes through:

```python
url = self.link(tag)
if not url:
    return text                  # "" for an empty anchor: the target is gone
```

Neither is a mistake about links. Both are correct about links and silent about *targets*: an `<a>` with no `href` is not a broken link, it is a destination, and every `<a href="#ID-2FC4B4A1">` elsewhere in the corpus survives the conversion pointing at nothing. The validator has been reporting the consequence since Phase 7b without anyone reading it as a cause.

**This is not an `ems` quirk.** A 1,500-file sample per tree:

| tree | HTML files sampled | `<a name=>` targets | files carrying one |
|---|---|---|---|
| `ems` (downloaded, Flare) | 1,500 | 209 | 60 |
| `datasynapse` (cache, mixed) | 1,500 | **2,437** | **1,333** |
| predecessor `cache/pub` | 1,500 | **2,564** | **1,401** |

The pattern is *denser* outside `ems`. Every product converted so far has been losing these.

#### 16b. The fix emits the target, as HTML5 spells it

`validation/references.py:_HTML_ANCHOR` accepts `id=` **and** `name=`, so either spelling would satisfy the check. The output should be `id=`: HTML5 dropped `name` on `<a>`, AEM's renderer will not resolve it, and the findings register describes `ANCHOR_MISSING` as *"a `#fragment` naming no heading and no `id=` in the file it resolves to"*. Satisfying the validator with the attribute the validator tolerates rather than the one it documents would be a fix aimed at the test.

So a href-less `<a name="X">` — or `<a id="X">` — becomes `<a id="X"></a>`, kept next to the text it labelled, in both branches:

- **`rewrite()`**: keep the tag rather than unwrapping it; rename `name` to `id`; unwrap only when there is neither.
- **`_anchor()`**: return the marker ahead of whatever the tag would otherwise have produced — the bare marker when the tag is empty, `marker + text` when it has text and no href, `marker + [text](url)` in the rare case it carries both a target and a link.

**Headings need a third move.** 424 of the targets sit inside an `<h2>`, and `_block`'s heading branch builds the line from `inline_children`. Letting the marker through there would emit `## <a id="X"></a>Configuring Users`, and the validator computes heading slugs with `slugify_heading` over the raw title — so every *existing* `#configuring-users` fragment in the corpus would break in the act of fixing 424 others. The heading branch therefore lifts leading markers out into their own block:

```markdown
<a id="ID-2FC4B4A1"></a>

## Configuring Users
```

Both anchors then resolve, and the slug is untouched.

**Bounded output growth.** Counted over exactly the 8,613 HTML files Stage 5 converts, not the whole tree: **1,218 href-less anchors in 350 files**, all of them `name=`. Fewer than one marker per seven output files, and none in the 8,263 files that carry no target today.

`_code_fragment` is left alone: an anchor inside a code span cannot be a link destination in any renderer, and the branch already drops the `<a>` there for the same reason.

#### 16c. The broken link is the validator's, not the converter's

`error-and-status-mes.md:791` is a row of a Flare table too irregular for GFM, so Stage 5 emits it as passthrough HTML, verbatim:

```html
<p>Pulsar: [%s](%s:%d): %s</p>
```

The converter did not manufacture a link — that text is in the source HTML character for character, a printf format string in an error-message table. **CommonMark does not parse inline Markdown inside an HTML block**, so `[%s](%s:%d)` is text and `users-guide/%s:%d` is not a reference. `references()` reports it because `_MD_INLINE` runs over the whole file with only code masked. This is a false positive, and Phase 15's note calling it a converter defect was wrong.

The fix is a `mask_html_blocks` beside the existing `mask_code`, applied to the three *Markdown* extractors and **not** to `_HTML_REF` or `_HTML_ANCHOR` — links and targets written as HTML inside those blocks are real and must keep being checked. Block detection follows CommonMark: the type-6 tag list (which deliberately excludes `a`, `b`, `span`, `img`, so an inline tag at the start of a line suspends nothing) plus type 7, a complete tag alone on its line; ends at a blank line.

**Blast radius, measured over the published tree**: of 15,112 Markdown-syntax references in 8,657 files, masking removes **exactly 1** — the `%s:%d`. Nothing else in the corpus relies on Markdown being parsed where CommonMark says it is not.

#### 16d. Four more places a target is discarded, found by running it

16b's two branches took 1,763 down to **184**, not to 84. The remaining 100 were all the same mistake in four more rewrites, and each one was found the same way — re-resolve what is left, look at where it sits, fix, run again. **A destination is not a link, and every rewrite that carries text across has to be told so separately.**

| the rewrite | what it did | recovered |
|---|---|---|
| `markdown.code_span` | rendered the span from its *text*; Flare writes `<code><a name="tibemsd_Service_Parameters"></a>tibemsd </code>` | 34 |
| `flare._heading_paragraph` | rebuilt a split table's short label from `_text(cell)`, which has no children | *(in the 34 above)* |
| `markdown.table` | `tables.read` sees rows and cells; Flare's table-level target sits between `<col>` and `<thead>`, in neither | 42 |
| `flare._split_colspan_tables` / `_fake_list_tables` | moved the rows into a new element and decomposed the old table, destroying anything that was not a row | 18 |
| `transforms/links.classify` | **the validator's side**: a same-page `#foo` was the one branch that did not percent-decode the fragment | 6 |

The first four take the same remedy as the heading: hoist the target out in front of the construct, because it cannot be a destination inside one. The fifth is different and worth naming — `classify` decodes the fragment on the `RELATIVE` path and left it raw on the `FRAGMENT` path, so `%0A%20%20%20` was compared against a literal newline and three spaces. One corpus anchor has a whole pasted table in its `name`, which is the only reason anything exercised it. The asymmetry was also double-encoding those fragments on the way out, via `links.emit`.

#### Acceptance — measured, 2026-09-19

`convert --family ems --force`, `sync --family ems`, `validate --target-dir`:

| | |
|---|---|
| `LINK_BROKEN` | **0** (was 1) |
| `ANCHOR_MISSING` | **84** (was 1,763) |
| fragments resolving | **1,703 of 1,787** (was 1,603) |
| exit code | **0** |
| the 84 survivors | re-resolved through `output_map`: **84 of 84 absent from the source**, 0 present-and-dropped |
| output tree | **8,847 files**, unchanged — this phase adds anchors inside files, not files |
| suite | **1,327 pass** (+12), lint clean |

New unit tests, one per site: a target in a passthrough table survives as `id=`; one in prose emits the marker; one in a heading is hoisted above it and the slug is unaffected; one in a code span is hoisted in front of it; a table's own target survives both the pipe-table conversion and the two Flare table rewrites; a split label keeps the target its rebuild dropped; an `<a>` with neither `href` nor a target is still unwrapped; a same-page fragment is decoded; `references()` finds no Markdown link inside an HTML block and still finds the `<a href=>` in one.

---

### Phase 17: WebWorks Rewrites Its Links in the Coordinate System It Does Not Publish In — **Built, 2026-09-22**

The `tra` family is the second to go end to end and the **first non-Flare family to reach `validate`**. `download` 15/15, `extract` 15/15, `convert` 15/15 with 0 failures, `sync` 62 rows and 0 failed, idempotent on a third run. Then `validate --target-dir` over the published tree reports **3,862 `LINK_BROKEN`** and exits 1.

The split is exactly the engine line, which is the whole finding:

| product | versions | engine | `LINK_BROKEN` | `ANCHOR_MISSING` |
|---|---|---|---|---|
| `tibco-runtime-agent` | 5.12.2 / 5.12.3 / 5.12.4 | WebWorks | 2,398 | 267 |
| `tibco-administrator-enterprise-edition` | 5.12.2 / 5.12.4 | WebWorks | 996 | 49 |
| `tibco-designer-add-in-for-tibco-business-studio` | 1.0.0 – 1.5.0 (8) | WebWorks | 468 | 0 |
| both `5.13.0` | 2 | **Flare** | **0** | **0** |

**All 13 WebWorks versions fail. Both Flare versions are clean.** Phases 8, 14, 15 and 16 all measured on `ems`, which is Flare, and Phase 5d proved WebWorks against the *converted* tree — where the links are internally consistent and nothing was wrong. No WebWorks version had ever been walked by `validate` in its published form.

#### 17a. Two coordinate systems meet in one `relpath` call

`engines/webworks.py` builds a topic index once in `_scan`, and resolves every link through it in `_topic`:

```python
# _scan, line 1025 -- value is the TREE-relative source path, suffix-swapped
index.topics[source.lower()] = links.to_markdown(PurePosixPath(source))

# _render, line 1194-1201 -- self.output is the UNIT-relative OUTPUT path
output = PurePosixPath(_join(unit.name, relative))

# _topic, line 411
return links.emit(links.relative_to(self.output, target), fragment)
```

`relative_to` is handed a **source in output coordinates and a target in source coordinates**. The key is right — tree-relative is the correct lookup coordinate, and the docstring defends it. Only the *value* is in the wrong space.

For Flare the two spaces coincide: `architecture.md` §5.1.2 keeps the output tree mirroring the source precisely *so that* link rewriting is a suffix substitution. WebWorks publishes per unit, and `subtree_name` drops the book root — so the spaces differ by exactly the segment between the version root and the book, which is what appears in every broken link. The two published layouts both show it:

| book | `unit.name` | emitted | on disk |
|---|---|---|---|
| `…-5-12-2/designerhelp/tib_Designer_palettes` | `""` | `tibco-runtime-agent-5-12-2/designerhelp/tib_Designer_palettes/palette.4.03.md` | `palette.4.03.md` |
| `…-5-12-4/trahelp/tib_TRA_upgrade` | `tib_TRA_upgrade` | `../tibco-runtime-agent-5-12-4/trahelp/tib_TRA_upgrade/migrate.2.5.md` | `tib_TRA_upgrade/migrate.2.5.md` |

The second is the arithmetic proof: the leading `../` is `relpath` climbing out of a one-segment output directory before descending the source path. A flat book gets no `../` because its output parent is already `.`.

`subtree_name`'s own docstring named this failure mode before it happened — *"Two of them would be two answers, and two answers here put a topic's pages and that topic's images in different subtrees — every image on the version 404s and nothing reports it, because each half is internally consistent."* That is this defect, one field over: pages and *links to* pages rather than pages and images.

**The target identity was never wrong.** Every broken link names the right file and the right `#fragment`; only the prefix is in the wrong space. Re-resolving all 3,862 through `output_map` and testing the published tree on disk:

| | |
|---|---|
| `LINK_BROKEN` reported | **3,862** |
| parsed back out of the report | 3,859 (3 lost to console line-wrapping, see 17c) |
| target found in `output_map` and **present on disk** | **3,856 (99.9%)** |
| no `output_map` row — genuinely dangling | 3 |

So this is a rebase, not a repair: the fix is expected to take 3,862 to **3**, and those 3 should be re-checked upstream rather than assumed.

#### 17b. The fix puts the index in output coordinates

One line, at the one place the value is written. `_scan` already takes `context`, and `subtree_name` is a pure function of the book root, so the unit name is available there:

```python
for relative in book.topics:
    source = _join(book.name, relative)
    index.topics[source.lower()] = links.to_markdown(
        PurePosixPath(_join(context.subtree_name(book.root), relative))
    )
```

The key stays tree-relative — `_topic`'s docstring is right that a cross-book popup and a `../other_book/x.htm` must arrive at the same table through the same coordinate. `index.topics` is read at **exactly one site** (line 401), so the value's space is not load-bearing anywhere else; `index.anchors` and `index.referenced` are keyed on the same tree-relative string and are untouched.

**The other three engines need checking, not assuming.** Flare is proven correct by `ems` and by both `5.13.0` versions here. DITA and DocBook also publish flat or per-unit and have never been through `validate` either; each builds its own map and may or may not have the same mismatch. That check is part of this phase — a `validate` run over one published DITA version and one DocBook version — and whatever it finds is reported before any second fix is written.

#### 17c. A finding rewrites itself on the way to the terminal

`validate` **crashed** on this run with `UnicodeEncodeError: 'charmap' codec can't encode character '\U0001f4af'` — after the whole validation had completed, in the reporting loop at `cli.py:1649`. There is no 💯 anywhere in the corpus. The finding was:

```
palette.4.24.md:100: tibco-runtime-agent-5-12-2/designerhelp/…
```

`console.print` is given an **f-string with the path and message interpolated into rich markup**, and rich's emoji substitution is on by default: `:100:` is the shortcode for 💯. The finding is on line 100, so `.md:100:` became `.md💯`.

The crash is the lesser half. On a UTF-8 terminal there is **no error at all** — the line number is silently replaced by an emoji and the finding still prints, looking fine. The cp1252 console is the only reason anyone found out. The same interpolation also passes `[` through as markup, so a path containing brackets is eaten rather than printed.

Three sites share the pattern — `cli.py:1649` (`validate`), `cli.py:1980` (`report`) and `cli.py:2252` (`csh`) — and no site in the tool currently sets `emoji=False`, `markup=False` or `highlight=False`. The fix is to render untrusted text as data rather than as markup at all three: keep the colour on the literal parts, pass the path and message through `rich.markup.escape` with emoji off. A finding is machine output and must survive the terminal byte for byte.

This is filed here rather than as its own phase because 17a is the reason it was discovered, but it is independent of the link fix and lands first — otherwise the acceptance run for 17b cannot be read.

#### Acceptance

1. `convert --family tra --force`, `sync --family tra --force`, `validate --target-dir` over all 15 versions.
2. `LINK_BROKEN` **3,862 → 3**, and each of the 3 named with the upstream file it wants.
3. Both Flare versions stay at **0** — the fix must not move a coordinate that was already correct.
4. Output file count unchanged at **4,685**: this phase rewrites link text inside files, it does not add or remove any.
5. `ems` re-validated unchanged at `LINK_BROKEN` 0 — Flare's path goes through the same `relative_to`.
6. The 316 `ANCHOR_MISSING` are re-resolved through `output_map` the way Phase 16a did, and classified present-upstream vs absent-upstream **before** any decision to fix them. WebWorks' `_anchor` already emits `<a id=>` for wanted targets (line 335), so the Phase 16 remedy may or may not apply here; the count is not assumed to be the same defect.
7. A finding on line 100 prints as `:100:`, and one whose path contains `[` prints its brackets — tested through a cp1252-backed stream so the regression cannot pass only on a UTF-8 terminal.

Unit tests: a WebWorks link between two topics in the same flattened book emits a bare sibling; one from a nested unit to a topic in that same unit emits a bare sibling; one across two units emits `../other/x.md`; a cross-book `WWHClickedPopup` resolves through the same table and lands in output coordinates; the index key stays tree-relative so a `../other_book/x.htm` and a popup naming that book resolve to one entry.

#### Result

| | before | after |
|---|---|---|
| `LINK_BROKEN`, 13 WebWorks versions | 3,862 | **0** |
| `ANCHOR_MISSING`, 13 WebWorks versions | 316 | **0** |
| `LINK_BROKEN` / `ANCHOR_MISSING`, both Flare `5.13.0` | 0 / 1 | 0 / 1 |
| `ems` (6 Flare versions) `LINK_BROKEN` / `ANCHOR_MISSING` | 0 / 84 | 0 / 84 |
| output tree, `tra` | 4,685 files | **4,685 files**, unchanged |
| `validate --target-dir` over all 93 folders | exit 1 | **exit 0**, 85 warnings, 0 errors |
| suite | 1,327 pass | **1,334 pass** (+7), lint clean |

`LINK_BROKEN` went to **0**, not the predicted 3: the three that had no `output_map` row were the three the console wrapped mid-path in 17c's report, so they were never dangling — they were unreadable. The measurement was right about 3,856 and wrong about why the other 3 were missing, which is the reporting bug proving itself a second time.

`ANCHOR_MISSING` 316 → 0 was **not predicted**. Acceptance criterion 6 assumed a separate defect; it was the same one. The 85 warnings that remain are all Flare — 84 on `ems` (unchanged for five phases) and 1 on `tibco-administrator-enterprise-edition` 5.13.0 — and none of them are WebWorks.

**17b shipped differently than planned.** Putting `subtree_name` inside `_scan` does not work: `_scan` runs inside `units()`, *before* the driver calls `subtree_names`, so `context.subtrees` is still empty and `subtree_name` falls back to the full tree-relative path — the original bug, restored. The transform had to move to lookup time instead. `_Index.topics` now stores `(book.root, relative)` — deliberately not a finished path — and `_topic` completes it with `context.subtree_name(root)` once the driver has populated `context.subtrees`. A unit test caught this; nothing about it was visible from reading the code.

**A second instance of the same confusion was hiding one field over.** `renderer.key` was built in output coordinates while `index.anchors` and `index.referenced` are keyed tree-relative, so `wanted` came back empty for every book that did not take the version root and `<a id=>` was silently never written for any of them. That is the 316 `ANCHOR_MISSING`. `_convert` now derives `within = _join(book.name, relative)` and uses it for both `key` and `base`, keeping them in the index's coordinate while `output` stays in the publishing one. The `WebWorksRenderer.__init__` comments had the two spaces written the wrong way round, and `Unit`'s docstring in `engines/base.py` said `name` is "the unit's path relative to the extracted tree" — which is the misconception itself, in the definition. Both corrected.

**The test harness was the reason this survived Phase 5d.** `run()` in `test_webworks.py` named each unit by its full tree-relative path instead of going through `subtree_names`, so `unit.name == book.name` in every test and the two coordinate systems were identical in the fixture. The harness now calls `subtree_names` exactly as the driver does; three tests that asserted book identity through `unit.name` were retargeted at a new `Run.roots()`, and one test expecting `../reference/ref.md#p9` was updated — that expectation *was* the bug, written down and locked in.

**DITA and DocBook were checked statically, not measured.** No DITA or DocBook version is converted yet, so there is no published tree for `validate` to walk and that half of the plan is blocked rather than done. Reading the code: `dita.py:286` and `docbook.py:287` both pass `self.output` and `target.output`, two fields written in the same unit-relative space (`dita.py:957`, `docbook.py:475`), and `flare.py:314` does the same. WebWorks was the only engine whose index spans several books under one unit, which is the only place the two spaces can diverge. This stays open until a DITA and a DocBook family reach `validate`.

---

### Phase 18: A Parent Product Publishes No Versions of Its Own — **Planned, 2026-09-22**

The `streaming` family ran `download` 20/24, `extract` 20/20, and then `convert` **converted 2 of 24**: 4 `NO_TREE`, 18 `ENGINE_UNKNOWN`, 0 failed. Seventeen of the eighteen are the correct outcome and not a defect — those trees hold no HTML at all. `tibco-enterprise-streaming@11.2.1` is four files: a readme, a ReminderNotice, an RTU, and a licence PDF.

That is not a broken package. It is the wrong product.

| | `tibco-enterprise-streaming` | `tibco-streaming` |
|---|---|---|
| docsite id | 9042 | 4943 |
| `product_code` | `platform-tp-stream` | `str` |
| API shape | `isChildProduct: true` | `isParentProduct: true` |
| versions | 4 | **22** |
| package | readme + licence, 0.2 MB | the help |
| in `config/products.csv` | yes | **no** |

`tibco-enterprise-streaming` is a **licence bundle**. Its own API `description` says so: *"Click on the links below to access Documentation for the included Suite Components."* The catalog has the bundle and has never had the product.

#### 18a. The crawler drops every parent product, silently

`/api/products/{slug}` returns two shapes, and `discovery/crawler.py` handles one. The module docstring (`crawler.py:14-17`) describes the child shape correctly — the detail object *is* the current version, carrying `version_no` and `folder_path`, with the rest in `siblings`. A **parent** returns neither:

```
spotfire-application               parent=False child=True  ver='15.0.0'  folder='sfire-analyst/15.0.0'  siblings=True
tibco-streaming                    parent=True  child=None  ver=None      folder=''                      siblings=absent
tibco-flogo                        parent=True  child=None  ver=None      folder=''                      siblings=absent
tibco-activematrix-businessworks   parent=True  child=None  ver=None      folder=''                      siblings=absent
ibi-webfocus-client                parent=True  child=None  ver=None      folder=''                      siblings=absent
```

So at `crawler.py:236-239` the `_first(r, _VERSION_KEYS)` filter empties `records`, `_build_product` returns `None`, and the product is gone. `a_to_z` advertises `versionCount: 22` for `tibco-streaming` and the catalog ends up with nothing.

*(Corrected 2026-09-22: an earlier draft of this paragraph said "no error, no count, no line in the report". The count exists — `discover()` does `result.unversioned += 1` at `crawler.py:152`, and `cli.py:238-241` prints "Skipped N entries with no published versions and M that are not publicly visible." The defect is not silence, it is **misattribution**. `unversioned` is documented as the licence-page and connector-stub bucket, so a product with 22 published versions lands in a tally whose name says it has none, next to entries for which that is true. Nothing cross-checks the bucket against the `versionCount` `a_to_z` already returned for every slug in it, which is why a 22-version product could sit in a printed number for twelve days without anyone reading it as a fault. Item 3 of 18d is unchanged by this correction — it is about naming and cross-checking the drop, not about creating a counter that already exists.)*

The versions are one slug away. `/api/products/tibco-streaming-11-2-1` returns `version_no: '11.2.1'`, `folder_path: 'str/11.2.1'`, and **21 siblings** — 22 total, matching `versionCount` exactly. Fed to the existing `active_template` that yields:

```
/pub/{folder_path}/{slug}-{version_dashed}_documentation.zip
  -> https://docs.tibco.com/pub/str/11.2.1/tibco-streaming-11-2-1_documentation.zip
```

**The template is not wrong and `docsite.yaml` does not change.** Discovery never got far enough to use it.

#### 18b. Blast radius: 35 products, 707 versions

Live `a_to_z` against `config/products.csv`: 738 entries, 636 catalog rows. 69 of the missing carry `isPublicLevel: false` and are dropped on purpose (`crawler.py:170-172`). That leaves **35 public, versioned products absent from the catalog, carrying 707 versions**:

| versions | slug | | versions | slug |
|---:|---|---|---:|---|
| 99 | `spotfire-application` | | 16 | `tibco-bpm-enterprise` |
| 49 | `tibco-flogo` | | 14 | `tibco-product-and-service-catalog` |
| 47 | `tibco-activespaces-enterprise-edition` | | 14 | `tibco-mdm` |
| 45 | `tibco-activematrix-businessworks` | | 14 | `tibco-foresight-studio` |
| 39 | `ibi-webfocus-reporting-server` | | 11 | `spotfire-statistica` |
| 39 | `ibi-webfocus-client` | | 10 | `tibco-businessconnect-container-edition` |
| 38 | `ibi-webfocus-app-studio` | | 9 | `tibco-activematrix-service-grid` |
| 36 | `ibi-webfocus-installer` | | 8 | `tibco-foresight-hipaa-validator-desktop` |
| 32 | `tibco-businessevents-enterprise-edition` | | 8 | `ibi-iway-service-manager` |
| 26 | `tibco-data-virtualization` | | 7 | `tibco-messaging-enterprise-edition` |
| 26 | `ibi-focus` | | 5 | `ibi-omni-gen-mdm` |
| 25 | `tibco-operational-intelligence-hawk-redtail` | | 5 | `ibi-omni-gen` |
| 22 | `tibco-streaming` | | 4 | `ibi-omni-healthdata` |
| 18 | `tibco-businessconnect` | | 3 | `tibco-offer-and-price-engine` |
| 16 | `tibco-order-management` | | 2 | `tibco-activematrix-service-grid-container-edition` |
| 16 | `tibco-foresight-instream` | | 1 | 4 more |

*(Written when the parent-product mechanism was verified on 4 of the 35 and `spotfire-application` was an unexplained second cause. Both are resolved in 18d below: 34 of the 35 are parent products and the 35th is a distinct dedup defect. The table stands as the measured gap.)*

#### 18c. Interim: pin `tibco-streaming` by hand — **Built, 2026-09-22**

The catalog is CSV so that this is possible (`architecture.md` §3.1). Adding the product does not wait on 18d.

One row in `config/products.csv`:

```
tibco-streaming,str,TIBCO® Streaming,tibco,streaming,manual,true,default,true
```

Six rows in `config/versions.csv` — every **active** version, each with the `active_template` URL written out. *(Planned as `zip_source=manual`; shipped as `auto` — see the correction below.)*

| version | `folder_path` | release |
|---|---|---|
| 11.2.1 | `str/11.2.1` | 2025-10-23 |
| 11.2.0 | `str/11.2.0` | 2025-06-13 |
| 11.1.3 | `str/11.1.3` | 2026-03-25 |
| 11.1.2 | `str/11.1.2` | 2025-11-20 |
| 11.1.1 | `str/11.1.1` | 2024-10-04 |
| 11.1.0 | `str/11.1.0` | 2023-11-16 |

The other 16 (11.0.1 down to 10.4.0) are archived, so `convert_eligible=false` by the 2026-09-02 archive policy, and their real `zipPath` comes from `/api/products/archive/tibco-streaming` rather than from a template — the last seven carry the stale `folder_path: 'str'` the crawler docstring warns about. **They are deferred to 18d**, where the archive index is read the way it is read for every other product.

Durability is the point of the exercise, and two mechanisms carry it:

* `custom_override=true` on the product row is a **whole-row pin** — `_merge_product` returns before reading a single upstream field (`catalog.py:629-631`). A `catalog fetch` that still cannot see this product cannot damage it.
* `family_source=manual` pins the family, per the provenance table in the `propagate-catalog-edit` skill. `family` needs it most: it resolves by provenance **rank**, not by snapshot diff, so a `taxonomy_rule` value would survive only as long as `state.db` holds a snapshot. ~~`zip_source=manual`~~ — wrong, and corrected below.

`catalog fetch` does not delete versions discovery stops returning unless `--allow-deletes` is passed, so the rows are safe from an ordinary fetch even before the pin.

Then `download` → `extract` → `convert` over `--product tibco-streaming`. The engine is whatever the detector says; `tibco-streaming` is the StreamBase documentation set and no prediction is recorded here.

##### 18c shipped with two corrections to the plan above, both about `zip_source`

**`zip_source=manual` does not mean "a human set the URL". It means "a human places the package; never fetch this row."** `download_one` returns `SKIPPED_MANUAL` before it resolves anything (`fetcher.py:214-215`), ahead of `--force`. Writing the six rows as `manual` — which the plan did, following the provenance table in the `propagate-catalog-edit` skill — would have made all six undownloadable. `catalog import` said so immediately, twice per row. The rows were corrected to `zip_source=auto` via `catalog set`.

**And the `zip_url` column is not read for an active row at all.** `_resolve_url` derives the endpoint from `_folder_path` + `active_zip_url` and trusts the stored column only when the row is archived or manually pinned (`fetcher.py:150-171`) — a deliberate choice from 2026-09-19, when discovery's template was wrong for the whole corpus. So the six URLs written into the CSV are documentation, not mechanism. What actually makes the download work is `product_code=str`: `_folder_path` falls back to `f"{code}/{version}"` → `str/11.2.1`, which is the correct folder, so the derivation lands on the right URL with no `state.db` metadata to seed it.

The durable pin is therefore `custom_override=true` alone, on the product row and on all six version rows. That is the mechanism the skill's table does not cover, and it is the one that matters here.

##### The `spotfire-` era is real, and it explains the four `sb-hp-fix` failures too

`download` fetched 4 of 6 — 11.2.1, 11.2.0, 11.1.3, 11.1.2, 400.6 MiB. **11.1.1 and 11.1.0 failed** with the same empty-200 as the `sb-hp-fix` rows. The predecessor's manifest records their doc URLs as `docs.tibco.com/products/spotfire-streaming-11-1-1` — a rebrand window — and a ranged probe settles it:

| URL | status | first 4 bytes |
|---|---|---|
| `/pub/str/11.1.1/tibco-streaming-11-1-1_documentation.zip` | 200 | *empty body* |
| `/pub/str/11.1.1/spotfire-streaming-11-1-1_documentation.zip` | **206** | **`PK\x03\x04`** |

Same for 11.1.0. The `finalSlug` in the filename is the display name **as it was at that release**, not as it is now — so `active_template` is correct in form and wrong in input for every product that was rebranded mid-life. Both packages were fetched by hand and filed with `download --from-file`, which pins `zip_source=manual` for exactly the reason that flag exists. Their extracted wrappers are named `spotfire-streaming-11-1-1/`, which is the rebrand visible on disk.

This is the cause of 18d's item 4 as well, now confirmed rather than suspected: the four `tibco-streambase-high-performance-fix-engine` failures are the same window and will need the same stem.

##### Acceptance

`download` 4/6 fetched + 2 filed by hand, `extract` **6/6, all six detected `docbook`**, `convert` **6/6 with 0 failed, 0 `ENGINE_UNKNOWN`, 0 `NO_TREE`** — 7,071 topics, 8,178 assets, 15,261 output files.

| version | topics | nav nodes | out files | resolved | dangling | orphan |
|---|---:|---:|---:|---:|---:|---:|
| 11.2.1 | 1,196 | 3,384 | 2,566 | 2,118 | 0 | 1,272 (40.3 MB) |
| 11.2.0 | 1,191 | 3,362 | 2,534 | 2,118 | 0 | 1,272 (40.3 MB) |
| 11.1.3 | 1,187 | 3,341 | 2,555 | 2,127 | 1 | 1,155 (33.4 MB) |
| 11.1.2 | 1,182 | 3,319 | 2,550 | 2,127 | 1 | 1,155 (33.4 MB) |
| 11.1.1 | 1,179 | 3,301 | 2,547 | 2,125 | 1 | 1,155 (33.5 MB) |
| 11.1.0 | 1,171 | 3,268 | 2,537 | 2,119 | 0 | 1,153 (33.5 MB) |

0 skin, 0 escaped, 0 case-mismatch throughout. Findings: **3 errors, 30 notes** — the three errors are one `REFERENCE_UNRESOLVED` apiece in 11.1.3, 11.1.2 and 11.1.1, the same single dangling reference `spotfire-data-streams@11.1.1` carries. Each version skips ~850–1,010 `foreign-generator` and ~1,477 `not-docbook` files, and the orphan block is the `html/apidocs/` Javadoc tree the extractor flags as having no known generator marker (2,530–2,829 files per version).

**`validate` has not been run against this family** — `sync` has not been run either, so there is no published tree to walk. The conversion is measured; the publication is not.

**What 18c does not do.** It does not touch the bundle rows. `tibco-enterprise-streaming` and `tibco-enterprise-streaming-high-performance-fix-engine` stay `convert_eligible=true` and will keep reporting `ENGINE_UNKNOWN` on every run, because turning them off is a policy question about how the catalog should represent a licence bundle that publishes a licence — and answering it for two rows in the `streaming` family, when 18b says there are more bundles behind the other 34 products, would be setting precedent from the smallest possible sample.

#### 18d. The crawler fix — **Built, 2026-09-23**

18d's blocking question was *"how is the child slug obtained?"* — `a_to_z` gives a `versionCount` but no version list, and a parent detail gives no children, so `{slug}-{version_dashed}` needed a version nobody had. **Mayur supplied the answer: append `-latest`.** `/api/products/{slug}-latest` returns the ordinary child shape, and its `siblings` array is the version drop-down.

##### The `-latest` fallback resolves the whole parent-product class

Probed against every one of the 35 missing products:

| | |
|---|---|
| `-latest` returns a child shape | **34 of 34 parent products** |
| sibling count matches `a_to_z` `versionCount` | **34 of 34, exactly** |
| versions recovered | **685** |

```
tibco-streaming-latest                   11.2.1   str/11.2.1                      21 siblings  (22 = versionCount)
tibco-flogo-latest                        3.0.0   flogo/3.0.0                     48 siblings  (49)
tibco-activematrix-businessworks-latest   6.13.0  activematrix_businessworks/6.13.0  44 siblings  (45)
ibi-webfocus-client-latest                9.3.8   wf-wf/9.3.8                     38 siblings  (39)
```

The exact match on all 34 is the load-bearing result: it says `-latest`'s siblings are the *complete* version set, not a recent window, so the fallback needs no pagination and no second call.

Two cautions the probe turned up. **`-latest` is a slug suffix, not a URL suffix** — the user's list is of `/products/...` page paths, and `/products/tibco-webfocus-client` is a page whose API slug is `ibi-webfocus-client`; `tibco-webfocus-client-latest` errors. The fallback must be driven by the slug `a_to_z` returns, never by a hand-kept list. And the user counted ~20 custom pages; `a_to_z` says **34**. The list is a sample, so the fallback is applied to every parent, not to an allow-list.

##### `spotfire-application` is a different defect: first-wins dedup lets a non-public twin shadow a public product

The 35th product is not a parent — `/api/products/spotfire-application` returns a perfectly good child shape with 98 siblings. It never gets requested. `a_to_z` returns **two records under that one slug**:

| id | `isPublicLevel` | `isOnlyForAdmin` | `versionCount` |
|---|---|---|---:|
| 8862 | `False` | `True` | 1 |
| 2452 | `True` | `False` | **99** |

and `_list_products` (`crawler.py:178-186`) dedups **first-wins**, adding the slug to `seen` *before* it applies the visibility filter:

```python
if not slug or slug in seen:
    continue
seen.add(slug)                      # the admin stub claims the slug here
public = _present(record, _PUBLIC_KEYS)
if public is not None and not record[public]:
    result.non_public += 1          # ...and is then dropped as non-public
    continue
```

The admin-only stub arrives first, consumes the slug, and is discarded. The real 99-version product is then skipped as a duplicate. `discover(selectors=['spotfire-application'])` returns `products: 0, unversioned: 0, non_public: 70` — it never reaches `_build_product` at all, which is why 18b could not explain it as a parent.

This is **the only duplicated slug in `a_to_z`** (739 records, 738 distinct slugs), so the fix reaches exactly one product.

##### …and those 99 versions are out of scope, which is the actual finding

`spotfire-application` is `folder_path: 'sfire-analyst/15.0.0'` — **Spotfire Analyst itself**, the core client, beside `spotfire`, `spotfire-desktop` and `spotfire-server`, all three of which `config/scope.yaml` already excludes. Not one of its 99 versions would ever be converted. *(An earlier draft of this phase counted them as recovered yield. They are not yield.)*

The defect is therefore not the missing versions. It is that **`config/scope.yaml` does not exclude it.** The file excludes 61 products and deliberately leaves 16 public `spotfire*` slugs in scope — its header names the Data Science and Statistica lines, and Mayur's custom-page list includes `spotfire-statistica`, so that policy is intact. But `spotfire-application` is in that in-scope 16 **only because the dedup bug hid it when the list was compiled on 2026-09-09.** It was never a candidate for exclusion because nobody could see it.

So the standing state is: *99 versions of Spotfire Analyst are out of scope by intent, in scope by configuration, and protected from download by nothing but a bug.* The record ordering that hides it belongs to the API, not to us.

The two changes have to ship together. `scope.yaml` reports rules that match no product (`catalog.py:547`, `997-998`), so adding the entry while the product stays undiscoverable leaves a rule that warns on every fetch — and that warning exists to flag an upstream rename, so one that never clears is worse than no warning. Fixing the dedup makes the product discoverable, the rule match, and the exclusion behave exactly like the other 61: **catalogued, counted, never converted.** The dedup is also worth correcting as a rule rather than as a special case, because a visibility filter that runs *after* the dedup it depends on will reproduce this the next time the API duplicates a slug.

##### What gets built

1. **Parent fallback.** When `_build_product` finds no versioned record, re-request `{slug}-latest` before returning `None`, and build from that detail plus its siblings. One extra call per parent, ~34 per full crawl.
2. **Dedup after visibility, and prefer the public record.** Group `a_to_z` by slug, drop non-public records first, and only then dedup — so `non_public` counts a slug only when *every* record for it is non-public.
3. **Exclude `spotfire-application` in `config/scope.yaml`**, in the same change as 2 and for the reason above. Reason string matching the existing Spotfire entries; `display_name: "Spotfire® Application"` as documentation, since the file matches on `slug` by string equality only.
4. **Name the drop and cross-check it.** Keep `unversioned` but split out the products `a_to_z` claims have versions: a product with `versionCount > 0` that yields none is a defect, not a licence page, and belongs on its own report line with its slugs named. This is the guard that would have caught 18a on 2026-09-10; per the correction in 18a the counter already exists, so this is a naming and cross-check change, not a new tally.

##### Acceptance

A full `catalog fetch` adds **34 products / 685 versions** by the parent fallback, and the new defect line reads zero afterwards. `tibco-streaming` arrives from discovery with all 22 versions — matching the six rows 18c pinned by hand, which is the check that the fallback and the hand-pin agree. The 18c rows keep `custom_override=true` and must survive the fetch unchanged.

`spotfire-application` arrives as the 35th product with 99 versions and is **immediately out of scope**: `in_scope=false`, `scope_source=scope_rule`, zero versions download-eligible, and `scope_rules_unmatched` does **not** name it — the rule matching is the proof the dedup fix worked. Its 99 rows are inventory, not yield; the 62 `scope.yaml` rules must still match 62 products with none unmatched.

##### Shipped 2026-09-23 — and the gap closed exactly

`catalog fetch --all --include-archived` against the live docsite:

| | before | after |
|---|---:|---:|
| products in `config/products.csv` | 637 | **669** |
| versions in `config/versions.csv` | 4,480 | **5,181** |
| public A-to-Z slugs **not** in the catalog | 33 | **2** |
| products `in_scope=false` | 60 | **61** |

**669 public A-to-Z slugs, 669 catalog products.** 32 products added (0 removed), carrying 683 versions; the other 18 of the +701 are archived versions topped up onto products already present, `tibco-streaming`'s 16 among them. The largest arrivals are `spotfire-application` 99, `tibco-flogo` 49, `tibco-activespaces-enterprise-edition` 47, `tibco-activematrix-businessworks` 45 and the four `ibi-webfocus-*` at 152 between them.

**`tibco-streaming` now arrives from discovery with all 22 versions, and 18c's hand-pinned rows survived intact** — `custom_override=true` on the product row and on all six, `family_source=manual` held, `zip_source` untouched (`manual` on the two hand-filed 11.1.x packages, `auto` on the other four), and the 16 archived versions arrived `is_archived=true, convert_eligible=false`. That is the check the phase was built around: the fallback and the hand-pin independently produce the same 22 versions, and the merge protected the hand-pin rather than overwriting it.

**`spotfire-application` landed exactly as intended:** `in_scope=false`, `scope_source=scope_rule`, `product_code=sfire-analyst`, 99 versions catalogued and none of them ever selectable.

##### Two corrections to the acceptance criteria above

**"34 products / 685 versions" was wrong, in a way worth recording.** The real figure is 32 new products and 683 versions from them. Two of the 34 parents were never going to become new products: `tibco-streaming` was already in the catalog from 18c, so recovering it adds versions rather than a product — and the 685 count was taken by summing `-latest` sibling lists without checking that each sibling carries a usable version number. It counted records, and two of them are blank.

**"the new defect line reads zero" was also wrong, and the line is right.** It names **two** products, and both are real:

| slug | `versionCount` | what `-latest` actually returns |
|---|---:|---|
| `ibi` | 1 | `version_no: ''`, `folder_path: 'ibi'`, 0 siblings, **67 Documents** |
| `tibco-spotfire-for-apple-ipad` | 1 | `version_no: null`, `folder_path: null`, 0 siblings, 0 documents |

Neither is a crawler defect. Both are landing pages the docsite counts as having one version while publishing no version number for it — `ibi` is a documents hub, and the iPad product is already excluded by `scope.yaml` (and is the one rule that was *already* unmatched before this phase, now explained). The line is doing precisely the job 18a's correction defined for it: surfacing a disagreement between what the index claims and what discovery can read, by name, for a human to judge. Reporting two products a reader can resolve in one look is the intended output, not a failure of the fix.

`scope_rules_unmatched` therefore still names `tibco-spotfire-for-apple-ipad` — 62 rules, 61 matched. Unchanged by this phase and not caused by it.

##### Acceptance, measured

The catalog growth moved the end-of-support guard for the first time — `versions_retired` 128 → **139**, `eos_coverage` (253, 637) → **(270, 669)** — and the reading is still *population, not verdict*, on better evidence than the count:

* **Not one of the 4,480 pre-existing version rows changed `release_status` or `convert_eligible`.** The merge was purely additive.
* All 173 newly retired rows sit on products this fetch added, led by `tibco-activematrix-businessworks` (38) and `tibco-businessevents-enterprise-edition` (26).
* `products_fully_retired` is **unmoved at 11**, and it is the same 11 — nothing newly discovered is retired in its entirety.

Support's report is judging products it previously could not see; its verdict on everything it had already judged is untouched. Re-baselined with that written into the test.

**1,341 tests pass (+7), 2 skipped, lint clean.** The seven new tests cover the fallback path, its cost (a product with a child shape never asks for `-latest`), version keying onto the parent slug, the archived-sibling URL rule surviving the fallback, a parent whose `-latest` does not resolve being named rather than swallowed, a genuinely unversioned entry staying out of the defect bucket, and both duplicate-slug directions. `test_shipped_scope_lists_the_ebx_and_spotfire_products` was re-baselined 61 → 62 with the reason written into the test.

##### Still deferred

1. The **16 archived `tibco-streaming` versions**, which need `/api/products/archive/{slug}` rather than a template.
2. The two `streaming` bundle rows left `convert_eligible=true` (see "What 18c does not do").
3. **Not in this phase, and no longer a hypothesis:** `tibco-streambase-high-performance-fix-engine` 11.1.1, 11.1.0, 10.6.6 and 10.6.5 are active with correct `sb-hp-fix/<version>` folder paths whose templated URLs return an empty body under HTTP 200 — the four `NO_TREE` rows in the streaming run. 18c **proved the mechanism** on `tibco-streaming` 11.1.1 and 11.1.0: the `finalSlug` in the filename is the product's display name *at that release*, and both resolve under a `spotfire-` stem. `active_template` needs a per-version stem, not the catalog's current slug. A filename-derivation defect, independent of the parent-product shape, and it gets its own phase rather than being absorbed into this one.

---

### Phase 18e: The First DocBook Family Reaches Publication — **Measured, 2026-09-23**

Not a build. `sync` and `validate` were run over the `streaming` family exactly as they shipped; nothing in the tool changed. It is recorded here because **no DocBook family had ever reached Stage 7**, so every number below is the first of its kind, and because the one class of finding it produced is a converter defect that needs its own phase.

##### `sync --family streaming --target-dir C:\github\tibco-docs-aem`

30 versions selected, **76 rows synced, 41,523 files, 858.3 MB**, into `en-us-tib-streaming-userdocs` and `en-us-tib-streaming-userdocs-resources`.

| doc-class | synced | no source tree |
|---|---:|---:|
| `online-help` | 8 | 22 |
| `user-guides` | 2 | 0 |
| `release-information` | 26 | 0 |
| `reference-documents` | 26 | 0 |
| `api-references` | 8 | 0 |
| `archives` | 6 | 0 |

0 failed, 0 skipped, 0 already-current. **8 product `metadata.yml` and 19 `version.yml` written.**

**The 22 `No source tree` rows are the ones already accounted for and none of them is new** — the 17 licence bundles and `tibco-modelops@1.3.0` that `ENGINE_UNKNOWN` names, plus the 4 `sb-hp-fix` `NO_TREE` rows. Each still published its `release-information` and `reference-documents` from the *extracted* package, which is the behaviour §6 was built for: **a version that never converted still publishes the PDFs it shipped.** Those 22 absences are the reason `release-information` is 26 rows while `online-help` is 8.

`spotfire-data-streams` 11.1.0 and 11.1.1 publish a full `online-help` and `api-references` of their own. That is the rebrand showing up in the published tree — the same content under both the old and the new product name — and it is catalog truth, not a sync fault.

##### `validate --target-dir C:\github\tibco-docs-aem --product <slug>`, all 8 products

`validate` has no `--family`, so it ran once per published product. **All eight exit 0.**

| | |
|---|---:|
| folders walked | 76 |
| files | 9,481 |
| references | 121,157 |
| of which external | 3,925 |
| of which tree-rooted | 268 |
| anchors resolved | 46,202 / 46,354 |
| `LINK_BROKEN` | **0** |
| errors, any code | **0** |
| warnings | **152 `ANCHOR_MISSING`** |

**268 tree-rooted API references resolve, 268 of 268** — which also proves the two `-resources` trees they name were actually written. Phase 17's precedent was that sync is where link damage becomes visible; for DocBook it did not, and 0 of 121,157 is the strongest single number the family produced.

**Version drop-down integrity holds** (§2): all 19 `version.yml` were read back, **62 of 62 `path` values resolve to a sibling directory sync wrote**, the listed set equals the on-disk set in every file, and every file is ordered numeric-descending.

##### The one defect: a DocBook admonition's anchor dies with its title

All 152 warnings are **4 distinct anchors** — an identical 19 per `online-help` version, 114 on `tibco-streaming` and 38 on `spotfire-data-streams`, which is the same content twice. Every one has the same shape:

```html
<div class="note" style="margin-left: 0.5in; margin-right: 0.5in;">
   <h3 class="title"><a name="mapsUsageNote"></a>Usage Note</h3>
   <p>The JMS Configuration Editor does not support …</p>
</div>
```

`engines/docbook.py` renders the admonition as a GFM alert and **discards both the custom title and the anchor**:

```markdown
> [!NOTE]
> The JMS Configuration Editor does not support …
```

The six inbound `…#mapsUsageNote` links per version survive the conversion intact and now point at nothing. The four are `mapsUsageNote` and `expressions_timestamp_abs_usagenote` / `expressions_note_aggfuncs-in-query-op` (`div.note`) and `docker-create_dockernotes` / `docker-lv-create_important` (`div.note`, `div.important`).

**The population is bounded and was measured, not estimated.** Scanning the whole 11.2.1 source for `div.{note,important,warning,caution,tip}` whose title carries an `<a name=…>` finds **exactly 5**; 4 are link targets and account for 100% of the family's findings, and the 5th has no inbound link. A titled admonition is not a heading in the DocBook output either — it is an `h3` inside the box — so the fix is to carry the id onto the emitted alert rather than to synthesize a heading slug, and `anchors` already has to agree with whatever is emitted. **A code change, so it waits for its own plan and approval.**

##### What this run does not claim

**A clean `validate` is not evidence that the 3 `REFERENCE_UNRESOLVED` conversion errors were repaired.** `REFERENCE_UNRESOLVED` is a *convert*-stage code (`findings.py:139`, emitted at `driver.py:444` for asset references that resolved to nothing) — the reference was dropped from the Markdown before sync ever saw it, so Stage 7 is silent about them by construction. `report --run` on the convert run remains the only place they are visible. Reading their absence here as a fix would be reading the wrong stage's silence.

---

### Phase 19: A DocBook Admonition's Title Is Not Only a Label — **Built, 2026-09-23**

18e's `validate` produced exactly one class of finding over the whole `streaming` family, and this phase is it. `engines/docbook.py:_admonition` deletes the `h3.title` because GFM's alert syntax draws the label itself (§5.6.7) — correct for the 96.3% of titles that say nothing but "Note". For the rest, the `h3` is carrying two things the deletion takes with it.

##### The defect, stated precisely

The engine **records an anchor it does not emit**. `_prune_anchors` (`docbook.py:795`) runs at line 523, keeps every `a[name]` something references, and returns that set as the page's `anchors`. Rendering happens afterwards, and `_admonition` (`docbook.py:186`) calls `title.decompose()` on the whole `h3` — taking a surviving `<a name="mapsUsageNote"></a>` with it. Nothing notices, because the two halves never speak: the page still *claims* the anchor, so `link()` (`docbook.py:662`) resolves every inbound `…#mapsUsageNote` and emits a live link into it. The result is a link the converter is confident about, pointing at a fragment that was deleted three hundred lines earlier — invisible until a published tree is walked.

That is why this only surfaced at Stage 7. It is not a link the engine dropped and reported; it is a link the engine *kept* on the strength of a promise it then broke.

##### Measured over every DocBook tree in the extraction cache

8 trees (the 6 `tibco-streaming` versions and the 2 `spotfire-data-streams` ones — the whole of the extracted DocBook corpus), **10,757 titled admonitions**:

| | count | share |
|---|---:|---:|
| titled admonitions | 10,757 | 100% |
| title is exactly the kind label ("Note", "Caution") | 10,361 | 96.3% |
| **title is something else** | **396** | **3.7%** |
| **title carries an anchor** | **40** | **0.37%** |

By kind: note 5,496, caution 2,731, important 1,717, tip 465, warning 348. The 40 anchored titles are 32 `note` and 8 `important`.

The 396 custom titles are not noise, and they are not evenly spread — they are a short vocabulary repeated across versions:

| title | occurrences |
|---|---:|
| `Disclaimer` | 120 |
| `Notes` | 96 |
| `Third-Party Software` | 42 |
| `Usage Note` | 16 |
| `Deprecated` / `DEPRECATED` | 22 |
| `Documents or My Documents?` | 14 |
| `Caution 1` / `Caution 2` / `Caution 3` | 24 |
| `Note on Backslashes in Examples` | 8 |
| the remaining 8 distinct titles | 54 |

`Disclaimer`, `Third-Party Software` and the numbered `Caution 1..3` are the ones that make the case: a box labelled "Disclaimer" rendered as a bare `> [!NOTE]` has lost the only word that said what it was, and a cross-reference reading "see Caution 2" now points into a page with three indistinguishable cautions.

##### What gets built

**1. The anchor survives the title.** `_admonition` harvests `markdown.anchor_target()` from every `a[name]`/`id` inside the `h3.title` *before* decomposing it, and emits `markdown.anchor_marker()` as a block immediately above the alert. Both helpers already exist (`transforms/markdown.py:120,135`) and are what `inline_override` (`docbook.py:228`) already uses for every other kept anchor in the engine, so this is the existing mechanism reaching one element it could not reach, not a new one.

Above the box rather than inside it: an `<a id>` is a block-level HTML line there, unambiguous to every renderer, and it cannot interfere with GFM's alert parsing — which is sensitive to what follows `> [!NOTE]`. Landing the reader at the top of the box is also what the DocBook anchor meant.

**2. The custom title survives as the alert's first line**, bolded, when and only when it is not the kind label — `callouts.alert_for(title_text)` is the existing test and it already folds case and punctuation (`callouts.py:53`), so `Note:`, `NOTE` and `note` are all recognised as the plain label and still deleted. The 10,361 ordinary ones are untouched and the double-label trap §5.6.7 exists to avoid stays closed.

**3. `_prune_anchors`' promise becomes checkable.** The set it returns is the page's `anchors`, and the whole defect is that rendering can silently fail to honour it. The renderer asserts the kept set against what was actually emitted and records the difference rather than letting it pass — a converter that believes in an anchor it dropped should say so at Stage 5, not at Stage 7 two commands later.

##### Acceptance

- `validate --target-dir … --product tibco-streaming` and `--product spotfire-data-streams` report **0 `ANCHOR_MISSING`**, down from 114 and 38.
- Re-converting the 8 DocBook versions changes **exactly** the admonition blocks: 40 anchor markers added, 396 titles restored, and no other diff in 15,261 output files.
- The 10,361 plain-labelled admonitions are byte-identical to what ships today.
- No new finding code; `ALERT_LABEL_UNMAPPED` stays unreachable from this engine, because a custom title is not an unmapped label — it is a title, and it is now kept rather than matched.

##### Shipped, measured 2026-09-23

Re-converted all 30 `streaming` rows, re-synced, re-validated.

| | before | after |
|---|---:|---:|
| `tibco-streaming` anchors resolved | 34,674 / 34,788 | **34,788 / 34,788** |
| `spotfire-data-streams` anchors resolved | 11,528 / 11,566 | **11,566 / 11,566** |
| `ANCHOR_MISSING` | 152 | **0** |
| findings, whole family | 152 warnings | **none** |

**The diff is purely additive, and that is the acceptance criterion rather than a pleasant surprise.** Against the previous publication of `tibco-streaming@11.2.1` as a byte baseline: **38 of 2,538 files changed, 92 lines added, 0 lines removed, 0 files added or dropped.** The added lines are exactly the restored titles and the anchor markers — `**Disclaimer**` 12, `**Notes**` 8, `**Third-Party Software**` 5, `**Usage Note**` 2, `**Caution 1/2/3**` 1 each, two `<a id=…>` markers, and the `>` continuation lines the blockquote needs. All five anchored admonitions are emitted in all six `tibco-streaming` versions.

`sync` then reported **8 synced and 68 already-current** — it re-copied the 8 `online-help` trees and nothing else, which is the idempotency rule of 6b holding on a real change rather than on a re-run.

##### The guard found a second population on its first run, and that is the point of it

`ANCHOR_DROPPED` fired **7 times across 6 pages** — `d0e3280`, `d0e5253`, `d0e3109`, `d0e3244`, `d0e12125` — and none of them is an admonition. They are DocBook's auto-generated `a.indexterm` anchors sitting **inside table cells**, kept by `_prune_anchors` because something references them and then lost on the table path. A second instance of the same class of bug, in a different handler, that nothing in the tool had ever said a word about.

**None of the 7 produces an `ANCHOR_MISSING`**, because no inbound link to them survives into the published tree either — so the guard is reporting a broken promise that nothing happened to depend on. That is the right side to err on: it fires when the engine contradicts itself, not when a reader notices. Left unfixed and named here rather than folded into this phase; it is the table renderer's, not the admonition handler's.

##### Cost, as built

One function in one engine (`_admonition`), one line in `inline_override`, one comparison in `_convert`, and the register's 44th code. **1,345 tests pass, 2 skipped, lint clean** on `src` and `tests`.

---

### Phase 20: Reframe — A Flare Topic Is Too Small To Maintain — **20a–20d.1 built, 20e planned, 2026-09-24**

Every phase so far has converted a source tree faithfully. Reframe is the first that deliberately *changes the shape* of what the source said: it merges MadCap Flare's very small topics into fewer, larger pages, turning each former topic into an anchored `##` section, and it does so once, permanently, because Markdown becomes the authoring source the moment the migration lands.

The component arrived specified. `docs/REFRAME-REQUIREMENTS.md` defines R1–R7, five hard constraints and eight acceptance checks; `docs/REFRAME-INTEGRATION-PLAN.md` proposes the phasing. Both are committed verbatim and **neither was written against this codebase** — the plan says so itself (§2) and ends with seven questions for the DocuShift side. This section answers those seven against the code, and records the two places where the specification and this repository disagree.

#### 20.1 The seven questions, answered against the code

| # | Question | Answer |
|---|---|---|
| Q1 | How does a stage read the **conversion engine**? | `VersionRow.engine`, a `SourceEngine` enum (`models.py`) carried in the `engine` column of `config/versions.csv` and threaded to converters as `ConversionContext.engine` (`engines/base.py:236`). A stage reads it off the catalog row; nothing needs threading. |
| Q2 | Can eligibility return **more than one version of the same doc set**? | **Yes, and for the reference product itself.** `tibco-enterprise-message-service` has **6 eligible Flare versions** — 10.4.0, 10.4.1, 10.4.3, 10.4.4, 10.5.0, 10.5.1 — all converted and standing in `output/en-us-tib-ems/`. `_download_selection` (`cli.py:833`) passes `eligible_only=True` and returns every one of them. **R1.4 layout pinning is mandatory, not conditional.** |
| Q3 | Is there a **manifest/report convention** the four CSVs should match? | Partly, and it cuts both ways — see 20.3. |
| Q4 | Can a stage **fail the pipeline** on its own validation? | Yes, and there is a two-command idiom: `errors = findings.counts()[Severity.ERROR]`, `findings.finish(exit_code=1 if errors else 0)`, `raise click.exceptions.Exit(1)` (`cli.py:1498` for sync, `cli.py:1581` for validate). Note `convert` deliberately does **not** do this. Reframe follows sync and validate. |
| Q5 | Where do **per-doc-set configs** live, and is there precedent for editorial policy? | `config/*.yaml`, loaded through `ConfigManager` (`config.py:143`). The precedent is `scope.yaml`: a YAML rule file stating policy, overridable per row by a CSV column, with a `*_source` provenance column deciding who wins. `MAX_WORDS` belongs in exactly that shape. |
| Q6 | Can a stage **run standalone** against frozen upstream output? | Yes. `convert --input/--output` (`cli.py:1252`) already converts a standalone extracted folder, and `validate --target-dir` walks any synced tree. The plan's assumption holds and the fast iterate loop is available. |
| Q7 | Which stage owns `toc.yml`/`metadata.yml`, and does anything downstream consume them? | Stage 6a writes both, per version, at `converter/driver.py:423,429`, rendered by `converter/navigation.py` from `NavNode` trees. Downstream, `sync/distributor.py` writes *container-level* files of the same names and never rewrites a version's; `validation/artifacts.py:150` reads the version's `toc.yml` and checks every `path` in it. So Reframe has one producer to coordinate with and one checker that will grade its work. |

There is **no stage-registration abstraction** to hook into. A stage in this tool is a package under `src/docushift/` plus a `@main.command()` in `cli.py` — `downloader/`, `extractor/`, `converter/`, `sync/`, `validation/`. Adding Reframe means adding `reframe/` and a command, not registering with an orchestrator. The integration plan's "recommended integration shape" (§3) therefore lands as written, and the engine gate it asks for in two places (C1/C2) has only one place to live, which makes C2 the operative rule rather than a belt-and-braces one.

#### 20.2 The corpus checks out, and that is not a given

The requirements quote a POC baseline for EMS 10.5.1. Measured against this repository's own Stage 6 output at `output/en-us-tib-ems/tibco-enterprise-message-service/10.5.1`:

| | requirements §6 | measured here |
|---|---:|---:|
| topics | 1,441 | **1,441** |
| median words/topic | ~107 | **107** |
| total words | 226,517 | **226,871** |
| guides (top-level TOC items) | 9 | **9** |
| largest single topic | — | **3,533** |

The POC was run against DocuShift's output, not against some other conversion, so §6's numbers are a genuine regression baseline rather than a figure from a neighbouring tool. The 354-word gap is frontmatter handling and nothing to chase. The largest *topic* is 3,533 words and §6's largest *page* is also 3,533 — the POC's biggest output page was one oversized topic on its own, which is R1.3 already firing once on the reference corpus.

Two further facts the requirements do not mention, both from the measured tree:

- **`toc.yml` carries 1,441 paths and zero fragments today.** Every node points at a whole file. R3 turns most of them into `page.md#anchor`, which is a shape this tool already emits elsewhere — `NavNode.anchor` exists and 12.1% of Flare's *source* TOC entries carry one (`engines/base.py:91`).
- **Output filename stems are truncated to 20 characters** (`installation-overvie.md`, `integrating-with-thi.md`). R2 slugs anchors from the source filename, so it slugs from these truncated stems. That materially raises the collision rate the "dedup must loop" edge case (§7) was written about, and it is why that rule is not optional here.

#### 20.3 Where the specification and this repository disagree

Two conflicts. Both are cheap now and expensive after Phase 20b.

**1. `## Heading {#anchor}` is not a shape this tool can emit or check.** R2 specifies the Pandoc/kramdown heading-attribute syntax. GFM has no such syntax — the braces render as literal text — and this repository has already answered the question in the opposite direction: `engines/docbook.py:inline_override` emits `<a id="…"></a>` as passthrough HTML with the comment *"GFM has no anchor syntax"*, and Phase 19 extended exactly that mechanism. Worse, Stage 7 would not merely fail to see the anchor, it would see the **wrong** one: `validation/references.anchors()` collects computed heading slugs and `id=`/`name=` attributes only, and `slugify_heading` strips `{`, `#` and `}` as punctuation, so `## Overview {#tibemsd-conf}` registers the anchor `overview-tibemsd-conf` and every R4 link written to `#tibemsd-conf` becomes an `ANCHOR_MISSING`. **R2 is implemented as `markdown.anchor_marker()` above the heading**, which is the house idiom, is already validated, and is what Phase 19 shipped 40 of.

**2. Three of the four CSVs are derived data, and this tool does not publish derived data as CSV.** CSV here means one thing: the human-editable catalog surface, `config/products.csv` and `config/versions.csv`, written through `utils/csvio.py` and governed by `*_source` provenance columns. Derived per-version facts are YAML sidecars in the output tree (`toc.yml`, `metadata.yml`, `csh.yml`); derived *findings* go to the register and `state.db` and are rendered by `reporting/report.py`. So:

| spec artifact | proposed home | why |
|---|---|---|
| `manifest/pages.csv` | `reframe.yml` sidecar in the version's output tree | derived, per version, alongside `toc.yml` — the same shape and the same lifecycle |
| `manifest/topic-mapping.csv` | the same `reframe.yml` | it is the inverse index of the same fact; two files would be two truths |
| `manifest/redirects.csv` | `redirects.yml` sidecar, and a Stage 7 check | a redirect map is a publishing artifact, and R5's "zero dangling" is a validation question |
| **`manifest/review-queue.csv`** | **stays CSV, as specified** | it is the one human-editable artifact of the four, and that is precisely what CSV is for in this repository |

This is a change to R6's neighbours, not to R6. The review queue — which the integration plan (§5) correctly identifies as the contract to fix first — keeps its columns and its format.

#### 20.4 Phasing

Renumbered onto this repository's scheme; the integration plan's Phase 0–4 map onto 20a–20e.

- **20a — Contracts and the gate.** *(built)* `reframe/` package, `docushift reframe` command with the standard `_scope_options`, engine assertion inside the stage (C2), no-op passthrough for non-Flare, the `reframe.yaml` config shape with `MAX_WORDS` and the TOC-schema adapter seam. *Exit: the command runs over the whole catalog, touches nothing that is not Flare, and passes a Flare set through byte-identical.*
- **20b — Packing.** *(built)* R1–R5, fence-aware parsing, the three POC defects from requirements §10 left unported, **R1.4 layout pinning pinned to the newest eligible version** (required by Q2), determinism check. Anchors emitted per 20.3(1). *Exit: reproduces §6's baseline on EMS 10.5.1, page count allowed to rise from dropping `MIN_WORDS`.*
- **20c — Review queue.** *(built)* R6 and R7.1. On the critical path, not polish: the ~25–30 flagged pages are the only ones a human ever sees, and Phase 20b ships deliberately incomplete without this.
- **20d — Stage 7 integration.** *(built)* Teach `validation/` about the redirect map and the merged TOC, so R5 and R6's acceptance checks are enforced by the existing checker rather than by a second one inside Reframe. Wire the exit-code idiom from Q4.
- **20e — Pilot.** One doc set, queue worked, **explicit writer sign-off before redirects are published.**

#### 20.5 What this phase does not claim

- **That Reframe should run on all six EMS versions.** Q2 establishes that it *can* be asked to, which is what makes R1.4 mandatory. Whether the older five are worth merging is a scope decision for 20e, not a mechanical one.
- **That the 14 `engine=flare` rows are the Flare population.** 1,647 of the 1,683 convert-eligible version rows are `engine=auto` and detect their engine at extract time (`engines/detector.py`). Reframe's real reach is unknown until those run, and sizing it is not a blocker for 20a.
- **That §8's pre-existing defects have been confirmed here.** The requirements list 31 dangling in-page anchors and title mojibake in the reference corpus. Neither has been measured against the current tree, and Phase 19 changed how at least one engine emits anchors. They are baselined in 20b, before merging, exactly as the risk table says. *(20b: the link half is measured — 92 unresolvable relative references, all `.html`/`.htm` into a sibling `…-resources` tree that Stage 6 does not produce. They are counted as `unresolved`, left exactly as written, and reported as `REFRAME_LINK_UNRESOLVED` rather than failing the stage. The in-page anchor count and the title mojibake are still unmeasured and belong to 20c, which is the phase that looks at page titles.)*

#### 20a Contracts and the gate — **Built & verified, 2026-09-23**

`src/docushift/reframe/` — `driver.py` (the gate, currency, build-and-swap), `toc.py` (the adapter seam), `policy.py` (per-product resolution and the currency digest) — plus `config/reframe.yaml`, `ConfigManager.reframed_path` / `load_reframe`, and a `reframe` command sitting between `convert` and `sync`.

**The register gains a sixth stage.** `Stage.REFRAME` is declared between `CONVERT` and `SYNC`, which is what puts the section in pipeline order in `report` (`_STAGE_RANK` reads declaration order). Two codes, taking the register **44 → 46**, and deliberately only two: 20a merges nothing, so the only things it can report are the two ways it refuses to guess. The codes the merge itself owes — an oversized page, a collided anchor, a queued review — are not registered ahead of the checks that emit them, which is what `test_every_registered_code_is_written_down_somewhere_in_src` exists to prevent.

| decision | what was built | why not the obvious alternative |
|---|---|---|
| **Output location** | A sibling `reframed/` tree, never a rewrite of `output/` | C4. Boundary rules get tuned repeatedly and each pass needs a clean input; an in-place merge makes every tuning pass a restore from git, and makes the irreversibility the plan calls its first risk start one phase earlier than it has to. |
| **Engine gate** | First statement in `reframe_one`, before any path is computed | C2. `--input` is the invocation the selection cannot filter, and it is exactly where a wrong-doc-set run happens. |
| **Unrecognised `toc.yml`** | `REFRAME_TOC_SCHEMA_UNKNOWN`, **error**, version fails, nothing swapped | A half-parsed tree does not merge badly — it merges into a plausible page count with one branch silently missing. A configured schema that is not registered also fails rather than falling back to detection, for the same reason. |
| **Currency key** | `reframe_source_checksum` (the upstream `convert_source_checksum`) **and** `reframe_policy_key` (a digest of the resolved policy) | Keying on the input alone is convert's `convert_api_prefix` lesson. Here it would be the common case, not a corner: a tuned `reframe.yaml` would leave every tree reporting `current` and the tuning loop would silently be a no-op. |
| **Swap budget** | 8 attempts over ~9s, not `swap`'s default 5 over ~1s | Measured, not guessed — see below. |
| **Non-Flare rows** | Counted, never named | 1,669 of 1,683. The opposite call to `convert`'s `ENGINE_UNKNOWN`, which is rare and is a to-do. `NO_OUTPUT` is still named: it means somebody expected a merge. |

**Two things the first real run found.**

The swap failed on EMS 10.5.1 with `PermissionError: [WinError 5]` and left the `.part` tree standing — then succeeded on a manual retry seconds later. `swap`'s 1-second budget is calibrated against `convert`, which writes its files one at a time over minutes; this stage hands the scanner 1,441 files in a burst and immediately asks to rename the directory out from under it. Widened at the call site rather than in `utils/swap.py`, so the other callers' genuine failures stay fast. Three consecutive `--force` runs then passed.

The six DataSynapse Flare versions have **no `convert_source_checksum` recorded at all**, so they can never report `current` and are re-copied on every run. This is inherited behaviour, not a defect introduced here — `convert` applies the same rule — and the rule is the safe direction: no recorded provenance, no currency claim. Pinned by `test_a_version_with_no_recorded_conversion_is_never_current` so it is specified rather than accidental.

**R1.4 decided, not deferred.** The first full run raised `REFRAME_LAYOUT_UNPINNED` five times across two products. All three multi-version Flare sets are now pinned to their newest eligible version in `config/reframe.yaml` — EMS `10.5.1`, gridserver-manager `7.2.0`, hpc-cloud-adapter `2.2.0` — which is the version `iter_versions` yields first and the one a fix gets written against. The other three Flare products have one eligible version each and are left unpinned; the code will name them if a second arrives. The risk table calls this "cheap now and impossible later", and it cost one config block.

**Verification.** `reframe --all` over the full catalog: **6 reframed, 8 already current, 1,669 not Flare, 0 no-output, 0 failed, 0 findings.** EMS 10.5.1 passes through **byte-identical — all 1,476 files, SHA-256 per file, zero differences** — and reads **1,441 topics** out of `toc.yml`, matching the corpus measurement in 20.2 exactly. The input tree is unmodified on bytes and mtimes. A second run with no `--force` reports `current`; a `max_words` edit invalidates it. **1,373 tests pass** (25 new in `tests/unit/test_reframe.py`), `ruff` clean.

**What 20a does not do.** It merges nothing. `pages` equals the `.md` files copied, which is why the report reads `1441 topic(s) -> 1441 page(s)`; the number only becomes meaningful when 20b writes merged pages. No anchors are emitted, no TOC is regenerated, no redirects are written, and `review-queue.csv` does not exist yet. The `reframed/` tree is currently a copy, and that is the baseline 20b diffs against.

#### 20b Packing — **Built & verified, 2026-09-23**

Four new modules and one rewired driver. `packer.py` decides layout (R1, R2, R4.1, R4.2) and never opens a topic body — word counts arrive through a callable, so the whole of R1 is testable against a dict of sizes. `pages.py` turns a page's topics into bytes (R2.1, R4, R7). `audit.py` is §6's acceptance suite, run **before** the swap. `manifest.py` writes the two sidecars. `toc.retarget` regenerates the navigation (R3).

**The register gains three codes, 46 → 49.** `REFRAME_SELF_CHECK_FAILED` (error), `REFRAME_LINK_UNRESOLVED` (warning), `REFRAME_TOPIC_UNTOCKED` (warning). Each is registered alongside the check that emits it, not ahead of it.

| decision | what was built | why not the obvious alternative |
|---|---|---|
| **Anchor syntax** | `markdown.anchor_marker` as its own block above the heading | 20.3(1). GFM has no attribute syntax, so the POC's `## Title {#a}` renders the braces as literal text and the anchor does not exist. |
| **Reading order** | `_subtree` returns one ordered run of closed `Page`s and open `_Unit`s; the packer splices *around* the pages | The POC appended to a shared list as the recursion unwound, so an overflowing child subtree's pages landed before the page holding their own parent's topic — which reads earlier. Order becomes an invariant of the return type rather than something to check. |
| **R4.2** | Enforced at the join, not checked afterwards | "No page spans two source directories" then holds by construction. Every top-level subtree on the reference corpus is single-directory, so this changes nothing here; it is the sets not laid out that way that would otherwise get a page whose relative asset paths are correct for half its content. |
| **Fence-awareness** | Every scan matches against `references.mask_code` / `mask_html_blocks` and edits the original by offset | Requirements §7's latent corruption. A `# comment` preceding a topic's real H1 becomes the *anchored* heading, and the topic's identity becomes a line of shell. The corpus has zero of these, which is why the POC never showed it. |
| **Self-validation** | In the stage, before the swap; a failure removes the staging tree | §6 asks for it and §1 says why: the merge is a one-way door, so the run that built a tree is the last cheap moment to reject it. A check that lives only in the test suite protects the reference corpus and nothing else. |
| **Broken links** | Split into `unresolved` (absent from disk — tolerated, §8) and `orphaned` (present but unclaimed — fatal) | R4's discriminator is *unresolvable*, which is an existence question, not a suffix question. A first cut keyed on `.html` would have passed a genuinely orphaned `.md` and failed on Stage 6's pre-existing defects. |
| **Sidecars** | `reframe.yml` and `redirects.yml` at the version root, YAML | The POC wrote three CSVs into a `manifest/` directory beside the script, shared across every version it ever ran on, so the second run overwrote the first. These are the only place that survives the `.part` swap and the only place Stage 7 can find without being told. |

**Three things the corpus found that the reference set does not exhibit.**

*Word conservation failed by exactly one token per topic.* `<a id="x"></a>` is **two** whitespace-delimited tokens, not the one requirements §6's "+1 per topic" assumes. `shift_headings` now *measures* what it added and returns it; a hand-written constant only ever encodes whichever anchor syntax was in mind when it was written.

*A topic listed under two guides.* GridServer 7.2.0's `toc.yml` has 1,014 nodes over 1,000 distinct paths — `Typographical_Conventions.md` appears three times — and packing it three times copies its body onto three pages. A `claimed` set threads through the walk: the first node to reach a path owns the content, the rest become rows pointing at the same `page.md#anchor`, which `retarget` handles for free.

*A topic on disk the TOC never lists.* Runtime Agent 5.13.0 has 651 `.md` files and 649 nodes, and one of the two strays is the target of a live link. Stage 7 publishes the whole `output/` tree, so these are **already published**; dropping them would make Reframe delete live content as a side effect of a navigation gap. `packer.carry` turns each into a single-topic page rendered through the same pass — so its own links are rewritten — exempt from reachability only, and named by `REFRAME_TOPIC_UNTOCKED`.

**Verification against §6's reference baseline** (EMS 10.5.1, `max_words: 3000`):

| metric | POC baseline | built |
|---|---|---|
| topics → pages | 1,441 → 106 | 1,441 → **124** |
| words per page | median 2,354 · min 20 · max 3,533 | median 2,082 · min 7 · **max 3,533** |
| topics per page | median 12 · min 1 · max 60 | median 10 · min 1 · **max 60** |
| guides | 9 | **9** |
| words in → out | 226,517 → 227,958 | 226,871 → 229,753 |
| links | 2,345 checked, 2,314 rewritten, 0 newly broken | 2,784 checked, 2,695 rewritten, **0 newly broken** |

The page-count gap is accounted for twice over and the exit condition allows it. The POC ran against a *different* conversion of the same doc set (226,517 words against DocuShift's 226,871), and the reading-order fix refuses to merge units across an already-closed page — worth about eleven pages, and it buys pages whose sections are contiguous in the guide.

**Verification, the rest.** `reframe --all --force` over the catalog: **14 reframed, 1,669 not Flare, 0 failed, 0 errors, 7 warnings**; 11,776 topics → 1,131 pages. C5 checked by copying the tree aside and re-running with `--force` — `diff -r` byte-identical. C4 checked with `git status --porcelain output/` — clean. R2's looping dedup fires on exactly §7's case (`tibemslookupcontext-.md` → `-2`, then `tibemslookupcontext-2.md` → `-2-2`); 16 slugs collide corpus-wide and only two dedups fire, because R2's uniqueness scope is per page. The output tree is 124 pages + 33 images + `metadata.yml` + the three regenerated YAML files, and carries 1,441 redirects with unique `from` values. **1,417 tests pass** (66 in `tests/unit/test_reframe.py`, up from 25), `ruff` clean.

**What 20b does not do.** No review queue and no `review-queue.csv` — R6 and R7.1 are 20c, and a merged page still inherits its first topic's title with nothing flagging it. Stage 7 does not yet read `redirects.yml` or merge the TOC (20d). `MIN_WORDS` is deliberately not reimplemented (R1.2), and the POC's unused basename-keyed `dest` map is not ported.

#### 20c Review queue — **Planned, 2026-09-24**

R6 and R7.1. This is the interface between the mechanical stage and the writer, and the requirements put it on the critical path: "Reframe deliberately does not resolve these cases itself."

**The specified flag set does not discriminate in this implementation, and that had to be measured before anything was built.** Applying R6's five conditions literally to EMS 10.5.1 at `max_words: 3000` queues **124 pages out of 124** — which R6's own sentence forbids in the line above the table: *"a queue containing every page is not a queue."* Two flags are responsible:

| flag | fires on | why |
|---|---|---|
| `title-inherited` | **107 of 124** | The condition is "`n_topics > 1` and the page title equals its first topic's title". R7 *defines* the page title as the first topic's, so the second clause is true by construction and the flag reduces to `n_topics > 1`. |
| `single-topic` | **17 of 124** | R6's own column says "usually fine; flags structural outliers". A condition that is usually fine is not a reason to put a page in front of a human. |

Between them they cover every page — 107 + 17 = 124 — so the other three flags never get to mean anything. Those three, on their own, flag **20 pages**: `reference-list` 13, `heterogeneous` 7, `oversized` 1. *(18 as built — see the `heterogeneous` scope decision below.)* That is very close to R6's own predicted load of "roughly 25–30 rows out of 106 pages", which suggests the estimate was made against a queue the two structural flags did not dominate.

**A better page title cannot be derived from the TOC, and that is worth recording rather than re-litigating.** The obvious answer to R7.1 — "emit the best title it can" — is to title a page after the TOC node whose subtree it covers, rather than after its first topic. Measured: **30 of 124 pages are exactly one TOC subtree (20 of the 107 multi-topic pages), and in every one of those cases the subtree node's title is the identical string to the first topic's title.** It has to be: the packer walks bottom-up in reading order, so a subtree's own node contributes the first topic on the page it collapses into. There is no better title available from structure. R7.1's "best it can" is already what R7 emits, and the improvement is a human one — which is the whole reason the flag exists.

**Decided — `title-inherited` and `single-topic` annotate, they do not queue.** Measured on EMS 10.5.1, with `reference-list`, `oversized` and `heterogeneous` queueing as specified in every row; the first row is the one taken:

| rule for `title-inherited` | queue | share of 124 pages |
|---|---|---|
| **Annotation only — never queues a page by itself** ← chosen | **20** (18 as built) | **16%** |
| `n_topics >= 12` and the page is not exactly one TOC subtree | 56 | 45% |
| `n_topics >= 12` | 61 | 49% |
| `n_topics > 1` and not exactly one TOC subtree | 91 | 73% |
| `n_topics > 1` — the literal specification | 108 | 87% |

`single-topic` is annotation-only under every row; nothing in R6 argues for queueing a condition it calls "usually fine". Both remain visible in the queued rows' `flags` column and in `reframe.yml` for every page, so widening the queue later is a filter change rather than a re-measurement — which is why this is a safe row to take first.

**Everything below is settled regardless of which row is chosen.**

| decision | what gets built | why not the obvious alternative |
|---|---|---|
| **Location** | `<out>/review-queue.csv`, at the version root beside `toc.yml`, `reframe.yml` and `redirects.yml`; added to `_REGENERATED` | Same reasoning 20b applied to the sidecars. The POC's `manifest/` directory sat beside the script and was shared across every version it ever ran on, so the second run overwrote the first. The version root is the only place that survives the `.part` swap and the only place Stage 7 can find without being told. |
| **CSV, not YAML** | The one artifact of the four a human edits | Decided in 20.3 and unchanged. Derived per-version facts are YAML here; a flat worklist a writer opens in a spreadsheet is what CSV is for. Written `utf-8-sig` like the catalog CSVs, because titles carry `®`/`™` and Excel needs the BOM to read them. |
| **Columns** | `page_path, guide, n_topics, words, flags, detail` — R6's, unchanged | It is a published contract with an editorial skill that does not exist yet. Adding a column is cheap later; renaming one is not. |
| **Row order** | Reading order, matching `reframe.yml` | Not sorted by `page_path`. A writer works a guide at a time, and reading order is already deterministic, so sorting buys nothing and costs the ordering that makes the file navigable. |
| **Every flag recorded, queued or not** | The full flag set for every page goes into `reframe.yml`'s per-page block; the CSV carries only queued pages | Nothing is lost by narrowing the queue — a later decision to widen it is a filter change, not a re-measurement. This is also what makes the `title-inherited` row above reversible. |
| **`detail`** | One clause per flag, in the flags' declared order, joined by `; ` — e.g. `23 topics, median 61 words each`, `3,533 words over a 3,000 cap` | The flag says which judgment is being asked for; the detail has to carry the numbers that judgment turns on, or the writer opens the page to find them. |
| **Finding** | `REFRAME_REVIEW_QUEUED`, **note**, one per version, carrying the count and the flag breakdown. Register **49 → 50** | Not a warning. The queue is expected output of a successful merge on every run, and a warning that always fires stops being read — the same argument 20a made for counting non-Flare rows instead of naming them. |
| **Audit** | One new check: every queued `page_path` is a page that was actually written | The same class of bug `_redirects` already catches, and the same cost. A queue naming a page that is not there is a writer's dead end. |
| **Report** | `ReframeResult.queued`, surfaced in the per-version line and the run summary | The count is the thing a human acts on. It should not require opening a file to discover. |

*Exit: `review-queue.csv` at every merged version root; the queue is a strict subset of the pages and its size is defensible against R6's "not every page"; every flag is reproducible from `reframe.yml`; determinism unchanged.*

#### 20c Review queue — **Built & verified, 2026-09-24**

`src/docushift/reframe/review.py`, wired into `driver.py` between the pack and the write. Every row of the decision table above was built as written. One thing the corpus changed:

**`heterogeneous` counts *depth-2* ancestors only, and a guide's landing topic has none.** The first implementation bucketed a top-level row's own topic under its own title, which makes a page holding a parent topic plus its single child branch read as spanning two branches — the one shape that obviously is not heterogeneous. R6 says "depth-2 ancestor", and a guide landing topic does not have one. Measured on EMS 10.5.1: **5 pages either way against 7**, and the two dropped are exactly that false positive. A page merging a landing topic with *several* branches still flags, on the branches. Queue: **18 of 124**, not 20.

**Verified.** EMS 10.5.1, `--force`: 1,441 topics → 124 pages, **18 queued (14%)**, flag totals across all 124 pages `reference-list` 13, `oversized` 1, `title-inherited` 107, `heterogeneous` 5, `single-topic` 17. The one `oversized` row is `users-guide/tibemsd-conf.md`, a single 3,533-word topic — R1.3 forbids splitting a body, so the cap yields and the row says why. The queue reads as a worklist: eleven parameter tables, five multi-branch pages, one outsized topic. Two `--force` runs are byte-identical under `diff -r` (C5) and `output/` is untouched (C4). Suite `1,431 passed, 2 skipped`; `ruff` clean on `src`/`tests`; registry 50.

#### 20d Stage 7 integration — **Planned, 2026-09-24**

The merged tree currently goes nowhere. `sync` reads `config.output_path(...)` at `distributor.py:234` and has never heard of `reframed/`, so every version of every doc set publishes its unmerged Stage 6 pages and the four sidecars Reframe writes are, today, files on a developer's disk. 20d is the phase that makes the component load-bearing — and the phase where a mistake becomes a published URL.

**Two of the integration plan's four Phase 3 bullets are already done, and saying so is part of the phase.** Eligibility-driven version scoping shipped in 20a (C3, `_scope_options`, `eligible_only=True`). The Q4 exit-code idiom shipped in 20b: `cli.py:1451-1462` already fails the command on `len(stats.failures) or findings.counts()[Severity.ERROR]`, with the comment explaining why Reframe gates and `convert` does not. Neither is rebuilt. The **second TOC schema adapter** is measured and **not in scope**: all 14 merged doc sets parse as `items-path-children` and no run has ever raised `REFRAME_TOC_SCHEMA_UNKNOWN`. The seam stays; a second adapter arrives with the set that needs it.

What is left is the bullet this repository's own §20.4 wrote: teach Stage 7 and Stage 8 about the merged tree, so R5 and §6's TOC check are enforced by the existing checker against **what actually shipped**, rather than only by Reframe against what it believed it wrote.

**Half of that already works, and it was checked rather than assumed.** `artifacts._check_toc` resolves every `toc.yml` path against the published folder and — when the target is `.md` and the reference carries a fragment — looks the fragment up in `index.anchors(target)`. That is §6's "every referenced page exists; every referenced anchor exists" applied to a merged TOC, written three phases before there was a merged TOC to apply it to. Nothing needs adding for R3. `redirects.yml` is the one nobody reads.

##### The decision 20d turns on: publishing is opt-in, per doc set

| option | why not |
|---|---|
| Publish `reframed/` whenever it exists | 14 merged trees are already on disk from 20b/20c tuning runs. This option publishes all of them on the next `sync --all`, which is the irreversible step the whole plan exists to gate. |
| A `sync --reframed` flag | Not durable and not reviewable. The decision "this doc set is merged now" is a property of the doc set, not of one invocation, and it needs to survive the next person's `sync --all`. |
| **Opt-in per product in `config/reframe.yaml`** ← proposed | Same file, same shape and same reasoning as `pin_layout_to`. A writer's sign-off becomes **a commit** — reviewable, attributable, revertable — which is exactly what 20e asks for and the only form of sign-off this tool can actually enforce. Default `false`; **no product opts in during 20d.** |

So 20d ships the mechanism with nobody using it. That is deliberate: the pilot doc set is 20e's choice and a writer's, not this phase's.

**`publish: true` with no usable merged tree does not fall back.** A silent fallback to `output/` is the worst failure available here — it republishes 1,441 unmerged topics over a merged tree whose URLs are already live, un-merging published pages as a side effect of a merge that failed. Three cases, all reported, none published:

| state | what sync does |
|---|---|
| no `reframed/` tree | `SyncOutcome.NO_OUTPUT`-shaped row naming `docushift reframe`, same as a missing conversion |
| `reframe_source_checksum` ≠ the version's current `convert_source_checksum` | refuse and name it: the merge predates the conversion beneath it |
| tree present and current | publish it instead of `output/` |

The staleness test is the comparison Reframe already makes for its own currency (`driver.py:237-238`), read from the same state metadata. It belongs in `sync` and not in `validate`, because `validate` deliberately takes no catalog — §7.1, "the target is the evidence" — and a checker that needed the state DB could not check the one tree somebody most wants checked.

##### What validation learns

`redirects.yml`, checked the way `toc.yml` is checked, in `artifacts.py` beside it and reusing its codes:

| check | code | why |
|---|---|---|
| every `to` resolves to a file in the folder | `LINK_BROKEN` (**error**) | R5's "zero dangling", enforced at the gate. Same code `toc.yml` paths already use — a dangling redirect is a broken link that happens to live in a different file. |
| every `to` fragment is a real anchor on that page | `ANCHOR_MISSING` (warning) | A redirect landing at the top of a twelve-section page is the exact failure R5's anchors exist to prevent. Warning, matching `toc.yml`. |
| a `from` that still resolves to a published file | **`REDIRECT_SHADOWED`** (warning, register **50 → 51**) | New, and found by measuring rather than by reading the spec. |

**`REDIRECT_SHADOWED` exists because EMS has five of them.** 1,441 redirects: 108 where `from` is the page's own path (the leader of each page — harmless and expected, and excluded), 1,333 where the source topic is genuinely gone. Of those 1,333, **five have a `from` that still resolves on disk**, and all five differ from their target **only in case**:

```
_templates/Home.md                    -> _templates/home.md#home
_templates/Legal-and-Third-Party-Notices.md -> _templates/legal-and-third-party-notices.md#...
_templates/TIBCO-Documentation-and-Support-Services.md -> ...
c-and-cobol-reference/tibemsOAuth2Params-and-Environment-Variables.md -> ...
users-guide/DisasterRecovery.md       -> users-guide/disasterrecovery.md#disasterrecovery
```

On a case-sensitive host these are correct and necessary. On a case-insensitive one they are **301 loops**. The tool does not know which host it is publishing to, so it cannot call this an error — it names it, with the case-only ones distinguished in the message, and a human decides once per platform. Reframe cannot catch it either: its own audit resolves paths through `PurePosixPath` against a set it built, where the two names are distinct.

**Nothing else needs adding.** The sidecars land in `online-help/<segment>/`, which is not in `_INDEXED_DOC_CLASSES`, so `_check_index` never reports them as unlinked — checked, not assumed, and no `_GENERATED` change is needed.

##### What 20d will not do

**It will not rewrite redirect paths into published URLs.** `redirects.yml` ships as written, relative to the version root. The mapping from `online-help/<segment>/page.md` to a URL belongs to the publishing platform, and this tool has never been told it — baking a guess into a 301 map is a guess that becomes permanent the moment it is served. Naming the transform is 20e's conversation with whoever runs the platform, and it needs an answer before any redirect is published, not before this phase is built.

*Exit: `sync` publishes the merged tree for a doc set that opts in and refuses, loudly, for one that opts in without a current merge; a dangling redirect fails `validate`; EMS 10.5.1 publishes to a scratch target and validates with the five case-only redirects named and nothing else new; no product opts in on `master`.*

#### 20d Stage 7 integration — **Built & verified, 2026-09-24**

Every row of the plan above was built as written. Three files carry it: `reframe/policy.py` gains `publish`, `sync/distributor.py` gains `_source` and `_stale`, `validation/artifacts.py` gains `_check_redirects`. **Register 50 → 52**: `SYNC_MERGE_UNAVAILABLE` (warning, sync) and `REDIRECT_SHADOWED` (warning, validate).

**`publish` is the one policy field kept out of the currency digest**, and that is a deliberate exception to `policy.key`'s rule that the digest is the dataclass's own fields. In the digest, a sign-off commit re-merges the whole doc set for no change in output — and worse, the field's mere arrival changes the digest of *every* policy that does not name it, invalidating all 14 merged trees on this branch. The rule stays "every field counts"; `_NOT_OUTPUT` is the named exemption and it has to argue for itself.

**The import is lazy, and it has to be.** `reframe` reads `validation.references` for its fence-aware masking and `validation.artifacts` reads `sync.distributor` for `STAGING_SUFFIX`, so a module-level `from docushift.reframe import policy_for` in the distributor closes the loop and nothing in `docushift.validation` will load at all. Found by the suite, one import after writing it.

**Verified on the corpus, end to end.** EMS 10.5.1 opted in, synced to a scratch target, and validated:

| | |
|---|---|
| `sync` | 6 rows synced, 1,241 files, 39.4 MB, `Published merged (Stage 6b): tibco-enterprise-message-service.` The merged tree is what landed in `online-help/10-5-1/`, sidecars and all. |
| `validate` | 128 files, 2,919 references, **2,732 of 2,733 anchors matched**, **0 errors** |
| R5 at the gate | **zero `LINK_BROKEN` from `redirects.yml`** — all 1,441 redirect targets resolve to a published page *and* a published anchor |
| new | **5 `REDIRECT_SHADOWED`**, exactly the five predicted, each naming the 301-loop-on-a-case-insensitive-host condition |
| pre-existing | 1 `ANCHOR_MISSING`, `#Using`, an in-page link inside a page — §8's dangling-anchor baseline, not a redirect and not new |

**The refusal was verified on real data too**, and not only in tests. `tibco-datasynapse-gridserver-manager` 7.2.0 opted in: `online-help` published **nothing** and said why — *"publishes merged and the merge or the conversion recorded no source checksum, so neither can be vouched for"* — while its PDFs shipped normally, because documents come from the extracted tree and a merge has nothing to say about them. That doc set is one of the six DataSynapse versions with no `convert_source_checksum` at all, which is the inherited gap 20a pinned a test around; the safe direction turns out to be the one that matters here.

**`config/reframe.yaml` ships with `publish: false` and no product opting in**, which was the second thing decided. Both opt-ins above were temporary and are reverted.

Suite `1,449 passed, 2 skipped` (+18); `ruff` clean on `src`/`tests`.

**What 20d does not do.** No redirect path is rewritten into a published URL — see above, that belongs to the platform and needs an answer before 20e publishes anything. *(That premise was wrong and 20d.1 below corrects it: only the host belongs to the platform, and `published_url` settled what to do about a missing host in 6e.)* `sync` still has exactly one thing to say about Reframe, `_source`; nothing downstream branches on which tree it was handed. And no writer has signed anything off, which is 20e.

#### 20d.1 The published redirect map — **Planned, 2026-09-24**

20d shipped `redirects.yml` as written: `users-guide/foo.md → users-guide/bar.md#foo`, relative to the version root. I recorded that turning those into served URLs was blocked on the publishing platform. **That was wrong, and the codebase already says so.** `apirefs.published_url` solved this exact problem in 6e and wrote the answer into its docstring:

> An empty `base` yields the tree-rooted path with no scheme and no host. That is the shipped state and a deliberate choice: the path is the part this tool can derive, a link missing only its prefix is fixable by search-and-replace when the AEM host is known, and a link that was never emitted is not recoverable at all.

The host is unknown; **the path is not**, and the path is the part with the information in it. `publish_base_url` has been empty and supported since Phase 3.8, `sync` already composes cross-tree API links this way, and `catalog validate` already refuses a non-absolute base. So the transform is the one `published_url` performs, against `online-help` instead of `api-references`:

```
users-guide/bar.md#foo
  -> {base}/{tree}/{locale}/{slug}/online-help/{segment}/users-guide/bar.md#foo
  -> en-us-tib-ems-userdocs/en-us/tibco-enterprise-message-service/online-help/10-5-1/users-guide/bar.md#foo
     (the shipped state, base empty)
```

Both sides transform identically: `from` is the *pre-merge* published path of a topic that was in the same version folder, so it takes the same prefix.

##### Where it goes, and why not in the version folder

**A 301 map is consumed per site, not per version folder.** Rewriting the copied `redirects.yml` in place fails on its own terms and on a mechanical one:

- The mechanical one: `_identical` compares the published folder against its source file by file (`filecmp.cmp`, shallow). A file rewritten after the copy never matches its source, so **every version would re-copy on every run** and `CURRENT` would stop existing for merged products.
- The one that matters: a redirect map scoped to one version folder is not something a platform can serve. It needs every version's entries in one place, and it needs them to survive `sync --version 10.5.1`, which touches one folder out of six.

So it is written where `version.yml` is written and assembled the way `version.yml` is assembled — `{target}/{tree}/{locale}/{slug}/online-help/redirects.yml`, built by `finish_product` **from the doc-class directory after the copy**, not from the run's write list. That rule exists because a scoped run would otherwise rewrite a 38-entry drop-down down to one and report success; a redirect map has exactly the same hazard and exactly the same fix.

The per-version `redirects.yml` stays where it is. The two files have different jobs and the split is the same one `version.yml` makes against the version folders beside it: the version-root file is Reframe's **record** — relative, auditable, byte-identical across runs, and what `validate._check_redirects` resolves against the folder it sits in — and the doc-class file is the **published map**, which is cross-version and not resolvable that way.

##### Decisions

| decision | what gets built | why not the obvious alternative |
|---|---|---|
| **The transform** | One function in a new `sync/redirects.py`, mirroring `apirefs.published_url`: prefix, percent-encode the path, leave the fragment alone. Empty base yields the tree-rooted path. | Not a second composition of the same five segments. If the folder `sync` writes and the URL it emits are derived separately they disagree by a dashed segment, which is the bug `url_map`'s docstring records from `tps/6.0.0`. |
| **`.md` is kept** | The published path keeps the extension the published file has | The tool does not know whether AEM serves `page.md` or `page`. Every relative link inside every published page, and every `toc.yml` path, already carries `.md` — a redirect map that guessed differently would be the only artifact in the tree that disagreed with the others, and would be wrong in a way search-and-replace could not distinguish from correct. |
| **Assembly from the directory** | Every version folder under the doc-class that carries a `redirects.yml` contributes; versions this run did not touch keep their entries | `version.yml`'s first rule, for its reason. A scoped re-sync that silently dropped five versions' redirects would report success. |
| **Hand-added rows are carried through** | DocuShift owns an entry whose `from` sits under a version segment present on disk; anything else is copied verbatim in its original position. A file that will not parse is left alone and named. | `version.yml`'s second rule, and the same asymmetry: a stale row is a visible wart `validate` can name, and a deleted row is somebody's only copy. |
| **No new finding code for the empty base** | The run report names it once, beside the existing `Published merged (Stage 6b):` line | `PUBLISH_BASE_URL_UNSET` is registered against a different artifact and widening a registered code's meaning is worse than not having one. This is a property of the whole run, not of a product, and the shipped state is *expected* — a warning that fires on every run of a correctly configured tool stops being read, which is the argument 20a and 20c both made. |
| **`validate` checks it** | New doc-class-level check beside `check_dropdown`: every `to` resolves to a file under the target. `LINK_BROKEN`, the code `toc.yml` and the per-version map already use. | These are the entries actually served. The per-version check resolves relative paths against one folder; this one resolves tree-rooted paths against the target root, the resolution `links.py` already performs for every tree-rooted reference it counts (`links.py:194-203`). |
| **Register unchanged at 52** | No new codes | Every condition here is one of the three that already exist. |

*Exit: EMS 10.5.1 publishes and its doc-class `redirects.yml` carries 1,441 tree-rooted entries; a scoped re-sync of one version leaves the others' entries intact; a hand-added row survives; `validate` resolves every entry and reports nothing new; the per-version maps and the merged trees are byte-identical to 20d's.*

#### 20d.1 The published redirect map — **Built & verified, 2026-09-24**

Built as planned. One new module, `sync/redirects.py`, three call sites: `finish_product` writes the map, `cli._report_sync` names the base it was rendered against, `validation.artifacts.check_redirect_map` resolves it. **Register unchanged at 52** — every condition here is `LINK_BROKEN` or `ARTIFACT_UNPARSED`, both already registered against the same conditions in the same words.

**Verified on the corpus.** EMS opted in and synced to a scratch target, all six merged versions:

| | |
|---|---|
| the map | **8,639 rows** — 10-4-0: 1,457, 10-4-1: 1,442, 10-4-3: 1,429, 10-4-4: 1,429, 10-5-0: 1,441, 10-5-1: 1,441 |
| shape | every row tree-rooted (**0 carry a host**), every `to` ends `.md`, every `to` carries a fragment, sorted by `from`, `status: 301` throughout |
| `validate` | 768 files, 17,213 references, **0 errors** — all 8,639 published redirects resolve to a file the target holds |
| the check has teeth | one dangling row injected by hand → **1 error**, named with its `from`, its `to` and the folder |
| the scoped run | `sync --version 10.5.1` re-ran against the six-version map and produced a **byte-identical file**, all six segments intact. This is the bug the assembly rule exists for and it is the only one worth measuring here. |
| the hand-added row | a `legacy/ems-help.html → https://docs.example.com/ems` row added by hand survived a full re-sync in its own position; 8,640 rows out, 8,639 regenerated |
| currency | the re-sync after all of it reported **31 of 31 rows `Already current`** |

That last row is the one the placement decision turns on. Rewriting `redirects.yml` inside the copied version folder would have left it differing from its source, `_identical`'s shallow `filecmp` would have reported it stale, and **every merged version would have re-copied on every run** with `CURRENT` no longer reachable. The doc-class file is written beside `version.yml`, after the copies, and never touches a byte the copy placed: `reframed/…/10.5.1/redirects.yml` and the published `online-help/10-5-1/redirects.yml` are byte-identical.

**Two files, and the duplication is the point.** The version-root map is Reframe's record — relative, resolved by `_check_redirects` against the folder it sits in, byte-identical across runs. The doc-class map is the served 301 map — cross-version, prefixed, and not resolvable relative to anything. `validate` checks both and they do not overlap: the published map checks that every `to` names a file the target holds, and anchors are left to the per-version check, which has the folder index to check them against. Two checkers reporting one dangling anchor twice would make `report --code ANCHOR_MISSING` a count of how many views of the map exist.

**`relative_path` resolves a row whether or not it carries a host**, which is what let the validator stay ignorant of the config. `validate` takes no `ConfigManager` (§7.1) and so cannot know what `publish_base_url` was when the map was rendered — but it does not need to, because the tree name is the first path segment either way. A row that does not start at a published tree is somebody else's and is not resolved, the rule the page checker already applies to an absolute link.

The empty-base note goes in the run report (`8639 redirect(s) in 1 redirects.yml, tree-rooted (no publish_base_url set)`) and not into the register, because an empty base is the expected shipped state and a warning that fires on every correct run stops being read.

Suite `1,465 passed, 2 skipped` (+16); `ruff` clean on `src`/`tests`. `config/reframe.yaml` still opts nobody in.


#### 20e Pilot — **Planned, 2026-09-24**

The roadmap bullet is one line: *"One doc set, queue worked, explicit writer sign-off before redirects are published."* Preparing it found the gap 20d.1's closing note said was not there. `ReframePolicy` has four fields — `max_words`, `toc_schema`, `pin_layout_to`, `publish` — and **none of them is per-page**. A writer who reads the 18 rows and concludes "this page should have stayed granular" has exactly two places to put that: accept everything, or move the global cap and re-lay out all 124 pages to fix one. So 20e is not only a process phase; the queue is a question the config cannot currently answer.

##### What the 18 rows actually ask for

Measured, not assumed — this is the whole population a writer sees on the pilot doc set:

| flag | rows | the decision it puts to a writer | verb |
|---|---|---|---|
| `reference-list` | **13** | 20–60 topics of 60–90 words each, merged into one page. Right for a parameter reference; wrong if the topics are conceptually separate. | *stay granular* |
| `heterogeneous` | **5** | The page spans 2–4 TOC branches. | *split per branch* |
| `oversized` | **1** | `tibemsd-conf.md`, a single 3,533-word topic. R1.3 forbids splitting a topic body. | *none — nothing a writer can do* |
| `title-inherited`, `single-topic` | 17, 1 | Annotations. 20c measured that they hold for every page here and made them never queue alone. | *none* |

**Correcting the question I asked**: I proposed one `keep_separate` list described as covering both verbs, and the packer says it does not. The two are opposite operations on the same node. *Stay granular* means a subtree's topics never merge **with each other**; *split per branch* means a subtree is packed **as one unit** and never merges with its siblings — which is R1.1's existing top-level rule applied deeper. A single list cannot mean both, and guessing per entry from whether the path is a leaf or a directory would make the file's meaning depend on the shape of the tree it names.

So 20e builds **one** field, for the verb 13 of the 18 rows need, and records the other.

##### Decisions

| decision | what gets built | why not the obvious alternative |
|---|---|---|
| **`keep_separate` on `ReframePolicy`** ← approved | A per-product list of paths. A topic whose source path is, or sits under, a listed path **is never merged with anything**: it closes the page before it, and nothing joins onto it. One page per topic, which is Stage 6's own layout for exactly that subtree. | The name is the user's and it reads right. The semantics are the *granular* verb, because that is the 13-row case and because it is the conservative direction: un-merging is what a writer asks for when the merge was wrong, and the answer is always available — those pages already exist in `output/`. |
| **Paths are prefixes, matched against the source topic path** | `users-guide/monitor` matches `users-guide/monitor-messages.md` and everything under `users-guide/monitor/`. Compared as POSIX path parts, not string prefixes, so `users-guide/mon` does not match `users-guide/monitoring.md`. | The writer's evidence is `reframe.yml`'s `sections[].source` and the redirect map's `from`, both of which are source topic paths. Making the file name *output* pages instead would be a config keyed on the thing the config changes. |
| **`split_at` is not built** | Recorded here as the deferred second verb, with its measurement: **5 of 18 rows**, all `heterogeneous`. | No writer has asked for it, and the phase that finds out is this one. Building both now doubles the config surface on a guess; the 5 rows are still *reportable* today and a writer can name them in the sign-off commit. Naming a heterogeneous page's branches in `keep_separate` is a coarser answer than splitting it but never a wrong one — it returns those topics to what Stage 6 already publishes. |
| **It counts in the currency digest** | `keep_separate` is **not** added to `_NOT_OUTPUT`, and is normalized to a sorted tuple in `policy_for` | The opposite call to `publish`, and for the opposite reason: this field changes every byte downstream of it, so a tuned list that left trees reporting `current` is exactly the silent no-op `reframe_policy_key` exists to prevent. Sorted so that reordering the list is not a re-merge. |
| **An entry matching nothing is a warning** | `REFRAME_KEEP_SEPARATE_UNMATCHED`, warning, reframe. **Register 52 → 53.** | A typo in this file fails silently and looks exactly like "the writer's decision was applied." `scope.yaml` already warns for a rule matching no product, for the same reason. A warning and not an error: a path can legitimately stop matching when a version drops a topic, and failing the run would make a version's disappearance break the *other* versions' merge. |
| **The pilot is all six EMS versions** | No scope narrowing | §20.5 left this open. Layout is pinned to 10.5.1, so the six are diffable by construction and a decision taken on 10.5.1's queue is the decision that shaped all six. Publishing only the newest would leave five active versions serving unmerged topics under URLs the merge has already claimed in the 8,639-row map. |
| **Sign-off stays a human's commit** ← approved | `publish: false` unchanged; the runbook says what to read and what to write | The gate is the point of the phase. Nothing on this branch asserts a writer has read the pages, because nobody has. |

##### The runbook, and what 20e delivers without a writer

`docs/user-guide.md` gains the procedure: run `reframe`, open `review-queue.csv`, for each row open the page it names, and either accept it, or add its topics' source paths to `keep_separate` and re-run. Then one commit sets `publish: true` and says who signed off on what. Rolling back is the inverse commit plus a `sync`, and it is only cheap until the redirects are live — which is the sentence the whole gate exists for.

*Exit: `keep_separate` changes the layout of exactly the subtrees it names and nothing else; a listed path that matches no topic is named in the run report; two runs with the same list are byte-identical and a reordered list does not re-merge; EMS's 18-row queue is unchanged, because nobody has worked it yet; no product opts in.*

#### 20e Pilot — **Built, 2026-09-24**

`keep_separate` on `ReframePolicy`, a per-product list of source paths whose topics are never merged with anything. Built as planned, with one thing learned from the packer and one from the corpus.

**From the packer: the override has to close the run on both sides.** `_close_run` greedily extends a page until the cap or a directory change closes it, so marking a unit "separate" and closing *before* it is only half the rule — the last topic of a named subtree would then absorb whatever came next, which is the opposite of what a writer asking for granularity means. `_Unit` carries `separate`, and `_close_run` closes before *and* after it. The bottom-up collapse in `_subtree` gains the matching guard: a subtree containing a separated unit no longer collapses into one unit, which is what keeps `keep_separate` from being silently undone one level up.

**From the corpus: the file's matching rule had to get stricter than the config comment first claimed.** The draft comment promised `users-guide/monitor` would match `monitor.md`; segment matching does not do that, and the test said so. The rule shipped is the strict one — path as written, a file with its `.md`, a directory without one, nothing guessed from a bare stem — because a bare stem would name two different things depending on what happened to be on disk. Spellings of the *same* path are still normalized: Windows separators, surrounding whitespace, a leading `/`, a trailing `/`, and a leading `./`. That last one is the one a writer actually produces, by copying a path out of a file explorer, and left unnormalized it matches nothing and the merge it was meant to undo happens anyway.

**Verified against EMS.** `users-guide/command-listing.md` is the worst row in the queue — 60 topics, 2,978 words, the page a writer is most likely to reject. Listing its 60 sources:

| | baseline | with the override |
|---|---|---|
| 10.5.1 pages | 124 | **183** (+59: one page became sixty) |
| 10.5.1 queue | 18 | **17** (the row it answered is gone) |
| `redirects.yml` rows | 1,441 | **1,441** — `users-guide/create-route.md` now 301s to `create-route.md#create-route` instead of `command-listing.md#create-route` |
| files differing from baseline | — | 59 new pages, `command-listing.md` itself, the four regenerated root files, and **14 other pages — link retargeting only**, e.g. ``[`connect`](command-listing.md#connect)`` → ``[`connect`](connect.md#connect)`` |

Nothing else moved: the override re-laid out exactly the subtree it named. Reverting `config/reframe.yaml` and re-running returned the tree **byte-identical** to the baseline snapshot, and the queue to 109 rows across the six versions.

The digest behaved as the decision intended and as it costs: the field's mere arrival re-merged all six versions once (`Already current 0`), producing the same 124 pages and 18 queue rows as 20c's record — the layout did not change, only the key did. A second run reported `Already current 6`, and a run with the 60 paths shuffled and trailing whitespace added reported `Already current 6` as well, so reordering the list is free.

`REFRAME_KEEP_SEPARATE_UNMATCHED` fires on real data: two bad paths (`users-guide/no-such-topic.md`, and `users-guide/command-listing` without its `.md` — the exact strictness trap) produced one extra warning naming both, aggregated per version rather than one finding per path.

`split_at` remains unbuilt and measured at 5 of 18 rows. No product opts in: `config/reframe.yaml` ships `keep_separate: []` in `defaults` and `publish: false`, and the sign-off commit is a writer's.

Register 52 → 53. Suite `1,480 passed, 2 skipped` (+15); `ruff` clean on `src`/`tests`.

#### 20f CSH survives the merge — **Planned, 2026-09-24**

Reframe retargets `toc.yml` (R3) and emits `redirects.yml` (R5), and does neither for `csh.yml`. The file is not in `_REGENERATED`, so it falls through to `source.assets` — *everything that is not a topic* — and is `shutil.copy2`'d into the merged tree still naming the pre-merge topic paths. The requirements never mention CSH, and the reference corpus cannot show the gap: **EMS has no `csh.yml`**, which is why five phases of measuring against it found nothing.

##### What is actually broken, measured

Seven `csh.yml` exist under `output/`; two are in reframed Flare sets:

| set | identifiers | paths dead in the merged tree | frontmatter `csh:` ids surviving the merge |
|---|---|---|---|
| `tibco-runtime-agent@5.13.0` | 108 | 105 | **0 of 108**, on 0 of 71 pages |
| `tibco-administrator-enterprise-edition@5.13.0` | 46 | 46 | **0 of 46** |

Opting runtime-agent in and syncing to a scratch target: **`LINK_BROKEN` 108 rows, 108 errors.** So the gate does hold — neither product can publish merged today — but it holds three stages too late. Reframe's audit runs before the swap precisely so a merge this broken is never built, and this one is built, swapped, synced, and only then refused.

**The second half is worse than the first and is hidden behind it.** `validation/csh.py:159` emits `LINK_BROKEN` and `continue`s, so a dead path short-circuits the anchor and mirror checks. Fixing only the paths would surface 108 fresh `CSH_FRONTMATTER_MISMATCH` warnings, because `pages._frontmatter` builds each merged page's frontmatter from the `Page` and discards every absorbed topic's — including §9.5's `csh:` mirror. Both halves have to move together or the second is discovered by the next person to run `validate`.

**The content itself is intact, which is what makes this small.** Both facts measured on the merged trees: **108 of 108** CSH anchors are present in the merged pages (the `<a id="…">` markers travelled with the topic bodies), and **0 of 154** CSH targets are topics the packer failed to place. Nothing has to be recovered; the map has to be pointed at where its content went.

##### Decisions

| decision | what gets built | why not the obvious alternative |
|---|---|---|
| **`csh.yml` joins `_REGENERATED`** | A `reframe/csh.py` retarget pass, called beside `retarget(roots, located)` in `_write_navigation`, writing the map from `located` | Leaving it an asset is the bug. The seam already exists and names its own reason — *"written fresh by this stage, so a copy of the source's version would be stale"* — and `csh.yml` has been exactly that since 20b. |
| **The path half is replaced and the fragment half is kept** | `topic.md#ident` → `page.md#ident`, the identifier's own anchor unchanged | This is where CSH and `toc.yml` differ and the difference matters. `toc.yml` gets the *section* anchor because a TOC node **is** the section. A CSH identifier points at its own `<a id>` marker, which survived the merge and is the more precise landing point; overwriting it with the section anchor would move every Help button to the top of its section for no gain. `redirects.yml` carries the section anchor, so the redirect map is **not** the right source for this rewrite even though it is the obvious one. |
| **A fragment-less entry gets the section anchor** | Fall back to `located`'s anchor when the value has no `#` | Measured: 0 of 154 in the two Flare sets, but **18 of 108** in `tibco-runtime-agent@5.12.2`, so the shape is real in this corpus and merely not Flare's. A fragment-less value landing on a merged page with no anchor is a Help button that opens a twelve-section page at the top — the exact defect R5 exists to prevent. |
| **The merged page carries the union of its topics' `csh:` frontmatter** | `pages._frontmatter` gains the identifiers of every absorbed topic, sorted | §9.6's third rule is a round trip, and dropping the mirror breaks it for all 154. Sorted rather than in section order because the digest and C5 both read this file, and because `transforms/csh.py` is the other writer of this key and a stable order is what makes the two comparable. |
| **The audit gains one check, and no register code** | Every `csh.yml` value resolves to a page that was written and an anchor that exists in it; every identifier is on its page's frontmatter | Same shape as the existing `_navigation` check, run before the swap. No new code: `validation/csh.py` already argues in its own docstring that a CSH target is link integrity and that inventing `CSH_TARGET_MISSING` would mean two codes for one condition. A failure here is `REFRAME_SELF_CHECK_FAILED`, which is what every other audit failure is. **Register stays at 53.** |
| **A version with no `csh.yml` is untouched** | No file written | Five of the seven `csh.yml` are not Flare and will never reach this code, and EMS has none. Writing an empty map would put a file in the merged tree that is not in the converted one, which `validate` reads as a promise nobody made. |

##### What this does not do

It does not reconcile CSH across versions — §7.6's fourth rule, a dropped identifier visible only by comparing two versions, stays `diff`'s job and is unaffected: the merge changes where an identifier points, never whether it exists. And it does not touch the five non-Flare maps.

*Exit: `csh.yml` in a merged tree resolves entirely against that tree — every path a page that exists, every fragment an anchor in it, every identifier mirrored in its page's frontmatter; runtime-agent 5.13.0 and administrator 5.13.0 sync and validate with **0 errors** where they produce 108 and 46 today; the identifier set is unchanged in both, because retargeting may move a Help button and must never drop one; two runs byte-identical; EMS, which has no `csh.yml`, is byte-identical to its current merged tree.*

#### 20f CSH survives the merge — **Built, 2026-09-24**

`reframe/csh.py` plus a frontmatter mirror in `pages._frontmatter` and one audit check. `csh.yml` joins `_REGENERATED`, so it is no longer copied through as an asset. Register unchanged at **53**, as planned.

**One decision changed under implementation, and it was the plan's own wording that was wrong.** The plan said `load` should return `None` both for "no map" and for "a map that will not parse", *"because the two call for the same thing: copy nothing and write nothing."* They do not. With `csh.yml` in `_REGENERATED` it is no longer copied, so writing nothing **deletes every Help button from the merged tree with no record anywhere** — the exact class of silent-deletion failure `packer.carry` exists to prevent for untocked topics. The three available answers are all bad: writing nothing deletes, copying through republishes the stale paths this phase exists to fix, and a partial parse loses whichever identifiers were past the error. So an unreadable map now raises `csh.Unreadable` and **fails the version before anything is written**, which is the rule the driver's own docstring already states for `toc.yml`: *"an unrecognised TOC is a failure, not a skip."* Same file class, same argument. Verified: a truncated `csh.yml` gives `x tibco-runtime-agent@5.13.0: csh.yml does not parse`, one `REFRAME_SELF_CHECK_FAILED`, and no staging tree left behind.

**The fragment rule held as measured.** Only the path half is rewritten; the identifier keeps its own `<a id>` marker, which is a more precise landing point than the section heading and which survived the merge in all 154 cases. A fragment-less value falls back to the section anchor. The audit resolves anchors through `validation.references.anchors` — the same function `validate` uses three stages later, so the two cannot disagree about what an anchor is.

**Results, on the two Flare sets that have a map:**

| | before | after |
|---|---|---|
| runtime-agent 5.13.0, dead paths | 105 of 108 | **0** |
| administrator 5.13.0, dead paths | 46 of 46 | **0** |
| frontmatter `csh:` ids surviving | 0 of 154 | **154 of 154** |
| `sync` + `validate` on both | **154 errors** | **0 errors** |

The remaining findings on that target are 16 `REDIRECT_SHADOWED` and the one pre-existing `#Using` `ANCHOR_MISSING` from 20d — no `CSH_FRONTMATTER_MISMATCH`, which is the check that would have fired had only the paths been fixed. The identifier **set** is byte-for-byte the source map's in both products: §9.6's rule is that a Help button may move and may never disappear, and that is asserted on the set rather than on the values.

Determinism and blast radius both confirmed: two forced runs of runtime-agent are byte-identical, and EMS 10.5.1 — which has no `csh.yml` — is byte-identical to its 20e baseline, so a version without context-sensitive help gets no new file and no changed byte.

The audit check emits no new code. A failure is `REFRAME_SELF_CHECK_FAILED`, and the three conditions are reported separately because they fail for different reasons: a missing page means the retarget did not fire, a missing anchor means the marker did not survive the body copy, and a missing mirror entry means `_frontmatter` dropped it.

Suite `1,494 passed, 2 skipped` (+14); `ruff` clean on `src`/`tests`. No product opts in.

---

#### 20e Pilot sign-off — **Signed off, 2026-09-25**

The human half of 20e, which no amount of code could supply. EMS's 18-row review queue was read and **every page accepted as merged** — so `keep_separate` stays empty for this product, and the queue's answer turned out to be the one the tooling could not have assumed. `publish: true` is now set for `tibco-enterprise-message-service`, with the reasoning in the config file beside it rather than only in this record, because the config is what the next person reads.

Re-verified immediately before the commit, against the current code rather than 20d.1's run: `reframe` reports **Already current 6**, and a sync of all six merged versions to a scratch target validates at **768 files, 17,213 references, 0 errors, exit 0**, with 8,639 redirects in one doc-class map. The 37 warnings are 7 pre-existing `ANCHOR_MISSING` — the DocBook `a.indexterm` anchors carried since 20b, unrelated to the merge — and 30 `REDIRECT_SHADOWED`, 5 per version.

**Those 30 are the one thing the sign-off does not settle, and deliberately so.** They are the case-only rows 20d measured: a `from` differing from its `to` in letter case alone, which is a necessary redirect on a case-sensitive host and a 301 loop on a case-insensitive one. Which of those the AEM host is, is not a fact about the documentation, so the tool names them and the answer has to arrive from the platform. They are warnings and do not gate.

What this changes operationally: `sync` now reads `reframed/` for EMS, so the next run against a real target replaces 1,441 published topic URLs per version with 124 merged pages plus the 301 map that points the old URLs at the sections that replaced them. The rollback is the inverse commit plus a `sync`, and it is cheap only until those redirects are being served.

### Phase 21: A Passthrough Table Carries the Authoring Tool's Styling Into the Output — **Planned, 2026-09-28**

`tables.passthrough` is one line — `return str(table)` — and that line is the whole of the problem. Half the corpus's tables take the passthrough branch for a good reason (§5.5: GFM has no `rowspan`, no multi-block cell, and flattening one produces a plausible table that is wrong), but `markdown.rewrite` resolves only `img src` and `a href`/`id` before the subtree is dumped. Everything else Flare stamped on the markup ships verbatim.

**Measured on the published EMS tree** (`output/en-us-tib-ems`, 8,639 `.md` files):

| | |
|---|---:|
| files carrying a `class=` | **899** (10.4%) |
| `class` attributes total | **26,829** |
| `TableStyle-*` | **25,849** (96.3%) |
| everything else | **980** |

The `TableStyle-*` vocabulary is Flare's generated table-style naming — `TableStyle-Table-BodyE-Column1-Body1` and 30-odd siblings — and it is presentational by construction: it names a row band and a column position in a stylesheet that does not travel with the content. The remaining 980 are not that. `varname` (617), `MCXref xref` (184), `filepath`, `option`, `cite`, and the four `note*` variants carry semantics the plain text has already lost, and some of them are the raw material for a later phase that turns them into real Markdown constructs. **They are kept.**

Note what this is *not*. The `<table>` element also carries `border`, `cellpadding`, `cellspacing`, `width` and per-cell `valign`. Those are out of scope: unlike a class naming an absent stylesheet, they affect how a browser lays the table out today, and removing them is a rendering change rather than a cleanup. The predecessor stripped them; that is a separate decision and not this one.

There is a second-order finding worth recording because it explains the predecessor's output and will otherwise be rediscovered. `html-to-md`'s `_clean_table_html` iterates `table.find_all(True)`, which in BeautifulSoup returns **descendants only, never the element itself**. Its passthrough tables therefore have clean cells and a fully-attributed `<table>` tag — 530 `ebx_definitionList` classes survive on EMS's neighbour tree, all 530 on the `<table>`, none on any descendant. DocuShift's bug is the wider one (it scrubs nothing), but the shape of the predecessor's is the reason to write the fix as a whole-subtree walk that includes the root, and to have a test that would fail on the off-by-one.

#### Decisions

| decision | what gets built | why not the obvious alternative |
|---|---|---|
| **Scrubbed in `tables.passthrough`, not in `markdown.rewrite`** | `passthrough` walks `[table, *table.find_all(True)]` and drops non-semantic classes before rendering | `rewrite` is `markdown.py`'s and WebWorks calls it separately (`webworks.py:304`); putting the scrub in the shared choke point means every engine that passes a table through gets it, including the next one. Mutation in place is already sanctioned here — the subtree is discarded as soon as the topic renders (`rewrite`'s docstring). |
| **A keep-list, not a strip-list** | Classes are removed unless listed; the list is the semantic vocabulary above | A `TableStyle-*` prefix rule is a rule about *one* generator's naming. DITA, DocBook and WebWorks each have their own noise, and a strip-list would need extending per engine while silently passing anything unforeseen. A keep-list fails closed and is auditable in one place. |
| **The keep-list is a module constant, not config** | `tables.SEMANTIC_CLASSES` | `reframe.yaml` is editorial policy a writer tunes. This is a fact about the source vocabulary, changes only when an engine is added, and belongs beside the code that reads it — the same argument `SPAN_TO_TAG` already makes in `webworks.py`. |
| **An emptied `class` is removed, not left empty** | `class=""` never appears in the output | An empty attribute is the one shape that is neither the old output nor the clean one, and it would defeat a grep written against either. |
| **Layout attributes untouched** | `border`, `cellpadding`, `cellspacing`, `width`, `valign` all survive | They change rendering. This phase is a cleanup with no visible effect; bundling a rendering change into it would make any regression ambiguous. |
| **No new finding code** | Nothing is reported | Nothing here can fail or be ambiguous. A counter on a cleanup that always succeeds is a line nobody reads. |

#### What this costs downstream

The output of `convert` changes for every version with a passthrough table, so EMS must be re-converted, re-reframed and re-synced. **No path and no anchor changes**, so `toc.yml`, `csh.yml`, `redirects.yml` and the 8,639-row published map are all byte-identical across the change — which is the assertion worth making explicitly, because it is what makes this safe to run against a signed-off pilot. The merged pages themselves change in exactly one respect and `reframe` will report all six versions stale, which is correct and expected.

*Exit: EMS re-converts with **0** `TableStyle-*` classes and **980** semantic classes surviving in the same 899 files; `toc.yml`, `csh.yml` and `redirects.yml` byte-identical before and after; `validate` reports no new findings; a unit test pins the root-element case that the predecessor's off-by-one would fail.*

#### Phase 21 — **Built & verified, 2026-09-28**

Built as planned, in two files. `tables.scrub` walks `[table, *table.find_all(True)]` and `tables.passthrough` calls it; `webworks.KEEP_CLASSES` widens the keep-list with `SPAN_TO_TAG`'s keys, which the plan did not anticipate and which matters: in that engine the class name *is* the markup — a span is code by virtue of being `class="Code"` — and the passthrough branch is the one place that never got rewritten into `<code>`. Dropping them would have made it the only part of the corpus where that distinction was gone for good.

**Verified by re-converting EMS 10.5.1 to a scratch tree and diffing against the published one:**

| | before | after |
|---|---:|---:|
| `TableStyle-*` classes | **4,272** | **0** |
| semantic classes | 168 | **168** |
| `toc.yml` | — | byte-identical |
| `metadata.yml` | — | byte-identical |
| `.md` files differing | — | 149 |
| **files differing by anything other than a `class` attribute** | — | **0 of 1,441** |

That last row is the one that matters: strip `class="…"` from both trees and all 1,441 pages compare equal. No path moved and no anchor changed, so nothing the *converter* produces is affected beyond the classes.

**But "the merge layout is unaffected" — claimed here when this note was first written — is false, and the corpus rebuild showed it.** The packer sizes pages by word count, and a scrubbed `class="TableStyle-…"` is words. Re-converting all six EMS versions and re-merging moved two of them: **749 → 747 pages** (10.4.1 126 → 125, 10.4.0 129 → 128, the other four unchanged) and the review queue **109 → 115 rows**. Redirect coverage is unchanged at **8,613 rows**, so no topic gained or lost a redirect; only two page boundaries moved, and `REDIRECT_SHADOWED` went 30 → 32 as two more leaders became case-only self-redirects. `validate` is **0 errors** either way. The claim was wrong because it reasoned about the converter's output in isolation and the packer reads that output; the corrected statement is that the *content* is unaffected and the *layout* shifts by two pages.

**Open, found here and not fixed: a converter change does not invalidate a merged tree.** `reframe`'s currency check keys on `convert_source_checksum` — the *extracted* package — plus the policy key, so after re-converting with the scrub in place all six versions reported `Already current` while holding pre-scrub HTML. `--force` is the workaround and it is not discoverable. The fix is to key on something the converter's own output moves; it is not in this phase because it changes when every product re-merges, not just EMS.

The surviving 168 are exactly the declared vocabulary — `varname` 103, `MCXref xref` 35, `tabletitle` 10, `filepath` 7, and single figures of `option`, `noteHeadInTable`, `autonumber`, `note`, `noteTip`, `noteWarning`, `groupOfURLs`.

This version has no `csh.yml` to compare — EMS is the empty-alias-file case (`has_csh: true`, `csh_names: 0`, §5.3.1), so the byte-identity claim for the help map is carried by the other five versions at the corpus rebuild rather than by this one.

Six new tests, one per decision, including the root-element case the predecessor's off-by-one would fail. Suite **1,500 passed, 2 skipped**.

---

### Phase 22: The Redirect Map Does Not Start Where the Reader Does — **Planned, 2026-09-28**

20d.1 shipped a served 301 map and it is correct about everything except its starting point. Its `from` is the **pre-merge published path in the new tree** — `…/online-help/10-5-1/users-guide/foo.md`. That URL has never been served. It is the address the topic *would* have had in the new structure had it not been merged, which makes the map a faithful record of what Reframe did and useless for the migration cutover, because the URLs that are about to stop working are on `docs.tibco.com` and are not in the file.

What is missing is one join, and the pieces are all on disk:

- **`state.db`'s `output_map`** — `source → output` per version, written by `converter/driver.py:332`. For EMS 10.5.1: 1,441 rows, `tibco-enterprise-message-service-10-5-1/html/_shared/about-this-product.htm → _shared/about-this-product.md`.
- **Reframe's per-version `redirects.yml`** — `output → page.md#anchor`, 1,441 rows for the same version. The two counts agreeing is not a coincidence and is worth asserting: every converted topic has exactly one home after the merge.
- **`sync/redirects.published()`** — the version-root-relative path to the served URL, already written and already used.

**The origin URL, verified rather than assumed.** The live shape is `https://docs.tibco.com/pub/{folder_path}/doc/{source path, package-root segment removed}`, where `folder_path` is the directory part of `zip_url` under `/pub/` (`ems/10.5.1` for EMS 10.5.1). Checked against the live site on 2026-09-28: `https://docs.tibco.com/pub/ems/10.5.1/doc/html/_shared/about-this-product.htm` serves *About this Product* for EMS 10.5.1, which is the topic that row names.

**And it does not generalise, which is the whole design constraint.** Grouping `output_map` by the first two segments of its source paths across the converted catalog returns four distinct layouts:

| shape | example product |
|---|---|
| `<package-root>/html/…` | `tibco-enterprise-message-service`, `tibco-streaming`, `tibco-administrator-enterprise-edition` |
| `html/…` (no package root) | `spotfire-data-science-author`, `tibco-designer-add-in-for-tibco-business-studio` |
| `doc/html/…` | `tibco-datasynapse-gridserver-logviewer` |
| `<package-root>/designerhelp/…` | `tibco-runtime-agent` |

One rule applied to all four emits confident, wrong URLs for three of them. A wrong 301 is strictly worse than a missing one: the reader lands on a dead page and the map records success. So the origin template is **declared and verified per product, never inferred**.

#### Where the two files go

Per version, plus an assembled one per product — the same split `redirects.yml` already makes, for the same reasons, and with the same hazard to avoid.

- **Per version: `301.yml` at the version root of the *source* tree** (`reframed/…/10.5.1/` for a product that publishes merged, `output/…` otherwise), written by Reframe beside the `redirects.yml` it already writes at `driver.py:503`. It is then copied into the published tree like any other file. **It must not be written into the published folder after the copy** — that is 20d.1's measured trap: `_identical`'s shallow `filecmp` would see the version folder differ from its source and every merged version would re-copy on every run, with `CURRENT` no longer reachable.
- **Per product: `301.yml` at doc-class level**, beside `version.yml` and `redirects.yml`, assembled by `finish_product` **from the doc-class directory after the copy** — not from the run's write list, so `sync --version 10.5.1` cannot quietly publish a map that redirects one version out of six and reports success.

The coordinate systems mirror `redirects.yml` exactly: the version-root file's `to` is version-root-relative and auditable against the folder it sits in; the doc-class file's `to` is the served URL, tree-rooted when `publish_base_url` is empty. The `from` is an absolute `docs.tibco.com` URL in **both**, because unlike the `to` side it is not a path this tool invented — it is a live address, and truncating it to a path would lose the one thing that makes the row a cutover instruction.

#### Decisions

| decision | what gets built | why not the obvious alternative |
|---|---|---|
| **Origin templates are declared, not inferred** | New `config/origin-urls.yaml`: per product, the verified live URL template and the number of leading source segments to drop. EMS filled in and verified; everything else absent. | The four-layout measurement above. Inference would be right for EMS and silently wrong for Runtime Agent, and the failure is invisible until a reader hits it. This is `scope.yaml`'s shape — a YAML rule file naming products explicitly — for `scope.yaml`'s reason. |
| **A version with no declared template is skipped and named** | No `301.yml` is written; the run report names the version | The user's call, and the right one. A missing redirect is a gap someone can see and fill; a guessed one is a 404 with a success line beside it. |
| **New code `ORIGIN_TEMPLATE_UNDECLARED`, warning** | Register **52 → 53** | This is a genuinely new condition — not a broken link, not an unparsed artifact — and 20d.1's argument against widening a registered code's meaning applies in reverse here. A warning, not an error: an undeclared product is the expected state for all but one product today. |
| **Every converted topic gets a row, not only merged ones** | 1,441 rows per EMS version | The whole folder structure changed, so every live URL is about to break, merged or not. A map covering only merge-induced moves would leave the majority of the 404s unredirected — and that is the map that already exists. |
| **The row count is asserted against `output_map`** | A version whose `301.yml` row count differs from its `output_map` count fails the version | The join has three inputs and a silent drop in any of them produces a short map that looks fine. This is the one invariant that catches it, and it is free. |
| **`.md` is kept on the `to` side** | As 20d.1 | Unchanged argument: every relative link and every `toc.yml` path already carries it, and a map that guessed otherwise would be the only artifact in the tree that disagreed. |
| **`status: 301` throughout** | As Reframe's map | The file is named for it. A 302 is a different decision and nobody has asked for one. |
| **Hand-added rows survive; an unparsable file is left alone and named** | `version.yml`'s rules, via the existing `redirects.parse`/`merge` | Third time these rules apply to an assembled map. Reusing them rather than restating them is what keeps the three files behaving the same way under a scoped run. |
| **`validate` checks the `to` side only** | Every `to` in a doc-class `301.yml` resolves to a file under the target — `LINK_BROKEN`, via the existing `relative_path` | The `from` side is a URL on a site this tool does not own and cannot resolve offline. Checking it would mean a network call inside `validate`, which takes no config and makes none. |

#### Scope of this phase

EMS only — six versions, ~8,639 rows. It is the pilot, it is the one product whose origin URLs are verified against the live site, and it is the product whose merge has already been signed off, which makes it the one where the cutover is real. The other products gain nothing until someone confirms their URL shape, and `ORIGIN_TEMPLATE_UNDECLARED` is how they ask.

*Exit: each of EMS's six merged versions carries a `301.yml` whose row count equals its `output_map` count; the doc-class `301.yml` carries all six versions' rows, sorted, every `from` an absolute `docs.tibco.com` URL and every `to` tree-rooted; a scoped `sync --version 10.5.1` leaves the other five versions' rows byte-identical; a hand-added row survives; `validate` resolves every `to` with no new findings; a sample of origin URLs is confirmed live by hand before the map is called done; every other converted product reports `ORIGIN_TEMPLATE_UNDECLARED` and writes no file.*

### Phase 22 — **Built & verified, 2026-09-28**

`config/origin-urls.yaml` declares one product. `origins.py` turns a declaration plus a version's `zip_url` plus `state.db`'s `output_map` into rows; `reframe/driver._write_origins` writes `301.yml` into the **staging** tree so the copy's shallow `filecmp` check stays true; `sync/distributor._assemble_map` publishes the doc-class view after the copy. `sync/redirects` grew three parameters — `file_name`, `prefix_keys`, `merge(key=)` — rather than a second copy of the four rules.

**The asymmetry that is the whole phase.** `redirects.yml` prefixes both sides and reads entitlement off `from`, because both sides are ours. `301.yml` prefixes **only `to`** and reads entitlement off **`to`**, because `from` is an address on `docs.tibco.com`. Getting either wrong is silent: prefixing `from` buries a live host mid-path, and owning on `from` matches no prefix, regenerates nothing, and appends a second copy of every row on every run while every other assertion still passes. Both are pinned by a test.

| Exit criterion | Measured |
|---|---|
| Row count equals `output_map` per version | 1452 / 1437 / 1425 / 1425 / 1437 / 1437 — equal in all six, no dropped paths reported |
| Doc-class map carries all six versions | 8,613 rows; `{10-4-0: 1452, 10-4-1: 1437, 10-4-3: 1425, 10-4-4: 1425, 10-5-0: 1437, 10-5-1: 1437}`; every `from` an absolute `docs.tibco.com` URL |
| Every `to` resolves | 0 missing, checked in the reframed tree and again in the synced target |
| Scoped run leaves the rest alone | `sync --version 10.5.1` → doc-class `301.yml` **byte-identical** |
| Hand-added row survives | 8,613 → 8,614, the 302 carried through verbatim |
| `validate` | 0 errors; 7 `ANCHOR_MISSING` + 32 `REDIRECT_SHADOWED`, all pre-existing per-version findings, none from `301.yml` (30 before Phase 21's rebuild moved two page boundaries) |
| Origin URLs are live | `users-guide/connection-and-memor.htm` → "Connection and Memory Parameters"; `c-and-cobol-reference/tibemsmsgproducer-se.htm` → "tibemsMsgProducer_SetDeliveryMode"; `10.4.0/users-guide/export6.htm` → "Export" |
| Undeclared products | `tibco-runtime-agent@5.13.0` reframed, reported `ORIGIN_TEMPLATE_UNDECLARED`, wrote no `301.yml` |

**Deviations from the plan.** Two, both small. The `validate` check is `check_redirect_map` with a `file_name` argument rather than a new function — one checker, one message, and the `301.yml` name substituted into it, because the question and the code are identical. And the sync report line now says "N published map(s)" instead of "N redirects.yml": the counter always covered both files, and naming one of them was the kind of wrong that reads as right.

One observation worth recording: a **leader** topic gets `page.md#its-own-anchor`, not a bare `page.md`. That is `redirects.yml`'s existing shape and its reason — the reader arrives at the section rather than the top of a merged page — and it is why `REDIRECT_SHADOWED` fires at all.

---

### Phase 23: The Classes Went and Everything Else Stayed — **Planned, 2026-09-28**

Phase 21 scrubbed `class` and said so explicitly: layout attributes "change rendering", bundling the two would make any regression ambiguous about which caused it, and so `border`, `cellpadding`, `cellspacing`, `width` and `valign` were left alone. That was the right call for Phase 21 and it was an argument about **sequencing**, not a permanent boundary. A writer reading the output found the rest still there — *"I can still see cellspacing, style, and title attribute"* — and the measurement behind that observation turns out to be worse than "some layout survived".

**Measured on the published EMS tree, 887 files carrying a table:**

| what survives a Phase 21 passthrough | count | what it is |
|---|---:|---|
| `style="mc-table-style: url('../Resources/TableStyles/*.css')"` | **812** | a reference to a folder that **does not exist anywhere under `output/`** |
| `<col title="C1">` | **1,696** (806 files) | not a label, a **tooltip**: hover a column border and the reader is shown "C1" |
| `data-mc-conditions`, `data-mc-autonum`, stray `xmlns`, `madcap:` href | **201** | authoring-tool plumbing with no meaning outside Flare |
| `cellspacing`, `col style="width: 169px"`, `td style="padding"`, `valign`, `align` | **1,386** | genuine layout |

The first three rows are not a rendering decision at all — they are the same category as `TableStyle-*`, and Phase 21 simply did not look past `class`. The `mc-table-style` URL is the sharpest case: it is a dead link that **the link checker cannot see**, because the checker reads `href` and `src` and this is inside a `style`. 812 dangling references passing validation.

The fourth row is a real rendering decision, and the writer made it: **the layout goes too**, and the site's own stylesheet sizes these tables. That is better on a narrow screen — a `width="100%"` table with pixel columns does not reflow — and occasionally worse where a pixel width was holding a command name on one line. It is a visible change and is not claimed to be anything else.

#### Decisions

| decision | what gets built | why not the obvious alternative |
|---|---|---|
| **A keep-list of attributes, mirroring the class keep-list** | `tables.STRUCTURAL_ATTRS`; `scrub` gains an `attrs` parameter beside `keep` | Same argument as `SEMANTIC_CLASSES` and it has already been proved by this phase: a strip-list written against Flare's vocabulary is exactly what let `data-mc-*` and `mc-table-style` through. What is kept is structure and content — what a cell spans, where a link points, what an anchor is called — never how any of it looks. |
| **`title` is kept on `a`, `abbr`, `area`, `img`, `iframe` and dropped everywhere else** | `tables.TITLE_BEARERS` | A single rule about the attribute cannot work: on an `<a>` a human wrote it and it is content; on a `<col>` the generator wrote it and it renders as "C1" under the reader's cursor. 1,696 of the latter against a handful of the former. |
| **An emptied `<col>` is removed, and a `<colgroup>` emptied by that goes with it** | two ordered passes at the end of `scrub` | Once the widths are gone a `<col/>` carries nothing. Keeping 1,696 empty ones is keeping the skeleton of the decision rather than the decision. `span` still counts as content, so `<col span="2">` survives. |
| **No new finding code** | nothing is reported | Same as Phase 21: nothing here can fail. The 812 dead stylesheet URLs are *removed*, not reported — reporting a reference that nothing should have emitted is a queue nobody can action. |
| **`webworks.py` is not touched** | it passes `keep` positionally and picks up the default `attrs` | Its override is about class vocabulary (`SPAN_TO_TAG`), which is orthogonal. An engine that needs a different attribute set can pass one. |

#### What this costs downstream

`convert` output changes for every version with a passthrough table, so EMS re-converts, re-reframes and re-syncs — and `reframe` must be `--force`d, for the reason recorded as an Open under Phase 21. **Expect the page count and review queue to move again**: removing attribute text changes the packer's word counts exactly as Phase 21's class removal did.

*Exit: `mc-table-style`, `<col title>`, `cellspacing`, `data-mc-*` and `xmlns` all at **0** in the published tree; semantic classes and every structural attribute (`rowspan`, `colspan`, `scope`, `href`, `id`, `span`) unchanged in count; `validate` reports no new findings; tests pin the generated-vs-authored `title` split and the emptied-`<col>` removal.*

#### Phase 23 — **Built & verified, 2026-09-28**

One file. `tables.STRUCTURAL_ATTRS` and `tables.TITLE_BEARERS` are new; `scrub` gained an `attrs` parameter and two ordered passes at the end (a `<colgroup>` is only empty once its `<col>` children have gone, and `find_all` hands back the parent first); `passthrough` passes it through. `webworks.py` was not touched — it passes `keep` positionally and picks up the default.

**Measured on the rebuilt EMS tree, 8,639 published files:**

| | before | after |
|---|---:|---:|
| `mc-table-style` | 812 files | **0** |
| `<col …title=…>` | 1,696 in 806 files | **0** |
| `cellspacing` | 830 files | **0** |
| `data-mc-*` | 77 | **0** |
| `xmlns` | 120 | **0** |
| `valign`, `cellpadding`, `bgcolor` | present | **0** |
| `class="varname"` | 617 | **617** |
| `class="MCXref xref"` | 184 | **184** |
| `rowspan` / `scope` | 18 / 24 | **18 / 24** |
| `<table>` elements | 1,050 | **1,050** |

The two semantic counts are the Phase 21 baseline unchanged, which is the row that says this removed presentation and nothing else. No table was lost.

**Pipeline, all six versions re-converted (`--force`), re-merged (`--force`, per Phase 21's Open), re-synced and validated:**

| | |
|---|---|
| Pages | **747**, the same total as after Phase 21, redistributed: 10.5.1 and 10.5.0 125 → **124**, 10.4.4 and 10.4.3 → **123**, 10.4.1 **125**, 10.4.0 **128**. The packer sizes by word count and attribute text is words, exactly as Phase 21 found. |
| Review queue | **115**, unchanged in total |
| Redirects | **17,252 in 2 published maps** — 8,639 + 8,613, unchanged, so no topic gained or lost a redirect |
| `validate` | **0 errors**; 7 `ANCHOR_MISSING` + 32 `REDIRECT_SHADOWED`, identical to the Phase 22 baseline |
| Suite | **1,544 passed, 2 skipped**, `ruff` clean |

**One thing the measurement turned up that is not this phase's doing.** `colspan` is **0** in the output while the 10.5.1 source carries 56 genuine `colspan="2"`/`"3"`. It is in the keep-list and a test pins it; the reason it never arrives is upstream — a full-width row like `<td colspan="2"><b>Headings specific to file-based stores</b></td>` is lifted out as a bold paragraph and the table split in two, which is the right rendering and predates Phase 21. Recorded because "0 colspan in the output" reads like a bug in this change and is not one.

---

### Phase 24: The Row Stops One Stage Short — **Planned, 2026-09-28**

`versions.csv` records a before and an after, and §3.9 says so in as many words: "the before/after pair to read across a row is `doc_files` -> `out_files`". That sentence was true when `convert` was the last stage that changed the shape of the tree. It has not been true since Phase 20. The merge is the stage that does the compression, and **its result is recorded nowhere that survives the run**.

**What a row says today, for the pilot:**

| version | `_doc_files` | `_md_files` | `_out_files` | after reframe |
|---|---:|---:|---:|---|
| 10.5.1 | 2,268 | 1,441 | 1,476 | *not recorded* |
| 10.5.0 | 2,268 | 1,441 | 1,476 | *not recorded* |
| 10.4.4 | 2,247 | 1,429 | 1,463 | *not recorded* |
| 10.4.3 | 2,247 | 1,429 | 1,463 | *not recorded* |
| 10.4.1 | 2,258 | 1,442 | 1,475 | *not recorded* |
| 10.4.0 | 2,276 | 1,457 | 1,494 | *not recorded* |

The last column exists on disk — 10.5.1's merged tree holds **124** Markdown files in **163** files total, 10.4.0's **128** in **169** — and it exists in `ReframeStats` for the length of one process. `_report_reframe` prints "`{topics} topic(s) read into {pages} page(s)`" and then the numbers are gone. Worse, they are gone *selectively*: the `CURRENT` branch returns `topics=0, pages=0` without reading anything, so the second run of `reframe` over an unchanged tree prints **nothing at all** where the first printed 747 pages. The one stage whose entire purpose is a ratio is the one stage that cannot tell you the ratio on a re-run.

#### Decisions

| decision | what gets built | why not the obvious alternative |
|---|---|---|
| **Two new columns, `_reframed_md_files` and `_reframed_files`** | a third inventory block in `catalog._VERSION_COLUMNS`, `ProductVersion`, and `record_reframe_inventory` / `clear_reframe_inventory` | The pair mirrors `_md_files`/`_out_files` for the same reason that pair exists: the Markdown count is the thing that changed shape, and the total is what the folder actually holds. A single column would force every reader to guess which one it was. Kept apart from the Stage 5 block for the reason that block is kept apart from Stage 4's — discarding a merged tree must not blank a conversion measurement that is still true. |
| **Walked, not derived from `len(built)`** | one `rglob` after the swap, the same shape as `converter._measure_output` | `len(built)` is 124 and the merged tree holds 163 files: `toc.yml`, `reframe.yml`, `redirects.yml`, `301.yml`, `review-queue.csv`, `csh.yml` and the copied assets. The artifact set is *conditional* — `csh.yml` only for a non-empty map, `301.yml` only for a declared origin template — which is precisely the arithmetic that was already found wrong once at Stage 5. A walk cannot be wrong about it. |
| **The walk cross-checks the counter** | `_reframed_md_files != len(built)` records `REFRAME_SELF_CHECK_FAILED` | The measured corpus says they agree exactly (128/128, 124/124) — every merged page is one `.md` and nothing else writes one. That is a real invariant, so a disagreement means a page write landed somewhere unintended, which is the failure Stage 5's equivalent check was added to catch. Free, since the walk is happening anyway. |
| **`CURRENT` backfills blank columns** | the `CURRENT` branch reads the two columns and measures the tree if either is blank | Exactly what `convert` already does at `driver.py:230`, and for the same reason: a version that was merged before these columns existed is as real as one merged today, and leaving it blank forever makes "never reframed" and "reframed before Phase 24" the same row. |
| **Two percentages, never one** | the reframe summary prints both `_md_files → _reframed_md_files` and `_doc_files → _reframed_md_files` | They measure different things and a single number would silently be whichever the reader assumed. 1,441 → 124 is **91.4%**, and it is the merge's own work. 2,268 → 124 is **94.5%**, and most of the gap between them is `convert` skipping files rather than anything being compressed — `_doc_files` counts source HTML the converter never had to emit. Publishing only the second would credit the merge with the converter's skips; publishing only the first would hide the end-to-end figure that is the actual question. |
| **The summary, not `status`** | `_report_reframe` gains the funnel line; `Funnel` is untouched | `status`'s funnel counts *versions* at each step, and every row in it is a version count. Putting a file count in it would make one row mean something different from all the others. |

#### What this does not do

It does not backfill history. The columns fill as `reframe` runs, and a version that is `CURRENT` fills on the next invocation of the command — no migration pass, no re-merge. It also does not touch `_api_files`, which stays absent at this end for the reason §3.9 already gives: the merge does not read API trees any more than the converter does.

*Exit: all six EMS rows carry `_reframed_md_files`/`_reframed_files`; `reframe` over an unchanged tree prints the same funnel as the run that built it; the walked Markdown count equals `len(built)` on every version; a re-run with no changes leaves `versions.csv` byte-identical; tests pin the `CURRENT` backfill, the `clear_` symmetry, and the two percentages against the measured 1,441 → 124.*

#### Phase 24 — **Built & verified, 2026-09-28**

Four files plus tests. `models.ProductVersion` gains the two optional ints; `catalog` gains the columns, `_REFRAME_COLUMNS`, `record_reframe_inventory`, `clear_reframe_inventory` and the third `_inventory_notes` check; `reframe/driver` gains `_measure_merged`, the two `ReframeResult` fields, the two `ReframeStats` properties, the `CURRENT` backfill and the page-count cross-check; `cli` gains `_report_reframe_funnel` and `_pct`, and `_report_reframe` takes the manager.

**Measured against the six EMS versions, on the `CURRENT` path — the case that previously printed nothing at all:**

```
Files: 13564 source doc -> 8639 converted -> 747 merged
       (91.4% fewer at the merge, 94.5% end to end);
       979 file(s) standing in the measured merged tree(s).
```

| version | `_doc_files` | `_md_files` | `_reframed_md_files` | `_reframed_files` |
|---|---:|---:|---:|---:|
| 10.5.1 / 10.5.0 | 2,268 | 1,441 | 124 | 163 |
| 10.4.4 / 10.4.3 | 2,247 | 1,429 | 123 | 161 |
| 10.4.1 | 2,258 | 1,442 | 125 | 162 |
| 10.4.0 | 2,276 | 1,457 | 128 | 169 |
| **total** | **13,564** | **8,639** | **747** | **979** |

The page totals match Phase 23's exactly — 124/124/123/123/125/128 = 747 — which is the row that says this measured the merge rather than changing it. The second invocation printed the identical funnel from the columns without walking a tree. `versions.csv` grew two cells on every row and changed nothing else: of 5,182 modified lines, seven carry a value and the rest gained `,,`.

**Suite: 1,564 passed, 2 skipped** (20 new), `ruff` clean.

**One thing worth recording about the cross-check.** `_reframed_md_files == pages` held on all six versions, which is what made it worth adding as a finding rather than a comment — the invariant is real and cheap, and it is Stage 5's `OUTPUT_COUNT_MISMATCH` one stage later. It has not fired.

---

## 2. Validation & Testing Criteria
- **Catalog Merge Fidelity**: 100% preservation of manual edits and toggle states when fetching updates — *without* requiring the user to have flagged them.
- **CSV Round-Trip Fidelity**: A load-then-save cycle with no changes produces a byte-identical file (stable sort, fixed columns, normalized booleans/dates). No diff churn on repeat fetches.
- **Active vs Archive Segregation**: Archived versions are never auto-converted unless explicitly flagged.
- **Scope Exclusion Durability**: No version of an out-of-scope product is ever downloaded, extracted, converted or laid out — including versions first discovered after the exclusion was written. Excluded products remain fully catalogued and counted, and no slug is matched by anything looser than string equality.
- **Retirement Durability**: No version marked `Retired` by the active end-of-support report is ever downloaded, extracted, converted or laid out — including versions first discovered after the report landed. Absence from the report never retires anything, no product name is matched by anything looser than an exact slug or a reviewed alias, and a product left with no convertible version is named in the run report rather than quietly disappearing.
- **Package Source Transparency**: A manually supplied ZIP converts through exactly the same path as a downloaded one — no downstream stage branches on provenance, and no machine-local path appears in either CSV.
- **Unit Test Coverage**: >90% coverage on core transforms, engines, catalog, and state management.
- **Link & Asset Integrity**: Zero broken relative links or missing referenced assets in converted output. This is a structural guarantee, not a target: a relative asset link exists if and only if the asset was copied, because one resolution at emit time produces both (`design.md` invariant 13). Every reference that did not resolve is counted and named in the run report — the failure mode being designed out is the predecessor's, which loses 31.2% of its image links and logs nothing.
- **CSH Fidelity**: Every identifier in the source help map is either resolved in `csh.yml` or **named in the run report** — none is silently dropped. *(Reworded 2026-09-10: `csh.yml` is now a flat map with no `unresolved` key, so the report carries what the file no longer can. The guarantee is unchanged; only its location moved.)* Identifier text round-trips byte-exactly as a string, including case and digit-only values. The map is keyed on the identifier, the one key the corpus shows to be unique within a source.
- **Reporting Completeness**: Every finding code emitted anywhere in the tool is present in the §7.5 registry, and every registered code is reachable from at least one code path. This is the test that keeps a promise made in prose three phases earlier from evaporating — the register is only worth having if it cannot silently fall out of step with the code.
- **Exit-code Discipline**: `validate` exits non-zero if and only if the run recorded at least one `error`. A stage command exits non-zero when it did no work, and zero when it did its work and found problems — the two are different conditions and must not be conflated.
- **Version Drop-down Integrity**: Every `path` in a `version.yml` resolves to a sibling directory that sync actually wrote, and every version folder in that doc-class has exactly one entry — the file and the folders beside it are two views of one list, so neither can carry what the other lacks. Ordering is numeric-descending, so `10.4.0` precedes `9.3.0`. A hand-added entry survives a re-sync.
- **CSH Survives a Merge**: A merged tree's `csh.yml` resolves entirely against that tree — every path a page that exists, every fragment an anchor in it, every identifier listed in its page's frontmatter. The identifier **set** is exactly the converted map's: merging moves a Help button and never drops one, and a map the stage cannot parse fails the version rather than being written empty or copied stale. A version with no `csh.yml` gains no file.
- **Editorial Override Fidelity**: A path in `keep_separate` returns exactly the subtree it names to Stage 6's layout — every topic at or under it becomes its own page, nothing merges onto it from either side, and no page outside it changes except for links that now point at a topic's own page. Removing the path returns the merged tree byte-identically to what it was before. A path matching no topic is named in the run report rather than applied silently, and reordering the list is not a re-merge.
- **Redirect Map Integrity**: Every `to` in a published `redirects.yml` resolves to a file the target actually holds — these are the entries a reader is 301'd through, so a dangling one is an error. The map carries every merged version under its doc-class, not only the ones the run touched: a scoped `--version` re-sync leaves the other versions' redirects byte-identical. A hand-added redirect survives a re-sync. Paths are the served ones; an empty `publish_base_url` makes them tree-rooted rather than absent, because a map missing only its prefix is recoverable and a map never emitted is not.
- **Passthrough Carries Content, Not Presentation**: A table emitted as raw HTML carries no generated stylesheet class — on the `<table>` element itself as well as on every descendant, the case a scrub written as a descendant walk silently misses. Classes naming semantics the plain text has lost (`varname`, `MCXref xref`, the `note*` family) survive, because a later phase turns them into Markdown rather than discarding them. Layout attributes are not touched: they change rendering, and a cleanup that changes rendering cannot be verified by showing that nothing changed. A conversion run before and after the scrub produces byte-identical `toc.yml`, `csh.yml` and `redirects.yml`.
- **Origin Redirect Coverage**: Every converted topic of a product with a declared origin template has exactly one row in its version's `301.yml` — the row count equals the version's `output_map` count, so a drop anywhere in the three-way join fails the version rather than shipping a short map. The `from` is the live docsite URL the reader has today, verified against the real site before the product is declared, never inferred from another product's layout; a product with no declared template writes no file and is named in the run report. The doc-class map carries every version under it, not only the ones the run touched, and a hand-added row survives a re-sync.
