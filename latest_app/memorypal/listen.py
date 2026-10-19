"""Offline speech recognition for talk-back study, with no extra packages.

Windows has a dictation recogniser built in (System.Speech.Recognition); it
is driven through PowerShell, like speech.py drives System.Speech for
reading aloud. Nothing the user typed or said is ever put on the command
line: the script only contains numbers this module formats itself, and the
recognised words come back on stdout. macOS and Linux have no recogniser
that works offline without installing something, so there talk-back study
reads aloud and takes typed answers instead.

The listener is non-blocking: start() launches the recogniser and poll()
returns None until it has finished, so a Tk app can check it from after().
"""

import re
import subprocess
import sys
from dataclasses import dataclass

from .core import normalize_space, powershell_exe

HEARD = "MP-HEARD"
SILENCE = "MP-SILENCE"
ERROR = "MP-ERROR"
RECOGNIZERS = "MP-RECOGNIZERS"

WINDOWS_LISTEN_SCRIPT = (
    "$ErrorActionPreference = 'Stop'; "
    "[Console]::OutputEncoding = [Text.Encoding]::UTF8; "
    "try {{ "
    "Add-Type -AssemblyName System.Speech; "
    "$engine = New-Object System.Speech.Recognition.SpeechRecognitionEngine; "
    "$engine.LoadGrammar((New-Object System.Speech.Recognition.DictationGrammar)); "
    "$engine.SetInputToDefaultAudioDevice(); "
    "$engine.InitialSilenceTimeout = [TimeSpan]::FromMilliseconds({initial_ms}); "
    "$engine.BabbleTimeout = [TimeSpan]::FromMilliseconds({max_ms}); "
    "$engine.EndSilenceTimeout = [TimeSpan]::FromMilliseconds({end_ms}); "
    "$engine.EndSilenceTimeoutAmbiguous = [TimeSpan]::FromMilliseconds({end_ms}); "
    "$heard = $engine.Recognize([TimeSpan]::FromMilliseconds({max_ms})); "
    "if ($heard -ne $null -and $heard.Text) {{ "
    "[Console]::Out.WriteLine('" + HEARD + " ' + $heard.Confidence.ToString('0.000', [Globalization.CultureInfo]::InvariantCulture) + ' ' + $heard.Text) "
    "}} else {{ [Console]::Out.WriteLine('" + SILENCE + "') }}; "
    "$engine.Dispose() "
    "}} catch {{ [Console]::Out.WriteLine('" + ERROR + " ' + $_.Exception.Message) }}"
)

WINDOWS_PROBE_SCRIPT = (
    "[Console]::OutputEncoding = [Text.Encoding]::UTF8; "
    "try { Add-Type -AssemblyName System.Speech; "
    "[Console]::Out.WriteLine('" + RECOGNIZERS + " ' + [System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers().Count) "
    "} catch { [Console]::Out.WriteLine('" + RECOGNIZERS + " 0') }"
)


@dataclass
class ListenResult:
    """What one listening turn produced.

    status is "heard" (text holds the words), "silence" (nothing was said in
    time), "error" (message says why, e.g. no microphone) or "unavailable"
    (no recogniser on this computer).
    """

    status: str
    text: str = ""
    confidence: float = 0.0
    message: str = ""

    @property
    def heard(self):
        return self.status == "heard" and bool(self.text)


def platform_supported(platform=None):
    """Whether this kind of computer has an offline recogniser we can drive."""
    return (platform or sys.platform).startswith("win")


def _ms(seconds):
    return int(round(max(0.1, float(seconds)) * 1000))


def listen_command(max_seconds=12, initial_silence=6, end_silence=1.2, platform=None):
    """The command that listens once and prints the result, or None off Windows."""
    if not platform_supported(platform):
        return None
    script = WINDOWS_LISTEN_SCRIPT.format(initial_ms=_ms(initial_silence), max_ms=_ms(max_seconds), end_ms=_ms(end_silence))
    return [powershell_exe(), "-NoProfile", "-NonInteractive", "-Command", script]


def probe_command(platform=None):
    """The command that prints how many recognisers are installed, or None."""
    if not platform_supported(platform):
        return None
    return [powershell_exe(), "-NoProfile", "-NonInteractive", "-Command", WINDOWS_PROBE_SCRIPT]


