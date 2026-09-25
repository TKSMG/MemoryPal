"""Progress numbers for the Dashboard and Stats pages.

Everything here is computed from what the store already saves (the daily
activity log and the cards), so it needs no extra history and works for
existing profiles straight away.
"""

from datetime import date, timedelta

XP_PER_REVIEW = 10
MATURE_DAYS = 21
YOUNG_DAYS = 7
MASTERED_SCORE = 82
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def level_info(practiced):
    """Level from total reviews. Each level needs 100 XP more than the last."""
    xp = max(0, int(practiced)) * XP_PER_REVIEW
    level, need = 1, 100
    while xp >= need:
        xp -= need
        level += 1
        need += 100
    return {"level": level, "xp": xp, "need": need, "pct": xp / need}


def daily_series(activity, days, end=None):
    """(date, count) for the last `days` days, oldest first."""
    end = end or date.today()
    start = end - timedelta(days=days - 1)
    return [(start + timedelta(days=offset), int(activity.get((start + timedelta(days=offset)).isoformat(), 0) or 0)) for offset in range(days)]


def best_streak(activity):
    active = sorted(date.fromisoformat(day) for day, count in activity.items() if (count or 0) > 0 and _is_iso(day))
    best = run = 0
    previous = None
    for day in active:
        run = run + 1 if previous is not None and (day - previous).days == 1 else 1
        best = max(best, run)
        previous = day
    return best


def _is_iso(value):
    try:
        date.fromisoformat(value)
        return True
    except (TypeError, ValueError):
        return False


def due_forecast(cards, days=14, today=None):
    """Cards coming due on each of the next `days` days; overdue counts as today."""
    today = today or date.today()
    counts = [0] * days
    for card in cards:
        try:
            due = date.fromisoformat(card.next_review)
        except (TypeError, ValueError):
            continue
        offset = max(0, (due - today).days)
        if offset < days:
            counts[offset] += 1
    return [(today + timedelta(days=offset), counts[offset]) for offset in range(days)]


def maturity_breakdown(cards):
    """New (never reviewed), learning (<1 week), young (<3 weeks) and mature cards."""
    groups = {"new": 0, "learning": 0, "young": 0, "mature": 0}
    for card in cards:
        if card.repetitions == 0:
            groups["new"] += 1
        elif card.interval < YOUNG_DAYS:
            groups["learning"] += 1
        elif card.interval < MATURE_DAYS:
            groups["young"] += 1
        else:
            groups["mature"] += 1
    return groups


# Saved results come from the rating buttons (store.schedule) or from Smart
# Check (core.answer_assessment); group both the way the buttons are named.
RATING_BUCKETS = (
    ("Again", ("Again", "Weak", "Weak match", "Missed context", "Needs response")),
    ("Hard", ("Review", "Partial match")),
    ("Good", ("Good", "Close enough")),
    ("Easy", ("Easy", "Strong match")),
)


def rating_mix(cards):
    """How each card went last time, grouped into the four rating buttons."""
    counts = {name: 0 for name, _labels in RATING_BUCKETS}
    for card in cards:
        if card.repetitions == 0 and card.lapses == 0 and card.last_result in ("", "New"):
            continue
        result = card.last_result or ""
        for name, labels in RATING_BUCKETS:
            if result in labels:
                counts[name] += 1
                break
        else:
            score = card.last_score or 0
            if score or result:
                bucket = "Easy" if score >= 90 else "Good" if score >= 70 else "Hard" if score >= 45 else "Again"
                counts[bucket] += 1
    return counts


def weekday_rhythm(activity, weeks=12, today=None):
    """Average reviews for each weekday over the last `weeks` weeks."""
    today = today or date.today()
    totals = [0] * 7
    for day, count in daily_series(activity, weeks * 7, today):
        totals[day.weekday()] += count
    return [(WEEKDAYS[index], totals[index] / weeks) for index in range(7)]


def mastered_count(cards):
    return sum(1 for card in cards if card.last_score >= MASTERED_SCORE or card.last_result == "Strong match")


def achievements(store):
    """Badges with progress. Earned ones first, then the closest to earning."""
    activity = store.activity
    best = max(best_streak(activity), store.current_streak())
    mastered = mastered_count(store.cards)
    goal_days = sum(1 for count in activity.values() if (count or 0) >= max(1, store.daily_goal))
    plan_saved = 1 if getattr(store, "study_plan", None) else 0
    items = [
        ("first_review", "✨", "First step", "Finish your first review.", store.practiced, 1),
        ("reviews_50", "\U0001F4AA", "Warming up", "Finish 50 reviews.", store.practiced, 50),
        ("reviews_250", "\U0001F3C3", "Memory athlete", "Finish 250 reviews.", store.practiced, 250),
        ("reviews_1000", "\U0001F3C6", "Recall legend", "Finish 1,000 reviews.", store.practiced, 1000),
        ("streak_3", "\U0001F525", "On a roll", "Practise 3 days in a row.", best, 3),
        ("streak_7", "\U0001F4C5", "Week warrior", "Practise 7 days in a row.", best, 7),
        ("streak_30", "\U0001F451", "Habit locked in", "Practise 30 days in a row.", best, 30),
        ("goal_day", "\U0001F3AF", "Goal getter", "Reach your daily goal once.", goal_days, 1),
        ("goal_10", "\U0001F31F", "Reliable", "Reach your daily goal on 10 days.", goal_days, 10),
        ("mastered_10", "\U0001F9E0", "Ten solid", "Master 10 cards.", mastered, 10),
        ("mastered_50", "\U0001F393", "Deep roots", "Master 50 cards.", mastered, 50),
        ("decks_3", "\U0001F5C2", "Collector", "Study cards in 3 decks.", len(store.decks()), 3),
        ("capture_1", "\U0001F4DD", "Note taker", "Capture your own material.", len(store.captures), 1),
        ("planner", "\U0001F5FA", "Planner", "Save a study plan.", plan_saved, 1),
    ]
    badges = []
    for key, icon, title, body, current, target in items:
        current = min(int(current), target)
        badges.append({"key": key, "icon": icon, "title": title, "body": body, "current": current, "target": target, "done": current >= target})
    badges.sort(key=lambda badge: (not badge["done"], -(badge["current"] / badge["target"])))
    return badges


def next_achievement(store):
    pending = [badge for badge in achievements(store) if not badge["done"]]
    return pending[0] if pending else None
