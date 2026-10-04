# R10 — Publishing layout: findings
Base: review-base-b4 (73cc93d) · Reviewed: `sync/distributor.py`, `router.py`, `documents.py`, `apirefs.py`, `archives.py`, `redirects.py`, `versions.py`, `__init__.py` (2,456 lines), their 5 test files (169 pass) · Date: 2026-10-04

| S1 | S2 | S3 | S4 |
|---|---|---|---|
| 2 | 1 | 10 | 3 |

Real-data runs: the library was driven from `C:\tmp\review-R10\run_sync.py`, with a copied config and `state.db` and the real `families/`, `output/` and `reframed/` read-only, into `C:\tmp\review-R10\t1` (EMS and ActiveSpaces complete, Streaming partial, TRA not reached; the first run was killed at the 30-minute limit). Published trees `C:\tmp\p35-aem` and `C:\github\tibco-docs-aem` were read only.

## Findings

### R10-01 · S1 · An archived version marked for migration is published, but no drop-down lists it
- **Where:** `versions.py:119` (`generated_rows` keeps only `not v.is_archived`), `distributor.py:908-910` (`_report_rows` skips archived rows), `cli.py:1125-1132` (`sync` selects with `eligible_only=True`, which includes archived rows). The premise is in `archives.py:27-31` and phase-06.md:157: "0 archived rows are `convert_eligible`, so no archived version is published".
- **What:** That premise is now false. `sync` places an archived, eligible version's folders in `online-help` and the document doc-classes, then writes a `version.yml` that leaves it out. Nothing is reported.
- **Failing scenario:** `tibco-designer` 5.10.0 (`is_archived=true`, `convert_eligible=true`, `migrate`) is extracted and synced. The run writes `user-guides/5-10-0/` and `release-information/5-10-0/`, and both `version.yml` files come out as a bare `versions:` (YAML null, no rows). The product's only published content cannot be reached, and the archives index lists 5.10.0 only as a ZIP download.
- **Confirmed:** yes, in two parts. (1) From the catalog: `sync --all` selects **88 archived rows on 45 products** (`archived_eligible.py`). None has an extracted or converted tree yet, so no published tree shows the problem today. (2) By a probe on that real catalog row, with a stand-in extract in `C:\tmp\review-R10\probe`: the folders above were written, both drop-downs were empty, and the run recorded no finding except the probe PDF's `DOCUMENT_UNREADABLE`.
- **Suggested fix:** Decide what an archived-but-migrated version is. Either list it in the drop-down (drop the `is_archived` filter for rows that are `convert_eligible`) or keep `sync` from selecting it. Raise a finding for any published folder that `version.yml` does not list.

### R10-02 · S1 · Setting `publish_base_url` doubles every published 301 map
- **Where:** `redirects.py:204-226` (`owned_prefixes`) and `118-134` (`prefix`, `_legacy_prefix`) build the owned prefixes from the base configured *now*. `redirects.py:250` matches by `startswith`. Caller: `distributor.py:870-896`.
- **What:** Rows written while the base was empty start `us/en/…`. After the host is filled in, those rows no longer match any owned prefix, so they survive as "foreign" rows beside a full new set.
- **Failing scenario:** Sync EMS with `publish_base_url: ""` (the shipped state), then set it to the AEM host, as `publishing.yaml` and §6.4.1 anticipate, and sync again. Every map now holds both the host-less and the hosted rows. The run reports success, and `validate` resolves both halves.
- **Confirmed:** yes, on scratch target `t1` with the real EMS trees (`root2` config, `run_base.py`). `301.yml` went from 8,613 to **17,226** rows and `redirects.yml` from 8,639 to **17,278**. In each, half the rows have no host. Run summary: `maps 2 rows 34504`, findings `{}`. It is not yet in any published tree, because the key is still empty everywhere.
- **Suggested fix:** Decide ownership from the path after the scheme and host (strip both before the prefix test), so a base change replaces rows instead of adding to them. Add a test that syncs twice with different bases.

