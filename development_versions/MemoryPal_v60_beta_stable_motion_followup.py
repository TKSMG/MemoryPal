"""
MemoryPal v60 beta - stable motion follow-up.

This milestone records the follow-up polish pass where page transitions were
covered at the full page-panel level by an in-window reveal, fullscreen/focus
protection stopped using transparent helper windows, and sidebar collapse became
a clean width snap with a small rail reveal instead of a repeated page reflow.
"""

import tkinter as tk


APP_NAME = "MemoryPal"
BG = "#111827"
SURFACE = "#192338"
RAIL = "#0b1020"
PRIMARY = "#65afff"
INK = "#edf2fb"
MUTED = "#aeb8cb"


class MemoryPalV60(tk.Tk):
    def __init__(self):
        super().__init__()
        self.withdraw()
        self.configure(bg=BG)
        self.geometry("1020x660")
        self.minsize(760, 500)
        self.title(f"{APP_NAME} v60")
        self.collapsed = False
        self.current_page = "Dashboard"
        self.route_token = 0

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

    def layout_shell(self, event=None):
        width = self.winfo_width()
        height = self.winfo_height()
        if width <= 1 or height <= 1:
            return
        self.rail.place_configure(width=self.rail_width, height=height)
        self.main.place_configure(x=self.rail_width, y=0, width=max(1, width - self.rail_width), height=height)

    def draw_rail(self, preserve_cover=None):
        for child in self.rail.winfo_children():
            if child is preserve_cover:
                continue
            child.destroy()
        brand = "M" if self.collapsed else APP_NAME
        tk.Label(self.rail, text=brand, bg=RAIL, fg=INK, font=("Segoe UI Semibold", 22)).pack(anchor="w", padx=18, pady=(24, 16))
        toggle = ">" if self.collapsed else "<  Collapse"
        tk.Button(self.rail, text=toggle, command=self.toggle_rail, relief="flat", bg=PRIMARY, fg="white").pack(fill="x", padx=14, pady=(0, 16))
        for page in ("Dashboard", "Capture", "Review", "Settings"):
            text = page[:1] if self.collapsed else page
            tk.Button(self.rail, text=text, command=lambda value=page: self.show_page(value), relief="flat", bg=RAIL, fg=MUTED).pack(fill="x", padx=14, pady=5)

    def toggle_rail(self):
        cover = tk.Canvas(self.rail, bg=RAIL, highlightthickness=0)
        cover.place(relx=0, rely=0, relwidth=1, relheight=1)
        cover.memorypal_color = RAIL
        cover.create_rectangle(0, 0, max(1, self.rail.winfo_width()), max(1, self.rail.winfo_height()), fill=RAIL, outline="")
        cover.lift()
        cover.update()
        self.collapsed = not self.collapsed
        self.rail_width = 78 if self.collapsed else 260
        self.draw_rail(preserve_cover=cover)
        self.layout_shell()
        cover.lift()
        self.after(30, lambda: self.fade_cover(cover))

    def make_page_cover(self):
        cover = tk.Canvas(self.main, bg=BG, highlightthickness=0)
        cover.place(relx=0, rely=0, relwidth=1, relheight=1)
        cover.memorypal_color = BG
        cover.create_rectangle(0, 0, max(1, self.main.winfo_width()), max(1, self.main.winfo_height()), fill=BG, outline="")
        cover.lift()
        cover.update()
        return cover

    def show_page(self, page, transition=True):
        self.route_token += 1
        token = self.route_token
        cover = self.make_page_cover() if transition and self.main.winfo_viewable() else None
        self.current_page = page
        self.title_label.configure(text=page)
        for child in self.content.winfo_children():
            child.destroy()
        delay = 24 if cover else 0
        self.after(delay, lambda: self.finish_page(page, token, cover))

    def finish_page(self, page, token, cover):
        if token != self.route_token:
            self.destroy_cover(cover)
            return
        card = tk.Frame(self.content, bg=SURFACE, padx=24, pady=22)
        card.pack(fill="both", expand=True)
        tk.Label(card, text=page, bg=SURFACE, fg=INK, font=("Segoe UI Semibold", 22)).pack(anchor="w")
        tk.Label(card, text="Page content changes behind one stable same-window cover, then fades in after the redraw settles.", bg=SURFACE, fg=MUTED, font=("Segoe UI", 12), wraplength=560, justify="left").pack(anchor="w", pady=(8, 0))
        if cover:
            self.after(32, lambda: self.fade_cover(cover, token=token))

    def fade_cover(self, cover, step=0, token=None):
        if token is not None and token != self.route_token:
            self.destroy_cover(cover)
            return
        if not cover or not cover.winfo_exists():
            return
        stipples = ("", "gray75", "gray50", "gray25", "gray12")
        color = getattr(cover, "memorypal_color", BG)
        cover.delete("veil")
        cover.configure(bg=color)
        cover.create_rectangle(
            0,
            0,
            max(1, cover.winfo_width()),
            max(1, cover.winfo_height()),
            fill=color,
            outline="",
            stipple=stipples[min(step, len(stipples) - 1)],
            tags="veil",
        )
        cover.lift()
        if step < len(stipples) - 1:
            self.after(30, lambda: self.fade_cover(cover, step + 1, token))
        else:
            self.after(30, lambda: self.destroy_cover(cover))

    def destroy_cover(self, cover):
        try:
            if cover and cover.winfo_exists():
                cover.destroy()
        except tk.TclError:
            pass


if __name__ == "__main__":
    MemoryPalV60().mainloop()
