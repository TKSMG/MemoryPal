"""Hands the week's notifications to Windows or macOS to show.

The computer shows them even while MemoryPal is closed, like the phone:
  Windows  scheduled toasts (WinRT ScheduledToastNotification), set up by a
           short PowerShell script; no extra packages. Toasts are tagged
           with the group "memorypal" so the next week replaces them.
  macOS    one launch agent (~/Library/LaunchAgents) that wakes at each
           time and runs a small shell script calling `display notification`.
Elsewhere (Linux) nothing is scheduled.

What the notifications say comes from notifications.plan_notifications.
"""

import json
import os
import plistlib
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

APP_NAME = "MemoryPal"
GROUP = "memorypal"
MAC_LABEL = "app.memorypal.notifications"
# Windows PowerShell's own id: shows "Windows PowerShell" as the sender, used
# only when MemoryPal has no Start menu entry (running from source).
POWERSHELL_APP_ID = "{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\\WindowsPowerShell\\v1.0\\powershell.exe"
CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008
# A notification that couldn't show on time (the Mac was asleep) still shows
# when it wakes within this long, then is dropped.
MAC_GRACE_SECONDS = 3600


def platform_name():
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "mac"
    return ""


def supported():
    return bool(platform_name())


def signature(planned):
    """What was handed over, to skip handing over the same week again."""
    return json.dumps([[entry["at"].isoformat(timespec="minutes"), entry["kind"], entry["title"], entry["body"]] for entry in planned])


# ---------------------------------------------------------------- Windows
WINDOWS_SCRIPT = r"""
param([string]$Data)
$ErrorActionPreference = 'Stop'
[void][Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]
[void][Windows.UI.Notifications.ScheduledToastNotification, Windows.UI.Notifications, ContentType = WindowsRuntime]
[void][Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime]
$plan = Get-Content -LiteralPath $Data -Raw -Encoding UTF8 | ConvertFrom-Json
$appId = $null
try {
  $entry = Get-StartApps | Where-Object { $_.Name -eq $plan.app } | Select-Object -First 1
  if ($entry) { $appId = $entry.AppID }
} catch {}
if (-not $appId) { $appId = $plan.fallback }
$notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId)
foreach ($old in @($notifier.GetScheduledToastNotifications())) {
  if ($old.Group -eq $plan.group) { $notifier.RemoveFromSchedule($old) }
}
foreach ($item in @($plan.items)) {
  $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
  $xml.LoadXml($item.xml)
  $when = [DateTimeOffset]::Parse($item.at, [Globalization.CultureInfo]::InvariantCulture)
  if ($when -le [DateTimeOffset]::Now) { continue }
  $toast = New-Object Windows.UI.Notifications.ScheduledToastNotification -ArgumentList $xml, $when
  $toast.Group = $plan.group
  $toast.Tag = $item.tag
  $notifier.AddToSchedule($toast)
}
"""


def toast_xml(entry):
    title = escape(entry["title"])
    body = escape(entry["body"])
    launch = escape(f"memorypal:{entry.get('open', 'review')}", {'"': "&quot;"})
    return (
        f'<toast launch="{launch}"><visual><binding template="ToastGeneric">'
        f"<text>{title}</text><text>{body}</text>"
        '</binding></visual><audio silent="true"/></toast>'
    )


def windows_payload(planned):
    items = []
    for index, entry in enumerate(planned):
        at = entry["at"].astimezone() if entry["at"].tzinfo is None else entry["at"]
        items.append({"tag": f"mp{index}", "at": at.isoformat(timespec="seconds"), "xml": toast_xml(entry)})
    return {"app": APP_NAME, "fallback": POWERSHELL_APP_ID, "group": GROUP, "items": items}


def schedule_windows(planned, folder, wait=False):
    folder.mkdir(parents=True, exist_ok=True)
    script = folder / "schedule-toasts.ps1"
    data = folder / "toasts.json"
    script.write_text(WINDOWS_SCRIPT, encoding="utf-8-sig")
    data.write_text(json.dumps(windows_payload(planned), ensure_ascii=False), encoding="utf-8")
    command = ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(script), "-Data", str(data)]
    # Detached, so it finishes even when MemoryPal is closing.
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW | (0 if wait else DETACHED_PROCESS), close_fds=True)
    if wait:
        return process.wait(timeout=30) == 0
    return True


