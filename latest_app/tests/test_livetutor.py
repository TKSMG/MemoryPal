import base64
import json
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from memorypal import ai, liveaudio, livetutor  # noqa: E402
from test_ai import ENV, FakeOpener  # noqa: E402


def b64(size):
    return base64.b64encode(bytes(size)).decode("ascii")


class FakeSocket:
    def __init__(self, url):
        self.url, self.sent, self.closed = url, [], False

    def send(self, text):
        self.sent.append(json.loads(text))

    def close(self):
        self.closed = True


class FakeAudio:
    def __init__(self):
        self.played, self.cleared, self.muted, self.stopped, self.on_mic = [], 0, False, False, None

    def start(self, on_mic):
        self.on_mic = on_mic

    def set_muted(self, muted):
        self.muted = muted

    def play(self, data):
        self.played.append(data)

    def clear(self):
        self.cleared += 1

    def stop(self):
        self.stopped = True


def audio_message(seconds):
    return {"serverContent": {"modelTurn": {"parts": [{"inlineData": {"data": b64(int(seconds * 48000)), "mimeType": "audio/pcm;rate=24000"}}]}}}


class Conversation:
    def __init__(self, minutes=10):
        self.clock = 1000.0
        self.audio = FakeAudio()
        self.cards = {"c1": SimpleNamespace(id="a", front="Capital of France?", back="Paris"), "c2": SimpleNamespace(id="b", front="2 + 2?", back="4")}
        self.tutor = livetutor.LiveTutor("auth_tokens/xyz", {"model": "models/gemini-3.8-live"}, self.cards, minutes, self.open, self.audio, now=lambda: self.clock, threaded=False)
        self.tutor.start()

    def open(self, url):
        self.socket = FakeSocket(url)
        return self.socket

    def server(self, message, binary=False):
        text = json.dumps(message)
        self.tutor.receive(text.encode("utf-8") if binary else text)

    def advance(self, seconds):
        self.clock += seconds
        self.tutor.tick()


