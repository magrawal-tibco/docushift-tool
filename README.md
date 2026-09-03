# DocuShift Tool

> **Enterprise Multi-Source Documentation Migration Engine**  
> Migrating ~250 Products across TIBCO & IBI to Adobe Experience Manager (AEM) on GitHub.

---

## Key Capabilities
- **Multi-Engine Ingestion**: MadCap Flare (Primary), SDL DITA CMS, FrameMaker + WebWorks, and DocBook.
- **Spreadsheet-Editable Catalog**: `products.csv` + `versions.csv`, with a snapshot-based 3-way merge that preserves your edits automatically on re-fetch — no override flags to remember.
- **Active & Archived Version Management**: Automatic download link resolution with selective conversion flags.
- **Context-Sensitive Help (CSH)**: Maps Flare CSH identifiers to Markdown anchor targets.
- **AEM Architecture Synthesis**: Generates `toc.yml`, `nav.yml`, `meta.yml`, landing pages, and frontmatter.
- **Enterprise Tracking & Delta Engine**: SQLite ledger for phased batch runs and delta updates.

---

## Documentation
- [Project Context & Decisions](CONTEXT.md)
- [System Architecture](docs/architecture.md)
- [User Guide & CLI Reference](docs/user-guide.md)
- [Project Roadmap & Milestones](docs/planning.md)
