# BW Plug-in for AI 6.0.2: pages by menu depth, a draft for review (17 Nov 2026)

Phase 81 (AI-assisted grouping). This is a draft only. The entries are in `tibco-businessworks-plug-in-for-ai-6.0.2.yaml`, as a **new product block**; `config/reframe.yaml` has no block for this product today (no pin, no `keep_separate`). The 8 entries are scoped `versions: ["6.0.2"]`. 6.0.2 is the newest version (Flare, family bw-plugin).

## Pin: a decision needed before reframing 6.0.2

With no block, the automatic pin is the newest Flare version. 6.0.0 and 6.0.1 were merged (7 Oct) and published when 6.0.1 was the newest, so they were laid out on 6.0.1. Now that 6.0.2 is converted, the automatic pin becomes **6.0.2**, and the next reframe would **re-cut the published 6.0.0 and 6.0.1 onto 6.0.2's layout**, with or without these entries. The entries only make 6.0.2 its own pin; they do not stop the older versions moving.

Recommendation: add `pin_layout_to: "6.0.1"` to the new block together with the entries (as Flogo was pinned to 3.0.1). Then 6.0.0 and 6.0.1 keep their layout, and 6.0.2 gets its own (Phase 81 rule). Not drafted in the YAML because it is a separate decision.

## The result (6.0.2)

| | Projected onto 6.0.1 (R1) | R1 on its own | **This draft** |
|---|---|---|---|
| Pages in the menu | 17 | 17 | **24** |
| Pages not in navigation | 2 | 2 | 2 |
| **Total pages** | 19 | 19 | **26** |
| Median page (menu pages) | 1,061 | 1,509 | **743** |
| Largest page | 3,674 | 3,163 | **4,894** (RAG LLM and Embedding Connection) |
| Pages over 5,000 words | 0 | 0 | **0** |
| Pages under 300 words | 5 | 5 | 8 |
| Pages holding only some of a parent's children | 5 | 6 | **0** |

Every TOC topic lands on a page in each layout (0 missing, 0 extra).

The pages under 300 words are landing pages and short topics: RAG Palette (41, the palette's intro), Home (109), Troubleshooting Installation (143), Error Codes (181), Installation (186), User Guide (224), Deploying Applications (234), Documentation and Support (288).

## Guides and chapters, measured

Pages (largest page in words) if the entry were set at that depth, measured with the real packer. `levels.py` reads this tree correctly (its rows carry no `#fragment`); its figures agree with these.

| guide | chapter | words | topics | menu depth | depth 1 | depth 2 | depth 3 |
|---|---|---|---|---|---|---|---|
| **Installation** | (whole guide) | 4,789 | 21 | 4 | 1 (4,789) | 7 (1,380) | 18 (982) |
| Installation | Installation Requirements | 425 | 1 | 1 | 1 (425) | | |
| Installation | Installing by Using the TIBCO Universal Installer | 1,380 | 7 | 3 | 1 (1,380) | 4 (982) | 7 (294) |
| Installation | Installing by Using an Update Site | 1,203 | 4 | 2 | 1 (1,203) | 4 (373) | |
| Installation | Uninstalling by Using the TIBCO Universal Installer | 865 | 4 | 2 | 1 (865) | 4 (341) | |
| Installation | Uninstalling by Using an Update Site | 587 | 3 | 2 | 1 (587) | 3 (245) | |
| Installation | Troubleshooting Installation | 143 | 1 | 1 | 1 (143) | | |
| **User Guide** | (whole guide) | 16,993 | 29 | 4 | 1 (16,993) | 8 (6,832) | 28 (3,163) |
| User Guide | Getting Started | 1,275 | 7 | 3 | 1 (1,275) | 6 (331) | 7 (331) |
| User Guide | Deploying Applications | 234 | 2 | 2 | 1 (234) | 2 (149) | |
| User Guide | RAG LLM and Embedding Connection | 4,894 | 3 | 2 | 1 (4,894) | 3 (3,163) | |
| User Guide | RAG Palette | 6,832 | 6 | 2 | 1 (6,832) | 6 (2,056) | |
| User Guide | Working with Sample Projects | 2,731 | 5 | 2 | 1 (2,731) | 5 (1,002) | |
| User Guide | Log Management | 622 | 4 | 2 | 1 (622) | 4 (236) | |
| User Guide | Error Codes | 181 | 1 | 1 | 1 (181) | | |

Top-level single topics (Home 109, What's New 951, Documentation and Support 288, Legal and Third-Party Notices 550) are one page each under R1; they need no entry.

## Choice per chapter

| Guide | Chapter | Depth | Pages | Largest | Reason |
|---|---|---|---|---|---|
| Installation | (whole guide) | **2** | 7 | 1,380 | One page per method: a reader installs with the Universal Installer or an update site, not both. Each install/uninstall chapter keeps its modes (GUI, console, silent) together. See the decision below. |
| User Guide | Getting Started | 1 | 1 | 1,275 | One tutorial, read in order (project, connection, process, test). Depth 2 would give 6 pages of 75 to 331 words. |
| User Guide | Deploying Applications | 1 | 1 | 234 | One short task. |
| User Guide | RAG LLM and Embedding Connection | 1 | 1 | 4,894 | Under 5,000. One shared-resource reference; its two children (RBAC policy file format 524, ActiveSpaces vector database 1,207) are about configuring that connection. Depth 2 would leave a 3,163-word parent page split from them. |
| User Guide | RAG Palette | **2** | 6 | 2,056 | Over 5,000 whole (6,832). Reference: one page per activity (Chunk, Ingest, Agent Step, Query, Vector Store Operation), as for CICS's palette. The palette's own page is 41 words. |
| User Guide | Working with Sample Projects | 1 | 1 | 2,731 | Under 5,000; the import step and three samples belong together. |
| User Guide | Log Management | 1 | 1 | 622 | One topic: levels, setting them, exporting. |
| User Guide | Error Codes | 1 | 1 | 181 | One topic. |

## Pages over 5,000 words

None. The largest is RAG LLM and Embedding Connection at 4,894.

## Decisions for you

- **Pin:** add `pin_layout_to: "6.0.1"` in the same block (see above). Without it the published 6.0.0 and 6.0.1 are regrouped.
- **Installation:** the draft makes one page per method (depth 2, 7 pages, largest 1,380). The alternative is the whole guide as one page (depth 1, 4,789 words), just under the target.

## Exact titles

All 8 entries match `output/en-us-tib-bw-plugin/tibco-businessworks-plug-in-for-ai/6.0.2/toc.yml` exactly: 8 of 8 matched, 0 unmatched (`policy_for` with the draft block added, `for_version("6.0.2")`, `packer.depth_nodes`). No entry title has a non-ASCII character; the registered sign is only in the home row, which no entry names. 6.0.1 and 6.0.0 pick up no entry and their policy keys are unchanged.

Measured read-only, in memory (`pack`, `depth_nodes`, `project`). Script: `C:/tmp/ai-grouping-ai602/check.py` (uses `C:/tmp/ai-grouping/measure.py`).
