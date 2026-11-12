# Verify triage: BW plug-ins, newest versions, 2026-11-12

This is a read-only triage. Nothing was edited, logged or run. The data comes from each version's latest stored findings in `cache/state.db` (the same data `ISSUES.csv` uses), with the current `config/verify-triage.yaml` applied.

**Scope.** 75 BW plug-in versions were checked today:
- 73 with online help, plus EDI Healthcare and EDI Standard 6.3.1 (documents only).
- Results: 63 `lost`, 3 `issues`, 7 `logged`, 2 `clean`.
- BusinessEvents 6.3.2 is covered in its own section below.

**What the 63 `lost` versions are:**
- 61 are not on staging at all.
- LDAP 7.3.0 has one page that staging serves empty.
- MDM 7.0.2 has a menu entry whose topic is missing from the original package.

**Simulated result.** The triage entries proposed below were applied in memory to the stored findings, with no file written and no requests made:
- Every one of the 76 versions (75 BW plug-ins plus BE 6.3.2) moves to `logged`, except the 2 that are `clean`.
- 64 versions go from `lost` to `logged`, and 3 from `issues` to `logged`.
- No unlogged finding is left.

**Proposed Jira changes:**
- **2 new sub-tasks**, both owned by TechDocs: A (versions published incomplete) and B (`verify` false findings).
- **4 existing issues get more versions:** DOCOPS-346, 344, 351 and 364.

---

## 1. Summary table

| # | Kind (plain words) | Codes | Versions / findings | Verdict | Jira | Owner |
|---|---|---|---|---|---|---|
| K1 | **BW plug-in help is not on staging.** For each version, staging returns 404 for the menu entry page, the version page and every topic. The product page is 404 too, although the content is in the repo, on both `wip` and `main`. | `PUBLISHED_PAGE_MISSING` (version level) | 61 versions / 61 | (a) widen an existing issue | **DOCOPS-346** (rename: "Online help not served on staging: Streaming, 61 BW plug-in versions") | Digital Platform |
| K2 | **A page is served with an empty article** (LDAP 7.3.0, ModifyDN Entry). Staging shows only the title. None of the 158 sentences, 6 pictures or 2 heading targets are served. | `PUBLISHED_ANCHOR_MISSING` 2 (unlogged), plus `TEXT_DIFF` 1 and `IMAGE_BROKEN` 6, now filed under 348/347 | 1 version / 9 | (a) | **DOCOPS-344** | Digital Platform |
| K3 | **A page disappears from the staging menu when its first `toc.yml` row is a heading row elsewhere** (BE 6.3.2, Addressing Schema Elements). See section 5. | `PUBLISHED_TOC_ENTRY_MISSING` | 1 version / 1. A scan of the repos finds 25 pages in 10 versions | (a), a variant of DOCOPS-351 | **DOCOPS-351** | Digital Platform (our side could also fix it) |
| K4 | **The help was published incomplete.** The menu holds only Home and What's New, and every topic sits in `unfiled/`: OData S/4HANA 6.3.0 (found by repo scan) and 6.4.0, SAP BTP 6.0.0. Package documents (PDF guides, readme, license) were never published for 6 versions. The REST and JSON 2.1.0 readme on docs.tibco.com has changed since we published it. | `TOPIC_MISSING` 4, `DOCUMENT_MISSING` 30, `DOCUMENT_CHANGED` 1 | 8 versions / 35 | (d) new | **NEW-A** | TechDocs |
| K5 | **`verify` reports things that are not wrong** (5 causes, listed in section 3). | `TOC_ENTRY_MISSING` 12, `TOC_MOVED` 61, `TOC_ORDER` 1, `TEXT_DROPPED` 7 | 10 versions / 81 | (b) checker false positives | **NEW-B** | TechDocs |
| K6 | **The same topic is listed under two parents** in both the old menu and `toc.yml`. The check pairs the copies crosswise. | `TOC_MOVED` (rows of the form `page.md#anchor`) | 6 versions / 7 | accepted (as already done for Scribe and Flogo PAYG) | none | none |
| K7 | **Trillium 6.0.0 findings.** The published copy is the old flat tree from 6 Oct (`out-of-date`). The version is on Karan's **remove** list (K2, Mon 16). | `TEXT_DROPPED` 21, `TOC_ENTRY_MISSING` 46, `TOPIC_MISSING` 25, `TOC_MOVED` 5 | 1 version / 97 | (a) it will be removed | **DOCOPS-364** | Engineering decision; TechDocs removes it |
| K8 | **Writers' draft comments are visible** ("Draft comments: …", "<draft>: …"). Confidentiality 6.1.1. The original help shows them on docs.tibco.com too (checked). | `TEXT_DROPPED` | 1 version / 2 | (c) `source` | none | see Open question 2 |
| K9 | **The old menu points to a topic that is not in the package** (MDM 7.0.2, "Installing TIBCO BusinessWorks" → `applying-the-hf-001-hotfix-…htm`). | `TOPIC_MISSING` | 1 version / 1 | (c) `source` | none | none |
| K10 | **Siebel 7.3.0 home page is reduced to "# Home".** The banner is gone: product name (which has a broken character "BusinessWorks�" in the source), version, release date, and links to the release documents. Those documents are published separately. | `TEXT_DROPPED` | 1 version / 1 | accepted (see Open question 4) | none | none |
| K11 | **An inline toolbar icon in a menu path was dropped** (Kafka 6.8.2: "Debug [icon] > Debug Configurations" became "**Debug > Debug Configurations**"). | `IMAGE_MISSING` | 1 version / 1 | accepted (the icon is decorative; the word "Debug" carries the meaning) | none | none |

