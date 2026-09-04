from datetime import UTC, datetime, timedelta

from skyblock_monitor.models import Snapshot
from skyblock_monitor.store import Store


def snap(account_id: int, at: datetime, mining_xp: float = 1_000) -> Snapshot:
    return Snapshot(account_id, at, mining_xp, 30, 50_000, 4, 10, 200, 30, 0, 1_000, 50)


def test_presence_reconnect_inside_grace_keeps_one_session(tmp_path):
    store = Store(tmp_path / "bot.db")
    account = store.add_account(7, "Hunter_sssss", "u", "Grapes")
    started = datetime(2026, 9, 4, 10, tzinfo=UTC)

    first = store.record_presence(account.id, True, started)
    store.record_presence(account.id, False, started + timedelta(minutes=10))
    resumed = store.record_presence(account.id, True, started + timedelta(minutes=25))

    assert resumed.id == first.id
    assert resumed.started_at == started
    assert resumed.ended_at is None
    assert resumed.offline_since is None
    assert len(store.list_sessions(7)) == 1


def test_presence_closes_session_after_thirty_offline_minutes(tmp_path):
    store = Store(tmp_path / "bot.db")
    account = store.add_account(7, "VenomKillerIRL", "u", "Papaya")
    started = datetime(2026, 9, 4, 10, tzinfo=UTC)
    offline = started + timedelta(hours=1)

    session = store.record_presence(account.id, True, started)
    store.record_presence(account.id, False, offline)
    closed = store.record_presence(account.id, False, offline + timedelta(minutes=30))

    assert closed.id == session.id
    assert closed.ended_at == offline
    assert closed.offline_since == offline
    assert store.active_session(account.id) is None


def test_return_after_grace_starts_a_new_session(tmp_path):
    store = Store(tmp_path / "bot.db")
    account = store.add_account(7, "VenomKillerIRL", "u", "Papaya")
    started = datetime(2026, 9, 4, 10, tzinfo=UTC)
    offline = started + timedelta(hours=1)
    first = store.record_presence(account.id, True, started)
    store.record_presence(account.id, False, offline)

    second = store.record_presence(account.id, True, offline + timedelta(minutes=31))

    assert second.id != first.id
    assert second.started_at == offline + timedelta(minutes=31)
    sessions = store.list_sessions(7)
    assert sessions[1].ended_at == offline


def test_sessions_are_scoped_to_telegram_owner(tmp_path):
    store = Store(tmp_path / "bot.db")
    mine = store.add_account(7, "Hunter_sssss", "u", "Grapes")
    other = store.add_account(8, "Other", "o", "Apple")
    now = datetime(2026, 9, 4, 10, tzinfo=UTC)
    store.record_presence(mine.id, True, now)
    store.record_presence(other.id, True, now)

    sessions = store.list_sessions(7)

    assert [session.account_id for session in sessions] == [mine.id]


def test_live_report_uses_single_fixed_baseline_snapshot(tmp_path):
    store = Store(tmp_path / "bot.db")
    account = store.add_account(7, "Hunter_sssss", "u", "Grapes")
    now = datetime(2026, 9, 4, 10, tzinfo=UTC)
    store.save_snapshot(snap(account.id, now, 5_000))

    report = store.live_report(account.id, now, now + timedelta(seconds=1))

    assert report is not None
    assert report.start == report.end
    assert report.mining_xp == 0


def test_starting_live_view_replaces_previous_view_for_user(tmp_path):
    store = Store(tmp_path / "bot.db")
    now = datetime(2026, 9, 4, 10, tzinfo=UTC)

    first = store.start_live_view(7, 100, 200, 0, now)
    second = store.start_live_view(7, 100, 201, 0, now + timedelta(minutes=1))

    assert first.id != second.id
    assert [view.id for view in store.list_active_live_views()] == [second.id]
    assert store.get_live_view(second.id, 7).message_id == 201
    store.stop_live_view(second.id, 7)
    assert store.list_active_live_views() == []
