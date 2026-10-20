"""The desktop's AI notes and questions flow, kept free of Tk so it can be tested.

ai.py talks to the server; this module holds what sits around it in the app:

- consent: AI stays off until the person allows it once (the one-time AI
  screen), and the Settings switch withdraws it again;
- gate(): what has to happen before a request (sign in, consent);
- error_message(): every failure as words people can act on, never a traceback;
- Job: one request on a worker thread that the UI polls with after(), with Cancel;
- staging: AI questions as set-builder rows, with the picture or PDF page they
  came from attached, and AI notes as a capture;
- quiz history: the last round's question ids, so the next round avoids them.

Preferences live in MemoryStore.preferences (this device only, not synced).
"""

import threading
import urllib.error
from datetime import datetime
from pathlib import Path

from . import ai, cloud
from .core import normalize_space, today_iso

CONSENT_VERSION = 1
QUIZ_RECENT_MAX = 60
# The server's default daily allowance (supabase/functions/ai, AI_DAILY_LIMIT).
AI_DAILY_LIMIT = 10
GEMINI_TERMS_URL = "https://ai.google.dev/gemini-api/terms"
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")
PDF_SUFFIX = ".pdf"
SOURCE_SUFFIXES = (PDF_SUFFIX,) + IMAGE_SUFFIXES
SOURCE_FILETYPES = [("PDF or picture", "*.pdf *.png *.jpg *.jpeg *.webp"), ("PDF", "*.pdf"), ("Pictures", "*.png *.jpg *.jpeg *.webp")]
REPORT_CATEGORY = "AI content report"


# ------------------------------------------------------------- preferences
def default_preferences():
    return {
        "ai_enabled": False,
        "ai_consent_at": "",
        "ai_consent_version": 0,
        "ai_remaining": None,
        "ai_remaining_day": "",
        "quiz_recent": [],
        "quiz_deck": "",
    }


def normalize_preferences(raw):
    prefs = default_preferences()
    if not isinstance(raw, dict):
        return prefs
    prefs["ai_enabled"] = raw.get("ai_enabled") is True
    prefs["ai_consent_at"] = str(raw.get("ai_consent_at") or "")[:40]
    version = raw.get("ai_consent_version")
    prefs["ai_consent_version"] = version if isinstance(version, int) and not isinstance(version, bool) and 0 <= version < 1000 else 0
    remaining = raw.get("ai_remaining")
    prefs["ai_remaining"] = remaining if isinstance(remaining, int) and not isinstance(remaining, bool) and 0 <= remaining < 100000 else None
    prefs["ai_remaining_day"] = str(raw.get("ai_remaining_day") or "")[:10]
    recent = raw.get("quiz_recent")
    prefs["quiz_recent"] = [str(item)[:120] for item in recent if isinstance(item, (str, int))][-QUIZ_RECENT_MAX:] if isinstance(recent, list) else []
    prefs["quiz_deck"] = str(raw.get("quiz_deck") or "")[:200]
    return prefs


def has_consent(prefs):
    """AI is allowed: the switch is on and the current AI screen was accepted."""
    prefs = prefs or {}
    return prefs.get("ai_enabled") is True and int(prefs.get("ai_consent_version") or 0) >= CONSENT_VERSION


def give_consent(prefs, when=None):
    updated = normalize_preferences(prefs)
    updated.update(ai_enabled=True, ai_consent_version=CONSENT_VERSION, ai_consent_at=when or datetime.now().isoformat(timespec="seconds"))
    return updated


def withdraw_consent(prefs):
    """Turning AI off forgets the consent too, so turning it on asks again."""
    updated = normalize_preferences(prefs)
    updated.update(ai_enabled=False, ai_consent_version=0, ai_consent_at="")
    return updated


def gate(prefs, signed_in, configured=True):
    """What must happen before an AI request: not_configured, sign_in, consent or ok."""
    if not configured:
        return "not_configured"
    if not signed_in:
        return "sign_in"
    if not has_consent(prefs):
        return "consent"
    return "ok"


# ---------------------------------------------------------- daily allowance
def remember_remaining(prefs, remaining, day=None):
    updated = normalize_preferences(prefs)
    if isinstance(remaining, int) and not isinstance(remaining, bool) and remaining >= 0:
        updated["ai_remaining"] = remaining
        updated["ai_remaining_day"] = day or today_iso()
    return updated


