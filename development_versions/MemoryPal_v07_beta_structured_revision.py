import sys
import ctypes
import tkinter as tk
from tkinter import ttk


VERSION = "v07 Beta"
TITLE = "Structured non-random revision path"
ACCENT = "#ff2d55"
FEATURES = ["Revision order is intentional instead of random.", "Newer items pull older ones back into practice.", "The path is visible before the user starts."]


def enable_dpi_awareness():
    if sys.platform.startswith("win"):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            pass


def revision_path(count=5):
    path = []
    for current in range(1, count + 1):
        window = list(range(current, max(0, current - 3), -1))
        path.append("-".join(str(item) for item in window))
    return path


class StageApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.scale = max(1.0, min(self.winfo_fpixels("1i") / 96, 1.3))
        self.title(f"MemoryPal {VERSION}")
        self.geometry(f"{self.px(1040)}x{self.px(680)}")
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
        style.configure("TButton", padding=(16, 10), font=("Segoe UI Semibold", 11))

    def build(self):
        page = ttk.Frame(self, style="Page.TFrame", padding=self.px(28))
        page.pack(fill="both", expand=True)
        ttk.Label(page, text=f"MemoryPal {VERSION}", style="Title.TLabel").pack(anchor="w")
        card = ttk.Frame(page, style="Card.TFrame", padding=self.px(24))
        card.pack(fill="both", expand=True, pady=(self.px(18), 0))
        tk.Frame(card, bg=ACCENT, height=self.px(4)).pack(fill="x", pady=(0, self.px(16)))
        ttk.Label(card, text=TITLE, style="H2.TLabel").pack(anchor="w")
        output = ttk.Label(card, text=" -> ".join(revision_path(5)), style="Text.TLabel", wraplength=self.px(880))
        output.pack(anchor="w", pady=self.px(14))
        ttk.Button(card, text="Preview Structured Revision", command=lambda: output.configure(text=" -> ".join(revision_path(7)))).pack(fill="x")


def main():
    enable_dpi_awareness()
    StageApp().mainloop()


if __name__ == "__main__":
    main()
