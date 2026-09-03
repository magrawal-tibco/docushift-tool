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

---

## 2. Managing the Additive Product Catalog

The catalog is **two CSV files**, designed to be edited directly in Excel:

| File | Contents |
| :--- | :--- |
| `config/products.csv` | One row per product — `bu`, `family`, `engine`, display name |
| `config/versions.csv` | One row per version — the `convert_eligible` toggle, `zip_url`, `is_archived` |

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

### Active vs Archived Version Rules
- **Active Versions**: `convert_eligible: true` (Eligible for automatic download and conversion).
- **Archived Versions**: `convert_eligible: false` (Tracked in catalog for completeness, but skipped during download/conversion unless explicitly enabled).

### Enabling Conversion for an Archived Version
```bash
# Enable conversion for a specific archived version
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

### Triaging Unclassified Products

Most products carry no category on the docsite, so `family` is largely assigned by hand. The `family_source` column in `products.csv` tracks how each one was set — `manual`, `taxonomy_rule`, `docsite_category`, or `unclassified`.

```bash
# How much triage is left?
docushift catalog triage
```

Filter `products.csv` to `family_source=unclassified`, assign families in bulk, and set `family_source=manual` on those rows to pin them.

---

## 3. End-to-End Migration Commands

### View Status & Delta Dashboard
```bash
# Print overall status summary in terminal
docushift status

# Filter by BU or Family
docushift status --bu tibco --family integration

# Generate an exportable Markdown/HTML migration report
docushift report --output ./reports/migration_summary.md
```

### Download Documentation ZIPs
Downloads all versions flagged `convert_eligible: true`:
```bash
# Download all eligible packages in catalog
docushift download --all

# Download specific BU, Family, or Product
docushift download --bu tibco --family integration
docushift download --product businessevents-enterprise --version 6.4.0
```

### Extract & Convert to GFM
```bash
# Convert all downloaded packages
docushift convert --all

# Convert a specific product version
docushift convert --product businessevents-enterprise --version 6.4.0

# Convert a local standalone folder directly
docushift convert --input ./cache/extracted/tibco/businessevents-enterprise/6.4.0 --output ./output/tibco/integration/businessevents-enterprise/6.4.0
```

### AEM Synthesis & Git Sync
```bash
# Sync converted AEM files to local GitHub repo folder
docushift sync --target-dir ../tibco-docs-aem/

# Run link and asset integrity validation
docushift validate --target-dir ../tibco-docs-aem/
```

---

## 4. Product Taxonomy Configuration (`config/taxonomy.yaml`)

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
  - match: ["rendezvous", "streambase", "iprocess"]
    engine: docbook
```

Anything that matches no rule is written as `family_source=unclassified` for manual triage.
