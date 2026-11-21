"""Acceptance criteria for the document-analysis offer, written as a check a
stranger can run rather than a sentence in a contract (Slice 97).

The Flashy estate's 18 Nov integration document argued that an outcome-based
price is "a word rather than a mechanism" without acceptance criteria agreed
*before* work starts and checkable *after* delivery. This is that check, built
entirely from what this repo already verifies (`analystos.l4.seal_verify.verify_bundle`)
- it adds no new trust requirement, only states explicitly which of the
verifier's existing answers a buyer should require before accepting delivery.

A client should run this, or its own equivalent, against the bundle AnalystOS
hands over - not take AnalystOS's word that the engagement's criteria were met.
"""

from analystos.l4 import seal
from analystos.l4.seal_verify import verify_bundle

#: Reused verbatim in drafts/playbook-document-analysis.json's step briefs, so
#: the two can never silently disagree about what "accepted" means.
CRITERIA = (
    "The seal verifies: every structural and signature check in the bundle passes.",
    "Every cited figure is checked against the source text (content_checked is "
    "true) - a seal that merely parses, or a check run with no source text at "
    "all, is not enough. The client holds the source text; supply it.",
    "The report was sealed at one of the tiers this repo actually delivers from "
    "(written, deterministic or plain) - never an unrecognised or missing tier.",
)


def document_analysis_acceptance(bundle, source_text):
    """Returns a list of human-readable failure reasons; an empty list means
    the deliverable meets the document-analysis offer's acceptance criteria.
    Never raises - a malformed bundle is a failure reason, not an exception,
    matching ``verify_bundle``'s own fail-closed contract.

    ``source_text`` is required, not optional: the second criterion in
    CRITERIA only has teeth when it is supplied. A client accepting a
    delivery holds its own source document and should pass it in - calling
    this with ``None`` and treating a pass as acceptance would be exactly
    the gamed check this module exists to prevent."""
    reasons = []

    if not isinstance(bundle, dict):
        return [f"not a bundle: expected an object, got {type(bundle).__name__}"]

    result = verify_bundle(bundle, source_text=source_text)
    if not result["ok"]:
        failing = [c["name"] for c in result["checks"] if c["status"] == "fail"]
        reasons.append(f"the seal does not verify: {', '.join(failing) or 'unknown check'}")

    if not result["content_checked"]:
        reasons.append(
            "content was not checked against the source text"
            if source_text is not None
            else "no source text was supplied, so content could not be checked at all"
        )

    tier = bundle.get("payload", {}).get("tier") if isinstance(bundle.get("payload"), dict) else None
    if tier not in seal._SEALABLE_TIERS:
        reasons.append(f"tier {tier!r} is not one this repo delivers from {seal._SEALABLE_TIERS}")

    return reasons
