import sys
import ctypes
import tkinter as tk
from tkinter import ttk


VERSION = "v05 Beta"
TITLE = "First modern UI pass"
ACCENT = "#af52de"
FEATURES = ["Cleaner color palette.", "Larger cards and buttons.", "Dashboard cards replace the plain form look."]


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
        self.geometry(f"{self.px(1080)}x{self.px(720)}")
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
        style.configure("Title.TLabel", background="#f6f7fb", foreground="#111827", font=("Segoe UI Semibold", 26))
        style.configure("Text.TLabel", background="#ffffff", foreground="#111827", font=("Segoe UI", 12))
        style.configure("H2.TLabel", background="#ffffff", foreground="#111827", font=("Segoe UI Semibold", 16))
        style.configure("TButton", padding=(16, 10), font=("Segoe UI Semibold", 11))

    def build(self):
        page = ttk.Frame(self, style="Page.TFrame", padding=self.px(30))
        page.pack(fill="both", expand=True)
        ttk.Label(page, text=f"MemoryPal {VERSION}", style="Title.TLabel").pack(anchor="w")
        grid = ttk.Frame(page, style="Page.TFrame")
        grid.pack(fill="both", expand=True, pady=(self.px(18), 0))
        for index, title in enumerate(["Capture", "Review", "Repetition", "Library"]):
            card = ttk.Frame(grid, style="Card.TFrame", padding=self.px(22))
            card.grid(row=index // 2, column=index % 2, sticky="nsew", padx=(0 if index % 2 == 0 else self.px(12), 0), pady=(0, self.px(12)))
            tk.Frame(card, bg=ACCENT, height=self.px(4)).pack(fill="x", pady=(0, self.px(14)))
            ttk.Label(card, text=title, style="H2.TLabel").pack(anchor="w")
            ttk.Label(card, text=FEATURES[index % len(FEATURES)], style="Text.TLabel", wraplength=self.px(420)).pack(anchor="w", pady=self.px(8))
            ttk.Button(card, text="Open").pack(fill="x")
            grid.columnconfigure(index % 2, weight=1)
            grid.rowconfigure(index // 2, weight=1)


def main():
    enable_dpi_awareness()
    StageApp().mainloop()


if __name__ == "__main__":
    main()