# ------------------------------------------------------------------ macOS
def shell_quote(text):
    return "'" + str(text).replace("'", "'\"'\"'") + "'"


def mac_script(planned, folder):
    lines = [
        "#!/bin/sh",
        "# Written by MemoryPal: shows its study notifications. Replaced each time MemoryPal plans the week.",
        f"DIR={shell_quote(folder)}",
        "now=$(date +%s)",
        "show() {",
        f'  [ "$now" -ge "$1" ] && [ "$now" -lt $(( $1 + {MAC_GRACE_SECONDS} )) ] || return 0',
        '  mark="$DIR/shown-$1-$2"',
        '  [ -e "$mark" ] && return 0',
        '  : > "$mark"',
        "  /usr/bin/osascript -e 'on run argv' -e 'display notification (item 2 of argv) with title \"MemoryPal\" subtitle (item 1 of argv)' -e 'end run' \"$3\" \"$4\"",
        "}",
    ]
    for index, entry in enumerate(planned):
        stamp = int(entry["at"].timestamp())
        lines.append(f"show {stamp} {index} {shell_quote(entry['title'])} {shell_quote(entry['body'])}")
    lines.append('find "$DIR" -name "shown-*" -mtime +8 -delete 2>/dev/null')
    return "\n".join(lines) + "\n"


def mac_plist(planned, script):
    times = []
    for entry in planned:
        at = entry["at"]
        when = {"Month": at.month, "Day": at.day, "Hour": at.hour, "Minute": at.minute}
        if when not in times:
            times.append(when)
    return {
        "Label": MAC_LABEL,
        "ProgramArguments": ["/bin/sh", str(script)],
        "StartCalendarInterval": times,
        "RunAtLoad": False,
        "ProcessType": "Background",
    }


def mac_agent_path():
    return Path.home() / "Library" / "LaunchAgents" / f"{MAC_LABEL}.plist"


def launchctl(*args):
    try:
        return subprocess.run(["launchctl", *args], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def schedule_mac(planned, folder):
    agent = mac_agent_path()
    domain = f"gui/{os.getuid()}"
    if agent.exists():
        launchctl("bootout", domain, str(agent))
    if not planned:
        try:
            agent.unlink()
        except OSError:
            pass
        return True
    folder.mkdir(parents=True, exist_ok=True)
    script = folder / "notify.sh"
    script.write_text(mac_script(planned, folder), encoding="utf-8")
    script.chmod(0o755)
    agent.parent.mkdir(parents=True, exist_ok=True)
    with open(agent, "wb") as handle:
        plistlib.dump(mac_plist(planned, script), handle)
    return launchctl("bootstrap", domain, str(agent)) or launchctl("load", str(agent))


# ----------------------------------------------------------------- shared
def schedule(planned, folder, wait=False):
    """Replace MemoryPal's scheduled notifications with `planned` (an empty list clears them).

    Returns True when handed over (not a promise the system will show them).
    """
    folder = Path(folder)
    try:
        kind = platform_name()
        if kind == "windows":
            return schedule_windows(planned, folder, wait=wait)
        if kind == "mac":
            return schedule_mac(planned, folder)
    except Exception:
        # Notifications are a convenience: never let them break the app.
        return False
    return False


TEST_TITLE = "Notifications are working"
TEST_BODY = "This is how MemoryPal will remind you."


def send_test(planned, folder):
    """Show a sample notification in a few seconds, keeping the week's in place."""
    kind = platform_name()
    try:
        if kind == "windows":
            sample = {"kind": "test", "at": datetime.now() + timedelta(seconds=4), "title": TEST_TITLE, "body": TEST_BODY, "open": "review", "due": 0}
            return schedule_windows([sample] + list(planned), Path(folder))
        if kind == "mac":
            script = f'display notification "{TEST_BODY}" with title "MemoryPal" subtitle "{TEST_TITLE}"'
            return subprocess.run(["/usr/bin/osascript", "-e", script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10).returncode == 0
    except Exception:
        return False
    return False
