> Archived from `docs/planning.md` on 2026-10-02. Status: **Built, 2026-09-19**. Kept verbatim; a heading that says *Planned* was built later in this same section.
> Index of every phase: [`docs/planning.md`](../../planning.md#finished-phases).

### Phase 14: The Download Leg Has Never Run — **Built, 2026-09-19**

Three defects on one path — catalog row → ZIP → extracted tree — all found in one attempt to convert the `ems` family, and none of them reachable from the test suite: each needs either the live docsite or a real package deep enough to hurt.

The three compound. `zip_url` is wrong, so nothing downloads; nothing downloads, so `extract` never runs on a real package; `extract` never runs, so the path-length ceiling under `.part/` has never been hit. Every extracted tree in this repo arrived by hand-copy from the predecessor's cache, which is why Phase 12 was needed at all — and why `status` has reported `Downloaded 0%` on every family since the column existed.

#### 14a. Every active `zip_url` in the catalog is wrong

| | |
|---|---|
| products sampled (newest eligible version each) | 35 |
| stored `zip_url` returns a ZIP | **0** |
| landing-page pattern returns a ZIP | **28** |
| neither pattern resolves | 7 |
| `ems` eligible versions, stored `zip_url` | 0 of 7 |
| `ems` eligible versions, landing-page pattern | **7 of 7** |

It went unnoticed because **the docsite answers a missing `/pub/` path with HTTP 200 and an empty body**. The 2026-09-03 ledger row recording "33 EMS versions, 4 spot-checked URLs all HTTP 200" was checking the status code, and the status code is not the signal. `downloader/fetcher.py` already catches this correctly at download time — *"did not return a readable ZIP (most often an error or sign-in page served as HTTP 200)"* — so the defect was always going to surface here rather than in discovery.

The real pattern is not guessed. It is read out of `html/Resources/Scripts/landing-page.js`, a MadCap Flare file shipped **inside the package**, which reproduces the product's docsite landing page and builds its own Download Help link:

```js
finalSlug = slugify(productName) + "-" + version.split(".").join("-")
baseUrl   = location.href.split("doc/html")[0]      // -> /pub/{code}/{version}/
download  = baseUrl + finalSlug + "_documentation.zip"
```

Two things follow. The ZIP sits at the **version root**, not under `doc/zip/`; and its name carries the *dashed* version a second time. `finalSlug` is re-derivable from the display name, but need not be: the docsite API already publishes it as the per-version `slug` (`tibco-ebx-add-ons-6-2-3`), and in every case measured it equals the catalog's `slug` plus the dashed version. Re-implementing the JS `[^\w\s]` fold would be a second slugifier to keep in agreement with `utils/slug.py`, for no gain.

| File | Change |
|---|---|
| `config/docsite.yaml` | `active_template` becomes `/pub/{folder_path}/{slug}-{version_dashed}_documentation.zip`. The old template stays as a commented `legacy_template` with its measured 0-of-35 beside it, so the next person does not re-derive it |
| `discovery/client.py` | `active_zip_url(folder_path, slug, version)` — two new tokens, same `None`-rather-than-malformed contract |
| `discovery/crawler.py:309` | passes the slug and version it already holds |
| `downloader/fetcher.py` | derives through the same function rather than trusting the column |

**Precedence is the crux**, because the column is not empty — all 4,462 rows hold a confidently wrong string, so a plain `row.zip_url or template(...)` would never once reach the template. Stored wins only where it is a human override or an upstream-given fact:

1. `zip_source=manual` — the row is pinned by hand (§3.8). Stored wins.
2. archived — the stored value is the archive index's `zipPath`, given verbatim by upstream, never templated (`crawler.py:309` already refuses to guess one). Stored wins. `download` never fetches these anyway.
3. otherwise, active and `auto` — **derive**. The stored value is discovery output, and discovery output is known wrong catalog-wide.

That is what holds the catalog diff at **0 rows**. The residual untidiness is worth stating rather than hiding: for active rows `zip_url` keeps a stale string that nothing reads, until the next `catalog fetch` rewrites it through the corrected template. It is not blanked, because a 4,462-row deletion commit to remove data the next fetch regenerates is churn, and a blank column cannot be distinguished from "discovery found nothing".

The 7-of-35 residue is **reported, not chased**. Its shape is a directory-segment problem rather than a filename one — `businessworks_integrationmanager_plugin` publishes under `1.0.0_october_2004` while its catalog version is `1.0` — and each case looks bespoke. A new **`ZIP_URL_UNRESOLVED`** (warning) names the version and points at `--from-file`, which exists for exactly this. Register **41 → 42**.

#### 14b. The `.part` staging suffix pushes extraction over Windows MAX_PATH

All six EMS packages failed identically, on the deepest file in the `.NET` API tree:

| | |
|---|---|
| failing path, under `.part/` | **262** chars |
| the same path after the swap | **257** chars |
| Windows limit without opt-in | 260 |
| `HKLM\…\FileSystem\LongPathsEnabled` on this machine | `0x0` |

The tree is legal at its destination and illegal only while being built. The build-and-swap that exists to make extraction atomic is what makes it fail — `.part` costs 5 characters and the margin was 3. This is not an EMS quirk: `dotnetdoc`/`javadoc` trees across the corpus generate names like `class_t_i_b_c_o_1_1_e_m_s_1_1_a_d_m_i_n_1_1_detailed_transaction_info_1_1_producer_message.html`, and the real ZIP adds a wrapper directory (below) that the cache trees never had.

Shortening the suffix is rejected: it buys 4 characters against a ceiling that deeper trees will clear anyway, and it would trade a loud failure for a rarer one. **The fix is the `\\?\` extended-length prefix on write**, verified in isolation — a 278-character path fails on the plain form and succeeds on the prefixed one. It needs no administrator, no registry change, and no per-machine setup, which matters because the next person to run this has a different checkout depth.

| File | Change |
|---|---|
| `utils/` (new helper) | `long_path(p)` — on Windows, return `\\?\` + the absolutized, normalized path; elsewhere return it unchanged. One owner, because a second copy is how two writers end up disagreeing |
| `extractor/safe_unzip.py` | member writes and `makedirs` go through it. The traversal refusal stays **before** it and unchanged — prefixing must not become a way to escape the target |
| `utils/swap.py` | the rename pair, which is where a 262-char source still has to be addressable |

`\\?\` disables path normalization, so it must be applied to an already-absolute, already-normalized path — which is also why it belongs in one helper rather than at each call site.

**Built as `utils/longpath.py`, and it cost one more change than the table says.** `ZipFile.extract` joins the member onto a target it builds itself, so handing it a prefixed directory puts the limit straight back; `safe_extract` now opens each member and copies it to a destination it computes, which is also the point at which the already-proven-safe member name is the only sanitization being given up. The scope is deliberately the two *writers* of a staged tree and nothing downstream: a **final** extracted path over 260 characters would still be unreadable to every consumer, and that is a condition to report rather than to paper over one call site at a time. EMS does not reach it — 257 is the deepest — but a corpus-wide run may, and prefixing the whole pipeline would be a much larger change made on no evidence.

The control matters as much as the test: the deep-extract case was run against the pre-fix code path and raised `FileNotFoundError: [WinError 206] The filename or extension is too long`, so it is a regression test rather than a test that happens to pass.

#### 14c. A download worker pool trips SQLite

`download --family ems` with the default 4 workers: 5 of 6 succeeded and `10.4.3` failed with `InterfaceError: bad parameter or other API misuse`. Re-run alone, the same version downloaded cleanly. A SQLite error on a network stage, non-deterministic, and cured by serialising, is a connection crossing a thread boundary — the downloader's shared pool writing progress into `state.db`. It needs the connection made thread-local or the writes funnelled through one owner; which of the two is a reading of `state.py`, not a decision to take here.

This one is scoped to diagnosis in this phase: **reproduce it deliberately** (a wider pool over a family with more versions), then fix. A 1-in-6 silent failure on a stage that is about to run over ~1,500 versions for the first time is not something to leave until it shows up as a gap in the output.

**Reproduced, and it is neither of the two guesses.** The connection is already shared deliberately and `check_same_thread=False` makes that legal (`state.py:209`, written for Stage 3's pool). What was missing is narrower: **every write took the lock and no read took it at all.** Writes go through `_tx()`, which holds `self._lock`; the twenty-three read sites called `self.connect().execute(...)` directly, so one worker's `commit()` could land while another was mid-statement on the same connection.

Eight threads doing read → write → read, 400 rounds each, raised on 2–3 of every 3,200 rounds, on every one of three runs — and **one of those was an `IndexError: tuple index out of range`, not an `InterfaceError`**: a row coming back malformed rather than an exception. That is the half of the race worth the most, because it is the half that does not announce itself, and it is why the fix is a lock rather than a retry. Two helpers, `_one` and `_all`, take `self._lock` and **materialize inside it** — returning a live cursor would hand the caller a statement to step after the lock was dropped, which is the same bug with an extra step. Zero failures across four re-runs after the change.

#### 14d. The real package is shaped differently from the cached tree

The ZIP unpacks to `tibco-enterprise-message-service-10-5-1/{html,doc,pdf,…}` — one wrapper directory that `html-to-md/cache/pub/ems/10.5.1/` does not have. `roots.py` locates output roots by content and `apiref.py` decides by marker, so both should absorb an extra level; that is a claim to **check, not assume**, and it means the three versions already converted in this session came from a tree shaped unlike the one the pipeline will see from now on. They are re-extracted and re-converted as part of the acceptance below, and the output compared.

##### Acceptance

`docushift download --family ems` with the six hand-set `zip_url` values **reverted first**, so the derivation is what is under test rather than the override: 6 of 6 downloaded, each a real ZIP by magic number. Then `extract --family ems` on a checkout deep enough to reproduce 262 characters: 6 of 6 extracted, no `FileNotFoundError`, no `.part` left behind, and the deepest file present at its full name. Then `convert --family ems`: 6 of 6, and the three already converted from cache trees reconcile against their earlier output — a wrapper directory must not change the Markdown. `status --family ems` finally reads `Downloaded 6`, `Extracted 6`, `Converted 6`, the first time any family has.

For the URL change specifically: a `zip_source=manual` row keeps its stored URL untouched, an archived row keeps its `zipPath`, and an active row ignores the stale column. `ZIP_URL_UNRESOLVED` fires on `businessworks_integrationmanager_plugin@1.0` and not on anything that resolves. For the path change: a unit test that writes past 260 characters through `safe_unzip`, and the traversal-refusal tests unchanged and still passing — the prefix must not have opened a hole. For 14c: the pool reproduces the error before the fix and does not after. Then the full suite and `ruff`.

##### Met, 2026-09-19

The six `zip_url` values were reverted to the wrong template before the run, so every URL below was derived and none read.

| | |
|---|---|
| `download --family ems` | **6 of 6**, ~200 MB, every file a real ZIP; a second run reports 6 `Already current` |
| `extract --family ems --force` | **6 of 6**, 20,024 files, `flare` on all six, **no `.part` left behind** |
| `convert --family ems --force` | **6 of 6**, 8,613 topics, 8,847 files, **0 failures**, 38 findings and every one a note |
| `status --family ems` | Downloaded **6**, Extracted **6**, Converted **6** — 100% at every step, the first time any family has read that |

**14d is answered by arithmetic, not by inspection.** The three versions converted earlier in the session from the predecessor's wrapper-free cache trees produced 4,326 topics in 4,445 files. Re-converted from the real ZIP, with its `tibco-enterprise-message-service-10-5-1/` wrapper directory in the way, 10.5.0 + 10.4.1 + 10.4.0 produce 1,437 + 1,437 + 1,452 = **4,326 topics** in 1,476 + 1,475 + 1,494 = **4,445 files**. `roots.py` and `apiref.py` absorb the extra level exactly as claimed, and the claim is now a number rather than a reading.

**14d's scope, corrected 2026-09-19.** The arithmetic above is about *counts*, and it holds. It is not a statement that the wrapper is harmless: it was measured over Stage 5, which is the only stage that had run. Stage 7 had not, and the wrapper breaks two of its steps outright — see Phase 15.

The suite went 1,270 → **1,285** (+15, 2 skipped: the `\\?\` assertions are Windows-only and skip elsewhere), `ruff` clean. One test changed premise rather than being added: `test_a_version_with_no_url_is_a_report_line` asserted that blanking `zip_url` stops a download, which after the inversion means nothing — it is now two tests, one that a blank column no longer stops anything and one for the condition that genuinely remains, a version with no folder to build a path from. `tests/conftest.py`'s `project_root` copies the shipped `docsite.yaml` in for the same reason it already copied the AEM templates: a root without it now downloads nothing, which is a condition no installation is in.

---
