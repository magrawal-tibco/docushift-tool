# DocuShift User Guide: Migration & Conversion CLI

> **Document Status:** Living User Manual  
> **Last Updated:** 2026-09-03  
> **Target Environment:** TIBCO & IBI Documentation Migration to AEM

---

## 1. Quickstart & Installation

```bash
# Clone the repository
git clone https://github.com/magrawal-tibco/docushift-tool.git
cd docushift-tool

# Install in development mode
pip install -e ".[dev]"

# Enable the commit message template (local git config, not inherited by clones)
git config --local commit.template .gitmessage
git config --local core.commentChar ';'
```

> `core.commentChar` must be set to `;`. Git's default comment character is
> `#`, which would strip the template's `## User Requests` / `## Changes` /
> `## Technical Details` headers out of every commit message.

### Verify the installation

```bash
docushift doctor
```

Prints the resolved project paths (`config/`, `cache/`, `families/`, `output/`, `state.db`), the active locale, and which family workspaces exist so far. The working directories are created on first run; per-family folders are not, so an untouched project reads `family workspaces: none yet`.

> **Implementation status.** The command tree below is the full intended surface and `--help` reflects it. Implemented today: `doctor` and the whole `catalog` group **except `catalog fetch`**, which waits on the Phase 3 docsite crawler to supply its input — the merge engine behind it is already built and tested. Every unbuilt command exits non-zero naming the phase that will build it (see `docs/planning.md`); commands are never silently no-op.

---

## 2. Managing the Additive Product Catalog

The catalog is **two CSV files**, designed to be edited directly in Excel:

| File | Contents |
| :--- | :--- |
| `config/products.csv` | One row per product — `bu`, `family`, display name |
| `config/versions.csv` | One row per version — the `convert_eligible` toggle, the `convert_batch` run label, `zip_url` / `zip_source`, `is_archived`, and the detected `engine` |

They join on `product_code`. It is additive, distinguishes Active vs Archived versions, and **preserves your edits automatically** — see "How your edits are protected" below.

### On-Demand Fetching from Docsite
Queries `docs.tibco.com/a_z_products` via its backend REST APIs to discover all products, active versions, and archived ("Other Versions") packages:
```bash
# Fetch catalog for both TIBCO and IBI
docushift catalog fetch --all

# Fetch catalog for a specific Business Unit
docushift catalog fetch --bu tibco
docushift catalog fetch --bu ibi

# List catalog products and versions
docushift catalog list
docushift catalog show --product businessevents-enterprise
```

### Choosing which versions get converted

Two columns in `config/versions.csv`, answering two different questions:

| Column | Question | Default |
| :--- | :--- | :--- |
| `convert_eligible` | *May this version ever be converted?* | `true` for active, `false` for archived |
| `convert_batch` | *Is it in **this** run?* | empty (not scheduled) |

Use `convert_eligible` for permanent policy — this version is out of scope, full stop. Use `convert_batch` to scope a run: tag the handful of rows you want with a label like `poc-1` or `wave-2` and pass `--batch poc-1` to the pipeline. Nothing else in the sheet has to move.

```bash
# Scope a POC to two versions
docushift catalog set --product ems --version 10.4.0 --batch poc-1
docushift catalog set --product ebx --version 6.2.0 --batch poc-1

# Check the scope before running anything
docushift catalog batches
docushift catalog list --batch poc-1

# Run the pipeline over just those two
docushift download --batch poc-1
docushift extract  --batch poc-1
docushift convert  --batch poc-1
```

For anything larger than a handful, the spreadsheet is faster: filter `versions.csv` by `_family`, select the `convert_batch` column, and fill down `wave-2`. Values are lowercased on save, so `POC-1` and `poc-1` are the same batch. To unschedule a version, clear the cell (or pass `--batch ""`).

**The two columns compose, and eligibility wins.** A version tagged `poc-1` but left `convert_eligible=false` is skipped, not converted — `catalog import` warns about that combination by name, since it is nearly always an oversight.

### Active vs Archived Version Rules
- **Active Versions**: `convert_eligible: true` — eligible for download and conversion.
- **Archived Versions**: `convert_eligible: false` — tracked in the catalog for a complete product history, but **never downloaded and never extracted**. Across ~250 products, pulling history nothing reads would dominate bandwidth and disk.

