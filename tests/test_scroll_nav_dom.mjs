// Minimal DOM regression test for Streamlit's repeated component initialization.
// No browser packages or network calls required.
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";

class Element {
  constructor(tag) {
    this.tagName = tag;
    this.id = "";
    this.children = [];
    this.dataset = {};
    this.attrs = {};
    this.listeners = {};
    this.top = 1000;
    this.parent = null;
  }
  appendChild(child) {
    if (child.parent) child.remove();
    this.children.push(child);
    child.parent = this;
    return child;
  }
  replaceChildren(...children) {
    for (const item of this.children) item.parent = null;
    this.children = [];
    for (const child of children) this.appendChild(child);
  }
  remove() {
    if (!this.parent) return;
    this.parent.children = this.parent.children.filter(e => e !== this);
    this.parent = null;
  }
  setAttribute(k, v) { this.attrs[k] = v; }
  removeAttribute(k) { delete this.attrs[k]; }
  addEventListener(k, v) { this.listeners[k] = v; }
  removeEventListener(k) { delete this.listeners[k]; }
  getBoundingClientRect() { return {top:this.top}; }
  scrollIntoView(options) { this.scrolled = options; }
}

const body = new Element("body");
const main = new Element("main");
const ids = ["philosophy", "news", "scanner", "metrics", "sentiment"];
const anchors = new Map(ids.map((id, i) => {
  const el = new Element("div");
  el.top = i ? 1300 + i * 500 : 100;
  return ["si-anchor-" + id, el];
}));
const events = [];
let lastHash = "";
globalThis.document = {
  body,
  createElement: name => new Element(name),
  getElementById: id => id === "si-global-scroll-nav"
    ? body.children.find(child => child.id === id) ?? null
    : anchors.get(id) ?? null,
  querySelector: () => main,
  addEventListener: () => {},
  removeEventListener: () => {},
  documentElement: {clientHeight: 900},
};
globalThis.window = {
  innerHeight: 900,
  location: {pathname:"/",search:"",hash:""},
  history: {replaceState: (_a, _b, value) => { lastHash = value; }},
  addEventListener: () => {},
  removeEventListener: () => {},
};
globalThis.MutationObserver = class {
  observe() {}
  disconnect() {}
};
globalThis.requestAnimationFrame = callback => { callback(); return 1; };

const {default: mount} = await import(pathToFileURL(process.argv[2]).href);
const data = {
  sections: [
    ["philosophy", "Investment Philosophy"],
    ["news", "General News Screen"],
    ["scanner", "Regression Scanner"],
    ["metrics", "Metrics & Competition"],
    ["sentiment", "Recent Sentiment"],
  ].map(([id,label])=>({id,label})),
  loaded: ["philosophy"],
};
const mountOnce = () => mount({
  parentElement: new Element("div"),
  data,
  setTriggerValue: (key,val)=>events.push([key,val]),
});
const cleanup1 = mountOnce();
let nav = document.getElementById("si-global-scroll-nav");
assert.ok(nav, "bar is mounted directly on document.body");
assert.equal(nav.children.length, 5, "five labels initially");
assert.deepEqual(nav.children.map(b=>b.dataset.section), ids);

const cleanup2 = mountOnce();
assert.equal(body.children.length, 1, "only one global bar exists after reinitialization");
nav = document.getElementById("si-global-scroll-nav");
assert.equal(nav.children.length, 5, "reinitialization must not duplicate labels");
assert.equal(nav.children.filter(b=>b.dataset.active === "true").length, 1, "one highlighted tab");
nav.children[1].listeners.click();
assert.deepEqual(anchors.get("si-anchor-news").scrolled, {behavior:"smooth",block:"start"});
assert.equal(lastHash, "/#si-news", "clicking the tab navigates to its anchor");

cleanup1();
assert.ok(document.getElementById("si-global-scroll-nav"),
  "unmounting an old component must not remove the new bar");
cleanup2();
assert.equal(document.getElementById("si-global-scroll-nav"), null,
  "unmounting the latest component cleans up the bar");
console.log("PASS: nav is unclipped, five unique tabs, clickable, and lifecycle-safe");
