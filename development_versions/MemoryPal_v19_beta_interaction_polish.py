import sys
import ctypes
import tkinter as tk
from tkinter import ttk


VERSION = "v19 Beta"
TITLE = "Interaction and capture polish"
ACCENT = "#32ade6"
FEATURES = [
    "Capture uses separate question and answer boxes for normal cards.",
    "Practice screens use labeled answer panels instead of plain text fields.",
    "Section changes include a subtle transition bar.",
    "Q/A parsing handles numbered question => answer lines consistently.",
]


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
        self.geometry(f"{self.px(1180)}x{self.px(760)}")
        self.configure(bg="#f6f7fb")
        self.styles()
        self.build()

    def px(self, value):
        return int(round(value * self.scale))

    def styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Page.TFrame", background="#f6f7fb")
        style.configure("Card.TFrame", background="#ffffff")
        style.configure("Alt.TFrame", background="#eef5ff")
        style.configure("Title.TLabel", background="#f6f7fb", foreground="#111827", font=("Segoe UI Semibold", 26))
        style.configure("Card.TLabel", background="#ffffff", foreground="#111827", font=("Segoe UI", 12))
        style.configure("Muted.TLabel", background="#ffffff", foreground="#6b7280", font=("Segoe UI", 11))
        style.configure("Alt.TLabel", background="#eef5ff", foreground="#111827", font=("Segoe UI", 12))
        style.configure("TButton", padding=(self.px(16), self.px(10)), font=("Segoe UI Semibold", 11))

    def build(self):
        page = ttk.Frame(self, style="Page.TFrame", padding=self.px(30))
        page.pack(fill="both", expand=True)
        ttk.Label(page, text=f"MemoryPal {VERSION}", style="Title.TLabel").pack(anchor="w")

        capture = ttk.Frame(page, style="Alt.TFrame", padding=self.px(22))
        capture.pack(fill="x", pady=(self.px(18), self.px(14)))
        ttk.Label(capture, text="Question and answer card", style="Alt.TLabel").pack(anchor="w")
        ttk.Entry(capture).pack(fill="x", pady=(self.px(8), self.px(10)))
        answer = tk.Text(capture, height=4, wrap="word", bg="#fbfdff", relief="flat", padx=self.px(12), pady=self.px(10), highlightthickness=1, highlightbackground="#dbeafe")
        answer.pack(fill="x")
        ttk.Button(capture, text="Add Q/A").pack(fill="x", pady=(self.px(10), 0))

        grid = ttk.Frame(page, style="Page.TFrame")
        grid.pack(fill="both", expand=True)
        for index, feature in enumerate(FEATURES):
            card = ttk.Frame(grid, style="Card.TFrame", padding=self.px(20))
            card.grid(row=index // 2, column=index % 2, sticky="nsew", padx=(0 if index % 2 == 0 else self.px(12), 0), pady=(0, self.px(12)))
            tk.Frame(card, bg=ACCENT, height=self.px(4)).pack(fill="x", pady=(0, self.px(14)))
            ttk.Label(card, text=feature, style="Card.TLabel", wraplength=self.px(400)).pack(anchor="w")
            grid.columnconfigure(index % 2, weight=1)
            grid.rowconfigure(index // 2, weight=1)


def main():
    enable_dpi_awareness()
    StageApp().mainloop()


if __name__ == "__main__":
    main()
