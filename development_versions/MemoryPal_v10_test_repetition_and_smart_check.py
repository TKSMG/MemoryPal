import re
import sys
import ctypes
import tkinter as tk
from difflib import SequenceMatcher
from tkinter import ttk


VERSION = "v10 Test"
TITLE = "Start/range repetition and smart checking"
ACCENT = "#007aff"
FEATURES = ["Shuffle becomes a start/range repetition path.", "Smart Check scores typed responses.", "The score suggests how much repetition is needed."]


def enable_dpi_awareness():
    if sys.platform.startswith("win"):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            pass


def repetition_path(count, start, span):
    start = min(max(start, 1), count) - 1
    steps, current = [], []
    for offset in range(max(1, span)):
        index = start - offset
        if index < 0:
            break
        current.append(index)
        steps.append("-".join(str(item + 1) for item in current))
    if current and current[-1] > 0:
        steps.append("-".join(str(item + 1) for item in range(current[-1], -1, -1)))
    return steps


def score_answer(response, expected):
    response, expected = response.lower().strip(), expected.lower().strip()
    words = set(re.findall(r"[a-z0-9']{3,}", expected))
    hits = len(words & set(re.findall(r"[a-z0-9']{3,}", response))) / max(1, len(words))
    score = round((SequenceMatcher(None, response, expected).ratio() * 0.35 + hits * 0.65) * 100)
    reps = 1 if score >= 80 else 2 if score >= 60 else 4
    return score, reps


class StageApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.scale = max(1.0, min(self.winfo_fpixels("1i") / 96, 1.3))
        self.title(f"MemoryPal {VERSION}")
        self.geometry(f"{self.px(1060)}x{self.px(720)}")
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
        result = ttk.Label(card, text="Path: " + " -> ".join(repetition_path(5, 5, 3)), style="Text.TLabel", wraplength=self.px(900))
        result.pack(anchor="w", pady=(0, self.px(12)))
        expected = "Spaced repetition means reviewing information at increasing intervals."
        ttk.Label(card, text=f"Expected: {expected}", style="Text.TLabel", wraplength=self.px(900)).pack(anchor="w")
        answer = tk.Text(card, height=4, wrap="word", padx=12, pady=10)
        answer.pack(fill="x", pady=self.px(10))
        answer.insert("1.0", "Reviewing information after longer gaps.")
        ttk.Button(card, text="Smart Check", command=lambda: result.configure(text=f"Path: {' -> '.join(repetition_path(5, 5, 3))}\nScore/Reps: {score_answer(answer.get('1.0', 'end'), expected)}")).pack(fill="x")


def main():
    enable_dpi_awareness()
    StageApp().mainloop()


if __name__ == "__main__":
    main()
