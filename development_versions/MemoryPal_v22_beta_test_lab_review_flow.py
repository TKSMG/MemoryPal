import sys
import ctypes
import tkinter as tk
from tkinter import ttk


VERSION = "v22 Beta"
TITLE = "Test Lab review flow"
ACCENT = "#af52de"
FEATURES = [
    "Review opens a short start page and sends cards into Test Lab.",
    "Test Lab can Smart Check, reveal, and schedule review cards.",
    "Self-check quiz uses Test Lab instead of inline answer panels.",
    "Multiple choice remains in-place because it behaves like a quick game.",
]


def enable_dpi_awareness():
    if sys.platform.startswith("win"):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            pass


class StageApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.scale = max(1.0, min(self.winfo_fpixels("1i") / 96, 1.3))
        self.title(f"MemoryPal {VERSION}")
        self.geometry(f"{self.px(1100)}x{self.px(720)}")
        self.configure(bg="#f6f7fb")
        self.styles()
        self.build()

    def px(self, value):
        return int(round(value * self.scale))

    def styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Page.TFrame", background="#f6f7fb")
        style.configure("Card.TFrame", background="#ffffff")
        style.configure("Alt.TFrame", background="#eef5ff")
        style.configure("Title.TLabel", background="#f6f7fb", foreground="#111827", font=("Segoe UI Semibold", 26))
        style.configure("Card.TLabel", background="#ffffff", foreground="#111827", font=("Segoe UI", 12))
        style.configure("Muted.TLabel", background="#ffffff", foreground="#6b7280", font=("Segoe UI", 11))
        style.configure("TButton", padding=(self.px(16), self.px(10)), font=("Segoe UI Semibold", 11))

    def build(self):
        page = ttk.Frame(self, style="Page.TFrame", padding=self.px(30))
        page.pack(fill="both", expand=True)
        ttk.Label(page, text=f"MemoryPal {VERSION}", style="Title.TLabel").pack(anchor="w")
        lab = ttk.Frame(page, style="Card.TFrame", padding=self.px(24))
        lab.pack(fill="x", pady=(self.px(18), self.px(14)))
        tk.Frame(lab, bg=ACCENT, height=self.px(4)).pack(fill="x", pady=(0, self.px(14)))
        ttk.Label(lab, text="Review now uses Test Lab", style="Card.TLabel").pack(anchor="w")
        ttk.Label(lab, text="The card prompt, answer box, reveal, Smart Check, bucket highlight, and rating buttons live on one dedicated testing page.", style="Muted.TLabel", wraplength=self.px(900)).pack(anchor="w", pady=(self.px(8), self.px(12)))
        ttk.Button(lab, text="Start in Test Lab").pack(fill="x")

        grid = ttk.Frame(page, style="Page.TFrame")
        grid.pack(fill="both", expand=True)
        for index, feature in enumerate(FEATURES):
            card = ttk.Frame(grid, style="Card.TFrame", padding=self.px(18))
            card.grid(row=index // 2, column=index % 2, sticky="nsew", padx=(0 if index % 2 == 0 else self.px(12), 0), pady=(0, self.px(12)))
            ttk.Label(card, text=feature, style="Card.TLabel", wraplength=self.px(420)).pack(anchor="w")
            grid.columnconfigure(index % 2, weight=1)
            grid.rowconfigure(index // 2, weight=1)


def main():
    enable_dpi_awareness()
    StageApp().mainloop()


if __name__ == "__main__":
    main()
