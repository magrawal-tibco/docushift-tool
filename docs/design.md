# DocuShift Design Document: Logic & Algorithms

> **Document Status:** Living Design Specification
> **Last Updated:** 2026-09-11
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
| Product | `slug` | The docsite slug, e.g. `tibco-enterprise-message-service`. Required; a product without one is a discovery error. |
| Version | `(slug, version)` | `version` keeps its dots (`10.4.0`) everywhere except the published AEM path. |
| Doc-set | `(slug, version, doc_set)` | One help output inside a package, e.g. `bw-ent-html`. |
| Help identifier | the identifier string itself | Byte-exact, case-significant, always a string (§9). |
| End-of-support row | `(resolved slug, version)` | The report carries a product *name*, resolved to a slug by `slugify` or a reviewed alias (§3.3.2). `version` is matched byte-exactly — never coerced. |

Every key is compared byte-exactly after trimming surrounding whitespace. Nothing is case-folded except where a rule below says so explicitly, and the two places it happens (`bu`, `family`) are controlled vocabularies, not data.

**`product_code` is not a key** (`architecture.md` §3.1). It is a short label derived from the docsite's ZIP folder path — `ems`, `dsp_gridserver` — and 21 of the 634 products share one with a sibling. It is carried as a column because it is what a human types and what taxonomy rules match, and `--product` therefore accepts it; but resolution goes through the catalog, and a code naming more than one product is refused with the candidate slugs rather than resolved to one of them.

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

`family_workspace_folder(locale, bu, family)` slugifies all three parts and joins them with hyphens — `en-us-tib-messaging`. Its `bu` and `family` are `repo_slug` tokens resolved from `taxonomy.yaml` by `ConfigManager`, not raw keys. If any part slugifies to empty, it **raises** rather than returning `en-us-tib-`, which would otherwise be created on the next download and then quietly accumulate every misclassified product.

Three more functions build the *publishing* names from the same tokens: `docs_tree_name(…, suffix, localized_prefix, primary_locale)` → `en-us-tib-messaging-userdocs`, or `loc-tib-messaging-userdocs` for any non-primary locale; `resources_tree_name(…)` → `en-us-tib-messaging-userdocs-resources`, which **raises** for a non-primary locale rather than naming a repository that will never exist; and `is_primary_locale(locale, primary)`, the single predicate both localized rules read so they cannot disagree. The empty-component guard covers the suffixes too — `en-us-tib--userdocs` is the same bug with a longer name.

The tokens arrive as arguments and are never read from disk here. `slug.py` owns the **shape** of a name and `config/publishing.yaml` owns its **words**, the same split that already keeps `taxonomy.yaml` and `slug.py` from drifting.

### 1.5 Path derivation — **Built**

All working paths are computed from `(bu, family, slug, version)` and are never passed between stages:

```
families/<locale>-<bu>-<family>/downloads/<slug>-<version>.zip
families/<locale>-<bu>-<family>/extracted/<slug>/<version>/
families/<locale>-<bu>-<family>/archive/<slug>-<version>.zip
```

The product segment is the **slug** and not `product_code`, because a path has to be unique and the code is not: nine of its ten collisions are within one family, so two products would share a `downloads/` filename and an `extracted/` directory (§1.1).

Derivation rather than passing is what lets a resumed run, a manually supplied ZIP, and a fresh download all land on the same location with no coordination (`architecture.md` §3.8, §4.1). The resolved path is *recorded* in `state.db` afterwards for audit and for resume, but it is never the authority — the layout function is.

---

## 2. Stage 1: Discovery

### 2.1 Request policy — **Built**

Every endpoint, URL template and politeness setting is read from `config/docsite.yaml`, so a moved endpoint is a config edit rather than a release.

One request proceeds as follows:

1. **Throttle.** If a rate limit is configured, sleep until at least `1 / rate` seconds have passed since the previous request *started*. This is a hard floor between requests, not a token bucket — a burst of 250 product lookups is precisely the traffic shape this crawler generates, and a bucket would pass the whole burst through untouched.
2. **GET** with the configured timeout. Transport-level failures raise a `DocsiteError` naming the URL.
3. **Retry** is handled beneath this, by the HTTP adapter: up to *N* attempts with exponential backoff, but only on 429, 500, 502, 503 and 504, and only for GET. A 404 is **not** retried — an absent archive index is a normal answer for a product that has no history, not a transient fault.
4. **Reject non-200** with the status code in the message.
5. **Decode JSON.** If decoding fails, inspect the first 2 KB of the body: if it looks like HTML and contains a sign-in marker, report *"this product is not public"* rather than *"invalid JSON"*. The docsite serves its SSO interstitial with HTTP 200, and the distinction is the difference between a crawler bug and an access boundary.

**The floor is on request *starts*, and it is shared** (`utils/http.py:Throttle`, extracted from the crawler in Phase 4a so the crawler and the downloader cannot disagree about what politeness means). Two consequences. A failed request still counts against the limit, so a run of failures cannot spin at full speed against a site that is already struggling. And a long transfer does not extend the gap after it — which is what lets Stage 3's worker pool share one floor (§5.1) without the pool collapsing back into a single serialized stream, since a 900 MB download would otherwise hold the gate for its whole duration.

The session itself — retry adapter, `User-Agent`, `Accept` — is built by `utils/http.py:build_session` for the same reason. Stage 3 passes a different `Accept` (a ZIP is not JSON) and nothing else differs.

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

**Product code.** The docsite calls `tibco-enterprise-message-service`'s ZIP folder `ems`, which is not derivable from the slug. It is read from a folder path instead:

1. For the detail record first, then every other record in turn, read the folder path and split it on the first `/`.
2. If **both** halves are non-empty — the path is version-shaped, `<code>/<version>` — slugify the first half and return it.
3. If no record yields one, fall back to the slug with a known vendor prefix (`tibco-`, `ibi-`, `spotfire-`) stripped.

The detail record is tried first because archived siblings carry stale paths (`enterprise_message_service`, `ems-zlinux`). The two-segment test is the whole guard: a one-segment path is exactly the stale form.

This derivation was **unchanged** by the 2026-09-10 re-key onto the slug (§1.1), deliberately: it always answered *what does the docsite call this product's folder?*, which is a real question with a correct answer, and it is still the answer every ZIP URL is built from. What was wrong was treating that answer as a unique product key. Making the derivation guess harder would not have helped — `tibco-clarity` and `tibco-clarity-enterprise-edition` genuinely publish under one folder.

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

1. Read `products.csv`. Skip rows with no slug. Coerce each enum column tolerantly — an unrecognized token falls back to that column's default rather than raising, since a spreadsheet will eventually contain one.
2. Read `versions.csv`. Skip rows missing either the slug or the version.
3. For each version row, look up its product by slug. **A version whose product is absent raises** and names both keys. This is a broken join, not a product to invent: silently creating a shell product would make a mistyped slug look like a successful import.

A **repeated slug** does not raise: the later row wins in memory and the slug is recorded, so `validate()` can report it while the file on disk still holds both rows. Raising would leave the sheet unopenable by the tool that is supposed to explain what is wrong with it; saving without reporting would write the collapsed catalog back over the original. Only a hand-edit can produce one — discovery's keys are unique by construction.
4. Default `convert_eligible` to *not archived* when the cell is blank (§1.2).
5. Ignore the `_bu` and `_family` columns entirely on read. They are denormalized conveniences for spreadsheet filtering and are regenerated on every write.

### 3.2 The three-way field decision — **Built**

The merge takes three inputs per field: **base** (what discovery wrote last time, from `state.db`), **theirs** (what discovery returns now), and **mine** (what the CSV currently says). It reduces to a single predicate:

> **Take the fetched value only if the CSV value still equals the recorded snapshot.** Otherwise a human moved it, and the human wins.

With **no snapshot** — the first fetch after the state DB was adopted, or after it was discarded — the fallback is to **keep the CSV value unless it is empty**. Inventing a base would silently overwrite edits made before the snapshot existed; filling genuinely blank cells is safe and useful.

Comparison is textual on both sides: the snapshot stores everything as text, so `None` becomes empty string and booleans become `true`/`false` before comparing. The decision is **per field, never per row** — editing `display_name` must not also freeze the `product_code` beside it.

Discovery owns exactly six fields, and merges only those: `display_name`, `product_code`, `is_archived`, `convert_eligible`, `release_date`, `zip_url`.

`slug` is **not** among them, and not for either of the reasons the table below gives: it is the key. A fetch returning a different slug is describing a different product, not proposing an edit to this one.

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

### 3.3.1 Scope, by rule then provenance — **Built**

`config/scope.yaml` is loaded once per run into a `{slug: reason}` map (`architecture.md` §3.10). For each product the merge touches, resolve `in_scope` the way `family` resolves, ranked `manual` (0) > `scope_rule` (1) > `default` (2):

1. If `scope_source` is already `manual`, preserve both fields — unconditionally.
2. Otherwise, if the product's `slug` is a key in the map, write `in_scope=false, scope_source=scope_rule`.
3. Otherwise write `in_scope=true, scope_source=default`.

Four details carry the weight:

