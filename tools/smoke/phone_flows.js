/**
 * Phone smoke test: drives the phone app's web build through the main flows
 * (first run, a new set, review, quiz, notes, Talk-back, settings, a set page,
 * dark mode) and fails on any page error or missing screen.
 *
 *   cd mobile && npx expo export -p web --output-dir /tmp/web
 *   node tools/store_shots/serve_spa.js /tmp/web 8765 &
 *   node tools/smoke/phone_flows.js http://localhost:8765 /tmp/smoke
 *
 * The web build has no microphone, camera or native audio, so the live tutor,
 * classic speech and photo picking still need a real phone.
 */
const { chromium } = require('playwright');
const B = process.argv[2] || 'http://localhost:8765';
const OUT = process.argv[3] || '.';
const fs = require('fs');
fs.mkdirSync(OUT, { recursive: true });
let failed = 0;
(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: 400, height: 860 } });
  const p = await ctx.newPage();
  const errs = [];
  p.on('pageerror', (e) => errs.push('pageerror: ' + e.message));
  p.on('console', (m) => { if (m.type() === 'error') errs.push('console: ' + m.text().slice(0, 240)); });
  const body = async () => (await p.innerText('body')).replace(/\n+/g, ' | ');
  const last = (sel) => p.locator(sel).last();
  const byLabel = (l) => last(`[aria-label="${l}"]`);
  const text = (t) => p.getByText(t, { exact: true }).last();
  const wait = (ms = 900) => p.waitForTimeout(ms);
  let n = 0;
  const step = async (name, fn, expect) => {
    n++;
    try {
      await fn(); await wait();
      const t = await body();
      if (expect && !expect.test(t)) throw new Error('expected ' + expect + ' in: ' + t.slice(-400));
      console.log('ok   ' + name);
    } catch (e) {
      failed++;
      console.log('FAIL ' + name + ': ' + String(e.message).split('\n')[0].slice(0, 400));
      await p.screenshot({ path: `${OUT}/fail-${n}.png` });
    }
  };
  await p.goto(B); await wait(2500);
  await step('first screen offers sign in and no-account', async () => {}, /Continue without/);
  await step('welcome has 3 questions', async () => { await p.getByText(/Continue without/).last().click(); }, /3\. Read questions aloud/);
  await step('finish welcome', async () => { await text("I'm studying").click(); await p.getByText('Start using MemoryPal').last().click(); await wait(1500); }, /Today/);
  await step('new set: name it and add two cards', async () => {
    await p.goto(B + '/add'); await wait(2000);
    await last('input[placeholder="e.g. Spanish verbs"]').fill('Test Biology');
    await last('[placeholder="What is photosynthesis?"]').fill('What makes ATP?');
    await last('[placeholder="How plants turn light into food"]').fill('The mitochondrion');
    await byLabel('Add a card').click(); await wait();
    await last('[placeholder="What is photosynthesis?"]').fill('Where is DNA kept?');
    await last('[placeholder="How plants turn light into food"]').fill('In the nucleus');
    await last('[aria-label^="Save "]').click(); await wait(1500);
  }, /2 cards saved to Test Biology/);
  await step('set appears on Create', async () => { await p.goto(B + '/create'); await wait(2000); }, /Test Biology/);
  await step('review: show answer and rate Good', async () => {
    await p.goto(B + '/review'); await wait(2000);
    await byLabel('Show answer').click(); await wait();
    await last('[aria-label^="Good"]').click(); await wait();
  }, /Card 2|Question|done|Nice/i);
  await step('quiz: answer one question', async () => {
    await p.goto(B + '/quiz'); await wait(2000);
    const t = await body();
    if (/Add a few more cards/.test(t)) return;
    const idk = byLabel('I don’t know'); if (await idk.count()) await idk.click();
  }, /Quiz|question|Add a few more/i);
  await step('paste notes with bold', async () => {
    await p.goto(B + '/add?mode=paste'); await wait(2000);
    const box = last('textarea');
    await box.fill('Mitochondria make ATP. The nucleus holds DNA.');
    const bold = last('[aria-label="Bold"]'); if (await bold.count()) { await box.selectText(); await bold.click(); }
  }, /Split into cards|Notes/i);
  await step('study tab lists Talk-back', async () => { await p.goto(B + '/study'); await wait(1800); }, /Talk-back/);
  await step('talk-back start screen', async () => { await p.goto(B + '/talkback?mode=all'); await wait(2000); }, /Study out loud|Talk-back|No cards/);
  await step('progress shows streak', async () => { await p.goto(B + '/progress'); await wait(1800); }, /streak|Progress/i);
  await step('settings: AI switch present', async () => { await p.goto(B + '/settings'); await wait(1800); }, /AI/);
  await step('saved notes page', async () => { await p.goto(B + '/notes'); await wait(1800); }, /notes/i);
  await step('a set page', async () => { await p.goto(B + '/deck/Test%20Biology'); await wait(1800); }, /Test Biology/);
  await step('practice: memory techniques', async () => { await p.goto(B + '/practice'); await wait(1800); }, /Technique|Puzzles|recall/i);
  await step('dark mode renders', async () => { await p.emulateMedia({ colorScheme: 'dark' }); await p.goto(B + '/'); await wait(2000); await p.screenshot({ path: `${OUT}/dark-today.png` }); }, /Today/);
  console.log('\nERRORS (' + errs.length + ')');
  for (const e of [...new Set(errs)].slice(0, 15)) console.log(' - ' + e);
  await b.close();
  process.exit(failed || errs.length ? 1 : 0);
})();
