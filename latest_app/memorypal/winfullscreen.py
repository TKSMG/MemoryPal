"""Full screen on Windows the way Chrome, Edge and Windows Terminal do it.

Tk's own `wm attributes -fullscreen` destroys the native window and builds a
new one each time it switches. The new window starts with Windows' default
white background and light title bar, so leaving full screen flashed white.

Instead this keeps the same window and changes its style, as Raymond Chen
describes in "How do I switch a window between normal and fullscreen?" and
as Chromium's FullscreenHandler does: drop the caption and sizing frame, then
cover the monitor; to leave, put the style and placement back. The window's
dark title bar colours and background brush stay, so nothing flashes.

Only ctypes from the standard library is used. Each function returns None or
False when it can't do the job, and the caller falls back to Tk's version.
"""

import sys

GWL_STYLE = -16
GWL_EXSTYLE = -20
WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000
WS_EX_DLGMODALFRAME = 0x00000001
WS_EX_WINDOWEDGE = 0x00000100
WS_EX_CLIENTEDGE = 0x00000200
WS_EX_STATICEDGE = 0x00020000
MONITOR_DEFAULTTONEAREST = 2
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
SWP_NOCOPYBITS = 0x0100
SWP_NOOWNERZORDER = 0x0200

# Experiment switch (render probe): don't let Windows copy the old client
# pixels to the new client position when the frame changes.
NO_COPY_BITS = False
# Experiment switch: switch in two moves so the client area never moves on
# screen while the frame is added or removed (see _keep_client).
TWO_STEP = False

FRAME_STYLE = WS_CAPTION | WS_THICKFRAME
FRAME_EXSTYLE = WS_EX_DLGMODALFRAME | WS_EX_WINDOWEDGE | WS_EX_CLIENTEDGE | WS_EX_STATICEDGE


def fullscreen_styles(style, exstyle):
    """The window styles while full screen: no caption, sizing frame or edges."""
    return style & ~FRAME_STYLE, exstyle & ~FRAME_EXSTYLE


def _copy_flag():
    return SWP_NOCOPYBITS if NO_COPY_BITS else 0


def _outer_rect(user32, ctypes, hwnd, left, top, right, bottom, style, exstyle):
    """The window rect whose client area is exactly the given screen rect."""
    class RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

    rect = RECT(left, top, right, bottom)
    adjust = getattr(user32, "AdjustWindowRectExForDpi", None)
    dpi_for = getattr(user32, "GetDpiForWindow", None)
    if adjust is not None and dpi_for is not None:
        ok = adjust(ctypes.byref(rect), ctypes.c_ulong(style & 0xFFFFFFFF), False, ctypes.c_ulong(exstyle & 0xFFFFFFFF),
                    dpi_for(hwnd))
    else:
        ok = user32.AdjustWindowRectEx(ctypes.byref(rect), ctypes.c_ulong(style & 0xFFFFFFFF), False,
                                       ctypes.c_ulong(exstyle & 0xFFFFFFFF))
    return (rect.left, rect.top, rect.right, rect.bottom) if ok else None


def _api():
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32

    class RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    class WINDOWPLACEMENT(ctypes.Structure):
        _fields_ = [("length", ctypes.c_uint), ("flags", ctypes.c_uint), ("showCmd", ctypes.c_uint),
                    ("ptMinPosition", POINT), ("ptMaxPosition", POINT), ("rcNormalPosition", RECT)]

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_ulong), ("rcMonitor", RECT), ("rcWork", RECT), ("dwFlags", ctypes.c_ulong)]

    get_long = getattr(user32, "GetWindowLongPtrW", None) or user32.GetWindowLongW
    set_long = getattr(user32, "SetWindowLongPtrW", None) or user32.SetWindowLongW
    get_long.argtypes = (wintypes.HWND, ctypes.c_int)
    get_long.restype = ctypes.c_ssize_t
    set_long.argtypes = (wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t)
    set_long.restype = ctypes.c_ssize_t
    user32.SetWindowPos.argtypes = (wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint)
    user32.MonitorFromWindow.argtypes = (wintypes.HWND, ctypes.c_ulong)
    user32.MonitorFromWindow.restype = ctypes.c_void_p
    user32.GetMonitorInfoW.argtypes = (ctypes.c_void_p, ctypes.c_void_p)
    user32.GetWindowPlacement.argtypes = (wintypes.HWND, ctypes.c_void_p)
    user32.SetWindowPlacement.argtypes = (wintypes.HWND, ctypes.c_void_p)
    return ctypes, user32, get_long, set_long, WINDOWPLACEMENT, MONITORINFO


