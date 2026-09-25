from datetime import date, timedelta

STUDY_HABIT_OPTIONS = [
    ("mnemonics", "I remember better with mnemonics, stories, or images"),
    ("repetition", "I like structured repetition drilling"),
    ("quick_mc", "I prefer quick multiple choice over typing answers"),
    ("games", "I like short recall-game breaks to reset focus"),
    ("breaks", "I focus better with short rest breaks (Pomodoro style)"),
    ("explain", "I learn by explaining ideas in my own words"),
]

TIME_UNIT_OPTIONS = {
    "minutes": ["15", "30", "45", "60", "90"],
    "hours": ["1", "2", "3", "4"],
    "days": ["1", "2", "3", "5", "7"],
    "weeks": ["1", "2", "3", "4"],
}
TIME_UNIT_ORDER = ["minutes", "hours", "days", "weeks"]

# Rough time per due card with Smart Check (answer, check, rate).
MINUTES_PER_CARD = 0.6
# Expanding review days after first learning new material (day 1).
NEW_MATERIAL_REVIEW_DAYS = (2, 4, 7, 14, 21, 30)
SHORT_SESSION_MINUTES = 12
MIN_STEP_MINUTES = 2
# Rest breaks: one after roughly every FOCUS_BLOCK_MINUTES of study.
FOCUS_BLOCK_MINUTES = 25
BREAK_MINUTES = 5
# New cards take longer than reviews and add to future review load.
MINUTES_PER_NEW_CARD = 1.5
MAX_NEW_CARDS_PER_SESSION = 20


def plural(count, word):
    return f"{count} {word}{'' if count == 1 else 's'}"


def allocate_minutes(shares, minutes):
    """Split minutes across steps in proportion to shares, summing exactly.

    Every step gets at least MIN_STEP_MINUTES; the rest is shared by weight
    using largest remainders so rounding never over- or under-shoots.
    """
    count = len(shares)
    if not count:
        return []
    floor = MIN_STEP_MINUTES if minutes >= MIN_STEP_MINUTES * count else 0
    spare = minutes - floor * count
    total = sum(shares) or 1
    exact = [spare * share / total for share in shares]
    allotted = [int(value) for value in exact]
    leftovers = sorted(range(count), key=lambda i: exact[i] - allotted[i], reverse=True)
    for index in leftovers[: spare - sum(allotted)]:
        allotted[index] += 1
    return [floor + value for value in allotted]


def review_detail(due_count, share_minutes):
    if not due_count:
        return "Nothing is due, so this works through weak and fresh cards instead."
    needed = max(1, round(due_count * MINUTES_PER_CARD))
    if needed > share_minutes:
        return f"{plural(due_count, 'card')} due (about {needed} min) — do the oldest first; the rest can wait for tomorrow."
    return f"{plural(due_count, 'card')} due, about {needed} min."


