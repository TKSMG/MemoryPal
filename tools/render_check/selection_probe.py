"""Drag-select text with the real mouse and report what ends up highlighted.

python selection_probe.py [view ...]
Windows moves the system pointer (SetCursorPos + mouse_event); Linux uses
XTest (pip install python-xlib, run under Xvfb). For each selectable label on
the page, and for the page's text boxes, it presses on the first line and
drags straight down in steps, printing the highlighted text and the caret
after each step. A highlight must never shrink while the pointer only moves
further down, must reach the end of the label once the pointer is below it
(carrying on into the labels below, like a web page), and typing boxes must
not show their blinking cursor while text is highlighted.
"""
import os
import sys
import tempfile
import time

os.environ["MEMORYPAL_DATA_DIR"] = tempfile.mkdtemp(prefix="mp-select-")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "latest_app"))
import tkinter as tk  # noqa: E402
from tkinter import ttk  # noqa: E402

import MemoryPalDesktop as M  # noqa: E402
from memorypal.models import Card  # noqa: E402

WINDOWS = sys.platform.startswith("win")
if WINDOWS:
    import ctypes

    user32 = ctypes.windll.user32

    def move(x, y):
        user32.SetCursorPos(int(x), int(y))
        pump()

    def button(press):
        user32.mouse_event(0x0002 if press else 0x0004, 0, 0, 0, 0)  # LEFTDOWN / LEFTUP
        pump()
else:
    from Xlib import X, display
    from Xlib.ext import xtest

    _display = display.Display()

    def move(x, y):
        xtest.fake_input(_display, X.MotionNotify, x=int(x), y=int(y))
        _display.sync()
        pump()

    def button(press):
        xtest.fake_input(_display, X.ButtonPress if press else X.ButtonRelease, 1)
        _display.sync()
        pump()

M.enable_dpi_awareness()
app = M.MemoryPalApp()
app.store.onboarding = {"done": True, "persona": "student"}
app.store.add_cards([Card(deck="Biology", front=f"Question {n}: what does photosynthesis make in the leaves of green plants, and why does every animal depend on it?", back="Sugar and oxygen. " * 8) for n in range(6)])
app.geometry("1200x820+20+20")
app.lift()
app.attributes("-topmost", True)


def pump(rounds=4):
    for _ in range(rounds):
        app.update()
        time.sleep(0.015)


def walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from walk(child)


def selected(box):
    try:
        return box.get("sel.first", "sel.last")
    except tk.TclError:
        return ""


def caret_shown(box):
    if isinstance(box, ttk.Entry):
        return not box.instate(["user2"])  # user2 = cursor hidden while highlighted
    try:
        return int(float(box.cget("insertwidth"))) > 0 and int(float(box.cget("insertofftime") or 0)) >= 0 and str(box.cget("insertontime")) != "0"
    except tk.TclError:
        return None


problems = []
views = sys.argv[1:] or ["review", "dashboard"]
for view in views:
    app.show_view(view)
    pump(30)
    labels = [w for w in walk(app) if isinstance(w, (tk.Label, ttk.Label)) and w.winfo_ismapped() and app._selectable_label(w) and len(str(w.cget("text"))) > 12]
    print(f"== {view}: {len(labels)} labels")
    for label in labels[:5]:
        text = " ".join(str(label.cget("text")).split())
        x0, y0 = label.winfo_rootx() + 12, label.winfo_rooty() + 10
        move(x0, y0)
        button(True)
        steps = []
        for dy in (0, 6, 14, 24, 40, 70, 120, 200):
            move(x0 + 2, y0 + dy)
            steps.append((dy, len(app.selected_label_text())))
            if os.environ.get("SHOT_DIR") and dy == 120:
                from PIL import ImageGrab
                ImageGrab.grab((app.winfo_rootx(), app.winfo_rooty(), app.winfo_rootx() + app.winfo_width(), app.winfo_rooty() + app.winfo_height())).save(os.path.join(os.environ["SHOT_DIR"], f"{view}-{labels.index(label)}.png"))
        button(False)
        pump()
        box = app._select_overlay
        try:
            reached_end = bool(box) and box.compare("sel.last", ">=", "end-1c")
        except tk.TclError:
            reached_end = False
        print(f"  label {text[:40]!r}: lengths {steps} reached end {reached_end}")
        print(f"    highlighted: {app.selected_label_text()[:160]!r}")
        lengths = [n for _dy, n in steps]
        if any(b < a for a, b in zip(lengths, lengths[1:])):
            problems.append(f"{view}: highlight shrank while dragging down on {text[:30]!r}: {steps}")
        if not reached_end:
            problems.append(f"{view}: dragging below {text[:30]!r} did not highlight to the end")
        move(5, 5)
        app.clear_text_selection()
    for box in [w for w in walk(app) if isinstance(w, (tk.Text,)) and not hasattr(w, "owner") and w.winfo_ismapped() and str(w.cget("state")) == "normal"][:2]:
        box.delete("1.0", "end")
        box.insert("1.0", "\n".join(f"line {n} of typed words" for n in range(10)))
        pump()
        x0, y0 = box.winfo_rootx() + 30, box.winfo_rooty() + 8
        move(x0, y0)
        button(True)
        steps = []
        for dy in (0, 10, 30, 60, 120):
            move(x0 + 40, y0 + dy)
            steps.append((dy, len(selected(box)), box.index("insert"), caret_shown(box)))
        button(False)
        pump()
        time.sleep(0.8)  # past the double-click time
        move(x0, y0)
        button(True)
        button(False)
        pump()
        back = caret_shown(box)
        print(f"  text box {box.winfo_class()}: {steps} cursor back after a click: {back}")
        if not back:
            problems.append(f"{view}: text box cursor did not come back after a click")
        if any(n and shown for _dy, n, _i, shown in steps):
            problems.append(f"{view}: text box shows its blinking caret while text is highlighted: {steps}")
    for entry in [w for w in walk(app) if isinstance(w, (tk.Entry, ttk.Entry)) and w.winfo_ismapped()][:1]:
        entry.delete(0, "end")
        entry.insert(0, "some words typed into a single line field")
        pump()
        x0, y0 = entry.winfo_rootx() + 12, entry.winfo_rooty() + entry.winfo_height() // 2
        move(x0, y0)
        button(True)
        steps = []
        for dx, dy in ((60, 0), (120, 0), (120, 30), (120, 80)):
            move(x0 + dx, y0 + dy)
            steps.append((dy, entry.selection_present(), caret_shown(entry)))
        button(False)
        time.sleep(0.8)  # past the double-click time
        move(x0, y0)
        button(True)
        button(False)
        pump()
        back = caret_shown(entry)
        print(f"  entry: {steps} cursor back after a click: {back}")
        if not back:
            problems.append(f"{view}: entry cursor did not come back after a click")
        if any(present and shown for _dy, present, shown in steps):
            problems.append(f"{view}: entry shows its blinking caret while text is highlighted: {steps}")

print("PROBLEMS" if problems else "OK: no selection problems")
for problem in problems:
    print("  " + problem)
app.destroy()
