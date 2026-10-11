"""Password strength, a leaked-password check, and a sign-in attempt limiter.

These run on the person's device to give quick, friendly feedback. The real
limits are enforced by the server (Supabase Auth's rate limits and password
policy, see CLOUD_SYNC_SETUP.md), because anything on a device can be
bypassed. mobile/src/core/security.ts is a line-by-line port (parity tests).
"""

import hashlib
import re
import time

MIN_PASSWORD = 10

# The most-used passwords (and easy variants are caught by the checks below).
COMMON_PASSWORDS = {
    "123456", "password", "12345678", "qwerty", "123456789", "12345", "1234", "111111", "1234567", "dragon",
    "123123", "baseball", "abc123", "football", "monkey", "letmein", "696969", "shadow", "master", "666666",
    "qwertyuiop", "123321", "mustang", "1234567890", "michael", "654321", "superman", "1qaz2wsx", "7777777",
    "121212", "000000", "qazwsx", "123qwe", "killer", "trustno1", "jordan", "jennifer", "zxcvbnm", "asdfgh",
    "hunter", "buster", "soccer", "harley", "batman", "andrew", "tigger", "sunshine", "iloveyou", "2000",
    "charlie", "robert", "thomas", "hockey", "ranger", "daniel", "starwars", "klaster", "112233", "george",
    "computer", "michelle", "jessica", "pepper", "1111", "zxcvbn", "555555", "11111111", "131313", "freedom",
    "777777", "pass", "maggie", "159753", "aaaaaa", "ginger", "princess", "joshua", "cheese", "amanda",
    "summer", "love", "ashley", "nicole", "chelsea", "biteme", "matthew", "access", "yankees", "987654321",
    "dallas", "austin", "thunder", "taylor", "matrix", "welcome", "admin", "passw0rd", "password1", "password123",
    "welcome1", "qwerty123", "iloveyou1", "abcdef", "abcd1234", "changeme", "secret", "login", "memorypal",
    "memory", "remember", "flashcards", "student", "teacher", "school", "football1", "baseball1", "letmein1",
}

SEQUENCES = ("abcdefghijklmnopqrstuvwxyz", "0123456789", "qwertyuiop", "asdfghjkl", "zxcvbnm")


def character_classes(password):
    return sum(bool(re.search(pattern, password)) for pattern in (r"[a-z]", r"[A-Z]", r"[0-9]", r"[^A-Za-z0-9]"))


def predictable(password):
    """True when most of the password is one repeated character or a keyboard/alphabet run."""
    text = password.lower()
    if len(text) < 4:
        return False
    if len(set(text)) <= 2:
        return True
    longest = 0
    for sequence in SEQUENCES:
        for direction in (sequence, sequence[::-1]):
            run = 0
            for previous, current in zip(text, text[1:]):
                if direction.find(previous + current) >= 0:
                    run = run + 1 if run else 2
                else:
                    run = 0
                longest = max(longest, run)
    return longest >= max(4, int(len(text) * 0.6))


def password_problems(password, email=""):
    """Plain-language reasons a password is too weak (empty list = acceptable)."""
    password = password or ""
    problems = []
    if len(password) < MIN_PASSWORD:
        problems.append(f"Use at least {MIN_PASSWORD} characters. A few unrelated words work well.")
    stripped = re.sub(r"[^a-z]", "", password.lower())
    if password.lower() in COMMON_PASSWORDS or (len(stripped) >= 4 and stripped in COMMON_PASSWORDS):
        problems.append("This is one of the most common passwords. Choose something less guessable.")
    name = re.sub(r"[^a-z0-9]", "", (email or "").split("@", 1)[0].lower())
    if len(name) >= 3 and name in re.sub(r"[^a-z0-9]", "", password.lower()):
        problems.append("Don't use your email name in your password.")
    if predictable(password):
        problems.append("Avoid repeated letters and runs like 1234 or qwerty.")
    if len(password) >= MIN_PASSWORD and character_classes(password) < 2 and len(password) < 16:
        problems.append("Mix in a number, a capital or a symbol, or make it longer.")
    return problems


def password_strength(password, email=""):
    """0 (very weak) to 4 (strong), for a strength meter."""
    password = password or ""
    if not password:
        return 0
    score = 0
    if len(password) >= MIN_PASSWORD:
        score += 1
    if len(password) >= 14:
        score += 1
    # Length counts most: a long passphrase is strong even without symbols.
    if character_classes(password) >= 3 or len(password) >= 20:
        score += 1
    if len(password) >= 24 or (len(password) >= 12 and character_classes(password) == 4):
        score += 1
    if password_problems(password, email):
        score = min(score, 1)
    return score


STRENGTH_LABELS = ("Very weak", "Weak", "Fair", "Good", "Strong")


def pwned_count(password, opener=None, timeout=8):
    """How often this password appears in known data breaches (Pwned Passwords).

    k-anonymity: only the first five characters of the password's SHA-1 hash
    leave the device; the match is done here. Returns None if the service
    can't be reached (the check is skipped rather than blocking sign-up).
    """
    import urllib.error
    import urllib.request

    digest = hashlib.sha1((password or "").encode("utf-8")).hexdigest().upper()
    prefix, suffix = digest[:5], digest[5:]
    request = urllib.request.Request(f"https://api.pwnedpasswords.com/range/{prefix}", headers={"Add-Padding": "true", "User-Agent": "MemoryPal"})
    try:
        with (opener or urllib.request.urlopen)(request, timeout=timeout) as response:
            text = response.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError, TimeoutError):
        return None
    for line in text.splitlines():
        candidate, _sep, count = line.strip().partition(":")
        if candidate == suffix:
            return int(count or 0)
    return 0


class AttemptLimiter:
    """Slows repeated failed attempts on this device (the server enforces the real limit).

    After FREE_TRIES failures for the same email, each further try must wait,
    starting at 30 seconds and doubling up to 15 minutes. A success clears it.
    """

    FREE_TRIES = 5
    FIRST_WAIT = 30
    MAX_WAIT = 15 * 60
    FORGET_AFTER = 60 * 60

    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.failures = {}  # key -> (count, last failure time)

    def wait_seconds(self, key):
        count, last = self.failures.get(key.strip().lower(), (0, 0.0))
        if count < self.FREE_TRIES or self.clock() - last > self.FORGET_AFTER:
            return 0
        wait = min(self.MAX_WAIT, self.FIRST_WAIT * 2 ** (count - self.FREE_TRIES))
        return max(0, int(round(last + wait - self.clock())))

    def failed(self, key):
        key = key.strip().lower()
        count, last = self.failures.get(key, (0, 0.0))
        if self.clock() - last > self.FORGET_AFTER:
            count = 0
        self.failures[key] = (count + 1, self.clock())

    def succeeded(self, key):
        self.failures.pop(key.strip().lower(), None)


def wait_message(seconds):
    if seconds >= 90:
        return f"Too many tries. Please wait about {round(seconds / 60)} minutes before trying again."
    return f"Too many tries. Please wait {seconds} seconds before trying again."
