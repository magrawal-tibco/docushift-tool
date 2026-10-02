> Archived from `docs/planning.md` on 2026-10-02. Status: **Complete, 2026-09-19**. Kept verbatim; a heading that says *Planned* was built later in this same section.
> Index of every phase: [`docs/planning.md`](../../planning.md#finished-phases).

### Phase 16: The Converter Deletes the Targets Its Own Links Point At

`validate --target-dir` over the published `ems` tree walks 8,658 files and 17,214 references and reports **1 `LINK_BROKEN`** and **1,763 `ANCHOR_MISSING`**. Phase 15 left both on the table deliberately: they are Stage 5's, and folding a converter fix into a sync phase would have made neither measurable. This is that phase.

Phase 7b already predicted the shape of it — *"spot-checks say these are anchors the conversion genuinely dropped rather than slug-algorithm disagreement, which makes `ANCHOR_MISSING` the first measurement of a defect nobody had counted."* The spot-check is now a count.

#### 16a. Measured, 2026-09-19: 1,679 of 1,763 targets exist upstream and are deleted in conversion

Each finding's target file was resolved back through `output_map` to the HTML it was converted from, and the fragment looked up in that source:

| | |
|---|---|
| `ANCHOR_MISSING`, run 52 | **1,763** |
| target present in the source as `<a name=>` | **1,679** (95.2%) |
| target present as `id=` only | **0** |
| target genuinely absent upstream | 84 (4.8%) |

Where the surviving 1,679 sit in the source DOM — which is the same question as *which converter branch drops them*:

| location | findings |
|---|---|
| inside a `<table>` | **1,092** |
| inside an `<h1>`–`<h6>` | **424** |
| in ordinary prose | 163 |

Two lines of `transforms/markdown.py` account for all three. In `rewrite()`, the raw-HTML table path:

```python
for anchor in tag.find_all("a"):
    url = self.link(anchor)
    if url:
        anchor["href"] = url
    else:
        anchor.unwrap()          # <a name="ID-2FC4B4A1"></a> ceases to exist
```

and in `_anchor()`, the inline path every heading and paragraph goes through:

```python
url = self.link(tag)
if not url:
    return text                  # "" for an empty anchor: the target is gone
```

Neither is a mistake about links. Both are correct about links and silent about *targets*: an `<a>` with no `href` is not a broken link, it is a destination, and every `<a href="#ID-2FC4B4A1">` elsewhere in the corpus survives the conversion pointing at nothing. The validator has been reporting the consequence since Phase 7b without anyone reading it as a cause.

**This is not an `ems` quirk.** A 1,500-file sample per tree:

| tree | HTML files sampled | `<a name=>` targets | files carrying one |
|---|---|---|---|
| `ems` (downloaded, Flare) | 1,500 | 209 | 60 |
| `datasynapse` (cache, mixed) | 1,500 | **2,437** | **1,333** |
| predecessor `cache/pub` | 1,500 | **2,564** | **1,401** |

The pattern is *denser* outside `ems`. Every product converted so far has been losing these.

#### 16b. The fix emits the target, as HTML5 spells it

`validation/references.py:_HTML_ANCHOR` accepts `id=` **and** `name=`, so either spelling would satisfy the check. The output should be `id=`: HTML5 dropped `name` on `<a>`, AEM's renderer will not resolve it, and the findings register describes `ANCHOR_MISSING` as *"a `#fragment` naming no heading and no `id=` in the file it resolves to"*. Satisfying the validator with the attribute the validator tolerates rather than the one it documents would be a fix aimed at the test.

So a href-less `<a name="X">` — or `<a id="X">` — becomes `<a id="X"></a>`, kept next to the text it labelled, in both branches:

- **`rewrite()`**: keep the tag rather than unwrapping it; rename `name` to `id`; unwrap only when there is neither.
- **`_anchor()`**: return the marker ahead of whatever the tag would otherwise have produced — the bare marker when the tag is empty, `marker + text` when it has text and no href, `marker + [text](url)` in the rare case it carries both a target and a link.

**Headings need a third move.** 424 of the targets sit inside an `<h2>`, and `_block`'s heading branch builds the line from `inline_children`. Letting the marker through there would emit `## <a id="X"></a>Configuring Users`, and the validator computes heading slugs with `slugify_heading` over the raw title — so every *existing* `#configuring-users` fragment in the corpus would break in the act of fixing 424 others. The heading branch therefore lifts leading markers out into their own block:

```markdown
<a id="ID-2FC4B4A1"></a>

## Configuring Users
```

Both anchors then resolve, and the slug is untouched.

**Bounded output growth.** Counted over exactly the 8,613 HTML files Stage 5 converts, not the whole tree: **1,218 href-less anchors in 350 files**, all of them `name=`. Fewer than one marker per seven output files, and none in the 8,263 files that carry no target today.

`_code_fragment` is left alone: an anchor inside a code span cannot be a link destination in any renderer, and the branch already drops the `<a>` there for the same reason.

#### 16c. The broken link is the validator's, not the converter's

`error-and-status-mes.md:791` is a row of a Flare table too irregular for GFM, so Stage 5 emits it as passthrough HTML, verbatim:

```html
<p>Pulsar: [%s](%s:%d): %s</p>
```

The converter did not manufacture a link — that text is in the source HTML character for character, a printf format string in an error-message table. **CommonMark does not parse inline Markdown inside an HTML block**, so `[%s](%s:%d)` is text and `users-guide/%s:%d` is not a reference. `references()` reports it because `_MD_INLINE` runs over the whole file with only code masked. This is a false positive, and Phase 15's note calling it a converter defect was wrong.

The fix is a `mask_html_blocks` beside the existing `mask_code`, applied to the three *Markdown* extractors and **not** to `_HTML_REF` or `_HTML_ANCHOR` — links and targets written as HTML inside those blocks are real and must keep being checked. Block detection follows CommonMark: the type-6 tag list (which deliberately excludes `a`, `b`, `span`, `img`, so an inline tag at the start of a line suspends nothing) plus type 7, a complete tag alone on its line; ends at a blank line.

**Blast radius, measured over the published tree**: of 15,112 Markdown-syntax references in 8,657 files, masking removes **exactly 1** — the `%s:%d`. Nothing else in the corpus relies on Markdown being parsed where CommonMark says it is not.

#### 16d. Four more places a target is discarded, found by running it

16b's two branches took 1,763 down to **184**, not to 84. The remaining 100 were all the same mistake in four more rewrites, and each one was found the same way — re-resolve what is left, look at where it sits, fix, run again. **A destination is not a link, and every rewrite that carries text across has to be told so separately.**

| the rewrite | what it did | recovered |
|---|---|---|
| `markdown.code_span` | rendered the span from its *text*; Flare writes `<code><a name="tibemsd_Service_Parameters"></a>tibemsd </code>` | 34 |
| `flare._heading_paragraph` | rebuilt a split table's short label from `_text(cell)`, which has no children | *(in the 34 above)* |
| `markdown.table` | `tables.read` sees rows and cells; Flare's table-level target sits between `<col>` and `<thead>`, in neither | 42 |
| `flare._split_colspan_tables` / `_fake_list_tables` | moved the rows into a new element and decomposed the old table, destroying anything that was not a row | 18 |
| `transforms/links.classify` | **the validator's side**: a same-page `#foo` was the one branch that did not percent-decode the fragment | 6 |

The first four take the same remedy as the heading: hoist the target out in front of the construct, because it cannot be a destination inside one. The fifth is different and worth naming — `classify` decodes the fragment on the `RELATIVE` path and left it raw on the `FRAGMENT` path, so `%0A%20%20%20` was compared against a literal newline and three spaces. One corpus anchor has a whole pasted table in its `name`, which is the only reason anything exercised it. The asymmetry was also double-encoding those fragments on the way out, via `links.emit`.

#### Acceptance — measured, 2026-09-19

`convert --family ems --force`, `sync --family ems`, `validate --target-dir`:

| | |
|---|---|
| `LINK_BROKEN` | **0** (was 1) |
| `ANCHOR_MISSING` | **84** (was 1,763) |
| fragments resolving | **1,703 of 1,787** (was 1,603) |
| exit code | **0** |
| the 84 survivors | re-resolved through `output_map`: **84 of 84 absent from the source**, 0 present-and-dropped |
| output tree | **8,847 files**, unchanged — this phase adds anchors inside files, not files |
| suite | **1,327 pass** (+12), lint clean |

New unit tests, one per site: a target in a passthrough table survives as `id=`; one in prose emits the marker; one in a heading is hoisted above it and the slug is unaffected; one in a code span is hoisted in front of it; a table's own target survives both the pipe-table conversion and the two Flare table rewrites; a split label keeps the target its rebuild dropped; an `<a>` with neither `href` nor a target is still unwrapped; a same-page fragment is decoded; `references()` finds no Markdown link inside an HTML block and still finds the `<a href=>` in one.

---
