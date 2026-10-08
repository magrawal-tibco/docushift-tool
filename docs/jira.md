# Jira Tracking — What Is Logged in DOCOPS

> **Last reconciled:** 2026-10-08, against Jira and `config/versions.csv`.
> Conventions (site, cloud ID, story points, transitions, who owns what) live in
> `C:\github\confluence-mcp\reports\docushift-claude-atlassian-context.md`; this file
> does not repeat them. It answers one question: **is this piece of work in Jira, and where?**

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

Other logged work: stakeholder status page DOCOPS-197; family reassignments DOCOPS-120 (in progress).

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
