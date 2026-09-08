# DocuShift Design Document: Logic & Algorithms

> **Document Status:** Living Design Specification
> **Last Updated:** 2026-09-07
> **Companion to:** `architecture.md` (what the system is and *why*), `planning.md` (when each part gets built), `user-guide.md` (how to drive it)

This document states, in plain English, **how each piece of DocuShift decides what it decides**. Where `architecture.md` records a shape and its justification, this records the procedure: the inputs, the ordered steps, the tie-breaks, and what happens when the input is malformed — which, across ~250 products of undocumented API and twenty years of accumulated help output, is routine rather than exceptional.

**Status legend.** Every algorithm is marked:

- **Built** — implemented and covered by the test suite. The description matches the code; if they ever disagree, the code is the defect *or* this document is, and the pair should be reconciled rather than one assumed correct.
- **Specified** — designed and agreed, not yet written. Steps are binding on the implementation; anything genuinely still open is called out as **Open** inline.

**A note on style.** Steps are numbered where order is load-bearing, which is most places — nearly every ordering here exists because reversing it loses data silently rather than loudly. Where a rule looks arbitrary, the one-line reason follows it, and the fuller argument is a section reference into `architecture.md`.

---

## 1. Shared primitives

These are used by every stage. They are small, and they are where most of the corpus's roughness is absorbed.

### 1.1 Identity keys — **Built**

| Thing | Key | Notes |
| :--- | :--- | :--- |
| Product | `product_code` | Lowercase slug, e.g. `ems`. Rarely equal to the docsite slug. |
| Version | `(product_code, version)` | `version` keeps its dots (`10.4.0`) everywhere except the published AEM path. |
| Doc-set | `(product_code, version, doc_set)` | One help output inside a package, e.g. `bw-ent-html`. |
| Help identifier | the identifier string itself | Byte-exact, case-significant, always a string (§9). |

Every key is compared byte-exactly after trimming surrounding whitespace. Nothing is case-folded except where a rule below says so explicitly, and the two places it happens (`bu`, `family`) are controlled vocabularies, not data.

### 1.2 Tolerant read, strict write — **Built**

The single rule that governs all I/O at the edges of the tool:

> **Accept every form the outside world plausibly produces. Emit exactly one form.**

Reading is permissive because the two upstream sources — an undocumented JSON API and a spreadsheet — both mutate their output without notice. Writing is canonical because that is what makes a no-op run produce a zero-line diff, which is in turn what makes a real diff worth reading.

Applied to booleans, dates, encodings and column sets:

| Field kind | Accepted on read | Written as |
| :--- | :--- | :--- |
| Boolean | `true`/`1`/`yes`/`y`/`t`, any case; blank counts as false | `true` / `false`, lowercase |
| Date | ISO date, ISO timestamp, `m/d/Y`, `d/m/Y`, `Y/m/d`, `d-m-Y`; anything else verbatim | ISO `YYYY-MM-DD`, or the original text unchanged |
| Encoding | UTF-8 with or without BOM | UTF-8 **with** BOM |
| Columns | Any superset or subset of the declared set | The declared set, in declared order, nothing else |

**Boolean parse.** Trim, lowercase, and test against the true-set and the false-set. A value in neither set falls back to a caller-supplied default rather than to `false` — the default is what carries the rule "a blank `convert_eligible` means eligible if the version is active and ineligible if it is archived", which a hard `false` would silently break.

**Date normalization.** In order: an empty value yields empty; a value that starts with an ISO timestamp (`2025-02-06T09:21:53.000Z`) is truncated to its first ten characters, because the catalog records the day and the time of day is noise in a spreadsheet column; otherwise each format is tried in turn and the first that parses wins; and a value that parses as none of them — `June 2022`, which the archive API really returns — **passes through untouched**. Coercing or dropping it would lose the only release date some archived versions have.

The month-first format is tried before day-first deliberately: the hazard being defended against is a US-locale Excel rewriting `2025-11-04` as `11/4/2025`. A day greater than 12 fails the month-first attempt and falls through to day-first on its own.

**Column handling on write.** Fields outside the declared column set are dropped, not appended. A stray column typed into the spreadsheet is therefore lost on the next write rather than silently becoming part of the schema — the loss is visible and recoverable from git; a schema that grows by accident is neither.

### 1.3 Natural version ordering — **Built**

Versions must sort so that `10.4.0` sits above `9.1.0`, which a lexical sort inverts.

1. Split the version text on runs of digits, keeping the runs.
2. Discard empty pieces.
3. Map each digit run to the pair `(0, <integer value>)` and each non-digit piece to `(1, <lowercased text>)`.
4. Compare the resulting tuples.

The leading `0`/`1` tag is not decoration: it keeps a numeric piece from ever being compared against a textual one, which would raise. It also orders any numeric segment ahead of any textual one at the same position, so `2.0.0` sorts above `2.0.0-rc1` — a release above its own pre-releases, which is the intuitive reading.

### 1.4 Slugs and workspace folder names — **Built**

`slugify` turns any human string into a filesystem- and URL-safe token:

1. **Delete the trademark family** (`™ ® © ℠`) first.
2. Apply an NFKD Unicode fold and drop anything that is not ASCII.
3. Lowercase, replace every run of non-alphanumeric characters with a single hyphen, and strip leading and trailing hyphens.

Step 1 must precede step 2. NFKD gives `™` a *compatibility* decomposition into the literal letters `TM`, so folding first turns `TIBCO EMS™` into `tibco-emstm`. Nearly every product name in the catalog carries one of these symbols, so this is the common path, not an edge case.

`family_folder(locale, bu, family)` slugifies all three parts and joins them with hyphens — `en-us-tibco-messaging`. If any part slugifies to empty, it **raises** rather than returning `en-us-tibco-`, which would otherwise be created on the next download and then quietly accumulate every misclassified product.

### 1.5 Path derivation — **Built**

All working paths are computed from `(bu, family, product_code, version)` and are never passed between stages:

```
families/<locale>-<bu>-<family>/downloads/<product_code>-<version>.zip
families/<locale>-<bu>-<family>/extracted/<product_code>/<version>/
families/<locale>-<bu>-<family>/archive/<product_code>-<version>.zip
```

Derivation rather than passing is what lets a resumed run, a manually supplied ZIP, and a fresh download all land on the same location with no coordination (`architecture.md` §3.8, §4.1). The resolved path is *recorded* in `state.db` afterwards for audit and for resume, but it is never the authority — the layout function is.

---

## 2. Stage 1: Discovery

### 2.1 Request policy — **Built**

Every endpoint, URL template and politeness setting is read from `config/docsite.yaml`, so a moved endpoint is a config edit rather than a release.

One request proceeds as follows:

1. **Throttle.** If a rate limit is configured, sleep until at least `1 / rate` seconds have passed since the previous request *returned*. This is a hard floor between requests, not a token bucket — a burst of 250 product lookups is precisely the traffic shape this crawler generates, and a bucket would pass the whole burst through untouched.
2. **GET** with the configured timeout. Transport-level failures raise a `DocsiteError` naming the URL.
3. **Retry** is handled beneath this, by the HTTP adapter: up to *N* attempts with exponential backoff, but only on 429, 500, 502, 503 and 504, and only for GET. A 404 is **not** retried — an absent archive index is a normal answer for a product that has no history, not a transient fault.
4. **Reject non-200** with the status code in the message.
5. **Decode JSON.** If decoding fails, inspect the first 2 KB of the body: if it looks like HTML and contains a sign-in marker, report *"this product is not public"* rather than *"invalid JSON"*. The docsite serves its SSO interstitial with HTTP 200, and the distinction is the difference between a crawler bug and an access boundary.

The timestamp in step 1 is updated in a `finally` block, so a failed request still counts against the rate limit. Otherwise a run of failures would spin at full speed against a site that is already struggling.

### 2.2 Reading a payload that keeps changing shape — **Built**

Three helpers absorb the API's inconsistency. All are pure functions over already-decoded JSON, which is what lets the entire crawler be tested offline against canned records.

