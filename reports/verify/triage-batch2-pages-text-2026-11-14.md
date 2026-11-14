# Verify triage: Batch 2 (TIBCO newest), pages, text and menus, 2026-11-14

This triage is read-only. Nothing was edited, logged or run. The data is Batch 2's findings in `cache/state.db` (runs 2131–2227, 13 Nov 18:57–23:03 IST), read with the current `config/verify-triage.yaml`. The evidence comes from `origin/wip` of the `tibco-docs-aem` repos (fetched 13 Nov 16:51), the unpacked packages under `families/`, and about 25 staging fetches made on 14 Nov.

**Scope.** This report covers page, text and menu kinds only. Redirects, images and anchors are in the parallel triage.

**What the batch found, in short:**
- **20 versions are not on staging at all.** They return 404, and so does their product page, although they have been on `wip` since 30 Oct or 5 Nov. It is not a timing problem, so they join DOCOPS-346.
- **ActiveSpaces 5.2.0 is served, but with an empty menu** (5.1.0 has the same problem).
- **One Hawk RedTail page returns HTTP 500.**
- **Staging drops `<samp>` and `<var>` elements, text included.** On the mainframe message pages, every message code is gone.
- **Real loss on our side:** the converter drops content that the source places directly inside a list, outside a list item. This affects 7 versions (8 pages).
- **Most of the rest is known:** fixes already built (DOCOPS-349, 360, 362), a deliberate design (support and legal copies), problems in the source, or `verify` misreading the page.
- **Not yet rebuilt:** 5 versions still had unlabelled notes at check time. The repo has the labels, and Cloud API Modeler showed them on 14 Nov.

**Simulated result.** The main YAML block below (block A, plus block B) was applied in memory to the stored Batch 2 findings. Nothing was written and no requests were made.
- **My kinds only:**
  - 36 versions leave `lost`: 33 become `logged` and 3 `explained`.
  - 2 move from `issues` to `logged`.
  - 11 drop from `lost` to `issues`. What keeps them there is the 246 "nested under the guide page" moves (Open question 2) and 6 `TOC_ORDER` warnings.
  - With the optional block C as well: 39 → `logged`, 3 → `explained`, and 3 more `issues` → `logged`.
- **All kinds, while the other triage's kinds are still open:** 24 versions go from `lost` to `logged` and 2 from `issues` to `logged`. Batch 2 then reads 49 `logged`, 26 `lost`, 7 `issues` and 2 `clean`, against 23 / 57 / 2 / 2 today.
- **Every proposed entry matches at least one finding.** Block B matches only once it sits above the existing callout entry (see section 3).

---

## 1. Summary table

| # | Kind (plain words) | Codes | Versions / findings | Verdict | Jira | Owner |
|---|---|---|---|---|---|---|
| P1 | **Help not on staging.** The version page, its first menu page and the product page are 404. The folder has been on `wip` and `main` since 30 Oct or 5 Nov. | `PUBLISHED_PAGE_MISSING` (version level) | 20 / 20 | existing issue | **DOCOPS-346** | Digital Platform |
| P2 | **Served with an empty menu.** ActiveSpaces 5.2.0 (and 5.1.0) pages are served ("Last published Oct 30"), but the menu list is empty. `toc.yml` is valid. | `PUBLISHED_PAGE_MISSING` | 1 / 1 | existing issue (variant) | **DOCOPS-346** | Digital Platform |
| P3 | **A page answers 500.** Hawk RedTail 7.5.0, Error Codes. A second page ("Structure") was not served at check time but is served now. | `PUBLISHED_PAGE_MISSING` | 1 / 2 | existing issue; 1 transient | **DOCOPS-344** | Digital Platform |
| P4 | **Published in the early shape.** Silver Fabric Enabler for ActiveSpaces 1.2.0 (30 Sep): `toc.yml` uses `items:`/`path:`, which AEM does not read, and every book is in it twice. | `PUBLISHED_PAGE_MISSING` 1, `TOC_ENTRY_MISSING` 32 | 1 / 33 | ours | **DOCOPS-365** (widen) | TechDocs |
| P5 | **Not published yet.** Platform 1.1.0 is a K3 addition. It is committed on local `content-fix` only, for R2. | `PUBLISHED_PAGE_MISSING` | 1 / 1 | not yet published | none (R2) | TechDocs |
| T1 | **`verify` misses Flare subproject copies.** The old menu names `html/Subsystems/<proj>/x.htm`. The converter published the master copy (`html/<folder>/x.htm` or its `_1` rename). All 387 entries resolve to a published menu page. | `TOPIC_MISSING` | 2 / 387 | checker false positive | **DOCOPS-366** | TechDocs |
| T2 | **Real pages dropped by name or folder.** Translator 4.2.0 `User/Default.htm` and Offer and Price Engine 6.0.0 `installation-configuration/index.htm` are covered by the built fix. ActiveSpaces 5.2.0 "About This Product" sits in `_globalpages/` and is not covered. | `TOPIC_MISSING` | 3 / 3 | pending fix (2), ours (1) | **DOCOPS-349** | TechDocs |
| T3 | **The old menu names files the package does not ship.** `process-archive-cp-190.htm` (Control Plane 1.20.0, Platform 1.1.0, Platform CLI 1.2.0), `managing-app-archives-apidocs-bw6.htm` (Platform 1.1.0), and 7 GUID-named Reward 22.3.0 files. | `TOPIC_MISSING` | 4 / 11 | source | none | none |
| X1 | **Content written directly inside a list is lost.** In these cases the source puts a list, table, code block or procedure title directly inside `<ul>`/`<ol>`, outside any `<li>`. The converter drops it, or runs the procedures together. | `TEXT_DROPPED` | 7 / 8 | **ours, new** | **NEW-L** | TechDocs |
| X2 | **`\<` placeholders**, and entity names the source shows as text (`&amp;apos;`). | `TEXT_DROPPED` | 6 / 6 | pending fix (R002); variant | **DOCOPS-360** | TechDocs |
| X3 | **Text is on the page; `verify` misreads it.** The text is split over lines, sits in `<samp>`, or sits inside a fence or in `<code>` with backticks. | `TEXT_DROPPED` | 7 / 7 | checker false positive | accepted (4), **DOCOPS-366** (3) | TechDocs |
| X4 | **Staging drops `<samp>` and `<var>` with their text.** On the Substation ES, CICS and IMS message pages the Code column is empty, and the page reads "The supported codes are,, and". | `PUBLISHED_TEXT_DIFF` | 3 versions (messages-and-codes pages); about 1,000 pages use `<samp>`/`<var>` across the repos | **platform, new** | **NEW-S** | Digital Platform |
| X5 | **The other served-text differences.** About a third are `<…>` placeholders (DOCOPS-360); most of the rest are long tables. | `PUBLISHED_TEXT_DIFF` | 54 / 777 | already `logged` | DOCOPS-348 | TechDocs (to trace) |
| M1 | **Second copies of the support and legal pages are left out of the menu.** One copy is kept at the end, by design (`navigation._tail`). | `TOC_ENTRY_MISSING` | 11 / 48 | accepted (design) | none | none |
| M2 | **Doubled heading knock-on.** The page repeats its title, so the old entry pairs with `#title-1`. | `TOC_ENTRY_MISSING` 7, `TOC_MOVED` 20 | 3 / 27 | existing issue | **DOCOPS-336** | TechDocs |
| M3 | **A heading target written with dashes** (Flogo VS Code 1.3.5, "if/else"). | `TOC_ENTRY_MISSING` | 1 / 1 | pending fix | **DOCOPS-362** | TechDocs |
| M4 | **A topic in two sister guides** (EE/CE, ebMS2/ebMS3, X12/HIPAA, user/installation). The check pairs the copies crosswise. | `TOC_MOVED` | 11 / 57 | accepted (crosswise) | none | none |
| M5 | **A guide's chapters listed at the top of the old menu.** `toc.yml` nests them under the guide page. | `TOC_MOVED` | 8 / 246 | accepted? (Open question 2) | none | none |
| M6 | **Menu order differs under one parent.** | `TOC_ORDER` | 6 / 6 | not triaged (warnings, nothing lost) | none | TechDocs, later |
| M7 | **Staging shows a page that is listed twice only once.** | `PUBLISHED_TOC_MOVED` | 3 / 4 | accepted (as for Scribe) | none | none |
| M8 | **Heading-row knock-on.** iProcess Workspace (Windows) 11.10.0: the page follows 4 heading rows. It is served and in the menu. | `PUBLISHED_TOC_ENTRY_MISSING` | 1 / 1 | existing issue | **DOCOPS-351** | Digital Platform |
| C1 | **Notes without a label at check time.** The Markdown has the labels (R001, 30 Oct). Staging had not rebuilt: Cloud API Modeler shows them on 14 Nov. | `PUBLISHED_CALLOUT_UNRENDERED` | 5 / 442 | not yet rebuilt (already `ours DOCOPS-250`) | DOCOPS-250 / 313 | none; re-check |
| C2 | **R001 missed a note in, or right after, a list.** These are still `> [!NOTE]` in the repo. | `PUBLISHED_CALLOUT_UNRENDERED` | 2 / 2 | ours | **DOCOPS-313** | TechDocs |

