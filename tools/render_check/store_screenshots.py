"""Take Microsoft Store screenshots of the desktop app with a realistic library.

python store_screenshots.py OUT_DIR [WIDTHxHEIGHT]

Fills a throwaway profile with a few decks and three weeks of reviews, opens
each main page and saves the window as a PNG (the Store wants at least
1366x768). Run it on Windows at 100% scaling so the pictures match the app
people install (the "Store screenshots" workflow does this).
"""
import os
import random
import sys
import tempfile
import time
from datetime import date, timedelta

os.environ["MEMORYPAL_DATA_DIR"] = tempfile.mkdtemp(prefix="mp-shots-")
os.environ["MEMORYPAL_CAPTCHA_URL"] = ""
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "latest_app"))
import MemoryPalDesktop as M  # noqa: E402
from memorypal.models import Card  # noqa: E402

OUT = sys.argv[1]
WIDTH, HEIGHT = (int(v) for v in (sys.argv[2] if len(sys.argv) > 2 else "1600x900").split("x"))
os.makedirs(OUT, exist_ok=True)

DECKS = {
    "Spanish Basics": [
        ("hola", "hello"), ("gracias", "thank you"), ("la biblioteca", "the library"), ("el desayuno", "breakfast"),
        ("¿Dónde está la estación?", "Where is the station?"), ("mañana", "tomorrow; morning"), ("la ventana", "the window"),
        ("aprender", "to learn"), ("el cumpleaños", "birthday"), ("despacio", "slowly"),
    ],
    "Biology": [
        ("What does the mitochondrion do?", "Releases energy from glucose (cellular respiration) as ATP."),
        ("Where does photosynthesis happen?", "In the chloroplasts of plant cells."),
        ("What carries oxygen in red blood cells?", "Haemoglobin."), ("What are the four DNA bases?", "Adenine, thymine, cytosine and guanine."),
        ("What is osmosis?", "Water moving across a membrane from a dilute to a more concentrated solution."),
        ("What do ribosomes make?", "Proteins."), ("Name the stages of mitosis.", "Prophase, metaphase, anaphase, telophase."),
    ],
    "World Capitals": [
        ("Canada", "Ottawa"), ("Australia", "Canberra"), ("Japan", "Tokyo"), ("Kenya", "Nairobi"), ("Brazil", "Brasília"),
        ("Norway", "Oslo"), ("Peru", "Lima"), ("Vietnam", "Hanoi"), ("Morocco", "Rabat"),
    ],
    "Chemistry": [
        ("Symbol for sodium", "Na"), ("pH of pure water at 25 °C", "7"), ("Avogadro's number", "6.022 × 10²³ per mole"),
        ("What is an isotope?", "Atoms of one element with different numbers of neutrons."),
        ("Most reactive group of metals", "Group 1, the alkali metals."),
    ],
}

random.seed(7)
today = date.today()
cards = []
for deck, pairs in DECKS.items():
    for n, (front, back) in enumerate(pairs):
        learned = n % 4 != 0
        interval = random.choice([1, 3, 6, 12, 25]) if learned else 0
        due = today + timedelta(days=0 if n % 3 == 0 else random.randint(1, 9))
        score = random.choice([88, 95, 100]) if learned and n % 2 else (70 if learned else 0)
        cards.append(Card(deck=deck, front=front, back=back, interval=interval, repetitions=3 if learned else 0,
                          next_review=due.isoformat(), last_result="Good" if learned else "New", last_score=score))

M.enable_dpi_awareness()
app = M.MemoryPalApp()
app.store.onboarding = {"done": True, "persona": "student"}
app.store.cards = []
app.store.add_cards(cards)
# A month of study with a couple of rest days, so Progress has a streak, a
# level and a full chart.
app.store.activity = {(today - timedelta(days=d)).isoformat(): random.randint(14, 42) for d in range(0, 31) if d not in (19, 26)}
app.store.practiced = sum(app.store.activity.values())
app.store.save(merge_existing=False)

screen_w, screen_h = app.winfo_screenwidth(), app.winfo_screenheight()
WIDTH, HEIGHT = min(WIDTH, screen_w), min(HEIGHT, screen_h - 60)
app.geometry(f"{WIDTH}x{HEIGHT}+0+0")
app.lift()
app.focus_force()


def pump(seconds):
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        app.update()
        time.sleep(0.01)


def shot(name):
    from PIL import ImageGrab

    pump(1.2)
    x, y = app.winfo_rootx(), app.winfo_rooty()
    image = ImageGrab.grab(bbox=(x, y, x + app.winfo_width(), y + app.winfo_height()))
    path = os.path.join(OUT, f"{name}.png")
    image.save(path)
    print(f"{path} {image.size[0]}x{image.size[1]}")


pump(1.0)
print(f"screen {screen_w}x{screen_h}, window {WIDTH}x{HEIGHT}")
for number, (view, name) in enumerate([
    ("dashboard", "today"),
    ("testing", "review"),
    ("study", "study"),
    ("library", "library"),
    ("stats", "progress"),
    ("create", "create"),
    ("plan", "study-plan"),
], start=1):
    app.show_view(view)
    shot(f"{number:02d}-{name}")

app.toggle_theme()  # the app starts dark; one picture in light
app.show_view("dashboard")
shot("08-today-light")
app.destroy()
