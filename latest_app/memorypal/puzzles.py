"""The memory puzzles: rounds, scoring, levels, saved results and today's mix.

The same logic as mobile/src/core/puzzles.ts (checked by the parity
fixtures), so a puzzle plays the same on the desktop and the phone.

Made with older players in mind: every answer can be tapped (typing is
optional), each game is a few short rounds that gently follow the player's
level, and a "Help me" clue is always there. Results stay on this device
(preferences["puzzles"]), never synced.

A round is plain JSON:
    {"kind", "level", "show": [lines to remember], "questions": [...], ...}
Most puzzles ask choice questions ({"prompt", "options", "answer"});
sequence, words, search and routine carry their own fields (see make_round).
"""

from datetime import date, timedelta

from .questions import Rng

ROUNDS = 4
DAILY_ROUNDS = 2
RECENT_MAX = 12
DAYS_MAX = 60
# A round counts as remembered when at least this share is right.
PASS_SHARE = 0.6

# kind, title, skill, first level, lowest, highest, what it asks, a tip.
# Skills: memory (remember then recall), attention (spot and keep track),
# thinking (sort and order), everyday (names, places, stories from daily life).
PUZZLES = [
    {"kind": "sequence", "title": "Number run", "skill": "memory", "first": 4, "low": 3, "high": 10,
     "body": "See a short run of numbers, then tap them back.",
     "tip": "Say the numbers in little groups, like a phone number."},
    {"kind": "words", "title": "Word recall", "skill": "memory", "first": 4, "low": 3, "high": 9,
     "body": "Look at a few words, then pick out the ones you saw.",
     "tip": "Picture the words together in one silly scene."},
    {"kind": "pairs", "title": "Pair recall", "skill": "memory", "first": 3, "low": 2, "high": 7,
     "body": "See word pairs, then remember each partner.",
     "tip": "Imagine the two things touching or talking to each other."},
    {"kind": "missing", "title": "What's missing?", "skill": "memory", "first": 4, "low": 3, "high": 9,
     "body": "Remember a list, then spot the one that has gone.",
     "tip": "Read the list once as a little sentence."},
    {"kind": "names", "title": "Names and faces", "skill": "everyday", "first": 2, "low": 2, "high": 6,
     "body": "Meet a few people, then remember who is who.",
     "tip": "Link the name to the detail: Rose grows roses."},
    {"kind": "places", "title": "Where did I put it?", "skill": "everyday", "first": 2, "low": 2, "high": 7,
     "body": "See where things were put down, then find them again.",
     "tip": "Picture yourself walking into the room and putting it down."},
    {"kind": "story", "title": "Story recall", "skill": "everyday", "first": 3, "low": 3, "high": 6,
     "body": "Read a short story, then answer a few questions about it.",
     "tip": "Ask yourself who, where, when and what as you read."},
    {"kind": "routine", "title": "Put it in order", "skill": "thinking", "first": 3, "low": 3, "high": 7,
     "body": "See the steps of an everyday task, then put them back in order.",
     "tip": "Walk through the task in your head, step by step."},
    {"kind": "sort", "title": "Sort it out", "skill": "thinking", "first": 4, "low": 4, "high": 10,
     "body": "Put each thing into the group where it belongs.",
     "tip": "Ask yourself where you would find it at home."},
    {"kind": "search", "title": "Spot them all", "skill": "attention", "first": 3, "low": 2, "high": 7,
     "body": "Find every copy of one word in a grid.",
     "tip": "Scan slowly, one row at a time, left to right."},
    {"kind": "nback", "title": "Same as before?", "skill": "attention", "first": 6, "low": 5, "high": 14,
     "body": "Words appear one at a time. Say if each matches the one before.",
     "tip": "Keep saying the last word quietly to yourself."},
]
KINDS = [puzzle["kind"] for puzzle in PUZZLES]
SKILLS = {"memory": "Memory", "attention": "Attention", "thinking": "Thinking", "everyday": "Everyday memory"}

