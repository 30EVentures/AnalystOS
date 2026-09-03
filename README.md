# AnalystOS

An operating system for the analyst's core loop: gather evidence, impose
structure on it, reason across it, produce a defensible answer, and keep a
trail that survives review.

## Status

Early build. Working through the **NOW** milestone — see [`ROADMAP.md`](ROADMAP.md).

## Getting started

Requires Python 3.11+ (developed on 3.14). No third-party packages yet.

Run the tests:

```
python3 -m unittest discover -s tests -v
```

Run a report on a CSV: see [`docs/using-analystos.md`](docs/using-analystos.md).

Try the worked example:

```
python3 -m analystos fixtures/golden
```

## Layout

| Path | What's in it |
|------|--------------|
| `docs/`            | architecture and the decision log |
| `specs/`           | one folder per slice of work: goal + acceptance checks |
| `fixtures/golden/` | the canonical worked example (added in a later slice) |
| `tests/`           | the test suite |

## Background

Vision, architecture, brand and roadmap live in the founding dossier and its
Revision A. This repo is the working copy; [`ROADMAP.md`](ROADMAP.md) is the
source of truth.
