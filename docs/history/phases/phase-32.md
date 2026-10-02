> Archived from `docs/planning.md` on 2026-10-02. Status: **Complete, 2026-10-02**. Kept verbatim; a heading that says *Planned* was built later in this same section.
> Index of every phase: [`docs/planning.md`](../../planning.md#finished-phases).

### Phase 32: A Family Is a Human's Call — **Complete, 2026-10-02**

Phase 31 ended by splitting a keyword rule five ways, and the exercise argued
against the mechanism it was repairing. The rule claimed seven products on a
brand substring and would have claimed sixteen more on a packaging one; both
were caught by counting matches by hand. A classifier whose every edit has to be
audited product-by-product is not saving the triage it exists to save.

**The decision: keyword rules never assign a family again.** A newly discovered
product arrives `family_source=unclassified` and waits for `catalog set`. The
271 products currently carrying `taxonomy_rule` are **not** retroactively
unset — they are the accumulated result of real review, and clearing them would
manufacture a 271-product backlog out of work already done.

**Where it changes.** `ConfigManager.resolve_product_info`
(`config.py:832`) is the only place a rule becomes a family; its one production
caller is `Crawler._product_shell` (`crawler.py:331`). The merge path does not
re-infer, so existing rows are untouched by construction — the change cannot
reach them even if it is wrong.

#### Three sub-decisions this forces, none of which should be made silently

**1. `bu` must keep being inferred, or the catalog misfiles everything.** The
same rules resolve business unit and family together, and the no-match fallback
is `bu=tibco`. Switching the rules off wholesale would file every new ibi,
Spotfire and DataSynapse product under TIBCO — replacing a wrong family with a
wrong *repository*, which is worse, because `bu` is the first path segment of
the workspace and the publishing target. **Proposal: rules still run and still
return `bu`; only the family they name is discarded.** The BU-level signal is
the reliable half — `webfocus` really is ibi — and the family-level one is the
half that has twice been wrong. A rule that matches now sets `bu` with
`family=unclassified`.

**2. The docsite-category promotion is the same mechanism and should go too.**
`_product_shell` fills an unclassified family from the docsite's own category
(`crawler.py:336`, `FamilySource.DOCSITE_CATEGORY`). It is automatic family
assignment by a different source, so leaving it in would reopen the door this
phase is closing. It is also **inert**: `catalog triage` reports 0 products
carrying it. **Proposal: remove the promotion and retire the enum member's use
at the crawler.** Zero rows change.

**3. An undeclared family should become an error on the manual path.** Today a
family typed into `products.csv` that `taxonomy.yaml` does not declare is
accepted with a warning and auto-registers a workspace
(`catalog.py:957-967`). That leniency existed because rules could outrun the
taxonomy file. With a human as the only author, a family key that is not
declared is a typo, and a typo that silently creates a publishing repository is
exactly the ghost-family failure the propagation skill warns about.
**Proposal: `catalog set --family` rejects an undeclared key and names the
declared ones**, with a flag to declare-and-set in one step if that proves
annoying in practice. This is the only sub-decision that could block a
legitimate workflow, so it is the one most worth arguing with.

#### What stays

The `rules:` block in `taxonomy.yaml` stays, now read for `bu` only. Deleting it
would mean rebuilding BU inference from nothing. The `family:` key on each rule
becomes documentation of what the rule *used to* guess; it is left in place and
commented rather than stripped, so the history of a classification is still
readable when someone triages one of the 154 unclassified products by hand.

`catalog triage` becomes the primary workflow rather than a progress report, and
its "N of M products still need triage" line stops being a number that shrinks
on its own. Worth saying out loud: **this phase makes the backlog grow.** Every
newly discovered product now lands in it. That is the point — the previous
behaviour did not have a smaller backlog, it had an unreviewed one.

#### Verification

- A discovered product matching a rule gets that rule's `bu` and
  `family_source=unclassified`; one matching nothing gets `bu=tibco` and the
  same unclassified family. No path returns `TAXONOMY_RULE`.
- The 271 existing `taxonomy_rule` rows and the 244 `manual` rows are
  byte-identical after a `catalog import`, and `catalog triage`'s counts move
  only by what a fetch newly discovers.
- `catalog set --family` on an undeclared key exits non-zero and changes
  nothing.
- The existing `resolve_product_info` tests in `tests/unit/test_config.py`
  (313-352, 597-600) assert the old contract and must be rewritten to the new
  one rather than deleted — they are the specification of this behaviour.

#### Outcome

All three sub-decisions shipped as proposed. **1,681 tests pass, 2 skipped,
lint clean**, and `catalog import` leaves both CSVs byte-identical — the 271
`taxonomy_rule` and 244 `manual` rows are untouched, as the merge ranks
guarantee: a fetch now arrives at rank 3 and loses to both.

**Two things the plan did not foresee, found by the tests rather than by
reading.**

`catalog fetch --family` had become a filter over a field discovery no longer
sets, so it would have matched nothing whatever the user typed — silently, with
exit 0 and "no products". A family is a fact the catalog holds, so the CLI now
resolves `--family` to crawl selectors out of `products.csv`, the way `--batch`
already did. It is strictly better than what it replaced: `--family messaging`
is three requests instead of 700, and a family with no products fails loudly
instead of crawling everything to find nothing. `discover()` lost the parameter
entirely, and the test fake's signature was narrowed to match so the CLI cannot
quietly start passing one again.

Rejecting an undeclared family had to be **gated on the BU having declared any**.
A root with no `taxonomy.yaml` — a fresh checkout, and most of `test_cli.py` —
declares nothing, so validating against it refused every key and turned the
guard into a blanket refusal. An empty reference means unconfigured, not "every
family is a typo".

**The retired inference is kept as advice rather than deleted.** A matched
rule's `family` key is returned as `family_rule_hint` and printed by `catalog
triage` beside the slug — 56 of the 154 unclassified products get one. Throwing
it away would have made a 154-product triage start from nothing, when the
cheapest thing to hand a reviewer is a name to agree or disagree with. It is
never written to the catalog, and the test asserts exactly that: the suggestion
appears and the row stays `unclassified`.
