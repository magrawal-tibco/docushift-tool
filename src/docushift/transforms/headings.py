"""Heading levels, compacted to the depth the page actually nests to.

`Concepts/Sample-Programs.htm` is authored `h1, h2, h2, h6, h6, h2, h6, h6`. The
`h6` sections are not five levels deep -- they are second-level sections whose
author reached for the tag that was styled the way the page wanted. The walk in
`markdown.py` maps `hN` straight through, so the Markdown inherits the jump, and
`reframe`'s `shift_headings` adds one level to everything and cannot undo it.

**Measured over the emitted Markdown, 2026-09-29: 612 of 24,781 files in
`output/` and 19 of 1,434 in `reframed/` skip at least one level.** Counting raw
`<hN>` in the source instead gives 5,022, of which 4,990 are DocBook admonition
titles -- `<h3>Note</h3>`, `<h3>Caution</h3>` -- that Phase 19 turns into a
callout and never emits as a heading at all. The `.md` is the only honest place
to measure this, which is also why the exit criterion is stated against it.

**The rule is a stack, not a running offset.** Each heading pops every level at
or below its own and pushes itself; the depth of the stack is what it becomes.
`h1,h2,h2,h6,h6,h2,h6,h6` -> `h1,h2,h2,h3,h3,h2,h3,h3`. An offset ("subtract two
from everything after the jump") needs revising at every later heading and can
push one below `h1`; the stack has no offset to get wrong and cannot invert two
headings' relative depth.

**The shallowest heading on the page keeps its own level**, rather than every
page being forced to open at `h1`. 921 DocBook pages legitimately open at `h2`
(`docbook.py` promotes those deliberately, and does it before this runs); a page
that opens at `h2` because its `h1` lives in chrome outside the content container
must not silently acquire a title level it never had. Depth is measured from the
minimum, so a page is renumbered relative to itself and never promoted.

**Known limit, accepted (`planning.md` Phase 27).** Where a page goes deep before
it goes shallow across a gap -- `h1, h4, h2` -- both the `h4` and the `h2` land at
depth 2 and two source levels merge. The source is ambiguous there and every
alternative rule tested produced something worse.

**A heading the engine is going to consume is not a heading**, and `skip` is how
an engine says so. DocBook's admonition label is an `h3.title` inside `div.note`
that `_admonition` deletes on its way to rendering `> [!NOTE]` -- it is still an
`<h3>` in the DOM when this runs, and letting it take a rung would renumber the
real sections around a heading no reader ever sees. It is also the entire reason
the 5,022-file HTML census was wrong. Flare, DITA and WebWorks carry their
admonition labels in an attribute, a `span` and a table cell respectively, so
none of the three passes a predicate.

Only the tag name changes. Text, order, `id` and therefore every slug and every
`#fragment` that resolves today are untouched, which is why this runs on the DOM
and not over the emitted Markdown -- a regex over the body cannot tell a heading
from a `# comment` inside a shell fence (`reframe/pages.py` §1).

**WebWorks has no `<hN>` at all**, which is why the rule is exported as `compact`
as well as applied by `normalize`. Its headings are `div.N1Heading`,
`div.N3Syntax`, `div.MinorHead` -- the level is in the class name and the engine
reads it in `block_override` (§5.3.7). Retagging those divs into real headings
here would route them through the generic branch, which hoists an `<a id>` out of
the heading line and would therefore move slugs that resolve today. So WebWorks
keeps its own path and borrows the arithmetic.
"""

from collections.abc import Callable, Sequence

from bs4 import Tag

_LEVELS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}

# GFM has no `h7`. Unreachable given the rule -- the stack holds distinct levels
# drawn from 1..6, so depth can never exceed 6 minus the minimum, plus one -- but
# stated rather than assumed, because the cost of being wrong is a literal `#######`
# in published output.
_DEEPEST = 6


def is_empty(tag: Tag) -> bool:
    """A heading that will emit nothing, so it must not take a rung.

    `markdown.Renderer._block` drops a heading whose inline run is blank, keeping
    only any anchor it carried. Letting one hold a level is not a cosmetic waste:
    `tibco-administrator-enterprise-edition`'s `admin_server.4.063` carries an
    empty `N3Heading` between its title and its first section, and it is the whole
    reason that page still read `#` then `###` after the first cut of this.

    An image counts as content. GFM renders `# ![Logo](a.png)`, so a heading whose
    only child is an `<img>` is a heading with something in it.
    """
    return not tag.get_text(strip=True) and tag.find("img") is None


def compact(levels: Sequence[int]) -> list[int]:
    """One page's heading levels in order, renumbered by nesting depth.

    The whole rule, and the only copy of it. `[1,2,2,6,6,2,6,6]` -> `[1,2,2,3,3,2,3,3]`.
    """
    if not levels:
        return []
    base = min(levels)
    stack: list[int] = []
    out: list[int] = []
    for level in levels:
        while stack and stack[-1] >= level:
            stack.pop()
        stack.append(level)
        out.append(min(base + len(stack) - 1, _DEEPEST))
    return out


def normalize(container: Tag, skip: Callable[[Tag], bool] | None = None) -> int:
    """Renumbers `container`'s `<hN>` by nesting depth. Returns how many moved."""
    headings = [tag for tag in container.find_all(list(_LEVELS))
                if isinstance(tag, Tag) and not is_empty(tag) and not (skip and skip(tag))]
    moved = 0
    for tag, target in zip(headings, compact([_LEVELS[tag.name] for tag in headings]), strict=True):
        if target != _LEVELS[tag.name]:
            tag.name = f"h{target}"
            moved += 1
    return moved