**Peel the envelope.** Responses arrive wrapped, sometimes twice: `{"result": {"product": {…}}}`. Repeatedly, while the payload is an object, look for the first of `result`, `data`, `response`, `payload`, `product` whose value is itself an object or a list, and descend into it. Stop when no candidate matches, or after as many iterations as there are candidate names — a bounded loop, so a self-referential payload cannot hang the crawl.

**Find the first present value.** Given a record and an ordered list of candidate key names, return the first value that is not `None`, `""`, `[]` or `{}`, as trimmed text. Key spellings differ per endpoint (`version_no` here, `versionNumber` there) and the API is undocumented; matching a handful of names costs nothing, while being strict would mean a release every time the docsite team renames a field.

**Find the first present *key*.** Same input, but return the key name rather than its value, and treat a declared-but-false value as present. This is deliberately distinct from the above, because for flags an explicit `false` and an absent key mean different things — see §2.6.

**Extract a list of records.** Given a payload that may or may not be wrapped, in order: return it if it is already a list of objects; look for each named candidate key holding a list, or holding an object that recursively yields records; look inside each envelope key; and finally, as a last resort, return any single list-of-objects found on the object. The last fallback exists to survive a wrapper nobody has seen yet, and is ordered last so it can never pre-empt a key that was named on purpose.

### 2.3 The crawl — **Built**

**Input:** an optional BU, family, and set of selectors (product codes and/or docsite slugs).
**Output:** a `CrawlResult` — the products built, the errors collected, and counts of entries skipped as unversioned or non-public.

1. **List products** from the A-to-Z endpoint (§2.4). A failure here is fatal to the crawl and returns immediately with the error recorded; there is nothing to iterate.
2. **Apply selectors, if given**, against the A-to-Z list. An entry matches if the selector set contains either its slug or the code derived from its slug. This filtering happens *before* any per-product request, which is what makes `--product` and `--batch` cheap: a three-product batch is three requests, not seven hundred. `bu` and `family` cannot be applied here — they are only known after classification — so they cost a full crawl.
3. **Load category data once**, if any entries survived, and only as an advisory hint (§2.7).
4. **For each entry**, build one product (§2.5). A `DocsiteError` is caught, recorded against the slug, and the loop continues.
5. **Apply the BU and family filters** to each built product.
6. Return.

**The partial-failure policy is the important part of this loop.** A product that could not be built is *absent from the result*, never present with an empty version list. An empty list would read to the merge in §3 as "every version of this product was deleted upstream", so a transient 503 would either abort the whole fetch or, with `--allow-deletes`, delete a product's entire history.

### 2.4 Normalizing the product list — **Built**

For each record in the A-to-Z payload:

1. Read the slug; **skip if absent** — the slug is the key every other endpoint is addressed by, so there is nothing to be done with an entry lacking one.
2. **Skip if already seen.** The list contains duplicates.
3. Read the public-visibility flag *as a key*: if the flag is declared and false, count the entry as non-public and skip it. If the flag is **absent**, treat the entry as public. 70 of the docsite's 739 entries are marked not public, and requesting one yields an SSO page as HTTP 200 — filtering here saves 70 requests and 70 spurious errors. Defaulting a *missing* flag to public means a future schema change degrades to noise rather than silently emptying the crawl.
4. Emit `{slug, name, id}`, falling back to the slug for a missing name.

### 2.5 Building one product — **Built**

1. **Fetch and unwrap** the product detail. A payload that is not an object raises.
2. **Assemble the record set.** The detail object *is* the current version — it carries `version_no` and `folder_path` itself — and every other release sits under `siblings`. So the set is `[detail] + siblings`. The siblings key is looked up **by name only**, never by the generic list search of §2.2, because that search would happily return the product's `Documents` array instead.
3. **Drop records with no version number.**
4. **If nothing remains, return "no product"** and count it as unversioned. These are licence pages and connector stubs: real docsite entries with nothing to convert. Counted rather than listed, because none of them are actionable.
5. **Derive the product code** (§2.6).
6. **Build the product shell** — display name, BU, family, provenance (§2.7).
7. **Build one version per record** (§2.6), inserting each **only if that version number is not already present**. The detail record is first in the set, so where a version appears twice the current-version record wins.
8. **Overlay the archive index** if archived versions are wanted and the archive flag permits (§2.8).
9. **Record the docsite slug and id** as metadata for `state.db` — not as catalog columns.

### 2.6 Deriving the product code and a version's folder — **Built**

**Product code.** The catalog's key for `tibco-enterprise-message-service` is `ems`, which is not derivable from the slug. It is read from a folder path instead:

1. For the detail record first, then every other record in turn, read the folder path and split it on the first `/`.
2. If **both** halves are non-empty — the path is version-shaped, `<code>/<version>` — slugify the first half and return it.
3. If no record yields one, fall back to the slug with a known vendor prefix (`tibco-`, `ibi-`, `spotfire-`) stripped.

The detail record is tried first because archived siblings carry stale paths (`enterprise_message_service`, `ems-zlinux`). The two-segment test is the whole guard: a one-segment path is exactly the stale form.

**Version folder.** For each version record the same split is applied, returning a pair:

- *declared* — the path the docsite actually published, non-empty only when the path has both segments. This is what gets recorded in `state.db`.
- *usable* — the declared path if there is one; otherwise the canonical `<code>/<version>` reconstructed for URL building only, or empty when there is no version to reconstruct from.

The distinction matters because a reconstructed path is good enough to build a URL from but is not a fact about the docsite, and recording it as one would mislead a later stage.

**Version record.** From each record: the version number; the archived flag; the declared/usable folder pair; the release date, normalized (§1.2); `convert_eligible` from the configured default for its archive status; and the ZIP URL —

> **`None` if the version is archived**, otherwise the active template applied to the usable folder path.

Archived versions are not published under the active layout, so a templated URL for one is a plausible-looking 404 recorded in the catalog as fact and discovered three stages later. Their real endpoints come from the archive index instead.

**Active ZIP URL construction.** Given a folder path, strip surrounding slashes; if either the template or the path is empty, return **nothing rather than a malformed URL**; otherwise substitute the path both verbatim and with `/` replaced by `_`, producing `/pub/ems/10.4.0/doc/zip/tib_ems_10.4.0_doc.zip`.

**Release-date candidates deliberately exclude `published_date`.** On old releases that field is a bulk-migration timestamp — every EMS 5.x and 6.x record reads `2022-05-26`. Leaving it out lets the archive index's `GA_date` supply the real month.

### 2.7 Family classification — **Built**

Applied when a product shell is built, in strict precedence order. Only the last two steps happen during a crawl; `manual` is a human's edit, preserved by the merge in §3.3.

1. **Keyword rules from `taxonomy.yaml`.** For each rule in file order, for each of its match tokens: the rule matches if the token equals the product code exactly (case-insensitively), or if the token appears as a substring of the display name (case-insensitively). **First rule to match wins**, so specific rules must be ordered above broad ones — the file is a decision list, not a set. A match yields `bu`, `family`, and provenance `taxonomy_rule`.
2. **No match** yields BU `tibco`, family `general`, provenance `unclassified`. The product is *flagged for triage*, not guessed into a family: with most products carrying no category data at all, a wrong-but-confident classification is more expensive than an honest gap.
3. **Advisory promotion.** If and only if the result is `unclassified` and the category endpoint supplied a category for this slug, take it as the family with provenance `docsite_category`. A category may fill a gap; it may never override a rule match.

**Display name** comes from the A-to-Z list in preference to the detail payload: the detail name carries the version number (`… 10.5.0`), and a version baked into a product-level row goes stale on the next release.

**Category loading is best-effort.** If the endpoint is not configured, or the request fails, record the failure as an advisory note and continue with no categories. Losing them degrades triage; it must not degrade the crawl.

### 2.8 Overlaying the archive index — **Built**

