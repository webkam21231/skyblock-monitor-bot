from __future__ import annotations

import random
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .hypixel import HOTM_XP_COSTS, MINING_XP_COSTS, LevelProgress, level_progress
from .models import Account, PeriodReport
from .presentation import MOSCOW, signed

WIDTH = 1200
CARD_HEIGHT = 900
MAX_ACCOUNTS_PER_CARD = 4
FONT_REGULAR = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
FONT_BOLD = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT_REGULAR), size)


def color_for(value: float) -> str:
    if value > 0:
        return "#74f0b0"
    if value < 0:
        return "#ff7995"
    return "#a9acc0"


def format_number(value: float) -> str:
    return f"{value:,.0f}".replace(",", " ")


def _text_top(
    draw: ImageDraw.ImageDraw,
    xy: tuple[float, float],
    text: str,
    *,
    text_font: ImageFont.FreeTypeFont,
    fill: str,
    align: str = "left",
) -> None:
    """Draw using the visible glyph top, not Pillow's font ascender offset."""
    x, y = xy
    bbox = draw.textbbox((0, 0), text, font=text_font)
    width = bbox[2] - bbox[0]
    if align == "right":
        x -= width
    elif align == "center":
        x -= width / 2
    draw.text((x - bbox[0], y - bbox[1]), text, font=text_font, fill=fill)


def _fit_font(draw: ImageDraw.ImageDraw, text: str, max_width: int, preferred: int, minimum: int = 15) -> ImageFont.FreeTypeFont:
    for size in range(preferred, minimum - 1, -1):
        candidate = font(size, True)
        bbox = draw.textbbox((0, 0), text, font=candidate)
        if bbox[2] - bbox[0] <= max_width:
            return candidate
    return font(minimum, True)


def _cut_points(box: tuple[int, int, int, int], cut: int = 18) -> list[tuple[int, int]]:
    x1, y1, x2, y2 = box
    return [
        (x1 + cut, y1),
        (x2 - cut, y1),
        (x2, y1 + cut),
        (x2, y2 - cut),
        (x2 - cut, y2),
        (x1 + cut, y2),
        (x1, y2 - cut),
        (x1, y1 + cut),
    ]


def _draw_pickaxe(draw: ImageDraw.ImageDraw, origin: tuple[int, int]) -> None:
    x, y = origin
    draw.polygon(_cut_points((x, y, x + 88, y + 88), 13), fill="#0b1b27", outline="#168ca8", width=3)
    draw.line((x + 29, y + 67, x + 59, y + 30), fill="#8b6840", width=10)
    draw.line((x + 31, y + 66, x + 61, y + 29), fill="#b0854e", width=4)
    draw.line((x + 29, y + 28, x + 68, y + 30), fill="#dceaf0", width=9)
    draw.line((x + 24, y + 33, x + 31, y + 27), fill="#dceaf0", width=7)
    draw.line((x + 67, y + 30, x + 73, y + 38), fill="#dceaf0", width=7)
    draw.line((x + 33, y + 27, x + 63, y + 29), fill="#5be7ff", width=2)


