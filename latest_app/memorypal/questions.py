"""Varied quiz questions made from cards and notes, without any AI.

The phone has the same logic in mobile/src/core/questions.ts. Both use the
small seeded generator below (mulberry32), so for the same seed and cards
they give exactly the same questions; tools/parity/make_fixtures.py checks it.

Question types, chosen by what fits each card:

- choice     front -> pick the back among similar answers
- reverse    short back -> pick the front it belongs to
- cloze      a key word blanked out of a sentence-like back (picked or typed)
- truefalse  a front shown with its own back or a plausible same-deck one
- match      three or four short pairs to match up
- order      a back that is a list: which item comes first / next
- recall     type the back (only when nothing else fits)

A question is a plain dict (see make_question). build_quiz picks the cards
and types for a whole round.
"""

import functools
import re

from . import richtext
from .core import STOP_WORDS, comparable_text, hangman_hint, normalize_space, split_study_bits, strip_list_marker, today_iso, token_words

M32 = 0xFFFFFFFF


class Rng:
    """mulberry32: tiny, seedable, and identical in Python and TypeScript."""

    def __init__(self, seed=0):
        self.state = int(seed) & M32

    def next_uint(self):
        self.state = (self.state + 0x6D2B79F5) & M32
        a = self.state
        t = ((a ^ (a >> 15)) * (1 | a)) & M32
        t = ((t + (((t ^ (t >> 7)) * (61 | t)) & M32)) & M32) ^ t
        return (t ^ (t >> 14)) & M32

    def random(self):
        return self.next_uint() / 4294967296

    def below(self, n):
        """A whole number from 0 to n - 1."""
        return int(self.random() * n) if n > 0 else 0

    def choice(self, items):
        return items[self.below(len(items))]

    def shuffle(self, items):
        """Shuffle a list in place (Fisher-Yates) and return it."""
        for i in range(len(items) - 1, 0, -1):
            j = self.below(i + 1)
            items[i], items[j] = items[j], items[i]
        return items


TYPES = ("choice", "reverse", "cloze", "truefalse", "match", "order", "recall")
BLANK = "_____"
WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'-]{2,}")
# Everyday words that make poor blanks and give-away wrong answers ("over", "them").
CLOZE_FILLER = {
    "above", "across", "after", "again", "against", "along", "among", "around", "been", "before",
    "behind", "being", "below", "between", "both", "does", "doing", "down", "during", "each",
    "even", "ever", "every", "here", "into", "many", "more", "most", "much", "must",
    "only", "onto", "other", "over", "same", "some", "such", "them", "these", "they",
    "those", "through", "under", "until", "upon", "very", "well", "within", "without",
}
YEAR_RE = re.compile(r"(?<![0-9])(1[0-9]{3}|20[0-9]{2})(?![0-9])")
NUMBER_RE = re.compile(r"(?<![A-Za-z0-9.,])[0-9](?:[0-9,.:]*[0-9])?%?(?![A-Za-z0-9])")
NUMBER_WORD = re.compile(r"^[-+]?[0-9][0-9,.:]*%?$")
MONTH_RE = re.compile(r"(?<![a-z])(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec|january|february|march|april|june|july|august|september|october|november|december)(?![a-z])")
TYPED_NEWLINE = re.compile(r"\\n|(?<![A-Za-z0-9])/n(?![A-Za-z0-9])")
GENERIC_FRONT = re.compile(r"^(?:what should i recall from bit (?:[0-9]+|\{n\})\??|study bit [0-9]+)$", re.IGNORECASE)
PRONOUNS = {"it", "this", "that", "these", "those", "there", "he", "she", "they", "we", "you", "i", "which", "what", "who", "its", "his", "her", "their", "our"}
DEFINITION_RE = re.compile(r"^(.{1,60}?)\s+(is called|is known as|refers to|stands for|means|is|are|was|were)\s+(.+)$", re.IGNORECASE)
NOT_DEFINING = {"not", "no", "very", "also", "being", "been", "so", "too", "still", "now", "often", "usually", "always", "never"}
AI_PATHWAY = "Made with AI"
AI_NOTE = "Made with AI, check it."


def field(card, name, default=""):
    value = card.get(name, default) if isinstance(card, dict) else getattr(card, name, default)
    return default if value is None else value


