import json
from dataclasses import asdict
from datetime import date, timedelta

from . import paths
from .core import add_days, today_iso
from .models import Card, Capture, sample_cards


class MemoryStore:
    """Small JSON-backed store for cards, captures, scheduling, and progress."""

    def __init__(self):
        self.cards = []
        self.captures = []
        self.practiced = 0
        self.activity = {}
        self.daily_goal = 15
        self.nav_order = []
        self.last_action = None
        self.load()

    def load(self):
        paths.refresh_current_data_paths()
        paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
        paths.ATTACHMENT_DIR.mkdir(parents=True, exist_ok=True)
        if not paths.DATA_FILE.exists():
            self.cards = sample_cards()
            self.save()
            return
        try:
            raw = json.loads(paths.DATA_FILE.read_text(encoding="utf-8"))
            self.cards = [Card.from_dict(item) for item in raw.get("cards", [])]
            self.captures = [Capture.from_dict(item) for item in raw.get("captures", [])]
            self.practiced = int(raw.get("practiced", 0))
            self.activity = dict(raw.get("activity", {}))
            self.daily_goal = int(raw.get("daily_goal", 15))
            self.nav_order = list(raw.get("nav_order", []))
        except (OSError, json.JSONDecodeError, ValueError):
            self.cards = sample_cards()
            self.captures = []
            self.practiced = 0
            self.activity = {}
            self.daily_goal = 15
            self.nav_order = []

    def save(self):
        paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
        paths.DATA_FILE.write_text(
            json.dumps(
                {
                    "cards": [asdict(card) for card in self.cards],
                    "captures": [asdict(capture) for capture in self.captures],
                    "practiced": self.practiced,
                    "activity": self.activity,
                    "daily_goal": self.daily_goal,
                    "nav_order": self.nav_order,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def log_activity(self, count=1):
        key = today_iso()
        self.activity[key] = self.activity.get(key, 0) + count

    def today_count(self):
        return self.activity.get(today_iso(), 0)

    def current_streak(self):
        streak = 0
        cursor = date.today()
        if self.activity.get(cursor.isoformat(), 0) <= 0:
            cursor -= timedelta(days=1)
        while self.activity.get(cursor.isoformat(), 0) > 0:
            streak += 1
            cursor -= timedelta(days=1)
        return streak

    def heatmap_weeks(self, weeks=18):
        end = date.today()
        start = end - timedelta(days=weeks * 7 - 1)
        start -= timedelta(days=start.weekday() + 1 if start.weekday() != 6 else 0)
        days = []
        cursor = start
        while cursor <= end:
            days.append((cursor.isoformat(), self.activity.get(cursor.isoformat(), 0)))
            cursor += timedelta(days=1)
        columns = []
        column = []
        for iso_day, count in days:
            column.append((iso_day, count))
            if len(column) == 7:
                columns.append(column)
                column = []
        if column:
            while len(column) < 7:
                column.append(("", -1))
            columns.append(column)
        return columns

    def decks(self):
        names = []
        for card in self.cards:
            name = card.deck or "General"
            if name not in names:
                names.append(name)
        return sorted(names, key=str.lower)

    def deck_summary(self):
        summary = {}
        for deck in self.decks():
            cards = [card for card in self.cards if (card.deck or "General") == deck]
            due = len([card for card in cards if card.next_review <= today_iso()])
            weak = len([card for card in cards if card.lapses > 0 or card.last_score < 64 or card.repetitions == 0])
            mastered = len([card for card in cards if card.last_score >= 82])
            summary[deck] = {
                "total": len(cards),
                "due": due,
                "weak": weak,
                "mastery": round(mastered / len(cards) * 100) if cards else 0,
            }
        return summary

    def due_cards(self, deck=None):
        cards = [card for card in self.cards if card.next_review <= today_iso() and card.buried_until <= today_iso()]
        if deck:
            cards = [card for card in cards if (card.deck or "General") == deck]
        return cards

    def bury_card(self, card, days=1):
        card.buried_until = add_days(days)
        self.save()

    def is_leech(self, card):
        return card.lapses >= 8

    def leech_count(self, deck=None):
        cards = self.cards if not deck else [card for card in self.cards if (card.deck or "General") == deck]
        return len([card for card in cards if self.is_leech(card)])

    def upcoming_cards(self):
        return sorted([card for card in self.cards if card.next_review > today_iso()], key=lambda card: card.next_review)

    def weak_cards(self):
        scored = [
            card for card in self.cards
            if card.lapses > 0 or card.last_score < 64 or card.repetitions == 0
        ]
        return sorted(scored, key=lambda card: (-card.lapses, card.last_score, card.next_review, card.front.lower()))

    def add_card(self, card):
        self.cards.insert(0, card)
        self.save()

    def add_capture(self, capture):
        self.captures.insert(0, capture)
        self.save()

    def schedule(self, card, quality, assessment=None):
        snapshot = asdict(card)
        activity_key = today_iso()
        if quality < 3:
            card.repetitions = 0
            card.interval = 1
            card.lapses += 1
        else:
            if card.repetitions == 0:
                card.interval = 1
            elif card.repetitions == 1:
                card.interval = 3
            else:
                card.interval = max(1, round(card.interval * card.ease))
            card.repetitions += 1
        card.ease = max(1.3, card.ease + (0.1 - (5 - quality) * 0.08))
        card.next_review = add_days(card.interval)
        if assessment:
            card.last_score = int(assessment.get("score", 0))
            card.last_result = assessment.get("label", "Checked")
        else:
            card.last_score = {1: 20, 2: 35, 3: 55, 4: 78, 5: 95}.get(quality, 0)
            card.last_result = {1: "Again", 2: "Weak", 3: "Review", 4: "Good", 5: "Easy"}.get(quality, "Checked")
        self.practiced += 1
        self.log_activity()
        self.last_action = {"card_id": card.id, "snapshot": snapshot, "activity_key": activity_key, "practiced_before": self.practiced - 1}
        self.save()

    def undo_last(self):
        action = self.last_action
        if not action:
            return False
        card = next((c for c in self.cards if c.id == action["card_id"]), None)
        if not card:
            return False
        for key, value in action["snapshot"].items():
            setattr(card, key, value)
        self.practiced = action["practiced_before"]
        key = action["activity_key"]
        if self.activity.get(key, 0) > 0:
            self.activity[key] -= 1
            if self.activity[key] <= 0:
                del self.activity[key]
        self.last_action = None
        self.save()
        return True

    def reset(self):
        self.cards = sample_cards()
        self.captures = []
        self.practiced = 0
        self.activity = {}
        self.daily_goal = 15
        self.nav_order = []
        self.last_action = None
        self.save()
