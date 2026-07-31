// MEP manifest linter — canonical rule engine. Dependency-free; runs in Node
// and the browser. This is the ONE place the rules live: the Node CLI
// (lint.mjs), the browser tool (lint.html), and the xlsx path (lint_manifest.py,
// which shells out to Node) all use it, so the rules never drift.
//
// Rules mirror references/source-notes.md. NOT flagged (verified non-issues):
// mixed fragment-URL domains, prepend/append on fragment selectors, 1 vs TRUE.

const INFO_KEYS = new Set([
  "action", "selector", "page filter", "page filter (optional)", "pagefilter",
]);
const TRUSTED_HOST = /(^|\.)adobe\.com$|--adobecom\.(hlx|aem)\.(page|live)$/;

// Accepts either the published-JSON shape ({experiences:{data,columns},…}) or
// the normalized shape from mep_xlsx ({ "helix-experiences": {columns,rows} }).
// Keeps EVERY sheet-like key (including misspelled ones) so structural checks
// can flag them.
export function toManifest(json) {
  if (!json || typeof json !== "object") return json;
  const isPublished = json[":type"] || json[":names"] ||
    Object.entries(json).some(([k, v]) => !k.startsWith(":") && v && Array.isArray(v.data));
  const raw = {};
  if (isPublished) {
    for (const [k, v] of Object.entries(json)) {
      if (k.startsWith(":")) continue;
      if (v && Array.isArray(v.data)) raw[k] = { columns: v.columns || [], rows: v.data };
    }
  } else {
    for (const [k, v] of Object.entries(json)) // already {sheet:{columns,rows}}
      if (v && typeof v === "object" && (Array.isArray(v.rows) || Array.isArray(v.data) || "columns" in v))
        raw[k] = { columns: v.columns || [], rows: v.rows || v.data || [] };
    if (!Object.keys(raw).length) return json;
  }
  // Normalize like the runtime: lowercase every key (normalizeKeys), and derive
  // the column list from the row keys when it's absent (e.g. pasted JSON).
  const out = {};
  for (const [k, s] of Object.entries(raw)) {
    const rows = (s.rows || []).map((r) => {
      const nr = {};
      for (const [kk, vv] of Object.entries(r || {})) nr[String(kk).toLowerCase()] = vv;
      return nr;
    });
    let cols = (s.columns || []).map((c) => String(c).toLowerCase());
    if (!cols.length) {
      const seen = new Set();
      for (const r of rows) for (const kk of Object.keys(r)) if (!seen.has(kk)) { seen.add(kk); cols.push(kk); }
    }
    out[k] = { columns: cols, rows };
  }
  return out;
}

