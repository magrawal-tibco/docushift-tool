# Documentation migration: where we stand

As of 15 Nov 2026, 11:35 (Jira as of Sun 15 Nov).

- **Go-live:** Mon 23 Nov, in 8 days. **Old site switched off:** Mon 30 Nov, in 15 days.
- **746 documentation versions are in the migration.** Converted: 733 (98%). In the new site's repositories: 733 (98%). Checked page by page on the staging site: 129 of the 733 in the repositories.
  - TIBCO: 522 versions; 511 converted, 511 in the repositories, 129 checked on staging.
  - IBI: 202 versions; 200 converted, 200 in the repositories, 0 checked on staging.
  - Spotfire: 22 versions; 22 converted, 22 in the repositories, 0 checked on staging.

## Areas

- **Converting the documentation**: on track (733 of 746 versions done). Karan's additions and the fixes are converted; 73 versions are re-converting on Sun 15 for the list fix (DOCOPS-370); releases since 5 Nov follow Mon 16 to Wed 18. Next, Mon 16 Nov: Convert the releases since 5 Nov and the remaining fixes for release 2 (to Wed 18). Owner: TechDocs.
- **Publishing to the new site**: on track (733 of 746 versions done). Release 1 is on staging for every TIBCO repo (Data Management fixed Sat after a repo-name problem); EMS 10.5.1's new layout went out Sun 15; release 2 runs Mon 16 to Thu 19 in small pushes the pipeline can take; ibi Mon 16. Next, Mon 16 Nov: Release 2 opens (pushes Mon to Wed, last wave Thu); ibi release 1. Owner: TechDocs.
- **Checking the new site (staging)**: on track (129 of 733 versions done). Newest versions are checked page by page on staging, now 6 pages at a time and up to 3 batches at once; older versions follow after go-live. Next, Mon 16 Nov: Read the weekend's checks (TIBCO and ibi newest versions). Owner: TechDocs.
- **Problems found by the checks**: on track (227 of 240 finding types done). Each kind of problem gets one Jira issue; the backslash/angle-bracket repair (36,204 changes) and the list fix are ready for release 2; AEM-side problems are in the UAT sheet. Next, Mon 16 Nov: Sort the weekend's findings; re-convert with the fixes (Mon 16 to Tue 17). Owner: TechDocs.
- **Go-live blockers on the new site**: blocked (0 of 2 Jira items done). AEM cuts product folder names after 50 characters, so we are renaming 116 product folders (Phase 80); 8 families done or in progress, the BW plug-ins wait for an AEM answer; 9 versions are still not served at all; pages under a heading row are hidden from the menu. Next, Fri 20 Nov: Go / no-go: served, or a date from Digital Platform. Owner: Digital Platform.
- **Which Integration versions to publish (Karan's list)**: on track (28 of 107 changes done). Engineering's list is final for 1,166 Integration versions; the 80 removals and 26 of the 27 additions are ready for release 2; one PDF-only addition has no site repository yet. Next, Mon 16 Nov: Out with release 2 (Thu 19); a repository for the Integration Platform family, or drop that one addition. Owner: TechDocs.
- **Releases since 5 Nov (delta migration)**: on track. The catalog was last refreshed on 5 Nov; it is refreshed Mon 16 and for the last time Fri 27, before the old site closes. Next, Mon 16 Nov: Refresh the catalog and list what is new. Owner: TechDocs.
- **Old links keep working (redirects)**: at risk (1 of 4 Jira items done). Go-live needs the new site to load our redirect maps, or a date for it; no date is recorded yet (to confirm). Old addresses for help with no map are collected while the old site is up. Next, Fri 20 Nov: Go / no-go: redirect maps loaded, or a date. Owner: Digital Platform.
- **Backups of the original help packages**: on track (0 of 3 Jira items done). TIBCO is on the shared drive (1,988 of 2,018 versions; 30 are being obtained by hand, 29 more marked not needed), ibi on Google Drive, Spotfire copy started 12 Nov. Next, Fri 27 Nov: Close the backups (Spotfire run summary; ibi count confirmed). Owner: TechDocs.
- **Product teams' own requirements**: on track (0 of 5 Jira items done). Messaging, iProcess, Scribe and Streaming need more than conversion, and the publishing pipeline is being joined to PRISM and the product builds; most finish after 30 Nov. Next, to confirm: Each team's next step, noted as it moves. Owner: Engineering.
- **Translated help**: on track (1 of 2 Jira items done). Checks of the translated help are planned after 30 Nov. Next, after 30 Nov: Check the translated help on the new site. Owner: TechDocs.
- **Writers' spot-checks**: on track (0 of 2 Jira items done). Writers spot-check the migrated help after 30 Nov. Next, after 30 Nov: Writers spot-check each family. Owner: TechDocs.
- **EMS 10.5.1 in its new page layout**: done (0 of 1 Jira items done). Pushed to staging Sun 15, four days early, with 217 pages instead of 159, every old link still redirected, older EMS versions unchanged. Owner: TechDocs.

## Effort

Work started Fri 25 Sep, 51 days ago. Effort logged in Jira: 65.5 points done, 19.5 in progress, 32 still to do (one point is one 8-hour day; Jira as of Sun 15 Nov).

- Converting the documentation: 32.25 done, 2.75 in progress, 3.75 to do
- Publishing to the new site: 0 done, 1 in progress, 0 to do
- Checking the new site (staging): 1.5 done, 2.75 in progress, 3.25 to do
- Problems found by the checks: 1.25 done, 2.75 in progress, 5.5 to do
- Go-live blockers on the new site: 0 done, 0 in progress, 1.25 to do
- Which Integration versions to publish (Karan's list): 0 done, 1 in progress, 0 to do
- Old links keep working (redirects): 1 done, 1.25 in progress, 0 to do
- Backups of the original help packages: 0 done, 0.5 in progress, 0.75 to do
- Product teams' own requirements: 0 done, 1.75 in progress, 1 to do
- Translated help: 1 done, 1 in progress, 0 to do
- Writers' spot-checks: 0 done, 0 in progress, 7 to do
- EMS 10.5.1 in its new page layout: 0 done, 0.5 in progress, 0 to do
- Building the conversion tool, and earlier work: 28.5 done, 4.25 in progress, 9.5 to do

## What each team owes

**TechDocs**

- Mon 16 Nov, Converting the documentation: Convert the releases since 5 Nov and the remaining fixes for release 2 (to Wed 18)
- Mon 16 Nov, Publishing to the new site: Release 2 opens (pushes Mon to Wed, last wave Thu); ibi release 1
- Mon 16 Nov, Checking the new site (staging): Read the weekend's checks (TIBCO and ibi newest versions)
- Mon 16 Nov, Problems found by the checks: Sort the weekend's findings; re-convert with the fixes (Mon 16 to Tue 17)
- Mon 16 Nov, Which Integration versions to publish (Karan's list): Out with release 2 (Thu 19); a repository for the Integration Platform family, or drop that one addition
- Mon 16 Nov, Releases since 5 Nov (delta migration): Refresh the catalog and list what is new
- Mon 16 Nov, Decisions: Decide: Delta before go-live: which new versions from the 16 Nov catalog refresh go into release 2, and the cut-off for hand-supplied ZIPs
- Tue 17 Nov, Releases since 5 Nov (delta migration): Writers send the files of releases still in progress (by noon)
- Fri 20 Nov, Decisions: Decide: The TIBCO versions with no package on the old site: 82 on 12 Nov. 13 Nov: 23 uploaded by hand (checksums verified), 29 marked not required by the user; 33 left (C:/tmp/handzips/still-missing.csv). 30 are for the user to obtain; 3 BW plug-in additions (K3) have never been tried, so the backup script fetches them after batch-fixes ends (it deletes workspace ZIPs).
- Fri 27 Nov, Old links keep working (redirects): Collect old addresses for help with no redirect map
- Fri 27 Nov, Backups of the original help packages: Close the backups (Spotfire run summary; ibi count confirmed)
- after 30 Nov, Translated help: Check the translated help on the new site
- after 30 Nov, Writers' spot-checks: Writers spot-check each family
- 43 kinds of problem found by the checks, 13 still to sort at the morning triage
- 53 open items in Jira

**Digital Platform**

- Fri 20 Nov, Go-live blockers on the new site: Keep full product folder names in the address (50-character limit), and serve the 9 missing versions
- Fri 20 Nov, Go-live blockers on the new site: Show pages under heading rows in the staging menu, or agree that we restructure our menus
- Fri 20 Nov, Old links keep working (redirects): Load the redirect maps on the new site, or give a date
- to confirm, Problems found by the checks: Answer the site problems reported in the UAT sheet
- 5 kinds of problem found by the checks
- 6 open items in Jira

**Engineering**

- to confirm, Which Integration versions to publish (Karan's list): Confirm or decline new Integration versions the catalog refreshes find
- to confirm, Releases since 5 Nov (delta migration): Support sends the end-of-support report with its retirement dates again
- to confirm, Product teams' own requirements: Each team's next step, noted as it moves
- 4 open items in Jira
