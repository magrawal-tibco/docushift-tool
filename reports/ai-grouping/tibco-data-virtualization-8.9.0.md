# Data Virtualization 8.9.0: one menu for five help systems (Phase 87, DOCOPS-385)

AI draft, 19 Nov 2026. **For review. Nothing has been moved.** The plan file is `tibco-data-virtualization-8.9.0.yaml` in this folder. Measured on the English 8.9.0 repo tree (`toc.yml` and pages). Pages under `unfiled/` are left out.

## 1. Proposed top-level menu (12 sections)

| # | Menu title | Folder | Section page | What goes under it |
|---|---|---|---|---|
| 1 | What's New | `whats-new` | `whats-new.md` | "What's New in SDV 8.9" (Studio copy), "Key New Features" (the Web UI home page) |
| 2 | Getting Started | `getting-started` | `user-guides.md` (the product overview) | Getting Started Guide, Tutorial Guide |
| 3 | Installation and Upgrade Guide | `installation` | the guide's own page | the guide's 9 chapters, one level up |
| 4 | Using Studio | `studio` | new | User Guide, Discovery Guide |
| 5 | Web UI | `web-ui` | `web-ui/sdv-web-ui.md` | Introduction, Data Catalog, Data Workbench, Monitoring |
| 6 | Adapters | `adapters` | `adapters.md` (for now, see 5.1) | 7 groups, 74 adapters (section 2) |
| 7 | Business Directory | `business-directory` | `business-directory/businessdirectory.md` | Install, Introduction, Using, API and System Tables, REST API |
| 8 | Deployment Manager | `deployment-manager` | `deployment-manager/deployment-manager.md` | its 6 chapters |
| 9 | Administration and Security | `administration` | new | Administration Guide, Security Features Guide, ActiveCluster Guide, Troubleshooting |
| 10 | Client Interfaces and APIs | `developer` | new | Client Interfaces Guide, Application Programming Interface Guide, Data Source Toolkit Guide |
| 11 | Reference Guide | `reference` | the guide's own page | the guide's 12 chapters, one level up |
| 12 | Documentation, Support and Legal | `support-and-legal` | new | Spotfire Documentation and Support Services, Legal and Third-Party Notices |

Every Studio guide keeps its name, so a reader of the old site still finds "Administration Guide", "User Guide" and the rest. Where a section holds one guide, the section takes the guide's name (3, 11).

## 2. Adapter groups (74 adapters; Drill listed once)

The section folder is `adapters/`. Each adapter folder is shortened: `sdv-db2-adapter` becomes `db2`, so a page lands at `adapters/relational-databases/db2/...`.

- **Relational Databases** (`relational-databases`, 19): DB2, Greenplum, HSQLDB, Informix, Microsoft Access, Microsoft Access (Non-ODBC), MySQL, NeoView, Netezza, Oracle, PostgreSQL, SAP HANA, SingleStore, SQL Server, Sybase, Teradata, Vertica, DataDirect Mainframe, Composite.
- **Cloud Data Warehouses** (`cloud-data-warehouses`, 3): Amazon Redshift, Google BigQuery, Snowflake.
- **Big Data, NoSQL and Streaming** (`big-data-nosql`, 16): Drill, HBase, Apache HBase, Hive, Impala, SparkSQL, ComputeDB, Cassandra, CosmosDB, Couchbase, Amazon DynamoDB, Elasticsearch, MarkLogic, MongoDB, Splunk, Streaming.
- **Files and Cloud Storage** (`files-and-storage`, 5): File Data Sources, Local File Storage, Amazon S3, Azure Data Lake, Google Cloud Storage.
- **Enterprise Applications** (`enterprise-applications`, 13): Oracle E-Business Suite, NetSuite, Salesforce.com, Salesforce with SSO, SAP, SAP BW, SAP BW BEx, Siebel, Microsoft Dynamics CRM, GP and NAV, SharePoint, Active Directory.
- **SaaS, Marketing and Social** (`saas-and-social`, 14): Google Ads, Analytics, Calendar, Contacts, Directory, Drive and Sheets, HubSpot, Marketo, Oracle Eloqua, Facebook, Twitter, Email, RSS.
- **Web Services and Custom Sources** (`web-and-custom`, 4): Web-Based Data Sources (WSDL/REST), OData, JDBC-ODBC Bridge, Custom Java Procedures.

Drill appears twice in today's menu with the same page (`adapters/sdv-drill-adapter.md`). The plan lists it once, so the second menu entry goes. No page is dropped.

## 3. Collapses (7)

