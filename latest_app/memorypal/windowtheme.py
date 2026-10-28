"""Make the operating system's own title bar match the app's light or dark theme.

Windows 10 (build 17763+) and 11 draw a dark title bar when asked through
DwmSetWindowAttribute(DWMWA_USE_IMMERSIVE_DARK_MODE); Windows 11 (build
22000+) also takes an exact caption and caption-text colour. Older builds
simply ignore the request. macOS follows the theme through Tk's own
"appearance" window style (Tk 8.6.10+). Elsewhere nothing happens.

Only ctypes from the standard library is used, and every call is allowed
to fail quietly: the title bar is cosmetic.
"""

import sys

DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_USE_IMMERSIVE_DARK_MODE_OLD = 19  # Windows 10 builds before 18985
DWMWA_BORDER_COLOR = 34
DWMWA_CAPTION_COLOR = 35
DWMWA_TEXT_COLOR = 36


def colorref(hex_color):
    """'#rrggbb' as a Windows COLORREF (0x00bbggrr), or None if not a colour."""
    raw = str(hex_color or "").lstrip("#")
    if len(raw) != 6:
        return None
    try:
        red, green, blue = (int(raw[index:index + 2], 16) for index in (0, 2, 4))
    except ValueError:
        return None
    return (blue << 16) | (green << 8) | red


def dwm_attributes(dark, caption=None, text=None, border=None):
    """The (attribute, value) pairs to send, in order: dark mode first, so a
    build without caption colours still gets a matching dark or light bar."""
    pairs = [(DWMWA_USE_IMMERSIVE_DARK_MODE, 1 if dark else 0), (DWMWA_USE_IMMERSIVE_DARK_MODE_OLD, 1 if dark else 0)]
    for attribute, colour in ((DWMWA_CAPTION_COLOR, caption), (DWMWA_TEXT_COLOR, text), (DWMWA_BORDER_COLOR, border)):
        value = colorref(colour)
        if value is not None:
            pairs.append((attribute, value))
    return pairs


def mac_appearance(dark):
    return "darkaqua" if dark else "aqua"


def apply_windows(hwnd, dark, caption=None, text=None, border=None):
    """Send the attributes to a top-level window handle. Returns how many took."""
    if not hwnd or not sys.platform.startswith("win"):
        return 0
    try:
        import ctypes

        set_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
    except (AttributeError, OSError):
        return 0
    applied = 0
    for attribute, value in dwm_attributes(dark, caption, text, border):
        data = ctypes.c_int(value)
        try:
            if set_attribute(ctypes.c_void_p(hwnd), attribute, ctypes.byref(data), ctypes.sizeof(data)) == 0:
                applied += 1
        except OSError:
            pass
    return applied


def apply_mac(window, dark):
    """Tk on macOS: set the window's appearance. Returns True if Tk accepted it."""
    if sys.platform != "darwin":
        return False
    try:
        window.tk.call("::tk::unsupported::MacWindowStyle", "appearance", window._w, mac_appearance(dark))
        return True
    except Exception:  # an older Tk without the option
        return False


def set_background_brush(hwnd, hex_color):
    """Have Windows fill a window with the app's background colour, not white.

    While a window grows or leaves full screen, Windows erases the new area
    with the window class's brush before the app paints it; Tk's class has
    none, so it showed as a white flash. The brush belongs to the class, so
    it covers every MemoryPal window. Returns True if the brush was set.
    """
    value = colorref(hex_color)
    if not hwnd or value is None or not sys.platform.startswith("win"):
        return False
    try:
        import ctypes

        user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
        set_class = getattr(user32, "SetClassLongPtrW", None) or user32.SetClassLongW
        set_class.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
        set_class.restype = ctypes.c_void_p
        gdi32.CreateSolidBrush.restype = ctypes.c_void_p
        brush = gdi32.CreateSolidBrush(value)
        previous = set_class(ctypes.c_void_p(hwnd), -10, ctypes.c_void_p(brush))  # GCLP_HBRBACKGROUND
        if previous and previous in _brushes:
            gdi32.DeleteObject(ctypes.c_void_p(previous))
            _brushes.discard(previous)
        _brushes.add(brush)
        return True
    except (AttributeError, OSError):
        return False


_brushes = set()  # brushes MemoryPal made, so replaced ones can be freed


DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_ROUND = 2
DWMWCP_ROUNDSMALL = 3