class LiveTutorTests(unittest.TestCase):
    def test_connects_sends_setup_then_starts_tutor_and_microphone(self):
        talk = Conversation()
        self.assertIn("BidiGenerateContentConstrained?access_token=auth_tokens%2Fxyz", talk.socket.url)
        self.assertEqual(talk.socket.sent[0], {"setup": {"model": "models/gemini-3.8-live"}})
        self.assertEqual(talk.tutor.snapshot().phase, "connecting")
        talk.server({"setupComplete": {}}, binary=True)
        self.assertEqual(talk.tutor.snapshot().phase, "live")
        self.assertTrue(talk.socket.sent[1]["clientContent"]["turnComplete"])
        talk.audio.on_mic("AQIDBA==")
        self.assertEqual(talk.socket.sent[2], {"realtimeInput": {"audio": {"data": "AQIDBA==", "mimeType": "audio/pcm;rate=16000"}}})

    def test_speech_plays_and_talking_over_it_clears_it(self):
        talk = Conversation()
        talk.server({"setupComplete": {}})
        for _ in range(10):
            talk.server(audio_message(0.1))
        self.assertEqual(len(talk.audio.played), 10)
        self.assertEqual(talk.tutor.snapshot().speaking, "tutor")
        talk.advance(0.2)
        talk.server({"serverContent": {"interrupted": True}})
        self.assertEqual(talk.audio.cleared, 1)
        self.assertNotEqual(talk.tutor.snapshot().speaking, "tutor")

    def test_captions_follow_each_turn(self):
        talk = Conversation()
        talk.server({"setupComplete": {}})
        talk.server({"serverContent": {"outputTranscription": {"text": "What is the capital "}}})
        talk.server({"serverContent": {"outputTranscription": {"text": "of France?"}}})
        talk.server({"serverContent": {"turnComplete": True}})
        talk.server({"serverContent": {"inputTranscription": {"text": "Paris"}}})
        snap = talk.tutor.snapshot()
        self.assertEqual((snap.tutor_line, snap.you_line), ("What is the capital of France?", "Paris"))
        talk.server({"serverContent": {"outputTranscription": {"text": "Yes! Next one."}}})
        talk.server({"serverContent": {"inputTranscription": {"text": "Four"}}})
        snap = talk.tutor.snapshot()
        self.assertEqual((snap.tutor_line, snap.you_line), ("Yes! Next one.", "Four"))

    def test_record_answer_rates_each_card_once_and_answers_every_call(self):
        talk = Conversation()
        talk.server({"setupComplete": {}})
        talk.server({"toolCall": {"functionCalls": [{"id": "1", "name": "record_answer", "args": {"card": "c1", "result": "right", "said": "Paris"}}]}})
        talk.server({"toolCall": {"functionCalls": [{"id": "2", "name": "record_answer", "args": {"card": "c1", "result": "wrong"}}, {"id": "3", "name": "record_answer", "args": {"card": "c9", "result": "right"}}]}})
        talk.server({"toolCall": {"functionCalls": [{"id": "4", "name": "record_answer", "args": {"card": "c2", "result": "skipped"}}]}})
        self.assertEqual([(card.id, outcome) for card, outcome in talk.tutor.take_ratings()], [("a", "right")])
        self.assertEqual(talk.tutor.take_ratings(), [])
        responses = [r for m in talk.socket.sent if "toolResponse" in m for r in m["toolResponse"]["functionResponses"]]
        self.assertEqual([(r["id"], r["response"]["result"]) for r in responses], [("1", "saved"), ("2", "saved"), ("3", "error: unknown card key or result"), ("4", "saved")])
        self.assertTrue(all(r["response"]["scheduling"] == "SILENT" for r in responses))
        self.assertEqual([(r.card.id, r.outcome) for r in talk.tutor.snapshot().results], [("a", "wrong"), ("b", "skipped")])

    def test_end_session_lets_the_goodbye_play_then_hangs_up(self):
        talk = Conversation()
        talk.server({"setupComplete": {}})
        talk.server(audio_message(0.5))
        talk.server({"toolCall": {"functionCalls": [{"id": "9", "name": "end_session", "args": {}}]}})
        talk.advance(0.3)
        self.assertEqual(talk.tutor.snapshot().phase, "live")
        talk.advance(1.0)
        self.assertEqual(talk.tutor.snapshot().phase, "done")
        self.assertTrue(talk.socket.closed and talk.audio.stopped)

    def test_last_minute_asks_for_a_wrap_up_and_time_up_ends_it(self):
        talk = Conversation(minutes=2)
        talk.server({"setupComplete": {}})
        talk.advance(61)
        wrap = [m for m in talk.socket.sent if m.get("clientContent", {}).get("turnComplete") is False]
        self.assertIn("one minute", json.dumps(wrap))
        talk.advance(60)
        self.assertEqual(talk.tutor.snapshot().phase, "done")

    def test_mute_stops_sending_and_a_dropped_line_keeps_results(self):
        talk = Conversation()
        talk.server({"setupComplete": {}})
        talk.server({"toolCall": {"functionCalls": [{"id": "1", "name": "record_answer", "args": {"card": "c2", "result": "close"}}]}})
        talk.tutor.set_muted(True)
        self.assertTrue(talk.audio.muted)
        self.assertEqual(talk.socket.sent[-1], {"realtimeInput": {"audioStreamEnd": True}})
        count = len(talk.socket.sent)
        talk.audio.on_mic("AQI=")
        self.assertEqual(len(talk.socket.sent), count)
        talk.tutor.closed(talk.socket, 1006, "")
        snap = talk.tutor.snapshot()
        self.assertEqual(snap.phase, "error")
        self.assertIn("saved", snap.error)
        self.assertEqual([(card.id, outcome) for card, outcome in talk.tutor.take_ratings()], [("b", "close")])

    def test_a_refused_start_says_the_tutor_is_busy(self):
        talk = Conversation()
        talk.tutor.closed(talk.socket, 1008, "Quota exceeded")
        self.assertIn("busy", talk.tutor.snapshot().error)

    def test_a_microphone_that_fails_to_open_is_an_error(self):
        talk = Conversation()
        talk.audio.start = mock.Mock(side_effect=OSError("no device"))
        talk.server({"setupComplete": {}})
        self.assertEqual(talk.tutor.snapshot().phase, "error")
        self.assertIn("microphone", talk.tutor.snapshot().error)

    def test_verdicts_map_to_schedule_ratings(self):
        self.assertEqual(livetutor.live_assessment("right")["quality"], 4)
        self.assertEqual(livetutor.live_assessment("close")["quality"], 3)
        self.assertEqual(livetutor.live_assessment("wrong")["quality"], 1)
        self.assertIsNone(livetutor.live_assessment("skipped"))


@mock.patch.dict(os.environ, ENV)
class StartLiveTests(unittest.TestCase):
    def test_sends_keyed_cards_and_returns_token_setup_and_keys(self):
        opener = FakeOpener({"ok": True, "action": "live", "remaining": 7, "result": {"token": "auth_tokens/t", "setup": {"model": "models/m"}, "minutes": 10}})
        cards = [SimpleNamespace(front=f" Q{i} ", back=f"A{i}") for i in range(45)]
        cards[1] = SimpleNamespace(front="No answer", back=" ")
        started = ai.start_live("token", cards, "Bio", opener=opener)
        sent = opener.sent()
        self.assertEqual(sent["action"], "live")
        self.assertEqual(len(sent["cards"]), 40)
        self.assertEqual(sent["cards"][:2], [{"key": "c1", "front": "Q0", "back": "A0"}, {"key": "c2", "front": "Q2", "back": "A2"}])
        self.assertEqual(started["keys"]["c2"], 2)
        self.assertEqual((started["token"], started["minutes"], started["remaining"]), ("auth_tokens/t", 10, 7))

    def test_a_used_up_allowance_is_reported(self):
        opener = FakeOpener({"ok": False, "error": "limit_reached"}, status=429)
        with self.assertRaises(ai.AIError) as caught:
            ai.start_live("token", [("Q", "A")], opener=opener)
        self.assertEqual(caught.exception.code, "limit_reached")


