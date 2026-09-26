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
the Terminal). There are two ways to fill it in.

### The fast way: a template

If your table looks like an income statement (a period column, and any of
revenue / cost of revenue / gross profit / operating expenses / operating
income / net income, however they're labeled), skip `asks` entirely:

```
{
  "title": "Review of your.csv",
  "source": "your.csv",
  "schema": { "period": "text", "revenue": "number", "net_income": "number" },
  "template": "income_statement",
  "currency_unit": "actual"
}
```

This generates the standard questions automatically — the latest period's
figures, year-over-year growth, margins — for whichever line items it
recognizes. Nothing is invented: a line item it doesn't recognize is simply
left out.

**`currency_unit` matters and only has one right answer per table.** It says
what scale the numbers in your table *are* — look at what your source
document itself says (a real income statement almost always states this,
e.g. "$ in millions"):

- `"actual"` — the numbers are already raw dollars (`4200000` means $4.2M).
- `"thousands"` — the numbers are in thousands (`4200` means $4.2M).
- `"millions"` — the numbers are in millions (`4.2` means $4.2M).

Get this wrong and every dollar figure in the report is confidently wrong by
a factor of 1,000 or 1,000,000 - not an error, just a wrong number. Check it
against the source before you run the job.

### The manual way: write your own questions

For anything a template doesn't cover, write `asks` yourself:

```
{
  "title": "Review of your.csv",
  "source": "your.csv",
  "schema": { "period": "text", "revenue": "number" },
  "currency_unit": "actual",
  "asks": [
    { "text": "period Q1 revenue was {answer}.",
      "format": "usd",
      "where": ["period", "Q1"],
      "select": "revenue" }
  ]
}
```

- **`title`** — what this section is about.
- **`asks`** — one entry per fact you want. Each entry has:
  - `text` — the sentence to write. `{answer}` is where the number lands.
  - `where` — `[column, value]`: find the row where *column* equals *value*.
  - `select` — the column whose value is the answer.
  - `format` (optional) — see below.

**Worked example** — *"give me revenue for the FY2024 row"*:

```
{ "text": "FY2024 revenue was {answer}.",
  "format": "usd",
  "where": ["period", "FY2024"],
  "select": "revenue" }
```

Add as many `asks` as you want. Put a comma between entries; the **last** entry
has no comma after it.

**Making numbers readable.** Add an optional `"format"` to any ask so the
number prints properly instead of raw (`4200000.0`):

- `"usd"` — a dollar amount: prints as `$4.2M` / `$1.3B`, scaled by the job's
  one `currency_unit` (see above) — never set per-ask.
- `"percent"` — adds a `%` sign (growth and margin asks return a percent number).
- `"number"` — adds thousands commas: `4,200,000`.

A negative value always prints in parentheses — `($4.2M)` — the standard way
of showing a loss.

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

---

## Reading a document instead of a table

Running `python3 -m analystos <job-dir>` on a job with no `asks` and no
`template` reads the document's real text (CSV, Excel, Word, PowerPoint or PDF),
proposes facts with a model, verifies each in code, and writes a report. It needs
`ANTHROPIC_API_KEY` in your environment. Besides `section.html` and
`section.pdf` it writes `section.seal.json`: a seal you or anyone else can check
with `python3 -m analystos.l4.seal_verify section.seal.json` (see
[`seal.md`](seal.md)). Set `ANALYSTOS_SEAL_KEY` first to sign it.

To call AnalystOS from another program instead, see [`api.md`](api.md).

