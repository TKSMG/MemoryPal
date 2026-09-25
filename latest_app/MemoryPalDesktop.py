import base64
import importlib
import math
import os
import random
import re
import struct
import sys
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
    split_study_bits,
    today_iso,
)
try:
    from memorypal.core import salient_keywords
except ImportError:
    def salient_keywords(text, count=5):
        """Local fallback: top recurring words in text, used as a partial hint.

        Kept here (rather than assumed importable) because this file may be
        distributed on its own without a matching memorypal/core.py.
        """
        words = re.findall(r"[A-Za-z]{4,}", text or "")
        stopwords = {"this", "that", "with", "from", "have", "were", "which", "their", "about", "would", "there", "these", "those"}
        counts = {}
        for word in words:
            lower = word.lower()
            if lower in stopwords:
                continue
            counts[lower] = counts.get(lower, 0) + 1
        ranked = sorted(counts, key=lambda w: (-counts[w], words.index(next(x for x in words if x.lower() == w))))
        return [w.capitalize() for w in ranked[:count]]
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
from memorypal import onboarding, progress, techniques
from memorypal import media
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


def show_screen_cover(width, height):
    """Put a pixel-identical, topmost snapshot of the screen over everything.

    The captured bitmap is handed straight to a layered popup window
    (UpdateLayeredWindow), so it appears atomically with no Tk image
    conversion. The window never takes focus or shows in the taskbar.
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
        screen_dc = user32.GetDC(0)
        memory_dc = gdi32.CreateCompatibleDC(screen_dc)
        bitmap = gdi32.CreateCompatibleBitmap(screen_dc, width, height)
        previous = gdi32.SelectObject(memory_dc, bitmap)
        hwnd = None
        try:
            gdi32.BitBlt(memory_dc, 0, 0, width, height, screen_dc, 0, 0, 0x00CC0020)  # SRCCOPY
            # WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE, WS_POPUP
            hwnd = user32.CreateWindowExW(0x00080000 | 0x00000008 | 0x00000080 | 0x08000000, "STATIC", None,
                                          0x80000000, 0, 0, width, height, None, None, None, None)
            if not hwnd:
                return None
            origin, size = wintypes.POINT(0, 0), wintypes.SIZE(width, height)
            blend = BlendFunction(0, 0, 255, 0)
            if not user32.UpdateLayeredWindow(hwnd, screen_dc, ctypes.byref(origin), ctypes.byref(size), memory_dc,
                                              ctypes.byref(wintypes.POINT(0, 0)), 0, ctypes.byref(blend), 0x4):  # ULW_OPAQUE
                user32.DestroyWindow(hwnd)
                return None
            user32.ShowWindow(hwnd, 4)  # SW_SHOWNOACTIVATE
            ctypes.windll.dwmapi.DwmFlush()  # make sure it is on screen before anything changes
            return hwnd
        finally:
            gdi32.SelectObject(memory_dc, previous)
            gdi32.DeleteObject(bitmap)
            gdi32.DeleteDC(memory_dc)
            user32.ReleaseDC(0, screen_dc)
    except (AttributeError, OSError):
        return None


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
        self._wheel_after = None
        self._presenting = False

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
        if self.horizontal and getattr(event, "state", 0) & 0x0001:
            units = self._wheel_units(event, "x")
            if units:
                self._queue_wheel(units * self._wheel_step_px, axis="x")
            return "break"
        units = self._wheel_units(event, "y")
        if units:
            self._queue_wheel(units * self._wheel_step_px, axis="y")
        return "break"

    def _queue_wheel(self, pixels, axis="y"):
        # A fast wheel spin delivers many events per frame; moving and
        # repainting for each one outruns the embedded widgets and tears.
        # Sum the distance and apply it on a timer. Timers still fire while
        # input events stream in; idle callbacks (and Tk's repaints) don't.
        self._wheel_pending[axis] = self._wheel_pending.get(axis, 0) + pixels
        if self._wheel_after is None and not self._destroyed:
            self._wheel_after = self.after(1, self._flush_wheel)

    def _flush_wheel(self):
        self._wheel_after = None
        pending, self._wheel_pending = self._wheel_pending, {}
        if self._destroyed:
            return
        for axis, pixels in pending.items():
            if pixels:
                self._scroll_pixels(pixels, axis=axis)

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
            self._present(lambda: mover(fraction))
        except (tk.TclError, ValueError, TypeError):
            pass

    def _present(self, move):
        """Apply a scroll move and paint the result before the next one.

        Tk only repaints from idle callbacks, which never run while a
        scrollbar drag streams motion events, so Windows kept shifting stale
        pixels and the page smeared into overlapping ghosts. Each move now
        runs from a timer and immediately draws the newly exposed area.
        Moves are never nested: one requested while painting runs as its own
        frame afterwards.
        """
        if self._presenting:
            self.after(1, lambda: self._present(move))
            return
        self._presenting = True
        try:
            move()
            self._sync_scrollbars()
            self.viewport.update_idletasks()
            flush_pending_paint(self.viewport)
        finally:
            self._presenting = False

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

        try:
            self._present(move)
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
        try:
            self.viewport.yview_scroll(direction, "pages")
            self._sync_scrollbars()
        except tk.TclError:
            pass
        return "break"

    def _scroll_to(self, position):
        try:
            self.viewport.yview_moveto(max(0.0, min(1.0, float(position))))
            self._sync_scrollbars()
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
            if x is not None:
                m = self.max_x_offset()
                self.viewport.xview_moveto(0 if m <= 0 else max(0, min(1, float(x) / m)))
            if y is not None:
                m = self.max_y_offset()
                self.viewport.yview_moveto(0 if m <= 0 else max(0, min(1, float(y) / m)))
            if sync:
                self._sync_scrollbars()
        except (tk.TclError, ValueError, TypeError):
            pass

    def destroy(self):
        self._destroyed = True
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

    def show(self):
        if self.tip or not self.text:
            return
        x = self.widget.winfo_rootx() + 18
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            self.tip,
            text=self.text,
            bg=COLORS["rail"],
            fg=COLORS["white"],
            padx=10,
            pady=7,
            justify="left",
            wraplength=280,
            font=("Segoe UI", 10),
        )
        label.pack()

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
        self.rail_width_units = getattr(self, "rail_width_units", 276)
        self.store = MemoryStore()
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
        self.audio_player = media.AudioPlayer()
        self.preview_photos = {}

        self.app_icon_path = None
        self.title(f"{APP_NAME} \u2014 {active_profile_name()}")
        self.apply_app_icon()
        self._set_window_size()
        self.configure(bg=COLORS["bg"])
        self._styles()
        self._shell()
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Map>", self.restore_window_chrome, add="+")
        self.bind("<F11>", lambda _event: self.toggle_true_fullscreen())
        for sequence in ("<Control-Command-f>", "<Command-Control-f>"):
            try:
                self.bind(sequence, lambda _event: self.toggle_true_fullscreen(), add="+")
            except tk.TclError:
                pass
        self.bind("<Escape>", lambda _event: self.exit_fullscreen_or_focus())
        self.bind("<Alt-Left>", lambda _event: self.go_back())
        for sequence in ("<Control-k>", "<Control-K>"):
            self.bind(sequence, self.open_page_finder)
            # Entry/Text use Ctrl+K to delete to the end of the line; open the
            # finder there too instead of silently erasing what was typed.
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
            cover = show_screen_cover(self.winfo_screenwidth(), self.winfo_screenheight())
            if cover is None:
                frozen = self.set_redraw_frozen(True)
        if cover is None and not frozen:
            (fallback or change)()
            return
        try:
            change()
            self.settle_layout()
        finally:
            if frozen:
                self.set_redraw_frozen(False)
            flush_pending_paint(self)
            if cover is not None:
                remove_screen_cover(cover)

    def prelayout_shell(self, width, height):
        """Lay the rail and main area out for a window size not applied yet."""
        chrome = getattr(self, "app_chrome", None)
        try:
            chrome_h = chrome.winfo_height() if chrome is not None and chrome.winfo_ismapped() else 0
            body_h = max(1, height - chrome_h)
            rail_w = self.px(self.rail_width_units)
            self.rail.place_configure(height=body_h, relheight=0)
            self.main.place_configure(width=max(1, width - rail_w), height=body_h, relwidth=0, relheight=0)
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
        self.resize_start = (event.x_root, event.y_root, self.winfo_width(), self.winfo_height(), self.winfo_x(), self.winfo_y(), mode)

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

    def stop_resize(self, _event=None):
        geometry = self.pending_resize_geometry
        self.resize_start = None
        self.pending_resize_geometry = None
        if geometry:
            # Resize the existing widget tree directly.  The layout managers
            # already respond to <Configure>; hiding the whole application here
            # only masked the underlying geometry problem.
            try:
                self.geometry(geometry)
                self.update_idletasks()
                self.layout_app_body()
            except tk.TclError:
                pass

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

    def default_nav_items(self):
        return [
            ("dashboard", "Dashboard", "D"),
            ("training", "Memory Gym", "G"),
            ("elder", "Everyday Memory", "Em"),
            ("decks", "Decks", "De"),
            ("plan", "Study Plan", "P"),
            ("focus", "Focus", "F"),
            ("capture", "Capture", "C"),
            ("review", "Review", "R"),
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
        color = COLORS["rail"] if scope == "rail" else COLORS["bg"]
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
        color = COLORS["rail"] if scope == "rail" else COLORS["bg"]
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
        top.update_idletasks()
        popup_width = width or max(top.winfo_reqwidth(), top.winfo_width(), self.px(360))
        popup_height = height or max(top.winfo_reqheight(), top.winfo_height(), self.px(160))
        x = owner.winfo_rootx() + max(0, (owner.winfo_width() - popup_width) // 2)
        y = owner.winfo_rooty() + max(0, (owner.winfo_height() - popup_height) // 3)
        top.geometry(f"{popup_width}x{popup_height}+{x}+{y}")
        self.reveal_window(top, owner)
        if modal:
            top.grab_set()

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
        self.rail_width_units = 294 if multiplier > 1.1 else 276
        self.apply_theme_palette()

    def update_accessibility_preference(self, key, value, rebuild=True):
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

    def speak(self, text):
        """Read text aloud with the system voice (slower when More time is on)."""
        if not self.speaker.speak(text, slow=self.accessibility.get("more_time", False)):
            self.toast_message("Read aloud isn't available on this computer.")

    def read_aloud_button(self, parent, text, label="Read aloud"):
        button = ttk.Button(parent, text=label, command=lambda: self.speak(text))
        self.add_tooltip(button, "Read this out loud with the computer's voice. Works offline.")
        return button

    def show_focus_outline(self):
        return bool(self.accessibility.get("focus_outline") or self.accessibility.get("high_contrast"))

    def focus_color(self):
        return COLORS.get("focus", "#f5b301")

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
        return (family, max(8, int(round(size * self.font_scale))))

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
        self.option_add("*Font", self.font("Segoe UI", 12))
        self.style.configure("Root.TFrame", background=COLORS["bg"])
        self.style.configure("Rail.TFrame", background=COLORS["rail"])
        self.style.configure("Page.TFrame", background=COLORS["bg"])
        self.style.configure("Header.TFrame", background=COLORS["surface"], relief="flat", borderwidth=0)
        self.style.configure("Card.TFrame", background=COLORS["surface"], relief="flat", borderwidth=0)
        self.style.configure("AltCard.TFrame", background=COLORS["alt"], relief="flat", borderwidth=0)
        self.style.configure("WarmCard.TFrame", background=COLORS["warm"], relief="flat", borderwidth=0)
        self.style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["ink"], font=self.font("Segoe UI", 12))
        self.style.configure("Muted.TLabel", background=COLORS["bg"], foreground=COLORS["muted"], font=self.font("Segoe UI", 11))
        self.style.configure("Card.TLabel", background=COLORS["surface"], foreground=COLORS["ink"], font=self.font("Segoe UI", 12))
        self.style.configure("CardMuted.TLabel", background=COLORS["surface"], foreground=COLORS["muted"], font=self.font("Segoe UI", 11))
        self.style.configure("Header.TLabel", background=COLORS["surface"], foreground=COLORS["ink"], font=self.font("Segoe UI", 12))
        self.style.configure("HeaderMuted.TLabel", background=COLORS["surface"], foreground=COLORS["muted"], font=self.font("Segoe UI", 11))
        self.style.configure("AltCard.TLabel", background=COLORS["alt"], foreground=COLORS["ink"], font=self.font("Segoe UI", 12))
        self.style.configure("AltMuted.TLabel", background=COLORS["alt"], foreground=COLORS["muted"], font=self.font("Segoe UI", 11))
        self.style.configure("WarmCard.TLabel", background=COLORS["warm"], foreground=COLORS["warm_text"], font=self.font("Segoe UI", 12))
        self.style.configure("WarmMuted.TLabel", background=COLORS["warm"], foreground=COLORS["muted"], font=self.font("Segoe UI", 11))
        self.style.configure("Title.TLabel", background=COLORS["surface"], foreground=COLORS["ink"], font=self.font("Segoe UI Semibold", 28))
        self.style.configure("H2.TLabel", background=COLORS["surface"], foreground=COLORS["ink"], font=self.font("Segoe UI Semibold", 18))
        self.style.configure("AltH2.TLabel", background=COLORS["alt"], foreground=COLORS["ink"], font=self.font("Segoe UI Semibold", 18))
        self.style.configure("WarmH2.TLabel", background=COLORS["warm"], foreground=COLORS["warm_text"], font=self.font("Segoe UI Semibold", 18))
        self.style.configure("Stat.TLabel", background=COLORS["surface"], foreground=COLORS["primary"], font=self.font("Segoe UI Semibold", 34))
        self.style.configure("RailTitle.TLabel", background=COLORS["rail"], foreground=COLORS["white"], font=self.font("Segoe UI Semibold", 20))
        self.style.configure("RailText.TLabel", background=COLORS["rail"], foreground="#9ca3af", font=self.font("Segoe UI", 12))
        self.style.configure("TEntry", padding=self.px(11), background=COLORS["input"], fieldbackground=COLORS["input"], foreground=COLORS["ink"], insertcolor=COLORS["ink"], bordercolor=COLORS["input"], lightcolor=COLORS["input"], darkcolor=COLORS["input"], relief="flat")
        self.style.map("TEntry", bordercolor=[("focus", COLORS["primary"])], lightcolor=[("focus", COLORS["input"])], darkcolor=[("focus", COLORS["input"])])
        self.style.configure("TCombobox", padding=self.px(11), background=COLORS["input"], fieldbackground=COLORS["input"], foreground=COLORS["ink"], bordercolor=COLORS["input"], lightcolor=COLORS["input"], darkcolor=COLORS["input"], relief="flat")
        for scrollbar_style in ("Vertical.TScrollbar", "Horizontal.TScrollbar"):
            self.style.configure(
                scrollbar_style,
                gripcount=0,
                width=self.px(10),
                arrowsize=self.px(9),
                background=COLORS["muted"],
                darkcolor=COLORS["muted"],
                lightcolor=COLORS["muted"],
                troughcolor=COLORS["bg"],
                bordercolor=COLORS["bg"],
                arrowcolor=COLORS["muted"],
                relief="flat",
            )
            self.style.map(
                scrollbar_style,
                background=[("pressed", COLORS["primary"]), ("active", COLORS["primary"])],
                arrowcolor=[("active", COLORS["primary"])],
            )
        self.style.configure("Rail.Vertical.TScrollbar", gripcount=0, width=self.px(13), arrowsize=self.px(11), background=COLORS["muted"], darkcolor=COLORS["rail"], lightcolor=COLORS["rail"], troughcolor=COLORS["rail"], bordercolor=COLORS["rail"], arrowcolor=COLORS["muted"], relief="flat")
        self.style.configure("Horizontal.TProgressbar", troughcolor=COLORS["alt"], background=COLORS["primary"], bordercolor=COLORS["alt"], lightcolor=COLORS["primary"], darkcolor=COLORS["primary"])
        self.style.configure("TButton", padding=self.pad(18, 12), background=COLORS["surface_soft"], foreground=COLORS["ink"], borderwidth=0, relief="flat", focuscolor=COLORS["surface_soft"], font=self.font("Segoe UI Semibold", 11))
        self.style.map("TButton", background=[("active", COLORS["alt"]), ("pressed", self.tint(COLORS["alt"], -14))], foreground=[("active", COLORS["primary"])])
        self.style.configure("Primary.TButton", padding=self.pad(18, 12), background=COLORS["primary"], foreground=COLORS["white"], borderwidth=0, relief="flat", font=self.font("Segoe UI Semibold", 12))
        self.style.map("Primary.TButton", background=[("active", COLORS["primary_dark"]), ("pressed", self.tint(COLORS["primary_dark"], -14))])
        self.style.configure("TMenubutton", padding=self.pad(18, 12), background=COLORS["surface_soft"], foreground=COLORS["ink"], borderwidth=0, bordercolor=COLORS["surface_soft"], lightcolor=COLORS["surface_soft"], darkcolor=COLORS["surface_soft"], arrowcolor=COLORS["muted"], relief="flat", font=self.font("Segoe UI Semibold", 11))
        self.style.map("TMenubutton", background=[("active", COLORS["alt"]), ("pressed", self.tint(COLORS["alt"], -14))], foreground=[("active", COLORS["primary"])])
        self.style.configure("Select.TMenubutton", padding=self.pad(16, 11), background=COLORS["input"], foreground=COLORS["ink"], borderwidth=0, bordercolor=COLORS["input"], lightcolor=COLORS["input"], darkcolor=COLORS["input"], arrowcolor=COLORS["muted"], relief="flat", font=self.font("Segoe UI", 11))
        self.style.map("Select.TMenubutton", background=[("active", COLORS["alt"])])
        self.style.configure("Danger.TButton", padding=self.pad(18, 12), background=COLORS["danger"], foreground=COLORS["white"], borderwidth=0, relief="flat", font=self.font("Segoe UI Semibold", 11))
        self.style.configure("Again.TButton", padding=self.pad(18, 12), background=COLORS["again_bg"], foreground=COLORS["again_fg"], borderwidth=0, relief="flat", font=self.font("Segoe UI Semibold", 11))
        self.style.configure("Review.TButton", padding=self.pad(18, 12), background=COLORS["review_bg"], foreground=COLORS["review_fg"], borderwidth=0, relief="flat", font=self.font("Segoe UI Semibold", 11))
        self.style.configure("Good.TButton", padding=self.pad(18, 12), background=COLORS["good_bg"], foreground=COLORS["good_fg"], borderwidth=0, relief="flat", font=self.font("Segoe UI Semibold", 11))
        self.style.configure("Easy.TButton", padding=self.pad(18, 12), background=COLORS["easy_bg"], foreground=COLORS["easy_fg"], borderwidth=0, relief="flat", font=self.font("Segoe UI Semibold", 11))
        self.style.configure("Nav.TButton", padding=self.pad(20, 15), background=COLORS["rail"], foreground="#d7def0", anchor="w", borderwidth=0, relief="flat", focuscolor=COLORS["rail"], font=self.font("Segoe UI", 12))
        self.style.map("Nav.TButton", background=[("active", COLORS["rail_hover"])], foreground=[("active", COLORS["white"])])
        self.style.configure("ActiveNav.TButton", padding=self.pad(20, 15), background=COLORS["primary"], foreground=COLORS["white"], anchor="w", borderwidth=0, relief="flat", focuscolor=COLORS["primary"], font=self.font("Segoe UI Semibold", 12))

        if self.show_focus_outline():
            # A bright ring on the focused button so keyboard (Tab) users can
            # always see where they are; by default the ring matched the
            # button colour and was invisible.
            for name in ("TButton", "Primary.TButton", "Danger.TButton", "Again.TButton", "Review.TButton", "Good.TButton", "Easy.TButton", "Nav.TButton", "ActiveNav.TButton"):
                self.style.configure(name, focuscolor=self.focus_color(), focusthickness=max(2, self.px(3)))
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
        canvas.create_line(size * 0.25, size * 0.72, size * 0.25, size * 0.32, fill=COLORS["white"], width=max(2, self.px(2)), capstyle="round")
        canvas.create_line(size * 0.25, size * 0.32, size * 0.50, size * 0.62, fill=COLORS["white"], width=max(2, self.px(2)), capstyle="round")
        canvas.create_line(size * 0.50, size * 0.62, size * 0.75, size * 0.32, fill=COLORS["white"], width=max(2, self.px(2)), capstyle="round")
        canvas.create_line(size * 0.75, size * 0.32, size * 0.75, size * 0.72, fill=COLORS["white"], width=max(2, self.px(2)), capstyle="round")
        dot = max(2, self.px(2))
        for x, y in ((0.25, 0.32), (0.50, 0.62), (0.75, 0.32)):
            canvas.create_oval(size * x - dot, size * y - dot, size * x + dot, size * y + dot, fill=COLORS["white"], outline="")

    def render_window_chrome(self, parent, title, close_command, window=None, show_minimize=True, show_fullscreen=True):
        window = window or self
        bar = tk.Frame(parent, bg=COLORS["surface_soft"])
        bar.pack(fill="x")
        grip = tk.Frame(bar, bg=COLORS["surface_soft"])
        grip.pack(side="left", fill="x", expand=True, padx=self.px(14), pady=self.px(8))
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
            width = self.px(38)
            height = self.px(30)
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
                stroke = max(2, self.px(2))
                if value == "\u00d7":
                    arm = self.px(6)
                    button.create_line(cx - arm, cy - arm, cx + arm, cy + arm, fill=text_color, width=stroke, capstyle="round")
                    button.create_line(cx + arm, cy - arm, cx - arm, cy + arm, fill=text_color, width=stroke, capstyle="round")
                elif value == "\u2212":
                    arm = self.px(7)
                    button.create_line(cx - arm, cy, cx + arm, cy, fill=text_color, width=stroke, capstyle="round")
                elif value in ("\u25a1", "\u2750"):
                    half = self.px(6)
                    button.create_rectangle(cx - half, cy - half, cx + half, cy + half, outline=text_color, width=stroke)
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
            self.chrome_fullscreen_button = chrome_button("\u2750" if self.is_focus_window else "\u25a1", self.toggle_focus_window, hint="Toggle borderless focus. Press F11 on Windows/Linux or Control-Command-F on macOS for true fullscreen.")
        close = chrome_button("\u00d7", close_command, COLORS["danger"], COLORS["white"], "Close")
        return bar

    def nav_visible_count(self):
        host = getattr(self, "nav_list_host", None)
        if not host or not host.winfo_exists():
            return 7
        try:
            height = max(1, host.winfo_height())
        except tk.TclError:
            return 7
        # Measure the real Previous/Next controls, range label and nav button
        # height rather than guessing, so the last item is never clipped
        # behind the footer. Both controls are always reserved so the count
        # doesn't change (and reshuffle the list) when one appears.
        try:
            footer_h = (
                self.nav_down_button.winfo_reqheight() + self.px(2)
                + self.nav_range_label.winfo_reqheight() + self.px(6)
                + self.px(26)
            )
            up_h = self.nav_up_button.winfo_reqheight() + self.px(8)
        except (AttributeError, tk.TclError):
            footer_h, up_h = self.px(90), self.px(46)
        top_h = max(self.nav_top_padding(False), self.nav_top_padding(True) + up_h)
        reserved = footer_h + top_h + self.px(6)
        item_step = max(getattr(self, "_nav_item_step", 0) or self.px(58), 1)
        count = int((height - reserved) // item_step)
        return max(3, min(8, count))

    def nav_top_padding(self, has_previous=False):
        # Minimum gap above/below the item list; the spacers in
        # render_nav_page expand past this to centre the list vertically.
        return self.px(8)

    def bind_nav_wheel(self, widget):
        widget.bind("<MouseWheel>", self.handle_nav_wheel, add="+")
        widget.bind("<Button-4>", self.handle_nav_wheel, add="+")
        widget.bind("<Button-5>", self.handle_nav_wheel, add="+")

    def handle_nav_wheel(self, event):
        if getattr(event, "num", None) == 4:
            self.shift_nav_window(-2)
            return "break"
        if getattr(event, "num", None) == 5:
            self.shift_nav_window(2)
            return "break"
        delta = getattr(event, "delta", 0)
        if not delta:
            return "break"
        steps = max(1, min(4, abs(int(delta / 120)) or 1))
        self.shift_nav_window(-steps if delta > 0 else steps)
        return "break"

    def shift_nav_window(self, delta):
        items = getattr(self, "nav_items_cache", self.ordered_nav_items())
        visible = self.nav_visible_count()
        max_first = max(0, len(items) - visible)
        current = int(getattr(self, "nav_first_index", 0))
        next_index = int(clamp(current + delta, 0, max_first))
        if next_index == current:
            return
        self.nav_first_index = next_index
        self.render_nav_page()

    def ensure_nav_item_visible(self, key):
        items = getattr(self, "nav_items_cache", self.ordered_nav_items())
        keys = [item_key for item_key, _label, _short in items]
        if key not in keys:
            return
        index = keys.index(key)
        visible = self.nav_visible_count()
        first = int(getattr(self, "nav_first_index", 0))
        if index < first:
            self.nav_first_index = index
        elif index >= first + visible:
            self.nav_first_index = max(0, index - visible + 1)
        self.render_nav_page()

    def render_nav_page(self):
        host = getattr(self, "nav_list_frame", None)
        if not host or not host.winfo_exists():
            return
        for child in host.winfo_children():
            child.destroy()

        items = getattr(self, "nav_items_cache", self.ordered_nav_items())
        visible = self.nav_visible_count()
        max_first = max(0, len(items) - visible)
        first = int(clamp(getattr(self, "nav_first_index", 0), 0, max_first))
        self.nav_first_index = first
        end = min(len(items), first + visible)
        self.nav_buttons = {}
        above = first > 0
        below = end < len(items)

        # Equal expanding spacers above and below keep the visible page of
        # items vertically centred between the brand and the footer controls.
        top_padding = self.nav_top_padding(has_previous=above)
        spacer = tk.Frame(host, bg=COLORS["rail"], height=top_padding)
        spacer.pack(fill="both", expand=True)
        self.bind_nav_wheel(spacer)

        for key, label, _short in items[first:end]:
            button = ttk.Button(
                host,
                text=label,
                style="Nav.TButton",
                command=lambda view=key: self.show_view(view),
            )
            button.pack(fill="x", padx=self.px(20), pady=self.px(6))
            self.bind_nav_wheel(button)
            self.add_tooltip(button, self.nav_hint(key))
            self.nav_buttons[key] = button

        bottom_spacer = tk.Frame(host, bg=COLORS["rail"], height=top_padding)
        bottom_spacer.pack(fill="both", expand=True)
        self.bind_nav_wheel(bottom_spacer)

        if hasattr(self, "nav_range_label") and self.nav_range_label.winfo_exists():
            self.nav_range_label.configure(text=f"{first + 1}-{end} of {len(items)}")
        if hasattr(self, "nav_up_button") and self.nav_up_button.winfo_exists():
            if above:
                if not self.nav_up_button.winfo_manager():
                    self.nav_up_button.pack(fill="x", padx=self.px(20), pady=(0, self.px(8)), before=self.nav_list_frame)
                self.nav_up_button.configure(fg=COLORS["muted"], cursor="hand2")
            else:
                self.nav_up_button.pack_forget()
        if hasattr(self, "nav_down_button") and self.nav_down_button.winfo_exists():
            if below:
                if not self.nav_down_button.winfo_manager():
                    self.nav_down_button.pack(fill="x", pady=(0, self.px(2)), before=self.nav_range_label)
                self.nav_down_button.configure(
                    text="\u2193 Next pages",
                    fg=COLORS["muted"],
                    cursor="hand2",
                )
            else:
                self.nav_down_button.pack_forget()
        self.nav_visible_items = visible
        self.nav_top_padding_value = top_padding
        self.refresh_nav_selection()
        if self.nav_buttons:
            # Record the actual button height (plus its pady) for capacity
            # math; re-check once if the earlier estimate was off.
            step = next(iter(self.nav_buttons.values())).winfo_reqheight() + 2 * self.px(6)
            if step != getattr(self, "_nav_item_step", None):
                self._nav_item_step = step
                self.after_idle(self.refresh_nav_capacity)

    def refresh_nav_capacity(self, _event=None):
        if not hasattr(self, "nav_list_frame"):
            return
        visible = self.nav_visible_count()
        top_padding = self.nav_top_padding(has_previous=getattr(self, "nav_first_index", 0) > 0)
        if visible != getattr(self, "nav_visible_items", None) or top_padding != getattr(self, "nav_top_padding_value", None):
            self.render_nav_page()

    def render_navigation_rail(self, rail_width=None, preserve_cover=None):
        for child in self.rail.winfo_children():
            if child is preserve_cover:
                continue
            child.destroy()
        rail_width = rail_width if rail_width is not None else getattr(self, "rail_width_units", 276)
        self.rail_width_units = rail_width
        self.rail.configure(width=self.px(rail_width))
        self.layout_app_body()
        self.rail.pack_propagate(False)
        brand = ttk.Frame(self.rail, style="Rail.TFrame")
        brand.pack(fill="x", padx=self.px(22), pady=self.pad(30, 24))
        mark_size = self.px(54)
        mark = tk.Canvas(brand, width=mark_size, height=mark_size, bg=COLORS["rail"], highlightthickness=0)
        mark.pack(side="left", padx=(0, self.px(14)))
        if not self.draw_memorypal_logo(mark, mark_size):
            self.draw_chrome_icon(mark, mark_size)
        label_box = ttk.Frame(brand, style="Rail.TFrame")
        label_box.pack(side="left")
        ttk.Label(label_box, text="MemoryPal", style="RailTitle.TLabel").pack(anchor="w")
        ttk.Label(label_box, text="Memory training", style="RailText.TLabel").pack(anchor="w")

        self.nav_items_cache = self.ordered_nav_items()
        self.nav_buttons = {}

        nav_host = tk.Frame(self.rail, bg=COLORS["rail"], highlightthickness=0)
        nav_host.pack(fill="both", expand=True)
        self.bind_nav_wheel(self.rail)
        self.bind_nav_wheel(brand)
        self.bind_nav_wheel(nav_host)

        control_bg = self.tint(COLORS["rail"], 8 if self.theme == "dark" else -4)
        self.nav_up_button = tk.Label(
            nav_host,
            text="\u2191 Previous pages",
            bg=control_bg,
            fg=COLORS["muted"],
            padx=self.px(12),
            pady=self.px(8),
            cursor="hand2",
            font=self.font("Segoe UI Semibold", 10),
        )
        self.nav_up_button.bind("<Button-1>", lambda _event: self.shift_nav_window(-max(1, self.nav_visible_count())), add="+")
        self.bind_nav_wheel(self.nav_up_button)

        self.nav_list_host = nav_host
        self.nav_list_frame = tk.Frame(nav_host, bg=COLORS["rail"], highlightthickness=0)
        self.nav_list_frame.pack(fill="both", expand=True, pady=(self.px(6), 0))
        self.bind_nav_wheel(self.nav_list_frame)

        # Pack the footer from the bottom ahead of the list so the "Next pages"
        # control keeps its space instead of being squeezed off the rail.
        footer = tk.Frame(nav_host, bg=COLORS["rail"], highlightthickness=0)
        footer.pack(side="bottom", fill="x", padx=self.px(20), pady=(self.px(8), self.px(18)), before=self.nav_list_frame)
        self.nav_footer = footer
        self.nav_down_button = tk.Label(
            footer,
            text="\u2193 Next pages",
            bg=control_bg,
            fg=COLORS["muted"],
            padx=self.px(12),
            pady=self.px(8),
            cursor="hand2",
            font=self.font("Segoe UI Semibold", 10),
        )
        self.nav_down_button.bind("<Button-1>", lambda _event: self.shift_nav_window(max(1, self.nav_visible_count())), add="+")
        self.bind_nav_wheel(self.nav_down_button)
        self.nav_range_label = tk.Label(
            footer,
            text="",
            bg=COLORS["rail"],
            fg=COLORS["muted"],
            font=self.font("Segoe UI", 10),
        )
        self.nav_range_label.pack(anchor="center", pady=(self.px(6), 0))
        self.bind_nav_wheel(self.nav_range_label)

        nav_host.bind("<Configure>", self.refresh_nav_capacity, add="+")
        self.ensure_nav_item_visible(getattr(self, "current_view", "dashboard"))
        self.after_idle(lambda: self.ensure_nav_item_visible(getattr(self, "current_view", "dashboard")))

    def refresh_nav_selection(self):
        if not hasattr(self, "nav_buttons"):
            return
        for key, button in self.nav_buttons.items():
            if not button.winfo_exists():
                continue
            button.configure(style="ActiveNav.TButton" if key == self.current_view else "Nav.TButton")

    def active_profile_number(self):
        profiles = list_profiles()
        active = active_profile_name()
        try:
            return profiles.index(active) + 1
        except ValueError:
            return 1

    def header_icon_button(self, parent, icon, command, hint="", size=42, active=False):
        pixel_size = self.px(size)
        canvas = tk.Canvas(
            parent,
            width=pixel_size,
            height=pixel_size,
            bg=COLORS["surface"],
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        canvas._memorypal_active = active

        def icon_glyph(name):
            family = self.available_font("Segoe MDL2 Assets", "Segoe Fluent Icons")
            if family != "Segoe UI Symbol":
                glyphs = {
                    "moon": "\ue708",
                    "sun": "\ue706",
                    "backup": "\ue896",
                    "settings": "\ue713",
                    "help": "\ue897",
                    "search": "\ue721",
                    "back": "\ue72b",
                }
                return family, glyphs.get(name, name)
            fallback = {
                "moon": "\u263e",
                "sun": "\u2600",
                "backup": "\u2193",
                "settings": "\u2699",
                "help": "?",
                "search": "\u2315",
                "back": "\u2190",
            }
            return family, fallback.get(name, name)

        def draw_icon_text(name, icon_size, icon_color):
            family, glyph = icon_glyph(name)
            self.create_centered_canvas_text(
                canvas,
                pixel_size / 2,
                pixel_size / 2,
                text=glyph,
                fill=icon_color,
                font=self.font(family, icon_size),
            )

        def draw(hover=False):
            canvas.delete("all")
            is_active = bool(getattr(canvas, "_memorypal_active", active))
            normal_fill = self.tint(COLORS["surface"], -5 if self.theme == "light" else 10)
            active_fill = self.tint(COLORS["surface"], -10 if self.theme == "light" else 18)
            fill = active_fill if hover or is_active else normal_fill
            ink = COLORS["primary"] if hover or is_active else COLORS["muted"]
            if not self.draw_antialiased_shape(canvas, pixel_size, pixel_size, fill, radius=self.px(14), inset=1):
                canvas.create_rectangle(0, 0, pixel_size, pixel_size, fill=fill, outline="")
            center = pixel_size / 2
            if icon == "theme":
                if self.theme == "dark":
                    draw_icon_text("moon", 18, ink)
                else:
                    draw_icon_text("sun", 18, ink)
            elif icon == "fullscreen":
                pad = self.px(12)
                short = self.px(7)
                for sx, sy, dx, dy in ((pad, pad, short, short), (pixel_size - pad, pad, -short, short), (pad, pixel_size - pad, short, -short), (pixel_size - pad, pixel_size - pad, -short, -short)):
                    canvas.create_line(sx, sy, sx + dx, sy, fill=ink, width=self.px(2), capstyle="round")
                    canvas.create_line(sx, sy, sx, sy + dy, fill=ink, width=self.px(2), capstyle="round")
            elif icon == "backup":
                draw_icon_text("backup", 18, ink)
            elif icon == "help":
                draw_icon_text("help", 17, ink)
            elif icon in ("search", "back"):
                draw_icon_text(icon, 16, ink)
            elif icon == "settings":
                draw_icon_text("settings", 17, ink)
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
        size = self.px(42)
        profile_number = str(min(self.active_profile_number(), 99))
        profile_label = f"P{profile_number}"
        button = tk.Canvas(
            parent,
            width=size,
            height=size,
            bg=COLORS["surface"],
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )

        def draw(hover=False):
            button.delete("all")
            if self.theme == "light":
                fill = self.tint(COLORS["surface"], -9 if hover else -4)
            else:
                fill = self.tint(COLORS["surface"], 17 if hover else 9)
            ink = COLORS["primary"] if hover else COLORS["ink"]
            if not self.draw_antialiased_shape(button, size, size, fill, radius=self.px(14), inset=1):
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

        self.rail_width_units = getattr(self, "rail_width_units", 276)
        self.rail = ttk.Frame(self.app_body, style="Rail.TFrame")
        self.rail.place(x=0, y=0, width=self.px(self.rail_width_units), relheight=1)
        self.rail.pack_propagate(False)
        self.render_navigation_rail()

        self.main = ttk.Frame(self.app_body, style="Page.TFrame")
        self.main.place(x=self.px(self.rail_width_units), y=0, width=1, relheight=1)
        top = ttk.Frame(self.main, style="Header.TFrame", padding=self.pad(22, 18))
        top.pack(fill="x", padx=self.px(36), pady=self.pad(28, 16))
        top.columnconfigure(0, weight=1)
        top.columnconfigure(1, weight=0)
        title_box = ttk.Frame(top, style="Header.TFrame")
        title_box.grid(row=0, column=0, sticky="ew")
        self.eyebrow = ttk.Label(title_box, text="Today", style="HeaderMuted.TLabel")
        self.eyebrow.pack(anchor="w")
        self.title_label = ttk.Label(title_box, text="Dashboard", style="Title.TLabel")
        self.title_label.pack(anchor="w", fill="x")
        action_strip = tk.Frame(top, bg=COLORS["surface"])
        action_strip.grid(row=0, column=1, rowspan=2, sticky="ne", padx=(self.px(18), 0))
        status_row = tk.Frame(top, bg=COLORS["surface"])
        status_row.grid(row=1, column=0, sticky="w", pady=(self.px(14), 0))
        streak = self.store.current_streak()
        streak_chip = tk.Label(status_row, text=f"\U0001F525 {streak} day{'s' if streak != 1 else ''}", bg=COLORS["warm"], fg=COLORS["warm_text"], padx=self.px(12), pady=self.px(7), font=self.font("Segoe UI Semibold", 10))
        streak_chip.pack(side="left", padx=(0, self.px(10)))
        self.streak_chip = streak_chip
        today = self.store.today_count()
        goal_chip = tk.Label(status_row, text=f"{today}/{self.store.daily_goal} today", bg=COLORS["good_bg"] if today >= self.store.daily_goal else COLORS["alt"], fg=COLORS["good_fg"] if today >= self.store.daily_goal else COLORS["primary"], padx=self.px(12), pady=self.px(7), font=self.font("Segoe UI Semibold", 10))
        goal_chip.pack(side="left", padx=(0, self.px(10)))
        self.goal_chip = goal_chip
        local_chip = tk.Label(status_row, text="Local save", bg=COLORS["alt"], fg=COLORS["primary"], padx=self.px(12), pady=self.px(7), font=self.font("Segoe UI Semibold", 10))
        local_chip.pack(side="left", padx=(0, self.px(10)))
        back_button = self.header_icon_button(action_strip, "back", self.go_back, "Back to the previous page (Alt + Left).")
        back_button.pack(side="left", padx=(0, self.px(8)))
        find_button = self.header_icon_button(action_strip, "search", self.open_page_finder, "Go to any page or action (Ctrl + K).")
        find_button.pack(side="left", padx=(0, self.px(8)))
        help_button = self.header_icon_button(action_strip, "help", self.start_tour, "Show me around: a short guided tour of the pages you use most.")
        help_button.pack(side="left", padx=(0, self.px(8)))
        theme_button = self.header_icon_button(action_strip, "theme", self.toggle_theme, "Switch between light and dark appearance.")
        theme_button.pack(side="left", padx=(0, self.px(8)))
        backup = self.header_icon_button(action_strip, "backup", self.export_data, "Export a local JSON backup of your MemoryPal data.")
        backup.pack(side="left", padx=(0, self.px(8)))
        settings_button = self.header_icon_button(action_strip, "settings", lambda: self.show_view("settings"), "Open Settings.")
        settings_button.pack(side="left", padx=(0, self.px(8)))
        profile_avatar = self.profile_avatar_button(action_strip)
        profile_avatar.pack(side="left")

        self.content = ttk.Frame(self.main, style="Page.TFrame")
        self.content.pack(fill="both", expand=True, padx=self.px(36), pady=(0, self.px(18)))
        self.toast_var = tk.StringVar()
        self.toast = tk.Label(self, textvariable=self.toast_var, bg=COLORS["rail"], fg=COLORS["white"], padx=self.px(20), pady=self.px(14), font=self.font("Segoe UI Semibold", 12))
        right_grip = tk.Frame(self, bg=COLORS["line"], cursor="size_we")
        bottom_grip = tk.Frame(self, bg=COLORS["line"], cursor="size_ns")
        corner_grip = tk.Frame(self, bg=COLORS["muted"], cursor="size_nw_se")
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
            streak_chip.configure(text=f"\U0001F525 {streak} day{'s' if streak != 1 else ''}")
        chip = getattr(self, "goal_chip", None)
        if chip is None or not chip.winfo_exists():
            return
        today = self.store.today_count()
        met = today >= self.store.daily_goal
        chip.configure(
            text=f"{today}/{self.store.daily_goal} today",
            bg=COLORS["good_bg"] if met else COLORS["alt"],
            fg=COLORS["good_fg"] if met else COLORS["primary"],
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
        rail_width = self.px(self.rail_width_units)
        # place() adds relwidth/relheight to width/height, so clear the
        # relative sizes from the initial placement or both panels end up
        # taller than the window and their bottoms are clipped.
        self.rail.place_configure(x=0, y=0, width=rail_width, height=height, relwidth=0, relheight=0)
        self.main.place_configure(x=rail_width, y=0, width=max(1, width - rail_width), height=height, relwidth=0, relheight=0)

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
            "training": "Pick evidence-based study drills or gentle memory-support games.",
            "elder": "Large, calm memory support for routines, people, places, and caregiver-created prompts.",
            "decks": "Browse your decks, see per-deck mastery, and study one deck at a time.",
            "plan": "Answer a few questions and get a tailored study plan for today.",
            "stats": "Charts of your practice, what's coming up, card maturity, and achievements.",
            "focus": "A queue of due, weak, and fresh cards.",
            "capture": "Add study bits, Q/A cards, text, image, audio, and video cues.",
            "review": "Start due cards in Test Lab.",
            "testing": "Focused answer, reveal, Smart Check, and rating page.",
            "quiz": "Self-check or multiple choice practice.",
            "shuffle": "Structured repetition path such as 5, 5-4, 5-4-3, 3-2-1.",
            "tools": "Generate acronyms and mini-stories.",
            "cuelab": "Generate text, image, and audio cues for any card.",
            "games": "Short recall games for attention and memory.",
            "library": "Search, filter, import, export, and review saved material.",
            "feedback": "Record tester ratings, bug notes, accessibility comments, and feature ideas.",
            "settings": "Personalize appearance, profiles, storage, backups, and focus behavior.",
        }.get(key, "")

    def show_view(self, view, transition=False):
        titles = {
            "dashboard": ("Today", "Dashboard"), "training": ("Practice paths", "Memory Gym"),
            "elder": ("Support mode", "Everyday Memory"), "decks": ("Library", "Decks"),
            "plan": ("Plan ahead", "Study Plan"), "stats": ("Progress", "Stats & Streaks"),
            "focus": ("Study plan", "Focus Session"), "capture": ("MemoryPal", "Capture Material"),
            "review": ("MemoryPal", "Spaced Review"), "testing": ("Testing", "Test Lab"),
            "quiz": ("MemoryPal", "Quick Quiz"), "shuffle": ("MemoryPal", "Repetition Path"),
            "tools": ("MemoryPal", "Associations"), "cuelab": ("MemoryPal", "Cue Lab"),
            "games": ("MemoryPal", "Puzzles"), "library": ("MemoryPal", "Library"),
            "feedback": ("Testing", "Feedback Log"), "settings": ("Personalize", "Settings"),
            "welcome": ("Welcome", "Let's set things up"),
        }
        self.speaker.stop()
        self.audio_player.stop()
        self.close_page_finder()
        if self.current_view != view:
            self.save_current_draft()
            previous = self.current_view
            history = self.__dict__.setdefault("view_history", [])
            if previous and previous != "welcome" and not getattr(self, "_going_back", False):
                history.append(previous)
                del history[:-40]
        self.clear_rating_hotkeys()
        self.route_token += 1
        token = self.route_token
        old_host = getattr(self, "view_host", None)
        self.current_view = view
        if hasattr(self, "nav_list_frame"):
            self.ensure_nav_item_visible(view)
        for key, button in self.nav_buttons.items():
            button.configure(style="ActiveNav.TButton" if key == view else "Nav.TButton")

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
            getattr(self, f"view_{view}")()
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
        if old_host is not None and old_host.winfo_exists() and old_host is not new_host:
            old_host.destroy()
        self.update_idletasks()
        self.after_idle(self.layout_app_body)
        if getattr(self, "tour", None):
            self.render_tour_card()

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
        entries = [(label, self.nav_hint(key), lambda key=key: self.show_view(key)) for key, label, _short in self.ordered_nav_items()]
        entries.append(("Settings", self.nav_hint("settings"), lambda: self.show_view("settings")))
        entries += [
            ("Quick 10-minute session", "Ten focused minutes on whatever matters most right now.", self.quick_session),
            ("Start today's review", "Go through the cards that are due now.", lambda: self.show_view("review")),
            ("Make a study plan", "Choose your time and goal and get a step-by-step path.", lambda: self.show_view("plan")),
            ("Take the guided tour", "A short walk through the pages you use most.", self.start_tour),
            ("Switch light / dark", "Change the app's appearance.", self.toggle_theme),
            ("Go back", "Return to the page you were on before (Alt + Left).", self.go_back),
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
        """Ctrl+K: type part of a page or action name and press Enter."""
        self.close_dropdown()
        if getattr(self, "_finder", None) is not None:
            self.close_page_finder()
            return "break"
        entries = self.finder_entries()
        top = tk.Toplevel(self)
        top.withdraw()
        top.overrideredirect(True)
        top.configure(bg=COLORS["surface_soft"])
        top.transient(self)
        self._finder = top
        box = tk.Frame(top, bg=COLORS["surface_soft"], padx=self.px(16), pady=self.px(14))
        box.pack(fill="both", expand=True)
        tk.Label(box, text="Go to a page or action", bg=COLORS["surface_soft"], fg=COLORS["muted"], font=self.font("Segoe UI Semibold", 10)).pack(anchor="w", pady=(0, self.px(6)))
        query = tk.StringVar()
        entry = ttk.Entry(box, textvariable=query, font=self.font("Segoe UI", 13))
        entry.pack(fill="x")
        listbox = tk.Listbox(
            box, height=9, bg=COLORS["surface_soft"], fg=COLORS["ink"], selectbackground=COLORS["primary"], selectforeground=COLORS["white"],
            relief="flat", bd=0, highlightthickness=0, activestyle="none", font=self.font("Segoe UI", 12), exportselection=False, cursor="hand2",
        )
        listbox.pack(fill="both", expand=True, pady=(self.px(10), self.px(6)))
        detail = tk.Label(box, text="", bg=COLORS["surface_soft"], fg=COLORS["muted"], font=self.font("Segoe UI", 10), anchor="w", justify="left", wraplength=self.px(520))
        detail.pack(fill="x")
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

        width = self.px(600)
        top.update_idletasks()
        height = top.winfo_reqheight()
        anchor = getattr(self, "main", self)
        x = anchor.winfo_rootx() + max(0, (anchor.winfo_width() - width) // 2)
        y = anchor.winfo_rooty() + self.px(70)
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
        top.overrideredirect(True)
        top.title("Profiles")
        top.configure(bg=COLORS["bg"])
        self.apply_app_icon(top)
        top.transient(self)
        top.geometry(f"{self.px(420)}x{self.px(480)}")
        top.minsize(self.px(360), self.px(360))

        shell = tk.Frame(top, bg=COLORS["bg"])
        shell.pack(fill="both", expand=True)
        self.render_window_chrome(shell, "Profiles", top.destroy, window=top, show_minimize=False, show_fullscreen=False)

        wrap = tk.Frame(shell, bg=COLORS["bg"], padx=self.px(20), pady=self.px(20))
        wrap.pack(fill="both", expand=True)
        tk.Label(wrap, text="Profiles", bg=COLORS["bg"], fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 20)).pack(anchor="w")
        tk.Label(wrap, text="Each profile keeps its own decks, stats, and streak, completely separate.", bg=COLORS["bg"], fg=COLORS["muted"], font=self.font("Segoe UI", 11), wraplength=self.px(380), justify="left").pack(anchor="w", pady=(4, 16))

        list_holder = tk.Frame(wrap, bg=COLORS["bg"])
        list_holder.pack(fill="both", expand=True)

        def render_list():
            for child in list_holder.winfo_children():
                child.destroy()
            active = active_profile_name()
            for name in list_profiles():
                row = tk.Frame(list_holder, bg=COLORS["surface"], padx=self.px(14), pady=self.px(12))
                row.pack(fill="x", pady=(0, 8))
                label_text = f"\U0001F464 {name}" + ("   \u2022 active" if name == active else "")
                tk.Label(row, text=label_text, bg=COLORS["surface"], fg=(COLORS["primary"] if name == active else COLORS["ink"]), font=self.font("Segoe UI Semibold", 12)).pack(side="left")
                button_area = tk.Frame(row, bg=COLORS["surface"])
                button_area.pack(side="right")
                if name != active:
                    switch_btn = tk.Button(button_area, text="Switch", relief="flat", bd=0, cursor="hand2", bg=COLORS["primary"], fg=COLORS["white"], font=self.font("Segoe UI Semibold", 10), padx=self.px(12), pady=self.px(6), command=lambda n=name: (top.destroy(), self.switch_profile(n)))
                    switch_btn.pack(side="left", padx=(0, 6))
                rename_btn = tk.Button(button_area, text="Rename", relief="flat", bd=0, cursor="hand2", bg=COLORS["alt"], fg=COLORS["primary"], font=self.font("Segoe UI Semibold", 10), padx=self.px(12), pady=self.px(6), command=lambda n=name: do_rename(n))
                rename_btn.pack(side="left", padx=(0, 6))
                if len(list_profiles()) > 1:
                    delete_btn = tk.Button(button_area, text="Delete", relief="flat", bd=0, cursor="hand2", bg=COLORS["again_bg"], fg=COLORS["again_fg"], font=self.font("Segoe UI Semibold", 10), padx=self.px(12), pady=self.px(6), command=lambda n=name: do_delete(n))
                    delete_btn.pack(side="left")

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
            ok, error = delete_profile(name)
            if not ok:
                self.dialog_alert("Delete failed", error, "error", parent=top)
                return
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
        new_button = tk.Button(wrap, text="+ New profile", relief="flat", bd=0, cursor="hand2", bg=COLORS["green"], fg=COLORS["white"], font=self.font("Segoe UI Semibold", 11), padx=self.px(16), pady=self.px(10), command=do_create)
        new_button.pack(fill="x", pady=(12, 0))
        close_button = tk.Button(wrap, text="Close", relief="flat", bd=0, cursor="hand2", bg=COLORS["surface_soft"], fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 11), padx=self.px(16), pady=self.px(10), command=top.destroy)
        close_button.pack(fill="x", pady=(8, 0))
        top.bind("<Escape>", lambda _event: top.destroy())
        self.show_popup_window(top, self, self.px(420), self.px(480))

    def toggle_theme(self):
        self.save_current_draft()
        self.theme = "dark" if self.theme == "light" else "light"
        self.apply_theme_palette()
        self.rebuild_shell(self.current_view, refresh_styles=True)

    def clear_rating_hotkeys(self):
        if not self._hotkeys_bound:
            return
        for seq in ("1", "2", "3", "4", "<Control-z>", "<Control-Z>"):
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
            self.bind("<Control-z>", lambda _event: undo_handler())
            self.bind("<Control-Z>", lambda _event: undo_handler())
        self._hotkeys_bound = True

    def toast_message(self, text):
        self.toast_var.set(text)
        self.toast.place(relx=1, rely=1, anchor="se", x=-self.px(24), y=-self.px(24))
        pending = getattr(self, "_toast_after", None)
        if pending is not None:
            try:
                self.after_cancel(pending)
            except tk.TclError:
                pass
        self._toast_after = self.after(self.pace(2600), self.toast.place_forget)

    def dialog_window(self, title, body="", parent=None, width=480):
        # MemoryPal uses its own small modal surface so prompts, warnings, and
        # confirmations do not fall back to old stock Tk dialog boxes.
        owner = parent or self
        top = tk.Toplevel(owner)
        top.withdraw()
        top.overrideredirect(True)
        top.title(title)
        top.configure(bg=COLORS["bg"])
        self.apply_app_icon(top)
        top.transient(owner)
        top.resizable(False, False)
        top.configure(bg=COLORS["surface"])
        self.render_window_chrome(top, title, top.destroy, window=top, show_minimize=False, show_fullscreen=False)
        shell = tk.Frame(top, bg=COLORS["surface"], padx=self.px(22), pady=self.px(18))
        shell.pack(fill="both", expand=True)
        if body:
            tk.Label(shell, text=body, bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI", 11), wraplength=self.px(width - 70), justify="left", anchor="w").pack(fill="x", pady=(self.px(6), self.px(14)))
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

    def dialog_text(self, title, body, initial="", parent=None, required=True):
        result = {"value": None}
        top, content, actions = self.dialog_window(title, body, parent=parent)
        entry = ttk.Entry(content)
        entry.insert(0, initial or "")
        entry.pack(fill="x")
        error = tk.Label(content, text="", bg=COLORS["surface"], fg=COLORS["danger"], font=self.font("Segoe UI", 10), anchor="w")
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
                error.configure(text="Please enter a whole number.", fg=COLORS["danger"])
                return
            if value < minvalue or value > maxvalue:
                error.configure(text=f"Choose between {minvalue} and {maxvalue}.", fg=COLORS["danger"])
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
        box = tk.Text(parent, height=height, wrap="word", bg=COLORS["input"], fg=COLORS["ink"], bd=0, relief="flat", highlightthickness=1, highlightbackground=COLORS["input"], highlightcolor=COLORS["primary"], padx=self.px(12), pady=self.px(12), font=self.font("Segoe UI", font_size), insertbackground=COLORS["primary"])
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

    def solid_button(self, parent, text, command, color=COLORS["primary"]):
        button = tk.Button(parent, text=text, command=command, bg=color, fg=COLORS["white"], activebackground=color, activeforeground=COLORS["white"], relief="flat", bd=0, cursor="hand2", font=self.font("Segoe UI Semibold", 11), padx=self.px(20), pady=self.px(11))
        self.add_tooltip(button, self.action_hint(text))
        button.bind("<Enter>", lambda _event: button.configure(bg=self.tint(color, -18), activebackground=self.tint(color, -18)), add="+")
        button.bind("<Leave>", lambda _event: button.configure(bg=color, activebackground=color), add="+")
        return button

    def tint(self, hex_color, amount):
        raw = hex_color.lstrip("#")
        if len(raw) != 6:
            return hex_color
        values = [int(raw[index:index + 2], 16) for index in (0, 2, 4)]
        shifted = [max(0, min(255, value + amount)) for value in values]
        return "#" + "".join(f"{value:02x}" for value in shifted)

    def button_palette(self, style_name):
        palettes = {
            "Primary.TButton": (COLORS["primary"], COLORS["white"], COLORS["primary_dark"], COLORS["white"]),
            "Danger.TButton": (COLORS["danger"], COLORS["white"], self.tint(COLORS["danger"], -18), COLORS["white"]),
            "Again.TButton": (COLORS["again_bg"], COLORS["again_fg"], self.tint(COLORS["again_bg"], -14), COLORS["again_fg"]),
            "Review.TButton": (COLORS["review_bg"], COLORS["review_fg"], self.tint(COLORS["review_bg"], -14), COLORS["review_fg"]),
            "Good.TButton": (COLORS["good_bg"], COLORS["good_fg"], self.tint(COLORS["good_bg"], -14), COLORS["good_fg"]),
            "Easy.TButton": (COLORS["easy_bg"], COLORS["easy_fg"], self.tint(COLORS["easy_bg"], -14), COLORS["easy_fg"]),
        }
        return palettes.get(style_name, (COLORS["surface_soft"], COLORS["ink"], COLORS["alt"], COLORS["primary"]))

    def row_button(self, parent, label, command, style_name):
        bg, fg, hover_bg, hover_fg = self.button_palette(style_name)
        button = tk.Button(
            parent,
            text=label,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=hover_bg,
            activeforeground=hover_fg,
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            font=self.font("Segoe UI Semibold", 12 if style_name == "Primary.TButton" else 11),
            padx=self.px(18),
            pady=self.px(12),
        )
        button.bind("<Enter>", lambda _event: button.configure(bg=hover_bg, fg=hover_fg), add="+")
        button.bind("<Leave>", lambda _event: button.configure(bg=bg, fg=fg), add="+")
        button.bind("<Return>", lambda _event: button.invoke(), add="+")
        if self.show_focus_outline():
            # Same colour as the button until it has keyboard focus.
            button.configure(highlightthickness=max(2, self.px(3)), highlightcolor=self.focus_color(), highlightbackground=bg)
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
        normal = normal or COLORS["line"]
        frame.configure(highlightthickness=1, highlightbackground=normal)
        if command is None:
            return frame
        hover = hover or COLORS["primary"]

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

    def open_dropdown(self, anchor, entries):
        self.close_dropdown()
        if not entries:
            return
        previous_grab = self.grab_current()
        top = tk.Toplevel(self)
        top.withdraw()
        top.overrideredirect(True)
        top.configure(bg=COLORS["surface_soft"])
        top.transient(anchor.winfo_toplevel())
        inset = self.px(6)
        listbox = tk.Listbox(
            top,
            height=min(len(entries), 10),
            bg=COLORS["surface_soft"],
            fg=COLORS["ink"],
            selectbackground=COLORS["primary"],
            selectforeground=COLORS["white"],
            relief="flat",
            bd=0,
            highlightthickness=0,
            activestyle="none",
            font=self.font("Segoe UI", 11),
            exportselection=False,
            cursor="hand2",
        )
        listbox.pack(fill="both", expand=True, padx=inset, pady=inset)
        current = 0
        for index, (label, _command, selected) in enumerate(entries):
            listbox.insert("end", f"  {label}  ")
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
            listbox.yview_scroll(-1 if event.delta > 0 else 1, "units")
            return "break"

        listbox.bind("<Motion>", hover)
        listbox.bind("<ButtonRelease-1>", choose)
        listbox.bind("<Return>", choose)
        listbox.bind("<Escape>", lambda _event: (self.close_dropdown(), "break")[1])
        listbox.bind("<MouseWheel>", wheel)
        top.bind("<ButtonPress-1>", press)
        listbox.bind("<ButtonPress-1>", press, add="+")
        listbox.bind("<FocusOut>", lambda _event: self.after(1, lambda: self.focus_get() is None and self.close_dropdown()))

        top.update_idletasks()
        width = max(anchor.winfo_width(), listbox.winfo_reqwidth() + inset * 2)
        height = listbox.winfo_reqheight() + inset * 2
        x = anchor.winfo_rootx()
        y = anchor.winfo_rooty() + anchor.winfo_height() + self.px(4)
        if y + height > self.winfo_screenheight():
            y = anchor.winfo_rooty() - height - self.px(4)
        x = max(0, min(x, self.winfo_screenwidth() - width))
        top.geometry(f"{width}x{height}+{x}+{y}")
        self.reveal_window(top)
        listbox.focus_force()
        try:
            top.grab_set()
        except tk.TclError:
            pass

    def pill_group(self, parent, variable, options, on_change=None, max_columns=None, bg=None):
        bg = bg or COLORS["surface"]
        row = tk.Frame(parent, bg=bg)
        buttons = {}

        def refresh():
            for value, btn in buttons.items():
                selected = value == variable.get()
                btn.configure(
                    bg=COLORS["primary"] if selected else COLORS["input"],
                    fg=COLORS["white"] if selected else COLORS["ink"],
                    activebackground=COLORS["primary_dark"] if selected else COLORS["alt"],
                    activeforeground=COLORS["white"] if selected else COLORS["ink"],
                )

        def choose(value):
            variable.set(value)
            refresh()
            if on_change:
                on_change(value)

        columns = max_columns or len(options) or 1
        for index, option in enumerate(options):
            btn = tk.Button(
                row, text=option, relief="flat", bd=0, cursor="hand2",
                font=self.font("Segoe UI Semibold", 11), padx=self.px(16), pady=self.px(9),
                highlightthickness=0, command=lambda value=option: choose(value),
            )
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
        row = tk.Frame(parent, bg=bg, cursor="hand2")
        size = self.px(19)
        box = tk.Canvas(row, width=size, height=size, highlightthickness=0, bg=bg, cursor="hand2")
        box.pack(side="left", padx=(0, self.px(9)))
        label = tk.Label(row, text=text, bg=bg, fg=COLORS["ink"], font=self.font("Segoe UI", 11), cursor="hand2", justify="left", wraplength=self.px(wraplength), anchor="w")
        label.pack(side="left", fill="x", expand=True)
        if fit:
            self.bind_rewrap(label)

        def draw():
            box.delete("all")
            pad = max(1, self.px(2))
            if variable.get():
                box.create_rectangle(pad, pad, size - pad, size - pad, fill=COLORS["primary"], outline=COLORS["primary"], width=0)
                box.create_line(size * 0.27, size * 0.53, size * 0.43, size * 0.71, fill=COLORS["white"], width=max(2, self.px(2)), capstyle="round")
                box.create_line(size * 0.43, size * 0.71, size * 0.76, size * 0.30, fill=COLORS["white"], width=max(2, self.px(2)), capstyle="round")
            else:
                box.create_rectangle(pad, pad, size - pad, size - pad, fill=COLORS["input"], outline=COLORS["line"], width=max(1, self.px(1)))

        def toggle(_event=None):
            variable.set(not variable.get())
            draw()
            if on_change:
                on_change(variable.get())

        for widget in (row, box, label):
            widget.bind("<Button-1>", toggle)
        draw()
        return row

    def add_tooltip(self, widget, text):
        if text:
            Tooltip(widget, text)

    def action_hint(self, label):
        return {
            "Smart Check": "Compare your response with the saved answer and highlight the suggested bucket.",
            "Reveal / Hide Answer": "Show or hide the saved answer without rating the card.",
            "Reveal Only": "Show the answer without using Smart Check.",
            "Use Smart Rating": "Schedule the card using the latest Smart Check result.",
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
            "Move Up": "Move the selected page higher in the navigation rail.",
            "Move Down": "Move the selected page lower in the navigation rail.",
            "Apply Order": "Save this navigation order and refresh the side rail.",
            "Reset Order": "Return the navigation rail to the default MemoryPal order.",
            "Save Feedback": "Add this tester note to the local feedback log.",
            "Export Feedback": "Save tester notes and ratings as a CSV file.",
            "Open Feedback": "Open the feedback log for tester notes and bug reports.",
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
            "True Fullscreen": "Use the operating system fullscreen mode. F11 does the same thing.",
            "Focus Window": "Use a borderless focus window without changing the operating system fullscreen state.",
        }.get(label, "")

    def mastery_summary(self):
        total = len(self.store.cards)
        if not total:
            return 0, 0, 0
        mastered = len([card for card in self.store.cards if card.last_score >= 82 or card.last_result == "Strong match"])
        learning = len([card for card in self.store.cards if 42 <= card.last_score < 82])
        return round(mastered / total * 100), mastered, learning

    def render_status_chip(self, parent, text, color, fg=None):
        chip = tk.Label(parent, text=text, bg=color, fg=fg or COLORS["white"], font=self.font("Segoe UI Semibold", 10), padx=self.px(12), pady=self.px(6))
        chip.pack(side="left", padx=(0, self.px(8)))
        return chip

    def start_view(self):
        return "dashboard" if self.store.onboarding.get("done") else "welcome"

    def view_welcome(self):
        page = ScrollFrame(self.view_host)
        page.pack(fill="both", expand=True)
        state = {"persona": self.store.onboarding.get("persona") or "", "size_touched": False}
        text_size = tk.StringVar(value=self.accessibility.get("text_size", "Comfort"))
        read_aloud = tk.BooleanVar(value=bool(self.accessibility.get("read_aloud")))

        hero = self.hover_card(tk.Frame(page.inner, bg=COLORS["surface"], padx=self.px(30), pady=self.px(28)))
        hero.pack(fill="x", padx=(0, 8), pady=(0, 16))
        tk.Frame(hero, bg=COLORS["primary"], width=self.px(42), height=self.px(4)).pack(anchor="w", pady=(0, 14))
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
            preview.configure(font=("Segoe UI", sizes.get(text_size.get(), 12)))

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
        self.nav_first_index = 0
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
        tk.Label(card, text=title, bg=COLORS["alt"], fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 16), anchor="w").pack(fill="x", pady=(self.px(4), 0))
        text = tk.Label(card, text=body, bg=COLORS["alt"], fg=COLORS["muted"], font=self.font("Segoe UI", 12), anchor="w", justify="left", wraplength=self.px(410))
        text.pack(fill="x", pady=(self.px(6), self.px(14)))
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

    def view_training(self):
        page = ScrollFrame(self.view_host)
        page.pack(fill="both", expand=True)

        hero = self.hover_card(tk.Frame(page.inner, bg=COLORS["surface"], padx=self.px(28), pady=self.px(26), highlightthickness=1, highlightbackground=COLORS["line"]))
        hero.pack(fill="x", padx=(0, 8), pady=(0, 16))
        tk.Frame(hero, bg=COLORS["cyan"], width=self.px(42), height=self.px(4)).pack(anchor="w", pady=(0, 14))
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
                    canvas.create_text(x + span / 2, h / 2, text=str(value), fill=COLORS["white"], font=self.font("Segoe UI Semibold", 10))
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
        tk.Label(text, text=f"{self.greeting().upper()}  \u2022  TODAY'S PATH", bg=bg, fg=COLORS["primary"], font=self.font("Segoe UI Semibold", 10), anchor="w").pack(fill="x")
        buttons = tk.Frame(head, bg=bg)
        buttons.grid(row=0, column=1, sticky="ne", padx=(self.px(16), 0))

        if not today:
            title, body, action, color = self.best_next_action()
            tk.Label(text, text=title, bg=bg, fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 24), anchor="w").pack(fill="x", pady=(self.px(4), 0))
            tk.Label(text, text=body, bg=bg, fg=COLORS["muted"], font=self.font("Segoe UI", 13), wraplength=self.px(620), justify="left").pack(anchor="w", pady=(self.px(6), 0))
            self.solid_button(buttons, title, action, color).pack(fill="x")
            ttk.Button(buttons, text="Make a study plan", command=lambda: self.show_view("plan")).pack(fill="x", pady=(self.px(8), 0))
            tip = tk.Frame(box, bg=COLORS["alt"], padx=self.px(16), pady=self.px(12))
            tip.pack(fill="x", pady=(self.px(18), 0))
            tk.Label(tip, text="\U0001F5FA  Save a study plan and this card turns into a step-by-step path for each day, with steps you can tick off.", bg=COLORS["alt"], fg=COLORS["ink"], font=self.font("Segoe UI", 11), wraplength=self.px(900), justify="left").pack(anchor="w")
            return

        if today["finished"]:
            tk.Label(text, text="You finished your plan \U0001F389", bg=bg, fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 24), anchor="w").pack(fill="x", pady=(self.px(4), 0))
            tk.Label(text, text=f"{today['title']}. Make a new plan to keep the momentum going, or just keep reviewing what's due.", bg=bg, fg=COLORS["muted"], font=self.font("Segoe UI", 13), wraplength=self.px(620), justify="left").pack(anchor="w", pady=(self.px(6), 0))
            self.solid_button(buttons, "Make a new plan", lambda: self.show_view("plan"), COLORS["primary"]).pack(fill="x")
            ttk.Button(buttons, text="Review due cards", command=lambda: self.show_view("review")).pack(fill="x", pady=(self.px(8), 0))
            return

        steps = today["steps"]
        done = {index for index in self.store.plan_steps_done() if index < len(steps)}
        remaining = [index for index in range(len(steps)) if index not in done]
        heading = "Your plan is done for today \u2705" if not remaining else "Your study plan for today"
        tk.Label(text, text=heading, bg=bg, fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 24), anchor="w").pack(fill="x", pady=(self.px(4), 0))
        tk.Label(text, text=today["title"], bg=bg, fg=COLORS["muted"], font=self.font("Segoe UI", 12), wraplength=self.px(620), justify="left").pack(anchor="w", pady=(self.px(4), 0))
        if remaining:
            step = steps[remaining[0]]
            self.solid_button(buttons, f"Continue: {step['title']}", lambda s=step: self.start_plan_step(s), COLORS["primary"]).pack(fill="x")
        else:
            self.solid_button(buttons, "Keep going: quick quiz", lambda: self.show_view("quiz"), COLORS["green"]).pack(fill="x")
        ttk.Button(buttons, text="Edit plan", command=lambda: self.show_view("plan")).pack(fill="x", pady=(self.px(8), 0))

        progress_row = tk.Frame(box, bg=bg)
        progress_row.pack(fill="x", pady=(self.px(16), self.px(12)))
        progress_row.columnconfigure(0, weight=1)
        self.meter(progress_row, len(done) / max(1, len(steps)), COLORS["green"], 10, bg).grid(row=0, column=0, sticky="ew")
        tk.Label(progress_row, text=f"{len(done)} of {len(steps)} steps", bg=bg, fg=COLORS["muted"], font=self.font("Segoe UI Semibold", 10)).grid(row=0, column=1, padx=(self.px(12), 0))

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
            fg=COLORS["white"] if done else COLORS["primary"],
            font=self.font("Segoe UI Semibold", 12),
            cursor="hand2",
            pady=self.px(4),
        )
        mark.pack(side="left", padx=(0, self.px(14)))
        mark.bind("<Button-1>", lambda _event: on_toggle(index))
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

        streak_panel.configure(bg=COLORS["warm"])
        tk.Label(streak_panel, text=f"\U0001F525 {streak}", bg=COLORS["warm"], fg=COLORS["warm_text"], font=self.font("Segoe UI Semibold", 30), anchor="w").pack(fill="x")
        tk.Label(streak_panel, text=f"day streak" if streak == 1 else "days in a row", bg=COLORS["warm"], fg=COLORS["warm_text"], font=self.font("Segoe UI Semibold", 12), anchor="w").pack(fill="x")
        message = "Practise today to start one." if streak == 0 else ("Practise today to keep it going." if today == 0 else "Kept alive today.")
        tk.Label(streak_panel, text=f"{message} Best: {best} day{'s' if best != 1 else ''}.", bg=COLORS["warm"], fg=COLORS["warm_text"], font=self.font("Segoe UI", 10), wraplength=self.px(220), justify="left").pack(anchor="w", pady=(self.px(8), 0))

        tk.Label(goal_panel, text="Daily goal", bg=COLORS["surface"], fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 13), anchor="w").pack(fill="x")
        ring = tk.Frame(goal_panel, bg=COLORS["surface"])
        ring.pack(anchor="w", pady=(self.px(6), 0))
        self.render_goal_ring(ring, today, goal, size=96, color=COLORS["green"] if today >= goal else COLORS["primary"]).pack()
        left = max(0, goal - today)
        tk.Label(goal_panel, text="Goal reached! \U0001F3AF" if not left else f"{left} more to go", bg=COLORS["surface"], fg=COLORS["green"] if not left else COLORS["muted"], font=self.font("Segoe UI Semibold", 10), anchor="w").pack(fill="x", pady=(self.px(6), 0))

        tk.Label(level_panel, text=f"Level {level['level']}", bg=COLORS["surface"], fg=COLORS["violet"], font=self.font("Segoe UI Semibold", 26), anchor="w").pack(fill="x")
        tk.Label(level_panel, text=f"{level['xp']} / {level['need']} XP", bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI Semibold", 10), anchor="w").pack(fill="x", pady=(self.px(2), self.px(8)))
        self.meter(level_panel, level["pct"], COLORS["violet"], 10).pack(fill="x")
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
        quick = ("\u26a1", "Quick 10", "Ten focused minutes on whatever matters most right now.", self.quick_session, COLORS["primary"])
        modes = {
            "student": ("Picked for studying", [
                quick,
                ("\U0001F4DA", "Deep study", "A full hour: review, new cards, drills, and a self-test.", lambda: self.open_plan_preset(60, "Long-term retention"), COLORS["violet"]),
                ("\u23f1", "Exam cram", "45 minutes aimed at the test: weak cards first.", lambda: self.open_plan_preset(45, "Cram"), COLORS["pink"]),
                ("\U0001F4DD", "Add notes", "Turn today's notes into cards.", lambda: self.show_view("capture"), COLORS["orange"]),
            ]),
            "everyday": ("Picked for everyday memory", [
                ("\U0001F33F", "Gentle review", "People, routines, and places at a calm pace.", lambda: self.show_view("elder"), COLORS["cyan"]),
                ("\U0001F9E9", "Daily puzzles", "Short, friendly memory games.", lambda: self.show_view("games"), COLORS["pink"]),
                quick,
                ("\U0001F50A", "Listen and practise", "Hear each question read aloud as you review.", self.read_aloud_review, COLORS["green"]),
            ]),
            "caregiver": ("Picked for caregivers", [
                ("\U0001F5C2", "Add a memory card", "A person, routine, place, or reminder in plain words.", lambda: self.show_view("elder"), COLORS["cyan"]),
                ("\U0001F91D", "Practise together", "Sit together for a short review.", lambda: self.show_view("review"), COLORS["primary"]),
                ("\U0001F4F7", "Photos and voices", "Attach familiar photos or recordings as cues.", lambda: self.show_view("capture"), COLORS["orange"]),
                ("\U0001F4C8", "Check progress", "See how practice is going this week.", lambda: self.show_view("stats"), COLORS["green"]),
            ]),
            "general": ("Pick a way to practise", [
                quick,
                ("\U0001F9E0", "Try a technique", "Memory palaces, stories, peg lists and more.", lambda: self.show_view("training"), COLORS["violet"]),
                ("\U0001F9E9", "Play a puzzle", "A quick recall game for a warm-up or break.", lambda: self.show_view("games"), COLORS["pink"]),
                ("\U0001F5FA", "Build a plan", "Tell MemoryPal your time and goal; get a path.", lambda: self.show_view("plan"), COLORS["green"]),
            ]),
        }
        return modes.get(persona_key, modes["general"])

    def render_study_modes(self, parent):
        subtitle, modes = self.study_modes()
        head = tk.Frame(parent, bg=COLORS["bg"])
        head.pack(fill="x", padx=(0, 8), pady=(self.px(4), self.px(10)))
        tk.Label(head, text="Study modes", bg=COLORS["bg"], fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 16)).pack(side="left")
        tk.Label(head, text=f"{subtitle}  \u2022  Ctrl+K jumps to any page", bg=COLORS["bg"], fg=COLORS["muted"], font=self.font("Segoe UI", 10)).pack(side="left", padx=(self.px(12), 0), pady=(self.px(4), 0))
        panels = self.panel_row(parent, len(modes))
        for panel, (icon, title, body, action, color) in zip(panels, modes):
            card = self.hover_card(panel, normal=COLORS["surface"], hover=color, command=action)
            card.configure(highlightthickness=max(1, self.px(2)), highlightbackground=COLORS["surface"])
            tk.Label(card, text=icon, bg=COLORS["surface"], fg=color, font=self.font("Segoe UI Emoji", 22), anchor="w").pack(fill="x")
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
            self.accessibility["read_aloud"] = True
            self.store.accessibility = dict(self.accessibility)
            self.store.save()
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
        streak_panel.configure(bg=COLORS["warm"])
        tk.Label(streak_panel, text=f"\U0001F525 {streak}", bg=COLORS["warm"], fg=COLORS["warm_text"], font=self.font("Segoe UI Semibold", 30), anchor="w").pack(fill="x")
        tk.Label(streak_panel, text=f"current streak  \u2022  best {best}", bg=COLORS["warm"], fg=COLORS["warm_text"], font=self.font("Segoe UI Semibold", 11), anchor="w").pack(fill="x")
        tk.Label(level_panel, text=f"Level {level['level']}", bg=COLORS["surface"], fg=COLORS["violet"], font=self.font("Segoe UI Semibold", 26), anchor="w").pack(fill="x")
        tk.Label(level_panel, text=f"{level['xp']} / {level['need']} XP  \u2022  {store.practiced} reviews", bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI", 10), anchor="w").pack(fill="x", pady=(self.px(2), self.px(8)))
        self.meter(level_panel, level["pct"], COLORS["violet"], 10).pack(fill="x")
        goal_head = tk.Frame(goal_panel, bg=COLORS["surface"])
        goal_head.pack(fill="x")
        tk.Label(goal_head, text="Today's goal", bg=COLORS["surface"], fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 13)).pack(side="left")
        change = tk.Label(goal_head, text="Change", bg=COLORS["surface"], fg=COLORS["primary"], font=self.font("Segoe UI Semibold", 10), cursor="hand2")
        change.pack(side="right")
        change.bind("<Button-1>", lambda _event: self.edit_daily_goal())
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
            forecast_panel, [count for _day, count in forecast], ["Today" if index == 0 else day.strftime("%a")[:2] for index, (day, _count) in enumerate(forecast)], COLORS["violet"],
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

    def view_decks(self):
        page = ScrollFrame(self.view_host)
        page.pack(fill="both", expand=True)
        summary = self.store.deck_summary()
        if self.deck_filter:
            banner = self.card(page.inner, "AltCard.TFrame", 16)
            banner.pack(fill="x", padx=(0, 8), pady=(0, 12))
            ttk.Label(banner, text=f"Deck filter active: {self.deck_filter}", style="AltH2.TLabel").pack(side="left")
            ttk.Button(banner, text="Clear filter", command=self.clear_deck_filter).pack(side="right")
        if not summary:
            empty = self.card(page.inner)
            empty.pack(fill="x", padx=(0, 8))
            ttk.Label(empty, text="No decks yet", style="H2.TLabel").pack(anchor="w")
            ttk.Label(empty, text="Add cards in Capture to build your first deck.", style="CardMuted.TLabel").pack(anchor="w", pady=(6, 12))
            ttk.Button(empty, text="Go to Capture", style="Primary.TButton", command=lambda: self.show_view("capture")).pack(fill="x")
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
            self.pill_group(amount_host, amount_var, TIME_UNIT_OPTIONS[unit_var.get()], max_columns=4, bg=COLORS["alt"]).pack(fill="x")

        def cycle_unit(_event=None):
            current_index = TIME_UNIT_ORDER.index(unit_var.get())
            new_unit = TIME_UNIT_ORDER[(current_index + 1) % len(TIME_UNIT_ORDER)]
            unit_var.set(new_unit)
            amount_var.set(TIME_UNIT_OPTIONS[new_unit][0])
            render_amount_pills()
            unit_label.configure(text=unit_display())

        def unit_display():
            return f"{unit_var.get()}  \u2022  click to change"

        render_amount_pills()
        unit_label = tk.Label(time_section, text=unit_display(), bg=COLORS["alt"], fg=COLORS["primary"], font=self.font("Segoe UI Semibold", 10), cursor="hand2")
        unit_label.pack(anchor="w", pady=(2, 0))
        unit_label.bind("<Button-1>", cycle_unit)
        self.add_tooltip(unit_label, "Click to switch between minutes, hours, days, and weeks.")

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
                tk.Label(head, text=f"{index}", bg=COLORS["primary"], fg=COLORS["white"], font=self.font("Segoe UI Semibold", 12), width=3).pack(side="left", padx=(0, 12))
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
                        chart_host, [d["minutes"] for d in days], [str(d["day"]) for d in days], COLORS["violet"], height=120,
                        highlight=selected, tips=[f"Day {d['day']}: {d['minutes']} min, {d.get('due', 0)} due" for d in days],
                        on_click=lambda index: (day_var.set(str(days[index]["day"])), show_day(str(days[index]["day"]))),
                    ).pack(fill="x", pady=(self.px(6), 0))

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

        sections = [("Due now", due), ("Needs focus", weak[:8]), ("Fresh cards", new_cards[:8])]
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
        if source.suffix.lower() not in self.MEDIA_SUFFIXES.get(kind, ()):
            if not self.dialog_confirm(f"Attach this {name}?", f"\"{source.name}\" doesn't look like a {name} MemoryPal knows. Attach it anyway? It will open in whatever app Windows uses for it.", "Attach anyway"):
                return None
        self.store.attachment_dir.mkdir(parents=True, exist_ok=True)
        target = self.store.attachment_dir / f"{uuid4().hex}{source.suffix.lower()}"
        try:
            shutil.copy2(source, target)
        except OSError as exc:
            self.dialog_alert("Couldn't copy the file", f"{source.name} could not be copied into MemoryPal: {exc}", "error")
            return None
        if kind == "image" and self.image_photo(target) is None:
            self.toast_message("Image attached. Windows couldn't make a preview, but it will still open in your photo viewer.")
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
            status.configure(text=f"\u25cf  Recording  {int(seconds // 60)}:{int(seconds % 60):02d}", fg=COLORS["danger"])
            draw_level(recorder.level())
            if seconds >= max_seconds:
                finish()
                return
            state["after"] = self.after(100, tick)

        def start():
            ok, message = recorder.start()
            if not ok:
                status.configure(text="Microphone unavailable", fg=COLORS["danger"])
                note.configure(text=f"{message} Check Settings > Privacy & security > Microphone, or import an audio file instead.")
                return
            start_button.configure(text="Stop and save", command=finish, bg=COLORS["danger"], activebackground=COLORS["danger"])
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
                status.configure(text="Nothing was saved", fg=COLORS["danger"])
                note.configure(text=message)
                start_button.configure(text="Try again", command=start, bg=COLORS["primary"], activebackground=COLORS["primary"])
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
                status.configure(text="The Camera app couldn't be opened. Use Import video instead.", fg=COLORS["danger"])

        def use_recording():
            found = media.newest_video_since(started["at"])
            if found is None:
                folders = ", ".join(str(folder) for folder in media.camera_folders()) or "your Pictures\\Camera Roll folder"
                status.configure(text=f"No new video yet. Finish recording in the Camera app first. (Looked in {folders}.)", fg=COLORS["danger"])
                return
            self.store.attachment_dir.mkdir(parents=True, exist_ok=True)
            target = self.store.attachment_dir / f"video-recording-{datetime.now().strftime('%Y%m%d-%H%M%S')}{found.suffix.lower()}"
            try:
                shutil.copy2(found, target)
            except OSError as exc:
                status.configure(text=f"The video couldn't be copied: {exc}", fg=COLORS["danger"])
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
            ttk.Button(empty, text="Go to Capture", style="Primary.TButton", command=lambda: self.show_view("capture")).pack(fill="x")
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
                ("Record a Voice", lambda: self.record_audio_file(lambda path: self.set_card_media(card, "audio", path, render)), "TButton"),
                ("Attach Audio File", lambda: self.attach_file_to_card(card, "audio", render), "TButton"),
            ])
            if card.audio:
                self.audio_play_button(audio_card, card.audio).pack(fill="x", pady=(self.px(10), 0))

            video_card = self.card(body)
            video_card.pack(fill="x", pady=(12, 0))
            ttk.Label(video_card, text="Video cue", style="H2.TLabel").pack(anchor="w")
            ttk.Label(video_card, text="Current: " + (Path(card.video).name if card.video else "none"), style="CardMuted.TLabel").pack(anchor="w", pady=(4, 10))
            self.button_row(video_card, [
                ("Record with Camera", lambda: self.record_video_file(lambda path: self.set_card_media(card, "video", path, render)), "Primary.TButton"),
                ("Attach Video File", lambda: self.attach_file_to_card(card, "video", render), "TButton"),
            ])

        render()
        self.register_draft_saver("cuelab", lambda: {"pick": pick_var.get()})

    def view_capture(self):
        draft = self.view_drafts.get("capture", {})
        page = ScrollFrame(self.view_host)
        page.pack(fill="both", expand=True)
        wrapper = ttk.Frame(page.inner, style="Page.TFrame")
        wrapper.pack(fill="both", expand=True, padx=(0, 8))
        # Fixed 3:2 split (uniform group) instead of side-by-side pack, which
        # let the form's widest row claim the width and push the side panel
        # off-screen behind a horizontal scrollbar.
        wrapper.columnconfigure(0, weight=3, uniform="capture")
        wrapper.columnconfigure(1, weight=2, uniform="capture")
        wrapper.rowconfigure(0, weight=1)
        form = self.card(wrapper)
        form.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        side = self.card(wrapper, "AltCard.TFrame")
        side.grid(row=0, column=1, sticky="nsew")

        ttk.Label(form, text="Study set builder", style="H2.TLabel").pack(anchor="w")
        ttk.Label(form, text="Add each fact, reminder, or idea as its own bit.", style="CardMuted.TLabel").pack(anchor="w", pady=(6, 18))
        cue = self.card(form, "WarmCard.TFrame", 14)
        cue.pack(fill="x", pady=(0, 14))
        ttk.Label(cue, text="Build one clear item at a time", style="WarmH2.TLabel").pack(anchor="w")
        ttk.Label(cue, text="Use the separate question and answer fields for cards, or add short study bits below. Media buttons attach cues to the whole set.", style="WarmCard.TLabel", wraplength=680).pack(anchor="w", pady=(4, 0))
        ttk.Label(form, text="Title", style="CardMuted.TLabel").pack(anchor="w")
        title = ttk.Entry(form)
        title.insert(0, draft.get("title", "Chapter 3 key terms"))
        title.pack(fill="x", pady=(4, 12))
        ttk.Label(form, text="Card prompt", style="CardMuted.TLabel").pack(anchor="w")
        prompt = ttk.Entry(form)
        prompt.insert(0, draft.get("prompt", "What should I recall from bit {n}?"))
        prompt.pack(fill="x", pady=(4, 12))

        qa_items = [dict(item) for item in draft.get("qa_items", [])]
        qa_panel = self.card(form, "AltCard.TFrame", 18)
        qa_panel.pack(fill="x", pady=(0, 14))
        ttk.Label(qa_panel, text="Question and answer card", style="AltH2.TLabel").pack(anchor="w")
        ttk.Label(qa_panel, text="Use this when you already know the exact prompt and answer.", style="AltMuted.TLabel", wraplength=640).pack(anchor="w", pady=(4, 10))
        ttk.Label(qa_panel, text="Question / title", style="AltMuted.TLabel").pack(anchor="w")
        qa_prompt = ttk.Entry(qa_panel)
        qa_prompt.insert(0, draft.get("qa_prompt", ""))
        qa_prompt.pack(fill="x", pady=(4, 6))
        presets = ttk.Frame(qa_panel, style="AltCard.TFrame")
        presets.pack(fill="x", pady=(0, 10))
        ttk.Label(presets, text="Quick starts:", style="AltMuted.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
        presets.columnconfigure(0, weight=1, uniform="presets")
        presets.columnconfigure(1, weight=1, uniform="presets")

        def use_preset(text):
            qa_prompt.delete(0, "end")
            qa_prompt.insert(0, text)
            qa_prompt.focus_set()

        for preset_index, preset_text in enumerate(["Who is this person?", "What is this appointment?", "Where is this item kept?", "What should happen next?"]):
            chip = ttk.Button(presets, text=preset_text, style="TButton", command=lambda t=preset_text: use_preset(t))
            row, column = divmod(preset_index, 2)
            chip.grid(row=row + 1, column=column, sticky="ew", padx=(0 if column == 0 else 6, 0), pady=(0, 6))
            self.add_tooltip(chip, "Caregiver-friendly starter prompt \u2014 click to use it, then fill in the answer.")
        qa_has_answer = tk.BooleanVar(value=draft.get("qa_has_answer", True))
        answer_toggle = self.check_toggle(qa_panel, qa_has_answer, "This question has a saved answer", on_change=lambda _checked: update_answer_visibility(), bg=COLORS["alt"])
        answer_toggle.pack(anchor="w", pady=(0, 8))
        qa_answer_frame = ttk.Frame(qa_panel, style="AltCard.TFrame")
        qa_answer_frame.pack(fill="x")
        ttk.Label(qa_answer_frame, text="Answer", style="AltMuted.TLabel").pack(anchor="w")
        qa_answer = self.text_box(qa_answer_frame, 3, 12)
        qa_answer.insert("1.0", draft.get("qa_answer", ""))
        qa_answer.pack(fill="x", pady=(4, 10))
        qa_list = tk.Frame(qa_panel, bg=COLORS["alt"])
        qa_list.pack(fill="x", pady=(0, 10))

        def update_answer_visibility():
            if qa_has_answer.get():
                qa_answer_frame.pack(fill="x")
            else:
                qa_answer_frame.pack_forget()
                qa_answer.delete("1.0", "end")

        def refresh_qa():
            for child in qa_list.winfo_children():
                child.destroy()
            if not qa_items:
                tk.Label(qa_list, text="No Q/A cards staged yet.", bg=COLORS["alt"], fg=COLORS["muted"], font=self.font("Segoe UI", 11)).pack(anchor="w")
                return
            for index, item in enumerate(qa_items, 1):
                answer_text = item["answer"] if item["answer"] else "self-check only"
                text = f"{index}. {item['prompt']} -> {answer_text}"
                tk.Label(qa_list, text=text, bg=COLORS["alt"], fg=COLORS["ink"], font=self.font("Segoe UI", 11), wraplength=self.px(620), justify="left").pack(anchor="w", pady=(0, self.px(5)))
            self.fit_wrap_tree(qa_list)

        def add_qa():
            item = {
                "prompt": normalize_space(qa_prompt.get()),
                "answer": normalize_space(qa_answer.get("1.0", "end")) if qa_has_answer.get() else "",
            }
            if not item["prompt"]:
                self.toast_message("Add a question first.")
                return
            if qa_has_answer.get() and not item["answer"]:
                self.toast_message("Add an answer or turn off the answer checkbox.")
                return
            qa_items.append(item)
            qa_prompt.delete(0, "end")
            qa_answer.delete("1.0", "end")
            qa_has_answer.set(True)
            update_answer_visibility()
            refresh_qa()

        def remove_qa():
            if qa_items:
                qa_items.pop()
                refresh_qa()

        self.button_row(qa_panel, [("Add Q/A", add_qa, "Primary.TButton"), ("Remove Last Q/A", remove_qa, "TButton")], "AltCard.TFrame")
        update_answer_visibility()
        refresh_qa()

        ttk.Label(form, text="Study bit", style="CardMuted.TLabel").pack(anchor="w")
        entry = self.text_box(form, 4, 13)
        entry.insert("1.0", draft.get("entry", ""))
        entry.pack(fill="x", pady=(4, 10))
        ttk.Label(form, text="Tip: paste lines like `Question => Answer` here, then use Split Paste or Make Q/A Cards.", style="CardMuted.TLabel", wraplength=680).pack(anchor="w", pady=(0, 10))
        chunks = list(draft.get("chunks", []))
        count_label = ttk.Label(form, text="0 study bits added", style="CardMuted.TLabel")
        count_label.pack(anchor="w")
        chunk_panel = tk.Frame(form, bg=COLORS["surface"])
        chunk_panel.pack(fill="both", expand=True, pady=(8, 12))

        def refresh():
            for child in chunk_panel.winfo_children():
                child.destroy()
            if not chunks:
                tk.Label(chunk_panel, text="Add a bit or split a pasted list to build your study set.", bg=COLORS["surface"], fg=COLORS["muted"], font=("Segoe UI", 12), wraplength=520, justify="left").pack(anchor="w")
            for index, chunk in enumerate(chunks, 1):
                row = tk.Frame(chunk_panel, bg=COLORS["alt"], padx=14, pady=12)
                row.pack(fill="x", pady=(0, 8))
                tk.Label(row, text=f"{index}.", bg=COLORS["alt"], fg=COLORS["primary"], font=("Segoe UI Semibold", 12)).pack(side="left", anchor="n", padx=(0, 8))
                tk.Label(row, text=chunk, bg=COLORS["alt"], fg=COLORS["ink"], wraplength=520, justify="left", font=("Segoe UI", 12)).pack(side="left", fill="x", expand=True)
            count_label.configure(text=f"{len(chunks)} study bit{'s' if len(chunks) != 1 else ''} added")
            self.fit_wrap_tree(chunk_panel)

        def add_bit():
            raw = entry.get("1.0", "end").strip()
            if not raw:
                self.toast_message("Type a study bit first.")
                return
            chunks.append(normalize_space(raw))
            entry.delete("1.0", "end")
            refresh()

        def split_paste():
            bits = split_study_bits(entry.get("1.0", "end"))
            if not bits:
                self.toast_message("Paste a few lines or facts first.")
                return
            chunks.extend(normalize_space(bit) for bit in bits)
            entry.delete("1.0", "end")
            refresh()

        def remove_last():
            if chunks:
                chunks.pop()
                refresh()

        self.button_row(form, [("Add Bit", add_bit, "Primary.TButton"), ("Split Paste", split_paste, "TButton"), ("Remove Last", remove_last, "TButton")])
        ttk.Label(form, text="Attach cues", style="CardMuted.TLabel").pack(anchor="w", pady=(16, 6))
        self.pending_media = dict(draft.get("pending_media", {"text_file": "", "image": "", "audio": "", "video": ""}))
        labels = {
            kind: ttk.Label(side, text=(Path(self.pending_media.get(kind, "")).name if self.pending_media.get(kind) else f"No {self.MEDIA_NAMES.get(kind, kind)} selected"), style="AltCard.TLabel", wraplength=500)
            for kind in ("text_file", "image", "audio", "video")
        }
        cue_bar = ttk.Frame(form, style="Card.TFrame")
        cue_bar.pack(fill="x")
        cue_actions = [
            ("NOTE", [("Import note, PDF, Word or RTF", lambda: self.attach_media("text_file", labels, entry)), ("Save current note", lambda: self.record_text_note(labels, entry)), ("Remove note", lambda: self.set_pending_media("text_file", "", labels))]),
            ("IMG", [("Import image", lambda: self.attach_media("image", labels)), ("Remove image", lambda: self.set_pending_media("image", "", labels))]),
            ("AUD", [("Record audio", lambda: self.record_audio(labels)), ("Import audio", lambda: self.attach_media("audio", labels)), ("Remove audio", lambda: self.set_pending_media("audio", "", labels))]),
            ("VID", [("Record video (Camera app)", lambda: self.record_video(labels)), ("Import video", lambda: self.attach_media("video", labels)), ("Remove video", lambda: self.set_pending_media("video", "", labels))]),
        ]
        for index, (cue_label, actions) in enumerate(cue_actions):
            menu_button = self.cue_menu_button(cue_bar, cue_label, actions)
            menu_button.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else self.px(8), 0))
            cue_bar.columnconfigure(index, weight=1, uniform="cue")
        ttk.Label(form, text="Use the cue buttons to attach files or start recordings without adding more controls to the page.", style="CardMuted.TLabel", wraplength=680).pack(anchor="w", pady=(6, 0))

        def save(make_cards=False, qa_cards=False):
            title_text = normalize_space(title.get()) or "Captured memory material"
            draft = entry.get("1.0", "end").strip()
            final_chunks = list(chunks)
            if draft:
                final_chunks.extend(normalize_space(bit) for bit in split_study_bits(draft))
            staged_qa = list(qa_items)
            parsed_qa = parse_prompt_answer_lines("\n".join(final_chunks))
            qa_lines = [f"{item['prompt']} => {item['answer'] or SELF_CHECK_ANSWER}" for item in staged_qa]
            capture_chunks = final_chunks + qa_lines
            if not capture_chunks and not any(self.pending_media.values()):
                self.toast_message("Add a study bit or media cue first.")
                return
            capture = Capture(title=title_text, notes="\n".join(capture_chunks), chunks=capture_chunks, **self.pending_media)
            self.store.add_capture(capture)
            new_cards = []
            if qa_cards and (staged_qa or parsed_qa):
                for index, item in enumerate(staged_qa + parsed_qa, 1):
                    answer_text = item["answer"] or SELF_CHECK_ANSWER
                    association = "Prompt-answer card created from separate Q/A fields." if item in staged_qa else "Prompt-answer card created from pasted study lines."
                    new_cards.append(Card(deck=title_text, front=item["prompt"], back=answer_text, pathway=f"Capture > {title_text} > Q/A {index}", association=association, **self.pending_media))
            elif make_cards:
                prompt_text = normalize_space(prompt.get()) or "What should I recall from bit {n}?"
                card_chunks = capture_chunks or [f"Use the attached media to recall {title_text}."]
                for index, chunk in enumerate(card_chunks, 1):
                    front = prompt_text.replace("{n}", str(index)).replace("{total}", str(len(card_chunks)))
                    if front == prompt_text and len(card_chunks) > 1:
                        front = f"{front} ({index}/{len(card_chunks)})"
                    new_cards.append(Card(deck="Captured Material", front=front, back=chunk, pathway=f"Capture > {title_text} > Bit {index}", association="Use attached media as a memory cue.", **self.pending_media))
            # One save for the whole batch instead of one per card.
            self.store.add_cards(new_cards)
            created = len(new_cards)
            chunks.clear()
            qa_items.clear()
            entry.delete("1.0", "end")
            qa_prompt.delete(0, "end")
            qa_answer.delete("1.0", "end")
            qa_has_answer.set(True)
            update_answer_visibility()
            refresh()
            refresh_qa()
            self.pending_media = {"text_file": "", "image": "", "audio": "", "video": ""}
            self.view_drafts["capture"] = {}
            for kind, label in labels.items():
                label.configure(text=f"No {'note/document' if kind == 'text_file' else kind} selected")
            self.toast_message(f"Capture saved and {created} cards created." if make_cards else "Capture saved.")

        ttk.Frame(form, style="Card.TFrame").pack(pady=(10, 0))
        self.button_row(form, [("Save Capture", lambda: save(False), "Primary.TButton"), ("Make Cards", lambda: save(True), "TButton"), ("Make Q/A Cards", lambda: save(True, True), "TButton")])

        ttk.Label(side, text="Chunk-based capture", style="AltH2.TLabel").pack(anchor="w")
        ttk.Label(side, text="Each bit becomes its own reusable practice item.", style="AltCard.TLabel", wraplength=500).pack(anchor="w", pady=(10, 22))
        for label in labels.values():
            label.pack(anchor="w", pady=(0, 10))
        refresh()
        self.register_draft_saver("capture", lambda: {
            "title": title.get(),
            "prompt": prompt.get(),
            "qa_prompt": qa_prompt.get(),
            "qa_answer": qa_answer.get("1.0", "end").strip(),
            "qa_has_answer": qa_has_answer.get(),
            "qa_items": [dict(item) for item in qa_items],
            "entry": entry.get("1.0", "end").strip(),
            "chunks": list(chunks),
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

    def open_media(self, path):
        if not path or not Path(path).exists():
            self.toast_message("Media file was not found.")
            return
        try:
            import os
            os.startfile(path)
        except OSError as exc:
            self.dialog_alert("Could not open media", str(exc), "error")

    def audio_play_button(self, parent, path):
        """Play/Stop inside the app; falls back to the default player if needed."""
        button = ttk.Button(parent, text="\u25b6 Play Audio")
        self.add_tooltip(button, "Play the attached audio here. Press again to stop.")

        def watch():
            if not button.winfo_exists():
                return
            if self.audio_player.path == str(path) and self.audio_player.is_playing():
                button.after(250, watch)
            else:
                button.configure(text="\u25b6 Play Audio")

        def toggle():
            if self.audio_player.path == str(path) and self.audio_player.is_playing():
                self.audio_player.stop()
                button.configure(text="\u25b6 Play Audio")
                return
            if not Path(path).exists():
                self.toast_message("Audio file was not found.")
                return
            if self.audio_player.play(path):
                button.configure(text="\u25a0 Stop")
                button.after(250, watch)
            else:
                self.open_media(path)

        button.configure(command=toggle)
        return button

    def image_photo(self, path, max_width=620, max_height=360):
        """A Tk image of any picture Windows can read, scaled to fit (cached)."""
        source = Path(path)
        if not source.exists():
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
            source = Path(path)
            if kind == "text_file" and source.exists():
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
        self.read_aloud_button(host, card.front if not show_answer else f"{card.front}. The answer is: {card.back}", "Read aloud").pack(anchor="w", pady=(0, 12))
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
        ttk.Label(panel, text="Separate testing page", style="H2.TLabel").pack(anchor="w")
        ttk.Label(panel, text="Use this page for focused testing, then return to where you came from.", style="CardMuted.TLabel", wraplength=1040).pack(anchor="w", pady=(6, 16))
        if not card:
            ttk.Label(panel, text="Add cards first.", style="Card.TLabel").pack(anchor="w")
            ttk.Button(panel, text="Back", command=lambda: self.show_view(self.return_view)).pack(fill="x", pady=(16, 0))
            return
        self.testing_card = card
        guide = self.card(panel, "WarmCard.TFrame", 16)
        guide.pack(fill="x", pady=(0, self.px(12)))
        ttk.Label(guide, text="Answer first, then check", style="WarmH2.TLabel").pack(anchor="w")
        ttk.Label(guide, text="Smart Check compares your response in context and suggests a review bucket. Reveal is always available if this is a self-check card.", style="WarmCard.TLabel", wraplength=1040).pack(anchor="w", pady=(4, 0))
        ttk.Label(panel, text=card.front, style="H2.TLabel", wraplength=1040).pack(anchor="w", pady=(0, 8))
        self.read_aloud_button(panel, card.front, "Read question aloud").pack(anchor="w", pady=(0, 14))
        if self.accessibility.get("read_aloud"):
            self.after(250, lambda: self.speak(card.front))
        self.render_media_controls(panel, card)
        response = self.answer_area(panel, "Your test answer", "Answer here without leaving the testing page.", 5)
        if draft.get("card_id") == card.id and draft.get("context") == self.testing_context:
            response.insert("1.0", draft.get("response", ""))
        result = ttk.Label(panel, text="Smart Check will highlight the suggested bucket.", style="CardMuted.TLabel", wraplength=1040)
        result.pack(anchor="w", pady=(0, 10))
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
            self.read_aloud_button(answer_holder, card.back, "Read answer aloud").pack(anchor="w")
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
            ("Reveal / Hide Answer", "TButton", reveal),
            ("Use Smart Rating", "TButton", smart_rating),
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
            ttk.Label(panel, text="Rate your recall  \u2022  keyboard shortcuts 1-4  \u2022  Ctrl+Z to undo", style="CardMuted.TLabel").pack(anchor="w", pady=(self.px(10), self.px(4)))
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
            undo_button = ttk.Button(secondary, text="Undo last rating (Ctrl+Z)", command=undo_last_rating, state=("normal" if self.store.last_action else "disabled"))
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
        guide = self.card(host, "WarmCard.TFrame", 14)
        guide.pack(fill="x", pady=(0, 12))
        ttk.Label(guide, text="Choose how you want to check yourself", style="WarmH2.TLabel").pack(anchor="w")
        ttk.Label(guide, text="Self Check opens Test Lab for typed recall. Multiple Choice is faster when you want a quick confidence check.", style="WarmCard.TLabel", wraplength=1040).pack(anchor="w", pady=(4, 0))
        mode = ttk.Frame(host, style="Card.TFrame")
        mode.pack(fill="x", pady=(0, 16))
        self_check = ttk.Button(mode, text="Self Check", style="Primary.TButton" if self.quiz_mode == "self" else "TButton", command=lambda: self.set_quiz_mode(host, "self"))
        self_check.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        choices_button = ttk.Button(mode, text="Multiple Choice", style="Primary.TButton" if self.quiz_mode == "choices" else "TButton", command=lambda: self.set_quiz_mode(host, "choices"))
        choices_button.grid(row=0, column=1, sticky="ew")
        self.add_tooltip(self_check, self.action_hint("Self Check"))
        self.add_tooltip(choices_button, self.action_hint("Multiple Choice"))
        mode.columnconfigure(0, weight=1)
        mode.columnconfigure(1, weight=1)

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
        ttk.Label(host, text=card.front, style="H2.TLabel", wraplength=1040).pack(anchor="w", pady=(10, 20))
        self.render_media_controls(host, card)
        if self.quiz_mode == "choices":
            wrong = [item.back for item in self.store.cards if item.id != card.id]
            choices = random.sample(wrong, min(3, len(wrong))) + [card.back]
            random.shuffle(choices)
            for choice in choices:
                ttk.Button(host, text=choice, command=lambda value=choice: self.answer_quiz(host, value, card.back)).pack(fill="x", pady=5)
            return
        ttk.Label(host, text="Self-check uses Test Lab so the answer, reveal, and Smart Check stay on a separate testing page.", style="CardMuted.TLabel", wraplength=1040).pack(anchor="w", pady=(0, 12))
        self.button_row(host, [("Open in Test Lab", lambda: self.open_testing(card, "quiz", "quiz"), "Primary.TButton"), ("Skip / Next", lambda: self.next_self_quiz(host), "TButton")])

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
                    ("Reveal / Hide Answer", "TButton", reveal, "normal"),
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
            os.startfile(target)
        except (AttributeError, OSError):
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

    def view_feedback(self):
        page = ScrollFrame(self.view_host)
        page.pack(fill="both", expand=True)
        draft = self.view_drafts.get("feedback", {})
        summary = self.store.feedback_summary()

        hero = self.hover_card(tk.Frame(page.inner, bg=COLORS["surface"], padx=self.px(28), pady=self.px(26), highlightthickness=1, highlightbackground=COLORS["line"]))
        hero.pack(fill="x", padx=(0, 8), pady=(0, 16))
        tk.Frame(hero, bg=COLORS["green"], width=self.px(42), height=self.px(4)).pack(anchor="w", pady=(0, 14))
        tk.Label(hero, text="Testing feedback", bg=COLORS["surface"], fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 24)).pack(anchor="w")
        tk.Label(hero, text="Use this during real test sessions to collect ratings, bug reports, confusing moments, and accessibility notes.", bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI", 12), wraplength=self.px(1020), justify="left").pack(anchor="w", pady=(6, 0))

        stats = ttk.Frame(page.inner, style="Page.TFrame")
        stats.pack(fill="x", padx=(0, 8), pady=(0, 16))
        stat_items = [
            ("Entries", str(summary["total"]), "tester notes saved locally", COLORS["primary"]),
            ("Average", f"{summary['average']}/5" if summary["average"] else "None", "rated feedback score", COLORS["green"]),
            ("Latest", summary["latest"], "most recent feedback note", COLORS["orange"]),
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
        ttk.Label(form, text="Add tester note", style="H2.TLabel").pack(anchor="w")
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

        self.button_row(form, [("Save Feedback", save_feedback, "Primary.TButton"), ("Export Feedback", self.export_feedback, "TButton")])

        recent = self.card(page.inner, "AltCard.TFrame", 22)
        recent.pack(fill="x", padx=(0, 8))
        ttk.Label(recent, text="Recent feedback", style="AltH2.TLabel").pack(anchor="w")
        if not self.store.feedback:
            ttk.Label(recent, text="No tester notes yet.", style="AltMuted.TLabel").pack(anchor="w", pady=(6, 0))
        for entry in self.store.feedback[:10]:
            item = tk.Frame(recent, bg=COLORS["surface"], padx=self.px(14), pady=self.px(12), highlightthickness=1, highlightbackground=COLORS["soft_line"])
            item.pack(fill="x", pady=(10, 0))
            tk.Label(item, text=f"{entry.rating}/5 | {entry.category} | {entry.page} | {entry.created_at}", bg=COLORS["surface"], fg=COLORS["primary"], font=self.font("Segoe UI Semibold", 10)).pack(anchor="w")
            tk.Label(item, text=entry.note, bg=COLORS["surface"], fg=COLORS["ink"], font=self.font("Segoe UI", 11), wraplength=self.px(1020), justify="left").pack(anchor="w", pady=(4, 0))

        self.register_draft_saver("feedback", lambda: {
            "rating": rating_var.get(),
            "category": category_var.get(),
            "page": page_var.get(),
            "note": note.get("1.0", "end").strip(),
        })

    def view_settings(self):
        page = ScrollFrame(self.view_host)
        page.pack(fill="both", expand=True)

        profile_count = len(list_profiles())
        due = len(self.store.due_cards())
        storage_path = str(app_paths.DATA_DIR)
        profile_path = str(self.store.data_file)
        attachment_path = str(self.store.attachment_dir)

        hero = self.hover_card(tk.Frame(page.inner, bg=COLORS["surface"], padx=self.px(28), pady=self.px(26), highlightthickness=1, highlightbackground=COLORS["line"]))
        hero.pack(fill="x", padx=(0, 8), pady=(0, 16))
        tk.Frame(hero, bg=COLORS["violet"], width=self.px(42), height=self.px(4)).pack(anchor="w", pady=(0, 14))
        tk.Label(hero, text="Make MemoryPal yours", bg=COLORS["surface"], fg=COLORS["ink"], font=self.font("Segoe UI Semibold", 24)).pack(anchor="w")
        self.fit_wrap(tk.Label(hero, text="Adjust the way the app looks, how it opens, where data is kept, and which profile is active.", bg=COLORS["surface"], fg=COLORS["muted"], font=self.font("Segoe UI", 12), wraplength=self.px(1020), justify="left"), pady=(6, 0))

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
                ("Light mode" if self.theme == "dark" else "Dark mode", self.toggle_theme, "Primary.TButton"),
            ],
        )

        window_card = self.card(grid, "AltCard.TFrame", 22)
        window_card.grid(row=0, column=1, sticky="nsew", pady=(0, 12))
        ttk.Label(window_card, text="Window", style="AltH2.TLabel").pack(anchor="w")
        self.fit_wrap(ttk.Label(window_card, text="F11 uses true fullscreen. The titlebar square uses borderless focus mode.", style="AltMuted.TLabel", wraplength=self.px(500)), pady=(4, 12))
        state_row = tk.Frame(window_card, bg=COLORS["alt"])
        state_row.pack(fill="x", pady=(0, 12))
        self.render_status_chip(state_row, "True fullscreen on" if self.is_fullscreen else "True fullscreen off", COLORS["green"] if self.is_fullscreen else COLORS["surface"], COLORS["white"] if self.is_fullscreen else COLORS["muted"])
        self.render_status_chip(state_row, "Focus window on" if self.is_focus_window else "Focus window off", COLORS["primary"] if self.is_focus_window else COLORS["surface"], COLORS["white"] if self.is_focus_window else COLORS["muted"])
        self.button_row(
            window_card,
            [
                ("True Fullscreen", self.toggle_true_fullscreen, "Primary.TButton"),
                ("Focus Window", self.toggle_focus_window, "TButton"),
            ],
            "AltCard.TFrame",
        )

        profile_card = self.card(grid, "Card.TFrame", 22)
        profile_card.grid(row=1, column=0, sticky="nsew", padx=(0, 12))
        ttk.Label(profile_card, text="Profiles", style="H2.TLabel").pack(anchor="w")
        self.fit_wrap(ttk.Label(profile_card, text=f"Active profile: {active_profile_name()} | {profile_count} profile{'s' if profile_count != 1 else ''} on this PC.", style="CardMuted.TLabel", wraplength=self.px(500)), pady=(4, 12))
        self.button_row(profile_card, [("Manage Profiles", self.open_profile_manager, "Primary.TButton"), ("Edit Daily Goal", self.edit_daily_goal, "TButton")])

        study_card = self.card(grid, "WarmCard.TFrame", 22)
        study_card.grid(row=1, column=1, sticky="nsew")
        ttk.Label(study_card, text="Study Defaults", style="WarmH2.TLabel").pack(anchor="w")
        self.fit_wrap(ttk.Label(study_card, text=f"Daily goal: {self.store.daily_goal} cards. Due now: {due}. Cards and captures stay local unless exported.", style="WarmCard.TLabel", wraplength=self.px(500)), pady=(4, 12))
        self.button_row(study_card, [("Start Due Review", lambda: self.show_view("review"), "Primary.TButton"), ("Open in Test Lab", lambda: self.open_testing(return_view="settings", context="study"), "TButton")], "WarmCard.TFrame")

        accessibility_card = self.card(grid, "AltCard.TFrame", 22)
        accessibility_card.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(0, 12))
        ttk.Label(accessibility_card, text="Accessibility", style="AltH2.TLabel").pack(anchor="w")
        self.fit_wrap(ttk.Label(
            accessibility_card,
            text="Tune MemoryPal for larger text, steadier screens, clearer contrast, and caregiver-supported use. These settings are saved to this profile.",
            style="AltMuted.TLabel",
            wraplength=self.px(1040),
            justify="left",
        ), pady=(4, 12))
        text_size = tk.StringVar(value=self.accessibility.get("text_size", "Comfort"))
        ttk.Label(accessibility_card, text="Text size", style="AltMuted.TLabel").pack(anchor="w")
        self.select_button(
            accessibility_card,
            text_size,
            ["Comfort", "Large", "Extra Large"],
            on_change=lambda value: self.update_accessibility_preference("text_size", value),
        ).pack(fill="x", pady=(self.px(4), self.px(12)))
        toggle_grid = tk.Frame(accessibility_card, bg=COLORS["alt"])
        toggle_grid.pack(fill="x", pady=(0, self.px(12)))
        accessibility_toggles = [
            ("high_contrast", "Higher contrast text and borders"),
            ("reduce_motion", "Reduce fades and motion"),
            ("simple_language", "Use simpler wording where available"),
            ("caregiver_mode", "Caregiver mode: hide Reset so shared data can't be wiped"),
            ("read_aloud", "Read questions and answers aloud automatically"),
            ("more_time", "More time: slower timed games, messages, and speech"),
            ("focus_outline", "Show a bright outline on the focused button (keyboard use)"),
        ]
        for index, (key, label) in enumerate(accessibility_toggles):
            var = tk.BooleanVar(value=bool(self.accessibility.get(key)))
            row = self.check_toggle(toggle_grid, var, label, on_change=lambda checked, pref=key: self.update_accessibility_preference(pref, checked), bg=COLORS["alt"], wraplength=470, fit=True)
            row.grid(row=index // 2, column=index % 2, sticky="ew", padx=(0 if index % 2 == 0 else self.px(12), 0), pady=(0 if index < 2 else self.px(8), 0))
            toggle_grid.columnconfigure(index % 2, weight=1, uniform="toggles")
        self.button_row(
            accessibility_card,
            [
                ("Use Senior Layout", self.apply_senior_layout_defaults, "Primary.TButton"),
                ("Everyday Memory", lambda: self.show_view("elder"), "TButton"),
                ("Open Feedback", lambda: self.show_view("feedback"), "TButton"),
            ],
            "AltCard.TFrame",
        )

        welcome_card = self.card(page.inner, "Card.TFrame", 22)
        welcome_card.pack(fill="x", padx=(0, 8), pady=(0, 16))
        ttk.Label(welcome_card, text="Welcome & tour", style="H2.TLabel").pack(anchor="w")
        chosen = self.store.onboarding.get("persona")
        persona_title = onboarding.persona(chosen)["title"] if chosen else "Not chosen yet"
        ttk.Label(welcome_card, text=f"Set up for: {persona_title}. Answer the welcome questions again to change the menu order and comfort settings, or replay the guided tour (also the ? button at the top).", style="CardMuted.TLabel", wraplength=self.px(1040)).pack(anchor="w", pady=(4, 12))
        self.button_row(welcome_card, [("Replay Tour", self.start_tour, "Primary.TButton"), ("Redo Welcome Questions", lambda: self.show_view("welcome"), "TButton")])

        nav_card = self.card(page.inner, "AltCard.TFrame", 22)
        nav_card.pack(fill="x", padx=(0, 8), pady=(0, 16))
        ttk.Label(nav_card, text="Page Order", style="AltH2.TLabel").pack(anchor="w")
        self.fit_wrap(ttk.Label(nav_card, text="Move pages up or down to make the left navigation fit the way this profile studies. Settings stays pinned at the bottom.", style="AltMuted.TLabel", wraplength=self.px(1040)), pady=(4, 12))
        nav_order = [key for key, _label, _short in self.ordered_nav_items()]
        nav_labels = {key: label for key, label, _short in self.default_nav_items()}
        order_row = tk.Frame(nav_card, bg=COLORS["alt"])
        order_row.pack(fill="x", pady=(0, self.px(12)))
        listbox = tk.Listbox(
            order_row,
            height=8,
            bg=COLORS["input"],
            fg=COLORS["ink"],
            selectbackground=COLORS["primary"],
            selectforeground=COLORS["white"],
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
            self.toast_message("Navigation order saved.")

        def reset_nav_order():
            nav_order[:] = [key for key, _label, _short in self.default_nav_items()]
            self.set_nav_order(nav_order)
            self.render_navigation_rail()
            render_nav_order()
            self.toast_message("Navigation order reset.")

        render_nav_order()
        self.button_row(
            nav_card,
            [
                ("Move Up", lambda: move_nav(-1), "TButton"),
                ("Move Down", lambda: move_nav(1), "TButton"),
                ("Apply Order", apply_nav_order, "Primary.TButton"),
                ("Reset Order", reset_nav_order, "TButton"),
            ],
            "AltCard.TFrame",
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
            row = tk.Frame(storage, bg=COLORS["alt"], padx=self.px(14), pady=self.px(10))
            row.pack(fill="x", pady=(0, 8))
            tk.Label(row, text=label, bg=COLORS["alt"], fg=COLORS["primary"], font=self.font("Segoe UI Semibold", 11), width=14, anchor="w").pack(side="left", padx=(0, self.px(12)))
            value_label = tk.Label(row, text=value, bg=COLORS["alt"], fg=COLORS["ink"], font=self.font("Segoe UI", 10), wraplength=self.px(850), justify="left", anchor="w")
            value_label.pack(side="left", fill="x", expand=True)
            self.bind_rewrap(value_label)
        self.button_row(
            storage,
            [
                ("Open Data Folder", self.open_data_folder, "Primary.TButton"),
                ("Export Backup", self.export_data, "TButton"),
                ("Import Backup", self.import_data, "TButton"),
            ] + ([] if self.accessibility.get("caregiver_mode") else [("Reset", self.reset_data, "Danger.TButton")]),
        )

        comfort = self.card(page.inner, "AltCard.TFrame", 22)
        comfort.pack(fill="x", padx=(0, 8))
        ttk.Label(comfort, text="Comfort Notes", style="AltH2.TLabel").pack(anchor="w")
        self.fit_wrap(ttk.Label(comfort, text="Use focus mode when the rail feels distracting, true fullscreen for presentations or testing, and profiles when different people use the same computer.", style="AltCard.TLabel", wraplength=self.px(1040), justify="left"), pady=(4, 0))

    def view_library(self):
        tools = ttk.Frame(self.view_host, style="Page.TFrame")
        tools.pack(fill="x", pady=(0, 12))
        if self.deck_filter:
            filter_row = tk.Frame(tools, bg=COLORS["alt"], padx=self.px(14), pady=self.px(8))
            filter_row.pack(fill="x", pady=(0, 10))
            tk.Label(filter_row, text=f"Filtered to deck: {self.deck_filter}", bg=COLORS["alt"], fg=COLORS["primary"], font=self.font("Segoe UI Semibold", 11)).pack(side="left")
            ttk.Button(filter_row, text="Clear filter", command=self.clear_deck_filter).pack(side="right")
        search_var = tk.StringVar()
        filter_var = tk.StringVar(value="All")
        top = ttk.Frame(tools, style="Page.TFrame")
        top.pack(fill="x", pady=(0, 10))
        ttk.Entry(top, textvariable=search_var).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.select_button(top, filter_var, ["All", "Due", "Weak", "Captures"], on_change=lambda _value: render(), width=10).grid(row=0, column=1, sticky="ew", padx=(0, 8))
        ttk.Button(top, text="Apply", command=lambda: render()).grid(row=0, column=2, sticky="ew")
        top.columnconfigure(0, weight=3)
        top.columnconfigure(1, weight=1)
        self.button_row(tools, [("Add Samples", lambda: self.store.add_cards(sample_cards()) or self.show_view("library"), "Primary.TButton"), ("Import", self.import_data, "TButton"), ("Export", self.export_data, "TButton")] + ([] if self.accessibility.get("caregiver_mode") else [("Reset", self.reset_data, "Danger.TButton")]), "Page.TFrame")
        page = ScrollFrame(self.view_host)
        page.pack(fill="both", expand=True)

        def matches(text):
            query = normalize_space(search_var.get()).lower()
            return not query or query in text.lower()

        def render():
            for child in page.inner.winfo_children():
                child.destroy()
            mode = filter_var.get()
            shown = 0
            if mode in ("All", "Captures"):
                for capture in self.store.captures:
                    chunks = capture.chunks or split_study_bits(capture.notes)
                    searchable = " ".join([capture.title, capture.notes, " ".join(chunks)])
                    if not matches(searchable):
                        continue
                    item = self.card(page.inner)
                    item.pack(fill="x", padx=(0, 8), pady=(0, 10))
                    ttk.Label(item, text=f"Capture | {capture.created_at}", style="CardMuted.TLabel").pack(anchor="w")
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
                    item = self.card(page.inner)
                    item.pack(fill="x", padx=(0, 8), pady=(0, 10))
                    status_line = f"{card.deck} | Next: {card.next_review} | {card.last_result} {card.last_score}%"
                    if card.buried_until > today_iso():
                        status_line += f"  \u2022  Buried until {card.buried_until}"
                    ttk.Label(item, text=status_line, style="CardMuted.TLabel").pack(anchor="w")
                    if self.store.is_leech(card):
                        tk.Label(item, text=f"\u26a0 Leech \u2014 missed {card.lapses}x, consider rewriting this card", bg=COLORS["again_bg"], fg=COLORS["again_fg"], font=self.font("Segoe UI Semibold", 10), padx=self.px(8), pady=self.px(3)).pack(anchor="w", pady=(4, 0))
                    ttk.Label(item, text=card.front, style="H2.TLabel", wraplength=1060).pack(anchor="w", pady=(6, 5))
                    ttk.Label(item, text=card.back, style="Card.TLabel", wraplength=1080).pack(anchor="w")
                    ttk.Label(item, text=f"Path: {card.pathway or 'Not set'}", style="CardMuted.TLabel").pack(anchor="w", pady=(8, 0))
                    self.render_media_controls(item, card)
                    shown += 1
            if shown == 0:
                ttk.Label(page.inner, text="No matching material.", style="Muted.TLabel").pack(anchor="w")

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
            self.store.cards = load_items(raw.get("cards", []), Card.from_dict)
            self.store.captures = load_items(raw.get("captures", []), Capture.from_dict)
            self.store.practiced = safe_int(raw.get("practiced", 0), 0)
            self.store.activity = dict(raw.get("activity", {}))
            self.store.daily_goal = safe_int(raw.get("daily_goal", 15), 15)
            self.store.nav_order = list(raw.get("nav_order", []))
            self.store.accessibility = normalize_accessibility(raw.get("accessibility", {}))
            self.store.feedback = load_items(raw.get("feedback", []), FeedbackEntry.from_dict)
            self.store.save(merge_existing=False)
            self.accessibility = normalize_accessibility(self.store.accessibility)
            self.apply_accessibility_preferences()
            self.show_view("library")
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            self.dialog_alert("Import failed", str(exc), "error")

    def reset_data(self):
        if self.dialog_confirm("Reset MemoryPal", "Clear local data and restore sample cards?", "Reset", destructive=True):
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
