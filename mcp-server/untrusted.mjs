// Fences free text from a counterparty so it is returned as data, never as an
// instruction a caller's model could follow (Slice 100; see Flashy's own F-01
// fix in packages/mcp, which this deliberately mirrors rather than reinvents).
//
// A forged closing marker *inside* the untrusted text must not be able to
// close the fence early and inject text that reads as if it came from the
// server itself. Defused with a random nonce per call, so the text could
// only escape by predicting the nonce.

import { randomBytes } from "node:crypto";

export function fence(label, text) {
  if (text === undefined || text === null) return "";
  const nonce = randomBytes(8).toString("hex");
  const open = `<untrusted:${label}:${nonce}>`;
  const close = `</untrusted:${label}:${nonce}>`;
  // Nothing in `text` can reproduce `close` because it does not know `nonce`.
  return `${open}\n${String(text)}\n${close}`;
}
