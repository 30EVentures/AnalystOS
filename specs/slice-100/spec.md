# Slice 100 - AnalystOS's own MCP server, with fenced untrusted text

## Goal

Flashy's 21 Nov reply answered the question of whether to route through their MCP
tools directly: no, build your own. Their `@flashyos/mcp` was still 0.6.0 at the time
(0.7.0, carrying the F-01 fence, was not independently verified by this session),
and a document-analysis product's tools should not import a third party's unfixed
injection surface. Build a minimal, real server instead, over the official SDK, and
prove - not merely claim - that free text from a counterparty is returned as data,
never read as an instruction.

## Done when

1. `mcp-server/server.mjs` runs on the real `@modelcontextprotocol/sdk@1.32.2`,
   exposing exactly two tools (`verify_report`, `check_acceptance`), both thin
   wrappers over the already-tested Python (`analystos.l4.seal_verify.verify_bundle`,
   `analystos.l4.acceptance.document_analysis_acceptance` via
   `mcp-server/analystos_bridge.py`) - no verification or acceptance logic is
   reimplemented in JavaScript.
2. `mcp-server/untrusted.mjs::fence()` wraps any caller-supplied free text
   (`counterparty_note`) in delimiters keyed to a fresh random nonce per call, so a
   forged closing marker inside the untrusted text cannot close the fence early -
   mirroring the fix Flashy's own `packages/mcp` made for finding F-01, not
   reinventing a different approach.
3. `mcp-server/test.mjs` tests the real server over actual stdio with the official
   SDK's `Client` + `StdioClientTransport` - not a mock, not a direct function call -
   using the SAME real bundle fixture (`tests/test_l4_seal.py::trace`) every other
   test in this repo uses.
4. An actual prompt-injection string is sent as `counterparty_note` (asking the
   server to report `ok: true` / `authentic: true` regardless of the real result)
   and shown to change nothing about the structured verdict, while still being
   returned verbatim, fenced, so a human or a model reading the response can see
   exactly what was said without executing it.
5. `tests/test_mcp_server.py` wires the Node suite into `python3 -m unittest discover`,
   skipping (never failing the whole suite) when the npm step has not been run.

## Not in this slice

- Deploying this server anywhere, or publishing it to npm. It runs locally over
  stdio, exactly as an agent host would spawn it - nothing here is a public endpoint.
- Verifying Flashy's own F-01 fix in `@flashyos/mcp@0.7.0`. This slice does not
  depend on their fix landing; it is why AnalystOS has its own server at all.
- Any tool beyond the two built. `publish_roadmap`-style tools, or anything that
  would need its own authorization model, are out of scope for a minimal server.
