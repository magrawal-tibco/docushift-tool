# DocuShift User Guide: Migration & Conversion CLI

> **Document Status:** Living User Manual  
> **Last Updated:** 2026-09-11  
> **Target Environment:** TIBCO & IBI Documentation Migration to AEM

> **First time through?** [`quickstart.md`](quickstart.md) walks one product from `catalog fetch` to `validate` in nine commands, and links back here at each step. This guide is the reference; that one is the path.

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

> **Implementation status.** The command tree below is the full intended surface and `--help` reflects it. Implemented today: `doctor`, the **whole `catalog` group, `fetch` included** — discovery talks to the live docsite — **`download` and `archive download`**, including `--from-file`, and **`extract`** in full — it unpacks a package, detects its engine, inventories its assets and CSH sources, and writes the five inventory columns back to `versions.csv`. **`convert` converts all four engines — MadCap Flare, SDL DITA, WebWorks and DocBook** — the engine-neutral spine (asset resolution, CSH, frontmatter, the build-and-swap, the report and the findings register) plus four engines' readers, which between them are every eligible version in the corpus. A version on a recognised but unconvertible engine reports `Engine unknown` and is skipped by name (see §4). Everything downstream of `convert` is not built at all. Every unbuilt command exits non-zero naming the phase that will build it (see `docs/planning.md`); commands are never silently no-op.

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

# Re-apply the docsite team's migration export (records a verdict; gates nothing)
docushift catalog migrate
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
| `--allow-deletes` | Permits removal of versions discovery no longer returns. Without it, a disappearing version **aborts** the merge — an upstream outage should not silently prune your catalog. Two absences never count: archived versions of a product whose archive index was skipped or failed, and a version you added with `download --from-file` that discovery has never listed (named after the merge). |
| `--no-include-archived` | Skips the archive index. Faster; leaves you without version history. Archived rows already in the catalog are kept as they are. |

What it prints: a table of added / updated / unchanged / protected counts, a dim line counting entries skipped as unversioned or not publicly visible (roughly 70 of the 739 A-to-Z entries are employee-only), what support's end-of-support report retires, any catalog warnings, and — if some products could not be reached — how many. **A product that fails is left exactly as it was**, never emptied, so a partial crawl cannot look like a mass deletion.

One line is worth reading closely when it appears:

```
2 product(s) are listed with versions but yielded none: ibi, tibco-spotfire-for-apple-ipad
Discovery could not read their versions -- missing from the catalog, not empty upstream.
```

This is **not** the dim skipped-entries line above it, and the two are deliberately separate. A skipped entry is a licence page with nothing to convert — the docsite working as intended. A product on *this* line is one the A-to-Z index says has versions, which means the tool could not read what the docsite published, and the product is absent from your catalog as a result. It is named rather than counted because the first question is always *which product*. Two currently appear and both are genuine: `ibi` is a documents hub and `tibco-spotfire-for-apple-ipad` is retired, and neither publishes a version number the index nonetheless counts. If a product you expect to convert shows up here, that is a bug to report, not a setting to change.

*(Until 2026-09-23 these were folded into the skipped-entries count, which is how 34 products and ~683 versions — `tibco-streaming` and `tibco-flogo` among them — stayed out of the catalog while a number that said "nothing to convert here" was printed on every fetch.)*

### Choosing which versions get converted

Four columns, answering four different questions:

