# Jira Tracking — What Is Logged in DOCOPS

> **Last reconciled:** 2026-10-14, against Jira and `config/versions.csv`.
> Conventions (site, cloud ID, story points, transitions, who owns what) live in
> `C:\github\confluence-mcp\reports\docushift-claude-atlassian-context.md`; this file
> does not repeat them. It answers one question: **is this piece of work in Jira, and where?**

## Handoff — read first, update last

Any session that touches Jira, closes a phase, or lands a run updates this section before it
ends: rewrite **Waiting**, append one line to **Log**, and bump *Last reconciled* above.

**Waiting** (Jira changes due when the event happens):

| When this happens | Do this in Jira |
|---|---|
| Phase 47 re-runs (8 versions) pass | DOCOPS-187 → Done |
| Phase 40 network runs finish | DOCOPS-123 → Done |
| 50 long-path + 8 DITA versions re-run | DOCOPS-188 → Done |
| `sync --bu tibco` + `validate` run | DOCOPS-134, DOCOPS-135; refresh counts in DOCOPS-122, 125–127 |
| ibi re-sync | DOCOPS-200 → Done |
| A family reassignment is committed | Add a dated line to the progress comment on DOCOPS-120 |
| Family review finished | DOCOPS-120 → Done, then DOCOPS-130 |
| Edit to DOCOPS-217 is allowed (blocked by a permission check on 2026-10-09) | DOCOPS-217: append the 2026-10-09 publish note → Done |
| A follow-up from the BusinessConnect warnings is planned | DOCOPS-220 → In Progress |
| A new phase is opened | One sub-task under the matching story, In Progress, no `retro` |

**Left alone on purpose:** DOCOPS-8 is a Task where its siblings are Stories.

**Log** (newest first, one line per session):

- 2026-10-14 — DOCOPS-232 → Done: Phase 52 runs passed (PSC 5.1.0 0 image errors, z/Linux 8.1.0
  published).

- 2026-10-14 — Flogo, BusinessWorks, Fulfillment and MFT run logged as DOCOPS-231 (Done, 0.5 SP):
  38 of 43 published. Phase 52 opened as DOCOPS-232 (In Progress, 0.5 SP).

- 2026-10-13 — Phase 51 and the 6 held Foresight versions logged as DOCOPS-229 (Done, 1 SP, under
  DOCOPS-7); correction note on DOCOPS-228; DOCOPS-120 comment: older MFT versions ineligible (398d550).

- 2026-10-13 — Foresight run logged as DOCOPS-228 (Done, 0.5 SP, under DOCOPS-7): 33 of 39
  published, 6 held; DOCOPS-120 progress comment: HIPAA Validator Desktop 9.0.0–9.2.0 eligible.

- 2026-10-12 — EMS, FTL and Messaging run logged as DOCOPS-223 (Done, 0.5 SP, under DOCOPS-7):
  39 of 44 published; 7 leftover issues in docs/open-issues.md.

- 2026-10-12 — DOCOPS-120 progress comment: retired Gemini, FTL and eFTL versions ineligible,
  14 versions (5dc8f76).

- 2026-10-12 — DOCOPS-120 progress comment: legacy Messaging Monitor, Schema Repository and
  Messaging Manager 1.0.0/1.1.0 ineligible, 20 versions (543601e).

- 2026-10-12 — DOCOPS-120 progress comment: Messaging Bridge (Kafka, Pulsar) end of life, 15 versions
  ineligible (86081fd).

- 2026-10-12 — DOCOPS-120 progress comment: LogLogic decommissioned, all 136 versions ineligible
  (e2e1fc1).

- 2026-10-12 — Cloud family run logged as DOCOPS-222 (Done, 0.25 SP, under DOCOPS-7): 5 of 5
  real versions published. DOCOPS-120 progress comment: newest version only for cloud and
  integration platform (42cdaa4, 195 versions ineligible).

