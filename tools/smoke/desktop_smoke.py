"""Desktop smoke test: open every page in both themes at two window sizes,
then run the main flows (full screen, review modes, quiz, Talk-back, study
plan, a new set). Fails on any Python error or Tk callback exception.

    xvfb-run -a python tools/smoke/desktop_smoke.py     (Linux, no screen)
    python tools/smoke/desktop_smoke.py                 (Windows or Mac)

Uses a throwaway profile, so it never touches your own cards.
"""
import os
import sys
import tempfile
import time
import traceback

os.environ["MEMORYPAL_DATA_DIR"] = tempfile.mkdtemp(prefix="mp-smoke-")
os.environ["MEMORYPAL_CAPTCHA_URL"] = ""
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "latest_app"))
import MemoryPalDesktop as M  # noqa: E402
from memorypal.models import Card  # noqa: E402

errors = []
app = M.MemoryPalApp()
app.report_callback_exception = lambda *exc: errors.append("".join(traceback.format_exception(*exc)))
app.store.onboarding = {"done": True, "persona": "student"}
app.store.add_cards([Card(deck="Biology", front=f"Question {i}?", back=f"Answer {i}") for i in range(12)])
app.store.save()


def pump(seconds=0.4):
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        app.update()
        time.sleep(0.01)


def step(name, action, wait=0.4):
    try:
        action()
        pump(wait)
        print("ok  ", name)
    except Exception:
        errors.append(name + ": " + traceback.format_exc())
        print("FAIL", name)


views = [view for view in app.page_titles() if view not in ("welcome", "signin")]
for size in ("1280x800", "900x640"):
    app.geometry(size)
    pump(0.3)
    for _theme in range(2):
        for view in views:
            # Quick clicks, as a person flicking through pages would.
            step(f"{view} ({size}, {app.theme})", lambda view=view: app.show_view(view), wait=0.25)
        app.toggle_theme()
        pump(0.2)


def full_screen_twice():
    app.toggle_true_fullscreen()
    pump(0.5)
    app.toggle_true_fullscreen()


step("full screen on and off", full_screen_twice)


def theme_twice_quickly():
    # Each change shows a notice and rebuilds the window; the second comes
    # while the first notice is still queued to hide.
    app.toggle_theme()
    pump(0.3)
    app.toggle_theme()
    pump(3.2)


step("theme changed twice quickly", theme_twice_quickly)
for mode in ("due", "quick", "weak", "new"):
    step(f"review mode {mode}", lambda mode=mode: app.start_review(mode))
step("new set", lambda: app.start_new_set("Chemistry"))
pump(3.2)  # let any notice that is still showing time out
app.destroy()
print(f"\n{len(views)} pages x 2 themes x 2 sizes; errors: {len(errors)}")
for error in errors[:10]:
    print("-----\n" + error[-1500:])
sys.exit(1 if errors else 0)
