# Verify triage: Stage 2b (older TIBCO versions), 2026-11-16

This is a read-only triage. No repo file was edited, nothing was run, logged in Jira or pushed. `cache/state.db` was opened read-only while another batch was writing to it.

**What was checked:**
- **The batch:** the 81 lines of `cache/overnight/stage2-b.txt`, run Sun 15 Nov 22:02 to Mon 16 Nov 01:43 IST, all with `--refresh`. The outcomes are in `stage2-b.summary` and the logs in `stage2-b.logs/`. These are runs 2505–2648.
- **Re-run pending (excluded):** steps **001** (Hawk microagent for BW6 6.8.0), **002** (Gemini 5.0.2), **004** (Messaging EE 3.4.0) and **005** (Rendezvous 9.0.0). They crashed with "database is locked" and are being re-run in another batch.
- **No published folder (nothing to check):** 7 steps logged "No published version folders match this selection". They are Mosquitto bridge 2.0.7, Messaging 1.22.0, 1.25.0 and 1.27.0, Messaging EE 3.3.0, MDM Studio 5.3.0 and Mainframe RED 2.5.1. None of them has a result in `state.db`.
- **Triaged here:** the other **70 versions**. For each one, the latest result in `state.db` is this batch's run. The current `config/verify-triage.yaml` was applied to it the way `verify --retriage` does it, in memory. "Triage" here means the rule list that sorts each finding as known, logged in Jira, or accepted.
- **Evidence:**
  - the Markdown in `C:/github/tibco-docs-aem` (local `content-fix`, with `origin/wip` as of the last fetch, Sat 14 Nov 21:34);
  - the conversion record in `state.db`;
  - the staging pages that these runs cached in `cache/verify/`. No new staging fetch was made.
- **Verdicts reuse** `triage-batch2b-2026-11-15.md` and the two Batch 2 reports of 14 Nov wherever the kind is the same. The proposed entries are in `triage-stage2b-2026-11-16.yaml`.

**Where the batch stands now (70 versions):**
- 55 `lost`, 1 `issues`, 9 `logged`, 5 `clean`;
- **5,407** findings nobody has explained or logged yet. 2,665 of them come from one version (MDM 11.1.0, see N1).

**With the proposed entries (simulated):**

| Entries applied | lost | issues | logged | clean | Unlogged findings |
|---|---|---|---|---|---|
| none (today) | 55 | 1 | 9 | 5 | 5,407 |
| 3b + 3d (recommended) | 11 | 16 | 38 | 5 | 3,301 |
| 3b + 3d + 3c (with the optional "nested under the guide page" block) | 11 | 4 | 50 | 5 | 2,749 |

- **2,665 of what is left is MDM 11.1.0's lost redirects (N1).** This is a file to restore, not an entry to add. After the restore and a re-check, the batch would read 10 `lost`.
- **The 11 versions still `lost`:**
  - **6 wait for a decision on the 15 Nov re-conversion (N2):** Offer and Price Engine 6.0.0, Product and Service Catalog 5.1.0, Flogo 2.26.7 and 3.0.0, MDM 9.3.2 and Control Plane 1.17.0;
  - **MDM 11.1.0:** N1;
  - **4 have 1–4 small findings not traced yet (section 3):** iProcess Engine 11.9.2, BusinessConnect CE 1.6.1, Order Management 6.0.0 and TRA 5.12.4.
- **No version reads `explained`:** each has at least one finding logged in Jira.
- **Every proposed entry matches at least one finding:** 203 entries; 158 in 3b, 26 in 3d, 18 in 3c, 1 in 3e.

