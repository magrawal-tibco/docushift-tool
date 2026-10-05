> Archived from `docs/planning.md` on 2026-10-05. Status: **Complete, 2026-10-05**. Kept verbatim.
> Index of every phase: [`docs/planning.md`](../../planning.md#finished-phases).

### Phase 39: A PDF-Only Package Is Not Blocked — **Complete, 2026-10-05**

**Why.** The user asked on 2026-10-05 whether `format-unknown` (Phase 38) also covers a
package that holds only PDFs. It does, and that is wrong in a way that skews the
report. Measured 2026-10-05 over the 53 `format-unknown` versions by walking their
extracted trees: **52 hold no HTML at all**, 1 to 38 PDFs each, so there is nothing to
convert. Their PDFs already publish through `sync`'s document doc-classes. **One**,
`tibco-modelops@1.3.0` (141 HTML pages, Doxia), is genuinely unconvertible. The report
calls 58 versions blocked when 6 are. Phase 38's sync rule also counts only
`online-help`, so these 52 never read `synced` even though their PDFs are placed.

The Stage 4 inventory already separates the two cases exactly: all 52 have `document`
files and no `topic` files in `asset_inventory`, while ModelOps has topics.

#### Decisions

| decision | choice | why |
|---|---|---|
| **New `_status` value** | `pdf-only`: unpacked, engine not convertible, no `topic` files and at least one `document` file in the inventory | The inventory is the evidence the extractor already wrote, so the rule reads no file. `format-unknown` keeps its meaning, and is narrower: HTML the tool cannot convert |
| **Not blocked** | The status page counts `pdf-only` as its own state, "PDF only, nothing to convert", not under Blocked | A person has nothing to do. The version is done in the only way it can be |
| **Sync for a PDF-only version** | `sync` records a second event kind, `sync-docs`, when any document doc-class is `SYNCED` or `CURRENT`. A `pdf-only` version's `_sync_status` reads from it; every other version still reads from the `online-help` placement. `out-of-date` for `pdf-only` compares against the last extract, since that is where its PDFs come from | "Synced" keeps meaning "what this version has to publish was placed". A converted version whose PDFs were placed but whose help was not still does not read `synced` |
| **Back-fill** | None. The 52 read `synced` from their next `sync` | The documents placed before today were not recorded, and a date is not guessed |

#### Steps

1. `state.py`: `content_kinds()`, topic and document file counts per version from `asset_inventory`.
2. `reporting/status.py`: `pdf-only`, and the sync rule above; `sync/distributor.py`: record `sync-docs`.
3. Status page: a `pdf-only` state in the progress bar, the family table, the sheet-status table and the funnel; Blocked counts only what is blocked.
4. Tests; `catalog refresh`; diff the sheet (only `_status` / `_status_date` may change, on exactly the 52 rows).
5. Docs: `architecture.md` §3.2, `design.md` §8.8, `user-guide.md`, `quickstart.md`, `CONTEXT.md`.

*Exit: 52 rows read `pdf-only`, `format-unknown` is 1 (`tibco-modelops@1.3.0`), and no other cell changes. The page shows 6 blocked. Tests and lint clean.*

**As built (2026-10-05).** The user approved planning and building in one step. Steps 1–5 as planned, plus two additions:

- **Exit met.** `catalog refresh` moved exactly 52 rows from `format-unknown` to `pdf-only`, and no other cell changed (diffed against a copy taken first). `format-unknown` is 1, `tibco-modelops@1.3.0`. The page shows 6 blocked (1 format, 5 download) and 52 PDF only.
- **The PDF-only segment is violet** (slot 7: `#4a3aa7` / dark `#9085e9`). Aqua, the first choice, failed colour-blind separation beside the orange "blocked" status: ΔE 5.7 light and 2.9 dark. Violet passes beside its neighbours, with worst adjacent CVD ΔE 13.0 / 11.7 and normal-vision 16.3. Green also passed, but would read as a "good" status.
- **The page builder now refuses a `_status` value it does not know.** It used to count one as `not-started`. That briefly showed 1,589 not started, before `pdf-only` was mapped.
- **The 52 still read blank in `_sync_status`.** Their PDFs were placed before `sync-docs` was recorded, so they fill on their next `sync`, with no change to the target.
- **Tests:** 4 new and 1 updated in `test_version_status.py`. Full suite 2,140 passed, lint clean.
