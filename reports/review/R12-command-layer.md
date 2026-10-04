# R12 — Command layer: findings

Base: review-base-b4 (73cc93d) · Reviewed: cli.py · Date: 2026-10-04

| S1 | S2 | S3 | S4 |
|---|---|---|---|
| 0 | 5 | 11 | 2 |

Repros: CliRunner scripts in `C:\tmp\review-R12\` (`harness.py`, `t1.py`–`t12.py`), each on a scratch root under `C:\tmp\review-R12\roots\`. The main workspace was never invoked; its `state.db` was read once, read-only, for the run counts in R12-04 and R12-06. The unit's tests pass: 146 passed, 1 skipped.

## Findings

### R12-01 · S2 · `archive download --from-file` for an uncatalogued version puts it into the conversion pipeline
- **Where:** src/docushift/cli.py:2868 (calls `_ingest_target`), cli.py:1107-1116; catalog.py:1077 (`ProductVersion(slug, version)`), models.py:197-198 (`is_archived=False`, `convert_eligible=True`)
- **What:** The archive command shares `download --from-file`'s row-adding helper. The row it adds takes the model defaults (active, convert-eligible, `zip_source=auto`), so a reference ZIP for an old release becomes pipeline work.
- **Failing scenario:** `archive download --product ems --version 5.0.0 --from-file old.zip` (5.0.0 not in the catalog). After that, `download --all --dry-run` lists `5.0.0` with a templated URL to fetch, and `archive list` does **not** show it (it is not `is_archived`). The only warning printed is "adding the row". The user guide (§2, "Working with an archived version") promises "to just look at one, without putting it into the pipeline".
- **Confirmed:** yes. CliRunner `t6.py`. INDEX.md's "known gap" (the row blocks a later fetch) has the same root; this is a second, worse consequence of it.
- **Suggested fix:** Have `archive download` add the row with `is_archived=True, convert_eligible=False` (or refuse an unknown version). The fix for the known gap should cover both.

### R12-02 · S2 · `download --from-file` ignores `--dry-run`: copies the ZIP, adds a row, pins `zip_source=manual`
- **Where:** src/docushift/cli.py:1193-1205 (the `from_file` branch returns before the `dry_run` check at :1211)
- **What:** `--dry-run` is accepted with `--from-file` and silently does the real ingest.
- **Failing scenario:** `download --product ems --version 11.0.0 --from-file pkg.zip --dry-run` writes `families/…/downloads/…-11.0.0.zip`, adds `11.0.0` to `versions.csv`, and pins it manual. A pinned row is exempt from later downloads (user guide: "`zip_source=manual` means never fetch this"). `--all/--bu/--batch/--force/--workers` are also ignored without a word on this path.
- **Confirmed:** yes. CliRunner `t1.py`: file present, row present, exit 0.
- **Suggested fix:** On the `from_file` path, refuse `--dry-run`, or print what would be filed and stop. Reject the scope flags that have no meaning there.

### R12-03 · S2 · A `CatalogError` escapes as a Python traceback from six commands
- **Where:** cli.py:760 (`catalog enable`), :906 (`catalog import`'s `manager.save()`), :914 (`catalog batches`), :1022 (`catalog triage`), :2546-2548 (`status`), :2818 (`archive list`), :947 (`catalog sitemap`'s `manager.load()`)
- **What:** `save()` raises `CatalogError` for a CSV open in Excel (R1-04/R2-05's fix), and `load()` raises it for a version row whose slug has no product row. These call sites do not wrap it, while `catalog set`, `list`, `show` and the stages do.
- **Failing scenario:** With `versions.csv` open in Excel (simulated read-only), `catalog enable --product ems --version 8.6.0` and `catalog import` end in an uncaught `CatalogError`. With one mistyped slug in `versions.csv`, `catalog batches`, `catalog triage`, `status` and `archive list` all end in a traceback, while `catalog list`, `download` and `catalog show` print the clean `Error:` line. An Excel-locked CSV is the case the user guide documents.
- **Confirmed:** yes. CliRunner `t2.py` (locked CSV) and `t8.py` (broken join), `exc=CatalogError`.
- **Suggested fix:** Catch `CatalogError` once, in a `click.Group` subclass's `invoke` on `main`, and re-raise it as `ClickException`, rather than per call site.

### R12-04 · S2 · Every `download` run is recorded as "did not finish"
- **Where:** cli.py:1233 (run started), :1240 and :1251 (`flush()` only; `finish()` is never called)
- **What:** `download` never calls `findings.finish()`, so `runs.finished_at` and `exit_code` stay NULL on every run, successful or not.
- **Failing scenario:** After a clean `download --product ems`, `report --run last` prints `run 1: download, … (did not finish)`, and `report --runs` shows `Finished -`, `Exit` blank. That is the display used for a crashed run. In the real `cache/state.db`, 6 of 6 `download` runs are unfinished; every other command's runs are finished (except 1 of 101 sync runs).
- **Confirmed:** yes. CliRunner `t1.py`, plus a read-only query of the main `state.db`.
- **Suggested fix:** Wrap the download in `try/finally: findings.finish(exit_code=…)`, as `extract` does.

### R12-05 · S2 · `catalog sitemap` crashes with a traceback when its report CSV is open in Excel
- **Where:** cli.py:993-998 (bare `open(report, "w")`)
- **What:** The report write is unguarded. It runs after the whole fetch, so a locked file is a `PermissionError` traceback at the very end, and no report is written.
- **Failing scenario:** Open `reports/coveo-sitemap.csv` in Excel (the file exists for that), then run `catalog sitemap`. Uncaught `PermissionError(13)`. The cached XML survives, so a re-run is cheap, but the run ends in a crash, not a message.
- **Confirmed:** yes. CliRunner `t7.py`, with the network fetch stubbed and the report read-only.
- **Suggested fix:** Catch `OSError` around the write and raise `ClickException("Could not write … (open in Excel?)")`, as `report --export` does at :2784-2788.

### R12-06 · S3 · Failed rows: `download`, `extract` and `convert` exit 0, while `reframe` and `sync` exit 1
- **Where:** cli.py:1250-1252, :1467-1473, :1612 (no gate, run recorded `exit_code=0`) vs :1797-1803 and :1994-1998 (gate on failed rows or error findings)
- **What:** The same kind of fact (a version failed) gives exit 0 from three stages and exit 1 from two. A chained script (`extract --batch b && convert --batch b && reframe …`) carries on past extract and convert failures.
- **Failing scenario:** A corrupt ZIP: `extract` reports `Failed 1` and exits 0. A Flare tree with nothing convertible: `convert` reports `Failed 1` and exits 0, and the run row says exit 0. In the real `state.db`, 50 of 50 convert runs and 13 of 13 extract runs say exit 0, while 11 of 99 reframe runs and 29 of 101 sync runs say exit 1.
- **Confirmed:** yes. CliRunner `t3.py`. The `convert` behaviour is deliberate (comment at :1790-1793), so this is S3: the rule is inconsistent and undocumented, not broken.
- **Suggested fix:** Decide one rule for failed *rows* (as distinct from error *findings*) across all five stages. If convert stays at 0, document the per-command table (see R12-14).

### R12-07 · S3 · `catalog set --bu` accepts any value, and an unknown bu turns off the `--family` typo guard
- **Where:** cli.py:842, :868-870; catalog.py:1000-1001 (no check), catalog.py:991-992 (family check skipped when the bu declares no families)
- **What:** `--family` is checked against `taxonomy.yaml` precisely because a typo "would auto-register a workspace folder and, downstream, a publishing repository" (catalog.py:977-984). `--bu` has no check, and the bu is applied first.
- **Failing scenario:** With the real `taxonomy.yaml`, `catalog set --product ems --family nosuchfam` is refused, but `catalog set --product ems --bu tibcoo --family nosuchfam` exits 0. The workspace silently becomes `families/en-us-tibcoo-nosuchfam`, and the existing downloads and trees are orphaned in the old folder. Only a later `catalog import` warns.
- **Confirmed:** yes. CliRunner `t5.py`.
- **Suggested fix:** Validate `--bu` against `taxonomy.yaml`'s `business_units` (refuse, as `--family` does).

### R12-08 · S3 · `catalog set` writes the product fields, then fails on the version, and exits 1
- **Where:** cli.py:867-873; catalog.py:1016 and :1054 (`save()` after every field)
- **What:** Each field is saved on its own, so a mixed product-and-version edit that fails on the version leaves the product edit written behind an `Error:` line.
- **Failing scenario:** `catalog set --product ems --display-name CHANGED --version 9.9.9 --batch poc` prints `Error: No version '9.9.9'`, exits 1, and `products.csv` now holds `CHANGED`.
- **Confirmed:** yes. CliRunner `t2.py`.
- **Suggested fix:** Check that the version exists (and validate every value) before the first write, then save once.

### R12-09 · S3 · Runs left open on error paths: `catalog eos`, `catalog migrate`, `convert`
- **Where:** cli.py:544-548 and :643-647 (run started before `apply_eos`/`apply_migrate_decisions`, which raise → `ClickException`, never finished); :1610-1612 (`convert`'s `finish()` is not in a `finally`, unlike `extract` at :1467-1472)
- **What:** An error raised after `start()` leaves a `runs` row with no finish time and no exit code. It then becomes `report --run last`, labelled "(did not finish)".
- **Failing scenario:** `eos.yaml` names a missing report: `catalog eos` prints the clean error, exits 1, and leaves run 1 open. `catalog migrate` with a missing sheet leaves run 2 open.
- **Confirmed:** yes for eos and migrate (CliRunner `t7.py`). Unconfirmed for convert: it needs an exception escaping `convert_many`, which R4-08 now contains per version.
- **Suggested fix:** Start the run after the apply step, or use `try/finally` with `finish(exit_code=1)` on the error path.

### R12-10 · S3 · `catalog fetch --dry-run` tells the user to run `report --run 0`
- **Where:** cli.py:270 (`store=None` on a dry run, so `run_id=0`), :327 → :691-696
- **What:** `_report_findings` prints "Recorded N … `docushift report --run N`" whenever there are findings, even when nothing was recorded.
- **Failing scenario:** `catalog fetch --product ems --dry-run` with one batch-not-eligible row prints `Recorded 1 warning -- docushift report --run 0.`. The `runs` table is empty, and `report --run 0` answers `Error: No run 0 in state.db`.
- **Confirmed:** yes. CliRunner `t9.py`, with the crawler stubbed.
- **Suggested fix:** In `_report_findings`, print "Would record …" (no run id) when `findings.run_id` is 0.

### R12-11 · S3 · `report` filters match exactly and are never checked, so a near-miss reads as a clean run
- **Where:** cli.py:2739-2741, state.py:777-782 (`column = ?`); compare `--explain`, which upper-cases and checks the register (cli.py:2699-2706)
- **What:** `--code` is not upper-cased or checked against `REGISTRY`, `--stage` is not a `Choice`, and `--slug` is not resolved from a product code. A miss prints the green "Nothing to report for this selection".
- **Failing scenario:** On a convert run that holds one `OUTPUT_ROOT_MISSING` row, `--code output_root_missing`, `--stage Convert` and `--slug ems` each print "no findings. Nothing to report". The user guide's own example is `report --code TOPIC_LINK_DANGLING --slug ems` (user-guide.md:1282), and findings are keyed on `tibco-enterprise-message-service`.
- **Confirmed:** yes. CliRunner `t4.py`.
- **Suggested fix:** Normalise `--code` and refuse a code that is not registered, make `--stage` a `click.Choice` over `Stage`, and say "slug X matches no finding in this run" rather than "nothing to report". `report` deliberately does not read the catalog, so `--slug` stays exact; fix the docs example instead.

### R12-12 · S3 · `catalog sitemap --product X` replaces the whole-catalog report with one product's rows, and a typo empties it
- **Where:** cli.py:949-951, :993-998
- **What:** The report is rewritten from only the selected slugs. An unknown `--product` resolves to itself, matches no catalog row, exits 0, and leaves a header-only CSV.
- **Failing scenario:** After a full `catalog sitemap`, `catalog sitemap --product tibco-ems` (not a slug) exits 0 and `reports/coveo-sitemap.csv` goes from 501 lines to 1.
- **Confirmed:** yes. CliRunner `t12.py`, with the fetch stubbed.
- **Suggested fix:** Refuse an unknown `--product` (as `catalog show` does). Merge the selected product's rows into the existing report, or write a per-product file.

### R12-13 · S3 · `report --prune --keep -1` crashes with a traceback
- **Where:** cli.py:2665, :2710; state.py:802-803
- **What:** `--keep` is a plain `int`. A negative value raises `ValueError` from the store, uncaught.
- **Failing scenario:** `report --prune --keep -1` ends in an uncaught `ValueError('--keep cannot be negative')`.
- **Confirmed:** yes. CliRunner `t10.py`.
- **Suggested fix:** `type=click.IntRange(min=0)`.

### R12-14 · S3 · Docs drift: "only `validate` gates" is false
- **Where:** user-guide.md:1296 ("`validate` exits 1; nothing else gates"), :1322-1328 ("Only `validate` gates on what it found"), :1368-1370 ("the only command in the tool that gates"); the cli.py:2021-2023 docstring says the same
- **What:** `sync` (since Phase 15e), `reframe` and `csh validate` all exit 1 on error findings, and `sync` and `reframe` also exit 1 on failed rows (cli.py:1797-1803, :1994-1998, :2497-2511).
- **Failing scenario:** A script author who reads the exit-code section treats a `sync` exit 1 as an unexpected crash. Conversely, a reader expecting all stages to behave alike is misled about `convert` (R12-06).
- **Confirmed:** yes, by code read and CliRunner (`t3.py` shows the reframe and convert behaviour).
- **Suggested fix:** Replace the sentence with a per-command exit-code table (the one below).

### R12-15 · S3 · Docs drift: documented examples that fail as written
- **Where:** user-guide.md:672-675 (`convert --input … --output …` without `--product/--version`, which is required: cli.py:1560-1561); :889, :1169-1170, :1341-1342 (`--product tibco-ems`: neither a slug nor a product code in `config/products.csv`); :132, :447 (`dsp_gridserver`: the code is `dsp-gridserver`); :1561, :1569, :1585 (`csh … --product businessworks`: `csh` and `validate` take only the published folder slug, and no product's slug is `businessworks`); :1282 (`report --slug ems`, see R12-11)
- **What:** Copy-pasted, each of these exits 1 or prints an empty result.
- **Failing scenario:** `convert --input in --output out` prints `Error: --input needs --product and --version` (CliRunner `t2.py`). `reframe --product tibco-ems` hits the empty-selection exit 1.
- **Confirmed:** yes. CliRunner for the `--input` example; slugs checked against the real `config/products.csv`.
- **Suggested fix:** Correct the examples to real slugs, and add `--product/--version` to the `--input` example. State plainly that `validate` and `csh` take the published slug, not a product code, unlike every catalog-backed command.

### R12-16 · S3 · Docs drift: stale status block, and options that are missing or only half-documented
- **Where:** user-guide.md:40 ("Everything downstream of `convert` is not built at all. Every unbuilt command exits non-zero…"); cli.py:10-13 module docstring ("`convert` onward wait on Phases 5-7"); user-guide.md:589-592 (the extract flag table has no `--measure-only` row); the global `--root` appears nowhere in user-guide.md or quickstart.md; `catalog list --eligible-only` is undocumented, yet the tool's own empty-selection message sends users to it (cli.py:68); user-guide.md:525 lists the shared selectors for `download, extract, convert, and sync` (omits `reframe`); quickstart.md:259 says "run the same seven commands with `--batch poc-1`", but only five take `--batch` (`validate` takes none)
- **What:** The reference does not describe the CLI that exists.
- **Failing scenario:** A reader takes reframe, sync, validate, status and report to be unbuilt, or cannot find how to point the tool at another project root.
- **Confirmed:** yes, by `--help` and code read.
- **Suggested fix:** Delete the implementation-status block and the stale docstring, add the missing flag rows and `--root`, and fix the selector sentence and the quickstart count.

### R12-17 · S4 · Dead `_pending` helper and its empty test harness
- **Where:** cli.py:46-51 (no caller); tests/unit/test_cli.py:24-30, :129 (`PENDING_COMMANDS = []`, kept "because Phase 7c's `csh` group will use it", but `csh` shipped without it)
- **What:** Scaffolding for unbuilt commands, now that every declared command is built.
- **Failing scenario:** n/a
- **Confirmed:** n/a
- **Suggested fix:** Remove both in the end-of-Phase-34 cleanup commit.

### R12-18 · S4 · Duplicated wiring across commands
- **Where:** the `--input/--output` checks and the single-row `--input` execution, copied between `convert` (cli.py:1558-1561, :1600-1608) and `reframe` (:1734-1737, :1778-1786); `validate` re-declares `--target-dir/--product/--version/--doc-class` (:2002-2005) instead of using `_target_options` (:2227); `archive list` re-declares `--bu/--family/--product` (:2809-2811); two styles of findings footer (`_report_findings` "Recorded … `report --run N`" in catalog/download/extract, inline "Findings: …" in convert/reframe/sync/validate)
- **What:** The same rules are spelled out in several places, so a fix in one copy will not reach the others.
- **Failing scenario:** n/a
- **Confirmed:** n/a
- **Suggested fix:** Move the `--input` validation and the single-row run into one helper, use `_target_options` for `validate`, and settle on one footer that always names the run id.

## Exit-code table (command · exits non-zero on a failed row?)

| command | failed row / error finding | empty selection | notes |
|---|---|---|---|
| catalog fetch | **no**: unreachable products → 0 | n/a (scope required; zero products discovered → 1) | merge refusal → 1 |
| catalog eos / migrate / import | n/a | n/a | config error → 1 (run left open, R12-09); import on a locked CSV → traceback (R12-03) |
| catalog enable / set | n/a | unknown version → 1 | enable on a locked CSV → traceback (R12-03); set → partial write (R12-08) |
| download | **no**: Failed → 0 | 1 | run never finished (R12-04) |
| extract | **no**: Failed/Refused → 0 | 1 | |
| convert | **no**: Failed → 0 (deliberate) | 1 | run records exit 0 |
| reframe | **yes**: failed row or error finding → 1 | 1 | |
| sync | **yes**: failed row or error finding → 1 | 1 | |
| validate | **yes**: error finding → 1 | 1 | |
| csh validate | **yes**: error finding → 1 | 1 | |
| csh list / report | n/a | 1 | |
| archive download | **yes**: fetch/extract error → 1 (ClickException) | unknown version → 1 | `--from-file` adds a pipeline row (R12-01) |
| status / catalog list / archive list / catalog triage / batches | n/a | **0** ("no matching rows") | read-only; tracebacks on a broken CSV (R12-03) |
| report | n/a | missing run / bad export → 1 | bad filter → 0 "nothing to report" (R12-11) |

## Edge notes (for X1)
- `ConfigManager.__init__` creates `cache/`, `families/` and `output/` in the cwd for every command, `report --explain` and `validate` included (`t11.py`). Run from the wrong directory, `validate` and `csh validate` record their runs into a fresh `cwd/cache/state.db`, which the project's `report` never sees.
- Stage `--version` matching is exact and dotted only (catalog.py:535). `validate` and `csh` accept `10-4-0` too. `download --version 10-4-0` hits the empty-selection exit 1, which is loud but a different rule.
- `iter_versions` lowercases `--bu/--family` without stripping them (catalog.py:526-528); `catalog fetch` strips (cli.py:213, :217).
- `catalog enable` gives no warning when a closed gate (`in_scope=false`, `release_status=retired`) still keeps the version out of every stage.
- `status` points "`report --run last`" at funnel errors that may belong to an older run.
- A convert version that converts nothing is FAILED but records only a **warning** (`OUTPUT_ROOT_MISSING`, `t3.py`/`t4.py`), so even a findings-based gate would not catch it. For R4/R11.
- `--input` still writes the catalog version's state (already deferred to theme Z).

## Test gaps
- **reframe command**: no CLI test of the run path, the exit-1 gate, `--input/--output`, or `--renormalize` (test_cli covers only the funnel helper).
- **download run path**: no test asserts the run is finished (would have caught R12-04). No test for `--from-file --dry-run` (R12-02).
- **convert**: no CLI test of the `--input` run path, or pinning that a failed row exits 0.
- **CatalogError at the CLI**: no test of a locked CSV through `catalog enable/import`, or a broken join through `status/triage/batches/archive list`.
- **No CLI test at all** for `catalog sitemap`, `catalog migrate` (covered only in test_catalog), `extract --measure-only`, or `report --runs` / `--stage` / `--severity`.
- `test_scaffolding.SUBPACKAGES` omits `docushift.reframe` and `docushift.validation`.

## Docs drift
- R12-14 (the exit-code rule), R12-15 (examples that fail), R12-16 (stale status block, missing options, selector lists).
- The test_cli.py:1509 docstring correctly says `sync` gates; the user guide does not.

## Checked and fine
- `_no_selection` exits 1 for all five stages, `--dry-run` included; `validate` and `csh` exit 1 on an empty published selection.
- `catalog fetch` refuses `--version` and a missing scope, turns `--batch` and `--family` into crawl selectors, and leaves the catalog alone when discovery returns nothing. A fetch `--dry-run` uses `store=None`, and R2-02's purge stays fixed.
- An ambiguous product code is refused everywhere `_resolve` / `_selectors` is used. `catalog list` refuses both disjoint flag pairs. `extract --measure-only --force` is refused. `--input` and `--output` must be given together.
- `catalog set` refuses version fields without `--version` and a call with nothing to set. `--engine`, `--release-status` and `--migrate-decision` take only values from their enums.
- Every outcome table lists every value of its enum, so the counts add up to the selection, and failed rows are named one by one.
- The dry runs of `download`, `extract`, `convert`, `reframe`, `sync` and `validate` write nothing (apart from R12-02) and open no run.
- `validate --check-external` builds its HTTP session only when the flag is set, and `report --explain` refuses an unregistered code.
- The quickstart's nine commands use real options in a valid order. The shipped `config/products.csv` makes `--product ems` resolve on a fresh clone. The chain was not run end to end, because it needs the network.