def parse_result(stdout, returncode=0):
    """Read the recogniser's stdout into a ListenResult."""
    lines = [line.strip() for line in (stdout or "").splitlines() if line.strip()]
    for line in reversed(lines):
        if line.startswith(HEARD):
            rest = line[len(HEARD):].strip()
            confidence_text, _, text = rest.partition(" ")
            try:
                confidence = float(confidence_text)
            except ValueError:
                confidence, text = 0.0, rest
            text = normalize_space(text)
            return ListenResult("heard", text, confidence) if text else ListenResult("silence")
        if line.startswith(SILENCE):
            return ListenResult("silence")
        if line.startswith(ERROR):
            return ListenResult("error", message=normalize_space(line[len(ERROR):]) or "Speech recognition failed.")
    if returncode:
        return ListenResult("error", message=f"Speech recognition stopped unexpectedly (code {returncode}).")
    return ListenResult("silence")


def parse_probe(stdout):
    """How many recognisers the probe reported (0 if it could not tell)."""
    match = re.search(RECOGNIZERS + r"\s+(\d+)", stdout or "")
    return int(match.group(1)) if match else 0


SPOKEN_COMMANDS = {
    "repeat": ("repeat", "say again", "say that again", "again please", "repeat that", "pardon", "what was that"),
    "skip": ("skip", "next", "next question", "skip it", "pass"),
    "pause": ("pause", "stop", "wait", "hold on", "stop listening"),
    "dont_know": ("i don't know", "i do not know", "don't know", "no idea", "not sure", "i forget", "i forgot", "tell me"),
}


def spoken_command(text):
    """'repeat', 'skip', 'pause' or 'dont_know' when the words are a command, else None.

    Only a whole short utterance counts ("skip", "say that again"), so an
    answer that merely contains the word "next" is still an answer.
    """
    words = re.sub(r"[^\w' ]+", " ", (text or "").lower().replace("’", "'"))
    words = " ".join(words.split())
    if not words or len(words.split()) > 5:
        return None
    for command, phrases in SPOKEN_COMMANDS.items():
        if words in phrases or any(words == f"{phrase} please" for phrase in phrases):
            return command
    return None


class Listener:
    """Runs one listening turn at a time in the background."""

    def __init__(self, popen=subprocess.Popen, platform=None):
        self._popen = popen
        self.platform = platform or sys.platform
        self.process = None
        self._recognizers = None

    def supported(self):
        return platform_supported(self.platform)

    def _run(self, command):
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        return self._popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
        )

    def probe(self, timeout=20):
        """Whether a recogniser is installed (cached). Blocks: call it off the UI thread."""
        if self._recognizers is not None:
            return self._recognizers > 0
        command = probe_command(self.platform)
        if command is None:
            self._recognizers = 0
            return False
        try:
            process = self._run(command)
            stdout, _ = process.communicate(timeout=timeout)
        except (OSError, subprocess.SubprocessError):
            self._recognizers = 0
            return False
        self._recognizers = parse_probe(stdout.decode("utf-8", "replace") if isinstance(stdout, bytes) else stdout)
        return self._recognizers > 0

    def start(self, max_seconds=12, initial_silence=6, end_silence=1.2):
        """Start listening. Returns False when there is no recogniser to run."""
        self.stop()
        command = listen_command(max_seconds, initial_silence, end_silence, self.platform)
        if command is None:
            return False
        try:
            self.process = self._run(command)
        except OSError:
            self.process = None
            return False
        return True

    def listening(self):
        return self.process is not None and self.process.poll() is None

    def poll(self):
        """None while still listening; then the ListenResult (once)."""
        if self.process is None:
            return ListenResult("unavailable", message="Not listening.")
        returncode = self.process.poll()
        if returncode is None:
            return None
        process, self.process = self.process, None
        try:
            stdout = process.stdout.read() if process.stdout else b""
        except (OSError, ValueError):
            stdout = b""
        text = stdout.decode("utf-8", "replace") if isinstance(stdout, bytes) else (stdout or "")
        return parse_result(text, returncode)

    def stop(self):
        if self.process is not None and self.process.poll() is None:
            try:
                self.process.terminate()
            except OSError:
                pass
        self.process = None
