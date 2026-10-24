"""Two-way sync of a profile with the person's cloud account: the pure logic.

Everything that syncs becomes a record: ``card:<id>``, ``capture:<id>``,
``deck:<set name>`` (a set's details), ``settings:profile``, and each device's own review counts
(``activity:<day>:<device>``, ``practiced:<device>``). Counts are kept per
device and added up, so two devices reviewing on the same day both count.

Each device remembers the records as they were at its last sync (the
"base"). A record changed on only one side simply wins; a record changed on
both sides is merged field by field against the base. When both changed the
same card's review schedule, the side with more reviews wins, so practice is
never lost. Deletions travel as tombstones, and an edit beats a delete.

The network side lives in cloud.py; mobile/src/core/sync.ts is a line-by-line
port checked by the parity tests.
"""

SETTINGS_KEY = "settings:profile"
SETTINGS_FIELDS = ("daily_goal", "accessibility", "onboarding", "study_plan", "nav_order")
SCHEDULE_FIELDS = ("interval", "repetitions", "ease", "lapses", "last_score", "last_result", "next_review", "buried_until")
COUNT_KINDS = ("activity", "practiced")
KINDS = ("card", "capture", "deck", "settings") + COUNT_KINDS


def count_of(data):
    """A record's review count; anything malformed counts as nothing."""
    try:
        return max(0, int((data if isinstance(data, dict) else {}).get("count", 0) or 0))
    except (TypeError, ValueError, OverflowError):
        return 0


def whole(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError, OverflowError):
        return 0


def kind_of(key):
    return key.split(":", 1)[0]


def known_key(key):
    """A record key this app understands (``<kind>:...``).

    Anything else in the cloud is ignored: kept in the base it would be
    pushed back on every sync and refused by the database, stopping sync.
    """
    return isinstance(key, str) and ":" in key and kind_of(key) in KINDS


def known_only(records):
    return {key: data for key, data in records.items() if known_key(key)}


def device_of(key):
    """The device a count record belongs to (the part after the last colon)."""
    return key.rsplit(":", 1)[1] if kind_of(key) in COUNT_KINDS else ""


def other_device_counts(base, device_id):
    """Review counts other devices have reported: ({day: count}, practiced)."""
    activity, practiced = {}, 0
    for key, data in base.items():
        if kind_of(key) not in COUNT_KINDS or device_of(key) == device_id or not isinstance(data, dict):
            continue
        count = count_of(data)
        if kind_of(key) == "activity":
            day = str(data.get("day", ""))
            activity[day] = activity.get(day, 0) + count
        else:
            practiced += count
    return activity, practiced


def records_from_payload(payload, device_id, base):
    """Every record this device holds right now, as key -> data."""
    records = {}
    for card in payload.get("cards", []):
        records[f"card:{card['id']}"] = dict(card)
    for capture in payload.get("captures", []):
        records[f"capture:{capture['id']}"] = dict(capture)
    for info in payload.get("decks", []):
        records[f"deck:{info['id']}"] = dict(info)
    records[SETTINGS_KEY] = {name: payload.get(name) for name in SETTINGS_FIELDS}
    others_activity, others_practiced = other_device_counts(base, device_id)
    # This device's share is whatever the local totals hold beyond what the
    # other devices reported.
    for day, total in sorted(payload.get("activity", {}).items()):
        own = whole(total) - others_activity.get(day, 0)
        if own > 0:
            records[f"activity:{day}:{device_id}"] = {"day": day, "count": own}
    own_practiced = max(0, whole(payload.get("practiced", 0)) - others_practiced)
    records[f"practiced:{device_id}"] = {"count": own_practiced}
    # Other devices' counts, as last synced.
    for key, data in base.items():
        if kind_of(key) in COUNT_KINDS and device_of(key) != device_id:
            records[key] = data
    return records


