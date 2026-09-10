# Test Fixtures

Sample inputs for the unit and integration suites.

| Planned fixture | Used by | Arrives in |
| :--- | :--- | :--- |
| `flare/` — trimmed MadCap Flare output (`*.mcwebhelp`, `Skins/`, `Data/`, `csh.js`, a handful of topics) | engine detector, Flare engine, CSH mapper | Phase 5 |
| `webworks/`, `dita/`, `docbook/` — minimal marker sets per generator | `engines/detector.py` | Phase 5 |
| `csh/` — hand-written `Alias.xml` variants, one per hazard the corpus survey found | `transforms/csh.py` | Phase 5 |
| `csv/` — Excel-mangled `products.csv` / `versions.csv` (BOM loss, `1.10` → `1.1`, `TRUE`/`FALSE`, locale dates) | CSV round-trip regression tests | Phase 2 |

`discovery/crawl_2026_09_09.jsonl` is the one committed fixture that is *not* small: the whole
2026-09-09 crawl, 634 products and 4,462 versions, trimmed to slug, code, name, `bu`, `family`
and the version list. It exists because the Phase 3.6 bug — `product_code` shared by 21 products,
one pair straddling the scope boundary (`architecture.md` §3.1) — is a property of the real
population and does not reproduce at three hand-written products. Sampling it down would mean
choosing which collisions to keep, which is choosing which regression to stop catching.

JSONL rather than JSON so a re-crawl diffs as the products that changed, not as one 159 KB line.
The merge it drives runs in under a second; the earlier per-row `state.db` commits that made it
take two minutes are gone (`design.md` §12, `state.py:transaction`).

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
