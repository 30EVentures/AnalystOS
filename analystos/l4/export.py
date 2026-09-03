"""L4 - render a working-paper section with a footnote trail.

The caller supplies a title and a list of *findings*. Each finding is a dict::

    {
        "text": "Total FY2024 revenue was {answer}.",   # must contain {answer}
        "answer": 4200000.0,
        "citation": {"source": <hash>, "row": 3, "column": "revenue"},
    }

A ``citation`` is either one cell (a dict) or, for a computed metric, a list
of the cells it was derived from.

``render_section`` fills each ``{answer}`` in, appends a numbered ``[n]``
marker, and lists the citations as footnotes underneath. It returns the
section as a string; it does not write a file.

``render_html`` turns that string into a standalone, printable HTML page. It
is purpose-built for the format ``render_section`` produces - not a general
Markdown renderer.
"""

import html
import re

_MARKER_RE = re.compile(r"\[(\d+)\]")
_FOOTNOTE_RE = re.compile(r"^\[(\d+)\]\s*(.*)$")

_STYLE = """
body{font:16px/1.65 Georgia,'Times New Roman',serif;max-width:42rem;
  margin:3rem auto;padding:0 1.5rem;color:#1a1a1a}
h1{font-size:1.5rem;line-height:1.3;margin:0 0 1.75rem;
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}
p{margin:0 0 1rem}
sup{line-height:0}
sup a{text-decoration:none;color:#2f5ce0;font-size:.72em;padding:0 .1em}
hr{border:0;border-top:1px solid #ccc;margin:2.5rem 0 1.25rem}
.footnotes{font-size:12.5px;line-height:1.5;color:#555;
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}
.footnotes p{margin:.35rem 0}
.footnotes .n{color:#1a1a1a;font-weight:600;margin-right:.3em}
.footnotes a{color:#2f5ce0;text-decoration:none;margin-left:.3em}
@media print{body{margin:0;max-width:none;font-size:12pt}
  sup a,.footnotes a{color:#000}}
"""


def _one_cell(cell):
    return f'source {cell["source"]} - row {cell["row"]}, column "{cell["column"]}"'


def _footnote(n, citation):
    if isinstance(citation, list):
        return f"[{n}] computed from: " + "; ".join(_one_cell(c) for c in citation)
    return f"[{n}] {_one_cell(citation)}"


def render_section(title, findings):
    """Return the section as text: heading, body with ``[n]`` markers, footnotes."""
    body = []
    footnotes = []
    for n, finding in enumerate(findings, start=1):
        text = finding["text"]
        if "{answer}" not in text:
            raise ValueError(
                f"finding {n}: text has no {{answer}} placeholder: {text!r}"
            )
        body.append(text.replace("{answer}", str(finding["answer"])) + f" [{n}]")
        footnotes.append(_footnote(n, finding["citation"]))

    return (
        f"# {title}\n\n"
        + "\n\n".join(body)
        + "\n\n---\n"
        + "\n".join(footnotes)
        + "\n"
    )


def _para_html(text):
    """Escape a body paragraph and turn ``[n]`` into a superscript link."""
    esc = html.escape(text)
    return _MARKER_RE.sub(
        lambda m: (
            f'<sup><a href="#fn{m.group(1)}" id="ref{m.group(1)}">'
            f"{m.group(1)}</a></sup>"
        ),
        esc,
    )


def _note_html(line):
    """Turn a ``[n] ...`` footnote line into an anchored, back-linked <p>."""
    m = _FOOTNOTE_RE.match(line.strip())
    if not m:
        return f"<p>{html.escape(line.strip())}</p>"
    n, rest = m.group(1), html.escape(m.group(2))
    return (
        f'<p id="fn{n}"><span class="n">{n}.</span>{rest}'
        f' <a href="#ref{n}">&#8617;</a></p>'
    )


def render_html(section_md):
    """Render a section produced by ``render_section`` as a standalone HTML page."""
    body_part, _, notes_part = section_md.partition("\n---\n")
    chunks = [c.strip() for c in body_part.strip().split("\n\n") if c.strip()]

    title = ""
    paragraphs = []
    for chunk in chunks:
        if chunk.startswith("# ") and not title:
            title = chunk[2:].strip()
        else:
            paragraphs.append(chunk)

    esc_title = html.escape(title)
    body = "\n".join(f"<p>{_para_html(p)}</p>" for p in paragraphs)
    notes = "\n".join(
        _note_html(line) for line in notes_part.strip().split("\n") if line.strip()
    )

    return (
        "<!doctype html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        f"<title>{esc_title}</title>\n<style>{_STYLE}</style>\n</head>\n<body>\n"
        f"<h1>{esc_title}</h1>\n{body}\n<hr>\n"
        f'<div class="footnotes">\n{notes}\n</div>\n</body>\n</html>\n'
    )
