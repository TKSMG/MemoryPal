"""Turn saved feedback notes into a report people can send or save.

Three ways out, all started by the person, never automatically:
- "Send" posts the report straight from the app through FormSubmit
  (formsubmit.co), a free form-to-email relay, so no mail account or
  password is needed on either side. FormSubmit asks the receiving address to
  confirm once: the very first send triggers an "Activate Form" email to
  FEEDBACK_EMAIL, and every send after that is delivered.
- "Email" opens the person's own mail app (or Gmail in the browser) with the
  report filled in, so they see exactly what is sent and press Send.
- "Save" writes a text file to attach by hand.

The report holds the notes plus basic app details (version of Windows, text
size, theme) to help reproduce problems, and never the profile name or any
study cards.
"""

import json
import platform
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

FEEDBACK_EMAIL = "memorypal09@gmail.com"
# Mail apps and browsers cut off very long mailto/Gmail links; beyond this the
# full report goes in a file to attach instead.
MAX_LINK_BODY = 1800
# FormSubmit's JSON endpoint. After the address is confirmed, FormSubmit also
# offers a random alias to use here instead of the plain address.
SEND_URL = f"https://formsubmit.co/ajax/{FEEDBACK_EMAIL}"
# FormSubmit tells forms apart by the page they come from; the desktop app has
# no page, so it names itself.
SEND_REFERER = "https://memorypal.app/desktop-feedback"
SEND_TIMEOUT = 20


class SendResult:
    """What happened to a direct send: sent, activation, offline or error."""

    def __init__(self, status, detail=""):
        self.status = status
        self.detail = detail

    @property
    def ok(self):
        return self.status == "sent"

    def __repr__(self):
        return f"SendResult({self.status!r}, {self.detail!r})"


def send_payload(subject, body, reply_to=""):
    payload = {
        "_subject": subject,
        "_template": "box",
        "_captcha": "false",
        "name": "MemoryPal desktop app",
        "message": body,
    }
    if reply_to:
        # FormSubmit makes this the email's Reply-To.
        payload["email"] = reply_to
    return payload


def read_send_response(raw):
    """SendResult for FormSubmit's JSON reply."""
    try:
        reply = json.loads(raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw)
    except ValueError:
        return SendResult("error", "The feedback service sent an unexpected reply.")
    message = str(reply.get("message", ""))
    if str(reply.get("success", "")).lower() == "true":
        return SendResult("sent", message)
    if "activat" in message.lower():
        return SendResult("activation", message)
    return SendResult("error", message or "The feedback service didn't accept the note.")


def send_report(subject, body, reply_to="", opener=None, timeout=SEND_TIMEOUT):
    """Post the report to FEEDBACK_EMAIL. Blocking: call it off the UI thread.

    `opener` stands in for urllib's urlopen (tests pass a fake one).
    """
    request = urllib.request.Request(
        SEND_URL,
        data=json.dumps(send_payload(subject, body, reply_to)).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Referer": SEND_REFERER,
            "Origin": SEND_REFERER.rsplit("/", 1)[0],
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) MemoryPal-Desktop/1.0",
        },
        method="POST",
    )
    try:
        with (opener or urllib.request.urlopen)(request, timeout=timeout) as response:
            return read_send_response(response.read())
    except urllib.error.HTTPError as exc:
        try:
            result = read_send_response(exc.read())
        except OSError:
            result = SendResult("error", "")
        if result.status == "error" and not result.detail.strip():
            result.detail = f"The feedback service answered with error {exc.code}."
        return result
    except (urllib.error.URLError, OSError) as exc:
        return SendResult("offline", str(getattr(exc, "reason", exc)))


def looks_like_email(text):
    text = (text or "").strip()
    name, _at, domain = text.partition("@")
    return bool(name) and "." in domain and " " not in text and not domain.startswith(".") and not domain.endswith(".")


def system_details(accessibility=None, theme=""):
    accessibility = accessibility or {}
    details = [
        ("App", "MemoryPal (desktop)"),
        ("System", f"{platform.system()} {platform.release()} ({platform.version()})"),
        ("Python", sys.version.split()[0]),
        ("Text size", accessibility.get("text_size", "Comfort")),
        ("Theme", theme or "unknown"),
    ]
    extras = [name.replace("_", " ") for name, value in accessibility.items() if value is True]
    if extras:
        details.append(("Comfort options", ", ".join(sorted(extras))))
    return details


def compose_report(entries, details):
    """(subject, plain-text body) for a list of FeedbackEntry objects."""
    entries = list(entries)
    rated = [entry.rating for entry in entries if entry.rating]
    average = f", average rating {sum(rated) / len(rated):.1f}/5" if rated else ""
    subject = f"MemoryPal feedback: {len(entries)} note{'s' if len(entries) != 1 else ''}{average}"
    lines = [f"MemoryPal feedback report ({datetime.now().strftime('%Y-%m-%d %H:%M')})", ""]
    for index, entry in enumerate(entries, 1):
        stars = f"{entry.rating}/5" if entry.rating else "no rating"
        lines.append(f"{index}. [{entry.category}] {entry.page} | {stars} | {entry.created_at}")
        lines.extend(f"   {line}" for line in (entry.note or "").splitlines() or [""])
        lines.append("")
    lines.append("About this computer")
    lines.extend(f"- {name}: {value}" for name, value in details)
    return subject, "\n".join(lines).rstrip() + "\n"


def link_body(body, attachment_name=None):
    """The body to put in an email link, shortened if the link would be too long."""
    if len(body) <= MAX_LINK_BODY:
        return body
    note = f"\n\n[The full report is longer than an email link allows. It was saved as {attachment_name}; please attach that file.]" if attachment_name else "\n\n[Report shortened.]"
    return body[:MAX_LINK_BODY - len(note)].rstrip() + "\n..." + note


def mailto_url(subject, body):
    return f"mailto:{FEEDBACK_EMAIL}?subject={quote(subject)}&body={quote(body)}"


def gmail_url(subject, body):
    return f"https://mail.google.com/mail/?view=cm&fs=1&to={FEEDBACK_EMAIL}&su={quote(subject)}&body={quote(body)}"


def has_mail_app():
    """True when Windows has an app registered to open email links."""
    if not sys.platform.startswith("win"):
        return True
    try:
        import winreg

        key_path = r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\mailto\UserChoice"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            prog_id, _kind = winreg.QueryValueEx(key, "ProgId")
        return bool(prog_id)
    except OSError:
        return False


def default_report_name():
    return f"MemoryPal-feedback-{datetime.now().strftime('%Y%m%d-%H%M')}.txt"


def default_report_folder():
    documents = Path.home() / "Documents"
    return documents if documents.is_dir() else Path.home()


def save_report(path, subject, body):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    header = f"To: {FEEDBACK_EMAIL}\nSubject: {subject}\n\n"
    path.write_text(header + body, encoding="utf-8")
    return path