## 2. Evidence

Repo paths are under `C:/github/tibco-docs-aem/<repo>/` on `origin/wip`. Staging URLs start `https://stg-docs.tibco.com/us/en/`.

**P1, help not on staging.**
- **BusinessConnect Container Edition SOAP Protocol 1.3.0.** The following are all 404 on 14 Nov: `…/tibco-businessconnect-container-edition-soap-protocol/online-help/1-3-0/tibco-businessconnect-container-edition-soap.html`, `…/1-3-0/installation.html`, `…/1-3-0.html`, and the product page `…/tibco-businessconnect-container-edition-soap-protocol.html`. The repo folder `en-us-tib-businessconnect-userdocs/en-us/tibco-businessconnect-container-edition-soap-protocol/online-help/1-3-0/` (91 files, `toc.yml` ordinary) is the same on `wip` and `main`, last changed 5 Nov (`8df9178`, 301.yml only).
- **For comparison, BusinessConnect 7.5.0, in the same repo, is served** with a full menu ("Last published Nov 13"). Its product page answers 200.
- **More 404s:**
  - Adapter for JD Edwards 6.1.0 (`…/6-1-0/index.html` and the product page);
  - Adapter for Database 1.3.0;
  - Foresight Instream 9.4.0 and EDISIM 6.21.0;
  - Hawk Microagent for BWCE 2.2.0;
  - Messaging Schema Repository 2.1.0;
  - BusinessConnect EDI 6.11.0;
  - Product and Service Catalog powered by EBX 1.1.0.
- **The other 9** were not fetched one by one. `verify` found no menu at either entry URL.

**P2, ActiveSpaces 5.2.0.** `…/tibco-activespaces-enterprise-edition/online-help/5-2-0/tibco-activespaces-enterprise-edition.html` and `…/whats-new.html` answer 200 with full articles, but the "Online Help" list is empty. 5.1.0 behaves the same way. `toc.yml` loads as YAML (`docs_list_title`, `docs`; 733 lines).

**P3, Hawk RedTail 7.5.0.**
- **Error Codes.** `…/7-5-0/error-codes/error-codes.html` answered **HTTP 500** twice on 14 Nov. Its parent `…/7-5-0/error-codes.html` is served and links to it. The Markdown (`en-us-tib-hawk-userdocs/…/7-5-0/error-codes/error-codes.md`, 131 KB, raw HTML tables) is ordinary.
- **Structure.** `programmers-guide/hawk-console-api/structure.html` was not served at check time and is served now.

**P4, Silver Fabric 1.2.0.**
- `en-us-tib-activespaces-userdocs/en-us/tibco-silver-fabric-enabler-for-activespaces-enterprise-edition/online-help/1-2-0/toc.yml` starts `items:` / `- title: … path: "index.md"`. It is the only TIBCO online-help `toc.yml` on `wip` in that shape. The same shape appears only in its own reference, release and user-guide folders, and in 2 Streaming ModelOps folders.
- The folder has `Tib_sfas_Install_guide/`, `Tib_sfas_Users_guide/` and a byte-identical `html/` copy. Phase 34 drops that copy, but the version was published before Phase 34 (`c60fa9d`, 30 Sep). In the catalog it is `convert_eligible=false`, engine WebWorks.

**T1, Foresight Instream 9.4.0.**
- The old entry "APF File Format" is `html/Subsystems/APF/apf/APF_File_Format.htm`. `output_map` has `html/apf/APF_File_Format.htm`, published as `validation-profile-files-apf/apf-file-format.md`.
- Business Rules entries (`Subsystems/businessrules/Business-Rules/X.htm`) map to `html/Business-Rules/X_1.htm`, which is the converter's own rule (`6b5c7e5`).
- Checked for all 367 entries (and the 20 Transaction Insight entries): every one resolves to a page outside `unfiled/`.

**T2.**
- **Translator 4.2.0.** `html/User/Default.htm` begins "Default — This target rule adds a default value to flat file targets…". `_marked_topic` is true, so the 4202b6d rule keeps it.
- **Offer and Price Engine 6.0.0.** `installation-configuration/index.htm` begins "Index — The Offer Search Index Service creates product indices…".
- **ActiveSpaces 5.2.0.** `_globalpages/About-this-Product.htm` holds 4 sentences, for example "TIBCO FTL is an embedded and bundled component…". The landing page has only the first one. `GENERATED_DIRECTORIES` skips `_globalpages`.

**T3.** `families/en-us-tib-platform/extracted/tibco-control-plane/1.20.0/…/html/Subsystems/platform-ct/user-guide/` has no `process-archive*` file, and neither do Platform 1.1.0 or CLI 1.2.0. The Reward 22.3.0 package has no `*=GUID-*=en_US=.htm` files.

**X1, content written directly inside a list.**
- **Flogo 3.0.1, Oracle Database Delete.** The source (`connectors/oracledb/oracle-database-delete.htm`, lines 196–209) has `<ul>` directly inside `<ul>`, holding "Exec Procedure_Name;" and "Exec Procedure_Name @procedure_variable = ?param1;".
  - `…/oracle-database/oracle-database-query.md` (Delete section) ends that item at "**Call Procedure and Call Functions Syntax:**" with nothing under it.
  - The same loss is in Flogo VS Code 1.3.5.
- **Flogo VS Code 1.3.5, `installation.md`.** Step 5 reads "To create an image from the running container, run the following command:", and then the command is missing.
  - The source (`install-guide/Extension-with-Dev-Containers.htm`, line 290) has `<pre>docker commit …</pre>` and an `<ol>` with 2 items, both directly inside the `<ol>`.
- **Control Plane 1.20.0** (and Platform 1.1.0), "Configuring Monitoring for a Machine". The source has 4 `<ol class="steps">` procedures. Each starts with a "Procedure" label and a `<b>` title, directly inside the `<ol>`.
  - The page keeps the first two titles.
  - "To Clear…" and "To Delete a Monitoring Configuration From a Machine" are gone, and their steps run on as steps 5–7 of "To Add an Event".
