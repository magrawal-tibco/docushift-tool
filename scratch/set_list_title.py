"""Sets `docs_list_title` of existing online-help `toc.yml` files to "<product> <version>".

The user's call, 2026-11-14: the help menu on the AEM site is titled with the
product's name and version (`TIBCO® MDM Studio 6.1.1`), not "Online Help".
`convert` and `reframe` write it from then on; this updates the trees already on
disk, so thousands of published versions need no re-conversion.

Read-only unless `--apply`.

    python scratch/set_list_title.py --root C:/github/tibco-docs-aem/en-us-tib-ems-userdocs
    python scratch/set_list_title.py --root output --root reframed --product tibco-ems --apply

A root is walked for exactly two layouts, and nothing else:
  published repo   <locale>/<slug>/online-help/<dashed-version>/toc.yml
                   (also one level down, for a folder holding several repos)
  workspace tree   output|reframed/<family-dir>/<slug>/<version>/toc.yml
                   (the root is `output`, `reframed`, or a folder holding them)

Only the first `docs_list_title:` line at column 0 changes. Line endings, encoding
(UTF-8, a BOM kept) and the quoting style already on the line are kept.

**Run it over the workspace and the published repos together.** `sync` compares a
published file with the workspace's by size, so a title changed on one side only
re-copies the version folder on the next sync, and a workspace left on "Online
Help" puts that title back. In the workspace the file's modification time is
kept: `sync` refuses a merged tree whose `output/` twin has a newer top-level file
(`distributor._built_at`), and a later mtime on `output/.../toc.yml` alone would
trip that for every merged version. In a published repo the mtime is left to
change, so git sees the edit.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from docushift.catalog import CatalogManager  # noqa: E402
from docushift.config import ConfigManager  # noqa: E402
from docushift.converter.navigation import online_help_title  # noqa: E402
from docushift.transforms.csh import quote  # noqa: E402
from docushift.utils.slug import version_segment  # noqa: E402

KEY = "docs_list_title:"
LOCALE = re.compile(r"^[a-z]{2}-[a-z]{2}$")
WORKSPACE = ("output", "reframed")
BOM = "\ufeff"


def published(root: Path) -> list[Path]:
    """`<locale>/<slug>/online-help/<segment>/toc.yml`, at the root or one level down."""
    found = []
    for pattern in ("*/*/online-help/*/toc.yml", "*/*/*/online-help/*/toc.yml"):
        found += [p for p in root.glob(pattern) if LOCALE.match(p.parents[3].name)]
    return found


def workspace(root: Path) -> list[Path]:
    """`<family-dir>/<slug>/<version>/toc.yml` under an `output` or `reframed` folder."""
    trees = [root] if root.name in WORKSPACE else [root / name for name in WORKSPACE]
    return [p for tree in trees if tree.is_dir() for p in tree.glob("*/*/*/toc.yml")]


def render(value: str, old: str) -> str:
    """`value` as a YAML scalar in the style `old` (the line's current value) uses."""
    old = old.strip()
    if old.startswith('"'):
        text = quote(value)
    elif old.startswith("'"):
        text = "'" + value.replace("'", "''") + "'"
    else:
        text = value
    # Plain text with a `: ` or a leading `-` would parse as something else.
    if _parses(text) != value:
        text = quote(value)
    assert _parses(text) == value, value
    return text


def _parses(text: str) -> object:
    try:
        return (yaml.safe_load(f"k: {text}\n") or {}).get("k")
    except yaml.YAMLError:
        return None


def retitle(path: Path, title: str, apply: bool, keep_mtime: bool) -> tuple[str, str] | None:
    """`(old, new)` value text when the line changes, `None` when it already holds `title`.

    Raises `ValueError` for a file with no `docs_list_title:` line at column 0.
    """
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    bom = text.startswith(BOM)
    if bom:
        text = text[1:]
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if not line.startswith(KEY):
            continue
        body = line.rstrip("\r\n")
        ending = line[len(body):]
        old = body[len(KEY):]
        if _parses(old.strip()) == title:
            return None
        lines[index] = f"{KEY} {render(title, old)}{ending}"
        if apply:
            stat = path.stat()
            path.write_bytes(((BOM if bom else "") + "".join(lines)).encode("utf-8"))
            if keep_mtime:
                os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        return old.strip(), lines[index][len(KEY):].strip()
    raise ValueError("no docs_list_title line")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", action="append", required=True, type=Path,
                        help="a published repo, or output/, reframed/ or the folder holding them")
    parser.add_argument("--product", help="one product slug")
    parser.add_argument("--project", type=Path, default=REPO,
                        help="the DocuShift checkout whose catalog names the products")
    parser.add_argument("--apply", action="store_true", help="write the files (default: report only)")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # names carry ® and ™

    config = ConfigManager(root_dir=args.project)
    catalog = CatalogManager(config.products_path, config.versions_path, config=config).load()
    # Every catalog row, retired or out of scope included: a published tree may hold one.
    products = catalog.products

    changed = same = 0
    unmapped: list[str] = []
    for root in args.root:
        found = [(p, False) for p in published(root)] + [(p, True) for p in workspace(root)]
        for path, in_workspace in sorted(found):
            folder, slug = path.parent.name, path.parents[1 if in_workspace else 2].name
            if args.product and slug != args.product.lower():
                continue
            product = products.get(slug)
            if product is None:
                unmapped.append(f"{path}  (no product {slug!r} in the catalog)")
                continue
            if in_workspace:
                numbers = [folder] if folder in product.versions else []
            else:
                numbers = [n for n in product.versions if version_segment(n) == folder]
            if len(numbers) != 1:
                why = "no catalog version" if not numbers else f"several versions {numbers}"
                unmapped.append(f"{path}  ({why} for {folder!r})")
                continue
            title = online_help_title(product.display_name, numbers[0])
            try:
                result = retitle(path, title, args.apply, keep_mtime=in_workspace)
            except (OSError, UnicodeDecodeError, ValueError) as exc:
                unmapped.append(f"{path}  ({type(exc).__name__}: {exc})")
                continue
            if result is None:
                same += 1
                continue
            changed += 1
            print(f"{path}: {result[0]} -> {result[1]}")

    verb = "changed" if args.apply else "would change"
    print(f"\n{changed} file(s) {verb}, {same} already titled, {len(unmapped)} skipped"
          + ("" if args.apply else " (dry run; --apply writes)"))
    for line in unmapped:
        print(f"  skipped: {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
