/* Colour-fix round 2 — heatmap visual + Topic-goals scroll-margin check. */
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
    fs.writeFileSync(path.join(OUT, `${name}.png`), Buffer.from(s.result?.data || '', 'base64'));
    console.log('SHOT', name);
  };

  await tsend('Emulation.setDeviceMetricsOverride', { width: 1280, height: 900, deviceScaleFactor: 1, mobile: false });
  await tsend('Page.navigate', { url: BASE + '/demo?lang=en' });
  await waitFor(`document.body.innerText.includes('Rating history')`, 20000, 'demo');
  await sleep(1500);

  // 1. Topic goals — scrollIntoView on the heading, measure where it lands
  const goals = await ev(`(() => {
    const h = [...document.querySelectorAll('h2')].find(x => x.innerText && x.innerText.includes('Topic goals'));
    if (!h) return { found: false };
    h.scrollIntoView({ block: 'start' });
    return new Promise(res => setTimeout(() => {
      const r = h.getBoundingClientRect();
      const cs = getComputedStyle(h);
      const elAt = document.elementFromPoint(r.x + r.width / 2, r.y + 10);
      res({ found: true, headingTop: Math.round(r.top), scrollMarginTop: cs.scrollMarginTop,
            topmostAtHeading: elAt ? (elAt.tagName + '.' + (elAt.className && elAt.className.baseVal === undefined ? String(elAt.className).slice(0, 60) : '')) : null,
            headingCovered: elAt && !h.contains(elAt) && elAt !== h });
    }, 900));
  })()`);
  console.log('TOPIC-GOALS scroll:', JSON.stringify(goals));
  await shot('demo-desktop-en-topicgoals-fixed');

  // 2. Daily activity heatmap — scroll into view, shot + cell colours
  const heat = await ev(`(() => {
    const h = [...document.querySelectorAll('h2')].find(x => x.innerText && x.innerText.includes('Daily activity'));
    if (!h) return { found: false };
    h.scrollIntoView({ block: 'start' });
    return new Promise(res => setTimeout(() => {
      const card = h.closest('section');
      const cells = [...card.querySelectorAll('*')].filter(e => {
        const cs = getComputedStyle(e);
        return cs.backgroundColor && cs.backgroundColor !== 'rgba(0, 0, 0, 0)' && e.children.length === 0;
      });
      const counts = {};
      cells.forEach(e => { const c = getComputedStyle(e).backgroundColor; counts[c] = (counts[c] || 0) + 1; });
      const r = h.getBoundingClientRect();
      res({ found: true, headingTop: Math.round(r.top), cellBgCounts: counts, totalCells: cells.length });
    }, 900));
  })()`);
  console.log('HEATMAP:', JSON.stringify(heat));
  await shot('demo-desktop-en-heatmap');

  const errs = tevents
    .filter((e) => (e.method === 'Log.entryAdded' && e.params?.entry?.level === 'error') || e.method === 'Runtime.exceptionThrown')
    .map((e) => JSON.stringify(e.params).slice(0, 300));
  console.log('CONSOLE ERRORS:', errs.length, errs.slice(0, 5));
  console.log('DONE');
  tws.close();
  ws.close();
  try { await fetch(`${DEBUG}/json/close/${target.id}`); } catch {}
}

main().catch((e) => { console.error('SHOTS2 FAILED', e); process.exit(1); });
