# Flogo 3.0.2: pages by menu depth, a draft for review (15 Nov 2026)

Phase 81 (AI-assisted grouping). This is a draft only. The entries are in `proposed-depth-entries-2026-11-15.yaml`; nothing is in `config/reframe.yaml`. The 15 entries are scoped `versions: ["3.0.2"]`, so 3.0.2 becomes its own pin. 2.26.6 to 3.0.1 keep projecting onto 3.0.1 packed by R1, and their policy keys are unchanged (checked in memory).

## The result

| | Today: projected onto 3.0.1 (R1) | R1 on its own | **This draft** | 3.0.1 as published |
|---|---|---|---|---|
| Pages in the menu | 196 | 199 | **206** | 186 |
| Pages not in navigation (the same in every 3.0.2 column) | 23 | 23 | 23 | 63 |
| **Total pages** | 219 | 222 | **229** | 249 |
| Median page (menu pages) | 1,340 | 1,323 | **623** | 1,207 |
| 90th percentile | 2,783 | 2,799 | 3,665 | |
| Largest page | 6,065 | 6,065 | **12,091** (Activities) | 3,648 |
| Pages over 5,000 words | 2 | 2 | **10** | 0 |
| Pages under 300 words | 45 | 49 | 73 | 46 |
| Pages holding only some of a parent's children | 75 | 73 | **0** | 70 |

Every TOC topic lands on a page in each layout (0 missing). Menu rows that point into a merged page become sections (`page.md#anchor`), as for EMS.

## Guides and chapters, measured

Counts are pages (largest page in words) if the entry were set at that depth. They are measured with the real packer, so R4.2 is included: a subtree spanning two source folders goes one level deeper. That is why some chapters give several pages even at depth 1.

| guide | chapter | words | topics | menu depth | depth 1 | depth 2 | depth 3 | depth 4 |
|---|---|---|---|---|---|---|---|---|
| **Installation** | (whole guide) | 3,039 | 7 | 3 | 1 (3,039) | 6 (1,925) | 7 (1,361) | 7 (1,361) |
| **Migration Guide** | (whole guide) | 1,767 | 5 | 2 | 1 (1,767) | 5 (682) | | |
| **User Guide** | Introduction | 5,753 | 8 | 3 | 4 (4,936) | 4 (4,936) | 8 (1,501) | |
| User Guide | Designing Flogo Applications in Flogo Extension for Visual Studio Code | 59,846 | 192 | 6 | 34 (17,883) | 34 (17,883) | 80 (12,091) | 141 (3,828) |
| User Guide | License Activation and Enforcement | 1,921 | 2 | 2 | 1 (1,921) | 2 (1,659) | | |
| User Guide | TIBCO Flogo® Design Assistant - Tech Preview | 15,121 | 21 | 3 | 1 (15,121) | 8 (6,203) | 21 (6,065) | |
| User Guide | Deployment and Configuration | 31,053 | 95 | 5 | 17 (11,702) | 17 (11,702) | 33 (5,273) | 70 (5,273) |
| User Guide | Best Practices | 1,432 | 1 | 1 | 1 (1,432) | | | |
| User Guide | Performance Tuning | 3,053 | 9 | 3 | 1 (3,053) | 3 (2,481) | 9 (785) | |
| User Guide | Troubleshooting Workspace App Indexing | 169 | 1 | 1 | 1 (169) | | | |
| **Mapper Functions** | (whole guide) | 12,991 | 143 | 4 | 17 (4,092) | 17 (4,092) | 142 (355) | 143 (355) |
| Mapper Functions | Overview + 14 function groups (Array 1,471 ... String 4,092) | 115 to 4,092 | 2 to 43 | 2 to 3 | 1 each (Overview 2, R4.2) | one per function | | |
| **Connectors User Guide** | Introduction | 63 | 1 | 1 | 1 (63) | | | |
| Connectors User Guide | Using Connectors | 3,665 | 6 | 2 | 1 (3,665) | 6 (3,101) | | |
| Connectors User Guide | Supported Flogo Connectors (46 connectors) | 133,711 | 328 | 5 | 47 (6,634) | 47 (6,634) | 281 (2,370) | 326 (2,370) |
| **Security Guide** | (whole guide) | 346 | 4 | 2 | 1 (346) | 4 (186) | | |

