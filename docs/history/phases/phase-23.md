> Archived from `docs/planning.md` on 2026-10-02. Status: **Built & verified, 2026-09-28**. Kept verbatim; a heading that says *Planned* was built later in this same section.
> Index of every phase: [`docs/planning.md`](../../planning.md#finished-phases).

### Phase 23: The Classes Went and Everything Else Stayed — **Planned, 2026-09-28**

Phase 21 scrubbed `class` and said so explicitly: layout attributes "change rendering", bundling the two would make any regression ambiguous about which caused it, and so `border`, `cellpadding`, `cellspacing`, `width` and `valign` were left alone. That was the right call for Phase 21 and it was an argument about **sequencing**, not a permanent boundary. A writer reading the output found the rest still there — *"I can still see cellspacing, style, and title attribute"* — and the measurement behind that observation turns out to be worse than "some layout survived".

**Measured on the published EMS tree, 887 files carrying a table:**

| what survives a Phase 21 passthrough | count | what it is |
|---|---:|---|
| `style="mc-table-style: url('../Resources/TableStyles/*.css')"` | **812** | a reference to a folder that **does not exist anywhere under `output/`** |
| `<col title="C1">` | **1,696** (806 files) | not a label, a **tooltip**: hover a column border and the reader is shown "C1" |
| `data-mc-conditions`, `data-mc-autonum`, stray `xmlns`, `madcap:` href | **201** | authoring-tool plumbing with no meaning outside Flare |
| `cellspacing`, `col style="width: 169px"`, `td style="padding"`, `valign`, `align` | **1,386** | genuine layout |

The first three rows are not a rendering decision at all — they are the same category as `TableStyle-*`, and Phase 21 simply did not look past `class`. The `mc-table-style` URL is the sharpest case: it is a dead link that **the link checker cannot see**, because the checker reads `href` and `src` and this is inside a `style`. 812 dangling references passing validation.

The fourth row is a real rendering decision, and the writer made it: **the layout goes too**, and the site's own stylesheet sizes these tables. That is better on a narrow screen — a `width="100%"` table with pixel columns does not reflow — and occasionally worse where a pixel width was holding a command name on one line. It is a visible change and is not claimed to be anything else.

#### Decisions

| decision | what gets built | why not the obvious alternative |
|---|---|---|
| **A keep-list of attributes, mirroring the class keep-list** | `tables.STRUCTURAL_ATTRS`; `scrub` gains an `attrs` parameter beside `keep` | Same argument as `SEMANTIC_CLASSES` and it has already been proved by this phase: a strip-list written against Flare's vocabulary is exactly what let `data-mc-*` and `mc-table-style` through. What is kept is structure and content — what a cell spans, where a link points, what an anchor is called — never how any of it looks. |
| **`title` is kept on `a`, `abbr`, `area`, `img`, `iframe` and dropped everywhere else** | `tables.TITLE_BEARERS` | A single rule about the attribute cannot work: on an `<a>` a human wrote it and it is content; on a `<col>` the generator wrote it and it renders as "C1" under the reader's cursor. 1,696 of the latter against a handful of the former. |
| **An emptied `<col>` is removed, and a `<colgroup>` emptied by that goes with it** | two ordered passes at the end of `scrub` | Once the widths are gone a `<col/>` carries nothing. Keeping 1,696 empty ones is keeping the skeleton of the decision rather than the decision. `span` still counts as content, so `<col span="2">` survives. |
| **No new finding code** | nothing is reported | Same as Phase 21: nothing here can fail. The 812 dead stylesheet URLs are *removed*, not reported — reporting a reference that nothing should have emitted is a queue nobody can action. |
| **`webworks.py` is not touched** | it passes `keep` positionally and picks up the default `attrs` | Its override is about class vocabulary (`SPAN_TO_TAG`), which is orthogonal. An engine that needs a different attribute set can pass one. |

#### What this costs downstream

`convert` output changes for every version with a passthrough table, so EMS re-converts, re-reframes and re-syncs — and `reframe` must be `--force`d, for the reason recorded as an Open under Phase 21. **Expect the page count and review queue to move again**: removing attribute text changes the packer's word counts exactly as Phase 21's class removal did.

*Exit: `mc-table-style`, `<col title>`, `cellspacing`, `data-mc-*` and `xmlns` all at **0** in the published tree; semantic classes and every structural attribute (`rowspan`, `colspan`, `scope`, `href`, `id`, `span`) unchanged in count; `validate` reports no new findings; tests pin the generated-vs-authored `title` split and the emptied-`<col>` removal.*

#### Phase 23 — **Built & verified, 2026-09-28**

One file. `tables.STRUCTURAL_ATTRS` and `tables.TITLE_BEARERS` are new; `scrub` gained an `attrs` parameter and two ordered passes at the end (a `<colgroup>` is only empty once its `<col>` children have gone, and `find_all` hands back the parent first); `passthrough` passes it through. `webworks.py` was not touched — it passes `keep` positionally and picks up the default.

**Measured on the rebuilt EMS tree, 8,639 published files:**

| | before | after |
|---|---:|---:|
| `mc-table-style` | 812 files | **0** |
| `<col …title=…>` | 1,696 in 806 files | **0** |
| `cellspacing` | 830 files | **0** |
| `data-mc-*` | 77 | **0** |
| `xmlns` | 120 | **0** |
| `valign`, `cellpadding`, `bgcolor` | present | **0** |
| `class="varname"` | 617 | **617** |
| `class="MCXref xref"` | 184 | **184** |
| `rowspan` / `scope` | 18 / 24 | **18 / 24** |
| `<table>` elements | 1,050 | **1,050** |

The two semantic counts are the Phase 21 baseline unchanged, which is the row that says this removed presentation and nothing else. No table was lost.

**Pipeline, all six versions re-converted (`--force`), re-merged (`--force`, per Phase 21's Open), re-synced and validated:**

| | |
|---|---|
| Pages | **747**, the same total as after Phase 21, redistributed: 10.5.1 and 10.5.0 125 → **124**, 10.4.4 and 10.4.3 → **123**, 10.4.1 **125**, 10.4.0 **128**. The packer sizes by word count and attribute text is words, exactly as Phase 21 found. |
| Review queue | **115**, unchanged in total |
| Redirects | **17,252 in 2 published maps** — 8,639 + 8,613, unchanged, so no topic gained or lost a redirect |
| `validate` | **0 errors**; 7 `ANCHOR_MISSING` + 32 `REDIRECT_SHADOWED`, identical to the Phase 22 baseline |
| Suite | **1,544 passed, 2 skipped**, `ruff` clean |

**One thing the measurement turned up that is not this phase's doing.** `colspan` is **0** in the output while the 10.5.1 source carries 56 genuine `colspan="2"`/`"3"`. It is in the keep-list and a test pins it; the reason it never arrives is upstream — a full-width row like `<td colspan="2"><b>Headings specific to file-based stores</b></td>` is lifted out as a bold paragraph and the table split in two, which is the right rendering and predates Phase 21. Recorded because "0 colspan in the output" reads like a bug in this change and is not one.

---
