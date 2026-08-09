import sys
import ctypes
import tkinter as tk
from tkinter import ttk


VERSION = "v09 Test"
TITLE = "Home button scaling fixes"
ACCENT = "#30b0c7"
FEATURES = ["Dashboard buttons keep stable widths.", "Labels wrap instead of clipping.", "The layout works outside fullscreen."]


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
        self.geometry(f"{self.px(1000)}x{self.px(650)}")
        self.minsize(self.px(760), self.px(520))
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
        style.configure("TButton", padding=(16, 10), font=("Segoe UI Semibold", 11))

    def build(self):
        page = ttk.Frame(self, style="Page.TFrame", padding=self.px(28))
        page.pack(fill="both", expand=True)
        ttk.Label(page, text=f"MemoryPal {VERSION}", style="Title.TLabel").pack(anchor="w")
        grid = ttk.Frame(page, style="Page.TFrame")
        grid.pack(fill="x", pady=(self.px(18), 0))
        for index, title in enumerate(["Capture Material", "Spaced Review", "Repetition Path", "Library"]):
            card = ttk.Frame(grid, style="Card.TFrame", padding=self.px(18))
            card.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else self.px(10), 0))
            tk.Frame(card, bg=ACCENT, height=self.px(4)).pack(fill="x", pady=(0, self.px(10)))
            ttk.Label(card, text=title, style="Text.TLabel", wraplength=self.px(170)).pack(anchor="w")
            ttk.Button(card, text="Open").pack(fill="x", pady=(self.px(12), 0))
            grid.columnconfigure(index, weight=1, uniform="actions")


def main():
    enable_dpi_awareness()
    StageApp().mainloop()


if __name__ == "__main__":
    main()
