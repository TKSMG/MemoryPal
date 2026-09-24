from datetime import date, timedelta

STUDY_HABIT_OPTIONS = [
    ("mnemonics", "I remember better with mnemonics, stories, or images"),
    ("repetition", "I like structured repetition drilling"),
    ("quick_mc", "I prefer quick multiple choice over typing answers"),
    ("games", "I like short recall-game breaks to reset focus"),
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

    # Interleaving: mixing topics feels harder but transfers better to tests.
    if has_cards and deck is None and len(deck_names) > 1 and goal != "cram" and deck_choice != "New material" and minutes >= 30:
        add("Mixed practice across decks", 0.15, "quiz", f"Shuffle questions from {plural(len(deck_names), 'deck')} together. Switching topics is harder, and that is what makes it stick.", quiz_mode=self_check_mode)
    if "games" in habits and minutes >= 20 and deck_choice != "New material" and has_cards:
        add("Short recall game break", 0.10, "games", "A quick puzzle round to reset attention between study blocks.")

    for step, allotted in zip(steps, allocate_minutes([step["share"] for step in steps], minutes)):
        step["minutes"] = allotted
    return steps


def build_multi_day_plan(store, total_days, deck_choice, habits, goal):
    """Plan several days ahead, projecting which cards come due on each day."""
    total_days = max(1, int(total_days))
    base_minutes = 45 if goal == "cram" else 30
    today = date.today()
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
