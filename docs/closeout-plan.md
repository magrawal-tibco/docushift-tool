# Close-out plan: 12 Nov to 30 Nov 2026

> The one plan for finishing the migration. It replaces day-to-day picking from the Jira handoff.
> The testing scope (what each check covers, Stages 1–3, team requirements, backup table) stays in
> `reports/uat-plan-2026-11-12.md`; this file says **who does what, on which day**.
> Go-live: **Mon 23 Nov** (may move to 25–26 Nov). Old site off: **Mon 30 Nov**.

## Today

*Rewritten each morning. Never more than three decisions.*

**Mon 16 Nov.**
- **`wip` frozen for now (user, Mon):** Digital Platform is pushing ibi and the build pipeline is full. Nothing goes to `wip` until they finish; local work keeps going to `content-fix` (29 TIBCO repos pushed to `content-fix` Mon).
- **BW plug-in renames approved (user, Mon), without waiting for AEM's answer:** 133 folder moves in the 2 BW plug-in repos, committed on `content-fix` (`a69a137f`, `8b02901`); names active in `config/publish-names.yaml` (`90ac6c9`). They go to `wip` when it opens.
- **Phase 82 built (user approved Mon):** per-version old-site URL rules. TCM 6.1.0 (81), TCM 6.2.0 (107) and Partner Management Portal 1.0.0 (70) now have page redirects; BusinessConnect `1ac777f` on `content-fix`. TCM 6.1.1 is not published. All known redirect files without page rows are now fixed.
- **Staging checks, end of Mon:** 516 of 613 TIBCO versions checked (84%, from 17% Sat). Lost 36, issues 47, logged 362, explained 1, clean 70; 97 not checked (Karan's removals and versions with no published folder). Triage 2a/2b/3 merged (`284ffdd`), status page published. Stalled builds: EMS and Adapters only. Redirect fix: rules for Activation Service, BusinessConnect, MDM (`50058a5`); MDM 11.1.0 restored (`44216cd`).
- **`&#92;` confirmed on staging (user, Mon):** the Foresight test row (TI 6.0.0, "Sending in a File") shows `TransactionInsight\*version*\DemoData` with *version* in italics. R002 is cleared for R2 as committed; no change to the repair.
- **Stage 3 checks running (3 at once):** 3a, 83 (the 4 Stage 2b crash re-runs and the remaining TIBCO families); 3b, 119 BW plug-ins; 3c, 42 Streaming and MFT. Two agents triage Stage 2a and 2b into `reports/verify/triage-stage2{a,b}-2026-11-16.*`. Batch windows now close themselves when done.
- **Stalled builds reported (user, Mon):** EMS and Adapters were pushed and are on GitHub but staging has not rebuilt them. The team is notified. The build trigger is a GitHub App, so no webhook shows in a repo's settings, and its absence there means nothing. R2 pushes to these wait until they build. **Foresight TI 6.0.0 is built** (user, Mon): labels show; its doubled backslashes are R002, which goes with R2. Instream is not served at all (already in the UAT sheet as content missing). **General is not stalled** (user, Mon): Activation Service 1.1.0 (its newest commit, 9 Nov) shows "Last published Nov 13"; Enterprise Administrator 2.4.3 pages last changed 30 Oct and already carry note labels on `wip`, so "Nov 01" is right.
- **ibi still held:** Digital Platform's refresh is not on any ibi `wip` yet (newest commits 10–11 Nov).

**Fri 13 Nov (written 02:15).**

- **Priorities (user, 13 Nov 12:55):**
  - **TIBCO first, then ibi.** Statistica and Spotfire (Data Virtualization included) are last: their triage, checks and fixes come after all TIBCO and ibi work, and do not take a Monday slot.
  - **ibi is held until Mon 16:** Digital Platform refreshes the ibi content over the weekend. Nothing is pushed to any ibi repository (`wip` or `content-fix`), and R1's ibi group and Batch 3 (ibi newest) move to Mon 16 or later. Local ibi conversion in the running batch carries on; its syncs wait for Monday and are made only after a fresh fetch.
- **Update 11:20:** staging rebuilt groups 1–2 sometime between 03:20 and 11:20 (Control Plane now shows its "Note:" labels). So rebuilds take hours or follow a schedule; the question to Digital Platform still stands. **R1 resumed:** group 3 (General, FTL, Foresight, Flogo) is on `wip` at 11:21. Next groups follow once group 3 shows; TRA and BusinessWorks are pushed only up to before their K2 commits.
- **Pulled forward from Mon–Tue (user, 13 Nov: use the free time):**
  - **K2:** Karan's 80 removals are on `content-fix`, one commit per product.
  - **Batch running (110 steps):** re-conversion for 349 and 343/362/363 (EMS, BE 6.3.2 and 6.4.0, ibi FOCUS and WebFOCUS Client 9.3.x, WFC 9.3.5 translations), K3 conversion of the 27 additions, and the Δ1 test refresh. Nothing is synced until page lists are compared with the published ones.
  - **Phase 78: built, merged and applied (12:05).** EMS 10.5.1 has 217 pages (159 before); every old URL keeps its redirect row. It is one commit on `content-fix` (`28ce5b9`), held for R2.
  - **K3 synced (17:00):** 26 of Karan's 27 additions are committed on `content-fix` (platform 5 commits, businessworks 3, bw-plugin 1) for R2. Link check: 0 errors. **Held:** Hybrid Integration Connectivity Add-on 3.11.0 (PDF only). It is the only version of the Integration Platform family to migrate, and that family has no AEM repo. Decision for the user: ask Digital Platform for `en-us-tib-int-platform-userdocs`, or check with Karan.
  - **R1:** iProcess shows on staging (16:46). Fulfillment pushed to `wip` at 16:47 and showed by 18:55. **Data Management** pushed at 18:56 (`bcf95df`, about 1,050 files) has **still not shown at Sat 06:34**, 11½ h later: the probe page keeps its notes unlabelled. **R1 is held** (MFT, BPM, TRA, BusinessWorks) until it shows or Digital Platform says whether that build failed. **Sat 07:02 (user):** re-triggered with a small real change, the 8 online-help menu titles from "Online Help" to "<product name> <version>" (`0c6f0bd`). The user said to go on with the plan: **MFT** pushed at 07:03 (`5f38c6f`, about 1,450 files). Both are checked about 08:35; BPM next.
  - **Δ1 test refresh** (Fri, in batch-fixes, nothing written): **16 versions added** since 5 Nov, 0 new products, 6 in-scope versions now retired. The dry run does not name the 16; the real refresh on Mon 16 lists them for D7.
  - **Sat 07:30, agents (user: use the free resources):** (1) the menu title "<product name> <version>" in the converter and merge step, plus an in-place script for existing trees; (2) repair R002 for DOCOPS-360 (`\<` → `&lt;`, prose `\\` → `\`/`&#92;`) and the converter change; (3) and (4) triage of Batch 2, split by kind. All are read-only or on their own branches; nothing is published until reviewed.
  - **Sat 08:20, agent results:**
    - menu title merged (`6b41d78`), repair R002 merged (`0c48a15`), tests 502 passed;
    - Batch 2 triaged: entries merged (`e0cff51`) and 44 versions moved; TIBCO stands at 124 logged, 40 lost, 9 issues and 17 clean of 190 checked;
    - new issues DOCOPS-370 (ours, content directly inside a list dropped, 1 SP) and DOCOPS-371 (Digital Platform, `<samp>`/`<var>` dropped);
    - DOCOPS-346 widened (20 more versions, MFT, ActiveSpaces menu);
    - status page published (deployment @3).
  - **Sun 23:00: Δ1 TIBCO ready for R2, the first AI-assisted grouping.**
    - Flogo 3.0.2: 229 pages, median 623 words (1,340 under the old projection); 2.26.9: 254; CICS 1.5.1: 29. Drafts and reasons: `reports/ai-grouping/`. Entries are in `config/reframe.yaml` (`8ce7bc7`).
    - Older Flogo versions are still `already current`; CICS 2.5.0 rebuilt with the same 17 pages, so no regrouping.
    - Synced and committed on `content-fix`: Flogo `69d779d`, CICS `d6bffcd0`. **CICS 1.5.1 waits for Karan's yes before it is pushed.**
    - For review: Flogo's Activities reference page (12,091 words, kept whole like EMS's command list) and CICS Installation split per platform (one page is the alternative).
    - Follow-up: `levels.py` miscounts guides whose rows all carry `#fragment` (CICS).
  - **Sun 22:20:**
    - **Phase 81 merged** (`e1889a9`); the metrics script is now in `scratch/ai-grouping/levels.py`.
    - **Δ1 TIBCO all converted** (Flogo 3.0.2, 2.26.9, CICS 1.5.1) and their **ZIPs are on Drive** (checksums verified). An agent is drafting their AI depth grouping (`reports/ai-grouping/`); reframe follows its review.
    - **Staging checks scaled up:** Stage 2a/2b run 163 checks in 2 slots (the older TIBCO versions of the 17 families whose staging is current), about 4 h. That takes TIBCO coverage to about 300 of 610; the rest wait on Digital Platform (stalled builds, not served) and ibi on Mon.
    - **Found and fixed:** three batches at once hit `database is locked` in `state.db`, and the runner counted the crashes as findings. Now WAL mode, and a traceback marks a step FAILED (`eed302c`). **Stage 2b's 4 crashed checks must be re-run** after it finishes (delete their summary lines). The backup trigger also fired on the failed run's DONE and deleted a ZIP before the re-run; Flogo 2.26.9 was re-downloaded.
  - **Sun 22:00 (user decisions):**
    - **AI-assisted grouping is the default for all new and future versions**; older published versions are not regrouped (too expensive). Phase 81: a version with its own depth entries is laid out on its own even if the product is pinned (being built by an agent).
    - **Spotfire conversions are only Statistica and Data Virtualization**; the 14 new Spotfire Analytics versions are out of scope (already excluded by `config/scope.yaml`).
    - **Δ1 TIBCO conversion started** (Flogo 3.0.2 and 2.26.9, CICS 1.5.1; `cache/overnight/delta1-tibco.txt`). Their ZIPs go to the Drive backup once unpacked (user). The merge waits for the AI depth drafts.
  - **Sun 21:00:**
    - **370:** 55 re-converted versions synced and committed locally on `content-fix`, one commit per repo across 12 repos (597 files), for R2. validate showed no new errors; the BW plug-ins show only PUBLISH_NAME_TOO_LONG until their rename, and MDM's broken `Globalization-(G11n).md` link predates the sync. 16 versions are held for review (see 19:00).
    - **Batch 2b triaged** (`a98a94b`): 12 versions moved; TIBCO now 109 logged / 9 issues / 7 lost / 20 clean.
      - New issue DOCOPS-373 (DITA table descriptions dropped, 0.5 SP).
      - Placeholders inside bold are a DOCOPS-360 gap that R002 does not fix.
      - **Staging never rebuilt General and Foresight from Fri 13**, and serves Transaction Insight and FormBuilder at their menu path, not their folder path, so our redirects to the folder path 404. Both questions are in the Digital Platform chat message.
      - UAT rows: `reports/uat-sheet-rows-2026-11-15.csv` (3).
    - **Monday decisions added:** the two small converter gaps (DOCOPS-373, bold placeholders: R2 or after go-live), and Flogo 3.0.2 / 2.26.9 and CICS 1.5.1 under D7.
  - **Sun 19:00:**
    - **Staging has rebuilt nothing pushed since about 11:30** (EMS 10.5.1 still in its old menu at 18:50; Adapters still not served), so the next families are held. Asked Digital Platform (chat text in the session). Two more AEM-side items: links to the author host `author-p185304-…adobeaemcloud.com`, and Thiyagu's HTML link shows as plain code.
    - The two batches died together about 12:50 (cause unknown) and were restarted at 13:31; both DONE at 14:18. A memory-reaper kill of the wake-up timer lost 4½ h.
    - **Δ1 refresh done** (`0fb1df0`): 17 new versions (`reports/delta1-new-versions-2026-11-15.csv`). TIBCO: Flogo 3.0.2 and 2.26.9, BW plug-in CICS 1.5.1 (a Karan-list question); 14 Spotfire. **Flogo pinned to 3.0.1** so 3.0.2 cannot regroup published versions.
    - **Publish names for families not yet moved are switched off** (`4fc7dc0`). Otherwise a sync would create duplicate folders for the BW plug-ins, BusinessWorks, Platform and Streaming.
    - **370 re-conversion compared:** 57 of 73 have the same page list and are syncing locally. **16 are held for review:**
      - Service Grid 3.4.3/3.4.4: 23 pages renamed;
      - Control Plane 1.17/1.18 and Flogo 2.26.6/2.26.7/3.0.0: pages added or renamed by the fix;
      - Product and Service Catalog 5.1.0: 1,041 unfiled pages that the rebuild drops;
      - MDM 9.3.2/11.0.0: unfiled pages dropped;
      - BusinessWorks 5.16.1/6.12/6.13: one unfiled page;
      - Offer and Price Engine 6.0.0: 2 pages added (DOCOPS-349);
      - BE 6.3.1 and MDM 10.0.0: not published.
    - Batch 2b triage running (agent).
  - **Sun 11:33: EMS 10.5.1 new layout pushed to `wip`** (user: part of today's pushes; `4e31308`, 290 files, with the 10.4.0–10.5.0 fixes). Merged with Digital Platform's 12 `wip` commits: Thiyagu's Pulsar HTML-link fix now points at the new `transports-conf` page, and the Jakarta overview is folded as designed. validate 0 errors. `content-fix` holds `wip` again (`b139ebe`). Staging check about 13:30 (a new page: `c-and-cobol-reference/administration/tibemsqueueinfo.html`). Google re-auth done by the user.
  - **Sun 11:08:**
    - Batch 2b stalled: ActiveMatrix BPM 4.3.0 ran 14 h fetching pages one at a time. It was stopped, and steps 7–8 cleared to re-run.
    - **Speed-up merged** (`c40d244`): verify fetches 6 pages at a time and parses only `<main>`; catalog saves are lock-safe; `overnight.sh` runs up to 3 batches.
    - The speed-up agent died on Google re-auth (16 h rule), and overnight the memory reaper stopped the fix370 trigger and the Messaging timer.
    - **Now running in 3 slots:** Batch 2b (18 left), fix370 (147 steps), and the Messaging Phase 80 check.
  - **Sat 22:30: R002 committed locally in 23 TIBCO repos** (36,204 changes, 4,735 files; one commit per repo; idempotent; independently checked; script `8a0f8aa`). Not pushed: it waits for the `&#92;` check, and goes with R2 by the R2 plan's chunks.
  - **Sat 22:00:**
    - **R2 plan** written (`reports/r2-release-plan-2026-11-15.md`): about 47,000–52,000 files, 45 pushes Mon–Wed plus Δ1 on Thu. It fits if `&#92;` is confirmed Mon, 370 is committed Mon evening and ibi's refresh is on `wip` Mon. The BW plug-in renames go to R3 unless AEM answers by Tue.
    - **Repos where Digital Platform committed to `wip`:** EMS (12), Data Management (2), Streaming (2), all 8 ibi repos. So pushes go through a branch made from `origin/wip` that merges each chunk.
    - **EMS:** Thiyagu's 9 Nov hand fix replaced two `[`code`](link)` links with HTML links, because AEM's link resolver fails on links whose text is code. It clashes with our 10.5.1 relayout, so merge it and point it at the moved page. Ask Digital Platform whether such links fail site-wide (a common pattern).
    - Phase 80: Messaging pushed 22:00 by sha. ActiveSpaces needs no wait (only Silver Fabric moved, never served, DOCOPS-365).
  - **Sat 21:00 (user: use more agents):**
    - Phase 80 moves are committed locally for every non-BW family, each 0 errors in validate. Push by sha one family at a time: Messaging `bdca327`/`c4ffac8`, Adapters `bf9bd99`, Fulfillment `8415181`/`9dfe5ee`, MFT `fbfb772`/`796fe65`, BusinessConnect `4bad5b4`/`a88dca5`, General archives `ec07c55`, BusinessEvents archives `103d6eb`.
    - Agents: (1) R002 applied as local commits per TIBCO repo, without the census, which writes the catalog while a batch runs; (2) the R2 release plan (`reports/r2-release-plan-2026-11-15.md`), with chunks of ≤2,500 files and pushes by sha.
    - The fix370 batch also re-converts 5 versions whose API links name old folders.
    - Found: the Messaging archives page now links old versions to ZIPs on docs.tibco.com, which stop working on 30 Nov. Kept out of the commit; it needs a decision on archive links after shutdown.
  - **Sat evening:**
    - Phase 80: Hawk serves at its new folders (verify, 20:25). **ActiveSpaces pushed 20:31.**
    - DOCOPS-370 fixed and merged (`42e7c31`; the cause was Flare's list merge). **68 versions to re-convert** (`reports/fix-370-affected-2026-11-14.csv`); queued to run after Batch 2b (`cache/overnight/fix370.txt`, 136 steps), then compared with published before any sync.
    - DOCOPS-371 fallback ready, switched off (R003 optional, 37,002 elements).
  - **Data Management on staging (Sat ~19:15):** Thiyagu's centralised incremental build worked. The probe page shows labelled notes and "Last published: Nov 14, 2026", so R1 is complete for Data Management. **But** the menu panel heading still shows the folder name, not our new `docs_list_title` ("ibi™ MDM Add-on ... 4.0.0"). Ask Digital Platform where that heading comes from before rolling the menu-title script out in R2.
  - **Data Management cause (AEM team, Sat evening):** the GitHub repo names contain an underscore (`en-us-tib-data_management-userdocs` and `-resources`, from our family id `data_management`), and the Cloud Run build accepts hyphens only. No other TIBCO or ibi repo has one. AEM is checking whether they can lift that restriction. **Fallback if not:** rename the two GitHub repos to `data-management` (GitHub keeps redirecting the old name), and rename our family id to match (taxonomy, the catalog's `_family` column, the workspace family folder). That needs a GitHub admin, and it is small on our side.
  - **Done (user: "lets do it", Sat ~19:00):** both repos renamed on GitHub to `en-us-tib-data-management-userdocs` and `-resources` (this account has admin; GitHub redirects the old names). Local remotes updated. Our tool needs no change: the local folders were already hyphenated (`slug.family_workspace_folder`). **Not pushed:** Digital Platform (Thiyagu) is testing incremental builds on this repo's `wip` (probe commits 8451e0f at 14:01 and ccabb06 at 18:21, each an HTML comment). `content-fix` must merge `origin/wip` before its next push, so their probes are not overwritten.
  - **Phase 80, by family (user, 14 Nov):** the BW plug-ins wait until Digital Platform confirms they cannot lift the 50-character limit. The other families go one at a time, each after the previous shows: **Hawk pushed 18:28** (`c141736`, resources `14e8e4f`); then ActiveSpaces, Messaging, Adapters, Fulfillment, MFT, BusinessConnect, and the General/BusinessEvents archives. BusinessWorks, Platform and Streaming go with R2 (their repos carry R2 commits).
  - **Phase 80 built and merged (17:00, `e13de8a`, `18f8f32`):** publish names for 116 products (108 approved, plus 8 archive-only found by the build, named by the same rules). Sync, redirects, help IDs, verify and repairs use them, and validate guards the 50-character limit. The move script's dry run: **172 folder moves in 19 repos, about 25,400 files** (BW plug-ins 18,500). **Pipeline plan:** the moves are `git mv` on `content-fix` (local, no pipeline). `wip` gets them in chunks of about 10 products (about 2,500 files), each after the previous shows, so the BW plug-in repo needs about 8 chunks. Start early: proposed Sun 15 moves, Mon 16 onwards chunks.
  - **R1 TIBCO done (15:53):** BPM shows on staging (fresh check: 0 unlabelled notes, 60 before). Every TIBCO repo is through R1 except **Data Management** (build stuck, with the AEM team). The BW plug-ins and MFT are on `wip` but held back by the 50-character limit (Phase 80). Streaming is held. **ibi: Mon 16.** Batch verify lines now always use `--refresh`: Batch 2 read cached pages for 4 versions.
  - **Go-live blocker found (14:00, from the AEM team):** staging cuts product folder names after 50 characters. 92 TIBCO products (250 versions) are served at shortened addresses, and 24 of them share an address in 8 groups (7 with the same version number, so one overwrites the other). This explains most of DOCOPS-346. Only 9 versions are genuinely not served. Redirects, cross-links and help IDs use the full name. UAT rows: `reports/uat-sheet-rows-2026-11-14.csv` (6 rows). **Decision D8 (user + Digital Platform):** AEM keeps full names, or we shorten our folder names. **Reported to the AEM team by the user (Sat 14 Nov afternoon)**, with the Data Management and MFT build questions; waiting for their answer. **D8 decided (user, 14 Nov afternoon): we shorten the names (Phase 80, DOCOPS-372, 1.5 SP)**, as AEM is not expected to lift the limit. That is 108 products: the 92 over 50 characters, plus the rest of the BW plug-ins for one `tibco-bw-plugin-...` scheme. Names: `reports/url-names/proposal-2026-11-14-v2.csv`. Build started Sat with a helper agent; apply Tue/Wed on `content-fix`; out with R2 (Thu 19).
  - **R1, 13:12:** BusinessWorks showed (notes labelled on 6.12.0). **BPM pushed** (`ad26093`, the last TIBCO group). Data Management is still stuck (old pages at 13:11). Left for R1: Data Management (Digital Platform), ibi (Mon 16), Streaming (held).
  - **R1, 10:45:** TRA showed within 2½ h, so staging builds normally and the Data Management build alone is stuck (old pages at 10:43, 16 h after the first push). Message to Digital Platform is with the user. **BusinessWorks** was pushed (pre-K2) at 10:43; **BPM** follows once it shows.
  - **R1, 13:20:** **BusinessWorks shows** (its probe page has the "Warning:" label). **Data Management still old** (the GDS 4.0.0 note has no label), 18 h after the first push. **MFT is not served at all** (404 on Internet Server 8.7.1 and Command Center 8.6.0/8.7.1; Batch 2 found 977 pages "version not served"), so it cannot show a rebuild: add it to the AEM "not served" items with DOCOPS-346. **BPM** is ready to push (fast-forward of 3 pre-K2 commits, `ad26093`); the push needs the user's approval.
  - **R1:** TRA was pushed (pre-K2) at 08:11. BPM (2,072-file commit) is held until Data Management or MFT shows; BusinessWorks (pre-K2) follows TRA. Data Management had still not shown at 08:22.
  - **Open questions for the user (Monday):**
    - pictures in dot folders: Digital Platform fixes the DAM, or we rename the folders;
    - `.wmf`/`.emf`/`.bmp`/`.dib`: convert to PNG, or accept;
    - remove the DOCOPS-347 catch-all after Batch 3;
    - the list fix (370) in R2;
    - accept the "nested under the guide page" menu moves;
    - `<samp>`/`<var>`: wait for AEM, or write other tags.
  - **Batch 2 done** (Fri 23:03): 100 checks, 60 with findings. Errors by kind are in `reports/verify/batch2-prep-2026-11-14.md` for Monday.
  - **DOCOPS-360, second case (user's spot check, 13:30):** a backslash in normal text shows doubled on staging (`Systems\\ArchiverDemo`); in code text it is fine. About 11,600 occurrences on about 1,970 TIBCO pages. Test page pushed to `wip` (Foresight 6.0.0 "General Configuration After Installation", 53c7ee8). Once it and the FTL `&lt;` page show on staging, one in-place repair covers both cases for R2, plus a converter change. **UAT sheet row:** add it once the test result is in.
  - **DOCOPS-343 follow-up:** the first fix broke one EMS link per version. It is fixed (`9718ae6`), and EMS 10.4.0–10.5.1 are re-converted and committed per version on `content-fix` (R2). The link check has 0 errors.
- **Decided:** Phase 78 approved (EMS 10.5.1 pages by menu depth; build Mon 16, out with R2). UAT rows pasted.
- **K1 done:** Karan's decision is in the catalog for all 1,166 versions, each checked afterwards (DOCOPS-364).
- **R1 is paused after 2 of 5 groups.** Groups 1 (Scribe, Messaging, Cloud, Hawk, ActiveSpaces) and 2 (Adapters, Mainframe, Platform, BusinessEvents) are on `wip`.
  - **Correction, 03:20: staging shows neither group after about 2 hours.** On fresh fetches, Cloud API Modeler 1.5.0 still has 24 notes without a label and Control Plane 1.18.0 has 203. The earlier "Cloud updated" reading was wrong.
  - **R1 is stopped** until Digital Platform says how staging builds from `wip`: on each push, on a schedule, or by a manual trigger, and how long a repository takes.
  - **Question for you to send to Digital Platform (morning):** "We pushed `wip` for 9 TIBCO repos at about 01:00 on 13 Nov (Scribe, Messaging, Cloud, Hawk, ActiveSpaces, Adapters, Mainframe, Platform, BusinessEvents). Staging still serves the older pages at 03:20. How and when does staging rebuild from `wip`, and is a build queued or failed?"
  - Not yet merged:
    - TIBCO medium: General, FTL, TRA, Foresight, Flogo, BusinessWorks, iProcess, BusinessConnect;
    - TIBCO large, one at a time: Fulfillment, Data Management, MFT, BPM;
    - ibi: 7 repos.
- **Tonight (the batch is running):** K3 downloads and unpacks Karan's 27 additions, then Statistica is re-checked with the fixed checker. **Batch 2 (TIBCO newest) and Batch 3 (ibi newest) move to after R1 is visible on staging**, so they do not check stale pages.
- **Built and merged today:**
  - the status page (`reports/conversion-status.html`, `reports/status-latest.md`);
  - two more checker fixes (DOCOPS-366: Statistica's 14,025 false "missing" pages are now 1 real gap).


---

## 1. Why the last week felt like running in loops

- **One command at a time.** Every check was a command you started, watched and reported back on before the next one. On 583 versions, that is several hundred hand-offs.
- **New problems traced the same day.** Each check turned up a new kind of problem. It got traced and logged that day, so the next check waited and the day's plan changed.
- **One queue for everything.** Fixes, merges, backups, messages to other teams and new requests all came in together, with nothing saying which comes first.

## 2. How we work from now on

**Three lanes, each with its own owner.**

| Lane | Who | What runs there | Rule |
|---|---|---|---|
| **A: machine** | Claude starts it; nobody watches | Batches of checks, overnight; named download, unpack and conversion runs | **One run at a time.** All runs write the same status files, so a lock refuses a second batch. A batch is a list of short runs, one product each. It keeps going past failures, resumes where it stopped if restarted, and leaves one summary file. |
| **B: agents** | Claude, with parallel helper agents | Reading the night's results and tracing new problems (one agent per family, read-only); building fixes (one agent per Jira issue, each in its own copy of the code, with tests) | Agents never write to the shared folders or the published repos. Claude brings their work together and checks it before it goes anywhere. |
| **C: you** | You | Signing in each morning, decisions, approving merges, messages to other teams | One 15-minute slot each morning, from **Today**. At most three decisions a day. |

**Two machine limits the lanes are built around.**

- **Memory runs low overnight.** A long check holds every finding in memory until it ends. So a batch is now one short run per product, and each run gives its memory back when it exits. Before each run, the batch checks free memory. Under 3 GB, it waits up to 30 minutes and notes the wait in the summary. Nothing heavy runs beside a batch: no agents, no conversions.
- **The Google sign-in lasts 16 hours.** Claude and its agents stop working when it lapses. The batches do not, because they read only public sites (staging and docs.tibco.com). So:
  - all night work is a batch started in the evening;
  - nothing at night depends on Claude;
  - each morning starts with you signing in again, then Claude reads the night's summary.
  - Anything that writes to Google Drive is started right after a sign-in, and must finish within 16 hours or be able to resume.

**Rules against spiralling.**

1. **One focus per day**, as in the calendar below.
2. **A problem found by a check is logged, not chased.** The morning triage gives it a Jira issue, and it gets fixed in a planned fix window, never the same day.
3. **A new request goes to the parking lot (§5) with a date.** Only a go-live blocker jumps the queue. A go-live blocker means a reader of the newest version cannot find or read a page.
4. **Merges to `wip` happen only in release windows** (R1–R4). Within a window they are **spread out**: a group of about five repos at a time, and the next group only once staging shows the previous one rebuilt.
5. **You get one note a day:** what ran overnight, what was found, and what is decided next.

## 3. Calendar

Machine time: about 5 minutes per version checked.

| Day | Focus | Lane A: machine | Lane B: agents | Lane C: you |
|---|---|---|---|---|
| **Thu 12** | Plan | Day: **Batch 1**, BW plug-ins, newest versions; 26 of 80 could be checked. Night: **Batch 1b**, download and unpack the BW plug-in packages again, then check the newest versions Batch 1 skipped. | – | Done |
| **Fri 13** | **Release R1** | Day: first, **K1**: Karan's list written into the catalog (§6). Then R1 in four spread-out groups, each after the previous shows on staging: TIBCO small families; TIBCO middle families; TIBCO large families and the four already checked (FTL, Cloud, BusinessEvents, Scribe); ibi (7 repos, 4 with `wip` commits of their own, merged properly). Night: **Batch 2**: the 27 additions from Karan's list downloaded and unpacked (K3); then the TIBCO newest versions, without Karan's "do not migrate" ones, and the 20 re-checks, about 11 h. Then **Batch 3**, ibi newest (22), about 2 h. Statistica and EMS 10.4.0 were done on Thu 12. | Triage of Batch 1 and 1b; UAT sheet rows for the open AEM items (§8); **status page** built during the merge waits (§8b) | Sign in. Paste the new rows into the UAT sheet. |
| Sat 14 – Sun 15 | **TIBCO pulled forward** (user, Sat 19:15) | Sat night: **Batch 2b**, newest TRA, BusinessWorks, BPM and Data Management, plus re-checks of FTL, eFTL, Cloud API Modeler, Scribe, Transaction Insight, Enterprise Administrator and iProcess Workspace, all with `--refresh` (24 checks). Sat–Sun: **Phase 80 by family**, one push at a time as each shows: Hawk (out), ActiveSpaces, Messaging, Adapters, Fulfillment, MFT, BusinessConnect, then the General and BusinessEvents archives. Sun: **Δ1, the real catalog refresh** (from Mon), giving the list of new versions for D7. Then **repair R002** applied on `content-fix` for the TIBCO repos already moved (local; pushed with R2 once `&#92;` is confirmed). If approved, the re-conversion for DOCOPS-370. | Sat: an agent builds the **DOCOPS-370** fix (content inside a list) and the **DOCOPS-371** fallback (`<samp>`/`<var>`, off by default), with measurements. Sun: triage of Batch 2b. | Look at the Foresight `&#92;` row when you can |
| **Mon 16** | **Triage; R2 opens** | Day: confirm `&#92;`; ibi R1 after Digital Platform's refresh (fetch first, merge their `wip` commits); **Δ1**, the catalog refresh (its test run was done Fri: 16 new versions); R2 pushes begin by the R2 plan (`reports/r2-release-plan-2026-11-15.md`): ≤2,500 files per push, ≤3 repos in flight, a merge branch from `origin/wip` where others committed; commit the 370 re-conversions after comparing them with what is published. Night: Batch 3 (ibi newest), several batches at once. | Triage of Batches 2b and 3 | **D5** extended (370 in R2), **D7** (Δ1 list), D8/D9 answers from AEM, Streaming R2 or R3 |
| **Tue 17 – Wed 18** | **R2 pushes, fixes, delta** | R2 chunks continue (R002 repair, Karan's removals and additions, Platform and BusinessWorks from the finished tree, Phase 80 renames for BusinessWorks/Platform); Δ1 and Δ2 versions converted and merged; the BW plug-in renames only if AEM has answered by Tue morning (otherwise R3) | Fix agents for new kinds | Nothing, unless an agent finds a design question |
| **Thu 19** | **R2 complete** | Day: Δ1 pushes and re-pushes; last wave by 17:30. Night: **Batch 4**, re-check what R2 changed, plus the 250 renamed versions. | – | One yes or no: R2 complete; what is left moves to R3 |
| **Fri 20** | **Go / no-go** | – | Triage of Batch 4 | **Go / no-go** against §4. **D6:** the 82 TIBCO versions with no package on the old site. |
| Sat 21 – Sun 22 | Buffer | Re-runs if needed | – | – |
| **Mon 23** | **Go-live** | – | – | – |
| **Mon 23 – Wed 25** | Stage 2 | Nights: **Batches 5–6**, older TIBCO versions outside BW plug-ins (about 154), including the comparison with the live old site | Triage | AEM follow-ups |
| **Thu 26** | **Release R3** | Day: R3 (Streaming, anything held from R2, including additions that did not convert cleanly). Night: **Batch 7**, check them. | – | Approve R3 |
| **Fri 27 – Mon 30** | Old-site close | Fri 27: **Δ3**, the last catalog refresh; that night, its packages are downloaded and backed up. Collect old addresses for help with no redirect map (DOCOPS-322, 279), while the old site is up | Triage | Close the backups (DOCOPS-281, 283); confirm nothing else is needed from the old site |
| **Early Dec** | **Release R4** | Δ3's new versions and late hand-supplied ZIPs, converted and published | – | Approve R4 |
| **After 30 Nov** | Stage 3 | Older BW plug-in versions still published after Karan's removals (on disk after Batch 1b), older ibi (178), Statistica (24); Streaming once AEM serves it | Fixes left from §4 | – |

If go-live moves to 25–26 Nov, the calendar shifts by those days. R2 still lands three days before go-live.

## 4. Go / no-go on Fri 20

Ready when:

- Every newest version (TIBCO without Streaming, ibi, Statistica) has a check result, and every finding is logged, explained or clean.
- No go-live blocker is open on our side. AEM-side items (344, 345, 346, 351, 353) are reported, with the AEM team's answer noted.
- Redirect maps are loaded by AEM (DOCOPS-271), or the AEM team has said when they will be.
- The BW plug-ins missing from staging (DOCOPS-346, 61 versions) are served, or Digital Platform has a date for it.

## 5. Parking lot (dated, not now)

| Item | Slot |
|---|---|
| **Merge rule:** all-or-nothing siblings was measured and rejected (pages more than double). **The user chose pages by menu depth instead, EMS 10.5.1 first** (Phase 78, DOCOPS-367): 214 pages for 10.5.1 (159 today), older EMS versions unchanged. Waiting for approval of the Phase 78 plan; the build is Mon 16, and 10.5.1 goes out with R2 as one commit (about 400 files). | Approval Fri 13; build Mon 16 |
| Writers' draft comments published in the original help ("Draft comments:"; 16 versions, 7 families; `source`): drop them in conversion? | Writers, after 30 Nov |
| Statistica 14.4.0 text findings: most are Greek letters the source double-escapes (`&amp;alpha;`, so the old site showed the literal code, and our page shows the letter): `source`. To check as possibly real: `_templates/Whats-New.md` (25 sentences) and `itrees-results-manager-tab.md` (3). Data Virtualization: 81% of its old findings are cleared by the 12 Nov checker fix. | **Last priority**, after TIBCO and ibi (user, 13 Nov) |
| FOCUS 9.3.4 publishes Flare's generated `_globalpages` pages (contents, title): found by the DOCOPS-349 fixer, our converter | Triage, Fri 13 (fold into an existing issue or a new kind) |
| Spotfire backup run summary → close DOCOPS-283 | Whenever you paste it, by Fri 27 |
| ibi: confirm the 18 hand-obtained PDF-only versions are on Google Drive → close DOCOPS-281 | By Fri 27 |
| Streaming `content-fix` (its `wip` has its own commit, so a real merge is needed) | R3 |
| Doubled headings in 38 products (DOCOPS-336) | D5 decides R2 or after 30 Nov |
| Team requirements (DOCOPS-355–359) | Owned by those teams; notes when they move |
| PDFs, translated help, search, help-button links, layout and browser checks | After 30 Nov |

## 6. Karan's list: what Integration publishes (engineering request, D3)

**The source.** `cache/Integration Products migration to new docsite - versions.csv` lists 1,166 versions of the Integration families:

| Family | Versions |
|---|---|
| BW plug-ins | 661 |
| BusinessWorks | 177 |
| Cloud | 129 |
| Integration Platform | 114 |
| TRA | 55 |
| Platform | 30 |

**The rule.** For every version on this list, **"Karan's decision" is final** (user, 12 Nov). It wins over our own migrate column, over the support report's retirements, and over what is already published. Karan changed the earlier column on 44 rows.

**Against what is published today.** The full list is `reports/karan-decision-changes-2026-11-12.csv`.

| Change | Versions | Which |
|---|---|---|
| **Add:** migrate, never published | **27** | Control Plane 1.3.0–1.17.0 (16); Platform 1.0.0, 1.1.0; BusinessWorks 6.11.0, 5.15.1, 5.15.0; SmartMapper Enterprise Server 6.0.0, 6.0.1; BWCE 2.10.0; Hybrid Integration Connectivity Add-on 3.11.0; and 2 versions **retired** in the support report: BW plug-in for CICS 2.4.1 and for Files 8.2.0 |
| **Remove:** published, but do not migrate | **80** | BW plug-ins 64 (the 25 held for engineering since 2 Nov are among them); TRA 11 (Runtime Agent 5.12.2 and 5.12.3, Administrator 5.12.2, Designer Add-in 1.0.0–1.5.0); BusinessWorks 3 (BusinessWorks Enterprise 3.10.0 and 3.11.0, the AWS Marketplace subscription 2.3.1); Cloud 2 (BusinessWorks and Flogo pay-as-you-go 2.8.0 and 2.11.0) |
| Already as decided | 1,057 | – |

**Where the packages are.** 25 of the 27 additions are in the TIBCO backup and on the old site. The 2 retired ones are in neither the backup nor the local files, so they must come from the old site before 30 Nov.

My guess of 33 older BW plug-in versions is dropped: Karan marks all 33 "do not migrate".

**Steps (Jira first: one sub-task for the whole list):**

| Step | When | What |
|---|---|---|
| K1 | Fri 13, before R1 (no batch running) | Karan's decision written into the catalog's `migrate_decision`, as a manual decision a refresh cannot undo, with the selection to match. Retirement overridden for CICS 2.4.1 and Files 8.2.0. The batch builder skips "do not migrate" versions from then on. |
| K2 | Mon 16, day | The 80 removed from `content-fix`, the way DOCOPS-316 did it (version folders, version lists, redirect maps). Goes out with R2, so they are gone before go-live. |
| K3 | Fri 13, night | The 27 additions downloaded and unpacked, at the start of Batch 2 |
| K3 | Mon 16 – Tue 17, day | Converted, pages merged, published to `content-fix`. Out with R2 (Thu 19) and checked in Batch 4. If a version does not convert cleanly, it moves to R3 (Thu 26) and is logged. |

**Found 12 Nov (published BW plug-ins).** 184 of the 253 published BW plug-in versions had no unpacked original on this machine. The TIBCO backup run deleted the packages after uploading them, and their unpacked folders were gone as well. Every other TIBCO family is complete.

Without the originals, these versions cannot be checked, now or after 30 Nov. Batch 1b downloads all of them again from the old site: about 2 GB, with 63 GB free. The 3 retired Facebook and Twitter versions are not held anywhere.

## 6a. Delta migration: what was released since the last catalog refresh

**Why.** The catalog was last refreshed from docs.tibco.com on **5 Nov** (DOCOPS-333). Versions released since then, and releases still being written, are not converted.

**The limit.** A refresh reads the old site, so **the last possible refresh is before Mon 30 Nov**. After that, a new release can only come in as a ZIP supplied by hand, until the publishing pipeline is joined to the product builds (DOCOPS-359).

**Three passes:**

| Step | When | What |
|---|---|---|
| Δ1 refresh | Mon 16, day | Catalog refresh, first as a test run that lists what is new without writing anything: new versions and new products since 5 Nov, all BUs. The list goes in the morning note. Then the real refresh, with the end-of-support report re-applied. |
| Δ1 runs | Mon 16 night, then Tue 17 – Wed 18 | Download and unpack the new versions in the Mon 16 night batch; convert, merge and publish them to `content-fix` with K3 and the fixes. Out with R2 (Thu 19), checked in Batch 4. |
| Δ2 in-progress releases | ZIPs by **Tue 17, noon** for R2; later ones for R3 (Thu 26) | Releases whose documentation is not yet on the old site. You collect the ZIPs from the writers into `cache/manual-zips/` (one file per version, product and version in the name). Claude files each one as hand-supplied, so a later refresh cannot replace it. A new version of a known product gets its catalog row added on the way in. A brand-new product needs its catalog entry first. Then the same convert, merge and publish steps. |
| Δ3 final refresh | **Fri 27**, day; packages that night | Last refresh while the old site is up. Everything new since Δ1 is listed, and that night's batch downloads its packages to disk and adds them to the TIBCO backup, so they survive the shutdown. Converted and published in **R4** (early December), with nothing waiting on the old site. |
| After 30 Nov | Ongoing | New releases only as hand-supplied ZIPs (the Δ2 path) |

**Rules for what a refresh finds:**

- A new version is selected as usual: an active version converts, an archived one does not, a retired one is skipped.
- A new version of a product on **Karan's list** is not covered by his decision. It is selected by default, because it is the current release, and goes on a short list for Karan to confirm. If he says "do not migrate", it is removed in the next release window.
- A refresh never undoes a manual decision: Karan's, the retirement overrides, or the migrate column.
- A refresh writes the status files, so it runs only when no batch is running.

## 7. Decisions

| # | Decision | Answer |
|---|---|---|
| D1 | How `content-fix` reaches `wip` (R1: 20 TIBCO and 7 ibi repos) | **Claude merges, spread out** in groups of about five, each after the previous rebuild shows on staging; fetch first; Streaming held to R3 (user, 12 Nov) |
| D2 | Claude starts the calendar's runs, keeps going past failures, and reports in the morning | **Yes** (user, 12 Nov) |
| D3 | Which Integration versions to publish | **Karan's decision is final** for the 1,166 versions on his list: 27 to add, 80 to remove, both before go-live (§6; user, 12 Nov) |
| D4 | Parallel agents for triage and fixes | **Yes** (user, 12 Nov). Not while a batch runs (memory). |
| D5 | Which fixes go into R2 | **All of them** (user, 12 Nov: "go ahead with the remaining suggested fixes"); weekend fixes included (user, 14 Nov: "fixes if required"): R002 (360), the list fix (370), Phase 80 renames. 371's fallback stays off unless AEM cannot keep `<samp>`/`<var>`. |
| D6 | The TIBCO versions with no package on the old site: 82 on 12 Nov. **13 Nov:** 23 uploaded by hand (checksums verified), 29 marked not required by the user; **33 left** (`C:/tmp/handzips/still-missing.csv`). 30 are for the user to obtain; 3 BW plug-in additions (K3) have never been tried, so the backup script fetches them after batch-fixes ends (it deletes workspace ZIPs). | Fri 20 |
| D7 | Delta before go-live: which new versions from Δ1 go into R2, and the cut-off for hand-supplied ZIPs | Mon 16, from the refresh list. Recommendation: all of Δ1, and ZIPs received by Tue 17 noon; anything later goes in R3 (§6a). |
| D8 | AEM cuts product folder names after 50 characters | **We shorten them (Phase 80, DOCOPS-372)**, as AEM is not expected to lift the limit (user, 14 Nov): 116 products, the whole BW plug-in family included. Non-BW families renamed one family at a time from Sat 14. **BW plug-ins wait** until AEM confirms it cannot lift the limit (user, 14 Nov). |
| D9 | Data Management's repo name has an underscore, which Cloud Run rejects | **Renamed both repos to hyphens on GitHub** (user, 14 Nov: "lets do it"); the build then went through. |
| D10 | EMS 10.5.1's new layout before R2 | **Pushed Sun 15** (user: part of the weekend's pushes) |

## 8. Reporting a problem: Jira and the UAT sheet

Every kind of problem found in testing goes in two places.

- **Jira (DOCOPS)** is our own tracker. There is one sub-task per kind, as Phase 77 set up, and the triage file links each finding to it.
- **The UAT sheet** ("TIBCO_IBI_Spotfire UAT Sheet", Tibco UAT tab; export `cache/TIbco_IBI_Spotfire UAT Sheet - Tibco UAT.pdf`) is what you report from. It gets every problem with the **site, the pipeline or AEM**.

**What triage hands you.** Each morning's triage writes `reports/uat-sheet-rows-<date>.csv` with the sheet's own columns, ready to paste. It covers only kinds not already in the sheet.

| Column | What triage fills in |
|---|---|
| Type | Desktop or PDF |
| Issue description | What is wrong, an example heading or page, the staging URL, the GitHub URL, and "Related issue #…" where the sheet already has one |
| Category | Design or Content |
| Priority | Critical, High or Medium |
| Found In | Product and version |
| Reporter | Mayur |
| Status | New |
| Stage Issue link | The staging URL |
| Comments | The Jira key, and how many versions and pages are hit |

You add the screenshot and the assignee. After pasting, tell Claude the row numbers, and they go into the Jira note.

**Mapped so far:**

- The sheet's anchor rows (comma, colon, brackets, slash, en dash, repeated heading, `<`) are DOCOPS-345 and 353.
- The Streaming row is DOCOPS-346.

**Not in the sheet yet; first batch of rows on Fri 13, replacing the separate AEM report:**

- DOCOPS-344: pages shown nearly empty.
- DOCOPS-351: pages under a heading row hidden from the menu or not found, which is the 96-page list in `reports/verify/aem-content-missing.csv`.
- The lowercase-anchor case of DOCOPS-345.
- The questions on duplicate menu entries.

## 7a. Fixes built for D5 (Mon 16)

**Status 12 Nov evening (user: "go ahead with the remaining suggested fixes"):**
- All five branches are merged into the tool. The full suite passes: 2,507 tests.
- **Applied:**
  - DOCOPS-354: 7 of 8 versions re-published on `content-fix`; they go out with R1 on Fri 13.
  - The `&lt;` test page: FTL 7.3.0, Persistence Status Objects, also with R1.
  - The checker fix, live from Batch 2 on.
- **Still to apply:**
  - 349 and 343/362/363: re-convert Mon 16 – Tue 17, out with R2.
  - 360: an in-place repair or re-convert, once the test page reads right on staging.

~~Each fix sits on its own branch with tests. Nothing is merged or re-converted until D5.~~ When merging: `fix/ftl-301`, `fix/anchors` and `fix/verify-bw` each add a finding code (the register count conflicts), and `fix/anchors` and `fix/angle-brackets` both touch `utils/anchors.py`. Merge them one by one, and run the full suite after each.

| Jira | Branch | What it fixes | Re-run to apply |
|---|---|---|---|
| DOCOPS-349 | `fix/default-htm` (71378d4) | Real pages named `default` / `index` below the help root were dropped | EMS 10.4.0–10.5.1 (6); ibi WebFOCUS Client 9.3.0–9.3.8 (with 9.3.5's translations); ibi FOCUS 9.3.0–9.3.8. One page each. |
| DOCOPS-354 (applied to all 8; Flogo 2.26.8 with SQL Direct kept separate, version-scoped) | `fix/ftl-301` (4045308) | Cause was old data: FTL/eFTL 7.1.3 were merged before the old site listed their pages, and never rebuilt, so their redirect files hold no pages. The branch adds a publishing warning so this cannot pass silently again. | **No re-conversion:** re-merge and re-publish FTL and eFTL 7.1.3, Flogo 2.26.8 and 3.0.1, and 4 BusinessConnect Container Edition versions. 6 more versions need URL patterns first (DOCOPS-322). |
| DOCOPS-360 (and most of 353) | `fix/angle-brackets` (d9b71f9) | `<` in text was written as `\<`, which AEM shows as `\&lt;`: placeholders like `<host>` read wrong in prose, lists and headings on hundreds of pages (FTL 7.1.1 alone: 575). Now written as `&lt;`; menu paths escaped; anchors unchanged. | First confirm on staging that `&lt;` in plain text shows as `<` (a one-page test, riding R1). Then either re-convert the affected families, or, much cheaper, a new in-place repair of the published pages (R002, not built; about half a day). |
| DOCOPS-343, 362, 363 | `fix/anchors` (f87b912, 248c4c1) | Links to headings containing code pointed at a wrong, dashed target; EMS caption bookmarks running over several lines cut pages short on staging. Heading targets are now read from the heading as written; split bookmark names are not written; `validate` reports both. BusinessEvents figure/GUID links point at bookmarks the source never had: triaged `source` (Claude, 12 Nov; reversible). | EMS 10.4.0–10.5.1 (6): convert, merge, publish. Links to headings with code: convert and merge each affected version (Flogo PAYG 2.11.0, BE 6.3.2 and 6.4.0 measured; a per-version count chooses the rest). |
| DOCOPS-366 (checker) | `fix/verify-bw` (571e526) | Four false findings in the check: bookmarks on a page's own heading; DITA's legal page moved last; `<var>`, `< x >` and fences in list items. Plus a new error when a version's whole menu was lost. Measured on the 73 BW plug-in versions: 83 false findings gone, 2 real errors raised (the SAP versions of DOCOPS-365). | **Merged 12 Nov** (user: go ahead). Delete its 8 triage entries after Batch 2 re-checks those versions. No content change. |

## 8a. Jira guardrails (user, 12 Nov)

Claude creates, updates and closes Jira issues itself, within these limits.

1. **One issue per workstream or per kind of problem**, never one per step, run, batch or release. Steps, runs and releases are dated notes on the issue they belong to.
2. **A new issue only for:**
   - a new workstream of at least 2 hours of work;
   - a new kind of problem found by a check (the Phase 77 rule);
   - a team requirement.

   Anything else is a note.
3. **Story points measure Claude-assisted effort** (1 = 8 h, 0.25 = 2 h, the smallest step):
   - on sub-tasks only;
   - nothing for machine time or waiting;
   - most sub-tasks 1 or less;
   - changed at close only if off by 0.5 or more.
4. **Close as soon as the issue's exit is met**, with a closing note; Canceled if it is overtaken.
5. **Expected new issues to 30 Nov:**
   - DOCOPS-364, Karan's list (created 12 Nov, 1 SP);
   - one for the delta migration, covering all three passes (§6a), created when Δ1 runs;
   - one per new kind of problem from triage.

   Fixes are noted on the existing issues (343–363). Releases R1–R4 are notes on DOCOPS-313 and on the issue each release carries. More new issues than these needs a reason in the morning note.

## 8b. Where we stand: one status page (user, 12 Nov; built 13 Nov)

**Why.** When anyone asks, you need one place that says where the migration stands, how much is left, how much effort went in and is left, and which team owes what. Today that is spread over a dated report (`reports/migration-status-2026-11-12.md`, stale the next day), the per-version page (`reports/conversion-status.html`), Jira and this plan.

**What.** A first tab, **"Where we stand"**, on `reports/conversion-status.html`, plus a short text copy, `reports/status-latest.md`, to paste into an email or chat. Both are rebuilt every morning in the triage step, and both carry an "as of" time.

| Part | Shows | Read from |
|---|---|---|
| Headline | Days to go-live and to the old site's shutdown; versions migrated, published and checked on staging, each against its total | `versions.csv`, `state.db` |
| Areas | One row per area: migration (conversion), publishing, staging checks, problems found, Karan's list, delta migration, redirects, backups, team requirements, translated help, writer spot-checks. Each row gives status (done / on track / at risk / blocked), done and left, the responsible team, the next date, and its Jira issues. | Counts from the catalog and the check results. The rest from a small hand-kept file, `config/status-areas.yaml`: per area its name, team, Jira keys, plan section, next date and one-line status. Claude updates it with the morning note. |
| Effort | Story points done, in progress and to do per area and in total; the time since the first issue | The DOCOPS snapshot (`fetch_docops.py`), by the areas' Jira keys |
| Pending by team | What each of the three teams owes, with dates (user, 12 Nov). **TechDocs** (us): our fixes and runs, writers' spot-checks and in-progress ZIPs, and the open decisions D5–D7. **Digital Platform**: the AEM site and staging problems, UAT sheet rows, redirect loading, and the PRISM integration. **Engineering**: Karan's Integration decisions; the product teams (Messaging, iProcess, Streaming, Scribe); support's end-of-support reports. | A problem kind's owner from its triage decision (`platform` = Digital Platform; ours and `source` = TechDocs); open Jira issues by area; the decisions table in this plan |

**Built by** a helper agent in its own copy of the code, during the waits between the R1 merge groups on **Fri 13**. Claude reviews it before it is merged. It only reads; it changes nothing in the catalog or the repos. Jira: a note on DOCOPS-280 (Phase 65 built the page), no new issue; 0.5 SP added there if it takes over 4 h.

**Each morning (after sign-in), Claude:**
1. Updates `config/status-areas.yaml` from the night's results: status, next dates.
2. Runs `.venv/Scripts/python scratch/fetch_docops.py`.
3. Runs `.venv/Scripts/python scratch/build_conversion_status.py`.
4. Runs `scratch/publish_status.sh`: copies the page to `C:/github/apps-script/report.html`, `clasp push`, and moves the shared web-app deployment ("TIBCO++ Docs Migration Status") to the new version, so others see the live report (user, 13 Nov). **Every** rebuild of the page is followed by this step, not only the morning one.

The page and `reports/status-latest.md` are then current. Built 13 Nov (DOCOPS-280).

## 9. How a batch is run (for reference)

- `scratch/overnight_batch.py <file> --target <repos> --bu <bu> --family <f> ...` writes the batch file: one line per product, newest version.
- `scratch/overnight.sh <file>` runs it and writes `<file>.summary` and `<file>.logs/`. Run it again to resume.
- Batch files and summaries live in `cache/overnight/` (not committed).
- **Never edit `scratch/overnight.sh` while a batch runs.** Bash reads a script as it goes, so editing it mid-run cut Batch 1 off before its last line, on 12 Nov. Its one run had already finished.