**Out of scope here, still unlogged in `ISSUES.csv`:**
- Spotfire Statistica, Data Science and Statistica Integration, checked today: `TOPIC_MISSING` and `TOC_ENTRY_MISSING`, about 15,600 entries on Statistica and Data Science Workbench 14.4.0.
- Spotfire Data Virtualization 8.8.0–8.9.0 (the user said "not now" on 11 Nov).
- These belong to the Statistica triage (Batch 3), not to BW plug-ins.

### Examples (one per kind)

Repo: `https://github.com/tibco/en-us-tib-bw-plugin-userdocs/blob/wip/en-us/…`. Staging: `https://stg-docs.tibco.com/us/en/…`.

- **K1, Apache Kafka 6.8.2.**
  - Staging: `…/tibco-activematrix-businessworks-plug-in-for-apache-kafka/online-help/6-8-2/tibco-activematrix-businessworks-plug-apache-kafka.html` is 404. So are `…/6-8-2.html` and the product page `…/tibco-activematrix-businessworks-plug-in-for-apache-kafka.html` (WebFetch, today).
  - GitHub: `…/tibco-activematrix-businessworks-plug-in-for-apache-kafka/online-help/6-8-2/tibco-activematrix-businessworks-plug-apache-kafka.md`.
  - For comparison, AMQP 6.5.3 is served. Its files and commits are the same as Kafka's (`97c07b0c` on `main`, 14 Oct; `bc069869` on `wip`, 5 Nov). Nothing on our side explains why one is served and the other is not.
  - Served BW plug-ins: AMQP, CICS, EDI, EJB, IBM i, LDAP, MDM, MQTT, OData, PDF, Redis, AI.
- **K2, LDAP 7.3.0.**
  - Staging: `…/tibco-activematrix-businessworks-plug-in-for-ldap/online-help/7-3-0/user-guide/ldap-palette/modifydn-entry.html`. It returns 200, but the article has no headings and not even the first sentence ("Use the ModifyDN Entry activity to modify…").
  - GitHub: `…/tibco-activematrix-businessworks-plug-in-for-ldap/online-help/7-3-0/user-guide/ldap-palette/modifydn-entry.md`. It is an ordinary page: 449 lines, 9 raw-HTML tables, all closed.
- **K4, OData Services for SAP S/4HANA 6.4.0.**
  - GitHub: `…/tibco-activematrix-businessworks-plug-in-for-odata-services-for-sap-s-4hana/online-help/6-4-0/toc.yml` has 2 rows. 63 pages sit in `unfiled/`.
  - The conversion (6–7 Oct) recorded `NAV_NODE_DROPPED` "63 TOC id(s) with no payload entry in ent_html.js". Today the same reader (`engines/flare_toc.read_toc`) reads that file with unmatched 0, so a re-convert should restore the menu. This should be confirmed on a dry run.
  - Documents: `TIB_bwplugin-cawscs_6.1.1_*.pdf` are in the AWS Common Services 6.1.1 package (`pdf/`, `doc/`). There is no `user-guides/6-1-1`, `release-information/6-1-1` or `reference-documents/6-1-1` folder in the repo.
  - REST and JSON 2.1.0 readme: the package downloaded today adds "Windows … 2025" and "BusinessWorks (5.X and below)". The repo copy dates from 6 Oct, so the upstream package changed after we published.
- **K5, Patterns 6.2.0.**
  - GitHub: `…/tibco-activematrix-businessworks-plug-in-for-tibco-patterns/online-help/6-2-0/installation/installation-overview.md`.
  - `toc.yml` lists the page bare. The check expects `#installation-overview`.
