import json
import os
import time
from dataclasses import asdict
from datetime import date, timedelta

from . import paths
from .core import add_days, today_iso
from .models import Card, Capture, FeedbackEntry, sample_cards


def safe_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def load_items(raw_items, factory):
    items = []
    for raw in raw_items or []:
        if not isinstance(raw, dict):
            continue
        try:
            items.append(factory(raw))
        except (TypeError, ValueError, AttributeError):
            continue
    return items


def default_payload():
    return {
        "cards": [],
        "captures": [],
        "practiced": 0,
        "activity": {},
        "daily_goal": 15,
        "nav_order": [],
        "feedback": [],
    }


def read_payload(path):
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else default_payload()
    except (OSError, json.JSONDecodeError):
        return default_payload()


def atomic_write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temp_path, path)


class DataFileLock:
    """Tiny local lock so two open MemoryPal windows do not save at the same instant."""

    def __init__(self, target, timeout=2.0, stale_after=12.0):
        self.path = target.with_suffix(target.suffix + ".lock")
        self.timeout = timeout
        self.stale_after = stale_after
        self.handle = None
        self.acquired = False

    def __enter__(self):
        start = time.monotonic()
        while True:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self.handle = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(self.handle, str(os.getpid()).encode("ascii", "ignore"))
                self.acquired = True
                return self
            except FileExistsError:
                try:
                    if time.time() - self.path.stat().st_mtime > self.stale_after:
                        self.path.unlink()
                        continue
                except OSError:
                    pass
                if time.monotonic() - start >= self.timeout:
                    return self
                time.sleep(0.05)

    def __exit__(self, _exc_type, _exc, _tb):
        if self.handle is not None:
            try:
                os.close(self.handle)
            except OSError:
                pass
        if self.acquired:
            try:
                self.path.unlink()
            except OSError:
                pass


