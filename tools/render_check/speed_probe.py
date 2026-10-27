"""Measure how long the desktop app takes to start and to open each page.

python speed_probe.py [app folder ...]

With several app folders (for example this branch's latest_app and a copy of
main's), each is measured in turn, twice, on the same machine, so the
numbers can be compared directly. Different CI machines vary by half.

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


def run_once(app_dir):
    sys.path.insert(0, app_dir)
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
    profile = None
    if os.environ.get("SPEED_PROFILE") and "--first-folder" in sys.argv:
        import cProfile

        profile = cProfile.Profile()
    for view in VIEWS:
        mark = time.perf_counter()
        if profile is not None:
            profile.enable()
        app.show_view(view)
        app.update()
        if profile is not None:
            profile.disable()
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
    if profile is not None:
        # Where first visits spend their time (SPEED_PROFILE=1).
        import pstats

        stats = pstats.Stats(profile, stream=sys.stdout)
        stats.sort_stats("tottime").print_stats(15)
        stats.sort_stats("cumulative").print_stats("MemoryPalDesktop", 30)
    app.destroy()


if __name__ == "__main__":
    if "--child" in sys.argv:
        run_once(sys.argv[sys.argv.index("--child") + 1])
    else:
        folders = [os.path.abspath(arg) for arg in sys.argv[1:]] or [os.path.join(HERE, "..", "..", "latest_app")]
        print(f"platform={sys.platform}")
        for round_number in range(2 if len(folders) > 1 else 1):
            for folder in folders:
                env = dict(os.environ, MEMORYPAL_DATA_DIR=tempfile.mkdtemp(prefix="mp-speed-"))
                for label, extra in (("cold start (no saved icons)", ["--start-only"]), ("warm start", [])):
                    print(f"-- {os.path.basename(os.path.dirname(folder + os.sep)) if len(folders) == 1 else folder} round {round_number + 1}: {label}")
                    sys.stdout.flush()
                    if folder == folders[0] and round_number == 0 and not extra:
                        extra = ["--first-folder"]
                    subprocess.run([sys.executable, os.path.abspath(__file__), "--child", folder, *extra], env=env, check=False)
