import sys
import ctypes
import tkinter as tk
from tkinter import ttk


VERSION = "v25 Test"
TITLE = "Final scroll and UX polish"
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
        self.geometry(f"{self.px(1060)}x{self.px(720)}")
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

    def card(self, parent, padding=20):
        return ttk.Frame(parent, style="Card.TFrame", padding=self.px(padding))

    def build(self):
        page = ttk.Frame(self, style="Page.TFrame", padding=self.px(30))
        page.pack(fill="both", expand=True)
        ttk.Label(page, text=f"MemoryPal {VERSION}", style="Title.TLabel").pack(anchor="w")
        ttk.Label(page, text="This final nightly polish makes Repetition scroll as one page and improves keyboard-friendly scrolling.", style="Muted.TLabel").pack(anchor="w", pady=(self.px(4), self.px(18)))

        card = self.card(page)
        card.pack(fill="x", pady=(0, self.px(14)))
        ttk.Label(card, text="One continuous Repetition page", style="H2.TLabel").pack(anchor="w")
        ttk.Label(card, text="The builder, staged items, controls, and generated rounds now live in one scrollable page so text does not disappear below the window.", style="Muted.TLabel", wraplength=self.px(900)).pack(anchor="w", pady=(self.px(8), self.px(14)))
        ttk.Button(card, text="Build Path", style="Primary.TButton").pack(fill="x")

        grid = ttk.Frame(page, style="Page.TFrame")
        grid.pack(fill="both", expand=True)
        for index, text in enumerate([
            "Stacked prompt and answer fields reduce cramped text.",
            "Generated practice rounds appear below the builder on the same scroll area.",
            "Page Up, Page Down, Home, and End work when the page is focused.",
            "The app keeps previous media, Test Lab, Smart Check, and repetition features.",
        ]):
            item = self.card(grid, 18)
            item.grid(row=index // 2, column=index % 2, sticky="nsew", padx=(0 if index % 2 == 0 else self.px(12), 0), pady=(0, self.px(12)))
            ttk.Label(item, text=text, style="Card.TLabel", wraplength=self.px(420)).pack(anchor="w")
            grid.columnconfigure(index % 2, weight=1)
            grid.rowconfigure(index // 2, weight=1)


def main():
    enable_dpi_awareness()
    StageApp().mainloop()


if __name__ == "__main__":
    main()
