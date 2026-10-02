# R4 — Engine framework & converter driver: findings

Base: review-base (7dda975) · Reviewed: `engines/base.py`, `engines/detector.py`, `engines/roots.py`, `engines/csh.py`, `engines/__init__.py`, `converter/driver.py`, `converter/navigation.py` (plus the call sites in `extractor/unpacker.py:identify`, `extractor/inventory.py:_read_csh`, `transforms/csh.py:resolve/identifiers_by_source`, `cli.py:convert`) · Date: 2026-10-02

| S1 | S2 | S3 | S4 |
|---|---|---|---|
| 1 | 4 | 9 | 3 |

Real data used: the 43 extracted versions in `families/` (activespaces, ems, tra, streaming, datasynapse), the 36 converted trees in `output/`, `config/versions.csv`, `cache/state.db` (read-only: `version_metadata.output_roots`, `csh_source`, `engine_folder_map`, `findings`), and the html-to-md cache (a full-cache `find` for CSH sources over 200 KB, for `wwhdata/` dirs and for `Data/HelpSystem.xml`). The frozen Flare engine was also run read-only over the cached `bc/7.4.0` tree. Scratch scripts and repros are in `C:\tmp\review-R4\`: `repro.py`, `repro_tail.py`, `repro_bc.py`, `csh_consistency.py`, and `tests_r4/test_r4_repro.py`, which uses the project's own fixtures. The unit's own tests pass (69 of 69).

## Findings

### R4-01 · S1 · Byte-identical duplicate WebWorks books are each taken as a root, so the guides publish twice
- **Where:** `src/docushift/engines/roots.py:104-105` (`_is_webworks_root`), `roots.py:260-261` (falls back to full names), `engines/webworks.py:988-1006` (`units` has no duplicate test). Compare `engines/docbook.py:425-438` + `:974`, where DocBook rejects such copies and names each one.
- **What:** every directory holding `wwhdata/` becomes a unit. A package that ships each book both at the top level and under `html/` gets four units, two full copies of the documentation, and nothing reports it.
- **Failing scenario:** Silver Fabric Enabler for ActiveSpaces 1.2.0. `output_roots` = `Tib_sfas_Install_guide`, `Tib_sfas_Users_guide`, `html/Tib_sfas_Install_guide`, `html/Tib_sfas_Users_guide`. The published tree holds both copies, `toc.yml` lists "Installation" and "User's Guide" twice each (top-level lines 7, 49, 111, 153), and the top-level copy's pages link into the `html/` copy (`../html/Tib_sfas_Users_guide/preface.2.2.md`). The convert findings for the version (runs 286, 305, 322) contain no code that names the duplication.
- **Confirmed:** yes. `diff -rq` finds the two source copies of each book byte-identical. Output tree and `toc.yml` inspected, and the `findings` table queried. In the corpus, 6 versions carry the same WebWorks book name at two paths (`sfas/1.2.0`, `bc/7.4.0`, `loyalty/16.1.0`, `16.2.0`, `silver_fabric/5.8.1`, `activematrix_service_performance_manager/1.2.0_july_2009`). Only sfas was checked for byte identity.
- **Suggested fix:** apply DocBook's rule to WebWorks books: when one book root is byte-identical to another, drop it and report `DOCSET_SKIPPED`. Prefer the copy that a collection's `wwhelp/books.xml` declares.

### R4-02 · S2 · A version that mixes generators is converted by one engine; the other generator's books are lost under a misleading message
- **Where:** `converter/driver.py:200` (one handler per version), `engines/detector.py:140-152` (marker precedence, Flare first), `engines/base.py:446-450`
- **What:** the version's engine is a single value, and only that engine's roots are converted. A WebWorks book that sits inside a Flare root is fed to the Flare converter. One that sits outside every Flare root is never looked at. `architecture.md` §3.4 and `design.md` §7.1 say "both converters have work to do", and that the per-folder map is what makes this visible. The map cannot show it (R4-10).
- **Failing scenario:** BusinessConnect 7.4.0 (in scope, `convert_eligible=true`, `migrate`) detects as Flare (pass 1). Its 83-page WebWorks book `doc/bcgs/html/TIB_bc_apireference` lies inside the Flare root, and the Flare engine converts **0** of its pages. About 80 are skipped as `no-content-container` and reported one by one as `CONTENT_MISSING ... no div[role='main']#mc-main-content`, which reads as a Flare markup defect, not as "this is a WebWorks book". `ipe-db2/11.9.0` has 7 WebWorks books beside 4 Flare roots (not run).
- **Confirmed:** yes for bc 7.4.0, by running the frozen `FlareEngine` read-only over the cached tree (`repro_bc.py`): 523 documents, none from the WebWorks book, and the findings as quoted. The other copy, `doc/bcis/html`, is a strict byte-identical subset of `bcgs/html`, so nothing is lost there. In the cache, 2 versions hold both a Flare root and a `wwhdata/` book.
- **Suggested fix:** when a tree holds roots of a second convertible engine that the first engine does not own, report them as one finding naming the engine and the root (or dispatch them to their own engine). Exclude another engine's roots from a Flare unit's topic walk.

