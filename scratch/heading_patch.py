"""Phase 76 step 6: carry a re-merge's heading changes onto a repo that has moved on.

Usage:
    python scratch/heading_patch.py OLD NEW REPO [--apply] [--report CSV]

    OLD   copy of reframed/<family>/<product> taken before `reframe --force`
    NEW   reframed/<family>/<product> after it
    REPO  <repo>/en-us/<published folder>/online-help   (on content-fix)

Read-only unless --apply. `sync` is never used for this: the repo carries fixes made
there only (R002, help-menu titles, 301.yml, DOCOPS-374), which a sync would overwrite.

Guarantees, checked per file before anything is written:
  * the page list (.md files) of every version is identical in OLD and NEW, else stop;
  * OLD -> NEW changes only heading and blank lines, else the file is listed, not patched;
  * the repo's own edits are kept: each heading change is placed only where its lines
    sit unedited in the repo (else stop), and the merged file differs from the repo copy in heading and blank lines only, else stop;
  * toc.yml, 301.yml, csh.yml, redirects.yml changes are listed, never applied.
--apply writes all patchable files, or none if any merge conflicts or is unsafe.
"""

from __future__ import annotations

import argparse
import csv
import difflib
import re
import sys
from pathlib import Path

HEADING = re.compile(r"^(#{1,6})(?:\s+(.*?))?\s*#*\s*$")
FENCE = re.compile(r"^ {0,3}(```|~~~)")
LOCAL_ONLY = {"reframe.yml", "rename-map.csv", "review-queue.csv"}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def heading_lines(lines: list[str]) -> list[tuple[int, str] | None]:
    """Per line: (level, normalized text) for a heading outside a code fence, else None."""
    out: list[tuple[int, str] | None] = []
    fenced = False
    for line in lines:
        if FENCE.match(line):
            fenced = not fenced
            out.append(None)
            continue
        m = None if fenced else HEADING.match(line)
        out.append((len(m.group(1)), " ".join((m.group(2) or "").lower().split())) if m else None)
    return out


