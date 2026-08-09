import re
import sys
import ctypes
import tkinter as tk
from tkinter import ttk


VERSION = "v03 Alpha"
TITLE = "Multiple study bits and newline parsing"
ACCENT = "#34c759"
FEATURES = ["Parses /n and real newlines.", "Splits numbered lists and separators.", "Shows each study bit separately."]


def enable_dpi_awareness():
    if sys.platform.startswith("win"):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            pass


def split_bits(text):
    text = (text or "").replace("\\n", "\n").replace("/n", "\n")
    text = re.sub(r"\s+(?=\d+[.)]\s+)", "\n", text)
    text = re.sub(r"\s*[|;]\s*", "\n", text)
    lines = [re.sub(r"^[-*\d.)\s]+", "", line).strip() for line in text.splitlines()]
    return [line for line in lines if line]


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
        style.configure("TButton", padding=(16, 10), font=("Segoe UI Semibold", 11))

    def build(self):
        page = ttk.Frame(self, style="Page.TFrame", padding=self.px(28))
        page.pack(fill="both", expand=True)
        ttk.Label(page, text=f"MemoryPal {VERSION}", style="Title.TLabel").pack(anchor="w")
        card = ttk.Frame(page, style="Card.TFrame", padding=self.px(22))
        card.pack(fill="both", expand=True, pady=(self.px(18), 0))
        tk.Frame(card, bg=ACCENT, height=self.px(4)).pack(fill="x", pady=(0, self.px(14)))
        for feature in FEATURES:
            ttk.Label(card, text=f"- {feature}", style="Text.TLabel").pack(anchor="w")
        box = tk.Text(card, height=6, wrap="word", padx=12, pady=10)
        box.pack(fill="x", pady=self.px(12))
        box.insert("1.0", "1. Photosynthesis/n2. Retrieval practice | 3. Spaced review")
        result = ttk.Label(card, text="", style="Text.TLabel", wraplength=self.px(880))
        result.pack(anchor="w")
        ttk.Button(card, text="Split Into Study Bits", command=lambda: result.configure(text="\n".join(f"{i}. {bit}" for i, bit in enumerate(split_bits(box.get('1.0', 'end')), 1)))).pack(fill="x", pady=(self.px(12), 0))


def main():
    enable_dpi_awareness()
    StageApp().mainloop()


if __name__ == "__main__":
    main()
