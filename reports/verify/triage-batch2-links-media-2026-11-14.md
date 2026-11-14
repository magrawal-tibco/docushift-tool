# Verify triage: Batch 2, links and media (redirects, pictures, anchors), 2026-11-14

This is a read-only triage: nothing in the repo was edited, run or logged. The data is each version's latest stored findings in `cache/state.db` for the 97 Batch 2 versions (runs from 2026-11-13T13:27 UTC), with the current `config/verify-triage.yaml` applied. It is checked against the published Markdown in `C:/github/tibco-docs-aem`, the staging pages `verify` cached in `cache/verify/`, the extracted source packages under `families/*/extracted/`, and a few staging pages and pictures fetched today. Another agent covers pages, text and menus.

**Scope (my kinds, before triage):**
- 67 versions have at least one finding of my kinds; 26 of them have unlogged ones (2,045 findings).
- The big unlogged groups are `REDIRECT_UNMAPPED` (1,253, 3 versions) and `PUBLISHED_ANCHOR_MISSING` (769, 21 versions).
- Already logged by catch-all entries: `REDIRECT_MAP_MISSING` (28 versions → DOCOPS-322), `PUBLISHED_IMAGE_BROKEN` (1,911 → DOCOPS-347), `PUBLISHED_ANCHOR_DIFFERS` (1,288 in 46 versions → DOCOPS-345) and `PUBLISHED_ALT_DROPPED` (9 → DOCOPS-255).

**Simulated result.** I applied the entries in section 3 in memory, with no file written:
- Every finding of my kinds is triaged: 0 left unlogged (2,045 before).
- All 67 versions read `logged` for my kinds (41 before).
- Overall, other kinds included: **6 versions go `lost` → `logged`**: API Exchange Gateway 2.5.1, BC Trading Community Management 6.2.0, Foresight ARS 6.0.0, iProcess Technology Plug-ins 11.10.0, and both Product and Service Inventory 2.1.0 slugs.
- **2 go `lost` → `issues`**: iProcess Engine 11.10.0 and Rendezvous 9.0.0. They keep `TEXT_DIFF` warnings, which are the other agent's.
- The other 18 still have findings in the other agent's kinds.

**Three things to know first:**
1. **Most anchor and picture losses are one AEM problem.** Staging serves **92 pages in 15 versions with an empty article** (DOCOPS-344). This accounts for:
   - 747 of the 769 unlogged anchors;
   - 666 of the 1,911 broken pictures.

   The Markdown of these pages is ordinary.
2. **Pictures in a folder whose name has a dot are 404 on staging.** This covers 777 findings, every web-format 404 in the batch: Foresight's `tib_translator_4.1_installation/`, `archivsystems_6.0.0/`, and BC cXML's `TIB_bccxml_6.1.0_installation/`. The file is in the repo and the page links the right DAM path, but DAM answers 404.
   - Also 404: 124 pictures in formats browsers do not show (`.wmf`, `.emf`, `.bmp`, `.dib`). This is ours, and the fix is to convert them.
3. **Batch 2 reused cached staging pages for 4 versions.** `verify` was run without `--refresh`, so these versions were checked against pages fetched before Batch 2:
   - FTL 7.3.0 and eFTL 7.3.0, fetched 11 Nov;
   - Scribe Online, fetched 12 Nov;
   - Cloud API Modeler 1.5.0, fetched 13 Nov 02:52.

   FTL 7.3.0's 89 broken pictures are stale. On 11 Nov staging wrote page-relative picture URLs. Today the same page serves the DAM path, checked on `getting-started/.../samples-for-the-content-matching-model.html`. Re-checks need `--refresh`.

---

## 1. Summary table

| # | Kind (plain words) | Codes | Versions / findings | Verdict | Jira | Owner |
|---|---|---|---|---|---|---|
| L1 | **No redirect file (301.yml) for the version.** 25 of the 28 are not in the docsite sitemap, and no URL pattern is declared for them. 24 of those 25 are already rows in `reports/origin-url-requests.csv`; Silver Fabric Enabler 1.2.0 is not. Foresight Translator 4.2.0: the sitemap has no page list for 4.2.0. Platform 1.1.0 and Platform CLI 1.2.0: the sitemap entry they matched is Control Plane's (`platform-cp/1.21.0`, `1.11.0`), so 0 topics placed. Mostly adapters, BusinessConnect and General. | `REDIRECT_MAP_MISSING` | 28 / 28 | existing issue (already `logged`; the reason needs rewriting) | DOCOPS-322 | TechDocs |
| L2 | **The 301.yml has document rows only, no page rows.** Activation Service 1.1.0: 32 of 36 topics placed, under the threshold. BC 7.5.0 and BC TCM 6.2.0: the old site serves each help **twice** (`doc/bcgs/` + `doc/bcis/`, `doc/bctcm/` + `doc/webclient/`). The derivation ties 507/507 and 107/107, and one declared template would cover only one folder. All three are rows in the URL request sheet. | `REDIRECT_UNMAPPED` | 3 / 1,253 | existing issue | DOCOPS-322 | TechDocs |
| L3 | **Redirect targets not served: ActiveSpaces 5.2.0 is not on staging** (the menu and topics are 404), although it is on `wip` and `main`. | `REDIRECT_UNSERVED` | 1 / 9 | existing issue (same as its `PUBLISHED_PAGE_MISSING`) | DOCOPS-346 | Digital Platform |
| P1 | **Pictures and headings on pages served with an empty article.** Staging shows the title and chrome only. | `PUBLISHED_IMAGE_BROKEN` "not on the served page", `PUBLISHED_ANCHOR_MISSING` | 15 / 666 + 747 (92 pages) | existing issue, platform | DOCOPS-344 | Digital Platform |
| P2 | **Pictures in a folder whose name contains a dot are 404 in DAM.** Every web-format 404 in the batch is one. In the same versions, pictures in other folders are served. | `PUBLISHED_IMAGE_BROKEN` "HTTP 404" | 6 / 777 | platform (we could rename the folders) | DOCOPS-347 | Digital Platform |
| P3 | **Pictures in formats browsers do not show** (`.wmf`, `.emf`, `.bmp`, `.dib`). DAM answers 404, and even if served most would not render. | `PUBLISHED_IMAGE_BROKEN` "HTTP 404" | 6 / 124 | ours (convert to PNG) | DOCOPS-347 | TechDocs |
| P4 | **Picture links AEM did not resolve.** On one page per version, every picture gets a page-relative `src` (`/content/tibco/.../<page>/<file>`, 404), while the DAM copy is served (200). Thumbnails (`*_thumb_0_0.*`) get `src=""`. File names with spaces get `placeholder.png`. | `PUBLISHED_IMAGE_BROKEN` "not on the served page" | 9 / 197 | platform | DOCOPS-347 | Digital Platform |
| P5 | **Stale comparisons:** pages served from an older copy, or read from `verify`'s cache. Transaction Insight 6.0.0 serves the 14 Oct asset names, not the 30 Oct re-publish. FTL 7.3.0 and Scribe were read from the 11 and 12 Nov cache. | `PUBLISHED_IMAGE_BROKEN` | 3 / 136 | checker / timing: re-check with `--refresh` | DOCOPS-347 (as now) | TechDocs |
| P6 | **SVG served with other bytes** (API Exchange Gateway 2.5.1, Offer and Price Engine 6.0.0), as on EMS. | `PUBLISHED_IMAGE_BROKEN` | 2 / 9 | existing issue | DOCOPS-347 | Digital Platform |
| P7 | **Pictures dropped by unusual source markup:** a screenshot in a `<p>` directly inside `<ul>` (Control Plane 1.20.0, Platform 1.1.0, Platform CLI 1.2.0); an icon inside `<code><code>` (EDISIM 6.21.0); a thumbnail path with the wrong case and depth (HIPAA Validator Desktop 9.2.0). | `IMAGE_MISSING` 13, `PUBLISHED_IMAGE_BROKEN` 1 | 5 / 14 | ours, new | **NEW-C** | TechDocs |
| P8 | **A decorative "add" icon in a menu path** (BC Container Edition 1.7.1). | `IMAGE_MISSING` | 1 / 1 | accepted (as Kafka 6.8.2) | none | none |
| P9 | **Alt text not served.** 9 findings, all already on DOCOPS-255. New variants: an alt text spanning lines in raw HTML (Adapter Framework 1.6.1); `\*` (HIPAA 9.2.0). | `PUBLISHED_ALT_DROPPED` | 4 / 9 | existing issue | DOCOPS-255 | Digital Platform |
| A1 | **Links to headings with code written as dashes** (`#generating-the-----------------file-using-the------------utility`). | `PUBLISHED_ANCHOR_MISSING` | 3 / 3 | pending fix (built 12 Nov; applied so far only to Flogo PAYG and BE) | DOCOPS-362 | TechDocs |
| A2 | **Heading id with `_` written as `-`** (`#error-messages-in-the-swdirlogssw_warn-file`; staging has `...sw-warn-file`). Not paired because the heading text also differs (backslashes). | `PUBLISHED_ANCHOR_MISSING` | 3 / 3 | existing issue, platform | DOCOPS-345 | Digital Platform |
| A3 | **The source links to a bookmark no source page defines:** `#Manually`, `#Linking`, `#Configur`, `#Running`, `#Packet`, `#Generate2`, `#Listener2`, `#_Ref292373532`, `#_bookmark11/12`, `#pm_intro_…`, `#rv_install_…`. Checked in the extracted packages. | `PUBLISHED_ANCHOR_MISSING` | 9 / 16 | source | none | none |
| A4 | **Heading ids differ on staging.** Already logged, nothing new. | `PUBLISHED_ANCHOR_DIFFERS` | 46 / 1,288 | existing issue | DOCOPS-345 | Digital Platform |

