#!/usr/bin/env node
// Offline MEP behavior simulator. Loads the pinned Milo personalization.js
// (skills/milo-mep/assets/source) with browser globals stubbed per visitor, then
// reports the experience selected, the rows that apply on the page, the fixture
// elements each selector matches, and resolved placeholder values.
//
// Usage: node evals/simulate.mjs --manifest <read-json|published-json> [--spec <spec.json>]
// Prints { lint: [{sev, where, msg}], results: [per page x visitor] }.
// Spec: { page: { url, html | htmlFile, locale? }, visitors: [ { id, ... } ] }
// Visitor fields: ua | device (desktop-chrome, desktop-firefox, desktop-safari,
// desktop-edge, iphone, android-phone, ipad, android-tablet), screen {width,height},
// signedIn, country, entitlements [], label, referrer, consent {performance, advertising},
// override (forced experience name, as with ?mep), disabled (promo outside window).

import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseHTML, Element, UnsupportedSelector } from "./sim-dom.mjs";
import { lintManifest, toManifest } from "../skills/milo-mep/scripts/lint-core.mjs";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const SOURCE_DIR = join(ROOT, "skills/milo-mep/assets/source");

export const DEVICES = {
  "desktop-chrome": { ua: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36", screen: { width: 1512, height: 982 } },
  "desktop-firefox": { ua: "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0", screen: { width: 1920, height: 1080 } },
  "desktop-safari": { ua: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15", screen: { width: 1512, height: 982 } },
  "desktop-edge": { ua: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0", screen: { width: 1920, height: 1080 } },
  iphone: { ua: "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1", screen: { width: 393, height: 852 }, touch: 5 },
  "android-phone": { ua: "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36", screen: { width: 412, height: 915 }, touch: 5 },
  ipad: { ua: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15", screen: { width: 820, height: 1180 }, touch: 5 },
  "android-tablet": { ua: "Mozilla/5.0 (Linux; Android 14; SM-X710) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36", screen: { width: 800, height: 1280 }, touch: 5 },
};

// Subset of Milo locales; extend via spec.page.locales when a case needs more.
export const LOCALES = {
  "": { ietf: "en-US", region: "us" },
  uk: { ietf: "en-GB", region: "uk" },
  ca: { ietf: "en-CA", region: "ca" },
  ca_fr: { ietf: "fr-CA", region: "ca_fr" },
  au: { ietf: "en-AU", region: "au" },
  in: { ietf: "en-IN", region: "in" },
  de: { ietf: "de-DE", region: "de" },
  fr: { ietf: "fr-FR", region: "fr" },
  es: { ietf: "es-ES", region: "es" },
  it: { ietf: "it-IT", region: "it" },
  nl: { ietf: "nl-NL", region: "nl" },
  se: { ietf: "sv-SE", region: "se" },
  br: { ietf: "pt-BR", region: "br" },
  mx: { ietf: "es-MX", region: "mx" },
  la: { ietf: "es-419", region: "la" },
  jp: { ietf: "ja-JP", region: "jp" },
  kr: { ietf: "ko-KR", region: "kr" },
  cn: { ietf: "zh-CN", region: "cn" },
  tw: { ietf: "zh-TW", region: "tw" },
  ch_de: { ietf: "de-CH", region: "ch_de" },
  ch_fr: { ietf: "fr-CH", region: "ch_fr" },
};

// ---------------------------- source rewrite -----------------------------

const IMPORT_BLOCK = /^import \{[^}]*\} from '\.\.\/\.\.\/utils\/utils\.js';\nimport \{ getMepConsentConfig, sendAnalytics \} from '\.\.\/\.\.\/martech\/helpers\.js';\nimport \{ sanitizeHtmlBody \} from '\.\.\/\.\.\/utils\/sanitizeHtml\.js';\n/m;
const STUBBED = ["createTag", "getConfig", "getMetadata", "loadLink", "loadScript", "localizeLinkAsync",
  "getFederatedUrl", "isSignedOut", "isBot", "computeDetectedMarketCountry", "getCookie",
  "isMasImsLoginEnabled", "getMepConsentConfig", "sendAnalytics", "sanitizeHtmlBody"];
const REAL_UTILS = ["isTrustedUrl", "isSameOriginManifestPath", "normCountryCode"];
const EXTRA_EXPORTS = ["getManifestConfig", "getSelectedElements", "getSelectorType", "isTrustedUrl"];

function sliceUtils(utils) {
  const start = utils.indexOf("const TRUSTED_DOMAINS");
  const trustEnd = utils.indexOf("\n}\n", utils.indexOf("export function isSameOriginManifestPath")) + 3;
  const ccStart = utils.indexOf("export function normCountryCode");
  const ccEnd = utils.indexOf("\n}\n", ccStart) + 3;
  if (start < 0 || trustEnd < 3 || ccStart < 0 || ccEnd < 3) throw new Error("utils.js drift: helper boundaries not found");
  return (utils.slice(start, trustEnd) + utils.slice(ccStart, ccEnd)).replace(/^export /gm, "");
}

/** Returns { code, counts } so tests can detect source drift. */
export function rewriteSource(id) {
  const src = readFileSync(join(SOURCE_DIR, "personalization.js"), "utf8");
  const utils = readFileSync(join(SOURCE_DIR, "utils.js"), "utf8");
  const counts = { importBlock: 0, dynamicImports: 0 };
  const importNames = [...(IMPORT_BLOCK.exec(src)?.[0] || "").matchAll(/\{([^}]*)\}/g)]
    .flatMap((m) => m[1].split(",").map((n) => n.trim()).filter(Boolean));
  let code = src.replace(IMPORT_BLOCK, () => {
    counts.importBlock += 1;
    return [
      `const __sim = globalThis.__mepSim.get(${JSON.stringify(id)});`,
      "const { window, navigator, document, localStorage } = __sim.globals;",
      `const { ${STUBBED.join(", ")} } = __sim.stubs;`,
      sliceUtils(utils),
    ].join("\n");
  });
  code = code.replace(/\bimport\(/g, () => { counts.dynamicImports += 1; return "__sim.dynamicImport("; });
  code += `\nexport { ${EXTRA_EXPORTS.join(", ")} };\n`;
  counts.importNames = importNames.sort();
  return { code, counts };
}

export const EXPECTED_IMPORTS = [...STUBBED, ...REAL_UTILS].sort();

// ------------------------------- manifest --------------------------------

/** Accepts mep_xlsx.py read output or published JSON; returns published-JSON shape. */
export function toPublished(manifest) {
  const out = {};
  for (const [name, sheet] of Object.entries(manifest)) {
    if (name.startsWith(":") || name === "readme") continue;
    const key = name.replace(/^helix-/, "");
    if (Array.isArray(sheet?.rows)) {
      const cols = sheet.columns;
      const rows = sheet.rows
        .map((r) => Object.fromEntries(cols.map((c) => [c, r[c] == null ? "" : String(r[c])])))
        .filter((r) => Object.values(r).some((v) => v.trim() !== ""));
      out[key] = { data: rows };
    } else if (Array.isArray(sheet?.data)) out[key] = { data: sheet.data };
  }
  if (!out.experiences && Array.isArray(manifest.data)) out.experiences = { data: manifest.data };
  return out;
}

// -------------------------------- runner ---------------------------------

globalThis.__mepSim ??= new Map();
let counter = 0;

function localeFor(pathname, extra = {}) {
  const locales = { ...LOCALES, ...extra };
  const first = pathname.split("/")[1] || "";
  const prefixKey = first in locales && first !== "" ? first : "";
  return { locales, locale: { ...locales[prefixKey], prefix: prefixKey ? `/${prefixKey}` : "" } };
}

function makeStorage() {
  const m = new Map();
  return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)), removeItem: (k) => m.delete(k) };
}

