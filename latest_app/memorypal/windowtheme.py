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