### R4-03 · S2 · Correcting an engine by hand does not reach the output: convert reports `current`, and the recorded roots belong to the old engine
- **Where:** `converter/driver.py:229-231` (the currency key is `extract_zip_checksum` plus the API prefix only), `engines/base.py:446-450` (`units` returns the recorded `output_roots` whatever the engine), `extractor/unpacker.py:199-210` (an unchanged package returns `CURRENT` without re-running `identify`, so `output_roots` is never recomputed)
- **What:** `engine_source=manual` is the documented remedy for a misdetected engine (§3.4). After a pin, `convert` reports `current` and keeps the wrong engine's tree. `convert --force` still hands the new engine the old engine's roots, unless `extract --force` is run first. Nothing in the run or the docs says so.
- **Failing scenario:** a version converted as `flare` is pinned `webworks/manual`. The next `convert` reports `current` with `engine=webworks` and publishes the Flare output unchanged.
- **Confirmed:** by synthetic test (`test_manual_engine_pin_after_conversion_reports_current`): `CURRENT`, with no finding. On real data this is **unconfirmed**. `versions.csv` has 6 manual pins (DataSynapse), and they predate the trees they describe, so they do not show the sequence.
- **Suggested fix:** add the engine (and a hash of the recorded `output_roots`) to the convert currency key. Make `BaseEngine.units` refuse recorded roots that were located for a different engine, or have `identify` re-run when the engine column changes.

### R4-04 · S2 · `--input` applies the catalog tree's recorded roots, API roots and CSH paths to a different folder, and reports success with 0 topics
- **Where:** `converter/driver.py:274-275` + `apiref.py:99` (`tree / line` over the recorded paths), `driver.py:827-845` (the recorded CSH rows are joined to the `--input` tree, missing files are skipped at `:844`, and the locate fallback runs only when there are *no* rows)
- **What:** the "no record → locate" fallback assumes `--input` is never pointed at a version that `extract` has seen. When it is, and the folder's layout differs (no wrapper directory, or another copy), every recorded path misses.
- **Failing scenario:** an extracted version is converted with `--input` from a copy laid out under a different wrapper. The result is outcome `converted`, `units=1`, `documents=0`, no `csh.yml`, and the only finding is the unrelated `ORIGIN_SITEMAP_MISSING`. The CLI prints a green tick with "0 topic(s)".
- **Confirmed:** by synthetic test (`test_input_tree_reads_another_trees_recorded_roots_and_csh`). **Unconfirmed** on a real `--input` run (not executed against the main tree).
- **Suggested fix:** under `--input`, ignore the recorded metadata and locate everything, or check that every recorded root exists and fall back (with a finding) when one does not.