def round_popup(hwnd, border=None, small=False):
    """Windows 11: give a borderless popup (tooltip, list, menu) the system's
    rounded corners, hairline border and shadow, as its own menus and
    tooltips have. Returns True on Windows 11, False where it isn't
    supported (the caller then draws its own square edge)."""
    if not hwnd or not sys.platform.startswith("win"):
        return False
    try:
        import ctypes

        set_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
        corner = ctypes.c_int(DWMWCP_ROUNDSMALL if small else DWMWCP_ROUND)
        if set_attribute(ctypes.c_void_p(hwnd), DWMWA_WINDOW_CORNER_PREFERENCE, ctypes.byref(corner), ctypes.sizeof(corner)) != 0:
            return False
        value = colorref(border)
        if value is not None:
            color = ctypes.c_int(value)
            set_attribute(ctypes.c_void_p(hwnd), DWMWA_BORDER_COLOR, ctypes.byref(color), ctypes.sizeof(color))
        return True
    except (AttributeError, OSError):
        return False


WM_ERASEBKGND = 0x0014
WM_NCDESTROY = 0x0082
_erasers = {}  # hwnd -> (subclass callback, brush); kept alive while installed
_retired = []  # callbacks of closed windows (a few small objects)


def fill_on_erase(hwnd, hex_color):
    """Have a Tk window fill newly uncovered space with the app's background.

    When the window grows (dragging an edge, maximising, full screen),
    Windows asks the window under the new space to erase it before anything
    is drawn. Tk answers "done" without drawing, so the space kept whatever
    the screen had there: white on a fresh window surface, which flashed
    until Tk repainted. Answering with a fill in the theme's background is
    what Chrome and Electron do (their backgroundColor). Calling it again
    changes the colour. Returns True if the fill is in place.
    """
    value = colorref(hex_color)
    if not hwnd or value is None or not sys.platform.startswith("win"):
        return False
    try:
        import ctypes
        from ctypes import wintypes

        user32, gdi32, comctl32 = ctypes.windll.user32, ctypes.windll.gdi32, ctypes.windll.comctl32
        gdi32.CreateSolidBrush.restype = ctypes.c_void_p
        gdi32.DeleteObject.argtypes = (ctypes.c_void_p,)
        brush = gdi32.CreateSolidBrush(value)
        current = _erasers.get(hwnd)
        if current is not None:
            gdi32.DeleteObject(current[1])
            _erasers[hwnd] = (current[0], brush)
            return True
        LRESULT = ctypes.c_ssize_t
        SUBCLASSPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM, ctypes.c_size_t, ctypes.c_size_t)
        comctl32.DefSubclassProc.restype = LRESULT
        comctl32.DefSubclassProc.argtypes = (wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM)
        comctl32.SetWindowSubclass.argtypes = (wintypes.HWND, SUBCLASSPROC, ctypes.c_size_t, ctypes.c_size_t)
        user32.GetClientRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
        user32.FillRect.argtypes = (wintypes.HDC, ctypes.POINTER(wintypes.RECT), ctypes.c_void_p)

        comctl32.RemoveWindowSubclass.argtypes = (wintypes.HWND, SUBCLASSPROC, ctypes.c_size_t)

        def procedure(window, message, wparam, lparam, _id, _data):
            if message == WM_NCDESTROY:
                # The window is going: unhook, so a later window that gets the
                # same handle is hooked afresh.
                entry = _erasers.pop(hwnd, None)
                if entry is not None:
                    comctl32.RemoveWindowSubclass(window, entry[0], 0x4D50)
                    gdi32.DeleteObject(entry[1])
                    _retired.append(entry[0])  # still running: keep it alive
            elif message == WM_ERASEBKGND and wparam:
                entry = _erasers.get(hwnd)
                if entry is not None:
                    rect = wintypes.RECT()
                    user32.GetClientRect(window, ctypes.byref(rect))
                    user32.FillRect(wparam, ctypes.byref(rect), entry[1])
                    return 1
            return comctl32.DefSubclassProc(window, message, wparam, lparam)

        callback = SUBCLASSPROC(procedure)
        if not comctl32.SetWindowSubclass(hwnd, callback, 0x4D50, 0):  # "MP"
            gdi32.DeleteObject(brush)
            return False
        _erasers[hwnd] = (callback, brush)
        return True
    except (AttributeError, OSError):
        return False



