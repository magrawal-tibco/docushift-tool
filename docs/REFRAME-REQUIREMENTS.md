# Reframe — Requirements

Status: draft for DocuShift integration planning
Audience: engineer or agent planning Reframe's integration into DocuShift

---

## 1. What Reframe is

**Reframe merges granular Markdown topics into fewer, larger, editorially coherent pages,
without breaking deep links or navigation.**

MadCap Flare authors content as very small topics. When DocuShift converts a Flare source to
Markdown, that granularity carries over — in the reference corpus (TIBCO EMS 10.5.1) the median
topic is ~107 words across 1,441 topic files. Files that small cost more in scaffolding
(frontmatter, unique slug, TOC node, directory slot, redirect entry) than they carry in content.

Reframe packs those topics into merged pages, turning each former topic into an anchored `##`
section on its new page.

### Why this matters — read this before tuning anything

**The DocuShift conversion is a one-time migration. After it runs, Markdown is the permanent
authoring source and writers edit it directly in git.**

Two consequences that drive every requirement below:

1. **The optimization goal is writer maintainability**, not retrieval quality and not purely
   crawl-surface reduction. A writer updating one concept currently opens a dozen files; after
   Reframe they open one and can see the whole narrative.
2. **Every layout decision is permanent.** Reframe cannot be re-run to fix a bad boundary —
   by then the pages are hand-edited and the URLs are published. A bad merge is a manual
   refactor plus a broken link, not a config change. Correctness and reviewability outrank
   throughput.

---

## 2. Hard constraints

| # | Constraint |
|---|---|
| **C1** | **Reframe runs only for the MadCap Flare conversion engine.** For every other engine it must no-op and pass its input through untouched. |
| **C2** | The engine check must exist **inside Reframe**, not only in the pipeline orchestrator. Reframe is independently runnable by design, and a standalone run is exactly when someone points it at the wrong doc set. |
| **C3** | Version scope comes from DocuShift's **existing conversion-eligibility mechanism**. Reframe must not introduce its own version-selection policy. |
| **C4** | Reframe must never write to its input tree. Source is read-only. |
| **C5** | Output must be **deterministic** — two runs over identical input produce byte-identical output. |

---

## 3. Scope and non-goals

**In scope**
- Packing topics into merged pages
- Anchor generation and preservation of every former topic as an addressable target
- Rewriting `toc.yml` to retain the full original hierarchy
- Rewriting internal links and asset paths
- Emitting a 301 redirect map
- Emitting a review queue of pages needing human editorial judgment

**Explicitly not in scope**
- Deciding the end state of reference-list pages — flagged for writers, never auto-resolved (see R6)
- Splitting oversized source topics — flagged, not split
- Fixing pre-existing conversion defects (see §8)
- Any retrieval/RAG concern
- Cross-version content deduplication or canonicalization

---

## 4. Functional requirements

### R1 — Packing

Walk the source `toc.yml` in TOC order. **A page is a subtree, never a cut through the middle
of a sibling list.**

Parent-leads rule, applied top-down to each node:
- If the node's whole subtree is **≤ MAX_WORDS** *and* sits in one source directory (R4.2), it
  becomes one page.
- Otherwise the node becomes a page of its own body, and its children are grouped **in TOC
  order** into pages holding one or more *whole consecutive* child-subtrees of that one parent.
  A child whose own subtree still does not fit recurses by the same rule.

> **Amended 30 Sep 2026 (planning.md Phase 28).** The rule was bottom-up and, on overflow,
> packed a subtree's contents greedily without regard to whose children they were. Measured on
> the source TOCs, that put topics from more than one parent on **27 of ActiveSpaces' 46 pages
> and 67 of EMS' 124** — a majority of merged pages were arbitrary sibling runs with no single
> topic they were about, which is why no page could carry a meaningful H1. The cost of the new
> rule is about a fifth more pages (46 → 56, 124 → 160). Refusing to group siblings *at all*
> was measured too and is far worse: 119 and 628 pages, median page 416 and 159 words.

