# Verify triage: Stage 3 (remaining TIBCO, BW plug-ins, Streaming and MFT), 2026-11-16

This is a read-only triage. No repo file or config was edited, nothing was run, logged in Jira or pushed. `cache/state.db` was opened read-only. The only files written are this report and its YAML.

**What was checked:**
- **The batch:** the 244 lines of `cache/overnight/stage3-a.txt` (83: remaining TIBCO families, and the 4 Stage 2b steps that crashed), `stage3-b.txt` (119 BW plug-ins) and `stage3-c.txt` (42 Streaming and MFT). They ran Mon 16 Nov 13:00 to 15:01 IST, all with `--refresh` (runs 2672–2898). Outcomes are in the `.summary` files, logs in the `.logs/` folders.
- **One step failed and was re-run:** `stage3-c` step 019 (Enterprise Streaming FIX Engine 11.1.3) stopped while writing `reports/verify/ISSUES.csv` (`OSError: [Errno 22] Invalid argument`, the file was held open). Its result was stored, and the re-run at 15:00 passed. Nothing is lost.
- **Nothing to check (18 lines):**
  - 17 steps logged "No published version folders match this selection": Gemini 5.0.2, Mosquitto bridge and core 2.0.7, Hybrid Integration Connectivity 3.11.0, Messaging 1.21.0–1.30.0 (7), Messaging EE 3.3.0, MDM 10.0.0, MDM Studio 5.3.0, BC Trading Community Management 6.1.1, Mainframe RED 2.5.1 and BW plug-in for Amazon S3 6.6.0. Most were already listed by Stage 2a/2b; remove them from the overnight lists.
  - BW plug-in for Workday 1.0.0 was skipped: "extracted package not on disk".
- **Triaged here: the other 226 versions.** For each, the latest result in `state.db` is this batch's run. The triage file was applied the way `verify --retriage` applies it (`triage.decide`, `issues.tally`), in memory, four ways:
  1. the current `config/verify-triage.yaml`;
  2. plus the Stage 2a and 2b proposals of today (2a A + B + C; 2b 3b + 3d + 3c; not 3e). These are not in the config yet;
  3. plus this report's recommended blocks;
  4. plus its optional block.
- **Evidence:**
  - the Markdown in `C:/github/tibco-docs-aem`, both local `content-fix` and `origin/wip` (last fetched Sat 14 Nov 21:34);
  - the extracted packages under `families/`;
  - the staging pages these runs cached in `cache/verify/`.

  No new staging request was made.
- **Short names:**
  - **lost:** a version with unexplained errors;
  - **issues:** only unexplained warnings;
  - **logged:** every finding explained, at least one a known Jira problem;
  - **clean:** no finding.

**Where the batch stands (226 versions):**

| Entries applied | lost | issues | logged | clean | Unexplained findings |
|---|---|---|---|---|---|
| Today's config | 64 | 16 | 106 | 40 | 1,019 |
| + Stage 2a and 2b proposals | 57 | 17 | 112 | 40 | 998 |
| + Stage 3, recommended (S3-top, S3, S3-tmp) | **2** | 11 | 173 | 40 | 20 |
| + Stage 3, optional (S3-opt) | **2** | **3** | 181 | 40 | **6** |

- **The 2 left `lost`:** Flogo 3.0.2 and 2.26.9. They were added locally on Sun 15 Nov 22:36 (commit `69d779d`, "delta 1") and are not pushed. Re-verify after the push; no entry is proposed.
- **The 3 left `issues`:** menu-order warnings only (`TOC_ORDER`), left untriaged as on 14–16 Nov. They are Rendezvous 9.0.0 and Foresight Instream 9.3.0 and 9.4.0.
- **No version reads `explained`:** each has at least one finding logged in Jira.
- **Entries:** the YAML has 116 entries: S3-top 2, S3 106, S3-tmp 1, S3-opt 7. Every one decides at least one stored finding in the simulation. All but one decide only Stage 3 findings. The exception is the Transaction Insight 6.0.0 notes entry, which was asked for (69 notes).

**Things to know first:**

1. **Streaming's fixes since 30 Oct never reached `wip` (new, ours; High).**
   - **What is stuck:** in `en-us-tib-streaming-userdocs`, three of our commits are on `origin/content-fix` but not on `origin/wip`:
     - `1cfa47a`: R001 note labels, 30 Oct;
     - `ecff12b`: DocBook menus keep nested sections, 2 Nov;
     - `e5a1c2d`: 301.yml in AEM's new shape, 5 Nov.
   - **Why:** `wip` moved on separately, with two Digital Platform test commits (`0de0e42` on 6 Nov, `4dd77f8` on 14 Nov). So the two branches have diverged and no merge was made. Every other TIBCO repo has nothing on `content-fix` that `wip` lacks. BW plug-ins, for example, went in through "Merge pull request #1 from tibco/content-fix" on 6 Nov.
   - **Effect on staging:** Streaming 11.1.0 still has 1,005 `[!NOTE]` alerts on `wip`, against 0 on `content-fix`. Staging shows 1,004 notes in alert form on 586 pages. The same holds for Streaming 11.1.1 and Spotfire Data Streams 11.1.0.
   - **Why verify does not flag it:** the R001 entry excuses these notes, because R001 counts as "fixed" for these versions in `state.db` (local).
   - **Fix:** merge `content-fix` into Streaming's `wip`, with the two Digital Platform commits. Fetch and compare first, then raise the PR. This is a push, so it needs your go-ahead.
