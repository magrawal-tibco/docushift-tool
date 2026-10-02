# R2 — Catalog & discovery: findings
Base: review-base (7dda975) · Reviewed: `catalog.py`, `discovery/client.py`, `discovery/crawler.py`, `discovery/sitemap.py`, `apiref.py` (+ the `catalog fetch/set/import/sitemap` wiring in `cli.py` where it decides behaviour) · Date: 2026-10-02

| S1 | S2 | S3 | S4 |
|---|---|---|---|
| 4 | 3 | 13 | 1 |

All repros live in `C:\tmp\review-R2\`. They run on **copies** of `config/` and a backup of `cache/state.db` in `C:\tmp\review-R2\root\`, built with the SQLite backup API from a read-only handle. Tests: the unit's 4 files pass on the frozen code (262 passed).

## Findings

### R2-01 · S1 · A hand edit to `in_scope`, `release_status` or `migrate_decision` in the CSV is silently undone by the next fetch
- **Where:** `src/docushift/catalog.py:1418-1427` (`_resolve_scope`), `:1449-1461` (`_resolve_release_status`), `:1485-1496` (`_resolve_migrate_decision`). Called from `merge_fetch_results` at `:580-591`, `apply_eos` at `:700-701` and `apply_migrate_decisions` at `:726-727`.
- **What:** All three resolvers treat a value as a human's only when its `*_source` column already reads `manual`. A value edited in Excel keeps its old source (`default`/`scope_rule`/`eos_report`/`docsite_sheet`), so the resolver's "actively resets" step overwrites it. Nothing warns: `catalog import` neither detects nor pins the edit (`cli.py:871-895`), and these columns have no snapshot to compare against.
- **Failing scenario:** In `products.csv`, set `tibco-ebx` `in_scope` to `true` (the documented way to "put one excluded product back into scope by editing the CSV", architecture §3.10). Run `catalog fetch --product tibco-ebx` and the value is back to `false`. Same for `versions.csv` `tibco-partnerexpress@6.0.0` `release_status` `retired`→`ga`: after the fetch it is `retired` again, and the version silently stops converting. `catalog eos` and `catalog migrate` do the same.
- **Confirmed:** yes, by mechanism. `repro_merge.py` cases A and A2 ran on copies of the real CSVs and `state.db` and printed `True → False` and `ga → retired`. No current row is in that state: all 669 products' scope columns are consistent with `scope.yaml`.
- **Suggested fix:** On load, or in `catalog import`, detect a value that disagrees with what its recorded source would produce and promote that source to `manual`. Alternatively snapshot these columns the way `family` is snapshotted. Fixing the docs alone is the fallback.

### R2-02 · S1 · `catalog fetch --dry-run --allow-deletes` purges `state.db`
- **Where:** `src/docushift/catalog.py:593-599`; the `dry_run` check only guards `:616-618`.
- **What:** With `allow_deletes`, every version absent from the fetch is deleted in memory and `state.forget_version()` runs right away. That call auto-commits a DELETE across `version_snapshot`, `version_state`, `version_metadata` and `engine_folder_map` (`state.py:409-413`), even in a dry run. The CLI accepts both flags together and prints "dry run -- nothing written" (`cli.py:163, 261, 273`).
- **Failing scenario:** A user previews a destructive fetch with `--dry-run --allow-deletes`. The CSVs are untouched. The removed versions' download status, checksum, extract path, folder metadata and merge base are gone from `state.db`.
- **Confirmed:** yes. `repro_merge.py` case B dropped one EMS version from a fetch result. After `merge_fetch_results(..., allow_deletes=True, dry_run=True)` that version's snapshot row was gone from the state copy.
- **Suggested fix:** Collect the deletions and apply them, both the dict removal and `forget_version`, only inside the `if not dry_run` block. Ideally do it after `save()` succeeds.

### R2-03 · S1 · A hand-set `bu` is reverted when the product's family is still the fetched one
- **Where:** `src/docushift/catalog.py:777-785`
- **What:** For an `unclassified` product, which ranks equal to every incoming product since Phase 32, the family 3-way decision compares `family` only. If `family` still equals the snapshot (`general`), the code "takes theirs" and also writes `mine.bu = theirs.bu`. `bu` is never compared with its snapshot, though `product_snapshot` stores it (`state.py:330`). `catalog set --bu` pins nothing either (`catalog.py:889-890`), even though the command says it records "a manual edit" (`cli.py:827`).
- **Failing scenario:** During triage, `catalog set --product X --bu ibi` (or an Excel edit) on a product still at `general/unclassified`. The next fetch resets `bu` to the keyword-inferred `tibco`. `bu` is the first segment of the workspace path and the publishing repository.
- **Confirmed:** yes, by mechanism. `repro_merge.py` case D, on a copy of the real catalog, edited the bu of `tibbr,-tibbr-service,...` to `ibi`. After the fetch it read `tibco`. 41 products (154 unclassified minus 113 with a typed family, see R2-09) are exposed. None has a hand-set `bu` today.
- **Suggested fix:** Run `bu` through `_take_theirs` against the snapshot's `bu` as its own field instead of moving it with `family`. Or have `set_product_field("bu")` pin provenance.

### R2-04 · S1 · The bulk-migration timestamp the docs say is excluded is in `release_date`, and the archive index cannot correct it
- **Where:** `src/docushift/discovery/crawler.py:61` (`_DATE_KEYS` begins with `releaseDate`), `:346`, `:432-433` (archive `GA_date` fills only an empty date).
- **What:** Architecture §2.1 and design §2.6 say leaving out `published_date` keeps the 2022-05-26 bulk timestamp out, so the archive index's `GA_date` "supplies the real month". In the live data the same timestamp also arrives on archived siblings under a key the crawler does read. The overlay then refuses to overwrite a non-empty date.
- **Failing scenario:** `tibco-enterprise-message-service` 5.1.0–8.4.0 (20 archived versions) all read `release_date=2022-05-26`, in `versions.csv` and in `version_snapshot`, so discovery wrote them. `sync/archives.py:106` turns this into the archive list's title month ("May 2022" for EMS 8.2.1).
- **Confirmed:** yes, for the catalog values: 20 rows in `versions.csv` and in the read-only `state.db` `version_snapshot`. Unconfirmed: which payload key carries it (no raw API payloads are cached), and the rendered archive page (no EMS archive list has been published yet). Low blast radius; S1 by the rubric because nothing flags it.
- **Suggested fix:** Let the archive index's `GA_date` override a sibling date for archived versions, or ignore a known bulk-migration value. Add a fixture with the real shape.

### R2-05 · S2 · Snapshots are committed before the CSVs are written, so a failed save turns upstream changes into "human edits" for good
- **Where:** `src/docushift/catalog.py:616-618`; `utils/csvio.py:160` (in-place, non-atomic write).
- **What:** `_record_snapshots` commits the new base, then `save()` writes `products.csv` and then `versions.csv`. If the write fails, the snapshot already holds the new values while the CSV holds the old ones. Every later fetch reads `mine != base` as a human edit and preserves the stale value. It counts it under `fields_preserved`, the number the docs say measures "how much of the user's work the merge protected".
- **Failing scenario:** `versions.csv` is open in Excel (the expected editor, §3.6) during `catalog fetch`. The fetch crashes with `PermissionError`; `cli.py:262` only catches `CatalogError`. The user closes Excel and re-runs. Upstream `zip_url`/`is_archived`/`convert_eligible` changes are never applied, and nothing says so. If `products.csv` was written and `versions.csv` was not, the two files are out of step as well.
- **Confirmed:** yes. In `repro_lock.py`, a read-only `versions.csv` stood in for the Excel lock. Fetch 1 raised and the snapshot held the new `zip_url`. The re-fetch kept the old value and reported `fields_preserved 2`.
- **Suggested fix:** Write both CSVs first, atomically (temp file plus `replace_file`, as the sitemap cache already does), and record snapshots only after both succeed. Or record them in a transaction that is rolled back if the save raises.

### R2-06 · S2 · A product returned without its archive-only versions reads as a deletion and aborts the whole fetch
- **Where:** `src/docushift/discovery/crawler.py:400-406` (archive failure is recorded, and the product is still returned at `:279`), `:273` (`--no-include-archived`); `catalog.py:829-831, 593-614`.
- **What:** Versions that only the archive index lists (design §2.8, "the index can add versions siblings omit") are missing from the fetch whenever the archive request fails or `--no-include-archived` is passed. `_collect_deletions` counts them as removed upstream. One product's transient archive 503 then aborts an `--all` fetch, with advice ("Excel reads '1.10' as '1.1'... re-run with --allow-deletes") that, if followed, deletes that product's archived history and its state.
- **Failing scenario:** `catalog fetch --product ems --no-include-archived` → `CatalogError: ... tibco-enterprise-message-service@6.0.1`.
- **Confirmed:** mechanism yes. `repro_noarch.py` runs the test module's own payloads and gets a blocked fetch. Real counts are unconfirmed: no raw payloads are cached. 8 products hold more catalog versions than the Sep-9 A-to-Z `versionCount` (EMS 35 vs 33), which fits archive-only versions, but the dump is older than the catalog.
- **Suggested fix:** Mark a product whose archive index was skipped or failed as "archive-incomplete", and leave its archived rows out of deletion detection.

### R2-07 · S2 · A version added by `download --from-file` blocks every later fetch of its product
- **Where:** `src/docushift/catalog.py:946-969` (`add_version`), `:829-831`; `cli.py:1095-1101`.
- **What:** §3.8 accepts an unknown version on a known product because the user is holding the package. Discovery will never return that version, so each later `catalog fetch` of the product raises the deletion block. `--allow-deletes`, which the message suggests, deletes the hand-supplied row and purges its download state. `_collect_deletions` has no exemption for `zip_source=manual` rows.
- **Failing scenario:** `download --product tibco-streaming --version 99.0.0 --from-file x.zip`, then `catalog fetch --product tibco-streaming` → `CatalogError ... tibco-streaming@99.0.0`.
- **Confirmed:** mechanism yes (`repro_merge.py` case C, on a catalog copy). No such row exists today: all 5,181 versions have a discovery snapshot, including the 8 `zip_source=manual` rows. Unconfirmed on real data for that reason.
- **Suggested fix:** Exclude rows that discovery never returned (no snapshot) and are `zip_source=manual` from deletion detection, and report them as hand-added.

### R2-08 · S3 · 926 `release_date` values (18%) are epoch milliseconds, not ISO
- **Where:** `src/docushift/discovery/crawler.py:346, 413` → `utils/csvio.py:104-124` (an all-digit value passes through unchanged).
- **What:** Architecture §3.2 says "ISO where parseable". 926 rows across 291 products hold values like `1399420800000` (476 active, 450 archived). `sync/versions.py:65-81` knows this dialect. `converter/driver.py:526` does not: `normalize_date(...)[:4]` gives `1399`, so the year comparison would raise a false `METADATA_MISMATCH`.
- **Confirmed:** n/a (S3). The values are counted in `versions.csv`. No false mismatch is in `findings` today: the only release-date mismatch is a different defect, see the edge notes.
- **Suggested fix:** Normalize epoch-ms to ISO in the crawler, inside `normalize_date` or a crawler-side pre-pass, with a fixture that uses the real shape.

### R2-09 · S3 · 113 of the 154 "unclassified" products already carry a hand-typed family
- **Where:** `src/docushift/catalog.py:1121-1142` (`triage_summary` counts by `family_source`); merge `:777-787`.
- **What:** These products have `family` set in the CSV (`bpm`, `businessconnect`, …) but `family_source=unclassified`. The snapshot protects the family from a fetch, but `catalog triage` reports a backlog of 154 that is really about 41, and offers rule hints for products a human has already filed.
- **Confirmed:** yes. `unc.py` counted 113 unclassified rows whose family differs from their snapshot's `general`.
- **Suggested fix:** Count an unclassified product whose family differs from its snapshot as "hand-classified, source not pinned", or offer to pin those rows (the `propagate-catalog-edit` workflow does this by hand).

### R2-10 · S3 · `catalog fetch --bu` filters on discovery's guessed bu, not the catalog's
- **Where:** `src/docushift/discovery/crawler.py:185-186`; `cli.py:191-201`.
- **What:** `--family` is resolved from the catalog, but `--bu` is compared with the bu the keyword rules infer. 12 catalog products disagree with their inferred bu.
- **Failing scenario:** `catalog fetch --bu datasynapse` crawls all ~669 products and keeps none, because the 4 DataSynapse products infer `tibco`. It ends with "Discovery returned no products". `--bu spotfire` skips 3 catalog-spotfire products and refreshes 4 catalog-tibco ones.
- **Confirmed:** yes. `bu_filter.py` compared catalog bu with `resolve_product_info` over the real catalog: datasynapse→tibco 4, spotfire→tibco 3, tibco→spotfire 4, tibco→onebx 1.
- **Suggested fix:** Resolve `--bu` to selectors from the catalog, as `--family` is, and fall back to the inferred bu only for products not yet catalogued.

### R2-11 · S3 · Unrecognized enum tokens, provenance included, are coerced silently and `validate()` never says so
- **Where:** `src/docushift/catalog.py:1508-1514` (`_coerce_enum`), used at `:295, 302, 325-344`.
- **What:** A typo in a hand-edited `scope_source`/`release_status_source`/`engine_source`/`zip_source`/`release_status` falls back to the default without a word. The fallback then drives behaviour: `scope_source: manaul` → `default` → the next fetch resets `in_scope`. `release_status: retire` → `unknown` → the version converts. `zip_source: hand` → `auto` → the downloader fetches.
- **Confirmed:** n/a. Every enum column in the real CSVs holds only valid tokens today.
- **Suggested fix:** Collect unrecognized tokens during `load()` and report them from `validate()`, the way duplicate slugs are.

### R2-12 · S3 · The `match_leaf` digit guard rejects a real leaf for an in-scope version
- **Where:** `src/docushift/discovery/sitemap.py:170-175`
- **What:** The "name must not end in a number" guard throws out `tibco-activematrix-businessworks-plug-in-for-applicability-statement-2-6-0-0`, the only 6.0.0 leaf of the AS2 plug-in, a product whose name itself ends in `2`. Catalog 6.0.0 is active and `convert_eligible`, so it gets no pages.
- **Confirmed:** yes. `leafmatch.py` ran over the real `cache/coveo/manifest.json` and `versions.csv`: 3 versions have suffix candidates but no match. The guard correctly rejects 2 of them (`tibco-mdm-studio` 2.0/3.0 vs `-5-2-0`/`-5-3-0`). AS2 is the one false negative. It is reported as `leaf=no` in `reports/coveo-sitemap.csv`.
- **Suggested fix:** When the guard leaves zero candidates and exactly one leaf exists that no other catalog version claims, accept it, or add an alias. Low priority.

### R2-13 · S3 · A transient failure on a changed product index drops the whole product from the sitemap manifest
- **Where:** `src/docushift/discovery/sitemap.py:316-319` (and `:277-281` per leaf)
- **What:** When a product file's `lastmod` changed and the refetch fails, `manifest["products"].pop(slug)` makes every cached leaf of that product unreachable through `pages()` until a later run succeeds, though the XML is still on disk. One failed leaf likewise drops out of that product's stem list. It is reported in `result.errors`. Also, `lastmod` has day granularity, so a second change on the same day is never refetched.
- **Confirmed:** n/a.
- **Suggested fix:** Keep the previous manifest entry on a network error, as opposed to a parse error.

### R2-14 · S3 · Crawl selectors over-match through the slug-derived code
- **Where:** `src/docushift/discovery/crawler.py:165-167`
- **What:** `--product clarity` (code of `tibco-clarity-cloud-edition`) also fetches `tibco-clarity`, because `_code_from_slug("tibco-clarity") == "clarity"`. The same happens with `messaging`. Harmless today, since the extra product is current data merged under its own slug, but a scoped fetch is not scoped.
- **Confirmed:** yes. `sel.py` checked every unambiguous catalog code against the A-to-Z dump: 2 codes over-match.
- **Suggested fix:** Match the slug-derived code only for selectors the catalog cannot resolve to a slug.

### R2-15 · S3 · A product that disappears from A-to-Z is never reported
- **Where:** `src/docushift/catalog.py:593` (deletion detection runs only per fetched product); `cli.py:286-292` reports only unmatched scope rules.
- **What:** On `--all`, a catalogued product absent from A-to-Z stays in scope and eligible forever, with no line saying so. It surfaces only when its download fails.
- **Confirmed:** n/a. Two catalog products (`tibco-businessworks-plug-in-for-tibco-auditsafe-for-tibco-platform`, `tibco-product-and-service-inventory`) are absent from the Sep-9 A-to-Z dump, but the dump predates the catalog.
- **Suggested fix:** On `--all`, name the catalogued slugs that A-to-Z no longer lists, the same way `scope_rules_unmatched` is named.

### R2-16 · S3 · `version_metadata.folder_path` is last-wins while the version row is first-wins
- **Where:** `src/docushift/discovery/crawler.py:338-339` vs `:271`
- **What:** If a version number shows up both on the detail record and in `siblings`, the row keeps the detail's values, but `folder_path` metadata, which the downloader uses (`downloader/fetcher.py`), is overwritten by the later sibling's declared path.
- **Confirmed:** n/a.
- **Suggested fix:** Use `setdefault` for `folder_path` too, or write metadata only for the record that won.

### R2-17 · S3 · The crawler keeps the A-to-Z slug verbatim while `load()` lowercases it
- **Where:** `src/docushift/discovery/crawler.py:219`; `catalog.py:281, 562`
- **What:** A mixed-case slug from the docsite would miss its catalog row in the merge, be added as a second product, and come back on the next load as a duplicate slug. All 739 slugs are lowercase today. Two public slugs are not path-safe (`tibbr,-tibbr-service,...`, `tibco-activematrix-implementation-type-for-c++`); see the edge notes.
- **Confirmed:** n/a.
- **Suggested fix:** Normalize (strip + lower) the slug in `_list_products`.

### R2-18 · S3 · API roots are re-derived after all, by a second copy of the walk
- **Where:** `src/docushift/apiref.py:90-99, 149-156` (docstrings: "Never re-walks", "Nobody re-derives them"); callers `converter/driver.py:761`, `sync/distributor.py:639-642`; duplicate descent at `extractor/inventory.py:195-212`.
- **What:** `recorded or find_api_roots(...)` treats a recorded *empty* list, the answer for most versions, as "no record" and walks again. Stage 4's own walk is a separate implementation (it skips symlinks; `find_api_roots` follows `is_dir()`) and uses the output roots Stage 4 located, while Stage 5 passes its own. The two agree today only because they happen to share the same predicate.
- **Confirmed:** n/a.
- **Suggested fix:** Store "recorded, empty" distinctly (key present vs absent) and fall back only when the key is absent. Make `inventory.py` call `find_api_roots`, or share one descent helper.

### R2-19 · S3 · The discovery sections of design.md and architecture.md describe the crawler as it was before Phases 18d and 32
- **Where:** `docs/design.md` §2.3 steps 3 and 5, §2.4 steps 2–3, §2.6 "Active ZIP URL construction", §2.7; `docs/architecture.md` §2.1 rows 3 and 5 and the first policy bullet.
- **What:** See the Docs drift section. The docs say category data is loaded and promoted, rules assign `family`/`taxonomy_rule`, dedup runs before the visibility filter (`crawler.py:178-186`), parent products are dropped, and the ZIP template is `doc/zip/tib_…`. The code does none of these now.
- **Confirmed:** n/a.
- **Suggested fix:** Rewrite those subsections to match `crawler.py` as it stands.

### R2-20 · S3 · Architecture §3.1/§3.5/§3.10–3.12 contradict the merge code
- **Where:** `docs/architecture.md` §3.1, §3.5, §3.10–§3.12
- **What:** See the Docs drift section: the CSV-edit pinning claim (R2-01), §3.5's field list, the allowed `bu` values, and the "perfect mirror" figure in §3.12.
- **Confirmed:** n/a.
- **Suggested fix:** Correct after R2-01 is triaged, since the fix decides which side changes.

### R2-21 · S4 · Dead code
- **Where:** `src/docushift/discovery/client.py:169-175` (`product_list_by_suites`, `bu_category_products`, plus their `config/docsite.yaml` endpoints: no callers since Phase 32). `src/docushift/catalog.py:893-894`: the `set_product_field("slug")` branch has no caller and would be wrong if reached, because it changes `product.slug` without re-keying `catalog.products`, and `value or None` writes a blank key. `docsite_id` product metadata (`crawler.py:277-278`) is written and never read.
- **Confirmed:** n/a.
- **Suggested fix:** Delete them.

## Edge notes (for the cross-stage pass X1)
- **`release_date`** (written by R2): mixed ISO and epoch-ms (R2-08) plus a bulk-timestamp group (R2-04). Readers: `sync/versions.py:release_month` handles both formats; `sync/archives.py:106`; `sync/distributor.py:882`; `converter/driver.py:525-526`, where `[:4]` breaks on epoch-ms. The same line also breaks on `Month YYYY`: the one `METADATA_MISMATCH` in `findings` reads `homepage release-date June != catalog 2023` (`spotfire-data-science-author@1.4.0`). That is an R4 defect.
- **`zip_url`** for active rows uses the catalog slug for the filename (`client.py:62-100`). The API publishes the real per-version `slug`, the `finalSlug` §2.2 refers to (see the test fixture `test_discovery.py:75`), but the crawler neither captures it nor stores it in `version_metadata`. Renamed products keep old names on old releases (the Coveo `tibco-streaming.xml` lists `spotfire-streaming-11-1-0`), which may be why `tibco-streaming` 11.1.x are `zip_source=manual`. R3 should check how `downloader/fetcher.py` derives the URL.
- **`product_code`** is read by `downloader/fetcher.py` together with `version_metadata.folder_path`; the folder path is recorded only when declared, with two segments (`crawler.py:338`). The fallback `_code_from_slug` is a guess (design §2.6).
- **Path-unsafe identifiers become path components** (`config.py:359-394`: `<slug>-<version>.zip`, `extracted/<slug>/<version>/`). The slugs `tibbr,-tibbr-service,-tibbr-community,-and-tibbrcommunity-service` and `tibco-activematrix-implementation-type-for-c++`, and the versions `Cloud®` (`tibco-cloud`) and `(iPaaS)` (`tibco-cloud-integration-ipaas`), the latter two active and `convert_eligible=true`. Also `Cloud` (`tibco-health-essentials-cloud`). For X2.
- **`bu`** values in use are `tibco`, `ibi`, `spotfire`, `datasynapse`, `onebx`, not the two §3.1 names. Any reader that assumes the two should be checked.
- **`in_scope` / `release_status` / `convert_eligible`** are read only through `iter_versions(eligible_only=True)`. `migrate_decision` is read only by `cli.py` (display). Consistent with §3.12.
- **`state.db` writes from R2:** `product_snapshot`/`version_snapshot` (merge base) and `product_metadata.docsite_slug/docsite_id` plus `version_metadata.folder_path`, written by `cli.py:_record_discovery_metadata` after the merge. `forget_version` purges 4 tables (R2-02).
- **Coveo:** `cache.pages()` returns `None` both for "no leaf matched" and for "leaf file missing on disk" (`sitemap.py:237-243`). Reframe/301 consumers (`origins.py`, `reframe/driver.py`) cannot tell the two apart.

## Test gaps (real-data paths only)
- No test edits `in_scope`/`release_status` in the CSV (without `catalog set`) and then fetches (R2-01). The tests only exercise `scope_source=manual`.
- No test combines `dry_run=True` with `allow_deletes=True` (R2-02).
- No test sets `bu` on an unclassified product and then fetches (R2-03).
- The fixtures use only ISO `releaseDate`, while 926 real rows are epoch-ms (R2-08). No fixture has a bulk timestamp under `releaseDate` on an archived sibling (R2-04).
- No test covers a save failing after snapshots are recorded (R2-05).
- No test merges a fetch where the archive index failed for a product that already has archive-only versions (R2-06).
- No test runs `add_version` followed by a fetch (R2-07).
- No `match_leaf` case has a product name ending in a digit (R2-12, real: AS2).

## Docs drift
- `architecture.md` §3.10 ("So a human can put one excluded product back into scope by editing the CSV ... no later fetch will undo it"), the `manual` rows of the §3.10/§3.11/§3.12 provenance tables ("A human set … in the CSV"): false without also editing the `*_source` column (R2-01).
- `architecture.md` §3.5 lists `slug` among the merged fields. The code merges `product_code` (`catalog.py:154`), and design §3.2 is right.
- `architecture.md` §3.1: "`bu` — `tibco` or `ibi`". The catalog uses 5 values.
- `architecture.md` §3.12: "`convert_eligible` is today a perfect mirror of `is_archived` … zero exceptions". There are now 94 (88 archived and eligible, 6 active and ineligible).
- `architecture.md` §2.1: the `isParentProduct` row ("35 public products … missing"), the duplicate-slug row ("The crawler dedups first-wins … `crawler.py:178-186`") and the first policy bullet ("Phase 18d makes the drop a counted, named line") all describe defects that are fixed (`-latest` fallback, group-then-filter, `advertised_but_empty`).
- `design.md` §2.3 step 3 (load category data) and step 5 (family filter), §2.4 steps 2–3 (dedup before visibility), §2.5 step 4 (all empties counted as unversioned), §2.6 (old `doc/zip/tib_…` template), §2.7 (rules assign family with `taxonomy_rule`, plus category promotion): all pre-Phase-18d/32.
- `architecture.md` §2.1/§3.2: "the archive API returns values like `June 2022`". The catalog holds none; dates are ISO or epoch-ms.
- `apiref.py` docstrings "Never re-walks" / "Nobody re-derives them" (R2-18).
- `CatalogManager.validate()` docstring "Re-reads the CSVs": it uses the cached `load()`.

## Checked and fine
- A-to-Z normalization on the real dump (739 records, 669 public, 1 duplicated slug): visibility runs before dedup, the public `spotfire-application` record wins, `versionCount` is taken as the max over visible records, and a missing visibility flag counts as public.
- `-latest` parent fallback; `advertised_but_empty` vs `unversioned` split, named in the CLI output.
- Envelope peeling is bounded; `_versioned_records` reads `siblings` by name only; a stale one-segment folder never yields a ZIP URL; archived rows get no templated URL (0 active rows lack `zip_url`).
- Archive overlay's 3 cases (new / active untouched / archived topped up); `zipPath` is made absolute.
- Client: non-200 raises; JSON decode failure names the SSO page; `get_bytes` raises on an empty 200 and returns HTML for the sitemap parser to classify as `not_served`; the throttle is shared.
- Merge: per-field 3-way decision, no-snapshot rule, `custom_override` per row, deletion check scoped to fetched products and raised before any write (without `--allow-deletes`), stable sort, `_bu`/`_family` regenerated, CRLF + BOM.
- Every one of the 5,181 versions and 669 products has a snapshot. Scope columns are consistent with `scope.yaml`; one rule (`tibco-spotfire-for-apple-ipad`) is unmatched and reported, because A-to-Z lists it with `versionCount 1` but it yields no version (`advertised_but_empty`).
- `resolve_slug` refuses ambiguous codes; `iter_versions` composes scope → retirement → eligibility → batch as design §4 says.
- Sitemap cache: names are reduced to their last component (no path escape); no case-insensitive or cross-product name collisions in the 2,024 cached files; a login page cached as XML is re-parsed on reuse.
- `apiref` predicates: whole-segment name test (never substring), marker-first classification, `swallows_output_root` tie-break.
- Not checked: raw docsite detail/archive payload shapes (none cached, and the no-network rule forbids fetching them), so the payload keys behind R2-04 and the `_unwrap` descent into a detail object that carries a `data`/`product` key remain unverified. EOS/migration *loading* (`config.py`) belongs to R1; only its resolution here was reviewed.
