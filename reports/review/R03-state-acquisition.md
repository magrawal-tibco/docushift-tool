# R3 — State & acquisition: findings

Base: review-base (7dda975) · Reviewed: `state.py`, `downloader/fetcher.py`, `downloader/__init__.py`, `extractor/safe_unzip.py`, `extractor/unpacker.py`, `extractor/inventory.py`, `extractor/content_root.py`, `extractor/__init__.py` (plus the call sites in `cli.py` download/extract/archive download, `utils/swap.py`, `utils/longpath.py`) · Date: 2026-10-02

| S1 | S2 | S3 | S4 |
|---|---|---|---|
| 0 | 3 | 10 | 3 |

Real data used: 54 ZIPs in `families/*/downloads/`, 60 extracted trees, `config/versions.csv`, `cache/state.db` (opened read-only), `html-to-md/cache/pub` (1,867 version dirs). Scratch scripts and repros are in `C:\tmp\review-R3\` (`scan_zips.py`, `cmp_counts.py`, `roots.py`, `repro_slip.py`, `repro_names.py`, `tests_r3/test_r3_repro.py`).

## Findings

### R3-01 · S2 · A drive letter in a later member segment escapes the target directory (zip-slip on Windows)
- **Where:** `src/docushift/extractor/safe_unzip.py:41-44` (the check), `:79` (the join)
- **What:** `_is_unsafe` tests for `X:` only at the start of the whole member name. `root.joinpath(*parts)` then treats a later segment such as `C:evil.txt` as a drive-relative path, and that segment replaces the root.
- **Failing scenario:** a member named `wrapper/C:escaped.txt` passes the check and is written to the process's current directory on drive C:. `wrapper/D:x` would be written to the root of D:. No error and no warning. `written` counts it as a normal file.
- **Confirmed:** yes, by a synthetic repro (`repro_slip.py`): `_is_unsafe` returned False, and the file appeared in the CWD outside `out/`. No real package carries a `:` in any member name (0 of 54 ZIPs). It is rated S2 rather than S1 because the corpus does not reach it, but it breaks the refusal rule that `design.md` §6.1 step 2 and `architecture.md` §4.4 promise.
- **Suggested fix:** refuse any segment that contains `:` (and any other character Win32 reserves). Also assert after the join that the destination is still under `root`, as a backstop.

### R3-02 · S2 · The inventory ignores the content root, so `pdf/` and `doc/` inside a wrapper are reported as "unclaimed"
- **Where:** `src/docushift/extractor/inventory.py:268-274`
- **What:** the document-router test and the unclaimed-residue grouping read `relative.parts[0]` from the version directory. For a wrapped package (46 of 50 in the §4.5 sample), that segment is always the wrapper name.
- **Failing scenario:** EMS 10.4.0 (`<wrapper>/doc html javadoc pdf`). Its 7 PDFs land in `asset_inventory` as `unclaimed` instead of `document-router`, and `extract` prints `7 unclaimed file(s) in tibco-enterprise-message-service-10-4-0/ -- no destination`. Runtime Agent 5.12.2 reports 443 files "unclaimed in tibco-runtime-agent-5-12-2/". A real unmarked API tree in a wrapped package would be folded into the same single line under the wrapper name, which defeats the per-segment diagnostic that §6.4 step 2 exists for.
- **Confirmed:** yes. In `state.db`, `asset_inventory` has `document-router` rows for only 15 versions (the flat and hand-copied ones), and every wrapped version has its PDFs under `unclaimed`. Running `inventory_tree` live on the real EMS 10.4.0 and TRA 5.12.2 trees gave `unclaimed={'<wrapper>': 7}` and `{'<wrapper>': 443}` and an empty router. Nothing downstream reads `asset_inventory` (`get_asset_inventory` has no caller), so the damage is limited to the report and the table. `sync/router.py` does route the PDFs, because it uses `content_root`.
- **Suggested fix:** compute the router and unclaimed segment relative to `content_root.resolve(tree)` (it is already recorded before `measure` runs).

### R3-03 · S2 · `extract_one` is documented "never raises", but its post-swap steps can raise, and the re-run then leaves the old package's measurements in place for good
- **Where:** `src/docushift/extractor/unpacker.py:244-260` (identify/measure/catalog writes, outside any `try`), `:199-216` (the CURRENT short-circuit)
- **What:** `extract_zip_checksum` is written right after the swap. Then `identify` runs (`catalog.save` via `record_detected_engine`), then `measure` (`record_csh_sources`, `record_asset_inventory`, `api_roots`, `record_extract_inventory` → `save`). Any exception in those steps escapes `extract_many` and aborts the batch. On the next run the checksum matches and the columns are non-blank (they are from the *previous* package), so the version is reported `current` and is never measured again.
- **Failing scenario:** a re-extract of a changed package while `versions.csv` is open in Excel. `csvio.write_rows` opens the file `"w"` in place, so it raises PermissionError. After the crash, `_api_files`/`_doc_files`, `csh_source`, `api_roots` and possibly `engine` still describe the old package. The converter reads `csh_source` (`converter/driver.py:827`) and `api_roots` (`:760`). Its currency check then sees a new checksum and converts the new tree using the old package's CSH sources and API roots.
- **Confirmed:** by a synthetic repro (`tests_r3/test_r3_repro.py::test_crash_after_swap_leaves_stale_columns_forever`). I made `record_extract_inventory` raise PermissionError. The re-run returned `CURRENT` with `api_files=2` from the old package, whose replacement has none. The Excel trigger is **unconfirmed** on real data, because I did not run `extract` against the main tree.
- **Suggested fix:** put the post-swap steps in a `try` that records `FAILED`. Write `extract_zip_checksum` only after `measure` completes (or clear the inventory columns before the swap), so that a failed run cannot pass as current.

### R3-04 · S3 · A partial walk keeps the previous package's columns, not blank ones, and nothing reports it
- **Where:** `src/docushift/extractor/unpacker.py:382-392`; `inventory.py:210-228`; `inventory.partial` has no reader in `cli.py`
- **What:** when `partial` is set, `record_extract_inventory` is skipped, but the old values are never cleared. `csh_source`/`asset_inventory` are still overwritten with the partial walk's data. The result is `EXTRACTED` with an empty message, and the next run is `CURRENT`. `CatalogManager.clear_extract_inventory`, which exists for this purpose, is never called.
- **Failing scenario:** an unreadable directory (or a directory path at or above about 258 characters, since `os.scandir` gets the unprefixed spelling) in a re-extracted package. The CSV then shows the old counts, `state.db` shows the partial ones, and no warning appears.
- **Confirmed:** n/a (S3). The repro (`test_partial_walk_keeps_previous_columns_and_says_nothing`) shows outcome `extracted`, `partial=True`, the old columns, and `current` on the re-run. No real tree is partial: on all 60 trees, `api+doc` equals the on-disk count, and the longest extracted directory is 214 characters (a 46-character margin).
- **Suggested fix:** on `partial`, call `clear_extract_inventory`, record a finding (there is no register code yet), and print the version.

### R3-05 · S3 · Identification metadata goes stale on re-extract
- **Where:** `src/docushift/extractor/unpacker.py:338-348` (`engine_generator_raw`, `output_roots` written only when non-empty), `:376-380` (`api_roots` written only when non-empty), `state.py:534-541` (`engine_folder_map` is upserted and never cleared)
- **What:** a re-extract that finds no roots, no API trees or no generator string leaves the previous run's values in place. Stage 5 and Stage 7 trust the recorded `api_roots`/`output_roots` over a re-walk (`converter/driver.py:274,760`, `sync/distributor.py:639-642`).
- **Failing scenario:** a new package that dropped its Javadoc tree, or a manual engine pin with no root rule followed by `extract --force`. `_api_files=0`, but `api_roots` still names `w\api`.
- **Confirmed:** n/a (S3). Repro `test_api_roots_metadata_survives_a_package_that_dropped_its_api_tree`. The corpus has not reached it (packages have not changed upstream).
- **Suggested fix:** always write all three keys (an empty string means "measured, none"), and delete the folder map before re-recording it.

### R3-06 · S3 · Download resume never happens in practice
- **Where:** `src/docushift/downloader/fetcher.py:266-273` (resume only if `known_etag`), `:337-346` (`zip_etag` recorded only after a successful transfer), `:107-115` (ETag preferred even when weak), `:285` (206 accepted without checking `Content-Range`)
- **What:** (a) An interrupted *first* download has no recorded validator, so the kept `.part` is discarded on the next run. The test `test_a_truncated_transfer_leaves_a_part_and_no_canonical_file` pins that the part is kept, but not that it is ever resumed. (b) The docsite serves weak ETags, and RFC 9110 §13.1.5 forbids a weak tag in `If-Range` (a compliant server answers 200). (c) A partial that is already complete makes the server answer 416, which is recorded as FAILED on every run until `--force`.
- **Failing scenario:** a 900 MB download killed at 95% is fetched again from byte 0.
- **Confirmed:** partly. All 52 `zip_etag` values in `state.db` start with `W/"`. The server's actual If-Range behaviour is **unconfirmed**, because no network calls were allowed. Output is correct either way (a full re-fetch), hence S3.
- **Suggested fix:** record the response validator (in state or a `.part` sidecar) when streaming starts. Prefer `Last-Modified` when the ETag is weak. Check that the `Content-Range` start equals `resume_from`, and treat 416 as "restart".

