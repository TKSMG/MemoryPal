"""
MemoryPal v64 beta - low-end readiness.

This milestone records the pass focused on slower Windows PCs and future Mac
testing. The live app keeps the richer interface, while this standalone version
shows the lighter chrome pattern: cached asset lookup, one taskbar/chrome
refresh, and page changes that cover only the content panel.
"""

import sys
import time
import tkinter as tk
from pathlib import Path


APP_NAME = "MemoryPal"
BG = "#111827"
SURFACE = "#192338"
SURFACE_SOFT = "#22304a"
RAIL = "#0b1020"
PRIMARY = "#65afff"
INK = "#edf2fb"
MUTED = "#aeb8cb"
LINE = "#33445f"


class MemoryPalV64(tk.Tk):
    def __init__(self):
        start = time.perf_counter()
        super().__init__()
        self.withdraw()
        self.title(f"{APP_NAME} v64")
        self.geometry("1100x700")
        self.minsize(860, 560)
        self.configure(bg=BG)

        self.logo_path = self.find_asset("assets", "memorypal-logo-preview.png")
        self.logo_cache = {}
        self.chrome_refresh_active = False
        self.taskbar_ready = False

        self.shell()
        self.refresh_chrome()
        self.deiconify()
        self.after(80, self.refresh_chrome)
        self.show_page("Dashboard", transition=False)
        elapsed = (time.perf_counter() - start) * 1000
        self.status.configure(text=f"Ready in {elapsed:.0f} ms")

    def find_asset(self, *parts):
        relative = Path(*parts)
        candidates = [Path(__file__).resolve().parents[1] / relative, Path(sys.executable).resolve().parent / relative]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def refresh_chrome(self):
        if self.chrome_refresh_active:
            return
        self.chrome_refresh_active = True
        try:
            self.taskbar_ready = True
        finally:
            self.chrome_refresh_active = False

    def shell(self):
        rail = tk.Frame(self, bg=RAIL, width=260)
        rail.pack(side="left", fill="y")
        rail.pack_propagate(False)

        brand = tk.Frame(rail, bg=RAIL)
        brand.pack(fill="x", padx=24, pady=(28, 20))
        logo = tk.Canvas(brand, width=48, height=48, bg=RAIL, highlightthickness=0)
        logo.pack(side="left", padx=(0, 12))
        self.draw_logo(logo, 48)
        tk.Label(brand, text=APP_NAME, bg=RAIL, fg=INK, font=("Segoe UI Semibold", 20)).pack(side="left")

        for name in ("Dashboard", "Capture", "Review", "Settings"):
            tk.Button(
                rail,
                text=name,
                bg=RAIL,
                fg=MUTED,
                activebackground=SURFACE_SOFT,
                activeforeground=INK,
                relief="flat",
                anchor="w",
                padx=18,
                pady=12,
                command=lambda page=name: self.show_page(page),
            ).pack(fill="x", padx=20, pady=5)

        self.main = tk.Frame(self, bg=BG)
        self.main.pack(side="left", fill="both", expand=True)
        header = tk.Frame(self.main, bg=SURFACE, padx=24, pady=18, highlightthickness=1, highlightbackground=LINE)
        header.pack(fill="x", padx=36, pady=(30, 18))
        header.columnconfigure(0, weight=1)
        self.title_label = tk.Label(header, text="Dashboard", bg=SURFACE, fg=INK, font=("Segoe UI Semibold", 26))
        self.title_label.grid(row=0, column=0, sticky="w")
        self.status = tk.Label(header, text="Ready", bg=SURFACE, fg=PRIMARY, font=("Segoe UI Semibold", 10))
        self.status.grid(row=0, column=1, sticky="e")

        self.content = tk.Frame(self.main, bg=BG)
        self.content.pack(fill="both", expand=True, padx=36, pady=(0, 36))

    def draw_logo(self, canvas, size):
        if self.logo_path:
            try:
                photo = self.logo_cache.get(size)
                if photo is None:
                    photo = tk.PhotoImage(file=str(self.logo_path))
                    factor = max(1, max((photo.width() + size - 1) // size, (photo.height() + size - 1) // size))
                    if factor > 1:
                        photo = photo.subsample(factor, factor)
                    self.logo_cache[size] = photo
                canvas.create_image(size // 2, size // 2, image=photo)
                canvas.image = photo
                return
            except tk.TclError:
                pass
        canvas.create_oval(4, 4, size - 4, size - 4, fill=PRIMARY, outline="")
        canvas.create_text(size // 2, size // 2, text="M", fill="white", font=("Segoe UI Semibold", 20))

    def show_page(self, name, transition=True):
        cover = None
        if transition:
            cover = tk.Frame(self.main, bg=BG)
            cover.place(relx=0, rely=0, relwidth=1, relheight=1)
            cover.lift()
            cover.update_idletasks()

        self.title_label.configure(text=name)
        for child in self.content.winfo_children():
            child.destroy()
        card = tk.Frame(self.content, bg=SURFACE, padx=28, pady=24, highlightthickness=1, highlightbackground=LINE)
        card.pack(fill="both", expand=True)
        tk.Label(card, text=f"{name} stage", bg=SURFACE, fg=INK, font=("Segoe UI Semibold", 20)).pack(anchor="w")
        tk.Label(
            card,
            text="This version focuses on fewer redraws, cached graphics paths, and stable page covers for slower machines.",
            bg=SURFACE,
            fg=MUTED,
            font=("Segoe UI", 12),
            wraplength=680,
            justify="left",
        ).pack(anchor="w", pady=(8, 0))

        if cover:
            self.after(90, cover.destroy)


if __name__ == "__main__":
    MemoryPalV64().mainloop()
