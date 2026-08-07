"""Inline keyboards and presets for the bot."""
import urllib.parse
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from src.data.regions import REGIONS
from src.data.tariffs import PLANS
from src.data.categories import CATEGORIES

PRESETS = {
    "iphone": {"title": "📱 Все iPhone", "query": "iPhone", "prn": "17000", "cat": "17010"},
    "samsung": {"title": "📲 Samsung", "query": "Samsung", "prn": "17000", "cat": "17010"},
    "xiaomi": {"title": "📲 Xiaomi / Redmi", "query": "Xiaomi", "prn": "17000", "cat": "17010"},
    "laptops": {"title": "💻 Ноутбуки", "query": "Ноутбук", "prn": "16000", "cat": None},
    "ps5": {"title": "🎮 PlayStation 5", "query": "PlayStation 5", "prn": "5000", "cat": None},
    "bikes": {"title": "🚲 Велосипеды", "query": "Велосипед", "prn": "4000", "cat": None},
}


def get_main_menu(is_admin: bool = False) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="➕ Добавить поиск", callback_data="add_search"),
         InlineKeyboardButton(text="📋 Мои поиски", callback_data="my_searches")],
        [InlineKeyboardButton(text="👤 Кабинет", callback_data="profile"),
         InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton(text="💳 Тарифы", callback_data="tariffs"),
         InlineKeyboardButton(text="🎁 Рефералы", callback_data="referral")],
        [InlineKeyboardButton(text="🏆 Бейджи", callback_data="badges"),
         InlineKeyboardButton(text="🌍 Язык", callback_data="language_menu")],
        [InlineKeyboardButton(text="🕐 Тихие часы", callback_data="quiet_hours_menu")],
        [InlineKeyboardButton(text="ℹ️ Инструкция", callback_data="help"),
         InlineKeyboardButton(text="💬 Поддержка", callback_data="support")],
        [InlineKeyboardButton(text="🎟 Промокод", callback_data="promo_menu")]
    ]
    if is_admin:
        buttons.append([InlineKeyboardButton(text="⚙️ Админ панель", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_searches_menu(searches: list) -> InlineKeyboardMarkup:
    buttons = []
    for s in searches:
        title = s.title if len(s.title) < 25 else s.title[:22] + "..."
        status_icon = "🟢" if s.is_active else "⏸"
        action = f"edit_search_{s.id}" 
        buttons.append([
            InlineKeyboardButton(text=f"{status_icon} {title}", callback_data=action)
        ])
    buttons.append([InlineKeyboardButton(text="➕ Добавить поиск", callback_data="add_search")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад в меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_search_management_menu(search_id: int, is_active: bool, only_photos: bool = False) -> InlineKeyboardMarkup:
    photos_text = "📸 Только фото: ✅" if only_photos else "📸 Только фото: ❌"
    buttons = [
        [InlineKeyboardButton(text="✏️ Название", callback_data=f"edit_title_{search_id}"),
         InlineKeyboardButton(text="💰 Цены", callback_data=f"edit_price_{search_id}")],
        [InlineKeyboardButton(text="🚫 Исключения", callback_data=f"edit_blacklist_{search_id}"),
         InlineKeyboardButton(text="📉 Порог цены", callback_data=f"edit_threshold_{search_id}")],
        [InlineKeyboardButton(text=photos_text, callback_data=f"toggle_photos_{search_id}")],
    ]
    if is_active:
        buttons.append([InlineKeyboardButton(text="⏸ Пауза", callback_data=f"toggle_search_{search_id}")])
    else:
        buttons.append([InlineKeyboardButton(text="▶️ Возобновить", callback_data=f"toggle_search_{search_id}")])
    buttons.append([InlineKeyboardButton(text="❌ Удалить", callback_data=f"delete_search_{search_id}")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад к поискам", callback_data="my_searches")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_pay_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Тарифы", callback_data="tariffs"),
         InlineKeyboardButton(text="🎟 Промокод", callback_data="promo_menu")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu")]
    ])


def get_tariffs_menu() -> InlineKeyboardMarkup:
    buttons = []
    plans = list(PLANS.values())
    row = []
    for plan in plans:
        row.append(InlineKeyboardButton(
            text=f"{plan.name} — {plan.price_stars}⭐",
            callback_data=f"buy_plan_{plan.key}"
        ))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Выдать подписку", callback_data="admin_give_sub"),
          InlineKeyboardButton(text="💳 Изменить цену", callback_data="admin_change_price")],
        [InlineKeyboardButton(text="📊 Статистика бота", callback_data="admin_stats"),
          InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🎟 Промокоды", callback_data="admin_promocodes"),
          InlineKeyboardButton(text="🚫 Бан/Разбан", callback_data="admin_ban_menu")],
        [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="main_menu")]
    ])


