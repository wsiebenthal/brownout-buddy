"""Menu-bar / system-tray icon.

The icon is green (normal), amber (on battery), red (offline), or gray
(paused). Offline wins over on-battery when both are true. The menu has
status, recent outages, pause, settings, the brownout-or-unplugged
question, and quit.

Settings and the question are stubs. A missing display, or missing
``pystray`` / Pillow, raises :class:`TrayUnavailable` so the caller can
run headless instead.
"""

from __future__ import annotations

import sys

from brownout_buddy.classifier.prompt import StubConfirmationPrompt
from brownout_buddy.models import TrayState
from brownout_buddy.monitor import Monitor

ICON_COLORS = {
    TrayState.NORMAL: (46, 125, 50, 255),
    TrayState.ON_BATTERY: (249, 168, 37, 255),
    TrayState.OFFLINE: (198, 40, 40, 255),
    TrayState.PAUSED: (97, 97, 97, 255),
}


class TrayUnavailable(Exception):
    """The tray icon cannot be shown in this process."""


def draw_icon(state: TrayState, size: int = 64):
    """Draw a colored circle. Requires Pillow."""

    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:
        raise TrayUnavailable(
            "Tray icons need Pillow. Install them with: pip install 'brownout-buddy[tray]'"
        ) from exc
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((4, 4, size - 5, size - 5), fill=ICON_COLORS[state])
    return image


def run_tray(monitor: Monitor, stop, interval: float) -> None:
    """Block on the tray event loop until quit. ``stop`` is a ``threading.Event``."""

    try:
        import pystray
    except Exception as exc:
        # pystray raises ValueError when the desktop toolkit (GTK, AppKit,
        # Win32) is missing, not only ImportError when the package is absent.
        raise TrayUnavailable(
            "Tray support needs pystray, Pillow, and a desktop toolkit. "
            f"The tray could not be loaded ({exc}). "
            "Install the extra with: pip install 'brownout-buddy[tray]'"
        ) from exc

    icon_holder: dict[str, object] = {}

    def refresh(icon) -> None:
        icon.icon = draw_icon(monitor.tray)
        icon.title = f"Brownout Buddy ({monitor.tray.value})"

    def loop(icon) -> None:
        icon.visible = True
        while not stop.is_set():
            result = monitor.poll()
            refresh(icon)
            if result.actions:
                for action in result.actions:
                    print(
                        f"action {action.name}: {action.status}: {action.message}",
                        file=sys.stderr,
                    )
            if stop.wait(interval):
                break
        icon.stop()

    def toggle_pause(icon, _item) -> None:
        monitor.set_paused(not monitor.paused)
        refresh(icon)

    def settings(_icon, _item) -> None:
        path = monitor.config.config_path
        where = str(path) if path else "built-in defaults (run init-config to write a file)"
        print(
            "Settings window is not implemented yet. Edit the config file: " + where,
            file=sys.stderr,
        )

    def ask(_icon, _item) -> None:
        pending = monitor.pending_question()
        if pending is None:
            print(
                "No low-confidence power loss is waiting for an answer.",
                file=sys.stderr,
            )
            return
        classification, ids = pending
        print(StubConfirmationPrompt().menu_text(classification, ids), file=sys.stderr)

    def recent_menu():
        rows = monitor.recent(limit=5)
        if not rows:
            return (pystray.MenuItem("(no outages yet)", None, enabled=False),)
        items = []
        for record in rows:
            label = record.label or "unlabeled"
            text = f"#{record.id} {record.type.value} {label}"
            items.append(pystray.MenuItem(text, None, enabled=False))
        return tuple(items)

    def quit_app(icon, _item) -> None:
        stop.set()
        icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem(lambda _item: f"Status: {monitor.tray.value}", None, enabled=False),
        pystray.MenuItem("Recent outages", pystray.Menu(recent_menu)),
        pystray.MenuItem(
            "Pause monitoring",
            toggle_pause,
            checked=lambda _item: monitor.paused,
        ),
        pystray.MenuItem("Brownout or unplugged?", ask),
        pystray.MenuItem("Settings", settings),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", quit_app),
    )
    icon = pystray.Icon(
        "brownout-buddy",
        draw_icon(monitor.tray),
        "Brownout Buddy",
        menu,
    )
    icon_holder["icon"] = icon
    icon.run(setup=loop)


def graphical_session() -> bool:
    """Best-effort check. Windows and macOS are assumed to have a session."""

    import os

    if os.name == "nt" or sys.platform == "darwin":
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
