---
name: propagate-catalog-edit
description: Propagate hand edits to config/products.csv (or config/versions.csv) through the rest of the tool — pin provenance so a fetch cannot revert them, declare new families in taxonomy.yaml, regenerate the denormalized _bu/_family columns, and relocate orphaned family workspaces. Use whenever the user says they edited, updated, reassigned, or bulk-changed the catalog CSVs in Excel or by hand.
---

# Propagating a hand edit to the catalog CSVs

Editing `config/products.csv` in a spreadsheet is the supported workflow — it is
why the catalog is CSV (see `docs/architecture.md` §3.1). But a raw cell edit is
only half a change. Four things live downstream of it, and none of them update
themselves.

The failure this skill exists to prevent: an edit that looks applied, passes every
check, and then **silently reverts on the next `docushift catalog fetch`** because
its provenance column still says a tool owns the value.

## Step 0 — Find out what actually changed

Never trust `git diff` on these files. Excel rewrites the whole file (booleans
become `TRUE`/`FALSE`, quoting shifts), so a two-cell edit shows as 600 changed
lines. Diff semantically instead:

```bash
cd C:/github/docushift-tool
git show HEAD:config/products.csv > C:/tmp/old_products.csv
.venv/Scripts/python.exe - <<'EOF'
import csv
def load(p):
    with open(p, encoding='utf-8-sig', newline='') as f:
        return {r['slug']: r for r in csv.DictReader(f)}
o = load('C:/tmp/old_products.csv'); n = load('config/products.csv')
print("rows old/new:", len(o), len(n))
print("added:", sorted(set(n) - set(o)))
print("removed:", sorted(set(o) - set(n)))
ch = {}
for s in set(o) & set(n):
    for k in o[s]:
        a, b = o[s][k], n[s].get(k)
        if a != b and a.lower() != (b or '').lower():   # ignore Excel's TRUE/true churn
            ch.setdefault(k, []).append((s, a, b))
for k, v in ch.items():
    print(f"\n== {k}: {len(v)} changed")
    for s, a, b in sorted(v):
        print(f"   {s}: {a} -> {b}")
EOF
```

Report the real changes to the user before touching anything. Case-only boolean
churn is cosmetic — `parse_bool()` lowercases (`src/docushift/utils/csvio.py:34`)
and the next write normalizes it. Do not mention it beyond a one-liner.

## Step 1 — Pin provenance, or the edit is not durable

Every user-ownable field in `products.csv` is shadowed by a `*_source` column.
The 3-way merge in `CatalogManager` only refuses to overwrite a field when that
column names a human:

| Field edited | Must become | Enforced at |
|---|---|---|
| `family` (and `bu`) | `family_source=manual` | `catalog.py:623` |
| `in_scope` | `scope_source=manual` | outranks `config/scope.yaml` |
| `engine` (versions.csv) | `engine_source=manual` | permanent |
| `release_status` | `release_status_source=manual` | outranks the EOS report |
| `zip_url` | `zip_source=manual` | |

**`family` is the dangerous one.** It is resolved by *provenance rank*, not by the
snapshot diff every other field uses. If the user left `family_source` at
`taxonomy_rule` while changing `family`, ranks tie, control falls through to
`_take_theirs()`, and the edit survives **only while `state.db` holds a snapshot**.
On a fresh clone or a deleted state DB there is no base, the fetch's value wins,
and the reassignment is gone with no warning.

Do not hand-edit the `*_source` cell. Use the CLI — it sets the field and pins
provenance in one step (`catalog.py:706-712`):

```bash
.venv/Scripts/python.exe -m docushift.cli catalog set --product <slug> --family <family>
```

Loop over every affected slug. There is no `docushift` on `PATH` in this repo and
`python -m docushift` fails — always go through `.venv/Scripts/python.exe -m docushift.cli`.

**If `config/versions.csv` is open in Excel this fails with `PermissionError`
partway through** — `products.csv` is written first, so the product edit lands but
the `_family` regeneration does not. Ask the user to close it and re-run; do not
work around it by writing the CSV yourself.

