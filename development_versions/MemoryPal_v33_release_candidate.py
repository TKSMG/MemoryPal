"""
MemoryPal v33 release candidate

Independent milestone prototype. This version represents the release-prep stage:
clear testing notes, desktop build direction, a mobile prototype path, and a
calmer app flow inspired by modern study tools.
"""

import tkinter as tk
from tkinter import ttk


class ReleaseCandidate(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MemoryPal v33 - Release Candidate")
        self.geometry("980x660")
        self.minsize(820, 560)
        self.configure(bg="#0f172a")
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self.style.configure("TFrame", background="#0f172a")
        self.style.configure("Card.TFrame", background="#172235")
        self.style.configure("TLabel", background="#0f172a", foreground="#eef4ff", font=("Segoe UI", 12))
        self.style.configure("Card.TLabel", background="#172235", foreground="#eef4ff", font=("Segoe UI", 12))
        self.style.configure("Muted.TLabel", background="#172235", foreground="#9fb0cc", font=("Segoe UI", 10))
        self.style.configure("TButton", padding=(14, 10), background="#22314f", foreground="#eef4ff", borderwidth=0)
        self.style.configure("Primary.TButton", padding=(14, 10), background="#4d9cff", foreground="white", borderwidth=0)
        self.build()

    def build(self):
        outer = ttk.Frame(self, padding=24)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="MemoryPal release candidate", font=("Segoe UI Semibold", 28)).pack(anchor="w", pady=(0, 12))
        ttk.Label(outer, text="Desktop app, testing checklist, build path, and mobile prototype are now organized for a showcase repo.").pack(anchor="w", pady=(0, 18))
        for title, notes in [
            ("Daily study flow", ["Dashboard", "Focus queue", "Study Plan", "Stats"]),
            ("Practice flow", ["Test Lab", "Smart Check", "Repetition player", "Quiz"]),
            ("Materials", ["Chunked cards", "Notes/PDF/DOCX imports", "Image/audio/video cues"]),
            ("Release prep", ["Testing checklist", "Windows build command", "Mobile Kivy prototype"]),
        ]:
            card = ttk.Frame(outer, style="Card.TFrame", padding=18)
            card.pack(fill="x", pady=(0, 10))
            ttk.Label(card, text=title, style="Card.TLabel", font=("Segoe UI Semibold", 16)).pack(anchor="w")
            ttk.Label(card, text=", ".join(notes), style="Muted.TLabel").pack(anchor="w", pady=(4, 0))
        ttk.Button(outer, text="Ready for testing", style="Primary.TButton", command=self.destroy).pack(fill="x", pady=(8, 0))


if __name__ == "__main__":
    ReleaseCandidate().mainloop()
