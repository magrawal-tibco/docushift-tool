"""Drop Data Science Workbench 14.4.0; its old URLs go to Statistica 14.4.0 (user, 18 Nov; DOCOPS-382).

Workbench 14.4.0 publishes the same pages as Statistica 14.4.0 (14,250 each) from a different
old address (docs.tibco.com/pub/dsc-stat/14.4.0 vs /pub/stat/14.4.0). Every row of Workbench's
`301.yml` is re-pointed at the same page (or the matching document) under Statistica 14.4.0 and
appended to Statistica's map; then the Workbench 14.4.0 folders and their `version.yml` rows are
removed, in the repo and the reframed/ workspace.

    python scratch/drop_workbench_1440.py            # dry run
    python scratch/drop_workbench_1440.py --apply
"""
import os
import re
import shutil
import sys

APPLY = "--apply" in sys.argv
REPO = "C:/github/tibco-docs-aem/en-us-spotfire-statistica-userdocs"
WB, ST, SEG = "spotfire-data-science-workbench", "spotfire-statistica", "14-4-0"
WS = f"reframed/en-us-spotfire-statistica/{WB}/14.4.0"
ROW = re.compile(r'^"(https://[^"]+)": "([^"]+)"$', re.M)

wb_map = open(f"{REPO}/en-us/{WB}/online-help/{SEG}/301.yml", encoding="utf-8").read()
st_path = f"{REPO}/en-us/{ST}/online-help/{SEG}/301.yml"
st_map = open(st_path, encoding="utf-8").read()
st_old = set(o for o, _ in ROW.findall(st_map))

added, missing = [], []
for old, new in ROW.findall(wb_map):
    if old in st_old:
        continue
    path, _, anchor = new.partition("#")
    if path.startswith("/en-us/"):
        target = path.replace(f"/en-us/{WB}/", f"/en-us/{ST}/", 1)
        local = REPO + target
    else:  # a document in the DAM: Statistica's copy is named SPOT_stat_..., Workbench's SPOT_dsc-stat_...
        target = path.replace(f"/{WB}/", f"/{ST}/", 1).replace("SPOT_dsc-stat_", "SPOT_stat_")
        local = REPO + "/en-us/" + target.split("/us/en/", 1)[1]
    if not os.path.exists(local):
        missing.append((old, target))
        continue
    added.append(f'"{old}": "{target}{"#" + anchor if anchor else ""}"')

print(f"{len(added)} Workbench URL(s) re-pointed at Statistica 14.4.0; {len(missing)} with no Statistica page")
for old, target in missing[:20]:
    print("  no target:", old, "->", target)

folders = [f"{REPO}/en-us/{WB}/{cls}/{SEG}" for cls in os.listdir(f"{REPO}/en-us/{WB}")
           if os.path.isdir(f"{REPO}/en-us/{WB}/{cls}/{SEG}")]
print("remove:", *folders, WS if os.path.isdir(WS) else "(no workspace copy)", sep="\n  ")

if APPLY and not missing:
    with open(st_path, "a", encoding="utf-8", newline="") as fh:
        fh.write(f"# Data Science Workbench 14.4.0 (same pages, not migrated; DOCOPS-382)\n")
        fh.write("\n".join(added) + "\n")
    for f in folders:
        shutil.rmtree(f)
        vy = os.path.join(os.path.dirname(f), "version.yml")
        text = open(vy, encoding="utf-8").read()
        # one list item per version: drop the block naming 14.4.0
        blocks = re.split(r"(?m)^(?=- )", text)
        kept = [b for b in blocks if f'path: "/{SEG}"' not in b]
        with open(vy, "w", encoding="utf-8", newline="") as fh:
            fh.write("".join(kept))
    if os.path.isdir(WS):
        shutil.rmtree(WS)
    print("applied")
elif APPLY:
    print("not applied: fix the missing targets first")
