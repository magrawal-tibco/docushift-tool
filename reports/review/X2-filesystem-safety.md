# X2 — Filesystem & Windows safety: findings
Base: review-base-x (30f906b) · Date: 2026-10-05

| S1 | S2 | S3 | S4 |
|---|---|---|---|
| 2 | 4 | 8 | 1 |

Repros and scripts: `C:\tmp\review-X2\` (`repro\test_x2_reframe.py`, `repro\test_x2_convert.py`, `swap_lock.py`, `swap_stage_lock.py`, `eol.py`, `casecheck.py`, `longfiles.py`, `margin.py`). Every repro imported the review tree's `src` (asserted). For "open in Excel" I held a CPython handle, which opens without `FILE_SHARE_DELETE` as Excel does, or set the file read-only for write locks, as R1 and R12 did. Excel itself was not run.

## Findings

### X2-01 · S1 · A swap deletes the live tree before it knows the rename will work; after a `--force` run, the next run reports the gutted tree as `current`
- **Where:** `utils/swap.py:61-83` (`remove(target, attempts=1)` at :76, then `staging.replace(target)` at :78). It is reached from `converter/driver.py:433`, `reframe/driver.py:610`, `extractor/unpacker.py:273` and `sync/distributor.py:398, :521, :638, :752`. Currency keys that survive the failure: `converter/driver.py:265-277` and `:436-449`; `reframe/driver.py:360-372` and `:612-619`.
- **What:** `shutil.rmtree` deletes the old tree file by file and stops at the first locked file. Every retry deletes more, and the final raise leaves a target holding only the locked file and whatever sorts after it. If the *staging* rename fails instead (a scanner handle, the documented race), the target is already gone completely. The checksums are written only after a successful swap, so a run that was skipped because of `--force` reads as current against a tree that is now mostly empty.
- **Failing scenario:** The user has `rename-map.csv` open in Excel (the documented way to edit it) and runs `reframe --all --force` (the step INDEX says is needed after converter fixes). The run reports the version as FAILED (WinError 32). The real EMS 10.5.1 tree drops from 199 files to 6. The next plain `reframe` returns `current`, and `sync` then publishes the gutted tree. Convert behaves the same way: a held `toc.yml` during `convert --force` leaves `['toc.yml']`, and the next run is `current`. If a handle is on the staging tree instead, the target is deleted completely (`swap_stage_lock.py`: `target exists: False`). For `sync`, a published version folder disappears until the next sync. Unconfirmed chain: a gutted *extracted* tree has its checksum blanked (unpacker.py:271), so a `convert` run before the re-extract converts what is left and swaps that in.
- **Confirmed:** yes. `swap_lock.py` on a copy of the real EMS 10.5.1 reframed tree: 199 → 6 files with `rename-map.csv` held, 199 → 5 with `review-queue.csv` held. `test_x2_reframe.py::test_a_locked_rename_map_guts_the_tree_and_next_run_says_current` and `test_x2_convert.py` both pass, so the next run is `CURRENT` on the review code.
- **Suggested fix:** In `swap`, rename the target aside (`<target>.old`), rename staging in, then delete `.old`. If the second rename fails, rename `.old` back. Nothing is deleted until the new tree is in place, and a locked file fails the first rename cleanly.

### X2-02 · S1 · `rename-map.csv` pins are lost through any failed or interrupted reframe swap, without a word
- **Where:** `reframe/driver.py:497` (pins read only from `target/rename-map.csv`), `:778` (rewritten into staging), `:610` (swap); `reframe/renames.py:116-137` (an absent map reads as "no overrides"); `utils/swap.py:76`.
- **What:** The map is the only store of human-chosen page names, and it lives inside the tree that `swap` deletes. X2-01's partial delete removes it whenever a locked file sorts after it. `review-queue.csv` does, and the docs tell writers to open it in a spreadsheet. A failed staging rename or a kill between remove and rename also removes it. The next run sees no map: the digest differs, so it re-merges with computed names. `--renormalize` was never asked for, and no finding code covers a map that vanished.
- **Failing scenario:** A writer pins `users-guide/user-guide.md → users-guide/my-chosen-name.md` (applied). Later they have `review-queue.csv` open while `reframe --force` runs. The swap fails and deletes `rename-map.csv` ("r-e-n" sorts before "r-e-v"). The next `reframe` writes `user-guide.md` again, so the published URL moves, and the run reports nothing about it.
- **Confirmed:** yes. `test_x2_reframe.py::test_a_locked_review_queue_guts_the_tree_and_drops_the_pins`: after the forced run the tree is `['review-queue.csv', 'toc.yml']`. The next run is `reframed` and the pinned page is gone.
- **Suggested fix:** X2-01's swap fix closes the lock and kill cases. Also store the approved pins outside the swapped tree (state.db beside `_RENAME_DIGEST`, or a backup copy), and raise a warning when the digest is set but the map is missing.

### X2-03 · S2 · A rename-map pin is used as a write path without checks, so `..` or an absolute path writes outside the tree
- **Where:** `reframe/renames.py:131-136` (`new_path` accepted as typed), `reframe/packer.py:815-819` (`page.path = wanted`), `reframe/driver.py:684-688` (`long_path(staging / page.path)`, where `long_path` absolutizes and so collapses the `..`).
- **What:** Nothing confines `new_path` to the tree. The user guide invites "a human or a model" to write better names.
- **Failing scenario:** `new_path` set to `../10.5.0/user-guide.md` overwrites the merged page of the sibling version 10.5.0 in `reframed/`. An absolute `C:/…/pwned.md` is written exactly there. The version then fails its self-check with "a page write landed outside the layout" and the staging tree is removed. The write outside the tree stays, and nothing names it.
- **Confirmed:** yes. `test_a_rename_pin_escapes_the_staging_tree`: the sibling file's content was replaced by the merged page. `test_an_absolute_pin_writes_outside_the_workspace`: the outside file exists.
- **Suggested fix:** In `renames.load`, refuse (as `RENAME_MAP_REFUSED`) any `new_path` that is absolute, contains `..`, a drive or `:`, or does not end in `.md`. Also apply the safe_unzip backstop (`root in destination.parents`) before each page write.

### X2-04 · S2 · A CSV or YAML saved by Excel/Notepad in the ANSI code page crashes the run with a traceback that names no file
- **Where:** `utils/csvio.py:190-195` (strict `utf-8-sig`), reached from `catalog.py:285, :311` (every command) and `reframe/renames.py:127`. `renames.load` catches only `OSError`, and its first call is the currency check at `reframe/driver.py:360-364`, outside R9-11's `try` at :385-392. Also `sync/distributor.py:811, :884` (strict reads of the hand-edited `version.yml` and doc-class maps), with `finish_product` unguarded at :953.
- **What:** Excel's default "CSV (Comma delimited)" save writes cp1252, which turns `™` into byte 0x99. Each of these readers raises `UnicodeDecodeError`, and nobody catches it. R11-07's fix (theme BC) covers `validate` only, and R9-11's fix covers only the `try` it was added to.
- **Failing scenario:** (a) `products.csv` (751 non-ASCII characters today) saved as ANSI makes every command end in `UnicodeDecodeError: 'utf-8' codec can't decode byte 0x99 in position 154`, which names no file. (b) A `rename-map.csv` saved as ANSI after a title edit makes `reframe --all` stop at that version with a traceback, skipping every version after it and leaving the findings run open. (c) A `version.yml` saved as cp1252 aborts `sync` in `finish_product` after the copies, so the drop-downs and 301 maps of that product and every later product are not written. (c) is traced in code only.
- **Confirmed:** yes for (a) (`C:\tmp\review-X2\enc`, real products.csv re-encoded) and (b) (`test_a_cp1252_rename_map_raises_out_of_reframe_one`: raised from driver.py:363). (c) is by code trace.
- **Suggested fix:** Read hand-edited files through one helper that catches `UnicodeDecodeError` and raises a domain error naming the file and saying "save as CSV UTF-8". Have `reframe_one` and `finish_product` turn that error into a FAILED row or finding.