- **The lookup is a dict hit on the exact slug.** Not `in`, not `startswith`, not a regex over the display name — `architecture.md` §3.10 tabulates what each of those wrongly excludes.
- **Step 3 actively resets.** Removing a slug from the YAML must bring the product back into scope on the next fetch; leaving `in_scope=false` behind would make the rule file removable in name only. This is safe precisely because `manual` short-circuits at step 1, so it can only ever reset a value the rule file itself set.
- **Rules that matched nothing are collected**, not discarded: every YAML slug absent from the catalog is reported with the merge statistics and by `warnings()`. The check runs over the **whole catalog**, not the products one fetch touched — a `--product ems` fetch would otherwise call all sixty other rules dead — and is only conclusive after `catalog fetch --all`, which is what both callers say when they print it. A rule silently matching nothing is how a renamed product drifts back into scope.
- **`in_scope` is the one boolean column read with `parse_optional_bool`.** §1.2's permissive read maps a blank cell to `false`, which is the safe default for every other flag and the dangerous one here: a hand-added row with an empty cell would vanish from every stage of the pipeline. Only an explicit `false` excludes.

New products take the same three steps, so a product first discovered *after* the rule is written is excluded on arrival rather than converted once and excluded later.

### 3.3.2 Release status, by report then provenance — **Built**

`config/eos.yaml` and the CSV it names are loaded once per run (`architecture.md` §3.11). Resolution runs immediately after §3.3.1, on every product the merge touches, and mirrors it exactly — ranked `manual` (0) > `eos_report` (1) > `unknown` (2), per **version**:

1. If `release_status_source` is already `manual`, preserve all three fields — unconditionally.
2. Otherwise, if the report carries a row for this exact `(slug, version)`, write that status and its retirement date with `release_status_source=eos_report`.
3. Otherwise write `release_status=unknown`, `retirement_date=None`, `release_status_source=unknown`.

Loading the report is where the care goes:

- **Read `utf-8-sig`.** The file ships a BOM, and its header ends in a trailing comma that `DictReader` renders as a `None` key. Both are support's format, not damage.
- **Dates parse with one explicit `%m-%d-%Y`, not through `normalize_date`.** §1.2's permissive list tries `%d-%m-%Y` and would read `03-04-2021` as 3 April rather than 4 March. The report is unambiguously month-first: field one never exceeds 12 across 5,948 rows, field two reaches 31 in 5,134. A value that matches nothing is kept **verbatim** rather than blanked, so a format change from support is visible in the sheet.
- **A name resolves through an alias first, then `slugify`.** The alias is what lets a reviewed decision correct a name that happens to slugify onto the wrong product.
- **Two names resolving to one slug and disagreeing about a version raises.** Repeated rows do not — the report has 2 exact duplicates and **0 conflicting statuses** across 5,948 rows, so last-wins is safe within a name. Across names it is not: a conflict means an alias is wrong, and picking one silently is how that stays invisible.
- **A status the enum has no value for is collected, not guessed at.** A new spelling from support must not read as "not retired" by default.

Three details then carry the same weight they do for scope:

- **Step 3 actively resets.** Dropping a row from the report, or removing a wrong alias, restores the version — safe only because `manual` short-circuits at step 1. Without it a retirement would be permanent even after being retracted.
- **Aliases that the active report never mentions are collected**, exactly as unmatched scope rules are, and reported as one aggregated line. That is the rename detector: the day support renames a product, its alias silently stops retiring anything.
- **Resolution is re-run on every fetch**, for new and existing versions alike, because a fetch defaults a newly discovered version to `convert_eligible=true`. `catalog eos` runs steps 1–3 over the whole catalog on their own, so a new report costs a CSV swap rather than a crawl.

### 3.4 Deletion detection — **Built**

For each product in the fetch, compute the version keys the catalog holds that the fetch of *that same product* did not return.

- With `--allow-deletes`: remove each from the catalog and purge every trace of it from `state.db`.
- Without: collect them, and after processing all products, **raise** with the full list and a note that this usually means a version key was mangled (Excel reading `1.10` as `1.1`).

Two properties matter. The check is **scoped to the products actually fetched**, so `catalog fetch --product ems` cannot read every other product's absence as a removal. And the raise happens **before** snapshots are recorded and before anything is written, so a blocked fetch leaves both CSVs and the state DB exactly as they were — the fetch is all-or-nothing.

### 3.5 Whole-merge sequence — **Built**

1. Load the catalog.
2. For each discovered product: add it wholesale if unknown; otherwise merge product fields (§3.2, §3.3). Resolve scope for every product either way (§3.3.1), then merge versions — new versions added, existing ones merged field by field — then resolve release status over every version (§3.3.2).
3. Collect deletions per product (§3.4).
4. If deletions were blocked, raise. Nothing has been written.
5. If this is a dry run, return the statistics without writing.
6. Record the new snapshots — this fetch becomes the next merge's base.
7. Save both CSVs.

The reported statistics count products and versions added and updated, fields preserved, and deletions blocked. Read `versions_updated` as *versions the fetch revisited*, not *versions that changed*; `fields_preserved` is the number that says how much of the user's work the merge protected.

### 3.6 Canonical write — **Built**

1. Sort products by `(bu, family, slug)`.
2. Sort each product's versions by natural version key (§1.3), **descending**, so the newest release is the first row under its product.
3. Write the fixed column list in fixed order, regenerating `_bu` and `_family` from the product row.
4. Normalize every value on the way out: booleans lowercased, dates to ISO, `None` to empty string.
5. Write UTF-8 with BOM and CRLF line endings.

The sort is what makes a no-op fetch produce a zero-line diff, and the zero-line diff is what makes the catalog reviewable in git rather than merely stored there.

---

## 4. Selection: what a run acts on

**Built.** Four independent questions at two grains, composed at every stage command (`architecture.md` §3.7):

1. Walk products in catalog sort order, filtering by BU, family and product code where given.
2. If eligibility was requested, **skip the whole product** when `in_scope` is false — no version of it is ever selected (§3.3.1).
3. Within each surviving product, walk versions in natural descending order, filtering by version where given.
4. If a batch label was given, keep only versions whose (trimmed, lowercased) batch matches.
5. If eligibility was requested, drop versions whose `release_status` is `retired` (§3.3.2). Only `retired` — `retirement-announced` names a version that is still supported today, and `unknown` means the report is silent, which is not a verdict.
6. If eligibility was requested, keep only versions with `convert_eligible` true.
7. Return the surviving `(product, version)` pairs.

Steps 2, 4, 5 and 6 **compose rather than override**, outside in: scope, then retirement, then eligibility, with the batch a filter within all three. A version tagged into a batch but left ineligible is skipped; so is a retired one; so is any version of an out-of-scope product, even if it is both eligible and tagged. All three combinations are almost always a mistake, so each is reported as a warning naming the exact command that fixes it (§8.2) rather than being silently honoured or fatally rejected. The warnings name *which* gate closed, because a rule-file exclusion, a report verdict and a hand-edit are undone three different ways.

Steps 2, 5 and 6 are gated on `eligible_only` rather than applied always, so that inventory and reporting paths — which pass `eligible_only=False` — still see excluded rows. An out-of-scope or retired version is absent from the *work*, never from the *books* (`architecture.md` §3.10, §3.11).

Batch labels are trimmed and lowercased on write, so `POC-1`, `poc-1 ` and `poc-1` are one batch and not three. The batch census counts versions per label and **omits unscheduled rows entirely** — folding 3,900 untagged rows into the same table would bury the answer to the question being asked.

---

## 5. Stage 3: Acquisition

**Built** (Phase 4a, 2026-09-10), for acquisition. §5.1 and §5.2 are implemented in `downloader/fetcher.py`; §6's extraction landed in Phase 4b-1 and its inventory walk in Phase 4b-2.

### 5.1 Download one version

1. Resolve the canonical download path from `(bu, family, slug, version)`. Never accept a path from the caller.
2. **Skip immediately if `zip_source` is `manual`.** The package is expected to be at that path already, placed by hand; fetching would overwrite it with whatever the stale URL now serves.
3. If the file exists and `state.db` holds a checksum for it that still matches, mark it downloaded and return. This is what makes a re-run over a completed batch cheap.
4. Otherwise fetch `zip_url` to a temporary file beside the target, resuming from the partial length if one is present and the server's validator (etag or last-modified) matches the recorded one. A changed validator discards the partial and restarts — resuming against a different file produces a corrupt archive that passes a length check.
5. Compute sha256 while writing, rather than in a second pass over the file.
6. Verify the result is a readable ZIP before moving it into place.
7. Move into place atomically, and record path, size, etag, checksum and status `DOWNLOADED` in `state.db`.
8. On failure, record status `ERROR` with the message and leave the partial file for the next resume.

**Concurrency: a thread pool over versions, default width `docsite.yaml`'s `crawl.max_concurrent_requests` (4)** — resolved 2026-09-10 (user decision), previously open. Streaming a ZIP to disk is I/O-bound, so threads cost nothing here and the resume logic above stays ordinary synchronous code; async would have bought nothing and made steps 4–7 harder to read. The default is the value the config already carries, so politeness stays a config edit rather than a source change, and `--workers` overrides it for one run. The rate-limit floor of §2.1 is **shared across workers**, not applied per worker, and it paces request *starts* only — throttling transfers would serialize the pool back into one stream.

Two consequences of the pool that are not obvious from the steps: `state.db`'s connection is shared across worker threads (`check_same_thread=False`, with a lock around the write path), and every failure in step 8 is a **returned outcome rather than a raised exception**, because one unreachable product must not stop a 200-version batch. A run reports five counts: downloaded, already-current, skipped-manual, no-`zip_url`, failed — with the last two named individually, since "3 failed" out of 200 is not actionable.

### 5.2 Ingesting a hand-supplied package

`--from-file` requires both a product and a version selector.

