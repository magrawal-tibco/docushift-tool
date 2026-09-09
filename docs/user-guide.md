# DocuShift User Guide: Migration & Conversion CLI

> **Document Status:** Living User Manual  
> **Last Updated:** 2026-09-03  
> **Target Environment:** TIBCO & IBI Documentation Migration to AEM

> Wondering *why* a command behaved the way it did — which value a re-fetch kept, which versions a batch selected, how a help identifier was resolved? Every decision rule is written out step by step in [`design.md`](design.md).

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

> **Implementation status.** The command tree below is the full intended surface and `--help` reflects it. Implemented today: `doctor` and the **whole `catalog` group, `fetch` included** — discovery talks to the live docsite. The acquisition stages (`download`, `extract`) and everything downstream are not built yet. Every unbuilt command exits non-zero naming the phase that will build it (see `docs/planning.md`); commands are never silently no-op.

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
# One product — the fastest way to try it, and one HTTP request
docushift catalog fetch --product ems

# Everything already tagged into a run
docushift catalog fetch --batch poc-1

# A Business Unit, or the whole A-to-Z list (~670 products, several minutes)
docushift catalog fetch --bu tibco
docushift catalog fetch --all

# List catalog products and versions
docushift catalog list
docushift catalog show --product businessevents-enterprise
```

**A scope is required.** A bare `catalog fetch` would crawl the entire A-to-Z list, so it asks for `--all` or one of `--bu` / `--family` / `--product` / `--batch` instead of assuming. `--version` is rejected: discovery works a product at a time, and fetching one version would make the others look deleted.

`--product` accepts a **catalog product code or a docsite slug**. The two are usually different — `ems` is published as `tibco-enterprise-message-service` — so for a product already in `products.csv`, the code works and the recorded slug is used behind the scenes. For a product you have never fetched, pass the slug from its `docs.tibco.com` URL. If nothing matches, the error says so and suggests the slug.

Useful flags:

| Flag | Effect |
| :--- | :--- |
| `--dry-run` | Runs the whole crawl and merge, prints the counts, writes nothing. Worth doing first on `--all`. |
| `--allow-deletes` | Permits removal of versions discovery no longer returns. Without it, a disappearing version **aborts** the merge — an upstream outage should not silently prune your catalog. |
| `--no-include-archived` | Skips the archive index. Faster; leaves you without version history. |

What it prints: a table of added / updated / unchanged / protected counts, a dim line counting entries skipped as unversioned or not publicly visible (roughly 70 of the 739 A-to-Z entries are employee-only), any catalog warnings, and — if some products could not be reached — how many. **A product that fails is left exactly as it was**, never emptied, so a partial crawl cannot look like a mass deletion.

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

### What's actually in the package

Choosing a batch means judging packages you have not opened. `docushift extract` writes five read-only columns back into `versions.csv` so that after one exploratory extract, the sheet itself tells you:

| Column | Reads as |
| :--- | :--- |
| `_has_csh` | This version ships context-sensitive help, so it will get a `csh.yml`. Its Help button breaks if the identifiers do not survive — budget for verification. |
| `_csh_names` | How many help identifiers have to resolve. |
| `_has_api_ref` | It carries a Javadoc / C / Go / `tibdg` tree. That tree is **copied, never converted**, and publishes to the `-resources` repo. |
| `_api_files` | How much of the package that tree is. |
| `_doc_files` | Everything else — HTML, images, CSS, PDFs. A size figure, not a topic count. |

Two readings worth knowing:

- **An empty cell is not a zero.** Blank means the version has never been extracted. `0` means it was, and there was nothing there.
- **`_has_csh=true` with `_csh_names=0`** means the product ships a help map that yields no identifiers — a normal state, and in fact the *majority* of what we have surveyed: 476 of 863 Flare alias files (55%), 492 of 647 WebWorks `topics.js` (76%), 38 of 418 DITA `head.js` (9%). Worth seeing before conversion rather than after.

```bash
# Extract the batch, then sort versions.csv by _csh_names to see where the CSH risk is
docushift extract --batch poc-1
```

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

Columns starting with an underscore in `versions.csv` are generated by the tool for filtering convenience, and edits to them are ignored. `_bu` and `_family` are copied from `products.csv` on every write — change them there. The five inventory columns are written by `docushift extract` and stay put until the next extract of that version.

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

Conversion also writes the version's context-sensitive help map (`csh.yml`) and stamps the
matching identifiers into topic frontmatter — see §7.

### AEM Synthesis & Git Sync
```bash
# Sync converted AEM files to local GitHub repo folder
docushift sync --target-dir ../tibco-docs-aem/

