"""Bold, italics and highlighting in notes, kept as plain text with marks.

**bold**, _italic_ (or *italic*) and ==highlighted== are written into the
text itself, the way Markdown does, so notes stay plain strings: they save,
sync and export exactly as before, and an older copy of the app simply
shows the marks. The phone has the same logic in mobile/src/core/richtext.ts;
tools/parity/make_fixtures.py checks they agree.

A mark opens only before text (not a space) and closes only after text, so
"2 * 3" or "a == b" stay as typed. *, _ and == also need a word edge outside
them, so snake_case names and "2*3*4" stay whole (** may sit inside a word,
as in Markdown). A mark that never closes is shown as typed.
"""

BOLD, ITALIC, HIGHLIGHT = "bold", "italic", "highlight"
MARKS = {BOLD: "**", ITALIC: "*", HIGHLIGHT: "=="}
# Longest first, so "**" is read before "*".
_TOKENS = (("**", BOLD), ("==", HIGHLIGHT), ("*", ITALIC), ("_", ITALIC))


def _word_char(char):
    return bool(char) and char.isalnum()


def _scan(text):
    """(pieces, unclosed openers, unopened closers) for one piece of text.

    pieces are [start, end, kind, raw], kind "text" or the style a mark
    toggles. Openers and closers that never pair are text in pieces and are
    listed (as their raw marks) for balance_bits.
    """
    text = str(text or "")
    pieces = []
    open_at = {}  # style -> (index in pieces, raw mark)
    closers = []
    i = 0
    while i < len(text):
        found = next(((raw, style) for raw, style in _TOKENS if text.startswith(raw, i)), None)
        if found is None:
            pieces.append([i, i + 1, "text", text[i]])
            i += 1
            continue
        raw, style = found
        end = i + len(raw)
        before = text[i - 1] if i else ""
        after = text[end] if end < len(text) else ""
        edge = raw != "**"  # these need a word edge on the outside
        can_open = bool(after) and not after.isspace() and not (edge and _word_char(before))
        can_close = bool(before) and not before.isspace() and not (edge and _word_char(after))
        if can_close and style in open_at and open_at[style][1] == raw:
            pieces[open_at.pop(style)[0]][2] = style
            pieces.append([i, end, style, raw])
        elif can_open and style not in open_at:
            open_at[style] = (len(pieces), raw)
            pieces.append([i, end, "text", raw])
        else:
            if can_close:
                closers.append(raw)
            pieces.append([i, end, "text", raw])
        i = end
    unclosed = [raw for _index, raw in sorted(open_at.values())]
    return pieces, unclosed, closers


def tokens(text):
    """The text as (start, end, kind, raw) pieces, kind "text" or a style.

    Style pieces are the marks themselves, already paired: every mark in
    the result opens or closes that style. Neighbouring text is joined.
    """
    merged = []
    for start, end, kind, raw in _scan(text)[0]:
        if kind == "text" and merged and merged[-1][2] == "text":
            merged[-1] = (merged[-1][0], end, "text", merged[-1][3] + raw)
        else:
            merged.append((start, end, kind, raw))
    return merged


def spans(text):
    """Runs of text with their styles: [{"text", "bold", "italic", "highlight"}]."""
    active = {BOLD: False, ITALIC: False, HIGHLIGHT: False}
    result = []
    for _start, _end, kind, raw in tokens(text):
        if kind != "text":
            active[kind] = not active[kind]
            continue
        if result and all(result[-1][name] == active[name] for name in active):
            result[-1]["text"] += raw
        else:
            result.append({"text": raw, **active})
    return result


def plain(text):
    """The words without the marks, for reading aloud, searching and cards."""
    return "".join(span["text"] for span in spans(text))


def has_marks(text):
    return any(kind != "text" for *_rest, kind, _raw in tokens(text))


def marked(text):
    """The bold or highlighted words, in order: what the notes say matters most."""
    return [span["text"].strip() for span in spans(text) if (span[BOLD] or span[HIGHLIGHT]) and span["text"].strip()]


def blank_marked(text, blank="_____"):
    """(the plain sentence with bold or highlighted words blanked, those words) or None."""
    found = marked(text)
    if not found:
        return None
    out = []
    for span in spans(text):
        if (span[BOLD] or span[HIGHLIGHT]) and span["text"].strip():
            if not (out and out[-1] == blank):
                out.append(blank)
        else:
            out.append(span["text"])
    return "".join(out), ", ".join(found)


def balance_bits(bits):
    """Close marks a split cut through, and reopen them in the next bit.

    "**Hi. There** now" splits into "**Hi" and "There** now"; this gives
    "**Hi**" and "**There** now". A mark is carried only when the next bit
    has the closing half, so "a ==> b" stays as typed. Bits without marks
    come back unchanged.
    """
    bits = list(bits)
    result = []
    carry = []
    for index, bit in enumerate(bits):
        bit = "".join(carry) + bit
        _pieces, unclosed, _closers = _scan(bit)
        following = _scan(bits[index + 1])[2] if index + 1 < len(bits) else []
        carry = [raw for raw in unclosed if raw in following]
        result.append(bit + "".join(reversed(carry)))
    return result


def _run(text, index, step):
    """How many * sit next to index, walking by step (-1 left, 1 right)."""
    count = 0
    i = index - 1 if step < 0 else index
    while 0 <= i < len(text) and text[i] == "*":
        count += 1
        i += step
    return count


def _around(text, start, end, style):
    """The size of the style's marks just outside text[start:end], or 0."""
    if style == HIGHLIGHT:
        return 2 if text[max(0, start - 2):start] == "==" and text[end:end + 2] == "==" else 0
    if style == ITALIC and start and end < len(text) and text[start - 1] == "_" == text[end]:
        return 1
    stars = min(_run(text, start, -1), _run(text, end, 1))
    if style == BOLD:
        return 2 if stars >= 2 else 0
    return 1 if stars % 2 else 0


def toggle(text, start, end, style):
    """Add or remove a style on text[start:end], like a B or I button.

    Returns (new text, new start, new end) with the same words selected.
    With nothing selected it puts an empty pair at the cursor, cursor
    inside. Spaces at the edges of the selection stay outside the marks.
    """
    text = str(text or "")
    mark = MARKS[style]
    start, end = sorted((max(0, min(start, len(text))), max(0, min(end, len(text)))))
    # The selection includes the marks: take them away.
    chosen = text[start:end]
    if style == ITALIC and len(chosen) > 2 and chosen[0] == "_" == chosen[-1]:
        size = 1
    elif style == HIGHLIGHT:
        size = 2 if len(chosen) > 4 and chosen.startswith("==") and chosen.endswith("==") else 0
    else:
        stars = min(len(chosen) - len(chosen.lstrip("*")), len(chosen) - len(chosen.rstrip("*")))
        size = (2 if stars >= 2 else 0) if style == BOLD else (1 if stars % 2 else 0)
        if 2 * stars >= len(chosen):
            size = 0
    if size:
        inner = chosen[size:-size]
        return text[:start] + inner + text[end:], start, start + len(inner)
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    # Already marked just outside the selection: take the marks away.
    size = _around(text, start, end, style)
    if size and start < end:
        return text[:start - size] + text[start:end] + text[end + size:], start - size, end - size
    size = len(mark)
    if start == end:
        return text[:start] + mark + mark + text[start:], start + size, start + size
    return text[:start] + mark + text[start:end] + mark + text[end:], start + size, end + size