**R1.1 — Top-level TOC items are hard boundaries.** A guide must never merge into a sibling
guide. This is non-negotiable; see §7 for what happens without it.

**R1.2 — MAX_WORDS is a cap, never a target.** It may force a split. It must **not** force a
join. Do not merge sibling subtrees merely to reach some minimum size.

> This is the main behavioural change from the proof-of-concept, which carried a `MIN_WORDS`
> tunable. For a maintenance goal a small page that is one coherent conceptual unit is
> *correct*, and padding it with an unrelated sibling makes the file worse to maintain.
> `MIN_WORDS` should not be reimplemented. (In the POC it was declared but never referenced,
> so removing it is also a no-op behaviourally.)

**R1.3 — The cap is soft in one direction.** A single source topic larger than MAX_WORDS becomes
an oversized page on its own. Reframe must not split topic bodies. Flag it instead (R6).

**R1.4 — Layout stability across versions.** If conversion eligibility returns more than one
version of the *same* doc set, their layouts must be pinned to a single reference version's
topic→page mapping, with topics absent from a given version simply omitted.

> Rationale: greedy packing is chaotic. One topic growing by 50 words can push it past the cap,
> bump it to the next page, and cascade every subsequent boundary in that guide. Unpinned, two
> versions produce non-corresponding files, and porting a fix across versions stops being a
> clean diff — permanently, since these trees are hand-authored from then on.

### R2 — Anchors

Every former topic becomes an anchored heading on its merged page, at the level its place
in the tree gives it (R2.1).

> **Amended 30 Sep 2026 (planning.md Phase 28).** This read "every former topic becomes
> `## {Heading}`" — a flat list of siblings, whatever the TOC had nested. That was written
> when a page was a *run* of topics; now a page is a *subtree*, so the levels carry the
> nesting and the page's root topic supplies its one H1.

- **Slug rule:** take the source filename without extension, lowercase it, replace each run of
  `[^a-z0-9]+` with `-`, strip leading/trailing `-`.
- **Dedup rule:** if the slug is taken, append `-2`, `-3`, … **looping until unique.** A single
  suffix attempt is insufficient — see §7.
- **Uniqueness scope:** must be unique within a page. (Global uniqueness is not required,
  though the reference corpus happens to achieve it.)

> *As built (Phase 29):* no anchor is emitted. The publishing platform ignores `<a id>`
> markers and generates each anchor from the **heading text** — lowercased, punctuation
> deleted, spaces to `-` — numbering a repeated heading `-1`, `-2`, … across the whole page.
> So the slug and dedup rules above are not Reframe's to choose: it *predicts* the platform's
> answer (`utils/anchors.py`), over every heading on the page, sub-headings included, and
> every TOC row, redirect, CSH value and link fragment uses that prediction. The rule still
> loops (`-1`, `-2`, …) and is still unique within a page.

**R2.1 — Heading shift.** Each topic is given a **level**: the page's root topic takes 1, and
every other topic one below its nearest ancestor *that is also on the page*. A page holding
more than one whole sibling subtree drops every subtree after the first by one further level,
so the second never collides with the first's H1.

In each topic body the first `#` H1 becomes the anchored heading at that level; every other
heading moves by the same offset; everything caps at H6. If a topic has no H1, prepend
`{level hashes} {TOC title}` with its anchor above it.

