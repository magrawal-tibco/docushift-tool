> Archived from `docs/planning.md` on 2026-10-02. Status: **Built & verified, 2026-09-28**. Kept verbatim; a heading that says *Planned* was built later in this same section.
> Index of every phase: [`docs/planning.md`](../../planning.md#finished-phases).

### Phase 21: A Passthrough Table Carries the Authoring Tool's Styling Into the Output — **Planned, 2026-09-28**

`tables.passthrough` is one line — `return str(table)` — and that line is the whole of the problem. Half the corpus's tables take the passthrough branch for a good reason (§5.5: GFM has no `rowspan`, no multi-block cell, and flattening one produces a plausible table that is wrong), but `markdown.rewrite` resolves only `img src` and `a href`/`id` before the subtree is dumped. Everything else Flare stamped on the markup ships verbatim.

**Measured on the published EMS tree** (`output/en-us-tib-ems`, 8,639 `.md` files):

| | |
|---|---:|
| files carrying a `class=` | **899** (10.4%) |
| `class` attributes total | **26,829** |
| `TableStyle-*` | **25,849** (96.3%) |
| everything else | **980** |

The `TableStyle-*` vocabulary is Flare's generated table-style naming — `TableStyle-Table-BodyE-Column1-Body1` and 30-odd siblings — and it is presentational by construction: it names a row band and a column position in a stylesheet that does not travel with the content. The remaining 980 are not that. `varname` (617), `MCXref xref` (184), `filepath`, `option`, `cite`, and the four `note*` variants carry semantics the plain text has already lost, and some of them are the raw material for a later phase that turns them into real Markdown constructs. **They are kept.**

Note what this is *not*. The `<table>` element also carries `border`, `cellpadding`, `cellspacing`, `width` and per-cell `valign`. Those are out of scope: unlike a class naming an absent stylesheet, they affect how a browser lays the table out today, and removing them is a rendering change rather than a cleanup. The predecessor stripped them; that is a separate decision and not this one.

There is a second-order finding worth recording because it explains the predecessor's output and will otherwise be rediscovered. `html-to-md`'s `_clean_table_html` iterates `table.find_all(True)`, which in BeautifulSoup returns **descendants only, never the element itself**. Its passthrough tables therefore have clean cells and a fully-attributed `<table>` tag — 530 `ebx_definitionList` classes survive on EMS's neighbour tree, all 530 on the `<table>`, none on any descendant. DocuShift's bug is the wider one (it scrubs nothing), but the shape of the predecessor's is the reason to write the fix as a whole-subtree walk that includes the root, and to have a test that would fail on the off-by-one.

#### Decisions

| decision | what gets built | why not the obvious alternative |
|---|---|---|
| **Scrubbed in `tables.passthrough`, not in `markdown.rewrite`** | `passthrough` walks `[table, *table.find_all(True)]` and drops non-semantic classes before rendering | `rewrite` is `markdown.py`'s and WebWorks calls it separately (`webworks.py:304`); putting the scrub in the shared choke point means every engine that passes a table through gets it, including the next one. Mutation in place is already sanctioned here — the subtree is discarded as soon as the topic renders (`rewrite`'s docstring). |
| **A keep-list, not a strip-list** | Classes are removed unless listed; the list is the semantic vocabulary above | A `TableStyle-*` prefix rule is a rule about *one* generator's naming. DITA, DocBook and WebWorks each have their own noise, and a strip-list would need extending per engine while silently passing anything unforeseen. A keep-list fails closed and is auditable in one place. |
| **The keep-list is a module constant, not config** | `tables.SEMANTIC_CLASSES` | `reframe.yaml` is editorial policy a writer tunes. This is a fact about the source vocabulary, changes only when an engine is added, and belongs beside the code that reads it — the same argument `SPAN_TO_TAG` already makes in `webworks.py`. |
| **An emptied `class` is removed, not left empty** | `class=""` never appears in the output | An empty attribute is the one shape that is neither the old output nor the clean one, and it would defeat a grep written against either. |
| **Layout attributes untouched** | `border`, `cellpadding`, `cellspacing`, `width`, `valign` all survive | They change rendering. This phase is a cleanup with no visible effect; bundling a rendering change into it would make any regression ambiguous. |
| **No new finding code** | Nothing is reported | Nothing here can fail or be ambiguous. A counter on a cleanup that always succeeds is a line nobody reads. |