// Levenshtein distance + nearest known name (for "did you mean" suggestions).
function _lev(a, b) {
  const m = a.length, n = b.length;
  const d = Array.from({ length: m + 1 }, (_, i) => [i, ...Array(n).fill(0)]);
  for (let j = 0; j <= n; j++) d[0][j] = j;
  for (let i = 1; i <= m; i++)
    for (let j = 1; j <= n; j++)
      d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1,
        d[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
  return d[m][n];
}
function _nearest(name, candidates, max = 2) {
  let best = null, bestD = max + 1;
  for (const c of candidates) {
    const dist = _lev(name.toLowerCase(), c.toLowerCase());
    if (dist < bestD) { bestD = dist; best = c; }
  }
  return bestD <= max ? best : null;
}

const sheet = (m, ...names) => {
  for (const n of names) if (m[n]) return m[n];
  return { columns: [], rows: [] };
};

const isUrl = (v) =>
  typeof v === "string" &&
  /^https?:\/\//i.test(v.trim()) && !v.trim().includes(" ") && !v.includes("<");

function trusted(url) {
  const u = String(url).trim();
  if (u.startsWith("/") && !u.startsWith("//")) return true; // same-origin path
  const m = u.match(/^https?:\/\/([^/]+)/i);
  if (!m) return true; // not a URL → N/A
  const host = m[1].split("@").pop().split(":")[0].toLowerCase();
  return TRUSTED_HOST.test(host);
}

const pageFilterOf = (row) =>
  row["page filter (optional)"] ?? row["page filter"] ?? row["pagefilter"] ?? "";

// A value that looks like a fragment/URL/path (not inline text or HTML).
const pathLike = (v) =>
  typeof v === "string" && v.trim() !== "" && !v.includes(" ") && !v.includes("<") &&
  (/^https?:\/\//i.test(v) || v.startsWith("/") || (v.includes("/") && !v.includes("{{")));

const ACTIONS = new Set([
  "remove", "replace", "updateattribute", "analyticifseen", "insertbefore",
  "insertafter", "prepend", "append", "insertscript", "replacepage",
  "updateframework", "updatemetadata", "useblockcode",
]);
const SELECTOR_REQUIRED = new Set([
  "remove", "replace", "updateattribute", "analyticifseen", "insertbefore",
  "insertafter", "prepend", "append", "updatemetadata",
]);
const SELECTOR_UNUSED = new Set(["replacepage", "useblockcode", "insertscript", "updateframework"]);
const TAGS = ["all", "chrome", "firefox", "safari", "edge", "android", "ios",
  "windows", "mac", "mobile-device", "phone", "tablet", "desktop", "loggedout", "loggedin"];
const FLAGS = new Set(["all", "include-fragments", "include-gnav", "dnt", "inline", "href"]);
// mirrors the source: lowercase, then strip content/fragment/tosection (first occurrence)
const normAction = (a) =>
  a.toLowerCase().replace("content", "").replace("fragment", "").replace("tosection", "");

/**
 * Lint a normalized manifest. Returns an array of { sev, where, msg }.
 * sev ∈ "error" | "warn" | "info".
 */
export function lintManifest(m) {
  const out = [];
  const add = (sev, where, msg) => out.push({ sev, where, msg });

  // ---- structure: sheet names ----
  const KNOWN = ["info", "experiences", "placeholders", "readme"];
  const deHelix = (k) => k.replace(/^helix-/, "");
  const sheetKeys = Object.keys(m).filter(
    (k) => m[k] && typeof m[k] === "object" && ("columns" in m[k] || "rows" in m[k]));
  for (const k of sheetKeys) {
    if (KNOWN.includes(deHelix(k))) continue;
    const sug = _nearest(deHelix(k), KNOWN);
    if (sug) {
      const fix = (k.startsWith("helix-") ? "helix-" : "") + sug;
      add("error", `sheet '${k}'`, `unrecognized sheet name '${k}' — did you mean '${fix}'? Milo only reads info/experiences/placeholders, so as-is this sheet is ignored.`);
    } else {
      add("warn", `sheet '${k}'`, `unrecognized sheet '${k}' — Milo reads info/experiences/placeholders; this sheet is ignored.`);
    }
  }
  const hasExperiences = sheetKeys.some(
    (k) => deHelix(k) === "experiences" && (m[k].columns || []).length);
  if (!hasExperiences)
    add("error", "structure", "no 'experiences' sheet with columns found — the manifest defines no changes to apply (check the sheet name spelling).");

  // ---- info ----
  const infoSheet = sheet(m, "helix-info", "info");
  const info = {};
  for (const r of infoSheet.rows || []) if (r.key != null) info[r.key] = r.value ?? "";
  const mt = (info["manifest-type"] || "").trim();
  if (Object.keys(info).length) {
    if (mt && !["Personalization", "Promo", "Test"].includes(mt))
      add("error", "info", `manifest-type '${mt}' is not Personalization/Promo/Test.`);
    const eo = (info["manifest-execution-order"] || "").trim();
    if (eo && !["First", "Normal", "Last"].includes(eo))
      add("error", "info", `manifest-execution-order '${eo}' is not First/Normal/Last.`);
    const on = (info["manifest-override-name"] || "").trim();
    if (on.length > 15)
      add("warn", "info", `manifest-override-name '${on}' is ${on.length} chars; analytics truncates to 15.`);
    if (on && !/^[a-z0-9-]+$/.test(on))
      add("warn", "info", `manifest-override-name '${on}' should be lowercase letters, numbers, and dashes only (it's passed to analytics).`);
    if (on && mt && mt !== "Personalization")
      add("info", "info", "manifest-override-name is ignored for non-Personalization manifests.");
    if (!(info["manifest-marketing-action"] || "").trim()) {
      if (mt === "Promo")
        add("info", "info", "no manifest-marketing-action → promo default is 'core services/non-marketing' (always serves).");
      else
        add("info", "info", "no manifest-marketing-action → defaults to 'marketing increase' (advertising consent required); set it deliberately if this should serve pre-consent.");
    }
  }

  // ---- placeholders defined ----
  const ph = sheet(m, "helix-placeholders", "placeholders");
  const defined = new Set(
    (ph.rows || []).map((r) => (r.key || "").trim()).filter(Boolean)
  );

  // ---- experiences ----
  const exp = sheet(m, "helix-experiences", "experiences");
  const columns = exp.columns || [];
  const expCols = columns.filter((c) => !INFO_KEYS.has(String(c).toLowerCase()));
  const rows = exp.rows || [];

  // duplicate experience column headers
  const seenCols = new Set();
  for (const c of expCols) {
    if (seenCols.has(c)) add("warn", "experiences header", `duplicate experience column '${c}'.`);
    seenCols.add(c);
  }
  // near-miss of a built-in tag (only for simple single-token headers, to avoid
  // flagging legit data-driven entitlement tags)
  for (const c of expCols) {
    const h = String(c);
    const simple = !/[,&:]|\bnot\b|\s/.test(h) &&
      !/^(param-|target-|previouspage-|countryip|lob-|registered$)/i.test(h);
    if (!simple) continue;
    const lower = h.toLowerCase();
    if (TAGS.includes(lower)) continue;
    const near = _nearest(lower, TAGS, 2);
    if (near) add("warn", "experiences header", `experience column '${h}' looks like a typo of the tag '${near}' — as-is it won't match any built-in audience (ignore if it's an entitlement tag).`);
  }
  // a `key=value` header without the `param-` prefix (only param- uses `=`)
  for (const c of expCols) {
    const h = String(c);
    if (h.includes("=") && !/^param-/i.test(h.trim()) && !/^(target-|previouspage-|countryip)/i.test(h.trim()))
      add("error", "experiences header", `experience column '${h}' has '=' but no 'param-' prefix — a URL-param condition must be written 'param-${h.trim()}'; as-is it matches no audience and the whole column never applies.`);
  }
  // an 'all' (matches-everyone) column that isn't last shadows the columns to its right
  const allIdx = expCols.findIndex((c) => String(c).trim().toLowerCase() === "all");
  if (allIdx !== -1 && allIdx < expCols.length - 1)
    add("error", "experiences header", `the 'all' column matches everyone but isn't last — the first matching column wins, so columns to its right (${expCols.slice(allIdx + 1).join(", ")}) will never apply.`);

  // scope inconsistency map
  const baseMap = new Map();
  rows.forEach((row, i) => {
    const pf = String(pageFilterOf(row)).trim();
    if (!pf) return;
    const localized = pf.startsWith("**") || pf.startsWith("/(") || pf.includes("/**/");
    const base = pf.replace(/^\*\*/, "").replace(/^\/+/, "");
    if (!baseMap.has(base)) baseMap.set(base, []);
    baseMap.get(base).push({ i, localized, pf });
  });

  rows.forEach((row, i) => {
    const n = i + 1;
    const action = String(row.action || "").trim().toLowerCase();
    const selector = String(row.selector || "").trim();
    if (!action) {
      const hasContent = selector || String(pageFilterOf(row)).trim() ||
        expCols.some((c) => String(row[c] ?? "").trim());
      if (hasContent)
        add("error", `experiences row ${n}`, "row has a selector/values but no action → the row is skipped at runtime.");
      return;
    }
    const where = `experiences row ${n} (action=${action || "∅"}, selector=${selector.slice(0, 40) || "∅"})`;
    const nonblank = expCols
      .map((c) => [c, row[c] ?? ""])
      .filter(([, v]) => String(v).trim() !== "");

    if (nonblank.length === 0)
      add("warn", where, "row has an action but no value in any experience column → does nothing.");

    // unknown / misspelled action
    const na = normAction(action);
    if (!ACTIONS.has(na)) {
      const sug = _nearest(na, [...ACTIONS]);
      add("error", where, `unknown action '${row.action}'${sug ? ` — did you mean '${sug}'?` : ""} (unrecognized actions are silently ignored).`);
    } else {
      // required selector missing / stray selector on a global action
      if (SELECTOR_REQUIRED.has(na) && !selector)
        add("error", where, `action '${na}' requires a selector, but it's empty → nothing to act on.`);
      if (SELECTOR_UNUSED.has(na) && selector)
        add("warn", where, `action '${na}' ignores the selector; a value there is flagged as erroneous by the template.`);
      // updateAttribute needs the attribute appended to the selector
      if (na === "updateattribute" && selector && !selector.replace(/\s*#_[^\s]+/g, "").trim().includes(" "))
        add("warn", where, "updateAttribute selector should end with the attribute name (e.g. `… primary-cta href`).");
    }

    // unknown #_ flag in the selector
    for (const fm of selector.matchAll(/#_([a-z0-9-]+)/gi))
      if (!FLAGS.has(fm[1].toLowerCase()))
        add("warn", where, `unknown selector flag '#_${fm[1]}' — valid flags: #_all, #_include-fragments, #_include-gnav, #_dnt, #_inline, #_href.`);

    // insertScript URL must be the production URL (doesn't adjust preview→prod)
    if (na === "insertscript")
      for (const [c, v] of nonblank)
        if (/--adobecom\.(hlx|aem)\.page/i.test(String(v)))
          add("warn", where, `insertScript URL in [${c}] points at a preview host; insertScript URLs don't adjust preview→prod — use the production URL.`);

    // updateFramework value must be like c1/c2 or it's ignored
    if (na === "updateframework")
      for (const [c, v] of nonblank)
        if (!/^c\d+$/i.test(String(v).trim()))
          add("warn", where, `updateFramework value '${v}' in [${c}] should be a foundation code like 'c1'/'c2', or it's ignored.`);

    // updateAttribute href of javascript:/data: is rejected at runtime
    if (na === "updateattribute")
      for (const [c, v] of nonblank)
        if (/^\s*(javascript|data):/i.test(String(v)))
          add("warn", where, `updateAttribute value in [${c}] is a javascript:/data: URL — rejected at runtime for security.`);

    // a fragment-looking value that isn't a URL/path is injected as literal text
    if (["replace", "insertbefore", "insertafter", "prepend", "append"].includes(na))
      for (const [c, v] of nonblank) {
        const vs = String(v).trim();
        if (!vs.startsWith("/") && !/^https?:\/\//i.test(vs) && !vs.includes(" ") && !vs.includes("<") &&
            /(--adobecom|\/fragments\/|\.aem\.|\.hlx\.)/i.test(vs))
          add("warn", where, `value in [${c}] looks like a fragment path but doesn't start with '/' or 'https://' → it'll be injected as literal text, not fetched: ${vs.slice(0, 80)}`);
      }

    if (action === "remove") {
      for (const [c, v] of nonblank) {
        const vs = String(v);
        if (!["true", "false", "1"].includes(vs.toLowerCase()))
          add("warn", where, `remove value '${vs}' in [${c}] is not exactly true/false/1 — remove fires for anything except 'false', so this deletes the element (typo of 'false'? stray space? '0'/'no'?).`);
        else if (vs !== vs.trim())
          add("warn", where, `remove value in [${c}] has surrounding whitespace → treated as truthy (removes).`);
      }
    }

    for (const [c, v] of nonblank)
      if (isUrl(String(v)) && !trusted(String(v)))
        add("error", where, `value in [${c}] is an untrusted URL host → dropped at runtime: ${String(v).slice(0, 80)}`);
    if (isUrl(selector) && !trusted(selector))
      add("error", where, `selector is an untrusted URL host → won't match: ${selector.slice(0, 80)}`);

    // backslash in a fragment path/URL (typo for '/')
    for (const [c, v] of nonblank)
      if (pathLike(String(v)) && String(v).includes("\\"))
        add("warn", where, `backslash in the path in [${c}] — use '/'. An absolute http(s) URL gets auto-corrected by the URL parser, but it's unintended and a relative path would break: ${String(v).slice(0, 90)}`);
    if (pathLike(selector) && selector.includes("\\"))
      add("warn", where, "backslash in the selector path — use '/' (auto-corrected for absolute URLs, but breaks relative paths).");

    for (const [c, v] of nonblank)
      for (const key of String(v).matchAll(/\{\{\s*([^}]+?)\s*\}\}/g))
        if (!defined.has(key[1]))
          add("warn", where, `placeholder {{${key[1]}}} in [${c}] is not defined on the placeholders sheet (renders literally unless a global placeholder covers it).`);

    const pf = String(pageFilterOf(row)).trim();
    if (pf) {
      if (pf.includes("\\"))
        add("error", where, `page filter contains a backslash — likely a typo for '|' (e.g. \`be_nl\\nl\` should be \`be_nl|nl\`); it compiles as a regex and won't match: ${pf}`);
      // comma-separated paths: the page filter is a single regex, NOT a list.
      // A comma is a literal char (paths don't contain commas) so it never
      // matches — use grouped alternation instead. Ignore commas inside a
      // {n,m} regex quantifier to avoid false positives.
      if (/,/.test(pf.replace(/\{\d*,\d*\}/g, "")))
        add("error", where, `page filter has a comma — it is a single regex, not a comma-separated list, so a comma is a literal character that won't match a path. Use grouped alternation instead, e.g. \`**/uk/products/**, **/it/products/**\` → \`**/(uk|it)/products/**\`: ${pf}`);
      // stray '/' (or missing '|') inside the locale alternation group
      const gStart = pf.indexOf("(");
      const gEnd = pf.lastIndexOf(")");
      if (gStart !== -1 && gEnd > gStart) {
        const group = pf.slice(gStart + 1, gEnd);
        // A '/' inside the group is only a typo-for-'|' when the group is a
        // locale-code alternation (e.g. `be_fr/ca_fr`). A group that already
        // uses '|', or whose alternatives are paths (e.g.
        // `(/|/homepage/index-loggedout)`), is a legitimate path-alternation —
        // don't flag it.
        if (!group.includes("|")
          && /^[a-z]{2,3}(_[a-z]{2,3})?(\/[a-z]{2,3}(_[a-z]{2,3})?)+$/i.test(group.trim()))
          add("error", where, `page filter has a '/' inside the locale group (…) — likely a typo for '|' (e.g. \`be_fr/ca_fr\` should be \`be_fr|ca_fr\`); those locales won't match: ${pf}`);
        if (/\s/.test(group))
          add("warn", where, `page filter has whitespace inside the locale group (e.g. \`jp \`) — that locale won't match: ${pf}`);
      }
      // lone '*' (only '**' is a wildcard; a single '*' is a regex quantifier)
      if (pf.replaceAll("**", "").includes("*"))
        add("warn", where, `page filter has a single '*' — only '**' is an MEP wildcard; a lone '*' is treated as a regex quantifier: ${pf}`);
      // must start with '/' or '**' (the match is anchored ^…$) — a leading
      // '(' is fine too (an alternation group like `(/|/x)` or a negative
      // lookahead like `(?!be_fr)**/…`).
      if (!/^[/*(]/.test(pf))
        add("warn", where, `page filter should start with '/', '**', or a '(' group — the match is anchored, so '${pf}' won't match a page path.`);
      try {
        new RegExp("^" + pf.replaceAll("**", ".*") + "(\\.html)?$");
      } catch (e) {
        add("error", where, `page filter is not a valid regex (${e.message}): ${pf}`);
      }
    }
  });

  for (const [base, entries] of baseMap) {
    const locs = new Set(entries.map((e) => e.localized));
    if (locs.size > 1)
      for (const e of entries)
        if (!e.localized)
          add("info", `experiences row ${e.i + 1}`, `page filter '${e.pf}' is exact (US-only); sibling rows for '${base}' use '**' (all locales) — did this row mean '**/${base}'?`);
  }

  // replacePage: only the first applies PER PAGE. Multiple replacePage rows are
  // legitimate when scoped to different page filters (one page each). Only warn
  // when two+ can match the SAME page — i.e. they share a page filter, or are
  // blank (a blank filter matches every page the manifest runs on).
  const rpFilters = rows
    .filter((r) => normAction(String(r.action || "").trim()) === "replacepage"
      && expCols.some((c) => String(r[c] ?? "").trim()))
    .map((r) => String(pageFilterOf(r)).trim());
  const rpByFilter = {};
  for (const f of rpFilters) rpByFilter[f] = (rpByFilter[f] || 0) + 1;
  for (const [f, n] of Object.entries(rpByFilter))
    if (n > 1)
      add("warn", "experiences", `${n} replacePage rows ${f === "" ? "have no page filter, so they all match every page the manifest runs on" : `share the page filter \`${f}\``} — only the first applies on that page; the rest are ignored. (replacePage rows with distinct page filters are fine.)`);

  return out;
}

// Collect fragment references (for the optional link-check). Returns
// [{ where, ref }] for fragment-URL selectors and content-action values.
export function collectFragments(m) {
  const exp = sheet(m, "helix-experiences", "experiences");
  const columns = exp.columns || [];
  const expCols = columns.filter((c) => !INFO_KEYS.has(String(c).toLowerCase()));
  const rows = exp.rows || [];
  const CONTENT = new Set(["replace", "insertbefore", "insertafter", "prepend", "append", "replacepage"]);
  const isFrag = (s) => typeof s === "string" && (s.trim().startsWith("/") || /^https?:\/\//i.test(s.trim()));
  const refs = [];
  rows.forEach((row, i) => {
    const na = normAction(String(row.action || "").trim());
    const selector = String(row.selector || "").trim().split(/\s*#_/)[0];
    if (isFrag(selector)) refs.push({ where: `row ${i + 1} selector`, ref: selector.split("#")[0] });
    if (!CONTENT.has(na)) return;
    for (const c of expCols) {
      const v = String(row[c] ?? "").trim();
      if (isFrag(v) && !v.includes("<") && !v.includes(" "))
        refs.push({ where: `row ${i + 1} [${c}]`, ref: v.split("#")[0] });
    }
  });
  return refs;
}

export function formatFindings(findings) {
  const order = { error: 0, warn: 1, info: 2 };
  const icon = { error: "✗ ERROR", warn: "⚠ WARN", info: "ℹ INFO" };
  const sorted = [...findings].sort((a, b) => order[a.sev] - order[b.sev]);
  const counts = { error: 0, warn: 0, info: 0 };
  findings.forEach((f) => counts[f.sev]++);
  if (!findings.length) return { text: "✓ No issues found.", counts };
  const lines = sorted.map((f) => `${icon[f.sev]}  ${f.where}\n        ${f.msg}`);
  lines.push(`\nSummary: ${counts.error} error(s), ${counts.warn} warning(s), ${counts.info} info.`);
  return { text: lines.join("\n"), counts };
}
