"""Slice 9 - scaffold a job.json from a CSV, so nobody hand-writes JSON.

    python3 -m analystos.scaffold <csv-path> <dest-dir>

Creates ``<dest-dir>``, copies the CSV into it, and writes a ``job.json`` with:
  - a guessed schema (a column is ``"number"`` if every non-empty value parses
    as one, otherwise ``"text"``)
  - a few example asks pre-filled from the first data row, for you to edit.
"""

import csv
import json
import shutil
import sys
from pathlib import Path


def _looks_number(value):
    try:
        float(value)
        return True
    except ValueError:
        return False


def _guess_schema(rows, headers):
    schema = {}
    for col in headers:
        values = [r[col].strip() for r in rows if (r.get(col) or "").strip()]
        schema[col] = "number" if values and all(map(_looks_number, values)) else "text"
    return schema


def _example_asks(rows, schema):
    if not rows:
        return []
    first = rows[0]
    text_cols = [c for c, t in schema.items() if t == "text"]
    number_cols = [c for c, t in schema.items() if t == "number"]
    key_col = text_cols[0] if text_cols else next(iter(schema))
    key_val = (first.get(key_col) or "").strip()
    targets = number_cols[:3] or [c for c in schema if c != key_col][:1]
    return [
        {
            "text": f"{key_col} {key_val} {col} was {{answer}}.",
            "where": [key_col, key_val],
            "select": col,
        }
        for col in targets
    ]


def scaffold(csv_path, dest_dir):
    """Create a job folder at ``dest_dir`` from the CSV at ``csv_path``.

    Returns the path to the written ``job.json``.
    """
    csv_path = Path(csv_path)
    dest_dir = Path(dest_dir)
    if not csv_path.is_file():
        raise FileNotFoundError(f"no CSV at {csv_path}")
    if dest_dir.exists():
        raise FileExistsError(f"{dest_dir} already exists - pick another folder")

    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        rows = list(reader)

    schema = _guess_schema(rows, headers)
    job = {
        "title": f"Review of {csv_path.name}",
        "source": csv_path.name,
        "schema": schema,
        "asks": _example_asks(rows, schema),
    }

    dest_dir.mkdir(parents=True)
    shutil.copyfile(csv_path, dest_dir / csv_path.name)
    job_file = dest_dir / "job.json"
    job_file.write_text(json.dumps(job, indent=2) + "\n", encoding="utf-8")
    return job_file


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 2:
        print("usage: python3 -m analystos.scaffold <csv-path> <dest-dir>", file=sys.stderr)
        return 2
    job_file = scaffold(argv[0], argv[1])
    print(f"wrote {job_file}")
    print(f"edit the title and asks, then run:  python3 -m analystos {job_file.parent}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
