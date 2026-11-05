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

test("pinned runtime skips blank selected-experience cells rather than inheriting all", () => {
  const parseRow = new Function(
    "getConfig", "getFileName", "PAGE_URL", "TARGET_EXP_PREFIX", "getSelectorType",
    "COMMANDS", "SELECTOR_TYPES", "GLOBAL_CMDS", "CREATE_CMDS",
    `${section("const getVariantInfo =", "export function parseManifestVariants(")}; return getVariantInfo;`,
  )(
    config, () => "tool.json", new URL("https://www.adobe.com/example"),
    "target-", () => "css", { updateattribute: true, remove: true },
    { fragment: "fragment" }, [], {},
  );
  const variants = {
    firefox: { commands: [], fragments: [] },
    all: { commands: [], fragments: [] },
  };
  const names = Object.keys(variants);
  const unrelated = {
    action: "updateAttribute", selector: ".existing-link href",
    firefox: "", all: "/example/existing-destination",
  };
  parseRow(unrelated, names, variants, "/example/tool.json");
  parseRow({ action: "remove", selector: ".promo-banner", firefox: "TRUE", all: "" },
    names, variants, "/example/tool.json");
  assert.deepEqual(variants.firefox.commands.map(({ selector }) => selector), [".promo-banner"]);
  assert.deepEqual(variants.all.commands.map(({ selector }) => selector), [".existing-link href"]);
  parseRow({ ...unrelated, firefox: unrelated.all }, names, variants, "/example/tool.json");
  assert.equal(variants.firefox.commands[1].content, "/example/existing-destination");
});

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

test("pinned manifest priority sorts by execution order, then type, then incoming order", async () => {
  const getManifestConfig = new Function(
    "normalizePath", "createDefaultExperiment", "fetchData", "DATA_TYPE", "recordManifestError",
    "parseManifestVariants", "log", "getFileName", "TRACKED_MANIFEST_TYPE", "normalizeConsentType",
    "PERSONALIZED_OFFER", "setCountryEnabled", "setConsentEnabled", "PROMO_OR_NO_OFFER_CHANGES",
    "sendAnalytics", "getPersonalizationVariant",
    `${section("async function getManifestConfig(", "const normalizeFragPaths =")}; return getManifestConfig;`,
  )(
    (path) => path, () => null, async () => null, {}, () => {},
    () => ({ variantNames: ["all"], variants: { all: { commands: [], fragments: [] } } }),
    () => {}, (path) => path.split("/").pop(), "test or promo", (value) => value,
    "personalized offer", () => {}, () => {}, "promo or no offer changes",
    () => {}, async () => "all",
  );
  const load = (manifestPath, info) => getManifestConfig({
    manifestPath,
    manifestData: { experiences: { data: [] } },
    manifestInfo: info && Object.entries(info).map(([key, value]) => ({ key, value })),
  });
  const order = "manifest-execution-order";
  const type = "manifest-type";
  const incoming = [
    await load("/m/last-pers.json", { [order]: "Last", [type]: "Personalization" }),
    await load("/m/normal-promo.json", { [order]: "Normal", [type]: "Promo" }),
    await load("/m/normal-test.json", { [order]: "Normal", [type]: "Test" }),
    await load("/m/wrong-case.json", { [order]: "first", [type]: "personalization" }),
    await load("/m/first-test.json", { [order]: "First", [type]: "Test" }),
    await load("/m/normal-pers.json", { [order]: "Normal", [type]: "Personalization" }),
    await load("/m/no-info.json"),
  ];
  // Unknown or wrong-case values fall back to Normal/Promo, the same as no info tab.
  assert.deepEqual(incoming.map(({ executionOrder }) => executionOrder),
    ["2-0", "1-1", "1-2", "1-1", "0-2", "1-0", "1-1"]);

  const cleanAndSort = new Function("normalizePath", "getConfig", "parsePlaceholders", "log", "window",
    `${section("function compareExecutionOrder(", "export function handleFragmentCommand(")}; return cleanAndSortManifestList;`,
  )((path) => path, () => ({ mep: {} }), () => {}, () => {}, {});
  assert.deepEqual(cleanAndSort(incoming, { mep: {} }).map(({ manifestPath }) => manifestPath), [
    "/m/first-test.json",
    "/m/normal-pers.json",
    "/m/normal-promo.json",
    "/m/wrong-case.json",
    "/m/no-info.json",
    "/m/normal-test.json",
    "/m/last-pers.json",
  ]);
});

test("pinned commands complete on the first match; include-fragments widens scope, not uniqueness", async () => {
  const root = (name, count) => {
    const els = Array.from({ length: count }, (_, index) => ({ id: `${name}-${index + 1}` }));
    return { querySelector: () => null, querySelectorAll: () => els, contains: (el) => els.includes(el) };
  };
  const runner = (page) => {
    const applied = [];
    const getSelectedElements = new Function(
      "document", "getSelectorType", "SELECTOR_TYPES", "normalizePath", "modifyNonFragmentSelector", "FLAGS", "log",
      `${section("function getSelectedElements(", "const addHash =")}; return getSelectedElements;`,
    )(page, () => "css", { fragment: "fragment", twpButtons: "twp-buttons" }, (path) => path,
      modifySelector, { all: "all", includeFragments: "include-fragments" }, () => {});
    const handleCommands = new Function(
      "document", "addSectionAnchors", "getSelectorType", "SELECTOR_TYPES", "INLINE_HASH", "addHash",
      "IN_BLOCK_SELECTOR_PREFIX", "registerInBlockActions", "getSelectedElements", "COMMANDS", "CREATE_CMDS",
      "isPostLCP", "createContent", "FLAGS", "deleteMarkedEls",
      `${section("export async function handleCommands(", "const getCountryList =")}; return handleCommands;`,
    )(page, () => {}, () => "css", { fragment: "fragment" }, "_inline", (url) => url,
      "in-block:", () => {}, getSelectedElements, { updateattribute: (el) => applied.push(el.id) }, {},
      false, async () => null, { all: "all", includeFragments: "include-fragments" }, () => {});
    return { applied, handleCommands };
  };
  const command = (selector) => [{ action: "updateattribute", selector, content: "/example/new" }];

  let run = runner(root("page", 2));
  assert.deepEqual(await run.handleCommands(command("a.cta href")), []);
  assert.deepEqual(run.applied, ["page-1"]);

  run = runner(root("page", 2));
  assert.deepEqual(await run.handleCommands(command("a.cta href #_all")), []);
  assert.deepEqual(run.applied, ["page-1", "page-2"]);

  run = runner(root("page", 0));
  const pending = await run.handleCommands(command("a.cta href #_include-fragments"));
  assert.equal(pending.length, 1);
  assert.deepEqual(await run.handleCommands(pending, root("fragment-a", 2), false, true), []);
  assert.deepEqual(run.applied, ["fragment-a-1"]);

  run = runner(root("page", 0));
  let all = await run.handleCommands(command("a.cta href #_include-fragments #_all"));
  all = await run.handleCommands(all, root("fragment-a", 2), false, true);
  all = await run.handleCommands(all, root("fragment-b", 1), false, true);
  assert.equal(all.length, 1);
  assert.deepEqual(run.applied, ["fragment-a-1", "fragment-a-2", "fragment-b-1"]);
});
