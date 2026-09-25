import json
import os
import time
from dataclasses import asdict
from datetime import date, timedelta

from . import paths
from .core import add_days, now_label, today_iso
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
        "accessibility": default_accessibility(),
        "feedback": [],
        "onboarding": default_onboarding(),
        "study_plan": {},
    }


def normalize_study_plan(raw):
    """A saved plan: the choices it was built from, when, and ticked-off steps."""
    if not isinstance(raw, dict) or not isinstance(raw.get("settings"), dict):
        return {}
    done = raw.get("done") if isinstance(raw.get("done"), dict) else {}
    return {
        "settings": dict(raw["settings"]),
        "created": str(raw.get("created") or today_iso()),
        "done": {str(day): sorted({int(index) for index in indexes if str(index).isdigit()}) for day, indexes in done.items() if isinstance(indexes, list)},
    }


PERSONAS = ("student", "everyday", "caregiver", "general")


def default_onboarding(done=False):
    return {"done": done, "persona": ""}


def normalize_onboarding(raw):
    # Data saved before onboarding existed belongs to people already using
    # the app, so a missing record counts as done rather than interrupting.
    if not isinstance(raw, dict):
        return default_onboarding(done=True)
    persona = raw.get("persona", "")
    return {"done": bool(raw.get("done", True)), "persona": persona if persona in PERSONAS else ""}


def default_accessibility():
    return {
        "text_size": "Comfort",
        "high_contrast": False,
        "reduce_motion": False,
        "simple_language": False,
        "caregiver_mode": False,
        "read_aloud": False,
        "more_time": False,
        "focus_outline": False,
    }


ACCESSIBILITY_TOGGLES = (
    "high_contrast", "reduce_motion", "simple_language", "caregiver_mode",
    "read_aloud", "more_time", "focus_outline",
)


