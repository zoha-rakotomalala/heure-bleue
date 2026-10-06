// heure bleue -- web demo shim
//
// The real wall talks to a small Python server (/api/*) and to a player loop
// that writes data/now_playing.json. GitHub Pages can run neither. This file is
// injected only into the static build (scripts/build_demo.py) and answers those
// routes in the browser: favourites and taste live in localStorage, there is no
// player session, so the wall rotates on its own. The page itself is unchanged.
(() => {
  const KEY = "heurebleue.favorites", HKEY = "heurebleue.history", HMAX = 2000;
  const realFetch = window.fetch.bind(window);
  const json = (obj, status = 200) =>
    Promise.resolve(new Response(JSON.stringify(obj), { status, headers: { "Content-Type": "application/json" } }));

  const loadFavs = () => { try { return JSON.parse(localStorage.getItem(KEY) || "[]"); } catch (e) { return []; } };
  const saveFavs = (f) => localStorage.setItem(KEY, JSON.stringify(f));
  const loadHist = () => { try { return JSON.parse(localStorage.getItem(HKEY) || "[]"); } catch (e) { return []; } };
  const century = (date) => { const m = /(1[0-9]{3}|20[0-9]{2})/.exec(date || ""); return m ? String(Math.floor(+m[1] / 100) + 1) : null; };

  // mirrors server.rebuild_taste
  function taste(favs) {
    const count = (xs) => { const c = {}; for (const x of xs) if (x) c[x] = (c[x] || 0) + 1; return c; };
    const norm = (c) => { const top = Math.max(1, ...Object.values(c)); const o = {}; for (const k in c) o[k] = Math.round(c[k] / top * 1000) / 1000; return o; };
    return {
      n: favs.length,
      artists: norm(count(favs.map(f => f.artist !== "Unknown artist" ? f.artist : null))),
      museums: norm(count(favs.map(f => f.museum))),
      centuries: norm(count(favs.map(f => century(f.date)))),
      colors: favs.flatMap(f => (f.palette || []).slice(0, 2).map(c => c.hex)).slice(-20),
      updated_at: Date.now() / 1000,
    };
  }

  const CONFIG = {
    demo: true,
    city: { name: "Paris", lat: 48.8566, lon: 2.3522, timezone: "Europe/Paris" },
    locale: "", language: "", units: "celsius", theme: "forest",   // the web demo follows the visitor's browser language rotate_minutes: 4, paused_rotate_minutes: 20,
  };

  window.fetch = async (input, init = {}) => {
    const url = typeof input === "string" ? input : input.url;
    const path = url.replace(/^https?:\/\/[^/]+/, "").split("?")[0];
    const method = (init.method || "GET").toUpperCase();

    if (path.endsWith("/api/config")) return json(CONFIG);
    if (path.endsWith("/api/favorites")) return json(loadFavs());
    if (path.endsWith("/api/taste")) return json(taste(loadFavs()));
    if (path.endsWith("now_playing.json")) return json({ active: false, updated_at: 0 });
    if (path.endsWith("/api/swap")) return json({ ok: true });
    if (path.endsWith("/api/next")) return json({ ok: false, error: "no player in the web demo" }, 409);
    if (path.endsWith("/api/history")) return json(loadHist());
    if (path.endsWith("/api/seen") && method === "POST") {
      let body = {}; try { body = JSON.parse(init.body || "{}"); } catch (e) {}
      const row = {}; for (const k of ["id", "title", "artist", "museum", "mode", "track", "track_artist", "dwell_s", "swapped"]) row[k] = body[k] ?? null;
      row.ts = Date.now() / 1000;
      const hist = loadHist(), last = hist[hist.length - 1];
      if (last && last.id === row.id && last.track === row.track && row.ts - last.ts < 15) return json({ ok: true, deduped: true });
      localStorage.setItem(HKEY, JSON.stringify([...hist, row].slice(-HMAX)));
      return json({ ok: true });
    }

    if (path.endsWith("/api/favorite") && method === "POST") {
      let body = {}; try { body = JSON.parse(init.body || "{}"); } catch (e) {}
      const p = body.painting || {};
      if (!p.id) return json({ error: "painting.id required" }, 400);
      let favs = loadFavs(); let state;
      if (favs.some(f => f.id === p.id)) { favs = favs.filter(f => f.id !== p.id); state = false; }
      else {
        const keep = {}; for (const k of ["id", "title", "artist", "date", "museum", "url", "image", "palette"]) keep[k] = p[k] ?? null;
        keep.saved_at = new Date().toISOString().slice(0, 16).replace("T", " ");
        const t = body.track; keep.track = t && t.title ? { title: t.title, artist: t.artist ?? null, album: t.album ?? null, cover: t.cover ?? null, player: t.player ?? null } : null;
        favs.push(keep); state = true;
      }
      saveFavs(favs);
      return json({ favorite: state, count: favs.length, taste_n: favs.length });
    }
    return realFetch(input, init);
  };

  // the demo cannot hear music, so the music slot holds the install card instead:
  // one button per system, the visitor's own system first. Links go through get/,
  // which redirects to the newest release file, so they never go stale.
  addEventListener("DOMContentLoaded", async () => {
    const now = document.getElementById("now");
    if (!now || !document.getElementById("label")) return;
    const T = (k) => (window.HB ? HB.t(k) : k);
    if (window.HB && HB.init) await HB.init();
    const plat = (navigator.userAgentData && navigator.userAgentData.platform) || navigator.platform || "";
    const mine = /Mac/i.test(plat) ? "mac" : /Win/i.test(plat) ? "windows" : /Linux|X11/i.test(plat) && !/Android/i.test(navigator.userAgent) ? "linux" : "";
    const systems = [
      ["mac-arm64", "Mac", "Apple silicon"], ["mac-intel", "Mac", "Intel"], ["windows", "Windows", ""], ["linux", "Linux", ""],
    ].sort((a, b) => (b[0].startsWith(mine) ? 1 : 0) - (a[0].startsWith(mine) ? 1 : 0));
    const style = document.createElement("style");
    style.textContent = `
      #now.install { display: block; opacity: 1; transform: none; }
      #install .k { font-size: 1vmin; color: var(--faint); letter-spacing: 0.1em; text-transform: uppercase; }
      #install .h { font-family: var(--serif); font-style: italic; font-size: 2vmin; margin-top: 0.6vh; }
      #install .s { font-size: 1.25vmin; color: var(--muted); font-weight: 300; margin-top: 0.4vh; }
      #install .os { display: flex; flex-wrap: wrap; gap: 0.7vmin; margin-top: 1.4vh; }
      #install .os a { display: inline-flex; align-items: baseline; gap: 0.5vmin; padding: 0.55vh 1.2vmin; border-radius: 999px; border: 1px solid rgba(var(--text-rgb), 0.3); color: var(--text); text-decoration: none; font-size: 1.25vmin; background: rgba(var(--text-rgb), 0.05); transition: border-color 0.2s ease, background 0.2s ease; }
      #install .os a small { color: var(--muted); font-size: 0.95vmin; letter-spacing: 0.04em; }
      #install .os a:hover { border-color: var(--gold); background: rgba(240, 180, 92, 0.1); }
      #install .os a.mine { border-color: rgba(240, 180, 92, 0.65); color: var(--gold); }
      #install .os a.mine small { color: var(--gold); opacity: 0.75; }
      #install .n { font-size: 1.05vmin; color: var(--faint); margin-top: 1vh; }
      #install .n a { color: var(--muted); }`;
    document.head.appendChild(style);
    now.classList.add("install");
    now.innerHTML = `<div id="install">
      <div class="k">${T("demo_kicker")}</div>
      <div class="h">${T("demo_title")}</div>
      <div class="s">${T("demo_sub")}</div>
      <div class="os">${systems.map(([os, name, chip]) =>
        `<a href="get/?os=${os}" class="${os.startsWith(mine) ? "mine" : ""}">↓ ${name}${chip ? ` <small>${chip}</small>` : ""}</a>`).join("")}</div>
      <div class="n"><a href="https://github.com/zoha-rakotomalala/heure-bleue#install">${T("demo_how")}</a></div>
    </div>`;
    const rerender = () => { now.querySelector(".k").textContent = T("demo_kicker"); now.querySelector(".h").textContent = T("demo_title"); now.querySelector(".s").textContent = T("demo_sub"); now.querySelector(".n a").textContent = T("demo_how"); };
    document.addEventListener("hb:lang", rerender);
  });
})();
