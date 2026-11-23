"""What MemoryPal's notifications say, and when, for the next week.

Neither the phone nor the computer can run MemoryPal at the moment a
notification shows, so the next week is worked out ahead of time (when the
app closes, goes to the background, or the settings change) and handed to
the system to show. Opening MemoryPal and studying works the week out
again, so a reminder about something already done is taken back.

mobile/src/features/notifications.ts is the phone's copy of this file and
must give the same answers (tools/parity/make_notification_fixtures.py).

Kinds, each with its own switch in Settings:
  cards_due        cards are ready to review (at the reminder time)
  plan_today       today's study plan (replaces cards_due that day)
  plan_unfinished  steps of today's plan are left (evening)
  test_countdown   a set's test is 7, 3 or 1 days away, or today
  streak           a streak of 2+ days ends tonight (late evening)
  notes_waiting    notes not made into cards yet (Saturdays)
  weekly_recap     the week's reviews (Sunday evening)
"""

from datetime import date, datetime, timedelta

from . import planning
from .store import capture_deck, plain_text, source_quote

KINDS = ("cards_due", "plan_today", "plan_unfinished", "test_countdown", "streak", "notes_waiting", "weekly_recap")
# Which one stays when only one a day is allowed: the most time-sensitive.
PRIORITY = ("test_countdown", "plan_today", "cards_due", "streak", "plan_unfinished", "weekly_recap", "notes_waiting")
KIND_LABELS = {
    "cards_due": ("Cards due", "When cards are ready to review."),
    "plan_today": ("Today's study plan", "What your plan has for the day, instead of the cards reminder."),
    "plan_unfinished": ("Plan not finished", "An evening nudge if steps of today's plan are left."),
    "test_countdown": ("Test countdown", "A week, 3 days and a day before a set's test date, and that morning."),
    "streak": ("Streak saver", "Late in the evening if you haven't studied and have a streak of 2 days or more."),
    "notes_waiting": ("Notes waiting", "Saturdays, if some of your notes aren't cards yet."),
    "weekly_recap": ("Weekly recap", "Sunday evening: how your week went."),
}

REMINDER_TIMES = ("08:00", "13:00", "19:00", "21:00")
BEST_TIME = "best"
DEFAULT_TIME = "19:00"
QUIET_CHOICES = ("off", "21:00-08:00", "22:00-07:00", "23:00-07:00")
DEFAULT_QUIET = "22:00-07:00"
PLAN_NUDGE_TIME = "20:30"
STREAK_TIME = "21:00"
TEST_MORNING_TIME = "07:30"
RECAP_TIME = "18:00"
COUNTDOWN_DAYS = (7, 3, 1, 0)
NOTES_WEEKDAY = 5   # Saturday (Monday = 0)
RECAP_WEEKDAY = 6   # Sunday
DAYS_AHEAD = 7
WEEKDAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def plural(count, word):
    return f"{count} {word}{'' if count == 1 else 's'}"


def default_settings():
    """Off until turned on; once on, every kind is on."""
    return {"enabled": False, "time": DEFAULT_TIME, "kinds": list(KINDS), "quiet": DEFAULT_QUIET, "one_a_day": False}


def normalize_settings(raw):
    settings = default_settings()
    if not isinstance(raw, dict):
        return settings
    settings["enabled"] = raw.get("enabled") is True
    time = raw.get("time")
    settings["time"] = time if time == BEST_TIME or time in REMINDER_TIMES else DEFAULT_TIME
    kinds = raw.get("kinds")
    if isinstance(kinds, list):
        settings["kinds"] = [kind for kind in KINDS if kind in kinds]
    quiet = raw.get("quiet")
    settings["quiet"] = quiet if quiet in QUIET_CHOICES else DEFAULT_QUIET
    settings["one_a_day"] = raw.get("one_a_day") is True
    return settings


def clock(text, fallback=(19, 0)):
    """ "19:00" as (19, 0); anything else is the fallback."""
    parts = str(text or "").split(":")
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit() and len(parts[1]) == 2:
        hour, minute = int(parts[0]), int(parts[1])
        if hour < 24 and minute < 60:
            return hour, minute
    return fallback


def reminder_clock(store, time):
    """The reminder time; "best" is the hour the practice log likes best (7pm until it knows)."""
    if time == BEST_TIME:
        finder = getattr(planning, "best_study_hour", None)
        try:
            hour = finder(store) if finder else None
        except Exception:
            hour = None
        return (int(hour), 0) if isinstance(hour, int) and 0 <= hour < 24 else clock(DEFAULT_TIME)
    return clock(time)


