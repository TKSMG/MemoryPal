"""A gate in front of the AI tutor's ears.

Gemini Live treats any sound on the microphone as the learner starting to
talk: a cough, a door, a TV, or the tutor's own voice leaking back from the
speakers stopped it mid-sentence, and it then answered words nobody said (the
noise, transcribed) or started its question over and over. The gate sends the
microphone as it is only while someone is really talking; the rest of the
time it sends silence of the same length, so the stream never pauses and
Google still hears when a turn ends.

- While the tutor is quiet, speech opens the gate after a short moment.
- While the tutor is talking (and just after), only clearly louder speech that
  keeps going opens it, so talking over the tutor still works but echo and
  short noises don't.
- The last half second before the gate opens is sent too, so the first words
  aren't lost.
- Thresholds follow the room's own noise level.

Same numbers as mobile/src/features/speechGate.ts on the phone.
"""

import base64
import math
import sys
from array import array

FLOOR_START_DB = -60.0
FLOOR_MAX_DB = -50.0  # so the bar for speech never rises past -38 dBFS and quieter words still count
FLOOR_NEAR_DB = 6.0  # sounds this close above the noise move it at the normal pace; louder ones (soft speech) barely do
FLOOR_MIN_DB = -75.0
TALK_ABOVE_FLOOR_DB = 12.0
TALK_MIN_DB = -52.0  # low enough for someone speaking softly or a little away from the microphone
BARGE_ABOVE_FLOOR_DB = 22.0
BARGE_MIN_DB = -36.0
OPEN_MS = 150.0
BARGE_MS = 600.0  # a "mm" or "okay" while the tutor talks is shorter; someone who means to cut in keeps going
HANG_MS = 1200.0  # a pause between words never cuts into an answer
BARGE_HANG_MS = 250.0
PREROLL_MS = 500.0
ECHO_TAIL_MS = 500.0

_silence = {}


def silence_b64(size):
    """Base64 of `size` zero bytes: silence of the same length."""
    cached = _silence.get(size)
    if cached is None:
        cached = base64.b64encode(bytes(size)).decode("ascii")
        if len(_silence) < 64:
            _silence[size] = cached
    return cached


def level_db(pcm):
    """Loudness of 16-bit little-endian mono PCM bytes, in dBFS (-100 for silence)."""
    count = len(pcm) // 2
    if not count:
        return -100.0
    samples = array("h")
    samples.frombytes(bytes(pcm[: count * 2]))
    if sys.byteorder != "little":
        samples.byteswap()
    total = 0
    for value in samples:
        total += value * value
    rms = math.sqrt(total / count) / 32768
    return max(-100.0, 20 * math.log10(rms)) if rms > 0 else -100.0


class SpeechGate:
    def __init__(self, rate=16000):
        self.rate = rate
        self.open = False
        self.floor = FLOOR_START_DB
        self.above_ms = 0.0
        self.quiet_ms = 0.0
        self.preroll = []
        self.preroll_ms = 0.0
        # The last chunk's loudness, and whether it counted as speech (for the tutor's checks).
        self.last_db = -100.0
        self.last_loud = False

    def reset(self):
        """Back to closed (muted, or a fresh start); the noise estimate is kept."""
        self.open = False
        self.above_ms = 0.0
        self.quiet_ms = 0.0
        self.preroll = []
        self.preroll_ms = 0.0

    def process(self, data_b64, tutor_talking):
        """Takes one base64 chunk from the microphone and returns what to send,
        in order: the chunk itself, silence of its length, or (as the gate
        opens) the half second before it and then the chunk."""
        try:
            pcm = base64.b64decode(data_b64)
        except (ValueError, TypeError):
            return []
        ms = len(pcm) / 2 / self.rate * 1000
        if not ms:
            return []
        db = level_db(pcm)
        talk = max(TALK_MIN_DB, self.floor + TALK_ABOVE_FLOOR_DB)
        barge = max(BARGE_MIN_DB, self.floor + BARGE_ABOVE_FLOOR_DB)
        threshold = barge if tutor_talking else talk
        self.last_db = db
        self.last_loud = db >= threshold
        if self.open:
            # Once the tutor talks again, only real speech keeps the gate open, so its echo can't.
            self.quiet_ms = 0.0 if db >= threshold else self.quiet_ms + ms
            if self.quiet_ms >= (BARGE_HANG_MS if tutor_talking else HANG_MS):
                self.reset()
            return [data_b64]
        need = BARGE_MS if tutor_talking else OPEN_MS
        if db >= threshold:
            self.above_ms += ms
        else:
            # Short dips between syllables don't start the count again.
            self.above_ms = max(0.0, self.above_ms - ms)
            # Learn the room's noise while nobody is talking (not from the tutor's echo).
            if not tutor_talking and db < talk:
                self._learn(db, ms)
        if self.above_ms >= need:
            out = [chunk for chunk, _ in self.preroll] + [data_b64]
            self.reset()
            self.open = True
            return out
        self.preroll.append((data_b64, ms))
        self.preroll_ms += ms
        while len(self.preroll) > 1 and self.preroll_ms - self.preroll[0][1] >= PREROLL_MS:
            self.preroll_ms -= self.preroll.pop(0)[1]
        return [silence_b64(len(pcm))]

    def _learn(self, db, ms):
        # Quick to follow the noise down, slow to follow it up, and very slow for
        # sounds well above it: those are mostly soft speech, and learning from
        # them raised the bar until the learner's quieter words were cut out.
        rise = db - self.floor
        if rise < 0:
            weight = min(1.0, ms / 300)
        elif rise <= FLOOR_NEAR_DB:
            weight = min(1.0, ms / 4000)
        else:
            weight = min(1.0, ms / 30000)
        self.floor = min(FLOOR_MAX_DB, max(FLOOR_MIN_DB, self.floor + (db - self.floor) * weight))
