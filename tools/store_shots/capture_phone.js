/**
 * Raw phone and tablet captures of the phone app's web build, for the store
 * screenshots (frame.py adds the caption and device frame).
 *
 *   cd mobile && npx expo export -p web --output-dir /tmp/web
 *   node tools/store_shots/serve_spa.js /tmp/web 8765 &
 *   node tools/store_shots/capture_phone.js http://localhost:8765 OUT_DIR
 *
 * Fills the profile with a demo library (four sets, saved notes, a month of
 * study) before the app loads, then opens each screen at every device size.
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const [, , BASE = 'http://localhost:8765', OUT = 'raw-shots'] = process.argv;

// CSS viewport per device, shaped like the screen slot frame.py leaves for it
// (so the tab bar sits at the bottom edge of the frame).
const DEVICES = {
  'iphone-6.9': { width: 430, height: 887, scale: 3 },
  'ipad-13': { width: 820, height: 1028, scale: 2 },
  phone: { width: 400, height: 673, scale: 3 },
  'tablet-7': { width: 600, height: 905, scale: 2 },
  'tablet-10': { width: 800, height: 1208, scale: 2 },
};

const DECKS = {
  Biology: [
    ['What does the mitochondrion do?', 'Releases energy from glucose as ATP (cellular respiration).'],
    ['Where does photosynthesis happen?', 'In the chloroplasts of plant cells.'],
    ['What carries oxygen in red blood cells?', 'Haemoglobin.'],
    ['What are the four DNA bases?', 'Adenine, thymine, cytosine and guanine.'],
    ['What is osmosis?', 'Water moving across a membrane from a dilute to a more concentrated solution.'],
    ['What do ribosomes make?', 'Proteins.'],
    ['Name the stages of mitosis.', 'Prophase, metaphase, anaphase, telophase.'],
  ],
  'Spanish Basics': [
    ['hola', 'hello'], ['gracias', 'thank you'], ['la biblioteca', 'the library'], ['el desayuno', 'breakfast'],
    ['¿Dónde está la estación?', 'Where is the station?'], ['mañana', 'tomorrow; morning'], ['despacio', 'slowly'], ['aprender', 'to learn'],
  ],
  'World History': [
    ['When did the Berlin Wall fall?', '9 November 1989.'], ['Who was the first emperor of Rome?', 'Augustus.'],
    ['What year did World War I begin?', '1914.'], ['Where did the Industrial Revolution start?', 'Britain, in the late 1700s.'],
    ['What was the Magna Carta?', 'A 1215 charter limiting the English king\'s power.'], ['Who led India\'s independence movement?', 'Mahatma Gandhi.'],
  ],
  Chemistry: [
    ['Symbol for sodium', 'Na'], ['pH of pure water at 25 °C', '7'], ['Avogadro\'s number', '6.022 × 10²³ per mole'],
    ['What is an isotope?', 'Atoms of one element with different numbers of neutrons.'], ['Most reactive group of metals', 'Group 1, the alkali metals.'],
  ],
};

function iso(d) { return d.toISOString().slice(0, 10); }

function demoData() {
  let seed = 7;
  const rand = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  const today = new Date();
  const day = (n) => { const d = new Date(today); d.setDate(d.getDate() + n); return iso(d); };
  const cards = [];
  for (const [deck, pairs] of Object.entries(DECKS)) {
    pairs.forEach(([front, back], n) => {
      const learned = n % 4 !== 0;
      cards.push({
        id: `demo-${deck}-${n}`.replace(/\W+/g, '-'), deck, front, back, pathway: '', association: '',
        text_file: '', image: '', audio: '', video: '',
        next_review: n % 3 === 0 ? day(0) : day(1 + Math.floor(rand() * 9)),
        interval: learned ? [1, 3, 6, 12, 25][Math.floor(rand() * 5)] : 0, repetitions: learned ? 3 : 0,
        ease: 2.5, lapses: 0, last_score: learned ? [70, 88, 95, 100][Math.floor(rand() * 4)] : 0,
        last_result: learned ? 'Good' : 'New', created_at: `${day(-30)} 18:00`, buried_until: '',
      });
    });
  }
  const activity = {};
  for (let d = 1; d < 31; d++) if (d !== 19 && d !== 26) activity[day(-d)] = 14 + Math.floor(rand() * 28);
  activity[day(0)] = 9;
  return {
    cards,
    captures: [{
      id: 'demo-notes-cells', title: 'Cells and energy', deck: 'Biology', created_at: `${day(-4)} 17:30`,
      notes: 'The **mitochondrion** releases energy from glucose as ATP.\nPhotosynthesis happens in the ==chloroplasts==.\n_Ribosomes_ make proteins.',
      chunks: [],
    }],
    decks: [{ name: 'Biology', about: 'Year 11 biology, Ms Patel\'s class', exam_date: day(24) }],
    practiced: Object.values(activity).reduce((a, b) => a + b, 0),
    activity, daily_goal: 15, nav_order: [],
    accessibility: { text_size: 'Comfort', high_contrast: false, reduce_motion: false, simple_language: false, caregiver_mode: false, read_aloud: false, more_time: false, focus_outline: false },
    feedback: [], onboarding: { done: true, persona: 'student' }, study_plan: {},
  };
}

const SYNC = { device_id: 'demo', user_id: '', cursor: null, base: {}, last_synced: '', auto_sync: true, account_prompted: true, drive_user: '', drive_file: '', drive_seen: {}, entries: {}, moved_user: '', cloud_cleanup: false };

// Screens below the one in view stay mounted; the one in view comes last.
function last(page, label) {
  return page.locator(`[aria-label="${label}"]`).last();
}

const SHOTS = [
  ['01-today', '/', async (p) => {}],
  ['02-review', '/review', async (p) => { await last(p, 'Show answer').click(); }],
  ['03-study', '/study', async (p) => {}],
  ['04-progress', '/progress', async (p) => {}],
  ['05-set', '/deck/Biology', async (p) => {}],
  ['06-create', '/create', async (p) => {}],
];

(async () => {
  const browser = await chromium.launch();
  const data = JSON.stringify(demoData());
  for (const [device, size] of Object.entries(DEVICES)) {
    fs.mkdirSync(path.join(OUT, device), { recursive: true });
    for (const [name, route, go] of SHOTS) {
      const context = await browser.newContext({ viewport: { width: size.width, height: size.height }, deviceScaleFactor: size.scale, colorScheme: 'light' });
      await context.addInitScript(([d, s]) => {
        if (!sessionStorage.getItem('demo-seeded')) {
          localStorage.setItem('memorypal-data', d);
          localStorage.setItem('memorypal-sync-state', s);
          sessionStorage.setItem('demo-seeded', '1');
        }
      }, [data, JSON.stringify(SYNC)]);
      const page = await context.newPage();
      await page.goto(BASE);
      await page.waitForTimeout(2500);
      if (route !== '/') { await page.goto(BASE + route); await page.waitForTimeout(2500); }
      await go(page);
      await page.waitForTimeout(1200);
      const file = path.join(OUT, device, `${name}.png`);
      await page.screenshot({ path: file });
      console.log(file);
      await context.close();
    }
  }
  await browser.close();
})();
