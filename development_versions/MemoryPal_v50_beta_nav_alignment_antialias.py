"""
MemoryPal v50 beta - navigation alignment and softer edges.

This small standalone milestone records the polish pass that centered the
expanded rail toggle and introduced optional antialiased rounded drawing.
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
        self.title("MemoryPal v50 - Softer Edges")
        self.geometry("900x560")
        self.minsize(720, 460)
        self.rail_collapsed = False
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self.configure(bg=COLORS["bg"])
        self.apply_styles()
        self.build_shell()

    def apply_styles(self):
        self.style.configure("Root.TFrame", background=COLORS["bg"])
        self.style.configure("Rail.TFrame", background=COLORS["rail"])
        self.style.configure("Page.TFrame", background=COLORS["bg"])
        self.style.configure("Card.TFrame", background=COLORS["surface"])
        self.style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["ink"], font=("Segoe UI", 11))
        self.style.configure("Card.TLabel", background=COLORS["surface"], foreground=COLORS["ink"], font=("Segoe UI", 11))
        self.style.configure("Muted.TLabel", background=COLORS["surface"], foreground=COLORS["muted"], font=("Segoe UI", 10))
        self.style.configure("TButton", padding=(14, 10), background=COLORS["surface_soft"], foreground=COLORS["ink"], borderwidth=0)

    def antialiased_round_rect(self, canvas, width, height, fill, radius=None):
        try:
            from PIL import Image, ImageDraw, ImageTk
        except ImportError:
            return False
        scale = 3
        image = Image.new("RGBA", (width * scale, height * scale), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((0, 0, width * scale - 1, height * scale - 1), radius=(radius or height // 2) * scale, fill=fill)
        resampling = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
        photo = ImageTk.PhotoImage(image.resize((width, height), resampling))
        canvas.create_image(0, 0, anchor="nw", image=photo)
        canvas._memorypal_image = photo
        return True

    def build_shell(self):
        root = ttk.Frame(self, style="Root.TFrame")
        root.pack(fill="both", expand=True)
        self.rail = ttk.Frame(root, width=250, style="Rail.TFrame")
        self.rail.pack(side="left", fill="y")
        self.rail.pack_propagate(False)
        self.main = ttk.Frame(root, style="Page.TFrame")
        self.main.pack(side="left", fill="both", expand=True)
        self.render_rail()
        ttk.Label(self.main, text="Navigation polish", font=("Segoe UI Semibold", 24), style="TLabel").pack(anchor="w", padx=28, pady=(28, 10))
        card = ttk.Frame(self.main, style="Card.TFrame", padding=24)
        card.pack(fill="x", padx=28)
        ttk.Label(card, text="The expanded rail toggle is centered, and rounded controls use smoother drawing when Pillow is installed.", style="Muted.TLabel", wraplength=520).pack(anchor="w")

    def render_rail(self):
        for child in self.rail.winfo_children():
            child.destroy()
        self.rail.configure(width=78 if self.rail_collapsed else 250)
        ttk.Label(self.rail, text="M" if self.rail_collapsed else "MemoryPal", background=COLORS["rail"], foreground=COLORS["white"], font=("Segoe UI Semibold", 18)).pack(anchor="center", pady=(24, 12))
        width = 46 if self.rail_collapsed else 156
        canvas = tk.Canvas(self.rail, width=width, height=38, bg=COLORS["rail"], highlightthickness=0, cursor="hand2")
        canvas.pack(anchor="center", pady=(0, 14))
        self.draw_toggle(canvas, width, 38)
        canvas.bind("<Button-1>", lambda _event: self.toggle_rail())
        for label in ("Dashboard", "Review", "Puzzles", "Stats"):
            text = label[:1] if self.rail_collapsed else label
            ttk.Button(self.rail, text=text).pack(fill="x", padx=14, pady=4)

    def draw_toggle(self, canvas, width, height):
        canvas.delete("all")
        if not self.antialiased_round_rect(canvas, width, height, COLORS["rail_hover"]):
            radius = height // 2
            canvas.create_rectangle(radius, 0, width - radius, height, fill=COLORS["rail_hover"], outline="")
            canvas.create_oval(0, 0, height, height, fill=COLORS["rail_hover"], outline="")
            canvas.create_oval(width - height, 0, width, height, fill=COLORS["rail_hover"], outline="")
        canvas.create_text(width // 2, height // 2, text=">" if self.rail_collapsed else "<  Collapse", fill=COLORS["white"], font=("Segoe UI Semibold", 10))

    def toggle_rail(self):
        self.rail_collapsed = not self.rail_collapsed
        self.render_rail()


if __name__ == "__main__":
    MemoryPalDemo().mainloop()
