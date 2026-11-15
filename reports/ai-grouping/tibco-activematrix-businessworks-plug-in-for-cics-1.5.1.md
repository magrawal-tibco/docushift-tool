# BW Plug-in for CICS 1.5.1: pages by menu depth, a draft for review (15 Nov 2026)

Phase 81 (AI-assisted grouping). This is a draft only. The entries are in `proposed-depth-entries-2026-11-15.yaml`, as a new product block; nothing is in `config/reframe.yaml`. The 6 entries are scoped `versions: ["1.5.1"]`.

## Is R1 enough? Not as 1.5.1 is laid out today

CICS has two lines: 1.x for BusinessWorks 5 and 2.x for BusinessWorks 6. With no pin in `reframe.yaml`, the automatic pin per engine applies. The newest Flare version is **2.5.0**, so **1.5.1 is projected onto 2.5.0's layout**. The two share only the 3 template pages. 1.5.1's 77 other topics are therefore packed as flat runs in reading order, which cut sections in half:
- z/OS installation is split across two pages.
- "CICS Interaction" ends one page, and its tabs start the next.
- CICS Container Interaction's tabs share a page with all of Pool Manager.
- Samples, Security Modes and TLS run together on one page.

**R1 on its own** would be close to this draft (15 menu pages). It still puts two chapter pairs on one page: z/OS with Plug-in Data Sets, and Samples with Security Modes. And 1.5.1 only gets R1 on its own if something changes its pin. Depth entries do that (Phase 81: a version with entries is its own pin) and also fix the two joins. So the entries are worth having, even for a small guide. 2.5.0 and 2.4.1 are unchanged (policy keys checked in memory).

## The result

| | Today: projected onto 2.5.0 | R1 on its own | **This draft** |
|---|---|---|---|
| Pages in the menu | 10 | 15 | **17** |
| Pages not in navigation | 12 | 12 | 12 |
| **Total pages** | 22 | 27 | **29** |
| Median page (menu pages) | 1,666 | 986 | **715** |
| 90th percentile | 2,958 | 2,055 | 2,055 |
| Largest page | 2,996 | 2,625 | **2,396** |
| Pages over 5,000 words | 0 | 0 | **0** |
| Pages under 300 words | 2 | 6 | 7 |
| Pages holding only some of a parent's children | 4 | 2 | **0** |

The pages under 300 words are the landing pages (Home 29, Installation 15, User Guide 24, CICS Palette 14), Product Overview (192), Plug-in Data Sets (262) and Documentation and Support (292).

## Guides and chapters, measured

Note: `scratch/ai-grouping/levels.py` reads this tree as nearly empty (Installation 15 words, User Guide 24). Its rows carry a self-anchor (`Installation_Overview.md#installation-overview`), and the script skips any row with a fragment. The packer counts words by path, so the figures below use the packer's own counts.

| guide | chapter | words | topics | menu depth | depth 1 | depth 2 | depth 3 |
|---|---|---|---|---|---|---|---|
| **Installation** | (whole guide) | 4,542 | 35 | 4 | 1 (4,542) | 4 (2,363) | 14 (874) |
| Installation | Installation on Open Systems | 1,902 | 16 | 3 | 1 (1,902) | 5 (683) | 16 (301) |
| Installation | Installation on z/OS | 2,363 | 17 | 3 | 1 (2,363) | 7 (874) | 17 (874) |
| Installation | Plug-in Data Sets | 262 | 1 | 1 | 1 (262) | | |
| **User Guide** | (whole guide) | 10,419 | 42 | 4 | 1 (10,419) | 6 (6,921) | 16 (2,396) |
| User Guide | Product Overview | 192 | 1 | 1 | 1 (192) | | |
| User Guide | CICS Palette | 6,921 | 22 | 3 | 1 (6,921) | 5 (2,396) | 22 (1,444) |
| User Guide | Sample ActiveMatrix BusinessWorks Projects | 715 | 5 | 3 | 1 (715) | 3 (604) | 5 (333) |
| User Guide | Security Modes for z/OS Components | 1,019 | 7 | 3 | 1 (1,019) | 3 (586) | 7 (385) |
| User Guide | Transport Layer Security | 1,548 | 6 | 3 | 1 (1,548) | 3 (979) | 6 (638) |

## Choice per chapter

| Guide | Chapter | Depth | Pages | Largest | Reason |
|---|---|---|---|---|---|
| Installation | (whole guide) | **2** | 4 | 2,363 | Two platforms with different readers: one page for Open Systems (1,902) and one for z/OS (2,363), plus Plug-in Data Sets (262) and the guide's landing page. See the decision below. |
| User Guide | Product Overview | 1 | 1 | 192 | One topic. |
| User Guide | CICS Palette | 2 | 5 | 2,396 | Reference: one page per palette resource or activity (Region Shared Resource 1,470, CICS Interaction 2,396, Container Interaction 2,055, Pool Manager 986), each with its tabs. Whole, it would be 6,921 words over four unrelated items. |
| User Guide | Sample ActiveMatrix BusinessWorks Projects | 1 | 1 | 715 | One task. |
| User Guide | Security Modes for z/OS Components | 1 | 1 | 1,019 | One topic: the three modes and how to run them. |
| User Guide | Transport Layer Security | 1 | 1 | 1,548 | One task: RACF and the project configuration. |

## Pages over 5,000 words

None.

## Decision for you

- **Installation:** the draft makes one page per platform (depth 2, 4 pages). The alternative is the whole guide as one page (depth 1, 4,542 words), which is still modest, but a reader installs on one platform, not both.

## Exact titles

All 6 entries match `output/.../tibco-activematrix-businessworks-plug-in-for-cics/1.5.1/toc.yml` exactly: 6 of 6 matched, 0 unmatched. No entry title has a non-ASCII character. The trademark sign is only in the home row's title, which no entry names.

Measured read-only, in memory (`pack`, `depth_nodes`, `project`). Scripts are in `C:/tmp/ai-grouping/`.
