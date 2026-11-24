"""Which verified output each role delivers, and how to draw it (Slice 124).

Every format draws the same verified content and calls the same guard
(``deck.checked_role``); they differ only in layout. A role's format is its catalog
``delivers_today`` value; the catalog sets it by family (``FAMILY_FORMAT``).
"""

from analystos.l4.deck import render_deck
from analystos.l4.memo import render_memo
from analystos.l4.workbook import render_workbook

FORMATS = {
    "verified-deck": {"name": "deck", "extension": "pptx", "render": render_deck,
                      "media_type": "application/vnd.openxmlformats-officedocument.presentationml.presentation"},
    "verified-memo": {"name": "memo", "extension": "docx", "render": render_memo,
                      "media_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    "verified-workbook": {"name": "workbook", "extension": "xlsx", "render": render_workbook,
                          "media_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
}

# The format each family's work is read in (phase 1; role-written outputs come in phase 2).
FAMILY_FORMAT = {
    "consulting": "verified-deck", "content-communications": "verified-deck",
    "sales-customer-coordination": "verified-deck", "software-it": "verified-deck",
    "research-reporting": "verified-memo", "legal-contracts-procurement": "verified-memo",
    "risk-audit-controls": "verified-memo", "people-hr": "verified-memo", "insurance": "verified-memo",
    "financial-crime": "verified-memo",
    "finance-modeling": "verified-workbook", "accounting-operations": "verified-workbook",
    "data-analytics": "verified-workbook",
}


def format_of(role):
    """The format record for a catalog role (deck when the role names none)."""
    return FORMATS[role.get("delivers_today") or "verified-deck"]


def render(spec, engagement, catalog):
    """``(bytes, format record)`` for the spec's role, or ValueError (from the renderer's guard)."""
    roles = {r["id"]: r for r in catalog["roles"]}
    role = roles.get(spec.get("role")) if isinstance(spec, dict) else None
    fmt = format_of(role) if role else FORMATS["verified-deck"]
    return fmt["render"](spec, engagement, catalog), fmt
