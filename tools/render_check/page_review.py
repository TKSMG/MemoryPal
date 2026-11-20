"""Screenshot every desktop page for a look-over: each page top to bottom,
every dropdown on it opened, and every dialog its buttons open.

    python tools/render_check/page_review.py OUT_DIR [dark|light ...] [--pages a b] [--no-dialogs]

Uses a throwaway profile filled with a demo library. Pictures are named
<theme>/<NN-page>/<kind>-<n>-<label>.png. File pickers, the browser and
"open folder" are switched off, so nothing leaves the app.
"""
import os
import random
import re
import sys
import tempfile
import time
import traceback
from datetime import date, timedelta

os.environ["MEMORYPAL_DATA_DIR"] = tempfile.mkdtemp(prefix="mp-review-")
os.environ["MEMORYPAL_CAPTCHA_URL"] = ""
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "latest_app"))
import tkinter as tk  # noqa: E402
from tkinter import ttk, filedialog  # noqa: E402
from PIL import ImageGrab  # noqa: E402
import MemoryPalDesktop as M  # noqa: E402
from memorypal.models import Card  # noqa: E402

args = sys.argv[1:]
OUT = args.pop(0)
DIALOGS = "--no-dialogs" not in args
args = [a for a in args if a != "--no-dialogs"]
ONLY = []
if "--pages" in args:
    i = args.index("--pages")
    ONLY = args[i + 1:]
    args = args[:i]
THEMES = args or ["dark", "light"]

tmp = tempfile.mkdtemp()
filedialog.askopenfilename = lambda *a, **k: ""
filedialog.askopenfilenames = lambda *a, **k: ()
filedialog.asksaveasfilename = lambda *a, **k: os.path.join(tmp, "out.json")
filedialog.askdirectory = lambda *a, **k: ""
M.system_open = lambda *a, **k: None
M.system_reveal = lambda *a, **k: None
M.open_web_page = lambda *a, **k: None
import webbrowser  # noqa: E402
webbrowser.open = lambda *a, **k: True

DECKS = {
    "Spanish Basics": [
        ("hola", "hello"), ("gracias", "thank you"), ("la biblioteca", "the library"), ("el desayuno", "breakfast"),
        ("¿Dónde está la estación?", "Where is the station?"), ("mañana", "tomorrow; morning"), ("la ventana", "the window"),
        ("aprender", "to learn"), ("el cumpleaños", "birthday"), ("despacio", "slowly"),
    ],
    "Biology": [
        ("What does the mitochondrion do?", "Releases energy from glucose (cellular respiration) as ATP."),
        ("Where does photosynthesis happen?", "In the chloroplasts of plant cells."),
        ("What carries oxygen in red blood cells?", "Haemoglobin."), ("What are the four DNA bases?", "Adenine, thymine, cytosine and guanine."),
        ("What is osmosis?", "Water moving across a membrane from a dilute to a more concentrated solution."),
        ("What do ribosomes make?", "Proteins."), ("Name the stages of mitosis.", "Prophase, metaphase, anaphase, telophase."),
    ],
    "World Capitals": [
        ("Canada", "Ottawa"), ("Australia", "Canberra"), ("Japan", "Tokyo"), ("Kenya", "Nairobi"), ("Brazil", "Brasília"),
        ("Norway", "Oslo"), ("Peru", "Lima"), ("Vietnam", "Hanoi"), ("Morocco", "Rabat"),
    ],
    "Chemistry": [
        ("Symbol for sodium", "Na"), ("pH of pure water at 25 °C", "7"), ("Avogadro's number", "6.022 × 10²³ per mole"),
        ("What is an isotope?", "Atoms of one element with different numbers of neutrons."),
        ("Most reactive group of metals", "Group 1, the alkali metals."),
    ],
}

M.enable_dpi_awareness()
app = M.MemoryPalApp()
errors = []
app.report_callback_exception = lambda *exc: errors.append("".join(traceback.format_exception(*exc)))


