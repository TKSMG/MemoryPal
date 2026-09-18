"""
MemoryPal v61 beta - fixed rail and fullscreen stability.

This milestone records the pass where the collapsible navigation rail was
removed. The app keeps the left rail expanded, avoids root-window opacity during
fullscreen/focus changes, and uses same-window covers to hide redraw flashes.
"""

import tkinter as tk


APP_NAME = "MemoryPal"
BG = "#111827"
SURFACE = "#192338"
RAIL = "#0b1020"
PRIMARY = "#65afff"
INK = "#edf2fb"
MUTED = "#aeb8cb"


class MemoryPalV61(tk.Tk):
    def __init__(self):
        super().__init__()
        self.withdraw()
        self.configure(bg=BG)
        self.geometry("1040x660")
        self.minsize(780, 500)
        self.title(f"{APP_NAME} v61")
        self.current_page = "Dashboard"
        self.route_token = 0
        self.window_transition_active = False

        self.rail_width = 260
        self.rail = tk.Frame(self, bg=RAIL)
        self.rail.place(x=0, y=0, width=self.rail_width, relheight=1)

        self.main = tk.Frame(self, bg=BG)
        self.main.place(x=self.rail_width, y=0, relheight=1)
        self.bind("<Configure>", self.layout_shell, add="+")

        self.header = tk.Frame(self.main, bg=BG)
        self.header.pack(fill="x", padx=34, pady=(26, 10))
        self.title_label = tk.Label(self.header, text=self.current_page, bg=BG, fg=INK, font=("Segoe UI Semibold", 26))
        self.title_label.pack(anchor="w")
        self.content = tk.Frame(self.main, bg=BG)
        self.content.pack(fill="both", expand=True, padx=34, pady=(10, 34))

        self.draw_rail()
        self.show_page(self.current_page, transition=False)
        self.after(80, self.deiconify)

    def layout_shell(self, _event=None):
        width = self.winfo_width()
        height = self.winfo_height()
        if width <= 1 or height <= 1:
            return
        self.rail.place_configure(width=self.rail_width, height=height)
        self.main.place_configure(x=self.rail_width, y=0, width=max(1, width - self.rail_width), height=height)

    def draw_rail(self):
        for child in self.rail.winfo_children():
            child.destroy()
        tk.Label(self.rail, text=APP_NAME, bg=RAIL, fg=INK, font=("Segoe UI Semibold", 22)).pack(anchor="w", padx=20, pady=(28, 18))
        for page in ("Dashboard", "Capture", "Review", "Settings"):
            tk.Button(self.rail, text=page, command=lambda value=page: self.show_page(value), relief="flat", bg=RAIL, fg=MUTED, anchor="w", padx=18, pady=10).pack(fill="x", padx=16, pady=5)

    def make_cover(self, parent, color):
        cover = tk.Canvas(parent, bg=color, highlightthickness=0)
        cover.memorypal_color = color
        cover.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.paint_cover(cover)
        cover.lift()
        cover.update()
        return cover

    def paint_cover(self, cover, stipple=""):
        color = getattr(cover, "memorypal_color", BG)
        cover.delete("veil")
        cover.configure(bg=color)
        cover.create_rectangle(0, 0, max(1, cover.winfo_width()), max(1, cover.winfo_height()), fill=color, outline="", stipple=stipple, tags="veil")

    def fade_cover(self, cover, step=0):
        if not cover or not cover.winfo_exists():
            return
        stipples = ("", "gray75", "gray50", "gray25", "gray12")
        self.paint_cover(cover, stipples[min(step, len(stipples) - 1)])
        cover.lift()
        if step < len(stipples) - 1:
            self.after(28, lambda: self.fade_cover(cover, step + 1))
        else:
            self.after(28, cover.destroy)

    def show_page(self, page, transition=True):
        self.route_token += 1
        token = self.route_token
        cover = self.make_cover(self.main, BG) if transition and self.main.winfo_viewable() else None
        self.current_page = page
        self.title_label.configure(text=page)
        for child in self.content.winfo_children():
            child.destroy()
        self.after(24 if cover else 0, lambda: self.finish_page(page, token, cover))

    def finish_page(self, page, token, cover):
        if token != self.route_token:
            if cover:
                cover.destroy()
            return
        card = tk.Frame(self.content, bg=SURFACE, padx=24, pady=22)
        card.pack(fill="both", expand=True)
        tk.Label(card, text=page, bg=SURFACE, fg=INK, font=("Segoe UI Semibold", 22)).pack(anchor="w")
        tk.Label(card, text="The rail stays expanded. Page redraws and window changes use same-window covers instead of fading the whole desktop window.", bg=SURFACE, fg=MUTED, font=("Segoe UI", 12), wraplength=560, justify="left").pack(anchor="w", pady=(8, 0))
        if cover:
            self.after(32, lambda: self.fade_cover(cover))

    def toggle_fullscreen_demo(self):
        if self.window_transition_active:
            return
        self.window_transition_active = True
        cover = self.make_cover(self, BG)
        self.attributes("-fullscreen", not bool(self.attributes("-fullscreen")))
        self.after(130, lambda: self.fade_cover(cover))
        self.after(320, lambda: setattr(self, "window_transition_active", False))


if __name__ == "__main__":
    MemoryPalV61().mainloop()
