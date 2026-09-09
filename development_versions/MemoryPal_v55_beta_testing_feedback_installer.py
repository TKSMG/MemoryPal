"""
MemoryPal v55 beta - testing feedback and installer path.

This milestone records the move from a polished prototype toward a build that
can be shared with testers over longer periods.
"""

import csv
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, ttk


COLORS = {
    "bg": "#111827",
    "surface": "#192338",
    "alt": "#273852",
    "ink": "#edf2fb",
    "muted": "#aeb8cb",
    "primary": "#65afff",
    "green": "#37d67a",
    "orange": "#ffab3d",
    "line": "#33445f",
    "white": "#ffffff",
}


class FeedbackDemo(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MemoryPal v55 - Testing Feedback")
        self.geometry("860x560")
        self.minsize(680, 460)
        self.configure(bg=COLORS["bg"])
        self.feedback = []
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self.style.configure("Card.TFrame", background=COLORS["surface"])
        self.style.configure("TButton", padding=(12, 8), font=("Segoe UI Semibold", 10))
        self.style.configure("Title.TLabel", background=COLORS["surface"], foreground=COLORS["ink"], font=("Segoe UI Semibold", 20))
        self.style.configure("Body.TLabel", background=COLORS["surface"], foreground=COLORS["muted"], font=("Segoe UI", 11))
        self.build()

    def build(self):
        shell = ttk.Frame(self, style="Card.TFrame", padding=28)
        shell.pack(fill="both", expand=True, padx=28, pady=28)
        ttk.Label(shell, text="Testing Feedback Log", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            shell,
            text="A local log helps testers record confusing moments, bugs, accessibility issues, and feature ideas.",
            style="Body.TLabel",
            wraplength=720,
        ).pack(anchor="w", pady=(6, 16))

        row = ttk.Frame(shell, style="Card.TFrame")
        row.pack(fill="x", pady=(0, 12))
        self.rating = tk.StringVar(value="5")
        self.category = tk.StringVar(value="Usability")
        ttk.Combobox(row, textvariable=self.rating, values=["1", "2", "3", "4", "5"], state="readonly", width=8).pack(side="left", padx=(0, 10))
        ttk.Combobox(row, textvariable=self.category, values=["Usability", "Bug", "Confusing", "Accessibility", "Feature idea"], state="readonly", width=20).pack(side="left")

        self.note = tk.Text(shell, height=7, bg=COLORS["alt"], fg=COLORS["ink"], insertbackground=COLORS["ink"], relief="flat", wrap="word", font=("Segoe UI", 11))
        self.note.pack(fill="x", pady=(0, 12))

        actions = ttk.Frame(shell, style="Card.TFrame")
        actions.pack(fill="x")
        ttk.Button(actions, text="Save Feedback", command=self.save_feedback).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Export CSV", command=self.export_feedback).pack(side="left")

        self.recent = ttk.Label(shell, text="No notes yet.", style="Body.TLabel", wraplength=720)
        self.recent.pack(anchor="w", pady=(18, 0))

    def save_feedback(self):
        text = self.note.get("1.0", "end").strip()
        if not text:
            self.recent.configure(text="Add a tester note first.")
            return
        self.feedback.insert(0, {
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "rating": self.rating.get(),
            "category": self.category.get(),
            "note": text,
        })
        self.note.delete("1.0", "end")
        self.recent.configure(text=f"Saved {len(self.feedback)} feedback note(s). Latest: {text[:90]}")

    def export_feedback(self):
        if not self.feedback:
            self.recent.configure(text="No feedback to export yet.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="memorypal-feedback.csv")
        if not path:
            return
        with Path(path).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["created_at", "rating", "category", "note"])
            writer.writeheader()
            writer.writerows(self.feedback)
        self.recent.configure(text=f"Exported feedback to {path}")


if __name__ == "__main__":
    FeedbackDemo().mainloop()
