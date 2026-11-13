"""Live Talk-back: a spoken study conversation with Gemini Live.

Like a voice call with a tutor: the tutor asks the cards, listens, can be
interrupted mid-sentence, explains, and saves a result for each card through
a tool call (record_answer), so ratings land in the schedule like any review.
The phone has the same flow in mobile/src/features/liveTutor.ts.

This is the protocol and the timing only. The WebSocket and the audio are
passed in, so the flow can be tested without a network or a microphone. The
"ai" Edge Function hands out the one-use token and the set-up (ai.start_live,
supabase/functions/ai/live.ts); the audio goes straight to Google.

Threads: the socket is read on a worker thread, and the Tk page calls tick()
from after() a few times a second. tick() runs the clock and hands back the
ratings to save (take_ratings), so the store is only touched on the UI thread.
"""

import json
import re
import threading
import time
import urllib.parse
from dataclasses import dataclass, field

# Ephemeral (one-use) tokens only work on the v1alpha Live endpoint, as in Google's SDK.
LIVE_URL = "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContentConstrained"
MIC_RATE = 16000
MODEL_RATE = 24000
START_LINE = "(The learner pressed Start and is listening. Greet them in one short line and ask the first card.)"
LAST_MINUTE_LINE = "(About one minute is left. After the current card, give the short summary, say goodbye and call end_session.)"
OUTCOMES = ("right", "close", "wrong", "skipped")


def live_assessment(outcome):
    """The schedule rating for a tutor's verdict, as answer_assessment() shapes it; None for skipped."""
    detail = "Judged by the live AI tutor."
    if outcome == "right":
        return {"score": 80, "quality": 4, "label": "Right (AI tutor)", "bucket": "Good", "repetitions": 2, "detail": detail}
    if outcome == "close":
        return {"score": 50, "quality": 3, "label": "Nearly (AI tutor)", "bucket": "Review", "repetitions": 3, "detail": detail}
    if outcome == "wrong":
        return {"score": 10, "quality": 1, "label": "Not yet (AI tutor)", "bucket": "Again", "repetitions": 5, "detail": detail}
    return None


def close_text(code=None, reason=""):
    """Friendly text for a socket that closed before the conversation ended."""
    why = (reason or "").lower()
    if code == 1008 or "quota" in why or "resource" in why:
        return "The AI tutor is busy right now. Try again in a minute, or use classic Talk-back."
    if "token" in why or "auth" in why or "expired" in why:
        return "The conversation couldn't be started. Try again."
    return "The connection to the AI tutor dropped. Your answers so far are saved."


