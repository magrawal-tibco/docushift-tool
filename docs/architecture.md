# DocuShift Architecture Document: End-to-End Documentation Migration Engine

> **Document Status:** Living Architecture Specification  
> **Last Updated:** 2026-09-03  
> **Scope:** ~250 Products across TIBCO & IBI BUs  
> **Source:** `docs.tibco.com` (Active & Archived Versions)  
> **Target:** AEM-Ready GitHub-Flavored Markdown Repositories

---

## 1. End-to-End System Architecture

DocuShift is structured into 7 modular, decoupled stages supported by an **Additive Hybrid Catalog** and a central **State & Delta Engine**:

```mermaid
flowchart TD
    subgraph Catalog["Additive Hybrid Catalog & Discovery"]
        D1["docs.tibco.com API Discovery\n/api/a_to_z\n/api/products/{slug} (Active)\n/api/products/archive/{slug} (Archived)"] --> M1["Smart Merge & Upsert Engine"]
        M2["Manual User Edits\n(config/products.csv\nconfig/versions.csv)"] --> M1
        M1 --> CAT["Master Catalog Store\n(Active vs Archived Registry)"]
    end

    subgraph Taxonomy["Taxonomy & Mapping"]
        CAT --> T1["Taxonomy Engine (taxonomy.yaml)"]
        T1 --> T2["Categorized Products\n(BU: TIBCO / IBI -> Product Family)"]
    end

    subgraph Download["Package Acquisition"]
        T2 --> DW1["Async / Resumable\nPackage Downloader\n(Filter: convert_eligible AND convert_batch)"]
        DW1 --> DW2["Family Workspace\n(families/{locale}-{bu}-{family}/downloads/*.zip)"]
        MZ["Manually Supplied ZIP\n(--from-file; zip_source=manual)\nno usable zip_url"] --> DW2
    end

    subgraph Extract["Extraction & Asset Cataloging"]
        DW2 --> EX1["ZIP Extractor & Validator\n(same selection as download;\narchived versions never reach here)"]
        EX1 --> EX2["Asset & CSH Catalog\n(HTML, CSH Aliases, PDF, Word, XLS, Imgs)"]
        EX2 --> EX3["Engine Detector\n(per version, writes back to versions.csv)"]
    end

    subgraph Convert["Multi-Engine Conversion & Transforms"]
        EX3 --> C1["Profile Selector\n(Flare | DITA | WebWorks | DocBook)"]
        C1 --> C2["Core Transforms\n- Dropdowns & Callouts (> [!NOTE])\n- HTML Tables to GFM\n- Link & Anchor Resolution\n- CSH Mapping to MD Anchors\n- Asset Relinking"]
        C2 --> C3["Clean GFM Markdown Files"]
    end

    subgraph AEM["AEM Architecture Synthesis"]
        C3 --> AEM1["AEM Navigation Builder"]
        AEM1 --> AEM2["toc.yml, nav.yml, meta.yml\nLanding Pages & Frontmatter"]
    end

    subgraph Sync["Git Sync & Distribution"]
        AEM2 --> G1["Git Workspace Organizer"]
        G1 --> G2["Target GitHub Product Repositories\n(BU / Family / Product / Version)"]
    end

    subgraph Central["Central State & Tracking Engine"]
        ST["State & Delta Ledger (state.db)\nTracks status per (BU, Product, Version)\nEnables Phased Batches & Delta Updates"]
        Catalog -.-> ST
        Download -.-> ST
        Extract -.-> ST
        Convert -.-> ST
        AEM -.-> ST
        Sync -.-> ST
    end
```

---

## 2. Discovery Protocol & API Integration

DocuShift integrates directly with the `docs.tibco.com` REST APIs:

1. **Product Master List (`/api/a_to_z`)**:
   - Returns all active public and unversioned products, product names, slugs, and IDs.
