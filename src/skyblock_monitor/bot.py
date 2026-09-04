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
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from .cards import render_progress_card
from .hypixel import HypixelClient
from .presentation import MOSCOW, parse_custom_period
from .store import Store

log = logging.getLogger(__name__)
router = Router()
store: Store
hypixel: HypixelClient


class AddAccount(StatesGroup):
    username = State()
    profile = State()


class CustomPeriod(StatesGroup):
    value = State()


def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
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


@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Мониторинг прогресса Hypixel SkyBlock", reply_markup=main_keyboard())


@router.callback_query(F.data == "home")
async def home(query: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await query.message.answer("Главное меню", reply_markup=main_keyboard())
    await query.answer()


@router.callback_query(F.data == "all")
async def all_accounts(query: CallbackQuery) -> None:
    if not store.list_accounts(query.from_user.id):
        await query.message.answer("Пока нет добавленных аккаунтов.", reply_markup=main_keyboard())
    else:
        await query.message.answer("Выбери период для всех аккаунтов:", reply_markup=all_accounts_keyboard())
    await query.answer()


@router.callback_query(F.data == "add")
async def add_begin(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddAccount.username)
    await query.message.answer("Напиши Minecraft-ник:")
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
        await query.message.answer("Пока нет добавленных аккаунтов.", reply_markup=main_keyboard())
    else:
        keyboard = [[InlineKeyboardButton(text=f"{a.username} / {a.profile_name}", callback_data=f"account:{a.id}")]
                    for a in accounts_list]
        keyboard.append([InlineKeyboardButton(text="➕ Добавить аккаунт", callback_data="add")])
        await query.message.answer("Выбери аккаунт:", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    await query.answer()


@router.callback_query(F.data.startswith("account:"))
async def show_account(query: CallbackQuery) -> None:
    account_id = int(query.data.split(":")[1])
    account = store.get_account(account_id, query.from_user.id)
    if account:
        await query.message.answer(current_text(account, store.latest_snapshot(account.id)), reply_markup=account_keyboard(account.id))
    await query.answer()


async def send_report(message: Message, user_id: int, account_id: int, start_at: datetime, end_at: datetime) -> None:
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
        await message.answer("Для этого периода пока недостаточно снимков. Нужно минимум две точки.")
        return
    image = render_progress_card(reports)
    keyboard = all_accounts_keyboard() if account_id == 0 else account_keyboard(account_id)
    await message.answer_photo(BufferedInputFile(image, filename="skyblock-progress.png"), reply_markup=keyboard)


@router.callback_query(F.data.startswith("period:"))
async def preset_period(query: CallbackQuery) -> None:
    _, account_id, code = query.data.split(":")
    end_at = datetime.now(UTC)
    await send_report(query.message, query.from_user.id, int(account_id), end_at - duration(code), end_at)
    await query.answer()


@router.callback_query(F.data.startswith("custom:"))
async def custom_begin(query: CallbackQuery, state: FSMContext) -> None:
    account_id = int(query.data.split(":")[1])
    if account_id != 0 and store.get_account(account_id, query.from_user.id) is None:
        await query.answer("Аккаунт не найден", show_alert=True)
        return
    await state.set_state(CustomPeriod.value)
    await state.update_data(account_id=account_id)
    await query.message.answer("Введи период по МСК:\n<code>04.09.2026 18:30 - 04.09.2026 21:45</code>")
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
    await send_report(message, message.from_user.id, account_id, start_at, end_at)


@router.callback_query(F.data.startswith("refresh:"))
async def refresh(query: CallbackQuery) -> None:
    account_id = int(query.data.split(":")[1])
    account = store.get_account(account_id, query.from_user.id)
    if account:
        try:
            snapshot = await hypixel.fetch(account.id, account.uuid, account.profile_name)
            store.save_snapshot(snapshot)
            await query.message.answer(current_text(account, snapshot), reply_markup=account_keyboard(account.id))
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            await query.message.answer(f"Ошибка обновления: {exc}")
    await query.answer()


@router.callback_query(F.data.startswith("delete:"))
async def delete(query: CallbackQuery) -> None:
    account_id = int(query.data.split(":")[1])
    store.delete_account(account_id, query.from_user.id)
    await query.message.answer("Аккаунт удалён из мониторинга.", reply_markup=main_keyboard())
    await query.answer()


async def poll_forever() -> None:
    while True:
        started = datetime.now(UTC)
        for account in store.list_accounts():
            try:
                store.save_snapshot(await hypixel.fetch(account.id, account.uuid, account.profile_name))
            except (httpx.HTTPError, ValueError, KeyError):
                log.exception("Failed to update %s/%s", account.username, account.profile_name)
        elapsed = (datetime.now(UTC) - started).total_seconds()
        await asyncio.sleep(max(1, 60 - elapsed))


async def run() -> None:
    global store, hypixel
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    hypixel = HypixelClient(os.environ["HYPIXEL_API_KEY"])
    db_path = Path(os.environ.get("DATABASE_PATH", "data/monitor.db"))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    store = Store(db_path)
    bot = Bot(token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.include_router(router)
    poller = asyncio.create_task(poll_forever())
    try:
        await dispatcher.start_polling(bot)
    finally:
        poller.cancel()
        await bot.session.close()


def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    asyncio.run(run())
