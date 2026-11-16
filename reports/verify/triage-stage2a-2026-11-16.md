# Verify triage: Stage 2a (older TIBCO versions on current staging), 2026-11-16

This is a read-only triage: no repo file was edited, nothing was run, logged or pushed. The data is each version's latest run in `cache/state.db` for the 82 lines of `cache/overnight/stage2-a.txt`: runs 2504–2670, made Sun 15 Nov 22:12 to Mon 16 Nov 03:04 IST, all with `--refresh`. The current `config/verify-triage.yaml` was applied the way `verify --retriage` applies it (`triage.decide`, `issues.tally`), in memory. Evidence comes from the Markdown in `C:/github/tibco-docs-aem` (local `content-fix` and `origin/wip`), the extracted packages under `families/`, and the staging pages these runs cached in `cache/verify/` (no new staging fetch).

Verdicts reuse the 14 and 15 Nov reports where the kind is the same. Short names used below: **lost** = a version with unexplained errors; **issues** = only unexplained warnings; **logged** = every finding explained and at least one is a known Jira problem; **explained** = every finding explained, none open in Jira; **clean** = no finding.

**Where the batch stands now.** 82 lines, of which 7 had nothing to check (no published folder, see "Things to know" 4). Of the 75 checked: **49 lost, 1 issues, 20 logged, 5 clean**, with **3,865 unexplained findings**.

**With the proposed changes (simulated):**

| | lost | issues | logged | explained | clean | unexplained findings |
|---|---|---|---|---|---|---|
| Now | 49 | 1 | 20 | 0 | 5 | 3,865 |
| A only (fix 29 existing entries that never match) | 44 | 3 | 23 | 0 | 5 | 3,852 |
| A + B (new Stage 2a entries) | 20 | 11 | 38 | 1 | 5 | 658 |
| A + B + C (optional "nested under the guide page") | 20 | 4 | 45 | 1 | 5 | 27 |