WORDS = [
    "apple", "river", "candle", "garden", "pencil", "window", "basket", "violin", "mountain", "teacup",
    "ladder", "blanket", "compass", "lemon", "harbour", "button", "feather", "kettle", "meadow", "lantern",
    "pebble", "orchard", "saddle", "thimble", "piano", "carrot", "bridge", "clock", "honey", "jacket",
    "mirror", "parrot", "rocket", "tulip", "wagon", "anchor", "biscuit", "castle", "daisy", "engine",
]
CATEGORIES = [
    ("Fruit", ["apple", "banana", "pear", "cherry", "plum", "grape", "orange", "lemon", "peach", "mango"]),
    ("Animals", ["dog", "horse", "rabbit", "sheep", "goat", "duck", "fox", "owl", "cow", "mouse"]),
    ("In the kitchen", ["kettle", "teapot", "saucepan", "fork", "toaster", "ladle", "colander", "bread bin", "oven glove", "whisk"]),
    ("Clothes", ["scarf", "coat", "slippers", "cardigan", "hat", "gloves", "socks", "jumper", "boots", "shirt"]),
    ("In the garden", ["rose", "spade", "hose", "bench", "tulip", "rake", "hedge", "watering can", "daisy", "bird table"]),
    ("Getting about", ["bus", "train", "bicycle", "taxi", "car", "ferry", "tram", "scooter", "van", "aeroplane"]),
]
ROUTINES = [
    ["Fill the kettle", "Switch the kettle on", "Put a tea bag in the cup", "Pour in the hot water", "Wait for it to brew", "Take out the tea bag", "Add a splash of milk"],
    ["Put on your coat", "Check you have your keys", "Turn off the lights", "Step outside", "Close the front door", "Lock the door", "Check the handle"],
    ["Write the card", "Put it in the envelope", "Seal the envelope", "Write the address", "Stick on a stamp", "Walk to the post box", "Post the letter"],
    ["Fill the watering can", "Carry it to the plants", "Water the roots gently", "Check the soil is damp", "Pick off dead leaves", "Empty the can", "Put the can away"],
    ["Brush your teeth", "Wash your face", "Put on your pyjamas", "Take your evening tablets", "Set the alarm", "Get into bed", "Turn off the lamp"],
    ["Write a shopping list", "Take your bags", "Walk to the shop", "Find each thing on the list", "Pay at the till", "Carry the bags home", "Put the food away"],
]
NAMES = ["Margaret", "Arthur", "Joan", "Frank", "Rose", "Harold", "Betty", "Walter", "Irene", "George",
         "Dorothy", "Albert", "Priya", "Ahmed", "Mei", "Carlos", "Amara", "Kenji", "Nora", "Samuel"]
DETAILS = ["grows roses", "plays the piano", "has a dog called Max", "bakes bread", "was a teacher", "loves crosswords",
           "lives by the sea", "sings in a choir", "collects stamps", "walks every morning", "is learning to paint",
           "fixes old clocks", "keeps bees", "knits scarves", "was a nurse", "likes jazz"]
ITEMS = ["glasses", "keys", "wallet", "phone", "watch", "umbrella", "library book", "pill box", "purse", "remote control", "address book", "hat"]
ROOMS = ["Kitchen", "Bedroom", "Hallway", "Living room", "Bathroom", "Garden shed"]
STORY_FACTS = [
    # (question about the fact, options) – the story uses one option from each.
    ("day", "Which day was it?", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]),
    ("place", "Where did {name} go?", ["the market", "the library", "the park", "the bakery", "the post office", "the garden centre"]),
    ("item", "What did {name} buy?", ["a blue scarf", "fresh bread", "a birthday card", "tomato seeds", "a jar of honey", "a new teapot"]),
    ("friend", "Who was it for?", ["Joan", "Frank", "Betty", "Walter", "Irene", "Albert"]),
    ("weather", "What was the weather like?", ["raining", "sunny", "windy", "foggy", "snowing", "cloudy"]),
    ("travel", "How did {name} get there?", ["by bus", "by taxi", "by train", "by bicycle", "on foot", "by car"]),
]
STORY_NAMES = ["Margaret", "Arthur", "Rose", "Harold", "Dorothy", "George", "Priya", "Samuel"]

PRAISE = ["Well remembered!", "Lovely work!", "That's the way!", "Spot on!", "Brilliant!"]
GENTLE = ["Nearly. That one was tricky.", "Good try. Let's keep going.", "That was a hard one.", "Not quite, and that's fine."]


def puzzle(kind):
    return next((item for item in PUZZLES if item["kind"] == kind), PUZZLES[0])