def payload_from_records(payload, records):
    """A new payload with the synced records applied (feedback is untouched)."""
    result = dict(payload)
    local_order = [f"card:{card['id']}" for card in payload.get("cards", [])]
    card_keys = [key for key in records if kind_of(key) == "card"]
    known = [key for key in local_order if key in records]
    new = sorted((key for key in card_keys if key not in set(local_order)), key=lambda key: str(records[key].get("created_at", "")), reverse=True)
    result["cards"] = [dict(records[key]) for key in new + known]
    capture_order = [f"capture:{item['id']}" for item in payload.get("captures", [])]
    capture_keys = [key for key in records if kind_of(key) == "capture"]
    new_captures = sorted((key for key in capture_keys if key not in set(capture_order)), key=lambda key: str(records[key].get("created_at", "")), reverse=True)
    result["captures"] = [dict(records[key]) for key in new_captures + [key for key in capture_order if key in records]]
    deck_order = [f"deck:{item['id']}" for item in payload.get("decks", [])]
    deck_keys = sorted(key for key in records if kind_of(key) == "deck" and key not in set(deck_order))
    result["decks"] = [dict(records[key]) for key in [key for key in deck_order if key in records] + deck_keys]
    settings = records.get(SETTINGS_KEY) or {}
    for name in SETTINGS_FIELDS:
        if name in settings and settings[name] is not None:
            result[name] = settings[name]
    activity, practiced = {}, 0
    for key, data in records.items():
        if kind_of(key) == "activity" and isinstance(data, dict):
            day = str(data.get("day", ""))
            activity[day] = activity.get(day, 0) + count_of(data)
        elif kind_of(key) == "practiced":
            practiced += count_of(data)
    result["activity"] = {day: count for day, count in sorted(activity.items()) if count > 0}
    result["practiced"] = practiced
    return result


def progress(card):
    """How much review a card version carries: more reviews wins a schedule conflict."""
    return (whole(card.get("repetitions", 0)) + whole(card.get("lapses", 0)), str(card.get("next_review", "")))


def schedule_winner_of(base, local, remote):
    """Whose review schedule to keep when both devices reviewed the same card.

    A miss on either side wins, so a forgotten card comes back soon rather
    than being pushed weeks out; otherwise the side with more reviews wins.
    """
    lapses_before = whole(base.get("lapses", 0))
    local_missed = whole(local.get("lapses", 0)) > lapses_before
    remote_missed = whole(remote.get("lapses", 0)) > lapses_before
    if local_missed != remote_missed:
        return local if local_missed else remote
    return local if progress(local) > progress(remote) else remote


def unreviewed(key, data):
    return kind_of(key) == "card" and isinstance(data, dict) and whole(data.get("repetitions", 0)) == 0 and whole(data.get("lapses", 0)) == 0


def merge_record(key, base, local, remote):
    """Merge two versions of a record that both changed since `base`."""
    if local is None and remote is None:
        return None
    if local is None:
        return remote  # an edit on the other device beats a delete here
    if remote is None:
        return local
    base = base or {}
    merged = {}
    schedule_winner = None
    if kind_of(key) == "card" and any(
        local.get(name) != remote.get(name) and local.get(name) != base.get(name) and remote.get(name) != base.get(name)
        for name in SCHEDULE_FIELDS
    ):
        schedule_winner = schedule_winner_of(base, local, remote)
    for name in sorted(set(local) | set(remote)):
        mine, theirs, was = local.get(name), remote.get(name), base.get(name)
        if schedule_winner is not None and name in SCHEDULE_FIELDS:
            value = schedule_winner.get(name)
        elif mine == theirs:
            value = mine
        elif mine == was:
            value = theirs
        elif theirs == was:
            value = mine
        elif key == SETTINGS_KEY and isinstance(mine, dict) and isinstance(theirs, dict):
            # Settings groups (accessibility, the study plan) merge one level
            # deeper, so changing text size on one device and motion on
            # another keeps both.
            value = merge_record("settings:group", was if isinstance(was, dict) else {}, mine, theirs)
        else:
            value = theirs  # both changed the same field: the cloud copy wins
        merged[name] = value
    return merged


class SyncPlan:
    def __init__(self, push, apply, final):
        self.push = push      # key -> data, or None to delete in the cloud
        self.apply = apply    # key -> data, or None to delete here
        self.final = final    # key -> data: everything as it stands after sync (the next base)

    def __repr__(self):
        return f"SyncPlan(push={len(self.push)}, apply={len(self.apply)}, final={len(self.final)})"


