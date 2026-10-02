> Archived from `docs/planning.md` on 2026-10-02. Status: **Complete, 2026-09-19**. Kept verbatim; a heading that says *Planned* was built later in this same section.
> Index of every phase: [`docs/planning.md`](../../planning.md#finished-phases).

### Phase 13: The Output Tree Is Counted Too

Five columns describe the package going **in** — `_has_csh`, `_csh_names`, `_has_api_ref`, `_api_files`, `_doc_files`, all written by Stage 4's one walk. Nothing describes what came **out**. `convert` counts topics, generated pages and assets while it runs and prints them (`cli.py:1253`), and those numbers die with the process: `report` reads findings, `status` reads `version_state`, and neither can answer "how big is the Markdown for this version" for a run that finished last week. The catalog is where a per-version number lives, and on the output side it holds none.

#### Why the API count is not repeated

Because it is the same number at both ends, and storing it twice would be storing it twice. The converter **skips** API-reference trees (`flare.py:562`, on `apiref.is_api_reference`), so no API file is ever written into `output/`; Stage 7 copies those trees **verbatim** out of the *extracted* tree into `{resources-tree}/…/api-references/…` (§10.6). A Javadoc tree that arrives as 1,466 files is published as 1,466 files, and `_api_files` already says so.

So the before/after pair to read across a row is **`_doc_files` → `_out_files`**, and `_api_files` sits outside both ends of it, unchanged by construction.

#### Two columns, measured rather than derived

| Column | Meaning |
|---|---|
| `_md_files` | Markdown files in the version's output tree — converted topics **and** the pages Stage 6a generated |
| `_out_files` | **Every** file in that tree: the Markdown, the assets that were copied, and the `toc.yml` / `metadata.yml` / `csh.yml` artifacts |

Assets get no column of their own: they are `_out_files - _md_files` minus the artifacts, and the subtraction carries no nuance the way `_has_csh` against `_csh_names` does.

**Both come from one walk of the output tree, not from the run's counters** — and that is not ceremony. The obvious derivation, `documents + generated + assets + 3`, is already wrong by one on **every** version on disk today: `csh.yml` is written only when the map is non-empty (`transforms/csh.py:275`), and all six converted versions have `_csh_names=0`, so all six have **two** root artifacts, not three. A constant that is already false on 6 of 6 is not a constant.

#### What the corpus says, walked by hand on 2026-09-19

| version | `_doc_files` (in) | `_out_files` | `_md_files` | assets | out/in |
|---|---|---|---|---|---|
| `gridserver-logviewer` 1.0.0 | 345 | 46 | 27 | 17 | 13% |
| `gridserver-manager` 7.1.1 | 1,458 | 981 | 930 | 49 | 67% |
| `gridserver-manager` 7.2.0 | 1,552 | 1,050 | 1,000 | 48 | 68% |
| `hpc-cloud-adapter` 2.0.0 | 290 | 25 | 20 | 3 | 9% |
| `hpc-cloud-adapter` 2.1.0 | 313 | 29 | 24 | 3 | 9% |
| `hpc-cloud-adapter` 2.2.0 | 314 | 31 | 25 | 4 | 10% |
| **total** | **4,272** | **2,162** | **2,026** | **124** | **51%** |

Two things fall out that no existing column can show. **The output is 94% Markdown** — 124 asset files out of 2,162 — because a Flare package's file count is dominated by skin chrome and orphan images, neither of which is copied (§6.4 step 7: 54.6% of Flare's images are orphans). And **the ratio is not stable**: two products of the same generator land at 67% and 9%. A 9% survival rate is either correct or a conversion that quietly lost a guide, and today nothing in the catalog lets anyone ask which.

All six carry `_api_files=0`, so the "API files are unchanged" claim above is not demonstrated by this slice — it rests on the converter's skip and Stage 7's verbatim copy, which is where it should rest.

#### The invariant it buys

`_md_files` must equal `documents + generated`. When it does not, two writes landed on one path — which is not hypothetical: Phase 7b found `navigation._free` comparing a generated container page's path case-sensitively, so on Windows the page was written **over** a converted topic and three versions shipped with content silently replaced. That defect is arithmetic once the tree is counted. A new `warn` code, `OUTPUT_COUNT_MISMATCH`, carries the difference (register **40 → 41**); it is separable if the register is to stay put, but the check is the cheapest part of the phase and it catches the one failure mode that has already shipped once.

#### What changes

| File | Change |
|---|---|
| `models.py` | `ProductVersion.md_files`, `.out_files`, both `int \| None` — blank and `0` are different answers, as on the extract side |
| `catalog.py` | `VERSION_COLUMNS` gains `_md_files`, `_out_files` after `_doc_files`; `_INVENTORY_COLUMNS` splits into an extract tuple and a convert tuple; `parse_optional_int` / `format_optional_int` round-trips; `record_convert_inventory(slug, version, md_files, out_files)` and `clear_convert_inventory` |
| `converter/driver.py` | `_measure_output(path)` — one walk, two counts — called **after the swap** in `_build`, and on the `CURRENT` fast path when the columns are blank; `ConvertResult.md_files` / `.out_files` |
| `cli.py` (`convert`) | the per-version line and the run summary report files on disk beside topics and assets |
| `reporting/findings.py` | `OUTPUT_COUNT_MISMATCH`, warn, Stage.CONVERT |
| `architecture.md` §3.9, `design.md` §6.4, `user-guide.md` §2 | the two columns, who writes them, and the `_doc_files` → `_out_files` reading |