**Should the request be made at all?** Read the archive-exists flag *as a key*: an explicit `false` is trusted and saves one request per product; an **absent** flag is not read as "no", because the key is missing from some responses and skipping on absence would silently lose every archived version of those products.

If the request fails, record the error and return — non-fatal, because the active versions are the ones that get converted and abandoning the product over its history would be a poor trade.

For each archived child record, keyed by version number:

| Case | Action |
| :--- | :--- |
| Version unknown | Add it: archived, eligibility from the archived default, release date from `GA_date`, ZIP URL absolutised from `zipPath` |
| Version known and **active** | **Leave it alone.** A version listed in both places is the current one, and marking it archived would quietly make it ineligible for conversion |
| Version known and archived | Overwrite the ZIP URL from `zipPath` if the index has one; fill the release date **only if it is currently empty** |

The archive index *overlaps* the sibling list rather than replacing it, which is why this is an overlay with three cases rather than an append.

**URL absolutisation.** `zipPath` arrives both absolute and site-relative depending on the product, so a value already starting with `http://` or `https://` passes through unchanged and anything else is joined to the base URL.

---

## 3. The catalog merge

### 3.1 Loading and joining — **Built**

1. Read `products.csv`. Skip rows with no product code. Coerce each enum column tolerantly — an unrecognized token falls back to that column's default rather than raising, since a spreadsheet will eventually contain one.
2. Read `versions.csv`. Skip rows missing either the product code or the version.
3. For each version row, look up its product. **A version whose product is absent raises** and names both keys. This is a broken join, not a product to invent: silently creating a shell product would make a mistyped code look like a successful import.
4. Default `convert_eligible` to *not archived* when the cell is blank (§1.2).
5. Ignore the `_bu` and `_family` columns entirely on read. They are denormalized conveniences for spreadsheet filtering and are regenerated on every write.

### 3.2 The three-way field decision — **Built**

The merge takes three inputs per field: **base** (what discovery wrote last time, from `state.db`), **theirs** (what discovery returns now), and **mine** (what the CSV currently says). It reduces to a single predicate:

> **Take the fetched value only if the CSV value still equals the recorded snapshot.** Otherwise a human moved it, and the human wins.

With **no snapshot** — the first fetch after the state DB was adopted, or after it was discarded — the fallback is to **keep the CSV value unless it is empty**. Inventing a base would silently overwrite edits made before the snapshot existed; filling genuinely blank cells is safe and useful.

Comparison is textual on both sides: the snapshot stores everything as text, so `None` becomes empty string and booleans become `true`/`false` before comparing. The decision is **per field, never per row** — editing `display_name` must not also freeze the `slug` beside it.

Discovery owns exactly six fields, and merges only those: `display_name`, `slug`, `is_archived`, `convert_eligible`, `release_date`, `zip_url`.

**Four columns are excluded structurally**, meaning they are absent from the snapshot tables rather than skipped by a rule someone could later delete:

| Excluded | Because |
| :--- | :--- |
| `engine`, `engine_source` | Written by the detector *after* discovery. A fetch has nothing true to say about them |
| `convert_batch` | Written by no automated stage at all — pure human scheduling |
| `zip_source` | Records a human's decision to supply the package by hand, which a fetch has no standing to revoke |

`zip_url` stays merged even on a hand-supplied row. Recording the endpoint discovery has since found is exactly what makes "you can drop the manual pin now" a computable warning (§8.2) instead of something the user must notice.

**`custom_override`** short-circuits everything: on a product or version row it pins the whole row and no discovery-owned field is touched.

### 3.3 Family, by provenance rather than snapshot — **Built**

`family` is the one field resolved by ranking rather than by comparison, because two automated sources disagree with different confidence. Ranked `manual` (0) > `taxonomy_rule` (1) > `docsite_category` (2) > `unclassified` (3):

1. If the current provenance is `manual`, preserve — unconditionally.
2. Otherwise, if the incoming provenance ranks **equal or better** than the current one, run the ordinary three-way decision on the family value. If it takes the fetched value, `family_source` and `bu` move with it — a family is meaningless without the BU it belongs to.
3. Otherwise preserve.

A fetch may raise a product's classification confidence; it may never lower it.

### 3.4 Deletion detection — **Built**

For each product in the fetch, compute the version keys the catalog holds that the fetch of *that same product* did not return.

- With `--allow-deletes`: remove each from the catalog and purge every trace of it from `state.db`.
- Without: collect them, and after processing all products, **raise** with the full list and a note that this usually means a version key was mangled (Excel reading `1.10` as `1.1`).

Two properties matter. The check is **scoped to the products actually fetched**, so `catalog fetch --product ems` cannot read every other product's absence as a removal. And the raise happens **before** snapshots are recorded and before anything is written, so a blocked fetch leaves both CSVs and the state DB exactly as they were — the fetch is all-or-nothing.

### 3.5 Whole-merge sequence — **Built**

1. Load the catalog.
2. For each discovered product: add it wholesale if unknown; otherwise merge product fields (§3.2, §3.3) then versions — new versions added, existing ones merged field by field.
3. Collect deletions per product (§3.4).
4. If deletions were blocked, raise. Nothing has been written.
5. If this is a dry run, return the statistics without writing.
6. Record the new snapshots — this fetch becomes the next merge's base.
7. Save both CSVs.

The reported statistics count products and versions added and updated, fields preserved, and deletions blocked. Read `versions_updated` as *versions the fetch revisited*, not *versions that changed*; `fields_preserved` is the number that says how much of the user's work the merge protected.

### 3.6 Canonical write — **Built**

1. Sort products by `(bu, family, product_code)`.
2. Sort each product's versions by natural version key (§1.3), **descending**, so the newest release is the first row under its product.
3. Write the fixed column list in fixed order, regenerating `_bu` and `_family` from the product row.
4. Normalize every value on the way out: booleans lowercased, dates to ISO, `None` to empty string.
5. Write UTF-8 with BOM and CRLF line endings.

The sort is what makes a no-op fetch produce a zero-line diff, and the zero-line diff is what makes the catalog reviewable in git rather than merely stored there.

---

## 4. Selection: what a run acts on

**Built.** Two independent questions, two columns, composed at every stage command (`architecture.md` §3.7):

1. Walk products in catalog sort order, filtering by BU, family and product code where given.
2. Within each, walk versions in natural descending order, filtering by version where given.
3. If a batch label was given, keep only versions whose (trimmed, lowercased) batch matches.
4. If eligibility was requested, keep only versions with `convert_eligible` true.
5. Return the surviving `(product, version)` pairs.

Steps 3 and 4 **compose rather than override**: a version tagged into a batch but left ineligible is skipped, because eligibility is the hard gate and the batch is a filter within it. That combination is almost always a mistake, so it is reported as a warning naming the exact command that fixes it (§8.2) rather than being silently honoured or fatally rejected.

Batch labels are trimmed and lowercased on write, so `POC-1`, `poc-1 ` and `poc-1` are one batch and not three. The batch census counts versions per label and **omits unscheduled rows entirely** — folding 3,900 untagged rows into the same table would bury the answer to the question being asked.

---

## 5. Stage 3: Acquisition

**Specified.** The selection model and path contract are Built (§1.5, §4); the I/O is not.

### 5.1 Download one version

1. Resolve the canonical download path from `(bu, family, product_code, version)`. Never accept a path from the caller.
2. **Skip immediately if `zip_source` is `manual`.** The package is expected to be at that path already, placed by hand; fetching would overwrite it with whatever the stale URL now serves.
3. If the file exists and `state.db` holds a checksum for it that still matches, mark it downloaded and return. This is what makes a re-run over a completed batch cheap.
4. Otherwise fetch `zip_url` to a temporary file beside the target, resuming from the partial length if one is present and the server's validator (etag or last-modified) matches the recorded one. A changed validator discards the partial and restarts — resuming against a different file produces a corrupt archive that passes a length check.
5. Compute sha256 while writing, rather than in a second pass over the file.
6. Verify the result is a readable ZIP before moving it into place.
7. Move into place atomically, and record path, size, etag, checksum and status `DOWNLOADED` in `state.db`.
8. On failure, record status `ERROR` with the message and leave the partial file for the next resume.

