"""Support system with anonymous tickets."""
import asyncio
import logging
from datetime import datetime

from aiogram import F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from src.core.config import config
from src.keyboards import get_back_button
from .common import router, get_db, logger


# ── FSM States ─────────────────────────────────────

class SupportState(StatesGroup):
    waiting_for_message = State()
    waiting_for_reply = State()


# ── Database functions ────────────────────────────

async def create_ticket(user_id: int, username: str, message: str) -> int:
    """Создаёт новое обращение."""
    db = get_db()
    cursor = await db.connection.execute(
        """INSERT INTO support_tickets (user_id, username, message, status, created_at)
           VALUES (?, ?, ?, 'open', CURRENT_TIMESTAMP)""",
        (user_id, username, message)
    )
    await db.connection.commit()
    return cursor.lastrowid


async def get_ticket(ticket_id: int) -> dict:
    """Получает обращение по ID."""
    db = get_db()
    cursor = await db.connection.execute(
        "SELECT * FROM support_tickets WHERE id = ?",
        (ticket_id,)
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def get_all_tickets(status: str = None) -> list:
    """Получает все обращения."""
    db = get_db()
    if status:
        cursor = await db.connection.execute(
            "SELECT * FROM support_tickets WHERE status = ? ORDER BY created_at DESC",
            (status,)
        )
    else:
        cursor = await db.connection.execute(
            "SELECT * FROM support_tickets ORDER BY created_at DESC"
        )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def get_user_tickets(user_id: int) -> list:
    """Получает обращения пользователя."""
    db = get_db()
    cursor = await db.connection.execute(
        "SELECT * FROM support_tickets WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,)
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def close_ticket(ticket_id: int):
    """Закрывает обращение."""
    db = get_db()
    await db.connection.execute(
        "UPDATE support_tickets SET status = 'closed', closed_at = CURRENT_TIMESTAMP WHERE id = ?",
        (ticket_id,)
    )
    await db.connection.commit()


async def reopen_ticket(ticket_id: int):
    """Открывает обращение заново."""
    db = get_db()
    await db.connection.execute(
        "UPDATE support_tickets SET status = 'open', closed_at = NULL WHERE id = ?",
        (ticket_id,)
    )
    await db.connection.commit()


async def add_reply(ticket_id: int, admin_id: int, message: str):
    """Добавляет ответ."""
    db = get_db()
    await db.connection.execute(
        """INSERT INTO support_replies (ticket_id, admin_id, message, created_at)
           VALUES (?, ?, ?, CURRENT_TIMESTAMP)""",
        (ticket_id, admin_id, message)
    )
    await db.connection.commit()


async def get_replies(ticket_id: int) -> list:
    """Получает все ответы."""
    db = get_db()
    cursor = await db.connection.execute(
        "SELECT * FROM support_replies WHERE ticket_id = ? ORDER BY created_at",
        (ticket_id,)
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


def _is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором."""
    return user_id == config.ADMIN_ID


# ── User Handlers ──────────────────────────────────

@router.callback_query(F.data == "support_new")
async def cb_support_start(call: CallbackQuery, state: FSMContext):
    """Начало обращения в поддержку."""
    await call.answer()
    await state.set_state(SupportState.waiting_for_message)
    
    # Показываем последние обращения пользователя
    tickets = await get_user_tickets(call.from_user.id)
    
    text = "💬 <b>Поддержка</b>\n\n"
    if tickets:
        text += "📋 <b>Ваши обращения:</b>\n"
        for t in tickets[:3]:
            status_icon = "🟢" if t["status"] == "open" else "🔴"
            text += f"{status_icon} #{t['id']} — {t['status']} ({t['created_at'][:10]})\n"
        text += "\n"
    
    text += "Опишите вашу проблему или вопрос.\n"
    text += "Администратор ответит вам в ближайшее время.\n\n"
    text += "✏️ Напишите ваше сообщение:"
    
    await call.message.edit_text(
        text,
        reply_markup=get_back_button("main_menu"),
        parse_mode="HTML"
    )


@router.message(SupportState.waiting_for_message)
async def process_support_message(message: Message, state: FSMContext):
    """Обработка сообщения от пользователя."""
    user_id = message.from_user.id
    username = message.from_user.username or f"User{user_id}"
    msg_text = message.text
    
    if not msg_text or len(msg_text) < 3:
        await message.answer(
            "❌ Сообщение слишком короткое. Напишите хотя бы 3 символа.",
            reply_markup=get_back_button("main_menu"),
            parse_mode="HTML"
        )
        return
    
    if len(msg_text) > 1000:
        await message.answer(
            "❌ Сообщение слишком длинное (максимум 1000 символов).",
            reply_markup=get_back_button("main_menu"),
            parse_mode="HTML"
        )
        return
    
    # Создаём обращение
    ticket_id = await create_ticket(user_id, username, msg_text)
    
    # Уведомляем администратора
    admin_id = config.ADMIN_ID
    if admin_id:
        try:
            admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📝 Ответить", callback_data=f"support_reply_{ticket_id}")],
                [InlineKeyboardButton(text="❌ Закрыть", callback_data=f"support_close_{ticket_id}")],
                [InlineKeyboardButton(text="📋 Все обращения", callback_data="admin_tickets")]
            ])
            
            await message.bot.send_message(
                admin_id,
                f"🆕 <b>Новое обращение в поддержку!</b>\n\n"
                f"📋 ID: <code>#{ticket_id}</code>\n"
                f"👤 Пользователь: <a href='tg://user?id={user_id}'>{username}</a>\n"
                f"🆔 User ID: <code>{user_id}</code>\n"
                f"📝 Сообщение:\n{msg_text}\n\n"
                f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}",
                reply_markup=admin_keyboard,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить администратора: {e}")
    
    await state.clear()
    
    # Кнопка для пользователя
    user_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Мои обращения", callback_data="my_tickets")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu")]
    ])
    
    await message.answer(
        "✅ <b>Ваше обращение отправлено!</b>\n\n"
        f"📋 Номер обращения: <code>#{ticket_id}</code>\n"
        "Администратор ответит вам в ближайшее время.\n\n"
        "Вы можете отслеживать статус обращения в разделе 'Мои обращения'.",
        reply_markup=user_keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data == "my_tickets")
async def cb_my_tickets(call: CallbackQuery):
    """Показывает обращения пользователя."""
    await call.answer()
    
    tickets = await get_user_tickets(call.from_user.id)
    
    if not tickets:
        await call.message.edit_text(
            "📭 У вас пока нет обращений.",
            reply_markup=get_back_button("main_menu"),
            parse_mode="HTML"
        )
        return
    
    text = "📋 <b>Мои обращения:</b>\n\n"
    for t in tickets[:10]:
        status_icon = "🟢" if t["status"] == "open" else "🔴"
        status_text = "Открыто" if t["status"] == "open" else "Закрыто"
        text += f"{status_icon} <b>#{t['id']}</b> — {status_text}\n"
        text += f"   📝 {t['message'][:50]}...\n"
        text += f"   📅 {t['created_at']}\n\n"
    
    # Кнопки для открытых обращений
    buttons = []
    for t in tickets[:5]:
        if t["status"] == "open":
            buttons.append([
                InlineKeyboardButton(
                    text=f"💬 Ответить в #{t['id']}",
                    callback_data=f"support_reply_user_{t['id']}"
                )
            ])
    
    if buttons:
        buttons.append([InlineKeyboardButton(text="◀️ Назад в меню", callback_data="main_menu")])
        markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    else:
        markup = get_back_button("main_menu")
    
    await call.message.edit_text(text, reply_markup=markup, parse_mode="HTML")


@router.callback_query(F.data.startswith("support_reply_user_"))
async def cb_user_reply_to_ticket(call: CallbackQuery, state: FSMContext):
    """Пользователь отвечает на сообщение поддержки."""
    await call.answer()
    
    ticket_id = int(call.data.replace("support_reply_user_", ""))
    ticket = await get_ticket(ticket_id)
    
    if not ticket or ticket["user_id"] != call.from_user.id:
        await call.message.answer("❌ Обращение не найдено.")
        return
    
    if ticket["status"] == "closed":
        # Предлагаем открыть заново
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Открыть заново", callback_data=f"support_reopen_{ticket_id}")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="my_tickets")]
        ])
        await call.message.edit_text(
            f"❌ Обращение #{ticket_id} уже закрыто.\n\n"
            "Вы можете открыть его заново, чтобы продолжить диалог.",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        return
    
    await state.set_state(SupportState.waiting_for_message)
    await state.update_data(ticket_id=ticket_id, reply_mode=True)
    
    await call.message.edit_text(
        f"💬 <b>Ответ на обращение #{ticket_id}</b>\n\n"
        f"📝 Ваше предыдущее сообщение:\n{ticket['message']}\n\n"
        f"✏️ Напишите ваш ответ:",
        reply_markup=get_back_button("my_tickets"),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("support_reopen_"))
async def cb_support_reopen(call: CallbackQuery):
    """Открывает обращение заново."""
    await call.answer()
    
    ticket_id = int(call.data.replace("support_reopen_", ""))
    ticket = await get_ticket(ticket_id)
    
    if not ticket or ticket["user_id"] != call.from_user.id:
        await call.message.answer("❌ Обращение не найдено.")
        return
    
    await reopen_ticket(ticket_id)
    
    # Уведомляем администратора
    admin_id = config.ADMIN_ID
    if admin_id:
        try:
            await call.bot.send_message(
                admin_id,
                f"🔄 Пользователь <b>{ticket['username']}</b> открыл заново обращение #{ticket_id}",
                parse_mode="HTML"
            )
        except Exception:
            pass
    
    await call.message.edit_text(
        f"✅ Обращение #{ticket_id} открыто заново!",
        reply_markup=get_back_button("my_tickets"),
        parse_mode="HTML"
    )


# ── Admin Handlers ─────────────────────────────────

@router.callback_query(F.data == "admin_tickets")
async def cb_admin_tickets(call: CallbackQuery):
    """Просмотр всех обращений для админа."""
    await call.answer()
    
    if not _is_admin(call.from_user.id):
        await call.message.answer("❌ Доступ запрещён.")
        return
    
    # Сначала показываем открытые
    open_tickets = await get_all_tickets("open")
    closed_tickets = await get_all_tickets("closed")
    
    text = "📋 <b>Управление обращениями</b>\n\n"
    text += f"🟢 Открытых: <b>{len(open_tickets)}</b>\n"
    text += f"🔴 Закрытых: <b>{len(closed_tickets)}</b>\n\n"
    
    if open_tickets:
        text += "📌 <b>Открытые обращения:</b>\n"
        for t in open_tickets[:5]:
            text += f"#{t['id']} | {t['username']} | {t['created_at'][:10]}\n"
            text += f"📝 {t['message'][:40]}...\n\n"
    else:
        text += "📭 Нет открытых обращений.\n"
    
    # Кнопки для админа
    buttons = [
        [InlineKeyboardButton(text="📋 Все открытые", callback_data="admin_tickets_open")],
        [InlineKeyboardButton(text="📋 Все закрытые", callback_data="admin_tickets_closed")],
        [InlineKeyboardButton(text="📋 ВСЕ обращения", callback_data="admin_tickets_all")],
    ]
    
    # Добавляем кнопки для быстрых ответов
    for t in open_tickets[:5]:
        buttons.append([
            InlineKeyboardButton(
                text=f"💬 Ответить #{t['id']} - {t['username']}",
                callback_data=f"support_reply_{t['id']}"
            )
        ])
    
    buttons.append([InlineKeyboardButton(text="◀️ Назад в админку", callback_data="admin_panel")])
    markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await call.message.edit_text(text, reply_markup=markup, parse_mode="HTML")


@router.callback_query(F.data == "admin_tickets_open")
async def cb_admin_tickets_open(call: CallbackQuery):
    """Показывает все открытые обращения."""
    await call.answer()
    
    if not _is_admin(call.from_user.id):
        return
    
    tickets = await get_all_tickets("open")
    
    if not tickets:
        await call.message.edit_text(
            "📭 Нет открытых обращений.",
            reply_markup=get_back_button("admin_tickets"),
            parse_mode="HTML"
        )
        return
    
    text = "🟢 <b>Открытые обращения:</b>\n\n"
    for t in tickets:
        text += f"#{t['id']} | {t['username']} | {t['created_at']}\n"
        text += f"📝 {t['message'][:60]}...\n\n"
    
    # Кнопки для ответа на каждое
    buttons = []
    for t in tickets[:5]:
        buttons.append([
            InlineKeyboardButton(
                text=f"💬 Ответить #{t['id']}",
                callback_data=f"support_reply_{t['id']}"
            ),
            InlineKeyboardButton(
                text=f"❌ Закрыть #{t['id']}",
                callback_data=f"support_close_{t['id']}"
            )
        ])
    
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_tickets")])
    markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await call.message.edit_text(text, reply_markup=markup, parse_mode="HTML")


@router.callback_query(F.data == "admin_tickets_closed")
async def cb_admin_tickets_closed(call: CallbackQuery):
    """Показывает все закрытые обращения."""
    await call.answer()
    
    if not _is_admin(call.from_user.id):
        return
    
    tickets = await get_all_tickets("closed")
    
    if not tickets:
        await call.message.edit_text(
            "📭 Нет закрытых обращений.",
            reply_markup=get_back_button("admin_tickets"),
            parse_mode="HTML"
        )
        return
    
    text = "🔴 <b>Закрытые обращения:</b>\n\n"
    for t in tickets[:10]:
        text += f"#{t['id']} | {t['username']} | {t['created_at'][:10]}\n"
        text += f"📝 {t['message'][:50]}...\n"
        if t.get('closed_at'):
            text += f"🔒 Закрыто: {t['closed_at']}\n"
        text += "\n"
    
    # Кнопка для открытия заново
    buttons = []
    for t in tickets[:5]:
        buttons.append([
            InlineKeyboardButton(
                text=f"🔄 Открыть #{t['id']}",
                callback_data=f"admin_reopen_{t['id']}"
            )
        ])
    
    if buttons:
        buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_tickets")])
        markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    else:
        markup = get_back_button("admin_tickets")
    
    await call.message.edit_text(text, reply_markup=markup, parse_mode="HTML")


@router.callback_query(F.data == "admin_tickets_all")
async def cb_admin_tickets_all(call: CallbackQuery):
    """Показывает все обращения."""
    await call.answer()
    
    if not _is_admin(call.from_user.id):
        return
    
    tickets = await get_all_tickets()
    
    if not tickets:
        await call.message.edit_text(
            "📭 Нет обращений.",
            reply_markup=get_back_button("admin_tickets"),
            parse_mode="HTML"
        )
        return
    
    text = "📋 <b>Все обращения:</b>\n\n"
    for t in tickets[:10]:
        status_icon = "🟢" if t["status"] == "open" else "🔴"
        text += f"{status_icon} #{t['id']} | {t['username']} | {t['created_at'][:10]}\n"
        text += f"📝 {t['message'][:40]}...\n\n"
    
    text += f"\n<i>Всего: {len(tickets)} обращений</i>"
    
    await call.message.edit_text(
        text,
        reply_markup=get_back_button("admin_tickets"),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("support_reply_"))
async def cb_support_reply(call: CallbackQuery, state: FSMContext):
    """Начало ответа на обращение."""
    await call.answer()
    
    if not _is_admin(call.from_user.id):
        await call.message.answer("❌ Доступ запрещён.")
        return
    
    ticket_id = int(call.data.replace("support_reply_", ""))
    ticket = await get_ticket(ticket_id)
    
    if not ticket:
        await call.message.answer("❌ Обращение не найдено.")
        return
    
    if ticket["status"] == "closed":
        await call.message.answer(
            "❌ Это обращение уже закрыто.",
            reply_markup=get_back_button("admin_tickets"),
            parse_mode="HTML"
        )
        return
    
    await state.set_state(SupportState.waiting_for_reply)
    await state.update_data(ticket_id=ticket_id)
    
    await call.message.edit_text(
        f"📝 <b>Ответ на обращение #{ticket_id}</b>\n\n"
        f"👤 Пользователь: <b>{ticket['username']}</b>\n"
        f"🆔 User ID: <code>{ticket['user_id']}</code>\n"
        f"📅 Создано: {ticket['created_at']}\n\n"
        f"📝 <b>Сообщение пользователя:</b>\n{ticket['message']}\n\n"
        f"✏️ Напишите ваш ответ:",
        reply_markup=get_back_button("admin_tickets"),
        parse_mode="HTML"
    )


@router.message(SupportState.waiting_for_reply)
async def process_support_reply(message: Message, state: FSMContext):
    """Отправка ответа пользователю."""
    if not _is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещён.")
        return
    
    data = await state.get_data()
    ticket_id = data.get("ticket_id")
    
    if not ticket_id:
        await message.answer("❌ Ошибка: ID обращения не найден.")
        await state.clear()
        return
    
    reply_text = message.text
    if not reply_text or len(reply_text) < 3:
        await message.answer("❌ Ответ слишком короткий.")
        return
    
    ticket = await get_ticket(ticket_id)
    if not ticket:
        await message.answer("❌ Обращение не найдено.")
        await state.clear()
        return
    
    # Сохраняем ответ
    await add_reply(ticket_id, message.from_user.id, reply_text)
    
    # Отправляем ответ пользователю
    user_id = ticket["user_id"]
    try:
        user_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💬 Ответить", callback_data=f"support_reply_user_{ticket_id}")],
            [InlineKeyboardButton(text="❌ Закрыть обращение", callback_data=f"support_close_user_{ticket_id}")],
            [InlineKeyboardButton(text="📋 Мои обращения", callback_data="my_tickets")]
        ])
        
        await message.bot.send_message(
            user_id,
            f"💬 <b>Ответ от поддержки</b>\n\n"
            f"📋 Обращение #{ticket_id}\n"
            f"📝 {reply_text}\n\n"
            f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            reply_markup=user_keyboard,
            parse_mode="HTML"
        )
        await message.answer(
            f"✅ Ответ на обращение #{ticket_id} отправлен пользователю.",
            reply_markup=get_back_button("admin_tickets"),
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer(f"❌ Не удалось отправить ответ: {e}")
    
    await state.clear()


@router.callback_query(F.data.startswith("support_close_"))
async def cb_support_close(call: CallbackQuery):
    """Закрытие обращения администратором."""
    await call.answer()
    
    if not _is_admin(call.from_user.id):
        await call.message.answer("❌ Доступ запрещён.")
        return
    
    ticket_id = int(call.data.replace("support_close_", ""))
    ticket = await get_ticket(ticket_id)
    
    if not ticket:
        await call.message.answer("❌ Обращение не найдено.")
        return
    
    if ticket["status"] == "closed":
        await call.message.answer("❌ Это обращение уже закрыто.")
        return
    
    await close_ticket(ticket_id)
    
    # Уведомляем пользователя
    try:
        await call.bot.send_message(
            ticket["user_id"],
            f"🔒 <b>Обращение #{ticket_id} закрыто</b>\n\n"
            f"Администратор закрыл ваше обращение.\n"
            f"Если у вас остались вопросы, вы можете открыть его заново.",
            reply_markup=get_back_button("main_menu"),
            parse_mode="HTML"
        )
    except Exception:
        pass
    
    await call.message.edit_text(
        f"✅ Обращение #{ticket_id} закрыто.",
        reply_markup=get_back_button("admin_tickets"),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("admin_reopen_"))
async def cb_admin_reopen(call: CallbackQuery):
    """Администратор открывает обращение заново."""
    await call.answer()
    
    if not _is_admin(call.from_user.id):
        return
    
    ticket_id = int(call.data.replace("admin_reopen_", ""))
    ticket = await get_ticket(ticket_id)
    
    if not ticket:
        await call.message.answer("❌ Обращение не найдено.")
        return
    
    await reopen_ticket(ticket_id)
    
    # Уведомляем пользователя
    try:
        await call.bot.send_message(
            ticket["user_id"],
            f"🔄 <b>Обращение #{ticket_id} открыто заново</b>\n\n"
            f"Администратор открыл ваше обращение для продолжения диалога.",
            reply_markup=get_back_button("main_menu"),
            parse_mode="HTML"
        )
    except Exception:
        pass
    
    await call.message.edit_text(
        f"✅ Обращение #{ticket_id} открыто заново.",
        reply_markup=get_back_button("admin_tickets"),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("support_close_user_"))
async def cb_user_close_ticket(call: CallbackQuery):
    """Пользователь закрывает обращение."""
    await call.answer()
    
    ticket_id = int(call.data.replace("support_close_user_", ""))
    ticket = await get_ticket(ticket_id)
    
    if not ticket or ticket["user_id"] != call.from_user.id:
        await call.message.answer("❌ Обращение не найдено.")
        return
    
    if ticket["status"] == "closed":
        await call.message.answer("❌ Это обращение уже закрыто.")
        return
    
    await close_ticket(ticket_id)
    
    # Уведомляем администратора
    admin_id = config.ADMIN_ID
    if admin_id:
        try:
            await call.bot.send_message(
                admin_id,
                f"🔒 Пользователь <b>{ticket['username']}</b> закрыл обращение #{ticket_id}",
                parse_mode="HTML"
            )
        except Exception:
            pass
    
    await call.message.edit_text(
        f"✅ Обращение #{ticket_id} закрыто.",
        reply_markup=get_back_button("main_menu"),
        parse_mode="HTML"
    )
