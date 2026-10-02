> Archived from `docs/planning.md` on 2026-10-02. Status: **Measured, 2026-09-23**. Kept verbatim; a heading that says *Planned* was built later in this same section.
> Index of every phase: [`docs/planning.md`](../../planning.md#finished-phases).

### Phase 18e: The First DocBook Family Reaches Publication — **Measured, 2026-09-23**

Not a build. `sync` and `validate` were run over the `streaming` family exactly as they shipped; nothing in the tool changed. It is recorded here because **no DocBook family had ever reached Stage 7**, so every number below is the first of its kind, and because the one class of finding it produced is a converter defect that needs its own phase.

##### `sync --family streaming --target-dir C:\github\tibco-docs-aem`

30 versions selected, **76 rows synced, 41,523 files, 858.3 MB**, into `en-us-tib-streaming-userdocs` and `en-us-tib-streaming-userdocs-resources`.

| doc-class | synced | no source tree |
|---|---:|---:|
| `online-help` | 8 | 22 |
| `user-guides` | 2 | 0 |
| `release-information` | 26 | 0 |
| `reference-documents` | 26 | 0 |
| `api-references` | 8 | 0 |
| `archives` | 6 | 0 |

0 failed, 0 skipped, 0 already-current. **8 product `metadata.yml` and 19 `version.yml` written.**

**The 22 `No source tree` rows are the ones already accounted for and none of them is new** — the 17 licence bundles and `tibco-modelops@1.3.0` that `ENGINE_UNKNOWN` names, plus the 4 `sb-hp-fix` `NO_TREE` rows. Each still published its `release-information` and `reference-documents` from the *extracted* package, which is the behaviour §6 was built for: **a version that never converted still publishes the PDFs it shipped.** Those 22 absences are the reason `release-information` is 26 rows while `online-help` is 8.

`spotfire-data-streams` 11.1.0 and 11.1.1 publish a full `online-help` and `api-references` of their own. That is the rebrand showing up in the published tree — the same content under both the old and the new product name — and it is catalog truth, not a sync fault.

##### `validate --target-dir C:\github\tibco-docs-aem --product <slug>`, all 8 products

`validate` has no `--family`, so it ran once per published product. **All eight exit 0.**

| | |
|---|---:|
| folders walked | 76 |
| files | 9,481 |
| references | 121,157 |
| of which external | 3,925 |
| of which tree-rooted | 268 |
| anchors resolved | 46,202 / 46,354 |
| `LINK_BROKEN` | **0** |
| errors, any code | **0** |
| warnings | **152 `ANCHOR_MISSING`** |

**268 tree-rooted API references resolve, 268 of 268** — which also proves the two `-resources` trees they name were actually written. Phase 17's precedent was that sync is where link damage becomes visible; for DocBook it did not, and 0 of 121,157 is the strongest single number the family produced.

**Version drop-down integrity holds** (§2): all 19 `version.yml` were read back, **62 of 62 `path` values resolve to a sibling directory sync wrote**, the listed set equals the on-disk set in every file, and every file is ordered numeric-descending.

##### The one defect: a DocBook admonition's anchor dies with its title

All 152 warnings are **4 distinct anchors** — an identical 19 per `online-help` version, 114 on `tibco-streaming` and 38 on `spotfire-data-streams`, which is the same content twice. Every one has the same shape:

```html
<div class="note" style="margin-left: 0.5in; margin-right: 0.5in;">
   <h3 class="title"><a name="mapsUsageNote"></a>Usage Note</h3>
   <p>The JMS Configuration Editor does not support …</p>
</div>
```

`engines/docbook.py` renders the admonition as a GFM alert and **discards both the custom title and the anchor**:

```markdown
> [!NOTE]
> The JMS Configuration Editor does not support …
```

The six inbound `…#mapsUsageNote` links per version survive the conversion intact and now point at nothing. The four are `mapsUsageNote` and `expressions_timestamp_abs_usagenote` / `expressions_note_aggfuncs-in-query-op` (`div.note`) and `docker-create_dockernotes` / `docker-lv-create_important` (`div.note`, `div.important`).

**The population is bounded and was measured, not estimated.** Scanning the whole 11.2.1 source for `div.{note,important,warning,caution,tip}` whose title carries an `<a name=…>` finds **exactly 5**; 4 are link targets and account for 100% of the family's findings, and the 5th has no inbound link. A titled admonition is not a heading in the DocBook output either — it is an `h3` inside the box — so the fix is to carry the id onto the emitted alert rather than to synthesize a heading slug, and `anchors` already has to agree with whatever is emitted. **A code change, so it waits for its own plan and approval.**

##### What this run does not claim

**A clean `validate` is not evidence that the 3 `REFERENCE_UNRESOLVED` conversion errors were repaired.** `REFERENCE_UNRESOLVED` is a *convert*-stage code (`findings.py:139`, emitted at `driver.py:444` for asset references that resolved to nothing) — the reference was dropped from the Markdown before sync ever saw it, so Stage 7 is silent about them by construction. `report --run` on the convert run remains the only place they are visible. Reading their absence here as a fix would be reading the wrong stage's silence.

---