### When the ZIP URL is missing or wrong

Discovery does not always find a working download link — some products publish no
"Download All Docs" bundle, and archived links go stale. If you have the ZIP by other
means (support, an internal mirror, a colleague), hand it to DocuShift directly and it
converts exactly like a downloaded one:

```bash
docushift download --product ebx --version 6.2.0 --from-file "D:\downloads\ebx-docs.zip"
```

That copies your file into `families/en-us-tibco-data-management/downloads/ebx-6.2.0.zip`,
sets `zip_source=manual` on the row, and records its checksum. From then on `extract`,
`convert`, and `sync` treat it as an ordinary package — nothing downstream needs to know
where it came from. Your original file is copied, not moved.

For an archived version, the same flag is on the archive utility:

```bash
docushift archive download --product ems --version 8.6.0 --from-file "D:\downloads\ems-86.zip"
```

Notes:

- **`zip_source=manual` means "never fetch this".** The row is exempt from the
  *convert-eligible with no zip_url* check, and `download` will not try to re-fetch it or
  overwrite your file. Set it back to `auto` to return the version to normal downloading:
  `docushift catalog set --product ebx --version 6.2.0 --zip-source auto`.
- **The path is not stored in the CSV**, only the fact that the package is local. An
  absolute path like `D:\downloads\…` would be meaningless to anyone else sharing the
  catalog, so the location is derived from the family layout instead.
- **The file is checked before it is accepted.** A `.zip` that is really a saved login
  page or error page is rejected at this point rather than failing confusingly during
  extraction.
- If a later `catalog fetch` turns up a real URL for a row you pinned, `catalog import`
  mentions it — your pin still wins until you clear it.

### Working with an archived version

To just look at one, without putting it into the pipeline:

```bash
# What archived versions exist?
docushift archive list --product businessevents-enterprise

# Pull one ZIP into families/<family>/archive/ (no extraction, no conversion)
docushift archive download --product businessevents-enterprise --version 6.2.2
docushift archive download --product businessevents-enterprise --version 6.2.2 --extract

# Archived links go stale most often; supply the ZIP yourself when one does
docushift archive download --product ems --version 8.6.0 --from-file "D:\downloads\ems-86.zip"
```

The ZIP lands in `archive/`, deliberately outside `downloads/` — `downloads/` is the pipeline's working set, and a reference ZIP sitting there would look to `extract` like a package awaiting conversion.

To genuinely **convert** an archived version, flip its eligibility so it routes through the normal path:

```bash
docushift catalog enable --product businessevents-enterprise --version 6.2.2
```

Or open `config/versions.csv`, filter to the product, and set `convert_eligible` to `true`. For bulk changes the spreadsheet is the faster path — filter by `_family`, select the column, fill down.

### How your edits are protected

You do **not** need to flag your edits. The tool records what discovery last wrote in `state.db`; on the next `catalog fetch`, any cell that differs from that recorded value is recognised as your edit and left alone. Everything else picks up upstream changes.

Set `custom_override` to `true` only when you want to freeze an **entire row** against all future updates.

### Editing the CSVs safely

The files are written UTF-8 with a BOM so Excel opens `®` and `™` correctly. Two things to watch:

- **Format the `version` column as Text** before editing. Excel will otherwise read `1.10` as the number `1.1` and save it back that way. The importer aborts if a version key disappears, so you will be told rather than losing data silently — but it is friction worth avoiding.
- **Do not delete rows** to exclude something; set `convert_eligible=false` instead. Deletions require `docushift catalog import --allow-deletes`.

Columns starting with an underscore (`_bu`, `_family` in `versions.csv`) are generated for filtering convenience. Edits to them are ignored — change the value in `products.csv`.

After a spreadsheet session, re-import to normalize the files and check them for damage:

```bash
# Re-read, validate, and rewrite both CSVs in canonical form
docushift catalog import
```

It distinguishes two kinds of finding:

- **Problems block the write.** Version keys that vanished (the `1.10` → `1.1` case) and convert-eligible versions with no `zip_url` — unless `zip_source=manual`, which says the package is supplied by hand and no URL is expected. Nothing is written until you fix them, or re-run with `--allow-deletes` once you have confirmed the removals are intended.
- **Warnings do not.** A family not yet declared in `taxonomy.yaml`, a version tagged into a batch but left `convert_eligible=false`, or a `zip_source=manual` row that discovery has since found a real URL for. All are states you may have chosen deliberately, so they are reported and the write proceeds.