**Open:** concurrency model (thread pool over versions versus async) and its default width. Whatever it is, the rate-limit floor of §2.1 applies to docsite requests as a whole, not per worker.

### 5.2 Ingesting a hand-supplied package

`--from-file` requires both a product and a version selector.

1. Reject unless the *product* exists in the catalog. A typo'd product code is unrecoverable and would seed a junk row.
2. If the product exists but the version does not, **add the version row with a warning**. The user has a real package in hand, which is stronger evidence the version exists than discovery's silence is that it does not.
3. Reject anything that is not a readable ZIP, before copying. The common real failure is not a corrupt archive but an HTML login page saved under a `.zip` name; caught here it is one line, caught at extraction it is a baffling failure days later.
4. **Copy — never move.** The user's own copy is not the tool's to consume.
5. Set `zip_source=manual`, and record the computed sha256, the size, status `DOWNLOADED`, and the originating path for audit. There is no upstream checksum to compare against, so the computed one is authoritative for later "is this still the same file" checks.

The archive variant is identical but targets the archive path, and its `--extract` unpacks within `archive/` — never into the pipeline's `extracted/` tree.

---

## 6. Stage 4: Extraction and inventory

**Specified**, except the catalog half of §6.3 (the columns, the round-trip and the write-back), which is **Built**.

### 6.1 Extract

1. Run over **the same selection as the download**, so an archived version is neither fetched nor unpacked.
2. Refuse any archive member whose resolved path escapes the target directory, and any absolute member path. A documentation ZIP has no legitimate reason to contain either.
3. Unpack to the canonical extract path, then record the resolved path and status `EXTRACTED`.
4. Inventory assets by extension — PDF, Word, Excel, text, images, nested ZIPs — into `state.db`, so Stage 5 can relink them and Stage 7 can account for them.
5. Walk the extracted tree once more, partitioning every file into API-reference or not, and write the five inventory columns back to `versions.csv` (§6.3).

### 6.2 CSH source inventory

Locating help maps is separated from parsing them, because the *absence* of a help map needs to be visible before conversion starts rather than discovered after (`architecture.md` §5.3, planning Phase 4).

For each doc-set inside the extracted tree, look for:

| Format token | Where | Parsed? |
| :--- | :--- | :--- |
| `flare_alias` | `<book>/Data/Alias.xml` | **Yes** |
| `dita_head_js` | `<doc-set>/static/head.js`, the `suitehelp.contexts` object | **Yes** |
| `webworks_topics` | `<book>/wwhdata/common/topics.js` | **Yes** |

**All three are read** (§9.2). Two nearby files are deliberately *not* consulted: `<doc-set>/ctx/` holds redirect stubs generated from the WebWorks map rather than the map itself, and `<book>/wwhdata/xml/files.xml` is a lossy XML twin of `topics.js` — where the two disagree it is the XML that is missing entries, and one observed book ships no `files.xml` at all.

A source that is located but fails to parse still sets `_has_csh` — a file *was* found — with the failure counted and named in the extract report. "This version has help we could not read" and "this version has no help" are different facts, and only one of them is acceptable to discover after publishing.

Record path, format, raw entry count and parse status per `(product, version, doc_set)`. **Empty, zero-byte and unparseable sources are counted and skipped, never raised** — an empty map is the *normal* case in every format, and overwhelmingly so in two of them: 476 of 863 Flare alias files (55%), 492 of 647 WebWorks `topics.js` (76%), 38 of 418 DITA `head.js` (9%). Raising would make a routine condition look like a defect. `docushift extract` prints the tally (`CSH: 3 sources, 561 entries`) so that a version with no help map is a fact known at extraction time.

### 6.3 Inventory write-back to `versions.csv`

**Built** — the columns, the blank-preserving round-trip, `CatalogManager.record_extract_inventory` / `clear_extract_inventory`, the merge exclusion and the desync warning. **Specified** — the API-reference predicate below and its triage report, which belong to the Stage 4 extractor and land with it.

(`architecture.md` §3.9.) The per-doc-set detail from §6.2 stays in `state.db`; what goes back into the sheet is the five numbers a human needs in order to set `convert_eligible` and `convert_batch` on a package they have not opened.

**Is a path an API reference?** One predicate, three callers (Stage 4 here, Stage 5's skip-list, Stage 7's doc-class router). Its shape is set by the corpus survey of 2026-09-07 (§6.3.1): **a marker decides, a name never does.**

1. **Find the API-reference roots.** Walk the extracted tree; a directory is a root if it holds one of the generator markers in §6.3.1 Finding 5. Record the roots, not the files.
2. **Every file beneath a root is an API reference.** Roots do not nest meaningfully — a Javadoc tree inside a Doxygen tree is one artefact — so the outermost match wins and the walk does not descend past it.
3. **Names classify nothing.** They are used for exactly one thing: raising a flag (below). This is what makes `api reference/` (with a space) and `hawk/6.2.2/console-api/` resolve correctly while `api-exchange-gateway/`, a product name, does not.
4. Where a name *is* compared — the flag, and nothing else — compare **whole segments, case-insensitively**. The corpus carries `API`/`api`, `C`/`c`, `JavaDoc`/`javadoc` and `Java_API`; and the predecessor's substring test over-matched 186,856 files on the pattern `/c` alone, including `csh.js` and the WebWorks `ctx/` help-source directory.

**The flag.** A marker list only knows the generators we have seen. So after the roots are found, any directory whose *name* looks like an API reference — a whole segment matching `api`, `apidocs`, `api-docs`, `api_reference`, `api-reference`, `api reference`, `javadoc`, `Java_API`, `java`, `c`, `cpp`, `golang`, `tibdg`, or ending `-api` / `_api` — but which sits under **no** marker root is reported by `docushift extract`:

```
API-reference triage: 2 unmarked candidates in ftl@6.10.0
  html/api-docs/            412 files, no known generator marker
  html/api-docs/dotnet/     311 files, no known generator marker
```

It is a report line, not a classification: the files stay in `_doc_files` until a human says otherwise. The flag exists so that a generator we have no marker for surfaces as a question at extract time rather than as broken Markdown at conversion time, and so the marker list grows from evidence. Products whose *name* contains `api` are the reason this cannot be silently auto-promoted.

**The five values,** computed in a single walk so they always describe one moment:

| Value | Rule |
| :--- | :--- |
| `_api_files` | Files whose path satisfies the predicate |
| `_doc_files` | Every other file. Not a topic count — images, CSS and skin assets are included, which is what makes it a footprint figure rather than a workload one |
| `_has_api_ref` | `_api_files > 0` |
| `_csh_names` | Distinct identifiers across all of the version's CSH sources, counted **byte-exactly and case-sensitively** — `GatewayInstances` and `gatewayInstances` are two (§9.1) — and deduplicated version-wide, matching how the resolver merges them (§9.3) |
| `_has_csh` | At least one **readable** CSH source file was located — Flare `Alias.xml` or DITA `head.js` — regardless of whether it parsed to anything. `true` with `_csh_names=0` is the empty-source case, 55% of the Flare corpus. A WebWorks source leaves this `false` and produces a triage line instead (§6.2) |

Directories are not counted, only files. Symlinks are not followed — a documentation ZIP has no legitimate reason to contain one, and Stage 4 already refuses escaping members (§6.1).

**Writing.** One call sets all five together, so the two booleans cannot disagree with the counts they summarize. It follows `record_detected_engine`: locate the row, set the fields, save. A version that extracted with errors is left blank rather than written zero — a failed run must not look like an empty package.

### 6.3.1 What the corpus says about API-reference paths

Measured 2026-09-07 against the predecessor `html-to-md` extracted cache: **2,201,528 files across 515 products**. The reproduction scripts are `C:\tmp\an_segments.py` and `an_segments2.py`; they need that cache, which is not in this repo.

