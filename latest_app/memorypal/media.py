"""Recording, playback, previews and speech files using what Windows already has.

Nothing here needs extra packages: audio recording prefers `sounddevice`
when it is installed and otherwise uses the Windows MCI recorder; playback
uses MCI (MP3, WAV, WMA, and M4A where Windows has the codec); image
previews are decoded by Windows Imaging (JPEG, PNG, GIF, BMP, TIFF, WebP,
HEIC with the extension) and resized to a PNG that Tk can show; spoken cues
are written by the built-in System.Speech voice.
"""

import array
import ctypes
import hashlib
import importlib
import os
import subprocess
import sys
import threading
import time
import wave
from pathlib import Path

IS_WINDOWS = sys.platform.startswith("win")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

AUDIO_TYPES = (".mp3", ".wav", ".m4a", ".ogg", ".webm", ".aac", ".wma", ".flac")
VIDEO_TYPES = (".mp4", ".mov", ".avi", ".mkv", ".webm", ".wmv", ".m4v")
IMAGE_TYPES = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tif", ".tiff", ".heic")
TEXT_TYPES = (".txt", ".md", ".csv", ".pdf", ".docx", ".doc", ".rtf")

FILETYPES = {
    "text_file": [("Notes and documents", " ".join(f"*{ext}" for ext in TEXT_TYPES)), ("PDF", "*.pdf"), ("Word documents", "*.docx *.doc"), ("Plain text", "*.txt *.md *.csv")],
    "image": [("Images", " ".join(f"*{ext}" for ext in IMAGE_TYPES))],
    "audio": [("Audio", " ".join(f"*{ext}" for ext in AUDIO_TYPES))],
    "video": [("Video", " ".join(f"*{ext}" for ext in VIDEO_TYPES))],
}


def run_powershell(script, timeout=60, stdin_text=None):
    """Run a PowerShell script (passed on stdin-free -Command) and return (ok, stdout)."""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
            input=stdin_text.encode("utf-8") if stdin_text is not None else None,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, creationflags=NO_WINDOW,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    output = result.stdout.decode("utf-8", "ignore").strip()
    if result.returncode != 0:
        return False, (result.stderr.decode("utf-8", "ignore").strip() or output)
    return True, output


def ps_quote(value):
    return "'" + str(value).replace("'", "''") + "'"


# ----------------------------------------------------------------------------
# MCI (winmm) helpers
# ----------------------------------------------------------------------------
def mci(command):
    """Send an MCI command; returns (ok, reply or error text)."""
    if not IS_WINDOWS:
        return False, "MCI is only available on Windows."
    winmm = ctypes.windll.winmm
    buffer = ctypes.create_unicode_buffer(512)
    error = winmm.mciSendStringW(command, buffer, 511, 0)
    if error:
        message = ctypes.create_unicode_buffer(512)
        winmm.mciGetErrorStringW(error, message, 511)
        return False, message.value or f"MCI error {error}"
    return True, buffer.value


class AudioPlayer:
    """Plays one sound at a time inside the app (MCI), so there is a Stop button."""

    ALIAS = "memorypal_player"

    def __init__(self):
        self.path = None

    def play(self, path):
        self.stop()
        path = str(path)
        if not IS_WINDOWS or not Path(path).exists():
            return False
        kind = "waveaudio" if path.lower().endswith(".wav") else "mpegvideo"
        ok, _ = mci(f'open "{path}" type {kind} alias {self.ALIAS}')
        if not ok and kind == "waveaudio":
            ok, _ = mci(f'open "{path}" type mpegvideo alias {self.ALIAS}')
        if not ok:
            return False
        ok, _ = mci(f"play {self.ALIAS}")
        if ok:
            self.path = path
        else:
            mci(f"close {self.ALIAS}")
        return ok

    def is_playing(self):
        if not self.path:
            return False
        ok, mode = mci(f"status {self.ALIAS} mode")
        if not ok or mode not in ("playing", "seeking"):
            self.stop()
            return False
        return True

    def stop(self):
        if self.path:
            mci(f"stop {self.ALIAS}")
            mci(f"close {self.ALIAS}")
        self.path = None