def seed():
    random.seed(7)
    today = date.today()
    cards = []
    for deck, pairs in DECKS.items():
        for n, (front, back) in enumerate(pairs):
            learned = n % 4 != 0
            interval = random.choice([1, 3, 6, 12, 25]) if learned else 0
            due = today + timedelta(days=0 if n % 3 == 0 else random.randint(1, 9))
            score = random.choice([88, 95, 100]) if learned and n % 2 else (70 if learned else 0)
            cards.append(Card(deck=deck, front=front, back=back, interval=interval, repetitions=3 if learned else 0,
                              next_review=due.isoformat(), last_result="Good" if learned else "New", last_score=score))
    app.store.onboarding = {"done": True, "persona": "student"}
    app.store.cards = []
    app.store.add_cards(cards)
    app.store.activity = {(today - timedelta(days=d)).isoformat(): random.randint(14, 42) for d in range(0, 31) if d not in (19, 26)}
    app.store.practiced = sum(app.store.activity.values())
    app.store.save(merge_existing=False)


seed()
WIDTH, HEIGHT = 1440, 900
screen_w, screen_h = app.winfo_screenwidth(), app.winfo_screenheight()
WIDTH, HEIGHT = min(WIDTH, screen_w - 40), min(HEIGHT, screen_h - 80)
app.geometry(f"{WIDTH}x{HEIGHT}+20+20")
app.lift()
app.focus_force()


def pump(seconds=0.3):
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        app.update()
        time.sleep(0.01)


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")[:40] or "x"


def bbox(widget):
    return (widget.winfo_rootx(), widget.winfo_rooty(),
            widget.winfo_rootx() + widget.winfo_width(), widget.winfo_rooty() + widget.winfo_height())