- 2026-10-09 — Last 5 BusinessConnect versions re-run and published (44 of 44). DOCOPS-218 and
  DOCOPS-219 → Done (219 now 0.5 SP for the warning check); DOCOPS-220 created (Backlog, 0.25 SP,
  under DOCOPS-101) for three deferred follow-ups. DOCOPS-217 still In Progress: its edit was blocked.

- 2026-10-09 — Phases 49 and 50 (built, runs pending) logged as DOCOPS-217 (under DOCOPS-96) and
  DOCOPS-218 (under DOCOPS-114); the BusinessConnect run as DOCOPS-219 (under DOCOPS-7, 39 of
  44 published). All In Progress, 0.25 SP each.

- 2026-10-09 — Catalog refresh and the 2026-10-09 end-of-support report (5d8b461) logged as
  DOCOPS-215 (Done, 0.25 SP, under DOCOPS-6). Facebook, Marketo and Twitter plug-ins dropped.

- 2026-10-08 — DOCOPS-120 progress comment: added the pre-2016 ineligibility (3fe7d90) and
  the Service Grid + Container Edition move to bpm (73d111c).

- 2026-10-08 — This session's reconcile and handoff work logged as DOCOPS-208 (Done, 0.5 SP,
  under DOCOPS-101). DOCOPS-120 progress comment brought up to 68a9d11 (22 products
  reassigned, empty families dropped, Flogo below 2.26.0 and 90 retired versions disabled).

- 2026-10-08 — Family/catalog gap check. Created DOCOPS-206 (Phase 48, Flogo retirement) and
  DOCOPS-207 (ibi family regroup, 2026-10-05), both Done, no `retro`. Progress comment on
  DOCOPS-120 lists the TIBCO reassignments so far.

- 2026-10-08 — Full reconcile against Jira, `versions.csv`, phase history. Created DOCOPS-192–200,
  fixed counts (122, 125–127, 129), statuses (87, 120, 187), labels on all run tasks, broken
  DOCOPS-20/21 references (14, 15, 17, 19, 76). Retro rule set to "finished before the current
  month"; 27 retro tasks remain. Shared guide in confluence-mcp updated to match.

## How to log work

- **Where:** DOCOPS-74 Docushift, DOCOPS-75 Reframe, DOCOPS-5 TIBCO runs, DOCOPS-139 ibi runs.
  One sub-task per phase (tool work) or per run (migration work).
- **Labels:** `docushift` or `reframe` on everything; add `tibco` / `ibi` on run tasks.
- **`retro`:** only when the work **finished before the current calendar month**, so it is
  not counted in this month's effort. October work logged in October gets no `retro`, however
  late it is logged. A task spanning months is dated by when its last piece finished; a story
  gets `retro` only if every sub-task under it does. On 2026-10-08 that left 27 retro tasks,
  all finished in September (DOCOPS-13–19, 78–82, 85, 88, 89, 92, 97, 98, 108–113, 118, 119, 193).
- **Counts drift.** A task title that carries a count (versions merged, failed, out of date)
  is true on the day it was written. Re-read `versions.csv` (`_bu`, `_status`, `_sync_status`)
  before quoting a number, and re-check the open run tasks when a run lands.
- **Bulk changes go through `C:\github\confluence-mcp\jira\docops-plan.csv`**
  (`apply_docops_plan.py --dry-run`, then live). The script matches rows without a `ref`
  by parent and title, so **renaming an issue in Jira alone makes the next run create a
  duplicate.** To rename, put the key in the row's `ref` column and the new title in the CSV.
  The script never removes labels; remove them with the Atlassian MCP and in the CSV.

## Phases → Jira

"Folded" means the phase has no task of its own; its work is counted in the task named.

