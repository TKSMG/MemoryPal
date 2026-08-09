import sys
import ctypes
import tkinter as tk
from tkinter import ttk


VERSION = "v24 Beta"
TITLE = "Accessible repetition and media polish"
ACCENT = "#2563eb"
COLORS = {
    "bg": "#f6f8fc",
    "surface": "#ffffff",
    "alt": "#eef5ff",
    "warm": "#fff7ed",
    "ink": "#111827",
    "muted": "#64748b",
}


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
        self.geometry(f"{self.px(1120)}x{self.px(740)}")
        self.configure(bg=COLORS["bg"])
        self.styles()
        self.build()

    def px(self, value):
        return int(round(value * self.scale))

    def styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Page.TFrame", background=COLORS["bg"])
        style.configure("Card.TFrame", background=COLORS["surface"])
        style.configure("Alt.TFrame", background=COLORS["alt"])
        style.configure("Warm.TFrame", background=COLORS["warm"])
        style.configure("Title.TLabel", background=COLORS["bg"], foreground=COLORS["ink"], font=("Segoe UI Semibold", 27))
        style.configure("H2.TLabel", background=COLORS["surface"], foreground=COLORS["ink"], font=("Segoe UI Semibold", 17))
        style.configure("Card.TLabel", background=COLORS["surface"], foreground=COLORS["ink"], font=("Segoe UI", 12))
        style.configure("Muted.TLabel", background=COLORS["surface"], foreground=COLORS["muted"], font=("Segoe UI", 11))
        style.configure("Alt.TLabel", background=COLORS["alt"], foreground=COLORS["ink"], font=("Segoe UI", 12))
        style.configure("Warm.TLabel", background=COLORS["warm"], foreground="#9a3412", font=("Segoe UI", 12))
        style.configure("TButton", padding=(self.px(16), self.px(10)), font=("Segoe UI Semibold", 11))
        style.configure("Primary.TButton", padding=(self.px(16), self.px(10)), background=ACCENT, foreground="#ffffff", font=("Segoe UI Semibold", 11))

    def card(self, parent, style="Card.TFrame", padding=20):
        return ttk.Frame(parent, style=style, padding=self.px(padding))

    def build(self):
        page = ttk.Frame(self, style="Page.TFrame", padding=self.px(30))
        page.pack(fill="both", expand=True)
        ttk.Label(page, text=f"MemoryPal {VERSION}", style="Title.TLabel").pack(anchor="w")
        ttk.Label(page, text="This milestone removes the one-field repetition workflow and declutters media capture.", style="Muted.TLabel").pack(anchor="w", pady=(self.px(4), self.px(18)))

        top = ttk.Frame(page, style="Page.TFrame")
        top.pack(fill="x", pady=(0, self.px(14)))
        repetition = self.card(top)
        repetition.grid(row=0, column=0, sticky="nsew", padx=(0, self.px(12)))
        ttk.Label(repetition, text="Repetition item", style="H2.TLabel").pack(anchor="w")
        ttk.Label(repetition, text="Question / title", style="Muted.TLabel").pack(anchor="w", pady=(self.px(12), self.px(4)))
        ttk.Entry(repetition).pack(fill="x")
        ttk.Label(repetition, text="Answer / recall content", style="Muted.TLabel").pack(anchor="w", pady=(self.px(12), self.px(4)))
        tk.Text(repetition, height=5, wrap="word", bd=0, padx=10, pady=10, font=("Segoe UI", 12), bg="#f8fafc").pack(fill="x")
        row = ttk.Frame(repetition, style="Card.TFrame")
        row.pack(fill="x", pady=(self.px(14), 0))
        ttk.Button(row, text="Add Item", style="Primary.TButton").pack(side="left", fill="x", expand=True, padx=(0, self.px(8)))
        ttk.Button(row, text="Split Answer").pack(side="left", fill="x", expand=True)

        media = self.card(top, "Alt.TFrame")
        media.grid(row=0, column=1, sticky="nsew")
        ttk.Label(media, text="Decluttered media", style="Alt.TLabel").pack(anchor="w")
        ttk.Label(media, text="Set Builder shows one Audio button and one Video button. Import or record is chosen after clicking.", style="Alt.TLabel", wraplength=self.px(360)).pack(anchor="w", pady=(self.px(10), self.px(14)))
        ttk.Button(media, text="Add Audio", style="Primary.TButton").pack(fill="x", pady=(0, self.px(8)))
        ttk.Button(media, text="Add Video").pack(fill="x")
        top.columnconfigure(0, weight=3)
        top.columnconfigure(1, weight=2)

        bottom = self.card(page, "Warm.TFrame")
        bottom.pack(fill="x")
        ttk.Label(bottom, text="Accessibility pass", style="Warm.TLabel").pack(anchor="w")
        ttk.Label(bottom, text="Quiz and practice screens now use short guide panels, clearer button labels, hover hints, and a softer page reveal animation.", style="Warm.TLabel", wraplength=self.px(960)).pack(anchor="w", pady=(self.px(8), 0))


def main():
    enable_dpi_awareness()
    StageApp().mainloop()


if __name__ == "__main__":
    main()
