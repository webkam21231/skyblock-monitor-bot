from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .models import Account, PeriodReport
from .presentation import MOSCOW, signed

WIDTH = 1200
FONT_REGULAR = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
FONT_BOLD = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT_REGULAR), size)


def color_for(value: float) -> str:
    if value > 0:
        return "#70e1a1"
    if value < 0:
        return "#ff7d91"
    return "#9296a3"


def render_menu_card() -> bytes:
    image = Image.new("RGB", (WIDTH, 620), "#090a0d")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((55, 55, 1145, 565), radius=38, fill="#111218", outline="#303348", width=3)
    draw.text((95, 100), "SKYBLOCK MONITOR", font=font(28, True), fill="#7f8cff")
    draw.text((95, 165), "Mining Progress", font=font(64, True), fill="#f4f5f8")
    draw.text((95, 260), "Все аккаунты и периоды — в одном сообщении", font=font(30), fill="#a4a7b2")
    draw.rounded_rectangle((95, 350, 1105, 490), radius=28, fill="#17181d", outline="#282a33", width=2)
    draw.text((135, 382), "MINING  •  HOTM  •  POWDER  •  PURSE", font=font(29, True), fill="#70e1a1")
    draw.text((135, 435), "Автоматическое обновление каждую минуту", font=font(25), fill="#9296a3")
    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def draw_metric(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], label: str, value: str, delta: float) -> None:
    draw.rounded_rectangle(box, radius=20, fill="#17181d", outline="#282a33", width=2)
    x1, y1, _, _ = box
    draw.text((x1 + 22, y1 + 18), label, font=font(22), fill="#9296a3")
    draw.text((x1 + 22, y1 + 58), value, font=font(32, True), fill=color_for(delta))


def render_progress_card(rows: list[tuple[Account, PeriodReport]]) -> bytes:
    if not rows:
        raise ValueError("At least one report is required")
    height = 300 + len(rows) * 490
    image = Image.new("RGB", (WIDTH, height), "#090a0d")
    pixels = image.load()
    for y in range(height):
        blend = y / max(1, height - 1)
        pixels_color = (9 + int(5 * blend), 10 + int(7 * blend), 13 + int(12 * blend))
        for x in range(WIDTH):
            pixels[x, y] = pixels_color
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((55, 45, 1145, 205), radius=30, fill="#111218", outline="#303348", width=2)
    draw.text((90, 74), "SKYBLOCK PROGRESS", font=font(24, True), fill="#7f8cff")
    draw.text((90, 112), "Отчёт по майнингу", font=font(48, True), fill="#f4f5f8")
    period_start = min(report.start.observed_at for _, report in rows).astimezone(MOSCOW)
    period_end = max(report.end.observed_at for _, report in rows).astimezone(MOSCOW)
    period = f"{period_start:%d.%m.%Y %H:%M} — {period_end:%d.%m.%Y %H:%M} МСК"
    draw.text((90, 170), period, font=font(21), fill="#a4a7b2")

    for index, (account, report) in enumerate(rows):
        top = 245 + index * 490
        draw.rounded_rectangle((55, top, 1145, top + 450), radius=30, fill="#111218", outline="#282b39", width=2)
        draw.text((85, top + 28), account.username, font=font(34, True), fill="#f5f6fa")
        draw.text((85, top + 72), account.profile_name, font=font(22), fill="#7f8cff")
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
            x = 85 + col * 345
            y = top + 115 + row * 100
            draw_metric(draw, (x, y, x + 320, y + 84), label, value, delta)
        if report.mining_xp >= 10_000 and report.commissions == 0:
            draw.rounded_rectangle((85, top + 415, 1115, top + 440), radius=12, fill="#3a2519")
            draw.text((105, top + 416), "⚠ Mining XP растёт, но commissions не изменились", font=font(17, True), fill="#ffbf73")

    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()
