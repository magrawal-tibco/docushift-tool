# Quick Start: One Product, End to End

> **Document Status:** Living Quick Start
> **Last Updated:** 2026-10-05

This is the shortest path from an empty checkout to published-shaped folders for **one
product**, so you can see the whole pipeline work before pointing it at the catalog. It
takes about fifteen minutes, most of which is the download.

Every step here is the simple case. The flags, the selectors, the report lines and the
reasons behind each rule are in the [User Guide](user-guide.md); the decision rules
themselves are in [`design.md`](design.md). Where a step has a common way of going wrong,
it is called out inline with a pointer to the section that explains it.

We use **TIBCO Enterprise Message Service** throughout — docsite slug
`tibco-enterprise-message-service`, product code `ems`. It is a MadCap Flare product, so
it exercises every stage including `reframe`.

---

## 0. Install, and check the install

```bash
git clone https://github.com/magrawal-tibco/docushift-tool.git
cd docushift-tool
pip install -e ".[dev]"

docushift doctor
```

`doctor` prints the resolved paths (`config/`, `cache/`, `families/`, `output/`,
`state.db`), the active locale, and which family workspaces exist. On a fresh checkout it
reads `family workspaces: none yet` — that is correct; per-family folders are created when
a stage first needs one.

Every command works on the **current directory** as the project root. Run them from the
checkout, or name the root with the global `--root` option, which goes before the command:
`docushift --root D:\docushift-tool doctor`.

