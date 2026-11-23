"""Measure spacing on every desktop page: card insets, gaps between cards,
and the gap under each heading. Prints a table so odd ones out stand out.

    python tools/render_check/spacing_audit.py [--pages a b]

Reuses page_review.py's demo library and window (without taking pictures).
Measured in pixels at the app's ui_scale, which it prints first.
"""
import os
import sys
import tkinter as tk
from collections import Counter, defaultdict
from tkinter import ttk
import tkinter.font as tkfont

HERE = os.path.dirname(os.path.abspath(__file__))
source = open(os.path.join(HERE, "page_review.py"), encoding="utf-8").read()
setup = source.split("views = [v for v in app.page_titles()]")[0]
args = [a for a in sys.argv[1:]]
only = args[args.index("--pages") + 1:] if "--pages" in args else []
sys.argv = [sys.argv[0], os.path.join(HERE, "_spacing_out"), "dark", "--no-dialogs"]
namespace = {"__file__": os.path.join(HERE, "page_review.py"), "__name__": "page_review_setup"}
exec(compile(setup, "page_review.py", "exec"), namespace)
app, pump, walk, M = namespace["app"], namespace["pump"], namespace["walk"], namespace["M"]
COLORS = M.COLORS


def bg_of(widget):
    try:
        if isinstance(widget, ttk.Widget):
            style = widget.cget("style") or widget.winfo_class()
            return (app.style.lookup(style, "background") or "").lower()
        return str(widget.cget("bg")).lower()
    except tk.TclError:
        return ""


def font_of(widget):
    try:
        if isinstance(widget, ttk.Widget):
            style = widget.cget("style") or widget.winfo_class()
            spec = widget.cget("font") or app.style.lookup(style, "font")
        else:
            spec = widget.cget("font")
        f = tkfont.Font(root=app, font=spec)
        return int(f.actual("size")), f.actual("weight"), f.actual("family")
    except (tk.TclError, TypeError):
        return None


def text_of(widget):
    try:
        return str(widget.cget("text"))[:28]
    except tk.TclError:
        return ""


def box(widget):
    return widget.winfo_rootx(), widget.winfo_rooty(), widget.winfo_width(), widget.winfo_height()


def mapped_children(widget):
    # Corner pictures are placed over a rounded panel's corners: not content.
    return [c for c in widget.winfo_children() if c.winfo_ismapped() and c.winfo_width() > 1 and c.winfo_manager() != "place"]


SURFACES = {COLORS[name].lower() for name in ("surface", "alt", "hero") if name in COLORS}
PAGE_BG = COLORS["bg"].lower()


def audit(view):
    rows = {"inset": [], "card_gap": [], "heading_gap": [], "heading_top": []}
    host = app.view_host
    cards = [w for w in walk(host, (tk.Frame, ttk.Frame)) if w.winfo_ismapped() and bg_of(w) in SURFACES and bg_of(w.master) not in SURFACES and w.winfo_width() > 120]
    for card in cards:
        kids = mapped_children(card)
        if not kids:
            continue
        x, y, w, h = box(card)
        left = min(k.winfo_rootx() for k in kids) - x
        top = min(k.winfo_rooty() for k in kids) - y
        bottom = y + h - max(k.winfo_rooty() + k.winfo_height() for k in kids)
        first = sorted(kids, key=lambda k: (k.winfo_rooty(), k.winfo_rootx()))[0]
        rows["inset"].append((left, top, bottom, text_of(first) or first.winfo_class()))
    # Gaps between cards stacked in one column (same parent).
    by_parent = defaultdict(list)
    for card in cards:
        by_parent[str(card.master)].append(card)
    for siblings in by_parent.values():
        siblings.sort(key=lambda c: (c.winfo_rooty(), c.winfo_rootx()))
        for a, b in zip(siblings, siblings[1:]):
            ax, ay, aw, ah = box(a)
            bx, by, bw, bh = box(b)
            if bx < ax + aw and ax < bx + bw and by >= ay + ah:
                rows["card_gap"].append(by - (ay + ah))
            elif by == ay and bx >= ax + aw:
                rows["card_gap"].append(("h", bx - (ax + aw)))
    # Headings: what sits under each, and how far above the previous block it is.
    for label in walk(host, (tk.Label, ttk.Label)):
        if not label.winfo_ismapped():
            continue
        font = font_of(label)
        if not font or font[0] < 13 or font[1] != "bold" and "Semibold" not in font[2]:
            continue
        parent = label.master
        siblings = sorted(mapped_children(parent), key=lambda k: k.winfo_rooty())
        lx, ly, lw, lh = box(label)
        below = [s for s in siblings if s.winfo_rooty() >= ly + lh and s is not label]
        above = [s for s in siblings if s.winfo_rooty() + s.winfo_height() <= ly and s is not label]
        name = f"{font[0]}{'b' if font[1] == 'bold' or 'Semibold' in font[2] else ''} '{text_of(label)}'"
        if below:
            rows["heading_gap"].append((below[0].winfo_rooty() - (ly + lh), name, font_of(below[0]) and font_of(below[0])[0]))
        if above:
            rows["heading_top"].append((ly - max(s.winfo_rooty() + s.winfo_height() for s in above), name))
    return rows


views = ["dashboard", "plan", "study", "review", "quiz", "talkback", "create", "library", "decks", "capture",
         "ainotes", "practice", "tools", "games", "elder", "stats", "settings"]
if only:
    views = only
pump(1.0)
print(f"ui_scale {app.ui_scale} px(16)={app.px(16)}")
totals = defaultdict(Counter)
for view in views:
    app.show_view(view)
    pump(0.8)
    rows = audit(view)
    print(f"\n== {view}")
    for left, top, bottom, first in rows["inset"]:
        print(f"  card inset L{left} T{top} B{bottom}  ({first})")
        totals["inset_left"][left] += 1
        totals["inset_top"][top] += 1
    if rows["card_gap"]:
        print(f"  card gaps {rows['card_gap']}")
        for gap in rows["card_gap"]:
            totals["card_gap"][gap] += 1
    for gap, name, below in rows["heading_gap"]:
        print(f"  under {name}: {gap}px (next text {below})")
        totals["heading_gap"][(name.split()[0], gap)] += 1
    for gap, name in rows["heading_top"]:
        print(f"  above {name}: {gap}px")
print("\n== totals")
for key, counter in totals.items():
    print(key, sorted(counter.items(), key=lambda kv: -kv[1])[:24])
sys.stdout.flush()
os._exit(0)
