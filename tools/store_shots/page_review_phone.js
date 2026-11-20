/**
 * Screenshot every phone screen for a look-over, top to bottom, in light and
 * dark, with the demo library from capture_phone.js.
 *
 *   cd mobile && npx expo export -p web --output-dir /tmp/web
 *   node tools/store_shots/serve_spa.js /tmp/web 8765 &
 *   node tools/store_shots/page_review_phone.js http://localhost:8765 OUT_DIR
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const [, , BASE = 'http://localhost:8765', OUT = 'phone-review', ONLY = ''] = process.argv;
const src = fs.readFileSync(path.join(__dirname, 'capture_phone.js'), 'utf8');
// Reuse the demo library (DECKS, iso, demoData, SYNC) without running that script.
const lib = src.slice(src.indexOf('const DECKS'), src.indexOf('// Screens below'));
const { demoData, SYNC } = new Function(`${lib}; return { demoData, SYNC };`)();

const SCREENS = [
  ['01-today', '/'],
  ['02-study', '/study'],
  ['03-review', '/review', 'Show answer'],
  ['04-quiz', '/quiz'],
  ['05-talkback', '/talkback'],
  ['06-talk-live', '/talk-live'],
  ['07-plan', '/plan'],
  ['08-create', '/create'],
  ['09-add', '/add'],
  ['10-ai', '/ai'],
  ['11-ai-consent', '/ai-consent'],
  ['12-set', '/deck/Biology'],
  ['13-card', '/card/demo-Biology-1'],
  ['14-notes', '/notes'],
  ['15-note', '/notes/demo-notes-cells'],
  ['16-practice', '/practice'],
  ['17-puzzle', '/puzzle'],
  ['18-progress', '/progress'],
  ['19-settings', '/settings'],
  ['20-account', '/account'],
  ['21-start', '/start'],
  ['22-welcome', '/welcome'],
];

async function scroller(page) {
  // The tallest scrollable element that is actually on screen.
  return page.evaluateHandle(() => {
    let best = null; let most = 0;
    for (const el of document.querySelectorAll('*')) {
      const s = getComputedStyle(el);
      if (!/(auto|scroll)/.test(s.overflowY)) continue;
      const r = el.getBoundingClientRect();
      if (r.width < 100 || r.height < 100 || r.left < 0 || r.left >= innerWidth || r.top >= innerHeight) continue;
      const extra = el.scrollHeight - el.clientHeight;
      if (extra > most) { most = extra; best = el; }
    }
    return best;
  });
}

async function shootScrolled(page, dir, prefix) {
  const el = await scroller(page);
  const has = await el.evaluate((e) => !!e);
  let n = 1;
  if (!has) { await page.screenshot({ path: path.join(dir, `${prefix}-1.png`) }); console.log(dir, prefix, 1); return; }
  await el.evaluate((e) => { e.scrollTop = 0; });
  for (;;) {
    await page.waitForTimeout(350);
    await page.screenshot({ path: path.join(dir, `${prefix}-${n}.png`) });
    const done = await el.evaluate((e) => e.scrollTop + e.clientHeight >= e.scrollHeight - 2);
    if (done || n >= 8) break;
    await el.evaluate((e) => { e.scrollTop += e.clientHeight - 90; });
    n++;
  }
  await el.evaluate((e) => { e.scrollTop = 0; });
  console.log(dir, prefix, n);
}

(async () => {
  const browser = await chromium.launch();
  const data = JSON.stringify(demoData());
  for (const scheme of ['light', 'dark']) {
    for (const [name, route, press] of SCREENS) {
      if (ONLY && !ONLY.split(',').includes(name)) continue;
      const dir = path.join(OUT, scheme, name);
      fs.mkdirSync(dir, { recursive: true });
      const context = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, colorScheme: scheme, hasTouch: true, isMobile: true });
      await context.addInitScript(([d, s, w]) => {
        if (!sessionStorage.getItem('demo-seeded')) {
          localStorage.setItem('memorypal-data', w ? JSON.stringify({ ...JSON.parse(d), onboarding: { done: false } }) : d);
          localStorage.setItem('memorypal-sync-state', s);
          sessionStorage.setItem('demo-seeded', '1');
        }
      }, [data, JSON.stringify(SYNC), route === '/welcome']);
      const page = await context.newPage();
      page.on('pageerror', (e) => console.log('pageerror', name, String(e).slice(0, 200)));
      await page.goto(BASE);
      await page.waitForTimeout(2500);
      if (route !== '/') { await page.goto(BASE + route); await page.waitForTimeout(2500); }
      await shootScrolled(page, dir, 'page');
      // Open folded sections (Disclosure rows) and shoot again.
      const closed = page.locator('[aria-expanded="false"]');
      const count = await closed.count();
      if (count) {
        for (let i = 0; i < count; i++) { try { await closed.first().click({ timeout: 1000 }); await page.waitForTimeout(200); } catch (e) { break; } }
        await shootScrolled(page, dir, 'expanded');
      }
      if (press) {
        try {
          await page.locator(`[aria-label="${press}"]`).last().click({ timeout: 2000 });
          await page.waitForTimeout(800);
          await shootScrolled(page, dir, 'after');
        } catch (e) { console.log('no', press); }
      }
      await context.close();
    }
  }
  await browser.close();
})();
