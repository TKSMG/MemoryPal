import re
import sys
import ctypes
import tkinter as tk
from difflib import SequenceMatcher
from tkinter import ttk


VERSION = "v02 Alpha"
TITLE = "Scaled UI resolution"
ACCENT = "#32ade6"
FEATURES = ["Larger default window.", "Higher minimum size.", "DPI-aware sizing for Windows."]


def enable_dpi_awareness():
    if sys.platform.startswith("win"):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except (AttributeError, OSError):
                pass


class StageApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.scale = max(1.0, min(self.winfo_fpixels("1i") / 96, 1.35))
        self.title(f"MemoryPal {VERSION}")
        self.geometry(f"{self.px(1120)}x{self.px(740)}")
        self.minsize(self.px(900), self.px(600))
        self.configure(bg="#f6f7fb")
        self.styles()
        self.build()

    def px(self, value):
        return int(round(value * self.scale))

    def font(self, family, size):
        return family, int(round(size * min(self.scale, 1.12)))

    def styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Page.TFrame", background="#f6f7fb")
        style.configure("Card.TFrame", background="#ffffff")
        style.configure("Title.TLabel", background="#f6f7fb", font=self.font("Segoe UI Semibold", 26), foreground="#111827")
        style.configure("Text.TLabel", background="#ffffff", font=self.font("Segoe UI", 12), foreground="#111827")
        style.configure("Muted.TLabel", background="#f6f7fb", font=self.font("Segoe UI", 11), foreground="#6b7280")
        style.configure("TButton", padding=(self.px(18), self.px(12)), font=self.font("Segoe UI Semibold", 11))

    def build(self):
        page = ttk.Frame(self, style="Page.TFrame", padding=self.px(32))
        page.pack(fill="both", expand=True)
        ttk.Label(page, text=f"MemoryPal {VERSION}", style="Title.TLabel").pack(anchor="w")
        ttk.Label(page, text=TITLE, style="Muted.TLabel").pack(anchor="w", pady=(self.px(6), self.px(20)))
        card = ttk.Frame(page, style="Card.TFrame", padding=self.px(24))
        card.pack(fill="both", expand=True)
        tk.Frame(card, bg=ACCENT, height=self.px(4)).pack(fill="x", pady=(0, self.px(18)))
        for feature in FEATURES:
            ttk.Label(card, text=f"- {feature}", style="Text.TLabel").pack(anchor="w", pady=(0, self.px(8)))
        ttk.Button(card, text="Scaled Action Button").pack(fill="x", pady=(self.px(14), 0))


def main():
    enable_dpi_awareness()
    StageApp().mainloop()


if __name__ == "__main__":
    main()
