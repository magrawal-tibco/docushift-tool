# DocuShift User Guide: Migration & Conversion CLI

> **Document Status:** Living User Manual  
> **Last Updated:** 2026-09-11  
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

> **Implementation status.** The command tree below is the full intended surface and `--help` reflects it. Implemented today: `doctor`, the **whole `catalog` group, `fetch` included** — discovery talks to the live docsite — **`download` and `archive download`**, including `--from-file`, and **`extract`** in full — it unpacks a package, detects its engine, inventories its assets and CSH sources, and writes the five inventory columns back to `versions.csv`. `convert` and everything downstream are not built at all. Every unbuilt command exits non-zero naming the phase that will build it (see `docs/planning.md`); commands are never silently no-op.

---

## 2. Managing the Additive Product Catalog

The catalog is **two CSV files**, designed to be edited directly in Excel:

| File | Contents |
| :--- | :--- |
| `config/products.csv` | One row per product — `slug`, `product_code`, `bu`, `family`, display name |
| `config/versions.csv` | One row per version — the `convert_eligible` toggle, the `convert_batch` run label, `zip_url` / `zip_source`, `is_archived`, and the detected `engine` |

They join on `slug`, the product's `docs.tibco.com` slug. It is additive, distinguishes Active vs Archived versions, and **preserves your edits automatically** — see "How your edits are protected" below.

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

# Re-apply support's end-of-support report without re-crawling
docushift catalog eos
```

**A scope is required.** A bare `catalog fetch` would crawl the entire A-to-Z list, so it asks for `--all` or one of `--bu` / `--family` / `--product` / `--batch` instead of assuming. `--version` is rejected: discovery works a product at a time, and fetching one version would make the others look deleted.

`--product` accepts a **docsite slug or a product code**. The two are usually different — `ems` is published as `tibco-enterprise-message-service` — and the slug is the catalog's key, so it is what `catalog list` and `catalog show` print back at you. The code still works for a product already in `products.csv`: it is looked up and the slug is used behind the scenes. For a product you have never fetched, pass the slug from its `docs.tibco.com` URL. If nothing matches, the error says so and suggests the slug.

Ten product codes name **more than one product** (`spotfire`, `clarity-dt`, `stat-sts` and seven others), and one of those pairs is split across the scope boundary. Passing an ambiguous code is refused rather than resolved to whichever product sorted first:

```
Error: 'stat-sts' is a product_code shared by 2 products, and product_code is not unique.
       Pass one of these slugs instead: spotfire-service-for-statistica,
       tibco-data-science-service-for-tibco-spotfire
```

Useful flags:

| Flag | Effect |
| :--- | :--- |
| `--dry-run` | Runs the whole crawl and merge, prints the counts, writes nothing. Worth doing first on `--all`. |
| `--allow-deletes` | Permits removal of versions discovery no longer returns. Without it, a disappearing version **aborts** the merge — an upstream outage should not silently prune your catalog. |
| `--no-include-archived` | Skips the archive index. Faster; leaves you without version history. |

What it prints: a table of added / updated / unchanged / protected counts, a dim line counting entries skipped as unversioned or not publicly visible (roughly 70 of the 739 A-to-Z entries are employee-only), what support's end-of-support report retires, any catalog warnings, and — if some products could not be reached — how many. **A product that fails is left exactly as it was**, never emptied, so a partial crawl cannot look like a mass deletion.

### Choosing which versions get converted

Four columns, answering four different questions:

| Column | File | Question | Default |
| :--- | :--- | :--- | :--- |
| `in_scope` | `products.csv` | *May **this product** ever be converted?* | `true` |
| `release_status` | `versions.csv` | *Is this version still supported?* | `unknown` (from support's report) |
| `convert_eligible` | `versions.csv` | *May this version ever be converted?* | `true` for active, `false` for archived |
| `convert_batch` | `versions.csv` | *Is it in **this** run?* | empty (not scheduled) |

Three of the four are yours. `release_status` is not — it comes from support's end-of-support report, and only the value `retired` blocks anything.

Use `convert_eligible` for permanent policy — this version is out of scope, full stop. Use `convert_batch` to scope a run: tag the handful of rows you want with a label like `poc-1` or `wave-2` and pass `--batch poc-1` to the pipeline. Nothing else in the sheet has to move.

```bash
# Scope a POC to two versions
docushift catalog set --product ems --version 10.4.0 --batch poc-1
docushift catalog set --product dsp_gridserver --version 7.1.1 --batch poc-1

