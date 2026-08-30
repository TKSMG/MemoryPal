import re
import sys
import ctypes
import tkinter as tk
from difflib import SequenceMatcher
from pathlib import Path
from tkinter import filedialog, ttk


VERSION = "v01 Alpha"
TITLE = "Initial runnable PC app"
ACCENT = "#007aff"
DEMO = "cards"
FEATURES = [
    "Single-file Python/Tkinter desktop app.",
    "Basic memory trainer shell.",
    "First pass at capture, review, quiz, associations, puzzles, and library.",
]


def enable_dpi_awareness():
    if sys.platform.startswith("win"):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except (AttributeError, OSError):
                pass


def split_bits(text):
    text = (text or "").replace("\\n", "\n").replace("/n", "\n")
    text = re.sub(r"\s+(?=\d+[.)]\s+)", "\n", text)
    text = re.sub(r"\s*[|;]\s*", "\n", text)
    return [re.sub(r"^[-*\d.)\s]+", "", line).strip() for line in text.splitlines() if line.strip()]


def repetition_path(count=5, start=5, span=3):
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
    if not response:
        return 0, "Needs response"
    ratio = SequenceMatcher(None, response, expected).ratio()
    expected_words = set(re.findall(r"[a-z0-9']{3,}", expected))
    response_words = set(re.findall(r"[a-z0-9']{3,}", response))
    coverage = len(expected_words & response_words) / max(1, len(expected_words))
    score = round((ratio * 0.4 + coverage * 0.6) * 100)
    return score, "Strong match" if score >= 80 else "Close enough" if score >= 60 else "Review again"


class StageApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.scale = max(1.0, min(self.winfo_fpixels("1i") / 96, 1.3))
        self.media = {}
        self.title(f"MemoryPal {VERSION}")
        self.geometry(f"{self.px(1040)}x{self.px(700)}")
        self.minsize(self.px(820), self.px(560))
        self.configure(bg="#f6f7fb")
        self.configure_styles()
        self.build()

    def px(self, value):
        return int(round(value * self.scale))

    def font(self, family, size):
        return family, int(round(size * min(self.scale, 1.12)))

    def configure_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Page.TFrame", background="#f6f7fb")
        style.configure("Card.TFrame", background="#ffffff", relief="flat")
        style.configure("Title.TLabel", background="#f6f7fb", foreground="#111827", font=self.font("Segoe UI Semibold", 25))
        style.configure("Muted.TLabel", background="#f6f7fb", foreground="#6b7280", font=self.font("Segoe UI", 11))
        style.configure("Card.TLabel", background="#ffffff", foreground="#111827", font=self.font("Segoe UI", 12))
        style.configure("H2.TLabel", background="#ffffff", foreground="#111827", font=self.font("Segoe UI Semibold", 16))
        style.configure("TButton", padding=(self.px(16), self.px(10)), font=self.font("Segoe UI Semibold", 11))

    def card(self, parent):
        frame = ttk.Frame(parent, style="Card.TFrame", padding=self.px(20))
        frame.pack(fill="x", pady=(0, self.px(14)))
        return frame

    def build(self):
        page = ttk.Frame(self, style="Page.TFrame", padding=self.px(28))
        page.pack(fill="both", expand=True)
        ttk.Label(page, text=f"MemoryPal {VERSION}", style="Title.TLabel").pack(anchor="w")
        ttk.Label(page, text=TITLE, style="Muted.TLabel").pack(anchor="w", pady=(self.px(4), self.px(18)))
        feature_card = self.card(page)
        tk.Frame(feature_card, bg=ACCENT, height=self.px(4)).pack(fill="x", pady=(0, self.px(14)))
        ttk.Label(feature_card, text="What this version added", style="H2.TLabel").pack(anchor="w")
        for feature in FEATURES:
            ttk.Label(feature_card, text=f"- {feature}", style="Card.TLabel", wraplength=self.px(900)).pack(anchor="w", pady=(self.px(6), 0))
        demo_card = self.card(page)
        ttk.Label(demo_card, text="Working demo", style="H2.TLabel").pack(anchor="w")
        self.build_demo(demo_card)

    def build_demo(self, parent):
        if DEMO == "cards":
            count = tk.IntVar(value=2)
            ttk.Label(parent, textvariable=count, style="H2.TLabel").pack(anchor="w", pady=(self.px(8), 0))
            ttk.Label(parent, text="Cards ready for basic memory practice.", style="Card.TLabel").pack(anchor="w")
            ttk.Button(parent, text="Add Sample Card", command=lambda: count.set(count.get() + 1)).pack(fill="x", pady=(self.px(12), 0))


def main():
    enable_dpi_awareness()
    StageApp().mainloop()


if __name__ == "__main__":
    main()