The `IMAGE_BROKEN` totals add up to 1,911. P1–P6 hold 1,909. The other 2 are the HIPAA thumbnail (P7) and one GUID picture on a partly served Mainframe TCP Library 3.0.0 page. That page also has a `TEXT_DIFF`, which is the other agent's; the picture is left under DOCOPS-347.

**A defect in the triage file.** The DOCOPS-347 catch-all (`IMAGE_BROKEN`, no scope) and the DOCOPS-348 catch-all (`TEXT_DIFF`) sit **above** the Scribe and BusinessEvents DOCOPS-344 entries. The first matching entry wins, so those entries never apply. Scribe `connector-extensions/tools.md` reads DOCOPS-347 today, not 344. Move both catch-alls to the end of the file.

---

## 2. Evidence

Repos: `C:/github/tibco-docs-aem/<repo>/en-us/<slug>/online-help/<version>/`. Staging: `https://stg-docs.tibco.com/us/en/<slug>/online-help/<version>/…`.

### Redirects (L1–L3)

- **L1, Adapter Code for API Exchange and Joomla 2.3.4.**
  - `en-us-tib-adapters-userdocs/en-us/adapter-code-for-tibco-api-exchange-and-joomla/online-help/2-3-4/` has no `301.yml`.
  - `cache/coveo/manifest.json` lists no product file for the slug.
  - `config/origin-urls.yaml` declares 3 products only.
  - `reports/origin-url-requests.csv` row 2 asks for the pattern ("not in docsite sitemap").
  - The same holds for 24 of the 28 versions.
- **L1, Platform 1.1.0 and Platform CLI 1.2.0.**
  - Their sitemap page lists are Control Plane's: `https://docs.tibco.com/pub/platform-cp/1.21.0/doc/html/...` and `.../platform-cp/1.11.0/...`.
  - So `reframe` wrote `ORIGIN_TEMPLATE_UNDECLARED` ("0 of 583 topics placed", run 2088), and `sync` wrote `SYNC_ORIGIN_NO_PAGE_ROWS` (run 2101).
  - The request sheet's note for the CLI says it "is part of the tibco control plane", so its old URLs may be Control Plane's own. That needs a decision under DOCOPS-322.
  - Platform 1.1.0 and Silver Fabric Enabler 1.2.0 (`_status` not-selected, but published) are not in the request sheet.
- **L2, BusinessConnect 7.5.0.**
  - `.../tibco-businessconnect/online-help/7-5-0/301.yml` has 9 rows, all documents.
  - The 1,014 findings split evenly: `pub/bc/7.5.0/doc/bcgs/html/` 507 and `doc/bcis/html/` 507, the same 507 topics.
  - `origins.derive` on today's sitemap returns no template (507 hits, rival 507).
  - Request sheet row 54 suggests `.../doc/html/...` (wrong, `suggestion_ok` = no). The live URL is `.../doc/bcis/html/...`.
- **L2, Activation Service 1.1.0.** `reframe` run 1742: "32 of 36 topics placed, … none is declared". Derived on the 25 unmapped topics alone, the template is `https://docs.tibco.com/pub/tibco-activation/1.1.0/doc/{path}`, drop 1.
- **L3, ActiveSpaces 5.2.0.**
  - `…/tibco-activespaces-enterprise-edition/online-help/5-2-0/installation/product-overview.html` is 404 (WebFetch today).
  - The version is in `origin/wip` (last commit `8edf6dd`, 5 Nov) and in `origin/main`.

### Pictures (P1–P9)

