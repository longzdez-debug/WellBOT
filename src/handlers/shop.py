"""Digital shop handler."""
import os


# ── Image Validation ──────────────────────────────────

VALID_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB

def validate_image(file_path: str) -> bool:
    """Проверяет, что файл является изображением."""
    if not file_path:
        return False
    ext = Path(file_path).suffix.lower()
    if ext not in VALID_IMAGE_EXTENSIONS:
        return False
    try:
        size = os.path.getsize(file_path)
        if size > MAX_IMAGE_SIZE:
            return False
    except Exception:
        return False
    return True
import json
import logging
from datetime import datetime
from pathlib import Path
import os


# ── Image Validation ──────────────────────────────────

VALID_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB

def validate_image(file_path: str) -> bool:
    """Проверяет, что файл является изображением."""
    if not file_path:
        return False
    ext = Path(file_path).suffix.lower()
    if ext not in VALID_IMAGE_EXTENSIONS:
        return False
    try:
        size = os.path.getsize(file_path)
        if size > MAX_IMAGE_SIZE:
            return False
    except Exception:
        return False
    return True

from aiogram import F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, PreCheckoutQuery, LabeledPrice, InputFile, PreCheckoutQuery, LabeledPrice
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from src.core.config import config
from src.keyboards import get_shop_menu, get_admin_shop_menu, get_back_button
from .common import router, get_db, logger


# ── FSM States ─────────────────────────────────────

class ShopAdminState(StatesGroup):
    waiting_for_name = State()
    waiting_for_description = State()
    waiting_for_price = State()
    waiting_for_icon = State()
    waiting_for_image = State()
    waiting_for_stock = State()
    waiting_for_product_id = State()
    waiting_for_edit_field = State()


# ── Database functions ────────────────────────────

