"""Where popups go and how wide they are, kept free of Tk so it can be tested.

Every function takes plain numbers (and a `measure(text) -> pixels` callable
for text), so the desktop app can pass a real tkinter Font's measure method
and the tests can pass a fake one.
"""

ELLIPSIS = "…"


def fit_popup_rect(width, height, anchor_rect, screen_rect, gap=0, margin=8):
    """Place a width x height popup next to anchor_rect, fully on screen.

    anchor_rect and screen_rect are (left, top, right, bottom). The popup
    opens below the anchor, left-aligned with it. If that would run off the
    right edge it is right-aligned with the anchor instead (and shifted
    further left if it is still too wide); if it would run off the bottom it
    flips above the anchor, or pins to the bottom margin when neither side
    has room. The size is capped to the screen. Returns (x, y, width, height).
    """
    s_left, s_top, s_right, s_bottom = screen_rect
    width = int(max(1, min(width, s_right - s_left - margin * 2)))
    height = int(max(1, min(height, s_bottom - s_top - margin * 2)))
    a_left, a_top, a_right, a_bottom = anchor_rect
    x = a_left
    if x + width > s_right - margin:
        x = a_right - width
    x = max(s_left + margin, min(x, s_right - margin - width))
    y = a_bottom + gap
    if y + height > s_bottom - margin:
        above = a_top - gap - height
        if above >= s_top + margin:
            y = above
        else:
            y = max(s_top + margin, s_bottom - margin - height)
    return int(x), int(y), width, height


def centered_rect(width, height, owner_rect, screen_rect, margin=8):
    """Centre a window over owner_rect, capped to and kept on the screen."""
    s_left, s_top, s_right, s_bottom = screen_rect
    width = int(max(1, min(width, s_right - s_left - margin * 2)))
    height = int(max(1, min(height, s_bottom - s_top - margin * 2)))
    o_left, o_top, o_right, o_bottom = owner_rect
    x = o_left + ((o_right - o_left) - width) // 2
    y = o_top + ((o_bottom - o_top) - height) // 2
    x = max(s_left + margin, min(x, s_right - margin - width))
    y = max(s_top + margin, min(y, s_bottom - margin - height))
    return int(x), int(y), width, height


def elide(measure, text, max_width):
    """text, shortened with an ellipsis so measure(text) <= max_width."""
    if measure(text) <= max_width:
        return text
    low, high = 0, len(text)
    while low < high:
        mid = (low + high + 1) // 2
        if measure(text[:mid].rstrip() + ELLIPSIS) <= max_width:
            low = mid
        else:
            high = mid - 1
    return text[:low].rstrip() + ELLIPSIS


def dropdown_layout(labels, measure, anchor_rect, screen_rect, row_height, inset, side, gap=4, margin=8, max_rows=10):
    """Size and place a dropdown list of labels.

    The list is as wide as its longest label (plus `side` padding on both
    sides and `inset` around the list), never narrower than the anchor and
    never wider than the screen. It shows up to max_rows rows, fewer if the
    screen is short, and labels that still cannot fit are shortened with an
    ellipsis rather than cut off. Returns (x, y, width, height, rows, shown).
    """
    labels = [str(label) for label in labels]
    text_width = max((measure(label) for label in labels), default=0) + side * 2
    width = max(anchor_rect[2] - anchor_rect[0], text_width + inset * 2)
    rows = max(1, min(len(labels), max_rows))
    x, y, width, height = fit_popup_rect(width, rows * row_height + inset * 2, anchor_rect, screen_rect, gap, margin)
    fitted = max(1, min(rows, (height - inset * 2) // max(1, row_height)))
    if fitted != rows:
        rows = fitted
        x, y, width, height = fit_popup_rect(width, rows * row_height + inset * 2, anchor_rect, screen_rect, gap, margin)
    room = width - inset * 2 - side * 2
    shown = [elide(measure, label, room) for label in labels]
    return x, y, width, height, rows, shown
