import assert from "node:assert/strict";
import test from "node:test";
import { parseHTML } from "../evals/sim-dom.mjs";
import { EXPECTED_IMPORTS, rewriteSource, simulate } from "../evals/simulate.mjs";

const PAGE = `<main>
  <div data-eval="s1"><div class="marquee light" data-eval="marquee"><div><div>
    <h1 data-eval="h1">Photoshop</h1>
    <p data-eval="actions"><strong><a data-eval="cta1" href="/buy">Buy</a></strong> <em><a data-eval="cta2" href="/learn">Learn</a></em></p>
  </div></div></div></div>
  <div data-eval="s2"><div class="text" data-eval="text1"><div><div><h2 data-eval="h2">Plans</h2></div></div></div>
    <div class="text" data-eval="text2"><div><div><p><a data-eval="frag" href="https://main--cc--adobecom.aem.page/cc-shared/fragments/promo">promo</a></p></div></div></div></div>
  <div data-eval="s3"><div class="section-metadata"><div><div>style</div></div></div></div>
</main>`;

const manifest = (columns, rows, info = [["manifest-type", "Personalization"]], placeholders) => ({
  "helix-info": { columns: ["key", "value"], rows: info.map(([key, value]) => ({ key, value })) },
  "helix-experiences": { columns, rows: rows.map((r) => Object.fromEntries(columns.map((c, i) => [c, r[i] ?? ""]))) },
  ...(placeholders ? { "helix-placeholders": placeholders } : {}),
});

const run = async (m, visitors, url = "https://www.adobe.com/products/photoshop.html", html = PAGE) => (
  simulate(m, { page: { url, html, visitors } }));

test("source rewrite matches the pinned import surface", () => {
  const { counts, code } = rewriteSource("drift-check");
  assert.equal(counts.importBlock, 1, "static import block changed; update STUBBED/REAL_UTILS");
  assert.equal(counts.dynamicImports, 5, "dynamic import() count changed; review simulate.mjs dynamicImport");
  assert.deepEqual(counts.importNames, EXPECTED_IMPORTS);
  assert.doesNotMatch(code, /^import /m);
});

test("selector engine handles the CSS MEP generates", () => {
  // Every expectation here matches Chrome's querySelectorAll on PAGE.
  const doc = parseHTML(PAGE);
  const ids = (sel) => doc.querySelectorAll(sel).map((el) => el.getAttribute("data-eval"));
  assert.deepEqual(ids("main > div"), ["s1", "s2", "s3"]);
  assert.deepEqual(ids("main > div:nth-child(2)"), ["s2"]);
  assert.deepEqual(ids("main > div:last-child"), ["s3"]);
  assert.deepEqual(ids('main > div:has([class*="marquee"])'), ["s1"]);
  assert.deepEqual(ids('[class*="marquee"] strong a'), ["cta1"]);
  assert.deepEqual(ids("*:has(> em a, > strong a)"), ["actions"]);
  assert.deepEqual(ids(".text:nth-child(2 of .text)"), ["text2"]);
  assert.deepEqual(ids(":is(h1, h2, h3)"), ["h1", "h2"]);
  assert.deepEqual(ids("main > div:not(:has(.marquee)) h2"), ["h2"]);
  assert.deepEqual(ids("h1 + p a, h2 ~ p"), ["cta1", "cta2"]);
  assert.deepEqual(ids('a[href$="/promo"]'), ["frag"]);
  assert.deepEqual(ids("main > div:nth-child(2n+1)"), ["s1", "s3"]);
  assert.deepEqual(ids('a[href*="BUY" i]'), ["cta1"]);
  assert.deepEqual(ids("div:has(+ div.section-metadata)"), []);
  assert.deepEqual(ids('[class*="marquee"] div:has( > em a[href*="/learn"]) > em'), []);
  assert.deepEqual(ids('[class*="marquee"] div > p:has(> em a[href*="/learn"])'), ["actions"]);
  assert.deepEqual(ids("main > div > div:only-child"), ["marquee", null]);
  assert.throws(() => doc.querySelectorAll("main >"), SyntaxError);
});

