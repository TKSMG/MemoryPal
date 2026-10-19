import base64
import importlib
import math
import os
import random
import re
import struct
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import zlib
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import ttk
from uuid import uuid4

sys.dont_write_bytecode = True

# Windows and popups never fade: they are laid out and painted while fully
# transparent, then shown in one step (see reveal_window).



# Core behavior now lives in the memorypal package. The desktop file keeps the
# Tkinter screens and event flow, while storage, parsing, models, and planning
# are imported from smaller modules.
from memorypal import paths as app_paths
from memorypal.constants import (
    APP_NAME,
    BASE_DPI,
    BASE_MIN_WINDOW,
    BASE_WINDOW,
    COLORS,
    DARK_COLORS,
    LIGHT_COLORS,
    SELF_CHECK_ANSWER,
)
from memorypal.core import (
    answer_assessment,
    clamp,
    enable_dpi_awareness,
    extract_document_text,
    hangman_hint,
    mnemonic_sentence,
    normalize_space,
    parse_prompt_answer_lines,
    salient_keywords,
    split_study_bits,
    today_iso,
)
from memorypal.icon import ensure_icon_file, icon_pixels
from memorypal.models import Card, Capture, FeedbackEntry, sample_cards
from memorypal.paths import (
    active_profile_name,
    create_profile,
    delete_profile,
    list_profiles,
    normalize_profile_name,
    rename_profile,
    switch_active_profile_paths,
)
from memorypal import cloud, cloud_config, onboarding, progress, security, techniques
from memorypal import feedback as feedback_report
from memorypal import media
from memorypal import listen, popup_geometry, scrolling, setbuilder
from memorypal.speech import Speaker
from memorypal.planning import (
    STUDY_HABIT_OPTIONS,
    TIME_UNIT_OPTIONS,
    TIME_UNIT_ORDER,
    build_multi_day_plan,
    build_study_plan,
    plan_for_today,
)
from memorypal.store import MemoryStore, default_accessibility, load_items, normalize_accessibility, safe_int


APP_ROOT = Path(__file__).resolve().parent

# Mac people press Command where Windows people press Control, and the Mac
# writes shortcuts as symbols (⌘K) rather than words (Ctrl+K).
IS_MAC = sys.platform == "darwin"
MOD = "Command" if IS_MAC else "Control"


def shortcut(key):
    """How a Command/Control shortcut is written on this platform: ⌘K or Ctrl+K."""
    return f"\u2318{key}" if IS_MAC else f"Ctrl+{key}"


BACK_SHORTCUT = "\u2318[" if IS_MAC else "Alt + Left"


def platform_text(text):
    """Swap the Windows shortcut names in shared copy for the Mac's."""
    if not IS_MAC:
        return text
    return re.sub(r"Ctrl ?\+ ?([A-Za-z0-9])", lambda match: shortcut(match.group(1).upper()), text)


FILE_MANAGER = "Finder" if IS_MAC else "File Explorer"
# Tk on macOS reports a right-click as Button-2, and Control-click means the same.
CONTEXT_CLICKS = ("<Button-2>", "<Control-Button-1>") if IS_MAC else ("<Button-3>",)


def system_open(target):
    """Open a file, folder or link with its default app. os.startfile is Windows-only."""
    if sys.platform.startswith("win"):
        os.startfile(str(target))
        return
    import subprocess

    subprocess.Popen(["open" if IS_MAC else "xdg-open", str(target)])


def system_reveal(target):
    """Show a file selected in Explorer or Finder."""
    import subprocess

    if sys.platform.startswith("win"):
        subprocess.Popen(["explorer", f"/select,{Path(target)}"])
    elif IS_MAC:
        subprocess.Popen(["open", "-R", str(target)])
    else:
        subprocess.Popen(["xdg-open", str(Path(target).parent)])


def bundled_resource_path(*parts):
    """Find a source or packaged resource without generating it at startup."""
    relative = Path(*parts)
    candidates = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / relative)
    executable_dir = Path(sys.executable).resolve().parent
    candidates.extend(
        (
            APP_ROOT / relative,
            APP_ROOT.parent / relative,
            executable_dir / relative,
            executable_dir.parent / relative,
        )
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def open_web_page(url):
    import webbrowser

    webbrowser.open(url)


def set_window_redraw(widget, enabled):
    """Suspend/resume painting of a Tk widget's native window (Windows only).

    On resume the window and all its children are invalidated and repainted
    together. Returns True if painting was actually changed.
    """
    if not sys.platform.startswith("win"):
        return False
    try:
        import ctypes

        user32 = ctypes.windll.user32
        hwnd = widget.winfo_id()
        user32.SendMessageW(hwnd, 0x000B, 1 if enabled else 0, 0)  # WM_SETREDRAW
        if enabled:
            # RDW_INVALIDATE | RDW_ALLCHILDREN | RDW_UPDATENOW (no RDW_ERASE,
            # which would flash the default brush first).
            user32.RedrawWindow(hwnd, None, None, 0x0001 | 0x0080 | 0x0100)
        return True
    except (AttributeError, OSError, tk.TclError):
        return False


def display_refresh_hz(widget, default=60.0):
    """Refresh rate of the screen showing this window (Windows and Mac; else default).

    Asked fresh each time, since the window can move between a 60Hz and a
    144Hz monitor. Values reported as "hardware default" (0 or 1) or
    anything implausible fall back to the default.
    """
    if IS_MAC:
        hz = _mac_refresh_hz()
        return hz if hz else default
    if not sys.platform.startswith("win"):
        return default
    try:
        import ctypes

        user32 = ctypes.windll.user32
        hwnd = user32.GetAncestor(widget.winfo_id(), 2) or widget.winfo_id()  # GA_ROOT
        hdc = user32.GetDC(hwnd)
        if not hdc:
            return default
        try:
            hz = ctypes.windll.gdi32.GetDeviceCaps(hdc, 116)  # VREFRESH
        finally:
            user32.ReleaseDC(hwnd, hdc)
        return float(hz) if 24 <= hz <= 500 else default
    except (AttributeError, OSError, tk.TclError):
        return default


def _mac_refresh_hz():
    """NSScreen.mainScreen.maximumFramesPerSecond (120 on ProMotion), or None."""
    try:
        import ctypes
        import ctypes.util

        objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
        ctypes.cdll.LoadLibrary(ctypes.util.find_library("AppKit"))
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.objc_getClass.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]
        address = ctypes.cast(objc.objc_msgSend, ctypes.c_void_p).value
        send_id = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(address)
        send_bool = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(address)
        send_long = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p)(address)
        screen = send_id(objc.objc_getClass(b"NSScreen"), objc.sel_registerName(b"mainScreen"))
        selector = objc.sel_registerName(b"maximumFramesPerSecond")
        if not screen or not send_bool(screen, objc.sel_registerName(b"respondsToSelector:"), selector):
            return None
        hz = send_long(screen, selector)
        return float(hz) if 24 <= hz <= 500 else None
    except (AttributeError, OSError, TypeError, ValueError):
        return None


def ms_to_next_vblank():
    """Milliseconds until the screen's next refresh (Windows), or None.

    Scroll steps are timed to start just after a refresh, so each one is
    drawn by the next and a steady scroll moves exactly once per frame.
    Timing steps with plain timers drifted against the refresh, so every
    so often one frame showed two steps and the next none (judder).
    """
    if not sys.platform.startswith("win"):
        return None
    try:
        import ctypes

        timing = _dwm_timing_info()
        if ctypes.windll.dwmapi.DwmGetCompositionTimingInfo(None, ctypes.byref(timing)) != 0:
            return None
        period = timing.qpcRefreshPeriod
        if period <= 0:
            return None
        now, frequency = ctypes.c_int64(), ctypes.c_int64()
        ctypes.windll.kernel32.QueryPerformanceCounter(ctypes.byref(now))
        ctypes.windll.kernel32.QueryPerformanceFrequency(ctypes.byref(frequency))
        ahead = (timing.qpcVBlank - now.value) % period
        return ahead * 1000.0 / frequency.value
    except (AttributeError, OSError, ValueError, ZeroDivisionError):
        return None


_DWM_TIMING_INFO = None


def _dwm_timing_info():
    import ctypes

    global _DWM_TIMING_INFO
    if _DWM_TIMING_INFO is None:
        u32, u64 = ctypes.c_uint32, ctypes.c_uint64
        names = [("cbSize", u32), ("rateRefreshNum", u32), ("rateRefreshDen", u32), ("qpcRefreshPeriod", u64),
                 ("rateComposeNum", u32), ("rateComposeDen", u32), ("qpcVBlank", u64), ("cRefresh", u64),
                 ("cDXRefresh", u32), ("qpcCompose", u64), ("cFrame", u64), ("cDXPresent", u32),
                 ("cRefreshFrame", u64), ("cFrameSubmitted", u64), ("cDXPresentSubmitted", u32),
                 ("cFrameConfirmed", u64), ("cDXPresentConfirmed", u32), ("cRefreshConfirmed", u64),
                 ("cDXRefreshConfirmed", u32), ("cFramesLate", u64), ("cFramesOutstanding", u32),
                 ("cFrameDisplayed", u64), ("qpcFrameDisplayed", u64), ("cRefreshFrameDisplayed", u64),
                 ("cFrameComplete", u64), ("qpcFrameComplete", u64), ("cFramePending", u64),
                 ("qpcFramePending", u64), ("cFramesDisplayed", u64), ("cFramesComplete", u64),
                 ("cFramesPending", u64), ("cFramesAvailable", u64), ("cFramesDropped", u64),
                 ("cFramesMissed", u64), ("cRefreshNextDisplayed", u64), ("cRefreshNextPresented", u64),
                 ("cRefreshesDisplayed", u64), ("cRefreshesPresented", u64), ("cRefreshStarted", u64),
                 ("cPixelsReceived", u64), ("cPixelsDrawn", u64), ("cBuffersEmpty", u64)]
        # dwmapi.h packs its structures to 1 byte.
        _DWM_TIMING_INFO = type("DWM_TIMING_INFO", (ctypes.Structure,), {"_pack_": 1, "_fields_": names})
    info = _DWM_TIMING_INFO()
    info.cbSize = ctypes.sizeof(info)
    return info


def set_fine_timers(enabled):
    """Ask Windows for 1ms timer resolution while an animation runs.

    Windows wakes timers on a ~15.6ms tick by default, so Tk's after(8)
    really waited 16 or 31ms and a scroll glide stepped at an uneven 30-60fps.
    Calls must be paired; returns True if the resolution was changed.
    """
    if not sys.platform.startswith("win"):
        return False
    try:
        import ctypes

        winmm = ctypes.windll.winmm
        (winmm.timeBeginPeriod if enabled else winmm.timeEndPeriod)(1)
        return True
    except (AttributeError, OSError):
        return False


def flush_pending_paint(widget):
    """Draw queued Expose events now instead of on a later event-loop pass."""
    try:
        import _tkinter

        flags = _tkinter.WINDOW_EVENTS | _tkinter.DONT_WAIT
        handled = 0
        while handled < 500 and widget.tk.dooneevent(flags):
            handled += 1
        widget.update_idletasks()
        return handled
    except (AttributeError, tk.TclError):
        return 0


def show_screen_cover(width, height, left=0, top=0, source=None):
    """Put a pixel-identical, topmost snapshot of part of the screen over it.

    The captured bitmap is handed straight to a layered popup window
    (UpdateLayeredWindow), so it appears atomically with no Tk image
    conversion. The window never takes focus, ignores the mouse (clicks and
    drags go to the app underneath), and doesn't show in the taskbar.

    With `source` (a widget at left/top), its pixels are copied from its own
    window instead of the screen, which reads memory rather than the
    composed screen (about 1ms instead of 10-50ms). That copy doesn't
    include windows overlapping the app, so the snapshot is slotted into the
    z-order directly above the app's top-level window, below anything
    already above it (dialogs, tooltips, other programs).
    Returns a handle for remove_screen_cover, or None if unavailable.
    """
    if not sys.platform.startswith("win"):
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class BlendFunction(ctypes.Structure):
            _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
                        ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte)]

        user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
        user32.CreateWindowExW.restype = wintypes.HWND
        user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                           ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                           wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
        source_hwnd = source.winfo_id() if source is not None else 0
        app_hwnd = user32.GetAncestor(source_hwnd, 2) if source_hwnd else 0  # GA_ROOT
        topmost = not app_hwnd or bool(user32.GetWindowLongW(app_hwnd, -20) & 0x00000008)  # GWL_EXSTYLE, WS_EX_TOPMOST
        screen_dc = user32.GetDC(0)
        source_dc = user32.GetDC(source_hwnd) if source_hwnd else screen_dc
        memory_dc = gdi32.CreateCompatibleDC(screen_dc)
        bitmap = gdi32.CreateCompatibleBitmap(screen_dc, width, height)
        previous = gdi32.SelectObject(memory_dc, bitmap)
        hwnd = None
        try:
            if source_hwnd:
                gdi32.BitBlt(memory_dc, 0, 0, width, height, source_dc, 0, 0, 0x00CC0020)  # SRCCOPY
            else:
                gdi32.BitBlt(memory_dc, 0, 0, width, height, screen_dc, left, top, 0x00CC0020)
            # WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE (+ WS_EX_TOPMOST), WS_POPUP
            ex_style = 0x00080000 | 0x00000020 | 0x00000080 | 0x08000000 | (0x00000008 if topmost else 0)
            hwnd = user32.CreateWindowExW(ex_style, "STATIC", None, 0x80000000, left, top, width, height, None, None, None, None)
            if not hwnd:
                return None
            origin, size = wintypes.POINT(left, top), wintypes.SIZE(width, height)
            blend = BlendFunction(0, 0, 255, 0)
            if not user32.UpdateLayeredWindow(hwnd, screen_dc, ctypes.byref(origin), ctypes.byref(size), memory_dc,
                                              ctypes.byref(wintypes.POINT(0, 0)), 0, ctypes.byref(blend), 0x4):  # ULW_OPAQUE
                user32.DestroyWindow(hwnd)
                return None
            insert_after = 0  # HWND_TOP of the cover's band
            if app_hwnd:
                above = user32.GetWindow(app_hwnd, 3)  # GW_HWNDPREV: the window right above the app
                # A topmost window above a normal app marks the top of the
                # normal band, where HWND_TOP already lands.
                if above and topmost == bool(user32.GetWindowLongW(above, -20) & 0x00000008):
                    insert_after = above
            # Slot it in (SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE), then show
            # it where it is; SWP_SHOWWINDOW here left layered windows hidden.
            user32.SetWindowPos(hwnd, insert_after, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)
            user32.ShowWindow(hwnd, 4)  # SW_SHOWNOACTIVATE
            ctypes.windll.dwmapi.DwmFlush()  # make sure it is on screen before anything changes
            return hwnd
        finally:
            gdi32.SelectObject(memory_dc, previous)
            gdi32.DeleteObject(bitmap)
            gdi32.DeleteDC(memory_dc)
            if source_hwnd:
                user32.ReleaseDC(source_hwnd, source_dc)
            user32.ReleaseDC(0, screen_dc)
    except (AttributeError, OSError, tk.TclError):
        return None


def refresh_screen_cover(cover, width, height, source):
    """Show a fresh copy of `source` in an existing cover, in one frame.

    Used while scrolling: one cover stays up for the whole scroll and each
    step swaps its picture, instead of a cover being made and removed for
    every step (each of those waited for the screen twice, which halved the
    frame rate). Waits for the next screen refresh, which paces the steps.
    Returns False if the picture couldn't be swapped.
    """
    if not sys.platform.startswith("win"):
        return False
    try:
        import ctypes
        from ctypes import wintypes

        class BlendFunction(ctypes.Structure):
            _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
                        ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte)]

        user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
        source_hwnd = source.winfo_id()
        screen_dc = user32.GetDC(0)
        source_dc = user32.GetDC(source_hwnd)
        memory_dc = gdi32.CreateCompatibleDC(screen_dc)
        bitmap = gdi32.CreateCompatibleBitmap(screen_dc, width, height)
        previous = gdi32.SelectObject(memory_dc, bitmap)
        try:
            gdi32.BitBlt(memory_dc, 0, 0, width, height, source_dc, 0, 0, 0x00CC0020)  # SRCCOPY
            size = wintypes.SIZE(width, height)
            blend = BlendFunction(0, 0, 255, 0)
            # No position: the cover stays where it is, only its picture changes.
            done = user32.UpdateLayeredWindow(cover, screen_dc, None, ctypes.byref(size), memory_dc,
                                              ctypes.byref(wintypes.POINT(0, 0)), 0, ctypes.byref(blend), 0x4)  # ULW_OPAQUE
            if done:
                ctypes.windll.dwmapi.DwmFlush()
            return bool(done)
        finally:
            gdi32.SelectObject(memory_dc, previous)
            gdi32.DeleteObject(bitmap)
            gdi32.DeleteDC(memory_dc)
            user32.ReleaseDC(source_hwnd, source_dc)
            user32.ReleaseDC(0, screen_dc)
    except (AttributeError, OSError, tk.TclError):
        return False


def remove_screen_cover(cover):
    try:
        import ctypes

        ctypes.windll.dwmapi.DwmFlush()  # let the finished window be composed underneath first
        ctypes.windll.user32.DestroyWindow(cover)
    except (AttributeError, OSError):
        pass


class ScrollFrame(ttk.Frame):
    """Stable, clipped scrolling surface.

    The viewport never moves or resizes while its contents scroll.  The canvas
    owns the scroll coordinate and the content frame is only a canvas window.
    This avoids the old feedback loop where changing the content position
    changed the measured scroll region, which in turn moved the content again.
    """

    FRAME_MS = 1000 / 60  # wheel glide pacing until the screen's own rate is known
    # When any page last got wheel or trackpad input; background work waits
    # for scrolling to stop so it never costs a frame mid-glide.
    last_wheel_time = 0.0

    def __init__(self, parent, horizontal=False, min_width=0, bottom_padding=None):
        super().__init__(parent)
        self.horizontal = horizontal
        self.min_width = int(min_width or 0)
        root = parent.winfo_toplevel()
        scale = getattr(root, "ui_scale", 1.0)
        self.bottom_padding = max(12, int(round((bottom_padding if bottom_padding is not None else 18) * scale)))
        self._region_after = None
        self._destroyed = False
        self._wheel_remainder_y = 0.0
        self._wheel_remainder_x = 0.0
        self._wheel_step_px = max(36, int(round(72 * scale)))
        self._window_id = None
        self._updating_width = False
        self._wheel_bind_ids = []
        self._settle_after = None
        self._settle_attempts = 0
        self._last_content_h = None
        self._last_inner_size = None
        self._pending_drag = {}
        self._drag_after = None
        self._wheel_pending = {}
        self._wheel_targets = {}
        self._glide_last = {}
        self._wheel_after = None
        self._presenting = False
        self._live_cover = None  # (window, geometry) of the snapshot kept up while scrolling
        self._live_cover_after = None
        self._glide_time = None
        self._fine_timers = False
        self._frame_ms = self.FRAME_MS
        self._last_step = 0.0
        self._idle_after = None
        self._touchpad_time = -1.0
        self._last_wheel_event = 0.0
        self._glide_tau = {}

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.viewport = tk.Canvas(
            self, bg=COLORS["bg"], highlightthickness=0, bd=0,
            relief="flat", takefocus=0,
        )
        # Keep the scrollbar compact and inside this frame's exact grid cell.
        self.scrollbar = ttk.Scrollbar(
            self, orient="vertical", command=self._scrollbar_yview, style="Vertical.TScrollbar"
        )
        self.x_scrollbar = (
            ttk.Scrollbar(
                self, orient="horizontal", command=self._scrollbar_xview, style="Horizontal.TScrollbar"
            )
            if horizontal else None
        )

        self.inner = ttk.Frame(self.viewport, style="Page.TFrame")
        self._window_id = self.viewport.create_window(0, 0, window=self.inner, anchor="nw")

        self.viewport.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        if self.x_scrollbar is not None:
            self.x_scrollbar.grid(row=1, column=0, sticky="ew")

        self.inner.bind("<Configure>", self._content_configured, add="+")
        self.viewport.bind("<Configure>", self._viewport_configured, add="+")
        for widget in (self.viewport, self.inner):
            widget.bind("<Enter>", self._activate_wheel, add="+")
        self.viewport.bind("<Prior>", lambda _e: self._scroll_pages(-1))
        self.viewport.bind("<Next>", lambda _e: self._scroll_pages(1))
        self.viewport.bind("<Home>", lambda _e: self._scroll_to(0.0))
        self.viewport.bind("<End>", lambda _e: self._scroll_to(1.0))
        self.after_idle(self.refresh_scrollregion)

    def _content_configured(self, event=None):
        # Scrolling moves the content window, which also fires <Configure>.
        # Only a size change needs the scroll region re-measured; doing it on
        # every scroll step forced a full relayout mid-drag and caused tearing.
        size = (event.width, event.height) if event is not None else None
        if size is not None and size == self._last_inner_size:
            return
        self._last_inner_size = size
        self.queue_scrollregion_update()

    def _viewport_configured(self, event):
        if self._window_id is None or self._updating_width:
            return
        if not self.horizontal:
            self._updating_width = True
            try:
                self.viewport.itemconfigure(self._window_id, width=max(1, event.width))
            finally:
                self._updating_width = False
        self.queue_scrollregion_update()

    def queue_scrollregion_update(self):
        if self._region_after is not None or self._destroyed:
            return
        try:
            self._region_after = self.after_idle(self.refresh_scrollregion)
        except tk.TclError:
            self._region_after = None

    def refresh_scrollregion(self):
        self._region_after = None
        if self._destroyed:
            return
        try:
            # Measure the actual requested height of the inner frame.  Canvas
            # window bboxes can lag one geometry pass behind on pages containing
            # wrapped labels, which was the reason some pages stopped short.
            self.update_idletasks()
            bbox = self.viewport.bbox(self._window_id)
            vw = max(1, self.viewport.winfo_width())
            vh = max(1, self.viewport.winfo_height())
            req_w = max(1, self.inner.winfo_reqwidth())
            req_h = max(1, self.inner.winfo_reqheight())
            actual_h = max(1, self.inner.winfo_height())
            if bbox:
                bbox_w = max(1, int(bbox[2] - bbox[0]))
                bbox_h = max(1, int(bbox[3] - bbox[1]))
            else:
                bbox_w = bbox_h = 1
            content_w = max(vw, req_w, bbox_w)
            content_h = max(vh, req_h, actual_h, bbox_h) + self.bottom_padding
            if not self.horizontal:
                content_w = vw
            else:
                content_w = max(content_w, self.min_width)

            self.viewport.configure(scrollregion=(0, 0, int(content_w), int(content_h)))
            self._sync_scrollbars()

            # Wrapped text and some ttk widgets can settle across more than
            # one geometry pass on content-heavy pages (dashboard, stats,
            # library). A single fixed-delay check can land before a page
            # like that has finished growing, which is what silently
            # trimmed the bottom of the scroll range. Keep re-checking on a
            # short schedule as long as the measured height is still
            # growing, and stop once it holds steady (or after a capped
            # number of attempts, so a genuinely still-changing page can't
            # loop forever).
            previous = self._last_content_h
            self._last_content_h = content_h
            if previous is None or content_h > previous + 1:
                if self._settle_after is None and self._settle_attempts < 8:
                    self._settle_attempts += 1
                    self._settle_after = self.after(45, self._settle_scrollregion)
            else:
                self._settle_attempts = 0
        except tk.TclError:
            pass

    def _settle_scrollregion(self):
        self._settle_after = None
        if self._destroyed:
            return
        self.refresh_scrollregion()

    def _activate_wheel(self, _event=None):
        if self._destroyed or self._wheel_bind_ids:
            return
        try:
            root = self.winfo_toplevel()
            self._wheel_bind_ids = [
                root.bind_all("<MouseWheel>", self._wheel, add="+"),
                root.bind_all("<Button-4>", self._wheel, add="+"),
                root.bind_all("<Button-5>", self._wheel, add="+"),
            ]
        except tk.TclError:
            self._wheel_bind_ids = []

    def _nearest_scrollframe_under_pointer(self, event):
        try:
            widget = self.winfo_containing(event.x_root, event.y_root)
        except tk.TclError:
            return None
        while widget is not None:
            if widget is self or isinstance(widget, ScrollFrame):
                return widget
            widget = getattr(widget, "master", None)
        return None

    def _wheel(self, event):
        if self._destroyed or self._nearest_scrollframe_under_pointer(event) is not self:
            return None
        if self._inner_box_scrolls(event.widget):
            return None  # a text box or list with its own scrollbar scrolls alone
        # Wheel notches glide (eased over ~160ms, extra notches push the same
        # glide further); touchpad deltas are followed 1:1, since the system
        # has already smoothed them. See memorypal/scrolling.py.
        number = getattr(event, "num", None)
        button = number if number in (4, 5) else None
        delta = float(getattr(event, "delta", 0) or 0)
        now = time.perf_counter()
        gap, self._last_wheel_event = now - self._last_wheel_event, now
        if scrolling.is_touchpad_delta(delta, IS_MAC, button):
            self._touchpad_time = now
        root = self.winfo_toplevel()
        pixels, tau = scrolling.wheel_motion(
            delta, self._wheel_step_px, mac=IS_MAC, button=button, gap_s=gap,
            since_touchpad_s=now - self._touchpad_time,
            reduce_motion=bool(getattr(root, "accessibility", {}).get("reduce_motion")),
        )
        if not pixels:
            return "break"
        axis = "x" if self.horizontal and getattr(event, "state", 0) & 0x0001 else "y"
        if tau <= 0:
            self._direct_scroll(pixels, axis=axis)
        else:
            self._queue_wheel(pixels, axis=axis, tau=tau)
        return "break"

    @staticmethod
    def _inner_box_scrolls(widget):
        if not isinstance(widget, (tk.Text, tk.Listbox)):
            return False
        try:
            first, last = widget.yview()
        except (tk.TclError, ValueError):
            return False
        return first > 0.0 or last < 1.0

    def _mac_wheel(self, event):
        """Mac wheels and trackpads send small deltas (about 1 per notch) many
        times a second, already eased by macOS, so they move the page directly
        instead of being counted in Windows' 120-per-notch units."""
        delta = float(getattr(event, "delta", 0) or 0)
        if not delta or abs(delta) >= 120:
            return False
        axis = "x" if self.horizontal and getattr(event, "state", 0) & 0x0001 else "y"
        self._direct_scroll(-delta * self._wheel_step_px / 7, axis)
        return True

    def _direct_scroll(self, pixels, axis="y"):
        """Move with the fingers, 1:1, once per screen refresh.

        Touchpads already ease and coast in the operating system, so easing
        them again made the page lag behind the fingers. Every delta that
        arrives within one frame is summed and drawn in that frame's step.
        """
        ScrollFrame.last_wheel_time = time.perf_counter()
        self._wheel_pending[axis] = self._wheel_pending.get(axis, 0) + pixels
        self._request_frame()

    def _queue_wheel(self, pixels, axis="y", tau=scrolling.NOTCH_TAU_MS):
        # A fast wheel spin delivers many events per frame; moving and
        # repainting for each one outruns the embedded widgets and tears.
        # Sum the distance and apply it once per screen refresh. Timers still
        # fire while input events stream in; idle callbacks (and Tk's
        # repaints) don't.
        root = self.winfo_toplevel()
        if getattr(root, "accessibility", {}).get("reduce_motion"):
            self._direct_scroll(pixels, axis)
            return
        ScrollFrame.last_wheel_time = time.perf_counter()
        # Otherwise glide: each notch moves the target, and every frame covers
        # part of the remaining distance, so a notch eases in over a few
        # frames instead of jumping, and a fast spin becomes one smooth glide.
        position = self._scroll_position(axis)
        if position is None:
            return
        current, maximum = position
        base = self._wheel_targets.get(axis, current)
        self._wheel_targets[axis] = scrolling.clamp_target(base, pixels, maximum)
        self._glide_tau[axis] = tau
        self._request_frame()

    def _request_frame(self):
        if self._wheel_after is not None or self._destroyed:
            return
        if self._idle_after is not None:
            self.after_cancel(self._idle_after)
            self._idle_after = None
        if not self._fine_timers:
            self._fine_timers = set_fine_timers(True)
        if self._glide_time is None or time.perf_counter() - self._last_step > self._frame_ms / 1000.0:
            # Nothing drawn in the last frame: respond to the fingers at once.
            wait = 1
        else:
            wait = self._frame_wait()
        self._wheel_after = self.after(wait, self._scroll_step)

    def _frame_wait(self):
        """Milliseconds to wait so the next step starts just after a refresh."""
        spent = (time.perf_counter() - self._last_step) * 1000
        ahead = ms_to_next_vblank()
        if ahead is None or spent > self._frame_ms * 0.85:
            # No refresh timing, or this page takes about a frame to draw:
            # waiting for the next refresh would halve the rate, so go now.
            return max(1, round(self._frame_ms - spent))
        # Starting right after the refresh leaves the whole frame for drawing.
        return max(1, int(ahead) + 1)

    def _flush_wheel(self):
        self._scroll_step()

    def _scroll_position(self, axis):
        """(current offset, largest offset) in pixels, or None if unknown."""
        try:
            region = self.viewport.cget("scrollregion").split()
            if len(region) < 4:
                return None
            total = float(region[3] if axis == "y" else region[2])
            visible = float(self.viewport.winfo_height() if axis == "y" else self.viewport.winfo_width())
            first, _last = self.viewport.yview() if axis == "y" else self.viewport.xview()
            return first * total, max(0.0, total - visible)
        except (tk.TclError, ValueError, TypeError):
            return None

    def _glide_wheel(self):
        self._scroll_step()

    def _scroll_step(self):
        """One frame of scrolling: direct (touchpad) moves plus wheel glides."""
        self._wheel_after = None
        if self._destroyed:
            return
        now = time.perf_counter()
        if self._glide_time is None:
            # Scrolling starts: step at the refresh rate of the screen it's on.
            self._frame_ms = 1000.0 / display_refresh_hz(self)
        # Milliseconds since the last step (one frame for the first),
        # capped so a stall doesn't turn into a jump.
        elapsed = self._frame_ms if self._glide_time is None else min(50.0, max(1.0, (now - self._glide_time) * 1000))
        self._glide_time = now
        moves, self._wheel_pending = self._wheel_pending, {}
        for axis, pixels in moves.items():
            if axis in self._wheel_targets:
                # Fingers on the pad take over from a wheel glide.
                self._wheel_targets.pop(axis, None)
                self._glide_last.pop(axis, None)
        for axis, target in list(self._wheel_targets.items()):
            position = self._scroll_position(axis)
            if position is None:
                self._wheel_targets.pop(axis, None)
                continue
            current, _maximum = position
            remaining = target - current
            stalled = abs(current - self._glide_last.get(axis, current + 99)) < 0.5
            self._glide_last[axis] = current
            if stalled:
                # The page couldn't move (it shrank, or hit an edge): stop.
                step, done = 0, True
            else:
                # An exponential ease-out measured in time, not frames, so a
                # notch takes the same ~160ms at 60Hz or 144Hz; it lands on
                # the exact pixel instead of snapping the last few at once.
                step, done = scrolling.glide_step(remaining, elapsed, self._glide_tau.get(axis, scrolling.NOTCH_TAU_MS))
            if done:
                self._wheel_targets.pop(axis, None)
                self._glide_last.pop(axis, None)
                self._glide_tau.pop(axis, None)
            moves[axis] = moves.get(axis, 0) + step
        for axis, pixels in moves.items():
            if pixels:
                self._scroll_pixels(pixels, axis=axis)
        self._last_step = now
        if self._wheel_targets and not self._destroyed:
            self._wheel_after = self.after(self._frame_wait(), self._scroll_step)
        elif not self._destroyed:
            # Touchpad deltas keep arriving between frames; stay on the
            # frame clock until they've stopped for a moment.
            self._idle_after = self.after(250, self._end_glide_timing)

    def _end_glide_timing(self):
        self._idle_after = None
        self._glide_time = None
        if self._fine_timers:
            set_fine_timers(False)
            self._fine_timers = False

    def _stop_glide(self):
        """A scrollbar drag, page key or jump takes over from a wheel glide."""
        self._wheel_targets.clear()
        self._glide_last.clear()
        if self._idle_after is not None:
            self.after_cancel(self._idle_after)
        self._end_glide_timing()

    def _wheel_units(self, event, axis="y"):
        number = getattr(event, "num", None)
        if number == 4:
            return -1
        if number == 5:
            return 1
        delta = float(getattr(event, "delta", 0) or 0)
        if not delta:
            return 0
        remainder_name = "_wheel_remainder_x" if axis == "x" else "_wheel_remainder_y"
        remainder = getattr(self, remainder_name) + delta
        units = int(-remainder / 120.0)
        setattr(self, remainder_name, remainder + units * 120.0)
        return units

    def _scroll_pixels(self, pixels, axis="y"):
        try:
            region = self.viewport.cget("scrollregion").split()
            if len(region) < 4:
                return
            total = float(region[3] if axis == "y" else region[2])
            visible = float(self.viewport.winfo_height() if axis == "y" else self.viewport.winfo_width())
            maximum = max(0.0, total - visible)
            first, _last = self.viewport.yview() if axis == "y" else self.viewport.xview()
            # yview/xview fractions are relative to the full scroll region.
            current = first * total
            target = max(0.0, min(maximum, current + float(pixels)))
            fraction = 0.0 if total <= 0 else target / total
            mover = self.viewport.yview_moveto if axis == "y" else self.viewport.xview_moveto
            self._present(lambda: mover(fraction), distance=abs(target - current))
        except (tk.TclError, ValueError, TypeError):
            pass

    def _present(self, move, distance=None):
        """Apply a scroll move and paint the result before the next one.

        Tk only repaints from idle callbacks, which never run while a
        scrollbar drag streams motion events, so Windows kept shifting stale
        pixels and the page smeared into overlapping ghosts. Each move now
        runs from a timer and immediately draws the newly exposed area.
        Moves are never nested: one requested while painting runs as its own
        frame afterwards.

        `distance` is how far the move goes in pixels, if known. Short moves
        (wheel and touchpad steps) are blitted by Windows and only a thin
        strip is drawn fresh, so they skip the snapshot cover: copying the
        window into the cover and waiting for it to be composed took about
        16ms a step, which held scrolling to half the screen's frame rate.
        """
        if self._presenting:
            self.after(1, lambda: self._present(move, distance))
            return
        self._presenting = True
        cover = None
        try:
            # Even painted straight away, Windows composited frames where the
            # cards had moved but their text wasn't drawn yet (tearing). A
            # snapshot of just the scrolling area hides each step until it
            # is fully drawn, then the new position appears in one frame.
            # The snapshot stays up while scrolling continues; each step only
            # swaps its picture (see refresh_screen_cover).
            root = self.winfo_toplevel()
            geometry = None
            if not getattr(root, "use_native_window_chrome", True) and not getattr(root, "_hidden_active", False):
                width, height = self.viewport.winfo_width(), self.viewport.winfo_height()
                if width > 1 and height > 1:
                    geometry = (width, height, self.viewport.winfo_rootx(), self.viewport.winfo_rooty())
            small = distance is not None and distance <= self.viewport.winfo_height() / 3
            if small:
                geometry = None
            live = self._live_cover
            if live is not None and live[1] != geometry:
                self._release_live_cover()
                live = None
            if live is None and geometry is not None:
                cover = show_screen_cover(*geometry, source=self.viewport)
            move()
            self._sync_scrollbars()
            self.viewport.update_idletasks()
            flush_pending_paint(self.viewport)
            if live is not None:
                if not refresh_screen_cover(live[0], geometry[0], geometry[1], self.viewport):
                    self._release_live_cover()
            elif cover is not None:
                if refresh_screen_cover(cover, geometry[0], geometry[1], self.viewport):
                    self._live_cover, cover = (cover, geometry), None
        finally:
            self._presenting = False
            if cover is not None:
                remove_screen_cover(cover)
            if self._live_cover is not None:
                # Taken down once scrolling has paused; by then the window
                # underneath shows exactly the same picture.
                if self._live_cover_after is not None:
                    self.after_cancel(self._live_cover_after)
                self._live_cover_after = self.after(90, self._release_live_cover)

    def _release_live_cover(self):
        if self._live_cover_after is not None:
            try:
                self.after_cancel(self._live_cover_after)
            except tk.TclError:
                pass
            self._live_cover_after = None
        live, self._live_cover = self._live_cover, None
        if live is not None:
            remove_screen_cover(live[0])

    def _scrollbar_yview(self, *args):
        self._scrollbar_view("y", args)

    def _scrollbar_xview(self, *args):
        if self.x_scrollbar is None:
            return
        self._scrollbar_view("x", args)

    def _scrollbar_view(self, axis, args):
        # Thumb drags send a "moveto" per mouse event, far faster than the
        # embedded widgets can repaint, so half-drawn frames tear and overlap.
        # Keep only the latest drag position and apply it on a timer, which
        # still fires during a continuous drag (idle callbacks, including
        # Tk's own repaints, are starved until the mouse stops). Arrow/trough clicks are
        # relative steps and apply immediately.
        self._stop_glide()
        if args and args[0] == "moveto":
            self._pending_drag[axis] = args
            if self._drag_after is None and not self._destroyed:
                self._drag_after = self.after(1, self._flush_scrollbar_drag)
            return
        try:
            self._present(lambda: (self.viewport.yview if axis == "y" else self.viewport.xview)(*args))
        except tk.TclError:
            pass

    def _flush_scrollbar_drag(self):
        self._drag_after = None
        pending, self._pending_drag = self._pending_drag, {}
        if self._destroyed or not pending:
            return

        def move():
            for axis, args in pending.items():
                (self.viewport.yview if axis == "y" else self.viewport.xview)(*args)

        distance = None
        try:
            region = self.viewport.cget("scrollregion").split()
            args = pending.get("y")
            if args is not None and len(args) >= 2 and len(region) >= 4 and len(pending) == 1:
                total = float(region[3])
                distance = abs(float(args[1]) - self.viewport.yview()[0]) * total
        except (tk.TclError, ValueError, TypeError):
            distance = None
        try:
            self._present(move, distance)
        except tk.TclError:
            pass

    def _sync_scrollbars(self):
        try:
            self.scrollbar.set(*self.viewport.yview())
            if self.x_scrollbar is not None:
                self.x_scrollbar.set(*self.viewport.xview())
        except tk.TclError:
            pass

    def begin_scrollbar_drag(self, axis):
        pass

    def commit_scrollbar_drag(self, axis):
        self._sync_scrollbars()

    def preview_scrollbar_drag(self, fraction, axis):
        try:
            fraction = max(0.0, min(1.0, float(fraction)))
            if axis == "x" and self.x_scrollbar is not None:
                self.viewport.xview_moveto(fraction)
            elif axis == "y":
                self.viewport.yview_moveto(fraction)
            self._sync_scrollbars()
        except (tk.TclError, ValueError, TypeError):
            pass

    def handle_scrollbar(self, args, axis="y"):
        if not args:
            return
        try:
            if axis == "y":
                self.viewport.yview(*args)
            elif self.x_scrollbar is not None:
                self.viewport.xview(*args)
            self._sync_scrollbars()
        except tk.TclError:
            pass

    def scroll_by(self, dx=0, dy=0):
        if dy:
            self._scroll_pixels(dy, "y")
        if dx:
            self._scroll_pixels(dx, "x")

    def _scroll_pages(self, direction):
        self._stop_glide()
        try:
            self._present(lambda: self.viewport.yview_scroll(direction, "pages"))
        except tk.TclError:
            pass
        return "break"

    def _scroll_to(self, position):
        self._stop_glide()
        try:
            self._present(lambda: self.viewport.yview_moveto(max(0.0, min(1.0, float(position)))))
        except tk.TclError:
            pass
        return "break"

    def max_y_offset(self):
        try:
            region = self.viewport.cget("scrollregion").split()
            return max(0.0, float(region[3]) - self.viewport.winfo_height()) if len(region) >= 4 else 0.0
        except (tk.TclError, ValueError, TypeError):
            return 0.0

    def max_x_offset(self):
        try:
            region = self.viewport.cget("scrollregion").split()
            return max(0.0, float(region[2]) - self.viewport.winfo_width()) if len(region) >= 4 else 0.0
        except (tk.TclError, ValueError, TypeError):
            return 0.0

    def scroll_to_offsets(self, x=None, y=None, sync=True):
        try:
            # xview/yview_moveto take a fraction of the whole scroll region.
            region = self.viewport.cget("scrollregion").split()
            if x is not None and len(region) >= 4 and float(region[2]) > 0:
                self.viewport.xview_moveto(max(0.0, min(float(x), self.max_x_offset())) / float(region[2]))
            if y is not None and len(region) >= 4 and float(region[3]) > 0:
                self.viewport.yview_moveto(max(0.0, min(float(y), self.max_y_offset())) / float(region[3]))
            if sync:
                self._sync_scrollbars()
        except (tk.TclError, ValueError, TypeError):
            pass

    def destroy(self):
        self._destroyed = True
        self._release_live_cover()
        if self._idle_after is not None:
            try:
                self.after_cancel(self._idle_after)
            except tk.TclError:
                pass
        self._end_glide_timing()
        try:
            if self._region_after is not None:
                self.after_cancel(self._region_after)
            if self._settle_after is not None:
                self.after_cancel(self._settle_after)
            if self._drag_after is not None:
                self.after_cancel(self._drag_after)
            if self._wheel_after is not None:
                self.after_cancel(self._wheel_after)
            root = self.winfo_toplevel()
            for bind_id, sequence in zip(self._wheel_bind_ids, ("<MouseWheel>", "<Button-4>", "<Button-5>")):
                # unbind_all() can't target one callback and would drop every
                # other ScrollFrame's wheel handler, so strip just this one
                # from the shared "all" binding script.
                try:
                    script = str(root.tk.call("bind", "all", sequence))
                    kept = "\n".join(line for line in script.split("\n") if bind_id not in line)
                    root.tk.call("bind", "all", sequence, kept)
                    root.deletecommand(bind_id)
                except tk.TclError:
                    pass
        except tk.TclError:
            pass
        self._wheel_bind_ids = []
        super().destroy()


class Tooltip:
    def __init__(self, widget, text, delay=550):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.after_id = None
        self.tip = None
        widget.bind("<Enter>", self.schedule, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress>", self.hide, add="+")

    def schedule(self, _event=None):
        self.cancel()
        self.after_id = self.widget.after(self.delay, self.show)

    def cancel(self):
        if self.after_id:
            self.widget.after_cancel(self.after_id)
            self.after_id = None

    def _px(self, value):
        root = self.widget._root()
        return root.px(value) if hasattr(root, "px") else value

    def show(self):
        if self.tip or not self.text:
            return
        self.tip = tk.Toplevel(self.widget)
        self.tip.withdraw()
        self.tip.wm_overrideredirect(True)
        label = tk.Label(
            self.tip,
            text=self.text,
            # A raised surface with a hairline edge: on the rail, a rail-coloured
            # tip had no visible box and read as stray text.
            bg=COLORS["surface_soft"],
            fg=COLORS["ink"],
            highlightthickness=1,
            highlightbackground=COLORS["line"],
            padx=self._px(10),
            pady=self._px(7),
            justify="left",
            wraplength=self._px(280),
            font=self.widget._root().font("Segoe UI", 10) if hasattr(self.widget._root(), "font") else ("Segoe UI", 10),
        )
        label.pack()
        # Below the widget, nudged right; flipped above or shifted left when
        # it would run off the screen edge.
        self.tip.update_idletasks()
        width, height = self.tip.winfo_reqwidth(), self.tip.winfo_reqheight()
        left, top = self.widget.winfo_rootx() + self._px(18), self.widget.winfo_rooty()
        anchor = (left, top, left, top + self.widget.winfo_height())
        screen = (0, 0, self.widget.winfo_screenwidth(), self.widget.winfo_screenheight())
        x, y, width, height = popup_geometry.fit_popup_rect(width, height, anchor, screen, gap=self._px(8), margin=self._px(8))
        self.tip.wm_geometry(f"+{x}+{y}")
        self.tip.deiconify()

    def hide(self, _event=None):
        self.cancel()
        if self.tip:
            self.tip.destroy()
            self.tip = None


class MemoryPalApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.use_native_window_chrome = sys.platform == "darwin"
        self._chrome_update_active = False
        self._taskbar_ready = False
        self.withdraw()
        if not self.use_native_window_chrome:
            self.overrideredirect(True)
        self.resizable(True, True)
        try:
            self.attributes("-alpha", 0.0)
        except tk.TclError:
            pass
        self.dpi_scale, self.size_scale = self._display_scales()
        self.base_ui_scale = clamp(max(self.dpi_scale, self.size_scale), 0.95, 1.35)
        self.base_font_scale = clamp(self.size_scale, 0.96, 1.12)
        self.ui_scale = self.base_ui_scale
        self.font_scale = self.base_font_scale
        try:
            self.tk.call("tk", "scaling", clamp(self.dpi_scale * BASE_DPI / 72, 1.0, 2.4))
        except tk.TclError:
            pass
        self.theme = "dark"
        self.store = MemoryStore()
        self.init_cloud()
        self.accessibility = normalize_accessibility(self.store.accessibility)
        self.apply_accessibility_preferences()
        self.current_view = "dashboard"
        self.current_review = None
        self.quiz_cards = []
        self.quiz_round = 0
        self.quiz_score = 0
        self.quiz_mode = "self"
        self.sequence = ""
        self.testing_card = None
        self.return_view = "dashboard"
        self.testing_context = "study"
        self.pending_media = {"text_file": "", "image": "", "audio": "", "video": ""}
        self.route_token = 0
        self.media_images = []
        self.view_drafts = {}
        self.draft_savers = {}
        self.deck_filter = None
        self._hotkeys_bound = False
        self.is_fullscreen = False
        self.is_focus_window = False
        self.restoring_borderless = False
        self.window_transition_active = False
        self.page_transition_image = None
        self.page_transition_canvas = None
        self.page_transition_photo = None
        self.normal_geometry = ""
        self.drag_start = None
        self.resize_start = None
        self.pending_resize_geometry = None
        self.root_cover = None
        self.logo_photo_cache = {}
        self.shape_photo_cache = {}
        self.logo_source_path = bundled_resource_path("assets", "memorypal-logo-preview.png")
        self._pillow_modules = None
        self._pillow_unavailable = False
        self._font_families = None
        self.speaker = Speaker()
        self.listener = listen.Listener()
        self.talkback = None
        self.audio_player = media.AudioPlayer()
        self.preview_photos = {}

        self.app_icon_path = None
        self.title(f"{APP_NAME} \u2014 {active_profile_name()}")
        self.apply_app_icon()
        self._set_window_size()
        self.configure(bg=COLORS["bg"])
        self._styles()
        self.install_text_selection()
        self.install_smooth_box_scrolling()
        self.keep_flat_buttons_still()
        self.track_focus_source()
        self._shell()
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        if IS_MAC:
            self.install_mac_menus()
        self.bind("<Map>", self.restore_window_chrome, add="+")
        self.bind("<F11>", lambda _event: self.toggle_true_fullscreen())
        for sequence in ("<Control-Command-f>", "<Command-Control-f>"):
            try:
                self.bind(sequence, lambda _event: self.toggle_true_fullscreen(), add="+")
            except tk.TclError:
                pass
        self.bind("<Escape>", lambda _event: self.exit_fullscreen_or_focus())
        self.bind("<Alt-Left>", lambda _event: self.go_back())
        if IS_MAC:
            # ⌘[ is Back in Finder, Safari and every Mac app with history.
            self.bind("<Command-bracketleft>", lambda _event: self.go_back())
        for sequence in (f"<{MOD}-k>", f"<{MOD}-K>"):
            self.bind(sequence, self.open_page_finder)
            # Entry/Text use Ctrl+K to delete to the end of the line; open the
            # finder there too instead of silently erasing what was typed.
            # (On a Mac, ⌘K leaves Control-K's line delete alone.)
            for widget_class in ("Entry", "TEntry", "Text"):
                self.bind_class(widget_class, sequence, self.open_page_finder)
        self.bind("<Configure>", self.handle_window_configure, add="+")
        self.update_idletasks()
        self._taskbar_ready = self.ensure_taskbar_presence()
        self.tour = None
        # Map the window while it is still fully transparent, build and settle
        # the first page, then show the finished frame in one step (no fade).
        self.deiconify()
        self.show_view(self.start_view(), transition=False)
        self.settle_layout()
        self.reveal_window(self)
        self.after(120, lambda: setattr(self, "_taskbar_ready", self.ensure_taskbar_presence()))
        self._ui_ready = True

    def install_mac_menus(self):
        """Give the Mac the menu bar every Mac app has.

        Tk only shows menu shortcuts; it doesn't run them (the keys go to the
        bindings in __init__ and to Tk's own text bindings), so each shortcut
        listed here must also be bound. About, Settings… (⌘,) and Quit (⌘Q)
        are the system's own items in the app menu, hooked up through Tk's
        tk::mac commands. A menu named "window" becomes the system's Window
        menu, which brings Minimize (⌘M), Zoom and the window list with it.
        """
        try:
            self.createcommand("tkAboutDialog", lambda: self.tk.call("tk::mac::standardAboutPanel"))
            self.createcommand("tk::mac::ShowPreferences", lambda *_args: self.show_view("settings"))
            self.createcommand("tk::mac::Quit", self.destroy)
        except tk.TclError:
            pass

        def send(event_name):
            widget = self.focus_get()
            if widget is not None:
                widget.event_generate(event_name)

        menubar = tk.Menu(self)
        edit = tk.Menu(menubar, tearoff=False)
        edit.add_command(label="Undo", accelerator="Command-Z", command=lambda: send("<<Undo>>"))
        edit.add_command(label="Redo", accelerator="Shift-Command-Z", command=lambda: send("<<Redo>>"))
        edit.add_separator()
        edit.add_command(label="Cut", accelerator="Command-X", command=lambda: send("<<Cut>>"))
        edit.add_command(label="Copy", accelerator="Command-C", command=lambda: send("<<Copy>>"))
        edit.add_command(label="Paste", accelerator="Command-V", command=lambda: send("<<Paste>>"))
        edit.add_command(label="Select All", accelerator="Command-A", command=lambda: send("<<SelectAll>>"))
        menubar.add_cascade(label="Edit", menu=edit)

        view = tk.Menu(menubar, tearoff=False)
        view.add_command(label="Switch Light / Dark", command=self.toggle_theme)
        view.add_separator()
        view.add_command(label="Toggle Full Screen", accelerator="Control-Command-F", command=self.toggle_true_fullscreen)
        menubar.add_cascade(label="View", menu=view)

        go = tk.Menu(menubar, tearoff=False)
        go.add_command(label="Back", accelerator="Command-[", command=self.go_back)
        go.add_command(label="Go to Page\u2026", accelerator="Command-K", command=self.open_page_finder)
        go.add_separator()
        for key, label in (("dashboard", "Dashboard"), ("review", "Review"), ("capture", "New Study Set"), ("library", "Library"), ("stats", "Stats")):
            go.add_command(label=label, command=lambda key=key: self.show_view(key))
        menubar.add_cascade(label="Go", menu=go)

        menubar.add_cascade(label="Window", menu=tk.Menu(menubar, name="window", tearoff=False))

        help_menu = tk.Menu(menubar, name="help", tearoff=False)
        help_menu.add_command(label="Take the Guided Tour", command=self.start_tour)
        help_menu.add_command(label="Send Feedback\u2026", command=lambda: self.show_view("feedback"))
        menubar.add_cascade(label="Help", menu=help_menu)
        self.configure(menu=menubar)

    def capture_normal_geometry(self):
        if not self.is_fullscreen and not self.is_focus_window:
            self.normal_geometry = self.geometry()

    def toggle_true_fullscreen(self):
        if self.window_transition_active:
            return
        target = not self.is_fullscreen
        if target and not self.is_focus_window:
            self.capture_normal_geometry()
        # Going fullscreen is only a resize; the shell reflows in place, so
        # there is nothing to hide behind a blank cover.
        self.window_transition_active = True
        self.after_idle(lambda: self.apply_true_fullscreen(target))

    def apply_true_fullscreen(self, target):
        # Tk refuses the -fullscreen attribute on an override-redirect
        # (borderless) window, so there a screen-sized borderless window
        # is the fullscreen; it already covers the taskbar.
        borderless = bool(self.overrideredirect())
        screen = (self.winfo_screenwidth(), self.winfo_screenheight())

        def change():
            if target:
                self.is_focus_window = False
                self.is_fullscreen = True
                if borderless:
                    self.geometry(f"{screen[0]}x{screen[1]}+0+0")
                else:
                    self.attributes("-fullscreen", True)
            else:
                if not borderless:
                    self.attributes("-fullscreen", False)
                self.is_fullscreen = False
                if self.normal_geometry:
                    self.geometry(self.normal_geometry)

        size = screen if target else self.geometry_size(self.normal_geometry)
        self.restoring_borderless = True
        try:
            self.run_window_change(change, size)
        except tk.TclError as exc:
            self.is_fullscreen = False
            self.dialog_alert("Fullscreen unavailable", str(exc), "error")
        finally:
            self.restoring_borderless = False
            self.window_transition_active = False

    def toggle_focus_window(self):
        if self.window_transition_active:
            return
        self.window_transition_active = True
        self.after_idle(self.apply_focus_window)

    def apply_focus_window(self):
        entering = not self.is_focus_window
        if entering and not self.is_fullscreen:
            self.capture_normal_geometry()
        screen = (self.winfo_screenwidth(), self.winfo_screenheight())

        def change():
            if self.is_fullscreen:
                if not self.overrideredirect():
                    self.attributes("-fullscreen", False)
                self.is_fullscreen = False
            if entering:
                self.geometry(f"{screen[0]}x{screen[1]}+0+0")
                self.is_focus_window = True
            else:
                if self.normal_geometry:
                    self.geometry(self.normal_geometry)
                self.is_focus_window = False
                self.enable_borderless_chrome()

        size = screen if entering else self.geometry_size(self.normal_geometry)
        try:
            self.run_window_change(change, size)
        except tk.TclError:
            pass
        finally:
            self.window_transition_active = False

    @staticmethod
    def geometry_size(geometry):
        match = re.match(r"(\d+)x(\d+)", geometry or "")
        return (int(match.group(1)), int(match.group(2))) if match else None

    def run_window_change(self, change, target_size=None):
        """Resize the window with every layout and paint pass hidden.

        A pixel-identical snapshot of the screen is shown on top, then the
        window is resized and all follow-up work (Configure events that
        rewrap text, page reflow, scroll regions, painting) is settled
        underneath; removing the snapshot swaps to the finished result in a
        single frame. Pausing paint alone can't do that, since Windows shows
        the resized window, new area still blank, before Tk paints it. If no
        snapshot is available, fall back to pausing paint with the shell laid
        out at the target size in advance.
        """
        cover = None
        if not self.use_native_window_chrome:
            cover = show_screen_cover(self.winfo_screenwidth(), self.winfo_screenheight())
        frozen = False if cover is not None else self.set_redraw_frozen(True)
        try:
            if target_size and cover is None:
                self.prelayout_shell(*target_size)
            change()
            self.update_window_controls()
            self.settle_layout()
        finally:
            if frozen:
                self.set_redraw_frozen(False)
            flush_pending_paint(self)
            if cover is not None:
                remove_screen_cover(cover)

    def smooth(self, rebuild):
        """Wrap an in-page rebuild so it swaps in finished, in one frame.

        Rebuilding part of a page (new buttons, a different number of rows,
        a taller or shorter section) paints each geometry pass as it happens,
        which reads as a flash and a jump. The wrapped function runs under the
        same pixel-identical snapshot used for page switches. While a page is
        first being built, or inside another hidden change, it just runs.
        """
        def run(*args, **kwargs):
            if getattr(self, "_building_view", False) or getattr(self, "_hidden_active", False):
                return rebuild(*args, **kwargs)
            try:
                viewable = bool(self.winfo_viewable())
            except tk.TclError:
                viewable = False
            if not viewable:
                return rebuild(*args, **kwargs)
            result = {}
            self.run_hidden_change(lambda: result.setdefault("value", rebuild(*args, **kwargs)))
            return result.get("value")

        return run

    def run_hidden_change(self, change, fallback=None):
        """Run a big in-window change with the calculation gap hidden.

        Same idea as run_window_change, without a resize: a pixel-identical
        snapshot of the screen (or, failing that, frozen painting) covers the
        window while the change is built and every layout pass settles, then
        the finished result replaces the snapshot in a single frame. Nothing
        half-built, unstyled, or blank is ever painted in between.

        When neither hiding method is available (macOS/native chrome, or the
        window is not visible yet), run `fallback` instead, which should use
        the older in-window canvas cover.
        """
        cover = None
        frozen = False
        try:
            viewable = bool(self.winfo_viewable())
        except tk.TclError:
            viewable = False
        if viewable and not self.use_native_window_chrome:
            # Only the app window changes here (no resize), so copy just it.
            cover = show_screen_cover(self.winfo_width(), self.winfo_height(), self.winfo_rootx(), self.winfo_rooty(), source=self)
            if cover is None:
                frozen = self.set_redraw_frozen(True)
        if cover is None and not frozen:
            (fallback or change)()
            return
        self._hidden_active = True
        try:
            change()
            self.settle_layout()
        finally:
            self._hidden_active = False
            if frozen:
                self.set_redraw_frozen(False)
            flush_pending_paint(self)
            if cover is not None:
                remove_screen_cover(cover)

    def prelayout_shell(self, width, height):
        """Lay the tab bar and main area out for a window size not applied yet."""
        chrome = getattr(self, "app_chrome", None)
        try:
            chrome_h = chrome.winfo_height() if chrome is not None and chrome.winfo_ismapped() else 0
            body_h = max(1, height - chrome_h)
            bar = self.tab_bar_height()
            self.rail.place_configure(width=width, height=bar, relwidth=0, relheight=0)
            self.main.place_configure(width=width, height=max(1, body_h - bar), relwidth=0, relheight=0)
        except (AttributeError, tk.TclError):
            return
        self.settle_layout(relayout_shell=False)

    def settle_layout(self, rounds=6, relayout_shell=True):
        # Configure-driven work (label rewrapping, scroll regions) runs from
        # window events, not idle tasks, so alternate both until nothing new
        # is queued.
        for _ in range(rounds):
            self.update_idletasks()
            if relayout_shell:
                self.layout_app_body()
            if not flush_pending_paint(self):
                break

    def set_redraw_frozen(self, frozen):
        """Suspend or resume painting of the whole window (Windows only).

        Growing the window exposes new area that Tk fills in over several
        geometry passes (window, shell, pages, scroll regions), and each pass
        was painted as it happened, which read as a flash. Freezing redraw
        while all of that settles lets the window repaint once, fully laid
        out. Tk's client window is frozen, not the outer wrapper: while the
        wrapper's redraw is off Windows reports it as hidden and Tk skips the
        pending resize entirely. Returns True if painting was changed.
        """
        if self.use_native_window_chrome:
            return False
        return set_window_redraw(self, not frozen)

    def finish_window_transition_cover(self, cover):
        # Compatibility helper for callers that want to end a window veil.
        self.destroy_transition_cover(cover)
        self.window_transition_active = False

    def update_window_controls(self):
        if hasattr(self, "chrome_fullscreen_button") and self.chrome_fullscreen_button.winfo_exists():
            symbol = "\u2750" if self.is_focus_window else "\u25a1"
            if hasattr(self.chrome_fullscreen_button, "set_symbol"):
                self.chrome_fullscreen_button.set_symbol(symbol)
            else:
                self.chrome_fullscreen_button.configure(text=symbol)
        if getattr(self, "app_chrome", None) is not None and self.app_chrome.winfo_exists():
            if not self.app_chrome.winfo_ismapped():
                self.app_chrome.pack(fill="x", before=self.app_body)
        if self.is_fullscreen or self.use_native_window_chrome:
            self.set_resize_grips_visible(False)
        else:
            self.set_resize_grips_visible(True)

    def raise_widget(self, widget):
        try:
            widget.tk.call("raise", widget._w)
        except (AttributeError, tk.TclError):
            pass

    def center_canvas_item(self, canvas, item, x, y):
        try:
            bbox = canvas.bbox(item)
        except tk.TclError:
            bbox = None
        if not bbox:
            return
        current_x = (bbox[0] + bbox[2]) / 2
        current_y = (bbox[1] + bbox[3]) / 2
        canvas.move(item, x - current_x, y - current_y)

    ICON_FONTS = ("Segoe MDL2 Assets", "Segoe Fluent Icons", "Segoe UI Symbol", "Segoe UI Emoji")

    def create_centered_canvas_text(self, canvas, x, y, text, **kwargs):
        item = canvas.create_text(x, y, text=text, **kwargs)
        self.center_canvas_item(canvas, item, x, y)
        font = kwargs.get("font")
        family = font[0] if isinstance(font, tuple) and font else ""
        if font and family not in self.ICON_FONTS:
            # The text box includes the font's leading above the capitals and
            # room for descenders below, so box-centred text looks low. Centre
            # on the letters instead: capitals and digits fill ~65% of the
            # ascent in Segoe UI and similar UI fonts.
            try:
                metrics = tkfont.Font(font=font).metrics()
                ascent, descent = metrics["ascent"], metrics["descent"]
                canvas.move(item, 0, -round((ascent - descent - ascent * 0.649) / 2))
            except (tk.TclError, KeyError):
                pass
        return item

    def draw_antialiased_shape(self, canvas, width, height, fill, shape="round_rect", radius=None, inset=0):
        """Draw smoother custom UI shapes with Pillow or the built-in fallback."""
        modules = self.pillow_modules()
        if not modules:
            return self.draw_builtin_antialiased_shape(canvas, width, height, fill, shape, radius, inset)
        Image, ImageDraw, ImageTk = modules
        try:
            width = int(width)
            height = int(height)
            inset = int(inset)
            radius = int(radius if radius is not None else height / 2)
            key = (width, height, fill, shape, radius, inset)
            photo = self.shape_photo_cache.get(key)
            if photo is None:
                scale = 4 if max(width, height) <= 180 else 3
                image = Image.new("RGBA", (width * scale, height * scale), (0, 0, 0, 0))
                draw = ImageDraw.Draw(image)
                bounds = (
                    inset * scale,
                    inset * scale,
                    (width - inset) * scale - 1,
                    (height - inset) * scale - 1,
                )
                if shape == "oval":
                    draw.ellipse(bounds, fill=fill)
                else:
                    draw.rounded_rectangle(bounds, radius=radius * scale, fill=fill)
                resampling = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
                image = image.resize((width, height), resampling)
                photo = ImageTk.PhotoImage(image)
                if len(self.shape_photo_cache) > 48:
                    self.shape_photo_cache.clear()
                self.shape_photo_cache[key] = photo
            canvas.create_image(0, 0, image=photo, anchor="nw")
            canvas._memorypal_shape = photo
            return True
        except Exception:
            return False

    def draw_builtin_antialiased_shape(self, canvas, width, height, fill, shape="round_rect", radius=None, inset=0):
        """Draw small antialiased shapes without optional Pillow installed."""
        try:
            width = int(width)
            height = int(height)
            inset = int(inset)
            radius = int(radius if radius is not None else height / 2)
            key = ("builtin", width, height, fill, shape, radius, inset)
            photo = self.shape_photo_cache.get(key)
            if photo is None:
                photo = self.make_shape_photo(width, height, fill, shape, radius, inset)
                if photo is None:
                    return False
                if len(self.shape_photo_cache) > 64:
                    self.shape_photo_cache.clear()
                self.shape_photo_cache[key] = photo
            canvas.create_image(0, 0, image=photo, anchor="nw")
            canvas._memorypal_shape = photo
            return True
        except Exception:
            return False

    def make_shape_photo(self, width, height, fill, shape="round_rect", radius=None, inset=0):
        rgb = self.hex_to_rgb(fill)
        if rgb is None or width < 1 or height < 1:
            return None
        radius = max(0, min(float(radius or 0), width / 2, height / 2))
        inset = max(0, float(inset))
        scale = 4 if max(width, height) <= 90 else 3
        samples = scale * scale
        x0 = inset
        y0 = inset
        x1 = max(x0, width - inset)
        y1 = max(y0, height - inset)

        def inside(px, py):
            if shape == "oval":
                cx = (x0 + x1) / 2
                cy = (y0 + y1) / 2
                rx = max(0.5, (x1 - x0) / 2)
                ry = max(0.5, (y1 - y0) / 2)
                return ((px - cx) / rx) ** 2 + ((py - cy) / ry) ** 2 <= 1
            if not (x0 <= px <= x1 and y0 <= py <= y1):
                return False
            corner_x = min(max(px, x0 + radius), x1 - radius)
            corner_y = min(max(py, y0 + radius), y1 - radius)
            return (px - corner_x) ** 2 + (py - corner_y) ** 2 <= radius ** 2

        pixels = bytearray()
        full = (*rgb, 255)
        empty = (*rgb, 0)
        for y in range(height):
            for x in range(width):
                # Shapes are convex: a pixel whose four corners agree is fully
                # in or out, so only edge pixels need supersampling.
                corners = inside(x, y) + inside(x + 1, y) + inside(x, y + 1) + inside(x + 1, y + 1)
                if corners == 4:
                    pixels.extend(full)
                    continue
                if corners == 0 and not inside(x + 0.5, y + 0.5):
                    pixels.extend(empty)
                    continue
                covered = 0
                for sy in range(scale):
                    py = y + (sy + 0.5) / scale
                    for sx in range(scale):
                        px = x + (sx + 0.5) / scale
                        if inside(px, py):
                            covered += 1
                alpha = int(round(255 * covered / samples))
                pixels.extend((*rgb, alpha))
        data = self.png_rgba(width, height, bytes(pixels))
        encoded = base64.b64encode(data).decode("ascii")
        return tk.PhotoImage(data=encoded, format="png")

    def draw_antialiased_ring(self, canvas, size, track_color, progress_color, pct, stroke):
        try:
            size = int(size)
            stroke = int(stroke)
            pct = clamp(float(pct), 0, 1)
            key = ("ring", size, track_color, progress_color, round(pct, 4), stroke)
            photo = self.shape_photo_cache.get(key)
            if photo is None:
                photo = self.make_ring_photo(size, track_color, progress_color, pct, stroke)
                if photo is None:
                    return False
                if len(self.shape_photo_cache) > 72:
                    self.shape_photo_cache.clear()
                self.shape_photo_cache[key] = photo
            canvas.create_image(0, 0, image=photo, anchor="nw")
            canvas._memorypal_ring = photo
            return True
        except Exception:
            return False

    def make_ring_photo(self, size, track_color, progress_color, pct, stroke):
        track_rgb = self.hex_to_rgb(track_color)
        progress_rgb = self.hex_to_rgb(progress_color)
        if track_rgb is None or progress_rgb is None or size < 4 or stroke < 1:
            return None
        scale = 4 if size <= 180 else 3
        samples = scale * scale
        center = size / 2
        radius = max(1, (size - stroke - 2) / 2)
        edge = 0.85
        progress_sweep = pct * 360
        pixels = bytearray()
        clear = (*track_rgb, 0)
        half_stroke = stroke / 2

        for y in range(size):
            for x in range(size):
                dx = x + 0.5 - center
                dy = y + 0.5 - center
                band = abs(math.hypot(dx, dy) - radius) - half_stroke
                if band > edge + 0.75:
                    # Well outside the ring: fully transparent, skip sampling.
                    pixels.extend(clear)
                    continue
                if band < -0.75:
                    # Solidly inside the stroke: only the sweep edge needs care.
                    distance = max(1.0, math.hypot(dx, dy))
                    angle = (math.degrees(math.atan2(dx, -dy)) + 360) % 360
                    margin = math.degrees(1.0 / distance)
                    near_edge = progress_sweep > 0 and (angle < margin or angle > 360 - margin or abs(angle - progress_sweep) < margin)
                    if not near_edge:
                        if progress_sweep > 0 and angle <= progress_sweep:
                            pixels.extend((*progress_rgb, 255))
                        else:
                            pixels.extend((*track_rgb, 255))
                        continue
                track_hits = 0.0
                progress_hits = 0.0
                for sy in range(scale):
                    py = y + (sy + 0.5) / scale
                    for sx in range(scale):
                        px = x + (sx + 0.5) / scale
                        dx = px - center
                        dy = py - center
                        distance = math.hypot(dx, dy)
                        radial = max(0.0, min(1.0, (stroke / 2 + edge - abs(distance - radius)) / edge))
                        if radial <= 0:
                            continue
                        track_hits += radial
                        if progress_sweep > 0:
                            angle = (math.degrees(math.atan2(dx, -dy)) + 360) % 360
                            if angle <= progress_sweep:
                                progress_hits += radial
                track_alpha = int(round(255 * track_hits / samples))
                progress_alpha = int(round(255 * progress_hits / samples))
                if progress_alpha:
                    pixels.extend((*progress_rgb, progress_alpha))
                else:
                    pixels.extend((*track_rgb, track_alpha))
        data = self.png_rgba(size, size, bytes(pixels))
        encoded = base64.b64encode(data).decode("ascii")
        return tk.PhotoImage(data=encoded, format="png")

    # Line icons for the rail and hub tiles, drawn on a 24-unit grid like SF
    # Symbols: one stroke weight, round ends, no fills except small knobs.
    # Each shape is (kind, *numbers); strokes are measured from the centre line.
    LINE_ICONS = {
        "dashboard": [("circle", 12, 12, 4.5)] + [
            ("seg", 12 + 7.5 * dx, 12 + 7.5 * dy, 12 + 9 * dx, 12 + 9 * dy)
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (0.7071, 0.7071), (-0.7071, 0.7071), (0.7071, -0.7071), (-0.7071, -0.7071))
        ],
        "study": [
            ("box", 3.5, 8, 16.5, 20.5, 2),
            ("seg", 7.5, 4, 18.5, 4), ("seg", 18.5, 4, 20.5, 6), ("seg", 20.5, 6, 20.5, 16.5),
        ],
        "create": [("circle", 12, 12, 9), ("seg", 12, 8, 12, 16), ("seg", 8, 12, 16, 12)],
        "practice": [
            ("seg", 8.5, 12, 15.5, 12), ("box", 5, 5.5, 8.5, 18.5, 1.4), ("box", 15.5, 5.5, 19, 18.5, 1.4),
            ("seg", 2.5, 9.5, 2.5, 14.5), ("seg", 21.5, 9.5, 21.5, 14.5),
        ],
        "stats": [("box", 3.5, 13, 8, 20.5, 1.5), ("box", 9.75, 8, 14.25, 20.5, 1.5), ("box", 16, 3.5, 20.5, 20.5, 1.5)],
        "feedback": [("box", 3, 4, 21, 16, 3), ("seg", 8, 16, 7, 20.5), ("seg", 7, 20.5, 12.5, 16)],
        "settings": [
            ("seg", 3.5, 8, 20.5, 8), ("seg", 3.5, 16, 20.5, 16), ("dot", 9, 8, 2.6), ("dot", 15, 16, 2.6),
        ],
        # Pages inside the hubs.
        "review": [("box", 3.5, 5, 20.5, 20, 2.5), ("seg", 3.5, 9.5, 20.5, 9.5), ("seg", 8, 3, 8, 6.5), ("seg", 16, 3, 16, 6.5)],
        "focus": [("circle", 12, 12, 8.5), ("circle", 12, 12, 4.5), ("dot", 12, 12, 1.4)],
        "quiz": [("circle", 12, 12, 9), ("seg", 9.5, 9.5, 9.6, 9.2), ("seg", 9.6, 9.2, 12, 7.6), ("seg", 12, 7.6, 14.4, 9.2), ("seg", 14.4, 9.2, 12.2, 12.4), ("seg", 12.2, 12.4, 12.2, 13.4), ("dot", 12.2, 16.6, 1.2)],
        "shuffle": [("seg", 3, 7, 21, 7), ("seg", 21, 7, 17.5, 3.5), ("seg", 21, 17, 3, 17), ("seg", 3, 17, 6.5, 20.5)],
        "testing": [("box", 4, 3, 20, 21, 2.5), ("seg", 8, 12.5, 10.8, 15.3), ("seg", 10.8, 15.3, 16, 9)],
        "capture": [("box", 3.5, 3.5, 20.5, 20.5, 3), ("seg", 12, 8, 12, 16), ("seg", 8, 12, 16, 12)],
        "decks": [("box", 3, 9, 21, 20.5, 2), ("seg", 5.5, 5.5, 18.5, 5.5), ("seg", 8, 2.5, 16, 2.5)],
        "library": [("seg", 5.5, 4, 5.5, 20), ("seg", 10, 4, 10, 20), ("seg", 14, 4.5, 18.5, 19.5)],
        "cuelab": [("seg", 12, 3.5, 13.6, 10.4), ("seg", 13.6, 10.4, 20.5, 12), ("seg", 20.5, 12, 13.6, 13.6), ("seg", 13.6, 13.6, 12, 20.5), ("seg", 12, 20.5, 10.4, 13.6), ("seg", 10.4, 13.6, 3.5, 12), ("seg", 3.5, 12, 10.4, 10.4), ("seg", 10.4, 10.4, 12, 3.5)],
        "training": [("seg", 8.5, 12, 15.5, 12), ("box", 5, 5.5, 8.5, 18.5, 1.4), ("box", 15.5, 5.5, 19, 18.5, 1.4), ("seg", 2.5, 9.5, 2.5, 14.5), ("seg", 21.5, 9.5, 21.5, 14.5)],
        "elder": [("arc", 8.2, 9.5, 4.2, 135, 350), ("arc", 15.8, 9.5, 4.2, 190, 405), ("seg", 5.23, 12.47, 12, 19.5), ("seg", 18.77, 12.47, 12, 19.5)],
        "tools": [("box", 2, 7, 13.5, 17, 5), ("box", 10.5, 7, 22, 17, 5)],
        "games": [("box", 2.5, 7, 21.5, 18, 4.5), ("seg", 7.5, 10, 7.5, 15), ("seg", 5, 12.5, 10, 12.5), ("dot", 15.5, 11, 1.3), ("dot", 18, 14, 1.3)],
        # Header buttons. Drawn here rather than taken from an icon font so they
        # are the same size on every system (the font fallbacks off Windows
        # were much smaller than the Segoe glyphs).
        "search": [("circle", 10.5, 10.5, 6.5), ("seg", 15.3, 15.3, 20.5, 20.5)],
        # Window controls, the fullscreen corners and the tick in check boxes:
        # drawn antialiased like the other icons (Tk's canvas lines are jagged
        # on Windows).
        "close": [("seg", 6, 6, 18, 18), ("seg", 18, 6, 6, 18)],
        "minimize": [("seg", 5, 12, 19, 12)],
        "maximize": [("seg", 5.5, 5.5, 18.5, 5.5), ("seg", 18.5, 5.5, 18.5, 18.5), ("seg", 18.5, 18.5, 5.5, 18.5), ("seg", 5.5, 18.5, 5.5, 5.5)],
        "fullscreen": [
            seg for sx, sy, dx, dy in ((3.5, 3.5, 1, 1), (20.5, 3.5, -1, 1), (3.5, 20.5, 1, -1), (20.5, 20.5, -1, -1))
            for seg in (("seg", sx, sy, sx + 5 * dx, sy), ("seg", sx, sy, sx, sy + 5 * dy))
        ],
        "check": [("seg", 5, 12.5, 9.8, 17.3), ("seg", 9.8, 17.3, 19, 7)],
        "back": [("seg", 19.5, 12, 4.5, 12), ("seg", 4.5, 12, 10.5, 6), ("seg", 4.5, 12, 10.5, 18)],
        "help": [("circle", 12, 12, 9), ("arc", 12, 9.6, 2.6, 180, 405), ("seg", 13.84, 11.44, 12, 13.2), ("seg", 12, 13.2, 12, 14), ("dot", 12, 16.9, 1.2)],
        "moon": [("arc", 12, 12, 8.5, 7.07, 262.93), ("arc", 16.5, 7.5, 6.8, 54.64, 215.36)],
        "backup": [("seg", 12, 3.5, 12, 14.5), ("seg", 7.5, 10, 12, 14.5), ("seg", 16.5, 10, 12, 14.5), ("seg", 4, 15, 4, 20), ("seg", 4, 20, 20, 20), ("seg", 20, 20, 20, 15)],
        # Header status chips.
        "flame": [
            ("arc", 12, 15, 6, 0, 180), ("seg", 6, 15, 7.4, 10), ("seg", 7.4, 10, 9.6, 12), ("seg", 9.6, 12, 12, 3), ("seg", 18, 15, 16, 9.5), ("seg", 16, 9.5, 12, 3),
            ("arc", 12, 16.5, 2.4, 0, 180), ("seg", 9.6, 16.5, 12, 12.5), ("seg", 14.4, 16.5, 12, 12.5),
        ],
        "cloud": [("arc", 7, 14.5, 4, 90, 262.8), ("arc", 12, 10.5, 5.5, 179.7, 360), ("arc", 17.5, 14.5, 4, 270, 450), ("seg", 7, 18.5, 17.5, 18.5)],
        "syncing": [("arc", 12, 12, 7.5, 320, 625), ("seg", 13.9, 4.74, 10.6, 2), ("seg", 13.9, 4.74, 10.8, 7.8)],
        "warning": [("seg", 12, 3.5, 21, 19.5), ("seg", 21, 19.5, 3, 19.5), ("seg", 3, 19.5, 12, 3.5), ("seg", 12, 9.5, 12, 13.5), ("dot", 12, 16.5, 1.2)],
        # Read aloud and talk-back study.
        "speaker": [
            ("seg", 3.5, 9.5, 7.5, 9.5), ("seg", 7.5, 9.5, 12, 5), ("seg", 12, 5, 12, 19), ("seg", 12, 19, 7.5, 14.5),
            ("seg", 7.5, 14.5, 3.5, 14.5), ("seg", 3.5, 14.5, 3.5, 9.5),
            ("arc", 12, 12, 4.5, 315, 405), ("arc", 12, 12, 8.5, 310, 410),
        ],
        "stop": [("box", 6, 6, 18, 18, 2.5)],
        "pause": [("seg", 9, 6, 9, 18), ("seg", 15, 6, 15, 18)],
        "play": [("seg", 8, 5, 19, 12), ("seg", 19, 12, 8, 19), ("seg", 8, 19, 8, 5)],
        "skip": [("seg", 5, 5, 15, 12), ("seg", 15, 12, 5, 19), ("seg", 5, 19, 5, 5), ("seg", 19, 5, 19, 19)],
        "mic": [("box", 9, 3, 15, 14, 3), ("arc", 12, 11, 6.5, 0, 180), ("seg", 12, 17.5, 12, 21), ("seg", 8.5, 21, 15.5, 21)],
        "keyboard": [("box", 2.5, 6, 21.5, 18, 2.5), ("dot", 7, 10, 1), ("dot", 10.33, 10, 1), ("dot", 13.66, 10, 1), ("dot", 17, 10, 1), ("seg", 7.5, 14, 16.5, 14)],
    }
    LINE_ICONS["sun"] = LINE_ICONS["dashboard"]
    LINE_ICONS["repeat"] = LINE_ICONS["syncing"]
    LINE_ICONS["talkback"] = LINE_ICONS["mic"]

    # Icons drawn small get a slightly heavier stroke so they don't look faint.
    LINE_ICON_WEIGHT = {"check": 1.35}

    def icon_coverage(self, name, size):
        """Antialiased coverage (0-255 per pixel) of a line icon at this size."""
        cache = self.__dict__.setdefault("_icon_coverage_cache", {})
        key = (name, size)
        if key in cache:
            return cache[key]
        shapes = self.LINE_ICONS.get(name)
        if not shapes:
            return None
        unit = size / 24
        half = 0.9 * self.LINE_ICON_WEIGHT.get(name, 1)  # half the stroke, in grid units

        def distance(shape, x, y):
            kind = shape[0]
            if kind == "seg":
                x1, y1, x2, y2 = shape[1:]
                dx, dy = x2 - x1, y2 - y1
                length = dx * dx + dy * dy
                t = 0 if not length else max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / length))
                return math.hypot(x - x1 - t * dx, y - y1 - t * dy) - half
            if kind == "circle":
                cx, cy, r = shape[1:]
                return abs(math.hypot(x - cx, y - cy) - r) - half
            if kind == "arc":
                # Part of a circle from angle a0 to a1 in degrees, clockwise
                # on screen (y points down).
                cx, cy, r, a0, a1 = shape[1:]
                angle = math.degrees(math.atan2(y - cy, x - cx)) % 360
                if (angle - a0) % 360 <= (a1 - a0):
                    return abs(math.hypot(x - cx, y - cy) - r) - half
                ends = [(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))) for a in (a0, a1)]
                return min(math.hypot(x - ex, y - ey) for ex, ey in ends) - half
            if kind == "dot":
                cx, cy, r = shape[1:]
                return math.hypot(x - cx, y - cy) - r
            x0, y0, x1, y1, r = shape[1:]
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            qx = abs(x - cx) - ((x1 - x0) / 2 - r)
            qy = abs(y - cy) - ((y1 - y0) / 2 - r)
            outside = math.hypot(max(qx, 0), max(qy, 0)) + min(max(qx, qy), 0) - r
            return abs(outside) - half

        samples = 4
        coverage = bytearray(size * size)
        for py in range(size):
            for px in range(size):
                hits = 0
                for sy in range(samples):
                    gy = (py + (sy + 0.5) / samples) / unit
                    for sx in range(samples):
                        gx = (px + (sx + 0.5) / samples) / unit
                        if any(distance(shape, gx, gy) <= 0 for shape in shapes):
                            hits += 1
                coverage[py * size + px] = round(255 * hits / (samples * samples))
        cache[key] = coverage
        return coverage

    def line_icon(self, name, size, color):
        """A cached PhotoImage of a line icon in one colour, or None."""
        cache = self.__dict__.setdefault("_icon_photo_cache", {})
        key = (name, size, color)
        if key in cache:
            return cache[key]
        rgb = self.hex_to_rgb(color)
        coverage = self.icon_coverage(name, size) if rgb else None
        if coverage is None:
            return None
        pixels = bytearray()
        for alpha in coverage:
            pixels.extend((*rgb, alpha))
        photo = tk.PhotoImage(master=self, data=base64.b64encode(self.png_rgba(size, size, bytes(pixels))).decode("ascii"), format="png")
        cache[key] = photo
        return photo

    def hex_to_rgb(self, hex_color):
        raw = str(hex_color).lstrip("#")
        if len(raw) != 6:
            return None
        try:
            return tuple(int(raw[index:index + 2], 16) for index in (0, 2, 4))
        except ValueError:
            return None

    def png_rgba(self, width, height, rgba):
        def chunk(kind, data):
            payload = kind + data
            checksum = zlib.crc32(payload) & 0xFFFFFFFF
            return struct.pack(">I", len(data)) + payload + struct.pack(">I", checksum)

        rows = bytearray()
        stride = width * 4
        for y in range(height):
            rows.append(0)
            start = y * stride
            rows.extend(rgba[start:start + stride])
        header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
        return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(bytes(rows), 9)) + chunk(b"IEND", b"")

    def pillow_modules(self):
        if self._pillow_modules is not None:
            return self._pillow_modules
        if self._pillow_unavailable:
            return None
        try:
            from PIL import Image, ImageDraw, ImageTk
        except ImportError:
            self._pillow_unavailable = True
            return None
        self._pillow_modules = (Image, ImageDraw, ImageTk)
        return self._pillow_modules

    def draw_memorypal_logo(self, canvas, size):
        """Render the generated MemoryPal icon into the navigation rail."""
        try:
            size = int(size)
            bg = canvas.cget("bg") or COLORS["rail"]
            source_png = self.logo_source_path
            source_mtime = source_png.stat().st_mtime_ns if source_png and source_png.exists() else None
            key = (size, bg, str(source_png) if source_png else "", source_mtime)
            photo = self.logo_photo_cache.get(key)
            if photo is None:
                if source_png and source_png.exists():
                    modules = self.pillow_modules()
                    if modules:
                        Image, _ImageDraw, ImageTk = modules
                        with Image.open(source_png) as source_image:
                            image = source_image.convert("RGBA")
                        if image.size != (size, size):
                            resampling = getattr(Image, "Resampling", Image)
                            lanczos = getattr(resampling, "LANCZOS", getattr(Image, "LANCZOS", 1))
                            image = image.resize((size, size), lanczos)
                        photo = ImageTk.PhotoImage(image)
                    else:
                        pixels = icon_pixels(size)
                        bg_rgb = [value // 256 for value in self.winfo_rgb(bg)]
                        rows = []
                        for row in pixels:
                            colors = []
                            for red, green, blue, alpha in row:
                                if alpha < 255:
                                    ratio = alpha / 255
                                    red = round(red * ratio + bg_rgb[0] * (1 - ratio))
                                    green = round(green * ratio + bg_rgb[1] * (1 - ratio))
                                    blue = round(blue * ratio + bg_rgb[2] * (1 - ratio))
                                colors.append(f"#{red:02x}{green:02x}{blue:02x}")
                            rows.append("{" + " ".join(colors) + "}")
                        photo = tk.PhotoImage(width=size, height=size)
                        photo.put(" ".join(rows))
                else:
                    pixels = icon_pixels(size)
                    bg_rgb = [value // 256 for value in self.winfo_rgb(bg)]
                    rows = []
                    for row in pixels:
                        colors = []
                        for red, green, blue, alpha in row:
                            if alpha < 255:
                                ratio = alpha / 255
                                red = round(red * ratio + bg_rgb[0] * (1 - ratio))
                                green = round(green * ratio + bg_rgb[1] * (1 - ratio))
                                blue = round(blue * ratio + bg_rgb[2] * (1 - ratio))
                            colors.append(f"#{red:02x}{green:02x}{blue:02x}")
                        rows.append("{" + " ".join(colors) + "}")
                    photo = tk.PhotoImage(width=size, height=size)
                    photo.put(" ".join(rows))
                if len(self.logo_photo_cache) > 12:
                    self.logo_photo_cache.clear()
                self.logo_photo_cache[key] = photo
            canvas.create_image(size // 2, size // 2, image=photo, anchor="center")
            canvas._memorypal_logo = photo
            return True
        except Exception:
            return False

    def apply_app_icon(self, window=None):
        target = window or self
        if self.app_icon_path is None:
            source_icon = bundled_resource_path("assets", "memorypal.ico")
            if source_icon and source_icon.exists():
                self.app_icon_path = source_icon
            for folder in (app_paths.DATA_DIR, Path(os.environ.get("TEMP", "."))):
                if self.app_icon_path:
                    break
                try:
                    self.app_icon_path = ensure_icon_file(folder / "memorypal.ico")
                    break
                except OSError:
                    self.app_icon_path = None
        if not self.app_icon_path:
            return
        try:
            if target is self:
                target.iconbitmap(default=str(self.app_icon_path))
            else:
                target.iconbitmap(str(self.app_icon_path))
        except tk.TclError:
            pass

    def exit_fullscreen_or_focus(self):
        if self.is_fullscreen:
            self.toggle_true_fullscreen()
        elif self.is_focus_window:
            self.toggle_focus_window()

    def exit_fullscreen(self):
        self.exit_fullscreen_or_focus()

    def restore_window_chrome(self, _event=None):
        if self.use_native_window_chrome:
            return
        if _event is not None and _event.widget is not self:
            return
        if self.state() != "normal" or self.is_fullscreen or self.restoring_borderless or self._chrome_update_active:
            return
        try:
            already_borderless = bool(self.overrideredirect())
        except tk.TclError:
            already_borderless = False
        if already_borderless and self._taskbar_ready:
            return
        if self.state() == "normal":
            self.enable_borderless_chrome()

    def enable_borderless_chrome(self):
        if self.use_native_window_chrome:
            self.restoring_borderless = False
            return
        if self.is_fullscreen:
            self.restoring_borderless = False
            return
        if self._chrome_update_active:
            return
        self._chrome_update_active = True
        try:
            try:
                already_borderless = bool(self.overrideredirect())
            except tk.TclError:
                already_borderless = False
            if not already_borderless:
                self.overrideredirect(True)
                self.update_idletasks()
                self._taskbar_ready = False
            if not self._taskbar_ready:
                self._taskbar_ready = self.ensure_taskbar_presence()
        except tk.TclError:
            pass
        finally:
            self._chrome_update_active = False
            self.restoring_borderless = False

    def restore_from_minimize(self, _event=None):
        if self.use_native_window_chrome:
            return
        if not self.is_fullscreen:
            self.enable_borderless_chrome()

    def minimize_app(self):
        if self.use_native_window_chrome:
            try:
                self.iconify()
            except tk.TclError:
                pass
            return
        try:
            self.restoring_borderless = True
            self.overrideredirect(False)
            self.update_idletasks()
            self.iconify()
            self.after(120, self.restore_from_minimize)
        except tk.TclError:
            self.restoring_borderless = False

    def ensure_taskbar_presence(self):
        if not sys.platform.startswith("win"):
            return True
        try:
            import ctypes

            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            if not hwnd:
                hwnd = self.winfo_id()
            gwl_exstyle = -20
            ws_ex_appwindow = 0x00040000
            ws_ex_toolwindow = 0x00000080
            try:
                get_style = ctypes.windll.user32.GetWindowLongPtrW
                set_style = ctypes.windll.user32.SetWindowLongPtrW
            except AttributeError:
                get_style = ctypes.windll.user32.GetWindowLongW
                set_style = ctypes.windll.user32.SetWindowLongW
            style = get_style(hwnd, gwl_exstyle)
            style = (style & ~ws_ex_toolwindow) | ws_ex_appwindow
            set_style(hwnd, gwl_exstyle, style)
            # Tell Windows to re-read the window style without moving/resizing.
            swp_flags = 0x0001 | 0x0002 | 0x0010 | 0x0020
            ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, swp_flags)
            return True
        except (AttributeError, OSError, tk.TclError):
            return False

    def close_window(self, window=None):
        target = window or self
        try:
            target.destroy()
        except tk.TclError:
            pass

    def start_drag(self, event, window=None):
        window = window or self
        if window is self and self.is_fullscreen:
            return
        self.drag_start = (event.x_root, event.y_root, window.winfo_x(), window.winfo_y(), window)

    def drag_window(self, event):
        if not self.drag_start:
            return
        start_x, start_y, window_x, window_y, window = self.drag_start
        window.geometry(f"+{window_x + event.x_root - start_x}+{window_y + event.y_root - start_y}")

    def stop_drag(self, _event=None):
        self.drag_start = None

    def start_resize(self, event, mode="se"):
        self.capture_normal_geometry()
        self.resize_start = (event.x_root, event.y_root, self.winfo_width(), self.winfo_height(), self.winfo_rootx(), self.winfo_rooty(), mode)
        self.pending_resize_geometry = None

    def resize_window(self, event):
        if not self.resize_start or self.is_fullscreen:
            return
        start_x, start_y, start_width, start_height, window_x, window_y, mode = self.resize_start
        min_width, min_height = self.minsize()
        dx = event.x_root - start_x
        dy = event.y_root - start_y
        width = max(min_width, start_width + (dx if "e" in mode else 0))
        height = max(min_height, start_height + (dy if "s" in mode else 0))
        self.pending_resize_geometry = f"{width}x{height}+{window_x}+{window_y}"
        self.show_resize_outline(window_x, window_y, width, height)

    def show_resize_outline(self, x, y, width, height):
        """Preview the new size as an outline, like Windows does while dragging.

        The outline is four thin, solid, always-on-top bars, one per edge. The
        real window is resized once, on release. Moving small solid windows
        is cheap and never shows a half-drawn edge; an earlier version used one
        big see-through window, which had to be recomposited on every mouse
        move and made the moving edge blink.
        """
        bars = getattr(self, "resize_outline", None)
        if bars is None or not all(bar.winfo_exists() for bar in bars):
            self.hide_resize_outline()
            thickness = max(2, self.px(3)) + 2  # accent line plus a dark 1px rim each side
            bars = []
            for side in ("top", "bottom", "left", "right"):
                bar = tk.Toplevel(self)
                bar.withdraw()
                bar.overrideredirect(True)
                bar.configure(bg="#0b1220")
                try:
                    bar.attributes("-topmost", True)
                except tk.TclError:
                    pass
                # A dark rim around a bright accent line reads on light and
                # dark backgrounds alike. The side bars fit between the top
                # and bottom bars, so their accent runs straight into them.
                accent = COLORS["primary"]
                if side in ("top", "bottom"):
                    tk.Frame(bar, bg=accent).place(x=1, y=1, relwidth=1, relheight=1, width=-2, height=-2)
                    # Open the inner rim where a side bar joins, so the corner is one clean L.
                    joint_y = thickness - 1 if side == "top" else 0
                    tk.Frame(bar, bg=accent).place(x=1, y=joint_y, width=thickness - 2, height=1)
                    tk.Frame(bar, bg=accent).place(relx=1, x=-(thickness - 1), y=joint_y, width=thickness - 2, height=1)
                else:
                    tk.Frame(bar, bg=accent).place(x=1, y=0, relwidth=1, relheight=1, width=-2)
                bar.side = side
                bars.append(bar)
            self.resize_outline = bars
            self.resize_outline_thickness = thickness
            self.place_resize_bars(bars, x, y, width, height)
            for bar in bars:
                bar.deiconify()
            return
        self.place_resize_bars(bars, x, y, width, height)

    def place_resize_bars(self, bars, x, y, width, height):
        t = self.resize_outline_thickness
        spots = {
            "top": (x, y, width, t),
            "bottom": (x, y + height - t, width, t),
            "left": (x, y + t, t, max(1, height - 2 * t)),
            "right": (x + width - t, y + t, t, max(1, height - 2 * t)),
        }
        # Move all four in one step so the edges never drift apart mid-drag.
        try:
            import ctypes

            user32 = ctypes.windll.user32
            user32.BeginDeferWindowPos.restype = ctypes.c_void_p
            user32.DeferWindowPos.restype = ctypes.c_void_p
            user32.DeferWindowPos.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint)
            user32.EndDeferWindowPos.argtypes = (ctypes.c_void_p,)
            handles = [self.window_handle(bar) for bar in bars]
            if all(handles) and all(bar.winfo_ismapped() for bar in bars):
                batch = user32.BeginDeferWindowPos(len(bars))
                for bar, hwnd in zip(bars, handles):
                    bx, by, bw, bh = spots[bar.side]
                    # SWP_NOZORDER | SWP_NOACTIVATE | SWP_NOOWNERZORDER
                    batch = user32.DeferWindowPos(batch, hwnd, None, bx, by, bw, bh, 0x0004 | 0x0010 | 0x0200) if batch else None
                if batch and user32.EndDeferWindowPos(batch):
                    return
        except (AttributeError, OSError):
            pass
        for bar in bars:
            bx, by, bw, bh = spots[bar.side]
            bar.geometry(f"{bw}x{bh}+{bx}+{by}")

    def hide_resize_outline(self):
        bars = getattr(self, "resize_outline", None)
        self.resize_outline = None
        for bar in bars or ():
            try:
                bar.destroy()
            except tk.TclError:
                pass

    def stop_resize(self, _event=None):
        geometry = self.pending_resize_geometry
        self.resize_start = None
        self.pending_resize_geometry = None
        if not geometry:
            self.hide_resize_outline()
            return
        size = geometry.split("+")[0]
        width, height = (int(value) for value in size.split("x"))
        position = geometry[len(size):]

        def apply():
            self.hide_resize_outline()
            self.geometry(f"{width}x{height}{position}")

        # Same single-frame swap as fullscreen: everything reflows under a
        # snapshot and the finished layout appears at once.
        try:
            self.run_window_change(apply, (width, height))
        except tk.TclError:
            self.hide_resize_outline()

    def ease_out_cubic(self, step, total_steps):
        progress = clamp(step / max(1, total_steps), 0, 1)
        return 1 - (1 - progress) ** 3

    def set_resize_grips_visible(self, visible=True):
        grips = getattr(self, "resize_grips", [])
        if not grips:
            return
        if not visible:
            for grip in grips:
                if grip.winfo_exists():
                    grip.place_forget()
            return
        placements = (
            {"relx": 1, "rely": 0, "anchor": "ne", "width": self.px(5), "relheight": 1},
            {"relx": 0, "rely": 1, "anchor": "sw", "relwidth": 1, "height": self.px(5)},
            {"relx": 1, "rely": 1, "anchor": "se", "width": self.px(18), "height": self.px(18)},
        )
        for grip, placement in zip(grips, placements):
            if grip.winfo_exists():
                grip.place(**placement)

    # The rail holds five destinations, like the phone's tabs. Every other
    # page lives inside one of them (and stays reachable through the page
    # finder and Back). Today and Progress are existing pages; Study, Create
    # and Practice are hub pages listing what they hold.
    HUBS = (
        ("dashboard", "Today", "Td"),
        ("study", "Study", "St"),
        ("create", "Create", "Cr"),
        ("practice", "Practice", "Pr"),
        ("stats", "Progress", "Pg"),
    )
    HUB_PAGES = {
        "dashboard": ("plan",),
        "study": ("review", "talkback", "focus", "quiz", "shuffle", "testing"),
        "create": ("capture", "decks", "library", "cuelab"),
        "practice": ("training", "elder", "tools", "games"),
        "stats": (),
    }

    def rail_items(self):
        return list(self.HUBS)

    def hub_for(self, view):
        """The tab a page belongs to (pages outside the hubs map to themselves)."""
        for hub, pages in self.HUB_PAGES.items():
            if view == hub or view in pages:
                return hub
        return view

    def default_nav_items(self):
        return [
            ("dashboard", "Dashboard", "D"),
            ("training", "Memory Gym", "G"),
            ("elder", "Everyday Memory", "Em"),
            ("decks", "Decks", "De"),
            ("plan", "Study Plan", "P"),
            ("focus", "Focus", "F"),
            ("capture", "New Set", "C"),
            ("review", "Review", "R"),
            ("talkback", "Talk-back Study", "Tb"),
            ("testing", "Test Lab", "T"),
            ("quiz", "Quiz", "Q"),
            ("shuffle", "Repetition", "Rp"),
            ("tools", "Associations", "A"),
            ("cuelab", "Cue Lab", "Cu"),
            ("games", "Puzzles", "Pu"),
            ("library", "Library", "L"),
            ("stats", "Stats", "S"),
            ("feedback", "Feedback", "Fb"),
        ]

    def ordered_nav_items(self):
        defaults = self.default_nav_items()
        by_key = {key: item for key, *item in defaults}
        ordered = []
        for key in self.store.nav_order:
            if key in by_key:
                label, short = by_key.pop(key)
                ordered.append((key, label, short))
        ordered.extend((key, label, short) for key, label, short in defaults if key in by_key)
        return ordered

    def set_nav_order(self, keys):
        defaults = [key for key, _label, _short in self.default_nav_items()]
        valid = set(defaults)
        ordered = [key for key in keys if key in valid]
        for key in defaults:
            if key not in ordered:
                ordered.append(key)
        self.store.nav_order = ordered
        self.store.save()

    def destroy_transition_cover(self, cover):
        if not cover:
            return
        try:
            if cover.winfo_exists():
                cover.destroy()
        except tk.TclError:
            pass
        if getattr(self, "root_cover", None) is cover:
            self.root_cover = None

    def fade_frame_cover(self, cover, step=0):
        # Tk child widgets can't be partially transparent, so any animated
        # reveal (wipes, stipple "fades") shows as a sliding edge or popping
        # texture. Instead the cover hides the new page while it is built
        # and laid out, then is removed in a single step once geometry has
        # settled, which reads as a clean cut with no half-drawn frames.
        if not cover or not cover.winfo_exists():
            return
        try:
            self.update_idletasks()
        except tk.TclError:
            pass
        self.destroy_transition_cover(cover)

    def start_transition_cover(self, scope="content"):
        try:
            self.update_idletasks()
        except tk.TclError:
            return None
        parent = self if scope == "root" else getattr(self, scope, None)
        if parent is None or not parent.winfo_exists():
            return None
        color = COLORS["bg"]
        cover = tk.Canvas(parent, bg=color, highlightthickness=0, bd=0)
        cover.memorypal_scope = scope
        cover.memorypal_cover_color = color
        cover.place(relx=0, rely=0, relwidth=1, relheight=1)
        cover.bind("<Configure>", lambda _event, target=cover: self.paint_cover(target), add="+")
        self.paint_cover(cover)
        self.raise_widget(cover)
        cover.update_idletasks()
        return cover

    def rebuild_shell(self, view=None, refresh_styles=False, cover=None, use_cover=True):
        current = view or self.current_view
        if use_cover and cover is None:
            # Build the new shell under a snapshot of the old one, then swap
            # in one frame; the canvas cover is only the fallback.
            self.run_hidden_change(
                lambda: self.rebuild_shell(current, refresh_styles, use_cover=False),
                fallback=lambda: self._rebuild_shell_covered(current, refresh_styles),
            )
            return
        self._rebuild_shell_covered(current, refresh_styles, cover, use_cover)

    def _rebuild_shell_covered(self, current, refresh_styles=False, cover=None, use_cover=True):
        if use_cover:
            cover = cover or self.start_root_cover()
        for child in self.winfo_children():
            if child is cover:
                continue
            child.destroy()
        self.configure(bg=COLORS["bg"])
        if cover and cover.winfo_exists():
            cover.memorypal_cover_color = COLORS["bg"]
            cover.configure(bg=COLORS["bg"])
            self.paint_cover(cover)
            self.raise_widget(cover)
            cover.update()
        if refresh_styles:
            self._styles()
        self._shell()
        self.show_view(current, transition=False)
        if cover is None:
            return
        self.raise_widget(cover)
        self.after(70, lambda: self.fade_simple_cover(cover))

    def update_cover_geometry(self, cover):
        if not cover or not cover.winfo_exists():
            return
        try:
            cover.place_configure(relx=0, rely=0, relwidth=1, relheight=1)
            self.raise_widget(cover)
        except tk.TclError:
            pass

    def make_frame_cover(self, scope="root"):
        if scope == "root":
            parent = self
        elif scope == "main":
            parent = self.main
        elif scope == "rail":
            parent = self.rail
        else:
            parent = self.content
        if not parent.winfo_viewable():
            return None
        color = COLORS["bg"]
        cover = tk.Canvas(parent, bg=color, highlightthickness=0, bd=0)
        cover.memorypal_scope = scope
        cover.memorypal_cover_color = color
        cover.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.paint_cover(cover)
        cover.bind("<Configure>", lambda _event, target=cover: self.paint_cover(target), add="+")
        self.raise_widget(cover)
        cover.update()
        return cover

    def paint_cover(self, cover, stipple=None):
        if not cover or not cover.winfo_exists():
            return
        try:
            if stipple is None:
                stipple = getattr(cover, "memorypal_cover_stipple", "")
            cover.memorypal_cover_stipple = stipple
            cover.delete("all")
            color = getattr(cover, "memorypal_cover_color", COLORS["bg"])
            cover.configure(bg=color)
            width = max(1, cover.winfo_width())
            height = max(1, cover.winfo_height())
            cover.create_rectangle(0, 0, width, height, fill=color, outline="", stipple=stipple, tags="veil")
        except tk.TclError:
            pass

    def start_root_cover(self, prefer_fade=True):
        self.update_idletasks()
        if not self.winfo_viewable():
            return None
        self.destroy_transition_cover(self.root_cover)
        cover = self.start_transition_cover("root")
        self.root_cover = cover
        return cover

    def fade_simple_cover(self, cover, step=0):
        if not cover or not cover.winfo_exists():
            return
        self.raise_widget(cover)
        if getattr(self, "accessibility", {}).get("reduce_motion"):
            self.after(110, lambda target=cover: self.destroy_transition_cover(target))
            return
        self.fade_frame_cover(cover, step=step)

    def show_popup_window(self, top, owner, width=None, height=None, modal=True):
        # width/height are the preferred size; the popup still grows to fit
        # what it holds (a fixed size clipped buttons and text at the larger
        # text sizes) and is capped to, and kept on, the screen.
        top.update_idletasks()
        popup_width = max(width or 0, top.winfo_reqwidth(), self.px(360))
        if width:
            # Wrapped labels asked for their width at the preferred size; let
            # them settle at the final width before measuring the height.
            top.geometry(f"{popup_width}x{max(1, top.winfo_reqheight())}")
            top.update_idletasks()
        popup_height = max(height or 0, top.winfo_reqheight(), self.px(160))
        left, s_top, right, bottom = self.screen_bounds(owner)
        margin = self.px(8)
        popup_width = min(popup_width, right - left - margin * 2)
        popup_height = min(popup_height, bottom - s_top - margin * 2)
        x = owner.winfo_rootx() + (owner.winfo_width() - popup_width) // 2
        y = owner.winfo_rooty() + max(0, (owner.winfo_height() - popup_height) // 3)
        x = max(left + margin, min(x, right - margin - popup_width))
        y = max(s_top + margin, min(y, bottom - margin - popup_height))
        top.geometry(f"{popup_width}x{popup_height}+{x}+{y}")
        self.reveal_window(top, owner)
        previous_grab = None
        if modal:
            previous_grab = top.grab_current()
            top.grab_set()
        self.activate_popup(top, owner, previous_grab)

    def activate_popup(self, top, owner, previous_grab=None):
        """Make a popup the active window, and give focus back when it closes.

        Borderless (override-redirect) windows are shown without being
        activated, so Windows keeps sending keystrokes to the window
        underneath. Typing into a popup's box then only worked when Tk
        happened to pass the keys along. Activating the popup sends keys to
        it every time.
        """
        def activate():
            try:
                if not top.winfo_exists():
                    return
                top.focus_force()
                hwnd = self.window_handle(top)
                if hwnd and sys.platform.startswith("win"):
                    import ctypes

                    ctypes.windll.user32.SetForegroundWindow(hwnd)
            except (tk.TclError, AttributeError, OSError):
                pass

        activate()

        def give_back(event):
            if event.widget is not top:
                return

            def restore():
                try:
                    # A dialog opened from another popup (like Profiles) takes
                    # over its grab; hand it back so that popup stays modal.
                    if previous_grab is not None and previous_grab is not top and previous_grab.winfo_exists():
                        previous_grab.grab_set()
                    if owner is not None and owner.winfo_exists() and owner.winfo_ismapped():
                        owner.focus_force()
                except tk.TclError:
                    pass

            try:
                self.after_idle(restore)
            except tk.TclError:
                pass

        top.bind("<Destroy>", give_back, add="+")

    def window_handle(self, window):
        try:
            import ctypes
            from ctypes import wintypes

            get_ancestor = ctypes.windll.user32.GetAncestor
            get_ancestor.restype = wintypes.HWND
            get_ancestor.argtypes = (wintypes.HWND, ctypes.c_uint)
            return get_ancestor(window.winfo_id(), 2)  # GA_ROOT: the real top-level window
        except (AttributeError, OSError, tk.TclError):
            return None

    def own_window(self, top, owner):
        """Keep a borderless popup above the window it belongs to.

        On Windows, Tk turns a borderless window marked transient into a
        child window, and Windows never lets a child window be the active
        one, so it can't get keyboard focus (typing in it only worked by
        chance). Instead the owner is set directly when the popup is shown:
        it still stays above its owner, and it can be activated.
        """
        if sys.platform.startswith("win"):
            top._native_owner = owner
        else:
            top.transient(owner)

    def apply_native_owner(self, top):
        owner = getattr(top, "_native_owner", None)
        if owner is None:
            return
        try:
            import ctypes

            user32 = ctypes.windll.user32
            setter = getattr(user32, "SetWindowLongPtrW", None) or user32.SetWindowLongW
            setter.restype = ctypes.c_void_p
            setter.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p)
            hwnd, owner_hwnd = self.window_handle(top), self.window_handle(owner)
            if hwnd and owner_hwnd:
                setter(hwnd, -8, owner_hwnd)  # GWLP_HWNDPARENT: the owner window
        except (AttributeError, OSError, tk.TclError):
            pass

    def reveal_window(self, top, owner=None):
        """Map a window invisibly, let it lay out and paint, then show it at once.

        No fade: the window stays fully transparent until every geometry and
        paint pass has run, so its first visible frame is the finished one.
        """
        try:
            top.attributes("-alpha", 0.0)
        except tk.TclError:
            pass
        top.deiconify()
        self.apply_native_owner(top)
        if owner is not None:
            top.lift(owner)
        else:
            top.lift()
        for _ in range(4):
            top.update_idletasks()
            if not flush_pending_paint(top):
                break
        try:
            import ctypes

            ctypes.windll.dwmapi.DwmFlush()
        except (AttributeError, OSError):
            pass
        try:
            top.attributes("-alpha", 1.0)
        except tk.TclError:
            pass

    def _display_scales(self):
        try:
            dpi = float(self.winfo_fpixels("1i"))
        except tk.TclError:
            dpi = BASE_DPI
        dpi_scale = clamp(dpi / BASE_DPI, 1.0, 1.65)
        screen_w = max(1, self.winfo_screenwidth())
        screen_h = max(1, self.winfo_screenheight())
        size_scale = clamp(min(screen_w / 1536, screen_h / 960), 0.92, 1.14)
        return dpi_scale, size_scale

    def accessibility_multiplier(self):
        return {
            "Comfort": 1.0,
            "Large": 1.14,
            "Extra Large": 1.28,
        }.get(self.accessibility.get("text_size", "Comfort"), 1.0)

    def apply_accessibility_palette(self):
        if not self.accessibility.get("high_contrast"):
            return
        if self.theme == "light":
            COLORS.update({
                "bg": "#eef3fb",
                "surface": "#ffffff",
                "alt": "#dbe8f7",
                "muted": "#25324a",
                "line": "#8da4bf",
                "soft_line": "#6f86a3",
                "primary": "#005fcc",
                "primary_dark": "#004b9f",
                "rail": "#07111f",
                "rail_hover": "#13233b",
            })
        else:
            COLORS.update({
                "bg": "#0b1220",
                "surface": "#101b2d",
                "alt": "#1d2c45",
                "muted": "#d5dfef",
                "line": "#74859f",
                "soft_line": "#91a2bd",
                "primary": "#8dccff",
                "primary_dark": "#5eb6ff",
                "rail": "#050914",
                "rail_hover": "#172640",
            })

    def apply_theme_palette(self):
        COLORS.clear()
        COLORS.update(DARK_COLORS if self.theme == "dark" else LIGHT_COLORS)
        self.apply_accessibility_palette()

    def apply_accessibility_preferences(self):
        self.accessibility = normalize_accessibility(self.accessibility)
        multiplier = self.accessibility_multiplier()
        self.font_scale = clamp(self.base_font_scale * multiplier, 0.96, 1.48)
        self.ui_scale = clamp(self.base_ui_scale * (1 + (multiplier - 1) * 0.55), 0.95, 1.55)
        self.apply_theme_palette()

    def update_accessibility_preference(self, key, value, rebuild=True):
        # Start from the saved copy, which may have just synced from another device.
        self.accessibility = dict(normalize_accessibility(self.store.accessibility))
        self.accessibility[key] = value
        self.accessibility = normalize_accessibility(self.accessibility)
        self.store.accessibility = dict(self.accessibility)
        self.store.save()
        if rebuild:
            self.save_current_draft()
            self.apply_accessibility_preferences()
            self.rebuild_shell(self.current_view, refresh_styles=True)

    def apply_senior_layout_defaults(self):
        self.accessibility.update({
            "text_size": "Large",
            "high_contrast": True,
            "reduce_motion": True,
            "simple_language": True,
            "caregiver_mode": True,
            "more_time": True,
        })
        self.store.accessibility = normalize_accessibility(self.accessibility)
        self.set_nav_order(["dashboard", "elder", "training", "capture", "review", "testing", "games", "library", "stats", "settings"])
        self.apply_accessibility_preferences()
        self.rebuild_shell("settings", refresh_styles=True)
        self.toast_message("Senior-friendly layout applied.")

    def speak(self, text, quiet=False):
        """Read text aloud with the system voice (slower when More time is on)."""
        self._reset_speak_button()
        if not self.speaker.speak(text, slow=self.accessibility.get("more_time", False)):
            if normalize_space(text) and not quiet:
                self.toast_message("Read aloud isn't available on this computer.")
            return False
        return True

    def stop_speaking(self):
        self.speaker.stop()
        self._reset_speak_button()

    def _reset_speak_button(self):
        button = getattr(self, "_speaking_button", None)
        self._speaking_button = None
        if button is not None:
            try:
                if button.winfo_exists():
                    button._memorypal_set(False)
            except tk.TclError:
                pass

    def speak_button(self, parent, text, label="Read aloud", compact=False):
        """The read-aloud control used everywhere a card, note or answer is shown.

        A speaker icon (with "Read aloud" unless compact) that turns into Stop
        while reading. text may be a string or a function returning one, so
        it reads what is on screen at the moment it is pressed. It is a normal
        button: Tab reaches it, Space or Enter presses it, and changing page
        stops the voice.
        """
        source = text if callable(text) else (lambda: text)
        size = self.px(18)
        button = ttk.Button(parent, style="Link.TButton" if compact else "TButton", cursor="hand2", takefocus=1)

        def show(speaking):
            icon = self.line_icon("stop" if speaking else "speaker", size, COLORS["primary"] if compact else COLORS["ink"])
            words = "Stop" if speaking else label
            if icon is not None:
                button._memorypal_icon = icon
                button.configure(image=icon, compound="image" if compact else "left", text="" if compact else f" {words}")
            else:
                button.configure(text=words)

        def watch():
            if not button.winfo_exists() or getattr(self, "_speaking_button", None) is not button:
                return
            if self.speaker.speaking():
                button.after(250, watch)
            else:
                self._reset_speak_button()

        def press():
            if getattr(self, "_speaking_button", None) is button and self.speaker.speaking():
                self.stop_speaking()
                return
            if self.speak(source()):
                self._speaking_button = button
                show(True)
                button.after(250, watch)

        button._memorypal_set = show
        button.configure(command=press)
        button.bind("<Return>", lambda _event: (press(), "break")[1])
        show(False)
        self.add_tooltip(button, f"{label} with the computer's own voice. Works offline. Press again to stop.")
        return button

    def read_aloud_button(self, parent, text, label="Read aloud"):
        return self.speak_button(parent, text, label)

    def show_focus_outline(self):
        # Keyboard users must always see where focus is (WCAG 2.4.7), so the
        # ring is always on; the setting and high contrast make it thicker.
        return True

    def strong_focus_outline(self):
        return bool(self.accessibility.get("focus_outline") or self.accessibility.get("high_contrast"))

    def focus_thickness(self):
        return max(2, self.px(3 if self.strong_focus_outline() else 2))

    def focus_color(self):
        return COLORS.get("focus", "#f5b301")

    def keyboard_link(self, widget, handler):
        """Make a clickable label reachable with Tab and work with Enter or Space."""
        widget.configure(
            takefocus=1,
            highlightthickness=self.focus_thickness(),
            highlightbackground=widget.cget("bg"),
            highlightcolor=self.focus_color(),
        )
        for sequence in ("<Button-1>", "<Return>", "<KP_Enter>", "<space>"):
            widget.bind(sequence, handler)

    def pace(self, milliseconds):
        """Stretch timed displays when the More time preference is on."""
        return int(milliseconds * (2 if self.accessibility.get("more_time") else 1))

    def plain(self, normal, simple):
        return simple if self.accessibility.get("simple_language") else normal

    def describe_assessment(self, checked):
        if not self.accessibility.get("simple_language"):
            return f"{checked['label']} | {checked['score']}% | Bucket: {checked['bucket']} | Reps: {checked['repetitions']} | {checked['detail']}"
        message = {
            "Easy": "Well done \u2014 you remembered it.",
            "Good": "Nearly all there.",
            "Review": "You remembered part of it.",
            "Again": "Not quite yet \u2014 that's okay, it will come back soon.",
        }.get(checked["bucket"], checked["label"])
        if checked["detail"].startswith("Missing key cues:"):
            message += " Words that would help: " + checked["detail"].split(":", 1)[1].strip() + "."
        return message

    def rating_label(self, bucket):
        return self.plain(bucket, {"Again": "Not yet", "Review": "Hard", "Good": "Got it", "Easy": "Easy"}.get(bucket, bucket))

    def px(self, value):
        return max(1, int(round(value * self.ui_scale)))

    def font(self, family, size):
        size = max(8, int(round(size * self.font_scale)))
        if family in ("Segoe UI", "Segoe UI Semibold"):
            system = self.system_ui_family()
            if system:
                # Off Windows, ask for the system's own UI font (San Francisco
                # on a Mac) instead of letting Tk swap Segoe for a lookalike,
                # which also dropped the Semibold weight from every heading.
                return (system, size, "bold") if family.endswith("Semibold") else (system, size)
        return (family, size)

    def system_ui_family(self):
        """The platform UI font to use instead of Segoe UI, or None to keep Segoe."""
        cached = getattr(self, "_system_ui_family", False)
        if cached is not False:
            return cached
        family = None
        if self.available_font("Segoe UI", fallback="") != "Segoe UI":
            try:
                # Read before _styles points TkDefaultFont at the body font.
                family = tkfont.nametofont("TkDefaultFont", root=self).actual("family") or None
            except (tk.TclError, TypeError):
                family = None
        self._system_ui_family = family
        return family

    def available_font(self, *families, fallback="Segoe UI Symbol"):
        if self._font_families is None:
            try:
                self._font_families = set(tkfont.families(self))
            except tk.TclError:
                self._font_families = set()
        for family in families:
            if family in self._font_families:
                return family
        return fallback

    def pad(self, *values):
        return tuple(self.px(value) for value in values)

    def _set_window_size(self):
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        margin = self.px(96)
        width = min(self.px(BASE_WINDOW[0]), max(self.px(980), screen_w - margin))
        height = min(self.px(BASE_WINDOW[1]), max(self.px(640), screen_h - margin))
        min_width = min(self.px(BASE_MIN_WINDOW[0]), width)
        min_height = min(self.px(BASE_MIN_WINDOW[1]), height)
        self.geometry(f"{width}x{height}")
        self.minsize(min_width, min_height)

    def _styles(self):
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        # A blanket "*Font" option gives every ttk widget its own -font, and a
        # widget font beats the style font: every Title, H2 and Stat label
        # was drawn as 12pt body text. Set the default only for classic Tk
        # widgets (and ttk inputs, which take their font per widget), and let
        # the named default fonts cover everything else.
        body = self.font("Segoe UI", 12)
        for widget_class in ("Label", "Button", "Entry", "Text", "Listbox", "Checkbutton", "Radiobutton", "Menubutton", "Menu", "Message", "Spinbox", "TEntry", "TCombobox", "TSpinbox"):
            self.option_add(f"*{widget_class}.Font", body)
        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont"):
            try:
                tkfont.nametofont(name, root=self).configure(family=body[0], size=body[1])
            except (tk.TclError, TypeError):
                pass
        self.style.configure("Root.TFrame", background=COLORS["bg"])
        self.style.configure("Rail.TFrame", background=COLORS["rail"])
        self.style.configure("Page.TFrame", background=COLORS["bg"])
        # The page header sits straight on the window, like a macOS/Windows
        # title area: no card around it, so the page content is the first box.
        self.style.configure("Header.TFrame", background=COLORS["bg"], relief="flat", borderwidth=0)
        self.style.configure("Card.TFrame", background=COLORS["surface"], relief="flat", borderwidth=0)
        self.style.configure("AltCard.TFrame", background=COLORS["alt"], relief="flat", borderwidth=0)
        # "Warm" callouts are now quiet neutral insets; the orange boxes
        # shouted louder than the content they introduced.
        self.style.configure("WarmCard.TFrame", background=COLORS["alt"], relief="flat", borderwidth=0)
        self.style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["ink"], font=self.font("Segoe UI", 12))
        self.style.configure("Muted.TLabel", background=COLORS["bg"], foreground=COLORS["muted"], font=self.font("Segoe UI", 11))
        self.style.configure("Card.TLabel", background=COLORS["surface"], foreground=COLORS["ink"], font=self.font("Segoe UI", 12))
        self.style.configure("CardMuted.TLabel", background=COLORS["surface"], foreground=COLORS["muted"], font=self.font("Segoe UI", 11))
        self.style.configure("Header.TLabel", background=COLORS["bg"], foreground=COLORS["ink"], font=self.font("Segoe UI", 12))
        self.style.configure("HeaderMuted.TLabel", background=COLORS["bg"], foreground=COLORS["muted"], font=self.font("Segoe UI", 11))
        self.style.configure("PageTitle.TLabel", background=COLORS["bg"], foreground=COLORS["ink"], font=self.font("Segoe UI Semibold", 25))
        self.style.configure("AltCard.TLabel", background=COLORS["alt"], foreground=COLORS["ink"], font=self.font("Segoe UI", 12))
        self.style.configure("AltMuted.TLabel", background=COLORS["alt"], foreground=COLORS["muted"], font=self.font("Segoe UI", 11))
        self.style.configure("WarmCard.TLabel", background=COLORS["alt"], foreground=COLORS["ink"], font=self.font("Segoe UI", 11))
        self.style.configure("WarmMuted.TLabel", background=COLORS["alt"], foreground=COLORS["muted"], font=self.font("Segoe UI", 11))
        self.style.configure("Title.TLabel", background=COLORS["surface"], foreground=COLORS["ink"], font=self.font("Segoe UI Semibold", 28))
        self.style.configure("H2.TLabel", background=COLORS["surface"], foreground=COLORS["ink"], font=self.font("Segoe UI Semibold", 18))
        self.style.configure("AltH2.TLabel", background=COLORS["alt"], foreground=COLORS["ink"], font=self.font("Segoe UI Semibold", 18))
        self.style.configure("WarmH2.TLabel", background=COLORS["alt"], foreground=COLORS["ink"], font=self.font("Segoe UI Semibold", 13))
        self.style.configure("Stat.TLabel", background=COLORS["surface"], foreground=COLORS["primary"], font=self.font("Segoe UI Semibold", 34))
        self.style.configure("RailTitle.TLabel", background=COLORS["rail"], foreground=COLORS["white"], font=self.font("Segoe UI Semibold", 20))
        self.style.configure("RailText.TLabel", background=COLORS["rail"], foreground=COLORS["rail_muted"], font=self.font("Segoe UI", 12))
        self.style.configure("TEntry", padding=self.px(11), background=COLORS["input"], fieldbackground=COLORS["input"], foreground=COLORS["ink"], insertcolor=COLORS["ink"], bordercolor=COLORS["input"], lightcolor=COLORS["input"], darkcolor=COLORS["input"], relief="flat")
        self.style.map("TEntry", bordercolor=[("focus", COLORS["primary"])], lightcolor=[("focus", COLORS["input"])], darkcolor=[("focus", COLORS["input"])])
        self.style.configure("TCombobox", padding=self.px(11), background=COLORS["input"], fieldbackground=COLORS["input"], foreground=COLORS["ink"], bordercolor=COLORS["input"], lightcolor=COLORS["input"], darkcolor=COLORS["input"], relief="flat")
        # Slim overlay-style scrollbars: a quiet thumb on the window colour,
        # no arrow buttons (they drew as small square caps at each end), and
        # a darker thumb only while it is being used.
        thumb = self.blend_hex(COLORS["bg"], COLORS["muted"], 0.45)
        for orient in ("Vertical", "Horizontal"):
            scrollbar_style = f"{orient}.TScrollbar"
            self.style.layout(scrollbar_style, [(f"{orient}.Scrollbar.trough", {
                "sticky": "ns" if orient == "Vertical" else "ew",
                "children": [(f"{orient}.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})],
            })])
            self.style.configure(
                scrollbar_style,
                gripcount=0,
                width=self.px(8),
                arrowsize=self.px(8),
                background=thumb,
                darkcolor=thumb,
                lightcolor=thumb,
                troughcolor=COLORS["bg"],
                bordercolor=COLORS["bg"],
                arrowcolor=COLORS["muted"],
                relief="flat",
            )
            self.style.map(
                scrollbar_style,
                background=[("pressed", COLORS["muted"]), ("active", COLORS["muted"])],
                darkcolor=[("pressed", COLORS["muted"]), ("active", COLORS["muted"])],
                lightcolor=[("pressed", COLORS["muted"]), ("active", COLORS["muted"])],
            )
        self.style.configure("Rail.Vertical.TScrollbar", gripcount=0, width=self.px(13), arrowsize=self.px(11), background=COLORS["muted"], darkcolor=COLORS["rail"], lightcolor=COLORS["rail"], troughcolor=COLORS["rail"], bordercolor=COLORS["rail"], arrowcolor=COLORS["muted"], relief="flat")
        self.style.configure("Horizontal.TProgressbar", troughcolor=COLORS["alt"], background=COLORS["primary"], bordercolor=COLORS["alt"], lightcolor=COLORS["primary"], darkcolor=COLORS["primary"])
        semibold = self.font("Segoe UI Semibold", 11)
        self.style.configure("TButton", padding=self.pad(18, 11), foreground=COLORS["ink"], borderwidth=0, relief="flat", font=semibold)
        self.style.map("TButton", foreground=[("disabled", COLORS["muted"]), ("active", COLORS["primary"])])
        self.style.configure("Primary.TButton", padding=self.pad(18, 11), foreground=self.on_color(COLORS["primary"]), borderwidth=0, relief="flat", font=self.font("Segoe UI Semibold", 12))
        self.style.map("Primary.TButton", foreground=[("disabled", COLORS["muted"]), ("active", self.on_color(COLORS["primary_dark"]))])
        self.style.configure("TMenubutton", padding=self.pad(18, 11), foreground=COLORS["ink"], borderwidth=0, arrowcolor=COLORS["muted"], relief="flat", font=semibold)
        self.style.map("TMenubutton", foreground=[("active", COLORS["primary"])])
        self.style.configure("Select.TMenubutton", padding=self.pad(16, 10), foreground=COLORS["ink"], borderwidth=0, arrowcolor=COLORS["muted"], relief="flat", font=self.font("Segoe UI", 11))
        self.style.configure("Danger.TButton", padding=self.pad(18, 11), foreground=self.on_color(COLORS["danger"]), borderwidth=0, relief="flat", font=semibold)
        # A quiet text button ("More options", "Remove"): accent text on the
        # surface it sits on, a soft tile on hover, the usual focus ring.
        self.style.configure("Link.TButton", padding=self.pad(8, 6), foreground=COLORS["primary"], borderwidth=0, relief="flat", font=semibold)
        self.style.map("Link.TButton", foreground=[("disabled", COLORS["muted"]), ("active", COLORS["primary"])])
        # Segmented choices (Study Plan time, quiz modes): one pill per option.
        self.style.configure("Pill.TButton", padding=self.pad(14, 8), foreground=COLORS["ink"], borderwidth=0, relief="flat", font=semibold)
        self.style.map("Pill.TButton", foreground=[("active", COLORS["primary"])])
        self.style.configure("PillOn.TButton", padding=self.pad(14, 8), foreground=self.on_color(COLORS["primary"]), borderwidth=0, relief="flat", font=semibold)
        self.style.map("PillOn.TButton", foreground=[("active", self.on_color(COLORS["primary_dark"]))])
        for name, fg in (("Again", "again_fg"), ("Review", "review_fg"), ("Good", "good_fg"), ("Easy", "easy_fg")):
            self.style.configure(f"{name}.TButton", padding=self.pad(18, 11), foreground=COLORS[fg], borderwidth=0, relief="flat", font=semibold)
            self.style.map(f"{name}.TButton", foreground=[("active", COLORS[fg])])
        # Compact rail items so every page fits without paging on a normal
        # laptop screen; the active page is a calm filled pill, not a bright
        # block (white on the old bright blue was only 2.3:1).
        self.style.configure("Nav.TButton", padding=self.pad(12, 9), space=self.px(12), foreground=COLORS["rail_text"], anchor="w", borderwidth=0, relief="flat", font=self.font("Segoe UI", 12))
        self.style.map("Nav.TButton", foreground=[("disabled", self.tint(COLORS["rail_muted"], -50)), ("active", COLORS["white"])])
        self.style.configure("ActiveNav.TButton", padding=self.pad(12, 9), space=self.px(12), foreground=COLORS["white"], anchor="w", borderwidth=0, relief="flat", font=self.font("Segoe UI Semibold", 12))
        self.style.map("ActiveNav.TButton", foreground=[("active", COLORS["white"])])
        # The top tab bar: quiet tabs on the window background, and the
        # current section as a soft tinted pill in the accent colour.
        self.style.configure("TabBar.TFrame", background=COLORS["bg"])
        self.style.configure("TabBar.TButton", padding=self.pad(14, 8), space=self.px(8), foreground=COLORS["muted"], anchor="center", borderwidth=0, relief="flat", font=self.font("Segoe UI Semibold", 11))
        self.style.map("TabBar.TButton", foreground=[("active", COLORS["ink"])])
        self.style.configure("ActiveTabBar.TButton", padding=self.pad(14, 8), space=self.px(8), foreground=COLORS["primary"], anchor="center", borderwidth=0, relief="flat", font=self.font("Segoe UI Semibold", 11))
        self.style.map("ActiveTabBar.TButton", foreground=[("active", COLORS["primary"])])

        # Keyboard focus is always visible (a ring inside the button).
        for name in ("TButton", "Primary.TButton", "Danger.TButton", "Again.TButton", "Review.TButton", "Good.TButton", "Easy.TButton", "Nav.TButton", "ActiveNav.TButton", "TabBar.TButton", "ActiveTabBar.TButton", "TMenubutton", "Select.TMenubutton", "Pill.TButton", "PillOn.TButton", "Link.TButton"):
            self.style.configure(name, focuscolor=self.focus_color(), focusthickness=self.focus_thickness())
        self.install_rounded_controls()

    # ------------------------------------------------------------------
    # Rounded controls
    # ------------------------------------------------------------------
    def control_palettes(self):
        """(normal, hover, pressed) fills for each rounded button style."""
        soft, alt = COLORS["surface_soft"], COLORS["alt"]
        rating = lambda key: (COLORS[key], self.tint(COLORS[key], -12), self.tint(COLORS[key], -22))
        return {
            "TButton": ("TButton", (soft, alt, self.tint(alt, -14)), COLORS["surface"]),
            "Primary.TButton": ("TButton", (COLORS["primary"], COLORS["primary_dark"], self.tint(COLORS["primary_dark"], -14)), COLORS["surface"]),
            "Danger.TButton": ("TButton", (COLORS["danger"], self.tint(COLORS["danger"], -18), self.tint(COLORS["danger"], -30)), COLORS["surface"]),
            "Again.TButton": ("TButton", rating("again_bg"), COLORS["surface"]),
            "Review.TButton": ("TButton", rating("review_bg"), COLORS["surface"]),
            "Good.TButton": ("TButton", rating("good_bg"), COLORS["surface"]),
            "Easy.TButton": ("TButton", rating("easy_bg"), COLORS["surface"]),
            "Nav.TButton": ("TButton", (COLORS["rail"], COLORS["rail_hover"], COLORS["rail_hover"], COLORS["rail"]), COLORS["rail"]),
            "ActiveNav.TButton": ("TButton", (COLORS["rail_active"],) * 3 + (COLORS["rail"],), COLORS["rail"]),
            "TabBar.TButton": ("TButton", (COLORS["bg"], COLORS["surface_soft"], COLORS["alt"]), COLORS["bg"]),
            "ActiveTabBar.TButton": ("TButton", (COLORS["alt"],) * 3, COLORS["bg"]),
            "TMenubutton": ("TMenubutton", (soft, alt, self.tint(alt, -14)), COLORS["surface"]),
            "Link.TButton": ("TButton", (COLORS["surface"], soft, alt), COLORS["surface"]),
            "Select.TMenubutton": ("TMenubutton", (COLORS["input"], alt, alt), COLORS["surface"]),
            "Pill.TButton": ("TButton", (COLORS["input"], self.tint(COLORS["input"], -10 if self.theme == "light" else 16), self.tint(COLORS["input"], -20 if self.theme == "light" else 26)), COLORS["surface"]),
            "PillOn.TButton": ("TButton", (COLORS["primary"], COLORS["primary_dark"], self.tint(COLORS["primary_dark"], -14)), COLORS["surface"]),
        }

    def rounded_tile(self, fill, bg, ring=None, ring_width=0):
        """A small antialiased rounded square, stretched by ttk as a 9-slice.

        The tile is fully opaque: its corners are blended onto `bg`, the
        surface the control sits on. Tk on Windows draws photos with
        transparency by reading the screen back on every redraw, which made
        pages with many buttons take seconds to build and paint in pieces.
        """
        radius = self.px(9)
        size = radius * 2 + 4
        key = ("tile", size, fill, bg, ring, ring_width)
        photo = self._tile_cache.get(key)
        if photo is not None:
            return photo
        fill_rgb = self.hex_to_rgb(fill) or (128, 128, 128)
        bg_rgb = self.hex_to_rgb(bg) or fill_rgb
        ring_rgb = self.hex_to_rgb(ring) if ring else None
        half = size / 2

        def distance(px, py, inset):
            r = max(0.0, radius - inset)
            reach = half - inset - r
            qx, qy = abs(px - half) - reach, abs(py - half) - reach
            return math.hypot(max(qx, 0.0), max(qy, 0.0)) + min(max(qx, qy), 0.0) - r

        # The tile is symmetric about both centre lines, so work out one
        # quarter and mirror it (a quarter of the per-pixel maths).
        quarter = (size + 1) // 2
        rows = []
        for y in range(quarter):
            row = []
            for x in range(quarter):
                px, py = x + 0.5, y + 0.5
                cover = max(0.0, min(1.0, 0.5 - distance(px, py, 0)))
                color = fill_rgb
                if ring_rgb and ring_width:
                    inner = max(0.0, min(1.0, 0.5 - distance(px, py, ring_width)))
                    color = tuple(ring_rgb[i] + (fill_rgb[i] - ring_rgb[i]) * inner for i in range(3))
                row.append(bytes((*(int(round(bg_rgb[i] + (color[i] - bg_rgb[i]) * cover)) for i in range(3)), 255)))
            row += row[: size - quarter][::-1]
            rows.append(b"".join(row))
        rows += rows[: size - quarter][::-1]
        pixels = b"".join(rows)
        data = base64.b64encode(self.png_rgba(size, size, bytes(pixels))).decode("ascii")
        small = tk.PhotoImage(master=self, data=data, format="png")
        photo = self.widen_tile(small, radius, fill)
        self._tile_cache[key] = photo
        return photo

    def corner_photo(self, radius, fill, under, corner):
        """One antialiased quarter-circle corner (opaque, blended onto `under`), cached."""
        cache = self.__dict__.setdefault("_corner_cache", {})
        key = (radius, fill, under, corner)
        if key in cache:
            return cache[key]
        fill_rgb, under_rgb = self.hex_to_rgb(fill), self.hex_to_rgb(under)
        if not fill_rgb or not under_rgb:
            return None
        # The circle's centre sits at the inner corner of the r-by-r square.
        cx = radius if corner in ("nw", "sw") else 0
        cy = radius if corner in ("nw", "ne") else 0
        pixels = bytearray()
        for y in range(radius):
            for x in range(radius):
                cover = max(0.0, min(1.0, radius - math.hypot(x + 0.5 - cx, y + 0.5 - cy) + 0.5))
                pixels.extend((*(int(round(under_rgb[i] + (fill_rgb[i] - under_rgb[i]) * cover)) for i in range(3)), 255))
        photo = tk.PhotoImage(master=self, data=base64.b64encode(self.png_rgba(radius, radius, bytes(pixels))).decode("ascii"), format="png")
        cache[key] = photo
        return photo

    def widen_tile(self, small, radius, fill):
        """Grow a corner tile to a large 9-slice tile, using Tk's own copy.

        ttk fills a stretched image element by repeating its middle, so a
        tile with a 4px middle needed thousands of draw calls for one wide
        button. A large middle needs a handful. Edges are a 1px strip of the
        small tile repeated along the side.
        """
        s, r = small.width(), radius
        width, height = 2 * r + 256, 2 * r + 96
        big = tk.PhotoImage(master=self, width=width, height=height)
        call = lambda *args: self.tk.call(big.name, "copy", small.name, *args)
        big.put(fill, to=(0, 0, width, height))
        for (fx, fy), (tx, ty) in (((0, 0), (0, 0)), ((s - r, 0), (width - r, 0)), ((0, s - r), (0, height - r)), ((s - r, s - r), (width - r, height - r))):
            call("-from", fx, fy, fx + r, fy + r, "-to", tx, ty)
        call("-from", r, 0, r + 1, r, "-to", r, 0, width - r, r)
        call("-from", r, s - r, r + 1, s, "-to", r, height - r, width - r, height)
        call("-from", 0, r, r, r + 1, "-to", 0, r, r, height - r)
        call("-from", s - r, r, s, r + 1, "-to", width - r, r, width, height - r)
        big._memorypal_source = small  # keep the small tile alive with it
        return big

    def rounded_element(self, normal, hover=None, pressed=None, disabled=None, focus=None, focus_hover=None, keyboard_only=False):
        """A ttk image element (cached by its tiles) with per-state tiles.

        Keyboard focus is a solid ring drawn into the tile (clam's own focus
        indicator is a faint dotted box that is easy to miss). With
        keyboard_only, the ring needs the "user1" state too, which
        track_focus_source sets only when focus arrived from the keyboard.
        """
        key = (str(normal), str(hover), str(pressed), str(disabled), str(focus), str(focus_hover), keyboard_only)
        name = self._rounded_elements.get(key)
        if name:
            return name
        name = f"mp{len(self._rounded_elements) + 1}x{self._style_generation}.surface"
        states = []
        if disabled:
            states.append(("disabled", disabled))
        if pressed:
            states.append(("pressed", pressed))
        focused = ("focus", "user1") if keyboard_only else ("focus",)
        if focus_hover:
            states.append((*focused, "active", focus_hover))
        if focus:
            states.append((*focused, focus))
        if hover:
            states.append(("active", hover))
        # The border is the 9-slice corner size (it must leave a middle strip
        # to stretch). An image element also uses its border as the inner
        # padding unless told otherwise, which made every button ~30px taller.
        # width/height set the element's minimum size; without them it asks
        # for the full (large) tile size and every button grows to match.
        border = self.px(9)
        self.style.element_create(name, "image", normal, *states, border=border, padding=0, width=2 * border + 2, height=2 * border + 2, sticky="nsew")
        self._rounded_elements[key] = name
        return name

    def round_style(self, style, widget_class, fills, bg):
        """Give `style` rounded tiles in these (normal, hover, pressed[, disabled])
        fills, with corners baked onto the surface colour `bg`."""
        if widget_class == "TEntry":
            self.round_entry_style(style, bg)
            return
        normal, hover, pressed = fills[:3]
        # Disabled controls fade into their surface; the nav rail is disabled
        # during first-run setup and must stay rail-coloured, not light boxes.
        disabled = fills[3] if len(fills) > 3 else self.tint(COLORS["surface_soft"], 4 if self.theme == "dark" else -4)
        ring, width = self.focus_color(), self.focus_thickness()
        element = self.rounded_element(
            self.rounded_tile(normal, bg), self.rounded_tile(hover, bg), self.rounded_tile(pressed, bg),
            disabled=self.rounded_tile(disabled, bg),
            focus=self.rounded_tile(normal, bg, ring=ring, ring_width=width),
            focus_hover=self.rounded_tile(hover, bg, ring=ring, ring_width=width),
            keyboard_only=True,
        )
        self.style.layout(style, [(element, {"sticky": "nsew", "children": self.inner_layout(widget_class)})])
        self.set_corner_background(style, bg)

    def round_entry_style(self, style, bg):
        line = COLORS["soft_line"] if self.theme == "light" else COLORS["line"]
        thin = max(1, self.px(1))
        element = self.rounded_element(
            self.rounded_tile(COLORS["input"], bg, ring=line, ring_width=thin),
            hover=self.rounded_tile(COLORS["input"], bg, ring=COLORS["muted"], ring_width=thin),
            focus=self.rounded_tile(COLORS["input"], bg, ring=COLORS["primary"], ring_width=max(2, self.px(2))),
        )
        self.style.layout(style, [(element, {"sticky": "nsew", "children": self.inner_layout("TEntry")})])
        self.set_corner_background(style, bg)

    def set_corner_background(self, style, color):
        """Keep the style background equal to the surface in every state.

        clam maps a button's background to near-white when hovered or
        pressed; with the tiles' corners baked onto the surface colour, any
        other background could only show as a fleck at the edges.
        """
        self.style.configure(style, background=color)
        self.style.map(style, background=[("disabled", color), ("pressed", color), ("active", color)])

    def inner_layout(self, widget_class):
        """What clam draws inside a control's border, minus its dotted focus box
        (the rounded tile draws a solid focus ring instead)."""
        layout = self._clam_layouts[widget_class]
        children = layout[0][1].get("children", []) if layout else []
        if len(children) == 1 and children[0][0].endswith(".focus"):
            children = children[0][1].get("children", [])
        return children

    def track_focus_source(self):
        """Show the focus ring on buttons only when focus came from the keyboard.

        ttk buttons take focus when clicked, so the amber ring used to stay on
        whatever was last clicked (a rail item, a tile's button) and read as a
        stuck selection. Like a Mac or a browser's :focus-visible, the ring
        now appears when someone moves with Tab or the arrow keys, and goes
        away once they use the mouse again. Text fields keep their ring
        always, since that shows where typing will go.
        """
        self._keyboard_focus = False

        def mark(widget):
            try:
                if isinstance(widget, (ttk.Button, ttk.Menubutton, ttk.Checkbutton, ttk.Radiobutton)):
                    widget.state(["user1" if self._keyboard_focus else "!user1"])
            except tk.TclError:
                pass

        def keyboard(_event=None):
            self._keyboard_focus = True
            self.after_idle(lambda: mark(self.focus_get()))

        def pointer(_event=None):
            self._keyboard_focus = False
            widget = self.focus_get()
            if widget is not None:
                mark(widget)

        # Tab moves focus through Tk's <<NextWindow>>/<<PrevWindow>> virtual
        # events; binding <Tab> itself on "all" would shadow them.
        for sequence in ("<<NextWindow>>", "<<PrevWindow>>", "<Up>", "<Down>", "<Left>", "<Right>"):
            try:
                self.bind_all(sequence, keyboard, add="+")
            except tk.TclError:
                pass
        # "<ButtonPress-1>" is listed on its own because a more specific
        # binding on the same tag (text selection uses one) hides the general one.
        for sequence in ("<ButtonPress>", "<ButtonPress-1>"):
            self.bind_all(sequence, pointer, add="+")
        for widget_class in ("TButton", "TMenubutton", "TCheckbutton", "TRadiobutton"):
            self.bind_class(widget_class, "<FocusIn>", lambda event: mark(event.widget), add="+")
            self.bind_class(widget_class, "<FocusOut>", lambda event: event.widget.state(["!user1"]) if hasattr(event.widget, "state") else None, add="+")

    def install_rounded_controls(self):
        if not hasattr(self, "_tile_cache"):
            self._tile_cache = {}
            self._style_generation = 0
            # Captured before any restyling: the rounded layouts replace only
            # the outer border element of these.
            self._clam_layouts = {name: self.style.layout(name) for name in ("TButton", "TMenubutton", "TEntry")}
            for widget_class in ("TButton", "TMenubutton", "TEntry"):
                self.bind_class(widget_class, "<Map>", self.fit_control_corners, add="+")
        # Element names can't be deleted, so a theme change starts a new
        # generation of names; tiles are cached by colour and reused.
        self._style_generation += 1
        self._rounded_elements = {}
        self._corner_styles = {}
        self._accent_styles = {}
        # style -> (widget class, fills, default surface)
        self._round_specs = dict(self.control_palettes())
        self._round_specs["TEntry"] = ("TEntry", (), COLORS["surface"])
        try:
            for style, (widget_class, fills, bg) in self._round_specs.items():
                self.round_style(style, widget_class, fills, bg)
        except (tk.TclError, IndexError, KeyError):
            self._round_specs = {}  # an unusual Tk: keep the flat controls
            return
        self.warm_corner_styles()

    def accent_button_style(self, color):
        """A rounded filled button style for any accent colour (green, violet...)."""
        if color == COLORS["primary"]:
            return "Primary.TButton"
        if color == COLORS["danger"]:
            return "Danger.TButton"
        style = self._accent_styles.get(color)
        if style:
            return style
        style = f"A{color.lstrip('#')}.Primary.TButton"
        hover = self.tint(color, -18)
        self.style.configure(style, foreground=self.on_color(color))
        self.style.map(style, foreground=[("disabled", COLORS["muted"]), ("active", self.on_color(hover))])
        fills = (color, hover, self.tint(color, -30))
        try:
            self.round_style(style, "TButton", fills, COLORS["surface"])
            self._round_specs[style] = ("TButton", fills, COLORS["surface"])
        except tk.TclError:
            self.style.configure(style, background=color)
        self._accent_styles[color] = style
        return style

    def surface_behind(self, widget):
        """The colour a control sits on (its nearest ancestor's background)."""
        parent = widget.master
        while parent is not None:
            try:
                if isinstance(parent, ttk.Widget):
                    style = str(parent.cget("style")) or parent.winfo_class()
                    color = self.style.lookup(style, "background")
                else:
                    color = parent.cget("bg")
                if color:
                    red, green, blue = (value // 257 for value in self.winfo_rgb(color))
                    return f"#{red:02x}{green:02x}{blue:02x}"
            except tk.TclError:
                pass
            parent = parent.master
        return COLORS["bg"]

    def fit_control_corners(self, event):
        """Give a rounded control tiles baked onto the surface it actually sits on."""
        widget = event.widget
        try:
            style = str(widget.cget("style")) or widget.winfo_class()
        except (tk.TclError, AttributeError):
            return
        base = style.split(".", 1)[1] if style.startswith("on") and "." in style else style
        spec = getattr(self, "_round_specs", {}).get(base)
        if not spec:
            return
        derived = self.corner_style(base, spec, self.surface_behind(widget))
        if derived != style:
            widget.configure(style=derived)

    def corner_style(self, base, spec, behind):
        """The style for a `base` control sitting on `behind`, made on first use."""
        widget_class, fills, default_bg = spec
        # A soft secondary button on a tinted card of almost the same colour
        # vanishes (e.g. surface_soft on alt); lift it to the card colour.
        # (Only the soft secondary styles; nav items match the rail on purpose.)
        liftable = base in ("TButton", "TMenubutton", "Select.TMenubutton", "Pill.TButton")
        blends_in = liftable and self.contrast(fills[0], behind) < 1.12
        if behind == default_bg.lower() and not blends_in:
            return base
        derived = f"on{behind.lstrip('#')}.{base}"
        if derived not in self._corner_styles:
            step = -10 if self.theme == "light" else 12
            if blends_in:
                lifted = COLORS["surface"] if self.contrast(COLORS["surface"], behind) >= 1.12 else COLORS["bg"]
                fills = (lifted, self.tint(lifted, step), self.tint(lifted, 2 * step))
            elif base == "Link.TButton":
                # Text buttons have no fill of their own: they take the surface.
                fills = (behind, self.tint(behind, step), self.tint(behind, 2 * step))
            try:
                self.round_style(derived, widget_class, fills, behind)
            except tk.TclError:
                self.set_corner_background(derived, behind)
            self._corner_styles[derived] = True
        return derived

    def warm_corner_styles(self):
        """Make the common control-on-card styles while the app is idle.

        Each one needs a few antialiased tiles worked out in Python, which
        the first visit to a page used to pay for (about half of opening
        Library the first time). One style per timer tick keeps it out of
        the way of clicks and typing.
        """
        generation = self._style_generation
        surfaces = [COLORS[name].lower() for name in ("alt", "bg", "surface", "warm") if name in COLORS]
        bases = ("TButton", "Primary.TButton", "Select.TMenubutton", "Pill.TButton", "PillOn.TButton", "TEntry")
        queue = [(base, behind) for behind in surfaces for base in bases if base in self._round_specs]

        def step():
            if generation != self._style_generation or not queue:
                return
            if time.perf_counter() - ScrollFrame.last_wheel_time < 0.5:
                # Each style takes about 10ms; wait until scrolling stops.
                self.after(200, step)
                return
            base, behind = queue.pop(0)
            try:
                self.corner_style(base, self._round_specs[base], behind)
            except (tk.TclError, KeyError):
                pass
            self.after(15, step)

        self.after(1200, step)

    def draw_chrome_icon(self, canvas, size):
        canvas.delete("all")
        if self.draw_memorypal_logo(canvas, size):
            return
        radius = max(4, size // 4)
        if not self.draw_antialiased_shape(canvas, size, size, COLORS["primary"], radius=radius, inset=1):
            canvas.create_rectangle(radius, 1, size - radius, size - 1, fill=COLORS["primary"], outline="")
            canvas.create_rectangle(1, radius, size - 1, size - radius, fill=COLORS["primary"], outline="")
            canvas.create_oval(1, 1, radius * 2, radius * 2, fill=COLORS["primary"], outline="")
            canvas.create_oval(size - radius * 2, 1, size - 1, radius * 2, fill=COLORS["primary"], outline="")
            canvas.create_oval(1, size - radius * 2, radius * 2, size - 1, fill=COLORS["primary"], outline="")
            canvas.create_oval(size - radius * 2, size - radius * 2, size - 1, size - 1, fill=COLORS["primary"], outline="")
        # The same lowercase "m" of two arches and amber dot as icon.py.
        ink = self.on_color(COLORS["primary"])
        stroke = max(2, int(size * 0.11))
        legs = [size * value for value in (0.27, 0.50, 0.73)]
        arch_y, bottom = size * 0.43, size * 0.71
        half = (legs[1] - legs[0]) / 2
        for leg in legs:
            canvas.create_line(leg, arch_y, leg, bottom, fill=ink, width=stroke, capstyle="round")
        for left in legs[:2]:
            canvas.create_arc(left, arch_y - half, left + 2 * half, arch_y + half, start=0, extent=180, style="arc", outline=ink, width=stroke)
        dot = size * 0.066
        canvas.create_oval(size * 0.775 - dot, size * 0.235 - dot, size * 0.775 + dot, size * 0.235 + dot, fill="#ffb020", outline="")

    def render_window_chrome(self, parent, title, close_command, window=None, show_minimize=True, show_fullscreen=True):
        window = window or self
        bar = tk.Frame(parent, bg=COLORS["surface_soft"])
        bar.pack(fill="x")
        grip = tk.Frame(bar, bg=COLORS["surface_soft"])
        grip.pack(side="left", fill="both", expand=True, padx=self.px(14))
        icon_size = self.px(22)
        dot = tk.Canvas(grip, width=icon_size, height=icon_size, bg=COLORS["surface_soft"], highlightthickness=0)
        dot.pack(side="left", padx=(0, self.px(10)))
        self.draw_chrome_icon(dot, icon_size)
        label = tk.Label(grip, text=title, bg=COLORS["surface_soft"], fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 10))
        label.pack(side="left")
        for widget in (bar, grip, label, dot):
            widget.bind("<ButtonPress-1>", lambda event, w=window: self.start_drag(event, w), add="+")
            widget.bind("<B1-Motion>", self.drag_window, add="+")
            widget.bind("<ButtonRelease-1>", self.stop_drag, add="+")

        controls = tk.Frame(bar, bg=COLORS["surface_soft"])
        controls.pack(side="right", padx=self.px(8), pady=self.px(6))

        def chrome_button(text, command, bg=None, fg=None, hint=""):
            symbol = {"value": text}
            # Even sizes with an even stroke put symbols exactly on the centre
            # line; odd combinations land half a pixel off.
            width = self.px(38) // 2 * 2
            height = self.px(30) // 2 * 2
            button = tk.Canvas(controls, width=width, height=height, bg=COLORS["surface_soft"], highlightthickness=0, cursor="hand2")
            button.pack(side="left", padx=self.px(2))

            def draw(hover=False):
                button.delete("all")
                fill = bg or (COLORS["alt"] if hover else COLORS["surface_soft"])
                text_color = fg or (COLORS["primary"] if hover else COLORS["muted"])
                if not self.draw_antialiased_shape(button, width, height, fill, radius=self.px(10)):
                    button.create_rectangle(0, 0, width, height, fill=fill, outline="")
                cx = width / 2
                cy = height / 2
                value = symbol["value"]
                # Draw the window controls geometrically instead of using font glyphs.
                # Font metrics make X/minimize/maximize symbols look subtly off-center
                # on different platforms and scaling levels.
                icon = {"\u00d7": "close", "\u2212": "minimize", "\u25a1": "maximize", "\u2750": "maximize"}.get(value)
                image = self.line_icon(icon, self.px(24), text_color) if icon else None
                if image is not None:
                    button.create_image(cx, cy, image=image, anchor="center")
                    button._memorypal_icon = image
                else:
                    self.create_centered_canvas_text(button, cx, cy, value, fill=text_color, font=self.font("Segoe UI Symbol", 12))

            def set_symbol(value):
                symbol["value"] = value
                draw()

            draw()
            button.set_symbol = set_symbol
            button.bind("<Button-1>", lambda _event: command())
            button.bind("<Enter>", lambda _event: draw(True), add="+")
            button.bind("<Leave>", lambda _event: draw(False), add="+")
            if hint:
                self.add_tooltip(button, hint)
            return button

        if show_minimize:
            chrome_button("\u2212", self.minimize_app, hint="Minimize")
        if show_fullscreen:
            self.chrome_fullscreen_button = chrome_button("\u2750" if self.is_focus_window else "\u25a1", self.toggle_focus_window, hint="Toggle borderless focus. Press " + ("Control-Command-F" if IS_MAC else "F11") + " for true fullscreen.")
        close = chrome_button("\u00d7", close_command, COLORS["danger"], COLORS["white"], "Close")
        return bar

    def ensure_nav_item_visible(self, key):
        """Every tab always shows, so this only moves the selection."""
        self.refresh_nav_selection(key)

    def tab_bar_height(self):
        return self.px(64)

    def render_navigation_rail(self, rail_width=None, preserve_cover=None):
        """The tab bar across the top of the window, like the phone's tabs.

        The logo sits on the left, the five sections in the middle, and
        Feedback on the right; Settings and the other tools stay in each
        page's header. (The method keeps its old name because every rebuild
        path calls it.)"""
        for child in self.rail.winfo_children():
            if child is preserve_cover:
                continue
            child.destroy()
        bar = self.rail
        bar.configure(style="TabBar.TFrame")
        self.layout_app_body()

        brand = tk.Frame(bar, bg=COLORS["bg"])
        brand.place(x=self.px(24), rely=0.5, anchor="w")
        mark_size = self.px(32)
        mark = tk.Canvas(brand, width=mark_size, height=mark_size, bg=COLORS["bg"], highlightthickness=0)
        mark.pack(side="left", padx=(0, self.px(10)))
        if not self.draw_memorypal_logo(mark, mark_size):
            self.draw_chrome_icon(mark, mark_size)
        self.tab_brand_label = tk.Label(brand, text="MemoryPal", bg=COLORS["bg"], fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 14))
        self.tab_brand_label.pack(side="left")

        tabs = tk.Frame(bar, bg=COLORS["bg"])
        tabs.place(relx=0.5, rely=0.5, anchor="center")
        self.nav_tabs_frame = tabs
        self.nav_buttons = {}
        for key, label, _short in self.rail_items():
            button = ttk.Button(tabs, text=label, style="TabBar.TButton", width=0, command=lambda view=key: self.show_view(view))
            self.set_nav_button_state(button, key, False)
            button.pack(side="left", padx=self.px(3))
            self.add_tooltip(button, self.nav_hint(key))
            self.nav_buttons[key] = button

        # Feedback sits apart from the sections while the app is in testing.
        self.nav_feedback_button = ttk.Button(bar, text="Feedback", style="TabBar.TButton", width=0, command=lambda: self.show_view("feedback"))
        self.set_nav_button_state(self.nav_feedback_button, "feedback", False)
        self.nav_feedback_button.place(relx=1.0, x=-self.px(24), rely=0.5, anchor="e")
        self.add_tooltip(self.nav_feedback_button, self.nav_hint("feedback"))
        self.nav_settings_button = None

        # A hairline where the bar meets the page, like a toolbar's edge.
        tk.Frame(bar, bg=COLORS["line"], height=max(1, self.px(1))).place(x=0, rely=1.0, relwidth=1, anchor="sw")
        bar.bind("<Configure>", self.fit_tab_bar, add="+")
        self.refresh_nav_selection(getattr(self, "current_view", "dashboard"))
        self.after_idle(self.fit_tab_bar)

    def fit_tab_bar(self, _event=None):
        """On a narrow window the brand name goes first, then the tab labels, so the tabs never overlap."""
        tabs = getattr(self, "nav_tabs_frame", None)
        brand = getattr(self, "tab_brand_label", None)
        if tabs is None or not tabs.winfo_exists():
            return
        try:
            width = self.rail.winfo_width()
            if width <= 1:
                return
            feedback = self.nav_feedback_button.winfo_reqwidth()
            side = self.px(24) * 2 + self.px(16)
            brand_w = self.px(32) + self.px(10) + (brand.winfo_reqwidth() if brand is not None else 0)
            compact = getattr(self, "_tabs_compact", False)
            full_tabs = getattr(self, "_tabs_full_width", 0) or tabs.winfo_reqwidth()
            if not compact:
                self._tabs_full_width = tabs.winfo_reqwidth()
                full_tabs = self._tabs_full_width
            # The tabs are centred, so each side needs room for the wider of
            # the brand and Feedback.
            room = width - 2 * (max(brand_w, feedback) + side)
            show_brand = room >= full_tabs
            if brand is not None and brand.winfo_exists():
                if show_brand and not brand.winfo_manager():
                    brand.pack(side="left")
                elif not show_brand and brand.winfo_manager():
                    brand.pack_forget()
            if not show_brand:
                room = width - 2 * (max(self.px(32), feedback) + side)
            want_compact = room < full_tabs
            if want_compact != compact:
                self._tabs_compact = want_compact
                for key, button in self.nav_buttons.items():
                    if button.winfo_exists():
                        # Icons only (with their names as tooltips) when even the
                        # brand-less bar can't fit the labels.
                        button.configure(compound="image" if want_compact else "left")
        except (AttributeError, tk.TclError):
            return

    def nav_icon_size(self):
        # A little taller than the 13pt label beside it, as in an Apple tab bar.
        return max(18, self.px(20))

    def set_nav_button_state(self, button, key, selected):
        """Selected/unselected look for a tab, icon included."""
        size = self.nav_icon_size()
        on = self.line_icon(key, size, COLORS["primary"])
        quiet = self.line_icon(key, size, COLORS["muted"])
        hover = self.line_icon(key, size, COLORS["ink"])
        options = {"style": "ActiveTabBar.TButton" if selected else "TabBar.TButton"}
        if on is not None and quiet is not None:
            # Hovering darkens the icon along with the label.
            options["image"] = (on,) if selected else (quiet, "active", hover)
            options["compound"] = "image" if getattr(self, "_tabs_compact", False) and key in getattr(self, "nav_buttons", {}) else "left"
        button.configure(**options)

    def refresh_nav_selection(self, current=None):
        if not hasattr(self, "nav_buttons"):
            return
        current = self.hub_for(current or self.current_view)
        buttons = dict(self.nav_buttons)
        for key in ("settings", "feedback"):
            pinned_button = getattr(self, f"nav_{key}_button", None)
            if pinned_button is not None:
                buttons[key] = pinned_button
        for key, button in buttons.items():
            if not button.winfo_exists():
                continue
            self.set_nav_button_state(button, key, key == current)

    def active_profile_number(self):
        profiles = list_profiles()
        active = active_profile_name()
        try:
            return profiles.index(active) + 1
        except ValueError:
            return 1

    def header_icon_button(self, parent, icon, command, hint="", size=38, active=False):
        pixel_size = self.px(size)
        try:
            base = parent.cget("bg") or COLORS["surface"]
        except tk.TclError:
            base = COLORS["surface"]
        canvas = tk.Canvas(
            parent,
            width=pixel_size,
            height=pixel_size,
            bg=base,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        canvas._memorypal_active = active

        def draw_line_icon(name, icon_color):
            # About half the button, like a symbol in an Apple toolbar button.
            image = self.line_icon(name, self.px(round(size * 0.52)), icon_color)
            if image is not None:
                canvas.create_image(pixel_size / 2, pixel_size / 2, image=image, anchor="center")

        def draw(hover=False):
            canvas.delete("all")
            is_active = bool(getattr(canvas, "_memorypal_active", active))
            # Nothing behind the symbol at rest; a soft tile only on hover or
            # when the button is "on", like a native toolbar.
            if hover or is_active:
                fill = self.tint(base, -10 if self.theme == "light" else 16)
                if not self.draw_antialiased_shape(canvas, pixel_size, pixel_size, fill, radius=self.px(10), inset=1):
                    canvas.create_rectangle(0, 0, pixel_size, pixel_size, fill=fill, outline="")
            ink = COLORS["primary"] if hover or is_active else COLORS["muted"]
            center = pixel_size / 2
            if icon == "theme":
                draw_line_icon("moon" if self.theme == "dark" else "sun", ink)
            elif icon in self.LINE_ICONS:
                draw_line_icon(icon, ink)
            else:
                self.create_centered_canvas_text(canvas, center, center, icon, fill=ink, font=self.font("Segoe UI Semibold", 13))

        draw()
        canvas.bind("<Button-1>", lambda _event: command())
        canvas.bind("<Enter>", lambda _event: draw(True), add="+")
        canvas.bind("<Leave>", lambda _event: draw(False), add="+")
        if hint:
            self.add_tooltip(canvas, hint)
        canvas.redraw_icon = draw
        canvas.set_active = lambda value: (setattr(canvas, "_memorypal_active", bool(value)), draw(False))
        return canvas

    def profile_avatar_button(self, parent):
        size = self.px(38)
        profile_number = str(min(self.active_profile_number(), 99))
        # Initials read as "this is me" at a glance; "P1" read as a code.
        words = [word for word in re.split(r"[\s_-]+", active_profile_name()) if word]
        profile_label = ("".join(word[0] for word in words[:2]) or profile_number).upper()
        try:
            base = parent.cget("bg") or COLORS["surface"]
        except tk.TclError:
            base = COLORS["surface"]
        button = tk.Canvas(
            parent,
            width=size,
            height=size,
            bg=base,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )

        def draw(hover=False):
            button.delete("all")
            if self.theme == "light":
                fill = self.tint(base, -16 if hover else -9)
            else:
                fill = self.tint(base, 22 if hover else 14)
            ink = COLORS["primary"] if hover else COLORS["ink"]
            if not self.draw_antialiased_shape(button, size, size, fill, radius=size // 2, inset=1):
                button.create_rectangle(0, 0, size, size, fill=fill, outline="")
            self.create_centered_canvas_text(
                button,
                size / 2,
                size / 2,
                profile_label,
                fill=ink,
                font=self.font("Segoe UI Semibold", 11 if len(profile_label) <= 3 else 10),
            )

        draw()
        button.bind("<Button-1>", lambda _event: self.open_profile_manager())
        button.bind("<Enter>", lambda _event: draw(True), add="+")
        button.bind("<Leave>", lambda _event: draw(False), add="+")
        self.add_tooltip(button, f"Profile {profile_number}: {active_profile_name()}. Click to switch or manage profiles.")
        return button

    def _shell(self):
        # The navigation rail stays expanded for a steadier desktop layout.
        root = ttk.Frame(self, style="Root.TFrame")
        root.pack(fill="both", expand=True)

        if self.use_native_window_chrome:
            self.app_chrome = None
        else:
            self.app_chrome = self.render_window_chrome(root, APP_NAME, close_command=self.destroy)

        self.app_body = ttk.Frame(root, style="Root.TFrame")
        self.app_body.pack(fill="both", expand=True)
        self.app_body.bind("<Configure>", self.layout_app_body, add="+")

        # The section tabs run across the top, like the phone's tab bar.
        self.rail = ttk.Frame(self.app_body, style="TabBar.TFrame")
        self.rail.place(x=0, y=0, relwidth=1, height=self.tab_bar_height())
        self.rail.pack_propagate(False)
        self.render_navigation_rail()

        self.main = ttk.Frame(self.app_body, style="Page.TFrame")
        self.main.place(x=0, y=self.tab_bar_height(), relwidth=1, height=1)
        top = ttk.Frame(self.main, style="Header.TFrame", padding=0)
        top.pack(fill="x", padx=self.px(36), pady=(self.px(22), self.px(16)))
        top.columnconfigure(0, weight=1)
        top.columnconfigure(1, weight=0)
        title_box = ttk.Frame(top, style="Header.TFrame")
        title_box.grid(row=0, column=0, sticky="ew")
        self.eyebrow = ttk.Label(title_box, text="Today", style="HeaderMuted.TLabel")
        self.eyebrow.pack(anchor="w")
        self.title_label = ttk.Label(title_box, text="Dashboard", style="PageTitle.TLabel")
        self.title_label.pack(anchor="w", fill="x")
        header_bg = COLORS["bg"]
        action_strip = tk.Frame(top, bg=header_bg)
        action_strip.grid(row=0, column=1, sticky="e", padx=(self.px(18), 0))
        # Streak, today's count and sync as one quiet line of text with
        # small symbols, not three coloured badges competing with the page.
        status_row = tk.Frame(top, bg=header_bg)
        status_row.grid(row=1, column=0, sticky="w", pady=(self.px(6), 0))
        status_font = self.font("Segoe UI", 11)
        streak = self.store.current_streak()
        streak_chip = tk.Label(status_row, text=f" {streak} day streak", bg=header_bg, fg=COLORS["muted"], padx=0, pady=self.px(2), font=status_font)
        self.set_chip_icon(streak_chip, "flame", COLORS["warm_text"])
        streak_chip.pack(side="left", padx=(0, self.px(18)))
        self.streak_chip = streak_chip
        today = self.store.today_count()
        goal_chip = tk.Label(status_row, text=f"{today} of {self.store.daily_goal} today", bg=header_bg, fg=COLORS["good_fg"] if today >= self.store.daily_goal else COLORS["muted"], padx=0, pady=self.px(2), font=status_font)
        goal_chip.pack(side="left", padx=(0, self.px(18)))
        self.goal_chip = goal_chip
        # Where sync stands, at a glance; clicking it opens Account & sync in Settings.
        self.sync_chip = tk.Label(status_row, text="", bg=header_bg, fg=COLORS["muted"], padx=0, pady=self.px(2), font=status_font, cursor="hand2")
        self.keyboard_link(self.sync_chip, lambda _event: self.show_view("settings"))
        self.add_tooltip(self.sync_chip, "Account & sync settings")
        self.refresh_sync_chip()
        back_button = self.header_icon_button(action_strip, "back", self.go_back, f"Back to the previous page ({BACK_SHORTCUT}).")
        back_button.pack(side="left", padx=(0, self.px(4)))
        find_button = self.header_icon_button(action_strip, "search", self.open_page_finder, f"Go to any page or action ({shortcut('K')}).")
        find_button.pack(side="left", padx=(0, self.px(4)))
        help_button = self.header_icon_button(action_strip, "help", self.start_tour, "Show me around: a short guided tour of the pages you use most.")
        help_button.pack(side="left", padx=(0, self.px(4)))
        theme_button = self.header_icon_button(action_strip, "theme", self.toggle_theme, "Switch between light and dark appearance.")
        theme_button.pack(side="left", padx=(0, self.px(4)))
        backup = self.header_icon_button(action_strip, "backup", self.export_data, "Export a local JSON backup of your MemoryPal data.")
        backup.pack(side="left", padx=(0, self.px(4)))
        settings_button = self.header_icon_button(action_strip, "settings", lambda: self.show_view("settings"), "Open Settings.")
        settings_button.pack(side="left", padx=(0, self.px(10)))
        profile_avatar = self.profile_avatar_button(action_strip)
        profile_avatar.pack(side="left")

        self.content = ttk.Frame(self.main, style="Page.TFrame")
        self.content.pack(fill="both", expand=True, padx=self.px(36), pady=(0, self.px(18)))
        self.toast_var = tk.StringVar()
        self.toast = tk.Label(self, textvariable=self.toast_var, bg=COLORS["rail"], fg=COLORS["white"], padx=self.px(20), pady=self.px(14), font=self.font("Segoe UI Semibold", 12))
        # Invisible grips along the window edge: the cursor shows where to
        # drag, so they need no grey strip or corner square of their own.
        right_grip = tk.Frame(self, bg=COLORS["bg"], cursor="sb_h_double_arrow")
        bottom_grip = tk.Frame(self, bg=COLORS["bg"], cursor="sb_v_double_arrow")
        corner_grip = tk.Frame(self, bg=COLORS["bg"], cursor="bottom_right_corner")
        self.resize_grips = [right_grip, bottom_grip, corner_grip]
        right_grip.bind("<ButtonPress-1>", lambda event: self.start_resize(event, "e"), add="+")
        bottom_grip.bind("<ButtonPress-1>", lambda event: self.start_resize(event, "s"), add="+")
        corner_grip.bind("<ButtonPress-1>", lambda event: self.start_resize(event, "se"), add="+")
        for grip in self.resize_grips:
            grip.bind("<B1-Motion>", self.resize_window, add="+")
            grip.bind("<ButtonRelease-1>", self.stop_resize, add="+")
        self.set_resize_grips_visible(not self.is_fullscreen and not self.use_native_window_chrome)
        self.after_idle(self.layout_app_body)

    def refresh_header_status(self):
        streak_chip = getattr(self, "streak_chip", None)
        if streak_chip is not None and streak_chip.winfo_exists():
            streak = self.store.current_streak()
            streak_chip.configure(text=f" {streak} day streak")
        chip = getattr(self, "goal_chip", None)
        if chip is None or not chip.winfo_exists():
            return
        today = self.store.today_count()
        met = today >= self.store.daily_goal
        chip.configure(
            text=f"{today} of {self.store.daily_goal} today",
            fg=COLORS["good_fg"] if met else COLORS["muted"],
        )

    def layout_app_body(self, event=None):
        if not hasattr(self, "app_body") or not self.app_body.winfo_exists():
            return
        if not hasattr(self, "rail") or not hasattr(self, "main"):
            return
        width = event.width if event is not None else self.app_body.winfo_width()
        height = event.height if event is not None else self.app_body.winfo_height()
        if width <= 1 or height <= 1:
            return
        bar = self.tab_bar_height()
        # place() adds relwidth/relheight to width/height, so clear the
        # relative sizes from the initial placement or both panels end up
        # larger than the window and their edges are clipped.
        self.rail.place_configure(x=0, y=0, width=width, height=bar, relwidth=0, relheight=0)
        self.main.place_configure(x=0, y=bar, width=width, height=max(1, height - bar), relwidth=0, relheight=0)

    def handle_window_configure(self, event):
        if event.widget is not self:
            return
        if event.width <= 1 or event.height <= 1:
            return
        # <Configure> also fires when the window is only moved; relayout only
        # on a real size change, and let the existing widgets reflow in place
        # rather than hiding the whole app behind a cover.
        size = (event.width, event.height)
        if size == getattr(self, "_last_window_size", None):
            return
        self._last_window_size = size
        self.after_idle(self.layout_app_body)

    def nav_hint(self, key):
        return {
            "dashboard": "Today's path from your study plan, your streak and level, and study modes.",
            "talkback": "Hands-free: each question is read aloud, you answer out loud, and you hear whether you were right.",
            "training": "Pick evidence-based study drills or gentle memory-support games.",
            "elder": "Large, calm memory support for routines, people, places, and caregiver-created prompts.",
            "decks": "Browse your decks, see per-deck mastery, and study one deck at a time.",
            "plan": "Answer a few questions and get a tailored study plan for today.",
            "stats": "Charts of your practice, what's coming up, card maturity, and achievements.",
            "focus": "A queue of due, weak and new cards to work through.",
            "capture": "Name a set, then type questions and answers or paste notes to turn into cards.",
            "review": "Go through the cards that are due today, one at a time.",
            "testing": "Answer, reveal, let Smart Check compare, then rate how it went.",
            "quiz": "Self-check or multiple choice practice.",
            "shuffle": "Structured repetition path such as 5, 5-4, 5-4-3, 3-2-1.",
            "tools": "Turn lists into acronyms and mini-stories that are easier to recall.",
            "cuelab": "Generate text, image, and audio cues for any card.",
            "games": "Short recall games for attention and memory.",
            "library": "Search, filter, import, export, and review saved material.",
            "feedback": "Rate the app, report a problem, or suggest an idea.",
            "settings": "Personalize appearance, profiles, storage, backups, and focus behavior.",
            "study": "Every way to practise your cards: due review, focus, quizzes and repetition.",
            "create": "Add things to learn, organise decks, browse the library and make cues.",
            "practice": "Memory techniques, everyday memory support, associations and puzzles.",
        }.get(key, "")

    def page_titles(self):
        """(section, title) shown above each page."""
        return {
            "dashboard": ("Today", "Dashboard"), "training": ("Practice", "Memory Gym"),
            "elder": ("Practice", "Everyday Memory"), "decks": ("Create", "Decks"),
            "plan": ("Today", "Study Plan"), "stats": ("Progress", "Stats & Streaks"),
            "focus": ("Study", "Focus Session"), "capture": ("Create", "New study set"),
            "review": ("Study", "Spaced Review"), "testing": ("Study", "Test Lab"),
            "quiz": ("Study", "Quick Quiz"), "talkback": ("Study", "Talk-back study"), "shuffle": ("Study", "Repetition Path"),
            "tools": ("Practice", "Associations"), "cuelab": ("Create", "Cue Lab"),
            "games": ("Practice", "Puzzles"), "library": ("Create", "Library"),
            "feedback": ("Help us improve", "Send Feedback"), "settings": ("Personalize", "Settings"),
            "welcome": ("Welcome", "Let's set things up"),
            "signin": ("Welcome", "Sign in"),
            "study": ("Study", "Ways to study"), "create": ("Create", "Make and organise"),
            "practice": ("Practice", "Practise and play"),
        }

    def show_view(self, view, transition=False):
        """Switch pages behind a skeleton of the new page.

        The placeholder goes up at once, the real page is built out of sight
        beneath it, and it comes off with painting paused, so the finished page
        appears in one pass. Re-showing the current page is an in-place
        update and still uses the snapshot swap.
        """
        if getattr(self, "_hidden_active", False) or getattr(self, "_building_view", False):
            self._show_view_now(view)
            return
        skeleton = self.show_page_skeleton(view) if self.wants_skeleton(view) else None
        if skeleton is None:
            # Re-showing the same page (or the welcome page): an in-place
            # update, built under the snapshot like other in-page changes.
            self.run_hidden_change(lambda: self._show_view_now(view))
            return
        # A real page change: the skeleton is already on screen, so the page
        # is built underneath it (out of sight) with no snapshot, then the
        # skeleton comes off with painting paused, so the finished page is
        # drawn in one pass rather than widget by widget.
        try:
            self._show_view_now(view)
        finally:
            frozen = self.set_redraw_frozen(True)
            try:
                if skeleton.winfo_exists():
                    skeleton.destroy()
                self.settle_layout()
            finally:
                if frozen:
                    self.set_redraw_frozen(False)
                flush_pending_paint(self)

    # The placeholder layout each page shows while it is built (default "grid").
    SKELETON_PAGES = {
        "library": "list", "decks": "list", "settings": "list", "feedback": "list", "capture": "list",
        "stats": "grid", "dashboard": "grid", "training": "grid", "games": "grid", "elder": "grid", "tools": "grid",
        "focus": "study", "review": "study", "talkback": "study", "quiz": "study", "testing": "study", "shuffle": "study",
        "cuelab": "study", "plan": "study",
    }

    def wants_skeleton(self, view):
        """Every page change shows a skeleton, so all of them look and feel the same."""
        if view == getattr(self, "current_view", None) or view in ("welcome", "signin"):
            return False
        return hasattr(self, "content") and not getattr(self, "tour", None)

    def show_page_skeleton(self, view):
        """Paint a placeholder of the page's layout at once, before building it.

        The page itself still takes a moment to build; the skeleton is on
        screen during that time so a click answers immediately instead of
        the old page sitting still. The real page then replaces it in one
        frame (the build runs under run_hidden_change).
        """
        try:
            width, height = self.content.winfo_width(), self.content.winfo_height()
            if width < 40 or height < 40:
                return None
            canvas = tk.Canvas(self.content, bg=COLORS["bg"], highlightthickness=0, bd=0, takefocus=0)
            canvas.place(x=0, y=0, relwidth=1, relheight=1)
            self.tk.call("raise", canvas._w)  # Canvas.lift() raises canvas items, not the widget
            self.draw_page_skeleton(canvas, self.SKELETON_PAGES.get(view, "grid"), width, height)
            section, title = self.page_titles().get(view, ("", ""))
            self.eyebrow.configure(text=section)
            self.title_label.configure(text=title)
            self.refresh_nav_selection(view)
            self.update_idletasks()
            flush_pending_paint(self)
            return canvas
        except (tk.TclError, AttributeError):
            return None

    def draw_page_skeleton(self, canvas, kind, width, height):
        card = COLORS["surface"]
        bar = self.tint(card, -7 if self.theme == "light" else 9)
        radius, gap = self.px(14), self.px(16)
        pad = self.px(22)

        page_bg = canvas.cget("bg")

        def block(x1, y1, x2, y2, fill, r=radius):
            # Two rectangles plus four antialiased corners: a smoothed polygon
            # has jagged, slightly lumpy corners on Windows.
            r = max(1, min(r, (x2 - x1) // 2, (y2 - y1) // 2))
            under = card if fill == bar else page_bg
            canvas.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill, outline="")
            canvas.create_rectangle(x1, y1 + r, x2, y2 - r, fill=fill, outline="")
            for corner, x, y in (("nw", x1, y1), ("ne", x2 - r, y1), ("sw", x1, y2 - r), ("se", x2 - r, y2 - r)):
                image = self.corner_photo(r, fill, under, corner)
                if image is None:
                    canvas.create_rectangle(x, y, x + r, y + r, fill=fill, outline="")
                else:
                    canvas.create_image(x, y, image=image, anchor="nw")

        def lines(x1, y1, x2, count=2):
            span = x2 - x1
            for index, share in enumerate((0.42, 0.78, 0.6)[:count]):
                top = y1 + index * self.px(22)
                block(x1, top, x1 + int(span * share), top + self.px(10), bar, self.px(5))

        right = width - self.px(8)
        y = 0
        if kind == "list":
            # A search/filter row, a row of buttons, then the list of cards.
            control = self.px(40)
            block(0, y, int(right * 0.6), y + control, card, self.px(9))
            block(int(right * 0.6) + gap, y, right, y + control, card, self.px(9))
            y += control + self.px(12)
            third = (right - 2 * gap) // 3
            for index in range(3):
                x = index * (third + gap)
                block(x, y, x + third, y + control, card, self.px(9))
            y += control + gap
            row = self.px(104)
            while y < height:
                block(0, y, right, y + row, card)
                lines(pad, y + pad, right - pad, 3)
                y += row + gap
        elif kind == "study":
            # One large working card (the question or the session), a row of
            # buttons under it, then a smaller card.
            big = max(self.px(200), int(height * 0.48))
            block(0, y, right, y + big, card)
            lines(pad, y + pad, right - pad, 3)
            y += big + gap
            control = self.px(40)
            quarter = (right - 3 * gap) // 4
            for index in range(4):
                x = index * (quarter + gap)
                block(x, y, x + quarter, y + control, card, self.px(9))
            y += control + gap
            while y < height:
                block(0, y, right, y + self.px(140), card)
                lines(pad, y + pad, right - pad, 2)
                y += self.px(140) + gap
        else:
            tiles = 4 if width > self.px(900) else 2
            tile_w = (right - gap * (tiles - 1)) // tiles
            tile_h = self.px(112)
            for index in range(tiles):
                x = index * (tile_w + gap)
                block(x, y, x + tile_w, y + tile_h, card)
                lines(x + pad, y + pad, x + tile_w - pad, 2)
            y += tile_h + gap
            half = (right - gap) // 2
            big = max(self.px(160), (height - y - gap) // 2)
            while y < height:
                block(0, y, half, y + big, card)
                lines(pad, y + pad, half - pad, 3)
                block(half + gap, y, right, y + big, card)
                lines(half + gap + pad, y + pad, right - pad, 3)
                y += big + gap

    def _show_view_now(self, view):
        # The small line above each title names the part of the app the page
        # belongs to (Today, Study, Create, Practice, Progress), so people can
        # tell where they are without reading the rail.
        titles = self.page_titles()
        self.stop_talkback()
        self.stop_speaking()
        self.audio_player.stop()
        self.clear_text_selection()
        self.close_page_finder()
        if self.current_view != view:
            self.save_current_draft()
            previous = self.current_view
            history = self.__dict__.setdefault("view_history", [])
            if previous and previous not in ("welcome", "signin") and not getattr(self, "_going_back", False):
                history.append(previous)
                del history[:-40]
        self.clear_rating_hotkeys()
        self.route_token += 1
        token = self.route_token
        old_host = getattr(self, "view_host", None)
        # Rebuilding the page already on screen (a sync brought changes, a
        # setting changed) keeps its scroll position instead of jumping to the top.
        keep_scroll = self.page_scroll_offset(old_host) if view == self.current_view else None
        self.current_view = view
        self.refresh_nav_selection()

        # Build the new page underneath the current one instead of blanking
        # the content area: the old page stays on screen (and the rail and
        # header never change) until the new page is fully laid out, then the
        # old one is removed to reveal it in a single step.
        new_host = ttk.Frame(self.content, style="Page.TFrame")
        new_host.place(relx=0, rely=0, relwidth=1, relheight=1)
        if old_host is not None and old_host.winfo_exists():
            try:
                self.tk.call("lower", new_host._w, old_host._w)
            except tk.TclError:
                pass
        self.view_host = new_host
        try:
            self._building_view = True
            try:
                getattr(self, f"view_{view}")()
            finally:
                self._building_view = False
            # Fixed wrap widths clip text on narrow windows and at larger text
            # sizes; make every wrapped label on the page fit its real width.
            self.fit_wrap_tree(new_host)
            self.update_idletasks()
        except Exception:
            if new_host.winfo_exists():
                new_host.destroy()
            self.view_host = old_host
            raise
        if token != self.route_token:
            # The view redirected to another page while building; that newer
            # call has already swapped itself in.
            if new_host.winfo_exists():
                new_host.destroy()
            if old_host is not None and old_host.winfo_exists() and old_host is not self.view_host:
                old_host.destroy()
            return
        self.refresh_header_status()
        self.eyebrow.configure(text=titles[view][0])
        self.title_label.configure(text=titles[view][1])
        if keep_scroll:
            self.restore_page_scroll(new_host, keep_scroll)
        if old_host is not None and old_host.winfo_exists() and old_host is not new_host:
            old_host.destroy()
        self.update_idletasks()
        self.after_idle(self.layout_app_body)
        if getattr(self, "tour", None):
            self.render_tour_card()

    @staticmethod
    def page_scrollframe(host):
        """The main scrolling area of a page, or None."""
        queue = [host] if host is not None else []
        while queue:
            widget = queue.pop(0)
            if isinstance(widget, ScrollFrame):
                return widget
            try:
                queue.extend(widget.winfo_children())
            except tk.TclError:
                pass
        return None

    def page_scroll_offset(self, host):
        page = self.page_scrollframe(host)
        if page is None or not page.winfo_exists():
            return None
        position = page._scroll_position("y")
        return position[0] if position else None

    def restore_page_scroll(self, host, offset):
        page = self.page_scrollframe(host)
        if page is None:
            return
        try:
            page.refresh_scrollregion()
        except tk.TclError:
            return
        page.scroll_to_offsets(y=offset)

    def go_back(self):
        history = getattr(self, "view_history", [])
        while history:
            view = history.pop()
            if view != self.current_view and hasattr(self, f"view_{view}"):
                self._going_back = True
                try:
                    self.show_view(view)
                finally:
                    self._going_back = False
                return
        self.toast_message("You're at the start. Nothing to go back to.")

    def finder_entries(self):
        entries = [(label, self.nav_hint(key), lambda key=key: self.show_view(key)) for key, label, _short in self.rail_items()]
        entries += [(label, self.nav_hint(key), lambda key=key: self.show_view(key)) for key, label, _short in self.ordered_nav_items()]
        entries.append(("Settings", self.nav_hint("settings"), lambda: self.show_view("settings")))
        entries += [
            ("Quick 10-minute session", "Ten focused minutes on whatever matters most right now.", self.quick_session),
            ("Start today's review", "Go through the cards that are due now.", lambda: self.show_view("review")),
            ("Make a study plan", "Choose your time and goal and get a step-by-step path.", lambda: self.show_view("plan")),
            ("Take the guided tour", "A short walk through the pages you use most.", self.start_tour),
            ("Switch light / dark", "Change the app's appearance.", self.toggle_theme),
            ("Go back", f"Return to the page you were on before ({BACK_SHORTCUT}).", self.go_back),
        ]
        return entries

    def close_page_finder(self):
        finder = getattr(self, "_finder", None)
        self._finder = None
        if finder is None:
            return
        try:
            finder.grab_release()
            finder.destroy()
        except tk.TclError:
            pass

    def open_page_finder(self, _event=None):
        """Ctrl+K (Command-K on a Mac): type part of a page or action name and press Enter."""
        self.close_dropdown()
        if getattr(self, "_finder", None) is not None:
            self.close_page_finder()
            return "break"
        entries = self.finder_entries()
        top = tk.Toplevel(self)
        top.withdraw()
        top.overrideredirect(True)
        top.configure(bg=COLORS["surface_soft"])
        self.own_window(top, self)
        self._finder = top
        box = tk.Frame(top, bg=COLORS["surface_soft"], padx=self.px(16), pady=self.px(14))
        box.pack(fill="both", expand=True)
        tk.Label(box, text="Go to a page or action", bg=COLORS["surface_soft"], fg=COLORS["muted"], font=self.font("Segoe UI Semibold", 10)).pack(anchor="w", pady=(0, self.px(6)))
        query = tk.StringVar()
        entry = ttk.Entry(box, textvariable=query, font=self.font("Segoe UI", 13))
        entry.pack(fill="x")
        listbox = tk.Listbox(
            box, height=9, bg=COLORS["surface_soft"], fg=COLORS["ink"], selectbackground=COLORS["primary"], selectforeground=self.on_color(COLORS["primary"]),
            relief="flat", bd=0, highlightthickness=0, activestyle="none", font=self.font("Segoe UI", 12), exportselection=False, cursor="hand2",
        )
        listbox.pack(fill="both", expand=True, pady=(self.px(10), self.px(6)))
        detail = tk.Label(box, text="", bg=COLORS["surface_soft"], fg=COLORS["muted"], font=self.font("Segoe UI", 10), anchor="w", justify="left", wraplength=self.px(520))
        self.fit_wrap(detail)
        tk.Label(box, text="\u2191 \u2193 to move  \u2022  Enter to open  \u2022  Esc to close", bg=COLORS["surface_soft"], fg=COLORS["muted"], font=self.font("Segoe UI", 9)).pack(anchor="w", pady=(self.px(8), 0))
        shown = []

        def select(index):
            if not shown:
                detail.configure(text="No match. Try another word.")
                return
            index = max(0, min(len(shown) - 1, index))
            listbox.selection_clear(0, "end")
            listbox.selection_set(index)
            listbox.see(index)
            detail.configure(text=shown[index][1])

        def refresh(*_args):
            words = query.get().lower().split()
            shown[:] = [item for item in entries if all(word in f"{item[0]} {item[1]}".lower() for word in words)]
            listbox.delete(0, "end")
            for label, _hint, _action in shown:
                listbox.insert("end", f"  {label}")
            select(0)

        def current():
            picked = listbox.curselection()
            return picked[0] if picked else 0

        def choose(_event=None):
            if not shown:
                return "break"
            action = shown[current()][2]
            self.close_page_finder()
            action()
            return "break"

        def press(event):
            inside = 0 <= event.x_root - top.winfo_rootx() < top.winfo_width() and 0 <= event.y_root - top.winfo_rooty() < top.winfo_height()
            if not inside:
                self.close_page_finder()
                return "break"
            return None

        query.trace_add("write", refresh)
        entry.bind("<Down>", lambda _event: (select(current() + 1), "break")[1])
        entry.bind("<Up>", lambda _event: (select(current() - 1), "break")[1])
        entry.bind("<Return>", choose)
        top.bind("<Escape>", lambda _event: (self.close_page_finder(), "break")[1])
        listbox.bind("<Motion>", lambda event: select(listbox.nearest(event.y)))
        listbox.bind("<ButtonRelease-1>", choose)
        top.bind("<ButtonPress-1>", press)
        refresh()

        measure = tkfont.Font(root=self, font=self.font("Segoe UI", 12))
        longest = max((measure.measure(f"  {label}") for label, _hint, _action in entries), default=0)
        width = max(self.px(600), longest + self.px(32) + self.px(24))
        top.update_idletasks()
        height = top.winfo_reqheight()
        anchor = getattr(self, "main", self)
        left, s_top, right, bottom = self.screen_bounds(anchor)
        margin = self.px(8)
        width = min(width, right - left - margin * 2)
        height = min(height, bottom - s_top - margin * 2)
        x = anchor.winfo_rootx() + (anchor.winfo_width() - width) // 2
        y = anchor.winfo_rooty() + self.px(70)
        x = max(left + margin, min(x, right - margin - width))
        y = max(s_top + margin, min(y, bottom - margin - height))
        top.geometry(f"{width}x{height}+{x}+{y}")
        self.reveal_window(top)
        entry.focus_force()
        try:
            top.grab_set()
        except tk.TclError:
            pass
        return "break"

    def register_draft_saver(self, view, saver):
        self.draft_savers[view] = saver

    def save_current_draft(self):
        saver = self.draft_savers.get(self.current_view)
        if not saver:
            return
        try:
            self.view_drafts[self.current_view] = saver()
        except tk.TclError:
            pass

    def edit_daily_goal(self):
        goal = self.dialog_integer("Daily goal", "Cards to review per day:", initial=self.store.daily_goal, minvalue=1, maxvalue=500)
        if goal:
            self.store.daily_goal = goal
            self.store.save()
            self.refresh_header_status()
            self.show_view(self.current_view)

    def switch_profile(self, name, force=False):
        if not force and name == active_profile_name():
            return
        self.save_current_draft()
        switch_active_profile_paths(name)
        self.store = MemoryStore()
        self.init_cloud()  # each profile has its own account link
        self.accessibility = normalize_accessibility(self.store.accessibility)
        self.apply_accessibility_preferences()
        self.deck_filter = None
        self.view_drafts = {}
        self.title(f"{APP_NAME} \u2014 {active_profile_name()}")
        self.tour = None
        self.rebuild_shell(self.start_view())
        self.toast_message(f"Switched to {name}.")

    def open_profile_manager(self):
        top = tk.Toplevel(self)
        top.withdraw()
        self.make_dialog_frame(top)
        top.title("Profiles")
        top.configure(bg=COLORS["bg"])
        self.apply_app_icon(top)
        self.own_window(top, self)
        top.minsize(self.px(360), self.px(360))

        shell = tk.Frame(top, bg=COLORS["bg"])
        shell.pack(fill="both", expand=True)
        if not self.use_native_window_chrome:
            self.render_window_chrome(shell, "Profiles", top.destroy, window=top, show_minimize=False, show_fullscreen=False)

        wrap = tk.Frame(shell, bg=COLORS["bg"], padx=self.px(20), pady=self.px(20))
        wrap.pack(fill="both", expand=True)
        tk.Label(wrap, text="Profiles", bg=COLORS["bg"], fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 20)).pack(anchor="w")
        self.fit_wrap(tk.Label(wrap, text="Each profile keeps its own decks, stats, and streak. Sign each one in to a different account to keep them apart in the cloud too.", bg=COLORS["bg"], fg=COLORS["muted"], font=self.font("Segoe UI", 11), wraplength=self.px(380), justify="left"), pady=(4, 16))

        list_holder = tk.Frame(wrap, bg=COLORS["bg"])
        list_holder.pack(fill="both", expand=True)

        @self.smooth
        def render_list():
            for child in list_holder.winfo_children():
                child.destroy()
            active = active_profile_name()
            for name in list_profiles():
                row = tk.Frame(list_holder, bg=COLORS["surface"], padx=self.px(14), pady=self.px(12))
                row.pack(fill="x", pady=(0, 8))
                label_text = name + ("  (active)" if name == active else "")
                button_area = tk.Frame(row, bg=COLORS["surface"])
                button_area.pack(side="right")
                # Packed after the buttons so a long name wraps instead of
                # pushing them out of the window.
                name_label = tk.Label(row, text=label_text, bg=COLORS["surface"], fg=(COLORS["primary"] if name == active else COLORS["ink"]), font=self.font("Segoe UI Semibold", 12), anchor="w", justify="left", wraplength=self.px(160))
                name_label.pack(side="left", fill="x", expand=True)
                self.bind_rewrap(name_label)
                # The app's own rounded buttons, like every other dialog.
                if name != active:
                    ttk.Button(button_area, text="Switch", style="Primary.TButton", cursor="hand2", command=lambda n=name: (top.destroy(), self.switch_profile(n))).pack(side="left", padx=(0, self.px(6)))
                ttk.Button(button_area, text="Rename", cursor="hand2", command=lambda n=name: do_rename(n)).pack(side="left", padx=(0, self.px(6)))
                if len(list_profiles()) > 1:
                    ttk.Button(button_area, text="Delete", cursor="hand2", command=lambda n=name: do_delete(n)).pack(side="left")

        def do_rename(name):
            new_name = self.dialog_text("Rename profile", f"New name for \"{name}\":", initial=name, parent=top)
            if new_name is None:
                return
            was_active = name == active_profile_name()
            ok, error = rename_profile(name, new_name)
            if not ok:
                self.dialog_alert("Rename failed", error, "error", parent=top)
                return
            if was_active:
                switch_active_profile_paths(new_name)
                top.destroy()
                self.title(f"{APP_NAME} \u2014 {new_name}")
                self.rebuild_shell(self.current_view)
                return
            render_list()

        def do_delete(name):
            if not self.dialog_confirm("Delete profile", f"Delete \"{name}\" and everything in it? This can't be undone.", "Delete profile", parent=top, destructive=True):
                return
            was_active = name == active_profile_name()
            leaving = self.account if was_active else cloud.Account(app_paths.profile_dir(name))
            ok, error = delete_profile(name)
            if not ok:
                self.dialog_alert("Delete failed", error, "error", parent=top)
                return
            if leaving.signed_in:
                # End its sign-in on the server too, not just the copy on disk.
                self.run_in_background(leaving.sign_out, lambda _result, _error: None)
            render_list()
            if was_active:
                top.destroy()
                self.switch_profile(active_profile_name(), force=True)

        def do_create():
            new_name = self.dialog_text("New profile", "Profile name:", parent=top)
            if new_name is None:
                return
            ok, error = create_profile(new_name)
            if not ok:
                self.dialog_alert("Couldn't create profile", error, "error", parent=top)
                return
            # Open the new profile right away so its welcome page can set it up.
            top.destroy()
            self.switch_profile(normalize_profile_name(new_name))

        render_list()
        ttk.Button(wrap, text="New profile", style="Primary.TButton", cursor="hand2", command=do_create).pack(fill="x", pady=(self.px(12), 0))
        ttk.Button(wrap, text="Close", cursor="hand2", command=top.destroy).pack(fill="x", pady=(self.px(8), 0))
        top.bind("<Escape>", lambda _event: top.destroy())
        self.show_popup_window(top, self, self.px(440), self.px(420))

    def toggle_theme(self):
        self.save_current_draft()
        self.theme = "dark" if self.theme == "light" else "light"
        self.apply_theme_palette()
        self.rebuild_shell(self.current_view, refresh_styles=True)

    def clear_rating_hotkeys(self):
        if not self._hotkeys_bound:
            return
        for seq in ("1", "2", "3", "4", f"<{MOD}-z>", f"<{MOD}-Z>"):
            try:
                self.unbind(f"<Key-{seq}>" if len(seq) == 1 else seq)
            except tk.TclError:
                pass
        self._hotkeys_bound = False

    def bind_rating_hotkeys(self, handler, undo_handler=None):
        self.clear_rating_hotkeys()
        mapping = {"1": 1, "2": 3, "3": 4, "4": 5}
        for seq, quality in mapping.items():
            self.bind(f"<Key-{seq}>", lambda _event, value=quality: handler(value))
        if undo_handler:
            self.bind(f"<{MOD}-z>", lambda _event: undo_handler())
            self.bind(f"<{MOD}-Z>", lambda _event: undo_handler())
        self._hotkeys_bound = True

    def toast_message(self, text):
        self.toast_var.set(text)
        room = max(self.px(200), self.winfo_width() - self.px(48))
        self.toast.configure(wraplength=min(self.px(520), room), justify="left")
        self.toast.place(relx=1, rely=1, anchor="se", x=-self.px(24), y=-self.px(24))
        pending = getattr(self, "_toast_after", None)
        if pending is not None:
            try:
                self.after_cancel(pending)
            except tk.TclError:
                pass
        self._toast_after = self.after(self.pace(2600), self.toast.place_forget)

    def make_dialog_frame(self, top):
        """Give a titled popup the platform's frame.

        On Windows the app draws its own title bar, so popups are borderless
        and draw the same bar. A Mac keeps the native frame, with the close
        button top-left where Mac people look for it, like the main window.
        """
        if not self.use_native_window_chrome:
            top.overrideredirect(True)

    def dialog_window(self, title, body="", parent=None, width=480):
        # MemoryPal uses its own small modal surface so prompts, warnings, and
        # confirmations do not fall back to old stock Tk dialog boxes.
        owner = parent or self
        top = tk.Toplevel(owner)
        top.withdraw()
        self.make_dialog_frame(top)
        top.title(title)
        top.configure(bg=COLORS["bg"])
        self.apply_app_icon(top)
        self.own_window(top, owner)
        top.resizable(False, False)
        top.configure(bg=COLORS["surface"])
        if not self.use_native_window_chrome:
            self.render_window_chrome(top, title, top.destroy, window=top, show_minimize=False, show_fullscreen=False)
        shell = tk.Frame(top, bg=COLORS["surface"], padx=self.px(22), pady=self.px(18))
        shell.pack(fill="both", expand=True)
        if body:
            body_label = tk.Label(shell, text=body, bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI", 11), wraplength=self.px(width - 70), justify="left", anchor="w")
            self.fit_wrap(body_label, pady=(self.px(6), self.px(14)))
        content = ttk.Frame(shell, style="Card.TFrame")
        content.pack(fill="x")
        actions = ttk.Frame(shell, style="Card.TFrame")
        actions.pack(fill="x", pady=(self.px(18), 0))
        top.dialog_owner = owner
        top.dialog_width = self.px(width)
        return top, content, actions

    def present_dialog(self, top):
        # Shown only once its fields and buttons exist, so the height fits them.
        self.show_popup_window(top, top.dialog_owner, top.dialog_width, modal=True)

    def dialog_alert(self, title, body, kind="info", parent=None):
        top, _content, actions = self.dialog_window(title, body, parent=parent)
        color = COLORS["danger"] if kind == "error" else COLORS["primary"]
        ok = self.solid_button(actions, "OK", top.destroy, color)
        ok.pack(fill="x")
        self.present_dialog(top)
        top.bind("<Return>", lambda _event: top.destroy())
        top.bind("<Escape>", lambda _event: top.destroy())
        ok.focus_set()
        top.wait_window()

    def dialog_confirm(self, title, body, confirm_text="Continue", parent=None, destructive=False):
        result = {"value": False}
        top, _content, actions = self.dialog_window(title, body, parent=parent)

        def finish(value):
            result["value"] = value
            top.destroy()

        cancel = ttk.Button(actions, text="Cancel", command=lambda: finish(False))
        cancel.grid(row=0, column=0, sticky="ew", padx=(0, self.px(8)))
        confirm = self.solid_button(actions, confirm_text, lambda: finish(True), COLORS["danger"] if destructive else COLORS["primary"])
        confirm.grid(row=0, column=1, sticky="ew")
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)
        self.present_dialog(top)
        top.bind("<Escape>", lambda _event: finish(False))
        confirm.focus_set()
        top.wait_window()
        return result["value"]

    def dialog_choice(self, title, body, options, parent=None):
        """Ask with several answers, stacked: options are (value, label); the
        first is the main one and the last is the way out (also Escape)."""
        result = {"value": options[-1][0]}
        top, _content, actions = self.dialog_window(title, body, parent=parent, width=520)

        def finish(value):
            result["value"] = value
            top.destroy()

        first = None
        for index, (value, label) in enumerate(options):
            if index == 0:
                button = self.solid_button(actions, label, lambda v=value: finish(v), COLORS["primary"])
                first = button
            else:
                button = ttk.Button(actions, text=label, command=lambda v=value: finish(v))
            button.pack(fill="x", pady=(0 if index == 0 else self.px(8), 0))
        self.present_dialog(top)
        top.bind("<Escape>", lambda _event: finish(options[-1][0]))
        if first is not None:
            first.focus_set()
        top.wait_window()
        return result["value"]

    def dialog_text(self, title, body, initial="", parent=None, required=True):
        result = {"value": None}
        top, content, actions = self.dialog_window(title, body, parent=parent)
        entry = ttk.Entry(content)
        entry.insert(0, initial or "")
        entry.pack(fill="x")
        error = tk.Label(content, text="", bg=COLORS["surface"], fg=COLORS["again_fg"], font=self.font("Segoe UI", 10), anchor="w")
        error.pack(fill="x", pady=(self.px(6), 0))

        def submit():
            value = normalize_space(entry.get())
            if required and not value:
                error.configure(text="This field cannot be empty.")
                return
            result["value"] = value
            top.destroy()

        cancel = ttk.Button(actions, text="Cancel", command=top.destroy)
        cancel.grid(row=0, column=0, sticky="ew", padx=(0, self.px(8)))
        save = self.solid_button(actions, "Save", submit, COLORS["primary"])
        save.grid(row=0, column=1, sticky="ew")
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)
        self.present_dialog(top)
        top.bind("<Return>", lambda _event: submit())
        top.bind("<Escape>", lambda _event: top.destroy())
        entry.focus_set()
        entry.selection_range(0, "end")
        top.wait_window()
        return result["value"]

    def open_card_editor(self, card, on_done=None):
        """Edit a card's words, deck and memory hook, or delete it.

        Fixing a confusing card is the main cure for a card that keeps being
        missed (a "leech"), so this is reachable from every card in Library.
        """
        top, content, actions = self.dialog_window("Edit card", "Change the words on this card. Its review schedule stays the same.", width=620)
        fields = {}

        def field(label, name, value, lines=1):
            tk.Label(content, text=label, bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI Semibold", 10), anchor="w").pack(fill="x", pady=(self.px(8), self.px(4)))
            if lines == 1:
                widget = ttk.Entry(content)
                widget.insert(0, value or "")
            else:
                widget = self.text_box(content, height=lines, font_size=11)
                widget.insert("1.0", value or "")
            widget.pack(fill="x")
            fields[name] = widget

        field("Deck", "deck", card.deck)
        field("Question or prompt", "front", card.front, lines=2)
        field("Answer (leave empty for a self-check card)", "back", card.back, lines=3)
        field("Memory hook (optional)", "association", card.association, lines=2)
        error = tk.Label(content, text="", bg=COLORS["surface"], fg=COLORS["again_fg"], font=self.font("Segoe UI", 10), anchor="w")
        error.pack(fill="x", pady=(self.px(6), 0))

        def value(name):
            widget = fields[name]
            return widget.get().strip() if isinstance(widget, ttk.Entry) else widget.get("1.0", "end").strip()

        def save():
            if not value("front"):
                error.configure(text="A card needs a question or prompt.")
                return
            self.store.update_card(card, **{name: value(name) for name in fields})
            top.destroy()
            self.toast_message("Card saved.")
            if on_done:
                on_done()

        def delete():
            if not self.dialog_confirm("Delete this card?", f"“{card.front[:80]}” and its review history will be removed. This can't be undone.", "Delete card", parent=top, destructive=True):
                return
            self.store.delete_cards([card.id])
            top.destroy()
            self.toast_message("Card deleted.")
            if on_done:
                on_done()

        def start_over():
            self.store.reset_progress([card.id])
            top.destroy()
            self.toast_message("This card is new again and due today.")
            if on_done:
                on_done()

        ttk.Button(actions, text="Delete", style="Danger.TButton", command=delete).grid(row=0, column=0, sticky="ew", padx=(0, self.px(8)))
        reset = ttk.Button(actions, text="Learn again", command=start_over)
        reset.grid(row=0, column=1, sticky="ew", padx=(0, self.px(8)))
        self.add_tooltip(reset, "Reset this card's progress so it comes back as a new card today.")
        ttk.Button(actions, text="Cancel", command=top.destroy).grid(row=0, column=2, sticky="ew", padx=(0, self.px(8)))
        self.solid_button(actions, "Save", save).grid(row=0, column=3, sticky="ew")
        for column, weight in enumerate((1, 1, 1, 2)):
            actions.columnconfigure(column, weight=weight)
        self.present_dialog(top)
        top.bind("<Escape>", lambda _event: top.destroy())
        top.bind(f"<{MOD}-Return>", lambda _event: save())
        fields["front"].focus_set()
        top.wait_window()

    def dialog_integer(self, title, body, initial=10, minvalue=1, maxvalue=120, parent=None):
        result = {"value": None}
        top, content, actions = self.dialog_window(title, body, parent=parent)
        entry = ttk.Entry(content)
        entry.insert(0, str(initial))
        entry.pack(fill="x")
        error = tk.Label(content, text=f"Enter a number from {minvalue} to {maxvalue}.", bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI", 10), anchor="w")
        error.pack(fill="x", pady=(self.px(6), 0))

        def submit():
            try:
                value = int(entry.get().strip())
            except ValueError:
                error.configure(text="Please enter a whole number.", fg=COLORS["again_fg"])
                return
            if value < minvalue or value > maxvalue:
                error.configure(text=f"Choose between {minvalue} and {maxvalue}.", fg=COLORS["again_fg"])
                return
            result["value"] = value
            top.destroy()

        cancel = ttk.Button(actions, text="Cancel", command=top.destroy)
        cancel.grid(row=0, column=0, sticky="ew", padx=(0, self.px(8)))
        start = self.solid_button(actions, "Continue", submit, COLORS["primary"])
        start.grid(row=0, column=1, sticky="ew")
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)
        self.present_dialog(top)
        top.bind("<Return>", lambda _event: submit())
        top.bind("<Escape>", lambda _event: top.destroy())
        entry.focus_set()
        entry.selection_range(0, "end")
        top.wait_window()
        return result["value"]

    def card(self, parent, style="Card.TFrame", padding=24):
        return ttk.Frame(parent, style=style, padding=self.px(padding))

    def text_box(self, parent, height=4, font_size=12):
        # A visible edge: in the light theme the box is white on a white card,
        # so with an input-coloured border there was nothing to show where to type.
        edge = COLORS["soft_line"] if self.theme == "light" else COLORS["line"]
        box = tk.Text(parent, height=height, wrap="word", bg=COLORS["input"], fg=COLORS["ink"], bd=0, relief="flat", highlightthickness=max(1, self.px(1)), highlightbackground=edge, highlightcolor=COLORS["primary"], padx=self.px(12), pady=self.px(12), font=self.font("Segoe UI", font_size), insertbackground=COLORS["primary"])
        return box

    def answer_area(self, parent, title="Your answer", hint="Type what you remember, then check or reveal.", height=4):
        panel = self.card(parent, "AltCard.TFrame", 18)
        panel.pack(fill="x", pady=(0, self.px(10)))
        ttk.Label(panel, text=title, style="AltH2.TLabel").pack(anchor="w")
        ttk.Label(panel, text=hint, style="AltMuted.TLabel", wraplength=self.px(980)).pack(anchor="w", pady=(self.px(4), self.px(10)))
        box = self.text_box(panel, height, 12)
        box.pack(fill="x")
        return box

    def bucket_style(self, bucket):
        return {
            "Again": "Again.TButton",
            "Review": "Review.TButton",
            "Good": "Good.TButton",
            "Easy": "Easy.TButton",
        }.get(bucket, "TButton")

    def render_bucket_highlight(self, parent, bucket):
        colors = {
            "Again": (COLORS["again_bg"], COLORS["again_fg"]),
            "Review": (COLORS["review_bg"], COLORS["review_fg"]),
            "Good": (COLORS["good_bg"], COLORS["good_fg"]),
            "Easy": (COLORS["easy_bg"], COLORS["easy_fg"]),
        }
        row = tk.Frame(parent, bg=COLORS["surface"])
        row.pack(fill="x", pady=(0, self.px(12)))
        for label in ("Again", "Review", "Good", "Easy"):
            bg, fg = colors[label] if label == bucket else (COLORS["bg"], COLORS["muted"])
            badge = tk.Label(row, text=label, bg=bg, fg=fg, font=self.font("Segoe UI Semibold", 11), padx=self.px(14), pady=self.px(8))
            badge.pack(side="left", padx=(0, self.px(8)))

    def open_testing(self, card=None, return_view=None, context="study"):
        self.testing_card = card or self.current_review
        self.return_view = return_view or self.current_view or "dashboard"
        self.testing_context = context
        self.show_view("testing")

    def solid_button(self, parent, text, command, color=None):
        """A filled, rounded call-to-action in any accent colour."""
        button = ttk.Button(parent, text=text, command=command, style=self.accent_button_style(color or COLORS["primary"]), cursor="hand2")
        button.bind("<Return>", lambda _event: button.invoke(), add="+")
        self.add_tooltip(button, self.action_hint(text))
        return button

    def tint(self, hex_color, amount):
        raw = hex_color.lstrip("#")
        if len(raw) != 6:
            return hex_color
        values = [int(raw[index:index + 2], 16) for index in (0, 2, 4)]
        shifted = [max(0, min(255, value + amount)) for value in values]
        return "#" + "".join(f"{value:02x}" for value in shifted)

    @staticmethod
    def luminance(hex_color):
        raw = str(hex_color).lstrip("#")
        if len(raw) != 6:
            return 0.0
        channels = [int(raw[index:index + 2], 16) / 255 for index in (0, 2, 4)]
        channels = [value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4 for value in channels]
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]

    def contrast(self, first, second):
        high, low = sorted((self.luminance(first), self.luminance(second)), reverse=True)
        return (high + 0.05) / (low + 0.05)

    def on_color(self, fill):
        """Text colour for a filled button or chip: white when it reads clearly
        (WCAG AA, 4.5:1), otherwise dark ink. Bright dark-theme accents such as
        #65afff fail with white (2.3:1), so they get dark text instead."""
        if self.contrast(COLORS["white"], fill) >= 4.5:
            return COLORS["white"]
        dark = COLORS.get("on_light", "#0b1020")
        return dark if self.contrast(dark, fill) > self.contrast(COLORS["white"], fill) else COLORS["white"]

    def row_button(self, parent, label, command, style_name):
        button = ttk.Button(parent, text=label, command=command, style=style_name, cursor="hand2")
        button.bind("<Return>", lambda _event: button.invoke(), add="+")
        self.add_tooltip(button, self.action_hint(label))
        return button

    def hover_card(self, frame, normal=None, hover=None, command=None):
        """Border a card; if it has a command, make the whole card clickable.

        Only clickable cards highlight on hover, so a glowing border always
        means "you can click this". Static information cards keep a plain
        border. Clicking anywhere on a clickable card (its text included)
        runs the command, which also gives a much larger target than the
        small button inside it.
        """
        # Cards are set apart by their fill, not a 1px outline on every box;
        # the edge stays invisible until a clickable card is hovered, and it
        # is always the one accent colour (the per-tile rainbow is gone).
        try:
            normal = frame.cget("bg")
        except tk.TclError:
            normal = normal or COLORS["surface"]
        frame.configure(highlightthickness=1, highlightbackground=normal, highlightcolor=normal)
        if command is None:
            return frame
        hover = COLORS["primary"]

        def pointer_inside():
            try:
                widget = frame.winfo_containing(*frame.winfo_pointerxy())
            except (KeyError, tk.TclError):
                return False
            while widget is not None:
                if widget is frame:
                    return True
                widget = widget.master
            return False

        def leave(_event):
            # Tk sends <Leave> when the pointer moves onto a child (the card's
            # text); only clear the highlight once it is really outside.
            if not pointer_inside():
                frame.configure(highlightbackground=normal)

        def wire(widget):
            # Buttons and inputs inside keep their own behaviour.
            if isinstance(widget, (tk.Button, ttk.Button, tk.Entry, ttk.Entry, tk.Text, ttk.Menubutton)):
                return
            widget.bind("<Button-1>", lambda _event: command(), add="+")
            try:
                widget.configure(cursor="hand2")
            except tk.TclError:
                pass
            for child in widget.winfo_children():
                wire(child)

        frame.bind("<Enter>", lambda _event: frame.configure(highlightbackground=hover), add="+")
        frame.bind("<Leave>", leave, add="+")
        # Children are added after this call, so wire them once built.
        frame.after_idle(lambda: frame.winfo_exists() and wire(frame))
        return frame
    def button_row(self, parent, buttons, style="Card.TFrame"):
        row = ttk.Frame(parent, style=style)
        row.pack(fill="x")
        columns = 3 if len(buttons) > 3 else max(1, len(buttons))
        if len(buttons) > 2 and self.accessibility_multiplier() > 1.1:
            columns = 2
        for index, (label, command, button_style) in enumerate(buttons):
            grid_row, grid_col = divmod(index, columns)
            button = self.row_button(row, label, command, button_style)
            button.grid(
                row=grid_row,
                column=grid_col,
                sticky="ew",
                padx=(0 if grid_col == 0 else self.px(12), 0),
                pady=(0 if grid_row == 0 else self.px(10), 0),
            )
            row.columnconfigure(grid_col, weight=1, uniform="buttons")
        return row

    def cue_menu_button(self, parent, text, actions, hint=""):
        button = ttk.Menubutton(parent, text=text)
        self.bind_dropdown(button, lambda: [(label, command, False) for label, command in actions])
        self.add_tooltip(button, hint or self.action_hint(text))
        return button

    def select_button(self, parent, variable, options, on_change=None, width=None):
        button = ttk.Menubutton(parent, text=variable.get(), style="Select.TMenubutton")
        if width:
            button.configure(width=width)

        def choose(value):
            variable.set(value)
            button.configure(text=value)
            if on_change:
                on_change(value)

        self.bind_dropdown(button, lambda: [(option, lambda value=option: choose(value), option == variable.get()) for option in options])
        return button

    def bind_dropdown(self, button, entries):
        # Native Tk menus get a light system border on Windows; this opens
        # MemoryPal's own borderless list instead.
        def open_list(_event=None):
            if str(button.cget("state")) != "disabled":
                self.open_dropdown(button, entries())
            return "break"

        for sequence in ("<ButtonPress-1>", "<Key-space>", "<Return>", "<Key-Down>"):
            button.bind(sequence, open_list)

    def close_dropdown(self):
        dropdown = getattr(self, "_dropdown", None)
        self._dropdown = None
        if dropdown is None:
            return
        top, previous_grab = dropdown
        try:
            top.grab_release()
            top.destroy()
        except tk.TclError:
            pass
        if previous_grab is not None:
            try:
                if previous_grab.winfo_exists():
                    previous_grab.grab_set()
            except tk.TclError:
                pass

    def screen_bounds(self, widget=None):
        """(left, top, right, bottom) of the screen area a popup may use."""
        widget = widget or self
        try:
            return 0, 0, widget.winfo_screenwidth(), widget.winfo_screenheight()
        except tk.TclError:
            return 0, 0, self.winfo_screenwidth(), self.winfo_screenheight()

    def fit_popup_rect(self, width, height, anchor_rect, gap=0):
        """(x, y, width, height) for a popup beside anchor_rect, kept on screen."""
        return popup_geometry.fit_popup_rect(width, height, anchor_rect, self.screen_bounds(), gap, self.px(8))

    def place_centered(self, top, owner, width, height):
        """Centre top over owner at width x height, capped to and kept on the screen."""
        try:
            owner_rect = (owner.winfo_rootx(), owner.winfo_rooty(),
                          owner.winfo_rootx() + owner.winfo_width(), owner.winfo_rooty() + owner.winfo_height())
        except tk.TclError:
            owner_rect = self.screen_bounds()
        x, y, width, height = popup_geometry.centered_rect(width, height, owner_rect, self.screen_bounds(), self.px(8))
        top.geometry(f"{width}x{height}+{x}+{y}")
        return width, height

    def open_dropdown(self, anchor, entries):
        self.close_dropdown()
        if not entries:
            return
        previous_grab = self.grab_current()
        top = tk.Toplevel(self)
        top.withdraw()
        top.overrideredirect(True)
        top.configure(bg=COLORS["surface_soft"])
        self.own_window(top, anchor.winfo_toplevel())
        inset = self.px(6)
        font_spec = self.font("Segoe UI", 11)
        measure = tkfont.Font(root=self, font=font_spec)
        row_height = measure.metrics("linespace") + 1
        anchor.update_idletasks()
        anchor_rect = (
            anchor.winfo_rootx(), anchor.winfo_rooty(),
            anchor.winfo_rootx() + anchor.winfo_width(), anchor.winfo_rooty() + anchor.winfo_height(),
        )
        x, y, width, height, rows, shown = popup_geometry.dropdown_layout(
            [label for label, _command, _selected in entries], measure.measure, anchor_rect, self.screen_bounds(),
            row_height, inset, side=measure.measure("  "), gap=self.px(4), margin=self.px(8))
        listbox = tk.Listbox(
            top,
            height=rows,
            width=0,  # Tk's default is 20 characters, which clipped long labels.
            bg=COLORS["surface_soft"],
            fg=COLORS["ink"],
            selectbackground=COLORS["primary"],
            selectforeground=self.on_color(COLORS["primary"]),
            relief="flat",
            bd=0,
            highlightthickness=0,
            activestyle="none",
            font=font_spec,
            exportselection=False,
            cursor="hand2",
        )
        listbox.pack(fill="both", expand=True, padx=inset, pady=inset)
        current = 0
        for index, (_label, _command, selected) in enumerate(entries):
            listbox.insert("end", f"  {shown[index]}  ")
            if selected:
                current = index
                listbox.itemconfigure(index, fg=COLORS["primary"])
        listbox.selection_set(current)
        listbox.see(current)
        self._dropdown = (top, previous_grab)

        def choose(_event=None):
            picked = listbox.curselection()
            self.close_dropdown()
            if picked:
                entries[picked[0]][1]()
            return "break"

        def hover(event):
            index = listbox.nearest(event.y)
            listbox.selection_clear(0, "end")
            listbox.selection_set(index)

        def press(event):
            # With the grab set, clicks anywhere in the app arrive here.
            inside = 0 <= event.x_root - top.winfo_rootx() < top.winfo_width() and 0 <= event.y_root - top.winfo_rooty() < top.winfo_height()
            if not inside:
                self.close_dropdown()
                return "break"
            return None

        def wheel(event):
            self._box_wheel(event)
            return "break"

        listbox.bind("<Motion>", hover)
        listbox.bind("<ButtonRelease-1>", choose)
        listbox.bind("<Return>", choose)
        listbox.bind("<Escape>", lambda _event: (self.close_dropdown(), "break")[1])
        listbox.bind("<MouseWheel>", wheel)
        listbox.bind("<Button-4>", wheel)
        listbox.bind("<Button-5>", wheel)
        top.bind("<ButtonPress-1>", press)
        listbox.bind("<ButtonPress-1>", press, add="+")
        listbox.bind("<FocusOut>", lambda _event: self.after(1, lambda: self.focus_get() is None and self.close_dropdown()))

        top.update_idletasks()
        # The listbox knows its exact row height; re-place with it so a list
        # that flipped above the anchor still sits right against it.
        height = listbox.winfo_reqheight() + inset * 2
        x, y, width, height = self.fit_popup_rect(width, height, anchor_rect, gap=self.px(4))
        top.geometry(f"{width}x{height}+{x}+{y}")
        self.reveal_window(top)
        listbox.focus_force()
        try:
            top.grab_set()
        except tk.TclError:
            pass

    def set_control_style(self, widget, style):
        """Switch a rounded control's style and refit its corners to its surface."""
        widget.configure(style=style)
        self.fit_control_corners(type("MapEvent", (), {"widget": widget})())

    def pill_group(self, parent, variable, options, on_change=None, max_columns=None, bg=None):
        bg = bg or COLORS["surface"]
        row = tk.Frame(parent, bg=bg)
        buttons = {}

        def refresh():
            for value, btn in buttons.items():
                self.set_control_style(btn, "PillOn.TButton" if value == variable.get() else "Pill.TButton")

        def choose(value):
            variable.set(value)
            refresh()
            if on_change:
                on_change(value)

        columns = max_columns or len(options) or 1
        for index, option in enumerate(options):
            btn = ttk.Button(row, text=option, style="Pill.TButton", cursor="hand2", command=lambda value=option: choose(value))
            grid_row, grid_col = divmod(index, columns)
            btn.grid(row=grid_row, column=grid_col, sticky="ew", padx=(0 if grid_col == 0 else self.px(6), 0), pady=(0 if grid_row == 0 else self.px(6), 0))
            row.columnconfigure(grid_col, weight=1)
            buttons[option] = btn
        refresh()
        # Follow the variable too, so a selection made elsewhere (e.g. clicking
        # a chart bar) moves the highlighted pill.
        trace = variable.trace_add("write", lambda *_args: row.winfo_exists() and refresh())
        row.bind("<Destroy>", lambda event: event.widget is row and variable.trace_remove("write", trace), add="+")
        return row

    def fit_wrap(self, label, **pack_options):
        """Pack a label so its text wraps to the width it is actually given.

        A fixed pixel wraplength wider than a narrow card/column clips the
        right side of the text instead of wrapping it. The label must fill
        its row horizontally so its allocated width is known.
        """
        pack_options.setdefault("anchor", "w")
        label.pack(fill="x", **pack_options)
        try:
            label.configure(justify="left", anchor="w")
        except tk.TclError:
            pass
        self.bind_rewrap(label)
        return label

    def fit_wrap_tree(self, container):
        """Make every wrapped, pack-managed label under container fit its width."""
        stack = [container]
        while stack:
            widget = stack.pop()
            stack.extend(widget.winfo_children())
            if not isinstance(widget, (tk.Label, ttk.Label)) or getattr(widget, "_memorypal_fit", False):
                continue
            try:
                wrap = int(float(str(widget.cget("wraplength")) or 0))
                if wrap <= 0 or widget.winfo_manager() != "pack":
                    continue
                widget.pack_configure(fill="x")
                widget.configure(justify="left", anchor="w")
            except (ValueError, tk.TclError):
                continue
            widget._memorypal_fit = True
            self.bind_rewrap(widget)

    def bind_rewrap(self, label):
        def rewrap(event):
            width = max(1, event.width - 2)
            try:
                current = int(float(str(label.cget("wraplength")) or 0))
            except (ValueError, tk.TclError):
                current = 0
            if abs(current - width) > 1:
                label.configure(wraplength=width)

        label.bind("<Configure>", rewrap, add="+")

    def check_toggle(self, parent, variable, text, on_change=None, bg=None, wraplength=520, fit=False):
        bg = bg or COLORS["surface"]
        # Reachable with Tab and ticked with Space, with a visible focus ring.
        row = tk.Frame(parent, bg=bg, cursor="hand2", takefocus=1, highlightthickness=max(1, self.px(2)),
                       highlightbackground=bg, highlightcolor=self.focus_color())
        size = self.px(19)
        box = tk.Canvas(row, width=size, height=size, highlightthickness=0, bg=bg, cursor="hand2")
        box.pack(side="left", padx=(0, self.px(9)))
        label = tk.Label(row, text=text, bg=bg, fg=COLORS["ink"], font=self.font("Segoe UI", 11), cursor="hand2", justify="left", wraplength=self.px(wraplength), anchor="w")
        label.pack(side="left", fill="x", expand=True)
        # Always follow the real width: a fixed wrap clipped long labels in
        # narrow columns and at the larger text sizes.
        self.bind_rewrap(label)

        def draw():
            box.delete("all")
            pad = max(1, self.px(2))
            if variable.get():
                box.create_rectangle(pad, pad, size - pad, size - pad, fill=COLORS["primary"], outline=COLORS["primary"], width=0)
                tick = self.line_icon("check", size, self.on_color(COLORS["primary"]))
                if tick is not None:
                    box.create_image(size / 2, size / 2, image=tick, anchor="center")
                    box._memorypal_icon = tick
            else:
                box.create_rectangle(pad, pad, size - pad, size - pad, fill=COLORS["input"], outline=COLORS["line"], width=max(1, self.px(1)))

        def toggle(_event=None):
            variable.set(not variable.get())
            draw()
            if on_change:
                on_change(variable.get())

        for widget in (row, box, label):
            widget.bind("<Button-1>", toggle)
        row.bind("<space>", toggle)
        draw()
        return row

    # ------------------------------------------------------------------
    # Selectable text
    # ------------------------------------------------------------------
    def keep_flat_buttons_still(self):
        """Stop flat buttons nudging their text when pressed.

        Tk shows a press by sinking the button, and on Windows a sunken
        button draws its label one pixel lower and to the right, so the words
        jump under the pointer. Flat buttons here show presses with colour
        instead, so they stay flat; buttons with a real border keep sinking.
        """
        try:
            self.tk.eval(
                "if {[info procs ::tk::_mpButtonDown] eq {}} {"
                " rename ::tk::ButtonDown ::tk::_mpButtonDown;"
                " rename ::tk::ButtonEnter ::tk::_mpButtonEnter;"
                " proc ::tk::_mpStayFlat w {"
                "  variable ::tk::Priv;"
                "  if {[info exists Priv($w,relief)] && $Priv($w,relief) eq {flat} && [$w cget -relief] eq {sunken}} {"
                "   $w configure -relief flat; set Priv($w,prelief) flat } };"
                " proc ::tk::ButtonDown w { ::tk::_mpButtonDown $w; ::tk::_mpStayFlat $w };"
                " proc ::tk::ButtonEnter w { ::tk::_mpButtonEnter $w; ::tk::_mpStayFlat $w } }"
            )
        except tk.TclError:
            pass  # an unusual Tk: presses just sink as before

    def install_smooth_box_scrolling(self):
        """Text boxes and lists (in pages, dialogs and dropdowns) glide on the
        wheel like pages do, instead of jumping four lines per notch."""
        for widget_class in ("Text", "Listbox"):
            for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                self.bind_class(widget_class, sequence, self._box_wheel)

    def _box_wheel(self, event):
        widget = event.widget
        try:
            first, last = widget.yview()
        except (tk.TclError, ValueError, AttributeError):
            return None
        if first <= 0.0 and last >= 1.0:
            return None  # nothing to scroll: let the page under it scroll
        state = getattr(widget, "_mp_glide", None)
        if state is None:
            state = {"target": 0.0, "lines": 0, "after": None, "last": 0.0, "event": 0.0, "touch": -1.0, "tau": scrolling.NOTCH_TAU_MS}
            widget._mp_glide = state
        number = getattr(event, "num", None)
        button = number if number in (4, 5) else None
        delta = float(getattr(event, "delta", 0) or 0)
        now = time.perf_counter()
        gap, state["event"] = now - state["event"], now
        if scrolling.is_touchpad_delta(delta, IS_MAC, button):
            state["touch"] = now
        try:
            line = max(8, tkfont.Font(root=self, font=widget.cget("font")).metrics("linespace"))
        except (tk.TclError, TypeError):
            line = self.px(20)
        # Three lines a notch, the platform's usual wheel step.
        pixels, tau = scrolling.wheel_motion(delta, line * 3, mac=IS_MAC, button=button, gap_s=gap,
                                             since_touchpad_s=now - state["touch"],
                                             reduce_motion=bool(self.accessibility.get("reduce_motion")))
        if not pixels:
            return "break"
        if isinstance(widget, tk.Listbox):
            # Lists only move by whole rows: spread a notch's rows over frames.
            state["remainder"] = state.get("remainder", 0.0) + pixels / line
            rows = int(state["remainder"])
            state["remainder"] -= rows
            if tau <= 0:
                widget.yview_scroll(rows, "units")
                return "break"
            state["lines"] += rows
        elif tau <= 0:
            state["target"] = 0.0
            whole = int(round(pixels))
            if whole:
                widget.yview_scroll(whole, "pixels")
            return "break"
        else:
            state["target"] += pixels
            state["tau"] = tau
        if state["after"] is None:
            state["last"] = now - 1 / 60
            self._box_glide(widget)
        return "break"

    def _box_glide(self, widget):
        state = getattr(widget, "_mp_glide", None)
        if state is None:
            return
        state["after"] = None
        try:
            if not widget.winfo_exists():
                return
        except tk.TclError:
            return
        now = time.perf_counter()
        elapsed = min(50.0, max(1.0, (now - state["last"]) * 1000))
        state["last"] = now
        busy = False
        try:
            if isinstance(widget, tk.Listbox):
                rows, state["lines"] = scrolling.take_lines(state["lines"])
                if rows:
                    widget.yview_scroll(rows, "units")
                busy = bool(state["lines"])
            else:
                step, done = scrolling.glide_step(state["target"], elapsed, state["tau"])
                whole = int(round(step))
                if whole:
                    widget.yview_scroll(whole, "pixels")
                state["target"] = 0.0 if done else state["target"] - whole
                busy = not done
        except tk.TclError:
            busy = False
        if busy:
            state["after"] = self.after(16, lambda: self._box_glide(widget))

    def install_text_selection(self):
        """Let people highlight and copy any text shown in a label.

        Tk labels can't be selected, and swapping every label for a text box
        would change how pages lay out. Instead, pressing on a label's text
        lays a read-only text box with the same font, colours and wrapping
        exactly over it; the drag carries on in that box, so the highlight
        appears where the words are. It goes away on the next click elsewhere.
        Buttons and clickable cards (hand cursor) are left alone.
        """
        self._select_overlay = None
        for widget_class in ("Label", "TLabel"):
            self.bind_class(widget_class, "<ButtonPress-1>", self._label_press, add="+")
            self.bind_class(widget_class, "<B1-Motion>", self._label_drag, add="+")
            self.bind_class(widget_class, "<Double-Button-1>", lambda event: self._label_multi_click(event, "word"), add="+")
            self.bind_class(widget_class, "<Triple-Button-1>", lambda event: self._label_multi_click(event, "line"), add="+")
            for button in CONTEXT_CLICKS:
                self.bind_class(widget_class, button, self._label_copy_all, add="+")
            self.bind_class(widget_class, "<Enter>", self._label_hover_cursor, add="+")
        self.bind_all("<ButtonPress-1>", self._maybe_clear_selection, add="+")

    def _selectable_label(self, widget):
        if not isinstance(widget, (tk.Label, ttk.Label)) or not widget.winfo_exists():
            return False
        try:
            text = str(widget.cget("text"))
            if len(text.strip()) < 2 or str(widget.cget("image")):
                return False
            if str(widget.cget("cursor")) not in ("", "xterm"):
                return False  # clickable (hand) labels keep their click
        except tk.TclError:
            return False
        if widget is getattr(self, "toast", None):
            return False
        # Navigation rail and tooltips aren't content.
        rail = getattr(self, "rail", None)
        parent = widget
        while parent is not None:
            if parent is rail:
                return False
            if isinstance(parent, tk.Toplevel) and parent.overrideredirect() and not hasattr(parent, "dialog_owner") and parent is not getattr(self, "_finder", None):
                return False  # tooltips and dropdown lists
            parent = parent.master
        return True

    def _label_hover_cursor(self, event):
        widget = event.widget
        if self._selectable_label(widget) and not str(widget.cget("cursor")):
            try:
                widget.configure(cursor="xterm")
            except tk.TclError:
                pass

    def _label_style(self, label):
        """Font, colours and layout of a tk or ttk label, as a text box needs them."""
        if isinstance(label, ttk.Label):
            style = str(label.cget("style")) or "TLabel"

            def look(option, fallback):
                value = str(label.cget(option)) if option in label.keys() else ""
                return value or self.style.lookup(style, option) or fallback

            padding = str(label.cget("padding") or self.style.lookup(style, "padding") or "0").split()
            # The clam Label layout wraps the text in a 1px border element and
            # a 1px padding element before any padding of its own.
            pad = [int(float(value)) + 2 for value in padding] or [2]
            return {
                "font": look("font", "TkDefaultFont"),
                "fg": look("foreground", COLORS["ink"]),
                "bg": self.style.lookup(style, "background") or COLORS["surface"],
                "padx": pad[0], "pady": pad[1] if len(pad) > 1 else pad[0],
                "anchor": look("anchor", "w"), "justify": look("justify", "left"),
                "wrap": int(float(str(label.cget("wraplength") or 0) or 0)),
            }
        return {
            "font": label.cget("font"), "fg": label.cget("fg"), "bg": label.cget("bg"),
            "padx": int(float(label.cget("padx"))) + int(float(label.cget("bd"))),
            "pady": int(float(label.cget("pady"))) + int(float(label.cget("bd"))),
            "anchor": str(label.cget("anchor")), "justify": str(label.cget("justify")),
            "wrap": int(float(str(label.cget("wraplength")) or 0)),
        }

    def clear_text_selection(self):
        overlay = getattr(self, "_select_overlay", None)
        self._select_overlay = None
        if overlay is not None:
            try:
                overlay.destroy()
            except tk.TclError:
                pass

    def _maybe_clear_selection(self, event):
        overlay = getattr(self, "_select_overlay", None)
        if overlay is not None and event.widget not in (overlay, getattr(overlay, "owner", None)):
            self.clear_text_selection()

    def _overlay_for(self, label):
        overlay = getattr(self, "_select_overlay", None)
        if overlay is not None and getattr(overlay, "owner", None) is label and overlay.winfo_exists():
            return overlay
        self.clear_text_selection()
        look = self._label_style(label)
        text = str(label.cget("text"))
        box = tk.Text(
            label.master, font=look["font"], fg=look["fg"], bg=look["bg"], bd=0, highlightthickness=0,
            padx=0, pady=0, wrap="none", cursor="xterm", insertwidth=0,
            selectbackground=COLORS["primary"], selectforeground=self.on_color(COLORS["primary"]), inactiveselectbackground=COLORS["primary"],
            exportselection=True, takefocus=0, undo=False,
        )
        box.owner = label
        # Break the lines exactly where the label does. Letting the text box
        # wrap by itself can put a word on a different line (the two measure
        # the end of a line slightly differently), which makes the text jump
        # as soon as it is clicked. The added breaks are "soft": copying
        # turns them back into spaces.
        for number, line in enumerate(self.label_lines(look["font"], text, look["wrap"])):
            if number:
                box.insert("end", "\n", ("soft",) if line[1] else ())
            box.insert("end", line[0])
        # Only our own bindings: no typing, no text-box scrolling (the wheel
        # still scrolls the page through the "all" bindings).
        box.bindtags((str(box), str(label.winfo_toplevel()), "all"))
        # place(in_=...) measures from inside the label's border; step back
        # over it so the text box covers the whole label, pixel for pixel.
        border = 0
        if isinstance(label, tk.Label):
            border = int(float(label.cget("bd"))) + int(float(label.cget("highlightthickness")))
        box.place(in_=label, x=-border, y=-border, relwidth=1, relheight=1, width=2 * border, height=2 * border)
        box.update_idletasks()
        width, height = label.winfo_width(), label.winfo_height()
        inner_w = max(1, width - 2 * look["padx"])
        box.tag_configure("all", justify=look["justify"] if look["justify"] in ("left", "center", "right") else "left")
        box.tag_add("all", "1.0", "end")
        # Lay the lines out, then measure the block they make.
        box.tag_configure("all", lmargin1=look["padx"], lmargin2=look["padx"], rmargin=0)
        box.update_idletasks()
        lines = []
        index = "1.0"
        while True:
            info = box.dlineinfo(index)
            if info is None:
                break
            lines.append(info)
            nxt = box.index(f"{index} +1 display lines")
            if box.compare(nxt, "<=", index):
                break
            index = nxt
        block_h = (lines[-1][1] + lines[-1][3] - lines[0][1]) if lines else 0
        block_w = max((info[2] for info in lines), default=0)
        anchor = look["anchor"]
        left = look["padx"]
        if anchor in ("center", "n", "s"):
            left = look["padx"] + max(0, (inner_w - block_w) // 2)
        elif anchor in ("e", "ne", "se"):
            left = look["padx"] + max(0, inner_w - block_w)
        # The label places its text block by anchor and aligns lines inside
        # that block by justify; make the text box area exactly the block.
        slack = 2  # spare room for rounding in centred and right-aligned text
        shift = {"center": slack // 2, "right": slack}.get(look["justify"], 0)
        box.tag_configure("all", lmargin1=left - shift, lmargin2=left - shift, rmargin=max(0, width - left - max(block_w, 1) - slack + shift))
        top = look["pady"]
        if anchor in ("w", "center", "e"):
            top = max(0, (height - block_h) // 2)
        elif anchor in ("sw", "s", "se"):
            top = max(0, height - look["pady"] - block_h)
        box.configure(pady=0)
        box.tag_configure("first", spacing1=top)
        box.tag_add("first", "1.0", "1.0 lineend")
        box.bind("<ButtonPress-1>", lambda event: self._overlay_press(box, event))
        box.bind("<B1-Motion>", lambda event: self._overlay_drag(box, event))
        box.bind("<Double-Button-1>", lambda event: self._overlay_select_unit(box, event, "word"))
        box.bind("<Triple-Button-1>", lambda event: self._overlay_select_unit(box, event, "line"))
        for button in CONTEXT_CLICKS:
            box.bind(button, lambda _event: self._copy_overlay(box, whole_if_empty=True))
        for sequence in (("<Command-c>", "<Command-C>") if IS_MAC else ("<Control-c>", "<Control-C>", "<Control-Insert>")):
            box.bind(sequence, lambda _event: (self._copy_overlay(box), "break")[1])
        for sequence in (f"<{MOD}-a>", f"<{MOD}-A>"):
            box.bind(sequence, lambda _event: (box.tag_add("sel", "1.0", "end-1c"), "break")[1])
        box.bind("<Escape>", lambda _event: self.clear_text_selection())
        self._select_overlay = box
        return box

    def label_lines(self, font, text, wrap):
        """[(line, soft_break_before)] as a Tk label with this wraplength shows them.

        Tk doesn't report where a label wrapped its text, so ask it: a hidden
        probe label with the same font says whether a stretch of text fits on
        one line (its requested height is one line tall). The longest stretch
        that fits, with the space after it, is the line, just as Tk decides it,
        including a very long word being split when nothing else fits.
        """
        paragraphs = str(text).split("\n")
        if wrap <= 0:
            return [(line, False) for line in paragraphs]
        probe = getattr(self, "_wrap_probe", None)
        if probe is None or not probe.winfo_exists():
            probe = self._wrap_probe = tk.Label(self, bd=0, padx=0, pady=0, highlightthickness=0, justify="left")
        probe.configure(font=font, wraplength=wrap, text="x")
        one_line = probe.winfo_reqheight()

        def fits(chunk):
            probe.configure(text=chunk)
            return probe.winfo_reqheight() <= one_line

        lines = []
        for paragraph in paragraphs:
            rest = paragraph
            soft = False
            while True:
                if not rest or fits(rest):
                    lines.append((rest, soft))
                    break
                breaks = [index for index, char in enumerate(rest) if char == " " and index and rest[index - 1] != " "]
                low, high, best = 0, len(breaks) - 1, 0
                while low <= high:
                    middle = (low + high) // 2
                    # Tk counts the space after a word when deciding whether it fits.
                    if fits(rest[:breaks[middle] + 1]):
                        best = breaks[middle]
                        low = middle + 1
                    else:
                        high = middle - 1
                if not best:
                    # The first word alone is too wide: Tk splits it where it runs out of room.
                    low, high, best = 1, (breaks[0] if breaks else len(rest)) - 1, 1
                    while low <= high:
                        middle = (low + high) // 2
                        if fits(rest[:middle]):
                            best = middle
                            low = middle + 1
                        else:
                            high = middle - 1
                lines.append((rest[:best], soft))
                rest = rest[best:].lstrip(" ")
                soft = True
        return lines

    def _overlay_text(self, box, first, last):
        """Text between two indices, with the added line breaks put back as spaces."""
        parts = []
        cursor = first
        ranges = box.tag_ranges("soft")
        for start, end in zip(ranges[0::2], ranges[1::2]):
            if box.compare(end, "<=", first) or box.compare(start, ">=", last):
                continue
            parts.append(box.get(cursor, start))
            parts.append(" ")
            cursor = end
        parts.append(box.get(cursor, last))
        return "".join(parts)

    def _overlay_press(self, box, event):
        box.tag_remove("sel", "1.0", "end")
        box._anchor = box.index(f"@{event.x},{event.y}")
        box.mark_set("insert", box._anchor)
        try:
            box.focus_set()
        except tk.TclError:
            pass
        return "break"

    def _overlay_drag(self, box, event):
        anchor = getattr(box, "_anchor", None)
        if anchor is None:
            return "break"
        here = box.index(f"@{event.x},{event.y}")
        box.tag_remove("sel", "1.0", "end")
        first, last = (anchor, here) if box.compare(anchor, "<=", here) else (here, anchor)
        box.tag_add("sel", first, last)
        return "break"

    def _overlay_select_unit(self, box, event, unit):
        here = f"@{event.x},{event.y}"
        box.tag_remove("sel", "1.0", "end")
        if unit == "word":
            box.tag_add("sel", f"{here} wordstart", f"{here} wordend")
        else:
            box.tag_add("sel", f"{here} display linestart", f"{here} display lineend")
        return "break"

    def _copy_overlay(self, box, whole_if_empty=False):
        try:
            text = self._overlay_text(box, box.index("sel.first"), box.index("sel.last"))
        except tk.TclError:
            text = self._overlay_text(box, "1.0", box.index("end-1c")) if whole_if_empty else ""
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.toast_message("Copied.")

    def _label_press(self, event):
        if not self._selectable_label(event.widget):
            return None
        box = self._overlay_for(event.widget)
        return self._overlay_press(box, event)

    def _label_drag(self, event):
        overlay = getattr(self, "_select_overlay", None)
        if overlay is not None and getattr(overlay, "owner", None) is event.widget:
            return self._overlay_drag(overlay, event)
        return None

    def _label_multi_click(self, event, unit):
        overlay = getattr(self, "_select_overlay", None)
        if overlay is not None and getattr(overlay, "owner", None) is event.widget:
            return self._overlay_select_unit(overlay, event, unit)
        return None

    def _label_copy_all(self, event):
        if not self._selectable_label(event.widget):
            return None
        self.clipboard_clear()
        self.clipboard_append(str(event.widget.cget("text")))
        self.toast_message("Copied.")
        return "break"

    def add_tooltip(self, widget, text):
        if text:
            Tooltip(widget, text)

    def action_hint(self, label):
        hints = self._action_hints()
        if label in hints:
            return hints[label]
        folded = {key.casefold(): value for key, value in hints.items()}
        return folded.get(str(label).casefold(), "")

    def _action_hints(self):
        return {
            "Smart Check": "Compare your response with the saved answer and highlight the suggested bucket.",
            "Reveal / Hide Answer": "Show or hide the saved answer without rating the card.",
            "Reveal Only": "Show the answer without using Smart Check.",
            "Use Smart Rating": "Schedule the card using the latest Smart Check result.",
            "Use suggested rating": "Schedule the card using the latest Smart Check result.",
            "Reveal answer": "Show or hide the saved answer without rating the card.",
            "Next card": "Move to the next self-check card.",
            "Again": "Bring this card back soon.",
            "Good": "You remembered enough; schedule it a little later.",
            "Easy": "You knew it well; schedule it further out.",
            "Start in Test Lab": "Open the next due card on the focused testing page.",
            "Open in Test Lab": "Practice this card on the separate testing page.",
            "Add Q/A": "Stage one prompt-answer card from the question and answer fields.",
            "Add Item": "Add this prompt and answer as one repetition item.",
            "Split Answer": "Split the answer box into separate repetition answers.",
            "Remove Last": "Remove the most recently staged item.",
            "Make Q/A Cards": "Create flashcards from staged Q/A items and pasted Q/A lines.",
            "Split Paste": "Turn pasted notes, /n markers, and numbered lists into separate study bits.",
            "Build Path": "Create the structured repetition rounds from the material above.",
            "Add Audio": "Choose whether to import an audio file or record one.",
            "Add Video": "Choose whether to import a video file or record one.",
            "TXT": "Import a text file or save the current note as a text cue.",
            "IMG": "Attach an image cue.",
            "AUD": "Import or record an audio cue.",
            "VID": "Import or record a video cue.",
            "NOTE": "Import a note, PDF, or Word document, or save the current text as a note.",
            "Use All": "Load saved captures and cards into the repetition builder.",
            "Use Captures": "Load saved capture bits into this practice mode.",
            "Use Cards": "Load saved cards into this practice mode.",
            "Self Check": "Use Test Lab to answer, reveal, and Smart Check yourself.",
            "Multiple Choice": "Pick from answer options for a faster quiz game.",
            "Play Again": "Restart this quiz mode with a fresh set of cards.",
            "Skip / Next": "Move to the next self-check card.",
            "Start": "Begin this puzzle round.",
            "Check": "Check your answer.",
            "Show Words": "Briefly show the word list, then hide it.",
            "New Pair Set": "Make a small prompt-answer matching set.",
            "Reveal Cue": "Show one side of the next pair.",
            "Make Gap": "Create a missing-item challenge.",
            "Peg List": "Map ideas onto a simple numbered peg list.",
            "Memory Palace": "Place ideas along a familiar route.",
            "Chunk Map": "Group ideas into smaller study clusters.",
            "Link Chain": "Connect each idea to the next with a tiny scene.",
            "Mini Story": "Auto-generate an ordered memory story from your ideas.",
            "Export": "Save your MemoryPal data as a JSON backup.",
            "Import": "Load a MemoryPal JSON backup.",
            "Export backup": "Save this profile's cards and progress as a file you can keep or move to another computer.",
            "Import backup": "Replace this profile with a saved backup file. You'll be asked first, and a copy of the current data is kept.",
            "Add cards": "Type questions and answers, paste notes, or import a document to make new cards.",
            "Reset": "Clear local data and restore sample cards.",
            "Open": "Open this section.",
            "Start Due Review": "Move due cards into Test Lab.",
            "Build Repetition Path": "Create a recall sequence from saved or pasted material.",
            "Practice": "Open this item in Test Lab.",
            "Open Technique": "Open the matching MemoryPal tool for this technique.",
            "Build Technique Plan": "Turn the notes into a practical memory strategy plan.",
            "Visual Search": "Practice selective attention by finding target tiles.",
            "N-Back Lite": "Practice working memory by judging whether the item matches the previous one.",
            "Same as Last": "Mark the current item as matching the previous item.",
            "Different": "Mark the current item as different from the previous item.",
            "New Round": "Start a fresh short puzzle round.",
            "Build Sort": "Turn saved or pasted items into a simple category-sorting exercise.",
            "Use Sample": "Load a small everyday sample to practise with.",
            "Show Routine": "Briefly show the routine steps before recall.",
            "Check Routine": "Compare the typed routine with the shown steps.",
            "Move Up": "Move the selected page earlier in its section.",
            "Move Down": "Move the selected page later in its section.",
            "Apply Order": "Save this page order and refresh the sections.",
            "Reset Order": "Return the pages to the default MemoryPal order.",
            "Save Feedback": "Save this note on this computer.",
            "Export Feedback": "Save your notes and ratings as a CSV file.",
            "Open Feedback": "Rate the app, report a problem, or suggest an idea.",
            "Back": "Return to the previous section.",
            "Settings": "Personalize MemoryPal's appearance, profiles, storage, and window behavior.",
            "Everyday Memory": "Open the calm older-adult memory support area.",
            "Start Gentle Review": "Review one familiar prompt at a time in Test Lab.",
            "Add Person Card": "Create a simple name, relationship, and reminder card.",
            "Add Routine Card": "Create a step-by-step everyday routine card.",
            "Add Place Card": "Create a card for where an item belongs or where something happens.",
            "Add Reminder Card": "Create a calm daily reminder card.",
            "Create Starter Set": "Add a few sample Everyday Memory cards.",
            "Use Senior Layout": "Turn on larger text, higher contrast, reduced motion, and a simpler page order.",
            "Open Puzzles": "Open short attention and recall games.",
            "Open Caregiver Notes": "Open capture so a helper can add notes, images, audio, or video.",
            "Edit Daily Goal": "Change how many cards count as a completed study day.",
            "Manage Profiles": "Create, rename, delete, or switch separate study profiles.",
            "Open Data Folder": "Open the folder where MemoryPal stores profiles, data, and attachments.",
            "Export Backup": "Save a portable JSON copy of the active profile.",
            "Import Backup": "Load a JSON backup into the active profile.",
            "True Fullscreen": f"Use the operating system fullscreen mode. {'Control-Command-F' if IS_MAC else 'F11'} does the same thing.",
            "Focus Window": "Use a borderless focus window without changing the operating system fullscreen state.",
        }

    def mastery_summary(self):
        total = len(self.store.cards)
        if not total:
            return 0, 0, 0
        mastered = len([card for card in self.store.cards if card.last_score >= 82 or card.last_result == "Strong match"])
        learning = len([card for card in self.store.cards if 42 <= card.last_score < 82])
        return round(mastered / total * 100), mastered, learning

    def render_status_chip(self, parent, text, color, fg=None):
        chip = tk.Label(parent, text=text, bg=color, fg=fg or self.on_color(color), font=self.font("Segoe UI Semibold", 10), padx=self.px(12), pady=self.px(6))
        chip.pack(side="left", padx=(0, self.px(8)))
        return chip

    def start_view(self):
        # A new install opens on sign-in, then the setup questions, then Today.
        if self.needs_sign_in_prompt():
            return "signin"
        return "dashboard" if self.store.onboarding.get("done") else "welcome"

    def needs_sign_in_prompt(self):
        """Until someone signs in or chooses to go on without an account."""
        return cloud.configured() and not self.account.signed_in and not self.account.state.account_prompted

    def mark_sign_in_prompted(self):
        state = self.account.state
        if not state.account_prompted:
            state.account_prompted = True
            state.save()

    def continue_without_account(self):
        self.mark_sign_in_prompted()
        self.show_view(self.start_view())

    def view_signin(self):
        """First launch: sign in or create an account, or go on without one."""
        page = ScrollFrame(self.view_host)
        page.pack(fill="both", expand=True)
        holder = tk.Frame(page.inner, bg=COLORS["bg"])
        holder.pack(fill="x", pady=(self.px(24), 0))
        card = tk.Frame(holder, bg=COLORS["surface"], padx=self.px(40), pady=self.px(36), highlightthickness=1, highlightbackground=COLORS["line"])
        card.pack(anchor="center")
        mark_size = self.px(72)
        mark = tk.Canvas(card, width=mark_size, height=mark_size, bg=COLORS["surface"], highlightthickness=0)
        mark.pack(pady=(0, self.px(14)))
        if not self.draw_memorypal_logo(mark, mark_size):
            self.draw_chrome_icon(mark, mark_size)
        tk.Label(card, text="Welcome to MemoryPal", bg=COLORS["surface"], fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 22)).pack()
        tk.Label(
            card,
            text="Sign in to keep your cards, progress and settings on all your devices: this computer, your phone and more.",
            bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI", 12), wraplength=self.px(440), justify="center",
        ).pack(pady=(self.px(6), self.px(22)))
        buttons = tk.Frame(card, bg=COLORS["surface"])
        buttons.pack(fill="x")
        buttons.columnconfigure(0, weight=1)
        for row, (label, command, style_name) in enumerate((
            ("Sign in", lambda: self.open_account_dialog("sign_in"), "Primary.TButton"),
            ("Create an account", lambda: self.open_account_dialog("create"), "TButton"),
        )):
            self.row_button(buttons, label, command, style_name).grid(row=row, column=0, sticky="ew", pady=(0, self.px(10)))
        skip = tk.Label(card, text="Continue without an account", bg=COLORS["surface"], fg=COLORS["primary"], font=self.font("Segoe UI Semibold", 11), cursor="hand2", takefocus=1)
        skip.pack(pady=(self.px(8), 0))
        self.keyboard_link(skip, lambda _event: self.continue_without_account())
        self.add_tooltip(skip, "Your cards stay on this computer. You can sign in later from Settings.")
        tk.Label(card, text="You can sign in or out any time in Settings.", bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI", 10)).pack(pady=(self.px(10), 0))

    def view_welcome(self):
        page = ScrollFrame(self.view_host)
        page.pack(fill="both", expand=True)
        state = {"persona": self.store.onboarding.get("persona") or "", "size_touched": False}
        text_size = tk.StringVar(value=self.accessibility.get("text_size", "Comfort"))
        read_aloud = tk.BooleanVar(value=bool(self.accessibility.get("read_aloud")))

        hero = self.hover_card(tk.Frame(page.inner, bg=COLORS["surface"], padx=self.px(30), pady=self.px(28)))
        hero.pack(fill="x", padx=(0, 8), pady=(0, 16))
        tk.Label(hero, text=f"Welcome to MemoryPal, {active_profile_name()}", bg=COLORS["surface"], fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 24)).pack(anchor="w")
        tk.Label(hero, text="Three quick questions so the app fits you. You can change any of this later in Settings.", bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI", 12), wraplength=self.px(1000), justify="left").pack(anchor="w", pady=(6, 0))

        who = self.card(page.inner, "Card.TFrame", 22)
        who.pack(fill="x", padx=(0, 8), pady=(0, 16))
        ttk.Label(who, text="1. Who will be using MemoryPal?", style="H2.TLabel").pack(anchor="w", pady=(0, 12))
        choices = ttk.Frame(who, style="Card.TFrame")
        choices.pack(fill="x")
        for column in range(2):
            choices.columnconfigure(column, weight=1, uniform="persona")
        colors = {"student": COLORS["primary"], "everyday": COLORS["cyan"], "caregiver": COLORS["violet"], "general": COLORS["green"]}

        @self.smooth
        def render_choices():
            for child in choices.winfo_children():
                child.destroy()
            for index, key in enumerate(onboarding.PERSONA_ORDER):
                data = onboarding.PERSONAS[key]
                selected = state["persona"] == key
                tile = self.hover_card(
                    tk.Frame(choices, bg=COLORS["surface"], padx=self.px(20), pady=self.px(18)),
                    normal=colors[key] if selected else None,
                    hover=colors[key],
                    command=lambda value=key: choose(value),
                )
                tile.configure(highlightthickness=max(2, self.px(3)) if selected else 1)
                row, column = divmod(index, 2)
                tile.grid(row=row, column=column, sticky="nsew", padx=(0 if column == 0 else self.px(12), 0), pady=(0, self.px(12)))
                tk.Frame(tile, bg=colors[key], width=self.px(36), height=self.px(4)).pack(anchor="w", pady=(0, self.px(10)))
                heading = ("\u2713  " if selected else "") + data["title"]
                tk.Label(tile, text=heading, bg=COLORS["surface"], fg=colors[key] if selected else COLORS["ink"], font=self.font("Segoe UI Semibold", 15), anchor="w").pack(fill="x")
                body = tk.Label(tile, text=data["body"], bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI", 11), justify="left", anchor="w", wraplength=self.px(420))
                body.pack(fill="x", pady=(self.px(5), 0))
                self.bind_rewrap(body)

        def choose(key):
            state["persona"] = key
            if not state["size_touched"]:
                text_size.set(onboarding.persona(key)["accessibility"].get("text_size", "Comfort"))
            render_choices()

        render_choices()

        comfort = self.card(page.inner, "Card.TFrame", 22)
        comfort.pack(fill="x", padx=(0, 8), pady=(0, 16))
        ttk.Label(comfort, text="2. How big should the text be?", style="H2.TLabel").pack(anchor="w", pady=(0, 10))
        sizes = {"Comfort": 12, "Large": 14, "Extra Large": 16}
        preview = tk.Label(comfort, text="This is how easy the text will be to read.", bg=COLORS["surface"], fg=COLORS["ink"], anchor="w")

        def show_preview(*_args):
            preview.configure(font=self.font("Segoe UI", sizes.get(text_size.get(), 12)))

        def size_chosen(_value):
            state["size_touched"] = True

        self.pill_group(comfort, text_size, list(sizes), on_change=size_chosen, max_columns=3).pack(fill="x")
        show_preview()
        preview.pack(fill="x", pady=(self.px(12), 0))
        text_size.trace_add("write", show_preview)

        voice = self.card(page.inner, "Card.TFrame", 22)
        voice.pack(fill="x", padx=(0, 8), pady=(0, 16))
        ttk.Label(voice, text="3. Would you like questions read aloud?", style="H2.TLabel").pack(anchor="w", pady=(0, 10))
        self.check_toggle(voice, read_aloud, "Yes, read questions and answers aloud to me", fit=True).pack(fill="x", pady=(0, self.px(10)))
        self.button_row(voice, [("Test the Voice", lambda: self.speak("Hello. This is how MemoryPal sounds when it reads to you."), "TButton")])

        finish = self.card(page.inner, "AltCard.TFrame", 22)
        finish.pack(fill="x", padx=(0, 8), pady=(0, 16))
        ttk.Label(finish, text="All set?", style="AltH2.TLabel").pack(anchor="w")
        ttk.Label(finish, text="The tour shows the few pages you'll use most, one at a time. It takes about a minute.", style="AltMuted.TLabel", wraplength=self.px(1000)).pack(anchor="w", pady=(4, 12))
        self.button_row(
            finish,
            [
                ("Start the Tour", lambda: self.finish_welcome(state["persona"], text_size.get(), read_aloud.get(), True), "Primary.TButton"),
                ("Skip the Tour", lambda: self.finish_welcome(state["persona"], text_size.get(), read_aloud.get(), False), "TButton"),
            ],
            "AltCard.TFrame",
        )

    def finish_welcome(self, persona_key, text_size, read_aloud, take_tour):
        persona_key = persona_key if persona_key in onboarding.PERSONAS else "general"
        data = onboarding.persona(persona_key)
        prefs = dict(self.accessibility)
        # Redoing the welcome with a different answer shouldn't keep the old
        # answer's comfort settings, so reset every persona-managed option.
        defaults = default_accessibility()
        prefs.update({key: defaults[key] for key in onboarding.MANAGED_SETTINGS})
        prefs.update(data["accessibility"])
        prefs.update({"text_size": text_size, "read_aloud": bool(read_aloud)})
        self.accessibility = normalize_accessibility(prefs)
        self.store.accessibility = dict(self.accessibility)
        self.store.onboarding = {"done": True, "persona": persona_key}
        self.set_nav_order(data["nav"])  # saves the profile
        self.tour = {"persona": persona_key, "index": 0} if take_tour else None
        first_view = onboarding.tour_steps(persona_key)[0][0] if take_tour else "dashboard"

        def rebuild(hidden):
            # New text size, palette, nav order and first page all change at
            # once; build them out of sight so no white or unstyled frame shows.
            self.apply_accessibility_preferences()
            self.configure(bg=COLORS["bg"])
            self.rebuild_shell(first_view, refresh_styles=True, use_cover=not hidden)

        self.run_hidden_change(lambda: rebuild(True), fallback=lambda: rebuild(False))
        if not take_tour:
            self.toast_message("All set. Press ? at the top any time for a quick tour.")

    def show_tour_view(self, view):
        """Switch pages for a tour step with the new page and tour card built out of sight."""
        self.run_hidden_change(lambda: self.show_view(view))

    def start_tour(self):
        persona_key = self.store.onboarding.get("persona") or "general"
        self.tour = {"persona": persona_key, "index": 0}
        self.show_tour_view(onboarding.tour_steps(persona_key)[0][0])

    def move_tour(self, step):
        if not self.tour:
            return
        steps = onboarding.tour_steps(self.tour["persona"])
        index = self.tour["index"] + step
        if index >= len(steps):
            self.end_tour("That's the tour. Press ? at the top any time to see it again.")
            return
        self.tour["index"] = max(0, index)
        self.show_tour_view(steps[self.tour["index"]][0])

    def end_tour(self, message="Tour closed. Press ? at the top any time to see it again."):
        self.tour = None
        card = getattr(self, "tour_card", None)
        if card is not None and card.winfo_exists():
            card.destroy()
        self.tour_card = None
        self.toast_message(message)

    def render_tour_card(self):
        old = getattr(self, "tour_card", None)
        if old is not None and old.winfo_exists():
            old.destroy()
        self.tour_card = None
        if not self.tour or not hasattr(self, "main") or not self.main.winfo_exists():
            return
        steps = onboarding.tour_steps(self.tour["persona"])
        index = min(self.tour["index"], len(steps) - 1)
        _view, title, body = steps[index]
        last = index == len(steps) - 1
        card = tk.Frame(self.main, bg=COLORS["alt"], padx=self.px(22), pady=self.px(18))
        card.place(relx=1.0, rely=1.0, anchor="se", x=-self.px(52), y=-self.px(34), width=self.px(460))
        tk.Label(card, text=f"Guided tour  \u2022  step {index + 1} of {len(steps)}", bg=COLORS["alt"], fg=COLORS["primary"], font=self.font("Segoe UI Semibold", 10), anchor="w").pack(fill="x")
        self.fit_wrap(tk.Label(card, text=title, bg=COLORS["alt"], fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 16), anchor="w", justify="left", wraplength=self.px(410)), pady=(self.px(4), 0))
        body = platform_text(body)
        text = tk.Label(card, text=body, bg=COLORS["alt"], fg=COLORS["muted"], font=self.font("Segoe UI", 12), anchor="w", justify="left", wraplength=self.px(410))
        self.fit_wrap(text, pady=(self.px(6), self.px(14)))
        buttons = [("Back", lambda: self.move_tour(-1), "TButton")] if index else []
        buttons += [("Finish" if last else "Next", lambda: self.move_tour(1), "Primary.TButton"), ("End Tour", self.end_tour, "TButton")]
        row = tk.Frame(card, bg=COLORS["alt"])
        row.pack(fill="x")
        for column, (label, command, style_name) in enumerate(buttons):
            button = self.row_button(row, label, command, style_name)
            button.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else self.px(8), 0))
            row.columnconfigure(column, weight=2 if style_name == "Primary.TButton" else 1)
        self.raise_widget(card)
        self.tour_card = card
        if self.accessibility.get("read_aloud"):
            self.speak(f"{title}. {body}")

    HUB_INTROS = {
        "study": "Answer from memory first, then rate how it went. Easy cards come back later; hard ones sooner.",
        "create": "Add what you want to remember, keep it in decks, and give it cues that help it stick.",
        "practice": "Techniques that make memories stronger, gentle everyday support, and short recall games.",
    }

    def view_study(self):
        self.view_hub("study")

    def view_create(self):
        self.view_hub("create")

    def view_practice(self):
        self.view_hub("practice")

    def icon_badge(self, parent, icon, size=40):
        """A page symbol on a soft neutral tile, in the one accent colour."""
        bg = parent.cget("bg")
        badge_size = self.px(size)
        badge = tk.Canvas(parent, width=badge_size, height=badge_size, bg=bg, highlightthickness=0)
        self.draw_antialiased_shape(badge, badge_size, badge_size, self.blend_hex(bg, COLORS["primary"], 0.10), radius=self.px(10))
        image = self.line_icon(icon, self.px(round(size * 0.58)), COLORS["primary"])
        if image is not None:
            badge.create_image(badge_size // 2, badge_size // 2, image=image, anchor="center")
            badge._memorypal_icon = image
        return badge

    def hub_page_note(self, view):
        """A short live count for a hub tile, or "" when there's nothing to count."""
        store = self.store
        if view == "review":
            due = len(store.due_cards())
            return f"{due} card{'s' if due != 1 else ''} due now" if due else "Nothing due right now"
        if view == "focus":
            weak = len(store.weak_cards())
            return f"{weak} card{'s' if weak != 1 else ''} to strengthen" if weak else ""
        if view == "talkback":
            return "Answer out loud" if listen.platform_supported() else "Read aloud, answer by typing"
        if view == "library":
            count = len(store.cards)
            return f"{count} card{'s' if count != 1 else ''} saved"
        if view == "decks":
            count = len(store.decks())
            return f"{count} deck{'s' if count != 1 else ''}"
        return ""

    def view_hub(self, hub):
        """A section page: one clickable tile per page it holds, in this profile's page order."""
        page = ScrollFrame(self.view_host)
        page.pack(fill="both", expand=True)
        intro = ttk.Label(page.inner, text=self.HUB_INTROS.get(hub, ""), style="Muted.TLabel", wraplength=self.px(1040))
        intro.pack(anchor="w", padx=(0, 8), pady=(0, self.px(14)))

        labels = {key: label for key, label, _short in self.default_nav_items()}
        order = {key: index for index, (key, _label, _short) in enumerate(self.ordered_nav_items())}
        pages = sorted(self.HUB_PAGES[hub], key=lambda key: order.get(key, len(order)))

        tiles = ttk.Frame(page.inner, style="Page.TFrame")
        tiles.pack(fill="both", expand=True, padx=(0, 8))
        for column in range(2):
            tiles.columnconfigure(column, weight=1, uniform=f"hub-{hub}")
        for index, key in enumerate(pages):
            row, column = divmod(index, 2)
            title = self.page_titles().get(key, ("", labels.get(key, key)))[1]
            tile = self.hover_card(
                tk.Frame(tiles, bg=COLORS["surface"], padx=self.px(20), pady=self.px(18)),
                command=lambda view=key: self.show_view(view),
            )
            tile.grid(row=row, column=column, sticky="nsew", padx=(0 if column == 0 else self.px(12), 0), pady=(0, self.px(12)))
            self.icon_badge(tile, key).pack(anchor="w", pady=(0, self.px(10)))
            tk.Label(tile, text=title, bg=COLORS["surface"], fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 15), anchor="w").pack(fill="x")
            tk.Label(tile, text=self.nav_hint(key), bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI", 11), wraplength=self.px(500), justify="left", anchor="w").pack(fill="x", pady=(self.px(5), 0))
            note = self.hub_page_note(key)
            if note:
                tk.Label(tile, text=note, bg=COLORS["surface"], fg=COLORS["primary"], font=self.font("Segoe UI Semibold", 11), anchor="w").pack(fill="x", pady=(self.px(8), 0))
            # The whole tile is clickable; the button is a quiet secondary one
            # (five bright filled buttons competed with each other and with the
            # page's real next step) that gives keyboard users a focus stop.
            # Packed to the bottom so the buttons in a row line up even when
            # one tile's description runs to an extra line.
            ttk.Button(tile, text="Open", style="TButton", command=lambda view=key: self.show_view(view)).pack(side="bottom", anchor="w", pady=(self.px(14), 0))

        # Rows share the visible height (up to a comfortable cap), so four
        # tiles fill the page instead of sitting in its top half above an
        # empty band. Hubs with more tiles than fit simply scroll.
        rows = max(1, (len(pages) + 1) // 2)
        gutter = self.px(12)
        cap = self.px(250)

        def fit_rows(_event=None):
            try:
                if not tiles.winfo_exists():
                    return
                spare = page.viewport.winfo_height() - intro.winfo_height() - self.px(14) - self.px(18)
            except tk.TclError:
                return
            height = max(0, min(cap, int(spare / rows) - gutter))
            for row in range(rows):
                tiles.rowconfigure(row, minsize=height + gutter)

        page.viewport.bind("<Configure>", fit_rows, add="+")
        self.after_idle(fit_rows)

    def view_training(self):
        page = ScrollFrame(self.view_host)
        page.pack(fill="both", expand=True)

        hero = self.hover_card(tk.Frame(page.inner, bg=COLORS["surface"], padx=self.px(28), pady=self.px(26), highlightthickness=1, highlightbackground=COLORS["line"]))
        hero.pack(fill="x", padx=(0, 8), pady=(0, 16))
        tk.Label(hero, text="Memory Gym", bg=COLORS["surface"], fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 24)).pack(anchor="w")
        tk.Label(
            hero,
            text="Choose a study path or a gentle recall path. The same saved cards, notes, images, audio, and video cues stay available across the app.",
            bg=COLORS["surface"],
            fg=COLORS["muted"],
            font=self.font("Segoe UI", 12),
            wraplength=self.px(1020),
            justify="left",
        ).pack(anchor="w", pady=(6, 0))

        grid = ttk.Frame(page.inner, style="Page.TFrame")
        grid.pack(fill="both", expand=True, padx=(0, 8))
        for column in range(2):
            grid.columnconfigure(column, weight=1, uniform="training")

        def technique_tile(parent, row, column, title, body, target, color):
            tile = self.hover_card(tk.Frame(parent, bg=COLORS["surface"], padx=self.px(20), pady=self.px(18), highlightthickness=1, highlightbackground=COLORS["line"]), hover=color, command=lambda view=target: self.show_view(view))
            tile.grid(row=row, column=column, sticky="nsew", padx=(0 if column == 0 else self.px(12), 0), pady=(0, self.px(12)))
            tk.Frame(tile, bg=color, width=self.px(32), height=self.px(3)).pack(anchor="w", pady=(0, self.px(10)))
            tk.Label(tile, text=title, bg=COLORS["surface"], fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 15), anchor="w").pack(fill="x")
            tk.Label(tile, text=body, bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI", 10), wraplength=self.px(500), justify="left").pack(fill="x", pady=(self.px(5), self.px(12)))
            self.solid_button(tile, "Open Technique", lambda view=target: self.show_view(view), color).pack(fill="x")

        student = self.card(grid, "AltCard.TFrame", 22)
        student.grid(row=0, column=0, sticky="nsew", padx=(0, self.px(12)), pady=(0, self.px(12)))
        ttk.Label(student, text="Student study track", style="AltH2.TLabel").pack(anchor="w")
        ttk.Label(student, text="Best for school topics, exam prep, language learning, and revision sessions.", style="AltMuted.TLabel", wraplength=self.px(520)).pack(anchor="w", pady=(4, 0))

        older = self.card(grid, "WarmCard.TFrame", 22)
        older.grid(row=0, column=1, sticky="nsew", pady=(0, self.px(12)))
        ttk.Label(older, text="Everyday memory track", style="WarmH2.TLabel").pack(anchor="w")
        ttk.Label(older, text="Gentle activities for names, routines, attention, confidence, and daily reminders.", style="WarmCard.TLabel", wraplength=self.px(520)).pack(anchor="w", pady=(4, 0))

        tiles = ttk.Frame(page.inner, style="Page.TFrame")
        tiles.pack(fill="both", expand=True, padx=(0, 8))
        for column in range(2):
            tiles.columnconfigure(column, weight=1, uniform="techniques")

        techniques = [
            ("Retrieval practice", "Answer first, reveal later, and let Smart Check place the card in the right review bucket.", "testing", COLORS["primary"]),
            ("Spaced practice", "Review across time instead of cramming. Due cards and the study plan help pace each session.", "review", COLORS["green"]),
            ("Interleaving", "Mix related topics so practice feels closer to a real test and less like memorizing one block.", "quiz", COLORS["orange"]),
            ("Elaboration", "Ask why, how, and what it connects to. Associations turns plain notes into stronger hooks.", "tools", COLORS["violet"]),
            ("Concrete examples", "Attach real examples, images, notes, and media cues so abstract ideas have something to stick to.", "capture", COLORS["pink"]),
            ("Dual coding", "Pair words with visual, audio, or video cues in Cue Lab for more than one route back to the memory.", "cuelab", COLORS["cyan"]),
            ("Spaced retrieval", "Practice small answers at increasing intervals, useful for names, routines, and important facts.", "shuffle", COLORS["green"]),
            ("Attention games", "Use short puzzle rounds such as visual search, missing item, pair recall, and n-back warmups.", "games", COLORS["primary"]),
            ("Category sorting", "Group everyday or school items to strengthen organization and long-term recall.", "games", COLORS["orange"]),
            ("Routine recall", "Practise short step-by-step routines with a calm show-hide-check flow.", "games", COLORS["pink"]),
        ]
        for index, item in enumerate(techniques):
            row, column = divmod(index, 2)
            technique_tile(tiles, row, column, *item)

    def view_elder(self):
        draft = self.view_drafts.get("elder", {})
        page = ScrollFrame(self.view_host)
        page.pack(fill="both", expand=True)
        simple = self.accessibility.get("simple_language", False)

        hero = self.hover_card(tk.Frame(page.inner, bg=COLORS["surface"], padx=self.px(30), pady=self.px(28), highlightthickness=1, highlightbackground=COLORS["line"]))
        hero.pack(fill="x", padx=(0, 8), pady=(0, 16))
        tk.Frame(hero, bg=COLORS["cyan"], width=self.px(46), height=self.px(5)).pack(anchor="w", pady=(0, 14))
        tk.Label(hero, text="Everyday Memory", bg=COLORS["surface"], fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 24)).pack(anchor="w")
        intro = "Simple memory support for people, routines, places, reminders, and calm practice." if simple else "A calm support area for older adults, people with memory changes, and caregivers who want simple prompts, familiar cues, routines, and short confidence-building practice."
        tk.Label(hero, text=intro, bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI", 13), wraplength=self.px(900), justify="left").pack(anchor="w", pady=(6, 0))

        today_card = self.card(page.inner, "WarmCard.TFrame", 30)
        today_card.pack(fill="x", padx=(0, 8), pady=(0, 16))
        ttk.Label(today_card, text="Today board", style="WarmH2.TLabel").pack(anchor="w", pady=(0, self.px(10)))
        today_lines = [
            f"Today is {date.today().strftime('%A, %B %d, %Y')}.",
            f"Active profile: {active_profile_name()}.",
            f"Reviews due now: {len(self.store.due_cards())}.",
            "One small step is enough: review one card, add one reminder, or play one gentle puzzle.",
        ]
        today_copy = ttk.Frame(today_card, style="WarmCard.TFrame")
        today_copy.pack(fill="x", pady=(0, self.px(16)))
        for line in today_lines:
            ttk.Label(today_copy, text=line, style="WarmCard.TLabel", wraplength=self.px(1040), justify="left").pack(anchor="w", pady=(0, self.px(7)))
        today_actions = ttk.Frame(today_card, style="WarmCard.TFrame")
        today_actions.pack(fill="x")
        self.button_row(
            today_actions,
            [
                ("Start Gentle Review", lambda: self.start_everyday_review(), "Primary.TButton"),
                ("Use Senior Layout", self.apply_senior_layout_defaults, "TButton"),
                ("Open Puzzles", lambda: self.show_view("games"), "TButton"),
            ],
            "WarmCard.TFrame",
        )

        builder = self.card(page.inner, "Card.TFrame", 22)
        builder.pack(fill="x", padx=(0, 8), pady=(0, 16))
        ttk.Label(builder, text="Caregiver card builder", style="H2.TLabel").pack(anchor="w")
        builder_help = "Make one clear memory card at a time. A helper can add photos, audio, or video from Capture after the card is saved." if simple else "Create respectful everyday cards for names, relationships, routines, places, and reminders. These become normal MemoryPal cards, so they can be reviewed in Test Lab and mixed with audio, image, video, or text cues."
        ttk.Label(builder, text=builder_help, style="CardMuted.TLabel", wraplength=self.px(900), justify="left").pack(anchor="w", pady=(4, 12))
        kind_var = tk.StringVar(value=draft.get("elder_kind", "Person"))
        self.select_button(builder, kind_var, ["Person", "Routine", "Place", "Reminder"]).pack(fill="x", pady=(0, self.px(10)))
        prompt_var = tk.StringVar(value=draft.get("elder_prompt", "Who is this person?"))
        prompt_entry = ttk.Entry(builder, textvariable=prompt_var)
        prompt_entry.pack(fill="x", pady=(0, self.px(10)))
        answer_box = self.answer_area(builder, "Answer or helpful cue", "Example: This is Maya, your granddaughter. She visits on Sundays.", 4)
        answer_box.insert("1.0", draft.get("elder_answer", ""))
        notes_box = self.answer_area(builder, "Optional gentle note", "Example: Show a family photo, play a familiar voice note, or use a short routine.", 3)
        notes_box.insert("1.0", draft.get("elder_notes", ""))

        def apply_kind_prompt(*_args):
            if normalize_space(prompt_var.get()) and prompt_var.get() not in {
                "Who is this person?",
                "What are the steps?",
                "Where does this belong?",
                "What should I remember?",
            }:
                return
            prompt_var.set({
                "Person": "Who is this person?",
                "Routine": "What are the steps?",
                "Place": "Where does this belong?",
                "Reminder": "What should I remember?",
            }.get(kind_var.get(), "What should I remember?"))

        kind_var.trace_add("write", apply_kind_prompt)

        def add_everyday_card():
            prompt = normalize_space(prompt_var.get())
            answer = normalize_space(answer_box.get("1.0", "end"))
            note = normalize_space(notes_box.get("1.0", "end"))
            if not prompt or not answer:
                self.toast_message("Add a prompt and answer first.")
                return
            kind = kind_var.get()
            card = Card(
                deck="Everyday Memory",
                front=prompt,
                back=answer,
                pathway=f"Everyday Memory > {kind}",
                association=note or f"Use one familiar cue for this {kind.lower()} card.",
            )
            self.store.add_card(card)
            answer_box.delete("1.0", "end")
            notes_box.delete("1.0", "end")
            self.toast_message(f"{kind} card added.")

        def load_everyday_starters():
            starters = [
                ("Who is a family member I want to remember?", "Say the person's name, relationship, and one familiar detail."),
                ("What are my morning steps?", "Check the date, drink water, take medicine if prescribed, and put keys in the usual place."),
                ("Where do my keys belong?", "The keys belong in the same bowl or hook near the door."),
                ("What appointment should I ask about?", "Look at today's calendar or ask a caregiver to confirm the next appointment."),
                ("What helps me feel calm?", "Pause, breathe slowly, look at a familiar photo, and ask for help if needed."),
            ]
            existing = {(card.front, card.back) for card in self.store.cards}
            added = 0
            for front, back in starters:
                if (front, back) in existing:
                    continue
                self.store.cards.insert(0, Card(deck="Everyday Memory", front=front, back=back, pathway="Everyday Memory > Starter", association="Keep the wording short and familiar."))
                added += 1
            if added:
                self.store.save()
                self.toast_message(f"Added {added} starter cards.")
            else:
                self.toast_message("Starter cards already exist.")

        self.button_row(
            builder,
            [
                ("Add Person Card", lambda: (kind_var.set("Person"), add_everyday_card()), "Primary.TButton"),
                ("Add Routine Card", lambda: (kind_var.set("Routine"), add_everyday_card()), "TButton"),
                ("Add Place Card", lambda: (kind_var.set("Place"), add_everyday_card()), "TButton"),
                ("Add Reminder Card", lambda: (kind_var.set("Reminder"), add_everyday_card()), "TButton"),
            ],
        )
        self.button_row(builder, [("Create Starter Set", load_everyday_starters, "Primary.TButton"), ("Open Caregiver Notes", lambda: self.show_view("capture"), "TButton")])

        grid = ttk.Frame(page.inner, style="Page.TFrame")
        grid.pack(fill="x", padx=(0, 8), pady=(0, 16))
        idea_columns = 1 if self.accessibility_multiplier() > 1.1 else 2
        for column in range(idea_columns):
            grid.columnconfigure(column, weight=1, uniform="elder")
        ideas = [
            ("People & names", "Use one photo, one name, one relationship, and one warm detail. Keep the answer short.", COLORS["primary"]),
            ("Routine practice", "Use Routine Recall for two to four steps. Missing a step means the routine needs another calm pass.", COLORS["green"]),
            ("Where things belong", "Practise common places: keys, glasses, medicine list, phone charger, appointment card.", COLORS["orange"]),
            ("Caregiver support", "Add cues with a familiar voice, a real photo, or plain words. Avoid surprise sounds or clutter.", COLORS["violet"]),
        ]
        for index, (title, body, color) in enumerate(ideas):
            tile = self.hover_card(tk.Frame(grid, bg=COLORS["surface"], padx=self.px(22), pady=self.px(20), highlightthickness=1, highlightbackground=COLORS["line"]))
            row, column = divmod(index, idea_columns)
            tile.grid(row=row, column=column, sticky="nsew", padx=(0 if column == 0 else self.px(12), 0), pady=(0, self.px(12)))
            tk.Frame(tile, bg=color, width=self.px(36), height=self.px(4)).pack(anchor="w", pady=(0, self.px(12)))
            tk.Label(tile, text=title, bg=COLORS["surface"], fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 16)).pack(anchor="w")
            tk.Label(tile, text=body, bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI", 12), wraplength=self.px(820 if idea_columns == 1 else 430), justify="left").pack(anchor="w", pady=(self.px(6), 0))

        safety = self.card(page.inner, "AltCard.TFrame", 20)
        safety.pack(fill="x", padx=(0, 8))
        ttk.Label(safety, text="Care note", style="AltH2.TLabel").pack(anchor="w")
        ttk.Label(safety, text="MemoryPal can support practice and reminders, but it is not a medical device, emergency tool, or replacement for professional care. For urgent safety concerns, use the person's normal care plan or emergency contacts.", style="AltCard.TLabel", wraplength=self.px(900), justify="left").pack(anchor="w", pady=(4, 0))
        self.register_draft_saver("elder", lambda: {
            "elder_kind": kind_var.get(),
            "elder_prompt": prompt_var.get(),
            "elder_answer": answer_box.get("1.0", "end").strip(),
            "elder_notes": notes_box.get("1.0", "end").strip(),
        })

    def start_everyday_review(self):
        everyday = [card for card in self.store.due_cards() if (card.deck or "General") == "Everyday Memory"]
        if not everyday:
            everyday = [card for card in self.store.cards if (card.deck or "General") == "Everyday Memory"]
        if not everyday:
            everyday = self.store.due_cards() or self.store.cards
        if not everyday:
            self.toast_message("Add an Everyday Memory card first.")
            return
        self.current_review = everyday[0]
        self.open_testing(everyday[0], "elder", "everyday")

    # ------------------------------------------------------------------
    # Small chart kit (plain Tk canvases that redraw when resized)
    # ------------------------------------------------------------------
    def blend_hex(self, first, second, ratio):
        a = self.hex_to_rgb(first)
        b = self.hex_to_rgb(second)
        if a is None or b is None:
            return first
        return "#" + "".join(f"{round(x + (y - x) * ratio):02x}" for x, y in zip(a, b))

    @staticmethod
    def short_number(value):
        if isinstance(value, float) and not value.is_integer():
            return f"{value:.1f}"
        value = int(value)
        return f"{value / 1000:.1f}k" if value >= 1000 else str(value)

    def chart_canvas(self, parent, height, draw, bg=None):
        """A canvas that fills its width and redraws its chart whenever resized."""
        bg = bg or COLORS["surface"]
        pixel_height = self.px(height)
        canvas = tk.Canvas(parent, width=1, height=pixel_height, bg=bg, highlightthickness=0, bd=0)
        state = {"width": 0}

        def redraw(event=None):
            width = event.width if event is not None else canvas.winfo_width()
            if width <= 1 or width == state["width"]:
                return
            state["width"] = width
            canvas.delete("all")
            draw(canvas, width, pixel_height)

        canvas.bind("<Configure>", redraw, add="+")
        return canvas

    def bar_chart(self, parent, values, labels, color, height=150, highlight=None, tips=None, on_click=None, bg=None):
        bg = bg or COLORS["surface"]
        values = list(values)
        small = self.font("Segoe UI", 9)
        bold = self.font("Segoe UI Semibold", 9)

        def draw(canvas, width, h):
            count = max(1, len(values))
            top, bottom = self.px(20), self.px(22)
            plot = max(1, h - top - bottom)
            peak = max(values) if values and max(values) > 0 else 1
            slot = width / count
            bar_w = max(self.px(4), min(self.px(44), slot * 0.62))
            soft = self.blend_hex(color, bg, 0.5)
            longest = max((len(str(label)) for label in labels), default=1) if labels else 1
            every = max(1, math.ceil(count * self.px(10 + 7 * longest) / max(1, width)))
            show_values = count <= 16
            baseline = top + plot
            canvas.create_line(0, baseline, width, baseline, fill=COLORS["line"])
            for index, value in enumerate(values):
                cx = slot * index + slot / 2
                bar_h = plot * value / peak
                fill = color if highlight is None or index == highlight else soft
                if value > 0:
                    canvas.create_rectangle(cx - bar_w / 2, baseline - max(self.px(2), bar_h), cx + bar_w / 2, baseline, fill=fill, outline="")
                    if show_values:
                        canvas.create_text(cx, baseline - bar_h - self.px(3), text=self.short_number(value), anchor="s", fill=COLORS["muted"], font=bold)
                # Label every Nth bar, always the highlighted one, and never a
                # neighbour close enough to collide with the highlighted label.
                near_highlight = highlight is not None and index != highlight and abs(index - highlight) < every
                if labels and (index == highlight or (index % every == 0 and not near_highlight)):
                    item = canvas.create_text(cx, baseline + self.px(5), text=labels[index], anchor="n", fill=COLORS["ink"] if index == highlight else COLORS["muted"], font=bold if index == highlight else small)
                    x0, _y0, x1, _y1 = canvas.bbox(item)
                    if x0 < 0:
                        canvas.move(item, -x0, 0)
                    elif x1 > width:
                        canvas.move(item, width - x1, 0)

            def index_at(x):
                return min(count - 1, max(0, int(x // slot)))

            def hover(event):
                canvas.delete("tip")
                if not tips:
                    return
                index = index_at(event.x)
                cx = slot * index + slot / 2
                text = canvas.create_text(0, 0, text=tips[index], anchor="n", fill=COLORS["white"], font=bold, tags="tip")
                x0, y0, x1, y1 = canvas.bbox(text)
                half = (x1 - x0) / 2 + self.px(8)
                cx = min(max(cx, half), width - half)
                canvas.coords(text, cx, self.px(4))
                x0, y0, x1, y1 = canvas.bbox(text)
                pad = self.px(6)
                box = canvas.create_rectangle(x0 - pad, y0 - self.px(3), x1 + pad, y1 + self.px(3), fill=COLORS["rail"], outline="", tags="tip")
                canvas.tag_raise(text, box)

            canvas.bind("<Motion>", hover)
            canvas.bind("<Leave>", lambda _event: canvas.delete("tip"))
            if on_click:
                canvas.configure(cursor="hand2")
                canvas.bind("<Button-1>", lambda event: on_click(index_at(event.x)))

        return self.chart_canvas(parent, height, draw, bg)

    def stacked_bar(self, parent, segments, height=28, bg=None):
        total = sum(value for _label, value, _color in segments)

        def draw(canvas, width, h):
            canvas.create_rectangle(0, 0, width, h, fill=COLORS["line"], outline="")
            if not total:
                return
            x = 0
            for _label, value, color in segments:
                if value <= 0:
                    continue
                span = width * value / total
                canvas.create_rectangle(x, 0, x + span, h, fill=color, outline="")
                if span > self.px(34):
                    canvas.create_text(x + span / 2, h / 2, text=str(value), fill=self.on_color(color), font=self.font("Segoe UI Semibold", 10))
                x += span

        return self.chart_canvas(parent, height, draw, bg)

    def chart_legend(self, parent, items, bg=None):
        bg = bg or COLORS["surface"]
        row = tk.Frame(parent, bg=bg)
        for label, color in items:
            tk.Frame(row, bg=color, width=self.px(10), height=self.px(10)).pack(side="left", padx=(0, self.px(6)))
            tk.Label(row, text=label, bg=bg, fg=COLORS["muted"], font=self.font("Segoe UI", 10)).pack(side="left", padx=(0, self.px(14)))
        return row

    def meter(self, parent, fraction, color, height=10, bg=None):
        fraction = clamp(fraction, 0, 1)

        def draw(canvas, width, h):
            canvas.create_rectangle(0, 0, width, h, fill=COLORS["line"], outline="")
            if fraction > 0:
                canvas.create_rectangle(0, 0, max(self.px(3), width * fraction), h, fill=color, outline="")

        return self.chart_canvas(parent, height, draw, bg)

    def meter_rows(self, parent, rows, bg=None):
        """Label | bar | note rows; rows are (label, value, maximum, color, note)."""
        bg = bg or COLORS["surface"]
        table = tk.Frame(parent, bg=bg)
        table.columnconfigure(1, weight=1)
        for index, (label, value, maximum, color, note) in enumerate(rows):
            tk.Label(table, text=label, bg=bg, fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 11), anchor="w").grid(row=index, column=0, sticky="w", padx=(0, self.px(12)), pady=self.px(5))
            self.meter(table, 0 if maximum <= 0 else value / maximum, color, 12, bg).grid(row=index, column=1, sticky="ew")
            tk.Label(table, text=note, bg=bg, fg=COLORS["muted"], font=self.font("Segoe UI", 10), anchor="e").grid(row=index, column=2, sticky="e", padx=(self.px(12), 0))
        return table

    def panel_row(self, parent, count, per_row=None):
        """A row of plain surface panels that stacks for large text."""
        per_row = per_row or count
        if self.accessibility_multiplier() > 1.1:
            per_row = min(per_row, 2 if count >= 4 else 1)
        row = tk.Frame(parent, bg=COLORS["bg"])
        row.pack(fill="x", padx=(0, 8), pady=(0, self.px(16)))
        gap = self.px(14)
        cells = []
        for index in range(count):
            r, c = divmod(index, per_row)
            cell = tk.Frame(row, bg=COLORS["surface"], padx=self.px(22), pady=self.px(20))
            cell.grid(row=r, column=c, sticky="nsew", padx=(0 if c == 0 else gap, 0), pady=(0 if r == 0 else gap, 0))
            cells.append(cell)
        for c in range(per_row):
            row.columnconfigure(c, weight=1, uniform=f"panels{count}")
        return cells

    def panel_title(self, panel, title, subtitle=None):
        tk.Label(panel, text=title, bg=panel.cget("bg"), fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 15), anchor="w").pack(fill="x")
        if subtitle:
            tk.Label(panel, text=subtitle, bg=panel.cget("bg"), fg=COLORS["muted"], font=self.font("Segoe UI", 10), wraplength=self.px(600), justify="left").pack(anchor="w", pady=(self.px(2), 0))
        tk.Frame(panel, bg=panel.cget("bg"), height=self.px(12)).pack(fill="x")

    # ------------------------------------------------------------------
    # Dashboard: today's path, a fun progress strip, modes, next badge
    # ------------------------------------------------------------------
    def view_dashboard(self):
        page = ScrollFrame(self.view_host)
        page.pack(fill="both", expand=True)
        path = tk.Frame(page.inner, bg=COLORS["surface"], padx=self.px(28), pady=self.px(24))
        path.pack(fill="x", padx=(0, 8), pady=(0, self.px(16)))
        self.render_today_path(path)
        self.render_progress_strip(page.inner)
        self.render_study_modes(page.inner)
        self.render_next_badge(page.inner)

    def greeting(self):
        hour = datetime.now().hour
        return "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"

    def best_next_action(self):
        due = self.store.due_cards()
        weak = self.store.weak_cards()
        if due:
            return "Start today's review", f"{len(due)} card{'s' if len(due) != 1 else ''} are ready for you." if len(due) != 1 else "1 card is ready for you.", lambda: self.show_view("review"), COLORS["primary"]
        if weak:
            return "Strengthen shaky cards", f"{len(weak)} card{'s' if len(weak) != 1 else ''} could use a confidence pass.", lambda: self.show_view("focus"), COLORS["pink"]
        if not self.store.captures:
            return "Add something to learn", "Paste notes or type questions and answers to build your first set.", lambda: self.show_view("capture"), COLORS["orange"]
        return "Try a quick quiz", "Everything is up to date. A short quiz keeps recall fresh.", lambda: self.show_view("quiz"), COLORS["green"]

    def render_today_path(self, box):
        for child in box.winfo_children():
            child.destroy()
        bg = COLORS["surface"]
        today = plan_for_today(self.store)
        head = tk.Frame(box, bg=bg)
        head.pack(fill="x")
        head.columnconfigure(0, weight=1)
        text = tk.Frame(head, bg=bg)
        text.grid(row=0, column=0, sticky="nsew")
        tk.Label(text, text=self.greeting(), bg=bg, fg=COLORS["muted"], font=self.font("Segoe UI", 12), anchor="w").pack(fill="x")
        buttons = tk.Frame(head, bg=bg)
        buttons.grid(row=0, column=1, sticky="ne", padx=(self.px(16), 0))

        if not today:
            title, body, action, _color = self.best_next_action()
            tk.Label(text, text=title, bg=bg, fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 24), anchor="w").pack(fill="x", pady=(self.px(2), 0))
            tk.Label(text, text=body, bg=bg, fg=COLORS["muted"], font=self.font("Segoe UI", 13), wraplength=self.px(620), justify="left").pack(anchor="w", pady=(self.px(6), 0))
            self.solid_button(buttons, title, action).pack(fill="x")
            ttk.Button(buttons, text="Make a study plan", command=lambda: self.show_view("plan")).pack(fill="x", pady=(self.px(8), 0))
            self.fit_wrap(tk.Label(box, text="A saved study plan turns this into a step-by-step path for each day.", bg=bg, fg=COLORS["muted"], font=self.font("Segoe UI", 11), wraplength=self.px(900), justify="left"), pady=(self.px(16), 0))
            return

        if today["finished"]:
            tk.Label(text, text="You finished your plan", bg=bg, fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 24), anchor="w").pack(fill="x", pady=(self.px(4), 0))
            tk.Label(text, text=f"{today['title']}. Make a new plan to keep the momentum going, or just keep reviewing what's due.", bg=bg, fg=COLORS["muted"], font=self.font("Segoe UI", 13), wraplength=self.px(620), justify="left").pack(anchor="w", pady=(self.px(6), 0))
            self.solid_button(buttons, "Make a new plan", lambda: self.show_view("plan"), COLORS["primary"]).pack(fill="x")
            ttk.Button(buttons, text="Review due cards", command=lambda: self.show_view("review")).pack(fill="x", pady=(self.px(8), 0))
            return

        steps = today["steps"]
        done = {index for index in self.store.plan_steps_done() if index < len(steps)}
        remaining = [index for index in range(len(steps)) if index not in done]
        heading = "Your plan is done for today" if not remaining else "Your study plan for today"
        tk.Label(text, text=heading, bg=bg, fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 24), anchor="w").pack(fill="x", pady=(self.px(4), 0))
        tk.Label(text, text=today["title"], bg=bg, fg=COLORS["muted"], font=self.font("Segoe UI", 12), wraplength=self.px(620), justify="left").pack(anchor="w", pady=(self.px(4), 0))
        if remaining:
            step = steps[remaining[0]]
            self.solid_button(buttons, f"Continue: {step['title']}", lambda s=step: self.start_plan_step(s), COLORS["primary"]).pack(fill="x")
        else:
            self.solid_button(buttons, "Keep going: quick quiz", lambda: self.show_view("quiz")).pack(fill="x")
        ttk.Button(buttons, text="Edit plan", command=lambda: self.show_view("plan")).pack(fill="x", pady=(self.px(8), 0))

        progress_row = tk.Frame(box, bg=bg)
        progress_row.pack(fill="x", pady=(self.px(16), self.px(12)))
        progress_row.columnconfigure(0, weight=1)
        self.meter(progress_row, len(done) / max(1, len(steps)), COLORS["green"], 10, bg).grid(row=0, column=0, sticky="ew")
        tk.Label(progress_row, text=f"{len(done)} of {len(steps)} steps", bg=bg, fg=COLORS["muted"], font=self.font("Segoe UI Semibold", 10)).grid(row=0, column=1, padx=(self.px(12), 0))

        @self.smooth
        def toggle(index):
            now_done = self.store.toggle_plan_step(index)
            if now_done and len(self.store.plan_steps_done()) >= len(steps):
                self.toast_message("Plan done for today. Nice work! \U0001F389")
            self.render_today_path(box)
            self.fit_wrap_tree(box)

        for index, step in enumerate(steps):
            self.plan_step_row(box, index, step, index in done, toggle)
        tk.Label(box, text="Tick each step when you finish it.", bg=bg, fg=COLORS["muted"], font=self.font("Segoe UI", 10)).pack(anchor="w", pady=(self.px(2), 0))

    def plan_step_row(self, parent, index, step, done, on_toggle):
        bg = COLORS["alt"]
        row = tk.Frame(parent, bg=bg, padx=self.px(14), pady=self.px(10))
        row.pack(fill="x", pady=(0, self.px(8)))
        mark = tk.Label(
            row,
            text="\u2713" if done else str(index + 1),
            width=3,
            bg=COLORS["green"] if done else COLORS["surface"],
            fg=self.on_color(COLORS["green"]) if done else COLORS["primary"],
            font=self.font("Segoe UI Semibold", 12),
            cursor="hand2",
            pady=self.px(4),
        )
        mark.pack(side="left", padx=(0, self.px(14)))
        self.keyboard_link(mark, lambda _event: on_toggle(index))
        self.add_tooltip(mark, "Mark as not done yet." if done else "Tick this step as done.")
        action = "Rest" if step.get("view") == "break" else "Start"
        start = ttk.Button(row, text=action, command=lambda s=step: self.start_plan_step(s))
        start.pack(side="right", padx=(self.px(12), 0))
        body = tk.Frame(row, bg=bg)
        body.pack(side="left", fill="x", expand=True)
        tk.Label(body, text=step["title"], bg=bg, fg=COLORS["muted"] if done else COLORS["ink"], font=self.font("Segoe UI Semibold", 13), anchor="w").pack(fill="x")
        tk.Label(body, text=f"~{step['minutes']} min", bg=bg, fg=COLORS["muted"], font=self.font("Segoe UI", 10), anchor="w").pack(fill="x")
        return row

    def render_progress_strip(self, parent):
        streak = self.store.current_streak()
        best = max(streak, progress.best_streak(self.store.activity))
        today = self.store.today_count()
        goal = self.store.daily_goal
        level = progress.level_info(self.store.practiced)
        week = progress.daily_series(self.store.activity, 7)
        streak_panel, goal_panel, level_panel, week_panel = self.panel_row(parent, 4)

        tk.Label(streak_panel, text=f" {streak}", image=self.line_icon("flame", self.px(34), COLORS["warm_text"]) or "", compound="left", bg=COLORS["surface"], fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 28), anchor="w").pack(fill="x")
        tk.Label(streak_panel, text=f"day streak" if streak == 1 else "days in a row", bg=COLORS["surface"], fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 13), anchor="w").pack(fill="x")
        message = "Practise today to start one." if streak == 0 else ("Practise today to keep it going." if today == 0 else "Kept alive today.")
        tk.Label(streak_panel, text=f"{message} Best: {best} day{'s' if best != 1 else ''}.", bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI", 10), wraplength=self.px(220), justify="left").pack(anchor="w", pady=(self.px(8), 0))

        tk.Label(goal_panel, text="Daily goal", bg=COLORS["surface"], fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 13), anchor="w").pack(fill="x")
        ring = tk.Frame(goal_panel, bg=COLORS["surface"])
        ring.pack(anchor="w", pady=(self.px(6), 0))
        self.render_goal_ring(ring, today, goal, size=96, color=COLORS["green"] if today >= goal else COLORS["primary"]).pack()
        left = max(0, goal - today)
        tk.Label(goal_panel, text="Goal reached" if not left else f"{left} more to go", bg=COLORS["surface"], fg=COLORS["green"] if not left else COLORS["muted"], font=self.font("Segoe UI Semibold", 10), anchor="w").pack(fill="x", pady=(self.px(6), 0))

        tk.Label(level_panel, text=f"Level {level['level']}", bg=COLORS["surface"], fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 26), anchor="w").pack(fill="x")
        tk.Label(level_panel, text=f"{level['xp']} / {level['need']} XP", bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI Semibold", 10), anchor="w").pack(fill="x", pady=(self.px(2), self.px(8)))
        self.meter(level_panel, level["pct"], COLORS["primary"], 10).pack(fill="x")
        tk.Label(level_panel, text=f"+{progress.XP_PER_REVIEW} XP for every review.", bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI", 10), wraplength=self.px(220), justify="left").pack(anchor="w", pady=(self.px(8), 0))

        total = sum(count for _day, count in week)
        tk.Label(week_panel, text="This week", bg=COLORS["surface"], fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 13), anchor="w").pack(fill="x")
        tk.Label(week_panel, text=f"{total} review{'s' if total != 1 else ''} in 7 days", bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI", 10), anchor="w").pack(fill="x")
        chart = self.bar_chart(
            week_panel,
            [count for _day, count in week],
            [day.strftime("%a")[:2] for day, _count in week],
            COLORS["primary"],
            height=108,
            highlight=len(week) - 1,
            tips=[f"{day.strftime('%a %d %b')}: {count}" for day, count in week],
            on_click=lambda _index: self.show_view("stats"),
        )
        chart.pack(fill="x", pady=(self.px(6), 0))

    def study_modes(self):
        persona_key = self.store.onboarding.get("persona") or "general"
        quick = ("focus", "Quick 10", "Ten focused minutes on whatever matters most right now.", self.quick_session, COLORS["primary"])
        modes = {
            "student": ("Picked for studying", [
                quick,
                ("study", "Deep study", "A full hour: review, new cards, drills, and a self-test.", lambda: self.open_plan_preset(60, "Long-term retention"), COLORS["violet"]),
                ("testing", "Exam cram", "45 minutes aimed at the test: weak cards first.", lambda: self.open_plan_preset(45, "Cram"), COLORS["pink"]),
                ("capture", "Add notes", "Turn today's notes into cards.", lambda: self.show_view("capture"), COLORS["orange"]),
            ]),
            "everyday": ("Picked for everyday memory", [
                ("elder", "Gentle review", "People, routines, and places at a calm pace.", lambda: self.show_view("elder"), COLORS["cyan"]),
                ("games", "Daily puzzles", "Short, friendly memory games.", lambda: self.show_view("games"), COLORS["pink"]),
                quick,
                ("talkback", "Talk-back study", "Hear each question, answer out loud, and move on.", lambda: self.show_view("talkback"), COLORS["green"]),
            ]),
            "caregiver": ("Picked for caregivers", [
                ("decks", "Add a memory card", "A person, routine, place, or reminder in plain words.", lambda: self.show_view("elder"), COLORS["cyan"]),
                ("review", "Practise together", "Sit together for a short review.", lambda: self.show_view("review"), COLORS["primary"]),
                ("cuelab", "Photos and voices", "Attach familiar photos or recordings as cues.", lambda: self.show_view("capture"), COLORS["orange"]),
                ("stats", "Check progress", "See how practice is going this week.", lambda: self.show_view("stats"), COLORS["green"]),
            ]),
            "general": ("Pick a way to practise", [
                quick,
                ("training", "Try a technique", "Memory palaces, stories, peg lists and more.", lambda: self.show_view("training"), COLORS["violet"]),
                ("games", "Play a puzzle", "A quick recall game for a warm-up or break.", lambda: self.show_view("games"), COLORS["pink"]),
                ("dashboard", "Build a plan", "Tell MemoryPal your time and goal; get a path.", lambda: self.show_view("plan"), COLORS["green"]),
            ]),
        }
        return modes.get(persona_key, modes["general"])

    def render_study_modes(self, parent):
        subtitle, modes = self.study_modes()
        head = tk.Frame(parent, bg=COLORS["bg"])
        head.pack(fill="x", padx=(0, 8), pady=(self.px(4), self.px(10)))
        tk.Label(head, text="Study modes", bg=COLORS["bg"], fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 16)).pack(side="left")
        tk.Label(head, text=f"{subtitle}  \u2022  {shortcut('K')} jumps to any page", bg=COLORS["bg"], fg=COLORS["muted"], font=self.font("Segoe UI", 10)).pack(side="left", padx=(self.px(12), 0), pady=(self.px(4), 0))
        panels = self.panel_row(parent, len(modes))
        for panel, (icon, title, body, action, color) in zip(panels, modes):
            card = self.hover_card(panel, command=action)
            card.configure(highlightthickness=max(1, self.px(2)))
            # Line icons in a tinted badge, matching the hub tiles.
            self.icon_badge(card, icon).pack(anchor="w")
            tk.Label(card, text=title, bg=COLORS["surface"], fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 14), anchor="w").pack(fill="x", pady=(self.px(6), 0))
            tk.Label(card, text=body, bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI", 10), wraplength=self.px(220), justify="left").pack(anchor="w", pady=(self.px(4), 0))

    def render_next_badge(self, parent):
        badges = progress.achievements(self.store)
        earned = [badge for badge in badges if badge["done"]]
        upcoming = next((badge for badge in badges if not badge["done"]), None)
        (panel,) = self.panel_row(parent, 1)
        card = self.hover_card(panel, normal=COLORS["surface"], hover=COLORS["orange"], command=lambda: self.show_view("stats"))
        card.configure(highlightthickness=max(1, self.px(2)), highlightbackground=COLORS["surface"])
        card.columnconfigure(1, weight=1)
        if upcoming:
            tk.Label(card, text=upcoming["icon"], bg=COLORS["surface"], font=self.font("Segoe UI Emoji", 26)).grid(row=0, column=0, rowspan=3, sticky="nw", padx=(0, self.px(16)))
            tk.Label(card, text=f"Next badge: {upcoming['title']}", bg=COLORS["surface"], fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 14), anchor="w").grid(row=0, column=1, sticky="ew")
            tk.Label(card, text=f"{upcoming['body']}  {upcoming['current']} / {upcoming['target']}", bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI", 10), anchor="w").grid(row=1, column=1, sticky="ew", pady=(self.px(2), self.px(8)))
            self.meter(card, upcoming["current"] / upcoming["target"], COLORS["orange"], 10).grid(row=2, column=1, sticky="ew")
        else:
            tk.Label(card, text="\U0001F3C6  Every badge earned. Legendary!", bg=COLORS["surface"], fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 14)).grid(row=0, column=0, columnspan=2, sticky="w")
        shelf = tk.Frame(card, bg=COLORS["surface"])
        shelf.grid(row=0, column=2, rowspan=3, sticky="e", padx=(self.px(20), 0))
        icons = "".join(badge["icon"] for badge in earned[:6]) or "\u2014"
        tk.Label(shelf, text=icons, bg=COLORS["surface"], font=self.font("Segoe UI Emoji", 16)).pack(anchor="e")
        tk.Label(shelf, text=f"{len(earned)} of {len(badges)} badges  \u2022  see all", bg=COLORS["surface"], fg=COLORS["primary"], font=self.font("Segoe UI Semibold", 10)).pack(anchor="e")

    def quick_session(self):
        if self.store.due_cards():
            self.toast_message("Quick 10: clear the due cards first.")
            self.show_view("review")
        elif self.store.weak_cards():
            self.toast_message("Quick 10: firm up a few shaky cards.")
            self.show_view("focus")
        else:
            self.quiz_mode = "choices"
            self.view_drafts["quiz"] = {}
            self.toast_message("Quick 10: nothing due, so here's a fast quiz.")
            self.show_view("quiz")

    def read_aloud_review(self):
        if not self.accessibility.get("read_aloud"):
            self.update_accessibility_preference("read_aloud", True, rebuild=False)
            self.toast_message("Read aloud is on. Turn it off any time in Settings.")
        self.show_view("review")

    def open_plan_preset(self, minutes, goal_label):
        draft = dict(self.view_drafts.get("plan") or {})
        draft.update({"unit": "minutes", "amount": str(minutes), "goal_label": goal_label})
        draft.setdefault("deck", "All decks")
        draft.setdefault("habits", [])
        self.view_drafts["plan"] = draft
        self.show_view("plan")

    def render_goal_ring(self, parent, done, goal, size=132, color=None):
        color = color or COLORS["primary"]
        pixel_size = self.px(size)
        canvas = tk.Canvas(parent, width=pixel_size, height=pixel_size, bg=COLORS["surface"], highlightthickness=0)
        pct = 0 if goal <= 0 else clamp(done / goal, 0, 1)
        pad = self.px(10)
        stroke = self.px(10)
        if not self.draw_antialiased_ring(canvas, pixel_size, COLORS["line"], color, pct, stroke):
            box = pixel_size - pad
            canvas.create_oval(pad, pad, box, box, outline=COLORS["line"], width=stroke)
            if pct > 0:
                canvas.create_arc(pad, pad, box, box, start=90, extent=-360 * pct, style="arc", outline=color, width=stroke)
        self.create_centered_canvas_text(canvas, pixel_size / 2, pixel_size / 2 - self.px(6), text=str(done), fill=COLORS["ink"], font=self.font("Segoe UI Semibold", 22))
        # The small ring has room for "of 15" but not "of 15 goal".
        caption = f"of {goal}" if size < 120 else f"of {goal} goal"
        self.create_centered_canvas_text(canvas, pixel_size / 2, pixel_size / 2 + self.px(16), text=caption, fill=COLORS["muted"], font=self.font("Segoe UI", 10))
        return canvas

    def render_heatmap(self, parent, weeks=18):
        columns = self.store.heatmap_weeks(weeks)
        wrap = tk.Frame(parent, bg=COLORS["surface"])
        wrap.pack(anchor="w", pady=(4, 0))
        cell = self.px(14)
        gap = self.px(3)
        levels = {0: "heat_0", 1: "heat_1", 2: "heat_2", 3: "heat_3", 4: "heat_4"}

        def level_for(count):
            if count <= 0:
                return 0
            if count < 3:
                return 1
            if count < 6:
                return 2
            if count < 12:
                return 3
            return 4

        canvas = tk.Canvas(wrap, width=len(columns) * (cell + gap), height=7 * (cell + gap), bg=COLORS["surface"], highlightthickness=0)
        canvas.pack()
        for col_index, column in enumerate(columns):
            for row_index, (iso_day, count) in enumerate(column):
                x0 = col_index * (cell + gap)
                y0 = row_index * (cell + gap)
                color = COLORS["surface"] if count < 0 else COLORS[levels[level_for(count)]]
                rect = canvas.create_rectangle(x0, y0, x0 + cell, y0 + cell, fill=color, outline="")
                if count >= 0:
                    label = f"{iso_day}: {count} review{'s' if count != 1 else ''}"
                    canvas.tag_bind(rect, "<Enter>", lambda _event, text=label: self.toast_message(text))
        legend = tk.Frame(parent, bg=COLORS["surface"])
        legend.pack(anchor="w", pady=(self.px(8), 0))
        tk.Label(legend, text="Less", bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI", 9)).pack(side="left")
        for level in range(5):
            tk.Frame(legend, bg=COLORS[levels[level]], width=self.px(12), height=self.px(12)).pack(side="left", padx=self.px(3))
        tk.Label(legend, text="More", bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI", 9)).pack(side="left")

    # ------------------------------------------------------------------
    # Stats: every number with a picture
    # ------------------------------------------------------------------
    def view_stats(self):
        page = ScrollFrame(self.view_host)
        page.pack(fill="both", expand=True)
        store = self.store
        streak = store.current_streak()
        best = max(streak, progress.best_streak(store.activity))
        today = store.today_count()
        level = progress.level_info(store.practiced)
        mastery, mastered, learning = self.mastery_summary()

        streak_panel, level_panel, goal_panel, mastery_panel = self.panel_row(page.inner, 4)
        tk.Label(streak_panel, text=f" {streak}", image=self.line_icon("flame", self.px(34), COLORS["warm_text"]) or "", compound="left", bg=COLORS["surface"], fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 28), anchor="w").pack(fill="x")
        tk.Label(streak_panel, text=f"current streak  \u2022  best {best}", bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI Semibold", 11), anchor="w").pack(fill="x")
        tk.Label(level_panel, text=f"Level {level['level']}", bg=COLORS["surface"], fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 26), anchor="w").pack(fill="x")
        tk.Label(level_panel, text=f"{level['xp']} / {level['need']} XP  \u2022  {store.practiced} reviews", bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI", 10), anchor="w").pack(fill="x", pady=(self.px(2), self.px(8)))
        self.meter(level_panel, level["pct"], COLORS["primary"], 10).pack(fill="x")
        goal_head = tk.Frame(goal_panel, bg=COLORS["surface"])
        goal_head.pack(fill="x")
        tk.Label(goal_head, text="Today's goal", bg=COLORS["surface"], fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 13)).pack(side="left")
        change = tk.Label(goal_head, text="Change", bg=COLORS["surface"], fg=COLORS["primary"], font=self.font("Segoe UI Semibold", 10), cursor="hand2")
        change.pack(side="right")
        self.keyboard_link(change, lambda _event: self.edit_daily_goal())
        self.render_goal_ring(goal_panel, today, store.daily_goal, size=96, color=COLORS["green"] if today >= store.daily_goal else COLORS["primary"]).pack(anchor="w", pady=(self.px(6), 0))
        tk.Label(mastery_panel, text=f"{mastery}%", bg=COLORS["surface"], fg=COLORS["green"], font=self.font("Segoe UI Semibold", 30), anchor="w").pack(fill="x")
        tk.Label(mastery_panel, text=f"mastered  \u2022  {mastered} of {len(store.cards)} cards", bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI", 10), anchor="w").pack(fill="x", pady=(self.px(2), self.px(8)))
        self.meter(mastery_panel, mastery / 100, COLORS["green"], 10).pack(fill="x")

        (month_panel,) = self.panel_row(page.inner, 1)
        month = progress.daily_series(store.activity, 30)
        month_total = sum(count for _day, count in month)
        active = [count for _day, count in month if count > 0]
        self.panel_title(month_panel, "Last 30 days", f"{month_total} reviews on {len(active)} days" + (f"  \u2022  about {round(month_total / len(active))} on a day you practise" if active else "  \u2022  your practice will show up here"))
        self.bar_chart(
            month_panel, [count for _day, count in month], [day.strftime("%d %b").lstrip("0") for day, _count in month], COLORS["primary"],
            height=170, highlight=len(month) - 1, tips=[f"{day.strftime('%a %d %b')}: {count} review{'s' if count != 1 else ''}" for day, count in month],
        ).pack(fill="x")

        forecast_panel, maturity_panel = self.panel_row(page.inner, 2)
        forecast = progress.due_forecast(store.cards, 14)
        tomorrow = forecast[1][1] if len(forecast) > 1 else 0
        self.panel_title(forecast_panel, "Coming up", f"Cards due over the next two weeks  \u2022  {tomorrow} tomorrow")
        self.bar_chart(
            forecast_panel, [count for _day, count in forecast], ["Today" if index == 0 else day.strftime("%a")[:2] for index, (day, _count) in enumerate(forecast)], COLORS["primary"],
            height=150, highlight=0, tips=[f"{'Today (incl. overdue)' if index == 0 else day.strftime('%a %d %b')}: {count} due" for index, (day, count) in enumerate(forecast)],
        ).pack(fill="x")
        groups = progress.maturity_breakdown(store.cards)
        segments = [("New", groups["new"], COLORS["muted"]), ("Learning", groups["learning"], COLORS["orange"]), ("Young", groups["young"], COLORS["primary"]), ("Mature", groups["mature"], COLORS["green"])]
        self.panel_title(maturity_panel, "Card maturity", "How settled your cards are: mature cards come back 3+ weeks apart.")
        self.stacked_bar(maturity_panel, segments, height=30).pack(fill="x", pady=(self.px(8), self.px(12)))
        self.chart_legend(maturity_panel, [(f"{label} {value}", color) for label, value, color in segments]).pack(anchor="w")

        answers_panel, rhythm_panel = self.panel_row(page.inner, 2)
        mix = progress.rating_mix(store.cards)
        answered = sum(mix.values())
        self.panel_title(answers_panel, "How your answers went", "Each card's most recent result.")
        if answered:
            colors = {"Again": COLORS["pink"], "Hard": COLORS["orange"], "Good": COLORS["primary"], "Easy": COLORS["green"]}
            rows = [(self.rating_label(name), value, answered, colors[name], f"{round(value / answered * 100)}%") for name, value in mix.items()]
            self.meter_rows(answers_panel, rows).pack(fill="x")
        else:
            tk.Label(answers_panel, text="Review a few cards to see this.", bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI", 11)).pack(anchor="w")
        rhythm = progress.weekday_rhythm(store.activity)
        busiest = max(rhythm, key=lambda item: item[1])
        self.panel_title(rhythm_panel, "Your weekly rhythm", f"Average reviews by weekday (last 12 weeks)" + (f"  \u2022  busiest: {busiest[0]}" if busiest[1] > 0 else ""))
        self.bar_chart(
            rhythm_panel, [round(value, 1) for _day, value in rhythm], [name for name, _value in rhythm], COLORS["cyan"],
            height=150, highlight=date.today().weekday(), tips=[f"{name}: {value:.1f} a day" for name, value in rhythm],
        ).pack(fill="x")

        (heat_panel,) = self.panel_row(page.inner, 1)
        self.panel_title(heat_panel, "Activity calendar", "Each square is one day. Darker squares mean more reviews.")
        self.render_heatmap(heat_panel)

        (deck_panel,) = self.panel_row(page.inner, 1)
        summary = store.deck_summary()
        self.panel_title(deck_panel, "Deck mastery", "How much of each deck you've mastered.")
        if summary:
            palette = [COLORS["primary"], COLORS["green"], COLORS["orange"], COLORS["violet"], COLORS["pink"], COLORS["cyan"]]
            rows = [(deck, info["mastery"], 100, palette[index % len(palette)], f"{info['mastery']}%  \u2022  {info['due']} due  \u2022  {info['total']} cards") for index, (deck, info) in enumerate(summary.items())]
            self.meter_rows(deck_panel, rows).pack(fill="x")
        else:
            tk.Label(deck_panel, text="Add cards to see per-deck stats.", bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI", 11)).pack(anchor="w")

        badges = progress.achievements(store)
        earned = sum(1 for badge in badges if badge["done"])
        head = tk.Frame(page.inner, bg=COLORS["bg"])
        head.pack(fill="x", padx=(0, 8), pady=(self.px(4), self.px(10)))
        tk.Label(head, text="Achievements", bg=COLORS["bg"], fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 16)).pack(side="left")
        tk.Label(head, text=f"{earned} of {len(badges)} earned", bg=COLORS["bg"], fg=COLORS["muted"], font=self.font("Segoe UI", 10)).pack(side="left", padx=(self.px(12), 0), pady=(self.px(4), 0))
        per_row = 4
        for start in range(0, len(badges), per_row):
            chunk = badges[start:start + per_row]
            panels = self.panel_row(page.inner, per_row)
            for panel, badge in zip(panels, chunk):
                done = badge["done"]
                panel.configure(bg=COLORS["surface"] if done else COLORS["alt"])
                bg = panel.cget("bg")
                top = tk.Frame(panel, bg=bg)
                top.pack(fill="x")
                tk.Label(top, text=badge["icon"], bg=bg, font=self.font("Segoe UI Emoji", 20)).pack(side="left")
                if done:
                    tk.Label(top, text="Earned", bg=COLORS["good_bg"], fg=COLORS["good_fg"], font=self.font("Segoe UI Semibold", 9), padx=self.px(8), pady=self.px(2)).pack(side="right")
                tk.Label(panel, text=badge["title"], bg=bg, fg=COLORS["ink"] if done else COLORS["muted"], font=self.font("Segoe UI Semibold", 12), anchor="w").pack(fill="x", pady=(self.px(6), 0))
                tk.Label(panel, text=badge["body"], bg=bg, fg=COLORS["muted"], font=self.font("Segoe UI", 10), wraplength=self.px(220), justify="left").pack(anchor="w")
                if not done:
                    tk.Label(panel, text=f"{badge['current']} / {badge['target']}", bg=bg, fg=COLORS["muted"], font=self.font("Segoe UI Semibold", 9), anchor="w").pack(fill="x", pady=(self.px(6), self.px(4)))
                    self.meter(panel, badge["current"] / badge["target"], COLORS["orange"], 6, bg).pack(fill="x")
            for panel in panels[len(chunk):]:
                panel.configure(bg=COLORS["bg"])

    def new_set_dialog(self):
        name = self.dialog_text("New study set", "Name your set. Every card you add to it goes into this deck.")
        if name is None:
            return
        name = setbuilder.clean_set_name(name)
        if not name:
            return
        self.start_new_set(name)

    def rename_set_dialog(self, deck):
        new_name = self.dialog_text("Rename set", f"New name for \"{deck}\". Every card in it moves to the new name.", initial=deck)
        if new_name is None:
            return
        new_name = setbuilder.clean_set_name(new_name)
        if not new_name or new_name == deck:
            return
        if new_name in self.store.decks() and not self.dialog_confirm("Merge sets?", f"You already have a set called \"{new_name}\". Move the cards from \"{deck}\" into it?", "Merge sets"):
            return
        moved = self.store.rename_deck(deck, new_name)
        if self.deck_filter == deck:
            self.deck_filter = new_name
        self.toast_message(f"Renamed to {new_name} ({moved} card{'s' if moved != 1 else ''}).")
        self.show_view("decks")

    def view_decks(self):
        page = ScrollFrame(self.view_host)
        page.pack(fill="both", expand=True)
        summary = self.store.deck_summary()
        toolbar = ttk.Frame(page.inner, style="Page.TFrame")
        toolbar.pack(fill="x", padx=(0, self.px(8)), pady=(0, self.px(12)))
        ttk.Button(toolbar, text="New set", style="Primary.TButton", cursor="hand2", command=self.new_set_dialog).pack(side="left")
        if self.deck_filter:
            banner = self.card(page.inner, "AltCard.TFrame", 16)
            banner.pack(fill="x", padx=(0, 8), pady=(0, 12))
            ttk.Label(banner, text=f"Deck filter active: {self.deck_filter}", style="AltH2.TLabel").pack(side="left")
            ttk.Button(banner, text="Clear filter", command=self.clear_deck_filter).pack(side="right")
        if not summary:
            empty = self.card(page.inner)
            empty.pack(fill="x", padx=(0, 8))
            ttk.Label(empty, text="No decks yet", style="H2.TLabel").pack(anchor="w")
            ttk.Label(empty, text="Make a study set to start your first deck.", style="CardMuted.TLabel").pack(anchor="w", pady=(6, 12))
            ttk.Button(empty, text="Make a study set", style="Primary.TButton", command=lambda: self.start_new_set()).pack(fill="x")
            return
        grid = ttk.Frame(page.inner, style="Page.TFrame")
        grid.pack(fill="x", padx=(0, 8))
        palette = [COLORS["primary"], COLORS["green"], COLORS["orange"], COLORS["violet"], COLORS["pink"], COLORS["cyan"]]
        for index, (deck, info) in enumerate(summary.items()):
            color = palette[index % len(palette)]
            tile = self.hover_card(tk.Frame(grid, bg=COLORS["surface"], padx=self.px(22), pady=self.px(20), highlightthickness=1, highlightbackground=COLORS["line"]))
            tile.grid(row=index // 2, column=index % 2, sticky="nsew", padx=(0 if index % 2 == 0 else 12, 0), pady=(0, 12))
            grid.columnconfigure(index % 2, weight=1)
            tk.Frame(tile, bg=color, width=36, height=4).pack(anchor="w", pady=(0, 12))
            tk.Label(tile, text=deck, bg=COLORS["surface"], fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 16)).pack(anchor="w")
            tk.Label(tile, text=f"{info['total']} cards  \u2022  {info['due']} due  \u2022  {info['weak']} need focus", bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI", 11)).pack(anchor="w", pady=(4, 10))
            bar = ttk.Progressbar(tile, style="Horizontal.TProgressbar", maximum=100, value=info["mastery"])
            bar.pack(fill="x", pady=(0, 6))
            tk.Label(tile, text=f"{info['mastery']}% mastered", bg=COLORS["surface"], fg=color, font=self.font("Segoe UI Semibold", 11)).pack(anchor="w", pady=(0, 12))
            actions = tk.Frame(tile, bg=COLORS["surface"])
            actions.pack(fill="x")
            self.solid_button(actions, "Study this deck", lambda name=deck: self.study_deck(name), color).pack(side="left", fill="x", expand=True, padx=(0, 8))
            ttk.Button(actions, text="Add cards", command=lambda name=deck: self.start_new_set(name)).pack(side="left", padx=(0, 8))
            ttk.Button(actions, text="Rename", command=lambda name=deck: self.rename_set_dialog(name)).pack(side="left", padx=(0, 8))
            ttk.Button(actions, text="Library", command=lambda name=deck: self.open_deck_library(name)).pack(side="left")

    def study_deck(self, deck):
        self.deck_filter = deck
        due = self.store.due_cards(deck)
        if not due:
            self.toast_message(f"No cards due in {deck} today.")
            self.show_view("decks")
            return
        self.current_review = due[0]
        self.open_testing(due[0], "decks", "review")

    def open_deck_library(self, deck):
        self.deck_filter = deck
        self.show_view("library")

    def clear_deck_filter(self):
        self.deck_filter = None
        self.show_view(self.current_view)

    def view_plan(self):
        # This page stays stacked instead of column-heavy so it survives larger
        # Windows scaling, laptop screens, and fullscreen/non-fullscreen changes.
        draft = self.view_drafts.get("plan", {})
        page = ScrollFrame(self.view_host)
        page.pack(fill="both", expand=True)
        intro = self.card(page.inner, "WarmCard.TFrame", 18)
        intro.pack(fill="x", padx=(0, 8), pady=(0, 14))
        ttk.Label(intro, text="Tell me what you're working with", style="WarmH2.TLabel").pack(anchor="w")
        ttk.Label(intro, text="This builds a rule-based plan from your due cards, deck size, and habits below \u2014 no internet required.", style="WarmCard.TLabel", wraplength=1040).pack(anchor="w", pady=(4, 0))
        self.render_resource_strip(page.inner, "Available notes and cues")

        form = self.card(page.inner)
        form.pack(fill="x", padx=(0, 8), pady=(0, 14))
        grid = ttk.Frame(form, style="Card.TFrame")
        grid.pack(fill="x")

        time_section = self.card(grid, "AltCard.TFrame", 14)
        time_section.pack(fill="x", pady=(0, 10))
        ttk.Label(time_section, text="How much time do you have?", style="AltMuted.TLabel").pack(anchor="w", pady=(0, 4))
        unit_var = tk.StringVar(value=draft.get("unit", "minutes") if draft.get("unit", "minutes") in TIME_UNIT_ORDER else "minutes")
        amount_var = tk.StringVar(value=draft.get("amount", "30"))
        if amount_var.get() not in TIME_UNIT_OPTIONS[unit_var.get()]:
            amount_var.set(TIME_UNIT_OPTIONS[unit_var.get()][0])
        amount_host = tk.Frame(time_section, bg=COLORS["alt"])
        amount_host.pack(fill="x", pady=(0, 4))

        def render_amount_pills():
            for child in amount_host.winfo_children():
                child.destroy()
            self.pill_group(amount_host, amount_var, TIME_UNIT_OPTIONS[unit_var.get()], max_columns=5, bg=COLORS["alt"]).pack(fill="x")

        @self.smooth
        def cycle_unit(_event=None):
            current_index = TIME_UNIT_ORDER.index(unit_var.get())
            new_unit = TIME_UNIT_ORDER[(current_index + 1) % len(TIME_UNIT_ORDER)]
            unit_var.set(new_unit)
            amount_var.set(TIME_UNIT_OPTIONS[new_unit][0])
            render_amount_pills()
            unit_label.configure(text=unit_display())

        def unit_display():
            return f"{unit_var.get()}  \u2022  change unit"

        render_amount_pills()
        unit_label = tk.Label(time_section, text=unit_display(), bg=COLORS["alt"], fg=COLORS["primary"], font=self.font("Segoe UI Semibold", 10), cursor="hand2")
        unit_label.pack(anchor="w", pady=(2, 0))
        self.keyboard_link(unit_label, cycle_unit)
        self.add_tooltip(unit_label, "Switch between minutes, hours, days, and weeks.")

        deck_section = self.card(grid, "AltCard.TFrame", 14)
        deck_section.pack(fill="x", pady=(0, 10))
        ttk.Label(deck_section, text="What material?", style="AltMuted.TLabel").pack(anchor="w", pady=(0, 4))
        deck_values = ["All decks"] + self.store.decks() + ["New material"]
        deck_var = tk.StringVar(value=draft.get("deck", "All decks") if draft.get("deck", "All decks") in deck_values else "All decks")
        self.select_button(deck_section, deck_var, deck_values).pack(fill="x")

        goal_section = self.card(grid, "AltCard.TFrame", 14)
        goal_section.pack(fill="x", pady=(0, 10))
        ttk.Label(goal_section, text="What's the goal?", style="AltMuted.TLabel").pack(anchor="w", pady=(0, 4))
        goal_labels = {"cram": "Cram", "exam_prep": "Exam prep", "long_term": "Long-term retention"}
        goal_var = tk.StringVar(value=draft.get("goal_label", goal_labels["long_term"]))
        old_goal_labels = {
            "Cram before a test soon": "Cram",
            "Steady prep for an exam": "Exam prep",
            "Build long-term retention": "Long-term retention",
        }
        if goal_var.get() in old_goal_labels:
            goal_var.set(old_goal_labels[goal_var.get()])
        if goal_var.get() not in goal_labels.values():
            goal_var.set(goal_labels["long_term"])
        self.pill_group(goal_section, goal_var, list(goal_labels.values()), max_columns=3, bg=COLORS["alt"]).pack(fill="x")

        ttk.Label(form, text="How do you study best? (pick any)", style="CardMuted.TLabel").pack(anchor="w", pady=(4, 6))
        habit_vars = {}
        habit_row = ttk.Frame(form, style="Card.TFrame")
        habit_row.pack(fill="x", pady=(0, 14))
        saved_habits = set(draft.get("habits", []))
        for index, (key, label) in enumerate(STUDY_HABIT_OPTIONS):
            var = tk.BooleanVar(value=key in saved_habits)
            habit_vars[key] = var
            toggle = self.check_toggle(habit_row, var, label, wraplength=900)
            toggle.pack(fill="x", pady=(0, 6))

        result_holder = ttk.Frame(page.inner, style="Page.TFrame")
        result_holder.pack(fill="both", expand=True, padx=(0, 8))

        def goal_key_for(label):
            for key, value in goal_labels.items():
                if value == label:
                    return key
            return "long_term"

        def render_steps_list(container, steps):
            for index, step in enumerate(steps, 1):
                row = self.card(container, "Card.TFrame", 18)
                row.pack(fill="x", pady=(0, 10))
                head = tk.Frame(row, bg=COLORS["surface"])
                head.pack(fill="x")
                tk.Label(head, text=f"{index}", bg=COLORS["primary"], fg=self.on_color(COLORS["primary"]), font=self.font("Segoe UI Semibold", 12), width=3).pack(side="left", padx=(0, 12))
                title_box = tk.Frame(head, bg=COLORS["surface"])
                title_box.pack(side="left", fill="x", expand=True)
                tk.Label(title_box, text=step["title"], bg=COLORS["surface"], fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 14)).pack(anchor="w")
                tk.Label(title_box, text=f"~{step['minutes']} min", bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI", 10)).pack(anchor="w")
                ttk.Label(row, text=step["blurb"], style="Card.TLabel", wraplength=900).pack(anchor="w", pady=(8, 10))
                is_break = step.get("view") == "break"
                start_button = ttk.Button(row, text=f"Start {step['minutes']}-min break" if is_break else "Start this step", style="TButton" if is_break else "Primary.TButton", command=lambda s=step: self.start_plan_step(s))
                start_button.pack(fill="x")
                self.add_tooltip(start_button, "Start a rest timer." if is_break else "Open the app section for this plan step.")

        def render_follow_row(container):
            settings = self.view_drafts.get("plan", {})
            saved = self.store.study_plan.get("settings") if self.store.study_plan else None
            row = tk.Frame(container, bg=COLORS["alt"])
            row.pack(fill="x", pady=(self.px(10), 0))
            if saved == settings:
                tk.Label(row, text="\u2713 This is your plan. The Dashboard shows today's steps.", bg=COLORS["alt"], fg=COLORS["green"], font=self.font("Segoe UI Semibold", 11)).pack(side="left")
                ttk.Button(row, text="Stop following", command=lambda: (self.store.set_study_plan(None), self.toast_message("Plan cleared."), render_plan())).pack(side="right")
            else:
                def follow():
                    self.store.set_study_plan(settings)
                    self.toast_message("Saved. Your Dashboard now follows this plan.")
                    render_plan()
                self.solid_button(row, "Make this my plan", follow, COLORS["primary"]).pack(side="left")
                tk.Label(row, text="Your Dashboard will show these steps each day, ready to tick off.", bg=COLORS["alt"], fg=COLORS["muted"], font=self.font("Segoe UI", 10)).pack(side="left", padx=(self.px(12), 0))

        @self.smooth
        def render_plan():
            for child in result_holder.winfo_children():
                child.destroy()
            unit = unit_var.get()
            amount = int(amount_var.get())
            deck_choice = deck_var.get()
            goal_key = goal_key_for(goal_var.get())
            habits = {key for key, var in habit_vars.items() if var.get()}
            self.view_drafts["plan"] = {
                "unit": unit,
                "amount": amount_var.get(),
                "deck": deck_choice,
                "goal_label": goal_var.get(),
                "habits": list(habits),
            }

            if unit in ("minutes", "hours"):
                minutes = amount * (60 if unit == "hours" else 1)
                steps = build_study_plan(self.store, minutes, deck_choice, habits, goal_key)
                summary = self.card(result_holder, "AltCard.TFrame", 16)
                summary.pack(fill="x", pady=(0, 12))
                ttk.Label(summary, text=f"Your {amount} {unit} plan", style="AltH2.TLabel").pack(anchor="w")
                study_steps = [step for step in steps if step.get("view") != "break"]
                rests = len(steps) - len(study_steps)
                parts = [f"{len(study_steps)} step{'s' if len(study_steps) != 1 else ''}", deck_choice, goal_var.get()]
                if rests:
                    parts.append(f"{rests} rest break{'s' if rests != 1 else ''}")
                ttk.Label(summary, text=" \u2022 ".join(parts), style="AltMuted.TLabel").pack(anchor="w", pady=(2, 0))
                render_follow_row(summary)
                render_steps_list(result_holder, steps)
                self.fit_wrap_tree(result_holder)
            else:
                total_days = amount * (7 if unit == "weeks" else 1)
                days = build_multi_day_plan(self.store, total_days, deck_choice, habits, goal_key)
                summary = self.card(result_holder, "AltCard.TFrame", 16)
                summary.pack(fill="x", pady=(0, 12))
                ttk.Label(summary, text=f"Your {total_days}-day plan", style="AltH2.TLabel").pack(anchor="w")
                total_minutes = sum(day["minutes"] for day in days)
                ttk.Label(summary, text=f"Learn early, reinforce in the middle, sharpen near the end \u2022 {deck_choice} \u2022 {goal_var.get()} \u2022 about {round(total_minutes / 60, 1):g} hours in total", style="AltMuted.TLabel", wraplength=1000).pack(anchor="w", pady=(2, 0))
                render_follow_row(summary)
                chart_host = tk.Frame(result_holder, bg=COLORS["surface"], padx=self.px(20), pady=self.px(16))
                chart_host.pack(fill="x", pady=(0, 12))
                tab_host = tk.Frame(result_holder, bg=COLORS["bg"])
                tab_host.pack(fill="x", pady=(0, 12))
                tk.Label(tab_host, text="Jump to day:", bg=COLORS["bg"], fg=COLORS["muted"], font=self.font("Segoe UI", 10)).pack(anchor="w", pady=(0, 6))
                day_steps_host = ttk.Frame(result_holder, style="Page.TFrame")
                day_steps_host.pack(fill="both", expand=True)
                day_var = tk.StringVar(value="1")

                def render_day_chart(selected):
                    for child in chart_host.winfo_children():
                        child.destroy()
                    tk.Label(chart_host, text="Minutes each day  \u2022  click a bar to open that day", bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI Semibold", 10)).pack(anchor="w")
                    self.bar_chart(
                        chart_host, [d["minutes"] for d in days], [str(d["day"]) for d in days], COLORS["primary"], height=120,
                        highlight=selected, tips=[f"Day {d['day']}: {d['minutes']} min, {d.get('due', 0)} due" for d in days],
                        on_click=lambda index: (day_var.set(str(days[index]["day"])), show_day(str(days[index]["day"]))),
                    ).pack(fill="x", pady=(self.px(6), 0))

                @self.smooth
                def show_day(value):
                    for child in day_steps_host.winfo_children():
                        child.destroy()
                    day = next((d for d in days if str(d["day"]) == value), days[0])
                    render_day_chart(days.index(day))
                    kind_labels = {"learn": "Learn day", "review": "Spaced review day", "maintenance": "Short maintenance day", "light": "Light day before the test", "study": "Study day"}
                    try:
                        when = datetime.strptime(day["date"], "%Y-%m-%d").strftime("%a %d %b")
                    except (KeyError, ValueError):
                        when = ""
                    parts = [f"Day {day['day']}", when, kind_labels.get(day.get("kind"), "Study day"), f"{day.get('due', 0)} due", f"{day['minutes']} min"]
                    tk.Label(day_steps_host, text="  \u2022  ".join(part for part in parts if part), bg=COLORS["bg"], fg=COLORS["muted"], font=self.font("Segoe UI Semibold", 11)).pack(anchor="w", pady=(0, 8))
                    render_steps_list(day_steps_host, day["steps"])
                    self.fit_wrap_tree(day_steps_host)

                self.pill_group(tab_host, day_var, [str(d["day"]) for d in days], on_change=show_day, max_columns=14).pack(anchor="w")
                show_day("1")

        self.button_row(form, [("Build my plan", render_plan, "Primary.TButton")])
        if draft.get("habits") is not None or self.view_drafts.get("plan"):
            render_plan()
        self.register_draft_saver("plan", lambda: self.view_drafts.get("plan", {}))

    def start_plan_step(self, step):
        if step.get("view") == "break":
            self.start_break(step.get("minutes", 5))
            return
        self.deck_filter = step.get("deck")
        if "quiz_mode" in step:
            self.quiz_mode = step["quiz_mode"]
            self.view_drafts["quiz"] = {}
        self.show_view(step["view"])

    def start_break(self, minutes):
        pending = getattr(self, "_break_after", None)
        if pending is not None:
            try:
                self.after_cancel(pending)
            except tk.TclError:
                pass
        self.toast_message(f"Break started. I'll let you know in {minutes} minutes.")
        self._break_after = self.after(int(minutes * 60_000), lambda: (self.bell(), self.toast_message("Break's over. Ready for the next step?")))

    def view_focus(self):
        page = ScrollFrame(self.view_host)
        page.pack(fill="both", expand=True)
        due = self.store.due_cards()
        weak = [card for card in self.store.weak_cards() if card not in due]
        new_cards = [card for card in self.store.cards if card.repetitions == 0 and card not in due and card not in weak]
        hero = self.card(page.inner, "AltCard.TFrame")
        hero.pack(fill="x", padx=(0, 8), pady=(0, 12))
        ttk.Label(hero, text="Next best study queue", style="AltH2.TLabel").pack(anchor="w")
        ttk.Label(hero, text=f"Due: {len(due)} | Weak/new: {len(weak)} | Fresh: {len(new_cards)}", style="AltCard.TLabel").pack(anchor="w", pady=(6, 12))
        self.button_row(hero, [("Start Due Review", lambda: self.show_view("review"), "Primary.TButton"), ("Build Repetition Path", lambda: self.show_view("shuffle"), "TButton"), ("Add Material", lambda: self.show_view("capture"), "TButton")], "AltCard.TFrame")
        self.render_resource_strip(page.inner, "Recent study cues")

        def practice(card):
            card.next_review = today_iso()
            self.store.save()
            self.current_review = card
            self.open_testing(card, "focus", "review")

        # A preview of each queue, not the whole thing: listing every due card
        # built hundreds of rows and made the page slow to open and scroll.
        # Start Due Review still works through all of them.
        sections = [("Due now", due[:12]), ("Needs focus", weak[:8]), ("Fresh cards", new_cards[:8])]
        for title, cards in sections:
            section = self.card(page.inner)
            section.pack(fill="x", padx=(0, 8), pady=(0, 10))
            header = ttk.Frame(section, style="Card.TFrame")
            header.pack(fill="x")
            ttk.Label(header, text=title, style="H2.TLabel").pack(side="left", anchor="w", padx=(0, self.px(12)))
            self.render_status_chip(header, f"{len(cards)} item{'s' if len(cards) != 1 else ''}", COLORS["alt"], COLORS["primary"])
            if not cards:
                ttk.Label(section, text="Nothing in this queue.", style="CardMuted.TLabel").pack(anchor="w", pady=(6, 0))
                continue
            for card in cards:
                row = ttk.Frame(section, style="Card.TFrame")
                row.pack(fill="x", pady=(8, 0))
                ttk.Label(row, text=f"{card.front}  |  {card.last_result} {card.last_score}%", style="Card.TLabel", wraplength=830).grid(row=0, column=0, sticky="w")
                practice_button = ttk.Button(row, text="Practice", command=lambda value=card: practice(value))
                practice_button.grid(row=0, column=1, sticky="e", padx=(10, 0))
                self.add_tooltip(practice_button, self.action_hint("Practice"))
                row.columnconfigure(0, weight=1)
            if title == "Due now" and len(due) > len(cards):
                more = len(due) - len(cards)
                ttk.Label(section, text=f"And {more} more due. Start Due Review goes through all of them.", style="CardMuted.TLabel").pack(anchor="w", pady=(10, 0))

    MEDIA_NAMES = {"text_file": "note or document", "image": "image", "audio": "audio clip", "video": "video"}
    MEDIA_SUFFIXES = {"text_file": media.TEXT_TYPES, "image": media.IMAGE_TYPES, "audio": media.AUDIO_TYPES, "video": media.VIDEO_TYPES}

    def import_media_file(self, kind):
        """Ask for a file of this kind and copy it into the profile. Returns the new path or None."""
        import shutil
        from tkinter import filedialog

        name = self.MEDIA_NAMES.get(kind, kind)
        selected = filedialog.askopenfilename(parent=self, title=f"Choose a {name}", filetypes=media.FILETYPES.get(kind, []) + [("All files", "*.*")])
        if not selected:
            return None
        source = Path(selected)
        if media.is_program(source):
            self.dialog_alert("Programs can't be attached", f"\"{source.name}\" is a program or script. Attach notes, documents, pictures, audio or video instead.", "error")
            return None
        if source.suffix.lower() not in self.MEDIA_SUFFIXES.get(kind, ()):
            if not self.dialog_confirm(f"Attach this {name}?", f"\"{source.name}\" doesn't look like a {name} MemoryPal knows. Attach it anyway? It will open in whatever app your computer uses for it.", "Attach anyway"):
                return None
        self.store.attachment_dir.mkdir(parents=True, exist_ok=True)
        suffix = source.suffix.lower() if re.fullmatch(r"\.[a-z0-9]{1,10}", source.suffix.lower()) else ""
        target = self.store.attachment_dir / f"{uuid4().hex}{suffix}"
        try:
            shutil.copy2(source, target)
        except OSError as exc:
            self.dialog_alert("Couldn't copy the file", f"{source.name} could not be copied into MemoryPal: {exc}", "error")
            return None
        if kind == "image" and self.image_photo(target) is None:
            self.toast_message("Image attached. No preview could be made, but it will still open in your photo viewer.")
        return target

    def set_pending_media(self, kind, path, labels):
        self.pending_media[kind] = str(path) if path else ""
        if kind in labels and labels[kind].winfo_exists():
            labels[kind].configure(text=Path(path).name if path else f"No {self.MEDIA_NAMES.get(kind, kind)} selected")

    def attach_media(self, kind, labels, text_target=None):
        target = self.import_media_file(kind)
        if target is None:
            return
        self.set_pending_media(kind, target, labels)
        if kind != "text_file" or text_target is None:
            self.toast_message(f"{self.MEDIA_NAMES.get(kind, kind).capitalize()} attached. It is saved with this capture.")
            return
        try:
            text = extract_document_text(target)
        except Exception as exc:
            self.toast_message(f"Note attached, but its text couldn't be read: {exc}")
            return
        if not normalize_space(text):
            self.toast_message("Note attached, but no readable text was found in it.")
            return
        text_target.delete("1.0", "end")
        text_target.insert("1.0", text)
        self.toast_message("Note imported. Its text is in the study bit box, ready to split into cards.")

    def record_text_note(self, labels, text_target):
        text = normalize_space(text_target.get("1.0", "end"))
        if not text:
            self.toast_message("Type or dictate text first, then save it as a note.")
            return
        self.store.attachment_dir.mkdir(parents=True, exist_ok=True)
        target = self.store.attachment_dir / f"text-note-{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
        target.write_text(text + "\n", encoding="utf-8")
        self.pending_media["text_file"] = str(target)
        labels["text_file"].configure(text=target.name)
        self.toast_message("Text note saved as an attached file.")

    def record_audio(self, labels):
        self.record_audio_file(lambda path: (self.set_pending_media("audio", path, labels), self.toast_message(f"Voice recording attached ({media.wav_duration(path):.0f} s).")))

    def record_audio_file(self, on_saved, max_seconds=300):
        """A small recorder window: live timer and level, Stop to save, Cancel to discard."""
        recorder = media.AudioRecorder()
        top, content, actions = self.dialog_window("Record audio", "Press Start, speak clearly, then press Stop and save. Recordings can be up to 5 minutes.")
        status = tk.Label(content, text="Ready", bg=COLORS["surface"], fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 22), anchor="w")
        status.pack(fill="x")
        note = tk.Label(content, text="Your microphone is only used while recording.", bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI", 10), anchor="w")
        note.pack(fill="x", pady=(self.px(2), self.px(10)))
        level = tk.Canvas(content, height=self.px(10), bg=COLORS["surface"], highlightthickness=0)
        level.pack(fill="x")
        state = {"after": None, "saved": None}

        def draw_level(amount):
            level.delete("all")
            width = max(1, level.winfo_width())
            level.create_rectangle(0, 0, width, self.px(10), fill=COLORS["line"], outline="")
            if amount > 0:
                level.create_rectangle(0, 0, width * min(1.0, amount * 1.6), self.px(10), fill=COLORS["green"], outline="")

        def tick():
            if not top.winfo_exists():
                return
            seconds = recorder.elapsed()
            status.configure(text=f"\u25cf  Recording  {int(seconds // 60)}:{int(seconds % 60):02d}", fg=COLORS["again_fg"])
            draw_level(recorder.level())
            if seconds >= max_seconds:
                finish()
                return
            state["after"] = self.after(100, tick)

        def start():
            ok, message = recorder.start()
            if not ok:
                status.configure(text="Microphone unavailable", fg=COLORS["again_fg"])
                note.configure(text=f"{message} Check Settings > Privacy & security > Microphone, or import an audio file instead.")
                return
            start_button.configure(text="Stop and save", command=finish, style="Danger.TButton")
            note.configure(text="Speak now. Press Stop and save when you're done.")
            tick()

        def finish():
            if state["after"]:
                self.after_cancel(state["after"])
                state["after"] = None
            self.store.attachment_dir.mkdir(parents=True, exist_ok=True)
            target = self.store.attachment_dir / f"audio-recording-{datetime.now().strftime('%Y%m%d-%H%M%S')}.wav"
            ok, message = recorder.stop(target)
            if not ok:
                status.configure(text="Nothing was saved", fg=COLORS["again_fg"])
                note.configure(text=message)
                start_button.configure(text="Try again", command=start, style="Primary.TButton")
                return
            state["saved"] = target
            top.destroy()

        def cancel():
            if state["after"]:
                self.after_cancel(state["after"])
            recorder.cancel()
            top.destroy()

        cancel_button = ttk.Button(actions, text="Cancel", command=cancel)
        cancel_button.grid(row=0, column=0, sticky="ew", padx=(0, self.px(8)))
        start_button = self.solid_button(actions, "Start recording", start, COLORS["primary"])
        start_button.grid(row=0, column=1, sticky="ew")
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)
        self.present_dialog(top)
        top.protocol("WM_DELETE_WINDOW", cancel)
        top.bind("<Escape>", lambda _event: cancel())
        top.after(50, lambda: draw_level(0))
        top.wait_window()
        if state["saved"] is not None:
            on_saved(state["saved"])

    def record_video(self, labels):
        self.record_video_file(lambda path: (self.set_pending_media("video", path, labels), self.toast_message("Video attached.")))

    def record_video_file(self, on_saved):
        """Record with the Windows Camera app, then bring the new video into MemoryPal."""
        import shutil
        import time as time_module

        started = {"at": time_module.time()}
        top, content, actions = self.dialog_window(
            "Record a video",
            "1. Press Open Camera. In the Camera app, switch to Video and record.\n2. Stop recording, then come back here and press Use my recording.",
        )
        status = tk.Label(content, text="", bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI", 10), anchor="w", justify="left", wraplength=self.px(420))
        status.pack(fill="x")
        result = {"path": None}

        def open_camera():
            started["at"] = time_module.time()
            if media.open_camera_app():
                status.configure(text="Camera opened. Record your video, then press Use my recording.", fg=COLORS["muted"])
            else:
                status.configure(text="The Camera app couldn't be opened. Use Import video instead.", fg=COLORS["again_fg"])

        def use_recording():
            found = media.newest_video_since(started["at"])
            if found is None:
                folders = ", ".join(str(folder) for folder in media.camera_folders()) or "your Pictures\\Camera Roll folder"
                status.configure(text=f"No new video yet. Finish recording in the Camera app first. (Looked in {folders}.)", fg=COLORS["again_fg"])
                return
            self.store.attachment_dir.mkdir(parents=True, exist_ok=True)
            target = self.store.attachment_dir / f"video-recording-{datetime.now().strftime('%Y%m%d-%H%M%S')}{found.suffix.lower()}"
            try:
                shutil.copy2(found, target)
            except OSError as exc:
                status.configure(text=f"The video couldn't be copied: {exc}", fg=COLORS["again_fg"])
                return
            result["path"] = target
            top.destroy()

        ttk.Button(actions, text="Open Camera", command=open_camera).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, self.px(8)))
        ttk.Button(actions, text="Cancel", command=top.destroy).grid(row=1, column=0, sticky="ew", padx=(0, self.px(8)))
        self.solid_button(actions, "Use my recording", use_recording, COLORS["primary"]).grid(row=1, column=1, sticky="ew")
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)
        self.present_dialog(top)
        top.bind("<Escape>", lambda _event: top.destroy())
        top.wait_window()
        if result["path"] is not None:
            on_saved(result["path"])

    def attach_file_to_card(self, card, kind, refresh=None):
        target = self.import_media_file(kind)
        if target is None:
            return
        self.set_card_media(card, kind, target, refresh)

    def set_card_media(self, card, kind, path, refresh=None):
        setattr(card, kind, str(path))
        self.store.save()
        self.toast_message(f"{self.MEDIA_NAMES.get(kind, kind).capitalize()} cue attached to the card.")
        if refresh:
            refresh()

    def save_text_cue(self, card, text, refresh=None):
        text = normalize_space(text)
        if not text:
            self.toast_message("Generate a hint first.")
            return
        self.store.attachment_dir.mkdir(parents=True, exist_ok=True)
        target = self.store.attachment_dir / f"cue-{uuid4().hex}.txt"
        target.write_text(text + "\n", encoding="utf-8")
        card.text_file = str(target)
        self.store.save()
        self.toast_message("Hint saved as a text cue.")
        if refresh:
            refresh()

    def open_image_search(self, query):
        if not query:
            self.toast_message("Add a card first.")
            return
        try:
            import webbrowser
            from urllib.parse import quote_plus

            webbrowser.open(f"https://www.google.com/search?tbm=isch&q={quote_plus(query)}")
            self.toast_message("Opened an image search in your browser. Save an image, then use Attach Image below.")
        except Exception as exc:
            self.dialog_alert("Could not open browser", str(exc), "error")

    def generate_tts_cue(self, card, text, refresh=None):
        text = normalize_space(text)
        if not text:
            self.toast_message("Nothing to speak yet.")
            return
        self.store.attachment_dir.mkdir(parents=True, exist_ok=True)
        target = self.store.attachment_dir / f"voice-cue-{uuid4().hex}.wav"
        self.toast_message("Creating the spoken cue...")
        self.update_idletasks()
        ok, message = media.speech_to_wav(text, target)
        if not ok:
            self.dialog_alert("Voice generation failed", f"The computer's voice couldn't create the audio: {message}", "error")
            return
        card.audio = str(target)
        self.store.save()
        self.toast_message("Spoken cue created and attached. Press Play to hear it.")
        if refresh:
            refresh()

    def view_cuelab(self):
        draft = self.view_drafts.get("cuelab", {})
        page = ScrollFrame(self.view_host)
        page.pack(fill="both", expand=True)
        if not self.store.cards:
            empty = self.card(page.inner)
            empty.pack(fill="x", padx=(0, 8))
            ttk.Label(empty, text="No cards yet", style="H2.TLabel").pack(anchor="w")
            ttk.Label(empty, text="Add cards in Capture, then come back to generate cues for them.", style="CardMuted.TLabel").pack(anchor="w", pady=(6, 12))
            ttk.Button(empty, text="Make a study set", style="Primary.TButton", command=lambda: self.start_new_set()).pack(fill="x")
            return

        intro = self.card(page.inner, "WarmCard.TFrame", 16)
        intro.pack(fill="x", padx=(0, 8), pady=(0, 14))
        ttk.Label(intro, text="Pick a card, then generate a cue", style="WarmH2.TLabel").pack(anchor="w")
        ttk.Label(intro, text="Text hints are made on this computer. Image search opens your browser. Spoken cues use the computer's built-in voice, or record your own.", style="WarmCard.TLabel", wraplength=1040).pack(anchor="w", pady=(4, 0))

        picker = self.card(page.inner)
        picker.pack(fill="x", padx=(0, 8), pady=(0, 14))
        options = [f"{card.front[:70] or '(blank prompt)'}  \u2014  {card.deck}" for card in self.store.cards]
        pick_var = tk.StringVar(value=draft.get("pick", options[0]))
        if pick_var.get() not in options:
            pick_var.set(options[0])
        ttk.Label(picker, text="Card", style="CardMuted.TLabel").pack(anchor="w")
        self.select_button(picker, pick_var, options, on_change=lambda _value: render()).pack(fill="x", pady=(4, 0))

        body = ttk.Frame(page.inner, style="Page.TFrame")
        body.pack(fill="both", expand=True, padx=(0, 8))

        def current_card():
            index = options.index(pick_var.get()) if pick_var.get() in options else 0
            return self.store.cards[index]

        @self.smooth
        def render():
            for child in body.winfo_children():
                child.destroy()
            card = current_card()
            self.view_drafts["cuelab"] = {"pick": pick_var.get()}

            preview = self.card(body, "AltCard.TFrame", 16)
            preview.pack(fill="x", pady=(0, 12))
            ttk.Label(preview, text=card.front, style="AltH2.TLabel", wraplength=1040).pack(anchor="w")
            ttk.Label(preview, text=card.back, style="AltCard.TLabel", wraplength=1040).pack(anchor="w", pady=(6, 0))
            self.render_media_controls(preview, card)

            hint_holder = {"text": ""}
            text_card = self.card(body)
            text_card.pack(fill="x", pady=(0, 12))
            ttk.Label(text_card, text="Text hint", style="H2.TLabel").pack(anchor="w")
            ttk.Label(text_card, text="Generate a partial-answer hint or a memorable sentence, without giving the whole answer away.", style="CardMuted.TLabel", wraplength=1040).pack(anchor="w", pady=(4, 10))
            hint_label = ttk.Label(text_card, text="Choose a hint style below.", style="Card.TLabel", wraplength=1040)
            hint_label.pack(anchor="w", pady=(0, 10))

            def show_hint(text):
                hint_holder["text"] = text
                hint_label.configure(text=text)

            self.button_row(text_card, [
                ("Letter Hint", lambda: show_hint(hangman_hint(card.back)), "Primary.TButton"),
                ("Keyword Hint", lambda: show_hint("Key ideas: " + ", ".join(salient_keywords(card.back)) if salient_keywords(card.back) else "Not enough text to pull keywords from."), "TButton"),
                ("Mnemonic Sentence", lambda: show_hint(mnemonic_sentence(card.front, card.back)), "TButton"),
            ])
            ttk.Button(text_card, text="Save as text cue", command=lambda: self.save_text_cue(card, hint_holder["text"], render)).pack(fill="x", pady=(10, 0))

            image_card = self.card(body)
            image_card.pack(fill="x", pady=(0, 12))
            ttk.Label(image_card, text="Image cue", style="H2.TLabel").pack(anchor="w")
            ttk.Label(image_card, text="Current: " + (Path(card.image).name if card.image else "none"), style="CardMuted.TLabel").pack(anchor="w", pady=(4, 10))
            self.button_row(image_card, [
                ("Search the web", lambda: self.open_image_search(card.front), "Primary.TButton"),
                ("Attach Image File", lambda: self.attach_file_to_card(card, "image", render), "TButton"),
            ])

            audio_card = self.card(body)
            audio_card.pack(fill="x")
            ttk.Label(audio_card, text="Audio cue", style="H2.TLabel").pack(anchor="w")
            ttk.Label(audio_card, text="Current: " + (Path(card.audio).name if card.audio else "none"), style="CardMuted.TLabel").pack(anchor="w", pady=(4, 10))
            self.button_row(audio_card, [
                ("Generate Spoken Cue", lambda: self.generate_tts_cue(card, f"{card.front}. {card.back}", render), "Primary.TButton"),
                *([] if IS_MAC else [("Record a Voice", lambda: self.record_audio_file(lambda path: self.set_card_media(card, "audio", path, render)), "TButton")]),
                ("Attach Audio File", lambda: self.attach_file_to_card(card, "audio", render), "TButton"),
            ])
            if card.audio:
                self.audio_play_button(audio_card, card.audio).pack(fill="x", pady=(self.px(10), 0))

            video_card = self.card(body)
            video_card.pack(fill="x", pady=(12, 0))
            ttk.Label(video_card, text="Video cue", style="H2.TLabel").pack(anchor="w")
            ttk.Label(video_card, text="Current: " + (Path(card.video).name if card.video else "none"), style="CardMuted.TLabel").pack(anchor="w", pady=(4, 10))
            self.button_row(video_card, [
                *([] if IS_MAC else [("Record with Camera", lambda: self.record_video_file(lambda path: self.set_card_media(card, "video", path, render)), "Primary.TButton")]),
                ("Attach Video File", lambda: self.attach_file_to_card(card, "video", render), "Primary.TButton" if IS_MAC else "TButton"),
            ])

        render()
        self.register_draft_saver("cuelab", lambda: {"pick": pick_var.get()})

    def capture_draft(self):
        """The set builder's draft, reading the older capture draft keys too."""
        draft = dict(self.view_drafts.get("capture", {}))
        if "items" not in draft:
            items = [setbuilder.typed_item(item.get("prompt", ""), item.get("answer", "")) for item in draft.get("qa_items", [])]
            items = [item for item in items if item]
            if draft.get("chunks"):
                items += setbuilder.notes_to_items("\n".join(draft["chunks"]), draft.get("prompt") or setbuilder.DEFAULT_PROMPT)
            draft["items"] = items
        draft.setdefault("name", draft.get("title", ""))
        draft.setdefault("question", draft.get("qa_prompt", ""))
        draft.setdefault("answer", draft.get("qa_answer", ""))
        draft.setdefault("notes", draft.get("entry", ""))
        return draft

    def start_new_set(self, name=""):
        """Open the set builder for a new set, optionally already named."""
        if self.current_view == "capture":
            self.save_current_draft()
        pending = self.capture_draft().get("items", [])
        if pending:
            unsaved = setbuilder.clean_set_name(self.capture_draft().get("name")) or "an untitled set"
            if not self.dialog_confirm("Discard unsaved cards?", f"You have {len(pending)} unsaved card{'s' if len(pending) != 1 else ''} in {unsaved}. Start a new set without them?", "Discard and start"):
                self.show_view("capture")
                return
        self.view_drafts["capture"] = {"name": setbuilder.clean_set_name(name), "items": []}
        self.pending_media = {"text_file": "", "image": "", "audio": "", "video": ""}
        if self.current_view == "capture":
            self.draft_savers.pop("capture", None)
        self.show_view("capture")

    def view_capture(self):
        """Make a study set: name it, add cards, save. Everything else is under More options."""
        draft = self.capture_draft()
        page = ScrollFrame(self.view_host)
        page.pack(fill="both", expand=True)
        wrapper = ttk.Frame(page.inner, style="Page.TFrame")
        wrapper.pack(fill="both", expand=True, padx=(0, self.px(8)))
        wrapper.columnconfigure(0, weight=3, uniform="capture")
        wrapper.columnconfigure(1, weight=2, uniform="capture")
        wrapper.rowconfigure(0, weight=1)
        form = self.card(wrapper)
        form.grid(row=0, column=0, sticky="nsew", padx=(0, self.px(16)))
        side = self.card(wrapper)
        side.grid(row=0, column=1, sticky="nsew")
        surface = COLORS["surface"]
        items = [dict(item) for item in draft.get("items", []) if item]
        self.pending_media = dict(draft.get("pending_media", {"text_file": "", "image": "", "audio": "", "video": ""}))

        # 1. The set's name: it becomes the deck of every card made here.
        ttk.Label(form, text="Name your set", style="H2.TLabel").pack(anchor="w")
        self.fit_wrap(ttk.Label(form, text="Every card you add goes into this set. You can rename it later on the Decks page.", style="CardMuted.TLabel", wraplength=self.px(560)), pady=(self.px(4), self.px(10)))
        name_row = ttk.Frame(form, style="Card.TFrame")
        name_row.pack(fill="x")
        name_var = tk.StringVar(value=draft.get("name", ""))
        name_entry = ttk.Entry(name_row, textvariable=name_var, font=self.font("Segoe UI", 13))
        name_entry.pack(side="left", fill="x", expand=True)
        existing = self.store.decks()
        if existing:
            pick = tk.StringVar(value="Existing sets")
            chooser = self.select_button(name_row, pick, existing, on_change=lambda value: (name_var.set(value), pick.set("Existing sets")))
            chooser.configure(text="Existing sets")
            chooser.pack(side="left", padx=(self.px(10), 0))
            self.add_tooltip(chooser, "Add these cards to a set you already have.")

        # 2. Cards: typed one at a time, or pasted notes split into cards.
        ttk.Label(form, text="Add cards", style="H2.TLabel").pack(anchor="w", pady=(self.px(28), self.px(10)))
        mode = tk.StringVar(value=draft.get("mode", "Type questions"))
        tabs = self.pill_group(form, mode, ["Type questions", "Paste notes"], on_change=lambda _value: show_mode(), bg=surface)
        tabs.pack(fill="x", pady=(0, self.px(14)))
        typed_panel = ttk.Frame(form, style="Card.TFrame")
        paste_panel = ttk.Frame(form, style="Card.TFrame")
        modes_host_marker = ttk.Frame(form, style="Card.TFrame")
        modes_host_marker.pack(fill="x")

        ttk.Label(typed_panel, text="Question", style="CardMuted.TLabel").pack(anchor="w")
        question = ttk.Entry(typed_panel, font=self.font("Segoe UI", 12))
        question.insert(0, draft.get("question", ""))
        question.pack(fill="x", pady=(self.px(4), self.px(12)))
        ttk.Label(typed_panel, text="Answer", style="CardMuted.TLabel").pack(anchor="w")
        answer = self.text_box(typed_panel, 3, 12)
        answer.insert("1.0", draft.get("answer", ""))
        answer.pack(fill="x", pady=(self.px(4), self.px(6)))
        self.fit_wrap(ttk.Label(typed_panel, text="Enter adds the card (Shift+Enter for a new line). Leave the answer empty for a self-check card.", style="CardMuted.TLabel", wraplength=self.px(560)), pady=(0, self.px(12)))
        typed_actions = ttk.Frame(typed_panel, style="Card.TFrame")
        typed_actions.pack(fill="x")

        self.fit_wrap(ttk.Label(paste_panel, text="Paste or type notes. Lines like \"Question => Answer\" (or tab-separated, as spreadsheets and Quizlet export) become that card; every other line or sentence becomes a recall card.", style="CardMuted.TLabel", wraplength=self.px(560)), pady=(0, self.px(8)))
        notes = self.text_box(paste_panel, 8, 12)
        notes.insert("1.0", draft.get("notes", ""))
        notes.pack(fill="x", pady=(0, self.px(12)))
        paste_actions = ttk.Frame(paste_panel, style="Card.TFrame")
        paste_actions.pack(fill="x")

        def show_mode():
            typed_panel.pack_forget()
            paste_panel.pack_forget()
            panel = typed_panel if mode.get() == "Type questions" else paste_panel
            panel.pack(fill="x", before=modes_host_marker)
            (question if panel is typed_panel else notes).focus_set()

        # 3. More options, folded away: card prompt, question starters, cues.
        more_open = tk.BooleanVar(value=bool(draft.get("more_open")))
        more_toggle = ttk.Button(form, style="Link.TButton", cursor="hand2")
        more_toggle.pack(anchor="w", pady=(self.px(24), 0))
        more = ttk.Frame(form, style="Card.TFrame")
        ttk.Label(more, text="Prompt for recall cards", style="CardMuted.TLabel").pack(anchor="w", pady=(self.px(12), 0))
        prompt = ttk.Entry(more)
        prompt.insert(0, draft.get("prompt", setbuilder.DEFAULT_PROMPT))
        prompt.pack(fill="x", pady=(self.px(4), self.px(4)))
        self.fit_wrap(ttk.Label(more, text="Used on the front of cards made from notes without a question. {n} is the card's number.", style="CardMuted.TLabel", wraplength=self.px(560)), pady=(0, self.px(14)))
        ttk.Label(more, text="Question starters", style="CardMuted.TLabel").pack(anchor="w", pady=(0, self.px(6)))
        starters = ttk.Frame(more, style="Card.TFrame")
        starters.pack(fill="x", pady=(0, self.px(14)))

        def use_starter(text):
            mode.set("Type questions")
            show_mode()
            question.delete(0, "end")
            question.insert(0, text)
            question.focus_set()
            question.icursor("end")

        for index, starter in enumerate(["Who is this person?", "What is this appointment?", "Where is this item kept?", "What should happen next?"]):
            chip = ttk.Button(starters, text=starter, style="Pill.TButton", cursor="hand2", command=lambda t=starter: use_starter(t))
            row, column = divmod(index, 2)
            chip.grid(row=row, column=column, sticky="ew", padx=(0 if column == 0 else self.px(8), 0), pady=(0, self.px(8)))
            starters.columnconfigure(column, weight=1, uniform="starters")
        ttk.Label(more, text="Attach a cue to every card in this set", style="CardMuted.TLabel").pack(anchor="w", pady=(0, self.px(6)))
        cue_rows = ttk.Frame(more, style="Card.TFrame")
        cue_rows.pack(fill="x")
        labels = {}
        cue_actions = [
            ("text_file", "Note", [("Import note, PDF, Word or RTF", lambda: self.attach_media("text_file", labels, notes)), ("Save the pasted notes as a note", lambda: self.record_text_note(labels, notes)), ("Remove note", lambda: self.set_pending_media("text_file", "", labels))]),
            ("image", "Image", [("Import image", lambda: self.attach_media("image", labels)), ("Remove image", lambda: self.set_pending_media("image", "", labels))]),
            # Recording uses Windows' own recorder and Camera app, so the Mac
            # offers importing only.
            ("audio", "Audio", ([] if IS_MAC else [("Record audio", lambda: self.record_audio(labels))]) + [("Import audio", lambda: self.attach_media("audio", labels)), ("Remove audio", lambda: self.set_pending_media("audio", "", labels))]),
            ("video", "Video", ([] if IS_MAC else [("Record video (Camera app)", lambda: self.record_video(labels))]) + [("Import video", lambda: self.attach_media("video", labels)), ("Remove video", lambda: self.set_pending_media("video", "", labels))]),
        ]
        for row_index, (kind, cue_label, actions) in enumerate(cue_actions):
            button = self.cue_menu_button(cue_rows, cue_label, actions, hint=f"Attach or remove the {self.MEDIA_NAMES.get(kind, kind)} for this set.")
            button.grid(row=row_index, column=0, sticky="ew", pady=(0, self.px(8)))
            path = self.pending_media.get(kind)
            labels[kind] = ttk.Label(cue_rows, text=Path(path).name if path else f"No {self.MEDIA_NAMES.get(kind, kind)} selected", style="CardMuted.TLabel")
            labels[kind].grid(row=row_index, column=1, sticky="w", padx=(self.px(12), 0), pady=(0, self.px(8)))
        cue_rows.columnconfigure(0, minsize=self.px(130))
        cue_rows.columnconfigure(1, weight=1)

        def show_more():
            more_toggle.configure(text=("Hide options" if more_open.get() else "More options") + ("  ▴" if more_open.get() else "  ▾"))
            if more_open.get():
                more.pack(fill="x", after=more_toggle)
            else:
                more.pack_forget()

        more_toggle.configure(command=lambda: (more_open.set(not more_open.get()), self.smooth(show_more)()))

        # The set so far, on the right, with Save at the bottom.
        set_title = ttk.Label(side, text="", style="H2.TLabel")
        set_title.pack(anchor="w")
        set_count = ttk.Label(side, text="", style="CardMuted.TLabel")
        set_count.pack(anchor="w", pady=(self.px(4), self.px(14)))
        listing = tk.Frame(side, bg=surface)
        listing.pack(fill="x")
        save_button = ttk.Button(side, text="Save set", style="Primary.TButton", cursor="hand2")
        save_button.pack(fill="x", pady=(self.px(16), 0))
        clear_button = ttk.Button(side, text="Clear cards", cursor="hand2")
        clear_button.pack(fill="x", pady=(self.px(8), 0))
        after_save = tk.Frame(side, bg=surface)
        after_save.pack(fill="x", pady=(self.px(16), 0))

        def update_heading(*_args):
            name = setbuilder.clean_set_name(name_var.get())
            set_title.configure(text=name or "Untitled set")
            count = len(items)
            set_count.configure(text=f"{count} card{'s' if count != 1 else ''}" + ("" if name else ". Give the set a name to save it."))
            save_button.configure(text=f"Save {count} card{'s' if count != 1 else ''}" if count else "Save set")

        @self.smooth
        def refresh():
            for child in listing.winfo_children():
                child.destroy()
            if items:
                for child in after_save.winfo_children():
                    child.destroy()
            if not items:
                self.fit_wrap(tk.Label(listing, text="Cards you add appear here. Check them, remove any you don't want, then save.", bg=surface, fg=COLORS["muted"], font=self.font("Segoe UI", 11), wraplength=self.px(360), justify="left"))
            for index, item in enumerate(items):
                row = tk.Frame(listing, bg=surface)
                row.pack(fill="x", pady=(0 if index == 0 else self.px(10), 0))
                if index:
                    tk.Frame(row, bg=COLORS["line"], height=1).pack(fill="x", pady=(0, self.px(10)))
                body = tk.Frame(row, bg=surface)
                body.pack(fill="x")
                remove = ttk.Button(body, text="Remove", style="Link.TButton", cursor="hand2", command=lambda i=index: remove_item(i))
                remove.pack(side="right", anchor="n", padx=(self.px(4), 0))
                self.speak_button(body, f"{item['prompt']}. {item['answer'] or ''}", compact=True).pack(side="right", anchor="n", padx=(self.px(8), 0))
                text = tk.Frame(body, bg=surface)
                text.pack(side="left", fill="x", expand=True)
                self.fit_wrap(tk.Label(text, text=item["prompt"], bg=surface, fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 12), wraplength=self.px(300), justify="left"))
                self.fit_wrap(tk.Label(text, text=item["answer"] or "Self-check (no saved answer)", bg=surface, fg=COLORS["muted"], font=self.font("Segoe UI", 11), wraplength=self.px(300), justify="left"), pady=(self.px(2), 0))
            update_heading()

        def remove_item(index):
            if 0 <= index < len(items):
                items.pop(index)
                refresh()

        def add_typed(_event=None):
            item = setbuilder.typed_item(question.get(), answer.get("1.0", "end"))
            if item is None:
                self.toast_message("Type a question first.")
                question.focus_set()
                return "break"
            items.append(item)
            question.delete(0, "end")
            answer.delete("1.0", "end")
            refresh()
            question.focus_set()
            return "break"

        def split_notes():
            new_items = setbuilder.notes_to_items(notes.get("1.0", "end"), prompt.get())
            if not new_items:
                self.toast_message("Paste a few lines or facts first.")
                notes.focus_set()
                return
            items.extend(new_items)
            notes.delete("1.0", "end")
            refresh()
            self.toast_message(f"Made {len(new_items)} card{'s' if len(new_items) != 1 else ''} from your notes. Check them on the right.")

        def clear_items():
            if items and not self.dialog_confirm("Clear these cards?", f"Remove the {len(items)} unsaved card{'s' if len(items) != 1 else ''} from this set? Nothing saved is changed.", "Clear cards"):
                return
            items.clear()
            refresh()

        ttk.Button(typed_actions, text="Add card", cursor="hand2", command=add_typed).pack(side="left")
        ttk.Button(paste_actions, text="Split into cards", cursor="hand2", command=split_notes).pack(side="left")
        self.speak_button(paste_actions, lambda: notes.get("1.0", "end")).pack(side="left", padx=(self.px(8), 0))
        question.bind("<Return>", lambda _event: (answer.focus_set(), "break")[1])
        answer.bind("<Return>", add_typed)
        answer.bind("<KP_Enter>", add_typed)
        answer.bind("<Shift-Return>", lambda _event: None)

        def show_saved(name, count):
            for child in after_save.winfo_children():
                child.destroy()
            self.fit_wrap(tk.Label(after_save, text=f"Saved {count} card{'s' if count != 1 else ''} to {name}.", bg=surface, fg=COLORS["green"], font=self.font("Segoe UI Semibold", 11), wraplength=self.px(360), justify="left"))
            ttk.Button(after_save, text="Study this set", cursor="hand2", command=lambda: self.study_deck(name)).pack(fill="x", pady=(self.px(8), 0))

        def save():
            name = setbuilder.clean_set_name(name_var.get())
            if not name:
                self.toast_message("Name your set first.")
                name_entry.focus_set()
                return
            # Whatever is still in the boxes is part of the set too.
            typed = setbuilder.typed_item(question.get(), answer.get("1.0", "end"))
            if typed:
                items.append(typed)
            if normalize_space(notes.get("1.0", "end")):
                items.extend(setbuilder.notes_to_items(notes.get("1.0", "end"), prompt.get()))
            if not items and not any(self.pending_media.values()):
                self.toast_message("Add at least one card first.")
                return
            chunks = [f"{item['prompt']} => {item['answer'] or SELF_CHECK_ANSWER}" if item["kind"] == "qa" else item["answer"] for item in items]
            self.store.add_capture(Capture(title=name, notes="\n".join(chunks), chunks=chunks, **self.pending_media))
            new_cards = []
            for index, item in enumerate(items, 1):
                association = "Typed or pasted as a question and answer." if item["kind"] == "qa" else "Made from pasted notes."
                new_cards.append(Card(deck=name, front=item["prompt"], back=item["answer"] or SELF_CHECK_ANSWER, pathway=f"Set > {name} > Card {index}", association=association, **self.pending_media))
            if not new_cards:
                new_cards.append(Card(deck=name, front=f"What does the attached cue help you remember about {name}?", back=f"Use the attached media to recall {name}.", pathway=f"Set > {name} > Cue", association="Use attached media as a memory cue.", **self.pending_media))
            # One save for the whole batch instead of one per card.
            self.store.add_cards(new_cards)
            items.clear()
            question.delete(0, "end")
            answer.delete("1.0", "end")
            notes.delete("1.0", "end")
            self.pending_media = {"text_file": "", "image": "", "audio": "", "video": ""}
            for kind, label in labels.items():
                label.configure(text=f"No {self.MEDIA_NAMES.get(kind, kind)} selected")
            self.view_drafts["capture"] = {"name": name}
            refresh()
            show_saved(name, len(new_cards))
            self.toast_message(f"Saved {len(new_cards)} card{'s' if len(new_cards) != 1 else ''} to {name}.")

        save_button.configure(command=save)
        clear_button.configure(command=clear_items)
        name_var.trace_add("write", update_heading)
        show_mode()
        show_more()
        refresh()
        if not name_var.get():
            name_entry.focus_set()
        self.register_draft_saver("capture", lambda: {
            "name": name_var.get(),
            "mode": mode.get(),
            "prompt": prompt.get(),
            "question": question.get(),
            "answer": answer.get("1.0", "end").strip(),
            "notes": notes.get("1.0", "end").strip(),
            "items": [dict(item) for item in items],
            "more_open": more_open.get(),
            "pending_media": dict(self.pending_media),
        })

    def media_summary(self, item):
        parts = []
        names = {"text_file": "Text", "image": "Image", "audio": "Audio", "video": "Video"}
        for kind in ("text_file", "image", "audio", "video"):
            path = getattr(item, kind, "")
            if path:
                parts.append(f"{names[kind]}: {Path(path).name}")
        return " | ".join(parts)

    def attachment(self, path):
        """The attached file, only if it is in this profile's attachments folder (see media.attachment_file)."""
        return media.attachment_file(path, self.store.attachment_dir)

    def open_media(self, path):
        target = self.attachment(path)
        if target is None:
            self.toast_message("Media file was not found.")
            return
        try:
            system_open(target)
        except OSError as exc:
            self.dialog_alert("Could not open media", str(exc), "error")

    def audio_play_button(self, parent, path):
        """Play/Stop inside the app; falls back to the default player if needed."""
        button = ttk.Button(parent, text="\u25b6 Play Audio")
        self.add_tooltip(button, "Play the attached audio here. Press again to stop.")

        def playing():
            target = self.attachment(path)
            return target is not None and self.audio_player.path == str(target) and self.audio_player.is_playing()

        def watch():
            if not button.winfo_exists():
                return
            if playing():
                button.after(250, watch)
            else:
                button.configure(text="\u25b6 Play Audio")

        def toggle():
            if playing():
                self.audio_player.stop()
                button.configure(text="\u25b6 Play Audio")
                return
            target = self.attachment(path)
            if target is None:
                self.toast_message("Audio file was not found.")
                return
            if self.audio_player.play(target):
                button.configure(text="\u25a0 Stop")
                button.after(250, watch)
            else:
                self.open_media(path)

        button.configure(command=toggle)
        return button

    def image_photo(self, path, max_width=620, max_height=360):
        """A Tk image of any picture Windows can read, scaled to fit (cached)."""
        source = self.attachment(path)
        if source is None:
            return None
        width, height = self.px(max_width), self.px(max_height)
        preview = media.image_preview(source, self.store.attachment_dir / "previews", width, height)
        if preview is None:
            return None
        key = str(preview)
        photo = self.preview_photos.get(key)
        if photo is None:
            try:
                photo = tk.PhotoImage(file=key)
            except tk.TclError:
                return None
            if len(self.preview_photos) > 40:
                self.preview_photos.clear()
            self.preview_photos[key] = photo
        return photo

    def render_media_controls(self, parent, item):
        media = [(kind, getattr(item, kind, "")) for kind in ("text_file", "image", "audio", "video") if getattr(item, kind, "")]
        if not media:
            return
        panel = self.card(parent, "AltCard.TFrame", 16)
        panel.pack(fill="x", pady=(8, 12))
        ttk.Label(panel, text="Attached cues", style="AltH2.TLabel").pack(anchor="w")
        ttk.Label(panel, text=self.media_summary(item), style="AltMuted.TLabel", wraplength=1040).pack(anchor="w", pady=(4, 10))
        action_row = ttk.Frame(panel, style="AltCard.TFrame")
        action_row.pack(fill="x")
        for index, (kind, path) in enumerate(media):
            label = "Note" if kind == "text_file" else kind.title()
            if kind == "audio":
                button = self.audio_play_button(action_row, path)
            else:
                action = "Open" if kind == "text_file" else "View" if kind == "image" else "Play"
                button = ttk.Button(action_row, text=f"{action} {label}", command=lambda value=path: self.open_media(value))
                self.add_tooltip(button, "Opens in your photo viewer." if kind == "image" else "Opens in your video player." if kind == "video" else "Opens the full note.")
            button.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 8, 0))
            action_row.columnconfigure(index, weight=1)

        for kind, path in media:
            source = self.attachment(path)
            if kind == "text_file" and source is not None:
                try:
                    preview = extract_document_text(source).strip()
                except Exception:
                    preview = ""
                if preview:
                    text_panel = self.card(panel, "WarmCard.TFrame", 12)
                    text_panel.pack(fill="x", pady=(10, 0))
                    ttk.Label(text_panel, text="Note preview", style="WarmH2.TLabel").pack(anchor="w")
                    ttk.Label(text_panel, text=preview[:900] + ("..." if len(preview) > 900 else ""), style="WarmCard.TLabel", wraplength=1000).pack(anchor="w", pady=(4, 0))
            elif kind == "image":
                photo = self.image_photo(path)
                if photo:
                    self.media_images.append(photo)
                    holder = tk.Frame(panel, bg=COLORS["alt"])
                    holder.pack(fill="x", pady=(10, 0))
                    tk.Label(holder, image=photo, bg=COLORS["alt"]).pack(anchor="w")
            elif kind == "video":
                hint = "Videos play in your usual video player."
                ttk.Label(panel, text=hint, style="AltMuted.TLabel", wraplength=1040).pack(anchor="w", pady=(8, 0))

    def resource_items(self, limit=3):
        pool = list(reversed(self.store.captures)) + list(reversed(self.store.cards))
        return [item for item in pool if any(getattr(item, kind, "") for kind in ("text_file", "image", "audio", "video"))][:limit]

    def render_resource_strip(self, parent, title="Study resources"):
        # A small practice-hub strip keeps notes and media nearby without
        # turning every study page into a full library view.
        items = self.resource_items()
        if not items:
            return
        panel = self.card(parent, "AltCard.TFrame", 14)
        panel.pack(fill="x", padx=(0, 8), pady=(0, 12))
        ttk.Label(panel, text=title, style="AltH2.TLabel").pack(anchor="w")
        ttk.Label(panel, text="Attached notes, images, audio, and video stay reachable from study pages.", style="AltMuted.TLabel", wraplength=980).pack(anchor="w", pady=(4, 8))
        for item in items:
            name = getattr(item, "title", "") or getattr(item, "front", "") or "Saved material"
            row = tk.Frame(panel, bg=COLORS["alt"])
            row.pack(fill="x", pady=(0, self.px(6)))
            tk.Label(row, text=name, bg=COLORS["alt"], fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 11), anchor="w").pack(side="left", fill="x", expand=True, padx=(0, self.px(8)))
            for kind, label, action in [
                ("text_file", "Note", "Read"),
                ("image", "Image", "Display"),
                ("audio", "Audio", "Play"),
                ("video", "Video", "Play"),
            ]:
                path = getattr(item, kind, "")
                if not path:
                    continue
                button = ttk.Button(row, text=label, command=lambda value=path: self.open_media(value))
                button.pack(side="left", padx=(self.px(6), 0))
                self.add_tooltip(button, f"{action} the attached {label.lower()} cue.")

    def view_review(self):
        page = ScrollFrame(self.view_host)
        page.pack(fill="both", expand=True)
        host = self.card(page.inner)
        host.pack(fill="both", expand=True, padx=(0, 8))
        if self.deck_filter:
            filter_row = tk.Frame(host, bg=COLORS["alt"], padx=self.px(14), pady=self.px(8))
            filter_row.pack(fill="x", pady=(0, 12))
            tk.Label(filter_row, text=f"Studying deck: {self.deck_filter}", bg=COLORS["alt"], fg=COLORS["primary"], font=self.font("Segoe UI Semibold", 11)).pack(side="left")
            ttk.Button(filter_row, text="Clear filter", command=self.clear_deck_filter).pack(side="right")
        due = self.store.due_cards(self.deck_filter)
        if not due:
            ttk.Label(host, text="No cards due today", style="H2.TLabel").pack(anchor="w")
            ttk.Label(host, text="Capture new material or browse your library.", style="Card.TLabel").pack(anchor="w", pady=(8, 0))
            return
        self.current_review = due[0]
        ttk.Label(host, text=f"{len(due)} due card{'s' if len(due) != 1 else ''}", style="H2.TLabel").pack(anchor="w")
        ttk.Label(host, text="Review now opens in Test Lab so the answer, reveal, Smart Check, and rating stay on one focused page.", style="CardMuted.TLabel", wraplength=1040).pack(anchor="w", pady=(8, 16))
        preview = self.card(host, "AltCard.TFrame", 18)
        preview.pack(fill="x", pady=(0, 12))
        ttk.Label(preview, text="Next card", style="AltH2.TLabel").pack(anchor="w")
        ttk.Label(preview, text=self.current_review.front, style="AltCard.TLabel", wraplength=1000).pack(anchor="w", pady=(6, 0))
        self.button_row(host, [("Start in Test Lab", lambda: self.open_testing(self.current_review, "review", "review"), "Primary.TButton"), ("Focus Queue", lambda: self.show_view("focus"), "TButton"), ("Library", lambda: self.show_view("library"), "TButton")])

    def render_review(self, host, show_answer=False, assessment=None, response_text=""):
        if not getattr(self, "_building_view", False) and not getattr(self, "_hidden_active", False):
            return self.smooth(lambda: self.render_review(host, show_answer, assessment, response_text))()
        for child in host.winfo_children():
            child.destroy()
        due = self.store.due_cards()
        if not due:
            ttk.Label(host, text="No cards due today", style="H2.TLabel").pack(anchor="w")
            ttk.Label(host, text="Capture new material or browse your library.", style="Card.TLabel").pack(anchor="w", pady=(8, 0))
            return
        if not self.current_review or self.current_review not in due:
            self.current_review = due[0]
        card = self.current_review
        ttk.Label(host, text=f"{card.deck} | Next review: {card.next_review}", style="CardMuted.TLabel").pack(anchor="w")
        ttk.Label(host, text=card.front, style="H2.TLabel", wraplength=1040).pack(anchor="w", pady=(10, 8))
        self.speak_button(host, card.front if not show_answer else f"{card.front}. The answer is: {card.back}").pack(anchor="w", pady=(0, 12))
        if not show_answer and self.accessibility.get("read_aloud"):
            self.after(250, lambda: self.speak(card.front))
        self.render_media_controls(host, card)
        if show_answer:
            if response_text:
                ttk.Label(host, text=f"Your response: {response_text}", style="CardMuted.TLabel", wraplength=1040).pack(anchor="w", pady=(0, 10))
            if assessment:
                ttk.Label(host, text=self.describe_assessment(assessment), style="H2.TLabel", wraplength=1040).pack(anchor="w", pady=(0, 12))
                self.render_bucket_highlight(host, assessment["bucket"])
            ttk.Label(host, text=card.back, style="Card.TLabel", wraplength=1040).pack(anchor="w", pady=(0, 14))
            ttk.Label(host, text=f"Path: {card.pathway or 'Not set'}", style="CardMuted.TLabel").pack(anchor="w")
            ttk.Label(host, text=f"Hook: {card.association or 'Not set'}", style="CardMuted.TLabel").pack(anchor="w", pady=(0, 16))
            row = ttk.Frame(host, style="Card.TFrame")
            row.pack(fill="x")
            if assessment:
                ttk.Button(row, text=f"Use Smart Rating ({self.rating_label(assessment['bucket'])})", style="Primary.TButton", command=lambda: self.rate_review(host, assessment["quality"], assessment)).grid(row=0, column=0, sticky="ew", padx=(0, 8))
                row.columnconfigure(0, weight=2)
                offset = 1
            else:
                offset = 0
            for index, (label, quality) in enumerate([("Again", 1), ("Good", 4), ("Easy", 5)]):
                style = self.bucket_style(label) if assessment and assessment["bucket"] == label else "TButton"
                ttk.Button(row, text=self.rating_label(label), style=style, command=lambda value=quality: self.rate_review(host, value)).grid(row=0, column=index + offset, sticky="ew", padx=(0 if index == 0 and not offset else 8, 0))
                row.columnconfigure(index + offset, weight=1)
            ttk.Button(row, text="Open Test Page", command=lambda: self.open_testing(card, "review", "review")).grid(row=0, column=offset + 3, sticky="ew", padx=(8, 0))
            row.columnconfigure(offset + 3, weight=1)
            return

        response = self.answer_area(host, "Your recall", "Type your answer, transcript, caption, or media description.", 5)

        def smart_check():
            if card.back == SELF_CHECK_ANSWER:
                # Nothing saved to compare against: show the card and let the
                # learner rate themselves instead of scoring against filler.
                self.render_review(host, True, None, response.get("1.0", "end").strip())
                return
            result = answer_assessment(response.get("1.0", "end").strip(), card.back)
            self.render_review(host, True, result, response.get("1.0", "end").strip())

        self.button_row(host, [("Smart Check", smart_check, "Primary.TButton"), ("Reveal Only", lambda: self.render_review(host, True), "TButton"), ("Open Test Page", lambda: self.open_testing(card, "review", "review"), "TButton")])

    def rate_review(self, host, quality, assessment=None):
        self.store.schedule(self.current_review, quality, assessment)
        self.current_review = None
        self.toast_message("Review scheduled.")
        self.render_review(host)

    def view_testing(self):
        draft = self.view_drafts.get("testing", {})
        page = ScrollFrame(self.view_host)
        page.pack(fill="both", expand=True)
        card = self.testing_card or (self.store.due_cards()[0] if self.store.due_cards() else self.store.cards[0] if self.store.cards else None)
        panel = self.card(page.inner)
        panel.pack(fill="both", expand=True, padx=(0, 8))
        if not card:
            ttk.Label(panel, text="Add cards first.", style="Card.TLabel").pack(anchor="w")
            ttk.Button(panel, text="Back", command=lambda: self.show_view(self.return_view)).pack(fill="x", pady=(16, 0))
            return
        self.testing_card = card
        ttk.Label(panel, text="Answer from memory, then check or reveal.", style="CardMuted.TLabel").pack(anchor="w", pady=(0, self.px(10)))
        ttk.Label(panel, text=card.front, style="H2.TLabel", wraplength=1040).pack(anchor="w", pady=(0, 8))
        self.speak_button(panel, card.front).pack(anchor="w", pady=(0, 14))
        if self.accessibility.get("read_aloud"):
            self.after(250, lambda: self.speak(card.front))
        self.render_media_controls(panel, card)
        response = self.answer_area(panel, "Your answer", "Type what you remember.", 5)
        if draft.get("card_id") == card.id and draft.get("context") == self.testing_context:
            response.insert("1.0", draft.get("response", ""))
        result_row = ttk.Frame(panel, style="Card.TFrame")
        result_row.pack(fill="x", pady=(0, 10))
        self.speak_button(result_row, lambda: str(result.cget("text")), "Read result", compact=True).pack(side="right", anchor="n")
        result = ttk.Label(result_row, text="Smart Check will highlight the suggested bucket.", style="CardMuted.TLabel", wraplength=1040)
        result.pack(side="left", fill="x", expand=True, anchor="w")
        self.bind_rewrap(result)
        bucket_holder = ttk.Frame(panel, style="Card.TFrame")
        bucket_holder.pack(fill="x")
        answer_holder = ttk.Frame(panel, style="Card.TFrame")
        answer_visible = {"value": False}
        latest_assessment = {"value": None}

        def smart_check():
            for child in bucket_holder.winfo_children():
                child.destroy()
            if card.back == SELF_CHECK_ANSWER:
                latest_assessment["value"] = None
                result.configure(text=self.plain(
                    "This is a self-check card with no saved answer. Reveal it if helpful, then rate yourself below.",
                    "There is no saved answer for this one. Think about how well you remembered, then pick a button below.",
                ))
                return
            checked = answer_assessment(response.get("1.0", "end").strip(), card.back)
            latest_assessment["value"] = checked
            result.configure(text=self.describe_assessment(checked))
            self.render_bucket_highlight(bucket_holder, checked["bucket"])
            if self.accessibility.get("read_aloud"):
                self.speak(self.describe_assessment(checked) if self.accessibility.get("simple_language") else checked["label"])

        def reveal():
            if answer_visible["value"]:
                answer_holder.pack_forget()
                answer_visible["value"] = False
                return
            for child in answer_holder.winfo_children():
                child.destroy()
            ttk.Label(answer_holder, text="Saved answer", style="CardMuted.TLabel").pack(anchor="w")
            ttk.Label(answer_holder, text=card.back, style="Card.TLabel", wraplength=1040).pack(anchor="w", pady=(4, 8))
            self.speak_button(answer_holder, card.back).pack(anchor="w")
            answer_holder.pack(fill="x", pady=(8, 0))
            answer_visible["value"] = True
            if self.accessibility.get("read_aloud"):
                self.speak(card.back)

        def schedule_from_lab(quality, assessment=None):
            self.store.schedule(card, quality, assessment)
            self.toast_message("Review scheduled.")
            self.testing_card = None
            self.current_review = None
            self.view_drafts["testing"] = {}
            remaining_due = self.store.due_cards(self.deck_filter)
            if self.testing_context == "review" and remaining_due:
                next_card = remaining_due[0]
                self.open_testing(next_card, self.return_view, "review")
            else:
                self.show_view(self.return_view)

        def smart_rating():
            assessment = latest_assessment["value"]
            if not assessment:
                self.toast_message("Smart Check first, then use Smart Rating.")
                return
            schedule_from_lab(assessment["quality"], assessment)

        actions = ttk.Frame(panel, style="Card.TFrame")
        actions.pack(fill="x", pady=(self.px(10), 0))
        action_defs = [
            ("Smart Check", "Primary.TButton", smart_check),
            ("Reveal answer", "TButton", reveal),
            ("Use suggested rating", "TButton", smart_rating),
            ("Back", "TButton", lambda: self.show_view(self.return_view)),
        ]
        for column, (label, style, command) in enumerate(action_defs):
            button = ttk.Button(actions, text=label, style=style, command=command)
            button.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else self.px(8), 0))
            self.add_tooltip(button, self.action_hint(label))
        for column in range(4):
            actions.columnconfigure(column, weight=1)

        def skip_for_today():
            self.store.bury_card(card, 1)
            self.toast_message("Skipped \u2014 it'll come back tomorrow. Doesn't count as a miss.")
            self.testing_card = None
            self.current_review = None
            self.view_drafts["testing"] = {}
            remaining_due = self.store.due_cards(self.deck_filter)
            if self.testing_context == "review" and remaining_due:
                self.open_testing(remaining_due[0], self.return_view, "review")
            else:
                self.show_view(self.return_view)

        def undo_last_rating():
            pending = self.store.last_action
            action_card_id = pending["card_id"] if pending else None
            if self.store.undo_last():
                self.toast_message("Last rating undone.")
                restored = next((c for c in self.store.cards if c.id == action_card_id), None)
                if restored:
                    self.open_testing(restored, self.return_view, "review")
                else:
                    self.show_view(self.return_view)
            else:
                self.toast_message("Nothing to undo yet.")

        if self.testing_context == "review":
            ttk.Label(panel, text=f"Rate your recall  \u2022  keyboard shortcuts 1-4  \u2022  {shortcut('Z')} to undo", style="CardMuted.TLabel").pack(anchor="w", pady=(self.px(10), self.px(4)))
            rating = ttk.Frame(panel, style="Card.TFrame")
            rating.pack(fill="x")
            for index, (label, quality, key) in enumerate([("Again", 1, "1"), ("Review", 3, "2"), ("Good", 4, "3"), ("Easy", 5, "4")]):
                button = ttk.Button(rating, text=f"{self.rating_label(label)}  ({key})", style=self.bucket_style(label), command=lambda value=quality: schedule_from_lab(value))
                button.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else self.px(8), 0))
                self.add_tooltip(button, self.action_hint(label))
                rating.columnconfigure(index, weight=1)
            secondary = ttk.Frame(panel, style="Card.TFrame")
            secondary.pack(fill="x", pady=(self.px(8), 0))
            skip_button = ttk.Button(secondary, text="Skip for today", command=skip_for_today)
            skip_button.grid(row=0, column=0, sticky="ew", padx=(0, self.px(8)))
            self.add_tooltip(skip_button, "Bury this card until tomorrow without affecting its stats \u2014 doesn't count as a miss.")
            undo_button = ttk.Button(secondary, text=f"Undo last rating ({shortcut('Z')})", command=undo_last_rating, state=("normal" if self.store.last_action else "disabled"))
            undo_button.grid(row=0, column=1, sticky="ew")
            self.add_tooltip(undo_button, "Misclick? Roll back the last card you rated.")
            secondary.columnconfigure(0, weight=1)
            secondary.columnconfigure(1, weight=1)
            self.bind_rating_hotkeys(schedule_from_lab, undo_last_rating)
        self.register_draft_saver("testing", lambda: {
            "card_id": card.id,
            "context": self.testing_context,
            "response": response.get("1.0", "end").strip(),
        })

    def view_quiz(self):
        draft = self.view_drafts.get("quiz", {})
        page = ScrollFrame(self.view_host)
        page.pack(fill="both", expand=True)
        host = self.card(page.inner)
        host.pack(fill="both", expand=True, padx=(0, 8))
        if draft.get("card_ids"):
            card_by_id = {card.id: card for card in self.store.cards}
            self.quiz_cards = [card_by_id[card_id] for card_id in draft["card_ids"] if card_id in card_by_id]
        else:
            self.quiz_cards = random.sample(self.store.cards, min(5, len(self.store.cards))) if self.store.cards else []
        self.quiz_round = min(int(draft.get("round", 0)), len(self.quiz_cards))
        self.quiz_score = int(draft.get("score", 0))
        self.quiz_mode = draft.get("mode", self.quiz_mode)
        self.render_quiz(host)

    def render_quiz(self, host):
        if not getattr(self, "_building_view", False) and not getattr(self, "_hidden_active", False):
            return self.smooth(lambda: self.render_quiz(host))()
        for child in host.winfo_children():
            child.destroy()
        if not self.store.cards:
            ttk.Label(host, text="Add cards first", style="H2.TLabel").pack(anchor="w")
            return
        self.register_draft_saver("quiz", lambda: {
            "card_ids": [card.id for card in self.quiz_cards],
            "round": self.quiz_round,
            "score": self.quiz_score,
            "mode": self.quiz_mode,
        })
        mode = ttk.Frame(host, style="Card.TFrame")
        mode.pack(anchor="w", pady=(0, 16))
        self_check = ttk.Button(mode, text="Type the answer", style="PillOn.TButton" if self.quiz_mode == "self" else "Pill.TButton", cursor="hand2", command=lambda: self.set_quiz_mode(host, "self"))
        self_check.grid(row=0, column=0, sticky="w", padx=(0, self.px(6)))
        choices_button = ttk.Button(mode, text="Multiple choice", style="PillOn.TButton" if self.quiz_mode == "choices" else "Pill.TButton", cursor="hand2", command=lambda: self.set_quiz_mode(host, "choices"))
        choices_button.grid(row=0, column=1, sticky="w")
        self.add_tooltip(self_check, self.action_hint("Self Check"))
        self.add_tooltip(choices_button, self.action_hint("Multiple Choice"))

        if self.quiz_mode == "choices" and len(self.store.cards) < 2:
            ttk.Label(host, text="Multiple Choice needs at least two cards.", style="H2.TLabel").pack(anchor="w")
            return
        if self.quiz_round >= len(self.quiz_cards):
            summary = f"Score: {self.quiz_score} / {len(self.quiz_cards)}" if self.quiz_mode == "choices" else f"Completed: {len(self.quiz_cards)} cards"
            ttk.Label(host, text=summary, style="H2.TLabel").pack(anchor="w")
            play = ttk.Button(host, text="Play Again", style="Primary.TButton", command=lambda: self.show_view("quiz"))
            play.pack(fill="x", pady=(16, 0))
            self.add_tooltip(play, self.action_hint("Play Again"))
            return
        card = self.quiz_cards[self.quiz_round]
        ttk.Label(host, text=f"Question {self.quiz_round + 1} of {len(self.quiz_cards)}", style="CardMuted.TLabel").pack(anchor="w")
        ttk.Label(host, text=card.front, style="H2.TLabel", wraplength=1040).pack(anchor="w", pady=(10, 8))
        choices = []
        if self.quiz_mode == "choices":
            wrong = [item.back for item in self.store.cards if item.id != card.id]
            choices = random.sample(wrong, min(3, len(wrong))) + [card.back]
            random.shuffle(choices)
        spoken = card.front + (". The choices are: " + "; ".join(choices) if choices else "")
        self.speak_button(host, spoken).pack(anchor="w", pady=(0, 16))
        if self.accessibility.get("read_aloud"):
            self.after(250, lambda: self.speak(spoken))
        self.render_media_controls(host, card)
        if self.quiz_mode == "choices":
            for choice in choices:
                ttk.Button(host, text=choice, command=lambda value=choice: self.answer_quiz(host, value, card.back)).pack(fill="x", pady=5)
            return
        self.button_row(host, [("Open in Test Lab", lambda: self.open_testing(card, "quiz", "quiz"), "Primary.TButton"), ("Next card", lambda: self.next_self_quiz(host), "TButton")])

    def set_quiz_mode(self, host, mode):
        self.quiz_mode = mode
        self.quiz_round = 0
        self.quiz_score = 0
        self.quiz_cards = random.sample(self.store.cards, min(5, len(self.store.cards)))
        self.render_quiz(host)

    def next_self_quiz(self, host):
        self.quiz_round += 1
        self.render_quiz(host)

    def answer_quiz(self, host, choice, answer):
        if choice == answer:
            self.quiz_score += 1
            self.toast_message("Correct.")
        else:
            self.toast_message(f"Answer: {answer}")
        self.quiz_round += 1
        self.render_quiz(host)

    # ------------------------------------------------------------------
    # Talk-back study: hands-free review
    # ------------------------------------------------------------------
    def talkback_queue(self):
        """Cards with saved answers: due ones first, else ones that need work."""
        answerable = lambda cards: [card for card in cards if normalize_space(card.back) and card.back != SELF_CHECK_ANSWER]
        due = answerable(self.store.due_cards(self.deck_filter))
        if due:
            return due[:20], False
        pool = self.store.weak_cards()
        if self.deck_filter:
            pool = [card for card in pool if (card.deck or "General") == self.deck_filter]
        return answerable(pool)[:10], True

    def stop_talkback(self):
        state, self.talkback = self.talkback, None
        self.listener.stop()
        if state is not None:
            pulse = state.get("pulse")
            if pulse:
                try:
                    self.after_cancel(pulse)
                except tk.TclError:
                    pass

    def view_talkback(self):
        page = ScrollFrame(self.view_host)
        page.pack(fill="both", expand=True)
        panel = self.card(page.inner, padding=32)
        panel.pack(fill="both", expand=True, padx=(0, self.px(8)))
        surface = COLORS["surface"]
        queue, practising = self.talkback_queue()
        if not queue:
            ttk.Label(panel, text="Nothing to practise yet", style="H2.TLabel").pack(anchor="w")
            self.fit_wrap(ttk.Label(panel, text="Talk-back study needs cards with saved answers. Make a study set with questions and answers, then come back.", style="CardMuted.TLabel", wraplength=self.px(640)), pady=(self.px(6), self.px(16)))
            ttk.Button(panel, text="Make a study set", style="Primary.TButton", command=self.start_new_set).pack(anchor="w")
            return
        voice_wanted = bool(self.accessibility.get("listen_answers", True))
        state = {
            "queue": queue, "index": 0, "right": 0, "answered": 0, "paused": False,
            # Typed answers until the recogniser is confirmed (and always off Windows).
            "typed": True, "can_listen": False, "phase": "idle", "silences": 0,
            "token": self.route_token, "pulse": None,
        }
        self.talkback = state

        top = tk.Frame(panel, bg=surface)
        top.pack(fill="x")
        progress = tk.Label(top, text="", bg=surface, fg=COLORS["muted"], font=self.font("Segoe UI", 11))
        progress.pack(side="left")
        score = tk.Label(top, text="", bg=surface, fg=COLORS["muted"], font=self.font("Segoe UI", 11))
        score.pack(side="right")
        if practising:
            self.fit_wrap(tk.Label(panel, text="Nothing is due right now, so this round uses cards that need more practice.", bg=surface, fg=COLORS["muted"], font=self.font("Segoe UI", 11), justify="left", wraplength=self.px(640)), pady=(self.px(4), 0))

        question = tk.Label(panel, text="", bg=surface, fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 24), justify="left", anchor="w", wraplength=self.px(900))
        self.fit_wrap(question, pady=(self.px(28), self.px(20)))

        # The listening indicator: a dot (red while the microphone is open,
        # like a recording light) with a plain status line beside it.
        status_row = tk.Frame(panel, bg=surface)
        status_row.pack(fill="x")
        dot_size = self.px(14)
        dot = tk.Canvas(status_row, width=dot_size, height=dot_size, bg=surface, highlightthickness=0)
        dot.pack(side="left", padx=(0, self.px(10)))
        status_icon = tk.Label(status_row, bg=surface)
        status_icon.pack(side="left", padx=(0, self.px(8)))
        status = tk.Label(status_row, text="", bg=surface, fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 13), anchor="w", justify="left")
        status.pack(side="left", fill="x", expand=True)

        heard = tk.Label(panel, text="", bg=surface, fg=COLORS["muted"], font=self.font("Segoe UI", 12), justify="left", anchor="w", wraplength=self.px(900))
        self.fit_wrap(heard, pady=(self.px(14), 0))
        feedback = tk.Label(panel, text="", bg=surface, fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 14), justify="left", anchor="w", wraplength=self.px(900))
        self.fit_wrap(feedback, pady=(self.px(6), 0))

        typed_row = ttk.Frame(panel, style="Card.TFrame")
        typed_entry = ttk.Entry(typed_row, font=self.font("Segoe UI", 13))
        typed_entry.pack(side="left", fill="x", expand=True, padx=(0, self.px(10)))
        check_button = ttk.Button(typed_row, text="Check", style="Primary.TButton", cursor="hand2")
        check_button.pack(side="left")
        typed_anchor = ttk.Frame(panel, style="Card.TFrame")
        typed_anchor.pack(fill="x", pady=(self.px(18), 0))

        controls = ttk.Frame(panel, style="Card.TFrame")
        controls.pack(fill="x", pady=(self.px(18), 0))
        notice = tk.Label(panel, text="", bg=surface, fg=COLORS["muted"], font=self.font("Segoe UI", 11), justify="left", anchor="w", wraplength=self.px(900))
        self.fit_wrap(notice, pady=(self.px(16), 0))
        hint = tk.Label(panel, text="", bg=surface, fg=COLORS["muted"], font=self.font("Segoe UI", 11), justify="left", anchor="w", wraplength=self.px(900))
        self.fit_wrap(hint, pady=(self.px(6), 0))

        icon_size = self.px(18)

        def control(text, icon, command, style="TButton"):
            image = self.line_icon(icon, icon_size, self.on_color(COLORS["primary"]) if style == "Primary.TButton" else COLORS["ink"])
            button = ttk.Button(controls, text=f" {text}", image=image, compound="left", style=style, cursor="hand2", command=command)
            button._memorypal_icon = image
            return button

        def say(text):
            # Without a system voice, say so once per round, not on every card.
            if not self.speak(text, quiet=state.get("voice_warned", False)):
                state["voice_warned"] = True

        def alive():
            return self.talkback is state and state["token"] == self.route_token and panel.winfo_exists()

        def later(ms, callback):
            if alive():
                self.after(ms, lambda: alive() and callback())

        def set_status(text, kind):
            """kind: reading, listening, typing, checking, paused, done."""
            status.configure(text=text)
            icon_name = {"reading": "speaker", "listening": "mic", "typing": "keyboard", "paused": "pause"}.get(kind)
            image = self.line_icon(icon_name, icon_size, COLORS["ink"]) if icon_name else None
            status_icon.configure(image=image or "")
            status_icon._memorypal_icon = image
            colour = {"listening": COLORS["danger"], "reading": COLORS["primary"], "typing": COLORS["primary"]}.get(kind, COLORS["line"])
            draw_dot(colour)
            if state.get("pulse"):
                self.after_cancel(state["pulse"])
                state["pulse"] = None
            if kind == "listening" and not self.accessibility.get("reduce_motion"):
                pulse(True)

        def draw_dot(colour):
            dot.delete("all")
            dot.create_oval(1, 1, dot_size - 1, dot_size - 1, fill=colour, outline=colour)

        def pulse(bright):
            if not alive() or state["phase"] != "listening":
                return
            draw_dot(COLORS["danger"] if bright else self.blend_hex(surface, COLORS["danger"], 0.35))
            state["pulse"] = self.after(520, lambda: pulse(not bright))

        def card():
            return state["queue"][state["index"]]

        def update_counts():
            total = len(state["queue"])
            progress.configure(text=f"Card {min(state['index'] + 1, total)} of {total}")
            score.configure(text=f"{state['right']} right of {state['answered']}" if state["answered"] else "")

        def after_speech(then):
            """Run then() once the voice has finished (never listen over it)."""
            def wait():
                if not alive():
                    return
                if self.speaker.speaking():
                    later(150, wait)
                else:
                    later(self.pace(250), then)
            wait()

        def ask():
            if not alive() or state["paused"]:
                return
            self.listener.stop()
            state["phase"] = "reading"
            state["silences"] = 0
            update_counts()
            question.configure(text=card().front)
            heard.configure(text="")
            feedback.configure(text="")
            typed_entry.delete(0, "end")
            set_status("Reading the question", "reading")
            say(f"Question {state['index'] + 1}. {card().front}")
            after_speech(answer_turn)

        def answer_turn():
            if not alive() or state["paused"]:
                return
            if state["typed"] or not state["can_listen"]:
                state["phase"] = "typing"
                set_status("Type your answer, then press Enter", "typing")
                typed_entry.focus_set()
                return
            seconds = 20 if self.accessibility.get("more_time") else 12
            if not self.listener.start(max_seconds=seconds, initial_silence=seconds / 2, end_silence=1.4):
                switch_to_typing("The microphone couldn't be started, so answers are typed for now.")
                return
            state["phase"] = "listening"
            set_status("Listening. Say your answer.", "listening")
            poll_listener()

        def poll_listener():
            if not alive() or state["phase"] != "listening":
                return
            result = self.listener.poll()
            if result is None:
                later(150, poll_listener)
                return
            if result.heard:
                command = listen.spoken_command(result.text)
                if command == "repeat":
                    ask()
                elif command == "skip":
                    skip()
                elif command == "pause":
                    toggle_pause()
                elif command == "dont_know":
                    judge("", said="I don't know")
                else:
                    judge(result.text, said=result.text)
                return
            if result.status == "silence":
                state["silences"] += 1
                if state["silences"] >= 2:
                    toggle_pause(message="Paused because nothing was heard. Press Resume when you're ready.")
                    return
                state["phase"] = "reading"
                set_status("Didn't catch that. Listening again in a moment.", "reading")
                say("I didn't catch that.")
                after_speech(answer_turn)
                return
            switch_to_typing(f"Speech recognition stopped: {result.message} Answers are typed for now.")

        def switch_to_typing(message):
            state["typed"] = True
            self.listener.stop()
            notice.configure(text=message)
            refresh_controls()
            if state["phase"] in ("listening", "typing", "reading"):
                state["phase"] = "typing"
                set_status("Type your answer, then press Enter", "typing")
                typed_entry.focus_set()

        def judge(answer_text, said=""):
            if not alive() or state["phase"] not in ("listening", "typing"):
                return
            self.listener.stop()
            state["phase"] = "checking"
            current = card()
            checked = answer_assessment(answer_text, current.back)
            correct = checked["bucket"] in ("Good", "Easy")
            state["answered"] += 1
            state["right"] += 1 if correct else 0
            self.store.schedule(current, checked["quality"], checked)
            heard.configure(text=f"You said: {said}" if said else "")
            if correct:
                message = "Correct."
                feedback.configure(text=message, fg=COLORS["green"])
            else:
                message = f"Not quite. The answer is {current.back}."
                feedback.configure(text=message, fg=COLORS["ink"])
            update_counts()
            set_status("Checking", "checking")
            say(message)
            after_speech(next_card)

        def next_card():
            if not alive():
                return
            state["index"] += 1
            if state["index"] >= len(state["queue"]):
                finish()
            else:
                ask()

        def skip():
            if not alive():
                return
            self.listener.stop()
            self.stop_speaking()
            state["paused"] = False
            refresh_controls()
            next_card()

        def repeat():
            if not alive():
                return
            self.stop_speaking()
            state["paused"] = False
            refresh_controls()
            ask()

        def toggle_pause(message=""):
            if not alive():
                return
            state["paused"] = not state["paused"]
            if state["paused"]:
                self.listener.stop()
                self.stop_speaking()
                state["phase"] = "paused"
                set_status(message or "Paused", "paused")
            else:
                ask()
            refresh_controls()

        def toggle_typing():
            if not state["can_listen"]:
                return
            state["typed"] = not state["typed"]
            notice.configure(text="")
            refresh_controls()
            if state["phase"] in ("listening", "typing"):
                self.listener.stop()
                state["phase"] = "typing" if state["typed"] else "reading"
                answer_turn()

        def check_typed(_event=None):
            if state["phase"] != "typing":
                return "break"
            text = typed_entry.get()
            judge(text, said=normalize_space(text) or "(nothing)")
            return "break"

        def finish():
            self.listener.stop()
            state["phase"] = "done"
            for child in panel.winfo_children():
                child.destroy()
            total = state["answered"]
            summary = f"You got {state['right']} of {total} right." if total else "Round finished."
            ttk.Label(panel, text="Round finished", style="H2.TLabel").pack(anchor="w")
            ttk.Label(panel, text=summary, style="Card.TLabel").pack(anchor="w", pady=(self.px(8), self.px(20)))
            row = ttk.Frame(panel, style="Card.TFrame")
            row.pack(anchor="w")
            ttk.Button(row, text="Study again", style="Primary.TButton", cursor="hand2", command=lambda: self.show_view("talkback")).pack(side="left")
            ttk.Button(row, text="Back to Study", cursor="hand2", command=lambda: self.show_view("study")).pack(side="left", padx=(self.px(10), 0))
            say(f"Round finished. {summary}")

        def refresh_controls():
            for child in controls.winfo_children():
                child.destroy()
            buttons = [
                control("Resume" if state["paused"] else "Pause", "play" if state["paused"] else "pause", toggle_pause),
                control("Repeat", "repeat", repeat),
                control("Skip", "skip", skip),
            ]
            if state["can_listen"]:
                buttons.append(control("Answer by voice" if state["typed"] else "Type instead", "mic" if state["typed"] else "keyboard", toggle_typing))
            for column, button in enumerate(buttons):
                button.grid(row=0, column=column, sticky="w", padx=(0 if column == 0 else self.px(10), 0))
            if state["typed"]:
                typed_row.pack(fill="x", before=typed_anchor)
            else:
                typed_row.pack_forget()
            hint.configure(text="Say \"repeat\", \"skip\", \"pause\" or \"I don't know\" at any time." if state["can_listen"] and not state["typed"] else "")

        check_button.configure(command=check_typed)
        typed_entry.bind("<Return>", check_typed)
        typed_entry.bind("<KP_Enter>", check_typed)

        def recogniser_ready(available, _error=None):
            if not alive():
                return
            state["can_listen"] = bool(available) and voice_wanted
            state["typed"] = not state["can_listen"]
            if not available and not getattr(self, "_talkback_notice_given", False):
                # Said once per run of the app, not on every card.
                self._talkback_notice_given = True
                text = ("This computer has no offline speech recogniser, so type your answers. Questions and results are still read aloud."
                        if not listen.platform_supported() else
                        "Windows speech recognition isn't set up on this computer, so type your answers. Questions and results are still read aloud.")
                notice.configure(text=text)
                refresh_controls()
                # Say it once too, since this mode is meant to be used by ear.
                say("Type your answers. I'll still read the questions and results aloud.")
                after_speech(ask)
                return
            elif available and not voice_wanted:
                notice.configure(text="Listening is turned off in Settings, so answers are typed.")
            refresh_controls()
            ask()

        update_counts()
        refresh_controls()
        set_status("Getting ready", "checking")
        if not listen.platform_supported():
            later(50, lambda: recogniser_ready(False))
        else:
            self.run_in_background(self.listener.probe, recogniser_ready)

    def practice_text(self, source="all"):
        lines = []
        if source in ("all", "captures"):
            for capture in self.store.captures:
                for index, bit in enumerate(capture.chunks or split_study_bits(capture.notes), 1):
                    lines.append(f"{capture.title} - bit {index} => {bit}")
        if source in ("all", "cards"):
            for card in self.store.cards:
                if card.back:
                    lines.append(f"{card.front or card.deck} => {card.back}")
        return "\n".join(lines)

    def practice_items_from_saved(self, source="all"):
        items = []
        if source in ("all", "captures"):
            for capture in self.store.captures:
                for index, bit in enumerate(capture.chunks or split_study_bits(capture.notes), 1):
                    items.append({"prompt": f"{capture.title} - bit {index}", "answer": bit})
        if source in ("all", "cards"):
            for card in self.store.cards:
                if card.back:
                    items.append({"prompt": card.front or card.deck or "Saved card", "answer": card.back})
        return [item for item in items if item["answer"]]

    def practice_items_from_text(self, raw):
        raw = (raw or "").replace("\\n", "\n").replace("/n", "\n")
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        if len(lines) < 2:
            lines = split_study_bits(raw)
        items = []
        for index, line in enumerate(lines, 1):
            parsed = parse_prompt_answer_lines(line)
            if parsed:
                items.extend(parsed)
                continue
            answer = normalize_space(re.sub(r"^[-*\d.)\s]+", "", line))
            prompt = f"Study bit {index}"
            items.append({"prompt": prompt or f"Study bit {index}", "answer": answer})
        return [item for item in items if item["answer"]]

    @staticmethod
    def repetition_steps(bits, start, span):
        # Requested pattern example: start 5 with range 3 becomes
        # 5, 5-4, 5-4-3, then 3-2-1.
        if not bits:
            return []
        start_index = min(max(start, 1), len(bits)) - 1
        span = start_index + 1 if span is None else min(max(span, 1), len(bits))
        steps, current = [], []
        for offset in range(span):
            index = start_index - offset
            if index < 0:
                break
            current.append(index)
            steps.append(("-".join(str(item + 1) for item in current), list(current)))
        if current and current[-1] > 0:
            walk = list(range(current[-1], -1, -1))
            steps.append(("-".join(str(item + 1) for item in walk), walk))
        return steps

    def view_shuffle(self):
        draft = self.view_drafts.get("shuffle", {})
        page = ScrollFrame(self.view_host)
        page.pack(fill="both", expand=True)
        panel = self.card(page.inner)
        panel.pack(fill="x")
        ttk.Label(panel, text="Repetition path", style="H2.TLabel").pack(anchor="w")
        ttk.Label(panel, text="Add each repetition item with a separate prompt and answer. Prompts show first; answers reveal when you choose.", style="CardMuted.TLabel", wraplength=980).pack(anchor="w", pady=(6, 14))

        guide = self.card(panel, "WarmCard.TFrame", 14)
        guide.pack(fill="x", pady=(0, 12))
        ttk.Label(guide, text="Best for list recall", style="WarmH2.TLabel").pack(anchor="w")
        ttk.Label(guide, text="Start from any item, set a loop range, and MemoryPal walks the sequence backward before returning to item 1.", style="WarmCard.TLabel", wraplength=980).pack(anchor="w", pady=(4, 0))
        self.render_resource_strip(page.inner, "Notes and media cues")

        form = self.card(panel, "AltCard.TFrame", 18)
        form.pack(fill="x", pady=(0, 12))
        form.columnconfigure(0, weight=1)
        left = ttk.Frame(form, style="AltCard.TFrame")
        left.grid(row=0, column=0, sticky="nsew")
        right = ttk.Frame(form, style="AltCard.TFrame")
        right.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        ttk.Label(left, text="Question / title", style="AltMuted.TLabel").pack(anchor="w")
        prompt_var = tk.StringVar()
        prompt_var.set(draft.get("prompt", ""))
        prompt_entry = ttk.Entry(left, textvariable=prompt_var)
        prompt_entry.pack(fill="x", pady=(4, 0))
        ttk.Label(right, text="Answer / recall content", style="AltMuted.TLabel").pack(anchor="w")
        answer_box = self.text_box(right, 4, 12)
        answer_box.insert("1.0", draft.get("answer", ""))
        answer_box.pack(fill="both", expand=True, pady=(4, 0))
        bulk_panel = ttk.Frame(form, style="AltCard.TFrame")
        bulk_panel.grid(row=2, column=0, sticky="nsew", pady=(12, 0))
        ttk.Label(bulk_panel, text="Optional bulk notes", style="AltMuted.TLabel").pack(anchor="w")
        bulk_text = self.text_box(bulk_panel, 3, 12)
        bulk_text.insert("1.0", draft.get("bulk", ""))
        bulk_text.pack(fill="x", pady=(4, 0))
        ttk.Label(bulk_panel, text="Paste plain facts or numbered notes here if you want to split them into repetition items.", style="AltMuted.TLabel", wraplength=920).pack(anchor="w", pady=(6, 0))

        staged_items = [dict(item) for item in draft.get("staged_items", [])]
        staged_panel = tk.Frame(panel, bg=COLORS["surface"])
        staged_panel.pack(fill="x", pady=(0, 12))
        count_label = ttk.Label(panel, text="0 repetition items staged", style="CardMuted.TLabel")
        count_label.pack(anchor="w", pady=(0, 8))

        @self.smooth
        def refresh_staged():
            for child in staged_panel.winfo_children():
                child.destroy()
            if not staged_items:
                tk.Label(staged_panel, text="No repetition items staged yet.", bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI", 12)).pack(anchor="w")
            for index, item in enumerate(staged_items, 1):
                row = tk.Frame(staged_panel, bg=COLORS["alt"], padx=self.px(14), pady=self.px(10))
                row.pack(fill="x", pady=(0, self.px(8)))
                tk.Label(row, text=f"{index}.", bg=COLORS["alt"], fg=COLORS["primary"], font=self.font("Segoe UI Semibold", 12)).pack(side="left", anchor="n", padx=(0, self.px(8)))
                details = tk.Frame(row, bg=COLORS["alt"])
                details.pack(side="left", fill="x", expand=True)
                tk.Label(details, text=item["prompt"], bg=COLORS["alt"], fg=COLORS["ink"], wraplength=self.px(980), justify="left", font=self.font("Segoe UI Semibold", 12)).pack(anchor="w")
                tk.Label(details, text=item["answer"], bg=COLORS["alt"], fg=COLORS["muted"], wraplength=self.px(980), justify="left", font=self.font("Segoe UI", 11)).pack(anchor="w", pady=(self.px(3), 0))
            count_label.configure(text=f"{len(staged_items)} repetition item{'s' if len(staged_items) != 1 else ''} staged")

        def add_item():
            prompt = normalize_space(prompt_var.get()) or f"Study item {len(staged_items) + 1}"
            answer = normalize_space(answer_box.get("1.0", "end"))
            if not answer:
                self.toast_message("Add an answer or recall item first.")
                return
            staged_items.append({"prompt": prompt, "answer": answer})
            prompt_var.set("")
            answer_box.delete("1.0", "end")
            refresh_staged()

        def split_answer():
            bits = split_study_bits(answer_box.get("1.0", "end"))
            if not bits:
                self.toast_message("Add a few answer lines first.")
                return
            base = normalize_space(prompt_var.get()) or "Study item"
            total = len(bits)
            for index, bit in enumerate(bits, 1):
                prompt = base if total == 1 else f"{base} {index}/{total}"
                staged_items.append({"prompt": prompt, "answer": normalize_space(bit)})
            prompt_var.set("")
            answer_box.delete("1.0", "end")
            refresh_staged()

        def split_bulk():
            bits = self.practice_items_from_text(bulk_text.get("1.0", "end"))
            if not bits:
                self.toast_message("Paste plain facts, titles, or numbered notes first.")
                return
            staged_items.extend(bits)
            bulk_text.delete("1.0", "end")
            refresh_staged()

        def remove_last():
            if staged_items:
                staged_items.pop()
                refresh_staged()

        self.button_row(panel, [("Add Item", add_item, "Primary.TButton"), ("Split Answer", split_answer, "TButton"), ("Split Paste", split_bulk, "TButton"), ("Remove Last", remove_last, "TButton")])

        controls = ttk.Frame(panel, style="Card.TFrame")
        controls.pack(fill="x", pady=(0, 12))
        ttk.Label(controls, text="Start #", style="CardMuted.TLabel").grid(row=0, column=0, sticky="w")
        start_var = tk.StringVar()
        start_var.set(draft.get("start", ""))
        ttk.Entry(controls, textvariable=start_var).grid(row=1, column=0, sticky="ew", padx=(0, 8))
        ttk.Label(controls, text="Loop range (optional)", style="CardMuted.TLabel").grid(row=0, column=1, sticky="w")
        range_var = tk.StringVar()
        range_var.set(draft.get("range", ""))
        ttk.Entry(controls, textvariable=range_var).grid(row=1, column=1, sticky="ew", padx=(0, 8))
        example = ttk.Label(controls, text="Example: range 3 at item 5 gives 5, 5-4, 5-4-3, then 3-2-1.", style="CardMuted.TLabel", wraplength=620)
        example.grid(row=1, column=2, sticky="ew")
        self.bind_rewrap(example)
        controls.columnconfigure(0, weight=1)
        controls.columnconfigure(1, weight=1)
        controls.columnconfigure(2, weight=3)

        results_header = self.card(page.inner, "AltCard.TFrame", 16)
        results_header.pack(fill="x", pady=(14, 8))
        ttk.Label(results_header, text="Round player", style="AltH2.TLabel").pack(anchor="w")
        ttk.Label(results_header, text="Build the path, then move through one round at a time instead of working through a long stack.", style="AltMuted.TLabel", wraplength=980).pack(anchor="w", pady=(4, 0))
        results = ttk.Frame(page.inner, style="Page.TFrame")
        results.pack(fill="x")

        def load(source):
            staged_items.clear()
            staged_items.extend(self.practice_items_from_saved(source))
            refresh_staged()
            self.toast_message("Loaded saved material.")

        @self.smooth
        def build():
            for child in results.winfo_children():
                child.destroy()
            items = list(staged_items)
            if normalize_space(answer_box.get("1.0", "end")):
                items.append({"prompt": normalize_space(prompt_var.get()) or f"Study item {len(items) + 1}", "answer": normalize_space(answer_box.get("1.0", "end"))})
            items.extend(self.practice_items_from_text(bulk_text.get("1.0", "end")))
            if not items:
                ttk.Label(results, text="Add repetition items or load saved cards/captures first.", style="Muted.TLabel").pack(anchor="w")
                return
            try:
                start = int(start_var.get()) if start_var.get().strip() else len(items)
                span = int(range_var.get()) if range_var.get().strip() else None
            except ValueError:
                self.toast_message("Start and range must be numbers.")
                return
            answers = [item["answer"] for item in items]
            steps = self.repetition_steps(answers, start, span)
            if not steps:
                ttk.Label(results, text="No repetition rounds could be built from these settings.", style="Muted.TLabel").pack(anchor="w")
                return
            round_state = {"index": 0, "items": items, "steps": steps}

            @self.smooth
            def render_round():
                for child in results.winfo_children():
                    child.destroy()
                round_index = round_state["index"]
                label, indexes = round_state["steps"][round_index]
                item_card = self.card(results)
                item_card.pack(fill="x", padx=(0, 8), pady=(0, 8))
                ttk.Label(item_card, text=f"Round {round_index + 1} of {len(round_state['steps'])}", style="CardMuted.TLabel").pack(anchor="w")
                ttk.Label(item_card, text=f"Repeat {label}", style="H2.TLabel").pack(anchor="w", pady=(4, 0))
                progress = ttk.Progressbar(item_card, maximum=len(round_state["steps"]), value=round_index + 1)
                progress.pack(fill="x", pady=(10, 14))
                prompt_panel = self.card(item_card, "AltCard.TFrame", 14)
                prompt_panel.pack(fill="x")
                ttk.Label(prompt_panel, text="Prompts to recall", style="AltH2.TLabel").pack(anchor="w")
                for index in indexes:
                    ttk.Label(prompt_panel, text=f"{index + 1}. {round_state['items'][index]['prompt']}", style="AltCard.TLabel", wraplength=1080).pack(anchor="w", pady=(4, 0))
                response = self.answer_area(item_card, "Your recall", "Write the answer sequence for this round.", 3)
                result = ttk.Label(item_card, text="Type your recall, then check or reveal.", style="CardMuted.TLabel", wraplength=1040)
                result.pack(anchor="w")
                bucket_slot = ttk.Frame(item_card, style="Card.TFrame")
                bucket_slot.pack(fill="x")
                answer_frame = ttk.Frame(item_card, style="Card.TFrame")
                visible = {"value": False}

                @self.smooth
                def reveal(frame=answer_frame, ids=indexes, flag=visible):
                    if flag["value"]:
                        frame.pack_forget()
                        flag["value"] = False
                        return
                    for child in frame.winfo_children():
                        child.destroy()
                    ttk.Label(frame, text="Answer", style="CardMuted.TLabel").pack(anchor="w")
                    for answer_index in ids:
                        ttk.Label(frame, text=f"{answer_index + 1}. {round_state['items'][answer_index]['answer']}", style="Card.TLabel", wraplength=1080).pack(anchor="w", pady=(3, 0))
                    frame.pack(fill="x", pady=(8, 0))
                    flag["value"] = True

                @self.smooth
                def check(box=response, target=result, ids=indexes):
                    for child in bucket_slot.winfo_children():
                        child.destroy()
                    expected = "\n".join(round_state["items"][index]["answer"] for index in ids)
                    checked = answer_assessment(box.get("1.0", "end").strip(), expected)
                    target.configure(text=f"{checked['label']} | {checked['score']}% | Bucket: {checked['bucket']} | Reps: {checked['repetitions']} | {checked['detail']}")
                    self.render_bucket_highlight(bucket_slot, checked["bucket"])

                def move(delta):
                    round_state["index"] = min(max(round_state["index"] + delta, 0), len(round_state["steps"]) - 1)
                    render_round()

                actions = ttk.Frame(item_card, style="Card.TFrame")
                actions.pack(fill="x", pady=(self.px(10), 0))
                controls = [
                    ("Smart Check", "Primary.TButton", check, "normal"),
                    ("Reveal answer", "TButton", reveal, "normal"),
                    ("Previous", "TButton", lambda: move(-1), "disabled" if round_index == 0 else "normal"),
                    ("Next Round", "TButton", lambda: move(1), "disabled" if round_index == len(round_state["steps"]) - 1 else "normal"),
                ]
                for column, (label_text, style, command, state) in enumerate(controls):
                    button = ttk.Button(actions, text=label_text, style=style, command=command, state=state)
                    button.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else self.px(8), 0))
                    self.add_tooltip(button, self.action_hint(label_text))
                    actions.columnconfigure(column, weight=1)

            render_round()

        self.button_row(panel, [("Build Path", build, "Primary.TButton"), ("Use Captures", lambda: load("captures"), "TButton"), ("Use Cards", lambda: load("cards"), "TButton"), ("Use All", lambda: load("all"), "TButton")])
        refresh_staged()
        self.register_draft_saver("shuffle", lambda: {
            "prompt": prompt_var.get(),
            "answer": answer_box.get("1.0", "end").strip(),
            "bulk": bulk_text.get("1.0", "end").strip(),
            "staged_items": [dict(item) for item in staged_items],
            "start": start_var.get(),
            "range": range_var.get(),
        })

    def material_bits(self):
        bits = []
        for capture in self.store.captures:
            bits.extend(capture.chunks or split_study_bits(capture.notes))
        for card in self.store.cards:
            bits.extend([card.front, card.back])
        return [bit for bit in bits if bit]

    def view_tools(self):
        draft = self.view_drafts.get("tools", {})
        page = ScrollFrame(self.view_host)
        page.pack(fill="both", expand=True)
        panel = self.card(page.inner)
        panel.pack(fill="x", padx=(0, 8), pady=(0, 12))
        ttk.Label(panel, text="Association builder", style="H2.TLabel").pack(anchor="w")
        ttk.Label(panel, text="Add ideas separated by commas, new lines, or slashes. Then choose a memory hook style.", style="CardMuted.TLabel", wraplength=1040).pack(anchor="w", pady=(6, 12))
        self.render_resource_strip(page.inner, "Reference cues")
        ideas = self.text_box(panel, 4, 12)
        ideas.insert("1.0", draft.get("ideas", "mitosis, meiosis, chromosomes"))
        ideas.pack(fill="x", pady=(0, 12))
        output = self.card(page.inner, "AltCard.TFrame")
        output.pack(fill="both", expand=True, padx=(0, 8), pady=(0, 12))
        out = ttk.Label(output, text=draft.get("output", "Your memory hook will appear here."), style="AltCard.TLabel", wraplength=1080)
        out.pack(anchor="w")

        def technique(generate):
            def run():
                out.configure(text=generate(techniques.parse_ideas(ideas.get("1.0", "end"))))
            return run

        acronym = technique(techniques.acronym)
        story = technique(techniques.story)
        peg_list = technique(techniques.peg_list)
        palace = technique(techniques.palace)
        chunk_map = technique(techniques.chunk_map)
        link_chain = technique(techniques.link_chain)

        def saved():
            ideas.delete("1.0", "end")
            ideas.insert("1.0", ", ".join(self.material_bits()[:10]))

        self.button_row(panel, [("Acronym", acronym, "Primary.TButton"), ("Mini Story", story, "TButton"), ("Peg List", peg_list, "TButton")])
        self.button_row(panel, [("Memory Palace", palace, "TButton"), ("Chunk Map", chunk_map, "TButton"), ("Link Chain", link_chain, "TButton"), ("Saved Material", saved, "TButton")])

        strategy_panel = self.card(page.inner, "Card.TFrame", 22)
        strategy_panel.pack(fill="x", padx=(0, 8), pady=(0, 12))
        ttk.Label(strategy_panel, text="Technique planner", style="H2.TLabel").pack(anchor="w")
        ttk.Label(strategy_panel, text="Turn notes into one practical exercise for study, recall, or everyday memory support.", style="CardMuted.TLabel", wraplength=self.px(1040)).pack(anchor="w", pady=(4, 12))
        strategy_mode = tk.StringVar(value=draft.get("strategy_mode", "Retrieval practice"))
        self.select_button(
            strategy_panel,
            strategy_mode,
            ["Retrieval practice", "Spaced practice", "Interleaving", "Elaboration", "Concrete examples", "Dual coding", "Spaced retrieval"],
        ).pack(fill="x", pady=(0, self.px(10)))
        strategy_text = self.text_box(strategy_panel, 4, 12)
        strategy_text.insert("1.0", draft.get("strategy_text", ""))
        strategy_text.pack(fill="x", pady=(0, self.px(10)))
        strategy_out = ttk.Label(strategy_panel, text=draft.get("strategy_output", "Choose a technique and build a plan."), style="Card.TLabel", wraplength=self.px(1040))
        strategy_out.pack(anchor="w", pady=(0, self.px(12)))

        def strategy_bits():
            raw = strategy_text.get("1.0", "end").strip()
            bits = split_study_bits(raw) if raw else self.material_bits()[:8]
            return bits[:8]

        def build_strategy_plan():
            bits = strategy_bits()
            if not bits:
                strategy_out.configure(text="Add notes here or save material first.")
                return
            mode = strategy_mode.get()
            if mode == "Retrieval practice":
                lines = [f"{index + 1}. Before looking, answer: what do I remember about {bit}?" for index, bit in enumerate(bits)]
            elif mode == "Spaced practice":
                first = bits[0]
                lines = [
                    f"Now: explain {first} from memory.",
                    "Later today: review only the parts that felt weak.",
                    "Tomorrow: answer the same prompt without notes.",
                    "In three days: mix it with a different topic in Quiz or Test Lab.",
                ]
            elif mode == "Interleaving":
                mixed = bits[::2] + bits[1::2]
                lines = [f"{index + 1}. Practice: {bit}" for index, bit in enumerate(mixed)]
            elif mode == "Elaboration":
                lines = [f"{index + 1}. Why does {bit} matter, and what does it connect to?" for index, bit in enumerate(bits)]
            elif mode == "Concrete examples":
                lines = [f"{index + 1}. Find one real example of: {bit}" for index, bit in enumerate(bits)]
            elif mode == "Dual coding":
                lines = [f"{index + 1}. Pair {bit} with a quick sketch, image cue, or short audio reminder." for index, bit in enumerate(bits)]
            else:
                lines = [
                    "Start with one small answer.",
                    "Repeat it after 30 seconds, 1 minute, 2 minutes, and 4 minutes.",
                    "If it is missed, return to the shortest interval.",
                    "Best for names, routines, safety steps, and important everyday facts.",
                ]
            strategy_out.configure(text=f"{mode} plan:\n\n" + "\n".join(lines))

        self.button_row(strategy_panel, [("Build Technique Plan", build_strategy_plan, "Primary.TButton"), ("Saved Material", lambda: (strategy_text.delete("1.0", "end"), strategy_text.insert("1.0", "\n".join(self.material_bits()[:8]))), "TButton")])
        self.register_draft_saver("tools", lambda: {
            "ideas": ideas.get("1.0", "end").strip(),
            "output": out.cget("text"),
            "strategy_mode": strategy_mode.get(),
            "strategy_text": strategy_text.get("1.0", "end").strip(),
            "strategy_output": strategy_out.cget("text"),
        })

    def view_games(self):
        draft = self.view_drafts.get("games", {})
        page = ScrollFrame(self.view_host)
        page.pack(fill="both", expand=True)
        intro = self.card(page.inner, "WarmCard.TFrame", 16)
        intro.pack(fill="x", padx=(0, 8), pady=(0, 12))
        ttk.Label(intro, text="Short recall puzzles", style="WarmH2.TLabel").pack(anchor="w")
        ttk.Label(intro, text="Use these as quick warmups between study modes. They pull from saved material when possible and fall back to sample prompts.", style="WarmCard.TLabel", wraplength=1040).pack(anchor="w", pady=(4, 0))
        self.render_resource_strip(page.inner, "Recent notes and audio")

        grid = ttk.Frame(page.inner, style="Page.TFrame")
        grid.pack(fill="both", expand=True, padx=(0, 8))
        for column in range(2):
            grid.columnconfigure(column, weight=1, uniform="puzzles")

        sequence_card = self.card(grid)
        sequence_card.grid(row=0, column=0, sticky="nsew", padx=(0, 12), pady=(0, 12))
        ttk.Label(sequence_card, text="Sequence Recall", style="H2.TLabel").pack(anchor="w")
        ttk.Label(sequence_card, text="Watch the digits, then type them back.", style="CardMuted.TLabel").pack(anchor="w", pady=(4, 12))
        sequence_box = ttk.Label(sequence_card, text="Press Start", style="Stat.TLabel", wraplength=500)
        if draft.get("sequence"):
            self.sequence = draft.get("sequence", "")
            sequence_box.configure(text=draft.get("sequence_prompt", "Now type it"))
        sequence_box.pack(anchor="w", pady=(0, 12))
        answer = ttk.Entry(sequence_card)
        answer.insert(0, draft.get("sequence_answer", ""))
        answer.pack(fill="x", pady=(0, 12))

        def start_sequence():
            self.sequence = "".join(str(random.randint(1, 9)) for _ in range(random.randint(4, 8)))
            sequence_box.configure(text=" ".join(self.sequence))
            answer.delete(0, "end")
            self.after(self.pace(3000), lambda: sequence_box.configure(text="Now type it") if sequence_box.winfo_exists() else None)

        def check_sequence():
            typed = re.sub(r"\D", "", answer.get())
            self.toast_message("Correct." if typed == self.sequence else f"Sequence: {self.sequence}")

        self.button_row(sequence_card, [("Start", start_sequence, "Primary.TButton"), ("Check", check_sequence, "TButton")])

        word_card = self.card(grid)
        word_card.grid(row=0, column=1, sticky="nsew", pady=(0, 12))
        ttk.Label(word_card, text="Word Recall", style="H2.TLabel").pack(anchor="w")
        ttk.Label(word_card, text="A short word list appears, then disappears.", style="CardMuted.TLabel").pack(anchor="w", pady=(4, 12))
        word_box = ttk.Label(word_card, text="Press Show Words", style="Card.TLabel", wraplength=500)
        current_words = list(draft.get("current_words", []))
        if current_words:
            word_box.configure(text=draft.get("word_prompt", "Say them back"))
        word_box.pack(anchor="w", pady=(0, 12))
        word_answer = ttk.Entry(word_card)
        word_answer.insert(0, draft.get("word_answer", ""))
        word_answer.pack(fill="x", pady=(0, 12))

        def word_pool():
            pool = [word.lower() for bit in self.material_bits() for word in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", bit)]
            clean = list(dict.fromkeys(pool))
            return clean if len(clean) >= 5 else ["river", "lamp", "garden", "silver", "window", "music", "orange"]

        def show_words():
            nonlocal current_words
            pool = word_pool()
            current_words = random.sample(pool, min(6, len(pool)))
            word_box.configure(text=", ".join(current_words))
            word_answer.delete(0, "end")
            self.after(self.pace(3800), lambda: word_box.configure(text="Say them back") if word_box.winfo_exists() else None)

        def check_words():
            result = answer_assessment(word_answer.get(), " ".join(current_words))
            self.toast_message(f"{result['label']} | {result['score']}%")

        self.button_row(word_card, [("Show Words", show_words, "Primary.TButton"), ("Smart Check", check_words, "TButton")])

        pair_card = self.card(grid)
        pair_card.grid(row=1, column=0, sticky="nsew", padx=(0, 12), pady=(0, 12))
        ttk.Label(pair_card, text="Pair Recall", style="H2.TLabel").pack(anchor="w")
        ttk.Label(pair_card, text="Practice one prompt-answer pair at a time.", style="CardMuted.TLabel").pack(anchor="w", pady=(4, 12))
        pair_prompt = ttk.Label(pair_card, text="Make a pair set", style="H2.TLabel", wraplength=500)
        pair_prompt.pack(anchor="w", pady=(0, 12))
        pair_answer = ttk.Entry(pair_card)
        pair_answer.insert(0, draft.get("pair_answer", ""))
        pair_answer.pack(fill="x", pady=(0, 12))
        pair_status = ttk.Label(pair_card, text="Smart Check will score the current pair.", style="CardMuted.TLabel", wraplength=500)
        pair_status.pack(anchor="w", pady=(0, 12))
        pair_state = {"pairs": [dict(item) for item in draft.get("pairs", [])], "index": int(draft.get("pair_index", 0))}
        if pair_state["pairs"]:
            pair_state["index"] = min(pair_state["index"], len(pair_state["pairs"]) - 1)
            pair_prompt.configure(text=draft.get("pair_prompt", pair_state["pairs"][pair_state["index"]]["prompt"]))
            pair_status.configure(text=draft.get("pair_status", f"Pair {pair_state['index'] + 1} of {len(pair_state['pairs'])}"))

        def new_pair_set():
            pairs = [{"prompt": card.front, "answer": card.back} for card in self.store.cards if card.front and card.back]
            if not pairs:
                pairs = [
                    {"prompt": "Where do spaced reviews go?", "answer": "Test Lab"},
                    {"prompt": "What does Smart Check suggest?", "answer": "A review bucket"},
                    {"prompt": "What does chunking create?", "answer": "Small study bits"},
                ]
            pair_state["pairs"] = random.sample(pairs, min(5, len(pairs)))
            pair_state["index"] = 0
            pair_answer.delete(0, "end")
            pair_prompt.configure(text=pair_state["pairs"][0]["prompt"])
            pair_status.configure(text=f"Pair 1 of {len(pair_state['pairs'])}")

        def reveal_pair():
            if not pair_state["pairs"]:
                new_pair_set()
            current = pair_state["pairs"][pair_state["index"]]
            pair_status.configure(text=f"Answer: {current['answer']}")

        def check_pair():
            if not pair_state["pairs"]:
                new_pair_set()
            current = pair_state["pairs"][pair_state["index"]]
            result = answer_assessment(pair_answer.get(), current["answer"], current["prompt"])
            pair_status.configure(text=f"{result['label']} | {result['score']}% | {result['detail']}")
            pair_state["index"] = (pair_state["index"] + 1) % len(pair_state["pairs"])
            pair_answer.delete(0, "end")
            self.after(self.pace(1200), lambda: pair_prompt.configure(text=pair_state["pairs"][pair_state["index"]]["prompt"]) if pair_prompt.winfo_exists() and pair_state["pairs"] else None)

        self.button_row(pair_card, [("New Pair Set", new_pair_set, "Primary.TButton"), ("Reveal Cue", reveal_pair, "TButton"), ("Smart Check", check_pair, "TButton")])

        gap_card = self.card(grid)
        gap_card.grid(row=1, column=1, sticky="nsew", pady=(0, 12))
        ttk.Label(gap_card, text="Missing Item", style="H2.TLabel").pack(anchor="w")
        ttk.Label(gap_card, text="Find the hidden item from a short sequence.", style="CardMuted.TLabel").pack(anchor="w", pady=(4, 12))
        gap_prompt = ttk.Label(gap_card, text="Press Make Gap", style="Card.TLabel", wraplength=500)
        if draft.get("gap_prompt"):
            gap_prompt.configure(text=draft["gap_prompt"])
        gap_prompt.pack(anchor="w", pady=(0, 12))
        gap_answer = ttk.Entry(gap_card)
        gap_answer.insert(0, draft.get("gap_answer", ""))
        gap_answer.pack(fill="x", pady=(0, 12))
        gap_state = {"answer": draft.get("gap_answer_key", "")}

        def make_gap():
            pool = word_pool()
            words = random.sample(pool, min(5, len(pool)))
            hidden = random.randrange(len(words))
            gap_state["answer"] = words[hidden]
            shown = list(words)
            shown[hidden] = "_____"
            gap_prompt.configure(text="  -  ".join(shown))
            gap_answer.delete(0, "end")

        def check_gap():
            result = answer_assessment(gap_answer.get(), gap_state["answer"])
            self.toast_message(f"{result['label']} | Missing: {gap_state['answer']}")

        self.button_row(gap_card, [("Make Gap", make_gap, "Primary.TButton"), ("Check", check_gap, "TButton")])

        visual_card = self.card(grid)
        visual_card.grid(row=2, column=0, sticky="nsew", padx=(0, self.px(12)), pady=(0, self.px(12)))
        ttk.Label(visual_card, text="Visual Search", style="H2.TLabel").pack(anchor="w")
        ttk.Label(visual_card, text="Find every matching target. This is a quick attention and scanning warmup.", style="CardMuted.TLabel", wraplength=self.px(500)).pack(anchor="w", pady=(4, 12))
        visual_status = ttk.Label(visual_card, text=draft.get("visual_status", "Start a round to make the search grid."), style="CardMuted.TLabel", wraplength=self.px(500))
        visual_status.pack(anchor="w", pady=(0, self.px(10)))
        visual_holder = tk.Frame(visual_card, bg=COLORS["surface"])
        visual_holder.pack(fill="x", pady=(0, self.px(12)))
        visual_state = {
            "target": draft.get("visual_target", ""),
            "tiles": list(draft.get("visual_tiles", [])),
            "found": set(draft.get("visual_found", [])),
        }

        @self.smooth
        def render_visual_grid():
            for child in visual_holder.winfo_children():
                child.destroy()
            if not visual_state["tiles"]:
                return
            for index, word in enumerate(visual_state["tiles"]):
                found = index in visual_state["found"]
                color = COLORS["good_bg"] if found else COLORS["input"]
                fg = COLORS["good_fg"] if found else COLORS["ink"]
                tile = tk.Button(
                    visual_holder,
                    text=word,
                    relief="flat",
                    bd=0,
                    cursor="hand2",
                    bg=color,
                    fg=fg,
                    activebackground=COLORS["alt"],
                    activeforeground=COLORS["primary"],
                    font=self.font("Segoe UI Semibold", 10),
                    padx=self.px(10),
                    pady=self.px(8),
                    command=lambda i=index: choose_visual_tile(i),
                )
                row, column = divmod(index, 4)
                tile.grid(row=row, column=column, sticky="ew", padx=(0 if column == 0 else self.px(6), 0), pady=(0 if row == 0 else self.px(6), 0))
                visual_holder.columnconfigure(column, weight=1)

        def choose_visual_tile(index):
            target = visual_state["target"]
            if not target:
                return
            if visual_state["tiles"][index] == target:
                visual_state["found"].add(index)
                total = len([item for item in visual_state["tiles"] if item == target])
                visual_status.configure(text=f"Target: {target} | Found {len(visual_state['found'])} of {total}")
                render_visual_grid()
                if len(visual_state["found"]) == total:
                    self.toast_message("Visual search complete.")
            else:
                self.toast_message("Different tile. Keep scanning.")

        def start_visual_search():
            pool = word_pool()
            target = random.choice(pool)
            distractors = [word for word in pool if word != target]
            if len(distractors) < 10:
                distractors.extend(["focus", "garden", "music", "window", "silver", "table"])
            target_count = random.randint(3, 5)
            tiles = [target] * target_count + random.sample(distractors, min(16 - target_count, len(distractors)))
            random.shuffle(tiles)
            visual_state["target"] = target
            visual_state["tiles"] = tiles
            visual_state["found"] = set()
            visual_status.configure(text=f"Target: {target} | Found 0 of {target_count}")
            render_visual_grid()

        if visual_state["tiles"]:
            render_visual_grid()
        self.button_row(visual_card, [("Visual Search", start_visual_search, "Primary.TButton")])

        nback_card = self.card(grid)
        nback_card.grid(row=2, column=1, sticky="nsew", pady=(0, self.px(12)))
        ttk.Label(nback_card, text="N-Back Lite", style="H2.TLabel").pack(anchor="w")
        ttk.Label(nback_card, text="Decide whether the current item matches the one just before it.", style="CardMuted.TLabel", wraplength=self.px(500)).pack(anchor="w", pady=(4, 12))
        nback_word = ttk.Label(nback_card, text=draft.get("nback_word", "Start a round"), style="Stat.TLabel", wraplength=self.px(500))
        nback_word.pack(anchor="w", pady=(0, self.px(8)))
        nback_status = ttk.Label(nback_card, text=draft.get("nback_status", "Score appears here."), style="CardMuted.TLabel", wraplength=self.px(500))
        nback_status.pack(anchor="w", pady=(0, self.px(12)))
        nback_state = {
            "items": list(draft.get("nback_items", [])),
            "index": int(draft.get("nback_index", 0)),
            "score": int(draft.get("nback_score", 0)),
            "total": int(draft.get("nback_total", 0)),
        }

        def show_nback_word():
            if not nback_state["items"]:
                nback_word.configure(text="Start a round")
                return
            index = min(nback_state["index"], len(nback_state["items"]) - 1)
            nback_word.configure(text=nback_state["items"][index])
            nback_status.configure(text=f"Item {index + 1} of {len(nback_state['items'])} | Score {nback_state['score']} / {nback_state['total']}")

        def start_nback():
            pool = word_pool()
            items = []
            for index in range(10):
                if index > 0 and random.random() < 0.35:
                    items.append(items[index - 1])
                else:
                    items.append(random.choice(pool))
            nback_state.update({"items": items, "index": 0, "score": 0, "total": 0})
            show_nback_word()

        def answer_nback(same):
            if not nback_state["items"]:
                start_nback()
                return
            index = nback_state["index"]
            if index == 0:
                nback_state["index"] = 1
                show_nback_word()
                return
            actual_same = nback_state["items"][index] == nback_state["items"][index - 1]
            nback_state["total"] += 1
            if same == actual_same:
                nback_state["score"] += 1
                self.toast_message("Correct.")
            else:
                self.toast_message("Not this time.")
            if index >= len(nback_state["items"]) - 1:
                nback_status.configure(text=f"Round complete | Score {nback_state['score']} / {nback_state['total']}")
                return
            nback_state["index"] += 1
            show_nback_word()

        if nback_state["items"]:
            show_nback_word()
        self.button_row(
            nback_card,
            [
                ("New Round", start_nback, "Primary.TButton"),
                ("Same as Last", lambda: answer_nback(True), "TButton"),
                ("Different", lambda: answer_nback(False), "TButton"),
            ],
        )

        sort_card = self.card(grid)
        sort_card.grid(row=3, column=0, sticky="nsew", padx=(0, self.px(12)), pady=(0, self.px(12)))
        ttk.Label(sort_card, text="Category Sort", style="H2.TLabel").pack(anchor="w")
        ttk.Label(sort_card, text="Group words or study bits before checking the suggested categories.", style="CardMuted.TLabel", wraplength=self.px(500)).pack(anchor="w", pady=(4, 12))
        sort_input = self.text_box(sort_card, 4, 11)
        sort_input.insert("1.0", draft.get("sort_input", "doctor appointment\nfamily photos\nbiology definition\npick up medicine\nbus stop"))
        sort_input.pack(fill="x", pady=(0, self.px(10)))
        sort_output = ttk.Label(sort_card, text=draft.get("sort_output", "Build a sorting round, then group the items in your head or on paper."), style="Card.TLabel", wraplength=self.px(500))
        sort_output.pack(anchor="w", pady=(0, self.px(12)))

        def category_for(item):
            text = item.lower()
            groups = [
                ("People", ("name", "family", "friend", "teacher", "doctor", "grand", "mother", "father")),
                ("Places", ("home", "room", "school", "class", "store", "bus", "park", "door", "kitchen")),
                ("Tasks", ("take", "pick", "call", "pay", "bring", "send", "read", "write", "finish")),
                ("Study", ("definition", "formula", "chapter", "exam", "biology", "history", "math", "science")),
                ("Time", ("today", "tomorrow", "morning", "night", "date", "appointment", "minute", "hour")),
            ]
            for name, words in groups:
                if any(word in text for word in words):
                    return name
            return "Other"

        def build_sort():
            raw_items = split_study_bits(sort_input.get("1.0", "end"))
            if not raw_items:
                raw_items = self.material_bits()[:10]
            if not raw_items:
                raw_items = ["family photo", "doctor appointment", "new word", "front door", "take medicine"]
            items = raw_items[:12]
            shuffled = list(items)
            random.shuffle(shuffled)
            buckets = {}
            for item in items:
                buckets.setdefault(category_for(item), []).append(item)
            lines = ["Sort these:", ", ".join(shuffled), "", "Suggested groups:"]
            lines.extend(f"{name}: {', '.join(values)}" for name, values in buckets.items())
            sort_output.configure(text="\n".join(lines))

        def sample_sort():
            sort_input.delete("1.0", "end")
            sort_input.insert("1.0", "family photo\nfront door key\nmorning medicine\nmath formula\ndoctor appointment\nchapter summary")

        self.button_row(sort_card, [("Build Sort", build_sort, "Primary.TButton"), ("Use Sample", sample_sort, "TButton")])

        routine_card = self.card(grid)
        routine_card.grid(row=3, column=1, sticky="nsew", pady=(0, self.px(12)))
        ttk.Label(routine_card, text="Routine Recall", style="H2.TLabel").pack(anchor="w")
        ttk.Label(routine_card, text="Briefly show a short routine, then type the steps back in order.", style="CardMuted.TLabel", wraplength=self.px(500)).pack(anchor="w", pady=(4, 12))
        routine_prompt = ttk.Label(routine_card, text=draft.get("routine_prompt", "Press Show Routine"), style="Card.TLabel", wraplength=self.px(500))
        routine_prompt.pack(anchor="w", pady=(0, self.px(10)))
        routine_answer = self.text_box(routine_card, 4, 11)
        routine_answer.insert("1.0", draft.get("routine_answer", ""))
        routine_answer.pack(fill="x", pady=(0, self.px(10)))
        routine_status = ttk.Label(routine_card, text=draft.get("routine_status", "A gentle score will appear here."), style="CardMuted.TLabel", wraplength=self.px(500))
        routine_status.pack(anchor="w", pady=(0, self.px(12)))
        routine_state = {"steps": list(draft.get("routine_steps", []))}

        def routine_pool():
            bits = [bit for bit in self.material_bits() if len(bit.split()) <= 12]
            if len(bits) >= 3:
                return bits[:8]
            return [
                "Check today's date",
                "Take the morning medicine",
                "Put keys by the front door",
                "Call a family member",
                "Drink a glass of water",
            ]

        def show_routine():
            steps = routine_pool()
            routine_state["steps"] = random.sample(steps, min(4, len(steps)))
            routine_answer.delete("1.0", "end")
            routine_status.configure(text="Read the routine, then recall it after it hides.")
            routine_prompt.configure(text="\n".join(f"{index + 1}. {step}" for index, step in enumerate(routine_state["steps"])))
            self.after(self.pace(4200), lambda: routine_prompt.configure(text="Now type the steps in order.") if routine_prompt.winfo_exists() else None)

        def check_routine():
            expected = "\n".join(routine_state["steps"])
            if not expected:
                show_routine()
                return
            result = answer_assessment(routine_answer.get("1.0", "end"), expected)
            routine_status.configure(text=f"{result['label']} | {result['score']}% | {result['detail']}")

        self.button_row(routine_card, [("Show Routine", show_routine, "Primary.TButton"), ("Check Routine", check_routine, "TButton")])
        self.register_draft_saver("games", lambda: {
            "sequence": self.sequence,
            "sequence_prompt": sequence_box.cget("text"),
            "sequence_answer": answer.get(),
            "current_words": list(current_words),
            "word_prompt": word_box.cget("text"),
            "word_answer": word_answer.get(),
            "pairs": [dict(item) for item in pair_state["pairs"]],
            "pair_index": pair_state["index"],
            "pair_prompt": pair_prompt.cget("text"),
            "pair_status": pair_status.cget("text"),
            "pair_answer": pair_answer.get(),
            "gap_prompt": gap_prompt.cget("text"),
            "gap_answer": gap_answer.get(),
            "gap_answer_key": gap_state["answer"],
            "visual_status": visual_status.cget("text"),
            "visual_target": visual_state["target"],
            "visual_tiles": list(visual_state["tiles"]),
            "visual_found": sorted(visual_state["found"]),
            "nback_word": nback_word.cget("text"),
            "nback_status": nback_status.cget("text"),
            "nback_items": list(nback_state["items"]),
            "nback_index": nback_state["index"],
            "nback_score": nback_state["score"],
            "nback_total": nback_state["total"],
            "sort_input": sort_input.get("1.0", "end").strip(),
            "sort_output": sort_output.cget("text"),
            "routine_prompt": routine_prompt.cget("text"),
            "routine_answer": routine_answer.get("1.0", "end").strip(),
            "routine_status": routine_status.cget("text"),
            "routine_steps": list(routine_state["steps"]),
        })

    def open_path(self, path):
        target = Path(path)
        if not target.exists():
            folder = target.parent if target.suffix else target
            folder.mkdir(parents=True, exist_ok=True)
        try:
            system_open(target)
        except OSError:
            import webbrowser

            webbrowser.open(target.resolve().as_uri())

    def open_data_folder(self):
        self.open_path(app_paths.DATA_DIR)

    def export_feedback(self):
        if not self.store.feedback:
            self.toast_message("No feedback to export yet.")
            return
        import csv
        from tkinter import filedialog

        path = filedialog.asksaveasfilename(
            title="Export MemoryPal feedback",
            defaultextension=".csv",
            initialfile="memorypal-feedback.csv",
            filetypes=[("CSV files", "*.csv")],
        )
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["created_at", "rating", "category", "page", "note"])
            writer.writeheader()
            for entry in self.store.feedback:
                writer.writerow({
                    "created_at": entry.created_at,
                    "rating": entry.rating,
                    "category": entry.category,
                    "page": entry.page,
                    "note": entry.note,
                })
        self.toast_message("Feedback exported.")

    def feedback_report_text(self, entries):
        details = feedback_report.system_details(self.accessibility, self.theme)
        return feedback_report.compose_report(entries, details)

    def send_feedback_now(self, collect, reply_to, button):
        """Send the waiting notes straight from the app, without freezing it."""
        reply_to = (reply_to or "").strip()
        if reply_to and not feedback_report.looks_like_email(reply_to):
            self.dialog_alert("Check your email address", "That doesn't look like an email address. Fix it, or leave the box empty to send without one.", "error")
            return
        self.feedback_reply_to = reply_to
        entries = collect()
        if not entries:
            return
        if getattr(self, "_feedback_sending", False):
            return
        self._feedback_sending = True
        subject, body = self.feedback_report_text(entries)
        ids = [entry.id for entry in entries]
        outcome = {}
        idle_label = str(button.cget("text"))
        try:
            button.configure(text="Sending\u2026", state="disabled", cursor="watch")
        except tk.TclError:
            pass

        def work():
            outcome["result"] = feedback_report.send_report(subject, body, reply_to)

        def finish():
            self._feedback_sending = False
            result = outcome["result"]
            if result.ok:
                self.store.mark_feedback_sent(ids)
                self.toast_message(f"Sent! Thank you, the MemoryPal team got your {'notes' if len(ids) != 1 else 'note'}.")
            elif result.status == "offline":
                self.dialog_alert("Couldn't reach the internet", "Your notes are saved. Try again when you're online, or save them as a file to send later.", "error")
            elif result.status == "activation":
                self.dialog_alert("Almost ready", "Sending from the app has to be switched on once by the MemoryPal team. Your notes are saved; try again a little later, or use Email it meanwhile.", "info")
            else:
                self.dialog_alert("Couldn't send the feedback", f"{result.detail} Your notes are saved; try Email or Save instead.".strip(), "error")
            if self.current_view == "feedback":
                self.show_view("feedback")
            else:
                try:
                    button.configure(text=idle_label, state="normal", cursor="hand2")
                except tk.TclError:
                    pass

        def wait(thread):
            if thread.is_alive():
                self.after(100, lambda: wait(thread))
            else:
                finish()

        thread = threading.Thread(target=work, daemon=True)
        thread.start()
        self.after(100, lambda: wait(thread))

    def email_feedback(self, collect, prefer_gmail=False):
        entries = collect()
        if not entries:
            return
        import webbrowser

        subject, body = self.feedback_report_text(entries)
        attachment = None
        if len(body) > feedback_report.MAX_LINK_BODY:
            # Too long for an email link: save the whole report to attach.
            attachment = feedback_report.save_report(feedback_report.default_report_folder() / feedback_report.default_report_name(), subject, body)
        short = feedback_report.link_body(body, attachment.name if attachment else None)
        opened = False
        if not prefer_gmail and feedback_report.has_mail_app():
            try:
                system_open(feedback_report.mailto_url(subject, short))
                opened = True
            except OSError:
                opened = False
        if not opened:
            opened = webbrowser.open(feedback_report.gmail_url(subject, short))
        if attachment:
            self.reveal_file(attachment)
            self.toast_message(f"Email opened. Attach {attachment.name} (it's open in {FILE_MANAGER}), then press Send.")
        elif opened:
            self.toast_message("Your email is ready. Check it, then press Send.")
        else:
            self.dialog_alert("Couldn't open email", "No email app or browser could be opened. Use Send Feedback Now instead; it doesn't need an email app.", "error")
        self.show_view("feedback")

    def save_feedback_file(self, collect):
        entries = collect()
        if not entries:
            return
        from tkinter import filedialog

        subject, body = self.feedback_report_text(entries)
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Save MemoryPal feedback",
            initialdir=str(feedback_report.default_report_folder()),
            initialfile=feedback_report.default_report_name(),
            defaultextension=".txt",
            filetypes=[("Text file", "*.txt")],
        )
        if not path:
            self.show_view("feedback")
            return
        try:
            saved = feedback_report.save_report(path, subject, body)
        except OSError as exc:
            self.dialog_alert("Couldn't save the file", str(exc), "error")
            return
        if self.dialog_confirm("Feedback saved", f"Saved as {saved.name}. To send it, use Email it and attach the file. Thank you!", "Show the File"):
            self.reveal_file(saved)
        self.show_view("feedback")

    def reveal_file(self, path):
        try:
            system_reveal(path)
        except OSError:
            pass

    def view_feedback(self):
        page = ScrollFrame(self.view_host)
        page.pack(fill="both", expand=True)
        draft = self.view_drafts.get("feedback", {})
        summary = self.store.feedback_summary()

        hero = self.hover_card(tk.Frame(page.inner, bg=COLORS["surface"], padx=self.px(28), pady=self.px(26), highlightthickness=1, highlightbackground=COLORS["line"]))
        hero.pack(fill="x", padx=(0, 8), pady=(0, 16))
        tk.Label(hero, text="Help make MemoryPal better", bg=COLORS["surface"], fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 24)).pack(anchor="w")
        tk.Label(hero, text="Tell us what's working, what's confusing, or what's broken. Notes stay on this computer until you send them.", bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI", 12), wraplength=self.px(1020), justify="left").pack(anchor="w", pady=(6, 0))

        stats = ttk.Frame(page.inner, style="Page.TFrame")
        stats.pack(fill="x", padx=(0, 8), pady=(0, 16))
        stat_items = [
            ("Entries", str(summary["total"]), "notes saved on this computer", COLORS["primary"]),
            ("Average", f"{summary['average']}/5" if summary["average"] else "None", "rated feedback score", COLORS["green"]),
            ("Latest", summary["latest"], "most recent feedback note", COLORS["warm_text"]),
        ]
        for index, (title, value, caption, color) in enumerate(stat_items):
            tile = self.hover_card(tk.Frame(stats, bg=COLORS["surface"], padx=self.px(20), pady=self.px(18), highlightthickness=1, highlightbackground=COLORS["line"]))
            tile.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else self.px(10), 0))
            tk.Label(tile, text=title, bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI", 10)).pack(anchor="w")
            tk.Label(tile, text=value, bg=COLORS["surface"], fg=color, font=self.font("Segoe UI Semibold", 20), wraplength=self.px(290), justify="left").pack(anchor="w", pady=(self.px(2), 0))
            tk.Label(tile, text=caption, bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI", 9), wraplength=self.px(290), justify="left").pack(anchor="w")
            stats.columnconfigure(index, weight=1)

        form = self.card(page.inner, "Card.TFrame", 22)
        form.pack(fill="x", padx=(0, 8), pady=(0, 16))
        ttk.Label(form, text="Add a note", style="H2.TLabel").pack(anchor="w")
        ttk.Label(form, text="Short notes are enough. Capture what felt confusing, broken, helpful, too small, too cluttered, or worth keeping.", style="CardMuted.TLabel", wraplength=self.px(1040)).pack(anchor="w", pady=(4, 12))

        controls = ttk.Frame(form, style="Card.TFrame")
        controls.pack(fill="x", pady=(0, 12))
        rating_var = tk.StringVar(value=draft.get("rating", "5"))
        category_var = tk.StringVar(value=draft.get("category", "Usability"))
        page_var = tk.StringVar(value=draft.get("page", "Overall app"))
        categories = ["Usability", "Bug", "Confusing", "Accessibility", "Feature idea", "Performance", "General"]
        page_options = ["Overall app"] + [label for _key, label, _short in self.default_nav_items()]

        tk.Label(controls, text="Rating", bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI Semibold", 10)).grid(row=0, column=0, sticky="w")
        tk.Label(controls, text="Category", bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI Semibold", 10)).grid(row=0, column=1, sticky="w", padx=(self.px(12), 0))
        tk.Label(controls, text="Page", bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI Semibold", 10)).grid(row=0, column=2, sticky="w", padx=(self.px(12), 0))
        self.pill_group(controls, rating_var, ["1", "2", "3", "4", "5"], max_columns=5).grid(row=1, column=0, sticky="ew", pady=(4, 0))
        self.select_button(controls, category_var, categories).grid(row=1, column=1, sticky="ew", padx=(self.px(12), 0), pady=(4, 0))
        self.select_button(controls, page_var, page_options).grid(row=1, column=2, sticky="ew", padx=(self.px(12), 0), pady=(4, 0))
        controls.columnconfigure(0, weight=2)
        controls.columnconfigure(1, weight=2)
        controls.columnconfigure(2, weight=3)

        note = self.text_box(form, height=5)
        note.pack(fill="x", pady=(0, 12))
        note.insert("1.0", draft.get("note", ""))

        def save_feedback():
            note_text = note.get("1.0", "end").strip()
            rating = int(rating_var.get()) if rating_var.get().isdigit() else 0
            if not note_text:
                self.toast_message("Add a quick note before saving feedback.")
                return
            self.store.add_feedback(rating, category_var.get(), page_var.get(), note_text)
            self.view_drafts["feedback"] = {}
            self.toast_message("Feedback saved.")
            self.show_view("feedback")

        self.button_row(form, [("Save Feedback", save_feedback, "Primary.TButton"), ("Export as Spreadsheet", self.export_feedback, "TButton")])

        def notes_to_send():
            """Saved notes, plus the one being typed (saved first so nothing is lost)."""
            typed = note.get("1.0", "end").strip()
            if typed:
                rating = int(rating_var.get()) if rating_var.get().isdigit() else 0
                self.store.add_feedback(rating, category_var.get(), page_var.get(), typed)
                note.delete("1.0", "end")
                self.view_drafts["feedback"] = {}
            if not self.store.feedback:
                self.toast_message("Write a note first, then send it.")
                return None
            return list(self.store.feedback)

        def unsent_notes():
            """Notes not sent from the app yet (the typed one saved first)."""
            if notes_to_send() is None:
                return None
            waiting = self.store.unsent_feedback()
            if not waiting:
                self.toast_message("All your notes have already been sent. Write a new one to send more.")
                return None
            return waiting

        send = tk.Frame(page.inner, bg=COLORS["surface"], padx=self.px(24), pady=self.px(22))
        send.pack(fill="x", padx=(0, 8), pady=(0, 16))
        tk.Label(send, text="Send feedback to the MemoryPal team", bg=COLORS["surface"], fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 18), anchor="w").pack(fill="x")
        tk.Label(send, text="Your notes stay on this computer until you choose to send them.", bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI", 11), wraplength=self.px(1000), justify="left").pack(anchor="w", pady=(self.px(4), self.px(14)))

        # The main way: straight from the app.
        direct = tk.Frame(send, bg=COLORS["alt"], padx=self.px(18), pady=self.px(16))
        direct.pack(fill="x")
        waiting = len(self.store.unsent_feedback())
        tk.Label(direct, text="\u27a4  Send it now", bg=COLORS["alt"], fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 14), anchor="w").pack(fill="x")
        ready = f"{waiting} note{'s' if waiting != 1 else ''} ready to send." if waiting else "Everything saved so far has been sent."
        tk.Label(direct, text=f"Goes straight to the MemoryPal team from here. No email app or account needed. {ready}", bg=COLORS["alt"], fg=COLORS["muted"], font=self.font("Segoe UI", 10), wraplength=self.px(900), justify="left").pack(anchor="w", pady=(self.px(4), self.px(12)))
        reply_row = tk.Frame(direct, bg=COLORS["alt"])
        reply_row.pack(fill="x", pady=(0, self.px(12)))
        tk.Label(reply_row, text="Your email (optional, so we can reply)", bg=COLORS["alt"], fg=COLORS["muted"], font=self.font("Segoe UI Semibold", 10)).pack(anchor="w")
        reply_var = tk.StringVar(value=draft.get("reply_to", getattr(self, "feedback_reply_to", "")))
        ttk.Entry(reply_row, textvariable=reply_var, font=self.font("Segoe UI", 11)).pack(fill="x", pady=(self.px(4), 0))
        send_button = self.solid_button(direct, "Send Feedback Now", None, COLORS["primary"])
        send_button.configure(command=lambda: self.send_feedback_now(unsent_notes, reply_var.get(), send_button))
        send_button.pack(fill="x")

        tk.Label(send, text="Or do it yourself:", bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI Semibold", 10), anchor="w").pack(fill="x", pady=(self.px(16), self.px(8)))
        options = tk.Frame(send, bg=COLORS["surface"])
        options.pack(fill="x")
        stack = self.accessibility_multiplier() > 1.1
        for index, (icon, title, body, label, action, color) in enumerate((
            ("\u2709", "Email it", "Opens your email app (or Gmail in your browser) with everything filled in. Check it, then press Send.", "Email Feedback", lambda: self.email_feedback(notes_to_send), COLORS["violet"]),
            ("\U0001F4BE", "Save it as a file", "Saves your notes as a text file to keep, or to attach when you use Email it.", "Save Feedback File", lambda: self.save_feedback_file(notes_to_send), COLORS["green"]),
        )):
            option = tk.Frame(options, bg=COLORS["alt"], padx=self.px(18), pady=self.px(16))
            if stack:
                option.grid(row=index, column=0, sticky="nsew", pady=(0 if index == 0 else self.px(12), 0))
            else:
                option.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else self.px(12), 0))
                options.columnconfigure(index, weight=1, uniform="send")
            tk.Label(option, text=f"{icon}  {title}", bg=COLORS["alt"], fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 14), anchor="w").pack(fill="x")
            tk.Label(option, text=body, bg=COLORS["alt"], fg=COLORS["muted"], font=self.font("Segoe UI", 10), wraplength=self.px(440), justify="left").pack(anchor="w", pady=(self.px(4), self.px(12)))
            self.solid_button(option, label, action, color).pack(fill="x")
        if stack:
            options.columnconfigure(0, weight=1)
        # The team's address is never shown on the page: Send goes through the
        # form service and Email fills the address in the person's mail app.
        links = tk.Frame(send, bg=COLORS["surface"])
        links.pack(fill="x", pady=(self.px(14), 0))
        gmail = tk.Label(links, text="Use Gmail in the browser instead", bg=COLORS["surface"], fg=COLORS["primary"], font=self.font("Segoe UI", 10), cursor="hand2")
        gmail.pack(side="right")
        self.keyboard_link(gmail, lambda _event: self.email_feedback(notes_to_send, prefer_gmail=True))
        tk.Label(send, text="Included: your saved notes, plus your system version, text size and theme to help fix problems. Never your study cards or profile name.", bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI", 9), wraplength=self.px(1000), justify="left").pack(anchor="w", pady=(self.px(10), 0))

        recent = self.card(page.inner, "AltCard.TFrame", 22)
        recent.pack(fill="x", padx=(0, 8))
        ttk.Label(recent, text="Recent feedback", style="AltH2.TLabel").pack(anchor="w")
        if not self.store.feedback:
            ttk.Label(recent, text="No notes yet.", style="AltMuted.TLabel").pack(anchor="w", pady=(6, 0))
        for entry in self.store.feedback[:10]:
            item = tk.Frame(recent, bg=COLORS["surface"], padx=self.px(14), pady=self.px(12), highlightthickness=1, highlightbackground=COLORS["soft_line"])
            item.pack(fill="x", pady=(10, 0))
            sent = f" | sent {entry.sent_at}" if entry.sent_at else ""
            tk.Label(item, text=f"{entry.rating}/5 | {entry.category} | {entry.page} | {entry.created_at}{sent}", bg=COLORS["surface"], fg=COLORS["primary"], font=self.font("Segoe UI Semibold", 10)).pack(anchor="w")
            tk.Label(item, text=entry.note, bg=COLORS["surface"], fg=COLORS["ink"], font=self.font("Segoe UI", 11), wraplength=self.px(1020), justify="left").pack(anchor="w", pady=(4, 0))

        self.register_draft_saver("feedback", lambda: {
            "rating": rating_var.get(),
            "category": category_var.get(),
            "page": page_var.get(),
            "note": note.get("1.0", "end").strip(),
            "reply_to": reply_var.get().strip(),
        })

    # ------------------------------------------------------------------
    # Accounts and cloud sync
    # ------------------------------------------------------------------
    SYNC_AFTER_CHANGE_MS = 5_000
    SYNC_EVERY_MS = 5 * 60_000
    REFRESH_AFTER_SYNC = ("dashboard", "library", "decks", "stats", "settings", "elder", "plan", "focus", "review")

    def init_cloud(self):
        """Link the active profile to its account (if any) and keep it in sync."""
        old = getattr(self, "_sync_timer", None)
        if old:
            try:
                self.after_cancel(old)
            except tk.TclError:
                pass
        self._sync_timer = None
        self._syncing = False
        self._applying_sync = False
        self._changed_during_sync = False
        # A sync still running for the previous profile reports back to
        # nobody: its finish is matched against this number.
        self._sync_generation = getattr(self, "_sync_generation", 0) + 1
        if not hasattr(self, "sign_in_limiter"):
            # Slows repeated wrong passwords or codes on this computer; the
            # server's own rate limits are the real protection.
            self.sign_in_limiter = security.AttemptLimiter()
        self.sync_status = ""
        self.account = cloud.Account(self.store.data_file.parent)
        self.account.client.captcha = cloud.browser_check()
        if self.store.recovered_from is not None:
            # Restored from the last good save: merge with the cloud as if new,
            # so cards newer than that save come back instead of being deleted.
            self.account.state.start_over()
        self.store.save_listeners.append(self._changed_since_sync)
        if not getattr(self, "_sync_focus_bound", False):
            self.bind("<FocusIn>", self._sync_on_return, add="+")
            self._sync_focus_bound = True
        if self.auto_sync_ready():
            self.schedule_sync(3000)

    def auto_sync_ready(self):
        """Signed in, with automatic sync on (the default)."""
        return cloud.configured() and self.account.signed_in and self.account.state.auto_sync

    def set_auto_sync(self, value):
        state = self.account.state
        state.auto_sync = bool(value)
        state.save()
        if state.auto_sync and self.account.signed_in:
            self.schedule_sync(0)
        elif self._sync_timer:
            try:
                self.after_cancel(self._sync_timer)
            except tk.TclError:
                pass
            self._sync_timer = None
        self.refresh_account_card()

    def _sync_on_return(self, event):
        """Coming back to the window fetches what other devices did meanwhile."""
        if event.widget is not self or self._syncing or not self.auto_sync_ready():
            return
        now = time.monotonic()
        if now - getattr(self, "_last_return_sync", 0.0) < 60:
            return
        self._last_return_sync = now
        self.schedule_sync(500)

    def _changed_since_sync(self):
        if not self._applying_sync and self.auto_sync_ready():
            if self._syncing:
                self._changed_during_sync = True  # goes up right after this sync
            else:
                self.schedule_sync(self.SYNC_AFTER_CHANGE_MS)

    def schedule_sync(self, delay_ms):
        if self._sync_timer:
            try:
                self.after_cancel(self._sync_timer)
            except tk.TclError:
                pass
        self._sync_timer = self.after(delay_ms, self.sync_now)

    def run_in_background(self, work, done, on_ui_requests=False):
        """Run `work` on a worker thread and call `done(result, error)` back on the UI thread.

        Tk isn't thread-safe, so the worker never touches widgets: when
        `on_ui_requests` is set, it gets a function that runs a callable on
        the UI thread (via a queue this thread polls) and waits for it.
        """
        import queue

        requests = queue.Queue()
        outcome = {}

        def on_ui(fn):
            box, ready = {}, threading.Event()
            requests.put((fn, box, ready))
            ready.wait()
            if "error" in box:
                raise box["error"]
            return box.get("value")

        def run():
            try:
                outcome["value"] = work(on_ui) if on_ui_requests else work()
            except Exception as error:  # reported to the UI thread below
                outcome["error"] = error

        thread = threading.Thread(target=run, daemon=True)

        def poll():
            while not requests.empty():
                fn, box, ready = requests.get()
                try:
                    box["value"] = fn()
                except Exception as error:
                    box["error"] = error
                ready.set()
            if thread.is_alive():
                self.after(40, poll)
            else:
                done(outcome.get("value"), outcome.get("error"))

        thread.start()
        self.after(40, poll)

    def sync_now(self, manual=False, mode=None):
        self._sync_timer = None
        if self._syncing:
            self._changed_during_sync = True
            return
        if not cloud.configured() or not self.account.signed_in:
            return
        self._syncing = True
        self._changed_during_sync = False
        self.sync_status = "Syncing…"
        self.refresh_account_card()
        # The profile can change while the network calls run. Everything
        # below sticks to the profile this sync started with, and its
        # merge step refuses to run once another profile is open, so one
        # profile's cards can never be written into (or deleted from)
        # another's account.
        account, store = self.account, self.store
        generation = self._sync_generation

        def still_current():
            if account is not self.account or store is not self.store:
                raise cloud.CloudError("The profile changed while syncing.", "profile_changed")

        def read_payload():
            still_current()
            self.save_current_draft()
            return store.payload()

        def write_payload(payload):
            still_current()
            self._applying_sync = True
            try:
                store.replace_with(payload)
            finally:
                self._applying_sync = False

        def finished(result, error):
            if generation != self._sync_generation:
                return  # the profile changed while syncing; its own sync is running
            self._syncing = False
            if account is not self.account:
                return
            if isinstance(error, cloud.CloudError) and error.code == "other_account":
                self.sync_status = error.message
                self.refresh_account_card()
                self.choose_account_merge()
                return
            if error is None:
                self.sync_status = ""
                if normalize_accessibility(self.store.accessibility) != self.accessibility:
                    # Text size, motion or contrast changed on another device.
                    self.save_current_draft()
                    self.accessibility = dict(self.store.accessibility)
                    self.apply_accessibility_preferences()
                    self.rebuild_shell(self.current_view, refresh_styles=True)
                elif self.current_view == "welcome" and self.store.onboarding.get("done"):
                    # Signed in on a new device during first launch: the
                    # account already answered the setup questions.
                    self.show_view("dashboard")
                elif result and result.get("applied") and self.current_view in self.REFRESH_AFTER_SYNC:
                    self.show_view(self.current_view)
                else:
                    self.refresh_header_status()
                    self.refresh_account_card()
                if manual:
                    self.toast_message("Everything is in sync.")
            else:
                message = error.message if isinstance(error, cloud.CloudError) else f"Sync stopped: {error}"
                self.sync_status = message
                self.refresh_account_card()
                if manual or not account.signed_in:
                    # Signed out by the server (or two-step turned on elsewhere): say so once.
                    self.dialog_alert("Couldn't sync", message, "error")
            changed = self._changed_during_sync and error is None
            if changed and account.signed_in:
                self.schedule_sync(self.SYNC_AFTER_CHANGE_MS)
            elif self.auto_sync_ready():
                self.schedule_sync(self.SYNC_EVERY_MS)

        if mode == "replace":
            self.keep_copy_before_account_switch()
        self.run_in_background(lambda on_ui: account.sync(read_payload, write_payload, on_ui, mode=mode), finished, on_ui_requests=True)

    def keep_copy_before_account_switch(self):
        """Save this profile's data next to it before it's swapped for an account's."""
        import shutil

        try:
            self.save_current_draft()
            self.store.save()
            target = self.store.data_file.with_name(f"before-account-switch-{time.strftime('%Y%m%d-%H%M%S')}.json")
            shutil.copy2(self.store.data_file, target)
        except OSError:
            pass

    def choose_account_merge(self):
        """This profile last synced with another account: ask before mixing the two."""
        email = self.account.email or "this account"
        choice = self.dialog_choice(
            "Different account",
            f"This profile's cards and progress came from a different account than {email}.\n\n"
            f"Use {email}'s cards: this profile switches to that account's cards and progress. "
            "A copy of what's here now is saved in the profile folder first.\n\n"
            f"Add these cards to {email}: both sets end up together in that account.",
            [("replace", f"Use {email}'s cards"), ("merge", "Add these cards"), ("cancel", "Sign out")],
        )
        if choice in ("replace", "merge"):
            self.sync_now(manual=True, mode=choice)
        else:
            try:
                self.account.sign_out()
            except cloud.CloudError:
                pass
            self.sync_status = ""
            self.refresh_account_card()
            self.refresh_header_status()


    def sync_chip_text(self):
        """(icon, text) for the header sync chip; empty text hides it."""
        if not cloud.configured():
            return "", ""
        if not self.account.signed_in:
            return "cloud", "Not signed in"
        if self._syncing:
            return "syncing", "Syncing\u2026"
        if self.sync_status:
            return "warning", "Not synced"
        return "cloud", "Synced" if self.account.state.auto_sync else "Auto sync off"

    def set_chip_icon(self, chip, name, color):
        """Put a line icon before a chip's text, sized to the text beside it."""
        image = self.line_icon(name, max(14, self.px(17)), color)
        if image is not None:
            chip.configure(image=image, compound="left")

    def refresh_sync_chip(self):
        chip = getattr(self, "sync_chip", None)
        if chip is None or not chip.winfo_exists():
            return
        icon, text = self.sync_chip_text()
        if not text:
            chip.pack_forget()
            return
        chip.configure(text=f" {text}")
        self.set_chip_icon(chip, icon, COLORS["muted"])
        if not chip.winfo_manager():
            chip.pack(side="left")

    def refresh_account_card(self):
        self.refresh_sync_chip()
        label = getattr(self, "_account_status_label", None)
        if label is not None and label.winfo_exists():
            label.configure(text=self.account_status_text())

    def account_status_text(self):
        if not cloud.configured():
            return "Sync isn't set up in this copy of MemoryPal yet."
        if not self.account.signed_in:
            return "Keep your cards, progress and settings on all your devices: this computer, your phone, and more."
        if self.sync_status:
            return f"Signed in as {self.account.email}. {self.sync_status}"
        last = self.account.state.last_synced
        mode = "Syncs automatically." if self.account.state.auto_sync else "Automatic sync is off."
        return f"Signed in as {self.account.email}. {mode} " + (f"Last synced {last}." if last else "Not synced yet.")

    def render_account_card(self, parent):
        card = self.card(parent, "Card.TFrame", 22)
        card.pack(fill="x", padx=(0, 8), pady=(0, 16))
        ttk.Label(card, text="Account & sync", style="H2.TLabel").pack(anchor="w")
        self._account_status_label = ttk.Label(card, text=self.account_status_text(), style="CardMuted.TLabel", wraplength=self.px(1040))
        self.fit_wrap(self._account_status_label, pady=(4, 12))
        if not cloud.configured():
            return
        if self.account.signed_in:
            auto = tk.BooleanVar(value=self.account.state.auto_sync)
            auto.trace_add("write", lambda *_args: self.set_auto_sync(auto.get()))
            self.check_toggle(card, auto, "Sync automatically: a few seconds after each change, when you come back to MemoryPal, and every few minutes", fit=True).pack(fill="x", pady=(0, self.px(12)))
            self._auto_sync_var = auto
            ttk.Label(card, text="Cards, reviews, streaks and settings sync. Pictures, recordings and attached files stay on the computer that has them.", style="CardMuted.TLabel", wraplength=self.px(1040)).pack(anchor="w", pady=(0, self.px(12)))
            self.button_row(card, [
                ("Sync now", lambda: self.sync_now(manual=True), "TButton"),
                ("Two-step sign-in", self.open_two_step_manager, "TButton"),
                ("Sign out", self.sign_out_account, "TButton"),
                ("Delete account", self.delete_cloud_account, "TButton"),
            ])
        else:
            self.button_row(card, [
                ("Create account", lambda: self.open_account_dialog("create"), "Primary.TButton"),
                ("Sign in", lambda: self.open_account_dialog("sign_in"), "TButton"),
            ])
        legal = [(label, url) for label, url in (("Privacy Policy", cloud_config.PRIVACY_URL), ("Terms of Use", cloud_config.TERMS_URL)) if url]
        if legal:
            links = tk.Frame(card, bg=COLORS["surface"])
            links.pack(anchor="w", pady=(self.px(12), 0))
            for label, url in legal:
                link = tk.Label(links, text=label, bg=COLORS["surface"], fg=COLORS["primary"], font=self.font("Segoe UI", 10), cursor="hand2")
                link.pack(side="left", padx=(0, self.px(14)))
                self.keyboard_link(link, lambda _event, target=url: open_web_page(target))

    def profiles_using_account(self, user_id):
        """Other profiles on this computer that last synced with this account."""
        names = []
        for name in list_profiles():
            if name == active_profile_name():
                continue
            try:
                state = cloud.SyncState(app_paths.profile_dir(name))
            except OSError:
                continue
            if user_id and state.user_id == user_id:
                names.append(name)
        return names

    def account_signed_in(self, session, message):
        """Remember a new session, sync straight away, and refresh Settings."""
        sharing = self.profiles_using_account(session.user_id)
        if sharing and not self.dialog_confirm(
            "Account already in use",
            f"The profile \"{sharing[0]}\" already syncs with {session.email or 'this account'}. "
            "If this profile signs in too, both profiles will share the same cards, progress and settings.",
            "Share the account",
        ):
            self.client_sign_out(session)
            return
        self.account.remember(session)
        self.mark_sign_in_prompted()
        self.toast_message(message)
        if self.current_view == "settings":
            self.show_view("settings")
        elif self.current_view == "signin":
            # First launch: on to the setup questions (or Today, when the
            # account's first sync brings them along).
            self.show_view(self.start_view())
        self.sync_now()

    def client_sign_out(self, session):
        """End a session that was never kept (the person changed their mind)."""
        self.run_in_background(lambda: self.account.client.sign_out(session), lambda _result, _error: None)

    def password_hint(self, password_field, email=None, email_field=None):
        """A live strength line for a password box: (values) -> (text, colour)."""
        def hint(values):
            password = values.get(password_field, "")
            if not password:
                return f"At least {security.MIN_PASSWORD} characters, with letters and at least one number. Three or four unrelated words and a number make a strong, memorable password.", COLORS["muted"]
            address = email if email is not None else values.get(email_field, "")
            score = security.password_strength(password, address)
            problems = security.password_problems(password, address)
            colour = (COLORS["again_fg"], COLORS["again_fg"], COLORS["warm_text"], COLORS["green"], COLORS["green"])[score]
            text = f"Strength: {security.STRENGTH_LABELS[score]}."
            return (f"{text} {problems[0]}" if problems else text), colour
        return hint

    def check_not_leaked(self, password):
        """Refuse passwords known from data breaches (only a hash prefix is sent)."""
        seen = security.pwned_count(password)
        if seen:
            raise cloud.CloudError(f"This password has appeared in data breaches {seen:,} times, so attackers try it first. Please choose a different one.", "pwned_password")

    def cloud_dialog(self, title, body, fields, submit_label, work, on_success, extra_links=(), hint=None, extra_widgets=None, footer=None, browser_check=False):
        """A small form dialog whose network call runs in the background.

        fields: [(name, label, secret)]. work(values) runs on a worker thread;
        on_success(result, values) runs on the UI thread after the dialog closes.
        hint(values) -> (text, colour) updates a line under the fields as people type.
        footer(content) adds widgets under the fields and returns {name: getter};
        the getters are read on the UI thread into `values` when submitting.
        """
        top, content, actions = self.dialog_window(title, body, width=520)
        if extra_widgets:
            extra_widgets(content)
        entries = {}
        for name, label, secret in fields:
            tk.Label(content, text=label, bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI Semibold", 10), anchor="w").pack(fill="x", pady=(self.px(8), self.px(4)))
            entry = ttk.Entry(content, show="•" if secret else "")
            entry.pack(fill="x")
            entries[name] = entry
        if hint is not None:
            hint_label = tk.Label(content, text="", bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI", 10), anchor="w", justify="left", wraplength=self.px(470))
            hint_label.pack(fill="x", pady=(self.px(6), 0))

            def update_hint(_event=None):
                text, colour = hint({name: entry.get() for name, entry in entries.items()})
                hint_label.configure(text=text, fg=colour)

            for entry in entries.values():
                entry.bind("<KeyRelease>", update_hint, add="+")
            update_hint()
        footer_values = footer(content) if footer else {}
        error = tk.Label(content, text="", bg=COLORS["surface"], fg=COLORS["again_fg"], font=self.font("Segoe UI", 10), anchor="w", justify="left", wraplength=self.px(470))
        error.pack(fill="x", pady=(self.px(8), 0))
        for text, action in extra_links:
            link = tk.Label(content, text=text, bg=COLORS["surface"], fg=COLORS["primary"], font=self.font("Segoe UI", 10), cursor="hand2", anchor="w")
            link.pack(fill="x", pady=(self.px(6), 0))
            self.keyboard_link(link, lambda _event, act=action: (top.destroy(), act()))
        busy = {"on": False}

        def submit():
            if busy["on"]:
                return
            values = {name: entry.get() for name, entry in entries.items()}
            values.update({name: read() for name, read in (footer_values or {}).items()})
            busy["on"] = True
            waiting = "Working…"
            if browser_check and self.account.client.captcha:
                waiting = "Working… Finish the quick check in the browser window that opens."
            error.configure(text=waiting, fg=COLORS["muted"])
            go.configure(state="disabled")

            def done(result, failure):
                busy["on"] = False
                if not top.winfo_exists():
                    return
                go.configure(state="normal")
                if failure is not None:
                    error.configure(text=failure.message if isinstance(failure, cloud.CloudError) else str(failure), fg=COLORS["again_fg"])
                    return
                top.destroy()
                on_success(result, values)

            self.run_in_background(lambda: work(values), done)

        ttk.Button(actions, text="Cancel", command=top.destroy).grid(row=0, column=0, sticky="ew", padx=(0, self.px(8)))
        go = self.solid_button(actions, submit_label, submit)
        go.grid(row=0, column=1, sticky="ew")
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=2)
        self.present_dialog(top)
        top.bind("<Return>", lambda _event: submit())
        top.bind("<Escape>", lambda _event: top.destroy())
        next(iter(entries.values())).focus_set()

    def open_account_dialog(self, mode):
        client = self.account.client
        if mode == "create":
            age_gate = cloud.AgeGate(app_paths.DATA_DIR)
            if age_gate.blocked():
                self.dialog_alert(f"Accounts are for ages {security.MIN_ACCOUNT_AGE} and up", security.UNDER_AGE_MESSAGE, "info")
                return

            def create(values):
                # The age check runs on the device before anything is sent,
                # and the birth month and year are never stored or uploaded.
                if age_gate.blocked():
                    raise cloud.CloudError(security.UNDER_AGE_MESSAGE, "under_age")
                today = date.today()
                problem, under_age = security.account_age_check(values["birth_month"], values["birth_year"], today.year, today.month)
                if under_age:
                    age_gate.refuse()
                if problem:
                    raise cloud.CloudError(problem, "under_age" if under_age else "age_format")
                email, password = values["email"].strip(), values["password"]
                if not cloud.looks_like_email(email):
                    raise cloud.CloudError("That doesn't look like an email address.")
                if password != values["again"]:
                    raise cloud.CloudError("The two passwords don't match.")
                if not values.get("agreed"):
                    raise cloud.CloudError("To create an account, tick the box to agree to the Terms of Use and Privacy Policy.")
                cloud.check_password(password, email)
                self.check_not_leaked(password)
                return client.sign_up(email, password, cloud.consent_record()), email

            def consent_box(content):
                agreed = tk.BooleanVar(value=False)
                row = tk.Frame(content, bg=COLORS["surface"])
                row.pack(fill="x", pady=(self.px(12), 0))
                # The app's own tick box: Tk's native one drew a white-edged
                # square that didn't match the theme.
                self.check_toggle(row, agreed, "I agree to the Terms of Use and Privacy Policy", wraplength=560).pack(anchor="w", fill="x")
                links = tk.Frame(row, bg=COLORS["surface"])
                links.pack(anchor="w", padx=(self.px(24), 0))
                for label, url in (("Read the Terms of Use", cloud_config.TERMS_URL), ("Read the Privacy Policy", cloud_config.PRIVACY_URL)):
                    if not url:
                        continue
                    link = tk.Label(links, text=label, bg=COLORS["surface"], fg=COLORS["primary"], font=self.font("Segoe UI", 10), cursor="hand2")
                    link.pack(side="left", padx=(0, self.px(14)))
                    self.keyboard_link(link, lambda _event, target=url: open_web_page(target))
                return {"agreed": agreed.get}

            def created(result, _values):
                session, email = result
                if session:
                    self.account_signed_in(session, "Account created. Your cards are syncing.")
                else:
                    self.open_code_dialog(email)

            self.cloud_dialog(
                "Create your MemoryPal account",
                "Use an email you can check: we'll email you a code to confirm it. You don't need an account to use MemoryPal; it only keeps your cards in step across devices.",
                [
                    ("birth_month", "Month you were born (1-12)", False),
                    ("birth_year", "Year you were born", False),
                    ("email", "Email", False),
                    ("password", "Password", True),
                    ("again", "Password again", True),
                ],
                "Create account", create, created,
                extra_links=[("Already have an account? Sign in", lambda: self.open_account_dialog("sign_in"))],
                hint=self.password_hint("password", email_field="email"),
                footer=consent_box,
                browser_check=True,
            )
            return

        def sign_in(values):
            email = values["email"].strip()
            wait = self.sign_in_limiter.wait_seconds(email)
            if wait:
                raise cloud.CloudError(security.wait_message(wait), "local_rate_limit")
            try:
                session = client.sign_in(email, values["password"])
            except cloud.CloudError as error:
                if error.code == "email_not_confirmed":
                    # Not confirmed yet: send a fresh code and go to the code
                    # box (this dialog has nowhere to type it). If resending is
                    # rate-limited, the earlier code still works.
                    try:
                        client.resend_confirmation(email)
                    except cloud.CloudError:
                        pass
                    return ("confirm", email)
                if error.code in ("invalid_credentials", "invalid_grant"):
                    self.sign_in_limiter.failed(email)
                raise
            self.sign_in_limiter.succeeded(email)
            return session

        def signed_in(session, _values):
            if isinstance(session, tuple):
                self.open_code_dialog(session[1])
            elif session.needs_second_step:
                self.open_second_step_dialog(session, lambda full: self.account_signed_in(full, "Signed in. Your cards are syncing."))
            else:
                self.account_signed_in(session, "Signed in. Your cards are syncing.")

        self.cloud_dialog(
            "Sign in to MemoryPal",
            "Sign in with the same account on every device to keep your cards in step.",
            [("email", "Email", False), ("password", "Password", True)],
            "Sign in", sign_in, signed_in,
            extra_links=[("Forgot your password?", self.open_reset_dialog), ("New here? Create an account", lambda: self.open_account_dialog("create"))],
            browser_check=True,
        )

    def open_second_step_dialog(self, session, on_done):
        """Ask for the authenticator code after the password (two-step sign-in)."""
        client = self.account.client
        key = f"{session.email}#authenticator"

        def check(values):
            wait = self.sign_in_limiter.wait_seconds(key)
            if wait:
                raise cloud.CloudError(security.wait_message(wait), "local_rate_limit")
            try:
                full = client.verify_authenticator(session, session.factors[0]["id"], values["code"])
            except cloud.CloudError:
                self.sign_in_limiter.failed(key)
                raise
            self.sign_in_limiter.succeeded(key)
            return full

        self.cloud_dialog(
            "Two-step sign-in",
            "Open your authenticator app and type the 6-digit code it shows for MemoryPal.",
            [("code", "Authenticator code", False)],
            "Continue", check, lambda full, _values: on_done(full),
        )

    def open_code_dialog(self, email):
        client = self.account.client
        key = f"{email}#confirm"

        def resend():
            self.run_in_background(lambda: client.resend_confirmation(email), lambda _r, error: self.toast_message(error.message if error else "A new code is on its way.") or self.open_code_dialog(email))

        def confirm(values):
            wait = self.sign_in_limiter.wait_seconds(key)
            if wait:
                raise cloud.CloudError(security.wait_message(wait), "local_rate_limit")
            try:
                return client.verify_code(email, values["code"], "signup")
            except cloud.CloudError:
                self.sign_in_limiter.failed(key)
                raise

        self.cloud_dialog(
            "Check your email",
            f"We sent a code to {email}. Type it here to finish creating your account. (It can take a minute; check the spam folder too.)",
            [("code", "Code from the email", False)],
            "Confirm", confirm,
            lambda session, _values: self.account_signed_in(session, "Email confirmed. Your cards are syncing."),
            extra_links=[("Send a new code", resend)],
        )

    def open_reset_dialog(self):
        client = self.account.client

        def ask(values):
            email = values["email"].strip()
            if not cloud.looks_like_email(email):
                raise cloud.CloudError("That doesn't look like an email address.")
            client.request_password_reset(email)
            return email

        def reset_with_code(email):
            key = f"{email}#reset"

            def verify(values):
                if values["password"] != values["again"]:
                    raise cloud.CloudError("The two passwords don't match.")
                cloud.check_password(values["password"], email)
                self.check_not_leaked(values["password"])
                wait = self.sign_in_limiter.wait_seconds(key)
                if wait:
                    raise cloud.CloudError(security.wait_message(wait), "local_rate_limit")
                try:
                    session = client.verify_code(email, values["code"], "recovery")
                except cloud.CloudError:
                    self.sign_in_limiter.failed(key)
                    raise
                if not session.needs_second_step:
                    client.set_password(session, values["password"])
                return session, values["password"]

            def verified(result, _values):
                session, password = result
                if not session.needs_second_step:
                    self.account_signed_in(session, "Password changed. You're signed in.")
                    return

                # Two-step accounts confirm the authenticator before the password changes.
                def finish(full):
                    self.run_in_background(
                        lambda: client.set_password(full, password),
                        lambda _r, error: self.dialog_alert("Couldn't change the password", error.message, "error") if error else self.account_signed_in(full, "Password changed. You're signed in."),
                    )

                self.open_second_step_dialog(session, finish)

            self.cloud_dialog(
                "Choose a new password",
                f"If {email} has a MemoryPal account, a code is on its way there.",
                [("code", "Code from the email", False), ("password", "New password", True), ("again", "New password again", True)],
                "Save new password", verify, verified,
                hint=self.password_hint("password", email=email),
            )

        self.cloud_dialog("Reset your password", "Enter your account's email and we'll send a code to choose a new password.", [("email", "Email", False)], "Send code", ask, lambda email, _values: reset_with_code(email), browser_check=True)

    def open_two_step_manager(self):
        """Turn two-step sign-in (an authenticator app) on or off."""
        account = self.account
        client = account.client

        def loaded(result, error):
            if error is not None:
                self.dialog_alert("Couldn't check two-step sign-in", getattr(error, "message", str(error)), "error")
                return
            session, factors = result
            if factors:
                if self.dialog_confirm(
                    "Turn off two-step sign-in?",
                    "Signing in will need only your password again. Your account is safer with two-step sign-in on.",
                    "Turn off", destructive=True,
                ):
                    self.run_in_background(
                        lambda: client.remove_authenticator(session, factors[0]["id"]),
                        lambda _r, failure: self.dialog_alert("Couldn't turn it off", failure.message, "error") if failure else self.toast_message("Two-step sign-in is off."),
                    )
                return
            self.run_in_background(lambda: client.enroll_authenticator(session), lambda setup, failure: self.dialog_alert("Couldn't start set-up", failure.message, "error") if failure else self.show_authenticator_setup(session, setup))

        self.run_in_background(lambda: (lambda session: (session, client.factors(session)))(account.active_session()), loaded)

    def show_authenticator_setup(self, session, setup):
        client = self.account.client
        secret = " ".join(setup["secret"][i:i + 4] for i in range(0, len(setup["secret"]), 4))

        def show_key(content):
            box = tk.Frame(content, bg=COLORS["alt"], padx=self.px(14), pady=self.px(12))
            box.pack(fill="x", pady=(0, self.px(6)))
            tk.Label(box, text="Setup key", bg=COLORS["alt"], fg=COLORS["muted"], font=self.font("Segoe UI Semibold", 10), anchor="w").pack(fill="x")
            tk.Label(box, text=secret, bg=COLORS["alt"], fg=COLORS["ink"], font=self.font("Consolas", 15), anchor="w").pack(fill="x", pady=(self.px(4), self.px(8)))
            ttk.Button(box, text="Copy key", command=lambda: (self.clipboard_clear(), self.clipboard_append(setup["secret"]), self.toast_message("Key copied."))).pack(anchor="w")

        def verify(values):
            return client.verify_authenticator(session, setup["factor_id"], values["code"])

        def done(full, _values):
            self.account.remember(full)
            self.toast_message("Two-step sign-in is on. You'll need your authenticator code on new devices.")

        self.cloud_dialog(
            "Set up two-step sign-in",
            "1. Open an authenticator app (Microsoft Authenticator, Google Authenticator, 1Password...).\n2. Add an account and choose \"enter a setup key\" (time-based).\n3. Type the key below, then enter the 6-digit code the app shows.",
            [("code", "Code from the app", False)],
            "Turn on", verify, done,
            extra_widgets=show_key,
        )

    def sign_out_account(self):
        if not self.dialog_confirm("Sign out?", "Your cards stay on this computer; they just stop syncing until you sign in again.", "Sign out"):
            return
        account = self.account
        self.run_in_background(account.sign_out, lambda _r, _e: (self.toast_message("Signed out."), self.show_view("settings") if self.current_view == "settings" else None))

    def delete_cloud_account(self):
        if not self.dialog_confirm(
            "Delete your account?",
            "This permanently deletes your MemoryPal account and the cloud copy of your cards on every device. The cards on this computer stay here. This can't be undone.",
            "Delete account", destructive=True,
        ):
            return
        account = self.account

        def done(_result, error):
            if error is not None:
                self.dialog_alert("Couldn't delete the account", getattr(error, "message", str(error)), "error")
                return
            self.toast_message("Your account and its cloud copy were deleted.")
            if self.current_view == "settings":
                self.show_view("settings")

        self.run_in_background(account.delete_account, done)

    def view_settings(self):
        page = ScrollFrame(self.view_host)
        page.pack(fill="both", expand=True)

        profile_count = len(list_profiles())
        due = len(self.store.due_cards())
        storage_path = str(app_paths.DATA_DIR)
        profile_path = str(self.store.data_file)
        attachment_path = str(self.store.attachment_dir)

        self.render_account_card(page.inner)

        grid = ttk.Frame(page.inner, style="Page.TFrame")
        grid.pack(fill="x", padx=(0, 8), pady=(0, 16))
        # Equal columns so neither card is squeezed; card text wraps to fit.
        grid.columnconfigure(0, weight=1, uniform="settings")
        grid.columnconfigure(1, weight=1, uniform="settings")

        appearance = self.card(grid, "Card.TFrame", 22)
        appearance.grid(row=0, column=0, sticky="nsew", padx=(0, 12), pady=(0, 12))
        ttk.Label(appearance, text="Appearance", style="H2.TLabel").pack(anchor="w")
        self.fit_wrap(ttk.Label(appearance, text=f"Current theme: {self.theme.title()}. Navigation stays expanded for a steadier layout.", style="CardMuted.TLabel", wraplength=self.px(500)), pady=(4, 12))
        self.button_row(
            appearance,
            [
                ("Light mode" if self.theme == "dark" else "Dark mode", self.toggle_theme, "TButton"),
            ],
        )

        window_card = self.card(grid, "Card.TFrame", 22)
        window_card.grid(row=0, column=1, sticky="nsew", pady=(0, 12))
        ttk.Label(window_card, text="Window", style="H2.TLabel").pack(anchor="w")
        self.fit_wrap(ttk.Label(window_card, text="F11 uses true fullscreen. The titlebar square uses borderless focus mode.", style="CardMuted.TLabel", wraplength=self.px(500)), pady=(4, 12))
        state_row = tk.Frame(window_card, bg=COLORS["surface"])
        state_row.pack(fill="x", pady=(0, 12))
        self.render_status_chip(state_row, "True fullscreen on" if self.is_fullscreen else "True fullscreen off", COLORS["green"] if self.is_fullscreen else COLORS["alt"], self.on_color(COLORS["green"]) if self.is_fullscreen else COLORS["muted"])
        self.render_status_chip(state_row, "Focus window on" if self.is_focus_window else "Focus window off", COLORS["primary"] if self.is_focus_window else COLORS["alt"], self.on_color(COLORS["primary"]) if self.is_focus_window else COLORS["muted"])
        self.button_row(
            window_card,
            [
                ("True fullscreen", self.toggle_true_fullscreen, "TButton"),
                ("Focus window", self.toggle_focus_window, "TButton"),
            ],
            "Card.TFrame",
        )

        profile_card = self.card(grid, "Card.TFrame", 22)
        profile_card.grid(row=1, column=0, sticky="nsew", padx=(0, 12))
        ttk.Label(profile_card, text="Profiles", style="H2.TLabel").pack(anchor="w")
        self.fit_wrap(ttk.Label(profile_card, text=f"Active profile: {active_profile_name()}  \u00b7  {profile_count} profile{'s' if profile_count != 1 else ''} on this PC.", style="CardMuted.TLabel", wraplength=self.px(500)), pady=(4, 12))
        self.button_row(profile_card, [("Manage profiles", self.open_profile_manager, "TButton"), ("Edit daily goal", self.edit_daily_goal, "TButton")])

        study_card = self.card(grid, "Card.TFrame", 22)
        study_card.grid(row=1, column=1, sticky="nsew")
        ttk.Label(study_card, text="Study defaults", style="H2.TLabel").pack(anchor="w")
        self.fit_wrap(ttk.Label(study_card, text=f"Daily goal: {self.store.daily_goal} cards. Due now: {due}. Cards stay on this computer unless you sync them with an account or export them.", style="CardMuted.TLabel", wraplength=self.px(500)), pady=(4, 12))
        self.button_row(study_card, [("Start due review", lambda: self.show_view("review"), "TButton"), ("Open in Test Lab", lambda: self.open_testing(return_view="settings", context="study"), "TButton")], "Card.TFrame")

        accessibility_card = self.card(grid, "Card.TFrame", 22)
        accessibility_card.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(0, 12))
        ttk.Label(accessibility_card, text="Accessibility", style="H2.TLabel").pack(anchor="w")
        self.fit_wrap(ttk.Label(
            accessibility_card,
            text="Tune MemoryPal for larger text, steadier screens, clearer contrast, and caregiver-supported use. These settings are saved to this profile.",
            style="CardMuted.TLabel",
            wraplength=self.px(1040),
            justify="left",
        ), pady=(4, 12))
        text_size = tk.StringVar(value=self.accessibility.get("text_size", "Comfort"))
        ttk.Label(accessibility_card, text="Text size", style="CardMuted.TLabel").pack(anchor="w")
        self.select_button(
            accessibility_card,
            text_size,
            ["Comfort", "Large", "Extra Large"],
            on_change=lambda value: self.update_accessibility_preference("text_size", value),
        ).pack(fill="x", pady=(self.px(4), self.px(12)))
        toggle_grid = tk.Frame(accessibility_card, bg=COLORS["surface"])
        toggle_grid.pack(fill="x", pady=(0, self.px(12)))
        accessibility_toggles = [
            ("high_contrast", "Higher contrast text and borders"),
            ("reduce_motion", "Reduce fades and motion"),
            ("simple_language", "Use simpler wording where available"),
            ("caregiver_mode", "Caregiver mode: hide Reset so shared data can't be wiped"),
            ("read_aloud", "Read questions and answers aloud automatically"),
            ("more_time", "More time: slower timed games, messages, and speech"),
            ("listen_answers", "Talk-back study listens for spoken answers (Windows)"),
            ("focus_outline", "Show a bright outline on the focused button (keyboard use)"),
        ]
        for index, (key, label) in enumerate(accessibility_toggles):
            var = tk.BooleanVar(value=bool(self.accessibility.get(key)))
            row = self.check_toggle(toggle_grid, var, label, on_change=lambda checked, pref=key: self.update_accessibility_preference(pref, checked), bg=COLORS["surface"], wraplength=470, fit=True)
            row.grid(row=index // 2, column=index % 2, sticky="ew", padx=(0 if index % 2 == 0 else self.px(12), 0), pady=(0 if index < 2 else self.px(8), 0))
            toggle_grid.columnconfigure(index % 2, weight=1, uniform="toggles")
        self.button_row(
            accessibility_card,
            [
                ("Use senior layout", self.apply_senior_layout_defaults, "TButton"),
                ("Everyday memory", lambda: self.show_view("elder"), "TButton"),
                ("Open feedback", lambda: self.show_view("feedback"), "TButton"),
            ],
            "Card.TFrame",
        )

        welcome_card = self.card(page.inner, "Card.TFrame", 22)
        welcome_card.pack(fill="x", padx=(0, 8), pady=(0, 16))
        ttk.Label(welcome_card, text="Welcome & tour", style="H2.TLabel").pack(anchor="w")
        chosen = self.store.onboarding.get("persona")
        persona_title = onboarding.persona(chosen)["title"] if chosen else "Not chosen yet"
        ttk.Label(welcome_card, text=f"Set up for: {persona_title}. Answer the welcome questions again to change the menu order and comfort settings, or replay the guided tour (also the ? button at the top).", style="CardMuted.TLabel", wraplength=self.px(1040)).pack(anchor="w", pady=(4, 12))
        self.button_row(welcome_card, [("Replay tour", self.start_tour, "TButton"), ("Redo welcome questions", lambda: self.show_view("welcome"), "TButton")])

        nav_card = self.card(page.inner, "Card.TFrame", 22)
        nav_card.pack(fill="x", padx=(0, 8), pady=(0, 16))
        ttk.Label(nav_card, text="Page order", style="H2.TLabel").pack(anchor="w")
        self.fit_wrap(ttk.Label(nav_card, text="Move pages up or down to choose which come first inside Today, Study, Create, Practice and Progress, and in the page finder.", style="CardMuted.TLabel", wraplength=self.px(1040)), pady=(4, 12))
        nav_order = [key for key, _label, _short in self.ordered_nav_items()]
        nav_labels = {key: label for key, label, _short in self.default_nav_items()}
        order_row = tk.Frame(nav_card, bg=COLORS["surface"])
        order_row.pack(fill="x", pady=(0, self.px(12)))
        listbox = tk.Listbox(
            order_row,
            height=8,
            bg=COLORS["input"],
            fg=COLORS["ink"],
            selectbackground=COLORS["primary"],
            selectforeground=self.on_color(COLORS["primary"]),
            relief="flat",
            bd=0,
            highlightthickness=0,
            activestyle="none",
            font=self.font("Segoe UI", 11),
            exportselection=False,
        )
        listbox.pack(side="left", fill="both", expand=True)
        list_scroll = ttk.Scrollbar(order_row, orient="vertical", command=listbox.yview)
        list_scroll.pack(side="right", fill="y")
        listbox.configure(yscrollcommand=list_scroll.set)

        def render_nav_order(selection=0):
            listbox.delete(0, "end")
            for index, key in enumerate(nav_order):
                listbox.insert("end", f"{index + 1}. {nav_labels.get(key, key)}")
            if nav_order:
                selection = max(0, min(selection, len(nav_order) - 1))
                listbox.selection_set(selection)
                listbox.see(selection)

        def selected_nav_index():
            selected = listbox.curselection()
            return selected[0] if selected else 0

        def move_nav(delta):
            index = selected_nav_index()
            target = index + delta
            if target < 0 or target >= len(nav_order):
                return
            nav_order[index], nav_order[target] = nav_order[target], nav_order[index]
            render_nav_order(target)

        def apply_nav_order():
            self.set_nav_order(nav_order)
            self.render_navigation_rail()
            self.toast_message("Page order saved.")

        def reset_nav_order():
            nav_order[:] = [key for key, _label, _short in self.default_nav_items()]
            self.set_nav_order(nav_order)
            self.render_navigation_rail()
            render_nav_order()
            self.toast_message("Page order reset.")

        render_nav_order()
        self.button_row(
            nav_card,
            [
                ("Move up", lambda: move_nav(-1), "TButton"),
                ("Move down", lambda: move_nav(1), "TButton"),
                ("Apply order", apply_nav_order, "TButton"),
                ("Reset order", reset_nav_order, "TButton"),
            ],
            "Card.TFrame",
        )

        storage = self.card(page.inner, "Card.TFrame", 22)
        storage.pack(fill="x", padx=(0, 8), pady=(0, 16))
        ttk.Label(storage, text="Storage & Backups", style="H2.TLabel").pack(anchor="w")
        self.fit_wrap(ttk.Label(storage, text="MemoryPal stores profiles in the platform app-data folder and keeps attachments beside the active profile.", style="CardMuted.TLabel", wraplength=self.px(1040)), pady=(4, 12))
        for label, value in [
            ("App data", storage_path),
            ("Active profile", profile_path),
            ("Attachments", attachment_path),
        ]:
            row = tk.Frame(storage, bg=COLORS["surface"], padx=self.px(14), pady=self.px(10))
            row.pack(fill="x", pady=(0, 8))
            tk.Label(row, text=label, bg=COLORS["surface"], fg=COLORS["primary"], font=self.font("Segoe UI Semibold", 11), width=14, anchor="w").pack(side="left", padx=(0, self.px(12)))
            value_label = tk.Label(row, text=value, bg=COLORS["surface"], fg=COLORS["ink"], font=self.font("Segoe UI", 10), wraplength=self.px(850), justify="left", anchor="w")
            value_label.pack(side="left", fill="x", expand=True)
            self.bind_rewrap(value_label)
        self.button_row(
            storage,
            [
                ("Open Data Folder", self.open_data_folder, "TButton"),
                ("Export Backup", self.export_data, "TButton"),
                ("Import Backup", self.import_data, "TButton"),
            ] + ([] if self.accessibility.get("caregiver_mode") else [("Reset", self.reset_data, "Danger.TButton")]),
        )

        comfort = self.card(page.inner, "Card.TFrame", 22)
        comfort.pack(fill="x", padx=(0, 8))
        ttk.Label(comfort, text="Comfort Notes", style="H2.TLabel").pack(anchor="w")
        self.fit_wrap(ttk.Label(comfort, text="Use focus mode when the window frame feels distracting, true fullscreen for presentations or testing, and profiles when different people use the same computer.", style="Card.TLabel", wraplength=self.px(1040), justify="left"), pady=(4, 0))

    def view_library(self):
        # On a card, like the other pages: on the bare page background the
        # quiet buttons and the filter had no visible edge in the light theme.
        tools = self.card(self.view_host, "Card.TFrame", 16)
        tools.pack(fill="x", padx=(0, 8), pady=(0, 12))
        if self.deck_filter:
            filter_row = tk.Frame(tools, bg=COLORS["alt"], padx=self.px(14), pady=self.px(8))
            filter_row.pack(fill="x", pady=(0, 10))
            tk.Label(filter_row, text=f"Filtered to deck: {self.deck_filter}", bg=COLORS["alt"], fg=COLORS["primary"], font=self.font("Segoe UI Semibold", 11)).pack(side="left")
            ttk.Button(filter_row, text="Clear filter", command=self.clear_deck_filter).pack(side="right")
        search_var = tk.StringVar()
        filter_var = tk.StringVar(value="All")
        ttk.Label(tools, text="Search your cards", style="CardMuted.TLabel").pack(anchor="w", pady=(0, self.px(4)))
        top = ttk.Frame(tools, style="Card.TFrame")
        top.pack(fill="x", pady=(0, 10))
        ttk.Entry(top, textvariable=search_var).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.select_button(top, filter_var, ["All", "Due", "Weak", "Captures"], on_change=lambda _value: render(), width=10).grid(row=0, column=1, sticky="ew", padx=(0, 8))
        ttk.Button(top, text="Apply", command=lambda: render()).grid(row=0, column=2, sticky="ew")
        top.columnconfigure(0, weight=3)
        top.columnconfigure(1, weight=1)
        # Everyday actions only; resetting everything lives in Settings, behind
        # a confirmation, rather than as a big red button beside "Add cards".
        self.button_row(tools, [("Add cards", lambda: self.show_view("capture"), "Primary.TButton"), ("Import backup", self.import_data, "TButton"), ("Export backup", self.export_data, "TButton")], "Card.TFrame")
        page = ScrollFrame(self.view_host)
        page.pack(fill="both", expand=True)

        def matches(text):
            query = normalize_space(search_var.get()).lower()
            return not query or query in text.lower()

        # Building a widget block per card freezes Tk with thousands of cards,
        # so the list shows a page at a time with a "Show more" button. Tk's
        # layout time grows with the page, so pages stay short.
        page_size = 20
        limit = {"count": page_size}

        def show_more():
            limit["count"] += page_size
            render()

        @self.smooth
        def render():
            for child in page.inner.winfo_children():
                child.destroy()
            mode = filter_var.get()
            shown = 0
            hidden = 0
            if mode in ("All", "Captures"):
                for capture in self.store.captures:
                    chunks = capture.chunks or split_study_bits(capture.notes)
                    searchable = " ".join([capture.title, capture.notes, " ".join(chunks)])
                    if not matches(searchable):
                        continue
                    item = self.card(page.inner)
                    item.pack(fill="x", padx=(0, 8), pady=(0, 10))
                    capture_head = ttk.Frame(item, style="Card.TFrame")
                    capture_head.pack(fill="x")
                    self.speak_button(capture_head, ". ".join([capture.title] + chunks), compact=True).pack(side="right")
                    ttk.Label(capture_head, text=f"Capture  \u00b7  {capture.created_at}", style="CardMuted.TLabel").pack(side="left", anchor="w")
                    ttk.Label(item, text=capture.title, style="H2.TLabel", wraplength=1060).pack(anchor="w", pady=(6, 5))
                    ttk.Label(item, text=f"{len(chunks)} study bits", style="CardMuted.TLabel").pack(anchor="w")
                    for index, chunk in enumerate(chunks[:5], 1):
                        ttk.Label(item, text=f"{index}. {chunk}", style="Card.TLabel", wraplength=1080).pack(anchor="w", pady=(2, 0))
                    self.render_media_controls(item, capture)
                    shown += 1
            card_pool = self.store.cards
            if mode == "Due":
                card_pool = self.store.due_cards()
            elif mode == "Weak":
                card_pool = self.store.weak_cards()
            if mode != "Captures":
                if self.deck_filter:
                    card_pool = [card for card in card_pool if (card.deck or "General") == self.deck_filter]
                for card in card_pool:
                    searchable = " ".join([card.deck, card.front, card.back, card.pathway, card.association])
                    if not matches(searchable):
                        continue
                    if shown >= limit["count"]:
                        hidden += 1
                        continue
                    item = self.card(page.inner)
                    item.pack(fill="x", padx=(0, 8), pady=(0, 10))
                    status_line = f"{card.deck}  \u00b7  due {card.next_review}  \u00b7  {card.last_result} {card.last_score}%"
                    if card.buried_until > today_iso():
                        status_line += f"  \u2022  Buried until {card.buried_until}"
                    head = ttk.Frame(item, style="Card.TFrame")
                    head.pack(fill="x")
                    edit = ttk.Button(head, text="Edit", command=lambda c=card: self.open_card_editor(c, render))
                    edit.pack(side="right")
                    self.speak_button(head, f"{card.front}. The answer is: {card.back}", compact=True).pack(side="right", padx=(0, self.px(6)))
                    self.add_tooltip(edit, "Change the words, deck or memory hook, or delete this card.")
                    ttk.Label(head, text=status_line, style="CardMuted.TLabel").pack(side="left", anchor="w")
                    if self.store.is_leech(card):
                        tk.Label(item, text=f"\u26a0 Missed {card.lapses} times \u2014 try rewriting it (Edit) or adding a memory hook", bg=COLORS["again_bg"], fg=COLORS["again_fg"], font=self.font("Segoe UI Semibold", 10), padx=self.px(8), pady=self.px(3)).pack(anchor="w", pady=(4, 0))
                    ttk.Label(item, text=card.front, style="H2.TLabel", wraplength=1060).pack(anchor="w", pady=(6, 5))
                    ttk.Label(item, text=card.back, style="Card.TLabel", wraplength=1080).pack(anchor="w")
                    if card.association:
                        ttk.Label(item, text=f"Memory hook: {card.association}", style="CardMuted.TLabel", wraplength=1080).pack(anchor="w", pady=(8, 0))
                    self.render_media_controls(item, card)
                    shown += 1
            if hidden:
                more = ttk.Frame(page.inner, style="Page.TFrame")
                more.pack(fill="x", pady=(4, 12))
                ttk.Label(more, text=f"Showing {shown} of {shown + hidden}. Search to narrow the list.", style="Muted.TLabel").pack(side="left")
                ttk.Button(more, text=f"Show {min(page_size, hidden)} more", command=show_more).pack(side="right")
            if shown == 0:
                ttk.Label(page.inner, text="No matching material.", style="Muted.TLabel").pack(anchor="w")
            # Search re-renders after the page was built; wrap to the real width again.
            self.fit_wrap_tree(page.inner)

        render()

    def export_data(self):
        import shutil
        from tkinter import filedialog

        path = filedialog.asksaveasfilename(title="Export MemoryPal data", defaultextension=".json", initialfile="memorypal-data.json", filetypes=[("JSON files", "*.json")])
        if path:
            self.store.save()
            shutil.copy2(self.store.data_file, path)
            self.toast_message("Data exported.")

    def import_data(self):
        import json
        from tkinter import filedialog

        path = filedialog.askopenfilename(title="Import MemoryPal data", filetypes=[("JSON files", "*.json")])
        if not path:
            return
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
            if not isinstance(raw, dict) or not isinstance(raw.get("cards", []), list):
                raise ValueError("This file isn't a MemoryPal backup.")
            count = len(raw.get("cards", []))
            if not self.dialog_confirm(
                "Replace this profile's data?",
                f"The backup has {count} card{'s' if count != 1 else ''}. Importing replaces everything in “{active_profile_name()}”. "
                "A copy of what's there now is saved first, next to your data, in case you want it back.",
                "Replace with backup",
                destructive=True,
            ):
                return
            import shutil
            safety = self.store.data_file.with_name(f"memorypal-data.before-import-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json")
            self.store.save()
            shutil.copy2(self.store.data_file, safety)
            self.account.state.start_over()
            self.store.apply_raw(raw)
            self.store.onboarding = {"done": True, "persona": self.store.onboarding.get("persona", "")}
            self.store.save(merge_existing=False)
            self.accessibility = normalize_accessibility(self.store.accessibility)
            self.apply_accessibility_preferences()
            self.show_view("library")
        except (OSError, json.JSONDecodeError, ValueError, TypeError, OverflowError) as exc:
            self.dialog_alert("Import failed", str(exc), "error")

    def reset_data(self):
        body = "Clear local data and restore sample cards?"
        if self.account.signed_in:
            body = (f"This clears this profile on this computer. Your cards and progress are still in your account "
                    f"({self.account.email}) and come back the next time it syncs. To remove them everywhere, "
                    "delete your account in Settings.")
        if self.dialog_confirm("Reset MemoryPal", body, "Reset", destructive=True):
            self.account.state.start_over()
            self.store.reset()
            self.accessibility = normalize_accessibility(self.store.accessibility)
            self.apply_accessibility_preferences()
            self.show_view("library")


def main():
    enable_dpi_awareness()
    app = MemoryPalApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