2. **Active Product Versions (`/api/products/{slug}`)**:
   - Returns the **current version as the product object itself** — `version_no`, `folder_path`, `isArchiveExists`, document listings — with every other release under `siblings`. See §2.1.
   - **Download All Docs ZIP Endpoint**: Built from `folder_path`, but only for active versions and only when the path is version-shaped:
     `https://docs.tibco.com/pub/{folder_path}/doc/zip/tib_{folder_path.replace('/', '_')}_doc.zip`
3. **Archived / "Other Versions" (`/api/products/archive/{parent_slug}`)**:
   - Returns `result.product.children`: archived records with `version_no`, `name`, `GA_date`, and a direct `zipPath` — the only trustworthy source of an archived version's URL.
   - **Conversion Policy**: By default, archived versions are inventoried with `is_archived: true` and `convert_eligible: false`. Users can flip `convert_eligible: true` on specific archived versions when needed.
4. **Product Suites / Categories (`/api/product_list_by_suites`, `/api/bu_category_products`, `/product/categories#name=All`)**:
   - Maps products to major suite groups (e.g. `WebFOCUS`, `ibi`, `Spotfire`, `EMS`, `BusinessWorks`, `EBX`).
   - **Advisory only.** The majority of products carry no docsite category, so this source can never be authoritative for `family`. It may promote a product from `unclassified`, but never overrides a `manual` assignment. See §3.3.

### 2.1 What the payloads actually look like

Verified against the live API on 2026-09-03, using `tibco-enterprise-message-service` as the reference product. Several of these are not what the endpoint names suggest, and each one changes how the crawler is written:

| Observed | Consequence |
| :--- | :--- |
| Every response is wrapped: `{"result": {"success": …, "product"\|"products": …}}` | The crawler peels a named envelope before reading anything. |
| `/api/products/{slug}` returns **the current version as the product object** — it carries `version_no` and `folder_path` itself — with every *other* release under `siblings` | The record set is `[detail] + siblings`. Reading only `siblings` would silently drop the newest version of every product. |
| `siblings` mixes active and archived releases, separated by an `isArchive` flag | Archive status is per record, not per endpoint. |
| Archived siblings carry **stale** folder paths (`enterprise_message_service`, `ems-zlinux` instead of `ems/8.2.1`) | An active ZIP URL is only templated from a path that looks like `<code>/<version>`. Archived rows get their URL from the archive index instead, never from a template — a guessed URL would be recorded in the catalog as fact and fail much later. |
| The archive index **overlaps** `siblings` rather than replacing it | The two are merged by version number: a version already known is topped up with the index's `zipPath` and `GA_date`, and an active record is never demoted to archived. |
| `published_date` on old releases is a bulk-migration timestamp (every EMS 5.x and 6.x row reads `2022-05-26`) | It is excluded from the release-date candidates, so the archive index's `GA_date` supplies the real month. |
| 70 of the 739 A-to-Z entries have `isPublicLevel: false`, and requesting one returns an **SSO interstitial as HTTP 200** | They are filtered out before the request. A missing flag is treated as public, so a schema change cannot silently empty the crawl. |
| Key spellings differ per endpoint (`version_no` / `versionNumber`, `folder_path` / `folderPath`) | Field reads match a small list of candidate names. The API is undocumented; being strict would mean a release every time a field is renamed. |

Two policies fall out of this and are worth stating separately, because they are what keep a bad crawl from becoming a bad catalog:

- **A product that cannot be reached is excluded from the result, not returned empty.** An empty version list would read to the merge as "every version was deleted upstream" and abort the whole fetch (§3.5).
- **`catalog fetch` requires a scope.** `--product` and `--batch` are resolved to crawl selectors *before* the per-product request, so a three-product batch costs three requests rather than 668. Because a product's code is rarely its slug (`ems` is published as `tibco-enterprise-message-service`), the selector set carries both the code and the slug already recorded in the catalog.

---

## 3. Catalog Data Schema (CSV)

