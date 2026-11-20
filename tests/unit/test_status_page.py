"""The "Where we stand" status (closeout plan §8b): scratch/status_page.py.

The module lives in scratch/ beside the build script and is standard library only,
so it is loaded from its path rather than imported from the package.
"""

import datetime as dt
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("status_page", ROOT / "scratch/status_page.py")
sp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sp)

AREAS_YAML = """\
go_live: 2026-11-23   # Mon
old_site_off: 2026-11-30
jira_owner:
  DOCOPS-346: Digital Platform
areas:
  - id: problems
    name: Problems found
    team: TechDocs
    status: on track
    note: "Fixed in a window: never the same day"
    next: 2026-11-16
    next_step: Sort the findings
    jira_labels: [verify-issue]
  - id: blockers
    name: Go-live blockers
    team: Digital Platform
    status: blocked
    next: 2026-11-20
    next_step: Serve the BW plug-ins
    jira: [DOCOPS-346]
    waiting_on:
      - team: Digital Platform
        what: Serve the BW plug-ins, or give a date
        due: 2026-11-20
      - team: Engineering
        what: Confirm the list
  - id: migration
    name: Converting
    team: TechDocs
    status: done
    jira: [DOCOPS-5]
"""


def issue(key, parent=None, status="Backlog", category="new", sp=0.5, labels=(), type_="Sub-task",
          created="2026-10-01"):
    return {"key": key, "parent": parent, "status": status, "category": category, "sp": sp, "labels": list(labels),
            "type": type_, "summary": f"summary {key}", "due": "", "created": created}


@pytest.fixture
def cfg():
    return sp.load_areas(AREAS_YAML)


# -- the YAML subset --------------------------------------------------------------

def test_parse_simple_yaml_reads_nested_lists_flow_lists_quotes_and_comments():
    doc = sp.parse_simple_yaml(AREAS_YAML)
    assert doc["go_live"] == "2026-11-23"
    assert doc["jira_owner"] == {"DOCOPS-346": "Digital Platform"}
    assert doc["areas"][0]["note"] == "Fixed in a window: never the same day"
    assert doc["areas"][0]["jira_labels"] == ["verify-issue"]
    assert doc["areas"][1]["waiting_on"][1] == {"team": "Engineering", "what": "Confirm the list"}
    assert doc["areas"][2]["jira"] == ["DOCOPS-5"]


def test_parse_simple_yaml_refuses_what_it_does_not_read():
    with pytest.raises(ValueError, match="multi-line"):
        sp.parse_simple_yaml("note: >-\n  folded text\n")
    with pytest.raises(ValueError, match="duplicate"):
        sp.parse_simple_yaml("a: 1\na: 2\n")


def test_the_real_areas_file_reads_the_same_as_full_yaml():
    yaml = pytest.importorskip("yaml")
    text = (ROOT / "config/status-areas.yaml").read_text(encoding="utf-8")

    def norm(value):
        if isinstance(value, dict):
            return {k: norm(v) for k, v in value.items()}
        if isinstance(value, list):
            return [norm(v) for v in value]
        return None if value is None else str(value)

    assert sp.parse_simple_yaml(text) == norm(yaml.safe_load(text))
    loaded = sp.load_areas(text)
    assert {a["team"] for a in loaded["areas"]} <= set(sp.TEAMS)


def test_load_areas_allows_only_the_three_teams_and_four_statuses():
    with pytest.raises(ValueError, match="team must be one of"):
        sp.load_areas(AREAS_YAML.replace("team: TechDocs", "team: Docs", 1))
    with pytest.raises(ValueError, match="status must be one of"):
        sp.load_areas(AREAS_YAML.replace("status: blocked", "status: late"))
    with pytest.raises(ValueError, match="waiting_on"):
        sp.load_areas(AREAS_YAML.replace("team: Engineering", "team: Support"))


# -- counts -----------------------------------------------------------------------

def test_headline_counts_only_versions_in_the_migration_and_days_left():
    rows = [
        {"bu": "TIBCO", "inMig": True, "converted": True, "published": True, "staging": True},
        {"bu": "TIBCO", "inMig": True, "converted": True, "published": False, "staging": False},
        {"bu": "IBI", "inMig": True, "converted": False, "published": False, "staging": False},
        {"bu": "IBI", "inMig": False, "converted": True, "published": True, "staging": True},
    ]
    h = sp.headline(rows, dt.date(2026, 11, 13), "2026-11-23", "2026-11-30")
    assert (h["daysToGoLive"], h["daysToOldSiteOff"]) == (10, 17)
    assert h["total"] == {"bu": "All", "inMig": 3, "converted": 2, "published": 1, "staging": 1,
                          "checked": 0, "understood": 0}
    assert [r["bu"] for r in h["byBu"]] == ["TIBCO", "IBI"]
    assert h["byBu"][1]["converted"] == 0


