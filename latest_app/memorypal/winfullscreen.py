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

    # Own copies of the DLLs: setting argtypes/restype on ctypes.windll's
    # shared ones would change how the rest of the app calls these functions.
    user32, gdi32 = ctypes.WinDLL("user32"), ctypes.WinDLL("gdi32")
    gdi32.GdiFlush.restype = ctypes.c_int
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


def wait_for_compose(frames=1, hz=60.0):
    """Give the compositor time to show what was just drawn: `frames`
    screen refreshes. (DwmFlush would say exactly when, but it blocks until
    the screen next changes, which on a still screen can be never.)"""
    if not sys.platform.startswith("win"):
        return False
    import time

    time.sleep(max(1, frames) / max(24.0, min(float(hz or 60.0), 500.0)))
    return True


# The still picture as its own plain Windows window.
#
# The first version showed the picture in a Tk window made see-through with
# -alpha and then made solid. Tk's see-through windows are "layered" windows
# whose picture Windows keeps in a buffer it fills in its own time, and a
# layered window shown or sized across a whole monitor can flash the default
# blue for a frame (the same cause as the blue frame on first maximise, fixed
# for the main window in windowtheme.drop_layered). Showing it also took the
# focus away from the app and gave it back, which redraws the title bar.
#
# This window gets its picture and its place in one call
# (UpdateLayeredWindow), so the first frame it is ever shown in already has
# the whole picture. It never takes the focus, lets the mouse through, has no
# taskbar button, and Windows' open/close animations are turned off for it.

WS_POPUP = 0x80000000
WS_EX_TOPMOST = 0x00000008
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
ULW_ALPHA = 0x00000002
SW_SHOWNOACTIVATE = 4
HWND_TOPMOST = -1
SWP_SHOWWINDOW = 0x0040
DWMWA_TRANSITIONS_FORCEDISABLED = 3
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWA_BORDER_COLOR = 34
DWMWCP_DONOTROUND = 1
DWMWA_COLOR_NONE = 0xFFFFFFFE


def _cover_api():
    import ctypes
    from ctypes import wintypes

    user32, gdi32 = _gdi()
    dwmapi = ctypes.WinDLL("dwmapi")
    kernel32 = ctypes.WinDLL("kernel32")
    kernel32.GetModuleHandleW.argtypes = (wintypes.LPCWSTR,)
    kernel32.GetModuleHandleW.restype = ctypes.c_void_p
    user32.CreateWindowExW.argtypes = (wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                       ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                       wintypes.HWND, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.UpdateLayeredWindow.argtypes = (wintypes.HWND, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                                           ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p,
                                           wintypes.DWORD)
    user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
    user32.SetWindowPos.argtypes = (wintypes.HWND, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_uint)
    user32.DestroyWindow.argtypes = (wintypes.HWND,)
    dwmapi.DwmSetWindowAttribute.argtypes = (wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD)
    return ctypes, wintypes, user32, gdi32, dwmapi, kernel32


def show_cover(rect, snap, owner=None):
    """Show `snap` (from snapshot(rect)) over rect in a window of its own,
    on top of everything. Returns the window handle for hide_cover, or None."""
    if not rect or not snap or not sys.platform.startswith("win"):
        return None
    try:
        ctypes, wintypes, user32, gdi32, dwmapi, kernel32 = _cover_api()
        left, top, right, bottom = rect
        width, height = right - left, bottom - top
        exstyle = WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_TRANSPARENT
        # STATIC is a class every process has; a layered window that is
        # filled with UpdateLayeredWindow never asks its class to paint.
        hwnd = user32.CreateWindowExW(exstyle, "STATIC", None, WS_POPUP, left, top, width, height,
                                      owner or None, None, kernel32.GetModuleHandleW(None), None)
        if not hwnd:
            return None
        for attribute, value in ((DWMWA_TRANSITIONS_FORCEDISABLED, 1),
                                 (DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_DONOTROUND),
                                 (DWMWA_BORDER_COLOR, DWMWA_COLOR_NONE)):
            setting = ctypes.c_uint(value)
            dwmapi.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(setting), ctypes.sizeof(setting))
        position, size, source = wintypes.POINT(left, top), wintypes.SIZE(width, height), wintypes.POINT(0, 0)

        class BLENDFUNCTION(ctypes.Structure):
            _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
                        ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte)]

        # Fully solid, ignoring the picture's own (unset) alpha channel.
        blend = BLENDFUNCTION(0, 0, 255, 0)
        screen = user32.GetDC(None)
        try:
            done = user32.UpdateLayeredWindow(hwnd, screen, ctypes.byref(position), ctypes.byref(size), snap["dc"],
                                              ctypes.byref(source), 0, ctypes.byref(blend), ULW_ALPHA)
        finally:
            user32.ReleaseDC(None, screen)
        if not done:
            user32.DestroyWindow(hwnd)
            return None
        user32.SetWindowPos(hwnd, ctypes.c_void_p(HWND_TOPMOST), 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW)
        gdi32.GdiFlush()
        return hwnd
    except (AttributeError, OSError, ValueError, KeyError):
        return None


