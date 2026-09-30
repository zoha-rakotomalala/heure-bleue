// Runs web/demo.js under a fake window and exercises the intercepted routes.
const fs = require("fs"), vm = require("vm"), assert = require("assert");
const store = {};
const sandbox = {
  localStorage: { getItem: k => store[k] ?? null, setItem: (k, v) => { store[k] = v; } },
  addEventListener: () => {}, document: { getElementById: () => null },
  Response: class { constructor(body, init) { this.body = body; this.status = init.status; } async json() { return JSON.parse(this.body); } },
  console,
};
sandbox.window = sandbox;
sandbox.fetch = async (u) => ({ status: 200, passthrough: true, url: u });
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), sandbox);
const f = sandbox.window.fetch;
const P = { id: "met-1", title: "Nocturne", artist: "Whistler", date: "1875", museum: "The Met", url: "u", image: "i", palette: [{ hex: "#112233" }, { hex: "#445566" }, { hex: "#778899" }] };
(async () => {
  assert.deepStrictEqual((await (await f("/api/favorites")).json()), []);
  assert.strictEqual((await (await f("/api/config")).json()).demo, true);
  assert.strictEqual((await (await f("data/now_playing.json?t=1")).json()).active, false);
  let r = await (await f("/api/favorite", { method: "POST", body: JSON.stringify({ painting: P }) })).json();
  assert.deepStrictEqual([r.favorite, r.count], [true, 1]);
  const favs = await (await f("/api/favorites")).json();
  assert.strictEqual(favs[0].id, "met-1"); assert.ok(favs[0].saved_at);
  const t = await (await f("/api/taste")).json();
  assert.deepStrictEqual([t.n, t.artists.Whistler, t.centuries["19"], t.colors.length], [1, 1, 1, 2]);
  r = await (await f("/api/favorite", { method: "POST", body: JSON.stringify({ painting: P }) })).json();
  assert.deepStrictEqual([r.favorite, r.count], [false, 0]);
  assert.strictEqual((await f("/api/favorite", { method: "POST", body: "{}" })).status, 400);
  assert.strictEqual((await f("/api/seen", { method: "POST", body: "{}" })).status, 200);
  const pass = await f("https://api.open-meteo.com/x");
  assert.strictEqual(pass.passthrough, true);
  const pass2 = await f("data/paintings.json?t=2");
  assert.strictEqual(pass2.passthrough, true);
  console.log("shim ok: 12 assertions");
})().catch(e => { console.error(e); process.exit(1); });
