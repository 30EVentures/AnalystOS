"""Shared test isolation (overnight round 6).

The legacy routes' per-IP rate limiter keeps its counters in a module-level dict that
lives for the whole test process, and every test client looks like the same client. Tests
that call those routes therefore passed only because of the order they happen to run in:
any other order (shuffled, reversed, a new test file that makes a few more requests, a slow
machine where a window rolls over) produced HTTP 429s in unrelated tests. Each test that
calls a rate-limited route starts from an empty table.
"""


def reset_rate_limits(case):
    from api.analyze import _rate_limit_buckets

    _rate_limit_buckets.clear()
    case.addCleanup(_rate_limit_buckets.clear)
