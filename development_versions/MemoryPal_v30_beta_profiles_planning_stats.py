"""
MemoryPal v30 beta - profiles, planning, and stats

Independent milestone prototype. This version shows the point where MemoryPal
started feeling less like a single study screen and more like a daily study app:
separate profiles, daily progress, a lightweight planner, and a cleaner modern
desktop shell.
"""

import json
import re
import tkinter as tk
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from tkinter import ttk


APP_DIR = Path.home() / "MemoryPal_v30_ProfileDemo"
CONFIG_FILE = APP_DIR / "profiles.json"
COLORS = {
    "bg": "#0f172a",
    "panel": "#18243a",
    "soft": "#22314f",
    "ink": "#eef4ff",
    "muted": "#9fb0cc",
    "primary": "#4da3ff",
    "green": "#3ddc84",
    "orange": "#ffb020",
}


@dataclass
class Card:
    prompt: str
    answer: str
    deck: str = "General"
    next_review: str = date.today().isoformat()
    rating: str = "New"


def clean(value):
    return re.sub(r"\s+", " ", value or "").strip()


def profile_file(name):
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", name).strip("-") or "Default"
    folder = APP_DIR / "profiles" / slug
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "data.json"


def load_config():
    APP_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    config = {"active": "Default", "profiles": ["Default"]}
    CONFIG_FILE.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return config


def save_config(config):
    APP_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2), encoding="utf-8")


