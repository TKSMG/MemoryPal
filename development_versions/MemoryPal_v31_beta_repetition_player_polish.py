"""
MemoryPal v31 beta - repetition player and final polish

Independent milestone prototype. This version captures the move from a long
generated list of repetition cards into a focused round-by-round exercise with
progress, Smart Check, reveal, and next/previous controls.
"""

import re
import tkinter as tk
from difflib import SequenceMatcher
from tkinter import ttk


COLORS = {
    "bg": "#101827",
    "panel": "#172235",
    "alt": "#20304c",
    "ink": "#f2f6ff",
    "muted": "#9aabc7",
    "primary": "#4d9cff",
    "good": "#49d17d",
    "warn": "#ffbe4d",
}


def normalize(value):
    return re.sub(r"\s+", " ", value or "").strip()


def split_bits(raw):
    raw = (raw or "").replace("\\n", "\n").replace("/n", "\n")
    return [normalize(re.sub(r"^[-*\d.)\s]+", "", line)) for line in raw.splitlines() if normalize(line)]


def smart_score(response, expected):
    response = normalize(response).lower()
    expected = normalize(expected).lower()
    if not response:
        return 0, "Type an answer first."
    ratio = SequenceMatcher(None, response, expected).ratio()
    response_words = set(re.findall(r"[a-z0-9]+", response))
    expected_words = set(re.findall(r"[a-z0-9]+", expected))
    overlap = len(response_words & expected_words) / max(1, len(expected_words))
    score = round(max(ratio, overlap) * 100)
    if score >= 82:
        return score, "Looks strong. Move on or mark Easy."
    if score >= 58:
        return score, "Close. Repeat this round once more."
    return score, "Needs another pass. Reveal, restudy, then try again."


def repetition_steps(count, start, span):
    if count <= 0:
        return []
    start_index = min(max(start, 1), count) - 1
    span = min(max(span, 1), count)
    steps = []
    current = []
    for offset in range(span):
        index = start_index - offset
        if index < 0:
            break
        current.append(index)
        steps.append(list(current))
    if current and current[-1] > 0:
        steps.append(list(range(current[-1], -1, -1)))
    return steps