| Column | File | Question | Default |
| :--- | :--- | :--- | :--- |
| `in_scope` | `products.csv` | *May **this product** ever be converted?* | `true` |
| `release_status` | `versions.csv` | *Is this version still supported?* | `unknown` (from support's report) |
| `convert_eligible` | `versions.csv` | *May this version ever be converted?* | `true` for active, `false` for archived |
| `convert_batch` | `versions.csv` | *Is it in **this** run?* | empty (not scheduled) |

Three of the four are yours. `release_status` is not — it comes from support's end-of-support report, and only the value `retired` blocks anything.

There is a fifth column, `migrate_decision`, and it is **not** on this list on purpose: it records what the docsite team decided, and gates nothing at all. See [The docsite team's verdict](#the-docsite-teams-verdict) below.

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

Two things to know if you edit `products.csv` by hand. An **empty `in_scope` cell means in scope** — only the literal `false` excludes, so a row you type in yourself cannot vanish from the pipeline by omission. And **deleting a slug from `scope.yaml` really does restore the product**: the next fetch resets it to `in_scope=true, scope_source=default`. The one thing a fetch will not touch is a `manual` decision — and typing `true` or `false` into `in_scope` makes one: the next fetch sees a value the rule file could not have written and sets `scope_source=manual` for you.

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

The override sets `release_status_source=manual`, which outranks the report permanently — no fetch and no new report will undo it. The retirement date stays in the row, because support really did retire the version on that day; you have decided to convert it regardless. The same flag works the other way (`--release-status retired`) for a version you want skipped before the report catches up. Typing the new status straight into `versions.csv` works too: the next fetch or `catalog eos` notices that the row no longer holds what the report wrote and sets `release_status_source=manual` itself. The same goes for `migrate_decision`.

Removing a row from the report, or removing a wrong alias, **restores the version** on the next `catalog eos` — the tool resets anything it set itself. And as with scope, retired versions stay fully catalogued: they keep their rows, their dates and their place in every inventory. They are just never downloaded, extracted, converted or laid out.

> **An alias that stops matching is reported.** If support renames a product, its alias silently stops retiring anything — so `catalog eos` and `catalog import` both name any alias the active report no longer mentions. That warning is the only sign you would get.

#### The docsite team's verdict

The docsite team keeps its own list of what moves to the new TIBCO docsite. That list is an editorial judgement made by people, and it is **not** the same question as `convert_eligible` — which, in the catalog as it stands, is a mirror of `is_archived` and nothing more. So the verdict is imported into its own column and **changes nothing**:

| Column | Values |
| :--- | :--- |
| `migrate_decision` | `migrate` · `do_not_migrate` · `unknown` |
| `migrate_decision_source` | `docsite_sheet` · `manual` · `unknown` |

Nothing downstream reads either one. No version is downloaded, skipped, converted or excluded because of them. The column exists so that the disagreement between the two lists is *visible* and can be settled row by row, by a human, rather than resolved silently by whichever list was imported last.

The export is committed under `config/migration/` and `config/docsite-migration.yaml` names the active one, the same shape as `eos.yaml`:

```yaml
sheet: migration/tibco-docsite-2026-09-03.csv
decision_column: Migrate to New TIBCO Docsite
aliases: []
```

The join key is the **slug**, recovered from the export's `doc_url` (the trailing `-10-4-0` version suffix is stripped). Where the export's slug is not the catalog's, add an alias exactly as you would for the EOS report. To re-apply an export:

```bash
docushift catalog migrate
```

That prints the verdict crossed against eligibility, and this is the whole point of the command:

```
| migrate_decision | eligible | not eligible |
| migrate          |      955 |           88 |
| do_not_migrate   |      370 |         1899 |
The export decides 3312 of 5181 catalogued versions; 1869 have no row in it and read 'unknown'.
WARN 458 version(s) disagree with convert_eligible (88 wanted but ineligible, 370 eligible but
     declined). Nothing was changed for them.
WARN 104 export slug(s) match no catalogued product -- 410 row(s), 91 of them marked migrate.
```

The two yellow cells are the work: 88 versions the docsite team wants that the catalog will not convert, and 370 the catalog will convert that the docsite team declined. Every one is also recorded as a `MIGRATE_DECISION_CONFLICT` finding, so `docushift report` lists them individually. `catalog show` marks them too — a disagreeing row reads `no (migrate)` in its Eligible cell instead of a bare `no`.

Settle one either way, and the decision sticks:

```bash
docushift catalog set --product ems --version 8.6.0 --migrate-decision migrate  # the verdict was wrong
docushift catalog enable --product ems --version 8.6.0                          # the catalog was wrong
```

`--migrate-decision` sets `migrate_decision_source=manual`, which outranks the export permanently — no fetch and no later export will undo it.

As with the EOS report, **absence is not a decision**: 1,869 versions have no row in the export and read `unknown`, which means nobody has looked, not that they were declined. Dropping a row from a new export resets that version back to `unknown` on the next `catalog migrate`, an alias that matches nothing in the export is reported, and a decision token the tool cannot read is reported rather than guessed at.

### What's actually in the package

Choosing a batch means judging packages you have not opened. `docushift extract` writes five read-only columns back into `versions.csv` so that after one exploratory extract, the sheet itself tells you:

| Column | Reads as |
| :--- | :--- |
| `_has_csh` | This version ships context-sensitive help, so it will get a `csh.yml`. Its Help button breaks if the identifiers do not survive — budget for verification. |
| `_csh_names` | How many help identifiers have to resolve. |
| `_has_api_ref` | It carries a Javadoc / C / Go / `tibdg` tree. That tree is **copied, never converted**, and publishes to the `-resources` repo. |
| `_api_files` | How much of the package that tree is. |
| `_doc_files` | Everything else — HTML, images, CSS, PDFs. A size figure, not a topic count. |

And `docushift convert` writes two more, so the sheet carries both ends of the pipeline:

| Column | Reads as |
| :--- | :--- |
| `_md_files` | Markdown pages produced — converted topics plus the landing and container pages the tool generated. |
| `_out_files` | Everything in the converted tree: the Markdown, the images and CSS that were actually referenced and copied, and the `toc.yml` / `metadata.yml` / `csh.yml` beside them. |

**Read `_doc_files` → `_out_files` as the before and after.** `_api_files` has no counterpart on purpose: an API-reference tree is copied verbatim rather than converted, so its file count is the same at both ends and the column already on the row is the answer.

Expect the output to be much smaller than the input, and expect the ratio to move. On the first six versions measured, 4,272 source files became 2,162 — but that is 67% for one product and 9% for another, because a Flare package's file count is mostly skin chrome and unreferenced images, and none of that is copied. A number far below its neighbours is worth one look before you tag the batch: it is usually correct, and occasionally a guide that did not convert.

Three readings worth knowing:

- **An empty cell is not a zero.** Blank means the version has never been extracted (or, for the last two, never converted). `0` means it was, and there was nothing there.
- **`_has_csh=true` with `_csh_names=0`** means the product ships a help map that yields no identifiers — a normal state, and in fact the *majority* of what we have surveyed: 476 of 863 Flare alias files (55%), 492 of 647 WebWorks `topics.js` (76%), 38 of 418 DITA `head.js` (9%). Worth seeing before conversion rather than after.

```bash
# Extract the batch, then sort versions.csv by _csh_names to see where the CSH risk is
docushift extract --batch poc-1
```

### Active vs Archived Version Rules
- **Active Versions**: `convert_eligible: true` — eligible for download and conversion.
- **Archived Versions**: `convert_eligible: false` — tracked in the catalog for a complete product history, but **never downloaded and never extracted**. Across ~250 products, pulling history nothing reads would dominate bandwidth and disk.

### When the ZIP URL is missing or wrong

> **Changed in Phase 14 (2026-09-19).** For an active version, `download` does not read
> the `zip_url` column at all — it **derives** the endpoint from the template in
> `config/docsite.yaml`, because every templated value that was in the catalog was
> wrong (0 of 35 sampled products resolved). Your `zip_url` still wins where you pinned
> the row with `zip_source=manual`, and an archived row still uses the archive index's
> link verbatim. A version that resolves under no known pattern is reported as
> `ZIP_URL_UNRESOLVED` and is a `--from-file` job, exactly as below.
>
> Two practical consequences. **`catalog show` labels its column `ZIP (stored)`** — on
> an active row that is what the last `catalog fetch` templated, not what `download`
> will use; run **`download --dry-run`** to see the endpoint that would actually be
> fetched. And the stale strings in `versions.csv` are left where they are: the next
> `catalog fetch` rewrites them through the corrected template, and a blanked cell
> could not be told apart from "discovery found nothing". See `planning.md` Phase 14a.
>
> The trap worth knowing either way: **docs.tibco.com answers a missing `/pub/` path
> with HTTP 200 and an empty body.** A URL that "returns 200" in a browser or with
> `curl -I` may still be nothing at all — which is why `download` checks that the bytes
> begin `PK\x03\x04` and reports *"did not return a readable ZIP"* rather than writing
> an empty file and calling it a success.

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

**`family` is assigned by hand, and only by hand.** Nothing else writes it: a `catalog fetch` files every newly discovered product as `unclassified` and leaves the name to you. The `family_source` column in `products.csv` records how each one was set — `manual`, or `unclassified` for anything awaiting you. Two older values, `taxonomy_rule` and `docsite_category`, still appear on products classified before this changed; they are not produced any more.

`catalog triage` prints a suggestion next to each unclassified product when a keyword rule in `taxonomy.yaml` recognises it. It is advice and nothing else — the family is set when you run `catalog set`, not before.

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

### Caching the Docsite's Page List (`catalog sitemap`)

The 301 map has to start at the address each page is served from on docs.tibco.com today. The docsite's Coveo search sitemap lists those addresses — every page of every current version, with its title — and `catalog sitemap` downloads it into `cache/coveo/` so later stages can read it with no network.

```bash
docushift catalog sitemap                                        # every in-scope product (~2,000 files, ~20 min first time)
docushift catalog sitemap --product tibco-enterprise-message-service
```

A re-run fetches only the files whose date changed. It writes `reports/coveo-sitemap.csv`, one row per catalog version: whether the sitemap has a page list for it, and how many pages. Expect archived versions to have none — the sitemap covers current versions only. The summary also counts the files the docsite answered with its login page instead of a sitemap; those products or versions simply have no public page list.

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

Each run ends with six counts — extracted, already current, measured from cache (only
with `--measure-only`), no package, refused, failed — an engine tally, and then **two named lists**: the versions left `auto`, and the versions
whose engine was identified but has no converter. Those are different problems. `auto`
means DocuShift could not tell what made the package and is worth reporting as a gap;
a named engine with no converter is a scoping question for you, not a bug. A failure
never stops the run. That includes a failure *after* the unzip — `versions.csv` open in
Excel when the counts are written back, say: the version is reported failed, and the
next run extracts it again rather than calling it current. A version whose tree could
not be read in full is named with a `partial walk` line, and its counts are left blank
until a later run reads every folder.

**Re-running is cheap and re-running is safe.** A package whose bytes have not changed
since the last extract is skipped entirely, so `extract --all` over a settled batch does
almost no work. When a package *has* changed, the new tree is built beside the old one and
swapped in, so files the new package no longer ships are gone rather than lingering — a
guide dropped upstream does not quietly survive and convert. If a run is killed mid-swap
you may find a a `.part` directory left behind; the next run removes it before it starts.

Extraction is deliberately serial. Downloads run in parallel because transfers overlap;
two large unzips onto one disk only contend, so there is no `--workers` here.

**A package that tries to write outside its own folder is refused, not repaired**, and
nothing from it is left on disk. So is a package holding a file name Windows cannot
store as written: a reserved character such as `:` or `?`, a name ending in a dot or a
space, or two files whose names differ only in case. That is counted separately from a failure because a
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

| Flag | Effect |
| :--- | :--- |
| `--dry-run` | List what would be converted, and where, without writing. |
| `--force` | Re-convert even when the extracted tree has not changed since last time. |
| `--input` / `--output` | Convert one folder that never went through `extract`. Both are required together, with `--product` and `--version`. The folder is always read afresh: nothing `extract` recorded for the catalog's copy (roots, API trees, help maps) is applied to it, and it is never reported as current. |

> **All four engines convert: MadCap Flare, SDL DITA, WebWorks and DocBook.** Between them
> they are every eligible version in the corpus. A version whose generator DocuShift
> recognises but has no converter for — RoboHelp, R help, MkDocs and the rest of the list in
> §8 — reports **`Engine unknown`**, and is skipped and named rather than guessed at. So does
> a version whose engine was never determined. The command exits 0 either way: one
> unconvertible version must not stop a 200-version run.

**What a Flare version produces.** One output subtree per *output root* — the directory
holding `Data/HelpSystem.xml` — mirroring the source layout, because filename stems collide
6% of the time inside a single root and a flat output would lose topics to each other. A
version shipping several roots (51 of 595) gets several subtrees, deliberately including
the paths they share: 30,736 of those overlap and about 15% differ in content, so
de-duplicating them would drop one release's notes on top of another's. Alongside the
topics: the landing page as the first navigation node, a generated section page for each
navigation node that has children and no page of its own, and the support and legal pages
identified as the last two. Topics in no TOC entry are filed under **Unfiled** and counted
rather than dropped — Flare's TOC covers 86% of its own topics, so this is the normal case
and not an error.

**What a DITA version produces**, and how it differs. One output subtree per *doc-set* —
a directory holding `GUID-*.html`, which sits at `html`, `doc/html`, `html_v3` or `en-US`
depending on the product, and 23 of 319 versions ship several. Inside it the layout is
**flat**, the opposite of Flare's mirror: DITA's source has no hierarchy to mirror, so
pages are named from their titles and the structure is carried by `toc.yml` alone. Titles
collide, so ties break with a `-2` suffix in a fixed order — two runs of the same doc-set
produce the same filenames. There is **no landing page**: a DITA doc-set's front page is a
metadata file rather than a topic, and its navigation is a forest of several top-level
entries rather than one root, so the version's landing node is generated later in the
pipeline instead of hoisted from the source. Topics in no TOC entry go under **Unfiled**
and are counted, as in Flare; DITA's own TOC covers about 97%.

A few DITA-specific behaviours worth knowing. Where SDL republished one topic at a second
place in the TOC, both places point at **one** page rather than two near-identical ones.
Where a cross-reference names a bookmark that does not exist in its target — usually
because SDL itself recorded the failure, with a `missing-elem-id` marker in the link — the
link to the page survives and only the bookmark is dropped, and the report names it.
Admonition labels ("Note:", "Warning:") are removed from the text, because GitHub-flavoured
Markdown draws them itself; a kind GitHub has no alert for, such as *Remember*, becomes a
note whose first bolded words are still "Remember:".

**What a WebWorks version produces.** One output subtree per *book* — the directory holding
`wwhdata/` — mirroring the source layout. A version ships **3.5 books on average** (median
3, max 30; only 25 of 195 ship just one), which is the reverse of Flare, so several
subtrees is the normal case rather than the exception. Where there are several, each book
gets its own folder named after its directory; none takes the version root. A book shipped
twice, byte for byte (at the top level and again under `html/`), is converted once and the
copy is reported. Where the books are gathered under a
collection, the order they appear in is the one the collection declares: it is authored,
and it is not alphabetical in 71% of them. Book display names come from each book's own
title file and are never invented. As with DITA there is **no landing page** — both
candidates in a WebWorks tree are frameset stubs with no content — so the version's landing
node is generated later in the pipeline. Topics in no TOC entry go under **Unfiled**;
WebWorks' own TOC covers about 87%.

WebWorks is the oldest generator in the corpus and **nothing in its output is semantic
HTML** — every list is a table, every heading is a styled `<div>`, and a code block is a run
of one-line `<div>`s — so the conversion is reconstructing structure rather than translating
it. Two consequences are worth knowing. A numbered procedure whose steps are interrupted by
a note, a figure or an example **keeps one sequence of numbers** rather than restarting at 1
after each interruption, and the interrupting content is indented inside the step it belongs
to. And a book's context-sensitive help identifiers, its cross-references and its bookmarks
are all recovered from the help runtime the generator shipped beside the pages, so links
between books in the same package resolve; a link naming a book the package does not ship is
emitted as plain text and counted.

**What a DocBook version produces.** One output subtree, `html/` — the whole version is one
unit, because that is how DocBook publishes: one stylesheet, one tab strip and 24 guides
under one directory. The guide directories are mirrored, since `index.html` alone is 24
pages per version. A `str` package also ships up to eight **byte-identical copies** of a
guide at the version root, and the copy is told from the original by where its stylesheet
link lands; the copies are reported and converted once, not eight times. Unlike DITA and
WebWorks the landing page is **real** — `html/index.html` is a written page, not a frameset
stub — so it is converted and used as it stands. Navigation comes from three places at once:
the tab strip across the top fixes the order of the guides it names, each guide's own
contents page nests its pages, and the three guides that ship no contents page at all are
filed by following their links two hops from the guide's front page. About 3.6% of pages are
reached by none of the three; they are appended to their guide and counted, never dropped.
The legal and support pages are read from the footer's own markup, because searching by
title picks up a topic called "Using Third-Party JARs and Native Libraries" first.

DocBook is the most uniform output of the four — one generator across ten years — so the
conversion is mostly vocabulary: `div.note`/`tip`/`important`/`warning`/`caution` become GFM
alerts, `pre.programlisting` becomes a bare fence (nothing in the source names a language),
the single-cell tables drawn around 1,126 images are unwrapped back to images, and index
anchors are dropped because nothing in the corpus references one. It is also the only engine
with **no context-sensitive help** to emit: neither product ships a help map, so these
versions produce no `csh.yml` — which is an absence in the source, not a gap in the reader.

**What it skips, and says it skipped.** In Flare: generated directories (`_globalpages/`,
`MicroContent/`, `Resources/`), the `Default.htm` runtime stubs, any localized subtree, any
whole output root built for another language (`ja-jp/`, `de-de/`, `ja/`: each is named with
a `LOCALIZED_ROOT_SKIPPED` warning; publishing them to the `loc-` tree is later work), and
API-reference trees — the last identified by a generator marker inside the directory, never
by its name, because `api-exchange-gateway/` is a product with 15,677 files of ordinary
documentation. In DITA: the publication homepage, `index.html`, the TOC files themselves,
and the generator's `static/` and `fonts/` chrome. In WebWorks: the `wwhdata/`, `wwhelp/`
and `tpl/` runtime directories (read for their metadata, never emitted), the frameset stubs,
and the generated list-of-figures, list-of-tables and index pages — a book's *first*
navigation entry is "Figures" or "Tables" often enough that dropping them silently would be
a visible change. In DocBook: the stylesheet directory, and **the three other generators
that ship inside the same package** — a TIBCO Streaming package holds Javadoc, Doxygen and a
Maven site beside the prose, and the Javadoc tree alone is about 2,400 files, more than
twice the prose. Across all four, a topic with no content container is reported, never
guessed at, which is what keeps a Javadoc page out of the Markdown output.

Each run ends with five counts — converted, already current, no extracted tree, engine
unknown, failed — plus the documents and assets written, the asset resolution line, and
the findings summary. Re-running is cheap on the same terms as `extract`: a version whose
extracted tree has not changed since it was converted is skipped, and `--force` overrides.
A changed engine (a hand correction in `versions.csv`) counts as a change. A version that
converts **nothing** (no unit of work, or units with no topic in them) is reported failed
and its previous output is left in place rather than replaced by an empty tree; so is a
version whose engine hits an unexpected error, and the run goes on to the next version.

Conversion also writes the version's context-sensitive help map (`csh.yml`) and stamps the
matching identifiers into topic frontmatter — see §7.

**Conversion also builds the version's navigation.** `toc.yml` and `metadata.yml` are
written by `convert`, not by `sync`, because the navigation tree exists only while the
source is in hand. Where a version ships several books or doc-sets — 90% of WebWorks
versions do — each becomes one top-level entry, in the order the source declares them
rather than alphabetically. A navigation node that has children but no page of its own
gets a page generated for it, marked `generated: true` so a re-run replaces it; a node
with neither is dropped and counted. Support and legal notices are moved to the end of
the version once, even when six books each ship a copy of the same notice — the extra
copies leave the navigation and stay on disk, since a help identifier may still open one.
The run's per-version line reports the node count and how many pages were generated.

**`toc.yml` uses html-to-md's field names.** Every generated TOC — a version's
navigation, the three document folders' and the archives' — is a `docs` list of
entries with `title`, `url` and `subfolderlist`, under a `docs_list_title`:

```yaml
docs_list_title: "Online Help"
docs:
  - title: "Installation"
    url: "Installation/installation-2.md"
    subfolderlist:
      - title: "Product Overview"
        url: "Installation/Product-Overview.md"
```

`docs_list_title` is `Online Help` for a version's navigation, `User Guides (PDF)`,
`Release Information` or `Reference Documents` for the document folders, and the product
name for archives — the values html-to-md used. Only the names match html-to-md; the
structure is DocuShift's: one TOC per version, the landing page first, support and legal
last. A TOC written before 2026-10-02 still says `items` / `path` / `children`; `reframe`
and `validate` read it, and reconverting the version rewrites it.

**Conversion copies an asset because a topic referenced it, and it copies it at the moment it writes the link.** There is no extension allow-list and no separate copying pass: the two happen together, so a relative image link in the output always has a file at the other end. Each asset keeps the path it had relative to its topic, so nothing is renamed, flattened or de-duplicated. Three things get reported rather than copied:

- **Skipped skin.** Most references in a help package point at the generator's own chrome — SDL's `static/`, WebWorks' `tpl/`, Flare's `Skins/`. Half to three-quarters of all references are these. They are counted and dropped.
- **Unreferenced assets.** Images no topic points at are named in the report and left behind — over half of a typical Flare image library. That is normal; MadCap projects accumulate.
- **References that resolve to nothing.** These are counted **grouped by folder**, because that is how they cluster: a broken reference usually means one generated tree whose source was already broken, not scattered per-file loss. A count spread thinly across many folders is a tool problem; a few thousand under one folder is the package.

Case mismatches are reported and not fixed. If a topic says `Images/Logo.png` and the file is `images/logo.png`, conversion copies the file as it found it and tells you — the link works on Windows and breaks once published to a case-sensitive host, so it needs a source fix, not a silent rewrite.

**A link inside a code span survives, and two of them look unusual in the Markdown.** Help
authors routinely make a code token the link — `<code><a href="tibems-status.htm">tibems_status</a></code>`
— and there are **13,126** of these in the corpus. Where the link is the whole token it is
written the only way GFM allows, with the code inside the link: ``[`tibems_status`](tibems-status.md)``.
Where the token is only *part* code and part link — `mode=sync`, with `sync` linked — GFM has
no syntax for it at all, so that span is written as a small piece of raw
`<code>…<a href="…">…</a></code>` HTML, which renders correctly and which `validate` checks
like any other link. There are about 299 of those.

**A link inside a code *block* keeps its words and loses its target**, and the run report
says how many. A fenced code block cannot contain a link in GFM, and the alternative —
emitting the whole block as HTML — would cost every code block in the tree its
copy-pasteability to preserve what is almost always a decorative type cross-reference in a
C function signature. So the fence is kept and each version reports a
`Link inside a code block…` note carrying the count, rather than losing them quietly:
about 4,964 corpus-wide, 1,179 of them in `tibco-ems` 10.4.0 alone.

**About half the tables stay as HTML, and they carry structure only.** GFM's pipe table has
no merged cells, no table inside a cell and no cell holding more than one paragraph, so a
table that uses any of those is written as HTML rather than flattened into a pipe table that
would read plausibly and be wrong. What passes through is **what the table means, never how
the authoring tool drew it**: merged-cell spans, header scopes, links, anchors and the
handful of class names that carry meaning the plain text has lost (`varname`, a
cross-reference, the note styles) are kept. Everything else goes — the generated
`TableStyle-…` class names, pixel column widths, `cellspacing` and cell padding, the
`data-mc-…` attributes, and Flare's reference to a table stylesheet that is not part of the
export and so was pointing at nothing.

Two of those are worth knowing about because you will see the difference. **Table widths now
come from your site's stylesheet**, not from pixel values baked into each page — tables
reflow on a narrow screen, and very occasionally a column that a fixed width was holding on
one line will wrap. And the **phantom "C1" tooltip is gone**: Flare labelled every column
`C1`, `C2` and so on, and that label showed to the reader on hover. A tooltip an author
actually wrote, on a link or an image, is kept.

### Reframe: merging Flare topics into maintainable pages

```bash
# Merge every eligible Flare version; everything else is counted and skipped
docushift reframe --all

# One product, or one version of it -- the same selectors every stage takes
docushift reframe --product tibco-enterprise-message-service
docushift reframe --product tibco-enterprise-message-service --version 10.5.1

# See what would be merged, at what cap, against which pinned layout
docushift reframe --all --dry-run

# A frozen converted folder, with no catalog paths involved
docushift reframe --product tibco-ems --version 10.5.1 --input ./converted --output ./merged
```

| Flag | What it does |
|---|---|
| `--force` | Re-merge even when the converted tree and the policy are both unchanged |
| `--renormalize` | Recompute every page name, ignoring the pins in `rename-map.csv`. **Published URLs will move** |
| `--dry-run` | List the selection, the cap and the pin; write nothing |
| `--input` / `--output` | Work on a standalone folder. Used together, and both need `--product` and `--version` |

A MadCap Flare topic is an authoring unit, not a reading unit. TIBCO Enterprise Message
Service 10.5.1 is **1,441 topics with a median of 107 words** — and once the Markdown becomes
the source that writers maintain, that is 1,441 files somebody has to keep in step. `reframe`
merges them by navigation subtree, so each former topic becomes an anchored `##` section of a
larger page, and hands the pages it could not confidently decide about to a human.

**It only runs for Flare.** Every other engine is counted as skipped, not warned about: on a
full catalog selection that is 1,669 of 1,683 eligible versions, and naming them would bury
the rows worth reading.

**It never writes to its input.** Stage 6's `output/` tree is read and a sibling `reframed/`
tree is built. Tuning a boundary rule is a re-run, not a restore — which matters because the
merge is irreversible once the pages have been hand-edited and the URLs published.

The editorial policy lives in `config/reframe.yaml`, not in the code, because it is expected
to be tuned repeatedly. Two keys:

- **`max_words`** is a **cap, not a target**. Subtree cohesion chooses the boundary; the cap
  only refuses a join that would cross it, and a source topic larger than the cap is never
  split. Measured over EMS 10.5.1: `2000` gives 183 pages, `3000` gives 124, `6000` gives 64.
  A 3,533-word page survives every one of those caps, because it is a single topic.
- **`pin_layout_to`** names the version whose page layout every other version of that doc set
  reuses. EMS has six eligible Flare versions; without a pin each would be laid out by its own
  subtree sizes, the versions would stop being diffable, and porting a fix would stop being a
  clean diff — permanently. `reframe` warns when a doc set has two eligible versions and no
  pin.

**What a merged tree contains.** The pages, every asset copied through untouched, and five
regenerated files at the version root:

| File | What it is for |
|---|---|
| `toc.yml` | The same navigation, retargeted. A topic that led its page gets `page.md`; a topic absorbed into one gets `page.md#anchor`. A reader following the TOC cannot tell the merge happened. |
| `redirects.yml` | One 301 per source topic, anchored — so a published URL from before the merge lands on the section that replaced it, not at the top of a twelve-section page. |
| `reframe.yml` | Which source topic became which section of which page, plus the policy that shaped it and the link counts. This is the record to read when a boundary looks wrong. |
| `rename-map.csv` | The address each merged page was given — the source topic that leads it, the path, the title, its place in the navigation, and the URL a reader will type. Only the last is not derivable from `reframe.yml`, and it is the one somebody checks when a link goes wrong. **A name written here is used, not just reported**: the next run reads it back and pins the page to that path, so a published URL does not move because somebody fixed a typo in a title. The `shortened` column flags the pages whose name does not carry their whole title — mostly words lost to the 50-character cut, 90 of 1,505 measured — which is where a human or a model can write a better one than the algorithm did. The same pages are queued in `review-queue.csv`. `--renormalize` recomputes every name anyway, so the pinning is a decision rather than a trap. |
| `review-queue.csv` | The pages a writer has to make a decision about, and why. Open it in a spreadsheet. |

**`301.yml`, the cutover map, appears alongside them for a version whose live URL shape is
known — read off the docsite's own page list, or declared.** `redirects.yml` answers "where did this page go inside the new tree"; `301.yml`
answers the question the migration actually asks — *the reader has a bookmark to
`docs.tibco.com`, and on cutover day it stops working.* Its left-hand side is that live address
and nothing else, so it is the one file here that cannot be derived from the tree.

The same file is written by `convert` into the converted tree, with every `to` pointing at the
topic's own page, because most products publish that tree rather than the merged one (Phase 35).
Reframe writes its own into the merged tree, pointing at the sections topics were merged into.

Nothing is guessed: the converted catalog contains four different source layouts, and a rule
that generalised one product's would produce a redirect to a page that never existed — which
nothing downstream could detect. The shape comes from one of two places:

- **The docsite's page list** (Phase 33). If `catalog sitemap` has cached the version's Coveo
  sitemap, Reframe finds the one way of turning source paths into listed URLs that places at
  least 90% of the converted topics, with a clear lead over any other. It then writes **only the
  rows the list confirms** — a mapping right for 99% of a version is still wrong for the 1%, and
  those are the rows a reader would follow to a dead page. Reframe never goes online; run
  `catalog sitemap` first.
- **A declaration** in `config/origin-urls.yaml`, written after checking a real page. A
  declaration wins over the list and writes every row; the list only counts where they disagree.

What the run report says:

| Code | Meaning |
|---|---|
| `ORIGIN_SITEMAP_MISSING` (warning) | No declaration and no cached page list for this version — no file. Expected for archived versions and the products the docsite lists no pages for. |
| `ORIGIN_TEMPLATE_UNDECLARED` (warning) | A page list exists but confirms no single mapping (the message gives the numbers), or a declared product's download URL is not a `/pub/` path — no file. |
| `ORIGIN_TEMPLATE_REJECTED` (warning) | The product is declared, but the entry is unusable: no `{path}`, a placeholder other than `{folder_path}` and `{path}`, or a `drop_segments` that is not a whole number. The message says which. The declaration is ignored and the version is handled as if undeclared, so the page list is used if there is one. |
| `ORIGIN_PATH_TOO_SHORT` (warning) | Topics whose source path has no segments left after `drop_segments`, so they get no row. The count is the number of topics. |
| `ORIGIN_URL_UNLISTED` (note) | Rows whose live URL the list does not contain — withheld if derived, written anyway if declared. |
| `ORIGIN_PAGE_UNMAPPED` (warning) | Listed live pages no row starts from: API reference, readmes and PDFs this tool does not convert. Each is a 404 at cutover unless something else redirects it. |

```yaml
# config/origin-urls.yaml
products:
  tibco-enterprise-message-service:
    template: "https://docs.tibco.com/pub/{folder_path}/doc/{path}"
    drop_segments: 1          # the package wrapper folder, which the docsite does not serve
```

`{folder_path}` comes from the version's own download URL rather than being rebuilt from the
slug and the version number — the URL the downloader actually fetched is the one the docsite
serves from, and composing it a second time is how the two come to disagree.

A sixth file appears when the conversion produced one: **`csh.yml`, retargeted**. A
context-sensitive help map is what an F1 keypress in the product resolves against, so it has to
move with the topics. Each identifier keeps its **own** anchor and only the page it sits on
changes — unlike `toc.yml` and `redirects.yml`, which both get the *section* anchor, because a
TOC node is the section while a CSH identifier points at its own marker inside the body. The
merged page also lists every identifier it absorbed in its frontmatter `csh:` key, which is the
mirror `validate` checks the map against. A version whose conversion has no `csh.yml` gets none,
and a map this stage cannot parse fails that version rather than being written empty — the same
rule an unreadable `toc.yml` gets, because a merged tree that quietly lost its Help buttons looks
exactly like one that never had any.

**The review queue is where a human comes in.** Merging is mechanical, but a few pages come
out of it needing an editorial call, and `reframe` lists those rather than guessing:

| Flag | What it means |
|---|---|
| `reference-list` | Twenty or more topics with a median under 100 words — usually a parameter table that would read better as an actual table, or as a page left granular. |
| `oversized` | Over the word cap, because a single source topic is already over it. Splitting a topic body is not something the merge will do. |
| `heterogeneous` | The page spans more than one branch of the navigation, so its sections may not belong together. |
| `shortened` | The page's filename, which is its URL, does not carry its whole title. Write a better name into `new_path` in `rename-map.csv`; the next run uses it. |

Two more flags, `title-inherited` and `single-topic`, are recorded against every page in
`reframe.yml` but never put a page in the queue on their own: a merged page is *always*
titled after its first topic, and a page that merged nothing is usually fine, so queueing on
either would queue everything. On EMS 10.5.1 the queue is 18 pages out of 124. The run
reports the count; nothing about the queue fails the stage.

**Working the queue.** A row is a question with two answers: accept the page, or take its
topics back out of the merge. Nothing records an acceptance — an unlisted page is a merged
page, and the queue is short enough to re-read. Taking one out is `keep_separate`:

```bash
.venv/Scripts/python.exe -m docushift.cli reframe --product tibco-enterprise-message-service
```

Open `review-queue.csv`, and for each row open the page it names under `reframed/`. If the
merge reads badly, find that page in `reframe.yml` and copy the `source` of every section you
want back to its own page into the product's `keep_separate` list:

```yaml
products:
  tibco-enterprise-message-service:
    pin_layout_to: "10.5.1"
    keep_separate:
      - users-guide/connect.md        # one topic, one page
      - c-and-cobol-reference/types   # a whole directory, left granular
```

Then re-run `reframe`. A topic at or under a listed path is never joined to anything, and
nothing is ever joined to it from behind, so the subtree keeps the layout Stage 6 gave it.
Everything around it merges as before — taking one page out does not re-granularize the guide
it sits in. This is the setting that answers a `reference-list` row without moving `max_words`
and re-laying out all 124 pages.

Write the path exactly as `reframe.yml` spells it: a file with its `.md`, a directory without
one. Matching is on whole path segments, so `users-guide/monitor` takes the directory
`users-guide/monitor/` and never `monitor.md` or `monitoring.md`; a leading `./`, a trailing
slash and Windows separators are all normalized away, but a bare stem is not guessed at. A
path matching no topic in a version is a `REFRAME_KEEP_SEPARATE_UNMATCHED` warning naming it —
which is what makes the strictness safe, and which also catches the real case behind it: a
path right for 10.5.1 and absent from 10.4.0.

Editing the list re-merges the doc set, deliberately — it is part of the currency key, unlike
`publish`, because it changes every page boundary downstream. Reordering the list does not:
it is sorted and de-duplicated before it is digested, so grouping lines by guide is free.

`oversized` is the one flag `keep_separate` cannot answer. That page is a single source topic
larger than the cap, and the merge does not split topic bodies; the decision there is a
writing one.

**It checks its own output before it swaps it in.** Words are conserved exactly, every topic
is anchored once, no page spans two source directories, the TOC round-trips in both
directions, every redirect resolves, and no link that worked before the merge is broken by
it. A failure names every check that failed, deletes the staging tree, and leaves the
previous merge — if there is one — exactly where it was. The merge is a one-way door once
pages have been hand-edited, so the run that built a tree is the last cheap moment to reject
it.

Two things it reports rather than fixes. A relative link that pointed at nothing *before* the
merge still points at nothing after, and is counted and named rather than repathed — on EMS
10.5.1 that is 92 `.html` references into a resources tree Stage 6 does not produce. And a
topic on disk that `toc.yml` never lists is carried through as its own page and warned about:
`sync` publishes the whole tree, so those topics are already live, and dropping them would
delete published content as a side effect of a navigation gap.

A version whose conversion has no recorded source checksum — a set converted through
`--input`, for instance — is re-merged on every run rather than reported as current. That is
`convert`'s rule too: no recorded provenance, no currency claim.

**Merging changes nothing about what gets published until you say so.** `sync` reads the
Stage 6 tree for every product, and goes on doing that however many merged trees are sitting
in `reframed/`. A product publishes its merged pages only when `config/reframe.yaml` says so:

```yaml
products:
  tibco-enterprise-message-service:
    pin_layout_to: "10.5.1"
    publish: true            # after a writer has worked review-queue.csv
```

Turning it on is a commit, which is the point: merging is reversible right up until a merged
page is served under an old topic's URL, and after that it is not. **One product has it on** —
`tibco-enterprise-message-service`, signed off on 2026-09-25 after its 18-row queue was read
and every page accepted as merged. Every other Flare set is still `false`, and the commit that
changes that should say who read which queue.

Once a product has opted in, `sync` will not fall back. If the merged tree is missing, or is
older than the conversion beneath it, that version's `online-help` publishes **nothing** and
the run says why — its PDFs and other documents still ship, because those come from the
extracted package and a merge has nothing to say about them. The alternative, quietly
publishing the unmerged topics instead, would un-merge URLs that are already live.

`validate` then checks `redirects.yml` against the tree that actually shipped: a redirect
pointing at a page or a section that is not there is a `LINK_BROKEN` error and fails the gate,
and a redirect whose *source* path is still published is a `REDIRECT_SHADOWED` warning,
because it can never fire. Five of EMS 10.5.1's 1,441 are the latter — they differ from their
target only in case, which is a necessary redirect on a case-sensitive host and a 301 loop on
a case-insensitive one. Which of those you have is a question about your host, so the tool
names them and leaves the call to you.

#### The published redirect map

The `redirects.yml` inside a version folder uses paths relative to that folder — it is the
record of what moved where, and it is what the check above resolves. What a web server needs
is a different file, and `sync` writes it one level up, beside `version.yml`:

```
en-us-tib-ems-userdocs/en-us/tibco-enterprise-message-service/online-help/
├── redirects.yml          ← every merged version's redirects, as served URLs
├── 301.yml                ← every merged version's live docsite URLs, same shape
├── version.yml
├── 10-5-1/
│   ├── redirects.yml      ← this version's, relative to this folder
│   └── 301.yml            ← this version's cutover map, `to` relative to this folder
└── 10-5-0/…
```

It carries **every** merged version under that doc-class, rebuilt from the folders on disk
rather than from what the run happened to touch — so `sync --version 10.5.1` leaves the other
five versions' redirects exactly as they were. Rows you add by hand are kept where you put
them; `sync` only rewrites rows whose source sits under a version folder it published.

The paths are the URLs the pages are served at, minus the host:

```yaml
- from: en-us-tib-ems-userdocs/en-us/tibco-enterprise-message-service/online-help/10-5-1/users-guide/old.md
  to: en-us-tib-ems-userdocs/en-us/tibco-enterprise-message-service/online-help/10-5-1/users-guide/new.md#old
  status: 301
```

Set `publish_base_url` in `config/publishing.yaml` and every row is prefixed with it. Leave it
empty — the shipped state, because the AEM host is not known yet — and the rows come out
tree-rooted, as above. That is deliberate: a map missing only its prefix is one
search-and-replace away from correct, and a map that was never written is not recoverable at
all. The run report tells you which you got:

```
17252 redirect(s) in 2 published map(s), tree-rooted (no publish_base_url set).
```

`301.yml` is assembled by the same code under the same rules, with one difference that follows
from what it holds: only the **`to`** side is rewritten into a published URL, because the
`from` side is already an absolute address on `docs.tibco.com`. That also decides which rows
`sync` may rewrite — a row it owns is one whose *destination* sits under a version folder it
published, so a legacy URL you mapped by hand is left exactly where you put it.

```yaml
- from: https://docs.tibco.com/pub/ems/10.5.1/doc/html/users-guide/old.htm
  to: en-us-tib-ems-userdocs/en-us/tibco-enterprise-message-service/online-help/10-5-1/users-guide/new.md#old
  status: 301
```

`validate` resolves every `to` against the published tree and reports a dangling one as
`LINK_BROKEN`, the same as for `redirects.yml`. It never checks the `from` side: that is a page
on a site this tool does not own, and the only honest test of it is a network request, which
`validate` does not make. Sample a handful by hand before you hand the map over.

`validate` resolves every `to` in it against the published tree, host or no host, and a row
naming a file that is not there is a `LINK_BROKEN` error.

### AEM Synthesis & Publishing Layout
```bash
# Organize converted AEM files into repo-shaped folders on disk
docushift sync --all --target-dir ../tibco-docs-aem/

# One product, or one version of it -- the same selectors every stage takes
docushift sync --product tibco-ems --target-dir ../tibco-docs-aem/
docushift sync --product tibco-ems --version 10.4.0 --target-dir ../tibco-docs-aem/

# See where each version would land, and how many documents it would place
docushift sync --all --target-dir ../tibco-docs-aem/ --dry-run

# Re-copy even where the published tree already matches
docushift sync --all --target-dir ../tibco-docs-aem/ --force

# Check what you just published -- see "Is the output correct?" below
docushift validate --target-dir ../tibco-docs-aem/
```

`sync` ends with the same five-outcome table `download`, `extract` and `convert` do
— synced / already current / no converted tree / skipped / failed. A version you
have not converted yet is a report line, not an abort: over a partially converted
corpus that is the normal state. "Already current" is decided by comparing the two
trees, not by a recorded hash, so a version somebody edited in the target is
re-copied rather than skipped.

A version folder that would put any file over Windows' 260-character path limit under
your `--target-dir` is reported as failed and not copied, with the file and its length
named (`PUBLISHED_PATH_TOO_LONG`). Nobody outside DocuShift could open such a file.
The usual fix is a shorter target root: the deepest real pages already reach 236
characters under a 14-character root such as `C:\tmp\p35-aem`.

> **`sync` now places both trees.** In the docs tree: `online-help` from the
> converted tree, and `user-guides`, `release-information` and `reference-documents`
> from the *extracted* one — so a version you have not converted still publishes its
> PDFs and its readme. In the `-resources` sibling: `api-references/` copied verbatim
> out of the extracted tree, and `archives/` indexed from the catalog. The one piece
> still outstanding is the **cross-tree link rewrite** — see the last two bullets below.

Because the documents come from the extracted package rather than the converted
output, one version can report `no converted tree` for `online-help` and `synced`
for `user-guides` in the same run. The table counts **rows, not versions**: a
version shows up once per doc-class it had something to say about, up to four
times. A version whose extracted package holds no documents at all is not a row —
that is the normal state for roughly one version in twelve, and it is not something
you can act on.

> **`sync` writes folders, not commits.** DocuShift stops at the filesystem: it never runs a git command, creates no repository and pushes nothing. The two trees it writes per family are named exactly as the publishing repositories are, so taking them the rest of the way is a copy into a clone — done by you, by a CI job, or by whatever owns those repositories. That also means you can run `sync` and read the result without any GitHub credentials.

**What sync writes.** Two trees per family, named from the family workspace stem (§3) plus a publishing suffix — the workspace itself is not a repository name:

```
en-us-tib-messaging-userdocs/           # the docs tree — what a reader reads
└── en-us/ems/
    ├── metadata.yml                    # csg-product
    ├── online-help/
    │   ├── version.yml                 # the drop-down, listing only this doc-class's versions
    │   └── 10-4-0/…                    # converted Markdown, toc.yml, metadata.yml, index.md, csh.yml
    ├── user-guides/10-4-0/…            # user-guide PDFs + index.md, toc.yml, metadata.yml
    ├── release-information/10-4-0/…    # release notes + readme + index.md, toc.yml, metadata.yml
    └── reference-documents/10-4-0/…    # VPAT, licence, rest of doc/ + index.md, toc.yml, metadata.yml
                                        # each doc-class also carries its own version.yml

en-us-tib-messaging-userdocs-resources/ # the bulk tree
└── en-us/ems/
    ├── api-references/10-4-0/          # version first, then one folder per API
    │   ├── metadata.yml                #   csg-version — the only file added
    │   ├── java/…                      #   Javadoc, copied byte for byte
    │   └── c/…                         #   the C / Go / tibdg trees likewise
    └── archives/…                      # archived-version ZIPs + index.md, toc.yml, metadata.yml
                                        # no version segment: the folder is the whole history
```

Thirteen things to expect:

- **`version.yml` is the drop-down, and a scoped sync does not shrink it.** Each doc-class gets its own, listing only the versions that doc-class actually holds — so `user-guides` and `online-help` will legitimately disagree. It is rebuilt by reading the folder on disk and matching it against the catalog's active versions, *not* from what the run just wrote, so `sync --product tibco-ems --version 10.4.0` updates one entry and leaves the other thirty-seven alone. Titles carry the release date (`10.4.0 (Feb 2026)`); an undated version keeps the version and drops the bracket.

- **You can hand-edit `version.yml` and DocuShift will not undo it.** The AEM schema allows a row pointing at an absolute URL, so any row whose `path` is not a folder in that doc-class is preserved exactly where you put it. If the file will not parse, sync leaves it completely alone and says so in the report rather than replacing it.

- **A non-`en-us` run publishes into `loc-tib-messaging-userdocs` and gets no `-resources` tree.** All localized content shares one docs tree rather than getting one per language, and API references and archives are English-only. Asking for a localized resources tree is an error, not an empty directory.

- **`nav.yml` is gone and `meta.yml` is now `metadata.yml`.** The AEM spec arrived on 2026-09-10 and named neither of the two placeholder templates the project started with. Nothing consumed `nav.yml`, so it was deleted rather than kept; `metadata.yml` replaces `meta.yml` and carries exactly two keys — `csg-product` beside the product's doc-classes, and `csg-version` in each version folder, dotted (`10.4.0`) even though the folder around it is dashed. The eleven fields the old placeholder invented are not there and are not coming back. If you built anything against `meta.yml`, it needs rewriting.
- **The PDF doc-classes get an index too.** `user-guides/`, `release-information/` and `reference-documents/` each receive a generated `index.md`, `toc.yml` and `metadata.yml` beside their files, so a copied PDF is reachable. Titles come from the document kind where the name identifies one (Release Notes, VPAT, License Agreement), otherwise from the PDF's own metadata, otherwise from the filename with its separators opened out. A doc-class with no files gets no folder at all rather than an empty index. A PDF that will not open is still copied and still listed, titled from its filename and named in the report as a note — it means the shipped file is damaged, which is worth knowing and is not worth failing a run over.

- **What goes where is decided by the folder it shipped in, not by the extension.** Everything directly inside the package's `pdf/` is a user guide unless its name says VPAT, licence, reminder notice or release note; everything directly inside `doc/` is a reference document unless it is a readme or a release note. So a licence PDF and a licence `.txt` land together, and a user-guide PDF and a readme do not. Files in subdirectories are left to the converter.
- **`archives/` is indexed from the catalog, so it lists every archived version — including the ones you have not downloaded.** Entries whose ZIP is not in the repository link to the docsite instead, and the index says which is which. That is deliberate: `archives/` exists to be the complete product history, and `archive download` is what fills it in. `api-references/` gets no generated index — Javadoc ships its own.
- **Versions are dashed here** (`10.4.0` → `10-4-0`) and nowhere else. The catalog and the `families/` workspace keep the dots. Two versions in the catalog are not version numbers at all — `Cloud™` and `(iPaaS)`, upstream parse artifacts — and those are reduced further to `cloud` and `ipaas`, because a trademark glyph and a bracket pair cannot be a URL path. Any version that is not `N.N.N` is named in the run report, whether it was reshaped or just sorted to the bottom of the drop-down.

- **Re-running sync replaces a version's folder wholesale**, so a topic deleted upstream does not survive as a stale file. It replaces exactly that folder: `version.yml`, the product's `metadata.yml`, and every other version are untouched.
- **API references are never converted, and the folder names come from the package.** Javadoc and the C / Go / `tibdg` trees are copied through as HTML, byte for byte, with only a `metadata.yml` added beside them. Each gets a folder named from its path inside the package with the uninformative segments removed — `html/api-reference/java` becomes `java`, `api/java/lib` becomes `java-lib` — and if two of a version's trees would end up with the same name, *all* of that version's folders fall back to their full path so the set stays readable as one scheme.
- **A topic link into `api-references/` becomes the published URL of the resources tree**, written during `convert` rather than during `sync` — by the time the tree is placed the reference is gone, so the rewrite has to happen while the page is being converted. The host comes from `publish_base_url` in `config/publishing.yaml`. **With no host set the link is still written**, as the path without a scheme or host (`en-us-tib-messaging-userdocs-resources/en-us/ems/api-references/10-4-0/java/index.html`), and the run reports `PUBLISH_BASE_URL_UNSET` once per product so you know what is missing — a prefix you can add later, rather than a link you cannot get back. Anchors are kept, and a link to a page that is not actually in the tree is left unlinked and reported rather than pointed at a 404. **One known gap**: where the source wrote the reference inside a code span — `<code><a href="…">MessageListener</a></code>`, which is how the EMS developer guide writes all of its — the conversion flattens it to plain code and the link is not recovered. That is roughly a tenth of these references corpus-wide and all of them are in one product; it is recorded as its own fix.
- **Setting `publish_base_url` reconverts the versions it affects, and only those.** The host is part of what a converted tree contains, so `convert` treats a changed host the way it treats a changed package. Versions with no API tree are untouched, so setting one value does not reconvert the corpus. Each version that does rewrite reports `API_LINK_REWRITTEN` with the count — worth a glance, because a version with an API tree and a count of zero is either a product whose help never mentions its API or a sign something stopped matching.
- **`validate` skips those absolute links by default**, and pass `--check-external` to request them over HTTP. With no `publish_base_url` set the rewritten link has no host, and `validate` resolves it against `--target-dir` instead — so it also tells you whether the API tree it names was actually synced.
- **A broken relative asset link is a tool bug, not a content finding.** Conversion writes the link and copies the file in one step, so `validate` finding one means something downstream moved a file without moving its link — it is reported as a regression, with the stage that could have caused it. An asset that nothing links to is not an error and is not reported here; that count belongs to `convert`.

### Where things stand, and what happened

Three commands, three questions, and the split is deliberate: `status` answers
*where is everything now* from the catalog, `report` answers *what happened* from
the findings a run recorded, and `validate` (below) answers *is the output correct*
from the published tree on disk. No two of them read the same source, so they
cannot drift into different answers to the same question.

```bash
# Where is everything now? The funnel, per stage, over the whole catalog
docushift status

# Filter by BU or Family; add the target to learn what is actually published
docushift status --bu tibco --family integration
docushift status --target-dir ../tibco-docs-aem/

# What engines are in play, and what is still undetermined?
docushift status --engines

# What happened in the last run?
docushift report --run last

# Narrow it: one stage, one severity, one code, one product
docushift report --stage convert --severity error
docushift report --code TOPIC_LINK_DANGLING --slug ems

# What is this code, and who promised it?
docushift report --explain CSH_UNRESOLVED

# Write it out for somebody who was not at the terminal
docushift report --run last --export ./reports/convert-2026-09-16.md
```

Findings are grouped by stage, then by code, errors first. Each one carries a
severity that belongs to the **code**, never to the place that raised it:

| Severity | Meaning | Effect on the exit code |
| :--- | :--- | :--- |
| `error` | The output is wrong or unpublishable | `validate` exits 1; nothing else gates |
| `warning` | The run succeeded and a human decision is pending | Printed and counted |
| `note` | Normal for this corpus, recorded so a change in magnitude shows | Counted only |

Notes are aggregated — one row per code per version, carrying a count — because
the useful thing about 1,308 orphaned images is the number, not 1,308 rows. Errors
and warnings get a row each, because you act on those individually.

`status` reports a **Published** row **only** when you give it `--target-dir`, and
it counts the version folders on disk. Sync currency is compared against the
published tree and never recorded, so the database genuinely does not know what is
published — and a column that guessed would be wrong for exactly the versions
somebody had edited by hand.

The funnel's other rows nest, because each is read from what a stage recorded
rather than from a single status column: a version that downloaded and extracted
and then failed still counts as downloaded and extracted, because it was. The one
case where a later step can exceed an earlier one is `convert --input`, which runs
a tree this workspace never downloaded; `status` says so in a footnote rather than
leaving you to wonder.

Findings are kept across runs, so old ones stay queryable by run id.
`docushift report --runs` lists the recent ones with their counts, and
`docushift report --prune --keep 10` drops the findings of everything older — the
run rows survive, so a pruned run is still a dated record that something ran.

**Exit codes.** A stage that did its work exits 0 even when it recorded errors:
the errors are in the report, and that is what `report` is for. A selection that
matched nothing exits **1** — before Phase 7a a typo in `--product` was
indistinguishable from a clean run — and `--dry-run` is not exempt, because it is
the same mistake discovered one command earlier. `report` itself exits 1 only for
a run that is not there or an export it could not write. Only `validate` gates on
what it found.

### Is the output correct?

`validate` reads the **published tree** and nothing else — not the catalog. A tree
another machine synced validates the same way, and a product you retired last week
still has help on the shelf that can be checked.

```bash
# The whole target: links, anchors, AEM artifacts, CSH
docushift validate --target-dir ../tibco-docs-aem/

# Narrow it -- the walk costs about a second per 120 files, so this matters
docushift validate --target-dir ../tibco-docs-aem/ --product tibco-ems
docushift validate --target-dir ../tibco-docs-aem/ --product tibco-ems --version 10.4.0
docushift validate --target-dir ../tibco-docs-aem/ --doc-class online-help

# What would it walk? Reads no file
docushift validate --target-dir ../tibco-docs-aem/ --dry-run

# Also request every absolute URL once. Off by default; no network without it
docushift validate --target-dir ../tibco-docs-aem/ --check-external
```

`--version` takes `10.4.0` or `10-4-0`: the dashed form is what is on disk and the
dotted form is what you have in hand.

**There is no `--family` here, and that is not an oversight** — `validate` never
opens the catalog, and `family` is a catalog column. To check one family, loop over
the product folders in its tree:

```bash
for p in ../tibco-docs-aem/en-us-tib-streaming-userdocs/en-us/*/; do
  docushift validate --target-dir ../tibco-docs-aem/ --product "$(basename "$p")"
done
```

Each run gates on its own exit code, so a loop tells you *which* product failed
rather than only that something did.

**It exits 1 if and only if it recorded an error** — the only command in the tool
that gates. Warnings and notes are printed and counted and change nothing, and a
selection that matched no published folder exits 1 like every other stage.

Six things to expect:

- **A missing file is an error; a missing anchor is a warning.** Across a real
  published tree of 91 versions, 11.6% of links carrying a `#fragment` point at an
  anchor that is not there — anchors the conversion dropped, worth knowing about
  and far too common to fail a run over. A file that is not there is a 404 and
  gates.
- **Case matters, even on Windows.** The tree is published to Linux, so a link that
  differs from its file only in case resolves on your machine and 404s in
  production. The message names the file that is actually there, so the fix is one
  rename. This is not theoretical: the check's first run found three TOC entries
  like that, and the cause turned out to be a converter bug that had been writing a
  generated page over a real topic.
- **`.part` folders are skipped and counted, not checked.** A sync that failed
  leaves its staging folder behind; the swap refused to publish it, so validating it
  would report problems a re-run cures. You get one note per folder saying it is
  there.
- **`api-references/` is not link-checked.** It is copied Javadoc — not this tool's
  output and not fixable from here. Its `metadata.yml` is checked, because that file
  is ours.
- **Only `metadata.yml` is required.** `toc.yml`, `index.md`, `csh.yml` and
  `version.yml` are checked when they are there and never demanded, because which of
  them a doc-class carries legitimately varies. A YAML file that will not parse is
  reported once, and the rest of that file's checks are skipped.
- **It writes nothing, and there is no `--fix`.** The published tree is regenerated
  by `sync`, so a repair applied here would be reverted by the next run.
- **It compares each version's help map against the version below it.** An
  identifier that was published in 6.10.0 and is gone in 6.11.0 is a Help button
  that breaks on upgrade, and it is the one defect here that cannot be seen by
  looking at either version alone. One warning per version; `docushift csh report
  --since` lists the identifiers. §7 has the detail.

Everything it records goes into the findings register like any other run, so
`docushift report --run last` reads it back and `--export` writes it out.


---

## 5. Product Taxonomy Configuration (`config/taxonomy.yaml`)

This file defines **which families exist** and **the keyword rules that resolve a product's business unit**. It does *not* list individual products — per-product `bu`/`family` assignment lives in `config/products.csv`, where it can be bulk-edited.

The rules no longer assign a family. They did until the WebFOCUS split, where one rule matching the bare token `webfocus` turned out to claim all seven products of a line that wanted five families — and the obvious replacement, matching `container edition`, would have pulled sixteen unrelated TIBCO products into an ibi family. Both were caught by hand, which is the work the rules were there to save. A family is now a human's call; the rules keep the half they are reliable at.

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

# Keyword inference. First match wins. Sets `bu`; the `family` key is kept as
# the suggestion `catalog triage` prints, and is never written to the catalog.
rules:
  - match: ["webfocus"]
    bu: ibi
    family: webfocus
  - match: ["omni-gen", "omni-healthdata", "iway"]
    bu: ibi
    family: data_management
```

Every product is written `family_source=unclassified` for manual triage, whether or not it matched a rule. A product that matched nothing also gets `bu=tibco`, which is why a new business unit needs a rule even though families no longer do.

**Two things about `match` that the syntax does not show.** Each token is tested twice: as an **exact** `product_code`, and as a **raw lowercase substring** of `display_name`. Substring, not word — so a token as short as `cloud` claims every Cloud Edition in the catalog, and the tokens that work are either an exact code or a distinctive phrase. And the names carry a `®` or `™` **inside** them: the product is `TIBCO Silver® Fabric`, so `silver fabric` matches nothing and `fabric` matches everything you wanted. Nothing strips those symbols before the comparison. When you add a rule, check it against the catalog rather than reading it:

```bash
docushift catalog triage            # what is still unclassified
docushift catalog list --family mft # what a rule actually claimed
```

**Order is load-bearing, and not only "specific before broad".** Many products are named after two families at once — `BusinessWorks Plug-in for Managed File Transfer`, `Silver Fabric Enabler for EMS`, `Spotfire Extension for OpenSpirit`. The catalog files each of these with the product it *extends*, not the product it names, so the `bw`/`messaging`/`spotfire` rules sit **above** the `mft`/`silver-fabric`/`openspirit` rules. Reading the list top-down is the only way to predict where a product lands.

**Setting a family is one command, and it is the only way.**

```bash
docushift catalog set --product tibco-rtview --family monitoring   # sets family_source=manual
```

The family must already be declared under that business unit in `taxonomy.yaml`; an unknown key is rejected and the declared ones are listed. This is deliberately strict — an accepted typo would quietly create a workspace folder and, further down the pipeline, a publishing repository.

Editing the `family` column in the spreadsheet by hand does **not** pin it — set `family_source` to `manual` in the same row, or use the command above, which does both. `family_source` still ranks `manual > taxonomy_rule > docsite_category > unclassified` in the merge, so the older rule-assigned values keep their precedence over anything left unclassified.

> Rules assign `bu` only — never a `family`, and never `engine`. The source toolchain
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
docushift status --engines

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
├── toc.yml            ← the version's navigation
├── metadata.yml       ← csg-version: "6.12.0"
├── bw-ent-html/
├── bwce-html/
└── relnotes/
```

It is a flat map, identifier to path, and nothing else — the shape AEM asked for:

```yaml
"adb.palette.gettingstartedurl": "config/Getting_Started.md#adb.palette.gettingstartedurl"
"bw_java_bw_java_xmltojava": "bw-ent-html/binding-palette/xml-to-java.md"
"1234": "bw-ent-html/install/install.md"
```

Three things to know about reading it. The path is relative to `csh.yml` and carries the
anchor after a `#` where the source had one. The doc-set is the path's first segment.
And **both sides are always quoted**, because 7.5% of Flare identifiers are all digits and
an unquoted `1234` loads as an integer out of a map whose keys are strings.

What the file does *not* carry — identifiers that matched no produced topic, and
identifiers two doc-sets claim for different pages — is not lost: both are reported by the
run, as `CSH_UNRESOLVED` and `CSH_AMBIGUOUS`. A broken Help button is always countable.

The topics themselves carry their identifiers in frontmatter:

```yaml
---
title: REST reference
csh: ["bw_rest_binding", "restBindingRef"]
---
```

A version whose package contains no help map — around a quarter of them do not — gets **no `csh.yml`**. An empty map file would be indistinguishable from a failed run.

### Inspecting and checking it

**`docushift csh` reads a published tree, so every subcommand takes `--target-dir`** — the same directory `sync` wrote and `validate` checks. It never opens the catalog, which means you can point it at a tree another machine synced. The three selectors are `validate`'s: `--product`, `--version` (dotted or dashed) and `--doc-class`.

```bash
# What identifiers does this version publish, and are their targets on disk?
docushift csh list --target-dir /publish --product businessworks --version 6.12.0

# Coverage across the shelf: versions published, versions mapped, identifiers,
# target pages, comparable version pairs, and identifiers dropped
docushift csh report --target-dir /publish

# Integrity: every mapped topic exists, frontmatter and csh.yml agree,
# and nothing the version below published has gone missing
docushift csh validate --target-dir /publish --product businessworks
```

**The query worth remembering is `--identifier`.** A ticket says the Help button for `Gateway.BusinessAgreements` broke in 6.11.0; this says where it went, across every published version at once:

```bash
docushift csh list --target-dir /publish --identifier Gateway.BusinessAgreements
```

It prints the versions that carry it with its target and whether that file is there, then names every version that *has* a help map and does not carry it — which is the answer to "when did we lose it". The match is exact: an identifier differing only in case is reported as a near-miss rather than treated as a hit, because `GatewayInstances` and `gatewayInstances` are two different live help targets in this corpus.

**`docushift validate` already includes all of this**, so `csh validate` is for when you want the help checks without the 84-second link walk. Both run the same code and cannot disagree.

**To see what changed between two versions, name the older one:**

```bash
docushift csh report --target-dir /publish --product businessworks --since 6.11.0
```

That prints the diff identifier by identifier — dropped, added, and **retargeted**, meaning the identifier survived but now opens a different page. Retargeting is normal (it is pages being renamed between releases, 12.9% of surviving identifiers) and is never reported as a problem; it is shown here because when a Help button opens the wrong topic, this is where you see it.

`docushift extract` already prints the tally (`CSH: 3 source(s), 561 identifier(s).`), so a version with no help map is visible before you spend a conversion on it.

### A dropped identifier is a warning, and why

`validate` and `csh validate` both raise **`CSH_IDENTIFIER_DROPPED`** when a version's help map is missing an identifier the version below it published. It is one warning per version, carrying the number dropped and naming the first five; `csh report --since` lists the rest.

It is a warning rather than an error because **16% of upgrades do it** — 51 of 317 comparable version pairs across the whole corpus, and 70% of cross-major upgrades. A gate that fails on one upgrade in six is a gate people learn to skip. Two things follow that are worth knowing before you read the output:

- **A version's predecessor is the next-lower version folder of the same doc-class, and only that one.** If that folder has no help map, nothing is compared — so a product that loses its map entirely reports once, in the version that lost it, rather than in every version after it.
- **When more than 90% of the map is gone, the message says the map was re-keyed.** That is usually a product redesigning its help across a major version rather than a conversion losing it. Same warning, same severity — you still want to look, but you are looking at something different.

A product's oldest published version is never compared against anything, and that is not a gap being reported: it has no predecessor on the shelf.

### Four things worth knowing

**Every help format in the corpus is read.** MadCap Flare, SDL DITA and WebWorks all ship context-sensitive help in their own format, and DocuShift reads all three. DocBook is the exception, and only because it has no CSH to read. So `_has_csh=false` means this version ships no help map, not that we declined to look at one.

**There is one identifier, and it is a string.** In DITA it is the key of the context map; in WebWorks it is the dotted name the help viewer is called with (`as400.palette.gettingstartedurl`). In Flare, the numeric `ResolvedId` is deliberately not carried through: 15% of the alias files surveyed reuse an id for two different topics *within one file*, so it cannot address a page and is not an identifier. What you get is the alias name. It is a string, and always quoted, because 7.5% of the Flare names in the corpus are pure digits (`12`, `1000`, `1122`) and a digit-only identifier must not load as a number.

**Identifiers are case-sensitive, and the difference is load-bearing.** TIBCO BC 7.4 and 7.5 both ship `GatewayInstances` and `gatewayInstances` as *different* help targets pointing at different pages. (This is a Flare hazard specifically — WebWorks and DITA identifiers collide neither by case nor by digits — but nothing case-folds regardless.) Nothing in the pipeline case-folds an identifier, and neither should anything downstream — with the integer gone, case is the only thing keeping those two apart.

**Identifiers are merged across the version's doc-sets.** A version can ship several help outputs (`bw-ent-html`, `bwce-html`, `relnotes`), and Flare frequently copies one output's alias file into a sibling where none of its topics exist. Resolving version-wide rather than per-output fixes those: in TIBCO BusinessWorks, the release-notes alias file resolves 0 of 203 links on its own and 203 of 203 against the main output. Where two outputs genuinely disagree about a name, the larger output wins and the alternative is recorded under `also:` — nothing is dropped. WebWorks does not have the copied-alias problem at all (its links resolve where they sit, every time), but it does ship several books per version, so the `also:` case still comes up.

Full design and the corpus evidence behind it: `architecture.md` §5.4.
