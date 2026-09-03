"""L4 - render a working-paper section with a footnote trail.

The caller supplies a title and a list of *findings*. Each finding is a dict::

    {
        "text": "Total FY2024 revenue was {answer}.",   # must contain {answer}
        "answer": 4200000.0,
        "citation": {"source": <hash>, "row": 3, "column": "revenue"},
    }

``render_section`` fills each ``{answer}`` in, appends a numbered ``[n]``
marker, and lists the citations as footnotes underneath. It returns the
section as a string; it does not write a file.
"""


def _footnote(n, citation):
    return (
        f'[{n}] source {citation["source"]} - '
        f'row {citation["row"]}, column "{citation["column"]}"'
    )


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
