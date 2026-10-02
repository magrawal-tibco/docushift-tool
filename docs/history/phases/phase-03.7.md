> Archived from `docs/planning.md` on 2026-10-02. Status: **Complete, 2026-09-10**. Kept verbatim; a heading that says *Planned* was built later in this same section.
> Index of every phase: [`docs/planning.md`](../../planning.md#finished-phases).

### Phase 3.7: End-of-Support Exclusions

**Complete 2026-09-10.** Support publishes a retirement report, and **a retired version needs no conversion.** Latest drop: `cache/EOS Report-2026-09-10.csv` — 5,948 rows, 528 product names, columns `Product Name, Version, Release Status, Retirement Date, Last Updated On`. Statuses are `Retired` 5,642, `Retirement Announced` 291, `GA` 15. Two rows duplicate a `(name, version)` pair and **0 pairs carry conflicting statuses**, so the report is self-consistent and a plain last-wins read is safe.

Catalog work, not a pipeline stage, and it sits beside Phase 3.5 rather than inside it: scope is a *product*-level standing decision taken locally, retirement is a *version*-level fact reported upstream. Both answer "never convert this", and neither can be expressed as a cleared `convert_eligible` flag, for the same reason (§3.10) — the next fetch defaults new versions to eligible, so policy written as edited rows decays silently.

**Measured against the live catalog (634 products / 4,462 versions, 2026-09-10):**

| | all versions | in-scope **and** eligible |
| :--- | ---: | ---: |
| `Retired` | 1,751 | **128** |
| `Retirement Announced` | 192 | 94 |
| `GA` | 13 | 11 |
| no EOS row at all | 2,506 | 1,284 |
| **total** | **4,462** | **1,517** |

So the rule removes **128 versions from a working set of 1,517**, leaving 1,389. It looks small because it mostly *confirms* work already excluded: 1,560 of the 1,751 retired versions are already `is_archived=true` and `convert_eligible=false`. The value is not the 128 — it is that the exclusion now survives the next fetch instead of being re-enabled by it.

**Three decisions, taken by the user on 2026-09-10:**

1. **Only `Retired` gates conversion.** `Retirement Announced` (94 eligible versions, retiring 2027-04-30 and later) and `GA` still convert. The status is recorded either way, so a later report promotes them with no re-crawl.
2. **Absence means unknown, never retired.** 2,506 versions have no row: 2,050 because the product is absent from the report entirely, and of the remaining 456 the overwhelming majority are *newer* than anything the report lists for that product (`spotfire-data-science-workbench` 14.4.0/14.3.0/14.1.0 against an EOS maximum of 14.2.0). For a covered product absence reads as "not yet retired"; for an uncovered one it means nothing at all. Only an explicit `Retired` row is load-bearing.
3. **Exact-slug matching, plus a reviewed alias file.** The report offers no slug and no code — the display name is the only join key there is.

#### The join, and why it needs a reviewed alias file

`slugify(name)` against the catalog matches **237 of 528** report names exactly. A prefix-tolerant pass (iteratively stripping `tibco-`, `ibi-`, `spotfire-`, `jaspersoft-` from both sides) proposes 20 more with 0 ambiguities, and **271 names match nothing** — those are genuinely absent products, either undocumented on docs.tibco.com or named at a different granularity (EOS `DataSynapse GridServer` against catalog `…-gridserver-manager` and `…-gridserver-logviewer`).

The 20 proposals cannot ship unreviewed. **`Spotfire Analytics` → `tibco-analytics` is wrong**: the report lists 14.0.7–14.8.0 and the catalog holds 7.x and 10.x, **zero shared versions**. It is produced by stripping `spotfire-` from one side and `tibco-` from the other, which is exactly the looseness §3.10 already refused for scope rules.

Version-set overlap is the objective test, and it rejects **6** of the 20 (`Spotfire Analytics`, `Automation Services`, `DecisionSite`, `Developer`, `Miner`, `Operations Analytics`). It proves an alias; it does **not** disprove a match — 13 of the 237 *exact-slug* matches also share no version, and every one of those is plainly the right product whose report and docsite simply list different releases. The asymmetry is what makes the rule safe: since a version with no EOS row is never retired, **a zero-overlap alias changes nothing today**, so writing one is unverifiable speculation rather than a conservative default. Seed the file with the 14 provable aliases only; the totals are identical either way (1,751 / 128), because the 6 rejects contribute no rows by construction.

Rejected alternative: automatic fuzzy matching, no file. It covers the same products with no review step, and it is how `Spotfire Analytics` silently retires a live product the day either side gains a version.

#### The 11 products that lose everything

**11 in-scope products lose *every* remaining eligible version (25 versions).** Earlier arithmetic put this at 88, which counted products whose *newest catalog version* is retired; most of those are already archived and ineligible, so they are not a change. Restricted to what is actually in the working set today:

`tibco-auditsafe` (3), `tibco-businessworks-processmonitor` (9), `tibco-data-science-team-studio` (4), `tibco-silver-fabric-enabler-for-tibco-administrator-enterprise-edition` (2), and 7 more at one version each (`…-adapter-for-amdocs-crm`, `…-plug-in-for-twitter`, `…-cobol-copybook-plug-in`, `…-xa-transaction-manager`, `tibco-partnerexpress`, and two further Silver Fabric enablers).

These are fully dead products and dropping them is correct, but a rule that removes a product's entire documentation must say so out loud. **This gets its own report line**, not a warning buried among sixty others — it is the difference between "128 versions excluded" and "128 versions excluded, and 11 products now have nothing to convert".

- [x] **`config/eos/EOS-Report-2026-09-10.csv`** — the report committed under `config/`, not left in the git-ignored `cache/`. It is an input the catalog's contents depend on, exactly as `scope.yaml` is, and the exclusion has to be reproducible from a clean clone. Dated in the filename so the next drop is a *new file* whose effect is a reviewable diff, rather than an in-place overwrite that silently re-decides 128 rows. 445 KB, justified on the same grounds as the committed crawl fixture.
- [x] **`config/eos.yaml`** — the authored half: `report:` naming the active CSV, and `aliases:` as a list of `{report_name, slug, note}`. Seeded with the **14 verified aliases**, with the 6 rejected proposals present as commented-out candidates carrying their overlap figure, so the next reviewer inherits the evidence rather than re-deriving it. `ConfigManager.load_eos()` returns the parsed report indexed as `{slug: {version: (status, retirement_date)}}`; a duplicate `report_name`, an alias to an unknown slug, or a missing report file is an error, not a silent skip — the same contract `load_scope()` has.
- [x] **`ReleaseStatus`** StrEnum (`retired`, `retirement-announced`, `ga`, `unknown`) and **`ReleaseStatusSource`** (`manual` > `eos_report` > `unknown`). `CONVERTIBLE`-style set is unnecessary: exactly one value gates, and naming it in one predicate beats a frozenset of three.
- [x] **`ProductVersion.release_status`, `.retirement_date`, `.release_status_source`**, and the matching `versions.csv` columns placed immediately after `release_date` — GA date, retirement date and status read as one group. Un-prefixed, like `in_scope`/`scope_source` and unlike `_has_csh`: the leading underscore marks columns the tool owns outright, and these are hand-overridable.
- [x] **Excluded from `version_snapshot` and from `_MERGEABLE_VERSION_FIELDS`**, structurally rather than by rule — the docsite has no release-status value to three-way-merge against, so there is nothing for a fetch to overwrite.
- [x] **`_resolve_release_status()`, applied to every version the merge touches**, mirroring `_resolve_scope` (`design.md` §3.3.1) and ranked identically: `manual` short-circuits; a report hit sets status, date and `eos_report`; anything else **actively resets to `unknown`**, so removing an alias or shipping a corrected report really does restore the version. New versions included, so a release discovered after the report lands is classified on arrival.
- [x] **Version matching is exact string equality, with no normalization.** Trailing-`.0` coercion turned out to resolve exactly **one** of the 456 version-level misses, and any numeric coercion reintroduces the `1.10` → `1.1` hazard `csvio` exists to prevent (Phase 2). Unmatched versions are counted and reported, never guessed at.
- [x] **Normalize `Retirement Date` to ISO on read.** The report writes `MM-DD-YYYY` (`12-31-2025`); 2,782 of the retired rows carry one and the rest are blank. Verify `csvio`'s permissive date parsing handles the US ordering rather than assuming it — `01-15-2009` is unambiguous but `03-04-2021` is not, and getting it wrong is silent.
- [x] **The gate: `iter_versions(eligible_only=True)` skips `release_status=retired`.** It becomes the middle of four, composing outside in — scope (product policy) → retirement (upstream fact) → `convert_eligible` (local version policy) → `convert_batch` (scheduling). Conditioned on `eligible_only` for the §3.10 reason: a retired version is absent from the *work*, never from the *books*.
- [x] **`docushift catalog eos`** — re-resolve the status columns from the current report against the existing catalog and write the CSVs, without a fetch. A new report must not cost an hour-long crawl to apply.
- [x] **Reporting.** `catalog fetch` and `catalog eos` print the retired count **and the list of products left with nothing to convert**; `catalog triage` counts by release status beside family and scope provenance; `catalog list --retired`; `catalog set --release-status <value>` records `release_status_source=manual` for the one-off override.
- [x] **`warnings()`**: an alias whose `report_name` is absent from the active report (the rename detector, matching the unmatched-scope-rule warning); a retired version carrying a `convert_batch` tag, worded to distinguish a report verdict from a hand-set one exactly as the scope warning does. Both advisory, neither blocking.
- [x] **Tests.** The two regressions with names: `Spotfire Analytics` must **not** resolve to `tibco-analytics`, and `EBX` → `tibco-ebx` must (49 of 55 versions shared). Plus: `Retired` excluded and `Retirement Announced` / `GA` / no-row all still eligible; a version absent from the report on a product that *is* covered staying eligible; `release_status_source=manual` surviving a fetch that would retire it; an alias removed from the YAML restoring the version; a duplicate `report_name` rejected; an alias to an unknown slug rejected; `MM-DD-YYYY` round-tripping to ISO; a version string that must not be coerced (`1.10`); and the count assertion over the full 634-product dump — 128 eligible versions retired, 11 products emptied.
- [x] **Docs in the same commit** — `architecture.md` a new §3.11 for the report and the four-gate composition, with §3.7's gate list updated; `design.md` §1.1 (the status is not a key), a resolution section beside §3.3.1, and the §12 index; `user-guide.md` the new columns, `catalog eos`, and `--release-status`; `CONTEXT.md` ledger.

**Landed as measured.** `catalog eos` against the real catalog on 2026-09-10 retired exactly **128 in-scope eligible versions** across **11 emptied products**, with the report covering **251 of 634** catalogued products and **0 stale aliases**. 404 tests pass (55 new), lint clean. Two figures in the survey above were re-measured after the alias set was finalized and are corrected in place: absence-by-missing-product is 2,050 not 2,004, and trailing-`.0` coercion would have resolved 1 version rather than 14 — which strengthens the case for exact matching rather than weakening it.

**Not in this phase.** The 277 unmatched report names are left unmatched and unreported-on beyond a count — chasing them means deciding what `DataSynapse GridServer` maps to when the catalog splits it in two, which is product-knowledge work, not tool work. The report also carries `Last Updated On`, which nothing reads; it stays in the file and out of the model.
