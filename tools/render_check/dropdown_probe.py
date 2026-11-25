"""Open each dropdown with the real mouse and check it stays open.

python dropdown_probe.py [view ...]
Windows moves the system pointer (SetCursorPos + mouse_event); Linux uses
XTest (pip install python-xlib, run under Xvfb). For every dropdown button on
each page it clicks once (press, short pause, release) and reports whether the
list is still open a moment later, and which events closed it if not.
Then, with the list open again, it turns the wheel once over the page below
the list and checks the list is gone before the page has moved at all (a
list left behind while the field slides away looks broken).
"""
import os
import sys
import tempfile
import time
import traceback

os.environ["MEMORYPAL_DATA_DIR"] = tempfile.mkdtemp(prefix="mp-dropdown-")
os.environ["MEMORYPAL_CAPTCHA_URL"] = ""
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "latest_app"))
import tkinter as tk  # noqa: E402
from tkinter import ttk  # noqa: E402

import MemoryPalDesktop as M  # noqa: E402
from memorypal.models import Card  # noqa: E402

WINDOWS = sys.platform.startswith("win")


def pump(seconds=0.05):
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        app.update()
        time.sleep(0.005)


if WINDOWS:
    import ctypes

    user32 = ctypes.windll.user32

    def move(x, y):
        user32.SetCursorPos(int(x), int(y))
        pump()

    def button(press):
        user32.mouse_event(0x0002 if press else 0x0004, 0, 0, 0, 0)
        pump()

    def wheel_down():
        user32.mouse_event(0x0800, 0, 0, ctypes.c_ulong(-120 & 0xFFFFFFFF).value, 0)
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

    def wheel_down():
        xtest.fake_input(_display, X.ButtonPress, 5)
        xtest.fake_input(_display, X.ButtonRelease, 5)
        _display.sync()

M.enable_dpi_awareness()
app = M.MemoryPalApp()
app.store.onboarding = {"done": True, "persona": "student"}
app.store.add_cards([Card(deck=deck, front=f"Q{n}", back="A") for deck in ("Biology", "Chemistry") for n in range(5)])
app.store.save()
app.geometry("1300x860+20+20")
app.lift()
app.focus_force()
pump(1.0)

closes = []
original_close = app.close_dropdown


def traced_close():
    if getattr(app, "_dropdown", None) is not None:
        stack = "".join(traceback.format_stack(limit=8)[:-1])
        closes.append(stack)
    original_close()


app.close_dropdown = traced_close

HOVER = float(os.environ.get("PROBE_HOVER", "1.2"))
views = sys.argv[1:] or ["decks", "library", "plan", "quiz", "settings", "games", "tools", "elder", "capture"]
failures = 0
for view in views:
    app.show_view(view)
    pump(1.0)
    stack, buttons = [app.view_host], []
    while stack:
        w = stack.pop(0)
        for c in w.winfo_children():
            if isinstance(c, ttk.Menubutton) and c.winfo_ismapped():
                buttons.append(c)
            stack.append(c)
    for b in buttons[:3]:
        page = app.page_scrollframe(app.view_host)
        try:
            if page is not None:
                inner_top = page.viewport.winfo_rooty() - page.viewport.canvasy(0)
                page.scroll_to_offsets(y=max(0, b.winfo_rooty() - inner_top - 200))
                pump(0.3)
        except tk.TclError:
            pass
        closes.clear()
        x, y = b.winfo_rootx() + b.winfo_width() // 2, b.winfo_rooty() + b.winfo_height() // 2
        move(x, y)
        pump(HOVER)  # long enough for the tooltip to come up, as when a person aims
        button(True)
        pump(0.2)
        opened = getattr(app, "_dropdown", None) is not None
        button(False)
        pump(0.6)
        still = getattr(app, "_dropdown", None) is not None
        ok = opened and still
        failures += 0 if ok else 1
        print(f"{view} [{b.cget('text')}] opened={opened} open_after_release={still} focus={app.focus_get()}", flush=True)
        for s in closes:
            print("   closed by:\n" + s, flush=True)
        original_close()
        app._dropdown = None
        pump(0.3)
        if page is None or not still:
            continue
        # Open it again, point at the page beside the list and turn the wheel.
        # (Rest the pointer on the page first, as a person's would have been.)
        move(page.viewport.winfo_rootx() + page.viewport.winfo_width() // 2, page.viewport.winfo_rooty() + page.viewport.winfo_height() // 2)
        pump(0.2)
        try:
            app.open_dropdown(b, [(f"Option {n}", lambda: None, n == 0) for n in range(4)])
        except tk.TclError:
            continue
        pump(0.6)
        top = app._dropdown[0] if getattr(app, "_dropdown", None) else None
        if top is None:
            continue
        view_left, view_right = page.viewport.winfo_rootx(), page.viewport.winfo_rootx() + page.viewport.winfo_width()
        side_x = top.winfo_rootx() + top.winfo_width() + 60
        if side_x > view_right - 40:
            side_x = max(view_left + 40, top.winfo_rootx() - 60)
        move(side_x, top.winfo_rooty() + top.winfo_height() // 2)
        start = page.viewport.canvasy(0)
        wheel_down()
        moved_open, closed_after_ms, began = 0.0, None, time.perf_counter()
        while time.perf_counter() - began < 0.6:
            app.update()
            open_now = getattr(app, "_dropdown", None) is not None
            shift = abs(page.viewport.canvasy(0) - start)
            if open_now:
                moved_open = max(moved_open, shift)
            elif closed_after_ms is None:
                closed_after_ms = (time.perf_counter() - began) * 1000
            time.sleep(0.001)
        page_moved = abs(page.viewport.canvasy(0) - start)
        wheel_ok = closed_after_ms is not None and moved_open == 0
        failures += 0 if wheel_ok else 1
        print(f"   wheel: closed={closed_after_ms is not None} after_ms={closed_after_ms and round(closed_after_ms, 1)} "
              f"page_moved_px={page_moved:.0f} moved_while_open_px={moved_open:.0f} {'ok' if wheel_ok else 'LAGGED'}", flush=True)
        original_close()
        app._dropdown = None
        pump(0.3)
print("failures", failures, flush=True)
os._exit(1 if failures else 0)
