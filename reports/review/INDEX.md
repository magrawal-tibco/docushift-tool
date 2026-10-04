# Phase 34 review: findings index

Base: `review-base` (7dda975). Each unit's full findings file is beside this one.
**Proposed** is the reviewer's recommendation. **Decision** is the user's, and nothing
is fixed until it is filled in.

Severity: **S1** wrong output with no warning, or data loss · **S2** wrong output that is
reported, or a crash on real input · **S3** fragile but correct today · **S4** cleanup.

## Counts

| unit | S1 | S2 | S3 | S4 | total |
|---|---|---|---|---|---|
| R1 Foundations | 1 | 4 | 8 | 2 | 15 |
| R2 Catalog & discovery | 4 | 3 | 13 | 1 | 21 |
| R3 State & acquisition | 0 | 3 | 10 | 3 | 16 |
| **Batch 1** | **5** | **10** | **31** | **6** | **52** |

The orchestrator re-traced R1-01, R2-02 and R3-01 in the code; all three hold.

## Batch 1, grouped into fix themes

Triage approved by the user 2026-10-02, as proposed.

| theme | findings | proposed | decision |
|---|---|---|---|
| **A. Hand edits undone by the next fetch** | R2-01 (S1), R2-03 (S1) | fix | approved: fix 2026-10-02 |
| **B. A dry run, a failed save, or a partial fetch damages saved state** | R2-02 (S1), R2-05 (S2), R1-04 (S2), R3-11 | fix | approved: fix 2026-10-02 |
| **C. Valid situations abort the fetch as "deletions"** | R2-06 (S2), R2-07 (S2) | fix | approved: fix 2026-10-02 |
| **D. Published paths over 260 characters, written silently** | R1-01 (S1), R1-08 | fix | approved: fix 2026-10-02 |
| **E. Dates: epoch milliseconds, the bulk-migration date, "June 2023"** | R2-04 (S1), R1-05 (S2), R1-11, R2-08 | fix | approved: fix 2026-10-02 |
| **F. Zip-slip through a drive letter mid-path** | R3-01 (S2), R3-07 | fix | approved: fix 2026-10-02 |
| **G. A failed or partial extract leaves the old package's measurements in place** | R3-03 (S2), R3-04, R3-05, R3-08, R3-12 | fix | approved: fix 2026-10-02 |
| **H. Wrapped packages: documents reported "unclaimed"** | R3-02 (S2) | fix | approved: fix 2026-10-02 |
| **I. Blank `convert_eligible` reads as false** | R1-02 (S2) | fix | approved: fix 2026-10-02 |
| **J. C API function names publish as truncated MadCap stems** | R1-03 (S2) | fix | approved: fix 2026-10-02 |
| **K. Config entries dropped silently** | R1-06, R1-07 | fix (cheap) | approved: fix (cheap) 2026-10-02 |
| **L. Docs that contradict the code** | R1-12, R1-13, R2-19, R2-20, R3-16 | fix docs | approved: fix docs 2026-10-02 |
| **M. Fragile, correct today** | R1-09, R1-10, R2-10, R2-12, R2-13, R2-14, R2-15, R2-16, R2-17, R2-18, R3-06, R3-09, R3-10, R3-13 | defer to planning.md carried-forward items | approved: defer to planning.md carried-forward items 2026-10-02 |
| **N. Data, not code: 113 "unclassified" products already have a family typed in** | R2-09 | user to review in the catalog | approved: user to review in the catalog 2026-10-02 |
| **O. Cleanup (dead code, duplicates)** | R1-14, R1-15, R2-21, R3-14, R3-15 | one cleanup commit at the end of Phase 34 | approved: one cleanup commit at the end of Phase 34 2026-10-02 |

## Batch 1: fixes merged (2026-10-03)

All twelve fix themes are merged on `reframe-component`. Each fix carries a test that
failed on the old code. The full suite passes (1,815 tests) and lint is clean. No finding
turned out to be wrong.

| theme | commit |
|---|---|
| A | 0ae08fd fix(catalog): keep values typed into the CSV when the next fetch re-resolves them |
| B | 365afa1 fix(catalog): write both CSVs or neither, and touch state.db only after they are written |
| C | 6dfb409 fix(catalog): stop reading a skipped archive index or a hand-added version as a deletion |
| D | 435ce4b fix(sync): hold help and document paths to the 260-character ceiling |
| E | 1285c1e fix(dates): store epoch-millisecond dates as ISO, drop the bulk-migration day, read "June 2023" as 2023 |
| F | e2bce57 fix(extract): refuse ZIP members that escape through a drive letter or that Windows cannot hold |
| G | 976b876 fix(extract): a failed or partial extract no longer leaves the old package's measurements in place |
| H | 2da7f3a fix(extract): read the inventory's pdf/doc test and unclaimed groups below the package wrapper |
| I | 938114e fix(csvio): let a blank convert_eligible cell take the active/archived default |
| J | e57c9e9 fix(reframe): name C API pages after the full function name, and queue shortened names for review |
| K | 6cdeb37 fix(config): stop dropping reframe defaults and malformed origin templates without a word |
| L | d5be6ff, 1ecbf5c (docs), plus docstrings in 976b876 |

