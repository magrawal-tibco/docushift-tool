> Archived from `docs/planning.md` on 2026-10-02. Status: **Built (20a–20f), 2026-09-24**. Kept verbatim; a heading that says *Planned* was built later in this same section.
> Index of every phase: [`docs/planning.md`](../../planning.md#finished-phases).

### Phase 20: Reframe — A Flare Topic Is Too Small To Maintain — **20a–20d.1 built, 20e planned, 2026-09-24**

Every phase so far has converted a source tree faithfully. Reframe is the first that deliberately *changes the shape* of what the source said: it merges MadCap Flare's very small topics into fewer, larger pages, turning each former topic into an anchored `##` section, and it does so once, permanently, because Markdown becomes the authoring source the moment the migration lands.

The component arrived specified. `docs/REFRAME-REQUIREMENTS.md` defines R1–R7, five hard constraints and eight acceptance checks; `docs/REFRAME-INTEGRATION-PLAN.md` proposes the phasing. Both are committed verbatim and **neither was written against this codebase** — the plan says so itself (§2) and ends with seven questions for the DocuShift side. This section answers those seven against the code, and records the two places where the specification and this repository disagree.

#### 20.1 The seven questions, answered against the code

| # | Question | Answer |
|---|---|---|
| Q1 | How does a stage read the **conversion engine**? | `VersionRow.engine`, a `SourceEngine` enum (`models.py`) carried in the `engine` column of `config/versions.csv` and threaded to converters as `ConversionContext.engine` (`engines/base.py:236`). A stage reads it off the catalog row; nothing needs threading. |
| Q2 | Can eligibility return **more than one version of the same doc set**? | **Yes, and for the reference product itself.** `tibco-enterprise-message-service` has **6 eligible Flare versions** — 10.4.0, 10.4.1, 10.4.3, 10.4.4, 10.5.0, 10.5.1 — all converted and standing in `output/en-us-tib-ems/`. `_download_selection` (`cli.py:833`) passes `eligible_only=True` and returns every one of them. **R1.4 layout pinning is mandatory, not conditional.** |
| Q3 | Is there a **manifest/report convention** the four CSVs should match? | Partly, and it cuts both ways — see 20.3. |
| Q4 | Can a stage **fail the pipeline** on its own validation? | Yes, and there is a two-command idiom: `errors = findings.counts()[Severity.ERROR]`, `findings.finish(exit_code=1 if errors else 0)`, `raise click.exceptions.Exit(1)` (`cli.py:1498` for sync, `cli.py:1581` for validate). Note `convert` deliberately does **not** do this. Reframe follows sync and validate. |
| Q5 | Where do **per-doc-set configs** live, and is there precedent for editorial policy? | `config/*.yaml`, loaded through `ConfigManager` (`config.py:143`). The precedent is `scope.yaml`: a YAML rule file stating policy, overridable per row by a CSV column, with a `*_source` provenance column deciding who wins. `MAX_WORDS` belongs in exactly that shape. |
| Q6 | Can a stage **run standalone** against frozen upstream output? | Yes. `convert --input/--output` (`cli.py:1252`) already converts a standalone extracted folder, and `validate --target-dir` walks any synced tree. The plan's assumption holds and the fast iterate loop is available. |
| Q7 | Which stage owns `toc.yml`/`metadata.yml`, and does anything downstream consume them? | Stage 6a writes both, per version, at `converter/driver.py:423,429`, rendered by `converter/navigation.py` from `NavNode` trees. Downstream, `sync/distributor.py` writes *container-level* files of the same names and never rewrites a version's; `validation/artifacts.py:150` reads the version's `toc.yml` and checks every `path` in it. So Reframe has one producer to coordinate with and one checker that will grade its work. |

There is **no stage-registration abstraction** to hook into. A stage in this tool is a package under `src/docushift/` plus a `@main.command()` in `cli.py` — `downloader/`, `extractor/`, `converter/`, `sync/`, `validation/`. Adding Reframe means adding `reframe/` and a command, not registering with an orchestrator. The integration plan's "recommended integration shape" (§3) therefore lands as written, and the engine gate it asks for in two places (C1/C2) has only one place to live, which makes C2 the operative rule rather than a belt-and-braces one.

#### 20.2 The corpus checks out, and that is not a given

The requirements quote a POC baseline for EMS 10.5.1. Measured against this repository's own Stage 6 output at `output/en-us-tib-ems/tibco-enterprise-message-service/10.5.1`:

| | requirements §6 | measured here |
|---|---:|---:|
| topics | 1,441 | **1,441** |
| median words/topic | ~107 | **107** |
| total words | 226,517 | **226,871** |
| guides (top-level TOC items) | 9 | **9** |
| largest single topic | — | **3,533** |

The POC was run against DocuShift's output, not against some other conversion, so §6's numbers are a genuine regression baseline rather than a figure from a neighbouring tool. The 354-word gap is frontmatter handling and nothing to chase. The largest *topic* is 3,533 words and §6's largest *page* is also 3,533 — the POC's biggest output page was one oversized topic on its own, which is R1.3 already firing once on the reference corpus.

Two further facts the requirements do not mention, both from the measured tree:

- **`toc.yml` carries 1,441 paths and zero fragments today.** Every node points at a whole file. R3 turns most of them into `page.md#anchor`, which is a shape this tool already emits elsewhere — `NavNode.anchor` exists and 12.1% of Flare's *source* TOC entries carry one (`engines/base.py:91`).
- **Output filename stems are truncated to 20 characters** (`installation-overvie.md`, `integrating-with-thi.md`). R2 slugs anchors from the source filename, so it slugs from these truncated stems. That materially raises the collision rate the "dedup must loop" edge case (§7) was written about, and it is why that rule is not optional here.

#### 20.3 Where the specification and this repository disagree

Two conflicts. Both are cheap now and expensive after Phase 20b.

**1. `## Heading {#anchor}` is not a shape this tool can emit or check.** R2 specifies the Pandoc/kramdown heading-attribute syntax. GFM has no such syntax — the braces render as literal text — and this repository has already answered the question in the opposite direction: `engines/docbook.py:inline_override` emits `<a id="…"></a>` as passthrough HTML with the comment *"GFM has no anchor syntax"*, and Phase 19 extended exactly that mechanism. Worse, Stage 7 would not merely fail to see the anchor, it would see the **wrong** one: `validation/references.anchors()` collects computed heading slugs and `id=`/`name=` attributes only, and `slugify_heading` strips `{`, `#` and `}` as punctuation, so `## Overview {#tibemsd-conf}` registers the anchor `overview-tibemsd-conf` and every R4 link written to `#tibemsd-conf` becomes an `ANCHOR_MISSING`. **R2 is implemented as `markdown.anchor_marker()` above the heading**, which is the house idiom, is already validated, and is what Phase 19 shipped 40 of.

**2. Three of the four CSVs are derived data, and this tool does not publish derived data as CSV.** CSV here means one thing: the human-editable catalog surface, `config/products.csv` and `config/versions.csv`, written through `utils/csvio.py` and governed by `*_source` provenance columns. Derived per-version facts are YAML sidecars in the output tree (`toc.yml`, `metadata.yml`, `csh.yml`); derived *findings* go to the register and `state.db` and are rendered by `reporting/report.py`. So:

| spec artifact | proposed home | why |
|---|---|---|
| `manifest/pages.csv` | `reframe.yml` sidecar in the version's output tree | derived, per version, alongside `toc.yml` — the same shape and the same lifecycle |
| `manifest/topic-mapping.csv` | the same `reframe.yml` | it is the inverse index of the same fact; two files would be two truths |
| `manifest/redirects.csv` | `redirects.yml` sidecar, and a Stage 7 check | a redirect map is a publishing artifact, and R5's "zero dangling" is a validation question |
| **`manifest/review-queue.csv`** | **stays CSV, as specified** | it is the one human-editable artifact of the four, and that is precisely what CSV is for in this repository |

This is a change to R6's neighbours, not to R6. The review queue — which the integration plan (§5) correctly identifies as the contract to fix first — keeps its columns and its format.

#### 20.4 Phasing

Renumbered onto this repository's scheme; the integration plan's Phase 0–4 map onto 20a–20e.

- **20a — Contracts and the gate.** *(built)* `reframe/` package, `docushift reframe` command with the standard `_scope_options`, engine assertion inside the stage (C2), no-op passthrough for non-Flare, the `reframe.yaml` config shape with `MAX_WORDS` and the TOC-schema adapter seam. *Exit: the command runs over the whole catalog, touches nothing that is not Flare, and passes a Flare set through byte-identical.*
- **20b — Packing.** *(built)* R1–R5, fence-aware parsing, the three POC defects from requirements §10 left unported, **R1.4 layout pinning pinned to the newest eligible version** (required by Q2) — *the config key only here; the packer did not apply it until Phase 26* — determinism check. Anchors emitted per 20.3(1). *Exit: reproduces §6's baseline on EMS 10.5.1, page count allowed to rise from dropping `MIN_WORDS`.*
- **20c — Review queue.** *(built)* R6 and R7.1. On the critical path, not polish: the ~25–30 flagged pages are the only ones a human ever sees, and Phase 20b ships deliberately incomplete without this.
- **20d — Stage 7 integration.** *(built)* Teach `validation/` about the redirect map and the merged TOC, so R5 and R6's acceptance checks are enforced by the existing checker rather than by a second one inside Reframe. Wire the exit-code idiom from Q4.
- **20e — Pilot.** One doc set, queue worked, **explicit writer sign-off before redirects are published.**

#### 20.5 What this phase does not claim

- **That Reframe should run on all six EMS versions.** Q2 establishes that it *can* be asked to, which is what makes R1.4 mandatory. Whether the older five are worth merging is a scope decision for 20e, not a mechanical one.
- **That the 14 `engine=flare` rows are the Flare population.** 1,647 of the 1,683 convert-eligible version rows are `engine=auto` and detect their engine at extract time (`engines/detector.py`). Reframe's real reach is unknown until those run, and sizing it is not a blocker for 20a.
- **That §8's pre-existing defects have been confirmed here.** The requirements list 31 dangling in-page anchors and title mojibake in the reference corpus. Neither has been measured against the current tree, and Phase 19 changed how at least one engine emits anchors. They are baselined in 20b, before merging, exactly as the risk table says. *(20b: the link half is measured — 92 unresolvable relative references, all `.html`/`.htm` into a sibling `…-resources` tree that Stage 6 does not produce. They are counted as `unresolved`, left exactly as written, and reported as `REFRAME_LINK_UNRESOLVED` rather than failing the stage. The in-page anchor count and the title mojibake are still unmeasured and belong to 20c, which is the phase that looks at page titles.)*

#### 20a Contracts and the gate — **Built & verified, 2026-09-23**

`src/docushift/reframe/` — `driver.py` (the gate, currency, build-and-swap), `toc.py` (the adapter seam), `policy.py` (per-product resolution and the currency digest) — plus `config/reframe.yaml`, `ConfigManager.reframed_path` / `load_reframe`, and a `reframe` command sitting between `convert` and `sync`.

**The register gains a sixth stage.** `Stage.REFRAME` is declared between `CONVERT` and `SYNC`, which is what puts the section in pipeline order in `report` (`_STAGE_RANK` reads declaration order). Two codes, taking the register **44 → 46**, and deliberately only two: 20a merges nothing, so the only things it can report are the two ways it refuses to guess. The codes the merge itself owes — an oversized page, a collided anchor, a queued review — are not registered ahead of the checks that emit them, which is what `test_every_registered_code_is_written_down_somewhere_in_src` exists to prevent.

| decision | what was built | why not the obvious alternative |
|---|---|---|
| **Output location** | A sibling `reframed/` tree, never a rewrite of `output/` | C4. Boundary rules get tuned repeatedly and each pass needs a clean input; an in-place merge makes every tuning pass a restore from git, and makes the irreversibility the plan calls its first risk start one phase earlier than it has to. |
| **Engine gate** | First statement in `reframe_one`, before any path is computed | C2. `--input` is the invocation the selection cannot filter, and it is exactly where a wrong-doc-set run happens. |
| **Unrecognised `toc.yml`** | `REFRAME_TOC_SCHEMA_UNKNOWN`, **error**, version fails, nothing swapped | A half-parsed tree does not merge badly — it merges into a plausible page count with one branch silently missing. A configured schema that is not registered also fails rather than falling back to detection, for the same reason. |
| **Currency key** | `reframe_source_checksum` (the upstream `convert_source_checksum`) **and** `reframe_policy_key` (a digest of the resolved policy) | Keying on the input alone is convert's `convert_api_prefix` lesson. Here it would be the common case, not a corner: a tuned `reframe.yaml` would leave every tree reporting `current` and the tuning loop would silently be a no-op. |
| **Swap budget** | 8 attempts over ~9s, not `swap`'s default 5 over ~1s | Measured, not guessed — see below. |
| **Non-Flare rows** | Counted, never named | 1,669 of 1,683. The opposite call to `convert`'s `ENGINE_UNKNOWN`, which is rare and is a to-do. `NO_OUTPUT` is still named: it means somebody expected a merge. |

**Two things the first real run found.**

The swap failed on EMS 10.5.1 with `PermissionError: [WinError 5]` and left the `.part` tree standing — then succeeded on a manual retry seconds later. `swap`'s 1-second budget is calibrated against `convert`, which writes its files one at a time over minutes; this stage hands the scanner 1,441 files in a burst and immediately asks to rename the directory out from under it. Widened at the call site rather than in `utils/swap.py`, so the other callers' genuine failures stay fast. Three consecutive `--force` runs then passed.

The six DataSynapse Flare versions have **no `convert_source_checksum` recorded at all**, so they can never report `current` and are re-copied on every run. This is inherited behaviour, not a defect introduced here — `convert` applies the same rule — and the rule is the safe direction: no recorded provenance, no currency claim. Pinned by `test_a_version_with_no_recorded_conversion_is_never_current` so it is specified rather than accidental.

**R1.4 decided, not deferred.** The first full run raised `REFRAME_LAYOUT_UNPINNED` five times across two products. All three multi-version Flare sets are now pinned to their newest eligible version in `config/reframe.yaml` — EMS `10.5.1`, gridserver-manager `7.2.0`, hpc-cloud-adapter `2.2.0` — which is the version `iter_versions` yields first and the one a fix gets written against. The other three Flare products have one eligible version each and are left unpinned; the code will name them if a second arrives. The risk table calls this "cheap now and impossible later", and it cost one config block. **And a config block was all it was** — measured 2026-09-29, the pin changed no layout, because nothing read it but the check that warns when it is absent. Phase 26 built the projection that makes it mean something, and re-cut all four sets against it.

**Verification.** `reframe --all` over the full catalog: **6 reframed, 8 already current, 1,669 not Flare, 0 no-output, 0 failed, 0 findings.** EMS 10.5.1 passes through **byte-identical — all 1,476 files, SHA-256 per file, zero differences** — and reads **1,441 topics** out of `toc.yml`, matching the corpus measurement in 20.2 exactly. The input tree is unmodified on bytes and mtimes. A second run with no `--force` reports `current`; a `max_words` edit invalidates it. **1,373 tests pass** (25 new in `tests/unit/test_reframe.py`), `ruff` clean.

**What 20a does not do.** It merges nothing. `pages` equals the `.md` files copied, which is why the report reads `1441 topic(s) -> 1441 page(s)`; the number only becomes meaningful when 20b writes merged pages. No anchors are emitted, no TOC is regenerated, no redirects are written, and `review-queue.csv` does not exist yet. The `reframed/` tree is currently a copy, and that is the baseline 20b diffs against.

#### 20b Packing — **Built & verified, 2026-09-23**

Four new modules and one rewired driver. `packer.py` decides layout (R1, R2, R4.1, R4.2) and never opens a topic body — word counts arrive through a callable, so the whole of R1 is testable against a dict of sizes. `pages.py` turns a page's topics into bytes (R2.1, R4, R7). `audit.py` is §6's acceptance suite, run **before** the swap. `manifest.py` writes the two sidecars. `toc.retarget` regenerates the navigation (R3).

**The register gains three codes, 46 → 49.** `REFRAME_SELF_CHECK_FAILED` (error), `REFRAME_LINK_UNRESOLVED` (warning), `REFRAME_TOPIC_UNTOCKED` (warning). Each is registered alongside the check that emits it, not ahead of it.

| decision | what was built | why not the obvious alternative |
|---|---|---|
| **Anchor syntax** | `markdown.anchor_marker` as its own block above the heading | 20.3(1). GFM has no attribute syntax, so the POC's `## Title {#a}` renders the braces as literal text and the anchor does not exist. |
| **Reading order** | `_subtree` returns one ordered run of closed `Page`s and open `_Unit`s; the packer splices *around* the pages | The POC appended to a shared list as the recursion unwound, so an overflowing child subtree's pages landed before the page holding their own parent's topic — which reads earlier. Order becomes an invariant of the return type rather than something to check. |
| **R4.2** | Enforced at the join, not checked afterwards | "No page spans two source directories" then holds by construction. Every top-level subtree on the reference corpus is single-directory, so this changes nothing here; it is the sets not laid out that way that would otherwise get a page whose relative asset paths are correct for half its content. |
| **Fence-awareness** | Every scan matches against `references.mask_code` / `mask_html_blocks` and edits the original by offset | Requirements §7's latent corruption. A `# comment` preceding a topic's real H1 becomes the *anchored* heading, and the topic's identity becomes a line of shell. The corpus has zero of these, which is why the POC never showed it. |
| **Self-validation** | In the stage, before the swap; a failure removes the staging tree | §6 asks for it and §1 says why: the merge is a one-way door, so the run that built a tree is the last cheap moment to reject it. A check that lives only in the test suite protects the reference corpus and nothing else. |
| **Broken links** | Split into `unresolved` (absent from disk — tolerated, §8) and `orphaned` (present but unclaimed — fatal) | R4's discriminator is *unresolvable*, which is an existence question, not a suffix question. A first cut keyed on `.html` would have passed a genuinely orphaned `.md` and failed on Stage 6's pre-existing defects. |
| **Sidecars** | `reframe.yml` and `redirects.yml` at the version root, YAML | The POC wrote three CSVs into a `manifest/` directory beside the script, shared across every version it ever ran on, so the second run overwrote the first. These are the only place that survives the `.part` swap and the only place Stage 7 can find without being told. |

**Three things the corpus found that the reference set does not exhibit.**

*Word conservation failed by exactly one token per topic.* `<a id="x"></a>` is **two** whitespace-delimited tokens, not the one requirements §6's "+1 per topic" assumes. `shift_headings` now *measures* what it added and returns it; a hand-written constant only ever encodes whichever anchor syntax was in mind when it was written.

*A topic listed under two guides.* GridServer 7.2.0's `toc.yml` has 1,014 nodes over 1,000 distinct paths — `Typographical_Conventions.md` appears three times — and packing it three times copies its body onto three pages. A `claimed` set threads through the walk: the first node to reach a path owns the content, the rest become rows pointing at the same `page.md#anchor`, which `retarget` handles for free.

*A topic on disk the TOC never lists.* Runtime Agent 5.13.0 has 651 `.md` files and 649 nodes, and one of the two strays is the target of a live link. Stage 7 publishes the whole `output/` tree, so these are **already published**; dropping them would make Reframe delete live content as a side effect of a navigation gap. `packer.carry` turns each into a single-topic page rendered through the same pass — so its own links are rewritten — exempt from reachability only, and named by `REFRAME_TOPIC_UNTOCKED`.

**Verification against §6's reference baseline** (EMS 10.5.1, `max_words: 3000`):

| metric | POC baseline | built |
|---|---|---|
| topics → pages | 1,441 → 106 | 1,441 → **124** |
| words per page | median 2,354 · min 20 · max 3,533 | median 2,082 · min 7 · **max 3,533** |
| topics per page | median 12 · min 1 · max 60 | median 10 · min 1 · **max 60** |
| guides | 9 | **9** |
| words in → out | 226,517 → 227,958 | 226,871 → 229,753 |
| links | 2,345 checked, 2,314 rewritten, 0 newly broken | 2,784 checked, 2,695 rewritten, **0 newly broken** |

The page-count gap is accounted for twice over and the exit condition allows it. The POC ran against a *different* conversion of the same doc set (226,517 words against DocuShift's 226,871), and the reading-order fix refuses to merge units across an already-closed page — worth about eleven pages, and it buys pages whose sections are contiguous in the guide.

**Verification, the rest.** `reframe --all --force` over the catalog: **14 reframed, 1,669 not Flare, 0 failed, 0 errors, 7 warnings**; 11,776 topics → 1,131 pages. C5 checked by copying the tree aside and re-running with `--force` — `diff -r` byte-identical. C4 checked with `git status --porcelain output/` — clean. R2's looping dedup fires on exactly §7's case (`tibemslookupcontext-.md` → `-2`, then `tibemslookupcontext-2.md` → `-2-2`); 16 slugs collide corpus-wide and only two dedups fire, because R2's uniqueness scope is per page. The output tree is 124 pages + 33 images + `metadata.yml` + the three regenerated YAML files, and carries 1,441 redirects with unique `from` values. **1,417 tests pass** (66 in `tests/unit/test_reframe.py`, up from 25), `ruff` clean.

**What 20b does not do.** No review queue and no `review-queue.csv` — R6 and R7.1 are 20c, and a merged page still inherits its first topic's title with nothing flagging it. Stage 7 does not yet read `redirects.yml` or merge the TOC (20d). `MIN_WORDS` is deliberately not reimplemented (R1.2), and the POC's unused basename-keyed `dest` map is not ported.

#### 20c Review queue — **Planned, 2026-09-24**

R6 and R7.1. This is the interface between the mechanical stage and the writer, and the requirements put it on the critical path: "Reframe deliberately does not resolve these cases itself."

**The specified flag set does not discriminate in this implementation, and that had to be measured before anything was built.** Applying R6's five conditions literally to EMS 10.5.1 at `max_words: 3000` queues **124 pages out of 124** — which R6's own sentence forbids in the line above the table: *"a queue containing every page is not a queue."* Two flags are responsible:

| flag | fires on | why |
|---|---|---|
| `title-inherited` | **107 of 124** | The condition is "`n_topics > 1` and the page title equals its first topic's title". R7 *defines* the page title as the first topic's, so the second clause is true by construction and the flag reduces to `n_topics > 1`. |
| `single-topic` | **17 of 124** | R6's own column says "usually fine; flags structural outliers". A condition that is usually fine is not a reason to put a page in front of a human. |

Between them they cover every page — 107 + 17 = 124 — so the other three flags never get to mean anything. Those three, on their own, flag **20 pages**: `reference-list` 13, `heterogeneous` 7, `oversized` 1. *(18 as built — see the `heterogeneous` scope decision below.)* That is very close to R6's own predicted load of "roughly 25–30 rows out of 106 pages", which suggests the estimate was made against a queue the two structural flags did not dominate.

**A better page title cannot be derived from the TOC, and that is worth recording rather than re-litigating.** The obvious answer to R7.1 — "emit the best title it can" — is to title a page after the TOC node whose subtree it covers, rather than after its first topic. Measured: **30 of 124 pages are exactly one TOC subtree (20 of the 107 multi-topic pages), and in every one of those cases the subtree node's title is the identical string to the first topic's title.** It has to be: the packer walks bottom-up in reading order, so a subtree's own node contributes the first topic on the page it collapses into. There is no better title available from structure. R7.1's "best it can" is already what R7 emits, and the improvement is a human one — which is the whole reason the flag exists.

**Decided — `title-inherited` and `single-topic` annotate, they do not queue.** Measured on EMS 10.5.1, with `reference-list`, `oversized` and `heterogeneous` queueing as specified in every row; the first row is the one taken:

| rule for `title-inherited` | queue | share of 124 pages |
|---|---|---|
| **Annotation only — never queues a page by itself** ← chosen | **20** (18 as built) | **16%** |
| `n_topics >= 12` and the page is not exactly one TOC subtree | 56 | 45% |
| `n_topics >= 12` | 61 | 49% |
| `n_topics > 1` and not exactly one TOC subtree | 91 | 73% |
| `n_topics > 1` — the literal specification | 108 | 87% |

`single-topic` is annotation-only under every row; nothing in R6 argues for queueing a condition it calls "usually fine". Both remain visible in the queued rows' `flags` column and in `reframe.yml` for every page, so widening the queue later is a filter change rather than a re-measurement — which is why this is a safe row to take first.

**Everything below is settled regardless of which row is chosen.**

| decision | what gets built | why not the obvious alternative |
|---|---|---|
| **Location** | `<out>/review-queue.csv`, at the version root beside `toc.yml`, `reframe.yml` and `redirects.yml`; added to `_REGENERATED` | Same reasoning 20b applied to the sidecars. The POC's `manifest/` directory sat beside the script and was shared across every version it ever ran on, so the second run overwrote the first. The version root is the only place that survives the `.part` swap and the only place Stage 7 can find without being told. |
| **CSV, not YAML** | The one artifact of the four a human edits | Decided in 20.3 and unchanged. Derived per-version facts are YAML here; a flat worklist a writer opens in a spreadsheet is what CSV is for. Written `utf-8-sig` like the catalog CSVs, because titles carry `®`/`™` and Excel needs the BOM to read them. |
| **Columns** | `page_path, guide, n_topics, words, flags, detail` — R6's, unchanged | It is a published contract with an editorial skill that does not exist yet. Adding a column is cheap later; renaming one is not. |
| **Row order** | Reading order, matching `reframe.yml` | Not sorted by `page_path`. A writer works a guide at a time, and reading order is already deterministic, so sorting buys nothing and costs the ordering that makes the file navigable. |
| **Every flag recorded, queued or not** | The full flag set for every page goes into `reframe.yml`'s per-page block; the CSV carries only queued pages | Nothing is lost by narrowing the queue — a later decision to widen it is a filter change, not a re-measurement. This is also what makes the `title-inherited` row above reversible. |
| **`detail`** | One clause per flag, in the flags' declared order, joined by `; ` — e.g. `23 topics, median 61 words each`, `3,533 words over a 3,000 cap` | The flag says which judgment is being asked for; the detail has to carry the numbers that judgment turns on, or the writer opens the page to find them. |
| **Finding** | `REFRAME_REVIEW_QUEUED`, **note**, one per version, carrying the count and the flag breakdown. Register **49 → 50** | Not a warning. The queue is expected output of a successful merge on every run, and a warning that always fires stops being read — the same argument 20a made for counting non-Flare rows instead of naming them. |
| **Audit** | One new check: every queued `page_path` is a page that was actually written | The same class of bug `_redirects` already catches, and the same cost. A queue naming a page that is not there is a writer's dead end. |
| **Report** | `ReframeResult.queued`, surfaced in the per-version line and the run summary | The count is the thing a human acts on. It should not require opening a file to discover. |

*Exit: `review-queue.csv` at every merged version root; the queue is a strict subset of the pages and its size is defensible against R6's "not every page"; every flag is reproducible from `reframe.yml`; determinism unchanged.*

#### 20c Review queue — **Built & verified, 2026-09-24**

`src/docushift/reframe/review.py`, wired into `driver.py` between the pack and the write. Every row of the decision table above was built as written. One thing the corpus changed:

**`heterogeneous` counts *depth-2* ancestors only, and a guide's landing topic has none.** The first implementation bucketed a top-level row's own topic under its own title, which makes a page holding a parent topic plus its single child branch read as spanning two branches — the one shape that obviously is not heterogeneous. R6 says "depth-2 ancestor", and a guide landing topic does not have one. Measured on EMS 10.5.1: **5 pages either way against 7**, and the two dropped are exactly that false positive. A page merging a landing topic with *several* branches still flags, on the branches. Queue: **18 of 124**, not 20.

**Verified.** EMS 10.5.1, `--force`: 1,441 topics → 124 pages, **18 queued (14%)**, flag totals across all 124 pages `reference-list` 13, `oversized` 1, `title-inherited` 107, `heterogeneous` 5, `single-topic` 17. The one `oversized` row is `users-guide/tibemsd-conf.md`, a single 3,533-word topic — R1.3 forbids splitting a body, so the cap yields and the row says why. The queue reads as a worklist: eleven parameter tables, five multi-branch pages, one outsized topic. Two `--force` runs are byte-identical under `diff -r` (C5) and `output/` is untouched (C4). Suite `1,431 passed, 2 skipped`; `ruff` clean on `src`/`tests`; registry 50.

#### 20d Stage 7 integration — **Planned, 2026-09-24**

The merged tree currently goes nowhere. `sync` reads `config.output_path(...)` at `distributor.py:234` and has never heard of `reframed/`, so every version of every doc set publishes its unmerged Stage 6 pages and the four sidecars Reframe writes are, today, files on a developer's disk. 20d is the phase that makes the component load-bearing — and the phase where a mistake becomes a published URL.

**Two of the integration plan's four Phase 3 bullets are already done, and saying so is part of the phase.** Eligibility-driven version scoping shipped in 20a (C3, `_scope_options`, `eligible_only=True`). The Q4 exit-code idiom shipped in 20b: `cli.py:1451-1462` already fails the command on `len(stats.failures) or findings.counts()[Severity.ERROR]`, with the comment explaining why Reframe gates and `convert` does not. Neither is rebuilt. The **second TOC schema adapter** is measured and **not in scope**: all 14 merged doc sets parse as `items-path-children` and no run has ever raised `REFRAME_TOC_SCHEMA_UNKNOWN`. The seam stays; a second adapter arrives with the set that needs it.

What is left is the bullet this repository's own §20.4 wrote: teach Stage 7 and Stage 8 about the merged tree, so R5 and §6's TOC check are enforced by the existing checker against **what actually shipped**, rather than only by Reframe against what it believed it wrote.

**Half of that already works, and it was checked rather than assumed.** `artifacts._check_toc` resolves every `toc.yml` path against the published folder and — when the target is `.md` and the reference carries a fragment — looks the fragment up in `index.anchors(target)`. That is §6's "every referenced page exists; every referenced anchor exists" applied to a merged TOC, written three phases before there was a merged TOC to apply it to. Nothing needs adding for R3. `redirects.yml` is the one nobody reads.

##### The decision 20d turns on: publishing is opt-in, per doc set

| option | why not |
|---|---|
| Publish `reframed/` whenever it exists | 14 merged trees are already on disk from 20b/20c tuning runs. This option publishes all of them on the next `sync --all`, which is the irreversible step the whole plan exists to gate. |
| A `sync --reframed` flag | Not durable and not reviewable. The decision "this doc set is merged now" is a property of the doc set, not of one invocation, and it needs to survive the next person's `sync --all`. |
| **Opt-in per product in `config/reframe.yaml`** ← proposed | Same file, same shape and same reasoning as `pin_layout_to`. A writer's sign-off becomes **a commit** — reviewable, attributable, revertable — which is exactly what 20e asks for and the only form of sign-off this tool can actually enforce. Default `false`; **no product opts in during 20d.** |

So 20d ships the mechanism with nobody using it. That is deliberate: the pilot doc set is 20e's choice and a writer's, not this phase's.

**`publish: true` with no usable merged tree does not fall back.** A silent fallback to `output/` is the worst failure available here — it republishes 1,441 unmerged topics over a merged tree whose URLs are already live, un-merging published pages as a side effect of a merge that failed. Three cases, all reported, none published:

| state | what sync does |
|---|---|
| no `reframed/` tree | `SyncOutcome.NO_OUTPUT`-shaped row naming `docushift reframe`, same as a missing conversion |
| `reframe_source_checksum` ≠ the version's current `convert_source_checksum` | refuse and name it: the merge predates the conversion beneath it |
| tree present and current | publish it instead of `output/` |

The staleness test is the comparison Reframe already makes for its own currency (`driver.py:237-238`), read from the same state metadata. It belongs in `sync` and not in `validate`, because `validate` deliberately takes no catalog — §7.1, "the target is the evidence" — and a checker that needed the state DB could not check the one tree somebody most wants checked.

##### What validation learns

`redirects.yml`, checked the way `toc.yml` is checked, in `artifacts.py` beside it and reusing its codes:

| check | code | why |
|---|---|---|
| every `to` resolves to a file in the folder | `LINK_BROKEN` (**error**) | R5's "zero dangling", enforced at the gate. Same code `toc.yml` paths already use — a dangling redirect is a broken link that happens to live in a different file. |
| every `to` fragment is a real anchor on that page | `ANCHOR_MISSING` (warning) | A redirect landing at the top of a twelve-section page is the exact failure R5's anchors exist to prevent. Warning, matching `toc.yml`. |
| a `from` that still resolves to a published file | **`REDIRECT_SHADOWED`** (warning, register **50 → 51**) | New, and found by measuring rather than by reading the spec. |

**`REDIRECT_SHADOWED` exists because EMS has five of them.** 1,441 redirects: 108 where `from` is the page's own path (the leader of each page — harmless and expected, and excluded), 1,333 where the source topic is genuinely gone. Of those 1,333, **five have a `from` that still resolves on disk**, and all five differ from their target **only in case**:

```
_templates/Home.md                    -> _templates/home.md#home
_templates/Legal-and-Third-Party-Notices.md -> _templates/legal-and-third-party-notices.md#...
_templates/TIBCO-Documentation-and-Support-Services.md -> ...
c-and-cobol-reference/tibemsOAuth2Params-and-Environment-Variables.md -> ...
users-guide/DisasterRecovery.md       -> users-guide/disasterrecovery.md#disasterrecovery
```

On a case-sensitive host these are correct and necessary. On a case-insensitive one they are **301 loops**. The tool does not know which host it is publishing to, so it cannot call this an error — it names it, with the case-only ones distinguished in the message, and a human decides once per platform. Reframe cannot catch it either: its own audit resolves paths through `PurePosixPath` against a set it built, where the two names are distinct.

**Nothing else needs adding.** The sidecars land in `online-help/<segment>/`, which is not in `_INDEXED_DOC_CLASSES`, so `_check_index` never reports them as unlinked — checked, not assumed, and no `_GENERATED` change is needed.

##### What 20d will not do

**It will not rewrite redirect paths into published URLs.** `redirects.yml` ships as written, relative to the version root. The mapping from `online-help/<segment>/page.md` to a URL belongs to the publishing platform, and this tool has never been told it — baking a guess into a 301 map is a guess that becomes permanent the moment it is served. Naming the transform is 20e's conversation with whoever runs the platform, and it needs an answer before any redirect is published, not before this phase is built.

*Exit: `sync` publishes the merged tree for a doc set that opts in and refuses, loudly, for one that opts in without a current merge; a dangling redirect fails `validate`; EMS 10.5.1 publishes to a scratch target and validates with the five case-only redirects named and nothing else new; no product opts in on `master`.*

#### 20d Stage 7 integration — **Built & verified, 2026-09-24**

Every row of the plan above was built as written. Three files carry it: `reframe/policy.py` gains `publish`, `sync/distributor.py` gains `_source` and `_stale`, `validation/artifacts.py` gains `_check_redirects`. **Register 50 → 52**: `SYNC_MERGE_UNAVAILABLE` (warning, sync) and `REDIRECT_SHADOWED` (warning, validate).

**`publish` is the one policy field kept out of the currency digest**, and that is a deliberate exception to `policy.key`'s rule that the digest is the dataclass's own fields. In the digest, a sign-off commit re-merges the whole doc set for no change in output — and worse, the field's mere arrival changes the digest of *every* policy that does not name it, invalidating all 14 merged trees on this branch. The rule stays "every field counts"; `_NOT_OUTPUT` is the named exemption and it has to argue for itself.

**The import is lazy, and it has to be.** `reframe` reads `validation.references` for its fence-aware masking and `validation.artifacts` reads `sync.distributor` for `STAGING_SUFFIX`, so a module-level `from docushift.reframe import policy_for` in the distributor closes the loop and nothing in `docushift.validation` will load at all. Found by the suite, one import after writing it.

**Verified on the corpus, end to end.** EMS 10.5.1 opted in, synced to a scratch target, and validated:

| | |
|---|---|
| `sync` | 6 rows synced, 1,241 files, 39.4 MB, `Published merged (Stage 6b): tibco-enterprise-message-service.` The merged tree is what landed in `online-help/10-5-1/`, sidecars and all. |
| `validate` | 128 files, 2,919 references, **2,732 of 2,733 anchors matched**, **0 errors** |
| R5 at the gate | **zero `LINK_BROKEN` from `redirects.yml`** — all 1,441 redirect targets resolve to a published page *and* a published anchor |
| new | **5 `REDIRECT_SHADOWED`**, exactly the five predicted, each naming the 301-loop-on-a-case-insensitive-host condition |
| pre-existing | 1 `ANCHOR_MISSING`, `#Using`, an in-page link inside a page — §8's dangling-anchor baseline, not a redirect and not new |

**The refusal was verified on real data too**, and not only in tests. `tibco-datasynapse-gridserver-manager` 7.2.0 opted in: `online-help` published **nothing** and said why — *"publishes merged and the merge or the conversion recorded no source checksum, so neither can be vouched for"* — while its PDFs shipped normally, because documents come from the extracted tree and a merge has nothing to say about them. That doc set is one of the six DataSynapse versions with no `convert_source_checksum` at all, which is the inherited gap 20a pinned a test around; the safe direction turns out to be the one that matters here.

**`config/reframe.yaml` ships with `publish: false` and no product opting in**, which was the second thing decided. Both opt-ins above were temporary and are reverted.

Suite `1,449 passed, 2 skipped` (+18); `ruff` clean on `src`/`tests`.

**What 20d does not do.** No redirect path is rewritten into a published URL — see above, that belongs to the platform and needs an answer before 20e publishes anything. *(That premise was wrong and 20d.1 below corrects it: only the host belongs to the platform, and `published_url` settled what to do about a missing host in 6e.)* `sync` still has exactly one thing to say about Reframe, `_source`; nothing downstream branches on which tree it was handed. And no writer has signed anything off, which is 20e.

#### 20d.1 The published redirect map — **Planned, 2026-09-24**

20d shipped `redirects.yml` as written: `users-guide/foo.md → users-guide/bar.md#foo`, relative to the version root. I recorded that turning those into served URLs was blocked on the publishing platform. **That was wrong, and the codebase already says so.** `apirefs.published_url` solved this exact problem in 6e and wrote the answer into its docstring:

> An empty `base` yields the tree-rooted path with no scheme and no host. That is the shipped state and a deliberate choice: the path is the part this tool can derive, a link missing only its prefix is fixable by search-and-replace when the AEM host is known, and a link that was never emitted is not recoverable at all.

The host is unknown; **the path is not**, and the path is the part with the information in it. `publish_base_url` has been empty and supported since Phase 3.8, `sync` already composes cross-tree API links this way, and `catalog validate` already refuses a non-absolute base. So the transform is the one `published_url` performs, against `online-help` instead of `api-references`:

```
users-guide/bar.md#foo
  -> {base}/{tree}/{locale}/{slug}/online-help/{segment}/users-guide/bar.md#foo
  -> en-us-tib-ems-userdocs/en-us/tibco-enterprise-message-service/online-help/10-5-1/users-guide/bar.md#foo
     (the shipped state, base empty)
```

Both sides transform identically: `from` is the *pre-merge* published path of a topic that was in the same version folder, so it takes the same prefix.

##### Where it goes, and why not in the version folder

**A 301 map is consumed per site, not per version folder.** Rewriting the copied `redirects.yml` in place fails on its own terms and on a mechanical one:

- The mechanical one: `_identical` compares the published folder against its source file by file (`filecmp.cmp`, shallow). A file rewritten after the copy never matches its source, so **every version would re-copy on every run** and `CURRENT` would stop existing for merged products.
- The one that matters: a redirect map scoped to one version folder is not something a platform can serve. It needs every version's entries in one place, and it needs them to survive `sync --version 10.5.1`, which touches one folder out of six.

So it is written where `version.yml` is written and assembled the way `version.yml` is assembled — `{target}/{tree}/{locale}/{slug}/online-help/redirects.yml`, built by `finish_product` **from the doc-class directory after the copy**, not from the run's write list. That rule exists because a scoped run would otherwise rewrite a 38-entry drop-down down to one and report success; a redirect map has exactly the same hazard and exactly the same fix.

The per-version `redirects.yml` stays where it is. The two files have different jobs and the split is the same one `version.yml` makes against the version folders beside it: the version-root file is Reframe's **record** — relative, auditable, byte-identical across runs, and what `validate._check_redirects` resolves against the folder it sits in — and the doc-class file is the **published map**, which is cross-version and not resolvable that way.

##### Decisions

| decision | what gets built | why not the obvious alternative |
|---|---|---|
| **The transform** | One function in a new `sync/redirects.py`, mirroring `apirefs.published_url`: prefix, percent-encode the path, leave the fragment alone. Empty base yields the tree-rooted path. | Not a second composition of the same five segments. If the folder `sync` writes and the URL it emits are derived separately they disagree by a dashed segment, which is the bug `url_map`'s docstring records from `tps/6.0.0`. |
| **`.md` is kept** | The published path keeps the extension the published file has | The tool does not know whether AEM serves `page.md` or `page`. Every relative link inside every published page, and every `toc.yml` path, already carries `.md` — a redirect map that guessed differently would be the only artifact in the tree that disagreed with the others, and would be wrong in a way search-and-replace could not distinguish from correct. |
| **Assembly from the directory** | Every version folder under the doc-class that carries a `redirects.yml` contributes; versions this run did not touch keep their entries | `version.yml`'s first rule, for its reason. A scoped re-sync that silently dropped five versions' redirects would report success. |
| **Hand-added rows are carried through** | DocuShift owns an entry whose `from` sits under a version segment present on disk; anything else is copied verbatim in its original position. A file that will not parse is left alone and named. | `version.yml`'s second rule, and the same asymmetry: a stale row is a visible wart `validate` can name, and a deleted row is somebody's only copy. |
| **No new finding code for the empty base** | The run report names it once, beside the existing `Published merged (Stage 6b):` line | `PUBLISH_BASE_URL_UNSET` is registered against a different artifact and widening a registered code's meaning is worse than not having one. This is a property of the whole run, not of a product, and the shipped state is *expected* — a warning that fires on every run of a correctly configured tool stops being read, which is the argument 20a and 20c both made. |
| **`validate` checks it** | New doc-class-level check beside `check_dropdown`: every `to` resolves to a file under the target. `LINK_BROKEN`, the code `toc.yml` and the per-version map already use. | These are the entries actually served. The per-version check resolves relative paths against one folder; this one resolves tree-rooted paths against the target root, the resolution `links.py` already performs for every tree-rooted reference it counts (`links.py:194-203`). |
| **Register unchanged at 52** | No new codes | Every condition here is one of the three that already exist. |

*Exit: EMS 10.5.1 publishes and its doc-class `redirects.yml` carries 1,441 tree-rooted entries; a scoped re-sync of one version leaves the others' entries intact; a hand-added row survives; `validate` resolves every entry and reports nothing new; the per-version maps and the merged trees are byte-identical to 20d's.*

#### 20d.1 The published redirect map — **Built & verified, 2026-09-24**

Built as planned. One new module, `sync/redirects.py`, three call sites: `finish_product` writes the map, `cli._report_sync` names the base it was rendered against, `validation.artifacts.check_redirect_map` resolves it. **Register unchanged at 52** — every condition here is `LINK_BROKEN` or `ARTIFACT_UNPARSED`, both already registered against the same conditions in the same words.

**Verified on the corpus.** EMS opted in and synced to a scratch target, all six merged versions:

| | |
|---|---|
| the map | **8,639 rows** — 10-4-0: 1,457, 10-4-1: 1,442, 10-4-3: 1,429, 10-4-4: 1,429, 10-5-0: 1,441, 10-5-1: 1,441 |
| shape | every row tree-rooted (**0 carry a host**), every `to` ends `.md`, every `to` carries a fragment, sorted by `from`, `status: 301` throughout |
| `validate` | 768 files, 17,213 references, **0 errors** — all 8,639 published redirects resolve to a file the target holds |
| the check has teeth | one dangling row injected by hand → **1 error**, named with its `from`, its `to` and the folder |
| the scoped run | `sync --version 10.5.1` re-ran against the six-version map and produced a **byte-identical file**, all six segments intact. This is the bug the assembly rule exists for and it is the only one worth measuring here. |
| the hand-added row | a `legacy/ems-help.html → https://docs.example.com/ems` row added by hand survived a full re-sync in its own position; 8,640 rows out, 8,639 regenerated |
| currency | the re-sync after all of it reported **31 of 31 rows `Already current`** |

That last row is the one the placement decision turns on. Rewriting `redirects.yml` inside the copied version folder would have left it differing from its source, `_identical`'s shallow `filecmp` would have reported it stale, and **every merged version would have re-copied on every run** with `CURRENT` no longer reachable. The doc-class file is written beside `version.yml`, after the copies, and never touches a byte the copy placed: `reframed/…/10.5.1/redirects.yml` and the published `online-help/10-5-1/redirects.yml` are byte-identical.

**Two files, and the duplication is the point.** The version-root map is Reframe's record — relative, resolved by `_check_redirects` against the folder it sits in, byte-identical across runs. The doc-class map is the served 301 map — cross-version, prefixed, and not resolvable relative to anything. `validate` checks both and they do not overlap: the published map checks that every `to` names a file the target holds, and anchors are left to the per-version check, which has the folder index to check them against. Two checkers reporting one dangling anchor twice would make `report --code ANCHOR_MISSING` a count of how many views of the map exist.

**`relative_path` resolves a row whether or not it carries a host**, which is what let the validator stay ignorant of the config. `validate` takes no `ConfigManager` (§7.1) and so cannot know what `publish_base_url` was when the map was rendered — but it does not need to, because the tree name is the first path segment either way. A row that does not start at a published tree is somebody else's and is not resolved, the rule the page checker already applies to an absolute link.

The empty-base note goes in the run report (`8639 redirect(s) in 1 redirects.yml, tree-rooted (no publish_base_url set)`) and not into the register, because an empty base is the expected shipped state and a warning that fires on every correct run stops being read.

Suite `1,465 passed, 2 skipped` (+16); `ruff` clean on `src`/`tests`. `config/reframe.yaml` still opts nobody in.


#### 20e Pilot — **Planned, 2026-09-24**

The roadmap bullet is one line: *"One doc set, queue worked, explicit writer sign-off before redirects are published."* Preparing it found the gap 20d.1's closing note said was not there. `ReframePolicy` has four fields — `max_words`, `toc_schema`, `pin_layout_to`, `publish` — and **none of them is per-page**. A writer who reads the 18 rows and concludes "this page should have stayed granular" has exactly two places to put that: accept everything, or move the global cap and re-lay out all 124 pages to fix one. So 20e is not only a process phase; the queue is a question the config cannot currently answer.

##### What the 18 rows actually ask for

Measured, not assumed — this is the whole population a writer sees on the pilot doc set:

| flag | rows | the decision it puts to a writer | verb |
|---|---|---|---|
| `reference-list` | **13** | 20–60 topics of 60–90 words each, merged into one page. Right for a parameter reference; wrong if the topics are conceptually separate. | *stay granular* |
| `heterogeneous` | **5** | The page spans 2–4 TOC branches. | *split per branch* |
| `oversized` | **1** | `tibemsd-conf.md`, a single 3,533-word topic. R1.3 forbids splitting a topic body. | *none — nothing a writer can do* |
| `title-inherited`, `single-topic` | 17, 1 | Annotations. 20c measured that they hold for every page here and made them never queue alone. | *none* |

**Correcting the question I asked**: I proposed one `keep_separate` list described as covering both verbs, and the packer says it does not. The two are opposite operations on the same node. *Stay granular* means a subtree's topics never merge **with each other**; *split per branch* means a subtree is packed **as one unit** and never merges with its siblings — which is R1.1's existing top-level rule applied deeper. A single list cannot mean both, and guessing per entry from whether the path is a leaf or a directory would make the file's meaning depend on the shape of the tree it names.

So 20e builds **one** field, for the verb 13 of the 18 rows need, and records the other.

##### Decisions

| decision | what gets built | why not the obvious alternative |
|---|---|---|
| **`keep_separate` on `ReframePolicy`** ← approved | A per-product list of paths. A topic whose source path is, or sits under, a listed path **is never merged with anything**: it closes the page before it, and nothing joins onto it. One page per topic, which is Stage 6's own layout for exactly that subtree. | The name is the user's and it reads right. The semantics are the *granular* verb, because that is the 13-row case and because it is the conservative direction: un-merging is what a writer asks for when the merge was wrong, and the answer is always available — those pages already exist in `output/`. |
| **Paths are prefixes, matched against the source topic path** | `users-guide/monitor` matches `users-guide/monitor-messages.md` and everything under `users-guide/monitor/`. Compared as POSIX path parts, not string prefixes, so `users-guide/mon` does not match `users-guide/monitoring.md`. | The writer's evidence is `reframe.yml`'s `sections[].source` and the redirect map's `from`, both of which are source topic paths. Making the file name *output* pages instead would be a config keyed on the thing the config changes. |
| **`split_at` is not built** | Recorded here as the deferred second verb, with its measurement: **5 of 18 rows**, all `heterogeneous`. | No writer has asked for it, and the phase that finds out is this one. Building both now doubles the config surface on a guess; the 5 rows are still *reportable* today and a writer can name them in the sign-off commit. Naming a heterogeneous page's branches in `keep_separate` is a coarser answer than splitting it but never a wrong one — it returns those topics to what Stage 6 already publishes. |
| **It counts in the currency digest** | `keep_separate` is **not** added to `_NOT_OUTPUT`, and is normalized to a sorted tuple in `policy_for` | The opposite call to `publish`, and for the opposite reason: this field changes every byte downstream of it, so a tuned list that left trees reporting `current` is exactly the silent no-op `reframe_policy_key` exists to prevent. Sorted so that reordering the list is not a re-merge. |
| **An entry matching nothing is a warning** | `REFRAME_KEEP_SEPARATE_UNMATCHED`, warning, reframe. **Register 52 → 53.** | A typo in this file fails silently and looks exactly like "the writer's decision was applied." `scope.yaml` already warns for a rule matching no product, for the same reason. A warning and not an error: a path can legitimately stop matching when a version drops a topic, and failing the run would make a version's disappearance break the *other* versions' merge. |
| **The pilot is all six EMS versions** | No scope narrowing | §20.5 left this open. Layout is pinned to 10.5.1, so the six are diffable by construction and a decision taken on 10.5.1's queue is the decision that shaped all six. Publishing only the newest would leave five active versions serving unmerged topics under URLs the merge has already claimed in the 8,639-row map. |
| **Sign-off stays a human's commit** ← approved | `publish: false` unchanged; the runbook says what to read and what to write | The gate is the point of the phase. Nothing on this branch asserts a writer has read the pages, because nobody has. |

##### The runbook, and what 20e delivers without a writer

`docs/user-guide.md` gains the procedure: run `reframe`, open `review-queue.csv`, for each row open the page it names, and either accept it, or add its topics' source paths to `keep_separate` and re-run. Then one commit sets `publish: true` and says who signed off on what. Rolling back is the inverse commit plus a `sync`, and it is only cheap until the redirects are live — which is the sentence the whole gate exists for.

*Exit: `keep_separate` changes the layout of exactly the subtrees it names and nothing else; a listed path that matches no topic is named in the run report; two runs with the same list are byte-identical and a reordered list does not re-merge; EMS's 18-row queue is unchanged, because nobody has worked it yet; no product opts in.*

#### 20e Pilot — **Built, 2026-09-24**

`keep_separate` on `ReframePolicy`, a per-product list of source paths whose topics are never merged with anything. Built as planned, with one thing learned from the packer and one from the corpus.

**From the packer: the override has to close the run on both sides.** `_close_run` greedily extends a page until the cap or a directory change closes it, so marking a unit "separate" and closing *before* it is only half the rule — the last topic of a named subtree would then absorb whatever came next, which is the opposite of what a writer asking for granularity means. `_Unit` carries `separate`, and `_close_run` closes before *and* after it. The bottom-up collapse in `_subtree` gains the matching guard: a subtree containing a separated unit no longer collapses into one unit, which is what keeps `keep_separate` from being silently undone one level up.

**From the corpus: the file's matching rule had to get stricter than the config comment first claimed.** The draft comment promised `users-guide/monitor` would match `monitor.md`; segment matching does not do that, and the test said so. The rule shipped is the strict one — path as written, a file with its `.md`, a directory without one, nothing guessed from a bare stem — because a bare stem would name two different things depending on what happened to be on disk. Spellings of the *same* path are still normalized: Windows separators, surrounding whitespace, a leading `/`, a trailing `/`, and a leading `./`. That last one is the one a writer actually produces, by copying a path out of a file explorer, and left unnormalized it matches nothing and the merge it was meant to undo happens anyway.

**Verified against EMS.** `users-guide/command-listing.md` is the worst row in the queue — 60 topics, 2,978 words, the page a writer is most likely to reject. Listing its 60 sources:

| | baseline | with the override |
|---|---|---|
| 10.5.1 pages | 124 | **183** (+59: one page became sixty) |
| 10.5.1 queue | 18 | **17** (the row it answered is gone) |
| `redirects.yml` rows | 1,441 | **1,441** — `users-guide/create-route.md` now 301s to `create-route.md#create-route` instead of `command-listing.md#create-route` |
| files differing from baseline | — | 59 new pages, `command-listing.md` itself, the four regenerated root files, and **14 other pages — link retargeting only**, e.g. ``[`connect`](command-listing.md#connect)`` → ``[`connect`](connect.md#connect)`` |

Nothing else moved: the override re-laid out exactly the subtree it named. Reverting `config/reframe.yaml` and re-running returned the tree **byte-identical** to the baseline snapshot, and the queue to 109 rows across the six versions.

The digest behaved as the decision intended and as it costs: the field's mere arrival re-merged all six versions once (`Already current 0`), producing the same 124 pages and 18 queue rows as 20c's record — the layout did not change, only the key did. A second run reported `Already current 6`, and a run with the 60 paths shuffled and trailing whitespace added reported `Already current 6` as well, so reordering the list is free.

`REFRAME_KEEP_SEPARATE_UNMATCHED` fires on real data: two bad paths (`users-guide/no-such-topic.md`, and `users-guide/command-listing` without its `.md` — the exact strictness trap) produced one extra warning naming both, aggregated per version rather than one finding per path.

`split_at` remains unbuilt and measured at 5 of 18 rows. No product opts in: `config/reframe.yaml` ships `keep_separate: []` in `defaults` and `publish: false`, and the sign-off commit is a writer's.

Register 52 → 53. Suite `1,480 passed, 2 skipped` (+15); `ruff` clean on `src`/`tests`.

#### 20f CSH survives the merge — **Planned, 2026-09-24**

Reframe retargets `toc.yml` (R3) and emits `redirects.yml` (R5), and does neither for `csh.yml`. The file is not in `_REGENERATED`, so it falls through to `source.assets` — *everything that is not a topic* — and is `shutil.copy2`'d into the merged tree still naming the pre-merge topic paths. The requirements never mention CSH, and the reference corpus cannot show the gap: **EMS has no `csh.yml`**, which is why five phases of measuring against it found nothing.

##### What is actually broken, measured

Seven `csh.yml` exist under `output/`; two are in reframed Flare sets:

| set | identifiers | paths dead in the merged tree | frontmatter `csh:` ids surviving the merge |
|---|---|---|---|
| `tibco-runtime-agent@5.13.0` | 108 | 105 | **0 of 108**, on 0 of 71 pages |
| `tibco-administrator-enterprise-edition@5.13.0` | 46 | 46 | **0 of 46** |

Opting runtime-agent in and syncing to a scratch target: **`LINK_BROKEN` 108 rows, 108 errors.** So the gate does hold — neither product can publish merged today — but it holds three stages too late. Reframe's audit runs before the swap precisely so a merge this broken is never built, and this one is built, swapped, synced, and only then refused.

**The second half is worse than the first and is hidden behind it.** `validation/csh.py:159` emits `LINK_BROKEN` and `continue`s, so a dead path short-circuits the anchor and mirror checks. Fixing only the paths would surface 108 fresh `CSH_FRONTMATTER_MISMATCH` warnings, because `pages._frontmatter` builds each merged page's frontmatter from the `Page` and discards every absorbed topic's — including §9.5's `csh:` mirror. Both halves have to move together or the second is discovered by the next person to run `validate`.

**The content itself is intact, which is what makes this small.** Both facts measured on the merged trees: **108 of 108** CSH anchors are present in the merged pages (the `<a id="…">` markers travelled with the topic bodies), and **0 of 154** CSH targets are topics the packer failed to place. Nothing has to be recovered; the map has to be pointed at where its content went.

##### Decisions

| decision | what gets built | why not the obvious alternative |
|---|---|---|
| **`csh.yml` joins `_REGENERATED`** | A `reframe/csh.py` retarget pass, called beside `retarget(roots, located)` in `_write_navigation`, writing the map from `located` | Leaving it an asset is the bug. The seam already exists and names its own reason — *"written fresh by this stage, so a copy of the source's version would be stale"* — and `csh.yml` has been exactly that since 20b. |
| **The path half is replaced and the fragment half is kept** | `topic.md#ident` → `page.md#ident`, the identifier's own anchor unchanged | This is where CSH and `toc.yml` differ and the difference matters. `toc.yml` gets the *section* anchor because a TOC node **is** the section. A CSH identifier points at its own `<a id>` marker, which survived the merge and is the more precise landing point; overwriting it with the section anchor would move every Help button to the top of its section for no gain. `redirects.yml` carries the section anchor, so the redirect map is **not** the right source for this rewrite even though it is the obvious one. |
| **A fragment-less entry gets the section anchor** | Fall back to `located`'s anchor when the value has no `#` | Measured: 0 of 154 in the two Flare sets, but **18 of 108** in `tibco-runtime-agent@5.12.2`, so the shape is real in this corpus and merely not Flare's. A fragment-less value landing on a merged page with no anchor is a Help button that opens a twelve-section page at the top — the exact defect R5 exists to prevent. |
| **The merged page carries the union of its topics' `csh:` frontmatter** | `pages._frontmatter` gains the identifiers of every absorbed topic, sorted | §9.6's third rule is a round trip, and dropping the mirror breaks it for all 154. Sorted rather than in section order because the digest and C5 both read this file, and because `transforms/csh.py` is the other writer of this key and a stable order is what makes the two comparable. |
| **The audit gains one check, and no register code** | Every `csh.yml` value resolves to a page that was written and an anchor that exists in it; every identifier is on its page's frontmatter | Same shape as the existing `_navigation` check, run before the swap. No new code: `validation/csh.py` already argues in its own docstring that a CSH target is link integrity and that inventing `CSH_TARGET_MISSING` would mean two codes for one condition. A failure here is `REFRAME_SELF_CHECK_FAILED`, which is what every other audit failure is. **Register stays at 53.** |
| **A version with no `csh.yml` is untouched** | No file written | Five of the seven `csh.yml` are not Flare and will never reach this code, and EMS has none. Writing an empty map would put a file in the merged tree that is not in the converted one, which `validate` reads as a promise nobody made. |

##### What this does not do

It does not reconcile CSH across versions — §7.6's fourth rule, a dropped identifier visible only by comparing two versions, stays `diff`'s job and is unaffected: the merge changes where an identifier points, never whether it exists. And it does not touch the five non-Flare maps.

*Exit: `csh.yml` in a merged tree resolves entirely against that tree — every path a page that exists, every fragment an anchor in it, every identifier mirrored in its page's frontmatter; runtime-agent 5.13.0 and administrator 5.13.0 sync and validate with **0 errors** where they produce 108 and 46 today; the identifier set is unchanged in both, because retargeting may move a Help button and must never drop one; two runs byte-identical; EMS, which has no `csh.yml`, is byte-identical to its current merged tree.*

#### 20f CSH survives the merge — **Built, 2026-09-24**

`reframe/csh.py` plus a frontmatter mirror in `pages._frontmatter` and one audit check. `csh.yml` joins `_REGENERATED`, so it is no longer copied through as an asset. Register unchanged at **53**, as planned.

**One decision changed under implementation, and it was the plan's own wording that was wrong.** The plan said `load` should return `None` both for "no map" and for "a map that will not parse", *"because the two call for the same thing: copy nothing and write nothing."* They do not. With `csh.yml` in `_REGENERATED` it is no longer copied, so writing nothing **deletes every Help button from the merged tree with no record anywhere** — the exact class of silent-deletion failure `packer.carry` exists to prevent for untocked topics. The three available answers are all bad: writing nothing deletes, copying through republishes the stale paths this phase exists to fix, and a partial parse loses whichever identifiers were past the error. So an unreadable map now raises `csh.Unreadable` and **fails the version before anything is written**, which is the rule the driver's own docstring already states for `toc.yml`: *"an unrecognised TOC is a failure, not a skip."* Same file class, same argument. Verified: a truncated `csh.yml` gives `x tibco-runtime-agent@5.13.0: csh.yml does not parse`, one `REFRAME_SELF_CHECK_FAILED`, and no staging tree left behind.

**The fragment rule held as measured.** Only the path half is rewritten; the identifier keeps its own `<a id>` marker, which is a more precise landing point than the section heading and which survived the merge in all 154 cases. A fragment-less value falls back to the section anchor. The audit resolves anchors through `validation.references.anchors` — the same function `validate` uses three stages later, so the two cannot disagree about what an anchor is.

**Results, on the two Flare sets that have a map:**

| | before | after |
|---|---|---|
| runtime-agent 5.13.0, dead paths | 105 of 108 | **0** |
| administrator 5.13.0, dead paths | 46 of 46 | **0** |
| frontmatter `csh:` ids surviving | 0 of 154 | **154 of 154** |
| `sync` + `validate` on both | **154 errors** | **0 errors** |

The remaining findings on that target are 16 `REDIRECT_SHADOWED` and the one pre-existing `#Using` `ANCHOR_MISSING` from 20d — no `CSH_FRONTMATTER_MISMATCH`, which is the check that would have fired had only the paths been fixed. The identifier **set** is byte-for-byte the source map's in both products: §9.6's rule is that a Help button may move and may never disappear, and that is asserted on the set rather than on the values.

Determinism and blast radius both confirmed: two forced runs of runtime-agent are byte-identical, and EMS 10.5.1 — which has no `csh.yml` — is byte-identical to its 20e baseline, so a version without context-sensitive help gets no new file and no changed byte.

The audit check emits no new code. A failure is `REFRAME_SELF_CHECK_FAILED`, and the three conditions are reported separately because they fail for different reasons: a missing page means the retarget did not fire, a missing anchor means the marker did not survive the body copy, and a missing mirror entry means `_frontmatter` dropped it.

Suite `1,494 passed, 2 skipped` (+14); `ruff` clean on `src`/`tests`. No product opts in.

---

#### 20e Pilot sign-off — **Signed off, 2026-09-25**

The human half of 20e, which no amount of code could supply. EMS's 18-row review queue was read and **every page accepted as merged** — so `keep_separate` stays empty for this product, and the queue's answer turned out to be the one the tooling could not have assumed. `publish: true` is now set for `tibco-enterprise-message-service`, with the reasoning in the config file beside it rather than only in this record, because the config is what the next person reads.

Re-verified immediately before the commit, against the current code rather than 20d.1's run: `reframe` reports **Already current 6**, and a sync of all six merged versions to a scratch target validates at **768 files, 17,213 references, 0 errors, exit 0**, with 8,639 redirects in one doc-class map. The 37 warnings are 7 pre-existing `ANCHOR_MISSING` — the DocBook `a.indexterm` anchors carried since 20b, unrelated to the merge — and 30 `REDIRECT_SHADOWED`, 5 per version.

**Those 30 are the one thing the sign-off does not settle, and deliberately so.** They are the case-only rows 20d measured: a `from` differing from its `to` in letter case alone, which is a necessary redirect on a case-sensitive host and a 301 loop on a case-insensitive one. Which of those the AEM host is, is not a fact about the documentation, so the tool names them and the answer has to arrive from the platform. They are warnings and do not gate.

What this changes operationally: `sync` now reads `reframed/` for EMS, so the next run against a real target replaces 1,441 published topic URLs per version with 124 merged pages plus the 301 map that points the old URLs at the sections that replaced them. The rollback is the inverse commit plus a `sync`, and it is cheap only until those redirects are being served.
