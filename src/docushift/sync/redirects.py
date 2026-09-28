"""Stage 7: the published 301 map, assembled from the version folders beneath it.

Reframe writes one `redirects.yml` per merged version folder, and its paths are
relative to that folder -- `users-guide/foo.md -> users-guide/bar.md#foo`. That is
the right shape for the *record*: it is auditable beside the pages it describes,
`validate` resolves it against the folder it sits in, and it is byte-identical
across runs. It is the wrong shape for a **served** 301 map, which is a property
of the site rather than of one version directory.

So this module writes a second file, at doc-class level beside `version.yml`, and
it is the same file in the same sense that `version.yml` is the same list as the
directories beside it: two views, neither derivable from the other at serve time.
Three of `sync/versions.py`'s four rules carry over unchanged, for their reasons:

- **Not from the run's own write list.** `sync --version 10.5.1` touches one
  folder out of six. Assembling from what this run wrote would publish a map that
  301s one version and silently drops the other five -- and report success. The
  rows come from the doc-class directory *after* the copy.
- **Not from the previous file.** A row this tool is not entitled to own is
  carried through verbatim in its original position, keys and all. Entitlement is
  narrow -- see `owned_prefixes` -- and the asymmetry is the drop-down's: a stale
  redirect is a visible wart `validate` can name, and a deleted one is a URL that
  now 404s with no record that it ever worked.
- A file that will not parse is left alone and named in the run report.

The fourth does not: ordering is by source path, which is what Reframe already
sorts by, because a redirect map is looked up rather than read.

**The host is not this tool's to know, and the path is.** An empty
`publish_base_url` yields the tree-rooted path with no scheme and no host, which
is `apirefs.published_url`'s rule (6e) and for its reason: a map missing only its
prefix is fixable by search-and-replace once the AEM host is known, and a map that
was never emitted is not recoverable at all. The `.md` extension is kept, because
every relative link inside every published page and every `toc.yml` path carries
it -- a redirect map that guessed otherwise would be the one artifact in the tree
disagreeing with the rest, and wrong in a way search-and-replace could not tell
apart from right.
"""

from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote, urlsplit

import yaml

from docushift.transforms import links

#: The doc-class file this module writes, and the per-version file it reads. The
#: same name at two levels is deliberate: it is one map, published at the level it
#: can actually be served from.
REDIRECTS = "redirects.yml"

HEADER = (
    "# Published 301 map -- assembled by `docushift sync` from the merged trees\n"
    "# beneath this folder (planning.md 20d.1). Rows are regenerated per version\n"
    "# segment; anything else here is left exactly as it was found.\n"
)


def published(base: str, tree_name: str, locale: str, slug: str,
              doc_class: str, segment: str, reference: str) -> str:
    """A version-root-relative reference as the URL it is served at.

    One function for both sides of a row. `from` is the pre-merge published path
    of a topic that lived in the same version folder as the page it moved into, so
    it takes the same prefix -- deriving the two separately is how they come to
    disagree by a segment.

    The path is percent-encoded and the base is not: the base is a URL the config
    validated, and the path is folder names this tool invented.
    """
    path, _, fragment = str(reference).partition("#")
    url = links.emit(f"{tree_name}/{locale}/{slug}/{doc_class}/{segment}/{path}", fragment)
    return f"{base.rstrip('/')}/{url}" if base else url


def prefix(base: str, tree_name: str, locale: str, slug: str,
           doc_class: str, segment: str) -> str:
    """Everything left of a row's own path -- what `owned_prefixes` compares on."""
    return published(base, tree_name, locale, slug, doc_class, segment, "")


def parse(text: str) -> list[dict[str, Any]] | None:
    """Reads an existing map. `None` means "do not touch this file".

    A YAML error and a shape that is not the contract mean the same thing here:
    something other than DocuShift wrote it and this code cannot safely rewrite
    it. Rows are kept as the mappings they were found as, not narrowed to a
    dataclass, so a key this tool has never heard of survives the round trip.
    """
    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError:
        return None
    if document is None:
        return []
    if not isinstance(document, dict):
        return None
    entries = document.get("redirects")
    if entries is None:
        return []
    if not isinstance(entries, list):
        return None
    rows = []
    for entry in entries:
        if not isinstance(entry, dict) or "from" not in entry or "to" not in entry:
            return None
        rows.append(dict(entry))
    return rows


