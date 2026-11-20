# Data Virtualization 8.8.1: one menu for five help systems (Phase 87, DOCOPS-385)

AI draft, 20 Nov 2026. **Nothing has been moved.** Plan file: `tibco-data-virtualization-8.8.1.yaml`. Generated from the approved 8.9.0 plan (same 11 sections, titles, folders, order, adapter groups, collapses and retitles, with "TDV" for "SDV"). Duplicates re-measured on the reframed 8.8.1 tree: same body text after removing front matter, link targets (Markdown and HTML `href=`/`src=`) and `<a id>` anchors.

## 1. Menu

| Section | Folder | Entries below |
|---|---|---|
| What's New | `whats-new` | 0 (one page) |
| Getting Started | `getting-started` | 100 |
| Installation and Upgrade Guide | `installation` | 162 (10 chapters; 8.8.1 has "TDV for AWS Marketplace") |
| Using Studio | `studio` | 722 |
| Web UI | `web-ui` | 33 (Introduction, Data Catalog, Data Workbench; no Monitoring in 8.8.1) |
| Adapters | `adapters` | 6,572 (7 groups, 75 adapters) |
| Business Directory | `business-directory` | 218 (same 5 chapters) |
| Administration and Security | `administration` | 638 (Admin Guide, Security, ActiveCluster Guide, Troubleshooting) |
| Client Interfaces and APIs | `developer` | 892 |
| Reference Guide | `reference` | 827 |
| Documentation, Support and Legal | `support-and-legal` | 2 |

## 2. What differs from 8.9.0

- **Addresses:** `tdv-` adapter files; `computedb-adapter`, `tibco-streaming-adapter`, `tdv-google-analytics`, `using-*-with-tdv`, `using-the-sap-for-tdv-adapter`; `web-ui/tdv-web-ui.md`; `tibco-documentation-and-support-services.md`.
- **Extra adapter:** TDV SharePoint ExcelServices goes under Enterprise Applications, after SharePoint (folder `sharepoint-excelservices`, title "TDV SharePoint Excel Services Adapter").
- **No "Key New Features".** In 8.9.0 the Web UI home page (`web-ui.md`) was its own short page. In 8.8.1 it is word for word the Studio home page, so it is dropped to `user-guides.md`, and What's New has no child.
- **Web UI chapters are named in the plan.** After the collapse of `web-ui/tdv-web-ui.md`, the plan lists its three chapters. This makes their folders `web-ui/<chapter>`. The result is the same as without them here, but it guards against the 8.9.0 problem in section 6.
- **Off-menu Support and Legal copies.** The ones identical to the top-level pages are dropped (Studio, Business Directory, Deployment Manager). The nearly identical ones are in `review`, and until then they go to `unfiled/` (3 pages).

## 3. Duplicates dropped (60)

- **Home pages (4):** `business-directory.md`, `deployment-manager.md` and `web-ui.md` are identical to `user-guides.md`. `adapters.md` differs only in that it lacks the closing "See What's New" link, and is dropped as in 8.9.0 (Adapters has a generated page).
- **What's New (4) → `whats-new.md`:** the Studio and Deployment Manager copies are identical. The Business Directory and Web UI copies are an **older draft**: JDK 17.0.12 against 17.0.13, "Microsoft ADAL libraries have been migrated to MSAL" against "Azure domain support … migrated from the ADAL to MSAL library", and "Containers" against "containers". They are dropped by the 8.9.0 rule (one What's New page), and the kept page is the newer text.
- **User Guide → adapter copy (9):** Drill, DB2/DB2 z/OS, Hive, Netezza, Oracle and Vertica limitations, Teradata introspection, SQL Server Active Directory login, and Netezza caching tips. This is the same set as in 8.9.0.
- **Deployment Manager → Administration Guide (39 + the wrapper `deployment-manager/deployment-manager.md`):** all identical. Some Admin Guide names differ from 8.9.0 (`defining-deployment-plans.md`, `executing-deployment.md`, `defining-principal.md`, `viewing-source-site.md`).
- **Support and Legal (4):** `deployment-manager/` and `user-guides/` copies of the support page, `business-directory/` and `user-guides/` copies of the legal page → top-level copies.
- **Not dropped, though identical:** the connector property pages (Firewall and Proxy, SSLClientCertPassword) shared with the Power BI and SSIS drivers, as in 8.9.0.

## 4. Review pairs (not applied)

1. Changing the Repository Password (Business Directory against Admin Guide): **identical in 8.8.1**. 8.9.0 kept both. Recommend keep both.
2. Tips from an Expert if the Server Does Not Start (Business Directory against Install Guide): the Install copy is fuller. Keep both.
3. Microsoft SQL Server 2008 Limitation (adapter against User Guide): the java.security path differs (`\conf\server\security\` against `/jdk/conf/security/`). A writer should decide.
4. SAP HANA limitations (adapter against User Guide): the adapter copy has stale ", page 218/219". Recommend drop the User Guide copy.
5. Off-menu copies, recommend drop to the top-level page: `business-directory/` support page (italics only), `web-ui/` support page (older list), `web-ui/` legal ("Oracle Corporation"), `deployment-manager/` legal (copyright 2024 against 2025).

## 5. Dry run

`python scratch/restructure.py reports/ai-grouping/tibco-data-virtualization-8.8.1.yaml`:

`8.8.1: {'files': 10970, 'moved': 9515, 'dropped duplicates': 60, 'generated landings': 12, 'off-menu pages to unfiled/': 3, 'links rewritten': 0}`

The 3 off-menu pages are the review item 5 copies `deployment-manager/legal-and-third-party-notices.md`, `web-ui/legal-and-third-party-notices.md` and `web-ui/tibco-documentation-and-support-services.md`. New menu: 10,177 entries (10,265 before). No page appears twice apart from the anchors that were already repeated.

## 6. Found in 8.9.0 (for the record)

In the applied 8.9.0 tree, "Key New Features" (`web-ui.md`) still carries the whole Web UI subtree in the menu (36 entries, shown twice). The Web UI pages also landed under `whats-new/key-new-features/sdv-web-ui/` instead of `web-ui/`. Cause in `scratch/restructure.py`: an item's folder rule (`web-ui` → `whats-new/key-new-features`) is checked before the collapse rule for `web-ui/sdv-web-ui/`, and `remap_entry` copies all of a node's original children, including those collapsed or placed elsewhere. It does not affect 8.8.1, because `web-ui.md` is dropped here. 8.8.0 is affected (see its note).