> *As built (Phase 29):* nothing is written above the heading; its anchor is the platform's
> slug of the heading text (R2's as-built note).

- Depth is counted in **what is emitted**, not in what the TOC holds: a bare container row, or
  a row whose topic an earlier guide already claimed, contributes no level. Counting those
  leaves a gap — EMS' *Appendix B* page came out `#` then `####` — which is the same defect
  `design.md` §14 removed from the converter one stage earlier.
- Capping at H6 makes two depths render the same. That is a flattening and never a *skipped*
  level, so `design.md` invariant 14 continues to hold.
- Measured need: 10 of ActiveSpaces' 324 topics and 4 of EMS' 1,441 can reach the cap, and
  only on a page spanning the full tree depth.

### R3 — TOC regeneration

The merged `toc.yml` **retains every node and the full original hierarchy.** Nothing disappears
from navigation.

- A node whose topic is its page's *first* topic → `path: page.md`
- A node whose topic was *absorbed* → `path: page.md#anchor`
- A node with `#` in its path must generate no HTML page

This is what makes the merge invisible to users: navigation is unchanged while the number of
generated pages drops sharply.

### R4 — Links and assets

- Leave external links untouched (`http:`, `https:`, `mailto:`, `//`) and pure-fragment links (`#…`)
- `.md` targets resolve to their new `(page, anchor)`:
  - same page → `#anchor`
  - different page → `relative/path.md#anchor`
- Images and non-`.md` targets: recompute the relative path from the new page's directory
- Unresolvable targets: leave unchanged and **count them** for the validation report

> *As built (Phase 34, R9-01 and R9-02, 2026-10-04):* the `#anchor` a link gets is the one
> the heading it **names** lands on, not always the topic's section anchor. Since Phase 30 a
> converted link points at an exact heading, and since Phase 29 the anchor is the platform's
> slug of the heading text, numbered across the whole merged page — so a topic's second
> `## Import` becomes `import-1` once an earlier topic on the page has one. A link into
> another topic whose fragment names one of that topic's headings keeps that heading
> (503 links had been sent to the top of the topic instead). A pure `#…` link is no longer
> left untouched when the heading it names was renumbered: it follows the heading (9 links
> in 4 versions had landed on another topic's heading). A fragment that names no heading in
> the topic — a Stage 6a marker, or one already dangling in the source — is handled as
> before: the section anchor for a cross-topic link, untouched for a pure fragment.
> `reframe.yml` counts the re-pointed pure fragments as `links.renumbered`.

**R4.1 — Page placement.** A page is written into the directory of its **first topic's** source
path, and all relative paths are recomputed from there. This is what keeps directory-spanning
cases correct without special-casing.

> *As built (Phase 29):* a page is named from its first topic's **title**, not its filename,
> and written into a folder chain that mirrors the TOC (`installation.md` beside
> `installation/`), because the platform builds the URL from that chain. Relative paths are
> recomputed from wherever the page lands. A name is unique within its folder; a `-2` suffix
> appears only for two pages with one title under one parent. A name recorded in
> `rename-map.csv` wins over the computed name and folder.
>
> *As built (Phase 34, R9-03, R9-04, R9-05, 2026-10-04):* a topic `toc.yml` never lists is
> carried through as its own page (`guide: Not in navigation`), named in the folder it is
> written to, and filed among the children of the shallowest navigated page from its own
> source directory — in practice its guide's landing page. TRA Runtime Agent 5.13.0's second
> guide's legal and support pages had been named against the root TOC scope (gaining `-2`)
> and written into the raw source folder `trahelp/_templates/`. A carried page whose source
> directory no navigated page shares stays in that directory. An edit to `new_path` in
> `rename-map.csv`, or `--renormalize`, re-merges the version on the next run without
> `--force`. A name that another page ends up holding is refused, judged against the final
> set of paths rather than in page order, and each refusal is reported as
> `RENAME_MAP_REFUSED`.

**R4.2** A page must never contain topics from more than one source directory.

### R5 — Redirects

Emit one 301 per source topic: `old_path → new_page.md#anchor`. Zero dangling entries.

### R6 — Review queue *(new — not in the POC)*

Reframe must emit a queue of pages requiring human editorial judgment. **This is the primary
interface between the mechanical stage and the writer (or an editorial review skill), and it is
on the critical path — Reframe deliberately does not resolve these cases itself.**

Emit `review-queue.csv` (*as built:* at the merged tree's root, beside `toc.yml`; there is no
`manifest/` folder) with **only flagged pages** (a queue containing every page is
not a queue). Columns:

```
page_path, guide, n_topics, words, flags, detail
```

`flags` is a semicolon-separated list drawn from:

| flag | condition | what the writer decides |
|---|---|---|
| `reference-list` | `n_topics >= 20` and median words/topic `<= 100` | table conversion vs. stay granular vs. split |
| `oversized` | page words > MAX_WORDS | whether the source topic needs a manual split |
| `title-inherited` | `n_topics > 1` and page title equals its first topic's title | a real page title |
| `heterogeneous` | topics span more than one distinct depth-2 TOC ancestor | whether the page should split |
| `single-topic` | `n_topics == 1` | usually fine; flags structural outliers |
| `shortened` | the page filename does not carry its whole normalized title (added Phase 34, R1-03); not raised for a name taken from `rename-map.csv`, which is the writer's answer (R9-12) | a better filename, written into `rename-map.csv` |

On the reference corpus this yields roughly 25–30 rows out of 106 pages — a workable review load.

### R7 — Page frontmatter

Each merged page carries at minimum `title`, `guide`, and `merged_from` (the topic count).

**R7.1** Deriving `title` from the first topic's title is a known weakness — a twelve-topic page
titled after its first section is usually wrong. Reframe should emit the best title it can and
flag the page `title-inherited` so a human can correct it.

---

## 5. Interfaces

**Input** — a completed Stage 6 output tree:
```
<src>/toc.yml          hierarchy: docs / title / url / subfolderlist (items / path / children before Phase 36)
<src>/metadata.yml     version-level metadata
<src>/**/*.md          topic files, frontmatter + body
<src>/**/images, Resources, …   assets
```

**Output**
```
<out>/**/*.md                    merged pages
<out>/toc.yml                    full hierarchy, absorbed topics → page#anchor
<out>/metadata.yml               copied through
<out>/** assets                  copied, paths recomputed
manifest/pages.csv               page_path, title, guide, n_topics, words
manifest/topic-mapping.csv       page_path, guide, order, topic_title, source_path, anchor, words
manifest/redirects.csv           old_path, new_target, type
manifest/review-queue.csv        page_path, guide, n_topics, words, flags, detail
```

> *As built (Phase 20–35):* every sidecar is written at the merged tree's root, and there is
> no `manifest/` folder. `reframe.yml` carries what `pages.csv` and `topic-mapping.csv` would
> (pages, their sections, anchors and words, the policy and the link counts);
> `redirects.yml` replaces `redirects.csv`; `review-queue.csv` and `rename-map.csv` (page
> names, Phase 29) sit beside them, and `csh.yml` and `301.yml` appear when the version has a
> help map or a known live URL shape.

**Config** — per doc set, not hardcoded: `MAX_WORDS`, asset directories, TOC schema adapter.

> The TOC schema is **not** universal across doc sets. The reference corpus uses
> `items` / `path` / `children`. At least one other known set uses `docs` / `url` /
> `subfolderlist` with `_section_*.md` stub container pages. Treat schema handling as a
> pluggable adapter from the start rather than retrofitting it later.
>
> *As built (Phase 36, 2026-10-02):* Stage 6 now writes `docs` / `url` / `subfolderlist`
> itself, by the user's call to match html-to-md's field names — without the stub
> container pages. Both dialects have a registered reader; Reframe writes the new one.

---

## 6. Acceptance criteria

Reframe must self-validate and fail the stage if any check fails.

| check | pass condition |
|---|---|
| word conservation | output words == input words + one anchor token per topic; no content lost (*as built, Phase 29:* + the tokens each topic's scaffolding declares, which is 0 for a topic with an H1 and the synthesized heading's tokens otherwise, since no anchor marker is written) |
| anchors | count equals topic count; unique within every page |
| directory integrity | zero pages spanning more than one source directory |
| TOC completeness | every source node present; every referenced page exists; every referenced anchor exists |
| reachability | every emitted page reachable from the TOC |
| links | zero **newly** broken links (pre-existing breakage reported, not fatal) |
| redirects | one per source topic; zero dangling |
| determinism | two runs on identical input are byte-identical |

**Reference corpus results** (TIBCO EMS 10.5.1, POC, `MAX_WORDS=3000`):

| metric | value |
|---|---|
| topics → pages | 1,441 → 106 (93% fewer) |
| words/page | median 2,354 · min 20 · max 3,533 |
| topics/page | median 12 · min 1 · max 60 |
| guides | 9 |
| pages with >20 sections | 16 |
| words in → out | 226,517 → 227,958 (+1,441 = one anchor token per topic; since Phase 29 a topic with an H1 adds 0) |
| links | 2,345 checked, 2,314 rewritten, 0 newly broken |

Use these as a regression baseline: a reimplementation should reproduce them closely, though
R1.2 (dropping the minimum-size join) will legitimately shift page count upward somewhat.

---

## 7. Hard-won edge cases — do not regress these

Each of these was a real failure during the POC.

- **Guide boundaries.** An early version merged across top-level TOC items and swallowed an
  entire 21-topic Installation guide into a templates page; three directories vanished from the
  output. Costs roughly 5 extra pages to prevent. Non-negotiable.
- **Dedup must loop.** `tibemslookupcontext2.md` naturally slugs to `tibemslookupcontext-2`,
  colliding with the suffix assigned to a genuine duplicate. Applies to both anchor IDs and
  output filenames.
- **Page placement drives path correctness.** Writing pages into their first topic's source
  directory and recomputing every relative path from there is what made the directory-spanning
  cases come out clean without special-casing.
- **Heading overflow.** Shift must cap at H6. The reference corpus uses H1–H4 only, so nothing
  overflows there, but other sets will.
- **Fenced code blocks.** The POC's heading and link regexes match inside ``` fences. The
  reference corpus has zero heading-like lines inside fences so it never fired, but a corpus
  with `# comment` lines in shell samples **will be corrupted** — and if such a line precedes
  the topic's real H1, it becomes the anchored heading. Make the parser fence-aware.
- **Validation tooling.** `wc -w` with `find -exec +` emits a `total` per batch, so piping to
  `tail -1` silently reports only the last batch. Use a real parser for corpus-wide counts.

---

## 8. Pre-existing defects — not Reframe's to fix, not Reframe's fault

Present in the Stage 6 output before Reframe runs. Validation must not fail on them, and they
should not be attributed to the merge:

- **Dangling in-page anchors** (e.g. `#ID-000071DF`, `#Using`). The source contains no
  `<a name=>` and no `{#id}` anchors anywhere — these targets were lost in the original
  HTML→Markdown conversion. 31 instances in the reference corpus.
- **Mojibake in titles** — e.g. `XA<?>External Transaction Manager`, a replacement character
  where an em-dash belongs. A conversion artifact in the source TOC. Worth a separate sweep;
  it degrades both display and any lexical index built over titles.

---

## 9. Open decisions

| # | Decision | Status |
|---|---|---|
| D1 | Reference-list end state (table vs. granular vs. split) | **Deferred to writers, per page.** Reframe flags; it must not decide. |
| D2 | `MAX_WORDS` per doc set | 3000 validated on the reference corpus; expected to vary |
| D3 | Multi-version layout pinning | Required only if eligibility returns >1 version of one doc set (R1.4) |
| D4 | Whether the editorial review pass is a skill, a UI, or a manual checklist | Out of scope here; R6's queue is the contract either way |

---

## 10. Reference implementation

A working proof-of-concept exists at `docrestruct/build_merged.py` in the
`test-docs-md-optimization` repo, validated against TIBCO EMS 10.5.1. It implements R1–R5 and
all of §6 except determinism-checking, and implements none of R6.

Known defects in the POC, carried here so they are not ported forward:
- `MIN_WORDS` declared but never referenced — remove rather than wire up (R1.2)
- `assign()` builds and returns a `dest` dict that is never used; it is keyed by basename while
  the collision set is keyed by full path, so it would silently collide across directories
- `words()` swallows `OSError` and returns 0, but the write pass opens the same path unguarded —
  a TOC entry pointing at a missing file sizes as 0, then hard-crashes later
- Heading and link regexes are not fence-aware (§7)
