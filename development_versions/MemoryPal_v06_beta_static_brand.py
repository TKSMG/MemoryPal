import sys
import ctypes
import tkinter as tk
from tkinter import ttk


VERSION = "v06 Beta"
TITLE = "Removed decorative animation"
ACCENT = "#111827"
FEATURES = ["No decorative top-right animation.", "Calmer interface for elderly users and learners.", "Stable brand area with no distracting motion."]


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
        style.configure("Rail.TFrame", background=ACCENT)
        style.configure("Card.TFrame", background="#ffffff")
        style.configure("Title.TLabel", background="#ffffff", foreground="#111827", font=("Segoe UI Semibold", 25))
        style.configure("Text.TLabel", background="#ffffff", foreground="#6b7280", font=("Segoe UI", 12))
        style.configure("Rail.TLabel", background=ACCENT, foreground="#ffffff", font=("Segoe UI Semibold", 17))

    def build(self):
        root = ttk.Frame(self, style="Page.TFrame")
        root.pack(fill="both", expand=True)
        rail = ttk.Frame(root, style="Rail.TFrame", width=self.px(250))
        rail.pack(side="left", fill="y")
        rail.pack_propagate(False)
        ttk.Label(rail, text="MemoryPal", style="Rail.TLabel").pack(anchor="w", padx=self.px(24), pady=self.px(30))
        card = ttk.Frame(root, style="Card.TFrame", padding=self.px(28))
        card.pack(side="left", fill="both", expand=True, padx=self.px(28), pady=self.px(28))
        ttk.Label(card, text=f"{VERSION}: {TITLE}", style="Title.TLabel").pack(anchor="w")
        for feature in FEATURES:
            ttk.Label(card, text=f"- {feature}", style="Text.TLabel", wraplength=self.px(760)).pack(anchor="w", pady=(self.px(10), 0))


def main():
    enable_dpi_awareness()
    StageApp().mainloop()


if __name__ == "__main__":
    main()
