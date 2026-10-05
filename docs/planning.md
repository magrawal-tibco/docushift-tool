# DocuShift Master Planning & Roadmap

> **Document Status:** Active Roadmap
> **Last Updated:** 2026-10-05
> **Target:** Multi-Stage Documentation Migration Pipeline (TIBCO & IBI -> AEM)

**This file holds open work only.** A phase is written here in full while it is planned
or being built. When it is done, its whole section moves verbatim to
`docs/history/phases/phase-NN.md` and leaves one row in the [index](#finished-phases).
A reference such as "planning.md Phase 22" or "planning.md §7.4" (a Phase 7 subsection)
resolves through that index. The one exception is **§7.5, the findings register**, which is a living
table and stays [here](#75-the-findings-register-living).

---

## 1. Active Phases

None. The next phase is planned here when the user approves it.

---

## Carried-Forward Open Items

Technical items a finished phase recorded as *open, not fixed*. Product-level issues
live in [`open-issues.md`](open-issues.md), not here. The rows below are the findings
Phase 34 deferred at triage, each fragile but correct today; their full entries are in
`reports/review/`. Phase 34 closed the two older items (Phase 7's over-260 sync path,
Phase 21's stale merge). Closing an item means deleting its row.

| from | item | where |
|---|---|---|
| Phase 34 (R1–R3) | 14 fragile-but-correct items deferred at triage, theme M: R1-09, R1-10, R2-10, R2-12 – R2-18, R3-06, R3-09, R3-10, R3-13. Plus R2-09, a catalog check for the user (113 "unclassified" products already have a family typed in) | [reports/review/INDEX.md](../reports/review/INDEX.md) |
| Phase 34 (R4–R6) | 4 fragile-but-correct DITA/DocBook items deferred at triage, theme Z: R6-08, R6-10, R6-11, R6-13. Also deferred by decision: publishing non-English Flare builds to the `loc-` tree (Q), and converting a version that mixes two generators with both engines (T) | [reports/review/INDEX.md](../reports/review/INDEX.md) |
| Phase 34 (R7–R9) | 8 fragile-but-correct items deferred at triage, theme AI: R7-08, R7-10, R8-09, R8-10, R8-12, R9-06, R9-07, R9-08 | [reports/review/INDEX.md](../reports/review/INDEX.md) |
| Phase 34 (R10–R12) | 5 items deferred at triage, theme BF: R10-04 (all-archived products get no archives page), R10-07 (API link URL shape, unconfirmed), R10-08, R10-12, R11-10 | [reports/review/INDEX.md](../reports/review/INDEX.md) |
| Phase 34 (X1–X3) | 6 items deferred at triage, theme XJ: X1-09 (two sources for the docsite folder; 11 active rows disagree, needs the network to settle), X1-13, X1-14, X1-15, X1-16, X3-12 | [reports/review/INDEX.md](../reports/review/INDEX.md) |

---

## 7.5 The Findings Register (living)

*Phase 7 defined this table; it stays here, not in the archive, because every phase that adds a finding code adds its row, and `tests/unit/test_findings.py` fails when a registered code is missing from it. Code and CLI messages cite it as "planning.md §7.5".*

The concrete deliverable of §7.1: every deferred "report line" in the three documents, given a code. **A test asserts that every code emitted is registered and every registered code is reachable** — which is how a promise made in prose three phases earlier stops being able to quietly evaporate.

**Eight rows were added by Phase 5b** (marked ⁵ᵇ). They are the report lines `architecture.md` §5.1 asked for in prose and this table had not yet given a code; the reachability half of that test is what forced the last of them — `ALERT_LABEL_UNMAPPED` was unreachable against a closed callout vocabulary, and rather than delete the code the detection was widened to the open `div.note<Kind>` convention it was written for.

**Stage 6 netted two** (⁶ᶜ, ⁶ᵈ, ⁶ᵉ) — three added and `ARCHIVE_ALSO_LIVE` removed as unreachable once `sync/archives.py` was built and the condition turned out not to arise. **Phase 7b added seven** (⁷ᵇ), which is the largest single jump and not the register growing loosely: `validate` is the first command whose entire job is to raise findings, so its §7.4 and `design.md` §9.6 obligations had no codes for the plain reason that nothing had ever been written to emit them. **Phase 7c added none** (⁷ᶜ marks the row it *reached*, not a row it created) and took `NOT_YET_EMITTED` from two to **one**: `CSH_IDENTIFIER_DROPPED` fires, and only `DOC_REFERENCE_MISSING` is left, waiting on §10.7's class 2. A phase that closes a debt without opening one is the register working the way it was meant to. Four more followed one at a time — `CODE_LINK_FLATTENED` (⁸), `INDEX_UNLINKED` (¹⁰ᵇ), `WHATS_NEW_PLACEHOLDER` (¹¹ᵃ) and `OUTPUT_COUNT_MISMATCH` (¹³) — and the table grew past forty rows; it now carries every registered code, and a test counts them so this paragraph does not have to. The forty-second is `ZIP_URL_UNRESOLVED` (¹⁴ᵃ) — the register's **first `download` row**, in the phase that discovered the stage had never successfully run — and the forty-third `PUBLISHED_PATH_TOO_LONG` (¹⁵ᵈ), `sync`'s **first error**, added one phase later and deliberately at the opposite severity: the download code names a condition a user can fix with `--from-file`, and this one names a path nothing downstream can open. Three of those four were added to the code and not to this table, and the drift stood until Phase 13 came looking: `test_the_register_carries_every_row_of_7_5` pins the register's size against itself, which cannot see a missing row here. `test_the_published_table_carries_every_registered_code` now reads this file and asserts every registered code appears in it, so the next omission fails a test rather than waiting to be noticed.

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
| `NAV_NODE_DROPPED` | note | convert | A node with no page and no children — DITA's `lof`/`lot`/`ix` (first top-level node in 246 books), Flare's 7 childless headless nodes — or a Flare/WebWorks child that repeats its parent's page *and* bookmark exactly. A child pointing at a section of its parent's page is kept as `page.md#anchor` (Phase 34, R7-01) | Phase 5, Phase 34 |
| `OUTPUT_ROOT_MISSING`⁵ᵇ | warn | convert | Engine detected, no unit of work found — the 5 partial Flare outputs | `architecture.md` §5.1.1 |
| `CONTENT_MISSING`⁵ᵇ | warn | convert | A topic with no content container — reported, never guessed at | `architecture.md` §5.1.6 |
| `CONTENT_BODY_FALLBACK`³⁴ | note | convert | A Flare root whose skin writes no content container; its MadCap topics were converted from `<body>`, one row per root (10 Statistica roots, ~1,485 topics) | Phase 34 (R5-09) |
| `TOC_UNREADABLE`³⁴ | warn | convert | A Flare root's `HelpSystem.xml` or declared TOC is missing or did not parse; or a WebWorks book's `files.js`, `toc.js`, `title.js` or `context.js` is present and unreadable, or (`files.js`/`toc.js`) yields no entries. Its topics are filed under Unfiled, or the book loses what that file named | Phase 34 (R5-12, R7-09) |
| `TOC_SUBPROJECT_UNPLACED`³⁴ | note | convert | A merged-project TOC node (`*.flprj`, 121 over 937 roots) marking where a sub-project's TOC goes; dropped, so the sub-guide loses its place in the parent's navigation | Phase 34 (R5-11) |
| `TOC_ORPHAN`⁵ᵇ | note | convert | Converted topics in no TOC entry, filed under Unfiled — 14.1% for Flare | `architecture.md` §5.1.4 |
| `TOPIC_LINK_DANGLING`⁵ᵇ | note | convert | A cross-reference to a topic this run did not produce; text kept, link dropped | `architecture.md` §5.1.3 |
| `ALERT_LABEL_UNMAPPED`⁵ᵇ | warn | convert | An admonition label outside the five GitHub renders; rendered as NOTE | `transforms/callouts.py` |
| `ANCHOR_DROPPED`¹⁹ | warn | convert | A referenced anchor the engine kept and then did not emit; its links now dangle | `planning.md` Phase 19 |
| `LANDING_PAGE_EMPTY`⁵ᵇ | note | convert | A landing page with nothing past its hero — a stub was generated (4.5% measured) | `architecture.md` §5.1.5 |
| `TAIL_PAGE_MISSING`⁵ᵇ | warn | convert | No support or no legal page in the TOC — nothing is synthesized | `architecture.md` §5.1.5 |
| `ENGINE_ROOT_UNCONVERTED`³⁴ | warn | convert | A unit of work for a second convertible engine (a WebWorks book inside or beside a Flare root, as in BusinessConnect 7.4.0), in a version converted by another; not converted, one row per root naming the engine | Phase 34 (R4-02) |
| `LOCALIZED_TREE_SKIPPED`⁵ᵇ | note | convert | A localized subtree inside an English unit, not converted | `architecture.md` §5.1.9 |
| `LOCALIZED_ROOT_SKIPPED`³⁴ | warn | convert | An output root built for another locale (24 in the corpus: `ja`, `ja-jp`, `de-de`, `fr-fr`, `es-es`), not converted into this locale's tree; one row per root, naming its locale | Phase 34 (R5-01) |
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
| `PATH_TOO_LONG`³⁴ | **error** | validate | A published file whose absolute path under `--target-dir` exceeds 260 characters, measured as `sync` measures it; Windows readers cannot open it (longest today: 236) | Phase 34 (R11-06) |
| `ANCHOR_MISSING`⁷ᵇ | warn | validate | A `#fragment` naming no heading in the file it resolves to (heading slugs only since Phase 29; an `id=`/`name=` attribute is not an anchor) | §7.4 |
| `ANCHOR_WRONG_HEADING`³⁴ | warn | validate | A same-page `#fragment` that resolves, but to an earlier topic's heading: a heading with the same title, renumbered `-N` by the merge, sits between the target and the link (R9-01; 3 in p35, all real) | Phase 34 (R11-02) |
| `LINK_EXTERNAL_DEAD`⁷ᵇ | warn | validate | An absolute URL that did not respond, under `--check-external` | §7.4 |
| `CSH_FRONTMATTER_MISMATCH`⁷ᵇ | warn | validate | `csh.yml` and a topic's frontmatter disagree about an identifier | `design.md` §9.6 |
| `CSH_ANCHOR_MISSING`³⁴ | warn | validate | A `csh.yml` anchor naming no heading on its page, so the Help button opens the page top instead of the section (318 in p35, R8-04's TRA 5.12.x markers). An anchor that only repeats its identifier stays `ANCHOR_MISSING` | Phase 34 (R11-03) |
| `TOC_ENTRY_DUPLICATED`³⁴ | warn | validate | Sibling `toc.yml` entries with one title opening different pages with identical bodies (frontmatter aside): the same page or guide published twice, as SFAS 1.2.0 and Streaming's `index.md`/`lvindex.md` are. One title on pages that differ is not reported | Phase 34 (R11-01) |
| `METADATA_INVALID`⁷ᵇ | **error** | validate | `metadata.yml` missing, unshaped, or with an empty `csg-product`/`csg-version` | `architecture.md` §6.2 |
| `DROPDOWN_INCONSISTENT`⁷ᵇ | warn | validate | `version.yml` disagrees with the version folders beside it | `architecture.md` §6.6 |
| `ARTIFACT_UNPARSED`⁷ᵇ | **error** | validate | An AEM YAML artifact that would not parse; its field checks were skipped | §7.4 |
| `SYNC_RESIDUE`⁷ᵇ | note | validate | A `.part` staging folder left by a sync that did not finish | §7.4 |
| `CSH_IDENTIFIER_DROPPED`⁷ᶜ | warn | validate | Present in the prior version, absent here (§7.6). One row per version; `count` is how many | this phase |
| `CODE_LINK_FLATTENED`⁸ | note | convert | Link inside a code block kept its words and lost its target; a GFM fence cannot hold one | Phase 8 |
| `ELEMENT_UNRENDERED`³⁴ | note | convert | Embedded media with no Markdown form (`iframe`, `video`, `svg` …); an absolute URL became a link, anything else kept only its fallback text. One row per version, counted by tag | Phase 34 (R8-13) |
| `FRAGMENT_RETARGETED`³⁰ | note | convert | Cross-references pointed at a heading instead of an inert `<a id>` the platform does not honour | Phase 30 |
| `FRAGMENT_UNPLACEABLE`³⁰ | warn | convert | A cross-reference naming an anchor with no heading behind it; left as written and will not resolve | Phase 30 |
| `RENAME_MAP_APPLIED`²⁹ | note | reframe | Page names taken from `rename-map.csv` rather than recomputed, so a published URL does not move when a title is edited | Phase 29 |
| `RENAME_MAP_REFUSED`³⁴ | warn | reframe | A name in `rename-map.csv` that another page ends up holding; the computed name is kept, and each refused pin is named | Phase 34 (R9-05) |
| `RENAME_MAP_UNMATCHED`³⁴ | warn | reframe | A row in `rename-map.csv` whose `old_path` no longer leads a page (a re-convert renamed the topic, or a boundary change merged it); its name is not used and the row is dropped from the rewritten map, each one named old -> new | Phase 34 (X1-07) |
| `RENAME_MAP_MISSING`³⁴ | warn | reframe | `rename-map.csv` is gone from a merged tree that had one (a failed or killed swap used to take it along); the names come from the copy `state.db` keeps, or are recomputed if none survives, and the message says which | Phase 34 (X2-02, X3-02) |
| `HEADING_LEVEL_NORMALIZED`²⁷ | note | convert | Headings renumbered to close a level the source skipped; depth and order unchanged. One row per version; `count` is how many | Phase 27 |
| `DEFINITION_TERM_RECOVERED`²⁷ | note | convert | Terms marked up as `class="dt"` rather than `<dt>`, retagged so they publish as terms instead of as prose | Phase 27 |
| `INDEX_UNLINKED`¹⁰ᵇ | note | validate | A published document no `index.md` links to — the reverse of `LINK_BROKEN` | Phase 10b |
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
| `CONVERT_FINDINGS_IN_EARLIER_RUN`³⁴ | note | convert | A `current` version whose tree was built by an earlier run that recorded errors or warnings for it; names that run, so `report --run last` is not silent about a tree that still has them | Phase 34 (X3-11) |
| `REFRAME_FINDINGS_IN_EARLIER_RUN`³⁴ | note | reframe | The same for a `current` merged tree | Phase 34 (X3-11) |

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
| 34 | A Modular Review of the Whole Tool | Complete, 2026-10-05 | [phase-34.md](history/phases/phase-34.md) |
| 35 | Every Published Version Carries Its Cutover Map | Complete, 2026-10-02 | [phase-35.md](history/phases/phase-35.md) |
| 36 | `toc.yml` Speaks html-to-md's Dialect | Complete, 2026-10-02 | [phase-36.md](history/phases/phase-36.md) |
| 37 | One Sheet for the Family Decision | Complete, 2026-10-04 | [phase-37.md](history/phases/phase-37.md) |
| 38 | Where Each Version Stands, on the Sheet | Complete, 2026-10-05 | [phase-38.md](history/phases/phase-38.md) |

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
