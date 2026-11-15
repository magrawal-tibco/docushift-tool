# Verify triage: Batch 2b (TRA, BusinessWorks, BPM, Data Management, re-checks), 2026-11-15

This is a read-only triage: no repo file was edited, nothing was run, logged or pushed. The data is each version's latest run in `cache/state.db` for the 24 lines of `cache/overnight/batch2b.txt`. The runs are 2239–2403, made Sat 14 Nov 19:32 to Sun 15 Nov 14:18 IST, all with `--refresh`. The current `config/verify-triage.yaml` was applied the way `verify --retriage` applies it (`triage.decide`, `issues.tally`), in memory. The evidence comes from:
- the Markdown in `C:/github/tibco-docs-aem` (local `content-fix` and `origin/wip`);
- the extracted packages under `families/`;
- the staging pages these runs cached in `cache/verify/`. No new staging fetch was made.

Verdicts reuse yesterday's reports (`triage-batch2-links-media-2026-11-14.md`, `triage-batch2-pages-text-2026-11-14.md`) where the kind is the same.

**Where the batch stands now:** 12 versions `lost`, 1 `issues`, 5 `logged`, 6 `clean` (local-only stubs). That is 801 unlogged errors and warnings.

**With the entries in section 3 (simulated):**
- **8 versions go `lost` → `logged`:** Administrator 5.13.0, TRA 5.13.0, FormBuilder 5.3.2, AMX Service Grid 3.4.4, BPM Enterprise 5.7.0, Business Studio BPM 5.7.0, MDM GDS 4.0.0, Foresight Transaction Insight 6.0.0.
- **4 go `lost` → `issues`:**
  - BusinessWorks 6.13.0, MDM 11.1.0 and MDM Studio 6.1.1 keep only the "nested under the guide page" moves (the open question from 14 Nov);
  - ActiveMatrix BPM 4.3.0 keeps only 2 `TOC_ORDER` warnings.
- **With the optional block 3c as well:** MDM 11.1.0 and MDM Studio 6.1.1 also go to `logged` (10 in all). BusinessWorks 6.13.0 stays `issues` on 1 `TOC_ORDER` warning.
- **No version reads `explained`:** each has at least one logged finding (DOCOPS-348 text, DOCOPS-345 anchors).
- The batch would then read 0 `lost`, 5 `issues`, 13 `logged`, 6 `clean`; or 3 / 15 / 6 with 3c.
- 801 unlogged findings drop to 54 (50 menu moves, 4 `TOC_ORDER`), or 4 with 3c.
- Every proposed entry matches at least one finding.

**Three things to know first:**
1. **Foresight and General have not rebuilt from Friday's push.** Both repos went to `wip` on Fri 13 Nov 11:21 (R1 group 3), and on Sun 14:00 staging still shows the older content:
   - **Enterprise Administrator 2.4.3:** "Last published Nov 01" and 33 unlabelled notes. The `wip` Markdown has the labels.
   - **Transaction Insight 6.0.0:** the notes are still unlabelled, its 757 picture findings are unchanged from 13 Nov (the 14 Oct names, Batch 2 P5), and only the 13 Nov test page is new.

   FTL, pushed in the same minute, did rebuild: 88 → 0 unlabelled notes. So these two results are stale, and the existing R001 entry already excuses their notes.
2. **Staging serves Transaction Insight pages at their menu path, not their folder path.** The page is served at `6-0-0/common-administration/administrator-pages/alerts.html`, but its folder path, `6-0-0/tibco-foresight-transaction-insight/common-administration/...`, answers 404.
   - 9 of the 10 sampled redirect targets fail, so TI went from `logged` to `lost`.
   - 13 Nov's "none of 10 sampled targets is served, the layout has not reached staging" was this same rule, not a timing problem.
   - If AEM does not turn 301 rows written as Markdown paths into served URLs, the redirects and cross-links of every such version break.
3. **There is little new real loss on our side, and two small converter gaps:**
   - **DITA table descriptions are dropped** (AMX BPM, 2 pages, 10 sentences, including a 4-item "Note that" list). This is new, NEW-T.
   - **Placeholders in angle brackets written unescaped inside bold** (`**... <launched> BWEclipseAppNode ...**`) show as nothing. That is 11 findings in 4 versions. It belongs under DOCOPS-360, but **R002 does not fix it**, because R002 rewrites `\<` only.

   The rest is known:
   - 11 more empty-article pages (DOCOPS-344);
   - pages after heading rows (DOCOPS-351);
   - FormBuilder 5.3.2 is served with **no pictures at all** (143, DOCOPS-347);
   - checker misreadings, mainly MDM Studio's two builds and example code read as pictures (DOCOPS-366).

---

## 1. Summary table