**Four things to know first:**
1. **A local commit wiped MDM 11.1.0's redirect file (new, ours; Critical before R2).** The DOCOPS-370 re-convert commit `7b05335` (Sun 15 Nov 19:49, Data Management repo, local `content-fix`, **not pushed**) deleted all **2,665 page rows** from `tibco-mdm/online-help/11-1-0/301.yml`. Only the 8 document rows are left. If this goes out with R2, every old MDM 11.1.0 link breaks at go-live. **The fix:** restore the file from `4a4a913` before any push. No other repo has the same wipe. The 301.yml changes since 14 Nov in every TIBCO repo were checked, and the other large deletions are Phase 80 folder moves, with their rows added back in the new folder.
2. **26 of the 70 versions are not on `wip` yet, so their staging checks mean nothing.** Their folders exist only on local `content-fix`:
   - **Phase 80 renames, committed but not pushed (13):** 12 BusinessConnect versions (`4bad5b4`) and PSC powered by EBX 1.0.0 (`8415181`);
   - **Karan's K3 additions, held for R2 (13):** Control Plane 1.4.0–1.17.0 (8), Platform 1.0.0 and 1.1.0, BusinessWorks 5.15.1 and 6.11.0, and SmartMapper 6.0.0 and 6.0.1.

   "No menu served" on these is expected. Block 3d logs them for now (DOCOPS-372 / DOCOPS-364), to be deleted after the R2 push and a re-verify. None of this batch's versions is in a repo that has not rebuilt (S1: General, Foresight, EMS, Adapters). The R002 and DOCOPS-370 commits of 14–15 Nov are local only, so staging still shows the 5 Nov content for these repos.
3. **The 15 Nov re-conversion changed the comparison for 8 versions (new, process).**
   - **Which:** Offer and Price Engine 6.0.0, PSC 5.1.0, Flogo 2.26.7 and 3.0.0, Service Grid 3.4.3, MDM 9.3.2 and 11.0.0, and Control Plane 1.17.0.
   - **What happened:** they were re-converted Sun morning for DOCOPS-370 but not synced, because their page list differs from what is published. So `verify` compares the **published** pages with the **new** conversion record, and reports pages that only the new conversion has.
   - **Example:** Flogo 2.26.7 "Oracle Database Call Procedure". The new record maps it to `oracle-database-call-procedure.md`, which is in neither the repo nor the new output. Published, it is a section of `oracle-database-query.md`, line 174.
   - **Effect:** these findings (missing topics and menu entries, about 40) are not real loss. Re-check after the 370 compare-and-sync decision. No entries are proposed for them.
4. **Some existing triage entries never match (tooling, small).**
   - **Version-level entries:** a "version not on staging" finding has an **empty** page path. So the 22 entries of 14 Nov written with `path: "*/online-help/<version>"` match nothing, and versions such as BC CMI 6.1.0 and BC CE EDI 6.11.0 read `lost` although they were triaged.
   - **Leading `*/`:** entries whose path starts with `*/` miss pages at the top of the version folder. Two examples: OPE 6.0.0 `installation-and-configuration-guide/docker.md` (DOCOPS-370) and BC CMI 6.1.0 `TIB_bccmi_user/preface.2.4.md` (support copy).
   - **What 3b/3d do:** the new entries for this batch avoid both problems.
   - **Suggestion:** drop the `path:` from the 22 version-level entries of 14 Nov, in a separate edit.

---

## 1. Summary table

