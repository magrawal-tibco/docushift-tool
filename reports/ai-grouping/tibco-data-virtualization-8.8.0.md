# Data Virtualization 8.8.0: one menu for five help systems (Phase 87, DOCOPS-385)

AI draft, 20 Nov 2026. **Nothing has been moved.** Plan file: `tibco-data-virtualization-8.8.0.yaml`. Generated from the approved 8.9.0 plan, as for 8.8.1 (see `tibco-data-virtualization-8.8.1.md` for the address changes and the extra SharePoint ExcelServices adapter). Duplicates were re-measured on the reframed 8.8.0 tree with the same rules.

## 1. Menu

| Section | Folder | Entries below |
|---|---|---|
| What's New | `whats-new` | 1: Key New Features (34 in this dry run, see section 6) |
| Getting Started | `getting-started` | 100 |
| Installation and Upgrade Guide | `installation` | 162 (10 chapters) |
| Using Studio | `studio` | 722 |
| Web UI | `web-ui` | 33 |
| Adapters | `adapters` | 6,559 (7 groups, 74 adapters) |
| Business Directory | `business-directory` | 218 |
| Administration and Security | `administration` | 628 (Admin Guide, Security, ActiveCluster Guide) |
| Client Interfaces and APIs | `developer` | 917 |
| Reference Guide | `reference` | 824 |
| Documentation, Support and Legal | `support-and-legal` | 2 |

## 2. What differs from 8.9.0 and 8.8.1

- **No Microsoft Access (Non-ODBC)** and **no Troubleshooting guide**: their items are left out. Administration and Security has 3 guides.
- **Business Directory wrapper** `business-directory/businessdiirectory.md` (misspelt "BusinessDiirectory") is collapsed and becomes the section page, as in 8.9.0. Its title in the menu is the section's, "Business Directory".
- **Key New Features is back**, as in 8.9.0. In 8.8.0, `web-ui.md` is a short page of its own (Web-UI enhancements plus "See What's New"), not a copy of the Studio home page. So it is retitled "Key New Features" and placed under What's New.
- **The What's New page kept is the Studio copy** (`user-guides/whats-new-3.md`, identical to the Deployment Manager copy). It becomes the section page `whats-new.md`. The top-level `whats-new.md` is dropped to it. That copy is an incomplete, badly converted version of the same page: no Web-UI Enhancements block, a numbered list in place of headings, and stray `\` line breaks. This is the one deliberate change from 8.9.0, which kept the top-level copy.
- **Studio's second Support and Legal copies** (`user-guides/tibco-documentation-and-support-services.md`, `user-guides/legal-and-third-party-notices.md`, both in the Studio menu) are identical to the top-level pages and are dropped to them.

## 3. Duplicates dropped (59)

- **Home pages (3) → `user-guides.md`:**
  - `deployment-manager.md`: identical.
  - `business-directory.md`: differs by one full stop ("Enhanced AzureAD as IdP."). It has to be dropped for the collapse to work, and is.
  - `adapters.md`: an older overview without the Web-UI Enhancements block and with stray `\` breaks. Dropped as in 8.9.0; Adapters has a generated page.
- **What's New (3) → `user-guides/whats-new-3.md`:**
  - `deployment-manager/whats-new-2.md`: identical.
  - `whats-new.md`: see above.
  - `business-directory/whats-new.md`: identical except "**TDV 8.7** includes enhancements", a stale version number. The 8.9.0 rule is one page.
- **User Guide → adapter copy (9):** the same set as 8.9.0 and 8.8.1.
- **Deployment Manager → Administration Guide (39 + the wrapper):** all identical, with the same pairs as 8.8.1.
- **Support and Legal (5):** the `deployment-manager/` and `user-guides/` support pages, and the `business-directory/`, `deployment-manager/` and `user-guides/` legal pages → top-level copies.

## 4. Review pairs (not applied)

1. Changing the Repository Password (Business Directory against Admin Guide): **identical**. 8.9.0 kept both. Recommend keep both.
2. Tips from an Expert if the Server Does Not Start: the Install copy is fuller. Keep both.
3. Microsoft SQL Server 2008 Limitation: same text and path in 8.8.0, but the adapter copy's steps are misnumbered. Recommend drop the adapter copy to the User Guide copy, or keep both.
4. SAP HANA limitations: the adapter copy has stale ", page 218/219". Recommend drop the User Guide copy.
5. Off-menu copies, recommend drop to the top-level page: the `business-directory/` support page (italics only), the `web-ui/` support page (older list) and the `web-ui/` legal page ("Oracle Corporation"). Until decided, the two `web-ui/` copies follow `web-ui.md` to `whats-new/key-new-features/`, and the Business Directory one stays in `business-directory/`.

## 5. Dry run

`python scratch/restructure.py reports/ai-grouping/tibco-data-virtualization-8.8.0.yaml`:

`8.8.0: {'files': 10939, 'moved': 9510, 'dropped duplicates': 59, 'generated landings': 12, 'off-menu pages to unfiled/': 0, 'links rewritten': 0}`

## 6. Known problem: the Web UI subtree appears twice in the menu

The same fault as in the applied 8.9.0 tree. `remap_entry` in `scratch/restructure.py` copies every original child of a placed entry. So "Key New Features" (`web-ui.md`) still carries the "TDV Web UI" wrapper and its 33 entries, which also form the Web UI section. The plan cannot avoid it: `web-ui.md` is neither a landing nor a duplicate, so it cannot be collapsed.

- **Files are right.** The plan names the three Web UI chapters after the collapse, so the pages go to `web-ui/<chapter>/`, not under `whats-new/key-new-features/` as in 8.9.0.
- **Fix in the script (tested on a copy, not applied):** in `remap_entry`, skip a child whose page is collapsed or placed elsewhere:
  ```python
  kids = [e for c in node.get("subfolderlist") or []
          if str(c.get("url") or "").partition("#")[0] not in (collapsed | set(placed))
          for e in remap_entry(("node", c))]
  ```
  With it, the 8.8.0 menu has 10,177 entries, and Key New Features is a single page. 8.8.1 is unchanged. 8.9.0 would need the same fix plus a re-apply.