def build_study_plan(store, minutes, deck_choice, habits, goal, on=None):
    """Build one session's steps. `on` projects due cards for a future ISO date."""
    minutes = max(MIN_STEP_MINUTES, int(minutes))
    habits = set(habits or ())
    deck = None if deck_choice in ("All decks", "New material") else deck_choice
    due = store.due_cards(deck, on=on)
    weak = [card for card in store.weak_cards() if not deck or (card.deck or "General") == deck]
    fresh = [card for card in store.cards if card.repetitions == 0 and card.lapses == 0 and (not deck or (card.deck or "General") == deck)]
    breaks = "breaks" in habits and minutes >= 2 * FOCUS_BLOCK_MINUTES - 5
    study_minutes = minutes - (BREAK_MINUTES * max(0, round(minutes / (FOCUS_BLOCK_MINUTES + BREAK_MINUTES)) - 1) if breaks else 0)
    deck_names = {card.deck or "General" for card in store.cards if not deck or (card.deck or "General") == deck}
    has_cards = bool(deck_names)
    self_check_mode = "choices" if "quick_mc" in habits else "self"
    steps = []

    def add(title, share, view, blurb, **extra):
        steps.append({"title": title, "share": share, "view": view, "blurb": blurb, "deck": deck, **extra})

    review_view = "review" if due else "focus"
    if deck_choice == "New material" or not has_cards:
        add("Capture your material", 0.30, "capture", "Break the new material into small study bits and Q/A cards before anything else. One idea per card.")
        if "mnemonics" in habits:
            add("Build memory hooks", 0.20, "tools", "Turn the trickiest new terms into acronyms or a mini-story before you try to recall them cold.")
        add("First recall attempt", 0.30, "quiz", "Close your notes and try to recall each card. Getting it wrong now still helps it stick.", quiz_mode="self")
        add("Schedule spaced review", 0.20, "review", "Rate what you just captured so the scheduler brings it back at the right time.")
    elif minutes <= SHORT_SESSION_MINUTES:
        # Too short to split usefully: one review block and one quick check.
        add("Quick review", 0.7, review_view, "Clear the most important cards first. " + review_detail(len(due), minutes))
        add("Quick check", 0.3, "quiz", "A fast self-test to finish on a win.", quiz_mode="choices")
    elif goal == "cram":
        if due or weak:
            add("Warm-up: quick multiple choice", 0.15, "quiz", "Fast recall check to see where you stand before the clock starts.", quiz_mode="choices")
        add("Focused review", 0.45, review_view, "Work through due and weak cards with Smart Check, prioritising the ones you keep missing. " + review_detail(len(due), round(minutes * 0.45)))
        if "repetition" in habits:
            add("Repetition drilling", 0.20, "shuffle", "Run the 5, 5-4, 5-4-3, 3-2-1 pattern on your weakest items for extra reps right before the test.")
        add("Final confidence pass", 0.20, "quiz", "One more quick pass. Multiple choice if you're short on time, self-check if you have a few extra minutes.", quiz_mode=self_check_mode)
    elif goal == "exam_prep":
        if due or weak:
            add("Quick warm-up", 0.12, "quiz", "A short recall check to activate what you already know before digging in.", quiz_mode="choices")
        add("Spaced review", 0.33, review_view, "Work through what's due with Smart Check so nothing quietly slips. " + review_detail(len(due), round(minutes * 0.33)))
        if "mnemonics" in habits:
            add("Strengthen weak hooks", 0.15, "tools", "Build a fresh association for your shakiest cards while there's still time to let it sink in.")
        add("Repetition drilling", 0.20, "shuffle", "Run the repetition path on your weakest items so they're solid well before exam day.")
        add("Self-check quiz", 0.20, "quiz", "Confirm recall without leaning on the saved answer.", quiz_mode=self_check_mode)
    else:
        add("Spaced review", 0.35, review_view, "Work through everything due with Smart Check so your intervals stay honest. " + review_detail(len(due), round(minutes * 0.35)))
        if "mnemonics" in habits:
            add("Strengthen weak hooks", 0.20, "tools", "Build a fresh association for anything you recently rated Again or Review.")
        if "repetition" in habits:
            add("Repetition path", 0.20, "shuffle", "Walk the backward-then-forward pattern on your weakest deck items.")
        add("Self-check quiz", 0.15 if (habits & {"mnemonics", "repetition"}) else 0.25, "quiz", "Confirm recall without leaning on the saved answer.", quiz_mode=self_check_mode)

    if fresh and has_cards and deck_choice != "New material" and minutes > SHORT_SESSION_MINUTES and goal != "cram":
        new_limit = min(len(fresh), max(3, min(MAX_NEW_CARDS_PER_SESSION, int(study_minutes * 0.2 / MINUTES_PER_NEW_CARD))))
        add("Learn new cards", 0.15, "focus", f"Meet up to {plural(new_limit, 'new card')} ({len(fresh)} waiting). Keeping new cards to a steady number stops tomorrow's reviews from piling up.")
    if "explain" in habits and has_cards and minutes > SHORT_SESSION_MINUTES:
        add("Explain it back", 0.15, "testing", "Pick a card and explain the answer out loud or in writing as if teaching a friend. Gaps in the explanation show exactly what to review.")

    # Interleaving: mixing topics feels harder but transfers better to tests.
    if has_cards and deck is None and len(deck_names) > 1 and goal != "cram" and deck_choice != "New material" and minutes >= 30:
        add("Mixed practice across decks", 0.15, "quiz", f"Shuffle questions from {plural(len(deck_names), 'deck')} together. Switching topics is harder, and that is what makes it stick.", quiz_mode=self_check_mode)
    if "games" in habits and minutes >= 20 and deck_choice != "New material" and has_cards:
        add("Short recall game break", 0.10, "games", "A quick puzzle round to reset attention between study blocks.")

    if minutes >= 30 and has_cards:
        add("Wrap up", 0.06, "stats", "Look at what you got done and what's due tomorrow. Ending with a quick look back helps the session stick.")

    budget = study_minutes if breaks else minutes
    for step, allotted in zip(steps, allocate_minutes([step["share"] for step in steps], budget)):
        step["minutes"] = allotted
    if breaks:
        steps = insert_breaks(steps, minutes - budget)
    return steps