- **K6, SMPP 6.0.3.** `toc.yml` lines 105 and 123 both list `user-guide/smpp-palette.md#fault`, as the old menu did.
- **K8, Confidentiality 6.1.1.**
  - GitHub: `…/tibco-activematrix-businessworks-plug-in-for-confidentiality/online-help/6-1-1/tibco-documentation-and-support-services.md`, line 19: "**Draft comments:** In the following paragraph, update the …".
  - The old site shows the same text: `docs.tibco.com/pub/bwpluginconfidentiality/6.1.1/doc/html/_templates/TIBCO-Documentation-and-Support-Services.htm`.

---

## 2. Proposed triage YAML entries

Narrow entries come first, because the first matching entry wins. Insert this block **before** the general `DOCOPS-347` / `DOCOPS-348` entries in `config/verify-triage.yaml`, or else the LDAP `TEXT_DIFF` and `IMAGE_BROKEN` stay under 348 and 347. `DOCOPS-NEW-A` and `DOCOPS-NEW-B` are placeholders for the keys of the two new sub-tasks.

```yaml
  # Phase 77, BW plug-ins wave 2026-11-12.
  - code: VERIFY_PUBLISHED_TEXT_DIFF
    decision: logged
    ticket: DOCOPS-344
    slug: tibco-activematrix-businessworks-plug-in-for-ldap
    path: "*/modifydn-entry.md"
    reason: >-
      Staging serves ModifyDN Entry (LDAP 7.3.0) with an empty article; the Markdown is
      ordinary. For the AEM team.
  - code: VERIFY_PUBLISHED_ANCHOR_MISSING
    decision: logged
    ticket: DOCOPS-344
    slug: tibco-activematrix-businessworks-plug-in-for-ldap
    path: "*/modifydn-entry.md#*"
    reason: The same empty page.
  - code: VERIFY_PUBLISHED_IMAGE_BROKEN
    decision: logged
    ticket: DOCOPS-344
    slug: tibco-activematrix-businessworks-plug-in-for-ldap
    path: "*/modifydn-entry.md"
    reason: The same empty page.

  - code: VERIFY_PUBLISHED_TOC_ENTRY_MISSING
    decision: logged
    ticket: DOCOPS-351
    slug: tibco-businessevents-enterprise-edition
    version: "6.3.2"
    path: "*Addressing Schema Elements"
    reason: >-
      The page's first toc.yml row is a heading row elsewhere (#mapping-and-transforming-
      data-to-function-input, line 1841); staging shows the page once, at that row and
      under that title, at .../mapping-and-transforming-data/xpath-formula-builder-for-
      xpath-2-0.html, and drops its own row (line 1926). Fix later.

  # Trillium 6.0.0: on Karan's remove list (K2); the published copy is the old flat tree.
  - code: VERIFY_TEXT_DROPPED
    decision: logged
    ticket: DOCOPS-364
    slug: tibco-activematrix-businessworks-plug-in-for-trillium
    reason: To be removed (Karan's list, K2); the published copy predates the current conversion.
  - code: VERIFY_TOC_ENTRY_MISSING
    decision: logged
    ticket: DOCOPS-364
    slug: tibco-activematrix-businessworks-plug-in-for-trillium
    reason: To be removed (Karan's list, K2).
  - code: VERIFY_TOPIC_MISSING
    decision: logged
    ticket: DOCOPS-364
    slug: tibco-activematrix-businessworks-plug-in-for-trillium
    reason: To be removed (Karan's list, K2).
  - code: VERIFY_TOC_MOVED
    decision: logged
    ticket: DOCOPS-364
    slug: tibco-activematrix-businessworks-plug-in-for-trillium
    reason: To be removed (Karan's list, K2).

  # Version-level only in practice: no served BW plug-in version has a page-level
  # PAGE_MISSING today. Triage cannot match an empty path, see Open question 6.
  - code: VERIFY_PUBLISHED_PAGE_MISSING
    decision: logged
    ticket: DOCOPS-346
    slug: "tibco-*businessworks-plug-in*"
    reason: >-
      61 of 73 BW plug-in versions with online help are not on staging (version page,
      menu and product page 404) although they are in the repo on wip and main. For
      the AEM team.

  # NEW-A: published incomplete.
  - code: VERIFY_TOPIC_MISSING
    decision: logged
    ticket: DOCOPS-NEW-A
    slug: "tibco-activematrix-businessworks-plug-in-for-*sap-*"
    path: "*/_templates/*.htm"
    reason: >-
      OData S/4HANA and SAP BTP were converted with an empty menu (NAV_NODE_DROPPED
      126/106); every topic is in unfiled/, support and legal pages not converted.
      Re-convert and re-publish.
  - code: VERIFY_DOCUMENT_MISSING
    decision: logged
    ticket: DOCOPS-NEW-A
    slug: "tibco-*businessworks-plug-in*"
    reason: >-
      Package documents (PDF guides, readme, license) never published for 6 versions;
      the packages are on disk again since Batch 1b. Re-sync.
  - code: VERIFY_DOCUMENT_CHANGED
    decision: logged
    ticket: DOCOPS-NEW-A
    slug: tibco-activematrix-businessworks-plug-in-for-rest-and-json
    version: "2.1.0"
    reason: The readme was updated on docs.tibco.com after we published it. Re-sync.

  # NEW-B: verify false findings. Delete these once NEW-B is fixed and the versions re-run.
  - code: VERIFY_TOC_ENTRY_MISSING
    decision: logged
    ticket: DOCOPS-NEW-B
    slug: tibco-activematrix-businessworks-plug-in-for-tibco-patterns
    version: "6.2.0"
    reason: >-
      verify keeps a Flare TOC bookmark that lands on the page's own top heading as
      page.md#top-heading; toc.yml lists the page bare (driver._bookmark). Not a content change.
  - code: VERIFY_TOC_MOVED
    decision: logged
    ticket: DOCOPS-NEW-B
    slug: tibco-activematrix-businessworks-plug-in-for-tibco-patterns
    version: "6.2.0"
    reason: The same bookmark misreading, on the rows under those pages.
  - code: VERIFY_TOC_MOVED
    decision: logged
    ticket: DOCOPS-NEW-B
    slug: "tibco-*businessworks-plug-in*"
    path: important-information.md
    reason: >-
      DITA's legal page "Important Information" is moved to the end by the converter;
      verify's tail rule does not know it (toc._tail_page). Not a content change.
  - code: VERIFY_TOC_MOVED
    decision: logged
    ticket: DOCOPS-NEW-B
    slug: "tibco-*businessworks-plug-in*"
    path: tibco-documentation-and-support-services.md
    reason: The same tail move, for the support page listed in each DITA guide.
  - code: VERIFY_TOC_ORDER
    decision: logged
    ticket: DOCOPS-NEW-B
    slug: tibco-activematrix-businessworks-plug-in-for-edi
    version: "6.3.0"
    path: "(top)"
    reason: The same tail move, read as a reorder of the top level.
  - code: VERIFY_TEXT_DROPPED
    decision: logged
    ticket: DOCOPS-NEW-B
    slug: tibco-activematrix-businessworks-plug-in-for-oracle-e-business-suite
    version: "6.1.2"
    path: "users-guide/oracle-e-business-suite-palette/*"
    reason: >-
      verify leaves `\<var>` in a Windows path inside a raw HTML table as words
      (text._TAG lacks `var`); the page is right.
  - code: VERIFY_TEXT_DROPPED
    decision: logged
    ticket: DOCOPS-NEW-B
    slug: tibco-activematrix-businessworks-plug-in-for-sap-hana-database
    version: "6.1.0"
    path: user-guide/getting-started.md
    reason: >-
      verify deletes `< version_number >` as a tag (text._TAG); with a space after `<`
      it is text in Markdown.
  - code: VERIFY_TEXT_DROPPED
    decision: logged
    ticket: DOCOPS-NEW-B
    slug: tibco-activematrix-businessworks-plug-in-for-oracle-fusion-cloud-applications-suite
    version: "6.0.0"
    path: user-guide/advanced-topics.md
    reason: >-
      A fence opened on a list-item line (`- ` + three backticks, line 175) is not seen
      by text._FENCE, so later fences pair wrongly and two logback.xml code blocks are lost
      to the check. The page has them.

  # K6: one topic under two parents, crosswise (as for Scribe and Flogo PAYG).
  - code: VERIFY_TOC_MOVED
    decision: accepted
    slug: tibco-activematrix-businessworks-plug-in-for-data-conversion
    version: "5.0.0"
    reason: &crosswise >-
      The old menu and toc.yml both list this topic under two parents; the check pairs
      the copies crosswise. Not a content change.
  - {code: VERIFY_TOC_MOVED, decision: accepted, slug: tibco-activematrix-businessworks-plug-in-for-database, version: "8.6.0", reason: *crosswise}
  - {code: VERIFY_TOC_MOVED, decision: accepted, slug: tibco-activematrix-businessworks-plug-in-for-pdf, version: "6.2.3", reason: *crosswise}
  - {code: VERIFY_TOC_MOVED, decision: accepted, slug: tibco-activematrix-businessworks-plug-in-for-peoplesoft, version: "7.4.0", reason: *crosswise}
  - {code: VERIFY_TOC_MOVED, decision: accepted, slug: tibco-activematrix-businessworks-plug-in-for-siebel, version: "7.3.0", reason: *crosswise}
  - {code: VERIFY_TOC_MOVED, decision: accepted, slug: tibco-activematrix-businessworks-plug-in-for-smpp, version: "6.0.3", reason: *crosswise}

  # Source and accepted.
  - code: VERIFY_TEXT_DROPPED
    decision: source
    slug: tibco-activematrix-businessworks-plug-in-for-confidentiality
    version: "6.1.1"
    reason: >-
      The original help publishes the writers' draft comments ("Draft comments:",
      "<draft>:"); shown on docs.tibco.com too. The check misses only the "<draft>:" prefixes.
  - code: VERIFY_TOPIC_MISSING
    decision: source
    slug: tibco-activematrix-businessworks-plug-in-for-mdm
    version: "7.0.2"
    path: "*/applying-the-hf-001-hotfix-*"
    reason: >-
      The old menu's "Installing TIBCO BusinessWorks" points to
      applying-the-hf-001-hotfix-to-tibco-businessworks-container-edition.htm, which the
      package does not ship; broken on the old site too.
  - code: VERIFY_TEXT_DROPPED
    decision: accepted
    slug: tibco-activematrix-businessworks-plug-in-for-siebel
    version: "7.3.0"
    path: home.md
    reason: >-
      The landing banner (product name with a broken character in the source, version,
      date, links to the release documents) is not kept; the documents are published
      separately.
  - code: VERIFY_IMAGE_MISSING
    decision: accepted
    slug: tibco-activematrix-businessworks-plug-in-for-apache-kafka
    version: "6.8.2"
    path: user-guide/pushing-an-application-to-the-cloud.md
    reason: >-
      A decorative toolbar icon inside "Debug > Debug Configurations" is dropped; the
      menu path is kept.
```

