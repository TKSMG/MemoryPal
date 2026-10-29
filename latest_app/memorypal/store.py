import json
import os
import re
import shutil
import time
from dataclasses import asdict
from datetime import date, timedelta

from . import paths, techniques
from .aiflow import normalize_preferences
from .core import add_days, now_label, split_study_bits, today_iso
from .models import Card, Capture, DeckInfo, FeedbackEntry, deck_name, iso_day, sample_cards


def safe_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default


def as_dict(value):
    return dict(value) if isinstance(value, dict) else {}


def as_list(value):
    return list(value) if isinstance(value, list) else []


MAX_DAILY_GOAL = 500


def clamp_goal(value):
    """A daily goal of 0 or less made every day count as 'goal met'."""
    return max(1, min(MAX_DAILY_GOAL, safe_int(value, 15)))


def load_items(raw_items, factory):
    items = []
    for raw in raw_items or []:
        if not isinstance(raw, dict):
            continue
        try:
            items.append(factory(raw))
        except (TypeError, ValueError, AttributeError, OverflowError):
            continue
    return items


def unique_decks(infos):
    """Set details with one entry per set name (the last wins) and no empty ones."""
    by_name = {}
    for info in infos:
        if not info.empty():
            by_name.pop(info.id, None)
            by_name[info.id] = info
    return list(by_name.values())


def capture_deck(capture, decks=None):
    """The set a capture belongs to: its own `deck`, or for older notes a
    title "<set>: ..." naming a set in `decks` (any set when decks is None)."""
    if capture.deck:
        return capture.deck
    head, sep, _rest = str(capture.title or "").partition(": ")
    head = deck_name(head)
    if sep and head and (decks is None or head in decks):
        return head
    return ""


AI_PATHWAY = "Made with AI"


def days_until(exam_date, today=None):
    """Days from today to a YYYY-MM-DD exam date (negative once past), or None."""
    day = iso_day(exam_date)
    if not day:
        return None
    return (date.fromisoformat(day) - (today or date.today())).days


def exam_countdown(exam_date, today=None):
    """"Exam in 12 days", "Exam tomorrow", "Exam today", "Exam was 3 days ago", or ""."""
    days = days_until(exam_date, today)
    if days is None:
        return ""
    if days == 0:
        return "Exam today"
    if days == 1:
        return "Exam tomorrow"
    if days > 1:
        return f"Exam in {days} days"
    return f"Exam was {-days} day{'' if days == -1 else 's'} ago"


def source_quote(card):
    """The sentence an AI card's answer came from (its hook's Source: "..."), or ""."""
    match = re.search(r'Source: "(.+)"\s*$', str(card.association or ""), re.S)
    return match.group(1).strip() if match else ""


def ai_source_title(card):
    """What an AI card was made from, by name ("Made with AI > <title>"), or ""."""
    head, sep, rest = str(card.pathway or "").partition(" > ")
    return rest.strip() if sep and head == AI_PATHWAY else ""


def plain_text(text):
    """Lower case words only, for finding a quote in notes whatever the punctuation."""
    return " ".join(re.sub(r"[^\w\s]|_", " ", str(text or "").lower()).split())


def technique_item(card):
    """What a card is remembered by in a memory technique: its answer when short, else its question."""
    back = " ".join(str(card.back or "").split())
    return back if back and len(back.split()) <= 8 else " ".join(str(card.front or "").split())


def move_capture(capture, old_name, new_name):
    """Move notes to another set ("" for none), dropping an old "<set>: " title prefix."""
    prefix = f"{old_name}: "
    if capture.title.startswith(prefix) and len(capture.title) > len(prefix):
        capture.title = capture.title[len(prefix):]
    capture.deck = new_name


def default_payload():
    return {
        "cards": [],
        "captures": [],
        "decks": [],
        "practiced": 0,
        "activity": {},
        "daily_goal": 15,
        "nav_order": [],
        "accessibility": default_accessibility(),
        "feedback": [],
        "onboarding": default_onboarding(),
        "study_plan": {},
        "preferences": normalize_preferences(None),
    }


