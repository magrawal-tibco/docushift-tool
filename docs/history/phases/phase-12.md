> Archived from `docs/planning.md` on 2026-10-02. Status: **Complete**. Kept verbatim; a heading that says *Planned* was built later in this same section.
> Index of every phase: [`docs/planning.md`](../../planning.md#finished-phases).

### Phase 12: An Extracted Tree Can Be Measured Without Its Package

Stage 4 writes five columns for one version — `_has_csh`, `_csh_names`, `_has_api_ref`, `_api_files`, `_doc_files` — from one walk, in `record_extract_inventory` (`catalog.py:798`, called from `unpacker.measure`). Nothing else writes them: convert reads the extracted tree and produces Markdown, and `convert_batch` beside them is an *input* label set by `catalog set --batch`, not an output. So a version whose columns are blank has never been measured, whatever else has happened to it.

Six versions on disk are in exactly that state, and they are the six that have been converted:

| | |
|---|---|
| extracted version trees in `families/*/extracted/` | **6** (all DataSynapse) |
| of those, matching a catalog row | 6 |
| of those, **blank inventory columns** | **6** |
| trees extracted | 2026-05-29 … 2026-07-27 |
| `record_extract_inventory` landed (`b094ed1`) | **2026-09-11** |
| converted output written | 2026-09-17 |

The trees predate the writer by two to four months. `engine=flare` on those rows is not evidence of a run that could have measured them — `engine_source=manual` on both `gridserver-manager` rows; it was set by hand.

#### The branch that already exists, and the two guards that stop it

`unpacker.extract_one` **already** handles this. Its unchanged-package fast path is deliberately not a pure no-op:

> *"An unchanged package is a no-op unless nobody has measured it. A tree extracted before the inventory walk existed has blank columns, and reporting `current` over a blank row would leave it blank for good."* (`unpacker.py:186-193`)

It runs `identify` + `measure` over the tree already on disk and writes the five columns without unpacking anything. That is the behaviour wanted here; it simply cannot be reached:

1. **`source.is_file()` at `unpacker.py:168`** returns `NO_PACKAGE` first. There are **0 ZIPs** anywhere under `families/*/downloads/` — the 249M on disk is extracted trees. `--force` fails at the same line, so *neither* route to `measure` is reachable.
2. **The checksum test at `unpacker.py:179`** cannot pass even after a re-download: `state.db` holds **0 rows** with `extract_zip_checksum`, out of 3,453 `version_metadata` rows. That key is written only after a successful unpack, and these unpacks predate it too. A re-download therefore buys a full re-extract, not a measurement.

The package is wanted for one thing — a checksum, for the *currency* test. `measure()` takes a tree and walks it; it has no use for the archive.

#### What changes

| File | Change |
|---|---|
| `extractor/unpacker.py` | a `measure_cached(product, version)` route: `target.is_dir()` and the inventory columns blank is sufficient; it runs `identify` + `measure` and returns a new `ExtractOutcome.MEASURED`. The existing `source.is_file()` guard stays exactly where it is on the unpack path |
| `cli.py` (`extract`) | `--measure-only`, taking the same selection flags. Mutually exclusive with `--force`, which means the opposite thing |
| `extractor/unpacker.py` (`extract_many`) | reports `MEASURED` separately from `EXTRACTED` and `CURRENT`, so a run that touched no archive says so |
| `architecture.md` §3.9 | the five columns can be written from a cached tree, and what that does and does not assert |

#### What it deliberately does not do

- **It does not write `extract_zip_checksum`.** There is no package to hash, and a fabricated key would make the next real `extract` think the tree is current. The row stays "measured but not checksummed", which is the truth.
- **It does not claim the tree is current.** The columns describe what is on disk. This satisfies the rule the stage is built on — never write a number you did not just measure — but it cannot assert the tree was built from today's upstream ZIP. `--measure-only` is opt-in for that reason; the default path keeps demanding the package.
- **It does not backfill zeros.** `measure` already refuses to write columns for a partial walk (`unpacker.py:307`), and that refusal carries over unchanged: a blank row after a `--measure-only` run is a signal, not a failure of the flag.
- **It does not re-detect a manual engine.** `identify` refuses to overwrite `engine_source=manual` (§7.3 step 3), so the two `gridserver-manager` rows keep `flare` whatever detection says — and the run report should say when detection disagreed, rather than silently agreeing.

##### Acceptance

`extract --product tibco-datasynapse-gridserver-manager --measure-only` with `downloads/` still empty: outcome `MEASURED`, no network, no `.part` directory created, and `_has_csh`, `_csh_names`, `_has_api_ref`, `_api_files`, `_doc_files` filled on `7.1.1` and `7.2.0`. Byte-compare the extracted tree before and after — a measurement must not touch it. Re-run the same command: the rows are no longer blank, so it reports nothing to do. Then `--measure-only` over all six, and check the two booleans against their counts — `_has_csh=true` with `_csh_names=0` is legal and expected (55% of the corpus ships an empty help map), `_has_csh=false` with `_csh_names>0` is the contradiction `catalog import` already gates on (`catalog.py:1078`). Finally `extract --product … --measure-only --force` is refused with a message rather than doing something surprising, and the full suite.

---
