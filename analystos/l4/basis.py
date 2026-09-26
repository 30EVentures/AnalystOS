"""The basis of a figure: what a reader must know before leaning on it.

One definition, shared by every renderer (HTML and PDF; body text, KPI
tiles, chart notes), so a tag can never appear on one surface and be
missing on another. Slice 56.

A basis label is shown when a segment is forward-looking (``guidance`` or
``projected``), is a non-GAAP measure, or was read from an embedded image
rather than extracted text. These come from segment metadata; whether the
metadata is *right* is a separate matter (see specs/slice-56/spec.md).
"""

FORWARD_HORIZONS = ("guidance", "projected")
IMAGE_FOOTNOTE = "Read from an image, not from extracted text."


def basis_labels(segment):
    """Ordered list of human-readable basis labels for one segment."""
    labels = []
    horizon = segment.get("horizon", "reported")
    if horizon in FORWARD_HORIZONS:
        labels.append(horizon)
    if segment.get("gaap_status") == "non_gaap":
        labels.append("non-GAAP")
    if segment.get("source") == "image":
        labels.append("from image")
    return labels


def basis_text(*segments):
    """One line of distinct basis labels across ``segments`` ("" if none)."""
    seen = []
    for segment in segments:
        for label in basis_labels(segment):
            if label not in seen:
                seen.append(label)
    return " · ".join(seen)