def plan_sync(local, base, remote):
    """Decide what to send, what to change here, and the new base.

    local:  key -> data held on this device now
    base:   key -> data as of the last successful sync
    remote: key -> data (or None if deleted) for cloud records changed since then
    """
    local, base, remote = known_only(local), known_only(base), known_only(remote)
    push, apply, final = {}, {}, {}
    for key in sorted(set(local) | set(base) | set(remote)):
        mine = local.get(key)
        was = base.get(key)
        theirs = remote[key] if key in remote else was
        local_changed = mine != was
        remote_changed = key in remote and theirs != was
        if key in remote and theirs is None and was is None and unreviewed(key, mine):
            # A card deleted elsewhere that this device never synced or reviewed
            # (a starter card on a new install) stays deleted.
            local_changed, remote_changed = False, True
        if remote_changed and local_changed:
            result = merge_record(key, was, mine, theirs)
        elif remote_changed:
            result = theirs
        else:
            result = mine
        if result != theirs:  # the cloud doesn't hold this version yet
            push[key] = result
        if result != mine:
            apply[key] = result
        if result is not None:
            final[key] = result
    return SyncPlan(push, apply, final)


def apply_plan(payload, local, plan):
    """The payload after applying the plan's changes to this device's records."""
    records = dict(local)
    for key, data in plan.apply.items():
        if data is None:
            records.pop(key, None)
        else:
            records[key] = data
    return payload_from_records(payload, records)


# ------------------------------------------------- syncing through a drive
# With a file store (Google Drive) every device writes only its own file:
# all its records, each with a stamp saying when that version was made.
# Building "remote" takes each record's newest copy across all files, so a
# device that hasn't synced for a while can't undo newer changes, and no
# two devices ever write the same file. Deletions stay in the files as
# tombstones (data None) so they reach devices that were away.

FILE_PREFIX = "memorypal-"
FILE_FORMAT = 1
STAMP_DIGITS = (13, 6)


def file_name(device_id):
    return f"{FILE_PREFIX}{device_id}.json"


def stamp_parts(stamp):
    """(milliseconds, counter) of a stamp, or None when it isn't one."""
    parts = stamp.split(":", 2) if isinstance(stamp, str) else []
    if len(parts) != 3 or not parts[2] or not all(
        len(part) == size and part.isdigit() for part, size in zip(parts, STAMP_DIGITS)
    ):
        return None
    return int(parts[0]), int(parts[1])


def next_stamp(newest, device_id, now_ms):
    """A stamp newer than `newest` (the newest stamp seen anywhere).

    Normally it is the clock time; a device whose clock runs behind still
    moves past what it has seen, by counting up from it.
    """
    seen = stamp_parts(newest) or (0, 0)
    ms, count = (int(now_ms), 0) if int(now_ms) > seen[0] else (seen[0], seen[1] + 1)
    return f"{ms:0{STAMP_DIGITS[0]}d}:{count:0{STAMP_DIGITS[1]}d}:{device_id}"


def entries_of(content):
    """The records a device file holds, key -> [stamp, data|None]; anything malformed is skipped."""
    records = content.get("records") if isinstance(content, dict) else None
    entries = {}
    if not isinstance(records, dict):
        return entries
    for key, entry in records.items():
        if not known_key(key) or not isinstance(entry, list) or len(entry) != 2:
            continue
        stamp, data = entry
        if stamp_parts(stamp) is None or not (data is None or isinstance(data, dict)):
            continue
        entries[key] = [stamp, data]
    return entries


def remote_from_files(files):
    """Each record's newest copy across the device files: (remote, stamps).

    `files` are the parsed entries of every device file, this device's own
    included (its copy is what the others are measured against).
    """
    remote, stamps = {}, {}
    for entries in files:
        for key, (stamp, data) in entries.items():
            if key not in stamps or stamp > stamps[key]:
                stamps[key], remote[key] = stamp, data
    return remote, stamps


def newest_stamp(stamps):
    return max(stamps.values(), default="")


def entries_after(own, plan, remote, stamps, stamp):
    """This device's file after a sync: what it sent gets the new stamp,
    what it took from other devices keeps theirs, the rest is unchanged."""
    entries = {key: list(entry) for key, entry in own.items() if known_key(key)}
    for key, data in remote.items():
        if key not in plan.push:
            entries[key] = [stamps[key], data]
    for key, data in plan.push.items():
        entries[key] = [stamp, data]
    return entries


def file_content(device_id, entries, stamp):
    return {"format": FILE_FORMAT, "device": device_id, "written": stamp, "records": entries}
