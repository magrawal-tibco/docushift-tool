# X3 — Re-run consistency: findings
Base: review-base-x (30f906b) · Date: 2026-10-05

| S1 | S2 | S3 | S4 |
|---|---|---|---|
| 2 | 3 | 6 | 1 |

**Workspace.** `C:\tmp\review-X3\ws`, built from copies of `config\`, `cache\state.db`, four ZIPs, and the Coveo sitemap files for TRA Runtime Agent. The four versions: TRA Runtime Agent 5.13.0 (Flare, merged), TRA Runtime Agent 5.12.2 (WebWorks, 8 books), Silver Fabric Enabler for ActiveSpaces 1.2.0 (WebWorks, ActiveSpaces family), and StreamBase HP FIX Engine 11.2.1 (PDF only, Streaming family). They were tagged `convert_batch=x3` in the scratch `versions.csv`. Every stage was run through `docushift --root <scratch>`, extract → convert → reframe → sync (`--target-dir ws\target`) → validate. Kill-and-resume tests ran in a clone, `wsK`, using `C:\tmp\review-X3\killer.py`. It hard-kills (`TerminateProcess`) the CLI process at a chosen moment: when the first file that `shutil.rmtree` deletes under the live target disappears (the swap has begun), or N seconds after `<target>.part` appears. Snapshots (`snap.py`/`diff.py`) hash every file and dump the version rows of state.db. Nothing was written under `C:\github\docushift-tool` except this file. The mtime change on its CSVs at 19:59 comes from the mainstream session's commits (05518ad…90c5f35), not from this pass.

## Findings

### X3-01 · S1 · A convert run after an interrupted re-extract converts the half-deleted tree, and a later good extract makes that output `current` for good
- **Where:** `converter/driver.py:265` (a blank `extract_zip_checksum` skips the current test, so the run converts whatever tree is on disk) and `:447-448` (`convert_source_checksum` is written only `if checksum`, so the previous package's value is never cleared). `extractor/unpacker.py:271` blanks the checksum before the swap; `utils/swap.py:76-78` is remove-then-rename.
- **What:** Extract's R3-03 guard, the blanked checksum, protects `extract` itself. `convert` reads a blank checksum as "no currency claim", not as "this tree is not trustworthy". It converts the partial tree and leaves the old `convert_source_checksum` in place. Once `extract` re-unpacks the same package, the checksum matches again and `convert` reports `current` over the damaged output.
- **Failing scenario:** (1) `extract --force` TRA RA 5.12.2, killed 0.4 s into the swap's `rmtree`: the extracted tree goes from 2,935 to 2,250 files and the HTML from 582 to 0 in the deleted part. (2) `convert` without re-extracting: `converted`, 218 topics instead of 259, 7 units instead of 8 (the whole `tib_Designer_palettes` book is gone), 330 files instead of 621, CSH 7 resolved instead of 108. The only error says `92 reference(s) resolved to nothing`, which does not name the cause. (3) `extract`: `extracted`. (4) `convert`: **`current`**, and the output stays at 330 files, with nothing raised.
- **Confirmed:** yes, by kill-and-resume in `wsK` (logs `k-c2.log`; the file counts above are from the tree).
- **Suggested fix:** Refuse to convert (fail with a finding) when `extract_zip_checksum` is blank but a package exists. Also clear `convert_source_checksum` whenever a build runs without a checksum, so a later match cannot vouch for it.

### X3-02 · S1 · An interrupted reframe swap loses every hand-pinned page name: the next run deletes the `.part` that held them and recomputes the names
- **Where:** `reframe/driver.py:497` (`renames.load(target)`; the only copy of the pins lives in the merged tree being replaced), `:521` (`remove(staging)` deletes the complete `.part`, which held the new copy), `utils/swap.py:76-78` (the target is removed before the rename; the docstring at `:66-69` says this window exists).
- **What:** If the swap stops between `remove(target)` and `staging.replace(target)`, the target is missing and a complete `<version>.part` is left. That happens on a kill, on Ctrl-C, or when 8 rename attempts lose to a scanner, which `reframe` reports once as `failed`. The next `reframe` finds no `rename-map.csv`, so it lays out with computed names and deletes the `.part`. It reports `reframed` and raises no `RENAME_MAP_*` finding.
- **Failing scenario:** In `wsK`, `new_path` for `_templates/Home.md` was edited to `designer-home.md`, and `reframe` applied it (R9-04 works). That state was then reproduced: the merged tree copied to `5.13.0.part` and the tree removed. The next `reframe` is `reframed`; `designer-home.md` is gone, `tibco-designer.md` is back, and `rename-map.csv` lists the computed name. On real data the same applies to the TRA RA 5.13.0 legal and support pins and to every name an older algorithm chose that a pin now holds. Their published URLs would move.
- **Confirmed:** yes, but with the post-remove state reproduced by hand (copy and delete), not with a kill timed to the microsecond window between the last `rmdir` and the rename. `k-rf-gone.log`.
- **Suggested fix:** Before building, if the target is missing and `<target>.part` holds a `rename-map.csv`, read the pins from there (or finish the rename). Better still, keep the approved map outside the tree that gets swapped.

### X3-03 · S2 · A kill during the convert or reframe swap leaves a partly deleted tree that the next run calls `current`, and `sync` publishes it
- **Where:** `utils/swap.py:76` (`rmtree` of the live target runs bottom-up, so top-level files go last), `converter/driver.py:265-266` and `reframe/driver.py:360-366` (currency = metadata plus `target.is_dir()`; nothing checks that the tree is whole). `sync/distributor.py:271-279` (`_identical` compares output to the published copy, not to anything known-good).
- **What:** CPython 3.13 on Windows deletes with `os.walk(topdown=False)`, so a kill partway through `rmtree` leaves the version folder with its top-level files (`toc.yml`, `csh.yml`, `rename-map.csv`) and some subfolders gone. The checksums from the previous complete build still match, so the next run says `current`. The complete `<version>.part` beside it is ignored.
- **Failing scenario:** `convert --force` TRA RA 5.12.2, killed at the start of `rmtree`: 615 of 621 files remain. `convert`: `current`. `sync`: `synced`, 615 files. `validate`: 7 errors (missing `tib_Designer_palettes/images/*.gif`). The same for `reframe --force` TRA RA 5.13.0: 500 of 506 files, then `reframe` says `current`. `validate` catches only lost files that something references. A lost out-of-TOC page or an unreferenced asset goes unseen.
- **Confirmed:** yes, by kill-and-resume (`killer.py rmtree`) in `wsK`, for both stages.
- **Suggested fix:** Rename the live target aside (`<version>.old`) before deleting it, so the window becomes two renames. Or write a completion marker (a digest or file count) that the current test checks, and treat a leftover `.part` as "not current".

### X3-04 · S2 · A re-converted tree is not re-merged: `reframe` reports `current` over the old merge (Phase 21's carried-forward item, confirmed)
- **Where:** `reframe/driver.py:352-366`. `convert_source_checksum` is the *package* checksum, and `convert --force` writes the same value again (`converter/driver.py:447-448`). `docs/user-guide.md:897` says `--force` is needed only when "the converted tree, the policy and the names … are all unchanged", which implies a changed converted tree re-merges.
- **What:** No property of the converted output (digest, build time, converter version) enters reframe's key, so any change that reaches `output/` without a new package is invisible to it. That covers a converter fix, an engine correction, a sitemap arriving (X3-05), or a display-name edit (X3-07).
- **Failing scenario:** A topic in TRA RA 5.13.0 changed and `convert --force` was run: `output/…/palette-reference/Managing_Repository_Content.md` now carries the change. `reframe` returns `current` and `grep` finds it in 0 merged files. Only `reframe --force` brings it in. The publishing side of this is R10-06 (theme BB, in flight).
- **Confirmed:** yes, in `ws`.
- **Suggested fix:** Have `convert` record an output identity (a digest of `output_map` plus the written files' sizes, or a build counter) and key `reframe` on it in place of the package checksum. Then correct `user-guide.md:897`.

### X3-05 · S2 · `301.yml` depends on the Coveo sitemap cache and `origin-urls.yaml`, and neither is in the convert or reframe currency key
- **Where:** `converter/driver.py:482-483` and `reframe/driver.py:812-814` read `config.load_origin_urls()` and `origins.page_list(cache_dir, …)` (`origins.py:327-339`, `cache/coveo/`). The current tests are at `converter/driver.py:265` and `reframe/driver.py:365`.
- **What:** A run made before `catalog sitemap` writes no `301.yml` and warns `ORIGIN_SITEMAP_MISSING` once. After the sitemap arrives, every later run is `current` and repeats nothing, so the version publishes without its origin redirects. A sitemap refresh or a template edit is missed the same way. `user-guide.md:477-484` does not say that `--force` is needed afterwards.
- **Failing scenario:** Convert TRA RA 5.12.2 and 5.13.0 with no `cache/coveo`: no `301.yml`, one warning. Then copy in the sitemap files and `manifest.json`. `convert` is `current` (×3) and there is still no `301.yml`. `convert --force` writes both. For reframe: merge 5.13.0 without its sitemap file (no `301.yml`), restore the file, run `reframe`: `current`, still no `301.yml`.
- **Confirmed:** yes, in `ws` (`conv5.log`, then `conv6.log`), and for reframe.
- **Suggested fix:** Add a digest of the version's sitemap page list and of its resolved origin template to both keys, as `convert_api_prefix` already does for `publish_base_url`.

### X3-06 · S3 · `convert` has no code-version component, unlike `reframe`'s `_ALGORITHM`
- **Where:** `converter/driver.py:242-277` (the key is package checksum, API prefix and engine). Compare `reframe/policy.py:31-48`, whose comment describes exactly this hole and closes it for reframe.
- **What:** Every engine or transform fix reaches converted trees only through a `convert --force` that someone remembers, and then needs a second `reframe --force` (X3-04). The batch 2/3 roll-outs (runs 334–339) depended on that. `user-guide.md:680/791` presents `--force` as being for an unchanged extracted tree.
- **Failing scenario:** After a converter fix, `convert --all` reports `current` for all 42 converted versions and publishes the pre-fix output.
- **Confirmed:** yes by mechanism (`convert` is `current` after any code change, as in every second run above). The fix-rollout instance is recorded in INDEX.md batch 2.
- **Suggested fix:** Add a `_CONVERTER_VERSION` constant to the key, bumped by any commit that changes output, the way reframe's is.

### X3-07 · S3 · Catalog and config edits that change converted or merged bytes are outside the keys: `display_name`, `aem_templates/`, `publish_base_url`
- **Where:** `converter/navigation.py:558` (`display_name` titles the version index of a multi-collection WebWorks version). `converter/driver.py:558-566` (templates). `reframe/driver.py:716-723` (`publish_base_url` goes into `rename-map.csv`'s `expected_aem_url`, and `rename-map.csv` is published, as in `p35-aem`).
- **What:** Each of these edits changes the output, yet the stage stays `current`. R10-10 (in flight) covers the same gap for sync's document indexes; this is the convert and reframe half.
- **Failing scenario:** Change `display_name` to "Spotfire Runtime Agent" and run `convert` on TRA RA 5.12.2: `current`, and `index.md` still has `title: "TIBCO Runtime Agent™"`. `--force` changes `index.md` and `toc.yml`. Set `publish_base_url: https://x3.example.com` and run `reframe`: `current`. `--force` rewrites every `expected_aem_url` in `rename-map.csv`.
- **Confirmed:** yes, in `ws`, for `display_name` and `publish_base_url`. Templates: by code only.
- **Suggested fix:** Fold the display name, a digest of the templates used, and (for reframe) the base URL into each stage's key, or document `--force` for each.

### X3-08 · S3 · A version with no package checksum is re-converted and re-merged on every run, with no line saying why
- **Where:** `converter/driver.py:265` (`checksum and …`) and `:447`. `reframe/driver.py:365` (`converted_from and …`).
- **What:** `extract --measure-only` and a failed post-swap extract both leave `extract_zip_checksum` blank. From then on `convert` never reports `current`, never writes a checksum, and `reframe` never reports `current` either. The result is correct, but every run rebuilds and the CLI shows a plain `converted`.
- **Failing scenario:** Delete SFAS 1.2.0's two checksum keys and run `convert` twice: `converted`, `converted`. Real instances: the 6 DataSynapse Flare versions (state.db: converted, no `extract_zip_checksum`, no `convert_source_checksum`, no `convert_engine`), which `convert --all` and `reframe --all` rebuild every time.
- **Confirmed:** yes, in `ws`. The six are counted from a copy of the real state.db.
- **Suggested fix:** Print a note such as "no package checksum, rebuilt; run `download`/`extract` to make this version cacheable", or key these on a tree digest.

### X3-09 · S3 · `.part` residue survives every `current` re-run, in `extracted/`, `output/`, `reframed/` and the published target
- **Where:** `extractor/unpacker.py:252`, `converter/driver.py:314`, `reframe/driver.py:521`, `sync/distributor.py:385`. Each removes its staging only when it is about to rebuild, so a `current` decision leaves it.
- **What:** A run killed while building leaves `<version>.part`. The next plain run is `current` (correctly, since the old tree is intact) and the residue stays until a forced rebuild. R3 noted "no `.part` residue … the extract staging is swept before each run"; it is swept only before a rebuild. In the published tree the residue is what feeds R10-03 (fix in flight), and `validate` reports it only as a `SYNC_RESIDUE` note.
- **Failing scenario:** `extract --force` TRA RA 5.13.0 killed 1.5 s in, then `extract`: `current`, and `5.13.0.part` (715 files, 19 MB) remains. Similar runs left `convert` (163-file `5.12.2.part`) and `sync`, which after `current` left `online-help/5-13-0.part` with 133 files. This pass reproduced R10-03 there: `online-help/301.yml` gained 643 rows pointing into `5-13-0.part/`, and `validate` reports 581 `LINK_BROKEN`.
- **Confirmed:** yes, by kill-and-resume in `wsK`, for all four.
- **Suggested fix:** Sweep `<target>.part` on every visit, `current` included, or at least report it.

### X3-10 · S3 · A page's line endings depend on whether a later pass rewrote it, and on the OS
- **Where:** `converter/driver.py:532,555,558,564` and `transforms/csh.py:280` (`write_text` with the default newline, which is CRLF on Windows). `converter/driver.py:765-767,797` (the fragment pass re-reads with universal newlines and writes `newline=""`, giving LF). `reframe/driver.py:688` (LF). `sync/distributor.py:777,820,896` (CRLF). `origins.py:428` and `reframe/manifest.py:132` (LF).
- **What:** The tree is byte-identical on every Windows re-run, but its line endings are an accident. 562 of 967 converted `.md` files are CRLF and 405 are LF. Of the `.yml` files, 5 are CRLF and 5 LF, and the published target has 47 CRLF to 5 LF. One added or removed cross-reference fragment flips a whole page between CRLF and LF, so a re-convert diff shows every line of that page changed. A run on a non-Windows machine produces different bytes for every CRLF file.
- **Failing scenario:** SFAS 1.2.0: `index.md` is CRLF and `Tib_sfas_Install_guide/overview.3.1.md` is LF in the same tree. Both are published as written.
- **Confirmed:** yes, by a line-ending count over `ws\output`, `ws\reframed` and `ws\target` (`eol.py`).
- **Suggested fix:** Pass `newline="\n"` to every text write in convert, reframe and sync (`csvio` keeps its CSV CRLF).

### X3-11 · S3 · A `current` re-run records no per-version findings, so `report --run last` stops showing errors the tree still has
- **Where:** `converter/driver.py:265-277` (and the same in reframe and sync): the `current` return records nothing. `report` defaults to the last run, and `report --prune --keep N` deletes the only rows.
- **What:** The tree is unchanged but the report is not: run 1 "1 error, 10 warnings, 12 notes", run 2 "1 warning". `report --stage convert --severity error --slug <sfas>` after a `current` run prints "no findings" while SFAS 1.2.0's output still holds the unresolved reference. After `--prune --keep 3` the original record is gone too.
- **Failing scenario:** As above: runs 345 and 346, then run 382 after a prune.
- **Confirmed:** yes, in `ws` (state restored afterwards).
- **Suggested fix:** On `current`, re-emit the stored findings of the run that built the tree (or point to it, e.g. "built in run 345: 1 error"). Have prune keep the newest building run per version.

### X3-12 · S4 · `version_state` holds absolute paths, which go stale when the workspace moves or a family is renamed
- **Where:** `extractor/unpacker.py:286` (`extract_path=str(target)`), `downloader/fetcher.py:358,442` (`download_path`).
- **What:** Only the truth of `download_path` is ever read (`state.py:528`), so nothing breaks today. The copied state.db carries `C:\github\docushift-tool\…` paths, and for SFAS a `families\en-us-tib-messaging\…` path left over from an earlier family assignment.
- **Failing scenario:** A tool that later reads these columns as paths would open the wrong workspace or a family folder that no longer exists.
- **Confirmed:** yes. Every snapshot diff shows them unchanged after runs from two other roots.
- **Suggested fix:** Store paths relative to the root, or drop the columns in favour of `config.*_path`.

## Currency-key table (stage · key inputs · should re-run on · does?)

| stage | key inputs (code) | should re-run on | does? |
|---|---|---|---|
| extract | sha256(ZIP) = `extract_zip_checksum`, target dir exists (`unpacker.py:220`) | new package | yes (also on a family move, since the target is missing) |
| | | `--force` | yes, byte-identical tree; mtimes reset to extraction time |
| | | interrupted re-extract | yes: the checksum is blanked before the swap (R3-03); but see X3-01 for convert |
| | | detector or inventory code change | no, only measures blank columns (R4-03 handled in convert) |
| convert | `extract_zip_checksum` = `convert_source_checksum`, `convert_api_prefix`, `convert_engine`, target dir exists (`driver.py:265`) | new package | yes |
| | | engine corrected by hand | yes (R4-03 fixed; checked: `dita/manual` gives not-current, then failed, and the old tree is kept) |
| | | `publish_base_url` for API versions | yes by code (no API version in this set) |
| | | converter code change | **no** (X3-06) |
| | | Coveo sitemap or `origin-urls.yaml` | **no** (X3-05) |
| | | `display_name`, `aem_templates/` | **no** (X3-07) |
| | | extracted tree partial or deleted under a blank checksum | **converts it**, then later `current` (X3-01) |
| | | output tree partly deleted | **no**, `current` (X3-03) |
| | | no package checksum | rebuilds every run (X3-08) |
| reframe | `convert_source_checksum` = `reframe_source_checksum`, policy key (fields + `_ALGORITHM`, not `publish`), rename-map digest, not `--renormalize`, target exists (`driver.py:352-366`) | `reframe.yaml` shaping field | yes (checked: `max_words` edit gives re-merge; revert gives re-merge; then `current`) |
| | | `publish` toggled | no, correctly (checked) |
| | | `new_path` edited | yes (R9-04 fixed; checked) |
| | | `--renormalize` | yes by code |
| | | re-converted output (converter fix, engine fix, sitemap, display name) | **no** (X3-04) |
| | | Coveo sitemap or `origin-urls.yaml` | **no** (X3-05) |
| | | `publish_base_url` (rename-map URLs) | **no** (X3-07) |
| | | merged tree partly deleted | **no**, `current` (X3-03) |
| | | target missing with `.part` present | rebuilds, **losing pins** (X3-02) |
| sync | online-help: file set plus `filecmp` (shallow, then content) against the source tree (`distributor.py:271`); merged: `_stale` on the same checksums; documents: `_documents_current`; API: `apirefs.current`; archives: rendered index text | source tree changed | yes (checked after the convert change) |
| | | source rewritten with identical bytes and new mtimes | no, correctly (content compare) |
| | | published copy partly deleted or edited | yes |
| | | merged tree stale against its conversion | no: R10-06 (theme BB, in flight) |
| | | doc-class no longer routed, display-name in document index | no: R10-05 and R10-10 (in flight) |
| | | product-level `metadata.yml`, `version.yml`, `301.yml` | rewritten every run, same bytes |
| validate | none (reads the target, writes nothing) | — | — |

## Double-run results (stage · files · identical? · differing bytes explained)

| stage | files compared | run 2 identical? | notes |
|---|---|---|---|
| extract | 5,822 (whole ws) | yes, 4/4 `current`; no file or mtime change | `--force`: same bytes, every mtime new; downstream `convert`/`sync` stay `current` |
| convert | 7,544 | yes, 3 `current` + 1 `engine unknown` | `--force` against run 1: 0 content changes; 977 files rewritten with the same bytes (the asset copies keep their mtimes) |
| reframe | 8,052 | yes, `current` | `--force`: 0 content changes in `toc.yml`, `csh.yml`, `301.yml`, `redirects.yml`, `reframe.yml`, `rename-map.csv`, `review-queue.csv` and 118 pages. `products.csv`/`versions.csv` rewritten with the same bytes |
| sync | 9,867 | yes, 17/17 `current` | the 14 product-level files are rewritten with the same bytes every run. `--force`: 0 content changes |
| validate | — | yes; console output identical apart from the root path; writes nothing | |
| state.db | version rows | only `updated_at` and `runs`/`findings` grow | absolute paths (X3-12) |
| PYTHONHASHSEED=1 and root `C:\tmp\review-X3\alt\a-longer root name with spaces\ws2` | 9,867 | **0 content differences** against `ws` (random seed, shorter root) over `output/`, `reframed/`, `target/` and `config/` after forced convert, reframe and sync | only mtimes and validate's printed path differ |

Kill-and-resume (`wsK`):

| stage killed | moment | resume result |
|---|---|---|
| extract | during unzip | `current`, old tree intact, `.part` left (X3-09) |
| extract | in the swap's `rmtree` | re-extracts (checksum blank, so correct); but `convert` run first converts the partial tree (X3-01) |
| convert | 4 s into the build | `current`, old tree intact, `.part` left (X3-09) |
| convert | in the swap's `rmtree` | `current` over 615/621 files, then published (X3-03) |
| reframe | in the swap's `rmtree` | `current` over 500/506 files (X3-03) |
| reframe | target removed, `.part` complete (state reproduced by hand) | re-merged, hand pin lost (X3-02) |
| sync | 0.3 s into the copy | `current`, `5-13-0.part` stays published, and R10-03's 301 rows appear (X3-09) |
| sync | source changed since the killed run | re-placed, `.part` swept (correct) |

## Checked and fine
- **Hash seed:** every output-shaping set or dict is sorted before it is written. A forced run under `PYTHONHASHSEED=1` matches runs under random seeds byte for byte.
- **Workspace path:** no absolute path reaches any output file. A root containing spaces gives the same output.
- **Filesystem order:** every walk that feeds output is sorted (`flare._walk_files`, `webworks._walk_files`, `detector._survey`, `flare_toc`, `roots.find_output_roots`, `apiref.find_api_roots`, `_html_files`, the fragment pass). The remaining unsorted `iterdir`s build sets or membership tests only. NTFS order cannot be varied on this machine, so this rests on reading the code.
- **Time:** no output file carries a timestamp. Drop-down months come from `release_date` (`sync/versions.py:81-85`). They use `strftime("%b")`, which follows `LC_TIME`. That is `C` after importing the tool, so the output is deterministic today, but a dependency that calls `setlocale(LC_ALL, "")` would localize month names.
- **CSV:** `csvio.write_rows` writes BOM + CRLF consistently. `versions.csv` and `products.csv` are byte-stable across runs. `rename-map.csv` and `review-queue.csv` are byte-stable across forced merges.
- **R9-04 fix:** a `new_path` edit re-merges without `--force` and the pin is applied.
- **R4-03 fix:** an engine pin makes `convert` not current. A failed re-convert keeps the old tree, and reverting the pin returns to `current`.
- **`publish` toggle:** it is excluded from the policy key, so opting in re-merges nothing.
- **Sync after a killed copy whose source has since changed:** it re-places and sweeps the `.part`.
- **Not checked:** a kill landing between `convert`'s swap and its state writes (`converter/driver.py:433-453`), where a new tree sits beside the old `output_map` while the checksum still matches on a forced re-convert. With unchanged code the two are identical, so this is unconfirmable without a code change. API-reference and archive currency under re-run: no version in this set has an API tree, though archives were `current` on the second run. DITA and DocBook engines were not run.
