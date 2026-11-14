"""R003: `<samp>` and `<var>` lose their text on AEM (DOCOPS-371).

Staging removes both elements with the words inside them: Mainframe Substation ES
2.14.0's message pages read "The supported codes are,, and". Keeping the tags is
the Digital Platform's fix; this is ours **if AEM cannot keep them**, and it is not
meant to run before that is decided. It rewrites published trees with
`inline_tags.fix_markdown`, the rule the converter applies when
`aem.inline_tags_rewrite` is on, so a repaired page reads as a fresh conversion
with the option on would: a code span or emphasis in prose, `<code>` or `<em>` in
raw HTML, and code left alone.
"""

from docushift.repairs import Repair, register
from docushift.transforms import inline_tags


def detect(text: str) -> int:
    """`<samp>` and `<var>` elements outside code -- what `fix` would rewrite."""
    return inline_tags.fix_markdown(text).count


def fix(text: str) -> tuple[str, int]:
    fixed = inline_tags.fix_markdown(text)
    return fixed.text, fixed.count


R003 = register(Repair(
    id="R003",
    title="<samp>/<var> text dropped on AEM (-> `code` / *em*), for use if AEM cannot keep the tags",
    ticket="DOCOPS-371",
    # POSIX ERE for `git grep -E`: a start tag of either name, either case, followed
    # by a space, `>` or `/` so `<variable>` stays out. Matches in code too; `detect`
    # then counts exactly.
    pattern=r"<([sS][aA][mM][pP]|[vV][aA][rR])([[:space:]>/]|$)",
    detect=detect,
    fix=fix,
    # No `verify` finding names a dropped inline element yet; a staging look at a
    # fixed page is the confirmation.
    confirm="",
    phase="",
    # Off until AEM's answer is in: a census must name it (`--repair R003`).
    optional=True,
))
