import sys
import ctypes
import tkinter as tk
from tkinter import ttk


VERSION = "v27 Beta"
TITLE = "Cue previews, associations, and skeleton loading"
ACCENT = "#2563eb"


def enable_dpi_awareness():
    if sys.platform.startswith("win"):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            pass


class StageApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.scale = max(1.0, min(self.winfo_fpixels("1i") / 96, 1.35))
        self.title(f"MemoryPal {VERSION} - {TITLE}")
        self.geometry(f"{self.px(1100)}x{self.px(720)}")
        self.configure(bg="#f6f8fc")
        self.styles()
        self.build()

    def px(self, value):
        return int(round(value * self.scale))

    def styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Page.TFrame", background="#f6f8fc")
        style.configure("Card.TFrame", background="#ffffff")
        style.configure("Alt.TFrame", background="#eef5ff")
        style.configure("Warm.TFrame", background="#fff7ed")
        style.configure("Title.TLabel", background="#f6f8fc", foreground="#111827", font=("Segoe UI Semibold", 27))
        style.configure("H2.TLabel", background="#ffffff", foreground="#111827", font=("Segoe UI Semibold", 17))
        style.configure("Alt.TLabel", background="#eef5ff", foreground="#111827", font=("Segoe UI", 12))
        style.configure("Warm.TLabel", background="#fff7ed", foreground="#9a3412", font=("Segoe UI", 12))
        style.configure("Muted.TLabel", background="#ffffff", foreground="#64748b", font=("Segoe UI", 11))
        style.configure("TButton", padding=(self.px(16), self.px(10)), font=("Segoe UI Semibold", 11))
        style.configure("Primary.TButton", padding=(self.px(16), self.px(10)), background=ACCENT, foreground="#ffffff", font=("Segoe UI Semibold", 11))

    def card(self, parent, style="Card.TFrame", padding=18):
        return ttk.Frame(parent, style=style, padding=self.px(padding))

    def build(self):
        page = ttk.Frame(self, style="Page.TFrame", padding=self.px(30))
        page.pack(fill="both", expand=True)
        ttk.Label(page, text=f"MemoryPal {VERSION}", style="Title.TLabel").pack(anchor="w")
        ttk.Label(page, text="This milestone makes cues visible during testing, expands Associations, and replaces the page wipe with skeleton loading.", style="Muted.TLabel").pack(anchor="w", pady=(self.px(4), self.px(18)))

        hero = self.card(page, "Warm.TFrame")
        hero.pack(fill="x", pady=(0, self.px(14)))
        ttk.Label(hero, text="Skeleton loading", style="Warm.TLabel").pack(anchor="w")
        ttk.Label(hero, text="Page switches briefly show loading rows and a small spinner, which feels calmer than the old wipe animation.", style="Warm.TLabel", wraplength=self.px(900)).pack(anchor="w", pady=(self.px(8), 0))

        grid = ttk.Frame(page, style="Page.TFrame")
        grid.pack(fill="both", expand=True)
        cards = [
            ("Attached cue previews", "Text previews and image thumbnails appear in review, Test Lab, quiz, and library cue panels."),
            ("Playable media cues", "Audio and video use clear Play buttons that open the desktop player."),
            ("Association toolbox", "Acronym, mini-story, peg list, memory palace, chunk map, and link chain."),
            ("Review friendly", "The cue panel appears where the learner is actually testing, not buried as a file list."),
        ]
        for index, (title, body) in enumerate(cards):
            card = self.card(grid)
            card.grid(row=index // 2, column=index % 2, sticky="nsew", padx=(0 if index % 2 == 0 else self.px(12), 0), pady=(0, self.px(12)))
            ttk.Label(card, text=title, style="H2.TLabel").pack(anchor="w")
            ttk.Label(card, text=body, style="Muted.TLabel", wraplength=self.px(430)).pack(anchor="w", pady=(self.px(8), self.px(14)))
            ttk.Button(card, text="Open", style="Primary.TButton").pack(fill="x")
            grid.columnconfigure(index % 2, weight=1)
            grid.rowconfigure(index // 2, weight=1)


def main():
    enable_dpi_awareness()
    StageApp().mainloop()


if __name__ == "__main__":
    main()
