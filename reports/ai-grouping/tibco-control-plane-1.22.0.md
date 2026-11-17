# Control Plane 1.22.0: pages by menu depth, a draft for review (17 Nov 2026)

Phase 81 (AI-assisted grouping). This is a draft only. The 53 entries are in `tibco-control-plane-1.22.0.yaml`; nothing is in `config/reframe.yaml`. They go under the existing `tibco-control-plane:` block (pinned to 1.20.0). Every entry is scoped `versions: ["1.22.0"]`, so 1.22.0 becomes its own pin. The other 20 converted versions (1.3.0 to 1.21.0) keep projecting onto 1.20.0, and their policies are unchanged (checked in memory).

## The result

| | Today: projected onto 1.20.0 | R1 on its own | **This draft** |
|---|---|---|---|
| Pages in the menu | 148 | 222 | **336** |
| Pages not in navigation (the same in every column) | 18 | 18 | 18 |
| **Total pages** | 166 | 240 | **354** |
| Median page | 2,325 | 1,060 | **440** |
| Largest page | 9,250 | 9,250 | 9,250 (Previous Versions Release Notes, one topic) |
| Pages over 5,000 words | 4 | 4 | **7** |
| Pages under 300 words | 17 | 70 | **132** |
| Pages holding only some of a parent's children | 84 | 75 | **0** |

Every TOC topic lands on a page in each layout (0 missing, 0 extra).

**Why the page count more than doubles.** Three causes, in order of size:
1. **Source-folder splits (R4.2).** The 1.22.0 help is one Flare project with sub-projects (Control Tower, BW5, BW6, Flogo, EMS, Developer Hub) and topics spread over several folders. A subtree spanning two folders goes one level deeper whatever its entry says. That alone makes R1 lay out 222 pages, not 148. Installation (16 pages, 12 under 300 words), Data Plane Configuration (17, 13 under 300), Release Notes (8), Disaster Recovery (5) and Setting up Kubernetes Infrastructure (4) split this way at every depth.
2. **Control Tower products at depth 4** (54 pages): one page per CI/CD API area instead of two API pages of 19,520 and 16,174 words. See decision A.
3. **BW5, Flogo and Developer Hub capabilities at depth 3** (33 + 36 + 24 pages): their sections are 8,000 to 14,000 words at depth 2.

## Guides and chapters, measured

Pages (largest page in words) if the entry were set at that depth, measured with the real packer (`packer.pack`, `depth_nodes`), so R4.2 is included. `levels.py` was not used for the counts: the packer is what reframe runs, and it avoids `levels.py`'s #fragment miscount. Menu depth counts the guide or chapter itself as 1.

