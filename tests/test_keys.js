// Every key the pages ask for must exist in web/i18n.js, so no screen can ever
// show a raw key like `today_died`. Also: scripts must be versioned (?v=__V__),
// which is what keeps an updated app from using a cached old script.
//   node tests/test_keys.js web
const fs = require("fs"), path = require("path"), vm = require("vm"), assert = require("assert");
const dir = process.argv[2] || "web";
const sandbox = {
  URLSearchParams, Intl, console, CustomEvent: class {},
  localStorage: { getItem: () => null, setItem() {}, removeItem() {} },
  location: { search: "" }, navigator: { language: "en" },
  document: { documentElement: {}, querySelectorAll: () => [], querySelector: () => null, dispatchEvent: () => {} },
};
sandbox.window = sandbox;
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(dir, "i18n.js"), "utf8"), sandbox);
const known = new Set(Object.keys(sandbox.HB.LANGS.en));

const pages = ["index.html", "favorites.html", "stats.html", "demo.js"];
const used = new Map(); // key -> where
for (const f of pages) {
  const src = fs.readFileSync(path.join(dir, f), "utf8");
  const add = (k) => { if (!used.has(k)) used.set(k, f); };
  for (const m of src.matchAll(/data-i18n(?:-title|-ph|-doc)?="([a-z_]+)"/g)) add(m[1]);
  for (const m of src.matchAll(/\bT\(\s*"([a-z_]+)"/g)) add(m[1]);
  for (const m of src.matchAll(/\bHB\.t\(\s*"([a-z_]+)"/g)) add(m[1]);
  for (const m of src.matchAll(/\bstatus\(\s*"([a-z_]+)"/g)) add(m[1]);
  for (const m of src.matchAll(/"((?:tip|upd|today|card|demo|ver|taste|pace)_[a-z_]+)"/g)) add(m[1]);
  if (f.endsWith(".html")) {
    for (const m of src.matchAll(/<script src="([^"]+)"/g)) {
      assert.ok(/\?v=__V__$/.test(m[1]), `${f}: script ${m[1]} is not versioned (needs ?v=__V__)`);
    }
  }
}
// the help overlay rows name their keys in an array
const idx = fs.readFileSync(path.join(dir, "index.html"), "utf8");
for (const m of idx.matchAll(/\["[^"]*"|null, "[^"]*", "([a-z_]+)"\]/g)) if (m[1]) used.set(m[1], "index.html help");
const missing = [...used].filter(([k]) => !known.has(k));
assert.deepStrictEqual(missing, [], `keys used but not translated: ${missing.map(([k, f]) => `${k} (${f})`).join(", ")}`);
console.log(`keys ok: ${used.size} referenced, all ${known.size} defined, scripts versioned`);
