"""R002: backslash escapes AEM shows literally, `\\<` and `\\\\` in prose (DOCOPS-360).

AEM does not read CommonMark's backslash escapes in normal text: `\\<clus_name>`
showed as `\\&lt;clus_name>` and `Systems\\\\ArchiverDemo` with both backslashes. The
converter writes `&lt;` and a plain or entity backslash since DOCOPS-360; this
rewrites the trees written before it with `escapes.fix_markdown` -- the same rule, so
a repaired page reads exactly as a fresh conversion would. Front matter, code, raw
HTML and every other escape (`\\*`, `\\_`, `\\[` ...) are left as they are.
"""

from docushift.repairs import Repair, register
from docushift.transforms import escapes


def detect(text: str) -> int:
    """Prose `\\<` and `\\\\` outside code and raw HTML -- what `fix` would rewrite."""
    return escapes.fix_markdown(text).count


def fix(text: str) -> tuple[str, int]:
    fixed = escapes.fix_markdown(text)
    return fixed.text, fixed.count


R002 = register(Repair(
    id="R002",
    title="Backslash escapes show on AEM (\\< -> &lt;, \\\\ -> \\ or &#92;)",
    ticket="DOCOPS-360",
    # POSIX ERE for `git grep -E`: `\\` is one literal backslash there, so this is two
    # backslashes, or a backslash and `<` (not GNU's `\<` word boundary). No line-end
    # anchor, so a CRLF checkout needs no `[[:space:]]` (R001's 2026-10-23 lesson).
    # It matches in code and raw HTML too; `detect` then counts exactly.
    pattern=r"\\\\|\\<",
    detect=detect,
    fix=fix,
    # No `verify` finding names a literal backslash on staging; a staging look at a
    # fixed page is the confirmation for now.
    confirm="",
    phase="Phase 79",
))
