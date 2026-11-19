# Verify triage: ibi batch 2, second part, 2026-11-19

This is a read-only triage. No repo file or config was edited, nothing was run against staging, logged in Jira or pushed. `cache/state.db` was opened read-only. The only files written are this report and its YAML (helpers in `C:/tmp/ibi2b-triage`).

---

## Summary for all ibi checked so far (one page)

**What was checked.** 133 ibi versions have been compared with the staging site (stg-docs.ibi.com) in three rounds: batch 1 (41 versions, 16–17 Nov), batch 2 first part (58, 18 Nov morning) and this part (34, 18 Nov afternoon to 19 Nov 06:48). 72 of them are PDF-only versions with nothing to show online, and all 72 are fine. The other 61 are online help.

**What is broken, in plain words.**

1. **Pages that show a title and nothing else (Digital Platform).** This is the biggest problem for readers.
   - **Whole versions:** all of Reporting Server 9.3.1 (2,386 pages) and App Studio 9.3.6 (299 of 302 pages) are blank.
   - **The same 400-odd Reporting Server pages in every version:** mostly the Server Administration guide. They are blank in 9.3.0, 9.3.2, 9.3.3, 9.3.4 and 9.3.6. Because the same pages fail in every version, this looks like a page-level fault on the platform rather than one stalled upload.
   - **Smaller cases:** FOCUS 9.3.1 (395 pages), Data Intelligence 1.0.0 (22) and Installer 9.3.5 (6 of 7). WebFOCUS Client's "Installation Requirements" page is blank in 9.3.0, 9.3.1 and 9.3.8.
   - **What we checked:** our files for these pages are complete.
2. **Pictures that show a grey placeholder (ours, already fixed, waiting to ship).**
   - **How many:** about 8,000 pictures across Data Intelligence, FOCUS, Open Data Hub, WebFOCUS Client, iWay Service Manager, Data Quality, Reporting Server, App Studio and Installer. A few menu entries are missing for the same reason, such as "What's New" and the Container Edition 1.3.4 installation guide.
   - **Cause:** upper- and lower-case letters in file names.
   - **Status:** fixed on our `content-fix` branch. **It clears by itself when `content-fix` is published to `wip`.**
3. **Stray characters and cut pages (ours, mostly fixed, waiting to ship).**
   - **What readers see:** backslashes and `\<` show in the text, about 4,000 times in WebFOCUS Client alone.
   - **One escape cuts a page short:** WebFOCUS Client "Application Settings" stops halfway through, losing 20 sections.
   - **Status:** both are fixed on `content-fix` and **clear when it ships**.
   - **Still to build (small):** a handful of pages show "&" where the source shows the word "&amp;", such as XMLDECOD and XMLENCOD and four iWay pages.
4. **Old-site links that would break at cutover (ours, still to build).** The redirect maps for WebFOCUS Client 9.3.8, Reporting Server 9.3.8 and DSML Services 9.3.8 have no rows for the release-notes pages. That is 137 old pages, on top of the 323 App Studio 9.3.8 pages found earlier. Rebuilding the four maps and pushing them is a short task.
5. **Pictures written with the wrong address (Digital Platform).** All 780 pictures of App Studio 9.3.8 are written with a page address instead of the image store. This was found in the first part and is unchanged.
6. **Stale menu rows (Digital Platform).** FOCUS 9.3.4 and 9.3.7 show two old top-level menu entries (found in batch 1, DOCOPS-377).
7. **Things that are not problems.**
   - About 3,600 links point at bookmarks that the source never had, so they open the page at the top, as they always did.
   - Pages listed twice in a menu are shown once.
   - The rest are false alarms from our checker.

**New this time: the staging site started refusing our checker (Digital Platform question, our tool fix).**
- **When:** from about 19:30 on 18 Nov until 05:52 on 19 Nov.
- **What happened:** stg-docs.ibi.com answered "429 Too Many Requests" or dropped the connection for about 2,000 page requests.
- **Effect on results:** 10 versions are still marked `lost` only because of this. Their results are incomplete, not bad. They are Reporting Server 9.3.2, 9.3.3, 9.3.5, 9.3.6 and 9.3.8, iWay Service Manager 9.3.0, WebFOCUS Client 9.3.1, Container Edition 9.3.8, DSML Services Container Edition 9.3.8 and Data Quality 5.2.2.
- **Our side:** the checker should wait and retry instead of counting a refusal as a missing page.
- **Digital Platform's side:** they should tell us whether a rate limit was switched on.
- **Next step:** re-run those 10 versions during the day, with fewer parallel slots.

**Per product, all three rounds** (content side = ours or the source; design side = Digital Platform). Counts are findings; "versions" counts online and PDF-only. Status uses today's config for batches 1 and 2a, and today's config plus this report's YAML for this part.