def clamp_level(kind, level):
    info = puzzle(kind)
    if not isinstance(level, int) or isinstance(level, bool):
        level = info["first"]
    return max(info["low"], min(info["high"], level))


def _unique(items):
    seen = set()
    out = []
    for item in items:
        text = str(item).strip()
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            out.append(text)
    return out


def _short(text, words, chars):
    text = str(text or "").strip()
    return bool(text) and len(text.split()) <= words and len(text) <= chars


def material_from(cards):
    """A set's cards as puzzle material: short question/answer pairs and short answers."""
    pairs = []
    seen = set()
    for front, back in cards:
        if _short(front, 12, 80) and _short(back, 4, 40) and front.strip() not in seen:
            seen.add(front.strip())
            pairs.append([front.strip(), back.strip()])
    words = _unique(back for _front, back in cards if _short(back, 3, 30))
    return {"pairs": pairs, "words": words}


def enough_for(kind, material):
    """Enough of a set's material for this puzzle (otherwise the built-in words are used)."""
    if not material:
        return False
    if kind == "pairs":
        return len(material.get("pairs") or []) >= 3
    if kind in ("words", "missing", "search", "nback"):
        return len(material.get("words") or []) >= 6
    return False


def uses_material(kind):
    return kind in ("pairs", "words", "missing", "search", "nback")


def _word_pool(kind, material):
    return list(material["words"]) if enough_for(kind, material) else list(WORDS)


def _choice_options(answer, pool, count, rng):
    others = rng.shuffle([item for item in _unique(pool) if item.lower() != answer.lower()])
    return rng.shuffle([answer] + others[: count - 1])