# ----------------------------------------------------------------------------
# Audio recording
# ----------------------------------------------------------------------------
class AudioRecorder:
    """Record from the default microphone without blocking the window.

    Call start(), poll elapsed()/level() for the on-screen meter, then
    stop(path) to write a WAV file, or cancel().
    """

    RATE = 44100
    MCI_ALIAS = "memorypal_recorder"

    def __init__(self):
        self.backend = None
        self.stream = None
        self.frames = []
        self.peak = 0.0
        self.started = 0.0
        self.lock = threading.Lock()

    def start(self):
        """Begin recording. Returns (ok, message)."""
        try:
            sounddevice = importlib.import_module("sounddevice")
        except Exception:
            sounddevice = None
        if sounddevice is not None:
            try:
                def callback(indata, _frames, _time, _status):
                    chunk = bytes(indata)
                    samples = array.array("h", chunk)
                    with self.lock:
                        self.frames.append(chunk)
                        self.peak = max(abs(value) for value in samples) / 32768 if samples else 0.0

                self.stream = sounddevice.RawInputStream(samplerate=self.RATE, channels=1, dtype="int16", callback=callback)
                self.stream.start()
                self.backend = "sounddevice"
                self.started = time.monotonic()
                return True, "Recording"
            except Exception as exc:
                self.stream = None
                fallback_reason = str(exc)
        else:
            fallback_reason = "sounddevice is not installed"
        ok, message = mci(f"open new type waveaudio alias {self.MCI_ALIAS}")
        if ok:
            mci(f"set {self.MCI_ALIAS} bitspersample 16 channels 1 samplespersec {self.RATE}")
            ok, message = mci(f"record {self.MCI_ALIAS}")
        if not ok:
            mci(f"close {self.MCI_ALIAS}")
            return False, f"No microphone could be opened ({fallback_reason}; {message})."
        self.backend = "mci"
        self.started = time.monotonic()
        return True, "Recording"

    def elapsed(self):
        return time.monotonic() - self.started if self.backend else 0.0

    def level(self):
        """Loudness 0..1 of the latest sound (0 when the backend can't tell)."""
        with self.lock:
            return self.peak

    def stop(self, path):
        """Finish and save to `path` (WAV). Returns (ok, message)."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        backend, self.backend = self.backend, None
        if backend == "sounddevice":
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None
            with self.lock:
                data = b"".join(self.frames)
                self.frames = []
            if not data:
                return False, "No sound was captured. Check that the microphone is on and allowed in Windows privacy settings."
            with wave.open(str(path), "wb") as handle:
                handle.setnchannels(1)
                handle.setsampwidth(2)
                handle.setframerate(self.RATE)
                handle.writeframes(data)
            return True, str(path)
        if backend == "mci":
            mci(f"stop {self.MCI_ALIAS}")
            ok, message = mci(f'save {self.MCI_ALIAS} "{path}"')
            mci(f"close {self.MCI_ALIAS}")
            if not ok or not path.exists():
                return False, f"The recording could not be saved ({message})."
            return True, str(path)
        return False, "Nothing is being recorded."

    def cancel(self):
        backend, self.backend = self.backend, None
        if backend == "sounddevice" and self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None
            self.frames = []
        elif backend == "mci":
            mci(f"stop {self.MCI_ALIAS}")
            mci(f"close {self.MCI_ALIAS}")


def wav_duration(path):
    try:
        with wave.open(str(path), "rb") as handle:
            return handle.getnframes() / float(handle.getframerate() or 1)
    except (wave.Error, OSError, EOFError):
        return 0.0


# ----------------------------------------------------------------------------
# Image previews
# ----------------------------------------------------------------------------
PREVIEW_SCRIPT = r"""
Add-Type -AssemblyName PresentationCore
$src = {src}; $dst = {dst}; $maxW = {w}; $maxH = {h}
$stream = [IO.File]::OpenRead($src)
try {{
  $decoder = [System.Windows.Media.Imaging.BitmapDecoder]::Create($stream, 'IgnoreColorProfile', 'OnLoad')
  $frame = $decoder.Frames[0]
  $scale = [Math]::Min(1.0, [Math]::Min($maxW / $frame.PixelWidth, $maxH / $frame.PixelHeight))
  $bitmap = $frame
  if ($scale -lt 1.0) {{
    $bitmap = New-Object System.Windows.Media.Imaging.TransformedBitmap($frame, (New-Object System.Windows.Media.ScaleTransform($scale, $scale)))
  }}
  $encoder = New-Object System.Windows.Media.Imaging.PngBitmapEncoder
  $encoder.Frames.Add([System.Windows.Media.Imaging.BitmapFrame]::Create($bitmap))
  $out = [IO.File]::Create($dst)
  try {{ $encoder.Save($out) }} finally {{ $out.Close() }}
}} finally {{ $stream.Close() }}
"""


def preview_path(source, cache_dir, max_width, max_height):
    source = Path(source)
    try:
        stamp = f"{source.resolve()}|{source.stat().st_mtime_ns}|{max_width}x{max_height}"
    except OSError:
        return None
    digest = hashlib.sha1(stamp.encode("utf-8", "ignore")).hexdigest()[:16]
    return Path(cache_dir) / f"{source.stem[:40]}-{digest}.png"


def image_preview(source, cache_dir, max_width, max_height):
    """A PNG no bigger than max_width x max_height for any image Windows can read.

    Cached next to the attachments, so each image is only converted once.
    Returns the PNG path, or None if the image can't be read.
    """
    source = Path(source)
    if not source.exists():
        return None
    target = preview_path(source, cache_dir, max_width, max_height)
    if target is None:
        return None
    if target.exists() and target.stat().st_size > 0:
        return target
    if not IS_WINDOWS:
        return source if source.suffix.lower() in (".png", ".gif") else None
    target.parent.mkdir(parents=True, exist_ok=True)
    ok, _output = run_powershell(PREVIEW_SCRIPT.format(src=ps_quote(source), dst=ps_quote(target), w=int(max_width), h=int(max_height)))
    if ok and target.exists() and target.stat().st_size > 0:
        return target
    try:
        target.unlink()
    except OSError:
        pass
    return None


# ----------------------------------------------------------------------------
# Spoken cues
# ----------------------------------------------------------------------------
TTS_SCRIPT = (
    "[Console]::InputEncoding = [Text.Encoding]::UTF8; "
    "Add-Type -AssemblyName System.Speech; "
    "$voice = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
    "$voice.Rate = -1; "
    "$voice.SetOutputToWaveFile({dst}); "
    "$voice.Speak([Console]::In.ReadToEnd()); "
    "$voice.Dispose()"
)


def speech_to_wav(text, target):
    """Write `text` as spoken audio to a WAV file with the Windows voice."""
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if IS_WINDOWS:
        ok, message = run_powershell(TTS_SCRIPT.format(dst=ps_quote(target)), timeout=120, stdin_text=text)
        if ok and target.exists() and target.stat().st_size > 44:
            return True, str(target)
        return False, message or "The Windows voice could not create the file."
    try:
        pyttsx3 = importlib.import_module("pyttsx3")
        engine = pyttsx3.init()
        engine.save_to_file(text, str(target))
        engine.runAndWait()
        return target.exists(), str(target)
    except Exception as exc:
        return False, str(exc)


# ----------------------------------------------------------------------------
# Video via the Windows Camera app
# ----------------------------------------------------------------------------
def camera_folders():
    home = Path(os.environ.get("USERPROFILE") or Path.home())
    candidates = [home / "Pictures" / "Camera Roll", home / "OneDrive" / "Pictures" / "Camera Roll", home / "Videos" / "Captures", home / "Videos"]
    return [folder for folder in candidates if folder.is_dir()]


def open_camera_app():
    if not IS_WINDOWS:
        return False
    try:
        os.startfile("microsoft.windows.camera:")
        return True
    except OSError:
        return False


def newest_video_since(since_timestamp):
    """The newest video saved after `since_timestamp` in the usual camera folders."""
    newest = None
    for folder in camera_folders():
        try:
            entries = list(folder.iterdir())
        except OSError:
            continue
        for entry in entries:
            try:
                if entry.suffix.lower() in VIDEO_TYPES and entry.is_file():
                    modified = entry.stat().st_mtime
                    if modified >= since_timestamp - 2 and (newest is None or modified > newest[0]):
                        newest = (modified, entry)
            except OSError:
                continue
    return newest[1] if newest else None
