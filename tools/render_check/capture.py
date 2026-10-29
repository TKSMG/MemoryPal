"""Grab a screen rectangle as fast as possible (quarter size) for N seconds.

python capture.py x y w h seconds out.bin [hwnd]
Writes frames as: header (w4, h4, count) then for each frame: t (double),
the window's top edge on screen (int32, 0 without hwnd) + BGRA bytes.
"""
import ctypes
import struct
import sys
import time
from ctypes import wintypes

ctypes.windll.shcore.SetProcessDpiAwareness(2)
x, y, w, h = (int(v) for v in sys.argv[1:5])
seconds = float(sys.argv[5])
out = sys.argv[6]
hwnd = int(sys.argv[7]) if len(sys.argv) > 7 else 0
sw, sh = max(1, w // 4), max(1, h // 4)
user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG),
                ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


screen = user32.GetDC(0)
mem = gdi32.CreateCompatibleDC(screen)
bmp = gdi32.CreateCompatibleBitmap(screen, sw, sh)
gdi32.SelectObject(mem, bmp)
gdi32.SetStretchBltMode(mem, 3)  # COLORONCOLOR
info = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), sw, -sh, 1, 32, 0, 0, 0, 0, 0, 0)
buf = ctypes.create_string_buffer(sw * sh * 4)
frames = []
rect = wintypes.RECT()
print("ready", flush=True)
start = time.perf_counter()
while time.perf_counter() - start < seconds:
    gdi32.StretchBlt(mem, 0, 0, sw, sh, screen, x, y, w, h, 0x00CC0020)
    gdi32.GetDIBits(mem, bmp, 0, sh, buf, ctypes.byref(info), 0)
    top = 0
    if hwnd:
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        top = rect.top
    frames.append((time.perf_counter() - start, top, buf.raw))
with open(out, "wb") as handle:
    handle.write(struct.pack("<III", sw, sh, len(frames)))
    for t, top, data in frames:
        handle.write(struct.pack("<di", t, top))
        handle.write(data)
print(len(frames), "frames")
