"""Measure how evenly the desktop app scrolls (frame pacing), per strategy.

python scroll_probe.py [view ...]

Feeds a ScrollFrame a steady stream of small touchpad-style deltas (one every
8ms, like a Windows precision touchpad) and then a burst of wheel notches,
and records when each scroll step reached the screen. Prints, per view and
input: steps per second, the median / 95th percentile gap between steps, how
many gaps were longer than 1.5 frames (visible hitches), and the average time
spent in each phase of a step.
"""
import os
import statistics
import sys
import tempfile
import time

os.environ["MEMORYPAL_DATA_DIR"] = tempfile.mkdtemp(prefix="mp-scroll-")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "latest_app"))
import MemoryPalDesktop as M  # noqa: E402
from memorypal.models import Card  # noqa: E402

VIEWS = sys.argv[1:] or ["dashboard", "library", "stats"]

M.enable_dpi_awareness()
app = M.MemoryPalApp()
app.store.onboarding = {"done": True, "persona": "student"}
app.store.add_cards([Card(deck=f"Deck {n % 6}", front=f"Question number {n} about something long enough to wrap",
                          back=f"Answer {n} " * 6) for n in range(150)])
app.geometry("1280x900+0+0")
app.lift()
app.update()

hz = M.display_refresh_hz(app)
frame_ms = 1000.0 / hz
print(f"platform={sys.platform} refresh={hz:.0f}Hz frame={frame_ms:.1f}ms tk={app.tk.call('info', 'patchlevel')} "
      f"next_vblank={M.ms_to_next_vblank()}")

# Time the phases of each step.
phases = {}
presented = []


def timed(name, func):
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            phases.setdefault(name, []).append((time.perf_counter() - start) * 1000)
    return wrapper


M.flush_pending_paint = timed("paint", M.flush_pending_paint)
M.refresh_screen_cover = timed("cover", M.refresh_screen_cover)
M.show_screen_cover = timed("cover_new", M.show_screen_cover)
original_present = M.ScrollFrame._present


def present(self, move, distance=None):
    start = time.perf_counter()
    original_present(self, move, distance)
    end = time.perf_counter()
    presented.append(end)
    phases.setdefault("step", []).append((end - start) * 1000)


M.ScrollFrame._present = present

handled = []
original_flush = M.flush_pending_paint


def counting_flush(widget):
    count = original_flush(widget)
    handled.append(count)
    return count


M.flush_pending_paint = counting_flush


def scroll_frame():
    stack = [app.view_host]
    while stack:
        widget = stack.pop()
        if isinstance(widget, M.ScrollFrame) and widget.max_y_offset() > 400:
            return widget
        stack.extend(widget.winfo_children())
    return None


def pump(seconds):
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        app.update()


def report(label):
    gaps = [(b - a) * 1000 for a, b in zip(presented, presented[1:])]
    if len(gaps) < 3:
        print(f"  {label:10} too few steps ({len(presented)})")
        return
    span = presented[-1] - presented[0]
    hitches = sum(1 for g in gaps if g > frame_ms * 1.5)
    if handled:
        phases["events"] = handled
    parts = " ".join(f"{k}={statistics.mean(v):.1f}" for k, v in sorted(phases.items()))
    print(f"  {label:10} steps/s={len(gaps) / span:6.1f} gap_med={statistics.median(gaps):5.1f}ms "
          f"gap_p95={sorted(gaps)[int(len(gaps) * 0.95)]:5.1f}ms hitches={hitches:3}/{len(gaps)}  ms: {parts}")


def check_pixels(frame):
    """Compare what scrolling drew with a full repaint at the same offset."""
    if not sys.platform.startswith("win"):
        return
    from PIL import ImageGrab

    box = (frame.viewport.winfo_rootx(), frame.viewport.winfo_rooty(),
           frame.viewport.winfo_rootx() + frame.viewport.winfo_width() - 1,
           frame.viewport.winfo_rooty() + frame.viewport.winfo_height() - 1)
    pump(0.3)
    scrolled = ImageGrab.grab(bbox=box)
    M.set_window_redraw(frame.viewport, False)
    M.set_window_redraw(frame.viewport, True)
    pump(0.3)
    repainted = ImageGrab.grab(bbox=box)
    a, b = scrolled.tobytes(), repainted.tobytes()
    width = scrolled.size[0] * 3
    bad_rows = sum(1 for r in range(scrolled.size[1]) if a[r * width:(r + 1) * width] != b[r * width:(r + 1) * width])
    print(f"  pixels     rows differing from a full repaint: {bad_rows}/{scrolled.size[1]}")


def run(view):
    app.show_view(view)
    pump(0.6)
    frame = scroll_frame()
    if frame is None:
        print(f"{view}: no scrollable page")
        return
    print(f"{view}: max_offset={frame.max_y_offset():.0f}px")

    # Touchpad: small deltas every 8ms for 1.5s, down then up.
    phases.clear()
    presented.clear()
    handled.clear()
    frame.scroll_to_offsets(y=0)
    start = time.perf_counter()
    sent = 0
    while time.perf_counter() - start < 1.5:
        now = time.perf_counter() - start
        due = int(now * 1000 / 8)
        while sent < due:
            frame._direct_scroll(6 if now < 0.75 else -6)
            sent += 1
        app.update()
    pump(0.4)
    report("touchpad")
    check_pixels(frame)

    # Mouse wheel: one notch every 40ms for 1s.
    phases.clear()
    presented.clear()
    handled.clear()
    frame.scroll_to_offsets(y=0)
    for n in range(25):
        app.after(n * 40, lambda: frame._queue_wheel(frame._wheel_step_px))
    pump(1.6)
    report("wheel")
    check_pixels(frame)




