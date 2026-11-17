"""Windows power events from ``WM_POWERBROADCAST``.

Polling ``GetSystemPowerStatus`` can miss a short unplug between samples.
Windows also sends ``WM_POWERBROADCAST`` to top-level windows when the AC
line changes and around sleep and wake. This module decodes those messages
and runs a small hidden window on a background thread to receive them.

The decoder is pure so it is tested on every OS. The listener only runs on
Windows. Sleep and wake are reported separately so the tracker can avoid
logging a new outage just because the laptop was suspended.
"""

from __future__ import annotations

import enum
import sys
import threading
from typing import Callable

WM_POWERBROADCAST = 0x0218

PBT_APMSUSPEND = 0x0004
PBT_APMRESUMESUSPEND = 0x0007
PBT_APMPOWERSTATUSCHANGE = 0x000A
PBT_APMRESUMEAUTOMATIC = 0x0012
PBT_POWERSETTINGCHANGE = 0x8013


class PowerEvent(str, enum.Enum):
    STATUS_CHANGE = "status-change"
    SUSPEND = "suspend"
    RESUME = "resume"
    SETTING_CHANGE = "setting-change"


_EVENTS = {
    PBT_APMPOWERSTATUSCHANGE: PowerEvent.STATUS_CHANGE,
    PBT_APMSUSPEND: PowerEvent.SUSPEND,
    PBT_APMRESUMESUSPEND: PowerEvent.RESUME,
    PBT_APMRESUMEAUTOMATIC: PowerEvent.RESUME,
    PBT_POWERSETTINGCHANGE: PowerEvent.SETTING_CHANGE,
}


def decode_power_broadcast(wparam: int) -> PowerEvent | None:
    """Return the event for a ``WM_POWERBROADCAST`` wParam, or ``None``.

    Old APM codes that Windows no longer sends (battery low, query suspend)
    return ``None`` so callers can ignore them.
    """

    return _EVENTS.get(int(wparam))


class WindowsPowerListener:  # pragma: no cover - Windows only
    """Hidden window that calls ``callback`` for each decoded power event.

    ``start()`` returns once the window exists. ``stop()`` posts WM_CLOSE
    and waits for the thread. The callback runs on the listener thread, so
    keep it short (for example, push to a queue the monitor reads).
    """

    def __init__(self, callback: Callable[[PowerEvent], None]) -> None:
        if sys.platform != "win32":
            raise RuntimeError("WindowsPowerListener only runs on Windows")
        self._callback = callback
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._hwnd = None
        self._error: BaseException | None = None

    def start(self, timeout: float = 5.0) -> None:
        self._thread = threading.Thread(
            target=self._run, name="brownout-power-events", daemon=True
        )
        self._thread.start()
        if not self._ready.wait(timeout):
            raise RuntimeError("power listener window did not start in time")
        if self._error is not None:
            raise RuntimeError("power listener failed to start") from self._error

    def stop(self, timeout: float = 5.0) -> None:
        import ctypes
        from ctypes import wintypes

        if self._hwnd:
            post = ctypes.windll.user32.PostMessageW
            post.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
            post(self._hwnd, 0x0010, 0, 0)  # WM_CLOSE
        if self._thread is not None:
            self._thread.join(timeout)
        self._thread = None
        self._hwnd = None

    def _run(self) -> None:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        LRESULT = ctypes.c_ssize_t
        WNDPROC = ctypes.WINFUNCTYPE(
            LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
        )

        class WNDCLASSW(ctypes.Structure):
            _fields_ = [
                ("style", wintypes.UINT),
                ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int),
                ("hInstance", wintypes.HINSTANCE),
                ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HANDLE),
                ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR),
                ("lpszClassName", wintypes.LPCWSTR),
            ]

        user32.DefWindowProcW.restype = LRESULT
        user32.DefWindowProcW.argtypes = [
            wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
        ]
        user32.CreateWindowExW.restype = wintypes.HWND
        user32.CreateWindowExW.argtypes = [
            wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
        ]
        kernel32.GetModuleHandleW.restype = wintypes.HMODULE
        user32.UnregisterClassW.argtypes = [wintypes.LPCWSTR, wintypes.HINSTANCE]

        def wndproc(hwnd, msg, wparam, lparam):
            if msg == WM_POWERBROADCAST:
                event = decode_power_broadcast(wparam)
                if event is not None:
                    try:
                        self._callback(event)
                    except Exception:
                        pass
                return 1  # TRUE
            if msg == 0x0010:  # WM_CLOSE
                user32.DestroyWindow(hwnd)
                return 0
            if msg == 0x0002:  # WM_DESTROY
                user32.PostQuitMessage(0)
                return 0
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        self._wndproc = WNDPROC(wndproc)  # keep a reference alive
        hinst = kernel32.GetModuleHandleW(None)
        class_name = f"BrownoutBuddyPower{id(self)}"
        wc = WNDCLASSW()
        wc.lpfnWndProc = self._wndproc
        wc.hInstance = hinst
        wc.lpszClassName = class_name
        try:
            if not user32.RegisterClassW(ctypes.byref(wc)):
                raise ctypes.WinError(ctypes.get_last_error())
            # A normal hidden top-level window, not HWND_MESSAGE: message-only
            # windows do not receive WM_POWERBROADCAST.
            hwnd = user32.CreateWindowExW(
                0, class_name, "Brownout Buddy power", 0,
                0, 0, 0, 0, None, None, hinst, None,
            )
            if not hwnd:
                raise ctypes.WinError(ctypes.get_last_error())
        except BaseException as exc:
            self._error = exc
            self._ready.set()
            return

        self._hwnd = hwnd
        self._ready.set()
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        user32.UnregisterClassW(class_name, hinst)