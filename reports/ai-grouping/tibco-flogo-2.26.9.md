# Flogo 2.26.9: pages by menu depth, a draft for review (15 Nov 2026)

Phase 81 (AI-assisted grouping). This is a draft only. The entries are in `proposed-depth-entries-2026-11-15.yaml`; nothing is in `config/reframe.yaml`. The 13 entries are scoped `versions: ["2.26.9"]`, so 2.26.9 becomes its own pin. The published versions (2.26.6 to 3.0.1) keep projecting onto 3.0.1, and their policy keys are unchanged (checked in memory). 2.26.8's `keep_separate` (SQL Direct) is scoped to 2.26.8 and does not reach 2.26.9.

The method is the same as 3.0.2 (`tibco-flogo-3.0.2.md`). The 2.x guides have nearly the same chapters, so the choices match, with two differences:
- Introduction is depth 2 here. In 2.26.9 the REST API tutorial sits in the same folder as Concepts, so depth 1 would join them into one page; depth 2 keeps the tutorial its own page, as in 3.0.2.
- There is no Migration Guide and no "Troubleshooting Workspace App Indexing". "Migrating Flogo Assets from TIBCO Cloud Integration" is a one-topic guide and needs no entry.

## The result

| | Today: projected onto 3.0.1 (R1) | R1 on its own | **This draft** |
|---|---|---|---|
| Pages in the menu | 217 | 194 | **214** |
| Pages not in navigation | 40 | 40 | 40 |
| **Total pages** | 257 | 234 | **254** |
| Median page (menu pages) | 1,002 | 1,297 | **538** |
| 90th percentile | 2,750 | 2,824 | 3,252 |
| Largest page | 6,228 | 6,228 | **11,876** (Activities) |
| Pages over 5,000 words | 1 | 1 | **8** |
| Pages under 300 words | 63 | 49 | 80 |
| Pages holding only some of a parent's children | 93 | 68 | **1**\* |

\* Not a real split. "Flow Input and Output Tab" is listed twice in 2.26.9's User Guide, under Flows and under App Schemas. The second menu row points to the first page (dedupe within a guide), so the App Schemas page holds 2 of its 3 listed children. Every TOC topic lands on a page in each layout (0 missing).

## Guides and chapters, measured

Pages (largest page in words) at each depth, from the real packer, with R4.2 included.

| guide | chapter | words | topics | menu depth | depth 1 | depth 2 | depth 3 | depth 4 |
|---|---|---|---|---|---|---|---|---|
| **Installation** | (whole guide) | 3,013 | 7 | 3 | 1 (3,013) | 6 (1,925) | 7 (1,361) | 7 (1,361) |
| **User Guide** | Introduction | 4,211 | 3 | 2 | 1 (4,211) | 3 (3,520) | | |
| User Guide | Designing Flogo Applications in Flogo Extension for Visual Studio Code | 60,156 | 196 | 6 | 57 (17,589) | 57 (17,589) | 92 (11,876) | 149 (3,450) |
| User Guide | License Activation and Enforcement | 1,888 | 2 | 2 | 1 (1,888) | 2 (1,626) | | |
| User Guide | TIBCO Flogo® Design Assistant - Tech Preview | 12,990 | 21 | 3 | 1 (12,990) | 8 (6,228) | 21 (6,228) | |
| User Guide | Deployment and Configuration | 30,054 | 94 | 5 | 16 (11,761) | 16 (11,761) | 32 (4,818) | 69 (4,818) |
| User Guide | Best Practices | 1,422 | 1 | 1 | 1 (1,422) | | | |
| User Guide | Performance Tuning | 3,056 | 9 | 3 | 1 (3,056) | 3 (2,493) | 9 (785) | |
| **Mapper Functions** | (whole guide) | 13,291 | 145 | 4 | 17 (4,392) | 17 (4,392) | 144 (355) | 145 (355) |
| Mapper Functions | Overview + 14 function groups (Array 1,471 ... String 4,392) | 115 to 4,392 | 2 to 45 | 2 to 3 | 1 each (Overview 2, R4.2) | one per function | | |
| **Connectors User Guide** | Introduction | 63 | 1 | 1 | 1 (63) | | | |
| Connectors User Guide | Using Connectors | 3,811 | 6 | 2 | 1 (3,811) | 6 (3,319) | | |
| Connectors User Guide | Supported Flogo Connectors | 135,529 | 329 | 5 | 47 (7,556) | 47 (7,556) | 283 (2,368) | 327 (2,368) |
| **Security Guide** | (whole guide) | 346 | 4 | 2 | 1 (346) | 4 (186) | | |