def words_of(text):
    text = normalize_space(text)
    return text.split(" ") if text else []


def answer_kind(text):
    """date, number, word, short or long: distractors should share it."""
    text = normalize_space(text)
    words = words_of(text)
    if not words:
        return "empty"
    if len(words) <= 4 and (YEAR_RE.search(text) or (MONTH_RE.search(text.lower()) and re.search(r"[0-9]", text))):
        return "date"
    if len(words) <= 3 and NUMBER_WORD.match(words[0]):
        return "number"
    if len(words) == 1:
        return "word"
    return "short" if len(words) <= 5 else "long"


def is_short(text):
    return 0 < len(words_of(text)) <= 5 and len(normalize_space(text)) <= 40


def list_items(text):
    """The items of a back that is a list (three or more), else []."""
    raw = TYPED_NEWLINE.sub("\n", text or "")
    lines = [strip_list_marker(line) for line in raw.splitlines()]
    lines = [line for line in lines if line]
    if len(lines) >= 3:
        return lines if all(len(words_of(line)) <= 12 for line in lines) else []
    parts = [part.strip() for part in raw.split(";") if part.strip()]
    if len(parts) >= 3:
        return parts if all(len(words_of(part)) <= 12 for part in parts) else []
    flat = normalize_space(raw)
    while flat.endswith("."):
        flat = flat[:-1]
    parts = [part.strip() for part in flat.split(",")]
    if len(parts) < 3 and " and " not in flat:
        return []
    items = []
    for index, part in enumerate(parts):
        if index == len(parts) - 1:
            for joiner in ("and ", "or "):
                if part.startswith(joiner):
                    part = part[len(joiner):].strip()
            pieces = re.split(r"\s+(?:and|or)\s+", part)
            items.extend(piece.strip() for piece in pieces)
        else:
            items.append(part)
    items = [item for item in items if item]
    if len(items) < 3 or any(len(words_of(item)) > 3 for item in items):
        return []
    return items


def is_generic_front(front, back="", deck=""):
    """Fronts made for note bits that say nothing about the bit."""
    front = normalize_space(front)
    if not front or GENERIC_FRONT.match(front):
        return True
    return bool(back) and front == f"{normalize_space(deck)}: {hangman_hint(back)}"


def cloze_candidates(text, avoid=""):
    """Words worth blanking out, best first: (word as written, start, end)."""
    avoid_stems = {stem for stem, _word in token_words(avoid)}
    ranked = []
    seen = set()
    for match in WORD_RE.finditer(text):
        word = match.group(0)
        lower = word.lower()
        has_digit = bool(re.search(r"[0-9]", word))
        if lower in STOP_WORDS or lower in CLOZE_FILLER or lower in seen or (len(word) < 4 and not has_digit):
            continue
        seen.add(lower)
        stems = token_words(word)
        stem = stems[0][0] if stems else lower
        score = (30 if has_digit else 0) + (20 if re.match(r"[A-Z]", word) and match.start() > 0 else 0)
        score += (20 if stem not in avoid_stems else 0) + min(len(word), 12)
        ranked.append((score, len(ranked), word, match.start(), match.end()))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [(word, start, end) for _score, _index, word, start, end in ranked]


def cloze_words(text, like):
    """Words in a text that could stand in for the blanked word `like`.

    A word that starts a sentence takes the blanked word's capitalisation,
    so a capital letter gives nothing away; other capitals (names) stay.
    """
    return list(_cloze_words(text, bool(re.match(r"[A-Z]", like))))


# A round looks through every other card's text for each question, so the
# same texts are cleaned again and again; these remember the results.
@functools.lru_cache(maxsize=4096)
def _cloze_words(text, capital):
    out = []
    for match in WORD_RE.finditer(text):
        word = match.group(0)
        if word.lower() in STOP_WORDS or word.lower() in CLOZE_FILLER or (len(word) < 4 and not re.search(r"[0-9]", word)):
            continue
        if match.start() == 0 or re.search(r"[.!?]\s+$", text[: match.start()]):
            word = (word[:1].upper() if capital else word[:1].lower()) + word[1:]
        out.append(word)
    return tuple(out)


def blank_out(text, start, end):
    return text[:start] + BLANK + text[end:]


