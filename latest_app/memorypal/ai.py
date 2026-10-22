"""AI study notes and questions through the MemoryPal cloud, standard library only.

The apps never hold an AI key: they call the Supabase Edge Function "ai"
(supabase/functions/ai) with the signed-in person's access token, and the
function calls Google Gemini. The phone has the same logic in
mobile/src/cloud/ai.ts.

    notes = make_notes(account, text="...", file_path="lecture.pdf", style="one line per date")
    questions = make_questions(account, text=notes_text(notes), count=10, avoid=[c.front for c in cards])
    made = questions_to_cards(questions, deck="Biology")   # [{"card": Card, "page": 3 or None}]

Network calls block; run them on a worker thread.
"""

import base64
import json
import re
import urllib.error
import urllib.request
from pathlib import Path

from . import cloud

TIMEOUT = 120  # a PDF can take Gemini a while
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_QUESTIONS = 30
MAX_STYLE_CHARS = 500
MAX_CONTEXT_CHARS = 240
MAX_EXAMPLES = 20
MAX_QUESTION_CHARS = 600  # room for a short case or scenario question
QUESTION_TYPES = ("short", "choice", "truefalse", "cloze")
MIME_BY_SUFFIX = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".heic": "image/heic",
    ".heif": "image/heic",
}
AI_PATHWAY = "Made with AI"
AI_NOTE = "Made with AI, check it."

FRIENDLY = {
    "not_signed_in": "Sign in to your MemoryPal account to use AI notes.",
    "signed_out": "Sign in to your MemoryPal account to use AI notes.",
    "second_step": "Finish two-step sign-in first: enter the code from your authenticator app.",
    "limit_reached": "You've used today's AI requests. They reset tomorrow, and everything else keeps working.",
    "file_too_large": "That file is larger than 8 MB. Try a smaller file, or a few pages at a time.",
    "unsupported_file": "AI notes can read PDFs and PNG, JPEG or WEBP pictures.",
    "bad_request": "Add some notes or choose a file first.",
    "blocked": "This material can't be used for AI study notes.",
    "busy": "The AI is busy right now. Wait a minute and try again.",
    "busy_today": "The AI has had a lot of requests today and is paused until tomorrow. Everything else keeps working.",
    "provider_error": "The AI service had a problem. Try again later.",
    "not_configured": "AI notes aren't set up for this copy of MemoryPal yet.",
    "offline": "Couldn't reach the MemoryPal cloud. Check the internet connection and try again.",
    "bad_answer": "The AI's answer couldn't be read. Try again.",
}


class AIError(Exception):
    """A failure with a message that can be shown to people as it is."""

    def __init__(self, code, message=None):
        self.code = code
        self.message = message or FRIENDLY.get(code, FRIENDLY["provider_error"])
        super().__init__(self.message)


def friendly(code):
    return FRIENDLY.get(code, FRIENDLY["provider_error"])


# ------------------------------------------------------------------ input
def file_payload(path):
    """{"data": base64, "mime_type"} for a PDF or picture; raises AIError."""
    source = Path(path)
    mime = MIME_BY_SUFFIX.get(source.suffix.lower())
    if not mime:
        raise AIError("unsupported_file")
    try:
        size = source.stat().st_size
    except OSError:
        raise AIError("bad_request", "That file couldn't be opened.") from None
    if size > MAX_FILE_BYTES:
        raise AIError("file_too_large")
    return {"data": base64.b64encode(source.read_bytes()).decode("ascii"), "mime_type": mime}


def access_token(auth):
    """The bearer token from an access token string, a cloud.Session, or a cloud.Account."""
    if isinstance(auth, str):
        token = auth
    elif isinstance(auth, cloud.Session):
        token = auth.access_token
    elif auth is not None and hasattr(auth, "active_session"):
        try:
            token = auth.active_session().access_token
        except cloud.CloudError as error:
            raise AIError(error.code if error.code in FRIENDLY else "not_signed_in", error.message) from None
    else:
        token = ""
    if not token:
        raise AIError("not_signed_in")
    return token


