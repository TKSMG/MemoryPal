"""
MemoryPal v62 beta - concurrent save stability.

This milestone records the pass where save merging became safer for two open
windows. Unchanged stale copies now defer to newer saved card progress while
new cards from both windows are kept.
"""

import json
import os
import time
import tkinter as tk
from dataclasses import asdict, dataclass, field
from pathlib import Path
from uuid import uuid4


APP_NAME = "MemoryPal"
BG = "#111827"
SURFACE = "#192338"
RAIL = "#0b1020"
PRIMARY = "#65afff"
GREEN = "#37d67a"
INK = "#edf2fb"
MUTED = "#aeb8cb"


def app_data_file():
    root = os.environ.get("LOCALAPPDATA") or os.environ.get("TMP") or "."
    return Path(root) / "MemoryPalV62Demo" / "memorypal-data.json"


@dataclass
class DemoCard:
    id: str = field(default_factory=lambda: str(uuid4()))
    front: str = ""
    back: str = ""
    repetitions: int = 0
    last_score: int = 0
    last_result: str = "New"


class DemoStore:
    def __init__(self):
        self.path = app_data_file()
        self.cards = []
        self._loaded_cards = {}
        self.load()

    def load(self):
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self.cards = [DemoCard(**item) for item in raw.get("cards", [])]
        except (OSError, TypeError, json.JSONDecodeError):
            self.cards = [DemoCard(front="Sample question", back="Sample answer")]
        self.remember_loaded_state()

    def remember_loaded_state(self):
        self._loaded_cards = {card.id: asdict(card) for card in self.cards}

    def payload(self):
        return {"cards": [asdict(card) for card in self.cards]}

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        existing = self.read_existing()
        payload = self.merge_payload(existing, self.payload())
        temp = self.path.with_name(f".{self.path.name}.{os.getpid()}.tmp")
        temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(temp, self.path)
        self.cards = [DemoCard(**item) for item in payload["cards"]]
        self.remember_loaded_state()

    def read_existing(self):
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else {"cards": []}
        except (OSError, json.JSONDecodeError):
            return {"cards": []}

    def merge_payload(self, existing, local):
        existing_cards = existing.get("cards", [])
        existing_by_id = {
            item.get("id"): item
            for item in existing_cards
            if isinstance(item, dict) and item.get("id")
        }
        merged = []
        seen = set()
        for item in local.get("cards", []):
            item_id = item.get("id")
            existing_item = existing_by_id.get(item_id)
            loaded_item = self._loaded_cards.get(item_id)
            if item_id and existing_item is not None and loaded_item is not None and item == loaded_item and existing_item != loaded_item:
                merged.append(existing_item)
            else:
                merged.append(item)
            if item_id:
                seen.add(item_id)
        for item in existing_cards:
            item_id = item.get("id") if isinstance(item, dict) else None
            if item_id and item_id not in seen:
                merged.append(item)
                seen.add(item_id)
        return {"cards": merged}


class MemoryPalV62(tk.Tk):
    def __init__(self):
        super().__init__()
        self.store = DemoStore()
        self.title(f"{APP_NAME} v62")
        self.geometry("980x620")
        self.minsize(760, 480)
        self.configure(bg=BG)

        self.rail = tk.Frame(self, bg=RAIL, width=238)
        self.rail.pack(side="left", fill="y")
        tk.Label(self.rail, text=APP_NAME, bg=RAIL, fg=INK, font=("Segoe UI Semibold", 22)).pack(anchor="w", padx=22, pady=(28, 8))
        tk.Label(self.rail, text="Concurrent save demo", bg=RAIL, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w", padx=22, pady=(0, 22))

        self.main = tk.Frame(self, bg=BG)
        self.main.pack(side="left", fill="both", expand=True)
        self.header = tk.Label(self.main, text="Safe save check", bg=BG, fg=INK, font=("Segoe UI Semibold", 26))
        self.header.pack(anchor="w", padx=34, pady=(30, 16))
        self.content = tk.Frame(self.main, bg=SURFACE, padx=24, pady=22)
        self.content.pack(fill="both", expand=True, padx=34, pady=(0, 34))

        self.status = tk.Label(self.content, text="", bg=SURFACE, fg=MUTED, font=("Segoe UI", 11), anchor="w")
        self.status.pack(fill="x", pady=(0, 16))
        self.listbox = tk.Listbox(self.content, bg="#101827", fg=INK, selectbackground=PRIMARY, relief="flat", highlightthickness=0, font=("Segoe UI", 11))
        self.listbox.pack(fill="both", expand=True)

        row = tk.Frame(self.content, bg=SURFACE)
        row.pack(fill="x", pady=(16, 0))
        tk.Button(row, text="Add card", command=self.add_card, bg=PRIMARY, fg="#05111f", relief="flat", padx=16, pady=10).pack(side="left", padx=(0, 8))
        tk.Button(row, text="Mark first card easy", command=self.mark_easy, bg=GREEN, fg="#05111f", relief="flat", padx=16, pady=10).pack(side="left", padx=(0, 8))
        tk.Button(row, text="Reload", command=self.reload, bg="#25344f", fg=INK, relief="flat", padx=16, pady=10).pack(side="left")
        self.refresh("Loaded demo data.")

    def refresh(self, message):
        self.listbox.delete(0, "end")
        for index, card in enumerate(self.store.cards, 1):
            self.listbox.insert("end", f"{index}. {card.front} -> {card.back} | {card.last_result} | reps {card.repetitions}")
        self.status.configure(text=message)

    def add_card(self):
        number = len(self.store.cards) + 1
        self.store.cards.append(DemoCard(front=f"Question {number}", back=f"Answer {number}"))
        self.store.save()
        self.refresh("Saved a new card without dropping existing saved cards.")

    def mark_easy(self):
        if not self.store.cards:
            return
        self.store.cards[0].last_score = 95
        self.store.cards[0].last_result = "Easy"
        self.store.cards[0].repetitions += 1
        self.store.save()
        self.refresh("Saved review progress. A stale second window should keep this progress.")

    def reload(self):
        self.store.load()
        self.refresh(f"Reloaded at {time.strftime('%H:%M:%S')}.")


if __name__ == "__main__":
    MemoryPalV62().mainloop()
