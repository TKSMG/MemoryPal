"""Write the desktop's notification plans for the phone's parity test.

    python tools\\parity\\make_notification_fixtures.py

mobile/__tests__/notifications.parity.test.ts loads each store, pins the
clock to the day this ran, and expects the same notifications from
mobile/src/features/notifications.ts. Kept apart from parity.json so the
study plan fixtures can be regenerated without touching these.
"""

import json
import os
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

os.environ["MEMORYPAL_DATA_DIR"] = tempfile.mkdtemp(prefix="memorypal-parity-")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "latest_app"))

from memorypal import notifications  # noqa: E402
from memorypal.models import Capture, Card, DeckInfo  # noqa: E402
from memorypal.store import MemoryStore  # noqa: E402

OUT = ROOT / "mobile" / "__tests__" / "fixtures" / "notifications.json"
TODAY = date.today()


def on(offset):
    return (TODAY + timedelta(days=offset)).isoformat()


def cards(specs):
    made = []
    for index, (deck, due, reps, score, lapses) in enumerate(specs):
        card = Card(id=f"c{index}", deck=deck, front=f"Question {index}", back=f"Answer {index}", repetitions=reps, last_score=score, lapses=lapses)
        card.next_review = on(due)
        made.append(card)
    return made


def scenario(name, store, settings, hour=9):
    start = datetime(TODAY.year, TODAY.month, TODAY.day, hour, 0)
    planned = notifications.plan_notifications(store, settings, start=start)
    return {
        "name": name,
        "store": json.loads(json.dumps(store.payload(), default=str)),
        "settings": settings,
        "start": start.strftime("%Y-%m-%dT%H:%M"),
        "expected": [{**entry, "at": entry["at"].strftime("%Y-%m-%dT%H:%M")} for entry in planned],
    }


def fresh():
    store = MemoryStore()
    store.reset()
    return store


def main():
    every = {"enabled": True, "kinds": list(notifications.KINDS), "quiet": "off"}
    cases = []

    store = fresh()
    store.cards = cards([("Biology", -3, 0, 0, 0), ("Biology", 0, 2, 70, 0), ("History", 2, 4, 90, 0), ("History", 5, 1, 40, 2)])
    store.activity = {on(-1): 6, on(-2): 4, on(-3): 9, on(-5): 2}
    store.deck_infos = [DeckInfo(id="History", exam_date=on(3)), DeckInfo(id="Biology", exam_date=on(7))]
    store.captures = [Capture(id="n1", title="Chapter 3", notes="Cells make energy in mitochondria.\nPlants use light.", deck="Cells")]
    cases.append(scenario("everything on", store, every))
    cases.append(scenario("quiet evenings, one a day", store, {**every, "quiet": "21:00-08:00", "one_a_day": True, "time": "08:00"}, hour=7))
    cases.append(scenario("only cards and streak, evening start", store, {**every, "kinds": ["cards_due", "streak"], "time": "21:00"}, hour=20))

    store = fresh()
    store.cards = cards([("Spanish", 0, 0, 0, 0) for _ in range(6)] + [("Spanish", 4, 3, 85, 0)])
    store.activity = {on(0): 3, on(-1): 5}
    store.set_study_plan({"unit": "minutes", "amount": "30", "deck": "All decks", "goal_label": "Long-term retention", "habits": ["breaks", "games"]})
    cases.append(scenario("minute plan, studied today", store, every))

    store = fresh()
    store.cards = cards([("Law", offset % 4, 0, 0, 0) for offset in range(12)])
    store.set_study_plan({"unit": "days", "amount": "5", "deck": "Law", "goal_label": "Exam prep", "habits": ["mnemonics", "repetition"]})
    steps = notifications._plan_days(store, TODAY, 1)[on(0)]
    store.toggle_plan_step(0, on(0), steps)
    cases.append(scenario("five-day plan under way", store, {**every, "time": "13:00", "quiet": "22:00-07:00"}))

    store = fresh()
    store.captures = [Capture(id="n2", title="Week 1 lecture", notes="The heart has four chambers.")]
    store.activity = {on(-offset): offset + 1 for offset in range(1, 9)}
    cases.append(scenario("notes and recap only", store, {**every, "kinds": ["notes_waiting", "weekly_recap", "streak"]}))

    OUT.write_text(json.dumps({"made_on": TODAY.isoformat(), "cases": cases}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(cases)} cases to {OUT}")


if __name__ == "__main__":
    main()