**Finding 1 — the inherited seven-name list under-covers.** All seven segments do occur (283,267 files), but the corpus's real generated-API trees are named far more variously, and none of these are on the list:

| Segment | Files | What it is |
| :--- | ---: | :--- |
| `apidocs/` | 27,450 | Spotfire SFDS — Doxygen C++ and .NET |
| `apischemas/` | 16,464 | AMX BPM |
| `components-api/` | 15,563 | BPME |
| `api-docs/` | 3,935 | FTL — C and .NET |
| `api-reference/` | 3,257 | ActiveSpaces C/Go, eFTL JavaScript/Python |
| `console-api/`, `config-api/` | 3,930 | Hawk — Javadoc (`allclasses-frame.html`, `COM/TIBCO/…/class-use/`) |
| `cpp-reference/`, `c-and-cobol-reference/` | 3,200 | Rendezvous, EMS |
| `api reference/` | 1,141 | Contains a space |
| `api_reference/` | 1,084 | Loyalty |

Observed spellings: `api`, `apidocs`, `api-docs`, `api_reference`, `api-reference`, `api reference`, `<product>_api_ref`, `<thing>-api`. Across 515 products written by different teams over fifteen years there is no naming convention to key off.

**Finding 2 — widening to a substring test is worse, not better.** `api-exchange-gateway/` (15,677 files) and `api-exchange-manager/` (1,015) are *product names* — TIBCO API Exchange Gateway. A "contains api" rule discards an entire product's documentation. This is why the predecessor's approach fails: it tests `seg.rstrip("/") in path`, so its `/c/` entry becomes the substring `/c` and matches **186,856 files (8.5% of the corpus)** that are not API references at all — `csh.js`, `collapse.png`, `contents.htm`, `css/`, `common/`, and the WebWorks **`ctx/` directory, which is a CSH source**. A rule meant for the C API has been quietly skipping context-sensitive-help inputs.

**Finding 3 — casing is not stable.** `API`/`api`, `C`/`c`, `JavaDoc`/`javadoc`, and `Java_API` all occur. Comparison must fold case. (This is the one place in the tool that does: CSH identifiers are byte-exact, §9.1. Paths are not identifiers.)

**Finding 4 — `javascript/` is an API tree, not documentation.** Every occurrence is `eftl/*/html/api-reference/javascript/eFTL.html` beside `styles/jsdoc-default.css` — JSDoc output. It is already covered by its `api-reference/` parent. `c-tutorial/` does not exist in the corpus.

**Finding 5 — the trees are identifiable by content even when the name is unguessable.** Each generator leaves an unmistakable marker at the tree root:

| Generator | Marker |
| :--- | :--- |
| Javadoc | `allclasses-frame.html`, `package-frame.html`, `index-all.html`, `class-use/` |
| Doxygen (C / C++) | `annotated.html`, `*_8h.html` |
| JSDoc | `styles/jsdoc-default.css` |
| godoc | `lib/godoc/godocs.js` |
| Sandcastle (.NET) | `fti/FTI_*.json`, `Help/html/<guid>.htm` |

This is the same conclusion §7 reaches for engine detection, for the same reason: **what a tree contains is knowable; what someone named it is not.**

## 7. Stage 5: Engine detection

**Specified** (`architecture.md` §3.4). Rules measured against the whole `html-to-md` cache on 2026-09-08 — 1,822 versions, of which 539 (29.6%) carry no HTML at all and are not this algorithm's problem.

### 7.1 The rules

Run per version, over the extracted tree, in three passes.

**Pass 1 — layout markers.** Cheapest and least ambiguous: a directory listing decides it.

| Engine | Markers | Versions |
| --- | --- | --- |
| Flare | `*.mcwebhelp`, `*.mclog`, `MicroContent/`, `_globalpages/`, `csh.js` | 595 |
| WebWorks | `wwhelp/`, `wwhdata/` | 176 |
| DITA (SDL) | `GUID-*.html` filenames, or `static/head.js` + `static/body.js` | 371 |
| R help | `snext.css` or `snextchm.css` | 11 |

19 further versions match Flare *and* WebWorks markers — a Flare output with a WebWorks tree left beside it. Flare wins; the per-folder map (below) keeps the ambiguity visible.

**`Skins/` and `Data/` were dropped from the Flare row on 2026-09-08** (`architecture.md` §5.1.2). Over all 1,822 cached versions the seven-marker list matched 689 against 595 that actually hold a `Data/HelpSystem.xml` runtime: `Skins/` is 91.4% precise and `Data/` 88.0%, because other publishers use directories by those names too. **All 94 false positives come from those two markers and no other** — 43 matched both, 38 `Data/` alone, 13 `Skins/` alone; 17 are WebWorks, 3 DITA, and 74 carry no engine marker at all (mostly 2010–2013 adapter packages). Removing them costs no recall: **`*.mcwebhelp` alone finds all 595 and `csh.js` alone finds all 595.** Worth a regression test with a WebWorks fixture that ships a `Skins/` directory: under the old list it detects as Flare.

**And the casing matters, in the opposite direction to §7.2's DITA rule.** The figures above are case-insensitive matching. Matching exact casing gives 631 matches and 36 false positives and makes `Skins/` 100% precise — every non-Flare match was a lowercase `skins`. `Data/` misfires either way: 36 versions ship a correctly-cased `Data` with no Flare runtime. So case sensitivity is decided per signal here — mandatory-insensitive for `DC.*` (§7.2), and not worth specifying for a marker that is being dropped anyway.

**Flare root detection is a separate step from engine detection.** The engine answers "which converter", per version; the converter then locates its units of work by walking for `Data/HelpSystem.xml`, since **51 of 595 versions ship more than one output root and 153 roots nest inside another** (`architecture.md` §5.1.1, §5.1.3). The walk descends into nested roots rather than stopping at the first match, and the innermost root owns a file.

**Pass 2 — content signatures.** Corroboration for pass 1, and the *only* means of identifying DocBook, whose flat HTML output has no distinctive layout. Signatures: the `MadCap` namespace and `MadCap:*` attributes; the WebWorks generator meta tag; the DITA-OT generator comment; `DC.Type` / `DC.Identifier` / `DC.Title` meta tags (SDL DITA); `class="RdName"` / `class="RdTitle"` (R help); the `DocBook XSL Stylesheets` generator comment.

**Pass 3 — the generator meta tag.** A last look for `<meta name="generator">`, which names the remaining long tail outright: Adobe RoboHelp 11, Microsoft FrontPage 6.0, Help & Manual, MkDocs / mkdocs-material, Docusaurus, Apache Maven Doxia. 19 versions, ~7,200 files. None of these has a Stage 5 handler; they are recorded anyway (§7.3). A string we cannot map to a known name becomes `other`, with the raw value kept in `state.db`.

### 7.2 Why DITA needed its own rule

The original spec looked for DITA the way DITA-OT leaves it: `.dita` remnants and the DITA-OT generator comment. **The corpus has almost none of that.** TIBCO publishes DITA through SDL's publisher, which emits neither marker — so 371 versions and 61,712 HTML files, the second-largest engine in the corpus and larger than WebWorks, detected as `auto`.

The signals SDL *does* leave, measured over the 408 HTML-bearing versions that the original rules missed:

| Signal | Hits |
| --- | --- |
| `static/head.js` + `static/body.js` | 382 |
| `screen.css` + `print.css` | 382 |
| `DC.*` meta tags | 369 |
| `GUID-*.html` filenames | 316 |

`GUID-*.html OR DC.* meta` recovers 371; the R-help rule recovers 11 more. Together **382 of 408 (94%)**, taking coverage of HTML-bearing versions from **68% to 98%**. The residue is ~6 hand-authored `openspirit-*` versions and a handful of one-offs, which stay `auto` and should.