| # | Kind (plain words) | Codes | Versions / findings | Verdict | Jira | Owner |
|---|---|---|---|---|---|---|
| S1 | **Repo not rebuilt from the 13 Nov push** (General: EA 2.4.3, "Last published Nov 01"; Foresight: TI 6.0.0 old notes and unchanged pictures; the 13 Nov test page is new) | `PUBLISHED_CALLOUT_UNRENDERED` (already excused), stale `IMAGE_BROKEN` | 2 / 58 notes + TI pictures | **not rebuilt** | DOCOPS-338 note; UAT row | Digital Platform |
| S2 | **Pages served at their menu path, not their folder path** (TI 6.0.0); sampled 301 targets by folder path 404 | `REDIRECT_UNSERVED` | 1 / 9 | platform (URL rule); open question 2 | DOCOPS-351 | Digital Platform |
| P1 | **Page served with an empty article** (0% of its text): BW 6.13.0 OpenTelemetry Traces, Scope ×2, HTTP Client, Maven shared module ×2; AMX BPM 4.3.0 WCC pages ×4, Configuring Business Data | `PUBLISHED_ANCHOR_MISSING` 75, `PUBLISHED_IMAGE_BROKEN` 41 (from the 347 catch-all) | 2 / 116 (11 pages) | existing issue, platform | DOCOPS-344 | Digital Platform |
| P2 | **Pages after (or titled like) a heading row**: dropped or moved in the menu, own path 404 | `PUBLISHED_TOC_ENTRY_MISSING` 26, `PUBLISHED_ANCHOR_MISSING` 11 | 3 / 37 | existing issue | DOCOPS-351 | Digital Platform |
| P3 | **Pictures not served** (already logged by the catch-all): page-relative `src` (BW, BPM Ent, AMX BPM); `placeholder.png` for names with spaces (GDS 83, MDM 29); SVG bytes (FTL 70, AMX BPM 7); `.wmf` (TRA 1, iProcess 45); dot folders (TI 391). **New variant: FormBuilder 5.3.2 serves no `<img>` at all** on its dotted WebWorks pages (143) | `PUBLISHED_IMAGE_BROKEN` | 14 / 1,156 (after 41 move to DOCOPS-344) | existing issue (FormBuilder: UAT row) | DOCOPS-347 | Digital Platform |
| M1 | Support/legal copies and DITA's Important Information kept once, at the end | `TOC_ENTRY_MISSING` | 5 / 12 | accepted (design) | none | none |
| M2 | A topic listed under two parents (or a merged section paired with the other parent) | `TOC_MOVED` | 8 / 214 | accepted (crosswise) | none | none |
| M3 | DITA "Important Information" pages moved; verify's tail rule does not know them | `TOC_MOVED` | 1 / 30 | checker false positive | DOCOPS-366 | TechDocs |
| M4 | A guide's chapters at the top of the old menu, nested under the guide page in `toc.yml` | `TOC_MOVED` | 3 / 50 | accepted? (14 Nov open question 2; block 3c) | none | none |
| M5 | Staging shows a page listed twice only once; MDM's Custom Guide page listed under itself | `PUBLISHED_TOC_MOVED` 74, `PUBLISHED_TOC_ENTRY_MISSING` 7 | 5 / 81 | accepted | none | none |
| M6 | Menu order under one parent | `TOC_ORDER` | 3 / 4 | not triaged (warnings; as 14 Nov) | none | TechDocs, later |
| R1 | **No 301 rows for the old `relnotes/` folder** (BW 6.13.0 release notes) | `REDIRECT_UNMAPPED` | 1 / 44 | existing issue (second old folder, as BC 7.5.0) | DOCOPS-322 | TechDocs |
| T1 | **`<placeholder>` unescaped inside bold**: `<launched>`, `<Application Name>`, `<version_number>`, `<version>`, `<project >`, plus one `&apos;` | `TEXT_DROPPED` | 4 / 12 | existing issue; **R002 does not cover it** | DOCOPS-360 | TechDocs |
| T2 | Content directly inside a list (`<ul>` in `<ul>`: the 40-row license-error list) | `TEXT_DROPPED` | 1 / 2 | pending fix (re-converted 15 Nov, not synced) | DOCOPS-370 | TechDocs |
| T3 | **DITA table description dropped** (`<span class="tabledesc">` inside `<table>`) | `TEXT_DROPPED` | 1 / 2 (10 sentences) | **ours, new** | **NEW-T** | TechDocs |
| T4 | Checker: MDM Studio has two builds (`html/`, `relnotes/`) and verify compares with the one we did not publish; example code read as a picture (`path/?.gif`, `<![CDATA[`, a form template, `%%Skin`); `\-` in a raw `<pre>` | `IMAGE_MISSING` 189, `TEXT_DROPPED` 9 | 4 / 198 | checker false positive | DOCOPS-366 | TechDocs |
| T5 | "The default value is 0." split over two lines in a raw table | `TEXT_DROPPED` | 2 / 2 | accepted (as BE) | none | none |
| T6 | The overflow icon in a menu cascade is dropped ("click > Open Next") | `IMAGE_MISSING` | 1 / 4 | ours | DOCOPS-370 (picture variant) | TechDocs |
| A1 | Staging's heading-id rule: `®` kept in the id; raw ids starting with `/` dropped; a WebWorks heading holding only `<a id="30096">` | `PUBLISHED_ANCHOR_MISSING` | 3 / 10 | existing issue, platform | DOCOPS-345 | Digital Platform |
| A2 | Heading with code: the code part written as dashes or dropped | `PUBLISHED_ANCHOR_MISSING` | 2 / 5 | pending fix (built 12 Nov) | DOCOPS-362 | TechDocs |
| A3 | DITA section/step ids not kept (`#SECTION_…`, `#STEP_…`) | `PUBLISHED_ANCHOR_MISSING` | 1 / 2 | existing issue | DOCOPS-363 | TechDocs |
| A4 | Source: bookmark not defined (Administrator); the old menu names archive topics the package does not ship (Service Grid 5, MDM 2) | `PUBLISHED_ANCHOR_MISSING` 1, `TOPIC_MISSING` 7 | 3 / 8 | source | none | none |
| C1 | R001 left `> [!NOTE]` indented in a list (staging rebuilt BPM, so it is real) | `PUBLISHED_CALLOUT_UNRENDERED` | 2 / 2 | ours (now excused as fixed, wrongly) | DOCOPS-313 | TechDocs |

**Re-checks:**
- **Notes now labelled:** Cloud API Modeler 1.5.0 (8 → 0), eFTL 7.3.0 (8 → 0), FTL 7.3.0 (88 → 0).
- **FTL 7.3.0 pictures:** 89 → 70, and every one left is an SVG served with other bytes.
- **FTL 7.3.0 anchors:** 24 for headings with an escaped `<` (DOCOPS-353) and 3 source, all logged.
- **Scribe Online:** its 2 `TEXT_DROPPED` are gone.
- **iProcess Workspace (Windows) 11.10.0:** unchanged (`issues`, 1 `TOC_ORDER`).
- **EA 2.4.3 and TI 6.0.0:** S1 above.

**DOCOPS-371 (not a triage change):**
- 313 of ActiveMatrix BPM 4.3.0's 421 served-text pages contain `<samp>`/`<var>`.
- So the DOCOPS-348 catch-all on that version is mostly DOCOPS-371.

---

## 2. Evidence

Repos are `C:/github/tibco-docs-aem/<repo>/en-us/<slug>/online-help/<version>/`. Staging URLs start `https://stg-docs.tibco.com/us/en/`. Cached pages are from the batch's own runs.

**S1, not rebuilt.**
- **EA 2.4.3, `installation/installation-overview.md`.**
  - `origin/wip` has 5 `> **Note:**` (R001 `f42256c`, pushed with `1bbe4b6` on Fri 13 Nov 11:20).
  - The cached staging page (15 Nov 14:08) reads "Last published: Nov 01, 2026" and carries 5 `data-attr-keyref="!NOTE"`.
- **TI 6.0.0, `275-and-277-transactions/appendix-c-...`.**
  - `wip` has `> **Note:**` (R001 `89203dd`, pushed 13 Nov 11:21).
  - Staging (15 Nov 13:53) still has `<a class="xref" data-attr-keyref="!NOTE">`.
- **The 13 Nov test page is new.**
  - `installation-guide/general-configuration-after-installation` (`53c7ee8`, the tip of the 14:19 push) shows `Systems\ArchiverDemo` with a single backslash.
  - So that one page rebuilt, and the rest of the version did not.
- **FTL, for comparison.** FTL was pushed in the same minute (`d021831`, with its R001 `962c098` inside the push) and shows its labels.