### Editing from the command line

`catalog set` is the scriptable equivalent of editing a cell, and it records provenance for you:

```bash
# Product row (products.csv)
docushift catalog set --product ems --family messaging     # also sets family_source=manual
docushift catalog set --product ems --bu tibco
docushift catalog set --product ems --display-name "TIBCO Enterprise Message Service"

# Version row (versions.csv) — --engine, --zip-url, --zip-source and --batch require --version
docushift catalog set --product ems --version 8.6.0 --engine webworks
docushift catalog set --product ems --version 8.6.0 --zip-url https://internal/mirror.zip
docushift catalog set --product ems --version 10.4.0 --batch poc-1
docushift catalog set --product ebx --version 6.2.0 --zip-source auto   # undo a manual pin
```

### Triaging Unclassified Products

Most products carry no category on the docsite, so `family` is largely assigned by hand. The `family_source` column in `products.csv` tracks how each one was set — `manual`, `taxonomy_rule`, `docsite_category`, or `unclassified`.

```bash
# How much triage is left?
docushift catalog triage
```

Filter `products.csv` to `family_source=unclassified`, assign families in bulk, and set `family_source=manual` on those rows to pin them.

### Defining a New Family

Type the family name straight into the `family` column of `products.csv` — it does **not** have to exist in `taxonomy.yaml` first. The workspace folder is created for it on the next download, and `catalog import` tells you what it will be called:

```
WARN newthing: family 'streaming_analytics' is not declared in taxonomy.yaml for bu 'tibco'.
     Accepted; workspace folder -> families/en-us-tibco-streaming-analytics.
     Add it to taxonomy.yaml to silence this.
```

This is a warning, not an error: the write goes through. Add the family under `business_units.<bu>.families` in `config/taxonomy.yaml` once you have settled on it, both to silence the warning and to give it a display name. The warning also catches the other case — if you see one for `mesaging`, that is a typo about to become its own folder.

---

## 3. The Families Workspace

Downloaded ZIPs and extracted packages are organized by **family**, under a git-ignored `families/` directory. The folder name is `{locale}-{bu}-{family}`:

```
families/
└── en-us-tibco-messaging/
    ├── downloads/
    │   ├── ems-10.4.0.zip
    │   └── ems-10.3.0.zip
    ├── extracted/
    │   └── ems/
    │       ├── 10.4.0/
    │       └── 10.3.0/
    └── archive/            # only what `docushift archive download` put there
```

Notes on the naming:

- The family is **hyphenated** even though `taxonomy.yaml` keys are underscored: `data_management` → `en-us-tibco-data-management`.
- Trademark symbols are stripped, so `TIBCO EBX®` slugs to `tibco-ebx`.
- Versions keep their dots (`10.4.0`, not `10-4-0`) so the folder maps back to a `versions.csv` row unambiguously.
- The `en-us` prefix is fixed today. It is there because the same string names the publishing repository each family is destined for, and because other locales exist upstream.

`docushift catalog show --product ems` prints the resolved workspace path for a product, and `docushift doctor` lists every workspace created so far.

Clearing disk after a successful extract is a matter of deleting `downloads/` — the extracted trees are in a sibling directory precisely so that works.

A ZIP you supplied with `--from-file` sits in `downloads/` under the same name a downloaded one would have, and behaves identically from there.

---

## 4. End-to-End Migration Commands

### View Status & Delta Dashboard
```bash
# Print overall status summary in terminal
docushift status

# Filter by BU or Family
docushift status --bu tibco --family integration

# Generate an exportable Markdown/HTML migration report
docushift report --output ./reports/migration_summary.md
```

### Selecting what a command acts on

`download`, `extract`, `convert`, and `sync` all take the same selectors, which combine:

| Flag | Selects |
| :--- | :--- |
| `--all` | The whole catalog |
| `--bu tibco` | One business unit |
| `--family integration` | One family |
| `--product ems` | One product |
| `--version 10.4.0` | One version (with `--product`) |
| `--batch poc-1` | Every version tagged into that run |

Versions with `convert_eligible=false` are excluded regardless of the selector.

