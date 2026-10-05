// Loads web/i18n.js under a fake window and checks every language is complete.
//   node tests/test_i18n.js web/i18n.js
const fs = require("fs"), vm = require("vm"), assert = require("assert");
const store = {};
const sandbox = {
  URLSearchParams, Intl, console, CustomEvent: class {},
  localStorage: { getItem: k => store[k] ?? null, setItem: (k, v) => { store[k] = v; }, removeItem: k => { delete store[k]; } },
  location: { search: "" }, navigator: { language: "de-DE" },
  document: { documentElement: {}, querySelectorAll: () => [], querySelector: () => null, dispatchEvent: () => {} },
};
sandbox.window = sandbox;
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), sandbox);
const HB = sandbox.HB, L = HB.LANGS, keys = Object.keys(L.en);
for (const [code, m] of Object.entries(L)) {
  const missing = keys.filter(k => !(k in m)), extra = Object.keys(m).filter(k => !keys.includes(k));
  assert.deepStrictEqual([missing, extra], [[], []], `${code}: missing ${missing} extra ${extra}`);
  for (const k of ["sunset_in", "first_light_in"]) assert.ok(m[k].includes("{n}"), `${code}.${k} lost {n}`);
  for (const k of ["set_at", "rise_at"]) assert.ok(m[k].includes("{t}"), `${code}.${k} lost {t}`);
  assert.ok(m.of.includes("{a}") && m.of.includes("{b}"), `${code}.of`);
  assert.ok(m.century.includes("{n}") || m.century.includes("{c}"), `${code}.century`);
}
assert.strictEqual(HB.lang, "de", "no stored choice: the browser language wins over the fallback");
HB.setLang("fi"); assert.strictEqual(HB.century(18), "1700-luku");
HB.setLang("en"); assert.strictEqual(HB.century(18), "18th century"); assert.strictEqual(HB.century(21), "21st century");
HB.setLang("fr"); assert.strictEqual(HB.wmo(61), "Pluie légère"); assert.strictEqual(HB.wmo(999), "Quelques nuages");
assert.strictEqual(HB.t("sunset_in", { n: 12 }), "coucher du soleil dans 12 min");
HB.setLang("xx"); assert.strictEqual(HB.lang, "fr", "an unknown code is ignored");
HB.setUnits("fahrenheit"); assert.strictEqual(HB.units(), "fahrenheit");
HB.setCity({ name: "Oslo", lat: 59.9, lon: 10.7, timezone: "Europe/Oslo" }); assert.strictEqual(HB.city().name, "Oslo");
assert.strictEqual(HB.overridden(), true);
HB.reset(); assert.strictEqual(HB.overridden(), false); assert.strictEqual(HB.units(), "celsius");
console.log(`i18n ok: ${Object.keys(L).length} languages, ${keys.length} keys each`);
