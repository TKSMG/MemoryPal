import ctypes
import random
import re
import sys
import zipfile
from collections import Counter
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from uuid import uuid4
import xml.etree.ElementTree as ET


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
    # Pasted notes are usually messy, so this accepts common separators before
    # falling back to sentences or comma-separated fragments.
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


def extract_document_text(path):
    # Keep document import local and dependency-light. DOCX is parsed directly;
    # PDFs use pypdf/PyPDF2 if the user's Python environment already has one.
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix in {".txt", ".md", ".csv"}:
        try:
            return source.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return source.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".docx":
        with zipfile.ZipFile(source) as archive:
            xml = archive.read("word/document.xml")
        root = ET.fromstring(xml)
        namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        pieces = []
        for paragraph in root.findall(".//w:p", namespace):
            text = "".join(node.text or "" for node in paragraph.findall(".//w:t", namespace))
            if text.strip():
                pieces.append(text.strip())
        return "\n".join(pieces)
    if suffix == ".pdf":
        for module_name in ("pypdf", "PyPDF2"):
            try:
                module = __import__(module_name)
                reader = module.PdfReader(str(source))
                return "\n".join((page.extract_text() or "").strip() for page in reader.pages).strip()
            except Exception:
                continue
        raise RuntimeError("PDF text extraction needs pypdf or PyPDF2 installed for this Python environment.")
    if suffix == ".doc":
        raise RuntimeError("Older .doc files can be attached, but automatic extraction needs the file converted to .docx first.")
    return ""


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


def hangman_hint(text):
    def mask(word):
        if len(word) <= 1 or not word[0].isalnum():
            return word
        return word[0] + re.sub(r"[A-Za-z0-9]", "_", word[1:])

    return " ".join(mask(word) for word in (text or "").split())


def salient_keywords(text, count=5):
    tokens = text_tokens(text)
    if not tokens:
        return []
    ranked = Counter(tokens).most_common(count)
    return [word.capitalize() for word, _freq in ranked]


MNEMONIC_TEMPLATES = [
    "Picture {front} standing right next to {back_short} - the image alone should pull the rest back.",
    "Say it like a headline: \"{front} means {back_short}.\" Repeat it out loud twice.",
    "Link {front} to something absurd: imagine {back_short} bursting out of it.",
    "Break it down: {front} -> {back_short}. Say the arrow out loud as \"leads to.\"",
    "Give {front} a nickname built from {back_short} and picture that nickname on a sign.",
]


def mnemonic_sentence(front, back):
    front_text = normalize_space(front) or "this term"
    back_words = salient_keywords(back, 4)
    back_short = ", ".join(back_words) if back_words else normalize_space(back)[:60]
    template = random.choice(MNEMONIC_TEMPLATES)
    return template.format(front=front_text, back_short=back_short or "the answer")