1. Reject unless the *product* exists in the catalog. A typo'd product code is unrecoverable and would seed a junk row.
2. If the product exists but the version does not, **add the version row with a warning**. The user has a real package in hand, which is stronger evidence the version exists than discovery's silence is that it does not.
3. Reject anything that is not a readable ZIP, before copying. The common real failure is not a corrupt archive but an HTML login page saved under a `.zip` name; caught here it is one line, caught at extraction it is a baffling failure days later.
4. **Copy — never move.** The user's own copy is not the tool's to consume.
5. Set `zip_source=manual`, and record the computed sha256, the size, status `DOWNLOADED`, and the originating path for audit — in `state.db`'s `version_metadata` under `zip_origin_path`, which is free-form and so costs no `SCHEMA_VERSION` bump for a field only a few rows carry. There is no upstream checksum to compare against, so the computed one is authoritative for later "is this still the same file" checks.

The archive variant is identical but targets the archive path, and its `--extract` unpacks within `archive/` — never into the pipeline's `extracted/` tree. **It does not set `zip_source=manual`,** which is the one place the two diverge: `zip_source` states where the *pipeline's* package for a version comes from, and a reference ZIP pulled outside the working set is not that. Pinning it there would make `download` skip a version whose real package was never supplied.

Extraction under `--extract` goes through the same path-traversal refusal as §6.1 step 2: every member is checked *before* any is written, so a malicious archive cannot leave half a tree on disk before being refused.

---

## 6. Stage 4: Extraction and inventory

**Built.** §6.1 steps 1–3 landed in Phase 4b-1 (2026-09-11) in `extractor/unpacker.py`, along with the catalog half of §6.3 (the columns, the round-trip and the write-back) and §6.1 step 2's path-traversal refusal — which landed earlier still, in Phase 4a, because `archive download --extract` needs it and there must not be two answers to "is this member safe". **Steps 4 and 5 — the one walk, §6.2, §6.3's predicate and §6.4 steps 1–2 — landed in Phase 4b-2 (2026-09-11)** in `apiref.py`, `engines/csh.py` and `extractor/inventory.py`. **§6.4's steps 3–7 — the converter's half — landed in Phase 5a (2026-09-11)** in `transforms/assets.py`, driven by `converter/driver.py`.

### 6.1 Extract — **Built** (steps 1–3 Phase 4b-1, steps 4–5 Phase 4b-2)

1. Run over **the same selection as the download**, so an archived version is neither fetched nor unpacked.
2. Refuse any archive member whose resolved path escapes the target directory, and any absolute member path. A documentation ZIP has no legitimate reason to contain either.
3. Unpack to the canonical extract path, then record the resolved path and status `EXTRACTED`.
4. Walk the extracted tree **once**, partitioning every file into API-reference or not, inventorying assets **by category and by destination** rather than by an extension allow-list, and locating the CSH sources (§6.2, §6.3, §6.4). One walk, so all three describe one moment; the per-file detail goes to `state.db`.
5. Write the five inventory columns back to `versions.csv` (§6.3) — but only from a walk that finished. A directory the walk could not read leaves the columns blank, on the same rule as a failed extract.

**Step 3 unpacks into `<extract_path>.part/` and swaps, never over a live directory.** Unpacking in place leaves the *previous* package's files behind, so a guide deleted upstream survives on disk forever — and converts, and nothing in the report says why. The swap is build, remove, rename, and **is not atomic on Windows**: an interrupted run can leave a `.part` directory, which the next run removes before it starts. That is the honest guarantee, and it is stated rather than implied.

**The rename retries before it fails** (`utils/swap.py`, Phase 5a). On Windows it raises `PermissionError: [WinError 5]` whenever any handle to the tree is still open, and an unrequested handle is the normal case there — the search indexer and the on-access scanner open files moments after they are written. Measured while building Stage 5: roughly **one run in seven** of a 21-test suite failed at this call on a tree of *nine* files. Five attempts, 0.1 s apart and growing, is a second of patience; a real permission failure is still reported, and the retry is shared with §6.4's converter swap because it is the same syscall losing the same race.

**An unchanged package is a no-op.** The ZIP's sha256 goes to `version_metadata` under `extract_zip_checksum`, and a matching one with a directory already in place skips the whole step; `--force` overrides. Keyed on the *package* rather than on the tree, because a tree is thousands of files and hashing it would cost more than re-extracting it. Same mechanism as §5.2's `zip_origin_path`, and for the same reason: detail for the rows that have it, not a field every version carries, so it costs no `SCHEMA_VERSION` bump.

**Extraction is serial, and that is a decision rather than a default.** §5.1's pool exists because HTTP transfers overlap; two 900 MB unzips onto one disk contend rather than overlap, and the second finishes no sooner for having been started early. It also keeps `catalog.save()` — which §7's write-back calls per version — off a thread pool.

**Five outcomes, and `refused` is not `failed`.** `extracted`, `current`, `no-package`, `refused`, `failed`. An archive that escapes its target directory is a statement about the package, not about this run: a retry will not fix it and somebody has to look at the ZIP, so it is counted apart from an I/O failure rather than summed into one number nobody can act on.

### 6.2 CSH source inventory — **Built** (Phase 4b-2)

`engines/csh.py:csh_format_of` locates, `read_csh_source` parses; `extractor/inventory.py` runs both inside the §6.1 walk.

Locating help maps is separated from parsing them, because the *absence* of a help map needs to be visible before conversion starts rather than discovered after (`architecture.md` §5.4, planning Phase 4).

For each doc-set inside the extracted tree, look for:

| Format token | Where | Parsed? |
| :--- | :--- | :--- |
| `flare_alias` | `<book>/Data/Alias.xml` | **Yes** |
| `dita_head_js` | `<doc-set>/static/head.js`, the `suitehelp.contexts` object | **Yes** |
| `webworks_topics` | `<book>/wwhdata/common/topics.js` | **Yes** |

**A source is located by shape — the file name *and* its parent directory — not by sitting under an output root.** 153 Flare alias files in the corpus sit in roots nested below another root, so keying off the root list would lose them; the parent test is what keeps a stray `head.js` in some product's script folder from being read as a context map.

**All three are read** (§9.2). Two nearby files are deliberately *not* consulted: `<doc-set>/ctx/` holds redirect stubs generated from the WebWorks map rather than the map itself, and `<book>/wwhdata/xml/files.xml` is a lossy XML twin of `topics.js` — where the two disagree it is the XML that is missing entries, and one observed book ships no `files.xml` at all.

A source that is located but fails to parse still sets `_has_csh` — a file *was* found — with the failure counted and named in the extract report. "This version has help we could not read" and "this version has no help" are different facts, and only one of them is acceptable to discover after publishing.

Record path, format, raw entry count and parse status per `(product, version, doc_set)`. **Empty, zero-byte and unparseable sources are counted and skipped, never raised** — an empty map is the *normal* case in every format, and overwhelmingly so in two of them: 476 of 863 Flare alias files (55%), 492 of 647 WebWorks `topics.js` (76%), 38 of 418 DITA `head.js` (9%). Raising would make a routine condition look like a defect. `docushift extract` prints the tally (`CSH: 3 source(s), 561 identifier(s).`) so that a version with no help map is a fact known at extraction time.

### 6.3 Inventory write-back to `versions.csv`

**Built.** The columns, the blank-preserving round-trip, `CatalogManager.record_extract_inventory` / `clear_extract_inventory`, the merge exclusion and the desync warning landed in Phase 4b-1. The API-reference predicate below and its triage report landed in Phase 4b-2 as `apiref.py` — a top-level module rather than one under `extractor/`, because Stage 5's skip-list and Stage 7's doc-class router are its other two callers and neither should import from the extractor to get it.

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
  html/api-docs/c/          101 files, no known generator marker
