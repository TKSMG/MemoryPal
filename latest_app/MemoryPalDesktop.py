import json
import random
import re
import shutil
import sys
import tkinter as tk
import ctypes
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from uuid import uuid4


APP_NAME = "MemoryPal"
DATA_DIR = Path.home() / "MemoryPalData"
DATA_FILE = DATA_DIR / "memorypal-data.json"
ATTACHMENT_DIR = DATA_DIR / "attachments"
BASE_DPI = 96
BASE_WINDOW = (1420, 900)
BASE_MIN_WINDOW = (1080, 720)

COLORS = {
    "bg": "#f4f7fb",
    "surface": "#ffffff",
    "surface_soft": "#f8fbff",
    "alt": "#edf6ff",
    "ink": "#111827",
    "muted": "#5f6f85",
    "line": "#dfe7f2",
    "soft_line": "#dbeafe",
    "primary": "#007aff",
    "primary_dark": "#0066d6",
    "green": "#34c759",
    "orange": "#ff9500",
    "pink": "#ff2d55",
    "violet": "#af52de",
    "cyan": "#32ade6",
    "rail": "#0f172a",
    "rail_hover": "#1e293b",
    "white": "#ffffff",
    "danger": "#ff3b30",
    "input": "#fbfdff",
    "warm": "#fff7ed",
    "warm_text": "#9a3412",
    "again_bg": "#ffe8e6",
    "again_fg": "#b42318",
    "review_bg": "#fff3d6",
    "review_fg": "#9a5b00",
    "good_bg": "#e8f8ef",
    "good_fg": "#147a3d",
    "easy_bg": "#e7f0ff",
    "easy_fg": "#0057c2",
}

SELF_CHECK_ANSWER = "No saved answer. Use this as a self-check prompt, then rate yourself."


def clamp(value, low, high):
    return max(low, min(high, value))


def enable_dpi_awareness():
    if not sys.platform.startswith("win"):
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def uid():
    return str(uuid4())


def today_iso():
    return date.today().isoformat()


def add_days(days):
    return (date.today() + timedelta(days=days)).isoformat()


def now_label():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def normalize_space(value):
    return re.sub(r"\s+", " ", value or "").strip()


def split_study_bits(raw):
    raw = (raw or "").replace("\\n", "\n").replace("/n", "\n")
    raw = re.sub(r"\s+(?=\d+[.)]\s+)", "\n", raw)
    raw = re.sub(r"\s*[|;]\s*", "\n", raw)
    lines = [re.sub(r"^[-*\d.)\s]+", "", line).strip() for line in raw.splitlines()]
    lines = [line for line in lines if line]
    if len(lines) >= 2:
        return lines
    sentences = [part.strip() for part in re.split(r"[.!?]+", raw) if part.strip()]
    if len(sentences) > 1:
        return sentences
    comma_bits = [part.strip() for part in raw.split(",") if part.strip()]
    return comma_bits if len(comma_bits) > 1 else ([raw.strip()] if raw.strip() else [])


def parse_prompt_answer_lines(raw):
    items = []
    for index, line in enumerate((raw or "").replace("\\n", "\n").replace("/n", "\n").splitlines(), 1):
        line = normalize_space(line)
        if not line:
            continue
        line = re.sub(r"^[-*\d.)\s]+", "", line).strip()
        prompt, answer = "", line
        for delimiter in ("=>", "::", " - "):
            if delimiter in line:
                prompt, answer = line.split(delimiter, 1)
                prompt, answer = normalize_space(prompt), normalize_space(answer)
                break
        if answer:
            items.append({"prompt": prompt or f"Study bit {index}", "answer": answer})
    return items


STOP_WORDS = {
    "the", "and", "for", "with", "into", "that", "this", "what", "should",
    "remember", "image", "audio", "video", "cue", "about", "from", "your",
    "their", "there", "then", "than", "when", "where", "which", "while",
    "because", "have", "has", "had", "are", "was", "were", "will", "would",
    "could", "also", "just", "like", "make", "made",
}


def text_tokens(value):
    tokens = []
    for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9'-]{2,}", value or ""):
        token = token.lower()
        if token in STOP_WORDS:
            continue
        for suffix in ("ingly", "edly", "ing", "ed", "es", "s"):
            if token.endswith(suffix) and len(token) > len(suffix) + 3:
                token = token[: -len(suffix)]
                break
        tokens.append(token)
    return tokens


def answer_assessment(response, expected, context=""):
    response = normalize_space(response)
    expected_text = normalize_space(" ".join(part for part in [expected, context] if part))
    if not response:
        return {
            "score": 0,
            "quality": 1,
            "label": "Needs response",
            "bucket": "Again",
            "repetitions": 5,
            "detail": "Type an answer, transcript, caption, or media description first.",
        }

    expected_tokens = text_tokens(expected_text)
    response_tokens = text_tokens(response)
    sequence = SequenceMatcher(None, response.lower(), expected_text.lower()).ratio() if expected_text else 0
    expected_set = set(expected_tokens)
    response_set = set(response_tokens)
    coverage = len(expected_set & response_set) / max(1, len(expected_set))

    expected_counts = Counter(expected_tokens)
    response_counts = Counter(response_tokens)
    weighted_hits = sum(min(response_counts[word], expected_counts[word]) for word in expected_counts)
    weighted = weighted_hits / max(1, sum(expected_counts.values()))

    score = min(100, round(100 * (0.28 * sequence + 0.52 * coverage + 0.20 * weighted)))
    if score >= 82:
        quality, label, reps, bucket = 5, "Strong match", 1, "Easy"
    elif score >= 64:
        quality, label, reps, bucket = 4, "Close enough", 2, "Good"
    elif score >= 42:
        quality, label, reps, bucket = 3, "Partial match", 3, "Review"
    elif score >= 24:
        quality, label, reps, bucket = 2, "Weak match", 4, "Again"
    else:
        quality, label, reps, bucket = 1, "Missed context", 5, "Again"

    missing = [word for word, _count in expected_counts.most_common(6) if word not in response_set]
    detail = "Missing key cues: " + ", ".join(missing[:4]) if missing else "Main cues are covered."
    return {"score": score, "quality": quality, "label": label, "bucket": bucket, "repetitions": reps, "detail": detail}


@dataclass
class Card:
    id: str = field(default_factory=uid)
    deck: str = "General"
    front: str = ""
    back: str = ""
    pathway: str = ""
    association: str = ""
    text_file: str = ""
    image: str = ""
    audio: str = ""
    video: str = ""
    next_review: str = field(default_factory=today_iso)
    interval: int = 0
    repetitions: int = 0
    ease: float = 2.5
    lapses: int = 0
    last_score: int = 0
    last_result: str = "New"
    created_at: str = field(default_factory=now_label)

    @classmethod
    def from_dict(cls, raw):
        values = {field_name: raw.get(field_name) for field_name in cls.__dataclass_fields__}
        values["id"] = raw.get("id", uid())
        values["next_review"] = raw.get("next_review", raw.get("nextReview", today_iso()))
        values["interval"] = int(raw.get("interval", 0))
        values["repetitions"] = int(raw.get("repetitions", 0))
        values["ease"] = float(raw.get("ease", 2.5))
        values["lapses"] = int(raw.get("lapses", 0))
        values["last_score"] = int(raw.get("last_score", raw.get("lastScore", 0)))
        values["last_result"] = raw.get("last_result", raw.get("lastResult", "New"))
        values["created_at"] = raw.get("created_at", raw.get("createdAt", now_label()))
        return cls(**values)


@dataclass
class Capture:
    id: str = field(default_factory=uid)
    title: str = "Captured memory material"
    notes: str = ""
    chunks: list = field(default_factory=list)
    text_file: str = ""
    image: str = ""
    audio: str = ""
    video: str = ""
    created_at: str = field(default_factory=now_label)

    @classmethod
    def from_dict(cls, raw):
        notes = raw.get("notes", "")
        chunks = raw.get("chunks") or split_study_bits(notes)
        return cls(
            id=raw.get("id", uid()),
            title=raw.get("title", "Captured memory material"),
            notes=notes,
            chunks=chunks,
            text_file=raw.get("text_file", raw.get("textFile", "")),
            image=raw.get("image", ""),
            audio=raw.get("audio", ""),
            video=raw.get("video", ""),
            created_at=raw.get("created_at", raw.get("createdAt", now_label())),
        )


def sample_cards():
    return [
        Card(
            deck="Memory Techniques",
            front="What is spaced repetition?",
            back="Reviewing information at increasing intervals so recall strengthens over time.",
            pathway="Dashboard > Review > due cards",
            association="The space between reviews grows like stepping stones.",
        ),
        Card(
            deck="Memory Techniques",
            front="What is retrieval practice?",
            back="Trying to recall the answer before rereading or revealing it.",
            pathway="Quiz > Self Check",
            association="Pull the memory out instead of looking it up first.",
        ),
        Card(
            deck="Memory Techniques",
            front="What is chunking?",
            back="Breaking information into smaller meaningful pieces so each part is easier to practise.",
            pathway="Capture > study bits",
            association="One shelf per idea.",
        ),
        Card(
            deck="Memory Techniques",
            front="Why use media cues?",
            back="Images, audio, video, and text notes can make a memory more familiar and easier to retrieve.",
            pathway="Capture > attach cues",
            association="A cue gives the memory a handle.",
        ),
    ]