| guide | chapter | words | topics | menu depth | depth 1 | depth 2 | depth 3 | depth 4 |
|---|---|---|---|---|---|---|---|---|
| **Release Notes** | (whole guide) | 15,586 | 8 | 2 | 8 (9,250) | 8 (9,250) | | |
| **TIBCO Control Plane and Data Plane Overview** | (whole guide) | 1,579 | 3 | 2 | 1 (1,579) | 3 (669) | | |
| **Requirements and Prerequisites** | (whole guide) | 5,975 | 12 | 3 | 6 (3,469) | 6 (3,469) | 12 (1,151) | |
| **Installation** | (whole guide) | 6,930 | 23 | 3 | 16 (2,857) | 16 (2,857) | 23 (2,704) | |
| **Upgrades** | (whole guide) | 3,247 | 13 | 3 | 5 (1,210) | 5 (1,210) | 13 (734) | |
| **Rollback** | (whole guide) | 664 | 3 | 2 | 3 (410) | 3 (410) | | |
| **Getting Started** | (whole guide) | 3,036 | 9 | 2 | 1 (3,036) | 9 (1,222) | | |
| **TIBCO Enterprise Smart System Agent (TESSA™)** | (whole guide) | 7,674 | 13 | 2 | 1 (7,674) | 13 (1,180) | | |
| **TIBCO MCP Hub** | (whole guide) | 24,232 | 27 | 3 | 8 (7,516) | 8 (7,516) | 27 (2,069) | |
| MCP Hub | Overview; Installing; Access Tokens; Troubleshooting | 595 to 1,750 | 1 each | 1 | 1 each | | | |
| MCP Hub | Managing Gateways | 3,818 | 4 | 2 | 1 (3,818) | 4 (1,538) | | |
| MCP Hub | Managing MCP Server, tools, and registry | 7,516 | 8 | 2 | 1 (7,516) | 8 (1,285) | | |
| MCP Hub | Plugins and Governance | 7,301 | 10 | 2 | 1 (7,301) | 10 (2,069) | | |
| **TIBCO Platform CLI** | (whole guide) | 20,417 | 15 | 3 | 8 (18,153) | 8 (18,153) | 15 (5,110) | |
| Platform CLI | Installing; Concepts; Command Format; Interactive Mode; Profiles; Uninstalling | 70 to 562 | 1 to 2 | 1 to 2 | 1 each | | | |
| Platform CLI | TIBCO Platform CLI Reference | 18,153 | 7 | 2 | 1 (18,153) | 7 (5,110) | | |
| **User Management** | (whole guide) | 4,513 | 7 | 2 | 1 (4,513) | 7 (1,214) | | |
| **Setting up Kubernetes Infrastructure** | (whole guide) | 647 | 4 | 2 | 4 (253) | 4 (253) | | |
| **Registering a Data Plane** | (whole guide) | 3,230 | 4 | 2 | 1 (3,230) | 4 (2,183) | | |
| **Managing Data Planes** | (whole guide) | 4,828 | 12 | 2 | 1 (4,828) | 12 (878) | | |
| **Managing Control Tower Data Planes** | (whole guide) | 63,029 | 96 | 7 | 27 (55,970) | 27 (55,970) | 31 (32,684) | 43 (19,520) |
| Control Tower | 8 small chapters (Overview ... Native Control Tower) | 12 to 1,889 | 1 each | 1 | 1 each | | | |
| Control Tower | Data Plane Configuration | 4,133 | 18 | 4 | 17 (842) | 17 (842) | 18 (842) | 18 (842) |
| Control Tower | Control Tower Data Plane: Products | 55,970 | 69 | 6 | 1 (55,970) | 5 (32,684) | 16 (19,520) | 54 (4,212) |
| **Managing Resources** | (whole guide) | 1,732 | 10 | 3 | 1 (1,732) | 8 (601) | 10 (347) | |
| **Managing OAuth Access Tokens** | (whole guide) | 509 | 4 | 2 | 1 (509) | 4 (162) | | |
| **Managing Capabilities** | (whole guide) | 95,590 | 227 | 6 | 25 (22,066) | 25 (22,066) | 59 (14,454) | 165 (4,032) |
| Capabilities | Provisioning a Capability; Refreshing Capability; Platform Infra MCP Server | 160 to 548 | 1 each | 1 | 1 each | | | |
| Capabilities | TIBCO BusinessWorks™ 6 (Containers) | 18,521 | 45 | 4 | 1 (18,521) | 14 (6,815) | 38 (1,583) | 45 (1,583) |
| Capabilities | TIBCO BusinessWorks™ 5 (Containers) | 18,691 | 46 | 4 | 1 (18,691) | 9 (8,287) | 33 (3,388) | 46 (1,775) |
| Capabilities | TIBCO Flogo | 25,382 | 51 | 5 | 16 (8,559) | 16 (8,559) | 36 (3,233) | 45 (2,527) |
| Capabilities | TIBCO Enterprise Message Service | 9,001 | 26 | 3 | 1 (9,001) | 8 (5,370) | 26 (1,021) | |
| Capabilities | TIBCO ActiveSpaces® | 1,043 | 4 | 2 | 1 (1,043) | 4 (523) | | |
| Capabilities | TIBCO Developer Hub | 22,066 | 51 | 4 | 1 (22,066) | 4 (14,454) | 24 (4,032) | 51 (2,112) |
| **Monitoring** | (whole guide) | 2,895 | 7 | 3 | 1 (2,895) | 4 (1,405) | 7 (1,086) | |
| **Observability in TIBCO Control Plane** | (whole guide) | 13,851 | 30 | 3 | 1 (13,851) | 11 (5,160) | 30 (2,983) | |
| **TIBCO Platform Console** | (whole guide) | 7,309 | 25 | 4 | 10 (3,231) | 10 (3,231) | 24 (1,696) | 25 (1,493) |
| **Security Guide** | (whole guide) | 1,059 | 6 | 2 | 1 (1,059) | 6 (566) | | |
| **Disaster Recovery** | (whole guide) | 3,497 | 5 | 2 | 5 (1,345) | 5 (1,345) | | |
| **Legal Notices** | (whole guide) | 6,258 | 3 | 2 | 3 (5,682) | 3 (5,682) | | |

