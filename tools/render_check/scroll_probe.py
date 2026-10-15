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
MODE = os.environ.get("SCROLL_MODE", "current")

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
print(f"mode={MODE} platform={sys.platform} refresh={hz:.0f}Hz frame={frame_ms:.1f}ms tk={app.tk.call('info', 'patchlevel')}")

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


def present(self, move):
    start = time.perf_counter()
    original_present(self, move)
    end = time.perf_counter()
    presented.append(end)
    phases.setdefault("step", []).append((end - start) * 1000)


M.ScrollFrame._present = present

if MODE in ("nocover", "scrollwindow"):
    M.show_screen_cover = lambda *a, **k: None

if MODE == "scrollwindow" and sys.platform.startswith("win"):
    import ctypes

    user32 = ctypes.windll.user32
    original_scroll = M.ScrollFrame._scroll_pixels

    def scroll_pixels(self, pixels, axis="y"):
        if axis != "y":
            return original_scroll(self, pixels, axis)
        region = self.viewport.cget("scrollregion").split()
        total = float(region[3])
        maximum = max(0.0, total - self.viewport.winfo_height())
        current = round(self.viewport.yview()[0] * total)
        target = int(round(max(0.0, min(maximum, current + float(pixels)))))
        dy = target - current
        if not dy:
            return

        def move():
            # Blit what's already drawn and move the content window with it;
            # only the strip that scrolls into view is invalidated.
            user32.ScrollWindowEx(self.viewport.winfo_id(), 0, -dy, None, None, None, None, 0x0001 | 0x0002)
            self.viewport.yview_moveto(target / total)

        self._present(move)

    M.ScrollFrame._scroll_pixels = scroll_pixels

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
        phases["events"] = handled[-len(gaps):]
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
            frame._queue_wheel(6 if now < 0.75 else -6)
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


for view in VIEWS:
    run(view)
app.destroy()
