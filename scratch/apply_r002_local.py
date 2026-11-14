"""Apply R002 (DOCOPS-360) to published repos without touching versions.csv or state.db.

`docushift repair apply` records its run in config/versions.csv and cache/state.db;
this only rewrites the Markdown, so it can run while another batch owns those files.

    python scratch/apply_r002_local.py REPO [REPO ...] [--dry-run]

Candidates come from `git grep -l -E` with R002's pattern over `en-us/*.md`; each
is fixed with R002's own `fix`, keeping its bytes (BOM, line endings) apart from the
rewrites, and written only when it changed.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from docushift.repairs.r002_escapes import R002

BOM = b"\xef\xbb\xbf"


def candidates(repo: Path) -> list[Path]:
    done = subprocess.run(
        ["git", "-C", str(repo), "grep", "-l", "-z", "-E", R002.pattern, "--", "en-us/*.md"],
        capture_output=True,
    )
    if done.returncode not in (0, 1):
        raise RuntimeError(done.stderr.decode("utf-8", "replace"))
    return [repo / name for name in done.stdout.decode("utf-8").split("\0") if name]


def apply(repo: Path, dry_run: bool) -> tuple[int, int, list[str]]:
    files = changes = 0
    problems: list[str] = []
    for path in candidates(repo):
        raw = path.read_bytes()
        bom = raw.startswith(BOM)
        try:
            # No newline translation: `fix` keeps \r\n and \n as they are.
            text = raw[len(BOM) if bom else 0:].decode("utf-8")
        except UnicodeDecodeError as error:
            problems.append(f"{path.relative_to(repo)}: not UTF-8 ({error})")
            continue
        new, count = R002.fix(text)
        if new == text:
            continue
        files += 1
        changes += count
        if not dry_run:
            path.write_bytes((BOM if bom else b"") + new.encode("utf-8"))
    return files, changes, problems


def main(argv: list[str]) -> int:
    dry_run = "--dry-run" in argv
    repos = [Path(arg) for arg in argv if arg != "--dry-run"]
    total_files = total_changes = 0
    for repo in repos:
        files, changes, problems = apply(repo, dry_run)
        total_files += files
        total_changes += changes
        print(f"{repo.name}\t{files}\t{changes}")
        for problem in problems:
            print(f"  ! {problem}")
    print(f"TOTAL\t{total_files}\t{total_changes}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