- **Also affected:**
  - Activation Service 1.1.0 "Step 1: Planning for Activation": the 3 benefits and the note after "helping:" are gone;
  - EDISIM 6.21.0 introduction: "Other TIBCO Foresight products" and its 11-row table are gone;
  - Offer and Price Engine 6.0.0 "EMS Setup": the `kubectl run ems-client` command is gone.

**X2.** These pages carry the text, with `\<`:
- BusinessConnect 7.5.0 `remote-client-service-audit-log.md` line 282;
- the BusinessConnect EDI HIPAA pages;
- Files adapter `jms-messages-compression.md` line 137 (‘\<’).

Translator 4.2.0 `rules-string.md` line 504 writes "XML Escape Code &apos;", which shows as an apostrophe. The source has `&amp;apos;`, so the old site showed the code itself. Line 485 reads "**&lt; = \<&gt; = >&apos; = ’**".

**X3.**
- Substation ES `lta-agent-messages.md` lines 226–229: "The supported codes are" followed by `<samp>1</samp>,` `<samp>2</samp>, and` `<samp>3.</samp>`, each on its own line.
- Control Plane `known-issues.md` line 797 has "`helm uninstall &lt;oauth2proxy-release-name&gt; …`" inside `<code>`, as the source does.
- Order Management 6.1.0 `deployment.md` lines 215–219 have the ENTRYPOINT in a fence.

**X4, staging and `<samp>`/`<var>`.**
- **What staging shows.** `…/tibco-substation-es/online-help/2-14-0/messages-and-codes/substation-es-messages/lta-agent-messages.html` reads "The supported codes are,, and". The Code column is empty for every row; `transformer-messages.html` rows start "IId:" with no message code and "RC: RSN:" with no values.
- **What the Markdown has.** The same tables hold `<samp>SXT5003E</samp>` and `<var class="varname">Intf-Id</var>` (`transformer-messages.md`, lines 20–26).
- **How common it is.** A partial scan of `wip` finds `<samp>` and `<var>` on about 1,000 pages: BPM 531/251, BW plug-ins 205/94, mainframe 128/119, adapters 44/47, data management 9/144, and more. The scan stopped before the last repos.

**M1.**
- Adapter for IBM i 6.4.0 `toc.yml` lines 530–531 list "TIBCO Product Documentation and Support Services" once, at the end. The old menu had a copy per guide (`Legal and Third-Party Notices/copyright.md`, `TIBCO Product Documentation and Support Services/…`).
- Reward 22.3.0 lists both pages last (`tibco-documentation-and-support-services.md`, `legal-and-third-party-notices.md`). The `tibco-reward-2/` copies are on disk, outside the menu.
- `docs/planning.md` describes the tail move (`navigation._tail` removes "every further copy").

**M2.** Patterns 6.2.0 `utilities/nsc-commands.md` starts "# NSC Commands" and then "## NSC Commands". `toc.yml` line 699 lists the page bare, while the old entry pairs with `#nsc-commands-1`. Twelve `TOC_MOVED` entries follow from it ("under …#nsc-commands-1").

**M4.**
- Hawk RedTail: the Enterprise Edition topics pair against the "Installation, Configuration and Administration Container Edition" guide.
- BusinessConnect CE ebXML: ebMS2 against ebMS3.
- EDISIM: the X12 and HIPAA tutorials.
- Enterprise Administrator: the user guide against the installation guide.

**M5.**
- Control Plane 1.20.0: "Accessing the API documentation…", "Managing Containers" and others sit "under (top)" in the old menu. `toc.yml` line 624 nests them under "TIBCO BusinessWorks 5 (Containers)".
- Product and Service Catalog 5.1.0: the release-note sections now sit under "New Features".
- iProcess Engine: 73 DB2/Oracle/SQL Server administration chapters.

**M8.** `en-us-tib-iprocess-userdocs/…/11-10-0/toc.yml` lines 266–275 have 4 heading rows (`defining-the-procedure.md#…`) before the page. On 14 Nov staging lists it under "Getting Started", right after "Defining the Procedure".

**C1 and C2.**
- **Repair status.** `repair_status` has R001 `fixed` for all 7 versions.
- **No leftover alerts in these repos.** `wip` has no `[!NOTE]` left in the Cloud, FTL or Foresight repos.
- **Cloud API Modeler 1.5.0** `authorizing-access-to-your-github-repository.html` shows "**Note:**" on 14 Nov.
- **Real leftovers:**
  - Fulfillment Provisioning 3.10.0 `developers-guide/data-mapping.md` line 468 (`> [!NOTE]` after a list);
  - Product and Service Catalog 5.1.0 `sid-based-data-modeling-for-the-product-catalog.md` line 303 (indented in a list).
- **Probably the same miss, on pages Batch 2 did not flag:** API Exchange Gateway 2.5.1 `authentication-using-file-based-identity-store.md` (3), Fulfillment Provisioning 3.9.0 `samples.md`, and 1 BW plug-in and 6 MFT pages. BPM, BusinessWorks, TRA and Streaming carry thousands, which is R001 not yet run there, not this miss.

## 3. Proposed `config/verify-triage.yaml` entries

**Block A.** Paste it **after** the K6 crosswise block (it uses `*crosswise`) and **before** the general `DOCOPS-347` / `DOCOPS-348` entries.
- `DOCOPS-NEW-L` and `DOCOPS-NEW-S` are placeholders for the two new sub-tasks.
- Version-level `PAGE_MISSING` entries match the version folder only (`*/online-help/<v>`), so a page-level one still counts.