class AudioHelperTests(unittest.TestCase):
    def test_resampling_keeps_length_ratios_across_chunks(self):
        for source, target in ((24000, 48000), (48000, 16000), (44100, 16000)):
            converter = liveaudio.Resampler(source, target)
            total = sum(len(converter.convert(bytes(source // 100 * 2))) for _ in range(100))
            self.assertAlmostEqual(total / 2, target, delta=target * 0.01)

    def test_pure_python_resampling_matches_lengths_too(self):
        with mock.patch.object(liveaudio, "audioop", None):
            for source, target in ((24000, 48000), (48000, 16000)):
                converter = liveaudio.Resampler(source, target)
                total = sum(len(converter.convert(bytes(source // 100 * 2))) for _ in range(100))
                self.assertAlmostEqual(total / 2, target, delta=target * 0.01)

    def test_level_is_zero_for_silence_and_higher_for_speech(self):
        self.assertEqual(liveaudio.level(bytes(960)), 0.0)
        loud = b"".join(int(4000 * (1 if i % 20 < 10 else -1)).to_bytes(2, "little", signed=True) for i in range(480))
        self.assertGreater(liveaudio.level(loud), 0.5)

    def test_microphone_frames_are_cleaned_converted_and_sent_in_tenth_seconds(self):
        sent = []
        audio = liveaudio.LiveAudio()
        audio.apm = mock.Mock()
        audio.AudioFrame = lambda data, rate, channels, frames: SimpleNamespace(data=memoryview(data))
        audio.to_device = liveaudio.Resampler(24000, 48000)
        audio.to_model = liveaudio.Resampler(48000, 16000)
        audio.sending, audio.counts, audio.on_mic = bytearray(), {"tutor": 0, "you": 0}, sent.append
        for _ in range(20):
            audio.process("speaker", bytes(960))
            audio.process("mic", bytes(960))
        self.assertEqual(audio.apm.process_reverse_stream.call_count, 20)
        self.assertEqual(audio.apm.process_stream.call_count, 20)
        self.assertEqual([len(base64.b64decode(chunk)) for chunk in sent], [3200, 3200])
        audio.set_muted(True)
        for _ in range(10):
            audio.process("mic", bytes(960))
        self.assertEqual(len(sent), 2)

    def test_playback_queues_and_clear_drops_it(self):
        audio = liveaudio.LiveAudio()
        audio.to_device = liveaudio.Resampler(24000, 48000)
        audio.play(b64(480))
        out = bytearray(960)
        audio.speak(out, 480, None, None)
        self.assertEqual(audio.jobs.get_nowait()[0], "speaker")
        audio.play(b64(4800))
        audio.clear()
        audio.speak(out, 480, None, None)
        self.assertEqual(bytes(out), bytes(960))


@unittest.skipUnless(liveaudio.available(), "livekit/sounddevice not installed")
class EchoCancellerTests(unittest.TestCase):
    def test_the_echo_canceller_removes_the_tutor_from_the_microphone(self):
        import math
        import random
        import struct

        from livekit import rtc

        apm = rtc.AudioProcessingModule(echo_cancellation=True, noise_suppression=True, high_pass_filter=True)
        apm.set_stream_delay_ms(40)
        rate, size, delay = 48000, 480, 1920
        rng = random.Random(1)
        far = [int(8000 * math.sin(i * 2 * math.pi * (300 + 200 * math.sin(i / 4000)) / rate) + rng.gauss(0, 800)) for i in range(rate * 5)]
        before = after = 0.0
        for n in range(len(far) // size):
            speaker = rtc.AudioFrame(bytearray(struct.pack(f"<{size}h", *far[n * size:(n + 1) * size])), rate, 1, size)
            apm.process_reverse_stream(speaker)
            echo = [far[n * size + k - delay] // 2 if n * size + k >= delay else 0 for k in range(size)]
            mic = rtc.AudioFrame(bytearray(struct.pack(f"<{size}h", *echo)), rate, 1, size)
            apm.process_stream(mic)
            if n > 250:
                before += liveaudio.level(struct.pack(f"<{size}h", *echo))
                after += liveaudio.level(bytes(mic.data.cast("B")))
        self.assertLess(after, before * 0.2)


if __name__ == "__main__":
    unittest.main()
