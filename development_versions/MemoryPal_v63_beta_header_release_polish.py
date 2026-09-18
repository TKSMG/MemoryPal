"""
MemoryPal v63 beta - header release polish.

This milestone records the pass where the busy header row was spread out for
testing. Status chips stay on the left, app actions move to the right, and the
active profile becomes a compact numbered avatar.
"""

import tkinter as tk


APP_NAME = "MemoryPal"
BG = "#111827"
SURFACE = "#192338"
SURFACE_SOFT = "#23304a"
RAIL = "#0b1020"
PRIMARY = "#65afff"
WARM = "#3b2f1f"
GREEN = "#37d67a"
INK = "#edf2fb"
MUTED = "#aeb8cb"
LINE = "#33445f"


class MemoryPalV63(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} v63")
        self.geometry("1080x680")
        self.minsize(780, 500)
        self.configure(bg=BG)

        self.rail = tk.Frame(self, bg=RAIL, width=250)
        self.rail.pack(side="left", fill="y")
        self.main = tk.Frame(self, bg=BG)
        self.main.pack(side="left", fill="both", expand=True)

        tk.Label(self.rail, text=APP_NAME, bg=RAIL, fg=INK, font=("Segoe UI Semibold", 22)).pack(anchor="w", padx=24, pady=(32, 18))
        for label in ("Dashboard", "Capture", "Review", "Settings"):
            tk.Button(self.rail, text=label, bg=RAIL, fg=MUTED, activebackground=SURFACE_SOFT, activeforeground=INK, relief="flat", anchor="w", padx=18, pady=12).pack(fill="x", padx=18, pady=4)

        header = tk.Frame(self.main, bg=SURFACE, padx=24, pady=20, highlightthickness=1, highlightbackground=LINE)
        header.pack(fill="x", padx=36, pady=(32, 18))
        header.columnconfigure(0, weight=1)

        title = tk.Frame(header, bg=SURFACE)
        title.grid(row=0, column=0, sticky="ew")
        tk.Label(title, text="Today", bg=SURFACE, fg=MUTED, font=("Segoe UI", 11)).pack(anchor="w")
        tk.Label(title, text="Dashboard", bg=SURFACE, fg=INK, font=("Segoe UI Semibold", 28)).pack(anchor="w")
        self.profile_avatar(header, 1).grid(row=0, column=1, sticky="ne", padx=(18, 0))

        actions = tk.Frame(header, bg=SURFACE)
        actions.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(18, 0))
        actions.columnconfigure(0, weight=1)
        left = tk.Frame(actions, bg=SURFACE)
        left.grid(row=0, column=0, sticky="w")
        right = tk.Frame(actions, bg=SURFACE)
        right.grid(row=0, column=1, sticky="e")
        self.chip(left, "2 day streak", WARM, "#ffd48a")
        self.chip(left, "7/15 today", "#203a31", GREEN)
        self.chip(left, "Local save", SURFACE_SOFT, PRIMARY)
        self.action(right, "Light")
        self.action(right, "Fullscreen")
        self.action(right, "Backup")

        card = tk.Frame(self.main, bg=SURFACE, padx=28, pady=24, highlightthickness=1, highlightbackground=LINE)
        card.pack(fill="both", expand=True, padx=36, pady=(0, 36))
        tk.Label(card, text="Release-polish snapshot", bg=SURFACE, fg=INK, font=("Segoe UI Semibold", 20)).pack(anchor="w")
        tk.Label(
            card,
            text="The top bar has breathing room, the profile control is compact, and fullscreen guidance lives in hints instead of crowding the toolbar.",
            bg=SURFACE,
            fg=MUTED,
            font=("Segoe UI", 12),
            wraplength=680,
            justify="left",
        ).pack(anchor="w", pady=(8, 0))

    def profile_avatar(self, parent, number):
        size = 52
        badge = 22
        canvas = tk.Canvas(parent, width=size, height=size, bg=SURFACE, highlightthickness=0)
        canvas.create_oval(2, 2, size - 2, size - 2, fill=SURFACE_SOFT, outline=LINE, width=2)
        canvas.create_oval(19, 12, 33, 27, fill="", outline=MUTED, width=2)
        canvas.create_arc(12, 25, 40, 50, start=20, extent=140, style="arc", outline=MUTED, width=2)
        x = size - badge - 1
        y = size - badge - 1
        canvas.create_oval(x, y, x + badge, y + badge, fill=PRIMARY, outline=SURFACE, width=2)
        canvas.create_text(x + badge / 2, y + badge / 2, text=str(number), fill="white", font=("Segoe UI Semibold", 9))
        return canvas

    def chip(self, parent, text, bg, fg):
        tk.Label(parent, text=text, bg=bg, fg=fg, padx=12, pady=7, font=("Segoe UI Semibold", 10)).pack(side="left", padx=(0, 12))

    def action(self, parent, text):
        tk.Button(parent, text=text, bg=SURFACE_SOFT, fg=INK, activebackground="#2a3a59", activeforeground=PRIMARY, relief="flat", padx=18, pady=10).pack(side="left", padx=(0, 10))


if __name__ == "__main__":
    MemoryPalV63().mainloop()
