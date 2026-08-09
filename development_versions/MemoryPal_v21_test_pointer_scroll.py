import sys
import ctypes
import tkinter as tk
from tkinter import ttk


VERSION = "v21 Test"
TITLE = "Pointer-aware page scrolling"
ACCENT = "#007aff"
FEATURES = [
    "Mouse wheel scrolling works anywhere inside the active page section.",
    "Users no longer need to hover over the scrollbar itself.",
    "Nested scroll areas only scroll the section under the pointer.",
]


def enable_dpi_awareness():
    if sys.platform.startswith("win"):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            pass


class ScrollFrame(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, bg="#f6f7fb", highlightthickness=0)
        self.inner = ttk.Frame(self.canvas, style="Page.TFrame")
        self.window_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.inner.bind("<Configure>", lambda _event: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda event: self.canvas.itemconfigure(self.window_id, width=event.width))
        self.canvas.bind_all("<MouseWheel>", self._wheel)

    def _nearest_scrollframe_under_pointer(self, event):
        widget = self.winfo_containing(event.x_root, event.y_root)
        while widget is not None:
            if isinstance(widget, ScrollFrame):
                return widget
            widget = getattr(widget, "master", None)
        return None

    def _wheel(self, event):
        if self._nearest_scrollframe_under_pointer(event) is self:
            self.canvas.yview_scroll(int(-event.delta / 120), "units")
            return "break"
        return None


class StageApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.scale = max(1.0, min(self.winfo_fpixels("1i") / 96, 1.3))
        self.title(f"MemoryPal {VERSION}")
        self.geometry(f"{self.px(900)}x{self.px(620)}")
        self.configure(bg="#f6f7fb")
        self.styles()
        self.build()

    def px(self, value):
        return int(round(value * self.scale))

    def styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Page.TFrame", background="#f6f7fb")
        style.configure("Card.TFrame", background="#ffffff")
        style.configure("Title.TLabel", background="#f6f7fb", foreground="#111827", font=("Segoe UI Semibold", 24))
        style.configure("Card.TLabel", background="#ffffff", foreground="#111827", font=("Segoe UI", 12))

    def build(self):
        page = ScrollFrame(self)
        page.pack(fill="both", expand=True, padx=self.px(24), pady=self.px(24))
        ttk.Label(page.inner, text=f"MemoryPal {VERSION}", style="Title.TLabel").pack(anchor="w", pady=(0, self.px(16)))
        for index in range(1, 28):
            card = ttk.Frame(page.inner, style="Card.TFrame", padding=self.px(18))
            card.pack(fill="x", pady=(0, self.px(10)))
            tk.Frame(card, bg=ACCENT, height=self.px(4)).pack(fill="x", pady=(0, self.px(10)))
            ttk.Label(card, text=f"{index}. Scroll anywhere over this page, not just on the bar.", style="Card.TLabel").pack(anchor="w")


def main():
    enable_dpi_awareness()
    StageApp().mainloop()


if __name__ == "__main__":
    main()