**The two clauses of the DITA rule match two different publishers**, which the 2026-09-08 converter survey (`architecture.md` §5.2.1) separated: `GUID-*.html` matches 316 SDL SuiteHelp versions, and `DC.*` meta picks up ~55 more that SuiteHelp never touches — file-named topics under `topics/`, all in the Spotfire family. That is why the `DC.*` hit count (369) exceeds the GUID one (316) rather than merely corroborating it, and it is the reason both clauses stay: dropping `DC.*` as redundant would lose a sixth of the DITA corpus.

**`DC.*` is matched case-insensitively.** SuiteHelp writes `DC.Type`, the file-named flavour writes `DC.type`. A case-sensitive match silently drops all 66 of the latter's versions — it did exactly that once during the survey, and produced a confident, wrong "correction" of 371 down to 316 before the casing was spotted.

Two lessons are worth keeping. First, the CSS/JS pair is the *broadest* signal but the worst rule — `screen.css` + `print.css` is a filename coincidence waiting to happen, so the specific signals are preferred even though they match less. Second, `<!-- NewPage -->` in the `bex` and `spm` trees is **Javadoc**, not a missing engine: those are API-reference trees, and the §6.3 predicate — not this algorithm — is what should be claiming them.

### 7.3 What detection does with the answer

1. **Never guess.** A version matching no signature stays `auto` and is skipped at conversion with a warning. A wrong engine does not fail — it produces plausible-looking, silently wrong Markdown, which is the most expensive outcome available.
2. **Name what cannot be converted.** `auto` and "R help" are both unconvertible, but they are not the same fact, so they do not share a value: `auto` means *undetected* and is a detector bug, while a named engine with no handler is a scoping decision for a human. `SourceEngine` therefore carries the pass-3 generators as real values, and Stage 5 tests membership of `CONVERTIBLE_ENGINES` rather than "is it `auto`". `warnings()` reports an identified-but-unconvertible engine on a `convert_eligible` row, because such a row *looks* settled in the sheet and silently produces nothing.
3. **Never override a manual value.** Writing back is refused outright when `engine_source` is `manual`; otherwise the engine is written with `engine_source=detected`.
4. **Record the per-guide-folder map** in `state.db` regardless. One version's ZIP commonly bundles nine sibling guide folders of a single Flare output; should a bundle ever genuinely mix generators, the map makes it visible rather than flattening it into one CSV cell.

This is the step that makes the catalog a mid-pipeline write target: the engine cannot be known at discovery, so it is written back after extraction and read by conversion.

---

## 8. Verification and reporting

### 8.1 Catalog validation — **Built**

`validate()` returns problems that **block** an import. Each is a shape that indicates data damage rather than a choice:

1. **Versions known to discovery but absent from the CSV.** Compared against the snapshot table; this is the Excel `1.10` → `1.1` coercion, caught by name.
2. **Engine `auto` with a resolved engine source** — an internally inconsistent row.
3. **Convert-eligible with no `zip_url`** — *except* on a `zip_source=manual` row, whose package arrives by hand and legitimately has no URL.

### 8.2 Catalog warnings — **Built**

`warnings()` returns things worth saying that must **not** block a write, kept structurally separate because the two have opposite consequences:

1. **A family not declared in `taxonomy.yaml`**, naming the workspace folder that will be created. Families are user-extensible by design (`architecture.md` §4.2); the warning is what stops a typo (`mesaging`) from silently becoming a third family folder holding one product. If the family name cannot even form a folder, that failure is reported in its place.
2. **In a batch but not eligible** — nothing downstream will ever pick this row up. The message includes the exact `catalog enable` command that fixes it.
3. **`zip_source=manual` but discovery now has a URL** — the pin still wins; the user may no longer need it.
4. **An inventory boolean disagreeing with its count** — `_has_api_ref=false` beside a non-zero `_api_files`, or `_has_csh=false` beside a non-zero `_csh_names` (`architecture.md` §3.9). The tool writes both from one computation, so this shape only arises from a hand-edit. A warning rather than a problem: the values are advisory, the next `docushift extract` overwrites them, and blocking an import over a stale summary column would be out of proportion.

### 8.3 Triage progress — **Built**

Count products by family provenance and list the unclassified ones. This turns "classify 250 products" from an unbounded chore into a number that goes down, which is the only reason the provenance column exists.

### 8.4 Link, asset and CSH integrity — **Specified**

`docushift validate` treats CSH as link integrity, because that is what it is (§9.6).

**Links are classified before they are checked.** A relative link resolves against the filesystem and a missing target is an error. An absolute URL is external — which, after Stage 7, includes every rewritten API-reference link (`architecture.md` §6.4) — and is skipped by default, checked over HTTP only behind an explicit flag. Checking the two the same way would report the entire API surface of every product as broken.

---

## 9. Context-Sensitive Help

**Specified.** This is the most intricate algorithm in the tool, and the one grounded most directly in measurement — now re-measured over the whole cache: **863 `Alias.xml` files, 387 with content, 11,054 entries, 2,396 distinct names**, superseding the 2026-09-04 subset of 272 files / 7,220 entries. **Scope: all three HTML engines — Flare, DITA and WebWorks** (§9.2). The full evidence table and the reasoning are in `architecture.md` §5.3; what follows is the procedure.

### 9.1 The single identifier rule

Flare offers one key that is genuinely unique, and it is not the integer: the `Map`'s `Name`. `ResolvedId` is parsed — so that a malformed entry is still recognised as an entry — and then discarded. The identifier is typed as a **string**, not as an integer and not as a name-shaped token.

Three consequences follow, and all are correctness requirements rather than style:

- **Comparison is byte-exact.** `GatewayInstances` and `gatewayInstances` are two different live help targets in TIBCO BC 7.4/7.5. With no integer to disambiguate them, case is the only thing that does — and the full-cache re-measure finds **8 such case-only collisions**, so this is not a single anecdote.
- **The string typing is carried by Flare alone.** It is often attributed to WebWorks, but WebWorks needs none of it: its identifiers are dotted lowercase names with **zero digit-only and zero case-only collisions** in the corpus. Flare supplies the whole justification on its own — **834 of 11,054 names (7.5%) are digit-only** (`12`, `1000`, `1122`), and the 8 case-only collisions above are all Flare's.
- **Identifiers are always emitted double-quoted**, in map keys and in frontmatter alike. A YAML 1.1 loader turns an unquoted `1234` into an integer and `6.2` into a float, in a map documented as string-keyed. Measured over Flare the live hazard is *only* numeric coercion — zero names are `Yes`/`No`/`On`/`Off`/`null`-shaped, zero are sexagesimal, zero carry a leading zero — but the rule is applied to every identifier rather than narrowed to the digit ones, because a conditional quote is a branch that can be wrong and an unconditional one cannot.

### 9.2 Three readers, one per HTML engine

The schema, the resolver and the writer are shared and engine-neutral; an engine contributes only a reader yielding `(identifier, link, anchor)`. **Every format the corpus ships is read.**

| Engine | Read from | Identifier | Status |
| :--- | :--- | :--- | :--- |
| Flare | `<book>/Data/Alias.xml`, one `Map` element per entry | the `Name` attribute | **Supported** |
| DITA (SDL) | `<doc-set>/static/head.js` → `suitehelp.contexts` | the JSON object key | **Supported** |
| WebWorks | `<book>/wwhdata/common/topics.js` | the `WWHBookData_MatchTopic` case label | **Supported** |
| DocBook | nothing observed | — | No CSH exists |

**The DITA contract, measured.** `static/head.js` assigns a single flat JSON object:

```js
suitehelp.contexts={"bwmarketo_palette":"GUID-3F0A….html","bwmarketo_conn":"GUID-9C21….html", …}
```

Identifier → target HTML file, one level deep, no nesting and no per-entry attributes — materially simpler to read than Flare's `Alias.xml`. It is present in **380 of 418 `static/head.js` files (91%)**; the remaining 38 assign an empty object, which is the DITA equivalent of Flare's empty `<CatapultAliasFile />` and is counted and skipped the same way. Because the values are plain file names, the fragment split below usually finds no fragment — the reader still applies it rather than special-casing, since the shape is the same.

