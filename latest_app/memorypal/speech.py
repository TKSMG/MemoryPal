"""Offline read-aloud using the voice built into the operating system.

No extra packages: Windows uses System.Speech through PowerShell, macOS uses
`say`, and Linux uses `espeak` if it is installed. Text is passed on stdin,
never on the command line, so card text can't break or inject into the
command.
"""

import shutil
import subprocess
import sys

from .core import normalize_space

WINDOWS_SCRIPT = (
    "[Console]::InputEncoding = [Text.Encoding]::UTF8; "
    "Add-Type -AssemblyName System.Speech; "
    "$voice = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
    "$voice.Rate = {rate}; "
    "$voice.Speak([Console]::In.ReadToEnd())"
)


class Speaker:
    def __init__(self):
        self.process = None

    def command(self, slow=False):
        if sys.platform.startswith("win"):
            return ["powershell", "-NoProfile", "-NonInteractive", "-Command", WINDOWS_SCRIPT.format(rate=-3 if slow else -1)]
        if sys.platform == "darwin":
            return ["say", "-r", "150" if slow else "180"]
        espeak = shutil.which("espeak-ng") or shutil.which("espeak")
        if espeak:
            return [espeak, "--stdin", "-s", "130" if slow else "160"]
        return None

    def available(self):
        return self.command() is not None

    def speak(self, text, slow=False):
        """Start reading text aloud, replacing anything already being read."""
        self.stop()
        text = normalize_space(text)
        command = self.command(slow)
        if not text or not command:
            return False
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            self.process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=flags,
            )
            self.process.stdin.write(text.encode("utf-8"))
            self.process.stdin.close()
            return True
        except OSError:
            self.process = None
            return False

    def stop(self):
        if self.process is not None and self.process.poll() is None:
            try:
                self.process.terminate()
            except OSError:
                pass
        self.process = None
