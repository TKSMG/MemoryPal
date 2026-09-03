"""
MemoryPal v53 beta - element fade and logo fix.

This milestone records the change from whole-window opacity fades to
same-color overlay reveals over the part of the interface that changed.
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
    "white": "#ffffff",
}


class MemoryPalDemo(tk.Tk):
    def __init__(self):
        super().__init__()
        self.withdraw()
        self.title("MemoryPal v53 - Element Fade")
        self.geometry("920x580")
        self.minsize(740, 480)
        self.page = "Capture"
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
        self.startup_fade()

    def apply_styles(self):
        self.style.configure("Root.TFrame", background=COLORS["bg"])
        self.style.configure("Rail.TFrame", background=COLORS["rail"])
        self.style.configure("Page.TFrame", background=COLORS["bg"])
        self.style.configure("Card.TFrame", background=COLORS["surface"])
        self.style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["ink"], font=("Segoe UI", 11))
        self.style.configure("Card.TLabel", background=COLORS["surface"], foreground=COLORS["ink"], font=("Segoe UI", 11))
        self.style.configure("Muted.TLabel", background=COLORS["surface"], foreground=COLORS["muted"], font=("Segoe UI", 10))
        self.style.configure("TButton", padding=(14, 10), background=COLORS["surface_soft"], foreground=COLORS["ink"], borderwidth=0)

    def startup_fade(self, step=0):
        steps = (0.0, 0.2, 0.45, 0.7, 0.88, 1.0)
        try:
            self.attributes("-alpha", steps[min(step, len(steps) - 1)])
        except tk.TclError:
            return
        if step < len(steps) - 1:
            self.after(18, lambda: self.startup_fade(step + 1))

    def build_shell(self):
        root = ttk.Frame(self, style="Root.TFrame")
        root.pack(fill="both", expand=True)
        rail = ttk.Frame(root, width=220, style="Rail.TFrame")
        rail.pack(side="left", fill="y")
        rail.pack_propagate(False)
        self.draw_logo(rail)
        for label in ("Capture", "Review", "Settings"):
            ttk.Button(rail, text=label, command=lambda name=label: self.show_page(name)).pack(fill="x", padx=16, pady=5)
        self.main = ttk.Frame(root, style="Page.TFrame")
        self.main.pack(side="left", fill="both", expand=True)
        self.title_label = ttk.Label(self.main, text="", font=("Segoe UI Semibold", 24), style="TLabel")
        self.title_label.pack(anchor="w", padx=28, pady=(28, 10))
        self.content = ttk.Frame(self.main, style="Page.TFrame")
        self.content.pack(fill="both", expand=True, padx=28, pady=(0, 28))
        self.show_page(self.page, transition=False)

    def draw_logo(self, parent):
        logo = tk.Canvas(parent, width=54, height=54, bg=COLORS["rail"], highlightthickness=0)
        logo.pack(anchor="center", pady=(24, 14))
        logo.create_rectangle(8, 8, 46, 46, fill=COLORS["primary"], outline="")
        logo.create_line(17, 39, 17, 17, 27, 33, 39, 17, 39, 39, fill=COLORS["white"], width=4, capstyle="round", joinstyle="round")

    def cover_content(self):
        cover = tk.Toplevel(self)
        cover.withdraw()
        cover.overrideredirect(True)
        cover.configure(bg=COLORS["bg"])
        cover.geometry(f"{self.content.winfo_width()}x{self.content.winfo_height()}+{self.content.winfo_rootx()}+{self.content.winfo_rooty()}")
        cover.attributes("-alpha", 1.0)
        cover.deiconify()
        cover.lift(self)
        cover.update()
        return cover

    def fade_cover(self, cover, step=0):
        steps = (1.0, 0.82, 0.62, 0.40, 0.20, 0.0)
        try:
            cover.attributes("-alpha", steps[min(step, len(steps) - 1)])
        except tk.TclError:
            return
        if step < len(steps) - 1:
            self.after(18, lambda: self.fade_cover(cover, step + 1))
        else:
            cover.destroy()

    def show_page(self, page, transition=True):
        cover = self.cover_content() if transition and self.content.winfo_viewable() else None
        self.page = page
        self.title_label.configure(text=page)
        for child in self.content.winfo_children():
            child.destroy()
        card = ttk.Frame(self.content, style="Card.TFrame", padding=24)
        card.pack(fill="x")
        ttk.Label(card, text="The shell stays solid while this card fades into view.", style="Muted.TLabel", wraplength=520).pack(anchor="w")
        if cover:
            self.fade_cover(cover)


if __name__ == "__main__":
    MemoryPalDemo().mainloop()
