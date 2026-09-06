"""L4 - chart rendering as plain inline SVG. No charting library and no
new dependency: a browser renders SVG natively with zero JavaScript, and
pulling in something like ``matplotlib`` for this would add real weight
to Vercel's serverless functions for what a few hundred lines of string-
built markup already does. ``reportlab`` (already a dependency) has
``reportlab.graphics.charts`` for a PDF equivalent - deliberately not
built yet, see ``specs/slice-28/spec.md``.

Every function here takes already-resolved ``(label, value)`` pairs and
a format spec - this module knows nothing about verification, the same
separation ``analystos.l4.export.format_number`` already has from the
segments that feed it. Resolving a chart spec's ``fact_index`` list
against verified segments (and dropping an unverifiable point, or the
whole chart) is ``analystos.l4.rich_export``'s job, not this module's.
"""

import html

from analystos.l4.export import format_number

_WIDTH = 560
_HEIGHT = 320
_PALETTE = ("#2F5CE0", "#1B3A6B", "#57C79E", "#D79A5C", "#8A93A1", "#A94442")
_AXIS_COLOR = "#C3C8D2"
_TEXT_COLOR = "#10151F"
_LABEL_COLOR = "#565E6B"


def _esc(text):
    return html.escape(str(text))


def _value_label(value, value_format, currency_unit):
    return _esc(format_number(value, value_format, currency_unit))


def _svg_open(title):
    return (
        f'<svg viewBox="0 0 {_WIDTH} {_HEIGHT}" xmlns="http://www.w3.org/2000/svg" '
        f'role="img" aria-label="{_esc(title)}">'
    )


def bar_chart_svg(title, categories, values, value_format="number", currency_unit="actual"):
    """A vertical bar chart comparing ``values`` across ``categories`` -
    the shape for a segment/peer/region comparison. Returns an ``<svg>``
    string sized to fill its container; embed directly in HTML.
    """
    n = len(categories)
    pad_left, pad_right, pad_top, pad_bottom = 50, 30, 50, 60
    plot_w = _WIDTH - pad_left - pad_right
    plot_h = _HEIGHT - pad_top - pad_bottom
    max_val = max(values) if values else 0
    max_val = max_val or 1  # avoid divide-by-zero for an all-zero series

    slot = plot_w / n
    bar_w = slot * 0.55

    bars = []
    for i, (cat, val) in enumerate(zip(categories, values)):
        bar_h = (val / max_val) * plot_h if max_val else 0
        x = pad_left + i * slot + (slot - bar_w) / 2
        y = pad_top + plot_h - bar_h
        color = _PALETTE[i % len(_PALETTE)]
        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" '
            f'fill="{color}" rx="3"/>'
            f'<text x="{x + bar_w / 2:.1f}" y="{y - 8:.1f}" text-anchor="middle" '
            f'font-size="13" font-weight="600" fill="{_TEXT_COLOR}">'
            f'{_value_label(val, value_format, currency_unit)}</text>'
            f'<text x="{x + bar_w / 2:.1f}" y="{pad_top + plot_h + 22:.1f}" '
            f'text-anchor="middle" font-size="12" fill="{_LABEL_COLOR}">{_esc(cat)}</text>'
        )

    baseline_y = pad_top + plot_h
    return (
        _svg_open(title)
        + f'<text x="{pad_left}" y="24" font-size="15" font-weight="600" '
        + f'fill="{_TEXT_COLOR}">{_esc(title)}</text>'
        + f'<line x1="{pad_left}" y1="{baseline_y}" x2="{_WIDTH - pad_right}" '
        + f'y2="{baseline_y}" stroke="{_AXIS_COLOR}" stroke-width="1"/>'
        + "".join(bars)
        + "</svg>"
    )


