import re
import sys
import ctypes
import tkinter as tk
from tkinter import ttk


VERSION = "v12 Test"
TITLE = "Chunk-based capture and card creation"
ACCENT = "#34c759"
FEATURES = ["Capture becomes a study-set builder.", "Each bit is stored separately.", "Make Cards creates one card per chunk."]


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
    return [re.sub(r"^[-*\d.)\s]+", "", line).strip() for line in text.splitlines() if line.strip()]


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
        card = ttk.Frame(page, style="Card.TFrame", padding=self.px(24))
        card.pack(fill="both", expand=True, pady=(self.px(18), 0))
        tk.Frame(card, bg=ACCENT, height=self.px(4)).pack(fill="x", pady=(0, self.px(14)))
        box = tk.Text(card, height=6, wrap="word", padx=12, pady=10)
        box.pack(fill="x")
        box.insert("1.0", "1. Term one/n2. Term two/n3. Term three")
        output = ttk.Label(card, text="", style="Text.TLabel", wraplength=self.px(900))
        output.pack(anchor="w", pady=self.px(12))
        ttk.Button(card, text="Make Cards From Chunks", command=lambda: output.configure(text=f"Created {len(split_bits(box.get('1.0', 'end')))} separate cards.")).pack(fill="x")


def main():
    enable_dpi_awareness()
    StageApp().mainloop()


if __name__ == "__main__":
    main()