def make_round(kind, level, seed, material=None):
    rng = Rng(seed)
    level = clamp_level(kind, level)
    base = {"kind": kind, "level": level, "show": [], "questions": []}
    if kind == "sequence":
        digits = []
        for _ in range(level):
            digit = str(rng.below(10))
            # Never three of the same in a row: it reads as a typo.
            while len(digits) >= 2 and digits[-1] == digit and digits[-2] == digit:
                digit = str(rng.below(10))
            digits.append(digit)
        # Shown in groups of three (chunking), the way phone numbers are read.
        return {**base, "show": [" ".join(digit_groups("".join(digits)))], "answer": "".join(digits)}
    if kind == "words":
        pool = _word_pool(kind, material)
        shown = rng.shuffle(list(pool))[:level]
        rest = [word for word in pool if word not in shown]
        if len(rest) < level:
            rest += [word for word in WORDS if word not in shown and word not in rest]
        options = rng.shuffle(shown + rng.shuffle(rest)[:level])
        return {**base, "show": shown, "options": options, "answer": list(shown)}
    if kind == "pairs":
        if enough_for(kind, material):
            pairs = rng.shuffle([list(pair) for pair in material["pairs"]])[:level]
        else:
            words = rng.shuffle(list(WORDS))[: level * 2]
            pairs = [[words[i * 2], words[i * 2 + 1]] for i in range(level)]
        partners = [b for _a, b in pairs]
        questions = [{"prompt": f"What went with “{a}”?", "options": rng.shuffle(list(partners)), "answer": b} for a, b in rng.shuffle([list(pair) for pair in pairs])]
        joiner = " → " if enough_for(kind, material) else " and "
        return {**base, "show": [f"{a}{joiner}{b}" for a, b in pairs], "questions": questions}
    if kind == "missing":
        pool = _word_pool(kind, material)
        shown = rng.shuffle(list(pool))[:level]
        gone = rng.below(len(shown))
        remaining = rng.shuffle([word for index, word in enumerate(shown) if index != gone])
        others = rng.shuffle([word for index, word in enumerate(shown) if index != gone])[:3]
        options = rng.shuffle([shown[gone]] + others)
        return {**base, "show": shown, "remaining": remaining, "questions": [{"prompt": "Which one has gone?", "options": options, "answer": shown[gone]}]}
    if kind == "names":
        names = rng.shuffle(list(NAMES))[:level]
        details = rng.shuffle(list(DETAILS))[:level]
        people = [[names[i], details[i]] for i in range(level)]
        questions = []
        for name, detail in rng.shuffle([list(person) for person in people]):
            options = _choice_options(name, names + rng.shuffle([n for n in NAMES if n not in names])[:2], min(4, level + 1), rng)
            questions.append({"prompt": f"Who {detail}?", "options": options, "answer": name})
        return {**base, "show": [f"{name}: {detail}" for name, detail in people], "people": people, "questions": questions}
    if kind == "places":
        items = rng.shuffle(list(ITEMS))[:level]
        rooms = [rng.choice(ROOMS) for _ in items]
        questions = []
        for index in rng.shuffle(list(range(level))):
            options = _choice_options(rooms[index], ROOMS, 4, rng)
            questions.append({"prompt": f"Where did you put the {items[index]}?", "options": options, "answer": rooms[index]})
        return {**base, "show": [f"The {item} in the {room.lower()}" for item, room in zip(items, rooms)], "questions": questions}
    if kind == "story":
        name = rng.choice(STORY_NAMES)
        facts = {key: rng.choice(options) for key, _question, options in STORY_FACTS}
        text = [f"On {facts['day']}, {name} went to {facts['place']} {facts['travel']}.",
                f"It was {facts['weather']}.",
                f"{name} bought {facts['item']} for {facts['friend']}."]
        asked = rng.shuffle([list(fact) for fact in STORY_FACTS])[:level]
        questions = [{"prompt": question.replace("{name}", name), "options": _choice_options(facts[key], options, 4, rng), "answer": facts[key]} for key, question, options in asked]
        return {**base, "show": [" ".join(text)], "questions": questions}
    if kind == "routine":
        steps = list(rng.choice(ROUTINES)[:level])
        options = list(steps)
        while options == steps:
            rng.shuffle(options)
        return {**base, "show": [f"{i + 1}. {step}" for i, step in enumerate(steps)], "options": options, "answer": steps}
    if kind == "sort":
        groups = rng.shuffle([[name, list(items)] for name, items in CATEGORIES])[: 2 if level <= 6 else 3]
        names = [name for name, _items in groups]
        picked = []
        questions = []
        for index in range(level):
            name, items = groups[index % len(groups)]
            item = rng.choice([entry for entry in items if entry not in picked])
            picked.append(item)
            questions.append({"prompt": item, "options": list(names), "answer": name})
        return {**base, "groups": names, "questions": rng.shuffle(questions)}
    if kind == "search":
        pool = [word for word in _word_pool(kind, material) if len(word) <= 14]
        if len(pool) < 6:
            pool = list(WORDS)
        target = rng.choice(pool)
        others = [word for word in pool if word != target]
        size = min(20, 8 + level * 2)
        tiles = [target] * level + [rng.choice(others) for _ in range(size - level)]
        return {**base, "target": target, "tiles": rng.shuffle(tiles), "answer": level}
    if kind == "nback":
        pool = _word_pool(kind, material)
        items = []
        for index in range(level):
            if index > 0 and rng.random() < 0.35:
                items.append(items[-1])
            else:
                choices = [word for word in pool if not items or word != items[-1]]
                items.append(rng.choice(choices))
        questions = [{"prompt": items[i], "options": ["Same", "Different"], "answer": "Same" if items[i] == items[i - 1] else "Different"} for i in range(1, len(items))]
        return {**base, "items": items, "questions": questions}
    return make_round("sequence", level, seed)


def digit_groups(digits):
    """Digits in twos and threes, never a lone digit: 4 -> 2+2, 7 -> 3+2+2."""
    groups = []
    rest = digits
    while rest:
        size = 2 if len(rest) in (2, 4) else 3
        if len(rest) == 1:
            size = 1
        groups.append(rest[:size])
        rest = rest[size:]
    return groups


def show_ms(round_, more_time=False):
    """How long the things to remember stay up before the answer screen (0: no show step)."""
    kind = round_["kind"]
    size = round_["level"]
    base = {"sequence": 1500 + 700 * size, "words": 2500 + 1300 * size, "pairs": 2500 + 2000 * size,
            "missing": 2500 + 1300 * size, "names": 3000 + 3000 * size, "places": 3000 + 2200 * size,
            "story": 12000, "routine": 3000 + 2000 * size}.get(kind, 0)
    return base * (2 if more_time else 1)


def norm(text):
    return " ".join("".join(ch if ch.isalnum() else " " for ch in str(text).lower()).split())


