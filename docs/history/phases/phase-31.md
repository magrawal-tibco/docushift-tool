> Archived from `docs/planning.md` on 2026-10-02. Status: **Complete, 2026-10-02**. Kept verbatim; a heading that says *Planned* was built later in this same section.
> Index of every phase: [`docs/planning.md`](../../planning.md#finished-phases).

### Phase 31: Splitting WebFOCUS into Four — **Complete, 2026-10-02**

`webfocus` holds seven products that publish as one repository. Three of them
are separate deliverables with their own release trains, and two more are
container repackagings of products that otherwise live elsewhere. Splitting them
out is a catalog edit, not a code change — but a catalog edit that silently
reverts is worse than none, so the whole chain is written down here first.

**The four families, and who lands in each.** Names are the user's: the three
product splits carry their product's own name.

| family key | display name | products |
|---|---|---|
| `webfocus-app-studio` | WebFOCUS App Studio | `ibi-webfocus-app-studio` |
| `webfocus-dsml-services` | WebFOCUS DSML Services | `ibi-webfocus-dsml-services` |
| `webfocus-reporting-server` | WebFOCUS Reporting Server | `ibi-webfocus-reporting-server` |
| `container-editions` | Container Editions | `ibi-webfocus-container-edition`, `ibi-webfocus-dsml-services-container-edition` |

`webfocus` is left holding `ibi-webfocus-client` and `ibi-webfocus-installer`.
Five of the seven move; the family does not disappear.

**Why `container-editions` is a family and not a suffix.** The two container
editions are the same documentation shipped for a different runtime. Grouping
them by packaging rather than by product keeps the DSML split clean — a reader
looking for DSML gets the product, not the product plus its Docker variant — and
it is a bucket the other BUs can reuse later. The cost is that
`ibi-webfocus-dsml-services-container-edition` no longer sits beside the product
it documents; that is the explicit trade the user chose.

**The keyword rule is the part that bites.** `taxonomy.yaml:197` currently reads

    - match: ["webfocus", "webfocus-app-studio", "webfocus-client", "webfocus-reporting-server"]
      bu: ibi
      family: webfocus

First match wins and the bare token `webfocus` is a substring of every display
name in the set, so this one rule claims all seven. A `family_source=manual` pin
protects the five rows that exist today, but it does nothing for a product
discovery adds tomorrow — a new "WebFOCUS App Studio" SKU would land back in
`webfocus` and nobody would be told. The rule is therefore split into four, most
specific first, with the bare `webfocus` token left last as the fallback it
already is in practice.

**What gets done, in the skill's order.** `catalog set --product <slug>
--family <key>` for each of the five slugs, which pins `family_source=manual`
and regenerates `_bu`/`_family` across every version row in one step — no
hand-edited `*_source` cells. Then the four `families:` keys in `taxonomy.yaml`,
then the rule split, then `catalog import` to validate, then `catalog triage` to
confirm the `manual` count rose by exactly five.

**Nothing on disk needs relocating, and that is checked rather than assumed.**
`families/en-us-ibi-webfocus/` holds an `extracted/` directory with three empty
product folders and no `downloads/` or `archive/` at all; there is no
`output/en-us-ibi-webfocus/`. Nothing has been downloaded, extracted or
converted for this family, so the four new workspaces are created empty and the
three stale placeholders are removed. Had a single package been downloaded this
would instead be a question for the user, not a `mv`.

**One thing deliberately left at its default, flagged rather than decided.**
`repo_slug` is unset on all four, so they publish to
`en-us-ibi-webfocus-app-studio-userdocs` and friends — the DSML one reaching 38
characters before the product slug is appended. The doc platform's own naming
pressure is why `tibco` became `tib`. Shortening these is a publishing decision
with a one-way door (changing `repo_slug` later moves both the workspace
directory and the repository), so it is raised now and left to the user rather
than guessed. **Decided: kept at the long defaults.**

#### Outcome

All five moved, `family_source=manual` on each, the `manual` count rising
239 → 244 — exactly five rows, no collateral. `_bu`/`_family` regenerated across
127 `versions.csv` rows (container-editions 35, app-studio 38,
reporting-server 39, dsml-services 15; `webfocus` down to 75). The three empty
placeholders were removed. **1,673 tests pass, 2 skipped.**

**The rule split was the part worth doing carefully, and the first draft of it
was wrong.** Matching `container-editions` on the substring "container edition"
reads correctly and is a 16-product accident: BusinessWorks CE, BusinessConnect
CE and its seven protocols, Hawk CE and its BW microagent, Microflow CE,
ActiveMatrix Service Grid CE, LogLogic EVA CE, and an AWS Marketplace
subscription all carry that phrase, and an ibi rule sitting above the TIBCO
block in a first-match-wins list would have claimed every one of them into an
ibi family. Caught by counting the matches before writing the rule rather than
by reading the output afterwards; the rule ships matching the product codes
`wfce` and `dsmlce` instead, with the count written into the comment so the next
person to widen it sees the number first.

---