class MemoryStore:
    def __init__(self):
        self.cards = []
        self.captures = []
        self.practiced = 0
        self.load()

    def load(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        ATTACHMENT_DIR.mkdir(parents=True, exist_ok=True)
        if not DATA_FILE.exists():
            self.cards = sample_cards()
            self.save()
            return
        try:
            raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            self.cards = [Card.from_dict(item) for item in raw.get("cards", [])]
            self.captures = [Capture.from_dict(item) for item in raw.get("captures", [])]
            self.practiced = int(raw.get("practiced", 0))
        except (OSError, json.JSONDecodeError, ValueError):
            self.cards = sample_cards()
            self.captures = []
            self.practiced = 0

    def save(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        DATA_FILE.write_text(
            json.dumps(
                {
                    "cards": [asdict(card) for card in self.cards],
                    "captures": [asdict(capture) for capture in self.captures],
                    "practiced": self.practiced,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def due_cards(self):
        return [card for card in self.cards if card.next_review <= today_iso()]

    def upcoming_cards(self):
        return sorted([card for card in self.cards if card.next_review > today_iso()], key=lambda card: card.next_review)

    def weak_cards(self):
        scored = [
            card for card in self.cards
            if card.lapses > 0 or card.last_score < 64 or card.repetitions == 0
        ]
        return sorted(scored, key=lambda card: (-card.lapses, card.last_score, card.next_review, card.front.lower()))

    def add_card(self, card):
        self.cards.insert(0, card)
        self.save()

    def add_capture(self, capture):
        self.captures.insert(0, capture)
        self.save()

    def schedule(self, card, quality, assessment=None):
        if quality < 3:
            card.repetitions = 0
            card.interval = 1
            card.lapses += 1
        else:
            if card.repetitions == 0:
                card.interval = 1
            elif card.repetitions == 1:
                card.interval = 3
            else:
                card.interval = max(1, round(card.interval * card.ease))
            card.repetitions += 1
        card.ease = max(1.3, card.ease + (0.1 - (5 - quality) * 0.08))
        card.next_review = add_days(card.interval)
        if assessment:
            card.last_score = int(assessment.get("score", 0))
            card.last_result = assessment.get("label", "Checked")
        else:
            card.last_score = {1: 20, 2: 35, 3: 55, 4: 78, 5: 95}.get(quality, 0)
            card.last_result = {1: "Again", 2: "Weak", 3: "Review", 4: "Good", 5: "Easy"}.get(quality, "Checked")
        self.practiced += 1
        self.save()

    def reset(self):
        self.cards = sample_cards()
        self.captures = []
        self.practiced = 0
        self.save()


class ScrollFrame(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, highlightthickness=0, bg=COLORS["bg"])
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas, style="Page.TFrame")
        self.window_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.inner.bind("<Configure>", lambda _event: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda event: self.canvas.itemconfigure(self.window_id, width=event.width))
        self.canvas.bind("<Enter>", lambda _event: self.canvas.focus_set())
        self.canvas.bind("<Prior>", lambda _event: self._scroll_pages(-1))
        self.canvas.bind("<Next>", lambda _event: self._scroll_pages(1))
        self.canvas.bind("<Home>", lambda _event: self._scroll_to(0.0))
        self.canvas.bind("<End>", lambda _event: self._scroll_to(1.0))
        self.canvas.bind_all("<MouseWheel>", self._wheel)
        self.canvas.bind_all("<Button-4>", self._wheel)
        self.canvas.bind_all("<Button-5>", self._wheel)

    def _nearest_scrollframe_under_pointer(self, event):
        widget = self.winfo_containing(event.x_root, event.y_root)
        while widget is not None:
            if isinstance(widget, ScrollFrame):
                return widget
            widget = getattr(widget, "master", None)
        return None

    def _wheel(self, event):
        if not self.winfo_ismapped():
            return None
        if self._nearest_scrollframe_under_pointer(event) is not self:
            return None
        if getattr(event, "num", None) == 4:
            units = -3
        elif getattr(event, "num", None) == 5:
            units = 3
        else:
            delta = getattr(event, "delta", 0)
            units = int(-delta / 120) if abs(delta) >= 120 else (-1 if delta > 0 else 1)
        self.canvas.yview_scroll(units, "units")
        return "break"

    def _scroll_pages(self, direction):
        self.canvas.yview_scroll(direction, "pages")
        return "break"

    def _scroll_to(self, position):
        self.canvas.yview_moveto(position)
        return "break"


class Tooltip:
    def __init__(self, widget, text, delay=550):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.after_id = None
        self.tip = None
        widget.bind("<Enter>", self.schedule, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress>", self.hide, add="+")

    def schedule(self, _event=None):
        self.cancel()
        self.after_id = self.widget.after(self.delay, self.show)

    def cancel(self):
        if self.after_id:
            self.widget.after_cancel(self.after_id)
            self.after_id = None

    def show(self):
        if self.tip or not self.text:
            return
        x = self.widget.winfo_rootx() + 18
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            self.tip,
            text=self.text,
            bg=COLORS["rail"],
            fg=COLORS["white"],
            padx=10,
            pady=7,
            justify="left",
            wraplength=280,
            font=("Segoe UI", 10),
        )
        label.pack()

    def hide(self, _event=None):
        self.cancel()
        if self.tip:
            self.tip.destroy()
            self.tip = None


class MemoryPalApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.dpi_scale, self.size_scale = self._display_scales()
        self.ui_scale = clamp(max(self.dpi_scale, self.size_scale), 0.95, 1.35)
        self.font_scale = clamp(self.size_scale, 0.96, 1.12)
        try:
            self.tk.call("tk", "scaling", clamp(self.dpi_scale * BASE_DPI / 72, 1.0, 2.4))
        except tk.TclError:
            pass
        self.store = MemoryStore()
        self.current_view = "dashboard"
        self.current_review = None
        self.quiz_cards = []
        self.quiz_round = 0
        self.quiz_score = 0
        self.quiz_mode = "self"
        self.sequence = ""
        self.testing_card = None
        self.return_view = "dashboard"
        self.testing_context = "study"
        self.pending_media = {"text_file": "", "image": "", "audio": "", "video": ""}
        self.route_token = 0
        self.media_images = []
        self.view_drafts = {}
        self.draft_savers = {}

        self.title(APP_NAME)
        self._set_window_size()
        self.configure(bg=COLORS["bg"])
        self._styles()
        self._shell()
        self.show_view("dashboard")

    def _display_scales(self):
        try:
            dpi = float(self.winfo_fpixels("1i"))
        except tk.TclError:
            dpi = BASE_DPI
        dpi_scale = clamp(dpi / BASE_DPI, 1.0, 1.65)
        screen_w = max(1, self.winfo_screenwidth())
        screen_h = max(1, self.winfo_screenheight())
        size_scale = clamp(min(screen_w / 1536, screen_h / 960), 0.92, 1.14)
        return dpi_scale, size_scale

    def px(self, value):
        return max(1, int(round(value * self.ui_scale)))

    def font(self, family, size):
        return (family, max(8, int(round(size * self.font_scale))))

    def pad(self, *values):
        return tuple(self.px(value) for value in values)

    def _set_window_size(self):
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        margin = self.px(96)
        width = min(self.px(BASE_WINDOW[0]), max(self.px(980), screen_w - margin))
        height = min(self.px(BASE_WINDOW[1]), max(self.px(640), screen_h - margin))
        min_width = min(self.px(BASE_MIN_WINDOW[0]), width)
        min_height = min(self.px(BASE_MIN_WINDOW[1]), height)
        self.geometry(f"{width}x{height}")
        self.minsize(min_width, min_height)

    def _styles(self):
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self.option_add("*Font", self.font("Segoe UI", 12))
        self.style.configure("Root.TFrame", background=COLORS["bg"])
        self.style.configure("Rail.TFrame", background=COLORS["rail"])
        self.style.configure("Page.TFrame", background=COLORS["bg"])
        self.style.configure("Header.TFrame", background=COLORS["surface"], relief="flat", borderwidth=0)
        self.style.configure("Card.TFrame", background=COLORS["surface"], relief="flat", borderwidth=0)
        self.style.configure("AltCard.TFrame", background=COLORS["alt"], relief="flat", borderwidth=0)
        self.style.configure("WarmCard.TFrame", background=COLORS["warm"], relief="flat", borderwidth=0)
        self.style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["ink"], font=self.font("Segoe UI", 12))
        self.style.configure("Muted.TLabel", background=COLORS["bg"], foreground=COLORS["muted"], font=self.font("Segoe UI", 11))
        self.style.configure("Card.TLabel", background=COLORS["surface"], foreground=COLORS["ink"], font=self.font("Segoe UI", 12))
        self.style.configure("CardMuted.TLabel", background=COLORS["surface"], foreground=COLORS["muted"], font=self.font("Segoe UI", 11))
        self.style.configure("Header.TLabel", background=COLORS["surface"], foreground=COLORS["ink"], font=self.font("Segoe UI", 12))
        self.style.configure("HeaderMuted.TLabel", background=COLORS["surface"], foreground=COLORS["muted"], font=self.font("Segoe UI", 11))
        self.style.configure("AltCard.TLabel", background=COLORS["alt"], foreground=COLORS["ink"], font=self.font("Segoe UI", 12))
        self.style.configure("AltMuted.TLabel", background=COLORS["alt"], foreground=COLORS["muted"], font=self.font("Segoe UI", 11))
        self.style.configure("WarmCard.TLabel", background=COLORS["warm"], foreground=COLORS["warm_text"], font=self.font("Segoe UI", 12))
        self.style.configure("WarmMuted.TLabel", background=COLORS["warm"], foreground=COLORS["muted"], font=self.font("Segoe UI", 11))
        self.style.configure("Title.TLabel", background=COLORS["surface"], foreground=COLORS["ink"], font=self.font("Segoe UI Semibold", 28))
        self.style.configure("H2.TLabel", background=COLORS["surface"], foreground=COLORS["ink"], font=self.font("Segoe UI Semibold", 18))
        self.style.configure("AltH2.TLabel", background=COLORS["alt"], foreground=COLORS["ink"], font=self.font("Segoe UI Semibold", 18))
        self.style.configure("WarmH2.TLabel", background=COLORS["warm"], foreground=COLORS["warm_text"], font=self.font("Segoe UI Semibold", 18))
        self.style.configure("Stat.TLabel", background=COLORS["surface"], foreground=COLORS["primary"], font=self.font("Segoe UI Semibold", 34))
        self.style.configure("RailTitle.TLabel", background=COLORS["rail"], foreground=COLORS["white"], font=self.font("Segoe UI Semibold", 20))
        self.style.configure("RailText.TLabel", background=COLORS["rail"], foreground="#9ca3af", font=self.font("Segoe UI", 12))
        self.style.configure("TEntry", padding=self.px(11), fieldbackground=COLORS["white"], bordercolor=COLORS["line"], lightcolor=COLORS["line"], darkcolor=COLORS["line"], relief="flat")
        self.style.map("TEntry", bordercolor=[("focus", COLORS["primary"])])
        self.style.configure("TCombobox", padding=self.px(11), fieldbackground=COLORS["white"], bordercolor=COLORS["line"], relief="flat")
        self.style.configure("Vertical.TScrollbar", gripcount=0, background="#cbd5e1", darkcolor=COLORS["bg"], lightcolor=COLORS["bg"], troughcolor=COLORS["bg"], bordercolor=COLORS["bg"], arrowcolor=COLORS["muted"], relief="flat")
        self.style.configure("Horizontal.TProgressbar", troughcolor=COLORS["alt"], background=COLORS["primary"], bordercolor=COLORS["alt"], lightcolor=COLORS["primary"], darkcolor=COLORS["primary"])
        self.style.configure("TButton", padding=self.pad(18, 12), background=COLORS["surface_soft"], foreground=COLORS["ink"], borderwidth=0, relief="flat", focuscolor=COLORS["surface_soft"], font=self.font("Segoe UI Semibold", 11))
        self.style.map("TButton", background=[("active", "#e8f2ff"), ("pressed", "#dcecff")], foreground=[("active", COLORS["primary"])])
        self.style.configure("Primary.TButton", padding=self.pad(18, 12), background=COLORS["primary"], foreground=COLORS["white"], borderwidth=0, relief="flat", font=self.font("Segoe UI Semibold", 12))
        self.style.map("Primary.TButton", background=[("active", COLORS["primary_dark"]), ("pressed", "#005bbf")])
        self.style.configure("TMenubutton", padding=self.pad(18, 12), background=COLORS["surface_soft"], foreground=COLORS["ink"], borderwidth=0, relief="flat", font=self.font("Segoe UI Semibold", 11))
        self.style.map("TMenubutton", background=[("active", "#e8f2ff"), ("pressed", "#dcecff")], foreground=[("active", COLORS["primary"])])
        self.style.configure("Danger.TButton", padding=self.pad(18, 12), background=COLORS["danger"], foreground=COLORS["white"], borderwidth=0, relief="flat", font=self.font("Segoe UI Semibold", 11))
        self.style.configure("Again.TButton", padding=self.pad(18, 12), background=COLORS["again_bg"], foreground=COLORS["again_fg"], borderwidth=0, relief="flat", font=self.font("Segoe UI Semibold", 11))
        self.style.configure("Review.TButton", padding=self.pad(18, 12), background=COLORS["review_bg"], foreground=COLORS["review_fg"], borderwidth=0, relief="flat", font=self.font("Segoe UI Semibold", 11))
        self.style.configure("Good.TButton", padding=self.pad(18, 12), background=COLORS["good_bg"], foreground=COLORS["good_fg"], borderwidth=0, relief="flat", font=self.font("Segoe UI Semibold", 11))
        self.style.configure("Easy.TButton", padding=self.pad(18, 12), background=COLORS["easy_bg"], foreground=COLORS["easy_fg"], borderwidth=0, relief="flat", font=self.font("Segoe UI Semibold", 11))
        self.style.configure("Nav.TButton", padding=self.pad(20, 15), background=COLORS["rail"], foreground="#d7def0", anchor="w", borderwidth=0, relief="flat", focuscolor=COLORS["rail"], font=self.font("Segoe UI", 12))
        self.style.map("Nav.TButton", background=[("active", COLORS["rail_hover"])], foreground=[("active", COLORS["white"])])
        self.style.configure("ActiveNav.TButton", padding=self.pad(20, 15), background=COLORS["primary"], foreground=COLORS["white"], anchor="w", borderwidth=0, relief="flat", focuscolor=COLORS["primary"], font=self.font("Segoe UI Semibold", 12))

    def _shell(self):
        root = ttk.Frame(self, style="Root.TFrame")
        root.pack(fill="both", expand=True)

        self.rail = ttk.Frame(root, width=self.px(276), style="Rail.TFrame")
        self.rail.pack(side="left", fill="y")
        self.rail.pack_propagate(False)

        brand = ttk.Frame(self.rail, style="Rail.TFrame")
        brand.pack(fill="x", padx=self.px(22), pady=self.pad(30, 26))
        mark_size = self.px(54)
        mark = tk.Canvas(brand, width=mark_size, height=mark_size, bg=COLORS["rail"], highlightthickness=0)
        mark.pack(side="left", padx=(0, self.px(14)))
        mark.create_oval(self.px(5), self.px(5), self.px(49), self.px(49), fill=COLORS["primary"], outline="")
        mark.create_text(mark_size // 2, mark_size // 2, text="M", fill=COLORS["white"], font=self.font("Segoe UI Semibold", 23))
        label_box = ttk.Frame(brand, style="Rail.TFrame")
        label_box.pack(side="left")
        ttk.Label(label_box, text="MemoryPal", style="RailTitle.TLabel").pack(anchor="w")
        ttk.Label(label_box, text="Memory training", style="RailText.TLabel").pack(anchor="w")

        self.nav_buttons = {}
        for key, label in [
            ("dashboard", "Dashboard"),
            ("focus", "Focus"),
            ("capture", "Capture"),
            ("review", "Review"),
            ("testing", "Test Lab"),
            ("quiz", "Quiz"),
            ("shuffle", "Repetition"),
            ("tools", "Associations"),
            ("games", "Puzzles"),
            ("library", "Library"),
        ]:
            button = ttk.Button(self.rail, text=label, style="Nav.TButton", command=lambda view=key: self.show_view(view))
            button.pack(fill="x", padx=self.px(20), pady=self.px(5))
            self.add_tooltip(button, self.nav_hint(key))
            self.nav_buttons[key] = button

        ttk.Label(self.rail, text="Data is saved locally on this PC.", style="RailText.TLabel", wraplength=self.px(230)).pack(side="bottom", padx=self.px(22), pady=self.px(26))

        self.main = ttk.Frame(root, style="Page.TFrame")
        self.main.pack(side="left", fill="both", expand=True)
        top = ttk.Frame(self.main, style="Header.TFrame", padding=self.pad(22, 18))
        top.pack(fill="x", padx=self.px(36), pady=self.pad(28, 16))
        title_box = ttk.Frame(top, style="Header.TFrame")
        title_box.pack(side="left", fill="x", expand=True)
        self.eyebrow = ttk.Label(title_box, text="Today", style="HeaderMuted.TLabel")
        self.eyebrow.pack(anchor="w")
        self.title_label = ttk.Label(title_box, text="Dashboard", style="Title.TLabel")
        self.title_label.pack(anchor="w")
        actions = ttk.Frame(top, style="Header.TFrame")
        actions.pack(side="right")
        local_chip = tk.Label(actions, text="Local save", bg=COLORS["alt"], fg=COLORS["primary"], padx=self.px(12), pady=self.px(7), font=self.font("Segoe UI Semibold", 10))
        local_chip.pack(side="left", padx=(0, self.px(10)))
        backup = ttk.Button(actions, text="Backup", command=self.export_data, style="TButton")
        backup.pack(side="left")
        self.add_tooltip(backup, "Export a local JSON backup of your MemoryPal data.")

        self.content = ttk.Frame(self.main, style="Page.TFrame")
        self.content.pack(fill="both", expand=True, padx=self.px(36), pady=(0, self.px(30)))
        self.toast_var = tk.StringVar()
        self.toast = tk.Label(self, textvariable=self.toast_var, bg=COLORS["rail"], fg=COLORS["white"], padx=self.px(20), pady=self.px(14), font=self.font("Segoe UI Semibold", 12))

    def nav_hint(self, key):
        return {
            "dashboard": "Your daily overview, progress, and next best action.",
            "focus": "A queue of due, weak, and fresh cards.",
            "capture": "Add study bits, Q/A cards, text, image, audio, and video cues.",
            "review": "Start due cards in Test Lab.",
            "testing": "Focused answer, reveal, Smart Check, and rating page.",
            "quiz": "Self-check or multiple choice practice.",
            "shuffle": "Structured repetition path such as 5, 5-4, 5-4-3, 3-2-1.",
            "tools": "Generate acronyms and mini-stories.",
            "games": "Short recall games for attention and memory.",
            "library": "Search, filter, import, export, and review saved material.",
        }.get(key, "")

    def show_view(self, view):
        titles = {
            "dashboard": ("Today", "Dashboard"),
            "focus": ("Study plan", "Focus Session"),
            "capture": ("MemoryPal", "Capture Material"),
            "review": ("MemoryPal", "Spaced Review"),
            "testing": ("Testing", "Test Lab"),
            "quiz": ("MemoryPal", "Quick Quiz"),
            "shuffle": ("MemoryPal", "Repetition Path"),
            "tools": ("MemoryPal", "Associations"),
            "games": ("MemoryPal", "Puzzles"),
            "library": ("MemoryPal", "Library"),
        }
        if self.current_view != view:
            self.save_current_draft()
        self.route_token += 1
        token = self.route_token
        self.current_view = view
        self.eyebrow.configure(text=titles[view][0])
        self.title_label.configure(text=titles[view][1])
        for key, button in self.nav_buttons.items():
            button.configure(style="ActiveNav.TButton" if key == view else "Nav.TButton")
        for child in self.content.winfo_children():
            child.destroy()
        self.render_loading_skeleton(titles[view][1], token)
        self.after(90, lambda: self.finish_show_view(view, token))

    def render_loading_skeleton(self, title, token):
        loader = ttk.Frame(self.content, style="Page.TFrame")
        loader.pack(fill="both", expand=True)
        head = self.card(loader, "WarmCard.TFrame", 16)
        head.pack(fill="x", padx=(0, 8), pady=(0, 14))
        spin = ttk.Label(head, text=f"Loading {title} |", style="WarmH2.TLabel")
        spin.pack(anchor="w")
        ttk.Label(head, text="Preparing the page layout and practice controls.", style="WarmCard.TLabel").pack(anchor="w", pady=(4, 0))
        for width in (0.72, 0.94, 0.58):
            block = tk.Frame(loader, bg=COLORS["surface"], height=self.px(76), highlightthickness=1, highlightbackground=COLORS["line"])
            block.pack(fill="x", padx=(0, 8), pady=(0, 10))
            line = tk.Frame(block, bg=COLORS["alt"], height=self.px(14))
            line.place(relx=0.03, rely=0.34, relwidth=width, height=self.px(14))
            small = tk.Frame(block, bg=COLORS["soft_line"], height=self.px(10))
            small.place(relx=0.03, rely=0.64, relwidth=max(0.28, width - 0.22), height=self.px(10))

        def tick(step=0):
            if token != self.route_token or not spin.winfo_exists():
                return
            frames = ["|", "/", "-", "\\"]
            spin.configure(text=f"Loading {title} {frames[step % len(frames)]}")
            self.after(90, lambda: tick(step + 1))

        tick()

    def finish_show_view(self, view, token):
        if token != self.route_token:
            return
        for child in self.content.winfo_children():
            child.destroy()
        getattr(self, f"view_{view}")()

    def register_draft_saver(self, view, saver):
        self.draft_savers[view] = saver

    def save_current_draft(self):
        saver = self.draft_savers.get(self.current_view)
        if not saver:
            return
        try:
            self.view_drafts[self.current_view] = saver()
        except tk.TclError:
            pass

    def toast_message(self, text):
        self.toast_var.set(text)
        self.toast.place(relx=1, rely=1, anchor="se", x=-self.px(24), y=-self.px(24))
        self.after(2600, self.toast.place_forget)

    def card(self, parent, style="Card.TFrame", padding=24):
        return ttk.Frame(parent, style=style, padding=self.px(padding))

    def text_box(self, parent, height=4, font_size=12):
        box = tk.Text(parent, height=height, wrap="word", bg=COLORS["input"], fg=COLORS["ink"], bd=0, relief="flat", highlightthickness=1, highlightbackground=COLORS["soft_line"], highlightcolor=COLORS["primary"], padx=self.px(12), pady=self.px(12), font=self.font("Segoe UI", font_size), insertbackground=COLORS["primary"])
        return box

    def answer_area(self, parent, title="Your answer", hint="Type what you remember, then check or reveal.", height=4):
        panel = self.card(parent, "AltCard.TFrame", 18)
        panel.pack(fill="x", pady=(0, self.px(10)))
        ttk.Label(panel, text=title, style="AltH2.TLabel").pack(anchor="w")
        ttk.Label(panel, text=hint, style="AltMuted.TLabel", wraplength=self.px(980)).pack(anchor="w", pady=(self.px(4), self.px(10)))
        box = self.text_box(panel, height, 12)
        box.pack(fill="x")
        return box

    def bucket_style(self, bucket):
        return {
            "Again": "Again.TButton",
            "Review": "Review.TButton",
            "Good": "Good.TButton",
            "Easy": "Easy.TButton",
        }.get(bucket, "TButton")

    def render_bucket_highlight(self, parent, bucket):
        colors = {
            "Again": (COLORS["again_bg"], COLORS["again_fg"]),
            "Review": (COLORS["review_bg"], COLORS["review_fg"]),
            "Good": (COLORS["good_bg"], COLORS["good_fg"]),
            "Easy": (COLORS["easy_bg"], COLORS["easy_fg"]),
        }
        row = tk.Frame(parent, bg=COLORS["surface"])
        row.pack(fill="x", pady=(0, self.px(12)))
        for label in ("Again", "Review", "Good", "Easy"):
            bg, fg = colors[label] if label == bucket else (COLORS["bg"], COLORS["muted"])
            badge = tk.Label(row, text=label, bg=bg, fg=fg, font=self.font("Segoe UI Semibold", 11), padx=self.px(14), pady=self.px(8))
            badge.pack(side="left", padx=(0, self.px(8)))

    def open_testing(self, card=None, return_view=None, context="study"):
        self.testing_card = card or self.current_review
        self.return_view = return_view or self.current_view or "dashboard"
        self.testing_context = context
        self.show_view("testing")

    def solid_button(self, parent, text, command, color=COLORS["primary"]):
        button = tk.Button(parent, text=text, command=command, bg=color, fg=COLORS["white"], activebackground=color, activeforeground=COLORS["white"], relief="flat", bd=0, cursor="hand2", font=self.font("Segoe UI Semibold", 11), padx=self.px(20), pady=self.px(11))
        self.add_tooltip(button, self.action_hint(text))
        button.bind("<Enter>", lambda _event: button.configure(bg=self.tint(color, -18), activebackground=self.tint(color, -18)), add="+")
        button.bind("<Leave>", lambda _event: button.configure(bg=color, activebackground=color), add="+")
        return button

    def tint(self, hex_color, amount):
        raw = hex_color.lstrip("#")
        if len(raw) != 6:
            return hex_color
        values = [int(raw[index:index + 2], 16) for index in (0, 2, 4)]
        shifted = [max(0, min(255, value + amount)) for value in values]
        return "#" + "".join(f"{value:02x}" for value in shifted)

    def hover_card(self, frame, normal=None, hover=None):
        normal = normal or COLORS["line"]
        hover = hover or COLORS["primary"]
        frame.configure(highlightthickness=1, highlightbackground=normal)
        frame.bind("<Enter>", lambda _event: frame.configure(highlightbackground=hover), add="+")
        frame.bind("<Leave>", lambda _event: frame.configure(highlightbackground=normal), add="+")
        return frame

    def button_row(self, parent, buttons, style="Card.TFrame"):
        row = ttk.Frame(parent, style=style)
        row.pack(fill="x")
        for index, (label, command, button_style) in enumerate(buttons):
            button = ttk.Button(row, text=label, command=command, style=button_style)
            button.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else self.px(8), 0))
            self.add_tooltip(button, self.action_hint(label))
            row.columnconfigure(index, weight=1, uniform="buttons")
        return row

    def cue_menu_button(self, parent, text, actions, hint=""):
        button = ttk.Menubutton(parent, text=text)
        menu = tk.Menu(button, tearoff=0, bg=COLORS["surface"], fg=COLORS["ink"], activebackground=COLORS["alt"], activeforeground=COLORS["primary"])
        for label, command in actions:
            menu.add_command(label=label, command=command)
        button.configure(menu=menu)
        self.add_tooltip(button, hint or self.action_hint(text))
        return button

    def add_tooltip(self, widget, text):
        if text:
            Tooltip(widget, text)

    def action_hint(self, label):
        return {
            "Smart Check": "Compare your response with the saved answer and highlight the suggested bucket.",
            "Reveal / Hide Answer": "Show or hide the saved answer without rating the card.",
            "Reveal Only": "Show the answer without using Smart Check.",
            "Use Smart Rating": "Schedule the card using the latest Smart Check result.",
            "Again": "Bring this card back soon.",
            "Good": "You remembered enough; schedule it a little later.",
            "Easy": "You knew it well; schedule it further out.",
            "Start in Test Lab": "Open the next due card on the focused testing page.",
            "Open in Test Lab": "Practice this card on the separate testing page.",
            "Add Q/A": "Stage one prompt-answer card from the question and answer fields.",
            "Add Item": "Add this prompt and answer as one repetition item.",
            "Split Answer": "Split the answer box into separate repetition answers.",
            "Remove Last": "Remove the most recently staged item.",
            "Make Q/A Cards": "Create flashcards from staged Q/A items and pasted Q/A lines.",
            "Split Paste": "Turn pasted notes, /n markers, and numbered lists into separate study bits.",
            "Build Path": "Create the structured repetition rounds from the material above.",
            "Add Audio": "Choose whether to import an audio file or record one.",
            "Add Video": "Choose whether to import a video file or record one.",
            "TXT": "Import a text file or save the current note as a text cue.",
            "IMG": "Attach an image cue.",
            "AUD": "Import or record an audio cue.",
            "VID": "Import or record a video cue.",
            "Use All": "Load saved captures and cards into the repetition builder.",
            "Use Captures": "Load saved capture bits into this practice mode.",
            "Use Cards": "Load saved cards into this practice mode.",
            "Self Check": "Use Test Lab to answer, reveal, and Smart Check yourself.",
            "Multiple Choice": "Pick from answer options for a faster quiz game.",
            "Play Again": "Restart this quiz mode with a fresh set of cards.",
            "Skip / Next": "Move to the next self-check card.",
            "Start": "Begin this puzzle round.",
            "Check": "Check your answer.",
            "Show Words": "Briefly show the word list, then hide it.",
            "New Pair Set": "Make a small prompt-answer matching set.",
            "Reveal Cue": "Show one side of the next pair.",
            "Make Gap": "Create a missing-item challenge.",
            "Peg List": "Map ideas onto a simple numbered peg list.",
            "Memory Palace": "Place ideas along a familiar route.",
            "Chunk Map": "Group ideas into smaller study clusters.",
            "Link Chain": "Connect each idea to the next with a tiny scene.",
            "Mini Story": "Auto-generate an ordered memory story from your ideas.",
            "Export": "Save your MemoryPal data as a JSON backup.",
            "Import": "Load a MemoryPal JSON backup.",
            "Reset": "Clear local data and restore sample cards.",
            "Open": "Open this section.",
            "Start Due Review": "Move due cards into Test Lab.",
            "Build Repetition Path": "Create a recall sequence from saved or pasted material.",
            "Practice": "Open this item in Test Lab.",
            "Back": "Return to the previous section.",
        }.get(label, "")

    def mastery_summary(self):
        total = len(self.store.cards)
        if not total:
            return 0, 0, 0
        mastered = len([card for card in self.store.cards if card.last_score >= 82 or card.last_result == "Strong match"])
        learning = len([card for card in self.store.cards if 42 <= card.last_score < 82])
        return round(mastered / total * 100), mastered, learning

    def render_status_chip(self, parent, text, color, fg=None):
        chip = tk.Label(parent, text=text, bg=color, fg=fg or COLORS["white"], font=self.font("Segoe UI Semibold", 10), padx=self.px(12), pady=self.px(6))
        chip.pack(side="left", padx=(0, self.px(8)))
        return chip

    def view_dashboard(self):
        page = ScrollFrame(self.content)
        page.pack(fill="both", expand=True)
        due = self.store.due_cards()
        weak = self.store.weak_cards()
        upcoming = self.store.upcoming_cards()
        mastery, mastered, learning = self.mastery_summary()
        if due:
            next_title, next_body, next_view, next_color = "Start today's review", f"{len(due)} card{'s' if len(due) != 1 else ''} due now.", "review", COLORS["primary"]
        elif weak:
            next_title, next_body, next_view, next_color = "Focus weak items", f"{len(weak)} item{'s' if len(weak) != 1 else ''} need a confidence pass.", "focus", COLORS["pink"]
        elif not self.store.captures:
            next_title, next_body, next_view, next_color = "Add study material", "Build your first study set from notes, media, or Q/A lines.", "capture", COLORS["orange"]
        else:
            next_title, next_body, next_view, next_color = "Try a quick quiz", "Keep recall active with a short self-check session.", "quiz", COLORS["green"]

        hero = self.hover_card(tk.Frame(page.inner, bg=COLORS["surface"], padx=self.px(28), pady=self.px(26), highlightthickness=1, highlightbackground=COLORS["line"]))
        hero.pack(fill="x", padx=(0, 8), pady=(0, 16))
        hero.columnconfigure(0, weight=0)
        hero.columnconfigure(1, weight=3)
        hero.columnconfigure(2, weight=2)
        tk.Frame(hero, bg=next_color, width=self.px(5), height=self.px(62)).grid(row=0, column=0, rowspan=2, sticky="nsw", padx=(0, self.px(16)))
        tk.Label(hero, text=next_title, bg=COLORS["surface"], fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 24)).grid(row=0, column=1, sticky="w")
        tk.Label(hero, text=next_body, bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI", 13)).grid(row=1, column=1, sticky="w", pady=(8, 0))
        quick = tk.Frame(hero, bg=COLORS["surface"])
        quick.grid(row=0, column=2, rowspan=2, sticky="nsew")
        quick.columnconfigure(0, weight=1)
        quick.columnconfigure(1, weight=1)
        self.solid_button(quick, next_title, lambda view=next_view: self.show_view(view), next_color).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        self.solid_button(quick, "Start Review", lambda: self.show_view("review"), COLORS["green"]).grid(row=1, column=0, sticky="ew", padx=(0, 8))
        self.solid_button(quick, "Add Material", lambda: self.show_view("capture"), COLORS["orange"]).grid(row=1, column=1, sticky="ew")

        progress = ttk.Frame(page.inner, style="Page.TFrame")
        progress.pack(fill="x", padx=(0, 8), pady=(0, 16))
        mastery_card = self.card(progress, "AltCard.TFrame", 20)
        mastery_card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        ttk.Label(mastery_card, text="Mastery progress", style="AltH2.TLabel").pack(anchor="w")
        ttk.Label(mastery_card, text=f"{mastery}% mastered across {len(self.store.cards)} cards", style="AltMuted.TLabel").pack(anchor="w", pady=(4, 10))
        bar = ttk.Progressbar(mastery_card, style="Horizontal.TProgressbar", maximum=100, value=mastery)
        bar.pack(fill="x", pady=(0, 10))
        chip_row = tk.Frame(mastery_card, bg=COLORS["alt"])
        chip_row.pack(fill="x")
        self.render_status_chip(chip_row, f"Due {len(due)}", COLORS["primary"])
        self.render_status_chip(chip_row, f"Learning {learning}", COLORS["orange"])
        self.render_status_chip(chip_row, f"Mastered {mastered}", COLORS["green"])

        goal_card = self.card(progress, "WarmCard.TFrame", 20)
        goal_card.grid(row=0, column=1, sticky="nsew")
        ttk.Label(goal_card, text="Today feel", style="WarmH2.TLabel").pack(anchor="w")
        ttk.Label(goal_card, text="Complete one review, one Test Lab check, or one new capture. Small sessions count.", style="WarmCard.TLabel", wraplength=self.px(420)).pack(anchor="w", pady=(4, 12))
        self.button_row(goal_card, [("Open in Test Lab", lambda: self.open_testing(return_view="dashboard", context="study"), "Primary.TButton"), ("Focus Queue", lambda: self.show_view("focus"), "TButton")], "WarmCard.TFrame")
        progress.columnconfigure(0, weight=3)
        progress.columnconfigure(1, weight=2)

        stats = ttk.Frame(page.inner, style="Page.TFrame")
        stats.pack(fill="x", padx=(0, 8))
        for index, (number, label, color) in enumerate([
            (len(self.store.due_cards()), "Due today", COLORS["primary"]),
            (len(self.store.cards), "Cards", COLORS["violet"]),
            (len(weak), "Focus", COLORS["pink"]),
            (self.store.practiced, "Practiced", COLORS["orange"]),
        ]):
            tile = self.hover_card(tk.Frame(stats, bg=COLORS["surface"], padx=self.px(20), pady=self.px(18), highlightthickness=1, highlightbackground=COLORS["line"]), hover=color)
            tile.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else 12, 0))
            tk.Frame(tile, bg=color, width=34, height=4).pack(anchor="w", pady=(0, 12))
            tk.Label(tile, text=str(number), bg=COLORS["surface"], fg=color, font=("Segoe UI Semibold", 34)).pack(anchor="w")
            tk.Label(tile, text=label, bg=COLORS["surface"], fg=COLORS["muted"], font=("Segoe UI", 12)).pack(anchor="w")
            stats.columnconfigure(index, weight=1)

        actions = ttk.Frame(page.inner, style="Page.TFrame")
        actions.pack(fill="x", padx=(0, 8), pady=(16, 0))
        cards = [
            ("Focus session", "A study-app style queue for due, weak, and new cards.", "focus", COLORS["pink"]),
            ("Capture material", "Build separate study bits with text, image, audio, and video cues.", "capture", COLORS["orange"]),
            ("Spaced review", "Smart-check recall, reveal answers, and schedule next practice.", "review", COLORS["primary"]),
            ("Repetition path", "Practice chunks backwards, then walk back to the first item.", "shuffle", COLORS["green"]),
            ("Associations", "Turn material into acronyms, story routes, and recall hooks.", "tools", COLORS["violet"]),
            ("Puzzles", "Short recall games with large, steady controls.", "games", COLORS["pink"]),
            ("Library", "Browse captures, cards, media cues, and exports.", "library", COLORS["cyan"]),
        ]
        for index, (title, body, target, color) in enumerate(cards):
            frame = self.hover_card(tk.Frame(actions, bg=COLORS["surface"], padx=self.px(24), pady=self.px(24), highlightthickness=1, highlightbackground=COLORS["line"]), hover=color)
            frame.grid(row=index // 2, column=index % 2, sticky="nsew", padx=(0 if index % 2 == 0 else 12, 0), pady=(0, 12))
            frame.columnconfigure(0, weight=1)
            tk.Frame(frame, bg=color, width=38, height=4).pack(anchor="w", pady=(0, 16))
            tk.Label(frame, text=title, bg=COLORS["surface"], fg=COLORS["ink"], font=("Segoe UI Semibold", 17)).pack(anchor="w")
            tk.Label(frame, text=body, bg=COLORS["surface"], fg=COLORS["muted"], font=("Segoe UI", 12), wraplength=460, justify="left").pack(anchor="w", pady=(8, 12))
            self.solid_button(frame, "Open", lambda view=target: self.show_view(view), color).pack(fill="x")
            actions.columnconfigure(index % 2, weight=1)

        if weak or upcoming:
            insight = self.card(page.inner, "AltCard.TFrame")
            insight.pack(fill="x", padx=(0, 8), pady=(4, 0))
            ttk.Label(insight, text="Study insight", style="AltH2.TLabel").pack(anchor="w")
            message = f"Weak/new cards: {len(weak)}. "
            message += f"Next scheduled card: {upcoming[0].next_review}." if upcoming else "No future cards are scheduled yet."
            ttk.Label(insight, text=message, style="AltCard.TLabel", wraplength=1040).pack(anchor="w", pady=(6, 0))

    def view_focus(self):
        page = ScrollFrame(self.content)
        page.pack(fill="both", expand=True)
        due = self.store.due_cards()
        weak = [card for card in self.store.weak_cards() if card not in due]
        new_cards = [card for card in self.store.cards if card.repetitions == 0 and card not in due and card not in weak]
        hero = self.card(page.inner, "AltCard.TFrame")
        hero.pack(fill="x", padx=(0, 8), pady=(0, 12))
        ttk.Label(hero, text="Next best study queue", style="AltH2.TLabel").pack(anchor="w")
        ttk.Label(hero, text=f"Due: {len(due)} | Weak/new: {len(weak)} | Fresh: {len(new_cards)}", style="AltCard.TLabel").pack(anchor="w", pady=(6, 12))
        self.button_row(hero, [("Start Due Review", lambda: self.show_view("review"), "Primary.TButton"), ("Build Repetition Path", lambda: self.show_view("shuffle"), "TButton"), ("Add Material", lambda: self.show_view("capture"), "TButton")], "AltCard.TFrame")

        def practice(card):
            card.next_review = today_iso()
            self.store.save()
            self.current_review = card
            self.open_testing(card, "focus", "review")

        sections = [("Due now", due), ("Needs focus", weak[:8]), ("Fresh cards", new_cards[:8])]
        for title, cards in sections:
            section = self.card(page.inner)
            section.pack(fill="x", padx=(0, 8), pady=(0, 10))
            header = ttk.Frame(section, style="Card.TFrame")
            header.pack(fill="x")
            ttk.Label(header, text=title, style="H2.TLabel").pack(side="left", anchor="w")
            self.render_status_chip(header, f"{len(cards)} item{'s' if len(cards) != 1 else ''}", COLORS["alt"], COLORS["primary"])
            if not cards:
                ttk.Label(section, text="Nothing in this queue.", style="CardMuted.TLabel").pack(anchor="w", pady=(6, 0))
                continue
            for card in cards:
                row = ttk.Frame(section, style="Card.TFrame")
                row.pack(fill="x", pady=(8, 0))
                ttk.Label(row, text=f"{card.front}  |  {card.last_result} {card.last_score}%", style="Card.TLabel", wraplength=830).grid(row=0, column=0, sticky="w")
                practice_button = ttk.Button(row, text="Practice", command=lambda value=card: practice(value))
                practice_button.grid(row=0, column=1, sticky="e", padx=(10, 0))
                self.add_tooltip(practice_button, self.action_hint("Practice"))
                row.columnconfigure(0, weight=1)

    def attach_media(self, kind, labels, text_target=None):
        filetypes = {
            "text_file": [("Text notes", "*.txt *.md *.csv")],
            "image": [("Images", "*.png *.jpg *.jpeg *.gif *.bmp *.webp")],
            "audio": [("Audio", "*.mp3 *.wav *.m4a *.ogg *.webm *.aac")],
            "video": [("Video", "*.mp4 *.mov *.avi *.mkv *.webm *.wmv")],
        }.get(kind, [("All files", "*.*")])
        label_name = "text" if kind == "text_file" else kind
        selected = filedialog.askopenfilename(title=f"Choose {label_name}", filetypes=filetypes + [("All files", "*.*")])
        if not selected:
            return
        ATTACHMENT_DIR.mkdir(parents=True, exist_ok=True)
        source = Path(selected)
        target = ATTACHMENT_DIR / f"{uuid4().hex}{source.suffix.lower()}"
        shutil.copy2(source, target)
        self.pending_media[kind] = str(target)
        labels[kind].configure(text=target.name)
        if kind == "text_file" and text_target is not None:
            try:
                text = source.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                text = source.read_text(encoding="utf-8", errors="ignore")
            except OSError as exc:
                self.toast_message(f"Text imported as a file, but could not be read: {exc}")
                return
            text_target.delete("1.0", "end")
            text_target.insert("1.0", text)
            self.toast_message("Text file imported into the study bit box.")

    def record_text_note(self, labels, text_target):
        text = normalize_space(text_target.get("1.0", "end"))
        if not text:
            self.toast_message("Type or dictate text first, then save it as a note.")
            return
        ATTACHMENT_DIR.mkdir(parents=True, exist_ok=True)
        target = ATTACHMENT_DIR / f"text-note-{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
        target.write_text(text + "\n", encoding="utf-8")
        self.pending_media["text_file"] = str(target)
        labels["text_file"].configure(text=target.name)
        self.toast_message("Text note saved as an attached file.")

    def record_audio(self, labels):
        seconds = simpledialog.askinteger("Record Audio", "Seconds to record:", initialvalue=10, minvalue=1, maxvalue=120)
        if not seconds:
            return
        try:
            import wave
            import sounddevice as sd
        except ImportError:
            messagebox.showinfo(
                "Audio recorder unavailable",
                "Import an audio file for now, or install sounddevice for desktop recording. The planned mobile version should use the phone's native recorder.",
            )
            return
        ATTACHMENT_DIR.mkdir(parents=True, exist_ok=True)
        target = ATTACHMENT_DIR / f"audio-recording-{datetime.now().strftime('%Y%m%d-%H%M%S')}.wav"
        samplerate = 44100
        try:
            data = sd.rec(int(seconds * samplerate), samplerate=samplerate, channels=1, dtype="int16")
            sd.wait()
            with wave.open(str(target), "wb") as handle:
                handle.setnchannels(1)
                handle.setsampwidth(2)
                handle.setframerate(samplerate)
                handle.writeframes(data.tobytes())
        except Exception as exc:
            messagebox.showerror("Audio recording failed", str(exc))
            return
        self.pending_media["audio"] = str(target)
        labels["audio"].configure(text=target.name)
        self.toast_message("Audio recording attached.")

    def record_video(self, labels):
        seconds = simpledialog.askinteger("Record Video", "Seconds to record:", initialvalue=8, minvalue=1, maxvalue=60)
        if not seconds:
            return
        try:
            import cv2
        except ImportError:
            messagebox.showinfo(
                "Video recorder unavailable",
                "Import a video file for now, or install opencv-python for desktop webcam recording. The planned mobile version should use the phone's camera recorder.",
            )
            return
        ATTACHMENT_DIR.mkdir(parents=True, exist_ok=True)
        target = ATTACHMENT_DIR / f"video-recording-{datetime.now().strftime('%Y%m%d-%H%M%S')}.avi"
        camera = cv2.VideoCapture(0)
        if not camera.isOpened():
            messagebox.showerror("Video recording failed", "No webcam was found.")
            return
        width = int(camera.get(cv2.CAP_PROP_FRAME_WIDTH) or 640)
        height = int(camera.get(cv2.CAP_PROP_FRAME_HEIGHT) or 480)
        writer = cv2.VideoWriter(str(target), cv2.VideoWriter_fourcc(*"XVID"), 20.0, (width, height))
        deadline = datetime.now() + timedelta(seconds=seconds)
        try:
            while datetime.now() < deadline:
                ok, frame = camera.read()
                if not ok:
                    break
                writer.write(frame)
        finally:
            camera.release()
            writer.release()
        self.pending_media["video"] = str(target)
        labels["video"].configure(text=target.name)
        self.toast_message("Video recording attached.")

    def view_capture(self):
        draft = self.view_drafts.get("capture", {})
        page = ScrollFrame(self.content)
        page.pack(fill="both", expand=True)
        wrapper = ttk.Frame(page.inner, style="Page.TFrame")
        wrapper.pack(fill="both", expand=True, padx=(0, 8))
        form = self.card(wrapper)
        form.pack(side="left", fill="both", expand=True, padx=(0, 14))
        side = self.card(wrapper, "AltCard.TFrame")
        side.pack(side="left", fill="both", expand=True)

        ttk.Label(form, text="Study set builder", style="H2.TLabel").pack(anchor="w")
        ttk.Label(form, text="Add each fact, reminder, or idea as its own bit.", style="CardMuted.TLabel").pack(anchor="w", pady=(6, 18))
        cue = self.card(form, "WarmCard.TFrame", 14)
        cue.pack(fill="x", pady=(0, 14))
        ttk.Label(cue, text="Build one clear item at a time", style="WarmH2.TLabel").pack(anchor="w")
        ttk.Label(cue, text="Use the separate question and answer fields for cards, or add short study bits below. Media buttons attach cues to the whole set.", style="WarmCard.TLabel", wraplength=680).pack(anchor="w", pady=(4, 0))
        ttk.Label(form, text="Title", style="CardMuted.TLabel").pack(anchor="w")
        title = ttk.Entry(form)
        title.insert(0, draft.get("title", "Chapter 3 key terms"))
        title.pack(fill="x", pady=(4, 12))
        ttk.Label(form, text="Card prompt", style="CardMuted.TLabel").pack(anchor="w")
        prompt = ttk.Entry(form)
        prompt.insert(0, draft.get("prompt", "What should I recall from bit {n}?"))
        prompt.pack(fill="x", pady=(4, 12))

        qa_items = [dict(item) for item in draft.get("qa_items", [])]
        qa_panel = self.card(form, "AltCard.TFrame", 18)
        qa_panel.pack(fill="x", pady=(0, 14))
        ttk.Label(qa_panel, text="Question and answer card", style="AltH2.TLabel").pack(anchor="w")
        ttk.Label(qa_panel, text="Use this when you already know the exact prompt and answer.", style="AltMuted.TLabel", wraplength=640).pack(anchor="w", pady=(4, 10))
        ttk.Label(qa_panel, text="Question / title", style="AltMuted.TLabel").pack(anchor="w")
        qa_prompt = ttk.Entry(qa_panel)
        qa_prompt.insert(0, draft.get("qa_prompt", ""))
        qa_prompt.pack(fill="x", pady=(4, 10))
        qa_has_answer = tk.BooleanVar(value=draft.get("qa_has_answer", True))
        answer_toggle = ttk.Checkbutton(qa_panel, text="This question has a saved answer", variable=qa_has_answer)
        answer_toggle.pack(anchor="w", pady=(0, 8))
        qa_answer_frame = ttk.Frame(qa_panel, style="AltCard.TFrame")
        qa_answer_frame.pack(fill="x")
        ttk.Label(qa_answer_frame, text="Answer", style="AltMuted.TLabel").pack(anchor="w")
        qa_answer = self.text_box(qa_answer_frame, 3, 12)
        qa_answer.insert("1.0", draft.get("qa_answer", ""))
        qa_answer.pack(fill="x", pady=(4, 10))
        qa_list = tk.Frame(qa_panel, bg=COLORS["alt"])
        qa_list.pack(fill="x", pady=(0, 10))

        def update_answer_visibility():
            if qa_has_answer.get():
                qa_answer_frame.pack(fill="x")
            else:
                qa_answer_frame.pack_forget()
                qa_answer.delete("1.0", "end")

        answer_toggle.configure(command=update_answer_visibility)

        def refresh_qa():
            for child in qa_list.winfo_children():
                child.destroy()
            if not qa_items:
                tk.Label(qa_list, text="No Q/A cards staged yet.", bg=COLORS["alt"], fg=COLORS["muted"], font=self.font("Segoe UI", 11)).pack(anchor="w")
                return
            for index, item in enumerate(qa_items, 1):
                answer_text = item["answer"] if item["answer"] else "self-check only"
                text = f"{index}. {item['prompt']} -> {answer_text}"
                tk.Label(qa_list, text=text, bg=COLORS["alt"], fg=COLORS["ink"], font=self.font("Segoe UI", 11), wraplength=self.px(620), justify="left").pack(anchor="w", pady=(0, self.px(5)))

        def add_qa():
            item = {
                "prompt": normalize_space(qa_prompt.get()),
                "answer": normalize_space(qa_answer.get("1.0", "end")) if qa_has_answer.get() else "",
            }
            if not item["prompt"]:
                self.toast_message("Add a question first.")
                return
            if qa_has_answer.get() and not item["answer"]:
                self.toast_message("Add an answer or turn off the answer checkbox.")
                return
            qa_items.append(item)
            qa_prompt.delete(0, "end")
            qa_answer.delete("1.0", "end")
            qa_has_answer.set(True)
            update_answer_visibility()
            refresh_qa()

        def remove_qa():
            if qa_items:
                qa_items.pop()
                refresh_qa()

        self.button_row(qa_panel, [("Add Q/A", add_qa, "Primary.TButton"), ("Remove Last Q/A", remove_qa, "TButton")], "AltCard.TFrame")
        update_answer_visibility()
        refresh_qa()

        ttk.Label(form, text="Study bit", style="CardMuted.TLabel").pack(anchor="w")
        entry = self.text_box(form, 4, 13)
        entry.insert("1.0", draft.get("entry", ""))
        entry.pack(fill="x", pady=(4, 10))
        ttk.Label(form, text="Tip: paste lines like `Question => Answer` here, then use Split Paste or Make Q/A Cards.", style="CardMuted.TLabel", wraplength=680).pack(anchor="w", pady=(0, 10))
        chunks = list(draft.get("chunks", []))
        count_label = ttk.Label(form, text="0 study bits added", style="CardMuted.TLabel")
        count_label.pack(anchor="w")
        chunk_panel = tk.Frame(form, bg=COLORS["surface"])
        chunk_panel.pack(fill="both", expand=True, pady=(8, 12))

        def refresh():
            for child in chunk_panel.winfo_children():
                child.destroy()
            if not chunks:
                tk.Label(chunk_panel, text="Add a bit or split a pasted list to build your study set.", bg=COLORS["surface"], fg=COLORS["muted"], font=("Segoe UI", 12), wraplength=520, justify="left").pack(anchor="w")
            for index, chunk in enumerate(chunks, 1):
                row = tk.Frame(chunk_panel, bg=COLORS["alt"], padx=14, pady=12)
                row.pack(fill="x", pady=(0, 8))
                tk.Label(row, text=f"{index}.", bg=COLORS["alt"], fg=COLORS["primary"], font=("Segoe UI Semibold", 12)).pack(side="left", anchor="n", padx=(0, 8))
                tk.Label(row, text=chunk, bg=COLORS["alt"], fg=COLORS["ink"], wraplength=520, justify="left", font=("Segoe UI", 12)).pack(side="left", fill="x", expand=True)
            count_label.configure(text=f"{len(chunks)} study bit{'s' if len(chunks) != 1 else ''} added")

        def add_bit():
            raw = entry.get("1.0", "end").strip()
            if not raw:
                self.toast_message("Type a study bit first.")
                return
            chunks.append(normalize_space(raw))
            entry.delete("1.0", "end")
            refresh()

        def split_paste():
            bits = split_study_bits(entry.get("1.0", "end"))
            if not bits:
                self.toast_message("Paste a few lines or facts first.")
                return
            chunks.extend(normalize_space(bit) for bit in bits)
            entry.delete("1.0", "end")
            refresh()

        def remove_last():
            if chunks:
                chunks.pop()
                refresh()

        self.button_row(form, [("Add Bit", add_bit, "Primary.TButton"), ("Split Paste", split_paste, "TButton"), ("Remove Last", remove_last, "TButton")])
        ttk.Label(form, text="Attach cues", style="CardMuted.TLabel").pack(anchor="w", pady=(16, 6))
        self.pending_media = dict(draft.get("pending_media", {"text_file": "", "image": "", "audio": "", "video": ""}))
        labels = {
            kind: ttk.Label(side, text=(Path(self.pending_media.get(kind, "")).name if self.pending_media.get(kind) else f"No {'text' if kind == 'text_file' else kind} selected"), style="AltCard.TLabel", wraplength=500)
            for kind in ("text_file", "image", "audio", "video")
        }
        cue_bar = ttk.Frame(form, style="Card.TFrame")
        cue_bar.pack(fill="x")
        cue_actions = [
            ("TXT", [("Import text file", lambda: self.attach_media("text_file", labels, entry)), ("Save current note", lambda: self.record_text_note(labels, entry))]),
            ("IMG", [("Import image", lambda: self.attach_media("image", labels))]),
            ("AUD", [("Import audio", lambda: self.attach_media("audio", labels)), ("Record audio", lambda: self.record_audio(labels))]),
            ("VID", [("Import video", lambda: self.attach_media("video", labels)), ("Record video", lambda: self.record_video(labels))]),
        ]
        for index, (cue_label, actions) in enumerate(cue_actions):
            menu_button = self.cue_menu_button(cue_bar, cue_label, actions)
            menu_button.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else self.px(8), 0))
            cue_bar.columnconfigure(index, weight=1, uniform="cue")
        ttk.Label(form, text="Use the cue buttons to attach files or start recordings without adding more controls to the page.", style="CardMuted.TLabel", wraplength=680).pack(anchor="w", pady=(6, 0))

        def save(make_cards=False, qa_cards=False):
            title_text = normalize_space(title.get()) or "Captured memory material"
            draft = entry.get("1.0", "end").strip()
            final_chunks = list(chunks)
            if draft:
                final_chunks.extend(normalize_space(bit) for bit in split_study_bits(draft))
            staged_qa = list(qa_items)
            parsed_qa = parse_prompt_answer_lines("\n".join(final_chunks))
            qa_lines = [f"{item['prompt']} => {item['answer'] or SELF_CHECK_ANSWER}" for item in staged_qa]
            capture_chunks = final_chunks + qa_lines
            if not capture_chunks and not any(self.pending_media.values()):
                self.toast_message("Add a study bit or media cue first.")
                return
            capture = Capture(title=title_text, notes="\n".join(capture_chunks), chunks=capture_chunks, **self.pending_media)
            self.store.add_capture(capture)
            created = 0
            if qa_cards and (staged_qa or parsed_qa):
                for index, item in enumerate(staged_qa + parsed_qa, 1):
                    answer_text = item["answer"] or SELF_CHECK_ANSWER
                    association = "Prompt-answer card created from separate Q/A fields." if item in staged_qa else "Prompt-answer card created from pasted study lines."
                    self.store.add_card(Card(deck=title_text, front=item["prompt"], back=answer_text, pathway=f"Capture > {title_text} > Q/A {index}", association=association, **self.pending_media))
                    created += 1
            elif make_cards:
                prompt_text = normalize_space(prompt.get()) or "What should I recall from bit {n}?"
                card_chunks = capture_chunks or [f"Use the attached media to recall {title_text}."]
                for index, chunk in enumerate(card_chunks, 1):
                    front = prompt_text.replace("{n}", str(index)).replace("{total}", str(len(card_chunks)))
                    if front == prompt_text and len(card_chunks) > 1:
                        front = f"{front} ({index}/{len(card_chunks)})"
                    self.store.add_card(Card(deck="Captured Material", front=front, back=chunk, pathway=f"Capture > {title_text} > Bit {index}", association="Use attached media as a memory cue.", **self.pending_media))
                    created += 1
            chunks.clear()
            qa_items.clear()
            entry.delete("1.0", "end")
            qa_prompt.delete(0, "end")
            qa_answer.delete("1.0", "end")
            qa_has_answer.set(True)
            update_answer_visibility()
            refresh()
            refresh_qa()
            self.pending_media = {"text_file": "", "image": "", "audio": "", "video": ""}
            self.view_drafts["capture"] = {}
            for kind, label in labels.items():
                label.configure(text=f"No {'text' if kind == 'text_file' else kind} selected")
            self.toast_message(f"Capture saved and {created} cards created." if make_cards else "Capture saved.")

        ttk.Frame(form, style="Card.TFrame").pack(pady=(10, 0))
        self.button_row(form, [("Save Capture", lambda: save(False), "Primary.TButton"), ("Make Cards", lambda: save(True), "TButton"), ("Make Q/A Cards", lambda: save(True, True), "TButton")])

        ttk.Label(side, text="Chunk-based capture", style="AltH2.TLabel").pack(anchor="w")
        ttk.Label(side, text="Each bit becomes its own reusable practice item.", style="AltCard.TLabel", wraplength=500).pack(anchor="w", pady=(10, 22))
        for label in labels.values():
            label.pack(anchor="w", pady=(0, 10))
        refresh()
        self.register_draft_saver("capture", lambda: {
            "title": title.get(),
            "prompt": prompt.get(),
            "qa_prompt": qa_prompt.get(),
            "qa_answer": qa_answer.get("1.0", "end").strip(),
            "qa_has_answer": qa_has_answer.get(),
            "qa_items": [dict(item) for item in qa_items],
            "entry": entry.get("1.0", "end").strip(),
            "chunks": list(chunks),
            "pending_media": dict(self.pending_media),
        })

    def media_summary(self, item):
        parts = []
        names = {"text_file": "Text", "image": "Image", "audio": "Audio", "video": "Video"}
        for kind in ("text_file", "image", "audio", "video"):
            path = getattr(item, kind, "")
            if path:
                parts.append(f"{names[kind]}: {Path(path).name}")
        return " | ".join(parts)

    def open_media(self, path):
        if not path or not Path(path).exists():
            self.toast_message("Media file was not found.")
            return
        try:
            import os
            os.startfile(path)
        except OSError as exc:
            messagebox.showerror("Could not open media", str(exc))

    def image_photo(self, path, max_width=620, max_height=360):
        source = Path(path)
        if not source.exists():
            return None
        try:
            from PIL import Image, ImageTk
            image = Image.open(source)
            image.thumbnail((self.px(max_width), self.px(max_height)))
            return ImageTk.PhotoImage(image)
        except Exception:
            try:
                photo = tk.PhotoImage(file=str(source))
            except tk.TclError:
                return None
            return photo

    def render_media_controls(self, parent, item):
        media = [(kind, getattr(item, kind, "")) for kind in ("text_file", "image", "audio", "video") if getattr(item, kind, "")]
        if not media:
            return
        panel = self.card(parent, "AltCard.TFrame", 16)
        panel.pack(fill="x", pady=(8, 12))
        ttk.Label(panel, text="Attached cues", style="AltH2.TLabel").pack(anchor="w")
        ttk.Label(panel, text=self.media_summary(item), style="AltMuted.TLabel", wraplength=1040).pack(anchor="w", pady=(4, 10))
        action_row = ttk.Frame(panel, style="AltCard.TFrame")
        action_row.pack(fill="x")
        for index, (kind, path) in enumerate(media):
            label = "Text" if kind == "text_file" else kind.title()
            action = "Read" if kind == "text_file" else "Display" if kind == "image" else "Play"
            button = ttk.Button(action_row, text=f"{action} {label}", command=lambda value=path: self.open_media(value))
            button.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 8, 0))
            self.add_tooltip(button, f"{action} the attached {label.lower()} cue.")
            action_row.columnconfigure(index, weight=1)

        for kind, path in media:
            source = Path(path)
            if kind == "text_file" and source.exists():
                try:
                    preview = source.read_text(encoding="utf-8", errors="ignore").strip()
                except OSError:
                    preview = ""
                if preview:
                    text_panel = self.card(panel, "WarmCard.TFrame", 12)
                    text_panel.pack(fill="x", pady=(10, 0))
                    ttk.Label(text_panel, text="Text cue preview", style="WarmH2.TLabel").pack(anchor="w")
                    ttk.Label(text_panel, text=preview[:900] + ("..." if len(preview) > 900 else ""), style="WarmCard.TLabel", wraplength=1000).pack(anchor="w", pady=(4, 0))
            elif kind == "image":
                photo = self.image_photo(path)
                if photo:
                    self.media_images.append(photo)
                    holder = tk.Frame(panel, bg=COLORS["alt"])
                    holder.pack(fill="x", pady=(10, 0))
                    tk.Label(holder, image=photo, bg=COLORS["alt"]).pack(anchor="w")
            elif kind in ("audio", "video"):
                hint = "Audio/video plays in your default desktop player so the app stays lightweight."
                ttk.Label(panel, text=hint, style="AltMuted.TLabel", wraplength=1040).pack(anchor="w", pady=(8, 0))

    def view_review(self):
        page = ScrollFrame(self.content)
        page.pack(fill="both", expand=True)
        host = self.card(page.inner)
        host.pack(fill="both", expand=True, padx=(0, 8))
        due = self.store.due_cards()
        if not due:
            ttk.Label(host, text="No cards due today", style="H2.TLabel").pack(anchor="w")
            ttk.Label(host, text="Capture new material or browse your library.", style="Card.TLabel").pack(anchor="w", pady=(8, 0))
            return
        self.current_review = due[0]
        ttk.Label(host, text=f"{len(due)} due card{'s' if len(due) != 1 else ''}", style="H2.TLabel").pack(anchor="w")
        ttk.Label(host, text="Review now opens in Test Lab so the answer, reveal, Smart Check, and rating stay on one focused page.", style="CardMuted.TLabel", wraplength=1040).pack(anchor="w", pady=(8, 16))
        preview = self.card(host, "AltCard.TFrame", 18)
        preview.pack(fill="x", pady=(0, 12))
        ttk.Label(preview, text="Next card", style="AltH2.TLabel").pack(anchor="w")
        ttk.Label(preview, text=self.current_review.front, style="AltCard.TLabel", wraplength=1000).pack(anchor="w", pady=(6, 0))
        self.button_row(host, [("Start in Test Lab", lambda: self.open_testing(self.current_review, "review", "review"), "Primary.TButton"), ("Focus Queue", lambda: self.show_view("focus"), "TButton"), ("Library", lambda: self.show_view("library"), "TButton")])

    def render_review(self, host, show_answer=False, assessment=None, response_text=""):
        for child in host.winfo_children():
            child.destroy()
        due = self.store.due_cards()
        if not due:
            ttk.Label(host, text="No cards due today", style="H2.TLabel").pack(anchor="w")
            ttk.Label(host, text="Capture new material or browse your library.", style="Card.TLabel").pack(anchor="w", pady=(8, 0))
            return
        if not self.current_review or self.current_review not in due:
            self.current_review = due[0]
        card = self.current_review
        ttk.Label(host, text=f"{card.deck} | Next review: {card.next_review}", style="CardMuted.TLabel").pack(anchor="w")
        ttk.Label(host, text=card.front, style="H2.TLabel", wraplength=1040).pack(anchor="w", pady=(10, 16))
        self.render_media_controls(host, card)
        if show_answer:
            if response_text:
                ttk.Label(host, text=f"Your response: {response_text}", style="CardMuted.TLabel", wraplength=1040).pack(anchor="w", pady=(0, 10))
            if assessment:
                ttk.Label(host, text=f"Smart check: {assessment['label']} | {assessment['score']}% | Bucket: {assessment['bucket']} | Reps: {assessment['repetitions']}", style="H2.TLabel", wraplength=1040).pack(anchor="w", pady=(0, 8))
                ttk.Label(host, text=assessment["detail"], style="CardMuted.TLabel", wraplength=1040).pack(anchor="w", pady=(0, 12))
                self.render_bucket_highlight(host, assessment["bucket"])
            ttk.Label(host, text=card.back, style="Card.TLabel", wraplength=1040).pack(anchor="w", pady=(0, 14))
            ttk.Label(host, text=f"Path: {card.pathway or 'Not set'}", style="CardMuted.TLabel").pack(anchor="w")
            ttk.Label(host, text=f"Hook: {card.association or 'Not set'}", style="CardMuted.TLabel").pack(anchor="w", pady=(0, 16))
            row = ttk.Frame(host, style="Card.TFrame")
            row.pack(fill="x")
            if assessment:
                ttk.Button(row, text=f"Use Smart Rating ({assessment['bucket']})", style="Primary.TButton", command=lambda: self.rate_review(host, assessment["quality"], assessment)).grid(row=0, column=0, sticky="ew", padx=(0, 8))
                row.columnconfigure(0, weight=2)
                offset = 1
            else:
                offset = 0
            for index, (label, quality) in enumerate([("Again", 1), ("Good", 4), ("Easy", 5)]):
                style = self.bucket_style(label) if assessment and assessment["bucket"] == label else "TButton"
                ttk.Button(row, text=label, style=style, command=lambda value=quality: self.rate_review(host, value)).grid(row=0, column=index + offset, sticky="ew", padx=(0 if index == 0 and not offset else 8, 0))
                row.columnconfigure(index + offset, weight=1)
            ttk.Button(row, text="Open Test Page", command=lambda: self.open_testing(card, "review", "review")).grid(row=0, column=offset + 3, sticky="ew", padx=(8, 0))
            row.columnconfigure(offset + 3, weight=1)
            return

        response = self.answer_area(host, "Your recall", "Type your answer, transcript, caption, or media description.", 5)

        def smart_check():
            context = " ".join(part for part in [card.front, card.pathway, card.association, self.media_summary(card)] if part)
            result = answer_assessment(response.get("1.0", "end").strip(), card.back, context)
            self.render_review(host, True, result, response.get("1.0", "end").strip())

        self.button_row(host, [("Smart Check", smart_check, "Primary.TButton"), ("Reveal Only", lambda: self.render_review(host, True), "TButton"), ("Open Test Page", lambda: self.open_testing(card, "review", "review"), "TButton")])

    def rate_review(self, host, quality, assessment=None):
        self.store.schedule(self.current_review, quality, assessment)
        self.current_review = None
        self.toast_message("Review scheduled.")
        self.render_review(host)

    def view_testing(self):
        draft = self.view_drafts.get("testing", {})
        page = ScrollFrame(self.content)
        page.pack(fill="both", expand=True)
        card = self.testing_card or (self.store.due_cards()[0] if self.store.due_cards() else self.store.cards[0] if self.store.cards else None)
        panel = self.card(page.inner)
        panel.pack(fill="both", expand=True, padx=(0, 8))
        ttk.Label(panel, text="Separate testing page", style="H2.TLabel").pack(anchor="w")
        ttk.Label(panel, text="Use this page for focused testing, then return to where you came from.", style="CardMuted.TLabel", wraplength=1040).pack(anchor="w", pady=(6, 16))
        if not card:
            ttk.Label(panel, text="Add cards first.", style="Card.TLabel").pack(anchor="w")
            ttk.Button(panel, text="Back", command=lambda: self.show_view(self.return_view)).pack(fill="x", pady=(16, 0))
            return
        self.testing_card = card
        guide = self.card(panel, "WarmCard.TFrame", 16)
        guide.pack(fill="x", pady=(0, self.px(12)))
        ttk.Label(guide, text="Answer first, then check", style="WarmH2.TLabel").pack(anchor="w")
        ttk.Label(guide, text="Smart Check compares your response in context and suggests a review bucket. Reveal is always available if this is a self-check card.", style="WarmCard.TLabel", wraplength=1040).pack(anchor="w", pady=(4, 0))
        ttk.Label(panel, text=card.front, style="H2.TLabel", wraplength=1040).pack(anchor="w", pady=(0, 14))
        self.render_media_controls(panel, card)
        response = self.answer_area(panel, "Your test answer", "Answer here without leaving the testing page.", 5)
        if draft.get("card_id") == card.id and draft.get("context") == self.testing_context:
            response.insert("1.0", draft.get("response", ""))
        result = ttk.Label(panel, text="Smart Check will highlight the suggested bucket.", style="CardMuted.TLabel", wraplength=1040)
        result.pack(anchor="w", pady=(0, 10))
        bucket_holder = ttk.Frame(panel, style="Card.TFrame")
        bucket_holder.pack(fill="x")
        answer_holder = ttk.Frame(panel, style="Card.TFrame")
        answer_visible = {"value": False}
        latest_assessment = {"value": None}

        def smart_check():
            for child in bucket_holder.winfo_children():
                child.destroy()
            checked = answer_assessment(response.get("1.0", "end").strip(), card.back, card.front)
            latest_assessment["value"] = checked
            result.configure(text=f"{checked['label']} | {checked['score']}% | Bucket: {checked['bucket']} | Reps: {checked['repetitions']} | {checked['detail']}")
            self.render_bucket_highlight(bucket_holder, checked["bucket"])

        def reveal():
            if answer_visible["value"]:
                answer_holder.pack_forget()
                answer_visible["value"] = False
                return
            for child in answer_holder.winfo_children():
                child.destroy()
            ttk.Label(answer_holder, text="Saved answer", style="CardMuted.TLabel").pack(anchor="w")
            ttk.Label(answer_holder, text=card.back, style="Card.TLabel", wraplength=1040).pack(anchor="w", pady=(4, 0))
            answer_holder.pack(fill="x", pady=(8, 0))
            answer_visible["value"] = True

        def schedule_from_lab(quality, assessment=None):
            self.store.schedule(card, quality, assessment)
            self.toast_message("Review scheduled.")
            self.testing_card = None
            self.current_review = None
            self.view_drafts["testing"] = {}
            if self.testing_context == "review" and self.store.due_cards():
                next_card = self.store.due_cards()[0]
                self.open_testing(next_card, self.return_view, "review")
            else:
                self.show_view(self.return_view)

        def smart_rating():
            assessment = latest_assessment["value"]
            if not assessment:
                self.toast_message("Smart Check first, then use Smart Rating.")
                return
            schedule_from_lab(assessment["quality"], assessment)

        actions = ttk.Frame(panel, style="Card.TFrame")
        actions.pack(fill="x", pady=(self.px(10), 0))
        action_defs = [
            ("Smart Check", "Primary.TButton", smart_check),
            ("Reveal / Hide Answer", "TButton", reveal),
            ("Use Smart Rating", "TButton", smart_rating),
            ("Back", "TButton", lambda: self.show_view(self.return_view)),
        ]
        for column, (label, style, command) in enumerate(action_defs):
            button = ttk.Button(actions, text=label, style=style, command=command)
            button.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else self.px(8), 0))
            self.add_tooltip(button, self.action_hint(label))
        for column in range(4):
            actions.columnconfigure(column, weight=1)

        if self.testing_context == "review":
            rating = ttk.Frame(panel, style="Card.TFrame")
            rating.pack(fill="x", pady=(self.px(10), 0))
            for index, (label, quality) in enumerate([("Again", 1), ("Good", 4), ("Easy", 5)]):
                button = ttk.Button(rating, text=label, style=self.bucket_style(label), command=lambda value=quality: schedule_from_lab(value))
                button.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else self.px(8), 0))
                self.add_tooltip(button, self.action_hint(label))
                rating.columnconfigure(index, weight=1)
        self.register_draft_saver("testing", lambda: {
            "card_id": card.id,
            "context": self.testing_context,
            "response": response.get("1.0", "end").strip(),
        })

    def view_quiz(self):
        draft = self.view_drafts.get("quiz", {})
        page = ScrollFrame(self.content)
        page.pack(fill="both", expand=True)
        host = self.card(page.inner)
        host.pack(fill="both", expand=True, padx=(0, 8))
        if draft.get("card_ids"):
            card_by_id = {card.id: card for card in self.store.cards}
            self.quiz_cards = [card_by_id[card_id] for card_id in draft["card_ids"] if card_id in card_by_id]
        else:
            self.quiz_cards = random.sample(self.store.cards, min(5, len(self.store.cards))) if self.store.cards else []
        self.quiz_round = min(int(draft.get("round", 0)), len(self.quiz_cards))
        self.quiz_score = int(draft.get("score", 0))
        self.quiz_mode = draft.get("mode", self.quiz_mode)
        self.render_quiz(host)

    def render_quiz(self, host):
        for child in host.winfo_children():
            child.destroy()
        if not self.store.cards:
            ttk.Label(host, text="Add cards first", style="H2.TLabel").pack(anchor="w")
            return
        self.register_draft_saver("quiz", lambda: {
            "card_ids": [card.id for card in self.quiz_cards],
            "round": self.quiz_round,
            "score": self.quiz_score,
            "mode": self.quiz_mode,
        })
        guide = self.card(host, "WarmCard.TFrame", 14)
        guide.pack(fill="x", pady=(0, 12))
        ttk.Label(guide, text="Choose how you want to check yourself", style="WarmH2.TLabel").pack(anchor="w")
        ttk.Label(guide, text="Self Check opens Test Lab for typed recall. Multiple Choice is faster when you want a quick confidence check.", style="WarmCard.TLabel", wraplength=1040).pack(anchor="w", pady=(4, 0))
        mode = ttk.Frame(host, style="Card.TFrame")
        mode.pack(fill="x", pady=(0, 16))
        self_check = ttk.Button(mode, text="Self Check", style="Primary.TButton" if self.quiz_mode == "self" else "TButton", command=lambda: self.set_quiz_mode(host, "self"))
        self_check.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        choices_button = ttk.Button(mode, text="Multiple Choice", style="Primary.TButton" if self.quiz_mode == "choices" else "TButton", command=lambda: self.set_quiz_mode(host, "choices"))
        choices_button.grid(row=0, column=1, sticky="ew")
        self.add_tooltip(self_check, self.action_hint("Self Check"))
        self.add_tooltip(choices_button, self.action_hint("Multiple Choice"))
        mode.columnconfigure(0, weight=1)
        mode.columnconfigure(1, weight=1)

        if self.quiz_mode == "choices" and len(self.store.cards) < 2:
            ttk.Label(host, text="Multiple Choice needs at least two cards.", style="H2.TLabel").pack(anchor="w")
            return
        if self.quiz_round >= len(self.quiz_cards):
            summary = f"Score: {self.quiz_score} / {len(self.quiz_cards)}" if self.quiz_mode == "choices" else f"Completed: {len(self.quiz_cards)} cards"
            ttk.Label(host, text=summary, style="H2.TLabel").pack(anchor="w")
            play = ttk.Button(host, text="Play Again", style="Primary.TButton", command=lambda: self.show_view("quiz"))
            play.pack(fill="x", pady=(16, 0))
            self.add_tooltip(play, self.action_hint("Play Again"))
            return
        card = self.quiz_cards[self.quiz_round]
        ttk.Label(host, text=f"Question {self.quiz_round + 1} of {len(self.quiz_cards)}", style="CardMuted.TLabel").pack(anchor="w")
        ttk.Label(host, text=card.front, style="H2.TLabel", wraplength=1040).pack(anchor="w", pady=(10, 20))
        self.render_media_controls(host, card)
        if self.quiz_mode == "choices":
            wrong = [item.back for item in self.store.cards if item.id != card.id]
            choices = random.sample(wrong, min(3, len(wrong))) + [card.back]
            random.shuffle(choices)
            for choice in choices:
                ttk.Button(host, text=choice, command=lambda value=choice: self.answer_quiz(host, value, card.back)).pack(fill="x", pady=5)
            return
        ttk.Label(host, text="Self-check uses Test Lab so the answer, reveal, and Smart Check stay on a separate testing page.", style="CardMuted.TLabel", wraplength=1040).pack(anchor="w", pady=(0, 12))
        self.button_row(host, [("Open in Test Lab", lambda: self.open_testing(card, "quiz", "quiz"), "Primary.TButton"), ("Skip / Next", lambda: self.next_self_quiz(host), "TButton")])

    def set_quiz_mode(self, host, mode):
        self.quiz_mode = mode
        self.quiz_round = 0
        self.quiz_score = 0
        self.quiz_cards = random.sample(self.store.cards, min(5, len(self.store.cards)))
        self.render_quiz(host)

    def next_self_quiz(self, host):
        self.quiz_round += 1
        self.render_quiz(host)

    def answer_quiz(self, host, choice, answer):
        if choice == answer:
            self.quiz_score += 1
            self.toast_message("Correct.")
        else:
            self.toast_message(f"Answer: {answer}")
        self.quiz_round += 1
        self.render_quiz(host)

    def practice_text(self, source="all"):
        lines = []
        if source in ("all", "captures"):
            for capture in self.store.captures:
                for index, bit in enumerate(capture.chunks or split_study_bits(capture.notes), 1):
                    lines.append(f"{capture.title} - bit {index} => {bit}")
        if source in ("all", "cards"):
            for card in self.store.cards:
                if card.back:
                    lines.append(f"{card.front or card.deck} => {card.back}")
        return "\n".join(lines)

    def practice_items_from_saved(self, source="all"):
        items = []
        if source in ("all", "captures"):
            for capture in self.store.captures:
                for index, bit in enumerate(capture.chunks or split_study_bits(capture.notes), 1):
                    items.append({"prompt": f"{capture.title} - bit {index}", "answer": bit})
        if source in ("all", "cards"):
            for card in self.store.cards:
                if card.back:
                    items.append({"prompt": card.front or card.deck or "Saved card", "answer": card.back})
        return [item for item in items if item["answer"]]

    def practice_items_from_text(self, raw):
        raw = (raw or "").replace("\\n", "\n").replace("/n", "\n")
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        if len(lines) < 2:
            lines = split_study_bits(raw)
        items = []
        for index, line in enumerate(lines, 1):
            parsed = parse_prompt_answer_lines(line)
            if parsed:
                items.extend(parsed)
                continue
            answer = normalize_space(re.sub(r"^[-*\d.)\s]+", "", line))
            prompt = f"Study bit {index}"
            items.append({"prompt": prompt or f"Study bit {index}", "answer": answer})
        return [item for item in items if item["answer"]]

    @staticmethod
    def repetition_steps(bits, start, span):
        if not bits:
            return []
        start_index = min(max(start, 1), len(bits)) - 1
        span = start_index + 1 if span is None else min(max(span, 1), len(bits))
        steps, current = [], []
        for offset in range(span):
            index = start_index - offset
            if index < 0:
                break
            current.append(index)
            steps.append(("-".join(str(item + 1) for item in current), list(current)))
        if current and current[-1] > 0:
            walk = list(range(current[-1], -1, -1))
            steps.append(("-".join(str(item + 1) for item in walk), walk))
        return steps

    def view_shuffle(self):
        draft = self.view_drafts.get("shuffle", {})
        page = ScrollFrame(self.content)
        page.pack(fill="both", expand=True)
        panel = self.card(page.inner)
        panel.pack(fill="x")
        ttk.Label(panel, text="Repetition path", style="H2.TLabel").pack(anchor="w")
        ttk.Label(panel, text="Add each repetition item with a separate prompt and answer. Prompts show first; answers reveal when you choose.", style="CardMuted.TLabel", wraplength=980).pack(anchor="w", pady=(6, 14))

        guide = self.card(panel, "WarmCard.TFrame", 14)
        guide.pack(fill="x", pady=(0, 12))
        ttk.Label(guide, text="Best for list recall", style="WarmH2.TLabel").pack(anchor="w")
        ttk.Label(guide, text="Start from any item, set a loop range, and MemoryPal walks the sequence backward before returning to item 1.", style="WarmCard.TLabel", wraplength=980).pack(anchor="w", pady=(4, 0))

        form = self.card(panel, "AltCard.TFrame", 18)
        form.pack(fill="x", pady=(0, 12))
        form.columnconfigure(0, weight=1)
        left = ttk.Frame(form, style="AltCard.TFrame")
        left.grid(row=0, column=0, sticky="nsew")
        right = ttk.Frame(form, style="AltCard.TFrame")
        right.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        ttk.Label(left, text="Question / title", style="AltMuted.TLabel").pack(anchor="w")
        prompt_var = tk.StringVar()
        prompt_var.set(draft.get("prompt", ""))
        prompt_entry = ttk.Entry(left, textvariable=prompt_var)
        prompt_entry.pack(fill="x", pady=(4, 0))
        ttk.Label(right, text="Answer / recall content", style="AltMuted.TLabel").pack(anchor="w")
        answer_box = self.text_box(right, 4, 12)
        answer_box.insert("1.0", draft.get("answer", ""))
        answer_box.pack(fill="both", expand=True, pady=(4, 0))
        bulk_panel = ttk.Frame(form, style="AltCard.TFrame")
        bulk_panel.grid(row=2, column=0, sticky="nsew", pady=(12, 0))
        ttk.Label(bulk_panel, text="Optional bulk notes", style="AltMuted.TLabel").pack(anchor="w")
        bulk_text = self.text_box(bulk_panel, 3, 12)
        bulk_text.insert("1.0", draft.get("bulk", ""))
        bulk_text.pack(fill="x", pady=(4, 0))
        ttk.Label(bulk_panel, text="Paste plain facts or numbered notes here if you want to split them into repetition items.", style="AltMuted.TLabel", wraplength=920).pack(anchor="w", pady=(6, 0))

        staged_items = [dict(item) for item in draft.get("staged_items", [])]
        staged_panel = tk.Frame(panel, bg=COLORS["surface"])
        staged_panel.pack(fill="x", pady=(0, 12))
        count_label = ttk.Label(panel, text="0 repetition items staged", style="CardMuted.TLabel")
        count_label.pack(anchor="w", pady=(0, 8))

        def refresh_staged():
            for child in staged_panel.winfo_children():
                child.destroy()
            if not staged_items:
                tk.Label(staged_panel, text="No repetition items staged yet.", bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI", 12)).pack(anchor="w")
            for index, item in enumerate(staged_items, 1):
                row = tk.Frame(staged_panel, bg=COLORS["alt"], padx=self.px(14), pady=self.px(10))
                row.pack(fill="x", pady=(0, self.px(8)))
                tk.Label(row, text=f"{index}.", bg=COLORS["alt"], fg=COLORS["primary"], font=self.font("Segoe UI Semibold", 12)).pack(side="left", anchor="n", padx=(0, self.px(8)))
                details = tk.Frame(row, bg=COLORS["alt"])
                details.pack(side="left", fill="x", expand=True)
                tk.Label(details, text=item["prompt"], bg=COLORS["alt"], fg=COLORS["ink"], wraplength=self.px(980), justify="left", font=self.font("Segoe UI Semibold", 12)).pack(anchor="w")
                tk.Label(details, text=item["answer"], bg=COLORS["alt"], fg=COLORS["muted"], wraplength=self.px(980), justify="left", font=self.font("Segoe UI", 11)).pack(anchor="w", pady=(self.px(3), 0))
            count_label.configure(text=f"{len(staged_items)} repetition item{'s' if len(staged_items) != 1 else ''} staged")

        def add_item():
            prompt = normalize_space(prompt_var.get()) or f"Study item {len(staged_items) + 1}"
            answer = normalize_space(answer_box.get("1.0", "end"))
            if not answer:
                self.toast_message("Add an answer or recall item first.")
                return
            staged_items.append({"prompt": prompt, "answer": answer})
            prompt_var.set("")
            answer_box.delete("1.0", "end")
            refresh_staged()

        def split_answer():
            bits = split_study_bits(answer_box.get("1.0", "end"))
            if not bits:
                self.toast_message("Add a few answer lines first.")
                return
            base = normalize_space(prompt_var.get()) or "Study item"
            total = len(bits)
            for index, bit in enumerate(bits, 1):
                prompt = base if total == 1 else f"{base} {index}/{total}"
                staged_items.append({"prompt": prompt, "answer": normalize_space(bit)})
            prompt_var.set("")
            answer_box.delete("1.0", "end")
            refresh_staged()

        def split_bulk():
            bits = self.practice_items_from_text(bulk_text.get("1.0", "end"))
            if not bits:
                self.toast_message("Paste plain facts, titles, or numbered notes first.")
                return
            staged_items.extend(bits)
            bulk_text.delete("1.0", "end")
            refresh_staged()

        def remove_last():
            if staged_items:
                staged_items.pop()
                refresh_staged()

        self.button_row(panel, [("Add Item", add_item, "Primary.TButton"), ("Split Answer", split_answer, "TButton"), ("Split Paste", split_bulk, "TButton"), ("Remove Last", remove_last, "TButton")])

        controls = ttk.Frame(panel, style="Card.TFrame")
        controls.pack(fill="x", pady=(0, 12))
        ttk.Label(controls, text="Start #", style="CardMuted.TLabel").grid(row=0, column=0, sticky="w")
        start_var = tk.StringVar()
        start_var.set(draft.get("start", ""))
        ttk.Entry(controls, textvariable=start_var).grid(row=1, column=0, sticky="ew", padx=(0, 8))
        ttk.Label(controls, text="Loop range (optional)", style="CardMuted.TLabel").grid(row=0, column=1, sticky="w")
        range_var = tk.StringVar()
        range_var.set(draft.get("range", ""))
        ttk.Entry(controls, textvariable=range_var).grid(row=1, column=1, sticky="ew", padx=(0, 8))
        ttk.Label(controls, text="Example: range 3 at item 5 gives 5, 5-4, 5-4-3, then 3-2-1.", style="CardMuted.TLabel", wraplength=620).grid(row=1, column=2, sticky="w")
        controls.columnconfigure(0, weight=1)
        controls.columnconfigure(1, weight=1)
        controls.columnconfigure(2, weight=3)

        results_header = self.card(page.inner, "AltCard.TFrame", 16)
        results_header.pack(fill="x", pady=(14, 8))
        ttk.Label(results_header, text="Practice rounds", style="AltH2.TLabel").pack(anchor="w")
        ttk.Label(results_header, text="Built rounds appear below on this same scrollable page.", style="AltMuted.TLabel", wraplength=980).pack(anchor="w", pady=(4, 0))
        results = ttk.Frame(page.inner, style="Page.TFrame")
        results.pack(fill="x")

        def load(source):
            staged_items.clear()
            staged_items.extend(self.practice_items_from_saved(source))
            refresh_staged()
            self.toast_message("Loaded saved material.")

        def build():
            for child in results.winfo_children():
                child.destroy()
            items = list(staged_items)
            if normalize_space(answer_box.get("1.0", "end")):
                items.append({"prompt": normalize_space(prompt_var.get()) or f"Study item {len(items) + 1}", "answer": normalize_space(answer_box.get("1.0", "end"))})
            items.extend(self.practice_items_from_text(bulk_text.get("1.0", "end")))
            if not items:
                ttk.Label(results, text="Add repetition items or load saved cards/captures first.", style="Muted.TLabel").pack(anchor="w")
                return
            try:
                start = int(start_var.get()) if start_var.get().strip() else len(items)
                span = int(range_var.get()) if range_var.get().strip() else None
            except ValueError:
                self.toast_message("Start and range must be numbers.")
                return
            answers = [item["answer"] for item in items]
            for round_number, (label, indexes) in enumerate(self.repetition_steps(answers, start, span), 1):
                item_card = self.card(results)
                item_card.pack(fill="x", padx=(0, 8), pady=(0, 8))
                ttk.Label(item_card, text=f"Round {round_number} | Repeat {label}", style="H2.TLabel").pack(anchor="w")
                ttk.Label(item_card, text="Prompt", style="CardMuted.TLabel").pack(anchor="w", pady=(8, 0))
                for index in indexes:
                    ttk.Label(item_card, text=f"{index + 1}. {items[index]['prompt']}", style="Card.TLabel", wraplength=1080).pack(anchor="w", pady=(4, 0))
                response = self.answer_area(item_card, "Your recall", "Write the answer sequence for this round.", 3)
                result = ttk.Label(item_card, text="Type your recall, then check or reveal.", style="CardMuted.TLabel", wraplength=1040)
                result.pack(anchor="w")
                answer_frame = ttk.Frame(item_card, style="Card.TFrame")
                visible = {"value": False}

                def reveal(frame=answer_frame, ids=indexes, flag=visible):
                    if flag["value"]:
                        frame.pack_forget()
                        flag["value"] = False
                        return
                    for child in frame.winfo_children():
                        child.destroy()
                    ttk.Label(frame, text="Answer", style="CardMuted.TLabel").pack(anchor="w")
                    for answer_index in ids:
                        ttk.Label(frame, text=f"{answer_index + 1}. {items[answer_index]['answer']}", style="Card.TLabel", wraplength=1080).pack(anchor="w", pady=(3, 0))
                    frame.pack(fill="x", pady=(8, 0))
                    flag["value"] = True

                def check(box=response, target=result, ids=indexes):
                    expected = "\n".join(items[index]["answer"] for index in ids)
                    checked = answer_assessment(box.get("1.0", "end").strip(), expected)
                    target.configure(text=f"{checked['label']} | {checked['score']}% | Reps: {checked['repetitions']} | {checked['detail']}")

                self.button_row(item_card, [("Smart Check", check, "Primary.TButton"), ("Reveal / Hide Answer", reveal, "TButton")])

        self.button_row(panel, [("Build Path", build, "Primary.TButton"), ("Use Captures", lambda: load("captures"), "TButton"), ("Use Cards", lambda: load("cards"), "TButton"), ("Use All", lambda: load("all"), "TButton")])
        refresh_staged()
        self.register_draft_saver("shuffle", lambda: {
            "prompt": prompt_var.get(),
            "answer": answer_box.get("1.0", "end").strip(),
            "bulk": bulk_text.get("1.0", "end").strip(),
            "staged_items": [dict(item) for item in staged_items],
            "start": start_var.get(),
            "range": range_var.get(),
        })

    def material_bits(self):
        bits = []
        for capture in self.store.captures:
            bits.extend(capture.chunks or split_study_bits(capture.notes))
        for card in self.store.cards:
            bits.extend([card.front, card.back])
        return [bit for bit in bits if bit]

    def view_tools(self):
        draft = self.view_drafts.get("tools", {})
        page = ScrollFrame(self.content)
        page.pack(fill="both", expand=True)
        panel = self.card(page.inner)
        panel.pack(fill="x", padx=(0, 8), pady=(0, 12))
        ttk.Label(panel, text="Association builder", style="H2.TLabel").pack(anchor="w")
        ttk.Label(panel, text="Add ideas separated by commas, new lines, or slashes. Then choose a memory hook style.", style="CardMuted.TLabel", wraplength=1040).pack(anchor="w", pady=(6, 12))
        ideas = self.text_box(panel, 4, 12)
        ideas.insert("1.0", draft.get("ideas", "mitosis, meiosis, chromosomes"))
        ideas.pack(fill="x", pady=(0, 12))
        output = self.card(page.inner, "AltCard.TFrame")
        output.pack(fill="both", expand=True, padx=(0, 8), pady=(0, 12))
        out = ttk.Label(output, text=draft.get("output", "Your memory hook will appear here."), style="AltCard.TLabel", wraplength=1080)
        out.pack(anchor="w")

        def parse():
            raw = ideas.get("1.0", "end").replace("/n", "\n")
            return [item.strip() for item in re.split(r"[,\n;|/]+", raw) if item.strip()]

        def acronym():
            items = parse()
            out.configure(text="".join(item[0].upper() for item in items) + "\n\nConnect each letter back to: " + ", ".join(items) if items else "Add ideas first.")

        def story():
            items = parse()
            if not items:
                out.configure(text="Add ideas first.")
                return
            scenes = [
                "at the front door",
                "on the kitchen table",
                "beside a bright window",
                "inside a small notebook",
                "under a glowing lamp",
                "next to the final doorway",
            ]
            lines = []
            for index, item in enumerate(items):
                scene = scenes[index % len(scenes)]
                action = ["shines", "speaks", "spins", "points", "opens", "locks"][index % 6]
                lines.append(f"{index + 1}. Picture {item} {scene}. It {action} so you notice it before moving on.")
            out.configure(text="Mini-story:\n\n" + "\n".join(lines) + "\n\nWalk through the scenes in order and let each image cue the next idea.")

        def peg_list():
            items = parse()
            pegs = ["sun", "shoe", "tree", "door", "hive", "sticks", "heaven", "gate", "line", "pen"]
            if not items:
                out.configure(text="Add ideas first.")
                return
            lines = []
            for index, item in enumerate(items):
                peg = pegs[index % len(pegs)]
                lines.append(f"{index + 1}. {peg.title()} peg: imagine {item} attached to a {peg}.")
            out.configure(text="Peg list:\n\n" + "\n".join(lines))

        def palace():
            items = parse()
            route = ["front door", "hallway", "kitchen", "table", "window", "sofa", "bedroom", "desk", "mirror", "back door"]
            if not items:
                out.configure(text="Add ideas first.")
                return
            lines = []
            for index, item in enumerate(items):
                place = route[index % len(route)]
                lines.append(f"{index + 1}. Put {item} at the {place}. Make it oversized or moving.")
            out.configure(text="Memory palace route:\n\n" + "\n".join(lines) + "\n\nReview by walking through the route in the same order.")

        def chunk_map():
            items = parse()
            if not items:
                out.configure(text="Add ideas first.")
                return
            chunks = [items[index:index + 3] for index in range(0, len(items), 3)]
            lines = [f"Group {index + 1}: " + ", ".join(group) for index, group in enumerate(chunks)]
            out.configure(text="Chunk map:\n\n" + "\n".join(lines) + "\n\nStudy one group at a time, then connect the groups.")

        def link_chain():
            items = parse()
            if not items:
                out.configure(text="Add ideas first.")
                return
            if len(items) == 1:
                out.configure(text=f"Link chain:\n\nStart with {items[0]} and add more ideas to build a chain.")
                return
            lines = []
            for first, second in zip(items, items[1:]):
                lines.append(f"{first} leads to {second}: imagine {first} handing a bright clue to {second}.")
            out.configure(text="Link chain:\n\n" + "\n".join(lines))

        def saved():
            ideas.delete("1.0", "end")
            ideas.insert("1.0", ", ".join(self.material_bits()[:10]))

        self.button_row(panel, [("Acronym", acronym, "Primary.TButton"), ("Mini Story", story, "TButton"), ("Peg List", peg_list, "TButton")])
        self.button_row(panel, [("Memory Palace", palace, "TButton"), ("Chunk Map", chunk_map, "TButton"), ("Link Chain", link_chain, "TButton"), ("Saved Material", saved, "TButton")])
        self.register_draft_saver("tools", lambda: {
            "ideas": ideas.get("1.0", "end").strip(),
            "output": out.cget("text"),
        })

    def view_games(self):
        draft = self.view_drafts.get("games", {})
        page = ScrollFrame(self.content)
        page.pack(fill="both", expand=True)
        intro = self.card(page.inner, "WarmCard.TFrame", 16)
        intro.pack(fill="x", padx=(0, 8), pady=(0, 12))
        ttk.Label(intro, text="Short recall puzzles", style="WarmH2.TLabel").pack(anchor="w")
        ttk.Label(intro, text="Use these as quick warmups between study modes. They pull from saved material when possible and fall back to sample prompts.", style="WarmCard.TLabel", wraplength=1040).pack(anchor="w", pady=(4, 0))

        grid = ttk.Frame(page.inner, style="Page.TFrame")
        grid.pack(fill="both", expand=True, padx=(0, 8))
        for column in range(2):
            grid.columnconfigure(column, weight=1, uniform="puzzles")

        sequence_card = self.card(grid)
        sequence_card.grid(row=0, column=0, sticky="nsew", padx=(0, 12), pady=(0, 12))
        ttk.Label(sequence_card, text="Sequence Recall", style="H2.TLabel").pack(anchor="w")
        ttk.Label(sequence_card, text="Watch the digits, then type them back.", style="CardMuted.TLabel").pack(anchor="w", pady=(4, 12))
        sequence_box = ttk.Label(sequence_card, text="Press Start", style="Stat.TLabel", wraplength=500)
        if draft.get("sequence"):
            self.sequence = draft.get("sequence", "")
            sequence_box.configure(text=draft.get("sequence_prompt", "Now type it"))
        sequence_box.pack(anchor="w", pady=(0, 12))
        answer = ttk.Entry(sequence_card)
        answer.insert(0, draft.get("sequence_answer", ""))
        answer.pack(fill="x", pady=(0, 12))

        def start_sequence():
            self.sequence = "".join(str(random.randint(1, 9)) for _ in range(random.randint(4, 8)))
            sequence_box.configure(text=" ".join(self.sequence))
            answer.delete(0, "end")
            self.after(3000, lambda: sequence_box.configure(text="Now type it") if sequence_box.winfo_exists() else None)

        def check_sequence():
            typed = re.sub(r"\D", "", answer.get())
            self.toast_message("Correct." if typed == self.sequence else f"Sequence: {self.sequence}")

        self.button_row(sequence_card, [("Start", start_sequence, "Primary.TButton"), ("Check", check_sequence, "TButton")])

        word_card = self.card(grid)
        word_card.grid(row=0, column=1, sticky="nsew", pady=(0, 12))
        ttk.Label(word_card, text="Word Recall", style="H2.TLabel").pack(anchor="w")
        ttk.Label(word_card, text="A short word list appears, then disappears.", style="CardMuted.TLabel").pack(anchor="w", pady=(4, 12))
        word_box = ttk.Label(word_card, text="Press Show Words", style="Card.TLabel", wraplength=500)
        current_words = list(draft.get("current_words", []))
        if current_words:
            word_box.configure(text=draft.get("word_prompt", "Say them back"))
        word_box.pack(anchor="w", pady=(0, 12))
        word_answer = ttk.Entry(word_card)
        word_answer.insert(0, draft.get("word_answer", ""))
        word_answer.pack(fill="x", pady=(0, 12))

        def word_pool():
            pool = [word.lower() for bit in self.material_bits() for word in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", bit)]
            clean = list(dict.fromkeys(pool))
            return clean if len(clean) >= 5 else ["river", "lamp", "garden", "silver", "window", "music", "orange"]

        def show_words():
            nonlocal current_words
            pool = word_pool()
            current_words = random.sample(pool, min(6, len(pool)))
            word_box.configure(text=", ".join(current_words))
            word_answer.delete(0, "end")
            self.after(3800, lambda: word_box.configure(text="Say them back") if word_box.winfo_exists() else None)

        def check_words():
            result = answer_assessment(word_answer.get(), " ".join(current_words))
            self.toast_message(f"{result['label']} | {result['score']}%")

        self.button_row(word_card, [("Show Words", show_words, "Primary.TButton"), ("Smart Check", check_words, "TButton")])

        pair_card = self.card(grid)
        pair_card.grid(row=1, column=0, sticky="nsew", padx=(0, 12), pady=(0, 12))
        ttk.Label(pair_card, text="Pair Recall", style="H2.TLabel").pack(anchor="w")
        ttk.Label(pair_card, text="Practice one prompt-answer pair at a time.", style="CardMuted.TLabel").pack(anchor="w", pady=(4, 12))
        pair_prompt = ttk.Label(pair_card, text="Make a pair set", style="H2.TLabel", wraplength=500)
        pair_prompt.pack(anchor="w", pady=(0, 12))
        pair_answer = ttk.Entry(pair_card)
        pair_answer.insert(0, draft.get("pair_answer", ""))
        pair_answer.pack(fill="x", pady=(0, 12))
        pair_status = ttk.Label(pair_card, text="Smart Check will score the current pair.", style="CardMuted.TLabel", wraplength=500)
        pair_status.pack(anchor="w", pady=(0, 12))
        pair_state = {"pairs": [dict(item) for item in draft.get("pairs", [])], "index": int(draft.get("pair_index", 0))}
        if pair_state["pairs"]:
            pair_state["index"] = min(pair_state["index"], len(pair_state["pairs"]) - 1)
            pair_prompt.configure(text=draft.get("pair_prompt", pair_state["pairs"][pair_state["index"]]["prompt"]))
            pair_status.configure(text=draft.get("pair_status", f"Pair {pair_state['index'] + 1} of {len(pair_state['pairs'])}"))

        def new_pair_set():
            pairs = [{"prompt": card.front, "answer": card.back} for card in self.store.cards if card.front and card.back]
            if not pairs:
                pairs = [
                    {"prompt": "Where do spaced reviews go?", "answer": "Test Lab"},
                    {"prompt": "What does Smart Check suggest?", "answer": "A review bucket"},
                    {"prompt": "What does chunking create?", "answer": "Small study bits"},
                ]
            pair_state["pairs"] = random.sample(pairs, min(5, len(pairs)))
            pair_state["index"] = 0
            pair_answer.delete(0, "end")
            pair_prompt.configure(text=pair_state["pairs"][0]["prompt"])
            pair_status.configure(text=f"Pair 1 of {len(pair_state['pairs'])}")

        def reveal_pair():
            if not pair_state["pairs"]:
                new_pair_set()
            current = pair_state["pairs"][pair_state["index"]]
            pair_status.configure(text=f"Answer: {current['answer']}")

        def check_pair():
            if not pair_state["pairs"]:
                new_pair_set()
            current = pair_state["pairs"][pair_state["index"]]
            result = answer_assessment(pair_answer.get(), current["answer"], current["prompt"])
            pair_status.configure(text=f"{result['label']} | {result['score']}% | {result['detail']}")
            pair_state["index"] = (pair_state["index"] + 1) % len(pair_state["pairs"])
            pair_answer.delete(0, "end")
            self.after(1200, lambda: pair_prompt.configure(text=pair_state["pairs"][pair_state["index"]]["prompt"]) if pair_prompt.winfo_exists() and pair_state["pairs"] else None)

        self.button_row(pair_card, [("New Pair Set", new_pair_set, "Primary.TButton"), ("Reveal Cue", reveal_pair, "TButton"), ("Smart Check", check_pair, "TButton")])

        gap_card = self.card(grid)
        gap_card.grid(row=1, column=1, sticky="nsew", pady=(0, 12))
        ttk.Label(gap_card, text="Missing Item", style="H2.TLabel").pack(anchor="w")
        ttk.Label(gap_card, text="Find the hidden item from a short sequence.", style="CardMuted.TLabel").pack(anchor="w", pady=(4, 12))
        gap_prompt = ttk.Label(gap_card, text="Press Make Gap", style="Card.TLabel", wraplength=500)
        if draft.get("gap_prompt"):
            gap_prompt.configure(text=draft["gap_prompt"])
        gap_prompt.pack(anchor="w", pady=(0, 12))
        gap_answer = ttk.Entry(gap_card)
        gap_answer.insert(0, draft.get("gap_answer", ""))
        gap_answer.pack(fill="x", pady=(0, 12))
        gap_state = {"answer": draft.get("gap_answer_key", "")}

        def make_gap():
            pool = word_pool()
            words = random.sample(pool, min(5, len(pool)))
            hidden = random.randrange(len(words))
            gap_state["answer"] = words[hidden]
            shown = list(words)
            shown[hidden] = "_____"
            gap_prompt.configure(text="  -  ".join(shown))
            gap_answer.delete(0, "end")

        def check_gap():
            result = answer_assessment(gap_answer.get(), gap_state["answer"])
            self.toast_message(f"{result['label']} | Missing: {gap_state['answer']}")

        self.button_row(gap_card, [("Make Gap", make_gap, "Primary.TButton"), ("Check", check_gap, "TButton")])
        self.register_draft_saver("games", lambda: {
            "sequence": self.sequence,
            "sequence_prompt": sequence_box.cget("text"),
            "sequence_answer": answer.get(),
            "current_words": list(current_words),
            "word_prompt": word_box.cget("text"),
            "word_answer": word_answer.get(),
            "pairs": [dict(item) for item in pair_state["pairs"]],
            "pair_index": pair_state["index"],
            "pair_prompt": pair_prompt.cget("text"),
            "pair_status": pair_status.cget("text"),
            "pair_answer": pair_answer.get(),
            "gap_prompt": gap_prompt.cget("text"),
            "gap_answer": gap_answer.get(),
            "gap_answer_key": gap_state["answer"],
        })

    def view_library(self):
        tools = ttk.Frame(self.content, style="Page.TFrame")
        tools.pack(fill="x", pady=(0, 12))
        search_var = tk.StringVar()
        filter_var = tk.StringVar(value="All")
        top = ttk.Frame(tools, style="Page.TFrame")
        top.pack(fill="x", pady=(0, 10))
        ttk.Entry(top, textvariable=search_var).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttk.Combobox(top, textvariable=filter_var, values=["All", "Due", "Weak", "Captures"], state="readonly").grid(row=0, column=1, sticky="ew", padx=(0, 8))
        ttk.Button(top, text="Apply", command=lambda: render()).grid(row=0, column=2, sticky="ew")
        top.columnconfigure(0, weight=3)
        top.columnconfigure(1, weight=1)
        self.button_row(tools, [("Add Samples", lambda: [self.store.add_card(card) for card in sample_cards()] or self.show_view("library"), "Primary.TButton"), ("Import", self.import_data, "TButton"), ("Export", self.export_data, "TButton"), ("Reset", self.reset_data, "Danger.TButton")], "Page.TFrame")
        page = ScrollFrame(self.content)
        page.pack(fill="both", expand=True)

        def matches(text):
            query = normalize_space(search_var.get()).lower()
            return not query or query in text.lower()

        def render():
            for child in page.inner.winfo_children():
                child.destroy()
            mode = filter_var.get()
            shown = 0
            if mode in ("All", "Captures"):
                for capture in self.store.captures:
                    chunks = capture.chunks or split_study_bits(capture.notes)
                    searchable = " ".join([capture.title, capture.notes, " ".join(chunks)])
                    if not matches(searchable):
                        continue
                    item = self.card(page.inner)
                    item.pack(fill="x", padx=(0, 8), pady=(0, 10))
                    ttk.Label(item, text=f"Capture | {capture.created_at}", style="CardMuted.TLabel").pack(anchor="w")
                    ttk.Label(item, text=capture.title, style="H2.TLabel", wraplength=1060).pack(anchor="w", pady=(6, 5))
                    ttk.Label(item, text=f"{len(chunks)} study bits", style="CardMuted.TLabel").pack(anchor="w")
                    for index, chunk in enumerate(chunks[:5], 1):
                        ttk.Label(item, text=f"{index}. {chunk}", style="Card.TLabel", wraplength=1080).pack(anchor="w", pady=(2, 0))
                    self.render_media_controls(item, capture)
                    shown += 1
            card_pool = self.store.cards
            if mode == "Due":
                card_pool = self.store.due_cards()
            elif mode == "Weak":
                card_pool = self.store.weak_cards()
            if mode != "Captures":
                for card in card_pool:
                    searchable = " ".join([card.deck, card.front, card.back, card.pathway, card.association])
                    if not matches(searchable):
                        continue
                    item = self.card(page.inner)
                    item.pack(fill="x", padx=(0, 8), pady=(0, 10))
                    ttk.Label(item, text=f"{card.deck} | Next: {card.next_review} | {card.last_result} {card.last_score}%", style="CardMuted.TLabel").pack(anchor="w")
                    ttk.Label(item, text=card.front, style="H2.TLabel", wraplength=1060).pack(anchor="w", pady=(6, 5))
                    ttk.Label(item, text=card.back, style="Card.TLabel", wraplength=1080).pack(anchor="w")
                    ttk.Label(item, text=f"Path: {card.pathway or 'Not set'}", style="CardMuted.TLabel").pack(anchor="w", pady=(8, 0))
                    self.render_media_controls(item, card)
                    shown += 1
            if shown == 0:
                ttk.Label(page.inner, text="No matching material.", style="Muted.TLabel").pack(anchor="w")

        render()

    def export_data(self):
        path = filedialog.asksaveasfilename(title="Export MemoryPal data", defaultextension=".json", initialfile="memorypal-data.json", filetypes=[("JSON files", "*.json")])
        if path:
            self.store.save()
            shutil.copy2(DATA_FILE, path)
            self.toast_message("Data exported.")

    def import_data(self):
        path = filedialog.askopenfilename(title="Import MemoryPal data", filetypes=[("JSON files", "*.json")])
        if not path:
            return
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
            self.store.cards = [Card.from_dict(item) for item in raw.get("cards", [])]
            self.store.captures = [Capture.from_dict(item) for item in raw.get("captures", [])]
            self.store.practiced = int(raw.get("practiced", 0))
            self.store.save()
            self.show_view("library")
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            messagebox.showerror("Import failed", str(exc))

    def reset_data(self):
        if messagebox.askyesno("Reset MemoryPal", "Clear local data and restore sample cards?"):
            self.store.reset()
            self.show_view("library")


def main():
    enable_dpi_awareness()
    app = MemoryPalApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