def lower_article(text):
    """'The heart' -> 'the heart', so it reads well inside a question."""
    first = text.split(" ", 1)[0]
    return text[0].lower() + text[1:] if first in ("The", "A", "An") else text


def capitalize(text):
    return text[:1].upper() + text[1:]


def question_for_bit(bit):
    """A real question from one sentence of notes, or None.

    Returns {"prompt", "answer", "type", "source"}; type is definition,
    list, date, cloze or hint. Rule-based and conservative.
    """
    marked_text = normalize_space(strip_list_marker(normalize_space(bit)))
    text = normalize_space(richtext.plain(marked_text))
    while text and text[-1] in ".!;":
        text = text[:-1].rstrip()
    words = words_of(text)
    if not words or text.endswith("?"):
        return None

    def made(prompt, answer, kind):
        return {"prompt": prompt, "answer": answer, "type": kind, "source": normalize_space(richtext.plain(bit))}

    # Words the notes made bold or highlighted are the ones to remember.
    filled = richtext.blank_marked(marked_text, BLANK)
    if filled and words_of(filled[0].replace(BLANK, " ")):
        sentence = filled[0]
        while sentence and sentence[-1] in ".!;":
            sentence = sentence[:-1].rstrip()
        return made(f"Fill in the blank: {sentence}", filled[1], "cloze")

    colon = re.match(r"^([^:]{1,60}):\s+(.+)$", text)
    if colon and len(words_of(colon.group(1))) <= 6 and not re.search(r"[0-9]$", colon.group(1)):
        term, answer = colon.group(1).strip(), colon.group(2).strip()
        listed = len([part for part in answer.split(",") if part.strip()]) >= 2
        return made(f"What {'are' if listed else 'is'} {lower_article(term)}?", answer, "list" if listed else "definition")

    year = YEAR_RE.search(text)
    if year:
        opening = re.match(r"^In ((?:1[0-9]{3}|20[0-9]{2})),?\s+(.+)$", text)
        if opening and len(words_of(opening.group(2))) >= 2:
            return made(f"When did this happen? {capitalize(opening.group(2))}.", opening.group(1), "date")
        closing = re.match(r"^(.+?)\s+(?:in|during|by)\s+((?:1[0-9]{3}|20[0-9]{2}))$", text)
        if closing and len(words_of(closing.group(1))) >= 2:
            head = closing.group(1)
            head_words = words_of(head)
            if head_words[-1].lower() in ("was", "were", "is", "are"):
                subject = " ".join(head_words[:-1])
                return made(f"When {head_words[-1].lower()} {lower_article(subject)}?", closing.group(2), "date")
            return made(f"When did this happen? {capitalize(head)}.", closing.group(2), "date")
        if len(words) >= 3:
            return made(f"Fill in the blank: {blank_out(text, year.start(), year.end())}", year.group(0), "date")

    definition = DEFINITION_RE.match(text)
    if definition:
        term, verb, answer = definition.group(1).strip(), definition.group(2).lower(), definition.group(3).strip()
        term_words = words_of(term)
        first_answer = answer.split(" ", 1)[0].lower()
        # "was exiled", "is not", "are growing" describe, they don't define.
        passive = verb in ("is", "are", "was", "were") and (first_answer.endswith(("ed", "en", "ing")) or first_answer in NOT_DEFINING)
        if 1 <= len(term_words) <= 6 and term_words[0].lower() not in PRONOUNS and answer and not passive:
            subject = lower_article(term)
            prompt = {
                "means": f"What does {subject} mean?",
                "refers to": f"What does {subject} refer to?",
                "stands for": f"What does {subject} stand for?",
                "is called": f"What is {subject} called?",
                "is known as": f"What is {subject} known as?",
            }.get(verb, f"What {verb} {subject}?")
            return made(prompt, answer, "list" if list_items(answer) else "definition")

    if len(words) >= 4:
        number = NUMBER_RE.search(text)
        if number:
            return made(f"Fill in the blank: {blank_out(text, number.start(), number.end())}", number.group(0), "cloze")
    if len(words) >= 5:
        candidates = cloze_candidates(text)
        if candidates:
            word, start, end = candidates[0]
            return made(f"Fill in the blank: {blank_out(text, start, end)}", word, "cloze")
    return made(f"What is this? {hangman_hint(text)}", text, "hint")


