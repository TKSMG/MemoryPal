import sys
import ctypes
import tkinter as tk
from tkinter import ttk


VERSION = "v18 Beta"
TITLE = "Study-app polish pass"
ACCENT = "#007aff"
FEATURES = [
    "Dashboard recommends the next best study action.",
    "Focus mode groups due, weak, and fresh cards.",
    "Capture can create normal Q/A cards from question => answer lines.",
    "Library has search plus All, Due, Weak, and Captures filters.",
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
        self.geometry(f"{self.px(1180)}x{self.px(760)}")
        self.minsize(self.px(900), self.px(620))
        self.configure(bg="#f6f7fb")
        self.styles()
        self.build()

    def px(self, value):
        return int(round(value * self.scale))

    def styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Page.TFrame", background="#f6f7fb")
        style.configure("Rail.TFrame", background="#111827")
        style.configure("Card.TFrame", background="#ffffff")
        style.configure("Alt.TFrame", background="#eef5ff")
        style.configure("Title.TLabel", background="#f6f7fb", foreground="#111827", font=("Segoe UI Semibold", 26))
        style.configure("Rail.TLabel", background="#111827", foreground="#ffffff", font=("Segoe UI Semibold", 15))
        style.configure("Card.TLabel", background="#ffffff", foreground="#111827", font=("Segoe UI", 12))
        style.configure("Muted.TLabel", background="#ffffff", foreground="#6b7280", font=("Segoe UI", 11))
        style.configure("Alt.TLabel", background="#eef5ff", foreground="#111827", font=("Segoe UI", 12))
        style.configure("TButton", padding=(self.px(16), self.px(10)), font=("Segoe UI Semibold", 11))

    def build(self):
        root = ttk.Frame(self, style="Page.TFrame")
        root.pack(fill="both", expand=True)
        rail = ttk.Frame(root, style="Rail.TFrame", width=self.px(230))
        rail.pack(side="left", fill="y")
        rail.pack_propagate(False)
        ttk.Label(rail, text="MemoryPal", style="Rail.TLabel").pack(anchor="w", padx=self.px(24), pady=self.px(30))
        for label in ["Dashboard", "Focus", "Capture", "Review", "Library"]:
            ttk.Label(rail, text=label, style="Rail.TLabel").pack(anchor="w", padx=self.px(24), pady=self.px(8))

        page = ttk.Frame(root, style="Page.TFrame", padding=self.px(30))
        page.pack(side="left", fill="both", expand=True)
        ttk.Label(page, text=f"MemoryPal {VERSION}", style="Title.TLabel").pack(anchor="w")
        hero = ttk.Frame(page, style="Alt.TFrame", padding=self.px(22))
        hero.pack(fill="x", pady=(self.px(18), self.px(14)))
        ttk.Label(hero, text="Start today's review", style="Alt.TLabel").pack(anchor="w")
        ttk.Label(hero, text="3 due cards, 2 weak cards, and 4 fresh cards are ready.", style="Alt.TLabel").pack(anchor="w", pady=(self.px(6), self.px(12)))
        ttk.Button(hero, text="Start Focus Session").pack(fill="x")

        grid = ttk.Frame(page, style="Page.TFrame")
        grid.pack(fill="both", expand=True)
        for index, title in enumerate(["Focus queue", "Q/A capture", "Smart review", "Search library"]):
            card = ttk.Frame(grid, style="Card.TFrame", padding=self.px(20))
            card.grid(row=index // 2, column=index % 2, sticky="nsew", padx=(0 if index % 2 == 0 else self.px(12), 0), pady=(0, self.px(12)))
            tk.Frame(card, bg=ACCENT, height=self.px(4)).pack(fill="x", pady=(0, self.px(14)))
            ttk.Label(card, text=title, style="Card.TLabel").pack(anchor="w")
            ttk.Label(card, text=FEATURES[index], style="Muted.TLabel", wraplength=self.px(390)).pack(anchor="w", pady=self.px(8))
            grid.columnconfigure(index % 2, weight=1)
            grid.rowconfigure(index // 2, weight=1)


def main():
    enable_dpi_awareness()
    StageApp().mainloop()


if __name__ == "__main__":
    main()