## Choice per chapter

| Guide | Chapter | Depth | Pages | Largest | Reason |
|---|---|---|---|---|---|
| Installation | (whole guide) | 1 | 1 | 3,013 | Modest: one page. |
| User Guide | Introduction | **2** | 3 | 3,520 | Concepts and the REST API tutorial are different reads; keeps the tutorial a page of its own, as in 3.0.2. |
| User Guide | Designing Flogo Applications ... | **3** | 92 | 11,876 | As 3.0.2. Depth 2 gives one 17,589-word page across triggers, activities and connections. At 3, each is one reference page. |
| User Guide | License Activation and Enforcement | 1 | 1 | 1,888 | One topic. |
| User Guide | TIBCO Flogo® Design Assistant - Tech Preview | 2 | 8 | 6,228 | Tools as one reference page (4,523); the CLI reference is one topic. |
| User Guide | Deployment and Configuration | **3** | 32 | 4,818 | As 3.0.2. Depth 2 makes Monitoring one 11,761-word page. |
| User Guide | Best Practices | 1 | 1 | 1,422 | One topic. |
| User Guide | Performance Tuning | 1 | 1 | 3,056 | Reads as one topic. |
| Mapper Functions | (guide at depth 2) | 2 | 17 | 4,392 | One reference page per function group. |
| Connectors User Guide | Introduction | 1 | 1 | 63 | One topic. |
| Connectors User Guide | Using Connectors | 1 | 1 | 3,811 | One task. |
| Connectors User Guide | Supported Flogo Connectors | 2 | 47 | 7,556 | One page per connector. |
| Security Guide | (whole guide) | 1 | 1 | 346 | Short. |

## Pages over 5,000 words (8)

| Page | Words | Why acceptable |
|---|---|---|
| Activities (General category) | 11,876 | Reference listing of 24 activities (decision A in the 3.0.2 draft). |
| Agentic AI - Tech Preview | 7,556 | One connector. It is 1,600 words longer than in 3.0.2. |
| Oracle Database | 6,447 | One connector. |
| Design Assistant CLI Reference | 6,228 | A single source topic, over 5,000 today too. |
| IBM MQ | 6,080 | One connector. |
| PostgreSQL | 5,954 | One connector. |
| Microsoft SQL Server | 5,890 | One connector. |
| Oracle MySQL | 5,002 | One connector. |

## Decisions for you

The same as 3.0.2:
- **A.** Activities stays one page (11,876 words); the alternative is "Designing ..." at depth 4, 149 pages instead of 92, largest 3,450.
- **B.** Small pages from "Designing ..." at depth 3: 51 of its 92 pages are under 300 words. Entries reach chapters only, so this chapter cannot be deepened in some sections and kept whole in others.
- **C.** Seven connectors over 5,000 words, each one page.

## Exact titles

Every entry matches `output/.../tibco-flogo/2.26.9/toc.yml` exactly: 13 of 13 matched, 0 unmatched. The only non-ASCII character in an entry is `TIBCO Flogo\u00ae Design Assistant - Tech Preview`, escaped in the YAML. In 2.26.9 the CLI reference title has a plain space, not 3.0.2's no-break space; it is a section, not named by any entry.

Measured read-only, in memory (`pack`, `depth_nodes`, `project`). Scripts are in `C:/tmp/ai-grouping/`.