def enter(hwnd):
    """Make the window cover its monitor. Returns what `leave` needs, or None."""
    if not hwnd or not sys.platform.startswith("win"):
        return None
    try:
        ctypes, user32, get_long, set_long, WINDOWPLACEMENT, MONITORINFO = _api()
        style, exstyle = get_long(hwnd, GWL_STYLE), get_long(hwnd, GWL_EXSTYLE)
        placement = WINDOWPLACEMENT()
        placement.length = ctypes.sizeof(WINDOWPLACEMENT)
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if not user32.GetWindowPlacement(hwnd, ctypes.byref(placement)):
            return None
        if not user32.GetMonitorInfoW(user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST), ctypes.byref(info)):
            return None
        full_style, full_exstyle = fullscreen_styles(style, exstyle)
        area = info.rcMonitor
        if TWO_STEP:
            # First grow the framed window until its client area covers the
            # monitor (caption and borders just off screen). The page lays
            # out at full screen size here, and the next step, dropping the
            # frame, then changes nothing inside the window: no shift.
            outer = _outer_rect(user32, ctypes, hwnd, area.left, area.top, area.right, area.bottom, style, exstyle)
            if outer is not None:
                user32.SetWindowPos(hwnd, None, outer[0], outer[1], outer[2] - outer[0], outer[3] - outer[1],
                                    SWP_NOZORDER | SWP_NOOWNERZORDER | SWP_NOACTIVATE)
        set_long(hwnd, GWL_STYLE, full_style)
        set_long(hwnd, GWL_EXSTYLE, full_exstyle)
        user32.SetWindowPos(hwnd, None, area.left, area.top, area.right - area.left, area.bottom - area.top,
                            SWP_NOZORDER | SWP_NOOWNERZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED | _copy_flag())
        return {"style": style, "exstyle": exstyle, "placement": placement}
    except (AttributeError, OSError, ValueError):
        return None


def leave(hwnd, saved):
    """Put back the style and place `enter` saved. Returns True if it did."""
    if not hwnd or not saved or not sys.platform.startswith("win"):
        return False
    try:
        ctypes, user32, _get_long, set_long, _placement, MONITORINFO = _api()
        set_long(hwnd, GWL_STYLE, saved["style"])
        set_long(hwnd, GWL_EXSTYLE, saved["exstyle"])
        placement = saved["placement"]
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if TWO_STEP and user32.GetMonitorInfoW(user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST),
                                                ctypes.byref(info)):
            # Put the frame back around the client area where it is, so the
            # page doesn't move; then the normal restore below is a resize.
            area = info.rcMonitor
            outer = _outer_rect(user32, ctypes, hwnd, area.left, area.top, area.right, area.bottom,
                                saved["style"], saved["exstyle"])
            if outer is not None:
                user32.SetWindowPos(hwnd, None, outer[0], outer[1], outer[2] - outer[0], outer[3] - outer[1],
                                    SWP_NOZORDER | SWP_NOOWNERZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED)
        if NO_COPY_BITS and placement.showCmd == 1 and user32.GetMonitorInfoW(
                user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST), ctypes.byref(info)):
            # One move straight to the saved place, frame and size together.
            # The saved place is in work-area coordinates.
            rect = placement.rcNormalPosition
            dx, dy = info.rcWork.left - info.rcMonitor.left, info.rcWork.top - info.rcMonitor.top
            user32.SetWindowPos(hwnd, None, rect.left + dx, rect.top + dy, rect.right - rect.left, rect.bottom - rect.top,
                                SWP_NOZORDER | SWP_NOOWNERZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED | SWP_NOCOPYBITS)
            return True
        user32.SetWindowPlacement(hwnd, ctypes.byref(saved["placement"]))
        user32.SetWindowPos(hwnd, None, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOOWNERZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED | _copy_flag())
        return True
    except (AttributeError, OSError, KeyError):
        return False
