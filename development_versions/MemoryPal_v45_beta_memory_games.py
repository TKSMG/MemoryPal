import random
import re
import tkinter as tk
from difflib import SequenceMatcher
from tkinter import ttk


BG = "#101827"
SURFACE = "#182235"
ALT = "#24324b"
INK = "#e8edf7"
MUTED = "#a3b0c8"
PRIMARY = "#5aa8ff"
GREEN = "#37d67a"
ORANGE = "#ffab3d"
PINK = "#ff5c8a"


SAMPLE_ITEMS = [
    "family photo",
    "front door key",
    "morning medicine",
    "math formula",
    "doctor appointment",
    "chapter summary",
    "water the plant",
    "bus stop",
]


def split_bits(text):
    normalized = text.replace("/n", "\n")
    return [item.strip(" -\t") for item in re.split(r"[\n;,|]+", normalized) if item.strip(" -\t")]


def similarity(answer, expected):
    answer = re.sub(r"\s+", " ", answer.lower()).strip()
    expected = re.sub(r"\s+", " ", expected.lower()).strip()
    if not answer or not expected:
        return 0
    return round(SequenceMatcher(None, answer, expected).ratio() * 100)


class MemoryPalV45(tk.Tk):
    """Standalone milestone for the richer Memory Gym puzzle set."""

    def __init__(self):
        super().__init__()
        self.title("MemoryPal v45 - Memory Games")
        self.geometry("1040x720")
        self.minsize(780, 560)
        self.configure(bg=BG)
        self.words = []
        self.nback_items = []
        self.nback_index = 0
        self.nback_score = 0
        self.nback_total = 0
        self.routine_steps = []
        self.build_styles()
        self.build_ui()

    def build_styles(self):
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self.style.configure("Root.TFrame", background=BG)
        self.style.configure("Card.TFrame", background=SURFACE, relief="flat")
        self.style.configure("TLabel", background=BG, foreground=INK, font=("Segoe UI", 11))
        self.style.configure("Card.TLabel", background=SURFACE, foreground=INK, font=("Segoe UI", 11))
        self.style.configure("Muted.TLabel", background=SURFACE, foreground=MUTED, font=("Segoe UI", 10))
        self.style.configure("H1.TLabel", background=BG, foreground=INK, font=("Segoe UI Semibold", 24))
        self.style.configure("H2.TLabel", background=SURFACE, foreground=INK, font=("Segoe UI Semibold", 15))
        self.style.configure("TButton", background=ALT, foreground=INK, padding=(12, 9), borderwidth=0)
        self.style.configure("Primary.TButton", background=PRIMARY, foreground="white", padding=(12, 9), borderwidth=0)

    def build_ui(self):
        page = ttk.Frame(self, style="Root.TFrame", padding=24)
        page.pack(fill="both", expand=True)
        ttk.Label(page, text="MemoryPal Memory Games", style="H1.TLabel").pack(anchor="w")
        tk.Label(
            page,
            text="Short activities for attention, recall, routine memory, and student revision.",
            bg=BG,
            fg=MUTED,
            font=("Segoe UI", 11),
        ).pack(anchor="w", pady=(4, 18))

        grid = ttk.Frame(page, style="Root.TFrame")
        grid.pack(fill="both", expand=True)
        for column in range(2):
            grid.columnconfigure(column, weight=1, uniform="cards")

        self.visual_card(grid, 0, 0)
        self.nback_card(grid, 0, 1)
        self.sort_card(grid, 1, 0)
        self.routine_card(grid, 1, 1)

    def make_card(self, parent, row, column, title, color):
        card = ttk.Frame(parent, style="Card.TFrame", padding=18)
        card.grid(row=row, column=column, sticky="nsew", padx=(0 if column == 0 else 12, 0), pady=(0, 12))
        tk.Frame(card, bg=color, width=34, height=4).pack(anchor="w", pady=(0, 10))
        ttk.Label(card, text=title, style="H2.TLabel").pack(anchor="w")
        return card

    def item_pool(self):
        return list(SAMPLE_ITEMS)

    def visual_card(self, parent, row, column):
        card = self.make_card(parent, row, column, "Visual Search", PRIMARY)
        status = ttk.Label(card, text="Find every matching target.", style="Muted.TLabel")
        status.pack(anchor="w", pady=(4, 10))
        holder = tk.Frame(card, bg=SURFACE)
        holder.pack(fill="x", pady=(0, 10))
        state = {"target": "", "tiles": [], "found": set()}

        def render():
            for child in holder.winfo_children():
                child.destroy()
            for index, word in enumerate(state["tiles"]):
                marked = index in state["found"]
                tile = tk.Button(
                    holder,
                    text=word,
                    bg=GREEN if marked else ALT,
                    fg="white" if marked else INK,
                    relief="flat",
                    bd=0,
                    command=lambda i=index: choose(i),
                )
                tile.grid(row=index // 4, column=index % 4, sticky="ew", padx=3, pady=3)
                holder.columnconfigure(index % 4, weight=1)

        def choose(index):
            if state["tiles"][index] == state["target"]:
                state["found"].add(index)
            count = len([item for item in state["tiles"] if item == state["target"]])
            status.configure(text=f"Target: {state['target']} | Found {len(state['found'])} of {count}")
            render()

        def start():
            pool = self.item_pool()
            target = random.choice(pool)
            tiles = [target] * 4 + random.sample([item for item in pool if item != target], 8)
            random.shuffle(tiles)
            state.update({"target": target, "tiles": tiles, "found": set()})
            status.configure(text=f"Target: {target} | Found 0 of 4")
            render()

        ttk.Button(card, text="New Round", style="Primary.TButton", command=start).pack(fill="x")

    def nback_card(self, parent, row, column):
        card = self.make_card(parent, row, column, "N-Back Lite", PINK)
        word = ttk.Label(card, text="Start a round", style="Card.TLabel", font=("Segoe UI Semibold", 24))
        word.pack(anchor="w", pady=(6, 8))
        status = ttk.Label(card, text="Decide whether this matches the previous item.", style="Muted.TLabel")
        status.pack(anchor="w", pady=(0, 10))

        def show():
            if self.nback_items:
                word.configure(text=self.nback_items[self.nback_index])
                status.configure(text=f"Item {self.nback_index + 1} of {len(self.nback_items)} | Score {self.nback_score}/{self.nback_total}")

        def start():
            pool = self.item_pool()
            self.nback_items = []
            for index in range(10):
                if index and random.random() < 0.35:
                    self.nback_items.append(self.nback_items[-1])
                else:
                    self.nback_items.append(random.choice(pool))
            self.nback_index = 0
            self.nback_score = 0
            self.nback_total = 0
            show()

        def answer(same):
            if not self.nback_items:
                start()
                return
            if self.nback_index == 0:
                self.nback_index = 1
                show()
                return
            actual = self.nback_items[self.nback_index] == self.nback_items[self.nback_index - 1]
            self.nback_total += 1
            self.nback_score += int(actual == same)
            if self.nback_index < len(self.nback_items) - 1:
                self.nback_index += 1
                show()
            else:
                status.configure(text=f"Round complete | Score {self.nback_score}/{self.nback_total}")

        ttk.Button(card, text="New Round", style="Primary.TButton", command=start).pack(fill="x", pady=(0, 6))
        ttk.Button(card, text="Same as Last", command=lambda: answer(True)).pack(fill="x", pady=(0, 6))
        ttk.Button(card, text="Different", command=lambda: answer(False)).pack(fill="x")

    def sort_card(self, parent, row, column):
        card = self.make_card(parent, row, column, "Category Sort", ORANGE)
        entry = tk.Text(card, height=5, bg=ALT, fg=INK, bd=0, padx=10, pady=10, font=("Segoe UI", 10))
        entry.insert("1.0", "\n".join(SAMPLE_ITEMS[:6]))
        entry.pack(fill="x", pady=(8, 10))
        output = ttk.Label(card, text="Build a sorting round.", style="Card.TLabel", wraplength=420)
        output.pack(anchor="w", pady=(0, 10))

        def category(item):
            lower = item.lower()
            if any(word in lower for word in ("family", "doctor", "photo")):
                return "People and memories"
            if any(word in lower for word in ("key", "bus", "door")):
                return "Places and objects"
            if any(word in lower for word in ("medicine", "water", "plant")):
                return "Routines"
            return "Study"

        def build():
            buckets = {}
            for item in split_bits(entry.get("1.0", "end")):
                buckets.setdefault(category(item), []).append(item)
            lines = [f"{name}: {', '.join(items)}" for name, items in buckets.items()]
            output.configure(text="\n".join(lines) if lines else "Add items first.")

        ttk.Button(card, text="Build Sort", style="Primary.TButton", command=build).pack(fill="x")

    def routine_card(self, parent, row, column):
        card = self.make_card(parent, row, column, "Routine Recall", GREEN)
        prompt = ttk.Label(card, text="Press Show Routine", style="Card.TLabel", wraplength=420)
        prompt.pack(anchor="w", pady=(8, 10))
        answer = tk.Text(card, height=5, bg=ALT, fg=INK, bd=0, padx=10, pady=10, font=("Segoe UI", 10))
        answer.pack(fill="x", pady=(0, 10))
        status = ttk.Label(card, text="A gentle score will appear here.", style="Muted.TLabel")
        status.pack(anchor="w", pady=(0, 10))

        def show():
            self.routine_steps = SAMPLE_ITEMS[:4]
            prompt.configure(text="\n".join(f"{index + 1}. {step}" for index, step in enumerate(self.routine_steps)))
            answer.delete("1.0", "end")
            self.after(4200, lambda: prompt.configure(text="Now type the steps in order."))

        def check():
            expected = "\n".join(self.routine_steps)
            status.configure(text=f"Similarity: {similarity(answer.get('1.0', 'end'), expected)}%")

        ttk.Button(card, text="Show Routine", style="Primary.TButton", command=show).pack(fill="x", pady=(0, 6))
        ttk.Button(card, text="Check Routine", command=check).pack(fill="x")


if __name__ == "__main__":
    MemoryPalV45().mainloop()