class Store:
    def __init__(self, profile):
        self.profile = profile
        self.cards = []
        self.activity = {}
        self.load()

    def load(self):
        path = profile_file(self.profile)
        if not path.exists():
            self.cards = [
                Card("What should MemoryPal help with?", "Gentle recall practice."),
                Card("What makes a card easier to study?", "One clear prompt and one clear answer."),
            ]
            self.save()
            return
        raw = json.loads(path.read_text(encoding="utf-8"))
        self.cards = [Card(**item) for item in raw.get("cards", [])]
        self.activity = dict(raw.get("activity", {}))

    def save(self):
        profile_file(self.profile).write_text(
            json.dumps({"cards": [asdict(card) for card in self.cards], "activity": self.activity}, indent=2),
            encoding="utf-8",
        )

    def due_cards(self):
        today = date.today().isoformat()
        return [card for card in self.cards if card.next_review <= today]

    def log_review(self):
        key = date.today().isoformat()
        self.activity[key] = self.activity.get(key, 0) + 1
        self.save()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.config_data = load_config()
        self.store = Store(self.config_data["active"])
        self.title(f"MemoryPal v30 - {self.store.profile}")
        self.geometry("1060x720")
        self.minsize(900, 620)
        self.configure(bg=COLORS["bg"])
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self.style.configure("TFrame", background=COLORS["bg"])
        self.style.configure("Panel.TFrame", background=COLORS["panel"])
        self.style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["ink"], font=("Segoe UI", 12))
        self.style.configure("Muted.TLabel", background=COLORS["bg"], foreground=COLORS["muted"], font=("Segoe UI", 10))
        self.style.configure("Panel.TLabel", background=COLORS["panel"], foreground=COLORS["ink"], font=("Segoe UI", 12))
        self.style.configure("Title.TLabel", background=COLORS["bg"], foreground=COLORS["ink"], font=("Segoe UI Semibold", 26))
        self.style.configure("TButton", padding=(14, 10), background=COLORS["soft"], foreground=COLORS["ink"], borderwidth=0)
        self.style.configure("Primary.TButton", padding=(14, 10), background=COLORS["primary"], foreground="white", borderwidth=0)
        self.view = tk.StringVar(value="dashboard")
        self.build_shell()

    def build_shell(self):
        rail = ttk.Frame(self, width=220)
        rail.pack(side="left", fill="y", padx=18, pady=18)
        ttk.Label(rail, text="MemoryPal", style="Title.TLabel").pack(anchor="w", pady=(0, 18))
        for label, view in [("Dashboard", "dashboard"), ("Study Plan", "plan"), ("Profiles", "profiles")]:
            ttk.Button(rail, text=label, command=lambda target=view: self.show(target)).pack(fill="x", pady=5)
        self.host = ttk.Frame(self)
        self.host.pack(side="left", fill="both", expand=True, padx=(0, 22), pady=22)
        self.show("dashboard")

    def clear(self):
        for child in self.host.winfo_children():
            child.destroy()

    def panel(self, parent):
        frame = ttk.Frame(parent, style="Panel.TFrame", padding=22)
        frame.pack(fill="x", pady=(0, 14))
        return frame

    def modal_shell(self, title):
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.configure(bg=COLORS["bg"])
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        card = tk.Frame(dialog, bg=COLORS["panel"], padx=22, pady=20)
        card.pack(fill="both", expand=True, padx=14, pady=14)
        tk.Label(card, text=title, bg=COLORS["panel"], fg=COLORS["ink"], font=("Segoe UI Semibold", 18)).pack(anchor="w")
        return dialog, card

    def alert(self, title, body):
        dialog, card = self.modal_shell(title)
        tk.Label(card, text=body, bg=COLORS["panel"], fg=COLORS["muted"], font=("Segoe UI", 12), wraplength=420, justify="left").pack(anchor="w", pady=(10, 18))
        ttk.Button(card, text="OK", style="Primary.TButton", command=dialog.destroy).pack(anchor="e")
        dialog.update_idletasks()
        dialog.geometry(f"+{self.winfo_rootx() + 120}+{self.winfo_rooty() + 120}")
        self.wait_window(dialog)

    def ask_text(self, title, body):
        result = {"value": None}
        dialog, card = self.modal_shell(title)
        tk.Label(card, text=body, bg=COLORS["panel"], fg=COLORS["muted"], font=("Segoe UI", 12), wraplength=420, justify="left").pack(anchor="w", pady=(10, 10))
        entry = tk.Entry(card, bg="#0b1220", fg=COLORS["ink"], insertbackground=COLORS["primary"], relief="flat", font=("Segoe UI", 12))
        entry.pack(fill="x", ipady=9)

        def submit():
            result["value"] = entry.get()
            dialog.destroy()

        row = tk.Frame(card, bg=COLORS["panel"])
        row.pack(fill="x", pady=(16, 0))
        ttk.Button(row, text="Cancel", command=dialog.destroy).pack(side="right")
        ttk.Button(row, text="Save", style="Primary.TButton", command=submit).pack(side="right", padx=(0, 8))
        entry.focus_set()
        dialog.bind("<Return>", lambda _event: submit())
        dialog.update_idletasks()
        dialog.geometry(f"+{self.winfo_rootx() + 120}+{self.winfo_rooty() + 120}")
        self.wait_window(dialog)
        return result["value"]

    def show(self, view):
        self.view.set(view)
        self.clear()
        getattr(self, f"view_{view}")()

    def view_dashboard(self):
        ttk.Label(self.host, text="Today", style="Title.TLabel").pack(anchor="w", pady=(0, 14))
        due = len(self.store.due_cards())
        total = len(self.store.cards)
        reviewed = self.store.activity.get(date.today().isoformat(), 0)
        stats = self.panel(self.host)
        ttk.Label(stats, text=f"{due} due    {total} cards    {reviewed} reviewed today", style="Panel.TLabel").pack(anchor="w")
        action = self.panel(self.host)
        ttk.Label(action, text="Next best action", style="Panel.TLabel").pack(anchor="w")
        ttk.Label(action, text="Start with due cards, then add a short association for anything missed twice.", style="Panel.TLabel", wraplength=700).pack(anchor="w", pady=(8, 12))
        ttk.Button(action, text="Review one card", style="Primary.TButton", command=self.review_one).pack(anchor="w")

    def review_one(self):
        due = self.store.due_cards()
        if not due:
            self.alert("Review", "Nothing is due right now.")
            return
        card = due[0]
        response = self.ask_text(card.prompt, "Answer from memory:")
        if response is None:
            return
        card.rating = "Reviewed"
        card.next_review = (date.today() + timedelta(days=2)).isoformat()
        self.store.log_review()
        self.store.save()
        self.alert("Answer", card.answer)
        self.show("dashboard")

    def view_plan(self):
        ttk.Label(self.host, text="Study Plan", style="Title.TLabel").pack(anchor="w", pady=(0, 14))
        choices = [
            ("Warm-up", "Review one due card to activate memory."),
            ("Build", "Add or rewrite one clear prompt-answer card."),
            ("Strengthen", "Create a small hook for the weakest card."),
            ("Close", "Do one quick self-check before stopping."),
        ]
        for title, body in choices:
            card = self.panel(self.host)
            ttk.Label(card, text=title, style="Panel.TLabel").pack(anchor="w")
            ttk.Label(card, text=body, style="Panel.TLabel", wraplength=720).pack(anchor="w", pady=(5, 0))

    def view_profiles(self):
        ttk.Label(self.host, text="Profiles", style="Title.TLabel").pack(anchor="w", pady=(0, 14))
        for name in self.config_data["profiles"]:
            row = self.panel(self.host)
            ttk.Label(row, text=name + ("  - active" if name == self.store.profile else ""), style="Panel.TLabel").pack(side="left")
            ttk.Button(row, text="Switch", command=lambda value=name: self.switch_profile(value)).pack(side="right")
        ttk.Button(self.host, text="New profile", style="Primary.TButton", command=self.new_profile).pack(fill="x")

    def switch_profile(self, name):
        self.config_data["active"] = name
        save_config(self.config_data)
        self.store = Store(name)
        self.title(f"MemoryPal v30 - {name}")
        self.show("dashboard")

    def new_profile(self):
        name = clean(self.ask_text("New profile", "Profile name:"))
        if not name:
            return
        if name not in self.config_data["profiles"]:
            self.config_data["profiles"].append(name)
        save_config(self.config_data)
        self.switch_profile(name)


if __name__ == "__main__":
    App().mainloop()