def line_chart_svg(title, x_labels, values, value_format="usd", currency_unit="actual"):
    """A line chart tracing ``values`` across ``x_labels`` (periods) - the
    shape for a trend over time.
    """
    n = len(x_labels)
    pad_left, pad_right, pad_top, pad_bottom = 50, 30, 50, 45
    plot_w = _WIDTH - pad_left - pad_right
    plot_h = _HEIGHT - pad_top - pad_bottom
    max_val = max(values) if values else 0
    min_val = min(values) if values else 0
    span = (max_val - min_val) or 1

    step = plot_w / (n - 1) if n > 1 else 0
    points = []
    for i, val in enumerate(values):
        x = pad_left + i * step
        y = pad_top + plot_h - ((val - min_val) / span) * plot_h
        points.append((x, y))

    polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    dots = []
    for (x, y), val, label in zip(points, values, x_labels):
        dots.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{_PALETTE[0]}"/>'
            f'<text x="{x:.1f}" y="{y - 12:.1f}" text-anchor="middle" font-size="13" '
            f'font-weight="600" fill="{_TEXT_COLOR}">'
            f'{_value_label(val, value_format, currency_unit)}</text>'
            f'<text x="{x:.1f}" y="{pad_top + plot_h + 22:.1f}" text-anchor="middle" '
            f'font-size="12" fill="{_LABEL_COLOR}">{_esc(label)}</text>'
        )

    baseline_y = pad_top + plot_h
    return (
        _svg_open(title)
        + f'<text x="{pad_left}" y="24" font-size="15" font-weight="600" '
        + f'fill="{_TEXT_COLOR}">{_esc(title)}</text>'
        + f'<line x1="{pad_left}" y1="{baseline_y}" x2="{_WIDTH - pad_right}" '
        + f'y2="{baseline_y}" stroke="{_AXIS_COLOR}" stroke-width="1"/>'
        + f'<polyline points="{polyline}" fill="none" stroke="{_PALETTE[0]}" stroke-width="2.5"/>'
        + "".join(dots)
        + "</svg>"
    )


def donut_chart_svg(title, categories, values, value_format="usd", currency_unit="actual"):
    """A donut chart showing ``values`` as a share of their total - the
    shape for a composition/mix breakdown, with a legend since a ring
    alone can't carry category labels legibly.
    """
    total = sum(values) or 1
    cx, cy, r, stroke = 130, _HEIGHT / 2, 85, 34
    circumference = 2 * 3.14159265 * r

    arcs = []
    offset = 0.0
    for i, val in enumerate(values):
        fraction = val / total
        dash = fraction * circumference
        color = _PALETTE[i % len(_PALETTE)]
        arcs.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" '
            f'stroke-width="{stroke}" '
            f'stroke-dasharray="{dash:.2f} {circumference - dash:.2f}" '
            f'stroke-dashoffset="{-offset:.2f}" transform="rotate(-90 {cx} {cy})"/>'
        )
        offset += dash

    legend = []
    legend_x, legend_y = 260, cy - (len(categories) * 26) / 2 + 8
    for i, (cat, val) in enumerate(zip(categories, values)):
        y = legend_y + i * 26
        pct = val / total * 100
        color = _PALETTE[i % len(_PALETTE)]
        legend.append(
            f'<rect x="{legend_x}" y="{y - 11}" width="14" height="14" rx="3" fill="{color}"/>'
            f'<text x="{legend_x + 22}" y="{y:.1f}" font-size="13" fill="{_TEXT_COLOR}">'
            f'{_esc(cat)}</text>'
            f'<text x="{legend_x + 22}" y="{y + 16:.1f}" font-size="12" fill="{_LABEL_COLOR}">'
            f'{_value_label(val, value_format, currency_unit)} ({pct:.0f}%)</text>'
        )

    return (
        _svg_open(title)
        + f'<text x="30" y="24" font-size="15" font-weight="600" '
        + f'fill="{_TEXT_COLOR}">{_esc(title)}</text>'
        + "".join(arcs)
        + "".join(legend)
        + "</svg>"
    )
