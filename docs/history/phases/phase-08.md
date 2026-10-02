> Archived from `docs/planning.md` on 2026-10-02. Status: **Complete, 2026-09-16**. Kept verbatim; a heading that says *Planned* was built later in this same section.
> Index of every phase: [`docs/planning.md`](../../planning.md#finished-phases).

### Phase 8: The Code-Span Link Swallow

Phase 7 closed the last numbered stage, so what is left are the Opens the earlier phases named rather than fixed. This is the largest of them, and it is not a stage: it is one behaviour in the walk that every engine shares, and it silently loses more links than any defect the tool has found so far.

**The defect, in one sentence.** `transforms/markdown.py` renders a code span from its *text*, so an `<a>` inside one never reaches `link()` — the engine hook that resolves references, copies assets and records `TOPIC_LINK_DANGLING`. `<code><a href="tibems-status.htm">tibems_status</a></code>` becomes `` `tibems_status` `` and the reference is gone before any engine sees it. It is invisible in the findings register in both directions: no URL is emitted, and no dangling link is raised either, because the reference is never *classified* rather than dropped. 6e named it and left it, because it is a change to the walk every engine runs and 6e's scope was the API-link rewrite.

##### The measurement

**It is six sites, not one.** This is the first thing the measurement found and it is the reason the phase is bigger than 6e's paragraph implied. Every engine's `inline_override` maps a *class* to code and renders it the same flattening way, and `<pre>` renders a fence from the same call:

| Site | What it swallows |
| :--- | :--- |
| `transforms/markdown.py:303` | `code`, `tt`, `kbd`, `samp` — the shared inline path |
| `transforms/markdown.py:211` | `pre` — the shared **block** path, a fence |
| `engines/flare.py:276` | `span.filepath`, `span.codeph`, `span.userinput` |
| `engines/dita.py:238` | *any* tag classed `codeph`, `msgph`, `filepath`, `varname`, `parmname`, `cmdname`, `apiname`, `userinput`, `sysout`, `option` |
| `engines/docbook.py:238` | `span.command` |
| `engines/webworks.py:317` | `span.Code`, `span.CodeItalic`, `span.CodeBold`, `span.Command`, `span.URL`, `span.ErrorVariable`, `span.codeph` |

6e's published figure — **7,999 of 931,715 relative anchors, 7,761 of them alone in the span** — counted the first row only. Re-measured over all six (`C:\tmp\codespan_shape.py`, `lxml`, API roots excluded, 2026-09-16), over **all 13 in-scope products, 88,691 files**:

| | Links | |
| :--- | ---: | :--- |
| **Swallowed relative anchors** | **13,126** | Two thirds again the published figure, because the published figure counted one site of six. |
| …inside a `<pre>` | **4,964 (37.8%)** | A fence cannot hold a link. A different problem, below. |
| …in an inline span | **8,162 (62.2%)** | The fixable half. |
| **…of those, the anchor is the span's whole content** | **7,863 (96.3%)** | Invertible to ``[`text`](url)``. |
| …and the anchor is the span's **direct** child | **7,645**, with **218 wrapped** | All 218 are DocBook, which nests the anchor inside another element. The test is therefore on the *text*, not on the child list — a direct-childness check would have silently skipped every DocBook case. |
| …the anchor shares the span | **299 (3.7%)** | Needs its own answer; GFM has none. |
| …spans holding more than one anchor | **68** | The pathological case is 68 spans. |
| By engine | Flare **12,386**, DocBook **597**, DITA **143**, WebWorks **0** | DITA's 143 against 6e's 79, and DocBook's 597 against 224, is the class sites showing up. DocBook's split is `span.command` 269, `<code>` 174, `<pre>` 104, `<tt>` 50 — four of the six sites in one engine. WebWorks' 0 is only its *relative* anchors: its cross-references are `javascript:WWHClickedPopup(...)` and the scan cannot classify them, which is why the acceptance run below still finds 30 to recover there. |

**The shapes, sampled from `ems`.** The `<pre>` cases are C API signatures whose return type links to the type page — `<pre><a href="tibems-status.htm">tibems_status</a> tibems_GetAllowCloseInCallback(...)</pre>` — repeated across a reference guide. The shared spans are short and regular: `<code><a href="overflowpolicy.htm">overflowPolicy</a>=rejectIncoming</code>`, `<code>mode=<a href="stores.conf_Parameters.htm#mode">sync</a></code>`, `<code><a href="commit.htm">commit</a> and <a href="autocommit.htm">autocommit</a></code>`. None of them is a link that happens to be in a code span; all of them are a code token one *part* of which is a link.

**Two facts verified before designing, because both could have sunk a branch.** `validation/references.py` reads **both** candidate output forms with no change to it: `mask_code` blanks a backtick span but preserves offsets, so ``[`MessageListener`](../api/x.html)`` still matches `_MD_INLINE`, and a raw `<code>…<a href="b.md">…</a></code>` is not masked at all — `_CODE_SPAN` matches backticks, not tags — so `_HTML_REF` finds it and reports it with `syntax="html"`. Stage 8 will check whatever this phase emits. And `link()` **has side effects**: Flare's calls `self.engine.dangling_link(...)` and `self._asset(...)`, which copies files. Reaching it for 8,162 anchors that never reached it before will move `TOPIC_LINK_DANGLING` volumes and may copy assets nothing copied before. That is the fix working, not a regression, but it has to be measured rather than discovered.

##### The design

**One shared helper, called from all five inline sites.** `Renderer.code_span(tag)` in `transforms/markdown.py` replaces every `code_transform.inline(markdown.text_of(tag))` in the four engines and the one in the shared walk. The rule that four engines each re-implement is the rule that four engines each get wrong differently — the 7b ledger row on two implementations of one decoding rule applies here unchanged, and this time there are four.

- [x] **The anchor alone in the span inverts the nesting.** One anchor, whose text is the span's whole text, and `self.link(anchor)` returns a URL: emit ``[`text`](url)``. The URL comes from the hook, never from `href`, so §5.4's invariant 13 holds and API rewriting, asset copying and dangling-link recording all happen for the first time on these references. CommonMark binds a code span tighter than a link, so a `]` inside the backticks does not close the link text — asserted rather than assumed.
- [x] **`link()` returning `None` keeps today's output exactly.** A `javascript:` skin button or an unresolvable target renders as the plain code span it renders as now. The fix adds links; it never removes a code span.
- [x] **A span sharing its content with an anchor is emitted as raw HTML** — `<code>` with the anchors rewritten through the existing `Renderer.rewrite`, which already resolves `href` and `src` inside a subtree and unwraps a dead link while keeping its words. This is `_KEEP_AS_HTML`'s precedent and `tables.passthrough`'s, both of them the same sentence: GFM has no syntax for this and dropping it changes what the text says. It is **299 spans**, it is validated by Stage 8 unchanged, and the alternative — splitting `mode=sync` into `` `mode=` `` followed by ``[`sync`](url)`` — invents two code tokens where the author wrote one.
- [x] **Nothing is emitted from source attributes.** The raw-HTML branch rebuilds `<code>` from the subtree's text and its rewritten anchors rather than dumping the source tag, so `class="memberNameLink"` and friends do not reach the output.

##### What is deliberately not built, each with its number

- [x] **`<pre>` keeps its fence and its links stay lost — 4,964 of the 13,126 (37.8%), and this is the one call in the phase worth arguing with.** A GFM fence cannot contain a link at all, so the only way to keep these is to emit the whole block as passthrough HTML, and that trades a correct, portable, copy-pasteable code block for an HTML blob in every one of ~4,964 blocks to recover a decorative type cross-reference in a function signature. The reader of a C signature loses more than they gain. **The alternative is one line of code** — `_block`'s `pre` arm calling `tables_transform.passthrough(self.rewrite(tag))` when the block holds a link, exactly as `table` already does — so this is a preference, not a limit, and it can be flipped at approval.
- [x] **A new note code, `CODE_LINK_FLATTENED`, records the residue.** Register **37 → 38**, `NOT_YET_EMITTED` stays at 1. If `<pre>` stays out of scope then the phase ends with thousands of links still silently dropped, and *silently* is the word this phase exists to delete. A note, folded on `(code, slug, version)` with a `count`, is what §7.5 already does for magnitude-without-action; it makes the residue a number in the run report instead of a paragraph in a design document. If `<pre>` is brought in scope instead, the code still earns its place for the handful the fence branch cannot take.
- [x] **No change to `validation/references.py`.** Verified above: it already reads both forms.
- [x] **No language inference on the fences it touches.** `transforms/code.py`'s docstring forbids it and nothing here revisits that.

##### Acceptance

- [x] **The count is completed over the remaining ~64 trees** — msg-akd-repo, rtview, sfire-sfds, tea, tpm-rest, tps and the rest of amx-bpm — so the phase's headline number is the corpus's, not a third of it.
- [x] **One version per engine converted before and after, and the two runs reconcile**, as 6e's did: links emitted go up by exactly the number of anchors the new branch resolved, and nothing else moves except `TOPIC_LINK_DANGLING` and the asset count, both of which are named with their deltas rather than absorbed.
- [x] **`ems/10.4.0` is the acceptance case.** 6e measured 8 of its 89 API references rewritten, the other 81 lost to this defect; after the fix that number is the count of API references whose target resolves, and the shortfall paragraph in `architecture.md` §6.4 is rewritten rather than left standing.
- [x] **`validate` over the sample published tree still reports two errors and no more**, with the new links checked and any new dangling ones named.
- [x] Unit tests in `tests/unit/test_transforms.py`'s markdown-walk section, using its `render()` helper: the inversion, the `link()`-returns-`None` passthrough, the `]`-inside-backticks case, the shared-span HTML, the multi-anchor span, and a `<pre>` holding a link asserting today's fence — a test that pins the decision rather than the accident.
- [x] **Docs in the same commit** — `design.md` §5.1's walk gains the rule and §12 an index row; `architecture.md` §6.4's shortfall paragraph and the §7.5 register row; `user-guide.md` if the output form is visible to a reader; `CONTEXT.md` a ledger row and the status line.

##### What the acceptance run actually said

One version per engine, converted twice in one process — once with `Renderer.code_span` and once with it monkeypatched back to the flattening it replaced, which is exactly the five inline sites' old behaviour (`C:\tmp\acc_p8.py`, 1,073s, 2026-09-16):

| Version | Engine | References emitted | API URLs | `TOPIC_LINK_DANGLING` | HTML spans | Flattened |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: |
| `ems/10.4.0` | Flare | 1,178 → **2,795** (+1,617) | 6 → **86** | 1 → 2 | 406 | 1,179 |
| `sfire-sfds/10.6.5` | DocBook | 15,093 → **15,163** (+70) | 30 → 30 | 39 → 39 | 10 | 2 |
| `amx-bpm/4.2.0` | DITA | 17,654 → **17,680** (+26) | 696 → 696 | 2,328 → 2,328 | 16 | 49 |
| `bcedi/6.10.0` | WebWorks | 1,180 → **1,210** (+30) | 1 → 1 | 0 → 0 | 0 | 0 |

**The reconciliation holds in all four.** References go up and nothing goes down. `TOPIC_LINK_DANGLING` moves once, by one, in `ems` — a link that was never classified now is, and it does not resolve, which is the finding appearing for the first time rather than a regression. The other three do not move it at all.

**`ems` is the acceptance case and it is the one that mattered.** 6e measured 8 of its 89 API references rewritten and named the other 81 as lost to this defect; the fix takes it to **86**, and the three that remain are `<pre>` residue, which is the trade the phase made on purpose. The 1,617 recovered references are 1,617 links that reached `link()` for the first time — resolved, asset-copied and classified — against 1,179 the fence still flattens.

**WebWorks scored 0 in the static scan and recovers 30 here**, which is the scan's limit rather than the engine's: its cross-references are `javascript:WWHClickedPopup(...)`, which `links.classify` cannot call relative, so the count never saw them. The engine's own `link()` resolves them.

**DITA's 26 against a swallowed count of 143** is the class-site arithmetic: most of `amx-bpm`'s are inside `<pre>`, and its 49 flattened says so.

---
