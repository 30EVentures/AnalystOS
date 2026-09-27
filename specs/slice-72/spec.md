# Slice 72 - the evidence store says out loud when it uses the public key (roadmap Q9)

## Goal

Audit finding 4: with no `ANALYSTOS_EVIDENCE_KEY`, the evidence store encrypts with
a key derived from a constant printed in the source. That is a reasonable
zero-configuration default (never plaintext) but it protects only against casual
reading, and nothing told the person running it. A run on someone's laptop looked
identical to a configured one.

- The first time a process falls back to the development key it writes one line to
  stderr saying so and what to set. Once per process, so a server's logs are not
  flooded and a CLI run prints it once.
- Behaviour is otherwise unchanged: same key, same files, same defaults, so existing
  stores stay readable.
- With a key configured, nothing is printed.

## Not in this slice

- Refusing to run without a key (a breaking change; the fallback exists so the CLI
  works out of the box).
- Rotating or re-encrypting existing stores.

## Done when

1. Fallback use prints exactly one warning per process; a configured key prints none.
2. The warning names the environment variable and says the key is public.
3. Files written before and after are byte-compatible (decrypt round trip).
4. Full suite OK.