#### What this costs downstream

The output of `convert` changes for every version with a passthrough table, so EMS must be re-converted, re-reframed and re-synced. **No path and no anchor changes**, so `toc.yml`, `csh.yml`, `redirects.yml` and the 8,639-row published map are all byte-identical across the change — which is the assertion worth making explicitly, because it is what makes this safe to run against a signed-off pilot. The merged pages themselves change in exactly one respect and `reframe` will report all six versions stale, which is correct and expected.

*Exit: EMS re-converts with **0** `TableStyle-*` classes and **980** semantic classes surviving in the same 899 files; `toc.yml`, `csh.yml` and `redirects.yml` byte-identical before and after; `validate` reports no new findings; a unit test pins the root-element case that the predecessor's off-by-one would fail.*

#### Phase 21 — **Built & verified, 2026-09-28**

Built as planned, in two files. `tables.scrub` walks `[table, *table.find_all(True)]` and `tables.passthrough` calls it; `webworks.KEEP_CLASSES` widens the keep-list with `SPAN_TO_TAG`'s keys, which the plan did not anticipate and which matters: in that engine the class name *is* the markup — a span is code by virtue of being `class="Code"` — and the passthrough branch is the one place that never got rewritten into `<code>`. Dropping them would have made it the only part of the corpus where that distinction was gone for good.

**Verified by re-converting EMS 10.5.1 to a scratch tree and diffing against the published one:**

| | before | after |
|---|---:|---:|
| `TableStyle-*` classes | **4,272** | **0** |
| semantic classes | 168 | **168** |
| `toc.yml` | — | byte-identical |
| `metadata.yml` | — | byte-identical |
| `.md` files differing | — | 149 |
| **files differing by anything other than a `class` attribute** | — | **0 of 1,441** |

That last row is the one that matters: strip `class="…"` from both trees and all 1,441 pages compare equal. No path moved and no anchor changed, so nothing the *converter* produces is affected beyond the classes.

**But "the merge layout is unaffected" — claimed here when this note was first written — is false, and the corpus rebuild showed it.** The packer sizes pages by word count, and a scrubbed `class="TableStyle-…"` is words. Re-converting all six EMS versions and re-merging moved two of them: **749 → 747 pages** (10.4.1 126 → 125, 10.4.0 129 → 128, the other four unchanged) and the review queue **109 → 115 rows**. Redirect coverage is unchanged at **8,613 rows**, so no topic gained or lost a redirect; only two page boundaries moved, and `REDIRECT_SHADOWED` went 30 → 32 as two more leaders became case-only self-redirects. `validate` is **0 errors** either way. The claim was wrong because it reasoned about the converter's output in isolation and the packer reads that output; the corrected statement is that the *content* is unaffected and the *layout* shifts by two pages.

**Open, found here and not fixed: a converter change does not invalidate a merged tree.** `reframe`'s currency check keys on `convert_source_checksum` — the *extracted* package — plus the policy key, so after re-converting with the scrub in place all six versions reported `Already current` while holding pre-scrub HTML. `--force` is the workaround and it is not discoverable. The fix is to key on something the converter's own output moves; it is not in this phase because it changes when every product re-merges, not just EMS.

The surviving 168 are exactly the declared vocabulary — `varname` 103, `MCXref xref` 35, `tabletitle` 10, `filepath` 7, and single figures of `option`, `noteHeadInTable`, `autonumber`, `note`, `noteTip`, `noteWarning`, `groupOfURLs`.

This version has no `csh.yml` to compare — EMS is the empty-alias-file case (`has_csh: true`, `csh_names: 0`, §5.3.1), so the byte-identity claim for the help map is carried by the other five versions at the corpus rebuild rather than by this one.

Six new tests, one per decision, including the root-element case the predecessor's off-by-one would fail. Suite **1,500 passed, 2 skipped**.

---