def test_each_sub_task_counts_under_one_area_key_then_label_then_parent(cfg):
    issues = [
        issue("DOCOPS-5", type_="Epic", created="2026-09-25"),
        issue("DOCOPS-96", type_="Story"),
        issue("DOCOPS-346", parent="DOCOPS-96", labels=["verify-issue"], sp=0.25),   # named: blockers
        issue("DOCOPS-349", parent="DOCOPS-96", labels=["verify-issue"], category="indeterminate"),
        issue("DOCOPS-7", parent="DOCOPS-5", type_="Story"),
        issue("DOCOPS-364", parent="DOCOPS-7", category="done", sp=1),               # parent chain: migration
        issue("DOCOPS-300", parent="DOCOPS-96", sp=2),                               # nothing: other
        issue("DOCOPS-301", parent="DOCOPS-7", status="Canceled", category="done"),  # never counted
    ]
    assigned = sp.assign_issues(issues, cfg["areas"])
    assert assigned == {"DOCOPS-346": "blockers", "DOCOPS-349": "problems", "DOCOPS-364": "migration",
                        "DOCOPS-300": sp.OTHER_AREA}
    e = sp.effort(issues, cfg["areas"])
    rows = {r["id"]: r for r in e["rows"]}
    assert rows["problems"]["doing"] == 0.5 and rows["blockers"]["todo"] == 0.25
    assert rows["migration"]["done"] == 1 and rows[sp.OTHER_AREA]["todo"] == 2
    assert e["total"] == {"done": 1, "doing": 0.5, "todo": 2.25, "issues": 4}
    assert e["firstIssue"] == "2026-09-25"
    assert e["missing"] == []


def test_karan_measure_reads_actions_with_notes():
    changes = [{"action": "add", "slug": "a", "version": "1"},
               {"action": "add (retired: override needed)", "slug": "b", "version": "1"},
               {"action": "remove (retired)", "slug": "c", "version": "1"}]
    versions = {("a", "1"): {"migrate_decision": "migrate", "published": True},
                ("b", "1"): {"migrate_decision": "unknown", "published": False},
                ("c", "1"): {"migrate_decision": "do_not_migrate", "published": False}}
    m = sp.karan_measure(changes, versions)
    assert (m["done"], m["total"]) == (2, 3)
    assert "written into the catalog: 2 of 3; added: 1 of 2; removed: 1 of 1" in m["detail"]


def test_problem_kinds_owner_follows_triage_decision_and_jira_owner():
    kinds = [
        {"kind": "unlogged", "code": "A", "scope": "", "decision": "error", "jira": ""},
        {"kind": "triaged", "code": "B", "scope": "x", "decision": "logged", "jira": "DOCOPS-346"},
        {"kind": "triaged", "code": "C", "scope": "y", "decision": "logged", "jira": "DOCOPS-346"},
        {"kind": "triaged", "code": "D", "scope": "", "decision": "logged", "jira": "DOCOPS-360"},
        {"kind": "triaged", "code": "E", "scope": "", "decision": "platform", "jira": "DOCOPS-255"},
        {"kind": "triaged", "code": "F", "scope": "", "decision": "source", "jira": ""},
        {"kind": "triaged", "code": "G", "scope": "", "decision": "accepted", "jira": ""},
    ]
    k = sp.problem_kinds(kinds, {"DOCOPS-346": "Digital Platform"})
    assert k["teams"]["Digital Platform"] == {"kinds": 2, "byDecision": {"logged": 1, "platform": 1}}
    assert k["teams"]["TechDocs"] == {"kinds": 3, "byDecision": {"unlogged": 1, "logged": 1, "source": 1}}
    assert (k["accepted"], k["unlogged"], k["entries"]) == (1, 1, 7)


# -- the plan, and who owes what ---------------------------------------------------

PLAN = """\
## 7. Decisions

| # | Decision | Answer |
|---|---|---|
| D5 | Which fixes go into R2 | **All of them** (user, 12 Nov) |
| D6 | The 82 TIBCO versions with no package | Fri 20 |
| D7 | Delta: which new versions from Δ1 go into R2 | Mon 16, from the refresh list |

## 8. Next
"""


def test_open_decisions_are_the_unanswered_rows_with_their_day():
    got = sp.open_decisions(PLAN, "2026-11")
    assert [(d["id"], d["due"]) for d in got] == [("D6", "2026-11-20"), ("D7", "2026-11-16")]
    assert sp.plain(got[1]["what"]) == "Delta: which new versions from the 16 Nov catalog refresh go into release 2"