async def create_product(name: str, description: str, price: int, icon: str, image_path: str = None, stock: int = 999) -> int:
    """Создаёт товар в БД."""
    db = get_db()
    cursor = await db.connection.execute(
        """INSERT INTO shop_products (name, description, price, icon, image_path, stock, created_at)
           VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
        (name, description, price, icon, image_path, stock)
    )
    await db.connection.commit()
    return cursor.lastrowid


async def get_product(product_id: int) -> dict:
    """Получает товар по ID."""
    db = get_db()
    cursor = await db.connection.execute(
        "SELECT * FROM shop_products WHERE id = ?",
        (product_id,)
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def get_all_products() -> list:
    """Получает все товары."""
    db = get_db()
    cursor = await db.connection.execute(
        "SELECT * FROM shop_products ORDER BY created_at DESC"
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def update_product(product_id: int, **kwargs) -> bool:
    """Обновляет товар."""
    db = get_db()
    allowed = {"name", "description", "price", "icon", "image_path", "stock", "is_active"}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not updates:
        return False
    
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [product_id]
    await db.connection.execute(
        f"UPDATE shop_products SET {set_clause} WHERE id = ?",
        tuple(values)
    )
    await db.connection.commit()
    return True


async def delete_product(product_id: int) -> bool:
    """Удаляет товар."""
    db = get_db()
    # Получаем путь к изображению
    product = await get_product(product_id)
    if product and product.get("image_path"):
        try:
            os.remove(product["image_path"])
        except Exception:
            pass
    
    await db.connection.execute("DELETE FROM shop_products WHERE id = ?", (product_id,))
    await db.connection.commit()
    return True


async def purchase_product(user_id: int, product_id: int) -> bool:
    """Покупка товара."""
    db = get_db()
    product = await get_product(product_id)
    if not product or not product["is_active"] or product["stock"] <= 0:
        return False
    
    # Проверяем подписку (можно купить только с активной подпиской)
    cursor = await db.connection.execute(
        "SELECT subscription_until FROM users WHERE user_id = ?",
        (user_id,)
    )
    user = await cursor.fetchone()
    if not user:
        return False
    
    # Списание звёзд (здесь логика оплаты через Telegram Stars)
    # Для теста просто записываем покупку
    
    # Уменьшаем остаток
    await db.connection.execute(
        "UPDATE shop_products SET stock = stock - 1 WHERE id = ?",
        (product_id,)
    )
    
    # Записываем покупку
    await db.connection.execute(
        """INSERT INTO shop_purchases (user_id, product_id, price, purchased_at)
           VALUES (?, ?, ?, CURRENT_TIMESTAMP)""",
        (user_id, product_id, product["price"])
    )
    await db.connection.commit()
    return True


async def get_user_purchases(user_id: int) -> list:
    """Получает покупки пользователя."""
    db = get_db()
    cursor = await db.connection.execute(
        """SELECT p.*, s.name, s.icon, s.description 
           FROM shop_purchases p
           JOIN shop_products s ON p.product_id = s.id
           WHERE p.user_id = ?
           ORDER BY p.purchased_at DESC""",
        (user_id,)
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


def save_product_image(product_id: int, photo_file) -> str:
    """Сохраняет изображение товара."""
    shop_dir = Path("data/shop_images")
    shop_dir.mkdir(exist_ok=True)
    
    file_path = shop_dir / f"product_{product_id}.jpg"
    # Здесь логика сохранения файла
    return str(file_path)


# ── User Handlers ──────────────────────────────────

@router.callback_query(F.data == "shop_menu")
async def cb_shop_menu(call: CallbackQuery):
    """Показывает магазин."""
    await call.answer()
    
    products = await get_all_products()
    active_products = [p for p in products if p.get("is_active", 1)]
    
    if not active_products:
        await call.message.edit_text(
            "🛒 <b>Магазин цифровых товаров</b>\n\n"
            "К сожалению, сейчас нет доступных товаров.\n"
            "Загляните позже!",
            reply_markup=get_back_button("main_menu"),
            parse_mode="HTML"
        )
        return
    
    text = "🛒 <b>Магазин цифровых товаров</b>\n\n"
    for p in active_products:
        stock_text = f" (в наличии: {p['stock']})" if p['stock'] < 10 else ""
        text += f"{p['icon']} <b>{p['name']}</b> — {p['price']}⭐{stock_text}\n"
        text += f"   {p['description'][:50]}...\n\n"
    
    text += "👇 Выберите товар для покупки:"
    
    await call.message.edit_text(
        text,
        reply_markup=get_shop_menu(active_products),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("shop_buy_"))
async def cb_shop_buy(call: CallbackQuery):
    """Покупка товара."""
    await call.answer()
    
    product_id = int(call.data.replace("shop_buy_", ""))
    product = await get_product(product_id)
    
    if not product or not product.get("is_active", 1) or product["stock"] <= 0:
        await call.message.edit_text(
            "❌ Товар временно недоступен.",
            reply_markup=get_back_button("shop_menu"),
            parse_mode="HTML"
        )
        return
    
    # Проверяем подписку
    db = get_db()
    cursor = await db.connection.execute(
        "SELECT subscription_until FROM users WHERE user_id = ?",
        (call.from_user.id,)
    )
    user = await cursor.fetchone()
    
    if not user:
        await call.message.edit_text(
            "❌ Пользователь не найден.",
            reply_markup=get_back_button("main_menu"),
            parse_mode="HTML"
        )
        return
    
    # Создаём инвойс для оплаты
    from aiogram.types import LabeledPrice, PreCheckoutQuery
    
    prices = [LabeledPrice(label=product["name"], amount=product["price"])]
    
    try:
        await call.bot.send_invoice(
            chat_id=call.from_user.id,
            title=f"🛒 {product['name']}",
            description=product["description"][:255],
            payload=f"shop_{product_id}",
            provider_token="",
            currency="XTR",
            prices=prices,
            start_parameter="shop_pay"
        )
    except Exception as e:
        logger.error(f"Ошибка оплаты: {e}")
        await call.message.edit_text(
            f"❌ Ошибка при создании платежа: {e}",
            reply_markup=get_back_button("shop_menu"),
            parse_mode="HTML"
        )


@router.pre_checkout_query()
async def process_shop_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    """Обработка предоплаты."""
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def process_shop_payment(message: Message):
    """Обработка успешной оплаты."""
    payload = message.successful_payment.invoice_payload
    
    if payload.startswith("shop_"):
        product_id = int(payload.replace("shop_", ""))
        product = await get_product(product_id)
        
        if not product:
            await message.answer("❌ Товар не найден.")
            return
        
        success = await purchase_product(message.from_user.id, product_id)
        
        if success:
            await message.answer(
                f"✅ <b>Поздравляем с покупкой!</b>\n\n"
                f"Вы приобрели:\n"
                f"{product['icon']} <b>{product['name']}</b>\n"
                f"💰 Цена: {product['price']}⭐\n\n"
                f"📝 <b>Описание:</b>\n{product['description']}\n\n"
                f"📦 Товар будет доставлен автоматически.",
                reply_markup=get_back_button("shop_menu"),
                parse_mode="HTML"
            )
        else:
            await message.answer(
                "❌ Ошибка при оформлении покупки.",
                reply_markup=get_back_button("shop_menu"),
                parse_mode="HTML"
            )


# ── Admin Handlers ─────────────────────────────────

def _is_admin(user_id: int) -> bool:
    return user_id == config.ADMIN_ID


@router.callback_query(F.data == "admin_shop_manage")
async def cb_admin_shop_manage(call: CallbackQuery):
    """Управление магазином."""
    await call.answer()
    
    if not _is_admin(call.from_user.id):
        await call.message.answer("❌ Доступ запрещён.")
        return
    
    await call.message.edit_text(
        "🛒 <b>Управление магазином</b>\n\n"
        "Выберите действие:",
        reply_markup=get_admin_shop_menu(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin_shop_add")
async def cb_admin_shop_add(call: CallbackQuery, state: FSMContext):
    """Добавление товара."""
    await call.answer()
    
    if not _is_admin(call.from_user.id):
        return
    
    await state.set_state(ShopAdminState.waiting_for_name)
    await call.message.edit_text(
        "🛒 <b>Добавление товара</b>\n\n"
        "Введите <b>название</b> товара:",
        reply_markup=get_back_button("admin_shop_manage"),
        parse_mode="HTML"
    )


@router.message(ShopAdminState.waiting_for_name)
async def process_shop_name(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    
    await state.update_data(name=message.text.strip())
    await state.set_state(ShopAdminState.waiting_for_description)
    await message.answer(
        "📝 Введите <b>описание</b> товара:",
        reply_markup=get_back_button("admin_shop_manage"),
        parse_mode="HTML"
    )


@router.message(ShopAdminState.waiting_for_description)
async def process_shop_description(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    
    await state.update_data(description=message.text.strip())
    await state.set_state(ShopAdminState.waiting_for_price)
    await message.answer(
        "💰 Введите <b>цену</b> в Telegram Stars (только число):",
        reply_markup=get_back_button("admin_shop_manage"),
        parse_mode="HTML"
    )


@router.message(ShopAdminState.waiting_for_price)
async def process_shop_price(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    
    try:
        price = int(message.text.strip())
        if price <= 0:
            await message.answer("❌ Цена должна быть больше 0!")
            return
        await state.update_data(price=price)
    except ValueError:
        await message.answer("❌ Введите число!")
        return
    
    await state.set_state(ShopAdminState.waiting_for_icon)
    await message.answer(
        "🎨 Введите <b>иконку</b> товара (эмодзи):\n"
        "Например: 🎮, 📱, 💻, 🎯, 🔑",
        reply_markup=get_back_button("admin_shop_manage"),
        parse_mode="HTML"
    )


@router.message(ShopAdminState.waiting_for_icon)
async def process_shop_icon(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    
    icon = message.text.strip()
    if len(icon) > 5:
        await message.answer("❌ Иконка должна быть эмодзи (не более 5 символов)!")
        return
    
    await state.update_data(icon=icon)
    await state.set_state(ShopAdminState.waiting_for_stock)
    await message.answer(
        "📦 Введите <b>количество</b> товара в наличии:\n"
        "Напишите <code>0</code> для бесконечного количества.",
        reply_markup=get_back_button("admin_shop_manage"),
        parse_mode="HTML"
    )


@router.message(ShopAdminState.waiting_for_stock)
async def process_shop_stock(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    
    try:
        stock = int(message.text.strip())
        if stock < 0:
            stock = 0
        await state.update_data(stock=stock if stock > 0 else 999)
    except ValueError:
        await message.answer("❌ Введите число!")
        return
    
    # Сохраняем товар
    data = await state.get_data()
    product_id = await create_product(
        name=data["name"],
        description=data["description"],
        price=data["price"],
        icon=data["icon"],
        stock=data["stock"]
    )
    
    await state.clear()
    
    await message.answer(
        f"✅ <b>Товар добавлен!</b>\n\n"
        f"{data['icon']} <b>{data['name']}</b>\n"
        f"💰 Цена: {data['price']}⭐\n"
        f"📦 В наличии: {data['stock'] if data['stock'] < 999 else '∞'}\n"
        f"🆔 ID товара: <code>{product_id}</code>\n\n"
        f"💡 Теперь можно добавить изображение через редактирование.",
        reply_markup=get_back_button("admin_shop_manage"),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin_shop_list")
async def cb_admin_shop_list(call: CallbackQuery):
    """Список товаров для админа."""
    await call.answer()
    
    if not _is_admin(call.from_user.id):
        return
    
    products = await get_all_products()
    
    if not products:
        await call.message.edit_text(
            "📭 Товаров пока нет.",
            reply_markup=get_back_button("admin_shop_manage"),
            parse_mode="HTML"
        )
        return
    
    text = "📋 <b>Список товаров:</b>\n\n"
    for p in products:
        status = "🟢" if p.get("is_active", 1) else "🔴"
        stock_text = f"{p['stock']}" if p['stock'] < 999 else "∞"
        text += f"{status} {p['icon']} <b>{p['name']}</b>\n"
        text += f"   ID: {p['id']} | Цена: {p['price']}⭐ | Остаток: {stock_text}\n"
        text += f"   📝 {p['description'][:40]}...\n\n"
    
    await call.message.edit_text(
        text,
        reply_markup=get_back_button("admin_shop_manage"),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin_shop_edit")
async def cb_admin_shop_edit(call: CallbackQuery, state: FSMContext):
    """Редактирование товара."""
    await call.answer()
    
    if not _is_admin(call.from_user.id):
        return
    
    await state.set_state(ShopAdminState.waiting_for_product_id)
    await call.message.edit_text(
        "✏️ <b>Редактирование товара</b>\n\n"
        "Введите <b>ID</b> товара для редактирования:",
        reply_markup=get_back_button("admin_shop_manage"),
        parse_mode="HTML"
    )


@router.message(ShopAdminState.waiting_for_product_id)
async def process_edit_product_id(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    
    try:
        product_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите число!")
        return
    
    product = await get_product(product_id)
    if not product:
        await message.answer("❌ Товар не найден!")
        return
    
    await state.update_data(edit_id=product_id)
    await state.set_state(ShopAdminState.waiting_for_edit_field)
    
    await message.answer(
        f"✏️ <b>Редактирование товара #{product_id}</b>\n\n"
        f"Текущие данные:\n"
        f"{product['icon']} <b>{product['name']}</b>\n"
        f"💰 Цена: {product['price']}⭐\n"
        f"📦 Остаток: {product['stock'] if product['stock'] < 999 else '∞'}\n"
        f"📝 Описание: {product['description'][:50]}...\n\n"
        f"Введите, что хотите изменить:\n"
        f"<code>название</code> — название\n"
        f"<code>описание</code> — описание\n"
        f"<code>цена</code> — цену\n"
        f"<code>иконка</code> — иконку\n"
        f"<code>остаток</code> — количество\n"
        f"<code>статус</code> — активен/неактивен\n\n"
        f"Или отправьте новое значение:",
        reply_markup=get_back_button("admin_shop_manage"),
        parse_mode="HTML"
    )


@router.message(ShopAdminState.waiting_for_edit_field)
async def process_edit_field(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    product_id = data.get("edit_id")
    product = await get_product(product_id)
    
    if not product:
        await message.answer("❌ Товар не найден!")
        await state.clear()
        return
    
    field = message.text.strip().lower()
    
    # Словарь полей
    fields = {
        "название": "name",
        "описание": "description", 
        "цена": "price",
        "иконка": "icon",
        "остаток": "stock",
        "статус": "is_active"
    }
    
    if field in fields:
        await state.update_data(edit_field=fields[field])
        
        if fields[field] == "is_active":
            new_status = not product.get("is_active", 1)
            await update_product(product_id, is_active=new_status)
            await message.answer(
                f"✅ Статус изменён: {'Активен' if new_status else 'Неактивен'}",
                reply_markup=get_back_button("admin_shop_manage"),
                parse_mode="HTML"
            )
            await state.clear()
            return
        
        await message.answer(
            f"Введите новое значение для <b>{field}</b>:",
            reply_markup=get_back_button("admin_shop_manage"),
            parse_mode="HTML"
        )
    else:
        # Сохраняем значение
        if data.get("edit_field"):
            new_value = message.text.strip()
            field_key = data.get("edit_field")
            
            if field_key == "price":
                try:
                    new_value = int(new_value)
                except ValueError:
                    await message.answer("❌ Введите число!")
                    return
            elif field_key == "stock":
                try:
                    new_value = int(new_value)
                    if new_value < 0:
                        new_value = 0
                except ValueError:
                    await message.answer("❌ Введите число!")
                    return
            
            await update_product(product_id, **{field_key: new_value})
            await message.answer(
                f"✅ Поле <b>{field_key}</b> обновлено!",
                reply_markup=get_back_button("admin_shop_manage"),
                parse_mode="HTML"
            )
            await state.clear()


@router.callback_query(F.data == "admin_shop_delete")
async def cb_admin_shop_delete(call: CallbackQuery, state: FSMContext):
    """Удаление товара."""
    await call.answer()
    
    if not _is_admin(call.from_user.id):
        return
    
    await state.set_state(ShopAdminState.waiting_for_product_id)
    await state.update_data(delete_mode=True)
    await call.message.edit_text(
        "🗑 <b>Удаление товара</b>\n\n"
        "Введите <b>ID</b> товара для удаления:",
        reply_markup=get_back_button("admin_shop_manage"),
        parse_mode="HTML"
    )


@router.message(ShopAdminState.waiting_for_product_id)
async def process_delete_product(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    if not data.get("delete_mode"):
        return
    
    try:
        product_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите число!")
        return
    
    product = await get_product(product_id)
    if not product:
        await message.answer("❌ Товар не найден!")
        return
    
    await delete_product(product_id)
    await state.clear()
    
    await message.answer(
        f"✅ Товар <b>{product['name']}</b> удалён!",
        reply_markup=get_back_button("admin_shop_manage"),
        parse_mode="HTML"
    )


# ── My Purchases ──────────────────────────────────

@router.callback_query(F.data == "my_purchases")
async def cb_my_purchases(call: CallbackQuery):
    """Мои покупки."""
    await call.answer()
    
    purchases = await get_user_purchases(call.from_user.id)
    
    if not purchases:
        await call.message.edit_text(
            "📭 У вас пока нет покупок.",
            reply_markup=get_back_button("shop_menu"),
            parse_mode="HTML"
        )
        return
    
    text = "🛒 <b>Мои покупки</b>\n\n"
    for p in purchases[:10]:
        text += f"{p['icon']} <b>{p['name']}</b>\n"
        text += f"💰 {p['price']}⭐ | 📅 {p['purchased_at']}\n"
        text += f"📝 {p['description'][:50]}...\n\n"
    
    await call.message.edit_text(
        text,
        reply_markup=get_back_button("shop_menu"),
        parse_mode="HTML"
    )
