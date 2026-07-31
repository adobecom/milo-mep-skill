#!/usr/bin/env node
// Lint a published MEP manifest .json (or a normalized manifest on stdin).
//
//   node lint.mjs <manifest.json>            # local file
//   node lint.mjs https://…/manifest.json    # fetch a published manifest
//   node lint.mjs -                           # read JSON from stdin
//       (e.g. python mep_xlsx.py read foo.xlsx | node lint.mjs -)
//
//   --check-links        also fetch every fragment path and flag 404s
//   --base <origin>      base origin for relative fragment paths
//                        (defaults to the manifest URL's origin when fetched)
//
// Exit code is non-zero when any ERROR-level finding is reported (incl. 404s).

import { readFileSync } from "node:fs";
import { lintManifest, toManifest, formatFindings, collectFragments } from "./lint-core.mjs";

const argv = process.argv.slice(2);
if (argv.includes("--help") || argv.includes("-h") || argv.length === 0) {
  console.log("Usage: node lint.mjs <manifest.json | URL | -> [--check-links] [--base <origin>]");
  process.exit(2);
}
const checkLinks = argv.includes("--check-links");
const baseArg = argv[argv.indexOf("--base") + 1] && argv.includes("--base") ? argv[argv.indexOf("--base") + 1] : null;
const input = argv.find((a) => !a.startsWith("--") && a !== baseArg) || "-";

async function readInput(arg) {
  if (!arg || arg === "-") return { text: readFileSync(0, "utf8"), base: null };
  if (/^https?:\/\//i.test(arg)) {
    const res = await fetch(arg);
    if (!res.ok) throw new Error(`fetch ${arg} → HTTP ${res.status}`);
    return { text: await res.text(), base: new URL(arg).origin };
  }
  return { text: readFileSync(arg, "utf8"), base: null };
}

// At runtime Milo strips the fragment's host and resolves its PATH against the
// page origin, so test <base><path>. Fall back to the fragment's own published
// (.aem.live) host only when we don't know the origin (local file / stdin).
function toTestUrl(ref, base) {
  let path = ref;
  if (/^https?:\/\//i.test(ref)) {
    try { path = new URL(ref).pathname; } catch { return null; }
  }
  if (!path.startsWith("/")) path = "/" + path;
  if (base) return base.replace(/\/+$/, "") + path;
  if (/^https?:\/\//i.test(ref)) return ref.replace(/(--adobecom\.)(hlx|aem)\.page/i, "$1aem.live");
  return null; // relative path, no base → can't resolve
}

async function fetchStatus(url) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 10000);
  try {
    // GET, not HEAD — the adobe.com CDN hangs on HEAD. Cancel the body so we
    // don't download it; we only want the status.
    const res = await fetch(url, { method: "GET", redirect: "follow", signal: ctrl.signal });
    if (res.body) { try { await res.body.cancel(); } catch { /* ignore */ } }
    return { status: res.status };
  } catch (e) {
    return { error: e.name === "AbortError" ? "timeout" : e.message };
  } finally {
    clearTimeout(t);
  }
}

async function pool(items, n, fn) {
  const out = []; let i = 0;
  await Promise.all(Array.from({ length: Math.min(n, items.length) }, async () => {
    while (i < items.length) { const idx = i++; out[idx] = await fn(items[idx]); }
  }));
  return out;
}

async function linkCheck(manifest, base) {
  const refs = collectFragments(manifest);
  // unique by test URL, keeping one "where" for reporting
  const seen = new Map();
  for (const r of refs) {
    const url = toTestUrl(r.ref, base);
    if (!url) { seen.set("REL:" + r.ref, { rel: r.ref, where: r.where }); continue; }
    if (!seen.has(url)) seen.set(url, { url, where: r.where });
  }
  const entries = [...seen.values()];
  const findings = [];
  await pool(entries.filter((e) => e.url), 8, async (e) => {
    const { status, error } = await fetchStatus(e.url);
    if (error) findings.push({ sev: "info", where: e.where, msg: `couldn't verify (${error}): ${e.url}` });
    else if (status === 404) findings.push({ sev: "error", where: e.where, msg: `fragment not found (404): ${e.url}` });
    else if (status === 401 || status === 403) findings.push({ sev: "info", where: e.where, msg: `couldn't verify (auth ${status}): ${e.url}` });
    else if (status >= 400) findings.push({ sev: "warn", where: e.where, msg: `HTTP ${status}: ${e.url}` });
  });
  for (const e of entries.filter((e) => e.rel))
    findings.push({ sev: "info", where: e.where, msg: `relative fragment path not checked (pass --base <origin>): ${e.rel}` });
  return findings;
}

try {
  const { text, base } = await readInput(input);
  const manifest = toManifest(JSON.parse(text));
  const findings = lintManifest(manifest);
  if (checkLinks) findings.push(...await linkCheck(manifest, baseArg || base));
  const { text: report, counts } = formatFindings(findings);
  console.log(report);
  if (checkLinks && !(baseArg || base) && collectFragments(manifest).some((r) => !/^https?:/i.test(r.ref)))
    console.log("(some fragments are relative paths; pass --base <origin> to check them)");
  process.exit(counts.error ? 1 : 0);
} catch (e) {
  console.error(`Error: ${e.message}`);
  process.exit(2);
}
