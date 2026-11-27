from datetime import date, timedelta

from . import techniques
from .core import split_study_bits
from .store import capture_deck, plain_text, source_quote

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
# The longest plans the app makes (a year of weeks; a day of minutes). A
# synced plan asking for more is cut to this rather than built day by day.
MAX_PLAN_DAYS = 400
MAX_PLAN_MINUTES = 24 * 60


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


def review_detail(due_count, share_minutes, per_card=MINUTES_PER_CARD):
    if not due_count:
        return "Nothing is due, so this works through weak and fresh cards instead."
    needed = max(1, round(due_count * per_card))
    if needed > share_minutes:
        return f"{plural(due_count, 'card')} due (about {needed} min) — do the oldest first; the rest can wait for tomorrow."
    return f"{plural(due_count, 'card')} due, about {needed} min."


# ------------------------------------------------------------ the learner
# What the practice log (store.practice_log, this device only) says about the
# person. Each finding needs enough answers behind it before the plan uses it.
PROFILE_DAYS = 60
MIN_PACE_ANSWERS = 15
MIN_METHOD_ANSWERS = 8
MIN_HOOK_ANSWERS = 6
MIN_TIME_ANSWERS = 10
RECALL_METHODS = ("review", "quiz", "quiz_choices", "talkback", "tutor")
TIMES_OF_DAY = (("morning", 5, 12), ("afternoon", 12, 17), ("evening", 17, 22))
GENTLE_PERSONAS = ("everyday", "caregiver")
GENTLE_FOCUS_MINUTES = 15
# Missing this share of answers in the last week slows new cards down.
STRUGGLING_MISS_RATE = 0.4


def time_of_day(hour):
    return next((name for name, start, stop in TIMES_OF_DAY if start <= hour < stop), "night")


def recall_rate(entries):
    return sum(1 for entry in entries if entry["ok"]) / len(entries) if entries else 0.0