def note_questions(text):
    """Questions from pasted notes: one per study bit that gives a question."""
    out, seen = [], set()
    for bit in split_study_bits(text):
        question = question_for_bit(bit)
        if question is None:
            continue
        key = comparable_text(question["prompt"])
        if key in seen:
            continue
        seen.add(key)
        out.append(question)
    return out


# ----------------------------------------------------------------- distractors
def pick_distractors(answer, candidates, count, rng, deck=""):
    """Up to `count` wrong answers from (text, deck) pairs.

    Same deck and same kind first (numbers with numbers, dates with dates,
    single words with single words), then the same kind from other decks,
    then the same deck, then anything. Never the answer again (compared
    without case or punctuation) and never the same text twice.
    """
    kind = answer_kind(answer)
    seen = {comparable_text(answer)}
    tiers = [[], [], [], []]
    for text, source_deck in candidates:
        text, key, text_kind = _distractor_facts(text)
        if not key or key in seen:
            continue
        seen.add(key)
        same_kind = text_kind == kind
        same_deck = source_deck == deck
        tiers[0 if same_deck and same_kind else 1 if same_kind else 2 if same_deck else 3].append(text)
    picked = []
    for tier in tiers:
        rng.shuffle(tier)
        picked.extend(tier)
    return picked[:count]


@functools.lru_cache(maxsize=4096)
def _distractor_facts(text):
    text = normalize_space(text)
    return text, comparable_text(text), answer_kind(text)


def with_answer(answer, distractors, rng):
    options = [answer] + list(distractors)
    rng.shuffle(options)
    return options, options.index(answer)


# ------------------------------------------------------------------- questions
class Pool:
    """The cards a round can draw on, cleaned once (fronts, backs, keys)."""

    def __init__(self, cards):
        self.entries = []
        for card in cards:
            front, back, deck = normalize_space(str(field(card, "front"))), normalize_space(str(field(card, "back"))), str(field(card, "deck") or "General")
            raw_back = str(field(card, "back"))
            if is_generic_front(front, back, deck) and back:
                made = question_for_bit(back)
                if made is not None:
                    front, back, raw_back = made["prompt"], made["answer"], made["answer"]
            if not front or not back:
                continue
            self.entries.append({
                "id": str(field(card, "id")),
                "deck": deck,
                "front": front,
                "back": back,
                "raw_back": raw_back,
                "front_key": comparable_text(front),
                "back_key": comparable_text(back),
                "card": card,
            })
        self.back_keys = {entry["back_key"] for entry in self.entries}
        self.front_keys = {entry["front_key"] for entry in self.entries}
        self.pair_back_keys = {entry["back_key"] for entry in self.entries if self.pairable(entry)}
        self.fit_cache = {}

    @staticmethod
    def pairable(entry):
        return is_short(entry["back"]) and len(words_of(entry["front"])) <= 8

    def fits(self, entry):
        """The question types this card can make, in TYPES order."""
        key = id(entry)
        if key not in self.fit_cache:
            self.fit_cache[key] = self.work_out_fits(entry)
        return self.fit_cache[key]

    def work_out_fits(self, entry):
        out = []
        # Every entry's own keys are in the sets, so "others" is one fewer.
        if len(self.back_keys) - 1 >= 2:
            out.append("choice")
        if is_short(entry["back"]) and len(words_of(entry["front"])) <= 12 and len(self.front_keys) - 1 >= 2:
            out.append("reverse")
        if len(words_of(entry["back"])) >= 5 and cloze_candidates(entry["back"], entry["front"]):
            out.append("cloze")
        out.append("truefalse")
        if self.pairable(entry) and len(self.pair_back_keys) - 1 >= 2:
            out.append("match")
        if len(list_items(entry["raw_back"])) >= 3:
            out.append("order")
        out.append("recall")
        return out


def question(entry, kind, prompt, answer, options=(), answer_index=-1, typed=False, pairs=(), context=""):
    return {
        "id": f"{entry['id']}:{kind}",
        "card_id": entry["id"],
        "deck": entry["deck"],
        "type": kind,
        "prompt": prompt,
        "answer": answer,
        "options": list(options),
        "answer_index": answer_index,
        "typed": typed,
        "pairs": [list(pair) for pair in pairs],
        "context": context,
        "hint": hangman_hint(answer) if typed else "",
    }


