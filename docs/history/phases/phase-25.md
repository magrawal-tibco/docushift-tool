> Archived from `docs/planning.md` on 2026-10-02. Status: **Built & verified, 2026-09-28**. Kept verbatim; a heading that says *Planned* was built later in this same section.
> Index of every phase: [`docs/planning.md`](../../planning.md#finished-phases).

### Phase 25: The Migration Verdict Nobody Can Read — **Planned, 2026-09-28**

Someone has already decided, product version by product version, what moves to the new docsite. The decision lives in a spreadsheet — `TIBCO Docs on Docsite - tibco_versions.csv`, 3,722 rows, a `Migrate to New TIBCO Docsite` column reading `Migrate` (1,134) or `Do Not Migrate` (2,588). The catalog cannot see it. Nothing in the tool can.

**And it does not agree with the catalog.** Joined on `slug` + `version` — the slug recovered from `doc_url` by stripping the trailing dashed version — 3,312 rows match a catalogued version, and **458 of them disagree with `convert_eligible`**:

| | `convert_eligible=true` | `convert_eligible=false` |
|---|---:|---:|
| **Migrate** | 955 | **88** |
| **Do Not Migrate** | **370** | 1,899 |

The disagreement has one cause and it is structural. `convert_eligible` is today a perfect mirror of `is_archived` — 3,078 archived rows false, 2,103 live rows true, **zero exceptions across all 5,181 rows**. It carries no editorial signal whatsoever; it restates a column sitting two cells to its left. The sheet's verdict is a real decision that departs from archived status in 520 rows, and every one of the 458 conflicts is exactly that departure: all 88 in the top-right are `is_archived=true`, all 370 in the bottom-left are `is_archived=false`.

Nothing has been damaged yet. None of the 458 carries `custom_override=true`, and none has `_md_files` — not one has been converted. But the 88 are versions a human asked for that the pipeline would silently skip, and the 370 are versions a human declined that it would convert.

#### Decisions

| decision | what gets built | why not the obvious alternative |
|---|---|---|
| **Store the verdict, do not act on it** | two new columns; `convert_eligible` is not touched by any code path this phase adds | 458 rows is not a number to flip from a join written this afternoon. The verdict and the gate are two different facts and the catalog should be able to hold both at once and show them disagreeing — that disagreement *is* the review artifact. Overwriting `convert_eligible` directly would destroy the evidence in the act of using it, and leave no way to ask "which rows did the sheet change my mind about?" |
| **`migrate_decision` + `migrate_decision_source`, un-prefixed** | `MigrateDecision` (`migrate` / `do_not_migrate` / `unknown`) and `MigrateDecisionSource` (`manual` / `docsite_sheet` / `unknown`) on `ProductVersion`; two columns in `VERSION_COLUMNS` placed immediately after `convert_batch` | Exactly the shape of `release_status` / `release_status_source` (§3.11), because it is exactly the same kind of fact: an external editorial verdict resolved at merge time, carried in the sheet so the answer is visible without opening the source, and hand-overridable — hence no `_` prefix. The source column is what makes a re-import safe: `MANUAL` outranks the sheet and a re-apply resets only what it owns. A single column could not express "a human overrode this". |
| **A dated source file plus `config/docsite-migration.yaml`** | the sheet moves to `config/migration/tibco-docsite-2026-09-03.csv`; the YAML names the active file and carries an `aliases:` block | `eos.yaml`'s rule, for `eos.yaml`'s reason: a new sheet is a new file, not an overwrite, so the change is a reviewable diff rather than a silent re-decision of three thousand rows. The date is the sheet's own (`Marked Retired on support site (09/03/26)`). |
| **Join on the slug in `doc_url`, by string equality** | `doc_url` path minus the trailing `-{version with dots as dashes}`, tested against `products.csv` by equality; anything else goes in `aliases:` | Better than eos's position, which has only a display name: this sheet carries the canonical docsite URL, so the join key is the catalog key itself and no slugification guesswork is involved. It recovered the slug on 3,722 of 3,722 rows and matched 3,312. No fuzzy fallback, for the reason `scope.yaml` and `eos.yaml` both give. |
| **Unmatched rows are a finding, never a guess** | `MIGRATE_SHEET_SLUG_UNMATCHED` per unmatched slug, with its row count and how many are `Migrate` | 410 rows across **104 slugs** name products absent from the catalog, and 91 of those rows say `Migrate` — so this is not a rounding error, it is the set of renames the catalog has not absorbed. Several are plainly real: `tibco-liveview-web-enterprise-edition` → `spotfire-liveview-web-enterprise-edition`, `tibco-data-streams` → `spotfire-data-streams`, `tibco-nimbus-control` → `tibco-nimbus`. Every one gets reviewed and written into `aliases:` by hand, one at a time, exactly as eos's were. The largest single group is `tibco-flogo-enterprise` (38 rows, 15 `Migrate`). |
| **Absence stores `unknown`, not `do_not_migrate`** | a version with no sheet row gets `migrate_decision=unknown`, source `unknown` | 1,869 catalogued versions — 36% of the catalog, 778 of them currently eligible — have no row in the sheet at all. Defaulting them to "do not migrate" would silently convert a coverage gap into a decision, which is the failure mode §3.11's "ABSENCE NEVER RETIRES ANYTHING" paragraph exists to name. |
| **`catalog migrate` prints the conflict table** | a new command beside `catalog eos`, and `apply_migrate_decisions` also runs inside `catalog fetch` | The 2×2 above is the whole point of the phase and must be one command away, not a script someone writes twice. `catalog eos` is the precedent for both halves: a standalone re-apply for when only the sheet changed, and a call inside `fetch` so a crawl never leaves the column stale. |
| **`catalog set migrate_decision`** | the field joins the `set` dispatch, writing source `MANUAL` | A final call on 458 rows will be taken row by row, and it must survive the next fetch. `MANUAL` is the only thing `apply_migrate_decisions` will not overwrite. |

#### What this does not do

It changes no version's eligibility, schedules no conversion, and resolves none of the 458 conflicts — the final call is the user's and this phase exists to put it in front of them. It does not import the sheet's other two columns: `is_archived in docsite` is already in the catalog (and agrees, on 3,304 of 3,312 rows — the eight exceptions are `tibco-control-plane` 1.3.0–1.9.0, recorded here and left alone), and `Marked Retired on support site (09/03/26)` is `eos.yaml`'s job, resolved from a report the tool already reads. It does not add the 104 unmatched slugs to the catalog; discovery owns what exists.

*Exit: every catalogued version carries a `migrate_decision`; 955 + 1,899 agree with `convert_eligible`, 88 + 370 are reported as conflicts and 1,869 read `unknown`; `catalog migrate` prints the 2×2 and names all 104 unmatched slugs; a hand-set `manual` row survives `catalog fetch` and a re-apply; a re-apply with no sheet change leaves `versions.csv` byte-identical; `convert_eligible` is provably untouched — the same 2,103 rows are true before and after.*

#### Phase 25 — **Built & verified, 2026-09-28**

Six files plus tests, and the shape is §3.11's throughout. `models` gains `MigrateDecision` / `MigrateDecisionSource` and the two fields; `config` gains `MigrationSheet`, `load_docsite_migration`, `_read_migration_sheet` and the `_sheet_slug` recovery; `catalog` gains the two columns in `VERSION_COLUMNS` after `convert_batch`, `MigrateStats`, `apply_migrate_decisions`, `unmatched_migration_aliases` and the ranked `_resolve_migrate_decision` called from the fetch loop; `findings` gains three `Stage.CATALOG` warnings (register **54 → 57**); `cli` gains `catalog migrate`, `_record_migration_findings`, `_record_migrate_conflicts` and `set --migrate-decision`. The sheet moved to `config/migration/tibco-docsite-2026-09-03.csv` behind `config/docsite-migration.yaml`.

**Against the live catalog, first apply:**

```
| migrate_decision | eligible | not eligible |
| migrate          |      955 |           88 |
| do_not_migrate   |      370 |         1899 |
The export decides 3312 of 5181 catalogued versions; 1869 have no row in it and read 'unknown'.
WARN 458 version(s) disagree with convert_eligible (88 wanted but ineligible, 370 eligible but declined).
WARN 104 export slug(s) match no catalogued product -- 410 row(s), 91 of them marked migrate.
Recorded 562 warnings -- `docushift report --run 176`.
```

Every number in the plan reproduced exactly, from the shipped code rather than the afternoon's join — which is the only reason to trust the 458.

**`convert_eligible` is provably untouched.** Rows whose eligibility changed: **0**. True before and after: **2,103 and 2,103**. Of the 5,182 `versions.csv` lines that differ, the number differing by anything other than the two inserted cells: **0**. A second `catalog migrate` with no sheet change wrote a byte-identical file. Pinning one row by hand (`set --migrate-decision`) and re-applying moved the conflict count 458 → 457 and left the pin at `manual` — the row was then restored, so the catalog carries only what the export decided.

**Suite: 1,583 passed, 2 skipped** (16 new), `ruff` clean.

**Follow-through, same day: 94 of the 458 conflicts were resolved by hand in `versions.csv`, leaving 376.** 88 archived-but-wanted rows were made eligible and 6 retired-but-declined rows were made ineligible, so the split is now 6 migrate-but-ineligible and 370 eligible-but-declined. Two consequences worth naming. First, `convert_eligible` is **no longer a mirror of `is_archived`** — 94 rows now depart from it, which is the first editorial signal that column has ever carried and the outcome the phase was built to enable. Second, the retirement guard on the real three files moved: **`versions_retired` 139 → 133** (the 6 newly-ineligible rows are all retired) and **`products_fully_retired` 11 → 10** (`tibco-activematrix-businessworks-plug-in-for-twitter@6.1.2` became eligible and is retirement-announced, not retired, so the product is no longer wholly retired over its convertible set). **Not one of the 5,181 rows changed `release_status`** and `eos_coverage` is unmoved at 270/669, so the report's verdict is untouched in both directions — only the population it is measured over moved. `test_the_shipped_report_retires_the_measured_set` was re-baselined with that reading recorded in its docstring, as the three re-baselines before it were.

**Two things worth recording.** The first is that `catalog show` could not take a ninth column: adding a "Migrate?" column pushed the table past 80 columns and Rich elided the *Status* header, which a test caught. The verdict now lives inside the existing Eligible cell and only adds ink when it disagrees (`no (migrate)`) — which is better than the column would have been, because the cell that carries the conflict is the cell the conflict is about. The second is that the conflict finding is emitted from `_record_catalog_findings` as well as from `catalog migrate`, so a `fetch` or an `eos` surfaces the 458 too; a warning that only appears when you run the command that produces it is a warning nobody sees.

---