def insert_breaks(steps, break_minutes):
    """Put a short rest after each ~25 minutes of study (never at the very end)."""
    count = break_minutes // BREAK_MINUTES
    if count <= 0:
        return steps
    planned = []
    since_break = 0
    for index, step in enumerate(steps):
        planned.append(step)
        since_break += step["minutes"]
        if count and since_break >= FOCUS_BLOCK_MINUTES - 5 and index < len(steps) - 1:
            planned.append({
                "title": "Rest break", "share": 0, "view": "break", "deck": step.get("deck"), "minutes": BREAK_MINUTES,
                "blurb": "Stand up, stretch, get water, look away from the screen. Short rests keep attention sharp for the next block.",
            })
            count -= 1
            since_break = 0
    # Any break time that didn't fit between steps goes back to the longest step.
    if count:
        longest = max((step for step in planned if step["view"] != "break"), key=lambda step: step["minutes"])
        longest["minutes"] += count * BREAK_MINUTES
    return planned


def build_multi_day_plan(store, total_days, deck_choice, habits, goal, start=None):
    """Plan several days ahead, projecting which cards come due on each day."""
    total_days = max(1, int(total_days))
    base_minutes = 45 if goal == "cram" else 30
    today = start or date.today()
    days = []
    for day_number in range(1, total_days + 1):
        on = (today + timedelta(days=day_number - 1)).isoformat()
        progress = day_number / total_days
        kind = "study"
        day_deck_choice = deck_choice
        phase_goal = goal
        minutes = base_minutes

        if deck_choice == "New material":
            # Learn on day 1, then revisit on expanding intervals; other days
            # are short maintenance so the new cards get time to settle.
            if day_number == 1:
                kind = "learn"
            elif day_number in NEW_MATERIAL_REVIEW_DAYS:
                kind, day_deck_choice = "review", "All decks"
            else:
                kind, day_deck_choice, minutes = "maintenance", "All decks", 15
        elif goal == "exam_prep":
            if progress <= 0.34:
                phase_goal = "long_term"
            elif progress <= 0.75:
                phase_goal = "exam_prep"
            else:
                phase_goal, minutes = "cram", base_minutes + 15
        if goal in ("exam_prep", "cram") and total_days >= 3 and day_number == total_days:
            # The day before a test: a light confidence pass, then rest.
            kind, phase_goal, minutes = "light", "cram", 20

        due = len(store.due_cards(None if day_deck_choice in ("All decks", "New material") else day_deck_choice, on=on))
        if kind in ("study", "review"):
            # Make room for a heavy review day instead of a fixed block.
            minutes = max(minutes, min(90, round(due * MINUTES_PER_CARD) + 15))
        steps = build_study_plan(store, minutes, day_deck_choice, habits, phase_goal, on=on)
        if kind == "light":
            steps[-1]["blurb"] += " Then stop for the day — sleep does more for recall than a late-night cram."
        days.append({"day": day_number, "date": on, "kind": kind, "due": due, "minutes": minutes, "steps": steps})
    return days


def plan_minutes(settings):
    """Session length in minutes for a saved plan's time choice (per day for day/week plans)."""
    unit = settings.get("unit", "minutes")
    try:
        amount = int(settings.get("amount", 30))
    except (TypeError, ValueError):
        amount = 30
    if unit == "hours":
        return amount * 60
    if unit == "minutes":
        return amount
    return None


GOAL_KEYS = {"Cram": "cram", "Exam prep": "exam_prep", "Long-term retention": "long_term"}


def plan_for_today(store, plan=None, today=None):
    """Today's part of the saved plan: a title line, the steps, and whether it has ended."""
    plan = plan if plan is not None else getattr(store, "study_plan", None)
    if not plan:
        return None
    settings = plan.get("settings", {})
    today = today or date.today()
    deck_choice = settings.get("deck", "All decks")
    goal_label = settings.get("goal_label", "Long-term retention")
    goal = GOAL_KEYS.get(goal_label, "long_term")
    habits = set(settings.get("habits", []))
    minutes = plan_minutes(settings)
    if minutes is not None:
        steps = build_study_plan(store, minutes, deck_choice, habits, goal)
        return {"title": f"{minutes} min • {goal_label} • {deck_choice}", "steps": steps, "finished": False, "day": None, "total_days": None}
    try:
        created = date.fromisoformat(plan.get("created"))
    except (TypeError, ValueError):
        created = today
    try:
        amount = int(settings.get("amount", 1))
    except (TypeError, ValueError):
        amount = 1
    total_days = amount * (7 if settings.get("unit") == "weeks" else 1)
    day_number = (today - created).days + 1
    if day_number > total_days:
        return {"title": f"Your {total_days}-day plan is complete", "steps": [], "finished": True, "day": day_number, "total_days": total_days}
    days = build_multi_day_plan(store, total_days, deck_choice, habits, goal, start=created)
    day = days[max(0, day_number - 1)]
    kind = {"learn": "Learn day", "review": "Spaced review day", "maintenance": "Short maintenance day", "light": "Light day", "study": "Study day"}.get(day["kind"], "Study day")
    return {"title": f"Day {day_number} of {total_days} • {kind} • {day['minutes']} min", "steps": day["steps"], "finished": False, "day": day_number, "total_days": total_days}