def quiet_window(quiet):
    """(start, end) minutes of the day, or None when quiet hours are off."""
    if quiet == "off" or quiet not in QUIET_CHOICES:
        return None
    start, _sep, end = quiet.partition("-")
    start_hour, start_minute = clock(start)
    end_hour, end_minute = clock(end)
    return start_hour * 60 + start_minute, end_hour * 60 + end_minute


def is_quiet(at, window):
    if not window:
        return False
    minute = at.hour * 60 + at.minute
    start, end = window
    return start <= minute or minute < end if start > end else start <= minute < end


def at_time(day, hour_minute):
    return datetime(day.year, day.month, day.day, hour_minute[0], hour_minute[1])


def _plan_days(store, first_day, days):
    """{iso day: steps} of the saved plan for the coming days (skips days it has ended).

    Mirrors planning.plan_for_today, but builds a multi-day plan once
    instead of once a day.
    """
    plan = getattr(store, "study_plan", None)
    if not plan or not plan.get("settings"):
        return {}
    settings = plan["settings"]
    deck_choice = settings.get("deck", "All decks")
    goal = planning.GOAL_KEYS.get(settings.get("goal_label", "Long-term retention"), "long_term")
    habits = settings.get("habits") if isinstance(settings.get("habits"), list) else []
    habits = {habit for habit in habits if isinstance(habit, str)}
    minutes = planning.plan_minutes(settings)
    found = {}
    if minutes is not None:
        steps = planning.build_study_plan(store, minutes, deck_choice, habits, goal)
        for offset in range(days):
            found[(first_day + timedelta(days=offset)).isoformat()] = steps
        return found
    try:
        created = date.fromisoformat(plan.get("created"))
    except (TypeError, ValueError):
        created = first_day
    try:
        amount = int(settings.get("amount", 1))
    except (TypeError, ValueError, OverflowError):
        amount = 1
    total_days = min(planning.MAX_PLAN_DAYS, amount * (7 if settings.get("unit") == "weeks" else 1))
    built = None
    for offset in range(days):
        day = first_day + timedelta(days=offset)
        number = max(1, (day - created).days + 1)
        if number > total_days:
            continue
        if built is None:
            built = planning.build_multi_day_plan(store, total_days, deck_choice, habits, goal, start=created)
        found[day.isoformat()] = built[number - 1]["steps"]
    return found


def plan_left(store, steps, iso):
    """(steps left, minutes left) of a plan day, counting ticked-off steps."""
    steps = store.plan_day_steps(steps, iso)
    done = store.plan_steps_done(iso)
    left = [step for index, step in enumerate(steps) if index not in done and step.get("view") != "break"]
    return len(left), sum(int(step.get("minutes") or 0) for step in left)


def weak_count(store, deck):
    return len([card for card in store.cards if (card.deck or "General") == deck and (card.lapses > 0 or card.last_score < 64 or card.repetitions == 0)])


def notes_waiting(store):
    """Notes with study bits that no card seems to come from yet.

    Notes in a set that has cards count as used (cards typed by hand from
    notes don't say where they came from); other notes count as used when an
    AI card quotes them.
    """
    with_cards = {card.deck or "General" for card in store.cards}
    quotes = [quote for quote in (plain_text(source_quote(card))[:80] for card in store.cards) if len(quote) >= 12]
    waiting = []
    for capture in store.captures:
        if not (capture.chunks or str(capture.notes or "").strip()):
            continue
        if capture_deck(capture) in with_cards:
            continue
        text = plain_text(" ".join([capture.notes or ""] + list(capture.chunks or [])))
        if any(quote in text for quote in quotes):
            continue
        waiting.append(capture)
    return waiting


def item(kind, at, title, body, target, due=0):
    return {"kind": kind, "at": at, "title": title, "body": body, "open": target, "due": due}


