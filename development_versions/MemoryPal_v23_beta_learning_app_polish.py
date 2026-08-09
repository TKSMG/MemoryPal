import sys
import ctypes
import tkinter as tk
from tkinter import ttk


VERSION = "v23 Beta"
TITLE = "Learning app polish"
ACCENT = "#2563eb"
COLORS = {
    "bg": "#f6f8fc",
    "surface": "#ffffff",
    "alt": "#eef5ff",
    "warm": "#fff7ed",
    "ink": "#111827",
    "muted": "#64748b",
    "line": "#dbe4f0",
    "green": "#16a34a",
    "orange": "#f97316",
    "pink": "#db2777",
}


def enable_dpi_awareness():
    if sys.platform.startswith("win"):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            pass


class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.popup = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, _event=None):
        if self.popup or not self.text:
            return
        x = self.widget.winfo_rootx() + 18
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        self.popup = tk.Toplevel(self.widget)
        self.popup.wm_overrideredirect(True)
        self.popup.wm_geometry(f"+{x}+{y}")
        tk.Label(
            self.popup,
            text=self.text,
            bg="#111827",
            fg="#ffffff",
            padx=10,
            pady=7,
            font=("Segoe UI", 10),
            wraplength=280,
        ).pack()

    def hide(self, _event=None):
        if self.popup:
            self.popup.destroy()
            self.popup = None


class StageApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.scale = max(1.0, min(self.winfo_fpixels("1i") / 96, 1.35))
        self.title(f"MemoryPal {VERSION} - {TITLE}")
        self.geometry(f"{self.px(1120)}x{self.px(740)}")
        self.configure(bg=COLORS["bg"])
        self.styles()
        self.build()

    def px(self, value):
        return int(round(value * self.scale))

    def styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Page.TFrame", background=COLORS["bg"])
        style.configure("Card.TFrame", background=COLORS["surface"])
        style.configure("Alt.TFrame", background=COLORS["alt"])
        style.configure("Warm.TFrame", background=COLORS["warm"])
        style.configure("Title.TLabel", background=COLORS["bg"], foreground=COLORS["ink"], font=("Segoe UI Semibold", 27))
        style.configure("H2.TLabel", background=COLORS["surface"], foreground=COLORS["ink"], font=("Segoe UI Semibold", 17))
        style.configure("Card.TLabel", background=COLORS["surface"], foreground=COLORS["ink"], font=("Segoe UI", 12))
        style.configure("Muted.TLabel", background=COLORS["surface"], foreground=COLORS["muted"], font=("Segoe UI", 11))
        style.configure("Alt.TLabel", background=COLORS["alt"], foreground=COLORS["ink"], font=("Segoe UI", 12))
        style.configure("Warm.TLabel", background=COLORS["warm"], foreground="#9a3412", font=("Segoe UI", 12))
        style.configure("TButton", padding=(self.px(16), self.px(10)), font=("Segoe UI Semibold", 11))
        style.configure("Primary.TButton", padding=(self.px(16), self.px(10)), background=ACCENT, foreground="#ffffff", font=("Segoe UI Semibold", 11))
        style.configure("Horizontal.TProgressbar", troughcolor=COLORS["alt"], background=ACCENT)

    def card(self, parent, style="Card.TFrame", padding=20):
        return ttk.Frame(parent, style=style, padding=self.px(padding))

    def button(self, parent, text, hint, style="TButton"):
        button = ttk.Button(parent, text=text, style=style)
        Tooltip(button, hint)
        return button

    def chip(self, parent, text, color):
        tk.Label(parent, text=text, bg=color, fg="#ffffff", font=("Segoe UI Semibold", 10), padx=12, pady=6).pack(side="left", padx=(0, 8))

    def build(self):
        shell = ttk.Frame(self, style="Page.TFrame", padding=self.px(30))
        shell.pack(fill="both", expand=True)
        ttk.Label(shell, text=f"MemoryPal {VERSION}", style="Title.TLabel").pack(anchor="w")
        ttk.Label(shell, text="A polished learning-app snapshot with visible progress, a clear next step, and hover guidance.", style="Muted.TLabel").pack(anchor="w", pady=(self.px(4), self.px(18)))

        hero = self.card(shell)
        hero.pack(fill="x", pady=(0, self.px(14)))
        ttk.Label(hero, text="Start today's review", style="H2.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(hero, text="The main dashboard points to the next useful action instead of making the learner hunt through modes.", style="Muted.TLabel", wraplength=self.px(650)).grid(row=1, column=0, sticky="w", pady=(self.px(6), 0))
        start = self.button(hero, "Start in Test Lab", "Open the focused answer, reveal, Smart Check, and rating page.", "Primary.TButton")
        start.grid(row=0, column=1, rowspan=2, sticky="ew", padx=(self.px(24), 0))
        hero.columnconfigure(0, weight=3)
        hero.columnconfigure(1, weight=1)

        row = ttk.Frame(shell, style="Page.TFrame")
        row.pack(fill="x", pady=(0, self.px(14)))
        mastery = self.card(row, "Alt.TFrame")
        mastery.grid(row=0, column=0, sticky="nsew", padx=(0, self.px(12)))
        ttk.Label(mastery, text="Mastery progress", style="Alt.TLabel").pack(anchor="w")
        ttk.Progressbar(mastery, maximum=100, value=68).pack(fill="x", pady=(self.px(10), self.px(10)))
        chips = tk.Frame(mastery, bg=COLORS["alt"])
        chips.pack(fill="x")
        self.chip(chips, "Due 4", ACCENT)
        self.chip(chips, "Learning 7", COLORS["orange"])
        self.chip(chips, "Mastered 12", COLORS["green"])

        goal = self.card(row, "Warm.TFrame")
        goal.grid(row=0, column=1, sticky="nsew")
        ttk.Label(goal, text="Small daily win", style="Warm.TLabel").pack(anchor="w")
        ttk.Label(goal, text="Complete one review, one Smart Check, or one capture. The interface keeps the session short and understandable.", style="Warm.TLabel", wraplength=self.px(360)).pack(anchor="w", pady=(self.px(8), 0))
        row.columnconfigure(0, weight=3)
        row.columnconfigure(1, weight=2)

        grid = ttk.Frame(shell, style="Page.TFrame")
        grid.pack(fill="both", expand=True)
        cards = [
            ("Learner queue", "Due, weak, and fresh cards are grouped into a simple queue.", COLORS["pink"]),
            ("Capture", "Question and answer boxes stay separate, with media cues attached to the study set.", COLORS["orange"]),
            ("Test Lab", "Review opens in a dedicated testing page with reveal, Smart Check, and bucket guidance.", ACCENT),
            ("Repetition", "The path still follows the requested 5, 5-4, 5-4-3, 3-2-1 pattern.", COLORS["green"]),
        ]
        for index, (title, body, color) in enumerate(cards):
            card = self.card(grid)
            card.grid(row=index // 2, column=index % 2, sticky="nsew", padx=(0 if index % 2 == 0 else self.px(12), 0), pady=(0, self.px(12)))
            tk.Frame(card, bg=color, height=self.px(4)).pack(fill="x", pady=(0, self.px(14)))
            ttk.Label(card, text=title, style="H2.TLabel").pack(anchor="w")
            ttk.Label(card, text=body, style="Muted.TLabel", wraplength=self.px(430)).pack(anchor="w", pady=(self.px(8), self.px(12)))
            self.button(card, "Open", f"Open the {title.lower()} section.").pack(fill="x")
            grid.columnconfigure(index % 2, weight=1)
            grid.rowconfigure(index // 2, weight=1)


def main():
    enable_dpi_awareness()
    StageApp().mainloop()


if __name__ == "__main__":
    main()