Note: `triage.load` reads a YAML anchor (`&crosswise`) like any other value. If you would rather not use anchors, repeat the reason text in each entry.

---

## 3. Proposed new Jira sub-tasks

Both go under **DOCOPS-96** (Docushift: sync and validation), like 343–363, with the labels `docushift`, `tibco`, `verify-issue`.

### NEW-A, owner TechDocs, 0.5 SP

**Summary (61 chars):** BW plug-ins published incomplete: empty menu, missing documents

**Description:**
> Found by `docushift verify`, BW plug-in newest versions, 2026-11-12 (DOCOPS-338). Logged now, fixed later.
> **Empty menu:** OData Services for SAP S/4HANA 6.3.0 and 6.4.0, SAP Business Technology Platform 6.0.0 were converted (6–7 Oct) with `NAV_NODE_DROPPED` 126/106. `toc.yml` lists only Home and What's New; 61–87 topics sit in `unfiled/`, and the support and legal pages were not converted. Today the TOC reader reads the same `ent_html.js` with no loss, so a re-convert is expected to restore the menu.
> **Documents not published:** the PDF guides, readme and license in the package are missing from the repo for AWS Common Services 6.1.1 (6), Microsoft Dynamics CRM 6.10.1 (4), OData S/4HANA 6.4.0 (7), SAP BTP 6.0.0 (7), SAP SuccessFactors 6.1.0 (1), AuditSafe for TIBCO Platform 6.0.0 (5). REST and JSON 2.1.0: the readme on docs.tibco.com changed after we published it.
> Fix: re-convert the 3 versions and re-sync all 8 from the packages Batch 1b brought back; validate; publish to `content-fix` in R2.
> Verify findings: `TOPIC_MISSING`, `DOCUMENT_MISSING`, `DOCUMENT_CHANGED` (plus `TOPIC_UNFILED` notes).

