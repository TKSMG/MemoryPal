"""
MemoryPal v49 beta - no-reload focus and navigation.

This milestone records the pass where navigation collapse, focus mode, and
fullscreen became layout changes instead of full page rebuilds.
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
        self.title("MemoryPal v49 - No Reload Layout")
        self.geometry("980x640")
        self.minsize(780, 520)
        self.rail_collapsed = False
        self.is_focus = False
        self.is_fullscreen = False
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self.configure(bg=COLORS["bg"])
        self.apply_styles()
        self.build_shell()
        self.bind("<F11>", lambda _event: self.toggle_fullscreen())
        self.bind("<Escape>", lambda _event: self.exit_modes())

    def apply_styles(self):
        self.style.configure("Root.TFrame", background=COLORS["bg"])
        self.style.configure("Rail.TFrame", background=COLORS["rail"])
        self.style.configure("Page.TFrame", background=COLORS["bg"])
        self.style.configure("Card.TFrame", background=COLORS["surface"])
        self.style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["ink"], font=("Segoe UI", 11))
        self.style.configure("Muted.TLabel", background=COLORS["bg"], foreground=COLORS["muted"], font=("Segoe UI", 10))
        self.style.configure("Card.TLabel", background=COLORS["surface"], foreground=COLORS["ink"], font=("Segoe UI", 11))
        self.style.configure("CardMuted.TLabel", background=COLORS["surface"], foreground=COLORS["muted"], font=("Segoe UI", 10))
        self.style.configure("Title.TLabel", background=COLORS["bg"], foreground=COLORS["ink"], font=("Segoe UI Semibold", 24))
        self.style.configure("TButton", padding=(14, 10), background=COLORS["surface_soft"], foreground=COLORS["ink"], borderwidth=0)
        self.style.map("TButton", background=[("active", COLORS["alt"])], foreground=[("active", COLORS["primary"])])
        self.style.configure("Nav.TButton", padding=(16, 12), background=COLORS["rail"], foreground="#d7def0", anchor="w", borderwidth=0)
        self.style.configure("ActiveNav.TButton", padding=(16, 12), background=COLORS["primary"], foreground=COLORS["white"], anchor="w", borderwidth=0)

    def build_shell(self):
        root = ttk.Frame(self, style="Root.TFrame")
        root.pack(fill="both", expand=True)
        self.rail = ttk.Frame(root, style="Rail.TFrame")
        self.rail.pack(side="left", fill="y")
        self.main = ttk.Frame(root, style="Page.TFrame")
        self.main.pack(side="left", fill="both", expand=True)
        self.render_rail()
        ttk.Label(self.main, text="Review Workspace", style="Title.TLabel").pack(anchor="w", padx=28, pady=(28, 10))
        card = ttk.Frame(self.main, style="Card.TFrame", padding=22)
        card.pack(fill="x", padx=28, pady=(0, 28))
        ttk.Label(card, text="Question", style="Card.TLabel", font=("Segoe UI Semibold", 14)).pack(anchor="w")
        self.question = ttk.Entry(card)
        self.question.insert(0, "What should stay intact when the layout changes?")
        self.question.pack(fill="x", pady=(6, 14))
        ttk.Label(card, text="Answer", style="Card.TLabel", font=("Segoe UI Semibold", 14)).pack(anchor="w")
        self.answer = ttk.Entry(card)
        self.answer.insert(0, "The current page and typed work.")
        self.answer.pack(fill="x", pady=(6, 14))
        ttk.Button(card, text="Borderless Focus", command=self.toggle_focus).pack(anchor="w")

    def render_rail(self):
        for child in self.rail.winfo_children():
            child.destroy()
        self.rail.configure(width=78 if self.rail_collapsed else 220)
        self.rail.pack_propagate(False)
        ttk.Label(self.rail, text="M" if self.rail_collapsed else "MemoryPal", background=COLORS["rail"], foreground=COLORS["white"], font=("Segoe UI Semibold", 18)).pack(anchor="w", padx=18, pady=(24, 12))
        ttk.Button(self.rail, text=">" if self.rail_collapsed else "< Collapse", command=self.toggle_rail).pack(fill="x", padx=14, pady=(0, 12))
        for label in ("Dashboard", "Review", "Puzzles", "Stats"):
            text = label[:1] if self.rail_collapsed else label
            style = "ActiveNav.TButton" if label == "Review" else "Nav.TButton"
            ttk.Button(self.rail, text=text, style=style).pack(fill="x", padx=14, pady=4)
        ttk.Button(self.rail, text="S" if self.rail_collapsed else "Settings", style="Nav.TButton").pack(side="bottom", fill="x", padx=14, pady=18)

    def toggle_rail(self):
        self.rail_collapsed = not self.rail_collapsed
        self.render_rail()

    def toggle_focus(self):
        self.is_focus = not self.is_focus
        self.overrideredirect(self.is_focus)

    def toggle_fullscreen(self):
        self.is_fullscreen = not self.is_fullscreen
        self.attributes("-fullscreen", self.is_fullscreen)

    def exit_modes(self):
        if self.is_fullscreen:
            self.toggle_fullscreen()
        elif self.is_focus:
            self.toggle_focus()


if __name__ == "__main__":
    MemoryPalDemo().mainloop()
