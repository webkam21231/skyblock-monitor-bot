from datetime import datetime
from zoneinfo import ZoneInfo

from .models import PeriodReport

MOSCOW = ZoneInfo("Europe/Moscow")


def parse_custom_period(value: str) -> tuple[datetime, datetime]:
    try:
        left, right = (part.strip() for part in value.split(" - ", 1))
        start = datetime.strptime(left, "%d.%m.%Y %H:%M").replace(tzinfo=MOSCOW)
        end = datetime.strptime(right, "%d.%m.%Y %H:%M").replace(tzinfo=MOSCOW)
    except (ValueError, TypeError) as exc:
        raise ValueError("Формат: ДД.ММ.ГГГГ ЧЧ:ММ - ДД.ММ.ГГГГ ЧЧ:ММ") from exc
    if end <= start:
        raise ValueError("Начало должно быть раньше конца периода")
    return start.astimezone(ZoneInfo("UTC")), end.astimezone(ZoneInfo("UTC"))


def signed(value: float, digits: int = 0) -> str:
    rendered = f"{abs(value):,.{digits}f}".replace(",", " ")
    return ("+" if value >= 0 else "−") + rendered


def format_report(username: str, profile_name: str, report: PeriodReport) -> str:
    start = report.start.observed_at.astimezone(MOSCOW).strftime("%d.%m %H:%M")
    end = report.end.observed_at.astimezone(MOSCOW).strftime("%d.%m %H:%M")
    lines = [
        f"<b>{username} / {profile_name}</b>",
        f"Период: {start} — {end} МСК",
        "",
        f"Mining XP: {signed(report.mining_xp)}",
        f"Mining: {report.start.mining_level} → {report.end.mining_level}",
        f"HOTM XP: <b>{signed(report.end.hotm_xp - report.start.hotm_xp)}</b>",
        f"HOTM: {report.start.hotm_level} → {report.end.hotm_level}",
        f"Commissions: {signed(report.commissions)}",
        f"Mithril Powder: <b>{signed(report.mithril_powder)}</b>",
        f"Gemstone Powder: <b>{signed(report.gemstone_powder)}</b>",
        f"Glacite Powder: <b>{signed(report.glacite_powder)}</b>",
        f"Purse: <b>{signed(report.purse)}</b>",
    ]
    if report.mining_xp >= 10_000 and report.commissions == 0:
        lines.extend(["", "⚠️ Mining XP растёт, но не выполнено ни одной комиссии."])
    return "\n".join(lines)