### R4-05 · S2 · Frontmatter and `csh.yml` disagree for every identifier that the version-wide fallback rescues, or that loses an ambiguity
- **Where:** `converter/driver.py:269-270` (frontmatter comes from `csh_transform.identifiers_by_source`, before conversion), `transforms/csh.py:214-234` (own-doc-set path only) against `transforms/csh.py:168-200` (`_target`: own doc-set, then siblings, then the ambiguity winner)
- **What:** `csh.yml` resolves through §9.3 steps 4-5, but the frontmatter is keyed only on the link inside its own doc-set. A rescued identifier is put on a page that does not exist (`relnotes/a.htm`) and is missing from the page that `csh.yml` names. The losing page of an ambiguous identifier keeps it in its frontmatter while `csh.yml` points elsewhere. That contradicts §5.4.5/§9.6 ("every identifier in a topic's frontmatter appears in `csh.yml`, and vice versa").
- **Failing scenario:** the BW-style `relnotes/Data/Alias.xml` copy (22% of Flare links dangle in their own doc-set, §5.4.1). The repro gives `csh.yml {ID_RESCUED: a.md, ID_BOTH: a.md}` and frontmatter `{relnotes/a.htm: [ID_RESCUED], relnotes/r.htm: [ID_BOTH]}`. `validate` would then raise `CSH_FRONTMATTER_MISMATCH` for each one, so the mismatch is reported (S2), not silent.
- **Confirmed:** by synthetic repro (`repro.py` (a)). On real output: **0** mismatches across the 7 TRA versions that ship `csh.yml` (`csh_consistency.py`), because none has a second alias file per doc-set. No version that reaches the path has been converted yet. Shared with R8 (`transforms/csh.py`).
- **Suggested fix:** derive frontmatter from `resolve()`'s winners (reverse map output → identifiers), by resolving before the write against the *planned* output paths, or by moving the frontmatter injection after resolution.

### R4-06 · S3 · Zero units, or zero documents, is still `converted`, and an empty tree is swapped over the previous output
- **Where:** `converter/driver.py:299-337`. `engines/flare.py:385-393`, `webworks.py:997-1003`, `dita.py:545-550` and `docbook.py:439-444` each return `[]` with a warning. `roots.py:175-179` claims that callers treat `[]` as "the tree is the single unit".
- **What:** no outcome distinguishes "converted nothing". The result is `CONVERTED`, a `toc.yml` with no nodes, and the swap removes whatever the last good run produced. Only a warning (`OUTPUT_ROOT_MISSING`/`DOCSET_SKIPPED`) is recorded.
- **Failing scenario:** a re-extract that loses `Data/HelpSystem.xml` (the 5 partial Flare outputs of §5.1.1) replaces a populated tree with an empty one, and the CLI line is green.
- **Confirmed:** n/a (S3). No converted version has 0 documents.
- **Suggested fix:** if `units` is empty or `documents == 0`, return `FAILED` (or a new outcome) without swapping.

### R4-07 · S3 · Only `OSError` is caught: any other exception aborts the whole batch, skips `findings.finish()`, and leaves `<version>.part`
- **Where:** `converter/driver.py:244-252`. `convert_many` (`:867-871`) and `cli.py:1595-1598` have no guard. `navigation.py:343` raises `ValueError` by design.
- **What:** "Never raises" (`base.py:454`, `driver.py:186`) is a convention that nothing enforces. An engine bug on one page (a `ValueError`, `RecursionError` or `KeyError`) stops every remaining version, and the run row is never finished.
- **Failing scenario:** an engine raises `ValueError` while converting a unit. `convert_many` propagates it and `output/.../<version>.part` remains (it is removed by the next run of the same version only).
- **Confirmed:** n/a (S3). Synthetic test `test_a_non_oserror_aborts_the_batch_and_leaves_staging`. No real conversion has raised so far, and there is no `.part` residue in `output/`.
- **Suggested fix:** catch `Exception` in `convert_one`, `remove(staging)`, record `FAILED` with the traceback summary, and continue.

### R4-08 · S3 · Bookkeeping that fails after the swap leaves a new tree with the old `output_map` and the old checksum
- **Where:** `converter/driver.py:337-357`. `_measure_output` → `catalog.record_convert_inventory` → `save()` (a CSV write) runs before `record_output_map` and before the checksum write.
- **What:** this is R3-03's shape on the convert side. If `versions.csv` is locked (Excel), the swap has already happened. The result is `FAILED`/`ERROR`, but the published tree is the new one, `output_map` (which Reframe reads, `reframe/driver.py:761`) describes the previous build, and after a `--force` re-convert the next plain run reports `current`.
- **Confirmed:** n/a (S3). Reasoned from the code path, not run.
- **Suggested fix:** write the state rows (`output_map`, checksum) before the CSV save, or wrap the post-swap block so that a failure records which artefacts are stale.