def score(round_, response):
    """{"correct", "total", "right"} for one round.

    response: sequence -> the typed or tapped digits; words -> the words picked
    (or typed text); routine -> the steps in the order tapped; search ->
    {"found", "wrong"}; the rest -> one chosen option per question.
    """
    kind = round_["kind"]
    if kind == "sequence":
        typed = "".join(ch for ch in str(response or "") if ch.isdigit())
        answer = round_["answer"]
        correct = sum(1 for a, b in zip(typed, answer) if a == b)
        return {"correct": correct, "total": len(answer), "right": typed == answer}
    if kind == "words":
        shown = round_["answer"]
        if isinstance(response, str):
            typed = f" {norm(response)} "
            hits = sum(1 for word in shown if f" {norm(word)} " in typed)
            wrong = 0
        else:
            picked = _unique(response or [])
            hits = sum(1 for word in picked if word in shown)
            wrong = len(picked) - hits
        correct = max(0, hits - wrong)
        return {"correct": correct, "total": len(shown), "right": correct >= len(shown) * PASS_SHARE}
    if kind == "routine":
        order = list(response or [])
        answer = round_["answer"]
        correct = sum(1 for a, b in zip(order, answer) if a == b)
        return {"correct": correct, "total": len(answer), "right": correct >= len(answer) * PASS_SHARE}
    if kind == "search":
        found = int((response or {}).get("found", 0))
        wrong = int((response or {}).get("wrong", 0))
        total = round_["answer"]
        return {"correct": found, "total": total, "right": found >= total and wrong <= 2}
    picks = list(response or [])
    questions = round_["questions"]
    correct = sum(1 for question, pick in zip(questions, picks) if pick == question["answer"])
    return {"correct": correct, "total": len(questions), "right": bool(questions) and correct >= len(questions) * PASS_SHARE}


def next_level(kind, level, right, helped=False):
    """One step harder after a success, one easier after a miss; a helped success stays put."""
    if right and helped:
        return clamp_level(kind, level)
    return clamp_level(kind, level + (1 if right else -1))


def clue(question, seed):
    """Help me: the question with all but one wrong option taken away."""
    rng = Rng(seed)
    options = question["options"]
    wrong = [option for option in options if option != question["answer"]]
    if len(options) <= 2 or not wrong:
        return list(options)
    keep = rng.choice(wrong)
    return [option for option in options if option in (question["answer"], keep)]


def feedback(right, seed, simple=False):
    rng = Rng(seed)
    if right:
        return rng.choice(PRAISE)
    return GENTLE[1] if simple else rng.choice(GENTLE)


# ------------------------------------------------------------------ results
def normalize_results(raw):
    """Saved puzzle results: {"kinds": {kind: {...}}, "days": [ISO dates played]}."""
    out = {"kinds": {}, "days": []}
    if not isinstance(raw, dict):
        return out
    kinds = raw.get("kinds") if isinstance(raw.get("kinds"), dict) else {}
    for kind in KINDS:
        item = kinds.get(kind)
        if not isinstance(item, dict):
            continue
        recent = item.get("recent") if isinstance(item.get("recent"), list) else []
        out["kinds"][kind] = {
            "level": clamp_level(kind, item.get("level")),
            "best": clamp_level(kind, item.get("best")) if _int(item.get("best")) > 0 else 0,
            "plays": max(0, _int(item.get("plays"))),
            "last": str(item.get("last") or "")[:10],
            "recent": [1 if value in (1, True) else 0 for value in recent][-RECENT_MAX:],
        }
    days = raw.get("days") if isinstance(raw.get("days"), list) else []
    out["days"] = sorted({str(day)[:10] for day in days if isinstance(day, str) and len(day) >= 10})[-DAYS_MAX:]
    return out


def _int(value):
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def start_level(results, kind):
    """Where a game starts: the level reached last time, else the first level."""
    item = normalize_results(results)["kinds"].get(kind)
    return item["level"] if item else puzzle(kind)["first"]