test("first matching experience column wins; tags, AND and NOT combine", async () => {
  const cols = ["action", "selector", "loggedin & phone", "not firefox", "all"];
  const m = manifest(cols, [["replace", "any-marquee primary-cta", "/f/a", "/f/b", "/f/c"]]);
  const out = await run(m, [
    { id: "si-phone", device: "iphone", signedIn: true },
    { id: "so-phone", device: "iphone" },
    { id: "firefox", device: "desktop-firefox" },
  ]);
  assert.deepEqual(out.map((r) => r.experience), ["loggedin & phone", "not firefox", "all"]);
  assert.deepEqual(out[0].commands[0].matched, ["cta1"]);
});

test("page filter, country filter and blank cells drop rows", async () => {
  const cols = ["action", "selector", "page filter (optional)", "country filter (optional)", "all"];
  const m = manifest(cols, [
    ["remove", "section2", "**/products/photoshop", "", "true"],
    ["remove", "section3", "/products/illustrator", "", "true"],
    ["remove", "any-header", "", "JP, US", "true"],
    ["remove", "section1", "", "", ""],
  ]);
  const [us] = await run(m, [{ id: "us", country: "US" }]);
  assert.deepEqual(us.commands.map((c) => [c.selector, c.matched]), [["section2", ["s2"]], ["any-header", ["h1"]]]);
  const [br] = await run(m, [{ id: "br", country: "BR" }], "https://www.adobe.com/br/products/photoshop.html");
  assert.deepEqual(br.commands.map((c) => c.selector), ["section2"]);
});

test("placeholder value column is the first header in sheet order that matches", async () => {
  const cols = ["action", "selector", "all"];
  const rows = [["updateAttribute", "any-marquee primary-cta href", "/{{plan}}"]];
  const valueFirst = { columns: ["key", "value", "jp"], rows: [{ key: "plan", value: "us-plan", jp: "jp-plan" }] };
  const jpFirst = { columns: ["key", "jp", "value"], rows: [{ key: "plan", value: "us-plan", jp: "jp-plan" }] };
  const jpUrl = "https://www.adobe.com/jp/products/photoshop.html";
  const [a] = await run(manifest(cols, rows, undefined, valueFirst), [{ id: "jp" }], jpUrl);
  const [b] = await run(manifest(cols, rows, undefined, jpFirst), [{ id: "jp" }], jpUrl);
  const [c] = await run(manifest(cols, rows, undefined, jpFirst), [{ id: "us" }]);
  assert.equal(a.commands[0].content, "/us-plan");
  assert.equal(b.commands[0].content, "/jp-plan");
  assert.equal(c.commands[0].content, "/us-plan");
  assert.equal(c.commands[0].attribute, "href");
});

test("country restriction, consent, override and disabled promos select Default or force", async () => {
  const cols = ["action", "selector", "countryip(jp)", "all"];
  const rows = [["remove", "section2", "true", "true"]];
  const restricted = manifest(cols, rows, [["manifest-type", "Test"], ["manifest-country-restriction", "JP"]]);
  const out = await run(restricted, [{ id: "jp", country: "JP" }, { id: "us", country: "US" }]);
  assert.deepEqual(out.map((r) => r.experience), ["countryip(jp)", "default"]);
  const plain = manifest(cols, rows);
  const consent = await run(plain, [
    { id: "no-ads", consent: { advertising: false } },
    { id: "forced", override: "countryip(jp)" },
    { id: "disabled", disabled: true },
  ]);
  assert.deepEqual(consent.map((r) => r.experience), ["default", "countryip(jp)", "default"]);
});

test("fragment selectors, #_all and entitlement columns", async () => {
  const cols = ["action", "selector", "photoshop-any", "all"];
  const m = manifest(cols, [
    ["replace", "/cc-shared/fragments/promo", "/cc-shared/fragments/promo-ps", ""],
    ["remove", "text #_all", "", "true"],
  ]);
  const [ent, anon] = await run(m, [{ id: "ent", entitlements: ["photoshop-any"] }, { id: "anon" }]);
  assert.equal(ent.experience, "photoshop-any");
  assert.deepEqual(ent.fragments, [{
    action: "replace", selector: "/cc-shared/fragments/promo", content: "/cc-shared/fragments/promo-ps", trusted: true, matched: ["frag"],
  }]);
  assert.equal(anon.experience, "all");
  assert.deepEqual(anon.commands[0].matched, ["text1", "text2"]);
});