### Download Documentation ZIPs
Downloads eligible versions into `families/<locale>-<bu>-<family>/downloads/`:
```bash
# Download all eligible packages in catalog
docushift download --all

# Download a specific BU, Family, Product, or scheduled batch
docushift download --bu tibco --family integration
docushift download --product businessevents-enterprise --version 6.4.0
docushift download --batch poc-1

# Supply a ZIP by hand when discovery has no usable URL (single version only)
docushift download --product ebx --version 6.2.0 --from-file "D:\downloads\ebx-docs.zip"
```

Archived versions are never downloaded here — use `docushift archive download` for those.
Versions pinned with `zip_source=manual` are skipped: their package is already in place.

### Extract & Convert to GFM
Extraction is a separate step because it is where the engine is detected and written
back into `versions.csv` (see §6). It runs over the same selection as `download`, so an
archived or ineligible version is never unpacked:
```bash
# Unzip, catalog assets and CSH maps, detect engines
docushift extract --all
docushift extract --product businessevents-enterprise --version 6.4.0
docushift extract --batch poc-1
```

```bash
# Convert all downloaded packages
docushift convert --all

# Convert a specific product version, or a whole batch
docushift convert --product businessevents-enterprise --version 6.4.0
docushift convert --batch poc-1

# Convert a local standalone folder directly
docushift convert \
  --input ./families/en-us-tibco-integration/extracted/businessevents-enterprise/6.4.0 \
  --output ./output/tibco/integration/businessevents-enterprise/6.4.0
```

### AEM Synthesis & Git Sync
```bash
# Sync converted AEM files to local GitHub repo folder
docushift sync --target-dir ../tibco-docs-aem/

# Run link and asset integrity validation
docushift validate --target-dir ../tibco-docs-aem/
```

---

## 5. Product Taxonomy Configuration (`config/taxonomy.yaml`)

This file defines **which families exist** and **the keyword rules used to guess them**. It does *not* list individual products — per-product `bu`/`family` assignment lives in `config/products.csv`, where it can be bulk-edited.

```yaml
version: "1.0"

business_units:
  tibco:
    name: "TIBCO"
    default_engine: "flare"
    families:
      integration:
        name: "Integration"
        description: "Application integration, API management, and event-driven architecture"
      messaging:
        name: "Messaging"
        description: "High-performance messaging, streaming, and pub-sub"
  ibi:
    name: "ibi"
    default_engine: "flare"
    families:
      webfocus:
        name: "WebFOCUS"
        description: "Business intelligence and enterprise reporting"

# Keyword inference. First match wins; only applied to products whose
# family_source is not "manual".
rules:
  - match: ["webfocus"]
    bu: ibi
    family: webfocus
  - match: ["omni-gen", "omni-healthdata", "iway"]
    bu: ibi
    family: data_management
```

Anything that matches no rule is written as `family_source=unclassified` for manual triage.

> Rules assign `bu` and `family` only — never `engine`. The source toolchain
> differs between versions of the same product, so it is detected per version
> from the extracted package rather than declared here. See §6.

---

## 6. Source Engines (Per-Version)

The tool that built a doc set — MadCap Flare, DITA, WebWorks, DocBook — **varies between versions of the same product**. TIBCO moved products onto Flare over time, so an older release may be WebWorks or DITA while the current one is Flare. `engine` is therefore a column in `versions.csv`, not `products.csv`.

You do not assign it by hand. It is detected from the package contents during extraction:

| `engine_source` | Meaning |
| :--- | :--- |
| `auto` | Not yet known — package not downloaded or extracted |
| `detected` | Identified from the extracted files |
| `manual` | You set it; detection will not overwrite it |

```bash
# What engines are in play, and what is still undetermined?
docushift report --engines

# Override a misdetection (sets engine_source=manual, permanent)
docushift catalog set --product ems --version 8.6.0 --engine webworks
```

A version left at `engine=auto` is **skipped during conversion with a warning**, not guessed. Guessing wrong produces Markdown that looks plausible but is subtly wrong throughout, which is far more expensive to discover later than a skipped package.

If `report --engines` shows a version stuck at `auto` after extraction, the detector found no recognised signature — inspect the extracted folder under `families/<locale>-<bu>-<family>/extracted/` and set the engine manually.