| Product | Versions checked | Content side (kinds / findings) | Design side (kinds / findings) | lost / issues / logged / explained / clean |
|---|---|---|---|---|
| Data Intelligence | 5 | letter case 819 pictures + What's New/Installation menu rows (374, on content-fix); empty menu titles 228 rows (376, to build); escapes `\<` `\\` (360, on content-fix); 1 source bookmark | blank pages DI 1.0.0: 22 (344) | 0 / 0 / 5 / 0 / 0 |
| iWay Service Manager EDI Add-on | 2 | letter case: What's New dropped (374, on content-fix); escapes (360) | none | 0 / 0 / 2 / 0 / 0 |
| FOCUS | 19 (10 PDF) | letter case 3,171 pictures + Overview row (374, on content-fix); escapes and `&amp;` (360); INDEX topic dropped 27 (349, to build); empty titles 5 (376); old bookmarks 2,226 (source) | blank pages 9.3.1: 395 (344); stale menu rows 9.3.4/9.3.7: 99 (377) | 0 / 9 / 0 / 0 / 10 |
| AI Assistant | 1 | none | alt text dropped 5 (255) | 0 / 0 / 0 / 1 / 0 |
| Omni family, Web Query for IBM i, iWay BAM/TPM | 14 (all PDF) | none | none | 0 / 0 / 0 / 0 / 14 |
| Open Data Hub for Mainframe Connectors | 15 (4 PDF) | letter case 336 pictures (374, on content-fix); escapes (360, on content-fix); heading ids 27 (345) | none | 0 / 1 / 10 / 0 / 4 |
| WebFOCUS App Studio | 23 (14 PDF) | letter case 39 pictures (374); 9.3.8 redirect map empty 323 (322, to build); old bookmarks 576 (source); escapes (360, on content-fix) | 9.3.8 pictures not from the image store 788 (347); 9.3.6 blank 299 of 302 pages (344) | 0 / 2 / 7 / 0 / 14 |
| WebFOCUS Installer | 10 (3 PDF) | letter case 36 pictures (374); old bookmarks 30 (source); escapes (360, on content-fix) | 9.3.5 blank 6 of 7 pages (344) | 0 / 0 / 1 / 6 / 3 |
| WebFOCUS Reporting Server | 22 (14 PDF) | letter case 210 pictures (374); 9.3.8 redirect map missing release notes 66 (322, to build); `&amp;`/`&gt;` shown 18 (360, to build); escapes (360, on content-fix); heading ids 24 (345); old bookmarks 43 (source) | blank pages: 9.3.1 whole version 2,386, the same ~410 pages in 9.3.0/9.3.2/9.3.3/9.3.4/9.3.6 (344); 429 refusals 9.3.5/9.3.6/9.3.8 | 5 / 3 / 0 / 0 / 14 |
| WebFOCUS Client | 16 (13 PDF) | letter case 3,155 pictures (374, on content-fix); "Application Settings" cut short 15 links (360, on content-fix); escapes about 640 `\<` and 3,640 `\\` (360, on content-fix); 9.3.8 redirect map missing release notes 66 (322, to build); INDEX topic 9 (349, to build); `&amp;` shown 4 (360, to build); old bookmarks 691 (source) | Installation Requirements blank in 3 versions (344); 7 refusals in 9.3.1 | 1 / 2 / 0 / 0 / 13 |
| WebFOCUS DSML Services | 1 | 9.3.8 redirect map has no page rows 5 (322, to build); stray draft page in Unfiled with 66 dead links (source, remove) | none | 0 / 0 / 0 / 1 / 0 |
| WebFOCUS Container Edition | 2 | letter case: 33 menu rows of 1.3.4 (374, on content-fix) | 9.3.8: 15 refusals | 1 / 0 / 0 / 1 / 0 |
| DSML Services Container Edition | 1 | letter case 3 pictures (374) | 1 refusal | 1 / 0 / 0 / 0 / 0 |
| Data Quality | 1 | letter case 59 pictures + What's New row (374, on content-fix) | 3 refusals | 1 / 0 / 0 / 0 / 0 |
| iWay Service Manager | 1 | letter case 112 pictures + What's New row, 271 menu shifts (374, on content-fix); `&amp;`/`&lt.` shown on 4 pages (360, to build); old bookmarks 23 (source) | 553 refusals (only 1,068 of 1,604 pages checked); 1 blank page (344) | 1 / 0 / 0 / 0 / 0 |
| **All** | **133 (72 PDF)** | | | **10 / 17 / 25 / 9 / 72** |

- **The 17 `issues` are warnings only.** They are old-menu moves (`TOC_MOVED`, held for the DOCOPS-375 per-product review) plus 3 menu-order warnings, and none of them hides a missing page.
- **The 10 `lost` are all from the staging refusals above.**

---

## This part: what was checked

- **The batch:** `cache/overnight/ibi2-new.txt`, `ibi2-a.txt`, `ibi2-b.txt`, all `--refresh`. Only lines that finished `ok` or `ok-findings` after the first triage's cut-off (18 Nov 14:29 IST) count. FAILED lines are ignored.
  - **Two sessions:** 18 Nov afternoon until the disk filled at 23:49, then the re-run from 19 Nov 01:41.
  - **Disk-full crashes:** the crashed lines from the first session were re-run: Reporting Server 9.3.5, 9.3.6 and 9.3.8, Container Edition 9.3.8, DSML Services CE 9.3.8, Data Quality 5.2.2 and iWay Service Manager 9.3.0.
- **This triage's cut-off: 19 Nov 06:48 IST (01:18 UTC), run 3183.** 34 versions have a stored result in this window, in runs 3067–3183:
  - **Triaged (21 online versions):**
    - WebFOCUS Client 9.3.0, 9.3.1, 9.3.8;
    - App Studio 9.3.4–9.3.7;
    - Reporting Server 9.3.1–9.3.6, 9.3.8;
    - Installer 9.3.6;
    - DSML Services 9.3.8;
    - Container Edition 9.3.8, 1.3.4;
    - DSML Services Container Edition 9.3.8;
    - Data Quality 5.2.2;
    - iWay Service Manager 9.3.0.
  - **PDF-only, local check, all `clean` (13):** WebFOCUS Client 9.1.0–9.2.7.
