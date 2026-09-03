import json
import tkinter as tk
from datetime import date, timedelta
from pathlib import Path
from tkinter import ttk


BG = "#101827"
SURFACE = "#182235"
ALT = "#24324b"
INK = "#e8edf7"
MUTED = "#a3b0c8"
PRIMARY = "#5aa8ff"
GREEN = "#37d67a"
ORANGE = "#ffab3d"
PINK = "#ff5c8a"
DATA_FILE = Path.home() / ".memorypal-v47-demo.json"


DEFAULT_NAV = [
    ("dashboard", "Dashboard"),
    ("gym", "Memory Gym"),
    ("review", "Review"),
    ("puzzles", "Puzzles"),
    ("stats", "Stats"),
]


class MemoryPalV47(tk.Tk):
    """Standalone milestone for custom navigation and calmer transitions."""

    def __init__(self):
        super().__init__()
        self.title("MemoryPal v47 - Custom Navigation")
        self.geometry("980x680")
        self.minsize(780, 560)
        self.configure(bg=BG)
        self.current_page = "dashboard"
        self.data = self.load_data()
        self.transitioning = False
        self.build_styles()
        self.build_shell()
        self.show_page("dashboard", transition=False)

    def load_data(self):
        if DATA_FILE.exists():
            try:
                return json.loads(DATA_FILE.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass
        return {
            "nav_order": [key for key, _label in DEFAULT_NAV],
            "activity": {
                date.today().isoformat(): 4,
                (date.today() - timedelta(days=1)).isoformat(): 2,
                (date.today() - timedelta(days=3)).isoformat(): 6,
            },
            "daily_goal": 6,
        }

    def save_data(self):
        DATA_FILE.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    def build_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Root.TFrame", background=BG)
        style.configure("Rail.TFrame", background="#0b1020")
        style.configure("Header.TFrame", background=SURFACE)
        style.configure("Card.TFrame", background=SURFACE)
        style.configure("TLabel", background=BG, foreground=INK, font=("Segoe UI", 11))
        style.configure("Header.TLabel", background=SURFACE, foreground=INK, font=("Segoe UI Semibold", 22))
        style.configure("Card.TLabel", background=SURFACE, foreground=INK, font=("Segoe UI", 11))
        style.configure("Muted.TLabel", background=SURFACE, foreground=MUTED, font=("Segoe UI", 10))
        style.configure("TButton", background=ALT, foreground=INK, padding=(12, 9), borderwidth=0)
        style.configure("Primary.TButton", background=PRIMARY, foreground="white", padding=(12, 9), borderwidth=0)

    def ordered_nav(self):
        labels = dict(DEFAULT_NAV)
        ordered = [key for key in self.data.get("nav_order", []) if key in labels]
        ordered.extend(key for key, _label in DEFAULT_NAV if key not in ordered)
        return [(key, labels[key]) for key in ordered]

    def start_cover(self):
        cover = tk.Frame(self, bg=BG)
        cover.place(relx=0, rely=0, relwidth=1, relheight=1)
        cover.tkraise()
        cover.update()
        return cover

    def clear_cover(self, cover, step=0):
        shades = ("#101827", "#111a2a", "#121c2e", "#141f33")
        if step < len(shades):
            cover.configure(bg=shades[step])
            cover.tkraise()
            self.after(18, lambda: self.clear_cover(cover, step + 1))
        else:
            cover.destroy()
            self.transitioning = False

    def build_shell(self):
        for child in self.winfo_children():
            child.destroy()
        self.body = ttk.Frame(self, style="Root.TFrame")
        self.body.pack(fill="both", expand=True)
        self.rail = ttk.Frame(self.body, style="Rail.TFrame", width=190)
        self.rail.pack(side="left", fill="y")
        self.rail.pack_propagate(False)
        tk.Label(self.rail, text="MemoryPal", bg="#0b1020", fg="white", font=("Segoe UI Semibold", 18)).pack(anchor="w", padx=16, pady=(22, 14))
        for key, label in self.ordered_nav():
            ttk.Button(self.rail, text=label, command=lambda page=key: self.show_page(page)).pack(fill="x", padx=12, pady=5)
        ttk.Button(self.rail, text="Settings", command=lambda: self.show_page("settings")).pack(side="bottom", fill="x", padx=12, pady=18)
        main = ttk.Frame(self.body, style="Root.TFrame")
        main.pack(side="left", fill="both", expand=True, padx=24, pady=24)
        header = ttk.Frame(main, style="Header.TFrame", padding=18)
        header.pack(fill="x", pady=(0, 18))
        self.title_label = ttk.Label(header, text="Dashboard", style="Header.TLabel")
        self.title_label.pack(anchor="w", fill="x")
        chips = tk.Frame(header, bg=SURFACE)
        chips.pack(fill="x", pady=(12, 0))
        today = self.data["activity"].get(date.today().isoformat(), 0)
        self.chip(chips, f"{today}/{self.data['daily_goal']} today", PRIMARY)
        self.chip(chips, "local save", ALT, PRIMARY)
        self.content = ttk.Frame(main, style="Root.TFrame")
        self.content.pack(fill="both", expand=True)

    def chip(self, parent, text, bg, fg="white"):
        tk.Label(parent, text=text, bg=bg, fg=fg, font=("Segoe UI Semibold", 10), padx=12, pady=7).pack(side="left", padx=(0, 8))

    def show_page(self, page, transition=True):
        if self.transitioning:
            return
        cover = self.start_cover() if transition else None
        self.transitioning = bool(cover)
        self.current_page = page
        self.title_label.configure(text={"dashboard": "Dashboard", "gym": "Memory Gym", "review": "Review", "puzzles": "Puzzles", "stats": "Stats", "settings": "Settings"}[page])
        for child in self.content.winfo_children():
            child.destroy()
        getattr(self, f"page_{page}")()
        if cover:
            self.after(45, lambda: self.clear_cover(cover))

    def card(self, title, body, color=PRIMARY):
        frame = ttk.Frame(self.content, style="Card.TFrame", padding=18)
        frame.pack(fill="x", pady=(0, 12))
        tk.Frame(frame, bg=color, width=34, height=4).pack(anchor="w", pady=(0, 10))
        ttk.Label(frame, text=title, style="Card.TLabel", font=("Segoe UI Semibold", 15)).pack(anchor="w")
        ttk.Label(frame, text=body, style="Muted.TLabel", wraplength=660).pack(anchor="w", pady=(6, 0))

    def page_dashboard(self):
        self.card("Ready to practise", "The header keeps progress chips on a separate row so page titles never collide with controls.", GREEN)
        self.card("Custom navigation", "Settings can reorder the left rail for each profile.", PRIMARY)

    def page_gym(self):
        self.card("Student track", "Retrieval, spacing, interleaving, elaboration, examples, and dual coding.", ORANGE)
        self.card("Everyday track", "Spaced retrieval, category sorting, routine recall, and attention games.", PINK)

    def page_review(self):
        self.card("Review flow", "Answer, reveal, Smart Check, and schedule the next attempt.", PRIMARY)

    def page_puzzles(self):
        self.card("Memory games", "Visual search, n-back, category sort, missing item, and routine recall.", GREEN)

    def page_stats(self):
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_total = sum(self.data["activity"].get((week_start + timedelta(days=offset)).isoformat(), 0) for offset in range(7))
        active_days = len([count for count in self.data["activity"].values() if count > 0])
        best_day, best_count = max(self.data["activity"].items(), key=lambda item: item[1])
        self.card("This week", f"{week_total} reviews since Monday.", PRIMARY)
        self.card("Active days", f"{active_days} practice days saved.", GREEN)
        self.card("Best day", f"{best_count} reviews on {best_day}.", ORANGE)

    def page_settings(self):
        frame = ttk.Frame(self.content, style="Card.TFrame", padding=18)
        frame.pack(fill="x")
        ttk.Label(frame, text="Page Order", style="Card.TLabel", font=("Segoe UI Semibold", 15)).pack(anchor="w")
        order = [key for key, _label in self.ordered_nav()]
        labels = dict(DEFAULT_NAV)
        box = tk.Listbox(frame, height=6, bg=ALT, fg=INK, selectbackground=PRIMARY, relief="flat", bd=0, exportselection=False)
        box.pack(fill="x", pady=10)

        def render(selected=0):
            box.delete(0, "end")
            for index, key in enumerate(order):
                box.insert("end", f"{index + 1}. {labels[key]}")
            box.selection_set(max(0, min(selected, len(order) - 1)))

        def move(delta):
            index = box.curselection()[0] if box.curselection() else 0
            target = index + delta
            if 0 <= target < len(order):
                order[index], order[target] = order[target], order[index]
                render(target)

        def apply():
            self.data["nav_order"] = order
            self.save_data()
            self.build_shell()
            self.show_page("settings", transition=False)

        render()
        ttk.Button(frame, text="Move Up", command=lambda: move(-1)).pack(fill="x", pady=(0, 6))
        ttk.Button(frame, text="Move Down", command=lambda: move(1)).pack(fill="x", pady=(0, 6))
        ttk.Button(frame, text="Apply Order", style="Primary.TButton", command=apply).pack(fill="x")


if __name__ == "__main__":
    MemoryPalV47().mainloop()
