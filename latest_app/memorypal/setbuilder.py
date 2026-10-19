"""Turning what someone types or pastes into the cards of one study set.

The set builder page stages cards as plain dicts ({"prompt", "answer",
"kind"}) so they can be previewed, removed and kept in a draft before any
Card is created. Kept free of Tk so it can be tested.
"""

from .core import normalize_space, parse_prompt_answer_lines, split_study_bits

DEFAULT_PROMPT = "What should I recall from bit {n}?"
QA_DELIMITERS = ("\t", "=>", "::", " - ")


def clean_set_name(name):
    """A set (deck) name with its spacing tidied; empty when blank."""
    return normalize_space(name or "")


def _has_delimiter(text):
    return any(delimiter in text for delimiter in QA_DELIMITERS)


def notes_to_items(text, prompt_template=DEFAULT_PROMPT, make_questions=False):
    """Split pasted notes into staged cards.

    Lines written as a question and answer ("Q => A", "Q :: A", "Q - A" or
    tab-separated, as spreadsheets and Quizlet export) become that card. Any
    other line, sentence or list item becomes a recall card: the prompt
    template on the front ({n} is its number, {total} how many there are)
    and the note itself on the back.

    With make_questions, a note that reads as a fact becomes a real question
    instead ("Paris is the capital of France" -> "What is Paris?", a date or
    key word to fill in); notes no rule fits keep the template.
    """
    from .questions import question_for_bit

    items = []
    notes = []
    for bit in split_study_bits(text or ""):
        if _has_delimiter(bit):
            parsed = parse_prompt_answer_lines(bit)
            if parsed and not parsed[0]["prompt"].startswith("Study bit "):
                items.extend({"prompt": item["prompt"], "answer": item["answer"], "kind": "qa"} for item in parsed)
                continue
        bit = normalize_space(bit)
        if bit:
            items.append(None)  # placeholder keeps the pasted order
            notes.append((len(items) - 1, bit))
    template = normalize_space(prompt_template) or DEFAULT_PROMPT
    total = len(notes)
    for number, (slot, note) in enumerate(notes, 1):
        made = question_for_bit(note) if make_questions else None
        if made is not None and made["type"] != "hint":
            items[slot] = {"prompt": made["prompt"], "answer": made["answer"], "kind": "note"}
            continue
        front = template.replace("{n}", str(number)).replace("{total}", str(total))
        if front == template and total > 1:
            front = f"{front} ({number}/{total})"
        items[slot] = {"prompt": front, "answer": note, "kind": "note"}
    return items


def typed_item(question, answer):
    """A staged card from the Question and Answer boxes, or None if no question."""
    question, answer = normalize_space(question), normalize_space(answer)
    if not question:
        return None
    return {"prompt": question, "answer": answer, "kind": "qa"}
