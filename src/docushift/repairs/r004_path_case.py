"""R004: a committed path differs in case from the file on disk (DOCOPS-374, Phase 83).

A link names `resources/images/x.png`, the disk holds `resources/images/x.png`, and
git holds `Resources/Images/x.png`: the publish repos run with `core.ignorecase=true`,
so the index kept the folder spelling of an earlier publish. AEM serves what was
committed and shows a placeholder.

Unlike R001-R003 this does not rewrite text. R002 already sits in these pages, and a
link respelled to the old case would be undone by the next sync (the reframed tree
spells `resources/`). It repairs the index instead: the version folder is re-indexed
from disk (`sync/reindex.py`, which `sync` now does after every placement), so git
records `Resources/Images/x.png -> resources/images/x.png` as a rename.

Only where the disk does not match the link either -- a file on disk in a third
spelling, a folder moved by Phase 80 -- is the link respelled, to the committed
case, and listed. Idempotent: a second apply finds nothing. Confirmed by `validate`'s
`LINK_CASE_UNCOMMITTED`, which asks the same question of the index.
"""

from __future__ import annotations

import subprocess
from collections import Counter, defaultdict
from pathlib import Path

from docushift.repairs import Repair, RepoApplied, register
from docushift.sync.reindex import reindex_case
from docushift.validation import committed
from docushift.validation.links import TargetPaths


def census_repo(repo: Path, ref: str | None = None) -> dict[tuple[str, str], int]:
    """`{(product folder, segment): targets git holds only in another case}`.

    Read from `git ls-tree -r <ref>` and `git grep <ref>` (the index when `ref` is
    None, so a census right after an uncommitted apply reads 0), never the disk.
    """
    rows = committed.case_rows(repo, ref)
    return dict(Counter(committed.key_of(row.target.file) for row in rows))


def _respell(repo: Path, rows: list[committed.CaseRow], dry_run: bool, into: RepoApplied) -> None:
    """Rewrites each row's link to the committed spelling, in place, line by line."""
    by_file: dict[str, list[committed.CaseRow]] = defaultdict(list)
    for row in rows:
        by_file[row.target.file].append(row)
    for file, mine in sorted(by_file.items()):
        path = repo / file
        try:
            text = path.read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            into.failed.append(f"{path}: {exc}")
            continue
        lines = text.splitlines(keepends=True)
        changed = False
        for row in mine:
            index = row.target.line - 1
            after = committed.respelled(row)
            if index >= len(lines) or row.target.raw not in lines[index] or after == row.target.raw:
                into.failed.append(f"{file}:{row.target.line}: {row.target.raw} not found to respell")
                continue
            lines[index] = lines[index].replace(row.target.raw, after, 1)
            changed = True
            into.rewritten.append({"file": file, "line": str(row.target.line),
                                   "before": row.target.raw, "after": after})
        if changed and not dry_run:
            try:
                path.write_bytes("".join(lines).encode("utf-8"))
                subprocess.run(["git", "-C", str(repo), "add", "--", file], check=True,
                               capture_output=True, timeout=600)
            except (OSError, subprocess.SubprocessError) as exc:
                into.failed.append(f"{path}: {exc}")


def apply_repo(repo: Path, folders: list[Path], dry_run: bool = False) -> RepoApplied:
    """Re-index each version folder where the disk matches the links; respell the rest.

    Never commits: the re-index and any respelled page are staged, for review with
    `git diff --cached --stat -M` (renames only, 100%).
    """
    done = RepoApplied()
    held = committed.committed(repo)
    disk = TargetPaths(repo)
    for folder in folders:
        relative = folder.absolute().relative_to(repo.absolute()).as_posix()
        rows = committed.case_rows(repo, None, [relative], held)
        if not rows:
            continue
        on_disk = [row for row in rows if disk.actual(row.target.resolved) == row.target.resolved]
        rest = [row for row in rows if row not in on_disk]
        if on_disk:
            if dry_run:
                done.renamed.extend(sorted({(row.real, row.target.resolved) for row in on_disk}))
            else:
                try:
                    done.renamed.extend(reindex_case(repo, folder))
                except (OSError, subprocess.SubprocessError) as exc:
                    done.failed.append(f"{folder}: re-index failed: {exc}")
                    continue
                held = committed.committed(repo)
                rest = committed.case_rows(repo, None, [relative], held)
        _respell(repo, rest, dry_run, done)
    return done


R004 = register(Repair(
    id="R004",
    title="Committed path differs in case from the file on disk",
    ticket="DOCOPS-374",
    pattern="",
    detect=lambda text: 0,
    fix=lambda text: (text, 0),
    confirm="LINK_CASE_UNCOMMITTED",
    phase="Phase 83",
    scope="repo",
    census_repo=census_repo,
    apply_repo=apply_repo,
))
