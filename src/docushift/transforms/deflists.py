"""Definition lists that carry their vocabulary in `class=`, not in the tag.

`markdown.py` has emitted `**term**` for a `<dt>` since Phase 5b and does it
correctly. The corpus's Flare-from-DITA output does not use the tag:

    <div class="dl">
      <div class="dlentry"><span class="dt">Scalability</span>
        <div class="dd">The biggest advantage of using ActiveSpaces is ...</div>
      </div>
    </div>

`div` is in `markdown._TRANSPARENT` and `span` is not a block, so the term falls
into the loose-inline run and is published as a bare sentence sitting above its
own definition. Seven of them do exactly that on the merged ActiveSpaces
*Concepts* page.

**Measured, 2026-09-29:** 146 files carry `<span class="dt">` (ActiveSpaces 119,
EMS 24, DataSynapse 3) and 11 carry `<div class="dt">`. Against 18,848 files that
use the real tag and already convert correctly.

**Retagged, never re-styled.** This rewrites `span.dt`/`div.dt` into a real
`<dt>` and hands the result to the branch that already exists. Emitting `**term**`
from here instead would give one corpus two definition-list renderers, which is
the failure `markdown.py`'s own docstring was written to prevent.

**A `dlentry` may hold more than one `dd`, and a `dd` may open with a bold run of
its own.** ActiveSpaces 5.2.0 has 97 `div.dd` against 84 terms; one of the extra
definitions begins `<b>Persistence on Nodes</b>`. That is authored content inside
a definition, not a second term, and nothing here touches it.

**Two near-misses that are already right.** Streaming's 2,892 `<span class="term">`
files are DocBook's `<dt><span class="term">...</span></dt>` -- real tag, already
bold. EMS's 1,536 `<span class="varname">` files are an inline role in running
prose, not a term. Neither is a definition list and neither is matched: the walk
starts from a `.dl` container and descends, so a class token has to be *inside a
definition list* to mean anything here.
"""

from bs4 import Tag

# The wrapper this starts from. Everything else is reached by descending, so a
# stray `class="dd"` elsewhere on the page is not a definition of anything.
_LIST = "dl"
_ENTRY = "dlentry"
_TERM = "dt"
_DEFINITION = "dd"


def _classed(tag: Tag, token: str) -> bool:
    classes = tag.get("class") or []
    return token in classes


def normalize(container: Tag) -> int:
    """Retags class-named definition lists in place. Returns the terms recovered."""
    lists = [tag for tag in container.find_all(class_=_LIST) if tag.name != _LIST]
    terms = 0
    for wrapper in lists:
        for tag in wrapper.find_all(True):
            if _classed(tag, _TERM) and tag.name != _TERM:
                tag.name = _TERM
                terms += 1
            elif _classed(tag, _DEFINITION) and tag.name != _DEFINITION:
                tag.name = _DEFINITION
        # Unwrapped last, so the loop above still sees the entries it descends
        # through. `dlentry` has no Markdown counterpart -- the pairing it carries
        # is positional in GFM -- and leaving it as a `div` would be harmless but
        # would put a transparent container between the `dl` and its own children.
        for entry in wrapper.find_all(class_=_ENTRY):
            if entry.name != _LIST:
                entry.unwrap()
        wrapper.name = _LIST
    return terms
