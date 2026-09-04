from datetime import UTC, datetime
from io import BytesIO

from PIL import Image

from skyblock_monitor.cards import render_progress_card
from skyblock_monitor.models import Account, PeriodReport, Snapshot


def report(account_id: int, *, mining: float, commissions: int, powder: int) -> PeriodReport:
    start = Snapshot(account_id, datetime(2026, 9, 4, 12, tzinfo=UTC), 1_000, 29, 60_000, 4, 100, 200, 10, 0, 1_000, 55)
    end = Snapshot(account_id, datetime(2026, 9, 4, 13, tzinfo=UTC), 1_000 + mining, 30, 61_000, 4, 100 + commissions, 200 + powder, 10, 0, 2_000, 55)
    return PeriodReport(start, end, mining, commissions, powder, 0, 0, 1_000)


def test_renders_one_account_as_shareable_png():
    account = Account(1, 7, "VenomKillerIRL", "uuid", "Papaya")

    result = render_progress_card([(account, report(1, mining=25_000, commissions=0, powder=500))])
    image = Image.open(BytesIO(result))

    assert image.format == "PNG"
    assert image.width == 1200
    assert image.height >= 700


def test_renders_all_accounts_on_one_image():
    accounts = [
        (Account(1, 7, "VenomKillerIRL", "v", "Papaya"), report(1, mining=25_000, commissions=0, powder=500)),
        (Account(2, 7, "Hunter_sssss", "h", "Grapes"), report(2, mining=15_000, commissions=4, powder=300)),
    ]

    image = Image.open(BytesIO(render_progress_card(accounts)))

    assert image.width == 1200
    assert image.height >= 1_100
