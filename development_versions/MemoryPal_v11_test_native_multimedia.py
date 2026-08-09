import sys
import ctypes
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk


VERSION = "v11 Test"
TITLE = "Text, image, audio, and video support"
ACCENT = "#ff9f0a"
FEATURES = ["Text files can be imported.", "Image/audio/video cues can be imported.", "Media belongs to the study item, not only flashcards."]


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
        style.configure("Title.TLabel", background="#f6f7fb", foreground="#111827", font=("Segoe UI Semibold", 25))
        style.configure("Text.TLabel", background="#ffffff", foreground="#111827", font=("Segoe UI", 12))
        style.configure("TButton", padding=(16, 10), font=("Segoe UI Semibold", 11))

    def import_file(self, kind, status):
        selected = filedialog.askopenfilename(title=f"Import {kind}")
        if selected:
            self.media[kind] = selected
            status.configure(text="\n".join(f"{name.title()}: {Path(path).name}" for name, path in self.media.items()))

    def build(self):
        page = ttk.Frame(self, style="Page.TFrame", padding=self.px(28))
        page.pack(fill="both", expand=True)
        ttk.Label(page, text=f"MemoryPal {VERSION}", style="Title.TLabel").pack(anchor="w")
        card = ttk.Frame(page, style="Card.TFrame", padding=self.px(24))
        card.pack(fill="both", expand=True, pady=(self.px(18), 0))
        tk.Frame(card, bg=ACCENT, height=self.px(4)).pack(fill="x", pady=(0, self.px(14)))
        status = ttk.Label(card, text="No files imported yet.", style="Text.TLabel", wraplength=self.px(900))
        status.pack(anchor="w", pady=(0, self.px(12)))
        for kind in ("text", "image", "audio", "video"):
            ttk.Button(card, text=f"Import {kind.title()}", command=lambda value=kind: self.import_file(value, status)).pack(fill="x", pady=(0, self.px(8)))


def main():
    enable_dpi_awareness()
    StageApp().mainloop()


if __name__ == "__main__":
    main()