def get_admin_promocode_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать промокод", callback_data="admin_create_promo")],
        [InlineKeyboardButton(text="📋 Список промокодов", callback_data="admin_list_promo")],
        [InlineKeyboardButton(text="🗑 Удалить промокод", callback_data="admin_delete_promo")],
        [InlineKeyboardButton(text="◀️ Назад в админку", callback_data="admin_panel")]
    ])


def get_back_button(target: str = "main_menu") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data=target)]
    ])


def get_add_search_type_menu() -> InlineKeyboardMarkup:
    buttons = []
    for key, data in PRESETS.items():
        buttons.append([
            InlineKeyboardButton(text=f"➕ {data['title']}", callback_data=f"use_preset_{key}"),
            InlineKeyboardButton(text="📩 Тест", callback_data=f"test_preset_{key}")
        ])
    buttons.append([InlineKeyboardButton(text="📂 Поиск по категории", callback_data="search_by_category"),
                    InlineKeyboardButton(text="✏️ Свой запрос", callback_data="custom_query")])
    buttons.append([InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_regions_keyboard(is_test: bool = False) -> InlineKeyboardMarkup:
    prefix = "test_reg_" if is_test else "select_reg_"
    buttons = [[InlineKeyboardButton(text="🔍 По всей Беларуси", callback_data=f"{prefix}all_belarus")]]
    row = []
    for reg_id, reg_info in REGIONS.items():
        row.append(InlineKeyboardButton(text=reg_info["name"], callback_data=f"{prefix}{reg_id}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="add_search")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_cities_keyboard(region_id: str, is_test: bool = False) -> InlineKeyboardMarkup:
    prefix = "test_city_" if is_test else "set_city_"
    reg_data = REGIONS.get(region_id, {})
    cities = reg_data.get("cities", {})
    reg_code = reg_data.get("code", "")
    reg_name = reg_data.get("name", "Область").replace("📍 ", "")

    buttons = []
    if reg_code:
        buttons.append([InlineKeyboardButton(text=f"📍 Вся {reg_name}", callback_data=f"{prefix}{reg_code}")])
    row = []
    for city_code, city_name in cities.items():
        row.append(InlineKeyboardButton(text=city_name, callback_data=f"{prefix}{city_code}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([InlineKeyboardButton(text="◀️ Назад к областям", callback_data="add_search")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_categories_keyboard(is_test: bool = False) -> InlineKeyboardMarkup:
    prefix = "test_cat_" if is_test else "cat_"
    buttons = [[InlineKeyboardButton(text="🔍 Без категории (везде)", callback_data=f"{prefix}none")]]
    row = []
    for cat_id, cat_data in CATEGORIES.items():
        row.append(InlineKeyboardButton(text=cat_data["name"], callback_data=f"{prefix}{cat_id}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="add_search")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ── New Feature Keyboards ──────────────────────────

def get_language_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton(text="🇧🇾 Беларуская", callback_data="lang_by")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]
    ])


def get_badges_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Все бейджи", callback_data="badges_list")],
        [InlineKeyboardButton(text="🎁 Заработать бейджи", callback_data="badges_howto")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu")]
    ])


def get_quiet_hours_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏰ Установить тихие часы", callback_data="quiet_hours_set")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]
    ])


def get_only_photos_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📸 Включить (только фото)", callback_data="only_photos_on")],
        [InlineKeyboardButton(text="🖼 Выключить (все объявления)", callback_data="only_photos_off")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]
    ])


def get_search_with_channel(search_id: int, has_channel: bool) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="📢 Канал/группа", callback_data=f"channel_set_{search_id}")],
        [InlineKeyboardButton(text="🔗 Написать продавцу", url=f"https://kufar.by/ad/{search_id}")]
    ]
    if has_channel:
        buttons.append([InlineKeyboardButton(text="❌ Убрать канал", callback_data=f"channel_remove_{search_id}")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад к поискам", callback_data="my_searches")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)