# Run link and asset integrity validation
docushift validate --target-dir ../tibco-docs-aem/
```

**What sync writes.** Two repositories per family, both named after the family workspace (§3):

```
en-us-tibco-messaging/                  # the docs repo — what a reader reads
└── en-us/ems/
    ├── online-help/10-4-0/…            # converted Markdown, toc.yml, nav.yml, meta.yml, csh.yml
    ├── user-guides/10-4-0/…            # user-guide PDFs + index.md, toc.yml
    ├── release-information/10-4-0/…    # release notes + readme + index.md, toc.yml
    └── reference-documents/10-4-0/…    # VPAT, licence, rest of doc/ + index.md, toc.yml

en-us-tibco-messaging-resources/        # the bulk repo
└── en-us/ems/
    ├── api-references/java/10-4-0/…    # Javadoc and the C / Go / tibdg trees
    └── archives/…                      # archived-version ZIPs + index.md, toc.yml
```

Five things to expect:

- **The PDF doc-classes get an index too.** `user-guides/`, `release-information/` and `reference-documents/` each receive a generated `index.md` and `toc.yml` listing their files, so a copied PDF is reachable. Titles come from the document kind where the name identifies one (Release Notes, VPAT, License Agreement), otherwise from the PDF's own metadata, otherwise from the filename. A doc-class with no files gets no folder at all rather than an empty index.
- **`archives/` is indexed from the catalog, so it lists every archived version — including the ones you have not downloaded.** Entries whose ZIP is not in the repository link to the docsite instead, and the index says which is which. That is deliberate: `archives/` exists to be the complete product history, and `archive download` is what fills it in. `api-references/` gets no generated index — Javadoc ships its own.
- **Versions are dashed here** (`10.4.0` → `10-4-0`) and nowhere else. The catalog and the `families/` workspace keep the dots.
- **API references are never converted.** Javadoc is copied through as HTML, and topic links into it are rewritten to absolute URLs on the AEM host. Set that host in `config/publishing.yaml` (`publish_base_url`) before your first sync — the path after it is derived, not configured.
- **`validate` skips those absolute links by default.** They point at a different repository, so there is nothing on disk to check; pass `--check-external` to verify them over HTTP.

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

### Two ways a version can be unconvertible

Four engines convert: `flare`, `dita`, `webworks`, `docbook`. The `engine` column also holds names DocuShift can *recognise* but has no converter for — `r-help`, `robohelp`, `frontpage`, `help-and-manual`, `mkdocs`, `docusaurus`, `doxia`, and `other` for a generator tag we do not have a name for. Both kinds skip conversion, and telling them apart is the whole reason they are not all written as `auto`:

- **`auto` means the detector could not tell.** That is a gap in DocuShift, and it is worth a look — open the extracted folder under `families/<locale>-<bu>-<family>/extracted/` and, if you can identify it, set the engine by hand. If it is a generator we should be recognising, say so; the detection rules are grown from exactly these.
- **A named engine with no converter means we know what it is and did not build for it.** That is a scoping question for you, not a bug. Take the version out of scope with `catalog enable --disable`, or convert it by hand.

`catalog import` warns about the second case whenever the row is still `convert_eligible`, because a row reading `engine=mkdocs, engine_source=detected` otherwise looks completely settled and will quietly produce nothing.

---

## 7. Context-Sensitive Help (CSH)

A product's **Help** button passes an identifier, not a URL. If that identifier does not come through the migration, the button breaks in the shipping product — and nothing in the Markdown looks wrong. Conversion therefore carries the help map through as a first-class output.

### What you get

Each converted version gets a **`csh.yml`** at the root of its Markdown output, beside `toc.yml`:

```
output/.../businessworks/6.12.0/
├── csh.yml            ← identifier → topic map for this version
├── toc.yml
├── bw-ent-html/
├── bwce-html/
└── relnotes/
```

```yaml
schema: docushift.csh/1
product: bw
version: 6.12.0
engine: flare
counts: { topics: 358, ambiguous: 5, unresolved: 0 }