A wrapper level is removed and its children move up into its place:
- `deployment-manager.md` (the Home page; dropped as a duplicate) and `deployment-manager/deployment-manager.md` (becomes the section page). This removes the repeated `deployment-manager/deployment-manager/`.
- `business-directory.md` (Home; dropped) and `business-directory/businessdirectory.md` ("BusinessDirectory", becomes the section page). This removes `business-directory/businessdirectory/business-directory/`. The chapter folders get new names: `installation`, `introduction` (was `business-directory`), `using`, `api-and-system-tables`, `rest-api`.
- `web-ui/sdv-web-ui.md` ("SDV Web UI", becomes the section page).
- `user-guides/installation-upgrade-guide.md` and `user-guides/reference-guide.md` (each becomes its section's page).

The Studio Home page `user-guides.md` becomes the Getting Started page. Its 14 guides are placed one by one.

## 4. Retitles (14)

- 5 top-level "Spotfire® Data Virtualization" entries: none is left with that title. Two are dropped, `user-guides.md` becomes "Getting Started", `adapters.md` becomes "Adapters", and `web-ui.md` becomes "Key New Features".
- `user-guides/whats-new-2.md` "What's New" becomes "What's New in SDV 8.9", which is its own heading.
- Wrapper titles taken from folder names ("BusinessDirectory", "SDV Web UI", "Whats New") are gone (collapsed or dropped).
- Adapters: "SDV Microsoft Access Adapter(non-odbc)" becomes "SDV Microsoft Access Adapter (Non-ODBC)". The Dynamics CRM, GP and NAV adapters and Oracle Eloqua get a space added ("Dynamics CRM", "Oracle Eloqua"). The six "Using the ... Adapter" and "Using X with SDV" titles become "Oracle E-Business Suite Adapter", "Salesforce.com Adapter", "SAP Adapter", "SAP BW", "SAP BW BEx" and "Siebel".
- "ActiveCluster" becomes "ActiveCluster Guide", to match the other guides.

## 5. Topics in more than one help system

My measurement: 123 titles appear in more than one system: 73 identical, 13 nearly identical (90% or more of the same words) and 37 different. The count includes 22 menu entries that are sections of one page. It is not the 110 (45 / 14 / 51) in the plan. The difference: I also ignore `href=`/`src=` targets in HTML links and image folders, and that turns all the Deployment Manager pairs identical (5.3). Of the 73 identical titles, 60 are Deployment Manager against the Administration Guide.

### 5.1 Identical: drop one copy, redirect it (13, in `drop_duplicates`)

- **Home and What's New pages (4).** `business-directory.md` goes to `adapters.md`, and `deployment-manager.md` to `user-guides.md` (each pair is word-for-word the same). `web-ui/whats-new.md` goes to `whats-new.md`, and `business-directory/whats-new-in-sdv-8-9.md` to `user-guides/whats-new-2.md`. **The four What's New pages are one page, the SDV 8.9 release notes, not one per component.** So they are not retitled per component.
- **Data-source pages in both the User Guide and an adapter guide (9).** The User Guide copy is dropped and the adapter copy kept, because the topic is about that one source and a reader looking for it goes to the adapter. Pages: Apache Drill, DB2 and DB2 z/OS, Hive, Netezza, Oracle and Vertica limitations, Teradata introspection, SQL Server Active Directory login, and Netezza caching tips (the last one from the User Guide's caching chapter). The User Guide's "Data Source Limitations" chapter keeps its other pages.
- **Not dropped although identical:** connection-property pages shared by an adapter guide and the Power BI or SSIS connector in the Client Interfaces Guide ("Firewall and Proxy", "SSLClientCertPassword"; 12 and 10 pairs). They are generated driver documentation, one set per driver. Each belongs to its own driver's reference, so they stay, like "Authentication". The Deployment Manager "Limitations" pair is under 5.3.

### 5.2 Nearly identical: for your decision (in `review`)

- `adapters.md` and `user-guides.md` (Home pages): one word differs ("SDV connects" against "Spotfire connects"). **Recommend dropping `adapters.md`** and giving Adapters a generated section page (`landing: new`). Re-point `business-directory.md`'s redirect to `user-guides.md`.
- `whats-new.md` and `user-guides/whats-new-2.md`: only the heading differs. **Recommend dropping `whats-new-2`** (and re-pointing the Business Directory copy's redirect). The What's New section is then a single page.
- Changing the Repository Password (Business Directory against Admin Guide): two words differ ("SDV"/`<SDV_install_dir>` against "Spotfire"/`<TDV_install_dir>`). Recommend keeping both.
- Tips from an Expert if the Server Does Not Start (Business Directory against Install Guide): the Install Guide copy has one more sentence and fixes `<BD_install_dir>`. Recommend keeping both.
- Microsoft SQL Server 2008 Limitation (adapter against User Guide): **the java.security path differs** (`\conf\server\security\` against `/jdk/conf/security/`). A writer has to say which one is right.
- SAP HANA Data Source Limitations (adapter against User Guide): the adapter copy keeps stale PDF page numbers (", page 218/219") in two link texts. Choose which to keep.
- Not listed pair by pair: the generated connector property pages (Location, LogModules, Logging, Readonly, SSL, SSL Configuration, SSLClientCert, SSLClientCertSubject, SSLClientCertType). Their small wording differences between adapter and SSIS/Power BI driver versions are expected. They stay.

### 5.3 Deployment Manager help against Administration Guide chapter (39 pairs in `review`)

- **Coverage.** The Deployment Manager help has 41 pages: 39 in the menu, plus off-menu copies of the Legal and Support pages (5.4). All 39 menu pages have a twin in `user-guides/administration-guide/deployment-manager/`, in the same order with the same titles.
- **Text.** Page by page, the text is the same, with the same word counts. Only these differ:
  - `<a id="kanchorNNN">` numbers (166 lines);
  - link targets, because the Admin Guide files carry a `-2` suffix (146 lines);
  - the picture folder, `deploymanhelp/` against `onlinedocs/` (44 lines; same file names);
  - a blank line in Defining Mappings.
- **Newer copy.** Neither copy is longer or newer.
- **Recommendation:** publish it once, **in the Administration Guide**, and redirect the 39 Deployment Manager help pages to their twins. The Admin Guide then stays whole and recognisable, and the Deployment Manager section (8) and its 2 collapses go away (11 sections).
- **Alternative:** keep the Deployment Manager section and drop the Admin Guide chapter, which is more visible but leaves the Admin Guide with a gap.
- **Why it is not applied yet.** The plan file keeps both until you decide. On approval, move the 39 rows from `review` to `drop_duplicates` and delete section 8.

### 5.4 Different text, same title (37): stay

Examples: "Getting Started", "Authentication", "Tables", "Introduction", "Schema", "Kerberos", "Informix Data Source Limitations", "Sybase Data Source Characteristics". Their parents tell them apart. No action.

## 6. Unsure / open points

1. **Deployment Manager**: keep the Admin Guide copy (recommended) or the standalone section? See 5.3.
2. **Section pages that are the product overview.** `adapters.md` (Adapters) and `user-guides.md` (Getting Started) are the product overview with key new features, not a list of what is below. If 5.2's first recommendation is taken, Adapters gets a generated page. Getting Started keeps the overview, which reads well as a start page.
3. **"Key New Features"** (`web-ui.md`) is a short bullet list linking to What's New. It sits in What's New as a 2nd entry. You could drop it instead, but it is not an identical duplicate, so the plan keeps it.
4. **Off-menu pages.** `deployment-manager/legal-and-third-party-notices.md` and `deployment-manager/spotfiredocumentation-and-support-services.md` are in no menu, are not under `unfiled/`, and differ from the top-level copies (older wording and links). The plan does not touch them. The apply script must still move or redirect them.
5. **Adapter placement calls.** Active Directory is under Enterprise Applications, Email and RSS under SaaS, Composite (SDV-to-SDV) under Relational, and ComputeDB and Streaming under Big Data. Move any you would file differently.
6. **Apply-script semantics.** The plan relies on items applying in order: collapse a wrapper first, then name its lifted children to give them a folder. A dropped page's menu entry is removed.

## 7. Reuse for 8.8.1 and 8.8.0

The top-level shape is the same: 5 systems, top What's New, support and legal pages. But **the plan cannot be applied as is**, because most addresses differ:
- **Adapters:** 8.8.x uses the `tdv-` prefix instead of `sdv-` (`tdv-db2-adapter.md`). It also has `computedb-adapter.md`, `tibco-streaming-adapter.md`, `tdv-google-analytics.md`, `using-*-with-tdv.md` and `using-the-sap-for-tdv-adapter.md`, plus one extra adapter, **`tdv-sharepoint-excelservices-adapter.md`**. 8.8.1 has 76 menu entries (Drill twice). 8.8.0 has 75: no Microsoft Access (Non-ODBC).
- **Titles:** "TIBCO® Data Virtualization", "TDV Web UI" (`web-ui/tdv-web-ui.md`), "TIBCO Documentation and Support Services" (`tibco-documentation-and-support-services.md`).
- **What's New:** five copies, not four. Deployment Manager also has one (`deployment-manager/whats-new-2.md`), and the Studio and Web UI copies are `whats-new-3.md` and `web-ui/whats-new-4.md`.
- **Order:** the Web UI comes last.
- **Business Directory:** 219 menu entries against 73. The same 5 chapters, with more entries below them. **8.8.0's wrapper is misspelt "BusinessDiirectory"** (`businessdiirectory.md`).
- **Studio:** 8.8.0 has no Troubleshooting guide, and it carries a second copy of the Support and Legal pages inside `user-guides/`.

So: generate the 8.8.x plans from this one with a url map (`sdv-` to `tdv-`, the renamed files above). Then re-run the duplicate checks per version: the duplicate lists were measured on 8.9.0 only.
