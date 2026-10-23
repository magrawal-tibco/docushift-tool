# DocuShift Master Planning & Roadmap

> **Document Status:** Active Roadmap
> **Last Updated:** 2026-10-06
> **Target:** Multi-Stage Documentation Migration Pipeline (TIBCO & IBI -> AEM)

**This file holds open work only.** A phase is written here in full while it is planned
or being built. When it is done, its whole section moves verbatim to
`docs/history/phases/phase-NN.md` and leaves one row in the [index](#finished-phases).
A reference such as "planning.md Phase 22" or "planning.md §7.4" (a Phase 7 subsection)
resolves through that index. The one exception is **§7.5, the findings register**, which is a living
table and stays [here](#75-the-findings-register-living).

---

## 1. Active Phases

### Phase 40: The Download Is Named for the Version, Not the Product — **Built, 2026-10-05; network steps pending**

**Why.** Converting FOCUS on 2026-10-05, 9.1.0 and 9.1.1 failed to download: the docsite
publishes them as `tibco-focus-9-1-0_documentation.zip`, from before the ibi rebrand, while
`download` builds `ibi-focus-9-1-0` from the catalog slug. `architecture.md` §2.2 says the
package name "in every case measured" equals the slug plus the dashed version. The cases
measured were current versions only.

Measured 2026-10-05 (`C:\tmp\an_zip_names.py`, `an_sitemap_resolve.py`) against the 582
real package names in the html-to-md ZIP cache, 496 of which match a catalog row:

- **455 match** the template. **41 do not**: 18 are a brand swap (`ibi-`↔`tibco-`, e.g.
  Web Query for IBM i 9.0.x, MDM 10/11), and 23 are an older product name
  (`…-adapter-for-sap-7-3-1` for today's `…-plug-in-for-sap-solutions`). A prefix swap
  would fix fewer than half.
- **The Coveo sitemap names every version correctly.** Each product's index file lists one
  leaf per version, and the leaf's stem *is* the package name: `ibi-focus.xml` lists
  `tibco-focus-9-1-0`. Matched with the existing `sitemap.match_leaf`, the leaf equals the
  real name in **449 of 449** cases where one exists, and is never wrong. It fixes 37 of the
  41. It also explains the 4 `tibco-streambase-high-performance-fix-engine` versions
  already in `download-failed`: they are published as `spotfire-streambase-…`.
- **Ahead of us:** of the 1,435 active versions not yet downloaded, the sitemap gives a
  name different from the template for **96** (82 `tibco-`, 7 `ibi-`, 7 `spotfire-`).
  **615 have no leaf**, because `cache/coveo/` holds 288 products, not the whole scope.

#### Decisions

| decision | choice | why |
|---|---|---|
| **Where the name comes from** | For an active version, `download` tries the sitemap leaf's stem first, then the template, and takes the first that returns a readable ZIP. Archived rows and `zip_source=manual` are unchanged | The leaf was never wrong, but the template is the tested path for the 92% it covers, so it stays as the fallback. A second request happens only when the first fails |
| **No network for the sitemap** | `download` reads `cache/coveo/manifest.json` only. A product the cache does not hold gets today's behaviour | The sitemap already has a command with its own caching (`catalog sitemap`); `download` fetching it too would be two ways to fill one cache |
| **What the user sees** | `download --dry-run` prints which source each URL came from (`sitemap` or `template`). A failure lists every URL it tried | A failed fetch that names one URL hides that another was tried |
| **The stored `zip_url` column** | Unchanged. It stays the template's answer, as §2.2 already says for active rows | Writing the resolved URL back is a catalog-wide rewrite for a column `download` does not read |
| **No new finding code** | The existing failure line and `ZIP_URL_UNRESOLVED` cover it | The success case needs no report row; the dry-run is where to look |
| **FOCUS 9.1.0 / 9.1.1** | Stay `zip_source=manual`. The files on disk are the ones the sitemap name would fetch | Unpinning would re-download identical bytes |

#### Steps

1. `downloader/fetcher.py`: `resolve_urls()` returns the ordered candidates with their source; `download_one` tries each and records every failure in the message. `discovery/client.py`: `active_zip_url` takes the filename stem as an optional argument, so both sources share one template.
2. `--dry-run` output gains the source column.
3. Tests: sitemap name preferred; template used when the cache has no leaf; template tried after a sitemap URL fails; archived and manual rows unaffected; dry-run labels.
4. Measure: `download --all --dry-run` shows 96 rows sourced `sitemap`. Re-run `download` for the 4 StreamBase FIX Engine versions; they should land.
5. The user runs `catalog sitemap` over the whole scope (network, ~20 min) to fill the 615, then the dry-run is repeated.
6. Docs: `architecture.md` §2.2 (correct the "in every case" claim), `user-guide.md` download section, `CONTEXT.md`.

*Exit: the 4 StreamBase versions download; the dry-run counts match the measurement; tests and lint clean.*

**As built (2026-10-05).** The user approved the plan as written. Steps 1–3 and 6 done; 4 half done; 5 is the user's.

- **Only a "not a package" answer moves on.** `fetch_to` raises `NotAPackage` (an `OSError`) for a non-success status or a body that is not a ZIP. Any other failure ends the version as before, so a dropped connection keeps its resumable `.part` instead of losing it to the second URL.
- **`resolve_url` is now `resolve_urls`**, returning `(source, url)` pairs. The one test that patched the old name was updated. A sitemap name equal to the template's gives one candidate, labelled `sitemap`.
- **Dry run, measured.** `download --all --dry-run`: 1,665 versions, 930 `sitemap`, 627 `template`, 88 `archive`, 20 `manual`. Of the `sitemap` rows, **96 carry a name different from the template**, exactly the 96 predicted, including all 4 StreamBase FIX Engine failures (`spotfire-streambase-…`).
- **Tests:** 8 new in `test_downloader.py`, 1 in `test_cli.py`. Full suite 2,149 passed, lint clean.
- **StreamBase, done 2026-10-21:** the 4 versions downloaded under the sitemap name. Each is PDF-only (readme, licence, VPAT) like its siblings, and is published.
- **Pending (network):** `catalog sitemap` over the whole scope, then repeat the dry run.

---

### Phase 42: Merged Pages Are the TIBCO Default, for Flare and DITA — **Built, 2026-10-06; runs in progress**

**Why.** The user's decision, 2026-10-06: reframe applies to every TIBCO product except the
Streaming family, for **Flare and DITA** versions; WebWorks stays unmerged. Today `publish`
in `config/reframe.yaml` is set per product (EMS and ActiveSpaces only), the only wider
switch is `defaults`, which would also cover IBI, and the stage merges Flare only
(requirement C1). Three things stand in the way:

- **A version reframe does not merge would not publish at all.** With `publish: true`,
  `sync` (`distributor.py`, the merged-tree branch) refuses a version with no merged tree
  (`SYNC_MERGE_UNAVAILABLE`) and does not fall back. Engines are per version, and mixed:
  of the BusinessWorks plug-in versions detected so far, 145 are Flare, 64 DITA, 42
  WebWorks; TRA has 2 Flare and 13 WebWorks.
- **A multi-version product needs a hand-written pin** (`pin_layout_to`, R1.4), or each
  version is laid out on its own and raises `REFRAME_LAYOUT_UNPINNED`. With 85 plug-ins
  alone, writing those by hand does not scale.
- **DITA output repeats its support and legal pages in the TOC**, which reframe's
  acceptance check refuses.

**DITA, measured 2026-10-06** over the converted plug-ins (scratch root `C:\tmp\rf-dita`, the
engine gate opened in-process, the real workspace untouched):

- **The benefit equals Flare's.** Median words per converted topic: DITA 177, Flare 180,
  WebWorks 234; topics under 300 words: 71%, 70%, 57%. This is why WebWorks stays out.
- **The merge itself needs no change.** `plug-in-for-database` 8.5.0 merged as it stands,
  185 pages to 34 (81.6% fewer), with the TOC dialect detected and no error. The Flare
  control (`plug-in-for-snowflake` 6.3.1) merged 65 to 18.
- **Three of four failed for one reason.** `smartmapper` 7.1.2, `mongodb` 6.4.2 and `mdm`
  6.3.1 each fail `REFRAME_SELF_CHECK_FAILED` with exactly two more anchors than topics,
  and those two pages "not reachable from the TOC". In `mdm` 6.3.1's converted `toc.yml`,
  `important-information.md` and `tibco-documentation-and-support-services.md` are listed
  inside the Installation guide *and* again at the tail. `converter/navigation.py:_tail`
  is meant to move those pages ("Moved, never appended"); for DITA it does not find the
  existing entry and appends a second one. A conversion defect, visible in the unmerged
  TOC too.
- **Scale.** 64 DITA versions are known (all plug-ins). 1,115 TIBCO versions are not yet
  unpacked, so their engine is unknown; at the plug-in ratio that is roughly 200–300 DITA
  versions in all. Corpus-wide, DITA is the second engine: 371 versions to Flare's 595
  (`design.md` §7).

#### Decisions

| decision | choice | why |
|---|---|---|
| **Which engines merge** | Flare and DITA (`REFRAMABLE_ENGINES`). WebWorks, DocBook and the rest pass through, as today | Measured above. Requirement C1 is rewritten to say so |
| **Where the switch lives** | Two new optional blocks in `reframe.yaml`, between `defaults` and `products`: `bus: {tibco: {publish: true}}` and `families: {streaming: {publish: false}}`. Resolution order: defaults, BU, family, product, each key overriding the one before | Keeps the decision a reviewable line in the policy file, as the file's own comment requires. A per-product line still wins, so one product can be held back |
| **`publish` for a version reframe does not merge** | Publish the converted tree, as if `publish` were off, and record nothing. Only a Flare or DITA version is held to the merged tree | Nothing will ever merge it, so refusing it blocks the version for good. A Flare or DITA version keeps today's refusal when its merge is missing or stale, which is what protects live merged URLs |
| **Pinning** | When no `pin_layout_to` is written, the layout pins to the newest eligible Flare or DITA version, chosen by the same order `iter_versions` yields. A written pin still wins. `REFRAME_LAYOUT_UNPINNED` becomes a note naming the chosen version | This is the rule all four hand-written pins already follow. The cost: a newer version arriving later re-cuts the older ones. That is free until merged URLs go live, and writing the pin freezes it |
| **Mixed Flare/DITA products** | The pin is chosen among Flare and DITA versions together; a version whose layout cannot be projected from the pin falls back to its own layout, as a pin naming an unlayable version already does (`driver.py`, the pin check) | No special case. Whether any product mixes the two is not known until its packages are unpacked |
| **The DITA tail fix** | In conversion, not in reframe: `_tail` moves the DITA entry as it moves Flare's. `_CONVERTER_VERSION` is bumped, as every converter-output change is | Fixes the unmerged TOC as well. Working around it in reframe would leave every unmerged DITA TOC with duplicate entries |
| **The sign-off gate** | The user's decision stands in for each product's review-queue sign-off. Review queues are still written, for writers to work later | The file currently says publishing waits for a writer's review. This changes that policy, so the comment in the file is rewritten to say so |
| **IBI** | Unchanged: no BU block, so `publish: false` | Out of the decision |

**Side effect of the converter bump.** Every converted tree is stale to `convert` afterwards,
but `convert` only rebuilds what is unpacked, so families whose unpacked files were deleted
after publishing (wf-reporting-server, bw-plugin) are not touched. The fix changes DITA
TOCs only, so nothing else needs rebuilding. The 64 DITA plug-in versions must be
re-downloaded and unpacked (about 0.5 GB) to be re-converted.

#### Steps

1. `converter/navigation.py` (and `engines/dita.py` if the path it reports is the cause): the DITA support/legal entry is moved, not duplicated. Bump `_CONVERTER_VERSION`.
2. `reframe/driver.py`: `REFRAMABLE_ENGINES` gains DITA; the automatic pin and its note.
3. `reframe/policy.py`: `policy_for` takes the product's BU and family and applies the two new blocks. Callers in `reframe/driver.py` and `sync/distributor.py` pass them.
4. `sync/distributor.py`: a version whose engine is not reframable publishes its converted tree under any `publish` value.
5. `config/reframe.yaml`: the `bus` and `families` blocks; rewrite the sign-off comment.
6. Tests: a DITA TOC whose support/legal pages sit inside a guide comes out with each listed once, at the tail; resolution order (BU, family, product override); a WebWorks version under `publish: true` syncs its converted tree; a Flare or DITA version with no merge is still refused; the automatic pin picks the newest eligible version, and a written pin overrides it; a DITA tree merges end to end.
7. Measure before switching on: re-download, unpack and re-convert the 64 DITA plug-in versions (batch label `bwp-dita`), then `reframe` them. Exit for this step: no `REFRAME_SELF_CHECK_FAILED`, the merge ratio reported beside Flare's, and `csh.yml` entries surviving the merge on the DITA versions that carry context-sensitive help.
8. Run: `reframe --bu tibco` over everything converted (BusinessWorks plug-ins, TRA; EMS and ActiveSpaces are already current), then `sync --bu tibco --target-dir C:\github\tibco-docs-aem`, then `validate`. Streaming is left out by the family block.
9. Docs: `REFRAME-REQUIREMENTS.md` C1, `architecture.md` §6.6 (sync tree choice), `user-guide.md` reframe section, `CONTEXT.md`.

*Exit: every converted TIBCO Flare and DITA version except Streaming publishes merged pages; every other engine publishes converted pages; no `SYNC_MERGE_UNAVAILABLE` for a version reframe does not merge; tests and lint clean.*

#### As built (2026-10-06)

- **Steps 1–6 and 9 done.** `navigation._tail` now removes every further copy of the moved support or legal page (`NAV_NODE_DROPPED` counts them); `_CONVERTER_VERSION` is 2. MDM 6.3.1 re-converted lists each back page once and merges 67 topics into 11 pages with no self-check failure.
- **Two additions to the decisions.** The automatic pin prefers the newest eligible version that is *converted*, because an unconverted reference would fail every sibling. An automatic pin that cannot be laid out falls back to each version's own layout and still reports `REFRAME_PIN_UNAVAILABLE`; a written pin keeps today's refusal.
- **`REFRAME_LAYOUT_UNPINNED` is a note**, naming the chosen version. `reframe --dry-run` shows automatic pins in its Pinned column.
- **Step 7 scope.** 55 of the 64 DITA plug-in versions are in `bwp-dita`. MDM 6.3.1 was done by hand. The 8 that never converted are blocked by the Windows path-length defect in root finding and engine detection, and wait for that fix.
- **Step 8, first run (2026-10-06).** `reframe --bu tibco`: 138 reframed, 70 already current, 6 failed `REFRAME_SELF_CHECK_FAILED` (Kafka 5.0.0, Database 7.2.1/7.3.1/7.3.2, SAP 7.3.2, FTL 5.0.0). All six are orphan topics merged into an Unfiled page with blank titles, so two topics anchor to `""`. Phase 43 removes the cause. Sync waits for it.

### Phase 43: Orphan Topics Stay Out of the TOC and Unmerged — **Built 2026-10-07; runs pending**

**Why.** The user's decision, 2026-10-06: a topic that is in no source TOC entry may be an
orphan the authors meant to hide, so the tool must not add it to the navigation or merge it
into other pages, because both change the content of the docset. Orphans are kept as their
own files in an `unfiled/` folder and left out of `toc.yml`. This reverses
`architecture.md` §5.2.3, which appends them under an explicit "Unfiled" node.

**Measured 2026-10-06** over the converted output (`scratch/orphan_survey.py`):

| engine | versions with orphans | orphan topics | share of topics | linked from a TOC page | CSH targets | in `301.yml` |
|---|---|---|---|---|---|---|
| Flare | 224 of 253 | 5,950 | 5.9% | 588 | 359 | 4,451 |
| WebWorks | 11 of 53 | 141 | 1.5% | 0 | 0 | 113 |
| DITA | 9 of 56 | 19 | 0.4% | 1 | 0 | 17 |
| DocBook | 0 of 8 | 0 | — | — | — | — |

- **The Unfiled node does harm today.** 461 of its entries in 49 Flare versions have a blank
  title, because the topic has no `h1` and the node takes the label from the topic. 6 TIBCO
  merges fail on it (Phase 42, step 8). Merged ActiveSpaces 4.10.0 lists a topic named
  `temp_tibDateTime_ExcludeFromTOC`.
- **Orphans are still reached.** 588 are linked from a page the TOC lists, 359 open from
  product help (CSH), and 4,451 are where an old docsite URL redirects. The user checked the
  39 samples in `reports/orphan-link-examples.csv` (2026-10-07): all were links made by
  mistake.
- **244 converted versions carry an Unfiled node**: bw-plugin 152, webfocus 39,
  container-editions 18, wf-reporting-server 9, focus 9, di-ism 8, activespaces 6, ems 2,
  tra 1. About 160 of them (most of bw-plugin, all of wf-reporting-server) are no longer
  unpacked, so `convert` cannot rebuild them.

#### Decisions

| decision | choice | why |
|---|---|---|
| **Navigation** | No "Unfiled" node and no generated `unfiled.md` in any published `toc.yml`. The engines still build the node, and the pass removes it, so one mechanism serves new and old trees. `TOC_ORPHAN` still counts orphans, as a note | The user's rule |
| **Where orphans go** | `unfiled/` at the version root, keeping the topic's path below it: `users-guide/Smart_Engine.md` becomes `unfiled/users-guide/Smart_Engine.md` | One folder holds every page a reader cannot navigate to. Keeping the path avoids name clashes and keeps the file easy to trace to its source |
| **Links, CSH, redirects** | Links re-pathed so the tree stays consistent; AEM does not publish `unfiled/`, so links from listed pages break there. `csh.yml` retargeted. `301.yml` rows into orphans dropped, in `convert` and `reframe` (`origins.build`) | The user, 2026-10-07: "let the link break, AEM doesn't automatically publish unfiled topics". A redirect to an unpublished page only trades one 404 for another |
| **Merging** | Reframe copies each orphan through as one page at the same `unfiled/` path. It never merges it. The self-check skips the TOC-reachability test for `unfiled/` and checks the rest | Same URL in both trees. An orphan's content is unchanged |
| **How the move is done** | A pass over a written version tree (move the files, rewrite links in every page, rewrite `csh.yml` and `301.yml`, drop the node). `convert` runs it on its staging tree before the swap, and a new `docushift convert --reshelve-orphans` runs it on output already written | The pass needs no source files, so the ~160 versions that are no longer unpacked are fixed without a re-download |
| **Converter version** | `_CONVERTER_VERSION` 3 | Every converter-output change bumps it. A reshelved tree whose key matched version 2 is restamped current, so it is not rebuilt for this change alone |
| **TOC lost** | A version whose `toc.yml` lists nothing but the Unfiled node is left as converted | Its topics are orphans only because the TOC did not read (`TOC_UNREADABLE`); shelving all of them would publish an empty version |
| **Inbound links recorded** | Every link from a listed page into `unfiled/` is written to `unfiled/inbound-links.csv` in that version (linking page, line, link text, orphan, orphan title), and `validate` reports each one as `LINK_TO_UNFILED`, a note | The user, 2026-10-07: these links break on AEM, so they must be on record. The file is written where the tree is built, `convert` (and `--reshelve-orphans`) and `reframe`, in the staging tree before the swap, because `validate` never writes. It ships with the tree; AEM does not publish `unfiled/`. `validate` reads the tree itself, not the file |
| **Published trees** | Re-synced. The old `unfiled.md` and the orphan files at their old paths are removed from `tibco-docs-aem` and `ibi-docs-aem`. Their `301.yml` points at the new paths | Sync already removes files a version no longer ships |

#### Steps

1. `converter/orphans.py` (new): the reshelve pass over a written version tree. Called from `converter/driver.py` before the swap. Remove the Unfiled node from `engines/flare.py`, `dita.py`, `webworks.py`, `docbook.py`. Bump `_CONVERTER_VERSION`.
2. `cli.py`: `convert --reshelve-orphans` over a selection, for output already written; it stamps the converter version.
3. `reframe/`: topics under `unfiled/` are copied through unmerged; the self-check skips the reachability test for them; links and CSH resolve to them; no redirect targets them.
4. Tests: an orphan moves to `unfiled/` with a link into it and a CSH id rewritten and its `301.yml` row dropped; no Unfiled node in any engine's TOC; a reframed tree copies an orphan unmerged; reshelving twice changes nothing.
5. Run: `convert --reshelve-orphans` over the 244 versions; `reframe --bu tibco`; `sync` to `tibco-docs-aem` and `ibi-docs-aem`; `validate`. Exit for this step: no `REFRAME_SELF_CHECK_FAILED` from orphans, no blank TOC title, no new `LINK_BROKEN`.
6. Docs: `architecture.md` §5.2.3 and the WebWorks and DocBook orphan paragraphs, `user-guide.md`, findings register (`TOC_ORPHAN` text), `CONTEXT.md`.

*Exit: no converted or merged `toc.yml` lists an orphan; every orphan is one page under `unfiled/`, every link and CSH entry to it resolves in the tree, and no redirect targets it; Phase 42 step 8 completes.*

#### As built (2026-10-07)

- `converter/orphans.py` is the pass; `transforms/fragments.repath` is the link rewrite it shares with the fragment pass. `utils/naming.UNFILED` names the folder for `convert`, `reframe` and `origins`.
- Steps 1–4 and 6 done. Step 1 differs from the plan: the engines are unchanged and keep building the Unfiled node, which the pass removes.
- Checked on copies of EMS 10.4.0 (24 orphans) and FOCUS 9.3.4 (99 orphans, two Unfiled nodes): no Unfiled left, `toc.yml` parses, unresolved references unchanged (90 and 0). A second run changes nothing.
- **Inbound links recorded** (the user, 2026-10-07). `orphans.write_inbound` writes `unfiled/inbound-links.csv` at the end of the pass and again in `reframe`'s staging tree; it is removed when no link remains. `validate` reports each link as `LINK_TO_UNFILED`, from the tree, not the file. `fragments.labelled` gives each link's text.
- Step 5 (the runs) is next.
- **Step 5, first run (2026-10-07).** `convert --bu tibco --reshelve-orphans`: 161 reshelved, 114 nothing to move, 1,149 no tree. A read-only check of all 161 (`C:\tmp\reshelve-check\check.py`) passed TOC, links into orphans, CSH, `301.yml` and `inbound-links.csv` in 136; 25 had 98 broken links in moved pages, all one shape (Phase 44).

### Phase 44: A Link Around an Image Is a Link — **Done 2026-10-07**

**Why.** `[![thumb](images/a_thumb.png)](images/a.png)` is a thumbnail that opens the full
picture. The three inline-link patterns (`transforms/fragments.py`, `reframe/pages.py`,
`validation/references.py`) cannot hold a `]` in the link text, so each reads only the inner
image and never sees the outer destination. Whatever moves a page re-paths the thumbnail and
leaves the click-through pointing at nothing, and `validate` never reports it.

**Measured 2026-10-07:**

- Reshelved output: 98 broken click-through links in moved pages, in 25 versions, all
  BusinessWorks plug-ins. Every image is still at its original path.
- Merged tree (`reframed/`): 643 of 788 linked images have a broken click-through, in 34
  versions. These are published pages.

#### Decisions

| decision | choice | why |
|---|---|---|
| **One pattern** | `utils/mdlinks.MD_LINKED_IMAGE` reads the outer destination of a linked image; the three readers use it beside their inline pattern | The three copies drifted together once; one definition keeps them agreeing |
| **Repair written trees** | `reshelve` also re-paths a link in an `unfiled/` page that no longer resolves but resolves from the page's old path. `convert --reshelve-orphans` reports such a version as reshelved, with a new build id | Re-running the pass finds no Unfiled node, so without this the 25 trees stay broken. It needs no source, like the pass itself |
| **Re-merge** | `reframe/policy._ALGORITHM` 6 | The merged trees were written by the faulty pattern; a bump is how a merge-rule change re-merges every version |

#### Steps

1. `MD_LINKED_IMAGE` in `utils/mdlinks.py`; used by `references()`, `fragments._destinations` and `labelled`, and `reframe/pages.py`.
2. `converter/orphans.py`: the repair; `reshelve_one` counts it.
3. `_ALGORITHM` 6.
4. Tests: each reader sees the outer destination; a reshelved and a merged linked image resolve; the repair fixes a tree from the faulty pass and a second run changes nothing.
5. Runs (the user): `convert --bu tibco --reshelve-orphans`; `reframe --bu tibco`. Exit: the check script and the linked-image scan find no broken click-through.

#### As built (2026-10-07)

- Steps 1–4 done. The pattern is in a leaf module, `utils/mdlinks.py`, because `transforms` importing `validation` was circular.
- Tried on copies of Plug-in Development Kit 6.3.1 and SharePoint 6.3.1: the repair fixed exactly the 6 and 8 broken links, changed no other line, and a second run repaired 0. Swift 6.8.0, the worst case: 29 of 29.
- `validate` now checks these links, so the next run may report new `LINK_BROKEN` from trees not yet repaired or re-merged.
- **Step 5, repair run (2026-10-07).** `convert --bu tibco --reshelve-orphans`: 25 reshelved, 98 links repaired, 0 failed. The check passes in all 161 reshelved versions and no broken click-through remains in the converted bw-plugin output. 
- **Step 5, re-merge (2026-10-07).** `reframe --bu tibco`: 214 reframed, 0 failed, no `REFRAME_SELF_CHECK_FAILED`. 0 of 788 linked images broken in `reframed/` (was 643). The moved-pages check passes in 148 of the 150 merged trees; the other 2 (ActiveSpaces plug-in 7.1.1, Twitter 6.1.2) are the check, not the tree: a merged listed page took the name an orphan had, and every link and redirect to it lands on a real heading. Phase 44 exit met; `sync` and `validate` are next.

### Phase 45: A Function Catalog Is an API Reference — **Built and run 2026-10-07; sync pending**

**Why.** BusinessEvents ships its catalog functions (signature, domain, description, one
page per function) as a generated HTML tree, `functions/`, with no Flare markers. The
converter drops each page as `no-content-container` and raises `CONTENT_MISSING` for it:
5,234 warnings in the first BusinessEvents run (run 476), and no function reference in the
output. The user's decision, 2026-10-07: treat it as Javadoc is treated, copied verbatim and
published to the `-resources` repo.

**Measured 2026-10-07** over `html-to-md/cache/pub` (`C:\tmp\an_funccat.py`):

- 16 directories hold `functions.css`. 12 also have an `index.html` that imports
  `functions.css` and opens `<body class="category">`: businessevents-enterprise 6.2.2–6.4.0
  (`functions/` and an identical `html/functions/` in each) and bstudio-decisions-addin 1.3.0
  and 1.4.0 (`Functions/`). The other 4 are 12-file `CORE/Functions` folders inside RTView
  6.9.0–7.1.0 user guides, which are documentation. So `functions.css` alone is not a marker;
  the pair is.
- In the catalog: 6 versions convert (BE Enterprise 6.3.0, 6.3.1, 6.3.2, 6.4.0; Decisions
  add-in 1.3.0, 1.4.0). BE 6.2.2 is retired.

#### Decisions

| decision | choice | why |
|---|---|---|
| **Marker** | A directory holding `functions.css` and an `index.html` whose first 4 KB imports `functions.css` and has `class="category"`. Added to `apiref.has_api_marker` beside the Javadoc and Doxygen markers | Matches the 12 catalogs and none of RTView's folders. A marker decides, a name never does (§6.3) |
| **Both BE copies** | Both become API roots; sync's existing de-duplication publishes one | The two are byte-identical (checked on 6.4.0); sync already drops a root's duplicate |
| **Published name** | From the path, as for every API tree: `functions` (Decisions add-in: `Functions`) | Existing rule in `sync/apirefs.py` |
| **Links into it** | Rewritten to the `-resources` URL during `convert`, as for Javadoc | Existing behaviour once the root is recorded |

#### Steps

1. `apiref.py`: the function-catalog marker.
2. Tests: a catalog fixture is an API root; an RTView-shaped `Functions/` with `functions.css` and no catalog index is not.
3. Runs (the user): `extract --force` then `convert --force` for `tibco-businessevents-enterprise-edition` and `tibco-business-studio-activematrix-decisions-add-in`. The roots are recorded at extract, so a plain re-run would not see them.
4. Docs: `design.md` §6.3.1 Finding 5 marker list, `user-guide.md` API-reference paragraph.

*Exit: no `CONTENT_MISSING` under `functions/` in the six versions; their `_api_files` include the catalog; sync places one `functions` tree per version in `-resources`.*

#### As built (2026-10-07)

- Steps 1, 2 and 4 done. On the extracted trees the marker finds `functions/` and
  `html/functions/` in BE Enterprise 6.4.0 and `Functions/` in Decisions add-in 1.4.0, and
  nothing in the cached RTView 7.1.0.
- **Step 3, runs (2026-10-07).** `extract --force` and `convert --force` for both products:
  6 converted, 0 failed. BE Enterprise warnings 5,252 → 11 (run 476 → 478), no
  `CONTENT_MISSING` left; `api-reference` skips 215 → 1,533 per version (1,491 in 6.3.0),
  and `_api_files` now 3,106 (3,020 in 6.3.0). Topic output unchanged (same resolved counts).
  Decisions add-in 1.4.0: `_api_files` 197. 1.3.0's inventory stays blank from an older
  partial walk (unreadable WebWorks `wwhelp/wwhimpl/common/` folders, not this phase);
  `find_api_roots` still finds its `Functions/`, which later stages locate themselves.
  Exit met except the sync check, which waits for the family syncs.

### Phase 46: Long Paths Are Read, or the Run Stops — **Built 2026-10-07; runs pending**

**Why.** Windows hides any file whose full path is 260 characters or longer unless
long-path support is turned on, and on this machine it is off (`LongPathsEnabled=0`).
`Path.is_file()` and `iterdir()` then report the file as absent rather than failing, so the
tool skips it without a word. Adapter for Files (Business Studio) 1.3.0 converted nothing:
all 209 of its pages sit at 260–277 characters, because the slug appears twice, once in the
workspace folder and once in the package's own wrapper folder. The user's decision,
2026-10-07: turn the setting on, and make the tool refuse to run when it is off.

**Measured 2026-10-07** over `families/*/extracted/` (`scratch/long-path-versions.tsv`):
1,792 files and folders at 260+ characters in **50 versions**: 21 container-editions, 6 each
activematrix, bw-plugin and ems, 4 each businessevents and di-ism, 3 adapters. All 50 have
been processed: 37 `converted`, 12 `merged`, 1 `convert-failed`. They include ActiveMatrix
Service Grid 3.4.3 and 3.4.4 (116 each; likely the cause of their 126
`REFERENCE_UNRESOLVED` each), JD Edwards 6.0.0 and 6.1.0, and both Decisions add-in
versions (their partial walks). Long-path support was confirmed absent by probe: 0 of 209
pages pass `is_file()`.

#### Decisions

| decision | choice | why |
|---|---|---|
| **Read long paths** | Windows long-path support turned on (`HKLM\SYSTEM\CurrentControlSet\Control\FileSystem\LongPathsEnabled=1`, or the Group Policy "Enable Win32 long paths"). No code change to read them | `utils/longpath.long_path` already lifts the limit with the `\\?\` prefix (§4.4), but only where a call site uses it. `engines/roots._is_dita_root` and `apiref` do not, and a missed site fails silently. The setting covers every site at once, including ones not yet found |
| **The guard** | `utils/longpaths.py` (new): a probe that writes and reads back a file at 300+ characters under the workspace's `cache/`, once per run. `extract`, `convert`, `reframe`, `sync` and `validate` stop with exit 2 and the fix in the message when it fails. Always passes off Windows | A probe tests what the running Python can actually do, which a registry read does not. A stop rather than a warning, because the failure is silent data loss |
| **Re-run** | The 50 versions tagged `convert_batch=p46`, then extracted and converted with `--force`, reframed and re-synced | Their inventories, conversions and merges were all made from a partial view |

#### Steps

1. `utils/longpaths.py` and the guard in the five commands.
2. Tests: the probe passes on a filesystem that keeps long paths; each guarded command exits 2 with the message when the probe fails; `download` and `catalog` are not guarded.
3. The user turns the setting on (admin). Check: the probe passes, and Files 1.3.0's 209 pages pass `is_file()`.
4. Runs (the user): tag the 50 versions `p46`; `extract --force --batch p46`; `convert --force --batch p46`; `reframe --batch p46`; then each family's `sync` and `validate`.
5. Docs: `user-guide.md` §1 installation (the setting is a prerequisite on Windows), `architecture.md` where the workspace layout is described.

*Exit: no file at 260+ characters is missing from `_doc_files`; Files 1.3.0 converts; Service Grid 3.4.3/3.4.4's `REFERENCE_UNRESOLVED` re-measured; no partial walk among the 50.*

#### As built (2026-10-07)

- Steps 1, 2 and 5 done. `utils/longpath.long_paths_enabled` is the probe; `cli._require_long_paths` raises exit 2 with `LONG_PATHS_OFF`. `validate --dry-run` is not probed, because it opens no file. `doctor` prints `long paths: on/off`.
- An existing test (`test_the_walk_finds_a_file_that_rglob_silently_drops`) asserted that a plain walk misses a long file; it now asserts that only when the probe fails.
- Step 3 done: the user turned the setting on. A new process sees all 209 of Files 1.3.0's pages, `find_output_roots` finds its `html/`, and the probe passes.
- **Step 4, re-run (2026-10-07, `scratch/p46-rerun.sh`, named versions rather than a `p46`
  tag because 6 of the 50 carry `bwp-dita`).** 50 converted, 12 re-merged, 0 failed, no partial
  walk, no reframe error. Files 1.3.0: `convert-failed` → `converted`, 206 pages. Service Grid
  3.4.3/3.4.4 and Decisions add-in 1.3.0 now have their inventory. 31 versions (container
  editions, iWay, EMS 10.4–10.5) have no package left, so `extract --force` skipped them; their
  trees were complete (unpacking already used the prefix) and convert read them in full, but
  their inventory columns are from the old walk.
- The 21 container-edition and 4 iWay versions show one page fewer: the generated `unfiled.md`,
  gone because a forced convert applies Phase 43, which had only run for TIBCO. No content lost
  (checked against `ibi-docs-aem` for WFCE 9.3.8 and iWay EDI 9.3.0).
- **Service Grid's 126 `REFERENCE_UNRESOLVED` each are unchanged**, so long paths were not
  their cause; still open. JD Edwards 6.0.0/6.1.0 keep their 1 each.
- `extract --measure-only` for the 31 changed nothing: it fills blank columns only, every one
  was `already measured`, and `--force` is refused beside it. What the old walk missed in them:
  389 files (216 png, 70 jpg, 103 htm/html), no CSH source and no API marker. The topics did
  convert (checked: WFCE 1.3.0's two long-named topics are in `output/`), since the engines
  walk through the prefix. So only `_doc_files`/`_total_files` are low, by 389 across 31 rows.
- Left: sync and validate for the affected families.

### Phase 47: Service Grid Merges — One Topic in Two Guides, Deep Pages, Page-as-Folder Links — **Done 2026-10-08**

**Why.** Three ActiveMatrix merges failed `REFRAME_SELF_CHECK_FAILED` on 2026-10-07, and
Service Grid 3.4.3/3.4.4 each lose 126 pictures at conversion (`docs/open-issues.md`).
Reproduced in a private root (`C:\tmp\sgroot`, staging kept) on 2026-10-07. Four causes:

1. **Per-guide copies fail the audit.** Since Phase 29 `pack` gives a topic listed under two
   guides one copy per guide (`claimed` is per root). `assign` keeps only the first copy in
   `located` (the per-node copies are in `placements`), and `audit._anchors` and
   `_navigation` still read `located`: the second copy counts as an extra anchor and its
   page as unreachable. Hits 3.4.4 ("1856 topics located, 1866 anchored") and CE 1.0.1
   (`cloud-deployment-guide/activematrix-service-grid-container-edition-2.md`).
2. **`project` does not make the copies.** A version laid out from a pin dedupes across the
   whole version (`claimed` over all roots), so the Phase 29 rule holds only in the
   reference version. CE 1.0.0 passes for that reason, with the topic placed once.
3. **Heading levels on a TOC deeper than six.** `_relevel` runs `compact` on raw TOC depths,
   and `compact` caps at H6 before `_relevel` rebases. With a shallowest depth of 7 the first
   topic gets level 0, so it renders as a plain line and the next one comes out at the wrong level.
   3.4.3's "difference -2" is two such pages. Pinned versions only.
4. **Page-as-folder references in the source.** The Composite Development Guide writes
   `setting-the-value-of.htm/ellipsis.png` and `tibco-business-studi5.htm/tibco-business-studi3.htm`:
   126 pictures (`REFERENCE_UNRESOLVED`) and 166 links (`TOPIC_LINK_DANGLING`) per version.

**Measured 2026-10-07/08:**

- Cause 4: across every unpacked version, 584 references of this shape, all in Service Grid
  3.4.3 and 3.4.4 (292 each). Dropping the `*.htm` segment resolves all 292 in each.
- Cause 2: 3 of the 352 merged versions have a topic under two guides (SmartMapper 7.1.2,
  IBM MQ 8.7.0, CE 1.0.0, one topic each); these change when `project` makes copies.
- Cause 3: no merged tree is affected; the audit fails every such page, as it did for 3.4.3.

#### Decisions

| decision | choice | why |
|---|---|---|
| **Audit** | `_anchors` and `_navigation` count placements per TOC node (`placements`), not per source topic: every anchor belongs to one placement, every placed page is reachable from its own node. `located` stays first-copy for redirects and CSH | The copies are intended (Phase 29); the check has to expect them |
| **`project`** | Dedupes per guide, like `pack`; a pin group is keyed by guide and source, so each guide's copy follows its own reference page | One rule for both paths. Changes 3 merged versions |
| **`_relevel`** | Rebase depths to 1 before `compact` | The cap must apply to page levels, not to raw TOC depth |
| **Page-as-folder references** | In `transforms/assets.resolve` and the Flare topic-link resolver: when a reference does not resolve and a path segment ending `.htm`/`.html` names an existing file, retry without that segment, and count it (`page_segment_dropped`) as a note | The pictures and pages exist; only the address is wrong. Measured to touch only these two versions |
| **Re-running** | No `_ALGORITHM` or `_CONVERTER_VERSION` bump. The affected versions are re-run with `--force`: convert 3.4.3, 3.4.4; reframe 3.4.3, 3.4.4, CE 1.0.0, CE 1.0.1, SmartMapper 7.1.2, IBM MQ 8.7.0 | A bump re-merges or re-converts every version for output that changes in 8. Departs from the Phase 44 practice, so it is stated here |

#### Steps

1. `reframe/audit.py`: anchors and reachability from `placements`; the driver passes them.
2. `reframe/packer.project`: per-guide dedupe, pin groups keyed by guide.
3. `reframe/packer._relevel`: rebase before `compact`.
4. `transforms/assets.py` and `engines/flare.py`: the page-segment retry and its note.
5. Tests: a topic under two guides passes the audit in `pack` and in `project`, with one copy per guide; a page whose topics sit at depth 7+ gets H1 then H2; `a.htm/img.png` resolves to `img.png` beside `a.htm`, and a reference with no such file stays dangling.
6. Runs (the user): `convert --force` for Service Grid 3.4.3 and 3.4.4; `reframe --force` for the six versions above.
7. Docs: `architecture.md` (audit, projection), `docs/open-issues.md` (close both entries).

*Exit: the three versions merge with no `REFRAME_SELF_CHECK_FAILED`; 3.4.3/3.4.4 report 0 `REFERENCE_UNRESOLVED` from the Composite Development Guide; the three re-merged versions pass and each has one copy per guide.*

#### As built (2026-10-08)

- Steps 1–5 done. `audit._anchors` compares anchored and located *sources* as sets;
  `_navigation` reaches each row's own copy through `placements`. `project` keys pin groups
  by (guide, source), with a path-only fallback for a source on exactly one reference page
  so a guide retitled between versions keeps its pins, and never places one topic twice on
  a page. `_Reference` gained the guide. `_relevel` reads depths by row (`Topic.node`, now
  set by `project`) and rebases before `compact`.
- **Found while verifying: `relocate` filed the second copy in the first guide's folder.**
  Its owner map was keyed by source, so the last copy owned both rows. Now keyed by row
  first. CE's Quick Start copy moves from `cloud-deployment-guide/…-2.md` to
  `quick-start/introduction/containerizing-activematrix-service-grid/…`.
- **Known limit:** `rename-map.csv` and the copy `state.db` keeps are keyed by source topic,
  so a kept name cannot tell two copies apart; a pin recorded for a copy's source applies
  to whichever copy leads a page. Seen only in the private test root, where an earlier run
  had pinned the old path; neither CE version has such a pin in the workspace.
- Step 4 as built: the retry keeps the shortened path only if it resolves; it does not
  separately check that the dropped segment names a file. New code `REFERENCE_PAGE_SEGMENT_DROPPED`
  (note); the register is 87.
- Verified in `C:\tmp\sgroot` (renormalized for CE): all four Service Grid versions merge
  with no self-check failure; 3.4.3's deep page opens `#` then `##`; converting 3.4.4 gives
  0 `REFERENCE_UNRESOLVED` (was 126), `TOPIC_LINK_DANGLING` 1 (was 167), 292
  `REFERENCE_PAGE_SEGMENT_DROPPED`; the re-merge from that conversion passes.
- `architecture.md` has no section on the audit or the pin, so step 7 is this entry and
  `open-issues.md`.
- **Step 6, first run (2026-10-08).** Converts: 3.4.3 and 3.4.4, 0 `REFERENCE_UNRESOLVED`,
  `TOPIC_LINK_DANGLING` 1 each, 292 `REFERENCE_PAGE_SEGMENT_DROPPED` each. Re-merges: all six
  passed, and CE 1.0.0/1.0.1 file the Quick Start copy under `quick-start/`. **But IBM MQ
  8.7.0 regressed:** its reference (8.8.2) lists the shared topic in the first guide only, so
  the path-only fallback put the *second* guide's copy on a first-guide page
  (`setting-up-log-levels.md`). The audit passed it: no check compared a topic's guide with
  its page's.
- **Fixed (2026-10-08).** The fallback applies only to a topic's first appearance in the
  version; a later guide's copy matches its own guide or is packed as new in that guide. A
  run of new topics is flushed at a guide change. New audit check `_guides` ("guide
  integrity"): every row-placed topic sits on a page of its own row's guide. Re-checked in
  the private root: IBM MQ 8.7.0 has one copy in each of its two guides, SmartMapper 7.1.2
  one in each of three. 2,201 tests pass. The six re-merges are to be run again.
- **Step 6, re-run (2026-10-08).** All six re-merged with no `REFRAME_SELF_CHECK_FAILED`.
  Every copy sits on a page of its own guide: Service Grid 3.4.3/3.4.4 10 topics each (Java and
  Spring guides), CE 1.0.0/1.0.1 one (Cloud Deployment, Quick Start), SmartMapper 7.1.2 one
  in three guides, IBM MQ 8.7.0 one in two. `RENAME_MAP_UNMATCHED` in SmartMapper (4 rows)
  and IBM MQ (2): those topics no longer lead a page under the per-guide layout; neither
  merge had been published. Exit met; both `open-issues.md` entries closed.

### Phase 48: Flogo Connectors Retire; the VS Code Extension Joins Flogo — **Done 2026-10-08**

**Why.** A business change on 2026-10-08: the Flogo Extension for Visual Studio Code
(`flogo-vscode`) moves to the Flogo family, and only its latest version gets converted. The
other 64 Flogo Connectors products are retired, so none of them get converted.

**Measured 2026-10-08:** `flogo-connectors` holds 65 products, assigned by `taxonomy_rule`.
The 64 that are not `flogo-vscode` have 153 versions: 103 merged, 6 `pdf-ready`, 5
`download-failed`, 39 not eligible. `flogo-vscode` has 11 eligible versions (1.0.0–1.3.5),
all merged. All of this work sits under `en-us-tib-flogo-connectors` in `families/`,
`output/` and `reframed/`. No `en-us-tib-flogo` workspace exists yet. This phase needs no
code change.

#### Decisions

| decision | choice | why |
|---|---|---|
| **Retire the 64** | Add one `scope.yaml` `out_of_scope` entry per slug, with the reason "Flogo connectors retired (2026-10-08)" | One reviewable file. It also excludes versions a later fetch discovers, which a per-version `release_status=retired` would miss (user, 2026-10-08) |
| **Move `flogo-vscode`** | `catalog set --family flogo`, which pins `family_source=manual` | `flogo` is already declared in `taxonomy.yaml`, so no new family and no new `repo_slug` |
| **Only 1.3.5** | `catalog enable --disable` for 1.0.0–1.3.4; 1.3.5 stays eligible | A one-off choice for this product, not a "latest only" rule (user, 2026-10-08). The disable survives a fetch through the snapshot (`set_conversion_eligibility`), not through a pin |
| **Existing connector work** | After the `flogo-vscode` 1.3.5 work has moved, delete `en-us-tib-flogo-connectors` from `families/`, `output/` and `reframed/` | The user's call (2026-10-08). The catalog rows stay, as for every out-of-scope product |
| **`flogo-vscode` 1.0.0–1.3.4 work** | Delete with the rest; do not move it | Not eligible any more, so nothing would read it |
| **`flogo-connectors` in `taxonomy.yaml`** | Keep the family | Its 64 products are still in the catalog and still belong to it; only the work stops |

#### Steps

1. `config/scope.yaml`: 64 entries (slug, display name, reason), and update the header count
   (62 → 126).
2. `catalog set --product flogo-vscode --family flogo`; `catalog enable --disable` for the
   ten older versions; then `catalog import` so `in_scope` and the `_family` columns update.
3. Move `flogo-vscode` 1.3.5 (the ZIP, the extracted tree, the converted output and the
   reframed output) from `en-us-tib-flogo-connectors` to `en-us-tib-flogo`. Read the paths
   from the stage layouts before moving anything.
4. Check, read-only: `catalog show --product flogo-vscode`, `catalog list --eligible-only
   --family flogo-connectors` (expect empty), and that `reframe` / `sync` dry runs find
   1.3.5 under the new workspace without re-converting it.
5. Delete the three `en-us-tib-flogo-connectors` folders (the user, as `!` commands).
6. Docs: `CONTEXT.md` (the scope count), `docs/open-issues.md` (close any Flogo connector
   items), `docs/jira.md` if this is logged.

*Exit: no `flogo-connectors` version is eligible; `flogo-vscode` sits in `flogo` with 1.3.5 as
its only eligible version, and its output resolves in `en-us-tib-flogo`; the old connector
workspace is gone.*

#### As built (2026-10-08)

- Steps 1–4 done. `catalog import` does not read `scope.yaml`; only the fetch merge does, so
  step 2 also ran `catalog fetch --family flogo-connectors`: 64 products to
  `in_scope=false (scope_rule)`, 0 added, 0 removed. The `versions.csv` changes are only
  `_status` (163), `_status_date`, `_family` (11) and `convert_eligible` (10).
- Moved 1.3.5 in all four stages. `state.db` keeps the old download and extract paths for
  information only (stages compute paths from the family), and they were rewritten for the
  one row; a backup is at `C:\tmp\state-before-p48.db`.
- Dry runs: `convert` and `reframe` resolve 1.3.5 under `en-us-tib-flogo`, with both trees
  present. `sync` would place it, merged, in `en-us-tib-flogo-userdocs`. No connector
  version had been synced, so no target repo holds connector pages.
- `docs/open-issues.md` has no Flogo entries. Step 5 done by the user (2026-10-08); only
  `en-us-tib-flogo` remains, holding 1.3.5.

---

### Phase 49: An Image Too Long to Publish Gets a Shorter Name — **Built 2026-10-09; runs pending**

**Why.** The BusinessConnect run (2026-10-09) could not publish 11 merged versions: their
paths would pass Windows' 260-character limit under `C:\github\tibco-docs-aem`
(`PUBLISHED_PATH_TOO_LONG`). 39 of the 42 files are pages, and `rename-map.csv` already lets
a person give a page a shorter address. The other 3 are one image,
`GatewayConfiguration/Images/Figure_1_Features_of_TIBCO_BusinessConnect_EDI_Protocol_powered_by_Instream.jpg`
(264 characters published), in EDI Protocol Container Edition 1.5.0, 1.6.0 and 1.6.1. Nothing
can rename an image: `transforms/assets.py` keeps every asset's source path, "never
flattened, never renamed". So those three versions cannot publish at all.

**Measured 2026-10-09**, every non-page file in `output/` and `reframed/`, at its published
length under `C:\github\tibco-docs-aem`: this image is the only one over 260, in 3 versions.
732 in-scope versions are not converted yet, so it will not be the last.

#### Decisions

| decision | choice | why |
|---|---|---|
| **Where** | `convert`, in the asset resolution that writes both the copy and the link | One resolution, two outputs (invariant 13). Renaming at `sync` would mean rewriting Markdown there, and `sync` copies verbatim |
| **When** | Only when the asset's published path would pass the limit; every other asset keeps its source path | The rule stays "never renamed" for all but the files that cannot be published otherwise |
| **How long** | Measure against the layout from `publishing.yaml` plus a root allowance, a new `publishing.yaml` key set to the length of the root the published repos live under | `convert` does not know `sync`'s `--target-dir`; `sync` still checks the real length and still refuses |
| **New name** | Same folder and extension; the name cut to fit, then `-` and the first 8 hex characters of the SHA-256 of the source path | Deterministic, so a re-run produces identical output, and two cut names cannot collide |
| **Reported** | A new note, `ASSET_RENAMED_FOR_LENGTH`, naming the source path and the new one | A renamed file should be findable |
| **Reframe** | No change: it copies the converted tree's assets and links as they are | The new name is already in the converted page |

#### Steps

1. `publishing.yaml`: the root-allowance key, documented in place.
2. `transforms/assets.py`: compute the published length; shorten the target when it is over;
   record the note. Register the code in `reporting/findings.py` and §7.5.
3. Tests: an over-long asset is renamed and its link follows; an asset under the limit is
   untouched; the same input gives the same name twice; two long names that cut to the same
   text still get different names.
4. Docs: the asset rule in `design.md` §6.4 and `architecture.md` §5.5; the `sync` note in
   `user-guide.md` (line ~1356) says the tool now shortens images on its own.
5. Re-run (the user, as `!` commands) `convert`, `reframe`, `sync` for the three EDI versions;
   then check, read-only, that they publish and `validate` is clean.

*Exit: the three EDI Container Edition versions publish; no other asset in the corpus changes
name; `ruff` and the test suite pass.*

#### As built (2026-10-09)

- Steps 1–4 done. The key is `published_root_length: 24`; 0 or a value that is not a whole
  number turns the shortening off, and `catalog validate` names a bad value.
- One rule added while testing: when the file name is too short to cut (the folder alone is
  over), the tagged name would be *longer*, so the source name is kept and `sync` still names
  the file when it refuses the version.
- The register is 89 codes. Three guard tests on the shipped catalog were re-baselined in the
  same change, for the 2026-10-08 and 2026-10-09 catalog edits, not for this phase: scope
  62 → 129 rules, the EOS report 528 → 535 names, retired-and-eligible 123 → 115.
- Step 5 waits for the user's run.

---

### Phase 50: A Topic That Leads Two Pages Can Be Named Per Page — **Built 2026-10-09; runs pending**

**Why.** The BusinessConnect re-run (2026-10-09) left ebXML Protocol Container Edition 1.2.1
and 1.3.0 unpublished. Their page for "Creating a Process Invoker" (265 characters) was given
a shorter name in `rename-map.csv`, and the merge dropped it without a warning. Since Phase 47
one source topic can lead a page in two guides. `rename-map.csv` has one row per page, but
`renames.load` keys the names by source topic alone, so the second row overwrites the first.
`toc_breadcrumb` is keyed the same way, so both rows also show the first guide's breadcrumb.

**Measured 2026-10-09** over every `rename-map.csv` in `reframed/`: 5 versions have a source
topic that leads more than one page, 30 rows in all.

#### Decisions

| decision | choice | why |
|---|---|---|
| **Key** | A topic that leads one page stays keyed by `old_path`. A topic that leads several is keyed by `old_path` plus the page's computed name, written to a new `page_key` column | The computed name comes from the converted tree alone, so it is stable across runs; existing maps keep working unchanged |
| **Ambiguous rows** | A row for a shared topic with no `page_key` (every map written before this phase) pins nothing and warns `RENAME_MAP_AMBIGUOUS`, naming the rows | Guessing which page a name meant could move the wrong page's URL |
| **Breadcrumb** | Written per page, from that page's own place in the TOC | Two rows showing the same breadcrumb hide which page is which |

#### Steps

1. `reframe/renames.py`: write `page_key` for shared topics; `load` returns per-page keys;
   breadcrumbs per page. `packer.override` and the driver's refused / unmatched checks use the
   new key.
2. Register `RENAME_MAP_AMBIGUOUS` in `reporting/findings.py` and §7.5.
3. Tests: two pages led by one topic take two different pinned names; an old map without
   `page_key` warns and pins neither; a topic leading one page behaves exactly as today.
4. Docs: `rename-map.csv` in `user-guide.md` (line ~1065) and `design.md`.
5. Re-run `reframe` (the user) for the 5 versions; write the BusinessConnect name into the new
   row; then `reframe` and `sync` for ebXML 1.2.1 and 1.3.0; check read-only.

*Exit: ebXML Container Edition 1.2.1 and 1.3.0 publish; the other 3 versions merge to
identical trees; `ruff` and the test suite pass.*

#### As built (2026-10-09)

- Steps 1–4 done. `page_key` is the last column, so a sheet saved before it reads unchanged.
  A topic that leads one page keeps its plain key, so every existing map, its digest and the
  copy in `state.db` are unchanged, and no version re-merges because of this phase.
- `design.md` has no `rename-map.csv` section; the rule is documented in `user-guide.md` only.
- Step 5: `page_key` was written by hand into the two shared rows of the ebXML 1.2.1 and 1.3.0
  maps (each row's current path, which is the computed one, since neither pin took effect),
  and `process-invoker.md` onto the ebMS2 row, so one `reframe` applies it. The other 3
  versions with a shared topic keep their maps; they warn `RENAME_MAP_AMBIGUOUS` once on their
  next re-merge, and their pages keep the computed names they already have.

---

### Phase 51: A Merged Help System's Guides Are in Its Subsystems' TOCs — **Built 2026-10-13; runs pending**

**Why.** The Foresight run (2026-10-13, DOCOPS-228) held back Instream 9.2–9.4 and
Transaction Insight 5.4–6.0, on a reading of the *reframed* trees: 89–98% and 50–78% of their
pages in `unfiled/`. That overstated it. Merging packs listed topics into few pages and leaves
each orphan as its own page. **Corrected, measured on the converted trees:** Instream 9.4.0's
navigation had 778 entries, 394 of them from the subsystems' copies, which are the older 9.3.0
build. They were appended at the end as 14 sections all titled "TIBCO Foresight® Instream®",
while the master's current pages sat in `unfiled/`. Transaction Insight lost nothing: 821
entries, 26% unfiled, and its subsystems are separate guides.

**Cause, read 2026-10-13.** These are Flare runtime-merged outputs. The master's
`Data/HelpSystem.xml` lists its subsystems in `<Subsystems><Url Source=…mcwebhelp TocPath="">`,
and its TOC places each one as a node `{i:15,r:1,m:0}`, where `m` indexes that list. The chunk
file maps those ids to a `.flprj` key (`/../../../../foresight_shared/foresight_shared.flprj`).
`flare_toc._node` reads only `i` and `n`. `_project()` turns the key into a sub-project, and
`flare.py:948-951` drops the node with `TOC_SUBPROJECT_UNPLACED`; placing it was never
attempted. Each subsystem's own TOC lists only its own guide (EDIWrap: 3 entries of 474 `.htm`),
so the master's guide topics are reached by no TOC and become orphans (`flare.py:896-907`).
Each subsystem is also converted as its own root. In Instream 9.4.0 each one carries a full
copy of the guides from an older build: it says 9.3.0, and the master says 9.4.0.

**Measured 2026-10-13** over the html-to-md cache (`cache/pub`, every docsite package): 31 roots
place a subsystem through a `.flprj` node, in two shapes.

| shape | versions | today |
|---|---|---|
| **Shared library**: the subsystem TOC lists a few of its pages; the guides live in the master (Instream: 3–228 of 467 listed, 362 also in the master) | Instream 9.3.0, 9.4.0 | 90% of topics unfiled; half the navigation from the stale copies; held |
| **Self-contained**: the subsystem TOC lists nearly all its own pages, none shared (Control Plane 1.17.0: 25–63 of 29–70 listed, 0 shared) | Transaction Insight 5.5.0, 6.0.0 (held); ibi FOCUS 9.3.4–9.3.8 (published); Control Plane 1.3.0–1.17.0, TIBCO Platform 1.1.0, Platform CLI 1.2.0, iProcess Engine 11.9.0–11.10.0 (all not started) | Every page converts, as the subsystem's own unit; only its place in the master's navigation is lost |

No version published before this run lost pages to this cause. **Instream 9.2.0 and Transaction
Insight 5.4.0 are not merged.** Their unfiled guides (analyzer-user-guide, SE-user-guide, …) are
named by no TOC at all, so this phase does not change them; see step 6.

#### Decisions

| decision | choice | why |
|---|---|---|
| **Placing a merge node** | Resolve `m` to `<Subsystems>[m]`, read that root's TOC, and splice its tree in at the node | That is what the Flare runtime does when a reader opens the help |
| **Which copy a spliced entry points at** | The master's own file at the same relative path; the subsystem's file only where the master has none | The master copy is the current build; the Instream subsystems carry a stale one. Transaction Insight's `fsp_archive` and `fsp_opmon` are mostly separate guides with no master copy |
| **A subsystem listed in `<Subsystems>`** | Not converted as its own unit. Its files feed the master, as above | Converting it publishes each guide up to 14 more times, from an older build |
| **A merge node that cannot be resolved** (no `m`, index out of range, root missing) | Keep today's behaviour: drop the node and report `TOC_SUBPROJECT_UNPLACED` | No guessing; the finding already names it |
| **Links into `Subsystems/X/…`** | Rewritten to the master path when the master copy is the one converted | Otherwise a link points at a page that is no longer published |

#### Steps

1. `engines/flare_toc.py`: keep `m` on `TocNode`; `read_manifest` reads `<Subsystems>` (Source
   and TocPath).
2. `engines/flare.py`: in `_plan` / `_tocs`, splice each resolved subsystem TOC at its node, with
   paths re-rooted to the master; file entries against the master's documents first. Skip
   subsystem roots listed in the manifest from both conversion and the parent's exclusion.
   Rewrite cross-root links.
3. Tests: a fixture with a master and two subsystems, `m:` nodes and a `.flprj` key. The spliced
   guides are in the nav. A topic with a master copy comes from the master; one without comes
   from the subsystem. No subsystem converts on its own. An out-of-range `m` still reports
   `TOC_SUBPROJECT_UNPLACED`. Update `test_flare.py:1476-1492` to match.
4. Regression: re-convert ibi FOCUS 9.3.4–9.3.8 to a scratch folder and diff against
   `output/`. Expect the same pages, with the HTML5 Charts guide moved to its place in the
   navigation. Convert Control Plane 1.17.0 from the cache the same way and check that each
   capability guide sits where the master places it.
5. Docs: the merged-help rule in `user-guide.md` (Flare section, near the `unfiled/` paragraph)
   and `design.md`; register nothing new unless step 2 needs a finding.
6. Instream 9.2.0 and Transaction Insight 5.4.0: check whether any landing page or the docsite
   links the untocced guides. Record the call in `docs/open-issues.md`: publish without them,
   or treat them as a separate fix.
7. Runs (the user): `convert --force`, `reframe` and `sync` for Instream 9.3.0 and 9.4.0 and
   Transaction Insight 5.5.0 and 6.0.0; then `validate`, checked read-only.

*Exit: every TOC entry of the four versions resolves to the master's current page, each guide
once; ibi FOCUS 9.3.4–9.3.8 keep every page and URL; `ruff` and the test suite pass; DOCOPS
gets a new sub-task linking DOCOPS-228. (Was "under 15% unfiled", which assumed the unfiled
pages were Instream's own. About 900 are other products' guides its TOC never lists.)*

#### As built (2026-10-13)

- Steps 1–6 done. `TocNode.merge` and `Manifest.subsystems` in `flare_toc.py`. In `flare.py`,
  `_merged_subsystems` finds each subsystem a master's TOC places, `units()` drops it, and
  `_spliced` / `_rerooted` splice its TOC in. A new `naming_roots` hook (`base.py`, used by
  the driver) keeps subtree names computed over all roots, so no URL moves.
- Two rules found on real trees that the plan did not have. **Grouping:** a merge node that
  is the only child of a labelled entry is replaced by the subsystem's entries (Instream).
  One with siblings keeps several entries under its own label (ibi FOCUS HTML5 Charts:
  18 entries). **Repeated unlisted pages:** an unlisted subsystem page an earlier subsystem
  already holds is skipped. Instream's 13 subsystems repeat 87 stale pages each.
- Trials in a scratch workspace (`--root`, so nothing reached `cache/state.db`; plain
  `convert --input` records against the catalog row and is not safe for this):
  - Instream 9.4.0: 8,094 to 1,748 topics, 764 entries, 1 dropped node.
  - Instream 9.3.0: 8,381 to 1,845 topics.
  - Transaction Insight 6.0.0: 1,117 to 1,093 topics.
  - Transaction Insight 5.5.0: 1,315 to 1,200 topics.
  - ibi FOCUS 9.3.8: every URL kept except 4 function pages (HEXTR, HMASK, MIRR, XIRR),
    whose subsystem copy is dropped for the master's. The 2 legacy `unfiled.md` pages are
    also gone, and HTML5 Charts sits in place.
  - Control Plane 1.17.0 (from the cache): the capability guides sit under "Managing
    Capabilities".
- Step 6: Instream 9.2.0's unlisted pages are the same other-product guides; publish. In
  Transaction Insight 5.4.0 the release notes (also a PDF) and a 43-page hotfix addendum are
  in no TOC and linked from nowhere; publish, with the addendum recorded in `open-issues.md`.
- Full suite: 2,219 passed. One failure is not from this phase:
  `test_the_shipped_report_retires_the_measured_set` expects 115 retired, and the catalog now
  gives 112 after the 2026-10-12 ineligibility commits. It fails at HEAD too, and needs a
  re-baseline.
- **Flare's `_1` rename** (added after the first real re-run, 2026-10-13). Instream 9.4.0's
  Business Rules guide still came from the subsystem: the master writes 68 of those pages as
  `<stem>_1.htm`, and the subsystem's TOC names `<stem>.htm`. 64 of the pairs differ in text.
  A subsystem page's master copy is now the same path or its `_1` rename. That is used for
  the TOC entry, the copy skip and the link alias. With it, 11 of 764 entries still point
  into a subsystem. About 9 of those have no master equivalent. 2 have master copies under
  `_2` / `_3` and are deliberately not matched, because a higher number can be a different
  topic with the same name. ibi FOCUS 9.3.8 and Control Plane 1.17.0 are unchanged by it.
- Step 7, and re-converting ibi FOCUS 9.3.4–9.3.8 under this rule, are the user's runs.

---

### Phase 52: Letter Case the Source Gets Wrong — **Done 2026-10-14**

**Why.** Two failures from the 2026-10-14 run of the Flogo, BusinessWorks, Fulfillment and
MFT families, both about names that differ only in letter case:

1. **Product and Service Catalog 5.1.0 publishes 399 broken images.** Its topics link
   `html-opd/...` and the folder is `html-OPD/`. Windows resolves it, and AEM, on Linux,
   will 404. `validate` reports each one as an error. `design.md` §6.4 step 6 chose to
   check and not correct case, because the corpus held 14 such references. One version
   now holds 399.
2. **MFT Platform Server for z/Linux 8.1.0 is refused at extract.** The ZIP holds
   `SourceSansPro-Regular.otf` and `sourcesanspro-regular.otf` in one folder, which
   Windows writes to one file. Extract refuses any such package, by design, so nothing
   is guessed.

#### Decisions

| decision | choice | why |
|---|---|---|
| **An asset reference spelled in the wrong case** | Emit the file's on-disk spelling, as page links already do (R5-06), and copy the file under that spelling. Still counted, now as corrected | The page-link rule is the same problem, already solved. Uncorrected, the link breaks on publish |
| **Two ZIP members that differ only in case** | Extract keeps one when the two are byte-identical, or when both sit under a skin path (`Resources/Stylesheets`, `Skins`, …) that is never published. Any other pair still refuses the package | Neither case loses content. Anything else is a real choice between two files, and stays a human's |
| **Reporting** | A new note for each tolerated pair, naming both members and which was kept | Nothing silent |

#### Steps

1. `transforms/assets.py`: on a case mismatch, emit and copy under the on-disk spelling
   from `_case_differs`' listing walk; keep the count. Update `design.md` §6.4 step 6.
2. `extractor/`: on a case-only clash, compare the two members (CRC and size from the ZIP
   directory); keep the first if identical or both skin, record the note, and otherwise
   refuse as today.
3. Tests for each rule, including the refusal that remains.
4. Runs (handed over 2026-10-14): `extract --force` for z/Linux 8.1.0, then convert,
   reframe and sync it; `convert --force`, reframe and sync for Product and Service
   Catalog 5.1.0. Then `validate`.

*Exit: PSC 5.1.0 validates with no image errors; z/Linux 8.1.0 publishes; `ruff` and the
suite pass.*

#### As built (2026-10-14)

- **Extract** (`safe_unzip.py`, `unpacker.py`): a case-only pair with the same CRC-32 and
  size writes once and records `ZIP_CASE_DUPLICATE_SKIPPED`. The skin half of the decision
  was not built. The one package needing the rule has identical members, and letting
  through two *different* files because of where they sit would choose content for a human.
- **Convert** (`transforms/assets.py`): `_on_disk` returns the filesystem's spelling, and
  the link and the copy use it.
- **A second cause, found on the run.** After convert was fixed, the reframed pages still
  read `html-opd/`. Reframe lower-cases every asset folder (`asset_destination`, the
  ActiveSpaces fix), and a carried legal page had already created `html-OPD/` in the
  staging tree, so on Windows the copy landed there. `page_folders` now maps each page
  folder case-folded to its spelling, and `asset_destination` takes that spelling when an
  asset's folder matches one. Both callers, the copier and `pages.rewrite_links`, get the
  same map.
- Runs: z/Linux 8.1.0 extracted (1 duplicate skipped), converted, reframed and published;
  0 validate errors. PSC 5.1.0 re-converted and re-merged (`--force`); validate went from
  399 errors to 0.
- Suite: 2,223 passed; the one failure is the catalog re-baseline noted under Phase 51.

---

### Phase 53: What the TIBCO-Wide Sync Could Not Publish — **Planned 2026-10-14**

**Why.** The first `reframe --bu tibco` and `sync --bu tibco` (2026-10-14, logs
`scratch/tibco-reframe.log`, `scratch/tibco-sync.log`) held back 7 versions for two
reasons:

1. **Messaging Manager 3.1.1 and 4.0.0 fail the merge self-check.** The user guide's
   msgmx command summary has three topics titled `!`, `/` and `#`. A heading that is
   only punctuation slugs to nothing (`utils/anchors.anchor_run` returns `""`), all three
   land on `users-guide/getting-started.md`, and `_anchors` fails the page for repeating
   `""`. The check is right: AEM derives an anchor from the heading text, so no link can
   reach a section headed `!`.
2. **5 versions publish paths over 260 characters** under `C:\github\tibco-docs-aem`
   (`PUBLISHED_PATH_TOO_LONG`). `sync` names the first file per version; all of them,
   measured 2026-10-14 against each merged tree:

   | version | over 260 | longest |
   |---|---|---|
   | Service Grid 3.4.3, 3.4.4 | 11 pages each | 364, under `running-enterprise-deployment-health-check-using-2/` |
   | Service Grid 3.4.3, 3.4.4, API reference | 1 tree each | 276, `AttributedURI.html` |
   | BusinessEvents Enterprise 6.3.2 | 6 pages | 307 |
   | BusinessEvents Enterprise 6.4.0 | 4 pages | 307 |
   | Runtime Agent 5.13.0 | 3 pages | 280 |

   TRA 5.13.0 still has the copy an earlier sync published, so it serves stale help until
   it publishes again.

Service Grid's API reference is four javadoc trees under
`html/Mediation-Java-API-Reference/mediation_api/javadoc/` (plus the Admin web service
tree). Each tree is named by its whole path, so one is
`mediation-java-api-reference-mediation_api-javadoc-com.tibco.amf.platform.runtime.extension`,
91 characters before the javadoc's own package folders start.

Not in this phase: 7 BW plug-in versions (AWS Common Services 6.0.0–6.1.0, Files 8.3.0,
Oracle E-Business Suite 6.1.2, Oracle Fusion Cloud 6.0.0) are `convert-failed`, "nothing
converted (0 units)", and are counted in DOCOPS-122.

#### Decisions

| decision | choice | why |
|---|---|---|
| **A topic whose heading slugs to nothing** | It leads a page of its own and is never absorbed into another. Links to it go to the page, with no fragment | A section headed `!` has no anchor anywhere, so it can only be reached as a page. Rewriting the heading would change what the doc says |
| **Over-long pages** | No code. Shorter names go into each version's `rename-map.csv`, as for BusinessConnect (Phases 49–50). I draft them in `scratch/tibco-rename-proposals.csv` for the user's review first | A page name is its URL, and the tool leaves URLs to a person. Most of the 35 share a few long parent folders, so renaming those parents shortens the rest |
| **An over-long API tree name** | When any tree in a version would publish a path over the limit, every tree in that version is named by its first and last segments (`mediation-java-api-reference-com.tibco.amf.platform.runtime.extension`, 276 → 254). If two trees end up with the same name, the version keeps its current names and `sync` still refuses it | Uniform within a version, as `_named` already is. Measured with `published_root_length`, as Phase 49 does, so `convert`'s `url_map` and `sync` reach the same name |
| **Reported** | A note when a tree is named short, naming both names | A renamed folder should be findable |

#### Steps

1. `reframe/packer.py`: a topic whose `anchor_run` slot is `""` starts a page and ends it.
   Test: the three msgmx topics become three pages and the audit passes; a page with no such
   topic merges exactly as today.
2. `sync/apirefs.py`: the short-name rule in `_named`, with the length measured from
   `publishing.yaml`; register the note in `reporting/findings.py` and §7.5. Tests: an
   over-long version gets short names and `url_map` agrees with them; a version under the
   limit is unchanged; a collision keeps the long names.
3. Draft `scratch/tibco-rename-proposals.csv` (35 rows, old and new path, length before and
   after) for the user's review. Once approved, write the names into the five versions'
   `rename-map.csv`.
4. Docs: the boundary rule in `design.md`; API tree names in `architecture.md` and
   `user-guide.md`.
5. Runs (the user, as `!` commands): `reframe` for Messaging Manager 3.1.1 and 4.0.0 and the
   five renamed versions; `convert --force` and `reframe` for Service Grid 3.4.3 and 3.4.4;
   then `sync --bu tibco` and `validate`. Then I check the results without writing anything.

*Exit: all 7 versions publish; no other version's API tree name or page layout changes;
`ruff` and the suite pass.*

---

### Phase 54: A Release-Notes Root That Copies the Main Guides — **Done 2026-10-15**

**Why.** The Data Management run (2026-10-15, logs `scratch/data-management-*.log`)
found Flare packages whose `relnotes/` output root holds the whole guide set as well as
the release notes. Flare built that target with the full project instead of only its
TOC's topics. The release-notes TOC lists only `Release-Notes/` and `_templates/`; every
other page in the root is an orphan, so Phase 43 moves it to `unfiled/` and it is
published there. Measured against `output/`:

| version | relnotes orphans | under a folder its TOC never enters, also a main-guide folder | left |
|---|---|---|---|
| MDM Studio 6.1.1 | 922 | 913 (Installation 26, Process-Designer 189, Repository-Designer 274, Rulebase-Designer 311, UI-Builder 113) | 8 `Release-Notes/`, 1 `_templates/` |
| MDM Studio 6.0.0 | 901 | 896 | 5 `Release-Notes/` |
| MDM 9.3.2, 11.1.0, 11.0.0; Studio 6.1.0, 5.2.0; GDSN 4.0.0 | 0–12 | 0 | unchanged |

MDM 10.0.0 had two such copies (`relnotes/`, `Custom-installation/`) and MDM Studio 5.3.0
one. The user made both ineligible instead (2026-10-15).

The copies are not byte-identical to the main guides: each target was built separately,
with its own generated pages (`diff -r` differs on ~1,200 files for Studio 6.1.1). Page
names match; byte comparison cannot be the test.

#### Decisions

| decision | choice | why |
|---|---|---|
| **Which orphans are copies** | An orphan under a top-level folder of a secondary output root when (a) the version's TOC lists no page under that folder in that root, and (b) another output root of the version has a folder of the same name with pages the TOC lists | The user's description: the root should hold only what its TOC holds. Folder-level, not page-level: a page the main guide also leaves unlisted is still part of the copied folder. Genuine orphans in folders the TOC does enter (`Release-Notes/Known-Issues123.md`) are untouched |
| **What happens to a copy** | Dropped, not moved to `unfiled/` | It is a build artefact, not content its authors hid |
| **Links, `csh.yml`, `301.yml` into a copy** | Retargeted to the same path in the listed root when that page exists; otherwise as a Phase 43 move to nothing: links break and are listed, identifiers keep the copy's twin folder, redirect rows are dropped | The copy and its twin are the same page; a reader landing on either wants the listed one |
| **Reported** | One note per version: the root, the folders dropped and the page count | Nothing silent |

#### Steps

1. `converter/orphans.py`: in `_shelve`, before the move, find the copy folders by the rule
   above and drop their orphans; retarget references as decided. Register the note in
   `reporting/findings.py` and §7.5.
2. Tests: a relnotes root with a copied guide folder drops it and keeps its genuine
   release-notes orphan; a folder the root's TOC enters is never dropped; a folder with no
   listed twin elsewhere is shelved as today; a link from a release-notes page into the copy
   lands on the listed page.
3. Docs: the rule beside Phase 43 in `architecture.md` §5.1.4 and `user-guide.md`.
4. Runs (the user, as `!` commands): `convert --reshelve-orphans` for Studio 6.1.1 and 6.0.0
   (no re-download needed), then `reframe` and `sync` for the family. The sync swaps each
   version folder wholesale, so the published copies go. Then I check the results without
   writing anything.

*Exit: Studio 6.1.1 and 6.0.0 publish without the copied folders; no other Data Management
version's output changes; `ruff` and the suite pass.*

#### As built (2026-10-15)

- `converter/orphans.py` `_copies`: the folder gate as decided, then page by page: an
  orphan in a copied folder is a copy only when the same path exists in the twin folder
  (listed or not). One without a twin is shelved as before, so nothing is lost on a guess.
  A copy goes where its twin goes; `Reshelved.paths` carries both kinds of move into
  `output_map`. Note `ROOT_COPY_DROPPED`.
- **Step 4 changed.** `--reshelve-orphans` finds no Unfiled node in a tree already
  shelved, so it cannot reach these copies. Studio 6.1.1 and 6.0.0 need `convert --force`
  (their extracted trees are still on disk).
- Suite: 2,227 passed; the one failure is the catalog re-baseline noted under Phase 51.
- Runs: Studio 6.1.1 and 6.0.0 re-converted, re-merged and published. 913 and 896 copies
  dropped, as measured; 1,006 → 93 and 988 → 92 merged pages. 4 and 2 pages in the copied
  folders had no twin and are shelved. No other version re-merged.

---

### Phase 55: Verify — Nothing Lost Between docs.tibco.com and stg-docs.ibi.com — **Built 2026-10-23; staging pilot pending**

**Why.** ibi docs are converted and published through AEM to stg-docs.ibi.com. The
business needs evidence that **no topic, text or image was dropped**, and that **the
table of contents keeps its structure** (entries, parents, order), from the old site to
the staging site. Today nothing compares content:

- `validate` checks that links, images and the AEM files exist, not that the text is all there.
- `reframe/audit.py` checks word counts and TOC reachability inside the merge only.
- `ORIGIN_PAGE_UNMAPPED` (`origins.py`) checks page coverage against the live sitemap, not content.
- Nothing reads what stg-docs.ibi.com actually serves.
- The predecessor's `html-to-md/scripts/compare_html_md.py` passes a page at 20% of its text, which is too loose to prove anything.

User decisions (2026-10-22): stg-docs.ibi.com needs no login. The baseline is the local
downloaded HTML for every page, plus a sample of live docs.tibco.com pages. Start with one
pilot product.

A new command, `docushift verify`, makes three comparisons:

```
live docs.tibco.com --(C: sample)--> downloaded HTML --(A: every page)--> Markdown in ibi-docs-aem --(B: every page)--> stg-docs.ibi.com
```

**Known drops are not findings.** The tool already records intentional drops in `state.db`:
`NAV_NODE_DROPPED`, `TOC_SUBPROJECT_UNPLACED`, `ROOT_COPY_DROPPED` and `TOC_ORPHAN`. A topic
with one of these codes is classed as a **known drop**, not as missing. `TOC_ORPHAN` pages are
published under `unfiled/` but have no menu entry (Phase 43), so the report lists them
separately for a decision instead of hiding them.

**A. Old page vs. converted page (local, every page).** `output_map` gives source to
output, and `reframe.yml` / `redirects.yml` give output to merged page. For each source topic:

1. **Topic:** it reaches a published page or is a known drop. Otherwise `VERIFY_TOPIC_MISSING`.
2. **Text:** both sides are normalised. Normalising strips markup and the chrome (with the
   engines' own content selectors), lowercases, collapses whitespace, and evens out quotes and
   dashes. Then the text is cut into 8-word shingles. Source shingles must appear somewhere
   in the target page, so a merged page needs no special handling. If at least one whole
   source sentence is missing, the result is `VERIFY_TEXT_DROPPED`, listing the missing
   sentences. Coverage % is reported but does not decide anything.
   - Hidden source text (Flare dropdowns, togglers, popups) counts on both sides.
   - Tables are compared cell by cell.
   - Text the converter rewrites on purpose (expanded variables, inlined snippets,
     generated titles) is allowlisted up front from the conversion settings.
3. **Images:** each source `<img>` is matched by content hash, so a renamed file still
   matches. It must be referenced on the target page and present in the repo; otherwise
   `VERIFY_IMAGE_MISSING`.
4. **Counts** of headings, tables, code blocks and list items are reported, never flagged.
5. **TOC structure, old TOC vs. `toc.yml`:** the old TOC is rebuilt with the readers
   conversion already uses (`engines/flare_toc.py`, `engines/webworks_toc.py`, DITA/DocBook
   nav). It is compared with `toc.yml` entry by entry on parent, sibling order and title. An
   entry whose topic was merged matches if it points at the merged page's `#anchor`. A
   regrouping recorded in `reframe.yml` is not flagged.

**B. Converted page vs. stg-docs.ibi.com (every page).**

0. B compares against the `ibi-docs-aem` commit staging was published from, not the latest
   one. Otherwise every later edit would read as a loss. If that commit is unknown, B's text
   findings drop to warnings and the report says why.
1. Each page's staging URL is derived from its `toc.yml` position, not its repo path (see the
   probe below). A non-200 response is `VERIFY_PUBLISHED_PAGE_MISSING`.
2. The local Markdown text must appear in the served main content; otherwise
   `VERIFY_PUBLISHED_TEXT_DIFF`. This catches AEM rendering drops such as raw-HTML
   tables, includes and snippets.
3. Every `<img>` on the served page must return 200 and match the local file. Matching is
   by byte hash, or by dimensions/perceptual hash if AEM serves resized renditions.
   Otherwise `VERIFY_PUBLISHED_IMAGE_BROKEN`.
4. **TOC structure, `toc.yml` vs. served menu:** same comparison as A5, with the
   `VERIFY_PUBLISHED_TOC_*` codes. A5 and B4 together cover old TOC → `toc.yml` → staging
   menu, so a fault is pinned to conversion or to AEM.

**C. Live docs.tibco.com vs. downloaded copy (sample).** About 20 pages per version are
sampled from the origin URLs (`origins.py` / `301.yml`). A text gap against the extracted
HTML is `VERIFY_LIVE_DRIFT`, meaning the download was not what readers saw. A page served as
the SSO login page (`_AUTH_MARKERS`, `discovery/client.py`) is "not checkable", not drift.
The download date is shown so an update on the live site can be told apart from a loss.
Page-level coverage against the live sitemap stays with `ORIGIN_PAGE_UNMAPPED`.

All fetching is throttled and cached under `cache/verify/`, so a re-run costs nothing.

#### Decisions

| decision | choice | why |
|---|---|---|
| **When text counts as dropped** | At least one whole source sentence missing from the target. Coverage % is shown, not used to decide | One changed word on a 60-word page costs ~15% of 8-word shingles, so a 99% cutoff would flag every short page |
| **Merged pages** | Source text must appear *somewhere* in the merged target | No section-by-section alignment is needed, and a merge cannot hide a drop |
| **Known drops** | Read from the findings already in `state.db`; not re-flagged | They were decided when they happened; re-flagging them would bury real losses |
| **TOC check** | Structure (parent, order, title) at both hops, not just "is it present" | An entry can exist under the wrong parent or out of order, and a presence check would pass it |
| **Staging baseline** | The published commit, not HEAD | Edits since publishing are not losses |
| **Staging host** | New key `verify_base_url` in `config/publishing.yaml`, apart from `publish_base_url` | `publish_base_url` (empty, `config.py:62`) drives link rewriting; the check must not change links. The predecessor only knew `stg-docs.onebx.com` |
| **Severity** | Errors: `VERIFY_TOPIC_MISSING`, `VERIFY_TEXT_DROPPED`, `VERIFY_IMAGE_MISSING`, `VERIFY_TOC_ENTRY_MISSING`, `VERIFY_PUBLISHED_PAGE_MISSING`, `VERIFY_PUBLISHED_IMAGE_BROKEN`. Warnings: `VERIFY_PUBLISHED_TEXT_DIFF`, `VERIFY_PUBLISHED_ALT_DROPPED`, `VERIFY_PUBLISHED_CALLOUT_UNRENDERED` (both added by the probe), `VERIFY_TOC_MOVED`, `VERIFY_TOC_ORDER`, `VERIFY_LIVE_DRIFT`. Note: `VERIFY_TOC_TITLE_CHANGED`. `VERIFY_PUBLISHED_TOC_*` mirror the A5 severities | Loss is an error; a change a person may have intended is a warning. Errors set exit code 1, as `validate` does. Pilot tuning may move a code, recorded here |

#### Steps

0. **Read-only probe** (me): fetch one stg-docs.ibi.com page and one image, and find out:
   - the repo-path → URL pattern and the main-content selector, and that there is no login;
   - how the menu is built (in the page HTML, a nav JSON endpoint, or JavaScript that needs a
     headless browser) and whether it loads in full;
   - whether AEM serves the original image bytes or resized renditions;
   - whether the converter copies image bytes unchanged;
   - which `ibi-docs-aem` commit staging reflects.
   The findings are written into this phase before building.
1. `src/docushift/verify/`: `text.py` (normalise, shingles, sentences), `images.py`,
   `toc.py` (tree comparison for A5 and B4), `driver.py`. Then A, with tests on small fixtures:
   - a merged page, a renamed image and a dropped paragraph;
   - a moved TOC entry and a reordered one;
   - a known-drop topic;
   - a clean fixture, and one with only known drops, that both produce no findings.
2. `published.py` (B) and `live.py` (C), with fetch tests on recorded responses.
3. `cli.py`: `verify --target-dir --product [--skip-published] [--live-sample N]`, next to
   `validate`. Register the codes in `reporting/findings.py` under a new Verify stage and in
   §7.5.
4. Output: `reports/verify-<product>.csv`, one row per old page. Columns: old URL, local
   source, new path, staging URL, text %, missing-sentence count, images found/expected, TOC
   parent and position matched, published status, skip reason, missing sentences. Also a
   short HTML summary of the lowest-scoring pages, linking each old and new page.
5. **Pilot** (the user, as a `!` command): `docushift verify --product <pilot> --target-dir
   C:/github/ibi-docs-aem`. We review the CSV together, then tune chrome stripping and the
   allowlist.
   - Mutation check: in a scratch copy, delete a paragraph and an image reference, and move a
     `toc.yml` entry under another parent. All three must be flagged.
   - Spot-check about 10 pages and one guide's menu by eye, old against staging.
6. Roll out to every ibi product. Summarise in plain language: pages and images checked,
   what is missing, what needs a decision.
7. Docs: the command in `user-guide.md`, the stage in `architecture.md`, the comparison rules
   in `design.md`. Jira: a DOCOPS sub-task, with `docs/jira.md` Handoff and Log updated.

*Exit: the pilot's report is reviewed with no unexplained finding; the mutation check flags
all three; every ibi product is verified and summarised; `ruff` and the suite pass.*

#### Probe (2026-10-22, pilot ibi™ AI Assistant 9.3.8)

The pilot is 24 pages in `en-us-ibi-webfocus-userdocs/en-us/ibi-ai-assistant/online-help/9-3-8`.
The probe read `home.html` and `user_guide/chapter-2.html`.

| question | answer |
|---|---|
| Login | None. Pages are served openly. An unknown path returns the docs home page with HTTP 200, not a 404, so "page missing" must be detected by content (title/H1), not status |
| URL pattern | `https://stg-docs.ibi.com/us/en/<product>/<doc-class>/<version>/…` (`en-us` → `us/en`). Below the version, the path follows **`toc.yml`**, not the repo: a top-level entry is `<page-stem>.html` (`_templates/Home.md` → `home.html`), and a child is `<parent-page-stem>/<page-stem>.html` (`installation/overview.md` under `_templates/installation_guide.md` → `installation_guide/overview.html`). Deeper levels and anchors are still to be confirmed in the pilot |
| Menu | Rendered in the page HTML, fully expanded (all 23 entries of the online-help `toc.yml`, matching titles and order). No headless browser needed. Each doc-class (release information, user guides) has its own menu |
| Images | Served from `/content/dam/ibi/us/en/<product>/<doc-class>/<version>/<repo path>`, keeping the repo's folder and file name (`webfocus-aiassistant/images/hub-welcome_324x734.png`) |
| Converter image bytes | Unchanged: 18 of 18 images in the repo match the extracted source by SHA-256 |
| Staging image bytes | Unchanged: `hub-welcome_324x734.png` from staging matches the repo copy by SHA-256. AEM serves originals, so B3 compares by byte hash |
| Published commit | The page footer shows "Last published : Oct 15, 2026". The product's only content commit is `3ee14c2c` (2026-10-06), so staging serves that commit. The deploy state is kept in a cloud bucket we cannot read (`last_deployed_sha.txt`), so `verify` takes the last commit touching the product **before the page's "Last published" date** |
| Main content | `main#section-topic div.topic-renderer__content`: the article body only, one `div.cmp-text` per block. Everything else is chrome (the `cmp-navigation` menu, breadcrumb, "In this article", feedback, PDF/share/print, the authoring modal, prev/next). The page path is in `main[data-page-path]` (`/content/ibi/us/en/…/user_guide/chapter-2`) |
| Menu markup | `nav.cmp-navigation` → nested `ul.cmp-navigation__group` / `li.cmp-navigation__item--level-N` / `a.cmp-navigation__item-link`. Parent entries with a page are links too. B4 reads this |
| Spot check, chapter-2 | 4 images (source 4, Markdown 4, staging 4); 3 tables (Markdown 3, staging 3); headings in the same order. The caption "A typical answer…" has no picture under it at **every** step, source included, so it is a gap in the source and not a loss |
| **Alt text dropped** (confirmed) | Staging serves no `alt` on 2 of the 4 images in chapter-2 (`hub-slash-menu`, `hub-context`); the Markdown has alt text for all 4. The two are the only ones on the page whose alt contains `⌘` or `:`, a guess the pilot tests on all 18 images. B adds **`VERIFY_PUBLISHED_ALT_DROPPED`** (warning): an image whose Markdown alt text is missing on staging |
| **Note boxes not rendered** (confirmed; fixed by Phase 56) | All 5 GFM alerts in chapter-2 (`> [!TIP]`, `> [!NOTE]`) render as a plain quote holding an empty link (`<a class="xref" data-attr-keyref="!TIP"></a>`). The text survives; the "Tip"/"Note" label and the box are gone. Every converted note uses this syntax (`transforms/callouts.py`; ~1,700 in the corpus, `architecture.md` §5.1). The predecessor wrote `> **Note:**`, which AEM shows as a bold label. B adds **`VERIFY_PUBLISHED_CALLOUT_UNRENDERED`** (warning), one per page with the count. The fix (a different syntax from the converter, or GFM alert support in AEM) is a decision for the user and the AEM owners, outside this phase |


#### As built (2026-10-23)

- `src/docushift/verify/`: `text.py` (blocks, normalising, sentences, 8-word shingles),
  `images.py`, `toc.py` (`by_page` for A5, `by_title` for B4), `fetch.py` (throttled,
  cached under `cache/verify/`), `published.py` (B), `live.py` (C), `driver.py`,
  `report.py`. `docushift verify --target-dir [--product] [--version] [--skip-published]
  [--live-sample N] [--base-url] [--refresh]`. `state.py` gains `latest_counts`;
  `publishing.yaml` gains `verify_base_url: "https://stg-docs.ibi.com"`.
- 20 codes under a new `verify` stage (§7.5). Two more than planned:
  `VERIFY_TOC_UNCHECKED` and `VERIFY_TOPIC_UNFILED`, and `VERIFY_LIVE_UNCHECKABLE` for
  the sign-in case.
- **Changed from the plan:**
  - **Known drops are per topic only where provable.** The conversion's drop findings
    are per-version counts with no path (`NAV_NODE_DROPPED` "58 node(s)"), so they cannot
    excuse one topic. A page under `unfiled/` is an orphan (`VERIFY_TOPIC_UNFILED`). A TOC
    row with no page, or repeating its parent's page, is skipped. Anything else is
    `VERIFY_TOPIC_MISSING`, with the version's recorded drop counts in the message.
  - **Staging URLs come from the served menu, not from a rule.** The menu is read once
    per version and matched to `toc.yml` by title, which gives each page's URL.
  - **The old-TOC check (A5) reads Flare only.** Other engines get `VERIFY_TOC_UNCHECKED`.
    96 ibi versions are recorded as Flare; DITA, DocBook and WebWorks readers are a
    follow-up.
  - **The supporting counts (A4) are not built.** Merged pages make heading and table
    counts differ by design, so as warnings they would only be noise.
- **Deliberate converter changes, applied up front:**
  - the Flare landing page is cut at the converter's own `PORTAL_BLOCKS` and stripped of
    `LANDING_CHROME`;
  - each engine's `CHROME_SELECTORS` are removed inside the container;
  - the help skin's pictures (`Skins/`) are not content;
  - HTML comments are not text, and Markdown inline code is read verbatim.
- **Pilot, local (2026-10-23):** ibi™ AI Assistant 9.3.8, 24 old pages, **0 findings**:
  every page 100% text, every image found, the TOC's structure equal.
  - Before the tuning above, the run reported a landing page missing 7 sentences and
    4 images, and 4 pages missing a sentence each. Every one was traced to a deliberate
    cut or to a reading error in `verify`, not a loss.
  - Mutation check on a copy of the published folder: deleting one paragraph, one image
    reference and moving one TOC entry gave exactly `VERIFY_TEXT_DROPPED` (quoting both
    sentences), `VERIFY_IMAGE_MISSING` and `VERIFY_TOC_MOVED`.
- Staging parsing is tested on the probe's saved page: the 23-entry menu, the
  page-path check and the 5 unlabelled notes.
- Tests: `tests/unit/test_verify.py`, 24 tests. `ruff` clean.
- **Left:**
  - the staging and live runs over the pilot (the user, as a `!` command), then all ibi
    products;
  - old-TOC readers for the other engines.

---

### Phase 56: A Note Shows Its Label on AEM — **Built 2026-10-22; runs pending**

**Why.** Phase 55's probe found that AEM does not render GitHub alerts. `> [!TIP]` becomes a
plain quote holding an empty link (`<a class="xref" data-attr-keyref="!TIP"></a>`), so the
reader sees the text with no "Tip" or "Note" label and no box. Every note the converter writes
uses that syntax: one function, `transforms/callouts.py::render`, called by all four engines,
for ~1,700 notes in the corpus (`architecture.md` §5.1). The predecessor wrote `> **Note:**`.
Staging renders bold inside a quote (`<b class="ph b">` in `div.lq`), so that form keeps the
label.

User decision (2026-10-22): fix it in the converter for future conversions. For trees already
converted and published, use a small utility that rewrites the notes in place, with no
re-conversion.

#### Decisions

| decision | choice | why |
|---|---|---|
| **Target syntax** | The marker line `> [!NOTE]` becomes `> **Note:**`, and nothing else in the note changes. Labels: Note, Tip, Important, Warning, Caution | The smallest change that keeps the label. Staging already renders bold in a quote. The note's body, line breaks and nesting stay byte-identical, so the converter and the utility produce the same text |
| **No blank line after the label** (user, 2026-10-22) | The label line is followed directly by the note's first line: `> **Note:**` then `> text`, never `> **Note:**` then `>` then `> text`. Markdown then joins them into one paragraph, which reads "**Note:** text". The utility also removes a blank quote line found directly after a label line, whether the label came from the marker or was already a `> **Note:**`-style line (the predecessor wrote the blank line, e.g. `html-to-md` EBX output) | A blank line makes the label a paragraph of its own above the text. Measured 2026-10-22 over a sample of `output/` and `reframed/`: the converter never writes one today, and the first line after a marker was text 663 times, a list 54 and bold 8. A list may follow a paragraph line directly in CommonMark, so it needs no blank line. **The one exception is a table:** GFM would read the label line as the table's header row. No note in the sample opens with a table; any that does keeps its blank line and is listed in the report for review |
| **Authored labels that collapse** | `remember`, `attention`, `restriction` keep their own word as the label (`> **Remember:**`). Today they are `> [!NOTE]` followed by `**Remember**` as the first bolded word | With the GFM label gone, `**Note:** **Remember** …` would say two labels. The authored word is the more specific one |
| **A styled box** | Not in this phase. The AEM owners are asked whether their Markdown pipeline has a note syntax that renders a box. If it does, `render` and the utility's output change in one place each | Only AEM can say. `**Note:**` loses nothing in the meantime |
| **Where the utility runs** | Any folder of `.md` files: the published repos (`C:\github\ibi-docs-aem\*`, `C:\github\tibco-docs-aem\*`) **and** the local `output/` and `reframed/` trees | `sync` re-copies a page that differs from its local source (`_identical`), so fixing only the repos would be undone by the next sync. `sync`'s stale-tree check reads root files only (`_built_at`), so editing pages does not trip it |
| **What the utility touches** | Only marker lines: `> [!KIND]` at any indent and quote depth (a note inside a list item), outside fenced code blocks. Line endings and encoding are kept. Running it twice changes nothing | A page that documents Markdown may show `> [!NOTE]` in a code sample, which is content. Idempotence makes a partial run safe to repeat |
| **Git** | The utility edits files only. Committing and pushing the repos stays with the user | `architecture.md` §6.0: git is out of scope |

#### Steps

1. `transforms/callouts.py`: `render(kind, body, label=None)` writes `> **<Label>:**` in place
   of `> [!KIND]`. `dita.py` passes the authored label instead of prefixing it to the body.
   The other engines need no change. The module docstring and the `Alert` docstring stop
   saying "GitHub renders". Tests: one per kind; a collapsed label; the label line is followed
   directly by content, with no blank `>` line, for a text, list and multi-paragraph body; a
   multi-paragraph note keeps `>` on its blank lines further down; a table-first body keeps one
   blank line; engine tests that assert `[!NOTE]` updated.
2. `transforms/callouts.py`: `fix_markdown(text) -> (text, count)` holds the rewrite rule, so
   the converter and the utility share one label table. A marker followed by a first line that
   opens with `**Remember**`, `**Attention**` or `**Restriction**` takes that word as its label
   and drops it from the line. A blank quote line directly after a label line (from a marker,
   or an existing `> **Note:**`-style line) is removed, except before a table. Tests: indented
   and nested markers; a marker inside a fenced block left alone; a predecessor-style
   `> **Note:**` / `>` / `> text` loses its blank line; a table-first note keeps it; CRLF kept;
   a second run is a no-op.
3. `cli.py`: `docushift fix-callouts PATH... [--dry-run]`. It walks `*.md` under each path and
   rewrites what `fix_markdown` changes. It prints notes and files changed per top folder and
   writes `reports/fix-callouts-<date>.csv` (file, markers rewritten, blank lines removed,
   table-first notes left for review). `--dry-run` writes nothing.
4. Docs: `architecture.md` §5.1 and `design.md` (callouts are a bold label, and why);
   `user-guide.md` (the command); `ALERT_LABEL_UNMAPPED`'s wording in §7.5 if it names GFM.
5. Runs (the user, as `!` commands): `--dry-run` over each folder first, counts reviewed, then
   the real run over `output/`, `reframed/`, `ibi-docs-aem` and `tibco-docs-aem`. Then I check,
   read-only, that no `[!KIND]` marker remains outside code blocks. The user commits and pushes
   the repos; AEM republishes.
6. After the republish: Phase 55's `VERIFY_PUBLISHED_CALLOUT_UNRENDERED` is 0 for the pilot,
   and one page is checked by eye on staging.

*Exit: a fresh conversion writes `> **Note:**` with the content on the next line; the utility
has run over all four folders with no marker and no blank line after a label left (table-first
notes excepted and listed); the staging pilot shows the labels; `ruff` and the suite pass.*

#### As built (2026-10-22)

- `transforms/callouts.py`: `render(kind, body, label=None)` writes `> **Note:**` with the
  body on the next line, plus one blank quote line only before a table. `fix_markdown` holds
  the repair rule and returns what it changed (`markers`, `blanks`, `tables`).
- `engines/dita.py`: an authored label the vocabulary knows (`Remember`, `Fastpath`) is the
  label; an unknown one (`Best practice`) stays the body's first bolded run, which is also what
  `fix_markdown` leaves. DocBook captions (`**Caution 2**`) stay in the body: `fix_markdown`
  takes a run-in label only when it carries a colon, and captions have none.
- `cli.py`: `docushift fix-callouts PATH... [--dry-run]`, skipping dot-folders such as `.git`.
- Docs: `design.md` §1.6, `architecture.md` §5.1/§5.2/§5.6, `user-guide.md`, §7.5 wording.
- Tests: 15 new test functions (`test_transforms.py`, `test_cli.py`); 20 engine assertions moved from
  `[!KIND]` to the label. `ruff` clean. The full suite passes except two catalog-data tests
  that fail without this change: `test_shipped_scope_lists_the_ebx_and_spotfire_products`
  expects 129 out-of-scope products where Statistica (`461168f`) made 130, and
  `test_the_shipped_report_retires_the_measured_set` reads the uncommitted `versions.csv`.
- Measured, read-only: the pilot product (ibi™ AI Assistant) has 61 notes in 20 files. On a
  copy of `chapter-2.md` exactly its 5 marker lines changed and nothing else.
- Run, Statistica first (2026-10-22, `scratch/statistica-fix-callouts.log`, 37 minutes per pass,
  disk-bound: 87,208 pages in `output/` alone): 6,199 labels in `output/`, 6,199 in `reframed/`,
  4,175 in `en-us-spotfire-statistica-userdocs` (3,408 files), 0 in `-resources`; no blank line or
  table-first note. Checked read-only: the repo diff is only `[!NOTE]`→`**Note:**` (4,166) and
  `[!TIP]`→`**Tip:**` (9), line endings unchanged; no marker left in any of the four folders.
  Waiting: commit and push, AEM republish, then the other families.


---

### Phase 57: Translated Help Is Published to the `loc-` Tree — **Done 2026-10-23; all 27 roots committed, push and staging check pending**

**Why.** The user, 2026-10-22: languages other than English must be migrated too, for IBI
as well as TIBCO. Today every non-English build is skipped on purpose (`LOCALIZED_ROOT_SKIPPED`,
Phase 34 R5-01, deferred as item Q). The tree it should go to has been named since Phase 3.8,
`loc-{bu}-{family}-userdocs`, one tree shared by every non-English locale
(`architecture.md` §6.1). But nothing sets a locale: `ConfigManager(locale=…)` has no CLI
flag, so every run is `en-us`.

**Measured 2026-10-22** over the 739 eligible versions: extracted trees, the html-to-md
cache, `state.db` and the Coveo sitemaps.

- **Inside the packages: IBI only. Three WebFOCUS products, 15 versions, 27 localized
  roots, 61,425 pages.** All are MadCap Flare output roots at `html/<locale>/`, next to
  `html/en-us/`, each with its own `Data/HelpSystem.xml`, UTF-8 and `lang="ja-jp"` in the
  page head.

  | product | versions | locales | pages |
  |---|---|---|---|
  | WebFOCUS Client (`ibi-webfocus-client`) | 9.3.0 | ja-jp | 1,425 |
  | WebFOCUS Client | 9.3.5–9.3.8 | ja-jp, de-de, fr-fr, es-es | 46,397 |
  | WebFOCUS App Studio (`ibi-webfocus-app-studio`) | 9.3.0, 9.3.5–9.3.8 | ja-jp | 1,615 |
  | WebFOCUS Reporting Server (`ibi-webfocus-reporting-server`) | 9.3.0, 9.3.5–9.3.8 | ja-jp | 11,879 (from `asset_inventory`; the tree is no longer on disk) |

  WebFOCUS Client 9.3.7 and 9.3.8 also ship 8 more locale folders (es-mx, fr-ca, id-id,
  it-it, ko-ko, pt-br, zh-cn, zh-tw) plus en-au/en-ca/en-gb. Each holds a single
  `Default.htm` redirect stub, with no topics.
- **TIBCO and Spotfire packages: none.** That covers 129 more versions read from the
  html-to-md cache. 55 eligible versions have no tree to read: 30 BusinessWorks plug-ins,
  23 Reporting Server versions older than 9.3, App Studio 9.2.8 and Scribe. None of them has
  a localized page in Coveo.
- **Live on docs.tibco.com, not in any package:**
  - Data Virtualization 8.8.0/8.8.1 Japanese: 6,917 pages.
  - WebFOCUS Client 9.3.5–9.3.7 Japanese release notes (`relnotes/ja`): 252 pages.
  - Japanese PDFs in WebFOCUS 9.1.2–9.3.4: 121.
- **Not all of it is translated.** These figures come from a 100-topic sample per root,
  classified by script and keywords, so they are approximate:

  | | de-de / fr-fr / es-es | ja-jp |
  |---|---|---|
  | 9.3.5–9.3.7 | 97–100% translated | 98–100% Japanese |
  | WebFOCUS Client 9.3.8 | 0–3% translated | ~56% Japanese |
  | App Studio 9.3.8 | — | ~39% Japanese |
  | App Studio 9.3.0 | — | ~46% Japanese |

  App Studio 9.3.0's ja-jp root has 340 of 459 pages with no en-us counterpart.
- **Repositories:** `loc-ibi-webfocus-userdocs` exists (empty, `ibi-docs-aem`). There is no
  `loc-ibi-wf-reporting-server-userdocs`, and no TIBCO `loc-` repo.
- **The architecture doc's count is out of date.** §5.1's "24 localized roots" is now 27
  eligible: Reporting Server's 5 were added, and Team Studio's 2 left when it retired.

User decisions, 2026-10-22:
- Content that is live but not in a package: ask the docs team for packages, and don't
  crawl the site.
- Partly translated builds are published as shipped, with the untranslated share reported.
- Translated pages keep the English page names, so each locale's addresses mirror en-us.

#### Decisions

| decision | choice | why |
|---|---|---|
| **Locale is a run setting** | `--locale ja-jp` on `convert`, `sync`, `validate`, `status` and `report`, default `primary_locale`. It sets `ConfigManager(locale=…)`, which already routes `docs_tree_name` to `loc-…` and the inner folder to `ja-jp/` | The naming machinery exists and is tested (Phase 3.8). One run converts one language, so every stage, check and finding stays per language, exactly as English is today |
| **A localized run reads the English package** | A non-primary run takes the download and extracted tree of the **primary** workspace (`families/en-us-…`) whenever its own `families/ja-jp-…` has none. A separate localized ZIP, if the docs team ever ships one, still lands in its own workspace, as §6.1 always said | Every localized build measured ships *inside* the English ZIP. Downloading and unpacking it a second time would only duplicate 1 GB per version |
| **Which roots a run converts** | A primary run keeps untagged roots and its own language's, as today. A localized run keeps **only roots tagged with its locale**: an untagged root such as `Release-Notes-93x` or `_templates` is English and belongs to the en-us run. A tagged root with no topics (the 8 stubs) is reported and left out | The skip rule today keeps untagged roots for every run, which would publish the English release notes into the Japanese tree |
| **State is kept per locale** | A localized run writes its own state file, `cache/state-<locale>.db`, with the same schema. It reads extract-stage facts (`version_metadata` output roots and engine, `csh_source`, `asset_inventory`) from `state.db`. `versions.csv` stays the English view; `status --locale` reports the rest | Every table is keyed `(slug, version)`, and a second language under the same key would overwrite the English row's status, output map and findings. Adding a locale column means changing every query that state.py keys on `(slug, version)` (17 of them), in the middle of the English runs, while a separate file leaves the English pipeline byte-identical. The cost is two files, and `report`/`status` must be told which one to read |
| **Page names** (user) | Every converted topic is named from its source path, as Flare already does, so `html/ja-jp/bi-portal/x.htm` publishes as `ja-jp/<slug>/online-help/<ver>/bi-portal/x.md`, the en-us name. A **generated** page (a TOC heading with no topic) takes the name of the en-us node at the same TOC position, when the two TOCs have the same shape, and otherwise a positional name (`section-2-3`) | Measured: `navigation._slug` keeps `[a-z0-9]` only, so a Japanese TOC label slugs to nothing today. Positional fallback keeps names stable across re-runs without using title text |
| **Translated-share report** (user: publish as shipped) | A page whose converted body is identical to the en-us page of the same name counts as untranslated. One finding per root gives the count and share, and a page with no en-us counterpart is counted separately | It needs no language detection: the English build is the reference. It works the same for German as for Japanese |
| **Labels the tool writes** | "Unfiled", "Online Help", "Documentation", the doc-class index titles and the release-notes, readme and licence labels move into `config/locales.yaml`, one block per language. A missing entry falls back to English with a note, and the first runs publish with English labels | The translations have to come from the docs team, so the tool must not invent them. The fallback means the work does not wait for them |
| **Merging** | Localized trees follow the product's English merge policy. Every localized build today is IBI, which is not merged (`reframe.yaml` publishes only TIBCO), so `reframe` gets no `--locale` in this phase | The word cap counts words by spaces, which is meaningless for Japanese. Fixing that is only worth doing once a merged product has a translation |
| **Redirects** | Each localized version gets its `301.yml` from its own live URLs (`…/doc/html/ja-jp/…`), through the same Coveo derivation as English. `redirects.region_and_language` already maps `ja-jp` to `jp/ja` | The Japanese live pages are in the sitemaps (measured), so nothing new is needed beyond running it per locale |
| **CSH** | Each locale's `Alias.xml` gives that locale's `csh.yml`, in its own version folder | Today a localized root's help map is dropped (R5-01), so it can't reach the English map. The loc tree has its own folders, so the maps can't collide |
| **Heading anchors** | No change until staging shows one Japanese page. If AEM keeps voiced kana (ガ) in an anchor and we strip them (`anchors.slugify_heading` folds to NFKD), the fold becomes ASCII-only | Only the platform can say what anchor it generates. The pilot in step 7 answers it |
| **New repositories** | `loc-ibi-webfocus-userdocs` exists. The doc platform is asked for `loc-ibi-wf-reporting-server-userdocs`. TIBCO needs none until a package with a translation arrives | Creating repositories is outside this tool (§6.0) |

#### Steps

1. **Run setting.** `--locale` on the five commands. `ConfigManager` takes it and derives
   `state_db_path` for it. `doctor` prints the locale and the state file. The primary
   workspace becomes the fallback source for download and extract paths. Tests: the en-us
   paths don't change. A ja-jp run resolves the en-us extracted tree, writes
   `output/ja-jp-ibi-webfocus/…` and `state-ja-jp.db`, and gives
   `loc-ibi-webfocus-userdocs/ja-jp/…` in sync.
2. **Root selection.** `_without_localized` becomes "keep the run's own language". A localized
   run drops untagged roots, reported in one note per version. A tagged root with no topic is
   reported as a stub. Tests use the wf-wf 9.3.7 layout: en-us, ja-jp, 4 full roots and 8
   stubs.
3. **State split.** A `SourceStore` view reads extract-stage tables from `state.db`. Convert,
   sync and validate write to the run's store. Tests: an en-us convert after a ja-jp convert
   leaves the en-us `output_map`, `stage_event` and findings unchanged, and the reverse.
4. **Names and generated pages.** Generated pages are named from the en-us TOC by position,
   with the positional fallback. Tests: an identical-shape TOC mirrors the English names; a
   reshaped one falls back; a Japanese label never produces an empty name.
5. **Labels and the translated share.** `config/locales.yaml`, read where each label is
   written today (`orphans.py`, `navigation.py`, `sync/documents.py`, `sync/router.py`, the
   four engines' "Unfiled"). The share comparison runs after convert against the en-us
   output, and is skipped with a note when the en-us version isn't converted. New codes:
   `LOCALIZED_SHARE_UNTRANSLATED` (warning, per root), `LOCALIZED_ROOT_STUB` (note),
   `LOCALIZED_LABEL_UNTRANSLATED` (note), `LOCALIZED_UNTAGGED_ROOT_LEFT` (note). Each goes into
   §7.5 as it is built.
6. **Docs.** `architecture.md`: §5.1, root selection and the 27-root count. §6.1, localized
   runs read the primary workspace. A new subsection on per-locale state.
   `user-guide.md`: `--locale`, with a worked WebFOCUS example. `design.md`: the same, marked
   Built. `open-issues.md`: the content that is live but not in a package.
7. **Pilot run** (the user). WebFOCUS Client 9.3.6 ja-jp: `convert --locale ja-jp`, then
   `sync --locale ja-jp` into `ibi-docs-aem`, then `validate`. I check, read-only, the page
   count against the root (2,833), the names against en-us, `301.yml`, `csh.yml`, and that
   the en-us tree and `state.db` are unchanged. The user pushes the branch, and one page is
   checked on staging, including the anchor question.
8. **Full run** (the user). Every remaining WebFOCUS Client and App Studio locale into
   `loc-ibi-webfocus-userdocs`. Reporting Server is first re-downloaded and re-extracted, then
   converted once `loc-ibi-wf-reporting-server-userdocs` exists. A per-version table of the
   translated share goes to the docs team.

**Not in this phase:**
- The content that is live but not in a package, until the docs team supplies packages.
  It then goes through `download --from-file` into its own locale workspace.
- Merging localized trees.
- Translating product names (they are brand names and stay as published).

#### As built (2026-10-22)

Approved by the user 2026-10-22. Steps 1-6 done; steps 7-8 are the user's runs.

- **`--locale` is a global option**, `docushift --locale ja-jp convert …`, rather than one
  flag per command. Every command sees the same setting, so each one either works per
  locale or refuses it:
  - `catalog` and `reframe` refuse it (`_primary_only`, exit 2).
  - `download` accepts it only with `--from-file`.
  - `status` and `report` read the locale's state file.
- **State:** `ConfigManager.state_db_path` became a property, so `publishing.yaml` is not read
  at construction; reading it there broke a test that writes the file afterwards. It gives
  `cache/state-ja-jp.db` for a localized run, built by `cfg.state_store()`.
  `state.LocaleStateStore` reads these from `state.db`:
  - catalog snapshots, help-map sources, engine map and asset inventory;
  - metadata, as the base's keys overlaid with the run's own;
  - the downloaded and extracted halves of `status`'s funnel and events.

  `CatalogManager.save` is a no-op for a localized run, so `versions.csv` stays the English
  view. Measured: an en-us convert's state rows and `versions.csv` are byte-identical after a
  ja-jp convert of the same version (test).
- **The package path falls back** to the primary workspace in `download_path` and
  `extract_path` when the run's own has none (`ConfigManager._or_primary`).
- **Roots:** a localized run keeps only roots tagged with its language. Untagged roots go to
  `excluded_roots` with one `LOCALIZED_UNTAGGED_ROOT_LEFT` note, but not to the
  nested-root cascade, so a localized root inside one is still found.
- **The 8 one-file locale folders are not output roots** (no `Data/HelpSystem.xml`), so
  nothing picks them up and no stub code was needed. Dropped from the plan.
- **Generated-page names: no TOC mirroring.** A label that slugs to nothing is already named
  `index`, `index-2`, … by `_free`, never empty (test). English WebFOCUS Client 9.3.6 has 2
  generated pages, both `unfiled.md` or template pages, so mirroring had nothing to mirror.
  Dropped.
- **Page paths mirror the English *within* the guide.** The English tree has one extra folder
  level when its package holds more than one guide set: WebFOCUS Client publishes
  `9-3-6/en-us/bi-portal/x.md` because `Release-Notes-93x` is a second unit. The Japanese
  run has one unit, so it publishes `9-3-6/bi-portal/x.md`.
- **Labels:** `config/locales.yaml` holds the one label a `loc-` tree shows, `toc.yml`'s
  `docs_list_title` ("Online Help"), read by `ConfigManager.label`. The other labels the
  plan listed never reach a `loc-` tree:
  - `sync_documents` publishes nothing for a localized run, because the package's PDFs and
    release notes are English and publish through the primary run.
  - The "Unfiled" node is shelved out of the TOC (Phase 43).

  The label is folded into a localized run's inputs key only, so no English key moves.
- **Redirects:** `origins.in_locale` narrows a version's sitemap to its own language before
  `301.yml` is built and fingerprinted. Measured on WebFOCUS Client 9.3.6: 2,833 ja-jp
  pages, the same as the root's page count; 2,716 de-de; 2,779 en-us of 13,972. The English
  run's list is unchanged on purpose: narrowing it would move the inputs key of every
  WebFOCUS and Data Virtualization version.
- **Sync:** a localized run publishes its converted tree whatever the product's merge
  policy says.
- **Pilot convert, WebFOCUS Client 9.3.6 ja-jp (2026-10-22, run by the user):**
  - Converted: 2,825 topics, 1 unit. All 2,722 TOC links resolve, with Japanese titles.
  - `301.yml` has 2,686 rows and 8 live pages unmapped. The English 9.3.6 has no `301.yml`
    (`ORIGIN_TEMPLATE_UNDECLARED`), because its page list mixes 5 languages.
  - `csh.yml` has 135 identifiers.
  - The share: 1 page identical to English, 76 with no English counterpart.
  - The English tree, `state.db` rows and `versions.csv` row are unchanged.
  - **900 `REFERENCE_UNRESOLVED`, against 0 in English.** The Japanese build ships 1,605
    PNGs to the English build's 3,059, and every missing one checked is present in
    `html/en-us/` at the same path.

  User decision, 2026-10-22: use the English image. `AssetCopier` takes a `fallback` root,
  which the driver sets to `translation.english_root(root)` for a localized run only. A
  missing file found there is copied to the same target, counted as
  `LOCALIZED_IMAGE_BORROWED`, and is not case-checked against the localized root. The
  package does not change, so the pilot needs `convert --force` to pick it up.
- **Full run, 2026-10-22** (`scratch/loc-full-convert.sh`, `loc-full-sync.sh`): 22 localized
  versions converted, synced and validated into `loc-ibi-webfocus-userdocs` on `main`
  (commits `2e49354` and `e5144e9`; not pushed).

  | builds | pages per version | images from English | errors |
  |---|---|---|---|
  | ja-jp: Client 9.3.0–9.3.8, App Studio 9.3.0–9.3.8 | 257–3,366 | up to 893 (Client 9.3.6/9.3.7) | 0 |
  | de-de, fr-fr, es-es: Client 9.3.5–9.3.8 | 2,708–3,257 | about 1,550 (9.3.6/9.3.7) | 0 |

  Every version has a `301.yml`; Japanese Client alone has 11,431 redirects.

  The warning-heavy versions match their English twins, finding for finding:
  - Client 9.3.5 has about 2,100 `ANCHOR_MISSING` per language, against 2,066 in English.
  - Japanese Client 9.3.0 has 1,024, against 2,129.
  - Japanese App Studio 9.3.0 has 341, against 305.
  - Client 9.3.8 has 128–136 `REFERENCE_UNRESOLVED` per language, against 129 in English:
    the functions chapter's images ship in no language.

  **The share understates English text in 9.3.8.** Only about half of the de/fr/es and
  Japanese 9.3.8 pages are body-identical to English (1,593–1,596 of 3,257–3,366, 47–49%).
  The inventory's sample read de/fr/es 9.3.8 as 97–100% English, so the other half differs
  from the English build without being translated. The figure is a floor.

  Reporting Server, 2026-10-23: the five 9.3.x packages were re-downloaded and re-extracted, then
  Japanese converted, synced and committed (`15711ad` in `loc-ibi-wf-reporting-server-userdocs`,
  not pushed). 1,746–2,904 pages per version; up to 792 images from English. 0 errors in the
  Japanese folders. The 15 `LINK_BROKEN` the run reported are in the English folders, which
  `validate` walks too. Share: 9.3.0 10% and 9.3.8 29% identical to English; 9.3.5–9.3.7 0%.
  Japanese 9.3.6 has 27 unresolved images against English's 1: old screenshots only the
  Japanese pages still reference, shipped in neither build. All 27 eligible localized roots
  are now published.
- **Codes:** `LOCALIZED_UNTAGGED_ROOT_LEFT`, `LOCALIZED_SHARE_UNTRANSLATED`,
  `LOCALIZED_LABEL_UNTRANSLATED` and `LOCALIZED_IMAGE_BORROWED`, registered in §7.5.
  Register 91 → 95.
- **Tests:** `test_converter.py`, `test_config.py` and `test_state.py`, all in Phase 57
  sections. The suite has 2,261 passed; the 2 failures were already failing at HEAD before
  this phase (`test_the_shipped_report_retires_the_measured_set`,
  `test_shipped_scope_lists_the_ebx_and_spotfire_products`, both catalog counts).

*Exit: all 27 localized roots are converted
and synced into their `loc-` trees, with English names, redirects and help maps. The 8 stubs
and the untranslated share are reported. A second en-us run of a WebFOCUS version produces
no diff. The staging pilot renders one Japanese page. `ruff` and the suite pass.*

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
| Phase 34 (R4–R6) | 4 fragile-but-correct DITA/DocBook items deferred at triage, theme Z: R6-08, R6-10, R6-11, R6-13. Also deferred by decision: publishing non-English Flare builds to the `loc-` tree (Q, now planned as Phase 57), and converting a version that mixes two generators with both engines (T) | [reports/review/INDEX.md](../reports/review/INDEX.md) |
| Phase 34 (R7–R9) | 8 fragile-but-correct items deferred at triage, theme AI: R7-08, R7-10, R8-09, R8-10, R8-12, R9-06, R9-07, R9-08 | [reports/review/INDEX.md](../reports/review/INDEX.md) |
| Phase 34 (R10–R12) | 5 items deferred at triage, theme BF: R10-04 (all-archived products get no archives page), R10-07 (API link URL shape, unconfirmed), R10-08, R10-12, R11-10 | [reports/review/INDEX.md](../reports/review/INDEX.md) |
| flogo-connectors run, 2026-10-07 | `OUTPUT_COUNT_MISMATCH` false alarms: 43 Flare versions, 1 each. 9 are an unfilled What's New template (`WHATS_NEW_PLACEHOLDER`, not published by design), 34 Flare's sample `MicroContent/.../what-is-micro-content.htm` (a `GENERATED_DIRECTORIES` folder). Both are counted as converted documents but never written. Checked by diffing source topics against `output/` for HTTP 1.1.1, SNS 1.0.1, Kafka 1.3.1, VS Code 1.3.5 | run 629 |
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
| `ZIP_CASE_DUPLICATE_SKIPPED`⁵² | note | extract | Two ZIP members differing only in letter case with the same CRC-32 and size; the second is not written. One package on 2026-10-14 (MFT z/Linux 8.1.0, a font) | Phase 52 |
| `CSH_SOURCE_EMPTY` | note | extract | CSH source present but empty — no `csh.yml` written | `architecture.md` §5.4.2 |
| `CSH_SOURCE_UNPARSED` | warn | extract | Source located but failed to parse; `_has_csh` still set | `design.md` §6.2 |
| `INVENTORY_PARTIAL`³⁴ | warn | extract | A directory in the extracted tree could not be read; the inventory columns are left blank, not the previous package's | Phase 34 (R3-04) |
| `ENGINE_UNKNOWN` | warn | convert | `auto`, or a named engine with no handler — skipped, not guessed | invariant 7 |
| `DOCSET_SKIPPED` | warn | convert | A file-named doc-set reaching the engine guard | `architecture.md` §5.2 |
| `NAV_NODE_DROPPED` | note | convert | A node with no page and no children — DITA's `lof`/`lot`/`ix` (first top-level node in 246 books), Flare's 7 childless headless nodes — or a Flare/WebWorks child that repeats its parent's page *and* bookmark exactly. A child pointing at a section of its parent's page is kept as `page.md#anchor` (Phase 34, R7-01) | Phase 5, Phase 34 |
| `OUTPUT_ROOT_MISSING`⁵ᵇ | warn | convert | Engine detected, no unit of work found — the 5 partial Flare outputs | `architecture.md` §5.1.1 |
| `CONTENT_MISSING`⁵ᵇ | warn | convert | A topic with no content container — reported, never guessed at | `architecture.md` §5.1.6 |
| `CONTENT_BODY_FALLBACK`³⁴ | note | convert | A Flare root whose skin writes no content container; its MadCap topics were converted from `<body>`, one row per root (10 Statistica roots, ~1,485 topics) | Phase 34 (R5-09) |
| `CONTENT_SOURCE_TOPIC` | note | convert | A Flare root shipping authored source topics: each converted from `<body>`, variables and conditions settled from the root's built topics, one row per root | Phase 41 |
| `TOC_UNREADABLE`³⁴ | warn | convert | A Flare root's `HelpSystem.xml` or declared TOC is missing or did not parse; or a WebWorks book's `files.js`, `toc.js`, `title.js` or `context.js` is present and unreadable, or (`files.js`/`toc.js`) yields no entries. Its topics are filed under Unfiled, or the book loses what that file named | Phase 34 (R5-12, R7-09) |
| `TOC_SUBPROJECT_UNPLACED`³⁴ | note | convert | A merged-project TOC node (`*.flprj`, 121 over 937 roots) marking where a sub-project's TOC goes; dropped, so the sub-guide loses its place in the parent's navigation | Phase 34 (R5-11) |
| `TOC_ORPHAN`⁵ᵇ | note | convert | Converted topics in no TOC entry, kept out of `toc.yml` and unmerged under `unfiled/` — 5.9% for Flare; left in an Unfiled node only when the version has no other TOC entry | `architecture.md` §5.1.4, Phase 43 |
| `ROOT_COPY_DROPPED` | note | convert | Unlisted pages of a secondary output root that copy a main guide's pages (a Flare target built from the whole project); dropped, their links, help ids and redirects pointed at the twin | `architecture.md` §5.1.4, Phase 54 |
| `TOPIC_LINK_DANGLING`⁵ᵇ | note | convert | A cross-reference to a topic this run did not produce; text kept, link dropped | `architecture.md` §5.1.3 |
| `ALERT_LABEL_UNMAPPED`⁵ᵇ | warn | convert | An admonition label outside the five kinds; rendered as NOTE | `transforms/callouts.py` |
| `ANCHOR_DROPPED`¹⁹ | warn | convert | A referenced anchor the engine kept and then did not emit; its links now dangle | `planning.md` Phase 19 |
| `LANDING_PAGE_EMPTY`⁵ᵇ | note | convert | A landing page with nothing past its hero — a stub was generated (4.5% measured) | `architecture.md` §5.1.5 |
| `TAIL_PAGE_MISSING`⁵ᵇ | warn | convert | No support or no legal page in the TOC — nothing is synthesized | `architecture.md` §5.1.5 |
| `ENGINE_ROOT_UNCONVERTED`³⁴ | warn | convert | A unit of work for a second convertible engine (a WebWorks book inside or beside a Flare root, as in BusinessConnect 7.4.0), in a version converted by another; not converted, one row per root naming the engine | Phase 34 (R4-02) |
| `LOCALIZED_TREE_SKIPPED`⁵ᵇ | note | convert | A localized subtree inside an English unit, not converted | `architecture.md` §5.1.9 |
| `LOCALIZED_ROOT_SKIPPED`³⁴ | warn | convert | An output root built for another locale (24 in the corpus: `ja`, `ja-jp`, `de-de`, `fr-fr`, `es-es`), not converted into this locale's tree; one row per root, naming its locale | Phase 34 (R5-01) |
| `LOCALIZED_UNTAGGED_ROOT_LEFT`⁵⁷ | note | convert | A localized run's root that names no language (`Release-Notes-93x`), left to the primary run; one row per version, naming the roots | Phase 57 |
| `LOCALIZED_SHARE_UNTRANSLATED`⁵⁷ | warn | convert | A localized version's pages whose body is identical to the English build's page of the same source name, counted with those that have no English counterpart; published as shipped (user, 2026-10-22). Also a count-0 row when the English version is not converted, so the share was not measured | Phase 57 |
| `LOCALIZED_LABEL_UNTRANSLATED`⁵⁷ | note | convert | A label the tool writes into a `loc-` tree (`toc.yml`'s "Online Help") kept in English, because `config/locales.yaml` has no text for the run's locale | Phase 57 |
| `LOCALIZED_IMAGE_BORROWED`⁵⁷ | note | convert | A file a localized build references but does not ship, copied from its English sibling root at the same path (user, 2026-10-22); one row per unit with the count | Phase 57 |
| `ASSET_ORPHANED` | note | convert | Unreferenced asset — 54.6% is normal for Flare | `architecture.md` §5.5.7 |
| `REFERENCE_UNRESOLVED` | **error** | convert | A reference producing neither link nor copy | invariant 13 |
| `ASSET_RENAMED_FOR_LENGTH`⁴⁹ | note | convert | An asset whose published path would pass 260 characters, copied under a shorter name in the same folder (cut, plus 8 hex digits of its source path); its link follows. One image in the corpus on 2026-10-09 | Phase 49 |
| `REFERENCE_PAGE_SEGMENT_DROPPED`⁴⁷ | note | convert | A reference naming a page as a folder (`a.htm/b.png`), resolved without that segment (Service Grid 3.4.3/3.4.4 only, 292 each) | Phase 47 |
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
| `LINK_TO_UNFILED` | note | validate | A listed page links to an orphan under `unfiled/`, which AEM does not publish; listed in that version's `unfiled/inbound-links.csv` | Phase 43 |
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
| `RENAME_MAP_AMBIGUOUS`⁵⁰ | warn | reframe | A row in `rename-map.csv` for a source topic that leads more than one page, with no `page_key` to say which; no page takes the name, each row named | Phase 50 |
| `RENAME_MAP_UNMATCHED`³⁴ | warn | reframe | A row in `rename-map.csv` whose `old_path` no longer leads a page (a re-convert renamed the topic, or a boundary change merged it); its name is not used and the row is dropped from the rewritten map, each one named old -> new | Phase 34 (X1-07) |
| `RENAME_MAP_MISSING`³⁴ | warn | reframe | `rename-map.csv` is gone from a merged tree that had one (a failed or killed swap used to take it along); the names come from the copy `state.db` keeps, or are recomputed if none survives, and the message says which | Phase 34 (X2-02, X3-02) |
| `HEADING_LEVEL_NORMALIZED`²⁷ | note | convert | Headings renumbered to close a level the source skipped; depth and order unchanged. One row per version; `count` is how many | Phase 27 |
| `DEFINITION_TERM_RECOVERED`²⁷ | note | convert | Terms marked up as `class="dt"` rather than `<dt>`, retagged so they publish as terms instead of as prose | Phase 27 |
| `INDEX_UNLINKED`¹⁰ᵇ | note | validate | A published document no `index.md` links to — the reverse of `LINK_BROKEN` | Phase 10b |
| `WHATS_NEW_PLACEHOLDER`¹¹ᵃ | note | convert | What's New shipped as the unfilled MadCap template (167 of 648 roots); not published | Phase 11a |
| `OUTPUT_COUNT_MISMATCH`¹³ | warn | convert | Fewer Markdown files on disk than documents converted; two writes landed on one path | Phase 13 |
| `REFRAME_TOC_SCHEMA_UNKNOWN`²⁰ᵃ | error | reframe | No TOC adapter matches this version's `toc.yml`; refusing to merge a partly-understood tree | `REFRAME-INTEGRATION-PLAN.md` §4 Phase 0 |
| `REFRAME_LAYOUT_UNPINNED`²⁰ᵃ | note | reframe | More than one eligible version and no pin in `reframe.yaml`; laid out on the newest eligible version, chosen automatically (Phase 42) | `REFRAME-REQUIREMENTS.md` R1.4 |
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
| `VERIFY_TOPIC_MISSING`⁵⁵ | error | verify | An old TOC topic or converted topic with no published page and no recorded reason; the message carries the version's recorded drop counts | Phase 55 (A1) |
| `VERIFY_TEXT_DROPPED`⁵⁵ | error | verify | Whole sentences of an old page found nowhere on the page it became; the message quotes them | Phase 55 (A2) |
| `VERIFY_IMAGE_MISSING`⁵⁵ | error | verify | An old page's picture, matched by content hash, not referenced by the page it became, or referenced and not in the tree | Phase 55 (A3) |
| `VERIFY_TOC_ENTRY_MISSING`⁵⁵ | error | verify | An old TOC entry whose page has no toc.yml entry | Phase 55 (A5) |
| `VERIFY_TOC_MOVED`⁵⁵ | warn | verify | A toc.yml entry under a different parent than in the old TOC | Phase 55 (A5) |
| `VERIFY_TOC_ORDER`⁵⁵ | warn | verify | Siblings in a different order than in the old TOC, once per parent | Phase 55 (A5) |
| `VERIFY_TOC_TITLE_CHANGED`⁵⁵ | note | verify | A toc.yml entry titled differently from the old TOC's | Phase 55 (A5) |
| `VERIFY_TOC_UNCHECKED`⁵⁵ | note | verify | A version whose old TOC verify cannot read yet (engine other than Flare); its TOC structure was not compared | Phase 55, as built |
| `VERIFY_TOPIC_UNFILED`⁵⁵ | note | verify | Converted topics kept under unfiled/ (TOC_ORPHAN): in the tree, in no menu | Phase 55, known drops |
| `VERIFY_PUBLISHED_PAGE_MISSING`⁵⁵ | error | verify | A published page, or the version itself, not served by staging (non-200, or the home-page fallback) | Phase 55 (B1) |
| `VERIFY_PUBLISHED_TEXT_DIFF`⁵⁵ | warn | verify | Sentences of a published page missing from what staging serves | Phase 55 (B2) |
| `VERIFY_PUBLISHED_IMAGE_BROKEN`⁵⁵ | error | verify | A page's image not on the served page, not served, or served with other bytes | Phase 55 (B3) |
| `VERIFY_PUBLISHED_ALT_DROPPED`⁵⁵ | warn | verify | An image whose Markdown alt text staging serves empty | Phase 55 (probe) |
| `VERIFY_PUBLISHED_CALLOUT_UNRENDERED`⁵⁵ | warn | verify | GitHub alerts AEM rendered with no label, counted per page; fix-callouts repairs them (Phase 56) | Phase 55 (probe) |
| `VERIFY_PUBLISHED_TOC_ENTRY_MISSING`⁵⁵ | error | verify | A toc.yml entry with no row in the menu staging serves | Phase 55 (B4) |
| `VERIFY_PUBLISHED_TOC_MOVED`⁵⁵ | warn | verify | A toc.yml entry the served menu shows under another parent | Phase 55 (B4) |
| `VERIFY_PUBLISHED_TOC_ORDER`⁵⁵ | warn | verify | Menu siblings in a different order than toc.yml, once per parent | Phase 55 (B4) |
| `VERIFY_PUBLISHED_TOC_TITLE_CHANGED`⁵⁵ | note | verify | A menu row titled differently from its toc.yml entry | Phase 55 (B4) |
| `VERIFY_LIVE_DRIFT`⁵⁵ | warn | verify | A sampled docs.tibco.com page holding sentences the downloaded copy lacks; updated since download, or not what was downloaded | Phase 55 (C) |
| `VERIFY_LIVE_UNCHECKABLE`⁵⁵ | note | verify | Sampled docs.tibco.com pages that answered with the sign-in page or an error | Phase 55 (C) |

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
| 39 | A PDF-Only Package Is Not Blocked | Complete, 2026-10-05 | [phase-39.md](history/phases/phase-39.md) |
| 41 | Flare Source Topics Shipped in the Output | Complete, 2026-10-06 | [phase-41.md](history/phases/phase-41.md) |

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
