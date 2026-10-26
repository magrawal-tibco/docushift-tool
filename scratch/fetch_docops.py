"""Snapshot this migration's DOCOPS issues into reports/jira/docops-snapshot.json.

A reader of Jira, never a writer: one paged search, the fields the status page's
work-done section needs. Only the migration's epics and what sits under them are
written; DOCOPS also holds other teams' issues, and those never reach the file.
build_conversion_status.py reads the snapshot, so the page rebuilds offline and the
numbers say which day they are from.
Uses the API token kept beside apply_docops_plan.py (never copied into this repo).

    python scratch/fetch_docops.py
"""

import argparse
import base64
import datetime as dt
import json
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = "https://csg-engops.atlassian.net"
EMAIL = "mayur.agrawal@cloud.com"
TOKEN_FILE = Path("C:/github/confluence-mcp/jira/jira-api-token")
SP_FIELD = "customfield_10039"
# The epics this migration's work is logged under (docs/jira.md).
WORK_EPICS = {"DOCOPS-5", "DOCOPS-74", "DOCOPS-75", "DOCOPS-139", "DOCOPS-153", "DOCOPS-170"}
FIELDS = ["summary", "parent", "issuetype", "status", "components", "labels", "created",
          "resolutiondate", "duedate", "assignee", SP_FIELD]


def search(token: str) -> list[dict]:
    auth = base64.b64encode(f"{EMAIL}:{token}".encode()).decode()
    issues, next_token = [], None
    while True:
        params = {"jql": "project = DOCOPS ORDER BY key ASC", "maxResults": 100, "fields": ",".join(FIELDS)}
        if next_token:
            params["nextPageToken"] = next_token
        req = urllib.request.Request(f"{SITE}/rest/api/3/search/jql?{urllib.parse.urlencode(params)}",
                                     headers={"Authorization": "Basic " + auth, "Accept": "application/json"})
        with urllib.request.urlopen(req) as resp:
            data = json.load(resp)
        issues += data.get("issues", [])
        next_token = data.get("nextPageToken")
        if not next_token or not data.get("issues"):
            return issues


def slim(issue: dict) -> dict:
    f = issue["fields"]
    return {
        "key": issue["key"],
        "summary": f["summary"].strip(),
        "type": f["issuetype"]["name"],
        "parent": (f.get("parent") or {}).get("key"),
        "status": f["status"]["name"],
        "category": f["status"]["statusCategory"]["key"],  # new / indeterminate / done
        "components": [c["name"] for c in f.get("components") or []],
        "labels": f.get("labels") or [],
        "created": f["created"][:10],
        "resolved": (f.get("resolutiondate") or "")[:10],
        "due": f.get("duedate") or "",
        "assignee": (f.get("assignee") or {}).get("displayName", ""),
        "sp": f.get(SP_FIELD),
    }


def ours(issues: list[dict]) -> list[dict]:
    """The work epics and every issue whose parent chain reaches one."""
    parent = {i["key"]: i["parent"] for i in issues}

    def under_work(key: str | None) -> bool:
        seen = set()
        while key and key not in seen:
            if key in WORK_EPICS:
                return True
            seen.add(key)
            key = parent.get(key)
        return False

    return [i for i in issues if under_work(i["key"])]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "reports/jira/docops-snapshot.json")
    args = parser.parse_args()
    issues = ours([slim(i) for i in search(TOKEN_FILE.read_text().strip())])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"fetched": dt.date.today().isoformat(), "issues": issues},
                                   indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {args.out}  {len(issues)} issues")


if __name__ == "__main__":
    main()