2. **Not on staging (not served at all):**

   | Family | Versions | Detail | Already logged? |
   |---|---|---|---|
   | **BW plug-ins** | 96 versions of 33 plug-ins, on `wip` since 6 Oct–6 Nov | Most folder names are over 50 characters (DOCOPS-372; the renames wait for AEM's answer). **5 are 49–50 characters and still not served:** SFTP 1.1.1 and 6.1.4; SWIFT 5.24.0, 5.25.0 and 6.10.0. 4 more are local only (CICS 1.5.1 and 2.4.1, Files 8.2.0, SAP 8.6.0). | All logged by the existing BW plug-in entry (DOCOPS-346) |
   | **MFT** | 14 | **6 have short names and are on `wip` since 15 Oct:** Command Center and Internet Server 8.6.0, 8.7.0 and 8.7.1. The other **8 are Platform Server** (UNIX 8.1.1–8.2.0, Windows 8.1.0 and 8.2.0, z/Linux 8.1.0–8.1.2). Their `wip` names are 52–56 characters, and the rename under 50 (`fbfb772`, 14 Nov) is local, held for AEM. | None; block S3 and S3-tmp |
   | **Streaming** | Streaming 11.1.2, 11.2.0 and 11.2.1 (11.1.3 earlier), and Spotfire Data Streams 11.1.1 | On `wip` since 29 Sep / 30 Oct. Streaming 11.1.0 and 11.1.1 and Data Streams 11.1.0 are served, but with the old content (point 1). | Streaming yes (DOCOPS-346); Data Streams in S3 |
   | **Foresight Instream** | 9.2.0, 9.3.0 and 9.4.0 | Already in the UAT sheet: add 9.2.0 and 9.3.0 to that row. | 9.2.0 and 9.3.0 in S3 |

   Paste-ready rows for the first three are in section 6. They extend the 14 Nov rows, which named only 2–3 versions each.
3. **Transaction Insight 6.0.0 notes: verify's rule is out of date (checker, DOCOPS-366).**
   - **The Markdown is right:** `wip` has no GitHub alert anywhere in TI 6.0.0 or 5.5.0. Every note is `> **Note:**`, since R001 on 30 Oct (`b7e48e7`).
   - **What staging serves:** on 25 of the 47 pages with notes, staging writes the note as AEM's alert markup, `<a class="xref" data-attr-keyref="!NOTE"></a>` followed by the text. On the other 22 it writes `<b>Note:</b>`, for the same Markdown, and all pages show "Last published Nov 13".
   - **Why verify reports them:** it counts every `[data-attr-keyref^="!"]` in the article as "a note with no label". That rule is in `src/docushift/verify/published.py`, line 273, and it dates from Phase 56, when AEM showed no label for alerts.
   - **Why it is a false positive:** you see the label on staging, so it is added when the page is displayed (the site's stylesheet or script). The cached HTML cannot show that.
   - **Not explained:** why AEM chose the alert form for some pages and not others. It may be a newer renderer, or pages kept from the 14 Oct rendition.
   - **The entry:** S3-top marks the 69 notes of 6.0.0 and the 13 of 5.5.0 `accepted` (DOCOPS-366). It must sit above the R001 entry, which matches first otherwise.
   - **Checker fix, to describe only:** count a keyref note as "no label" only when the Markdown at that place is still `[!…]`, or look for a label element instead.
4. **Stale results (not rebuilt):**
   - **EMS** 10.4.0–10.5.0 (5 versions) were checked against a build older than the 15 Nov push (`4e31308`). They read `logged`; re-check after the rebuild.
   - **Adapters:** only the four folders renamed in `bf9bd99` (14 Nov) are affected: Database, Files and SAP for Business Studio, and JDE. Their "not on staging" is stale. The other Adapters products (Framework, IBM i, SDK, Migration, Joomla) have not changed since 30 Oct, so their results stand.
5. **New, small, ours:** one new reader-facing loss and four converter details. All fit existing issues.
   - **TI 5.5.0 "Deploying Docker Images in a Kubernetes Cluster" (DOCOPS-370).** Four whole sections are written inside step 2 of a numbered list, indented, with raw-HTML tables. Staging serves 510 of the page's 2,562 words: the four Helm chart property tables, 133 sentences and 4 pictures are missing.
   - **Kafka 6.8.0 and 6.8.1 (DOCOPS-370):** a Debug icon inside a menu cascade is dropped.
   - **Pulsar 5.0.0 (DOCOPS-370):** a screenshot inside `<pre>` is dropped.
   - **Data Conversion 4.8.0 and FTL 6.7.1/6.7.2 (DOCOPS-349):** "What's New" in Flare `_templates/` is skipped.
   - **AMQP 5.0.0 (DOCOPS-363):** a source heading id is not kept.
   - **Adapter Framework (DOCOPS-345):** a heading with `<sup>®</sup>` gets another id.
6. **More empty articles (DOCOPS-344): 24 pages in 5 versions.**
   - **Which:** Foresight ARS 5.5.0 (3), Transaction Insight 5.4.0 (4) and 5.5.0 (9), Patterns 6.1.2 (1), Reward 22.2.0 (7).
   - **What the reader sees:** the cached article is empty, against 1,190–3,020 words in the Markdown. 640 anchor and picture findings sit on these pages.
   - **Why this shows up now:** Foresight and General are now rebuilt, so this is current, not stale.
7. **Already known, noted only.** Activation Service 1.1.0 has 25 unmapped redirects, because its `301.yml` has no page rows (DOCOPS-354). The fix is in progress, and the finding is already logged. Doubled backslashes (DOCOPS-360) do not show as findings in this batch.

---

## 1. Summary table

"Findings" counts errors and warnings decided by the Stage 3 blocks.

| # | Kind (plain words) | Codes | Versions / findings | Verdict | Jira | Owner |
|---|---|---|---|---|---|---|
| **N1** | **Streaming `content-fix` never merged into `wip`** (R001, menus, 301.yml; `wip` has Digital Platform test commits instead) | `PUBLISHED_CALLOUT_UNRENDERED` (excused by the R001 entry) | 3 / 1,764 notes | **ours, new: merge** | DOCOPS-250, DOCOPS-338 (notes) | TechDocs |
| **N2** | **Sections inside a list step not served** (TI 5.5.0 Docker page) | `PUBLISHED_ANCHOR_MISSING`, `IMAGE_BROKEN`, `TEXT_DIFF` | 1 / 9 | ours, new variant | DOCOPS-370 | TechDocs |
| N3 | Checker: AEM's alert markup counted as "no label" (TI 6.0.0 69, 5.5.0 13) | `PUBLISHED_CALLOUT_UNRENDERED` | 2 / 82 | accepted, checker | DOCOPS-366 | TechDocs |
| S1 | Not on staging, on `wip` (Instream 9.2/9.3, Data Streams 11.1.1, MFT CC/IS 6) | `PUBLISHED_PAGE_MISSING` | 9 / 9 | existing issue | DOCOPS-346 | Digital Platform |
| S2 | Not pushed: MFT Platform Server renamed locally (held for AEM) | `PUBLISHED_PAGE_MISSING` | 8 / 8 | temporary `logged` (S3-tmp) | DOCOPS-372 | TechDocs / AEM answer |
| S3 | Not pushed: Flogo 3.0.2 and 2.26.9 (delta 1) | `PUBLISHED_PAGE_MISSING` | 2 / 2 | no entry; re-verify after push | none | TechDocs |
| P1 | **Empty article** (24 pages) | `PUBLISHED_ANCHOR_MISSING`, `IMAGE_BROKEN` | 5 / 640 | existing issue, platform | DOCOPS-344 | Digital Platform |
| P2 | Pages after heading rows: dropped or moved, 404 at folder path (Foresight ARS/TI 5.x, OpMon, Studio, Patterns; Adapter Framework 1.3.0–1.6.0; BW MDM 6.3.1) | `PUBLISHED_TOC_ENTRY_MISSING`, `PUBLISHED_TOC_MOVED`, `REDIRECT_UNSERVED`, `PUBLISHED_TOC_ORDER` | 18 / 150 | existing issue | DOCOPS-351 | Digital Platform |
| M1 | Support and legal copies kept once, at the end (IBM i adapter, IBM MQ, LDAP, Reward) | `TOC_ENTRY_MISSING` | 6 / 38 | accepted (design) | none | none |
| M2 | Topic under two parents / paired crosswise | `TOC_MOVED` | 17 / 39 | accepted | none | none |
| M4 | Page moved between the top level and a guide page (optional, the 14 Nov question) | `TOC_MOVED` | 8 / 14 | accepted? (S3-opt) | none | none |
| T1 | Checker: old menu's subproject path (Instream 9.3.0, TI 5.5.0) | `TOPIC_MISSING` | 2 / 399 | checker | DOCOPS-366 | TechDocs |
| T2 | Checker: `\<samp>` in raw HTML (Data Conversion), long URL link text (SAP 8.6/8.7), hotfix page under another name (BW MDM 7.0.x) | `TEXT_DROPPED`, `TOPIC_MISSING` | 6 / 6 | checker | DOCOPS-366 | TechDocs |
| T3 | Sentence split over lines in a table cell (Streaming / Data Streams 11.1.1); automatic "Table 1" number not kept (BW Database 7.x) | `TEXT_DROPPED` | 5 / 5 | accepted | none | none |
| T4 | Pictures dropped by unusual markup (icon in menu cascade, screenshot in `<pre>`) | `IMAGE_MISSING` | 3 / 3 | ours | DOCOPS-370 | TechDocs |
| A1 | Heading ids: `<sup>®</sup>` (Adapter Framework); source's own heading id (AMQP 5.0.0); code as dashes (MFT PS UNIX 8.1.2) | `PUBLISHED_ANCHOR_MISSING`, `REDIRECT_TARGET_MISSING` | 8 / 17 | existing issues | DOCOPS-345, 363, 362 | as before |
| A2 | Source: links to bookmarks never defined on that page (`_Ref292373532`, `_bookmark17`) | `PUBLISHED_ANCHOR_MISSING` | 2 / 3 | source | none | none |
| A3 | Source: old menu names files the package does not ship (Reward GUID names with `&`; MFT 2 topics) | `TOPIC_MISSING` | 7 / 17 | source | none | none |
| A4 | Flare `_templates/Whats-New.htm` skipped | `TOPIC_MISSING` | 3 / 3 | existing issue | DOCOPS-349 | TechDocs |
| L1 | Live legal text newer than the package | `LIVE_DRIFT` | 6 / 8 | accepted | none | none |
| M6 | Menu order under one parent | `TOC_ORDER` | 3 / 3 | not triaged (warnings) | none | TechDocs, later |

---

## 2. Evidence

Repos are under `C:/github/tibco-docs-aem/<repo>/en-us/<folder>/online-help/<version>/`. Staging URLs start `https://stg-docs.tibco.com/us/en/`.

**N1, Streaming:**
- `git log origin/wip..origin/content-fix` lists `e5a1c2d`, `ecff12b` and `1cfa47a` (Mayur, 30 Oct–5 Nov).
- `git log origin/content-fix..origin/wip` lists `4dd77f8` "Dummy commit to test .md.html link rewrite" (14 Nov) and `0de0e42` "Test staging streaming link rewrite" (6 Nov), both by Thiyagu Maruthachalam.
- The `[!NOTE|TIP|…]` count in `tibco-streaming/online-help/11-1-0/*.md` is 1,005 on `origin/wip` and 0 on `origin/content-fix`.
- The same count for every other TIBCO repo's `origin/wip..origin/content-fix` is 0 commits.

**N2, TI 5.5.0 Docker page:**
- `tibco-foresight-transaction-insight/container-deployment/deploying-docker-images-in-a-kubernetes-cluster.md` has these headings, each indented under step 2 with a raw-HTML `<table>`:
  - line 39: `   ## TIBCO Foresight Transaction Insight Portal Helm Chart Properties`;
  - lines 254, 392 and 540: the next three sections.
- The cached staging article (`.../5-5-0/tibco-foresight-transaction-insight/container-deployment/deploying-docker-images-in-a-kubernetes-cluster.html`) has 510 words and the headings `before-you-begin`, `procedure`, `sample-kubectl-commands`, `sample-helm-commands`… None of the four property sections is there.
- Run 2803 holds the evidence: "133 sentence(s) not served", 4 pictures "not on the served page", and 4 anchors.
- TI 6.0.0 has no such page.

**N3, TI notes:**
- `git grep -E "\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]" origin/wip -- …/6-0-0/*.md` finds 0 (5.5.0 also 0).
- `fhirarchiver.md` lines 41–42 read `> **Note:**` / `> Before using FHIRArchiver…`. Staging (cached 16 Nov 14:37) serves `<a class="xref" data-has-usertext="true" data-attr-keyref="!NOTE"></a> Before using FHIRArchiver…`.
- `275-and-277-transactions/introduction.md`, with the identical form, is served as `<b class="ph b display-inline">Note:</b>`.
- Of the 134 TI 6.0.0 pages cached, all read "Last published Nov 13". 25 use the keyref form (69 notes), 22 the bold form, and no page mixes the two.
- FTL 7.3.0 shows the bold form for the same Markdown.

**S1/S2, not served:**
- Each version answers "no menu served" at its version page and at its first menu page, for example `tibco-managed-file-transfer-command-center/online-help/8-7-0.html` and `spotfire-data-streams/online-help/11-1-1.html`.
- `git cat-file -e origin/wip:<folder>/toc.yml` succeeds for the S1 versions.
- For MFT Platform Server, `origin/wip` has `tibco-managed-file-transfer-platform-server-for-unix/` (52 characters), and local `content-fix` has `tibco-mft-platform-server-unix/` (`fbfb772`, not pushed). Verify asked staging for the short name.

**P1, empty articles:** the words in `div.topic-renderer__content` of the cached page were counted:
- Foresight ARS 5.5.0 `administration-guide.md` serves 0 (2,898 in the Markdown);
- TI 5.4.0 `common-administration.md` serves 0 (2,995);
- Patterns 6.1.2 `utilities/patterns-data-synchronizer-overview.md` serves 0 (1,825);
- Reward 22.2.0 `tibco-reward/integration-guide/batch-file-integration/reward-export-file.md` serves 0 (2,315).

Pages beside them are served whole: TI 5.5.0 `ti-ems-queue-reader.md` serves 771 of 794 words.

**P2, heading-row menus:** most `toc.yml` rows in these versions are heading rows:

| Version | Heading rows | All rows |
|---|---|---|
| ARS 5.4.0 | 87 | 100 |
| Studio 9.2.0 | 279 | 345 |
| TI 5.5.0 | 828 | 934 |
| Adapter Framework 1.4.0 | 89 | 99 |
| BW MDM 6.3.1 | 56 | 67 |

Example: ARS 5.4.0 "Search Control" (line 213) follows `user-guide/action-page-direct.md#tree-view-filter`. Staging leaves it out of the menu, and `.../5-4-0/user-guide/search-control.html` is 404.

**T2, checkers:**
- **Data Conversion 4.6.0 `general-tab.md`, line 134:** `<p>\<samp>u0009</samp> – Horizontal tabulation …`. The source `GUID-56F14E05….html` has the same `\<samp class="codeph">u0009</samp>`, so the page shows `\u0009` correctly.
- **BW MDM 7.0.1:** `toc.yml` line 40–41 lists "Applying the HF-001 Hotfix…" at `installation/support-for-tibco-businessworks-container-edition/applying-hf-001-hotfix-tibco-businessworks.md`.
- **SAP 8.6.0 `sap-account-requirements.md`, line 150:** has the sentence, with a help.sap.com URL as link text.

**T4, pictures:**
- **Kafka 6.8.0:** the source `testing-a-process.htm` has `Debug <img src="images/debugicon_38x21.gif" class="icon"…> &gt; Debug Configurations` inside `span.menucascade`.
- **Pulsar 5.0.0:** the source `Creating_a_TIBCO_ActiveMatrix_BusinessWorks_Process.htm` has `<pre class="Indent"><img src="images/ProcessDefintion.jpg" /></pre>`.

Neither picture is in the Markdown.

**A1–A4:**
- **Adapter Framework 1.4.0:** `tibco-activematrix-adapter-framework.md` line 15 is `## TIBCO ActiveMatrix<sup>®</sup> Adapter Framework Administration`, and `toc.yml` line 8 links `#tibco-activematrix-adapter-framework-administration`.
- **AMQP 5.0.0:** the source `log-status-settings.htm` line 181 is `<h2 id="amqp-debug-switch">`. Our heading is `## Turning AMQP plug-in debug on`.
- **TI:** `#_Ref292373532` is defined on no page. `#_bookmark17` is defined on `filters.md` and `fhir-etl-page.md`, not on `granting-user-permissions.md`.
- **Reward 22.2.0:** the old menu names `blue-user-guide/CSR Roles & Privileges=GUID-…=2=en_US=.htm`. The package has no file of that name (`csr2.htm` instead).
- **MFT:** `mft-platform-server-high-availability.htm` and `archive-server-status-new.htm` are not in the 8.7.1 package.

---

## 3. Per-version table

"Now" is today. "2a+2b" adds both of today's earlier proposals, "S3" adds this report's recommended blocks, and "+opt" adds S3-opt. Versions whose status does not change and that are `logged` or `clean` throughout are grouped at the end.

| Step | Version | Now | 2a+2b | S3 | +opt | Main kinds / what is left |
|---|---|---|---|---|---|---|
| a004 | Rendezvous 9.0.0 | issues | issues | issues | issues | left: 1 `TOC_ORDER` |
| a005 | Foresight EDISIM 6.21.0 | lost | logged | logged | logged | 2a A3 fix; M2 |
| a006 | Foresight Instream 9.4.0 | lost | issues | issues | issues | not served (2a A3); left: 1 `TOC_ORDER` |
| a009 | Activation Service 1.1.0 | lost | logged | logged | logged | DOCOPS-354 (known); 2a/2b |
| a010, a067 | Flogo 3.0.2, 2.26.9 | lost | lost | lost | lost | **not pushed (S3)**; re-verify after push |
| a013, a015, a016 | Adapter Files 1.3.0, JDE 6.1.0, SAP 1.3.0 | lost | logged | logged | logged | not served; stale (renamed `bf9bd99`) |
| a014, a073, a074 | Adapter IBM i 6.4.0, 6.2.2, 6.3.0 | lost | logged (6.4.0) / lost | logged | logged | M1 |
| a023, a024 | Foresight ARS 5.4.0, 5.5.0 | lost | lost | logged | logged | P1 (3 pages, 5.5.0), P2 |
| a032, a033 | Foresight Instream 9.2.0, 9.3.0 | lost | lost | logged / issues | logged / issues | S1, M2, T1 (379); 9.3.0 left 1 `TOC_ORDER` |
| a034 | Foresight Operational Monitor 5.4.0 | lost | lost | logged | logged | P2 |
| a041 | Foresight Studio 9.2.0 | lost | lost | logged | logged | P2, M2 |
| a042 | Foresight Transaction Insight 5.4.0 | lost | lost | logged | logged | P1 (4 pages), P2, A2 |
| a043 | Foresight Transaction Insight 5.5.0 | lost | lost | logged | logged | P1 (9 pages), **N2**, P2, T1, N3 (13), A2 |
| a056 | Enterprise Administrator 2.4.2 | issues | issues | logged | logged | M2 |
| a057 | Patterns 6.1.2 | lost | lost | logged | logged | P1 (1 page), P2, title repeated (DOCOPS-336) |
| a058 | Reward 22.2.0 | lost | lost | issues | logged | P1 (7 pages), A3, M1, M2, M4 |
| a075–a081 | Adapter Framework 1.3.0–1.6.0 (7) | lost | lost | logged | logged | P2, A1 (`®`) |
| b015 | BWP AMQP 5.0.0 | lost | lost | logged | logged | A1 (own heading id) |
| b022, b023 | BWP Kafka 6.8.0, 6.8.1 | lost | lost | logged | logged | not served; T4 |
| b024 | BWP Pulsar 5.0.0 | lost | lost | logged | logged | not served; T4 |
| b036–b039 | BWP Data Conversion 4.6.0–4.8.1 | lost / issues | lost / issues | logged (4.7.0 issues) | logged | not served; T2, A4, M2, M4 |
| b040–b043 | BWP Database 7.2.1–8.5.0 | lost / issues | same | logged | logged | not served; T3, M2 |
| b046, b050 | BWP HL7 7.3.0, 8.4.0 | issues | issues | logged / issues | logged | not served; L1, M4 |
| b052–b056 | BWP IBM MQ 7.7.3–8.8.1 | lost / issues | same | logged (8.8.x issues) | logged | not served; M1, M2, M4 |
| b057 | BWP LDAP 6.1.2 | lost | lost | logged | logged | M1 (20) |
| b058–b060 | BWP MDM 6.3.1, 7.0.0, 7.0.1 | lost | lost | logged | logged | P2 (6.3.1), T2 (7.0.x) |
| b079–b081 | BWP SAP 7.3.2, 8.6.0, 8.7.0 | issues / lost | same | logged (7.3.2 issues) | logged | not served (8.6.0 local only); T2, M4 |
| b093 | BWP AuditSafe 6.3.1 | issues | issues | issues | logged | not served; L1, M4 |
| b098–b103 | BWP FTL 6.4.4, 6.6.0, 6.7.1, 6.7.2 | issues / lost | same | logged (6.6.0 issues) | logged | not served; L1, A4, M4 |
| b106, b107, b111 | BWP Patterns 1.2.0, 1.5.0, 5.4.0 | issues | issues | logged | logged | not served; L1 |
| c001 | Spotfire Data Streams 11.1.1 | lost | lost | logged | logged | S1, T3 |
| c031 | Streaming 11.1.1 | lost | lost | logged | logged | T3; **N1** (old content served) |
| c008, c009, c034–c037 | MFT Command Center / Internet Server 8.6.0, 8.7.0, 8.7.1 (6) | lost | lost | logged | logged | S1, A3, M2 |
| c010–c012, c038–c042 | MFT Platform Server UNIX / Windows / z-Linux (8) | lost | lost | logged | logged | S2 (S3-tmp); A1 (UNIX 8.1.2) |
| (71 more BW plug-in versions) | not served, nothing else | logged | logged | logged | logged | existing DOCOPS-346 entry (3 of them local only: CICS 1.5.1 and 2.4.1, Files 8.2.0) |
| (12 more BW plug-in versions) | served: AMQP 6.3.1-6.5.3, CICS 1.2.2/1.5.0, EJB 5.4.0, OData 6.6.0/6.7.0, PDF 6.2.2, Redis 6.0.0, AI 6.0.0 | logged / clean | same | same | same | |
| a001, a003, a012, a017–a022, a025–a031, a035–a040, a044–a046, a055, a059, a070–a072, a082, a083 | Hawk BW6 6.8.0, Messaging EE 3.4.0, Joomla, Adapter Framework 1.6.1, SDK, Migration, Files IBM i, Enterprise Foresight, FHIR, EDISIM 6.19/6.20, HIPAA Validator, Instream 9.0/9.1, OpMon 5.5.0, REST API, Studio 9.0–9.1, Translator, Activation Service 1.0.0, RTView, IBM i 6.2.0/6.2.1 | logged / clean | same | same | same | |
| a060–a064 | EMS 10.4.0–10.5.0 | logged | logged | logged | logged | **stale** (not rebuilt since 15 Nov push) |
| c002–c007, c013–c030, c032, c033 | Streaming family (other) | clean / logged | same | same | same | PDF-only stubs clean; Streaming 11.1.0 and Data Streams 11.1.0 served with old notes (N1); 11.1.2, 11.2.x not served (logged) |

---

## 4. Proposed entries

All proposed entries are in `reports/verify/triage-stage3-2026-11-16.yaml`. It was checked to load with today's config and the 2a and 2b proposals, in paste order.

- **S3-top (2 entries):** the TI notes (N3). Paste directly above the R001 catch-all, the entry with `decision: ours` and `repair: R001`, after the DOCOPS-313 lines. Placed anywhere lower, it never matches.
- **S3 (106):** paste directly above `  # Catch-alls: keep last`, after the 2a and 2b blocks. It reuses `*menurows` from 2a B and `*notpushed` from 2b 3d.
- **S3-tmp (1, temporary):** MFT Platform Server, not pushed. Delete it after the push and a re-verify.
- **S3-opt (7, optional):** pages moved between the top level and a guide page; the open question of 14 Nov.
- **No entry for:**
  - Flogo 3.0.2 and 2.26.9: not pushed, re-verify;
  - the 3 `TOC_ORDER` warnings;
  - Streaming's old notes: they are excused by the R001 entry already, and the fix is the merge (N1), not an entry.

---

## 5. Jira changes (to apply when you choose; none was made)

| Issue | Change | Points |
|---|---|---|
| DOCOPS-338 | Note: Stage 3 is triaged. 64 lost go to 2 (Flogo delta, not pushed) with the 2a, 2b and Stage 3 entries, and unexplained findings go from 1,019 to 6. **Streaming's `content-fix` (R001, menus, 301.yml; 30 Oct–5 Nov) was never merged into `wip`**, and `wip` has 2 Digital Platform test commits instead. 18 lines had nothing to check; remove them from the lists. | none |
| DOCOPS-250 | Note: R001 for Streaming (`1cfa47a`) is not on `wip`, so staging shows 1,004 unlabelled notes on Streaming 11.1.0 (and 11.1.1, Data Streams 11.1.0). The repair status "fixed" is local only. | none |
| DOCOPS-346 | Note: also not served: MFT Command Center and Internet Server 8.6.0/8.7.0/8.7.1 (short names, on `wip` since 15 Oct), Spotfire Data Streams 11.1.1, Instream 9.2.0 and 9.3.0, and BW plug-ins SFTP (1.1.1, 6.1.4) and SWIFT (5.24.0, 5.25.0, 6.10.0), which have names of 49–50 characters. | none |
| DOCOPS-372 | Note: Stage 3 found 96 BW plug-in versions of 33 plug-ins not served, and MFT Platform Server (8 versions) renamed locally (`fbfb772`), held for AEM's answer. | none |
| DOCOPS-344 | Note: 24 more empty-article pages: Foresight ARS 5.5.0 (3), TI 5.4.0 (4) and 5.5.0 (9), Patterns 6.1.2 (1), Reward 22.2.0 (7). | none |
| DOCOPS-366 | Note: (1) the callout rule `[data-attr-keyref^="!"]` counts AEM's alert markup as "no label" although the label shows. TI 6.0.0 has 69 and 5.5.0 has 13, and the Markdown has no alert. (2) Subsystem paths on Instream 9.3.0 and TI 5.5.0. (3) `\<samp>` in raw HTML, a long URL as link text, and the hotfix page under another name. | none |
| DOCOPS-370 | Note: TI 5.5.0 Docker page: whole sections nested in a list step are not served (133 sentences, 4 tables, 4 pictures). Also the Kafka 6.8.x icon in a menu cascade and the Pulsar 5.0.0 picture in `<pre>`. | none |
| DOCOPS-351 | Note: heading-row menus also on Foresight ARS 5.4/5.5, TI 5.4/5.5, OpMon 5.4, Studio 9.2, Patterns 6.1.2, Adapter Framework 1.3.0–1.6.0 and BW MDM 6.3.1. | none |
| DOCOPS-349 / 345 / 363 / 362 | Notes with the examples in section 1 (A1, A4). | none |

---

## 6. UAT-sheet rows (Digital Platform)

Each row below is one Critical row per family, with the full Stage 3 list. Each extends the matching 14 Nov row: replace that row, or paste the new list into its Comments.
- **Instream:** already in the sheet; add 9.2.0 and 9.3.0 to its Comments.
- **ActiveSpaces:** the row is in the Stage 2b report.
- **DOCOPS-344 (empty article):** add the 24 new pages of section 1 to the existing row's Comments.

```csv
Type,Issue description,Issue screenshot,Category,Priority,Found In,Reporter,Status,Assignee,Stage Issue link,Prod Issue link,Comments,DEV status / comment
Desktop,"BusinessWorks plug-ins: online help is not on staging for 96 versions of 33 plug-ins checked on 16 Nov, although they are on wip (since 6 Oct-6 Nov). The version page and the first menu page give no menu. Most folder names are over 50 characters (the AEM cut, DOCOPS-372), but 5 versions have names of 49-50 characters and are not served either: SFTP 1.1.1 and 6.1.4; SWIFT 5.24.0, 5.25.0 and 6.10.0. Served in the same batch (names of 50 characters or fewer): AMQP, CICS 1.2.2/1.5.0, EJB, LDAP 6.1.2, MDM, OData, PDF, Redis, AI. Staging URL: https://stg-docs.tibco.com/us/en/tibco-activematrix-businessworks-plug-in-for-swift/online-help/6-10-0.html Github URL: https://github.com/tibco/en-us-tib-bw-plugin-userdocs/tree/wip/en-us/tibco-activematrix-businessworks-plug-in-for-swift/online-help/6-10-0",,Content,Critical,"BusinessWorks plug-ins (96 versions, 33 plug-ins), e.g. Apache Kafka 6.8.1, SWIFT 6.10.0, SFTP 6.1.4",Mayur,New,,https://stg-docs.tibco.com/us/en/tibco-activematrix-businessworks-plug-in-for-swift/online-help/6-10-0.html,,"DOCOPS-346, DOCOPS-372; verify Mon 16 Nov 13:00-14:20 IST; extends the 12 and 14 Nov rows",
Desktop,"Managed File Transfer (MFT): online help is not on staging. 6 versions have short folder names (41-43 characters) and have been on wip since 15 Oct: Command Center 8.6.0, 8.7.0, 8.7.1 and Internet Server 8.6.0, 8.7.0, 8.7.1. The version page and the first menu page give no menu. The 8 Platform Server versions (UNIX 8.1.1, 8.1.2, 8.2.0; Windows 8.1.0, 8.2.0; z/Linux 8.1.0, 8.1.1, 8.1.2) have wip folder names of 52-56 characters; their rename under 50 is ready and waits for AEM's answer on the 50-character cut. Staging URL: https://stg-docs.tibco.com/us/en/tibco-managed-file-transfer-command-center/online-help/8-7-0.html Github URL: https://github.com/tibco/en-us-tib-mft-userdocs/tree/wip/en-us/tibco-managed-file-transfer-command-center/online-help/8-7-0",,Content,Critical,Managed File Transfer (MFT) (14 versions),Mayur,New,,https://stg-docs.tibco.com/us/en/tibco-managed-file-transfer-command-center/online-help/8-7-0.html,,"DOCOPS-346 (Command Center, Internet Server), DOCOPS-372 (Platform Server); verify Mon 16 Nov 13:00-15:00 IST; extends the 14 Nov row",
Desktop,"Streaming: online help is not on staging for Streaming 11.1.2, 11.1.3, 11.2.0 and 11.2.1 and for Spotfire Data Streams 11.1.1, although they are on wip (since 29 Sep / 30 Oct) and the folder names are short (15 and 21 characters). The version page and the index page give no menu. Streaming 11.1.0, 11.1.1 and Data Streams 11.1.0 are served. Staging URL: https://stg-docs.tibco.com/us/en/tibco-streaming/online-help/11-2-1.html Github URL: https://github.com/tibco/en-us-tib-streaming-userdocs/tree/wip/en-us/tibco-streaming/online-help/11-2-1",,Content,Critical,"Streaming (4 versions), Spotfire Data Streams 11.1.1",Mayur,New,,https://stg-docs.tibco.com/us/en/tibco-streaming/online-help/11-2-1.html,,"DOCOPS-346; verify Mon 16 Nov 13:00-15:00 IST; extends the 14 Nov row",
```

---

## 7. Open questions

1. **Streaming merge (N1).** Fetch, then raise a PR of `content-fix` into `wip` for `en-us-tib-streaming-userdocs`, keeping Digital Platform's two test commits? This is a push, so it needs your go-ahead. Until it lands, Streaming 11.1.0 and 11.1.1 show notes without labels, the old menus and the old `301.yml`.
2. **Checker rule for notes (N3).** Change verify to count alert markup as unlabelled only where the Markdown still holds `[!…]`? It would also stop the R001 entry hiding cases like Streaming. That is a code change, to describe in DOCOPS-366 first.
3. **TI 5.5.0 Docker page (N2).** Re-convert with the sections taken out of the list, with the DOCOPS-370 re-converts, or edit the one page by hand?
4. **"Nested under a page" (S3-opt).** The 14 Nov question again; here it covers 8 versions and 14 findings.
