# Test Fixtures

Sample inputs for the unit and integration suites.

| Planned fixture | Used by | Arrives in |
| :--- | :--- | :--- |
| `flare/` — trimmed MadCap Flare output (`*.mcwebhelp`, `Skins/`, `Data/`, `csh.js`, a handful of topics) | engine detector, Flare engine, CSH mapper | Phase 5 |
| `webworks/`, `dita/`, `docbook/` — minimal marker sets per generator | `engines/detector.py` | Phase 5 |
| `csh/` — hand-written `Alias.xml` variants, one per hazard the corpus survey found | `transforms/csh.py` | Phase 5 |
| `csv/` — Excel-mangled `products.csv` / `versions.csv` (BOM loss, `1.10` → `1.1`, `TRUE`/`FALSE`, locale dates) | CSV round-trip regression tests | Phase 2 |

The `csh/` fixtures are enumerated rather than sampled, because each one stands for a
measured property of the real corpus (`docs/architecture.md` §5.3.1): two identifiers
differing only in case, an identifier YAML would coerce to a non-string (`1000`, `Yes`,
`6.2` — routine for WebWorks, whose identifiers are ctx stems), a `Link` carrying a
fragment, an alias file that resolves 0% because it was copied from a sibling output, a
version with three doc-sets whose identifiers overlap, and the empty and zero-byte files
that are 28% of the population.

A duplicate `ResolvedId` is deliberately *not* among them: the reader discards the integer,
so there is nothing for a fixture to assert beyond that it was ignored.

No `api/` directory: the discovery suite (`tests/unit/test_discovery.py`) declares its
payloads inline instead. They are hand-written to match the shapes observed live
(`docs/architecture.md` §2.1) — envelope wrapping, the detail object doubling as the
current version, mixed-archive siblings, stale archived folder paths, camelCase
variants — and trimmed to the fields under test. A recorded response would be a few
hundred lines of document listings around the same handful of keys, and the point of
each case would stop being visible in the file.

Keep fixtures small and committed. Full packages stay in the git-ignored `cache/`;
a real Flare sample is available there at `cache/pub/dsp_gridserver/7.1.1/doc/html/`.
