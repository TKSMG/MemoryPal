"""
MemoryPal v54 beta - logo assets.

This milestone records the final connected-dot logo pass and the decision to
keep reusable icon exports in the project folder.
"""

import tkinter as tk
from tkinter import ttk


COLORS = {
    "bg": "#111827",
    "surface": "#192338",
    "surface_soft": "#22304a",
    "ink": "#edf2fb",
    "muted": "#aeb8cb",
    "primary": "#65afff",
    "violet": "#7868ff",
    "mint": "#83ffd8",
    "white": "#ffffff",
}


class LogoAssetDemo(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MemoryPal v54 - Logo Assets")
        self.geometry("780x520")
        self.minsize(620, 420)
        self.configure(bg=COLORS["bg"])
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self.style.configure("Card.TFrame", background=COLORS["surface"])
        self.style.configure("Title.TLabel", background=COLORS["surface"], foreground=COLORS["ink"], font=("Segoe UI Semibold", 20))
        self.style.configure("Body.TLabel", background=COLORS["surface"], foreground=COLORS["muted"], font=("Segoe UI", 11))
        self.build()

    def build(self):
        shell = ttk.Frame(self, style="Card.TFrame", padding=28)
        shell.pack(fill="both", expand=True, padx=28, pady=28)

        logo = tk.Canvas(shell, width=180, height=180, bg=COLORS["surface"], highlightthickness=0)
        logo.pack(pady=(0, 20))
        self.draw_logo(logo, 180)

        ttk.Label(shell, text="MemoryPal Logo Export", style="Title.TLabel").pack()
        ttk.Label(
            shell,
            text=(
                "The latest app mark keeps the sharper M shape, brings back the "
                "connected recall dots, and exports reusable ICO, PNG, and SVG assets."
            ),
            style="Body.TLabel",
            wraplength=560,
            justify="center",
        ).pack(pady=(10, 18))

        for item in (
            "assets/memorypal.ico",
            "assets/memorypal-logo-preview.png",
            "assets/memorypal-logo.svg",
        ):
            ttk.Label(shell, text=item, style="Body.TLabel").pack(anchor="center", pady=2)

    def draw_logo(self, canvas, size):
        canvas.create_rectangle(18, 18, size - 18, size - 18, fill=COLORS["violet"], outline="")
        canvas.create_rectangle(18, 18, size - 18, size // 2, fill=COLORS["primary"], outline="")
        canvas.create_line(
            size * 0.25, size * 0.70,
            size * 0.25, size * 0.31,
            size * 0.50, size * 0.62,
            size * 0.75, size * 0.31,
            size * 0.75, size * 0.70,
            width=size * 0.12,
            fill=COLORS["white"],
            capstyle="round",
            joinstyle="round",
        )
        canvas.create_line(
            size * 0.25, size * 0.70,
            size * 0.43, size * 0.34,
            size * 0.58, size * 0.58,
            size * 0.75, size * 0.30,
            width=size * 0.04,
            fill=COLORS["mint"],
            capstyle="round",
            joinstyle="round",
        )
        for x, y in ((0.25, 0.31), (0.50, 0.62), (0.75, 0.31)):
            r = size * 0.055
            canvas.create_oval(size * x - r, size * y - r, size * x + r, size * y + r, fill=COLORS["white"], outline="")


if __name__ == "__main__":
    LogoAssetDemo().mainloop()
