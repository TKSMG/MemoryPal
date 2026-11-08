"""Microphone and speaker for the live AI tutor, with echo cancelling.

The tutor talks out loud through the computer's speakers while the
microphone stays open, so the learner can talk over it. Without echo
cancelling the tutor would hear itself and keep interrupting. Video-call
apps solve this the same way: the system's own microphone and speakers
(sounddevice: Core Audio on a Mac, Windows audio on a PC) and WebRTC's audio
processing (echo cancelling, noise suppression, from the livekit package),
which removes the speaker sound from the microphone signal.

    audio = LiveAudio(on_level=lambda who, level: ...)
    audio.start(on_mic)       # on_mic(base64 16 kHz 16-bit mono PCM), about 10 times a second
    audio.play(base64_pcm)    # Gemini's 24 kHz speech, queued after what is playing
    audio.clear()             # drop unplayed speech (the learner talked over it)
    audio.set_muted(True)
    audio.stop()

The audio callbacks only copy bytes into a queue; the echo canceller and the
rate conversion run on a worker thread. Both packages are imported only when
a conversation starts, so they never slow the app's start.
"""

import base64
import importlib.util
import math
import queue
import struct
import sys
import threading
from array import array

try:  # Python 3.12 and earlier: a fast, stateful rate converter
    import audioop
except ImportError:  # removed in 3.13
    audioop = None

MIC_RATE = 16000
MODEL_RATE = 24000
DEVICE_RATE = 48000
SEND_SECONDS = 0.1
LEVEL_EVERY = 5  # frames (50 ms) between loudness updates


def available():
    """Whether this copy of the app has the audio packages (cheap: nothing is imported)."""
    return all(importlib.util.find_spec(name) is not None for name in ("sounddevice", "livekit", "websockets"))


def permission_hint():
    if sys.platform == "darwin":
        return "If the tutor can't hear you, allow MemoryPal in System Settings > Privacy & Security > Microphone."
    if sys.platform.startswith("win"):
        return "If the tutor can't hear you, turn on microphone access for desktop apps in Settings > Privacy & security > Microphone."
    return ""


class Resampler:
    """16-bit mono PCM from one rate to another, keeping state between chunks."""

    def __init__(self, source, target):
        self.source = source
        self.target = target
        self.state = None
        self.position = 0.0
        self.last = 0

    def convert(self, data):
        if self.source == self.target or not data:
            return bytes(data)
        if audioop is not None:
            out, self.state = audioop.ratecv(bytes(data), 2, 1, self.source, self.target, self.state)
            return out
        return self._linear(data)

    def _linear(self, data):
        samples = array("h")
        samples.frombytes(bytes(data))
        if sys.byteorder == "big":
            samples.byteswap()
        step = self.source / self.target
        out = array("h")
        if self.target < self.source:
            # Average each output sample's span: a cheap low-pass against aliasing.
            span = step
            pos = self.position
            while pos + span <= len(samples):
                start = max(0, int(pos))  # a few samples may belong to the last chunk
                end = max(start + 1, int(pos + span))
                window = samples[start:end]
                out.append(int(sum(window) / len(window)))
                pos += span
            self.position = pos - len(samples)
        else:
            pos = self.position
            previous = self.last
            count = len(samples)
            while pos < count:
                base = math.floor(pos)
                left = previous if base < 0 else samples[base]
                right = samples[base + 1] if base + 1 < count else samples[base] if base >= 0 else samples[0]
                frac = pos - base
                out.append(int(left + (right - left) * frac))
                pos += step
            self.position = pos - count
            self.last = samples[-1] if count else previous
        if sys.byteorder == "big":
            out.byteswap()
        return out.tobytes()


def level(data):
    """0-1 loudness of 16-bit PCM, for the picture."""
    count = len(data) // 2
    if not count:
        return 0.0
    if audioop is not None:
        rms = audioop.rms(bytes(data), 2)
    else:
        samples = struct.unpack(f"<{count}h", bytes(data[: count * 2]))
        rms = math.sqrt(sum(sample * sample for sample in samples) / count)
    # Speech sits around 500-5000; map that roughly onto 0-1.
    return max(0.0, min(1.0, (math.log10(max(rms, 1)) - 2.2) / 1.6))