```yaml
  # Batch 2 (TIBCO newest, 13 Nov), pages, text and menus. Narrow entries: keep them
  # before the general DOCOPS-347 / DOCOPS-348 entries, and after the K6 &crosswise anchor.
  # DOCOPS-NEW-L and DOCOPS-NEW-S are placeholders for the keys of the two new sub-tasks.

  # Help not on staging: the version, its menu entry page and its product page are 404,
  # although the folder is on wip and main (most since 30 Oct or 5 Nov). Version-level
  # findings only: the path is the version folder, so a page-level PAGE_MISSING still counts.
  - code: VERIFY_PUBLISHED_PAGE_MISSING
    decision: logged
    ticket: DOCOPS-346
    slug: tibco-activematrix-adapter-for-database-tibco-business-studio
    version: "1.3.0"
    path: "*/online-help/1-3-0"
    reason: &notserved >-
      Not on staging: the version, its first menu page and the product page return 404,
      although the version is on wip and main. Same as the BW plug-ins and Streaming.
      For the AEM team.
  - {code: VERIFY_PUBLISHED_PAGE_MISSING, decision: logged, ticket: DOCOPS-346, slug: tibco-activematrix-adapter-for-files-for-unix-win-tibco-business-studio, version: "1.3.0", path: "*/online-help/1-3-0", reason: *notserved}
  - {code: VERIFY_PUBLISHED_PAGE_MISSING, decision: logged, ticket: DOCOPS-346, slug: tibco-activematrix-adapter-for-jd-edwards-enterpriseone, version: "6.1.0", path: "*/online-help/6-1-0", reason: *notserved}
  - {code: VERIFY_PUBLISHED_PAGE_MISSING, decision: logged, ticket: DOCOPS-346, slug: tibco-activematrix-adapter-for-sap-tibco-business-studio, version: "1.3.0", path: "*/online-help/1-3-0", reason: *notserved}
  - {code: VERIFY_PUBLISHED_PAGE_MISSING, decision: logged, ticket: DOCOPS-346, slug: tibco-businessconnect-configstore-management-interface-protocol, version: "6.1.0", path: "*/online-help/6-1-0", reason: *notserved}
  - {code: VERIFY_PUBLISHED_PAGE_MISSING, decision: logged, ticket: DOCOPS-346, slug: tibco-businessconnect-container-edition-configstore-management-interface-protocol, version: "1.2.1", path: "*/online-help/1-2-1", reason: *notserved}
  - {code: VERIFY_PUBLISHED_PAGE_MISSING, decision: logged, ticket: DOCOPS-346, slug: tibco-businessconnect-container-edition-ebxml-protocol, version: "1.3.0", path: "*/online-help/1-3-0", reason: *notserved}
  - {code: VERIFY_PUBLISHED_PAGE_MISSING, decision: logged, ticket: DOCOPS-346, slug: tibco-businessconnect-container-edition-edi-protocol-hipaa-edition-powered-by-instream, version: "1.3.0", path: "*/online-help/1-3-0", reason: *notserved}
  - {code: VERIFY_PUBLISHED_PAGE_MISSING, decision: logged, ticket: DOCOPS-346, slug: tibco-businessconnect-container-edition-edi-protocol-powered-by-instream, version: "1.6.1", path: "*/online-help/1-6-1", reason: *notserved}
  - {code: VERIFY_PUBLISHED_PAGE_MISSING, decision: logged, ticket: DOCOPS-346, slug: tibco-businessconnect-container-edition-rosettanet-protocol, version: "1.7.0", path: "*/online-help/1-7-0", reason: *notserved}
  - {code: VERIFY_PUBLISHED_PAGE_MISSING, decision: logged, ticket: DOCOPS-346, slug: tibco-businessconnect-container-edition-services-plug-in, version: "1.7.0", path: "*/online-help/1-7-0", reason: *notserved}
  - {code: VERIFY_PUBLISHED_PAGE_MISSING, decision: logged, ticket: DOCOPS-346, slug: tibco-businessconnect-container-edition-soap-protocol, version: "1.3.0", path: "*/online-help/1-3-0", reason: *notserved}
  - {code: VERIFY_PUBLISHED_PAGE_MISSING, decision: logged, ticket: DOCOPS-346, slug: tibco-businessconnect-edi-protocol-hipaa-edition-powered-by-instream, version: "6.7.0", path: "*/online-help/6-7-0", reason: *notserved}
  - {code: VERIFY_PUBLISHED_PAGE_MISSING, decision: logged, ticket: DOCOPS-346, slug: tibco-businessconnect-edi-protocol-powered-by-instream, version: "6.11.0", path: "*/online-help/6-11-0", reason: *notserved}
  - {code: VERIFY_PUBLISHED_PAGE_MISSING, decision: logged, ticket: DOCOPS-346, slug: tibco-foresight-edisim, version: "6.21.0", path: "*/online-help/6-21-0", reason: *notserved}
  - {code: VERIFY_PUBLISHED_PAGE_MISSING, decision: logged, ticket: DOCOPS-346, slug: tibco-foresight-instream, version: "9.4.0", path: "*/online-help/9-4-0", reason: *notserved}
  - {code: VERIFY_PUBLISHED_PAGE_MISSING, decision: logged, ticket: DOCOPS-346, slug: tibco-hawk-microagent-for-tibco-activematrix-businessworks-6, version: "6.8.0", path: "*/online-help/6-8-0", reason: *notserved}
  - {code: VERIFY_PUBLISHED_PAGE_MISSING, decision: logged, ticket: DOCOPS-346, slug: tibco-hawk-microagent-for-tibco-businessworks-container-edition, version: "2.2.0", path: "*/online-help/2-2-0", reason: *notserved}
  - {code: VERIFY_PUBLISHED_PAGE_MISSING, decision: logged, ticket: DOCOPS-346, slug: tibco-messaging-schema-repository-for-apache-kafka-enterprise-edition, version: "2.1.0", path: "*/online-help/2-1-0", reason: *notserved}
  - {code: VERIFY_PUBLISHED_PAGE_MISSING, decision: logged, ticket: DOCOPS-346, slug: tibco-product-and-service-catalog-powered-by-tibco-ebx, version: "1.1.0", path: "*/online-help/1-1-0", reason: *notserved}
  - code: VERIFY_PUBLISHED_PAGE_MISSING
    decision: logged
    ticket: DOCOPS-346
    slug: tibco-activespaces-enterprise-edition
    version: "5.2.0"
    path: "*/online-help/5-2-0"
    reason: >-
      Staging serves the pages (Last published 30 Oct) but with an empty menu, here and on
      5.1.0; toc.yml is ordinary (733 lines, valid). For the AEM team, with DOCOPS-346.

  - code: VERIFY_PUBLISHED_PAGE_MISSING
    decision: logged
    ticket: DOCOPS-344
    slug: tibco-operational-intelligence-hawk-redtail
    version: "7.5.0"
    path: "*/7-5-0/error-codes/error-codes.md"
    reason: >-
      Staging answers 500 for Error Codes (error-codes/error-codes.html, 14 Nov, twice);
      the Markdown is an ordinary 131 KB page of tables. Its parent page is served.

  # Silver Fabric Enabler for ActiveSpaces 1.2.0: published 30 Sep in the early shape
  # (toc.yml `items:`/`path:`, each book twice under html/), never re-converted.
  - code: VERIFY_PUBLISHED_PAGE_MISSING
    decision: logged
    ticket: DOCOPS-365
    slug: tibco-silver-fabric-enabler-for-activespaces-enterprise-edition
    version: "1.2.0"
    path: "*/online-help/1-2-0"
    reason: &oldshape >-
      Published 30 Sep in the early shape: toc.yml uses `items:`/`path:`, which AEM does
      not read, and every book is there twice (top level and html/). Not served. To
      re-convert and re-publish (WebWorks; Phase 34 drops the html/ copy).
  - {code: VERIFY_TOC_ENTRY_MISSING, decision: logged, ticket: DOCOPS-365, slug: tibco-silver-fabric-enabler-for-activespaces-enterprise-edition, version: "1.2.0", reason: *oldshape}

  # Topics the old menu names under a Flare subproject path (html/Subsystems/<proj>/...):
  # the converter took the master copy (html/<folder>/<name>.htm or its _1 rename) and
  # published it; verify does not resolve that alias. All 387 resolve to a menu page.
  - code: VERIFY_TOPIC_MISSING
    decision: logged
    ticket: DOCOPS-366
    slug: tibco-foresight-instream
    version: "9.4.0"
    path: "*/html/Subsystems/*"
    reason: &subproject >-
      verify reads the old menu's subproject path (html/Subsystems/<proj>/x.htm); the
      converter published the master copy (html/<folder>/x.htm or x_1.htm). Every one of
      these resolves to a published menu page (checked 14 Nov). Checker fix.
  - {code: VERIFY_TOPIC_MISSING, decision: logged, ticket: DOCOPS-366, slug: tibco-foresight-transaction-insight, version: "6.0.0", path: "*/html/Subsystems/*", reason: *subproject}

  # DOCOPS-349 (real pages named default/index): the built fix covers these two.
  - code: VERIFY_TOPIC_MISSING
    decision: logged
    ticket: DOCOPS-349
    slug: tibco-foresight-translator
    version: "4.2.0"
    path: "*/html/User/Default.htm"
    reason: >-
      "Default" (a target rule) is a real topic, listed in the menu and marked Topic; the
      Flare stub rule dropped it. Fixed in the converter (4202b6d); needs a re-convert.
  - code: VERIFY_TOPIC_MISSING
    decision: logged
    ticket: DOCOPS-349
    slug: tibco-offer-and-price-engine
    version: "6.0.0"
    path: "*/html/installation-configuration/index.htm"
    reason: >-
      "Index" (the Offer Search Index Service) is a real topic, listed in the menu and
      marked Topic; the Flare stub rule dropped it. Fixed in the converter (4202b6d);
      needs a re-convert.
  - code: VERIFY_TOPIC_MISSING
    decision: logged
    ticket: DOCOPS-349
    slug: tibco-activespaces-enterprise-edition
    version: "5.2.0"
    path: "*/html/_globalpages/About-this-Product.htm"
    reason: >-
      "About This Product" is listed in the menu but sits in Flare's _globalpages/, which
      the converter skips as generated. 4 sentences; the landing page has the first one.
      Not covered by the 4202b6d fix.

  # The old menu names files the package does not ship.
  - code: VERIFY_TOPIC_MISSING
    decision: source
    path: "*/html/Subsystems/platform-ct/user-guide/process-archive-cp-190.htm"
    reason: >-
      The old menu's "Process Archive or Adapter Archive" points to
      process-archive-cp-190.htm, which the Control Plane 1.20.0, Platform 1.1.0 and
      Platform CLI 1.2.0 packages do not ship; broken on the old site too.
  - code: VERIFY_TOPIC_MISSING
    decision: source
    slug: tibco-platform
    version: "1.1.0"
    path: "*/html/Subsystems/platform-ct/user-guide/managing-app-archives-apidocs-bw6.htm"
    reason: >-
      The old menu's "Managing Application Archives" points to a file the package does not
      ship; broken on the old site too.
  - code: VERIFY_TOPIC_MISSING
    decision: source
    slug: tibco-reward
    version: "22.3.0"
    path: "*=GUID-*=en_US=.htm"
    reason: >-
      7 old menu entries point to GUID-named files ("Award & Limits Options =GUID-...=en_US=.htm")
      that the 22.3.0 package does not ship; broken on the old site too.

  # NEW-L: a block written directly inside a list (not inside a list item) is dropped,
  # or the lists around it are run together. Real content loss.
  - code: VERIFY_TEXT_DROPPED
    decision: logged
    ticket: DOCOPS-NEW-L
    slug: tibco-activation-service
    version: "1.1.0"
    path: "*/user-guide/activation-setup/step-1-planning-for-activation.md"
    reason: &listblock >-
      The source puts a list, table, code block or procedure title directly inside a list,
      outside any list item; the converter drops it (or merges the lists around it).
      The original shows it. Converter fix and re-convert.
  - {code: VERIFY_TEXT_DROPPED, decision: logged, ticket: DOCOPS-NEW-L, slug: tibco-flogo, version: "3.0.1", path: "*/oracle-database/oracle-database-query.md", reason: *listblock}
  - {code: VERIFY_TEXT_DROPPED, decision: logged, ticket: DOCOPS-NEW-L, slug: tibco-flogo-extension-for-visual-studio-code, version: "1.3.5", path: "*/oracle-database/oracle-database-query.md", reason: *listblock}
  - {code: VERIFY_TEXT_DROPPED, decision: logged, ticket: DOCOPS-NEW-L, slug: tibco-flogo-extension-for-visual-studio-code, version: "1.3.5", path: "*/1-3-5/installation.md", reason: *listblock}
  - {code: VERIFY_TEXT_DROPPED, decision: logged, ticket: DOCOPS-NEW-L, slug: tibco-foresight-edisim, version: "6.21.0", path: "*/6-21-0/introduction-to-edisim.md", reason: *listblock}
  - {code: VERIFY_TEXT_DROPPED, decision: logged, ticket: DOCOPS-NEW-L, slug: tibco-offer-and-price-engine, version: "6.0.0", path: "*/installation-and-configuration-guide/docker.md", reason: *listblock}
  - {code: VERIFY_TEXT_DROPPED, decision: logged, ticket: DOCOPS-NEW-L, slug: tibco-control-plane, version: "1.20.0", path: "*/configuration/resource-management-overview.md", reason: *listblock}
  - {code: VERIFY_TEXT_DROPPED, decision: logged, ticket: DOCOPS-NEW-L, slug: tibco-platform, version: "1.1.0", path: "*/configuration/service-instance-configuration.md", reason: *listblock}

  # DOCOPS-360: `\<` in prose (AEM shows the backslash); R002 rewrites it as &lt;.
  - code: VERIFY_TEXT_DROPPED
    decision: logged
    ticket: DOCOPS-360
    slug: tibco-activematrix-adapter-for-files-for-unix-win-tibco-business-studio
    version: "1.3.0"
    path: "*/users-guide/advanced-topics/jms-messages-compression.md"
    reason: &escapedlt >-
      The sentence is on the page with `\<` (‘\<’, *\<var name>*, *\<end date>*); the check
      does not read it, and AEM shows the backslash. R002 (`\<` -> `&lt;`) clears both.
  - {code: VERIFY_TEXT_DROPPED, decision: logged, ticket: DOCOPS-360, slug: tibco-businessconnect, version: "7.5.0", path: "*/trading-partner-administration/remote-client-service-audit-log.md", reason: *escapedlt}
  - {code: VERIFY_TEXT_DROPPED, decision: logged, ticket: DOCOPS-360, slug: tibco-businessconnect-container-edition-edi-protocol-hipaa-edition-powered-by-instream, version: "1.3.0", path: "*/de-identifying-a-file.md", reason: *escapedlt}
  - {code: VERIFY_TEXT_DROPPED, decision: logged, ticket: DOCOPS-360, slug: tibco-businessconnect-edi-protocol-hipaa-edition-powered-by-instream, version: "6.7.0", path: "*/hipaa.5.09.md", reason: *escapedlt}
  - code: VERIFY_TEXT_DROPPED
    decision: logged
    ticket: DOCOPS-360
    slug: tibco-foresight-translator
    version: "4.2.0"
    path: "*/user-guide/rules-reference/rules-string.md"
    reason: &literalentity >-
      The source shows an entity name as text (&amp;apos;, &amp;lt;: the page is about the
      code itself); the page writes &apos; / &lt;, which shows as the character. Same
      escaping area as DOCOPS-360.
  - {code: VERIFY_TEXT_DROPPED, decision: logged, ticket: DOCOPS-360, slug: tibco-fulfillment-provisioning, version: "3.10.0", path: "*/developers-guide/provtest/deploying.md", reason: *literalentity}

  # Present on the page; the check misreads it.
  - code: VERIFY_TEXT_DROPPED
    decision: accepted
    path: "*/substation-es-messages/lta-agent-messages.md"
    reason: >-
      "The supported codes are 1, 2, and 3." is present (raw HTML table, each code in
      <samp> on its own line); the check reads it in parts. Substation ES, Transaction
      Interface for CICS and IMS 2.14.0.
  - code: VERIFY_TEXT_DROPPED
    decision: accepted
    slug: tibco-businessconnect-container-edition
    version: "1.7.1"
    path: "*/others/activate-protocol-plug-ins.md"
    reason: >-
      "The default value is 1000." is present (raw HTML table, split over two lines); the
      check reads it in two parts.
  - code: VERIFY_TEXT_DROPPED
    decision: logged
    ticket: DOCOPS-366
    slug: tibco-order-management
    version: "6.1.0"
    path: "*/administration/deployment.md"
    reason: >-
      The ENTRYPOINT line with <service_name> is in a fenced code block, wrapped as in the
      source; verify does not read it. Checker.
  - code: VERIFY_TEXT_DROPPED
    decision: logged
    ticket: DOCOPS-366
    slug: tibco-control-plane
    version: "1.20.0"
    path: "*/release-notes/known-issues.md"
    reason: &backtick >-
      "helm uninstall <oauth2proxy-release-name> ..." is present, escaped, inside <code>
      with the source's own backticks; verify does not read it. Checker.
  - {code: VERIFY_TEXT_DROPPED, decision: logged, ticket: DOCOPS-366, slug: tibco-platform-command-line-interface, version: "1.2.0", path: "*/release-notes/known-issues.md", reason: *backtick}

  # Support and legal pages: one copy kept at the end of the menu, further copies dropped
  # on purpose (navigation._tail; planning.md, DITA tail move).
  - code: VERIFY_TOC_ENTRY_MISSING
    decision: accepted
    slug: tibco-activematrix-adapter-for-ibm-i
    version: "6.4.0"
    path: "*Notices/*"
    reason: &tailcopy >-
      A second copy of the support or legal page (one per guide in the old menu); toc.yml
      keeps one copy, at the end, by design (navigation._tail). The page is published.
  - {code: VERIFY_TOC_ENTRY_MISSING, decision: accepted, slug: tibco-activematrix-adapter-for-ibm-i, version: "6.4.0", path: "*/TIBCO Product Documentation and Support Services/*", reason: *tailcopy}
  - {code: VERIFY_TOC_ENTRY_MISSING, decision: accepted, slug: tibco-activematrix-adapter-for-jd-edwards-enterpriseone, version: "6.1.0", path: "*/Legal/*", reason: *tailcopy}
  - {code: VERIFY_TOC_ENTRY_MISSING, decision: accepted, slug: tibco-activematrix-adapter-for-jd-edwards-enterpriseone, version: "6.1.0", path: "*/TIBCO_Documentation_and_Support/*", reason: *tailcopy}
  - {code: VERIFY_TOC_ENTRY_MISSING, decision: accepted, slug: tibco-businessconnect-configstore-management-interface-protocol, version: "6.1.0", path: "*/TIB_bccmi_user/preface.2.4.md*", reason: *tailcopy}
  - {code: VERIFY_TOC_ENTRY_MISSING, decision: accepted, slug: tibco-businessconnect-cxml-protocol, version: "6.1.0", path: "*/preface.?.4.md*", reason: *tailcopy}
  - {code: VERIFY_TOC_ENTRY_MISSING, decision: accepted, slug: tibco-businessconnect-edi-protocol-hipaa-edition-powered-by-instream, version: "6.7.0", path: "*/TIB_bcedihed_6.7_configuration/preface.4.4.md*", reason: *tailcopy}
  - {code: VERIFY_TOC_ENTRY_MISSING, decision: accepted, slug: tibco-businessconnect-plug-in-for-ssh-server, version: "1.1.0", path: "*/TIB_bcsftp_user_guide/preface.2.4.md*", reason: *tailcopy}
  - {code: VERIFY_TOC_ENTRY_MISSING, decision: accepted, slug: tibco-businessconnect-rosettanet-protocol, version: "5.3.0", path: "*/tib_bcrn_usr/preface.3.4.md*", reason: *tailcopy}
  - {code: VERIFY_TOC_ENTRY_MISSING, decision: accepted, slug: tibco-businessconnect-partner-management-portal, version: "1.1.1", path: "*/legal-and-third-party-notices.md", reason: *tailcopy}
  - {code: VERIFY_TOC_ENTRY_MISSING, decision: accepted, slug: tibco-businessconnect-partner-management-portal, version: "1.1.1", path: "*/tibco-documentation-and-support-services.md", reason: *tailcopy}
  - {code: VERIFY_TOC_ENTRY_MISSING, decision: accepted, slug: tibco-product-and-service-catalog, version: "5.1.0", path: "*/_templates/legal-and-third-party-notices.md", reason: *tailcopy}
  - {code: VERIFY_TOC_ENTRY_MISSING, decision: accepted, slug: tibco-product-and-service-catalog, version: "5.1.0", path: "*/_templates/tibco-documentation-and-support-services.md", reason: *tailcopy}
  - {code: VERIFY_TOC_ENTRY_MISSING, decision: accepted, slug: tibco-product-and-service-catalog-powered-by-tibco-ebx, version: "1.1.0", path: "*/legal-and-third-party-notices.md", reason: *tailcopy}
  - {code: VERIFY_TOC_ENTRY_MISSING, decision: accepted, slug: tibco-product-and-service-catalog-powered-by-tibco-ebx, version: "1.1.0", path: "*/tibco-documentation-and-support-services.md", reason: *tailcopy}
  - {code: VERIFY_TOC_ENTRY_MISSING, decision: accepted, slug: tibco-reward, version: "22.3.0", path: "*/tibco-reward-2/legal-and-third-party-notices.md", reason: *tailcopy}
  - {code: VERIFY_TOC_ENTRY_MISSING, decision: accepted, slug: tibco-reward, version: "22.3.0", path: "*/tibco-reward-2/tibco-documentation-and-support-services.md", reason: *tailcopy}

  # Doubled heading (DOCOPS-336): the merged page repeats its title as "## Title", so the
  # old entry pairs with #title-1. Clears when the doubled headings go.
  - code: VERIFY_TOC_ENTRY_MISSING
    decision: logged
    ticket: DOCOPS-336
    slug: tibco-foresight-edisim
    version: "6.21.0"
    path: "*.md#*-1"
    reason: &doubled >-
      The page repeats its title as a second heading, so the old menu entry pairs with
      #<title>-1, a row toc.yml does not have; the page is in the menu. Clears with
      DOCOPS-336.
  - {code: VERIFY_TOC_ENTRY_MISSING, decision: logged, ticket: DOCOPS-336, slug: tibco-foresight-hipaa-validator-desktop, version: "9.2.0", path: "*.md#*-1", reason: *doubled}
  - {code: VERIFY_TOC_ENTRY_MISSING, decision: logged, ticket: DOCOPS-336, slug: tibco-patterns, version: "6.2.0", path: "*.md#*-1", reason: *doubled}
  - {code: VERIFY_TOC_MOVED, decision: logged, ticket: DOCOPS-336, slug: tibco-patterns, version: "6.2.0", path: "*/utilities/nsc-commands*", reason: *doubled}
  - {code: VERIFY_TOC_MOVED, decision: logged, ticket: DOCOPS-336, slug: tibco-foresight-edisim, version: "6.21.0", path: "*/using-xml/using-standards-editor-with-schemas-and-dtds/*", reason: *doubled}

  - code: VERIFY_TOC_ENTRY_MISSING
    decision: logged
    ticket: DOCOPS-362
    slug: tibco-flogo-extension-for-visual-studio-code
    version: "1.3.5"
    path: "*#*-----*"
    reason: >-
      "Mapping Data by Using if/else Conditions": the heading target is written with
      dashes for the code part. Fixed in fix/anchors; needs a re-convert.

  # A topic in two guides (sister guides: EE/CE, ebMS2/ebMS3, X12/HIPAA, user/installation):
  # the check pairs the old entries with the copies crosswise. Not a content change.
  - {code: VERIFY_TOC_MOVED, decision: accepted, slug: tibco-businessconnect-container-edition-ebxml-protocol, version: "1.3.0", reason: *crosswise}
  - {code: VERIFY_TOC_MOVED, decision: accepted, slug: tibco-businessconnect-container-edition-edi-protocol-powered-by-instream, version: "1.6.1", reason: *crosswise}
  - {code: VERIFY_TOC_MOVED, decision: accepted, slug: tibco-enterprise-administrator, version: "2.4.3", path: "*/*", reason: *crosswise}
  - {code: VERIFY_TOC_MOVED, decision: accepted, slug: tibco-foresight-edisim, version: "6.21.0", path: "*/business-rules/*", reason: *crosswise}
  - {code: VERIFY_TOC_MOVED, decision: accepted, slug: tibco-foresight-hipaa-validator-desktop, version: "9.2.0", reason: *crosswise}
  - {code: VERIFY_TOC_MOVED, decision: accepted, slug: tibco-foresight-studio, version: "9.3.0", reason: *crosswise}
  - {code: VERIFY_TOC_MOVED, decision: accepted, slug: tibco-operational-intelligence-hawk-redtail, version: "7.5.0", reason: *crosswise}
  - {code: VERIFY_TOC_MOVED, decision: accepted, slug: tibco-order-management, version: "6.1.0", reason: *crosswise}
  - {code: VERIFY_TOC_MOVED, decision: accepted, slug: tibco-flogo-extension-for-visual-studio-code, version: "1.3.5", reason: *crosswise}
  - {code: VERIFY_TOC_MOVED, decision: accepted, slug: tibco-reward, version: "22.3.0", path: "*/22-3-0/tibco-reward/*", reason: *crosswise}
  - {code: VERIFY_TOC_MOVED, decision: accepted, slug: tibco-foresight-instream, version: "9.4.0", path: "*/*", reason: *crosswise}

  # Staging shows a page listed twice only once (as for Scribe).
  - code: VERIFY_PUBLISHED_TOC_MOVED
    decision: accepted
    slug: tibco-flogo-extension-for-visual-studio-code
    version: "1.3.5"
    reason: &shownonce >-
      toc.yml lists the page under two parents, as the old menu did; staging shows it
      once, and readers still reach it.
  - {code: VERIFY_PUBLISHED_TOC_MOVED, decision: accepted, slug: tibco-order-management, version: "6.1.0", reason: *shownonce}
  - {code: VERIFY_PUBLISHED_TOC_MOVED, decision: accepted, slug: tibco-product-and-service-catalog, version: "5.1.0", path: "*Offer and Price Designer Overview > Offer and Price Designer Overview", reason: *shownonce}

  - code: VERIFY_PUBLISHED_TOC_ENTRY_MISSING
    decision: logged
    ticket: DOCOPS-351
    slug: tibco-iprocess-workspace-windows
    version: "11.10.0"
    path: "*Where To Find More Information On Defining Procedures"
    reason: >-
      The page follows four heading rows (defining-the-procedure.md#...), which staging
      drops; the pairing slips. The page is served and in the menu (14 Nov).

  # AEM drops <samp> and <var> (with their text) from raw HTML: message codes and
  # placeholders vanish (Substation ES "The supported codes are,, and").
  - code: VERIFY_PUBLISHED_TEXT_DIFF
    decision: logged
    ticket: DOCOPS-NEW-S
    path: "*/2-14-0/messages-and-codes/*"
    reason: >-
      Staging drops <samp> and <var> elements with their text from raw HTML tables: the
      Code column is empty and placeholders are gone. Substation ES, Transaction Interface
      for CICS and IMS 2.14.0. For the AEM team (UAT row); or we write <code>/<em>.
```

