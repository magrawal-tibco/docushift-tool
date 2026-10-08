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
- **Pending (network):** re-download the 4 StreamBase versions; `catalog sitemap` over the whole scope, then repeat the dry run.

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