**S2, menu path vs folder path (TI 6.0.0).**
- **`toc.yml`:** the top row "Archive and Retrieval System Administration Guide" (`archive-and-retrieval-system-administration-guide.md`) holds `tibco-foresight-archive-and-retrieval-system/archive-and-retrieval-system-systems-guide/introduction.md`.
- **Staging's menu** links `6-0-0/archive-and-retrieval-system-administration-guide/archive-and-retrieval-system-systems-guide/introduction.html` (the menu path), and also `6-0-0/common-administration/administrator-pages/alerts.html`.
- **Folder paths answer 404:** `6-0-0/tibco-foresight-transaction-insight/common-administration/administrator-pages/alerts.html` and 8 more, cached 15 Nov 13:53.
- **The content check paired the pages through the menu**, so it found them.
- **FormBuilder 5.3.2 follows the same rule:** `tib_bwformbuilder_guide/install.06.8.md` is served at `user-s-guide/install-06-1/install-06-8.html`.

**P1, empty article.**
- BW 6.13.0 `tibco-activematrix-businessworks/bindings-and-palettes-reference/basic-activities-palette/scope.md` has 2,135 words in Markdown; staging's article holds 0 words, with 12 anchors and its pictures missing. The same holds for its BWCE copy `scope-2.md`.
- AMX BPM 4.3.0 `.../workspace-configuration-and-customization-guide/introduction/launching-a-wcc-application.md` also serves 0 words.
- Pages of the same versions with similar length (`creating-an-application-module.md`, 2,300 words) are served whole.

**P2, after a heading row.**
- AMX BPM 4.3.0 "HTTP Connector": `.../properties-resource-templates/http-connector...md` follows the heading row `hibernate.md#http-client`.
- Its sibling `ldap-connection.md` is 404 at its own path, so `#smtp`, `#teneo` and `#thread-pool` were looked for on a 404.
- Service Grid 3.4.4 `jms-resource-templates.md` is 404 the same way.
- MDM Studio "Classification Functions" follows `context-variables.md#tips`.

**P3 variant, FormBuilder 5.3.2.**
- `tib_bwformbuilder_guide/install.06.8.md` has `![](images/select_domain.gif)`, and the file is in the repo.
- The served page `.../5-3-2/user-s-guide/install-06-1/install-06-8.html` (1,165 words, served) has no `<img>` in its article: not a broken `src`, no picture at all.
- All 143 FormBuilder pictures are affected. The version is WebWorks, with page names holding dots, and was published 21 Oct without reframe.

**R1.**
- The 44 unmapped URLs are all `https://docs.tibco.com/pub/activematrix_businessworks/6.13.0/relnotes/bw-ent-relnotes/*.htm`, for example `bwce-ci-binding.htm`.
- `.../6-13-0/301.yml` has 2,269 rows, none of them for `relnotes/`.

**T1, `<placeholder>` in bold.**
- **BW 6.13.0 `getting-started/rest-service-tutorial.md`:** "6. In the **Debug** view, expand **BWApplication [BusinessWorks Application] > <launched> BWEclipseAppNode > ...**". `<launched>` is read as an HTML tag, so "launched" is lost.
- **MDM GDS 4.0.0 `configure-tibco-businessconnect-tibco.md`:** "**Programs - > TIBCO - > TIBCO Runtime Agent & Adapter SDK <version> - > Domain Utility.**"
- **Business Studio BPM 5.7.0 `localization-of-forms.md`:** "**/<project > /Presentation Resources**".
- **Not R002's case:** none of these is `\<`, so R002 leaves them as they are.

**T3, table description (NEW-T).**
- **AMX BPM 4.3.0 source `bpmhelp/GUID-192A5D46-….html`:**
  - The source is `<table …><span class="tabledesc"><p>Note that:</p><ul><li>If the attribute specified is "*", all attributes … </li>… (4 items)</ul><p>The following attributes can be used to query process templates.</p></span><thead>…`.
  - `sorting-filtering-lists-process-templates.md` "Query Parameter Attributes" goes straight from "All attributes can be used for both filtering and sorting." to the table.
- **AMX BPM 4.3.0 source `soahelp/GUID-2D20662F-….html`:** "Consider the following set of mappings:" sits in the same place, and `url-mappings.md` lacks it.
- **Spread:** 19 source topics in `bpmhelp/` and `soahelp/` carry a `tabledesc`. They were not counted across other DITA packages.

**T4, checker.**
- **MDM Studio 6.1.1, two builds.**
  - **Two copies:** the package has `html/` (917 topics) and `relnotes/` (931). Both are live on the old site (`301.yml` has 910 `/doc/html/` and 915 `/doc/relnotes/` rows) and both map to one page.
  - **The page:** `repository-designer-tutorial.md` line 243 shows `GroupConnectorIcon_108x21.gif`, which is the `html/` build's icon. The `relnotes/` build uses `GroupConnectorIcon_116x22.gif`.
  - **The 11 "missing" report screenshots** on `repository-model-report.md` are on lines 66–146. They match the `html/` copy byte for byte; the `relnotes/` copies differ.
  - **The wording also differs.** `html/` reads "editing the Name field in the **General** tab", which is what we publish; `relnotes/` reads "editing the Name in the General tab".
  - **One example exists only in `relnotes/`:** the `<constraint>` "Set Language" XML (`relnotes/.../SESSION.htm`). The `html/` copy we publish does not have it.
- **AMX BPM 4.3.0 `application-log-methods.md` line 687:** `` `<img src='path/?.gif'><span …>Caption String</span>` `` is inline code (38 findings).
- **`resumeprocessinstances.md` line 639:** `&lt;![CDATA[` is read as the start of a Markdown image (22 findings).
- **MDM 11.1.0 `how-forms-work.md` line 234:** `<IMG alt="Submit" … src="images/submit_btn.gif" />` sits inside a form template code sample.

**A1.**
- **`®` kept in the id.** BW 6.13.0 `using-the-bwdesign-utility-2/messaging.md` has `## Integrating with TIBCO FTL<sup>®</sup>`. Staging writes `id="integrating-with-tibco-ftl®"`, and our link is `#integrating-with-tibco-ftl`. AMX BPM "Editing TIBCO Hawk® Rulebase Files" is the same case.
- **Ids starting with `/` dropped.** BW 6.13.0 `smart-engine/.../triggers.md` has `<a id="/monitor2"></a>` and others. None is on the served page, while Administrator's `<a id="admin_server_…">` anchors are served.

**A4.**
- **Administrator 5.13.0.** The source `server-configuration/Multiple_Load_Balanced_Servers_in_a_Subnet.htm` links `#admin_server_1931582264_2109256`, which no page defines.
- **Service Grid 3.4.4.** `deleting-the-archive.htm` and the 4 other archive topics are not in `families/en-us-tib-bpm/extracted/tibco-activematrix-service-grid/3.4.4/`. Only `exporting-from-gui.htm` and the Flare TOC chunk name them.

