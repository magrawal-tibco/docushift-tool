"""Stage 6b: the `version.yml` drop-down, assembled rather than regenerated.

One file per doc-class folder, listing the product's active versions newest
first. Four rules carry it, and three of them are rules about what the file is
*not* built from:

- **Not from the run's own write list.** `sync` takes the same `--product` /
  `--version` scope options `convert` does, so a scoped run touches one version
  out of thirty-eight. Building the list from what this run wrote would rewrite a
  38-entry drop-down down to one and unlink the rest -- and report success. The
  rows come from the doc-class directory *after* the copy, intersected with the
  catalog's active rows: the disk says which versions are published, the catalog
  says which of them are still current. (`architecture.md` §6.6. This is §6.2.3's
  `archives/` rule in reverse, and for the reverse reason: there the directory is
  a subset of the truth, here it is a superset.)
- **Not from the previous file.** AEM's schema permits a hand-written row with an
  absolute URL, so the file is *read* before it is written and any row DocuShift
  is not entitled to own is carried through verbatim in its original position.
  Entitlement is narrow on purpose -- see `merge` -- because the cost of the two
  mistakes is not symmetric: a stale row is a visible wart that `validate` can
  name, and a deleted row is somebody's only copy.
- **Not from a lexical sort.** `10.4.0` outranks `9.3.0`, which string order gets
  backwards, and the largest product carries 38 active versions.
- **Not from two date formats.** Measured over the 1,762 active rows on
  2026-09-15: **1,377 ISO, 372 epoch-millisecond, 13 empty**. The two formats
  `architecture.md` §6.2.3 documents were measured on *archived* `GA_date` and do
  not cover this column; 372 rows render as garbage without the third parser.

A file that will not parse is left entirely alone and named in the run report.
Overwriting it would destroy whatever a human put there, and the tool cannot tell
an intentional addition from a typo -- so it does not adjudicate.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml

from docushift.models import ProductVersion
from docushift.utils.csvio import natural_version_key, normalize_date
from docushift.utils.slug import is_numeric_version, version_segment
from docushift.utils.templating import template

# A row DocuShift could have written: one root-relative segment and nothing else.
_BARE_SEGMENT = re.compile(r"^/[^/]+$")


@dataclass(frozen=True)
class VersionRow:
    """One entry of the drop-down. `title` and `path` are AEM's two keys."""

    title: str
    path: str


# -- dates ---------------------------------------------------------------------


def release_month(value: str | None) -> str:
    """`2026-02-06` or `1703548800000` -> `Feb 2026`. Unparseable or empty -> `""`.

    Month precision, because that is what the title shows and what the *archived*
    side of the catalog has; synthesizing a day from an epoch would claim a
    precision one of the two formats does not carry. The epoch is read by
    `normalize_date`, in UTC and within its year range, so the same catalog does
    not render a different month on two machines, and an epoch outside the range
    falls through to the undated branch rather than rendering 1970 as data.
    """
    text = str(value or "").strip()
    if not text:
        return ""
    iso = normalize_date(text)
    for fmt in ("%Y-%m-%d", "%B %Y", "%b %Y"):
        try:
            return datetime.strptime(iso, fmt).strftime("%b %Y")
        except ValueError:
            continue
    return ""


def title_for(version: ProductVersion) -> str:
    """`10.4.0 (Feb 2026)`, or `10.4.0` when the row has no usable date.

    The version string is the catalog's, verbatim -- not trimmed to a marketing
    two-part form. `10.4.0` and `10.4.1` are routinely both active and both would
    render as `10.4`, which is a drop-down with two identical entries.
    """
    month = release_month(version.release_date)
    return f"{version.version} ({month})" if month else version.version


# -- assembly ------------------------------------------------------------------


def listed(version: ProductVersion) -> bool:
    """Whether a catalog row belongs in the drop-down once its folder is published.

    Active rows, and **archived rows marked for migration** (Phase 34, R10-01).
    `sync` selects what `download` selects, and that includes an archived row
    whose `convert_eligible` is true -- 88 of them on 45 products when this was
    measured. Such a version is placed like any other, so leaving it out of the
    drop-down published folders no page links to; for `tibco-designer` 5.10.0 that
    was the product's only content. An archived row nobody marked stays out, as
    §6.2.3 has it: its history is the archives index.
    """
    return not version.is_archived or version.convert_eligible


