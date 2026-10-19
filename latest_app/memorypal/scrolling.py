"""Wheel and touchpad scrolling maths, kept free of Tk so it can be tested.

A mouse wheel moves in notches: Windows reports each one as a delta of 120
(Tk on X11 sends Button-4/5 instead). Jumping a whole notch at once looks
like a stutter, so a notch moves a target and the page glides towards it
with an ease-out curve. More notches before the glide ends push the same
target further, so a fast spin is one continuous glide rather than a string
of restarts.

Touchpads are different: Windows precision touchpads send many small deltas
that are not multiples of 120, already smoothed by the system, and they
should be followed 1:1 (easing them again makes the page trail the fingers).
macOS sends small deltas for both wheels and trackpads; there the gap since
the previous event tells them apart well enough: an isolated event is a
wheel notch and glides, a dense stream (trackpad, or a wheel spun fast and
already accelerated by macOS) follows almost directly.
"""

import math

NOTCH = 120
# Gap between wheel events (seconds) above which a macOS event counts as a
# separate notch rather than part of a stream.
STREAM_GAP_S = 0.05
# After a touchpad delta, whole-notch deltas for this long still come from
# the touchpad (Windows sends a few when the fingers move fast).
TOUCHPAD_HOLD_S = 0.4
# Ease-out time constants (ms). A 72px notch settles in about 160ms.
NOTCH_TAU_MS = 38.0
# About one frame: a dense macOS stream stays glued to the fingers.
STREAM_TAU_MS = 12.0
MAC_DELTA_DIVISOR = 7.0


def wheel_motion(delta, step_px, mac=False, button=None, gap_s=1.0, since_touchpad_s=float("inf"), reduce_motion=False):
    """How far one wheel event moves the page, and how.

    Returns (pixels, tau_ms): positive pixels scroll down. tau_ms is the
    glide's time constant, or 0 to follow the event directly (touchpads, and
    every event when reduced motion is on).
    """
    if button in (4, 5):
        pixels, tau = (-step_px if button == 4 else step_px), NOTCH_TAU_MS
    else:
        delta = float(delta or 0)
        if not delta:
            return 0.0, 0.0
        if mac and abs(delta) < NOTCH:
            pixels = -delta * step_px / MAC_DELTA_DIVISOR
            tau = NOTCH_TAU_MS if gap_s >= STREAM_GAP_S else STREAM_TAU_MS
        elif delta % NOTCH or since_touchpad_s < TOUCHPAD_HOLD_S:
            pixels, tau = -delta / NOTCH * step_px, 0.0
        else:
            pixels, tau = -delta / NOTCH * step_px, NOTCH_TAU_MS
    if reduce_motion:
        tau = 0.0
    return float(pixels), float(tau)


def is_touchpad_delta(delta, mac=False, button=None):
    """A Windows high-resolution delta (not a whole number of notches)."""
    if mac or button in (4, 5):
        return False
    delta = float(delta or 0)
    return bool(delta) and bool(delta % NOTCH)


def glide_step(remaining, elapsed_ms, tau_ms=NOTCH_TAU_MS, snap_px=1.0, min_px=1.0):
    """One frame of an ease-out glide.

    remaining is the distance left to the target. Returns (step, finished).
    The step covers 1 - e^(-elapsed/tau) of the distance, so the curve is the
    same at 60Hz or 144Hz, and it never stops short: under snap_px it lands
    exactly, and it always moves at least min_px so the tail doesn't crawl.
    """
    remaining = float(remaining)
    if abs(remaining) <= snap_px or tau_ms <= 0:
        return remaining, True
    elapsed_ms = max(0.0, float(elapsed_ms))
    step = remaining * (1.0 - math.exp(-elapsed_ms / float(tau_ms)))
    if abs(step) < min_px:
        step = math.copysign(min(min_px, abs(remaining)), remaining)
    if abs(remaining - step) <= snap_px:
        return remaining, True
    return step, False


def settle_ms(distance, tau_ms=NOTCH_TAU_MS, snap_px=1.0):
    """About how long a glide of this distance takes to land."""
    distance = abs(float(distance))
    if distance <= snap_px or tau_ms <= 0:
        return 0.0
    return float(tau_ms) * math.log(distance / snap_px)


def clamp_target(base, pixels, maximum):
    """Move a glide target, keeping it inside the scrollable range."""
    return max(0.0, min(float(maximum), float(base) + float(pixels)))


def take_lines(pending, per_frame_max=3):
    """Split a backlog of list lines into this frame's share (for Listbox, which
    can only scroll whole lines): one line a frame, more if far behind."""
    pending = int(pending)
    if not pending:
        return 0, 0
    size = min(abs(pending), max(1, min(per_frame_max, abs(pending) // 4 + 1)))
    step = size if pending > 0 else -size
    return step, pending - step
