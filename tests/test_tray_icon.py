import pytest

from brownout_buddy.models import TrayState

pytest.importorskip("PIL")

from brownout_buddy.tray import ICON_COLORS, draw_icon  # noqa: E402


def test_icon_colors_match_the_tray_state():
    for state, color in ICON_COLORS.items():
        image = draw_icon(state)
        assert image.getpixel((32, 8)) == color


def test_offline_wins_over_battery_in_the_icon_map():
    assert TrayState.OFFLINE in ICON_COLORS
    assert ICON_COLORS[TrayState.OFFLINE] != ICON_COLORS[TrayState.ON_BATTERY]
