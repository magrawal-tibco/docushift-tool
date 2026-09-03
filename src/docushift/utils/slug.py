"""Slug and workspace-folder-name helpers.

The one non-obvious rule here is the **family workspace folder**,
`{locale}-{bu}-{family}` (e.g. `en-us-tibco-data-management`). That shape is
inherited from the predecessor `html-to-md` project, where the same string doubles
as the name of the publishing repository a family is destined for -- keeping the
working folder and the eventual repo identically named is what makes the hand-off
at Stage 7 a copy rather than a translation.

Note that `family` keys in `taxonomy.yaml` are underscored (`data_management`)
because they are YAML identifiers, while folder names are hyphenated. `slugify`
is the single place that conversion happens, so the two conventions cannot drift.
"""

import re
import unicodedata

_NON_ALNUM = re.compile(r"[^a-z0-9]+")

# Deleted before the NFKD fold below, not after. NFKD gives these a *compatibility*
# decomposition -- U+2122 becomes the letters "TM" -- so folding first would turn
# `TIBCO EMS™` into `tibco-emstm`. Nearly every product name in the catalog carries
# one of these, so this is the common case, not an edge case.
_SYMBOLS_TO_DROP = str.maketrans({char: None for char in "™®©℠"})


def slugify(value: str) -> str:
    """Lowercases and hyphenates a value into a filesystem- and URL-safe slug.

    Trademark symbols are dropped and accented characters folded to ASCII, so
    `TIBCO EBX®` and `ibi™ WebFOCUS®` produce `tibco-ebx` and `ibi-webfocus`
    rather than leaking a stray separator or a literal `tm` into a folder name.
    """
    stripped = str(value).translate(_SYMBOLS_TO_DROP)
    folded = unicodedata.normalize("NFKD", stripped).encode("ascii", "ignore").decode("ascii")
    return _NON_ALNUM.sub("-", folded.lower()).strip("-")


def family_folder(locale: str, bu: str, family: str) -> str:
    """The workspace folder name for one family, e.g. `en-us-tibco-messaging`.

    Raises on an empty component rather than producing a name with a doubled or
    trailing separator: `en-us-tibco-` would be silently created on first download
    and then quietly collect every unclassified product.
    """
    parts = {"locale": slugify(locale), "bu": slugify(bu), "family": slugify(family)}
    empty = sorted(name for name, slug in parts.items() if not slug)
    if empty:
        raise ValueError(f"Cannot build a family folder name with empty {', '.join(empty)}")
    return f"{parts['locale']}-{parts['bu']}-{parts['family']}"
