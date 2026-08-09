import sys
import ctypes
import tkinter as tk
from tkinter import ttk


VERSION = "v29 Beta"
TITLE = "Page draft preservation"
ACCENT = "#007aff"


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
        self.geometry(f"{self.px(1120)}x{self.px(720)}")
        self.configure(bg="#f4f7fb")
        self.styles()
        self.build()

    def px(self, value):
        return int(round(value * self.scale))

    def styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Page.TFrame", background="#f4f7fb")
        style.configure("Card.TFrame", background="#ffffff")
        style.configure("Alt.TFrame", background="#edf6ff")
        style.configure("Title.TLabel", background="#f4f7fb", foreground="#111827", font=("Segoe UI Semibold", 27))
        style.configure("H2.TLabel", background="#ffffff", foreground="#111827", font=("Segoe UI Semibold", 17))
        style.configure("Card.TLabel", background="#ffffff", foreground="#111827", font=("Segoe UI", 12))
        style.configure("Muted.TLabel", background="#ffffff", foreground="#5f6f85", font=("Segoe UI", 11))
        style.configure("TButton", padding=(self.px(18), self.px(12)), background="#f8fbff", foreground="#111827", borderwidth=0, relief="flat", font=("Segoe UI Semibold", 11))
        style.configure("Primary.TButton", padding=(self.px(18), self.px(12)), background=ACCENT, foreground="#ffffff", borderwidth=0, relief="flat", font=("Segoe UI Semibold", 11))

    def card(self, parent, padding=20):
        return ttk.Frame(parent, style="Card.TFrame", padding=self.px(padding))

    def build(self):
        page = ttk.Frame(self, style="Page.TFrame", padding=self.px(30))
        page.pack(fill="both", expand=True)
        ttk.Label(page, text=f"MemoryPal {VERSION}", style="Title.TLabel").pack(anchor="w")
        ttk.Label(page, text="This milestone keeps in-progress work when users move between pages.", style="Muted.TLabel").pack(anchor="w", pady=(self.px(4), self.px(18)))

        hero = self.card(page)
        hero.pack(fill="x", pady=(0, self.px(14)))
        ttk.Label(hero, text="Switch pages without losing work", style="H2.TLabel").pack(anchor="w")
        ttk.Label(hero, text="Capture drafts, repetition items, Test Lab answers, quiz progress, association outputs, and puzzle state are saved in memory before navigation.", style="Muted.TLabel", wraplength=self.px(920)).pack(anchor="w", pady=(self.px(8), self.px(14)))
        ttk.Button(hero, text="Saved Draft", style="Primary.TButton").pack(fill="x")

        grid = ttk.Frame(page, style="Page.TFrame")
        grid.pack(fill="both", expand=True)
        for index, label in enumerate(["Capture", "Repetition", "Test Lab", "Quiz", "Associations", "Puzzles"]):
            card = self.card(grid, 16)
            card.grid(row=index // 3, column=index % 3, sticky="nsew", padx=(0 if index % 3 == 0 else self.px(10), 0), pady=(0, self.px(10)))
            ttk.Label(card, text=label, style="H2.TLabel").pack(anchor="w")
            ttk.Label(card, text="In-progress state is restored when returning to this page.", style="Muted.TLabel", wraplength=self.px(280)).pack(anchor="w", pady=(self.px(8), 0))
            grid.columnconfigure(index % 3, weight=1)
            grid.rowconfigure(index // 3, weight=1)


def main():
    enable_dpi_awareness()
    StageApp().mainloop()


if __name__ == "__main__":
    main()
