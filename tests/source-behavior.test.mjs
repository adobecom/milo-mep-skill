import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(new URL("../skills/milo-mep/assets/source/personalization.js", import.meta.url), "utf8");

// Execute pinned pure functions, isolating browser/service dependencies.
function section(start, end) {
  const first = source.indexOf(start);
  const last = source.indexOf(end, first + start.length);
  assert.ok(first >= 0 && last > first, `Snapshot function boundary changed: ${start}`);
  return source.slice(first, last).replace(/^export /gm, "");
}

const matchGlob = new Function(`${section("export const matchGlob =", "export async function replaceInner(")}; return matchGlob;`)();
const parsePlaceholders = new Function("matchGlob", "createMartechMetadata", "hasCountryMatch",
  `${section("export function parsePlaceholders(", "const checkForParamMatch =")}; return parsePlaceholders;`)(
  matchGlob, () => {}, () => false,
);
const config = () => ({ locale: { region: "us", ietf: "en-US" }, mep: {} });

test("pinned phone targeting requires mobile detection and either screen dimension below 550", () => {
  const loadTags = new Function("window", "navigator",
    `${section("const getUA =", "const PERSONALIZATION_KEYS =")}; return PERSONALIZATION_TAGS;`);
  for (const [userAgent, width, height, expected] of [
    ["iPhone", 549, 900, true],
    ["iPhone", 900, 549, true],
    ["iPhone", 550, 550, false],
    ["iPhone", 900, 900, false],
    ["Desktop", 400, 400, false],
  ]) {
    const tags = loadTags({ screen: { width, height } }, { userAgent, maxTouchPoints: 0 });
    assert.equal(tags.phone(), expected, `${userAgent} ${width}x${height}`);
  }
});

const replacePlaceholders = new Function(
  `${section("export function replacePlaceholders(", "const getUpdatedHref =")}; return replacePlaceholders;`,
)();

test("pinned MEP substitution retains literal tokens for empty stored values", () => {
  for (const [row, stored, rendered] of [
    [{ key: "hero-copy", value: "General", phone: "Phone copy" }, "General", "General"],
    [{ key: "hero-copy", phone: "Phone copy", value: "General" }, "Phone copy", "Phone copy"],
    [{ key: "hero-copy", phone: "", value: "General" }, "", "{{hero-copy}}"],
  ]) {
    const state = config();
    parsePlaceholders([row], state, "phone", "/example/tool");
    assert.equal(state.placeholders["hero-copy"], stored);
    assert.equal(replacePlaceholders("{{hero-copy}}", state.placeholders), rendered);
    assert.equal(replacePlaceholders("Before {{hero-copy}} after", state.placeholders),
      `Before ${rendered} after`);
  }
});

test("pinned runtime normalizes trusted origins but retains query and other hash content", () => {
  const normalize = new Function("getConfig", "isDamContent",
    `${section("export const normalizePath =", "export const getFileName =")}; return normalizePath;`)(
    () => ({ codeRoot: "/libs", locale: { ietf: "de-DE", prefix: "/de" }, locales: { de: {} } }),
    () => false,
  );
  assert.equal(normalize("https://main--dc--adobecom.aem.live/example/fragment?mode=demo#details", false),
    "/example/fragment?mode=demo#details");
  assert.equal(normalize("https://main--dc--adobecom.aem.live/example/fragment?mode=demo#_dnt"),
    "/example/fragment?mode=demo");
});

test("pinned runtime supports page-scoped placeholder keys and a last fallback", () => {
  for (const header of ["page filter", "page filter (optional)"]) {
    const rows = [
      { key: "copy", [header]: "/example/a", value: "A" },
      { key: "copy", [header]: "/example/b", value: "B" },
      { key: "copy", value: "General" },
    ];
    for (const [path, expected] of [["/example/a", "A"], ["/example/b.html", "B"], ["/example/c", "General"]]) {
      const state = config();
      parsePlaceholders(rows, state, "all", path);
      assert.equal(state.placeholders.copy, expected);
    }
  }
});

test("pinned runtime uses the first matching placeholder row even if blank", () => {
  const state = config();
  parsePlaceholders([
    { key: "copy", value: "" },
    { key: "copy", "page filter": "/example/a", value: "Never used" },
  ], state, "all", "/example/a");
  assert.equal(state.placeholders.copy, "");
});

test("pinned runtime chooses the first eligible value column, not per-cell fallback", () => {
  for (const [row, expected] of [
    [{ key: "copy", value: "General", all: "Experience" }, "General"],
    [{ key: "copy", all: "", value: "General" }, ""],
  ]) {
    const state = config();
    parsePlaceholders([row], state, "all", "/example/a");
    assert.equal(state.placeholders.copy, expected);
  }
});

test("pinned runtime does not apply manifest placeholders for default experience", () => {
  const state = { ...config(), placeholders: { copy: "Existing global" } };
  parsePlaceholders([{ key: "copy", value: "Manifest" }], state, "default", "/example/a");
  assert.equal(state.placeholders.copy, "Existing global");
});

