# ActiveSpaces Enterprise Edition 5.2.1: pages by menu depth, a draft for review (17 Nov 2026)

Phase 81 (AI-assisted grouping). This is a draft only. The entries are in `tibco-activespaces-enterprise-edition-5.2.1.yaml`; nothing is in `config/reframe.yaml`. The 6 entries are scoped `versions: ["5.2.1"]` and go under the existing product block, which has `pin_layout_to: "5.2.0"`. With entries, 5.2.1 is its own pin (Phase 81). 4.10.0 to 5.2.0 keep projecting onto 5.2.0 packed by R1, and none of them picks up an entry (checked in memory).

## The result

| | Today: projected onto 5.2.0 (R1) | R1 on its own | **This draft** |
|---|---|---|---|
| Pages in the menu | 55 | 54 | **63** |
| Pages not in navigation (the same in every column) | 4 | 4 | 4 |
| Median page (menu pages) | 1,102 | 1,158 | **659** |
| 90th percentile | 2,830 | 2,830 | 3,184 |
| Largest page | 2,994 | 2,994 | **5,963** (Querying a Data Grid Table) |
| Pages over 5,000 words | 0 | 0 | **1** |
| Pages under 300 words | 12 | 12 | 18 |
| Pages holding only some of a parent's children | 22 | 22 | **0** |

