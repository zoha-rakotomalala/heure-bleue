// Takes the README screenshots from the running wall. Each frame is a real
// page of the app, so the images stay honest to what the desk screen shows.
//
//   node tools/shoot_docs.js --url http://127.0.0.1:8765 --out docs \
//        [--playwright <node_modules dir>] [--scale 0.5] [--only panel.png]
//
// Writes: wall.png (portrait), wall-landscape.png, kept.png, stats.png,
// panel.png (the ⚙ language/place/units panel, lower-right of a landscape wall),
// themes.png (six wall colours side by side).

const path = require("path");
const fs = require("fs");

const args = Object.fromEntries(
  process.argv.slice(2).map((a, i, arr) => (a.startsWith("--") ? [a.slice(2), arr[i + 1]] : null)).filter(Boolean)
);
const url = (args.url || "http://127.0.0.1:8765").replace(/\/$/, "");
const out = path.resolve(args.out || "docs");
const scale = Number(args.scale || 0.5);
const pwRoot = args.playwright ? path.resolve(args.playwright) : null;
const only = args.only || null;  // shoot one frame, leave the others as they are
const exe = process.env.PW_CHROMIUM || null;
const { chromium } = require(pwRoot ? path.join(pwRoot, "playwright") : "playwright");

fs.mkdirSync(out, { recursive: true });
setTimeout(() => { console.error("guard: timeout"); process.exit(2); }, 150000).unref();

const settle = async (page, ms) => page.waitForTimeout(ms);

// Portrait frames are captured at full 1080x1920 then scaled, so text stays crisp.
async function shot(browser, { file, w, h, path: p, wait = 6000, dsf = 1, act = null, clip = null }) {
  if (only && file !== only) return null;
  const ctx = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: dsf });
  const page = await ctx.newPage();
  await page.goto(url + p, { waitUntil: "domcontentloaded", timeout: 20000 });
  await settle(page, wait);
  if (act) await act(page);
  else {
    // Hide the cursor-triggered control cluster so the frame reads as the wall does at rest.
    await page.mouse.move(5, 5);
    await settle(page, 4500);
  }
  const dest = path.join(out, file);
  await page.screenshot({ path: dest, timeout: 15000, ...(clip ? { clip } : {}) });
  await ctx.close();
  console.log("wrote", dest);
  return dest;
}

(async () => {
  const browser = await chromium.launch(exe ? { executablePath: exe } : {});
  await shot(browser, { file: "wall.png", w: 1080, h: 1920, path: "/?theme=forest" });
  await shot(browser, { file: "wall-landscape.png", w: 1920, h: 1080, path: "/?theme=forest" });
  await shot(browser, { file: "kept.png", w: 1080, h: 1920, path: "/favorites.html", wait: 4000 });
  await shot(browser, { file: "stats.png", w: 1200, h: 1700, path: "/stats.html", wait: 4000 });
  // The ⚙ panel: open it, search a city so the results show, crop to the lower-right quarter.
  await shot(browser, { file: "panel.png", w: 1920, h: 1080, path: "/?theme=forest&lang=en", wait: 4000, dsf: 2, clip: { x: 1180, y: 300, width: 740, height: 780 },
    act: async (page) => { await page.keyboard.press("g"); await settle(page, 600); await page.fill("#prefs input", "Amst"); await settle(page, 2500); } });
  // Themes: six narrow portrait frames of the same wall.
  const themes = ["forest", "heure-bleue", "night", "plum", "oxblood", "paper"];
  for (const t of themes) {
    await shot(browser, { file: `_theme-${t}.png`, w: 1080, h: 1920, path: `/?theme=${t}`, wait: 4000 });
  }
  await browser.close();
  console.log("DONE");
})().catch((e) => { console.error("ERR", e.message.split("\n")[0]); process.exit(1); });
