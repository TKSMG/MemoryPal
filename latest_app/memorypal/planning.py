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


def build_study_plan(store, minutes, deck_choice, habits, goal):
    deck = None if deck_choice in ("All decks", "New material") else deck_choice
    due = store.due_cards(deck)
    weak = [card for card in store.weak_cards() if not deck or (card.deck or "General") == deck]
    steps = []

    def add(title, share, view, blurb, **extra):
        steps.append({"title": title, "share": share, "view": view, "blurb": blurb, "deck": deck, **extra})

    if deck_choice == "New material":
        add("Capture your material", 0.30, "capture", "Break the new material into small study bits and Q/A cards before anything else.")
        if "mnemonics" in habits:
            add("Build memory hooks", 0.20, "tools", "Turn the trickiest new terms into acronyms or a mini-story before you try to recall them cold.")
        add("First-pass self check", 0.30, "quiz", "Run a quick self-check quiz to see what's already sticking.", quiz_mode="self")
        add("Schedule spaced review", 0.20, "review", "Rate what you just captured so the scheduler brings it back at the right time.")
    elif goal == "cram":
        if due or weak:
            add("Warm-up: quick multiple choice", 0.15, "quiz", "Fast recall check to see where you stand before the clock starts.", quiz_mode="choices")
        add("Focused review", 0.45, "review" if due else "focus", "Work through due and weak cards with Smart Check, prioritizing the ones you keep missing.")
        if "repetition" in habits:
            add("Repetition drilling", 0.20, "shuffle", "Run the 5, 5-4, 5-4-3, 3-2-1 pattern on your weakest items for extra reps right before the test.")
        add("Final confidence pass", 0.20, "quiz", "One more quick pass. Multiple choice if you're short on time, self-check if you have a few extra minutes.", quiz_mode=("choices" if "quick_mc" in habits else "self"))
    elif goal == "exam_prep":
        if due or weak:
            add("Quick warm-up", 0.12, "quiz", "A short recall check to activate what you already know before digging in.", quiz_mode="choices")
        add("Spaced review", 0.33, "review" if due else "focus", "Work through what's due today with Smart Check so nothing quietly slips.")
        if "mnemonics" in habits:
            add("Strengthen weak hooks", 0.15, "tools", "Build a fresh association for your shakiest cards while there's still time to let it sink in.")
        add("Repetition drilling", 0.20, "shuffle", "Run the repetition path on your weakest items so they're solid well before exam day.")
        add("Self-check quiz", 0.20, "quiz", "Confirm recall without leaning on the saved answer.", quiz_mode=("choices" if "quick_mc" in habits else "self"))
    else:
        add("Spaced review", 0.35, "review" if due else "focus", "Work through everything due today with Smart Check so your intervals stay honest.")
        if "mnemonics" in habits:
            add("Strengthen weak hooks", 0.20, "tools", "Build a fresh association for anything you recently rated Again or Review.")
        if "repetition" in habits:
            add("Repetition path", 0.20, "shuffle", "Walk the backward-then-forward pattern on your weakest deck items.")
        add("Self-check quiz", 0.15 if (habits & {"mnemonics", "repetition"}) else 0.25, "quiz", "Confirm recall without leaning on the saved answer.", quiz_mode=("choices" if "quick_mc" in habits else "self"))

    if "games" in habits and minutes >= 20 and deck_choice != "New material":
        add("Short recall game break", 0.10, "games", "A quick puzzle round to reset attention between study blocks.")

    total_share = sum(step["share"] for step in steps) or 1
    running = 0
    for index, step in enumerate(steps):
        if index == len(steps) - 1:
            step["minutes"] = max(3, minutes - running)
        else:
            allotted = max(3, round(minutes * step["share"] / total_share))
            step["minutes"] = allotted
            running += allotted
    return steps


def build_multi_day_plan(store, total_days, deck_choice, habits, goal):
    total_days = max(1, int(total_days))
    daily_minutes = 45 if goal == "cram" else 30
    days = []
    for day_number in range(1, total_days + 1):
        progress = day_number / total_days
        day_deck_choice = deck_choice
        if deck_choice == "New material" and day_number > 1:
            day_deck_choice = "All decks"
        if goal == "exam_prep":
            if progress <= 0.34:
                phase_goal = "long_term"
            elif progress <= 0.75:
                phase_goal = "exam_prep"
            else:
                phase_goal = "cram"
        else:
            phase_goal = goal
        minutes = daily_minutes + (15 if goal == "exam_prep" and progress > 0.75 else 0)
        steps = build_study_plan(store, minutes, day_deck_choice, habits, phase_goal)
        days.append({"day": day_number, "minutes": minutes, "steps": steps})
    return days