def ordered(versions: Iterable[ProductVersion]) -> list[ProductVersion]:
    """Newest first by version, with non-numeric strings last in plain order.

    The drop-down's order and the archives index's, from one function so the two
    cannot drift apart (Phase 34, R10-15).
    """
    rows = list(versions)
    numeric = sorted(
        (v for v in rows if is_numeric_version(v.version)),
        key=lambda v: natural_version_key(v.version),
        reverse=True,
    )
    trailing = sorted(
        (v for v in rows if not is_numeric_version(v.version)),
        key=lambda v: v.version.lower(),
    )
    return [*numeric, *trailing]


def generated_rows(versions: list[ProductVersion], present: set[str]) -> list[VersionRow]:
    """The catalog's listed rows for one product (`listed`), narrowed to what is on disk.

    `present` is the set of directory names the doc-class folder holds. A version
    the catalog lists but this target has never been synced is absent rather than
    listed pointing at nothing. A directory whose row is no longer `listed` -- a
    version archived after it was published -- is absent too; its folder stays on
    disk, untouched, and `validate` names it (`DROPDOWN_INCONSISTENT`).

    Non-numeric strings sort last (`is_numeric_version`). Re-measured 2026-09-15:
    the 20 that exist sit on 20 distinct products, one each, and only 4 of those
    products are multi-version -- so in 16 drop-downs the artifact *is* the whole
    list and "sorts last" is invisible. The run report is the only place they
    surface, which is why `VERSION_NOT_NUMERIC` is a warning and not a note.
    """
    selected = [v for v in versions if listed(v) and version_segment(v.version) in present]
    return [
        VersionRow(title=title_for(v), path=f"/{version_segment(v.version)}")
        for v in ordered(selected)
    ]


def parse(text: str) -> list[VersionRow] | None:
    """Reads an existing `version.yml`. `None` means "do not touch this file".

    `None` covers a YAML error *and* a file whose shape is not the contract --
    both mean the same thing here, which is that something other than DocuShift
    wrote it and this code cannot safely rewrite it.
    """
    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError:
        return None
    if document is None:
        return []
    if not isinstance(document, dict):
        return None
    entries = document.get("versions")
    if entries is None:
        return []
    if not isinstance(entries, list):
        return None
    rows = []
    for entry in entries:
        if not isinstance(entry, dict) or "path" not in entry:
            return None
        rows.append(VersionRow(title=str(entry.get("title", "")), path=str(entry["path"])))
    return rows


def merge(existing: list[VersionRow], generated: list[VersionRow], owned: set[str]) -> list[VersionRow]:
    """Puts the generated block back where the old one was, keeping everything else.

    `owned` is the set of paths this run is entitled to rewrite: one per version
    folder on disk, plus one per active catalog version, both as `/{segment}`. A
    row outside that set survives -- an absolute URL, a path into another tree, a
    bare segment naming something nobody recognizes -- and it keeps its side of
    the generated block, so a hand-written "Latest" entry written above the list
    stays above it.

    The entitlement is deliberately narrow and its failure mode is deliberately
    one-sided. A version dropped from *both* the catalog and the disk leaves a row
    that nothing regenerates and nothing removes; `validate` names a row resolving
    to no directory (§8.4). The other direction -- guessing that an unrecognized
    row is ours and deleting it -- is somebody's only copy, which is why this rule
    exists at all.
    """
    if not existing:
        return list(generated)
    head: list[VersionRow] = []
    tail: list[VersionRow] = []
    replaced = False
    for row in existing:
        if _normalize(row.path) in owned:
            replaced = True
            continue
        (tail if replaced else head).append(row)
    return [*head, *generated, *tail]


def owned_paths(present: set[str], versions: list[ProductVersion]) -> set[str]:
    """The `/{segment}` strings `merge` may rewrite: on disk, or `listed` in the catalog."""
    active = {version_segment(v.version) for v in versions if listed(v)}
    return {f"/{segment}" for segment in (present | active) if segment}


def _normalize(path: str) -> str:
    """Compares a written `path` against `owned_paths`, tolerating a missing slash.

    Only a bare root-relative segment is normalized. An absolute URL and a
    multi-segment path are returned as they were found, so neither can be coerced
    into looking like a row DocuShift wrote.
    """
    text = str(path).strip().rstrip("/")
    if not text or "://" in text or "/" in text.strip("/"):
        return text
    return text if _BARE_SEGMENT.match(text) else f"/{text}"


def render(rows: list[VersionRow], templates: Path) -> str:
    """The file, from rows already ordered and already merged."""
    return template(templates, "version.yml.j2").render(rows=rows)
