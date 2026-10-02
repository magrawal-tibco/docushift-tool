> Archived from `docs/planning.md` on 2026-10-02. Status: **Complete, 2026-10-02**. Kept verbatim; a heading that says *Planned* was built later in this same section.
> Index of every phase: [`docs/planning.md`](../../planning.md#finished-phases).

### Phase 33: The Docsite Already Lists Every Page — **Complete, 2026-10-02**

Phase 22 made the origin URL a per-product declaration because nothing on disk
said where a topic is served today, and a guessed URL is a 404 with a success
line beside it. One product is declared; every other converted product reports
`ORIGIN_TEMPLATE_UNDECLARED` and gets no `301.yml`. The public `sitemap.xml`
does not help — it lists one level, the product landing pages.

**The Coveo search-index sitemap does.** `https://docs.tibco.com/ftp_portal/coveo/sitemap.xml`
is a three-level index, observed 2026-10-02:

| level | file | holds |
|---|---|---|
| root | `coveo/sitemap.xml` | `<sitemapindex>`, ~500 `<sitemap>` entries, one per product, named by the docsite slug — `tibco-enterprise-message-service.xml` |
| product | `coveo/{slug}.xml` | `<sitemapindex>`, one entry per version — `tibco-enterprise-message-service-10-5-1.xml` (EMS: 7, including 10.3.0) |
| version | `coveo/{slug}-{version_dashed}.xml` | `<urlset>`; per page a `<loc>` (the live URL) and `<coveo:metadata>` with `d_name` (title), `productversion`, `access_level`, `name` |

The EMS 10.5.1 file carries `https://docs.tibco.com/pub/ems/10.5.1/doc/html/_shared/about-this-product.htm`
titled "About this Product" — **the exact URL Phase 22 verified by hand**. The file
names use the catalog's own slug and dashed version, which are the keys
`versions.csv` already has.

Quirks seen in the first pass, each of which the parser has to survive rather
than trip on: a mojibake entry (`tibco-spotfireâ-server.xml`), a duplicate
(`tibco-foresight-translator.xml` twice), a placeholder (`no_id_mentioned.xml`),
an unencoded space in a `loc` (`MicroContent/Resources/MicroContent/API Activity/…`),
`.html` beside `.htm` (API reference), and product files listing their versions
out of order.

**Not yet measured** — the files were read through a summarising fetch, not
downloaded, so the numbers that decide the design are still open: whether a
version file lists every converted topic (EMS 10.5.1's `output_map` has 1,437
rows) or only what the search index chose to crawl; what `access_level` values
exist; and how many in-scope versions have a file at all. Step 1 below produces
those numbers before any join is written.

#### Decisions

| decision | what gets built | why not the obvious alternative |
|---|---|---|
| **The sitemap is fetched and cached, not read live** | `docushift catalog sitemap [--product X]` walks root → product → version files, stores the raw XML under `cache/coveo/`, and skips a file whose `lastmod` in its parent is unchanged | `validate` and `reframe` take no network today and must keep not taking it. A cache also makes a run reproducible: the 301 map is a function of files on disk. |
| **Child file names are read, never composed** | Version files are found by following the product file's `<loc>` entries, then matched to `versions.csv` by the `{slug}-{version_dashed}` stem | Composing `{slug}-{version_dashed}.xml` would be right until the first product whose file is named otherwise, and the miss would read as "no pages". The duplicate and mojibake entries above are why. |
| **The sitemap derives a template, per version, by agreement** | For each version, every `output_map` source path is tried against the sitemap's paths under `/pub/{folder_path}/` with 0–3 leading segments dropped and an optional served prefix (`doc/`); the one mapping that matches the most rows wins **only if** it matches ≥ 90% of the sitemap-listed `.htm`/`.html` pages and no rival comes within 10 points | This is what replaces "declared by a human" without becoming "guessed": the four layouts in Phase 22 are each a different mapping, and the sitemap is what picks between them. Per-row suffix matching was rejected — `index.htm` and `Default.htm` match in every subtree. |
| **Every row is checked against the list** | A row is written only if its URL is in that version's sitemap. Rows not listed are counted, not written | A derived template that is right for 99% of rows is still wrong for the 1%; the list is the per-row proof Phase 22 got from a hand check. |
| **`origin-urls.yaml` stays, and wins** | A declared template overrides derivation, and is itself checked against the sitemap; disagreement is a finding | EMS keeps working exactly as it does, and it becomes the regression test: the derived mapping must equal the declared one in all six versions. It is also the escape hatch for a product the sitemap gets wrong. |
| **Three new codes, register 63 → 66** | `ORIGIN_SITEMAP_MISSING` (warn: no version file for this version), `ORIGIN_URL_UNLISTED` (info, counted per version: a converted topic whose URL the sitemap does not list), `ORIGIN_PAGE_UNMAPPED` (warn, counted: a listed live page no converted topic produced — a reader there gets a 404 at cutover) | `ORIGIN_TEMPLATE_UNDECLARED` stays for the case where neither a declaration nor an agreeing derivation exists. The third code is new information Phase 22 could not produce at all: the live pages the map does *not* cover. |
| **`d_name` is a cross-check, not an input** | The sitemap title against the converted page's title, mismatches counted in the run report | Cheap evidence that a row joins the right two pages; never used to choose a mapping, because titles repeat ("Overview"). |

#### Steps

1. **Fetch and measure** (no join yet). `catalog sitemap` for all in-scope products; report per version: file present, page count, `access_level` values, and for converted versions the overlap with `output_map`. *This is the step that can change the design* — if coverage is low, the 90% threshold and the "write only listed rows" rule are revisited with you before step 2.
2. **Derive and join** in `origins.py`, called from `reframe/driver._write_origins` as today; the cache is read, never fetched, inside `reframe`.
3. **Re-run the converted catalog**, compare EMS's `301.yml` byte-for-byte with Phase 22's, and record per product: derived / declared / undeclared, rows written, unlisted, unmapped.

#### Step 1 — **Built & measured, 2026-10-02**

`discovery/sitemap.py` (parse, cache, walk), `DocsiteClient.get_bytes`, `docushift catalog sitemap`, `reports/coveo-sitemap.csv`. The walk took ~20 minutes at the 2 req/s floor; a re-run reuses every file whose `lastmod` is unchanged.

| measured | result |
|---|---|
| Product files | **288 of 604** in-scope products have one; 20 are absent from the root; the rest answer with the portal **login page** |
| Login page as HTTP 200 | **297 files**. Detected (`<!doctype html` / `<html`), counted as `not_served`, never cached — a cached one crashed every later read |
| Catalog versions with a page list | **1,731 of 4,208**. Every active version that has one; **no archived version has one** |
| Leaf matched by version suffix | **314** of the 1,731 — a renamed product keeps its old name on old leaves (`tibco-streaming.xml` lists `spotfire-streaming-11-1-0`). **All 314 agree with the leaf's own `productversion`**; the one exact-stem leaf that does not carries a blank `productversion` |
| `access_level` | `Public` on every leaf |
| Converted versions with a leaf | **28 of 44**. The 16 without: 6 are DataSynapse products now out of scope; 10 are three in-scope products with no product file at all (Designer Add-in ×8, PeopleSoft adapter, Silver Fabric Enabler) |
| `output_map` coverage by the best mapping | **27 of 28 at 100%**; Streaming 11.1.3 at 1,186/1,187 — the miss is a release-notes page (`dochome/sb-110102-rn-final.html`) the index does not list |
| Rival mapping within 10 points | **0 of 28** |
| Phase 22's layouts | EMS, Streaming, ActiveSpaces, Administrator: drop 1 under `/pub/{folder}/doc`. **Runtime Agent** 5.12.x: drop 1 under `…/doc/html` (the `designerhelp` case), 5.13.0 under `…/doc`. **Data Science Author**: drop 0 (no package root). All derived, none declared |
| Listed but not converted | EMS 10.5.1: 680 of 2,117 — 666 API reference (`api/dotnetdoc`, `api/javadoc`), help-system frames, 3 PDFs. The `ORIGIN_PAGE_UNMAPPED` population |

**Quirks, each now handled or recorded.** The leaves declare their default namespace as `…/sitemap/0.9/sitemap.xsd`, so elements are matched on local name. Three entries point at `http://localhost:5001/…` — a development host leaked into the live index — and fail as connection errors; they are not rewritten. `tibco-loglogic.xml` is a `<urlset>` at product level, with no version files under it — one product, recorded, not special-cased. A Windows scanner lost the `manifest.json` rename once (`WinError 32`); `utils/swap.replace_file` retries it.

**What step 1 changes in step 2.** Three adjustments to the decisions above, none to their direction:

- **Mappings that produce the same URLs are one mapping.** In every EMS version, "drop 1 under `…/doc`" and "drop 2 under `…/doc/html`" tie exactly, because they are the same URL. Ranking groups candidates by the URL set they produce, and the rival rule compares groups.
- **The threshold is on `output_map`, not on the leaf.** The leaf carries API reference and PDFs this tool does not convert (680 of 2,117 for EMS), so "≥ 90% of the sitemap's pages" would reject every product with an API reference. The rule becomes: the winning mapping covers ≥ 90% of the version's `output_map`, and no other group is within 10 points.
- **Leaves are matched by version suffix** (`sitemap.match_leaf`), exact stem first, unique suffix otherwise, and never across a numeric segment.

#### Steps 2–3 — **Built & verified, 2026-10-02**

`origins.derive` / `listed` / `unmapped` / `page_path`, called from `reframe/driver._write_origins`, which reads `cache/coveo/` and never fetches. A declaration still wins and writes every row; a derived template writes only listed rows. Register **63 → 66**: `ORIGIN_SITEMAP_MISSING` (warning), `ORIGIN_URL_UNLISTED` (note), `ORIGIN_PAGE_UNMAPPED` (warning). One refinement found while testing: a candidate group whose URLs are a **subset** of the winner's (`c.htm` matched again under `…/API Activity` at a deeper drop) is the same answer, not a rival, and is skipped when the runner-up is counted.

`reframe --all --force` over the converted catalog — Reframe runs for Flare only, so 14 versions:

| product | versions | source | rows written | unlisted | unmapped (listed, not converted) |
|---|---|---|---|---|---|
| EMS | 6 | declared | 8,613 | 0 | 669–681 per version (API reference, readme, PDFs) |
| ActiveSpaces | 6 | **derived** | 1,922 | 0 | 132–133 per version |
| Administrator 5.13.0 | 1 | **derived** | 423 | 0 | 12 |
| Runtime Agent 5.13.0 | 1 | **derived** | 643 | 0 | 26 |

| exit criterion | result |
|---|---|
| EMS `301.yml` byte-identical to Phase 22's | **6 of 6** |
| Derived mapping equals the declared one (EMS, declaration ignored) | **6 of 6**, same template, drop 1, identical rows, 0 rivals |
| Every derived `from` is in its sitemap | **yes** — 0 unlisted in 8 derived versions |
| Derived URLs live, three non-EMS layouts | **6 of 6** fetched pages (two each from ActiveSpaces, Administrator, Runtime Agent's `designerhelp`/`trahelp`) |
| `validate` over the three families synced to a scratch target | exit 0, 0 errors; **0 findings from any `301.yml`** — the 645 warnings are pre-existing `ANCHOR_MISSING` and `redirects.yml` case-only `REDIRECT_SHADOWED` |
| Full suite | **1,709 pass**, 2 skipped, lint clean |

**Deviations.** The `d_name` title cross-check is **deferred**: nothing in the measurement called for it (0 unlisted rows, 0 rivals), and it would be a fifth code with no observed case. **Not reached by this phase:** the non-Flare converted versions (Streaming, Data Science Author, Runtime Agent 5.12.x) — `301.yml` is written by Reframe, which skips them; their mappings derive cleanly in step 1's measurement, so moving the write is a decision for a later phase, not a design question.

*Exit: EMS's six `301.yml` files are byte-identical to Phase 22's; the derived mapping equals the declared one in all six versions; every other converted product either gets a `301.yml` whose every `from` appears in its sitemap, or is named with one of the four codes; a sample of derived URLs from three non-EMS layouts is confirmed live by hand; `validate` adds no findings.*