- **P2, Foresight Translator 4.2.0, `installation/before-installing.md`.**
  - Line 51: `![](../resources/images/tib_translator_4.1_installation/Installation_Overview.png)`. The file is in the repo (commit `ba30375`, 14 Oct).
  - Staging links `/content/dam/tibco/us/en/tibco-foresight-translator/online-help/4-2-0/resources/images/tib_translator_4.1_installation/Installation_Overview.png`, which is 404 (WebFetch today).
  - In this version, all 254 picture 404s are in dot folders, and none of the 365 pictures outside them failed.
  - Across the batch: 777 of 777 web-format 404s are in dot folders. The Batch 2 repos hold about 1,300 pictures in them (8 versions, counting two not checked on staging).
- **P3, BusinessConnect 7.5.0, `concepts/introduction.md`.**
  - The page links `images/BCdeploy1.wmf` and 3 more `.wmf`.
  - Staging links `/content/dam/.../7-5-0/concepts/images/BCdeploy1.wmf`, which is 404.
  - The same in iProcess Workspace (Windows) 11.10.0: 44 `.bmp` toolbar icons, e.g. `managers-guide/images/t_audit_22x21.bmp`.
- **P4, Order Management 6.1.0, `user-guide/order-management-system-user-interface/dashboard.md`.**
  - The Markdown has `![](../images/UI-autoRefresh.png)`.
  - Staging links `/content/tibco/us/en/tibco-order-management/online-help/6-1-0/user-guide/order-management-system-user-interface/dashboard/UI-autoRefresh.png`, which is 404.
  - `/content/dam/tibco/us/en/tibco-order-management/online-help/6-1-0/user-guide/images/UI-autoRefresh.png` is 200 (both checked today).
  - All 58 pictures on that page are affected; the version's other pages use DAM paths.
  - The same on one page each of Control Plane 1.20.0, Translator 4.2.0, iProcess Engine 11.10.0 and Workspace 11.10.0.
  - Thumbnails `src=""`: Hawk Database Adapter 6.2.1 `users-guide/using-methods-in-a-rulebase/overview.md`; Reward 22.3.0, 4 pages.
  - Spaces: BC cXML 6.1.0 `bwproj-search%20project.gif` is served as `https://stg-docs.tibco.com/content/dam/placeholder.png`.
- **P1, Rendezvous 9.0.0, `concepts/the-rendezvous-daemon.md`** (627 lines, merged from 10 topics). The served `topic-renderer__content` holds the navigation, the PDF and feedback widgets, and no article text and no heading. Flogo 3.0.1 `user-guide/deployment-and-configuration/environment-variables.md` (267 lines, 2 raw HTML tables, nothing unusual) is served at 1.2%.
- **P5, Transaction Insight 6.0.0, `.../ars-types.md`.**
  - Staging still serves `Foresight_Archive_and_Retrieval_System_Workflow_Considerations.jpg` (the 14 Oct name, still on `origin/main`).
  - The repo on `wip` has `..._Workflow_Cons-e5bcb583.jpg` (re-publish `b7e48e7`, 30 Oct). So staging has not picked up Foresight's R1 push.
- **P7, Control Plane 1.20.0.** Source `Subsystems/bwce-capability/bwce-user-guide/developer-hub.htm` has `</ul> <ul> <p> <img src="images/Import-Window.png" class="screenshot" /> </p> <li>`. The Markdown page `managing-capabilities/tibco-businessworks-6-containers/monitoring-tibco-businessworks6-containers.md` has no screenshot there.
- **P7, HIPAA Validator Desktop 9.2.0, `business-rules/business-rules-reference/list-business-rules.md` line 63.**
  - The line is `[![](../Resources/Images/BusinessRules/inlist_thumb_0_0.jpg)](../../resources/images/businessrules/inlist.png)`.
  - The file is `resources/images/businessrules/InList_thumb_0_0.jpg`, one folder higher and in another case. It is the only such line in the Foresight repo.
- **P7, EDISIM 6.21.0.** Source `<code><code><img src="../Resources/Images/FStdg/Step_1_Building_a_New_Message_Set_Model_1.png" />…</code></code>This element is to be excluded…`. The Markdown keeps the sentence without the icon.

### Anchors (A1–A3)

- **A1:** Control Plane 1.20.0 and Platform CLI 1.2.0, `.../building-deploying-tibco-businessworks6.md#generating-the-----------------file-using-the------------utility`. Flogo VS Code 1.3.5, `.../mapping-data-by-using-if-else-conditions.md#mapping-data-by-using-----------conditions`.
- **A2, iProcess Workspace (Windows) 11.10.0, `user-guide-tibco-iprocess-script-plug-in.md`.**
  - Line 292: `#### Error Messages in the *SWDIR*\\logs\\sw_warn File`.
  - The cached staging page has `id="error-messages-in-the-swdirlogssw-warn-file"`; our link is `#…swdirlogssw_warn-file`.
- **A3, Order Management 6.1.0, `.../authorization-service/create-user.md` line 358.**
  - The line is `- [Generate OAuth token](#Generate2)`.
  - The source `generating-an-author.htm` links `#Generate2`, and none of the 5 source topics merged into the page defines it.
  - The same check holds for the 15 other A3 findings.

---

## 3. Proposed `config/verify-triage.yaml` entries

Steps:

1. **Move** the two catch-alls, `VERIFY_PUBLISHED_IMAGE_BROKEN` → DOCOPS-347 and `VERIFY_PUBLISHED_TEXT_DIFF` → DOCOPS-348, to the **end** of the file. Then the existing Scribe and BE DOCOPS-344 entries apply, and so do the ones below.
2. **Replace** the reason of the existing `VERIFY_REDIRECT_MAP_MISSING` entry, and of the DOCOPS-347 catch-all, with the texts in 3a.
3. **Insert** block 3b, then the generated page list 3c, before the moved catch-alls.

`DOCOPS-NEW-C` is a placeholder for the new sub-task's key.

### 3a. Reason updates for existing entries

```yaml
  - code: VERIFY_REDIRECT_MAP_MISSING
    decision: logged
    ticket: DOCOPS-322
    reason: >-
      No 301.yml can be built: the docsite sitemap has no page list for the version and no URL
      pattern is declared in config/origin-urls.yaml (25 of Batch 2's 28; the requests are in
      reports/origin-url-requests.csv), or the list it has does not fit (Foresight Translator
      4.2.0 not listed; Platform 1.1.0 and Platform CLI 1.2.0 matched to Control Plane's lists).
      Traced 2026-11-14.

  - code: VERIFY_PUBLISHED_IMAGE_BROKEN
    decision: logged
    ticket: DOCOPS-347
    reason: >-
      A picture not served: DAM answers 404 for folders whose name has a dot and for .wmf, .emf,
      .bmp, .dib; on some pages AEM writes a page-relative src, an empty src (thumbnails) or
      placeholder.png (spaces in the name); SVGs served with other bytes (EMS, API Exchange).
      Traced on Batch 2, 2026-11-14. Keep last in the file.
```

