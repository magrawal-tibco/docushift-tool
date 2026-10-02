> Archived from `docs/planning.md` on 2026-10-02. Status: **Complete, 2026-09-30**. Kept verbatim; a heading that says *Planned* was built later in this same section.
> Index of every phase: [`docs/planning.md`](../../planning.md#finished-phases).

### Phase 28: A Merged Page Was a Run of Siblings, Not a Subtree — **Complete, 2026-09-30**

Reported as "the reframed topics start at `h2` instead of `h1`". That part is not a
regression — R2 has always said "every former topic becomes `## {Heading}`" — but it is the
visible end of something real. `packer._close_run` filled a page by walking topics in reading
order and joining until the cap, a directory change or a `keep_separate` unit stopped it. It
never asked whose children they were.

**Measured against the source TOCs before any change:**

| | pages | pages holding topics from more than one TOC parent |
|---|---:|---:|
| ActiveSpaces 5.2.0 | 46 | **27** |
| EMS 10.5.1 | 124 | **67** |

A majority of merged pages were arbitrary sibling runs. That is *why* no page could carry a
meaningful H1: there was no single topic the page was about. The heading level was a symptom;
the boundary rule was the defect.

#### Decisions

| decision | what got built | why not the obvious alternative |
|---|---|---|
| **A page is a subtree** | A node's whole subtree becomes one page when it fits and shares one source directory; otherwise the node stands alone and its children group into pages of whole *consecutive sibling subtrees* of that one parent | Refusing to group siblings at all — the first shape considered — was measured: **119 and 628 pages**, medians 416 and 159 words, 363 EMS pages under 200. The grouping is what keeps the page count sane, and grouping *whole subtrees under one parent* keeps the H1 guarantee the strict rule was wanted for. |
| **The H1 is always a real topic's** | The page's first topic supplies it, which is already the topic R4.1 names the page after. A subtree alone on a page keeps its own heading and title | Synthesising an H1 from the shared parent's title was the other candidate and would have titled ~half of all pages with a repeated parent name — four pages reading "Installation" in one section. It also needed new word-conservation accounting for a heading no topic owns. |
| **Depth is counted in what is emitted** | A bare container row, or a row an earlier guide already claimed, contributes no level | Counting raw TOC depth leaves a hole. It did: EMS' *Appendix B* page came out `#` then `####`, which is Phase 27's defect reintroduced one stage later. `_relevel` reuses Phase 27's own `compact` rather than growing a second copy of the rule. |
| **The packer's algorithm is in the currency digest** | A module constant `_ALGORITHM`, folded into `ReframePolicy.key` | The digest is built from config fields, and this change touches none of them — every merged tree on disk would have reported CURRENT and kept its old layout for good, re-cut only by a `--force` somebody happened to remember. Not a `reframe.yaml` field: a config that could select an algorithm would be two packers to keep alive. |

#### Built, and what it measured

`Topic.level`, `shift_headings(..., level=2)`, a top-down `_subtree` with a `_collect`/`_commit`
probe pair, `_close_run` narrowed to whole sibling subtrees, `_relevel` for the projected path,
and `_ALGORITHM`. **1,623 tests pass** (+11), lint clean.

| | pages before | after | median words | pages holding two parents |
|---|---:|---:|---:|---:|
| ActiveSpaces 5.2.0 | 46 | **56** | 1,772 → 1,120 | 27 → **0** |
| EMS 10.5.1 | 124 | **160** | 1,989 → 1,364 | 67 → **0** |

Both page counts landed exactly on the simulation that justified the plan. Across all twelve
re-merged versions, **1,323 of 1,323 merged pages now open at H1** and **none skips a heading
level**. The review queue is unchanged — 87 and 118 — so the `heterogeneous` flag did not fire
on the new sibling-group pages and the gate the plan held in reserve was not needed.

**Three faults the plan did not predict, each found by measuring the real output rather than
by reading the diff.** All three were the same mistake in different places: a level assigned
from something other than the page's own emitted tree.

1. **Carried pages** kept the `Topic` default and published 35 ActiveSpaces and 8 EMS pages
   opening at `##` with nothing above them. A carried page is one topic alone, so that topic
   *is* the page.
2. **`project`'s new-topic path** did the same for every topic a pinned version has and its
   reference does not — which is why the first re-cut looked clean on 5.2.0 and 10.5.1 and
   wrong on all ten projected versions.
3. **`_collect` counted skipped rows.** The hole this left is the `#` → `####` above.

**Not a regression, and checked rather than assumed:** the largest merged page is EMS 10.4.0's
`error-and-status-mes.md` at 13,985 words. It is a *single source topic*; R1.3 forbids
splitting a topic body, so an oversized topic is an oversized page. Its 10.5.1 equivalent is
3,395 words and also one topic.

**Published, and validated.** Both families re-synced; `validate` over the whole target reports
**0 errors** across 207 folders, 13,633 files and 148,464 references. `REDIRECT_SHADOWED` rose
31 → 340, and all 340 were checked individually: **every one differs from its target only in
capital letters**, none is a redirect onto a genuinely different live page. That is the class
already accepted in `open-issues.md`, grown because more topics now become a page named after
themselves — the lower-casing is what makes the pair. `sync` hit intermittent Windows file
locks in the API-reference copy on several passes and needed re-running; unrelated to this
work, but worth knowing it recurs.

**Still open: the cap.** The "Installation" subtree the request used as its example is 3,188
words against a 3,000 cap, so it comes out as a parent page plus two grouped child pages
rather than the single page described. At 4,000 it is one page. Left at 3,000 deliberately —
the decision was to look at a real re-cut first, and it is a config field, so changing it
costs a re-merge and no code.

---
