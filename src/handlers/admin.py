"""Admin panel handlers: subscriptions, broadcast, ban, promocodes."""
import asyncio

from aiogram import F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from src.keyboards import get_admin_menu, get_admin_promocode_menu, get_back_button
from src.core.config import config

from .common import router, get_db, AdminState, AdminPriceState


def _is_admin(user_id: int) -> bool:
    return user_id == config.ADMIN_ID


@router.callback_query(F.data == "admin_panel")
async def cb_admin_panel(call: CallbackQuery):
    await call.answer()
    if not _is_admin(call.from_user.id):
        await call.message.edit_text("❌ Доступ запрещен.", reply_markup=get_back_button())
        return
    await call.message.edit_text(
        "⚙️ <b>Админ-панель</b>\n\nВыберите опцию:",
        reply_markup=get_admin_menu(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin_give_sub")
async def cb_admin_give_sub(call: CallbackQuery, state: FSMContext):
    await call.answer()
    if not _is_admin(call.from_user.id):
        return
    await state.set_state(AdminState.waiting_for_user_and_days)
    await call.message.edit_text(
        "✍️ Введите <b>ID или @username</b> и <b>дней</b> через пробел.\n"
        "<i>Пример: 123456789 30</i>",
        reply_markup=get_back_button("admin_panel"),
        parse_mode="HTML"
    )


@router.message(AdminState.waiting_for_user_and_days)
async def process_admin_give_sub(message: Message, state: FSMContext):
    parts = message.text.strip().split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("❌ Неверный формат!")
        return
    target_user, days = parts[0], int(parts[1])
    success = await get_db().give_subscription_by_identifier(target_user, days)
    if success:
        await message.answer(f"✅ Подписка для <b>{target_user}</b> продлена на <b>{days} дней</b>!", parse_mode="HTML")
    else:
        await message.answer("❌ Пользователь не найден.")
    await state.clear()


@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(call: CallbackQuery):
    await call.answer()
    if not _is_admin(call.from_user.id):
        return

    total = await get_db().get_total_users_count()
    active = await get_db().get_active_users_count()
    paying = await get_db().get_paying_users_count()

    cursor = await get_db().connection.execute("SELECT COUNT(*) FROM searches")
    row = await cursor.fetchone()
    total_searches = row[0] if row else 0
    
    cursor = await get_db().connection.execute("SELECT COUNT(*) FROM searches WHERE is_active = TRUE")
    row = await cursor.fetchone()
    active_searches = row[0] if row else 0
    
    cursor = await get_db().connection.execute("SELECT COUNT(*) FROM sent_ads")
    row = await cursor.fetchone()
    total_ads = row[0] if row else 0

    await call.message.edit_text(
        f"📊 <b>Статистика бота</b>\n\n"
        f"👥 Всего пользователей: <b>{total}</b>\n"
        f"🟢 Активных: <b>{active}</b>\n"
        f"💎 Pro-подписчиков: <b>{paying}</b>\n\n"
        f"🔍 Всего поисков: <b>{total_searches}</b>\n"
        f"🟢 Активных поисков: <b>{active_searches}</b>\n"
        f"📨 Отправлено объявлений: <b>{total_ads}</b>",
        reply_markup=get_back_button("admin_panel"),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin_broadcast")
async def cb_admin_broadcast(call: CallbackQuery, state: FSMContext):
    await call.answer()
    if not _is_admin(call.from_user.id):
        return
    await state.set_state(AdminState.waiting_for_broadcast)
    await call.message.edit_text(
        "📢 <b>Рассылка</b>\n\nВведите текст для отправки всем пользователям:",
        reply_markup=get_back_button("admin_panel"),
        parse_mode="HTML"
    )


@router.message(AdminState.waiting_for_broadcast)
async def process_admin_broadcast(message: Message, state: FSMContext):
    await state.clear()
    if not _is_admin(message.from_user.id):
        return

    text = message.text
    users = await get_db().get_all_users()
    sent, failed = 0, 0

    for user in users:
        if user.get("is_banned"):
            continue
        try:
            await message.bot.send_message(
                chat_id=user["user_id"],
                text=f"📢 <b>Сообщение от администратора:</b>\n\n{text}",
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1

    await message.answer(
        f"✅ Рассылка завершена.\nОтправлено: <b>{sent}</b>\nОшибок: <b>{failed}</b>",
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin_ban_menu")
async def cb_admin_ban_menu(call: CallbackQuery, state: FSMContext):
    await call.answer()
    if not _is_admin(call.from_user.id):
        return
    await state.set_state(AdminState.waiting_for_ban_user)
    await call.message.edit_text(
        "🚫 <b>Бан / Разбан</b>\n\n"
        "Введите <b>ID пользователя</b> и действие через пробел:\n"
        "<i>Пример: 123456789 ban</i> или <i>123456789 unban</i>",
        reply_markup=get_back_button("admin_panel"),
        parse_mode="HTML"
    )


@router.message(AdminState.waiting_for_ban_user)
async def process_admin_ban(message: Message, state: FSMContext):
    await state.clear()
    if not _is_admin(message.from_user.id):
        return

    parts = message.text.strip().split()
    if len(parts) != 2 or not parts[0].isdigit():
        await message.answer("❌ Неверный формат! Пример: 123456789 ban")
        return

    target_id, action = int(parts[0]), parts[1].lower()
    if action == "ban":
        await get_db().ban_user(target_id)
        await message.answer(f"🚫 Пользователь <b>{target_id}</b> забанен.", parse_mode="HTML")
    elif action == "unban":
        await get_db().unban_user(target_id)
        await message.answer(f"✅ Пользователь <b>{target_id}</b> разбанен.", parse_mode="HTML")
    else:
        await message.answer("❌ Неизвестное действие. Используйте ban или unban.")


# ── Admin Promocodes ───────────────────────────────

@router.callback_query(F.data == "admin_promocodes")
async def cb_admin_promocodes(call: CallbackQuery):
    await call.answer()
    if not _is_admin(call.from_user.id):
        return
    await call.message.edit_text(
        "🎟 <b>Управление промокодами</b>",
        reply_markup=get_admin_promocode_menu(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin_create_promo")
async def cb_admin_create_promo(call: CallbackQuery, state: FSMContext):
    await call.answer()
    if not _is_admin(call.from_user.id):
        return
    await state.set_state(AdminState.waiting_for_promo_create)
    await call.message.edit_text(
        "➕ <b>Создание промокода</b>\n\n"
        "Введите данные через пробел:\n"
        "<code>КОД дней max_uses</code>\n"
        "<i>Пример: SUMMER2025 30 100</i>\n"
        "(max_uses = -1 для безлимита)",
        reply_markup=get_back_button("admin_promocodes"),
        parse_mode="HTML"
    )


@router.message(AdminState.waiting_for_promo_create)
async def process_admin_create_promo(message: Message, state: FSMContext):
    await state.clear()
    if not _is_admin(message.from_user.id):
        return

    parts = message.text.strip().split()
    if len(parts) < 2:
        await message.answer("❌ Неверный формат!")
        return

    code = parts[0].upper()
    try:
        days = int(parts[1])
        max_uses = int(parts[2]) if len(parts) > 2 else -1
    except ValueError:
        await message.answer("❌ Дни и лимит должны быть числами!")
        return

    success = await get_db().create_promocode(code, days, max_uses)
    if success:
        await message.answer(
            f"✅ Промокод <b>{code}</b> создан!\nДней: {days}\nЛимит: {'∞' if max_uses < 0 else max_uses}",
            parse_mode="HTML"
        )
    else:
        await message.answer("❌ Промокод с таким кодом уже существует!")


@router.callback_query(F.data == "admin_list_promo")
async def cb_admin_list_promo(call: CallbackQuery):
    await call.answer()
    if not _is_admin(call.from_user.id):
        return

    promos = await get_db().list_promocodes()
    if not promos:
        await call.message.edit_text(
            "📭 Промокодов пока нет.",
            reply_markup=get_back_button("admin_promocodes"),
            parse_mode="HTML"
        )
        return

    lines = ["📋 <b>Промокоды:</b>\n"]
    for p in promos:
        status = "🟢" if p["is_active"] else "🔴"
        limit = f"{p['used_count']}/{p['max_uses']}" if p["max_uses"] >= 0 else f"{p['used_count']}/∞"
        lines.append(f"{status} <code>{p['code']}</code> — {p['days']}дн. ({limit})")

    await call.message.edit_text(
        "\n".join(lines),
        reply_markup=get_back_button("admin_promocodes"),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin_delete_promo")
async def cb_admin_delete_promo(call: CallbackQuery, state: FSMContext):
    await call.answer()
    if not _is_admin(call.from_user.id):
        return
    await state.set_state(AdminState.waiting_for_promo_delete)
    await call.message.edit_text(
        "🗑 Введите код промокода для удаления:",
        reply_markup=get_back_button("admin_promocodes"),
        parse_mode="HTML"
    )


@router.message(AdminState.waiting_for_promo_delete)
async def process_admin_delete_promo(message: Message, state: FSMContext):
    await state.clear()
    if not _is_admin(message.from_user.id):
        return

    code = message.text.strip().upper()
    success = await get_db().delete_promocode(code)
    if success:
        await message.answer(f"✅ Промокод <b>{code}</b> удалён!", parse_mode="HTML")
    else:
        await message.answer("❌ Промокод не найден.")


# ── Admin Change Subscription Price ──────────────────────

@router.callback_query(F.data == "admin_change_price")
async def cb_admin_change_price(call: CallbackQuery, state: FSMContext):
    await call.answer()
    if not _is_admin(call.from_user.id):
        return
    await state.set_state(AdminPriceState.waiting_for_plan_price)
    await call.message.edit_text(
        "💳 <b>Изменение стоимости подписки</b>\n\n"
        "Введите данные через пробел:\n"
        "<code>тариф цена</code>\n"
        "<i>Пример: basic 200</i> или <i>pro 500</i>\n"
        "<i>Доступные тарифы: basic, pro</i>",
        reply_markup=get_back_button("admin_panel"),
        parse_mode="HTML"
    )


@router.message(AdminPriceState.waiting_for_plan_price)
async def process_admin_change_price(message: Message, state: FSMContext):
    await state.clear()
    if not _is_admin(message.from_user.id):
        return

    from src.data.tariffs import PLANS

    parts = message.text.strip().split()
    if len(parts) != 2:
        await message.answer("❌ Неверный формат! Пример: basic 200")
        return

    plan_key, price_str = parts[0].lower(), parts[1]
    
    if plan_key not in PLANS:
        available = ", ".join(PLANS.keys())
        await message.answer(f"❌ Тариф не найден. Доступные: {available}")
        return
    
    try:
        new_price = int(price_str)
        if new_price <= 0:
            await message.answer("❌ Цена должна быть больше 0!")
            return
    except ValueError:
        await message.answer("❌ Цена должна быть числом!")
        return

    plan = PLANS[plan_key]
    old_price = plan.price_stars
    
    # Update the plan price in memory
    plan.price_stars = new_price

    await message.answer(
        f"✅ Стоимость подписки <b>{plan.name}</b> изменена!\n\n"
        f"Старая цена: <b>{old_price}⭐</b>\n"
        f"Новая цена: <b>{new_price}⭐</b>",
        parse_mode="HTML"
    )