Five top-level single pages need no entry: TIBCO® Control Plane (home), Data Governance, TIBCO Control Plane MCP Server (Tech Preview), TIBCO Platform APIs, TIBCO Documentation and Support Services.

## Choice per guide and chapter

In this TOC every top-level row is a "guide" and acts like a chapter of one user guide, so the guide-level rule applies: one page unless large. Where every depth gives the same pages (R4.2), the entry states the depth that describes the result.

| Guide | Chapter | Depth | Pages | Largest | Reason |
|---|---|---|---|---|---|
| Release Notes | (guide) | 2 | 8 | 9,250 | One page per note, as R4.2 gives anyway. Previous Versions is one topic and cannot split. |
| Control Plane and Data Plane Overview | (guide) | 1 | 1 | 1,579 | Short concept guide, read as one. |
| Requirements and Prerequisites | (guide) | 2 | 6 | 3,469 | One page per requirement area; the two cluster-preparation chapters stay whole. |
| Installation | (guide) | 2 | 16 | 2,857 | One page per chapter, forced by R4.2 (12 pages under 300 words; cannot be merged). |
| Upgrades | (guide) | 2 | 5 | 1,210 | One page per chapter (control plane, capability charts, infrastructure, a capability). |
| Rollback | (guide) | 2 | 3 | 410 | Forced by R4.2. |
| Getting Started | (guide) | 1 | 1 | 3,036 | A first-run narrative (quick start, sign in, regions, home page): one scroll. |
| TESSA | (guide) | 2 | 13 | 1,180 | 7,674 words of 12 independent topics (architecture, Bedrock, guardrails, FAQ); one page each. |
| MCP Hub | Managing MCP Server, tools, and registry | 2 | 8 | 1,285 | 7,516 words, 7 separate tasks: one page per task. |
| MCP Hub | Plugins and Governance | 2 | 10 | 2,069 | 7,301 words: setup page plus one page per plugin category. |
| MCP Hub | the other 5 chapters | 1 | 1 each | 3,818 | Each one task or one topic; Managing Gateways (deploy, configure, monitor) reads as one. |
| Platform CLI | TIBCO Platform CLI Reference | 2 | 7 | 5,110 | Command reference: one page per command group, never one per command. |
| Platform CLI | the other 6 chapters | 1 | 1 each | 562 | Short. |
| User Management | (guide) | 1 | 1 | 4,513 | Under 5,000; users, groups, teams and permissions read together. |
| Setting up Kubernetes Infrastructure | (guide) | 2 | 4 | 253 | Forced by R4.2. |
| Registering a Data Plane | (guide) | 1 | 1 | 3,230 | One task with its certificate options. |
| Managing Data Planes | (guide) | 1 | 1 | 4,828 | Under 5,000. See decision C. |
| Control Tower | 8 small chapters | 1 | 1 each | 1,889 | Each a single topic. |
| Control Tower | Data Plane Configuration | 2 | 17 | 842 | Forced by R4.2 at any depth (its Managing Resources mixes two folders). |
| Control Tower | Control Tower Data Plane: Products | **4** | 54 | 4,212 | Three products (BW5 + Adapters 32,684; BW6 19,548; BusinessEvents 2,447). At 3 the two "Control Tower CI/CD APIs" sections are 19,520 and 16,174 words. At 4 each API area (applications, folders, machines, plug-ins ...) is its own page, like EMS's one page per C type. See decision A. |
| Managing Resources | (guide) | 1 | 1 | 1,732 | Short. |
| Managing OAuth Access Tokens | (guide) | 1 | 1 | 509 | Short. |
| Capabilities | Provisioning; Refreshing; Platform Infra MCP Server | 1 | 1 each | 548 | Single topics. |
| Capabilities | TIBCO BusinessWorks™ 6 (Containers) | 2 | 14 | 6,815 | Sections whole: managing apps 4,151, monitoring 2,104. The Swagger API section (6 API groups, 6,815) stays one reference page. See decision B. |
| Capabilities | TIBCO BusinessWorks™ 5 (Containers) | **3** | 33 | 3,388 | At 2, "Managing ... Applications" is one 8,287-word narrative page. At 3 it splits per task; adapter supplements (3,388) stay together. See decision B. |
| Capabilities | TIBCO Flogo | **3** | 36 | 3,233 | At 2, "Managing TIBCO Flogo apps" is 8,559 and the Data Plane APIs 7,323. At 3: one page per app task and per API group; App Configuration Management whole. |
| Capabilities | TIBCO Enterprise Message Service | 2 | 8 | 5,370 | Sections whole. "EMS Capability Navigation" is a reference of 15 UI screens (5,370): one page. |
| Capabilities | TIBCO ActiveSpaces® | 1 | 1 | 1,043 | Short. |
| Capabilities | TIBCO Developer Hub | **3** | 24 | 4,032 | At 2, Software Catalog is 14,454 and Overview 7,371. At 3: templates, import flows, catalog entities, integrations one page each. |
| Monitoring | (guide) | 1 | 1 | 2,895 | Short. |
| Observability | (guide) | 2 | 11 | 5,160 | Every chapter whole. Dashboard Cards (16 cards) is one reference page; at depth 3 it would be 17 pages of 47 to 471 words. |
| TIBCO Platform Console | (guide) | 2 | 10 | 3,231 | Chapters whole: subscriptions, user management, email server. |
| Security Guide | (guide) | 1 | 1 | 1,059 | Short. |
| Disaster Recovery | (guide) | 2 | 5 | 1,345 | Forced by R4.2: one page per cloud and plane. |
| Legal Notices | (guide) | 2 | 3 | 5,682 | Forced by R4.2. |

