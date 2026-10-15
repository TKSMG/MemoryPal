"""Grab a screen rectangle at full size, as fast as possible, for N seconds.

python grab_frames.py x y w h seconds out.bin
Writes: header (w4, h4, count) then per frame: t (double) + RGB bytes.
"""
import ctypes
import struct
import sys
import time

from PIL import ImageGrab

ctypes.windll.shcore.SetProcessDpiAwareness(2)
x, y, w, h = (int(v) for v in sys.argv[1:5])
seconds, out = float(sys.argv[5]), sys.argv[6]
frames = []
print("ready", flush=True)
start = time.perf_counter()
while time.perf_counter() - start < seconds:
    frames.append((time.perf_counter() - start, ImageGrab.grab(bbox=(x, y, x + w, y + h)).tobytes()))
with open(out, "wb") as handle:
    handle.write(struct.pack("<III", w, h, len(frames)))
    for t, data in frames:
        handle.write(struct.pack("<d", t))
        handle.write(data)
