// Records a time-lapse of the running wall: one headless page, one PNG frame
// every `every` seconds for `minutes` minutes. Frames go to <out>/frames/.
// Assemble with tools/assemble_demo.py.
//
//   node tools/record_demo.js --url http://127.0.0.1:8765/ --out ./rec \
//        --minutes 4 --every 3 --size 1080x1920 [--playwright <node_modules dir>]
//
// The page is a real second viewer of the wall (it follows the same player
// loop), so the frames show exactly what the desk screen shows.

const path = require("path");
const fs = require("fs");

const args = Object.fromEntries(
  process.argv.slice(2).map((a, i, arr) => (a.startsWith("--") ? [a.slice(2), arr[i + 1]] : null)).filter(Boolean)
);
const url = args.url || "http://127.0.0.1:8765/";
const out = path.resolve(args.out || "rec");
const minutes = Number(args.minutes || 4);
const every = Number(args.every || 3);
const [w, h] = (args.size || "1080x1920").split("x").map(Number);
const pwRoot = args.playwright ? path.resolve(args.playwright) : null;
const exe = process.env.PW_CHROMIUM || null;

const { chromium } = require(pwRoot ? path.join(pwRoot, "playwright") : "playwright");

const frames = path.join(out, "frames");
fs.mkdirSync(frames, { recursive: true });

const total = Math.floor((minutes * 60) / every);
// Hard guard: Chromium has hung before. Never outlive the plan by more than a minute.
setTimeout(() => { console.error("guard: timeout, exiting"); process.exit(2); }, (minutes * 60 + 60) * 1000).unref();

(async () => {
  const browser = await chromium.launch(exe ? { executablePath: exe } : {});
  const page = await browser.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
  await page.goto(url, { waitUntil: "domcontentloaded", timeout: 20000 });
  await page.waitForTimeout(3000); // let the first painting and weather land
  const t0 = Date.now();
  for (let i = 0; i < total; i++) {
    const file = path.join(frames, `f${String(i).padStart(4, "0")}.png`);
    try {
      await page.screenshot({ path: file, timeout: 8000 });
    } catch (e) {
      console.error(`frame ${i}: ${e.message.split("\n")[0]}`);
    }
    if (i % 10 === 0) console.log(`frame ${i}/${total} at +${Math.round((Date.now() - t0) / 1000)}s`);
    const due = t0 + (i + 1) * every * 1000;
    const wait = due - Date.now();
    if (wait > 0) await page.waitForTimeout(wait);
  }
  await browser.close();
  console.log(`DONE ${total} frames in ${frames}`);
  process.exit(0);
})().catch((e) => { console.error("ERR", e.message.split("\n")[0]); process.exit(1); });
