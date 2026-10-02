> Archived from `docs/planning.md` on 2026-10-02. Status: **Complete, 2026-10-02**. Kept verbatim; a heading that says *Planned* was built later in this same section.
> Index of every phase: [`docs/planning.md`](../../planning.md#finished-phases).

### Phase 35: Every Published Version Carries Its Cutover Map — **Complete, 2026-10-02**

**Why.** Phase 33 left `301.yml` where Phase 22 put it: written by Reframe into `reframed/`. Two populations never get one published:

1. **Versions Reframe skips** (not Flare): Streaming ×6, Spotfire Data Streams ×2, Data Science Author 1.4.0, Administrator 5.12.x ×2, Runtime Agent 5.12.x ×3. Step 1 measured every one of them deriving cleanly.
2. **Flare versions that publish the converted tree** (`publish: false` in `reframe.yaml`): Administrator 5.13.0 and Runtime Agent 5.13.0 got a `301.yml` in `reframed/` on 2026-10-02. **Neither reached the published scratch tree**, because `sync` copies `output/` for them. Phase 33's report counted them as covered, which was true of `reframed/` and not of what ships.

The rule that fixes both: **the map belongs to whichever tree `sync` publishes from.** Only EMS and ActiveSpaces publish merged today.

#### Decisions

| decision | choice | why |
|---|---|---|
| **Where it is written** | `convert` writes `301.yml` into its staging tree before the swap, for every engine. Reframe keeps writing its own into `reframed/`, overwriting nothing it carried (`_REGENERATED` already lists it) | Same position as Reframe's: inside the tree, before the swap. Writing it in `sync` is the 20d.1 `filecmp` trap Phase 22 avoided: a file added to the published folder after the copy makes every version re-copy on every run |
| **`to` side in `output/`** | The converted output path, unmoved (`moved = {}`) | Nothing moved. `origins.rows` already treats a missing `moved` entry this way, which is why it works for a product that never reframes |
| **One builder, two callers** | `_write_origins`'s body moves into `origins.build(...)`, which returns the rows plus the findings to record. Reframe and convert both call it | Two copies of the declared/derived/listed rules would drift. Moving it puts the decision logic in a module with no stage dependencies |
| **Findings** | Both stages record the same four codes; their registered stage moves **reframe → convert** | A Flare version reports its unmapped pages once per run of each command. That's accepted: each run's report should be complete on its own. *Built differently from planned:* a code has exactly one stage, documented as "which command discovers the condition, not which one reports it", and after this phase that is `convert`; the run's command column already says which reported it. Register size unchanged at 66 |
| **Currency** | No new currency key. `301.yml` is rebuilt whenever the version reconverts; a newer sitemap needs `convert --force`, as it already needs `reframe --force` | A sitemap hash in the currency key would reconvert every version on each `catalog sitemap` refresh, for a file that is cheap to regenerate on purpose |
| **Counts** | `_out_files` grows by one where a map is written; `_md_files` is unchanged, so `OUTPUT_COUNT_MISMATCH` arithmetic is unaffected | Recorded so the `versions.csv` diff after the re-run is expected, not a surprise |

#### Steps

1. `origins.build`, Reframe switched to it (no output change: re-run reframe, all 14 `301.yml` byte-identical to Phase 33's).
2. `convert` writes `301.yml`; tests for a derived, a declared, a missing-sitemap and a not-derivable version.
3. **Run after Phase 36's `toc.yml` format change lands**, because both phases regenerate `output/` and `reframed/` and running twice wastes ~an hour: `convert --force` and `reframe --force` over the converted catalog, `sync` to a scratch target, `validate`.

#### Steps 1–2 — **Built, 2026-10-02**

`origins.build` (the declared/derived/listed rules, returning rows plus `(code, message, count)` findings), `origins.page_list` (cache read, never a fetch) and `origins.write` (the sidecar dump options, so both stages' files are byte-comparable — `converter` cannot import `reframe.manifest` without a cycle through `reframe/__init__`). `reframe/driver._write_origins` is now a call to it; `converter/driver._write_origins` writes into staging just before the swap, skipped without `state.db` as Reframe skips it.

| check | result |
|---|---|
| `reframe --all --force`, all 14 `301.yml` against Phase 33's | **14 of 14 byte-identical** |
| New converter tests | derived map in `output/` with `to` = output path and the unlisted API page reported; no sitemap → no file + `ORIGIN_SITEMAP_MISSING`; unconfirmable sitemap → no file + `ORIGIN_TEMPLATE_UNDECLARED` |

*Exit: every published `online-help` version with a sitemap page list has a `301.yml` in the published tree (expected: 30 as planned, 27 as measured — EMS 6, ActiveSpaces 6, Streaming 6, Spotfire Data Streams 2, Administrator 3, Runtime Agent 4; Data Science Author 1.4.0 is in no convert batch, see step 3, Silver Fabric/PeopleSoft/Designer Add-in excluded for having no list); every derived `from` is in its sitemap; a sample of six URLs from the newly covered layouts is confirmed live; `validate` adds no finding from any `301.yml`; Reframe's 14 maps are byte-identical to Phase 33's.*

#### Step 3 — **Run, 2026-10-02**

One regeneration shared with Phase 36: `convert --force` for the activespaces, ems, streaming and tra batches, `reframe --all --force`, `sync` of those four families to `C:/tmp/p35-aem`, `validate`. Every command exit 0.

| check | result |
|---|---|
| Version-level `301.yml` in the published tree | **27**: EMS 6, ActiveSpaces 6, Streaming 6, Spotfire Data Streams 2, Administrator 3, Runtime Agent 4 (plus 6 doc-class-level published maps). Administrator 5.13.0 and Runtime Agent 5.13.0 now ship one |
| Planned 30 vs 27 | The plan double-counted: 6+6+6+2+1+3+4 is 28, not 30. Of those 28, Data Science Author 1.4.0 is in no convert batch (`convert_batch` blank, family `statistica`); it was measured in step 1 from a one-off conversion but is not part of the published catalog. 27 is every batch version with a sitemap list |
| Derived rows not on the sitemap | 1 row, withheld (Streaming 11.1.3, `ORIGIN_URL_UNLISTED`); every written derived `from` is listed |
| `ORIGIN_SITEMAP_MISSING` | 9: Designer Add-in ×8, Silver Fabric 1.2.0 — the excluded products, no file written |
| Live spot-check, newly covered layouts | **6 of 6 return 200**: Spotfire Data Streams 11.1.1, Streaming 11.1.0 and 11.2.1, Administrator 5.12.2, Runtime Agent 5.12.3 (`designerhelp`) and 5.12.4 (`trahelp`) |
| `validate` | 208 folders, 0 errors, 661 warnings (537 `ANCHOR_MISSING`, 124 `REDIRECT_SHADOWED`, both pre-existing); **0 findings from any `301.yml`** |
| `versions.csv` | 27 rows, `_out_files` +1 each (the map). The 13 reframed versions also show `_reframed_md_files` −1 and `_reframed_files` −1: Phase 36's legal-label fix, not this phase. In each, the third-party topic the old test lifted out as its own top-level page is back in its chapter and merged as a section (confirmed in all 13 by the Phase 36 session, Runtime Agent 5.13.0 included). None of the 661 warnings is in a `toc.yml` |

---