**C1.**
- **The leftover notes:** AMX BPM 4.3.0 `tasks/mappings-tab.md` line 265 and Service Grid 3.4.4 `host-manager/patch-commands.md` line 148 are both `  > [!NOTE]`, indented in a list.
- **Staging serves them unlabelled:** "Last published Nov 14", `keyref="!NOTE"`.

---

## 3. Proposed `config/verify-triage.yaml` entries

`DOCOPS-NEW-T` is a placeholder for the new sub-task's key. Placement:
- **3a** goes **directly below** the existing Product and Service Catalog 5.1.0 DOCOPS-313 line (it uses `*r001miss`), above the `VERIFY_PUBLISHED_CALLOUT_UNRENDERED` / DOCOPS-250 entry. Below that entry, the two findings would keep reading "fixed".
- **3b** goes **directly above** `# Catch-alls: keep last`, after the EMS `#Using` source entry. It uses anchors defined earlier: `*tailcopy`, `*crosswise`, `*shownonce`, `*listblock`, `*literalentity`, `*no-bookmark`, `*empty-article`.
- **3c (optional)** goes directly after 3b.

### 3a. R001 misses

```yaml
  - {code: VERIFY_PUBLISHED_CALLOUT_UNRENDERED, decision: logged, ticket: DOCOPS-313, slug: tibco-activematrix-bpm, version: "4.3.0", path: "*/tasks/mappings-tab.md", reason: *r001miss}
  - {code: VERIFY_PUBLISHED_CALLOUT_UNRENDERED, decision: logged, ticket: DOCOPS-313, slug: tibco-activematrix-service-grid, version: "3.4.4", path: "*/host-manager/patch-commands.md", reason: *r001miss}
```

### 3b. Batch 2b entries (and the generated DOCOPS-344 page list at the end)

