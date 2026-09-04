# Test Fixtures

Sample inputs for the unit and integration suites.

| Planned fixture | Used by | Arrives in |
| :--- | :--- | :--- |
| `flare/` — trimmed MadCap Flare output (`*.mcwebhelp`, `Skins/`, `Data/`, `csh.js`, a handful of topics) | engine detector, Flare engine, CSH mapper | Phase 5 |
| `webworks/`, `dita/`, `docbook/` — minimal marker sets per generator | `engines/detector.py` | Phase 5 |
| `csv/` — Excel-mangled `products.csv` / `versions.csv` (BOM loss, `1.10` → `1.1`, `TRUE`/`FALSE`, locale dates) | CSV round-trip regression tests | Phase 2 |

No `api/` directory: the discovery suite (`tests/unit/test_discovery.py`) declares its
payloads inline instead. They are hand-written to match the shapes observed live
(`docs/architecture.md` §2.1) — envelope wrapping, the detail object doubling as the
current version, mixed-archive siblings, stale archived folder paths, camelCase
variants — and trimmed to the fields under test. A recorded response would be a few
hundred lines of document listings around the same handful of keys, and the point of
each case would stop being visible in the file.

Keep fixtures small and committed. Full packages stay in the git-ignored `cache/`;
a real Flare sample is available there at `cache/pub/dsp_gridserver/7.1.1/doc/html/`.