| Phase | Work | Jira |
|---|---|---|
| 1 | Architecture, docs, scaffolding | DOCOPS-13 |
| 2, 3.5, 3.6 | Catalog CSVs, merge, scope exclusions, slug key | DOCOPS-85 |
| 3, 33 | Discovery, docsite sitemap | DOCOPS-84 |
| 3.7 | End-of-support exclusions | DOCOPS-193 |
| 3.8 | `-userdocs` publishing names | folded: DOCOPS-97 |
| 4 | Download, extract | DOCOPS-88, DOCOPS-89 |
| 5 | Conversion driver, engines, detection | DOCOPS-14, DOCOPS-78–82 |
| 6, 36 | Navigation, `toc.yml`, publishing layout | DOCOPS-93, DOCOPS-97 |
| 7 | CLI, findings, reporting | DOCOPS-15, DOCOPS-98 |
| 8–19, 21, 23, 27 | Conversion fixes (code spans, landing pages, WebWorks links, DocBook, tables, classes) | folded: DOCOPS-16, DOCOPS-17 |
| 20 | Reframe engine | DOCOPS-108–113 |
| 22, 35 | Redirect / cutover maps | DOCOPS-94, DOCOPS-131 |
| 24, 25 | Status rows, migration verdict | folded: DOCOPS-98 |
| 26, 28 | Layout pin, subtree merge | folded: DOCOPS-109 |
| 29 | Filename is the URL | folded: DOCOPS-92 |
| 30 | ~50,000 cross-references repaired | DOCOPS-196 |
| 31 | WebFOCUS split | DOCOPS-142 |
| 32 | Families assigned by hand | DOCOPS-86 |
| 34 | Whole-tool review | DOCOPS-102; deferred findings DOCOPS-106 |
| 37–39 | Family-review columns, status columns, PDF-ready | DOCOPS-194 |
| 40 | Sitemap package names | build DOCOPS-195; runs DOCOPS-123 |
| 41 | Flare source topics in output | DOCOPS-192 |
| 42 | Reframe for Flare + DITA, all TIBCO | build DOCOPS-198; run DOCOPS-129 |
| 43 | Orphan topics out of TOC | build DOCOPS-95; runs DOCOPS-124, DOCOPS-115 |
| 44 | Links around images | DOCOPS-185 |
| 45 | Function catalogs as API reference | DOCOPS-186 |
| 46 | Long-path refusal | build DOCOPS-184; re-runs DOCOPS-188 |
| 47 | Service Grid merges | DOCOPS-187 (in progress) |
| 48 | Flogo connectors retired; VS Code extension to flogo | DOCOPS-206 |
| 49 | Images too long to publish get a shorter name | DOCOPS-217 (in progress) |
| 50 | Per-page names for a topic in two guides | DOCOPS-218 |
| 51 | Merged Flare help systems: subsystem TOCs spliced into the master | DOCOPS-229 |
| 52 | Letter case the source gets wrong: image links, ZIP name clashes | DOCOPS-232 |

Other logged work: Jira reconcile and this handoff DOCOPS-208; stakeholder status page DOCOPS-197; TIBCO family reassignments DOCOPS-120
(in progress, progress kept as comments); ibi family regroup DOCOPS-207; catalog refresh and 2026-10-09 end-of-support report DOCOPS-215; cloud family run DOCOPS-222; EMS, FTL and Messaging run DOCOPS-223.

## Open run tasks (as of 2026-10-08)

| Jira | What | `versions.csv` on 2026-10-08 |
|---|---|---|
| DOCOPS-125–127 | TIBCO wave 2a/b/c | 895 TIBCO `not-started` |
| DOCOPS-122 | Failed TIBCO versions | 12 `convert-failed`, 23 `download-failed` |
| DOCOPS-199 | Leftover TIBCO versions | 2 `format-unknown`, 1 `sync-failed` |
| DOCOPS-134 | TIBCO re-sync | 214 `out-of-date` |
| DOCOPS-200 | ibi re-sync | 25 `out-of-date` |
| DOCOPS-147 | ibi download | 1 `download-failed` |
| DOCOPS-128 | Spotfire | 42 `not-started` |

## Not in Jira, by choice

- Committing and pushing this repo's own branch: part of each phase, not a task.
- The Phase 8–29 fixes listed as folded above.