- **The 20 still lost are not content problems.** 19 are versions whose folders exist only in local commits that are not pushed (point 1 below); 1 is Hawk Redtail 7.5.0 (a page answered with an error once during the run, and the known Error Codes 500).
- **The 4 issues** are 4 menu-order warnings (`TOC_ORDER`), left untriaged as on 14 and 15 Nov, plus one staging menu-order warning on BusinessWorks 6.12.0.
- **The 631 findings that block C** are all one kind: the old menu lists a guide's chapters at the top, our menu nests them under the guide page (the 14 Nov open question). Control Plane (10 versions), Platform CLI 1.2.0, BusinessWorks 5.16.1 and 6.12.0, iProcess Engine 11.9.1, MDM Studio 6.0.0, Partner Management Portal 1.1.0, Product and Service Catalog EBX 1.1.0.
- **Explained:** iProcess Workspace Plug-ins 11.9.0. Its 2 findings are the live site's newer legal wording.
- Every proposed entry matches at least one stored finding (checked over every version's latest run, not only this batch).

**Things to know first:**

1. **19 versions are "lost" only because their folders are not pushed.** Verify read the local `content-fix` branches. Five repos have commits there that are not on `origin/wip`:
   - **Phase 80 folder renames (14 Nov 21:32):** BusinessConnect (`4bad5b4`), Fulfillment (`8415181`), ActiveSpaces (`0ab259e`). Verify asks staging for the new short names (`tibco-businessconnect-ce-ebxml-protocol/...`), which staging has never seen. 9 versions: BC CE ebXML 1.3.0, CE EDI 1.6.0 and 1.6.1, CE Services Plug-in 1.6.0 and 1.7.0, CE CMI 1.2.0, CE EDI HIPAA 1.2.0, BC EDI HIPAA 6.7.0, Product and Service Catalog EBX 1.1.0.
   - **K3 additions (13 Nov 17:01–17:03):** Control Plane 1.3.0–1.17.0 and Platform 1.1.0 (`02b5801`…`fad28d8`), BusinessWorks 5.15.0 (`135c82f`), BWCE 2.10.0 (`e6d9a01`). 10 versions in this batch: Control Plane 1.3.0, 1.5.0, 1.6.0, 1.8.0, 1.10.0, 1.12.0, 1.14.0, 1.16.0; BW 5.15.0; BWCE 2.10.0.
   - R002 (14 Nov) and the DOCOPS-370 list fix (15 Nov 19:48) are in the same unpushed stacks.
   - Verdict: **not pushed** (call it S3). No triage entry; re-verify after the R2 push. The version pages answer 404 (`.../tibco-control-plane/online-help/1-3-0.html`, cached 16 Nov 02:39).
2. **No version in this batch is in a repo that staging has not rebuilt** (General, Foresight, EMS, Adapters). S1 does not apply here. The two Adapters entries in A3 are fixed only so that they work once the Adapters rebuild lands.
3. **29 existing triage entries can never match, so versions read "lost" although their problem is logged.** Triage compares the path *inside* the version folder, and a version-level finding has an empty path.
   - 20 entries start with `*/` before a top-level folder: `"*/release-notes/known-issues.md"` never matches `release-notes/known-issues.md`. Hit in this batch: Control Plane 1.20.0, Platform CLI 1.2.0, Fulfillment Provisioning 3.10.0, Order Management 6.1.0, RosettaNet 5.3.0.
   - 9 version-level "not on staging" entries carry a path (`"*/online-help/1-3-0"`), and one page entry carries the version folder (`"*/7-5-0/error-codes/..."`).
   - Part A of the YAML lists every line and the fix. The 11 BusinessConnect and Catalog EBX entries are deliberately **not** fixed, because of point 1.
4. **7 lines had nothing to check.** `No published version folders match`: Messaging 1.21.0, 1.24.0, 1.26.0, 1.30.0; Mosquitto Core 2.0.7; MDM 10.0.0 (sync failed 15 Oct); BC Trading Community Management 6.1.1 (6.1.0 and 6.2.0 are published, 6.1.1 is not). `versions.csv` says "synced" for six of them, so the list builder took them in. They are not migration losses.
5. **Staging serves pages at their menu path, not their folder path. This is general, not a Transaction Insight quirk.** 2b's S2 is now seen on Flogo, BPM Enterprise, BusinessWorks, Control Plane, iProcess, MDM Studio and Order Management. Example: Flogo 2.26.8 `connectors-user-guide/amazon-sqs.md` is served at `.../2-26-8/connectors-user-guide/creating-connections/amazon-sqs.html`, and its folder path `.../connectors-user-guide/amazon-sqs.html` is 404. Two consequences:
   - The sampled redirect targets fail (46 in 8 versions). If AEM does not turn our 301 rows (written as Markdown paths) into the served URL, **redirects break at go-live**. Candidate **Critical** for the UAT sheet.
   - Verify finds a page's URL in the menu by its title. Where two pages share a title ("Output", "Advanced", "Introduction", "Plan Item"), it compares with the wrong one: **28 pages, 178 anchor findings** that are not real (checker, DOCOPS-366).
6. **Pages served with an empty article (DOCOPS-344): 41 more pages in 6 versions.** iProcess Engine 11.9.1 (13 database-administration pages), Flogo 2.26.6 and 2.26.8 (7 each), BW 6.12.0 (the same 6 as 6.13.0), Rendezvous 8.8.1 (4), ActiveMatrix BPM 4.2.0 (4). The served page holds only the site's frame (about 230–250 words); the Markdown has 500–3,000. This is the largest real reader-facing loss in the batch: 296 anchor and 73 picture findings sit on these pages.
7. **No new converter bug.** The content findings are known kinds, on versions converted before the fixes:
   - DOCOPS-360: placeholders in bold, now also BPM Enterprise 4.3.5 (5 pages);
   - DOCOPS-370: blocks directly inside a list, BW 5.16.1, BW 6.12.0 and Flogo 2.26.6;
   - DOCOPS-373: DITA table descriptions, ActiveMatrix BPM 4.2.0;
   - DOCOPS-366: MDM Studio's two builds, 6.0.0.

   The new problems are in our tooling: the 29 dead triage entries (point 3), and the checker's same-title pairing (point 5).

---

## 1. Summary table

| # | Kind (plain words) | Codes | Versions / findings | Verdict | Jira | Owner |
|---|---|---|---|---|---|---|
| S3 | **Folder only in local, unpushed commits** (Phase 80 renames, K3 additions); staging 404 | `PUBLISHED_PAGE_MISSING` (version) | 19 / 19 | **not pushed**; no entry, re-verify after R2 push | DOCOPS-338 note | TechDocs |
| S2 | **Pages served at their menu path**; sampled 301 targets by folder path 404 | `REDIRECT_UNSERVED` | 8 / 46 | platform (URL rule), open question 1 | DOCOPS-351 | Digital Platform |
| S4 | Page answered with an error once during the run (Redtail `hawk-console-api/structure.html`, 200 when cached at 22:13) | `PUBLISHED_PAGE_MISSING`, `REDIRECT_UNSERVED` | 1 / 3 | transient; no entry, re-check | none | none |
| X1 | **Existing entries that never match** (`*/` before a top-level folder; path on version-level entries) | many | 29 entries | ours (triage file), fix A | DOCOPS-338 note | TechDocs |
| P1 | **Page served with an empty article** (41 pages) | `PUBLISHED_ANCHOR_MISSING` 296, `PUBLISHED_IMAGE_BROKEN` 73 (moved from the 347 catch-all) | 6 / 369 | existing issue, platform | DOCOPS-344 | Digital Platform |
| P2 | **Heading-row menus** (older conversions: toc.yml mostly `page.md#anchor` rows; Flogo 2.26.6 595 of 805, BPM 4.3.5 4,455 of 4,876); staging drops, moves or reorders the pages after them | `PUBLISHED_TOC_MOVED` 480, `PUBLISHED_TOC_ENTRY_MISSING` 390, `PUBLISHED_TOC_ORDER` 22 | 13 / 892 | existing issue | DOCOPS-351 | Digital Platform (re-convert would also clear it) |
| P3 | Empty menu on a served version (ActiveSpaces 4.10.1, 5.1.0, as 5.2.0) | `PUBLISHED_PAGE_MISSING` | 2 / 2 | existing issue | DOCOPS-346 | Digital Platform |
| P4 | Error Codes answers 500 (Redtail 7.5.0, third time) | `PUBLISHED_PAGE_MISSING` | 1 / 1 | existing issue (entry fixed in A) | DOCOPS-344 | Digital Platform |
| M1 | Support/legal copies (and DITA Important Information) kept once, at the end | `TOC_ENTRY_MISSING` | 12 / 64 | accepted (design) | none | none |
| M2 | Topic under two parents, or a merged page's section paired with the other parent | `TOC_MOVED` | 15 / 263 | accepted (crosswise) | none | none |
| M3 | DITA "Important Information" moves (AMX BPM 4.2.0) | `TOC_MOVED` | 1 / 15 | checker | DOCOPS-366 | TechDocs |
| M4 | **A guide's chapters at the top of the old menu, nested under the guide page in ours** | `TOC_MOVED` | 17 / 631 | accepted? (open question 2, block C) | none | none |
| M5 | Staging shows a page listed twice only once | `PUBLISHED_TOC_MOVED` | 3 / 18 | accepted | none | none |
| M6 | Menu order under one parent | `TOC_ORDER`, `PUBLISHED_TOC_ORDER` | 5 / 5 | not triaged (warnings) | none | TechDocs, later |
| R1 | **No page rows in 301.yml**: BC 7.4.0 (help served twice, `bcgs/` and `bcis/`, as 7.5.0); BW 6.12.0 and 5.16.1 old `relnotes/` folder | `REDIRECT_UNMAPPED` | 3 / 1,061 | existing issue | DOCOPS-322 | TechDocs |
| T1 | `<placeholder>` unescaped inside bold (`<launched>`, `<Application Name>`, `<severity >`, `<Ctrl >`, `<project >`) | `TEXT_DROPPED` | 3 / 17 | existing issue; R002 does not cover it | DOCOPS-360 | TechDocs |
| T2 | Entity shown as text in the source (`&apos;`, `&lt;`) | `TEXT_DROPPED` | 2 / 2 | existing issue | DOCOPS-360 | TechDocs |
| T3 | Block or picture directly inside a list (license-error list, "A confirmation message…", Import screenshot in `<ol>`) | `TEXT_DROPPED` 6, `IMAGE_MISSING` 7 | 4 / 13 | pending re-convert (fix built 15 Nov) | DOCOPS-370 | TechDocs |
| T4 | DITA table description dropped (AMX BPM 4.2.0, the same 2 pages as 4.3.0) | `TEXT_DROPPED` | 1 / 2 | existing issue | DOCOPS-373 | TechDocs |
| T5 | Checker: MDM Studio 6.0.0 two builds (`html/`, `relnotes/`); example code read as pictures (`path/?.gif`, `<![CDATA[`); `\-` in `<pre>`; backticks in `<code>` (Control Plane ×10, CLI); four-backtick fence (BW 6.12.0 Design Assistant prompts); ENTRYPOINT line; Flogo 2.26.6 Call Procedure published as a section | `IMAGE_MISSING` 229, `TEXT_DROPPED` 26, `TOPIC_MISSING` 6, `TOC_ENTRY_MISSING` 6 | 8 / 267 | checker | DOCOPS-366 | TechDocs |
| T6 | **Checker: same-title pairing** through the menu (BW 5.16.1 `palette-reference/output-4.md` compared with `.../output-7.html`) | `PUBLISHED_ANCHOR_MISSING` | 6 / 178 | checker, new variant | DOCOPS-366 | TechDocs |
| A1 | Staging heading ids: `®` kept; raw ids starting with `/`; headings with emphasis or underscores (not traced) | `PUBLISHED_ANCHOR_MISSING` | 5 / 18 | existing issue | DOCOPS-345 | Digital Platform |
| A2 | Heading with code written as dashes (`----------`, `` (`CONFIG_HOME)` ``, `if/else`) | `PUBLISHED_ANCHOR_MISSING` 2, `TOC_ENTRY_MISSING` 2 | 2 / 4 | pending re-convert | DOCOPS-362 | TechDocs |
| A3 | DITA ids not kept (`#GUID-…__ID-…`, `#ID-209-…`) | `PUBLISHED_ANCHOR_MISSING` | 1 / 18 | existing issue | DOCOPS-363 | TechDocs |
| A4 | Heading with an escaped `<` (`$_error_&lt;activityName>`) | `PUBLISHED_ANCHOR_MISSING` | 1 / 1 | existing issue | DOCOPS-353 | TechDocs |
| A5 | Source: link to a bookmark no page defines (`#rv_install_…`, `#release_…`, `#1`, `#bookmark=id.…`, `#Configur`, `#USE-BY-REFERENCE`); archive topics not shipped (BPM 4.3.5, 8) | `PUBLISHED_ANCHOR_MISSING` 12, `TOPIC_MISSING` 8 | 7 / 20 | source | none | none |
| A6 | Flare `_globalpages/` topics skipped (ActiveSpaces 4.10.1, 5.1.0) | `TOPIC_MISSING` | 2 / 5 | existing issue | DOCOPS-349 | TechDocs |
| L1 | Live site's newer legal wording ("Cloud Software Group, Inc.") | `LIVE_DRIFT` | 1 / 2 | accepted | none | none |

---

## 2. Per version

"Now" is today's stored status. "A+B" and "A+B+C" are simulated. "Left" counts the findings still unexplained after A+B+C.

| Version | Now (errors / warnings) | A+B | A+B+C | Left | Main kinds |
|---|---|---|---|---|---|
| Hawk Database Adapter 6.2.1 | logged | logged | logged | 0 | |
| Hawk Redtail 7.5.0 | lost (4/0) | lost | lost | 3 | S4 transient; P4 Error Codes 500 |
| Messaging 1.31.0 | clean | clean | clean | 0 | PDF-only stub |
| Kafka Schema Repository 2.1.0 | logged | logged | logged | 0 | |
| Rendezvous Network Service 2.2.0 | logged | logged | logged | 0 | |
| Flogo 3.0.1 | logged | logged | logged | 0 | |
| BusinessConnect 7.5.0 | logged | logged | logged | 0 | |
| BC Container Edition 1.7.1 | logged | logged | logged | 0 | |
| BC CE ebXML 1.3.0 | lost (1/0) | lost | lost | 1 | S3 renamed, not pushed |
| BC CE EDI 1.6.1 | lost (1/0) | lost | lost | 1 | S3 |
| BC CE Services Plug-in 1.7.0 | lost (1/0) | lost | lost | 1 | S3 |
| BC cXML 6.1.0 | logged | logged | logged | 0 | |
| BC EDI HIPAA 6.7.0 | lost (5/0) | lost | lost | 1 | S3; M1 (fixed by A) |
| BC Palette 6.6.0 | logged | logged | logged | 0 | |
| BC Plug-in for FTP Server 1.0.1 | logged | logged | logged | 0 | |
| BC RosettaNet 5.3.0 | lost (4/0) | logged | logged | 0 | M1 (A) |
| BC SOAP 7.2.0 | logged | logged | logged | 0 | |
| Trading Partner Mgmt REST API 1.1.0 | logged | logged | logged | 0 | |
| Fulfillment Provisioning 3.10.0 | lost (1/0) | logged | logged | 0 | T2 (A) |
| Order Management 6.1.0 | lost (1/0) | logged | logged | 0 | T5 (A) |
| Product and Service Catalog EBX 1.1.0 | lost (1/6) | lost | lost | 1 | S3; M4 |
| Product and Service Inventory 2.1.0 | logged | logged | logged | 0 | |
| BWCE 2.10.0 | lost (1/26) | lost | lost | 1 | S3 (K3, not pushed); M2 |
| Control Plane 1.20.0 | lost (1/50) | issues | logged | 0 | M4; T5 (A) |
| Platform CLI 1.2.0 | lost (1/48) | issues | logged | 0 | M4; T5 (A) |
| BusinessEvents 6.4.0 | logged | logged | logged | 0 | |
| Hawk Microagent BW6 6.7.2 | logged | logged | logged | 0 | |
| Kafka Schema Repository 2.0.0 | logged | logged | logged | 0 | |
| Rendezvous 8.8.1 | lost (63/23) | issues | issues | 1 | P1 (4 pages); P2; A5; M6 |
| eFTL 7.1.3 | logged | logged | logged | 0 | |
| Flogo 2.26.6 | lost (52/49) | logged | logged | 0 | P1 (7 pages); P2; S2; T3; T5 Call Procedure; A2 |
| Flogo 2.26.8 | lost (36/52) | logged | logged | 0 | P1 (7 pages); P2; S2 |
| iProcess Engine 11.9.1 | lost (170/130) | issues | logged | 0 | P1 (13 pages); P2; S2; M4; A1 |
| iProcess Server Objects Java 11.9.0 | clean | clean | clean | 0 | stub |
| iProcess Technology Plug-ins 11.9.2 | lost (1/0) | logged | logged | 0 | P2 |
| iProcess Workspace Plug-ins 11.9.0 | issues (0/2) | explained | explained | 0 | L1 |
| BusinessConnect 7.4.0 | lost (1,007/0) | logged | logged | 0 | R1 (two folders) |
| BC Container Edition 1.7.0 | lost (2/0) | logged | logged | 0 | split default value; add icon |
| BC CE CMI 1.2.0 | lost (1/0) | lost | lost | 1 | S3 |
| BC CE EDI HIPAA 1.2.0 | lost (1/0) | lost | lost | 1 | S3 |
| BC CE EDI 1.6.0 | lost (1/1) | lost | lost | 1 | S3; M2 |
| BC CE Services Plug-in 1.6.0 | lost (1/0) | lost | lost | 1 | S3 |
| BC ebXML 6.3.0 | lost (8/0) | logged | logged | 0 | M1 |
| BC Palette 6.5.0 | logged | logged | logged | 0 | |
| BC Partner Management Portal 1.1.0 | lost (2/1) | issues | logged | 0 | M1; M4 |
| BC SOAP 7.1.0 | lost (4/0) | logged | logged | 0 | M1 |
| Order Management 5.0.1 | lost (45/28) | logged | logged | 0 | P2; S2; T6 |
| Order Management 6.0.1 | lost (1/18) | logged | logged | 0 | M2; M5; P2 |
| Administrator 5.12.4 | lost (8/0) | logged | logged | 0 | M1 |
| BusinessWorks 5.15.0 | lost (25/0) | lost | lost | 1 | S3 (K3); M1 |
| BusinessWorks 5.16.1 | lost (121/53) | issues | logged | 0 | T6 (10 pages); P2; R1; T3; A4; A5; M4 |
| BusinessWorks 6.12.0 | lost (117/94) | issues | issues | 2 | P1 (6 pages); R1; T1; T3; A1; M2; M4; M6 |
| ActiveMatrix BPM 4.2.0 | lost (229/250) | issues | issues | 1 | P1 (4); T6 (11); P2; T4; T5; M2; M3; M6 |
| BPM Enterprise 4.3.5 | lost (236/148) | logged | logged | 0 | P2; T6; T1 (5 pages); T5; A3; A5 |
| BPM Enterprise 5.6.1 | lost (4/5) | logged | logged | 0 | overflow icon (T3); M2 |
| BPM Suite 4.3.0 | clean | clean | clean | 0 | stub |
| Business Studio Analyst 4.2.0 | clean | clean | clean | 0 | stub |
| Business Studio BPM 5.6.1 | lost (1/11) | logged | logged | 0 | T1; M2; M5 |
| MDM Studio 5.2.0 | lost (38/8) | issues | issues | 1 | P2; M1; M2; M6 |
| MDM Studio 6.0.0 | lost (165/18) | issues | logged | 0 | T5 two builds (159); P2; M2; M4 |
| Control Plane 1.3.0, 1.5.0, 1.6.0, 1.8.0, 1.10.0, 1.12.0, 1.14.0, 1.16.0 (8) | lost (2/38–50 each) | lost | lost | 1 each | S3 (K3); M4; T5 |
| Control Plane 1.19.0 | lost (45/60) | issues | logged | 0 | P2; S2; T6; M4; T5 |
| Platform CLI 1.1.0 | clean | clean | clean | 0 | stub |
| Mainframe TCP Library 2.5.0 | logged | logged | logged | 0 | |
| RED Enabled for zIIP 2.5.0 | logged | logged | logged | 0 | |
| ActiveSpaces 4.10.1 | lost (5/0) | logged | logged | 0 | P3; A6 |
| ActiveSpaces 5.1.0 | lost (2/0) | logged | logged | 0 | P3; A6 |
| BusinessEvents 6.3.2 | logged | logged | logged | 0 | |
| (7 lines with no published folder) | none | | | | point 4 |

---

## 3. Evidence

Repos are `C:/github/tibco-docs-aem/<repo>/en-us/<folder>/online-help/<version>/`. Staging URLs start `https://stg-docs.tibco.com/us/en/`.

**S3, not pushed.**
- `git rev-list HEAD...origin/wip`: BusinessConnect 3 commits ahead, Platform 7, BusinessWorks 7, Fulfillment 2, ActiveSpaces 1; 0 behind.
- `origin/wip` has `en-us/tibco-businessconnect-container-edition-ebxml-protocol/` (the long name, 54 characters, which AEM truncates, DOCOPS-372). The local tree has `en-us/tibco-businessconnect-ce-ebxml-protocol/` (from `4bad5b4`).
- `en-us/tibco-control-plane/online-help/1-3-0` has no commit on `origin/wip`. It was added in `02b5801` on 13 Nov.
- Staging `.../tibco-control-plane/online-help/1-3-0.html` answers 404, while `1-19-0/tibco-control-plane.html` answers 200.

**X1, entries that never match.**
- Control Plane 1.20.0 `release-notes/known-issues.md` "To delete the chart, run - `helm uninstall <oauth2proxy-release-name> ...`" has carried the DOCOPS-366 entry since 14 Nov. It is still unexplained on runs 2157 (13 Nov) and 2568 (15 Nov), because the entry's path is `"*/release-notes/known-issues.md"`.
- `driver.py` records a version-level finding with an empty path, so `"*/online-help/1-3-0"` is never compared with anything that could match it.

**S2, menu path.**
- Report rows (column `staging_url`):
  - Flogo 2.26.8 `connectors-user-guide/amazon-sqs.md` → `.../connectors-user-guide/creating-connections/amazon-sqs.html` (served);
  - BPM Enterprise 4.3.5 `developer-guide/replaceuser.md` → `.../developer-guide/soap-api-updatepageflow/replaceuser.html`;
  - BW 5.16.1 `palette-reference/configuration-6.md` → `.../palette-reference/time-zone-names/configuration-6.html`.
- The redirect sample asks for the folder path, which is 404.

**T6, same-title pairing (checker).**
- BW 5.16.1 `palette-reference/output-4.md` (2,593 words) was compared with `.../wsdl-source/built-in-resource-provider/output-7.html`. The result was "text 11.5%", and 4 of its anchors were looked for there.
- Order Management 5.0.1 `tibco-order-management-long-running-concepts/plan-item.md` was compared with `.../long-running-users-guide/general-approach/plan-item-3.html`.
- ActiveMatrix BPM 4.2.0: 3 different "Introduction" pages were all compared with `workspace-users-guide/introduction-2.html`.
- The 28 pages are where the served file name or folder differs from ours and the served page has a full article.

**P1, empty article.** Measured as the words between "Last published" and "In this article" on the cached page: site frame only, 231–263 words.
- Rendezvous 8.8.1 `concepts/the-rendezvous-daemon.md`: 2,685 words in Markdown. Served 15 Nov 23:20 with "Last published: Nov 14, 2026" and an empty article; its 62 anchors (daemon, subject names, wildcards…) are all "no heading on the served page".
- iProcess Engine 11.9.1 `administration-guide-oracle/list-values.md` (2,851 words), `.../casenum-gaps.md` (2,946) and 11 more database-administration pages.
- Flogo 2.26.6/2.26.8 `connectors-user-guide/websocket.md` (2,306 words) and `.../app-configuration-management/consul.md` (2,968). Flogo 3.0.1 shows the same pages empty (already logged).
- BW 6.12.0: `administration/opentelemetry/traces.md`, `basic-activities-palette/scope.md` and the BWCE copy, `shared-resources/http-client.md`, and both Maven shared-module pages. These are the same 6 as 6.13.0.
- ActiveMatrix BPM 4.2.0: `workspace-configuration/localization/default-language.md`, `introduction/launching-a-wcc-application.md`, `introduction/configuring-customizing-non.md`, `using-tibco-pagebus-managed/managed-hub-sample.md`.

**P2, heading-row menus.** `toc.yml` rows with `#`, out of all rows: Flogo 2.26.6 595 of 805, Rendezvous 8.8.1 1,495 of 1,714, BPM Enterprise 4.3.5 4,455 of 4,876, iProcess Engine 11.9.1 1,640 of 1,803. Flogo 3.0.1, converted in the current layout, has no staging-menu findings at all.

**R1.**
- BC 7.4.0 `301.yml` has 13 lines: the 10 PDF/readme rows, no page row. The 1,007 unmapped URLs are `pub/bc/7.4.0/doc/bcgs/html/…` (503) and `…/doc/bcis/html/…` (504), the same two-folder case as 7.5.0.
- BW 6.12.0: 44 under `relnotes/bw-ent-relnotes/`, plus 1 `relnotes/_templates/`.

**T1.** BPM Enterprise 4.3.5:
- `administration/default-audit-level.md` line 114: `4. Add an additional **<severity >**<!-- -->line for each severity level…`;
- `workspace-configuration-and-customization/application-monitor.md` line 49: `(**<Ctrl > +<Alt > +<m >**<!-- -->by default)`.

The browser reads `<severity >` as a tag, so the word is lost.

**T3.**
- BW 5.16.1 `Upgrading_TIBCO_ActiveMatrix_BusinessWorks.htm` lines 169–172 nest `<ul>` directly inside `<ul>`: the license-error list, 53 sentences.
- BW 6.12.0 `maven-plugin/generating-test-case.htm` line 179 has `<p>A confirmation message reports the outcome…</p><p><img src="images/generate-test-case-confirmation.png"…></p>` directly inside `<ol>`.
- Flogo 2.26.6 `creating-your-first-.htm` line 180 is the same with a screenshot.

**T5.**
- **MDM Studio 6.0.0** has `html/` and `relnotes/` builds, as 6.1.1. Our `repository-designer-users-guide/getting-started.md` reads "…capabilities of MDM Studio", and the `relnotes/` copy reads "…of ibi MDM Studio".
- **BW 6.12.0 Design Assistant.** The source has the sample prompts as Markdown text inside one `<pre>` (`sample-prompts-create-rest-service.htm` lines 125–194). The page holds them in a four-backtick fence, lines 242–312, which is correct. Verify ends the block at the inner ```` ``` ````.
- **Flogo 2.26.6.** `toc.yml` line 1554 links "Oracle Database Call Procedure" to `oracle-database-query.md#oracle-database-call-procedure`, and the section is there (line 174). Verify's page map expects `oracle-database-call-procedure.md`, which exists only in 2.26.8.

**A5.**
- `#rv_install_2928680826_33603921` appears only as `href` in Rendezvous `IBM_i_Installation_Package.htm`. The same holds for `#release_4113493088_1929193` (BW 5.16.1), `#1` (`Summary_of_Transactions.htm`), `#bookmark=id.grtvexai0z1c` (BW 6.12.0) and `#USE-BY-REFERENCE` (BPM 4.3.5).
- BPM Enterprise 4.3.5: `java-api-checkautoarchive.htm` and the 7 other archive topics are not in the package.

**P3.** ActiveSpaces 4.10.1 and 5.1.0: the version pages answer 200 (60 KB, 16 Nov 02:55) but give no menu. Both are on `wip` since `8edf6dd` (5 Nov).

**S4.**
- Redtail 7.5.0 `programmers-guide/hawk-console-api/structure.html` is cached 200 at 15 Nov 22:13. A failed request is not cached, so the "not served" was a one-off.
- `error-codes/error-codes.html` answered 500 again (22:17).

---

## 4. Proposed entries

See `reports/verify/triage-stage2a-2026-11-16.yaml`:
- **A** lists 29 line edits to the current file (20 `*/` → `*`, 1 version-folder path, 8 path deletions), and the 14 entries to leave or delete.
- **B** has 226 entries. It goes directly above `# Catch-alls: keep last`, after the Batch 2b block. The per-page lists come last: 41 empty-article pages to DOCOPS-344 (anchors and pictures), and 28 same-title pages to DOCOPS-366.
- **C** has 17 optional "nested under the guide page" entries.

**No entry for:**
- the 19 S3 versions (re-verify after the R2 push);
- the Redtail one-off (S4);
- the 5 menu-order warnings (as on 14–15 Nov).

---

## 5. Jira changes (reuse only; no new issue)

| Issue | Change |
|---|---|
| DOCOPS-338 (verify waves) | Note: Stage 2a done. 49 lost → 20 with A+B (19 are unpushed folders, re-verify after R2), 3,865 → 27 unexplained with C. Note the 29 dead triage entries (fixed in A). Proposal: `triage.load` should warn on an entry whose path starts with `*/` plus a top-level folder, or that carries a path for a version-level code. |
| DOCOPS-344 | Note: 41 more pages served empty. iProcess Engine 11.9.1 (13), Flogo 2.26.6 and 2.26.8 (7 each), BW 6.12.0 (6, the same pages as 6.13.0), Rendezvous 8.8.1 (4, including "The Rendezvous Daemon"), AMX BPM 4.2.0 (4). Redtail 7.5.0 Error Codes 500 a third time. |
| DOCOPS-351 | Note: (1) the menu-path URL rule is general: Flogo, BPM Enterprise, BW, Control Plane, iProcess, MDM Studio, Order Management (46 failed redirect targets). (2) 13 older conversions whose `toc.yml` is mostly heading rows (892 staging-menu findings). A re-convert in the current layout clears (2): Flogo 3.0.1 has none. |
| DOCOPS-366 | Note: the same-title pairing (178 anchors, 28 pages; follows from S2); the four-backtick fence; Flogo 2.26.6 Call Procedure page map; MDM Studio 6.0.0 two builds (159). |
| DOCOPS-322 | Note: BC 7.4.0 is the same two-folder case as 7.5.0 (1,007). BW 6.12.0 and 5.16.1 have no rows for `relnotes/` (54). |
| DOCOPS-360 | Note: `<placeholder>` in bold also on BPM Enterprise 4.3.5 (5 pages, 8 sentences) and BW 6.12.0 (8). |
| DOCOPS-370 | Note: add BW 5.16.1, BW 6.12.0 and Flogo 2.26.6 to the re-convert list. Add BPM Enterprise 5.6.1 (overflow icon). |
| DOCOPS-373 | Note: AMX BPM 4.2.0 has the same 2 pages as 4.3.0. |
| DOCOPS-345 / 362 / 363 / 349 / 346 / 353 | Notes with the examples in the summary table (iProcess `®` ids; BPM 4.3.5 DITA ids; ActiveSpaces 4.10.1 and 5.1.0 `_globalpages` and empty menu). |

---

## 6. UAT-sheet rows (Digital Platform)

DOCOPS-344 (empty article) and DOCOPS-351 (menu-path URLs, 15 Nov row) are already in the sheet: add the new examples to their Comments, and **raise the menu-path row to Critical**. It now spans 8 products and decides whether redirects work at go-live.

```csv
Type,Issue description,Issue screenshot,Category,Priority,Found In,Reporter,Status,Assignee,Stage Issue link,Prod Issue link,Comments,DEV status / comment
Desktop,"Pages are served at their menu path, not their folder path, on many products (not only Transaction Insight). Example: Flogo 2.26.8 Amazon SQS is served at .../2-26-8/connectors-user-guide/creating-connections/amazon-sqs.html; its folder path .../2-26-8/connectors-user-guide/amazon-sqs.html is 404. Our 301.yml rows and cross-links name the Markdown file path. 46 sampled redirect targets fail on Flogo 2.26.6/2.26.8, BPM Enterprise 4.3.5, BusinessWorks 5.16.1, Control Plane 1.19.0, iProcess Engine 11.9.1, MDM Studio 6.0.0, Order Management 5.0.1. Question: does AEM resolve a Markdown path in 301.yml to the served URL? GitHub: https://github.com/tibco/en-us-tib-flogo-userdocs/blob/wip/en-us/tibco-flogo/online-help/2-26-8/toc.yml",,Content,Critical,"Flogo, BPM Enterprise, BusinessWorks, Control Plane, iProcess, MDM Studio, Order Management (+ Transaction Insight 6.0.0)",Mayur,New,,https://stg-docs.tibco.com/us/en/tibco-flogo/online-help/2-26-8/connectors-user-guide/amazon-sqs.html,,"DOCOPS-351; redirects at go-live",
Desktop,"Pages served with an empty article: the page loads with menu and frame, but the article body is blank, although the Markdown holds 500-3,000 words. 41 more pages in Stage 2a, e.g. Rendezvous 8.8.1 'The Rendezvous Daemon' (2,685 words), iProcess Engine 11.9.1 Database Administration (13 pages), Flogo 2.26.6/2.26.8 WebSocket and Consul, BusinessWorks 6.12.0 Scope and OpenTelemetry Traces. GitHub: https://github.com/tibco/en-us-tib-messaging-userdocs/blob/wip/en-us/tibco-rendezvous/online-help/8-8-1/concepts/the-rendezvous-daemon.md",,Content,High,"Rendezvous 8.8.1; iProcess Engine 11.9.1; Flogo 2.26.6, 2.26.8; BusinessWorks 6.12.0; ActiveMatrix BPM 4.2.0",Mayur,New,,https://stg-docs.tibco.com/us/en/tibco-rendezvous/online-help/8-8-1/concepts/the-rendezvous-daemon.html,,"DOCOPS-344; verify 15-16 Nov",
```

---

## 7. Open questions

1. **Menu-path URLs (S2).** Same question as 15 Nov, now with 8 products. If AEM does not resolve Markdown paths in `301.yml`, should we write served (menu) URLs into the redirect rows, or make folders follow the menu? This needs an answer before the R2 pushes.
2. **"Nested under the guide page" (block C).** Still open since 14 Nov. Accepting it explains 631 findings in 17 versions; this batch's verdicts are otherwise final.
3. **Push order.** 19 versions wait only on the R2 push of the BusinessConnect, Platform, BusinessWorks, Fulfillment and ActiveSpaces stacks (K3 additions, Phase 80 renames, R002, DOCOPS-370). Re-verify them right after the push. Should the Phase 80 rename go first, since AEM cannot serve the long names at all (DOCOPS-372)?
4. **The 7 lines with nothing to check.** Remove them from the overnight lists. Should `versions.csv` stop calling Messaging 1.21–1.30 and Mosquitto Core 2.0.7 "synced" when nothing is in the repo?