# What a saved plan may say. Plans arrive from other devices through sync, so
# a plan asking for a million days (or a habit that isn't a word) is cut down
# here instead of freezing the app when today's plan is worked out.
PLAN_AMOUNTS = {"minutes": (1, 600, "30"), "hours": (1, 24, "1"), "days": (1, 365, "1"), "weeks": (1, 52, "1")}
PLAN_HABITS = ("mnemonics", "repetition", "quick_mc", "games", "breaks", "explain")
MAX_PLAN_TEXT = 200


def plan_text(value, default):
    return value if isinstance(value, str) and len(value) <= MAX_PLAN_TEXT else default


def normalize_plan_settings(raw):
    unit = raw.get("unit") if isinstance(raw.get("unit"), str) and raw.get("unit") in PLAN_AMOUNTS else "minutes"
    low, high, default = PLAN_AMOUNTS[unit]
    amount = raw.get("amount", default)
    if isinstance(amount, bool) or not isinstance(amount, (int, float, str)):
        amount = default
    elif isinstance(amount, (int, float)):
        amount = str(max(low, min(high, int(amount)))) if isinstance(amount, int) or amount.is_integer() else default
    # Plain digits only: int() also takes " 7", "²", "١٢" and "1_000".
    elif re.fullmatch(r"[0-9]{1,12}", amount):
        amount = str(max(low, min(high, int(amount))))
    else:
        amount = default
    habits = {habit for habit in as_list(raw.get("habits")) if isinstance(habit, str)}
    return {
        "unit": unit,
        "amount": amount,
        "deck": plan_text(raw.get("deck"), "All decks"),
        "goal_label": plan_text(raw.get("goal_label"), "Long-term retention"),
        "habits": [key for key in PLAN_HABITS if key in habits],
    }


def normalize_study_plan(raw):
    """A saved plan: the choices it was built from, when, and ticked-off steps."""
    if not isinstance(raw, dict) or not isinstance(raw.get("settings"), dict):
        return {}
    done = raw.get("done") if isinstance(raw.get("done"), dict) else {}
    return {
        "settings": normalize_plan_settings(raw["settings"]),
        "created": str(raw.get("created") or today_iso()),
        "done": {str(day): sorted({int(index) for index in indexes if re.fullmatch(r"[0-9]{1,4}", str(index))}) for day, indexes in done.items() if isinstance(indexes, list)},
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
        "listen_answers": True,
    }


ACCESSIBILITY_TOGGLES = (
    "high_contrast", "reduce_motion", "simple_language", "caregiver_mode",
    "read_aloud", "more_time", "focus_outline", "listen_answers",
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


class UnreadableDataFile(ValueError):
    """The data file exists but is not valid MemoryPal JSON."""


def read_payload(path, strict=False):
    """The saved payload, or an empty one if the file is missing.

    With strict=True a file that exists but cannot be parsed raises
    UnreadableDataFile instead of looking empty, so callers never overwrite
    a damaged file (which may still be recoverable) with a blank profile.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return default_payload()
    except (OSError, UnicodeDecodeError):
        if strict:
            raise UnreadableDataFile(f"{path.name} could not be read")
        return default_payload()
    try:
        raw = json.loads(text)
    except json.JSONDecodeError:
        raw = None
    if isinstance(raw, dict):
        return raw
    if strict:
        raise UnreadableDataFile(f"{path.name} is not valid MemoryPal data")
    return default_payload()


def backup_path(path):
    return path.with_name(path.name + ".bak")


def atomic_write_json(path, payload, keep_backup=False):
    """Write JSON so a crash or power cut leaves either the old or the new file.

    With keep_backup the previous file is kept as `<name>.bak`, which load()
    falls back to if the main file is ever damaged.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with open(temp_path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, indent=2))
        handle.flush()
        os.fsync(handle.fileno())
    if keep_backup and path.exists():
        try:
            shutil.copy2(path, backup_path(path))
        except OSError:
            pass
    os.replace(temp_path, path)