If you intend to commit, also set the commit template — see
[User Guide §1](user-guide.md#1-quickstart--installation).

---

## 1. Discover the product (`catalog fetch`)

```bash
docushift catalog fetch --product ems
```

One HTTP request against `docs.tibco.com`. It writes rows into `config/products.csv` and
`config/versions.csv` — active versions and archived ones both.

```bash
docushift catalog show --product tibco-enterprise-message-service
```

Note that `show` answers on the **slug**, not the code: the slug is the catalog's key.
`--product ems` works on fetch because the code is looked up, but once a product is in the
catalog, the slug is what everything prints back at you.

**A scope is always required.** A bare `catalog fetch` would crawl ~670 products, so it
asks for `--all` or one of `--bu` / `--family` / `--product` / `--batch` rather than
assuming. See [§2](user-guide.md#2-managing-the-additive-product-catalog).

---

## 2. Make one version eligible (`catalog enable`)

Every stage below is scoped with `--version`, so a first run stays to seconds either way.
What you do need is for that one version to be eligible:

```bash
docushift catalog enable --product tibco-enterprise-message-service --version 10.5.1
```

`--disable` is the same command in reverse, one version at a time.

Three gates decide what the later stages act on, and a selector cannot override any of
them: `in_scope` on the product, `release_status=retired` from support's report, and
`convert_eligible` on the version. If a stage reports it selected nothing, one of those
three is why — [§4](user-guide.md#selecting-what-a-command-acts-on).

You can also edit `config/versions.csv` directly in Excel. Your edits survive a re-fetch;
that is what the 3-way merge is for.

---

## 3. Download the package

```bash
docushift download --product tibco-enterprise-message-service --version 10.5.1
```

Lands in `families/<locale>-<bu>-<family>/downloads/`. Transfers resume, the checksum is
taken while writing, and nothing reaches the final path until the whole ZIP has arrived
and been checked.

The run ends with five counts — downloaded / already current / skipped (manual) / no
`zip_url` / failed — and the last two are listed by name. **A failure never aborts the
run.**

If discovery found no usable URL, supply the ZIP yourself:

```bash
docushift download --product tibco-enterprise-message-service --version 10.5.1 \
  --from-file "D:\downloads\ems-docs.zip"
```

Archived versions are not downloaded here; use `docushift archive download`.

---

## 4. Extract, and let it detect the engine

```bash
docushift extract --product tibco-enterprise-message-service --version 10.5.1
```

This is a separate stage because it is where the **engine is detected** and written back
into `versions.csv`, alongside the asset and CSH inventory columns.

Two outcomes are worth reading in the report, and they are different problems:

- a version left on `auto` — DocuShift could not tell what built the package; report it
- a named engine with no converter — a scoping question for you, not a bug

Confirm the detection before converting:

```bash
docushift catalog show --product tibco-enterprise-message-service
```

You want `engine: flare` on the row.

---

## 5. Convert to GFM Markdown

```bash
docushift convert --product tibco-enterprise-message-service --version 10.5.1
```

Writes Markdown into `output/`, plus — in the same pass — the navigation (`toc.yml`), the
product metadata (`metadata.yml`), the help map (`csh.yml`), and every asset a topic
actually referenced, copied at the moment the link is written.

Re-running is cheap: a version whose extracted tree has not changed is skipped. `--force`
overrides.

Expect report lines you do not have to act on. Unreferenced images (over half a typical
Flare library), links inside code blocks that keep their words and lose their target, and
tables kept as HTML because GFM has no merged cells are all normal and all counted. What
*is* worth acting on: case-mismatched asset paths (they work on Windows and break once
published) and broken references clustered under a single folder. See
[§4](user-guide.md#extract--convert-to-gfm).

---

## 6. Reframe (Flare only)

```bash
docushift reframe --product tibco-enterprise-message-service --version 10.5.1
```

A Flare topic is an authoring unit, not a reading unit — EMS 10.5.1 is 1,441 topics with a
median of 107 words. `reframe` merges them by navigation subtree into pages a writer can
maintain, and reads `output/` to build a sibling `reframed/` tree. **It never writes to
its input**, so tuning a boundary is a re-run, not a restore.

It only runs for Flare. Every other engine is counted as skipped, which is the expected
report line for most of the catalog.

Five files land at the version root — `toc.yml` (retargeted, anchors and all),
`redirects.yml`, `reframe.yml` (the record of which topic became which section),
`rename-map.csv` and `review-queue.csv`. The last two are the ones meant to be edited:
the review queue lists the pages needing a human decision, and a path you write into
`rename-map.csv` is read back and pinned on the next run, so a page's published URL stops
moving when its title changes.

Two settings in `config/reframe.yaml` shape the result, and both are expected to be tuned:
`max_words` (a **cap**, not a target) and `pin_layout_to` (the version whose layout every
other version of the doc set reuses, so the versions stay diffable). With two or more
eligible versions and no pin, `reframe` warns.

---

## 7. Place the publishing trees (`sync`)

```bash
docushift sync --product tibco-enterprise-message-service --version 10.5.1 \
  --target-dir ../tibco-docs-aem/ --dry-run

docushift sync --product tibco-enterprise-message-service --version 10.5.1 \
  --target-dir ../tibco-docs-aem/
```

Writes two trees per family: the docs tree (`online-help` from the converted output;
`user-guides`, `release-information` and `reference-documents` straight from the extracted
package) and the `-resources` sibling (`api-references/` copied verbatim, `archives/`
indexed from the catalog).

**`sync` writes folders, not commits.** DocuShift stops at the filesystem — no git command
is ever run. The trees are named exactly as the publishing repositories are, so taking them
the rest of the way is a copy into a clone, done by you or by CI. It also means you need no
GitHub credentials to get this far.

Two things that surprise people: versions are **dashed** here (`10.5.1` → `10-5-1`) and
nowhere else, and the counts in the report are **rows, not versions** — one version can
appear up to four times, once per doc-class.

---

## 8. Check what you published

```bash
docushift validate --target-dir ../tibco-docs-aem/
```

A broken **relative** asset link here is a tool bug, not a content finding: conversion
writes the link and copies the file in one step, so one appearing means something
downstream moved a file without its link. Absolute links are skipped unless you pass
`--check-external`.

Then, for the two standing questions:

```bash
docushift status   # where is everything now, from the catalog
docushift report   # what happened, from the last runs
```

---

## 9. Share the status (`reports/conversion-status.html`)

```bash
python scratch/build_conversion_status.py
```

Rebuilds the status page for a business audience. Open
`reports/conversion-status.html` in any browser to present it, or print it to PDF. It
shows how far the whole programme has got, from the catalogue to synced: progress by
family with each family's last activity, every `_status` and `_sync_status` value with
its count, what has been converted and when it was last built and synced, what is
blocked and when it was last attempted, where we disagree with the docsite team's
migration list, and the decisions still open. Filters at the top narrow
it to one business unit or one family.

The page reads `versions.csv`'s status columns
([User Guide](user-guide.md#where-each-version-stands)), so it agrees with the sheet and
with `docushift status`. It holds the figures from the moment it was built, so rebuild it
before each meeting. It needs only Python's standard library, not the installed tool.

---

## The whole thing, in one block

```bash
docushift doctor
docushift catalog fetch   --product ems
docushift catalog enable  --product tibco-enterprise-message-service --version 10.5.1
docushift download        --product tibco-enterprise-message-service --version 10.5.1
docushift extract         --product tibco-enterprise-message-service --version 10.5.1
docushift convert         --product tibco-enterprise-message-service --version 10.5.1
docushift reframe         --product tibco-enterprise-message-service --version 10.5.1
docushift sync            --product tibco-enterprise-message-service --version 10.5.1 --target-dir ../tibco-docs-aem/
docushift validate        --target-dir ../tibco-docs-aem/
```

## Scaling up from here

Every stage from `download` to `sync` takes the **same selectors**, so widening the run is a
flag change, not a different procedure (`validate` takes the published tree instead):

| Flag | Selects |
| :--- | :--- |
| `--all` | The whole catalog |
| `--bu tibco` | One business unit |
| `--family integration` | One family |
| `--product ems` | One product |
| `--version 10.5.1` | One version (with `--product`) |
| `--batch poc-1` | Every version tagged into that run |

The usual next step is a **batch**: tag a handful of versions with a `convert_batch` label
in `versions.csv`, then run the five pipeline stages — `download`, `extract`, `convert`,
`reframe`, `sync` — with `--batch poc-1`, and `validate` over the target as before. Add
`--dry-run` to any stage first to see the selection without writing anything.

Each stage exits **1** when a version in it failed, or when the selection matched nothing,
so chaining them with `&&` stops at the first stage that lost a version. The full table is
under "Exit codes" in [User Guide §4](user-guide.md#4-end-to-end-migration-commands).