The catalog is stored as **two normalized CSV files**, not JSON. At ~250 products x 5-15 versions (1,500-4,000 version rows), the dominant human operations are column operations — bulk-toggling `convert_eligible` across a family, reassigning `family` for a batch, triaging unclassified products. Those are a filter and a fill-down in Excel, and near-impossible by hand in nested JSON. CSV also produces a one-line git diff when discovery finds a new version, versus a ten-line nested insert.

The pydantic models in `models.py` remain the in-memory representation; CSV is purely the on-disk form.

### 3.1 `config/products.csv` — one row per product

| Column | Owner | Notes |
| :--- | :--- | :--- |
| `product_code` | tool | Primary key; join key for `versions.csv` |
| `display_name` | tool, user-editable | e.g. `TIBCO Enterprise Message Service™` |
| `bu` | **user** | `tibco` or `ibi` |
| `family` | **user** | Must exist in `taxonomy.yaml` for this BU |
| `family_source` | tool | Provenance — see §3.3 |
| `slug` | tool | Docsite slug used for API calls |
| `custom_override` | user | Explicit whole-row pin; ignore all upstream changes |

```csv
product_code,display_name,bu,family,family_source,slug,custom_override
ems,TIBCO Enterprise Message Service™,tibco,messaging,manual,tibco-ems,false
ebx,TIBCO EBX®,tibco,data_management,taxonomy_rule,tibco-ebx,false
webfocus,ibi™ WebFOCUS®,ibi,webfocus,manual,ibi-webfocus,true
```

> **`engine` is deliberately absent here.** The source toolchain varies *between versions* of the same product — TIBCO migrated products onto Flare over time, so an older version may be WebWorks or DITA while the current one is Flare. It is therefore a `versions.csv` column. See §3.4.

### 3.2 `config/versions.csv` — one row per version

| Column | Owner | Notes |
| :--- | :--- | :--- |
| `product_code` | tool | FK to `products.csv` |
| `version` | tool | e.g. `10.4.0`; with `product_code` forms the row key |
| `is_archived` | tool | From the archive API |
| `convert_eligible` | **user** | Policy gate: *may* this version ever be converted? Active defaults `true`, archived defaults `false` |
| `convert_batch` | **user** | Scheduling: which run this version belongs to, e.g. `poc-1`. Empty = not scheduled. Free text, lowercased on write — see §3.7 |
| `release_date` | tool | ISO where parseable; free text otherwise (the archive API returns values like `June 2022`) |
| `engine` | tool (detected), user-overridable | `flare` \| `dita` \| `webworks` \| `docbook` \| `auto`. **Per-version, not per-product** — see §3.4 |
| `engine_source` | tool | `detected` \| `manual` \| `auto` (not yet determined) |
| `zip_url` | tool, user-editable | Resolved download endpoint. May be empty when `zip_source=manual` |
| `zip_source` | **user** | `auto` (fetch from `zip_url`) \| `manual` (package supplied by hand; never fetched) — see §3.8 |
| `custom_override` | user | Explicit row pin |
| `_bu`, `_family` | **tool, read-only** | Denormalized from `products.csv` so you can filter by family without a VLOOKUP. Regenerated on every write; **edits here are ignored** — change them in `products.csv` |

```csv
product_code,version,is_archived,convert_eligible,convert_batch,release_date,engine,engine_source,zip_url,zip_source,custom_override,_bu,_family
ems,10.4.0,false,true,poc-1,2025-11-04,flare,detected,https://docs.tibco.com/pub/ems/10.4.0/doc/zip/tib_ems_10.4.0_doc.zip,auto,false,tibco,messaging
ems,10.2.1,true,false,,2023-06-12,auto,auto,https://docs.tibco.com/pub/ems/tibco-ems-10-2-1_documentation.zip,auto,false,tibco,messaging
ems,8.6.0,true,false,,2020-04-30,webworks,detected,https://docs.tibco.com/pub/ems/tibco-ems-8-6-0_documentation.zip,auto,false,tibco,messaging
ebx,6.2.0,false,true,poc-1,2025-09-30,flare,detected,,manual,false,tibco,data_management
```