### X2-05 · S2 · `versions.csv` open in Excel aborts `reframe` partway through the selection, after the swap
- **Where:** `reframe/driver.py:611` → `_measure_merged` → `:658 catalog.record_reframe_inventory` → `save()` raises `CatalogError`, which is not in `except (OSError, UnicodeDecodeError)` at :390. The same call sits on the `current` path (`:377`). Same pattern in convert's `current` path, `converter/driver.py:276`, which is outside `_build`'s `try`. `convert_many` (:1044) has no guard.
- **What:** R1-04/R2-05 turned the lock into a clean `CatalogError`, and extract and convert's build path catch it. Reframe does not, so the exception leaves `reframe_one` ("never raises") and `reframe_many`.
- **Failing scenario:** With `versions.csv` open in Excel, `reframe --all` swaps in the first version's new tree. It then raises before writing that version's checksums, skips every remaining version, and leaves the findings run unfinished. After batch 4's R12-03 fix this becomes a clean error instead of a traceback, but the run is still cut off.
- **Confirmed:** yes. `test_a_locked_versions_csv_escapes_reframe_one`: `CatalogError … It is usually open in Excel`, the tree is swapped in, and the metadata is `{}`. The convert `current` path is by code trace.
- **Suggested fix:** Catch `CatalogError` in `reframe_one` (and around convert's current-path `_measure_output`) as a FAILED row, or record the inventory column after the run as R4-08 did for convert.

### X2-06 · S2 · `review-queue.csv` is documented as "meant to be edited", but every re-merge rewrites it from scratch
- **Where:** `reframe/driver.py:777` → `reframe/review.py:183-189` → `csvio.write_rows` (`extrasaction="ignore"`, fixed `COLUMNS`). Docs: `quickstart.md:172` ("The last two are the ones meant to be edited"), `user-guide.md:940`.
- **What:** Nothing reads the old queue back. A writer's notes, decision column or edited cells disappear on the next re-merge (any convert change, policy edit, algorithm bump, pin edit or `--force`), with no warning. This is Phase 16's bug class.
- **Failing scenario:** A writer adds a `decision` column and works 40 rows. The next `reframe --all --force` writes back six columns and the queue as it was before.
- **Confirmed:** yes by code. Today all 14 queues on disk carry the stock six-column header, so nothing has been lost yet.
- **Suggested fix:** Either say in the docs that the queue is read-only output (decisions go to `reframe.yaml`), or carry over unknown columns and cells, keyed on `page_path`, the way `version.yml` keeps its hand rows.

### X2-07 · S3 · Converted trees mix CRLF and LF, and which a file gets depends on whether any fragment in it was retargeted
- **Where:** CRLF on Windows from `write_text` without `newline=`: `converter/driver.py:532` (topics), `:555` (generated pages), `:558` (`toc.yml`), `:564` (`metadata.yml`), `transforms/csh.py:280` (`csh.yml`). LF from the rewrite: `converter/driver.py:743` reads with universal newlines, then `:765-767` and `:797` write with `newline=""`. Also CRLF: `sync/distributor.py:510-519, :632, :743-749, :777, :820, :896`. LF everywhere: `reframe/manifest.py:132`, `origins.py:428`, `reframe/driver.py:688`.
- **What:** This is the cause of the batch 2 observation. Every page is first written CRLF, and `_retarget_fragments` rewrites only the pages (and `toc.yml`) where it moved an anchor, in LF. So line endings differ by file, and differ by platform: a Linux run writes LF everywhere.
- **Failing scenario:** Measured in `output\`: 16,061 `.md` CRLF and 6,589 LF. Of the LF files, 6,413 contain a `](…#…)` link. Of the CRLF files, 200 do, and those are the unplaced fragments. `toc.yml`: 12 CRLF, 24 LF. `metadata.yml` 36 CRLF, `csh.yml` 7 CRLF, `301.yml` 27 LF. `reframed\`: all 1,493 `.md` LF and the manifests LF, but `metadata.yml` (copied from output) CRLF. A published tree mixes both, and a tree built on another OS differs in size from one built here, so `_identical` re-copies it.
- **Confirmed:** yes (`eol.py`, plus the fragment correlation over all of `output\`).
- **Suggested fix:** Write every generated text file with `newline="\n"` (one helper), as `manifest.write` already does. CSVs keep CRLF and the BOM on purpose.

### X2-08 · S3 · Engines read through the plain path while extract writes through `\\?\`; the margin today is 5 characters
- **Where:** `engines/flare.py:1351-1365` (`os.walk` + plain `read_text`, which reports `CONTENT_MISSING`), `engines/docbook.py:502` (`root.rglob`, which drops files over 260 **silently**), `engines/webworks.py:1634-1638`, `:1773` (book identity by `rglob`), `converter/driver.py:509` (`_measure_output`), `:741` (`_retarget_fragments`), `:1123` (`_find_csh`), `transforms/assets.py:228-229` (plain `copy2`, counted as dangling). Converter staging writes are also unprefixed (`:530-532`).
- **What:** `safe_extract` writes any length, but nothing after it reads past 260. Whether a topic converts therefore depends on how long the workspace root is.
- **Failing scenario:** The longest non-API topic is ActiveSpaces 4.10.0 `…\Administration\Deployment-Scenario-for-Ru…` at **255** characters, and TRA Administrator 5.13.0 is at 252, both under the 24-character `C:\github\docushift-tool`. A clone at `C:\Users\<name>\source\repos\docushift-tool` makes those topics `CONTENT_MISSING`, and a DocBook topic past the line vanishes with no finding. Streaming's margin is 60.
- **Confirmed:** yes for the lengths (`margin.py`, `longfiles.py`: 18 files over 260 in `families\`, all in EMS `dotnetdoc`). The failure mode is by code; no topic crosses the line today.
- **Suggested fix:** Use `walk_files` and `long_path` in the engines' walkers and readers and in the converter's walks and writes, as reframe and sync already do.

### X2-09 · S3 · `sync`'s `_identical` walks with `rglob`, so a merged tree holding a file over 260 characters never reads as current
- **Where:** `sync/distributor.py:997-998`.
- **What:** The source side omits over-length files but the destination side, held under the ceiling, lists them. The two sets never match, so every run re-copies. R10 left this as an edge note for X2.
- **Failing scenario:** `reframed\…\tibco-runtime-agent\5.13.0\…\to-create-file-based-repository-domain-using-gui.md` is 262 characters. `rglob` finds 505 files where `walk_files` finds 506. Today this is latent, because TRA Runtime Agent is `publish: false`. It goes live when TRA is set to publish merged.
- **Confirmed:** yes. `_identical(real tree, fresh copy2 copy)` returns `False`.
- **Suggested fix:** Build both sets with `walk_files` and compare with `filecmp` through the prefixed paths.

### X2-10 · S3 · Theme F's name rules hold only for ZIP members: the sitemap cache accepts a drive letter, and unzip accepts device names
- **Where:** `discovery/sitemap.py:63` (`unquote` *after* taking the last segment) and `:219-221` (`directory / name`). `extractor/safe_unzip.py:61-72` (`_unwritable` has no `CON`/`NUL`/`AUX`/`COMn`/`LPTn` check).
- **What:** A `<loc>` ending `D%3Aevil.xml` gives the name `D:evil.xml`, and joining that onto the cache directory produces a path relative to drive D's current directory. A `<loc>` ending `..%2F..` gives `..`, a directory, which crashes the write. A ZIP member `aux.htm` is written through the prefix, but plain readers then open the device.
- **Failing scenario:** Computed: `SitemapCache.path("D:evil.xml") → D:evil.xml`, `path("../../..") → …\sitecache\..`.
- **Confirmed:** yes for the path computation. There is no real trigger: the docsite's own sitemaps, and 0 device names across the 101,809 members of the 54 real ZIPs.
- **Suggested fix:** In `SitemapCache.path`, reuse safe_unzip's segment rules (refuse `:`, `..`, empty, reserved characters) and add device names to `_unwritable`.

### X2-11 · S3 · Slug and version cells are used as path segments as typed; `..` makes a swap delete a whole family or product folder
- **Where:** `catalog.py:312-313` (only `strip()`/`lower()`), `config.py:369-418` (`extract_path`/`output_path`/`reframed_path` join raw), `sync/distributor.py:208-226` (raw `product.slug`); the swap's `remove(target)`.
- **What:** Nothing confines a slug or version to one segment.
- **Failing scenario:** Computed with the review `ConfigManager`: version `..` gives `extract_path` = `families\en-us-tibco-general\extracted`, so the swap would rmtree every extracted package in the family. Version `5.2.0/..` resolves to the product folder. Slug `../../escape` resolves outside `output\`.
- **Confirmed:** yes for path resolution only; nothing was deleted. No real row triggers it: of 5,181 versions, the odd ones are `Cloud™`, `(iPaaS)` and `6.0.1.`, all safe, and slugs include `c++` and commas.
- **Suggested fix:** Validate slug and version on `load()` (no `/`, `\`, `:`, `..`, no leading or trailing dot or space) and raise `CatalogError` naming the row.

### X2-12 · S3 · Pins are compared case-sensitively, so two pages that differ only in case collide on NTFS and the error message names the wrong cause
- **Where:** `reframe/packer.py:799-809` (`holders` keyed on the exact `PurePosixPath`).
- **What:** `User-Guide.md` and `user-guide.md` count as two paths. On Windows they are one file, so the second write replaces the first.
- **Failing scenario:** Pin the installation page to `User-Guide.md` beside the computed `user-guide.md`. On Windows the version fails with "a page write landed outside the layout" (misleading). On Linux both files are written, and a Windows clone of the published repo silently keeps one.
- **Confirmed:** yes on Windows (`test_a_pin_differing_only_in_case_collides_on_ntfs`). Linux behaviour is by code.
- **Suggested fix:** Key `holders` on `str(path).casefold()` and report it as `RENAME_MAP_REFUSED`.

### X2-13 · S3 · The published artifacts that keep hand-edited rows are rewritten in place, not by temp file and rename
- **Where:** `sync/distributor.py:820` (`version.yml`), `:896` (doc-class `redirects.yml` / `301.yml`), `:777` (product `metadata.yml`).
- **What:** `write_text` truncates first. A kill or a full disk mid-write leaves a short file. If the short YAML still parses, the next merge keeps only the rows it can read, and the hand rows ("the only copy", per :813) are gone without a word.
- **Failing scenario:** A hard kill during `finish_product` on a product with a hand-edited `version.yml`.
- **Confirmed:** unconfirmed. I did not reproduce a kill mid-write; the window is one small file.
- **Suggested fix:** Write to `<name>.tmp` and `replace_file` it, as `csvio.write_rows_together` and the sitemap cache do.

### X2-14 · S3 · The ZIP download's final rename is the one `os.replace` without the scanner retry, and `swap.py`'s module docstring still says none is needed
- **Where:** `downloader/fetcher.py:338` (`partial.replace(target)`) and `:432`; `utils/swap.py:21-24` vs `:86-94`.
- **What:** Phase 33 showed a single-file rename losing to WinError 32 from the indexer and added `replace_file`. The downloader, which writes the largest freshly closed files the scanner inspects, still renames once.
- **Failing scenario:** The on-access scanner holds the just-closed `.zip.part`, and the version reports a failed download. The `.part` is kept, so a re-run recovers.
- **Confirmed:** unconfirmed (no scanner race reproduced).
- **Suggested fix:** Use `replace_file` at both sites and correct the module docstring.

### X2-15 · S4 · Extract's failure path cleans `.part` with plain `rmtree(ignore_errors=True)`
- **Where:** `extractor/unpacker.py:255, :263`.
- **What:** The path is not prefixed, so files over 260 in the staging tree (EMS has 265-character members, 270 under `.part`) are silently left behind. The next run's `remove(staging)` (prefixed) cleans them up, so the only effect is residue in the meantime.
- **Confirmed:** by code. `utils/swap.remove` exists for exactly this case (its docstring says so).
- **Suggested fix:** Call `remove(staging)` in a `try` at both sites.

## Write-path table

| artifact | atomic? | lock handled? | long-path safe? |
|---|---|---|---|
| `config/products.csv`, `versions.csv` | yes: `.tmp` + lock probe + `replace_file`; two-rename window between files (documented) | yes, `CatalogError` naming the file. Extract and convert catch it; reframe does not (X2-05) | n/a |
| `cache/sitemaps/*`, `manifest.json` | yes: `.part` + `replace_file` | retried (WinError 32) | n/a; name check weak (X2-10) |
| `cache/state.db` | SQLite transactions | not checked | n/a |
| `reports/coveo-sitemap.csv` | no (`open("w")`, cli.py:995) | no, traceback (R12-05, batch 4) | n/a |
| `report --export` file | no | yes (`ClickException`) | n/a |
| `families/*/downloads/*.zip`, `--from-file` | yes: `.part` + `os.replace` | reported FAILED, no retry (X2-14) | n/a |
| `families/*/extracted/<slug>/<ver>` | staging + swap; target gutted on a lock (X2-01) | swap retries, then FAILED | yes (writes, swap); failure-path rmtree no (X2-15) |
| `output/<fam>/<slug>/<ver>` (topics, toc/metadata/csh/301) | staging + swap (X2-01) | FAILED; after `--force`, gutted tree reads `current` (X2-01) | writes no (fail loudly); `_measure_output`/retarget `rglob` (X2-08); max 192 today |
| `reframed/…/<ver>` incl. `rename-map.csv`, `review-queue.csv` | staging + swap (X2-01, X2-02); queue edits overwritten (X2-06) | FAILED; tree gutted, pins lost (X2-02) | yes (pages, assets, `walk_files`); max 262 today |
| published `online-help/<seg>` | staging + swap; `.part` removed on exception | FAILED; folder missing until next sync | copy yes; ceiling checked (R1-01 fix holds); `_identical` no (X2-09) |
| published `user-guides` etc. | staging + swap | FAILED row | flat; ceiling checked per name |
| `-resources/api-references/<seg>` | staging + swap | FAILED row | yes; `_overflowing` first |
| `-resources/archives` | staging + swap, no cleanup (R10-09, batch 4) | FAILED row | short paths |
| product `metadata.yml`, `version.yml`, doc-class `redirects.yml` / `301.yml` | no, in-place (X2-13) | no: `finish_product` unguarded (X2-04) | short paths |

## Checked and fine
- **Zip-slip (theme F holds in unzip):** `..`, absolute, `\`, a `:` in any segment, reserved characters, trailing dot or space, and case-duplicate files are all refused before any write, with a `root in destination.parents` backstop (`safe_unzip.py:96-128`).
- **Asset hrefs:** backslashes are normalized before resolution (`links.py:91`), a leading `..` is refused as an escape (`assets.py:150`), and an absolute or scheme-style href is never copied.
- **Case:** 0 links that resolve only case-insensitively among 183,924 relative links in `output\` and 14,885 in `reframed\` (`casecheck.py`). There are no case-duplicate (slug, version) keys. Document folders de-duplicate by lower-cased filename (`documents.py:171-176`). Merged directories are lower-cased (`asset_destination`).
- **260 ceiling, fixes holding:** reframe's `_Source`, `_measure_merged` and page/asset writes use `walk_files`/`long_path` (R9-10's fix holds). `sync` runs `over_limit` before every online-help copy and checks document names (R1-01/R1-08 hold). No directory reaches 248 in `families\`, `output\` or `reframed\`.
- **Catalog CSV round-trip:** BOM + CRLF, `utf-8-sig` read, and temp files removed in `finally` (`csvio.py:212-239`). The lock probe raises before any rename.
- **`.part` hygiene:** convert removes staging on every exception (R4-07 fix) and on "nothing converted" (R4-06). Reframe removes it on self-check failure. Sync's three placers remove it on `BaseException` (archives excepted, R10-09).
- **Download:** a truncated or non-ZIP body never reaches the canonical name. A changed validator discards the partial.

**Not checked:** real Excel (I used handles and the read-only attribute instead), a hard kill mid-write, behaviour on Linux or macOS, a synced target tree (no published workspace measured for line endings), and `state.db` locking.
