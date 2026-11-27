"""Watch the whole screen while the desktop app starts (Windows).

python launch_probe.py [rounds]

Starts MemoryPalDesktop.py as people do, in its own process, and grabs the
screen as fast as it can from just before the launch until the first page
has been up for a while. Each start is checked for frames that show a big
bright (white or near white) area that was not on the desktop before: the
white flash some people see when the app opens. Starts are run on a new
data folder (first start: no profile and no saved icons) and again on the
same folder (a later start).

Prints, per start: frames grabbed, when the app's dark page first showed,
and the worst bright area (share of the screen) with its time and box.
Exits 1 if any start showed a flash.
"""
import os
import subprocess
import sys
import tempfile
import time

import mss
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "..", "..", "latest_app", "MemoryPalDesktop.py")
STEP = 6  # sample every 6th pixel each way
BRIGHT = 215  # every channel at least this: white or near white
FLASH_SHARE = 0.01  # 1% of the screen more than the desktop showed
OUT = os.environ.get("LAUNCH_PROBE_OUT", os.path.join(tempfile.gettempdir(), "launch-probe"))


def bright_mask(shot):
    raw = shot.rgb
    width, height = shot.width, shot.height
    mask = []
    for y in range(0, height, STEP):
        row = y * width * 3
        for x in range(0, width, STEP):
            i = row + x * 3
            mask.append(raw[i] >= BRIGHT and raw[i + 1] >= BRIGHT and raw[i + 2] >= BRIGHT)
    return mask


def dark_page_share(shot, colour=(0x14, 0x14, 0x13), tolerance=10):
    raw = shot.rgb
    width, height = shot.width, shot.height
    hits = total = 0
    for y in range(0, height, STEP * 2):
        row = y * width * 3
        for x in range(0, width, STEP * 2):
            i = row + x * 3
            total += 1
            if all(abs(raw[i + k] - colour[k]) <= tolerance for k in range(3)):
                hits += 1
    return hits / max(1, total)


def run(label, data_dir, seconds=float(os.environ.get("LAUNCH_PROBE_SECONDS", "9")), env_extra=None):
    with mss.mss() as grabber:
        monitor = grabber.monitors[1]
        before = grabber.grab(monitor)
        base = bright_mask(before)
        cols = len(range(0, before.width, STEP))
        env = dict(os.environ, MEMORYPAL_DATA_DIR=data_dir, MEMORYPAL_CAPTCHA_URL="", **(env_extra or {}))
        started = time.perf_counter()
        exe = os.environ.get("LAUNCH_PROBE_EXE")
        child = subprocess.Popen([exe] if exe else [sys.executable, APP], env=env)
        frames = []
        while time.perf_counter() - started < seconds:
            shot = grabber.grab(monitor)
            frames.append((time.perf_counter() - started, shot))
        child.terminate()
        try:
            child.wait(5)
        except subprocess.TimeoutExpired:
            child.kill()
    worst = (0.0, None, None, None)
    first_page = None
    timeline = []
    for index, (moment, shot) in enumerate(frames):
        mask = bright_mask(shot)
        extra = [i for i, (now, was) in enumerate(zip(mask, base)) if now and not was]
        share = len(extra) / max(1, len(mask))
        page = dark_page_share(shot)
        if first_page is None and page > 0.05:
            first_page = moment
        timeline.append(f"{moment:.2f}:{100 * share:.1f}/{100 * page:.0f}")
        if share > worst[0]:
            xs = [(i % cols) * STEP for i in extra]
            ys = [(i // cols) * STEP for i in extra]
            worst = (share, moment, (min(xs), min(ys), max(xs), max(ys)), index)
    flashed = worst[0] >= FLASH_SHARE
    box = worst[2]
    print(f"{label:28} frames={len(frames):4} page_at={first_page if first_page is None else round(first_page, 2)}s "
          f"worst_bright={100 * worst[0]:.1f}% at={worst[1] and round(worst[1], 2)}s box={box} {'FLASH' if flashed else 'ok'}")
    # Bright share / dark page share (percent) per frame around the page's arrival.
    if first_page is not None:
        near = [entry for entry, (moment, _shot) in zip(timeline, frames) if first_page - 1.0 <= moment <= first_page + 1.5]
        print("   ", " ".join(near))
    os.makedirs(OUT, exist_ok=True)
    if worst[3] is not None:
        for name, index in (("worst", worst[3]), ("before", max(0, worst[3] - 1)), ("after", min(len(frames) - 1, worst[3] + 1))):
            shot = frames[index][1]
            Image.frombytes("RGB", shot.size, shot.rgb).save(os.path.join(OUT, f"{label.replace(' ', '_')}-{name}.png"))
    sys.stdout.flush()
    return flashed


def hog():
    while True:
        pass


def main():
    busy = int(os.environ.get("LAUNCH_PROBE_BUSY", "0") or 0)
    if busy:
        # Keep every core busy, as a slow or freshly booted PC is, so the
        # app's start stretches out the way it does there.
        import multiprocessing

        for _ in range(busy * (os.cpu_count() or 2)):
            multiprocessing.Process(target=hog, daemon=True).start()
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    env_extra = {}
    for item in os.environ.get("LAUNCH_PROBE_ENV", "").split(","):
        if "=" in item:
            key, value = item.split("=", 1)
            env_extra[key.strip()] = value.strip()
    flashes = 0
    for number in range(1, rounds + 1):
        data_dir = tempfile.mkdtemp(prefix="mp-launch-")
        flashes += run(f"round {number} first start", data_dir, env_extra=env_extra)
        flashes += run(f"round {number} later start", data_dir, env_extra=env_extra)
    print(f"starts with a flash: {flashes} of {2 * rounds}")
    return 1 if flashes else 0


if __name__ == "__main__":
    raise SystemExit(main())