**The WebWorks contract, measured.** `wwhdata/common/topics.js` is a generated dispatch chain, one file per book:

```js
function  WWHBookData_MatchTopic(P)
{
var C=null;
if(P=="as400.palette.gettingstartedurl")C="adas400_gettingstarted.6.1.htm#1674528";
if(P=="as400.instance.helpurl")C="adas400_instance.7.1.htm#1851467";
return C;
}
```

The reader takes each `if(P=="<identifier>")C="<target>"` pair. Identifiers are dotted lowercase names; targets are a file plus, 43% of the time, a Frame-generated numeric anchor. Present in **647 of 692 `wwhdata/` trees (93%)**, of which 155 carry at least one case — the other 492 (76%) return `null` unconditionally and are the WebWorks equivalent of an empty `<CatapultAliasFile />`.

It is the cleanest of the three sources. **All 3,439 targets exist and all 1,492 anchors are present in the file they name** — 100% internal integrity, against Flare's 78%.

**Two nearby files are not the source, and picking either would be a mistake.** `wwhdata/xml/files.xml` holds the same map as `<... name="id" href="file#anchor" />` and agrees with `topics.js` in 153 of 155 books — but the two disagreements are entries *missing from the XML*, and one book ships no `files.xml` at all, so the XML is the lossy twin despite being the more parseable format. `ctx/<book><n>.htm` is not a map either: each file is a two-line redirect stub carrying `document.location = "../index.htm?context=…&topic=…"`, generated from the map rather than holding it.

**How this section had WebWorks wrong.** Until 2026-09-08 WebWorks was out of scope, on the argument that its reader depended on `ctx/`, and that `ctx/` was missing from 90% of WebWorks output — 692 `wwhdata/` trees against 69 `ctx/` directories. Both halves were wrong. The ratio compared a **per-book** directory against a **per-doc-set** one, and WebWorks averages 3.5 books per doc-set; measured at matching granularity, 68 of the 186 doc-sets holding WebWorks books have a `ctx/`, which is 37%. And the reader never needed `ctx/` in the first place. The general form of the error is worth naming, because it produced two descoping decisions in one day: a ratio between two counts is only evidence if the counts are of the same kind of thing.

A link may carry a fragment — `config/Getting_Started.htm#adb.palette…` in 3% of Flare entries, a numeric `#1674528` in 43% of WebWorks ones. The reader splits it: the path is the link, the fragment is the anchor. WebWorks is why that field is not optional decoration.

### 9.3 Resolution

Run **after** the version's topics have been converted, so resolution tests against files that were actually produced.

1. **Collect** every CSH source under the version's extracted tree, grouped by doc-set.
2. **Parse** to `(identifier, link, anchor, doc_set)`. Empty, zero-byte and unparseable files are counted and skipped.
3. **Resolve within the doc-set first**: map the link's `.htm` path to the Markdown file the converter emitted for that HTML file.
4. **Fall back version-wide**: if the link does not resolve in its own doc-set, try the identical relative path in every sibling doc-set. One hit wins. This is a Flare remedy specifically — WebWorks links resolve inside their own book 100% of the time, so on a WebWorks version the step never fires.
5. **Merge by identifier.** The same target reached from several doc-sets collapses to one entry. Different targets produce a primary plus alternatives under `also`. **The primary is the doc-set with the most resolved entries; ties break alphabetically** — deterministic, and it picks the main help output over a release-notes or getting-started sidecar every time.
6. **Emit** `csh.yml`, then the frontmatter.

**Step 4 is the one that earns the per-version file.** Flare frequently copies one output's alias file wholesale into a sibling where none of its links exist: 1,609 of 7,220 links (22%) dangle inside their own doc-set, and 10 of the 11 affected files are a `relnotes` alias resolving at 0%. Per-doc-set resolution would report 205 broken identifiers for BW release notes; version-wide resolution resolves all 205 against the main output, where the topics actually live.

**Steps 3 and 4 depend on a source-HTML → output-Markdown mapping** recorded per version in `state.db` by the converter, rather than recomputed here. Recomputing it would let CSH resolution disagree with what conversion actually did about renaming, deduplication, or dropped topics — and disagree silently.

### 9.4 Writing `csh.yml`

One file per version at the Markdown output root, beside `toc.yml`. It carries the schema tag, the product/version/engine, the per-source tally (entries and resolved counts per doc-set), the counts, the `topics` map, and the `unresolved` list.

- **`topics` is the only index**, keyed by the identifier. A schema with one key cannot develop a disagreement between two.
- **`file` is POSIX and relative to `csh.yml`**, so the whole output tree relocates without a rewrite. `anchor` stays a separate field rather than being appended, because the consumer decides how to fragment-encode it and because an anchor's existence is separately checkable.
- **`also` appears only on a genuinely conflicting identifier**; its absence means "unambiguous in this version", which is the common case.
- **`unresolved` keeps every entry whose link matched no produced topic anywhere in the version**, with the original link. Dropping them would convert a broken Help button into a silent absence that no later check can find.
- **A version with no CSH source, or only empty ones, gets no file at all.** An empty map is indistinguishable from a failed run; absence plus a report line is the honest signal.

### 9.5 Frontmatter

A topic that owns identifiers carries them as a flat list of quoted strings:

```yaml
csh: ["bw_rest_binding", "restBindingRef"]
```

Always a list, even at length one, because a page commonly owns several. Topics with no identifier get no key at all.

Identifiers are known before conversion writes the file — parsing a 24 KB alias file is cheap — so frontmatter lands in the topic's **first and only write**, not in a second read-modify-write pass over the whole output tree.

### 9.6 CSH verification

- Every `file` in `csh.yml` exists, and every `anchor` is present in that file.
- Every identifier in a topic's frontmatter appears in `csh.yml`, and every identifier in `csh.yml` appears in its topic's frontmatter.
- `unresolved` is empty, or each entry in it is accounted for in the report.
- **Cross-version regression:** identifiers present in the previously converted version and absent from this one are reported. A dropped identifier is an upgrade that breaks the product's Help button, and it cannot be seen from inside a single version.

---

## 10. Stages 6 and 7: Synthesis and sync

**Specified.** Navigation synthesis walks the converted tree to produce `toc.yml`, `nav.yml`, `meta.yml` and landing pages from the Jinja templates in `config/aem_templates/`, then the distributor copies each version's output into the target repository layout.

**Navigation synthesis does not just serialize what the engine handed it.** Two nodes come from the synthesizer rather than from the source TOC, both settled by the 2026-09-09 Flare survey (`architecture.md` §5.1.5) and both engine-neutral:

- **The landing page is the first node.** The engine reports which converted topic is the version's landing page — for Flare, `HelpSystem.xml`'s `DefaultUrl`, which resolves in 676 of 676 output roots but is absent from the TOC in 55 of 60 sampled ones. If that topic is already a TOC node it moves to first; otherwise it is inserted as first. It never falls through to "Unfiled".
- **A node with children and no page gets a generated one.** AEM treats a childed navigation node with no page as a broken parent, and Flare's `'___'` sentinel produces 165 of them per 60 output roots — 151 at top level, holding 1,357 children between them. The synthesizer emits a page titled from the node's label whose body links its immediate children, stamped as generated in frontmatter so a re-run replaces it rather than treating it as authored. Childless headless nodes are dropped and counted.

**The sync path shape is settled** (`architecture.md` §6.1): the publishing form `{locale}-{bu}-{family}/{locale}/{product}/{doc-class}/{version-dashed}/`, with the docs repo taking `online-help`, `user-guides`, `release-information` and `reference-documents`, and a sibling `-resources` repo taking `api-references` and `archives`. The distributor therefore does four things per version, in order: copy the converted tree and its navigation into `online-help/`; copy the PDF and document assets into their three doc-classes; copy the API-reference trees, unconverted, into the sibling repo; then rewrite every link that crosses from one repo to the other. The rewrite is last because it needs both destinations to exist, and it belongs here rather than in Stage 5 because conversion does not know the publishing layout.

