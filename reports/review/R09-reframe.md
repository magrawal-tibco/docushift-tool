# R9 — Reframe: findings
Base: review-base-b3 (a976513) · Reviewed: `src/docushift/reframe/{__init__,policy,packer,pages,toc,manifest,renames,csh,review,audit,driver}.py`, `tests/unit/test_reframe.py` · Date: 2026-10-04

| S1 | S2 | S3 | S4 |
|---|---|---|---|
| 2 | 2 | 10 | 2 |

How things were measured. All 14 merged trees in `reframed/` were checked against their converted inputs in `output/`, read-only. The scripts are in `C:\tmp\review-R9\`:
- `verify.py` resolves every redirect, `toc.yml` row, `301.yml` row, `csh.yml` value and in-page link against the anchors the platform will actually generate from the rendered page.
- `purefrag.py` and `frag_demote.py` trace each source link fragment through the merge.
- `pin.py` checks layout pinning across versions.
- `carry_names.py` re-runs the frozen packer on TRA Runtime Agent 5.13.0.
- `probe/test_r9_probe.py` drives `Reframer` on pytest fixtures to check currency and pin refusal.

The findings history was read from `cache/state.db`, read-only. `pytest tests/unit/test_reframe.py`: 161 passed.

## Findings

### R9-01 · S1 · A same-topic `#fragment` link lands on another topic's heading once the merge renumbers duplicate headings
- **Where:** `pages.py:240-242`: a pure fragment is not `resolvable`, so `_retarget` returns it untouched. `packer.py:640-643`: `anchor_run` numbers the whole page's headings, so a topic's second `#### Import` becomes `import-1` or `import-2`.
- **What:** R4 leaves `#…` links alone. In the source topic, `#import` named that topic's own *Import* heading. On the merged page, `#import` names the first *Import* heading on the page, which belongs to an earlier topic.
- **Failing scenario:** `reframed/…/ems/10.5.1/user-guide/interoperation-with-apache-kafka.md`. Lines 213 and 245 link `[…](#import)` from inside the topics `jakarta-messaging-property-kafka` and `jakarta-messaging-body-kafka`. Their own headings are at lines 190 and 230, but both links resolve to the *Import* heading at line 170.
- **Confirmed:** yes. **9 links in 4 versions** (EMS 10.5.0: 1, EMS 10.5.1: 2, TRA Administrator 5.13.0: 1, TRA Runtime Agent 5.13.0: 5) resolved in their source topic and now resolve to a different topic's heading. `validate` cannot catch this, because the anchor exists. 14 further fragments were already dangling in the source, which is §8's case and not the merge's doing.
- **Suggested fix:** In `render`, rewrite a pure fragment through the same position map R9-02 needs: (topic, index of the heading in that topic's own anchor run) → the page-run anchor at that index.

### R9-02 · S1 · A cross-topic link to a sub-heading loses its sub-heading
- **Where:** `pages.py:246-253`. Both the intra-page and the inter-page branch emit the target *topic's* section anchor and discard `reference.fragment`.
- **What:** Since Phase 30, converted links point at the exact heading. Reframe replaces that heading's anchor with the anchor of the topic the heading sits in, and counts the link as `rewritten`.
- **Failing scenario:** TRA Administrator 5.13.0, `Changing_Domain_Administrator_User_Credentials.md` links `Advanced_Tab_.md#global-variables`. The merged page links `../setting-deployment-options/application-management-configuration-dialog.md#advanced-tab`. The target page has `#### Global Variables` at line 114, but the reader lands on `### Advanced Tab` at line 108.
- **Confirmed:** yes. **503 links** whose fragment names an existing non-first heading of the target topic: EMS 77 per version × 6, TRA Administrator 7, TRA Runtime Agent 34, ActiveSpaces 0. The code follows R4 to the letter, but R4 predates fragment-bearing links. The reader still reaches the right topic, just not the sub-section the author named. Nothing reports the change.
- **Suggested fix:** `assign` already computes every heading's page anchor. Keep a (topic, source anchor) → page anchor map, and use it whenever the incoming fragment names a heading in the target topic. Fall back to the section anchor only when it doesn't.

### R9-03 · S2 · Out-of-TOC pages are named in the root-level scope but written into their raw source folder (root cause of the TRA Runtime Agent 5.13.0 move)
- **Where:**
  - `packer.py:388-389`: `carry` builds `Topic` with `parent=""`.
  - `packer.py:612-616`: `assign` looks up name clashes in `taken_stems[slugify(parent)]`, which for `""` is the **root TOC scope**.
  - `packer.py:617-620`: the page is then placed at `_unique(first.source.parent, …)`.
  - `packer.py:668-670` and `707`: `relocate` leaves carried pages where they are.
  - Contributing: `driver.py:471`. `--renormalize` discards every pin, recorded or human.
- **What:** A page the TOC never lists is given a name as if it sat at the top of the navigation. So any top-level page with the same title forces a `-2`, even though the page is written somewhere else: its source directory, with source casing and source folder names in the URL.
- **Failing scenario:** TRA Runtime Agent 5.13.0 has two guides, Designer (`_templates/…`) and Runtime Agent (`trahelp/_templates/…`). The converted `toc.yml` lists only the Designer guide's legal and support pages, as top-level rows. The Runtime Agent guide's own pair is untocked and gets carried. Their titles clash with those top-level rows in scope `""`, giving `legal-and-third-party-notices-2` and `tibco-documentation-and-support-services-2`. The folder is then the source `trahelp/_templates/`. Each suffix guards against a clash that cannot happen in that folder, because `_unique` already deduplicates within it.
  - **Why the old name was better:** the findings history shows runs 123–319 (2026-09-23 → 10-02) reporting `trahelp/installation/Third_Party_Libraries_.md` and the support page as untocked. Before Phase 36 narrowed `is_legal_label`, "Third-Party Libraries" took the Runtime Agent root's legal slot and dropped out of the TOC. The real legal page stayed in the navigation under that guide and was relocated to `tibco-runtime-agent/legal-and-third-party-notices.md`. `rename-map.csv` recorded that name on 10-01. From run 326 (10-02) the converter picks the real legal page and drops it from the TOC with the rest of the second tail. The pin held it until `--renormalize` (run 332) recomputed it through the carry path above. This history is reconstructed from the findings messages, since the old `toc.yml` is gone.
- **Confirmed:** yes. `carry_names.py` runs the frozen packer on `output/…/tibco-runtime-agent/5.13.0` and gives exactly `trahelp/_templates/legal-and-third-party-notices-2.md` and `trahelp/_templates/tibco-documentation-and-support-services-2.md`. A unit probe reproduces the same with a two-node tree. **Other out-of-TOC pages:** across all 14 merged versions, before and after the re-merge, there are exactly **2 carried pages**, both in TRA Runtime Agent 5.13.0, and **both** are hit. The support page has published as `trahelp/_templates/tibco-documentation-and-support-services-2.md` all along, in the pre-J and current maps alike, and is still unpinned to anything better. ActiveSpaces and EMS carry none. `REFRAME_TOPIC_UNTOCKED` names both topics, but nothing reports the name they get. `project()`'s new topics share the same `parent=""` scope (`packer.py:287`). They are relocated afterwards, so they risk only a stray `-2`, and the 43 new-topic pages in projected versions show none.
- **Suggested fix:** Look up a carried page's name in the folder it is actually written to, and drop the root-scope check. Consider placing it beside the navigated page that shares its source directory: `trahelp/_templates/Home.md` → `tibco-runtime-agent/`, which reproduces the old name. Separately, an R5/X1 item: give a multi-root version's second guide its own legal and support rows, or say why not.

### R9-04 · S2 · A name written into `rename-map.csv`, or `--renormalize`, is ignored unless `--force` is also given
- **Where:** `driver.py:340-343`. The currency key is the convert checksum plus the policy key. Neither `rename-map.csv` nor `self.renormalize` takes part. `cli.py` `on_result` prints nothing for a `current` version.
- **What:** The documented workflow is "write a better name into `new_path` … the next run uses it" (`user-guide.md:993`). In fact the next run returns `CURRENT` and leaves the old name in place. `reframe --all --renormalize` over unchanged trees likewise changes nothing.
- **Failing scenario:** Merge, edit `new_path` for `users-guide/user-guide.md`, then run `reframe` again. The result is `current` and the tree still holds `user-guide.md`. A plain `--renormalize` run is also `current`.
- **Confirmed:** yes, by the probe (`test_rename_edit_without_force_is_ignored`, passing on the frozen code). In the real runs, J's re-merge worked only because J bumped `_ALGORITHM`, which changes the policy key. The user's TRA re-pin (run 333) rebuilt because the version was forced.
- **Suggested fix:** Make `--renormalize` imply `--force`, and add a digest of the approved rename map to the currency check (or say "rename-map.csv changed; re-merging"). Otherwise, correct the user guide to say `--force` is required.

### R9-05 · S3 · A refused rename-map pin is silent, though the docstring says the run reports it
- **Where:** `packer.py:728-746` (`continue` when `wanted in taken`); `driver.py:472-478` only counts applied pins.
- **What:** A pin to a path another page holds is dropped and the computed name is used, with no finding. The check is also order-dependent: a pin to a path that a later page is about to vacate is refused anyway.
- **Failing scenario:** A pin that sends `users-guide/user-guide.md` to `installation.md` is ignored. The probe records only `ORIGIN_SITEMAP_MISSING`.
- **Confirmed:** yes in the probe; no real `rename-map.csv` is in this state (unconfirmed in corpus).
- **Suggested fix:** Count refused pins and raise a warning naming each one. Resolve pins against the final set of paths rather than in page order.

### R9-06 · S3 · A pinned product's reference-version renames never reach its projected siblings
- **Where:** `driver.py:880-896`. `_reference_pages` runs `assign` but not `override`, so `layout_of` carries the computed names, not the reference's `rename-map.csv`.
- **What:** A writer who fixes a name in EMS 10.5.1's map renames that page in 10.5.1 only. Each sibling keeps its own recorded name, so the same page publishes under two names across versions. R1.4 exists to prevent exactly that.
- **Failing scenario:** Edit `new_path` for one page in `10.5.1/rename-map.csv` and re-merge all six versions. Five keep the old filename.
- **Confirmed:** unconfirmed. No pinned product has a hand-edited map yet (`pin.py`: 0 cross-version path differences today).
- **Suggested fix:** Apply the reference version's approved map inside `_reference_pages`, or document that a rename must go into every version's map.

### R9-07 · S3 · Siblings stay `CURRENT` when only the pinned reference re-lays out
- **Where:** `driver.py:340-343`, `policy.py:126-129`. The key holds the value `pin_layout_to`, not the reference's checksum or layout.
- **What:** Re-converting only the reference version (for example, `convert --version 10.5.1` after a Flare fix changes word counts) re-merges it with new boundaries, while every sibling reports `current` on the old projection.
- **Confirmed:** unconfirmed. Today all 10 siblings match their reference exactly (`pin.py`). Batch 2's Flare fixes will re-convert everything, which hides this.
- **Suggested fix:** Add the reference version's convert checksum to a sibling's currency key.

### R9-08 · S3 · Per-guide copies (Phase 29) are not carried through `project()` or `rename-map.csv`
- **Where:**
  - `packer.py:242`: `project` dedupes across the whole version, while `pack` dedupes per guide (`packer.py:171`).
  - `packer.py:234-238`: `group_of` keeps the first copy.
  - `renames.py:308-312`: two rows with one `old_path` collapse to the last row.
- **What:** In a pinned product, a topic listed under two guides gets one page in every sibling, though the reference has two. The second guide's row points into the first guide. Two copies also share one `old_path`, so after a title change the first copy can take the second's pinned URL.
- **Confirmed:** unconfirmed. In-scope duplicates are all within one guide (EMS 10.4.0/10.4.1). GridServer has `pin_layout_to: 7.2.0` and 13 cross-guide duplicates, but it is out of scope and not merged.
- **Suggested fix:** Scope `claimed` per root in `project`, and key the rename map on (guide, source).

### R9-09 · S3 · The post-swap page-count check reports an error but still marks the tree current
- **Where:** `driver.py:556-575`. The check runs after `swap`, records `REFRAME_SELF_CHECK_FAILED`, then stamps `reframe_source_checksum` and returns `REFRAMED`.
- **What:** The next run returns `CURRENT` and never re-checks, so a real "page written outside the layout" stays in place silently after the first report.
- **Confirmed:** reached by real data three times. Runs 248, 249 and 252 (2026-09-30) reported "118 page(s) merged but 116 Markdown file(s)". That was a false alarm from a long-path walk, but each tree was swapped in and stamped.
- **Suggested fix:** Don't stamp the checksum when this check fails, or move the count before the swap (the staging tree can be walked with `walk_files`).

### R9-10 · S3 · `_Source` inventories the converted tree with `rglob`, which silently skips paths over 260 characters
- **Where:** `driver.py:122`. Phases 29–30 replaced every other such walk with `walk_files`.
- **What:** If a skipped file is a TOC topic, the version fails with a named error. If it is an asset, it is not copied, and links to it are counted `unresolved` and reported as "present before the merge" (`driver.py:538-545`). That blames Stage 6 for a file Reframe dropped.
- **Confirmed:** unconfirmed. The longest converted path in the three families is 192 characters.
- **Suggested fix:** Use `utils/longpath.walk_files`.

### R9-11 · S3 · "Never raises" holds only for `OSError`
- **Where:** `driver.py:362-366`. `_Source.read` (`driver.py:144`) and `_navigation` (`driver.py:790`) can raise `UnicodeDecodeError`, which is a `ValueError`.
- **What:** One undecodable topic aborts the whole `reframe_many` selection instead of failing one version.
- **Confirmed:** unconfirmed. Every converted `.md` is UTF-8 today.
- **Suggested fix:** Catch `UnicodeDecodeError` alongside `OSError` and record it.

### R9-12 · S3 · `shortened` keeps re-queuing a page whose better name a human already chose
- **Where:** `packer.py:786-788`. The flag fires whenever the stem neither starts nor ends with the normalized title, and a pinned name is not exempt.
- **What:** The workflow R6 describes (write `activespaces-as-windows-services` into `new_path`) leaves the page in `review-queue.csv` on every later run, so the queue never empties.
- **Confirmed:** unconfirmed. No hand-written names exist yet. The one hand pin (the TRA legal page) contains its title.
- **Suggested fix:** Don't flag a page whose path came from an approved `rename-map.csv` row.

### R9-13 · S3 · Docs say a CSH identifier keeps its own anchor; since Phase 29 it gets the section anchor
- **Where:** `user-guide.md:976-978`; `csh.py:9-18` (module docstring); `csh.py:41-45`. The last is `CSH_HEADER`, which is written into every merged `csh.yml`: "Each identifier keeps its own anchor."
- **What:** `csh._value` (`csh.py:92-114`) replaces the fragment with the section anchor unconditionally.
- **Confirmed:** yes. All 154 merged `csh.yml` values equal the section anchor of their source topic (`verify.py`).
- **Suggested fix:** Rewrite the three passages to describe the section-anchor rule.

### R9-14 · S3 · The requirements document was never amended for Phase 29, and the user guide's numbers are stale
- **Where:**
  - `REFRAME-REQUIREMENTS.md:125` (anchor slug "from the source filename"; it is now the heading text).
  - `:139` ("with its anchor above it"; no anchor is emitted).
  - `:171` (R4.1, page "in its first topic's source directory"; `relocate` now mirrors the TOC folder chain).
  - `:187`, `:236` (`manifest/review-queue.csv`; the file is at the tree root).
  - `:258`, `:276` ("one anchor token per topic"; a topic with an H1 adds 0).
  - `user-guide.md:893` ("anchored `##` section").
  - `user-guide.md:905` ("Two keys"; also `toc_schema` and `keep_separate`).
  - `user-guide.md:998` ("18 pages out of 124"; now 19 of 159).
  - `review.py:35` ("the packer walks bottom-up"; Phase 28 made it top-down).
  - `toc.py:210` (a `--toc-schema` option that does not exist).
  - `packer.py:728-730` (`override` "reports it"; see R9-05).
- **Confirmed:** yes, each checked against code and data.
- **Suggested fix:** Amend R2, R2.1, R4.1, R6, §5 and §6 with "As built (Phase 29)" notes, as R1 was amended. Refresh the user-guide figures.

### R9-15 · S4 · Dead helpers
- **Where:** `pages.py:349-358` (`tally`, no caller); `toc.py:209-211` (`registered_schemas`, used only by a test).
- **Suggested fix:** Remove them, or wire `registered_schemas` into a real `--toc-schema` option.

### R9-16 · S4 · Three heading regexes must agree for anchor prediction
- **Where:** `driver.py:84` (`_HEADINGS`, predicts), `pages.py:63` (`_HEADING`, shifts), `validation/references.py` `_HEADING` (checks).
- **What:** The driver's comment says the first two "are free to diverge". If they do, the predicted section anchors stop matching the rendered page. The audit checks redirects against the *predicted* anchors (`audit.py:188`), not the rendered ones, so the drift would pass. Today all 11,673 redirect anchors resolve on the rendered pages.
- **Suggested fix:** Share one heading pattern, and have `_redirects` check against `added.anchors` the way `_csh` already does.

## Edge notes (for X1)
- **Convert → reframe, multi-root tails.** In a version with two Flare roots (TRA Runtime Agent 5.13.0), only the first root's support and legal pages become TOC rows. The second root's pair is left untocked and Reframe carries it (R9-03). The support page has been untocked since at least 2026-09-23. The legal page joined it on 2026-10-02, when Phase 36 changed the legal pick.
- **Convert's `csh.yml` fragments.** In the *converted* TRA trees, 154 of 154 CSH fragments name a marker that no heading backs. They resolve only in the merged trees, through Reframe's section-anchor fallback. Products that publish `output/` (not merged) ship those values as they are. That falls to R4/U.
- **Every `.md` under `output/` is a topic to Reframe.** Untocked ones are published as pages with `guide: Not in navigation`. Any non-topic Markdown that convert or a later stage writes into `output/` would be published too.
- **Reframe → sync, path length.** Reframe writes one file at 262 characters (TRA, `…/to-create-file-based-repository-domain-using-gui.md`) through `long_path`. Sync's 260 ceiling (theme D) has to be the gate. Belongs to X2.
- **Reframe → validate, carried pages.** Carried pages are absent from `toc.yml` by design, so reachability must exempt them downstream too. Their URLs expose source folders (R9-03).
- **Currency.** Reframe's `CURRENT` ignores `rename-map.csv`, `--renormalize` and the reference version (R9-04, R9-07). X3 should note that "unchanged input" does not include those.
- **`301.yml`** is built from `state.get_output_map`, so an `--input` run writes none (documented). All 11,601 rows in the 14 trees point at an existing page and anchor.

## Test gaps (real-data paths only)
- No test names a carried page whose title matches a top-level page. `test_a_carried_page_is_left_where_it_was_because_no_toc_names_it` pins the source-folder placement that R9-03 questions.
- No test feeds `rewrite_links` a fragment that names a sub-heading (R9-02). No test merges two topics with a repeated sub-heading and a same-topic `#link` (R9-01). Real data reaches both: 503 and 9 links.
- No test edits `rename-map.csv` and re-runs without `--force` (R9-04). Both rename tests force.

## Docs drift
R9-13 and R9-14. Also `carry`'s docstring (`packer.py:375`) says Runtime Agent 5.13.0's two untocked topics include "the target of a live link". Since 2026-10-02 the pair is the legal and support pages, not `Third_Party_Libraries_`. That is worth re-measuring when the docstring is touched.

## Checked and fine
- **Engine gate and C4:** the gate is inside `reframe_one` before any path is read, and nothing writes under `output/`.
- **Topic coverage:** in all 14 trees, source `.md` count = `redirects.yml` rows = `reframe.yml` sections (11,673), with no duplicates. `pages` in `reframe.yml` = `.md` files on disk (1,492) = `rename-map.csv` rows. Every rename-map `new_path` exists, and every `expected_aem_url` ends in that path.
- **Targets resolve:** all 11,673 redirect targets, 11,675 `toc.yml` rows (row count identical to the source TOC), 11,601 `301.yml` rows and 154 `csh.yml` values point at an existing page and an anchor the rendered page generates. Each CSH value is on its own topic's section. No cross-page `.md` link points at a missing page or anchor.
- **Cap and headings:** no multi-topic page exceeds `max_words`. On all 1,492 pages the first heading is H1, there is exactly one H1, and no level is skipped.
- **Layout pin (R1.4):** across the 10 projected versions, 0 shared topics are on a different page path from the reference, and no new topic joined a projected page.
- **The review queue's** flags and thresholds match R6 plus `shortened`. Queued rows name written pages (`audit._queue`).
- **The rename-map pin** is honoured for the restored TRA legal page (run 333, `RENAME_MAP_APPLIED 1`, file present at the pinned path).
- **Reading the TOC:** both dialects are read, and an unknown shape fails with a named error. A malformed `csh.yml` fails before anything is written.
