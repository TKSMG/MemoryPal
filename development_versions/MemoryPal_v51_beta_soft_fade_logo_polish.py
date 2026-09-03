"""
MemoryPal v51 beta - soft fade and logo polish.

This milestone records the return of the startup-style fade for layout changes
while keeping the no-reload navigation and fullscreen behavior.
"""

import tkinter as tk
from tkinter import ttk


COLORS = {
    "bg": "#111827",
    "surface": "#192338",
    "surface_soft": "#22304a",
    "alt": "#273852",
    "ink": "#edf2fb",
    "muted": "#aeb8cb",
    "primary": "#65afff",
    "rail": "#0b1020",
    "rail_hover": "#202e47",
    "white": "#ffffff",
}


class MemoryPalDemo(tk.Tk):
    def __init__(self):
        super().__init__()
        self.withdraw()
        self.title("MemoryPal v51 - Soft Fade Logo Polish")
        self.geometry("920x580")
        self.minsize(740, 480)
        self.rail_collapsed = False
        self.fade_job = None
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self.configure(bg=COLORS["bg"])
        try:
            self.attributes("-alpha", 0.0)
        except tk.TclError:
            pass
        self.apply_styles()
        self.build_shell()
        self.deiconify()
        self.fade_window(0.0)

    def apply_styles(self):
        self.style.configure("Root.TFrame", background=COLORS["bg"])
        self.style.configure("Rail.TFrame", background=COLORS["rail"])
        self.style.configure("Page.TFrame", background=COLORS["bg"])
        self.style.configure("Card.TFrame", background=COLORS["surface"])
        self.style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["ink"], font=("Segoe UI", 11))
        self.style.configure("Card.TLabel", background=COLORS["surface"], foreground=COLORS["ink"], font=("Segoe UI", 11))
        self.style.configure("Muted.TLabel", background=COLORS["surface"], foreground=COLORS["muted"], font=("Segoe UI", 10))
        self.style.configure("TButton", padding=(14, 10), background=COLORS["surface_soft"], foreground=COLORS["ink"], borderwidth=0)

    def fade_window(self, start=0.94, step=0):
        if self.fade_job:
            try:
                self.after_cancel(self.fade_job)
            except tk.TclError:
                pass
        steps = (start, 0.70, 0.86, 0.96, 1.0) if start < 0.5 else (start, 0.96, 0.98, 0.99, 1.0)
        try:
            self.attributes("-alpha", steps[min(step, len(steps) - 1)])
        except tk.TclError:
            return
        if step < len(steps) - 1:
            self.fade_job = self.after(18, lambda: self.fade_window(start, step + 1))
        else:
            self.fade_job = None

    def build_shell(self):
        root = ttk.Frame(self, style="Root.TFrame")
        root.pack(fill="both", expand=True)
        self.rail = ttk.Frame(root, width=250, style="Rail.TFrame")
        self.rail.pack(side="left", fill="y")
        self.rail.pack_propagate(False)
        self.main = ttk.Frame(root, style="Page.TFrame")
        self.main.pack(side="left", fill="both", expand=True)
        self.render_rail()
        ttk.Label(self.main, text="Soft layout changes", font=("Segoe UI Semibold", 24), style="TLabel").pack(anchor="w", padx=28, pady=(28, 10))
        card = ttk.Frame(self.main, style="Card.TFrame", padding=24)
        card.pack(fill="x", padx=28)
        ttk.Label(card, text="Question", style="Card.TLabel", font=("Segoe UI Semibold", 14)).pack(anchor="w")
        self.question = ttk.Entry(card)
        self.question.insert(0, "What should happen when the rail collapses?")
        self.question.pack(fill="x", pady=(6, 14))
        ttk.Label(card, text="Answer", style="Card.TLabel", font=("Segoe UI Semibold", 14)).pack(anchor="w")
        self.answer = ttk.Entry(card)
        self.answer.insert(0, "The page stays in place and gently reveals.")
        self.answer.pack(fill="x", pady=(6, 14))
        ttk.Label(card, text="The rail mark represents the generated MemoryPal logo in the full app, with a drawn fallback when image support is missing.", style="Muted.TLabel", wraplength=560).pack(anchor="w", pady=(0, 12))
        ttk.Button(card, text="Soft Reveal", command=lambda: self.fade_window(0.94)).pack(anchor="w")

    def render_rail(self):
        for child in self.rail.winfo_children():
            child.destroy()
        self.rail.configure(width=78 if self.rail_collapsed else 250)
        logo = tk.Canvas(self.rail, width=54, height=54, bg=COLORS["rail"], highlightthickness=0)
        logo.pack(anchor="center", pady=(24, 12))
        logo.create_rectangle(9, 9, 45, 45, fill=COLORS["primary"], outline="")
        logo.create_line(17, 39, 17, 17, 27, 33, 39, 17, 39, 39, fill=COLORS["white"], width=4, capstyle="round", joinstyle="round")
        toggle = ttk.Button(self.rail, text=">" if self.rail_collapsed else "<  Collapse", command=self.toggle_rail)
        toggle.pack(fill="x", padx=14, pady=(0, 12))
        for label in ("Dashboard", "Review", "Puzzles", "Stats"):
            ttk.Button(self.rail, text=label[:1] if self.rail_collapsed else label).pack(fill="x", padx=14, pady=4)

    def toggle_rail(self):
        self.rail_collapsed = not self.rail_collapsed
        self.render_rail()
        self.fade_window(0.96)


if __name__ == "__main__":
    MemoryPalDemo().mainloop()
