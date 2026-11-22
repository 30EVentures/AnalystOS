"""The charter's measures, computed from the audit log (Slice 61, extended
Slice 104).

Each is a share with an explicit numerator and denominator, ``None`` when the
denominator is zero - never a made-up 100%. Only computed for roles with a
real audit-log event type behind them - a role the charter names but this
codebase has not built yet (coordination's siblings: research, synthesis,
client-delivery) is simply absent from this dict, never given a fabricated
number (see tests/test_api_v1.py::test_measure_text_matches_the_published_charter).
"""


def _share(numerator, denominator):
    return {"numerator": numerator, "denominator": denominator,
            "share": (numerator / denominator) if denominator else None}


def measures(events):
    analyses = [e for e in events if e.get("type") == "analysis"]
    jobs_created = [e for e in events if e.get("type") == "job_created"]
    proposed = sum(int(e.get("proposed", 0)) for e in analyses)
    dropped = sum(int(e.get("dropped", 0)) for e in analyses)
    scorable_engagements = sum(1 for e in jobs_created if e.get("agreed_by"))
    delivered_on_time = sum(1 for e in analyses if e.get("via") == "job" and e.get("on_time") is True)
    return {
        "coordination": {
            "measure": "Engagements delivered by the date agreed at acceptance, as a share of engagements accepted",
            **_share(delivered_on_time, scorable_engagements),
        },
        "analysis": {
            "measure": "Reports delivered at the written tier, with both quality gates passed, as a share of reports delivered",
            **_share(sum(1 for e in analyses if e.get("tier") == "written"), len(analyses)),
        },
        "verification": {
            "measure": "Facts refused for failing verification, as a share of facts proposed",
            **_share(dropped, proposed),
        },
        "evidence": {
            "measure": "Delivered reports whose seal re-verifies offline, as a share of reports delivered",
            **_share(sum(1 for e in analyses if e.get("seal_ok") is True), len(analyses)),
        },
    }
