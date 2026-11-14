"""Move published product folders to their publish names (Phase 80, DOCOPS-372).

For each product in `config/publish-names.yaml`, finds every repo under the target
that holds `<locale>/<slug>` (the docs repo and its `-resources` sibling, as
`scratch/remove_versions.py` does) and runs `git mv <locale>/<slug> <locale>/<folder>`,
so git and the pipeline see a rename, history kept.

Inside the moved folder, the three maps name the old folder in every row --
`301.yml` and `csh.yml` (`/en-us/<slug>/...`, `/content/dam/.../us/en/<slug>/...`)
and the product-level `redirects.yml` (`us/en/<slug>/...`). Those prefixes are
rewritten to the new folder, which is what `sync` writes next anyway; doing it here
keeps a version `sync` declines to re-publish from pointing at a folder that is gone.
Pages are not touched: the only pages naming the folder are the API-reference links
of four products, which `convert` rewrites (their API prefix changed, so they are
no longer current). The dry run counts them.

Nothing is committed. Run from the DocuShift root (it reads `config/`). Dry run by default:

    python scratch/move_publish_folders.py                      # every product, dry run
    python scratch/move_publish_folders.py --family bw-plugin   # one family
    python scratch/move_publish_folders.py --product <slug> --product <slug>
    python scratch/move_publish_folders.py --family mft --apply
    python scratch/move_publish_folders.py --target C:/github/tibco-docs-aem
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, "src")
from docushift.config import ConfigManager  # noqa: E402

TARGET = "C:/github/tibco-docs-aem"
#: The files in a product folder whose rows name the folder (Phase 68 / 72 / 20d.1).
MAPS = ("301.yml", "csh.yml", "redirects.yml")


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def tracked(repo: Path, rel: str) -> int:
    done = git(repo, "ls-files", "-z", "--", rel)
    return len([name for name in done.stdout.split("\0") if name])


def on_disk(folder: Path) -> int:
    return sum(len(names) for _, _, names in os.walk(folder))


def prefixes(locale: str, slug: str, folder: str) -> list[tuple[str, str]]:
    """Old -> new, every form an address naming the product folder takes in a map.

    Each ends in `/`, so a slug that begins another slug (`...-for-odata` and
    `...-for-odata-services-for-sap-s-4hana`) never matches the longer one.
    """
    language, _, country = locale.partition("-")
    served = f"{country}/{language}" if country else language
    return [
        (f"/{locale}/{slug}/", f"/{locale}/{folder}/"),          # repo-rooted (301.yml, csh.yml)
        (f"/{served}/{slug}/", f"/{served}/{folder}/"),          # DAM path and hosted URL
        (f"{served}/{slug}/", f"{served}/{folder}/"),            # host-less served (redirects.yml)
    ]


def rewrite(text: str, pairs: list[tuple[str, str]]) -> tuple[str, int]:
    count = 0
    for old, new in pairs:
        # The host-less form must start a value: after a space, a quote or a line start.
        pattern = re.escape(old) if old.startswith("/") else r"(?<![\w/.-])" + re.escape(old)
        text, n = re.subn(pattern, new.replace("\\", "\\\\"), text)
        count += n
    return text, count


def read(path: Path) -> str:
    """The file as written, line endings kept."""
    return path.read_bytes().decode("utf-8", errors="surrogateescape")


def map_files(folder: Path) -> list[Path]:
    return [path for path in folder.rglob("*") if path.name in MAPS and path.is_file()]


def api_links(repo: Path, rel: str, locale: str, slug: str) -> int:
    """The folder's pages linking into `<repo>-resources/<locale>/<slug>/` (its API refs)."""
    done = git(repo, "grep", "-l", "-F", f"-resources/{locale}/{slug}/", "--", rel)
    return len([line for line in done.stdout.splitlines() if line.endswith(".md")])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--target", default=TARGET, help="Folder holding the published repos.")
    parser.add_argument("--family", action="append", default=[], help="Only this catalog family; repeatable.")
    parser.add_argument("--product", action="append", default=[], help="Only this catalog slug; repeatable.")
    parser.add_argument("--apply", action="store_true", help="Move and rewrite; without it, a dry run.")
    args = parser.parse_args()

    cfg = ConfigManager(Path.cwd())
    names = cfg.load_publish_names()
    with open(cfg.products_path, encoding="utf-8-sig", newline="") as handle:
        family_of = {row["slug"]: row["family"] for row in csv.DictReader(handle)}
    unknown = [slug for slug in args.product if slug not in names]
    if unknown:
        print(f"not in config/publish-names.yaml: {', '.join(unknown)}")
        return 2
    chosen = [(slug, folder) for slug, folder in sorted(names.items())
              if (not args.family or family_of.get(slug) in args.family)
              and (not args.product or slug in args.product)]
    if not chosen:
        print("Nothing selected.")
        return 1

    target = Path(args.target)
    repos = sorted(child for child in target.iterdir() if (child / ".git").exists())
    mode = "APPLY" if args.apply else "DRY RUN"
    print(f"{mode}: {len(chosen)} product(s), {len(repos)} repo(s) under {target}\n")

    moves = files = map_rows = links = 0
    touched: set[str] = set()
    not_published: list[str] = []
    problems: list[str] = []
    for slug, folder in chosen:
        found = False
        for repo in repos:
            for locale_dir in sorted(p for p in repo.iterdir() if p.is_dir() and not p.name.startswith(".")):
                old = locale_dir / slug
                if not old.is_dir():
                    continue
                found = True
                locale = locale_dir.name
                rel_old, rel_new = f"{locale}/{slug}", f"{locale}/{folder}"
                count = tracked(repo, rel_old)
                loose = on_disk(old)
                maps = map_files(old)
                rows = sum(rewrite(read(path), prefixes(locale, slug, folder))[1] for path in maps)
                pages = 0 if repo.name.endswith("-resources") else api_links(repo, rel_old, locale, slug)
                print(f"  {repo.name}: {rel_old} -> {rel_new}  ({count} tracked file(s)"
                      f"{f', {loose - count} untracked' if loose != count else ''}; "
                      f"{rows} map row(s) in {len(maps)} file(s)"
                      f"{f'; {pages} page(s) link its API refs, re-convert' if pages else ''})")
                if (locale_dir / folder).exists():
                    problems.append(f"{repo.name}: {rel_new} already exists; not moved")
                    continue
                moves += 1
                files += count
                map_rows += rows
                links += pages
                touched.add(repo.name)
                if not args.apply:
                    continue
                if count:
                    done = git(repo, "mv", rel_old, rel_new)
                    if done.returncode != 0:
                        problems.append(f"{repo.name}: git mv {rel_old} failed: {done.stderr.strip()}")
                        continue
                else:
                    old.rename(locale_dir / folder)
                for path in map_files(locale_dir / folder):
                    new, n = rewrite(read(path), prefixes(locale, slug, folder))
                    if n:
                        path.write_bytes(new.encode("utf-8", errors="surrogateescape"))
        if not found:
            not_published.append(slug)

    print(f"\n{mode} summary: {moves} folder move(s) in {len(touched)} repo(s), {files} tracked file(s), "
          f"{map_rows} map row(s) {'rewritten' if args.apply else 'to rewrite'}"
          f"{f', {links} page(s) with API links to re-convert' if links else ''}.")
    if not_published:
        print(f"Not published in any repo ({len(not_published)}): {', '.join(not_published)}")
    for line in problems:
        print(f"PROBLEM {line}")
    if args.apply:
        print("Nothing committed. Next: `docushift sync` for the moved products, then `validate`, "
              "then review `git status` in each repo and commit.")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
