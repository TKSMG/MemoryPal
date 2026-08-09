import re
import sys
import ctypes
import tkinter as tk
from difflib import SequenceMatcher
from tkinter import ttk


VERSION = "v16 Test"
TITLE = "Prompt-answer practice modes"
ACCENT = "#007aff"
FEATURES = ["Question/title prompt appears first.", "Users can reveal or smart-check.", "Repetition is open-ended instead of fixed rounds."]


def enable_dpi_awareness():
    if sys.platform.startswith("win"):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            pass


def score_answer(response, expected):
    response, expected = response.lower().strip(), expected.lower().strip()
    words = set(re.findall(r"[a-z0-9']{3,}", expected))
    hits = len(words & set(re.findall(r"[a-z0-9']{3,}", response))) / max(1, len(words))
    return round((SequenceMatcher(None, response, expected).ratio() * 0.4 + hits * 0.6) * 100)


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
        style.configure("Muted.TLabel", background="#ffffff", foreground="#6b7280", font=("Segoe UI", 11))
        style.configure("TButton", padding=(16, 10), font=("Segoe UI Semibold", 11))

    def build(self):
        expected = "Trying to recall the answer before rereading or revealing it."
        page = ttk.Frame(self, style="Page.TFrame", padding=self.px(28))
        page.pack(fill="both", expand=True)
        ttk.Label(page, text=f"MemoryPal {VERSION}", style="Title.TLabel").pack(anchor="w")
        card = ttk.Frame(page, style="Card.TFrame", padding=self.px(24))
        card.pack(fill="both", expand=True, pady=(self.px(18), 0))
        tk.Frame(card, bg=ACCENT, height=self.px(4)).pack(fill="x", pady=(0, self.px(14)))
        ttk.Label(card, text="What is retrieval practice?", style="Text.TLabel").pack(anchor="w")
        ttk.Label(card, text="Answer from memory, then reveal or smart-check.", style="Muted.TLabel").pack(anchor="w", pady=(0, self.px(10)))
        answer = tk.Text(card, height=4, wrap="word", padx=12, pady=10)
        answer.pack(fill="x")
        result = ttk.Label(card, text="", style="Text.TLabel", wraplength=self.px(900))
        result.pack(anchor="w", pady=self.px(12))
        ttk.Button(card, text="Reveal Answer", command=lambda: result.configure(text=expected)).pack(fill="x", pady=(0, self.px(8)))
        ttk.Button(card, text="Smart Check", command=lambda: result.configure(text=f"Smart Check: {score_answer(answer.get('1.0', 'end'), expected)}% close.")).pack(fill="x")


def main():
    enable_dpi_awareness()
    StageApp().mainloop()


if __name__ == "__main__":
    main()
