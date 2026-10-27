"""Measure flashing and tearing in the desktop app (Windows only).

Drives rendering scenarios while capture.py records the window, then scores them.

python render_probe.py OUTDIR [scenario ...]
Per scenario it prints: frames, flash (peak extra bright-pixel share), and
"mixed" frames that match neither the before nor the after picture; the mixed
frames are also saved as PNGs to look at.
"""
import os
import struct
import subprocess
import sys
import tempfile
import time
import zlib

os.environ["MEMORYPAL_DATA_DIR"] = tempfile.mkdtemp(prefix="mp-render-")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "latest_app"))
import MemoryPalDesktop as M  # noqa: E402
from memorypal.models import Card  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(sys.argv[1])
os.makedirs(OUT, exist_ok=True)
WANTED = sys.argv[2:]

M.enable_dpi_awareness()
app = M.MemoryPalApp()
app.store.onboarding = {"done": True, "persona": "student"}
app.store.add_cards([Card(deck=f"Deck {n % 6}", front=f"Question number {n} about something long enough to wrap", back=f"Answer {n} " * 6) for n in range(150)])
app.show_view("dashboard")
app.lift()
app.attributes("-topmost", True)
app.update()


def png(path, w, h, bgra):
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        row = bgra[y * w * 4:(y + 1) * w * 4]
        for x in range(w):
            b, g, r = row[x * 4], row[x * 4 + 1], row[x * 4 + 2]
            raw += bytes((r, g, b))
    chunk = lambda k, d: struct.pack(">I", len(d)) + k + d + struct.pack(">I", zlib.crc32(k + d) & 0xFFFFFFFF)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(bytes(raw), 6)) + chunk(b"IEND", b""))


def stats(frame, step=7):
    bright = total = 0
    for i in range(0, len(frame), 4 * step):
        b, g, r = frame[i], frame[i + 1], frame[i + 2]
        total += 1
        if min(r, g, b) > 225:
            bright += 1
    return bright / max(1, total)


def diff(a, b, step=11):
    total = count = 0
    for i in range(0, len(a), 4 * step):
        total += abs(a[i] - b[i]) + abs(a[i + 1] - b[i + 1]) + abs(a[i + 2] - b[i + 2])
        count += 1
    return total / max(1, count) / 3


def run(name, action, seconds=2.2, lead=0.35):
    app.update()
    x, y, w, h = app.winfo_rootx(), app.winfo_rooty(), app.winfo_screenwidth(), app.winfo_screenheight()
    w, h = app.winfo_screenwidth() - x, app.winfo_screenheight() - y
    out = os.path.join(OUT, f"{name}.bin")
    proc = subprocess.Popen([sys.executable, os.path.join(HERE, "capture.py"), str(x), str(y), str(w), str(h), str(seconds), out], stdout=subprocess.PIPE, text=True)
    proc.stdout.readline()  # wait until frames are being recorded
    end = time.time() + lead
    while time.time() < end:
        app.update()
    action()
    while proc.poll() is None:
        app.update()
        time.sleep(0.005)
    with open(out, "rb") as f:
        fw, fh, count = struct.unpack("<III", f.read(12))
        frames = []
        for _ in range(count):
            (t,) = struct.unpack("<d", f.read(8))
            frames.append((t, f.read(fw * fh * 4)))
    os.remove(out)
    first, last = frames[0][1], frames[-1][1]
    base_bright = max(stats(first), stats(last))
    peak, mixed, changes = 0.0, [], 0
    previous = first
    for index, (t, data) in enumerate(frames):
        peak = max(peak, stats(data) - base_bright)
        if diff(data, previous) > 0.5:
            changes += 1
        previous = data
        if diff(data, first) > 1.5 and diff(data, last) > 1.5:
            mixed.append(index)
    distinct = []
    for index in mixed:
        if not distinct or diff(frames[index][1], frames[distinct[-1]][1]) > 1.5:
            distinct.append(index)
    for n, index in enumerate(distinct[:6]):
        png(os.path.join(OUT, f"{name}-mixed{n}.png"), fw, fh, frames[index][1])
    where = [f"{frames[index][0] - frames[0][0]:.2f}s:{changed_box(frames[index][1], last, fw, fh)}" for index in distinct[:3]]
    png(os.path.join(OUT, f"{name}-after.png"), fw, fh, last)
    print(f"{name:18} frames={len(frames):4} changes={changes:3} flash={peak:+.3f} mixed_frames={len(mixed):3} distinct_mixed={len(distinct)}"
          + (f" differs_from_final={' '.join(where)}" if where else ""))


def changed_box(a, b, w, h, step=8):
    """Where a frame differs from another, as x0,y0-x1,y1 in pixels (sampled)."""
    xs, ys = [], []
    for y in range(0, h, step):
        row = y * w * 4
        for x in range(0, w, step):
            i = row + x * 4
            if abs(a[i] - b[i]) + abs(a[i + 1] - b[i + 1]) + abs(a[i + 2] - b[i + 2]) > 24:
                xs.append(x)
                ys.append(y)
    return f"{min(xs)},{min(ys)}-{max(xs)},{max(ys)}" if xs else "none"


def scroll_frame():
    stack = [app.view_host]
    while stack:
        widget = stack.pop()
        if isinstance(widget, M.ScrollFrame):
            return widget
        stack.extend(widget.winfo_children())
    return None


def wheel_burst():
    frame = scroll_frame()
    for n in range(12):
        app.after(n * 30, lambda: frame._queue_wheel(frame._wheel_step_px))


def drag_burst():
    frame = scroll_frame()
    for n in range(40):
        app.after(n * 12, lambda n=n: frame._scrollbar_yview("moveto", str(n / 60)))


def resize():
    app.geometry(f"{app.winfo_width() - 200}x{app.winfo_height() - 120}")


def prebuild_now():
    # Build the rail pages out of sight, as the app does when left idle: the
    # screen should not change at all.
    if hasattr(app, "prebuild_page"):
        app.forget_kept_pages()
        for view in app.PREBUILD_PAGES:
            if view != app.current_view:
                app.prebuild_page(view)


SCENARIOS = [
    ("switch_stats", lambda: app.show_view("stats")),
    ("switch_library", lambda: app.show_view("library")),
    ("switch_capture", lambda: app.show_view("capture")),
    ("switch_dashboard", lambda: app.show_view("dashboard")),
    ("switch_kept_stats", lambda: app.show_view("stats")),
    ("switch_kept_dashboard", lambda: app.show_view("dashboard")),
    ("idle_prebuild", prebuild_now),
    ("wheel_scroll", wheel_burst),
    ("drag_scroll", drag_burst),
    ("fullscreen_on", app.toggle_true_fullscreen),
    ("fullscreen_off", app.toggle_true_fullscreen),
    ("resize", resize),
    ("restore", lambda: app.state("normal")),
    ("shrink", lambda: app.geometry(f"{app.winfo_screenwidth() * 2 // 3}x{app.winfo_screenheight() * 2 // 3}+0+0")),
    ("grow", lambda: app.geometry(f"{app.winfo_screenwidth() - 40}x{app.winfo_screenheight() - 80}+0+0")),
    ("maximize", lambda: app.state("zoomed")),
    ("unmaximize", lambda: app.state("normal")),
    ("theme_light", app.toggle_theme),
    ("theme_dark", app.toggle_theme),
    ("text_large", lambda: app.update_accessibility_preference("text_size", "Large")),
]
for name, action in SCENARIOS:
    if not WANTED or any(name.startswith(w) for w in WANTED):
        run(name, action)
app.destroy()