def learner_profile(store, today=None):
    """Pace, best methods, best technique and best time of day from the practice log."""
    today = today or date.today()
    cutoff = (today - timedelta(days=PROFILE_DAYS)).isoformat()
    week = (today - timedelta(days=7)).isoformat()
    log = [entry for entry in (getattr(store, "practice_log", None) or []) if entry["at"][:10] >= cutoff]
    accessibility = getattr(store, "accessibility", None) or {}
    timed = sorted(entry["sec"] for entry in log if entry["sec"] >= 3 and entry["m"] in RECALL_METHODS)
    if len(timed) >= MIN_PACE_ANSWERS:
        # The middle answer's time, plus a few seconds to rate it.
        per_card = min(2.5, max(0.3, timed[len(timed) // 2] / 60 + 0.1))
        measured = True
    else:
        per_card = MINUTES_PER_CARD * (1.5 if accessibility.get("more_time") else 1)
        measured = False
    methods = {}
    for method in sorted({entry["m"] for entry in log}):
        entries = [entry for entry in log if entry["m"] == method]
        methods[method] = {"answers": len(entries), "rate": recall_rate(entries)}
    recall = [entry for entry in log if entry["m"] in RECALL_METHODS]
    hooks = {}
    for kind in sorted({entry["hook"] for entry in recall}):
        entries = [entry for entry in recall if entry["hook"] == kind]
        hooks[kind] = {"answers": len(entries), "rate": recall_rate(entries)}
    plain = hooks.get("", {"answers": 0, "rate": 0.0})
    best_hook = ""
    best_rate = 0.5
    for kind, found in hooks.items():
        if kind in ("", "own") or found["answers"] < MIN_HOOK_ANSWERS:
            continue
        beats_plain = plain["answers"] < MIN_HOOK_ANSWERS or found["rate"] >= plain["rate"] + 0.1
        if beats_plain and found["rate"] > best_rate:
            best_hook, best_rate = kind, found["rate"]
    recent = [entry for entry in recall if entry["at"][:10] >= week]
    miss_rate = 1 - recall_rate(recent) if len(recent) >= 10 else None
    times = {}
    for name in [name for name, _start, _stop in TIMES_OF_DAY] + ["night"]:
        entries = [entry for entry in recall if time_of_day(int(entry["at"][11:13])) == name]
        if len(entries) >= MIN_TIME_ANSWERS:
            times[name] = {"answers": len(entries), "rate": recall_rate(entries)}
    best_time, best_hour = "", None
    if len(times) >= 2:
        ranked = sorted(times, key=lambda name: (-times[name]["rate"], name))
        if times[ranked[0]]["rate"] - times[ranked[-1]]["rate"] >= 0.1:
            best_time = ranked[0]
            counts = {}
            for entry in recall:
                hour = int(entry["at"][11:13])
                if time_of_day(hour) == best_time:
                    counts[hour] = counts.get(hour, 0) + 1
            best_hour = sorted(counts, key=lambda hour: (-counts[hour], hour))[0]
    return {
        "answers": len(log),
        "minutes_per_card": per_card,
        "measured_pace": measured,
        "methods": methods,
        "hooks": hooks,
        "best_hook": best_hook,
        "miss_rate": miss_rate,
        "best_time": best_time,
        "best_hour": best_hour,
    }


def best_study_hour(store, today=None):
    """The hour (0-23) this person tends to remember best at, or None until the log can tell."""
    return learner_profile(store, today)["best_hour"]


def plan_insights(store, today=None):
    """What the plan has learned about the person, in plain sentences (empty until it knows something)."""
    profile = learner_profile(store, today)
    lines = []
    if profile["measured_pace"]:
        seconds = int(profile["minutes_per_card"] * 60 + 0.5)
        lines.append(f"You take about {seconds} seconds a card, so the plan times reviews to your pace.")
    if profile["best_hook"]:
        lines.append(f"Cards with {techniques.TECHNIQUE_TITLES[profile['best_hook']].lower()} hooks are the ones you remember best, so the plan uses it more.")
    quiz = profile["methods"].get("quiz")
    if quiz and quiz["answers"] >= MIN_METHOD_ANSWERS and quiz["rate"] < 0.5:
        lines.append("Typed quiz answers have been hard lately, so quizzes start with multiple choice.")
    if profile["miss_rate"] is not None and profile["miss_rate"] >= STRUGGLING_MISS_RATE:
        lines.append("You've missed quite a few this week, so the plan adds fewer new cards until they settle.")
    if profile["best_time"]:
        lines.append(f"You remember best in the {profile['best_time']}." if profile["best_time"] != "night" else "You remember best at night.")
    return lines


# ------------------------------------------------------------- the material
MAX_NOTE_CAPTURES = 40
MAX_NOTE_BITS = 60


def technique_item(card):
    back = " ".join(str(card.back or "").split())
    return back if back and len(back.split()) <= 8 else " ".join(str(card.front or "").split())


def deck_of(card):
    return card.deck or "General"


def focus_deck(store, deck, weak):
    """The set a step works on: the plan's own, else the one with the most weak cards."""
    if deck:
        return deck
    counts = {}
    for card in weak:
        counts[deck_of(card)] = counts.get(deck_of(card), 0) + 1
    if not counts:
        for card in store.cards:
            counts[deck_of(card)] = counts.get(deck_of(card), 0) + 1
    return sorted(counts, key=lambda name: (-counts[name], name))[0] if counts else None


def card_index(cards):
    """Plain text of some cards, ready for quick "is this note covered?" checks."""
    by_word = {}
    for card in cards:
        for text in (plain_text(card.back), plain_text(source_quote(card))[:80]):
            if len(text) >= 4:
                by_word.setdefault(text.split()[0], []).append(text)
    joined = "\n".join(f"{plain_text(card.front)} {plain_text(card.back)}" for card in cards)
    return by_word, joined


def bit_covered(words, index):
    """A note part is a card already when a card's answer or quote is in it, or it opens a card."""
    by_word, joined = index
    if words[:40] in joined:
        return True
    for word in set(words.split()):
        if any(text in words for text in by_word.get(word, ())):
            return True
    return False


def notes_not_yet_cards(store, deck, memo=None):
    """(notes, how many of their parts no card covers) for the notes with the most, or (None, 0)."""
    memo = {} if memo is None else memo
    key = ("notes", deck)
    if key in memo:
        return memo[key]
    best, best_count = None, 0
    for capture in list(getattr(store, "captures", None) or [])[:MAX_NOTE_CAPTURES]:
        owner = capture_deck(capture)
        if deck and owner != deck:
            continue
        if ("cards", owner) not in memo:
            memo[("cards", owner)] = card_index([card for card in store.cards if not owner or deck_of(card) == owner])
        index = memo[("cards", owner)]
        count = 0
        for bit in (capture.chunks or split_study_bits(capture.notes))[:MAX_NOTE_BITS]:
            words = plain_text(bit)
            if len(words.split()) >= 4 and not bit_covered(words, index):
                count += 1
        if count > best_count:
            best, best_count = capture, count
    memo[key] = (best, best_count)
    return memo[key]


def notes_behind_weak(store, weak, memo=None):
    """(card, notes, bit) for the weakest card whose source notes can be found, or (None, None, -1)."""
    memo = {} if memo is None else memo
    key = ("weak", tuple(card.id for card in weak[:20]))
    if key not in memo:
        memo[key] = (None, None, -1)
        for card in weak[:20]:
            capture, bit = store.source_notes(card)
            if capture is not None:
                memo[key] = (card, capture, bit)
                break
    return memo[key]


def day_turn(on):
    try:
        day = date.fromisoformat(on) if on else date.today()
    except (TypeError, ValueError):
        day = date.today()
    return (day - date(1970, 1, 1)).days


TECHNIQUE_REASONS = {
    "acronym": "A few short items with different first letters fit one word made of their initials.",
    "chunk": "Numbers and long lists are easier in small groups of three.",
    "chain": "Longer ideas link well, each one handing a clue to the next.",
    "peg": "Up to ten items hang on rhyming number pictures, so you can recall them in order or by number.",
    "palace": "Placing each item along a walk through a home you know keeps a long list in order.",
    "story": "A short scene for each item turns a dry list into something you can picture.",
}


def build_study_plan(store, minutes, deck_choice, habits, goal, on=None, since=None, memo=None):
    """Build one session's steps.

    `on` projects due cards for a future ISO date; `since` counts only cards
    that come due after that date (the earlier days of a plan clear the rest).
    The person's practice log, persona, More time setting and notes shape it.
    `memo` keeps the notes checks between the days of one multi-day plan.
    """
    memo = {} if memo is None else memo
    minutes = max(MIN_STEP_MINUTES, int(minutes))
    habits = set(habits or ())
    deck = None if deck_choice in ("All decks", "New material") else deck_choice
    due = store.due_cards(deck, on=on, since=since)
    weak = [card for card in store.weak_cards() if not deck or deck_of(card) == deck]
    fresh = [card for card in store.cards if card.repetitions == 0 and card.lapses == 0 and (not deck or deck_of(card) == deck)]
    deck_names = {deck_of(card) for card in store.cards if not deck or deck_of(card) == deck}
    has_cards = bool(deck_names)
    today = date.fromisoformat(on) if on else None
    profile = learner_profile(store, today)
    per_card = profile["minutes_per_card"]
    persona = (getattr(store, "onboarding", None) or {}).get("persona", "")
    gentle = persona in GENTLE_PERSONAS and goal == "long_term" and has_cards and deck_choice != "New material"
    focus_block = GENTLE_FOCUS_MINUTES if gentle else FOCUS_BLOCK_MINUTES
    breaks = ("breaks" in habits or gentle) and minutes >= 2 * focus_block - 5
    study_minutes = minutes - (BREAK_MINUTES * max(0, round(minutes / (focus_block + BREAK_MINUTES)) - 1) if breaks else 0)
    quiz = profile["methods"].get("quiz")
    typed_is_hard = bool(quiz and quiz["answers"] >= MIN_METHOD_ANSWERS and quiz["rate"] < 0.5)
    self_check_mode = "choices" if "quick_mc" in habits or typed_is_hard else "self"
    struggling = profile["miss_rate"] is not None and profile["miss_rate"] >= STRUGGLING_MISS_RATE
    turn = day_turn(on)
    focus = focus_deck(store, deck, weak) if has_cards else None
    steps = []

    def add(title, share, view, blurb, **extra):
        steps.append({"title": title, "share": share, "view": view, "blurb": blurb, "deck": deck, **extra})

    def add_technique(title, share, fallback):
        """A memory hook step that names the technique that suits the set (and the person)."""
        items = [technique_item(card) for card in reversed(store.cards) if deck_of(card) == focus] if focus else []
        kind = techniques.pick_technique(items, profile["best_hook"], turn)
        if not kind:
            add(title, share, "tools", fallback)
            return
        name = techniques.TECHNIQUE_TITLES[kind]
        blurb = f"Make a {name.lower()} from {focus}'s cards and save it as their hooks. {TECHNIQUE_REASONS[kind]}"
        if kind == profile["best_hook"]:
            blurb += f" Your cards with {name.lower()} hooks are the ones you remember best."
        steps.append({"title": f"{title}: {name.lower()}", "share": share, "view": "tools", "blurb": blurb, "deck": focus, "technique": kind})

    def add_puzzle(title, share, blurb, daily=False):
        if daily:
            add(title, share, "games", blurb, puzzle_kind="daily")
        else:
            add(title, share, "games", blurb, puzzle_kind="pairs" if focus else "sequence", **({"deck": focus} if focus else {}))

    def add_notes_steps():
        capture, count = notes_not_yet_cards(store, deck, memo)
        if capture is not None and count >= 2:
            add("Turn notes into cards", 0.12, "notes", f"\u201c{capture.title or 'Your notes'}\u201d has {plural(count, 'part')} that aren't cards yet. Make cards from them so the plan can bring them back.", capture_id=capture.id)
        if minutes >= 20:
            card, source, bit = notes_behind_weak(store, weak, memo)
            if card is not None:
                add("Reread the notes behind a missed card", 0.08, "notes", f"You keep missing \u201c{' '.join(card.front.split())[:60]}\u201d. Read the part of \u201c{source.title or 'your notes'}\u201d it came from before you review.", capture_id=source.id, bit=bit)

    review_view = "review" if due else "focus"
    if deck_choice == "New material" or not has_cards:
        capture, count = notes_not_yet_cards(store, None, memo)
        if capture is not None and count >= 2:
            add("Capture your material", 0.30, "notes", f"Start with \u201c{capture.title or 'your notes'}\u201d: {plural(count, 'part')} aren't cards yet. One idea per card.", capture_id=capture.id)
        else:
            add("Capture your material", 0.30, "capture", "Break the new material into small study bits and Q/A cards before anything else. One idea per card.")
        if "mnemonics" in habits:
            add("Build memory hooks", 0.20, "tools", "Turn the trickiest new terms into acronyms or a mini-story before you try to recall them cold.")
        add("First recall attempt", 0.30, "quiz", "Close your notes and try to recall each card. Getting it wrong now still helps it stick.", quiz_mode="self")
        add("Schedule spaced review", 0.20, "review", "Rate what you just captured so the scheduler brings it back at the right time.")
    elif gentle:
        # Calm, short steps for everyday memory: familiar things first, the
        # same few things often (spaced retrieval), and a game from their own cards.
        add("Gentle review", 0.7 if minutes <= SHORT_SESSION_MINUTES else 0.4, "review", "A few cards at a calm pace, people, routines and places first. Take as long as you need on each one.", review_mode="gentle")
        if minutes > SHORT_SESSION_MINUTES:
            add("Repetition path", 0.25, "shuffle", "Recall a short list in growing runs. Coming back to the same few things often is one of the best ways to keep them.")
            if "mnemonics" in habits:
                add_technique("Make a memory picture", 0.15, "Turn something you keep forgetting into a picture or a short story.")
            if "explain" in habits or (getattr(store, "accessibility", None) or {}).get("read_aloud"):
                add("Listen and answer", 0.15, "talkback", "Hear each question read aloud and answer out loud, in your own words.")
        add_puzzle("Today's puzzles", 0.3 if minutes <= SHORT_SESSION_MINUTES else 0.2, "Three short, friendly games picked for you, everyday memory first, getting a little harder as you improve.", daily=True)
        if fresh and minutes > SHORT_SESSION_MINUTES:
            add("Meet a few new cards", 0.1, "review", f"Look at {plural(min(3, len(fresh)), 'new card')}, no more. A few at a time is plenty.", review_mode="new")
        if minutes >= 20:
            add("See how you did", 0.06, "stats", "A quick look at what you practiced today.")
    elif minutes <= SHORT_SESSION_MINUTES:
        # Too short to split usefully: one review block and one quick check.
        add("Quick review", 0.7, review_view, "Clear the most important cards first. " + review_detail(len(due), minutes, per_card))
        add("Quick check", 0.3, "quiz", "A fast self-test to finish on a win.", quiz_mode="choices")
    elif goal == "cram":
        if due or weak:
            add("Warm-up: quick multiple choice", 0.15, "quiz", "Fast recall check to see where you stand before the clock starts.", quiz_mode="choices")
        add("Focused review", 0.45, review_view, "Work through due and weak cards with Smart Check, prioritising the ones you keep missing. " + review_detail(len(due), round(minutes * 0.45), per_card))
        if "repetition" in habits:
            add("Repetition drilling", 0.20, "shuffle", "Run the 5, 5-4, 5-4-3, 3-2-1 pattern on your weakest cards for extra reps right before the test.")
        add("Final confidence pass", 0.20, "quiz", "One more quick pass. Multiple choice if you're short on time, self-check if you have a few extra minutes.", quiz_mode=self_check_mode)
    elif goal == "exam_prep":
        if due or weak:
            add("Quick warm-up", 0.12, "quiz", "A short recall check to activate what you already know before digging in.", quiz_mode="choices")
        add("Spaced review", 0.33, review_view, "Work through what's due with Smart Check so nothing quietly slips. " + review_detail(len(due), round(minutes * 0.33), per_card))
        if "mnemonics" in habits:
            add_technique("Strengthen weak hooks", 0.15, "Build a fresh association for your shakiest cards while there's still time to let it sink in.")
        add("Repetition drilling", 0.20, "shuffle", "Run the repetition path on your weakest cards so they're solid well before exam day.")
        add("Self-check quiz", 0.20, "quiz", "Confirm recall without leaning on the saved answer.", quiz_mode=self_check_mode)
    else:
        add("Spaced review", 0.35, review_view, "Work through everything due with Smart Check so your intervals stay honest. " + review_detail(len(due), round(minutes * 0.35), per_card))
        if "mnemonics" in habits:
            add_technique("Strengthen weak hooks", 0.20, "Build a fresh association for anything you recently rated Again or Review.")
        if "repetition" in habits:
            add("Repetition path", 0.20, "shuffle", "Walk the backward-then-forward pattern on your weakest cards until each one comes easily.")
        add("Self-check quiz", 0.15 if (habits & {"mnemonics", "repetition"}) else 0.25, "quiz", "Confirm recall without leaning on the saved answer.", quiz_mode=self_check_mode)

    if not gentle and fresh and has_cards and deck_choice != "New material" and minutes > SHORT_SESSION_MINUTES and goal != "cram":
        new_limit = min(len(fresh), max(3, min(MAX_NEW_CARDS_PER_SESSION, int(study_minutes * 0.2 / MINUTES_PER_NEW_CARD))))
        if struggling:
            new_limit = min(len(fresh), max(2, new_limit // 2))
            add("Learn new cards", 0.10, "review", f"Meet up to {plural(new_limit, 'new card')} ({len(fresh)} waiting). You've missed quite a few this week, so fewer new cards today while those settle.", review_mode="new")
        else:
            add("Learn new cards", 0.15, "review", f"Meet up to {plural(new_limit, 'new card')} ({len(fresh)} waiting). Keeping new cards to a steady number stops tomorrow's reviews from piling up.", review_mode="new")
    if not gentle and "explain" in habits and has_cards and minutes > SHORT_SESSION_MINUTES:
        add("Explain it back", 0.15, "talkback", "Use Talk-back: hear each question and answer out loud in your own words, as if teaching a friend. With AI on, the live tutor can ask you follow-up questions instead.")
    if has_cards and deck_choice != "New material" and minutes > SHORT_SESSION_MINUTES and goal != "cram" and not gentle:
        add_notes_steps()

    # Interleaving: mixing topics feels harder but transfers better to tests.
    if not gentle and has_cards and deck is None and len(deck_names) > 1 and goal != "cram" and deck_choice != "New material" and minutes >= 30:
        add("Mixed practice across decks", 0.15, "quiz", f"Shuffle questions from {plural(len(deck_names), 'deck')} together. Switching topics is harder, and that is what makes it stick.", quiz_mode=self_check_mode)
    if not gentle and "games" in habits and minutes >= 20 and deck_choice != "New material" and has_cards:
        add_puzzle("Short recall game break", 0.10, f"A quick Pair recall round from {focus}'s cards to reset attention between study blocks.")

    if not gentle and minutes >= 30 and has_cards:
        wrap = "Look at what you got done and what's due tomorrow. Ending with a quick look back helps the session stick."
        if profile["best_time"]:
            wrap += f" You remember best in the {profile['best_time']}, so that's a good time for the next session." if profile["best_time"] != "night" else " You remember best at night, so that's a good time for the next session."
        add("Wrap up", 0.06, "stats", wrap)

    budget = study_minutes if breaks else minutes
    for step, allotted in zip(steps, allocate_minutes([step["share"] for step in steps], budget)):
        step["minutes"] = allotted
    if breaks:
        steps = insert_breaks(steps, minutes - budget, focus_block)
    return steps


def insert_breaks(steps, break_minutes, focus_block=FOCUS_BLOCK_MINUTES):
    """Put a short rest after each ~25 minutes of study (15 for gentle plans; never at the very end)."""
    count = break_minutes // BREAK_MINUTES
    if count <= 0:
        return steps
    planned = []
    since_break = 0
    for index, step in enumerate(steps):
        planned.append(step)
        since_break += step["minutes"]
        if count and since_break >= focus_block - 5 and index < len(steps) - 1:
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
    total_days = max(1, min(MAX_PLAN_DAYS, int(total_days)))
    gentle = (getattr(store, "onboarding", None) or {}).get("persona", "") in GENTLE_PERSONAS and goal == "long_term"
    base_minutes = 45 if goal == "cram" else 20 if gentle else 30
    longest = 45 if gentle else 90
    per_card = learner_profile(store, start)["minutes_per_card"]
    today = start or date.today()
    memo = {}
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

        # Day 1 faces everything already due; later days only what newly
        # comes due, since each day's review clears the earlier backlog.
        # (Counting the backlog again on every day made each day look heavy.)
        since = None if day_number == 1 else (today + timedelta(days=day_number - 2)).isoformat()
        due = len(store.due_cards(None if day_deck_choice in ("All decks", "New material") else day_deck_choice, on=on, since=since))
        if kind in ("study", "review"):
            # Make room for a heavy review day instead of a fixed block.
            minutes = max(minutes, min(longest, round(due * per_card) + 15))
        steps = build_study_plan(store, minutes, day_deck_choice, habits, phase_goal, on=on, since=since, memo=memo)
        if kind == "light":
            steps[-1]["blurb"] += " Then stop for the day — sleep does more for recall than a late-night cram."
        days.append({"day": day_number, "date": on, "kind": kind, "due": due, "minutes": minutes, "steps": steps})
    return days


def plan_minutes(settings):
    """Session length in minutes for a saved plan's time choice (per day for day/week plans)."""
    unit = settings.get("unit", "minutes")
    try:
        amount = int(settings.get("amount", 30))
    except (TypeError, ValueError, OverflowError):
        amount = 30
    if unit == "hours":
        return min(MAX_PLAN_MINUTES, amount * 60)
    if unit == "minutes":
        return min(MAX_PLAN_MINUTES, amount)
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
    habits = settings.get("habits") if isinstance(settings.get("habits"), list) else []
    habits = {habit for habit in habits if isinstance(habit, str)}
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
    except (TypeError, ValueError, OverflowError):
        amount = 1
    total_days = min(MAX_PLAN_DAYS, amount * (7 if settings.get("unit") == "weeks" else 1))
    day_number = max(1, (today - created).days + 1)  # a plan made in a later time zone starts today
    if day_number > total_days:
        return {"title": f"Your {total_days}-day plan is complete", "steps": [], "finished": True, "day": day_number, "total_days": total_days}
    days = build_multi_day_plan(store, total_days, deck_choice, habits, goal, start=created)
    day = days[max(0, day_number - 1)]
    kind = {"learn": "Learn day", "review": "Spaced review day", "maintenance": "Short maintenance day", "light": "Light day", "study": "Study day"}.get(day["kind"], "Study day")
    return {"title": f"Day {day_number} of {total_days} • {kind} • {day['minutes']} min", "steps": day["steps"], "finished": False, "day": day_number, "total_days": total_days}
