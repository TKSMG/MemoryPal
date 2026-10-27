"""Measure how long the desktop app takes to start and to open each page.

python speed_probe.py

Starts the app twice on the same data folder (the second start finds the
icons the first one saved), then opens each page: the first visit, and the
fastest of three later visits. Also times building a quiz round. Prints
milliseconds; lower is better. Run on slow machines to see what people with
older computers feel.
"""
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
VIEWS = ["dashboard", "stats", "library", "settings", "decks", "plan", "focus", "training", "games", "capture", "review"]


def run_once():
    sys.path.insert(0, os.path.join(HERE, "..", "..", "latest_app"))
    started = time.perf_counter()
    import MemoryPalDesktop as M
    from memorypal.models import Card

    imported = time.perf_counter()
    M.enable_dpi_awareness()
    app = M.MemoryPalApp()
    app.store.onboarding = {"done": True, "persona": "student"}
    app.update()
    ready = time.perf_counter()
    print(f"start: import={1000 * (imported - started):.0f} window={1000 * (ready - imported):.0f}")

    app.store.add_cards([Card(deck=f"Deck {n % 6}", front=f"Question number {n} about something long enough to wrap",
                              back=f"Answer {n} " * 6) for n in range(300)])
    app.geometry("1280x900+0+0")
    app.update()
    if "--start-only" in sys.argv:
        if hasattr(app, "save_icon_cache"):  # older versions keep no icons
            app.save_icon_cache()
        app.destroy()
        return

    first, later = {}, {}
    for view in VIEWS:
        mark = time.perf_counter()
        app.show_view(view)
        app.update()
        first[view] = 1000 * (time.perf_counter() - mark)
    for _ in range(3):
        for view in VIEWS:
            mark = time.perf_counter()
            app.show_view(view)
            app.update()
            later[view] = min(later.get(view, 1e9), 1000 * (time.perf_counter() - mark))
    print("first visit: " + " ".join(f"{view}={first[view]:.0f}" for view in VIEWS))
    print("later visit: " + " ".join(f"{view}={later[view]:.0f}" for view in VIEWS))
    rounds = []
    for _ in range(5):
        mark = time.perf_counter()
        app.new_quiz_round()
        rounds.append(1000 * (time.perf_counter() - mark))
    print(f"quiz round: first={rounds[0]:.0f} best={min(rounds):.0f}")
    print(f"page total: first={sum(first.values()):.0f} later={sum(later.values()):.0f}")
    app.destroy()


if __name__ == "__main__":
    if "--child" in sys.argv:
        run_once()
    else:
        env = dict(os.environ, MEMORYPAL_DATA_DIR=tempfile.mkdtemp(prefix="mp-speed-"))
        print(f"platform={sys.platform}")
        for label, extra in (("cold start (no saved icons)", ["--start-only"]), ("warm start", [])):
            print(f"-- {label}")
            sys.stdout.flush()
            subprocess.run([sys.executable, os.path.abspath(__file__), "--child", *extra], env=env, check=False)