# Check the scope before running anything
docushift catalog batches
docushift catalog list --batch poc-1

# Run the pipeline over just those two
docushift download --batch poc-1
docushift extract  --batch poc-1
docushift convert  --batch poc-1
```

For anything larger than a handful, the spreadsheet is faster: filter `versions.csv` by `_family`, select the `convert_batch` column, and fill down `wave-2`. Values are lowercased on save, so `POC-1` and `poc-1` are the same batch. To unschedule a version, clear the cell (or pass `--batch ""`).

**The columns compose, outside in.** A version tagged `poc-1` but left `convert_eligible=false` is skipped, not converted; so is one support has retired; and so is any version of a product with `in_scope=false`, whatever its own three columns say. `catalog import` warns about all three combinations by name — and says which gate closed, since each is undone differently.

#### Products that are never converted

Some products are excluded permanently — as of 2026-09-09 that is 61 EBX and Spotfire products. The list lives in `config/scope.yaml`, keyed by the product's **docsite slug**:

```yaml
out_of_scope:
  - slug: tibco-ebx
    display_name: TIBCO EBX®
    reason: EBX and Spotfire are out of scope for migration (2026-09-09)
```

Every `catalog fetch` re-applies the file, so a version of an excluded product discovered next quarter is excluded the moment it appears — which is the whole point of putting it here rather than clearing `convert_eligible` on the rows you can see today. The tool writes the result into `products.csv` as `in_scope=false, scope_source=scope_rule`.

Excluded products are **still fully catalogued**: they appear in `products.csv`, all their versions appear in `versions.csv`, and they are counted in every inventory. They are simply never downloaded, extracted, converted or laid out. `docushift catalog list --out-of-scope` shows them.

To readmit one product without editing the YAML:

```bash
docushift catalog set --product ebx --in-scope
```

That sets `scope_source=manual`, which outranks the rule file — no later fetch will undo it. To exclude a product not on the list, either add it to `scope.yaml` (durable, reviewable) or run `catalog set --product X --out-of-scope` for a one-off.

Two things to know if you edit `products.csv` by hand. An **empty `in_scope` cell means in scope** — only the literal `false` excludes, so a row you type in yourself cannot vanish from the pipeline by omission. And **deleting a slug from `scope.yaml` really does restore the product**: the next fetch resets it to `in_scope=true, scope_source=default`. The one thing a fetch will not touch is a `manual` decision.

> **Slugs are matched exactly.** `slug: ebx` matches nothing, and a substring rule would be worse than useless — `ebx` appears inside `tibco-businessconnect-ebxml-protocol`, which is an unrelated product that *is* in scope. If you add an entry, copy the slug from `products.csv`. Any rule that matches no product is reported after every fetch, which is how you find out a product was renamed upstream.

#### Versions support has retired

Support publishes an end-of-support report, and **a version it marks `Retired` is not converted** — there is no point publishing fresh documentation for software nobody supports. On the 2026-09-10 report that removes 128 versions from the work and leaves 11 products with nothing convertible at all.

The report is committed as-is under `config/eos/`, and `config/eos.yaml` names the active one:

```yaml
report: eos/EOS-Report-2026-09-10.csv
aliases:
  - report_name: "TIBCO Data Streams"   # what the report calls it
    slug: spotfire-data-streams         # what the docsite calls it