def remaining_today(prefs, day=None):
    """The last count the server gave, if it was given today; else None."""
    prefs = prefs or {}
    if prefs.get("ai_remaining_day") != (day or today_iso()):
        return None
    remaining = prefs.get("ai_remaining")
    return remaining if isinstance(remaining, int) else None


def remaining_text(remaining):
    if remaining is None:
        return ""
    if remaining <= 0:
        return "No AI uses left today. They reset tomorrow."
    return f"{remaining} AI use{'s' if remaining != 1 else ''} left today"


# ------------------------------------------------------------------ errors
SIGN_IN_CODES = ("not_signed_in", "signed_out", "second_step")
TITLES = {
    "not_signed_in": "Sign in to use AI",
    "signed_out": "Sign in to use AI",
    "second_step": "Finish signing in",
    "limit_reached": "That's today's AI uses",
    "file_too_large": "That file is too big",
    "unsupported_file": "That file can't be read",
    "bad_request": "Nothing to send yet",
    "offline": "You're offline",
    "not_configured": "AI isn't ready yet",
    "busy": "The AI is busy",
}


def error_code(error):
    if isinstance(error, ai.AIError):
        return error.code
    if isinstance(error, cloud.CloudError):
        return error.code if error.code in SIGN_IN_CODES else "offline" if error.code in ("offline", "network") else "provider_error"
    if isinstance(error, (urllib.error.URLError, TimeoutError, ConnectionError, OSError)):
        return "offline"
    return "unexpected"


def error_message(error):
    """Words to show for any failure; never a traceback or a Python error name."""
    code = error_code(error)
    if isinstance(error, ai.AIError) and error.message:
        return error.message
    if code == "unexpected":
        return "Something went wrong while making that. Nothing was changed; try again in a moment."
    return ai.friendly(code)


def error_title(error):
    return TITLES.get(error_code(error), "AI couldn't make that")


def needs_sign_in(error):
    return error_code(error) in SIGN_IN_CODES


# ------------------------------------------------------- background work
class Job:
    """One blocking call (an AI request) on a worker thread.

    The UI starts it, then polls state() from after() callbacks; Tk widgets
    are never touched from the worker. cancel() can't stop a request already
    on the network, but its answer is then thrown away, so nothing changes.

        job = Job(lambda: ai.make_notes(account, text=...)).start()
        ... job.state() -> "running" | "done" | "failed" | "cancelled"
    """

    def __init__(self, work, thread_factory=threading.Thread):
        self.work = work
        self.thread_factory = thread_factory
        self.result = None
        self.error = None
        self._done = threading.Event()
        self._cancelled = False
        self.thread = None

    def start(self):
        self.thread = self.thread_factory(target=self.run, daemon=True)
        self.thread.start()
        return self

    def run(self):
        try:
            self.result = self.work()
        except BaseException as error:  # shown to people via error_message
            self.error = error
        finally:
            self._done.set()

    def cancel(self):
        self._cancelled = True

    @property
    def cancelled(self):
        return self._cancelled

    def state(self):
        if self._cancelled:
            return "cancelled"
        if not self._done.is_set():
            return "running"
        return "failed" if self.error is not None else "done"


def progress_text(action, seconds):
    """The line under the spinner: what is happening, and reassurance as it runs long."""
    what = "Making notes" if action == "notes" else "Making questions"
    if seconds < 8:
        return f"{what}…"
    if seconds < 30:
        return f"{what}… a PDF or picture can take up to a minute."
    return f"{what}… still working. You can cancel and try a smaller file."


# ------------------------------------------------------------ the source
def source_kind(path):
    """'pdf', 'image' or '' for a chosen file."""
    suffix = Path(str(path or "")).suffix.lower()
    if suffix == PDF_SUFFIX:
        return "pdf"
    return "image" if suffix in IMAGE_SUFFIXES else ""