| # | Kind (plain words) | Codes | Versions / findings | Verdict | Jira | Owner |
|---|---|---|---|---|---|---|
| **N1** | **MDM 11.1.0 redirect file wiped by the local 370 re-convert commit** (2,665 page rows gone) | `REDIRECT_UNMAPPED` | 1 / 2,665 | **ours, new: restore before push** | DOCOPS-370 (note) | TechDocs |
| N2 | **Re-converted 15 Nov, not synced:** verify compares the published pages with the newer conversion record (Flogo oracle "Call Procedure", Control Plane 1.17.0 RBAC pages, OPE index/browse, PSC GKE page) | `TOPIC_MISSING`, `TOC_ENTRY_MISSING`, some `TEXT_DROPPED` | 6 / ~45 | re-check after the 370 sync decision | DOCOPS-370 (note) | TechDocs |
| N3 | Triage entries that cannot match (empty version-level path; leading `*/`) | `PUBLISHED_PAGE_MISSING`, `TOC_ENTRY_MISSING`, `TEXT_DROPPED` | 22 entries; about 12 versions affected | tooling fix in the config | DOCOPS-338 (note) | TechDocs |
| S3 | **Not pushed yet** (Phase 80 renames: BusinessConnect and PSC-EBX; K3 additions: Control Plane, Platform, BW, SmartMapper) | `PUBLISHED_PAGE_MISSING` | 26 (25 with a finding) / 25 | temporary `logged` (block 3d) | DOCOPS-372, DOCOPS-364 | TechDocs (R2) |
| S2 | Pages served at their **menu** path, not their folder path (iProcess Engine `.../table-relationships-2/stat-rp-mins.html`, TRA `.../migrate-2-1/migrate-2-4.html`); redirect targets 404 at the folder path | `REDIRECT_UNSERVED` | 3 / 8 | existing issue | DOCOPS-351 | Digital Platform |
| P0 | **Pushed but not on staging:** ActiveSpaces 4.10.0, 5.0.0, 5.1.1 and 5.2.0 (no menu; on `wip` since 5 Nov) | `PUBLISHED_PAGE_MISSING`, `REDIRECT_UNSERVED` | 4 / 21 | existing issue, platform | DOCOPS-346 | Digital Platform |
| P1 | **Page served with an empty article** (0 words served against 1,240–3,340 in the Markdown): 30 pages: iProcess Engine 13, Flogo 3.0.0 6, Flogo 2.26.7 3, Rendezvous 8.8.0 4, iProcess Workspace (Windows) 2, Hawk RedTail 1, TRA 1 | `PUBLISHED_ANCHOR_MISSING` (and its pictures) | 7 / ~270 | existing issue, platform | DOCOPS-344 | Digital Platform |
| P2 | Pages after a heading row in the menu: dropped or moved, own path 404 | `PUBLISHED_TOC_ENTRY_MISSING`, a few `PUBLISHED_ANCHOR_MISSING` / `PAGE_MISSING` | 12 / ~110 | existing issue | DOCOPS-351 | Digital Platform |
| R1 | **No 301 rows for a second old folder** (PSC 5.1.0 `html-OPD/` and `html-relnotes/`; BC TCM 6.1.0 `bctcm/` and `webclient/`; BC PMP 1.0.0 `html-client/` and `html-server/`; BW 6.11.0 and MDM `relnotes/`; OPE index pages) | `REDIRECT_UNMAPPED` | 7 / 1,190 | existing issue | DOCOPS-322 | TechDocs |
| M1 | Support and legal copies kept once, at the end | `TOC_ENTRY_MISSING`, 1 `TOPIC_MISSING` | 13 / ~105 | accepted (design) | none | none |
| M2 | A topic under two parents, or sister guides paired crosswise | `TOC_MOVED` | 12 / ~110 | accepted | none | none |
| M4 | A guide's chapters (or a page's sections) at the top of the old menu, nested under the guide or page in `toc.yml` | `TOC_MOVED` | 18 / 552 | accepted? **open question (block 3c)** | none | none |
| M5 | Staging shows a page listed twice only once; MDM's Custom Guide listed under itself | `PUBLISHED_TOC_MOVED`, some `PUBLISHED_TOC_ENTRY_MISSING` | 13 / ~175 | accepted | none | none |
| M6 | Menu order under one parent | `TOC_ORDER`, `PUBLISHED_TOC_ORDER` | 6 / 10 | not triaged (warnings, as before) | none | TechDocs, later |
| A4 | Old menu names files the package does not ship (Service Grid archives, MDM ProcessExportArchive); ActiveSpaces `_globalpages` | `TOPIC_MISSING` | 5 / 12 | source; ActiveSpaces DOCOPS-349 | DOCOPS-349 | none |
| T1 | Content directly inside a list (OPE docker, Flogo oracle query, Control Plane 1.17.0 procedure titles) | `TEXT_DROPPED` | 4 / 5 | pending fix (re-converted, not synced) | DOCOPS-370 | TechDocs |
| T2 | `<placeholder>` unescaped inside bold or text (`<project >`, `<version>`, `<environment name>`); `&lt;` written literally | `TEXT_DROPPED` | 4 / 4 | existing issue; R002 does not cover it | DOCOPS-360 | TechDocs |
| T3 | Checker: `helm uninstall <...>` in code (Control Plane known issues ×8); `<img>` in a form-template sample (MDM ×54) | `TEXT_DROPPED`, `IMAGE_MISSING` | 10 / 62 | checker false positive | DOCOPS-366 | TechDocs |
| T4 | Overflow icon in a menu cascade dropped (BPM Enterprise 5.6.0, as 5.7.0); "default value is 1000" split over two lines (BC CE 1.6.1) | `IMAGE_MISSING`, `TEXT_DROPPED` | 2 / 5 | ours (DOCOPS-370) / accepted | DOCOPS-370 | TechDocs |
| A1–A4 | Anchors: bookmarks the source never defined (Flogo `#Configur`, Rendezvous `#rv_install_…`, iProcess `#pm_intro_…`); headings with code as dashes (Flogo 3.0.0); DITA `#SECTION_`/`#STEP_` (Service Grid 3.4.3); `SWDIR\logs\sw_warn` heading; WebWorks numeric-only headings (TRA) | `PUBLISHED_ANCHOR_MISSING` | 7 / 12 | source / existing issues | DOCOPS-362, 363, 345 | as before |

