"""
MemoryPal v59 beta - transition and launch polish.

This small milestone records the late-stage polish pass where packaged
launches stopped regenerating icon assets, page changes returned to a real
content fade, and the navigation rail stopped clipping long labels while it
collapsed.
"""

import sys
import tkinter as tk
from pathlib import Path


APP_NAME = "MemoryPal"
BG = "#111827"
SURFACE = "#192338"
RAIL = "#0b1020"
PRIMARY = "#65afff"
INK = "#edf2fb"
MUTED = "#aeb8cb"


def resource_path(*parts):
    """Resolve source, PyInstaller, or app-folder resources."""
    relative = Path(*parts)
    roots = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        roots.append(Path(meipass))
    roots.extend((Path(__file__).resolve().parent.parent, Path(sys.executable).resolve().parent))
    for root in roots:
        candidate = root / relative
        if candidate.exists():
            return candidate
    return None


class MemoryPalV59(tk.Tk):
    def __init__(self):
        super().__init__()
        self.withdraw()
        self.configure(bg=BG)
        self.geometry("980x640")
        self.minsize(760, 480)
        self.title(f"{APP_NAME} v59")
        icon = resource_path("assets", "memorypal.ico")
        if icon:
            try:
                self.iconbitmap(default=str(icon))
            except tk.TclError:
                pass
        self.collapsed = False
        self.page = "Dashboard"
        self.rail = tk.Frame(self, bg=RAIL, width=240)
        self.rail.pack(side="left", fill="y")
        self.rail.pack_propagate(False)
        self.main = tk.Frame(self, bg=BG)
        self.main.pack(side="left", fill="both", expand=True)
        self.content = tk.Frame(self.main, bg=BG)
        self.content.pack(fill="both", expand=True, padx=32, pady=32)
        self.draw_rail()
        self.show_page("Dashboard", transition=False)
        self.after(80, self.deiconify)

    def draw_rail(self, width=None):
        for child in self.rail.winfo_children():
            child.destroy()
        if width:
            self.rail.configure(width=width)
        label = "M" if self.collapsed else "MemoryPal"
        tk.Label(self.rail, text=label, bg=RAIL, fg=INK, font=("Segoe UI Semibold", 20)).pack(anchor="w", padx=20, pady=(24, 18))
        toggle = ">" if self.collapsed else "<  Collapse"
        tk.Button(self.rail, text=toggle, command=self.toggle_rail, relief="flat", bg=PRIMARY, fg="white").pack(fill="x", padx=16, pady=(0, 16))
        for page in ("Dashboard", "Review", "Capture", "Settings"):
            text = page[:1] if self.collapsed else page
            tk.Button(self.rail, text=text, command=lambda value=page: self.show_page(value), relief="flat", bg=RAIL, fg=MUTED).pack(fill="x", padx=16, pady=5)

    def toggle_rail(self):
        start = 72 if self.collapsed else 240
        end = 240 if self.collapsed else 72
        if not self.collapsed:
            self.collapsed = True
            self.draw_rail(start)
        self.animate_rail(start, end)

    def animate_rail(self, start, end, step=0, steps=12):
        progress = step / steps
        ease = 1 - (1 - progress) ** 3
        self.rail.configure(width=round(start + (end - start) * ease))
        if step < steps:
            self.after(13, lambda: self.animate_rail(start, end, step + 1, steps))
            return
        self.collapsed = end == 72
        self.draw_rail(end)

    def show_page(self, page, transition=True):
        cover = self.make_content_cover() if transition else None
        for child in self.content.winfo_children():
            child.destroy()
        card = tk.Frame(self.content, bg=SURFACE, padx=26, pady=24)
        card.pack(fill="both", expand=True)
        tk.Label(card, text=page, bg=SURFACE, fg=INK, font=("Segoe UI Semibold", 28)).pack(anchor="w")
        tk.Label(card, text="Content changes fade in; resize and rail changes keep the page alive.", bg=SURFACE, fg=MUTED, font=("Segoe UI", 13)).pack(anchor="w", pady=(10, 0))
        if cover:
            self.after_idle(lambda: self.fade_cover(cover))

    def make_content_cover(self):
        self.update_idletasks()
        if not self.content.winfo_viewable():
            return None
        cover = tk.Toplevel(self)
        cover.overrideredirect(True)
        cover.configure(bg=BG)
        cover.geometry(f"{self.content.winfo_width()}x{self.content.winfo_height()}+{self.content.winfo_rootx()}+{self.content.winfo_rooty()}")
        cover.attributes("-alpha", 1.0)
        cover.lift(self)
        return cover

    def fade_cover(self, cover, step=0):
        if not cover or not cover.winfo_exists():
            return
        alpha = (1.0, 0.90, 0.72, 0.50, 0.30, 0.14, 0.0)[min(step, 6)]
        cover.attributes("-alpha", alpha)
        cover.lift(self)
        if step < 6:
            self.after(24, lambda: self.fade_cover(cover, step + 1))
        else:
            cover.destroy()


if __name__ == "__main__":
    MemoryPalV59().mainloop()
