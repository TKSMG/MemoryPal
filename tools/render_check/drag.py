"""Drag the mouse like a person would: press at x,y, move by dx,dy, let go.

python drag.py x y dx dy seconds
Runs in its own process so the app can sit in Windows' move/resize loop
(which is where a real title bar or edge drag puts it) while this moves.
"""
import ctypes
import sys
import time

ctypes.windll.shcore.SetProcessDpiAwareness(2)
user32 = ctypes.windll.user32
x, y, dx, dy = (int(v) for v in sys.argv[1:5])
# CI machines often have "Show window contents while dragging" off, which
# drags only an outline and resizes once at the end; people have it on.
user32.SystemParametersInfoW(0x0025, 1, None, 0x02)  # SPI_SETDRAGFULLWINDOWS, SPIF_SENDCHANGE
seconds = float(sys.argv[5])
LEFTDOWN, LEFTUP = 0x0002, 0x0004
user32.SetCursorPos(x, y)
time.sleep(0.05)
user32.mouse_event(LEFTDOWN, 0, 0, 0, 0)
time.sleep(0.05)
steps = max(1, int(seconds / 0.008))
start = time.perf_counter()
for n in range(1, steps + 1):
    user32.SetCursorPos(x + dx * n // steps, y + dy * n // steps)
    # Even pace, like a hand: 125 moves a second.
    while time.perf_counter() - start < n * seconds / steps:
        time.sleep(0.001)
time.sleep(0.05)
user32.mouse_event(LEFTUP, 0, 0, 0, 0)