def hide_cover(hwnd):
    if not hwnd or not sys.platform.startswith("win"):
        return False
    try:
        _ctypes, _wintypes, user32, gdi32, _dwmapi, _kernel32 = _cover_api()
        gdi32.GdiFlush()
        return bool(user32.DestroyWindow(hwnd))
    except (AttributeError, OSError):
        return False


# The same still picture for maximise, restore and snapping.
#
# Those are started by Windows (the title bar buttons, a double-click, the
# snap layouts, Win+arrows), not by the app, and the window has its new size
# before Tk hears of it. Until the page was laid out again for that size the
# big window showed the small window's page in a corner, then a half-drawn
# frame. So the window is watched for a big size change that is about to
# happen, and the still picture goes up just before it.
#
# The watcher is a window procedure called by Windows from inside Tk's own
# event loop. It must never call into Tk (that crashes Python: the thread
# state Tk saved is not the one the callback runs with), so it only makes
# Windows calls and sets plain Python values that the app reads later.

WM_WINDOWPOSCHANGING = 0x0046
WM_NCDESTROY = 0x0082
WM_SYSCOMMAND = 0x0112
WM_ENTERSIZEMOVE = 0x0231
WM_EXITSIZEMOVE = 0x0232
WM_CLOSE = 0x0010
SC_MAXIMIZE = 0xF030
SC_RESTORE = 0xF120
COVER_MAX_SECONDS = 1.5
_resize_watch = {}  # hwnd -> state; holds the callback so it stays alive
_resize_retired = []


def set_transitions(hwnd, enabled):
    """Turn Windows' own grow/shrink animation of a window on or off."""
    try:
        ctypes, _wintypes, _user32, _gdi32, dwmapi, _kernel32 = _cover_api()
        setting = ctypes.c_uint(0 if enabled else 1)
        return dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_TRANSITIONS_FORCEDISABLED, ctypes.byref(setting), ctypes.sizeof(setting)) == 0
    except (AttributeError, OSError, ValueError):
        return False


def big_resize(old_size, new_size, threshold):
    return abs(new_size[0] - old_size[0]) > threshold or abs(new_size[1] - old_size[1]) > threshold


def _raise_resize_cover(hwnd, state):
    import threading
    import time

    rect = monitor_rect(hwnd)
    snap = snapshot(rect)
    if snap is None:
        return
    cover = show_cover(rect, snap)
    free_snapshot(snap)  # the cover window keeps its own copy of the picture
    if cover is None:
        return
    set_transitions(hwnd, False)
    state["cover"] = cover
    state["since"] = time.perf_counter()

    def give_up():
        # Should the app never come to take the cover down, ask the cover to
        # close itself (a posted message: handled on the window's own thread).
        try:
            _ctypes, _wintypes, user32, _gdi32, _dwmapi, _kernel32 = _cover_api()
            user32.PostMessageW(cover, WM_CLOSE, 0, 0)
        except (AttributeError, OSError):
            pass

    timer = threading.Timer(COVER_MAX_SECONDS, give_up)
    timer.daemon = True
    timer.start()
    state["timer"] = timer