**Re-checks in this batch:**
- **Scribe Online, Flogo VS Code 1.3.5, FTL 7.1.3, Rendezvous Network Service 2.1.0, BC ebXML 6.4.0, BC Services 6.4.0, BC TCM 6.2.0, PSI 2.1.0 and Mainframe WebUI 2.5.0** stay `logged`.
- **Five versions are `clean`** (local-only stubs or PDF only): EFOS 1.1.0, iProcess Server Objects .NET 11.9.0, BPM Suite 4.2.0 and 4.3.1, and Platform 1.0.0.

---

## 2. Evidence

Repos are under `C:/github/tibco-docs-aem/<repo>/en-us/<slug>/online-help/<version>/`. Staging URLs start `https://stg-docs.tibco.com/us/en/`.

**N1, MDM 11.1.0 `301.yml`:**
- `git show --stat 7b05335` (en-us-tib-data-management-userdocs) reports `en-us/tibco-mdm/online-help/11-1-0/301.yml | 2665 ----`.
- The file now has 19 lines: the header and 8 `/content/dam/...` document rows.
- The previous run (2356, Sun 07:18 UTC, commit `4a4a913`) had no `REDIRECT_UNMAPPED`. This run (2564, commit `7b05335`) has 2,665. Example: `https://docs.tibco.com/pub/mdm/11.1.0/doc/html/...` has no row, although its topic is published.
- `git branch -a --contains 7b05335` lists only local `content-fix`, so nothing has been pushed.

**N2, the comparison against a newer conversion:**
- **Conversion after the last sync:** `stage_event` shows convert after sync for these 8 versions. For example, Flogo 2.26.7 was converted Sun 15 Nov 07:03 UTC and last synced Thu 5 Nov 08:01 UTC.
- **Flogo:** the findings say `oracledb_call_procedure.htm -> connectors-user-guide/oracle-database/oracle-database-call-procedure.md#…: no published page`. That file is not in the repo or in `output/en-us-tib-flogo/tibco-flogo/2.26.7/`. The published `oracle-database-query.md` has `## Oracle Database Call Procedure` (line 174) and the sections under it.
- **Control Plane 1.17.0:** `rule-based-access-controls.md` is named by the findings but is in neither the repo nor the output.

**S3, not pushed:**
- `git ls-tree origin/wip` has no folder for these 26 versions.
- **Phase 80:** `tibco-businessconnect-cmi-protocol/online-help/6-1-0` is new in `4bad5b4` (local), and staging is asked for `tibco-businessconnect-cmi-protocol/...` ("no menu served"). The plan lists BusinessConnect's and Fulfillment's Phase 80 pushes as still to do (`docs/closeout-plan.md`, line 82).

**P0, ActiveSpaces:**
- The folder `tibco-activespaces-enterprise-edition` is unchanged on `wip` (last there `8edf6dd`, 5 Nov).
- All four versions answer "no menu served" at `.../online-help/<v>/tibco-activespaces-enterprise-edition.html` and at `.../<v>.html`.
- 5.2.0 was already known: pages served, empty menu, DOCOPS-346.

**P1, empty article:**
- The cached staging pages were read, and the words in `main#section-topic div.topic-renderer__content` were counted.
- **Examples:** Rendezvous 8.8.0 `net-reference/listeners/listener.md` serves 0 words (3,022 in the Markdown). Hawk RedTail 6.3.1 `java-virtual-machine-plug-in-microagent.md` serves 0 (3,340).
- **Pages served at their menu path:** iProcess Engine 11.9.2 `.../administration-guide-sql-server/proc-audit-2/pm-objects-lock.html` serves 0 (S2 URL), and TRA 5.12.4 `.../migrate-2-1/migrate-2-4.html` serves 0.
- **Same pages as on the newer versions:** the Rendezvous pages are the four already logged for 9.0.0, and Flogo's `consul`, `websocket` and `configurehttpresponse` are logged for 3.0.1.
- **Pages next to them are served whole:** iProcess `architecture-guide.md` (2,967 of 2,978 words) and Flogo `about-tibco-flogo-flow-state-manager.md` (2,509 of 2,632).

