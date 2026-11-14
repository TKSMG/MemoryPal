"""Check talk-back listening end to end on a Windows machine with no microphone.

Windows' own voice reads each answer into a sound file, and the app's
recogniser listens to that file: once the old way (dictation only) and once
the way the app runs it (the round's answers given as hints). Prints what
was heard each time.
"""

import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "latest_app"))

from memorypal import listen  # noqa: E402
from memorypal.core import answer_assessment, powershell_exe  # noqa: E402

ANSWERS = [
    "the mitochondria",
    "photosynthesis",
    "Canberra",
    "the Krebs cycle",
    "deoxyribonucleic acid",
    "Pythagoras",
    "osmosis is the movement of water across a membrane",
    "the Treaty of Versailles",
]


def speak_to_file(text, path):
    script = (
        "Add-Type -AssemblyName System.Speech; "
        "$voice = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"$voice.SetOutputToWaveFile('{path}'); $voice.Speak('{text}'); $voice.Dispose()"
    )
    subprocess.run([powershell_exe(), "-NoProfile", "-NonInteractive", "-Command", script], check=True, timeout=120)


def hear(path, hints):
    listener = listen.Listener()
    began = time.perf_counter()
    if not listener.prepare(hints, wave_file=path):
        return None, 0.0, 0.0
    while listener.prepared() and not any(line.startswith(listen.READY) for line in list(listener._lines)):
        time.sleep(0.02)
    loaded = time.perf_counter() - began
    listener.go()
    result = None
    while result is None:
        time.sleep(0.05)
        result = listener.poll()
    return result, loaded, time.perf_counter() - began


def main():
    listener = listen.Listener()
    print("recognisers installed:", listener.probe())
    if not listener.probe():
        return
    folder = Path(tempfile.mkdtemp())
    right = {"plain": 0, "hints": 0}
    commands = [phrase for phrases in listen.SPOKEN_COMMANDS.values() for phrase in phrases]
    for number, answer in enumerate(ANSWERS):
        path = folder / f"answer{number}.wav"
        speak_to_file(answer, path)
        for label, hints in (("plain", []), ("hints", commands + ANSWERS)):
            result, loaded, total = hear(path, hints)
            if result is None or not result.heard:
                print(f"{label:5} {answer!r}: {result}")
                continue
            best = max(result.readings(), key=lambda reading: answer_assessment(reading, answer)["score"])
            good = answer_assessment(best, answer)["bucket"] in ("Good", "Easy")
            right[label] += good
            print(f"{label:5} {answer!r}: heard {result.text!r} conf {result.confidence:.2f} others {list(result.alternates)} -> {'right' if good else 'WRONG'} (ready in {loaded:.1f}s, done {total:.1f}s)")
    # Wrong answers must not be heard as a right one just because the right
    # ones are known to the recogniser.
    for number, (said, expected) in enumerate((("Sydney", "Canberra"), ("the nucleus", "the mitochondria"), ("I think it is respiration", "photosynthesis"), ("Aristotle", "Pythagoras"))):
        path = folder / f"wrong{number}.wav"
        speak_to_file(said, path)
        result, _loaded, _total = hear(path, commands + ANSWERS)
        if result is None or not result.heard:
            print(f"wrong {said!r} for {expected!r}: {result}")
            continue
        best = max(result.readings(), key=lambda reading: answer_assessment(reading, expected)["score"])
        good = answer_assessment(best, expected)["bucket"] in ("Good", "Easy")
        print(f"wrong {said!r} for {expected!r}: heard {result.text!r} conf {result.confidence:.2f} others {list(result.alternates)} -> {'MARKED RIGHT (bad)' if good else 'marked wrong (good)'}")
    print(f"marked right: dictation only {right['plain']}/{len(ANSWERS)}, with hints {right['hints']}/{len(ANSWERS)}")


if __name__ == "__main__":
    main()
