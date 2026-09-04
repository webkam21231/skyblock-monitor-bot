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


def test_background_has_visible_skyblock_cavern_color():
    account = Account(1, 7, "VenomKillerIRL", "uuid", "Papaya")
    image = Image.open(BytesIO(render_progress_card([(account, report(1, mining=25_000, commissions=2, powder=500))])))

    saturated = sum(
        1 for red, green, blue in image.get_flattened_data() if max(red, green, blue) - min(red, green, blue) >= 45
    )
    assert saturated / (image.width * image.height) >= 0.08


def test_background_contains_stone_walls():
    account = Account(1, 7, "VenomKillerIRL", "uuid", "Papaya")
    image = Image.open(BytesIO(render_progress_card([(account, report(1, mining=25_000, commissions=2, powder=500))])))

    stone_pixels = sum(1 for pixel in image.get_flattened_data() if pixel in {(20, 37, 50), (26, 45, 58), (17, 34, 46)})
    assert stone_pixels >= 5_000


def test_header_has_pickaxe_icon():
    account = Account(1, 7, "VenomKillerIRL", "uuid", "Papaya")
    image = Image.open(BytesIO(render_progress_card([(account, report(1, mining=25_000, commissions=2, powder=500))])))
    icon = image.crop((75, 68, 180, 178))

    handle_pixels = sum(1 for red, green, blue in icon.get_flattened_data() if red > 100 and 45 < green < 150 and blue < 100)
    metal_pixels = sum(1 for red, green, blue in icon.get_flattened_data() if red > 180 and green > 190 and blue > 195)
    assert handle_pixels >= 80
    assert metal_pixels >= 80


def test_live_card_has_red_on_air_indicator():
    account = Account(1, 7, "Hunter_sssss", "uuid", "Grapes")
    image = Image.open(
        BytesIO(render_progress_card([(account, report(1, mining=25_000, commissions=2, powder=500))], live=True))
    )
    header = image.crop((820, 60, 1110, 160))

    red_pixels = sum(1 for red, green, blue in header.get_flattened_data() if red > 190 and green < 100 and blue < 120)
    assert red_pixels >= 100
