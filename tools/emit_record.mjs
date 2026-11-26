#!/usr/bin/env node
// Emit AnalystOS's public record (Slice 131).
//
//   node tools/emit_record.mjs            append new entries (what CI runs, on main)
//   node tools/emit_record.mjs --rev origin/main   the same, from a feature branch
//   node tools/emit_record.mjs --check    exit 1 if an emit would change anything
//   node tools/emit_record.mjs --rederive discard and re-derive everything (a stated
//                                         act; never after the record is registered)
//
// This is the vendored, unmodified `vendor-shiplog.mjs` (@flashyos/shiplog@0.2.0)
// with two privacy rules applied to the git history BEFORE anything is sealed:
//
//   1. A commit whose subject or body names the owner personally is dropped. There
//      is no version of it that is safe to publish, so it never enters the record.
//   2. Commit trailers (Co-Authored-By, Claude-Session) are stripped from the body.
//      Co-author attribution is parsed first, so agent/claude is still credited.
//
// Slice 106 applied both rules to the served copy AFTER sealing, which broke the
// seal of every surviving entry whose body carried a trailer. A seal has to cover
// exactly the bytes that are served, so the rules now run first.
//
// There is no private copy on disk. The repository is public, so a "private" full
// record committed beside the served one is not private. The state an append-only
// emit needs is the served public record itself.

import { existsSync, readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { dirname } from 'node:path'
import { execFileSync } from 'node:child_process'
import {
  readGitLog, parseGitLog, fromCommits, deriveOptionsFrom, mergeEntries, publicView, fragmentOf,
  devlogEntriesFromCommits, mergeDevlogEntries, devlogFragmentOf, renderDevlogMarkdown, commitBaseFrom,
} from '../vendor-shiplog.mjs'

export const PERSONAL_RE = /caleb|solway/i
const TRAILER_RE = /(^|\n)[ \t]*(Co-Authored-By|Claude-Session):[\s\S]*$/i

export const stripTrailers = (text) => (text ?? '').replace(TRAILER_RE, '').trim()

export const namesOwner = (commit) =>
  PERSONAL_RE.test(commit.subject ?? '') || PERSONAL_RE.test(commit.body ?? '')

/** The two rules, as a pure function over parsed commits. */
export function cleanCommits(commits) {
  let dropped = 0
  const kept = []
  for (const commit of commits) {
    if (namesOwner(commit)) { dropped += 1; continue }
    const body = stripTrailers(commit.body)
    const clean = { ...commit }
    if (body) clean.body = body
    else delete clean.body
    kept.push(clean)
  }
  return { commits: kept, dropped }
}

const readJson = (path) => (existsSync(path) ? JSON.parse(readFileSync(path, 'utf8')) : null)

/** Keep the previous `generated` stamp when the entries did not change, so an emit
 *  with nothing new is a true no-op and `--check` can say so. */
function stable(next, previous) {
  if (previous && JSON.stringify(previous.entries) === JSON.stringify(next.entries)) {
    return { ...next, generated: previous.generated }
  }
  return next
}

function main(argv) {
  const rederive = argv.includes('--rederive')
  const check = argv.includes('--check')
  const config = JSON.parse(readFileSync('.shiplog/config.json', 'utf8'))
  const held = readJson('.shiplog/held.json') ?? {}
  const shipPath = config.serve
  const devlogPath = config.serveDevlog
  const devlogMdPath = 'DEVLOG.md'
  if (!shipPath || !devlogPath) throw new Error('.shiplog/config.json needs both serve and serveDevlog')

  // The record is the trunk's story. Emitting on a feature branch would seal that
  // branch's own commits into a log that never forgets, so a branch must name the
  // revision it derives from (for example --rev origin/main).
  const revFlag = argv.indexOf('--rev') === -1 ? undefined : argv[argv.indexOf('--rev') + 1]
  const branch = execFileSync('git', ['rev-parse', '--abbrev-ref', 'HEAD'], { encoding: 'utf8' }).trim()
  const rev = revFlag ?? config.rev ?? 'HEAD'
  if (!check && !revFlag && !config.rev && branch !== (config.branch ?? 'main')) {
    throw new Error(`on branch ${branch}, not ${config.branch ?? 'main'}: pass --rev origin/main to derive the trunk's record`)
  }
  // A missing served file is not a fresh start: a plain emit would silently re-derive
  // every entry with a new assertion date and new digests. That is a stated act.
  if (!rederive && (!existsSync(shipPath) || !existsSync(devlogPath))) {
    throw new Error(`${shipPath} or ${devlogPath} is missing: restore it from git, or pass --rederive on purpose`)
  }

  const { commits, dropped } = cleanCommits(parseGitLog(readGitLog({ rev })))

  const derived = fromCommits(commits, { ...deriveOptionsFrom(config), held })
  const previousShip = readJson(shipPath)
  const keptShip = rederive || !previousShip ? [] : previousShip.entries ?? []
  const shipEntries = publicView(mergeEntries(keptShip, derived.entries), held)
  const ship = stable(fragmentOf(config, shipEntries), rederive ? null : previousShip)

  const devlogDerived = devlogEntriesFromCommits(commits, { repo: config.source, commitBase: commitBaseFrom(config), held })
  const previousDevlog = readJson(devlogPath)
  const keptDevlog = rederive || !previousDevlog ? [] : previousDevlog.entries ?? []
  const devlog = stable(devlogFragmentOf(config, mergeDevlogEntries(keptDevlog, devlogDerived)), rederive ? null : previousDevlog)
  const markdown = renderDevlogMarkdown(devlog.entries, { title: config.devlogTitle })

  const outputs = [
    [shipPath, `${JSON.stringify(ship, null, 2)}\n`],
    [devlogPath, `${JSON.stringify(devlog, null, 2)}\n`],
    [devlogMdPath, markdown],
  ]
  const changed = outputs.filter(([path, text]) => !existsSync(path) || readFileSync(path, 'utf8') !== text).map(([p]) => p)

  if (check) {
    console.log(changed.length ? `emit_record: STALE - would change ${changed.join(', ')}` : 'emit_record: up to date')
    return changed.length ? 1 : 0
  }
  for (const [path, text] of outputs) {
    mkdirSync(dirname(path), { recursive: true })
    writeFileSync(path, text)
  }
  console.log(`${ship.entries.length} shipped entries -> ${shipPath}${rederive ? ' (re-derived)' : ''}`)
  console.log(`${devlog.entries.length} devlog entries -> ${devlogPath}, ${devlogMdPath}`)
  console.log(`${dropped} commit(s) left out for naming the owner personally`)
  // A count, never the addresses: CI logs on a public repository are public.
  if (derived.unmapped.length) console.log(`${derived.unmapped.length} unmapped author address(es) attributed to ${config.defaultAuthor}`)
  return 0
}

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].split('/').pop())) {
  try { process.exit(main(process.argv.slice(2))) } catch (error) { console.error(error.message); process.exit(1) }
}