def _background(height: int) -> Image.Image:
    image = Image.new("RGBA", (WIDTH, height), "#07101e")
    draw = ImageDraw.Draw(image)
    top = (6, 14, 31)
    bottom = (22, 8, 39)
    for y in range(height):
        mix = y / max(1, height - 1)
        color = tuple(int(a + (b - a) * mix) for a, b in zip(top, bottom, strict=True)) + (255,)
        draw.line((0, y, WIDTH, y), fill=color)

    glow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse((-260, -180, 590, 600), fill=(15, 174, 255, 105))
    glow_draw.ellipse((720, -260, 1450, 540), fill=(126, 75, 255, 95))
    glow_draw.ellipse((580, height - 480, 1320, height + 220), fill=(255, 126, 54, 50))
    image = Image.alpha_composite(image, glow.filter(ImageFilter.GaussianBlur(145)))

    details = Image.new("RGBA", image.size, (0, 0, 0, 0))
    detail_draw = ImageDraw.Draw(details)
    left_wall = [(0, 0), (238, 0), (188, 150), (229, 300), (154, 460), (206, 650), (125, 830), (88, height), (0, height)]
    right_wall = [(1200, 0), (1012, 0), (1062, 165), (1004, 328), (1068, 500), (1018, 710), (1080, height), (1200, height)]
    detail_draw.polygon(left_wall, fill="#142532")
    detail_draw.polygon(right_wall, fill="#11222e")
    detail_draw.polygon([(0, 0), (128, 0), (92, 220), (166, 410), (76, 610), (0, 650)], fill="#1a2d3a")
    detail_draw.polygon([(1200, 80), (1105, 0), (1070, 245), (1130, 420), (1055, 650), (1200, 720)], fill="#1a2d3a")
    detail_draw.polygon([(0, height - 128), (245, height - 176), (430, height - 108), (690, height - 155), (910, height - 90), (1200, height - 145), (1200, height), (0, height)], fill="#0b171f")
    detail_draw.line([(26, 260), (94, 314), (68, 367), (177, 426)], fill=(22, 140, 168, 155), width=4)
    detail_draw.line([(1175, 585), (1100, 644), (1132, 706), (1032, 778)], fill=(155, 123, 57, 150), width=4)

    rng = random.Random(326)
    palette = [(72, 217, 255, 150), (150, 104, 255, 150), (255, 185, 72, 130)]
    for _ in range(max(45, height // 12)):
        x = rng.randrange(20, WIDTH - 20)
        y = rng.randrange(20, height - 20)
        radius = rng.choice((1, 1, 2, 3))
        detail_draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=rng.choice(palette))

    for anchor_x, anchor_y, scale, color in [
        (25, 90, 1.0, (36, 214, 255, 125)),
        (1170, 250, 0.8, (153, 91, 255, 135)),
        (35, height - 85, 0.65, (255, 172, 58, 115)),
        (1160, height - 70, 0.55, (45, 231, 190, 120)),
    ]:
        for offset, size in [(-22, 62), (18, 86), (48, 48)]:
            x = anchor_x + int(offset * scale)
            h = int(size * scale)
            w = max(12, int(28 * scale))
            detail_draw.polygon(
                [(x, anchor_y), (x + w // 2, anchor_y - h), (x + w, anchor_y), (x + w // 2, anchor_y + 20)],
                fill=color,
                outline=(210, 246, 255, 150),
            )
    return Image.alpha_composite(image, details)


def _panel(image: Image.Image, box: tuple[int, int, int, int], radius: int = 30, accent: str = "#42d9ff") -> None:
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    x1, y1, x2, y2 = box
    cut = min(22, radius)
    draw.polygon([(px + 7, py + 9) for px, py in _cut_points(box, cut)], fill=(0, 0, 0, 105))
    draw.polygon(_cut_points(box, cut), fill=(8, 18, 27, 238), outline=(45, 75, 93, 230), width=3)
    draw.line((x1 + cut, y1 + 2, x2 - 90, y1 + 2), fill=accent, width=5)
    draw.line((x1 + 2, y1 + cut, x1 + 2, y2 - 42), fill=accent, width=4)
    image.alpha_composite(layer)


def render_menu_card() -> bytes:
    image = _background(620)
    _panel(image, (65, 62, 1135, 558), radius=38, accent="#42d9ff")
    draw = ImageDraw.Draw(image)
    _draw_pickaxe(draw, (100, 94))
    _text_top(draw, (215, 105), "SKYBLOCK MONITOR", text_font=font(28, True), fill="#66e2ff")
    _text_top(draw, (215, 155), "Mining Progress", text_font=font(60, True), fill="#f7f8ff")
    _text_top(draw, (110, 255), "Живая статистика твоих шахтёров", text_font=font(30), fill="#b9bed4")
    draw.rounded_rectangle((110, 350, 1090, 492), radius=26, fill=(13, 20, 39, 235), outline="#44547d", width=2)
    _text_top(draw, (150, 382), "MINING  •  HOTM  •  POWDER  •  PURSE", text_font=font(29, True), fill="#80f2b8")
    _text_top(draw, (150, 435), "Автоматическое обновление каждую минуту", text_font=font(25), fill="#a9aec4")
    return _png(image)


def _progress_line(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    label: str,
    delta: float,
    progress: LevelProgress,
    xp_per_hour: float,
    accent: str,
) -> None:
    x1, y1, x2, y2 = box
    draw.polygon(_cut_points(box, 10), fill=(18, 32, 46, 245), outline=(45, 75, 93, 230), width=2)
    _text_top(draw, (x1 + 14, y1 + 8), f"{label} {progress.level}", text_font=font(16, True), fill="#dce5f5")
    _text_top(draw, (x2 - 14, y1 + 8), f"{signed(delta)} XP", text_font=font(16, True), fill=color_for(delta), align="right")
    if progress.next_level is None:
        progress_text = "Максимальный уровень"
    else:
        progress_text = (
            f"До {progress.next_level}: {format_number(progress.remaining)} XP"
            f"  •  {progress.remaining_percent:.1f}%  •  ≈ {eta_text(progress.remaining, xp_per_hour)}"
        )
    _text_top(draw, (x1 + 14, y1 + 33), progress_text, text_font=font(13), fill="#aeb8d0")
    bar = (x1 + 14, y2 - 12, x2 - 14, y2 - 6)
    draw.rounded_rectangle(bar, radius=3, fill="#26364b")
    fill_width = int((bar[2] - bar[0]) * min(100.0, max(0.0, progress.percent)) / 100)
    if fill_width:
        draw.rounded_rectangle((bar[0], bar[1], bar[0] + fill_width, bar[3]), radius=3, fill=accent)


def _metric(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], label: str, value: str, delta: float) -> None:
    x1, y1, x2, _ = box
    _text_top(draw, ((x1 + x2) / 2, y1 + 2), label.upper(), text_font=font(10, True), fill="#8996b4", align="center")
    _text_top(draw, ((x1 + x2) / 2, y1 + 17), value, text_font=font(16, True), fill=color_for(delta), align="center")


def xp_rates(report: PeriodReport) -> tuple[float, float]:
    seconds = max(1.0, (report.end.observed_at - report.start.observed_at).total_seconds())
    factor = 3600 / seconds
    return report.mining_xp * factor, (report.end.hotm_xp - report.start.hotm_xp) * factor


def eta_text(remaining_xp: int, xp_per_hour: float) -> str:
    if xp_per_hour <= 0:
        return "—"
    total_minutes = round(remaining_xp / xp_per_hour * 60)
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours}ч {minutes:02d}м"


def _compact_number(value: float) -> str:
    absolute = abs(value)
    if absolute >= 1_000_000:
        rendered = f"{absolute / 1_000_000:.1f}m"
    elif absolute >= 1_000:
        rendered = f"{absolute / 1_000:.1f}k"
    else:
        rendered = f"{absolute:.0f}"
    return ("+" if value >= 0 else "−") + rendered


def _draw_account_panel(
    image: Image.Image,
    box: tuple[int, int, int, int],
    account: Account,
    report: PeriodReport,
    accent: str,
) -> None:
    _panel(image, box, radius=24, accent=accent)
    draw = ImageDraw.Draw(image)
    x1, y1, x2, _ = box
    draw.ellipse((x1 + 22, y1 + 17, x1 + 64, y1 + 59), fill=accent, outline="#dffaff", width=2)
    initial_font = font(20, True)
    _text_top(draw, (x1 + 43, y1 + 27), account.username[:1].upper(), text_font=initial_font, fill="#07101e", align="center")
    name_font = _fit_font(draw, account.username, x2 - x1 - 104, 23)
    _text_top(draw, (x1 + 78, y1 + 15), account.username, text_font=name_font, fill="#f7f8ff")
    elapsed = report.end.observed_at - report.start.observed_at
    minutes = max(0, int(elapsed.total_seconds() // 60))
    meta = f"{account.profile_name.upper()}  •  {minutes // 60}ч {minutes % 60:02d}м"
    _text_top(draw, (x1 + 78, y1 + 44), meta, text_font=font(11, True), fill=accent)

    mining = level_progress(report.end.mining_xp, MINING_XP_COSTS)
    hotm = level_progress(report.end.hotm_xp, HOTM_XP_COSTS)
    mining_rate, hotm_rate = xp_rates(report)
    _progress_line(
        draw,
        (x1 + 22, y1 + 72, x2 - 22, y1 + 134),
        "MINING",
        report.mining_xp,
        mining,
        mining_rate,
        accent,
    )
    _progress_line(
        draw,
        (x1 + 22, y1 + 142, x2 - 22, y1 + 204),
        "HOTM",
        report.end.hotm_xp - report.start.hotm_xp,
        hotm,
        hotm_rate,
        accent,
    )

    metrics = [
        ("Комиссии", signed(report.commissions), report.commissions),
        ("Mithril", signed(report.mithril_powder), report.mithril_powder),
        ("Gemstone", signed(report.gemstone_powder), report.gemstone_powder),
        ("Glacite", signed(report.glacite_powder), report.glacite_powder),
        ("Purse", signed(report.purse), report.purse),
        ("SB Level", str(report.end.skyblock_level), report.end.skyblock_level - report.start.skyblock_level),
        ("Mining XP/ч", _compact_number(mining_rate), mining_rate),
        ("HOTM XP/ч", _compact_number(hotm_rate), hotm_rate),
    ]
    content_width = x2 - x1 - 44
    column_width = content_width // 4
    for index, (label, value, delta) in enumerate(metrics):
        col, row = index % 4, index // 4
        mx1 = x1 + 22 + col * column_width
        my1 = y1 + 216 + row * 39
        if col:
            draw.line((mx1, my1 + 2, mx1, my1 + 31), fill="#263d50", width=1)
        _metric(draw, (mx1, my1, mx1 + column_width, my1 + 36), label, value, delta)


def _panel_boxes(count: int) -> list[tuple[int, int, int, int]]:
    half_left = (55, 0, 585, 0)
    half_right = (615, 0, 1145, 0)
    if count == 1:
        return [(220, 300, 980, 610)]
    if count == 2:
        return [(half_left[0], 300, half_left[2], 610), (half_right[0], 300, half_right[2], 610)]
    if count == 3:
        return [
            (half_left[0], 205, half_left[2], 515),
            (half_right[0], 205, half_right[2], 515),
            (335, 535, 865, 845),
        ]
    return [
        (half_left[0], 205, half_left[2], 515),
        (half_right[0], 205, half_right[2], 515),
        (half_left[0], 535, half_left[2], 845),
        (half_right[0], 535, half_right[2], 845),
    ]


def render_progress_card(
    rows: list[tuple[Account, PeriodReport]],
    *,
    live: bool = False,
    page: int = 1,
    page_count: int = 1,
) -> bytes:
    if not rows:
        raise ValueError("At least one report is required")
    if len(rows) > MAX_ACCOUNTS_PER_CARD:
        raise ValueError("A progress card supports at most four accounts")

    image = _background(CARD_HEIGHT)
    _panel(image, (55, 34, 1145, 180), radius=30, accent="#a06bff")
    draw = ImageDraw.Draw(image)
    _draw_pickaxe(draw, (76, 62))
    _text_top(draw, (183, 59), "CRYSTAL HOLLOWS  /  MINING LOG", text_font=font(19, True), fill="#66e2ff")
    _text_top(draw, (183, 87), "Отчёт по майнингу", text_font=font(38, True), fill="#f7f8ff")
    if live:
        draw.ellipse((882, 61, 904, 83), fill="#ff4d68")
        draw.polygon(_cut_points((918, 55, 1097, 91), 9), fill="#5a1725", outline="#ff4d68", width=2)
        _text_top(draw, (1008, 63), "LIVE", text_font=font(18, True), fill="#ff8294", align="center")

    period_start = min(report.start.observed_at for _, report in rows).astimezone(MOSCOW)
    period_end = max(report.end.observed_at for _, report in rows).astimezone(MOSCOW)
    period = f"{period_start:%d.%m %H:%M} — {period_end:%d.%m %H:%M} МСК"
    draw.polygon(_cut_points((183, 139, 620, 168), 8), fill=(27, 37, 65, 230))
    _text_top(draw, (198, 145), period, text_font=font(15), fill="#c2c8dc")
    if page_count > 1:
        _text_top(draw, (1095, 145), f"КАРТОЧКА {page}/{page_count}", text_font=font(14, True), fill="#aeb8d0", align="right")

    accents = ["#42d9ff", "#a06bff", "#ffb84a", "#45e7b0"]
    for box, (account, report), accent in zip(_panel_boxes(len(rows)), rows, accents[:len(rows)], strict=True):
        _draw_account_panel(image, box, account, report, accent)

    _text_top(
        draw,
        (600, 872),
        "ДОПОЛНИТЕЛЬНО: SKYBLOCK LEVEL  •  MINING/HOTM XP В ЧАС  •  ВРЕМЯ ДО УРОВНЯ",
        text_font=font(12, True),
        fill="#72809e",
        align="center",
    )
    return _png(image)


def render_progress_cards(rows: list[tuple[Account, PeriodReport]], *, live: bool = False) -> list[bytes]:
    if not rows:
        raise ValueError("At least one report is required")
    chunks = [rows[index:index + MAX_ACCOUNTS_PER_CARD] for index in range(0, len(rows), MAX_ACCOUNTS_PER_CARD)]
    return [
        render_progress_card(chunk, live=live, page=index + 1, page_count=len(chunks))
        for index, chunk in enumerate(chunks)
    ]


def _png(image: Image.Image) -> bytes:
    output = BytesIO()
    image.convert("RGB").save(output, format="PNG", optimize=True)
    return output.getvalue()