**Block B.** Paste it **directly above** the existing `VERIFY_PUBLISHED_CALLOUT_UNRENDERED` / DOCOPS-250 entry near the top of the file. Otherwise that entry matches first, and these two stay excused as fixed.

```yaml
  # R001 left a note in GitHub alert form (inside or right after a list).
  - code: VERIFY_PUBLISHED_CALLOUT_UNRENDERED
    decision: logged
    ticket: DOCOPS-313
    slug: tibco-fulfillment-provisioning
    version: "3.10.0"
    path: "*/developers-guide/data-mapping.md"
    reason: &r001miss >-
      R001 left one note as `> [!NOTE]` (after a list, or indented in one); AEM shows it
      with no label. A second R001 pass, for notes in or after lists.
  - {code: VERIFY_PUBLISHED_CALLOUT_UNRENDERED, decision: logged, ticket: DOCOPS-313, slug: tibco-product-and-service-catalog, version: "5.1.0", path: "*/sid-based-data-modeling-for-the-product-catalog.md", reason: *r001miss}
```

**Block C (optional; Open question 2).** It accepts the 246 "nested under the guide page" moves. Paste it after block A.

```yaml
  # Optional (Open question 2): reframe nests a guide's top-level chapters under the
  # guide's own page; the old menu listed them at the top. Not a content change.
  - code: VERIFY_TOC_MOVED
    decision: accepted
    slug: tibco-control-plane
    version: "1.20.0"
    reason: &nested >-
      The old menu lists these topics at the top level (a guide's chapters, or a release
      note's sections); toc.yml nests them under their guide or page, as reframe does.
      Every page is in the menu. Not a content change.
  - {code: VERIFY_TOC_MOVED, decision: accepted, slug: tibco-platform, version: "1.1.0", reason: *nested}
  - {code: VERIFY_TOC_MOVED, decision: accepted, slug: tibco-platform-command-line-interface, version: "1.2.0", reason: *nested}
  - {code: VERIFY_TOC_MOVED, decision: accepted, slug: tibco-iprocess-engine, version: "11.10.0", reason: *nested}
  - {code: VERIFY_TOC_MOVED, decision: accepted, slug: tibco-product-and-service-catalog, version: "5.1.0", reason: *nested}
  - {code: VERIFY_TOC_MOVED, decision: accepted, slug: tibco-product-and-service-catalog-powered-by-tibco-ebx, version: "1.1.0", reason: *nested}
  - {code: VERIFY_TOC_MOVED, decision: accepted, slug: tibco-businessconnect-partner-management-portal, version: "1.1.1", reason: *nested}
  - {code: VERIFY_TOC_MOVED, decision: accepted, slug: tibco-reward, version: "22.3.0", path: "*/tibco-reward-2/whats-new.md", reason: *nested}
```

