"""Phase 72 rollout check for one repo (DOCOPS-324). Read-only.

After a family's `sync`: only `301.yml` files may have changed; every version map's page
rows must equal the committed file's (old shape or new); asset rows are counted; a deleted
map must be a product-level one.

    python scratch/check_301_rollout.py <repo path>
"""
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, "src")
from docushift.origins import is_asset_target, pairs  # noqa: E402
from docushift.sync.rooted import rooted  # noqa: E402

repo = Path(sys.argv[1])
# Content changes only (`git diff`, which reads through `core.autocrlf`), plus new files:
# `git status` also lists files a re-copy rewrote byte-for-byte, a line-ending artefact
# (Container Editions, 2026-11-05: 180 such files, none changed).
diff = subprocess.run(["git", "-C", str(repo), "diff", "--name-status"], capture_output=True, text=True,
                      encoding="utf-8").stdout.splitlines()
new_files = subprocess.run(["git", "-C", str(repo), "ls-files", "--others", "--exclude-standard"],
                           capture_output=True, text=True, encoding="utf-8").stdout.splitlines()
status = [f"{line.split(chr(9))[0]:<2} {line.split(chr(9))[-1]}" for line in diff] + [f"?? {n}" for n in new_files]
other, deleted_product, deleted_version, checked, assets, problems = [], [], [], 0, 0, []
for line in status:
    code, name = line[:2].strip(), line[3:].strip().strip('"')
    if not name.endswith("/301.yml"):
        other.append(line)
        continue
    parts = name.split("/")
    level = "product" if len(parts) == 4 else "version"  # <locale>/<slug>/online-help[/<seg>]/301.yml
    if code == "D":
        (deleted_product if level == "product" else deleted_version).append(name)
        continue
    new = pairs(yaml.safe_load((repo / name).read_text(encoding="utf-8")))
    old_text = subprocess.run(["git", "-C", str(repo), "show", f"HEAD:{name}"], capture_output=True,
                              text=True, encoding="utf-8").stdout if code != "??" else ""
    # The committed file may predate Phase 68 (version-relative `to`, as the translated
    # repos still had on 2026-11-05); read it in the rooted form before comparing.
    prefix = "/" + "/".join(parts[:-1]) + "/"
    old = {o: rooted(prefix, n) for o, n in pairs(yaml.safe_load(old_text))} if old_text else {}
    new_pages = {o: n for o, n in new if not is_asset_target(n)}
    new_assets = [o for o, n in new if is_asset_target(n)]
    # Each DAM path names `<doc-class>/<version>/<file>` of the product; it must be published.
    product_dir = repo / parts[0] / parts[1]
    for o, n in new:
        if is_asset_target(n):
            doc_class, segment, file_name = n.split("/")[-3:]
            if not (product_dir / doc_class / segment / file_name).is_file():
                problems.append(f"{name}: asset row names an unpublished file: {n}")
    checked += 1
    assets += len(new_assets)
    if level == "product":
        problems.append(f"product-level map rewritten instead of removed: {name}")
    elif old and new_pages != {o: n for o, n in old.items() if not is_asset_target(n)}:
        lost = set(old) - set(new_pages)
        changed = [o for o in old if o in new_pages and new_pages[o] != old[o]]
        problems.append(f"{name}: page rows differ ({len(lost)} gone, {len(changed)} changed, "
                        f"{len(set(new_pages) - set(old))} new), e.g. {(sorted(lost) or changed or [''])[0]}")
print(f"{repo.name}: {checked} version map(s) checked, {assets} asset row(s); "
      f"{len(deleted_product)} product-level map(s) deleted; {len(other)} other change(s)")
for name in deleted_version:
    print("  VERSION MAP DELETED:", name)
for line in other[:10]:
    print("  OTHER CHANGE:", line)
for problem in problems:
    print("  PROBLEM:", problem)
print("OK" if not (other or deleted_version or problems) else "STOP: review before committing")