def watch_big_resizes(hwnd, threshold):
    """Put the still picture up whenever the window is about to change size
    by more than `threshold` pixels at once. Off until arm_resize_cover."""
    if not hwnd or not sys.platform.startswith("win"):
        return False
    if hwnd in _resize_watch:
        _resize_watch[hwnd]["threshold"] = threshold
        return True
    try:
        ctypes, wintypes, user32, _gdi32, _dwmapi, _kernel32 = _cover_api()
        comctl32 = ctypes.WinDLL("comctl32")
        LRESULT = ctypes.c_ssize_t
        SUBCLASSPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM, ctypes.c_size_t, ctypes.c_size_t)
        comctl32.DefSubclassProc.restype = LRESULT
        comctl32.DefSubclassProc.argtypes = (wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM)
        comctl32.SetWindowSubclass.argtypes = (wintypes.HWND, SUBCLASSPROC, ctypes.c_size_t, ctypes.c_size_t)
        comctl32.RemoveWindowSubclass.argtypes = (wintypes.HWND, SUBCLASSPROC, ctypes.c_size_t)
        user32.GetWindowRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
        user32.IsWindowVisible.argtypes = (wintypes.HWND,)
        user32.IsIconic.argtypes = (wintypes.HWND,)
        user32.PostMessageW.argtypes = (wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM)

        class WINDOWPOS(ctypes.Structure):
            _fields_ = [("hwnd", wintypes.HWND), ("hwndInsertAfter", wintypes.HWND), ("x", ctypes.c_int), ("y", ctypes.c_int),
                        ("cx", ctypes.c_int), ("cy", ctypes.c_int), ("flags", ctypes.c_uint)]

        state = {"armed": False, "sizing": False, "cover": None, "since": 0.0, "timer": None, "threshold": threshold, "raised": 0}

        def procedure(window, message, wparam, lparam, _id, _data):
            try:
                if message == WM_ENTERSIZEMOVE:
                    state["sizing"] = True
                elif message == WM_EXITSIZEMOVE:
                    state["sizing"] = False
                elif message == WM_SYSCOMMAND and (wparam & 0xFFF0) in (SC_MAXIMIZE, SC_RESTORE) and state["armed"]:
                    set_transitions(window, False)
                elif message == WM_WINDOWPOSCHANGING and lparam and state["armed"] and not state["sizing"] and state["cover"] is None:
                    change = ctypes.cast(lparam, ctypes.POINTER(WINDOWPOS)).contents
                    if not change.flags & SWP_NOSIZE and change.x > -30000 and user32.IsWindowVisible(window) and not user32.IsIconic(window):
                        now = wintypes.RECT()
                        user32.GetWindowRect(window, ctypes.byref(now))
                        if big_resize((now.right - now.left, now.bottom - now.top), (change.cx, change.cy), state["threshold"]):
                            state["raised"] += 1
                            _raise_resize_cover(window, state)
                elif message == WM_NCDESTROY:
                    entry = _resize_watch.pop(hwnd, None)
                    if entry is not None:
                        comctl32.RemoveWindowSubclass(window, entry["callback"], 0x4D51)
                        _resize_retired.append(entry["callback"])
            except Exception:  # noqa: BLE001 - nothing may escape into Windows' message loop
                pass
            return comctl32.DefSubclassProc(window, message, wparam, lparam)

        state["callback"] = SUBCLASSPROC(procedure)
        if not comctl32.SetWindowSubclass(hwnd, state["callback"], 0x4D51, 0):
            return False
        _resize_watch[hwnd] = state
        return True
    except (AttributeError, OSError, ValueError):
        return False


def arm_resize_cover(hwnd, armed):
    """Switch the watcher on or off (off while the app changes its own size)."""
    state = _resize_watch.get(hwnd)
    if state is not None:
        state["armed"] = bool(armed)
    return state is not None


def resize_cover_up(hwnd):
    state = _resize_watch.get(hwnd)
    return bool(state and state["cover"])


def resize_covers_raised(hwnd):
    """How many times the cover has gone up (for the checks)."""
    state = _resize_watch.get(hwnd)
    return state["raised"] if state else 0


def drop_resize_cover(hwnd):
    """Take the still picture down (once the new layout is drawn). True if one was up."""
    state = _resize_watch.get(hwnd)
    if not state or not state["cover"]:
        return False
    cover, state["cover"] = state["cover"], None
    timer, state["timer"] = state["timer"], None
    if timer is not None:
        timer.cancel()
    hide_cover(cover)
    set_transitions(hwnd, True)
    return True