**R1, second folders:**
- PSC 5.1.0 `301.yml` has 473 `doc/html/` rows and 59 `doc/html-OPD/` rows. The unmapped URLs are 476 under `html-OPD/` and 527 under `html-relnotes/`.
- BC TCM 6.1.0 and PMP 1.0.0 `301.yml` hold only the documents (9 lines), the same as TCM 6.2.0, which is already logged.

**M4, nested (open question):**
- All moves on Control Plane 1.4.0–1.17.0, Platform 1.1.0, PSC 5.1.0 and PSC-EBX 1.0.0 read `under (top) -> <guide or page>.md`. Example: `managing-capabilities/integration-businessworks-container-edition.md#app-details-page`, `under (top) -> managing-capabilities/integration-businessworks-container-edition.md`.
- Control Plane 1.20.0 (Batch 2) has the same 50 moves, still open.

**P2, after heading rows:**
- Hawk RedTail 6.3.1 `toc.yml` line 659: "Concepts" is `how-the-hawk-console-api-fits-in.md#concepts`. Line 661 follows it with `hawk-console-api/structure.md`, which staging answers 404.
- MDM 9.3.2 line 4239: "Workitem Forms and Email Templates Customization" follows heading rows such as `customizing-gui-colors.md#customizing-logo-bar`.

---

## 3. Per-version table

Status: *now* is today; *3b+3d* is with the recommended blocks; *+3c* adds the optional nested block. "Local only" means the folder is not on `wip`.

