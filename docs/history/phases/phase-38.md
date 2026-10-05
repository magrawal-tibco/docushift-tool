> Archived from `docs/planning.md` on 2026-10-05. Status: **Complete, 2026-10-05**. Kept verbatim.
> Index of every phase: [`docs/planning.md`](../../planning.md#finished-phases).

### Phase 38: Where Each Version Stands, on the Sheet — **Complete, 2026-10-05**

**Why.** The user asked on 2026-10-05 for a status column in `versions.csv`, with the
sync status and the date of the last status change beside it. Today the answer
lives only in `state.db`. It is visible through `docushift status` (counts, never rows)
and through `reports/conversion-status.html`, whose builder re-derives the same rules
a second time. Nobody filtering the sheet in Excel can see which version is where.

Measured 2026-10-05 against the catalog and `state.db`:

- **What the column would say today:** out-of-scope 983 · retired 1,513 · not-selected
  1,020 · not-started 1,537 · download-failed 5 · format-unknown 53 · converted 56 ·
  merged 14. No version is currently `downloaded`, `extracted` or failed at a later stage.
- **No stage records a date.** `version_state.updated_at` is overwritten by every write,
  and a rebuild rewrites it for every version. `convert_run` / `reframe_run` (run ids,
  hence a run start time) are the only dated per-version records, on 68 and 14 versions.
- **`sync` records nothing per version.** That is deliberate (§6.6, §7.2: currency is
  compared, never recorded). This phase changes that rule; see *Sync is recorded as an event* below.

#### Decisions

| decision | choice | why |
|---|---|---|
| **Columns** | Four read-only columns right after `_family`: `_status`, `_status_date`, `_sync_status`, `_sync_date` | Where a version stands is the first thing a spreadsheet user filters on, so the columns sit beside the family rather than at the far end. The inventory columns move four places right; no column is renamed |
| **`_status` values** | Gates: `out-of-scope`, `retired`, `not-selected`. Pipeline: `not-started`, `downloaded`, `extracted`, `converted`, `merged`. Stuck: `download-failed`, `extract-failed`, `format-unknown`, `convert-failed`, `merge-failed` | One value per version, lowercase and hyphenated like `retirement-announced`. `format-unknown` is its own value because it needs a person, not a re-run: the package is unpacked and the detected engine is `auto` or has no converter |
| **Precedence** | A gate wins. Otherwise a failed attempt at a stage beyond the furthest success wins. Otherwise the furthest stage that succeeded | Gates first matches `status`'s funnel, so the sheet and the command count the same. A version converted and later disabled reads `not-selected`; its output is still on disk and its sync columns still say where it went |
| **`_status_date`** | ISO date (UTC) of the event that produced the value; blank for gates and `not-started` | A date, not a timestamp: it is read in Excel, and the time is kept in `state.db` |
| **Dated events** | New `stage_event` table: one row per `(slug, version, stage)`, holding `outcome` (`ok` \| `failed`), `at`, and `target` for sync. Every stage upserts it per version | A key per stage in `version_metadata` would work, but the derivation reads all stages for 5,181 versions on every save, so it wants one indexed table |
| **Sync is recorded as an event, not as currency** | `sync` records *that it placed a version, where, and when*: `SYNCED` and `CURRENT` both count as placed. `_sync_status`: blank (never placed), `synced`, `out-of-date` (converted or merged again after the last placement), `sync-failed`. A `NO_OUTPUT` row records nothing | §6.6 forbade a stored *fingerprint*, because it would vouch for a tree somebody has since edited. An event vouches for nothing: it says what this tool did, on a date. `out-of-date` compares two of this tool's own events and never reads the target. A hand edit in the target is still invisible to the sheet, which is why `status --target-dir` and `validate` stay the evidence. §7.2 is amended to say so |
| **One target at a time** | The last placement wins. The target path is kept in `stage_event` and printed by `catalog show` | Syncing to a scratch folder and then to the real one is the normal flow. The sheet answers "when did we last place it", and the path answers where |
| **When the columns are written** | Computed on every catalog save from the catalog and `state.db`, like `_bu`. `download` and `sync`, which never save today, save once at the end of a run | Computed on save means the columns cannot drift from the database. One save per run is a second or so |
| **The sheet is open in Excel** | The stage's work stands and the run exits as it would have. A warning says the status columns were not refreshed. The next save catches up | A status column must never fail the work it describes |
| **On-demand refresh** | New `docushift catalog refresh`: rewrites every tool-owned column and changes nothing a human typed | For the Excel case above, and after `state.db` is restored |
| **Back-fill** | On the first save: `convert` and `merge` dates from `convert_run` / `reframe_run`; `download` and `extract` dates from `version_state.updated_at`, the best record there is. Sync starts blank | No date is guessed from file times. For the four families already placed, one re-run of `sync` fills the sync columns. It finds them `CURRENT` and changes nothing in the target |
| **The status page** | `scratch/build_conversion_status.py` reads the four columns instead of re-deriving them. "Published" becomes "synced", counted from `_sync_status` | One definition instead of two. The page stops needing the target folder |

#### Steps

1. `state.py`: `stage_event` table with record and read methods; schema version bump.
2. Record events: `download`, `extract`, `convert`, `reframe` per version (ok or failed), and
   `sync` per version for `SYNCED` / `CURRENT` / failure.
3. `reporting/status.py`: one `version_status()` that derives all four values from a
   version, its product and the events. The funnel's gate logic and this function share
   one helper, so the two cannot disagree.
4. `catalog.py`: the four columns in `VERSION_COLUMNS` after `_family`, filled at save and
   ignored on read; back-fill as above.
5. `download` and `sync` save at the end of a run; the Excel warning; `catalog refresh`.
   `catalog show` prints the four values and the sync target.
6. Status page builder reads the columns.
7. Tests: each value and the precedence rules; dates; a hand edit to the columns is
   discarded; Excel-locked save warns and the stage succeeds; `CURRENT` records a
   placement and `NO_OUTPUT` does not; `out-of-date` after a re-convert; back-fill.
8. Regenerate `versions.csv` with `catalog refresh` and diff it. Only the four new columns
   may change. Then re-run `sync` over the four placed families.
9. Docs: `architecture.md` §3.2 and §7.2 (amended) and §6.6 (a pointer); `user-guide.md`
   (reading the sheet); `quickstart.md` step 9; `CONTEXT.md`.

*Exit: all 5,181 rows carry the four columns. `_status` counts equal the measurement above
(or differ only by work run in between, named). Every other cell is byte-identical. After the
re-run of `sync`, the version folders already in the target read `synced` with today's
date and nothing in the target has changed. The status page matches `docushift status`.
Tests and lint clean.*

**As built (2026-10-05).** Approved by the user 2026-10-05. Steps 1–7 and 9 as planned;
step 8's `sync` re-run done by the user. Four departures:

- **No schema bump.** `stage_event` is a new table, and `state.py`'s own rule is that an
  additive table needs none: an existing v2 database grows it on open. The plan said bump.
- **Back-fill is computed, not written.** A version with no event is dated at read time
  from `convert_run` / `reframe_run`, else `version_state.updated_at`, so nothing is
  inserted that a stage did not record.
- **`catalog show` prints a second table** for the four values. As extra columns they made
  the catalog table too wide for an 80-column terminal, and the version column was cut.
- **The status page counts "synced"** from `_sync_status` (`synced` and `out-of-date`
  both count as placed), and blocked versions gain a third kind, "failed during
  processing", for the three `*-failed` values after download.

- **Exit, measured.** `catalog refresh` wrote the four columns on all 5,181 rows, and no
  other cell changed (diffed against a copy taken first). `_status` matches the plan's
  measurement exactly: not-started 1,537 · retired 1,513 · not-selected 1,020 ·
  out-of-scope 983 · converted 56 · format-unknown 53 · merged 14 · download-failed 5.
  The user's `sync` over activespaces, ems, streaming and tra found every version already
  current (0 synced, 0 failed), so nothing in the target changed. The target holds
  **36** `online-help` version folders (the plan said 37, a miscount), and exactly those 36 rows
  now read `synced` / 2026-10-05: 22 `converted`, 14 `merged`. The run changed no other cell, not even
  a `_status`. The status page rebuilt from the columns shows 36 synced.
- **Tests:** 16 new in `test_version_status.py`. Full suite 2,133 passed and 3 failed.
  Two failures were `catalog show` width, now fixed. The third,
  `test_the_shipped_report_retires_the_measured_set`, was already failing: it expects
  133 retired versions in the real catalog, and the catalog edits of 2026-10-05
  (`f00eb60`, `63384ce`) leave 123. No `release_status` or `convert_eligible` cell was
  touched by this phase. Traced to `f00eb60` alone (nine retired Nimbus versions made
  ineligible, PartnerExpress out of scope); the user confirmed it as intended, and the
  test was re-baselined to 123 / 9 in the commit that closes this phase. Lint clean.