topics:
  "bw_java_bw_java_xmltojava":
    doc_set: bw-ent-html
    file: bw-ent-html/binding-palette/xml-to-java.md
```

and the topics themselves carry their identifiers in frontmatter:

```yaml
---
title: REST reference
csh: ["bw_rest_binding", "restBindingRef"]
---
```

A version whose package contains no help map — around a quarter of them do not — gets **no `csh.yml`**. An empty map file would be indistinguishable from a failed run.

### Inspecting and checking it

```bash
# What identifiers does this version publish?
docushift csh list --product businessworks --version 6.12.0

# Coverage across a run: sources found, identifiers resolved, anything unresolved
docushift csh report --batch poc-1

# Integrity: every mapped topic exists, frontmatter and csh.yml agree,
# and nothing the previous version published has gone missing
docushift csh validate --product businessworks --version 6.12.0
```

`docushift extract` already prints the tally (`CSH: 3 sources, 561 entries`), so a version with no help map is visible before you spend a conversion on it.

### Four things worth knowing

**Every help format in the corpus is read.** MadCap Flare, SDL DITA and WebWorks all ship context-sensitive help in their own format, and DocuShift reads all three. DocBook is the exception, and only because it has no CSH to read. So `_has_csh=false` means this version ships no help map, not that we declined to look at one.

**There is one identifier, and it is a string.** In DITA it is the key of the context map; in WebWorks it is the dotted name the help viewer is called with (`as400.palette.gettingstartedurl`). In Flare, the numeric `ResolvedId` is deliberately not carried through: 15% of the alias files surveyed reuse an id for two different topics *within one file*, so it cannot address a page and is not an identifier. What you get is the alias name. It is a string, and always quoted, because 7.5% of the Flare names in the corpus are pure digits (`12`, `1000`, `1122`) and a digit-only identifier must not load as a number.

**Identifiers are case-sensitive, and the difference is load-bearing.** TIBCO BC 7.4 and 7.5 both ship `GatewayInstances` and `gatewayInstances` as *different* help targets pointing at different pages. (This is a Flare hazard specifically — WebWorks and DITA identifiers collide neither by case nor by digits — but nothing case-folds regardless.) Nothing in the pipeline case-folds an identifier, and neither should anything downstream — with the integer gone, case is the only thing keeping those two apart.

**Identifiers are merged across the version's doc-sets.** A version can ship several help outputs (`bw-ent-html`, `bwce-html`, `relnotes`), and Flare frequently copies one output's alias file into a sibling where none of its topics exist. Resolving version-wide rather than per-output fixes those: in TIBCO BusinessWorks, the release-notes alias file resolves 0 of 203 links on its own and 203 of 203 against the main output. Where two outputs genuinely disagree about a name, the larger output wins and the alternative is recorded under `also:` — nothing is dropped. WebWorks does not have the copied-alias problem at all (its links resolve where they sit, every time), but it does ship several books per version, so the `also:` case still comes up.

Full design and the corpus evidence behind it: `architecture.md` §5.3.