### R4-09 · S3 · Detection interleaves pass 2 and pass 3 per file, so one stray generator tag outranks content signatures in later files
- **Where:** `engines/detector.py:251-265`
- **What:** `design.md` §7.1 has pass 3 as "a last look" after pass 2. The loop instead returns on the first sampled file that carries *any* `<meta name="generator">`, before the remaining sample is checked for `MadCap:`, `DocBook XSL` or `DC.*`. A single FrontPage, Doxygen or Doxia page that sorts first decides the version. A named unconvertible engine is then reported as `ENGINE_UNKNOWN`, not misconverted.
- **Failing scenario:** a tree with `a-cover.html` (FrontPage) and two DocBook pages detects `frontpage`, `decided_by=3` (`repro.py` (e)).
- **Confirmed:** n/a (S3). On real data, all 43 extracted versions detect as their content says. ModelOps 1.3.0 (`doxia`) was checked: 137 of 137 generator tags name Doxia.
- **Suggested fix:** run pass 2 over the whole sample, and only then pass 3 over the same sample.

### R4-10 · S3 · The per-folder engine map is taken above the wrapper, never cleared, and never read, and neither is the exhausted-sample flag
- **Where:** `engines/detector.py:280-288` (immediate children of the *version* directory), `state.py:534-541` (upsert, no delete), `unpacker.py:331-333`. No reader for `engine_folder_map`, `Detection.sample_exhausted` or `decided_by` exists anywhere in `src/`.
- **What:** §7.3 step 4 exists to make a mixed bundle visible. On real data the map has a single entry, the wrapper, in 42 of 43 versions. EMS 10.4.0, 10.4.1 and 10.5.0 also keep a stale `html=flare` row from an earlier layout. §7's "the bound is recorded so 'we stopped looking' stays a different report line" never becomes a line.
- **Confirmed:** n/a (S3). `engine_folder_map` was dumped from `state.db`. This is why R4-02 goes unnoticed.
- **Suggested fix:** compute the map from `content_root` (one level below the wrapper), or per output root of every engine. Replace the rows per extract. Surface disagreement and `sample_exhausted` as findings.

### R4-11 · S3 · The CSH readers truncate at 300 KB without saying so, and skip entries uncounted
- **Where:** `engines/csh.py:49`, `:119-125`, `:150-153` (a `Map` with no `Name` is skipped), `:178-180` (a DITA value that is not a string is skipped)
- **What:** `_read` silently keeps the first 300,000 bytes. For WebWorks that yields a partial entry list with status `OK`. For DITA, contexts that sit past the cap read as `EMPTY`. Skipped entries are not tallied, so "every identifier is resolved or listed" (invariant 9) can fail without a line.
- **Failing scenario:** a 494 KB `topics.js` with 12,000 cases is read as 7,370 cases, status `ok`. A `head.js` with the contexts after 310 KB of script is read as `empty` (`repro.py` (b), (b2)).
- **Confirmed:** n/a (S3). The full-cache `find` found **no** `Alias.xml`, `head.js` or `topics.js` above 200 KB.
- **Suggested fix:** return `UNPARSEABLE` (or a new `TRUNCATED` status) when the file exceeds the cap, and count skipped entries on the source.

### R4-12 · S3 · `subtree_names`' Flare rule puts an arbitrary WebWorks book at the version root
- **Where:** `engines/roots.py:247-264`
- **What:** with several sibling roots, the shallowest root takes the version root, ties broken by path, case-folded. Phase 10 measured that rule on Flare only (`architecture.md` §5.1.3). For WebWorks, where each book is a unit (§5.3.3), one book's pages are mixed with the version-root artefacts and the generated `index.md`, and the choice follows the path, not `books.xml` order.
- **Failing scenario:** Runtime Agent 5.12.4. `designerhelp/tib_Designer_palettes` publishes at the version root (`palette.4.01.md`… beside `toc.yml`), while the other 7 books get folders. Administrator 5.12.x does the same with `TIB_TIBCOAdmin_installation`.
- **Confirmed:** n/a (S3: a layout choice, no content lost). Output tree inspected.
- **Suggested fix:** decide per engine. Keep the rule for Flare (`doc/html` + `doc/relnotes`), and give each WebWorks book its folder (by last segment, when the names are unique).

