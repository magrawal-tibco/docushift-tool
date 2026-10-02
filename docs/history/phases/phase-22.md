> Archived from `docs/planning.md` on 2026-10-02. Status: **Built & verified, 2026-09-28**. Kept verbatim; a heading that says *Planned* was built later in this same section.
> Index of every phase: [`docs/planning.md`](../../planning.md#finished-phases).

### Phase 22: The Redirect Map Does Not Start Where the Reader Does — **Planned, 2026-09-28**

20d.1 shipped a served 301 map and it is correct about everything except its starting point. Its `from` is the **pre-merge published path in the new tree** — `…/online-help/10-5-1/users-guide/foo.md`. That URL has never been served. It is the address the topic *would* have had in the new structure had it not been merged, which makes the map a faithful record of what Reframe did and useless for the migration cutover, because the URLs that are about to stop working are on `docs.tibco.com` and are not in the file.

What is missing is one join, and the pieces are all on disk:

- **`state.db`'s `output_map`** — `source → output` per version, written by `converter/driver.py:332`. For EMS 10.5.1: 1,441 rows, `tibco-enterprise-message-service-10-5-1/html/_shared/about-this-product.htm → _shared/about-this-product.md`.
- **Reframe's per-version `redirects.yml`** — `output → page.md#anchor`, 1,441 rows for the same version. The two counts agreeing is not a coincidence and is worth asserting: every converted topic has exactly one home after the merge.
- **`sync/redirects.published()`** — the version-root-relative path to the served URL, already written and already used.

**The origin URL, verified rather than assumed.** The live shape is `https://docs.tibco.com/pub/{folder_path}/doc/{source path, package-root segment removed}`, where `folder_path` is the directory part of `zip_url` under `/pub/` (`ems/10.5.1` for EMS 10.5.1). Checked against the live site on 2026-09-28: `https://docs.tibco.com/pub/ems/10.5.1/doc/html/_shared/about-this-product.htm` serves *About this Product* for EMS 10.5.1, which is the topic that row names.

**And it does not generalise, which is the whole design constraint.** Grouping `output_map` by the first two segments of its source paths across the converted catalog returns four distinct layouts:

| shape | example product |
|---|---|
| `<package-root>/html/…` | `tibco-enterprise-message-service`, `tibco-streaming`, `tibco-administrator-enterprise-edition` |
| `html/…` (no package root) | `spotfire-data-science-author`, `tibco-designer-add-in-for-tibco-business-studio` |
| `doc/html/…` | `tibco-datasynapse-gridserver-logviewer` |
| `<package-root>/designerhelp/…` | `tibco-runtime-agent` |

One rule applied to all four emits confident, wrong URLs for three of them. A wrong 301 is strictly worse than a missing one: the reader lands on a dead page and the map records success. So the origin template is **declared and verified per product, never inferred**.

#### Where the two files go

Per version, plus an assembled one per product — the same split `redirects.yml` already makes, for the same reasons, and with the same hazard to avoid.

- **Per version: `301.yml` at the version root of the *source* tree** (`reframed/…/10.5.1/` for a product that publishes merged, `output/…` otherwise), written by Reframe beside the `redirects.yml` it already writes at `driver.py:503`. It is then copied into the published tree like any other file. **It must not be written into the published folder after the copy** — that is 20d.1's measured trap: `_identical`'s shallow `filecmp` would see the version folder differ from its source and every merged version would re-copy on every run, with `CURRENT` no longer reachable.
- **Per product: `301.yml` at doc-class level**, beside `version.yml` and `redirects.yml`, assembled by `finish_product` **from the doc-class directory after the copy** — not from the run's write list, so `sync --version 10.5.1` cannot quietly publish a map that redirects one version out of six and reports success.

The coordinate systems mirror `redirects.yml` exactly: the version-root file's `to` is version-root-relative and auditable against the folder it sits in; the doc-class file's `to` is the served URL, tree-rooted when `publish_base_url` is empty. The `from` is an absolute `docs.tibco.com` URL in **both**, because unlike the `to` side it is not a path this tool invented — it is a live address, and truncating it to a path would lose the one thing that makes the row a cutover instruction.

#### Decisions

| decision | what gets built | why not the obvious alternative |
|---|---|---|
| **Origin templates are declared, not inferred** | New `config/origin-urls.yaml`: per product, the verified live URL template and the number of leading source segments to drop. EMS filled in and verified; everything else absent. | The four-layout measurement above. Inference would be right for EMS and silently wrong for Runtime Agent, and the failure is invisible until a reader hits it. This is `scope.yaml`'s shape — a YAML rule file naming products explicitly — for `scope.yaml`'s reason. |
| **A version with no declared template is skipped and named** | No `301.yml` is written; the run report names the version | The user's call, and the right one. A missing redirect is a gap someone can see and fill; a guessed one is a 404 with a success line beside it. |
| **New code `ORIGIN_TEMPLATE_UNDECLARED`, warning** | Register **52 → 53** | This is a genuinely new condition — not a broken link, not an unparsed artifact — and 20d.1's argument against widening a registered code's meaning applies in reverse here. A warning, not an error: an undeclared product is the expected state for all but one product today. |
| **Every converted topic gets a row, not only merged ones** | 1,441 rows per EMS version | The whole folder structure changed, so every live URL is about to break, merged or not. A map covering only merge-induced moves would leave the majority of the 404s unredirected — and that is the map that already exists. |
| **The row count is asserted against `output_map`** | A version whose `301.yml` row count differs from its `output_map` count fails the version | The join has three inputs and a silent drop in any of them produces a short map that looks fine. This is the one invariant that catches it, and it is free. |
| **`.md` is kept on the `to` side** | As 20d.1 | Unchanged argument: every relative link and every `toc.yml` path already carries it, and a map that guessed otherwise would be the only artifact in the tree that disagreed. |
| **`status: 301` throughout** | As Reframe's map | The file is named for it. A 302 is a different decision and nobody has asked for one. |
| **Hand-added rows survive; an unparsable file is left alone and named** | `version.yml`'s rules, via the existing `redirects.parse`/`merge` | Third time these rules apply to an assembled map. Reusing them rather than restating them is what keeps the three files behaving the same way under a scoped run. |
| **`validate` checks the `to` side only** | Every `to` in a doc-class `301.yml` resolves to a file under the target — `LINK_BROKEN`, via the existing `relative_path` | The `from` side is a URL on a site this tool does not own and cannot resolve offline. Checking it would mean a network call inside `validate`, which takes no config and makes none. |

#### Scope of this phase

EMS only — six versions, ~8,639 rows. It is the pilot, it is the one product whose origin URLs are verified against the live site, and it is the product whose merge has already been signed off, which makes it the one where the cutover is real. The other products gain nothing until someone confirms their URL shape, and `ORIGIN_TEMPLATE_UNDECLARED` is how they ask.

*Exit: each of EMS's six merged versions carries a `301.yml` whose row count equals its `output_map` count; the doc-class `301.yml` carries all six versions' rows, sorted, every `from` an absolute `docs.tibco.com` URL and every `to` tree-rooted; a scoped `sync --version 10.5.1` leaves the other five versions' rows byte-identical; a hand-added row survives; `validate` resolves every `to` with no new findings; a sample of origin URLs is confirmed live by hand before the map is called done; every other converted product reports `ORIGIN_TEMPLATE_UNDECLARED` and writes no file.*

### Phase 22 — **Built & verified, 2026-09-28**

`config/origin-urls.yaml` declares one product. `origins.py` turns a declaration plus a version's `zip_url` plus `state.db`'s `output_map` into rows; `reframe/driver._write_origins` writes `301.yml` into the **staging** tree so the copy's shallow `filecmp` check stays true; `sync/distributor._assemble_map` publishes the doc-class view after the copy. `sync/redirects` grew three parameters — `file_name`, `prefix_keys`, `merge(key=)` — rather than a second copy of the four rules.

**The asymmetry that is the whole phase.** `redirects.yml` prefixes both sides and reads entitlement off `from`, because both sides are ours. `301.yml` prefixes **only `to`** and reads entitlement off **`to`**, because `from` is an address on `docs.tibco.com`. Getting either wrong is silent: prefixing `from` buries a live host mid-path, and owning on `from` matches no prefix, regenerates nothing, and appends a second copy of every row on every run while every other assertion still passes. Both are pinned by a test.

| Exit criterion | Measured |
|---|---|
| Row count equals `output_map` per version | 1452 / 1437 / 1425 / 1425 / 1437 / 1437 — equal in all six, no dropped paths reported |
| Doc-class map carries all six versions | 8,613 rows; `{10-4-0: 1452, 10-4-1: 1437, 10-4-3: 1425, 10-4-4: 1425, 10-5-0: 1437, 10-5-1: 1437}`; every `from` an absolute `docs.tibco.com` URL |
| Every `to` resolves | 0 missing, checked in the reframed tree and again in the synced target |
| Scoped run leaves the rest alone | `sync --version 10.5.1` → doc-class `301.yml` **byte-identical** |
| Hand-added row survives | 8,613 → 8,614, the 302 carried through verbatim |
| `validate` | 0 errors; 7 `ANCHOR_MISSING` + 32 `REDIRECT_SHADOWED`, all pre-existing per-version findings, none from `301.yml` (30 before Phase 21's rebuild moved two page boundaries) |
| Origin URLs are live | `users-guide/connection-and-memor.htm` → "Connection and Memory Parameters"; `c-and-cobol-reference/tibemsmsgproducer-se.htm` → "tibemsMsgProducer_SetDeliveryMode"; `10.4.0/users-guide/export6.htm` → "Export" |
| Undeclared products | `tibco-runtime-agent@5.13.0` reframed, reported `ORIGIN_TEMPLATE_UNDECLARED`, wrote no `301.yml` |

**Deviations from the plan.** Two, both small. The `validate` check is `check_redirect_map` with a `file_name` argument rather than a new function — one checker, one message, and the `301.yml` name substituted into it, because the question and the code are identical. And the sync report line now says "N published map(s)" instead of "N redirects.yml": the counter always covered both files, and naming one of them was the kind of wrong that reads as right.

One observation worth recording: a **leader** topic gets `page.md#its-own-anchor`, not a bare `page.md`. That is `redirects.yml`'s existing shape and its reason — the reader arrives at the section rather than the top of a merged page — and it is why `REDIRECT_SHADOWED` fires at all.

---