def grab(path, *widgets):
    boxes = [bbox(w) for w in widgets if w is not None and w.winfo_exists() and w.winfo_viewable()]
    if not boxes:
        return
    box = (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
    box = (max(0, box[0]), max(0, box[1]), min(screen_w, box[2]), min(screen_h, box[3]))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    ImageGrab.grab(bbox=box, all_screens=True).save(path)
    print(path, flush=True)


def walk(root, kinds):
    out, stack = [], [root]
    while stack:
        w = stack.pop(0)
        try:
            kids = w.winfo_children()
        except tk.TclError:
            continue
        for c in kids:
            if isinstance(c, tk.Toplevel):
                continue
            if isinstance(c, kinds):
                out.append(c)
            stack.append(c)
    return out


def label(w):
    try:
        return str(w.cget("text")) or w.winfo_class()
    except tk.TclError:
        return w.winfo_class()


def page_scroll():
    return app.page_scrollframe(getattr(app, "view_host", None))


def bring_into_view(widget):
    page = page_scroll()
    if page is None:
        return
    try:
        inner_top = page.viewport.winfo_rooty() - page.viewport.canvasy(0)
        y = widget.winfo_rooty() - inner_top
        page.scroll_to_offsets(y=max(0, y - page.viewport.winfo_height() // 4))
    except (tk.TclError, AttributeError):
        pass
    pump(0.25)


def toplevels():
    return [w for w in app.winfo_children() if isinstance(w, tk.Toplevel) and w.winfo_exists() and w.winfo_viewable()]


def capture_page(folder):
    page = page_scroll()
    pump(0.6)
    if page is None:
        grab(os.path.join(folder, "page-1.png"), app)
        return
    page.scroll_to_offsets(y=0)
    pump(0.3)
    step = max(200, page.viewport.winfo_height() - 120)
    n, offset = 1, 0
    while True:
        grab(os.path.join(folder, f"page-{n}.png"), app)
        top = page.max_y_offset()
        if offset >= top or n >= 8:
            break
        offset = min(top, offset + step)
        page.scroll_to_offsets(y=offset)
        pump(0.35)
        n += 1
    page.scroll_to_offsets(y=0)


def capture_dropdowns(folder):
    seen = set()
    buttons = [b for b in walk(app.view_host, (ttk.Menubutton,)) if b.winfo_ismapped()]
    n = 0
    for b in buttons:
        key = label(b)
        if key in seen or n >= 14:
            continue
        seen.add(key)
        try:
            bring_into_view(b)
            b.focus_force()
            app.update()
            b.event_generate("<Key-Down>")
            pump(1.0)
            drop = getattr(app, "_dropdown", None)
            n += 1
            grab(os.path.join(folder, f"dropdown-{n:02d}-{slug(key)}.png"), app, drop[0] if drop else None)
        except Exception:
            errors.append(traceback.format_exc())
        app.close_dropdown()
        pump(0.15)


def restore(theme):
    if getattr(app, "tour", None):
        app.end_tour("")
    if app.theme != theme:
        app.toggle_theme()
        pump(0.8)
    try:
        app.exit_fullscreen()
    except Exception:
        pass


def capture_dialogs(view, folder, seen_titles, theme):
    """Press each button on the page; any window that opens gets its picture."""
    def buttons():
        return [w for w in walk(app.view_host, (ttk.Button, tk.Button))
                if w.winfo_ismapped() and str(w.cget("state")) != "disabled" and str(w.cget("command"))]

    total = len(buttons())
    n = 0
    pressed = set()
    for i in range(total):
        seed_light()
        restore(theme)
        app.show_view(view)
        pump(0.4)
        ws = buttons()
        if i >= len(ws):
            break
        w = ws[i]
        text = label(w)
        if re.search(r"delete|reset|sign out|remove|start over|erase|light mode|dark mode|full screen", text, re.I):
            continue
        # A button repeated down a list (Edit, the speaker) opens the same window.
        if text in pressed:
            continue
        pressed.add(text)
        shot = {}

        def snap(tries=0):
            tops = toplevels()
            if not tops:
                if tries < 6:
                    app.after(150, lambda: snap(tries + 1))
                return
            top = tops[-1]
            heads = [label(x) for x in walk(top, (tk.Label, ttk.Label)) if x.winfo_ismapped() and label(x).strip()]
            title = (top.title() if top.title() not in ("", "MemoryPal", "tk") else "") or (heads[0] if heads else text)
            if title not in seen_titles:
                seen_titles.add(title)
                shot["n"] = True
                app.update_idletasks()
                grab(os.path.join(folder, f"dialog-{len(seen_titles):02d}-{slug(title)}.png"), top)
                # Dropdowns inside the dialog too.
                for k, mb in enumerate([m for m in walk(top, (ttk.Menubutton,)) if m.winfo_ismapped()][:6], 1):
                    try:
                        mb.focus_force()
                        app.update()
                        mb.event_generate("<Key-Down>")
                        for _ in range(40):
                            app.update()
                            time.sleep(0.02)
                        drop = getattr(app, "_dropdown", None)
                        grab(os.path.join(folder, f"dialog-{len(seen_titles):02d}-{slug(title)}-dropdown-{k}.png"), top, drop[0] if drop else None)
                    except Exception:
                        errors.append(traceback.format_exc())
                    app.close_dropdown()
            for t in toplevels():
                try:
                    t.destroy()
                except tk.TclError:
                    pass

        app.after(700, snap)
        try:
            bring_into_view(w)
            w.invoke()
        except Exception:
            errors.append(f"{view} [{text}]\n" + traceback.format_exc())
        pump(1.4)
        for t in toplevels():
            try:
                t.destroy()
            except tk.TclError:
                pass
        app.close_dropdown()
        n += 1
    return n


def seed_light():
    if len(app.store.cards) < 30:
        seed()


views = [v for v in app.page_titles()]
order = ["dashboard", "plan", "study", "review", "quiz", "talkback", "create", "library", "decks", "capture",
         "ainotes", "practice", "tools", "games", "elder", "stats", "settings", "welcome", "signin"]
views = [v for v in order if v in views] + [v for v in views if v not in order]
if ONLY:
    views = ONLY

pump(1.0)
print(f"screen {screen_w}x{screen_h}, window {WIDTH}x{HEIGHT}, ui_scale {getattr(app, 'ui_scale', 1)}", flush=True)
for theme in THEMES:
    if app.theme != theme:
        app.toggle_theme()
        pump(1.0)
    seen_titles = set()
    for number, view in enumerate(views, 1):
        folder = os.path.join(OUT, theme, f"{number:02d}-{view}")
        try:
            app.show_view(view)
            pump(0.8)
            capture_page(folder)
            if view == "review":
                for b in walk(app.view_host, (ttk.Button,)):
                    if "show answer" in label(b).lower():
                        b.invoke()
                        pump(0.6)
                        grab(os.path.join(folder, "answer-shown.png"), app)
                        break
            if view not in ("welcome", "signin"):
                capture_dropdowns(folder)
                if DIALOGS:
                    capture_dialogs(view, folder, seen_titles, theme)
        except Exception:
            errors.append(f"{view}\n" + traceback.format_exc())
        app.store.onboarding = {"done": True, "persona": "student"}

print("errors", len(errors))
for e in errors[:20]:
    print("=====")
    print(e[-1500:])
sys.stdout.flush()
os._exit(0)
