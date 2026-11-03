import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { collectFragments, formatFindings, lintManifest, toManifest } from "../skills/milo-mep/scripts/lint-core.mjs";

const cli = fileURLToPath(new URL("../skills/milo-mep/scripts/lint.mjs", import.meta.url));
const columns = ["action", "selector", "page filter (optional)", "all"];
const row = { action: "replace", selector: "any-marquee", all: "/fragments/hero" };
const manifest = (rows = [row], cols = columns) => ({
  experiences: { columns: cols, rows },
});
const findings = (rows, cols) => lintManifest(manifest(rows, cols));
const has = (items, sev, pattern) => items.some((f) => f.sev === sev && pattern.test(f.msg));

test("published JSON and normalized XLSX have identical findings", () => {
  const rows = [{ Action: "remvoe", Selector: "any-marquee", All: "true" }];
  const published = { ":type": "multi-sheet", experiences: { columns: ["Action", "Selector", "All"], data: rows } };
  const normalized = { "helix-experiences": { columns: ["Action", "Selector", "All"], rows } };
  const a = lintManifest(toManifest(published));
  const b = lintManifest(toManifest(normalized));
  assert.deepEqual(a.map(({ sev, msg }) => ({ sev, msg })), b.map(({ sev, msg }) => ({ sev, msg })));
  assert.ok(has(a, "error", /did you mean 'remove'/));
});

for (const [name, rows, cols, severity, pattern] of [
  ["missing action", [{ ...row, action: "" }], columns, "error", /no action/],
  ["missing selector", [{ ...row, selector: "" }], columns, "error", /requires a selector/],
  ["all shadows phone", [row], [...columns, "phone"], "error", /isn't last/],
  ["empty experience", [{ ...row, all: "" }], columns, "warn", /does nothing/],
  ["remove typo", [{ action: "remove", selector: "any-marquee", all: "false " }], columns, "warn", /not exactly true\/false\/1/],
  ["comma page filter", [{ ...row, "page filter (optional)": "**/uk/**, **/it/**" }], columns, "error", /comma/],
  ["locale separator typo", [{ ...row, "page filter (optional)": "/(be_fr/ca_fr)/example" }], columns, "error", /inside the locale group/],
  ["broken regex", [{ ...row, "page filter (optional)": "/(uk" }], columns, "error", /not a valid regex/],
  ["undefined placeholder", [{ ...row, all: "{{offer}}" }], columns, "warn", /not defined/],
  ["duplicate header", [row], [...columns, "all"], "warn", /duplicate experience column/],
]) {
  test(name, () => assert.ok(has(findings(rows, cols), severity, pattern)));
}

test("misspelled sheet is reported rather than normalized away", () => {
  const result = lintManifest(toManifest({ experienxes: { columns, data: [row] } }));
  assert.ok(has(result, "error", /did you mean 'experiences'/));
  assert.ok(has(result, "error", /no 'experiences' sheet/));
});

test("missing consent explains both source-dependent defaults", () => {
  const m = manifest();
  m.info = { columns: ["key", "value"], rows: [{ key: "manifest-type", value: "Promo" }] };
  const result = lintManifest(m);
  assert.ok(has(result, "info", /personalized offer.*performance \+ advertising.*promo-sourced.*promo or no offer changes/));
  m.info.rows.push({ key: "manifest-consent-type", value: "promo or no offer changes" });
  assert.ok(!has(lintManifest(m), "info", /no consent type/));
});

for (const [name, rows] of [
  ["path alternation", [{ ...row, "page filter (optional)": "(/|/homepage/index-loggedout)" }]],
  ["regex quantifier comma", [{ ...row, "page filter (optional)": "/example/[a-z]{2,3}" }]],
  ["mixed trusted fragment domains", [{ ...row, selector: "https://main--dc--adobecom.hlx.page/fragments/old", all: "https://main--da-dc--adobecom.aem.live/fragments/new" }]],
  ["prepend and append on fragment selectors", ["prepend", "append"].map((action) => ({ ...row, action, selector: "/fragments/old" }))],
  ["remove boolean values", ["TRUE", "false", "1"].map((all) => ({ action: "remove", selector: "any-marquee", all }))],
  ["replacePage on distinct pages", ["/one", "/two"].map((filter) => ({ ...row, action: "replacePage", selector: "", "page filter (optional)": filter }))],
]) {
  test(`known non-issue: ${name}`, () => assert.deepEqual(findings(rows), []));
}

test("replacePage sharing a page filter warns", () => {
  assert.ok(has(findings([1, 2].map(() => ({ ...row, action: "replacePage", selector: "" }))), "warn", /only the first applies/));
});

test("fragment collection strips flags and ignores attribute URLs", () => {
  assert.deepEqual(collectFragments(manifest([
    { ...row, selector: "/fragments/old #_include-fragments", all: "/fragments/new#_dnt" },
    { action: "updateAttribute", selector: "primary-cta href", all: "https://www.adobe.com/buy" },
  ])), [
    { where: "row 1 selector", ref: "/fragments/old" },
    { where: "row 1 [all]", ref: "/fragments/new" },
  ]);
});

test("report sorts by severity and preserves counts", () => {
  const report = formatFindings([
    { sev: "info", where: "info", msg: "note" },
    { sev: "error", where: "row", msg: "broken" },
    { sev: "warn", where: "row", msg: "suspect" },
  ]);
  assert.deepEqual(report.counts, { error: 1, warn: 1, info: 1 });
  assert.ok(report.text.indexOf("ERROR") < report.text.indexOf("WARN"));
});

test("CLI distinguishes clean, lint error and invalid JSON", () => {
  for (const [input, status, pattern] of [
    [JSON.stringify(manifest()), 0, /No issues found/],
    [JSON.stringify(manifest([{ ...row, action: "remvoe" }])), 1, /unknown action/],
    ["{", 2, /Error:/],
  ]) {
    const result = spawnSync(process.execPath, [cli, "-"], { input, encoding: "utf8" });
    assert.equal(result.status, status, result.stderr);
    assert.match(result.stdout + result.stderr, pattern);
  }
});