### 3b. New entries

```yaml
  # Batch 2 (13 Nov), links and media (triage 2026-11-14). Narrow entries first: insert this
  # block before the DOCOPS-347 / DOCOPS-348 catch-alls, then the generated DOCOPS-344 page list.

  # Redirects.
  - code: VERIFY_REDIRECT_UNMAPPED
    decision: logged
    ticket: DOCOPS-322
    slug: tibco-activation-service
    version: "1.1.0"
    reason: >-
      The sitemap places 32 of 36 topics under /pub/tibco-activation/1.1.0/doc/, under the
      derivation's threshold, so 301.yml holds only the 4 document rows. Needs the declared
      pattern (URL request sheet, row 4).
  - code: VERIFY_REDIRECT_UNMAPPED
    decision: logged
    ticket: DOCOPS-322
    slug: tibco-businessconnect
    version: "7.5.0"
    reason: >-
      The old site serves this help twice, under doc/bcgs/html/ and doc/bcis/html/ (507 pages
      each); the derivation ties and writes no page row. One declared template covers one
      folder; both need rows.
  - code: VERIFY_REDIRECT_UNMAPPED
    decision: logged
    ticket: DOCOPS-322
    slug: tibco-businessconnect-trading-community-management
    version: "6.2.0"
    reason: >-
      The same two-folder case: doc/bctcm/html/ and doc/webclient/html/ (107 pages each).
  - code: VERIFY_REDIRECT_UNSERVED
    decision: logged
    ticket: DOCOPS-346
    slug: tibco-activespaces-enterprise-edition
    version: "5.2.0"
    reason: >-
      ActiveSpaces 5.2.0 is not served on staging (menu, version page and topics 404) although
      it is on wip and main; the sampled 301 targets fail with it.

  # Pictures dropped by unusual source markup (NEW-C).
  - code: VERIFY_IMAGE_MISSING
    decision: logged
    ticket: DOCOPS-NEW-C
    slug: tibco-platform
    version: "1.1.0"
    path: "managing-capabilities/tibco-businessworks-6-containers/monitoring-tibco-businessworks6-containers.md"
    reason: &p-in-ul >-
      The Import Projects screenshot sits in a <p> placed directly inside <ul> in the source
      (developer-hub.htm); the converter drops it. Control Plane 1.20.0, Platform 1.1.0, Platform CLI 1.2.0.
  - code: VERIFY_IMAGE_MISSING
    decision: logged
    ticket: DOCOPS-NEW-C
    slug: tibco-control-plane
    version: "1.20.0"
    path: "managing-capabilities/tibco-businessworks-6-containers/monitoring-tibco-businessworks6-containers.md"
    reason: *p-in-ul
  - {code: VERIFY_IMAGE_MISSING, decision: logged, ticket: DOCOPS-NEW-C, slug: tibco-platform-command-line-interface, version: "1.2.0", path: "managing-capabilities/tibco-businessworks-6-containers/monitoring-tibco-businessworks6-containers.md", reason: *p-in-ul}
  - code: VERIFY_IMAGE_MISSING
    decision: logged
    ticket: DOCOPS-NEW-C
    slug: tibco-foresight-edisim
    version: "6.21.0"
    path: "test-data-generator-user-guide/tdg-tutorial/steps-in-creating-test-data/step-1-building-a-new-message-set-model.md"
    reason: >-
      The "excluded" icon is an <img> inside <code><code> in the source; the converter drops it,
      leaving "This element is to be excluded from the test data." with no icon.
  - code: VERIFY_IMAGE_MISSING
    decision: logged
    ticket: DOCOPS-NEW-C
    slug: tibco-foresight-hipaa-validator-desktop
    version: "9.2.0"
    path: "business-rules/business-rules-reference/list-business-rules.md"
    reason: &case-path >-
      The thumbnail is written as ../Resources/Images/BusinessRules/inlist_thumb_0_0.jpg; the
      file is resources/images/businessrules/InList_thumb_0_0.jpg, one folder up. The old site
      ignored case; AEM does not.
  - code: VERIFY_PUBLISHED_IMAGE_BROKEN
    decision: logged
    ticket: DOCOPS-NEW-C
    slug: tibco-foresight-hipaa-validator-desktop
    version: "9.2.0"
    path: "business-rules/business-rules-reference/list-business-rules.md"
    reason: *case-path
  - code: VERIFY_IMAGE_MISSING
    decision: accepted
    slug: tibco-businessconnect-container-edition
    version: "1.7.1"
    path: trading-partner-management/sshftp-transport.md
    reason: >-
      A decorative 18x18 "add" icon inside the menu path "Transport > Add Outbound Transport" is
      dropped; the words carry the meaning (as for Kafka 6.8.2).

  # Anchors.
  - code: VERIFY_PUBLISHED_ANCHOR_MISSING
    decision: logged
    ticket: DOCOPS-362
    slug: tibco-platform-command-line-interface
    version: "1.2.0"
    path: "*#*-----*"
    reason: &code-dashes >-
      Link to a heading with code written as dashes (fix built 12 Nov, applied so far to
      Flogo PAYG and BE only). Control Plane 1.20.0, Platform CLI 1.2.0, Flogo VS Code 1.3.5.
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-362, slug: tibco-control-plane, version: "1.20.0", path: "*#*-----*", reason: *code-dashes}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-362, slug: tibco-flogo-extension-for-visual-studio-code, version: "1.3.5", path: "*#*-----*", reason: *code-dashes}
  - code: VERIFY_PUBLISHED_ANCHOR_MISSING
    decision: logged
    ticket: DOCOPS-345
    slug: "tibco-iprocess-*"
    version: "11.10.0"
    path: "*#error-messages-in-the-swdirlogssw_warn-file"
    reason: >-
      Staging writes the heading "Error Messages in the SWDIR\logs\sw_warn File" as
      #error-messages-in-the-swdirlogssw-warn-file (`_` as `-`, AEM's rule); verify does not pair
      it because the heading text differs too (backslashes, DOCOPS-360).

  # The source page links to a bookmark no source page defines; broken on the old site too.
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: source, slug: tibco-platform-command-line-interface, version: "1.2.0", path: "*/tibco-developer-hub-overview/integrations.md#[ML]*", reason: &no-bookmark "The source page links to a bookmark that no source page defines (#Manually, #Linking, #Configur, #Running, #Packet, #Generate2, #Listener2, Word _Ref/_bookmark ids); broken on the old site too. Checked 2026-11-14."}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: source, slug: tibco-control-plane, version: "1.20.0", path: "*/tibco-developer-hub-overview/integrations.md#[ML]*", reason: *no-bookmark}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: source, slug: tibco-flogo, version: "3.0.1", path: "*/about-tibco-flogo-flow-state-manager.md#Configur", reason: *no-bookmark}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: source, slug: tibco-foresight-transaction-insight, version: "6.0.0", path: "*/ti-ems-queue-reader.md#_Ref292373532", reason: *no-bookmark}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: source, slug: tibco-foresight-translator, version: "4.2.0", path: "installation/windows-installation-steps.md#_bookmark1?", reason: *no-bookmark}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: source, slug: tibco-iprocess-workspace-windows, version: "11.10.0", path: "*/procedure-objects.md#pm_intro_2170742793_locked_object_handling", reason: *no-bookmark}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: source, slug: tibco-operational-intelligence-hawk-redtail, version: "7.5.0", path: "*/troubleshooting-for-container-components.md#Running", reason: *no-bookmark}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: source, slug: tibco-operational-intelligence-hawk-redtail, version: "7.5.0", path: "*/starting-tibco-oi-hawk-redtail-services.md#Manually", reason: *no-bookmark}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: source, slug: tibco-operational-intelligence-hawk-redtail, version: "7.5.0", path: "*/uninstalling-tibco-oi-hawk-redtail.md#Packet", reason: *no-bookmark}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: source, slug: tibco-order-management, version: "6.1.0", path: "*/create-user*.md#Generate2", reason: *no-bookmark}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: source, slug: tibco-order-management, version: "6.1.0", path: "*/design-and-implementation.md#Listener2", reason: *no-bookmark}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: source, slug: tibco-rendezvous, version: "9.0.0", path: "installation.md#rv_install_2928680826_33603921", reason: *no-bookmark}
```