```

The aliases exist because the report carries product **names** and the catalog is keyed on **slugs**. Most names slugify straight onto a product; fourteen do not, and each of those mappings was checked by hand against the two version lists before being added.

Three columns in `versions.csv` record the result:

| Column | Values |
| :--- | :--- |
| `release_status` | `retired` (blocks conversion) · `retirement-announced` (a dated warning; still supported, still converted) · `ga` · `unknown` |
| `retirement_date` | ISO, from the report |
| `release_status_source` | `eos_report` · `manual` · `unknown` |

**`unknown` means the report said nothing, not that the version is retired.** Support tracks 528 product names, 251 of which match something in this catalog — so most of the catalog is `unknown`, and all of it converts normally.

When a new report arrives, drop it in `config/eos/`, point `eos.yaml` at it, and run:

```bash
docushift catalog eos
```

That re-applies the report to every row and prints what changed, how many products the report actually covers, and — named in full, never as a count — every product it leaves with nothing to publish. `catalog fetch` does the same thing, but only as a side effect of re-crawling the whole docsite, which takes about an hour.

To see what is being skipped, and to convert something anyway:

```bash
docushift catalog list --retired
docushift catalog set --product ems --version 8.6.0 --release-status ga
```

The override sets `release_status_source=manual`, which outranks the report permanently — no fetch and no new report will undo it. The retirement date stays in the row, because support really did retire the version on that day; you have decided to convert it regardless. The same flag works the other way (`--release-status retired`) for a version you want skipped before the report catches up.

Removing a row from the report, or removing a wrong alias, **restores the version** on the next `catalog eos` — the tool resets anything it set itself. And as with scope, retired versions stay fully catalogued: they keep their rows, their dates and their place in every inventory. They are just never downloaded, extracted, converted or laid out.

> **An alias that stops matching is reported.** If support renames a product, its alias silently stops retiring anything — so `catalog eos` and `catalog import` both name any alias the active report no longer mentions. That warning is the only sign you would get.

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

That copies your file into `families/en-us-tib-data-management/downloads/ebx-6.2.0.zip`,
sets `zip_source=manual` on the row, and records its checksum. From then on `extract`,
`convert`, and `sync` treat it as an ordinary package — nothing downstream needs to know
where it came from. Your original file is copied, not moved.

If the version is not in `versions.csv` at all, the row is added for you with a warning —
you are holding the package, which is better evidence that the version exists than
discovery's silence is that it does not. An unknown **product**, though, is an error: run
`docushift catalog fetch --product <code>` first, so a typo cannot seed a junk row.

For an archived version, the same flag is on the archive utility:

```bash
docushift archive download --product ems --version 8.6.0 --from-file "D:\downloads\ems-86.zip"
```

That one does **not** set `zip_source=manual`, because `zip_source` says where the
*pipeline's* package for a version comes from and a reference ZIP in `archive/` is not
that — pinning it would make `download` skip a version whose real package you never
supplied.

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

The ZIP lands in `archive/`, deliberately outside `downloads/` — `downloads/` is the pipeline's working set, and a reference ZIP sitting there would look to `extract` like a package awaiting conversion. `--extract` unpacks into `archive/<slug>-<version>/` for the same reason. A ZIP already present is left alone unless you pass `--force`.

Archived `zip_url` values are the ones most likely to be stale, so if the fetch has nothing to work from the command tells you to obtain the file and re-run with `--from-file` rather than failing obscurely.

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
- **Warnings do not.** A family not yet declared in `taxonomy.yaml`, a version tagged into a batch but left `convert_eligible=false` or retired by support, a `zip_source=manual` row that discovery has since found a real URL for, or an alias in `eos.yaml` the active report no longer mentions. All are states you may have chosen deliberately, so they are reported and the write proceeds.

### Editing from the command line

`catalog set` is the scriptable equivalent of editing a cell, and it records provenance for you:

```bash
# Product row (products.csv)
docushift catalog set --product ems --family messaging     # also sets family_source=manual
docushift catalog set --product ems --bu tibco
docushift catalog set --product ems --display-name "TIBCO Enterprise Message Service"
docushift catalog set --product ebx --in-scope                # also sets scope_source=manual

# Version row (versions.csv) — every one of these requires --version
docushift catalog set --product ems --version 8.6.0 --engine webworks
docushift catalog set --product ems --version 8.6.0 --zip-url https://internal/mirror.zip
docushift catalog set --product ems --version 10.4.0 --batch poc-1
docushift catalog set --product ems --version 8.6.0 --release-status ga    # convert it despite the report
docushift catalog set --product dsp_gridserver --version 7.1.1 --zip-source auto   # undo a manual pin
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
     Accepted; workspace folder -> families/en-us-tib-streaming-analytics.
     Add it to taxonomy.yaml to silence this.
```

This is a warning, not an error: the write goes through. Add the family under `business_units.<bu>.families` in `config/taxonomy.yaml` once you have settled on it, both to silence the warning and to give it a display name. The warning also catches the other case — if you see one for `mesaging`, that is a typo about to become its own folder.

---

## 3. The Families Workspace

Downloaded ZIPs and extracted packages are organized by **family**, under a git-ignored `families/` directory. The folder name is `{locale}-{bu}-{family}`, using the short `repo_slug` tokens from `taxonomy.yaml` (`tibco` → `tib`):

```
families/
└── en-us-tib-messaging/
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