```

Nested candidates are separate lines, because `api-docs/` and the `c/` inside it are two questions a human may answer differently. A sibling `dotnet/` would produce **no** line: the name test is a fixed vocabulary, not a guess at what an API directory might be called, and a name that is not in it is not a candidate.

It is a report line, not a classification: the files stay in `_doc_files` until a human says otherwise. The flag exists so that a generator we have no marker for surfaces as a question at extract time rather than as broken Markdown at conversion time, and so the marker list grows from evidence. Products whose *name* contains `api` are the reason this cannot be silently auto-promoted.

**The five values,** computed in a single walk so they always describe one moment:

| Value | Rule |
| :--- | :--- |
| `_api_files` | Files whose path satisfies the predicate |
| `_doc_files` | Every other file. Not a topic count — images, CSS and skin assets are included, which is what makes it a footprint figure rather than a workload one |
| `_has_api_ref` | `_api_files > 0` |
| `_csh_names` | Distinct identifiers across all of the version's CSH sources, counted **byte-exactly and case-sensitively** — `GatewayInstances` and `gatewayInstances` are two (§9.1) — and deduplicated version-wide, matching how the resolver merges them (§9.3) |
| `_has_csh` | At least one CSH source file was located — Flare `Alias.xml`, DITA `head.js` or WebWorks `topics.js`, all three the same — regardless of whether it parsed to anything. It records that a file was *found*, so `true` with `_csh_names=0` is a routine state, not a contradiction: 55% of the Flare corpus and 76% of the WebWorks corpus. An unreadable source sets it too, and is named in the report (§6.2) |

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

### 6.4 Assets: the inventory, and the copy set — **Built** (steps 1–2 Phase 4b-2, steps 3–7 Phase 5a)

One algorithm that spans two stages, kept in one place because splitting it is what breaks it (`architecture.md` §5.5, §5.5.9). Stage 4 runs steps 1–2 (`extractor/inventory.py`); the converter runs steps 3–7 per topic; Stage 7's part is §10.7.

**Steps 3–7 are `transforms/assets.py:AssetCopier`, one per unit, and the driver owns it.** `converter/driver.py` constructs it, hands it to the engine on `ConversionContext.assets`, and calls `copy()` after the unit's topics are written. The engine therefore resolves *while* it emits — which is invariant 13 — without deciding where anything lands, which would put the destination rule in four engines instead of one.

**Step 1 — inventory, in the §6.1 walk.** The same single walk that partitions API-reference files also classifies **every** file — topics included, so the rows sum to the file count and the total is checkable — by **category** and by **destination**. Record counts and bytes per `(version, output_root, category, destination)` in `state.db`. Nothing is filtered by an extension allow-list: the corpus holds 100 extensions and the nine the old list named cover neither the images that matter nor the documents that do (`architecture.md` §5.5.1).

**Category is decided by extension, except `skin`, which is decided by location.** A `.gif` in `Skins/Default/` is chrome and a `.gif` beside a topic is an image, and no extension can tell them apart — so the skin test runs *first*, against the file's path relative to its output root, using step 4's per-engine prefix list and step 4's whole-segment rule. Everything else falls to extension: `topic`, `image`, `media`, `document`, `archive`, `source-format`, `other`.

**Destination is a precedence, not a set.** API-reference root, then engine output root, then a top-level `pdf/` or `doc/` (§10.4's document router), then unclaimed. It has to be ordered because an API tree commonly sits *inside* an output root, and a file counted under both would be counted twice.

**Step 2 — report the residue.** Files that no destination claims are counted and printed by `docushift extract`, grouped by their top path segment:

```
Assets: 30,810 images (1.25 GB), 208 source-format, 3 archives in 1 output root
Unclaimed: 5,426 files in components-api/ — no destination, no API-reference marker
```

This is the same mechanism as §6.3's API-reference flag and it exists for the same reason: 62,525 files across 243 rooted versions currently fall through, almost all of them generated reference trees whose generator has no marker yet (`architecture.md` §5.5.2). Silence here is how a whole tree goes missing without anyone noticing.

**Step 3 — resolve, while emitting** (`transforms/assets.py:AssetCopier.resolve`)**.** For each non-HTML reference found by the engine's content extractor, in the same pass that writes the topic:

1. **Classify the raw reference.** `data:` and any absolute URL (`http`, `https`, `ftp`, `mailto`) are emitted unchanged and never copied. A fragment-only reference is not an asset.
2. **Normalize before resolving**, in this order: strip the `#fragment` and `?query`; percent-**decode**; replace `\` with `/`. Skipping this reports 1,872 WebWorks references as missing that are not (`architecture.md` §5.5.6) — 1,224 percent-encoded, 648 backslash-separated.
3. **Resolve against the source topic's own directory**, then normalize `.` and `..`. The result is a path relative to the output root.
4. **Skin check first.** If the resolved path starts with one of the engine's skin prefixes — Flare `Skins/`, `Resources/Scripts/`, `Resources/Stylesheets/`, `Resources/MasterPages/`, `Resources/TemplateExtensions/`, `Data/`; DITA `static/`, `fonts/`; WebWorks `wwhdata/`, `wwhelp/`, `tpl/` — the reference is chrome. Drop the element, do not copy, do not count as missing. **Compare whole segments, never as a substring** (§6.3.1 Finding 2 for the same rule on API paths; the predecessor makes the substring mistake here too). This branch takes 48.7% of DITA references and 76.2% of WebWorks ones.
5. **Escape check.** A resolved path starting `..` leaves the output root. It is not copied and not emitted as a relative link; it is handed to Stage 7 with its resolved absolute source path, which routes it (§10.7). 279 in the Flare sample, 0 in DITA and WebWorks.

**Step 4 — the two outputs, or neither.** If the resolved path names a file that exists:

- Copy that file to **the same relative path** under the output root's subtree in the converted output. Never flatten: flattening collides 5,328 times inside a single Flare root (`architecture.md` §5.5.5). Never rename: the filename is kept byte-for-byte.
- Emit the Markdown link as the path **from the emitted topic to the emitted asset**, percent-encoded — space → `%20`, `(` → `%28`, `)` → `%29`, and a pre-existing literal `%` → `%25` *first*. 104 filenames in the corpus contain a `%`, and encoding them in the wrong order produces a different filename.

If it does not exist, emit **neither**: no link, no copy. The alt text or link label is emitted as plain text so the prose still reads, and the reference is counted.

**Step 5 — count, per output root.** Resolved, skin, escaped, dangling, and — after the topic loop — orphan (on disk, not in the copy set). Dangling references are grouped by **top path segment** in the report, not only totalled. A total hides the corpus's actual failure shape: 2,706 of Flare's 2,905 dangling references are one generated tree that is broken in its own source, and the remaining rate is 0.37% (`architecture.md` §5.5.6).

**Step 6 — case is checked, not corrected.** Where a reference resolves but its spelling differs from the file's, count it and name it. The extracted cache is on Windows, so these work locally and 404 after publishing. There are 14 in the whole corpus, so this is a report line and not a resolution strategy.

**Step 7 — orphans are reported, never copied.** Count and size everything on disk inside the output root that the copy set does not contain. This is 54.6% of Flare's images by count and 673 MB by size, and copying it would put unreachable files in the docs repo (`architecture.md` §5.5.7).

**Open:** whether a sharp version-over-version rise in the orphan count should warn rather than merely report. It is the signal that a guide silently failed to convert, but there is no baseline until Phase 5 has run twice.

## 7. Engine detection

**Built** (Phase 4b-1, 2026-09-11) in `engines/detector.py` and `engines/roots.py`, called by `extractor/unpacker.py` (`architecture.md` §3.4). Rules measured against the whole `html-to-md` cache on 2026-09-08 — 1,822 versions, of which 539 (29.6%) carry no HTML at all and are not this algorithm's problem.

**This section was filed under Stage 5 until 2026-09-11, and the number stayed while the phase moved.** Detection runs at *extract* time, not at conversion time — §6.2's per-doc-set CSH inventory and §6.4's asset destinations are both engine-specific and both walk the tree the moment it is unpacked, so an engine that arrived at Stage 5 would arrive after its first two consumers. `user-guide.md` has described `extract` as the command that detects engines since Phase 1; this is the design catching up to it. Every measured figure below is unchanged.

**Passes 2 and 3 read a bounded sample:** the first 8 KB of at most 200 HTML files per tree, breadth-first. `<head>`, the generator comment and the `MadCap:`/`DC.*` markers all live in the first few hundred bytes, and breadth-first reaches one file from each guide folder before it reaches the second file of any. The bound is recorded on the result, so "we looked at everything and found nothing" stays a different report line from "we stopped looking".

### 7.1 The rules

Run per version, over the extracted tree, in three passes.

**Pass 1 — layout markers.** Cheapest and least ambiguous: a directory listing decides it.

| Engine | Markers | Versions |
| --- | --- | --- |
| Flare | `*.mcwebhelp`, `*.mclog`, `MicroContent/`, `_globalpages/`, `csh.js` | 595 |
| WebWorks | `wwhelp/`, `wwhdata/` | 176 (195 with the 19 below) |
| DITA (SDL) | `GUID-*.html` filenames, or `static/head.js` + `static/body.js` | 371 |
| R help | `snext.css` or `snextchm.css` | 11 |

19 further versions match Flare *and* WebWorks markers — a Flare output with a WebWorks tree left beside it. Flare wins; the per-folder map (below) keeps the ambiguity visible.

**The WebWorks row is carried by `wwhdata/` alone, and that marker is exact** (`architecture.md` §5.3.2, 2026-09-09). Ground truth is "the version holds a directory containing `wwhdata/`" — **195 versions**, which is the 176 above plus all 19 of the mixed bundles. `wwhdata/` matches 195 with **zero false positives and zero false negatives**; `wwhelp/` matches 178 at 91.3% recall, missing the 17 versions whose books are stripped to `wwhdata/files.htm`. The union is also 195/195, so the pair stays as written — but the recall belongs to `wwhdata/`, and the marker is lowercase in all 1,822 versions with no variants. On the 19 mixed versions **both** converters have work to do; that is the case the per-folder map exists for, and the first one in the corpus where it is not hypothetical.

**`Skins/` and `Data/` were dropped from the Flare row on 2026-09-08** (`architecture.md` §5.1.2). Over all 1,822 cached versions the seven-marker list matched 689 against 595 that actually hold a `Data/HelpSystem.xml` runtime: `Skins/` is 91.4% precise and `Data/` 88.0%, because other publishers use directories by those names too. **All 94 false positives come from those two markers and no other** — 43 matched both, 38 `Data/` alone, 13 `Skins/` alone; 17 are WebWorks, 3 DITA, and 74 carry no engine marker at all (mostly 2010–2013 adapter packages). Removing them costs no recall: **`*.mcwebhelp` alone finds all 595 and `csh.js` alone finds all 595.** Worth a regression test with a WebWorks fixture that ships a `Skins/` directory: under the old list it detects as Flare.

**And the casing matters, in the opposite direction to §7.2's DITA rule.** The figures above are case-insensitive matching. Matching exact casing gives 631 matches and 36 false positives and makes `Skins/` 100% precise — every non-Flare match was a lowercase `skins`. `Data/` misfires either way: 36 versions ship a correctly-cased `Data` with no Flare runtime. So case sensitivity is decided per signal here — mandatory-insensitive for `DC.*` (§7.2), and not worth specifying for a marker that is being dropped anyway.

**Flare root detection is a separate step from engine detection.** The engine answers "which converter", per version; the converter then locates its units of work by walking for `Data/HelpSystem.xml`, since **51 of 595 versions ship more than one output root and 153 roots nest inside another** (`architecture.md` §5.1.1, §5.1.3). The walk descends into nested roots rather than stopping at the first match, and the innermost root owns a file.