**Data and output effects still to apply** (code is fixed; data on disk is not yet rewritten):
- **J:** the merged trees still carry the truncated EMS names until `reframe --all --renormalize` runs. That re-run needs the user's go-ahead. No `rename-map.csv` was hand-edited after its run (all 14 checked), so `--renormalize` discards no human pin.
- **E:** the next catalog save rewrites 926 epoch dates as ISO, and the next EMS fetch replaces 20 archived 2022-05-26 dates.
- **H:** the inventory tables change on the next `extract --force` (e.g. TRA 5.12.2: 443 unclaimed under the wrapper becomes 13 routed, plus 161 + 269 unclaimed in the two help trees).
- **D:** a `--target-dir` longer than ~38 characters now fails over-length versions instead of writing them.

**Implementation choices the fixers flagged** (each consistent with the architecture docs):
- R2-01 adds a `resolved_snapshot` table to state.db to tell a hand edit from a report change.
- R2-04 drops only the known bulk date on archived rows rather than overriding all archived dates with month text.
- F refuses a whole package with a bad member name, matching the existing escape rule.
- J bumps the reframe algorithm version 3 → 4 (every merged tree re-merges on its next run), and the new `shortened` review flag also queues ~90 pages cut at 50 characters across families.
- New finding codes: `ORIGIN_TEMPLATE_REJECTED`, `ORIGIN_PATH_TOO_SHORT`, `INVENTORY_PARTIAL` (register 66 → 69).
- Known gap, not in any finding: `archive download --from-file` for an unknown version still adds a row that blocks a later fetch.

### J applied (2026-10-04)

The user ran `reframe --all --renormalize` in the mainstream session. Diffed against a copy of every `rename-map.csv` taken just before:
- **66 EMS pages renamed, exactly as predicted**: 11 C API pages × 6 versions, e.g. `tibemsmsg-setpriorit.md` → `tibemsmsg-setpriority.md`. ActiveSpaces unchanged.
- **1 unexpected rename, not caused by J**: in TRA Runtime Agent 5.13.0, the second legal page (`trahelp/_templates/Legal-and-Third-Party-Notices`, outside the TOC) moved from `tibco-runtime-agent/legal-and-third-party-notices.md` to `trahelp/_templates/legal-and-third-party-notices-2.md`. That exposes a source folder in the URL and adds a collision suffix. J cannot reach this title (it has spaces); `--renormalize` recomputed a name an earlier run had pinned, and current naming of an out-of-TOC duplicate is worse. **Handed to R9 (reframe) for root cause.** Restored 2026-10-04 at the user's request: the old name was pinned back in that row of `rename-map.csv` (copied from the pre-run backup) and the one version re-merged with `--force`. The page is back at `tibco-runtime-agent/legal-and-third-party-notices.md`, the `-2` copy is gone, and the run raised no new findings.
- Review queues grew as the new `shortened` flag predicted: EMS 118 → 119, TRA Administrator 4 → 10, TRA Runtime Agent 1 → 6.
- The 926 epoch dates were migrated to ISO by the mainstream session (3f907d0).

## Batch 2 (R4–R6): counts

| unit | S1 | S2 | S3 | S4 | total |
|---|---|---|---|---|---|
| R4 Engine framework & converter driver | 1 | 4 | 9 | 3 | 17 |
| R5 Flare engine | 7 | 2 | 6 | 1 | 16 |
| R6 DITA & DocBook engines | 2 | 3 | 9 | 2 | 16 |
| **Batch 2** | **10** | **9** | **24** | **6** | **49** |

The orchestrator re-checked R5-02 in `output/` (EMS 10.5.1 `Deploying-the-FTL-Server-Cluster.md`: step 3 renders as "1." after a note paragraph); it holds. R4-01 is the cause of the open issue "Silver Fabric Enabler for ActiveSpaces: the whole guide set appears twice".

## Batch 2, grouped into fix themes

Triage approved by the user 2026-10-04, as proposed, including the two choices in Q (skip and report localized roots) and T (report lost books; dual-engine conversion deferred). The user also asked to restore the TRA Runtime Agent 5.13.0 legal page's old address.