### R10-03 · S2 · A leftover `.part` folder is published into the doc-class 301 map
- **Where:** `distributor.py:786` (`present` is every child directory, including `*.part`), which feeds `redirects.py:186-199` (`generated_rows` reads `{segment}/301.yml` for each).
- **What:** After an interrupted run, the next run that touches the product reads the staging folder's per-version map. It writes rows whose `to` points into `…/online-help/10-x-y.part/…`. The drop-down ignores the folder, because it is not in the catalog.
- **Failing scenario:** A run is killed while copying Streaming 11.1.0. Its `except BaseException` cleanup never runs, so `online-help/11-1-0.part/` is left behind. A later `sync --product tibco-streaming --version 11.2.1` is `current` for its version, yet it rewrites `online-help/301.yml` with the staging folder's rows.
- **Confirmed:** yes, in `t1`: **1,171 of 7,070 rows** in `tibco-streaming/online-help/301.yml` point at `11-1-0.part`. `validate` reports the `.part` folder as residue (`validation/tree.py:135-147`). It does not report the rows, and those resolve on disk because the folder exists.
- **Suggested fix:** Drop names ending in `STAGING_SUFFIX` from `present` in `finish_product` (or list folders through one shared helper that `validate` also uses).

### R10-04 · S3 · Products whose every version is archived get no archives index, and nothing says so
- **Where:** `distributor.py:952-962`. `sync_archives` runs only for products that have a selected version.
- **What:** 134 in-scope products with archived history are never selected, so **759 of the 2,393** in-scope archived rows are indexed nowhere. In the four synced families that is 13 products and 120 rows, e.g. `tibco-liveview-desktop` (29 rows) and `tibco-activespaces-transactions` (26). §6.2.3 says `archives/` is "the *complete product history*". Phase 6 measured this gap (phase-06.md:160, 150 products then) but recorded it only in the history file.
- **Failing scenario:** `sync --family streaming` publishes no `archives/` for `tibco-streambase` (21 archived rows), and no row or finding names it.
- **Confirmed:** yes (`archived_eligible.py`, `archives_audit.py`). Whether this is a defect is a product decision.
- **Suggested fix:** Decide. Either index archived-only products (select them for `sync_archives` alone), or state the limit in §6.2.3 and report the count.

### R10-05 · S3 · A doc-class or API folder the source no longer produces stays published, with no row
- **Where:** `distributor.py:437-443` (iterates only the doc-classes routing returns now) and `565-569` (`return []` when no API root remains).
- **What:** The swap replaces a version folder only when that doc-class still routes something. A doc-class that now routes nothing keeps its old folder, its old files and its drop-down row, and gets no report row.
- **Failing scenario:** A re-extracted package no longer ships its readme. `release-information/5-10-0/` keeps the old readme, and the run reports only `user-guides`.
- **Confirmed:** by probe (`tprobe`: readme removed, re-sync left the folder untouched, no row). No real instance today: all 174 published version folders in `p35-aem` and in `tibco-docs-aem` match current routing (`stale_docs.py`).
- **Suggested fix:** After routing, compare against the published doc-classes for that segment, and remove or report (`NO_OUTPUT`) any folder the version no longer feeds.

### R10-06 · S3 · `_stale` cannot see a forced re-conversion, though its docstring says it can
- **Where:** `distributor.py:335-357`.
- **What:** It compares `convert_source_checksum` with `reframe_source_checksum`. Both hold the *package* checksum, which `convert --force` leaves unchanged. A merge built from the previous conversion is therefore published as current.
- **Failing scenario:** The pending batch-2 re-convert (`convert --force`) runs without `reframe --force`. EMS and ActiveSpaces publish the old merged trees, and neither `SYNC_MERGE_UNAVAILABLE` nor any other finding is raised.
- **Confirmed:** mechanism only. In `state.db` both keys are equal, byte for byte, for all 12 merged versions. Today `reframed/` is newer than `output/` in all 12, so no stale tree is published. The reframe half of this is Phase 21's carried-forward item (R9-04).
- **Suggested fix:** Record a conversion-run identity (an output digest or a convert timestamp) and compare that, or have `_stale` compare the `output/` and `reframed/` timestamps.

