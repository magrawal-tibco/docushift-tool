# Close-out plan: 12 Nov to 30 Nov 2026

> The one plan for finishing the migration. It replaces day-to-day picking from the Jira handoff.
> The testing scope (what each check covers, Stages 1–3, team requirements, backup table) stays in
> `reports/uat-plan-2026-11-12.md`; this file says **who does what, on which day**.
> Go-live: **Mon 23 Nov** (may move to 25–26 Nov). Old site off: **Mon 30 Nov**.

## Today

*Rewritten each morning. Never more than three decisions.*

**Thu 12 Nov.** Plan agreed (D1–D4 answered).

- **Batches 1 and 1b are done** (BW plug-ins, newest versions). The 184 deleted packages were downloaded again from the old site and unpacked.
- **BW plug-in results:** 75 of 253 published versions checked: 63 with findings not yet triaged, 7 logged, 3 with warnings, 2 clean. 178 older versions stay for Stage 3. 4 were skipped, on Karan's remove list or never downloaded.
- **Problem kinds:** 11 not yet in Jira. They go to Friday's triage.
- **Karan's list:** received (§6) and final for 1,166 Integration versions: 27 to add and 80 to remove, both in R2 before go-live. DOCOPS-364 created.
- **Using the free afternoon (user, 12 Nov):**
  - **Batch 1c is done** (14:58).
    - EMS 10.4.0 now reads `logged`, so its parking-lot item is closed.
    - Statistica newest: 9 have unsorted findings and 2 are clean.
    - Statistica's main product reports about 14,000 of 14,250 old pages missing, and its menu entries missing too. That is the same pattern as Spotfire Data Virtualization's. It is either a real loss or the checker misreading Spotfire's help, and it goes to triage on Fri 13. Not chased today.
  - Four fix agents are building fixes, each on its own branch, for 343, 362 and 363 together, 349, 354 and 360. All six issues are In Progress.
  - **Triage of the BW plug-in wave is done.**
    - All 67 `lost` versions now read `logged`; TIBCO stands at 106 checked, every one logged or clean.
    - **Go-live blocker, Digital Platform:** 61 of the 73 newest BW plug-in versions are not served on staging at all (404), although they are on `wip`. Kafka 6.8.2 was checked by hand against AMQP 6.5.3, which is served. DOCOPS-346 is widened and marked Critical.
    - New kinds, both ours: DOCOPS-365 (3 SAP plug-in versions published with an empty menu, 6 with no package documents) and DOCOPS-366 (checker false findings; fixer running, aiming to finish before Friday night's batch).
    - BE 6.3.2 is a variant of DOCOPS-351.
    - The UAT sheet rows are ready: `reports/uat-sheet-rows-2026-11-12.csv` (4 rows: BW not served, Critical; empty pages; pages under heading rows; the BE variant).
  - Nothing gets merged or applied. The fixes wait for D5 on Mon 16.

**Friday morning, from you:** sign in; paste the 4 UAT rows, and flag the BW plug-in row to Digital Platform as Critical; say yes or no to the one-page `&lt;` test riding R1 (DOCOPS-360); and say yes or no to merging the checker fix (DOCOPS-366) before Friday night's batch.

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
| Sat 14 – Sun 15 | – | Batches 2–3 finish on their own | – | Nothing |
| **Mon 16** | **Triage** | Day: **Δ1**, catalog refresh (test run, then the real one, §6a); **K2**, the 80 removals in `content-fix`; **K3**, convert and merge the 27 additions (continues Tue). Night: Δ1's new versions downloaded and unpacked. | Triage of Batches 2–3, one agent per family. One list of every problem kind, with counts, plus UAT sheet rows for the new site, pipeline and AEM kinds. | Sign in. Paste the sheet rows. **D5:** which fixes go into R2, before go-live, and which wait until after 30 Nov. **D7:** the delta for R2. Ask the writers for ZIPs of in-progress releases (by Tue 17 noon). |
| **Tue 17 – Wed 18** | **Fixes and delta** | Day: re-conversion of what R2 touches; Δ1 and Δ2 versions converted and merged; **EMS 10.5.1 in its new layout (Phase 78)**; all published to `content-fix` | Fix agents, one per chosen Jira issue (candidates: 349 dropped topics, 360 angle-bracket text, 363 lost anchors, 362 code headings, 354 FTL redirects, 343 EMS anchors) | Nothing, unless an agent finds a design question |
| **Thu 19** | **Release R2** | Day: R2 (fixes, Karan's 80 removals and 27 additions, the delta), spread out as R1. Night: **Batch 4**, re-check what R2 changed. | – | Approve R2 (one yes or no) |
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
| Statistica and Data Virtualization: most old pages reported missing (checker or real) | Triage, Fri 13 |
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
| D5 | Which fixes go into R2 | **All of them** (user, 12 Nov: "go ahead with the remaining suggested fixes"). Re-conversions Mon 16 – Tue 17; 360's way of applying waits for the staging test. |
| D6 | The 82 TIBCO versions with no package on the old site | Fri 20 |
| D7 | Delta before go-live: which new versions from Δ1 go into R2, and the cut-off for hand-supplied ZIPs | Mon 16, from the refresh list. Recommendation: all of Δ1, and ZIPs received by Tue 17 noon; anything later goes in R3 (§6a). |

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

## 8b. Where we stand: one status page (user, 12 Nov; approved, built Fri 13)

**Why.** When anyone asks, you need one place that says where the migration stands, how much is left, how much effort went in and is left, and which team owes what. Today that is spread over a dated report (`reports/migration-status-2026-11-12.md`, stale the next day), the per-version page (`reports/conversion-status.html`), Jira and this plan.

**What.** A first tab, **"Where we stand"**, on `reports/conversion-status.html`, plus a short text copy, `reports/status-latest.md`, to paste into an email or chat. Both are rebuilt every morning in the triage step, and both carry an "as of" time.

| Part | Shows | Read from |
|---|---|---|
| Headline | Days to go-live and to the old site's shutdown; versions migrated, published and checked on staging, each against its total | `versions.csv`, `state.db` |
| Areas | One row per area: migration (conversion), publishing, staging checks, problems found, Karan's list, delta migration, redirects, backups, team requirements, translated help, writer spot-checks. Each row gives status (done / on track / at risk / blocked), done and left, the responsible team, the next date, and its Jira issues. | Counts from the catalog and the check results. The rest from a small hand-kept file, `config/status-areas.yaml`: per area its name, team, Jira keys, plan section, next date and one-line status. Claude updates it with the morning note. |
| Effort | Story points done, in progress and to do per area and in total; the time since the first issue | The DOCOPS snapshot (`fetch_docops.py`), by the areas' Jira keys |
| Pending by team | What each of the three teams owes, with dates (user, 12 Nov). **TechDocs** (us): our fixes and runs, writers' spot-checks and in-progress ZIPs, and the open decisions D5–D7. **Digital Platform**: the AEM site and staging problems, UAT sheet rows, redirect loading, and the PRISM integration. **Engineering**: Karan's Integration decisions; the product teams (Messaging, iProcess, Streaming, Scribe); support's end-of-support reports. | A problem kind's owner from its triage decision (`platform` = Digital Platform; ours and `source` = TechDocs); open Jira issues by area; the decisions table in this plan |

**Built by** a helper agent in its own copy of the code, during the waits between the R1 merge groups on **Fri 13**. Claude reviews it before it is merged. It only reads; it changes nothing in the catalog or the repos. Jira: a note on DOCOPS-280 (Phase 65 built the page), no new issue; 0.5 SP added there if it takes over 4 h.

## 9. How a batch is run (for reference)

- `scratch/overnight_batch.py <file> --target <repos> --bu <bu> --family <f> ...` writes the batch file: one line per product, newest version.
- `scratch/overnight.sh <file>` runs it and writes `<file>.summary` and `<file>.logs/`. Run it again to resume.
- Batch files and summaries live in `cache/overnight/` (not committed).
- **Never edit `scratch/overnight.sh` while a batch runs.** Bash reads a script as it goes, so editing it mid-run cut Batch 1 off before its last line, on 12 Nov. Its one run had already finished.