class RepetitionPlayer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MemoryPal v31 - Repetition Player")
        self.geometry("1100x760")
        self.minsize(900, 620)
        self.configure(bg=COLORS["bg"])
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self.style.configure("TFrame", background=COLORS["bg"])
        self.style.configure("Panel.TFrame", background=COLORS["panel"])
        self.style.configure("Alt.TFrame", background=COLORS["alt"])
        self.style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["ink"], font=("Segoe UI", 12))
        self.style.configure("Panel.TLabel", background=COLORS["panel"], foreground=COLORS["ink"], font=("Segoe UI", 12))
        self.style.configure("Muted.TLabel", background=COLORS["panel"], foreground=COLORS["muted"], font=("Segoe UI", 10))
        self.style.configure("Title.TLabel", background=COLORS["bg"], foreground=COLORS["ink"], font=("Segoe UI Semibold", 26))
        self.style.configure("TButton", padding=(14, 10), background=COLORS["alt"], foreground=COLORS["ink"], borderwidth=0)
        self.style.configure("Primary.TButton", padding=(14, 10), background=COLORS["primary"], foreground="white", borderwidth=0)
        self.items = []
        self.steps = []
        self.round_index = 0
        self.build()

    def build(self):
        ttk.Label(self, text="Repetition Path", style="Title.TLabel").pack(anchor="w", padx=24, pady=(24, 12))
        shell = ttk.Frame(self)
        shell.pack(fill="both", expand=True, padx=24, pady=(0, 24))
        builder = ttk.Frame(shell, style="Panel.TFrame", padding=20)
        builder.pack(fill="x")
        ttk.Label(builder, text="Question / title", style="Muted.TLabel").pack(anchor="w")
        self.prompt = ttk.Entry(builder)
        self.prompt.insert(0, "Study item")
        self.prompt.pack(fill="x", pady=(4, 10))
        ttk.Label(builder, text="Answers, one per line", style="Muted.TLabel").pack(anchor="w")
        self.answers = tk.Text(builder, height=7, wrap="word", bg="#0d1422", fg=COLORS["ink"], insertbackground=COLORS["primary"], bd=0, padx=12, pady=10)
        self.answers.insert("1.0", "First idea\nSecond idea\nThird idea\nFourth idea\nFifth idea")
        self.answers.pack(fill="x", pady=(4, 10))
        controls = ttk.Frame(builder, style="Panel.TFrame")
        controls.pack(fill="x")
        ttk.Label(controls, text="Start #", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(controls, text="Range", style="Muted.TLabel").grid(row=0, column=1, sticky="w")
        self.start = ttk.Entry(controls, width=8)
        self.start.insert(0, "5")
        self.start.grid(row=1, column=0, sticky="ew", padx=(0, 8))
        self.span = ttk.Entry(controls, width=8)
        self.span.insert(0, "3")
        self.span.grid(row=1, column=1, sticky="ew", padx=(0, 8))
        ttk.Button(controls, text="Build round player", style="Primary.TButton", command=self.start_player).grid(row=1, column=2, sticky="ew")
        controls.columnconfigure(2, weight=1)
        self.player = ttk.Frame(shell)
        self.player.pack(fill="both", expand=True, pady=(16, 0))

    def start_player(self):
        answers = split_bits(self.answers.get("1.0", "end"))
        self.items = [{"prompt": f"{normalize(self.prompt.get()) or 'Study item'} {index + 1}", "answer": answer} for index, answer in enumerate(answers)]
        try:
            start = int(self.start.get() or len(self.items))
            span = int(self.span.get() or 3)
        except ValueError:
            start, span = len(self.items), 3
        self.steps = repetition_steps(len(self.items), start, span)
        self.round_index = 0
        self.render_round()

    def render_round(self):
        for child in self.player.winfo_children():
            child.destroy()
        if not self.steps:
            ttk.Label(self.player, text="Add answers first.").pack(anchor="w")
            return
        indexes = self.steps[self.round_index]
        card = ttk.Frame(self.player, style="Panel.TFrame", padding=22)
        card.pack(fill="both", expand=True)
        label = "-".join(str(index + 1) for index in indexes)
        ttk.Label(card, text=f"Round {self.round_index + 1} of {len(self.steps)}", style="Muted.TLabel").pack(anchor="w")
        ttk.Label(card, text=f"Repeat {label}", style="Panel.TLabel", font=("Segoe UI Semibold", 22)).pack(anchor="w", pady=(4, 10))
        ttk.Progressbar(card, maximum=len(self.steps), value=self.round_index + 1).pack(fill="x", pady=(0, 16))
        prompts = ttk.Frame(card, style="Alt.TFrame", padding=14)
        prompts.pack(fill="x", pady=(0, 14))
        for index in indexes:
            ttk.Label(prompts, text=f"{index + 1}. {self.items[index]['prompt']}", background=COLORS["alt"], foreground=COLORS["ink"], font=("Segoe UI", 12)).pack(anchor="w", pady=2)
        answer = tk.Text(card, height=5, wrap="word", bg="#0d1422", fg=COLORS["ink"], insertbackground=COLORS["primary"], bd=0, padx=12, pady=10)
        answer.pack(fill="x")
        status = ttk.Label(card, text="Type the sequence, then Smart Check or reveal.", style="Muted.TLabel", wraplength=900)
        status.pack(anchor="w", pady=(10, 0))

        def check():
            expected = "\n".join(self.items[index]["answer"] for index in indexes)
            score, detail = smart_score(answer.get("1.0", "end"), expected)
            status.configure(text=f"Smart Check: {score}% - {detail}")

        def reveal():
            status.configure(text="Answer: " + "  |  ".join(self.items[index]["answer"] for index in indexes))

        def move(delta):
            self.round_index = min(max(self.round_index + delta, 0), len(self.steps) - 1)
            self.render_round()

        row = ttk.Frame(card, style="Panel.TFrame")
        row.pack(fill="x", pady=(16, 0))
        for column, (text, command, style) in enumerate([
            ("Smart Check", check, "Primary.TButton"),
            ("Reveal", reveal, "TButton"),
            ("Previous", lambda: move(-1), "TButton"),
            ("Next", lambda: move(1), "TButton"),
        ]):
            state = "disabled" if (text == "Previous" and self.round_index == 0) or (text == "Next" and self.round_index == len(self.steps) - 1) else "normal"
            ttk.Button(row, text=text, command=command, style=style, state=state).grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 8, 0))
            row.columnconfigure(column, weight=1)


if __name__ == "__main__":
    RepetitionPlayer().mainloop()
