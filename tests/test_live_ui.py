from skyblock_monitor.bot import account_keyboard, live_keyboard, main_keyboard


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
