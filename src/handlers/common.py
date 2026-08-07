"""Shared handlers state: DB instance, router, FSM states, helper functions."""
import re
import logging
from datetime import datetime, timezone, timedelta

from aiogram import Bot, Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup

from src.core.database import Database
from src.parser import Ad, WellBoTParser
from src.data.tariffs import get_plan
from src.core.config import config

router = Router()
_db: Database | None = None
logger = logging.getLogger(__name__)


def set_database(database: Database):
    global _db
    _db = database


def get_db() -> Database:
    """Get the current database instance."""
    if _db is None:
        raise RuntimeError("Database not initialized. Call set_database() first.")
    return _db


# ── FSM States ─────────────────────────────────────

class AddSearchState(StatesGroup):
    waiting_for_title = State()
    waiting_for_min_price = State()
    waiting_for_max_price = State()


class AdminState(StatesGroup):
    waiting_for_user_and_days = State()
    waiting_for_broadcast = State()
    waiting_for_ban_user = State()
    waiting_for_promo_create = State()
    waiting_for_promo_delete = State()


class EditSearchState(StatesGroup):
    waiting_for_title = State()
    waiting_for_min_price = State()
    waiting_for_max_price = State()
    waiting_for_blacklist = State()
    waiting_for_threshold = State()


class PromoState(StatesGroup):
    waiting_for_code = State()


class AdminPriceState(StatesGroup):
    waiting_for_plan_price = State()


# ── Helpers ────────────────────────────────────────

def analyze_market_price(current_ad_price_byn: float, all_ads: list) -> str:
    if not current_ad_price_byn or current_ad_price_byn <= 0:
        return "⚖️ Цена договорная"

    prices = []
    for ad in all_ads:
        nums = re.findall(r'\d+', str(ad.price).replace(" ", ""))
        if nums:
            val = float(nums[0])
            if current_ad_price_byn * 0.3 <= val <= current_ad_price_byn * 3:
                prices.append(val)

    if len(prices) < 3:
        return "⚖️ По рынку (недостаточно данных)"

    avg_price = sum(prices) / len(prices)
    diff_percent = ((current_ad_price_byn - avg_price) / avg_price) * 100

    if diff_percent < -12:
        return f"🔥 <b>Ниже рынка</b> (на {abs(round(diff_percent))}% дешевле средних {round(avg_price)} р.)"
    elif diff_percent > 12:
        return f"⚠️ <b>Выше рынка</b> (на {round(diff_percent)}% дороже средних {round(avg_price)} р.)"
    else:
        return f"⚖️ <b>Средняя цена</b> (около {round(avg_price)} р.)"


def extract_numeric_price(price_str: str) -> float:
    nums = re.findall(r'\d+', str(price_str).replace(" ", ""))
    return float(nums[0]) if nums else 0.0


async def send_profile_info(user_id: int, username: str, target_message: Message = None, call: CallbackQuery = None):
    db = get_db()
    user = await db.get_or_create_user(user_id, username)
    has_sub = await db.check_subscription(user_id)
    status_str = "🟢 <b>АКТИВНА</b>" if has_sub else "🔴 <b>ИСТЕКЛА</b>"
    plan_key = user.get("tariff_plan", "basic")
    plan = get_plan(plan_key)
    referrals = await db.get_referrals_count(user_id)

    searches = await db.get_user_searches(user_id)
    active_searches = [s for s in searches if s.get("is_active", 1)]
    
    language = user.get("language", "ru")
    lang_flags = {"ru": "🇷🇺", "by": "🇧🇾", "en": "🇬🇧"}
    lang_flag = lang_flags.get(language, "🇷🇺")
    
    last_active = user.get("last_active_at", "never")
    quiet_start, quiet_end = await db.get_quiet_hours(user_id)

    cabinet_text = (
        f"👤 <b>Личный кабинет</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"🆔 ID: <code>{user['user_id']}</code>\n"
        f"💎 Подписка: {status_str}\n"
        f"📋 Тариф: {plan.name}\n"
        f"⏳ Действует до: <code>{user['subscription_until']}</code>\n\n"
        f"🌍 Язык: {lang_flag} {language.upper()}\n"
        f"🕐 Тихие часы: {quiet_start}:00 - {quiet_end}:00\n"
        f"📊 Активных проектов: <b>{len(active_searches)}</b> / {plan.max_searches}\n"
        f"👥 Приглашено друзей: <b>{referrals}</b>\n"
        f"🏆 Бейджей: <b>{len(await db.get_user_badges(user_id))}</b>"
    )

    keyboard_buttons = [
        [InlineKeyboardButton(text="📋 Управлять поисками", callback_data="my_searches_cabinet")],
        [InlineKeyboardButton(text="💳 Тарифы", callback_data="tariffs"),
         InlineKeyboardButton(text="🎁 Рефералы", callback_data="referral")],
        [InlineKeyboardButton(text="🏆 Бейджи", callback_data="badges"),
         InlineKeyboardButton(text="🌍 Язык", callback_data="language_menu")],
        [InlineKeyboardButton(text="🕐 Тихие часы", callback_data="quiet_hours_menu"),
         InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu")]
    ]
    markup = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    if call:
        await call.message.edit_text(cabinet_text, reply_markup=markup, parse_mode="HTML")
    elif target_message:
        await target_message.answer(cabinet_text, reply_markup=markup, parse_mode="HTML")


def format_list_time(list_time: str) -> str:
    """Format ISO timestamp to readable date/time in Belarus timezone."""
    if not list_time:
        return ""
    try:
        dt = datetime.fromisoformat(list_time.replace("Z", "+00:00"))
        # Convert to Belarus timezone (UTC+3)
        msk_tz = timezone(timedelta(hours=3))
        dt_local = dt.astimezone(msk_tz)
        return dt_local.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return ""


async def send_ad_to_user(bot: Bot, user_id: int, ad: Ad, search_title: str, all_ads: list = None):
    db = get_db()
    has_sub = await db.check_subscription(user_id)
    if not has_sub:
        return

    numeric_price = extract_numeric_price(ad.price)
    market_evaluation = analyze_market_price(numeric_price, all_ads) if all_ads else "⚖️ По рынку"
    market_evaluation = market_evaluation.replace("**", "")

    desc_text = ad.description if ad.description else "Описание отсутствует."
    if len(desc_text) > 250:
        desc_text = desc_text[:247] + "..."

    text = (
        f"🚨 <b>Новое объявление!</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📱 <b>{ad.title}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 <b>Цена:</b> <code>{ad.price}</code>\n"
        f"📍 <b>Локация:</b> {ad.city}\n"
        + (f"👤 <b>Продавец:</b> {ad.seller}\n" if hasattr(ad, 'seller') and ad.seller else "")
        + (f"🕐 <b>Опубликовано:</b> {format_list_time(ad.list_time)}\n" if ad.list_time else "")
        + f"\n📝 <b>Описание:</b>\n{desc_text}\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Оценка рынка:</b> {market_evaluation}\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔗 <a href='{ad.url}'>Перейти к объявлению</a>"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Написать продавцу", url=ad.url)]
    ])

    if ad.images:
        try:
            await bot.send_photo(chat_id=user_id, photo=ad.images[0], caption=text, parse_mode="HTML", reply_markup=keyboard)
            return
        except Exception as e:
            logger.warning(f"send_ad_to_user: send_photo failed: {e}")

    try:
        await bot.send_message(chat_id=user_id, text=text, parse_mode="HTML", disable_web_page_preview=True, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"send_ad_to_user: send_message failed: {e}")
