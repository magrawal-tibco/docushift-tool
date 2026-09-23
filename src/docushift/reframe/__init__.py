"""Stage 6b: granular Flare topics into fewer, larger, maintainable pages.

A MadCap Flare topic is an authoring unit, not a reading unit. The reference set
(EMS 10.5.1) is 1,441 topics with a median of 107 words -- once Markdown becomes
the permanent source, that is 1,441 files a writer has to keep in step. Reframe
merges them by subtree, each former topic becoming an anchored `##` section, and
hands the pages it could not decide about to a human.

Three things shape the package:

- **It is its own stage, not logic inside the converter.** It carries editorial
  policy -- cap values, boundary rules, per-set TOC adapters -- that will be tuned
  repeatedly, and every tuning pass touching Stage 5 is the wrong blast radius. It
  also has to be runnable on its own against a frozen `output/` tree, because that
  fast loop is most of how the boundaries get judged.
- **It never writes to its input** (requirements C4). `output/` in, `reframed/`
  out. The merge is irreversible once the pages are hand-edited and the URLs are
  published; until then it must cost one re-run to undo.
- **The engine gate is inside the stage** (C2), not only in the selection.

Read `docs/REFRAME-REQUIREMENTS.md` first -- it defines what the merge does and
what the acceptance checks are. `docs/REFRAME-INTEGRATION-PLAN.md` covers how it
lands here, and `docs/planning.md` Phase 20 records the two places the specs and
this repository disagreed and what was done about it.
"""

from docushift.reframe.driver import (
    REFRAMABLE_ENGINES,
    ReframeOutcome,
    Reframer,
    ReframeResult,
    ReframeStats,
)
from docushift.reframe.policy import ReframePolicy, policy_for

__all__ = [
    "REFRAMABLE_ENGINES",
    "ReframeOutcome",
    "ReframePolicy",
    "ReframeResult",
    "ReframeStats",
    "Reframer",
    "policy_for",
]