### R10-07 · S3 · Links into the API tree use a URL shape that Phase 29 found the platform does not serve
- **Where:** `apirefs.py:186-204` (`{base}/{tree_name}/en-us/{slug}/api-references/…`) against `redirects.py:95-115` (`{base}/us/en/{slug}/{doc-class}/…`, no tree name).
- **What:** The tool's two builders of host-relative URLs disagree. Phase 29 found that served URLs carry no repository segment and put the region first. The API links carry both the repository name and `en-us`. §6.4.2 rejected `/en-us-…` server-absolute paths as "an assumption about someone else's infrastructure", yet that is what a configured base produces.
- **Failing scenario:** Once the host is set, the 758 API links in `p35-aem` (2,854 corpus-wide per §6.4.2) point at `https://host/en-us-tib-ems-userdocs-resources/en-us/…`. If `-resources` is served like the docs tree, every one of them 404s.
- **Confirmed:** unconfirmed. How `-resources` is served is not documented, and there was no network. On disk, all 758 tree-rooted links in `p35-aem` resolve (AS 18, EMS 516, Streaming 166, SDS 58).
- **Suggested fix:** Ask the platform how `-resources` is served, then derive both URL shapes from one function.

### R10-08 · S3 · `PUBLISH_BASE_URL_UNSET` fires per version, only on runs that copy, and says the wrong thing
- **Where:** `distributor.py:594-600`.
- **What:** §6.4.1 says one warning per product. The code warns once per version, only when that version's API tree was SYNCED. The message says links "stay relative and will not resolve", but since 6e they are tree-rooted paths that lack only the host.
- **Failing scenario:** The first EMS sync shows "Findings: 6 warnings" (`scratch/sync-p35-ems.log`). A re-run where everything is current records nothing, though no link has a host.
- **Confirmed:** yes (the p35 log, and the `t1` re-run returned findings `{}` with 12 API trees `current`).
- **Suggested fix:** Raise the warning once per product whenever an API tree is placed *or current* with the base empty, and correct the message.

### R10-09 · S3 · `_place_archives` leaves `archives.part` behind on failure
- **Where:** `distributor.py:733-753`.
- **What:** The other three placers wrap staging in `try/except BaseException: remove(staging)`. This one does not.
- **Failing scenario:** A ZIP copy fails partway (disk full, file locked). `…-resources/…/archives.part/` is left in the published tree until the next run.
- **Confirmed:** n/a (read). No ZIP is on disk anywhere today, so only the three rendered files are written.
- **Suggested fix:** Use the same guard (see R10-15).

### R10-10 · S3 · Document index currency ignores catalog edits that change the rendered index
- **Where:** `distributor.py:1004-1030` (`_documents_current`). The title comes from `display_name` at `distributor.py:509`.
- **What:** The docstring treats only a template change as escaping the check. A `display_name` edit in `products.csv` changes the heading of every `user-guides`, `release-information` and `reference-documents` index, but the folder reports `current` and keeps the old title. `archives/` compares its index as text and `metadata.yml` is rewritten every run, so only these three go stale.
- **Failing scenario:** A product is renamed TIBCO → Spotfire in the catalog. Online-help, archives and `csg-product` update; the three document indexes keep the old name until `--force`.
- **Confirmed:** unconfirmed. All 138 published document indexes in both trees match today's catalog (`titles.py`).
- **Suggested fix:** Add the rendered `index.md` text to the currency test, as `archives.current` does. Building it needs no PDF read when the titles are taken from the published index.

### R10-11 · S3 · `sync_documents` says it never raises, but two calls sit outside any guard
- **Where:** `distributor.py:466` (`_documents_current` → `filecmp.cmp`) and `470` (`entries_for` → `path.stat()`, `documents.py:201`). Neither is inside the `try` at `476-480`.
- **What:** An `OSError` while reading a source document escapes `sync_many` and aborts the whole run before `findings.flush()`.
- **Failing scenario:** A routed file vanishes or becomes unreadable between `iterdir` and `stat`.
- **Confirmed:** n/a. None of the 360 document-folder files in the real extracts is over 260 characters, and nothing failed in the runs.
- **Suggested fix:** Move both calls inside the guarded block.