## Step 2 — Declare any new family in taxonomy.yaml

A family typed into `products.csv` that `config/taxonomy.yaml` does not declare is
*accepted*, not rejected — it warns and auto-registers a workspace folder
(`catalog.py:957-967`, architecture §4.2). That is deliberate, and it is also how a
one-product ghost family appears. Check the BU's `families:` block and add the key:

```yaml
      <family_key>:
        name: "<Display Name>"
        description: "<one line>"
```

Then tell the user about `repo_slug`. It is optional and defaults to the slugified
key, so a new family publishes to `en-us-tib-<family_key>-userdocs`. If the doc
platform wants a shorter token (the way `tibco` → `tib`), it must be set **now** —
changing it later moves both the workspace directory and the repo name.

## Step 3 — Regenerate the denormalized columns

`versions.csv` carries `_bu` and `_family` copied from `products.csv` so the sheet
can be filtered without a VLOOKUP. They are tool-owned, edits to them are ignored,
and they are rewritten on every save (`catalog.py:329`). A `family` change leaves
them stale across every version row of that product.

`catalog set` already saves, so Step 1 usually covers this. If the user edited the
CSV by hand and you did not run `catalog set` (e.g. a `display_name` fix), flush
explicitly:

```bash
.venv/Scripts/python.exe -m docushift.cli catalog import
```

This validates, prints warnings, and normalizes. It **blocks on row deletions** —
if the user genuinely meant to remove products, re-run with `--allow-deletes`;
otherwise a blocked import means Excel dropped rows and the edit should be redone.

Note `catalog import` does **not** refresh the `state.db` snapshot — only `fetch`
does. This is why Step 1's `manual` pin, not the snapshot, is what makes an edit
durable.

## Step 4 — Relocate orphaned on-disk artifacts

Every path in the pipeline is derived from `(bu, family, slug, version)`. Changing
`family` silently repoints all of them:

| Stage | Path |
|---|---|
| download | `families/<locale>-<bu>-<family>/downloads/<slug>-<version>.zip` |
| archive | `families/<locale>-<bu>-<family>/archive/…` |
| extract | `families/<locale>-<bu>-<family>/extracted/<slug>/<version>/` |
| convert | `output/<locale>-<bu>-<family>/<slug>/<version>/` |

Anything already downloaded, extracted, or converted under the **old** family name
is now orphaned: the tool will not find it, and `download` will re-fetch from
scratch. Check the old workspace for the affected slugs:

```bash
ls families/ output/
ls families/<locale>-<bu>-<old_family>/downloads/ 2>/dev/null | grep <slug>
```

If artifacts exist, **ask the user before moving or deleting them** — re-downloading
a large package set is expensive, and deleting converted output is not reversible.
Offer to `mv` them into the new family workspace. If nothing has been downloaded
yet, say so and move on; there is nothing to relocate.

## Step 5 — Verify and report

```bash
.venv/Scripts/python.exe -m docushift.cli catalog triage   # family_source breakdown + unclassified backlog
.venv/Scripts/python.exe -m docushift.cli catalog show --product <slug>
```

Confirm the `manual` count rose by exactly the number of rows edited, and that
`_family` is no longer stale in `versions.csv`. Report a short table of what
changed in which file, and call out anything you did **not** do (orphaned
artifacts left in place, a `repo_slug` left at its default) rather than letting it
pass silently.

## Notes

- `config/products.csv` and `config/versions.csv` are UTF-8 **with BOM**
  (`utf-8-sig`) and contain `®`/`™` in display names. Always read them with
  `encoding='utf-8-sig'`. If characters look mangled in terminal output, suspect
  the console codepage, not the file — verify with a `.decode('utf-8')` round-trip
  before "fixing" anything.
- A pre-existing warning about `config/scope.yaml` rules matching no product is
  expected until `catalog fetch --all` has run. Do not chase it.
- Discovery may have added new product rows alongside the user's edits. New rows
  arrive `family_source=unclassified`; mention them for triage but do not classify
  them yourself unless asked.