# ------------------------------------------------------------ PDF pages
def render_pdf_page(pdf_path, page, out_path):
    """Save page `page` (1-based) of a PDF as a PNG; returns the path or None.

    MemoryPal adds no PDF renderer of its own, so this uses only what is
    already a dependency: pypdf finds the page's pictures and Pillow saves
    the largest one as a PNG, which covers scanned pages and slides with a
    figure. A page with only text gives None, and the card says "From page
    N" with the PDF attached as its note instead.
    """
    try:
        page = int(page)
    except (TypeError, ValueError):
        return None
    if page < 1:
        return None
    try:
        from pypdf import PdfReader
    except Exception:
        return None
    import logging

    logging.getLogger("pypdf").setLevel(logging.ERROR)  # a damaged PDF just gives no picture
    try:
        reader = PdfReader(str(pdf_path))
        if page > len(reader.pages):
            return None
        best = None
        for embedded in reader.pages[page - 1].images:
            picture = embedded.image
            area = picture.width * picture.height
            if area >= 160 * 160 and (best is None or area > best[0]):
                best = (area, picture)
        if best is None:
            return None
        picture = best[1]
        if picture.mode not in ("RGB", "RGBA", "L"):
            picture = picture.convert("RGB")
        picture.save(out_path, "PNG")
        return Path(out_path)
    except Exception:
        return None


def page_images(pdf_path, pages, folder, name_stem):
    """{page: png path} for the pages that could be saved as pictures."""
    out = {}
    for page in sorted({p for p in pages if isinstance(p, int)}):
        saved = render_pdf_page(pdf_path, page, Path(folder) / f"{name_stem}-page{page}.png")
        if saved is not None:
            out[page] = str(saved)
    return out


# ---------------------------------------------------------------- staging
def staged_from_questions(questions, deck, title="", source="", pictures=None):
    """Set-builder rows ({"prompt", "answer", "kind": "ai", ...}) from AI questions.

    - picture source: every card made from it gets the picture as its image cue;
    - PDF source: a question from page N gets that page's picture when one
      could be saved (`pictures`), else "From page N" stays in its hook; the
      PDF is attached as its note either way.
    """
    pictures = pictures or {}
    kind = source_kind(source)
    if not kind:
        # Typed notes have no pages, whatever the AI says.
        questions = [dict(item, page=None) for item in questions]
    rows = []
    for made in ai.questions_to_cards(questions, deck, title):
        card, page = made["card"], made["page"]
        row = {
            "prompt": card.front,
            "answer": card.back,
            "kind": "ai",
            "pathway": card.pathway,
            "association": card.association,
            "page": page,
            "image": "",
            "text_file": "",
        }
        if kind == "image":
            row["image"] = str(source)
        elif kind == "pdf":
            row["text_file"] = str(source)
            if page and pictures.get(page):
                row["image"] = pictures[page]
        rows.append(row)
    return rows


def is_ai_item(item):
    return isinstance(item, dict) and (item.get("kind") == "ai" or str(item.get("pathway", "")).startswith(ai.AI_PATHWAY))


def notes_capture_fields(notes, deck="", source=""):
    """Capture fields (title, notes, chunks, text_file, image) for AI notes saved in a set."""
    body = ai.notes_text(notes)
    title = normalize_space(notes.get("title", "")) or "Study notes"
    chunks = []
    for section in notes.get("sections", []):
        heading = normalize_space(section.get("heading", ""))
        for bullet in section.get("bullets", []):
            chunks.append(f"{heading}: {bullet}" if heading else bullet)
    chunks.extend(f"{item['term']} => {item['definition']}" for item in notes.get("key_terms", []))
    kind = source_kind(source)
    return {
        "title": f"{deck}: {title}" if deck else title,
        "notes": f"{ai.AI_NOTE}\n{body}",
        "chunks": [chunk for chunk in chunks if normalize_space(chunk)] or [title],
        "text_file": str(source) if kind == "pdf" else "",
        "image": str(source) if kind == "image" else "",
    }


def is_ai_capture(capture):
    notes = capture.get("notes", "") if isinstance(capture, dict) else getattr(capture, "notes", "")
    return str(notes or "").startswith(ai.AI_NOTE)


def report_note(kind, content):
    """The feedback note an AI report starts with; the person adds what was wrong."""
    content = str(content or "").strip()
    if len(content) > 1500:
        content = content[:1500].rstrip() + "…"
    what = "AI notes" if kind == "notes" else "AI card"
    return f"{REPORT_CATEGORY} ({what}).\nWhat's wrong: \n\n--- The content ---\n{content}"


# ---------------------------------------------------------------- quizzes
def remember_round(prefs, question_ids):
    """Keep this round's question ids so the next round avoids them."""
    updated = normalize_preferences(prefs)
    updated["quiz_recent"] = [str(item) for item in question_ids][-QUIZ_RECENT_MAX:]
    return updated
