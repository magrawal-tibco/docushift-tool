"""Markdown link shapes more than one reader shares (Phase 44).

A leaf module, so `transforms`, `reframe` and `validation` can all import it
without importing one another.
"""

from __future__ import annotations

import re

#: A linked image, `[![alt](src)](href)`: the outer destination only. The
#: readers' inline pattern cannot hold a `]` in the link text, so it reads the
#: inner image and never sees `href`. `text` is the image's alt text; the
#: destination is `angle` or `bare` (groups 2 and 3), so a reader can edit it in
#: place by name or by number.
MD_LINKED_IMAGE = re.compile(
    r"\[!\[(?P<text>(?:[^\]\\]|\\.)*)\]\([^)\n]*\)\]\(\s*(?:<(?P<angle>[^>\n]*)>|(?P<bare>[^)\s]*))"
    r"""(?:\s+(?:"[^"]*"|'[^']*'|\([^)]*\)))?\s*\)"""
)