The dots-to-dashes version conversion belongs here too, at the publishing boundary, and nowhere earlier: the working tree's dotted version must round-trip to a `versions.csv` key, which `6-2-3` cannot (`6.2.3`? `6-2.3`?).

`-resources` is a **separate repository**, not a directory in the docs repo (`architecture.md` §6.3) — generated API trees and archived ZIPs grow monotonically, do not delta, and are not reviewed like prose.

### 10.4 Step 2, the document router — **Specified**

Which doc-class a non-converted document lands in. Grounded in a 2026-09-07 survey of 1,822 versions and 11,633 documents (`architecture.md` §6.2.1).

**Locate the two source folders.** For a version's extracted root `V`, the PDF folder is `V/pdf` or `V/doc/pdf`, and the document folder is `V/doc`. Both depths occur — 1,123 versions put `pdf/` and `doc/` at the root, 373 nest them under `doc/`. Check both; a version may have either, both, or neither. Only *files directly inside* these folders are routed here: subdirectories are the converter's and the API router's business, not this step's.

**Four name patterns**, matched against the filename stem, case-insensitively, with `[\s_.-]?` standing for the optional separator:

| Pattern | Matches |
| :--- | :--- |
| release-note | `relnotes` \| `(^\|[\s_.-])rel(ease)?[\s_.-]?notes?` \| `readme` |
| vpat | `vpat` |
| licence | `licen[cs](e\|ing)` |
| reminder-notice | `remind(er)?[\s_.-]?notice` |

**Route**, first match wins:

1. A file in the **document folder** → `release-information` if it matches release-note, otherwise `reference-documents`. There is deliberately no second test: licence, reminder notice, RTU and the CSV/XLSX/HTML strays all share one destination, so asking anything beyond *is this the readme* would add branches that cannot change the answer.
2. A file in the **PDF folder** → `reference-documents` if it matches vpat, licence or reminder-notice; else `release-information` if it matches release-note; else **`user-guides`**.

`user-guides` is the **default, not a match**, which is why the router has no unclassified bucket and why a generator that ships an unfamiliar guide name is published rather than dropped.

**Three rules about the patterns themselves**, each of which the corpus broke at least once:

- **`\b` is not a usable boundary here.** `_` is a word character, so `\b` does not match between `_` and `rel`, and a first pass written with it misrouted **1,753 `*_relnotes.pdf` files into `user-guides`**. The alternation therefore lists `relnotes` bare and anchors the spelled-out form on `(^|[\s_.-])`.
- **Spaces are a real separator.** `mft platform server v7.1 for windows release notes.pdf` and `tibco nimbus control 8.1.3 release notes.pdf` exist. A pattern accepting only `_` and `-` misses them.
- **`licence` and `licencing` are spelled both ways** (`tib_nimbus_9.1.0_licencing_doc.pdf` beside `tib_control_9.0.1_licensing_doc.pdf`), hence `licen[cs](e|ing)` rather than a literal.

Validated against the full corpus, the residue in `user-guides` after routing is **4 files** — `special-notes` ×2 and `liveviewweb_newnote` ×2 — all of which are genuine guides that merely contain the word "note". Nothing is misrouted and nothing is unrouted.

**Step 4, the link rewrite, in full.** Every link from a converted topic into an API-reference path (`api/`, `javadoc/`, `Java_API/`, `java/`, `c/`, `golang/`, `tibdg/`, however many `../` deep) is replaced with an **absolute URL**: `publish_base_url` from `config/publishing.yaml`, then the same `{locale}-{bu}-{family}-resources/{locale}/{product}/api-references/{subdir}/{version-dashed}/{rest}` template that placed the file. Link construction and file placement call one function, so a link cannot point somewhere the copy did not write. Links that stay inside the docs repo — within `online-help/`, or out to the PDF doc-classes — are left relative, which is what keeps the repo previewable before publication.

---

## 11. Invariants

Properties that hold across the whole tool. Each is a rule some algorithm above exists to maintain, and each is worth testing directly.

1. **A load-then-save cycle with no changes produces a byte-identical file.** (§3.6)
2. **A fetch never loses a human edit**, and never requires the human to have flagged it. (§3.2)
3. **A fetch is all-or-nothing.** A blocked deletion leaves both CSVs and the state DB untouched. (§3.4)
4. **No machine-local path appears in either CSV.** Locations are derived; only intent is stored. (§1.5)
5. **An archived version is never downloaded, extracted or converted** unless a human flips its eligibility. (§4)
6. **An unknown engine is never guessed.** A version stays `auto` and is skipped loudly. (§7)
7. **A hand-supplied package converts through exactly the same path as a downloaded one.** No downstream stage branches on provenance. (§5.2)
8. **A help identifier is either resolved or listed as unresolved.** Nothing is silently dropped, and identifier text round-trips byte-exactly as a string. (§9)
9. **Absence is reported, never faked.** No empty `csh.yml`, no empty version list from a failed crawl, no stage command that exits 0 having done nothing.
10. **An unmeasured value is blank, never zero.** The inventory columns distinguish "never extracted" from "extracted, found none", and no stage writes them for a run that failed. (§6.3)
11. **One path is classified as an API reference by exactly one predicate**, shared by the Stage 4 count, the Stage 5 skip and the Stage 7 route. (§6.3)

---

## 12. Algorithm index

| § | Algorithm | Status | Implementation |
| :--- | :--- | :--- | :--- |
| 1.2 | Tolerant read / strict write | Built | `utils/csvio.py` |
| 1.3 | Natural version ordering | Built | `utils/csvio.py:natural_version_key` |
| 1.4 | Slug and folder naming | Built | `utils/slug.py` |
| 1.5 | Path derivation | Built | `config.py` |
| 2.1 | Request policy and throttling | Built | `discovery/client.py` |
| 2.2 | Tolerant payload reading | Built | `discovery/crawler.py` |
| 2.3 | The crawl | Built | `discovery/crawler.py:discover` |
| 2.4 | Product-list normalization | Built | `discovery/crawler.py:_list_products` |
| 2.5 | Building one product | Built | `discovery/crawler.py:_build_product` |
| 2.6 | Code, folder and ZIP URL derivation | Built | `discovery/crawler.py`, `client.py:active_zip_url` |
| 2.7 | Family classification | Built | `config.py:resolve_product_info` |
| 2.8 | Archive index overlay | Built | `discovery/crawler.py:_apply_archive_index` |
| 3.1 | Catalog load and join | Built | `catalog.py:load` |
| 3.2 | Three-way field decision | Built | `catalog.py:_take_theirs` |
| 3.3 | Family by provenance | Built | `catalog.py:_merge_product` |
| 3.4 | Deletion detection | Built | `catalog.py:_collect_deletions` |
| 3.6 | Canonical write | Built | `catalog.py:save` |
| 4 | Selection | Built | `catalog.py:iter_versions` |
| 5.1 | Download one version | Specified | Phase 4 |
| 5.2 | Hand-supplied ingestion | Specified | Phase 4 |
| 6.1 | Extraction | Specified | Phase 4 |
| 6.2 | CSH source inventory | Specified | Phase 4 |
| 6.3 | Inventory columns and write-back | Built | `catalog.py:record_extract_inventory`, `utils/csvio.py` |
| 6.3 | API-reference predicate and triage | Specified | Phase 4 |
| 7 | Engine detection | Specified | Phase 5 |
| 8.1–8.3 | Catalog validation, warnings, triage | Built | `catalog.py` |
| 9.3 | CSH resolution | Specified | Phase 5 |
| 9.4–9.5 | `csh.yml` and frontmatter | Specified | Phase 5 |
| 9.6 | CSH verification | Specified | Phase 7 |
| 9.2 | CSH readers (**Flare, DITA, WebWorks**) | Specified | Phase 5 |
| 10 | AEM synthesis and sync | Specified | Phases 6–7 |
| 10.4 | Document router (`pdf/` and `doc/` → doc-class) | Specified | Phase 6 |
