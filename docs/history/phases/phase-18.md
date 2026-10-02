> Archived from `docs/planning.md` on 2026-10-02. Status: **Built (18c–18d), 2026-09-23**. Kept verbatim; a heading that says *Planned* was built later in this same section.
> Index of every phase: [`docs/planning.md`](../../planning.md#finished-phases).

### Phase 18: A Parent Product Publishes No Versions of Its Own — **Planned, 2026-09-22**

The `streaming` family ran `download` 20/24, `extract` 20/20, and then `convert` **converted 2 of 24**: 4 `NO_TREE`, 18 `ENGINE_UNKNOWN`, 0 failed. Seventeen of the eighteen are the correct outcome and not a defect — those trees hold no HTML at all. `tibco-enterprise-streaming@11.2.1` is four files: a readme, a ReminderNotice, an RTU, and a licence PDF.

That is not a broken package. It is the wrong product.

| | `tibco-enterprise-streaming` | `tibco-streaming` |
|---|---|---|
| docsite id | 9042 | 4943 |
| `product_code` | `platform-tp-stream` | `str` |
| API shape | `isChildProduct: true` | `isParentProduct: true` |
| versions | 4 | **22** |
| package | readme + licence, 0.2 MB | the help |
| in `config/products.csv` | yes | **no** |

`tibco-enterprise-streaming` is a **licence bundle**. Its own API `description` says so: *"Click on the links below to access Documentation for the included Suite Components."* The catalog has the bundle and has never had the product.

#### 18a. The crawler drops every parent product, silently

`/api/products/{slug}` returns two shapes, and `discovery/crawler.py` handles one. The module docstring (`crawler.py:14-17`) describes the child shape correctly — the detail object *is* the current version, carrying `version_no` and `folder_path`, with the rest in `siblings`. A **parent** returns neither:

```
spotfire-application               parent=False child=True  ver='15.0.0'  folder='sfire-analyst/15.0.0'  siblings=True
tibco-streaming                    parent=True  child=None  ver=None      folder=''                      siblings=absent
tibco-flogo                        parent=True  child=None  ver=None      folder=''                      siblings=absent
tibco-activematrix-businessworks   parent=True  child=None  ver=None      folder=''                      siblings=absent
ibi-webfocus-client                parent=True  child=None  ver=None      folder=''                      siblings=absent
```

So at `crawler.py:236-239` the `_first(r, _VERSION_KEYS)` filter empties `records`, `_build_product` returns `None`, and the product is gone. `a_to_z` advertises `versionCount: 22` for `tibco-streaming` and the catalog ends up with nothing.

*(Corrected 2026-09-22: an earlier draft of this paragraph said "no error, no count, no line in the report". The count exists — `discover()` does `result.unversioned += 1` at `crawler.py:152`, and `cli.py:238-241` prints "Skipped N entries with no published versions and M that are not publicly visible." The defect is not silence, it is **misattribution**. `unversioned` is documented as the licence-page and connector-stub bucket, so a product with 22 published versions lands in a tally whose name says it has none, next to entries for which that is true. Nothing cross-checks the bucket against the `versionCount` `a_to_z` already returned for every slug in it, which is why a 22-version product could sit in a printed number for twelve days without anyone reading it as a fault. Item 3 of 18d is unchanged by this correction — it is about naming and cross-checking the drop, not about creating a counter that already exists.)*

The versions are one slug away. `/api/products/tibco-streaming-11-2-1` returns `version_no: '11.2.1'`, `folder_path: 'str/11.2.1'`, and **21 siblings** — 22 total, matching `versionCount` exactly. Fed to the existing `active_template` that yields:

```
/pub/{folder_path}/{slug}-{version_dashed}_documentation.zip
  -> https://docs.tibco.com/pub/str/11.2.1/tibco-streaming-11-2-1_documentation.zip
```

**The template is not wrong and `docsite.yaml` does not change.** Discovery never got far enough to use it.

#### 18b. Blast radius: 35 products, 707 versions

Live `a_to_z` against `config/products.csv`: 738 entries, 636 catalog rows. 69 of the missing carry `isPublicLevel: false` and are dropped on purpose (`crawler.py:170-172`). That leaves **35 public, versioned products absent from the catalog, carrying 707 versions**:

| versions | slug | | versions | slug |
|---:|---|---|---:|---|
| 99 | `spotfire-application` | | 16 | `tibco-bpm-enterprise` |
| 49 | `tibco-flogo` | | 14 | `tibco-product-and-service-catalog` |
| 47 | `tibco-activespaces-enterprise-edition` | | 14 | `tibco-mdm` |
| 45 | `tibco-activematrix-businessworks` | | 14 | `tibco-foresight-studio` |
| 39 | `ibi-webfocus-reporting-server` | | 11 | `spotfire-statistica` |
| 39 | `ibi-webfocus-client` | | 10 | `tibco-businessconnect-container-edition` |
| 38 | `ibi-webfocus-app-studio` | | 9 | `tibco-activematrix-service-grid` |
| 36 | `ibi-webfocus-installer` | | 8 | `tibco-foresight-hipaa-validator-desktop` |
| 32 | `tibco-businessevents-enterprise-edition` | | 8 | `ibi-iway-service-manager` |
| 26 | `tibco-data-virtualization` | | 7 | `tibco-messaging-enterprise-edition` |
| 26 | `ibi-focus` | | 5 | `ibi-omni-gen-mdm` |
| 25 | `tibco-operational-intelligence-hawk-redtail` | | 5 | `ibi-omni-gen` |
| 22 | `tibco-streaming` | | 4 | `ibi-omni-healthdata` |
| 18 | `tibco-businessconnect` | | 3 | `tibco-offer-and-price-engine` |
| 16 | `tibco-order-management` | | 2 | `tibco-activematrix-service-grid-container-edition` |
| 16 | `tibco-foresight-instream` | | 1 | 4 more |

*(Written when the parent-product mechanism was verified on 4 of the 35 and `spotfire-application` was an unexplained second cause. Both are resolved in 18d below: 34 of the 35 are parent products and the 35th is a distinct dedup defect. The table stands as the measured gap.)*

#### 18c. Interim: pin `tibco-streaming` by hand — **Built, 2026-09-22**

The catalog is CSV so that this is possible (`architecture.md` §3.1). Adding the product does not wait on 18d.

One row in `config/products.csv`:

```
tibco-streaming,str,TIBCO® Streaming,tibco,streaming,manual,true,default,true
```

Six rows in `config/versions.csv` — every **active** version, each with the `active_template` URL written out. *(Planned as `zip_source=manual`; shipped as `auto` — see the correction below.)*

| version | `folder_path` | release |
|---|---|---|
| 11.2.1 | `str/11.2.1` | 2025-10-23 |
| 11.2.0 | `str/11.2.0` | 2025-06-13 |
| 11.1.3 | `str/11.1.3` | 2026-03-25 |
| 11.1.2 | `str/11.1.2` | 2025-11-20 |
| 11.1.1 | `str/11.1.1` | 2024-10-04 |
| 11.1.0 | `str/11.1.0` | 2023-11-16 |

The other 16 (11.0.1 down to 10.4.0) are archived, so `convert_eligible=false` by the 2026-09-02 archive policy, and their real `zipPath` comes from `/api/products/archive/tibco-streaming` rather than from a template — the last seven carry the stale `folder_path: 'str'` the crawler docstring warns about. **They are deferred to 18d**, where the archive index is read the way it is read for every other product.

Durability is the point of the exercise, and two mechanisms carry it:

* `custom_override=true` on the product row is a **whole-row pin** — `_merge_product` returns before reading a single upstream field (`catalog.py:629-631`). A `catalog fetch` that still cannot see this product cannot damage it.
* `family_source=manual` pins the family, per the provenance table in the `propagate-catalog-edit` skill. `family` needs it most: it resolves by provenance **rank**, not by snapshot diff, so a `taxonomy_rule` value would survive only as long as `state.db` holds a snapshot. ~~`zip_source=manual`~~ — wrong, and corrected below.

`catalog fetch` does not delete versions discovery stops returning unless `--allow-deletes` is passed, so the rows are safe from an ordinary fetch even before the pin.

Then `download` → `extract` → `convert` over `--product tibco-streaming`. The engine is whatever the detector says; `tibco-streaming` is the StreamBase documentation set and no prediction is recorded here.

##### 18c shipped with two corrections to the plan above, both about `zip_source`

**`zip_source=manual` does not mean "a human set the URL". It means "a human places the package; never fetch this row."** `download_one` returns `SKIPPED_MANUAL` before it resolves anything (`fetcher.py:214-215`), ahead of `--force`. Writing the six rows as `manual` — which the plan did, following the provenance table in the `propagate-catalog-edit` skill — would have made all six undownloadable. `catalog import` said so immediately, twice per row. The rows were corrected to `zip_source=auto` via `catalog set`.

**And the `zip_url` column is not read for an active row at all.** `_resolve_url` derives the endpoint from `_folder_path` + `active_zip_url` and trusts the stored column only when the row is archived or manually pinned (`fetcher.py:150-171`) — a deliberate choice from 2026-09-19, when discovery's template was wrong for the whole corpus. So the six URLs written into the CSV are documentation, not mechanism. What actually makes the download work is `product_code=str`: `_folder_path` falls back to `f"{code}/{version}"` → `str/11.2.1`, which is the correct folder, so the derivation lands on the right URL with no `state.db` metadata to seed it.

The durable pin is therefore `custom_override=true` alone, on the product row and on all six version rows. That is the mechanism the skill's table does not cover, and it is the one that matters here.

##### The `spotfire-` era is real, and it explains the four `sb-hp-fix` failures too

`download` fetched 4 of 6 — 11.2.1, 11.2.0, 11.1.3, 11.1.2, 400.6 MiB. **11.1.1 and 11.1.0 failed** with the same empty-200 as the `sb-hp-fix` rows. The predecessor's manifest records their doc URLs as `docs.tibco.com/products/spotfire-streaming-11-1-1` — a rebrand window — and a ranged probe settles it:

| URL | status | first 4 bytes |
|---|---|---|
| `/pub/str/11.1.1/tibco-streaming-11-1-1_documentation.zip` | 200 | *empty body* |
| `/pub/str/11.1.1/spotfire-streaming-11-1-1_documentation.zip` | **206** | **`PK\x03\x04`** |

Same for 11.1.0. The `finalSlug` in the filename is the display name **as it was at that release**, not as it is now — so `active_template` is correct in form and wrong in input for every product that was rebranded mid-life. Both packages were fetched by hand and filed with `download --from-file`, which pins `zip_source=manual` for exactly the reason that flag exists. Their extracted wrappers are named `spotfire-streaming-11-1-1/`, which is the rebrand visible on disk.

This is the cause of 18d's item 4 as well, now confirmed rather than suspected: the four `tibco-streambase-high-performance-fix-engine` failures are the same window and will need the same stem.

##### Acceptance

`download` 4/6 fetched + 2 filed by hand, `extract` **6/6, all six detected `docbook`**, `convert` **6/6 with 0 failed, 0 `ENGINE_UNKNOWN`, 0 `NO_TREE`** — 7,071 topics, 8,178 assets, 15,261 output files.

| version | topics | nav nodes | out files | resolved | dangling | orphan |
|---|---:|---:|---:|---:|---:|---:|
| 11.2.1 | 1,196 | 3,384 | 2,566 | 2,118 | 0 | 1,272 (40.3 MB) |
| 11.2.0 | 1,191 | 3,362 | 2,534 | 2,118 | 0 | 1,272 (40.3 MB) |
| 11.1.3 | 1,187 | 3,341 | 2,555 | 2,127 | 1 | 1,155 (33.4 MB) |
| 11.1.2 | 1,182 | 3,319 | 2,550 | 2,127 | 1 | 1,155 (33.4 MB) |
| 11.1.1 | 1,179 | 3,301 | 2,547 | 2,125 | 1 | 1,155 (33.5 MB) |
| 11.1.0 | 1,171 | 3,268 | 2,537 | 2,119 | 0 | 1,153 (33.5 MB) |

0 skin, 0 escaped, 0 case-mismatch throughout. Findings: **3 errors, 30 notes** — the three errors are one `REFERENCE_UNRESOLVED` apiece in 11.1.3, 11.1.2 and 11.1.1, the same single dangling reference `spotfire-data-streams@11.1.1` carries. Each version skips ~850–1,010 `foreign-generator` and ~1,477 `not-docbook` files, and the orphan block is the `html/apidocs/` Javadoc tree the extractor flags as having no known generator marker (2,530–2,829 files per version).

**`validate` has not been run against this family** — `sync` has not been run either, so there is no published tree to walk. The conversion is measured; the publication is not.

**What 18c does not do.** It does not touch the bundle rows. `tibco-enterprise-streaming` and `tibco-enterprise-streaming-high-performance-fix-engine` stay `convert_eligible=true` and will keep reporting `ENGINE_UNKNOWN` on every run, because turning them off is a policy question about how the catalog should represent a licence bundle that publishes a licence — and answering it for two rows in the `streaming` family, when 18b says there are more bundles behind the other 34 products, would be setting precedent from the smallest possible sample.

#### 18d. The crawler fix — **Built, 2026-09-23**

18d's blocking question was *"how is the child slug obtained?"* — `a_to_z` gives a `versionCount` but no version list, and a parent detail gives no children, so `{slug}-{version_dashed}` needed a version nobody had. **Mayur supplied the answer: append `-latest`.** `/api/products/{slug}-latest` returns the ordinary child shape, and its `siblings` array is the version drop-down.

##### The `-latest` fallback resolves the whole parent-product class

Probed against every one of the 35 missing products:

| | |
|---|---|
| `-latest` returns a child shape | **34 of 34 parent products** |
| sibling count matches `a_to_z` `versionCount` | **34 of 34, exactly** |
| versions recovered | **685** |

```
tibco-streaming-latest                   11.2.1   str/11.2.1                      21 siblings  (22 = versionCount)
tibco-flogo-latest                        3.0.0   flogo/3.0.0                     48 siblings  (49)
tibco-activematrix-businessworks-latest   6.13.0  activematrix_businessworks/6.13.0  44 siblings  (45)
ibi-webfocus-client-latest                9.3.8   wf-wf/9.3.8                     38 siblings  (39)
```

The exact match on all 34 is the load-bearing result: it says `-latest`'s siblings are the *complete* version set, not a recent window, so the fallback needs no pagination and no second call.

Two cautions the probe turned up. **`-latest` is a slug suffix, not a URL suffix** — the user's list is of `/products/...` page paths, and `/products/tibco-webfocus-client` is a page whose API slug is `ibi-webfocus-client`; `tibco-webfocus-client-latest` errors. The fallback must be driven by the slug `a_to_z` returns, never by a hand-kept list. And the user counted ~20 custom pages; `a_to_z` says **34**. The list is a sample, so the fallback is applied to every parent, not to an allow-list.

##### `spotfire-application` is a different defect: first-wins dedup lets a non-public twin shadow a public product

The 35th product is not a parent — `/api/products/spotfire-application` returns a perfectly good child shape with 98 siblings. It never gets requested. `a_to_z` returns **two records under that one slug**:

| id | `isPublicLevel` | `isOnlyForAdmin` | `versionCount` |
|---|---|---|---:|
| 8862 | `False` | `True` | 1 |
| 2452 | `True` | `False` | **99** |

and `_list_products` (`crawler.py:178-186`) dedups **first-wins**, adding the slug to `seen` *before* it applies the visibility filter:

```python
if not slug or slug in seen:
    continue
seen.add(slug)                      # the admin stub claims the slug here
public = _present(record, _PUBLIC_KEYS)
if public is not None and not record[public]:
    result.non_public += 1          # ...and is then dropped as non-public
    continue
```

The admin-only stub arrives first, consumes the slug, and is discarded. The real 99-version product is then skipped as a duplicate. `discover(selectors=['spotfire-application'])` returns `products: 0, unversioned: 0, non_public: 70` — it never reaches `_build_product` at all, which is why 18b could not explain it as a parent.

This is **the only duplicated slug in `a_to_z`** (739 records, 738 distinct slugs), so the fix reaches exactly one product.

##### …and those 99 versions are out of scope, which is the actual finding

`spotfire-application` is `folder_path: 'sfire-analyst/15.0.0'` — **Spotfire Analyst itself**, the core client, beside `spotfire`, `spotfire-desktop` and `spotfire-server`, all three of which `config/scope.yaml` already excludes. Not one of its 99 versions would ever be converted. *(An earlier draft of this phase counted them as recovered yield. They are not yield.)*

The defect is therefore not the missing versions. It is that **`config/scope.yaml` does not exclude it.** The file excludes 61 products and deliberately leaves 16 public `spotfire*` slugs in scope — its header names the Data Science and Statistica lines, and Mayur's custom-page list includes `spotfire-statistica`, so that policy is intact. But `spotfire-application` is in that in-scope 16 **only because the dedup bug hid it when the list was compiled on 2026-09-09.** It was never a candidate for exclusion because nobody could see it.

So the standing state is: *99 versions of Spotfire Analyst are out of scope by intent, in scope by configuration, and protected from download by nothing but a bug.* The record ordering that hides it belongs to the API, not to us.

The two changes have to ship together. `scope.yaml` reports rules that match no product (`catalog.py:547`, `997-998`), so adding the entry while the product stays undiscoverable leaves a rule that warns on every fetch — and that warning exists to flag an upstream rename, so one that never clears is worse than no warning. Fixing the dedup makes the product discoverable, the rule match, and the exclusion behave exactly like the other 61: **catalogued, counted, never converted.** The dedup is also worth correcting as a rule rather than as a special case, because a visibility filter that runs *after* the dedup it depends on will reproduce this the next time the API duplicates a slug.

##### What gets built

1. **Parent fallback.** When `_build_product` finds no versioned record, re-request `{slug}-latest` before returning `None`, and build from that detail plus its siblings. One extra call per parent, ~34 per full crawl.
2. **Dedup after visibility, and prefer the public record.** Group `a_to_z` by slug, drop non-public records first, and only then dedup — so `non_public` counts a slug only when *every* record for it is non-public.
3. **Exclude `spotfire-application` in `config/scope.yaml`**, in the same change as 2 and for the reason above. Reason string matching the existing Spotfire entries; `display_name: "Spotfire® Application"` as documentation, since the file matches on `slug` by string equality only.
4. **Name the drop and cross-check it.** Keep `unversioned` but split out the products `a_to_z` claims have versions: a product with `versionCount > 0` that yields none is a defect, not a licence page, and belongs on its own report line with its slugs named. This is the guard that would have caught 18a on 2026-09-10; per the correction in 18a the counter already exists, so this is a naming and cross-check change, not a new tally.

##### Acceptance

A full `catalog fetch` adds **34 products / 685 versions** by the parent fallback, and the new defect line reads zero afterwards. `tibco-streaming` arrives from discovery with all 22 versions — matching the six rows 18c pinned by hand, which is the check that the fallback and the hand-pin agree. The 18c rows keep `custom_override=true` and must survive the fetch unchanged.

`spotfire-application` arrives as the 35th product with 99 versions and is **immediately out of scope**: `in_scope=false`, `scope_source=scope_rule`, zero versions download-eligible, and `scope_rules_unmatched` does **not** name it — the rule matching is the proof the dedup fix worked. Its 99 rows are inventory, not yield; the 62 `scope.yaml` rules must still match 62 products with none unmatched.

##### Shipped 2026-09-23 — and the gap closed exactly

`catalog fetch --all --include-archived` against the live docsite:

| | before | after |
|---|---:|---:|
| products in `config/products.csv` | 637 | **669** |
| versions in `config/versions.csv` | 4,480 | **5,181** |
| public A-to-Z slugs **not** in the catalog | 33 | **2** |
| products `in_scope=false` | 60 | **61** |

**669 public A-to-Z slugs, 669 catalog products.** 32 products added (0 removed), carrying 683 versions; the other 18 of the +701 are archived versions topped up onto products already present, `tibco-streaming`'s 16 among them. The largest arrivals are `spotfire-application` 99, `tibco-flogo` 49, `tibco-activespaces-enterprise-edition` 47, `tibco-activematrix-businessworks` 45 and the four `ibi-webfocus-*` at 152 between them.

**`tibco-streaming` now arrives from discovery with all 22 versions, and 18c's hand-pinned rows survived intact** — `custom_override=true` on the product row and on all six, `family_source=manual` held, `zip_source` untouched (`manual` on the two hand-filed 11.1.x packages, `auto` on the other four), and the 16 archived versions arrived `is_archived=true, convert_eligible=false`. That is the check the phase was built around: the fallback and the hand-pin independently produce the same 22 versions, and the merge protected the hand-pin rather than overwriting it.

**`spotfire-application` landed exactly as intended:** `in_scope=false`, `scope_source=scope_rule`, `product_code=sfire-analyst`, 99 versions catalogued and none of them ever selectable.

##### Two corrections to the acceptance criteria above

**"34 products / 685 versions" was wrong, in a way worth recording.** The real figure is 32 new products and 683 versions from them. Two of the 34 parents were never going to become new products: `tibco-streaming` was already in the catalog from 18c, so recovering it adds versions rather than a product — and the 685 count was taken by summing `-latest` sibling lists without checking that each sibling carries a usable version number. It counted records, and two of them are blank.

**"the new defect line reads zero" was also wrong, and the line is right.** It names **two** products, and both are real:

| slug | `versionCount` | what `-latest` actually returns |
|---|---:|---|
| `ibi` | 1 | `version_no: ''`, `folder_path: 'ibi'`, 0 siblings, **67 Documents** |
| `tibco-spotfire-for-apple-ipad` | 1 | `version_no: null`, `folder_path: null`, 0 siblings, 0 documents |

Neither is a crawler defect. Both are landing pages the docsite counts as having one version while publishing no version number for it — `ibi` is a documents hub, and the iPad product is already excluded by `scope.yaml` (and is the one rule that was *already* unmatched before this phase, now explained). The line is doing precisely the job 18a's correction defined for it: surfacing a disagreement between what the index claims and what discovery can read, by name, for a human to judge. Reporting two products a reader can resolve in one look is the intended output, not a failure of the fix.

`scope_rules_unmatched` therefore still names `tibco-spotfire-for-apple-ipad` — 62 rules, 61 matched. Unchanged by this phase and not caused by it.

##### Acceptance, measured

The catalog growth moved the end-of-support guard for the first time — `versions_retired` 128 → **139**, `eos_coverage` (253, 637) → **(270, 669)** — and the reading is still *population, not verdict*, on better evidence than the count:

* **Not one of the 4,480 pre-existing version rows changed `release_status` or `convert_eligible`.** The merge was purely additive.
* All 173 newly retired rows sit on products this fetch added, led by `tibco-activematrix-businessworks` (38) and `tibco-businessevents-enterprise-edition` (26).
* `products_fully_retired` is **unmoved at 11**, and it is the same 11 — nothing newly discovered is retired in its entirety.

Support's report is judging products it previously could not see; its verdict on everything it had already judged is untouched. Re-baselined with that written into the test.

**1,341 tests pass (+7), 2 skipped, lint clean.** The seven new tests cover the fallback path, its cost (a product with a child shape never asks for `-latest`), version keying onto the parent slug, the archived-sibling URL rule surviving the fallback, a parent whose `-latest` does not resolve being named rather than swallowed, a genuinely unversioned entry staying out of the defect bucket, and both duplicate-slug directions. `test_shipped_scope_lists_the_ebx_and_spotfire_products` was re-baselined 61 → 62 with the reason written into the test.

##### Still deferred

1. The **16 archived `tibco-streaming` versions**, which need `/api/products/archive/{slug}` rather than a template.
2. The two `streaming` bundle rows left `convert_eligible=true` (see "What 18c does not do").
3. **Not in this phase, and no longer a hypothesis:** `tibco-streambase-high-performance-fix-engine` 11.1.1, 11.1.0, 10.6.6 and 10.6.5 are active with correct `sb-hp-fix/<version>` folder paths whose templated URLs return an empty body under HTTP 200 — the four `NO_TREE` rows in the streaming run. 18c **proved the mechanism** on `tibco-streaming` 11.1.1 and 11.1.0: the `finalSlug` in the filename is the product's display name *at that release*, and both resolve under a `spotfire-` stem. `active_template` needs a per-version stem, not the catalog's current slug. A filename-derivation defect, independent of the parent-product shape, and it gets its own phase rather than being absorbed into this one.

---
