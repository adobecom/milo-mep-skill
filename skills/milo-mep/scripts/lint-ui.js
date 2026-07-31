// Browser UI for lint.html. Inlined by build-lint-html.mjs alongside lint-core
// (which exposes lintManifest / toManifest / collectFragments as globals).
// Written as a normal file (not a template literal) so regexes are verbatim.
const $ = (id) => document.getElementById(id);
const results = $("results");
const escapeHtml = (s) => { const d = document.createElement("div"); d.textContent = s; return d.innerHTML; };

function render(findings) {
  const order = { error: 0, warn: 1, info: 2 };
  const counts = { error: 0, warn: 0, info: 0 };
  findings.forEach((f) => counts[f.sev]++);
  if (!findings.length) { results.innerHTML = '<p class="ok">✓ No issues found.</p>'; return; }
  const sorted = [...findings].sort((a, b) => order[a.sev] - order[b.sev]);
  const label = { error: "ERROR", warn: "WARN", info: "INFO" };
  results.innerHTML = sorted.map((f) =>
    '<div class="f ' + f.sev + '"><span class="sev">' + label[f.sev] + '</span>' +
    '<span class="where">' + escapeHtml(f.where) + '</span><br>' + escapeHtml(f.msg) + '</div>').join("") +
    '<p class="summary">Summary: ' + counts.error + ' error(s), ' + counts.warn + ' warning(s), ' + counts.info + ' info.</p>';
}

function lintText(text) {
  try { render(lintManifest(toManifest(JSON.parse(text)))); }
  catch (e) { results.innerHTML = '<p class="f error">Could not parse JSON: ' + escapeHtml(e.message) + '</p>'; }
}

$("pasteBtn").onclick = () => lintText($("json").value);

$("fetchBtn").onclick = async () => {
  const url = $("url").value.trim(); if (!url) return;
  results.innerHTML = "<p class='hint'>Fetching…</p>";
  try {
    const res = await fetch(url); if (!res.ok) throw new Error("HTTP " + res.status);
    const text = await res.text(); $("json").value = text;
    try { if (!$("base").value) $("base").value = new URL(url).origin; } catch (e) { /* ignore */ }
    lintText(text);
  } catch (e) {
    results.innerHTML = '<p class="f error">Fetch failed (' + escapeHtml(e.message) +
      '). If CORS-blocked, open the URL in a tab, copy the JSON, and paste it above.</p>';
  }
};

// ---- best-effort fragment link check (CORS-limited in the browser) ----
function toTestUrl(ref, base) {
  let path = ref;
  if (/^https?:\/\//i.test(ref)) { try { path = new URL(ref).pathname; } catch (e) { return null; } }
  if (!path.startsWith("/")) path = "/" + path;
  if (base) return base.replace(/\/+$/, "") + path;
  if (/^https?:\/\//i.test(ref)) return ref.replace(/(--adobecom\.)(hlx|aem)\.page/i, "$1aem.live");
  return null;
}

async function fragStatus(url) {
  const c = new AbortController();
  const t = setTimeout(() => c.abort(), 10000);
  try { const r = await fetch(url, { redirect: "follow", signal: c.signal }); return { status: r.status }; }
  catch (e) { return { error: e.name === "AbortError" ? "timeout" : (e.message || "CORS/network") }; }
  finally { clearTimeout(t); }
}

async function pool(items, n, fn) {
  let i = 0;
  await Promise.all(Array.from({ length: Math.min(n, items.length) }, async () => {
    while (i < items.length) { await fn(items[i++]); }
  }));
}

$("linkBtn").onclick = async () => {
  let manifest;
  try { manifest = toManifest(JSON.parse($("json").value)); }
  catch (e) { results.innerHTML = '<p class="f error">Parse the JSON first: ' + escapeHtml(e.message) + '</p>'; return; }
  const base = $("base").value.trim() || null;
  const refs = collectFragments(manifest);
  if (!refs.length) { results.innerHTML = '<p class="ok">No fragment references to check.</p>'; return; }
  results.innerHTML = "<p class='hint'>Checking " + refs.length + " fragment reference(s)…</p>";
  const seen = new Map();
  for (const r of refs) {
    const url = toTestUrl(r.ref, base);
    if (!url) { seen.set("REL:" + r.ref, { rel: r.ref, where: r.where }); continue; }
    if (!seen.has(url)) seen.set(url, { url, where: r.where });
  }
  const entries = [...seen.values()];
  const findings = [];
  await pool(entries.filter((e) => e.url), 6, async (e) => {
    const { status, error } = await fragStatus(e.url);
    if (error) findings.push({ sev: "info", where: e.where, msg: "couldn't verify (" + error + "): " + e.url });
    else if (status === 404) findings.push({ sev: "error", where: e.where, msg: "fragment not found (404): " + e.url });
    else if (status === 401 || status === 403) findings.push({ sev: "info", where: e.where, msg: "couldn't verify (auth " + status + "): " + e.url });
    else if (status >= 400) findings.push({ sev: "warn", where: e.where, msg: "HTTP " + status + ": " + e.url });
  });
  for (const e of entries.filter((e) => e.rel))
    findings.push({ sev: "info", where: e.where, msg: "relative path not checked (set a base origin above): " + e.rel });
  const checked = entries.filter((e) => e.url).length;
  if (!findings.some((f) => f.sev !== "info"))
    findings.unshift({ sev: "info", where: "link check", msg: checked + " fragment URL(s) checked; no 404s among those the browser could read." });
  render(findings);
};
