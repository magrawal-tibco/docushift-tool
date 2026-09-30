"""The filename a page publishes under, built from its title.

**The filename is the URL.** AEM generates the published address from the TOC
chain, one segment per node, each segment that node's lowercased filename cut at
50 characters. So a page's name is not an implementation detail a reader never
sees; it is the address they read, paste and bookmark.

Names came from the *source* filename until Phase 29, and MadCap truncates its
own filenames at 20 characters. Measured over the merged corpus: **428 of 1,700
pages had a filename that disagreed with their own title** -- `schema` for
"Schema Resource", `attributes-panel-1` for "Attributes Panel" -- and one was
actively wrong, publishing a page titled *Upgrading to Release 5.13.0* as
`upgrading-to-release-5-12-4.md`. A further 33 exceeded 50 characters.

**Not `utils/slug.py`, and the split is deliberate.** That module names
repositories and workspace folders from catalog values, where a 50-character cut
would be wrong and dropping "the" from a product name would be worse. This one
names pages from prose titles. One function serving both is how each of them
gets broken by a change made for the other; the same argument keeps
`utils/anchors.py` separate again, because an anchor keeps its dots and a
filename does not.
"""

import re
import unicodedata

#: The cut AEM applies per URL segment. A name at or under it round-trips, so the
#: filename and the URL leaf are the same string and `whereis` is a lookup rather
#: than a simulation.
MAX_SEGMENT = 50

#: Dropped before anything else, so a title may lose them without gaining a
#: separator: "Developer's Guide" is `developers-guide`, never `developer-s-guide`.
_STRIPPED = str.maketrans({char: None for char in "'’‘\"“”"})

#: Deleted before the NFKD fold, which would otherwise decompose `™` to the
#: letters "TM" and leave `tibco-emstm`.
_SYMBOLS = str.maketrans({char: None for char in "™®©℠"})

#: A literal escape that survived an authoring tool: `u0027`, `'`, `&#39;`.
#: The corpus publishes `_section_developeru0027s_guide`, which is this, unhandled.
#:
#: Narrowed to the Latin-1 and General Punctuation blocks rather than any four
#: hex digits. `u([0-9a-f]{4})` also matches the tail of a real word -- `ubuntu`
#: followed by a digit, `u0041` in an API reference -- and silently replacing
#: those would corrupt a title to fix an escape.
_ESCAPE = re.compile(r"\\?u(00[0-9a-fA-F]{2}|2[0-9a-fA-F]{3})|&#x?([0-9a-fA-F]+);")

_NON_ALNUM = re.compile(r"[^a-z0-9]+")

#: Dropped first when a name is too long, because they carry the least and are
#: the most predictable to a reader scanning a URL. Never the first word: an
#: address beginning `/guide` reads worse than one beginning `/the-guide`.
_STOPWORDS = frozenset({"a", "an", "the", "of", "for", "to", "and", "in", "on", "with"})

#: Edit history a writer left in a *filename*. Only ever stripped from a fallback
#: stem -- a title that genuinely says "New" keeps it, and `Configuring HTTPS
#: updated` as a title is a word the writer chose rather than a revision marker.
_HISTORY = re.compile(r"(?:^\d+[-_]+)|(?:[-_]+(?:updated|new|old|copy|\d)$)", re.IGNORECASE)

#: A slug that names nothing on its own. Prefixed with its parent, so a reader
#: gets `/installation-overview` and not `/overview` -- and so that the twenty
#: pages titled "Overview" in one doc set do not all collide.
GENERIC = frozenset({
    "overview", "introduction", "summary", "services", "requirements",
    "before-you-begin", "prerequisites", "about", "reference", "examples",
})


def looks_like_a_filename(title: str) -> bool:
    """Whether a TOC "title" is really a stem somebody forgot to write out.

    `Know_the_Basics` is the shape: underscores and no spaces. Slugging it would
    produce a passable name by accident, but the *fallback* stem is the honest
    source and may carry history tokens worth stripping.
    """
    stripped = title.strip()
    return bool(stripped) and " " not in stripped and "_" in stripped


def normalize(value: str) -> str:
    """A title reduced to the characters a slug may contain, before any cutting."""
    text = _ESCAPE.sub(lambda m: chr(int(m.group(1) or m.group(2), 16)), str(value))
    text = unicodedata.normalize("NFKC", text)
    # NBSP and the narrow/figure spaces authoring tools emit. NFKC folds most
    # of them; this covers the ones it leaves, written as escapes so the rule
    # survives a copy-paste of this file into an editor that eats them.
    text = re.sub("[    ]", " ", text)
    text = text.translate(_SYMBOLS).translate(_STRIPPED)
    text = text.replace("&", " and ")
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return _NON_ALNUM.sub("-", folded.lower()).strip("-")


def shorten(slug: str, limit: int = MAX_SEGMENT, separator: str = "-") -> str:
    """`slug` at or under `limit`, losing as little meaning as possible.

    Three steps, in order of how much a reader loses. Drop stopwords, keeping the
    first word whatever it is. Then cut at the last separator boundary that fits,
    so the name ends on a whole word. Only a single word longer than the limit is
    ever cut mid-word -- and a name never ends on a separator, which would read
    as a truncation the platform then hides.
    """
    if len(slug) <= limit:
        return slug

    words = slug.split(separator)
    kept = [words[0]] + [word for word in words[1:] if word not in _STOPWORDS]
    slug = separator.join(kept)
    if len(slug) <= limit:
        return slug

    cut = slug[:limit]
    boundary = cut.rfind(separator)
    return (cut[:boundary] if boundary > 0 else cut).rstrip(separator)


def slugify(title: str, fallback_stem: str = "", *, separator: str = "-",
            limit: int = MAX_SEGMENT) -> str:
    """The filename stem for one page. Deterministic, and at most `limit` long.

    The title is the source of truth; `fallback_stem` is used only when the title
    is empty or is itself a filename, and it alone has edit-history tokens
    stripped -- `1__Copy_Files_Before_Installation` and `Prior_to_Upgrade_` are
    real corpus names, and a `Configuring_HTTPS_updated` that a writer typed as a
    *title* is a word they meant.
    """
    source = title.strip()
    from_stem = not source or looks_like_a_filename(source)
    if from_stem:
        source = _HISTORY.sub("", str(fallback_stem).strip())

    slug = normalize(source)
    if from_stem:
        # The history pattern is anchored, so a stem carrying two tokens
        # (`Prior_to_Upgrade_1`) needs a second look once the first is gone.
        slug = _HISTORY.sub("", slug)
    if separator != "-":
        slug = slug.replace("-", separator)
    return shorten(slug, limit, separator)


def qualify(slug: str, parent: str, *, separator: str = "-",
            limit: int = MAX_SEGMENT) -> str:
    """`slug` prefixed with its parent, for a collision or a generic name.

    The parent is shortened first rather than the slug, because the slug is the
    thing the page is actually about: `installation-guide` + `overview` losing
    characters should lose them from `installation-guide`.
    """
    if not parent:
        return slug
    room = limit - len(slug) - len(separator)
    if room < 1:
        return slug
    return f"{shorten(parent, room, separator)}{separator}{slug}"
