# Test Fixtures

Sample inputs for the unit and integration suites.

| Planned fixture | Used by | Arrives in |
| :--- | :--- | :--- |
| `flare/` — trimmed MadCap Flare output (`*.mcwebhelp`, `Skins/`, `Data/`, `csh.js`, a handful of topics) | engine detector, Flare engine, CSH mapper | Phase 5 |
| `webworks/`, `dita/`, `docbook/` — minimal marker sets per generator | `engines/detector.py` | Phase 5 |
| `api/` — recorded `docs.tibco.com` JSON responses (`a_to_z`, `products/{slug}`, `products/archive/{slug}`) | discovery crawler mocks | Phase 3 |
| `csv/` — Excel-mangled `products.csv` / `versions.csv` (BOM loss, `1.10` → `1.1`, `TRUE`/`FALSE`, locale dates) | CSV round-trip regression tests | Phase 2 |

Keep fixtures small and committed. Full packages stay in the git-ignored `cache/`;
a real Flare sample is available there at `cache/pub/dsp_gridserver/7.1.1/doc/html/`.
