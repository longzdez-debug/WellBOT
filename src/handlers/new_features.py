"""New features handlers: language, badges, quiet hours, photos only, channels."""
import logging

from aiogram import F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from src.keyboards import (
    get_language_menu, get_badges_menu, get_quiet_hours_menu,
    get_only_photos_menu, get_search_with_channel, get_back_button
)
from src.data.locales import get_locale, t
from src.core.config import config

from .common import router, get_db, logger

# ── FSM States ─────────────────────────────────────

class QuietHoursState(StatesGroup):
    waiting_for_start = State()
    waiting_for_end = State()

class ChannelState(StatesGroup):
    waiting_for_channel = State()


# ── Language ──────────────────────────────────────

@router.callback_query(F.data == "language_menu")
async def cb_language_menu(call: CallbackQuery):
    await call.answer()
    await call.message.edit_text(
        get_locale(await get_db().get_user_language(call.from_user.id))["language_select"],
        reply_markup=get_language_menu(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("lang_"))
async def cb_set_language(call: CallbackQuery):
    await call.answer()
    language = call.data.replace("lang_", "")
    await get_db().set_user_language(call.from_user.id, language)
    locale = get_locale(language)
    await call.message.edit_text(
        locale["language_select"],
        reply_markup=get_language_menu(),
        parse_mode="HTML"
    )


# ── Badges ───────────────────────────────────────

@router.callback_query(F.data == "badges")
async def cb_badges(call: CallbackQuery):
    await call.answer()
    badges = await get_db().get_user_badges(call.from_user.id)
    locale = get_locale(await get_db().get_user_language(call.from_user.id))
    
    if badges:
        badges_text = "\n".join(
            f"{b['icon']} <b>{b['name']}</b> — {b['description']}\n   📅 {b['earned_at']}"
            for b in badges
        )
    else:
        badges_text = "У вас пока нет бейджей. Создайте поиск или пригласите друга!"
    
    await call.message.edit_text(
        f"🏆 <b>Ваши бейджи</b>\n\n{badges_text}",
        reply_markup=get_back_button("main_menu"),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "badges_list")
async def cb_badges_list(call: CallbackQuery):
    await cb_badges(call)


@router.callback_query(F.data == "badges_howto")
async def cb_badges_howto(call: CallbackQuery):
    await call.answer()
    locale = get_locale(await get_db().get_user_language(call.from_user.id))
    await call.message.edit_text(
        "🏆 <b>Как заработать бейджи?</b>\n\n"
        "🔍 Первый шаг — создайте первый поиск\n"
        "🗺 Исследователь — создайте 10 поисков\n"
        "🎯 Профи поиска — создайте 50 поисков\n"
        "🎉 Первая находка — получите первое уведомление\n"
        "📦 Коллекционер — получите 100 уведомлений\n"
        "🤝 Коммуникабельный — пригласите друга\n"
        "👑 Лидер мнений — пригласите 5 друзей\n"
        "💎 Pro подписчик — оформите подписку Pro\n"
        "⭐ VIP клиент — Pro + 200 уведомлений",
        reply_markup=get_back_button("badges"),
        parse_mode="HTML"
    )


# ── Quiet Hours ──────────────────────────────────

@router.callback_query(F.data == "quiet_hours_menu")
async def cb_quiet_hours_menu(call: CallbackQuery):
    await call.answer()
    locale = get_locale(await get_db().get_user_language(call.from_user.id))
    await call.message.edit_text(
        locale["quiet_hours_menu"],
        reply_markup=get_quiet_hours_menu(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "quiet_hours_set")
async def cb_quiet_hours_set(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.set_state(QuietHoursState.waiting_for_start)
    locale = get_locale(await get_db().get_user_language(call.from_user.id))
    current_start, current_end = await get_db().get_quiet_hours(call.from_user.id)
    await call.message.edit_text(
        locale["quiet_hours"].format(start=current_start, end=current_end),
        reply_markup=get_back_button("quiet_hours_menu"),
        parse_mode="HTML"
    )


@router.message(QuietHoursState.waiting_for_start)
async def process_quiet_hours_start(message: Message, state: FSMContext):
    try:
        start_hour = int(message.text.strip())
        if not 0 <= start_hour <= 23:
            await message.answer("❌ Введите число от 0 до 23.")
            return
        await state.update_data(quiet_start=start_hour)
        await state.set_state(QuietHoursState.waiting_for_end)
        locale = get_locale(await get_db().get_user_language(message.from_user.id))
        await message.answer(locale["quiet_hours_end"], reply_markup=get_back_button("quiet_hours_menu"))
    except ValueError:
        await message.answer("❌ Введите число от 0 до 23.")


@router.message(QuietHoursState.waiting_for_end)
async def process_quiet_hours_end(message: Message, state: FSMContext):
    try:
        end_hour = int(message.text.strip())
        if not 0 <= end_hour <= 23:
            await message.answer("❌ Введите число от 0 до 23.")
            return
        data = await state.get_data()
        await get_db().set_quiet_hours(message.from_user.id, data["quiet_start"], end_hour)
        await state.clear()
        locale = get_locale(await get_db().get_user_language(message.from_user.id))
        await message.answer(
            locale["quiet_hours_set"].format(start=data["quiet_start"], end=end_hour),
            reply_markup=get_back_button("main_menu"),
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer("❌ Введите число от 0 до 23.")


# ── Photos Only ──────────────────────────────────

@router.callback_query(F.data == "only_photos_menu")
async def cb_only_photos_menu(call: CallbackQuery):
    await call.answer()
    locale = get_locale(await get_db().get_user_language(call.from_user.id))
    await call.message.edit_text(
        locale["only_photos_menu"],
        reply_markup=get_only_photos_menu(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "only_photos_on")
async def cb_only_photos_on(call: CallbackQuery):
    await call.answer()
    locale = get_locale(await get_db().get_user_language(call.from_user.id))
    await call.message.edit_text(
        locale["only_photos_on"],
        reply_markup=get_back_button("main_menu"),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "only_photos_off")
async def cb_only_photos_off(call: CallbackQuery):
    await call.answer()
    locale = get_locale(await get_db().get_user_language(call.from_user.id))
    await call.message.edit_text(
        locale["only_photos_off"],
        reply_markup=get_back_button("main_menu"),
        parse_mode="HTML"
    )


# ── Channel Mode ─────────────────────────────────

@router.callback_query(F.data.startswith("channel_set_"))
async def cb_channel_set(call: CallbackQuery, state: FSMContext):
    await call.answer()
    search_id = int(call.data.replace("channel_set_", ""))
    await state.set_state(ChannelState.waiting_for_channel)
    await state.update_data(search_id=search_id)
    await call.message.edit_text(
        "📢 <b>Канал/группа</b>\n\nВведите имя канала (@channel) или ID:",
        reply_markup=get_back_button("my_searches"),
        parse_mode="HTML"
    )


@router.message(ChannelState.waiting_for_channel)
async def process_channel_set(message: Message, state: FSMContext):
    data = await state.get_data()
    search_id = data["search_id"]
    channel_input = message.text.strip().lstrip("@")
    try:
        # Проверяем, существует ли канал и может ли бот отправлять туда сообщения
        channel_id = int(channel_input) if channel_input.isdigit() else channel_input
        
        # Проверяем доступность канала
        try:
            # Пытаемся получить информацию о канале
            chat = await message.bot.get_chat(channel_id)
            # Проверяем, что это канал или группа
            if chat.type not in ["channel", "group", "supergroup"]:
                await message.answer(
                    "❌ Это не канал и не группа. Пожалуйста, отправьте имя канала (с @) или его ID.",
                    reply_markup=get_back_button("my_searches"),
                    parse_mode="HTML"
                )
                return
            
            # Проверяем, может ли бот отправлять сообщения
            try:
                await message.bot.send_message(channel_id, "✅ Бот успешно подключён к каналу! Теперь сюда будут приходить уведомления.")
            except Exception:
                await message.answer(
                    "❌ Бот не может отправлять сообщения в этот канал. Убедитесь, что бот добавлен в канал и имеет права на отправку сообщений.",
                    reply_markup=get_back_button("my_searches"),
                    parse_mode="HTML"
                )
                return
                
        except Exception as e:
            error_msg = str(e).lower()
            if "chat not found" in error_msg or "user not found" in error_msg:
                await message.answer(
                    "❌ Канал не найден. Убедитесь, что вы правильно ввели имя канала (с @) или ID, и что бот добавлен в канал.",
                    reply_markup=get_back_button("my_searches"),
                    parse_mode="HTML"
                )
            else:
                await message.answer(
                    f"❌ Не удалось проверить канал: {e}",
                    reply_markup=get_back_button("my_searches"),
                    parse_mode="HTML"
                )
            return
        
        await get_db().add_channel_for_search(search_id, message.from_user.id, channel_id)
        await state.clear()
        await message.answer(
            "✅ Канал установлен для этого поиска!",
            reply_markup=get_back_button("my_searches"),
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer(
            "❌ Неверный формат. Введите ID канала (число) или имя (с @).",
            reply_markup=get_back_button("my_searches"),
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@router.callback_query(F.data.startswith("channel_remove_"))
async def cb_channel_remove(call: CallbackQuery):
    await call.answer()
    search_id = int(call.data.replace("channel_remove_", ""))
    await get_db().add_channel_for_search(search_id, call.from_user.id, None)
    await call.message.edit_text(
        "✅ Канал удалён из этого поиска!",
        reply_markup=get_back_button("my_searches"),
        parse_mode="HTML"
    )
