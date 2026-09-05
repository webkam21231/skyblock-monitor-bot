from __future__ import annotations

import asyncio
import logging
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Message,
)

from .cards import render_menu_card, render_progress_card, render_progress_cards
from .hypixel import HypixelClient, is_skyblock_online
from .models import LiveView
from .presentation import MOSCOW, parse_custom_period
from .store import Store

log = logging.getLogger(__name__)
router = Router()
store: Store
hypixel: HypixelClient
DEFAULT_DAILY_REQUEST_LIMIT = 2_400
DEFAULT_POLL_INTERVAL_SECONDS = 240


class AddAccount(StatesGroup):
    username = State()
    profile = State()


class CustomPeriod(StatesGroup):
    value = State()


def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔴 Прямой эфир", callback_data="live:0")],
        [InlineKeyboardButton(text="🗂 Сессии", callback_data="sessions")],
        [InlineKeyboardButton(text="📈 Все аккаунты", callback_data="all")],
        [InlineKeyboardButton(text="➕ Добавить аккаунт", callback_data="add")],
        [InlineKeyboardButton(text="👥 Мои аккаунты", callback_data="accounts")],
    ])


def account_keyboard(account_id: int) -> InlineKeyboardMarkup:
    periods = [("15 минут", "15m"), ("30 минут", "30m"), ("1 час", "1h"), ("3 часа", "3h"),
               ("6 часов", "6h"), ("12 часов", "12h"), ("24 часа", "24h"), ("7 дней", "7d"),
               ("30 дней", "30d")]
    rows = []
    for index in range(0, len(periods), 3):
        rows.append([InlineKeyboardButton(text=label, callback_data=f"period:{account_id}:{code}")
                     for label, code in periods[index:index + 3]])
    rows.extend([
        [InlineKeyboardButton(text="🔴 Прямой эфир", callback_data=f"live:{account_id}")],
        [InlineKeyboardButton(text="🗓 Произвольный период", callback_data=f"custom:{account_id}")],
        [InlineKeyboardButton(text="🔄 Обновить сейчас", callback_data=f"refresh:{account_id}")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete:{account_id}"),
         InlineKeyboardButton(text="⬅️ К аккаунтам", callback_data="accounts")],
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def all_accounts_keyboard() -> InlineKeyboardMarkup:
    periods = [("15 минут", "15m"), ("30 минут", "30m"), ("1 час", "1h"), ("3 часа", "3h"),
               ("6 часов", "6h"), ("12 часов", "12h"), ("24 часа", "24h"), ("7 дней", "7d"),
               ("30 дней", "30d")]
    rows = []
    for index in range(0, len(periods), 3):
        rows.append([InlineKeyboardButton(text=label, callback_data=f"period:0:{code}")
                     for label, code in periods[index:index + 3]])
    rows.extend([
        [InlineKeyboardButton(text="🗓 Произвольный период", callback_data="custom:0")],
        [InlineKeyboardButton(text="⬅️ Главное меню", callback_data="home")],
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _pager_row(prefix: str, page: int, page_count: int) -> list[InlineKeyboardButton]:
    row = []
    if page > 0:
        row.append(InlineKeyboardButton(text="⬅️", callback_data=f"{prefix}:{page - 1}"))
    row.append(InlineKeyboardButton(text=f"{page + 1}/{page_count}", callback_data="page-noop"))
    if page + 1 < page_count:
        row.append(InlineKeyboardButton(text="➡️", callback_data=f"{prefix}:{page + 1}"))
    return row


def report_keyboard(
    base: InlineKeyboardMarkup,
    prefix: str,
    *,
    page: int,
    page_count: int,
) -> InlineKeyboardMarkup:
    rows = [list(row) for row in base.inline_keyboard]
    if page_count > 1:
        rows.insert(0, _pager_row(prefix, page, page_count))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def live_keyboard(view_id: int, *, page: int = 0, page_count: int = 1) -> InlineKeyboardMarkup:
    rows = []
    if page_count > 1:
        rows.append(_pager_row(f"live-page:{view_id}", page, page_count))
    rows.extend([
        [InlineKeyboardButton(text="⏹ Остановить эфир", callback_data=f"live-stop:{view_id}")],
        [InlineKeyboardButton(text="🗂 Сессии", callback_data=f"live-sessions:{view_id}")],
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def session_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ К сессиям", callback_data="sessions")],
        [InlineKeyboardButton(text="⬅️ Главное меню", callback_data="home")],
    ])


def current_text(account, snapshot) -> str:
    if snapshot is None:
        return f"<b>{account.username} / {account.profile_name}</b>\nДанных пока нет."
    return "\n".join([
        f"<b>{account.username} / {account.profile_name}</b>",
        f"Mining: {snapshot.mining_level} · XP {snapshot.mining_xp:,.0f}".replace(",", " "),
        f"HOTM: {snapshot.hotm_level} · XP {snapshot.hotm_xp:,.0f}".replace(",", " "),
        f"Commissions counter: {snapshot.commissions}",
        f"Mithril Powder: {snapshot.mithril_powder:,.0f}".replace(",", " "),
        f"Gemstone Powder: {snapshot.gemstone_powder:,.0f}".replace(",", " "),
        f"Glacite Powder: {snapshot.glacite_powder:,.0f}".replace(",", " "),
        f"Purse: {snapshot.purse:,.0f}".replace(",", " "),
        f"Обновлено: {snapshot.observed_at.astimezone(MOSCOW).strftime('%d.%m.%Y %H:%M')} МСК",
    ])


def duration(code: str) -> timedelta:
    unit = code[-1]
    amount = int(code[:-1])
    return timedelta(minutes=amount) if unit == "m" else timedelta(hours=amount) if unit == "h" else timedelta(days=amount)


async def edit_screen(message: Message, text: str, keyboard: InlineKeyboardMarkup | None = None) -> None:
    try:
        if message.photo:
            await message.edit_caption(caption=text, reply_markup=keyboard)
        else:
            await message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc):
            raise


@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer_photo(
        BufferedInputFile(render_menu_card(), filename="skyblock-monitor.png"),
        caption="Мониторинг прогресса Hypixel SkyBlock",
        reply_markup=main_keyboard(),
    )


@router.callback_query(F.data == "home")
async def home(query: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await edit_screen(query.message, "Главное меню", main_keyboard())
    await query.answer()


@router.callback_query(F.data == "all")
async def all_accounts(query: CallbackQuery) -> None:
    if not store.list_accounts(query.from_user.id):
        await edit_screen(query.message, "Пока нет добавленных аккаунтов.", main_keyboard())
    else:
        await edit_screen(query.message, "Выбери период для всех аккаунтов:", all_accounts_keyboard())
    await query.answer()


@router.callback_query(F.data == "add")
async def add_begin(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddAccount.username)
    await edit_screen(query.message, "Напиши Minecraft-ник:")
    await query.answer()


@router.message(AddAccount.username)
async def add_username(message: Message, state: FSMContext) -> None:
    username = (message.text or "").strip()
    try:
        uuid, canonical = await hypixel.resolve_username(username)
    except (httpx.HTTPError, ValueError, KeyError):
        await message.answer("Не удалось найти такой Minecraft-аккаунт. Попробуй ещё раз.")
        return
    await state.update_data(username=canonical, uuid=uuid)
    await state.set_state(AddAccount.profile)
    await message.answer("Напиши название SkyBlock-профиля, например Papaya или Grapes:")


@router.message(AddAccount.profile)
async def add_profile(message: Message, state: FSMContext) -> None:
    profile_name = (message.text or "").strip()
    data = await state.get_data()
    account = store.add_account(message.from_user.id, data["username"], data["uuid"], profile_name)
    try:
        snapshot = await hypixel.fetch(account.id, account.uuid, account.profile_name)
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        store.delete_account(account.id, message.from_user.id)
        await message.answer(f"Не удалось открыть профиль: {exc}")
        return
    store.save_snapshot(snapshot)
    await state.clear()
    await message.answer(current_text(account, snapshot), reply_markup=account_keyboard(account.id))


@router.callback_query(F.data == "accounts")
async def accounts(query: CallbackQuery) -> None:
    accounts_list = store.list_accounts(query.from_user.id)
    if not accounts_list:
        await edit_screen(query.message, "Пока нет добавленных аккаунтов.", main_keyboard())
    else:
        keyboard = [[InlineKeyboardButton(text=f"{a.username} / {a.profile_name}", callback_data=f"account:{a.id}")]
                    for a in accounts_list]
        keyboard.append([InlineKeyboardButton(text="➕ Добавить аккаунт", callback_data="add")])
        await edit_screen(query.message, "Выбери аккаунт:", InlineKeyboardMarkup(inline_keyboard=keyboard))
    await query.answer()


@router.callback_query(F.data.startswith("account:"))
async def show_account(query: CallbackQuery) -> None:
    account_id = int(query.data.split(":")[1])
    account = store.get_account(account_id, query.from_user.id)
    if account:
        await edit_screen(query.message, current_text(account, store.latest_snapshot(account.id)), account_keyboard(account.id))
    await query.answer()


def scoped_accounts(user_id: int, account_id: int):
    if account_id == 0:
        return store.list_accounts(user_id)
    account = store.get_account(account_id, user_id)
    return [account] if account else []


def live_rows(view: LiveView, end_at: datetime):
    rows = []
    for account in scoped_accounts(view.telegram_user_id, view.account_id):
        report = store.live_report(account.id, view.started_at, end_at)
        if report:
            rows.append((account, report))
    return rows


def live_caption(view: LiveView, now: datetime, *, live: bool) -> str:
    if not live:
        return "⏹ <b>Прямой эфир остановлен.</b> Итог сохранён на карточке."
    started = view.started_at.astimezone(MOSCOW).strftime("%d.%m %H:%M")
    updated = now.astimezone(MOSCOW).strftime("%d.%m %H:%M")
    return (
        f"🔴 <b>Прямой эфир</b> · старт {started} МСК\n"
        f"Обновление каждые 2 минуты · обновлено {updated} МСК"
    )


def is_message_not_modified(exc: Exception) -> bool:
    return "message is not modified" in str(exc).lower()


async def update_live_message(bot: Bot, view: LiveView, *, live: bool = True) -> bool:
    now = datetime.now(UTC)
    rows = live_rows(view, now)
    if not rows:
        return False
    caption = live_caption(view, now, live=live)
    cards = render_progress_cards(rows, live=live)
    page = min(view.current_page, len(cards) - 1)
    media = InputMediaPhoto(
        media=BufferedInputFile(cards[page], filename=f"skyblock-live-{page + 1}.png"),
        caption=caption,
    )
    keyboard = live_keyboard(view.id, page=page, page_count=len(cards)) if live else main_keyboard()
    await bot.edit_message_media(chat_id=view.chat_id, message_id=view.message_id, media=media, reply_markup=keyboard)
    return True


@router.callback_query(F.data.startswith("live:"))
async def start_live(query: CallbackQuery, bot: Bot) -> None:
    account_id = int(query.data.split(":")[1])
    accounts_list = scoped_accounts(query.from_user.id, account_id)
    if not accounts_list:
        await query.answer("Нет доступных аккаунтов", show_alert=True)
        return
    if not query.message.photo:
        await query.answer("Отправь /start и открой эфир из нового меню", show_alert=True)
        return
    await query.answer("Фиксирую начальные значения…")
    started_at = datetime.now(UTC)
    saved = 0
    for account in accounts_list:
        try:
            snapshot = await hypixel.fetch(account.id, account.uuid, account.profile_name)
            store.save_snapshot(snapshot)
            saved += 1
            try:
                status = await hypixel.fetch_status(account.uuid)
                store.record_presence(account.id, is_skyblock_online(status), snapshot.observed_at)
            except httpx.HTTPError:
                log.exception("Failed to fetch status for %s", account.username)
        except (httpx.HTTPError, ValueError, KeyError):
            log.exception("Failed to start live view for %s/%s", account.username, account.profile_name)
    if saved == 0:
        await edit_screen(query.message, "Не удалось получить начальные данные.", main_keyboard())
        return
    view = store.start_live_view(
        query.from_user.id,
        query.message.chat.id,
        query.message.message_id,
        account_id,
        started_at,
    )
    await update_live_message(bot, view)


@router.callback_query(F.data.startswith("live-page:"))
async def show_live_page(query: CallbackQuery, bot: Bot) -> None:
    _, view_id, page = query.data.split(":")
    view = store.get_live_view(int(view_id), query.from_user.id)
    if view is None:
        await query.answer("Эфир не найден", show_alert=True)
        return
    store.set_live_page(view.id, int(page), query.from_user.id)
    updated = store.get_live_view(view.id, query.from_user.id)
    await update_live_message(bot, updated)
    await query.answer()


@router.callback_query(F.data == "page-noop")
async def page_noop(query: CallbackQuery) -> None:
    await query.answer()


@router.callback_query(F.data.startswith("live-stop:"))
async def stop_live(query: CallbackQuery, bot: Bot) -> None:
    view_id = int(query.data.split(":")[1])
    view = store.get_live_view(view_id, query.from_user.id)
    if view is None:
        await query.answer("Эфир не найден", show_alert=True)
        return
    store.stop_live_view(view.id, query.from_user.id)
    await update_live_message(bot, view, live=False)
    await query.answer("Эфир остановлен")


async def show_sessions_screen(message: Message, user_id: int) -> None:
    sessions_list = store.list_sessions(user_id)
    if not sessions_list:
        await edit_screen(
            message,
            "Сессий пока нет. Они начнут записываться, когда аккаунт появится в SkyBlock.",
            main_keyboard(),
        )
        return
    rows = []
    for session in sessions_list:
        account = store.get_account(session.account_id, user_id)
        if account is None:
            continue
        icon = "🔴" if session.ended_at is None and session.offline_since is None else "🟠" if session.ended_at is None else "✅"
        started = session.started_at.astimezone(MOSCOW).strftime("%d.%m %H:%M")
        rows.append([InlineKeyboardButton(text=f"{icon} {account.username} · {started}", callback_data=f"session:{session.id}")])
    rows.append([InlineKeyboardButton(text="⬅️ Главное меню", callback_data="home")])
    await edit_screen(
        message,
        "<b>Игровые сессии</b>\n🔴 онлайн · 🟠 ждём возвращения · ✅ завершена",
        InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(F.data == "sessions")
async def sessions(query: CallbackQuery) -> None:
    await show_sessions_screen(query.message, query.from_user.id)
    await query.answer()


@router.callback_query(F.data.startswith("live-sessions:"))
async def stop_live_and_show_sessions(query: CallbackQuery) -> None:
    view_id = int(query.data.split(":")[1])
    store.stop_live_view(view_id, query.from_user.id)
    await show_sessions_screen(query.message, query.from_user.id)
    await query.answer("Эфир остановлен")


@router.callback_query(F.data.startswith("session:"))
async def show_session(query: CallbackQuery) -> None:
    session_id = int(query.data.split(":")[1])
    session = store.get_session(session_id, query.from_user.id)
    if session is None:
        await query.answer("Сессия не найдена", show_alert=True)
        return
    account = store.get_account(session.account_id, query.from_user.id)
    end_at = session.ended_at or datetime.now(UTC)
    report = store.live_report(session.account_id, session.started_at, end_at)
    if account is None or report is None:
        await query.answer("Для этой сессии пока недостаточно данных", show_alert=True)
        return
    media = InputMediaPhoto(
        media=BufferedInputFile(render_progress_card([(account, report)], live=session.ended_at is None), filename="session.png"),
        caption=(
            "🔴 <b>Сессия идёт</b>"
            if session.ended_at is None and session.offline_since is None
            else "🟠 <b>Аккаунт вышел — ждём 30 минут</b>"
            if session.ended_at is None
            else "✅ <b>Завершённая игровая сессия</b>"
        ),
    )
    await query.message.edit_media(media, reply_markup=session_keyboard())
    await query.answer()


async def send_report(
    message: Message,
    user_id: int,
    account_id: int,
    start_at: datetime,
    end_at: datetime,
    *,
    page: int = 0,
    navigation: str | None = None,
) -> None:
    accounts_list = store.list_accounts(user_id) if account_id == 0 else []
    if account_id != 0:
        account = store.get_account(account_id, user_id)
        if account:
            accounts_list = [account]
    reports = []
    for account in accounts_list:
        report = store.period_report(account.id, start_at, end_at)
        if report:
            reports.append((account, report))
    if not reports:
        await edit_screen(message, "Для этого периода пока недостаточно снимков. Нужно минимум две точки.")
        return
    base_keyboard = all_accounts_keyboard() if account_id == 0 else account_keyboard(account_id)
    cards = render_progress_cards(reports)
    page = min(max(0, page), len(cards) - 1)
    prefix = navigation or f"report-page:{account_id}:1h"
    keyboard = report_keyboard(base_keyboard, prefix, page=page, page_count=len(cards))
    image = BufferedInputFile(cards[page], filename=f"skyblock-progress-{page + 1}.png")
    if message.photo:
        await message.edit_media(InputMediaPhoto(media=image), reply_markup=keyboard)
    else:
        await message.answer_photo(image, caption="Отчёт по выбранному периоду", reply_markup=keyboard)


@router.callback_query(F.data.startswith("period:"))
async def preset_period(query: CallbackQuery) -> None:
    _, account_id, code = query.data.split(":")
    end_at = datetime.now(UTC)
    await send_report(
        query.message,
        query.from_user.id,
        int(account_id),
        end_at - duration(code),
        end_at,
        navigation=f"report-page:{account_id}:{code}",
    )
    await query.answer()


@router.callback_query(F.data.startswith("report-page:"))
async def preset_report_page(query: CallbackQuery) -> None:
    _, account_id, code, page = query.data.split(":")
    end_at = datetime.now(UTC)
    await send_report(
        query.message,
        query.from_user.id,
        int(account_id),
        end_at - duration(code),
        end_at,
        page=int(page),
        navigation=f"report-page:{account_id}:{code}",
    )
    await query.answer()


@router.callback_query(F.data.startswith("custom:"))
async def custom_begin(query: CallbackQuery, state: FSMContext) -> None:
    account_id = int(query.data.split(":")[1])
    if account_id != 0 and store.get_account(account_id, query.from_user.id) is None:
        await query.answer("Аккаунт не найден", show_alert=True)
        return
    await state.set_state(CustomPeriod.value)
    await state.update_data(account_id=account_id)
    await edit_screen(query.message, "Введи период по МСК:\n<code>04.09.2026 18:30 - 04.09.2026 21:45</code>")
    await query.answer()


@router.message(CustomPeriod.value)
async def custom_value(message: Message, state: FSMContext) -> None:
    try:
        start_at, end_at = parse_custom_period(message.text or "")
    except ValueError as exc:
        await message.answer(str(exc))
        return
    account_id = int((await state.get_data())["account_id"])
    await state.clear()
    navigation = f"custom-page:{account_id}:{int(start_at.timestamp())}:{int(end_at.timestamp())}"
    await send_report(
        message,
        message.from_user.id,
        account_id,
        start_at,
        end_at,
        navigation=navigation,
    )


@router.callback_query(F.data.startswith("custom-page:"))
async def custom_report_page(query: CallbackQuery) -> None:
    _, account_id, start_timestamp, end_timestamp, page = query.data.split(":")
    start_at = datetime.fromtimestamp(int(start_timestamp), UTC)
    end_at = datetime.fromtimestamp(int(end_timestamp), UTC)
    navigation = f"custom-page:{account_id}:{start_timestamp}:{end_timestamp}"
    await send_report(
        query.message,
        query.from_user.id,
        int(account_id),
        start_at,
        end_at,
        page=int(page),
        navigation=navigation,
    )
    await query.answer()


@router.callback_query(F.data.startswith("refresh:"))
async def refresh(query: CallbackQuery) -> None:
    account_id = int(query.data.split(":")[1])
    account = store.get_account(account_id, query.from_user.id)
    if account:
        try:
            snapshot = await hypixel.fetch(account.id, account.uuid, account.profile_name)
            store.save_snapshot(snapshot)
            await edit_screen(query.message, current_text(account, snapshot), account_keyboard(account.id))
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            await edit_screen(query.message, f"Ошибка обновления: {exc}", account_keyboard(account.id))
    await query.answer()


@router.callback_query(F.data.startswith("delete:"))
async def delete(query: CallbackQuery) -> None:
    account_id = int(query.data.split(":")[1])
    store.delete_account(account_id, query.from_user.id)
    await edit_screen(query.message, "Аккаунт удалён из мониторинга.", main_keyboard())
    await query.answer()


async def poll_forever() -> None:
    interval = int(os.environ.get("POLL_INTERVAL_SECONDS", DEFAULT_POLL_INTERVAL_SECONDS))
    while True:
        started = datetime.now(UTC)
        for account in store.list_accounts():
            try:
                snapshot = await hypixel.fetch(account.id, account.uuid, account.profile_name)
                store.save_snapshot(snapshot)
            except (httpx.HTTPError, ValueError, KeyError):
                log.exception("Failed to update %s/%s", account.username, account.profile_name)
                continue
            try:
                status = await hypixel.fetch_status(account.uuid)
                store.record_presence(account.id, is_skyblock_online(status), snapshot.observed_at)
            except httpx.HTTPError:
                log.exception("Failed to update online status for %s", account.username)
        elapsed = (datetime.now(UTC) - started).total_seconds()
        await asyncio.sleep(max(1, interval - elapsed))


async def live_forever(bot: Bot) -> None:
    while True:
        await asyncio.sleep(120)
        for view in store.list_active_live_views():
            try:
                await update_live_message(bot, view)
            except TelegramBadRequest as exc:
                if is_message_not_modified(exc):
                    continue
                log.warning("Stopping live view %s after Telegram edit failure: %s", view.id, exc)
                store.stop_live_view(view.id)
            except Exception:
                log.exception("Failed to update live view %s", view.id)


async def run() -> None:
    global store, hypixel
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    db_path = Path(os.environ.get("DATABASE_PATH", "data/monitor.db"))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    store = Store(db_path)
    daily_limit = int(os.environ.get("HYPIXEL_DAILY_REQUEST_LIMIT", DEFAULT_DAILY_REQUEST_LIMIT))
    hypixel = HypixelClient(
        os.environ["HYPIXEL_API_KEY"],
        reserve_request=lambda: store.reserve_hypixel_request(datetime.now(UTC), daily_limit),
    )
    bot = Bot(token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.include_router(router)
    poller = asyncio.create_task(poll_forever())
    live_updater = asyncio.create_task(live_forever(bot))
    try:
        await dispatcher.start_polling(bot)
    finally:
        poller.cancel()
        live_updater.cancel()
        await bot.session.close()


def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    asyncio.run(run())
