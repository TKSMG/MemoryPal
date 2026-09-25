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


def read_text_file(path):
    """Read a plain-text note whatever encoding Notepad or another app used."""
    raw = Path(path).read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw[3:].decode("utf-8", "replace")
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16", "replace")
    if len(raw) >= 4 and raw[1:2] == b"\x00" and raw[3:4] == b"\x00":
        return raw.decode("utf-16-le", "replace")  # UTF-16 without a byte order mark
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", "replace")


def rtf_to_text(data):
    """Plain text from an RTF document (WordPad, TextEdit), dropping formatting."""
    # Escaped braces and backslashes are text, not formatting: park them on
    # placeholder characters until the formatting braces are gone.
    backslash = chr(92)
    parked = {backslash * 2: chr(2), backslash + "{": chr(0), backslash + "}": chr(1)}
    for escaped, placeholder in parked.items():
        data = data.replace(escaped, placeholder)
    text = re.sub(r"\\'([0-9a-fA-F]{2})", lambda m: bytes([int(m.group(1), 16)]).decode("cp1252", "replace"), data)
    text = re.sub(r"\\u(-?\d+)\??", lambda m: chr(int(m.group(1)) % 65536), text)
    # Drop header groups (fonts, colours, styles, pictures) with their contents.
    text = re.sub(r"\{(?:\\\*)?\\(?:fonttbl|colortbl|stylesheet|info|pict|listtable|listoverridetable|generator)(?:[^{}]|\{[^{}]*\})*\}", "", text)
    text = re.sub(r"\\(?:par|line)\b ?", "\n", text)
    text = re.sub(r"\\tab\b ?", "\t", text)
    text = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", text)
    text = text.replace("{", "").replace("}", "")
    for escaped, placeholder in parked.items():
        text = text.replace(placeholder, escaped[1])
    return "\n".join(line.strip() for line in text.splitlines()).strip()


def extract_document_text(path):
    # Keep document import local and dependency-light. DOCX and RTF are parsed
    # directly; PDFs use pypdf/PyPDF2 when installed and otherwise the
    # built-in reader in pdftext.py.
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix in {".txt", ".md", ".csv"}:
        return read_text_file(source)
    if suffix == ".rtf":
        return rtf_to_text(read_text_file(source))
    if suffix == ".docx":
        with zipfile.ZipFile(source) as archive:
            xml = archive.read("word/document.xml")
        root = ET.fromstring(xml)
        w = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        pieces = []
        for paragraph in root.iter(f"{w}p"):
            parts = []
            for node in paragraph.iter():
                if node.tag == f"{w}t":
                    parts.append(node.text or "")
                elif node.tag == f"{w}tab":
                    parts.append("\t")
                elif node.tag in (f"{w}br", f"{w}cr"):
                    parts.append("\n")
            text = "".join(parts).strip()
            if text:
                pieces.append(text)
        return "\n".join(pieces)
    if suffix == ".pdf":
        for module_name in ("pypdf", "PyPDF2"):
            try:
                module = __import__(module_name)
                reader = module.PdfReader(str(source))
                text = "\n".join((page.extract_text() or "").strip() for page in reader.pages).strip()
                if text:
                    return text
            except Exception:
                continue
        from .pdftext import extract_pdf_text

        text = extract_pdf_text(source)
        if not text.strip():
            raise RuntimeError("This PDF has no text layer (it may be a scanned image). The file is attached; type the key points into the box.")
        return text
    if suffix == ".doc":
        raise RuntimeError("Older .doc files can be attached, but automatic extraction needs the file saved as .docx first.")
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
        for suffix in ("ingly", "edly", "ing", "ed", "es"):
            if token.endswith(suffix) and len(token) > len(suffix) + 3:
                token = token[: -len(suffix)]
                break
        else:
            if token.endswith("s") and not token.endswith(("ss", "us", "is")) and len(token) > 4:
                token = token[:-1]
        tokens.append(token)
    return tokens


def comparable_text(value):
    """Lower-case text with punctuation and extra spaces removed."""
    return normalize_space(re.sub(r"[^a-z0-9\s]", " ", (value or "").lower()))


def tokens_match(expected_token, response_token):
    """Equal, a clear abbreviation ("info"/"information"), or a small typo."""
    if expected_token == response_token:
        return True
    shorter, longer = sorted((expected_token, response_token), key=len)
    if len(shorter) >= 4 and longer.startswith(shorter):
        return True
    return len(shorter) >= 5 and SequenceMatcher(None, expected_token, response_token).ratio() >= 0.8


def answer_assessment(response, expected, context=""):
    # Score against the saved answer only. Context (the question, pathway,
    # association) used to be folded into the expected text, so a perfect
    # answer was marked down for not repeating the question. Context is only
    # used when there is no saved answer to compare with.
    response = normalize_space(response)
    expected_text = normalize_space(expected) or normalize_space(context)
    if not response:
        return {
            "score": 0,
            "quality": 1,
            "label": "Needs response",
            "bucket": "Again",
            "repetitions": 5,
            "detail": "Type an answer, transcript, caption, or media description first.",
        }

    response_plain, expected_plain = comparable_text(response), comparable_text(expected_text)
    expected_tokens = text_tokens(expected_text)
    response_tokens = text_tokens(response)
    expected_counts = Counter(expected_tokens)
    sequence = SequenceMatcher(None, response_plain, expected_plain).ratio() if expected_plain else 0

    if expected_plain and response_plain == expected_plain:
        score, missing = 100, []
    elif not expected_tokens:
        # Very short answers (numbers, initials, "yes") have no scorable
        # words, so they must match closely as a whole.
        score, missing = (round(100 * sequence) if sequence >= 0.9 else round(40 * sequence)), []
    else:
        unmatched = list(response_tokens)
        hits = 0
        matched_words = set()
        for word in expected_tokens:
            partner = next((token for token in unmatched if tokens_match(word, token)), None)
            if partner is not None:
                unmatched.remove(partner)
                hits += 1
                matched_words.add(word)
        weighted = hits / len(expected_tokens)
        coverage = len(matched_words) / len(expected_counts)
        if len(expected_counts) <= 2:
            score = round(100 * (0.5 * sequence + 0.5 * coverage))
        else:
            score = round(100 * (0.28 * sequence + 0.52 * coverage + 0.20 * weighted))
        score = min(100, score)
        missing = [word for word, _count in expected_counts.most_common(6) if word not in matched_words]

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
