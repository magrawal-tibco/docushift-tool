# R11 — Validation & reporting: findings
Base: review-base-b4 (73cc93d) · Reviewed: `validation/{driver,tree,artifacts,links,references,csh}.py`, `reporting/{findings,report,status}.py` (plus the five `state.py` queries `report` uses and the `validate` command's gate in `cli.py`) · Date: 2026-10-04

| S1 | S2 | S3 | S4 |
|---|---|---|---|
| 2 | 0 | 10 | 3 |

**Real data used.** I ran `Validator(target, FindingsRun("validate"))` with no store, so nothing was written, over `C:\tmp\p35-aem` and `C:\github\tibco-docs-aem`. Both gave the same result: 28 products, 208 folders, 13.6k files, 148,471 references, 69,347 fragments, **0 errors, 537 `ANCHOR_MISSING`, 124 `REDIRECT_SHADOWED`**. That matches the last real run in `state.db` (run 331) row for row. Measurement scripts and fixtures are in `C:\tmp\review-R11\`.

## Coverage of defect classes found by hand

| class (earlier finding) | caught by `validate`? | cheap to add? | finding |
|---|---|---|---|
| Same-page `#fragment` lands on an earlier topic's heading after the merge renumbers duplicates (R9-01) | **No.** The anchor exists, and existence is all that is checked | **Yes.** A heuristic flags exactly R9-01's 3 EMS links in p35, with 0 false positives | R11-02 |
| Cross-topic link loses its sub-heading and lands on the topic heading (R9-02) | No | **No, structurally.** The anchor is valid and on the right page. Only the source anchor map knows the intent | — |
| Anchored section entries missing from `toc.yml` (R7-01) | No | **No, structurally.** The source TOC is not in the published tree. This belongs at convert (`NAV_NODE_DROPPED`) | — |
| Help-button marker anchor never retargeted, so the button opens the page top (R8-04) | **Partly.** `ANCHOR_MISSING` warning: all 318 TRA 5.12.x anchored values. Mixed in with 154 harmless ones; exit code 0 | Yes: a separate count or code for `csh.yml` anchors | R11-03 |
| Help-button anchor that exists but names the wrong section | No | No (same reason as R9-02) | — |
| Published paths over 260 characters (R1-01) | **No.** No length test anywhere | **Yes.** The folder walk already lists every path | R11-06 |
| Duplicate guides (R4-01) | **No.** SFAS 1.2.0 is duplicated in both published trees and gets 0 findings | **Yes**: duplicate sibling titles in `toc.yml`, identical page bodies | R11-01 |
| Link differs from its file only in letter case (R5-06 class) | Yes for in-folder links, `toc.yml`, `csh.yml` and per-version `redirects.yml`. **No** for tree-rooted links and the doc-class 301/redirect maps on Windows | Yes | R11-04 |
| Percent-encoded fragment naming an inert marker (R8-08) | Yes. The fragment is decoded, then misses: `ANCHOR_MISSING` | — | — |
| Dead marker cross-references (`FRAGMENT_UNPLACEABLE`, Designer add-in) | Yes. `ANCHOR_MISSING` 13/11/11, equal to convert's counts | — | — |
| Out-of-TOC page named into its raw source folder (R9-03) | No. The path is valid | No (a naming rule, not a link fact) | — |
| Text dropped or garbled, headings as paragraphs, step numbers (R5-02, R7-03, R8-01…07) | No | No, content-level | — |

## Findings

### R11-01 · S1 · Duplicate guides publish with no finding: nothing compares pages or TOC entries with each other
- **Where:** `validation/artifacts.py:156-187` (`_check_toc` only checks that each `url` resolves); `validation/links.py:107-118` (`FolderIndex` walks every file but compares none).
- **What:** No check looks for the same guide published twice. Two complete copies of a book, both listed in `toc.yml`, pass clean.
- **Failing scenario:** SFAS 1.2.0 in `C:\tmp\p35-aem` and in the real `C:\github\tibco-docs-aem`:
  - `toc.yml` lists "Installation" (lines 7, 111) and "User's Guide" (lines 49, 153) twice each.
  - 96 pages are two copies of 48 (`Tib_sfas_*` and `html/Tib_sfas_*`), with identical bodies.
  - `validate` records **0** findings for the product.
- **Confirmed:** yes. Validator run over both trees; md5 of page bodies; `toc.yml` inspected. A duplicate-sibling-title test over p35 finds 33 sibling groups. The 4 kinds I inspected are all real duplicates or mis-titles:
  - the SFAS guides
  - ActiveSpaces 4.10.x "Terminology Used to Address the TIBCO FTL Realm" ×3 under Unfiled, one of them a `-2` page
  - Streaming `index.md`/`lvindex.md`, byte-identical, both at the TOC root
  - EMS `msg_swapping` used as the title of the `#prefetch_none_timeout_request_reply` entry

  Identical page bodies: 28 groups, 41 extra files.
- **Suggested fix:** In `_check_toc`, warn on sibling entries with the same title. In the `FolderIndex` walk, add a note for pages with identical bodies (hash after the frontmatter). Use a new validate code.

### R11-02 · S1 · A fragment that lands on the wrong heading passes: anchors are matched by existence, not by meaning
- **Where:** `validation/links.py:199-209` (pure fragment), `:244-255`; `validation/references.py:228-254` (`anchors()` returns a set, so where each anchor sits on the page is lost).
- **What:** `#import` passes as long as some heading slugs to `import`. On a merged page that is the *first* "Import" heading, which belongs to an earlier topic (R9-01).
- **Failing scenario:** EMS 10.5.1 `user-guide/interoperation-with-apache-kafka.md:213` and `:245`, and 10.5.0 `:224`, each link `(#import)`. The reader lands on the Import heading of another topic. `validate` is silent.
- **Confirmed:** yes, on p35. A refined rule flags **exactly these 3 links** over all 13,608 pages: a pure `#x` where a heading slugged `x-N` sits between the `x` heading and the link. A looser rule (any `x-N` exists) flags 15. I read the 12 extra ones and all are correct (`#example` and `#c-programmers-checklist` link to the first heading, before the duplicate).
- **Suggested fix:** Keep each heading's line in `anchors()` (a map instead of a set). Warn when a pure fragment's target has a numbered twin between the target and the link. Cross-page cases (R9-02) cannot be caught this way.

### R11-03 · S3 · `ANCHOR_MISSING` cannot tell a Help button sent to the wrong place from a harmless dead fragment, and the measurement behind its severity no longer holds
- **Where:** `validation/csh.py:162-167`; `reporting/findings.py:478-486` (warning, justified by "11.6%").
- **What:** In p35, **all 472 anchored `csh.yml` values** raise the same warning:
  - **318 are R8-04's defect.** In TRA 5.12.x, WebWorks markers such as `#2256565` were never moved onto headings, so the Help button opens the page top instead of the section.
  - **154 are harmless.** In TRA 5.13.0 (Flare) the anchor is the identifier itself, e.g. `Advisories_Folder.md#aa.advisoriesfolder.helpurl`, on a page that is a single topic. The button lands correctly.

  Page anchors now miss at 65 of 69,347 (0.09%), not 11.6%.
- **Failing scenario:** `validate` over p35 exits 0 with 318 broken Help-button targets. A reader of the report cannot pick them out from the 154 harmless rows.
- **Confirmed:** yes. Counts from the validate run, broken down by file, plus `grep -c '#'` on all 7 `csh.yml` files.
- **Suggested fix:** Count `csh.yml` anchor misses separately (their own code, or a count per map). Re-measure before deciding whether either can gate. The identifier-as-anchor in Flare maps is X1/R4 material.

### R11-04 · S3 · Two existence checks fold letter case on Windows, against "case-sensitive on every platform"
- **Where:** `validation/links.py:214` (tree-rooted link: `(context.target / classified.path).exists()`); `validation/artifacts.py:463` (doc-class `redirects.yml` / `301.yml`: `long_path(target / c).exists()`).
- **What:** On Windows both checks pass a target that differs from the file only in case, so the link 404s on the Linux host. Every other check uses the case-exact `FolderIndex`.
- **Failing scenario:** Fixture `C:\tmp\review-R11\synth.py`: a help page links `t-docs-resources/.../index.html` and the file is `Index.html`; a doc-class `redirects.yml` row has `to: …/PAGE.html` and the file is `page.md`. **0 findings.**
- **Confirmed:** yes for the mechanism. On real data, none of p35's 820 tree-rooted links differs in case, so this is correct today. Tree-rooted fragments are not checked either: 300 of the 820 carry one, and all resolve today.
- **Suggested fix:** Resolve tree-rooted and redirect targets by exact-case directory listing (or a cached index per target folder), and check their anchors too.

### R11-05 · S3 · The origin 301 maps are only half checked: the per-version `301.yml` is never read, and nobody checks the anchors in the doc-class one
- **Where:** `validation/artifacts.py:193-246` (`_check_redirects` reads only `redirects.yml`); `validation/driver.py:220-222` (doc-class `301.yml`: file test only); docstring `artifacts.py:415-418`.
- **What:** The docstring says anchors "are checked by the per-version map". That holds for `redirects.yml` but not for `301.yml`. Nothing reads the per-version `301.yml`, so neither its file half nor its anchor half is checked anywhere.
- **Failing scenario:** A `301.yml` row `to: about-this-product.md#gone` publishes with no finding. A cutover redirect then lands on the page top, or on nothing if the page is missing.
- **Confirmed:** yes, as a gap. p35 has 27 per-version `301.yml` files with 22,218 relative rows, and every file and anchor resolves today (`check301.py`).
- **Suggested fix:** Run `_check_redirects` over `301.yml` as well (skipping its `from` side). Correct the docstring.

### R11-06 · S3 · Published path length is not checked
- **Where:** `validation/links.py:107-118` (the walk that already lists every path); no length test anywhere in `validation/`.
- **What:** `validate` cannot see R1-01's defect class (Windows readers fail on paths over 260). Only `sync` guards it now (theme D).
- **Failing scenario:** A tree synced before theme D, or by another machine, with a file at 288 characters validates clean.
- **Confirmed:** gap confirmed. The longest p35 path is 221 relative and 236 absolute, so there is no real instance today.
- **Suggested fix:** In the `FolderIndex` walk, compare `len(relative to target) + a clone-root budget`, or the actual absolute length, with 260. Report a validate-stage code; `PUBLISHED_PATH_TOO_LONG` is registered to `sync`.

### R11-07 · S3 · A hand-edited artifact that is not UTF-8 crashes the whole run
- **Where:** `validation/artifacts.py:76, :316, :356, :434` and `validation/csh.py:110`. All of them read strict UTF-8 and catch only `OSError`/`YAMLError`. The driver has no guard per folder, although `driver.py:4` promises "a failure is a returned outcome, never an exception".
- **What:** A `UnicodeDecodeError` escapes and aborts the run. Folders after it are never checked, and the run row is left unfinished.
- **Failing scenario:** Fixture `fx2`: `version.yml` saved in cp1252 with "révisé" (sync deliberately keeps hand-edited rows in this file) → `UnicodeDecodeError`, run aborted.
- **Confirmed:** yes, by fixture. No such file exists in the real trees.
- **Suggested fix:** Catch `UnicodeDecodeError` beside `OSError` and report `ARTIFACT_UNPARSED`.

### R11-08 · S3 · Anchors are lower-cased on both sides, so a `#Foo` link to heading `foo` passes
- **Where:** `validation/links.py:201, :248`; `validation/artifacts.py:182, :239`; `validation/csh.py:163`.
- **What:** The rule rests on "renderers fold anchor case" (`references.py` docstring). Browsers match fragment ids case-sensitively.
- **Failing scenario:** `[x](page.md#Install)` to `## Install` (slug `install`) passes. Whether it works depends on the AEM front end.
- **Confirmed:** unconfirmed: platform behaviour unknown. On p35, 0 of 69,282 matched fragments depend on the folding.
- **Suggested fix:** Compare case-exactly, and give a case-only miss its own message (as file links already have).

### R11-09 · S3 · Two reads still skip `long_path`
- **Where:** `validation/links.py:214` (tree-rooted `exists()`); `validation/csh.py:189` (`_read(folder.path / relative)`).
- **What:** This is the class behind the 60 false `LINK_BROKEN` already fixed in `check_redirect_map`. Past 260 characters, the first read returns False (a false **error**) and the second returns "" (a false `CSH_FRONTMATTER_MISMATCH`).
- **Failing scenario:** A tree-rooted link into a deep Javadoc path under a target root longer than about 75 characters, or a mapped help page past 260.
- **Confirmed:** gap confirmed by reading the code. On real data the longest tree-rooted target is 186 characters absolute; TRA help pages are short.
- **Suggested fix:** Wrap both in `long_path`, or read through the `FolderIndex`.

### R11-10 · S3 · `status --target-dir` "Published" does not nest under the funnel
- **Where:** `reporting/status.py:158` (counts every directory under `online-help/`); docstring `status.py:10` ("steps nest by construction").
- **What:** The count includes `.part` staging folders and every published version of a product, not only the selected eligible versions, so "Published" can exceed "Converted".
- **Failing scenario:** A product with a leftover `10-4-0.part`, or a retired version still on the shelf, counts one more published than converted.
- **Confirmed:** unconfirmed. p35 has no `.part` folders, and I did not build a catalog over it.
- **Suggested fix:** Skip `STAGING_SUFFIX`, and count only segments that match a selected eligible version's `version_segment`.

### R11-11 · S3 · Docs still say `id=`/`name=` attributes count as anchors; Phase 29 removed that
- **Where:** `docs/design.md:700`; `docs/planning.md:164` and `reporting/findings.py:485` (the `ANCHOR_MISSING` obligation, printed by `report --explain`); `validation/references.py:27`; `docs/architecture.md:2543`.
- **What:** `references.anchors()` (`:228`) counts heading slugs only. The register text and the docs describe the old rule.
- **Failing scenario:** A reader of `--explain ANCHOR_MISSING` concludes that an `<a id>` is a valid target.
- **Confirmed:** yes, by reading code and docs.
- **Suggested fix:** Reword the obligation to "naming no heading in the file it resolves to", and correct the four doc sites.

### R11-12 · S3 · The §7.5 table gives `INDEX_UNLINKED` the wrong stage, and the test cannot see it
- **Where:** `docs/planning.md:178` ("sync"); `reporting/findings.py:548` (`Stage.VALIDATE`); `tests/unit/test_findings.py:291-304` (presence check only).
- **What:** I compared all 74 rows: severities agree ("warn" = warning). The stage of `INDEX_UNLINKED` is the only mismatch.
- **Failing scenario:** `report --stage sync` finds no `INDEX_UNLINKED` rows that the table says belong there.
- **Confirmed:** yes. Script parsed the table and compared it with `REGISTRY`.
- **Suggested fix:** Fix the cell. Extend the test to compare the severity and stage columns.

### R11-13 · S4 · Dead code in `references.py`
- **Where:** `validation/references.py:55` (`_HTML_ANCHOR`, unused since Phase 29); `:216` (`slugify_heading` re-export; no caller in `src/` or `tests/`).
- **What:** Two dead definitions, and the docstring at `:27` still describes the first one as running.
- **Failing scenario:** n/a.
- **Confirmed:** yes (grep).
- **Suggested fix:** Delete both; adjust the docstring.

### R11-14 · S4 · One "resolve in this folder" check is written four times, with drift
- **Where:** `validation/links.py:222-255`, `validation/artifacts.py:166-186`, `:226-244`, `validation/csh.py:152-167`.
- **What:** Each copy does resolve → present → case hint → anchor. `_check_redirects` has already lost the case-only message the other three give.
- **Failing scenario:** n/a.
- **Confirmed:** yes (read).
- **Suggested fix:** One helper returning the finding or `None`, used by all four.

### R11-15 · S4 · Stale row count in the living §7.5 preamble
- **Where:** `docs/planning.md:119`.
- **What:** It says "the table is now 43 rows"; the table has 74.
- **Failing scenario:** n/a.
- **Confirmed:** yes.
- **Suggested fix:** Drop the number or say 74.

## Edge notes (for X1)
- **Version column format differs by stage.** `validate` writes the dashed folder segment (`10-4-0`) into the findings `version` column; every other stage writes the dotted version (`10.4.0`). This is deliberate (`tree.py:50-56`), but `report --slug X` mixes both forms, and nothing joins validate findings to convert findings for the same version.
- **Two `301.yml` shapes.**
  - Per-version: `to` is relative to the version folder (`about-this-product.md#…`).
  - Doc-class: `to` is a served URL (`us/en/{slug}/…/x.html#…`).
  - `disk_candidates` maps `{region}/{lang}` to the `{lang}-{region}` locale folder and `.html` to `.md`.
  - A `to` whose product folder is in no published tree is treated as "not ours" and skipped, so a misspelled slug in a `to` passes.
- **The anchor algorithm is shared.** The emitter, reframe's self-check (`reframe/driver.py:72` imports `validation.references.anchors`) and the validator all use `utils/anchors.anchor_run`. They agree by construction; whether they agree with the platform rests on `test_naming` alone.
- **Flare `csh.yml` writes the identifier as the anchor** (TRA 5.13.0, 154 values). These are dead fragments that `validate` reports. The owner is `transforms/csh.py` / R4.
- **`validate` writes its run to the configured `state.db`.** `cli.py`: `StateStore(cfg.state_db_path)`. Validating a scratch tree from the main config root therefore adds runs to the main database.
- **`.git` folders are walked.** Each published repo's `.git` is walked as a locale. This is harmless (no doc-class folders under it) and costs only time.
- **Other assumptions about the published layout.** `toc.yml` paths resolve from the version root; both TOC dialects are read. `archives/` is a unit with no segment. Only the six known doc-class names are walked; all present in both trees are known.

## Test gaps (real-data paths only)
- Tree-rooted link with a `#fragment` (300 in p35): no test says whether the anchor is checked. It is not.
- Per-version `301.yml` (27 files, 22,218 rows): untested because it is unchecked (R11-05).
- Tree-rooted link and doc-class redirect target differing only in case: the existing case tests cover in-folder, `toc.yml` and `csh.yml` only (R11-04).
- `test_the_published_table_carries_every_registered_code` checks that a code appears, not its severity or stage (R11-12).
- Non-UTF-8 artifact (R11-07).

## Docs drift
- R11-11: `id=`/`name=` anchors, in five places.
- R11-12: `INDEX_UNLINKED` stage.
- R11-15: "43 rows".
- R11-05: the `artifacts.py:415-418` docstring.
- R11-07: `driver.py:4` promises "never an exception".
- R11-10: `status.py:10` says the steps nest.
- `design.md:698` and `links.py:24` say resolution is "case-sensitive on every platform"; R11-04 shows two exceptions.
- `design.md:700` and the register justify the warning severity with an 11.6% miss rate; it is now 0.09% for page anchors (R11-03).

## Checked and fine
- **The gate.** `validate` exits 1 if and only if an error was recorded (`cli.py:2077-2081`), and an empty selection exits 1. Severity comes only from `REGISTRY`, and `record()` raises on an unregistered code. Every validate code's severity matches §7.5.
- **Note aggregation.** Notes fold by `(code, slug, version)` and reset per flush. Validate's two notes (`SYNC_RESIDUE`, `INDEX_UNLINKED`) aggregate as documented. Warnings stored with `count > 1` (`ORIGIN_PAGE_UNMAPPED`, 85 rows / 44,206; `FRAGMENT_UNPLACEABLE`, 71 / 642; `CSH_IDENTIFIER_DROPPED`, 5 / 475) carry the number in their message, so the export's missing Count column for warnings loses nothing.
- **Reproducibility.** The run is deterministic and matches `state.db` run 331 exactly.
- **Markdown masking.** Masking Markdown inside HTML blocks removes exactly 1 reference in 13,608 pages (the EMS printf string). There are 0 headings inside HTML blocks, 0 setext headings and 0 root-relative links. Percent-decoding of paths and fragments goes through `transforms/links.classify`.
- **Folder index.** It walks long paths through `walk_files` and is case-exact.
- **Redirects and CSH.** The 124 `REDIRECT_SHADOWED` rows are ActiveSpaces case-only loops, as designed. `CSH_FRONTMATTER_MISMATCH` and `CSH_IDENTIFIER_DROPPED` are 0 on p35. `natural_version_key` orders dashed segments correctly (`5-2-0` < `5-12-2` < `10-4-0`).
- **Report and status views.** `report` grouping, tally and prune keep their `runs` rows; `status` never reads findings; `report` never reads the catalog.
- **Tests.** The unit's 208 tests pass.