WM_NCCALCSIZE = 0x0083
WM_WINDOWPOSCHANGED = 0x0047
WM_ENTERSIZEMOVE = 0x0231
WM_EXITSIZEMOVE = 0x0232
WVR_VALIDRECTS = 0x0400
SWP_NOSIZE = 0x0001
_sizers = {}  # hwnd -> subclass callback; kept alive while installed
# The probe turns these off to compare with Windows' default handling.
ANCHOR = True
SYNC = True


def smooth_live_resize(hwnd, relayout=None):
    """Keep the page still under a moving window edge, as native apps do.

    Dragging the top (or left) edge moves the window's top on screen while
    the page inside is laid out again a moment later, so for a frame or
    two the page sat lower than the edge, then caught up: it looked as if
    it grew and shrank back. Two things fix that. Windows is told exactly
    which old pixels are still good and that they belong at the new
    top-left, and `relayout` runs before Windows shows the new size (inside
    its WM_WINDOWPOSCHANGED, while an edge is being dragged), so the edge
    and the page arrive in the same frame. Returns True if the hook is in
    place.
    """
    if not hwnd or not sys.platform.startswith("win"):
        return False
    if hwnd in _sizers:
        return True
    try:
        import ctypes
        from ctypes import wintypes

        comctl32 = ctypes.windll.comctl32
        LRESULT = ctypes.c_ssize_t
        SUBCLASSPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM, ctypes.c_size_t, ctypes.c_size_t)
        comctl32.DefSubclassProc.restype = LRESULT
        comctl32.DefSubclassProc.argtypes = (wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM)
        comctl32.SetWindowSubclass.argtypes = (wintypes.HWND, SUBCLASSPROC, ctypes.c_size_t, ctypes.c_size_t)
        comctl32.RemoveWindowSubclass.argtypes = (wintypes.HWND, SUBCLASSPROC, ctypes.c_size_t)

        class NCCALCSIZE_PARAMS(ctypes.Structure):
            _fields_ = [("rgrc", wintypes.RECT * 3), ("lppos", ctypes.c_void_p)]

        class WINDOWPOS(ctypes.Structure):
            _fields_ = [("hwnd", wintypes.HWND), ("after", wintypes.HWND), ("x", ctypes.c_int), ("y", ctypes.c_int),
                        ("cx", ctypes.c_int), ("cy", ctypes.c_int), ("flags", ctypes.c_uint)]

        state = {"sizing": False, "busy": False}

        def procedure(window, message, wparam, lparam, _id, _data):
            if message == WM_NCDESTROY:
                callback = _sizers.pop(hwnd, None)
                if callback is not None:
                    comctl32.RemoveWindowSubclass(window, callback, 0x4D51)
                    _retired.append(callback)
            elif message == WM_ENTERSIZEMOVE:
                state["sizing"] = True
            elif message == WM_EXITSIZEMOVE:
                state["sizing"] = False
            elif message == WM_NCCALCSIZE and wparam and lparam and ANCHOR:
                params = NCCALCSIZE_PARAMS.from_address(lparam)
                old = wintypes.RECT(params.rgrc[2].left, params.rgrc[2].top, params.rgrc[2].right, params.rgrc[2].bottom)
                result = comctl32.DefSubclassProc(window, message, wparam, lparam)
                new = params.rgrc[0]
                width = min(old.right - old.left, new.right - new.left)
                height = min(old.bottom - old.top, new.bottom - new.top)
                if result == 0 and width > 0 and height > 0:
                    params.rgrc[1] = wintypes.RECT(new.left, new.top, new.left + width, new.top + height)
                    params.rgrc[2] = wintypes.RECT(old.left, old.top, old.left + width, old.top + height)
                    return WVR_VALIDRECTS
                return result
            elif message == WM_WINDOWPOSCHANGED and lparam and relayout is not None and SYNC and state["sizing"] and not state["busy"]:
                result = comctl32.DefSubclassProc(window, message, wparam, lparam)
                if not WINDOWPOS.from_address(lparam).flags & SWP_NOSIZE:
                    state["busy"] = True
                    try:
                        relayout()
                    except Exception:  # never let a layout error escape into Windows
                        pass
                    finally:
                        state["busy"] = False
                return result
            return comctl32.DefSubclassProc(window, message, wparam, lparam)

        callback = SUBCLASSPROC(procedure)
        if not comctl32.SetWindowSubclass(hwnd, callback, 0x4D51, 0):
            return False
        _sizers[hwnd] = callback
        return True
    except (AttributeError, OSError):
        return False