- The family is **hyphenated** even though `taxonomy.yaml` keys are underscored: `data_management` → `en-us-tib-data-management`.
- Trademark symbols are stripped, so `TIBCO EBX®` slugs to `tibco-ebx`.
- Versions keep their dots (`10.4.0`, not `10-4-0`) so the folder maps back to a `versions.csv` row unambiguously.
- **This is not a repository name.** One family publishes into two or three trees (§8), so the workspace keeps the short, suffix-free stem and `sync` composes the destination name. `docushift doctor` prints which tree the current locale publishes to.
- The `en-us` prefix is fixed today, and other locales exist upstream. A localized run keeps its own locale here — those are different ZIPs and must not overwrite the English ones — even though all of them publish into the single `loc-` tree.

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

Versions with `convert_eligible=false` are excluded regardless of the selector, and so are versions support has retired (`release_status=retired`) and every version of a product with `in_scope=false` — `--product ebx --all` selects nothing.

### Download Documentation ZIPs
Downloads eligible versions into `families/<locale>-<bu>-<family>/downloads/`:
```bash
# Download all eligible packages in catalog
docushift download --all

# Download a specific BU, Family, Product, or scheduled batch
docushift download --bu tibco --family integration
docushift download --product businessevents-enterprise --version 6.4.0
docushift download --batch poc-1

# See what would be fetched, and where, without writing anything
docushift download --all --dry-run

# Supply a ZIP by hand when discovery has no usable URL (single version only)
docushift download --product ebx --version 6.2.0 --from-file "D:\downloads\ebx-docs.zip"
```

| Flag | Effect |
| :--- | :--- |
| `--dry-run` | Prints the product, version, source and target path for every version the selector picks, and stops. |
| `--force` | Re-fetches even when the local ZIP's checksum still matches. Does **not** override a `zip_source=manual` pin. |
| `--workers N` | How many versions download at once. Defaults to `crawl.max_concurrent_requests` in `config/docsite.yaml` (4). |
| `--from-file PATH` | Files a ZIP you already have instead of fetching. Needs both `--product` and `--version`. |

Archived versions are never downloaded here — use `docushift archive download` for those.
Versions pinned with `zip_source=manual` are skipped: their package is already in place.

Every run ends with five counts — downloaded, already current, skipped (manual), no
`zip_url`, failed — and the last two are listed by name, because those are the rows you
have to do something about. **A failure never stops the run**: one unreachable product
out of two hundred is a report line, not an aborted batch.

Downloads resume. An interrupted transfer leaves a `.part` file next to the target and
the next run continues from where it stopped, provided the server still reports the same
file; if the file changed upstream, the partial is discarded and the download restarts
rather than producing a plausible-looking corrupt archive. Nothing is ever written to the
final path until the whole ZIP has arrived and been checked, so a killed run cannot leave
a truncated package that a later run would trust.

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

| Flag | Effect |
| :--- | :--- |
| `--dry-run` | List what would be unpacked, and whether each package is on disk, without writing. |
| `--force` | Re-extract even when the package has not changed since last time. |

Each run ends with five counts — extracted, already current, no package, refused, failed —
an engine tally, and then **two named lists**: the versions left `auto`, and the versions
whose engine was identified but has no converter. Those are different problems. `auto`
means DocuShift could not tell what made the package and is worth reporting as a gap;
a named engine with no converter is a scoping question for you, not a bug. A failure
never stops the run.

**Re-running is cheap and re-running is safe.** A package whose bytes have not changed
since the last extract is skipped entirely, so `extract --all` over a settled batch does
almost no work. When a package *has* changed, the new tree is built beside the old one and
swapped in, so files the new package no longer ships are gone rather than lingering — a
guide dropped upstream does not quietly survive and convert. If a run is killed mid-swap
you may find a a `.part` directory left behind; the next run removes it before it starts.

Extraction is deliberately serial. Downloads run in parallel because transfers overlap;
two large unzips onto one disk only contend, so there is no `--workers` here.

**A package that tries to write outside its own folder is refused, not repaired**, and
nothing from it is left on disk. That is counted separately from a failure because a
retry will not help — somebody needs to look at the ZIP.

**Extract measures the packages it unpacked, in one walk, and prints four things.** All four name the version they came from, because a total nobody can trace back to a package is not something anybody can act on.

First, the help maps:

```
CSH: 3 source(s), 561 identifier(s).
! businessworks@6.8.0: guide/Data/Alias.xml is unparseable
```

A `!` line is a help map that was found and would not read. That is a different fact from a version with no help map at all, and only one of the two is acceptable to discover after publishing.

Then the asset table, **by category and by destination** rather than by extension. Every file is in it, topics included, so the `Files` column sums to what was unpacked:

```
              Assets
Category   Destination     Files      Size
topic      api-reference   8,904   412.3 MB
topic      output-root     4,110   180.6 MB
image      output-root     2,341     1.2 GB
skin       output-root       880    12.4 MB
document   document-router    12    46.8 MB
other      unclaimed         512     3.1 MB
```

`skin` is decided by *where* a file is, not by its extension — a `.gif` in `Skins/` is chrome and a `.gif` beside a topic is an image. Roughly half of a DITA package's references and three-quarters of a WebWorks one's are chrome, so this is not a rounding error.

Then the residue — files no destination claimed, grouped by their top folder:

```
? bpme@5.6.0: 498 unclaimed file(s) in components-api/ (14.2 MB) -- no destination
```

This is the group to read. A handful of stray files is normal; a few thousand under one folder name means a generated reference tree the tool has not learned to recognise, and it should be reported rather than converted.

And last, the API-reference triage:

```
? ftl@6.10.0: html/api-docs/ 412 file(s), no known generator marker
```

A directory whose *name* looks like an API reference but which carries no generator marker. **It is a question, not a classification** — the files stay in `_doc_files`, and the count stays out of `_api_files`, until somebody looks and a marker is added. A directory is only ever classified by what it contains: `api-exchange-gateway/` is a product name with 15,677 files of ordinary documentation, and any rule that reads names would throw the lot away.

```bash
# Convert all downloaded packages
docushift convert --all

# Convert a specific product version, or a whole batch
docushift convert --product businessevents-enterprise --version 6.4.0
docushift convert --batch poc-1

# Convert a local standalone folder directly
docushift convert \
  --input ./families/en-us-tib-integration/extracted/businessevents-enterprise/6.4.0 \
  --output ./output/tibco/integration/businessevents-enterprise/6.4.0
```

Conversion also writes the version's context-sensitive help map (`csh.yml`) and stamps the
matching identifiers into topic frontmatter — see §7.

**Conversion copies an asset because a topic referenced it, and it copies it at the moment it writes the link.** There is no extension allow-list and no separate copying pass: the two happen together, so a relative image link in the output always has a file at the other end. Each asset keeps the path it had relative to its topic, so nothing is renamed, flattened or de-duplicated. Three things get reported rather than copied:

- **Skipped skin.** Most references in a help package point at the generator's own chrome — SDL's `static/`, WebWorks' `tpl/`, Flare's `Skins/`. Half to three-quarters of all references are these. They are counted and dropped.
- **Unreferenced assets.** Images no topic points at are named in the report and left behind — over half of a typical Flare image library. That is normal; MadCap projects accumulate.
- **References that resolve to nothing.** These are counted **grouped by folder**, because that is how they cluster: a broken reference usually means one generated tree whose source was already broken, not scattered per-file loss. A count spread thinly across many folders is a tool problem; a few thousand under one folder is the package.

Case mismatches are reported and not fixed. If a topic says `Images/Logo.png` and the file is `images/logo.png`, conversion copies the file as it found it and tells you — the link works on Windows and breaks once published to a case-sensitive host, so it needs a source fix, not a silent rewrite.

### AEM Synthesis & Publishing Layout
```bash
# Organize converted AEM files into repo-shaped folders on disk
docushift sync --target-dir ../tibco-docs-aem/

# Run link and asset integrity validation
docushift validate --target-dir ../tibco-docs-aem/
```

> **`sync` writes folders, not commits.** DocuShift stops at the filesystem: it never runs a git command, creates no repository and pushes nothing. The two trees it writes per family are named exactly as the publishing repositories are, so taking them the rest of the way is a copy into a clone — done by you, by a CI job, or by whatever owns those repositories. That also means you can run `sync` and read the result without any GitHub credentials.

**What sync writes.** Two trees per family, named from the family workspace stem (§3) plus a publishing suffix — the workspace itself is not a repository name:

```
en-us-tib-messaging-userdocs/           # the docs tree — what a reader reads
└── en-us/ems/
    ├── online-help/10-4-0/…            # converted Markdown, toc.yml, nav.yml, meta.yml, csh.yml
    ├── user-guides/10-4-0/…            # user-guide PDFs + index.md, toc.yml
    ├── release-information/10-4-0/…    # release notes + readme + index.md, toc.yml
    └── reference-documents/10-4-0/…    # VPAT, licence, rest of doc/ + index.md, toc.yml

en-us-tib-messaging-userdocs-resources/ # the bulk tree
└── en-us/ems/
    ├── api-references/java/10-4-0/…    # Javadoc and the C / Go / tibdg trees
    └── archives/…                      # archived-version ZIPs + index.md, toc.yml
```

