> Archived from `docs/planning.md` on 2026-10-02. Status: **Built, 2026-09-29**. Kept verbatim; a heading that says *Planned* was built later in this same section.
> Index of every phase: [`docs/planning.md`](../../planning.md#finished-phases).

### Phase 27: Two Things the Source Says That the Markdown Does Not — **Planned, 2026-09-29**

Two defects reported against the merged ActiveSpaces output, both traced past reframe into the conversion walk. They are unrelated in mechanism and are planned together because they share one call site and one re-run.

#### 27a. A heading level the author skipped stays skipped

`reframed/en-us-tib-activespaces/tibco-activespaces-enterprise-edition/5.2.0/Concepts/vectors-in-tibco-activespaces.md` runs `## → ### → ###### → ###`. The source, `Concepts/Sample-Programs.htm`, is `h1, h2, h2, h6, h6, h2, h6, h6` — the author reached for `h6` because of how it was styled, not because the section is five levels deep. Reframe's `shift_headings` adds one level to everything and clamps at six, so it neither caused this nor can fix it; the walk in `transforms/markdown.py` maps `h1…h6` straight through.

**Measured over the emitted Markdown, 2026-09-29** (`scratch/scan_md_headings.py` — the `.md`, not the HTML, because a raw-HTML census counts things the engines never emit as headings):

| tree | files skipping a level | of | jumps seen |
|---|---:|---:|---|
| `output/` | **612** | 24,781 | h1→h4 308, h2→h4 238, h1→h3 160, h2→h6 2 |
| `reframed/` | **19** | 1,434 | h2→h5 6, h2→h4 6, h3→h5 6, h3→h6 2 |

**The HTML census said 5,022 files and was wrong.** Scanning `families/` for raw `<hN>` charged 4,990 of Streaming's 31,192 files with an `h1→h3`/`h1→h4` skip. Nearly all of them are DocBook admonition titles — `<h3>Note</h3>`, `<h3>Caution</h3>`, `<h3>Disclaimer</h3>` — which Phase 19 already turns into a callout, so they never reach the Markdown as headings. This is the whole reason the exit criterion below is stated against `output/` and not against the source.

Per family, over the emitted Markdown:

| family | files skipping | of | engine |
|---|---:|---:|---|
| Runtime Agent / Administrator / Designer add-in | **477** | 2,641 | WebWorks |
| TIBCO Streaming / Spotfire Data Streams | **112** | 9,421 | DocBook |
| Enterprise Message Service | **12** | 8,639 | Flare |
| ActiveSpaces | **9** | 2,054 | Flare |
| GridServer Manager | **2** | 2,026 | Flare |

**Correction, recorded rather than quietly fixed.** An earlier draft of this section read "Streaming contributes zero offenders", which was taken off the scan's printed sample of fifteen rather than off a per-family count. Streaming contributes 112 — the largest group after WebWorks. It cannot serve as the untouched control the exit criterion first named, and the exit criterion below is rewritten accordingly.

#### 27b. A definition term that is not a `<dt>`

`reframed/…/Concepts/concepts.md` renders *Scalability*, *System of Record*, *Tables*, *Rows*, *Columns*, *Nodes*, *Copysets* as bare paragraphs sitting above their definitions. The walk handles `<dt>` correctly and has since 5b — it emits `**term**`. The corpus's Flare-from-DITA output does not use the tag:

```html
<div class="dl">
  <div class="dlentry"><span class="dt">Scalability</span>
    <div class="dd">The biggest advantage of using ActiveSpaces is scalability. …</div>
  </div>
</div>
```

`div` is in `_TRANSPARENT`, `span` is not a block, so the term falls into the loose-inline run and comes out as prose. **Measured, same scan:**

| flavour | files | families |
|---|---:|---|
| `<span class="dt">` | 146 | ActiveSpaces 119, EMS 24, DataSynapse 3 |
| `<div class="dt">` | 11 | ActiveSpaces 6, EMS 3, DataSynapse 2 |
| real `<dt>` | 18,848 | Streaming 15,741, EMS 2,171, ActiveSpaces 936 |

`div.dd` outnumbers the terms (97 to 84 in ActiveSpaces 5.2.0 alone): a `dlentry` may carry several definitions for one term, and one of them may open with an authored `<b>` of its own. That is content, not a term, and must be left alone.

**Two near-misses that are already correct and must stay untouched.** Streaming's 2,892 `<span class="term">` files are DocBook's `<dt><span class="term">…</span></dt>` — the tag is real and the term is already bold. And 1,536 EMS files carry `<span class="varname">`, which is an inline code-ish role inside running prose, not a definition term. Neither is in scope.

#### Decisions

| decision | what gets built | why not the obvious alternative |
|---|---|---|
| **Heading levels are compacted by nesting depth, not by closing each gap** | Walk the page's headings in order against a stack of source levels; emit the stack's depth. `h1,h2,h2,h6,h6,h2,h6,h6` → `h1,h2,h2,h3,h3,h2,h3,h3` | "Subtract the gap from everything after it" needs a running offset that a later shallower heading invalidates, and can push a heading below `h1`. The stack has no offset to get wrong and cannot invert two headings' relative depth. |
| **Only depth is normalized; order, text, ids and slugs are untouched** | The retag happens on the DOM before the walk, so `anchor_target`, `_anchors` and `slugify_heading` see the same strings they see today | Rewriting the emitted Markdown with a regex is what Phase 20's proof-of-concept did to its cost (`reframe/pages.py` §1): a `# comment` in a shell fence is a heading to a regex. |
| **A class-named term is retagged, never re-styled** | `span.dt`/`div.dt` → `<dt>`, `div.dd` → `<dd>`, `div.dlentry` unwrapped, `div.dl` → `<dl>`; the existing `_block` branches then do the work | Emitting `**term**` directly from the normalizer would give the corpus two definition-list renderers that drift apart — the exact failure `transforms/markdown.py`'s docstring was written to prevent. |
| **Both run in the shared transform layer, called by all four engines** | `transforms/headings.py` and `transforms/deflists.py`, invoked immediately before `renderer.render(container)` in `flare.py`, `dita.py`, `docbook.py`, `webworks.py` | Putting either in `flare.py` leaves TRA's 400-odd WebWorks offenders unfixed and invites a second copy later. DocBook already promotes a leading `h2` to `h1` at that call site (`docbook.py:564`) — this is where page-level DOM repair lives. |
| **Counted, not narrated** | Each normalizer returns how many elements it retagged; the engines add it to the run report beside `flattened_links` | A structural rewrite with no number attached is unfalsifiable on the next corpus. |

**Known limit, accepted.** Where a page goes deep *before* it goes shallow across a gap — `h1, h4, h2` — the stack gives both `h4` and `h2` depth 2 and the two source levels merge. The source is genuinely ambiguous there and no rule recovers the author's intent; the alternative rules all produce something worse. It is recorded here rather than discovered later.

#### Scope

- `src/docushift/transforms/headings.py` — new; `normalize(container) -> int`.
- `src/docushift/transforms/deflists.py` — new; `normalize(container) -> int`.
- `src/docushift/engines/{flare,dita,docbook,webworks}.py` — one call each, before `render`.
- `src/docushift/reporting/` — two counters in the run report.
- `tests/unit/` — the four measured heading shapes above, the `dlentry` with two `dd`s and an authored `<b>`, DocBook's `<dt><span class="term">` unchanged, `span.varname` unchanged.
- Re-convert and re-merge ActiveSpaces, EMS, TRA and DataSynapse; Streaming re-converted as the untouched control.
- `docs/design.md` — the two rules; `docs/open-issues.md` — the ActiveSpaces entry closes when the re-merge lands.

#### Exit

`scratch/scan_md_headings.py` over `output/` reports **0 of 24,781** files skipping a level, and over `reframed/` **0 of 1,434**.

**The control is not "one family is byte-identical" but "only the faulty pages moved".** Streaming turned out to hold 112 of the offenders, so no family is untouched; the stronger statement is that the set of pages whose *heading lines* changed equals the set that was skipping, per family, exactly. The seven ActiveSpaces terms named in 27b are `**bold**`, the `<b>Persistence on Nodes</b>` beside them is unchanged, and the 18,848 real-`<dt>` files show no diff attributable to the deflist normalizer.

#### Built, and what it measured — **2026-09-29**

`transforms/headings.py` (`compact`, `normalize`, `is_empty`), `transforms/deflists.py` (`normalize`), one call apiece in all four engines, two counters on `ConversionContext`, and `driver._report_repairs`. Register **58 → 60**. **1,612 tests pass** (+21), lint clean.

Re-converted every convert-eligible version with `--force`, then re-merged every reframe set:

| tree | skipping before | after |
|---|---:|---:|
| `output/` | 612 of 24,781 | **2 of 24,781** |
| `reframed/` | 19 of 1,434 | **2 of 1,429** |

**Both survivors are the same two GridServer Manager pages, and neither can be repaired here.** `tibco-datasynapse-gridserver-manager` carries `in_scope: false` in `products.csv` with `scope_source: manual`, so `convert` selects none of its versions and the pages under `output/` are left over from 19 Sep 2026. Lifting the scope mark is a catalog decision, not a converter one; it is `docs/open-issues.md`'s to carry, and it is filed there.

**The heading rule moved exactly the pages that were broken, and no others.** Diffing every `.md` against a pre-change snapshot and classifying each changed line:

| family | files whose heading lines changed | files that were skipping |
|---|---:|---:|
| Runtime Agent / Administrator / Designer add-in | 477 | 477 |
| TIBCO Streaming / Spotfire Data Streams | 112 | 112 |
| Enterprise Message Service | 12 | 12 |
| ActiveSpaces | 9 | 9 |

The two sets are equal in all four, which is the property worth having and a stronger one than the byte-identical control the plan first asked for. (The snapshot also carries a larger, unrelated diff — 1,606 Streaming files and 224 TRA ones whose *table* markup changed. That is Phases 21 and 23 landing in a tree that had never been re-converted since, not this phase; none of those files has a changed heading line.)

**Definition terms, read back off the run report:** ActiveSpaces 84 / 86 / 86 / 85 / 82 / 82 across its six versions, EMS 11 in each of six. The reported page now opens `**Scalability**`, `**System of Record**`, `**Faster Access to Data**`; `**Persistence on Nodes**` — the authored `<b>` inside a second `dd` — is still exactly where it was.

**Three things the plan did not anticipate, each found by measuring rather than by reading.**

1. **WebWorks has no `<hN>`.** Its hierarchy is `div.N1Heading` / `div.MinorHead`, read out of the class name in `block_override`, so the shared normalizer found nothing to do on the largest offender group in the corpus. The rule is therefore exported as `compact` and the engine applies it to the levels its classes carry, writing the answer to an attribute — the class is also what identifies the div as a heading at all. Retagging those divs into real headings would have routed them through the generic branch, which hoists an `<a id>` out of the heading line and would have moved slugs that resolve today.
2. **A page can spell its headings both ways at once**, which the first cut got wrong by renumbering the two vocabularies separately — four pages still skipped. Depth is a property of the page, so both kinds are now collected in one document-ordered pass and share one stack.
3. **An empty heading emits nothing but was still taking a rung.** `admin_server.4.063` carries an empty `N3Syntax` between its title and its first section; with that rung spent, the page read `#` then `###` and no rule that only looks at levels could see why. `is_empty` excludes it — and counts a heading holding only an `<img>` as content, because GFM renders that.

And one the plan did anticipate but under-weighted: **the DocBook admonition predicate is load-bearing.** Without `_consumed_heading`, every `<h3>Note</h3>` in Streaming's 31,192 files would have taken a level and pushed the real sections around it — which is the raw-HTML census's 4,990 false positives, converted from a measurement error into an output defect.

---
