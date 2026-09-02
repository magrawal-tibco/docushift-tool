# DocuShift User Guide: Migration & Conversion CLI

> **Document Status:** Living User Manual  
> **Last Updated:** 2026-09-02  
> **Target Environment:** TIBCO & IBI Documentation Migration to AEM

---

## 1. Quickstart & Installation

```bash
# Clone the repository
git clone https://github.com/magrawal-tibco/docushift-tool.git
cd docushift-tool

# Install in development mode
pip install -e ".[dev]"
```

---

## 2. Managing the Additive Product Catalog

The product catalog (`config/catalog.json`) is **decoupled, additive, and distinguishes Active vs Archived versions**.

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

# Or directly set in config/catalog.json:
# "convert_eligible": true
```

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
Enables customizable categorization rules:
```yaml
business_units:
  tibco:
    name: "TIBCO"
    families:
      integration:
        name: "Integration"
        products:
          businessevents-enterprise:
            name: "TIBCO BusinessEvents® Enterprise Edition"
            engine: "flare"
          bw:
            name: "TIBCO ActiveMatrix BusinessWorks™"
            engine: "flare"
      messaging:
        name: "Messaging"
        products:
          ems:
            name: "TIBCO Enterprise Message Service™"
            engine: "flare"
  ibi:
    name: "ibi"
    families:
      webfocus:
        name: "WebFOCUS"
        products:
          webfocus_client:
            name: "ibi™ WebFOCUS® Client"
            engine: "flare"
```