Note the three `ems` rows: the current release is Flare, an older one is WebWorks, and the un-downloaded one is still `auto` because its engine cannot be known until the package is extracted. Two rows carry `convert_batch=poc-1`; `docushift download --batch poc-1` selects exactly those two and nothing else.

The `ebx` row shows the other acquisition path: it is convert-eligible with **no** `zip_url`, because discovery never produced a working one and the ZIP was handed to the tool directly. `zip_source=manual` is what makes that a valid state rather than a validation failure — see §3.8.

**Volatile machine state is deliberately excluded** from both files. `zip_etag`, `zip_size`, checksums, per-stage status, and free-form metadata live in `state.db`. This is what keeps the CSVs stable enough to leave open in a spreadsheet — a `catalog fetch` touches them only when discovery finds a genuinely new product or version.

### 3.3 Family Classification & Provenance

Classification is a **majority-manual triage job**: most products carry no docsite category, so no automated source can populate `family` reliably. `family_source` records how each assignment was reached, in strict precedence order (first match wins):

| `family_source` | Meaning | Overwritable by fetch? |
| :--- | :--- | :--- |
| `manual` | Set by a human | **Never** |
| `taxonomy_rule` | Matched a keyword rule in `taxonomy.yaml` | Yes |
| `docsite_category` | Docsite category data supplied one (minority of products) | Yes |
| `unclassified` | Fell through everything — **needs triage** | Yes |

This makes triage a spreadsheet filter, and makes progress reportable (`docushift catalog triage` → "187 of 250 unclassified").

Consequently `config/taxonomy.yaml` holds **family definitions and keyword inference rules only** — it no longer carries per-product mappings, since maintaining 250 hand-classified products in four-level nested YAML recreates the exact pain CSV was chosen to avoid. The ibi/WebFOCUS/Omni/iWay heuristics formerly hardcoded in `config.py:resolve_product_info()` are now YAML rule data.

A rule lists `match` tokens plus the `bu` and `family` to assign. Each token is compared case-insensitively against the `product_code` as an exact match, and against the display name as a substring; the first rule to match wins, so specific rules are ordered above broad ones. A product matching nothing is written `unclassified` rather than guessed into a family.

Because two automated sources can disagree, `family` is the one field the merge resolves by **provenance rank** rather than by snapshot comparison: a fetch may only raise a product's classification confidence, never lower it.

### 3.4 Engine Resolution (Per-Version, Detected)

**The source toolchain is a property of a version, not of a product.** TIBCO migrated products onto MadCap Flare progressively, so a single product's history commonly spans generators — an 8.x doc set built with FrameMaker + WebWorks, a 9.x set from DITA, and a 10.x set from Flare. Modelling `engine` on the product would apply the wrong converter to every older version.

It is also **detected, not declared**. Across 1,500-4,000 versions, hand-assignment is infeasible, and a wrong default is silently destructive: feeding a WebWorks set to the Flare engine produces plausible-looking but incorrect Markdown with no error. The default is therefore `auto`, never `flare`.

**Resolution order** (first match wins):

| `engine_source` | Meaning | Overwritable by detection? |
| :--- | :--- | :--- |
| `manual` | A human corrected it | **Never** |
| `detected` | `engines/detector.py` identified it from extracted content | Yes, on re-extract |
| `auto` | Not yet determined — package not downloaded/extracted | Yes |

**Detection signals**, ordered by reliability (marker files first, they are cheapest and least ambiguous):

| Engine | Marker files / directories | Content signature |
| :--- | :--- | :--- |
| Flare | `*.mcwebhelp`, `*.mclog`, `Skins/`, `Data/`, `MicroContent/`, `_globalpages/`, `csh.js` | `MadCap` namespace and `MadCap:*` attributes |
| WebWorks | `wwhelp/`, `wwhdata/` | `WebWorks` generator meta tag |
| DITA-OT | `*.dita` remnants, DITA metadata files | DITA-OT generator comment |
| DocBook | — (flat HTML output) | `DocBook XSL Stylesheets` generator comment |

