from dataclasses import dataclass, field

from .core import now_label, split_study_bits, today_iso, uid


def first_text(raw, names, default=""):
    """First non-empty value among names (field name, then legacy aliases)."""
    for name in names:
        value = raw.get(name)
        if value is not None and str(value) != "":
            return str(value)
    return default


def number(value, kind, default):
    try:
        return kind(value)
    except (TypeError, ValueError):
        return default



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
    buried_until: str = ""

    @classmethod
    def from_dict(cls, raw):
        # Older or hand-edited files can miss fields, use camelCase names, or
        # hold nulls. Fall back to defaults field by field so a card is never
        # half-None (which crashed sorting) or dropped for one bad number.
        defaults = cls()
        text = lambda *names: first_text(raw, names, getattr(defaults, names[0]))
        return cls(
            id=text("id"),
            deck=text("deck") or "General",
            front=text("front"),
            back=text("back"),
            pathway=text("pathway"),
            association=text("association"),
            text_file=text("text_file", "textFile"),
            image=text("image"),
            audio=text("audio"),
            video=text("video"),
            next_review=text("next_review", "nextReview"),
            interval=max(0, number(raw.get("interval"), int, 0)),
            repetitions=max(0, number(raw.get("repetitions"), int, 0)),
            ease=min(3.5, max(1.3, number(raw.get("ease"), float, 2.5))),
            lapses=max(0, number(raw.get("lapses"), int, 0)),
            last_score=max(0, min(100, number(raw.get("last_score", raw.get("lastScore")), int, 0))),
            last_result=text("last_result", "lastResult"),
            created_at=text("created_at", "createdAt"),
            buried_until=text("buried_until"),
        )


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
        defaults = cls()
        text = lambda *names: first_text(raw, names, getattr(defaults, names[0]))
        notes = text("notes")
        chunks = raw.get("chunks")
        if isinstance(chunks, list):
            chunks = [str(chunk) for chunk in chunks if chunk is not None and str(chunk).strip()]
        else:
            chunks = []
        return cls(
            id=text("id"),
            title=text("title") or defaults.title,
            notes=notes,
            chunks=chunks or split_study_bits(notes),
            text_file=text("text_file", "textFile"),
            image=text("image"),
            audio=text("audio"),
            video=text("video"),
            created_at=text("created_at", "createdAt"),
        )


@dataclass
class FeedbackEntry:
    id: str = field(default_factory=uid)
    rating: int = 0
    category: str = "General"
    page: str = "Overall app"
    note: str = ""
    created_at: str = field(default_factory=now_label)

    @classmethod
    def from_dict(cls, raw):
        try:
            rating = int(raw.get("rating", 0))
        except (TypeError, ValueError):
            rating = 0
        return cls(
            id=raw.get("id", uid()),
            rating=max(0, min(5, rating)),
            category=raw.get("category", "General") or "General",
            page=raw.get("page", "Overall app") or "Overall app",
            note=raw.get("note", ""),
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
