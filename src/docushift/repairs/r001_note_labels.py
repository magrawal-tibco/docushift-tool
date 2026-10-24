"""R001: notes show their label on AEM (Phase 56, DOCOPS-250).

AEM reads a GitHub alert, `> [!NOTE]`, as an empty key reference, so the reader got
the note with no "Note" label. The converter writes `> **Note:**` since Phase 56;
this rewrites the trees written before it, with `callouts.fix_markdown` -- the same
rule, so a repaired page reads exactly as a fresh conversion would.
"""

from docushift.repairs import Repair, register
from docushift.transforms import callouts


def detect(text: str) -> int:
    """Alert markers outside fenced code -- what `fix` would rewrite."""
    return callouts.fix_markdown(text).markers


def fix(text: str) -> tuple[str, int]:
    fixed = callouts.fix_markdown(text)
    return fixed.text, fixed.markers


R001 = register(Repair(
    id="R001",
    title="Notes show their label on AEM (> [!NOTE] -> > **Note:**)",
    ticket="DOCOPS-250",
    # POSIX ERE for `git grep -E`: `[[:blank:]]`, because `\t` inside brackets is a
    # backslash or a "t" there, not a tab. The line may end `\r` in a CRLF checkout,
    # which `[[:blank:]]` does not match -- hence `[[:space:]]*$` at the end
    # (2026-10-23: a CRLF file read as having no notes at all). An optional list
    # marker and any spacing between `>`s, as `callouts._QUOTE` (2026-10-25).
    pattern=(r"^[[:blank:]]*([-*+][[:blank:]]+|[0-9]+[.)][[:blank:]]+)?(>[[:blank:]]*)+"
             r"\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\][[:space:]]*$"),
    detect=detect,
    fix=fix,
    confirm="VERIFY_PUBLISHED_CALLOUT_UNRENDERED",
    phase="Phase 56",
))