def set_aside_damaged_file(path):
    """Copy a damaged data file aside (never delete it) and return the copy's path."""
    target = path.with_name(f"{path.stem}.damaged-{time.strftime('%Y%m%d-%H%M%S')}{path.suffix}")
    try:
        shutil.copy2(path, target)
    except OSError:
        return None
    return target


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
        # Each set's own details (exam date, AI style...), by set name.
        self.deck_infos = []
        self.practiced = 0
        self.activity = {}
        self.daily_goal = 15
        self.nav_order = []
        self.accessibility = default_accessibility()
        self.feedback = []
        self.onboarding = default_onboarding()
        self.study_plan = {}
        # This device's own choices (AI consent, quiz history): saved, never synced.
        self.preferences = normalize_preferences(None)
        self.last_action = None
        self._file_stamp = None
        self._loaded_preferences = normalize_preferences(None)
        self._loaded_onboarding = default_onboarding()
        self._loaded_practiced = 0
        self._loaded_activity = {}
        self._loaded_daily_goal = 15
        self._loaded_nav_order = []
        self._loaded_accessibility = default_accessibility()
        self._loaded_cards = {}
        self._loaded_captures = {}
        self._loaded_decks = {}
        self._loaded_feedback = {}
        # Called after every save (the desktop schedules a cloud sync).
        self.save_listeners = []
        # Goes up on every save or synced change, so a screen built from the
        # data can tell whether it is still current.
        self.revision = 0
        self.load()

    def set_profile_paths(self):
        directory = paths.profile_dir(self.profile_name)
        self.data_file = directory / "memorypal-data.json"
        self.attachment_dir = directory / "attachments"

    def load(self):
        self.set_profile_paths()
        paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.attachment_dir.mkdir(parents=True, exist_ok=True)
        self.recovered_from = None
        if not self.data_file.exists() and not backup_path(self.data_file).exists():
            self.cards = sample_cards()
            self.save(merge_existing=False)
            return
        # A crash between saves can leave only the backup behind.
        source = self.data_file if self.data_file.exists() else backup_path(self.data_file)
        try:
            raw = read_payload(source, strict=True)
        except UnreadableDataFile:
            # Keep a copy of the damaged file for recovery, then fall back to
            # the last good save instead of quietly starting from nothing
            # (which the next save would have written over the damaged file).
            self.recovered_from = set_aside_damaged_file(source) or source
            raw = read_payload(backup_path(self.data_file))
        self.apply_raw(raw)
        self._file_stamp = self.file_stamp()
        self.remember_loaded_state()
        if self.recovered_from is not None:
            self.save(merge_existing=False)

    def apply_raw(self, raw):
        """Fill the store from a saved payload, tolerating damaged fields."""
        self.cards = load_items(as_list(raw.get("cards")), Card.from_dict)
        self.captures = load_items(as_list(raw.get("captures")), Capture.from_dict)
        self.deck_infos = unique_decks(load_items(as_list(raw.get("decks")), DeckInfo.from_dict))
        self.practiced = max(0, safe_int(raw.get("practiced", 0), 0))
        self.activity = {str(day): safe_int(count, 0) for day, count in as_dict(raw.get("activity")).items() if safe_int(count, 0) > 0}
        self.daily_goal = clamp_goal(raw.get("daily_goal", 15))
        self.nav_order = [str(key) for key in as_list(raw.get("nav_order"))]
        self.accessibility = normalize_accessibility(raw.get("accessibility", {}))
        self.feedback = load_items(as_list(raw.get("feedback")), FeedbackEntry.from_dict)
        self.onboarding = normalize_onboarding(raw.get("onboarding"))
        self.study_plan = normalize_study_plan(raw.get("study_plan"))
        self.preferences = normalize_preferences(raw.get("preferences"))

    def remember_loaded_state(self, payload=None):
        self._loaded_practiced = self.practiced
        self._loaded_activity = dict(self.activity)
        self._loaded_daily_goal = self.daily_goal
        self._loaded_nav_order = list(self.nav_order)
        self._loaded_accessibility = dict(self.accessibility)
        self._loaded_onboarding = dict(self.onboarding)
        self._loaded_study_plan = normalize_study_plan(self.study_plan)
        self._loaded_preferences = normalize_preferences(self.preferences)
        if payload is None:
            self._loaded_cards = self.item_snapshot(self.cards)
            self._loaded_captures = self.item_snapshot(self.captures)
            self._loaded_decks = self.item_snapshot(self.deck_infos)
            self._loaded_feedback = self.item_snapshot(self.feedback)
        else:
            self._loaded_cards = self.raw_snapshot(payload.get("cards"))
            self._loaded_captures = self.raw_snapshot(payload.get("captures"))
            self._loaded_decks = self.raw_snapshot(payload.get("decks"))
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
            "decks": [asdict(info) for info in self.deck_infos],
            "practiced": self.practiced,
            "activity": self.activity,
            "daily_goal": self.daily_goal,
            "nav_order": self.nav_order,
            "accessibility": dict(self.accessibility),
            "feedback": [asdict(entry) for entry in self.feedback],
            "onboarding": dict(self.onboarding),
            "study_plan": normalize_study_plan(self.study_plan),
            "preferences": normalize_preferences(self.preferences),
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
            if not item_id or item_id in seen:
                continue
            if item_id in loaded_items:
                # This window loaded the item and has since deleted it; the
                # other window's copy must not bring it back.
                continue
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
        merged["decks"] = self.merge_items(local.get("decks", []), existing.get("decks", []), self._loaded_decks)
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
        if normalize_preferences(self.preferences) == self._loaded_preferences and "preferences" in existing:
            merged["preferences"] = normalize_preferences(existing.get("preferences"))
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

    def replace_with(self, payload):
        """Take a synced payload (keeping the card objects the UI holds) and save it."""
        self.apply_saved_payload(payload)
        self.save()

    def apply_saved_payload(self, payload):
        # Synced payloads come from other devices, so they get the same checks
        # as a file read from disk.
        self.cards = self.rebind_items(self.cards, as_list(payload.get("cards")), Card.from_dict)
        self.captures = self.rebind_items(self.captures, as_list(payload.get("captures")), Capture.from_dict)
        self.deck_infos = unique_decks(load_items(as_list(payload.get("decks")), DeckInfo.from_dict))
        self.practiced = max(0, safe_int(payload.get("practiced", 0), 0))
        self.activity = {str(day): safe_int(count, 0) for day, count in as_dict(payload.get("activity")).items() if safe_int(count, 0) > 0}
        self.daily_goal = clamp_goal(payload.get("daily_goal", 15))
        self.nav_order = [str(key) for key in as_list(payload.get("nav_order"))]
        self.accessibility = normalize_accessibility(payload.get("accessibility", {}))
        self.feedback = load_items(as_list(payload.get("feedback")), FeedbackEntry.from_dict)
        self.onboarding = normalize_onboarding(payload.get("onboarding"))
        self.study_plan = normalize_study_plan(payload.get("study_plan"))
        # Synced payloads never carry this device's preferences: keep ours.
        if "preferences" in payload:
            self.preferences = normalize_preferences(payload.get("preferences"))
        self.revision += 1
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
            if external:
                try:
                    existing = read_payload(self.data_file, strict=True)
                except UnreadableDataFile:
                    # Another window left a damaged file: keep a copy, write ours.
                    set_aside_damaged_file(self.data_file)
                    existing = None
                payload = self.merge_payload(existing, local)
            else:
                payload = local
            atomic_write_json(self.data_file, payload, keep_backup=True)
            self._file_stamp = self.file_stamp()
        if external:
            self.apply_saved_payload(payload)
        else:
            self.remember_loaded_state(payload)
        self.revision += 1
        for listener in list(self.save_listeners):
            listener()

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
            due = len([card for card in cards if card.next_review <= today_iso() and card.buried_until <= today_iso()])
            weak = len([card for card in cards if card.lapses > 0 or card.last_score < 64 or card.repetitions == 0])
            mastered = len([card for card in cards if card.last_score >= 82])
            summary[deck] = {
                "total": len(cards),
                "due": due,
                "weak": weak,
                "mastery": round(mastered / len(cards) * 100) if cards else 0,
            }
        return summary

    def due_cards(self, deck=None, on=None, since=None):
        """Cards due by `on` (an ISO date; today by default), optionally one deck.

        With `since`, only cards that first come due after that date count,
        which is what a future day of a plan will really face once the
        earlier days' reviews are done.
        """
        on = on or today_iso()
        cards = [card for card in self.cards if card.next_review <= on and card.buried_until <= on]
        if since:
            cards = [card for card in cards if card.next_review > since]
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

    EDITABLE_CARD_FIELDS = ("deck", "front", "back", "pathway", "association")

    def update_card(self, card, **fields):
        """Edit a card's words or deck. Its review schedule is left alone."""
        for name, value in fields.items():
            if name in self.EDITABLE_CARD_FIELDS:
                value = str(value or "").strip()
                setattr(card, name, (value or "General") if name == "deck" else value)
        self.save()

    def rename_deck(self, old_name, new_name):
        """Move every card in deck old_name to new_name with one save.

        Renaming onto an existing deck merges the two. Returns how many
        cards moved (0 when the name is blank or unchanged).
        """
        old_name = str(old_name or "").strip() or "General"
        new_name = " ".join(str(new_name or "").split())
        if not new_name or new_name == old_name:
            return 0
        moved = 0
        for card in self.cards:
            if (card.deck or "General") == old_name:
                card.deck = new_name
                moved += 1
        # The set's details and notes go with it; details already on the
        # target set win, and any it lacks are filled from the old one.
        info, target = self.deck_info(old_name), self.deck_info(new_name)
        for name in DeckInfo.FIELDS:
            if not getattr(target, name):
                setattr(target, name, getattr(info, name))
        changed = self._store_deck_info(target) | self._drop_deck_info(old_name)
        for capture in self.notes_for_deck(old_name):
            move_capture(capture, old_name, new_name)
            changed = True
        if moved or changed:
            self.save()
        return moved

    def delete_deck(self, name):
        """Delete a set's cards and details with one save. Its notes stay, unlinked.

        Returns how many cards were removed.
        """
        name = str(name or "").strip() or "General"
        ids = {card.id for card in self.cards if (card.deck or "General") == name}
        self.cards = [card for card in self.cards if card.id not in ids]
        if self.last_action and self.last_action.get("card_id") in ids:
            self.last_action = None
        changed = self._drop_deck_info(name)
        for capture in self.notes_for_deck(name):
            move_capture(capture, name, "")
            changed = True
        if ids or changed:
            self.save()
        return len(ids)

    def technique_items(self, deck):
        """A set's cards, oldest first, and the item each is remembered by (a short answer, else the question)."""
        cards = [card for card in reversed(self.cards) if (card.deck or "General") == deck]
        return cards, [technique_item(card) for card in cards]

    def add_technique_hooks(self, deck, kind):
        """Give each card in a set its line from a memory technique, added to its hook. Returns how many changed."""
        cards, items = self.technique_items(deck)
        hooks = techniques.hooks_for(kind, items)
        changed = 0
        if len(hooks) == len(cards):
            for card, hook in zip(cards, hooks):
                if hook in card.association:
                    continue
                card.association = f"{card.association}\n{hook}" if card.association.strip() else hook
                changed += 1
        if changed:
            self.save()
        return changed

    # ----------------------------------------------------------- set details
    def deck_info(self, name):
        """A copy of this set's details (blank when it has none)."""
        name = deck_name(name)
        for info in self.deck_infos:
            if info.id == name:
                return DeckInfo(**asdict(info))
        return DeckInfo(id=name)

    def set_deck_info(self, name, **fields):
        """Change some of a set's details (exam_date, about, ai_style, ai_examples) and save."""
        info = self.deck_info(name)
        if not info.id:
            return info
        raw = asdict(info)
        raw.update({key: value for key, value in fields.items() if key in DeckInfo.FIELDS})
        info = DeckInfo.from_dict(raw)
        if self._store_deck_info(info):
            self.save()
        return info

    def _store_deck_info(self, info):
        """Put info in place (or remove it when empty). True if anything changed."""
        if not info.id:
            return False
        if info.empty():
            return self._drop_deck_info(info.id)
        for index, existing in enumerate(self.deck_infos):
            if existing.id == info.id:
                if asdict(existing) == asdict(info):
                    return False
                existing.__dict__.update(info.__dict__)
                return True
        self.deck_infos.append(info)
        return True

    def _drop_deck_info(self, name):
        name = deck_name(name)
        before = len(self.deck_infos)
        self.deck_infos = [info for info in self.deck_infos if info.id != name]
        return len(self.deck_infos) != before

    def notes_for_deck(self, name):
        """Saved notes that belong to this set, newest first.

        Notes saved before 0.52.0 have no set, only a title starting "<set>: ".
        """
        name = deck_name(name)
        return [capture for capture in self.captures if capture_deck(capture) == name] if name else []

    def source_notes(self, card):
        """(notes, bit index) a card was made from, or (None, -1).

        An AI card quotes the sentence its answer came from; the saved notes
        holding that sentence (its own set's first) are its source. A card
        whose quote isn't found falls back to notes titled like its AI
        source. The bit index is -1 when the quote spans bits or is absent.
        """
        own = self.notes_for_deck(card.deck or "General")
        candidates = own + [capture for capture in self.captures if capture not in own]
        quote = plain_text(source_quote(card))[:80]
        if len(quote) >= 12:
            for capture in candidates:
                chunks = capture.chunks or split_study_bits(capture.notes)
                for index, chunk in enumerate(chunks):
                    if quote in plain_text(chunk):
                        return capture, index
                if quote in plain_text(capture.notes):
                    return capture, -1
        title = ai_source_title(card)
        if title:
            for capture in own:
                if plain_text(capture.title) == plain_text(title):
                    return capture, -1
        return None, -1

    def find_capture(self, capture_id):
        return next((capture for capture in self.captures if capture.id == capture_id), None)

    def delete_capture(self, capture_id):
        before = len(self.captures)
        self.captures = [capture for capture in self.captures if capture.id != capture_id]
        if len(self.captures) != before:
            self.save()
            return True
        return False

    def delete_cards(self, ids):
        """Remove cards by id with one save. Returns how many were removed."""
        ids = set(ids)
        before = len(self.cards)
        self.cards = [card for card in self.cards if card.id not in ids]
        if self.last_action and self.last_action.get("card_id") in ids:
            self.last_action = None
        removed = before - len(self.cards)
        if removed:
            self.save()
        return removed

    def reset_progress(self, ids):
        """Make these cards new again, keeping their words and cues."""
        ids = set(ids)
        fresh = Card()
        for card in self.cards:
            if card.id in ids:
                for name in ("interval", "repetitions", "ease", "lapses", "last_score", "last_result", "buried_until"):
                    setattr(card, name, getattr(fresh, name))
                card.next_review = today_iso()
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
                # The spread must never undo the growth a success earned.
                interval = max(interval, card.interval + 1)
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
        # Step back by one: a sync since the rating may have added other devices' counts.
        self.practiced = max(0, self.practiced - 1)
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
        self.deck_infos = []
        self.practiced = 0
        self.activity = {}
        self.daily_goal = 15
        self.nav_order = []
        self.accessibility = default_accessibility()
        self.feedback = []
        self.onboarding = default_onboarding()
        self.study_plan = {}
        # This device's own choices (AI consent, quiz history): saved, never synced.
        self.preferences = normalize_preferences(None)
        self.last_action = None
        self.save(merge_existing=False)
