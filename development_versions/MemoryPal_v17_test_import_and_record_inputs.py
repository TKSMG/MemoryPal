import sys
import ctypes
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


VERSION = "v17 Test"
TITLE = "Imported and on-demand text/audio/video inputs"
ACCENT = "#34c759"
FEATURES = ["Text, audio, and video can be imported as files.", "Typed or dictated text can be saved as an on-demand text note.", "Audio/video record buttons are prepared for desktop dependencies and future mobile native recorders."]


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
        self.geometry(f"{self.px(1080)}x{self.px(740)}")
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

    def import_file(self, kind, status):
        selected = filedialog.askopenfilename(title=f"Import {kind}")
        if selected:
            self.media[kind] = selected
            status.configure(text="\n".join(f"{name.title()}: {Path(path).name}" for name, path in self.media.items()))

    def save_text_note(self, box, status):
        path = filedialog.asksaveasfilename(title="Save text note", defaultextension=".txt", filetypes=[("Text files", "*.txt")])
        if not path:
            return
        Path(path).write_text(box.get("1.0", "end").strip() + "\n", encoding="utf-8")
        self.media["text note"] = path
        status.configure(text=f"Saved text note: {Path(path).name}")

    def recorder_notice(self, kind):
        package = "sounddevice" if kind == "audio" else "opencv-python"
        messagebox.showinfo(
            f"Record {kind.title()}",
            f"The latest desktop app can record {kind} when {package} is installed. A future mobile version should use the phone's native recorder.",
        )

    def build(self):
        page = ttk.Frame(self, style="Page.TFrame", padding=self.px(28))
        page.pack(fill="both", expand=True)
        ttk.Label(page, text=f"MemoryPal {VERSION}", style="Title.TLabel").pack(anchor="w")
        card = ttk.Frame(page, style="Card.TFrame", padding=self.px(24))
        card.pack(fill="both", expand=True, pady=(self.px(18), 0))
        tk.Frame(card, bg=ACCENT, height=self.px(4)).pack(fill="x", pady=(0, self.px(14)))
        for feature in FEATURES:
            ttk.Label(card, text=f"- {feature}", style="Text.TLabel", wraplength=self.px(900)).pack(anchor="w", pady=(0, self.px(6)))
        box = tk.Text(card, height=4, wrap="word", padx=12, pady=10)
        box.pack(fill="x", pady=self.px(10))
        box.insert("1.0", "Type or dictate a quick note here, then save it as a text record.")
        status = ttk.Label(card, text="No imports or recordings yet.", style="Muted.TLabel", wraplength=self.px(900))
        status.pack(anchor="w", pady=(0, self.px(12)))
        for kind in ("text", "audio", "video"):
            ttk.Button(card, text=f"Import {kind.title()} File", command=lambda value=kind: self.import_file(value, status)).pack(fill="x", pady=(0, self.px(8)))
        ttk.Button(card, text="Save Text Note", command=lambda: self.save_text_note(box, status)).pack(fill="x", pady=(0, self.px(8)))
        ttk.Button(card, text="Record Audio", command=lambda: self.recorder_notice("audio")).pack(fill="x", pady=(0, self.px(8)))
        ttk.Button(card, text="Record Video", command=lambda: self.recorder_notice("video")).pack(fill="x")


def main():
    enable_dpi_awareness()
    StageApp().mainloop()


if __name__ == "__main__":
    main()
