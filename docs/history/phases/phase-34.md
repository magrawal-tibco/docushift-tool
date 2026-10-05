> Archived from `docs/planning.md` on 2026-10-05. Status: **Complete, 2026-10-05**. Kept verbatim.
> Index of every phase: [`docs/planning.md`](../../planning.md#finished-phases).

### Phase 34: A Modular Review of the Whole Tool — **Complete, 2026-10-05**

**Progress.** Base tagged `review-base` (7dda975); the frozen copy is the worktree `C:\github\docushift-tool-review`. Findings land in `reports/review/`, indexed in `reports/review/INDEX.md`. **Batch 1 (R1–R3) reviewed**: 52 findings (5 S1, 10 S2, 31 S3, 6 S4), grouped into 15 fix themes; **triage approved as proposed**. Themes A–L are **fixed and merged** (13 commits, 1,815 tests); the EMS re-merge that applies J awaits the user. J applied by `reframe --all --renormalize` (66 EMS pages renamed). **Batch 2 (R4–R6) reviewed**: 49 findings (10 S1, 9 S2, 24 S3, 6 S4) in 12 themes; **triage approved as proposed**. Themes P–Y are **fixed and merged** (14 commits, 1,872 tests); the re-convert that applies them awaits the user. **Batch 3 (R7–R9) reviewed**: 43 findings (13 S1, 3 S2, 22 S3, 5 S4) in 11 themes; **triage approved as proposed**. Themes AA–AH and AJ are **fixed and merged** (13 commits, 1,932 tests); the combined re-convert for batches 2–3 awaits the user. **Batch 4 (R10–R12) reviewed**: 49 findings (4 S1, 6 S2, 31 S3, 8 S4) in 7 themes; **triage approved as proposed**. Themes BA–BE are **fixed and merged** (17 commits, 2,016 tests). **X1–X3 reviewed**: 43 findings (5 S1, 8 S2, 24 S3, 6 S4) in 10 themes; **triage approved as proposed**. Themes XA–XI are **fixed and merged** (12 commits, 2,130 tests). Cleanup merged (−242 lines, byte-identical output, 2,120 tests). Next: the final re-convert, then close-out.

The tool grew phase by phase, from Phase 1 to Phase 33, and each phase was
reviewed as a change. Nobody has read the whole thing end to end since. That is
about 29,000 lines in 80 modules. Done in one pass, that review would be shallow
everywhere. So it is split into **twelve component units**, each one sized to be
read fully in one sitting (about 1,500–3,300 lines), and **three cross-cutting
passes** that catch what a single-component review cannot see: mistakes in the
hand-off *between* stages.

Each unit follows the pipeline's own stage boundaries (§1 of `architecture.md`).
Its findings can then be read and fixed without loading the rest of the tool.

#### Decisions

| decision | what it means | why not the obvious alternative |
|---|---|---|
| **Component units, ordered by data flow** | Shared foundations first, then the stages in pipeline order (catalog → acquisition → engines → transforms → reframe → layout → validation), and the command layer last | Reviewing by stage alone puts all four HTML engines (~5,500 lines) into one unit, which is too big to read properly. Reviewing by file alone loses the stage context that says what "correct" means |
| **Find first, fix second** | A unit's review produces a findings file and **no code changes**. The user triages it (fix / defer / not a bug), and only then are the agreed fixes made, one commit per unit, each with a test | Fixing during the review mixes what was found with what was changed. It also skips the point where the user can say "that is intended" |
| **Wrong-but-silent output ranks highest** | Severity: **S1** wrong output with no warning, or data loss · **S2** wrong output that *is* reported, or a crash on real input · **S3** fragile but correct today · **S4** cleanup / simplification | This project's worst failures were all silent, e.g. a guessed URL that 404s while a success line prints beside it. A crash gets noticed, a quietly wrong page does not |
| **Output claims are measured, not argued** | A finding that says "this produces wrong output" is confirmed against real output in `families/`, `reframed/`, or the html-to-md cache before it is S1/S2. If it can't be confirmed, it is marked *unconfirmed* | Reading the code alone overstates bugs on paths the corpus never reaches and misses bugs on paths it reaches all the time |
| **Review a frozen commit, in its own worktree** | Phase 33 lands (or is parked) first. The review then runs against one tagged commit in a separate git worktree, so a second session can keep building while the review reads | Reviewing a moving tree means findings point at lines that have already changed |
| **Docs drift is a finding** | Each unit checks its `architecture.md` section against the code. Where they disagree, that is an S3 finding, whichever side is right | The docs are the plan of record. If they are wrong, the next phase is planned on a false picture |

#### The twelve component units

| # | unit | modules | ~lines | tests | architecture.md |
|---|---|---|---|---|---|
| R1 | **Foundations**: shared helpers, data model, config loading | `utils/*`, `models.py`, `config.py`, `origins.py` | 2,250 | `test_slug`, `test_naming`, `test_longpath`, `test_swap`, `test_csvio`, `test_config`, `test_origins` | §3.6, §4.4 |
| R2 | **Catalog & discovery**: docsite API, merge, scope, EOS, families | `catalog.py`, `discovery/*`, `apiref.py` | 2,850 | `test_catalog`, `test_discovery`, `test_sitemap`, `test_apirefs` | §2, §3.1–3.12 |
| R3 | **State & acquisition**: state ledger, download, unzip, inventory | `state.py`, `downloader/*`, `extractor/*` | 2,250 | `test_state`, `test_downloader`, `test_extractor`, `test_content_root`, `test_inventory` | §3.8–3.9, §4.3–4.5 |
| R4 | **Engine framework & converter driver**: detection, roots, CSH, navigation | `engines/base,detector,roots,csh,__init__`, `converter/*` | 2,700 | `test_roots`, `test_converter`, `test_navigation` | §3.4, §5.4 |
| R5 | **Flare engine** | `engines/flare.py`, `flare_toc.py` | 1,500 | `test_flare` | §5.1 |
| R6 | **DITA and DocBook engines** | `engines/dita.py`, `docbook.py` | 2,100 | `test_dita`, `test_docbook` | §5.2, §5.6 |
| R7 | **WebWorks engine** | `engines/webworks.py`, `webworks_toc.py` | 2,000 | `test_webworks` | §5.3 |
| R8 | **Transforms**: HTML → Markdown, tables, links, fragments, assets | `transforms/*` | 2,250 | `test_transforms` | §5 (core transforms) |
| R9 | **Reframe**: page merging, renames, packing, TOC | `reframe/*` | 3,300 | `test_reframe` | Phases 20, 28–30 |
| R10 | **Publishing layout**: distributor, router, redirects, versions | `sync/*` | 2,350 | `test_distributor`, `test_router`, `test_documents`, `test_archives`, `test_sync_versions` | §6 |
| R11 | **Validation & reporting**: checks, findings register, status views | `validation/*`, `reporting/*` | 2,850 | `test_validation`, `test_findings`, `test_reporting_views` | §7, findings register |
| R12 | **Command layer**: every CLI command's wiring, options, exit codes | `cli.py` | 2,950 | `test_cli`, `test_scaffolding`, `integration/test_pipeline_smoke` | `user-guide.md` |

#### What every unit checks, in this order

1. **Correctness**: does the code do what its `architecture.md` section says, on the inputs the corpus actually has?
2. **Silent failure**: every `except`, every default, every skipped row. Is it counted, reported, or swallowed?
3. **The unit's edges**: what it reads from the stage before it and what it promises the stage after. Mismatches are noted here, and settled in X1.
4. **Tests**: which behaviours the unit's tests pin and which they don't. A gap counts as a finding only where the untested path is reached by real data.
5. **Docs drift**: architecture/user-guide statements the code contradicts.
6. **Simplification**: dead code, duplicated helpers, needless indirection (S4 only, never mixed into a correctness fix).

#### The three cross-cutting passes (after R1–R12)

| # | pass | what it looks for |
|---|---|---|
| X1 | **Stage contracts** | Every hand-off: `products.csv`/`versions.csv` columns, the `families/` and `reframed/` path contract, `state.db` statuses, `output_map`/manifests. Does every writer and reader agree on name, type, and meaning? It is built from the edge notes the units collected in step 3 |
| X2 | **Filesystem & Windows safety** | Zip-slip, atomic writes, the 260-character ceiling, case-insensitive name collisions, CRLF/encoding on CSV round-trips, cleanup that deletes something it should keep (cf. Phase 16) |
| X3 | **Re-run consistency** | Re-running a stage on unchanged input gives byte-identical output; a partial run followed by a resume gives the same result as one clean run |

#### Output

- One findings file per unit: `reports/review/R01-foundations.md` … `X3-rerun.md`. Each finding has severity, location, the failing scenario, and whether it was confirmed against output.
- One index, `reports/review/INDEX.md`: counts by unit and severity, plus the user's triage decision per finding.
- A plain-language summary to the user after each unit: what was found, what needs a decision.

#### Steps

1. **Freeze.** Land or park Phase 33, tag the commit (`review-base`), create the review worktree.
2. **R1 → R12 in order**, one unit at a time. Each unit is reported and triaged before the next one starts, or in batches of three if fewer interruptions are preferred.
3. **X1 → X3**, built on the units' edge notes.
4. **Fix**, unit by unit, in triage order. One commit per unit, each fix with a test that fails before it, a full test-suite run per commit, and a re-run of an affected family where output changes.

*Exit: every unit and pass has a findings file; every finding has a triage decision; every "fix" is merged with a test; S1/S2 findings marked "defer" are recorded in `open-issues.md`; the test suite and lint are clean on the final commit.*

#### Outcome — **2026-10-05**

236 findings across twelve component units and three cross-cutting passes: 37 S1, 36 S2,
132 S3, 31 S4. Every S1 and S2 is fixed with a test, alongside 95 S3s; 37 S3s are deferred
to the carried-forward items; the S4 cleanup removed 242 lines with byte-identical output.
Tests 1,687 → 2,120, finding codes 66 → 84. No finding was wrong. The final re-convert
ran without `--force` and the new currency keys rebuilt every tree on their own; a TRA
convert interrupted mid-run left no residue and no stale tree. Every number, decision and
commit is in [`reports/review/INDEX.md`](../../../reports/review/INDEX.md), with each unit's
findings file beside it.