```yaml
  # Batch 2b (14-15 Nov: TRA, BusinessWorks, BPM, Data Management, re-checks; triage
  # 2026-11-15, reports/verify/triage-batch2b-2026-11-15.md). Narrow entries: keep them
  # after the generated DOCOPS-344 page list and before the catch-alls.
  # DOCOPS-NEW-T is a placeholder for the new sub-task's key.

  # Support and legal copies (and DITA's Important Information) kept once, at the end.
  - {code: VERIFY_TOC_ENTRY_MISSING, decision: accepted, slug: tibco-runtime-agent, version: "5.13.0", path: "*/tibco-documentation-and-support-services.md", reason: *tailcopy}
  - {code: VERIFY_TOC_ENTRY_MISSING, decision: accepted, slug: tibco-runtime-agent, version: "5.13.0", path: "*/legal-and-third-party-notices.md", reason: *tailcopy}
  - {code: VERIFY_TOC_ENTRY_MISSING, decision: accepted, slug: tibco-activematrix-businessworks, version: "6.13.0", path: "tibco-businessworks-container-edition/tibco-documentation-and-support-services.md", reason: *tailcopy}
  - {code: VERIFY_TOC_ENTRY_MISSING, decision: accepted, slug: tibco-activematrix-businessworks, version: "6.13.0", path: "tibco-businessworks-container-edition/legal-and-third-party-notices.md", reason: *tailcopy}
  - {code: VERIFY_TOC_ENTRY_MISSING, decision: accepted, slug: tibco-activematrix-bpm, version: "4.3.0", path: "tutorials/tibco-documentation-and-support-services.md", reason: *tailcopy}
  - {code: VERIFY_TOC_ENTRY_MISSING, decision: accepted, slug: tibco-activematrix-bpm, version: "4.3.0", path: "tutorials/important-information.md", reason: *tailcopy}
  - {code: VERIFY_TOC_ENTRY_MISSING, decision: accepted, slug: tibco-mdm, version: "11.1.0", path: "*/tibco-documentation-and-support-services.md", reason: *tailcopy}
  - {code: VERIFY_TOC_ENTRY_MISSING, decision: accepted, slug: tibco-mdm, version: "11.1.0", path: "*/legal-and-third-party-notices.md", reason: *tailcopy}
  - {code: VERIFY_TOC_ENTRY_MISSING, decision: accepted, slug: tibco-mdm-studio, version: "6.1.1", path: "tibco-mdm-studio-2/tibco-documentation-and-support-services.md", reason: *tailcopy}
  - {code: VERIFY_TOC_ENTRY_MISSING, decision: accepted, slug: tibco-mdm-studio, version: "6.1.1", path: "tibco-mdm-studio-2/legal-and-third-party-notices.md", reason: *tailcopy}
  - code: VERIFY_TOC_MOVED
    decision: logged
    ticket: DOCOPS-366
    slug: tibco-activematrix-bpm
    version: "4.3.0"
    path: "*important-information.md*"
    reason: >-
      DITA's "Important Information" pages (one per guide) sit where the converter puts them;
      verify's tail rule does not know them (as for the BW plug-ins). Not a content change.

  # Topics listed under two parents, or a merged page's section paired with the other
  # parent. Every page is in the menu. Not a content change.
  - {code: VERIFY_TOC_MOVED, decision: accepted, slug: tibco-activematrix-businessworks, version: "6.13.0", path: "*/*/*", reason: *crosswise}
  - {code: VERIFY_TOC_MOVED, decision: accepted, slug: tibco-mdm, version: "11.1.0", path: "*/*/*", reason: *crosswise}
  - {code: VERIFY_TOC_MOVED, decision: accepted, slug: tibco-mdm-studio, version: "6.1.1", path: "*/*/*", reason: *crosswise}
  - {code: VERIFY_TOC_MOVED, decision: accepted, slug: tibco-activematrix-bpm, version: "4.3.0", reason: *crosswise}
  - {code: VERIFY_TOC_MOVED, decision: accepted, slug: tibco-activematrix-service-grid, version: "3.4.4", reason: *crosswise}
  - {code: VERIFY_TOC_MOVED, decision: accepted, slug: tibco-bpm-enterprise, version: "5.7.0", reason: *crosswise}
  - {code: VERIFY_TOC_MOVED, decision: accepted, slug: tibco-business-studio-bpm-edition, version: "5.7.0", reason: *crosswise}
  - {code: VERIFY_TOC_MOVED, decision: accepted, slug: ibi-mdm-add-on-for-global-data-synchronization, version: "4.0.0", path: global-data-synchronization-network-overview.md, reason: *crosswise}
  - {code: VERIFY_PUBLISHED_TOC_MOVED, decision: accepted, slug: tibco-activematrix-businessworks, version: "6.13.0", reason: *shownonce}
  - {code: VERIFY_PUBLISHED_TOC_MOVED, decision: accepted, slug: tibco-activematrix-bpm, version: "4.3.0", reason: *shownonce}
  - {code: VERIFY_PUBLISHED_TOC_MOVED, decision: accepted, slug: tibco-activematrix-service-grid, version: "3.4.4", reason: *shownonce}
  - {code: VERIFY_PUBLISHED_TOC_MOVED, decision: accepted, slug: tibco-business-studio-bpm-edition, version: "5.7.0", reason: *shownonce}
  - code: VERIFY_PUBLISHED_TOC_ENTRY_MISSING
    decision: accepted
    slug: tibco-mdm
    version: "11.1.0"
    path: "Custom Guide Specific to your Installation Requirements > Custom Guide Specific to your Installation Requirements > *"
    reason: &selfchild >-
      toc.yml lists the Custom Guide page under itself (rows 1 and 2, same url); staging
      shows it once, so its 7 environments sit one level up. Every page is reached.
  - {code: VERIFY_PUBLISHED_TOC_MOVED, decision: accepted, slug: tibco-mdm, version: "11.1.0", path: "Custom Guide Specific to your Installation Requirements > *", reason: *selfchild}

  # DOCOPS-351: pages after (or titled like) a heading row; staging drops or moves them,
  # their own path is 404, so their headings are looked for on the wrong page.
  - code: VERIFY_PUBLISHED_TOC_ENTRY_MISSING
    decision: logged
    ticket: DOCOPS-351
    slug: tibco-activematrix-bpm
    version: "4.3.0"
    reason: &afterheading >-
      The page follows heading rows (page.md#anchor) in toc.yml, or shares its title with one
      (HTTP Connector after hibernate.md#http-client); staging drops or moves it, and its own
      path is 404. Resource-template and SOAP-binding pages, SOA guides.
  - {code: VERIFY_PUBLISHED_TOC_ENTRY_MISSING, decision: logged, ticket: DOCOPS-351, slug: tibco-activematrix-service-grid, version: "3.4.4", reason: *afterheading}
  - {code: VERIFY_PUBLISHED_TOC_ENTRY_MISSING, decision: logged, ticket: DOCOPS-351, slug: tibco-mdm-studio, version: "6.1.1", path: "*Classification Functions", reason: *afterheading}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-351, slug: tibco-activematrix-bpm, version: "4.3.0", path: "*/properties-resource-templates/ldap-connection.md#*", reason: *afterheading}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-351, slug: tibco-activematrix-bpm, version: "4.3.0", path: "*/soap-bindings-2/ws-addressing-2.md#*", reason: *afterheading}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-351, slug: tibco-activematrix-bpm, version: "4.3.0", path: "*/managing-applications-2/soap-bindings-3.md#*", reason: *afterheading}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-351, slug: tibco-activematrix-service-grid, version: "3.4.4", path: "*/properties-of-resource-templates/jms-resource-templates.md#*", reason: *afterheading}

  # The old menu names files the package does not ship (linked from exporting-from-gui.htm
  # and the Flare TOC; NAV_NODE_DROPPED at conversion).
  - code: VERIFY_TOPIC_MISSING
    decision: source
    slug: tibco-activematrix-service-grid
    version: "3.4.4"
    path: "*/html/*/*archive*.htm"
    reason: &unshipped2b >-
      The old menu lists archive topics (deleting-the-archive, export-archive-direc,
      modifying-archive-st, distributed-application-archive-daa, enterprise-archive-ear-loader;
      MDM ProcessExportArchive, ProcessExportArchive30) that the package does not ship;
      broken on the old site too. Checked 2026-11-15.
  - {code: VERIFY_TOPIC_MISSING, decision: source, slug: tibco-mdm, version: "11.1.0", path: "*/html/Workflow-reference/ProcessExportArchive*.htm", reason: *unshipped2b}

  # Staging serves Transaction Insight pages at their menu path, not their folder path.
  - code: VERIFY_REDIRECT_UNSERVED
    decision: logged
    ticket: DOCOPS-351
    slug: tibco-foresight-transaction-insight
    version: "6.0.0"
    reason: >-
      Staging serves these pages at their menu path (6-0-0/common-administration/
      administrator-pages/alerts.html), not at their folder path (6-0-0/tibco-foresight-
      transaction-insight/common-administration/...), which verify asks for: 9 of 10 sampled
      301 targets 404 (13 Nov: 10 of 10, read then as "not on staging yet"). The pages are
      served. Open: does AEM resolve 301 rows written as Markdown paths?

  # The old site also serves the release notes under relnotes/; 301.yml has doc/html/ rows only.
  - code: VERIFY_REDIRECT_UNMAPPED
    decision: logged
    ticket: DOCOPS-322
    slug: tibco-activematrix-businessworks
    version: "6.13.0"
    reason: >-
      44 release-note topics live at /pub/activematrix_businessworks/6.13.0/relnotes/
      bw-ent-relnotes/; the 301.yml (2,269 rows) has none for relnotes/. The topics are
      published. A second old folder, as for BusinessConnect 7.5.0.

  # Text.
  - {code: VERIFY_TEXT_DROPPED, decision: logged, ticket: DOCOPS-370, slug: tibco-activematrix-businessworks, version: "6.13.0", path: "*/installation/installation-requirements*.md", reason: *listblock}
  - code: VERIFY_TEXT_DROPPED
    decision: logged
    ticket: DOCOPS-360
    slug: tibco-activematrix-businessworks
    version: "6.13.0"
    path: "*/getting-started/rest-*.md"
    reason: &rawangle >-
      A placeholder in angle brackets is written unescaped inside bold (**... <launched>
      BWEclipseAppNode ...**, <Application Name>, <version_number>, <version>, <project >);
      the browser reads it as a tag and shows nothing. R002 (`\<` only) does not cover it.
  - {code: VERIFY_TEXT_DROPPED, decision: logged, ticket: DOCOPS-360, slug: tibco-activematrix-businessworks, version: "6.13.0", path: "*/creating-a-rest-reference*.md", reason: *rawangle}
  - {code: VERIFY_TEXT_DROPPED, decision: logged, ticket: DOCOPS-360, slug: tibco-activematrix-businessworks, version: "6.13.0", path: "*/tibco-business-studio-for-businessworks*.md", reason: *rawangle}
  - {code: VERIFY_TEXT_DROPPED, decision: logged, ticket: DOCOPS-360, slug: tibco-business-studio-bpm-edition, version: "5.7.0", path: "*/tasks/localization-of-forms.md", reason: *rawangle}
  - {code: VERIFY_TEXT_DROPPED, decision: logged, ticket: DOCOPS-360, slug: ibi-mdm-add-on-for-global-data-synchronization, version: "4.0.0", path: "*/configure-tibco-businessconnect-tibco.md", reason: *rawangle}
  - {code: VERIFY_TEXT_DROPPED, decision: logged, ticket: DOCOPS-360, slug: tibco-mdm, version: "11.1.0", path: "*/configuration-tibco-businessconnect-tibco.md", reason: *rawangle}
  - {code: VERIFY_TEXT_DROPPED, decision: logged, ticket: DOCOPS-360, slug: tibco-activematrix-businessworks, version: "6.13.0", path: "*/closed-issues-of-tibco-activematrix-businessworks/palette.md", reason: *literalentity}
  - code: VERIFY_TEXT_DROPPED
    decision: logged
    ticket: DOCOPS-NEW-T
    slug: tibco-activematrix-bpm
    version: "4.3.0"
    path: "*/working-with-processes/sorting-filtering-lists-process-templates.md"
    reason: &tabledesc >-
      DITA writes a table's description (<span class="tabledesc">) inside <table>, before
      <thead>; the converter drops it: "Note that:" and its 4-item list (Query Parameter
      Attributes), "Consider the following set of mappings:" (URL Mappings).
  - {code: VERIFY_TEXT_DROPPED, decision: logged, ticket: DOCOPS-NEW-T, slug: tibco-activematrix-bpm, version: "4.3.0", path: "*/web-application-component-development/url-mappings.md", reason: *tabledesc}
  - code: VERIFY_TEXT_DROPPED
    decision: accepted
    slug: "tibco-*bpm*"
    path: "*/api-for-scripting/m*-for-*-class.md"
    reason: >-
      "The default value is 0." is present (raw HTML table, <samp>0.</samp> or <code>0.</code>
      on its own line); the check reads it in two parts. ActiveMatrix BPM 4.3.0, Business
      Studio BPM Edition 5.7.0.
  - code: VERIFY_TEXT_DROPPED
    decision: logged
    ticket: DOCOPS-366
    slug: tibco-activematrix-bpm
    version: "4.3.0"
    path: "*/business-object-model-mappings-to-xml-schema/data-type-mappings.md"
    reason: >-
      The XSD date patterns (\-\-\-(0[1-9]|...)) are in a raw <pre>, written as in the
      source; verify reads `\-` there as a Markdown escape. Checker.

  # MDM Studio 6.1.1 ships the help twice (html/ and relnotes/, both live on the old site,
  # slightly different); we publish html/, verify compares some pages with relnotes/.
  - code: VERIFY_IMAGE_MISSING
    decision: logged
    ticket: DOCOPS-366
    slug: tibco-mdm-studio
    version: "6.1.1"
    reason: &twobuilds >-
      The package holds two Flare builds of the help (html/ 917 topics, relnotes/ 931), both
      on the old site. The page is converted from html/; verify compares it with relnotes/,
      whose icons are other files (GroupConnectorIcon_116x22 vs _108x21) and whose wording
      differs in places. Every flagged picture is on the page, from html/.
  - {code: VERIFY_TEXT_DROPPED, decision: logged, ticket: DOCOPS-366, slug: tibco-mdm-studio, version: "6.1.1", reason: *twobuilds}

  # Pictures: example code read as pictures (checker); one icon dropped from a menu path.
  - code: VERIFY_IMAGE_MISSING
    decision: logged
    ticket: DOCOPS-366
    slug: tibco-activematrix-bpm
    version: "4.3.0"
    path: "*/application-class-methods/application-log-methods.md"
    reason: &imgincode >-
      The "picture" is example code: <img src='path/?.gif'> in inline code, an HTML form
      template (submit_btn.gif), Flare skin markup (%%Skin.FileUrl), or `<![CDATA[` read as
      the start of an image. Checker.
  - {code: VERIFY_IMAGE_MISSING, decision: logged, ticket: DOCOPS-366, slug: tibco-activematrix-bpm, version: "4.3.0", path: "*/processmanagerservice/resumeprocessinstances.md", reason: *imgincode}
  - {code: VERIFY_IMAGE_MISSING, decision: logged, ticket: DOCOPS-366, slug: tibco-mdm, version: "11.1.0", path: "*/workitem-forms-and-email-templates-customization/how-forms-work.md", reason: *imgincode}
  - {code: VERIFY_IMAGE_MISSING, decision: logged, ticket: DOCOPS-366, slug: tibco-businessworks-formbuilder, version: "5.3.2", path: "*/desktop.12.6.md", reason: *imgincode}
  - code: VERIFY_IMAGE_MISSING
    decision: logged
    ticket: DOCOPS-370
    slug: tibco-bpm-enterprise
    version: "5.7.0"
    path: "*/work-views/processing-work-items-overview.md"
    reason: >-
      The overflow icon (ellipsis_10x21.png) inside a menu cascade is dropped, so the step
      reads "click > Open Next". Unlike Kafka 6.8.2, the icon is the first menu step.

  # Anchors.
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: source, slug: tibco-administrator-enterprise-edition, version: "5.13.0", path: "*/fault-tolerance-load-balancing-rendezvous/overview.md#admin_server_1931582264_2109256", reason: *no-bookmark}
  - code: VERIFY_PUBLISHED_ANCHOR_MISSING
    decision: logged
    ticket: DOCOPS-345
    slug: tibco-activematrix-businessworks
    version: "6.13.0"
    path: "*/using-the-bwdesign-utility-2/messaging.md#integrating-with-tibco-ftl"
    reason: &regid >-
      Heading with a registered sign (TIBCO FTL<sup>®</sup>, TIBCO Hawk<sup>®</sup>): staging
      keeps the sign in the id (#integrating-with-tibco-ftl®); our links drop it.
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-345, slug: tibco-activematrix-bpm, version: "4.3.0", path: "*/reconfiguring-jdbc.md#editing-tibco-hawk-rulebase-files", reason: *regid}
  - code: VERIFY_PUBLISHED_ANCHOR_MISSING
    decision: logged
    ticket: DOCOPS-345
    slug: tibco-activematrix-businessworks
    version: "6.13.0"
    path: "*/generating-reports-for-engine-data/triggers.md#/*"
    reason: >-
      Raw anchors whose id starts with "/" (<a id="/monitor2">, REST paths) are not on the
      served page; staging drops them. Other raw <a id> anchors are served.
  - code: VERIFY_PUBLISHED_ANCHOR_MISSING
    decision: logged
    ticket: DOCOPS-345
    slug: tibco-businessworks-formbuilder
    version: "5.3.2"
    path: "*/preface.04.3.md#30096"
    reason: >-
      A WebWorks heading holding only a numeric anchor (## <a id="30096"></a>) is not on the
      served page. Not traced further.
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-362, slug: tibco-businessworks-formbuilder, version: "5.3.2", path: "*/custom_control.08.?.md#*", reason: &codeid "Link or menu row to a heading with code, the code part written as dashes or dropped (#example-for, #understanding-the-------------example, #installation-environment). Fix built 12 Nov; needs a re-convert."}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-362, slug: tibco-activematrix-bpm, version: "4.3.0", path: "*/case-data-model-versioning.md#*-----*", reason: *codeid}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-362, slug: tibco-activematrix-bpm, version: "4.3.0", path: "*/tibco-activematrix-bpm-installation-developer/important-information.md#*", reason: *codeid}
  - code: VERIFY_PUBLISHED_ANCHOR_MISSING
    decision: logged
    ticket: DOCOPS-363
    slug: tibco-activematrix-service-grid
    version: "3.4.4"
    path: "*#[SC][ET][CE][TP]*"
    reason: >-
      Link to a DITA section or step id (#SECTION_9059..., #STEP_XPP_NQW_2G) the converter
      did not keep. Same as BusinessEvents' #GUID-/#FIG_ links.

  # Served with an empty article (DOCOPS-344): 11 pages, served text 0% of the page.
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-activematrix-businessworks, version: "6.13.0", path: "tibco-activematrix-businessworks/administration/opentelemetry/traces.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-activematrix-businessworks, version: "6.13.0", path: "tibco-activematrix-businessworks/administration/opentelemetry/traces.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-activematrix-businessworks, version: "6.13.0", path: "tibco-activematrix-businessworks/bindings-and-palettes-reference/basic-activities-palette/scope.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-activematrix-businessworks, version: "6.13.0", path: "tibco-activematrix-businessworks/bindings-and-palettes-reference/basic-activities-palette/scope.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-activematrix-businessworks, version: "6.13.0", path: "tibco-activematrix-businessworks/bindings-and-palettes-reference/shared-resources/http-client.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-activematrix-businessworks, version: "6.13.0", path: "tibco-activematrix-businessworks/maven-plug-in/deploying-a-shared-module-on-remote-repository.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-activematrix-businessworks, version: "6.13.0", path: "tibco-activematrix-businessworks/maven-plug-in/deploying-a-shared-module-on-remote-repository.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-activematrix-businessworks, version: "6.13.0", path: "tibco-businessworks-container-edition/bindings-and-palettes-reference/basic-activities-palette-2/scope-2.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-activematrix-businessworks, version: "6.13.0", path: "tibco-businessworks-container-edition/bindings-and-palettes-reference/basic-activities-palette-2/scope-2.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-activematrix-businessworks, version: "6.13.0", path: "tibco-businessworks-container-edition/maven-plug-in/deploying-a-shared-module-on-remote-repository-2.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-activematrix-businessworks, version: "6.13.0", path: "tibco-businessworks-container-edition/maven-plug-in/deploying-a-shared-module-on-remote-repository-2.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-activematrix-bpm, version: "4.3.0", path: "bpm/workspace/workspace-components/using-wcc-components-mash-ups/using-tibco-pagebus-managed/managed-hub-sample.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-activematrix-bpm, version: "4.3.0", path: "bpm/workspace/workspace-components/using-wcc-components-mash-ups/using-tibco-pagebus-managed/managed-hub-sample.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-activematrix-bpm, version: "4.3.0", path: "bpm/workspace/workspace-configuration-and-customization-guide/introduction/configuring-customizing-non-deployed-application.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-activematrix-bpm, version: "4.3.0", path: "bpm/workspace/workspace-configuration-and-customization-guide/introduction/configuring-customizing-non-deployed-application.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-activematrix-bpm, version: "4.3.0", path: "bpm/workspace/workspace-configuration-and-customization-guide/introduction/launching-a-wcc-application.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-activematrix-bpm, version: "4.3.0", path: "bpm/workspace/workspace-configuration-and-customization-guide/localization/default-language.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-activematrix-bpm, version: "4.3.0", path: "bpm/workspace/workspace-configuration-and-customization-guide/localization/default-language.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-activematrix-bpm, version: "4.3.0", path: "installation/tibco-activematrix-bpm/installation-upgrade/performing-post-installation/configuring-business-data.md#*", reason: *empty-article}
```

### 3c. Optional: "nested under the guide page" (still the 14 Nov open question)

```yaml
  # Optional (Open question 2 of 14 Nov, still open): the old menu lists a guide's chapters
  # at the top; toc.yml nests them under the guide page, as reframe does. Paste after the
  # Batch 2b block; the deeper moves are matched first by the crosswise entries.
  - {code: VERIFY_TOC_MOVED, decision: accepted, slug: tibco-activematrix-businessworks, version: "6.13.0", reason: &nested2b "The old menu lists the guide's chapters at the top level; toc.yml nests them under the guide page, as reframe does. Every page is in the menu. Not a content change."}
  - {code: VERIFY_TOC_MOVED, decision: accepted, slug: tibco-mdm, version: "11.1.0", reason: *nested2b}
  - {code: VERIFY_TOC_MOVED, decision: accepted, slug: tibco-mdm-studio, version: "6.1.1", reason: *nested2b}
```

**No entry for:**
- **the 4 `TOC_ORDER` warnings:** as on 14 Nov;
- **the 58 stale notes (EA 2.4.3, TI 6.0.0):** the R001 entry already excuses them; re-check after the rebuild.

---

## 4. Jira changes

Reuse first. One new sub-task.

| Issue | Change | Points |
|---|---|---|
| **NEW-T** (sub-task under DOCOPS-96, TechDocs) | "DITA table description inside `<table>` is dropped" (`<span class="tabledesc">` before `<thead>`). Write it as a paragraph before the table; count the affected DITA versions; re-convert them. Found on AMX BPM 4.3.0 (Query Parameter Attributes, URL Mappings). | 0.5 |
| DOCOPS-360 | Note: a third case, **`<placeholder>` unescaped inside bold**, which R002 does not cover. BW 6.13.0 (8), Business Studio BPM 5.7.0, MDM GDS 4.0.0, MDM 11.1.0. Extend R002 (escape `<word>` that is not an HTML tag) and the converter. | +0.25 |
| DOCOPS-344 | Note: 11 more pages, 0% served. BW 6.13.0: OpenTelemetry Traces, Scope ×2, HTTP Client, Maven shared module ×2. AMX BPM 4.3.0: Managed Hub Sample, WCC launch, non-deployed application, Default Language, Configuring Business Data. | none |
| DOCOPS-351 | Note: (1) AMX BPM 4.3.0 (20), Service Grid 3.4.4 (5) and MDM Studio 6.1.1 (1): pages after heading rows, own path 404. (2) **The menu-path URL rule:** TI 6.0.0 pages are served at their menu path, so redirect targets and cross-links by folder path 404. Ask whether 301 rows written as Markdown paths are resolved. | none |
| DOCOPS-347 | Note: the FormBuilder 5.3.2 variant (dotted WebWorks pages, no `<img>` served, 143). This batch's counts: GDS 83 and MDM 29 placeholders for spaces; FTL 70 and AMX BPM 7 SVG bytes. | none |
| DOCOPS-345 | Note: `®` kept in ids (BW, AMX BPM); raw ids starting with `/` dropped (BW Smart Engine REST page); a WebWorks numeric-only heading (FormBuilder). | none |
| DOCOPS-366 | Note: 3 checker causes. (1) A package with two Flare builds (`html/` and `relnotes/`), where verify compares with the copy we did not publish (MDM Studio, 109). (2) `<img>` in code samples, and `<![CDATA[` read as an image (88). (3) `\-` in a raw `<pre>`. Plus DITA Important Information moves on AMX BPM (30). | +0.25 |
| DOCOPS-362 | Note: add FormBuilder 5.3.2 and AMX BPM 4.3.0 to the re-convert list. | none |
| DOCOPS-363 | Note: Service Grid 3.4.4, DITA `#SECTION_`/`#STEP_` ids. | none |
| DOCOPS-370 | Note: BW 6.13.0 installation requirements is on the 15 Nov re-convert list. A picture variant: BPM Enterprise 5.7.0's overflow icon in a menu cascade ("click > Open Next"). | none |
| DOCOPS-322 | Note: BW 6.13.0 has no 301 rows for the old `relnotes/` folder (44 topics), the same as BC 7.5.0's second folder. | none |
| DOCOPS-313 | Note: 2 more R001 misses (AMX BPM 4.3.0, Service Grid 3.4.4), both indented in a list. | none |
| DOCOPS-371 | Note: on AMX BPM 4.3.0, 313 of the 421 pages with served-text differences carry `<samp>`/`<var>`. | none |
| DOCOPS-338 (verify waves) | Note: Batch 2b is done. 12 lost go to 8 logged and 4 issues with these entries. EA 2.4.3 and TI 6.0.0 are stale (S1); re-check them after the General and Foresight rebuild. | none |

---

## 5. UAT-sheet rows (Digital Platform)

These are for kinds not yet in the sheet. DOCOPS-344 (empty article), DOCOPS-345 (ids), DOCOPS-346 and DOCOPS-371 are there already: add the new examples to their Comments.

```csv
Type,Issue description,Issue screenshot,Category,Priority,Found In,Reporter,Status,Assignee,Stage Issue link,Prod Issue link,Comments,DEV status / comment
Desktop,"Staging has not picked up the 13 Nov wip push of two repos: General (pushed Fri 13 Nov 11:20) and Foresight (11:21, plus one page at 14:19). On Sun 15 Nov the pages still show the older content: notes without their 'Note:' label (33 on Enterprise Administrator 2.4.3, 25 on Transaction Insight 6.0.0). Only the one Foresight page changed at 14:19 is new. FTL, pushed in the same minute, did rebuild. Example: Enterprise Administrator 2.4.3, Installation Overview, 'Last published: Nov 01'. GitHub: https://github.com/tibco/en-us-tib-general-userdocs/blob/wip/en-us/tibco-enterprise-administrator/online-help/2-4-3/installation/installation-overview.md",,Content,High,"TIBCO Enterprise Administrator 2.4.3 (General repo); TIBCO Foresight Transaction Insight 6.0.0 (Foresight repo)",Mayur,New,,https://stg-docs.tibco.com/us/en/tibco-enterprise-administrator/online-help/2-4-3/installation/installation-overview.html,,"DOCOPS-338; 2 repos; verify 15 Nov 13:53-14:08 IST",
Desktop,"A page is served at its menu path, not at its folder path, so a link or redirect written with the folder path is 404. Example: Transaction Insight 6.0.0, Alerts, served at .../6-0-0/common-administration/administrator-pages/alerts.html; its folder path .../6-0-0/tibco-foresight-transaction-insight/common-administration/administrator-pages/alerts.html is 404 (9 of 10 sampled pages). Our 301.yml rows, csh.yml and cross-links name the Markdown file path. Question: does AEM turn a Markdown path into the served URL for redirects and links? GitHub: https://github.com/tibco/en-us-tib-foresight-userdocs/blob/wip/en-us/tibco-foresight-transaction-insight/online-help/6-0-0/toc.yml",,Content,High,TIBCO Foresight Transaction Insight 6.0.0 (and FormBuilder 5.3.2),Mayur,New,,https://stg-docs.tibco.com/us/en/tibco-foresight-transaction-insight/online-help/6-0-0/tibco-foresight-transaction-insight/common-administration/administrator-pages/alerts.html,,"DOCOPS-351; affects redirects at go-live",
Desktop,"No pictures on the served pages of BusinessWorks FormBuilder 5.3.2: the article has no <img> at all, not even a broken one, although the Markdown has the picture and the file is in the repo. The page files have dots in their names (install.06.8.md) and are served at a menu path with hyphens (install-06-1/install-06-8.html). GitHub: https://github.com/tibco/en-us-tib-businessworks-userdocs/blob/wip/en-us/tibco-businessworks-formbuilder/online-help/5-3-2/tib_bwformbuilder_guide/install.06.8.md",,Content,High,TIBCO BusinessWorks FormBuilder 5.3.2,Mayur,New,,https://stg-docs.tibco.com/us/en/tibco-businessworks-formbuilder/online-help/5-3-2/user-s-guide/install-06-1/install-06-8.html,,"DOCOPS-347; 143 pictures, every page of the version",
```

---

## 6. Open questions

1. **General and Foresight rebuild (S1).** Ask Digital Platform why the 13 Nov push did not build? Or re-trigger the build with a small real change, as was done for Data Management on Sat? The second is a push, so it needs your approval.
2. **Menu-path URLs (S2).** Does AEM resolve 301 rows and links written as Markdown paths when a page is served at its menu path? If it does not, every version whose menu nests differently from its folders (TI 6.0.0, FormBuilder 5.3.2, likely more) loses its redirects and cross-links at go-live. The fix would then be on our side: write served URLs, or make folders follow the menu.
3. **R2 scope for the two small converter gaps:**
   - **`<placeholder>` in bold (DOCOPS-360):** about 0.25 SP, as an R002 extension. Without it, R2 ships these as blank text.
   - **DITA table descriptions (NEW-T):** 0.5 SP plus a DITA re-convert.

   Both before the R2 pushes (Mon–Wed), or after go-live?
