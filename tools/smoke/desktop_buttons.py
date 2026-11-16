"""Desktop button check: press every button on every page, and every button of
each dialog that opens, and fail on any Python error.

    xvfb-run -a python tools/smoke/desktop_buttons.py            (Linux, no screen)
    python tools/smoke/desktop_buttons.py quiz review            (only these pages)

Uses a throwaway profile; file pickers, the browser and "open folder" are
switched off, so nothing leaves the app. Takes about ten minutes for all pages.
"""
import os, sys, tempfile, time, traceback
os.environ["MEMORYPAL_DATA_DIR"] = tempfile.mkdtemp(prefix="mp-monkey-")
os.environ["MEMORYPAL_CAPTCHA_URL"] = ""
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "latest_app"))
import tkinter as tk
from tkinter import ttk, filedialog
import MemoryPalDesktop as M
from memorypal.models import Card

ONLY = sys.argv[1:]  # optional list of views
errors = []
log = []
tmp = tempfile.mkdtemp()
filedialog.askopenfilename = lambda *a, **k: ""
filedialog.asksaveasfilename = lambda *a, **k: os.path.join(tmp, "out.json")
filedialog.askdirectory = lambda *a, **k: ""
M.system_open = lambda *a, **k: None
M.system_reveal = lambda *a, **k: None
M.open_web_page = lambda *a, **k: None
import webbrowser
webbrowser.open = lambda *a, **k: True

app = M.MemoryPalApp()
def cb(*exc):
    errors.append((current[0], "".join(traceback.format_exception(*exc))))
app.report_callback_exception = cb
current = ["start"]

def seed():
    app.store.onboarding = {"done": True, "persona": "student"}
    if len(app.store.cards) < 12:
        app.store.add_cards([Card(deck="Biology", front=f"Question {i}?", back=f"Answer {i}") for i in range(12)])
        app.store.save()
seed()

def pump(seconds=0.15):
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        app.update(); time.sleep(0.005)

def clickables(root):
    out = []
    def walk(w):
        try:
            kids = w.winfo_children()
        except tk.TclError:
            return
        for c in kids:
            if isinstance(c, tk.Toplevel):
                continue
            try:
                keys = c.keys()
                if "command" in keys and str(c.cget("command")) and str(c.cget("state")) != "disabled" and c.winfo_ismapped():
                    out.append(c)
            except tk.TclError:
                pass
            walk(c)
    walk(root)
    return out

def label(w):
    try:
        t = str(w.cget("text"))
    except tk.TclError:
        t = ""
    return (t or w.winfo_class())[:40]

def toplevels():
    return [w for w in app.winfo_children() if isinstance(w, tk.Toplevel) and w.winfo_exists() and w.winfo_viewable()]

def closer(press=None, depth=0):
    """Runs inside a modal dialog's wait loop: press one button or close."""
    tops = toplevels()
    if tops:
        top = tops[-1]
        btns = clickables(top)
        seen[0] = max(seen[0], len(btns))
        if press is not None and press < len(btns) and depth == 0:
            b = btns[press]
            current[0] = current[0] + f" > dialog[{label(b)}]"
            try:
                b.invoke()
            except Exception:
                errors.append((current[0], traceback.format_exc()))
            app.after(250, lambda: closer(None, 1))
            return
        try:
            top.destroy()
        except tk.TclError:
            pass
    app.after(120, lambda: closer(None, depth + 1)) if depth < 25 else None

seen = [0]
views = [v for v in app.page_titles() if v not in ("welcome", "signin")]
if ONLY:
    views = ONLY
count = 0
for view in views:
    app.show_view(view); pump(0.3)
    n = len(clickables(app))
    print(view, n, "buttons", flush=True)
    i = 0
    while i < n:
        presses = [None]
        j = 0
        while j < len(presses):
            seed()
            try:
                app.show_view(view); pump(0.2)
                ws = clickables(app)
                if i >= len(ws):
                    break
                w = ws[i]
                current[0] = f"{view} [{label(w)}]"
                seen[0] = 0
                app.after(300, lambda p=presses[j]: closer(p))
                w.invoke()
                pump(0.5)
                for t in toplevels():
                    t.destroy()
                pump(0.1)
                count += 1
                if presses[j] is None and seen[0]:
                    presses += list(range(min(seen[0], 6)))
            except Exception:
                errors.append((current[0], traceback.format_exc()))
            j += 1
        i += 1
print("presses", count, "errors", len(errors))
shown = set()
for where, err in errors:
    key = err.strip().splitlines()[-1] + err.strip().splitlines()[-2]
    if key in shown: continue
    shown.add(key)
    print("=====", where); print(err[-1800:])
os._exit(1 if errors else 0)
