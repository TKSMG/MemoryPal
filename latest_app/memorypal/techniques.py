"""Text generators for the Associations page's memory techniques.

Each technique gives every idea its own peg, place, or scene. Reusing one
for two ideas (which the old versions did past 6-10 items) makes the two
memories interfere, which is exactly what these techniques try to avoid.
"""

import re

EMPTY = "Add ideas first."

PEGS = [("one", "sun"), ("two", "shoe"), ("three", "tree"), ("four", "door"), ("five", "hive"),
        ("six", "sticks"), ("seven", "heaven"), ("eight", "gate"), ("nine", "line"), ("ten", "hen")]
# Second and later rounds reuse the rhymes with a distinct, vivid twist.
PEG_ROUNDS = ["", "giant golden ", "tiny frozen ", "noisy rainbow "]

PALACE_ROUTE = [
    "front door", "doormat", "hallway", "coat hook", "kitchen", "fridge", "table", "window",
    "sofa", "television", "bookshelf", "stairs", "landing", "bathroom", "bath", "bedroom",
    "bed", "wardrobe", "desk", "back door",
]
PALACE_ROUNDS = ["", "garden ", "garage "]

STORY_SCENES = [
    "at the front door", "on the kitchen table", "beside a bright window", "inside a small notebook",
    "under a glowing lamp", "on a busy bus", "in a quiet park", "on top of a tall ladder",
    "inside a lift", "at a market stall", "on a sandy beach", "next to the final doorway",
]
STORY_ACTIONS = ["shines", "speaks", "spins", "points", "opens", "locks", "sings", "bounces", "whistles", "waves"]

ACROSTIC_WORDS = {
    "a": ["Angry", "Apples"], "b": ["Brave", "Bears"], "c": ["Clever", "Cats"], "d": ["Dancing", "Dogs"],
    "e": ["Eager", "Eagles"], "f": ["Funny", "Frogs"], "g": ["Giant", "Goats"], "h": ["Happy", "Horses"],
    "i": ["Icy", "Islands"], "j": ["Jolly", "Jugglers"], "k": ["Kind", "Kings"], "l": ["Lazy", "Lions"],
    "m": ["Merry", "Monkeys"], "n": ["Noisy", "Neighbours"], "o": ["Orange", "Owls"], "p": ["Purple", "Penguins"],
    "q": ["Quiet", "Queens"], "r": ["Red", "Rabbits"], "s": ["Silly", "Snakes"], "t": ["Tiny", "Tigers"],
    "u": ["Upside-down", "Umbrellas"], "v": ["Very", "Violins"], "w": ["Wild", "Wolves"], "x": ["Extra", "X-rays"],
    "y": ["Yellow", "Yaks"], "z": ["Zany", "Zebras"],
}


def parse_ideas(raw):
    raw = (raw or "").replace("/n", "\n")
    return [item.strip() for item in re.split(r"[,\n;|/]+", raw) if item.strip()]


def acronym(items):
    if not items:
        return EMPTY
    letters = "".join(item[0].upper() for item in items)
    words = []
    for index, item in enumerate(items):
        first = item[0].lower()
        options = ACROSTIC_WORDS.get(first)
        # Alternate describing words and nouns so it reads like a phrase.
        words.append(options[index % 2] if options else item.split()[0])
    return (
        f"{letters}\n\nConnect each letter back to: {', '.join(items)}"
        f"\n\nOr as a sentence (acrostic): {' '.join(words)}."
        "\nSwap in your own words; a silly sentence you made yourself sticks best."
    )


def story(items):
    if not items:
        return EMPTY
    lines = []
    for index, item in enumerate(items):
        lap, position = divmod(index, len(STORY_SCENES))
        scene = STORY_SCENES[position] + (f" (walk {lap + 1})" if lap else "")
        action = STORY_ACTIONS[index % len(STORY_ACTIONS)]
        lines.append(f"{index + 1}. Picture {item} {scene}. It {action} so you notice it before moving on.")
    return "Mini-story:\n\n" + "\n".join(lines) + "\n\nWalk through the scenes in order and let each image cue the next idea."


def peg_list(items):
    if not items:
        return EMPTY
    lines = []
    for index, item in enumerate(items):
        lap, position = divmod(index, len(PEGS))
        number_word, peg = PEGS[position]
        twist = PEG_ROUNDS[lap] if lap < len(PEG_ROUNDS) else f"round-{lap + 1} "
        lines.append(f"{index + 1}. {number_word.title()} rhymes with {peg}: imagine {item} stuck to a {twist}{peg}.")
    tip = "\n\nSay the number, hear the rhyme, see the picture."
    if len(items) > len(PEGS):
        tip += " Past ten, the same rhymes return with a twist (golden, frozen) so each peg stays unique."
    return "Peg list:\n\n" + "\n".join(lines) + tip


def palace(items):
    if not items:
        return EMPTY
    lines = []
    for index, item in enumerate(items):
        lap, position = divmod(index, len(PALACE_ROUTE))
        area = PALACE_ROUNDS[lap] if lap < len(PALACE_ROUNDS) else f"extra room {lap + 1} "
        lines.append(f"{index + 1}. Put {item} at the {area}{PALACE_ROUTE[position]}. Make it oversized or moving.")
    return "Memory palace route:\n\n" + "\n".join(lines) + "\n\nReview by walking through the route in the same order. Use a home you know well."


def chunk_map(items, size=3):
    if not items:
        return EMPTY
    groups = [items[index:index + size] for index in range(0, len(items), size)]
    lines = [f"Group {index + 1}: " + ", ".join(group) for index, group in enumerate(groups)]
    return "Chunk map:\n\n" + "\n".join(lines) + "\n\nStudy one group at a time, then connect the groups."


def link_chain(items):
    if not items:
        return EMPTY
    if len(items) == 1:
        return f"Link chain:\n\nStart with {items[0]} and add more ideas to build a chain."
    lines = [f"{first} leads to {second}: imagine {first} handing a bright clue to {second}." for first, second in zip(items, items[1:])]
    return "Link chain:\n\n" + "\n".join(lines)