### R3-07 · S3 · `safe_extract` silently writes member names that Windows cannot hold
- **Where:** `src/docushift/extractor/safe_unzip.py:72-83`
- **What:** these members are written through the `\\?\` prefix without any check: case-insensitive duplicates (the second silently overwrites the first, and `written` still counts both), names ending in `.` or a space (created, but invisible to every unprefixed reader), and `ab:c.htm` (an empty file `ab` with the content in an alternate data stream).
- **Failing scenario:** a ZIP holding `Topic.htm` and `topic.htm` reports `written=2`, but disk has 1 file named `Topic.htm` with the content of `topic.htm`.
- **Confirmed:** n/a (S3). Repro `repro_names.py` gave `written=4`, `walk_files=3`, `trailing.` that `exists()` reports missing, and `ab` empty. No case duplicates, illegal characters or trailing dots in any of the 54 real ZIPs.
- **Suggested fix:** refuse such members (or report them as findings), and count distinct casefolded destinations.

### R3-08 · S3 · The "never raises" contracts leak on the unpack and download-current paths
- **Where:** `src/docushift/extractor/unpacker.py:231` (catches only `OSError`/`BadZipFile`); `src/docushift/downloader/fetcher.py:219-229` (`sha256_of(target)` and `stat()` sit outside the `try`)
- **What:** `zipfile` raises `NotImplementedError` (for example Deflate64), `RuntimeError` (encrypted), `EOFError` and `zlib.error`. These escape `extract_many` and leave a half-written `.part`. On the download side, an `OSError` while hashing the existing ZIP (a file held by a scanner) propagates through `pool.map` and aborts the whole download batch.
- **Failing scenario:** one Windows-built package compressed with Deflate64 stops a 200-version extract.
- **Confirmed:** n/a (S3). The real ZIPs use only methods 8 and 0 and none is encrypted.
- **Suggested fix:** catch `Exception` around `safe_extract` (as `download_one` already does around `_fetch`), and move the CURRENT check inside the guarded block.

### R3-09 · S3 · `archive download --from-file` writes the pipeline's `version_state`, and `--extract` has no staging
- **Where:** `src/docushift/downloader/fetcher.py:418-428` (always records state); `cli.py:2863` (`pin_manual=False`); `cli.py:2894-2907` (`_archive_target` does not require `is_archived`); `cli.py:2886-2890`
- **What:** the archive variant records `status=DOWNLOADED`, `checksum` and `download_path=archive/...` into the same row the pipeline uses. `--extract` unpacks straight onto `archive/<slug>-<version>/` (no `.part`/swap, so stale files survive a re-extract) and does not catch `BadZipFile`.
- **Failing scenario:** running `archive download --product ems --version 10.4.0 --from-file x.zip` on an eligible, converted version moves its status back to DOWNLOADED and replaces its checksum. The next `download` then sees a mismatch and fetches the package again. This contradicts §4.3/§3.8's "outside the working set".
- **Confirmed:** n/a (S3). Traced in code. `state.db` holds no archive pulls.
- **Suggested fix:** with `pin_manual=False`, record nothing in `version_state` (put audit data under a separate metadata key). Route `--extract` through the same staging and swap.

### R3-10 · S3 · Absolute `download_path`/`extract_path` in `version_state` go stale when a family moves
- **Where:** `src/docushift/downloader/fetcher.py:340,424`; `unpacker.py:246`
- **What:** absolute paths are recorded at write time and never refreshed. `content_root` deliberately stores a relative name for exactly this reason, but these two columns do not.
- **Failing scenario:** after the activespaces family was relocated, 7 rows still point to `families\en-us-tib-messaging\...`, which no longer exists.
- **Confirmed:** yes (`state.db`, 7 rows). Harmless today, because the only reader (`progress()`) tests `bool()`. Every consumer derives paths from `ConfigManager`.
- **Suggested fix:** store a path relative to the workspace, or store a flag. Document that the columns are never used as paths.

### R3-11 · S3 · `forget_version`/`forget_product` leave the Stage 4/5 tables behind
- **Where:** `src/docushift/state.py:409-421`
- **What:** `csh_source`, `asset_inventory` and `output_map` are not in the delete list. The test `test_forget_version_clears_every_table` covers only the four original tables.
- **Failing scenario:** an `--allow-deletes` import drops a version that is later re-added. `progress()` then counts it as converted (from the orphaned `output_map`), and CSH resolution has orphaned rows to read.
- **Confirmed:** n/a (S3).
- **Suggested fix:** add the three tables (and `findings` if wanted) to both delete lists, and extend the test.

### R3-12 · S3 · CURRENT paths never clear `error`/`status`
- **Where:** `src/docushift/downloader/fetcher.py:220-229`; `unpacker.py:199-216`; read by `reporting/status.py:106`
- **What:** after a failed `download --force` (status `ERROR`, error set), the next plain run reports `current` but leaves the error in place. The funnel then counts the version under `errors` indefinitely. `design.md` §5.1 step 3 says to "mark it downloaded".
- **Failing scenario:** a transient network failure on a re-fetch leaves a version showing as errored in `status`, although its package is fine.
- **Confirmed:** n/a (S3). The 4 real `ERROR` rows (sb-hp-fix, "did not return a readable ZIP") are genuine failures.
- **Suggested fix:** on CURRENT, clear `error` (and set the status only if it is behind).

### R3-13 · S3 · Recorded root lists use OS-native separators
- **Where:** `src/docushift/extractor/unpacker.py:347,379` (`str(root.relative_to(tree))`)
- **What:** `output_roots`/`api_roots` are stored as `doc\html` on Windows, while `csh_source.path` is POSIX (`as_posix()`). On a POSIX reader, `tree / "doc\\html"` names a file that does not exist, and the non-empty record suppresses the re-walk.
- **Failing scenario:** a `state.db` or tree moved to a Linux runner. Every recorded root resolves to nothing.
- **Confirmed:** yes, for the format (`state.db`: `output_roots='doc\\html'`). The consequence is unconfirmed (no POSIX run).
- **Suggested fix:** write `as_posix()`, matching `csh_rows`.

### R3-14 · S4 · Dead and write-only state API
- **Where:** `state.py` `versions_with_status`, `status_counts`, `batches`, `forget_product`, `get_engine_folder_map`, `get_asset_inventory` (0 callers in `src/`); `catalog.py:1017 clear_extract_inventory` (0 callers); metadata key `engine_generator_raw` (written at `unpacker.py:341`, never read)
- **What:** the `engine_folder_map` and `asset_inventory` tables are written on every extract and never read.
- **Confirmed:** n/a
- **Suggested fix:** delete them, or wire them up (`clear_extract_inventory` is the fix for R3-04).

### R3-15 · S4 · `CONTENT_SEGMENTS` duplicates `apirefs.CONTAINER_SEGMENTS` and has already drifted from it
- **Where:** `src/docushift/extractor/content_root.py:126-131` vs `sync/apirefs.py:38-43`
- **What:** apirefs gained `bpmhelp`, and content_root did not. That is harmless today, because amx-bpm's `bpmhelp/` never stands alone.
- **Confirmed:** n/a
- **Suggested fix:** move the shared list to a neutral module (for example `apiref.py`) that both import.

### R3-16 · S4 · Docstrings in the code contradict the code
- **Where:** `fetcher.py:360-376` (says "completion order" and "fires from the worker thread". In fact `pool.map` yields in input order on the main thread, so one slow version holds back the progress lines of finished ones); `unpacker.py:40` ("these five counts", but there are six outcomes); `unpacker.py:184` ("Never raises", see R3-03/08)
- **Confirmed:** n/a
- **Suggested fix:** use `as_completed` if completion order is wanted, otherwise fix the text.

## Edge notes (for the cross-stage pass X1)
- **`extract_zip_checksum` is convert's only currency key** (`converter/driver.py:216-230`). `extract --force` on an unchanged package (for example after an identify or roots fix) changes `output_roots`/`api_roots`/engine without invalidating the converted tree. This is the same shape as the Phase 21 carried-forward item, one stage earlier.
- **Recorded `api_roots`/`output_roots` outrank a re-walk** in convert and sync. "Absent" and "empty" are the same thing today (the keys are written only when non-empty), so the drivers' docstring claim that "a recorded empty list and a located empty list cannot disagree" holds only because both fall back to the walk. See R3-05 and R3-13.
- **`content_root`**: written by extract (all paths) and measure-only. Read by `converter/driver.py:791` and `sync/distributor.py:240` through `content_root.of`. The 6 EMS versions have a checksum but no `content_root` (never re-run since Phase 15b), and readers fall back to the live resolve, which gives the same answer. `inventory.py` should be a third reader (R3-02).
- **`csh_source`** is replaced wholesale per walk and read by convert (`driver.py:827`). It is overwritten even by a partial walk (R3-04).
- **`version_state.status`** is a single "furthest point" column that ERROR overwrites. Download, extract and the archive variant all write it. `progress()` deliberately ignores it in favour of evidence columns, but `errors` there reads the `error` text, which goes stale (R3-12).
- **The `versions.csv` inventory columns** are read by `cli.py:1416` (the measure-only dry run) and `cli.py:1632` (a totals view). Extract's CURRENT test treats non-blank columns as "measured for this package", which is not guaranteed (R3-03, R3-04).
- `engines/roots.py:88,127` (`iterdir` without a guard) runs inside `identify` after the swap. An unreadable directory there raises out of `extract_one` (R4 should confirm).

## Test gaps (real-data paths only)
- No inventory test with a wrapper directory around `pdf/`/`doc/`. This is the shape of 46 of 50 sampled packages and of every wrapped tree on disk (R3-02).
- No test of a re-extract whose post-swap step fails, or of the CURRENT decision when the columns come from a previous package (R3-03).
- No test that a resumed download happens after a first-time interruption, or with a weak ETag (`W/"…"` is what the docsite returns; R3-06).
- `test_forget_version_clears_every_table` does not cover `csh_source`/`asset_inventory`/`output_map` (R3-11). The deletes are reachable through `catalog import --allow-deletes`.

## Docs drift
- `design.md` §6.1 step 5, `architecture.md` §3.9 and the `inventory.py` docstring say a partial walk "leaves the columns blank". The code leaves the previous values (R3-04).
- `architecture.md` §4.5 says that "only the readers that address content by name use it — `router.source_folders`, and `apirefs`". `inventory.py`'s top-level `pdf`/`doc` test also addresses content by name, and does not use it (R3-02).
- `design.md` §5.1 steps 4 and 8 promise resumption "from the partial length". In practice it never happens (R3-06). Step 3 says "mark it downloaded", but CURRENT writes nothing (R3-12).
- `design.md` §6.1 says "Five outcomes… `extracted`, `current`, `no-package`, `refused`, `failed`". `measured` is a sixth (it is documented in §3.9, but not here).
- `design.md` §5.2 says the archive variant is "identical but targets the archive path". It also overwrites the pipeline's `version_state` (R3-09).
- `architecture.md` §4.4 says "Only the two writers of a staged tree call it". `long_path`/`walk_files` are now used by 8 more modules (`engines/flare,webworks`, `reframe/driver`, `sync/apirefs,distributor`, `validation/artifacts,links`). This overlaps R1.

## Checked and fine
- **Containment:** every member is validated before any is written. `..`, leading `/`, a leading drive letter and backslash forms are refused. A refused archive leaves no tree (tests, plus code reading). R3-01 is the exception.
- **Long paths:** for all 54 real ZIPs, the member file count equals the `walk_files` count of the extracted tree. All 6 EMS versions wrote their 3 members of 265 characters through the prefix (plain `rglob` sees 3 fewer).
- **Inventory totals:** `_api_files + _doc_files` equals the on-disk file count for all 60 extracted trees, including EMS's over-260 files (`os.scandir` lists them). No tree walked partially.
- **Content root:** the recorded value equals live resolution for all 48 recorded versions. 13 flat packages record `""`. The tibco-streaming 11.1.0/11.1.1 wrapper (`spotfire-streaming-*`, not the slug) resolves correctly, which supports the decision not to match on the stem. A scan of 1,867 cache versions found lone `doc`/`pdf`/`html` correctly not descended (448/51/23). 10 lone non-segment dirs (for example sf-kbn `user-guide/`) would be descended, which is harmless per §4.5.
- **Checksums:** `version_state.checksum`, `zip_size` and `extract_zip_checksum` match sha256 and size on disk for all 47 ZIPs that have a state row (the other 7 are R3-10).
- **No `.part` residue** in any `downloads/` or `extracted/`. The extract staging is swept before each run (`remove(staging)`).
- **Member-name hazards** across the 54 ZIPs: 0 non-ASCII names, 0 backslashes, 0 symlinks, 0 duplicate or case-duplicate names, 0 Windows-reserved characters. Compression is deflate or stored only, and nothing is encrypted.
- **Download integrity:** the move into place is atomic, and `is_zipfile` runs before it. The 4 real `ERROR` rows show the HTML-page rejection working. urllib3 2.7 enforces Content-Length, so a short body raises instead of truncating silently.
- **`--from-file`** validates the ZIP, copies rather than moves, pins `zip_source=manual` (download variant only) and records `zip_origin_path` (2 real rows).
- **State threading:** reads and writes share one RLock, and `transaction()` holds it for the batch. Schema-version refusal is in place.
- **§4.3:** download and extract both use `iter_versions(eligible_only=True)`. An archived row is acted on only if a human flips it to eligible, which is the documented route.
- **Tests:** all 176 R3 tests pass at `review-base`.
