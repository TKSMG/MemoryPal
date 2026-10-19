"""Write the desktop logic's real outputs for the mobile app's parity tests.

    python tools\\parity\\make_fixtures.py

The mobile app (mobile/src/core) is a TypeScript port of latest_app/memorypal.
mobile/__tests__/parity.test.ts replays every case in the JSON this writes and
expects identical results, so the two versions can't quietly drift apart.
Re-run this after changing the Python logic, then run `npm test` in mobile/.
Dates are stored as offsets from today, so the fixtures never go stale.
"""

import json
import os
import random
import sys
import tempfile
from pathlib import Path

os.environ["MEMORYPAL_DATA_DIR"] = tempfile.mkdtemp(prefix="memorypal-parity-")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "latest_app"))

from difflib import SequenceMatcher  # noqa: E402

from memorypal import progress, security, techniques  # noqa: E402
from memorypal.core import add_days, answer_assessment, parse_prompt_answer_lines, split_study_bits, text_tokens, today_iso  # noqa: E402
from memorypal.models import Card  # noqa: E402
from memorypal.planning import build_multi_day_plan, build_study_plan  # noqa: E402
from memorypal.store import MemoryStore  # noqa: E402

OUT = ROOT / "mobile" / "__tests__" / "fixtures" / "parity.json"
rng = random.Random(70)

ANSWERS = [
    "Reviewing information at increasing intervals so recall strengthens over time.",
    "Trying to recall the answer before rereading or revealing it.",
    "The process plants use to turn light, water, and carbon dioxide into food.",
    "The war ended in 1945.",
    "The reaction is not reversible.",
    "Mitochondria are the powerhouse of the cell",
    "Paris",
    "42",
    "Dr Lee",
    "Take the blue pill after breakfast with water",
    "Keys belong in the bowl by the front door",
    "Photosynthesis happens in chloroplasts and needs sunlight",
    "1,000 metres is one kilometre",
    "Isn't it obvious? Never leave the stove on.",
    "William Shakespeare wrote Hamlet around 1600",
]


