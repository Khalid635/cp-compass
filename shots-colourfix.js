/* Colour-fix verification shots — drives Chrome on :9222 via CDP.
   Screenshots landing + demo (desktop 1280, mobile 390, EN + BN),
   plus a programmatic check of the changed tokens and the demo banner. */
const fs = require('fs');
const path = require('path');

const OUT = 'D:\\Projects\\cp-compass\\shots-colourfix';
const BASE = 'http://127.0.0.1:4173';
const DEBUG = 'http://127.0.0.1:9222';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function getJson(url, method = 'GET') {
  const res = await fetch(url, { method });
  return res.json();
}

async function main() {
  fs.mkdirSync(OUT, { recursive: true });
  const version = await getJson(`${DEBUG}/json/version`);
  const ws = new WebSocket(version.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
  let id = 0;
  const pending = new Map();
  const events = [];
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
    else if (msg.method) events.push(msg);
  };
  const send = (method, params = {}) =>
    new Promise((resolve) => {
      const mid = ++id;
      pending.set(mid, resolve);
      ws.send(JSON.stringify({ id: mid, method, params }));
    });

  const target = await getJson(`${DEBUG}/json/new?${encodeURIComponent('about:blank')}`, 'PUT');
  const tws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { tws.onopen = resolve; tws.onerror = reject; });
  let tid = 0;
  const tpending = new Map();
  const tevents = [];
  tws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && tpending.has(msg.id)) { tpending.get(msg.id)(msg); tpending.delete(msg.id); }
    else if (msg.method) tevents.push(msg);
  };
  const tsend = (method, params = {}) =>
    new Promise((resolve) => {
      const mid = ++tid;
      tpending.set(mid, resolve);
      tws.send(JSON.stringify({ id: mid, method, params }));
    });

  await tsend('Page.enable');
  await tsend('Runtime.enable');
  await tsend('Log.enable');

  const ev = async (expr) => {
    const r = await tsend('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
    if (r.result?.exceptionDetails) throw new Error(JSON.stringify(r.result.exceptionDetails).slice(0, 500));
    return r.result?.result?.value;
  };
  const nav = async (urlPath) => {
    await tsend('Page.navigate', { url: BASE + urlPath });
    await sleep(2500);
  };
  const waitFor = async (expr, timeoutMs = 20000, label = '') => {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      if (await ev(expr)) return true;
      await sleep(300);
    }
    throw new Error(`timeout waiting for: ${label || expr}`);
  };
  const shot = async (name) => {
    const s = await tsend('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
    const p = path.join(OUT, `${name}.png`);
    fs.writeFileSync(p, Buffer.from(s.result?.data || '', 'base64'));
    console.log('SHOT', name);
  };
  const setSize = async (w, h, mobile) => {
    await tsend('Emulation.setDeviceMetricsOverride', { width: w, height: h, deviceScaleFactor: 1, mobile });
    await sleep(400);
  };

  const tokensCheck = async () => {
    return ev(`(() => {
      const cs = getComputedStyle(document.documentElement);
      const keys = ['--surface','--surface-2','--border','--muted','--heat-0','--heat-1','--active','--hover','--bg','--text'];
      const out = {};
      keys.forEach(k => out[k] = cs.getPropertyValue(k).trim());
      out.themeAttr = document.documentElement.getAttribute('data-theme') || document.documentElement.className;
      out.bodyBg = getComputedStyle(document.body).backgroundColor;
      return out;
    })()`);
  };

  const bannerCheck = async () => {
    return ev(`(() => {
      const els = [...document.querySelectorAll('div')].filter(d => d.innerText && d.innerText.includes('viewing demo data'));
      if (!els.length) return { found: false };
      const el = els[els.length - 1];
      const r = el.getBoundingClientRect();
      const cs = getComputedStyle(el);
      // heading that used to be covered
      const head = [...document.querySelectorAll('h1,h2,h3')].find(h => h.innerText && h.innerText.includes('Topic goals'));
      const hr = head ? head.getBoundingClientRect() : null;
      return {
        found: true,
        position: cs.position,
        top: Math.round(r.top), height: Math.round(r.height),
        headingTop: hr ? Math.round(hr.top) : null,
        // banner overlaps heading when their rects intersect while banner is on screen
        overlapsHeading: hr ? (r.top < hr.bottom && r.bottom > hr.top) : null,
      };
    })()`);
  };

  const ratingPillCheck = async () => {
    return ev(`(() => {
      const pills = [...document.querySelectorAll('*')].filter(e => e.children.length === 0 && e.textContent.trim() === '1478');
      return pills.map(e => {
        const r = e.getBoundingClientRect();
        const cs = getComputedStyle(e);
        return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), color: cs.color, borderColor: cs.borderColor, bg: cs.backgroundColor, fontSize: cs.fontSize };
      });
    })()`);
  };

  // ---------- DESKTOP 1280 ----------
  await setSize(1280, 900, false);

  // Landing EN — catch the hero fade near its start, then settled
  await tsend('Page.navigate', { url: BASE + '/?lang=en' });
  await waitFor(`document.body.innerText.includes('Track') || document.body.innerText.includes('Codeforces')`, 20000, 'landing hero');
  await shot('landing-desktop-en-early');
  await sleep(2500);
  await shot('landing-desktop-en');
  console.log('TOKENS landing-en:', JSON.stringify(await tokensCheck()));

  // Demo EN — top (rating pill, cards, heatmap)
  await nav('/demo?lang=en');
  await waitFor(`document.body.innerText.includes('Rating history')`, 20000, 'demo rating history');
  await sleep(800);
  await shot('demo-desktop-en-top');
  console.log('RATING-PILLS:', JSON.stringify(await ratingPillCheck()));
  console.log('TOKENS demo-en:', JSON.stringify(await tokensCheck()));

  // Demo EN — scrolled to Topic goals (banner-overlap check)
  await ev(`(() => { const h = [...document.querySelectorAll('h1,h2,h3')].find(x => x.innerText && x.innerText.includes('Topic goals')); if (h) h.scrollIntoView({block:'start'}); window.scrollBy(0, -8); return !!h; })()`);
  await sleep(1200);
  await shot('demo-desktop-en-scrolled');
  console.log('BANNER after scroll:', JSON.stringify(await bannerCheck()));

  // ---------- MOBILE 390 ----------
  await setSize(390, 844, true);
  await nav('/demo?lang=en');
  await waitFor(`document.body.innerText.includes('Rating history')`, 20000, 'demo mobile');
  await sleep(800);
  await shot('demo-mobile-en');
  await nav('/?lang=en');
  await waitFor(`document.body.innerText.length > 200`, 20000, 'landing mobile');
  await sleep(1200);
  await shot('landing-mobile-en');

  // ---------- BN (desktop) ----------
  await setSize(1280, 900, false);
  await nav('/?lang=bn');
  await waitFor(`document.body.innerText.length > 200`, 20000, 'landing bn');
  await sleep(1200);
  await shot('landing-desktop-bn');
  await nav('/demo?lang=bn');
  await waitFor(`document.body.innerText.length > 200`, 20000, 'demo bn');
  await sleep(1200);
  await shot('demo-desktop-bn-top');

  const errs = tevents
    .filter((e) => (e.method === 'Log.entryAdded' && e.params?.entry?.level === 'error') || e.method === 'Runtime.exceptionThrown')
    .map((e) => JSON.stringify(e.params).slice(0, 300));
  console.log('CONSOLE ERRORS:', errs.length, errs.slice(0, 5));
  console.log('DONE shots in', OUT);
  tws.close();
  ws.close();
  try { await fetch(`${DEBUG}/json/close/${target.id}`); } catch {}
}

main().catch((e) => { console.error('SHOTS FAILED', e); process.exit(1); });
