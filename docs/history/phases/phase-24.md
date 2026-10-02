> Archived from `docs/planning.md` on 2026-10-02. Status: **Built & verified, 2026-09-28**. Kept verbatim; a heading that says *Planned* was built later in this same section.
> Index of every phase: [`docs/planning.md`](../../planning.md#finished-phases).

### Phase 24: The Row Stops One Stage Short — **Planned, 2026-09-28**

`versions.csv` records a before and an after, and §3.9 says so in as many words: "the before/after pair to read across a row is `doc_files` -> `out_files`". That sentence was true when `convert` was the last stage that changed the shape of the tree. It has not been true since Phase 20. The merge is the stage that does the compression, and **its result is recorded nowhere that survives the run**.

**What a row says today, for the pilot:**

| version | `_doc_files` | `_md_files` | `_out_files` | after reframe |
|---|---:|---:|---:|---|
| 10.5.1 | 2,268 | 1,441 | 1,476 | *not recorded* |
| 10.5.0 | 2,268 | 1,441 | 1,476 | *not recorded* |
| 10.4.4 | 2,247 | 1,429 | 1,463 | *not recorded* |
| 10.4.3 | 2,247 | 1,429 | 1,463 | *not recorded* |
| 10.4.1 | 2,258 | 1,442 | 1,475 | *not recorded* |
| 10.4.0 | 2,276 | 1,457 | 1,494 | *not recorded* |

The last column exists on disk — 10.5.1's merged tree holds **124** Markdown files in **163** files total, 10.4.0's **128** in **169** — and it exists in `ReframeStats` for the length of one process. `_report_reframe` prints "`{topics} topic(s) read into {pages} page(s)`" and then the numbers are gone. Worse, they are gone *selectively*: the `CURRENT` branch returns `topics=0, pages=0` without reading anything, so the second run of `reframe` over an unchanged tree prints **nothing at all** where the first printed 747 pages. The one stage whose entire purpose is a ratio is the one stage that cannot tell you the ratio on a re-run.

#### Decisions

| decision | what gets built | why not the obvious alternative |
|---|---|---|
| **Two new columns, `_reframed_md_files` and `_reframed_files`** | a third inventory block in `catalog._VERSION_COLUMNS`, `ProductVersion`, and `record_reframe_inventory` / `clear_reframe_inventory` | The pair mirrors `_md_files`/`_out_files` for the same reason that pair exists: the Markdown count is the thing that changed shape, and the total is what the folder actually holds. A single column would force every reader to guess which one it was. Kept apart from the Stage 5 block for the reason that block is kept apart from Stage 4's — discarding a merged tree must not blank a conversion measurement that is still true. |
| **Walked, not derived from `len(built)`** | one `rglob` after the swap, the same shape as `converter._measure_output` | `len(built)` is 124 and the merged tree holds 163 files: `toc.yml`, `reframe.yml`, `redirects.yml`, `301.yml`, `review-queue.csv`, `csh.yml` and the copied assets. The artifact set is *conditional* — `csh.yml` only for a non-empty map, `301.yml` only for a declared origin template — which is precisely the arithmetic that was already found wrong once at Stage 5. A walk cannot be wrong about it. |
| **The walk cross-checks the counter** | `_reframed_md_files != len(built)` records `REFRAME_SELF_CHECK_FAILED` | The measured corpus says they agree exactly (128/128, 124/124) — every merged page is one `.md` and nothing else writes one. That is a real invariant, so a disagreement means a page write landed somewhere unintended, which is the failure Stage 5's equivalent check was added to catch. Free, since the walk is happening anyway. |
| **`CURRENT` backfills blank columns** | the `CURRENT` branch reads the two columns and measures the tree if either is blank | Exactly what `convert` already does at `driver.py:230`, and for the same reason: a version that was merged before these columns existed is as real as one merged today, and leaving it blank forever makes "never reframed" and "reframed before Phase 24" the same row. |
| **Two percentages, never one** | the reframe summary prints both `_md_files → _reframed_md_files` and `_doc_files → _reframed_md_files` | They measure different things and a single number would silently be whichever the reader assumed. 1,441 → 124 is **91.4%**, and it is the merge's own work. 2,268 → 124 is **94.5%**, and most of the gap between them is `convert` skipping files rather than anything being compressed — `_doc_files` counts source HTML the converter never had to emit. Publishing only the second would credit the merge with the converter's skips; publishing only the first would hide the end-to-end figure that is the actual question. |
| **The summary, not `status`** | `_report_reframe` gains the funnel line; `Funnel` is untouched | `status`'s funnel counts *versions* at each step, and every row in it is a version count. Putting a file count in it would make one row mean something different from all the others. |

#### What this does not do

It does not backfill history. The columns fill as `reframe` runs, and a version that is `CURRENT` fills on the next invocation of the command — no migration pass, no re-merge. It also does not touch `_api_files`, which stays absent at this end for the reason §3.9 already gives: the merge does not read API trees any more than the converter does.

*Exit: all six EMS rows carry `_reframed_md_files`/`_reframed_files`; `reframe` over an unchanged tree prints the same funnel as the run that built it; the walked Markdown count equals `len(built)` on every version; a re-run with no changes leaves `versions.csv` byte-identical; tests pin the `CURRENT` backfill, the `clear_` symmetry, and the two percentages against the measured 1,441 → 124.*

#### Phase 24 — **Built & verified, 2026-09-28**

Four files plus tests. `models.ProductVersion` gains the two optional ints; `catalog` gains the columns, `_REFRAME_COLUMNS`, `record_reframe_inventory`, `clear_reframe_inventory` and the third `_inventory_notes` check; `reframe/driver` gains `_measure_merged`, the two `ReframeResult` fields, the two `ReframeStats` properties, the `CURRENT` backfill and the page-count cross-check; `cli` gains `_report_reframe_funnel` and `_pct`, and `_report_reframe` takes the manager.

**Measured against the six EMS versions, on the `CURRENT` path — the case that previously printed nothing at all:**

```
Files: 13564 source doc -> 8639 converted -> 747 merged
       (91.4% fewer at the merge, 94.5% end to end);
       979 file(s) standing in the measured merged tree(s).
```

| version | `_doc_files` | `_md_files` | `_reframed_md_files` | `_reframed_files` |
|---|---:|---:|---:|---:|
| 10.5.1 / 10.5.0 | 2,268 | 1,441 | 124 | 163 |
| 10.4.4 / 10.4.3 | 2,247 | 1,429 | 123 | 161 |
| 10.4.1 | 2,258 | 1,442 | 125 | 162 |
| 10.4.0 | 2,276 | 1,457 | 128 | 169 |
| **total** | **13,564** | **8,639** | **747** | **979** |

The page totals match Phase 23's exactly — 124/124/123/123/125/128 = 747 — which is the row that says this measured the merge rather than changing it. The second invocation printed the identical funnel from the columns without walking a tree. `versions.csv` grew two cells on every row and changed nothing else: of 5,182 modified lines, seven carry a value and the rest gained `,,`.

**Suite: 1,564 passed, 2 skipped** (20 new), `ruff` clean.

**One thing worth recording about the cross-check.** `_reframed_md_files == pages` held on all six versions, which is what made it worth adding as a finding rather than a comment — the invariant is real and cheap, and it is Stage 5's `OUTPUT_COUNT_MISMATCH` one stage later. It has not fired.

---