**Pass 2 — content signatures.** Corroboration for pass 1, and the *only* means of identifying DocBook, whose flat HTML output has no distinctive layout. Signatures: the `MadCap` namespace and `MadCap:*` attributes; the WebWorks generator meta tag; the DITA-OT generator comment; `DC.Type` / `DC.Identifier` / `DC.Title` meta tags (SDL DITA); `class="RdName"` / `class="RdTitle"` (R help); the `DocBook XSL Stylesheets` generator comment.

**The WebWorks generator meta tag is corroboration only — it has 1.5% recall.** Measured 2026-09-09 it names WebWorks or ePublisher in **3 of the 195** WebWorks versions. It is precise, it costs nothing, and it must never be read as evidence of absence: a null result from it says nothing at all. Pass 1's `wwhdata/` is the WebWorks rule.

**Pass 3 — the generator meta tag.** A last look for `<meta name="generator">`, which names the remaining long tail outright: Adobe RoboHelp 11, Microsoft FrontPage 6.0, Help & Manual, MkDocs / mkdocs-material, Docusaurus, Apache Maven Doxia. 19 versions, ~7,200 files. None of these has a Stage 5 converter; they are recorded anyway (§7.3). A string we cannot map to a known name becomes `other`, with the raw value kept in `state.db`.

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

**The two clauses of the DITA rule match two different publishers**, which the 2026-09-08 converter survey (`architecture.md` §5.2.1) separated: `GUID-*.html` matches 316 SDL SuiteHelp versions, and `DC.*` meta picks up ~55 more that SuiteHelp never touches — file-named topics under `topics/`, all in the Spotfire family bar one EBX add-on. That is why the `DC.*` hit count (369) exceeds the GUID one (316) rather than merely corroborating it, and it is the reason both clauses stay: dropping `DC.*` as redundant would lose a sixth of the DITA corpus.

**`DC.*` is matched case-insensitively.** SuiteHelp writes `DC.Type`, the file-named flavour writes `DC.type`. A case-sensitive match silently drops all 66 of the latter's versions — it did exactly that once during the survey, and produced a confident, wrong "correction" of 371 down to 316 before the casing was spotted.

**The file-named flavour went out of scope on 2026-09-09, and that changes what these two clauses are for.** All nine products that publish it — `sf-pysrv`, `sf-rsrv`, `enterprise-runtime-for-R`, `ebx-addon`, `sf_ipad`, `sf_ipad_deploykit`, `sfire-android`, `sfire-cloud`, `sfire_dev` — are on `config/scope.yaml`'s exclusion list (`architecture.md` §3.10, §5.2.1), and an out-of-scope product is never extracted, so this algorithm never runs on one. The `DC.*` clause's live yield is therefore the SuiteHelp corroboration only, and its lowercase half yields nothing at all today. **Both stay exactly as written.** Neither costs anything, and both are what make a readmitted product detect as `dita` rather than as `auto` — which is the difference between one engine dispatch and a silent hole in a report. A signal kept for a population that is currently empty is cheap; re-deriving it after a scope change, from a null result that looks like a clean absence, is what §7.2 exists to warn about.

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

1. **A slug appearing on more than one `products.csv` row.** The slug is the key, so the load has already dropped one of them; blocking here is what stops a later `save()` from writing the collapsed catalog back over a file that still holds both rows (§3.1).
2. **Versions known to discovery but absent from the CSV.** Compared against the snapshot table; this is the Excel `1.10` → `1.1` coercion, caught by name.
3. **Engine `auto` with a resolved engine source** — an internally inconsistent row.
4. **Convert-eligible with no `zip_url`** — *except* on a `zip_source=manual` row, whose package arrives by hand and legitimately has no URL.

### 8.2 Catalog warnings — **Built**

`warnings()` returns things worth saying that must **not** block a write, kept structurally separate because the two have opposite consequences:

1. **A family not declared in `taxonomy.yaml`**, naming the workspace folder that will be created. Families are user-extensible by design (`architecture.md` §4.2); the warning is what stops a typo (`mesaging`) from silently becoming a third family folder holding one product. If the family name cannot even form a folder, that failure is reported in its place.
2. **In a batch but not eligible** — nothing downstream will ever pick this row up. The message includes the exact `catalog enable` command that fixes it.
3. **`zip_source=manual` but discovery now has a URL** — the pin still wins; the user may no longer need it.
4. **A batch tag on a version of an out-of-scope product** — the row looks scheduled and will never run. The message names the product and whether the exclusion came from `config/scope.yaml` or from a hand-set `in_scope=false`, because the two are undone in different places.
5. **A `config/scope.yaml` rule matching no product in the catalog** (§3.3.1) — usually an upstream rename, occasionally a typo. Reported after every fetch as well as by `catalog validate`, since the day it starts matching nothing is the day it stops working.
6. **An inventory boolean disagreeing with its count** — `_has_api_ref=false` beside a non-zero `_api_files`, or `_has_csh=false` beside a non-zero `_csh_names` (`architecture.md` §3.9). The tool writes both from one computation, so this shape only arises from a hand-edit. A warning rather than a problem: the values are advisory, the next `docushift extract` overwrites them, and blocking an import over a stale summary column would be out of proportion.

### 8.3 Triage progress — **Built**

Count products by family provenance and list the unclassified ones. This turns "classify 250 products" from an unbounded chore into a number that goes down, which is the only reason the provenance column exists.

### 8.4 Link, asset and CSH integrity — **Specified**

`docushift validate` treats CSH as link integrity, because that is what it is (§9.6).

**Links are classified before they are checked.** A relative link resolves against the filesystem and a missing target is an error. An absolute URL is external — which, after Stage 7, includes every rewritten API-reference link (`architecture.md` §6.4) — and is skipped by default, checked over HTTP only behind an explicit flag. Checking the two the same way would report the entire API surface of every product as broken.

**Asset links are checked, and finding one is a regression rather than a discovery.** §6.4 resolves the copy and the link together, so under invariant 13 a broken relative asset link cannot be produced; `validate` re-resolves them anyway, because an invariant nobody tests is an assumption. The linter decodes percent-escapes before resolving, so its comparison matches what a renderer does. It does **not** report unreferenced assets as errors — orphans are a Stage 5 report line (§6.4 step 7), and 54.6% of Flare's images are orphans by design of the authoring tool, not by defect.

**`nav.yml` and `meta.yml` are checked for existence and YAML well-formedness only** (§10). Their shapes are placeholders pending an AEM spec, so there is no field list to validate against; asserting one would pin a guess in the test suite and make the eventual real template read as a regression. `toc.yml`, `index.md` and `csh.yml` are validated on their content as specified above and in §9.6.

### 8.5 The findings register — **Built** (Phase 5a)

`reporting/findings.py`. Every deferred "report line" in this document has a **code**, and they are one table (`planning.md` §7.5) — twenty at 5a, **twenty-eight after Phase 5b added the eight `architecture.md` §5.1 had asked for in prose**. The module landed with Stage 5 rather than with `validate`, because the first stage that produces findings in bulk is conversion and a register invented alongside its second caller is a register shaped by its first.

Three rules, each of them a rule about where a decision is *not* made:

- **`code` is the contract; `message` is prose.** Tests assert on codes. An obligation that existed only as an English sentence in a design document becomes an enumerable thing that a run can be checked against.
- **Severity belongs to the code, not to the call site.** It is fixed once in `REGISTRY`. Two call sites reporting one condition at two severities would make the exit code depend on which of them fired. Recording an unregistered code raises — at the call site, which is the only place that can fix it.
- **Errors and warnings get a row each; notes are aggregated by `(code, slug, version)` with a count.** You act on an error individually and only need the magnitude of a note. A per-file note would write hundreds of thousands of rows for `ASSET_ORPHANED` alone, which is 54.6% of Flare's images *by design of the authoring tool*.

**Findings flush per version**, so a crash on version 200 of a batch does not discard the first 199, and the run row carries the batch tag and the exit code. Only `validate` gates, and only on `ERROR` (§8.4).

**All twenty rows are registered although Phase 5a can reach six.** A half-populated register cannot be audited. The reachability test names the unreached codes rather than failing, so the debt is a visible list that shrinks as Stages 6 and 7 land instead of a silence.

**And the reachability half earns its keep.** Phase 5b registered `ALERT_LABEL_UNMAPPED` and then could not reach it: every callout class the engine matched was one the vocabulary mapped. The two ways out were deleting the code and widening the detection, and the second is right — Flare's convention is `div.note<Kind>` for whatever kind the project stylesheet defines, so an unsampled `noteBestPractice` was going to arrive as unmarked prose with nothing said. An unreachable code is usually a rule that is narrower than the thing it was written about.

---

## 9. Context-Sensitive Help

**Built**, except §9.6's verification. The readers landed with Stage 4 (§9.2, Phase 4b-2); the schema, the resolver, the writer and the frontmatter landed in Phase 5a as `transforms/csh.py`. This is the most intricate algorithm in the tool, and the one grounded most directly in measurement — now re-measured over the whole cache: **863 `Alias.xml` files, 387 with content, 11,054 entries, 2,396 distinct names**, superseding the 2026-09-04 subset of 272 files / 7,220 entries. **Scope: all three HTML engines — Flare, DITA and WebWorks** (§9.2). The full evidence table and the reasoning are in `architecture.md` §5.4; what follows is the procedure.

### 9.1 The single identifier rule

Flare offers one key that is genuinely unique, and it is not the integer: the `Map`'s `Name`. `ResolvedId` is parsed — so that a malformed entry is still recognised as an entry — and then discarded. The identifier is typed as a **string**, not as an integer and not as a name-shaped token.