def normalize_accessibility(raw):
    prefs = default_accessibility()
    if isinstance(raw, dict):
        prefs.update({
            key: raw.get(key, value)
            for key, value in prefs.items()
        })
    if prefs["text_size"] not in ("Comfort", "Large", "Extra Large"):
        prefs["text_size"] = "Comfort"
    for key in ACCESSIBILITY_TOGGLES:
        prefs[key] = bool(prefs.get(key, False))
    return prefs


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
        self.accessibility = default_accessibility()
        self.feedback = []
        self.onboarding = default_onboarding()
        self.study_plan = {}
        self.last_action = None
        self._file_stamp = None
        self._loaded_onboarding = default_onboarding()
        self._loaded_practiced = 0
        self._loaded_activity = {}
        self._loaded_daily_goal = 15
        self._loaded_nav_order = []
        self._loaded_accessibility = default_accessibility()
        self._loaded_cards = {}
        self._loaded_captures = {}
        self._loaded_feedback = {}
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
            self.accessibility = normalize_accessibility(raw.get("accessibility", {}))
            self.feedback = load_items(raw.get("feedback", []), FeedbackEntry.from_dict)
            self.onboarding = normalize_onboarding(raw.get("onboarding"))
            self.study_plan = normalize_study_plan(raw.get("study_plan"))
            self._file_stamp = self.file_stamp()
        except (OSError, json.JSONDecodeError, ValueError):
            self.cards = sample_cards()
            self.captures = []
            self.practiced = 0
            self.activity = {}
            self.daily_goal = 15
            self.nav_order = []
            self.accessibility = default_accessibility()
            self.feedback = []
        self.remember_loaded_state()

    def remember_loaded_state(self, payload=None):
        self._loaded_practiced = self.practiced
        self._loaded_activity = dict(self.activity)
        self._loaded_daily_goal = self.daily_goal
        self._loaded_nav_order = list(self.nav_order)
        self._loaded_accessibility = dict(self.accessibility)
        self._loaded_onboarding = dict(self.onboarding)
        self._loaded_study_plan = normalize_study_plan(self.study_plan)
        if payload is None:
            self._loaded_cards = self.item_snapshot(self.cards)
            self._loaded_captures = self.item_snapshot(self.captures)
            self._loaded_feedback = self.item_snapshot(self.feedback)
        else:
            self._loaded_cards = self.raw_snapshot(payload.get("cards"))
            self._loaded_captures = self.raw_snapshot(payload.get("captures"))
            self._loaded_feedback = self.raw_snapshot(payload.get("feedback"))

    @staticmethod
    def raw_snapshot(raw_items):
        return {item["id"]: item for item in raw_items or [] if isinstance(item, dict) and item.get("id")}

    @staticmethod
    def item_snapshot(items):
        snapshot = {}
        for item in items:
            raw = asdict(item)
            item_id = raw.get("id")
            if item_id:
                snapshot[item_id] = raw
        return snapshot

    def payload(self):
        return {
            "cards": [asdict(card) for card in self.cards],
            "captures": [asdict(capture) for capture in self.captures],
            "practiced": self.practiced,
            "activity": self.activity,
            "daily_goal": self.daily_goal,
            "nav_order": self.nav_order,
            "accessibility": dict(self.accessibility),
            "feedback": [asdict(entry) for entry in self.feedback],
            "onboarding": dict(self.onboarding),
            "study_plan": normalize_study_plan(self.study_plan),
        }

    def merge_items(self, local_items, existing_items, loaded_items=None):
        loaded_items = loaded_items or {}
        existing_by_id = {
            item.get("id"): item
            for item in existing_items or []
            if isinstance(item, dict) and item.get("id")
        }
        merged = []
        seen = set()
        for item in local_items:
            if not isinstance(item, dict):
                continue
            item_id = item.get("id")
            existing_item = existing_by_id.get(item_id)
            loaded_item = loaded_items.get(item_id)
            if item_id and existing_item is not None and loaded_item is not None and item == loaded_item and existing_item != loaded_item:
                merged.append(existing_item)
            else:
                merged.append(item)
            if item_id:
                seen.add(item_id)
        for item in existing_items or []:
            item_id = item.get("id") if isinstance(item, dict) else None
            if item_id and item_id not in seen:
                merged.append(item)
                seen.add(item_id)
        return merged

    def merge_activity(self, existing_activity):
        # Apply this window's change (which can be negative after an undo)
        # on top of whatever another window saved in the meantime.
        merged = dict(existing_activity or {})
        keys = set(merged) | set(self.activity) | set(self._loaded_activity)
        for key in keys:
            existing_count = safe_int(merged.get(key, 0), 0)
            loaded_count = safe_int(self._loaded_activity.get(key, 0), 0)
            local_count = safe_int(self.activity.get(key, 0), 0)
            count = existing_count + local_count - loaded_count
            if count > 0:
                merged[key] = count
            elif key in merged:
                del merged[key]
        return merged

    def merge_payload(self, existing, local):
        if not existing:
            return local
        merged = dict(local)
        merged["cards"] = self.merge_items(local.get("cards", []), existing.get("cards", []), self._loaded_cards)
        merged["captures"] = self.merge_items(local.get("captures", []), existing.get("captures", []), self._loaded_captures)
        merged["feedback"] = self.merge_items(local.get("feedback", []), existing.get("feedback", []), self._loaded_feedback)
        practiced_delta = safe_int(local.get("practiced", 0), 0) - self._loaded_practiced
        merged["practiced"] = max(0, safe_int(existing.get("practiced", 0), 0) + practiced_delta)
        merged["activity"] = self.merge_activity(existing.get("activity", {}))
        if self.daily_goal == self._loaded_daily_goal:
            merged["daily_goal"] = safe_int(existing.get("daily_goal", self.daily_goal), self.daily_goal)
        if self.nav_order == self._loaded_nav_order:
            merged["nav_order"] = list(existing.get("nav_order", self.nav_order))
        if self.accessibility == self._loaded_accessibility:
            merged["accessibility"] = normalize_accessibility(existing.get("accessibility", self.accessibility))
        if self.onboarding == self._loaded_onboarding and "onboarding" in existing:
            merged["onboarding"] = normalize_onboarding(existing.get("onboarding"))
        if normalize_study_plan(self.study_plan) == self._loaded_study_plan and "study_plan" in existing:
            merged["study_plan"] = normalize_study_plan(existing.get("study_plan"))
        return merged

    @staticmethod
    def rebind_items(current, raw_items, factory):
        """Load saved items, reusing the existing object for each known id.

        The UI keeps references to cards (a quiz round, the card open in Test
        Lab, the card selected in Cue Lab). Replacing every object on save
        left those references detached, so later ratings or cues written to
        them were silently dropped on the next save.
        """
        live = {item.id: item for item in current}
        items = []
        for fresh in load_items(raw_items, factory):
            existing = live.get(fresh.id)
            if existing is not None:
                existing.__dict__.update(fresh.__dict__)
                items.append(existing)
            else:
                items.append(fresh)
        return items

    def apply_saved_payload(self, payload):
        self.cards = self.rebind_items(self.cards, payload.get("cards", []), Card.from_dict)
        self.captures = self.rebind_items(self.captures, payload.get("captures", []), Capture.from_dict)
        self.practiced = safe_int(payload.get("practiced", 0), 0)
        self.activity = dict(payload.get("activity", {}))
        self.daily_goal = safe_int(payload.get("daily_goal", 15), 15)
        self.nav_order = list(payload.get("nav_order", []))
        self.accessibility = normalize_accessibility(payload.get("accessibility", {}))
        self.feedback = load_items(payload.get("feedback", []), FeedbackEntry.from_dict)
        self.onboarding = normalize_onboarding(payload.get("onboarding"))
        self.study_plan = normalize_study_plan(payload.get("study_plan"))
        self.remember_loaded_state()

    def file_stamp(self):
        try:
            stat = self.data_file.stat()
            return (stat.st_mtime_ns, stat.st_size)
        except OSError:
            return None

    def save(self, merge_existing=True):
        paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.set_profile_paths()
        self.attachment_dir.mkdir(parents=True, exist_ok=True)
        local = self.payload()
        with DataFileLock(self.data_file):
            # Only merge when another window has written since our last
            # load/save; otherwise the file is exactly what we last wrote.
            external = merge_existing and self.file_stamp() != self._file_stamp
            payload = self.merge_payload(read_payload(self.data_file), local) if external else local
            atomic_write_json(self.data_file, payload)
            self._file_stamp = self.file_stamp()
        if external:
            self.apply_saved_payload(payload)
        else:
            self.remember_loaded_state(payload)

    def set_study_plan(self, settings):
        """Make these plan choices the profile's plan, starting today."""
        self.study_plan = {"settings": dict(settings), "created": today_iso(), "done": {}} if settings else {}
        self.save()

    def plan_steps_done(self, day=None):
        return set(self.study_plan.get("done", {}).get(day or today_iso(), [])) if self.study_plan else set()

    def toggle_plan_step(self, index, day=None):
        if not self.study_plan:
            return False
        day = day or today_iso()
        done = self.plan_steps_done(day)
        done.symmetric_difference_update({int(index)})
        # Keep only the last couple of weeks of ticks.
        history = {key: value for key, value in self.study_plan.setdefault("done", {}).items() if key >= add_days(-14)}
        history[day] = sorted(done)
        self.study_plan["done"] = history
        self.save()
        return int(index) in done

    def add_feedback(self, rating, category, page, note):
        entry = FeedbackEntry(rating=rating, category=category, page=page, note=note)
        self.feedback.insert(0, entry)
        self.save()
        return entry

    def unsent_feedback(self):
        return [entry for entry in self.feedback if not entry.sent_at]

    def mark_feedback_sent(self, ids):
        ids = set(ids)
        stamp = now_label()
        for entry in self.feedback:
            if entry.id in ids:
                entry.sent_at = stamp
        self.save()

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

    def due_cards(self, deck=None, on=None):
        """Cards due by `on` (an ISO date; today by default), optionally one deck."""
        on = on or today_iso()
        cards = [card for card in self.cards if card.next_review <= on and card.buried_until <= on]
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
        self.add_cards([card])

    def add_cards(self, cards):
        """Add several cards (newest first) with a single save."""
        cards = list(cards)
        if not cards:
            return
        self.cards[:0] = reversed(cards)
        self.save()

    def add_capture(self, capture):
        self.captures.insert(0, capture)
        self.save()

    MAX_INTERVAL = 365

    @staticmethod
    def days_overdue(card):
        try:
            return max(0, (date.today() - date.fromisoformat(card.next_review)).days)
        except (TypeError, ValueError):
            return 0

    def next_interval(self, card, quality):
        """SM-2 style spacing with hard/easy steps and credit for late reviews.

        quality 3 = recalled with effort (grows gently), 4 = good (grows by
        ease), 5 = easy (extra bonus). Remembering a card after it was due
        shows it held longer than scheduled, so part of that overdue time
        counts toward the next interval.
        """
        if card.repetitions == 0:
            interval = {3: 1, 4: 1}.get(quality, 3)
        elif card.repetitions == 1:
            interval = {3: 2, 4: 3}.get(quality, 5)
        else:
            overdue_credit = {3: 0.25, 4: 0.5}.get(quality, 1.0) * self.days_overdue(card)
            factor = {3: 1.2, 4: card.ease}.get(quality, card.ease * 1.3)
            interval = max(card.interval + 1, round((card.interval + overdue_credit) * factor))
            if interval >= 7:
                # Spread cards learned together across nearby days instead of
                # letting them all come due at once (deterministic per card).
                spread = max(1, round(interval * 0.05))
                interval += (sum(map(ord, card.id)) + card.repetitions) % (2 * spread + 1) - spread
        return max(1, min(self.MAX_INTERVAL, interval))

    def schedule(self, card, quality, assessment=None):
        snapshot = asdict(card)
        activity_key = today_iso()
        if quality < 3:
            card.repetitions = 0
            card.interval = 1
            card.lapses += 1
        else:
            card.interval = self.next_interval(card, quality)
            card.repetitions += 1
        card.ease = min(3.5, max(1.3, card.ease + (0.1 - (5 - quality) * 0.08)))
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
        self.accessibility = default_accessibility()
        self.feedback = []
        self.onboarding = default_onboarding()
        self.study_plan = {}
        self.last_action = None
        self.save(merge_existing=False)
