> Archived from `docs/planning.md` on 2026-10-02. Status: **Complete, 2026-09-09**. Kept verbatim; a heading that says *Planned* was built later in this same section.
> Index of every phase: [`docs/planning.md`](../../planning.md#finished-phases).

### Phase 3: Docsite Discovery Engine (`docs.tibco.com` API Client) — COMPLETE
`catalog fetch` is wired end to end and verified against the live docsite (2026-09-03): a scoped fetch of `tibco-enterprise-message-service` returns 33 versions, and the generated ZIP URLs answer HTTP 200 for both active and archived releases.
- [x] API client (`discovery/client.py`) for `/api/a_to_z`, `/api/products/{slug}`, `/api/products/archive/{slug}`, `/api/bu_category_products`, `/api/product_list_by_suites` — endpoints, templates and politeness read from `docsite.yaml`, urllib3 `Retry` on 429/5xx, and a hard minimum interval between requests rather than a token bucket.
- [x] Automated ZIP URL generator: `/pub/{folder_path}/doc/zip/tib_{folder_slug}_doc.zip` for active versions, the archive index's `zipPath` verbatim for archived ones.
- [x] Crawler (`discovery/crawler.py`) mapping payloads to `Product` records, **written against the API's verified real shape** (`architecture.md` §2.1): a `{"result": {"product": …}}` envelope, the detail object doubling as the current version with the rest under `siblings`, and `isArchive` splitting active from archived.
- [x] Category ingestion as an **advisory** family hint only — it may only promote `unclassified` rows, and a failure to reach it degrades triage rather than the crawl.
- [x] Partial-failure policy: an unreachable product is **excluded** from the result rather than returned empty, so a half-finished crawl can never trip deletion detection.
- [x] Pre-request filtering of the 70 (of 739) A-to-Z entries the docsite marks not publicly visible, which otherwise answer with an SSO page as HTTP 200.
- [x] `catalog fetch` wired to `CatalogManager.merge_fetch_results()` with `--allow-deletes`, `--dry-run`, a required scope, and `--product`/`--batch` resolved to crawl selectors so a three-product batch is three requests rather than 668.
- [x] Docsite ids and folder paths recorded in `state.db`, not in the CSVs.
- [x] **`zip_source` column** (`auto` | `manual`) in `versions.csv` — the catalog half of manually supplied packages (`architecture.md` §3.8). Landed here rather than in Phase 4 because the merge rule has to exist *before* the first real fetch runs, or a fetch could overwrite a hand-supplied row:
  - [x] `ProductVersion.zip_source` + `VERSION_COLUMNS` + round-trip; `catalog set --zip-source`.
  - [x] Excluded from `_MERGEABLE_VERSION_FIELDS` and from `version_snapshot`, alongside the engine columns and `convert_batch`. `zip_url` itself stays merged.
  - [x] `validate()`: exempt `zip_source=manual` from the *convert-eligible with no `zip_url`* problem.
  - [x] `warnings()`: flag `manual` rows that discovery has since found a `zip_url` for.
- [x] Unit & mock tests in `tests/unit/test_discovery.py` (38), plus `catalog fetch` wiring tests in `test_cli.py`. No network: a fake session serves payloads shaped like the real responses.