### R10-12 · S3 · The router finds output roots by walking the tree, not from the record
- **Where:** `router.py:205-206` (`find_output_roots(tree, engine)`).
- **What:** §6.3.3 and Invariant 12 say Stages 4, 5 and 7 read one recorded answer (`recorded_roots`). The router walks for its own. A later change to root detection (batch 2's localized-root skip, R4-12) could make inventory and router disagree about who owns a `doc/` file.
- **Failing scenario:** A root that the record holds but the walk now skips (or the other way round) inside `doc/` gets its `Default.htm`/`csh.js` published as reference documents, or loses a real document.
- **Confirmed:** n/a. Over every extracted eligible version in the four families, 0 files were skipped as root-owned, so walk and record cannot differ there.
- **Suggested fix:** Read `output_roots` through `apiref.recorded_roots`, and walk only when no record exists, as `api_roots` does.

### R10-13 · S3 · Docs that contradict the code
- **Where / What:**
  - `architecture.md` §6.2 ("Cross-repo links must be rewritten at sync time… it cannot be done during conversion"), `design.md` §10 intro ("then rewrite every link… The rewrite is last"), §10.6 "Step 4, the link rewrite, in full", and `distributor.py:934-936` (API trees placed first "so that a link… can be rewritten") all contradict §6.4.2. The rewrite runs at convert time.
  - §6.4.1 "one warning per product", the message at `distributor.py:597-599`, and the `publish_base_url` comment in `config/publishing.yaml` ("leaves those links exactly as the converter emitted them and reports one line per affected product") all disagree with the code (R10-08).
  - §6.2.2 says document `index.md` "carries the same frontmatter as the `online-help` index (product, version, BU, family) plus `doc_class`". Both carry `title`, `generated` (plus `doc_class`), and nothing else.
  - `archives.py:27-31` and phase 6: "0 archived rows are `convert_eligible`". It is 88 now (R10-01). `versions.py:110-111` says a non-active folder "stays on disk for 6d's archives tree to reach", but archives never link a folder.
  - `distributor.py:684-686` gives "1,270 archived rows a full sync reaches". It is 1,634 of 2,393 now. §6.2.3 says "complete product history" (R10-04).
- **Confirmed:** yes (read against code and the runs above).
- **Suggested fix:** Correct the docs side in each case, except where R10-01/04/08 change the code.

### R10-14 · S4 · `archives.entries_for` re-derives the archive ZIP name
- **Where:** `archives.py:101` builds `f"{product.slug}-{version.version}.zip"` instead of calling `ConfigManager.archive_path()` (`config.py:382-390`), which `archive download` writes through.
- **What:** Two copies of one naming rule. If either changes, the index lists a downloaded ZIP as "not available".
- **Confirmed:** n/a.
- **Suggested fix:** Pass a path function (`config.archive_path`) instead of the directory.

### R10-15 · S4 · Four copies of one stage-and-swap block, and two copies of one version sort
- **Where:** `distributor.py:382-402, 499-525, 616-647, 733-753`. Sorts at `versions.py:120-128` and `archives.py:90-97`.
- **What:** One `staged(destination)` context manager would remove R10-09 by construction. One `order_versions()` helper would keep the drop-down and the archive order from drifting apart.
- **Confirmed:** n/a.
- **Suggested fix:** Extract both. Cleanup commit only.

### R10-16 · S4 · The Phase 29 legacy-prefix migration can probably be retired
- **Where:** `redirects.py:124-134` (`_legacy_prefix`), the unused `tree_name` parameter (`redirects.py:95-121`), and the second prefix per segment at `redirects.py:225`.
- **What:** The published EMS map in `tibco-docs-aem` holds 0 rows under the old shape, and `p35-aem` holds 0 too. The migration code now exists only to delete rows that no longer exist.
- **Confirmed:** yes, for the two trees read. Other copies of published trees are unknown.
- **Suggested fix:** Once the user confirms that no older published tree remains, drop `_legacy_prefix` and the `tree_name` parameter.

## Edge notes (for X1)
- **Sync's selection is `download`'s** (`eligible_only=True`), which includes 88 archived rows. Stage 7's drop-down assumes "selected ⇒ active" (R10-01).
- **Merge currency:** sync reads `convert_source_checksum` and `reframe_source_checksum` as "which conversion this merge came from". Convert writes the package checksum (R10-06).
- **Archive ZIP path:** `archive download` writes through `config.archive_path`, while sync rebuilds the filename (R10-14).
- **API URL, convert ↔ sync:** both name folders from `content_root` plus the recorded `api_roots`, and all 758 links in `p35-aem` resolve. They diverge only when no `api_roots` record exists: convert then locates output roots with the engine, while `distributor.api_roots` (`664-677`) reads output roots from the record only.
- **Output-root ownership:** inventory and convert read the record, the router walks (R10-12).
- **Per-version `301.yml`** is written by convert (Phase 35) and by reframe. Sync assembles it keyed on `to`, and ownership depends on the base URL (R10-02).
- **Sync → validate:** `validate` reports `.part` folders as residue, but resolves 301 rows into them as valid (R10-03).
- **X3:** `finish_product` runs once, after every version. The killed first run left 8 Streaming products with 14 doc-class folders and no `version.yml`, until the next run touched them. With unchanged inputs, the second run over EMS and ActiveSpaces was `current` on all 64 version rows. Archives showed `synced` only because the first run never reached them.
- **X2:** `_identical` (`distributor.py:997-998`) uses plain `rglob`/`is_file` with `LongPathsEnabled=0`. A source file of 260+ characters is invisible on the source side, so that version never reaches `current`. Today the only such file is in `reframed/` TRA Runtime Agent 5.13.0, which publishes from `output/`, so nothing is affected.

## Test gaps (real-data paths only)
- No test syncs an archived row with `convert_eligible=true` (88 real rows reach the path).
- No test syncs twice with different `publish_base_url` values over a published map (the documented next step for every map).
- No test runs `finish_product` with a `*.part` folder beside the version folders (left by any hard-killed run).
- No test re-syncs a version whose routing lost a doc-class or whose API roots went away.

## Docs drift
See R10-13. Also, the template header in `version.yml.j2` promises that "rows pointing outside this doc-class are left as they were found". That is true, but an empty drop-down still renders as `versions:` (null), not `versions: []` (R10-01).

## Checked and fine
- **Tests:** 169 pass on the frozen tree.
- **Tree naming:** `en-us-tib-{family}-userdocs` and `…-userdocs-resources` in `t1` and `p35-aem`, product segment is the slug, locale segment `en-us`. `loc-` trees are not reachable: locale is one global setting, and the Q decision deferred them.
- **Routing:** over every extracted eligible version in the four families, 101 files went to `user-guides`, 87 to `release-information` and 116 to `reference-documents`. No name-level misroute was found (all `relnotes`/`readme` went to release-information; `license`/`vpat`/`ReminderNotice`/`RTU` went to reference-documents). There were no stray files at content root, none was lost to the output-root skip, and no document path is 260+ characters.
- **Version segments:** 0 collisions across `versions.csv`. One empty segment (`tibco-loglogic` `-`) is archived and not eligible, so `SKIPPED` is unreachable today.
- **Drop-downs:** in `p35-aem` and `tibco-docs-aem`, every version folder is listed and no row dangles.
- **Maps:** in `p35-aem`, each of the 8 doc-class maps equals the sum of its per-version rows (EMS 8,639/8,613, AS 1,957/1,922, Streaming 7,070, SDS 2,350, Administrator 965, Runtime Agent 1,298). Every `to` resolves, every row has the `us/en/…` shape, and there are no duplicate rows.
- **API cross-tree links:** all 758 tree-rooted links in `p35-aem` resolve to placed files.
- **Archives:** for all 14 indexed products in the four families, the index rows equal the catalog's archived rows. The order is version-descending.
- **R1-01 ceiling:** checked ahead of currency for online-help and documents. API trees are refused before copy.