class LiveAudio:
    def __init__(self, on_level=None):
        self.on_level = on_level or (lambda who, value: None)
        self.lock = threading.Lock()
        self.jobs = queue.Queue()
        self.playback = bytearray()
        self.streams = []
        self.worker = None
        self.running = False
        self.muted = False
        self.rate = DEVICE_RATE
        self.frame_bytes = DEVICE_RATE // 100 * 2
        self.to_device = None
        self.on_mic = None

    # ------------------------------------------------------------ controls
    def start(self, on_mic):
        """Opens the default microphone and speakers; raises if they can't be opened."""
        import sounddevice
        from livekit import rtc

        self.on_mic = on_mic
        self.apm = rtc.AudioProcessingModule(echo_cancellation=True, noise_suppression=True, high_pass_filter=True, auto_gain_control=True)
        self.AudioFrame = rtc.AudioFrame
        last_error = None
        for rate in self.rates(sounddevice):
            try:
                self.open(sounddevice, rate)
                break
            except Exception as error:  # noqa: BLE001 - try the device's own rate next
                last_error = error
                self.close_streams()
        else:
            raise last_error or RuntimeError("No microphone")
        self.running = True
        self.worker = threading.Thread(target=self.work, name="live-audio", daemon=True)
        self.worker.start()
        for stream in self.streams:
            stream.start()

    @staticmethod
    def rates(sounddevice):
        rates = [DEVICE_RATE]
        try:
            native = int(sounddevice.query_devices(kind="input")["default_samplerate"])
            if native not in rates:
                rates.append(native)
        except Exception:  # noqa: BLE001 - no default device; the open below reports it
            pass
        return rates

    def open(self, sounddevice, rate):
        frames = rate // 100  # the echo canceller works in 10 ms frames
        self.rate = rate
        self.frame_bytes = frames * 2
        self.to_device = Resampler(MODEL_RATE, rate)
        self.to_model = Resampler(rate, MIC_RATE)
        self.sending = bytearray()
        self.counts = {"tutor": 0, "you": 0}
        self.streams = [
            sounddevice.RawInputStream(samplerate=rate, channels=1, dtype="int16", blocksize=frames, callback=self.heard, latency="low"),
            sounddevice.RawOutputStream(samplerate=rate, channels=1, dtype="int16", blocksize=frames, callback=self.speak, latency="low"),
        ]

    def set_muted(self, muted):
        self.muted = bool(muted)

    def play(self, data_b64):
        try:
            pcm = base64.b64decode(data_b64)
        except (ValueError, TypeError):
            return
        converted = self.to_device.convert(pcm) if self.to_device else b""
        with self.lock:
            self.playback.extend(converted)

    def clear(self):
        with self.lock:
            self.playback.clear()

    def stop(self):
        self.running = False
        self.close_streams()
        self.jobs.put(None)
        self.clear()

    def close_streams(self):
        streams, self.streams = self.streams, []
        for stream in streams:
            try:
                stream.stop()
                stream.close()
            except Exception:  # noqa: BLE001 - already closed
                pass

    # ------------------------------------------------- audio callbacks
    def heard(self, data, _frames, _time, _status):
        self.jobs.put(("mic", bytes(data)))

    def speak(self, out, _frames, _time, _status):
        size = len(out)
        with self.lock:
            chunk = bytes(self.playback[:size])
            del self.playback[:size]
        if len(chunk) < size:
            chunk += bytes(size - len(chunk))
        out[:] = chunk
        self.jobs.put(("speaker", chunk))

    # ------------------------------------------------------------ worker
    def work(self):
        while self.running:
            job = self.jobs.get()
            if job is None:
                return
            kind, data = job
            try:
                self.process(kind, data)
            except Exception:  # noqa: BLE001 - one bad frame mustn't end the conversation
                continue

    def latency_ms(self):
        total = 0.0
        for stream in self.streams:
            try:
                total += float(stream.latency)
            except Exception:  # noqa: BLE001
                pass
        return max(10, min(500, int(total * 1000)))

    def process(self, kind, data):
        if len(data) != self.frame_bytes:
            return
        frame = self.AudioFrame(bytearray(data), self.rate, 1, self.rate // 100)
        if kind == "speaker":
            self.apm.process_reverse_stream(frame)
            self.report("tutor", data)
            return
        self.apm.set_stream_delay_ms(self.latency_ms())
        self.apm.process_stream(frame)
        clean = bytes(frame.data.cast("B"))
        if self.muted:
            self.sending.clear()
            self.report("you", b"")
            return
        self.report("you", clean)
        self.sending.extend(self.to_model.convert(clean))
        if len(self.sending) >= int(MIC_RATE * SEND_SECONDS) * 2:
            chunk, self.sending = bytes(self.sending), bytearray()
            if self.on_mic:
                self.on_mic(base64.b64encode(chunk).decode("ascii"))

    def report(self, who, data):
        self.counts[who] += 1
        if self.counts[who] % LEVEL_EVERY == 0:
            self.on_level(who, level(data))