Verified against the cached `dsp_gridserver` 7.1.1 sample: all six Flare marker paths present, and a `MadCap` reference in **197 of 197** `admin-guide` files. Marker-file detection alone is decisive there; the content signature serves as corroboration and as the fallback for DocBook, which has no distinctive file layout.

**Pipeline consequence:** `engine` cannot be populated at Stage 1 (Discovery) because it requires the package contents. It is written back into `versions.csv` after Stage 4 (Extraction), making the catalog a mid-pipeline write target rather than a discovery-time artifact. Stage 5 then reads it to select the converter.

**Granularity caveat:** one version's ZIP may bundle multiple guides. In the `dsp_gridserver` sample these are nine sibling folders (`admin-guide`, `dev-guide`, `install-guide`, `com-tutorial`, …) of a *single* Flare output, so per-version resolution is correct. Should a bundle ever mix generators across guides, the detector records the per-folder map in `state.db` and sets the dominant engine in the CSV; handling genuinely mixed bundles is deferred until one is observed.

### 3.5 Snapshot-Based 3-Way Merge

`state.db` retains the **last-fetched value of every field**. On `catalog fetch`, each field is resolved from three inputs:

- **base** — what discovery wrote last time (snapshot)
- **theirs** — what discovery returns now
- **mine** — what the CSV currently says

If `mine != base`, the field was edited by a human and is preserved. Otherwise `theirs` wins. No `custom_override` flag is required for this to work — expecting a user to remember to tick a protection column on each edited row of a 4,000-row sheet guarantees silent data loss. `custom_override` survives only as an explicit "pin this entire row" escape hatch.

Three properties of the implementation matter:

- **Resolution is per field, not per row.** Editing `display_name` must not also freeze the `slug` beside it.
- **With no snapshot, `mine` wins** unless it is empty. A missing base means the row predates the state DB (or the DB was discarded); inventing one would silently overwrite edits. Only genuinely blank cells are filled from the fetch.
- **The merge covers only what discovery owns**: `display_name`, `slug`, `is_archived`, `convert_eligible`, `release_date`, `zip_url`. Four columns are excluded structurally rather than by rule, and `version_snapshot` carries none of them: `engine`/`engine_source`, because the detector writes them *after* discovery (§3.4); `convert_batch`, because no automated stage writes it at all (§3.7); and `zip_source`, because it records a human's supply decision that a fetch has no standing to revoke (§3.8). A fetch therefore cannot reset a detected engine, clear a batch tag, or silently re-point a hand-supplied package at a URL.

Deletion detection is scoped to the products present in the current fetch, so `catalog fetch --product ems` cannot read every other product's absence as a removal.

### 3.6 CSV Round-Trip Hygiene

Excel is the expected editor, which imposes hard requirements:

| Hazard | Defense |
| :--- | :--- |
| `TIBCO EBX®` renders as `TIBCO EBXÂ®` on double-click open | Write `utf-8-sig` (BOM); read `utf-8-sig`, which also tolerates a missing BOM |
| Version `1.10` coerced to a number, saved back as `1.1` | Importer diffs version keys against the last-known set; orphaned keys **abort the import** rather than silently deleting |
| `2025-11-04` reformatted to `11/4/2025` by locale | Parse permissively, always write ISO; pass unparseable values through verbatim |
| Excel writes `TRUE` / `FALSE` | Read case-insensitively (`true`/`1`/`yes`/`y`); always write lowercase `true`/`false` |
| Row deleted to mean "skip this" | Deletion requires `--allow-deletes`; the supported way to exclude is `convert_eligible=false` |
| Diff churn on every fetch | Fixed column order; stable sort — products by `(bu, family, product_code)`, versions by `(product_code, version desc)` using natural version sort so `10.4.0` sorts above `9.1.0` |

### 3.7 Selecting Versions to Convert

Two separate columns, because they answer two different questions:

