import sys
import ctypes
import tkinter as tk
from tkinter import ttk


VERSION = "v28 Beta"
TITLE = "App feel visual polish"
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
        style.configure("Header.TFrame", background="#ffffff")
        style.configure("Card.TFrame", background="#ffffff")
        style.configure("Title.TLabel", background="#ffffff", foreground="#111827", font=("Segoe UI Semibold", 28))
        style.configure("Muted.TLabel", background="#ffffff", foreground="#5f6f85", font=("Segoe UI", 11))
        style.configure("H2.TLabel", background="#ffffff", foreground="#111827", font=("Segoe UI Semibold", 17))
        style.configure("TButton", padding=(self.px(18), self.px(12)), background="#f8fbff", foreground="#111827", borderwidth=0, relief="flat", font=("Segoe UI Semibold", 11))
        style.configure("Primary.TButton", padding=(self.px(18), self.px(12)), background=ACCENT, foreground="#ffffff", borderwidth=0, relief="flat", font=("Segoe UI Semibold", 11))
        style.configure("TMenubutton", padding=(self.px(18), self.px(12)), background="#f8fbff", foreground="#111827", borderwidth=0, relief="flat", font=("Segoe UI Semibold", 11))

    def card(self, parent, padding=22):
        return ttk.Frame(parent, style="Card.TFrame", padding=self.px(padding))

    def build(self):
        page = ttk.Frame(self, style="Page.TFrame", padding=self.px(28))
        page.pack(fill="both", expand=True)
        header = ttk.Frame(page, style="Header.TFrame", padding=self.px(22))
        header.pack(fill="x", pady=(0, self.px(16)))
        ttk.Label(header, text="MemoryPal", style="Title.TLabel").pack(side="left")
        tk.Label(header, text="Local save", bg="#edf6ff", fg=ACCENT, padx=12, pady=7, font=("Segoe UI Semibold", 10)).pack(side="right")
        ttk.Button(header, text="Backup").pack(side="right", padx=(0, self.px(10)))

        hero = self.card(page)
        hero.pack(fill="x", pady=(0, self.px(14)))
        tk.Frame(hero, bg=ACCENT, width=self.px(5), height=self.px(62)).pack(side="left", fill="y", padx=(0, self.px(16)))
        text = ttk.Frame(hero, style="Card.TFrame")
        text.pack(side="left", fill="x", expand=True)
        ttk.Label(text, text="Start today's review", style="H2.TLabel").pack(anchor="w")
        ttk.Label(text, text="A warmer app shell, softer controls, hover cards, and cleaner menu buttons make the desktop build feel more intentional.", style="Muted.TLabel", wraplength=self.px(720)).pack(anchor="w", pady=(self.px(6), 0))
        ttk.Button(hero, text="Open", style="Primary.TButton").pack(side="right")

        grid = ttk.Frame(page, style="Page.TFrame")
        grid.pack(fill="both", expand=True)
        for index, label in enumerate(["Soft app header", "Restyled buttons", "Styled cue menus", "Hover-highlight cards"]):
            card = self.card(grid, 18)
            card.grid(row=index // 2, column=index % 2, sticky="nsew", padx=(0 if index % 2 == 0 else self.px(12), 0), pady=(0, self.px(12)))
            ttk.Label(card, text=label, style="H2.TLabel").pack(anchor="w")
            ttk.Label(card, text="Keeps the app lightweight while reducing the plain stock-desktop feeling.", style="Muted.TLabel", wraplength=self.px(420)).pack(anchor="w", pady=(self.px(8), 0))
            grid.columnconfigure(index % 2, weight=1)
            grid.rowconfigure(index // 2, weight=1)


def main():
    enable_dpi_awareness()
    StageApp().mainloop()


if __name__ == "__main__":
    main()