async function loadFor(ctx) {
  const id = `v${counter += 1}`;
  globalThis.__mepSim.set(id, ctx);
  const { code } = rewriteSource(id);
  try {
    return await import(`data:text/javascript;base64,${Buffer.from(code).toString("base64")}`);
  } finally {
    globalThis.__mepSim.delete(id);
  }
}

function describe(el) {
  const label = el.getAttribute("data-eval");
  if (label) return label;
  const cls = el.classList[0];
  return `${el.localName}${cls ? `.${cls}` : ""}(unlabeled)`;
}

function resolveVisitor(v) {
  const dev = DEVICES[v.device || "desktop-chrome"];
  if (!dev && !v.ua) throw new Error(`unknown device ${v.device}`);
  return {
    ua: v.ua || dev.ua,
    screen: v.screen || dev?.screen || { width: 1440, height: 900 },
    touch: v.touch ?? dev?.touch ?? 0,
  };
}

export async function simulateVisitor(published, page, visitor) {
  const url = new URL(page.url);
  const html = page.html ?? readFileSync(page.htmlFile, "utf8");
  const doc = parseHTML(html);
  const { ua, screen, touch } = resolveVisitor(visitor);
  const { locales, locale } = localeFor(url.pathname, page.locales);
  const consent = { performance: true, advertising: true, ...(visitor.consent || {}) };
  const sent = [];
  const entitlements = visitor.entitlements || [];
  const config = {
    codeRoot: `${url.origin}/libs`,
    locale: { ...locale, ...(page.locale || {}) },
    locales,
    env: { name: "prod" },
    mep: {
      preview: false,
      countryIP: visitor.country ? visitor.country.toLowerCase() === "uk" ? "gb" : visitor.country.toLowerCase().split("_")[0] : undefined,
      consentState: consent,
      promises: {},
      entitlementMap: Object.fromEntries(entitlements.map((e, i) => [`sim-${i}`, e])),
    },
    entitlements: async () => entitlements,
  };
  const pageUrl = new URL(url.href);
  const window = {
    location: pageUrl,
    screen,
    performance: { getEntriesByType: () => [] },
    lana: { log: () => {} },
  };
  const ctx = {
    globals: {
      window,
      navigator: { userAgent: ua, maxTouchPoints: touch },
      document: Object.assign(doc, { referrer: visitor.referrer || "" }),
      localStorage: makeStorage(),
    },
    stubs: {
      createTag: (tag, attrs = {}) => new Element(tag, attrs),
      getConfig: () => config,
      getMetadata: (name) => doc.querySelector(`meta[name="${name}"]`)?.getAttribute("content") ?? null,
      loadLink: () => {}, loadScript: async () => {}, localizeLinkAsync: async (h) => h,
      getFederatedUrl: (u = "") => (typeof u === "string" && u.startsWith("/") && u.includes("/federal/") ? `https://www.adobe.com${u}` : u),
      isSignedOut: () => !visitor.signedIn,
      isBot: () => false,
      computeDetectedMarketCountry: () => config.mep.countryIP,
      getCookie: () => undefined,
      isMasImsLoginEnabled: () => false,
      getMepConsentConfig: () => consent,
      sendAnalytics: (msg) => sent.push(msg),
      sanitizeHtmlBody: (h) => h,
    },
    dynamicImport: async (spec) => {
      if (spec.endsWith("martech/attributes.js")) return { processTrackingLabels: (s) => s };
      throw new Error(`simulator does not load ${spec}`);
    },
  };
  const mod = await loadFor(ctx);
  const manifestPath = page.manifestPath || "/simulated/manifest.json";
  const variantOverride = visitor.override ? { [manifestPath]: visitor.override } : undefined;
  if (variantOverride) config.mep.variantOverride = { ...variantOverride };
  const mc = await mod.getManifestConfig({
    manifestData: published,
    manifestPath,
    disabled: !!visitor.disabled,
    source: ["pzn"],
  }, variantOverride);
  if (!mc) return { id: visitor.id, error: "manifest rejected (no experiences / experience columns)" };

  const selected = mc.selectedVariantName ?? null;
  const variant = selected ? mc.variants?.[selected] : null;
  const result = {
    id: visitor.id,
    experience: variant ? selected : "default",
    manifestType: mc.manifestType,
    executionOrder: mc.executionOrder,
    consentType: mc.consentType,
    countryEnabled: mc.countryEnabled,
    consentEnabled: mc.consentEnabled,
    placeholders: {},
    commands: [],
    fragments: [],
    global: {},
  };
  if (!variant) return result;

  mod.parsePlaceholders(mc.placeholderData, config, selected, url.pathname);
  mod.parseNestedPlaceholders(config);
  result.placeholders = { ...(config.placeholders || {}) };

  for (const cmd of variant.commands) {
    const entry = { action: cmd.action, selector: cmd.selector, content: mod.replacePlaceholders(cmd.content) };
    if (cmd.selector.startsWith("in-block:")) { entry.inBlock = true; result.commands.push(entry); continue; }
    try {
      const { els, modifiers, attribute } = mod.getSelectedElements(cmd.selector, doc, false, cmd.action);
      if (!els) entry.error = "invalid selector";
      entry.matched = [...(els || [])].map(describe);
      entry.modifiers = modifiers || [];
      if (attribute) entry.attribute = attribute;
      if (els && mod.getSelectorType(cmd.selector) !== "fragment") entry.modified = mod.modifyNonFragmentSelector(cmd.selector, cmd.action).modifiedSelector;
    } catch (e) {
      entry.error = e instanceof UnsupportedSelector ? `simulator unsupported: ${e.message}` : String(e.message || e);
    }
    result.commands.push(entry);
  }
  for (const frag of variant.fragments) {
    const links = doc.querySelectorAll("a[href]").filter((a) => {
      const href = a.getAttribute("href");
      return href.includes(mod.normalizePath(frag.selector, false)) || href.includes(mod.normalizePath(frag.selector, true));
    });
    result.fragments.push({ action: frag.action, selector: frag.selector, content: mod.replacePlaceholders(frag.val), trusted: !frag.val || mod.isTrustedUrl(mod.normalizePath(frag.val)), matched: links.map(describe) });
  }
  for (const key of ["updatemetadata", "useblockcode", "insertscript", "replacepage", "updateframework"]) {
    if (variant[key]?.length) result.global[key] = variant[key].map(({ selector, val }) => ({ selector, val: mod.replacePlaceholders(val) }));
  }
  return result;
}


