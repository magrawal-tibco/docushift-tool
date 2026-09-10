"""Slug, workspace-folder and publishing-tree name helpers.

Two different names are built here and they are deliberately not the same string:

* the **family workspace folder**, `{locale}-{bu}-{family}` (e.g.
  `en-us-tib-messaging`) -- a local working directory; and
* the **publishing trees**, `{locale}-{bu}-{family}-{suffix}` and its
  `-{resources}` sibling (e.g. `en-us-tib-messaging-userdocs`) -- the names of
  the repositories a family is destined for.

The predecessor `html-to-md` project made them one string, on the grounds that a
working folder named after its repo makes the Stage 7 hand-off a copy rather than
a translation. That stopped being possible when one family started mapping to two
or three trees: there is no single repo name left to match, so `sync` computes the
destination name and the workspace keeps the shorter one. The locale prefix stays
on the workspace regardless -- a localized package is a different ZIP and must not
land on top of the English one.

This module owns the **shape** of those names and nothing else. Every token that
goes into them -- the `repo_slug`, the suffixes, the localized prefix -- arrives as
an argument, from `taxonomy.yaml` or `publishing.yaml` via `ConfigManager`. That is
the same split that already keeps the taxonomy and this module from drifting.

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


def _joined(what: str, **components: str) -> str:
    """Slugifies each component and joins them, refusing an empty one.

    The guard is the reason `en-us-tibco-` never got created: a name with a doubled
    or trailing separator would be silently created on first download and then
    quietly collect every unclassified product. `en-us-tib--userdocs` is the same
    bug with a longer name, so the suffixes go through here too.
    """
    slugs = {name: slugify(value) for name, value in components.items()}
    empty = sorted(name for name, slug in slugs.items() if not slug)
    if empty:
        raise ValueError(f"Cannot build a {what} with empty {', '.join(empty)}")
    return "-".join(slugs[name] for name in components)


def is_primary_locale(locale: str, primary: str) -> bool:
    """Whether `locale` is the one that gets its own named tree.

    The single predicate behind both localized rules -- the `loc-` docs tree and the
    absent resources tree -- so the two cannot disagree about what "localized" means.
    """
    return slugify(locale) == slugify(primary)


def family_workspace_folder(locale: str, bu: str, family: str) -> str:
    """The local workspace folder for one family, e.g. `en-us-tib-messaging`.

    No publishing suffix: this is a working directory, not a repository. Pass the
    `repo_slug` tokens rather than the raw taxonomy keys so the workspace and the
    trees it feeds share a stem.
    """
    return _joined("family workspace folder", locale=locale, bu=bu, family=family)


def docs_tree_name(
    locale: str, bu: str, family: str, *, suffix: str, localized_prefix: str, primary_locale: str
) -> str:
    """The docs repository for one family, e.g. `en-us-tib-messaging-userdocs`.

    Every non-English locale shares **one** tree -- `loc-tib-messaging-userdocs` --
    so the locale segment is replaced by the prefix rather than prepended to it.
    """
    if is_primary_locale(locale, primary_locale):
        return _joined("docs tree name", locale=locale, bu=bu, family=family, suffix=suffix)
    return _joined("docs tree name", prefix=localized_prefix, bu=bu, family=family, suffix=suffix)


def resources_tree_name(
    locale: str, bu: str, family: str, *, docs_suffix: str, resources_suffix: str, primary_locale: str
) -> str:
    """The resources sibling, e.g. `en-us-tib-messaging-userdocs-resources`.

    Derived from `docs_suffix` rather than from a second literal, so renaming the
    docs tree cannot leave the resources tree pointing at a stem nobody publishes.

    **Raises for a non-primary locale.** API references and archives are English
    only, and returning a name for `ja-jp` would hand the caller a repository that
    is never going to exist -- a failure better had here than at push time.
    """
    if not is_primary_locale(locale, primary_locale):
        raise ValueError(
            f"No resources tree exists for locale '{locale}': API references and archives are "
            f"{primary_locale}-only, and localized content publishes to the docs tree alone."
        )
    return _joined(
        "resources tree name", locale=locale, bu=bu, family=family, suffix=docs_suffix, resources=resources_suffix
    )