| Question | Column | Type | Default | Lifetime |
| :--- | :--- | :--- | :--- | :--- |
| *May this version ever be converted?* | `convert_eligible` | bool | `true` active, `false` archived | Long-lived policy |
| *Is it in **this** run?* | `convert_batch` | free text | empty | Changes every wave |

**Why not one column.** Only a minority of the ~1,500–4,000 catalogued versions are ever converted, and a POC typically wants three. With `convert_eligible` alone, scoping that POC means setting `false` on ~1,497 rows — the sheet fills with `false`, and "deliberately out of scope" becomes indistinguishable from "not in this wave." `convert_batch` inverts the direction: it is **opt-in**, so tagging three rows is the entire cost of scoping a run, and every other row stays exactly as the last fetch left it.

**How they compose.** Eligibility is the hard gate; the batch is a filter applied within it.

```
selection = catalog.iter_versions(batch="poc-1", eligible_only=True)
```

A version tagged into a batch but left `convert_eligible=false` is **skipped**, not converted. That combination is almost always a mistake, so `catalog import` warns about it by name rather than failing.

**Provenance.** `convert_batch` is excluded from `_MERGEABLE_VERSION_FIELDS` and from the `version_snapshot` table entirely — the same structural exclusion the engine columns get, for the mirror-image reason. The engine columns are written after discovery, by the detector; `convert_batch` is never written by any automated stage at all. A fetch therefore cannot clear a batch tag, and does not need a merge rule saying so.

**Normalization.** Values are trimmed and lowercased on write, so `POC-1`, `poc-1 `, and `poc-1` are one batch rather than three. `docushift catalog batches` prints the labels in use with a version count each, so a run's scope is checkable before it starts.

### 3.8 Manually Supplied Packages