def variants(answer):
    words = answer.split()
    out = {answer, answer.lower(), answer.upper(), answer + ".", " ".join(words[: max(1, len(words) // 2)]), " ".join(words[len(words) // 2:]), "", "   ", "something completely unrelated here"}
    if len(words) > 2:
        out.add(" ".join(words[:1] + words[2:]))
        out.add(" ".join(reversed(words)))
        shuffled = words[:]
        rng.shuffle(shuffled)
        out.add(" ".join(shuffled))
    typo = list(answer)
    if len(typo) > 4:
        i = rng.randrange(1, len(typo) - 1)
        typo[i], typo[i + 1] = typo[i + 1], typo[i]
        out.add("".join(typo))
    out.add(answer.replace("1945", "1954").replace("42", "41").replace("1,000", "1000"))
    out.add(answer.replace("not ", "").replace("Never", "Always"))
    out.add("info " + answer)
    return sorted(out)


def smart_check_cases():
    cases = []
    for expected in ANSWERS:
        for response in variants(expected):
            cases.append({"response": response, "expected": expected, "context": "", "result": answer_assessment(response, expected)})
    for response, expected, context in [
        ("the blue pill after breakfast", "", "Blue pill after breakfast"),
        ("recieve", "receive", ""),
        ("reviewing info at increasing intervals over time", ANSWERS[0], ""),
        ("increasing intervals", ANSWERS[0], ""),
        ("no", "yes", ""),
        ("b12", "B12", ""),
        ("room 4.", "Room 4", ""),
    ]:
        cases.append({"response": response, "expected": expected, "context": context, "result": answer_assessment(response, expected, context)})
    return cases


TEXTS = [
    "1945 was the end of the war\n1066 was the Norman conquest",
    "Pi is about 3.14. It never ends.",
    "1. apples 2. pears 3. plums",
    "- one\n* two\n• three",
    "salt/nitrogen",
    "first /n second",
    "alpha; beta | gamma",
    "red, green, blue",
    "Just one idea",
    "",
    "Question one? Answer two! Statement three.",
    "line one\\nline two",
    "v2.0 shipped. Then v2.1 followed",
    "  spaced   out  \n\n  text  ",
]
PROMPT_TEXTS = [
    "mitochondria\tpowerhouse of the cell",
    "1984 :: Orwell",
    "Capital of France => Paris\nCapital of Spain - Madrid\nno delimiter here",
    "- dash item :: dash answer\n2) numbered :: item",
    "\n\nblank lines\n\n:: answer only",
    "term\t\nanother\tvalue",
    "a /n b :: c",
]


def sequence_cases():
    pairs = [("abcd", "bcde"), ("", "abc"), ("kitten", "sitting"), ("information", "info")]
    for _ in range(40):
        a = "".join(rng.choice("abcde ") for _ in range(rng.randrange(0, 30)))
        b = "".join(rng.choice("abcde ") for _ in range(rng.randrange(0, 30)))
        pairs.append((a, b))
    long_a = "".join(rng.choice("ab cd") for _ in range(260))
    long_b = "".join(rng.choice("ab cd") for _ in range(240))
    pairs.append((long_a, long_b))
    return [{"a": a, "b": b, "ratio": SequenceMatcher(None, a, b).ratio()} for a, b in pairs]


def schedule_cases():
    store = MemoryStore()
    cases = []
    for n in range(240):
        spec = {
            "id": f"{rng.getrandbits(64):016x}-card-{n}",
            "repetitions": rng.choice([0, 1, 2, 3, 5, 9]),
            "interval": rng.choice([0, 1, 3, 6, 7, 10, 20, 45, 120, 300]),
            "ease": round(rng.uniform(1.3, 3.5), 2),
            "lapses": rng.choice([0, 0, 1, 3]),
            "overdue": rng.choice([0, 0, 1, 4, 12, 40]),
        }
        quality = rng.choice([1, 2, 3, 4, 5])
        card = Card(id=spec["id"], front="Q", back="A", repetitions=spec["repetitions"], interval=spec["interval"], ease=spec["ease"], lapses=spec["lapses"], next_review=add_days(-spec["overdue"]))
        store.cards = [card]
        store.schedule(card, quality)
        cases.append({"card": spec, "quality": quality, "interval": card.interval, "ease": card.ease, "repetitions": card.repetitions, "lapses": card.lapses, "last_score": card.last_score, "last_result": card.last_result, "due_in": card.interval})
    return cases


def card_specs():
    specs = []
    decks = ["Biology", "History", "Spanish"]
    for n in range(36):
        specs.append({
            "id": f"plan-card-{n}",
            "deck": decks[n % 3],
            "front": f"Question {n}",
            "back": f"Answer {n}",
            "repetitions": [0, 0, 1, 2, 4][n % 5],
            "lapses": [0, 1, 0, 2][n % 4],
            "last_score": [0, 30, 55, 78, 95][n % 5],
            "interval": [0, 1, 3, 8, 25][n % 5],
            "due": [-3, 0, 0, 1, 2, 3, 5, 9, 15][n % 9],
        })
    return specs


def store_from(specs):
    store = MemoryStore()
    store.cards = [Card(id=s["id"], deck=s["deck"], front=s["front"], back=s["back"], repetitions=s["repetitions"], lapses=s["lapses"], last_score=s["last_score"], interval=s["interval"], next_review=add_days(s["due"])) for s in specs]
    return store


def strip_step(step):
    return {key: step[key] for key in ("title", "view", "minutes", "blurb") if key in step} | ({"quiz_mode": step["quiz_mode"]} if "quiz_mode" in step else {})


def plan_cases(specs):
    store = store_from(specs)
    empty = MemoryStore()
    empty.cards = []
    habit_sets = [[], ["mnemonics", "repetition", "quick_mc", "games", "breaks", "explain"], ["breaks"], ["explain", "games"], ["quick_mc", "mnemonics"]]
    sessions = []
    for minutes in (10, 12, 15, 20, 30, 45, 60, 90, 120, 240):
        for deck in ("All decks", "New material", "Biology"):
            for goal in ("cram", "exam_prep", "long_term"):
                for habits in habit_sets:
                    steps = build_study_plan(store, minutes, deck, set(habits), goal)
                    sessions.append({"store": "cards", "minutes": minutes, "deck": deck, "goal": goal, "habits": habits, "steps": [strip_step(s) for s in steps]})
    for minutes in (15, 30):
        steps = build_study_plan(empty, minutes, "All decks", set(), "long_term")
        sessions.append({"store": "empty", "minutes": minutes, "deck": "All decks", "goal": "long_term", "habits": [], "steps": [strip_step(s) for s in steps]})
    multi = []
    for days in (1, 3, 5, 7, 14):
        for deck in ("All decks", "New material", "History"):
            for goal in ("cram", "exam_prep", "long_term"):
                for habits in habit_sets[:3]:
                    plan = build_multi_day_plan(store, days, deck, set(habits), goal)
                    multi.append({"days": days, "deck": deck, "goal": goal, "habits": habits, "plan": [
                        {"day": d["day"], "offset": d["day"] - 1, "kind": d["kind"], "due": d["due"], "minutes": d["minutes"], "steps": [strip_step(s) for s in d["steps"]]} for d in plan
                    ]})
    return sessions, multi


def technique_cases():
    lists = [[], ["apple"], ["apple", "banana", "cherry"], [f"idea{n}" for n in range(1, 13)], [f"item {n}" for n in range(1, 45)], ["Oak", "elm", "1st place", "under the sea"]]
    out = []
    for items in lists:
        out.append({"items": items, "acronym": techniques.acronym(items), "story": techniques.story(items), "peg": techniques.peg_list(items), "palace": techniques.palace(items), "chunk": techniques.chunk_map(items), "chain": techniques.link_chain(items)})
    parse = [{"raw": raw, "ideas": techniques.parse_ideas(raw)} for raw in ("a, b\nc; d | e / f", "salt/nitrogen", "x /n y", "  ", "one\\ntwo")]
    return out, parse


def progress_cases(specs):
    levels = [{"practiced": n, "info": progress.level_info(n)} for n in (0, 1, 9, 10, 29, 30, 100, 1234)]
    store = store_from(specs)
    store.activity = {add_days(-offset): count for offset, count in ((0, 3), (1, 5), (2, 1), (4, 20), (5, 15), (6, 15), (30, 2))}
    store.practiced = 61
    store.daily_goal = 15
    activity_offsets = {str(offset): count for offset, count in ((0, 3), (1, 5), (2, 1), (4, 20), (5, 15), (6, 15), (30, 2))}
    return {
        "levels": levels,
        "activity_offsets": activity_offsets,
        "practiced": 61,
        "daily_goal": 15,
        "streak": store.current_streak(),
        "best_streak": progress.best_streak(store.activity),
        "maturity": progress.maturity_breakdown(store.cards),
        "rating_mix": progress.rating_mix(store.cards),
        "forecast": [count for _day, count in progress.due_forecast(store.cards, 14)],
        "weak_order": [card.id for card in store.weak_cards()],
        "deck_summary": store.deck_summary(),
        "badges": [(badge["key"], badge["current"], badge["done"]) for badge in progress.achievements(store)],
    }


def sync_cases():
    """Random base/local/remote combinations of edits, reviews and deletes."""
    from memorypal import sync

    def card(card_id, front="Q", back="A", reps=0, lapses=0, interval=0, next_review="2026-10-10", deck="General"):
        return {"id": card_id, "deck": deck, "front": front, "back": back, "repetitions": reps, "lapses": lapses, "interval": interval, "next_review": next_review, "ease": 2.5, "last_result": "New", "buried_until": ""}

    def variants(card_id):
        return [
            None,
            card(card_id),
            card(card_id, back="A edited"),
            card(card_id, front="Q edited"),
            card(card_id, reps=1, interval=1, next_review="2026-10-11"),
            card(card_id, reps=2, interval=3, next_review="2026-10-14"),
            card(card_id, lapses=1, interval=1, next_review="2026-10-11"),
            card(card_id, back="A edited", reps=1, interval=1, next_review="2026-10-11"),
            card(card_id, deck="Spanish"),
        ]

    cases = []
    for _ in range(300):
        base, local, remote = {}, {}, {}
        for card_id in ("a", "b", "c", "d"):
            key = f"card:{card_id}"
            pool = variants(card_id)
            b = rng.choice(pool)
            l = rng.choice([b, b, rng.choice(pool)])
            if b is not None:
                base[key] = b
            if l is not None:
                local[key] = l
            if rng.random() < 0.5:
                remote[key] = rng.choice(pool)
        settings = [{"daily_goal": 15, "accessibility": {"text_size": "Comfort"}}, {"daily_goal": 30, "accessibility": {"text_size": "Comfort"}}, {"daily_goal": 15, "accessibility": {"text_size": "Large"}}, {"daily_goal": 15, "accessibility": {"text_size": "Comfort", "reduce_motion": True}}]
        b = rng.choice(settings)
        base[sync.SETTINGS_KEY] = b
        local[sync.SETTINGS_KEY] = rng.choice([b, rng.choice(settings)])
        if rng.random() < 0.5:
            remote[sync.SETTINGS_KEY] = rng.choice(settings)
        plan = sync.plan_sync(local, base, remote)
        cases.append({"local": local, "base": base, "remote": remote, "push": plan.push, "apply": plan.apply, "final": plan.final})
    # Converting profile data to records and back, with counts from two devices.
    payload = {
        "cards": [{"id": "x", "front": "Q", "created_at": "2026-10-01 09:00"}, {"id": "y", "front": "Q2", "created_at": "2026-10-02 09:00"}],
        "captures": [],
        "activity": {"2026-10-09": 4, "2026-10-10": 7},
        "practiced": 20,
        "daily_goal": 15,
        "accessibility": {"text_size": "Large"},
        "onboarding": {"done": True, "persona": "student"},
        "study_plan": {},
        "nav_order": [],
    }
    base = {"activity:2026-10-10:phone": {"day": "2026-10-10", "count": 3}, "practiced:phone": {"count": 5}}
    records = sync.records_from_payload(payload, "laptop", base)
    records_more = dict(records)
    records_more["card:z"] = {"id": "z", "front": "New from phone", "created_at": "2026-10-10 10:00"}
    records_more["activity:2026-10-10:tablet"] = {"day": "2026-10-10", "count": 2}
    conversion = {"payload": payload, "base": base, "records": records, "records_more": records_more, "payload_back": sync.payload_from_records(payload, records_more)}
    return cases, conversion


PASSWORDS = [
    "", "abc", "password", "Password123", "password123!", "qwertyuiop", "aaaaaaaaaaaa", "1234567890",
    "abcdefghijkl", "zyxwvutsrqpo", "correct horse battery staple", "violet otter kettle 4419",
    "Tr0ub4dor&3x", "pat.lee-2024!", "PatLee rocks 99", "memorypal2026", "Summer!2026", "letmein1",
    "N0t-So-Obvious?", "longlonglonglonglong", "short1A!", "ilovemycat", "9f$Kq2!vLp#7", "a1a1a1a1a1a1",
    "mississippi river bend", "ZXCVBNM12345", "Café au lait 7", "trustno1trustno1",
]


def security_cases():
    """Password checks and the attempt limiter, with a fake clock."""
    passwords = [
        {"password": pw, "email": email, "problems": security.password_problems(pw, email), "strength": security.password_strength(pw, email), "predictable": security.predictable(pw), "classes": security.character_classes(pw)}
        for pw in PASSWORDS for email in ("", "pat.lee@example.com")
    ]
    now = [1000.0]
    limiter = security.AttemptLimiter(clock=lambda: now[0])
    steps = []
    script = [("fail", 0)] * 7 + [("wait", 10), ("fail", 0), ("wait", 200), ("fail", 0), ("wait", 4000), ("fail", 0), ("ok", 0), ("fail", 0)]
    for action, advance in script:
        now[0] += advance
        if action == "fail":
            limiter.failed(" Pat@Example.com")
        elif action == "ok":
            limiter.succeeded("pat@example.com")
        wait = limiter.wait_seconds("pat@example.com ")
        steps.append({"action": action, "advance": advance, "wait": wait, "message": security.wait_message(wait) if wait else ""})
    waits = [{"seconds": seconds, "message": security.wait_message(seconds)} for seconds in (5, 30, 89, 90, 150, 210, 900)]
    # Birthdays around the 13th, on both sides of the current month, plus bad input.
    ages = []
    for month, year in [(10, 2013), (11, 2013), (9, 2013), (10, 2012), (12, 2012), (1, 2014), (6, 1950), (13, 2000),
                        (0, 2000), ("", 2000), ("x", "2000"), (" 3 ", " 2001 "), ("+3", "2001"), (5, 2027), (5, 1890), ("1_0", "2000"), ("3.5", "2000")]:
        message, under = security.account_age_check(month, year, 2026, 10)
        ages.append({"month": month, "year": year, "message": message, "under": under})
    return {"passwords": passwords, "limiter": steps, "waits": waits, "ages": ages}


def hostile_cases():
    """Damaged or hostile data that can arrive through sync: both apps must clean it the same way."""
    from memorypal.store import normalize_study_plan

    plans = [
        {"settings": {"unit": "days", "amount": "1000000", "deck": "x" * 201, "goal_label": "Cram", "habits": [{}, "games", "games", "explain", 7]}, "created": "2026-10-01", "done": {"2026-10-01": ["²", "3", 1, "12345", None, True]}},
        {"settings": {"unit": "weeks", "amount": 99}},
        {"settings": {"unit": "hours", "amount": "0", "deck": "Spanish", "goal_label": "Exam prep", "habits": "games"}},
        {"settings": {"unit": "minutes", "amount": -4, "deck": None, "goal_label": 3}},
        {"settings": {"unit": "minutes", "amount": 4.5}},
        {"settings": {"unit": "minutes", "amount": " 45"}},
        {"settings": {"unit": "fortnights", "amount": "1_000"}},
        {"settings": {"unit": ["days"], "amount": "9999999999999"}},
        {"settings": {}, "done": []},
        {"settings": {"unit": "days", "amount": "12", "deck": "é" * 200}},
        {"settings": []},
        "not a plan",
    ]
    for raw in plans:
        if isinstance(raw, dict):
            raw.setdefault("created", "2026-10-02")  # a fixed date, so the fixtures never go stale
    cards = [
        {"id": "big", "interval": 10 ** 30, "repetitions": "99999999", "lapses": 123456, "ease": 50, "created_at": "2026-10-01 09:00", "next_review": "2026-10-02"},
        {"id": "neg", "interval": -5, "repetitions": "-3", "lapses": 1e300, "ease": -1, "created_at": "2026-10-01 09:00", "next_review": "2026-10-02"},
        {"id": "ok", "interval": 36500, "repetitions": 10000, "lapses": "17", "ease": "2.1", "created_at": "2026-10-01 09:00", "next_review": "2026-10-02"},
    ]
    from memorypal import sync

    card = {"id": "a", "front": "Q", "back": "A", "repetitions": 1}
    syncs = [
        # Unknown kinds, keys that are built-in names in JavaScript, and a non-key.
        ({"card:a": card}, {"card:a": card}, {"__proto__": {"card:a": None}, "constructor": {"x": 1}, "evil:x": {"a": 1}, "settings": {"daily_goal": 1}, "card:b": {"id": "b"}}),
        # An unknown key already in the base is dropped, not deleted in the cloud.
        ({"card:a": card}, {"card:a": card, "evil:x": {"a": 1}, "toString": {"b": 2}}, {}),
        # Field names that are built-in names in JavaScript, changed on both sides.
        ({"card:a": {**card, "__proto__": "mine", "constructor": "mine", "back": "mine"}}, {"card:a": card}, {"card:a": {**card, "__proto__": "theirs", "toString": "theirs", "back": "theirs"}}),
    ]
    return {
        "sync": [{"local": l, "base": b, "remote": r, "push": plan.push, "apply": plan.apply, "final": plan.final} for l, b, r in syncs for plan in [sync.plan_sync(l, b, r)]],
        "plans": [{"raw": raw, "plan": normalize_study_plan(raw)} for raw in plans],
        "cards": [{"raw": raw, "card": Card.from_dict(raw).__dict__} for raw in cards],
    }


QUIZ_TODAY = "2026-10-18"
NOTE_TEXTS = [
    "Photosynthesis is the process plants use to turn light into food. In 1492, Columbus sailed the ocean blue. The war ended in 1945.",
    "The Battle of Hastings was in 1066\nMitochondria means powerhouse of the cell\nPrimary colours: red, yellow, blue\nDNA stands for deoxyribonucleic acid",
    "It is raining today in the city. The heart has 4 chambers and pumps blood around the body. Paris",
    "Water boils at 100 degrees Celsius at sea level; A noun is called a naming word; Is this a question?; The Treaty of Versailles was signed in 1919",
    "1. Mercury 2. Venus 3. Earth",
    "Osmosis refers to water moving across a membrane | The capital of Peru is Lima | They were happy",
    "",
    "Interest rates rose by 0.25% in March 2024 according to the central bank report",
]
LIST_TEXTS = ["Mercury, Venus, Earth and Mars", "red; green; blue", "- one\n- two\n- three", "Salt and pepper", "Bread, butter", "apples, pears, or plums.", "The process plants use to turn light, water, and carbon dioxide into food.", "a\\nb\\nc"]
KIND_TEXTS = ["1945", "42", "1,000 metres", "3.14", "12 March", "May the force", "Paris", "Dr Lee", "Take the blue pill after breakfast with water", "", "4 July 1776", "50%"]


def quiz_cards():
    def card(card_id, deck, front, back, **extra):
        base = {"id": card_id, "deck": deck, "front": front, "back": back, "next_review": "2026-10-20", "repetitions": 2, "lapses": 0, "last_score": 90, "last_result": "Good", "buried_until": ""}
        base.update(extra)
        return base

    return [
        card("geo-fr", "Geography", "Capital of France", "Paris", next_review="2026-10-10", lapses=1),
        card("geo-es", "Geography", "Capital of Spain", "Madrid", next_review="2026-10-18"),
        card("geo-it", "Geography", "Capital of Italy", "Rome"),
        card("geo-de", "Geography", "Capital of Germany", "Berlin", last_score=40),
        card("geo-pl", "Geography", "Planets nearest the sun", "Mercury, Venus, Earth and Mars"),
        card("his-ww2", "History", "When did World War II end?", "1945", next_review="2026-10-01"),
        card("his-hast", "History", "Battle of Hastings", "1066"),
        card("his-bit", "History", "Study bit 3", "The Treaty of Versailles was signed in 1919"),
        card("his-gen", "History", "What should I recall from bit {n}?", "Napoleon was exiled to the island of Elba"),
        card("bio-ps", "Biology", "What is photosynthesis?", "The process plants use to turn light, water, and carbon dioxide into food.", repetitions=0, last_result="New"),
        card("bio-mito", "Biology", "Mitochondria", "The powerhouse of the cell that releases energy from food", last_result="Again"),
        card("bio-cells", "Biology", "Parts of a cell", "nucleus; membrane; cytoplasm; ribosome"),
        card("bio-same", "Biology", "Powerhouse?", "the powerhouse of the cell that releases energy from food"),
        card("bur", "Biology", "Buried card", "Never shown", buried_until="2026-12-01"),
        card("empty", "Biology", "", ""),
        card("mem-sr", "Memory Techniques", "What is spaced repetition?", "Reviewing information at increasing intervals so recall strengthens over time."),
        card("mem-rp", "Memory Techniques", "What is retrieval practice?", "Trying to recall the answer before rereading or revealing it."),
        card("num-km", "Maths", "Metres in a kilometre", "1,000"),
        card("num-pi", "Maths", "Pi to two places", "3.14"),
    ]


def question_cases():
    from memorypal import questions as q

    rng_cases = []
    for seed in (0, 1, 42, 70, 2 ** 32 - 1, 123456789):
        r = q.Rng(seed)
        values = [r.next_uint() for _ in range(6)]
        r2 = q.Rng(seed)
        rng_cases.append({"seed": seed, "uints": values, "below": [r2.below(n) for n in (1, 2, 3, 7, 10, 100, 1000)], "shuffle": q.Rng(seed).shuffle(list(range(10)))})
    cards = quiz_cards()
    quizzes = []
    for seed in range(12):
        for count, recent, types in ((5, [], None), (10, [], None), (25, [], None), (8, ["geo-fr", "his-ww2:choice", "bio-mito:cloze"], None), (6, [], ["choice", "truefalse"]), (6, [], ["recall"]), (4, [], ["match", "order", "reverse"])):
            quizzes.append({"seed": seed, "count": count, "recent": recent, "types": types, "quiz": q.build_quiz(cards, count, q.Rng(seed), recent_ids=recent, types=types, today=QUIZ_TODAY)})
    small = [cards[0], cards[1]]
    quizzes.append({"seed": 3, "count": 5, "recent": [], "types": None, "quiz": q.build_quiz(small, 5, q.Rng(3), today=QUIZ_TODAY), "cards": "small"})
    singles = []
    for index, card in enumerate(cards):
        for kind in q.TYPES:
            singles.append({"card": card["id"], "type": kind, "seed": index, "question": q.card_question(card, kind, cards, q.Rng(index * 7 + len(kind)))})
    bits = [bit for text in NOTE_TEXTS for bit in text.replace("|", "\n").replace(";", "\n").split("\n")] + ["  - The Nile is the longest river.  ", "Pi is about 3.14 and never ends", "AI", "x: y", "Gold is Au"]
    return {
        "today": QUIZ_TODAY,
        "rng": rng_cases,
        "cards": cards,
        "quizzes": quizzes,
        "singles": singles,
        "notes": [{"text": text, "questions": q.note_questions(text)} for text in NOTE_TEXTS],
        "bits": [{"bit": bit, "question": q.question_for_bit(bit)} for bit in bits],
        "lists": [{"text": text, "items": q.list_items(text)} for text in LIST_TEXTS],
        "kinds": [{"text": text, "kind": q.answer_kind(text)} for text in KIND_TEXTS],
        "cloze": [{"text": text, "candidates": [list(c) for c in q.cloze_candidates(text, "What is photosynthesis?")]} for text in ANSWERS],
        "generic": [{"front": f, "back": b, "deck": d, "generic": q.is_generic_front(f, b, d)} for f, b, d in (("Study bit 4", "x", ""), ("What should I recall from bit 2?", "x", ""), ("Notes: P____", "Paris", "Notes"), ("Capital of France", "Paris", "Geo"), ("", "x", ""))],
    }


def main():
    specs = card_specs()
    sessions, multi = plan_cases(specs)
    tech, parse = technique_cases()
    sync_plans, sync_conversion = sync_cases()
    fixtures = {
        "security": security_cases(),
        "hostile": hostile_cases(),
        "sync_plans": sync_plans,
        "sync_conversion": sync_conversion,
        "generated_for": "latest_app/memorypal",
        "smart_check": smart_check_cases(),
        "split": [{"raw": raw, "bits": split_study_bits(raw)} for raw in TEXTS],
        "prompt_answer": [{"raw": raw, "items": parse_prompt_answer_lines(raw)} for raw in PROMPT_TEXTS],
        "tokens": [{"raw": raw, "tokens": text_tokens(raw)} for raw in ANSWERS + TEXTS],
        "sequence": sequence_cases(),
        "schedule": schedule_cases(),
        "plan_cards": specs,
        "sessions": sessions,
        "multi_day": multi,
        "techniques": tech,
        "parse_ideas": parse,
        "progress": progress_cases(specs),
        "today_check": today_iso(),
        "questions": question_cases(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(fixtures, indent=1, ensure_ascii=False), encoding="utf-8")
    counts = {key: len(value) for key, value in fixtures.items() if isinstance(value, list)}
    print(f"wrote {OUT}: {counts}")


if __name__ == "__main__":
    main()
