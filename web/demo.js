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
    locale: "fr-FR", theme: "forest", rotate_minutes: 4, paused_rotate_minutes: 20,
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

  // one faint line so a visitor knows why there is no music badge
  addEventListener("DOMContentLoaded", () => {
    if (!document.getElementById("label")) return;
    const el = document.createElement("div");
    el.id = "demo-note";
    el.textContent = "web demo · the desktop app adds the music match";
    el.style.cssText = "position:fixed;left:50%;bottom:1.6vmin;transform:translateX(-50%);font-size:1.1vmin;letter-spacing:0.08em;text-transform:uppercase;color:var(--faint);pointer-events:none;white-space:nowrap";
    document.body.appendChild(el);
  });
})();
