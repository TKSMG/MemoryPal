import sys
import ctypes
import tkinter as tk
from tkinter import ttk


VERSION = "v26 Beta"
TITLE = "Puzzles and cue menus"
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
        self.geometry(f"{self.px(1080)}x{self.px(720)}")
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
        style.configure("Title.TLabel", background="#f6f8fc", foreground="#111827", font=("Segoe UI Semibold", 27))
        style.configure("H2.TLabel", background="#ffffff", foreground="#111827", font=("Segoe UI Semibold", 17))
        style.configure("Card.TLabel", background="#ffffff", foreground="#111827", font=("Segoe UI", 12))
        style.configure("Muted.TLabel", background="#ffffff", foreground="#64748b", font=("Segoe UI", 11))
        style.configure("TButton", padding=(self.px(16), self.px(10)), font=("Segoe UI Semibold", 11))
        style.configure("Primary.TButton", padding=(self.px(16), self.px(10)), background=ACCENT, foreground="#ffffff", font=("Segoe UI Semibold", 11))

    def card(self, parent, padding=18):
        return ttk.Frame(parent, style="Card.TFrame", padding=self.px(padding))

    def build(self):
        page = ttk.Frame(self, style="Page.TFrame", padding=self.px(30))
        page.pack(fill="both", expand=True)
        ttk.Label(page, text=f"MemoryPal {VERSION}", style="Title.TLabel").pack(anchor="w")
        ttk.Label(page, text="This milestone expands Puzzles and turns Set Builder media into compact cue menus.", style="Muted.TLabel").pack(anchor="w", pady=(self.px(4), self.px(18)))

        cue = self.card(page)
        cue.pack(fill="x", pady=(0, self.px(14)))
        ttk.Label(cue, text="Compact cue menu buttons", style="H2.TLabel").pack(anchor="w")
        ttk.Label(cue, text="Text, Image, Audio, and Video cues sit in one short row. Audio and Video open import/record choices from the button itself.", style="Muted.TLabel", wraplength=self.px(940)).pack(anchor="w", pady=(self.px(8), self.px(12)))
        row = ttk.Frame(cue, style="Card.TFrame")
        row.pack(fill="x")
        for label in ("TXT", "IMG", "AUD", "VID"):
            ttk.Menubutton(row, text=label).pack(side="left", fill="x", expand=True, padx=(0, self.px(8)))

        grid = ttk.Frame(page, style="Page.TFrame")
        grid.pack(fill="both", expand=True)
        for index, (title, body) in enumerate([
            ("Sequence Recall", "Watch digits, hide them, then type them back."),
            ("Word Recall", "Briefly study words pulled from saved material."),
            ("Pair Recall", "Practice prompt-answer pairs one at a time."),
            ("Missing Item", "Find the hidden item from a short sequence."),
        ]):
            card = self.card(grid)
            card.grid(row=index // 2, column=index % 2, sticky="nsew", padx=(0 if index % 2 == 0 else self.px(12), 0), pady=(0, self.px(12)))
            ttk.Label(card, text=title, style="H2.TLabel").pack(anchor="w")
            ttk.Label(card, text=body, style="Muted.TLabel", wraplength=self.px(420)).pack(anchor="w", pady=(self.px(8), self.px(14)))
            ttk.Button(card, text="Start", style="Primary.TButton").pack(fill="x")
            grid.columnconfigure(index % 2, weight=1)
            grid.rowconfigure(index // 2, weight=1)


def main():
    enable_dpi_awareness()
    StageApp().mainloop()


if __name__ == "__main__":
    main()
