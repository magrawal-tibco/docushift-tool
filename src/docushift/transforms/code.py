"""Code fences.

**Fences are emitted bare**, and that is a measurement rather than a shortcut:
1,565 of Flare's ~1,600 `<pre>` blocks carry no language, DITA's whole corpus has
exactly one language attribute across 864 blocks, and WebWorks has no language
attribute anywhere -- its 104,896 code lines are `div.WCodeLine` siblings against
60 `<pre>` in total. Guessing a language from the content would put a wrong
highlighter on a majority of blocks to get a right one on a handful.

`language` is still a parameter, because an engine that *does* find a declared one
should pass it, and inferring is the only thing forbidden.
"""

import re

# The longest run of backticks anywhere in the block. A fence has to be longer
# than the longest run it contains, or the block ends early and the remainder of
# the code renders as prose -- routine in API documentation, which quotes
# Markdown and shell prompts at each other.
_BACKTICKS = re.compile(r"`+")


def fence(text: str, language: str = "") -> str:
    """One fenced block. Trailing whitespace goes; internal blank lines stay."""
    body = text.replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    longest = max((len(run.group()) for run in _BACKTICKS.finditer(body)), default=0)
    marker = "`" * max(3, longest + 1)
    return f"{marker}{language}\n{body}\n{marker}"


def inline(text: str) -> str:
    """Inline code, with the same fence-length rule and the padding it forces.

    A span that starts or ends with a backtick needs a space inside the delimiters
    as well as a longer delimiter -- `` ` `` alone is ambiguous to every parser.
    """
    body = " ".join(text.split())
    if not body:
        return ""
    longest = max((len(run.group()) for run in _BACKTICKS.finditer(body)), default=0)
    marker = "`" * (longest + 1)
    pad = " " if body.startswith("`") or body.endswith("`") else ""
    return f"{marker}{pad}{body}{pad}{marker}"
