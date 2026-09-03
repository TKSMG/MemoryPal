"""
MemoryPal v52 beta - capture scroll, resize release, and fade tuning.

This standalone milestone records the pass that made wide Capture layouts
reachable, delayed custom resizing until mouse release, and made fades visible
after the cover is removed.
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


class HorizontalScrollFrame(ttk.Frame):
    def __init__(self, parent, min_width=1100):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, bg=COLORS["bg"], highlightthickness=0)
        self.inner = ttk.Frame(self.canvas, style="Page.TFrame")
        self.window_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        ybar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        xbar = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        ybar.grid(row=0, column=1, sticky="ns")
        xbar.grid(row=1, column=0, sticky="ew")
        self.inner.bind("<Configure>", lambda _event: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda event: self.canvas.itemconfigure(self.window_id, width=max(event.width, min_width)))


class MemoryPalDemo(tk.Tk):
    def __init__(self):
        super().__init__()
        self.withdraw()
        self.title("MemoryPal v52 - Capture Scroll")
        self.geometry("980x620")
        self.minsize(740, 480)
        self.resize_start = None
        self.pending_geometry = None
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
        self.style.configure("Page.TFrame", background=COLORS["bg"])
        self.style.configure("Card.TFrame", background=COLORS["surface"])
        self.style.configure("AltCard.TFrame", background=COLORS["alt"])
        self.style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["ink"], font=("Segoe UI", 11))
        self.style.configure("Card.TLabel", background=COLORS["surface"], foreground=COLORS["ink"], font=("Segoe UI", 11))
        self.style.configure("Alt.TLabel", background=COLORS["alt"], foreground=COLORS["ink"], font=("Segoe UI", 11))
        self.style.configure("Muted.TLabel", background=COLORS["surface"], foreground=COLORS["muted"], font=("Segoe UI", 10))
        self.style.configure("TButton", padding=(14, 10), background=COLORS["surface_soft"], foreground=COLORS["ink"], borderwidth=0)

    def fade_window(self, start=0.90, step=0):
        if step == 0 and self.fade_job:
            try:
                self.after_cancel(self.fade_job)
            except tk.TclError:
                pass
        steps = (start, 0.91, 0.94, 0.965, 0.985, 1.0) if start < 0.9 else (start, 0.955, 0.975, 0.99, 1.0)
        try:
            self.attributes("-alpha", steps[min(step, len(steps) - 1)])
        except tk.TclError:
            return
        if step < len(steps) - 1:
            self.fade_job = self.after(22, lambda: self.fade_window(start, step + 1))
        else:
            self.fade_job = None

    def build_shell(self):
        root = ttk.Frame(self, style="Root.TFrame")
        root.pack(fill="both", expand=True)
        title = ttk.Label(root, text="Capture", font=("Segoe UI Semibold", 24), style="TLabel")
        title.pack(anchor="w", padx=28, pady=(26, 8))
        page = HorizontalScrollFrame(root, min_width=1120)
        page.pack(fill="both", expand=True, padx=28, pady=(0, 28))
        form = ttk.Frame(page.inner, style="Card.TFrame", padding=22)
        form.pack(side="left", fill="both", expand=True, padx=(0, 14))
        side = ttk.Frame(page.inner, style="AltCard.TFrame", padding=22)
        side.pack(side="left", fill="both", expand=True)
        ttk.Label(form, text="Study set builder", style="Card.TLabel", font=("Segoe UI Semibold", 16)).pack(anchor="w")
        ttk.Entry(form).pack(fill="x", pady=(10, 12))
        tk.Text(form, height=8, bg=COLORS["surface_soft"], fg=COLORS["ink"], relief="flat").pack(fill="both", expand=True)
        ttk.Button(form, text="Save Capture", command=lambda: self.fade_window(0.90)).pack(fill="x", pady=(12, 0))
        ttk.Label(side, text="Captured material", style="Alt.TLabel", font=("Segoe UI Semibold", 16)).pack(anchor="w")
        ttk.Label(side, text="This right-side panel stays reachable with horizontal scrolling instead of disappearing off the edge.", style="Alt.TLabel", wraplength=420).pack(anchor="w", pady=(10, 0))
        grip = tk.Frame(self, bg=COLORS["muted"], cursor="size_nw_se")
        grip.place(relx=1, rely=1, anchor="se", width=18, height=18)
        grip.bind("<ButtonPress-1>", self.start_resize)
        grip.bind("<B1-Motion>", self.preview_resize)
        grip.bind("<ButtonRelease-1>", self.apply_resize)

    def start_resize(self, event):
        self.resize_start = (event.x_root, event.y_root, self.winfo_width(), self.winfo_height(), self.winfo_x(), self.winfo_y())

    def preview_resize(self, event):
        if not self.resize_start:
            return
        start_x, start_y, width, height, x, y = self.resize_start
        self.pending_geometry = f"{max(740, width + event.x_root - start_x)}x{max(480, height + event.y_root - start_y)}+{x}+{y}"

    def apply_resize(self, _event):
        if self.pending_geometry:
            self.geometry(self.pending_geometry)
            self.fade_window(0.92)
        self.resize_start = None
        self.pending_geometry = None


if __name__ == "__main__":
    MemoryPalDemo().mainloop()
