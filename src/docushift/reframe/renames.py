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
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from docushift.utils.csvio import NotUtf8, read_rows, write_rows

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
)


def breadcrumbs(roots: list[TocEntry]) -> dict[PurePosixPath, str]:
    """Each topic's place in the navigation, as ` > ` joined titles.

    For the report rather than for the layout: a reviewer deciding whether
    `overview` is a good name needs to know which Overview it is, and the page
    path alone no longer tells them once folders are slugs.
    """
    found: dict[PurePosixPath, str] = {}

    def walk(entry: TocEntry, trail: list[str]) -> None:
        here = [*trail, entry.title] if entry.title else list(trail)
        if entry.path is not None and entry.path not in found:
            found[entry.path] = " > ".join(here)
        for child in entry.children:
            walk(child, here)

    for root in roots:
        walk(root, [])
    return found


def rows(
    pages: list[Page],
    trail_of: dict[PurePosixPath, str],
    url_of: Callable[[PurePosixPath], str],
    shortened: set[PurePosixPath],
) -> list[dict[str, str]]:
    """One row per page, keyed on the source topic that leads it.

    Keyed on the *source* rather than on the new path, because the source is the
    stable identity: the new path is precisely the thing a row may change.
    """
    out: list[dict[str, str]] = []
    for page in pages:
        if not page.topics:  # pragma: no cover - a page always leads with a topic
            continue
        first = page.topics[0]
        out.append({
            "old_path": str(first.source),
            "new_path": str(page.path),
            "title": first.title,
            "toc_breadcrumb": trail_of.get(first.source, ""),
            "expected_aem_url": url_of(page.path),
            "shortened": "yes" if first.source in shortened else "",
        })
    out.sort(key=lambda row: row["old_path"])
    return out


def write(path: Path, mapping: list[dict[str, str]]) -> None:
    write_rows(path, COLUMNS, mapping)


def load(root: Path) -> dict[PurePosixPath, PurePosixPath]:
    """The previous merge's approved names: source topic -> page path.

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
    overrides: dict[PurePosixPath, PurePosixPath] = {}
    for row in found:
        old = str(row.get("old_path", "")).strip()
        new = str(row.get("new_path", "")).strip()
        if old and new:
            overrides[PurePosixPath(old)] = PurePosixPath(new)
    return overrides


def digest(approved: dict[PurePosixPath, PurePosixPath]) -> str:
    """A short digest of the approved names, for the currency check (R9-04).

    Over `load`'s mapping rather than the file's bytes: a reordered row or an
    edited `title` cell changes no page's address and must not re-merge a tree,
    while any `new_path` edit must.
    """
    payload = "\n".join(f"{old}\t{new}" for old, new in sorted(approved.items()))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def dumps(approved: dict[PurePosixPath, PurePosixPath]) -> str:
    """The approved names as text, for the copy `state.db` keeps (X2-02).

    The map lives inside the tree a swap replaces, so it was lost with any swap
    that failed or was killed. The copy is written after every successful merge
    and read only when the file is gone; the file stays the one a writer edits.
    """
    return json.dumps(sorted([str(old), str(new)] for old, new in approved.items()),
                      ensure_ascii=False, separators=(",", ":"))


def loads(text: str) -> dict[PurePosixPath, PurePosixPath]:
    """`dumps`, read back. Anything unreadable is no copy at all."""
    try:
        pairs = json.loads(text)
    except ValueError:
        return {}
    return {
        PurePosixPath(old): PurePosixPath(new)
        for old, new in pairs if isinstance(old, str) and isinstance(new, str) and old and new
    }
