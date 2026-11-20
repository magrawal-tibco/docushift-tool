"""Summary for the Data Virtualization docs team: what Phase 87 changed in each version's menu.

    python scratch/dv_structure_report.py > reports/dv-menu-changes-2026-11-20.md
"""
import csv
import sys
from pathlib import Path

import yaml

W = Path("reframed/en-us-spotfire-data-virtualization/tibco-data-virtualization")
PLANS = Path("reports/ai-grouping")
sys.stdout.reconfigure(encoding="utf-8")


def titles(toc_path: Path) -> dict[str, str]:
    out = {}

    def walk(nodes):
        for n in nodes or []:
            u = str(n.get("url") or "").partition("#")[0]
            if u:
                out.setdefault(u, str(n.get("title")))
            walk(n.get("subfolderlist"))

    walk(yaml.safe_load(toc_path.read_text(encoding="utf-8"))["docs"])
    return out


def items_text(items, before, depth=0) -> list[str]:
    lines = []
    for it in items or []:
        pad = "  " * depth
        if "group" in it:
            g = it["group"]
            names = [before.get(i.get("from"), i.get("from")) for i in g.get("items") or [] if "from" in i]
            lines.append(f"{pad}- **{g['title']}** (new group): " + ", ".join(names))
            continue
        old = before.get(it["from"], it["from"])
        if it.get("collapse"):
            lines.append(f"{pad}- \"{old}\": this wrapper level is removed; its chapters move up one level")
        elif it.get("title") and it["title"] != old:
            lines.append(f"{pad}- \"{old}\", now titled \"{it['title']}\"")
        else:
            lines.append(f"{pad}- {old}")
    return lines


print("# Spotfire Data Virtualization: changes to the help menu, 20 Nov 2026\n")
print("For the Data Virtualization documentation team. No topic's text was changed; this is about "
      "where topics sit in the menu and which repeated copies are published once.\n")
print("**Why.** Data Virtualization ships five separate help systems (Adapters, Business Directory, "
      "Deployment Manager, Studio, Web UI). Published side by side on the new site they gave five "
      "top-level entries all titled with the product name, four copies of What's New, folders "
      "repeated inside themselves (`deployment-manager/deployment-manager`, "
      "`business-directory/businessdirectory/business-directory`), 76 adapters in one flat list, and "
      "dozens of topics published twice. They are now one menu with 11 sections, the same in every "
      "version.\n")
print("**Old addresses.** Every page that moved, and every copy no longer published, redirects to "
      "its new place, so bookmarks and links from outside keep working. The Japanese help for 8.8.0 "
      "and 8.8.1 follows the English layout page for page.\n")

for version in ("8.9.0", "8.8.1", "8.8.0"):
    plan = yaml.safe_load((PLANS / f"tibco-data-virtualization-{version}.yaml").read_text(encoding="utf-8"))
    before = titles(W / (version + ".before-phase87") / "toc.yml")
    drops = plan.get("drop_duplicates") or []
    print(f"\n## Version {version}\n")
    print("### The new menu\n")
    for i, sec in enumerate(plan["sections"], 1):
        land = sec.get("landing")
        land_txt = ("a new section page" if land in (None, "new")
                    else f"section page: the former \"{before.get(land, land)}\" page, `{land}`")
        print(f"{i}. **{sec['title']}** ({land_txt})")
        for line in items_text(sec.get("items"), before, 1):
            print("   " + line)
    dm = [d for d in drops if d["drop"].startswith("deployment-manager")]
    other = [d for d in drops if not d["drop"].startswith("deployment-manager")]
    print("\n### Topics published once\n")
    if dm:
        print(f"- **Deployment Manager help ({len(dm)} pages):** it is the same text as the "
              "Administration Guide's Deployment Manager chapter, so only the Administration Guide "
              "copy is published. Each Deployment Manager page redirects to its twin there.")
    print(f"- **Other repeated copies ({len(other)}):** identical text in two places. The copy kept "
          "and the copy that now redirects to it:\n")
    print("| No longer published | Redirects to |\n|---|---|")
    for d in other:
        print(f"| {before.get(d['drop'], d['drop'])} (`{d['drop']}`) | "
              f"{before.get(d['keep'], d['keep'])} (`{d['keep']}`) |")
    review = plan.get("review") or []
    if review:
        print("\n### For the writers to decide (not changed)\n")
        print("These pairs are nearly the same but differ in a way only a writer can settle. Both "
              "copies are still published.\n")
        for r in review:
            print(f"- **{before.get(r['a'], r['a'])}** / **{before.get(r['b'], r['b'])}**: {r.get('note', '')}")

print("\n## Questions for the team\n")
print("1. The nearly identical pairs above: which copy is right (for example, the two java.security "
      "paths in the SQL Server 2008 limitation)?")
print("2. The section and group names (\"Using Studio\", \"Client Interfaces and APIs\", the seven "
      "adapter groups): are they the words your readers use?")
print("3. The 9 data-source limitation pages that were in both the User Guide and an adapter guide "
      "now live in the adapter guide only. Should the User Guide link to them instead?")
