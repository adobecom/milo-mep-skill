// Minimal HTML tree + CSS selector engine for offline MEP simulation.
// Covers the selector syntax MEP rows produce (see modifySelectorTerm) and that
// real manifests use. Unsupported syntax throws UnsupportedSelector so callers
// can report a simulator gap instead of a false "no match".

const VOID = new Set("area base br col embed hr img input link meta source track wbr".split(" "));

export class UnsupportedSelector extends Error {}

class Node {
  constructor() { this.parentNode = null; this.childNodes = []; }
  get children() { return this.childNodes.filter((n) => n instanceof Element); }
  get parentElement() { return this.parentNode instanceof Element ? this.parentNode : null; }
  append(...nodes) { for (const n of nodes) { n.parentNode = this; this.childNodes.push(n); } }
  contains(other) {
    for (let n = other; n; n = n.parentNode) if (n === this) return true;
    return false;
  }
  *descendants() {
    for (const child of this.children) { yield child; yield* child.descendants(); }
  }
  querySelectorAll(selector) {
    const list = parseSelectorList(selector);
    return [...this.descendants()].filter((el) => list.some((sel) => matchComplex(el, sel, sel.length - 1, this)));
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] ?? null; }
  get textContent() { return this.childNodes.map((n) => n.textContent).join(""); }
}

class Text extends Node {
  constructor(text) { super(); this.text = text; }
  get textContent() { return this.text; }
  get outerHTML() { return this.text; }
}

export class Element extends Node {
  constructor(tag, attrs = {}) {
    super();
    this.localName = tag.toLowerCase();
    this.attributes = attrs;
  }
  get tagName() { return this.localName.toUpperCase(); }
  getAttribute(name) { return this.attributes[name.toLowerCase()] ?? null; }
  hasAttribute(name) { return name.toLowerCase() in this.attributes; }
  get classList() { return (this.attributes.class || "").split(/\s+/).filter(Boolean); }
  get id() { return this.attributes.id || ""; }
  get dataset() {
    return Object.fromEntries(Object.entries(this.attributes)
      .filter(([k]) => k.startsWith("data-"))
      .map(([k, v]) => [k.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase()), v]));
  }
  get outerHTML() {
    const attrs = Object.entries(this.attributes).map(([k, v]) => ` ${k}="${v.replace(/"/g, "&quot;")}"`).join("");
    if (VOID.has(this.localName)) return `<${this.localName}${attrs}>`;
    return `<${this.localName}${attrs}>${this.childNodes.map((n) => n.outerHTML).join("")}</${this.localName}>`;
  }
  matches(selector) {
    return parseSelectorList(selector).some((sel) => matchComplex(this, sel, sel.length - 1, null));
  }
}

export class Document extends Node {
  get documentElement() { return this.children[0]; }
  get body() { return this.querySelector("body"); }
  get head() { return this.querySelector("head"); }
}

const decode = (s) => s.replace(/&(amp|lt|gt|quot|#39|nbsp);/g, (_, e) => (
  { amp: "&", lt: "<", gt: ">", quot: '"', "#39": "'", nbsp: "\u00a0" }[e]));