def plan_notifications(store, settings, start=None, days=DAYS_AHEAD):
    """The notifications for the next `days` days, soonest first.

    Each is {kind, at (local datetime), title, body, open, due}. `open` is
    where tapping it goes: review, plan, progress, notes or deck:<set>.
    """
    settings = normalize_settings(settings)
    if not settings["enabled"]:
        return []
    kinds = set(settings["kinds"])
    start = start or datetime.now()
    today = start.date()
    main = reminder_clock(store, settings["time"])
    window = quiet_window(settings["quiet"])
    studied_today = store.activity.get(today.isoformat(), 0) > 0
    streak = store.current_streak()
    plan_days = _plan_days(store, today, days) if kinds & {"plan_today", "plan_unfinished"} else {}
    exams = []
    if "test_countdown" in kinds:
        decks = set(store.decks())
        for info in getattr(store, "deck_infos", []):
            if info.exam_date and info.id in decks:
                exams.append((info.id, date.fromisoformat(info.exam_date)))
    waiting = notes_waiting(store) if "notes_waiting" in kinds else []
    found = []
    for offset in range(days):
        day = today + timedelta(days=offset)
        iso = day.isoformat()
        todays = []
        # The streak runs up to yesterday when today isn't done yet.
        keep = streak if offset == 0 or (offset == 1 and studied_today) else 0
        skip_study = offset == 0 and studied_today

        # One countdown a day: the nearest test, naming any others.
        coming = sorted(((exam - day).days, deck) for deck, exam in exams if (exam - day).days in COUNTDOWN_DAYS)
        if coming:
            away, deck = coming[0]
            weak = weak_count(store, deck)
            when = {0: "today", 1: "tomorrow", 7: "in a week"}.get(away, f"in {away} days")
            body = f"{plural(weak, 'card')} still {'needs' if weak == 1 else 'need'} work. A short review now helps." if weak else "Your cards look solid. A quick run-through keeps them fresh."
            others = [name for _away, name in coming[1:]]
            if others:
                body += f" Also coming up: {', '.join(others)}."
            hour_minute = clock(TEST_MORNING_TIME) if away == 0 else main
            todays.append(item("test_countdown", at_time(day, hour_minute), f"{deck} test {when}", body, f"deck:{deck}", weak))
        # A countdown at the reminder time already says to review.
        counted = any(entry["at"] == at_time(day, main) for entry in todays)

        due = len(store.due_cards(None, on=iso))
        steps = plan_days.get(iso)
        left, left_minutes = plan_left(store, steps, iso) if steps else (0, 0)
        # Once a step is ticked the plan is under way: only the evening nudge is left.
        started = bool(steps) and left < len([step for step in steps if step.get("view") != "break"])
        planned = False
        if "plan_today" in kinds and left and not started:
            title = f"Today's plan: {plural(left, 'step')}, about {left_minutes} min"
            first = next((step.get("title") for step in steps if step.get("view") != "break"), "")
            todays.append(item("plan_today", at_time(day, main), title, f"First: {first}." if first else "Open your plan to start.", "plan", due))
            planned = True
        if "cards_due" in kinds and due and not skip_study and not planned and not counted:
            title = "A card is ready to review" if due == 1 else f"{plural(due, 'card')} are ready to review"
            body = f"A few minutes keeps your {keep}-day streak going." if keep >= 2 else "A few minutes now helps them stick."
            todays.append(item("cards_due", at_time(day, main), title, body, "review", due))
        if "plan_unfinished" in kinds and left:
            nudge = clock(PLAN_NUDGE_TIME)
            if nudge > main:
                todays.append(item("plan_unfinished", at_time(day, nudge), f"Your plan has {plural(left, 'step')} left", f"About {left_minutes} min finishes today's plan.", "plan", due))
        if "streak" in kinds and keep >= 2 and not skip_study:
            late = clock(STREAK_TIME)
            reminded = any(entry["kind"] in ("cards_due", "plan_today") for entry in todays)
            if late > main or not reminded:
                todays.append(item("streak", at_time(day, late), f"Keep your {keep}-day streak", "A few cards before bed keeps it going.", "review", due))
        if "notes_waiting" in kinds and waiting and day.weekday() == NOTES_WEEKDAY:
            first = waiting[0].title
            title = f"{plural(len(waiting), 'set')} of notes aren't cards yet" if len(waiting) > 1 else "Some notes aren't cards yet"
            todays.append(item("notes_waiting", at_time(day, main), title, f"Turn “{first}” into cards to start remembering it.", "notes"))
        if "weekly_recap" in kinds and day.weekday() == RECAP_WEEKDAY:
            week = [day - timedelta(days=back) for back in range(6, -1, -1)]
            counts = [store.activity.get(each.isoformat(), 0) for each in week]
            reviews = sum(counts)
            if reviews:
                best = max(range(7), key=lambda index: (counts[index], -index))
                studied = len([count for count in counts if count > 0])
                tomorrow = len(store.due_cards(None, on=(day + timedelta(days=1)).isoformat()))
                body = f"Best day: {WEEKDAY_NAMES[week[best].weekday()]} ({counts[best]}). {plural(tomorrow, 'card')} due tomorrow."
                todays.append(item("weekly_recap", at_time(day, clock(RECAP_TIME)), f"Your week: {plural(reviews, 'review')} on {plural(studied, 'day')}", body, "progress"))

        todays = [entry for entry in todays if entry["at"] > start and not is_quiet(entry["at"], window)]
        if settings["one_a_day"] and todays:
            todays = [min(todays, key=lambda entry: PRIORITY.index(entry["kind"]))]
        found.extend(todays)
    found.sort(key=lambda entry: (entry["at"], PRIORITY.index(entry["kind"])))
    return found