def make_question(entry, kind, pool, rng):
    """One question of `kind` for a Pool entry, or None when it doesn't fit."""
    others = [other for other in pool.entries if other["id"] != entry["id"]]
    if kind == "choice":
        wrong = pick_distractors(entry["back"], [(o["back"], o["deck"]) for o in others], 3, rng, entry["deck"])
        if len(wrong) < 2:
            return None
        options, index = with_answer(entry["back"], wrong, rng)
        return question(entry, kind, entry["front"], entry["back"], options, index)
    if kind == "reverse":
        wrong = pick_distractors(entry["front"], [(o["front"], o["deck"]) for o in others if o["back_key"] != entry["back_key"]], 3, rng, entry["deck"])
        if len(wrong) < 2:
            return None
        options, index = with_answer(entry["front"], wrong, rng)
        return question(entry, kind, f"Which one goes with \u201c{entry['back']}\u201d?", entry["front"], options, index)
    if kind == "cloze":
        candidates = cloze_candidates(entry["back"], entry["front"])[:3]
        if not candidates or len(words_of(entry["back"])) < 5:
            return None
        word, start, end = rng.choice(candidates)
        prompt = f"Fill in the blank: {blank_out(entry['back'], start, end)}"
        sources = [o for o in others if o["deck"] == entry["deck"]] + [o for o in others if o["deck"] != entry["deck"]] + [entry]
        wrong = pick_distractors(word, [(found, source["deck"]) for source in sources for found in cloze_words(source["back"], word)], 3, rng, entry["deck"])
        if len(wrong) >= 2 and rng.random() >= 0.35:
            options, index = with_answer(word, wrong, rng)
            return question(entry, kind, prompt, word, options, index, context=entry["front"])
        return question(entry, kind, prompt, word, typed=True, context=entry["front"])
    if kind == "truefalse":
        same_deck = [(o["back"], o["deck"]) for o in others if o["deck"] == entry["deck"]]
        wrong = pick_distractors(entry["back"], same_deck, 1, rng, entry["deck"])
        show_false = bool(wrong) and rng.random() < 0.5
        shown = wrong[0] if show_false else entry["back"]
        stop = "" if re.search(r"[.!?]$", shown) else "."
        prompt = f"True or false? The answer to \u201c{entry['front']}\u201d is \u201c{shown}\u201d{stop}"
        answer = "False" if show_false else "True"
        return question(entry, kind, prompt, answer, ["True", "False"], 1 if show_false else 0, context=entry["front"])
    if kind == "match":
        if not pool.pairable(entry):
            return None
        tiers = [[], []]
        fronts, backs = {entry["front_key"]}, {entry["back_key"]}
        for other in others:
            if pool.pairable(other):
                tiers[0 if other["deck"] == entry["deck"] else 1].append(other)
        companions = []
        for tier in tiers:
            rng.shuffle(tier)
            for other in tier:
                if len(companions) < 3 and other["front_key"] not in fronts and other["back_key"] not in backs:
                    fronts.add(other["front_key"])
                    backs.add(other["back_key"])
                    companions.append(other)
        if len(companions) < 2:
            return None
        pairs = [(item["front"], item["back"]) for item in [entry] + companions]
        rng.shuffle(pairs)
        rights = rng.shuffle([right for _left, right in pairs])
        return question(entry, kind, "Match each one with what goes with it.", entry["back"], rights, rights.index(entry["back"]), pairs=pairs)
    if kind == "order":
        items = list_items(entry["raw_back"])
        if len(items) < 3:
            return None
        at = rng.below(len(items))
        answer = items[at]
        if at == 0:
            prompt = f"{entry['front']}: which comes first?"
        else:
            prompt = f"{entry['front']}: what comes after \u201c{items[at - 1]}\u201d?"
        before = items[at - 1] if at else None
        wrong = pick_distractors(answer, [(item, entry["deck"]) for item in items if item != before], 3, rng, entry["deck"])
        if len(wrong) < 2:
            return None
        options, index = with_answer(answer, wrong, rng)
        return question(entry, kind, prompt, answer, options, index, context=entry["front"])
    if kind == "recall":
        return question(entry, kind, entry["front"], entry["back"], typed=True)
    return None


