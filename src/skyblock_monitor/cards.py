from __future__ import annotations

import random
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .models import Account, PeriodReport
from .presentation import MOSCOW, signed

WIDTH = 1200
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
    glow_draw.ellipse((-260, -180, 590, 600), fill=(15, 174, 255, 110))
    glow_draw.ellipse((720, -260, 1450, 540), fill=(126, 75, 255, 100))
    glow_draw.ellipse((580, height - 480, 1320, height + 220), fill=(255, 126, 54, 55))
    glow = glow.filter(ImageFilter.GaussianBlur(145))
    image = Image.alpha_composite(image, glow)

    details = Image.new("RGBA", image.size, (0, 0, 0, 0))
    detail_draw = ImageDraw.Draw(details)
    left_wall = [(0, 0), (238, 0), (188, 150), (229, 300), (154, 460), (206, 650), (125, 830), (170, 1040), (88, height), (0, height)]
    right_wall = [(1200, 0), (1012, 0), (1062, 165), (1004, 328), (1068, 500), (1018, 710), (1080, 905), (1028, height), (1200, height)]
    detail_draw.polygon(left_wall, fill="#142532")
    detail_draw.polygon(right_wall, fill="#11222e")
    detail_draw.polygon([(0, 0), (128, 0), (92, 220), (166, 410), (76, 610), (0, 650)], fill="#1a2d3a")
    detail_draw.polygon([(1200, 80), (1105, 0), (1070, 245), (1130, 420), (1055, 650), (1200, 720)], fill="#1a2d3a")
    detail_draw.polygon([(0, height - 128), (245, height - 176), (430, height - 108), (690, height - 155), (910, height - 90), (1200, height - 145), (1200, height), (0, height)], fill="#0b171f")
    detail_draw.line([(26, 260), (94, 314), (68, 367), (177, 426)], fill=(22, 140, 168, 155), width=4)
    detail_draw.line([(1175, 585), (1100, 644), (1132, 706), (1032, 778)], fill=(155, 123, 57, 150), width=4)
    detail_draw.line([(128, height - 42), (225, height - 112), (332, height - 84), (402, height - 139)], fill=(22, 140, 168, 130), width=3)

    rng = random.Random(326)
    palette = [(72, 217, 255, 150), (150, 104, 255, 150), (255, 185, 72, 130)]
    for _ in range(max(45, height // 12)):
        x = rng.randrange(20, WIDTH - 20)
        y = rng.randrange(20, height - 20)
        radius = rng.choice((1, 1, 2, 3))
        color = rng.choice(palette)
        detail_draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)

    for anchor_x, anchor_y, scale, color in [
        (25, 90, 1.0, (36, 214, 255, 125)),
        (1170, 250, 0.8, (153, 91, 255, 135)),
        (35, height - 145, 0.75, (255, 172, 58, 115)),
        (1160, height - 115, 0.55, (45, 231, 190, 120)),
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
    shadow = [(px + 8, py + 12) for px, py in _cut_points(box, cut)]
    draw.polygon(shadow, fill=(0, 0, 0, 105))
    draw.polygon(_cut_points(box, cut), fill=(10, 20, 29, 232), outline=(45, 75, 93, 220), width=3)
    draw.line((x1 + cut, y1 + 2, x2 - 92, y1 + 2), fill=accent, width=5)
    draw.line((x1 + 2, y1 + cut, x1 + 2, y2 - 48), fill=accent, width=4)
    image.alpha_composite(layer)


def render_menu_card() -> bytes:
    image = _background(620)
    _panel(image, (65, 62, 1135, 558), radius=38, accent="#42d9ff")
    draw = ImageDraw.Draw(image)
    _draw_pickaxe(draw, (100, 94))
    draw.text((215, 105), "SKYBLOCK MONITOR", font=font(28, True), fill="#66e2ff")
    draw.text((215, 155), "Mining Progress", font=font(60, True), fill="#f7f8ff")
    draw.text((110, 255), "Живая статистика твоих шахтёров", font=font(30), fill="#b9bed4")
    draw.rounded_rectangle((110, 350, 1090, 492), radius=26, fill=(13, 20, 39, 235), outline="#44547d", width=2)
    draw.text((150, 382), "MINING  •  HOTM  •  POWDER  •  PURSE", font=font(29, True), fill="#80f2b8")
    draw.text((150, 435), "Автоматическое обновление каждую минуту", font=font(25), fill="#a9aec4")
    output = BytesIO()
    image.convert("RGB").save(output, format="PNG", optimize=True)
    return output.getvalue()


def draw_metric(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    label: str,
    value: str,
    delta: float,
    accent: str,
) -> None:
    draw.polygon(_cut_points(box, 13), fill=(20, 34, 48, 245), outline=(45, 75, 93, 230), width=2)
    x1, y1, _, _ = box
    draw.line((x1 + 17, y1 + 20, x1 + 17, y1 + 63), fill=accent, width=6)
    draw.text((x1 + 34, y1 + 15), label, font=font(19), fill="#9ea7c4")
    draw.text((x1 + 34, y1 + 47), value, font=font(29, True), fill=color_for(delta))


def render_progress_card(rows: list[tuple[Account, PeriodReport]], *, live: bool = False) -> bytes:
    if not rows:
        raise ValueError("At least one report is required")
    height = 320 + len(rows) * 500
    image = _background(height)
    _panel(image, (58, 46, 1142, 222), radius=32, accent="#a06bff")
    draw = ImageDraw.Draw(image)
    _draw_pickaxe(draw, (82, 74))
    draw.text((194, 76), "CRYSTAL HOLLOWS  /  MINING LOG", font=font(23, True), fill="#66e2ff")
    draw.text((194, 112), "Отчёт по майнингу", font=font(45, True), fill="#f7f8ff")
    if live:
        draw.ellipse((884, 79, 908, 103), fill="#ff4d68")
        draw.polygon(_cut_points((922, 72, 1098, 112), 10), fill="#5a1725", outline="#ff4d68", width=2)
        draw.text((948, 79), "LIVE", font=font(22, True), fill="#ff8294")
    period_start = min(report.start.observed_at for _, report in rows).astimezone(MOSCOW)
    period_end = max(report.end.observed_at for _, report in rows).astimezone(MOSCOW)
    period = f"{period_start:%d.%m.%Y %H:%M} — {period_end:%d.%m.%Y %H:%M} МСК"
    draw.polygon(_cut_points((194, 174, 711, 207), 9), fill=(27, 37, 65, 230))
    draw.text((211, 179), period, font=font(19), fill="#c2c8dc")

    accents = ["#42d9ff", "#a06bff", "#ffb84a", "#45e7b0"]
    for index, (account, report) in enumerate(rows):
        top = 258 + index * 500
        accent = accents[index % len(accents)]
        _panel(image, (58, top, 1142, top + 456), radius=30, accent=accent)
        draw = ImageDraw.Draw(image)
        draw.ellipse((91, top + 28, 145, top + 82), fill=accent, outline="#dffaff", width=2)
        initial = account.username[:1].upper()
        bbox = draw.textbbox((0, 0), initial, font=font(25, True))
        draw.text((118 - (bbox[2] - bbox[0]) / 2, top + 38), initial, font=font(25, True), fill="#07101e")
        draw.text((163, top + 24), account.username, font=font(33, True), fill="#f7f8ff")
        draw.text((164, top + 66), f"PROFILE  {account.profile_name.upper()}", font=font(18, True), fill=accent)
        metrics = [
            ("Mining XP", signed(report.mining_xp), report.mining_xp),
            ("Mining Level", f"{report.start.mining_level} → {report.end.mining_level}", report.end.mining_level - report.start.mining_level),
            ("Commissions", signed(report.commissions), report.commissions),
            ("HOTM XP", signed(report.end.hotm_xp - report.start.hotm_xp), report.end.hotm_xp - report.start.hotm_xp),
            ("HOTM Level", f"{report.start.hotm_level} → {report.end.hotm_level}", report.end.hotm_level - report.start.hotm_level),
            ("Mithril Powder", signed(report.mithril_powder), report.mithril_powder),
            ("Gemstone Powder", signed(report.gemstone_powder), report.gemstone_powder),
            ("Glacite Powder", signed(report.glacite_powder), report.glacite_powder),
            ("Purse", signed(report.purse), report.purse),
        ]
        for metric_index, (label, value, delta) in enumerate(metrics):
            col, row = metric_index % 3, metric_index // 3
            x = 91 + col * 340
            y = top + 112 + row * 98
            draw_metric(draw, (x, y, x + 315, y + 82), label, value, delta, accent)
        if report.mining_xp >= 10_000 and report.commissions == 0:
            draw.rounded_rectangle((91, top + 418, 1109, top + 445), radius=12, fill=(82, 49, 22, 235))
            draw.text((111, top + 419), "⚠ Mining XP растёт, но commissions не изменились", font=font(17, True), fill="#ffd08a")

    output = BytesIO()
    image.convert("RGB").save(output, format="PNG", optimize=True)
    return output.getvalue()