The Flare sub-projects that the 1.20.0 layout test found nested under "Managing Capabilities" (Flogo, BW5, BW6, EMS, Developer Hub) and under "Managing Control Tower Data Planes" each get their own chapter entry, so no capability shares a page with another and none is split part-way.

## Pages over 5,000 words (7)

| Page | Words | Why acceptable |
|---|---|---|
| Previous Versions Release Notes | 9,250 | One source topic; cannot split. Over 5,000 today too. |
| BW6 (Containers): Accessing the API Documentation with Swagger UI | 6,815 | API reference, 6 groups. Decision B. |
| Analyze Container Images and their Associated Licenses | 5,682 | One source topic. |
| EMS Capability Navigation | 5,370 | Reference of 15 UI screens. |
| Observability Dashboard Cards | 5,160 | Reference of 16 cards. |
| TIBCO BusinessWorks 6 (Containers) Commands | 5,110 | One source topic (CLI command group). |
| TIBCO BusinessWorks 5 (Containers) Commands | 5,088 | One source topic. |

## Decisions for you

Total pages in the menu with each alternative (one change at a time):

- **A. Control Tower products, depth 4 (draft, 336) or 3 (298).** At 3: 38 fewer pages, but the BW5 and BW6 "Control Tower CI/CD APIs" sections become pages of 19,520 and 16,174 words. At 4 the smaller sections split too: "Manage Application Configuration Overview" becomes 10 pages (22 to 1,032 words). A depth entry reaches chapters only, so the API sections cannot be split alone.
- **B. BW5 and BW6 at different depths.** The draft has BW6 at 2 (14 pages, API page 6,815) and BW5 at 3 (33 pages), because BW5's applications section is 8,287 words. For parallel menus: both at 3 (BW6 38 pages; total 360), or both at 2 (BW5 9 pages with an 8,287 page; total 312).
- **C. Managing Data Planes whole (draft, 4,828 words, 11 independent admin tasks).** Depth 2 gives 12 pages of 274 to 878 words (total 347). Kept whole because it is under 5,000.
- **D. TESSA at depth 2 (draft) or 1.** At 1: one 7,674-word page (total 324).
- **E. 132 pages under 300 words.** About half are forced by R4.2 (Installation, Data Plane Configuration and others) and would be small in R1 too (70 there).

## Exact titles

All 53 entries match 1.22.0's `toc.yml`: 53 of 53 matched, 0 unmatched. Validated by loading `tibco-control-plane-1.22.0.yaml` into the product block in memory and running `policy_for` → `for_version("1.22.0")` → `packer.depth_nodes`, as reframe does. Escaped in the YAML: `TESSA\u2122`, `BusinessWorks\u2122 6/5 (Containers)`, `ActiveSpaces\u00ae`, and the guide `TIBCO\u00a0MCP Hub` (no-break space). The chapter "TESSA\u00a0Overview" also has a no-break space but is not named by any entry.

Measured read-only, in memory. Scripts are in `C:/tmp/ai-grouping/cp/` (`draft.py`, `validate.py`).
