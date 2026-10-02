> Archived from `docs/planning.md` on 2026-10-02. Status: **Built, 2026-09-23**. Kept verbatim; a heading that says *Planned* was built later in this same section.
> Index of every phase: [`docs/planning.md`](../../planning.md#finished-phases).

### Phase 19: A DocBook Admonition's Title Is Not Only a Label — **Built, 2026-09-23**

18e's `validate` produced exactly one class of finding over the whole `streaming` family, and this phase is it. `engines/docbook.py:_admonition` deletes the `h3.title` because GFM's alert syntax draws the label itself (§5.6.7) — correct for the 96.3% of titles that say nothing but "Note". For the rest, the `h3` is carrying two things the deletion takes with it.

##### The defect, stated precisely

The engine **records an anchor it does not emit**. `_prune_anchors` (`docbook.py:795`) runs at line 523, keeps every `a[name]` something references, and returns that set as the page's `anchors`. Rendering happens afterwards, and `_admonition` (`docbook.py:186`) calls `title.decompose()` on the whole `h3` — taking a surviving `<a name="mapsUsageNote"></a>` with it. Nothing notices, because the two halves never speak: the page still *claims* the anchor, so `link()` (`docbook.py:662`) resolves every inbound `…#mapsUsageNote` and emits a live link into it. The result is a link the converter is confident about, pointing at a fragment that was deleted three hundred lines earlier — invisible until a published tree is walked.

That is why this only surfaced at Stage 7. It is not a link the engine dropped and reported; it is a link the engine *kept* on the strength of a promise it then broke.

##### Measured over every DocBook tree in the extraction cache

8 trees (the 6 `tibco-streaming` versions and the 2 `spotfire-data-streams` ones — the whole of the extracted DocBook corpus), **10,757 titled admonitions**:

| | count | share |
|---|---:|---:|
| titled admonitions | 10,757 | 100% |
| title is exactly the kind label ("Note", "Caution") | 10,361 | 96.3% |
| **title is something else** | **396** | **3.7%** |
| **title carries an anchor** | **40** | **0.37%** |

By kind: note 5,496, caution 2,731, important 1,717, tip 465, warning 348. The 40 anchored titles are 32 `note` and 8 `important`.

The 396 custom titles are not noise, and they are not evenly spread — they are a short vocabulary repeated across versions:

| title | occurrences |
|---|---:|
| `Disclaimer` | 120 |
| `Notes` | 96 |
| `Third-Party Software` | 42 |
| `Usage Note` | 16 |
| `Deprecated` / `DEPRECATED` | 22 |
| `Documents or My Documents?` | 14 |
| `Caution 1` / `Caution 2` / `Caution 3` | 24 |
| `Note on Backslashes in Examples` | 8 |
| the remaining 8 distinct titles | 54 |

`Disclaimer`, `Third-Party Software` and the numbered `Caution 1..3` are the ones that make the case: a box labelled "Disclaimer" rendered as a bare `> [!NOTE]` has lost the only word that said what it was, and a cross-reference reading "see Caution 2" now points into a page with three indistinguishable cautions.

##### What gets built

**1. The anchor survives the title.** `_admonition` harvests `markdown.anchor_target()` from every `a[name]`/`id` inside the `h3.title` *before* decomposing it, and emits `markdown.anchor_marker()` as a block immediately above the alert. Both helpers already exist (`transforms/markdown.py:120,135`) and are what `inline_override` (`docbook.py:228`) already uses for every other kept anchor in the engine, so this is the existing mechanism reaching one element it could not reach, not a new one.

Above the box rather than inside it: an `<a id>` is a block-level HTML line there, unambiguous to every renderer, and it cannot interfere with GFM's alert parsing — which is sensitive to what follows `> [!NOTE]`. Landing the reader at the top of the box is also what the DocBook anchor meant.

**2. The custom title survives as the alert's first line**, bolded, when and only when it is not the kind label — `callouts.alert_for(title_text)` is the existing test and it already folds case and punctuation (`callouts.py:53`), so `Note:`, `NOTE` and `note` are all recognised as the plain label and still deleted. The 10,361 ordinary ones are untouched and the double-label trap §5.6.7 exists to avoid stays closed.

**3. `_prune_anchors`' promise becomes checkable.** The set it returns is the page's `anchors`, and the whole defect is that rendering can silently fail to honour it. The renderer asserts the kept set against what was actually emitted and records the difference rather than letting it pass — a converter that believes in an anchor it dropped should say so at Stage 5, not at Stage 7 two commands later.

##### Acceptance

- `validate --target-dir … --product tibco-streaming` and `--product spotfire-data-streams` report **0 `ANCHOR_MISSING`**, down from 114 and 38.
- Re-converting the 8 DocBook versions changes **exactly** the admonition blocks: 40 anchor markers added, 396 titles restored, and no other diff in 15,261 output files.
- The 10,361 plain-labelled admonitions are byte-identical to what ships today.
- No new finding code; `ALERT_LABEL_UNMAPPED` stays unreachable from this engine, because a custom title is not an unmapped label — it is a title, and it is now kept rather than matched.

##### Shipped, measured 2026-09-23

Re-converted all 30 `streaming` rows, re-synced, re-validated.

| | before | after |
|---|---:|---:|
| `tibco-streaming` anchors resolved | 34,674 / 34,788 | **34,788 / 34,788** |
| `spotfire-data-streams` anchors resolved | 11,528 / 11,566 | **11,566 / 11,566** |
| `ANCHOR_MISSING` | 152 | **0** |
| findings, whole family | 152 warnings | **none** |

**The diff is purely additive, and that is the acceptance criterion rather than a pleasant surprise.** Against the previous publication of `tibco-streaming@11.2.1` as a byte baseline: **38 of 2,538 files changed, 92 lines added, 0 lines removed, 0 files added or dropped.** The added lines are exactly the restored titles and the anchor markers — `**Disclaimer**` 12, `**Notes**` 8, `**Third-Party Software**` 5, `**Usage Note**` 2, `**Caution 1/2/3**` 1 each, two `<a id=…>` markers, and the `>` continuation lines the blockquote needs. All five anchored admonitions are emitted in all six `tibco-streaming` versions.

`sync` then reported **8 synced and 68 already-current** — it re-copied the 8 `online-help` trees and nothing else, which is the idempotency rule of 6b holding on a real change rather than on a re-run.

##### The guard found a second population on its first run, and that is the point of it

`ANCHOR_DROPPED` fired **7 times across 6 pages** — `d0e3280`, `d0e5253`, `d0e3109`, `d0e3244`, `d0e12125` — and none of them is an admonition. They are DocBook's auto-generated `a.indexterm` anchors sitting **inside table cells**, kept by `_prune_anchors` because something references them and then lost on the table path. A second instance of the same class of bug, in a different handler, that nothing in the tool had ever said a word about.

**None of the 7 produces an `ANCHOR_MISSING`**, because no inbound link to them survives into the published tree either — so the guard is reporting a broken promise that nothing happened to depend on. That is the right side to err on: it fires when the engine contradicts itself, not when a reader notices. Left unfixed and named here rather than folded into this phase; it is the table renderer's, not the admonition handler's.

##### Cost, as built

One function in one engine (`_admonition`), one line in `inline_override`, one comparison in `_convert`, and the register's 44th code. **1,345 tests pass, 2 skipped, lint clean** on `src` and `tests`.

---