| theme | findings | proposed | decision |
|---|---|---|---|
| **P. Content published twice or in the wrong place** | R4-01 (S1), R6-07, R4-12, R4-13, R4-14 | fix | approved: fix 2026-10-04 |
| **Q. Non-English Flare builds land in the English tree** | R5-01 (S1) | fix: skip them and report each one; publishing them to the `loc-` tree is a later phase | approved: fix 2026-10-04 |
| **R. Flare formatting lost: step numbers, note boxes, table headings and captions, code moved across prose, popups** | R5-02, R5-03, R5-04, R5-05, R5-07 (S1), R5-13 | fix | approved: fix 2026-10-04 |
| **S. Links that should work but don't** | R5-06 (S1), R5-08 (S2), R6-03 (S2), R6-05 (S2), R6-14 | fix | approved: fix 2026-10-04 |
| **T. Mixed generators and hand-corrected engines** | R4-02 (S2), R4-03 (S2), R4-09 | fix: name each book a version loses (new finding) and make an engine correction re-convert; converting two engines in one version is deferred | approved: fix 2026-10-04 |
| **U. `--input` and help-ID (CSH) consistency** | R4-04 (S2), R4-05 (S2), R4-11 | fix | approved: fix 2026-10-04 |
| **V. "Converted" with nothing converted, or a crash that leaves residue** | R4-06, R4-07, R4-08, R5-09 (S2), R5-12, R5-15 | fix | approved: fix 2026-10-04 |
| **W. DITA, before the first DITA family converts** | R6-02 (S1), R6-04 (S2), R6-09, R6-12 | fix | approved: fix 2026-10-04 |
| **X. DocBook list order and false anchor warnings** | R6-01 (S1), R6-06 | fix (code and the docs claim) | approved: fix (code and the docs claim) 2026-10-04 |
| **Y. False warnings and dropped TOC nodes in Flare** | R5-10, R5-11 | fix | approved: fix 2026-10-04 |
| **Z. Fragile, correct today** | R6-08, R6-10, R6-11, R6-13 | defer to planning.md carried-forward items | approved: defer to planning.md carried-forward items 2026-10-04 |
| **O2. Cleanup** | R4-10, R4-15, R4-16, R4-17, R5-14, R5-16, R6-15, R6-16 | add to the end-of-Phase-34 cleanup commit | approved: add to the end-of-Phase-34 cleanup commit 2026-10-04 |

## Batch 2: fixes merged (2026-10-04)

All ten fix themes are merged on `reframe-component`, 14 commits, each with a test that failed on the old code (two R5-12 tests guard against a false report and cannot fail on the old code). The full suite passes (1,872) and lint is clean. The register is 74 codes (new: `CONTENT_BODY_FALLBACK`, `TOC_UNREADABLE`, `TOC_SUBPROJECT_UNPLACED`, `LOCALIZED_ROOT_SKIPPED`, `ENGINE_ROOT_UNCONVERTED`). No finding was wrong. Merge conflicts: the register count, and `FlareRenderer`'s link method, where R5-06 (the file's letter case) and R5-08 (cross-root links) were combined so the case-folded lookup runs first and the cross-root resolution is the fallback.

| theme | commits |
|---|---|
| P | 15dc6ca (R4-01/12/13/14), 9ac989d (R6-07) |
| Q | bb317c6 |
| R | 0b3d892 (R5-02/03/04/05/07/13) |
| S | dafaaba (R5-08), e2f7eb6 (R5-06), 5571dc2 (R6-03/05/14) |
| T | 1bbcc92 |
| U | dfbaf3d |
| V | 57a9ff5 (R4-06/07/08), bcc869a (R5-09/12/15) |
| W | 778ac29 |
| X | e4f65b5 |
| Y | 08b3cb4 |


**Measured on scratch copies (main tree untouched):**
- EMS 10.5.1: 11 of 1,437 pages change, all intended (step 3 renumbered, table headings keep links and code, 4 captions restored, 7 code blocks out of list bullets). ActiveSpaces 5.2.0: 5 pages, all R5-07.
- Streaming 11.2.1: 7 of 2,538 files (list order on 5 pages, footnote links on 2). Dangling reports 43 → 37; duplicate-directory reports 0 → 8.
- Silver Fabric Enabler for ActiveSpaces 1.2.0: 4 units → 2, toc.yml 95 → 49 titles. Each guide once.
- All 24 localized roots are skipped by name (sfire-dsc 7.1.0, wf-as 9.3.x, wf-wf 9.3.x); the 15 `en`/`en-us` roots are kept.
- DITA cache samples: stray-space titles 14 → 0, legal page found 0/4 → 4/4.