**No entry is proposed for:**
- **Platform 1.1.0:** re-check after R2.
- **Hawk RedTail "Structure":** it is served now.
- **The 6 `TOC_ORDER` warnings.**
- **C1:** already excused by the R001 entry; re-check instead.

## 4. Proposed Jira changes

Reuse first. This means two new sub-tasks, and story points only where there is work.

| Issue | Change | Points |
|---|---|---|
| **DOCOPS-346** | Dated note listing the 20 versions (P1) and the ActiveSpaces empty menu (P2). Rename to "Online help not served on staging: Streaming, BW plug-ins, and 20 more TIBCO versions; ActiveSpaces menu empty". | none (AEM) |
| **DOCOPS-344** | Note: Hawk RedTail 7.5.0 Error Codes answers 500 (a page not served properly, the same family). | none |
| **DOCOPS-349** | Note: Translator 4.2.0 and Offer and Price Engine 6.0.0 go on the re-convert list (fix built). ActiveSpaces 5.2.0 `_globalpages/About-this-Product.htm` needs a small extension: keep a TOC-listed topic in `_globalpages/`. | +0.25 |
| **DOCOPS-360** | Note: 4 more versions with `\<` (R002 covers them). Variant: an entity name shown as text (`&amp;apos;`, `&amp;lt;`) is written as `&apos;`/`&lt;` (Translator 4.2.0, Fulfillment Provisioning 3.10.0). | +0.25 |
| **DOCOPS-366** | Note: 2 new checker causes. (1) Flare subproject alias and `_1` renames (387 false `TOPIC_MISSING`). (2) Text in a fence, or backticks inside `<code>` (3). | +0.5 |
| **DOCOPS-336** | Note: EDISIM 6.21.0, HIPAA Validator Desktop 9.2.0 and Patterns 6.2.0. The menu findings clear with the doubled headings. | none |
| **DOCOPS-362** | Note: add Flogo VS Code 1.3.5 to the re-convert list. | none |
| **DOCOPS-365** | Widen to "help published incomplete or in an old shape". Note: Silver Fabric 1.2.0, to re-convert (WebWorks) and re-publish. | +0.25 |
| **DOCOPS-313** | Note: R001 misses notes inside or right after a list. Found on Fulfillment Provisioning 3.10.0 and 3.9.0, Product and Service Catalog 5.1.0, API Exchange Gateway 2.5.1, 1 BW plug-in and 6 MFT pages. A second pass is needed. | +0.25 |
| **DOCOPS-351** | Note: iProcess Workspace (Windows) 11.10.0, heading-row knock-on. | none |
| **DOCOPS-348** | Note: the `<samp>`/`<var>` cause is split out to NEW-S. About a third of the rest are `<…>` placeholders (360). | none |
| **NEW-L** (new sub-task, TechDocs) | "Content placed directly inside a list (not in a list item) is dropped." Converter fix, then re-convert 7 versions (8 pages): Activation Service 1.1.0, Flogo 3.0.1, Flogo VS Code 1.3.5 (2 pages), EDISIM 6.21.0, Offer and Price Engine 6.0.0, Control Plane 1.20.0 and Platform 1.1.0. A corpus count picks the rest. | 1 |
| **NEW-S** (new sub-task, Digital Platform) | "Staging drops `<samp>` and `<var>` with their text." Our part: the UAT row, and measuring the page count. Fallback if AEM declines: the converter writes `<code>`/`<em>`. | 0.25 |