test("pinned runtime applies header order and page matching independently per key", () => {
  for (const [columns, expected] of [
    [["other", "de-DE", "all"], ["General A", "General subtitle"]],
    [["de-DE", "all", "other"], ["Titel A", "Untertitel"]],
  ]) {
    const state = { locale: { region: "de", ietf: "de-DE" }, mep: {} };
    const rows = [
      ["title", "/example/b", "Elsewhere", "Anderswo", "B"],
      ["title", "/example/a", "General A", "Titel A", "Audience A"],
      ["subtitle", "/example/a", "General subtitle", "Untertitel", "Audience subtitle"],
    ].map(([key, filter, other, locale, all]) => {
      const values = { other, "de-DE": locale, all };
      return Object.fromEntries([
        ["key", key], ["page filter", filter],
        ...columns.map((column) => [column, values[column]]),
      ]);
    });
    parsePlaceholders(rows, state, "all", "/example/a");
    assert.deepEqual([state.placeholders.title, state.placeholders.subtitle], expected);
  }
});

const combineMepSources = new Function("parseManifestUrlAndAddSource", "isSameOriginManifestPath", "PAGE_URL",
  `${section("export const combineMepSources =", "async function updateManifestsAndPropositions(")}; return combineMepSources;`)(
  () => [], (path) => path.startsWith("/") && !path.startsWith("//"),
  new URL("https://www.adobe.com/de/example/unrelated"),
);
const parseMepParam = new Function(`${section("function parseMepParam(", "function compareExecutionOrder(")}; return parseMepParam;`)();

test("pinned runtime attaches a preview manifest without a normal delivery source", async () => {
  const result = await combineMepSources(false, false, false, "/example/tool.json--all");
  assert.deepEqual(result, [{ manifestPath: "/example/tool.json", source: ["mep param"] }]);
  assert.equal(parseMepParam("%2Fexample%2Ftool.json--all")["/example/tool.json"], "all");
});

test("pinned runtime does not attach preview manifests with bare mep or mep=off", async () => {
  assert.deepEqual(await combineMepSources(false, false, false, ""), []);
  assert.deepEqual(await combineMepSources(false, false, false, "off"), []);
});

test("pinned runtime checks an explicit variant override before audience qualification", async () => {
  const state = { mep: { variantOverride: { "/example/tool.json": "all" } } };
  const select = new Function("getConfig",
    `${section("async function getPersonalizationVariant(", "const createDefaultExperiment =")}; return getPersonalizationVariant;`)(() => state);
  assert.equal(await select("/example/tool.json"), "all");
});

const commandKeys = {
  remove: "remove", replace: "replace", analyticIfSeen: "analyticifseen",
  updateAttribute: "updateattribute",
};
const modifySelector = new Function("COMMANDS_KEYS", "SELECTOR_TYPES", "getSelectorType",
  `${section("const updateEndNumber =", "function getSelectedElements(")}; return modifyNonFragmentSelector;`)(
  commandKeys, { twpButtons: "twpButtons" }, () => "css",
);

test("pinned runtime separates the final attribute token from selector matching and flags", () => {
  const parsed = modifySelector('a[href*="query=example"] href #_include-fragments #_all', "updateattribute");
  assert.equal(parsed.modifiedSelector, 'a[href*="query=example"]');
  assert.equal(parsed.attribute, "href");
  assert.deepEqual(parsed.modifiers, ["include-fragments", "all"]);
  assert.equal(modifySelector("any-marquee class", "updateattribute").attribute, "class");
  assert.equal(modifySelector("any-marquee [class]", "updateattribute").attribute, "[class]");
});

const updateAttribute = new Function("COMMANDS_KEYS", "replacePlaceholders", "addIds", "normalizePath",
  `${section("const COMMANDS =", "const log =")}; return COMMANDS.updateattribute;`)(
  commandKeys, (content) => content, () => {}, (path) => path,
);

test("pinned runtime replaces a complete class value rather than merging classes", () => {
  const attributes = new Map([["class", "marquee small"]]);
  const el = { setAttribute: (name, value) => attributes.set(name, value) };
  updateAttribute(el, { attribute: "class", content: "dark" });
  assert.equal(attributes.get("class"), "dark");
  updateAttribute(el, { attribute: "class", content: "marquee small dark" });
  assert.equal(attributes.get("class"), "marquee small dark");
});

test("pinned runtime updates an existing external Studio href without changing link text", () => {
  const url = "https://mas.adobe.com/studio.html#content-type=merch-card&query=22222222-2222-4222-8222-222222222222&field=shortDescription";
  const attributes = new Map([["href", "https://mas.adobe.com/studio.html#query=example"]]);
  const el = { textContent: "Existing link", setAttribute: (name, value) => attributes.set(name, value) };
  updateAttribute(el, { attribute: "href", content: url });
  assert.equal(attributes.get("href"), url);
  assert.equal(el.textContent, "Existing link");
});
