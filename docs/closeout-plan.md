# Close-out plan: 12 Nov to 30 Nov 2026

> The one plan for finishing the migration. It replaces day-to-day picking from the Jira handoff.
> The testing scope (what each check covers, Stages 1–3, team requirements, backup table) stays in
> `reports/uat-plan-2026-11-12.md`; this file says **who does what, on which day**.
> Go-live: **Mon 23 Nov** (may move to 25–26 Nov). Old site off: **Mon 30 Nov**.

## Today

*Rewritten each morning. Never more than three decisions.*

**Thu 12 Nov.** Plan agreed (D1–D4 answered).

- **Batch 1** (BW plug-ins, newest versions) ran from 13:50.
- 54 of its 80 versions were skipped: their original packages had been deleted from this machine after the backup.
- Tonight, **Batch 1b** downloads them again from the old site, unpacks them, and checks the skipped versions.

Karan's list received (§6). It is final for 1,166 Integration versions: 27 to add, 80 published ones to remove, both in R2 before go-live.

Nothing needed from you until Friday morning, apart from one Jira yes or no.

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
4. **Merges to `wip` happen only in release windows** (R1, R2, R3). Within a window they are **spread out**: a group of about five repos at a time, and the next group only once staging shows the previous one rebuilt.
5. **You get one note a day:** what ran overnight, what was found, and what is decided next.

## 3. Calendar

Machine time: about 5 minutes per version checked.

| Day | Focus | Lane A: machine | Lane B: agents | Lane C: you |
|---|---|---|---|---|
| **Thu 12** | Plan | Day: **Batch 1**, BW plug-ins, newest versions; 26 of 80 could be checked. Night: **Batch 1b**, download and unpack the BW plug-in packages again, then check the newest versions Batch 1 skipped. | – | Done |
| **Fri 13** | **Release R1** | Day: first, **K1**: Karan's list written into the catalog (§6). Then R1 in four spread-out groups, each after the previous shows on staging: TIBCO small families; TIBCO middle families; TIBCO large families and the four already checked (FTL, Cloud, BusinessEvents, Scribe); ibi (7 repos, 4 with `wip` commits of their own, merged properly). Night: **Batch 2**: the 27 additions from Karan's list downloaded and unpacked (K3); then the TIBCO newest versions, without Karan's "do not migrate" ones, and the 20 re-checks, about 11 h. Then **Batch 3**, ibi newest (22) and Statistica newest (11), about 3 h. | Triage of Batch 1 and 1b; UAT sheet rows for the open AEM items (§8) | Sign in. Paste the new rows into the UAT sheet. |
| Sat 14 – Sun 15 | – | Batches 2–3 finish on their own | – | Nothing |
| **Mon 16** | **Triage** | Day: **K2**, the 80 removals in `content-fix`; **K3**, convert and merge the 27 additions (continues Tue) | Triage of Batches 2–3, one agent per family. One list of every problem kind, with counts, plus UAT sheet rows for the new site, pipeline and AEM kinds. | Sign in. Paste the sheet rows. **D5:** which fixes go into R2, before go-live, and which wait until after 30 Nov |
| **Tue 17 – Wed 18** | **Fixes** | Day: re-conversion of what R2 touches, then publish to `content-fix` | Fix agents, one per chosen Jira issue (candidates: 349 dropped topics, 360 angle-bracket text, 363 lost anchors, 362 code headings, 354 FTL redirects, 343 EMS anchors) | Nothing, unless an agent finds a design question |
| **Thu 19** | **Release R2** | Day: R2 (fixes, Karan's 80 removals and 27 additions), spread out as R1. Night: **Batch 4**, re-check what R2 changed. | – | Approve R2 (one yes or no) |
| **Fri 20** | **Go / no-go** | – | Triage of Batch 4 | **Go / no-go** against §4. **D6:** the 82 TIBCO versions with no package on the old site. |
| Sat 21 – Sun 22 | Buffer | Re-runs if needed | – | – |
| **Mon 23** | **Go-live** | – | – | – |
| **Mon 23 – Wed 25** | Stage 2 | Nights: **Batches 5–6**, older TIBCO versions outside BW plug-ins (about 154), including the comparison with the live old site | Triage | AEM follow-ups |
| **Thu 26** | **Release R3** | Day: R3 (Streaming, anything held from R2, including additions that did not convert cleanly). Night: **Batch 7**, check them. | – | Approve R3 |
| **Fri 27 – Mon 30** | Old-site close | Collect old addresses for help with no redirect map (DOCOPS-322, 279), while the old site is up | Triage | Close the backups (DOCOPS-281, 283); confirm nothing else is needed from the old site |
| **After 30 Nov** | Stage 3 | Older BW plug-in versions still published after Karan's removals (on disk after Batch 1b), older ibi (178), Statistica (24); Streaming once AEM serves it | Fixes left from §4 | – |

If go-live moves to 25–26 Nov, the calendar shifts by those days. R2 still lands three days before go-live.

## 4. Go / no-go on Fri 20

Ready when:

- Every newest version (TIBCO without Streaming, ibi, Statistica) has a check result, and every finding is logged, explained or clean.
- No go-live blocker is open on our side. AEM-side items (344, 345, 346, 351, 353) are reported, with the AEM team's answer noted.
- Redirect maps are loaded by AEM (DOCOPS-271), or the AEM team has said when they will be.

## 5. Parking lot (dated, not now)

| Item | Slot |
|---|---|
| BusinessEvents 6.3.2: "Addressing Schema Elements" missing from the staging menu | Triage, Mon 16 |
| EMS 10.4.0: re-check with the fixed checker | Batch 3 (Fri 13 night) |
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

## 7. Decisions

| # | Decision | Answer |
|---|---|---|
| D1 | How `content-fix` reaches `wip` (R1: 20 TIBCO and 7 ibi repos) | **Claude merges, spread out** in groups of about five, each after the previous rebuild shows on staging; fetch first; Streaming held to R3 (user, 12 Nov) |
| D2 | Claude starts the calendar's runs, keeps going past failures, and reports in the morning | **Yes** (user, 12 Nov) |
| D3 | Which Integration versions to publish | **Karan's decision is final** for the 1,166 versions on his list: 27 to add, 80 to remove, both before go-live (§6; user, 12 Nov) |
| D4 | Parallel agents for triage and fixes | **Yes** (user, 12 Nov). Not while a batch runs (memory). |
| D5 | Which fixes go into R2 | Mon 16, from the measured counts |
| D6 | The 82 TIBCO versions with no package on the old site | Fri 20 |

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

## 9. How a batch is run (for reference)

- `scratch/overnight_batch.py <file> --target <repos> --bu <bu> --family <f> ...` writes the batch file: one line per product, newest version.
- `scratch/overnight.sh <file>` runs it and writes `<file>.summary` and `<file>.logs/`. Run it again to resume.
- Batch files and summaries live in `cache/overnight/` (not committed).
- **Never edit `scratch/overnight.sh` while a batch runs.** Bash reads a script as it goes, so editing it mid-run cut Batch 1 off before its last line, on 12 Nov. Its one run had already finished.
