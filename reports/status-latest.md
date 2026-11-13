# Documentation migration: where we stand

As of 13 Nov 2026, 22:46 (Jira as of Fri 13 Nov).

- **Go-live:** Mon 23 Nov, in 10 days. **Old site switched off:** Mon 30 Nov, in 17 days.
- **746 documentation versions are in the migration.** Converted: 733 (98%). In the new site's repositories: 733 (98%). Checked page by page on the staging site: 164 of the 733 in the repositories.
  - TIBCO: 522 versions; 511 converted, 511 in the repositories, 164 checked on staging.
  - IBI: 202 versions; 200 converted, 200 in the repositories, 0 checked on staging.
  - Spotfire: 22 versions; 22 converted, 22 in the repositories, 0 checked on staging.

## Areas

- **Converting the documentation**: on track (733 of 746 versions done). Karan's 27 additions and the EMS, BusinessEvents and ibi fixes are converted (Fri 13); releases since 5 Nov follow Mon 16 to Wed 18. Next, Mon 16 Nov: Convert the releases since 5 Nov and the remaining fixes for release 2 (to Wed 18). Owner: TechDocs.
- **Publishing to the new site**: at risk (733 of 746 versions done). Release 1 is going out a group at a time as staging rebuilds (2 to 10 hours each); 16 TIBCO repos are out, Data Management is waiting, and MFT, BPM, TRA and BusinessWorks follow; ibi waits for Digital Platform's weekend refresh. Release 2 Thu 19, release 3 Thu 26, release 4 early December. Next, Mon 16 Nov: Finish release 1 (TIBCO over the weekend, ibi on Monday). Owner: TechDocs.
- **Checking the new site (staging)**: on track (164 of 733 versions done). Every newest version is checked page by page on staging before go-live, overnight; older versions follow after go-live. Next, Mon 16 Nov: Read the weekend's checks (TIBCO and ibi newest versions). Owner: TechDocs.
- **Problems found by the checks**: on track (59 of 71 finding types done). Each kind of problem gets one Jira issue at the morning triage and is fixed in a planned window; every fix built so far goes into release 2. Next, Mon 16 Nov: Sort the weekend's findings; re-convert with the fixes (Mon 16 to Tue 17). Owner: TechDocs.
- **Go-live blockers on the new site**: blocked (0 of 2 Jira items done). 61 of the 73 newest BW plug-in versions are not served on staging (Critical); pages placed under a heading row are hidden from the staging menu or not found. Next, Fri 20 Nov: Go / no-go: served, or a date from Digital Platform. Owner: Digital Platform.
- **Which Integration versions to publish (Karan's list)**: on track (28 of 107 changes done). Engineering's list is final for 1,166 Integration versions; the decisions are in the catalog, the 80 removals and 26 of the 27 additions are ready for release 2, and one PDF-only addition has no site repository yet. Next, Mon 16 Nov: Out with release 2 (Thu 19); a repository for the Integration Platform family, or drop that one addition. Owner: TechDocs.
- **Releases since 5 Nov (delta migration)**: on track. The catalog was last refreshed on 5 Nov; it is refreshed Mon 16 and for the last time Fri 27, before the old site closes. Next, Mon 16 Nov: Refresh the catalog and list what is new. Owner: TechDocs.
- **Old links keep working (redirects)**: at risk (1 of 4 Jira items done). Go-live needs the new site to load our redirect maps, or a date for it; no date is recorded yet (to confirm). Old addresses for help with no map are collected while the old site is up. Next, Fri 20 Nov: Go / no-go: redirect maps loaded, or a date. Owner: Digital Platform.
- **Backups of the original help packages**: on track (0 of 3 Jira items done). TIBCO is on the shared drive (1,988 of 2,018 versions; 30 are being obtained by hand, 29 more marked not needed), ibi on Google Drive, Spotfire copy started 12 Nov. Next, Fri 27 Nov: Close the backups (Spotfire run summary; ibi count confirmed). Owner: TechDocs.
- **Product teams' own requirements**: on track (0 of 5 Jira items done). Messaging, iProcess, Scribe and Streaming need more than conversion, and the publishing pipeline is being joined to PRISM and the product builds; most finish after 30 Nov. Next, to confirm: Each team's next step, noted as it moves. Owner: Engineering.
- **Translated help**: on track (1 of 2 Jira items done). Checks of the translated help are planned after 30 Nov. Next, after 30 Nov: Check the translated help on the new site. Owner: TechDocs.
- **Writers' spot-checks**: on track (0 of 2 Jira items done). Writers spot-check the migrated help after 30 Nov. Next, after 30 Nov: Writers spot-check each family. Owner: TechDocs.
- **EMS 10.5.1 in its new page layout**: on track (0 of 1 Jira items done). Built and ready on Fri 13, three days early: 217 pages instead of 159, every old link still redirected, older EMS versions unchanged. Next, Thu 19 Nov: Out with release 2 (Thu 19), then checked on staging. Owner: TechDocs.

## Effort

Work started Fri 25 Sep, 49 days ago. Effort logged in Jira: 65.5 points done, 19.5 in progress, 29.5 still to do (one point is one 8-hour day; Jira as of Fri 13 Nov).

- Converting the documentation: 32.25 done, 2.75 in progress, 3.75 to do
- Publishing to the new site: 0 done, 1 in progress, 0 to do
- Checking the new site (staging): 1.5 done, 2.75 in progress, 3.25 to do
- Problems found by the checks: 1.25 done, 2.75 in progress, 3 to do
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
- Mon 16 Nov, Publishing to the new site: Finish release 1 (TIBCO over the weekend, ibi on Monday)
- Mon 16 Nov, Checking the new site (staging): Read the weekend's checks (TIBCO and ibi newest versions)
- Mon 16 Nov, Problems found by the checks: Sort the weekend's findings; re-convert with the fixes (Mon 16 to Tue 17)
- Mon 16 Nov, Which Integration versions to publish (Karan's list): Out with release 2 (Thu 19); a repository for the Integration Platform family, or drop that one addition
- Mon 16 Nov, Releases since 5 Nov (delta migration): Refresh the catalog and list what is new
- Mon 16 Nov, Decisions: Decide: Delta before go-live: which new versions from the 16 Nov catalog refresh go into release 2, and the cut-off for hand-supplied ZIPs
- Tue 17 Nov, Releases since 5 Nov (delta migration): Writers send the files of releases still in progress (by noon)
- Thu 19 Nov, EMS 10.5.1 in its new page layout: Out with release 2 (Thu 19), then checked on staging
- Fri 20 Nov, Decisions: Decide: The TIBCO versions with no package on the old site: 82 on 12 Nov. 13 Nov: 23 uploaded by hand (checksums verified), 29 marked not required by the user; 33 left (C:/tmp/handzips/still-missing.csv). 30 are for the user to obtain; 3 BW plug-in additions (K3) have never been tried, so the backup script fetches them after batch-fixes ends (it deletes workspace ZIPs).
- Fri 27 Nov, Old links keep working (redirects): Collect old addresses for help with no redirect map
- Fri 27 Nov, Backups of the original help packages: Close the backups (Spotfire run summary; ibi count confirmed)
- after 30 Nov, Translated help: Check the translated help on the new site
- after 30 Nov, Writers' spot-checks: Writers spot-check each family
- 30 kinds of problem found by the checks, 12 still to sort at the morning triage
- 50 open items in Jira

**Digital Platform**

- Fri 20 Nov, Go-live blockers on the new site: Serve the 61 BW plug-in versions on staging, or give a date
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
