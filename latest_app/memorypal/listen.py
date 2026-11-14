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

import base64
import re
import subprocess
import sys
import threading
from dataclasses import dataclass

from .core import normalize_space, powershell_exe

HEARD = "MP-HEARD"
SILENCE = "MP-SILENCE"
ERROR = "MP-ERROR"
RECOGNIZERS = "MP-RECOGNIZERS"

READY = "MP-READY"
LISTENING = "MP-LISTENING"
ALTERNATE = "MP-ALT"

# The recogniser is started early (while the question is still being read
# aloud) so that it is loaded and waiting by the time the answer starts: a
# cold start takes a second or two, and words said in that gap were lost.
# It reads its hints from stdin, loads, prints READY, then waits for GO.
#
# Hints are the answers of the cards in this round. Plain dictation knows
# nothing about the subject, so it mishears names and technical words; with
# the round's own answers loaded as phrases it can recognise them directly.
WINDOWS_LISTEN_SCRIPT = " ".join(line.strip() for line in ("""
$ErrorActionPreference = 'Stop';
[Console]::OutputEncoding = [Text.Encoding]::UTF8;
function Tell($text) { [Console]::Out.WriteLine($text); [Console]::Out.Flush() };
function Unpack($line) { [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($line.Substring(2))) };
try {
$phrases = New-Object 'System.Collections.Generic.List[string]';
$wave = '';
while ($true) {
$line = [Console]::In.ReadLine();
if ($line -eq $null -or $line -eq 'END') { break };
if ($line.StartsWith('H ')) { $phrases.Add((Unpack $line)) }
elseif ($line.StartsWith('W ')) { $wave = (Unpack $line) }
};
Add-Type -AssemblyName System.Speech;
$engine = New-Object System.Speech.Recognition.SpeechRecognitionEngine;
$engine.LoadGrammar((New-Object System.Speech.Recognition.DictationGrammar));
if ($phrases.Count -gt 0) {
try {
$choices = New-Object System.Speech.Recognition.Choices;
foreach ($phrase in $phrases) { $choices.Add([string[]]@($phrase)) };
$builder = New-Object System.Speech.Recognition.GrammarBuilder;
$builder.Culture = $engine.RecognizerInfo.Culture;
$builder.Append($choices);
$known = New-Object System.Speech.Recognition.Grammar($builder);
$known.Name = 'known';
$known.Priority = 20;
$engine.LoadGrammar($known)
} catch { }
};
if ($wave) { $engine.SetInputToWaveFile($wave) } else { $engine.SetInputToDefaultAudioDevice() };
$engine.InitialSilenceTimeout = [TimeSpan]::FromMilliseconds({initial_ms});
$engine.BabbleTimeout = [TimeSpan]::FromMilliseconds({max_ms});
$engine.EndSilenceTimeout = [TimeSpan]::FromMilliseconds({end_ms});
$engine.EndSilenceTimeoutAmbiguous = [TimeSpan]::FromMilliseconds({end_ms});
$engine.MaxAlternates = 5;
Tell '""" + READY + """';
if ([Console]::In.ReadLine() -ne 'GO') { $engine.Dispose(); exit };
Tell '""" + LISTENING + """';
$heard = $engine.Recognize([TimeSpan]::FromMilliseconds({max_ms}));
if ($heard -ne $null -and $heard.Text) {
foreach ($other in $heard.Alternates) { if ($other.Text -and $other.Text -ne $heard.Text) { Tell ('""" + ALTERNATE + """ ' + $other.Text) } };
Tell ('""" + HEARD + """ ' + $heard.Confidence.ToString('0.000', [Globalization.CultureInfo]::InvariantCulture) + ' ' + $heard.Text)
} else { Tell '""" + SILENCE + """' };
$engine.Dispose()
} catch { Tell ('""" + ERROR + """ ' + $_.Exception.Message) }
""").strip().splitlines())

MAX_HINTS = 150
MAX_HINT_WORDS = 12

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
    alternates: tuple = ()

    def readings(self):
        """What was heard, then the recogniser's other guesses at the same words."""
        return [self.text, *self.alternates] if self.text else []

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
    script = WINDOWS_LISTEN_SCRIPT
    for name, seconds in (("initial_ms", initial_silence), ("max_ms", max_seconds), ("end_ms", end_silence)):
        script = script.replace("{" + name + "}", str(_ms(seconds)))
    return [powershell_exe(), "-NoProfile", "-NonInteractive", "-Command", script]


