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
SWP_NOOWNERZORDER = 0x0200

FRAME_STYLE = WS_CAPTION | WS_THICKFRAME
FRAME_EXSTYLE = WS_EX_DLGMODALFRAME | WS_EX_WINDOWEDGE | WS_EX_CLIENTEDGE | WS_EX_STATICEDGE


def fullscreen_styles(style, exstyle):
    """The window styles while full screen: no caption, sizing frame or edges."""
    return style & ~FRAME_STYLE, exstyle & ~FRAME_EXSTYLE


def _outer_rect(user32, ctypes, hwnd, area, style, exstyle):
    """The window rect, for these styles, whose client area is exactly `area`."""
    class RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

    rect = RECT(area.left, area.top, area.right, area.bottom)
    style, exstyle = ctypes.c_ulong(style & 0xFFFFFFFF), ctypes.c_ulong(exstyle & 0xFFFFFFFF)
    adjust = getattr(user32, "AdjustWindowRectExForDpi", None)
    dpi_for = getattr(user32, "GetDpiForWindow", None)
    if adjust is not None and dpi_for is not None:
        ok = adjust(ctypes.byref(rect), style, False, exstyle, dpi_for(hwnd))
    else:
        ok = user32.AdjustWindowRectEx(ctypes.byref(rect), style, False, exstyle)
    return (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top) if ok else None


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


def monitor_rect(hwnd):
    """(left, top, right, bottom) of the monitor the window is on, or None."""
    if not hwnd or not sys.platform.startswith("win"):
        return None
    try:
        ctypes, user32, _get_long, _set_long, _placement, MONITORINFO = _api()
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if not user32.GetMonitorInfoW(user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST), ctypes.byref(info)):
            return None
        area = info.rcMonitor
        return area.left, area.top, area.right, area.bottom
    except (AttributeError, OSError, ValueError):
        return None


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
        # Two moves. First grow the framed window until its client area
        # covers the monitor, caption and borders just off screen: the page
        # lays out at its full screen size here. Dropping the frame then
        # changes nothing inside the window. Done in one move, Windows showed
        # one frame of the new page still at the old client offset (shifted
        # right and down by the border and caption).
        outer = _outer_rect(user32, ctypes, hwnd, area, style, exstyle)
        if outer is not None:
            user32.SetWindowPos(hwnd, None, *outer, SWP_NOZORDER | SWP_NOOWNERZORDER | SWP_NOACTIVATE)
        set_long(hwnd, GWL_STYLE, full_style)
        set_long(hwnd, GWL_EXSTYLE, full_exstyle)
        user32.SetWindowPos(hwnd, None, area.left, area.top, area.right - area.left, area.bottom - area.top,
                            SWP_NOZORDER | SWP_NOOWNERZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED)
        return {"style": style, "exstyle": exstyle, "placement": placement}
    except (AttributeError, OSError, ValueError):
        return None


def leave(hwnd, saved):
    """Put back the style and place `enter` saved. Returns True if it did."""
    if not hwnd or not saved or not sys.platform.startswith("win"):
        return False
    try:
        ctypes, user32, _get_long, set_long, _placement, _info = _api()
        set_long(hwnd, GWL_STYLE, saved["style"])
        set_long(hwnd, GWL_EXSTYLE, saved["exstyle"])
        user32.SetWindowPlacement(hwnd, ctypes.byref(saved["placement"]))
        user32.SetWindowPos(hwnd, None, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOOWNERZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED)
        return True
    except (AttributeError, OSError, KeyError):
        return False


# A still picture of the screen, held over the window while it switches.
#
# Tk draws a window as many small native windows, one after another, so a
# switch that moves everything (full screen on or off) was shown by the
# compositor part old and part new for a frame or two: tearing, and now and
# then a flash of background where a part wasn't drawn yet. Games and some
# media players avoid it the same way as here: show a picture of the screen
# exactly as it is, make the change underneath, wait until it has been drawn
# and composed, then take the picture away. Nothing fades: the screen goes
# from the old picture to the finished new one in one step.

SRCCOPY = 0x00CC0020
CAPTUREBLT = 0x40000000


def _gdi():
    import ctypes
    from ctypes import wintypes

    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    user32.GetDC.argtypes = (wintypes.HWND,)
    user32.GetDC.restype = ctypes.c_void_p
    user32.ReleaseDC.argtypes = (wintypes.HWND, ctypes.c_void_p)
    gdi32.CreateCompatibleDC.argtypes = (ctypes.c_void_p,)
    gdi32.CreateCompatibleDC.restype = ctypes.c_void_p
    gdi32.CreateCompatibleBitmap.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_int)
    gdi32.CreateCompatibleBitmap.restype = ctypes.c_void_p
    gdi32.SelectObject.argtypes = (ctypes.c_void_p, ctypes.c_void_p)
    gdi32.SelectObject.restype = ctypes.c_void_p
    gdi32.BitBlt.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                             ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_uint)
    gdi32.DeleteObject.argtypes = (ctypes.c_void_p,)
    gdi32.DeleteDC.argtypes = (ctypes.c_void_p,)
    return user32, gdi32


def snapshot(rect):
    """Copy what the screen shows inside rect (left, top, right, bottom).
    Returns a handle for paint_snapshot/free_snapshot, or None."""
    if not rect or not sys.platform.startswith("win"):
        return None
    try:
        user32, gdi32 = _gdi()
        left, top, right, bottom = rect
        width, height = right - left, bottom - top
        if width <= 0 or height <= 0:
            return None
        screen = user32.GetDC(None)
        if not screen:
            return None
        try:
            memory = gdi32.CreateCompatibleDC(screen)
            bitmap = gdi32.CreateCompatibleBitmap(screen, width, height) if memory else None
            if not bitmap:
                if memory:
                    gdi32.DeleteDC(memory)
                return None
            old = gdi32.SelectObject(memory, bitmap)
            if not gdi32.BitBlt(memory, 0, 0, width, height, screen, left, top, SRCCOPY | CAPTUREBLT):
                gdi32.SelectObject(memory, old)
                gdi32.DeleteObject(bitmap)
                gdi32.DeleteDC(memory)
                return None
        finally:
            user32.ReleaseDC(None, screen)
        return {"dc": memory, "bitmap": bitmap, "old": old, "size": (width, height)}
    except (AttributeError, OSError, ValueError):
        return None


def paint_snapshot(hwnd, snap):
    """Draw the picture into a window, at its top left. True if drawn."""
    if not hwnd or not snap:
        return False
    try:
        user32, gdi32 = _gdi()
        target = user32.GetDC(hwnd)
        if not target:
            return False
        try:
            width, height = snap["size"]
            done = gdi32.BitBlt(target, 0, 0, width, height, snap["dc"], 0, 0, SRCCOPY)
        finally:
            user32.ReleaseDC(hwnd, target)
        gdi32.GdiFlush()
        return bool(done)
    except (AttributeError, OSError, ValueError):
        return False


def free_snapshot(snap):
    if not snap:
        return
    try:
        _user32, gdi32 = _gdi()
        gdi32.SelectObject(snap["dc"], snap["old"])
        gdi32.DeleteObject(snap["bitmap"])
        gdi32.DeleteDC(snap["dc"])
    except (AttributeError, OSError, ValueError, KeyError):
        pass


def wait_for_compose(frames=1):
    """Block until the compositor has shown what was drawn (DwmFlush)."""
    if not sys.platform.startswith("win"):
        return False
    try:
        import ctypes

        for _ in range(frames):
            if ctypes.windll.dwmapi.DwmFlush() != 0:
                return False
        return True
    except (AttributeError, OSError):
        return False