# -------------------------------------------------------------- transport
def call(auth, body, opener=None, timeout=TIMEOUT):
    """POST to the "ai" function; returns its decoded JSON or raises AIError."""
    url, key = cloud.config()
    if not url or not key:
        raise AIError("not_configured")
    token = access_token(auth)
    request = urllib.request.Request(
        f"{url}/functions/v1/ai",
        data=json.dumps(body).encode("utf-8"),
        headers={"apikey": key, "Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with (opener or urllib.request.urlopen)(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        raise error_from(exc.code, exc.read()) from None
    except (urllib.error.URLError, OSError, TimeoutError):
        raise AIError("offline") from None
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise AIError("bad_answer") from None
    if not isinstance(data, dict) or data.get("ok") is not True:
        raise error_from(200, raw)
    return data


def error_from(status, raw):
    try:
        detail = json.loads((raw or b"{}").decode("utf-8", "replace"))
    except (ValueError, RecursionError):
        detail = {}
    code = str(detail.get("error") or "") if isinstance(detail, dict) else ""
    if code in FRIENDLY:
        return AIError(code)
    if status == 401:
        return AIError("not_signed_in")
    if status == 413:
        return AIError("file_too_large")
    if status == 429:
        return AIError("limit_reached")
    if status == 404:
        return AIError("not_configured")
    return AIError("provider_error")


# ------------------------------------------------------------- validation
def clip(value, limit):
    return re.sub(r"\s+", " ", value).strip()[:limit] if isinstance(value, str) else ""


def parse_notes(raw):
    """Clean notes: {"title", "sections": [{"heading", "bullets"}], "key_terms": [{"term", "definition"}]}."""
    data = raw if isinstance(raw, dict) else {}
    sections = []
    for section in data.get("sections") if isinstance(data.get("sections"), list) else []:
        section = section if isinstance(section, dict) else {}
        bullets = [clip(b, 300) for b in (section.get("bullets") if isinstance(section.get("bullets"), list) else [])]
        item = {"heading": clip(section.get("heading"), 120), "bullets": [b for b in bullets if b][:12]}
        if item["heading"] or item["bullets"]:
            sections.append(item)
    terms = []
    for term in data.get("key_terms") if isinstance(data.get("key_terms"), list) else []:
        term = term if isinstance(term, dict) else {}
        item = {"term": clip(term.get("term"), 80), "definition": clip(term.get("definition"), 300)}
        if item["term"] and item["definition"]:
            terms.append(item)
    return {"title": clip(data.get("title"), 120) or "Study notes", "sections": sections[:12], "key_terms": terms[:30]}


def question_key(text):
    return " ".join(re.sub(r"[\W_]+", " ", text.lower()).split())


def parse_questions(raw, count=MAX_QUESTIONS, avoid=()):
    """Clean questions: [{"type", "question", "answer", "options", "context", "page"}], at most `count`.

    "context" is the sentence from the material the answer comes from ("" when
    the model gave none).
    """
    items = raw if isinstance(raw, list) else (raw.get("questions") if isinstance(raw, dict) else None)
    seen = {question_key(str(text)) for text in avoid or ()}
    out = []
    for item in items if isinstance(items, list) else []:
        if len(out) >= min(int(count), MAX_QUESTIONS):
            break
        item = item if isinstance(item, dict) else {}
        kind = str(item.get("type") or "").lower()
        question, answer = clip(item.get("question"), MAX_QUESTION_CHARS), clip(item.get("answer"), 300)
        if kind not in QUESTION_TYPES or not question or not answer:
            continue
        options = []
        if kind == "choice":
            keys, wrong = {question_key(answer)}, []
            for option in item.get("options") if isinstance(item.get("options"), list) else []:
                text = clip(option, 200)
                if text and question_key(text) not in keys:
                    keys.add(question_key(text))
                    wrong.append(text)
            if len(wrong) < 3:
                continue
            options = [answer] + wrong[:3]
        elif kind == "truefalse":
            verdict = re.sub(r"[^a-z]", "", answer.lower())
            if verdict not in ("true", "false"):
                continue
            answer = verdict.capitalize()
            options = ["True", "False"]
        elif kind == "cloze":
            question = re.sub(r"_{3,}", "_____", question)
            if "_____" not in question:
                at = question.lower().find(answer.lower())
                if at < 0:
                    continue
                question = question[:at] + "_____" + question[at + len(answer):]
        key = question_key(question)
        if not key or key in seen:
            continue
        seen.add(key)
        page = item.get("page")
        page = int(page) if isinstance(page, (int, float)) and not isinstance(page, bool) and 1 <= page <= 10000 else None
        out.append({"type": kind, "question": question, "answer": answer, "options": options, "context": clip(item.get("context"), MAX_CONTEXT_CHARS), "page": page})
    return out


# -------------------------------------------------------------- the calls
def example_lines(examples):
    """Teacher's past questions from a string (one per line) or a list, cleaned and capped."""
    items = examples.splitlines() if isinstance(examples, str) else list(examples or ())
    cleaned = [clip(str(item).lstrip("-•* \t"), 400) for item in items]
    return [item for item in cleaned if item][:MAX_EXAMPLES]


def request_body(action, text="", file_path=None, file=None, count=10, avoid=(), title="", style="", examples=()):
    body = {"action": action, "text": (text or "").strip()}
    if file_path:
        body["file"] = file_payload(file_path)
    elif file:
        body["file"] = {"data": file["data"], "mime_type": file["mime_type"]}
    if not body["text"] and "file" not in body:
        raise AIError("bad_request")
    if action == "questions":
        body["count"] = max(1, min(MAX_QUESTIONS, int(count)))
        body["avoid"] = [str(front) for front in avoid or () if str(front).strip()][:300]
        if example_lines(examples):
            body["examples"] = example_lines(examples)
    if title:
        body["title"] = str(title)[:120]
    style = clip(style, MAX_STYLE_CHARS)
    if style:
        body["style"] = style
    return body


def make_notes(auth, text="", file_path=None, file=None, title="", style="", opener=None, timeout=TIMEOUT):
    """Study notes from text and/or a file (path, or {"data", "mime_type"}).

    `style` is how the learner wants them laid out, in their own words
    ("one line per date: year, then what happened"); "" for the usual notes.

    `auth` is a cloud.Account, a cloud.Session or an access token. Returns
    parse_notes() output plus "remaining" (requests left today, or None).
    """
    data = call(auth, request_body("notes", text, file_path, file, title=title, style=style), opener, timeout)
    notes = parse_notes(data.get("result"))
    notes["remaining"] = data.get("remaining") if isinstance(data.get("remaining"), int) else None
    return notes


def make_questions(auth, text="", file_path=None, file=None, count=10, avoid=(), title="", style="", examples=(), opener=None, timeout=TIMEOUT):
    """Varied practice questions; returns {"questions": parse_questions(...), "remaining"}.

    `examples` are questions the learner's teacher has asked (a list, or one
    per line): the AI follows their pattern. Without them or a `style`, the
    server takes the pattern from `avoid`, the set's existing questions.
    """
    data = call(auth, request_body("questions", text, file_path, file, count, avoid, title, style, examples), opener, timeout)
    return {
        "questions": parse_questions(data.get("result"), count, avoid),
        "remaining": data.get("remaining") if isinstance(data.get("remaining"), int) else None,
    }


# ------------------------------------------------------------ conversions
def notes_text(notes):
    """Notes as plain text, for a capture's notes box or as input to make_questions."""
    lines = [notes.get("title", "")]
    for section in notes.get("sections", []):
        lines.append("")
        if section.get("heading"):
            lines.append(section["heading"])
        lines.extend(f"- {bullet}" for bullet in section.get("bullets", []))
    if notes.get("key_terms"):
        lines.append("")
        lines.append("Key terms")
        lines.extend(f"- {item['term']} :: {item['definition']}" for item in notes["key_terms"])
    return "\n".join(lines).strip()


def question_card_fields(question):
    """(front, back) for one AI question."""
    if question["type"] == "truefalse":
        return f"True or false: {question['question']}", question["answer"]
    # Multiple-choice options aren't stored: the quiz makes its own from the deck.
    return question["question"], question["answer"]


def questions_to_cards(questions, deck, title=""):
    """Cards from AI questions, marked as AI-made: [{"card": Card, "page": int or None}].

    The pathway starts with "Made with AI" and the association asks the
    person to check the card (no new card field, so sync is unchanged). When
    a question came from a PDF page, attach that page's image to the card.
    """
    from .models import Card

    made = []
    for question in questions:
        front, back = question_card_fields(question)
        page = question.get("page")
        note = card_note(question)
        made.append({
            "card": Card(deck=deck or "General", front=front, back=back, pathway=f"{AI_PATHWAY} > {title or deck or 'Notes'}", association=note),
            "page": page,
        })
    return made


def card_note(question):
    """The hook text for an AI card: check it, which page, and the source sentence."""
    note = AI_NOTE + (f" From page {question['page']}." if question.get("page") else "")
    context = question.get("context") or ""
    return note + (f' Source: "{context}"' if context else "")


def is_ai_card(card):
    return str(getattr(card, "pathway", "") or "").startswith(AI_PATHWAY)
