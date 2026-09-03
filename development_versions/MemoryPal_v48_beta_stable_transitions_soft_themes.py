"""
MemoryPal v48 beta - stable transitions and soft themes.

This standalone milestone records the pass that removed fragile page-overlay
windows, kept Settings in one predictable place, and softened both themes.
"""

import tkinter as tk
from tkinter import ttk


DARK = {
    "bg": "#111827",
    "surface": "#192338",
    "surface_soft": "#22304a",
    "alt": "#273852",
    "ink": "#edf2fb",
    "muted": "#aeb8cb",
    "line": "#33445f",
    "primary": "#65afff",
    "rail": "#0b1020",
    "rail_hover": "#202e47",
    "white": "#ffffff",
}

LIGHT = {
    "bg": "#f6f8fc",
    "surface": "#ffffff",
    "surface_soft": "#eef3fb",
    "alt": "#e9f1fb",
    "ink": "#172033",
    "muted": "#617089",
    "line": "#d8e2ef",
    "primary": "#3f8ee6",
    "rail": "#172033",
    "rail_hover": "#22304a",
    "white": "#ffffff",
}


class MemoryPalDemo(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MemoryPal v48 - Stable Transitions")
        self.geometry("980x640")
        self.minsize(780, 520)
        self.theme = "dark"
        self.colors = dict(DARK)
        self.current_page = "Dashboard"
        self.nav_order = ["Dashboard", "Capture", "Review", "Puzzles", "Stats"]
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self.configure(bg=self.colors["bg"])
        self.apply_styles()
        self.build_shell()
        self.show_page("Dashboard", transition=False)

    def apply_styles(self):
        c = self.colors
        self.style.configure("Root.TFrame", background=c["bg"])
        self.style.configure("Rail.TFrame", background=c["rail"])
        self.style.configure("Page.TFrame", background=c["bg"])
        self.style.configure("Card.TFrame", background=c["surface"])
        self.style.configure("TLabel", background=c["bg"], foreground=c["ink"], font=("Segoe UI", 11))
        self.style.configure("Muted.TLabel", background=c["bg"], foreground=c["muted"], font=("Segoe UI", 10))
        self.style.configure("Card.TLabel", background=c["surface"], foreground=c["ink"], font=("Segoe UI", 11))
        self.style.configure("CardMuted.TLabel", background=c["surface"], foreground=c["muted"], font=("Segoe UI", 10))
        self.style.configure("Title.TLabel", background=c["bg"], foreground=c["ink"], font=("Segoe UI Semibold", 24))
        self.style.configure("TButton", padding=(14, 10), background=c["surface_soft"], foreground=c["ink"], borderwidth=0)
        self.style.map("TButton", background=[("active", c["alt"])], foreground=[("active", c["primary"])])
        self.style.configure("Nav.TButton", padding=(16, 12), background=c["rail"], foreground="#d7def0", anchor="w", borderwidth=0)
        self.style.map("Nav.TButton", background=[("active", c["rail_hover"])])
        self.style.configure("ActiveNav.TButton", padding=(16, 12), background=c["primary"], foreground=c["white"], anchor="w", borderwidth=0)

    def build_shell(self, cover=None):
        for child in self.winfo_children():
            if child is cover:
                continue
            child.destroy()
        self.root = ttk.Frame(self, style="Root.TFrame")
        self.root.pack(fill="both", expand=True)
        self.rail = ttk.Frame(self.root, width=220, style="Rail.TFrame")
        self.rail.pack(side="left", fill="y")
        self.rail.pack_propagate(False)
        ttk.Label(self.rail, text="MemoryPal", background=self.colors["rail"], foreground=self.colors["white"], font=("Segoe UI Semibold", 20)).pack(anchor="w", padx=18, pady=(24, 8))
        self.nav_buttons = {}
        for name in self.nav_order:
            button = ttk.Button(self.rail, text=name, style="Nav.TButton", command=lambda page=name: self.show_page(page))
            button.pack(fill="x", padx=14, pady=4)
            self.nav_buttons[name] = button
        settings = ttk.Button(self.rail, text="Settings", style="Nav.TButton", command=lambda: self.show_page("Settings"))
        settings.pack(side="bottom", fill="x", padx=14, pady=18)
        self.nav_buttons["Settings"] = settings
        self.main = ttk.Frame(self.root, style="Page.TFrame")
        self.main.pack(side="left", fill="both", expand=True)
        self.title_label = ttk.Label(self.main, text="", style="Title.TLabel")
        self.title_label.pack(anchor="w", padx=28, pady=(28, 10))
        self.content = ttk.Frame(self.main, style="Page.TFrame")
        self.content.pack(fill="both", expand=True, padx=28, pady=(0, 28))

    def cover(self, parent=None):
        parent = parent or self.content
        cover = tk.Frame(parent, bg=self.colors["bg"])
        cover.place(relx=0, rely=0, relwidth=1, relheight=1)
        cover.tk.call("raise", cover._w)
        cover.update()
        return cover

    def reveal(self, cover, step=0):
        if step < 4 and cover.winfo_exists():
            cover.tk.call("raise", cover._w)
            self.after(22, lambda: self.reveal(cover, step + 1))
        elif cover.winfo_exists():
            cover.destroy()

    def show_page(self, page, transition=True):
        cover = self.cover() if transition and self.content.winfo_viewable() else None
        self.current_page = page
        self.title_label.configure(text=page)
        for name, button in self.nav_buttons.items():
            button.configure(style="ActiveNav.TButton" if name == page else "Nav.TButton")
        for child in self.content.winfo_children():
            if child is not cover:
                child.destroy()
        self.after_idle(lambda: self.finish_page(page, cover))

    def finish_page(self, page, cover):
        card = ttk.Frame(self.content, style="Card.TFrame", padding=22)
        card.pack(fill="x")
        if cover:
            cover.tk.call("raise", cover._w)
        if page == "Settings":
            ttk.Label(card, text="Personal settings", style="Card.TLabel", font=("Segoe UI Semibold", 16)).pack(anchor="w")
            ttk.Label(card, text="Theme switching and page order belong together here, not duplicated in the header.", style="CardMuted.TLabel", wraplength=620).pack(anchor="w", pady=(6, 16))
            ttk.Button(card, text="Switch theme", command=self.toggle_theme).pack(anchor="w")
        else:
            ttk.Label(card, text=f"{page} workspace", style="Card.TLabel", font=("Segoe UI Semibold", 16)).pack(anchor="w")
            ttk.Label(card, text="The page is rebuilt behind a same-color cover so unfinished content does not flash on screen.", style="CardMuted.TLabel", wraplength=620).pack(anchor="w", pady=(6, 16))
            ttk.Button(card, text="Open Settings", command=lambda: self.show_page("Settings")).pack(anchor="w")
        if cover:
            cover.tk.call("raise", cover._w)
            self.reveal(cover)

    def toggle_theme(self):
        cover = self.cover(self)
        self.colors = dict(LIGHT if self.theme == "dark" else DARK)
        self.theme = "light" if self.theme == "dark" else "dark"
        self.configure(bg=self.colors["bg"])
        if cover.winfo_exists():
            cover.configure(bg=self.colors["bg"])
            cover.tk.call("raise", cover._w)
            cover.update()
        self.apply_styles()
        self.build_shell(cover)
        self.show_page("Settings", transition=False)
        self.reveal(cover)


if __name__ == "__main__":
    MemoryPalDemo().mainloop()