def record_game(results, kind, rounds, day):
    """Add a finished game. rounds: [{"level", "right"}] in the order played."""
    updated = normalize_results(results)
    if kind not in KINDS or not rounds:
        return updated
    item = updated["kinds"].get(kind) or {"level": puzzle(kind)["first"], "best": 0, "plays": 0, "last": "", "recent": []}
    passed = [clamp_level(kind, entry.get("level")) for entry in rounds if entry.get("right")]
    last = rounds[-1]
    item["level"] = next_level(kind, clamp_level(kind, last.get("level")), bool(last.get("right")), bool(last.get("helped")))
    item["best"] = max([item["best"]] + passed)
    item["plays"] += 1
    item["last"] = day
    item["recent"] = (item["recent"] + [1 if entry.get("right") else 0 for entry in rounds])[-RECENT_MAX:]
    updated["kinds"][kind] = item
    updated["days"] = sorted(set(updated["days"]) | {day})[-DAYS_MAX:]
    return updated


def accuracy(results, kind):
    """Share of recent rounds remembered (None before any are played)."""
    item = normalize_results(results)["kinds"].get(kind)
    if not item or not item["recent"]:
        return None
    return sum(item["recent"]) / len(item["recent"])


def streak(results, today):
    """Days in a row with a puzzle, counting back from today (or yesterday: the day isn't over)."""
    days = set(normalize_results(results)["days"])
    current = date.fromisoformat(today)
    if today not in days:
        current -= timedelta(days=1)
    count = 0
    while current.isoformat() in days:
        count += 1
        current -= timedelta(days=1)
    return count


def streak_text(results, today):
    """A friendly line that never scolds for a missed day."""
    count = streak(results, today)
    played_today = today in normalize_results(results)["days"]
    if count >= 2:
        return f"{count} days in a row. Lovely."
    if played_today:
        return "You've played today. Well done."
    if normalize_results(results)["days"]:
        return "Welcome back. A few minutes is all it takes."
    return "A few minutes a day keeps the mind busy."


def _days_since(last, today):
    try:
        return (date.fromisoformat(today) - date.fromisoformat(last)).days
    except (TypeError, ValueError):
        return 99


def todays_puzzles(results, today, everyday=False, count=3):
    """Today's mix: the puzzles most worth playing, from different skills.

    Unplayed puzzles first, then the ones played longest ago or going worst.
    With `everyday` (the everyday-memory or caregiver profile) the everyday
    puzzles count a little more. The same day always gives the same mix.
    Story recall, when picked, goes first so its questions can come back at
    the end (remembering after a delay is what trains memory most).
    """
    saved = normalize_results(results)
    order = Rng(int(today.replace("-", ""))).shuffle(list(KINDS))
    scored = []
    for kind in order:
        item = saved["kinds"].get(kind)
        if not item:
            priority = 100
        else:
            share = sum(item["recent"]) / len(item["recent"]) if item["recent"] else 0.5
            priority = min(30, _days_since(item["last"], today)) * 2 + int((1 - share) * 10)
        if everyday and puzzle(kind)["skill"] == "everyday":
            priority += 6
        scored.append((priority, kind))
    ranked = [kind for _priority, kind in sorted(scored, key=lambda pair: -pair[0])]
    picked = []
    skills = set()
    for kind in ranked:
        skill = puzzle(kind)["skill"]
        # Different skills each day; the everyday profile may get two everyday puzzles.
        everyday_count = sum(1 for chosen in picked if puzzle(chosen)["skill"] == "everyday")
        if len(picked) < count and (skill not in skills or (everyday and skill == "everyday" and everyday_count < 2)):
            picked.append(kind)
            skills.add(skill)
    for kind in ranked:
        if len(picked) < count and kind not in picked:
            picked.append(kind)
    if "story" in picked:
        picked.remove("story")
        picked.insert(0, "story")
    return picked


def weakest_puzzle(results, today, everyday=False):
    """The one puzzle most worth a round now (for a study plan step)."""
    return todays_puzzles(results, today, everyday, 1)[0]


def summary(results, today):
    """For progress screens and the study plan: per kind level, best, plays, accuracy, days since played."""
    saved = normalize_results(results)
    rows = []
    for info in PUZZLES:
        item = saved["kinds"].get(info["kind"])
        share = (sum(item["recent"]) / len(item["recent"])) if item and item["recent"] else None
        rows.append({
            "kind": info["kind"], "title": info["title"], "skill": info["skill"],
            "level": item["level"] if item else info["first"], "best": item["best"] if item else 0,
            "plays": item["plays"] if item else 0,
            "accuracy": share,
            "days_since": _days_since(item["last"], today) if item and item["last"] else None,
        })
    return rows
