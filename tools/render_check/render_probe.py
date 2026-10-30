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


CONFIGURES = []
# Where a resize step's time goes (Windows): the whole relayout, and the
# repaint that ends it.
STEP_TIMES = {}


def _clocked(owner, attr, key):
    original = getattr(owner, attr)

    def wrapper(*args, **kwargs):
        began = time.perf_counter()
        try:
            return original(*args, **kwargs)
        finally:
            STEP_TIMES.setdefault(key, []).append((time.perf_counter() - began) * 1000)
    setattr(owner, attr, wrapper)


_clocked(M.MemoryPalApp, "_relayout_after_resize", "relayout")
_clocked(M.MemoryPalApp, "settle_layout", "settle")
_clocked(M, "set_window_redraw", "redraw")
_clocked(M, "flush_pending_paint", "paint")
app.bind("<Configure>", lambda e: CONFIGURES.append((time.perf_counter(), e.x, e.y, e.width, e.height)) if e.widget is app else None, add="+")


def run(name, action, seconds=2.2, lead=0.35):
    app.update()
    # A drag of the top edge grows the window upwards: record from higher up.
    lift = min(app.winfo_rooty(), 200) if name.startswith("drag_resize_top") else 0
    x, y = app.winfo_rootx(), app.winfo_rooty() - lift
    w, h = app.winfo_screenwidth() - x, app.winfo_screenheight() - y
    out = os.path.join(OUT, f"{name}.bin")
    start_top = window_rect().top
    proc = subprocess.Popen([sys.executable, os.path.join(HERE, "capture.py"), str(x), str(y), str(w), str(h), str(seconds), out,
                             str(app.window_handle(app) or 0)], stdout=subprocess.PIPE, text=True)
    proc.stdout.readline()  # wait until frames are being recorded
    end = time.time() + lead
    while time.time() < end:
        app.update()
    CONFIGURES.clear()
    STEP_TIMES.clear()
    started = time.perf_counter()
    action()
    # The real event loop, as the app runs it: Windows' move/size loop only
    # hands Tk its events from inside mainloop.
    def wait():
        if proc.poll() is None:
            app.after(20, wait)
        else:
            app.quit()
    app.after(20, wait)
    beats = []

    def beat():
        beats.append(time.perf_counter())
        if proc.poll() is None:
            app.after(10, beat)
    app.after(10, beat)
    app.mainloop()
    with open(out, "rb") as f:
        fw, fh, count = struct.unpack("<III", f.read(12))
        frames = []
        tops = []
        for _ in range(count):
            t, top = struct.unpack("<di", f.read(12))
            tops.append(top)
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
    if name.startswith("fullscreen"):
        # With the fade, every frame should be the old or the new picture
        # blended with the page colour; anything else is a glitch getting
        # through (shifted, half drawn, desktop showing).
        bg_hex = M.COLORS["bg"].lstrip("#")
        bg = (int(bg_hex[4:6], 16), int(bg_hex[2:4], 16), int(bg_hex[0:2], 16))  # BGR like the frames
        worst_off = (0.0, 0.0)
        worst_index = 0
        off_frames = 0
        for frame_index, (t, data) in enumerate(frames):
            best = None
            for ref in (first, last):
                num = den = 0.0
                samples = []
                for i in range(0, len(data), 4 * 13):
                    for c in range(3):
                        d, r = data[i + c] - ref[i + c], bg[c] - ref[i + c]
                        num += d * r
                        den += r * r
                        samples.append((d, r))
                a = max(0.0, min(1.0, num / den)) if den else 0.0
                residual = sum(abs(d - a * r) for d, r in samples) / max(1, len(samples))
                if best is None or residual < best:
                    best = residual
            if best > 3.0:
                off_frames += 1
            if best > worst_off[0]:
                worst_off = (best, t - frames[0][0])
                worst_index = frame_index
        extra_fade = f" not_a_fade_frames={off_frames} worst_residual={worst_off[0]:.1f}@{worst_off[1]:.2f}s"
    else:
        extra_fade = ""
        worst_off, worst_index = (0.0, 0.0), 0
    if name.startswith("fullscreen") and worst_off[0] > 3.0:
        # A coarse colour map of each in-between frame (artifacts can't be
        # fetched): B blue, W white, L light, M mid, D dark, K near black.
        def cls(r, g, b):
            if b > r + 40 and b > g + 15:
                return "B"
            v = (r + g + b) / 3
            return "W" if v > 235 else "L" if v > 170 else "M" if v > 90 else "D" if v > 25 else "K"
        shots = [("before", 0), ("worst", worst_index), ("after", len(frames) - 1)]
        for label, index in shots:
            data = frames[index][1]
            blue = sum(1 for i in range(0, len(data), 4 * 7) if data[i] > data[i + 2] + 40 and data[i] > data[i + 1] + 15)
            print(f"MAP {name} {label} t={frames[index][0] - frames[0][0]:.2f} blue={blue / max(1, len(data) // 28):.3f}")
            for gy in range(14):
                y = int((gy + 0.5) * fh / 14)
                row = ""
                for gx in range(40):
                    x = int((gx + 0.5) * fw / 40)
                    i = (y * fw + x) * 4
                    row += cls(data[i + 2], data[i + 1], data[i])
                print(f"MAP   {row}")
    extra = extra_fade
    if name.startswith("fullscreen") and distinct:
        # What the in-between frame is: the old or the new picture, moved?
        m = frames[distinct[0]][1]
        box = (2, 2, 60, 30)
        for label, ref in (("old", first), ("new", last)):
            best = None
            for dy in range(-14, 15):
                for dx in range(-14, 15):
                    total = count = 0
                    for y in range(box[1], box[3], 2):
                        for x in range(box[0], box[2], 2):
                            sx, sy = x - dx, y - dy
                            if 0 <= sx < fw and 0 <= sy < fh:
                                i, j = (y * fw + x) * 4, (sy * fw + sx) * 4
                                total += abs(m[i] - ref[j]) + abs(m[i + 1] - ref[j + 1]) + abs(m[i + 2] - ref[j + 2])
                                count += 1
                    err = total / max(1, count) / 3
                    if best is None or err < best[0]:
                        best = (err, dx, dy)
            extra += f" mid_vs_{label}=shift{4 * best[1]},{4 * best[2]}px,err{best[0]:.1f}"
        # How much of it is plain background (nothing drawn yet).
        bg = m[(fh // 2 * fw + fw // 2) * 4:(fh // 2 * fw + fw // 2) * 4 + 3]
        rows = [y for y in range(0, fh, 4) if all(abs(m[(y * fw + x) * 4] - last[(y * fw + x) * 4]) < 10 for x in range(0, fw, 8))]
        extra += f" mid_rows_matching_new={len(rows)}/{len(range(0, fh, 4))}"
    if LAST_TIMING:
        extra += f" busy={LAST_TIMING.pop():.0f}ms"
        intervals = [b[0] - a[0] for a, b in zip(frames, frames[1:])]
        extra += f" frame_interval={1000 * sum(intervals) / max(1, len(intervals)):.0f}ms"
    if name.startswith("drag_"):
        # The longest the window went without following the mouse.
        times = [started] + [entry[0] for entry in CONFIGURES]
        gaps = [later - earlier for earlier, later in zip(times, times[1:])]
        extra += f" window_updates={len(CONFIGURES)} longest_stall={1000 * max(gaps or [0]):.0f}ms"
        if CONFIGURES:
            extra += f" end={CONFIGURES[-1][3]}x{CONFIGURES[-1][4]}+{CONFIGURES[-1][1]}+{CONFIGURES[-1][2]}"
        beat_gaps = [later - earlier for earlier, later in zip(beats, beats[1:])]
        extra += f" timer_beats={len(beats)} longest_beat_gap={1000 * max(beat_gaps or [0]):.0f}ms"
        for key in ("relayout", "settle", "redraw", "paint"):
            values = STEP_TIMES.get(key, [])
            if values:
                extra += f" {key}={len(values)}x{sum(values) / len(values):.0f}/{max(values):.0f}ms"
    if name.startswith("drag_resize_top"):
        # The page should move up with the window's top edge, frame by frame.
        # Each frame: how far the title sits from where the edge says it
        # should be (in quarter pixels). Windows keeps the old picture in
        # place on screen while the edge moves, so a late repaint shows the
        # page pushed down from the top, then snapping back.
        top = (lift + app.tab_bar_height() + 4) // 4
        box = (0, top, 260 // 4, top + 110 // 4)
        offsets, seen = [], []
        edge0 = visible_top(first, fw, fh)
        for (_t, data), edge in zip(frames, tops):
            expected = (edge - start_top) / 4
            shift = vertical_shift(data, first, fw, fh, box)
            offsets.append(shift - expected)
            # Against the edge as it is drawn on screen, which is what people
            # see (the compositor can show the whole window late).
            seen.append(shift - (visible_top(data, fw, fh) - edge0))
        series = []
        for (t, data), edge in zip(frames, tops):
            if not 0.45 < t - frames[0][0] < 1.9:
                continue
            series.append(f"{edge - start_top}/{4 * vertical_shift(data, first, fw, fh, box)}/{4 * (visible_top(data, fw, fh) - edge0)}")
        if name.endswith("_grow"):
            print(f"SERIES {name} desk={tuple(first[120:123])} edge0={edge0} " + " ".join(series))
        off = [value for value in offsets if abs(value) > 2.5]
        extra += f" pushed_down_frames={len(off)} worst_offset={4 * max([abs(v) for v in offsets] or [0]):.0f}px"
        off = [value for value in seen if abs(value) > 1.5]
        extra += f" off_visible_edge_frames={len(off)} worst_vs_visible_edge={4 * max([abs(v) for v in seen] or [0]):.0f}px"
    elif name.startswith("drag_resize"):
        # Dragging the bottom-right corner must leave the top-left (the page
        # title) exactly where it was: any change there is the page jumping
        # or being stretched.
        top = (app.tab_bar_height() + 4) // 4
        box = (0, top, 260 // 4, top + 110 // 4)
        jumped = [index for index, (_t, data) in enumerate(frames) if region_diff(data, first, fw, box) > 2.0]
        extra += f" title_moved_frames={len(jumped)}"
        for n, index in enumerate(jumped[:4]):
            png(os.path.join(OUT, f"{name}-jump{n}.png"), fw, fh, frames[index][1])
        for index in jumped[:1] + jumped[len(jumped) // 2:len(jumped) // 2 + 1]:
            extra += f" jump@{frames[index][0] - frames[0][0]:.2f}s={best_fit(frames[index][1], first, fw, fh, box)}"
        if os.environ.get("PRINT_PNG") and jumped:
            # Artifacts can't always be fetched: the pictures go in the log too.
            import base64
            for label, index in (("before", 0), ("jump", jumped[0]), ("jump_mid", jumped[len(jumped) // 2])):
                path = os.path.join(OUT, f"{name}-{label}-print.png")
                png(path, fw, fh, frames[index][1])
                with open(path, "rb") as handle:
                    print(f"PNG {name} {label} t={frames[index][0]:.2f} " + base64.b64encode(handle.read()).decode("ascii"))
    print(f"{name:18} frames={len(frames):4} changes={changes:3} flash={peak:+.3f} mixed_frames={len(mixed):3} distinct_mixed={len(distinct)}"
          + (f" differs_from_final={' '.join(where)}" if where else "") + extra)


def visible_top(frame, w, h, x=30):
    """The first row (from the top) that isn't the desktop behind the window."""
    i = x * 4
    desk = frame[i:i + 3]
    for y in range(h):
        j = (y * w + x) * 4
        if abs(frame[j] - desk[0]) + abs(frame[j + 1] - desk[1]) + abs(frame[j + 2] - desk[2]) > 40:
            return y
    return 0


def vertical_shift(frame, before, w, h, box, reach=40):
    """How far up or down (quarter pixels) the box's picture moved."""
    x0, y0, x1, y1 = box
    best = None
    for dy in range(-reach, reach + 1):
        total = count = 0
        for y in range(y0, y1, 2):
            ty = y + dy
            if not (0 <= ty < h):
                continue
            for x in range(x0, x1, 2):
                i, j = (ty * w + x) * 4, (y * w + x) * 4
                total += abs(frame[i] - before[j]) + abs(frame[i + 1] - before[j + 1]) + abs(frame[i + 2] - before[j + 2])
                count += 1
        if count:
            err = total / count
            if best is None or err < best[0]:
                best = (err, dy)
    return best[1] if best else 0


def best_fit(frame, before, w, h, box):
    """How the title area moved: the scale (about the top-left) and shift
    that make the earlier picture match this frame best."""
    x0, y0, x1, y1 = box
    best = None
    for scale in [1 + n * 0.02 for n in range(-10, 26)]:
        for dx in range(-6, 7, 2):
            for dy in range(-6, 7, 2):
                total = count = 0
                for y in range(y0, y1, 2):
                    for x in range(x0, x1, 2):
                        sx, sy = int((x - dx) / scale), int((y - dy) / scale)
                        if not (0 <= sx < w and 0 <= sy < h):
                            continue
                        i, j = (y * w + x) * 4, (sy * w + sx) * 4
                        total += abs(frame[i] - before[j]) + abs(frame[i + 1] - before[j + 1]) + abs(frame[i + 2] - before[j + 2])
                        count += 1
                err = total / max(1, count) / 3
                if best is None or err < best[0]:
                    best = (err, scale, dx, dy)
    return f"scale{best[1]:.2f},shift{best[2]},{best[3]},err{best[0]:.1f}"


def region_diff(a, b, w, box):
    x0, y0, x1, y1 = box
    total = count = 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            i = (y * w + x) * 4
            total += abs(a[i] - b[i]) + abs(a[i + 1] - b[i + 1]) + abs(a[i + 2] - b[i + 2])
            count += 1
    return total / max(1, count) / 3


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


def window_rect():
    import ctypes
    from ctypes import wintypes

    rect = wintypes.RECT()
    ctypes.windll.user32.GetWindowRect(app.window_handle(app), ctypes.byref(rect))
    return rect


def drag(x, y, dx, dy, seconds=1.2):
    subprocess.Popen([sys.executable, os.path.join(HERE, "drag.py"), str(x), str(y), str(dx), str(dy), str(seconds)])


def idle_then(action):
    # As if the app had been left alone: the next idle build is due mid-drag.
    def run_it():
        if hasattr(app, "forget_kept_pages"):
            app.forget_kept_pages()
            app._last_input = 0.0
            if app.__dict__.get("_prebuild_after") is not None:
                app.after_cancel(app._prebuild_after)
                app._prebuild_after = None
            app.schedule_prebuild(250)
        action()
    return run_it


def drag_corner(dx, dy):
    def run_it():
        rect = window_rect()
        drag(rect.right - 4, rect.bottom - 4, dx, dy)
    return run_it


LAST_TIMING = []


def timed(action):
    # How long the change keeps the app busy (the old picture stays up meanwhile).
    def run_it():
        mark = time.perf_counter()
        action()
        LAST_TIMING.append(1000 * (time.perf_counter() - mark))
    return run_it


def drag_top(dy):
    def run_it():
        rect = window_rect()
        drag(rect.left + (rect.right - rect.left) // 2, rect.top + 2, 0, dy)
    return run_it


def drag_title():
    rect = window_rect()
    drag(rect.left + (rect.right - rect.left) // 3, rect.top + 12, 120, 70)


def place_for_drag():
    app.state("normal")
    app.geometry(f"{app.winfo_screenwidth() * 3 // 5}x{app.winfo_screenheight() * 3 // 5}+20+20")
    app.update()


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
    ("fullscreen_on", timed(app.toggle_true_fullscreen)),
    ("fullscreen_off", timed(app.toggle_true_fullscreen)),
    ("fullscreen_on_again", timed(app.toggle_true_fullscreen)),
    ("fullscreen_off_again", timed(app.toggle_true_fullscreen)),
    # Experiment: the same with the compositor's window animations turned off.
    ("resize", resize),
    ("restore", lambda: app.state("normal")),
    ("shrink", lambda: app.geometry(f"{app.winfo_screenwidth() * 2 // 3}x{app.winfo_screenheight() * 2 // 3}+0+0")),
    ("grow", lambda: app.geometry(f"{app.winfo_screenwidth() - 40}x{app.winfo_screenheight() - 80}+0+0")),
    ("maximize", lambda: app.state("zoomed")),
    ("unmaximize", lambda: app.state("normal")),
    ("drag_setup", place_for_drag),
    ("drag_move", drag_title),
    ("drag_move_idle", idle_then(drag_title)),
    ("drag_setup2", place_for_drag),
    ("drag_resize_grow", drag_corner(160, 90)),
    ("drag_resize_shrink", drag_corner(-160, -90)),
    ("drag_resize_idle", idle_then(drag_corner(160, 90))),
    # Pages kept from before the resize must show at the new size at once.
    ("after_resize_kept_stats", lambda: app.show_view("stats")),
    ("after_resize_kept_dashboard", lambda: app.show_view("dashboard")),
    ("drag_resize_bottom_grow", lambda: (lambda rect: drag(rect.left + (rect.right - rect.left) // 2, rect.bottom - 4, 0, 160))(window_rect())),
    ("drag_resize_bottom_shrink", lambda: (lambda rect: drag(rect.left + (rect.right - rect.left) // 2, rect.bottom - 4, 0, -160))(window_rect())),
    ("drag_resize_left", lambda: (lambda rect: drag(rect.left + 4, rect.top + (rect.bottom - rect.top) // 2, -120, 0))(window_rect())),
    ("after_resize_kept_library", lambda: app.show_view("library")),
    ("drag_setup_top", lambda: (app.state("normal"), app.geometry(f"{app.winfo_screenwidth() * 3 // 5}x{app.winfo_screenheight() * 2 // 5}+20+{app.winfo_screenheight() // 3}"), app.update())),
    ("drag_resize_top_grow", drag_top(-140)),
    ("drag_resize_top_shrink", drag_top(140)),
    ("theme_light", app.toggle_theme),
    ("theme_dark", app.toggle_theme),
    ("text_large", lambda: app.update_accessibility_preference("text_size", "Large")),
]
for name, action in SCENARIOS:
    if not WANTED or any(name.startswith(w) for w in WANTED):
        run(name, action)
app.destroy()