def generated_rows(folder: Path, present: set[str], base: str, tree_name: str,
                   locale: str, slug: str, file_name: str = REDIRECTS,
                   prefix_keys: tuple[str, ...] = ("from", "to"),
                   ) -> tuple[list[dict[str, Any]], list[str]]:
    """Every merged version folder's map, rewritten into served URLs.

    Returns the rows and the paths of any per-version file that would not parse.
    A version folder with no map contributes nothing and is not an error -- that
    is every version that has not opted in to publishing merged, and for
    `301.yml` also every product with no declared origin template.

    `prefix_keys` is which sides are version-root-relative and therefore need the
    prefix. Both, for `redirects.yml`. **`("to",)` for Phase 22's `301.yml`**,
    whose `from` is already an absolute `docs.tibco.com` URL -- prefixing it
    would produce a published path with a live docsite URL embedded in the middle
    of it, which is the one shape that is neither valid nor obviously wrong.
    """
    rows: list[dict[str, Any]] = []
    unparsed: list[str] = []
    doc_class = folder.name
    for segment in sorted(present):
        path = folder / segment / file_name
        if not path.is_file():
            continue
        parsed = parse(path.read_text(encoding="utf-8"))
        if parsed is None:
            unparsed.append(str(path))
            continue
        for row in parsed:
            moved = dict(row)
            for key in prefix_keys:
                moved[key] = published(base, tree_name, locale, slug, doc_class,
                                       segment, str(row[key]))
            rows.append(moved)
    rows.sort(key=lambda row: str(row["from"]))
    return rows, unparsed


def owned_prefixes(present: set[str], base: str, tree_name: str, locale: str,
                   slug: str, doc_class: str) -> list[str]:
    """The URL prefixes this run may rewrite: one per version folder on disk.

    Narrow on purpose. A row whose `from` sits under a version segment published
    here is one this tool wrote and will write again; everything else -- a hand
    added redirect, a row pointing into another product, a legacy URL with no
    version segment at all -- is outside the set and survives untouched.
    """
    return [prefix(base, tree_name, locale, slug, doc_class, segment)
            for segment in sorted(present) if segment]


def merge(existing: list[dict[str, Any]], generated: list[dict[str, Any]],
          prefixes: list[str], key: str = "from") -> list[dict[str, Any]]:
    """Puts the generated block back where the old one was, keeping everything else.

    The drop-down's structure and the drop-down's one-sided failure mode: a row
    for a version that has left both the disk and the merge is regenerated by
    nothing and removed by nothing, and `validate` names it. Guessing that an
    unrecognized row is ours and deleting it is the mistake that has no undo.

    `key` is the side entitlement is read from -- `from` for `redirects.yml`,
    where both sides are ours. **`to` for `301.yml`**, whose `from` is a
    `docs.tibco.com` URL that matches no prefix this tool could own: comparing on
    it would find nothing entitled, regenerate nothing, and append a second copy
    of every row on every run.
    """
    if not existing:
        return list(generated)
    head: list[dict[str, Any]] = []
    tail: list[dict[str, Any]] = []
    replaced = False
    for row in existing:
        if any(str(row.get(key, "")).startswith(known) for known in prefixes):
            replaced = True
            continue
        (tail if replaced else head).append(row)
    return [*head, *generated, *tail]


def render(rows: list[dict[str, Any]], header: str = HEADER) -> str:
    """The file. `sort_keys=False` keeps `from`, `to`, `status` in Reframe's order."""
    body = yaml.safe_dump({"redirects": rows}, sort_keys=False,
                          allow_unicode=True, width=10**6)
    return header + body


def relative_path(url: str, trees: set[str]) -> PurePosixPath | None:
    """A published URL back to a path under the target, or `None` if it is not one.

    Written for `validate`, which has the target and not the config, so it cannot
    know what `publish_base_url` was when the map was rendered. It does not need
    to: whatever the host, the tree name is the first path segment, so an absolute
    URL and the tree-rooted shipped form resolve through one rule. Anything that
    does not start at a published tree is somebody else's row and is left alone --
    the rule the page checker already applies to an absolute link.
    """
    path = unquote(urlsplit(str(url)).path).lstrip("/")
    if not path:
        return None
    parts = PurePosixPath(path).parts
    return PurePosixPath(path) if parts and parts[0] in trees else None