Eight things to expect:

- **A non-`en-us` run publishes into `loc-tib-messaging-userdocs` and gets no `-resources` tree.** All localized content shares one docs tree rather than getting one per language, and API references and archives are English-only. Asking for a localized resources tree is an error, not an empty directory.

- **`nav.yml` and `meta.yml` are placeholders — do not build on their shape yet.** `toc.yml`, `index.md` and `csh.yml` are specified and stable; those two are not. The AEM side has not supplied a spec for either, so `config/aem_templates/nav.yml.j2` and `meta.yml.j2` still hold the scaffolding shapes the project started with, and both templates say so at the top. They will be rewritten against the real requirements when those arrive, which is likely to change their field names. `validate` therefore checks that the files exist and parse, and asserts nothing about their content.
- **The PDF doc-classes get an index too.** `user-guides/`, `release-information/` and `reference-documents/` each receive a generated `index.md` and `toc.yml` listing their files, so a copied PDF is reachable. Titles come from the document kind where the name identifies one (Release Notes, VPAT, License Agreement), otherwise from the PDF's own metadata, otherwise from the filename. A doc-class with no files gets no folder at all rather than an empty index.
- **`archives/` is indexed from the catalog, so it lists every archived version — including the ones you have not downloaded.** Entries whose ZIP is not in the repository link to the docsite instead, and the index says which is which. That is deliberate: `archives/` exists to be the complete product history, and `archive download` is what fills it in. `api-references/` gets no generated index — Javadoc ships its own.
- **Versions are dashed here** (`10.4.0` → `10-4-0`) and nowhere else. The catalog and the `families/` workspace keep the dots.
- **API references are never converted.** Javadoc is copied through as HTML, and topic links into it are rewritten to absolute URLs on the AEM host. Set that host in `config/publishing.yaml` (`publish_base_url`) before your first sync — the path after it is derived, not configured.
- **`validate` skips those absolute links by default.** They point at a different repository, so there is nothing on disk to check; pass `--check-external` to verify them over HTTP.
- **A broken relative asset link is a tool bug, not a content finding.** Conversion writes the link and copies the file in one step, so `validate` finding one means something downstream moved a file without moving its link — it is reported as a regression, with the stage that could have caused it. An asset that nothing links to is not an error and is not reported here; that count belongs to `convert`.

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

`docushift extract` already prints the tally (`CSH: 3 source(s), 561 identifier(s).`), so a version with no help map is visible before you spend a conversion on it.

### Four things worth knowing

**Every help format in the corpus is read.** MadCap Flare, SDL DITA and WebWorks all ship context-sensitive help in their own format, and DocuShift reads all three. DocBook is the exception, and only because it has no CSH to read. So `_has_csh=false` means this version ships no help map, not that we declined to look at one.

**There is one identifier, and it is a string.** In DITA it is the key of the context map; in WebWorks it is the dotted name the help viewer is called with (`as400.palette.gettingstartedurl`). In Flare, the numeric `ResolvedId` is deliberately not carried through: 15% of the alias files surveyed reuse an id for two different topics *within one file*, so it cannot address a page and is not an identifier. What you get is the alias name. It is a string, and always quoted, because 7.5% of the Flare names in the corpus are pure digits (`12`, `1000`, `1122`) and a digit-only identifier must not load as a number.

**Identifiers are case-sensitive, and the difference is load-bearing.** TIBCO BC 7.4 and 7.5 both ship `GatewayInstances` and `gatewayInstances` as *different* help targets pointing at different pages. (This is a Flare hazard specifically — WebWorks and DITA identifiers collide neither by case nor by digits — but nothing case-folds regardless.) Nothing in the pipeline case-folds an identifier, and neither should anything downstream — with the integer gone, case is the only thing keeping those two apart.

**Identifiers are merged across the version's doc-sets.** A version can ship several help outputs (`bw-ent-html`, `bwce-html`, `relnotes`), and Flare frequently copies one output's alias file into a sibling where none of its topics exist. Resolving version-wide rather than per-output fixes those: in TIBCO BusinessWorks, the release-notes alias file resolves 0 of 203 links on its own and 203 of 203 against the main output. Where two outputs genuinely disagree about a name, the larger output wins and the alternative is recorded under `also:` — nothing is dropped. WebWorks does not have the copied-alias problem at all (its links resolve where they sit, every time), but it does ship several books per version, so the `also:` case still comes up.

Full design and the corpus evidence behind it: `architecture.md` §5.4.
