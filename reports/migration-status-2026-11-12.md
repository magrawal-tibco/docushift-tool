# Docs migration to AEM: status by business unit (12 Nov 2026)

The FTL staging check was being re-run while this was written; FTL counts as "checked on staging, being re-checked".

## 1. Product versions: migration progress

"Migrated" means the online help was converted to Markdown, **or** the version had only PDFs or release documents and those were moved over as they are.

| | **TIBCO** | **ibi** | **Spotfire** | **EBX** | **DataSynapse** |
|---|---|---|---|---|---|
| Versions in the catalog | 3,653 | 320 | 1,083 | 125 | 28 |
| Selected to migrate | 520 | 202 | 22 | 20 + 16 translated | 6 |
| **Migrated** | **509** | **200** | **22** | all | all |
| – online help converted | 441 | 96 | 20 | | |
| – PDFs / release documents only | 68 | 104 | 2 | | |
| **Left to migrate** | **11** | **2** | **0** | 0 (done earlier) | 0 (done earlier) |
| Published to the new repositories | 583 ¹ | 200 | 38 ¹ | yes | yes |
| Waiting to be re-published | 22 (20 out of date, 2 failed) | 0 | 0 | | |
| Checked locally (source vs. converted copy) | 23 | 198 ² | 3 | UAT done | UAT done |
| Checked on staging | 23 ³ | 65 ² | 0 | UAT done | UAT done |

¹ Includes versions published in earlier rounds that are now retired or outside the current selection (TIBCO 74, Spotfire 16).
² ibi was checked in October and re-published since; those results need a re-run.
³ 11 have every problem logged in Jira; 12 (FTL) are being re-checked. 560 TIBCO versions are left to check on staging.

EBX and DataSynapse were migrated earlier with the first-generation converter and closed after UAT; they are not in Docushift's counts.
Not selected: TIBCO 3,133 versions retired, out of scope or not chosen; Spotfire 964 out of scope and 39 retired.

## 2. Files before and after (published versions)

| | Files in the original packages | Converted files (Markdown pages) | After merging small pages (Markdown pages) |
|---|---|---|---|
| TIBCO | 732,484 + 57,784 API files | 277,303 (181,862) | **160,204 (63,062)** |
| ibi | 564,605 | 173,366 (75,747) | **174,087 (76,021)** |
| Spotfire | 221,709 | 157,086 (119,219) | **89,850 (51,843)** |
| **Total** | **1,518,798 + 57,784 API** | **607,755 (376,828)** | **424,141 (190,926)** |

About 72% fewer files overall; Markdown pages roughly halved by merging small pages. API reference files are copied over unchanged. ibi grows slightly when merged: its help is mostly in large pages already, and a few navigation pages are added.

## 3. New repositories

| BU | Repositories |
|---|---|
| TIBCO | **42**: 24 content + 18 resource repositories |
| Spotfire | **2**: Data Virtualization, Statistica |
| ibi | **8**: 6 English + 2 translated |
| EBX, DataSynapse | Publishing and resource repositories built in their own projects; not counted here |
| **Total** | **52** |

## 4. Story points by epic (Jira, sub-tasks)

| Epic | Done | In progress | To do | Total |
|---|---|---|---|---|
| Docushift: the migration tool (DOCOPS-74) | 26.0 | 6.25 | 14.0 | 46.25 |
| TIBCO docs migration (DOCOPS-5) | 16.5 | 4.0 | 9.75 | 30.25 |
| ibi docs migration (DOCOPS-139) | 3.5 | 2.75 | 5.0 | 11.25 |
| Merging small pages (DOCOPS-75) | 4.75 | 0.5 | 0.75 | 6.0 |
| EBX migration (DOCOPS-153) | 6.75 | – | – | 6.75 |
| DataSynapse migration (DOCOPS-170) | 3.75 | – | – | 3.75 |
| First-generation converter (under DOCOPS-3) | 3.25 | – | – | 3.25 |
| **Total** | **64.5** | **13.5** | **29.5** | **107.5** |

Spotfire work sits inside the TIBCO epic. The Citrix and NetScaler epics and their release activities are not included. Story points are estimates, adjusted as each item finishes. To do includes the writer spot-checks (5 TIBCO, 2 ibi), the remaining migration rounds, and the 12 staging problems logged this week.

## 5. Major categories of work

1. **Building the migration tool:** converters for four help formats (MadCap Flare, DITA, WebWorks, DocBook), catalog discovery, downloading, unpacking, link and image repair, menus.
2. **Merging small pages:** fewer pages, with redirects and context-sensitive help links carried over.
3. **Migration rounds, family by family:** TIBCO (about 20 families), ibi, Spotfire, EBX (with French and Japanese), DataSynapse.
4. **Redirects and help links:** old docs.tibco.com addresses mapped to new pages, in the format AEM expects.
5. **Publishing:** new repositories, syncing, re-publishing after fixes, removing retired versions.
6. **Checking quality:** local checks (original vs. converted); staging checks, with every problem logged in Jira, one issue per kind (12 kinds so far); UAT for EBX and DataSynapse.
7. **Upkeep:** catalog refreshes, end-of-support reports, source backups, a hand-off webhook for UAT issues.

## What's left

- Migrate 11 TIBCO and 2 ibi versions; re-publish 22 TIBCO versions.
- Check 560 TIBCO versions on staging; re-check ibi on staging.
- Writer spot-checks and production sign-off.

Sources: `config/versions.csv` status and file-count columns, the verify results in `state.db`, the repositories under `tibco-docs-aem` and `ibi-docs-aem`, and Jira DOCOPS (12 Nov 2026).
