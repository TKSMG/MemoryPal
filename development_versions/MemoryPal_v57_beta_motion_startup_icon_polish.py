"""
MemoryPal v57 beta - motion, startup, and icon polish.

This milestone records the pass where the desktop app stopped carrying old
duplicated support code in the launcher, kept page fades inside the content
area, animated the navigation rail width, and refreshed the generated icon.
"""

import importlib
import tkinter as tk


BG = "#101827"
SURFACE = "#192338"
RAIL = "#0b1020"
PRIMARY = "#50d5ff"
VIOLET = "#6a3dce"
INK = "#edf2fb"
MUTED = "#aeb8cb"


def optional_import(name):
    """Import an optional media package only when the feature is used."""
    try:
        return importlib.import_module(name)
    except ImportError:
        return None


class MotionDemo(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MemoryPal v57 motion demo")
        self.geometry("900x560")
        self.configure(bg=BG)
        self.rail_collapsed = False
        self.rail_width = 246
        self.page = 0

        self.rail = tk.Frame(self, bg=RAIL, width=self.rail_width)
        self.rail.pack(side="left", fill="y")
        self.rail.pack_propagate(False)

        self.main = tk.Frame(self, bg=BG)
        self.main.pack(side="left", fill="both", expand=True)

        self.render_rail()
        self.show_page(first=True)

    def render_rail(self):
        for child in self.rail.winfo_children():
            child.destroy()
        logo = tk.Canvas(self.rail, width=60, height=60, bg=RAIL, highlightthickness=0)
        logo.pack(pady=(28, 18))
        logo.create_rectangle(6, 6, 54, 54, fill=PRIMARY, outline="", width=0)
        logo.create_line(17, 43, 17, 18, 30, 38, 43, 18, 43, 43, fill="white", width=6, capstyle="round", joinstyle="round")
        for x, y in ((17, 18), (30, 38), (43, 18)):
            logo.create_oval(x - 4, y - 4, x + 4, y + 4, fill="white", outline="")

        text = ">" if self.rail_collapsed else "<  Collapse"
        tk.Button(self.rail, text=text, command=self.toggle_rail, bg=PRIMARY, fg=RAIL, relief="flat", padx=14, pady=10).pack(pady=(0, 18))
        for label in ("Today", "Gym", "Review", "Settings"):
            value = label[:1] if self.rail_collapsed else label
            tk.Button(self.rail, text=value, command=self.next_page, bg=RAIL, fg=INK, relief="flat", anchor="w", padx=18, pady=12).pack(fill="x", padx=14, pady=4)

    def ease_out(self, step, steps):
        t = min(1, max(0, step / steps))
        return 1 - (1 - t) ** 3

    def toggle_rail(self):
        start = 76 if self.rail_collapsed else 246
        end = 246 if self.rail_collapsed else 76
        self.rail_collapsed = not self.rail_collapsed
        self.animate_rail(start, end)

    def animate_rail(self, start, end, step=0, steps=12):
        width = round(start + (end - start) * self.ease_out(step, steps))
        self.rail.configure(width=width)
        if step < steps:
            self.after(14, lambda: self.animate_rail(start, end, step + 1, steps))
        else:
            self.render_rail()

    def next_page(self):
        self.page += 1
        self.show_page()

    def show_page(self, first=False):
        for child in self.main.winfo_children():
            child.destroy()
        card = tk.Frame(self.main, bg=SURFACE, padx=32, pady=28)
        card.pack(fill="both", expand=True, padx=36, pady=36)
        tk.Label(card, text=f"Practice page {self.page + 1}", bg=SURFACE, fg=INK, font=("Segoe UI Semibold", 26)).pack(anchor="w")
        tk.Label(card, text="The background stays solid while only page content is covered during a transition.", bg=SURFACE, fg=MUTED, font=("Segoe UI", 13)).pack(anchor="w", pady=(10, 24))
        tk.Button(card, text="Use optional audio", command=lambda: print(optional_import("sounddevice")), bg=VIOLET, fg="white", relief="flat", padx=18, pady=12).pack(anchor="w")
        if not first:
            cover = tk.Canvas(self.main, bg=BG, highlightthickness=0)
            cover.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.fade_cover(cover)

    def fade_cover(self, cover, step=0):
        stipples = ("", "gray75", "gray50", "gray25", "gray12")
        cover.delete("all")
        cover.create_rectangle(0, 0, max(1, cover.winfo_width()), max(1, cover.winfo_height()), fill=BG, outline="", stipple=stipples[min(step, len(stipples) - 1)])
        if step < len(stipples) - 1:
            self.after(22, lambda: self.fade_cover(cover, step + 1))
        else:
            cover.destroy()


if __name__ == "__main__":
    MotionDemo().mainloop()