def pcm_seconds(data_b64, rate):
    """How long base64 16-bit mono PCM plays for."""
    data = data_b64.rstrip("=")
    return (len(data) * 3 // 4) / 2 / rate


def tidy(text):
    return re.sub(r"\s+", " ", text)


@dataclass
class LiveResult:
    key: str
    card: object
    outcome: str
    said: str = ""


@dataclass
class Snapshot:
    phase: str  # connecting, live, done, error
    speaking: str  # "tutor", "you" or ""
    tutor_line: str
    you_line: str
    muted: bool
    results: list = field(default_factory=list)
    total: int = 0
    seconds_left: int = 0
    error: str = ""


class LiveTutor:
    """One conversation. open_socket(url) returns an object with send(text),
    recv() (blocks; returns text or bytes, raises when the socket closes) and
    close(); audio is a liveaudio.LiveAudio (start(on_mic), set_muted, play,
    clear, stop)."""

    def __init__(self, token, setup, cards, minutes, open_socket, audio, now=time.monotonic, threaded=True):
        self.token = token
        self.setup = setup
        self.cards = dict(cards)
        self.minutes = minutes
        self.open_socket = open_socket
        self.audio = audio
        self.now = now
        self.threaded = threaded
        self.lock = threading.RLock()
        self.phase = "connecting"
        self.socket = None
        self.speech_until = 0.0
        self.started_at = 0.0
        self.end_at = None
        self.warned = False
        self.ending = False
        self.tutor_line = ""
        self.you_line = ""
        self.tutor_turn_open = False
        self.you_fresh = True
        self.you_heard_at = -10.0
        self.muted = False
        self.results = []
        self.pending = []
        self.error = ""

    # ------------------------------------------------------------ controls
    def start(self):
        url = f"{LIVE_URL}?access_token={urllib.parse.quote(self.token, safe='')}"
        if self.threaded:
            threading.Thread(target=self._run, args=(url,), name="live-tutor", daemon=True).start()
        else:
            self._connect(url)

    def _connect(self, url):
        try:
            socket = self.open_socket(url)
        except Exception:  # noqa: BLE001 - any failure to connect reads the same to people
            self.fail("The AI tutor couldn't be reached. Check the internet connection.")
            return None
        with self.lock:
            if self.phase != "connecting":
                self._close(socket)
                return None
            self.socket = socket
        self.send({"setup": self.setup})
        return socket

    def _run(self, url):
        socket = self._connect(url)
        while socket is not None and self.socket is socket:
            try:
                data = socket.recv()
            except Exception as error:  # noqa: BLE001 - the socket closed
                self.closed(socket, getattr(getattr(error, "rcvd", None), "code", None), getattr(getattr(error, "rcvd", None), "reason", "") or "")
                return
            self.receive(data)

    def set_muted(self, muted):
        with self.lock:
            if self.phase != "live" or muted == self.muted:
                return
            self.muted = muted
        self.audio.set_muted(muted)
        # Tells the voice detector the speaker went quiet, so a half-said answer is still heard.
        if muted:
            self.send({"realtimeInput": {"audioStreamEnd": True}})

    def stop(self):
        """Ends now (the End button, leaving the page). Saved ratings stay."""
        if self.phase not in ("done", "error"):
            self.finish()

    def tick(self):
        """The clock: a wrap-up a minute before the end, then hang up. Call it a few times a second."""
        if self.phase != "live":
            return
        if self.end_at is not None and self.now() >= self.end_at:
            self.finish()
            return
        left = self.seconds_left()
        if left <= 60 and not self.warned:
            self.wrap_up(LAST_MINUTE_LINE)
        if left <= 0:
            self.finish()

    def take_ratings(self):
        """[(card, outcome)] saved by the tutor since the last call, to schedule on the UI thread."""
        with self.lock:
            ready, self.pending = self.pending, []
        return ready

    # ------------------------------------------------------------- incoming
    def closed(self, socket=None, code=None, reason=""):
        with self.lock:
            if socket is not None and self.socket is not socket:
                return
            self.socket = None
            if self.phase in ("done", "error"):
                return
            ending, connecting = self.ending, self.phase == "connecting"
        if ending:
            self.finish()
        else:
            self.fail(close_text(code, reason or "start") if connecting else close_text(code, reason))

    def receive(self, data):
        try:
            message = json.loads(bytes(data).decode("utf-8") if isinstance(data, (bytes, bytearray, memoryview)) else str(data))
        except (ValueError, UnicodeDecodeError):
            return
        if not isinstance(message, dict):
            return
        if "setupComplete" in message:
            self.begin()
        if isinstance(message.get("serverContent"), dict):
            self.content(message["serverContent"])
        if isinstance(message.get("toolCall"), dict):
            self.tool_call(message["toolCall"])
        if "goAway" in message:
            self.wrap_up(LAST_MINUTE_LINE)

    def begin(self):
        with self.lock:
            if self.phase != "connecting":
                return
            self.phase = "live"
            self.started_at = self.now()
        self.send({"clientContent": {"turns": [{"role": "user", "parts": [{"text": START_LINE}]}], "turnComplete": True}})
        try:
            self.audio.start(self.mic)
        except Exception:  # noqa: BLE001 - no microphone, no permission, a busy device
            self.fail("The microphone couldn't be started. Check that MemoryPal may use it in your computer's privacy settings.")

    def mic(self, data_b64):
        if self.phase == "live" and not self.muted:
            self.send({"realtimeInput": {"audio": {"data": data_b64, "mimeType": f"audio/pcm;rate={MIC_RATE}"}}})

    def content(self, content):
        if self.phase != "live":
            return
        clear = False
        with self.lock:
            heard = (content.get("inputTranscription") or {}).get("text") if isinstance(content.get("inputTranscription"), dict) else None
            if isinstance(heard, str) and heard:
                # The learner's first words after the tutor spoke start a fresh line.
                if self.you_fresh:
                    self.you_fresh = False
                    self.you_line = ""
                self.you_line = tidy(self.you_line + heard).lstrip()
                self.you_heard_at = self.now()
            turn = content.get("modelTurn") if isinstance(content.get("modelTurn"), dict) else {}
            for part in turn.get("parts") or []:
                audio = ((part or {}).get("inlineData") or {}).get("data") if isinstance(part, dict) else None
                if isinstance(audio, str) and audio:
                    self.open_tutor_turn()
                    self.audio.play(audio)
                    self.speech_until = max(self.speech_until, self.now()) + pcm_seconds(audio, MODEL_RATE)
            said = (content.get("outputTranscription") or {}).get("text") if isinstance(content.get("outputTranscription"), dict) else None
            if isinstance(said, str) and said:
                self.open_tutor_turn()
                self.tutor_line = tidy(self.tutor_line + said).lstrip()
            if content.get("interrupted"):
                # The learner spoke over the tutor: drop what hasn't been played.
                clear = True
                self.speech_until = min(self.speech_until, self.now())
            if content.get("turnComplete") or content.get("interrupted"):
                self.tutor_turn_open = False
        if clear:
            self.audio.clear()

    def open_tutor_turn(self):
        if self.tutor_turn_open:
            return
        self.tutor_turn_open = True
        self.you_fresh = True
        self.tutor_line = ""

    def tool_call(self, call):
        responses = []
        for fn in call.get("functionCalls") or []:
            fn = fn if isinstance(fn, dict) else {}
            name = str(fn.get("name") or "")
            response = {"result": "unknown tool"}
            if name == "record_answer":
                response = self.record(fn.get("args") if isinstance(fn.get("args"), dict) else {})
            elif name == "end_session":
                response = {"result": "ok"}
                self.end_after_speech()
            responses.append({"id": fn.get("id"), "name": name, "response": {**response, "scheduling": "SILENT"}})
        if responses:
            self.send({"toolResponse": {"functionResponses": responses}})

    def record(self, args):
        key = str(args.get("card") or "").strip()
        outcome = str(args.get("result") or "").strip().lower()
        card = self.cards.get(key)
        if card is None or outcome not in OUTCOMES:
            return {"result": "error: unknown card key or result"}
        said = tidy(args["said"]).strip()[:200] if isinstance(args.get("said"), str) else ""
        result = LiveResult(key, card, outcome, said)
        with self.lock:
            # A card the tutor comes back to keeps its latest result, and is rated once.
            for index, item in enumerate(self.results):
                if item.key == key:
                    self.results[index] = result
                    break
            else:
                self.results.append(result)
                if outcome != "skipped":
                    self.pending.append((card, outcome))
        return {"result": "saved"}

    # -------------------------------------------------------------- timing
    def seconds_left(self):
        if not self.started_at:
            return int(self.minutes * 60)
        return max(0, round(self.minutes * 60 - (self.now() - self.started_at)))

    def wrap_up(self, line):
        with self.lock:
            if self.warned or self.phase != "live":
                return
            self.warned = True
        # Not a turn of its own: the tutor reads it with the learner's next words.
        self.send({"clientContent": {"turns": [{"role": "user", "parts": [{"text": line}]}], "turnComplete": False}})

    def end_after_speech(self):
        with self.lock:
            self.ending = True
            # Let the goodbye finish playing first.
            self.end_at = max(self.speech_until, self.now()) + 0.6

    # ------------------------------------------------------------- endings
    def finish(self):
        with self.lock:
            if self.phase in ("done", "error"):
                return
            self.phase = "done"
        self.teardown()

    def fail(self, error):
        with self.lock:
            if self.phase in ("done", "error"):
                return
            self.phase = "error"
            self.error = error
        self.teardown()

    def teardown(self):
        try:
            self.audio.stop()
        except Exception:  # noqa: BLE001 - already stopped
            pass
        with self.lock:
            socket, self.socket = self.socket, None
        self._close(socket)

    @staticmethod
    def _close(socket):
        if socket is None:
            return
        try:
            socket.close()
        except Exception:  # noqa: BLE001 - already closed
            pass

    def send(self, message):
        socket = self.socket
        if socket is None:
            return
        try:
            socket.send(json.dumps(message))
        except Exception:  # noqa: BLE001 - a closing socket; the reader reports it
            pass

    # ------------------------------------------------------------- reading
    def snapshot(self):
        with self.lock:
            now = self.now()
            tutor = self.phase == "live" and self.speech_until > now
            you = self.phase == "live" and not tutor and now - self.you_heard_at < 1.2
            return Snapshot(
                phase=self.phase,
                speaking="tutor" if tutor else "you" if you else "",
                tutor_line=self.tutor_line,
                you_line=self.you_line,
                muted=self.muted,
                results=list(self.results),
                total=len(self.cards),
                seconds_left=self.seconds_left(),
                error=self.error,
            )


def open_websocket(url):
    """A Live API socket using the `websockets` package (sync client)."""
    from websockets.sync.client import connect

    return connect(url, open_timeout=20, close_timeout=2, max_size=None, compression=None)
