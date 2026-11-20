# Documentation migration: where we stand

As of 20 Nov 2026, 14:00 (Jira as of Thu 19 Nov).

- **Go-live:** Mon 30 Nov, in 10 days. **Old site switched off:** Mon 30 Nov, in 10 days.
- **728 documentation versions are in the migration.** Converted: 725 (100%). In the new site's repositories: 725 (100%). Checked page by page on the staging site: 516 of the 725 in the repositories.
  - TIBCO: **at risk**: 83% checked on staging; open UAT rows: 8 Critical and 16 High; 1 UAT row fixed by Digital Platform, waiting on our retest. 526 versions; 523 converted, 523 in the repositories, 432 checked on staging.
  - IBI: **at risk** (set by hand): 42% checked on staging, waiting for Digital Platform to put 10 products on staging; 1 Critical and 5 High UAT rows open. 202 versions; 202 converted, 202 in the repositories, 84 checked on staging.
  - UAT sheet as downloaded 2026-11-20 13:47: https://docs.google.com/spreadsheets/d/1lcMg602HoTxxvMTQnrzEt2i4Ft2Z4ch0dwmmIlZo6eg/edit?usp=sharing.

## Areas

- **Converting the documentation**: on track (725 of 728 versions done). Karan's additions, the list fix (DOCOPS-370) and the 13 versions the 5 Nov refresh missed are converted; two Messaging versions in another help format wait on a decision (DOCOPS-355). Next, Fri 27 Nov: Convert what the last catalog refresh finds. Owner: TechDocs.
- **Publishing to the new site**: on track (725 of 728 versions done). Release 2 went out overnight Wed 18 in 7 waves to 21 TIBCO repos with no errors; the 4 largest (BusinessConnect, BusinessWorks, Streaming, Platform) and the BW plug-ins follow in smaller pieces; first ibi update since the freeze went out Fri 20 (Data Intelligence and iWay Service Manager, 11 versions) and showed on staging within the hour. Next, Mon 23 Nov: Send the other ibi fixes to staging one repository at a time. Owner: TechDocs.
- **Checking the new site (staging)**: on track (516 of 725 versions done). Newest TIBCO versions are checked page by page on staging; ibi checks resumed Fri 20; the 10 versions refused earlier are re-checked, and the last 22 WebFOCUS versions are running; older versions follow after go-live. Next, Fri 20 Nov: Sort the WebFOCUS check results. Owner: TechDocs.
- **Problems found by the checks**: on track (990 of 1,005 finding types done). Each kind of problem gets one Jira issue; the backslash repair (confirmed on staging Mon), the list fix and the picture-link letter-case fix (about 21,000 links) went out with release 2; AEM-side problems are in the UAT sheet. Next, Fri 20 Nov: Read the re-check of what release 2 changed. Owner: TechDocs.
- **Go-live blockers on the new site**: blocked (0 of 2 Jira items done). AEM cuts product folder names after 50 characters, so we are renaming 116 product folders (Phase 80); every family but the BW plug-ins is renamed, and the BW plug-in renames (approved Mon) go out after release 2's main waves; 9 versions are still not served at all; pages under a heading row are hidden from the menu. Next, Fri 20 Nov: Go / no-go: served, or a date from Digital Platform. Owner: Digital Platform.
- **Which Integration versions to publish (Karan's list)**: on track (28 of 107 changes done). Engineering's list is final for 1,166 Integration versions; the 80 removals and 26 of the 27 additions are going out with release 2; one PDF-only addition has no site repository yet. Next, Thu 19 Nov: Out with release 2 (Thu 19); a repository for the Integration Platform family, or drop that one addition. Owner: TechDocs.
- **Releases since 5 Nov (delta migration)**: on track (0 of 1 Jira items done). Refreshed Sun 15 (17 new versions) and checked against the live site Tue 17 (13 versions no batch had picked up); all are converted and on their way with release 2. The last refresh is Fri 27, before the old site closes. Next, Fri 27 Nov: Last catalog refresh; its new versions are converted the same day. Owner: TechDocs.
- **Old links keep working (redirects)**: at risk (1 of 4 Jira items done). Go-live needs the new site to load our redirect maps, or a date for it; no date is recorded yet (to confirm). Old addresses for help with no map are collected while the old site is up. Next, Fri 20 Nov: Go / no-go: redirect maps loaded, or a date. Owner: Digital Platform.
- **Backups of the original help packages**: on track (0 of 3 Jira items done). TIBCO is on the shared drive (1,988 of 2,018 versions; 30 are being obtained by hand, 29 more marked not needed), ibi on Google Drive. Next, Fri 27 Nov: Close the backups (ibi count confirmed). Owner: TechDocs.
- **Product teams' own requirements**: on track (0 of 5 Jira items done). Messaging, iProcess, Scribe and Streaming need more than conversion, and the publishing pipeline is being joined to PRISM and the product builds; most finish after 30 Nov. Next, to confirm: Each team's next step, noted as it moves. Owner: Engineering.
- **Translated help**: on track (1 of 2 Jira items done). Checks of the translated help are planned after 30 Nov. Next, after 30 Nov: Check the translated help on the new site. Owner: TechDocs.
- **Writers' spot-checks**: on track (0 of 2 Jira items done). Writers spot-check the migrated help after 30 Nov. Next, after 30 Nov: Writers spot-check each family. Owner: TechDocs.

## Effort

Work started Fri 25 Sep, 56 days ago. Effort logged in Jira: 66.5 points done, 24.5 in progress, 30 still to do (one point is one 8-hour day; Jira as of Thu 19 Nov).

- Converting the documentation: 33.25 done, 3.75 in progress, 3.75 to do
- Publishing to the new site: 0 done, 1 in progress, 0 to do
- Checking the new site (staging): 1.5 done, 3.25 in progress, 3.25 to do
- Problems found by the checks: 1.25 done, 5.25 in progress, 3.5 to do
- Go-live blockers on the new site: 0 done, 0 in progress, 1.25 to do
- Which Integration versions to publish (Karan's list): 0 done, 1 in progress, 0 to do
- Releases since 5 Nov (delta migration): 0 done, 1 in progress, 0 to do
- Old links keep working (redirects): 1 done, 1.25 in progress, 0 to do
- Backups of the original help packages: 0 done, 0.5 in progress, 0.75 to do
- Product teams' own requirements: 0 done, 1.75 in progress, 1 to do
- Translated help: 1 done, 1 in progress, 0 to do
- Writers' spot-checks: 0 done, 0 in progress, 7 to do
- Building the conversion tool, and earlier work: 28.5 done, 4.75 in progress, 9.5 to do

## What each team owes

**TechDocs**

- Mon 16 Nov, Decisions: Decide: Delta before go-live: which new versions from the 16 Nov catalog refresh go into release 2, and the cut-off for hand-supplied ZIPs
- Tue 17 Nov, Releases since 5 Nov (delta migration): Writers send the files of releases still in progress (by noon)
- Thu 19 Nov, Which Integration versions to publish (Karan's list): Out with release 2 (Thu 19); a repository for the Integration Platform family, or drop that one addition
- Fri 20 Nov, Checking the new site (staging): Sort the WebFOCUS check results
- Fri 20 Nov, Problems found by the checks: Read the re-check of what release 2 changed
- Fri 20 Nov, Decisions: Decide: The TIBCO versions with no package on the old site: 82 on 12 Nov. 13 Nov: 23 uploaded by hand (checksums verified), 29 marked not required by the user; 33 left (C:/tmp/handzips/still-missing.csv). 30 are for the user to obtain; 3 BW plug-in additions (K3) have never been tried, so the backup script fetches them after batch-fixes ends (it deletes workspace ZIPs).
- Mon 23 Nov, Publishing to the new site: Send the other ibi fixes to staging one repository at a time
- Fri 27 Nov, Converting the documentation: Convert what the last catalog refresh finds
- Fri 27 Nov, Releases since 5 Nov (delta migration): Last catalog refresh; its new versions are converted the same day
- Fri 27 Nov, Old links keep working (redirects): Collect old addresses for help with no redirect map
- Fri 27 Nov, Backups of the original help packages: Close the backups (ibi count confirmed)
- after 30 Nov, Translated help: Check the translated help on the new site
- after 30 Nov, Writers' spot-checks: Writers spot-check each family
- 85 kinds of problem found by the checks, 15 still to sort at the morning triage
- 60 open items in Jira

**Digital Platform**

- Fri 20 Nov, Go-live blockers on the new site: Keep full product folder names in the address (50-character limit), and serve the 9 missing versions
- Fri 20 Nov, Go-live blockers on the new site: Show pages under heading rows in the staging menu, or agree that we restructure our menus
- Fri 20 Nov, Old links keep working (redirects): Load the redirect maps on the new site, or give a date
- to confirm, Problems found by the checks: Answer the site problems reported in the UAT sheet
- 6 kinds of problem found by the checks
- 6 open items in Jira

**Engineering**

- to confirm, Which Integration versions to publish (Karan's list): Confirm or decline new Integration versions the catalog refreshes find
- to confirm, Releases since 5 Nov (delta migration): Support sends the end-of-support report with its retirement dates again
- to confirm, Product teams' own requirements: Each team's next step, noted as it moves
- 4 open items in Jira
