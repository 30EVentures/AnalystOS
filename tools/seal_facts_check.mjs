#!/usr/bin/env node
// Validate a seal bundle's facts against the published SealFact schema (Slice 77).
// Dependency-free. Shape only: see docs/seal.md for the content checks.
import { readFileSync } from "node:fs";

const LIVE = "https://analystos.dev/api/v1/openapi.json";
const KEYWORDS = new Set(["description", "type", "const", "enum", "required", "properties",
                          "items", "oneOf", "anyOf", "pattern"]);

const kind = (v) => v === null ? "null" : Array.isArray(v) ? "array" : typeof v;
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

function unsupported(schema, path = "SealFact") {
  if (Array.isArray(schema)) return schema.flatMap((s, i) => unsupported(s, `${path}[${i}]`));
  if (schema === null || typeof schema !== "object") return [];
  const bad = Object.keys(schema).filter((k) => !KEYWORDS.has(k));
  const own = bad.map((k) => `${path}.${k}`);
  const nested = [];
  for (const [k, v] of Object.entries(schema)) {
    if (k === "properties") for (const [p, s] of Object.entries(v)) nested.push(...unsupported(s, `${path}.${p}`));
    else if (["items", "oneOf", "anyOf"].includes(k)) nested.push(...unsupported(v, `${path}.${k}`));
  }
  return [...own, ...nested];
}

function problems(value, schema, path) {
  if (schema.oneOf) {
    const hits = schema.oneOf.filter((s) => problems(value, s, path).length === 0).length;
    return hits === 1 ? [] : [`${path}: matches ${hits} of ${schema.oneOf.length} shapes (needs exactly 1)`];
  }
  if (schema.anyOf) {
    return schema.anyOf.some((s) => problems(value, s, path).length === 0) ? [] : [`${path}: matches none of the allowed shapes`];
  }
  const out = [];
  if ("const" in schema && !same(value, schema.const)) out.push(`${path}: must be ${JSON.stringify(schema.const)}`);
  if (schema.enum && !schema.enum.some((e) => same(e, value))) out.push(`${path}: ${JSON.stringify(value)} is not one of ${JSON.stringify(schema.enum)}`);
  if (schema.type) {
    const allowed = [].concat(schema.type);
    if (!allowed.includes(kind(value))) out.push(`${path}: is ${kind(value)}, needs ${allowed.join(" or ")}`);
  }
  if (typeof value === "string" && schema.pattern && !new RegExp(schema.pattern).test(value)) out.push(`${path}: ${JSON.stringify(value)} does not match ${schema.pattern}`);
  if (kind(value) === "object") {
    for (const r of schema.required || []) if (!(r in value)) out.push(`${path}: missing ${r}`);
    for (const [k, s] of Object.entries(schema.properties || {})) if (k in value) out.push(...problems(value[k], s, `${path}.${k}`));
  }
  if (Array.isArray(value) && schema.items) value.forEach((v, i) => out.push(...problems(v, schema.items, `${path}[${i}]`)));
  return out;
}

async function load(where) {
  if (/^https?:\/\//.test(where)) {
    const res = await fetch(where);
    if (!res.ok) throw new Error(`${where}: HTTP ${res.status}`);
    return res.json();
  }
  return JSON.parse(readFileSync(where, "utf8"));
}

async function main() {
  const [bundlePath, specPath = LIVE] = process.argv.slice(2);
  if (!bundlePath) { console.error("usage: seal_facts_check.mjs bundle.json [openapi.json|url]"); return 2; }
  let bundle, schema;
  try {
    bundle = JSON.parse(readFileSync(bundlePath, "utf8"));
    schema = (await load(specPath)).components.schemas.SealFact;
    if (!schema) throw new Error("no components.schemas.SealFact in that document");
    if (!Array.isArray(bundle.facts)) throw new Error("bundle has no facts array");
  } catch (e) { console.error(`unreadable input: ${e.message}`); return 2; }
  const bad = unsupported(schema);
  if (bad.length) { console.error(`schema uses keywords this checker does not implement: ${bad.join(", ")}`); return 2; }
  const found = [];
  bundle.facts.forEach((fact, i) => {
    const key = fact && fact.key !== undefined ? fact.key : `facts[${i}]`;
    for (const p of problems(fact ? fact.record : undefined, schema, "record")) found.push({ key, problem: p });
  });
  console.log(JSON.stringify({ ok: found.length === 0, checked: bundle.facts.length, problems: found }, null, 2));
  return found.length ? 1 : 0;
}

main().then((code) => process.exit(code));
