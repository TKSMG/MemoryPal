"""Two-way sync of a profile with the person's cloud account: the pure logic.

Everything that syncs becomes a record: ``card:<id>``, ``capture:<id>``,
``settings:profile``, and each device's own review counts
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


def kind_of(key):
    return key.split(":", 1)[0]


def device_of(key):
    """The device a count record belongs to (the part after the last colon)."""
    return key.rsplit(":", 1)[1] if kind_of(key) in COUNT_KINDS else ""


def other_device_counts(base, device_id):
    """Review counts other devices have reported: ({day: count}, practiced)."""
    activity, practiced = {}, 0
    for key, data in base.items():
        if kind_of(key) not in COUNT_KINDS or device_of(key) == device_id or not isinstance(data, dict):
            continue
        count = max(0, int(data.get("count", 0) or 0))
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
    records[SETTINGS_KEY] = {name: payload.get(name) for name in SETTINGS_FIELDS}
    others_activity, others_practiced = other_device_counts(base, device_id)
    # This device's share is whatever the local totals hold beyond what the
    # other devices reported.
    for day, total in sorted(payload.get("activity", {}).items()):
        own = int(total or 0) - others_activity.get(day, 0)
        if own > 0:
            records[f"activity:{day}:{device_id}"] = {"day": day, "count": own}
    own_practiced = max(0, int(payload.get("practiced", 0) or 0) - others_practiced)
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
    settings = records.get(SETTINGS_KEY) or {}
    for name in SETTINGS_FIELDS:
        if name in settings and settings[name] is not None:
            result[name] = settings[name]
    activity, practiced = {}, 0
    for key, data in records.items():
        if kind_of(key) == "activity":
            day = str(data.get("day", ""))
            activity[day] = activity.get(day, 0) + max(0, int(data.get("count", 0) or 0))
        elif kind_of(key) == "practiced":
            practiced += max(0, int(data.get("count", 0) or 0))
    result["activity"] = {day: count for day, count in sorted(activity.items()) if count > 0}
    result["practiced"] = practiced
    return result


def progress(card):
    """How much review a card version carries: more reviews wins a schedule conflict."""
    return (int(card.get("repetitions", 0) or 0) + int(card.get("lapses", 0) or 0), str(card.get("next_review", "")))


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
        schedule_winner = local if progress(local) > progress(remote) else remote
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
    push, apply, final = {}, {}, {}
    for key in sorted(set(local) | set(base) | set(remote)):
        mine = local.get(key)
        was = base.get(key)
        theirs = remote[key] if key in remote else was
        local_changed = mine != was
        remote_changed = key in remote and theirs != was
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
