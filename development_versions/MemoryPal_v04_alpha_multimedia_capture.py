import sys
import ctypes
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk


VERSION = "v04 Alpha"
TITLE = "Media support beyond flashcards"
ACCENT = "#ff9500"
FEATURES = ["Image cues attach to captures.", "Audio cues attach to captures.", "Media is shared beyond flashcards."]


def enable_dpi_awareness():
    if sys.platform.startswith("win"):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            pass


class StageApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.media = {}
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
        style.configure("Title.TLabel", background="#f6f7fb", font=("Segoe UI Semibold", 25), foreground="#111827")
        style.configure("Text.TLabel", background="#ffffff", font=("Segoe UI", 12), foreground="#111827")
        style.configure("TButton", padding=(16, 10), font=("Segoe UI Semibold", 11))

    def import_file(self, kind, label):
        path = filedialog.askopenfilename(title=f"Import {kind}")
        if path:
            self.media[kind] = path
            label.configure(text="\n".join(f"{name.title()}: {Path(value).name}" for name, value in self.media.items()))

    def build(self):
        page = ttk.Frame(self, style="Page.TFrame", padding=self.px(28))
        page.pack(fill="both", expand=True)
        ttk.Label(page, text=f"MemoryPal {VERSION}", style="Title.TLabel").pack(anchor="w")
        card = ttk.Frame(page, style="Card.TFrame", padding=self.px(22))
        card.pack(fill="both", expand=True, pady=(self.px(18), 0))
        tk.Frame(card, bg=ACCENT, height=self.px(4)).pack(fill="x", pady=(0, self.px(14)))
        for feature in FEATURES:
            ttk.Label(card, text=f"- {feature}", style="Text.TLabel").pack(anchor="w")
        status = ttk.Label(card, text="No media selected yet.", style="Text.TLabel", wraplength=self.px(880))
        status.pack(anchor="w", pady=self.px(12))
        ttk.Button(card, text="Import Image", command=lambda: self.import_file("image", status)).pack(fill="x", pady=(0, self.px(8)))
        ttk.Button(card, text="Import Audio", command=lambda: self.import_file("audio", status)).pack(fill="x")


def main():
    enable_dpi_awareness()
    StageApp().mainloop()


if __name__ == "__main__":
    main()