**Versions:** 8, listed above, plus OData S/4HANA 6.3.0, which is not checked yet.
**Triage:** the three `DOCOPS-NEW-A` entries above.

### NEW-B, owner TechDocs, 0.5 SP

**Summary (70 chars):** verify: false findings on BW plug-ins (TOC bookmarks, legal page, text)

**Description:**
> Found in the BW plug-in wave, 2026-11-12. These findings point at nothing wrong on the page or in the menu. To be fixed before the next wave, like DOCOPS-350/352/361.
> 1. A Flare TOC bookmark that lands on the page's own top heading is kept as `page.md#heading`, but `toc.yml` lists the page bare (`verify/driver.py:627-645` `_bookmark`; `key_of` at 222 already applies this rule to outmap anchors). Patterns 6.2.0: 12 missing, 38 moved.
> 2. DITA's legal page "Important Information" (`engines/dita.py:104`) is moved last by the converter, but `verify/toc.py:138-151` `_tail_page` only knows `is_legal_label`. EDI, EJB, Excel, Oracle EBS, ServiceNow, eFTL, Workday: 24 findings.
> 3. `verify/text.py:258-259` `_TAG`: `\<var>` is missing from the inline-tag list, and `< version_number >` (not a tag in Markdown) is deleted. Oracle EBS 6.1.2: 5; SAP HANA 6.1.0: 1. `text.py:263` `_FENCE`: a fence opened on a list-item line (`- ` + three backticks) is not seen. Oracle Fusion 6.0.0: 1.
> 4. Blind spot: `driver.py:284` skips old-TOC entries whose page sits in `unfiled/`, so a version whose whole menu was lost (NEW-A) shows only notes. Report it as an error when, for example, more than half the topics are unfiled.