def card_question(card, kind, cards, rng):
    """make_question for a Card (or dict) among `cards`; None when it doesn't fit."""
    pool = Pool(list(cards) if any(field(c, "id") == field(card, "id") for c in cards) else [card] + list(cards))
    entry = next((e for e in pool.entries if e["id"] == str(field(card, "id"))), None)
    return make_question(entry, kind, pool, rng) if entry else None


# ---------------------------------------------------------------- whole rounds
def priority_bucket(card, today):
    due = str(field(card, "next_review")) <= today
    weak = int(field(card, "lapses", 0) or 0) > 0 or str(field(card, "last_result")) == "Again" or (
        int(field(card, "repetitions", 0) or 0) > 0 and int(field(card, "last_score", 0) or 0) < 60
    )
    return 0 if due and weak else 1 if due else 2 if weak else 3


def build_quiz(cards, count, rng, recent_ids=(), types=None, today=None):
    """A round of up to `count` varied questions.

    - due and weak cards first; cards (or question ids "<card id>:<type>")
      in `recent_ids`, the last round's, go last
    - never the same card twice
    - no two questions in a row of the same type when it can be helped, and
      the least-used type so far is preferred
    - `types` limits the question types (default: all; "recall" is used only
      when nothing else fits)
    """
    today = today or today_iso()
    allowed = [kind for kind in TYPES if types is None or kind in types]
    recent = [str(item) for item in recent_ids or ()]
    recent_cards = {item.split(":", 1)[0] for item in recent} | set(recent)
    recent_questions = set(recent)
    pool = Pool([card for card in cards if not str(field(card, "buried_until")) > today])
    entries = list(pool.entries)
    rng.shuffle(entries)
    keyed = [((priority_bucket(entry["card"], today) + (4 if entry["id"] in recent_cards else 0)), index, entry) for index, entry in enumerate(entries)]
    keyed.sort(key=lambda item: (item[0], item[1]))
    chosen = [entry for _bucket, _index, entry in keyed[: max(0, int(count))]]

    used = {kind: 0 for kind in TYPES}
    previous = ""
    out = []
    while chosen:
        options_for = []
        for entry in chosen:
            fitting = [kind for kind in pool.fits(entry) if kind in allowed]
            preferred = [kind for kind in fitting if kind != "recall"] or fitting
            options_for.append(preferred)
        at = next((i for i, kinds in enumerate(options_for) if any(kind != previous for kind in kinds)), 0)
        entry = chosen.pop(at)
        kinds = options_for[at]
        if not kinds:
            continue
        fresh = [kind for kind in kinds if kind != previous and f"{entry['id']}:{kind}" not in recent_questions]
        kinds = fresh or [kind for kind in kinds if kind != previous] or kinds
        least = min(used[kind] for kind in kinds)
        kinds = [kind for kind in kinds if used[kind] == least]
        kind = rng.choice(kinds)
        made = make_question(entry, kind, pool, rng)
        if made is None:
            for fallback in ("choice", "truefalse", "recall"):
                if fallback in allowed and fallback != kind:
                    made = make_question(entry, fallback, pool, rng)
                    if made is not None:
                        break
        if made is None:
            continue
        used[made["type"]] += 1
        previous = made["type"]
        out.append(made)
    return out


def check_answer(question_item, response):
    """True when a picked option (index or text) is right; typed answers use
    answer_assessment in the app."""
    if isinstance(response, int) and not isinstance(response, bool):
        return response == question_item["answer_index"]
    return comparable_text(str(response)) == comparable_text(question_item["answer"])


def cards_from_note_questions(items, deck, ai=False):
    """Cards from note_questions (or the AI's) output."""
    from .models import Card

    cards = []
    for item in items:
        prompt, answer = normalize_space(item.get("prompt", "")), normalize_space(item.get("answer", ""))
        if prompt and answer:
            cards.append(Card(
                deck=deck or "General",
                front=prompt,
                back=answer,
                pathway=f"{AI_PATHWAY} > {deck}" if ai else f"Capture > {deck}",
                association=AI_NOTE if ai else "",
            ))
    return cards


def is_ai_card(card):
    return str(field(card, "pathway")).startswith(AI_PATHWAY)
