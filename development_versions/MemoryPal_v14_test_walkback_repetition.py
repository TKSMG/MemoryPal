import sys
import ctypes
import tkinter as tk
from tkinter import ttk


VERSION = "v14 Test"
TITLE = "Final walk-back repetition rule"
ACCENT = "#ff375f"
FEATURES = ["After the loop, walk back to item 1.", "Start 5 and range 3 gives 5, 5-4, 5-4-3, 3-2-1.", "The rule matches the requested study pattern."]


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
        style.configure("TButton", padding=(16, 10), font=("Segoe UI Semibold", 11))

    def build(self):
        page = ttk.Frame(self, style="Page.TFrame", padding=self.px(28))
        page.pack(fill="both", expand=True)
        ttk.Label(page, text=f"MemoryPal {VERSION}", style="Title.TLabel").pack(anchor="w")
        card = ttk.Frame(page, style="Card.TFrame", padding=self.px(24))
        card.pack(fill="both", expand=True, pady=(self.px(18), 0))
        tk.Frame(card, bg=ACCENT, height=self.px(4)).pack(fill="x", pady=(0, self.px(14)))
        start = tk.StringVar(value="5")
        span = tk.StringVar(value="3")
        ttk.Entry(card, textvariable=start).pack(fill="x", pady=(0, self.px(8)))
        ttk.Entry(card, textvariable=span).pack(fill="x", pady=(0, self.px(8)))
        output = ttk.Label(card, text="", style="Text.TLabel", wraplength=self.px(900))
        output.pack(anchor="w", pady=self.px(10))

        def build_path():
            try:
                output.configure(text=" -> ".join(repetition_path(5, int(start.get()), int(span.get()))))
            except ValueError:
                output.configure(text="Use numbers for start and range.")

        ttk.Button(card, text="Build Repetition Path", command=build_path).pack(fill="x")
        build_path()


def main():
    enable_dpi_awareness()
    StageApp().mainloop()


if __name__ == "__main__":
    main()