Discovery will not always produce a usable `zip_url`. Across ~250 products the docsite is not uniform: some products publish no "Download All Docs" bundle, some `folder_path` values do not compose into a valid ZIP endpoint, and archive `zipPath` entries go stale. The resulting row is convert-eligible with a URL that 404s or is simply blank — and the package itself is often obtainable another way (support, an internal mirror, a colleague's copy).

**A hand-supplied ZIP is therefore a first-class package source, not a workaround.** It converts, and it archives, through exactly the same downstream path as a downloaded one.

**Contract: the file goes where the pipeline already looks.** There is no new location and no path stored anywhere in the catalog:

| Version | Canonical location |
| :--- | :--- |
| Active / eligible | `ConfigManager.download_path(bu, family, product_code, version)` → `families/<family>/downloads/<product_code>-<version>.zip` |
| Archived | `ConfigManager.archive_path(bu, family, product_code, version)` → `families/<family>/archive/<product_code>-<version>.zip` |

Because the path is fully derivable from `(bu, family, product_code, version)`, Stage 4 needs no special case: a manually placed ZIP and a downloaded one are indistinguishable on disk, which is the point. `archive_path()` is the one new method this requires, added for symmetry with `download_path()`.

**Why a `zip_source` column and not just "is the file there?"** Two reasons, both concrete:

- `catalog import` runs on a fresh checkout where `families/` does not exist — it is git-ignored. A validator that stats the filesystem would report every manually supplied version as broken on any machine that has not downloaded yet. The catalog has to be able to state the intent independently of the working tree.
- `download` needs to know not to try. Without a pin, a version with no `zip_url` is an error and a version with a stale `zip_url` gets re-fetched over the good local copy.

**Why not put the local path in `zip_url`.** An absolute path (`C:\Users\…\ems.zip`) or a `file://` URL in a CSV that is committed and shared is valid on exactly one machine. Recording *that* the package is local, and deriving *where* from the layout, keeps both CSVs machine-independent.

**`zip_url` and `zip_source` stay independent.** `zip_url` remains fully merged — if a later fetch discovers a working endpoint, it is recorded even on a `manual` row. Only the supply decision is pinned. That combination (`zip_source=manual` with a non-empty `zip_url`) is exactly what makes "discovery has since found a real URL for this; you can drop the manual pin" a computable warning rather than something the user has to notice.

**Consequences elsewhere:**

| Component | Change |
| :--- | :--- |
| `validate()` | The `convert_eligible with no zip_url` problem is exempted when `zip_source=manual`. Without this, every hand-supplied version blocks the import. |
| `warnings()` | Reports `zip_source=manual` rows that now carry a `zip_url`, and `manual` rows whose expected file is absent when the family workspace exists locally. |
| Merge | `zip_source` excluded structurally (§3.5). |
| Stage 4 extract | Unchanged — reads the canonical path. |
| `state.db` | Records the computed sha256, size, `downloaded` status, and the originating path the file was copied from, for audit. There is no upstream checksum to compare against, so the computed one is authoritative for later "is this still the same file" checks. |

**Ingestion is validated, not trusted.** `--from-file` rejects anything `zipfile.is_zipfile` does not accept before copying. The common real failure is not a corrupt archive but an HTML login redirect or error page saved under a `.zip` name; caught at ingest it is a one-line message, and caught at Stage 4 it is a confusing extraction failure days later. The file is **copied**, not moved — the user's own copy is not the tool's to consume.

**Unknown versions.** `--from-file` requires the *product* to exist in the catalog: a typo'd product code is unrecoverable and would seed a junk row. If the product exists but the version does not, the version row is auto-added with a warning, matching the treatment of an undeclared family (§4.2) — the user has a real package in hand, which is stronger evidence the version exists than discovery's silence is that it does not.

---

## 4. The Families Workspace

Downloaded ZIPs and extracted trees are organized **by family**, not by product, in a top-level `families/` directory (git-ignored).

### 4.1 Layout

```
families/
└── en-us-tibco-messaging/          # {locale}-{bu}-{family}
    ├── downloads/
    │   ├── ems-10.4.0.zip          # {product_code}-{version}.zip
    │   └── ems-10.3.0.zip
    ├── extracted/
    │   └── ems/
    │       ├── 10.4.0/             # version keeps its dots
    │       │   └── doc/html/…
    │       └── 10.3.0/
    └── archive/                    # only via `docushift archive download`
```

`ConfigManager` is the single owner of these paths (`family_dir`, `downloads_dir`, `extracted_dir`, `archive_dir`, `download_path`, `extract_path`). Stage 3, Stage 4, and Stage 5 each derive the location they need rather than passing paths between themselves; `state.db` records the resolved `download_path` / `extract_path` per version so a resumed run does not have to recompute the layout it ran under.

Four naming decisions worth stating:

- **`{locale}-{bu}-{family}`, flat and hyphenated.** Inherited from the predecessor `html-to-md` project, where the identical string names the *publishing repository* a family is destined for (`en-us-ibi-ibi`, `en-us-spot-data-science-statistica`). Keeping the working folder and the eventual repo identically named makes the Stage 7 hand-off a copy rather than a translation.
- **The locale prefix is reserved, not yet variable.** `html-to-md` publishes `fr-fr` and `ja-jp` trees; nothing here is multi-locale, but `ConfigManager(locale=…)` means adding one is not a rename of every folder on disk.
- **`family` is slugified, `taxonomy.yaml` keys are not.** The YAML key `data_management` is an identifier; the folder is `data-management`. `utils/slug.py:slugify` is the only place that conversion happens, so the two cannot drift.
- **Versions keep their dots in the working tree.** `html-to-md` writes `6-2-3` in *published* paths, and Stage 6 will too. Here the segment must round-trip back to a `versions.csv` key, and `6-2-3` is ambiguous (`6.2.3`? `6-2.3`?) where `6.2.3` is not.

`downloads/` and `extracted/` are split rather than co-located per version so that reclaiming disk after a successful extract is one `rmtree` of `downloads/`, not a glob across the tree.

A hand-supplied ZIP (§3.8) lands in `downloads/` under the same `{product_code}-{version}.zip` name as a downloaded one and is deliberately indistinguishable from it — the provenance lives in `versions.csv` and `state.db`, not in the filename, so no downstream stage needs a second code path.

### 4.2 Families Are User-Extensible

A user may type a **new family name straight into `products.csv`** without declaring it in `taxonomy.yaml` first. The folder is auto-registered on first download and `catalog import` emits a warning naming the resulting path:

```
WARN newthing: family 'streaming_analytics' is not declared in taxonomy.yaml for bu 'tibco'.
     Accepted; workspace folder -> families/en-us-tibco-streaming-analytics.
     Add it to taxonomy.yaml to silence this.
```

Accepting-with-a-warning rather than rejecting is deliberate: requiring a YAML edit before a CSV edit takes effect is the two-step friction that pushed per-product classification out of `taxonomy.yaml` in the first place (§3.3). The warning is what keeps a typo (`mesaging`) from silently becoming a third family folder holding one product. Warnings never block a write — they are reported separately from `validate()` problems, which do.

### 4.3 Archived Versions Are Never Downloaded

Archived versions are inventoried for a complete product history but default to `convert_eligible=false`, and the pipeline honours that at **both** Stage 3 and Stage 4 — an archived ZIP is not downloaded, so there is nothing to extract. Across ~250 products with 5–15 versions each, downloading history nothing reads would dominate both bandwidth and disk.

When an old release does come up, `docushift archive download --product ems --version 8.6.0` pulls that one ZIP into `families/<family>/archive/`. It lands outside `downloads/` on purpose: that directory is the pipeline's working set, and a reference ZIP sitting in it would look to `extract` like a package awaiting conversion. Genuinely converting an archived version remains a `convert_eligible=true` flip on its row, which routes it through the normal path.

Archived `zipPath` values are the most likely to be stale, so the same command takes `--from-file` (§3.8) and files a hand-obtained ZIP at `archive_path()` instead of fetching it. Its `--extract` unpacks within `archive/`, never into the pipeline's `extracted/` tree — an archived package that was never selected for conversion must not appear alongside ones that were.

---

## 5. Multi-Engine Conversion & Asset Handling

The converter for a package is chosen from that **version's** `engine` value, resolved by `engines/detector.py` during extraction (§3.4) — not from any product-level setting. A version whose engine is still `auto` is skipped with a warning rather than guessed at, since a wrong guess yields silently malformed Markdown.

### 5.1 MadCap Flare Engine (`engines/flare.py`)
- **Dropdown Extraction**: Unrolls `MCDropDown` structures into native Markdown headings or sections.
- **Proxy Stripping**: Removes `MadCap:topicToolbarProxy`, breadcrumb proxies, search bars, and skin templates.
- **Callout Normalization**: Maps Flare `.note`, `.tip`, `.warning`, `.caution` classes to standard GFM alerts (`> [!NOTE]`, `> [!WARNING]`, etc.).
- **Table Normalization**: Formats Flare table styles into clean GFM pipe tables.
- **CSH Linkage**: Preserves Flare `Alias.xml` / `CSH.js` identifier-to-target anchor mapping.

### 5.2 Universal Asset Preservation
- Copies referenced assets (`PDF`, `DOC`, `DOCX`, `XLS`, `XLSX`, `TXT`, `PNG`, `SVG`, `ZIP`) and rewrites relative markdown paths.

---

## 6. AEM Structure Synthesis & Git Sync
- Synthesizes `toc.yml`, `nav.yml`, `meta.yml`, `index.md`, and YAML frontmatter.
- Distributes ready-to-push documentation sets into `{target_git}/{bu}/{family}/{product}/{version}/`.

> **Open, deferred to Phase 6:** the family workspace name (`en-us-tibco-messaging`, §4.1) is the same string `html-to-md` uses as a *publishing repository* name, which suggests the sync target should be `{target_git}/{locale}-{bu}-{family}/{locale}/{product}/{doc-class}/{version-dashed}/` rather than the nested form above. `html-to-md` also splits assets into a sibling `-resources` repo and dashes the version (`6-2-3`). Deciding between the two shapes needs a real AEM target repo to check against, so the workspace layout is settled and the sync layout is not.