def test_pending_by_team_groups_dates_issues_decisions_and_says_a_step_once(cfg):
    issues = [issue("DOCOPS-346", labels=["verify-issue"]), issue("DOCOPS-349", labels=["verify-issue"])]
    e = sp.effort(issues, cfg["areas"])
    rows = sp.area_rows(cfg["areas"], {}, issues, e["assigned"], cfg["owners"])
    kinds = sp.problem_kinds([], {})
    pending = sp.pending_by_team(rows, sp.open_decisions(PLAN, "2026-11"), kinds)

    tech = pending["TechDocs"]["items"]
    assert [i["due"] for i in tech] == ["2026-11-16", "2026-11-16", "2026-11-20"]
    assert {i.get("decision") for i in tech} == {None, "D6", "D7"}
    # The blockers' next step is the same day as Digital Platform's waiting_on item: said once.
    assert [i["what"] for i in pending["Digital Platform"]["items"]] == ["Serve the BW plug-ins, or give a date"]
    assert [i["due"] for i in pending["Engineering"]["items"]] == [""]
    assert [i["key"] for i in pending["Digital Platform"]["issues"]] == ["DOCOPS-346"]
    assert [i["key"] for i in pending["TechDocs"]["issues"]] == ["DOCOPS-349"]
    # The done area owes nothing.
    assert all(i["area"] != "Converting" for i in tech)


def _bu(**kw):
    row = {"bu": "TIBCO", "inMig": 100, "converted": 100, "published": 100, "staging": 100,
           "checked": 100, "understood": 100}
    row.update(kw)
    return row


def _uat(**kw):
    u = {"bu": "TIBCO", "rows": 5, "openCritical": 0, "openHigh": 0, "open": 0, "retest": 0}
    u.update(kw)
    return u


def test_bu_health_takes_the_weakest_share():
    assert sp.bu_health(_bu(), None)["status"] == "on track"
    h = sp.bu_health(_bu(staging=90, checked=90, understood=60), None)
    assert h["status"] == "blocked" and h["reason"].startswith("67% of checked")
    assert sp.bu_health(_bu(staging=85, checked=85, understood=85), None)["status"] == "at risk"


def test_bu_health_counts_local_checks_when_nothing_is_on_staging():
    h = sp.bu_health(_bu(staging=0, checked=97, understood=97), None)
    assert h["status"] == "on track"
    assert "no staging" in sp.bu_health(_bu(staging=0, checked=50, understood=50), None)["reason"]


def test_open_critical_uat_rows_mean_at_risk_never_blocked():
    h = sp.bu_health(_bu(), _uat(openCritical=2, open=2, retest=3))
    assert h["status"] == "at risk"
    assert "2 Critical" in h["reason"] and "3 UAT rows" in h["reason"]
    assert sp.bu_health(_bu(understood=10), _uat(openCritical=1, open=1))["status"] == "blocked"


def test_a_hand_set_health_wins():
    h = sp.bu_health(_bu(), None, {"status": "blocked", "reason": "Site not served"})
    assert (h["status"], h["reason"], h["byHand"]) == ("blocked", "Site not served", True)
    with pytest.raises(ValueError, match="bu_health"):
        bad = "bu_health:" + chr(10) + "  IBI:" + chr(10) + "    status: late" + chr(10) + "    reason: x" + chr(10)
        sp.load_areas(bad + AREAS_YAML)


def test_uat_summary_reads_open_and_completed_rows():
    head = ["Type", "Issue description", "Issue screenshot", "Category", "Priority", "Found In", "Reporter", "Status"]
    rows = [head,
            ["", "a", "", "", "Critical", "", "", "New"],
            ["", "b", "", "", "High", "", "", "In progress"],
            ["", "c", "", "", "High", "", "", "Completed"],
            ["", "d", "", "", "Critical", "", "", "Not a bug"],
            ["", "e", "", "", "Medium", "", "", "Closed"],
            ["", "", "", "", "Critical", "", "", "New"]]
    u = sp.uat_summary({"Tibco UAT": rows, "Spotfire UAT": [head]})
    assert u["TIBCO"] == {"bu": "TIBCO", "rows": 5, "openCritical": 1, "openHigh": 1, "open": 2, "retest": 1}
    assert u["Spotfire"]["rows"] == 0 and "IBI" not in u


def test_markdown_is_plain_and_carries_the_as_of_time(cfg):
    issues = [issue("DOCOPS-346", labels=["verify-issue"])]
    e = sp.effort(issues, cfg["areas"])
    rows = sp.area_rows(cfg["areas"], {}, issues, e.pop("assigned"), cfg["owners"])
    e.update(fetched="2026-11-13", daysSinceFirst=43)
    decisions = sp.open_decisions(PLAN, "2026-11")
    status = {
        "asOfText": "13 Nov 2026, 07:30",
        "headline": sp.headline([{"bu": "TIBCO", "inMig": True, "converted": True, "published": True,
                                  "staging": False}], dt.date(2026, 11, 13), "2026-11-23", "2026-11-30"),
        "areas": rows, "effort": e,
        "pending": sp.pending_by_team(rows, decisions, sp.problem_kinds([], {})),
    }
    text = sp.render_markdown(status)
    assert "As of 13 Nov 2026, 07:30." in text
    assert "in 10 days" in text and "in 17 days" in text
    assert "DOCOPS-" not in text and "Δ" not in text and "R2" not in text
    assert "**Digital Platform**" in text and "**Engineering**" in text
