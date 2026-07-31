#!/usr/bin/env node
// Generates a SELF-CONTAINED scripts/lint.html by inlining lint-core.mjs (the
// rules) and lint-ui.js (the browser UI), so the tool works from file://
// (double-click) with no server and no rule duplication. Both are read from
// disk and interpolated verbatim — no JS lives in this template literal, so
// regexes/backslashes are never mangled.
//
//   node scripts/build-lint-html.mjs   # re-run after editing lint-core.mjs or lint-ui.js

import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const core = readFileSync(join(here, "lint-core.mjs"), "utf8").replace(/^export\s+/gm, "");
const ui = readFileSync(join(here, "lint-ui.js"), "utf8");

const html = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MEP Manifest Linter</title>
<style>
  :root { color-scheme: light dark; }
  body { font: 14px/1.5 -apple-system, system-ui, sans-serif; max-width: 860px; margin: 2rem auto; padding: 0 1rem; }
  h1 { font-size: 1.3rem; }
  .row { display: flex; gap: .5rem; margin: .5rem 0; flex-wrap: wrap; }
  input[type=url] { flex: 1; min-width: 320px; padding: .5rem; }
  textarea { width: 100%; height: 160px; font-family: ui-monospace, monospace; padding: .5rem; }
  button { padding: .5rem .9rem; cursor: pointer; }
  .f { border-left: 4px solid #999; padding: .4rem .6rem; margin: .4rem 0; background: #8881; border-radius: 3px; }
  .error { border-color: #ef3726; } .warn { border-color: #ffb300; } .info { border-color: #17a2b8; }
  .where { font-weight: 600; font-family: ui-monospace, monospace; font-size: .85em; }
  .sev { font-weight: 700; margin-right: .4rem; }
  .summary { font-weight: 600; margin-top: 1rem; }
  .hint { color: #888; font-size: .85em; }
  .ok { color: #28a745; font-weight: 700; }
</style>
</head>
<body>
  <h1>MEP Manifest Linter</h1>
  <p class="hint">Lints a <strong>published manifest <code>.json</code></strong> entirely in your browser
    (works offline, double-clickable). Fetch a URL or paste JSON. Same rules as the Node CLI.</p>
  <div class="row">
    <input id="url" type="url" placeholder="https://…/manifest.json" />
    <button id="fetchBtn">Fetch &amp; lint</button>
  </div>
  <textarea id="json" placeholder="…or paste manifest JSON here"></textarea>
  <div class="row"><button id="pasteBtn">Lint pasted JSON</button></div>
  <div class="row">
    <input id="base" type="url" placeholder="base origin for link check (e.g. https://main--dc--adobecom.aem.live)" />
    <button id="linkBtn">Check fragment links</button>
  </div>
  <p class="hint">Link check is best-effort in the browser: it can only read a status when the fragment host allows
    cross-origin requests (CORS). Blocked hosts show "couldn't verify"; use the Node CLI (<code>--check-links</code>)
    for authoritative results.</p>
  <div id="results"></div>

  <!-- inlined from lint-core.mjs; regenerate via: node scripts/build-lint-html.mjs -->
  <script>
${core}
  </script>
  <!-- inlined from lint-ui.js -->
  <script>
${ui}
  </script>
</body>
</html>
`;

writeFileSync(join(here, "lint.html"), html);
console.log("Wrote scripts/lint.html (self-contained, " + html.length + " bytes)");