def tear_check(view):
    """Record the screen while scrolling and count frames that aren't a clean
    picture of the page at a single scroll offset (torn or half drawn)."""
    if not sys.platform.startswith("win"):
        return
    import ctypes
    import struct
    import subprocess
    from PIL import ImageGrab

    ctypes.windll.user32.SetCursorPos(0, 0)
    app.show_view(view)
    pump(0.6)
    frame = scroll_frame()
    vp = frame.viewport
    x, y, w, h = vp.winfo_rootx(), vp.winfo_rooty(), vp.winfo_width(), vp.winfo_height()
    # Reference: the whole page, drawn at rest, one screenful at a time.
    rows = {}
    offset, maximum = 0, int(frame.max_y_offset())
    while True:
        frame.scroll_to_offsets(y=offset)
        pump(0.25)
        actual = int(round(vp.yview()[0] * float(vp.cget("scrollregion").split()[3])))
        data = ImageGrab.grab(bbox=(x, y, x + w, y + h)).tobytes()
        for r in range(h):
            rows[actual + r] = data[r * w * 3:(r + 1) * w * 3]
        if offset >= maximum:
            break
        offset = min(maximum, offset + h - 40)
    index = {}
    for absolute, row in rows.items():
        index.setdefault(row, []).append(absolute)
    frame.scroll_to_offsets(y=0)
    pump(0.3)
    for label, action in (("still", "none"), ("touchpad", "touch"), ("wheel", "wheel"), ("drag", "drag")):
        frame.scroll_to_offsets(y=0)
        pump(0.3)
        out = os.path.join(tempfile.gettempdir(), "frames.bin")
        here = os.path.dirname(os.path.abspath(__file__))
        proc = subprocess.Popen([sys.executable, os.path.join(here, "grab_frames.py"), str(x), str(y), str(w), str(h), "1.6", out],
                                stdout=subprocess.PIPE, text=True)
        proc.stdout.readline()
        start = time.perf_counter()
        sent = 0
        if action == "wheel":
            for n in range(25):
                app.after(n * 40, lambda: frame._queue_wheel(frame._wheel_step_px))
        if action == "drag":
            for n in range(60):
                app.after(n * 16, lambda n=n: frame._scrollbar_yview("moveto", str(n / 150)))
        while proc.poll() is None:
            if action == "touch":
                now = time.perf_counter() - start
                due = int(now * 1000 / 8)
                while sent < due and now < 1.3:
                    frame._direct_scroll(6)
                    sent += 1
            app.update()
        with open(out, "rb") as handle:
            fw, fh, count = struct.unpack("<III", handle.read(12))
            captured = []
            for _ in range(count):
                handle.read(8)
                captured.append(handle.read(fw * fh * 3))
        # Each frame's scroll offset, from the rows it shares with the page.
        offsets = []
        for data in captured:
            votes = {}
            for r in range(0, fh, 3):
                hits = index.get(data[r * fw * 3:(r + 1) * fw * 3])
                if hits and len(hits) < 4:
                    for absolute in hits:
                        votes[absolute - r] = votes.get(absolute - r, 0) + 1
            offsets.append(max(votes, key=votes.get) if votes else None)
        # Then compare each frame with the page drawn at rest at that offset.
        at_rest = {}
        for offset in sorted({o for o in offsets if o is not None}):
            frame.scroll_to_offsets(y=max(0, offset))
            pump(0.15)
            at_rest[offset] = ImageGrab.grab(bbox=(x, y, x + w, y + h)).tobytes()
        torn = 0
        worst = (0, None)
        worst_spans = ""
        for data, offset in zip(captured, offsets):
            if offset is None:
                torn += 1
                continue
            rest = at_rest[offset]
            bad_rows = [r for r in range(fh) if rest[r * fw * 3:(r + 1) * fw * 3] != data[r * fw * 3:(r + 1) * fw * 3]]
            bad = len(bad_rows)
            if bad > 2 and bad > worst[0]:
                spans, run_start = [], None
                for n, r in enumerate(bad_rows):
                    if run_start is None:
                        run_start = r
                    if n + 1 == len(bad_rows) or bad_rows[n + 1] != r + 1:
                        spans.append(f"{run_start}-{r}")
                        run_start = None
                worst_spans = ",".join(spans[:8])
            if bad > 2:
                torn += 1
                if bad > worst[0]:
                    worst = (bad, data)
        if worst[1] is not None:
            from PIL import Image
            Image.frombytes("RGB", (fw, fh), worst[1]).save(os.path.join(os.environ.get("PROBE_OUT", "."), f"{view}-{label}-worst.png"))
        print(f"  tearing    {label:8} frames={len(captured)} torn_or_half_drawn={torn} worst_bad_rows={worst[0]}/{fh} rows={worst_spans}")


for view in VIEWS:
    run(view)
    tear_check(view)
app.destroy()