| Step | Version | Now | 3b+3d | +3c | Main kinds / what is left |
|---|---|---|---|---|---|
| 001, 002, 004, 005 | Hawk microagent BW6 6.8.0, Gemini 5.0.2, Messaging EE 3.4.0, Rendezvous 9.0.0 | re-run pending | | | crashed: database is locked |
| 003, 029–032, 066, 077 | Mosquitto bridge 2.0.7, Messaging 1.22.0/1.25.0/1.27.0, Messaging EE 3.3.0, MDM Studio 5.3.0, Mainframe RED 2.5.1 | no published folder | | | nothing to check |
| 006 | Scribe Online | logged | logged | logged | |
| 007 | Flogo VS Code 1.3.5 | logged | logged | logged | |
| 008 | BC CMI 6.1.0 (local only) | lost | logged | logged | S3, M1 |
| 009, 043 | BC CE CMI 1.2.1, 1.1.0 (local only) | lost | logged | logged | S3 |
| 010 | BC CE EDI HIPAA 1.3.0 (local only) | lost | logged | logged | S3 |
| 011, 046 | BC CE RosettaNet 1.7.0, 1.6.0 (local only) | lost | logged | logged | S3 |
| 012, 047 | BC CE SOAP 1.3.0, 1.2.1 (local only) | lost | logged | logged | S3 |
| 013 | BC ebXML 6.4.0 | logged | logged | logged | |
| 014, 048 | BC EDI 6.11.0, 6.10.0 (local only) | lost | logged | logged | S3, M1 |
| 015 | BC PMP 1.1.1 | issues | issues | logged | M4 (1) |
| 016 | BC SSH Server 1.1.0 | lost | logged | logged | M1 |
| 017, 018 | BC Services 6.4.0, BC TCM 6.2.0 | logged | logged | logged | |
| 019 | EFOS 1.1.0 | clean | clean | clean | |
| 020 | Offer and Price Engine 6.0.0 | lost | lost | lost | R1, T1; **left: N2** (index/browse, 4) |
| 021 | PSC 5.1.0 | lost | lost | lost | R1 (1,003); M4 (14); **left: N2** (GKE page 2), 2 pictures (N2, not traced) |
| 022 | PSI 2.1.0 | logged | logged | logged | |
| 023, 058 | SmartMapper 6.0.1, 6.0.0 (local only) | lost | logged | logged | S3, M1 |
| 024 | MDM 11.1.0 | lost | lost | lost | **N1** (2,665); M4 (7) |
| 025 | Platform 1.1.0 (local only) | lost | issues | logged | S3, M4 (51) |
| 026, 079, 080, 081 | ActiveSpaces 5.2.0, 4.10.0, 5.0.0, 5.1.1 | lost | logged | logged | P0, A4 |
| 027 | Hawk Database Adapter 6.2.0 | lost | logged | logged | M1 |
| 028 | Hawk RedTail 6.3.1 | lost | issues | issues | P1, P2, M5; left 1 `PUBLISHED_TOC_ORDER` |
| 033 | Rendezvous 8.8.0 | lost | issues | issues | P1 (4 pages), P2, M5, A1; left 1 `TOC_ORDER` |
| 034 | Rendezvous Network Service 2.1.0 | logged | logged | logged | |
| 035 | FTL 7.1.3 | logged | logged | logged | |
| 036 | Flogo 2.26.7 | lost | lost | lost | P1, P2, M2, M5, S2, T1; **left: N2** (oracle Call Procedure 15, MQTT 9 sentences, 3 single headings, 1 picture), 2 order |
| 037 | Flogo 3.0.0 | lost | lost | lost | P1 (6 pages), T1, A2; **left: N2** (16) |
| 038 | iProcess Engine 11.9.2 | lost | lost | lost | P1 (13 pages), P2, M5, M4 (78); left 3 anchors on `architecture-guide.md` (toc rows to headings the page does not have; not traced), 4 order |
| 039 | iProcess Server Objects .NET 11.9.0 | clean | clean | clean | |
| 040 | iProcess Workspace (Browser) 11.9.0 | lost | logged | logged | P2, M5, S2 |
| 041 | iProcess Workspace (Windows) 11.9.2 | lost | logged | logged | P1 (2 pages), A1 |
| 042 | BC Container Edition 1.6.1 | lost | lost | lost | P2, M5, T4; left 1 picture (`add-icon-1_18x18.jpg`, not traced) |
| 044 | BC CE ebXML 1.2.1 (local only) | lost | logged | logged | S3, M2 |
| 045 | BC CE EDI 1.5.0 (local only) | lost | logged | logged | S3, M2 |
| 049 | BC PMP 1.0.0 | lost | issues | logged | R1 (70), M1, M4 (1) |
| 050 | BC Services 6.3.0 | lost | logged | logged | M1 |
| 051 | BC TCM 6.1.0 | lost | logged | logged | R1 (81), M1 |
| 052 | Fulfillment Provisioning 3.9.0 | lost | issues | issues | P2, M5, S2, T2; left 1 order |
| 053 | Order Management 6.0.0 | lost | lost | lost | M2, M5; left 1 `TOPIC_MISSING` (`_shared/archival-service.htm`, not traced) |
| 054 | PSC powered by EBX 1.0.0 (local only) | lost | issues | logged | S3, M1, M4 (6) |
| 055 | TRA 5.12.4 | lost | lost | lost | M1 (28), P1, A1; left 3 pictures (palette 4.05, 4.38) and 1 sentence (install.3.15), not traced |
| 056 | BusinessWorks 5.15.1 (local only) | lost | logged | logged | S3, M1 |
| 057 | BusinessWorks 6.11.0 (local only) | lost | issues | issues | S3, R1 (23), M2, M4 (19); left 1 `TOC_ORDER` |
| 059 | AMX Service Grid 3.4.3 | lost | logged | logged | M2, M5, P2, A3, A4 (N2 version; nothing left) |
| 060 | BPM Enterprise 5.6.0 | lost | logged | logged | M2, T4 |
| 061, 062 | BPM Suite 4.2.0, 4.3.1 | clean | clean | clean | |
| 063 | Business Studio BPM 5.6.0 | lost | logged | logged | M2, M5, T2 |
| 064 | MDM 9.3.2 | lost | lost | lost | R1, M1, M2, M4, M5, P2, T3, A4; **left: N2** (3 sentences on `tibco-mdm.md` and others) |
| 065 | MDM 11.0.0 | lost | issues | logged | R1, M1, M2, M4 (8), M5, P2, T2, T3 |
| 067 | MDM Studio 6.1.0 | lost | logged | logged | M2, M5, P2, T2 |
| 068–074 | Control Plane 1.4.0, 1.5.1, 1.7.0, 1.9.0, 1.11.0, 1.13.0, 1.15.0 (local only) | lost | issues | logged | S3, T3, M4 (38–50 each) |
| 075 | Control Plane 1.17.0 (local only) | lost | lost | lost | S3, T1, T3, M2, M4; **left: N2** (RBAC 12), 1 picture |
| 076 | Platform 1.0.0 (local only) | clean | clean | clean | PDF only |
| 078 | Mainframe WebUI 2.5.0 | logged | logged | logged | |

---

## 4. Proposed entries

All proposed entries are in `reports/verify/triage-stage2b-2026-11-16.yaml`. It was checked to load after the current file's entries, with its anchors.