Every TOC topic lands on a page in each layout (0 missing, 0 extra). The 63 menu pages include the four top-level single pages (home, What's New, Documentation and Support, Legal), which need no entry.

## Guides and chapters, measured

Counts are pages (largest page in words) if the entry were set at that depth, measured with the real packer (`packer.pack`), so R4.2 is included. No chapter spans two source folders, so R4.2 never splits anything here. Words are the packer's counts by path, not `levels.py`'s.

| guide | chapter | words | topics | menu depth | depth 1 | depth 2 | depth 3 | depth 4 |
|---|---|---|---|---|---|---|---|---|
| **Installation** | (whole guide) | 3,184 | 20 | 4 | 1 (3,184) | 6 (1,113) | 14 (825) | 20 (825) |
| **Concepts** | (whole guide) | 31,803 | 129 | 7 | 1 (31,803) | 18 (18,612) | 43 (5,963) | 75 (5,054) |
| Concepts | Programming with ActiveSpaces | 18,612 | 86 | 6 | 1 (18,612) | 8 (5,963) | 34 (5,054) | 66 (2,128) |
| Concepts | Vectors in TIBCO ActiveSpaces | 2,994 | 6 | 2 | 1 (2,994) | 6 (962) | | |
| Concepts | The ActiveSpaces JDBC Driver | 2,940 | 13 | 4 | 1 (2,940) | 5 (2,014) | 11 (1,619) | 13 (1,132) |
| Concepts | 15 other chapters (Overview 963, Error Codes 1,267, Sizing Guide 947 ... Redesigned from the Ground Up 72) | 72 to 1,267 | 1 to 5 | 1 to 2 | 1 each | | | |
| **Administration** | (whole guide) | 36,399 | 151 | 5 | 1 (36,399) | 31 (4,323) | 102 (2,194) | 148 (1,568) |
| Administration | Disaster Recovery | 4,323 | 26 | 3 | 1 (4,323) | 12 (780) | 26 (692) | |
| Administration | Administration Tool | 3,597 | 13 | 3 | 1 (3,597) | 12 (733) | 13 (733) | |
| Administration | Defining a Data Grid | 3,299 | 9 | 4 | 1 (3,299) | 3 (1,721) | 8 (1,536) | 9 (1,536) |
| Administration | Security | 3,227 | 11 | 3 | 1 (3,227) | 4 (2,194) | 11 (1,279) | |
| Administration | Live Backup and Restore | 2,830 | 7 | 3 | 1 (2,830) | 2 (1,448) | 7 (1,448) | |
| Administration | Defining a Table | 2,041 | 10 | 3 | 1 (2,041) | 6 (747) | 10 (423) | |
| Administration | 24 other chapters (Deployment Scenario ... Windows Services 1,790, Methods of Selecting a Proxy 1,568 ... String Encoding 71) | 51 to 1,790 | 1 to 10 | 1 to 4 | 1 each | | | |
| **Security Guidelines** | (whole guide) | 2,720 | 14 | 3 | 1 (2,720) | 10 (1,302) | 14 (473) | |
| **API Reference** | (whole guide) | 47 | 2 | 2 | 1 (47) | 2 (38) | | |

Programming with ActiveSpaces, by section (depth 2): Structuring Programs 3,983; SQL Identifiers 138; Column Data Types 1,001; Querying a Data Grid Table 5,963 (of which The SQL SELECT Statement 5,054); Modifying Data in a Table 3,265; SQL Expressions 1,260; SQL Functions 2,453; plus the chapter's own page (549).

## Choice per guide and chapter

| Guide | Chapter | Depth | Pages | Largest | Reason |
|---|---|---|---|---|---|
| Installation | (whole guide) | 1 | 1 | 3,184 | Modest, and read as one task. Windows (387) and Linux (646) are too short to be pages of their own. |
| Concepts | (guide at depth 2) | 2 | 18 + guide page | 2,994 | Every chapter one page, which is the same as each chapter at depth 1. All but one are under 3,000 words, and each reads as one topic (Vectors, JDBC Driver, Sizing, Error Codes reference). |
| Concepts | Programming with ActiveSpaces | **2** | 8 | 5,963 | 18,612 words, a guide inside the guide. One page per section: Structuring Programs (the objects and tasks), Querying, Modifying Data, SQL Expressions, SQL Functions. Depth 3 would give 34 pages, many under 150 words (Task A/B/C, PUT, GET), and the SELECT reference (5,054) would still be one page. |
| Administration | (guide at depth 2) | 2 | 31 + guide page | 4,323 | Every chapter one page. The guide is a run of tasks (start a realm, define a grid, start a node ...), each a chapter; the largest, Disaster Recovery (4,323), is under 5,000. Administration Tool (3,597) stays one reference page, a heading per tibdg command, as for the EMS command listing. |
| Security Guidelines | (whole guide) | 1 | 1 | 2,720 | Short checklist guide; nine chapters, eight under 360 words. |
| API Reference | (whole guide) | 1 | 1 | 47 | A link page to the API docs. |

## Pages over 5,000 words (1)

| Page | Words | Why acceptable |
|---|---|---|
| Querying a Data Grid Table | 5,963 | SQL reference: the SELECT statement (5,054) clause by clause, plus three short topics on iterators and consistency. Splitting needs depth 3 for the whole chapter (34 pages). See the decision below. |

## Pages under 300 words (18)

Small chapters that are a page of their own because no chapter shares a page with only some of its siblings: Concepts' Redesigned from the Ground Up (72), Transaction Isolation (98), The Workflow for a PUT Operation (116), Log Levels (244), Best Practices for a Development Environment (241), Comparison Matrix (246); Administration's Who Should Read This Document (51), Clearing a Data Grid Definition (60), String Encoding (71), Building a Docker Image (161), Starting a State Keeper (199), Development Environment (222), Designing a Data Grid (286); Programming's SQL Identifiers (138); the guide pages of Concepts (75) and Administration (151); API Reference (47); and Documentation and Support (247).

## Decisions for you

- **Programming with ActiveSpaces:** depth 2 (8 pages, Querying 5,963) as drafted, or depth 3 (34 pages, largest 5,054, many very short pages). The draft prefers 2.
- **Administration / Disaster Recovery (4,323):** one page as drafted (under 5,000), or a chapter entry at depth 2 for 12 pages (largest 780: Playbook, Gridset Configuration, Activating the Mirror Grid ...).

## Exact titles

All 6 entries match `output/en-us-tib-activespaces/tibco-activespaces-enterprise-edition/5.2.1/toc.yml` exactly: 6 of 6 matched, 0 unmatched (`policy_for` -> `for_version("5.2.1")` -> `packer.depth_nodes`, loading the YAML file itself). No entry title has a non-ASCII character; the no-break spaces in "The SQL UPDATE Statement" and "Trust File (TIBCO FTL-Generated Certificates)" and the registered sign in the home row are in rows no entry names. The letter-case folder fixes (Installation/, Administration/, Concepts/, Security/) do not affect any title. 4.10.0 to 5.2.0 get no entries.

Measured read-only, in memory (`pack`, `depth_nodes`, `project`). Script: `C:/tmp/ai-grouping-as/run.py`, using `C:/tmp/ai-grouping/measure.py`.