### 3c. Generated: DOCOPS-344 pages (92 pages, 15 versions, 144 entries)

These pages are served with an empty article, below 25% of their text; the measured range is 1.1–21.9%. Each entry names one page, so a new loss on any other page still shows. The other agent's `PUBLISHED_TEXT_DIFF` entries for DOCOPS-344 should use the same page list.

<details><summary>144 one-line entries</summary>

```yaml
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-api-exchange-gateway, version: "2.5.1", path: "user-guide/overview-of-security-policies/authentication-using-file-based-identity-store.md#*", reason: &empty-article "Staging serves the page with an empty article (DOCOPS-344); its headings and pictures are not there."}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-control-plane, version: "1.20.0", path: "managing-capabilities/tibco-flogo/managing-tibco-flogo-apps/app-configuration-management/consul.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-flogo, version: "3.0.1", path: "connectors-user-guide/supported-flogo-connectors/microsoft-sql-server/creating-a-microsoft-sql-server-connection.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-flogo, version: "3.0.1", path: "connectors-user-guide/supported-flogo-connectors/websocket.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-flogo, version: "3.0.1", path: "connectors-user-guide/supported-flogo-connectors/websocket.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-flogo, version: "3.0.1", path: "user-guide/deployment-and-configuration/app-configuration-management/app-configuration-management/consul.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-flogo, version: "3.0.1", path: "user-guide/deployment-and-configuration/environment-variables.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-flogo, version: "3.0.1", path: "user-guide/designing-flogo-applications-flogo-extension/general-category-triggers-activities-connections/activities/configurehttpresponse.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-flogo, version: "3.0.1", path: "user-guide/designing-flogo-applications-flogo-extension/general-category-triggers-activities-connections/activities/configurehttpresponse.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-flogo-extension-for-visual-studio-code, version: "1.3.5", path: "supported-flogo-connectors/amazon-kinesis.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-flogo-extension-for-visual-studio-code, version: "1.3.5", path: "supported-flogo-connectors/amazon-s3/creating-an-amazon-s3-connection.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-flogo-extension-for-visual-studio-code, version: "1.3.5", path: "supported-flogo-connectors/amazon-sns.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-flogo-extension-for-visual-studio-code, version: "1.3.5", path: "supported-flogo-connectors/microsoft-sql-server/creating-a-microsoft-sql-server-connection.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-flogo-extension-for-visual-studio-code, version: "1.3.5", path: "supported-flogo-connectors/tibco-eftl.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-flogo-extension-for-visual-studio-code, version: "1.3.5", path: "supported-flogo-connectors/websocket.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-flogo-extension-for-visual-studio-code, version: "1.3.5", path: "supported-flogo-connectors/websocket.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-flogo-extension-for-visual-studio-code, version: "1.3.5", path: "user-guide/app-configuration-management/consul.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-flogo-extension-for-visual-studio-code, version: "1.3.5", path: "user-guide/app-development/general-category-triggers-activities-connections/activities/configurehttpresponse.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-flogo-extension-for-visual-studio-code, version: "1.3.5", path: "user-guide/app-development/general-category-triggers-activities-connections/activities/configurehttpresponse.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-flogo-extension-for-visual-studio-code, version: "1.3.5", path: "user-guide/app-development/unit-testing/creating-and-running-a-test-case.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-flogo-extension-for-visual-studio-code, version: "1.3.5", path: "user-guide/app-development/unit-testing/creating-and-running-a-test-case.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-archive-and-retrieval-system, version: "6.0.0", path: "administration-guide/appendix-a-filtering-technical-details.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-archive-and-retrieval-system, version: "6.0.0", path: "administration-guide/appendix-a-filtering-technical-details.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-archive-and-retrieval-system, version: "6.0.0", path: "administration-guide/appendix-b-tibco-foresight-archive-retrieval.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-archive-and-retrieval-system, version: "6.0.0", path: "administration-guide/appendix-b-tibco-foresight-archive-retrieval.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-archive-and-retrieval-system, version: "6.0.0", path: "administration-guide/introduction.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-archive-and-retrieval-system, version: "6.0.0", path: "administration-guide/introduction.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-archive-and-retrieval-system, version: "6.0.0", path: "user-guide/page-details/common-elements.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-archive-and-retrieval-system, version: "6.0.0", path: "user-guide/page-details/common-elements.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-archive-and-retrieval-system, version: "6.0.0", path: "user-guide/page-details/viewing-data.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-archive-and-retrieval-system, version: "6.0.0", path: "user-guide/page-details/viewing-data.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-hipaa-validator-desktop, version: "9.2.0", path: "using-flat-files/introduction.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-hipaa-validator-desktop, version: "9.2.0", path: "using-flat-files/introduction.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-hipaa-validator-desktop, version: "9.2.0", path: "using-xml/introduction.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-hipaa-validator-desktop, version: "9.2.0", path: "using-xml/introduction.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-hipaa-validator-desktop, version: "9.2.0", path: "using-xml/printing-dtds-and-schemas.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-hipaa-validator-desktop, version: "9.2.0", path: "using-xml/printing-dtds-and-schemas.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-hipaa-validator-desktop, version: "9.2.0", path: "using-xml/using-standards-editor-with-schemas-and-dtds/editing-a-schema-or-dtd.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-hipaa-validator-desktop, version: "9.2.0", path: "using-xml/using-standards-editor-with-schemas-and-dtds/editing-a-schema-or-dtd.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-hipaa-validator-desktop, version: "9.2.0", path: "using-xml/using-standards-editor-with-schemas-and-dtds/opening-a-schema-or-dtd.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-hipaa-validator-desktop, version: "9.2.0", path: "using-xml/using-standards-editor-with-schemas-and-dtds/opening-a-schema-or-dtd.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-transaction-insight, version: "6.0.0", path: "tibco-foresight-archive-and-retrieval-system/archive-and-retrieval-system-administration-guide/appendix-a-filtering-technical-details.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-transaction-insight, version: "6.0.0", path: "tibco-foresight-archive-and-retrieval-system/archive-and-retrieval-system-administration-guide/appendix-a-filtering-technical-details.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-transaction-insight, version: "6.0.0", path: "tibco-foresight-archive-and-retrieval-system/archive-and-retrieval-system-administration-guide/appendix-b-tibco-foresight-archive-retrieval.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-transaction-insight, version: "6.0.0", path: "tibco-foresight-archive-and-retrieval-system/archive-and-retrieval-system-administration-guide/appendix-b-tibco-foresight-archive-retrieval.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-transaction-insight, version: "6.0.0", path: "tibco-foresight-archive-and-retrieval-system/archive-and-retrieval-system-administration-guide/introduction.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-transaction-insight, version: "6.0.0", path: "tibco-foresight-archive-and-retrieval-system/archive-and-retrieval-system-administration-guide/introduction.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-transaction-insight, version: "6.0.0", path: "tibco-foresight-archive-and-retrieval-system/archive-and-retrieval-system-user-guide/page-details/common-elements.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-transaction-insight, version: "6.0.0", path: "tibco-foresight-archive-and-retrieval-system/archive-and-retrieval-system-user-guide/page-details/common-elements.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-transaction-insight, version: "6.0.0", path: "tibco-foresight-archive-and-retrieval-system/archive-and-retrieval-system-user-guide/page-details/viewing-data.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-transaction-insight, version: "6.0.0", path: "tibco-foresight-archive-and-retrieval-system/archive-and-retrieval-system-user-guide/page-details/viewing-data.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-transaction-insight, version: "6.0.0", path: "tibco-foresight-transaction-insight/common-administration/administrator-pages/alerts.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-transaction-insight, version: "6.0.0", path: "tibco-foresight-transaction-insight/common-administration/administrator-pages/alerts.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-transaction-insight, version: "6.0.0", path: "tibco-foresight-transaction-insight/common-administration/administrator-pages/fhir.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-transaction-insight, version: "6.0.0", path: "tibco-foresight-transaction-insight/common-administration/administrator-pages/fhir.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-transaction-insight, version: "6.0.0", path: "tibco-foresight-transaction-insight/common-administration/administrator-pages/filters.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-transaction-insight, version: "6.0.0", path: "tibco-foresight-transaction-insight/common-administration/administrator-pages/filters.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-transaction-insight, version: "6.0.0", path: "tibco-foresight-transaction-insight/common-administration/administrator-pages/partners.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-transaction-insight, version: "6.0.0", path: "tibco-foresight-transaction-insight/common-administration/administrator-pages/partners.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-transaction-insight, version: "6.0.0", path: "tibco-foresight-transaction-insight/common-administration/administrator-pages/settings/event-log.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-transaction-insight, version: "6.0.0", path: "tibco-foresight-transaction-insight/common-administration/administrator-pages/settings/event-log.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-transaction-insight, version: "6.0.0", path: "tibco-foresight-transaction-insight/common-administration/administrator-pages/settings/portals.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-transaction-insight, version: "6.0.0", path: "tibco-foresight-transaction-insight/common-administration/administrator-pages/settings/portals.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-transaction-insight, version: "6.0.0", path: "tibco-foresight-transaction-insight/common-administration/administrator-pages/teams.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-transaction-insight, version: "6.0.0", path: "tibco-foresight-transaction-insight/common-administration/administrator-pages/teams.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-transaction-insight, version: "6.0.0", path: "tibco-foresight-transaction-insight/common-administration/administrator-pages/users.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-transaction-insight, version: "6.0.0", path: "tibco-foresight-transaction-insight/common-administration/administrator-pages/users.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-transaction-insight, version: "6.0.0", path: "tibco-foresight-transaction-insight/common-administration/appendix-b-partner-assignment-errors.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-transaction-insight, version: "6.0.0", path: "tibco-foresight-transaction-insight/common-administration/appendix-b-partner-assignment-errors.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-transaction-insight, version: "6.0.0", path: "tibco-foresight-transaction-insight/common-administration/appendix-d-administrators-guide-to-forms-and-views/edi-viewing-formats.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-transaction-insight, version: "6.0.0", path: "tibco-foresight-transaction-insight/common-administration/appendix-d-administrators-guide-to-forms-and-views/edi-viewing-formats.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-transaction-insight, version: "6.0.0", path: "tibco-foresight-transaction-insight/common-administration/managing-statistics-tasks-and-files-pages.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-transaction-insight, version: "6.0.0", path: "tibco-foresight-transaction-insight/common-administration/managing-statistics-tasks-and-files-pages.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-transaction-insight, version: "6.0.0", path: "tibco-foresight-transaction-insight/common-administration/tutorial/set-up-an-administrative-user-for-the-tutorial.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-transaction-insight, version: "6.0.0", path: "tibco-foresight-transaction-insight/common-administration/tutorial/set-up-an-administrative-user-for-the-tutorial.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-transaction-insight, version: "6.0.0", path: "tibco-foresight-transaction-insight/filters-for-foresight-portal-applications/transaction-insight-filters.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-foresight-transaction-insight, version: "6.0.0", path: "tibco-foresight-transaction-insight/filters-for-foresight-portal-applications/transaction-insight-filters.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-iprocess-engine, version: "11.10.0", path: "tibco-iprocess-engine-database-administration/administration-guide-db2/cases/case-data.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-iprocess-engine, version: "11.10.0", path: "tibco-iprocess-engine-database-administration/administration-guide-db2/lists.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-iprocess-engine, version: "11.10.0", path: "tibco-iprocess-engine-database-administration/administration-guide-db2/lists.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-iprocess-engine, version: "11.10.0", path: "tibco-iprocess-engine-database-administration/administration-guide-db2/mbox-sets-and-message-queues/table-relationships.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-iprocess-engine, version: "11.10.0", path: "tibco-iprocess-engine-database-administration/administration-guide-db2/mbox-sets-and-message-queues/table-relationships.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-iprocess-engine, version: "11.10.0", path: "tibco-iprocess-engine-database-administration/administration-guide-db2/monitoring/stat-rp-daily.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-iprocess-engine, version: "11.10.0", path: "tibco-iprocess-engine-database-administration/administration-guide-db2/monitoring/table-relationships.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-iprocess-engine, version: "11.10.0", path: "tibco-iprocess-engine-database-administration/administration-guide-db2/monitoring/table-relationships.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-iprocess-engine, version: "11.10.0", path: "tibco-iprocess-engine-database-administration/administration-guide-db2/procedures/proc-instance.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-iprocess-engine, version: "11.10.0", path: "tibco-iprocess-engine-database-administration/administration-guide-db2/ssolite-stored-procedures/overview.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-iprocess-engine, version: "11.10.0", path: "tibco-iprocess-engine-database-administration/administration-guide-oracle/cases/case-data-2.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-iprocess-engine, version: "11.10.0", path: "tibco-iprocess-engine-database-administration/administration-guide-oracle/cases/table-relationships-2.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-iprocess-engine, version: "11.10.0", path: "tibco-iprocess-engine-database-administration/administration-guide-oracle/cases/table-relationships-2.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-iprocess-engine, version: "11.10.0", path: "tibco-iprocess-engine-database-administration/administration-guide-oracle/lists.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-iprocess-engine, version: "11.10.0", path: "tibco-iprocess-engine-database-administration/administration-guide-oracle/lists.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-iprocess-engine, version: "11.10.0", path: "tibco-iprocess-engine-database-administration/administration-guide-oracle/mbox-sets-and-message-queues.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-iprocess-engine, version: "11.10.0", path: "tibco-iprocess-engine-database-administration/administration-guide-oracle/mbox-sets-and-message-queues.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-iprocess-engine, version: "11.10.0", path: "tibco-iprocess-engine-database-administration/administration-guide-oracle/monitoring/stat-rp-daily-2.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-iprocess-engine, version: "11.10.0", path: "tibco-iprocess-engine-database-administration/administration-guide-oracle/monitoring/table-relationships-2.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-iprocess-engine, version: "11.10.0", path: "tibco-iprocess-engine-database-administration/administration-guide-oracle/monitoring/table-relationships-2.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-iprocess-engine, version: "11.10.0", path: "tibco-iprocess-engine-database-administration/administration-guide-oracle/procedures/procedure-lock.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-iprocess-engine, version: "11.10.0", path: "tibco-iprocess-engine-database-administration/administration-guide-oracle/ssolite-stored-procedures/overview-2.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-iprocess-engine, version: "11.10.0", path: "tibco-iprocess-engine-database-administration/administration-guide-oracle/work-items/table-relationships-2.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-iprocess-engine, version: "11.10.0", path: "tibco-iprocess-engine-database-administration/administration-guide-oracle/work-items/table-relationships-2.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-iprocess-engine, version: "11.10.0", path: "tibco-iprocess-engine-database-administration/administration-guide-sql-server/cases/case-data-3.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-iprocess-engine, version: "11.10.0", path: "tibco-iprocess-engine-database-administration/administration-guide-sql-server/cases/table-relationships-3.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-iprocess-engine, version: "11.10.0", path: "tibco-iprocess-engine-database-administration/administration-guide-sql-server/cases/table-relationships-3.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-iprocess-engine, version: "11.10.0", path: "tibco-iprocess-engine-database-administration/administration-guide-sql-server/lists.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-iprocess-engine, version: "11.10.0", path: "tibco-iprocess-engine-database-administration/administration-guide-sql-server/lists.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-iprocess-engine, version: "11.10.0", path: "tibco-iprocess-engine-database-administration/administration-guide-sql-server/mbox-sets-and-message-queues/table-relationships-2.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-iprocess-engine, version: "11.10.0", path: "tibco-iprocess-engine-database-administration/administration-guide-sql-server/mbox-sets-and-message-queues/table-relationships-2.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-iprocess-engine, version: "11.10.0", path: "tibco-iprocess-engine-database-administration/administration-guide-sql-server/monitoring/stat-rp-daily-3.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-iprocess-engine, version: "11.10.0", path: "tibco-iprocess-engine-database-administration/administration-guide-sql-server/monitoring/table-relationships-3.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-iprocess-engine, version: "11.10.0", path: "tibco-iprocess-engine-database-administration/administration-guide-sql-server/monitoring/table-relationships-3.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-iprocess-engine, version: "11.10.0", path: "tibco-iprocess-engine-database-administration/administration-guide-sql-server/procedures/proc-audit.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-iprocess-engine, version: "11.10.0", path: "tibco-iprocess-engine-database-administration/administration-guide-sql-server/ssolite-stored-procedures/overview-3.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-iprocess-engine, version: "11.10.0", path: "tibco-iprocess-engine-database-administration/administration-guide-sql-server/work-items/table-relationships-3.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-iprocess-engine, version: "11.10.0", path: "tibco-iprocess-engine-database-administration/administration-guide-sql-server/work-items/table-relationships-3.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-iprocess-workspace-windows, version: "11.10.0", path: "basic-design/defining-a-procedure/placing-procedure-objects.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-iprocess-workspace-windows, version: "11.10.0", path: "basic-design/defining-a-procedure/placing-procedure-objects.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-iprocess-workspace-windows, version: "11.10.0", path: "integration-techniques/understanding-xpdl-produced-from-iprocess/about-xpdl-entities-transformed-from-iprocess/procedure-package.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-offer-and-price-engine, version: "6.0.0", path: "installation-and-configuration-guide/docker.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-offer-and-price-engine, version: "6.0.0", path: "installation-and-configuration-guide/installation.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-offer-and-price-engine, version: "6.0.0", path: "installation-and-configuration-guide/postinstallation-tasks/task-1-copying-dependencies.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-offer-and-price-engine, version: "6.0.0", path: "installation-and-configuration-guide/postinstallation-tasks/task-1-copying-dependencies.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-offer-and-price-engine, version: "6.0.0", path: "user-guide/data-models.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-offer-and-price-engine, version: "6.0.0", path: "user-guide/data-models.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-offer-and-price-engine, version: "6.0.0", path: "web-services-guide/transport-modes.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-platform-command-line-interface, version: "1.2.0", path: "managing-capabilities/integration-flogo/managing-tibco-flogo-apps/app-configuration-management/consul.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-product-and-service-inventory, version: "2.1.0", path: "installation-and-configuration/installation-overview.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-product-and-service-inventory, version: "2.1.0", path: "user-guide/configurator-ui.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-product-and-service-inventory, version: "2.1.0", path: "user-guide/configurator-ui.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-product-and-service-inventory-2-1-0, version: "2.1.0", path: "installation-and-configuration/installation-overview.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-product-and-service-inventory-2-1-0, version: "2.1.0", path: "user-guide/configurator-ui.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-product-and-service-inventory-2-1-0, version: "2.1.0", path: "user-guide/configurator-ui.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-rendezvous, version: "9.0.0", path: "concepts/the-rendezvous-daemon.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-rendezvous, version: "9.0.0", path: "net-reference/data/messagefield.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-rendezvous, version: "9.0.0", path: "net-reference/event-queues/idispatchable.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-rendezvous, version: "9.0.0", path: "net-reference/listeners/listener.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_IMAGE_BROKEN, decision: logged, ticket: DOCOPS-344, slug: tibco-rendezvous, version: "9.0.0", path: "net-reference/listeners/listener.md", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-reward, version: "22.3.0", path: "tibco-reward-2/analytics-user-guide.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-reward, version: "22.3.0", path: "tibco-reward/api-reference-guide/api-entity-attribute-description-tables/api-entity-attributes-and-their-properties/registered-card-attribute-properties.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-reward, version: "22.3.0", path: "tibco-reward/api-reference-guide/api-entity-attribute-description-tables/api-entity-attributes-and-their-properties/shopper-entity-attributes-and-properties.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-reward, version: "22.3.0", path: "tibco-reward/api-reference-guide/overview-of-apis/start-with-authentication.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-reward, version: "22.3.0", path: "tibco-reward/integration-guide/batch-file-integration/product-catalog-import-file/product-catalog-file-guidelines-data-elements.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-reward, version: "22.3.0", path: "tibco-reward/integration-guide/batch-file-integration/reward-export-file.md#*", reason: *empty-article}
  - {code: VERIFY_PUBLISHED_ANCHOR_MISSING, decision: logged, ticket: DOCOPS-344, slug: tibco-reward, version: "22.3.0", path: "tibco-reward/integration-guide/the-data-integration-process.md#*", reason: *empty-article}
```