### R4-13 · S3 · A tail page that the TOC never listed is added with an empty title
- **Where:** `converter/navigation.py:196-202` (`NavNode(label="")`), rendered by `:405`
- **What:** the comment names WebWorks' `copyrigh.htm` as the case. The node is created with no label, and `_rows` writes `title: ""`. `_label_of` (used everywhere else) is not consulted.
- **Failing scenario:** the unit test's own shape renders `- title: ""  url: "copyrigh.md"` (`repro_tail.py`).
- **Confirmed:** n/a (S3). 0 empty titles across the 36 real `toc.yml` files, because the engines list the node themselves.
- **Suggested fix:** `NavNode(label=_label_of(path, documents), document=path)`.

### R4-14 · S3 · `subtree_name` answers `""` (the version root) for any root not in the lookup
- **Where:** `engines/base.py:382-383`. The lookup is set at `driver.py:300`, *after* `handler.units()` has run (`webworks.py:958-961` already works around this).
- **What:** inside `units()` the accessor returns the tree-relative path. Afterwards it returns `""` for any root that is not exactly a key. An engine that derives a unit root differently from the list it returned would write its pages and assets onto the version root, silently.
- **Confirmed:** n/a (S3). `repro.py` (f). No engine does this today.
- **Suggested fix:** raise (or record a finding) on a miss, instead of defaulting to `""`.

### R4-15 · S4 · `detect_version` walks the whole tree twice
- **Where:** `engines/detector.py:280-288`
- **What:** `detect_tree(tree)` surveys every directory, and then `detect_tree(child)` re-surveys every subtree, to fill a map nobody reads (R4-10).
- **Suggested fix:** collect per-top-folder markers in the one `_survey` pass.

