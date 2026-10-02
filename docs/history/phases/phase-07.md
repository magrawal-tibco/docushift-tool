> Archived from `docs/planning.md` on 2026-10-02. Status: **Complete, 2026-09-16**. Kept verbatim; a heading that says *Planned* was built later in this same section.
> Index of every phase: [`docs/planning.md`](../../planning.md#finished-phases).

### Phase 7: CLI, Reporting & Verification Dashboard

**Design settled 2026-09-10.** The reframe that drives everything below: **this phase is not a dashboard, it is where a dozen earlier decisions come due.** At least fifteen rules across Stages 1–6 end in "…is a report line", "counted and named", or "reported rather than dropped" — and since `csh.yml` lost its `unresolved` key (Phase 6 contract), the report is now the *only* surviving record that a Help identifier resolved to nothing. Built as a summary screen, every one of those obligations quietly becomes nothing, and `design.md` invariant 10 ("absence is reported, never faked") becomes untrue in a way no test would catch.

**Split into three sub-phases, 2026-09-16**, on the same rule Phases 5 and 6 were split by — what can be *accepted* on its own, not what is the same size. **7a is the read layer and the writers it reveals are missing**: `report`, `status`, and a `FindingsRun` in the three stage commands that record nothing today. **7b is `validate`** — §7.4's link, asset and AEM-artifact integrity, the first command that reads the published tree rather than the database. **7c is the `csh` group and §7.6's cross-version regression.** The order is not arbitrary: 7b and 7c both *write* findings and neither has a reader, so building either first means accepting it by inspecting a SQLite file. 7a also ends with the §7.5 register at three outstanding rows instead of nine, which is what makes "is this code reachable yet" a question the later two sub-phases can answer with a number.

#### 7.1 The findings table

Findings persist in `state.db`, written by the stage that discovers them and queried by `report`. Not in-memory: a record that dies with the terminal buffer cannot be the only copy of a broken Help button.

```sql
runs(run_id, command, batch, started_at, finished_at, exit_code)
findings(id, run_id, stage, severity, code, slug, version, path, message, count)
```

- [ ] **`code` is the contract; `message` is prose.** Tests assert on codes, so a message can be reworded without breaking anything, and an obligation that exists only as an English sentence becomes an enumerable thing. This is the single design decision that makes §7.5 auditable.
- [ ] **Severity is a property of the code, fixed in one registry — never chosen at the call site.** Two call sites reporting the same condition at different severities makes the exit code a matter of which one fired.
- [ ] **Errors and warnings get one row each; notes are aggregated into a single row with a `count`.** You act on an error individually and only need the magnitude of a note — and a per-file note would write hundreds of thousands of rows for the orphan-image case alone. The list behind a note is regenerable by re-running the stage.
- [ ] **Findings are written inside the stage's existing transaction** (`state.py:transaction`, §3.5). A failed stage leaves none, which is what keeps invariant 11 true — a failed run must not write partial measurements.
- [ ] Retained across runs, so §7.6 is a query rather than a re-parse. `report --prune --keep N` for the day that matters.

#### 7.2 Severity, and what gates

| Severity | Meaning | Exit effect |
| :--- | :--- | :--- |
| `error` | The output is wrong or unpublishable | `validate` exits **1** |
| `warning` | The run succeeded; a human decision is pending | Printed and counted; exit 0 |
| `note` | Normal for this corpus, recorded so a change in magnitude is visible | Counted only; exit 0 |

- [ ] **Only `validate` gates.** A `convert` that finishes 99 of 100 versions and reports one error has done its job; failing it would make partial progress impossible and tempt everyone to pass a skip flag. **But invariant 10 still binds**: a stage command that did nothing at all exits non-zero, which is a different condition from having found problems.
- [ ] **`note` exists so that `warning` stays worth reading.** 54.6% of Flare's images are orphans by the authoring tool's design; filed as warnings, they would bury the six that matter.

#### 7.3 Command surface

Three commands, split by the question each answers — the current `status`/`report` pair has no stated boundary and would otherwise converge.

- [ ] **`docushift status` — *where is everything now?*** A standing snapshot over the catalog, needing no run: counts per stage (discovered → in scope → eligible → downloaded → extracted → converted → synced), family workspaces, locale, batch tags. Extends what `status` already prints.
- [ ] **`docushift report` — *what happened?*** Findings from a run. `--run last|<id>`, `--stage`, `--severity`, `--code`, `--slug`, `--explain <CODE>`, `--export <file.md>`.
- [x] **`docushift validate` — *is the output correct?*** Runs §7.4 against `--target-dir`, writes findings, gates on errors. **Built, Phase 7b.**
- [x] `docushift csh {list,report,validate}` — per-version identifier listing, coverage, integrity checking. `csh report --since <version>` is §7.6. **Built, Phase 7c**, with one deliberate override: **coverage is across the published tree, not across a batch.** A batch is a `versions.csv` column, and `docushift report --run last --code CSH_UNRESOLVED` already answers the batch question from the run's own findings; the shelf had no reader at all. So the group takes `--target-dir` like `validate` and opens the catalog nowhere (`architecture.md` §7.6).
- [ ] **Markdown export only** (decided 2026-09-10 — no JSON, no HTML). One file: run header, then errors, warnings and notes grouped by stage then code. **Consequence: tests assert against the `findings` table, never by parsing the Markdown.** With no JSON there is no machine format to assert on, and a test that greps report prose pins the wording of every message in the tool.

#### 7.4 Link, asset and AEM-artifact integrity

- [x] Broken link and missing asset linter, including the CSH checks in `architecture.md` §5.4.6.
  - [x] **Classify before checking**: relative links resolve on the filesystem and a miss is an error; absolute URLs are external — which after Stage 7 means every API-reference link — and are skipped by default, HTTP-checked only under `validate --check-external`.
  - [x] **Percent-decode before resolving**, so the linter compares what a renderer would.
  - [x] **An unreferenced asset is not an error.** Orphans are a Phase 5 report line, not a lint failure — 54.6% of Flare's images are unreferenced by the authoring tool's design (`architecture.md` §5.5.7).
  - [x] A broken asset link here is a **regression against `design.md` invariant 13**, not a discovery: Phase 5 resolves the copy and the link together, so the count should be zero and the test exists to prove it stays zero.
- [x] **The AEM artifacts get field-level checks**, replacing `design.md` §8.4's "existence and well-formedness only" rule, which was justified by their shapes being guesses (both grounds gone — Phase 6 contract): `metadata.yml` carries its required `csg-*` key, non-empty; every `version.yml` `path` resolves to a sibling directory and every version directory has exactly one entry, ordered numeric-descending; every `csh.yml` value's file part exists and its anchor is present in that file.

#### 7.5 The obligation register

*Moved 2026-10-02 to [`docs/planning.md` §7.5](../../planning.md#75-the-findings-register-living): it is a living table, updated whenever a finding code is added, and `test_findings` checks it against the code.*

#### 7.6 Cross-version CSH regression

A dropped identifier is a Help button that breaks on upgrade, and it is invisible from inside a single version.

- [x] **The comparison target is the next-lower *converted* version of the same product**, by `natural_version_key` (§1.3, already built) — not "the previous run", which is a scheduling accident and would compare 10.4.0 against whatever happened to be converted last Tuesday. **Built, Phase 7c**, with the rule tightened by measurement: the predecessor is the immediate next-lower folder *in the same doc-class*, and if that folder has no map there is no finding. Skipping back to the last version that had one turns a vanished map into a row in every version after it.
- [x] **Read the prior version's `csh.yml` from the output tree**, not the findings table. That file is what actually shipped; the database records what the tool meant to ship, and the difference between those two is exactly the class of defect this check exists to find. **Built** — and the tree is the *published* one rather than the converter's output, for §7.3's reason above.
- [x] ~~A missing prior tree is a `note`, not a failure~~ **— refused on a number, Phase 7c.** The intent was *do not fail on a first conversion*, which writing no row honours. Writing one would add **150 rows** over the cache to a check that produces 51 real ones. The absence is a property of every product's oldest version, and it shows in `csh report`'s coverage table, which is a column rather than a finding.

#### 7.7 Sequencing: the findings module cannot wait for Phase 7

- [x] ~~**`reporting/findings.py` and the code registry land at the start of Phase 4**~~ **— slipped, and landed in Phase 5a instead** (2026-09-11), even though every command that reads them lands here. Phase 4 is the first stage that produces findings, and Phases 4–6 each carry several rows of the §7.5 register. If the module arrives last, those five phases each invent their own logging and Phase 7 becomes a rewrite of working code rather than a read layer over it. The table, the registry and a `record()` call are perhaps 80 lines; the commands are the phase.

  **What the slip cost, recorded rather than tidied away.** Phases 4a, 4b-1 and 4b-2 shipped without it, so Stage 4's two register rows (`CSH_SOURCE_EMPTY`, `CSH_SOURCE_UNPARSED`) exist today only as terminal output from `docushift extract` — the exact failure mode this section was written to prevent, arriving in the section that predicted it. It was caught while planning Phase 5, which carries **9 of the 20 rows**, and moved into 5a rather than deferred a second time. **Still owed after 5a**: both codes are *registered* and neither is *emitted* — `docushift extract` still prints its unreadable-source lines and writes no rows. That is the register working as designed (the reachability test names them, so the gap is visible rather than assumed closed), and it stays a small follow-on rather than a rewrite, because the report blocks already compute the counts.

- [ ] End-to-end integration test suite.
- [ ] **Docs in the same commit** — `design.md` gains §8.5 (findings and severity), §8.6 (the obligation register), §8.7 (cross-version CSH), with §8.4 rewritten for the AEM artifacts and §12 index rows for each; `architecture.md` §7 for the command surface; `user-guide.md` the `report` / `validate` / `csh` surfaces and the severity table; `CONTEXT.md` a ledger row. *(Split across the three sub-phases: §8.5 and §8.6 and `architecture.md` §7 land with 7a, §8.4's rewrite with 7b, §8.7 with 7c.)*

#### Phase 7a — The read layer, and the three stages that write no findings — **Complete (2026-09-16)**

**The phase this splits off is the one that makes the other two acceptable.** `report` is not the payoff of the register — it is the instrument every later sub-phase is measured with, and it is also where the register's own debt becomes visible as a number rather than as a paragraph in §7.7.

##### Measured 2026-09-16, against the shipped code and the real catalog

- **Nine of the thirty registered codes appear nowhere in `src/`** — a literal scan of every module except `findings.py` itself. By stage: **catalog** `SCOPE_RULE_UNMATCHED`, `EOS_ALIAS_STALE`, `EOS_PRODUCT_EMPTIED`, `BATCH_NOT_ELIGIBLE`; **extract** `CSH_SOURCE_EMPTY`, `CSH_SOURCE_UNPARSED`; **sync** `DOC_REFERENCE_MISSING`; **validate** `LINK_BROKEN`, `CSH_IDENTIFIER_DROPPED`. **An earlier count of twenty was wrong and the correction is the interesting part**: it came from grepping for `record("CODE"`, which misses every call whose code arrives on a continuation line or through a variable. That grep is also the obvious way to write a static reachability test, so the false positives it produces are recorded here rather than discovered by a test that fails on working code.
- **Two of the seven stage commands open a `FindingsRun` at all** — `convert` (`cli.py:1116`) and `sync` (`cli.py:1296`). `catalog`, `download` and `extract` write no rows, so a `report` built today could only ever show two stages of a seven-stage pipeline, and §7.7's "still owed" is wider than the two CSH codes it names.
- **The catalog already computes every figure its four codes need, and prints them.** `unmatched_scope_rules()` → **1** (`tibco-spotfire-for-apple-ipad`, the rename detector that has been firing since the first full crawl), `unmatched_eos_aliases()` → **0**, `triage_summary()` → **128 versions retired across 11 fully-retired products**, which is §3.11's published figure recomputed from the catalog rather than remembered from the run that wrote it. What is missing is not a measurement. It is a row.
- **`BATCH_NOT_ELIGIBLE` has no corpus traffic**: **0 of 4,462** version rows carry a `convert_batch`. It is reachable and it is a unit test, and recording the zero now is what stops a later reader diagnosing it as a defect.
- **CSH emptiness is the majority case, so its code has to aggregate**: 476 of 863 Flare alias files, 492 of 647 WebWorks `topics.js`, 38 of 418 DITA `head.js` (§5.4.1). One row per source would file roughly a thousand rows of *normal*. `CSH_SOURCE_EMPTY` is a note, notes fold on `(code, slug, version)` (§7.1), so it is one row per version carrying a count — the same shape `ASSET_ORPHANED` was given for the same reason.
- **The reader side of `state.db` is two methods** — `get_findings(run_id)` and `last_run(command)`. No run list, no filtered query, no delete. The write side has been complete since 5a: `runs`, `findings`, the `findings_by_run` index, `start_run` / `finish_run` / `record_findings`.
- **Findings volume is wildly skewed, which is what the filters and `--prune` are for.** Measured by converting 51 in-scope versions and counting what they recorded (48 minutes): **1,712 rows carrying 8,304 occurrences**, of which Flare contributes 1,690. The median version writes **2** rows and the 90th percentile writes **4** — but `tps/6.0.0` alone writes **1,005**, 59% of the sample, and the next three are all `ftl` at ~200. So a report is either two lines or a thousand, with almost nothing in between: `--code` and `--slug` are not conveniences, and a corpus-wide convert is the run that makes retention a question. The longest message recorded is 197 characters, so the export's table cells are not the constraint.
- **`runs.exit_code` is `0` on every row ever written**, because both callers call `finish()` with its default. And a stage command whose selection matches nothing prints a yellow line and returns **0** — so the "Exit-code Discipline" criterion (§2) is specified, twice, and implemented nowhere.

##### The design

- [x] **`docushift report` — what happened.** `--run last|<id>`, filters `--stage` / `--severity` / `--code` / `--slug`, plus `--explain <CODE>`, `--export <file.md>` and `--prune --keep N`. The stub's `--format terminal|markdown|html` **goes**: §7.3 settled Markdown export only on 2026-09-10, and a `--format` flag whose non-default values do not exist is the same lie as a `convert` that exits 0 having converted nothing.
  - [x] **`--engines` moves from `report` to `status`.** Engine resolution is a standing property of the catalog, not a record of a run, and it is the one flag on the current stub that answers the other command's question. `user-guide.md` §6 is updated with it.
  - [x] **Grouped by stage, then by code; errors, then warnings, then notes**, with a note's `count` beside it. The grouping is the register's own shape, so a reader who has seen §7.5 can find a row without being taught a second layout.
  - [x] **`--explain <CODE>` prints the register row** — severity, stage, obligation, and `specified_in`. That last field has been carried on `Code` since 5a with no reader; this is the reader it was written for, and it is what makes a finding traceable to the sentence that promised it.
  - [x] **`report` never gates.** Whatever it prints, it exits 0; only `validate` does otherwise (§7.2). It exits 1 for a run id that does not exist and for an `--export` path it cannot write — failures of the command, not of the run it is reporting on.
  - [x] **Tests assert against the `findings` table, never by parsing the report** (§7.3), with one stated refinement: an export test may assert that a **code** appears in the file. The code is the contract and the message is prose, so pinning a code pins nothing a reword should be free to change.
- [x] **`docushift status` — where is everything now.** A standing snapshot needing no run: the funnel (catalogued → in scope → not retired → eligible → downloaded → extracted → converted), engine resolution and what is still `auto`, family workspaces, batch tags, locale. `--bu` / `--family` narrow it.
  - [x] **There is no `synced` column unless `--target-dir` is given**, and then it is counted off the disk. 6b decided that sync currency is *compared and never recorded*, because a fingerprint in `state.db` would claim currency for a tree an editor had since changed — so the database cannot answer "is this version published" and a column that guessed would answer it wrongly for exactly the versions somebody had edited. The same direction 6b's drop-down takes: about the target, the disk is the truth.
- [x] **The three stages that write nothing get a `FindingsRun`**, in the shape `convert` and `sync` already use — constructed in `cli.py`, handed to the worker, flushed inside the stage's transaction.
  - [x] **`catalog fetch` and `catalog eos`** record the four catalog codes from the values `warnings()`, `unmatched_scope_rules()`, `unmatched_eos_aliases()` and `triage_summary()` already return. The rule is §7.1's: the stage that *discovers* the condition writes it, and both of these commands recompute it as part of doing their job.
  - [x] **`extract` records the two CSH codes**, and they are recorded by `extractor/inventory.py`, not by the CLI's report block. The walk is what knows a source was empty or would not parse; the CLI only prints what it is handed, and a finding written from the printout would be a second derivation of the same fact.
  - [x] **`download` opens no run, named rather than omitted.** It has no registered code, and a run row that can only ever hold zero findings is worse than no row: `report --run last` would select it, and the last thing a user did before asking what happened is frequently a download.
- [x] **The exit-code discipline is implemented where it was specified.** A stage command whose selection matches nothing exits **1** — `download`, `extract`, `convert`, `sync` — while one that did its work and found errors still exits 0. This is a **behaviour change to four shipped commands** and is called out as one: a `--batch poc-1` that matches no row currently looks exactly like a successful run in a script, which is the shape of failure §7.2 was written against. `--dry-run` is unaffected, because listing what *would* happen is the work.
- [x] **The §7.5 reachability test gains a static half and loses the phase chain.** The eight `REACHABLE_IN_PHASE_*` unions collapse into one `NOT_YET_EMITTED` frozenset, asserted **equal** to the registry's unreached set so that both directions fail — closing a code without updating the set breaks the test, and so does registering one and walking away. The new half is a literal scan of `src/` for each registered code, which catches "registered and never written down" cheaply. **It proves a code is written, not that it fires**, which is exactly why the curated set stays rather than being replaced by the scan.
- [x] **`report --prune --keep N`** deletes the findings of all but the N most recent runs, keeping the `runs` rows — §7.1's retention, and the reason `run_id` is an explicit column rather than a rowid alias. Cheap now, and the alternative is discovering the need for it on the day the database is already too big to query.
- [x] **What stays out, named rather than omitted.** `validate` and §7.4 are **7b**; the `csh` group and §7.6 are **7c**; `DOC_REFERENCE_MISSING` stays unemitted until §10.7's class 2 has §10.4's router answer, and it is the one of the three remaining debts that belongs to no sub-phase yet. `status` does not read the findings table and `report` does not read the catalog — the boundary §7.3 exists to defend is worth more than the one line of convenience that would break it.

##### Acceptance

- [x] **The unemitted set is exactly three, by test**: `LINK_BROKEN`, `CSH_IDENTIFIER_DROPPED` and `DOC_REFERENCE_MISSING`, each named to 7b, 7c and §10.7 class 2 respectively. Nine → three is the phase's headline number and it is asserted, not counted by hand.
- [x] **`catalog eos` against the real catalog writes 12 rows** — 1 `SCOPE_RULE_UNMATCHED` and 11 `EOS_PRODUCT_EMPTIED` — and they are the *same* 11 slugs the command already prints in red. The test that matters is not that rows exist but that the printed figure and the stored figure are one figure.
- [x] **An extract over a sample with known CSH statuses writes one row per version, not one per source**, with the count matching §5.4.1's ratio for the engine in question.
- [x] **`report --run last` over a full in-scope convert prints the same tally the convert run printed** on its own `Findings:` line. The write layer and the read layer agreeing about one run is the whole of what this phase claims.
- [x] **`report --explain` resolves for all 30 codes** — iterated over `REGISTRY`, so a code added later without an obligation line fails here.
- [x] **`--prune --keep 1` leaves one run's findings and no orphan rows**, with the `runs` rows intact.
- [x] **Docs in the same commit** — `architecture.md` gains **§7, the command surface** (the document has no §7 today and stops at §6.7); `design.md` §8.5 is updated to 30 codes and gains the read side, and §8.6 records the register as an auditable list with its §12 row; `user-guide.md` §4's "View Status & Delta Dashboard" is replaced with the real `status` and `report` surfaces and the severity table, and §6's `report --engines` becomes `status --engines`; `CONTEXT.md` a ledger row and the register count.

##### As built, where it differs from the design above

- **Extract's findings are recorded in `extractor/unpacker.py`'s `measure()`, not in `extractor/inventory.py`.** The design named `inventory.py` on the principle that the walk is what knows a source was empty, and the principle holds — but `inventory_tree()` is a pure function over a directory and does not know the slug or the version a finding has to be filed under. `measure()` is its immediate caller, holds both, and already owns the "write what this walk found to `state.db`" step. Putting the finding there keeps the walk free of the run and keeps the derivation single, which is what the bullet was actually protecting.
- **`PackageExtractor` takes an optional `findings=`.** Optional so a unit test and a `--dry-run` construct the extractor exactly as a run does, which is the same reason `FindingsRun` tolerates a `None` store.
- **`status` prints a footnote when `converted` exceeds `extracted`.** Measured against the real catalog on the day it was built: 4 converted, 0 downloaded, 0 extracted — every one of them a `convert --input` run over the `html-to-md` cache. The funnel is right and reads like a bug, so the command says which it is.
- **The `of eligible` share is suppressed on all four gate rows**, not just the first three. Convert-eligible is the denominator, and printing `100%` against it is noise.
- **`report --runs`** was added: the run list the `--run <id>` picker needs, since no other command lists run ids.

##### Verified against the real catalog, 2026-09-16

- **`catalog eos` wrote exactly 12 rows** — 1 `SCOPE_RULE_UNMATCHED` (`tibco-spotfire-for-apple-ipad`) and 11 `EOS_PRODUCT_EMPTIED`, the same 11 slugs the command prints in red, read back with `report --run 8`. The predicted figure and the stored figure are one figure.
- **`status` over the whole catalog**: 4,462 catalogued → 3,617 in scope → 2,294 not retired → 1,389 convert-eligible, with 1,291 versions still `auto`.
- **1,125 tests pass** (+64), lint clean.

#### Phase 7b — `validate` — **Complete (2026-09-16)**

§7.4 in full: the link, asset and AEM-artifact linter over `--target-dir`, `LINK_BROKEN`, and the one command in the tool that gates on what it finds. It is second because it is the first command that reads the *published* tree rather than the database, and because 7a's `report` is how its findings become legible. `design.md` §8.4 is rewritten with it.

**The reframe: almost everything `validate` looks for should not be there.** Stage 5 resolves the copy and the link in one pass (`design.md` invariant 13), so a broken relative asset link is not a discovery about the corpus — it is a regression in this tool. A linter written to *find* problems would be tuned for recall and would ship with a noisy baseline; this one is written to **stay** near zero, which means every gating check has to be one whose clean answer is knowable in advance. Where a check cannot make that claim — an anchor that depends on an emission convention no engine guarantees, an external URL that depends on the network — it is a warning and it does not gate. The measurement below is what turned that from a slogan into a specification: it found **two** broken links in 37,800, and it found them only after three classification rules were fixed that would otherwise have reported 121 correct links as broken and 1,626 warnings as errors.

##### Measured 2026-09-16, against a real published tree

Nothing in the checkout had ever been published, so one was built: 21 cached versions across all four engines (flare 15, docbook 4, webworks 1, dita 1) staged into a throwaway root, `convert --all` over the 19 the catalog accepted, `sync --all` into a throwaway target. That target is **6 trees, 91 published version folders, 10,190 Markdown files, 25,068 files and 728 MB**, and a prototype of the walk below was run over it.

- **40,054 references, of which 2,520 (6.3%) are raw HTML inside the Markdown** — `<a href>` and `<img src>` in the passthrough the engines emit for tables GFM cannot express — concentrated in 366 files. A linter reading only `[](…)` and `![](…)` would call the tree clean while those images 404. Separately, **11,887 `<a id=|name=>` anchor targets in 2,036 files**: the HTML is load-bearing in both directions.
- **121 of the 123 broken links were the linter's own bug, not the tree's.** With `publish_base_url` empty — the shipped state — a rewritten API-reference link is a tree-rooted path with no host (`architecture.md` §6.4.2), which `links.classify()` correctly calls RELATIVE. Resolve it against the citing page's directory and you get `html/apiguide/en-us-tib-analytics-userdocs-resources/…`, which exists nowhere. Detect it on the **raw** path instead and resolve it against `--target-dir`, and **121 of 121 resolve** — proving the link *and* that the API tree it names was actually synced.
- **That leaves 2 genuinely broken links**, the same reference in the same file in two versions of `tibco-eftl-enterprise-edition`: `api-reference/python/connection.md`, which the source package does not ship. Upstream authoring, not this tool — and still an error, because a 404 is a 404. The headline is therefore **not** zero: it is *zero from us, two from the publisher*, which is the number the acceptance criteria are written against.
- **Zero references live inside code.** Across 79,497 fenced lines and 928,552 characters of inline code span, the extractor dropped **0** links — the false-positive baseline that justified fence-stripping does not exist. The real trap is the opposite one: **787 HTML and 166 Markdown references sit on lines indented four spaces**, which is list continuation in converted help, not a code block. A CommonMark-correct extractor that honours indented code blocks would silently stop checking 953 references.
- **Anchors cannot gate.** 14,055 references carry a fragment onto a file that resolves; **12,429 match and 1,626 (11.6%) do not** — and spot-checking says these are real. `hocon-sb-JMSAdapter.md#mapsUsageNote` is cited six times in the file that should define it and the anchor is not there; `docker-create.md#docker-create_dockernotes` does not occur in `docker-create.md` at all. So the finding is worth raising — it is an unmeasured Stage 5/6 defect in its own right — and 1,626 of them cannot be allowed to fail a run.
- **`csh.yml`: 4 files, 215 entries, 0 missing file parts, and 33 of the 47 anchors missing.** The same split, from the other direction: the half `transforms/csh.py` controls is perfect, the half that depends on anchor emission is not.
- **Required artifacts are per doc-class, not global.** `online-help` has 19 `toc.yml` but only **2** `index.md` and **4** `csh.yml`; `api-references` has `metadata.yml` and nothing else (§6.2.1); the three document doc-classes have all three of `metadata.yml`, `toc.yml`, `index.md`. A single required-set would report 60 findings against correct output.
- **All 10 `-resources` product directories have no product `metadata.yml`**, because `sync` writes one per product in the docs tree only. That is as-built and undocumented either way, so it is *not* checked — see the open question below.
- **`sync` leaves `.part` directories behind when it fails.** Two online-help folders failed the copy (a Windows `MAX_PATH` overrun under `C:\tmp`, an artefact of the throwaway location) and left `1-5-0.part` and `1-6-0.part` on the shelf. The atomic swap did its job — no half-published folder — but a walk that enumerates directories counted them as two extra versions and found two extra broken links in them.
- **Cost: 93 folders and 10,190 files in 84 seconds.** Roughly a second per 120 files, single-threaded, with anchors cached per file. Extrapolated to 1,389 convert-eligible versions that is a run measured in hours, which is why the selectors are not a convenience.

##### The design

- [x] **`docushift validate` — is the output correct?** `--target-dir` (required), `--product` / `--version` / `--doc-class` to narrow, `--check-external` to verify absolute URLs over HTTP, `--dry-run` to list what would be walked. Writes findings, prints them grouped the way `report` does, and **exits 1 if and only if it recorded at least one `error`** (§7.2). The one gating command in the tool.

- [x] **It reads the disk, and the catalog is not its source of truth.** §7.1's table already says so; the consequence worth writing down is that the selectors filter *directory names*, not catalog rows. A published tree outlives the row that produced it — a product retired last week still has help on the shelf, and that is exactly when somebody wants to know whether it is intact. `validate` therefore works against a target another machine synced, with no `versions.csv` agreement required. It opens `state.db` to write its run, which is the 7a instrument being used rather than a second source of truth.

- [x] **One walk, three checkers, each a pure function over one version folder.** `validation/tree.py` enumerates `(tree, locale, slug, doc-class, segment)` from the disk; `validation/links.py`, `validation/artifacts.py` and `validation/csh.py` take a folder and return findings. None of them takes a `CatalogManager`, a `StateStore` or a `FindingsRun` — the driver records what they return. That is what makes each one testable against a fixture directory in three lines, and it is the same separation `sync/` already has between `router.py` and `distributor.py`.

- [x] **The walk skips `.part`.** A failed sync leaves its staging sibling on the shelf, and the measurement walked straight into two of them. Reporting findings about a folder the swap deliberately refused to publish is reporting on a file nobody can reach; worse, it makes a failed `sync` produce `validate` errors that a successful re-run silently cures, which trains people to ignore the gate. The presence of a `.part` is itself worth one note per folder, because it is litter from a failure that may have gone unnoticed. **New code: `SYNC_RESIDUE` (note).**

- [x] **Reference extraction reads Markdown *and* the HTML inside it.** Inline links, images, reference definitions and autolinks, plus `<a href>`, `<img src>`, `<source>` and `<iframe>` in the passthrough HTML — 2,520 of 40,054 references measured, 6.3%, in 366 files. An `<img>` in one of those is a link a renderer follows.
  - [x] **Fenced blocks and inline code spans are excluded, and indented lines are not.** The measurement found 0 references inside 79,497 fenced lines, so the exclusion buys nothing today and is kept only because a future engine emitting sample HTML inside a fence would otherwise break the gate. Treating four-space indentation as a code block, on the other hand, would stop checking **953 real references** sitting in nested list items — so the extractor is deliberately *not* CommonMark-correct here, and the reason is written into the code.
  - [x] **The extractor is multiline-aware.** `<img>` attributes in converted help span newlines; a line-oriented regex undercounts. Cheap to get right once, invisible when wrong.

- [x] **Classification and decoding reuse `transforms/links.py`.** `classify()` already strips the fragment and the query, percent-decodes and fixes backslashes, in that order — and §5.5.6 measured what skipping it costs: **1,872 WebWorks references reported missing that are not**, 1,224 percent-encoded and 648 backslash-separated. The linter has to decode exactly the way the emitter encoded or it reports the emitter's own correct output as broken. One resolution, two callers.

- [x] **A reference whose raw first segment names a tree in `--target-dir` is a host-less published URL, and it resolves against the target root.** This is the single highest-value rule in the phase: **121 of the sample's 123 broken links are what happens without it**, and `design.md` §9.6 already promised the behaviour ("§8.4 classifies these as external and does not resolve them against the filesystem") without saying where the classification happens. It happens on the *raw* path, before `resolve()` — after resolution the tree name is buried behind the citing page's own directory and the rule cannot fire. Resolving rather than merely skipping is the bonus: it catches help that links into an API tree nobody synced, which nothing else in the tool would notice. A dangling one is a `LINK_BROKEN`.

- [x] **Resolution is case-sensitive, on every platform.** The target is published to Linux. A link that differs from its file only in case resolves on the developer's Windows machine and 404s in production, which is precisely the defect class a linter is for. Where a case-insensitive match exists the message names the file that is actually there, so the fix is one rename rather than a search. It is a `LINK_BROKEN` like any other, because on the platform that matters it *is* broken. **This rule caught a data-loss bug on its first run** — see below; it is the reason the rule is in the phase rather than in a backlog.

- [x] **A missing file is an error; a missing anchor is a warning.** 1,626 unmatched fragments against 12,429 matched settles it arithmetically: an 11.6% rate cannot gate. It is still worth raising — the spot-checks say these are anchors the conversion genuinely dropped, not slug-algorithm disagreement, which makes this the first measurement of a Stage 5/6 defect nobody had counted. Explicit `id=` and `name=` attributes in passthrough HTML count as anchors alongside computed heading slugs, since the engines emit 11,887 of them. **New code: `ANCHOR_MISSING` (warning).**

- [x] **Absolute URLs are skipped by default and counted; `--check-external` checks them over HTTP.** 1,676 in the sample, and after §10.7 every link into an API reference on a configured host is one of these, so checking by default would put the API surface of every product on the wire on every run. Under the flag: deduplicated per URL across the whole run, `HEAD` with a `GET` fallback, the `discovery/client.py` request policy for rate and retry. **New code: `LINK_EXTERNAL_DEAD` (warning)** — a proxy, an outage or a host that dislikes `HEAD` is not a defect in the output, and an exit code that depends on the network is an exit code nobody trusts.

- [x] **CSH is checked as link integrity, because that is what it is** (§5.4.6, §9.6). A `csh.yml` value whose file part is absent is a `LINK_BROKEN` (0 in the sample); its anchor half is an `ANCHOR_MISSING` (33 of 47); an identifier in a topic's frontmatter that is not in `csh.yml`, or the reverse, is **new code `CSH_FRONTMATTER_MISMATCH` (warning)** — the two are written in one pass by `transforms/csh.py`, so a disagreement is a regression, but it breaks one Help button rather than the page, and §7.6's harder question is 7c's.

- [x] **The AEM artifacts get field-level checks**, replacing `design.md` §8.4's "existence and well-formedness only" rule — both of whose grounds are gone, since the shapes stopped being guesses when the AEM contract landed (2026-09-10).
  - [x] **Which artifacts are required is a per-doc-class table, not a global set.** Measured: `online-help` reliably has `toc.yml` and `metadata.yml` but `index.md` in 2 of 19 and `csh.yml` in 4 of 19; the three document doc-classes have all three (§6.2.2); `api-references` has `metadata.yml` alone (§6.2.1); `archives` has `index.md` and `toc.yml` and no version segment. One global set would raise ~60 findings against correct output. The table lives beside the doc-class constants it keys on, so adding a doc-class cannot forget it.
  - [x] **`metadata.yml`**: `csg-product` at product level and `csg-version` at version level, present and non-empty, and no version folder without one. **New code: `METADATA_INVALID` (error).**
  - [x] **`version.yml`**: every row DocuShift is entitled to own resolves to a sibling directory, every version directory has exactly one row, and the rows are in numeric-descending order. **New code: `DROPDOWN_INCONSISTENT` (warning)** — a warning, not an error, because `sync` deliberately preserves rows it does not own (`sync/versions.py`) and failing a run over somebody's intentional hand-edit is how a tool teaches people to stop running it.
  - [x] **`toc.yml`**: every `path` resolves to a file in the version folder. That is a link, so it is a `LINK_BROKEN`, and its `#anchor` half an `ANCHOR_MISSING`; giving the TOC its own code would mean two codes for one condition and a `report --code LINK_BROKEN` that misses half the broken links.
  - [x] **Any of the four YAML artifacts failing to parse is separate from any of them being wrong.** **New code: `ARTIFACT_UNPARSED` (error)** — the action is different (the file is unreadable, so no field check ran at all) and, more to the point, an unparseable file makes every other finding about that folder unsound. Reported once and the folder's remaining artifact checks are skipped.

- [x] **The `-resources` tree is walked, and `api-references/` is not link-checked.** `archives/`'s generated `index.md` and `toc.yml` are DocuShift's output and are checked like any other. The API trees are copied Javadoc — not this tool's output, not fixable from here, and 496 of 499 ship their own frame set. Walking them would dominate the run's wall-clock to report defects in somebody else's generator. Their `metadata.yml` is still checked, because that file *is* ours.

- [x] **`validate` writes nothing into the target.** The one command that reads the published tree is the one command with no business changing it; there is no `--fix`. Stated because a linter that can rewrite is the obvious next request and the answer wants to be on the record: the published tree is regenerated by `sync`, and a repair applied here would be silently reverted by the next run.

- [x] **The selectors are load-bearing, and the walk is measured.** 84 seconds for 91 folders extrapolates to hours over 1,389, so `--product` / `--version` / `--doc-class` are how the command is actually used and `--dry-run` says what a selection covers before it costs anything. Anchors are computed once per file and cached for the run; no file is read twice.

- [x] **Exit codes, all three rules in one command** (§7.4). Errors → 1. A selection that matched no version folder → 1, the same rule the four stage commands took in 7a. Anything else → 0, warnings and notes included.

- [x] **The register goes 30 → 37 and `NOT_YET_EMITTED` goes 3 → 2.** `LINK_BROKEN` starts firing and leaves the set by hand, as 7a's equality assertion requires. The six new codes are the §7.4 and §9.6 obligations that had no code because nothing had ever been written to raise them; `CSH_IDENTIFIER_DROPPED` stays outstanding for 7c and `DOC_REFERENCE_MISSING` for §10.7's class 2.

**One open question, carried rather than guessed.** No `-resources` product directory has a product `metadata.yml`, in all 10 cases, because `sync` writes that file in the docs tree only. Nothing in `architecture.md` §6.2 says whether AEM wants one there. `validate` therefore does not check it, and the phase records the gap instead of inventing a rule — a gating command that enforces a guess about someone else's contract is worse than one that stays quiet.

##### What the first run found — a Stage 6 defect, and it was losing text

The prototype read page links. The finished checker also reads `toc.yml`, and on its first run over the same tree it returned **five** errors rather than the two that were measured. The three extra were case-only: `toc.yml` said `html/install/installation.md` where the folder held `Installation.md`, in `tibco-patterns` 6.1.2 and 6.2.0 and `tibco-businessconnect-edi-protocol-powered-by-instream` 6.11.0.

The 404 was the symptom. `_slug` lower-cases a TOC container's label, and `navigation._free` tested the resulting path against the taken set **case-sensitively** — so with a converted `install/Installation.md` already on disk, `install/installation.md` looked free. On Windows it is not a second file: the generated container page was written straight into the converted topic, and `Installation.htm`'s text left the corpus without a single finding anywhere in the run. Three topics, silently, across three versions.

`_free` now folds case, the three container pages land on `installation-2.md`, and the three topics come back — the sample's file count goes 9,460 → 9,463. The measured baseline is unchanged at two errors, which is why the acceptance criterion below still reads two: the fix is what puts it back there. The general lesson is the one the reframe already claimed and this makes concrete — a check whose clean answer is knowable in advance is worth having precisely because the first thing it reports is real.

##### Acceptance

- [x] **The sample tree validates to exactly two errors, both named** — the `tibco-eftl-enterprise-edition` `python/connection.md` references in 7.1.2 and 7.2.0, exit 1. Not "clean": the measured truth, asserted as the number, so that a regression that adds a third is visible and a fix upstream that removes both is too. It reached two by way of five: see above.
- [x] **A TOC container whose slug collides with an existing topic in another case gets its own page** — `navigation._free` folds case, with a test that would have caught the three topics this lost.
- [x] **The 121 host-less API links produce no findings**, and moving the `api-references` folder aside turns all 121 into `LINK_BROKEN` — the rule tested in both directions, because a skip and a resolve are indistinguishable when everything is present.
- [x] **Deleting one asset from a published version turns exit 0 into exit 1**, with exactly one `LINK_BROKEN` row naming the file and the topic that points at it.
- [x] **Renaming a published asset to differ only in case is also a `LINK_BROKEN`**, on Windows, with the actual filename in the message.
- [x] **A `.part` folder yields one `SYNC_RESIDUE` note and no other findings**, however broken its contents.
- [x] **A reference on a four-space-indented line is checked; one inside a fence is not** — the two halves of the extractor's deliberate non-conformance, each with a fixture.
- [x] **Corrupting each of the four YAML artifacts in turn yields `ARTIFACT_UNPARSED` and no field-level findings for that folder** — the skip is asserted, not assumed.
- [x] **A `csh.yml` value pointing at a deleted topic is a `LINK_BROKEN`; a frontmatter identifier missing from `csh.yml` is a `CSH_FRONTMATTER_MISMATCH`** — the two halves of §9.6, distinguishable by code.
- [x] **`--check-external` makes no network call without the flag**, asserted by a test whose fake fetcher raises if called.
- [x] **`report --run last` reads back what `validate` just wrote**, which is the same cross-check 7a closed on and the reason 7b comes after it.
- [x] **Docs in the same commit** — `design.md` §8.4 rewritten and flipped to **Built** with its §12 row; `architecture.md` §7 gains **§7.5, what `validate` walks and what it refuses to do**, and its header stops calling `validate` unbuilt; `user-guide.md`'s `validate` block loses "not yet built" and gains the severity/exit-code paragraph and `--check-external`; `planning.md` §7.4's checkboxes and the §7.5 register's seven new rows; `CONTEXT.md` a ledger row and the register count 30 → 37.

##### Verified against the real published tree, 2026-09-16

- **The sample tree validates to exactly two errors, and they are the two that were predicted** — `tibco-eftl-enterprise-edition` 7.1.2 and 7.2.0, both citing `html/api-reference/python/connection.md`, which the source package does not ship. It reached two by way of five: the three case-only `toc.yml` rows the checker found on its first run were a real Stage 6 defect, fixed in `navigation._free`.
- **121 tree-rooted references, zero findings.** The highest-value rule, confirmed in the direction that matters: every host-less API link in the tree resolves against `--target-dir`, which also proves the `-resources` trees they name were synced.
- **9,463 files, 39,328 references, 2,418 of them HTML, 1,777 absolute, 12,440 of 14,3xx fragments matched.** The three recovered topics are the file count's move from 9,460.
- **3,006 `ANCHOR_MISSING` warnings and 1 `SYNC_RESIDUE` note over 2 `.part` folders** — exit 0 would have been wrong and exit 1 on either of them would have been worse. The gate fires on the two errors and on nothing else.
- **1,184 tests pass** (+59), lint clean.

#### Phase 7c — `csh {list,report,validate}` and the cross-version regression

The per-version identifier listing, coverage across the shelf, and §7.6's comparison against the next-lower published version, which is what `CSH_IDENTIFIER_DROPPED` is for. Last because it is the only part that needs two converted versions of one product on disk, and because a dropped identifier is a regression — something you check once the thing it regresses against is being produced routinely. `design.md` gains §8.7.

**The reframe: a dropped Help identifier is the one defect in this tool that cannot be seen from inside a version.** Every other check the tool runs is a statement about one artifact — this link resolves, this anchor is there, this `metadata.yml` has its key. §7.6's question is about two, and neither of them is wrong on its own: 6.10.0's map is correct and 6.11.0's map is correct, and the product's **Help** button still breaks on upgrade. That is why the comparison earns a command rather than a flag, and it is also why it cannot gate — the corpus says a map changes between releases far too often for "changed" to mean "broken".

##### Measured 2026-09-16, against the whole `html-to-md` cache

Every `Alias.xml`, `static/head.js` and `wwhdata/common/topics.js` under `cache/pub`, identifiers unioned per `(product, version)`, then each version compared with its next-lower one by `natural_version_key`. Script: `C:\tmp\csh_7c.py`.

| Measured | Number | What it decides |
| :--- | ---: | :--- |
| Products carrying CSH / versions carrying CSH | **153 / 470** | §7.6 is not a curiosity. A third of the catalogued products have a help map. |
| Products with ≥ 2 CSH-bearing versions | **104** | The comparison has something to compare on two thirds of them. |
| **Comparable adjacent pairs** | **317** | The population every rate below is over. |
| Pairs dropping ≥ 1 identifier | **51 (16.1%)** | `CSH_IDENTIFIER_DROPPED` fires on a sixth of upgrades. **It cannot gate.** |
| …of those, same-major upgrades | **35 of 294 (11.9%)** | Even restricted to the case that is unambiguously an upgrade, one in eight. |
| …of those, cross-major upgrades | **16 of 23 (69.6%)** | A major bump re-keys the map. That is a redesign, not a regression, and the finding says which kind it was by naming both versions. |
| Identifiers dropped in total | **784** (492 same-major) | The row count a per-identifier finding would write. |
| Median drop per affected pair | **4** (same-major: 2) | The interesting case is small. |
| Pairs losing > 90% of the prior map | **15 of 51** (same-major: 5) | Two pairs lose 188 of 188. **A per-identifier row buries the median case under the wholesale one** — 784 rows, of which 376 are two pairs. |
| Surviving identifiers that changed target | **1,084 of 8,425 (12.9%)**, in 81 of 317 pairs | **Retargeting is not a finding.** Pages get renamed between releases; the Help button still works. It is shown by `csh report --since` and never recorded. |
| Products whose oldest version has no predecessor | **150** | §7.6's "a missing prior tree is a note" would write 150 rows to say nothing happened — 32% of everything the check produces. Not written; see the refusals. |

**And the sample tree already contains one.** `tibco-businessconnect-edi-protocol-powered-by-instream` publishes 6-10-0 and 6-11-0 side by side in `C:/tmp/7b_target`, and **6.11.0's map has 28 identifiers where 6.10.0's had 123 — 95 dropped, 0 added**. The same 95 show in the cache's source alias files, so this is upstream authoring rather than a conversion defect, and it is the second time in two sub-phases that the first real run has found a genuine break in the published corpus. It means acceptance has a live finding to assert on rather than a fixture.

##### The design

**The `csh` group reads the published tree, and it takes `--target-dir` exactly as `validate` does.** This is the phase's load-bearing decision and it overrides §7.3's "coverage across a batch". A batch is a `versions.csv` column, so a batch-scoped `csh report` would have to read the catalog — and `docushift report --run last --code CSH_UNRESOLVED` already answers "did CSH come through for the batch I just converted", from the run's own findings. Building a second answer to that question is exactly the convergence §7.1's boundary exists to prevent. What has *no* reader is the shelf: which identifiers are published, where they point, and what changed since the version before. Three further consequences make it the right tree rather than merely the consistent one — the published tree is cumulative, so the predecessor is always there even when it was converted months and several runs ago; it is the upgrade path a customer actually travels; and it needs no `versions.csv` agreement, so a shelf another machine synced can be asked the question.

**One checker, three surfaces.** `validation/csh.py` gains `diff(prior, current)` and `check_regression(...)`, and nothing else computes a CSH difference. `validate` calls it in the product-folder pass it already runs `_dropdowns` in; `csh validate` calls the same functions scoped to CSH; `csh report --since` calls the same `diff` and **prints** instead of recording. The 7b ledger row is the reason the rule is written down rather than assumed: two implementations of one decoding rule is how a linter reports the emitter's own correct output as broken.

- [x] **`docushift csh list --target-dir T`** — every identifier in the selection, with its target and whether that target is on disk. Scoped by `--product` / `--version` / `--doc-class`, the same three selectors `validate` takes. **`--identifier <name>` is the query worth building the command for**: it looks one identifier up across *every* published version and prints the versions that have it and where each points, which is the question a support engineer arrives with — *the Help button for `Gateway.BusinessAgreements` is broken in 6.11.0, where did it go?* Without it the command is `cat csh.yml` with extra steps.
- [x] **`docushift csh report --target-dir T`** — coverage across the shelf: one row per product, with versions published, versions carrying a map, identifiers, distinct target pages, and identifiers dropped against the prior version. `--since <version>` narrows to one product and prints the §7.6 diff **in full** — dropped, added and retargeted, with every identifier named — which is where the 95 that the finding can only count are actually listed.
- [x] **`docushift csh validate --target-dir T`** — the §9.6 rules and the §7.6 regression, findings recorded, gating on `error` by §7.4's one rule. It is **not** `validate --product X`: it skips the link, anchor, asset and artifact passes, so it reads 4 `csh.yml` files and the pages they name instead of 9,463 files. That is the whole of its independent value and the phase does not claim more for it.
- [x] **`validate` gains §7.6** in the same commit. The gate's report has to be complete, and a warning it cannot fail on still belongs in it.

**The comparison target is the immediate next-lower version folder in the same doc-class, and nothing cleverer.** Sorted by `natural_version_key` over the **dashed published segment**, which orders correctly among segments because the key splits on digit runs and compares them numerically — `10-4-0` above `9-3-0`, measured, and the dashed form's failure to round-trip back to a dotted version (§4.1) does not touch ordering. **If the predecessor has no `csh.yml` there is nothing to compare and no finding is written.** The alternative — skip back to the last version that *had* a map — sounds more thorough and is worse: a product whose map vanishes in 6.11.0 would then report the same 123 identifiers again in 6.12.0, 6.13.0 and every version after, so one defect becomes an unbounded row count and the version that actually lost the map stops being identifiable. Under the rule as written, a vanished map fires exactly once, on the version that vanished it, with `count` equal to the predecessor's whole total.

**One warning row per version, with the magnitude in `count` and a sample in the message.** §7.1 says errors and warnings get a row each and only notes fold — and that rule is intact here, because the condition being reported is *this version dropped identifiers relative to its predecessor*, which is one condition per version and not one per identifier. The measurement is what forbids the other reading: 784 per-identifier rows, of which 376 come from two pairs, would bury the 30 pairs that dropped between one and five — and those are the ones that are actually a regression rather than a re-key. The message names the predecessor and the first few identifiers and says how many more there are; `csh report --since` is where the full list lives. The split is deliberate and it is the same one 7a made for notes: **the finding carries the magnitude, the command carries the detail.**

**No new codes, and that is worth stating after a phase that added seven.** `CSH_IDENTIFIER_DROPPED` has been registered and unemitted since 5a and this is the phase that reaches it. The register stays at **37** and `NOT_YET_EMITTED` goes **2 → 1**, leaving only `DOC_REFERENCE_MISSING`, which belongs to §10.7's class 2 and to no sub-phase yet.

##### What is deliberately not built, each with its number

- [x] **No note for "no prior version".** §7.6's third bullet asks for one; its intent was *do not fail on a first conversion*, and not writing a row honours that. Writing one would add **150 rows** to a check that produces 51 real ones — the absence is a property of every product's oldest version, and `csh report`'s coverage table shows it in the column where it belongs.
- [x] **Retargeting is not reported.** **1,084 of 8,425 surviving identifiers (12.9%) change target** between adjacent versions. That is authoring, not breakage: the identifier still opens a page. `csh report --since` prints it.
- [x] **No comparison against the *source* alias files.** The check is between two published maps. Comparing a published map against the ZIP it came from would be a second derivation of resolution, and §9.3 already rejected that for the same reason.
- [x] **No `--fix`, no rewriting of `csh.yml`**, for 7b's reason: a linter that edits the thing it is measuring cannot be trusted about either.
- [x] **`csh` does not read the catalog**, so it cannot say whether a version *should* have had a map. `status` and `report` own that question.

##### Acceptance

- [x] `docushift csh list`, `csh report` and `csh validate` run against `C:/tmp/7b_target`, and `csh list --identifier Gateway.BusinessAgreements` prints 6-10-0 with its target and nothing for 6-11-0.
- [x] **`csh validate` finds exactly one `CSH_IDENTIFIER_DROPPED`** on the sample tree — `tibco-businessconnect-edi-protocol-powered-by-instream`, 6-11-0, `count` 95, the message naming 6-10-0 — and **exits 0**, because it is a warning and the tree has no CSH error.
- [x] **A zero-drop control**, built — and the attempt to build it where the box said found a platform defect instead. Re-syncing `tibco-businessconnect-container-edition-edi-protocol-powered-by-instream` into `C:/tmp/7b_target` fails with `[WinError 3]`: the destination path is **268 characters**, past Windows' 260-character `MAX_PATH`, which is also why 7b left two `.part` folders there. Synced instead to the short root `C:/t7c` (1,005 files, 56.1 MB), where the product publishes 8 folders, 2 of them mapped, carrying the same 32 identifiers across 1 comparable pair: **0 dropped, `csh validate` reports "Findings: none" and exits 0.** A check that only ever fires has not been shown to be selective. The `MAX_PATH` failure is recorded as an Open below rather than fixed here.
- [x] `validate` over the whole tree still reports **two errors and no more**, now with the one new warning beside its 3,006 `ANCHOR_MISSING`.
- [x] `report --run last --code CSH_IDENTIFIER_DROPPED --export` reads the row back with its count.
- [x] **`NOT_YET_EMITTED` is `frozenset({"DOC_REFERENCE_MISSING"})`**, asserted equal, and the register is still 37.
- [x] Tests for the diff itself are fixture directories, as 7b's are, and none of them constructs a `CatalogManager`.
- [x] **Docs in the same commit** — `design.md` gains **§8.7 (cross-version CSH)** with its §12 index row and §9.6's fourth bullet flips from owed to built; `architecture.md` §5.4.6's last bullet and a **§7.6** for what the `csh` group reads; `user-guide.md` a CSH section; `planning.md` §7.3's three boxes and §7.6's; `CONTEXT.md` a ledger row and the status line.

##### What the acceptance run actually said

Against `C:/tmp/7b_target` — 101 version folders, 9,463 files, 39,328 references:

| | |
| :--- | :--- |
| `CSH_IDENTIFIER_DROPPED` rows | **1** — `tibco-businessconnect-edi-protocol-powered-by-instream` 6-11-0, `count` 95, message `95 of 6-10-0's 123: Gateway.BusinessAgreements, … and 90 more` |
| `csh validate` exit code | **0** — 34 warnings, no error |
| `validate` exit code and errors | unchanged: 2 errors, 3,007 warnings, 1 note |
| Zero-drop control (`C:/t7c`) | 8 published, 2 mapped, 32 identifiers, 24 pages, 1 compared, **0 dropped**; "Findings: none" |
| Register | 37 codes, `NOT_YET_EMITTED == {"DOC_REFERENCE_MISSING"}` |

`csh report --since 6.10.0` showed the shape of the failure the finding can only count: of the 123 identifiers 6.10.0 published, 95 are gone and the surviving 28 **all retargeted**, from `html/TIB_bcedi_edifact/edft.5.*.md` to `doc/html/edifact-config/*.md`. The product reorganised its help output between releases and took most of its identifiers with it — which is exactly the case the `wholesale` sentence exists to let a reader recognise without opening either file.

**Open, found here and not fixed: a `sync` destination path over 260 characters fails with `[WinError 3]` and leaves a `.part` folder behind.** Windows `MAX_PATH`. It is not a 7c defect — `sync` is Stage 7 and the two residue folders in `7b_target` predate this phase — but it is the first time the cause was identified rather than observed, and it will recur for any product whose slug, doc-class and version segment are long enough. The fixes are a shorter target root (what this phase did), the `\\?\` extended-length prefix on the destination, or enabling long paths in the registry; choosing between them is Stage 7's call, not this one's.

---