**Versions:** Patterns 6.2.0; EDI 6.3.0; EJB 6.1.1; Excel 6.1.1; Oracle EBS 6.1.2; ServiceNow 6.1.0; eFTL 6.0.0; Workday 6.0.1; SAP HANA 6.1.0; Oracle Fusion 6.0.0.
**Triage:** the `DOCOPS-NEW-B` entries. Delete them after the fix and a re-run.

### Changes to existing issues (dated notes; no new issue)

- **DOCOPS-346:** rename to "Online help not served on staging: Streaming, 61 BW plug-in versions". Add a note:
  - 61 of 73 BW plug-in versions with online help return 404 for the version page, menu and product page.
  - They are in the repo on `wip` and `main` since 14 Oct.
  - 12 are served: AMQP, CICS, EDI, EJB, IBM i, LDAP, MDM, MQTT, OData, PDF, Redis, AI.
  - Example: Kafka 6.8.2.
  - The list is in `ISSUES.csv`.
  - If the AEM team says the cause differs from Streaming, split it out as its own sub-task instead.
- **DOCOPS-344:** add LDAP 7.3.0 `user-guide/ldap-palette/modifydn-entry.md` (empty article; 158 sentences, 6 pictures, 2 heading targets).
- **DOCOPS-351:** add the variant from section 5. A page whose first `toc.yml` row is a heading row elsewhere is placed and titled by that row, and its own row is dropped. 25 pages in 10 versions:
  - ActiveSpaces 4.10.0/4.10.1, AMX BPM 4.2.0 (12), BE 6.3.2, HL7 FHIR 8.5.0, SFTP 1.1.1, EMS 10.4.0/10.4.1, Hawk RedTail 6.3.1, iProcess Workspace 11.9.2.
- **DOCOPS-364:** add a note that Trillium 6.0.0's verify findings (97) clear with the K2 removal.

---

## 4. UAT sheet rows (CSV, paste-ready)

Columns are in the sheet's order. Screenshot and assignee are left empty. Before this triage, the sheet had no row for these three kinds. "Related issue #12" assumes the sheet numbers rows from the header as #1, as its existing cross-references do; that makes the Streaming row #12.