### R4-16 · S4 · The `--input` CSH fallback runs on every conversion of a version whose extract found no CSH
- **Where:** `converter/driver.py:836-840`
- **What:** an empty `csh_source` result is read as "no record", so `_find_csh` runs `rglob('*')` over the whole tree (thousands of files for Streaming). "Absent" and "empty" are not distinguished (cf. R3's edge note).
- **Suggested fix:** key the fallback on "was this version extracted" (`extract_zip_checksum` / `content_root` present), not on the row count.

### R4-17 · S4 · The driver's module docstring still describes Phase 5a
- **Where:** `converter/driver.py:26-28`
- **What:** "In Phase 5a no engine is registered, so every selected version reports `ENGINE_UNKNOWN`" has not been true since 5b.
- **Suggested fix:** delete the paragraph.

## Edge notes (for the cross-stage pass X1)
- **`output_roots` / `api_roots` are stored with Windows separators** (`tibco-...-10-4-0\html`, every row in `state.db`) and read as `tree / line` (`apiref.py:99`). This works on Windows only; on POSIX the path holds a literal backslash. They are also written only when non-empty (`unpacker.py:343-348`), so a re-identify that finds none leaves the old list in place (cf. R3-05/R3-13).
- **Convert currency** = `extract_zip_checksum` + `convert_api_prefix` (`driver.py:216-231`). Changes to the engine, the recorded roots, the CSH inventory or the converter code do not invalidate (R4-03; the Phase 21 carried-forward item's shape, one stage earlier; R3's edge note).
- **`output_map`** is written after the swap and read by Reframe (`reframe/driver.py:761`). It can be stale relative to the tree after a post-swap failure (R4-08). CSH resolution correctly uses the in-hand rows rather than the table.
- **`csh_source.doc_set`** is the tree-relative owning root (POSIX). `output_map.source` is tree-relative POSIX. The two agree, and the 7 TRA `csh.yml` files resolve 100% (46 and 108 identifiers, matching the source entry counts).
- **`toc.yml` `url` values are raw (not percent-encoded) relative paths, while page-body links are encoded.** `_retarget_fragments` (`driver.py:626-647`) depends on the raw form. Validate and Reframe must read it the same way. No output filename contains a space or a parenthesis today.
- **Staging writes are not long-path spelled** (`driver.py:432-434`, `:456-458`), while `swap`/`remove` are. The longest output path today is 192 characters. This is for X2.
- **`.part` staging** sits beside the version (`output/<fam>/<slug>/<version>.part`). Sync reaches versions through `config.output_path`, so the residue from R4-07 is not published, but it is left on disk.
- **`engine_folder_map`** has a writer and no reader (R4-10). Candidate for removal or for a reader in `report`.
- R3's request: `roots.py:88` and `:127` are guarded. The `iterdir` calls sit inside `try/except OSError` (the generator is consumed inside the `try`), and `Path.is_dir()` returns False on error. No raise path out of `identify` from `roots.py`.

## Test gaps (real-data paths only)
- No test has two byte-identical WebWorks book copies (Silver Fabric 1.2.0, R4-01).
- No test has a Flare root that contains a `wwhdata/` book (BusinessConnect 7.4.0, R4-02).
- `subtree_names` is not tested on a multi-book WebWorks layout, where the shallowest-root rule picks a book (Runtime Agent 5.12.x, Administrator 5.12.x; R4-12).
- Nothing pins that a manual engine change invalidates a converted tree (6 manual pins in the catalog, R4-03).
- The CSH frontmatter ↔ `csh.yml` agreement under the version-wide fallback is untested (`test_identifiers_reach_the_topics_first_and_only_write` covers only a single doc-set; R4-05).

## Docs drift
- `design.md` §7.1: "three passes … Pass 3 — a last look". The code interleaves passes 2 and 3 per file (R4-09).
- `design.md` §7 (intro): "The bound is recorded on the result, so 'we looked at everything…' stays a different report line". Nothing reads `sample_exhausted` (R4-10).
- `architecture.md` §3.4, granularity caveat: "the detector records the per-folder map … and sets the **dominant** engine in the CSV". There is no vote. The version engine is a fixed precedence over the whole tree (Flare > WebWorks > DITA > R help), and the map is taken above the wrapper.
- `design.md` §7.1 says the 19 mixed versions are cases where "both converters have work to do", and §7.3 step 4 that the map "makes it visible". Neither holds (R4-02, R4-10).
- `architecture.md` §5.4.3 (last paragraph): the mapping is "recorded per version in state.db … rather than recomputed here". Resolution uses the rows in hand (`driver.py:326-330`), as `design.md` §9.3 correctly says.
- `engines/roots.py:175-179` docstring: "Callers treat [an empty list] as 'the version tree is the single unit of work'". All four engines treat it as nothing to convert (R4-06).
- `architecture.md` §5.1.3: the subtree-naming table is measured and argued for Flare only, but the code applies it to every engine (R4-12).

## Checked and fine
- **Detection on real trees:** all 43 extracted versions carry the engine their content shows. Flare, WebWorks and DocBook are decided by pass 1 and pass 2 as documented. ModelOps is genuinely Doxia. Manual pins outrank detection in `identify` and are never overwritten.
- **Roots:** `owning_root` takes the innermost root. Nested roots keep their full names. The case-folded primary tie-break, the clash with the primary's entries, and the duplicate secondary names all behave as `test_roots.py` pins. EMS, ActiveSpaces, Streaming, Spotfire Data Streams and Administrator 5.13.0 publish their single root at the version root.
- **CSH end to end:** 7 TRA versions. `csh.yml` counts equal the source entries (46 and 108). Frontmatter ↔ `csh.yml` has 0 mismatches. Empty sources go to `CSH_SOURCE_EMPTY` at extract. A UTF-8 BOM in `Alias.xml` parses. UTF-16 is `unparseable` (reported). Identifiers are byte-exact.
- **Build-and-swap:** staging is removed before each build. No `.part` residue in `output/` or `families/*/extracted/`. The checksum is written only after the swap.
- **Navigation on real output:** 0 empty titles in 36 TOCs. The 2 duplicated URLs each in EMS 10.4.0 and 10.4.1 come from the source TOC, not from synthesis. The 154 generated pages carry no link with a space or parenthesis. `_free` folds case.
- **Collision detection:** `OUTPUT_COUNT_MISMATCH` reports a shortfall when two writes land on one path (test passes).
- **Registry:** importing `docushift.engines` registers all four handlers, and `auto` and unhandled engines share `ENGINE_UNKNOWN`.
