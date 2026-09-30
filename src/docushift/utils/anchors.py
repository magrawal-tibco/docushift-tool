"""The anchor a heading gets, computed the way the publishing platform computes it.

**AEM ignores the `<a id="...">` markers this tool used to emit and generates its
own anchor from the heading text** -- lowercased, hyphenated, and disambiguated
GitHub-style when a page repeats a heading. Confirmed against a real instance,
2026-09-30. So the anchor is not something the tool chooses; it is something the
tool has to *predict*, and every `#fragment` in every link and every `csh.yml`
value is a bet on getting the prediction right.

Measured on the merged corpus before this module existed: anchors were slugged
from the source *filename*, and agreed with the heading-derived answer for
**7,153 of 18,657 (38%)**. The other ~11,500 named something the platform would
never create, and 94% of internal links carry a fragment -- so the majority of
cross-references in the corpus resolved to the top of a page rather than to the
section they named, with nothing reporting it. That is why this lives in `utils/`
and is imported by both the writer (`reframe`) and the checker (`validation`):
one rule, so the two cannot agree with each other and both be wrong.

**The `-1`/`-2` suffix is positional, and that is a real fragility rather than an
implementation detail.** 400 of 1,700 merged pages repeat a heading -- three
"Location", three "Syntax", three "Examples" on one page is a real example -- and
inserting a section above one of them renumbers every later duplicate, moving a
published anchor. Nothing here can prevent that; the fix, where it matters, is a
writer making the headings distinct.
"""

import re
import unicodedata

_TAG = re.compile(r"<[^>]*>")
# Inline Markdown that renders to nothing in a heading: `**bold**`, `` `code` ``,
# a link's brackets. Removed rather than replaced, so `**Bold** Term` gives
# `bold-term` and not `-bold--term`.
#
# **`_` is deliberately not in this set**, though it is an emphasis marker and
# was in it until Phase 29. It is also a word character to GitHub's rule, which
# keeps it: `TIBCO_HOME` anchors at `tibco_home`, not `tibcohome`. Measured over
# the merged corpus: **3,625 of 32,706 headings contain an underscore and none
# of them uses underscore-emphasis** -- they are environment variables and error
# codes. Stripping it was wrong for 11% of headings and right for none.
_INLINE_MARKUP = re.compile(r"[!\[\]()`*~]")
_DROP = re.compile(r"[^\w\- ]+", re.UNICODE)


def slugify_heading(title: str) -> str:
    """One heading's anchor, before any disambiguation.

    Deliberately *not* `utils/slug.py:slugify`, and the difference is sharper
    than "both lowercase and hyphenate". Punctuation here is **deleted**, not
    replaced by a separator, and `_` survives as a word character -- so
    `Release 10.4.0` anchors at `release-1040` where a directory name would be
    `release-10-4-0`, and `Know_the_Basics` keeps its underscores. Two callers,
    two rules, and conflating them would silently break whichever one lost.

    (An earlier version of this docstring claimed an anchor keeps its dots. It
    does not, and never did; the code below has always dropped them. Corrected
    when a test written against the sentence failed against the function.)
    """
    text = _TAG.sub("", title)
    text = _INLINE_MARKUP.sub("", text)
    text = unicodedata.normalize("NFKD", text).strip().lower()
    text = _DROP.sub("", text)
    return text.replace(" ", "-")


def anchor_run(titles: list[str]) -> list[str]:
    """Anchors for one page's headings, in document order, deduped as AEM dedupes.

    The first occurrence keeps the bare slug and later ones take `-1`, `-2`, …
    Returned as a list rather than a set because position *is* the answer here:
    the caller needs to know which heading got which anchor, not merely which
    anchors exist.

    A heading that slugs to nothing -- punctuation only, or an image -- gets an
    empty string rather than being dropped, so the result stays index-aligned
    with its input.
    """
    seen: dict[str, int] = {}
    out: list[str] = []
    for title in titles:
        base = slugify_heading(title)
        if not base:
            out.append("")
            continue
        index = seen.get(base, 0)
        out.append(base if not index else f"{base}-{index}")
        seen[base] = index + 1
    return out