def only_headings_changed(a: str, b: str) -> bool:
    """True when every line that differs between a and b is a heading or blank."""
    al, bl = a.splitlines(), b.splitlines()
    ah, bh = heading_lines(al), heading_lines(bl)
    sm = difflib.SequenceMatcher(None, al, bl, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        for k in range(i1, i2):
            if ah[k] is None and al[k].strip():
                return False
        for k in range(j1, j2):
            if bh[k] is None and bl[k].strip():
                return False
    return True


def audit(text: str) -> tuple[bool, bool]:
    """(skips a heading level, shows a title twice: heading followed by a deeper one, same text)."""
    hs = [h for h in heading_lines(text.splitlines()) if h]
    skip = any(b[0] > a[0] + 1 for a, b in zip(hs, hs[1:]))
    dup = any(b[0] > a[0] and a[1] == b[1] and a[1] for a, b in zip(hs, hs[1:]))
    return skip, dup


def merge(repo_text: str, old_text: str, new_text: str) -> tuple[str | None, int]:
    """The repo's edits plus OLD->NEW. Returns (text, hunks that could not be placed).

    Not `git merge-file`: it calls two edits a conflict when they merely sit next to
    each other, and a removed duplicate title is usually one blank line above a
    paragraph the repo fixed (R002). Here each OLD->NEW hunk (heading and blank lines
    only, checked by the caller) is placed where its own OLD lines sit unchanged in the
    repo; a hunk whose lines the repo has edited, or that has no unchanged neighbour to
    anchor an insertion, is not placed and the file is refused.
    """
    ol = old_text.splitlines(keepends=True)
    nl = new_text.splitlines(keepends=True)
    rl = repo_text.splitlines(keepends=True)
    where: dict[int, int] = {}  # OLD line -> the same, unedited line in the repo
    for i, j, size in difflib.SequenceMatcher(None, ol, rl, autojunk=False).get_matching_blocks():
        for k in range(size):
            where[i + k] = j + k
    edits: list[tuple[int, int, list[str]]] = []
    missed = 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ol, nl, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        if i1 == i2:  # pure insertion: anchor after the line above, or before the line below
            if i1 - 1 in where:
                at = where[i1 - 1] + 1
            elif i1 in where or i1 == 0:
                at = where.get(i1, 0)
            else:
                missed += 1
                continue
            edits.append((at, at, nl[j1:j2]))
            continue
        span = [where.get(k) for k in range(i1, i2)]
        if None in span or span != list(range(span[0], span[0] + len(span))):
            missed += 1
            continue
        edits.append((span[0], span[-1] + 1, nl[j1:j2]))
    if missed:
        return None, missed
    for start, end, lines in sorted(edits, reverse=True):
        rl[start:end] = lines
    return "".join(rl), 0


def files(root: Path, suffix: str | None = None) -> set[str]:
    return {p.relative_to(root).as_posix() for p in root.rglob("*")
            if p.is_file() and (suffix is None or p.suffix == suffix)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("old", type=Path)
    ap.add_argument("new", type=Path)
    ap.add_argument("repo", type=Path)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()

    versions = sorted(p.name for p in args.new.iterdir() if p.is_dir())
    rows: list[dict[str, str]] = []
    writes: list[tuple[Path, str]] = []
    stop: list[str] = []
    totals: dict[str, list[int]] = {}

    for v in versions:
        old_v, new_v, repo_v = args.old / v, args.new / v, args.repo / v.replace(".", "-")
        if not old_v.is_dir():
            stop.append(f"{v}: no copy in OLD")
            continue
        if not repo_v.is_dir():
            stop.append(f"{v}: not in the repo ({repo_v})")
            continue
        old_md, new_md = files(old_v, ".md"), files(new_v, ".md")
        if old_md != new_md:
            gone, added = sorted(old_md - new_md), sorted(new_md - old_md)
            stop.append(f"{v}: page list moved ({len(gone)} gone, {len(added)} new), "
                        f"e.g. {(gone + added)[:3]}")
            continue

        before = [0, 0]  # pages with a skipped level / a doubled title, in the repo now
        after = [0, 0]
        for rel in sorted(new_md):
            o, n, r = old_v / rel, new_v / rel, repo_v / rel
            repo_text = read(r) if r.is_file() else None
            result_text = repo_text
            status = "unchanged"
            ot, nt = read(o), read(n)
            if ot != nt:
                if not only_headings_changed(ot, nt):
                    status = "listed: re-merge changed more than headings"
                elif repo_text is None:
                    status = "listed: page missing in the repo"
                elif repo_text == ot:
                    result_text, status = nt, "patch"
                else:
                    merged, conflicts = merge(repo_text, ot, nt)
                    if merged is None or conflicts:
                        status = f"STOP: {conflicts} heading change(s) land on lines the repo edited"
                        stop.append(f"{v}/{rel}: heading change on a line the repo edited")
                    elif not only_headings_changed(repo_text, merged):
                        status = "STOP: merged file changes more than headings"
                        stop.append(f"{v}/{rel}: unsafe merge")
                    else:
                        result_text, status = merged, "patch (repo edits kept)"
                if status.startswith("patch") and result_text == repo_text:
                    status = "unchanged (repo already has it)"
                elif status.startswith("patch"):
                    writes.append((r, result_text))
            if repo_text is not None:
                for i, flag in enumerate(audit(repo_text)):
                    before[i] += flag
                for i, flag in enumerate(audit(result_text)):
                    after[i] += flag
            if status != "unchanged":
                rows.append({"version": v, "file": rel, "status": status})
        totals[v] = before + after

        for rel in sorted((files(old_v) | files(new_v)) - old_md - new_md):
            o, n = old_v / rel, new_v / rel
            if o.is_file() and n.is_file() and o.read_bytes() == n.read_bytes():
                continue
            name = Path(rel).name
            status = ("local only (not published)" if name in LOCAL_ONLY
                      else "listed, not applied: anchors or menu changed")
            if name == "rename-map.csv":
                status = "STOP: rename-map changed (page names moved)"
                stop.append(f"{v}/{rel}: rename-map changed")
            rows.append({"version": v, "file": rel, "status": status})

    print(f"{'version':10} {'skip before':>11} {'dup before':>10} {'skip after':>10} {'dup after':>9}")
    for v, (sb, db, sa, da) in totals.items():
        print(f"{v:10} {sb:11} {db:10} {sa:10} {da:9}")
    counts: dict[str, int] = {}
    for row in rows:
        key = row["status"].split(":")[0] if row["status"].startswith(("listed", "STOP")) else row["status"]
        counts[key] = counts.get(key, 0) + 1
    print("\nfiles:", ", ".join(f"{k} {c}" for k, c in sorted(counts.items())) or "none")
    for row in rows:
        if not row["status"].startswith(("patch", "unchanged", "local")):
            print(f"  {row['version']}/{row['file']}: {row['status']}")

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["version", "file", "status"])
            w.writeheader()
            w.writerows(rows)
        print(f"\nreport: {args.report}")

    if stop:
        print("\nSTOPPED, nothing written:")
        for s in stop:
            print("  " + s)
        return 2
    if not args.apply:
        print(f"\ndry run: {len(writes)} repo file(s) would change. Re-run with --apply.")
        return 0
    for path, text in writes:
        with path.open("w", encoding="utf-8", newline="") as fh:
            fh.write(text)
    print(f"\napplied: {len(writes)} repo file(s) changed. Review with git diff, then commit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
