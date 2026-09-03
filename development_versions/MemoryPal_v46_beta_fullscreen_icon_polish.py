import math
import struct
import tempfile
import tkinter as tk
from pathlib import Path
from tkinter import ttk


BG = "#101827"
SURFACE = "#182235"
ALT = "#24324b"
INK = "#e8edf7"
MUTED = "#a3b0c8"
PRIMARY = "#5aa8ff"


def make_demo_icon(path):
    size = 32
    pixels = []
    for y in range(size):
        row = []
        for x in range(size):
            cx = min(max(x, 7), size - 8)
            cy = min(max(y, 7), size - 8)
            if (x - cx) ** 2 + (y - cy) ** 2 > 7 * 7:
                row.append((0, 0, 0, 0))
                continue
            blue = 168 - int(y * 1.5)
            violet = 255 - int(x * 1.2)
            color = (90, max(96, blue), max(150, violet), 255)
            marks = [
                ((8, 23), (8, 10)),
                ((8, 10), (16, 20)),
                ((16, 20), (24, 10)),
                ((24, 10), (24, 23)),
            ]
            for (x1, y1), (x2, y2) in marks:
                vx, vy = x2 - x1, y2 - y1
                length = vx * vx + vy * vy
                pos = 0 if length == 0 else max(0, min(1, ((x - x1) * vx + (y - y1) * vy) / length))
                distance = math.hypot(x - (x1 + vx * pos), y - (y1 + vy * pos))
                if distance <= 2.2:
                    color = (255, 255, 255, 255)
            row.append(color)
        pixels.append(row)

    header = struct.pack("<HHH", 0, 1, 1)
    image_header = struct.pack("<IIIHHIIIIII", 40, size, size * 2, 1, 32, 0, size * size * 4, 0, 0, 0, 0)
    data = bytearray()
    for row in reversed(pixels):
        for red, green, blue, alpha in row:
            data.extend([blue, green, red, alpha])
    data.extend(b"\x00" * (((size + 31) // 32) * 4 * size))
    image = image_header + bytes(data)
    entry = struct.pack("<BBBBHHII", size, size, 0, 0, 1, 32, len(image), 22)
    path.write_bytes(header + entry + image)
    return path


class MemoryPalV46(tk.Tk):
    """Standalone milestone for steadier fullscreen and app icon polish."""

    def __init__(self):
        super().__init__()
        self.title("MemoryPal v46 - Fullscreen and Icon Polish")
        self.geometry("920x620")
        self.minsize(720, 500)
        self.configure(bg=BG)
        self.is_fullscreen = False
        self.window_transition_active = False
        self.normal_geometry = ""
        self.apply_icon()
        self.build_styles()
        self.build_ui()

    def apply_icon(self):
        try:
            icon = make_demo_icon(Path(tempfile.gettempdir()) / "memorypal-v46.ico")
            self.iconbitmap(default=str(icon))
        except tk.TclError:
            pass

    def build_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Root.TFrame", background=BG)
        style.configure("Card.TFrame", background=SURFACE)
        style.configure("TLabel", background=BG, foreground=INK, font=("Segoe UI", 11))
        style.configure("Card.TLabel", background=SURFACE, foreground=INK, font=("Segoe UI", 11))
        style.configure("Muted.TLabel", background=SURFACE, foreground=MUTED, font=("Segoe UI", 10))
        style.configure("H1.TLabel", background=BG, foreground=INK, font=("Segoe UI Semibold", 24))
        style.configure("TButton", background=ALT, foreground=INK, padding=(14, 10), borderwidth=0)
        style.configure("Primary.TButton", background=PRIMARY, foreground="white", padding=(14, 10), borderwidth=0)

    def build_ui(self):
        page = ttk.Frame(self, style="Root.TFrame", padding=26)
        page.pack(fill="both", expand=True)
        ttk.Label(page, text="MemoryPal Fullscreen Polish", style="H1.TLabel").pack(anchor="w")
        card = ttk.Frame(page, style="Card.TFrame", padding=22)
        card.pack(fill="x", pady=(18, 0))
        ttk.Label(card, text="This milestone debounces fullscreen changes and keeps one same-color cover over the app while Windows resizes it.", style="Card.TLabel", wraplength=720).pack(anchor="w")
        ttk.Label(card, text="F11 toggles true fullscreen. The fade button simulates the page-transition cover.", style="Muted.TLabel", wraplength=720).pack(anchor="w", pady=(8, 16))
        ttk.Button(card, text="Toggle Fullscreen", style="Primary.TButton", command=self.toggle_fullscreen).pack(fill="x", pady=(0, 8))
        ttk.Button(card, text="Preview Fade Cover", command=lambda: self.fade_cover(self.start_cover())).pack(fill="x")
        self.bind("<F11>", lambda _event: self.toggle_fullscreen())
        self.bind("<Escape>", lambda _event: self.toggle_fullscreen() if self.is_fullscreen else None)

    def start_cover(self):
        cover = tk.Frame(self, bg=BG)
        cover.place(relx=0, rely=0, relwidth=1, relheight=1)
        cover.tkraise()
        return cover

    def fade_cover(self, cover, step=0):
        shades = ("#101827", "#121b2b", "#141e30", "#162135", "#182235")
        if step < len(shades):
            cover.configure(bg=shades[step])
            cover.tkraise()
            self.after(22, lambda: self.fade_cover(cover, step + 1))
            return
        cover.destroy()

    def toggle_fullscreen(self):
        if self.window_transition_active:
            return
        self.window_transition_active = True
        target = not self.is_fullscreen
        cover = self.start_cover()
        self.after(35, lambda: self.apply_fullscreen(target, cover))

    def apply_fullscreen(self, target, cover):
        if target:
            self.normal_geometry = self.geometry()
        self.attributes("-fullscreen", target)
        if not target and self.normal_geometry:
            self.geometry(self.normal_geometry)
        self.is_fullscreen = target
        self.after(110, lambda: self.finish_transition(cover))

    def finish_transition(self, cover):
        self.fade_cover(cover)
        self.after(160, lambda: setattr(self, "window_transition_active", False))


if __name__ == "__main__":
    MemoryPalV46().mainloop()
