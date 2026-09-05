import asyncio
from datetime import UTC, datetime

import pytest

import skyblock_monitor.bot as bot_module
from skyblock_monitor.bot import (
    account_keyboard,
    all_accounts_keyboard,
    is_message_not_modified,
    live_caption,
    live_keyboard,
    main_keyboard,
    report_keyboard,
)
from skyblock_monitor.models import LiveView


def callback_values(keyboard) -> set[str]:
    return {button.callback_data for row in keyboard.inline_keyboard for button in row if button.callback_data}


def test_main_menu_exposes_live_and_session_history():
    callbacks = callback_values(main_keyboard())
    assert "live:0" in callbacks
    assert "sessions" in callbacks


def test_account_menu_can_start_account_only_live_view():
    assert "live:42" in callback_values(account_keyboard(42))


def test_live_screen_can_be_stopped_without_new_message():
    keyboard = live_keyboard(9)
    assert "live-stop:9" in callback_values(keyboard)


def test_live_screen_has_page_buttons_for_more_than_four_accounts():
    keyboard = live_keyboard(9, page=0, page_count=2)

    assert "live-page:9:1" in callback_values(keyboard)
    assert "live-page:9:0" not in callback_values(keyboard)


def test_period_report_has_in_place_card_pagination():
    keyboard = report_keyboard(all_accounts_keyboard(), "report-page:0:1h", page=0, page_count=2)

    assert "report-page:0:1h:1" in callback_values(keyboard)
    assert "report-page:0:1h:0" not in callback_values(keyboard)
    assert "period:0:1h" in callback_values(keyboard)


def test_live_caption_shows_refresh_time():
    view = LiveView(1, 7, 100, 200, 0, datetime(2026, 9, 4, 19, 10, tzinfo=UTC))
    now = datetime(2026, 9, 4, 19, 12, tzinfo=UTC)

    assert "обновлено 04.09 22:12 МСК" in live_caption(view, now, live=True)
    assert "Обновление каждые 4 минуты" in live_caption(view, now, live=True)


def test_poll_cycle_refreshes_live_view_after_snapshots(monkeypatch):
    view = LiveView(1, 7, 100, 200, 0, datetime(2026, 9, 4, 19, 10, tzinfo=UTC))
    refreshed = []

    class FakeStore:
        @staticmethod
        def list_accounts():
            return []

        @staticmethod
        def list_active_live_views():
            return [view]

    class StopPolling(Exception):
        pass

    async def fake_update(_bot, active_view):
        refreshed.append(active_view.id)

    async def stop_sleep(_seconds):
        raise StopPolling

    monkeypatch.setattr(bot_module, "store", FakeStore(), raising=False)
    monkeypatch.setattr(bot_module, "update_live_message", fake_update)
    monkeypatch.setattr(bot_module.asyncio, "sleep", stop_sleep)

    with pytest.raises(StopPolling):
        asyncio.run(bot_module.poll_forever(object()))

    assert refreshed == [view.id]


def test_not_modified_error_does_not_end_live_view():
    assert is_message_not_modified(RuntimeError("Bad Request: message is not modified")) is True
    assert is_message_not_modified(RuntimeError("Bad Request: message to edit not found")) is False
