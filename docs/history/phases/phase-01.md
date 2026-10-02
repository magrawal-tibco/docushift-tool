> Archived from `docs/planning.md` on 2026-10-02. Status: **Complete, 2026-09-03**. Kept verbatim; a heading that says *Planned* was built later in this same section.
> Index of every phase: [`docs/planning.md`](../../planning.md#finished-phases).

### Phase 1: Architecture, Living Docs & Project Scaffolding
**Status: COMPLETE.** Implemented and verified 2026-09-03 — 54 tests pass, `ruff check src tests` is clean.
- [x] Living documentation system (`CONTEXT.md`, `architecture.md`, `user-guide.md`, `planning.md`; joined 2026-09-07 by `design.md`, the algorithm reference).
- [x] Multi-engine 7-stage pipeline design with additive catalog and active/archived version handling.
- [x] Verified `docs.tibco.com` API endpoints (`/api/a_to_z`, `/api/products/{slug}`, `/api/products/archive/{slug}`).
- [x] Create initial `config/taxonomy.yaml`.
- [x] `pyproject.toml` authored; `jinja2` added as a dependency for the AEM templates; `[tool.ruff]` added with an explicitly pinned rule set (`E,F,I,UP,B,SIM`, line length 120) so linting does not drift with the ruff version.
- [x] **Working environment** — `.venv` created, `pip install -e ".[dev]"` succeeded on Python 3.13.7. The console script `docushift` installs and runs.
- [x] **Directory layout** — all 9 subpackages created (`discovery/`, `downloader/`, `extractor/`, `engines/`, `transforms/`, `aem/`, `sync/`, `reporting/`, `utils/`), each a real package with a docstring naming its stage and phase. `config/aem_templates/` populated with Jinja templates for `toc.yml`, `nav.yml`, `meta.yml`, and `index.md`. *(Superseded 2026-09-10: AEM supplied the real artifact list — `nav.yml.j2` is deleted, `meta.yml.j2` becomes `metadata.yml.j2`, and `version.yml.j2` is added. See Phase 6's artifact contract.)*
- [x] **`cli.py`** — Click command tree matching the surface in `user-guide.md`: `catalog {fetch,list,show,enable,set,import,triage}`, `download`, `extract`, `convert`, `sync`, `validate`, `status`, `report`, `doctor`. `doctor` is functional; every stage command raises a `ClickException` naming its implementing phase, so an unbuilt stage exits non-zero instead of silently succeeding.
- [x] **`pytest` framework** — `tests/{conftest.py,unit/,integration/,fixtures/}`, **54 passing tests**. Real coverage of `ConfigManager`, the additive catalog merge, the CLI surface, and Phase 1 layout guards (subpackage imports, console-script entrypoint, shipped config contents, `.gitignore`).
- [x] **`.gitignore`** — now covers `output/`, `*.db`, `.venv/`, `__pycache__/`, build and test caches.
- [x] `config/docsite.yaml` — endpoints, ZIP URL templates, crawl politeness settings, and the active/archived conversion defaults. Loaded via `ConfigManager.load_docsite()`.
