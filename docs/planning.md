# DocuShift Master Planning & Roadmap

> **Document Status:** Active Roadmap
> **Last Updated:** 2026-10-02
> **Target:** Multi-Stage Documentation Migration Pipeline (TIBCO & IBI -> AEM)

**This file holds open work only.** A phase is written here in full while it is planned
or being built. When it is done, its whole section moves verbatim to
`docs/history/phases/phase-NN.md` and leaves one row in the [index](#finished-phases).
A reference such as "planning.md Phase 22" or "planning.md §7.4" (a Phase 7 subsection)
resolves through that index. The one exception is **§7.5, the findings register**, which is a living
table and stays [here](#75-the-findings-register-living).

---

## 1. Active Phases

### Phase 34: A Modular Review of the Whole Tool — **In progress, 2026-10-02**

**Progress.** Base tagged `review-base` (7dda975); the frozen copy is the worktree `C:\github\docushift-tool-review`. Findings land in `reports/review/`, indexed in `reports/review/INDEX.md`. **Batch 1 (R1–R3) reviewed**: 52 findings (5 S1, 10 S2, 31 S3, 6 S4), grouped into 15 fix themes; **triage approved as proposed**. Themes A–L are **fixed and merged** (13 commits, 1,815 tests); the EMS re-merge that applies J awaits the user. J applied by `reframe --all --renormalize` (66 EMS pages renamed). **Batch 2 (R4–R6) reviewed**: 49 findings (10 S1, 9 S2, 24 S3, 6 S4) in 12 themes, awaiting triage.

The tool grew phase by phase, from Phase 1 to Phase 33, and each phase was
reviewed as a change. Nobody has read the whole thing end to end since. That is
about 29,000 lines in 80 modules. Done in one pass, that review would be shallow
everywhere. So it is split into **twelve component units**, each one sized to be
read fully in one sitting (about 1,500–3,300 lines), and **three cross-cutting
passes** that catch what a single-component review cannot see: mistakes in the
hand-off *between* stages.

Each unit follows the pipeline's own stage boundaries (§1 of `architecture.md`).
Its findings can then be read and fixed without loading the rest of the tool.

#### Decisions

| decision | what it means | why not the obvious alternative |
|---|---|---|
| **Component units, ordered by data flow** | Shared foundations first, then the stages in pipeline order (catalog → acquisition → engines → transforms → reframe → layout → validation), and the command layer last | Reviewing by stage alone puts all four HTML engines (~5,500 lines) into one unit, which is too big to read properly. Reviewing by file alone loses the stage context that says what "correct" means |
| **Find first, fix second** | A unit's review produces a findings file and **no code changes**. The user triages it (fix / defer / not a bug), and only then are the agreed fixes made, one commit per unit, each with a test | Fixing during the review mixes what was found with what was changed. It also skips the point where the user can say "that is intended" |
| **Wrong-but-silent output ranks highest** | Severity: **S1** wrong output with no warning, or data loss · **S2** wrong output that *is* reported, or a crash on real input · **S3** fragile but correct today · **S4** cleanup / simplification | This project's worst failures were all silent, e.g. a guessed URL that 404s while a success line prints beside it. A crash gets noticed, a quietly wrong page does not |
| **Output claims are measured, not argued** | A finding that says "this produces wrong output" is confirmed against real output in `families/`, `reframed/`, or the html-to-md cache before it is S1/S2. If it can't be confirmed, it is marked *unconfirmed* | Reading the code alone overstates bugs on paths the corpus never reaches and misses bugs on paths it reaches all the time |
| **Review a frozen commit, in its own worktree** | Phase 33 lands (or is parked) first. The review then runs against one tagged commit in a separate git worktree, so a second session can keep building while the review reads | Reviewing a moving tree means findings point at lines that have already changed |
| **Docs drift is a finding** | Each unit checks its `architecture.md` section against the code. Where they disagree, that is an S3 finding, whichever side is right | The docs are the plan of record. If they are wrong, the next phase is planned on a false picture |

#### The twelve component units

| # | unit | modules | ~lines | tests | architecture.md |
|---|---|---|---|---|---|
| R1 | **Foundations**: shared helpers, data model, config loading | `utils/*`, `models.py`, `config.py`, `origins.py` | 2,250 | `test_slug`, `test_naming`, `test_longpath`, `test_swap`, `test_csvio`, `test_config`, `test_origins` | §3.6, §4.4 |
| R2 | **Catalog & discovery**: docsite API, merge, scope, EOS, families | `catalog.py`, `discovery/*`, `apiref.py` | 2,850 | `test_catalog`, `test_discovery`, `test_sitemap`, `test_apirefs` | §2, §3.1–3.12 |
| R3 | **State & acquisition**: state ledger, download, unzip, inventory | `state.py`, `downloader/*`, `extractor/*` | 2,250 | `test_state`, `test_downloader`, `test_extractor`, `test_content_root`, `test_inventory` | §3.8–3.9, §4.3–4.5 |
| R4 | **Engine framework & converter driver**: detection, roots, CSH, navigation | `engines/base,detector,roots,csh,__init__`, `converter/*` | 2,700 | `test_roots`, `test_converter`, `test_navigation` | §3.4, §5.4 |
| R5 | **Flare engine** | `engines/flare.py`, `flare_toc.py` | 1,500 | `test_flare` | §5.1 |
| R6 | **DITA and DocBook engines** | `engines/dita.py`, `docbook.py` | 2,100 | `test_dita`, `test_docbook` | §5.2, §5.6 |
| R7 | **WebWorks engine** | `engines/webworks.py`, `webworks_toc.py` | 2,000 | `test_webworks` | §5.3 |
| R8 | **Transforms**: HTML → Markdown, tables, links, fragments, assets | `transforms/*` | 2,250 | `test_transforms` | §5 (core transforms) |
| R9 | **Reframe**: page merging, renames, packing, TOC | `reframe/*` | 3,300 | `test_reframe` | Phases 20, 28–30 |
| R10 | **Publishing layout**: distributor, router, redirects, versions | `sync/*` | 2,350 | `test_distributor`, `test_router`, `test_documents`, `test_archives`, `test_sync_versions` | §6 |
| R11 | **Validation & reporting**: checks, findings register, status views | `validation/*`, `reporting/*` | 2,850 | `test_validation`, `test_findings`, `test_reporting_views` | §7, findings register |
| R12 | **Command layer**: every CLI command's wiring, options, exit codes | `cli.py` | 2,950 | `test_cli`, `test_scaffolding`, `integration/test_pipeline_smoke` | `user-guide.md` |

#### What every unit checks, in this order

1. **Correctness**: does the code do what its `architecture.md` section says, on the inputs the corpus actually has?
2. **Silent failure**: every `except`, every default, every skipped row. Is it counted, reported, or swallowed?
3. **The unit's edges**: what it reads from the stage before it and what it promises the stage after. Mismatches are noted here, and settled in X1.
4. **Tests**: which behaviours the unit's tests pin and which they don't. A gap counts as a finding only where the untested path is reached by real data.
5. **Docs drift**: architecture/user-guide statements the code contradicts.
6. **Simplification**: dead code, duplicated helpers, needless indirection (S4 only, never mixed into a correctness fix).

#### The three cross-cutting passes (after R1–R12)

| # | pass | what it looks for |
|---|---|---|
| X1 | **Stage contracts** | Every hand-off: `products.csv`/`versions.csv` columns, the `families/` and `reframed/` path contract, `state.db` statuses, `output_map`/manifests. Does every writer and reader agree on name, type, and meaning? It is built from the edge notes the units collected in step 3 |
| X2 | **Filesystem & Windows safety** | Zip-slip, atomic writes, the 260-character ceiling, case-insensitive name collisions, CRLF/encoding on CSV round-trips, cleanup that deletes something it should keep (cf. Phase 16) |
| X3 | **Re-run consistency** | Re-running a stage on unchanged input gives byte-identical output; a partial run followed by a resume gives the same result as one clean run |

#### Output

- One findings file per unit: `reports/review/R01-foundations.md` … `X3-rerun.md`. Each finding has severity, location, the failing scenario, and whether it was confirmed against output.
- One index, `reports/review/INDEX.md`: counts by unit and severity, plus the user's triage decision per finding.
- A plain-language summary to the user after each unit: what was found, what needs a decision.

#### Steps

1. **Freeze.** Land or park Phase 33, tag the commit (`review-base`), create the review worktree.
2. **R1 → R12 in order**, one unit at a time. Each unit is reported and triaged before the next one starts, or in batches of three if fewer interruptions are preferred.
3. **X1 → X3**, built on the units' edge notes.
4. **Fix**, unit by unit, in triage order. One commit per unit, each fix with a test that fails before it, a full test-suite run per commit, and a re-run of an affected family where output changes.

*Exit: every unit and pass has a findings file; every finding has a triage decision; every "fix" is merged with a test; S1/S2 findings marked "defer" are recorded in `open-issues.md`; the test suite and lint are clean on the final commit.*

---

## Carried-Forward Open Items

Technical items a finished phase recorded as *open, not fixed*. Product-level issues
live in [`open-issues.md`](open-issues.md), not here. Both items below are **unverified
since they were written**. Phase 34 confirms or closes each one.

| from | item | where |
|---|---|---|
| Phase 7 | A `sync` destination path over 260 characters failed with `[WinError 3]` and left a `.part` folder. Phases 14–15's long-path work (`utils/longpath.py`, `PUBLISHED_PATH_TOO_LONG`) may have closed it | [phase-07.md](history/phases/phase-07.md) |
| Phase 21 | A converter change does not invalidate a merged tree: `reframe`'s currency check keys on the extracted source's checksum, so a re-conversion with new converter code is not re-merged without `--force` | [phase-21.md](history/phases/phase-21.md) |
| Phase 34 (R1–R3) | 14 fragile-but-correct items deferred at triage, theme M: R1-09, R1-10, R2-10, R2-12 – R2-18, R3-06, R3-09, R3-10, R3-13. Plus R2-09, a catalog check for the user (113 "unclassified" products already have a family typed in) | [reports/review/INDEX.md](../reports/review/INDEX.md) |

---

## 7.5 The Findings Register (living)

*Phase 7 defined this table; it stays here, not in the archive, because every phase that adds a finding code adds its row, and `tests/unit/test_findings.py` fails when a registered code is missing from it. Code and CLI messages cite it as "planning.md §7.5".*

The concrete deliverable of §7.1: every deferred "report line" in the three documents, given a code. **A test asserts that every code emitted is registered and every registered code is reachable** — which is how a promise made in prose three phases earlier stops being able to quietly evaporate.

**Eight rows were added by Phase 5b** (marked ⁵ᵇ). They are the report lines `architecture.md` §5.1 asked for in prose and this table had not yet given a code; the reachability half of that test is what forced the last of them — `ALERT_LABEL_UNMAPPED` was unreachable against a closed callout vocabulary, and rather than delete the code the detection was widened to the open `div.note<Kind>` convention it was written for.

**Stage 6 netted two** (⁶ᶜ, ⁶ᵈ, ⁶ᵉ) — three added and `ARCHIVE_ALSO_LIVE` removed as unreachable once `sync/archives.py` was built and the condition turned out not to arise. **Phase 7b added seven** (⁷ᵇ), which is the largest single jump and not the register growing loosely: `validate` is the first command whose entire job is to raise findings, so its §7.4 and `design.md` §9.6 obligations had no codes for the plain reason that nothing had ever been written to emit them. **Phase 7c added none** (⁷ᶜ marks the row it *reached*, not a row it created) and took `NOT_YET_EMITTED` from two to **one**: `CSH_IDENTIFIER_DROPPED` fires, and only `DOC_REFERENCE_MISSING` is left, waiting on §10.7's class 2. A phase that closes a debt without opening one is the register working the way it was meant to. Four more followed one at a time — `CODE_LINK_FLATTENED` (⁸), `INDEX_UNLINKED` (¹⁰ᵇ), `WHATS_NEW_PLACEHOLDER` (¹¹ᵃ) and `OUTPUT_COUNT_MISMATCH` (¹³) — and **the table is now 43 rows**. The forty-second is `ZIP_URL_UNRESOLVED` (¹⁴ᵃ) — the register's **first `download` row**, in the phase that discovered the stage had never successfully run — and the forty-third `PUBLISHED_PATH_TOO_LONG` (¹⁵ᵈ), `sync`'s **first error**, added one phase later and deliberately at the opposite severity: the download code names a condition a user can fix with `--from-file`, and this one names a path nothing downstream can open. Three of those four were added to the code and not to this table, and the drift stood until Phase 13 came looking: `test_the_register_carries_every_row_of_7_5` pins the register's size against itself, which cannot see a missing row here. `test_the_published_table_carries_every_registered_code` now reads this file and asserts every registered code appears in it, so the next omission fails a test rather than waiting to be noticed.

| Code | Sev | Stage | Obligation | Specified in |
| :--- | :--- | :--- | :--- | :--- |
| `SCOPE_RULE_UNMATCHED` | warn | catalog | A `scope.yaml` rule matching no product | `design.md` §8.2.5 |
| `EOS_ALIAS_STALE` | warn | catalog | An alias naming a product the active report lacks | `design.md` §8.2 |
| `EOS_PRODUCT_EMPTIED` | warn | catalog | Retirement left a product with nothing to convert (11 products) | Phase 3.7 |
| `BATCH_NOT_ELIGIBLE` | warn | catalog | Tagged into a batch but not eligible | `design.md` §8.2.2 |
| `MIGRATE_SHEET_SLUG_UNMATCHED`²⁵ | warn | catalog | A migration-export slug matching no catalogued product (104 slugs, 410 rows, 91 marked migrate) | Phase 25 |
| `MIGRATE_ALIAS_STALE`²⁵ | warn | catalog | An alias naming a slug the active export lacks | Phase 25 |
| `MIGRATE_DECISION_CONFLICT`²⁵ | warn | catalog | `migrate_decision` disagrees with `convert_eligible` (376 versions; 458 on the first apply) | Phase 25 |
| `ZIP_URL_UNRESOLVED`¹⁴ᵃ | warn | download | No ZIP endpoint could be derived for an active version (7 of 35 sampled products); supply it with `--from-file` | Phase 14a |
| `PUBLISHED_PATH_TOO_LONG`¹⁵ᵈ | error | sync | A file's published path would exceed 260 characters; the tree is skipped rather than half-copied | Phase 15d |
| `CSH_SOURCE_EMPTY` | note | extract | CSH source present but empty — no `csh.yml` written | `architecture.md` §5.4.2 |
| `CSH_SOURCE_UNPARSED` | warn | extract | Source located but failed to parse; `_has_csh` still set | `design.md` §6.2 |
| `INVENTORY_PARTIAL`³⁴ | warn | extract | A directory in the extracted tree could not be read; the inventory columns are left blank, not the previous package's | Phase 34 (R3-04) |
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
| `FRAGMENT_RETARGETED`³⁰ | note | convert | Cross-references pointed at a heading instead of an inert `<a id>` the platform does not honour | Phase 30 |
| `FRAGMENT_UNPLACEABLE`³⁰ | warn | convert | A cross-reference naming an anchor with no heading behind it; left as written and will not resolve | Phase 30 |
| `RENAME_MAP_APPLIED`²⁹ | note | reframe | Page names taken from `rename-map.csv` rather than recomputed, so a published URL does not move when a title is edited | Phase 29 |
| `HEADING_LEVEL_NORMALIZED`²⁷ | note | convert | Headings renumbered to close a level the source skipped; depth and order unchanged. One row per version; `count` is how many | Phase 27 |
| `DEFINITION_TERM_RECOVERED`²⁷ | note | convert | Terms marked up as `class="dt"` rather than `<dt>`, retagged so they publish as terms instead of as prose | Phase 27 |
| `INDEX_UNLINKED`¹⁰ᵇ | note | sync | A published document no `index.md` links to — the reverse of `LINK_BROKEN` | Phase 10b |
| `WHATS_NEW_PLACEHOLDER`¹¹ᵃ | note | convert | What's New shipped as the unfilled MadCap template (167 of 648 roots); not published | Phase 11a |
| `OUTPUT_COUNT_MISMATCH`¹³ | warn | convert | Fewer Markdown files on disk than documents converted; two writes landed on one path | Phase 13 |
| `REFRAME_TOC_SCHEMA_UNKNOWN`²⁰ᵃ | error | reframe | No TOC adapter matches this version's `toc.yml`; refusing to merge a partly-understood tree | `REFRAME-INTEGRATION-PLAN.md` §4 Phase 0 |
| `REFRAME_LAYOUT_UNPINNED`²⁰ᵃ | warn | reframe | More than one eligible version of this doc set and no pinned layout; versions may not correspond | `REFRAME-REQUIREMENTS.md` R1.4 |
| `REFRAME_PIN_UNAVAILABLE`²⁶ | error | reframe | `pin_layout_to` names a version whose layout cannot be computed; the versions pinned to it are refused rather than merged on their own boundaries | `REFRAME-REQUIREMENTS.md` R1.4 |
| `REFRAME_SELF_CHECK_FAILED`²⁰ᵇ | error | reframe | A §6 acceptance check failed; the merged tree was discarded rather than swapped in | `REFRAME-REQUIREMENTS.md` §6 |
| `REFRAME_LINK_UNRESOLVED`²⁰ᵇ | warn | reframe | Relative references pointing outside the converted tree, left as written; present before the merge | `REFRAME-REQUIREMENTS.md` R4, §8 |
| `REFRAME_TOPIC_UNTOCKED`²⁰ᵇ | warn | reframe | Topics absent from `toc.yml`, carried through unmerged and unreachable from navigation | `REFRAME-REQUIREMENTS.md` R3 |
| `REFRAME_REVIEW_QUEUED`²⁰ᶜ | note | reframe | Merged pages needing an editorial decision, listed in `review-queue.csv` | `REFRAME-REQUIREMENTS.md` R6 |
| `SYNC_MERGE_UNAVAILABLE`²⁰ᵈ | warn | sync | A product set to publish merged has no current reframed tree; it publishes nothing rather than falling back | §20d |
| `REDIRECT_SHADOWED`²⁰ᵈ | warn | validate | A redirect whose source path still exists in the published tree; a 301 loop where the two differ only in case | `REFRAME-REQUIREMENTS.md` R5 |
| `REFRAME_KEEP_SEPARATE_UNMATCHED`²⁰ᵉ | warn | reframe | A `keep_separate` path matches no topic in this version; the merge a writer meant to undo still happened | §20e |
| `ORIGIN_TEMPLATE_UNDECLARED`²² | warn | convert ³⁵ | No verified docsite URL template for this product, so no `301.yml` was written; a guessed origin URL redirects to a page that never existed | Phase 22 |
| `ORIGIN_SITEMAP_MISSING`³³ | warn | convert ³⁵ | No Coveo sitemap page list for this version and no declared template, so no `301.yml` was written | Phase 33 |
| `ORIGIN_URL_UNLISTED`³³ | note | convert ³⁵ | Converted topics whose origin URL the docsite sitemap does not list; a derived row is withheld rather than written unproven | Phase 33 |
| `ORIGIN_PAGE_UNMAPPED`³³ | warn | convert ³⁵ | Live docsite pages no `301.yml` row starts from (API reference, PDFs, help frames) — each a 404 at cutover unless redirected elsewhere | Phase 33 |
| `ORIGIN_TEMPLATE_REJECTED`³⁴ | warn | convert | A declared docsite URL template failed validation and was ignored; the version fell back to the sitemap, or wrote no `301.yml` without one | Phase 34 (R1-07) |
| `ORIGIN_PATH_TOO_SHORT`³⁴ | warn | convert | Converted topics whose source path is shorter than the template's `drop_segments`, so they have no `301.yml` row; counted per source | Phase 34 (R1-07) |

---

## Finished Phases

| phase | title | status | write-up |
|---|---|---|---|
| 1 | Architecture, Living Docs & Project Scaffolding | Complete, 2026-09-03 | [phase-01.md](history/phases/phase-01.md) |
| 2 | Catalog Migration to CSV, Catalog Manager & State Engine | Complete, 2026-09-03 | [phase-02.md](history/phases/phase-02.md) |
| 3 | Docsite Discovery Engine (`docs.tibco.com` API Client) | Complete, 2026-09-09 | [phase-03.md](history/phases/phase-03.md) |
| 3.5 | Product Scope Exclusions | Complete, 2026-09-09 | [phase-03.5.md](history/phases/phase-03.5.md) |
| 3.6 | Re-key the Catalog on `slug` | Complete, 2026-09-10 | [phase-03.6.md](history/phases/phase-03.6.md) |
| 3.7 | End-of-Support Exclusions | Complete, 2026-09-10 | [phase-03.7.md](history/phases/phase-03.7.md) |
| 3.8 | Publishing-Name Rework — `-userdocs` Repositories | Complete, 2026-09-10 | [phase-03.8.md](history/phases/phase-03.8.md) |
| 4 | Package Downloader & Extractor | Complete, 2026-09-11 | [phase-04.md](history/phases/phase-04.md) |
| 5 | Multi-Engine HTML -> GFM Conversion & Transforms | Complete, 2026-09-12 | [phase-05.md](history/phases/phase-05.md) |
| 6 | AEM Architecture Synthesis & Publishing Layout | Complete, 2026-09-15 | [phase-06.md](history/phases/phase-06.md) |
| 7 | CLI, Reporting & Verification Dashboard | Complete, 2026-09-16 | [phase-07.md](history/phases/phase-07.md) |
| 8 | The Code-Span Link Swallow | Complete, 2026-09-16 | [phase-08.md](history/phases/phase-08.md) |
| 9 | A Generated `toc.yml` Points at Pages, Not at Artifacts | Complete | [phase-09.md](history/phases/phase-09.md) |
| 10 | A Version With One Output Root Publishes At Its Version Root | Complete | [phase-10.md](history/phases/phase-10.md) |
| 11 | The Landing Page Keeps Its Product, Loses Its Portal | Complete | [phase-11.md](history/phases/phase-11.md) |
| 12 | An Extracted Tree Can Be Measured Without Its Package | Complete | [phase-12.md](history/phases/phase-12.md) |
| 13 | The Output Tree Is Counted Too | Complete, 2026-09-19 | [phase-13.md](history/phases/phase-13.md) |
| 14 | The Download Leg Has Never Run | Built, 2026-09-19 | [phase-14.md](history/phases/phase-14.md) |
| 15 | The Package Wrapper Is Not the Version Root | Built, 2026-09-19 | [phase-15.md](history/phases/phase-15.md) |
| 16 | The Converter Deletes the Targets Its Own Links Point At | Complete, 2026-09-19 | [phase-16.md](history/phases/phase-16.md) |
| 17 | WebWorks Rewrites Its Links in the Coordinate System It Does Not Publish In | Built, 2026-09-22 | [phase-17.md](history/phases/phase-17.md) |
| 18 | A Parent Product Publishes No Versions of Its Own | Built (18c–18d), 2026-09-23 | [phase-18.md](history/phases/phase-18.md) |
| 18e | The First DocBook Family Reaches Publication | Measured, 2026-09-23 | [phase-18e.md](history/phases/phase-18e.md) |
| 19 | A DocBook Admonition's Title Is Not Only a Label | Built, 2026-09-23 | [phase-19.md](history/phases/phase-19.md) |
| 20 | Reframe — A Flare Topic Is Too Small To Maintain | Built (20a–20f), 2026-09-24 | [phase-20.md](history/phases/phase-20.md) |
| 21 | A Passthrough Table Carries the Authoring Tool's Styling Into the Output | Built & verified, 2026-09-28 | [phase-21.md](history/phases/phase-21.md) |
| 22 | The Redirect Map Does Not Start Where the Reader Does | Built & verified, 2026-09-28 | [phase-22.md](history/phases/phase-22.md) |
| 23 | The Classes Went and Everything Else Stayed | Built & verified, 2026-09-28 | [phase-23.md](history/phases/phase-23.md) |
| 24 | The Row Stops One Stage Short | Built & verified, 2026-09-28 | [phase-24.md](history/phases/phase-24.md) |
| 25 | The Migration Verdict Nobody Can Read | Built & verified, 2026-09-28 | [phase-25.md](history/phases/phase-25.md) |
| 26 | The Layout Pin That Pins Nothing | Complete, 2026-09-29 | [phase-26.md](history/phases/phase-26.md) |
| 27 | Two Things the Source Says That the Markdown Does Not | Built, 2026-09-29 | [phase-27.md](history/phases/phase-27.md) |
| 28 | A Merged Page Was a Run of Siblings, Not a Subtree | Complete, 2026-09-30 | [phase-28.md](history/phases/phase-28.md) |
| 29 | The Filename Is the URL | Complete, 2026-09-30 | [phase-29.md](history/phases/phase-29.md) |
| 30 | Fifty Thousand Cross-References That Never Worked | Complete, 2026-10-01 | [phase-30.md](history/phases/phase-30.md) |
| 31 | Splitting WebFOCUS into Four | Complete, 2026-10-02 | [phase-31.md](history/phases/phase-31.md) |
| 32 | A Family Is a Human's Call | Complete, 2026-10-02 | [phase-32.md](history/phases/phase-32.md) |
| 33 | The Docsite Already Lists Every Page | Complete, 2026-10-02 | [phase-33.md](history/phases/phase-33.md) |
| 35 | Every Published Version Carries Its Cutover Map | Complete, 2026-10-02 | [phase-35.md](history/phases/phase-35.md) |
| 36 | `toc.yml` Speaks html-to-md's Dialect | Complete, 2026-10-02 | [phase-36.md](history/phases/phase-36.md) |

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
