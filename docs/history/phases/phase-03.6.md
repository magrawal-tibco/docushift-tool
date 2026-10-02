> Archived from `docs/planning.md` on 2026-10-02. Status: **Complete, 2026-09-10**. Kept verbatim; a heading that says *Planned* was built later in this same section.
> Index of every phase: [`docs/planning.md`](../../planning.md#finished-phases).

### Phase 3.6: Re-key the Catalog on `slug`

**Planned 2026-09-10, blocking.** The first full `catalog fetch --all` was run on 2026-09-09 and **aborted before writing anything**: the deletion guard refused a merge that would have removed 38 version rows. The guard was right, and its diagnostic ("a version key was mangled") was wrong. The real cause is that **`product_code` is not unique**, and the catalog is normalized on it.

`_derive_code` takes the first segment of `folder_path`, which is correct for the ZIP URL and wrong as an identity: **rebranded products keep both their old and their new docsite entry listed, and both publish into the same folder.** Measured over the crawl (634 products, 4,462 versions, 0 errors — dump at `C:\tmp\crawl_all.json`): **10 codes are shared by 21 products.**

| code | products sharing it |
| :--- | :--- |
| `spotfire` | `spotfire` (1 version), `tibco-spotfire-general` (1), `tibco-spotfire-professional` (19) |
| `loglmi` | `tibco-loglogic` (1), `tibco-loglogic-log-management-intelligence` (20) |
| `clarity-dt` | `tibco-clarity` (14), `tibco-clarity-enterprise-edition` (4) |
| `stat-ext` | `spotfire-statistica-integration` (4), `tibco-data-science-for-tibco-spotfire-analyst` (6) |
| `stat-sts` | `spotfire-service-for-statistica` (4), `tibco-data-science-service-for-tibco-spotfire` (5) |
| `sfire-cloud` | `tibco-cloud-spotfire-14-6-0` (1), `tibco-cloud-spotfire-14-6-2` (1) |
| `sfire-dscpn` | `tibco-data-science-package-for-notebooks` (2), `tibco-spotfire-data-science-package-for-notebooks` (2) |
| `fsi` | `tibco-fulfillment-subscriber-inventory` (3), `tibco-product-and-service-inventory-2-1-0` (1) |
| `bwpluginedi-healthcare` | `…-plug-in-for-edi` (2), `…-plug-in-for-edi-healthcare-edition` (1) |
| `business-studio-analyst-edition` | `tibco-business-studio-analyst-edition` (4), `tibco-business-studio-for-analysts` (3) |

**The abort is the mild symptom.** The merge loop inserts the first product under the code, merges the second *into* it, and then reads every version unique to the first as deleted. But if the guard is bypassed with `--allow-deletes`, the two products become one row carrying **one** slug — and `_resolve_scope` matches on slug. **`stat-sts` is exactly that case**: `spotfire-service-for-statistica` is on the exclusion list and `tibco-data-science-service-for-tibco-spotfire` is not, so depending on merge order either 4 versions convert that never should, or 5 are dropped that should not be. Phase 3.5 is undermined by a bug one layer beneath it.

**The fix, chosen by the user on 2026-09-10: `slug` becomes the catalog key.** It is unique by construction in the source system (634 products, **0 duplicate slugs, 0 nulls**), stable across rebrands, and already what `scope.yaml` matches on — so the catalog key and the scope key stop being two different things that can disagree. `product_code` is kept as a short descriptive column and is **no longer required to be unique**. Rejected alternative: disambiguating the code with a fallback. It is a smaller change, but which product keeps the short code would depend on a tie-break over version counts, and a code that shifts between fetches reads to the snapshot merge as a new product — trading a loud failure for a quiet one.

- [x] **`Product.slug` becomes required** (`str`, not `str | None`) and the identity field; `product_code` stays as a plain column. A product with no slug is a discovery error, not a catalog row.
- [x] **`products.csv` keyed on `slug`; `versions.csv` joins on `slug`.** Column order puts `slug` first. Both files are currently absent, so there is no migration to write and no user edits to preserve — which is the reason this lands now rather than after the first successful fetch.
- [x] **`state.db`: all six primary keys move from `product_code` to `slug`** (`product_snapshot`, `version_snapshot`, per-version status, metadata, and the per-folder engine map). Schema change only; no database exists yet.
- [x] **Paths take the slug** — `extract_path()` → `…/extracted/<slug>/<version>/`, `download_path()` → `…/downloads/<slug>-<version>.zip`, and the §6.1 publishing segment `{locale}-{bu}-{family}/{locale}/<slug>/{doc-class}/{version-dashed}/`. **This is forced, not preferred**: 9 of the 10 colliding codes also share `bu` and `family`, so a code-named directory collides in the workspace *and* in the published tree. The cost is real and should be seen before it ships — slug length is median 39, p90 60, **max 95** (`premium-subscription-for-tibco-businessworks-container-edition-and-plug-ins-for-aws-marketplace`), against short codes like `ems`. Published AEM URLs inherit it.
- [x] **`--product` keeps resolving either spelling.** It already matches slug or code; with codes non-unique, a code that matches several products must list them and ask rather than pick the first.
- [x] **`validate()` gains a duplicate-slug check** on load. The invariant that just broke silently should fail loudly the next time something threatens it.
- [x] **`_derive_code` is unchanged and keeps its job** — it derives the ZIP-URL folder, which is what it was always right about. What changes is that nothing keys on its answer.
- [x] **Tests.** All 10 collisions become fixtures, `stat-sts` by name as the mixed-scope case (one slug excluded, one not, asserting each resolves independently). Plus: two products sharing a code round-tripping through both CSVs as separate rows; a duplicate slug rejected by `validate()`; `--product` on an ambiguous code; and a re-run of the merge over the full 634-product dump asserting **0 blocked deletions**.
- [x] **Docs in the same commit** — `architecture.md` §3.1/§3.2 (schema and key), §3.10 (scope now matches the key itself), §6.1 (publishing segment); `design.md` §1.5 path derivation, §2.6 code derivation, §3.1 load and join, §12 index; `CONTEXT.md` ledger.
- [x] **One transaction per fetch** (unplanned, found writing the full-dump test). `_record_snapshots` wrapped in a new `StateStore.transaction()`. Recording 634 products and 4,462 versions one `commit()` at a time is ~5,100 fsyncs: the two-merge regression test took **116 s** before and **0.75 s** after. It is also the more correct shape — a merge that dies halfway no longer leaves a partial base, every row of which the next fetch would read as an unflagged manual edit.

**Then re-run the fetch.** The crawl half is already proven — 634 products, 4,462 versions, 0 errors, and 60 of the 61 scope rules matched (845 versions belong to excluded products). The one unmatched rule, `tibco-spotfire-for-apple-ipad`, is the rename detector firing on its first real run and is chased separately.