- **3b (158 entries):** paste directly above `  # Catch-alls: keep last`, after the Batch 2b block.
- **3d (26, temporary):** with 3b. These are the not-pushed versions; delete them after the R2 push and a re-verify.
- **3c (18, optional):** the "nested under the guide page" moves, still the open question of 14 Nov.
- **3e (1, not recommended):** MDM 11.1.0 only. Restore `301.yml` instead.
- **No entry for:**
  - **N2:** re-check after the 370 sync decision;
  - **the `TOC_ORDER` warnings:** as on 14 Nov;
  - **7 small findings not traced:** iProcess `architecture-guide.md` (3), BC CE 1.6.1 (1 picture), Order Management archival-service (1), and TRA (3 pictures, 1 sentence).

---

## 5. Jira changes (to apply when you choose; none was made)

| Issue | Change | Points |
|---|---|---|
| DOCOPS-370 | Note, **urgent:** commit `7b05335` (Data Management, local) deleted the 2,665 page rows of MDM 11.1.0's `301.yml`. Restore it from `4a4a913` before the R2 push, and add a check that a re-convert never shrinks `301.yml`. Also note that 8 re-converted versions are not synced, so verify reads the new conversion record for them (N2). | +0.25 |
| DOCOPS-346 | Note: ActiveSpaces 4.10.0, 5.0.0 and 5.1.1 are not served either (no menu), on `wip` since 5 Nov, as 5.2.0. | none |
| DOCOPS-344 | Note: 30 more empty-article pages (iProcess Engine 11.9.2 ×13, Flogo 3.0.0 ×6, Flogo 2.26.7 ×3, Rendezvous 8.8.0 ×4, iProcess Workspace (Windows) ×2, Hawk RedTail 6.3.1, TRA 5.12.4). | none |
| DOCOPS-322 | Note: second old folders, with no 301 rows, on PSC 5.1.0 (1,003), BC TCM 6.1.0 (81), BC PMP 1.0.0 (70), BW 6.11.0 (23) and MDM 9.3.2/11.0.0 (12). | none |
| DOCOPS-351 | Note: 12 more versions with pages after heading rows. iProcess Engine and TRA pages are served at their menu path. | none |
| DOCOPS-338 | Note: Stage 2b triaged. 55 lost go to 11 with 3b+3d. 26 versions are local-only (R2). Fix the 22 version-level entries whose `path` cannot match. | none |
| DOCOPS-372 / DOCOPS-364 | Note: verify cannot see the BusinessConnect/Fulfillment renames or the K3 additions until R2; re-verify them after the push. | none |

---

## 6. UAT-sheet rows (Digital Platform)

These are rows for kinds not yet in the sheet. DOCOPS-344 (empty article) and DOCOPS-351 are there already: add the new examples to their Comments.

```csv
Type,Issue description,Issue screenshot,Category,Priority,Found In,Reporter,Status,Assignee,Stage Issue link,Prod Issue link,Comments,DEV status / comment
Desktop,"Four ActiveSpaces versions are not on staging: no menu and no version page, although the folder has been on wip and main since 5 Nov (unchanged since). 4.10.0, 5.0.0, 5.1.1 and 5.2.0 all answer 'no menu' at the version page; the redirect targets sampled for 5.0.0 and 5.1.1 are 404 as well. GitHub: https://github.com/tibco/en-us-tib-activespaces-userdocs/tree/wip/en-us/tibco-activespaces-enterprise-edition/online-help/5-1-1",,Content,Critical,"TIBCO ActiveSpaces Enterprise Edition 4.10.0, 5.0.0, 5.1.1, 5.2.0",Mayur,New,,https://stg-docs.tibco.com/us/en/tibco-activespaces-enterprise-edition/online-help/5-1-1.html,,"DOCOPS-346; verify Sun 15 Nov 20:11-20:13 UTC",
```

---

## 7. Open questions

1. **MDM 11.1.0 (N1).** Restore `301.yml` from `4a4a913` on `content-fix` now? It is a local commit, so restoring it is a repo change and needs your go-ahead.
2. **N2.** For the 8 versions re-converted but not synced, which is right: compare first and sync the new conversion with R2, or keep the published copy and reset the conversion record? Verify will keep reporting differences until one of the two happens.
3. **Nested moves (M4, block 3c).** This is still the 14 Nov question. It now covers 18 versions, including all of Control Plane.