export async function simulate(manifest, spec) {
  const published = toPublished(manifest);
  const pages = spec.pages || [spec.page];
  const out = [];
  for (const page of pages) {
    for (const visitor of page.visitors || spec.visitors || []) {
      out.push({ page: page.url, ...(await simulateVisitor(published, page, visitor)) });
    }
  }
  return out;
}

async function main(argv) {
  const arg = (name) => { const i = argv.indexOf(name); return i >= 0 ? argv[i + 1] : undefined; };
  const manifestFile = arg("--manifest");
  const specFile = arg("--spec");
  if (!manifestFile) {
    console.error("usage: simulate.mjs --manifest <json> [--spec <spec.json>]");
    return 2;
  }
  const manifest = JSON.parse(readFileSync(manifestFile, "utf8"));
  let results = [];
  if (specFile) {
    const spec = JSON.parse(readFileSync(specFile, "utf8"));
    const base = dirname(resolve(specFile));
    for (const page of spec.pages || [spec.page]) if (page.htmlFile) page.htmlFile = resolve(base, page.htmlFile);
    results = await simulate(manifest, spec);
  }
  const lint = lintManifest(toManifest(manifest));
  process.stdout.write(`${JSON.stringify({ lint, results }, null, 2)}\n`);
  return 0;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exitCode = await main(process.argv.slice(2));
}
