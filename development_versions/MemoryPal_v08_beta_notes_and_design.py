import sys
import ctypes
import tkinter as tk
from tkinter import ttk


VERSION = "v08 Beta"
TITLE = "Notesheet and design artifacts"
ACCENT = "#5856d6"
FEATURES = ["Memory techniques documented.", "Initial design direction recorded.", "Project history starts living alongside the code."]


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
        self.geometry(f"{self.px(1040)}x{self.px(700)}")
        self.configure(bg="#f6f7fb")
        self.style()
        self.build()

    def px(self, value):
        return int(round(value * self.scale))

    def style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Page.TFrame", background="#f6f7fb")
        style.configure("Card.TFrame", background="#ffffff")
        style.configure("Title.TLabel", background="#f6f7fb", foreground="#111827", font=("Segoe UI Semibold", 25))
        style.configure("Text.TLabel", background="#ffffff", foreground="#111827", font=("Segoe UI", 12))
        style.configure("H2.TLabel", background="#ffffff", foreground="#111827", font=("Segoe UI Semibold", 16))

    def build(self):
        page = ttk.Frame(self, style="Page.TFrame", padding=self.px(28))
        page.pack(fill="both", expand=True)
        ttk.Label(page, text=f"MemoryPal {VERSION}", style="Title.TLabel").pack(anchor="w")
        card = ttk.Frame(page, style="Card.TFrame", padding=self.px(24))
        card.pack(fill="both", expand=True, pady=(self.px(18), 0))
        tk.Frame(card, bg=ACCENT, height=self.px(4)).pack(fill="x", pady=(0, self.px(16)))
        ttk.Label(card, text=TITLE, style="H2.TLabel").pack(anchor="w")
        summary = "Study bits, prompt-answer practice, spaced review, smart checking, repetition paths, associations, puzzles, and media cues."
        ttk.Label(card, text=summary, style="Text.TLabel", wraplength=self.px(880)).pack(anchor="w", pady=self.px(12))
        for feature in FEATURES:
            ttk.Label(card, text=f"- {feature}", style="Text.TLabel").pack(anchor="w", pady=(self.px(6), 0))


def main():
    enable_dpi_awareness()
    StageApp().mainloop()


if __name__ == "__main__":
    main()
