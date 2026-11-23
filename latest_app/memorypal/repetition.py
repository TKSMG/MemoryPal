"""Repetition path: recall a list in growing runs, such as 5, 5-4, 5-4-3,
then 3-2-1 back to the first item.

Each round names the items to recall by position. The person starts at one
item, walks backward one more item each round for the loop range, then
finishes with one run from where the loop stopped back to item 1. Mirrored
in mobile/src/core/repetition.ts; the parity fixtures check both agree.
"""

import re

from .core import normalize_space, parse_prompt_answer_lines

# A start this far into a long set already makes a long path; the person can
# still type a later start.
DEFAULT_START = 5
_DEFAULT_PROMPT = re.compile(r"^Study bit \d+$")


def default_start(count):
    """The start a new path uses: item 5, or the last item of a shorter list."""
    return min(max(count, 0), DEFAULT_START)


def repetition_steps(count, start=None, span=None):
    """Rounds as (label, item indexes from 0). With start 5 and range 3:
    5, 5-4, 5-4-3, then 3-2-1. No range walks all the way back to item 1."""
    if count <= 0:
        return []
    start = default_start(count) if start is None else start
    start_index = min(max(start, 1), count) - 1
    span = start_index + 1 if span is None else min(max(span, 1), count)
    steps, current = [], []
    for offset in range(span):
        index = start_index - offset
        if index < 0:
            break
        current.append(index)
        steps.append(("-".join(str(item + 1) for item in current), list(current)))
    if current and current[-1] > 0:
        walk = list(range(current[-1], -1, -1))
        steps.append(("-".join(str(item + 1) for item in walk), walk))
    return steps


def items_from_text(raw):
    """A typed list as path items. "prompt - answer" lines (or =>, ::, tab)
    keep their prompt; a plain line is remembered as itself, prompted by its
    place in the list."""
    items = []
    for item in parse_prompt_answer_lines(raw):
        prompt = item["prompt"]
        if _DEFAULT_PROMPT.match(prompt):
            prompt = f"Item {len(items) + 1}"
        items.append({"prompt": prompt, "answer": item["answer"]})
    return items


def items_from_cards(cards):
    """Cards as path items: the question is the prompt, the answer is what to recall."""
    items = []
    for card in cards:
        prompt = normalize_space(str(card.front or ""))
        answer = normalize_space(str(card.back or ""))
        if answer:
            items.append({"prompt": prompt or f"Item {len(items) + 1}", "answer": answer})
    return items


def round_expected(items, indexes):
    """The answers a round asks for, one per line, in the round's order."""
    return "\n".join(items[index]["answer"] for index in indexes)


# How many of the weakest cards a path drills: enough for a full 5-4-3-2-1
# and a little more.
WEAK_LIMIT = 10