class MemoryStore:
    """Small JSON-backed store for cards, captures, scheduling, and progress."""

    def __init__(self):
        self.profile_name = paths.active_profile_name()
        self.data_file = None
        self.attachment_dir = None
        self.cards = []
        self.captures = []
        self.practiced = 0
        self.activity = {}
        self.daily_goal = 15
        self.nav_order = []
        self.feedback = []
        self.last_action = None
        self._loaded_practiced = 0
        self._loaded_activity = {}
        self._loaded_daily_goal = 15
        self._loaded_nav_order = []
        self.load()

    def set_profile_paths(self):
        directory = paths.profile_dir(self.profile_name)
        self.data_file = directory / "memorypal-data.json"
        self.attachment_dir = directory / "attachments"

    def load(self):
        self.set_profile_paths()
        paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.attachment_dir.mkdir(parents=True, exist_ok=True)
        if not self.data_file.exists():
            self.cards = sample_cards()
            self.save(merge_existing=False)
            return
        try:
            raw = read_payload(self.data_file)
            self.cards = load_items(raw.get("cards", []), Card.from_dict)
            self.captures = load_items(raw.get("captures", []), Capture.from_dict)
            self.practiced = safe_int(raw.get("practiced", 0), 0)
            self.activity = dict(raw.get("activity", {}))
            self.daily_goal = safe_int(raw.get("daily_goal", 15), 15)
            self.nav_order = list(raw.get("nav_order", []))
            self.feedback = load_items(raw.get("feedback", []), FeedbackEntry.from_dict)
        except (OSError, json.JSONDecodeError, ValueError):
            self.cards = sample_cards()
            self.captures = []
            self.practiced = 0
            self.activity = {}
            self.daily_goal = 15
            self.nav_order = []
            self.feedback = []
        self.remember_loaded_state()

    def remember_loaded_state(self):
        self._loaded_practiced = self.practiced
        self._loaded_activity = dict(self.activity)
        self._loaded_daily_goal = self.daily_goal
        self._loaded_nav_order = list(self.nav_order)

    def payload(self):
        return {
            "cards": [asdict(card) for card in self.cards],
            "captures": [asdict(capture) for capture in self.captures],
            "practiced": self.practiced,
            "activity": self.activity,
            "daily_goal": self.daily_goal,
            "nav_order": self.nav_order,
            "feedback": [asdict(entry) for entry in self.feedback],
        }

    def merge_items(self, local_items, existing_items):
        local_by_id = {item.get("id"): item for item in local_items if isinstance(item, dict) and item.get("id")}
        merged = [item for item in local_items if isinstance(item, dict)]
        seen = {item.get("id") for item in merged if item.get("id")}
        for item in existing_items or []:
            item_id = item.get("id") if isinstance(item, dict) else None
            if item_id and item_id not in seen:
                merged.append(item)
                seen.add(item_id)
            elif item_id in local_by_id:
                continue
        return merged

    def merge_activity(self, existing_activity):
        merged = dict(existing_activity or {})
        keys = set(merged) | set(self.activity) | set(self._loaded_activity)
        for key in keys:
            existing_count = safe_int(merged.get(key, 0), 0)
            loaded_count = safe_int(self._loaded_activity.get(key, 0), 0)
            local_count = safe_int(self.activity.get(key, 0), 0)
            delta = max(0, local_count - loaded_count)
            count = max(existing_count, loaded_count) + delta
            if count > 0:
                merged[key] = count
            elif key in merged:
                del merged[key]
        return merged

    def merge_payload(self, existing, local):
        if not existing:
            return local
        merged = dict(local)
        merged["cards"] = self.merge_items(local.get("cards", []), existing.get("cards", []))
        merged["captures"] = self.merge_items(local.get("captures", []), existing.get("captures", []))
        merged["feedback"] = self.merge_items(local.get("feedback", []), existing.get("feedback", []))
        practiced_delta = max(0, safe_int(local.get("practiced", 0), 0) - self._loaded_practiced)
        merged["practiced"] = max(safe_int(existing.get("practiced", 0), 0), self._loaded_practiced) + practiced_delta
        merged["activity"] = self.merge_activity(existing.get("activity", {}))
        if self.daily_goal == self._loaded_daily_goal:
            merged["daily_goal"] = safe_int(existing.get("daily_goal", self.daily_goal), self.daily_goal)
        if self.nav_order == self._loaded_nav_order:
            merged["nav_order"] = list(existing.get("nav_order", self.nav_order))
        return merged

    def apply_saved_payload(self, payload):
        self.cards = load_items(payload.get("cards", []), Card.from_dict)
        self.captures = load_items(payload.get("captures", []), Capture.from_dict)
        self.practiced = safe_int(payload.get("practiced", 0), 0)
        self.activity = dict(payload.get("activity", {}))
        self.daily_goal = safe_int(payload.get("daily_goal", 15), 15)
        self.nav_order = list(payload.get("nav_order", []))
        self.feedback = load_items(payload.get("feedback", []), FeedbackEntry.from_dict)
        self.remember_loaded_state()

    def save(self, merge_existing=True):
        paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.set_profile_paths()
        self.attachment_dir.mkdir(parents=True, exist_ok=True)
        local = self.payload()
        with DataFileLock(self.data_file):
            payload = self.merge_payload(read_payload(self.data_file), local) if merge_existing else local
            atomic_write_json(self.data_file, payload)
        self.apply_saved_payload(payload)

    def add_feedback(self, rating, category, page, note):
        entry = FeedbackEntry(rating=rating, category=category, page=page, note=note)
        self.feedback.insert(0, entry)
        self.save()
        return entry

    def feedback_summary(self):
        rated = [entry.rating for entry in self.feedback if entry.rating > 0]
        average = round(sum(rated) / len(rated), 1) if rated else 0
        categories = {}
        for entry in self.feedback:
            categories[entry.category] = categories.get(entry.category, 0) + 1
        return {
            "total": len(self.feedback),
            "average": average,
            "categories": categories,
            "latest": self.feedback[0].created_at if self.feedback else "None yet",
        }

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
        self.feedback = []
        self.last_action = None
        self.save(merge_existing=False)