- **Running at the cut-off:**
  - Reporting Server 9.3.7 (`ibi2-b` line 31, started 06:05);
  - WebFOCUS Client 9.3.2 (`ibi2-a` line 52, started 06:10).
- **Not started, or no result stored (68 lines):**
  - WebFOCUS Client 9.3.3–9.3.7;
  - DSML Services 9.1.0–9.3.7;
  - Installer 9.1.0–9.2.3;
  - Container Edition 1.0.0–1.3.3 and 9.3.5–9.3.7;
  - DSML Services Container Edition 1.0.3–1.0.7 and 9.3.5–9.3.7;
  - Data Quality 3.0.0–5.2.1;
  - iWay Service Manager 8.0.5–9.2.0.
- **Container Edition 1.2.2–1.3.3 need a re-run.** `ibi2-b.summary` marks them `ok-findings` (lines 042–049), but no log and no result were written: the disk was full. Their latest result is still the 27 Oct local one, so they are re-runs, not checked versions.
- **Method:** the same as batches 1 and 2. The triage file was applied in memory the way `verify --retriage` applies it (`triage.decide`, `issues.tally`), two ways:
  - with today's `config/verify-triage.yaml` (batch 1 and batch 2 entries included);
  - with that config plus this report's YAML pasted above the catch-alls.
- **Evidence:**
  - the Markdown on `origin/wip` and `origin/content-fix` of the four ibi repos;
  - the extracted packages under `families/`;
  - the staging pages these runs cached in `cache/verify/`. No new staging request was made.
- **Repos:** staging's ibi content has had no `wip` push since 10–11 Nov. `content-fix` carries these fixes for all four ibi repos: letter case (DOCOPS-374), R002 escapes (DOCOPS-360) and the Help menu titles.
- **Side note: Japanese builds.** The Reporting Server 9.3.5 and 9.3.8 runs also checked the Japanese builds ("lost", in the logs only). `state.db` keeps only the English result.

**Where this part stands (34 versions):**

| Entries applied | lost | issues | logged | explained | clean | Unexplained findings |
|---|---|---|---|---|---|---|
| Today's config | 20 | 0 | 1 | 0 | 13 | 4,664 (3,739 errors, 925 warnings) |
| + this report's YAML | **10** | 5 | 3 | 3 | 13 | **2,320** (1,905 errors, 415 warnings) |

- **All 1,905 errors left are findings made while staging refused us.** The cached answer is HTTP 429 or nothing: verify counts a dropped connection as "not served" without caching it.
  - **Reporting Server 9.3.6:** 1,310. Only 1,074 of 2,375 pages answered.
  - **iWay Service Manager 9.3.0:** 554. 1,068 of 1,604 answered.
  - **Container Edition 9.3.8:** 15.
  - **WebFOCUS Client 9.3.1:** 7.
  - **Reporting Server 9.3.5:** 6. Its menu page got a 429, so no page of the version was compared.
  - **Reporting Server 9.3.3:** 4.
  - **Reporting Server 9.3.8:** 3. Its menu page got no answer, so no page was compared. The crashed first run of 18 Nov (run 3128) did compare it, but 576 of its pages were refused too.
  - **Data Quality 5.2.2:** 3.
  - **Reporting Server 9.3.2:** 2.
  - **DSML Services CE 9.3.8:** 1.
  - Nothing else is open in these 10 versions.
