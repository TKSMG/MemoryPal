"""
MemoryPal v56 beta - safer saves and faster installed builds.

This milestone records the shift from a one-file tester executable toward a
normal installed-app folder, plus local data saves that merge new work from
two open windows instead of blindly overwriting the latest file.
"""

import json
import os
import tempfile
import time
from pathlib import Path


class SmallDataLock:
    def __init__(self, target, timeout=2.0):
        self.path = Path(str(target) + ".lock")
        self.timeout = timeout
        self.handle = None
        self.acquired = False

    def __enter__(self):
        started = time.monotonic()
        while time.monotonic() - started < self.timeout:
            try:
                self.handle = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                self.acquired = True
                return self
            except FileExistsError:
                time.sleep(0.05)
        return self

    def __exit__(self, *_args):
        if self.handle is not None:
            os.close(self.handle)
        if self.acquired:
            self.path.unlink(missing_ok=True)


def merge_by_id(local_items, saved_items):
    merged = list(local_items)
    seen = {item["id"] for item in merged}
    for item in saved_items:
        if item["id"] not in seen:
            merged.append(item)
            seen.add(item["id"])
    return merged


def save_without_losing_other_window(path, local_payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with SmallDataLock(path):
        try:
            saved_payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            saved_payload = {"cards": [], "captures": [], "feedback": []}

        local_payload["cards"] = merge_by_id(local_payload.get("cards", []), saved_payload.get("cards", []))
        local_payload["captures"] = merge_by_id(local_payload.get("captures", []), saved_payload.get("captures", []))
        local_payload["feedback"] = merge_by_id(local_payload.get("feedback", []), saved_payload.get("feedback", []))

        temp_file = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        temp_file.write_text(json.dumps(local_payload, indent=2), encoding="utf-8")
        os.replace(temp_file, path)


if __name__ == "__main__":
    demo_path = Path(tempfile.gettempdir()) / "memorypal-v56-demo.json"
    first_window = {"cards": [{"id": "a", "front": "First window card"}], "captures": [], "feedback": []}
    second_window = {"cards": [{"id": "b", "front": "Second window card"}], "captures": [], "feedback": []}
    save_without_losing_other_window(demo_path, first_window)
    save_without_losing_other_window(demo_path, second_window)
    print(demo_path.read_text(encoding="utf-8"))