```csv
Type,Issue description,Issue screenshot,Category,Priority,Found In,Reporter,Status,Assignee,Stage Issue link,Prod Issue link,Comments,DEV status / comment
Desktop,"Online help for most BusinessWorks plug-ins is not on staging: 61 of the 73 newest plug-in versions return 404 for the version page, the menu, every topic and the product page, although the content is in GitHub (wip and main). Example: Apache Kafka 6.8.2. Staging URL: https://stg-docs.tibco.com/us/en/tibco-activematrix-businessworks-plug-in-for-apache-kafka/online-help/6-8-2/tibco-activematrix-businessworks-plug-apache-kafka.html Github URL: https://github.com/tibco/en-us-tib-bw-plugin-userdocs/blob/wip/en-us/tibco-activematrix-businessworks-plug-in-for-apache-kafka/online-help/6-8-2/tibco-activematrix-businessworks-plug-apache-kafka.md Served for comparison: AMQP 6.5.3, CICS, EDI, EJB, IBM i, LDAP, MDM, MQTT, OData, PDF, Redis, AI. Related issue #12",,Content,Critical,"BW plug-ins (61 versions), e.g. Apache Kafka 6.8.2",Mayur,New,,https://stg-docs.tibco.com/us/en/tibco-activematrix-businessworks-plug-in-for-apache-kafka/online-help/6-8-2/tibco-activematrix-businessworks-plug-apache-kafka.html,,"DOCOPS-346; 61 versions not served; list in reports/verify/ISSUES.csv",
Desktop,"A page is served with an empty article: only the title shows; none of the text, tables or pictures. Example: LDAP 7.3.0, ModifyDN Entry (158 sentences, 6 pictures missing). Staging URL: https://stg-docs.tibco.com/us/en/tibco-activematrix-businessworks-plug-in-for-ldap/online-help/7-3-0/user-guide/ldap-palette/modifydn-entry.html Github URL: https://github.com/tibco/en-us-tib-bw-plugin-userdocs/blob/wip/en-us/tibco-activematrix-businessworks-plug-in-for-ldap/online-help/7-3-0/user-guide/ldap-palette/modifydn-entry.md Also seen on EMS (Configuring the FTL Server Cluster), Scribe Online (Tools) and BusinessEvents (Domain Object Override Settings Reference).",,Content,High,"LDAP plug-in 7.3.0; EMS 10.4.x-10.5.x; Scribe Online; BusinessEvents 6.3.x",Mayur,New,,https://stg-docs.tibco.com/us/en/tibco-activematrix-businessworks-plug-in-for-ldap/online-help/7-3-0/user-guide/ldap-palette/modifydn-entry.html,,"DOCOPS-344; 4 pages, about 10 versions",
Desktop,"Pages listed in toc.yml under a heading row (a url with #) are missing from the left menu, together with the heading row. Example: EMS 10.4.0, Installation > Platform-Specific Instructions (installation.md#platform-specific-instructions) > Guidelines for macOS (installation/guidelines-for-macos.md) is not in the menu. Github URL: https://github.com/tibco/en-us-tib-ems-userdocs/blob/wip/en-us/tibco-enterprise-message-service/online-help/10-4-0/toc.yml (lines 29-35)",,Design,High,"TIBCO, 120 versions (EMS, FTL, BusinessEvents, others)",Mayur,New,,https://stg-docs.tibco.com/us/en/tibco-enterprise-message-service/online-help/10-4-0/installation/guidelines-for-macos.html,,"DOCOPS-351; 2,218 pages in 120 versions sit under heading rows",
Desktop,"A page whose first toc.yml row is a heading row of another branch (page.md#anchor) is shown once in the menu, at that row and under that row's title, and is served at that row's folder; its own row is dropped and its own path is 404. Example: BusinessEvents 6.3.2, Developers Guide > Mapping and Transforming Data > XPath Formula Builder For XPath 1.0 > Addressing Schema Elements is missing; the same page is shown as 'Mapping and Transforming Data to Function Input' under Mapping and Transforming Data. Served at: https://stg-docs.tibco.com/us/en/tibco-businessevents-enterprise-edition/online-help/6-3-2/developers-guide/mapping-and-transforming-data/xpath-formula-builder-for-xpath-2-0.html Expected (404): https://stg-docs.tibco.com/us/en/tibco-businessevents-enterprise-edition/online-help/6-3-2/developers-guide/mapping-and-transforming-data/xpath-formula-builder-for-xpath-1-0/xpath-formula-builder-for-xpath-2-0.html Github URL: https://github.com/tibco/en-us-tib-businessevents-userdocs/blob/wip/en-us/tibco-businessevents-enterprise-edition/online-help/6-3-2/toc.yml (lines 1841 and 1926)",,Design,Medium,"BusinessEvents 6.3.2 (25 pages in 10 versions)",Mayur,New,,https://stg-docs.tibco.com/us/en/tibco-businessevents-enterprise-edition/online-help/6-3-2/developers-guide/mapping-and-transforming-data/xpath-formula-builder-for-xpath-2-0.html,,"DOCOPS-351 (variant); 25 pages, 10 versions",
```

Rows not drafted:
- DOCOPS-347 (images): still "to trace", and its owner is not known yet.
- NEW-A and NEW-B: ours, not AEM's.

---

## 5. BusinessEvents 6.3.2: "Addressing Schema Elements" missing from the staging menu

**Verdict: AEM behaviour, triggered by our `toc.yml`. It is a variant of DOCOPS-351. `verify` is right.**

**Evidence:**

1. The report `reports/verify/tibco/tibco-businessevents-enterprise-edition/6.3.2-2026-11-12.csv`, row 588: the old topic `Developers/Addressing-Schema-Elements.htm` became `developers-guide/mapping-and-transforming-data/xpath-formula-builder-for-xpath-1-0/xpath-formula-builder-for-xpath-2-0.md`. Its `published_status` is `unmatched`: the menu has no row for it, so the page was never fetched.
2. That page is a merge of 9 topics (`merged_from: 9`). Its title is "Addressing Schema Elements". Its last section, at line 425, is "# Mapping and Transforming Data to Function Input", a topic that in the original menu sits in another branch.
3. `toc.yml` (published tree, read only):
   - Line 1841, under "Mapping and Transforming Data": `…/xpath-formula-builder-for-xpath-2-0.md#mapping-and-transforming-data-to-function-input`. This is the **first** row that opens the file.
   - Line 1926, under "XPath Formula Builder For XPath 1.0": `…/xpath-formula-builder-for-xpath-2-0.md`, titled "Addressing Schema Elements". This is the page's own row.
