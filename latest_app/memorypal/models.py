from dataclasses import dataclass, field

from .core import now_label, split_study_bits, today_iso, uid


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
        values["buried_until"] = raw.get("buried_until", "")
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
