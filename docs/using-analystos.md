# Using AnalystOS

AnalystOS takes a table and a list of questions, and writes a short section of
prose where **every number has a footnote back to the exact cell it came
from**. Anyone can check your figures without asking you.

Everything is a command you type in the **Terminal** app. Three steps.

---

## Before you start

- Your data must be a **CSV file**. In Excel: *File → Save As → CSV*.
- Open Terminal and go to the project folder — **do this first, every time**:

  ```
  cd ~/AnalystOS/AnalystOS
  ```

  If a later command says *"No such file or directory"*, you're probably in
  the wrong place — run that line again.

---

## Step 1 — make a job from your CSV

```
python3 -m analystos.scaffold path/to/your.csv jobs/my-first-job
```

This creates a folder `jobs/my-first-job/` holding a copy of your CSV and a
`job.json` file. It prints the next command to run.

---

## Step 2 — edit the job

Open `jobs/my-first-job/job.json` in a text editor (TextEdit, VS Code — **not**
the Terminal). It looks like this:

```
{
  "title": "Review of your.csv",
  "source": "your.csv",
  "schema": { "period": "text", "revenue": "number" },
  "asks": [
    { "text": "period Q1 revenue was {answer}.",
      "where": ["period", "Q1"],
      "select": "revenue" }
  ]
}
```

Change two things:

- **`title`** — what this section is about.
- **`asks`** — one entry per fact you want. Each entry has:
  - `text` — the sentence to write. `{answer}` is where the number lands.
  - `where` — `[column, value]`: find the row where *column* equals *value*.
  - `select` — the column whose value is the answer.

**Worked example** — *"give me revenue for the FY2024 row"*:

```
{ "text": "FY2024 revenue was {answer}.",
  "where": ["period", "FY2024"],
  "select": "revenue" }
```

Add as many `asks` as you want. Put a comma between entries; the **last** entry
has no comma after it.

---

## Step 3 — run it

```
python3 -m analystos jobs/my-first-job
```

It prints the section and writes two files into `jobs/my-first-job/`:

- `section.md` — the plain-text version.
- `section.html` — a formatted page, which **opens in your browser
  automatically**. To get a PDF: in the browser, **File → Print → Save as
  PDF** (or press **Cmd+P**).

---

## Reading the output

```
FY2024 revenue was 4200000.0. [1]

---
[1] source 32110ff4... - row 4, column "revenue"
```

The `[1]` footnote means: this number came from **row 4** (the header counts
as row 1), **column "revenue"**, of the file whose contents fingerprint to
`32110ff4...`. That fingerprint changes if even one character of the source
changes — so a footnote that still matches is proof the source wasn't altered.

---

## If something goes wrong

- **Pasted JSON into the Terminal and it hung** (a `>` or `cursh>` prompt) —
  press **Ctrl+C**. `job.json` is a *file*; edit it in a text editor.
- **"No such file or directory"** — run `cd ~/AnalystOS/AnalystOS` first.
- **`no row where 'period' == 'FY2024'`** — the value in your `where` doesn't
  match the CSV exactly. Check spelling, spaces, and things like `FY24` vs
  `FY2024`.

---

## What it can't do yet

- Only **CSV** files.
- Only **exact-match lookups** — no sums, growth rates, or ratios.
- No plain-English questions — you fill in `where` and `select` yourself.