export function parseHTML(html) {
  const doc = new Document();
  const stack = [doc];
  const re = /<!--[\s\S]*?-->|<!doctype[^>]*>|<\/([a-zA-Z][\w-]*)\s*>|<([a-zA-Z][\w-]*)((?:\s+[^\s"'>/=]+(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s"'>]+))?)*)\s*(\/?)>|([^<]+|<)/gi;
  for (const m of html.matchAll(re)) {
    const top = stack[stack.length - 1];
    if (m[1]) {
      const name = m[1].toLowerCase();
      const idx = stack.findLastIndex((n) => n instanceof Element && n.localName === name);
      if (idx > 0) stack.length = idx;
    } else if (m[2]) {
      const attrs = {};
      for (const a of m[3].matchAll(/([^\s"'>/=]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+)))?/g)) {
        attrs[a[1].toLowerCase()] = decode(a[2] ?? a[3] ?? a[4] ?? "");
      }
      const el = new Element(m[2], attrs);
      top.append(el);
      if (!VOID.has(el.localName) && !m[4]) stack.push(el);
    } else if (m[5] !== undefined && m[0].startsWith("<!") === false) {
      top.append(new Text(decode(m[5])));
    }
  }
  if (!doc.children.some((el) => el.localName === "html")) {
    const htmlEl = new Element("html");
    const body = new Element("body");
    body.append(...doc.childNodes.splice(0));
    htmlEl.append(new Element("head"), body);
    doc.childNodes = [];
    doc.append(htmlEl);
  }
  return doc;
}

// ------------------------------ selectors -------------------------------

const IDENT = /^-?(?:[_a-zA-Z\u00a0-\uffff]|\\.)(?:[-_a-zA-Z0-9\u00a0-\uffff]|\\.)*|^--(?:[-_a-zA-Z0-9\u00a0-\uffff]|\\.)*/;
const unescapeIdent = (s) => s.replace(/\\(.)/g, "$1");
const cache = new Map();

export function parseSelectorList(text) {
  if (cache.has(text)) return cache.get(text);
  const parser = new Parser(text);
  const list = parser.list(false);
  parser.ws();
  if (parser.pos < text.length) throw new SyntaxError(`Invalid selector: ${text}`);
  cache.set(text, list);
  return list;
}

class Parser {
  constructor(text) { this.s = text; this.pos = 0; }
  peek() { return this.s[this.pos]; }
  ws() { const m = /^\s*/.exec(this.s.slice(this.pos)); this.pos += m[0].length; return m[0].length > 0; }
  fail() { throw new SyntaxError(`Invalid selector: ${this.s}`); }
  ident() {
    const m = IDENT.exec(this.s.slice(this.pos));
    if (!m) this.fail();
    this.pos += m[0].length;
    return unescapeIdent(m[0]);
  }
  // Read up to the matching ")" (respecting nesting and strings).
  until() {
    let depth = 0; let quote = null; const start = this.pos;
    for (; this.pos < this.s.length; this.pos += 1) {
      const c = this.s[this.pos];
      if (quote) { if (c === "\\") this.pos += 1; else if (c === quote) quote = null; continue; }
      if (c === '"' || c === "'") quote = c;
      else if (c === "(") depth += 1;
      else if (c === ")") { if (depth === 0) { const out = this.s.slice(start, this.pos); this.pos += 1; return out; } depth -= 1; }
    }
    return this.fail();
  }
  list(relative) {
    const out = [];
    do { this.ws(); out.push(this.complex(relative)); this.ws(); } while (this.peek() === "," && ++this.pos);
    return out;
  }
  complex(relative) {
    const parts = [];
    if (relative) {
      this.ws();
      const c = /^[>+~]/.exec(this.s.slice(this.pos));
      parts.push({ scope: true }, c ? c[0] : " ");
      if (c) this.pos += 1;
      this.ws();
    }
    parts.push(this.compound());
    for (;;) {
      const hadWs = this.ws();
      const c = this.peek();
      if (c === ">" || c === "+" || c === "~") { this.pos += 1; this.ws(); parts.push(c, this.compound()); continue; }
      if (hadWs && c !== undefined && c !== "," && c !== ")") { parts.push(" ", this.compound()); continue; }
      return parts;
    }
  }
  compound() {
    const comp = { tests: [] };
    const c = this.peek();
    if (c === "*") { this.pos += 1; } else if (c && IDENT.test(this.s.slice(this.pos))) {
      const tag = this.ident().toLowerCase();
      comp.tests.push((el) => el.localName === tag);
    }
    let any = c === "*" || comp.tests.length > 0;
    for (;;) {
      const ch = this.peek();
      if (ch === "#") { this.pos += 1; const id = this.ident(); comp.tests.push((el) => el.id === id); }
      else if (ch === ".") { this.pos += 1; const cls = this.ident(); comp.tests.push((el) => el.classList.includes(cls)); }
      else if (ch === "[") { this.pos += 1; comp.tests.push(this.attribute()); }
      else if (ch === ":") { this.pos += 1; comp.tests.push(this.pseudo()); }
      else break;
      any = true;
    }
    if (!any) this.fail();
    return comp;
  }
  attribute() {
    this.ws();
    const name = this.ident().toLowerCase();
    this.ws();
    const op = /^([~|^$*]?=)/.exec(this.s.slice(this.pos));
    if (!op) { if (this.s[this.pos] !== "]") this.fail(); this.pos += 1; return (el) => el.hasAttribute(name); }
    this.pos += op[0].length;
    this.ws();
    let value;
    const q = this.peek();
    if (q === '"' || q === "'") {
      const end = this.s.indexOf(q, this.pos + 1);
      if (end < 0) this.fail();
      value = this.s.slice(this.pos + 1, end).replace(/\\(.)/g, "$1");
      this.pos = end + 1;
    } else value = this.ident();
    this.ws();
    let insensitive = false;
    if (/^[iIsS]\b/.test(this.s.slice(this.pos))) { insensitive = /i/i.test(this.peek()); this.pos += 1; this.ws(); }
    if (this.peek() !== "]") this.fail();
    this.pos += 1;
    const norm = (v) => (insensitive ? v.toLowerCase() : v);
    const want = norm(value);
    const ops = {
      "=": (v) => v === want,
      "~=": (v) => want !== "" && !/\s/.test(want) && v.split(/\s+/).includes(want),
      "|=": (v) => v === want || v.startsWith(`${want}-`),
      "^=": (v) => want !== "" && v.startsWith(want),
      "$=": (v) => want !== "" && v.endsWith(want),
      "*=": (v) => want !== "" && v.includes(want),
    };
    const test = ops[op[1]];
    return (el) => el.hasAttribute(name) && test(norm(el.getAttribute(name)));
  }
  pseudo() {
    if (this.peek() === ":") throw new UnsupportedSelector(`pseudo-element in ${this.s}`);
    const name = this.ident().toLowerCase();
    const siblings = (el) => (el.parentNode ? el.parentNode.children : [el]);
    const simple = {
      "first-child": (el) => siblings(el)[0] === el,
      "last-child": (el) => siblings(el).at(-1) === el,
      "only-child": (el) => siblings(el).length === 1,
      "first-of-type": (el) => siblings(el).find((s) => s.localName === el.localName) === el,
      "last-of-type": (el) => siblings(el).findLast((s) => s.localName === el.localName) === el,
      "only-of-type": (el) => siblings(el).filter((s) => s.localName === el.localName).length === 1,
      empty: (el) => el.childNodes.every((n) => !(n instanceof Element) && n.textContent === ""),
      root: (el) => el.parentNode instanceof Document,
    };
    if (simple[name]) return simple[name];
    if (this.peek() !== "(") throw new UnsupportedSelector(`:${name} in ${this.s}`);
    this.pos += 1;
    const arg = this.until();
    if (name === "not" || name === "is" || name === "where") {
      let list;
      if (name === "not") list = parseSelectorList(arg);
      else list = arg.split(/,(?![^(]*\))/).flatMap((part) => { try { return parseSelectorList(part); } catch (e) { if (e instanceof UnsupportedSelector) throw e; return []; } });
      const hit = (el) => list.some((sel) => matchComplex(el, sel, sel.length - 1, null));
      return name === "not" ? (el) => !hit(el) : hit;
    }
    if (name === "has") {
      const inner = new Parser(arg);
      const list = inner.list(true);
      inner.ws();
      if (inner.pos < arg.length) this.fail();
      return (el) => {
        const root = rootOf(el);
        return list.some((sel) => [...root.descendants()].some((c) => matchComplex(c, sel, sel.length - 1, null, el)));
      };
    }
    const nth = /^(nth-child|nth-last-child|nth-of-type|nth-last-of-type)$/.exec(name);
    if (nth) {
      const m = /^\s*(odd|even|[+-]?\d*n(?:\s*[+-]\s*\d+)?|[+-]?\d+)(?:\s+of\s+([\s\S]+))?\s*$/i.exec(arg);
      if (!m || (m[2] && !name.endsWith("child"))) this.fail();
      const [a, b] = anb(m[1].toLowerCase().replace(/\s+/g, ""));
      const of = m[2] ? parseSelectorList(m[2]) : null;
      const last = name.includes("last");
      return (el) => {
        let sibs = siblings(el);
        if (name.endsWith("of-type")) sibs = sibs.filter((s) => s.localName === el.localName);
        if (of) {
          if (!of.some((sel) => matchComplex(el, sel, sel.length - 1, null))) return false;
          sibs = sibs.filter((s) => of.some((sel) => matchComplex(s, sel, sel.length - 1, null)));
        }
        const i = last ? sibs.length - sibs.indexOf(el) : sibs.indexOf(el) + 1;
        return a === 0 ? i === b : (i - b) / a >= 0 && Number.isInteger((i - b) / a);
      };
    }
    throw new UnsupportedSelector(`:${name}() in ${this.s}`);
  }
}

function anb(s) {
  if (s === "odd") return [2, 1];
  if (s === "even") return [2, 0];
  if (!s.includes("n")) return [0, Number(s)];
  const [aPart, bPart] = s.split("n");
  const a = aPart === "" || aPart === "+" ? 1 : aPart === "-" ? -1 : Number(aPart);
  return [a, bPart ? Number(bPart) : 0];
}

function rootOf(el) { let n = el; while (n.parentNode) n = n.parentNode; return n; }

function matchCompound(el, comp, scope) {
  if (comp.scope) return el === scope;
  return comp.tests.every((t) => t(el));
}

// parts: [compound, comb, compound, ...]; match parts[0..i] ending at el.
function matchComplex(el, parts, i, root, scope = null) {
  if (!matchCompound(el, parts[i], scope)) return false;
  if (i === 0) return true;
  const comb = parts[i - 1];
  const next = i - 2;
  const inRoot = (n) => n instanceof Element && (!root || root === n || root.contains(n));
  if (comb === ">") { const p = el.parentElement; return !!p && inRoot(p) && matchComplex(p, parts, next, root, scope); }
  if (comb === " ") {
    for (let p = el.parentElement; p && inRoot(p); p = p.parentElement) if (matchComplex(p, parts, next, root, scope)) return true;
    return false;
  }
  const sibs = el.parentNode ? el.parentNode.children : [];
  const idx = sibs.indexOf(el);
  if (comb === "+") return idx > 0 && matchComplex(sibs[idx - 1], parts, next, root, scope);
  if (comb === "~") return sibs.slice(0, idx).some((s) => matchComplex(s, parts, next, root, scope));
  return false;
}
