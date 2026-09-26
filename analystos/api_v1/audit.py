"""The charter's three measures, computed from the audit log (Slice 61).

Each is a share with an explicit numerator and denominator, ``None`` when the
denominator is zero - never a made-up 100%.
"""


def _share(numerator, denominator):
    return {"numerator": numerator, "denominator": denominator,
            "share": (numerator / denominator) if denominator else None}


def measures(events):
    analyses = [e for e in events if e.get("type") == "analysis"]
    proposed = sum(int(e.get("proposed", 0)) for e in analyses)
    dropped = sum(int(e.get("dropped", 0)) for e in analyses)
    return {
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