4. What staging serves (menu from the cached `…/developers-guide/mapping-and-transforming-data.html`):
   - Under "Mapping and Transforming Data", the menu shows **"Mapping and Transforming Data to Function Input" → `…/mapping-and-transforming-data/xpath-formula-builder-for-xpath-2-0.html`**.
   - "XPath Formula Builder For XPath 1.0" has no children, so "Addressing Schema Elements" is gone.
   - WebFetch today: `…/mapping-and-transforming-data/xpath-formula-builder-for-xpath-2-0.html` is served (h1 "Addressing Schema Elements", full article). The page's own path `…/xpath-formula-builder-for-xpath-1-0/xpath-formula-builder-for-xpath-2-0.html` is **404**.
5. **How AEM behaves here:** it places each page **once**, at the first `toc.yml` row that refers to the file, even when that row is a heading row (`#anchor`). It uses that row's title and that row's folder for the URL, and it ignores the page's own row later on.
   - DOCOPS-351 is the same family: AEM decides menu placement from heading rows.
   - The DOCOPS-351 fix options cover it too. Either AEM keys the menu on page rows only, or we make sure each page's own row comes before any of its heading rows. A third option for us is not to merge a topic from another menu branch into a page.
6. **Spread** (scan of every `toc.yml` on `wip`, read only): 25 pages in 10 versions have a heading row before their own row.
   - AMX BPM 4.2.0 (12), Hawk RedTail 6.3.1 (3), ActiveSpaces 4.10.0/4.10.1 (2 each), BE 6.3.2, HL7 FHIR 8.5.0, SFTP 1.1.1, EMS 10.4.0/10.4.1, iProcess Workspace 11.9.2.
   - The EMS pair is the Appendix B case, already `accepted` as crosswise.

**Triage entry:** the `DOCOPS-351` entry in section 2 (code `VERIFY_PUBLISHED_TOC_ENTRY_MISSING`, version 6.3.2, path `*Addressing Schema Elements`). With it, BE 6.3.2 reads `logged`.

---

## 6. Open questions

1. **DOCOPS-346: widen it or open a new issue?** Streaming has its own cause (the help is tied to the product build, and it waits for R3). The BW plug-in cause is unknown: some products are served and some are not, with identical repo content. If the AEM team names a different cause, split it into a new Digital Platform sub-task. The proposal widens 346 to keep the number of new issues down.
2. **Draft comments are published (source).** Writers' draft comments ("Draft comments:", "<draft>:", "Self notes:") appear in the original help and therefore in our Markdown. A scan of `wip` finds them in 16 versions across 7 families:
   - BPM Enterprise 5.6.0–5.7.0; BW Confidentiality 6.1.1; MDM 9.3.2, MDM Studio 6.0.0, GDS add-on 4.0.0; Foresight Transaction Insight 5.4.0; iProcess Engine 11.9.1–11.10.0; Mainframe RED 3.1.0 x2; MFT Platform Server UNIX 8.1.1/8.1.2 and z/Linux 8.1.0/8.1.1.
   - The Flare CSS marks `div.draft-comment` as hidden text that was not excluded at build.
   - Should the converter drop `div.draft-comment` and `span.draft-comment`? That would be a TechDocs decision and one more sub-task. As proposed, it is triaged `source`.
3. **DOCOPS-271 is Done in Jira**, but the triage file still uses it as the `logged` ticket for `REDIRECT_MAP_MISSING`, which covers 16 versions including BW plug-ins. Should those findings move to a live issue?
4. **Siebel 7.3.0 home page.** The landing banner is lost, and Siebel is the only BW version whose `toc.yml` lists `home.md`. Accept it, or have NEW-A re-convert it?
5. **NEW-A's re-convert** depends on the claim that today's reader reads those TOCs. I tested this on 3 `ent_html.js` files (unmatched 0, ragged 0) but did not test a conversion run. Batch 1b replaced the packages, so the original packages could have differed.
6. **Triage cannot match an empty `path`**: `triage.load` turns `""` into `*`. The broad BW `PAGE_MISSING` entry would therefore also excuse a future page-level 404 on a served BW plug-in. A small change could fix this: let `path: ""` mean the version itself.
7. **UAT row numbering:** check that the Streaming row is #12 before pasting "Related issue #12".