## 5. UAT-sheet rows (Digital Platform)

Columns: Type, Issue description, Category, Priority, Found In, Reporter, Status, Stage Issue link, Comments.

```csv
Type,Issue description,Category,Priority,Found In,Reporter,Status,Stage Issue link,Comments
Desktop,"Online help not served: the version page, its first page and the product page return 404, although the content is in GitHub (wip and main) since 30 Oct / 5 Nov. Example: BusinessConnect Container Edition SOAP Protocol 1.3.0. GitHub: https://github.com/tibco/en-us-tib-businessconnect-userdocs/blob/wip/en-us/tibco-businessconnect-container-edition-soap-protocol/online-help/1-3-0/tibco-businessconnect-container-edition-soap.md. BusinessConnect 7.5.0 in the same repo is served. Related issue #<Streaming row>.",Content,Critical,"20 TIBCO versions (Adapters 4, BusinessConnect 10, Foresight 2, Hawk 2, Messaging 1, Fulfillment 1)",Mayur,New,https://stg-docs.tibco.com/us/en/tibco-businessconnect-container-edition-soap-protocol/online-help/1-3-0/tibco-businessconnect-container-edition-soap.html,"DOCOPS-346; 20 versions, whole help each; list in reports/verify/triage-batch2-pages-text-2026-11-14.md"
Desktop,"Online help menu is empty: pages are served but the left 'Online Help' list has no entries. toc.yml is valid. Example: ActiveSpaces Enterprise Edition 5.2.0 (5.1.0 the same). GitHub: https://github.com/tibco/en-us-tib-activespaces-userdocs/blob/wip/en-us/tibco-activespaces-enterprise-edition/online-help/5-2-0/toc.yml",Design,High,TIBCO ActiveSpaces Enterprise Edition 5.2.0,Mayur,New,https://stg-docs.tibco.com/us/en/tibco-activespaces-enterprise-edition/online-help/5-2-0/tibco-activespaces-enterprise-edition.html,"DOCOPS-346; 1 product, at least 2 versions"
Desktop,"Page returns HTTP 500 (Error Codes, a long page of tables); its parent page is served and links to it. GitHub: https://github.com/tibco/en-us-tib-hawk-userdocs/blob/wip/en-us/tibco-operational-intelligence-hawk-redtail/online-help/7-5-0/error-codes/error-codes.md",Content,High,TIBCO OI Hawk RedTail 7.5.0,Mayur,New,https://stg-docs.tibco.com/us/en/tibco-operational-intelligence-hawk-redtail/online-help/7-5-0/error-codes/error-codes.html,"DOCOPS-344; 1 page"
Desktop,"Text inside <samp> and <var> is removed on the served page: message codes and placeholders disappear (Code column empty; 'The supported codes are,, and'). The Markdown has <samp>SXT5003E</samp>, <var class=""varname"">Intf-Id</var>. GitHub: https://github.com/tibco/en-us-tib-mainframe-userdocs/blob/wip/en-us/tibco-substation-es/online-help/2-14-0/messages-and-codes/substation-es-messages/lta-agent-messages.md",Content,Critical,"TIBCO Substation ES 2.14.0 (also Transaction Interface for CICS/IMS 2.14.0)",Mayur,New,https://stg-docs.tibco.com/us/en/tibco-substation-es/online-help/2-14-0/messages-and-codes/substation-es-messages/lta-agent-messages.html,"NEW-S; about 1,000 pages use <samp>/<var> across TIBCO repos (BPM, BW plug-ins, mainframe, adapters, data management)"
```

