"""`rename-map.csv`: which source topic became which published page, and why.

Two jobs, and the second is the one that earns the file.

**A record.** One row per merged page: the source topic that leads it, the path
it was given, its title, its place in the navigation, and the address a reader
will type. The first four are derivable from `reframe.yml`; the fifth is not,
and the fifth is the one somebody checks when a link goes wrong.

**A set of overrides.** A name here is *used*, not merely reported. Read back on
the next run, it pins the page to that path -- so a published URL does not move
because somebody fixed a typo in a title, which is the failure requirements §1
calls permanent ("every layout decision is permanent") and which no amount of
care at the naming end can prevent. `--renormalize` is how a writer asks for the
names to be recomputed anyway, and it exists so that the pinning is a decision
rather than a trap. Both take effect on the next run without `--force` (R9-04):
the approved names are part of the currency check, and `--renormalize` always
re-merges.

**The `shortened` column is the hook for a better name than an algorithm can
write.** `utils/naming` cuts a title at 50 characters by dropping stopwords and
then whole words, and the words it drops are at the end -- which is often where
the meaning is. Measured over 1,505 merged pages: 1,350 names are the full
title, 65 are disambiguated by their folder, and **90 lost words**, among them
`deployment-scenario-running-activespaces` for "Deployment Scenario for Running
ActiveSpaces Processes **as Windows Services**". A human or a model reading the
page would write `activespaces-as-windows-services`.

So those 90 are flagged rather than guessed at. A suggestion pass -- model or
writer -- fills in `new_path`, a reviewer approves it, and the build reads the
approved map as fixed input. **The build itself stays deterministic**, which is
not a preference: the tool asserts byte-identical re-runs, and a name that
varied between runs would be a published address that moved on its own.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, NamedTuple

from docushift.utils.csvio import NotUtf8, read_rows, write_rows
from docushift.utils.longpath import segment_problem

if TYPE_CHECKING:  # pragma: no cover - import cycle at runtime only
    from docushift.reframe.packer import Page
    from docushift.reframe.toc import TocEntry

#: The file, beside `reframe.yml` in the merged tree. Read from the *previous*
#: merge and written fresh by this one, which is what makes a name persist.
RENAME_MAP = "rename-map.csv"


class Unreadable(ValueError):
    """A rename map that exists but cannot be read as a CSV (X1-06)."""

COLUMNS = (
    "old_path",
    "new_path",
    "title",
    "toc_breadcrumb",
    "expected_aem_url",
    "shortened",
    # Phase 50. Last, so a sheet saved before it existed reads unchanged.
    "page_key",
)


class PageKey(NamedTuple):
    """One page of a source topic that leads more than one page (Phase 50).

    Since Phase 47 a topic in two guides leads a page in each, and keyed by the
    source alone the second row of `rename-map.csv` overwrote the first: a name a
    writer gave one of them was dropped without a word. `page` is the page's
    *computed* path, which comes from the converted tree alone and so is the same
    on every run. A topic that leads one page keeps its plain source key, which
    leaves every map written before this phase, and its digest, as it was.
    """

    source: PurePosixPath
    page: str

    def __str__(self) -> str:
        return f"{self.source} ({self.page})"


#: How a page is named in the approved map: its source, or a `PageKey`.
Key = PurePosixPath | PageKey


def page_keys(pages: Sequence[Page]) -> dict[int, Key]:
    """Each page's key, by `id`. Read after `relocate` and before `override`.

    A shared topic's pages are told apart by the path the layout computed for
    them, not the one a pin then gave them.
    """
    leading = Counter(page.topics[0].source for page in pages if page.topics)
    return {
        id(page): (PageKey(page.topics[0].source, str(page.path))
                   if leading[page.topics[0].source] > 1 else page.topics[0].source)
        for page in pages if page.topics
    }


def matched(
    approved: dict[Key, PurePosixPath], keys: dict[int, Key]
) -> tuple[dict[Key, PurePosixPath], dict[Key, PurePosixPath]]:
    """The approved names this layout can use, and the ambiguous ones it cannot.

    A plain row for a topic that now leads several pages could mean any of them,
    and pinning the wrong one moves a published URL, so it pins nothing and is
    returned to be named (`RENAME_MAP_AMBIGUOUS`). A `PageKey` row for a topic
    that leads one page again names that page.
    """
    shared = {key.source for key in keys.values() if isinstance(key, PageKey)}
    usable: dict[Key, PurePosixPath] = {}
    ambiguous: dict[Key, PurePosixPath] = {}
    for key, new in approved.items():
        if isinstance(key, PageKey):
            usable[key if key.source in shared else key.source] = new
        elif key in shared:
            ambiguous[key] = new
        else:
            usable[key] = new
    return usable, ambiguous


def _order(key: Key) -> tuple[PurePosixPath, str]:
    """Sorts plain keys exactly as before Phase 50, so their digest is unchanged."""
    return (key.source, key.page) if isinstance(key, PageKey) else (key, "")


def breadcrumbs(roots: list[TocEntry]) -> dict[PurePosixPath, list[str]]:
    """Each topic's places in the navigation, as ` > ` joined titles, in TOC order.

    For the report rather than for the layout: a reviewer deciding whether
    `overview` is a good name needs to know which Overview it is, and the page
    path alone no longer tells them once folders are slugs. A list, because a
    topic in two guides leads a page in each, and each row shows its own (Phase 50).
    """
    found: dict[PurePosixPath, list[str]] = {}

    def walk(entry: TocEntry, trail: list[str]) -> None:
        here = [*trail, entry.title] if entry.title else list(trail)
        if entry.path is not None:
            found.setdefault(entry.path, []).append(" > ".join(here))
        for child in entry.children:
            walk(child, here)

    for root in roots:
        walk(root, [])
    return found


def rows(
    pages: list[Page],
    trail_of: dict[PurePosixPath, list[str]],
    url_of: Callable[[PurePosixPath], str],
    shortened: set[PurePosixPath],
    keys: dict[int, Key] | None = None,
) -> list[dict[str, str]]:
    """One row per page, keyed on the source topic that leads it.

    Keyed on the *source* rather than on the new path, because the source is the
    stable identity: the new path is precisely the thing a row may change. A
    topic leading several pages adds `page_key` (Phase 50), and its rows take
    its breadcrumbs in page order.
    """
    keys = keys if keys is not None else page_keys(pages)
    seen: Counter[PurePosixPath] = Counter()
    out: list[dict[str, str]] = []
    for page in pages:
        if not page.topics:  # pragma: no cover - a page always leads with a topic
            continue
        first = page.topics[0]
        trails = trail_of.get(first.source, [])
        trail = trails[min(seen[first.source], len(trails) - 1)] if trails else ""
        seen[first.source] += 1
        key = keys.get(id(page), first.source)
        out.append({
            "old_path": str(first.source),
            "new_path": str(page.path),
            "title": first.title,
            "toc_breadcrumb": trail,
            "expected_aem_url": url_of(page.path),
            "shortened": "yes" if first.source in shortened else "",
            "page_key": key.page if isinstance(key, PageKey) else "",
        })
    out.sort(key=lambda row: (row["old_path"], row["page_key"]))
    return out


def write(path: Path, mapping: list[dict[str, str]]) -> None:
    write_rows(path, COLUMNS, mapping)


def load(root: Path) -> dict[Key, PurePosixPath]:
    """The previous merge's approved names: source topic (or `PageKey`) -> page path.

    Absent means no overrides. A row with no `new_path` is a suggestion nobody
    filled in.

    **A file that does not decode raises `Unreadable`** (X1-06), and fails the one
    version rather than reading as `{}`: dropping a writer's names in silence
    would move every published URL they pinned. A sheet Excel saved as ANSI is
    read, through `read_rows`'s Windows-1252 fallback (X2-04); what is left is a
    file in neither encoding, or one the `csv` module refuses.
    """
    path = root / RENAME_MAP
    if not path.is_file():
        return {}
    try:
        found = read_rows(path)
    except OSError:  # pragma: no cover - unreadable on a machine that just wrote it
        return {}
    except NotUtf8 as exc:
        raise Unreadable(str(exc)) from exc
    except csv.Error as exc:
        raise Unreadable(f"{path} does not parse as a CSV ({exc}); save it again as 'CSV UTF-8'") from exc
    overrides: dict[Key, PurePosixPath] = {}
    for row in found:
        old = str(row.get("old_path", "")).strip()
        new = str(row.get("new_path", "")).strip()
        page = str(row.get("page_key", "") or "").strip()
        if old and new:
            overrides[PageKey(PurePosixPath(old), page) if page else PurePosixPath(old)] = PurePosixPath(new)
    return overrides


def refusal(wanted: PurePosixPath) -> str | None:
    """Why a `new_path` cannot be a page in the merged tree, or `None` (X2-03).

    The map invites "a human or a model" to write names, and the path was used
    as typed: `../10.5.0/user-guide.md` overwrote a sibling version's page and an
    absolute path wrote wherever it named. A page path is relative, stays inside
    the tree, and names a Markdown file; each segment is one Windows file name.
    """
    if wanted.is_absolute() or str(wanted).startswith(("/", chr(92))):
        return "an absolute path"
    for part in wanted.parts:
        if (problem := segment_problem(part)) is not None:
            return problem
        if part.endswith((".", " ")):
            return f"a trailing dot or space in {part!r}"
    if wanted.suffix.lower() != ".md":
        return "not a .md page"
    return None


def digest(approved: dict[Key, PurePosixPath]) -> str:
    """A short digest of the approved names, for the currency check (R9-04).

    Over `load`'s mapping rather than the file's bytes: a reordered row or an
    edited `title` cell changes no page's address and must not re-merge a tree,
    while any `new_path` edit must.
    """
    payload = "\n".join(
        f"{key.source}\t{key.page}\t{new}" if isinstance(key, PageKey) else f"{key}\t{new}"
        for key, new in sorted(approved.items(), key=lambda item: _order(item[0]))
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def dumps(approved: dict[Key, PurePosixPath]) -> str:
    """The approved names as text, for the copy `state.db` keeps (X2-02).

    The map lives inside the tree a swap replaces, so it was lost with any swap
    that failed or was killed. The copy is written after every successful merge
    and read only when the file is gone; the file stays the one a writer edits.
    """
    return json.dumps(
        [[str(key.source), key.page, str(new)] if isinstance(key, PageKey) else [str(key), str(new)]
         for key, new in sorted(approved.items(), key=lambda item: _order(item[0]))],
        ensure_ascii=False, separators=(",", ":"))


def loads(text: str) -> dict[Key, PurePosixPath]:
    """`dumps`, read back. Anything unreadable is no copy at all."""
    try:
        pairs = json.loads(text)
    except ValueError:
        return {}
    found: dict[Key, PurePosixPath] = {}
    for entry in pairs if isinstance(pairs, list) else []:
        if not isinstance(entry, list) or not all(isinstance(part, str) and part for part in entry):
            continue
        if len(entry) == 2:
            found[PurePosixPath(entry[0])] = PurePosixPath(entry[1])
        elif len(entry) == 3:
            found[PageKey(PurePosixPath(entry[0]), entry[1])] = PurePosixPath(entry[2])
    return found