Nothing is needed in `version_snapshot`: discovery has no value for these, and the snapshot carries only fields discovery owns, so the merge exclusion is structural rather than a rule (`catalog.py:129`).

#### The `CURRENT` fast path is not optional here

Phase 12 exists because a column shipped that a no-op left blank forever. `convert_one`'s unchanged-input fast path (`driver.py:205`) returns `CURRENT` without building anything, and a version converted before this phase would report `CURRENT` on every future run and never be counted. So the same rule 4b-1 wrote into `extract_one` applies: **`CURRENT` with blank output columns walks the target tree anyway.** It is a directory walk against a conversion, which is free.

This is also why `convert` gets no `--measure-only` twin. `extract` needed one because its fast path was gated behind a ZIP that no longer exists; `convert`'s is gated on a checksum and the output tree itself, both of which are on disk.

#### What it deliberately does not do

- **It does not count the published tree.** `_out_files` describes `output/<family>/<slug>/<version>/`, which is Stage 5's. What Stage 7 placed into a target workspace is `validate`'s question, answered against the target with no `versions.csv` agreement required (§7b), and a catalog column claiming to know it would be claiming to know another machine's disk.
- **It does not count what was skipped.** Topics dropped as `runtime-stub` or `empty`, orphan assets, dangling references — all already findings with codes, and folding them into a footprint column would make a healthy version and a broken one read the same.
- **It does not write on a failure.** `NO_TREE`, `ENGINE_UNKNOWN` and `FAILED` leave both columns exactly as they were, on §6.3's blank-not-zero rule: a version that did not convert is not a version that converted to nothing.
- **It does not add a boolean.** `_has_api_ref` is the one derivable column in the set and it is justified as a filtering convenience; `_out_files > 0` needs no second spelling.
- **It does not special-case `--input`/`--output`.** A conversion through overridden paths already writes `output_map` and `version_state` unconditionally (`driver.py:301`), and branching the catalog write on provenance would make the columns mean two things.

#### Tests

Round-trip: blank survives as blank in both directions, a measured `0` survives as `0`, an Excel `1,050` parses. A `FAILED` convert leaves both blank; a clean one with no assets writes `_md_files == _out_files - 2`. A version whose `csh.yml` **is** written lands on `- 3`, pinning the artifact count as measured rather than assumed. `CURRENT` over a blank row walks and fills; `CURRENT` over a filled row does not walk. `_md_files != documents + generated` emits `OUTPUT_COUNT_MISMATCH`, and the collision that produces it — two documents resolving to one path — is constructed rather than mocked. `clear_convert_inventory` blanks both and leaves the five extract columns alone.

One test here is not about output files at all. Registering the 41st code turned up three earlier ones — `CODE_LINK_FLATTENED`, `INDEX_UNLINKED`, `WHATS_NEW_PLACEHOLDER` — that were in `findings.py` and missing from §7.5, because the only test guarding that table compared the register's size to a literal and could not see the document. `test_the_published_table_carries_every_registered_code` reads this file and asserts every registered code appears as a row in it.

##### Acceptance

`convert --product tibco-datasynapse-gridserver-manager --force` and read the row back: `_md_files=930` and `_out_files=981` on `7.1.1`, `1000` / `1050` on `7.2.0`, matching the hand walk above. Re-run without `--force`: no re-conversion, no change to the columns. Then blank the two columns on one row by hand and re-run — the `CURRENT` path fills them without rewriting the tree, and the output tree is byte-identical before and after. Convert all six and check the totals against the table: **2,026 Markdown files, 2,162 files**, and `OUTPUT_COUNT_MISMATCH` emitted **0** times. Finally the full suite and `ruff`.

**Verified, 2026-09-19.** All six converted and every row read back matches the hand walk to the file: 930/981 and 1000/1050 on the two `manager` versions, 27/46 on `logviewer`, 20/25, 24/29 and 25/31 on the three `hpc` versions — **4,272 in, 2,162 out, 2,026 Markdown, 124 assets**. `findings` holds **0** `OUTPUT_COUNT_MISMATCH` rows, ever. **1,270 tests pass**, `ruff` clean.

One clause of the acceptance could not be run, for the reason Phase 12 found: none of these six carries an `extract_zip_checksum`, so `convert_one`'s `checksum` is empty and the `CURRENT` branch is unreachable for them — a second run reconverts rather than reporting `Already current`. The backfill on that branch is covered by two unit tests instead (walks a blank row and fills it, leaving the tree byte-identical; does not walk a filled one), and it will be exercised on the corpus the first time a version is converted from a package that is actually on disk.

---