def clean_hints(phrases):
    """Phrases the recogniser can take: plain words only, short, no repeats."""
    cleaned, seen = [], set()
    for phrase in phrases or ():
        words = re.sub(r"[^\w' -]+", " ", str(phrase or "").replace("’", "'").replace("_", " "))
        words = " ".join(words.split())
        key = words.casefold()
        if not words or key in seen or len(words.split()) > MAX_HINT_WORDS or not re.search(r"[^\W\d]", words):
            continue
        seen.add(key)
        cleaned.append(words)
        if len(cleaned) >= MAX_HINTS:
            break
    return cleaned


def _packed(kind, text):
    return f"{kind} {base64.b64encode(text.encode('utf-8')).decode('ascii')}\n".encode("ascii")


def setup_lines(hints=(), wave_file=None):
    """What the recogniser reads before it loads. Base64, so no text can break out of a line."""
    lines = [_packed("H", hint) for hint in clean_hints(hints)]
    if wave_file:
        lines.append(_packed("W", str(wave_file)))
    lines.append(b"END\n")
    return b"".join(lines)


def probe_command(platform=None):
    """The command that prints how many recognisers are installed, or None."""
    if not platform_supported(platform):
        return None
    return [powershell_exe(), "-NoProfile", "-NonInteractive", "-Command", WINDOWS_PROBE_SCRIPT]


def parse_result(stdout, returncode=0):
    """Read the recogniser's stdout into a ListenResult."""
    lines = [line.strip() for line in (stdout or "").splitlines() if line.strip()]
    alternates = tuple(text for text in (normalize_space(line[len(ALTERNATE):]) for line in lines if line.startswith(ALTERNATE)) if text)
    for line in reversed(lines):
        if line.startswith(HEARD):
            rest = line[len(HEARD):].strip()
            confidence_text, _, text = rest.partition(" ")
            try:
                confidence = float(confidence_text)
            except ValueError:
                confidence, text = 0.0, rest
            text = normalize_space(text)
            return ListenResult("heard", text, confidence, alternates=alternates) if text else ListenResult("silence")
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
        self._going = False
        self._lines = []
        self._reader = None

    def supported(self):
        return platform_supported(self.platform)

    def _run(self, command, stdin=subprocess.DEVNULL):
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        return self._popen(
            command,
            stdin=stdin,
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

    def prepare(self, hints=(), max_seconds=12, initial_silence=6, end_silence=1.2, wave_file=None):
        """Load the recogniser now so it is waiting when go() is called.

        hints are phrases likely to be said (the round's answers). Returns
        False when there is no recogniser to run.
        """
        self.stop()
        command = listen_command(max_seconds, initial_silence, end_silence, self.platform)
        if command is None:
            return False
        try:
            process = self._run(command, stdin=subprocess.PIPE)
            process.stdin.write(setup_lines(hints, wave_file))
            process.stdin.flush()
        except (OSError, ValueError):
            return False
        self.process = process
        self._going = False
        self._lines = lines = []
        self._reader = threading.Thread(target=self._read, args=(process, lines), daemon=True)
        self._reader.start()
        return True

    @staticmethod
    def _read(process, lines):
        try:
            for raw in process.stdout:
                lines.append(raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw)
        except (OSError, ValueError):
            pass

    def prepared(self):
        """A recogniser is loaded (or loading) and has not been told to listen yet."""
        return self.process is not None and not self._going and self.process.poll() is None

    def go(self):
        """Open the microphone on the prepared recogniser."""
        if not self.prepared():
            return False
        try:
            self.process.stdin.write(b"GO\n")
            self.process.stdin.flush()
            self.process.stdin.close()
        except (OSError, ValueError):
            self.stop()
            return False
        self._going = True
        return True

    def start(self, hints=(), max_seconds=12, initial_silence=6, end_silence=1.2, wave_file=None):
        """Start listening. Returns False when there is no recogniser to run."""
        if not self.prepared() and not self.prepare(hints, max_seconds, initial_silence, end_silence, wave_file):
            return False
        return self.go()

    def microphone_open(self):
        """True once the recogniser has actually started to listen."""
        return self.process is not None and any(line.startswith(LISTENING) for line in list(self._lines))

    def listening(self):
        return self.process is not None and self.process.poll() is None

    def poll(self):
        """None while still listening; then the ListenResult (once)."""
        if self.process is None:
            return ListenResult("unavailable", message="Not listening.")
        returncode = self.process.poll()
        if returncode is None:
            return None
        self.process = None
        if self._reader is not None:
            self._reader.join(timeout=2)
        return parse_result("".join(self._lines), returncode)

    def stop(self):
        process, self.process = self.process, None
        if process is not None and process.poll() is None:
            try:
                process.terminate()
            except OSError:
                pass