## 6. Re-check once staging has rebuilt (or the fix is out)

| Version | Why | When |
|---|---|---|
| Cloud API Modeler 1.5.0, eFTL 7.3.0, FTL 7.3.0, Enterprise Administrator 2.4.3, Foresight Transaction Insight 6.0.0 | Labelled notes not yet served at check time; CAM shows them on 14 Nov | Now |
| Hawk RedTail 7.5.0 | "Structure" is served now; Error Codes 500 | Now, then after AEM's answer |
| iProcess Workspace (Windows) 11.10.0 | The page is in the menu now | Now |
| Platform 1.1.0 | Not on `wip` yet (K3) | After R2 (Thu 19) |
| Translator 4.2.0, Offer and Price Engine 6.0.0, Flogo VS Code 1.3.5 | 349 / 362 re-convert | After R2 |
| Foresight Instream 9.4.0, Transaction Insight 6.0.0 | `TOPIC_MISSING` should clear | After the DOCOPS-366 checker fix |
| The 20 P1 versions, and ActiveSpaces 5.2.0 | Not served / empty menu | After Digital Platform answers on 346 |
| Silver Fabric 1.2.0 | Re-published in today's shape | After the DOCOPS-365 re-convert |

## 7. Open questions

1. **NEW-L scope.** Should the list fix go into R2 (re-convert the 7 versions by Tue 17), or after go-live? It is real loss (commands, procedure titles, a product table), but each case is small.
2. **Menu nesting (M5, 246 findings in 8 versions).** In these versions, `toc.yml` nests a guide's chapters under the guide's own page, where the old menu listed them at the top. Accept that as the reframe design (block C), or should it be traced first?
3. **`<samp>`/`<var>` (NEW-S).** Report it to Digital Platform and wait, or should the converter write `<code>`/`<em>` instead now? The second does not depend on AEM, but means a re-convert of about 1,000 pages.