Three consequences follow, and all are correctness requirements rather than style:

- **Comparison is byte-exact.** `GatewayInstances` and `gatewayInstances` are two different live help targets in TIBCO BC 7.4/7.5. With no integer to disambiguate them, case is the only thing that does — and the full-cache re-measure finds **8 such case-only collisions**, so this is not a single anecdote.
- **The string typing is carried by Flare alone.** It is often attributed to WebWorks, but WebWorks needs none of it: its identifiers are dotted lowercase names with **zero digit-only and zero case-only collisions** in the corpus. Flare supplies the whole justification on its own — **834 of 11,054 names (7.5%) are digit-only** (`12`, `1000`, `1122`), and the 8 case-only collisions above are all Flare's.
- **Identifiers are always emitted double-quoted**, in map keys and in frontmatter alike. A YAML 1.1 loader turns an unquoted `1234` into an integer and `6.2` into a float, in a map documented as string-keyed. Measured over Flare the live hazard is *only* numeric coercion — zero names are `Yes`/`No`/`On`/`Off`/`null`-shaped, zero are sexagesimal, zero carry a leading zero — but the rule is applied to every identifier rather than narrowed to the digit ones, because a conditional quote is a branch that can be wrong and an unconditional one cannot.

### 9.2 Three readers, one per HTML engine — **Built** (Phase 4b-2)

The schema, the resolver and the writer are shared and engine-neutral; an engine contributes only a reader yielding `(identifier, link, anchor)`. **Every format the corpus ships is read.** The readers landed early, with Stage 4, because §6.2's inventory cannot report "help we could not read" without them; the schema, resolver and writer stay in Phase 5's `transforms/csh.py`.

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

### 9.3 Resolution — **Built** (Phase 5a)

`transforms/csh.py:resolve`. Run **after** the version's topics have been converted, so resolution tests against files that were actually produced.

1. **Collect** every CSH source under the version's extracted tree, grouped by doc-set.
2. **Parse** to `(identifier, link, anchor, doc_set)`. Empty, zero-byte and unparseable files are counted and skipped.
3. **Resolve within the doc-set first**: map the link's `.htm` path to the Markdown file the converter emitted for that HTML file.
4. **Fall back version-wide**: if the link does not resolve in its own doc-set, try the identical relative path in every sibling doc-set. One hit wins. This is a Flare remedy specifically — WebWorks links resolve inside their own book 100% of the time, so on a WebWorks version the step never fires.
5. **Merge by identifier.** The same target reached from several doc-sets collapses to one entry and is not a conflict. Different targets keep one: **the doc-set with the most resolved entries, ties breaking alphabetically** — deterministic, and it picks the main help output over a release-notes or getting-started sidecar every time. The flat schema (§9.4) has nowhere to put the losers, so they go to the findings as `CSH_AMBIGUOUS`, naming both the winner and what was dropped.
6. **Emit** `csh.yml`, then the frontmatter.