Six top-level single pages (Tech Preview home, What's New, Disclaimer, Flogo Samples, Documentation and Support, Legal) need no entry.

## Choice per chapter

| Guide | Chapter | Depth | Pages | Largest | Reason |
|---|---|---|---|---|---|
| Installation | (whole guide) | 1 | 1 | 3,039 | Modest: one page, as the criteria ask. |
| Migration Guide | (whole guide) | 1 | 1 | 1,767 | Short, and read as one task (moving to 3.x). |
| User Guide | Introduction | 1 | 4 | 4,936 | Kept whole. R4.2 still gives the REST API tutorial (another folder) its own page, which reads as one scroll. |
| User Guide | Designing Flogo Applications ... | **3** | 80 | 12,091 | A guide inside the guide (60k words). Depth 2 would make "General Category Triggers, Activities, and Connections" one 17,883-word page across three types, and Data Mappings 12,252. At 3: Triggers, Activities and Connections are one reference page each, and Flows splits per task. |
| User Guide | License Activation and Enforcement | 1 | 1 | 1,921 | One topic. |
| User Guide | TIBCO Flogo® Design Assistant - Tech Preview | 2 | 8 | 6,203 | 15k words. One page per section: Tools is a reference listing (14 tools, 6,203); the CLI reference is one topic (6,065). |
| User Guide | Deployment and Configuration | **3** | 33 | 5,273 | At 2, Monitoring is one 11,702-word page across six areas. At 3: one page per container platform, per configuration provider (Consul, AWS, Azure ...), and per monitoring area (Monitoring app, Flow State Manager, metrics, tracing). |
| User Guide | Best Practices | 1 | 1 | 1,432 | One topic. |
| User Guide | Performance Tuning | 1 | 1 | 3,053 | Reads as one topic: the tuning variables plus CPU and memory monitoring. |
| User Guide | Troubleshooting Workspace App Indexing | 1 | 1 | 169 | One topic. |
| Mapper Functions | (guide at depth 2) | 2 | 17 | 4,092 | API function listing: one reference page per function group, never one per function. A single guide entry, equal to each group at depth 1. |
| Connectors User Guide | Introduction | 1 | 1 | 63 | One topic. |
| Connectors User Guide | Using Connectors | 1 | 1 | 3,665 | Prerequisites plus create, edit and delete a connection: one task. |
| Connectors User Guide | Supported Flogo Connectors | 2 | 47 | 6,634 | One page per connector (connection, triggers, activities together). Depth 3 would give 281 pages, mostly one per activity. |
| Security Guide | (whole guide) | 1 | 1 | 346 | Short. |

## Pages over 5,000 words (10)

| Page | Words | Why acceptable |
|---|---|---|
| Activities (General category) | 12,091 | Reference listing of 24 activities, one heading each, like EMS's command listing (11,698). See decision A. |
| Mapping Different Types of Data | 7,245 | One topic, one heading per data type (Mapping Arrays is 3,828 of it). Readers scan it for their type. |
| Oracle Database | 6,634 | One connector. |
| IBM MQ | 6,354 | One connector. |
| Design Assistant Tools | 6,203 | Reference listing of 14 tools. |
| Design Assistant CLI Reference | 6,065 | A single source topic, so it cannot be split. It is over 5,000 today too. |
| Agentic AI - Tech Preview | 5,977 | One connector. |
| PostgreSQL | 5,920 | One connector. |
| Microsoft SQL Server | 5,861 | One connector. |
| Building Flogo App Executable and Docker Image Using Flogo - App Build CLI | 5,273 | A single source topic, so it cannot be split. It is over 5,000 today too. |

## Decisions for you

- **A. Activities (12,091 words, 24 activities).**
  - **Draft:** one reference page.
  - **Alternative:** "Designing ..." at depth 4: 141 pages instead of 80, largest 3,828, nothing over 5,000. A depth entry reaches chapters only, never sections, so depth 4 would also split every other section of the chapter.
- **B. Small pages in "Designing ..." at depth 3.** 42 of its 80 pages are under 300 words. For example, "Creating and Managing a Flogo App" becomes 9 pages of 29 to 335 words. The cause is the same chapter-only limit: one depth for all 11 sections. At depth 2 those small sections stay whole, but the two pages of 17,883 and 12,252 words come back. The draft accepts the small pages.
- **C. Five connectors over 5,000 words.** Each stays one page. To split them, every connector would have to split (281 pages).

## Exact titles

Every entry matches `output/.../tibco-flogo/3.0.2/toc.yml` exactly: 15 of 15 matched, 0 unmatched. Only one entry title has a non-ASCII character: `TIBCO Flogo\u00ae Design Assistant - Tech Preview` (registered sign), escaped in the YAML. Titles with no-break spaces (`CLI\u00a0Reference`, `CPU\u00a0and Memory Monitoring`, `SAP\u00a0Solutions`, `TIBCO\u00a0Cloud Messaging`) are sections, not named by any entry.

Measured read-only, in memory, with `src/docushift/reframe/packer.py` (`pack`, `depth_nodes`, `project`). Scripts are in `C:/tmp/ai-grouping/`.