**Output effects to apply by re-converting** (user to run in the mainstream session):
- **R4-12 moves published paths**: in every multi-book WebWorks version, the book that sat at the version root moves into its own folder (e.g. TRA Runtime Agent 5.12.x `palette.*.md` → `tib_Designer_palettes/`). Its 301 rows are regenerated by the re-convert.
- Re-convert needs `--force` (converter code changes do not invalidate a converted tree), and re-merge needs `--force` too (Phase 21's carried-forward item, confirmed again by R9-04).

**Flagged choices** (consistent with the docs; recorded, not decisions): R5-07 merges a following code block only into Flare step-table lists; R5-13 renders text popups as `<sup>1</sup> (body)`; R5-11 reports merged-project TOC nodes instead of placing them; R6-01 always reads multi-column lists down the columns (all 9 real ones sort that way); R6-04 accepts "Important Information" at TOC depth ≤ 2. Trees converted before the engine became part of the currency key are treated as matching. `--input` still writes the catalog version's state (outside R4-04; added to theme Z). New for X3: the converter writes ~half its files with CRLF and rewrites link-adjusted files with LF.

## Batch 3 (R7–R9): counts

Reviewed at `review-base-b3` (a976513), i.e. after batch 1's fixes and before batch 2's.

| unit | S1 | S2 | S3 | S4 | total |
|---|---|---|---|---|---|
| R7 WebWorks engine | 4 | 0 | 6 | 1 | 11 |
| R8 Transforms | 7 | 1 | 6 | 2 | 16 |
| R9 Reframe | 2 | 2 | 10 | 2 | 16 |
| **Batch 3** | **13** | **3** | **22** | **5** | **43** |

R7-01 was checked against architecture.md §5.3.4, which requires anchored TOC entries to be kept ("discarding it collapses distinct TOC entries onto one page"), so it is a defect, not a design rule. R9-03 is the root cause of the TRA Runtime Agent 5.13.0 move. The same version's support page (`trahelp/_templates/tibco-documentation-and-support-services-2.md`) has always carried the bad name. Batch 2's R5-02 fix (lists honour `start` in every engine) already corrects part of R7-02 and 40 Streaming lists in R8's count; the fixer measures what remains.

## Batch 3, grouped into fix themes

Triage approved by the user 2026-10-04, as proposed, including the AA condition (stop and ask if the toc dialect cannot carry an anchor) and renaming the TRA Runtime Agent 5.13.0 support page once AG is in.

| theme | findings | proposed | decision |
|---|---|---|---|
| **AA. Section entries deleted from the navigation** | R7-01 (S1), and the same rule in Flare | fix: keep anchored entries in toc.yml; if the html-to-md toc dialect (Phase 36) cannot carry an anchor, report and bring back as a decision | approved: fix 2026-10-04 |
| **AB. Wrong step numbers and list types** | R7-02 (S1), R8-14 | fix | approved: fix 2026-10-04 |
| **AC. WebWorks headings rendered as paragraphs** | R7-03 (S1) | fix | approved: fix 2026-10-04 |
| **AD. Version named after the wrong collection; book groups missing from navigation** | R7-04 (S1) | fix | approved: fix 2026-10-04 |
| **AE. Text dropped or garbled by the Markdown walk** | R8-01, R8-02, R8-03, R8-05, R8-06, R8-07 (S1), R8-13 | fix | approved: fix 2026-10-04 |
| **AF. Links and Help buttons that land in the wrong place** | R8-04 (S1), R9-01 (S1), R9-02 (S1), R8-08 (S2), R8-11 | fix | approved: fix 2026-10-04 |
| **AG. Page names and pins** | R9-03 (S2), R9-04 (S2), R9-05, R9-12 | fix; then give the TRA Runtime Agent 5.13.0 support page its proper name | approved: fix 2026-10-04 |
| **AH. Silent losses, false warnings, the "Unfiled" branch** | R7-05, R7-06, R7-07, R7-09, R9-09, R9-10, R9-11 | fix | approved: fix 2026-10-04 |
| **AI. Fragile, correct today** | R7-08, R7-10, R8-09, R8-10, R8-12, R9-06, R9-07, R9-08 | defer to planning.md carried-forward items | approved: defer to planning.md carried-forward items 2026-10-04 |
| **AJ. Docs that contradict the code** | R9-13, R9-14 | fix docs | approved: fix docs 2026-10-04 |
| **O3. Cleanup** | R7-11, R8-15, R8-16, R9-15, R9-16 | add to the end-of-Phase-34 cleanup commit | approved: add to the end-of-Phase-34 cleanup commit 2026-10-04 |