**One ordering rule, not two.** Step 4's fallback scan and step 5's winner are the same `order_doc_sets` — most resolved entries first, then name. They were written from two specifications that said it two different ways (§9.3 step 5 and the Phase 6 contract's "first ordered doc-set"), and a second implementation of an ordering is a second answer waiting to disagree.

**Resolution runs against the rows this run just produced**, passed in from the converter rather than read back out of `state.db`. The table is written after the swap, so a read-back would resolve a re-convert against the *previous* run's output map.

**Step 4 is the one that earns the per-version file.** Flare frequently copies one output's alias file wholesale into a sibling where none of its links exist: 1,609 of 7,220 links (22%) dangle inside their own doc-set, and 10 of the 11 affected files are a `relnotes` alias resolving at 0%. Per-doc-set resolution would report 205 broken identifiers for BW release notes; version-wide resolution resolves all 205 against the main output, where the topics actually live.

**Steps 3 and 4 depend on a source-HTML → output-Markdown mapping** recorded per version in `state.db` by the converter, rather than recomputed here. Recomputing it would let CSH resolution disagree with what conversion actually did about renaming, deduplication, or dropped topics — and disagree silently.

### 9.4 Writing `csh.yml` — **Built** (Phase 5a)

`transforms/csh.py:render`, `write`. One file per version at the Markdown output root, beside `toc.yml`, and **it is a flat map and nothing else**:

```yaml
"bw_rest_binding": "topics/rest_binding.md#adb.palette"
"1234": "topics/install.md"
```

**The shape is AEM's contract, fixed on 2026-09-10** (`architecture.md` §5.4.2), and it replaced a nested schema this section carried until then — schema tag, product/version/engine header, per-doc-set tallies, a `topics` map of `{file, anchor, also}` objects and an `unresolved` list. What the consumer reads is `identifier → path`; everything else was the tool describing its own work inside a file somebody else parses.

- **Both sides are double-quoted, unconditionally** (§9.1). Keys because 834 of 11,054 Flare names are digit-only and YAML 1.1 turns `1234` into an integer and `6.2` into a float; values for symmetry, since a conditional quote is a branch that can be wrong.
- **Keys are sorted byte-exactly**, so a re-convert of an unchanged version produces an identical file and a diff means something changed.
- **The anchor is appended to the path**, `file.md#anchor`, rather than kept as its own field. There is no field to keep it in, and 43% of WebWorks entries carry one.
- **The path is POSIX and relative to `csh.yml`**, so the whole output tree relocates without a rewrite.
- **Everything the nested schema carried and this one cannot goes to the findings register** (§8.5), not to a sidecar file: `unresolved` becomes `CSH_UNRESOLVED` with the original link, `also` becomes `CSH_AMBIGUOUS` naming the winner and the dropped targets, and the per-doc-set tallies stay on the run's result for the report. Invariant 9 is the reason they go somewhere rather than nowhere — an identifier is resolved *or* listed, never quietly dropped.
- **A version with no CSH source, or only empty ones, gets no file at all**, and a stale one from a previous run is removed. An empty map is indistinguishable from a failed run; absence plus a report line is the honest signal.

### 9.5 Frontmatter — **Built** (Phase 5a)

A topic that owns identifiers carries them as a flat list of quoted strings:

```yaml
csh: ["bw_rest_binding", "restBindingRef"]
```

Always a list, even at length one, because a page commonly owns several. Topics with no identifier get no key at all.

Identifiers are known before conversion writes the file — parsing a 24 KB alias file is cheap — so frontmatter lands in the topic's **first and only write**, not in a second read-modify-write pass over the whole output tree.

### 9.6 CSH verification

- Every value in `csh.yml` names a file that exists, and where it carries a `#anchor`, that anchor is present in the file.
- Every identifier in a topic's frontmatter appears in `csh.yml`, and every identifier in `csh.yml` appears in its topic's frontmatter.
- `unresolved` is empty, or each entry in it is accounted for in the report.
- **Cross-version regression:** identifiers present in the previously converted version and absent from this one are reported. A dropped identifier is an upgrade that breaks the product's Help button, and it cannot be seen from inside a single version.

---

## 10. Stages 6 and 7: Synthesis and sync

**Specified.** Navigation synthesis walks the converted tree to produce `toc.yml`, `nav.yml`, `meta.yml` and landing pages from the Jinja templates in `config/aem_templates/`, then the distributor copies each version's output into the target publishing layout.

**Two of the four templates are placeholders, deliberately** (2026-09-09, user decision). `toc.yml` and `index.md` have specified shapes: the three node rules below fix the first, and §10.5 and the landing-page rule fix the second. **`nav.yml` and `meta.yml` have no authored spec** — the AEM side has not supplied one, and `config/aem_templates/nav.yml.j2` and `meta.yml.j2` are Phase-1 scaffolding guesses that were never measured against anything. They stay as they are, marked in the template files themselves as placeholders, until the details arrive; then the templates get written against those details rather than retro-fitted to a guess. Three consequences hold in the meantime: their rendered content is **not a contract**, so §8.4 asserts nothing beyond "the file exists and parses as YAML"; the one fact that *is* grounded — SuiteHelp's `GUID-*-homepage.html` supplying `publication-title`, `release-version` and `release-date` in all 314 doc-sets that ship one (`architecture.md` §5.2.7) — is an input the eventual `meta.yml` will want, and is collected regardless of what the template does with it; and no Stage 6 work is blocked by the gap, because the synthesizer's real work is the node list, which `toc.yml` consumes.

**The stage ends at the filesystem** (`architecture.md` §6.0, decided 2026-09-09). `docushift sync` writes repo-shaped directory trees under `--target-dir`; it runs no git command, creates no repository and pushes nothing. Publishing is picked up separately. Every rule below describes what is written, so none of them changes.

**Navigation synthesis does not just serialize what the engine handed it.** Three rules apply to the node list before it is written, all settled by the 2026-09-09 Flare survey (`architecture.md` §5.1.5) and all engine-neutral — two create nodes the source does not supply, one moves nodes the source misfiles:

- **The landing page is the first node.** The engine reports which converted topic is the version's landing page — for Flare, `HelpSystem.xml`'s `DefaultUrl`, which resolves in 676 of 676 output roots but is absent from the TOC in 55 of 60 sampled ones. If that topic is already a TOC node it moves to first; otherwise it is inserted as first. It never falls through to "Unfiled".
- **A node with children and no page gets a generated one.** AEM treats a childed navigation node with no page as a broken parent, and Flare's `'___'` sentinel produces 165 of them per 60 output roots — 151 at top level, holding 1,357 children between them. The synthesizer emits a page titled from the node's label whose body links its immediate children, stamped as generated in frontmatter so a re-run replaces it rather than treating it as authored. Childless headless nodes are dropped and counted.
- **The support and legal pages are the last two nodes** — `Documentation and Support Services` second-last, `Legal and Third-Party Notices` last, both at top level. The engine reports which converted topic is which; the synthesizer **moves** those nodes to the tail rather than appending, because they are already TOC entries in 97% and 96% of Flare roots and appending would duplicate the topic. It is the landing-page rule inverted, and it mostly ratifies the source: 610 of 676 roots (90.2%) already end support-then-legal. Three constraints follow from the survey. The label is taken from the node, never hard-coded — the support page's heading is `TIBCO` in 565 roots, `ibi` in 49 and `Spotfire` in 45. There is **one legal node, not two** — no separate third-party-notices page exists in the corpus, and the combined page has a single `h1` and no `h2` sections. And a version that ships neither page simply has a shorter tail; unlike a headless container, a missing legal page breaks nothing, so nothing is generated to stand in for it.

**The sync path shape is settled** (`architecture.md` §6.1): the publishing form `{docs-tree}/{locale}/{product}/{doc-class}/{version-dashed}/` where the tree is `en-us-tib-messaging-userdocs` (or `loc-…` for a non-primary locale), with the docs repo taking `online-help`, `user-guides`, `release-information` and `reference-documents`, and a sibling `-resources` repo taking `api-references` and `archives`. The distributor therefore does four things per version, in order: copy the converted tree and its navigation into `online-help/`; copy the PDF and document assets into their three doc-classes and generate an `index.md` and `toc.yml` for each (§10.5); copy the API-reference trees, unconverted, into the sibling repo and index `archives/` from the catalog (§10.6); then rewrite every link that crosses from one tree to the other. The rewrite is last because it needs both destinations to exist, and it belongs here rather than in Stage 5 because conversion does not know the publishing layout. There is no fifth step: the trees are left on disk.

The dots-to-dashes version conversion belongs here too, at the publishing boundary, and nowhere earlier: the working tree's dotted version must round-trip to a `versions.csv` key, which `6-2-3` cannot (`6.2.3`? `6-2.3`?).

`-resources` is a **separate tree**, not a directory in the docs tree (`architecture.md` §6.3) — generated API trees and archived ZIPs grow monotonically, do not delta, and are not reviewed like prose. It is written as a sibling and left to be published as a sibling repository.

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

### 10.5 Step 3, the document doc-class index — **Specified**

Each of `user-guides`, `release-information` and `reference-documents` gets a flat `index.md` and `toc.yml` built from its routed file list, because a copied PDF with no index is unreachable. Grounded in a 2026-09-08 survey of the same 1,822 versions (`architecture.md` §6.2.2).

**Input** is §10.4's routed list for one version, **de-duplicated by lower-cased filename within each doc-class**, root `V/pdf` winning over nested `V/doc/pdf`. 25 versions carry both folders and they share **178 filenames**; without this the same PDF is copied and listed twice.

**A doc-class with no files produces no folder and no index.** 156 of the 1,822 versions route nothing at all; the rest split 91 / 386 / 1,189 across one, two and three doc-classes. An index that links to nothing is a published dead end, so emptiness is expressed by absence.

**Title for one entry**, first hit wins:

1. **The canonical name of the kind**, if the filename stem matches one of §10.4's patterns or the fifth pattern `(^|[\s_.-])rtu([\s_.-]|$)` — Release Notes, Readme, License Agreement, Reminder Notice, VPAT (Accessibility Conformance Report), Right to Use Terms. Covers 100% of `release-information` and 97.7% of `reference-documents`. The `rtu` pattern exists for titling only: `doc/` already routes everything non-readme to `reference-documents`, so it changes no destination.
2. **The PDF's Info-dictionary `/Title`**, read with **`pypdf`**, for `.pdf` files that reached step 2 — i.e. `user-guides`, which is by construction the residue of the step-1 patterns. Over all 5,007 de-duplicated user-guide PDFs: **70.8% usable, 27.9% blank, 1.3% junk**. Wrap the read: pypdf raises on one truncated file in the corpus, and an exception falls through to step 3 like a blank does. **Never use a byte-level `/Title` regex** — outline bookmarks are `/Title` entries too and usually precede the Info dictionary, so a regex returns `'Basic Tab'` and `'Table of contents'` while claiming 57% success.
   - **Reject as junk**, falling through to step 3: `untitled` case-insensitively, any title ending `.book`/`.fm`/`.doc`/`.docx`/`.pdf`/`.indd`/`.mif`, and any beginning `Microsoft Word - `. That is the whole of it — all 65 junk titles in the corpus are the authoring tool's source filename, in 37 distinct values.
   - **`pypdf` over `pymupdf`, verified not assumed** (2026-09-09): head to head over all 5,007, byte-identical titles on the 5,006 both read (100.00%), identical tallies, pypdf 4× faster (122 s v 501 s), one pypdf-only failure on a truncated PDF. pymupdf is AGPL; pypdf is BSD-3-Clause.
3. **The filename stem with `[_.-]+` collapsed to single spaces.** Nothing more: no vendor-prefix strip, no product-token removal, no version excision. Doing all three yielded 3,352 distinct titles for 5,007 files, 82.9% of them unique, including `'adix 2'` and `'1 0 0 installation'`. The cleverness is what produces the garbage.

**Order** is by kind rank then title, so `release-information` leads with Release Notes and `reference-documents` with the VPAT, rather than with whatever order the filesystem returned.

**Output.** `toc.yml` is flat — these doc-classes have no hierarchy — one item per file with `title`, `path` (the bare filename), `type` (extension) and `bytes`. `index.md` carries the `online-help` index frontmatter plus `doc_class`, and renders the items as a linked list. Both come from new templates in `config/aem_templates/`; the existing `index.md.j2` and `toc.yml.j2` assume Markdown targets and a nested `guides` tree and are not reusable here.

### 10.6 The `archives/` index — **Specified**

`archives/` in the `-resources` repo gets an `index.md` and a `toc.yml` too, but **its input is the catalog, not the directory**. Archived ZIPs are downloaded on demand (`architecture.md` §4.3), so the folder typically holds two of a product's forty archived versions; indexing what is on disk would publish a history that is 95% missing and look complete while doing it. Grounded in a 2026-09-09 sample of 60 public products / 326 archived versions (`architecture.md` §6.2.3).

**Input** is every `versions.csv` row for the product with `is_archived` set — present or not on disk. A product with no archived rows gets no folder and no index; 17 of the 60 sampled products (28%) are in that state.

**One item per archived version:**

- `version` — `version_no` from the catalog. **Not parsed out of the ZIP filename**, which in 19% of cases carries a former product name (`…composite-information-server-3-1-0…` under the slug `cisco-information-server`).
- `released` — `GA_date` normalized to `YYYY-MM`. It arrives in two formats, `November 2022` (54.3%) and `2017-10-23T08:54:14.000Z` (45.7%); all 326 parse under those two patterns. Month is the precision the majority actually carries, so a day is never synthesized.
- `available` — is the ZIP in this repository. If true, `path` (relative) and `bytes`; if false, `url` — `{base_url}{zipPath}` verbatim, never templated.
- A cross-link to `online-help/` when the version is **also live**: 25 of 326 archived versions (7.7%) are, always the product's current one, which the archive list repeats rather than replaces (§2.8).

**Order is version descending** (§1.3's natural ordering), never `released` descending. The two disagree for 9 of the 32 sampled products with two or more archived versions (28%), because maintenance lines ship after their successors — EMS 8.7.0 is dated July 2023, EMS 10.2.1 November 2022.

**`api-references/` gets no index.** 496 of 499 Javadoc-shaped roots in the cache ship their own `index.html` (the 3 exceptions are package directories named `api`, not roots). Generating a second entry point beside the generator's own competes with it.

**Step 4, the link rewrite, in full.** Every link from a converted topic into an API-reference path (`api/`, `javadoc/`, `Java_API/`, `java/`, `c/`, `golang/`, `tibdg/`, however many `../` deep) is replaced with an **absolute URL**: `publish_base_url` from `config/publishing.yaml`, then the same `resources_tree_name(…)/{locale}/{product}/api-references/{subdir}/{version-dashed}/{rest}` template that placed the file — `en-us-tib-messaging-userdocs-resources/…`, composed from the same `docs_suffix` the tree was written with, so a link cannot name a repository that was never created. Link construction and file placement call one function, so a link cannot point somewhere the copy did not write. Links that stay inside the docs repo — within `online-help/`, or out to the PDF doc-classes — are left relative, which is what keeps the repo previewable before publication.

---

### 10.7 Step 4, the cross-boundary rewrite — **Specified**

The distributor's last step (§10 above), and the only link work Stage 7 does. Everything else was settled at conversion time, which is the point: §6.4 guarantees that a *relative* asset link inside an output root already resolves, so the assets move with their tree and those links are untouched. Three reference classes are left, all of which needed a destination that did not exist until now.

**1. Links into `-resources`.** Converted help links into an API-reference tree (`[…](api/java/index.html)`), which is now a sibling repository. Rewrite to an absolute URL from `publish_base_url` (`architecture.md` §6.4). §8.4 then classifies these as external and does not resolve them against the filesystem.

**2. References that escaped the output root**, handed over by §6.4 step 3.5 with their resolved absolute source path. Route the target through §10.4's document router to find the doc-class it landed in, then emit a relative path across doc-classes — both are in the docs repo, so this stays a filesystem link and stays checkable. Measured: 279 in the Flare sample (76 into `doc/`, 66 into `pdf/`, 68 at the version root, 15 in `license/`), **0 in DITA and 0 in WebWorks** (`architecture.md` §5.5.8). Where the target resolves to no routed document — 152 of the 279, references to files the ZIP does not ship — emit the link text as plain text and count it.

**3. The `archives/` and doc-class index links**, which §10.5 and §10.6 generate from lists rather than rewrite.

**Nothing is re-resolved from a URL or a cache path.** Every rewrite here consumes a target that Stage 5 already resolved and recorded; Stage 7 changes the *form* of a reference, never its identity. This is the rule `architecture.md` §5.5.9 measures the cost of breaking — 7,231 broken image links in the predecessor's output, from a second derivation of a path that was already known.

The rewrite is last because it needs both destinations on disk, and it is here rather than in Stage 5 because conversion does not know the publishing layout.

## 11. Invariants

Properties that hold across the whole tool. Each is a rule some algorithm above exists to maintain, and each is worth testing directly.

1. **A load-then-save cycle with no changes produces a byte-identical file.** (§3.6)
2. **A fetch never loses a human edit**, and never requires the human to have flagged it. (§3.2)
3. **A fetch is all-or-nothing.** A blocked deletion leaves both CSVs and the state DB untouched. (§3.4)
4. **No machine-local path appears in either CSV.** Locations are derived; only intent is stored. (§1.5)
5. **An archived version is never downloaded, extracted or converted** unless a human flips its eligibility. (§4)
6. **A version support has retired is never downloaded, extracted, converted or laid out** — including one first discovered after the report landed. Absence from the report never retires anything, and no product name is matched by anything looser than an exact slug or a reviewed alias. (§3.3.2)
7. **An unknown engine is never guessed.** A version stays `auto` and is skipped loudly. (§7)
8. **A hand-supplied package converts through exactly the same path as a downloaded one.** No downstream stage branches on provenance. (§5.2)
9. **A help identifier is either resolved or listed as unresolved.** Nothing is silently dropped, and identifier text round-trips byte-exactly as a string. (§9)
10. **Absence is reported, never faked.** No empty `csh.yml`, no empty version list from a failed crawl, no stage command that exits 0 having done nothing.
11. **An unmeasured value is blank, never zero.** The inventory columns distinguish "never extracted" from "extracted, found none", and no stage writes them for a run that failed. (§6.3)
12. **One path is classified as an API reference by exactly one predicate**, shared by the Stage 4 count, the Stage 5 skip and the Stage 7 route. (§6.3)
13. **A relative asset link exists in the output if and only if that asset was copied.** One resolution, at emit time, produces both — or neither, plus a counted failure. No later stage re-derives an asset path from a URL, a cache layout or a version segment. (§6.4, §10.7)

---

## 12. Algorithm index

Most rows are **Built** or **Specified**. Two are neither, and are marked as such rather than left off the table: **Unsurveyed** means the scope is known and the design is not, and **Placeholder** means the artifact is written but its shape is a guess awaiting a spec. Both are gaps someone has to close; a row that omits them reads as a complete index.

| § | Algorithm | Status | Implementation |
| :--- | :--- | :--- | :--- |
| 1.2 | Tolerant read / strict write | Built | `utils/csvio.py` |
| 1.3 | Natural version ordering | Built | `utils/csvio.py:natural_version_key` |
| 1.4 | Slug and folder naming | Built | `utils/slug.py` |
| 1.5 | Path derivation | Built | `config.py` |
| 2.1 | Request policy and throttling | Built | `utils/http.py:build_session`, `Throttle`; `discovery/client.py` |
| 2.2 | Tolerant payload reading | Built | `discovery/crawler.py` |
| 2.3 | The crawl | Built | `discovery/crawler.py:discover` |
| 2.4 | Product-list normalization | Built | `discovery/crawler.py:_list_products` |
| 2.5 | Building one product | Built | `discovery/crawler.py:_build_product` |
| 2.6 | Code, folder and ZIP URL derivation | Built | `discovery/crawler.py`, `client.py:active_zip_url` |
| 2.7 | Family classification | Built | `config.py:resolve_product_info` |
| 2.8 | Archive index overlay | Built | `discovery/crawler.py:_apply_archive_index` |
| 3.1 | Catalog load and join | Built | `catalog.py:load` |
| 3.1 | Selector resolution (slug or code) | Built | `catalog.py:resolve_slug` |
| 3.2 | Three-way field decision | Built | `catalog.py:_take_theirs` |
| 3.3 | Family by provenance | Built | `catalog.py:_merge_product` |
| 3.3.1 | Scope by rule then provenance | Built | `catalog.py:_resolve_scope` |
| 3.3.2 | End-of-support report loading | Built | `config.py:load_eos`, `_read_eos_report` |
| 3.3.2 | Release status by report then provenance | Built | `catalog.py:_resolve_release_status`, `apply_eos` |
| 3.4 | Deletion detection | Built | `catalog.py:_collect_deletions` |
| 3.6 | Canonical write | Built | `catalog.py:save` |
| 3.5 | Snapshot recording, one transaction per fetch | Built | `state.py:transaction`, `catalog.py:_record_snapshots` |
| 4 | Selection | Built | `catalog.py:iter_versions` |
| 5.1 | Download one version | Built | `downloader/fetcher.py:download_one`, `fetch_to`, `download_many` |
| 5.2 | Hand-supplied ingestion | Built | `downloader/fetcher.py:ingest_file`, `catalog.py:add_version` |
| 6.1 steps 1–3 | Extraction, `.part/` swap and the unchanged-package skip | Built | `extractor/unpacker.py:extract_one`, `extract_many` |
| 6.1 step 2 | Path-traversal refusal | Built | `extractor/safe_unzip.py:safe_extract` |
| 6.1 steps 4–5 | The one walk | Built | `extractor/inventory.py:inventory_tree`; `unpacker.py:measure` |
| 6.2 | CSH source location and the three readers | Built | `engines/csh.py:csh_format_of`, `read_csh_source` |
| 6.3 | Inventory columns and write-back | Built | `catalog.py:record_extract_inventory`, `utils/csvio.py` |
| 6.3 | API-reference predicate and triage | Built | `apiref.py:find_api_roots`, `is_api_reference`, `looks_like_api_name` |
| 6.4 steps 1–2 | Asset inventory by category and destination | Built | `extractor/inventory.py`; `state.py:record_asset_inventory` |
| 6.4 steps 3–7 | Asset copy set — resolve once, copy and link together | Built | `transforms/assets.py:AssetCopier` |
| 6.1, 6.4 | Build-and-swap, with the Windows scanner retry | Built | `utils/swap.py:swap`, `remove` |
| 7.1–7.3 | Engine detection, three passes | Built | `engines/detector.py:detect_version`, `detect_tree` |
| 7.1 | Output-root location, by content | Built | `engines/roots.py:find_output_roots`, `owning_root` |
| 7.3 | Write-back, folder map and the raw generator | Built | `extractor/unpacker.py:identify`, `catalog.py:record_detected_engine` |
| `architecture.md` §5 | Stage 5 driver — selection, dispatch, the write, the swap | Built | `converter/driver.py:DocumentConverter` |
| `architecture.md` §5 | The engine contract and the document model | Built | `engines/base.py:BaseEngine`, `ConversionContext`, `Unit`, `Document` |
| `architecture.md` §5.1.8, §5.2.6, §5.3.8 | Reference classification, normalization and emit | Built | `transforms/links.py` |
| `architecture.md` §5.1.7, §5.2.5, §5.3.7 | Callouts, code fences, GFM-safe tables | Built | `transforms/{callouts,code,tables}.py` |
| `architecture.md` §5.1 | Flare converter | Built | `engines/flare.py:FlareEngine`; its TOC reader in `engines/flare_toc.py` |
| `architecture.md` §5.1–§5.3 | The HTML→GFM walk the engines share | Built | `transforms/markdown.py:Renderer`, `parse` |
| `architecture.md` §5.2 | SDL DITA converter | Built | `engines/dita.py:DitaEngine`; its TOC reader is `read_toc` in the same module |
| `architecture.md` §5.3 | WebWorks converter | Specified | Phase 5d, `engines/webworks.py` |
| — (owed) | DocBook converter — `str` and `sfire-sfds`, 10 versions | **Unsurveyed** | Phase 5e, `engines/docbook.py`; needs an `architecture.md` §5.x first |
| 8.1–8.3 | Catalog validation, warnings, triage | Built | `catalog.py` |
| 8.5 | Findings register — codes, severity, per-version flush | Built | `reporting/findings.py`; `state.py:record_findings` |
| 9.3 | CSH resolution | Built | `transforms/csh.py:resolve`, `order_doc_sets` |
| 9.4–9.5 | `csh.yml` and frontmatter | Built | `transforms/csh.py:render`, `write`, `frontmatter_value` |
| 9.6 | CSH verification | Specified | Phase 7 |
| 9.2 | CSH readers (**Flare, DITA, WebWorks**) | Built | `engines/csh.py`; the schema, resolver and writer stay Phase 5 |
| 10 | AEM synthesis and sync | Specified | Phases 6–7 |
| 10 (part) | `nav.yml` / `meta.yml` shapes | **Placeholder** | Pending an AEM spec; the two templates in `config/aem_templates/` say so |
| 10.4 | Document router (`pdf/` and `doc/` → doc-class) | Specified | Phase 6 |
| 10.5 | Document doc-class index (`index.md`, `toc.yml`, title chain) | Specified | Phase 6 |
| 10.6 | `archives/` index, built from the catalog rather than the directory | Specified | Phase 6 |
| 10.7 | Cross-boundary link rewrite (`-resources` URLs, escaped asset references) | Specified | Phase 6 |