- **The 415 warnings left:**
  - 412 old-menu moves (`TOC_MOVED`, DOCOPS-375 review, not triaged on purpose);
  - 2 `TOC_ORDER` (the Regular Expression functions in Client 9.3.8 and RS 9.3.8);
  - 1 `PUBLISHED_TOC_ORDER` (App Studio 9.3.6's top level).
- **The 5 `issues`:** WebFOCUS Client 9.3.0 and 9.3.8, Reporting Server 9.3.1 and 9.3.4, App Studio 9.3.6. All are warnings only.
- **Entries:** the YAML has 190 active entries. Every one decides at least one stored finding of this part, and each is limited to the slug and the versions checked here. None is commented out, because every `ours` or `logged` entry fits an existing DOCOPS key.

---

## 1. Open problems, split by who fixes them

### (a) Content side: ours or the source documentation

| # | What | Reader effect | Products / versions (findings) | Jira | Fix; on `content-fix`? |
|---|---|---|---|---|---|
| **A1** | **Letter case on `wip`.** `Resources/Images/`, `Whats-New.md` and `Installation-and-Deployment-Guide/` are on `wip`; the links use lower case. | Grey placeholder instead of the picture; "What's New" or a whole guide's menu missing. | WebFOCUS Client 9.3.0 (1,080), 9.3.1 (1,078), 9.3.8 (997) pictures; Reporting Server 9.3.1–9.3.6 (13–57 each, 193); iWay Service Manager 9.3.0 112 pictures + What's New dropped (263 shifted menu rows, 8 pages compared with a neighbour); Data Quality 5.2.2 59 pictures + What's New (12 menu findings); App Studio 9.3.4–9.3.7 (27); Installer 9.3.6 (6); DSML Services CE 9.3.8 (3); Container Edition 1.3.4: all 33 rows under "Installation and Deployment Guide" missing. **3,555 pictures, 316 menu findings.** | DOCOPS-374 | **On `content-fix`** (9da55f7b, d92a8864, cfe3f1c, a3a0932); clears when it reaches `wip`. Each picture was checked: the exact path is on `content-fix`, and on `wip` only in another letter case (0 exceptions). |
| **A2** | **Page cut short by an escaped `\<a href>`** | WebFOCUS Client "Application Settings" stops after "…\<u>, \<a href>,". AEM turns the text into a real link, and about 8,500 of 21,000 words (20 sections) are not shown. | Client 9.3.0, 9.3.1, 9.3.8 (15 dead section links). On `wip`, 18 Client pages (9.3.0–9.3.8, including an Unfiled copy in 9.3.0/9.3.1) have the pattern. | DOCOPS-360 | **On `content-fix`** (R002, 0cec5732: `&lt;a href>`; 0 pages left); clears when it ships. |
| **A3** | **Escapes shown** (`\<`, `\\` in prose) | Stray backslashes ("drive:\\ibi\\…", "\<Vendor"). | `\<` / `\\` shown (pages): Client 9.3.0 228/1,340 (68/126), 9.3.1 206/1,193, 9.3.8 204/1,111; RS 9.3.2–9.3.4 35/~400 (17/94), 9.3.6 24/280 (of 1,074 checked); iWay SM 9.3.0 20/325; App Studio 9.3.4, 9.3.5, 9.3.7 20/130 each; Data Quality 5.2.2 5/3; Installer 9.3.6 0/3. Left under the DOCOPS-348 text catch-all. | DOCOPS-360 | **On `content-fix`** (R002 for WebFOCUS, RS, DI/ISM, CE); clears when it ships. |
| **A4** | **Entity names shown as characters** | "For &, the result is &." (source: "For &amp;…"); "A&B becomes A&B"; "such as <. to <". | XMLDECOD/XMLENCOD: Client 9.3.0, 9.3.1; RS 9.3.1–9.3.6, 9.3.8 (20 findings). iWay SM 9.3.0: 4 pages (`_entity()`, entity preemitter, XD.entityExpand). | DOCOPS-360 | **To build:** unchanged on `content-fix`; the source text needs `&amp;amp;`-style escaping. |
| **A5** | **Redirect maps missing the release notes** | Every old docs.tibco.com release-notes URL of these versions would 404 at cutover. | WebFOCUS Client 9.3.8: 66 rows; Reporting Server 9.3.8: 66 (`relnotes/en-us/Release-Notes-93x/…`, `_templates/…`); DSML Services 9.3.8: 5 (no page rows at all). 137 in all, plus App Studio 9.3.8's 323 (first part). | DOCOPS-322 | **To build:** rebuild the four `9-3-8/301.yml` (sync, then a `content-fix` commit). Same cause: built 5 Nov (d71782d0) before the page lists were cached. |
| **A6** | **"INDEX" topic dropped** | The SET INDEX parameter topic (`dev-reporting-apps/INDEX.htm`) is missing, with its menu row and redirect. | WebFOCUS Client 9.3.0, 9.3.1, 9.3.8 (9), as FOCUS in batch 1. | DOCOPS-349 | **To build:** the converter skips any file named INDEX.htm. |
| **A7** | **Stray draft page (source)** | DSML Services 9.3.8 has an Unfiled page "WebFOCUS Container Edition — ECS Deployment Guide" that is only a contents list, with 66 links to headings it does not have. | DSML Services 9.3.8 (66). The package ships it as `html/temp/WebFOCUS_Container_Edition.htm`; no old menu lists it. | none (source) | **To decide:** remove the page and its menu row on `content-fix` (one file). The old menu also names three files the package does not ship (DSML `dsml_intro.htm`; RS 9.3.3 `SOLR_preparing.htm`, `ms_365_dataflow_934.htm`). Nothing to convert. |
| A8 | **Old bookmarks never defined in the source** | The link opens the page at its top, as on the old site. | Client 9.3.0 342, 9.3.1 338, 9.3.8 11; App Studio 9.3.4 111; iWay SM 23; RS 9.3.2–9.3.4 19–24; Data Quality 1 (`#Service3`). 935 in all. | none (source) | No fix: the whole extracted package of each version was searched for an `id=`/`name=` with each value, and none matched. |
| A9 | **Heading-id differences** | The link opens the page at its top. | Doubled hyphens (`#mailing--an-html-file-…`, `#creating--------file-…`), the code part dropped (`#supplied-files-location`), `<a id="_regex()">` not kept, CE 9.3.8 "PART 4" heading inside a list. RS 9.3.2–9.3.6, Client 9.3.0/9.3.1, iWay SM, CE 9.3.8 (29). | DOCOPS-345 | Waits on AEM's id rule (as before). |
| A10 | **Checker false findings** | None: staging shows the sentence or code correctly. | Split sentences in raw HTML, `&REGION`/`&LTABLE` read as entities, raw `<strong>`/`<pre>`, `<IMG SRC="/ibi_html/…">` in example code (73). Also 8 "redirect not served" proven false by the cached page (429 at the time). | DOCOPS-366 | Checker fixes, as before. |
| **A11** | **Checker counts a refusal as "not served"** | No reader effect, but 10 versions read `lost` and about 2,000 findings are unknowns. | Staging answered 429 or nothing between 18 Nov ~19:30 and 19 Nov 05:52 IST. Affected: RS 9.3.2, 9.3.3, 9.3.5, 9.3.6, 9.3.8; iWay SM 9.3.0; Client 9.3.1; CE 9.3.8; DSML CE 9.3.8; DQ 5.2.2 (1,905 findings). | **new kind proposed** (or a note on DOCOPS-366) | **To build:** `verify/fetch.py` should back off and retry on 429 and connection errors, never cache a 429, and say "unchecked" rather than `PAGE_MISSING`. Also clear the cached 429 answers (about 1,700 entries) before the re-run: without `--refresh` they would be read back as answers. |
| A12 | Unlisted duplicate pages (layout leftovers) | None; readers reach the listed copy. | Reporting Server 9.3.8 `ibi-webfocus/legal-and-third-party-notices.md` (as App Studio 9.3.8). | none (accepted) | Tidy: remove the unlisted copy. |
| A13 | Old-menu moves | Not a defect by itself. | 412 warnings (Client 9.3.0, 9.3.1, 9.3.8; RS 9.3.1–9.3.6, 9.3.8). | DOCOPS-375 | Per-product review. |

### (b) Design / platform side: for Digital Platform

| # | What | Evidence | Reader effect | Jira |
|---|---|---|---|---|
| **D1** | **Whole versions served blank.** Reporting Server 9.3.1: 2,386 of 2,387 pages. App Studio 9.3.6: 299 of 302 (every guide). | RS: `https://stg-docs.ibi.com/us/en/ibi-webfocus-reporting-server/online-help/9-3-1/resource-analyzer/configuring/configuring-resource-management.html` (0 words; Markdown 2,596). App Studio: `…/ibi-webfocus-app-studio/online-help/9-3-6/installation-and-configuration/appendix-a-configuring-a-network-installation/network-installation-steps.html` (0 words; Markdown 3,622). | The two versions are unreadable: title only. | DOCOPS-344 |
| **D2** | **The same pages blank in every Reporting Server version.** 422 (9.3.2), 424 (9.3.3), 400 (9.3.4) and 123 of the 1,074 that answered (9.3.6); 418 of 9.3.3's 424 are also blank in 9.3.0 (910). Mostly Server Administration (about 410 of 620), Gathering Diagnostic Information (4 of 4) and a few Unfiled. Also: WebFOCUS Client "Installation Requirements" (Windows) blank in 9.3.0, 9.3.1, 9.3.8; 1 iWay SM page. | `…/ibi-webfocus-reporting-server/online-help/9-3-3/gathering-diagnostic-information-customer-support/create-savediag-from-webfocus-reporting-server.html`: 200, `data-page-path` correct, `div.topic-renderer__content` empty; Markdown 298 words, plain (headings, list, one picture). Blank in 9.3.0, 9.3.2, 9.3.3, 9.3.4 and 9.3.6. | Two thirds of the Server Administration guide is unreadable in every version. It is not a one-off stalled build, because the same pages fail every time. | DOCOPS-344 (new extent and pattern) |
| D3 | Pictures not served from the image store (unchanged kinds) | Client 9.3.0/9.3.1/9.3.8: 51 pictures with a page-relative `src` each; iWay SM 31 with an empty `src`; App Studio 9.3.4–9.3.7 13 each; RS 9.3.2–9.3.4 about 330 each (most on blank pages). App Studio 9.3.8 (first part: 780 of 780) is unchanged. | Missing pictures. | DOCOPS-347 |
| D4 | Alt text with `/` or `:` dropped (unchanged) | 122 in this part. | Screen readers lose part of the text. | DOCOPS-255 |
| **D5** | **Staging refused our checker (question).** HTTP 429 "Too Many Requests" and dropped connections, 18 Nov from ~15:57 (a few) and steadily 19:30, to 19 Nov 05:52 IST. The overnight runs used 2–3 slots of 6 threads each, as before; the first part (to 14:29 on 18 Nov) left no refused page in this part's results. | `…/ibi-webfocus-reporting-server/online-help/9-3-5/ibi-webfocus-reporting-server.html`: cached 429 at 01:48 on 19 Nov. RS 9.3.6: 921 answers were 429 and 380 had no answer. | None for readers if it is only a limit on bursts. We need to know the allowed rate so the re-run does not trip it. | none (question; new kind only if a defect) |

Already reported and still open (no change seen here): FOCUS 9.3.4/9.3.7 stale menu rows (DOCOPS-377), App Studio 9.3.8 pictures (DOCOPS-347), FOCUS 9.3.1, DI 1.0.0 and Installer 9.3.5 blank pages (DOCOPS-344).

---

## 2. Things to know first (this part)

1. **Reporting Server 9.3.1 and App Studio 9.3.6 are blank as whole versions (D1).**
   - **Measured:** 2,386 of 2,387 and 299 of 302 pages have an empty article.
   - **9.3.6's last check before this:** on 25 Oct its staging check was blocked by menu findings, so there is no earlier baseline.
   - **Entries:** the YAML moves all their anchors, pictures and text to DOCOPS-344. RS 9.3.1 is version-wide after the letter-case pictures; App Studio 9.3.6 uses 18 globs that cover blank pages only.
2. **The Reporting Server blank pages are the same pages in every version (D2).**
   - **The match:** 418 of 9.3.3's 424 blank pages are also blank in 9.3.0, and 9.3.2 and 9.3.4 match 9.3.3 in all but a few.
   - **What this suggests:** a fault tied to those pages on the platform side, not a stalled upload. Our Markdown for them is ordinary.
   - **Entries:** only the links into them are moved to DOCOPS-344 (7, 7, 5 and 4 globs). Their pictures and text stay under the DOCOPS-347/348 catch-alls, as for 9.3.0.
3. **Staging throttled the overnight runs (A11, D5).**
   - **Where it shows:** every `lost` left in this part is a 429 or an unanswered request.
   - **Proven false:** for 8 "redirect not served" findings, the cached page is 200 with the right `data-page-path`. They are moved to DOCOPS-366.
   - **Left open:** the rest, because a refusal says nothing about the page.
   - **Before the re-run:** 1,700 cached 429 answers sit in `cache/verify/`. They would be read back as answers by any run without `--refresh`.
4. **WebFOCUS Client "Application Settings" is cut in half by `\<a href>` (A2).**
   - **The effect:** the 15 dead section links come from that.
   - **Status:** R002 on `content-fix` fixes all 18 pages.
5. **Three more 9.3.8 redirect maps lack the release notes (A5).**
   - **Which:** Client 9.3.8 (66), Reporting Server 9.3.8 (66) and DSML Services 9.3.8 (5).
   - **Cause:** the same as App Studio 9.3.8 in the first part. The maps date from 5 Nov, before the page lists were cached.
6. **Letter case (A1):**
   - **3,555 pictures,** all checked one by one.
   - **Menus:** "What's New" dropped from Data Quality 5.2.2 and iWay Service Manager 9.3.0. Every row after it then pairs with the wrong neighbour: 263 iWay rows "moved", 7 iWay pages compared with a same-named page in another EDI guide.
   - **Container Edition 1.3.4:** all 33 rows of its installation guide are missing from the menu, because the folder on `wip` is `Installation-and-Deployment-Guide/`.
7. **Smaller items:**
   - **App Studio 9.3.4:** the authored `html_responsive.htm` page is accepted, as 9.3.3 was.
   - **Reporting Server 9.3.2:** the IMS page with an empty product variable in the source is accepted.
   - **Pages listed twice in `toc.yml` and shown once** (235 findings, accepted):
     - the SQL function rows in Client and RS;
     - Common Windows-Based Java Implementations and Third-Party Software under four platforms (RS);
     - Client 9.3.8's 14 Installation pages shared by Windows and UNIX/Linux;
     - Deleting a Role, Adding a Rule, Autoprompt Parameter Prompting, the Chart Rollup Tool, REGEXP_SUBSTR (3 rows);
     - iWay "Configuring iWay HTTP Services (Adapters)".
   - **RS 9.3.2–9.3.4:** the `#top` link is accepted.

---

## 3. Per-version table

"Now" uses today's config; "+YAML" adds this report's entries. Kinds are as in section 1.

| Step | Version | Now | +YAML | Main kinds / what is left |
|---|---|---|---|---|
| new003 | WebFOCUS Client 9.3.8 | lost | issues | A1 997, A5 66, A2 5, A6 3, A8 11, D1 2 links, A10 10, accepted menu 49; left: 88 `TOC_MOVED`, 1 `TOC_ORDER` |
| new004 | DSML Services 9.3.8 | lost | explained | A7 66, A5 5, old menu file 1 |
| new005 | Installer 9.3.6 | logged | explained | A1 6 |
| new006 | Reporting Server 9.3.8 | lost | **lost** | A5 66, A4 4, A10 4, A12 1, D5 5 proven false; **left: 3 refused (menu page, 2 redirects)**, 62 `TOC_MOVED`, 1 `TOC_ORDER` |
| new007 | Container Edition 9.3.8 | lost | **lost** | A9 1; **left: 15 refused** |
| new008 | DSML Services CE 9.3.8 | lost | **lost** | A1 3; **left: 1 refused** |
| new009 | Data Quality 5.2.2 | lost | **lost** | A1 59 + 12 menu, A8 1; **left: 3 refused** |
| new010 | iWay Service Manager 9.3.0 | lost | **lost** | A1 112 + 271 menu, A4 4, A8 23, A9 1, A10 5; **left: 553 refused pages, 1 refused redirect** |
| a033 | App Studio 9.3.4 | lost | logged | A8 111, A1 1, A10 1, accepted 1 |
| a034, a036 | App Studio 9.3.5, 9.3.7 | lost | logged | A1 9 each, A10 1 each |
| a035 | App Studio 9.3.6 | lost | issues | **D1** (299 of 302 pages: 16 links, 869 pictures, 299 text), A1 8, A10 1; left: 1 `PUBLISHED_TOC_ORDER` |
| a050 | WebFOCUS Client 9.3.0 | lost | issues | A1 1,080, A8 342, A2 5, A9 3, A6 3, A4 2, A10 10, D2 2; left: 20 `TOC_MOVED` |
| a051 | WebFOCUS Client 9.3.1 | lost | **lost** | as 9.3.0 (A1 1,078, A8 338); **left: 7 refused**, 20 `TOC_MOVED` |
| b025 | Reporting Server 9.3.1 | lost | issues | **D1** (whole version: 507 links, 2,181 pictures, 2,393 text), A1 13, A4 2, A10 4, accepted 36; left: 37 `TOC_MOVED` |
| b026, b027 | Reporting Server 9.3.2, 9.3.3 | lost | **lost** | **D2** (422/424 blank pages; 9 links each), A1 56/57, A9 6, A8 24/19, A4 2, A10 4, accepted 37–38; 9.3.3 also 2 missing old-menu files; **left: 2 / 4 refused**, 37 `TOC_MOVED` |
| b028 | Reporting Server 9.3.4 | lost | issues | **D2** (400 blank; 7 links), A1 57, A9 6, A4 2, A10 4, accepted 37; left: 37 `TOC_MOVED` |
| b029 | Reporting Server 9.3.5 | lost | **lost** | A4 2, A10 4; **staging not compared (menu page refused); left: 1 + 5 refused**, 37 `TOC_MOVED` |
| b030 | Reporting Server 9.3.6 | lost | **lost** | D2 (123 blank of 1,074 answered; 4 links), A1 10, A9 4, A4 2, A10 4, D5 1 proven false, accepted 36; **left: 1,302 refused pages + 8 refused redirects**, 37 `TOC_MOVED` |
| b050 (log 050) | Container Edition 1.3.4 | lost | explained | A1 33 menu rows |
| a037–a049 | WebFOCUS Client 9.1.0–9.2.7 (13, PDF-only) | clean | clean | local check only |

---

## 4. Proposed entries

All proposed entries are in `reports/verify/triage-ibi2b-2026-11-19.yaml`. It defines its own anchors (`&ibi2b-…`), so it loads on its own and after today's config. It was checked by loading today's config with the YAML pasted above the three catch-alls.

- **Where to paste:** directly above `  # Catch-alls: keep last`, after the ibi batch 2 block (J7).
- **Blocks:**
  - L1 letter case, with iWay's twice-listed row first (A1);
  - L2 blank articles (D1, D2);
  - L3 the `\<a href` cut (A2);
  - L4 heading ids, `#top` and source bookmarks (A9, A8, A7);
  - L5 text and example-code pictures (A4, A10, accepted authored pages);
  - L6 menus and INDEX (accepted twice-listed rows, A12, A6);
  - L7 redirect maps (A5);
  - L8 throttling findings proven false (A11).
- **Order matters:** the empty-page, R002 and DOCOPS-345 anchor entries come before the per-version `*.md#*` source entries.
- **Checked:**
  - every `ours DOCOPS-374` picture entry decides only pictures whose exact path is on `content-fix` and only in another letter case on `wip` (0 exceptions);
  - every DOCOPS-344 glob covers blank pages only (RS 9.3.1 is version-wide because 1 of its 2,387 pages has text);
  - every entry decides at least one finding.
- **Temporary:**
  - every `ours DOCOPS-374` and the DOCOPS-360 `application-settings` entry: delete after `content-fix` reaches `wip` and a re-verify;
  - the DOCOPS-322 entries: delete after the maps are rebuilt.
- **No entry for:**
  - findings made while staging refused us (left open on purpose until a re-run);
  - `TOC_MOVED` (DOCOPS-375);
  - `TOC_ORDER`;
  - the pictures and text on RS 9.3.2–9.3.6 blank pages (they stay `logged` under the DOCOPS-347/348 catch-alls).

---

## 5. Jira changes (to apply when you choose; none was made)

| Issue | Change | Points |
|---|---|---|
| DOCOPS-338 | Note: ibi batch 2 second part. 34 versions (13 PDF-only `clean`) to 19 Nov 06:48. With the proposed entries, 20 lost go to 10, and those 10 hold only findings made while staging refused requests (429 / no answer). Unexplained findings go from 4,664 to 2,320. Running: RS 9.3.7, Client 9.3.2. Not started: 68 lines. CE 1.2.2–1.3.3 need a re-run (disk full, no result stored). | none |
| DOCOPS-344 | Note: RS 9.3.1 is blank as a whole version (2,386 of 2,387 pages), and App Studio 9.3.6 is too (299 of 302). The same ~410 RS pages (mostly Server Administration) are blank in 9.3.0, 9.3.2, 9.3.3, 9.3.4 and 9.3.6, so this looks like a page-level fault rather than a stalled build. Also Client Installation Requirements (Windows) in 9.3.0, 9.3.1 and 9.3.8. | none |
| DOCOPS-374 | Note: 3,555 more pictures on staging (Client 9.3.0/9.3.1/9.3.8, iWay SM 9.3.0, DQ 5.2.2, RS 9.3.1–9.3.6, App Studio 9.3.4–9.3.7, Installer 9.3.6, DSML CE 9.3.8). What's New dropped in DQ 5.2.2 and iWay SM 9.3.0; CE 1.3.4's installation guide has no menu children. All fixed on `content-fix`. | none |
| DOCOPS-360 | Note: on staging, `\<a href>` cuts Client "Application Settings" in half (18 pages on `wip`, 0 on `content-fix`). `&amp;`/`&lt.` are still shown as characters on XMLDECOD/XMLENCOD (Client, RS) and 4 iWay SM pages; R002 does not cover that. | none |
| DOCOPS-322 | Note: Client 9.3.8 and RS 9.3.8 `301.yml` lack the 66 release-notes pages each; DSML 9.3.8 has no page rows (5). Rebuild together with App Studio 9.3.8. | none |
| DOCOPS-349 | Note: WebFOCUS Client 9.3.0, 9.3.1 and 9.3.8 also drop `dev-reporting-apps/INDEX.htm` (SET INDEX). | none |
| DOCOPS-366 | Note: more split sentences and `&REGIONMGR`/`&LTABLE`; example-code `<IMG>` read as pictures (Client); 8 "not served" findings that were 429s. | none |
| **New (ours, checker)** | `verify` counts HTTP 429 and dropped connections as "not served" and caches 429 answers. Add back-off and retry, do not cache 429, report "unchecked". Clear the about 1,700 cached 429 entries before the re-run. (Could instead be a note on DOCOPS-366.) | 0.25 |
| Question to Digital Platform (no key yet) | Was a rate limit switched on for stg-docs.ibi.com on 18 Nov (429 from ~19:30 IST)? What rate is allowed? | none |
| Optional | DSML Services 9.3.8: remove the stray Unfiled draft page (`html/temp/…`), as a note on DOCOPS-338. | none |

---

## 6. UAT-sheet rows (Digital Platform)

A1–A13 are ours or the source's, so they have no row. D3 and D4 are already in the sheet under DOCOPS-347/255.

```csv
Type,Issue description,Issue screenshot,Category,Priority,Found In,Reporter,Status,Assignee,Stage Issue link,Prod Issue link,Comments,DEV status / comment
Desktop,"ibi WebFOCUS Reporting Server 9.3.1 and ibi WebFOCUS App Studio 9.3.6 are served blank as whole versions: every page shows its title and an empty body. Reporting Server 9.3.1: 2,386 of the 2,387 pages checked on 18 Nov. App Studio 9.3.6: 299 of 302 pages (every guide). The Markdown is complete (e.g. Configuring Resource Management, 2,596 words; Network Installation Steps, 3,622 words). Please rebuild both versions and check why their articles are empty. Staging URL: https://stg-docs.ibi.com/us/en/ibi-webfocus-reporting-server/online-help/9-3-1/resource-analyzer/configuring/configuring-resource-management.html Github URL: https://github.com/csg-engops-product-docs/en-us-ibi-wf-reporting-server-userdocs/blob/wip/en-us/ibi-webfocus-reporting-server/online-help/9-3-1/resource-analyzer/configuring/configuring-resource-management.md",,Content,Critical,"ibi WebFOCUS Reporting Server 9.3.1 (2,386 pages), ibi WebFOCUS App Studio 9.3.6 (299 pages)",Mayur,New,,https://stg-docs.ibi.com/us/en/ibi-webfocus-reporting-server/online-help/9-3-1/resource-analyzer/configuring/configuring-resource-management.html,,"DOCOPS-344; verify Wed 18 Nov 13:00-15:30 IST; App Studio 9.3.6 example: https://stg-docs.ibi.com/us/en/ibi-webfocus-app-studio/online-help/9-3-6/installation-and-configuration/appendix-a-configuring-a-network-installation/network-installation-steps.html",
Desktop,"ibi WebFOCUS Reporting Server: the same pages are served blank in every version (title only, empty body): 422 pages in 9.3.2, 424 in 9.3.3, 400 in 9.3.4, 123 of the 1,074 checked in 9.3.6, and 910 in 9.3.0 (418 of 9.3.3's blank pages are also blank in 9.3.0). Mostly the Reporting Server Administration guide (about 410 of 620 pages) and all of Gathering Diagnostic Information. Because the same pages fail in every version, this does not look like one stalled build; something about these pages fails on the platform. The Markdown is plain and complete (e.g. Create a Savediag From the WebFOCUS Reporting Server browser interface, 298 words, one picture). Also blank: WebFOCUS Client 'Installation Requirements' (Windows) in 9.3.0, 9.3.1 and 9.3.8. Staging URL: https://stg-docs.ibi.com/us/en/ibi-webfocus-reporting-server/online-help/9-3-3/gathering-diagnostic-information-customer-support/create-savediag-from-webfocus-reporting-server.html Github URL: https://github.com/csg-engops-product-docs/en-us-ibi-wf-reporting-server-userdocs/blob/wip/en-us/ibi-webfocus-reporting-server/online-help/9-3-3/gathering-diagnostic-information-customer-support/create-savediag-from-webfocus-reporting-server.md",,Content,Critical,"ibi WebFOCUS Reporting Server 9.3.0, 9.3.2, 9.3.3, 9.3.4, 9.3.6 (about 400 pages each); ibi WebFOCUS Client 9.3.0, 9.3.1, 9.3.8 (1 page)",Mayur,New,,https://stg-docs.ibi.com/us/en/ibi-webfocus-reporting-server/online-help/9-3-3/gathering-diagnostic-information-customer-support/create-savediag-from-webfocus-reporting-server.html,,"DOCOPS-344; verify Wed 18 Nov 15:00-Thu 19 Nov 06:05 IST; add to the existing empty-article row",
Desktop,"Question: stg-docs.ibi.com answered 'HTTP 429 Too Many Requests' (and dropped some connections) to our page checker from about 19:30 IST on Wed 18 Nov to 05:52 IST on Thu 19 Nov; about 2,000 requests were refused. Runs earlier on 18 Nov at the same rate had none. Was a rate limit switched on, and what request rate is allowed? We will re-run the affected versions within it. Staging URL: https://stg-docs.ibi.com/us/en/ibi-webfocus-reporting-server/online-help/9-3-5/ibi-webfocus-reporting-server.html",,Content,Low,"stg-docs.ibi.com (verify runs of Reporting Server 9.3.5, 9.3.6, 9.3.8, iWay Service Manager 9.3.0, Container Edition 9.3.8, Data Quality 5.2.2)",Mayur,New,,https://stg-docs.ibi.com/us/en/ibi-webfocus-reporting-server/online-help/9-3-5/ibi-webfocus-reporting-server.html,,"question, no Jira key yet",
```

---

## 7. Open questions

1. **Re-run the 10 throttled versions, the 10 Container Edition lines with no result, and the 68 lines not started?**
   - **How:** during the day, with 1–2 slots, after clearing the cached 429 answers (or with `--refresh`). Ideally do it after the checker learns to retry (A11).
2. **When does `content-fix` reach `wip`?** Letter case, R002 and the cut-off page (A1–A3) wait on it. It is a `wip` push, so it needs your go-ahead: fetch and compare first, and note the `wip` freeze for ibi from 16 Nov.
3. **Rebuild the four 9.3.8 redirect maps now** (App Studio, Client, Reporting Server, DSML Services), in one `content-fix` commit?
4. **The DSML Services 9.3.8 draft page:** remove it from Unfiled?
5. **The checker fix for 429:** its own Jira key, or a note on DOCOPS-366?