</details>

---

## 4. Proposed Jira changes

Guardrails followed: existing issues are reused, there is one new issue for one new kind, and the points are for real work only.

| Issue | Change |
|---|---|
| **NEW-C** (sub-task under DOCOPS-96, TechDocs, **0.25 SP**) | "Pictures dropped by unusual source markup". The cases: a `<p>` directly inside `<ul>` (Control Plane 1.20.0, Platform 1.1.0, Platform CLI 1.2.0); `<img>` inside `<code>` (EDISIM 6.21.0); a wrong-case, wrong-depth thumbnail path (HIPAA 9.2.0). Fix in the converter, then re-convert those 5 versions. |
| DOCOPS-347 | Dated note: the traced causes P2–P6 with counts. Rename it to "Pictures not served on staging: dot folders, non-web formats, unresolved links". The non-web conversion (P3, 124 pictures in 6 versions, about 0.5 SP) is ours. Note it here rather than in a new issue, unless the user wants it tracked apart. |
| DOCOPS-344 | Dated note: Batch 2 adds 92 pages in 15 versions served with an empty article. Examples: Rendezvous 9.0.0 `concepts/the-rendezvous-daemon`; Flogo 3.0.1 `environment-variables`; 25 pages of iProcess Engine 11.10.0 database administration. |
| DOCOPS-322 | Dated note: the reasons for the 28 versions with no map, and the 3 versions with no page rows. Activation 1.1.0 needs the declared template. BC 7.5.0 and TCM 6.2.0 serve one help under two folders, which one template per product cannot cover. Platform 1.1.0 and Silver Fabric 1.2.0 are not in the request sheet. Platform CLI's old URLs may be Control Plane's. |
| DOCOPS-346 | Dated note: ActiveSpaces 5.2.0 is not served (with the other agent's `PAGE_MISSING`). |
| DOCOPS-362 | Dated note: 3 more versions for the re-convert list: Control Plane 1.20.0, Platform CLI 1.2.0, Flogo VS Code 1.3.5. |
| DOCOPS-345 | Dated note: the `_` → `-` case on iProcess `sw_warn` headings (3 pages). |
| DOCOPS-255 | Dated note: two more variants of dropped alt text, an alt spanning lines in raw HTML and `\*`. |
| DOCOPS-338 (the verify waves) | Dated note: Batch 2 ran `verify` without `--refresh`, so FTL/eFTL 7.3.0, Scribe Online and Cloud API Modeler 1.5.0 were judged on cached pages. Re-check them with `--refresh`. |

---

## 5. UAT-sheet rows (Digital Platform)

DOCOPS-344 (empty pages) and DOCOPS-346 (help not served) are already in the sheet: add the new examples to their Comments. New rows:

| Area | Issue | Example URL | Expected | Owner |
|---|---|---|---|---|
| Images (DAM) | Pictures in a folder whose name contains a dot are 404 (777 in 6 versions: Foresight Translator, Transaction Insight, ARS, HIPAA Validator Desktop, Operational Monitor; BC cXML). DOCOPS-347 | https://stg-docs.tibco.com/us/en/tibco-foresight-translator/online-help/4-2-0/installation/before-installing.html (picture `/content/dam/.../tib_translator_4.1_installation/Installation_Overview.png` 404) | The picture shows, as it does from folders without a dot | Digital Platform |
| Images (page render) | On some pages every picture gets a page-relative src under `/content/tibco/.../<page>/` (404) although the DAM copy is served; thumbnails get `src=""`; names with spaces get `placeholder.png` (197 in 9 versions). DOCOPS-347 | https://stg-docs.tibco.com/us/en/tibco-order-management/online-help/6-1-0/user-guide/order-management-system-user-interface/dashboard.html (`.../dashboard/UI-autoRefresh.png` 404; `/content/dam/.../6-1-0/user-guide/images/UI-autoRefresh.png` 200) | Pictures link the DAM path, as on the version's other pages | Digital Platform |
| Images (format) | Pictures in `.wmf`, `.emf`, `.bmp`, `.dib` are 404 (124 in 6 versions); browsers cannot show most of them anyway. Ours to convert. DOCOPS-347 | https://stg-docs.tibco.com/us/en/tibco-businessconnect/online-help/7-5-0/concepts/introduction.html | The diagrams show (as PNG) | TechDocs |

---

## 6. Open questions (for you)

1. **Pictures in dot folders (P2, 777):** should we ask Digital Platform to serve DAM folders with a dot? Or rename the folders ourselves (converter plus an in-place repair; about 1,300 pictures in 8 Batch 2 versions, more across the repos)?
2. **Non-web picture formats (P3, 124):** should we convert `.wmf`, `.emf`, `.bmp` and `.dib` to PNG in the converter and in place (about 0.5 SP)? Or accept them as they were on the old site?
3. **The DOCOPS-347 and DOCOPS-348 catch-alls:** may I move them to the end of the file now, and remove the DOCOPS-347 one after Batch 3? Today it logs every new kind of picture loss without anyone seeing it.
