"""The speech gate in front of the live tutor's ears (same cases as the phone's liveTutor.test.ts)."""

import base64
import math
import os
import sys
import unittest
from array import array

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from memorypal import livetutor, speechgate  # noqa: E402


def tone(ms, db):
    """base64 16 kHz PCM: `ms` of a tone at `db` dBFS (or silence below -99)."""
    count = round(ms * 16000 / 1000)
    amp = 0 if db <= -99 else 10 ** (db / 20) * 32767 * math.sqrt(2)
    samples = array("h", (max(-32768, min(32767, round(amp * math.sin(2 * math.pi * 220 * i / 16000)))) for i in range(count)))
    if sys.byteorder != "little":
        samples.byteswap()
    return base64.b64encode(samples.tobytes()).decode("ascii")


def silent(chunk):
    return not any(base64.b64decode(chunk))


class SpeechGateTest(unittest.TestCase):
    def test_helpers(self):
        for n in range(9):
            self.assertEqual(base64.b64decode(speechgate.silence_b64(n)), bytes(n))
        self.assertEqual(round(speechgate.level_db(base64.b64decode(tone(100, -20)))), -20)
        self.assertEqual(speechgate.level_db(b""), -100.0)

    def test_noise_and_clicks_send_silence_of_the_same_length(self):
        gate = speechgate.SpeechGate()
        for _ in range(50):
            chunk = tone(20, -58)
            out = gate.process(chunk, False)
            self.assertEqual(len(out), 1)
            self.assertTrue(silent(out[0]))
            self.assertEqual(len(base64.b64decode(out[0])), len(base64.b64decode(chunk)))
        self.assertTrue(all(silent(c) for c in gate.process(tone(20, -20), False)))
        self.assertTrue(all(silent(c) for c in gate.process(tone(20, -20), False)))
        for _ in range(10):
            gate.process(tone(20, -60), False)
        self.assertFalse(gate.open)

    def test_speech_opens_with_preroll_and_stays_open_through_a_pause(self):
        gate = speechgate.SpeechGate()
        for _ in range(40):
            gate.process(tone(20, -60), False)
        speech = tone(20, -25)
        out = []
        for _ in range(20):
            out = gate.process(speech, False)
            if gate.open:
                break
        self.assertTrue(gate.open)
        self.assertGreater(len(out), speechgate.PREROLL_MS / 20 - 2)
        self.assertEqual(out[-1], speech)
        for _ in range(int((speechgate.HANG_MS - 100) / 20)):
            self.assertEqual(len(gate.process(tone(20, -60), False)), 1)
        self.assertTrue(gate.open)
        for _ in range(10):
            gate.process(tone(20, -60), False)
        self.assertFalse(gate.open)

    def test_tutor_echo_and_a_cough_are_kept_out_but_talking_over_gets_through(self):
        gate = speechgate.SpeechGate()
        for _ in range(40):
            gate.process(tone(20, -60), False)
        for _ in range(100):
            self.assertTrue(all(silent(c) for c in gate.process(tone(20, -38), True)))
        for _ in range(10):
            gate.process(tone(20, -15), True)
        for _ in range(10):
            gate.process(tone(20, -60), True)
        self.assertFalse(gate.open)
        for _ in range(30):
            gate.process(tone(20, -20), True)
            if gate.open:
                break
        self.assertTrue(gate.open)

    def test_desktop_sized_chunks(self):
        # The desktop sends about 100 ms at a time: one loud chunk isn't enough, two are.
        gate = speechgate.SpeechGate()
        for _ in range(10):
            gate.process(tone(100, -60), False)
        self.assertTrue(silent(gate.process(tone(100, -20), False)[0]))
        gate.process(tone(100, -60), False)
        gate.process(tone(100, -60), False)
        self.assertFalse(gate.open)
        gate.process(tone(100, -20), False)
        out = gate.process(tone(100, -20), False)
        self.assertTrue(gate.open)
        self.assertFalse(silent(out[-1]))

    def test_tutor_uses_the_gate_by_default(self):
        class Audio:
            def start(self, on_mic):
                self.on_mic = on_mic

            def set_muted(self, muted):
                pass

            def play(self, data):
                pass

            def clear(self):
                pass

            def stop(self):
                pass

        class Socket:
            def __init__(self):
                self.sent = []

            def send(self, text):
                import json

                self.sent.append(json.loads(text))

            def close(self):
                pass

        socket, audio = Socket(), Audio()
        tutor = livetutor.LiveTutor("t", {}, {"c1": object()}, 10, lambda url: socket, audio, now=lambda: 100.0, threaded=False)
        tutor.start()
        tutor.receive('{"setupComplete": {}}')
        before = len(socket.sent)
        audio.on_mic(tone(20, -60))
        self.assertTrue(silent(socket.sent[before]["realtimeInput"]["audio"]["data"]))
        for _ in range(20):
            audio.on_mic(tone(20, -20))
        self.assertFalse(silent(socket.sent[-1]["realtimeInput"]["audio"]["data"]))
        tutor.set_muted(True)
        count = len(socket.sent)
        audio.on_mic(tone(20, -20))
        self.assertEqual(len(socket.sent), count)


if __name__ == "__main__":
    unittest.main()
