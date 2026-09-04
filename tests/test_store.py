from datetime import UTC, datetime, timedelta

from skyblock_monitor.models import Snapshot
from skyblock_monitor.store import Store


def snap(at: datetime, *, mining_xp: float, commissions: int, powder: int, purse: float) -> Snapshot:
    return Snapshot(
        account_id=1,
        observed_at=at,
        mining_xp=mining_xp,
        mining_level=29,
        hotm_xp=77_270,
        hotm_level=4,
        commissions=commissions,
        mithril_powder=powder,
        gemstone_powder=1_983,
        glacite_powder=0,
        purse=purse,
        skyblock_level=55,
    )


def test_custom_period_uses_first_and_last_snapshots_inside_range(tmp_path):
    store = Store(tmp_path / "bot.db")
    account = store.add_account(telegram_user_id=7, username="Hunter_sssss", uuid="u", profile_name="Grapes")
    start = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)
    store.save_snapshot(snap(start - timedelta(minutes=1), mining_xp=900, commissions=99, powder=90, purse=900))
    store.save_snapshot(snap(start, mining_xp=1_000, commissions=100, powder=100, purse=1_000))
    store.save_snapshot(snap(start + timedelta(minutes=30), mining_xp=2_500, commissions=102, powder=160, purse=1_300))
    store.save_snapshot(snap(start + timedelta(hours=1, minutes=1), mining_xp=5_000, commissions=106, powder=300, purse=2_000))

    report = store.period_report(account.id, start, start + timedelta(hours=1))

    assert report is not None
    assert report.mining_xp == 1_500
    assert report.commissions == 2
    assert report.mithril_powder == 60
    assert report.purse == 300


def test_account_names_are_case_insensitive_and_unique_per_user(tmp_path):
    store = Store(tmp_path / "bot.db")
    first = store.add_account(telegram_user_id=7, username="Hunter_sssss", uuid="u", profile_name="Grapes")
    second = store.add_account(telegram_user_id=7, username="hunter_SSSSS", uuid="u", profile_name="Grapes")

    assert second.id == first.id
    assert len(store.list_accounts(7)) == 1


def test_delete_account_hides_it_from_monitoring(tmp_path):
    store = Store(tmp_path / "bot.db")
    account = store.add_account(telegram_user_id=7, username="VenomKillerIRL", uuid="v", profile_name="Papaya")

    store.delete_account(account.id, telegram_user_id=7)

    assert store.list_accounts(7) == []


def test_get_account_enforces_owner_and_latest_snapshot(tmp_path):
    store = Store(tmp_path / "bot.db")
    account = store.add_account(telegram_user_id=7, username="VenomKillerIRL", uuid="v", profile_name="Papaya")
    now = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)
    store.save_snapshot(snap(now, mining_xp=12_000, commissions=10, powder=30, purse=40))

    assert store.get_account(account.id, 7) == account
    assert store.get_account(account.id, 8) is None
    assert store.latest_snapshot(account.id).mining_xp == 12_000
