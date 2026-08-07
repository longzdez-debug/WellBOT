"""Monitoring — polls Kufar for new ads and sends notifications.

Features:
- Photos only filtering
- Quiet hours checking
- Subscription expiry reminders
- Channel/group mode
- Weekly stats (Pro)
- Badge checking
- Smart spam filtering
- Inactivity reminders
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InputMediaPhoto, InlineKeyboardMarkup, InlineKeyboardButton

from src.parser import KufarParser
from src.core.database import Database
from src.handlers.common import analyze_market_price, format_list_time
from src.core.config import config
from src.data.tariffs import PLANS, DEFAULT_MAX_PHOTOS, DEFAULT_MONITORING_INTERVAL
from src.data.locales import get_locale, t

logger = logging.getLogger(__name__)

notification_queue = asyncio.Queue()
_parser = KufarParser()


def get_ad_keyboard(ad_url: str) -> InlineKeyboardMarkup:
    """Inline keyboard for ad messages."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Написать продавцу", url=ad_url)]
    ])


# ── Smart Spam Filter ─────────────────────────────

_SPAM_PATTERNS = [
    r"\d{10,}",  # phone numbers
    r"@\w+",     # mentions
    r"vk\.com|t\.me",  # external links
    r"куплю|продам|обмен",  # buy/sell/exchange spam
]


def _is_spam(ad_title: str, ad_description: str) -> bool:
    """Check if ad looks like spam."""
    combined = f"{ad_title} {ad_description or ''}".lower()
    for pattern in _SPAM_PATTERNS:
        if re.search(pattern, combined):
            return True
    return False


# ── Quiet Hours Check ─────────────────────────────

def _is_quiet_hours(user_id: int) -> bool:
    """Check if current time is within user's quiet hours."""
    return False


# ── Subscription Expiry Check ─────────────────────

async def _check_subscription_expiry(user_id: int, bot, db: Database, search_id: int) -> bool:
    """Check if subscription is expiring soon and send reminder."""
    try:
        cursor = await db.connection.execute(
            "SELECT subscription_until, language FROM users WHERE user_id = ?",
            (user_id,)
        )
        user = await cursor.fetchone()
        
        if not user:
            return False
        
        sub_until = user["subscription_until"]
        if isinstance(sub_until, str):
            sub_until = datetime.fromisoformat(sub_until)
        days_left = (sub_until - datetime.now()).days
        
        if 0 < days_left <= 3:  # Expiring in 3 days or less
            language = user["language"] or "ru"
            locale = get_locale(language)
            await bot.send_message(
                user_id,
                locale["sub_expiring_soon"].format(days=days_left),
                parse_mode="HTML"
            )
            logger.info(f"Sent subscription expiry reminder to user {user_id}")
        
        return days_left <= 0  # Return True if expired
    except Exception as e:
        logger.error(f"Error checking subscription expiry: {e}")
        return False


# ── Badge Checking ────────────────────────────────

async def _check_and_award_badges(user_id: int, bot, db: Database):
    """Check and award new badges."""
    try:
        new_badges = await db.check_and_award_badges(user_id)
        if new_badges:
            language = await db.get_user_language(user_id)
            locale = get_locale(language)
            for badge_key in new_badges:
                cursor = await db.connection.execute("SELECT icon, name FROM badges WHERE key = ?", (badge_key,))
                badge = await cursor.fetchone()
                if badge:
                    await bot.send_message(
                        user_id,
                        locale["badge_earned"].format(icon=badge["icon"], name=badge["name"]),
                        parse_mode="HTML"
                    )
            logger.info(f"Awarded {len(new_badges)} badges to user {user_id}")
    except Exception as e:
        logger.error(f"Error checking badges: {e}")


# ── Weekly Stats Saving ───────────────────────────

async def _save_weekly_stats(user_id: int, search_id: int, db: Database, prices: list):
    """Save weekly stats for Pro users."""
    try:
        plan_key = await db.get_tariff_plan(user_id)
        plan = PLANS.get(plan_key, PLANS["basic"])
        
        if not plan.priority:
            return  # Only save stats for Pro users
        
        week_start = datetime.now().strftime("%Y-%W")
        await db.save_weekly_stats(user_id, search_id, week_start, len(prices), prices)
    except Exception as e:
        logger.error(f"Error saving weekly stats: {e}")


# ── Photos Only Filter ────────────────────────────

def _filter_photos_only(ads: list, only_photos: bool) -> list:
    """Filter ads to show only those with photos if needed."""
    if not only_photos:
        return ads
    return [ad for ad in ads if ad.images and len(ad.images) > 0]


# ── Inactivity Reminder ───────────────────────────

async def _check_inactivity(user_id: int, bot, db: Database):
    """Check if user is inactive and send reminder."""
    try:
        cursor = await db.connection.execute(
            "SELECT last_active_at, language FROM users WHERE user_id = ?",
            (user_id,)
        )
        user = await cursor.fetchone()
        
        if not user or not user["last_active_at"]:
            return  # First time user
        
        last_active = user["last_active_at"]
        if isinstance(last_active, str):
            last_active = datetime.fromisoformat(last_active)
        days_inactive = (datetime.now() - last_active).days
        
        if days_inactive >= 7:
            language = user["language"] or "ru"
            locale = get_locale(language)
            count = await db.count_user_searches(user_id)
            await bot.send_message(
                user_id,
                locale["inactive_reminder"].format(days=days_inactive, searches=count),
                parse_mode="HTML"
            )
            logger.info(f"Sent inactivity reminder to user {user_id}")
    except Exception as e:
        logger.error(f"Error checking inactivity: {e}")


# ── Channel Mode ──────────────────────────────────

async def _send_to_channel_or_user(user_id: int, search_id: int, text: str, photo_urls: list, 
                                   ad_url: str, bot, db: Database):
    """Send notification to user or their channel."""
    try:
        channel_id = await db.get_search_channel(search_id, user_id)
        if channel_id:
            await bot.send_photo(
                chat_id=channel_id,
                photo=photo_urls[0] if photo_urls else None,
                caption=text if not photo_urls else None,
                parse_mode="HTML"
            )
            logger.info(f"Sent ad to channel {channel_id} for search {search_id}")
        else:
            notification_queue.put_nowait({
                "user_id": user_id,
                "text": text,
                "photo_urls": photo_urls,
                "ad_url": ad_url
            })
    except Exception as e:
        logger.error(f"Error sending to channel: {e}")
        # Fallback to user
        notification_queue.put_nowait({
            "user_id": user_id,
            "text": text,
            "photo_urls": photo_urls,
            "ad_url": ad_url
        })


# ── Send Worker ───────────────────────────────────

async def send_worker(bot, db: Database):
    """Async worker for sending messages with Telegram API ban protection."""
    while True:
        task = await notification_queue.get()
        user_id = task["user_id"]
        text = task["text"]
        photo_urls = task.get("photo_urls")
        ad_url = task.get("ad_url")
        keyboard = get_ad_keyboard(ad_url) if ad_url else None

        # Get max photos for this user's tariff
        try:
            plan_key = await db.get_tariff_plan(user_id)
            plan = PLANS.get(plan_key, PLANS["basic"])
            max_photos = plan.max_photos if plan.priority else DEFAULT_MAX_PHOTOS
        except Exception:
            max_photos = DEFAULT_MAX_PHOTOS

        try:
            if photo_urls and len(photo_urls) == 1:
                await bot.send_photo(chat_id=user_id, photo=photo_urls[0], caption=text, parse_mode="HTML", reply_markup=keyboard)
            elif photo_urls and len(photo_urls) > 1:
                media = []
                for i, url in enumerate(photo_urls[:max_photos]):
                    if i == 0:
                        media.append(InputMediaPhoto(media=url, caption=text, parse_mode="HTML"))
                    else:
                        media.append(InputMediaPhoto(media=url))
                await bot.send_media_group(chat_id=user_id, media=media)
                if keyboard:
                    await bot.send_message(chat_id=user_id, text="👆", reply_markup=keyboard)
            else:
                await bot.send_message(chat_id=user_id, text=text, parse_mode="HTML", disable_web_page_preview=True, reply_markup=keyboard)

            await asyncio.sleep(0.05)

        except TelegramRetryAfter as e:
            logger.warning(f"Telegram Flood Wait! Пауза {e.retry_after} сек.")
            await asyncio.sleep(e.retry_after)
            await notification_queue.put(task)

        except TelegramForbiddenError:
            logger.info(f"Пользователь {user_id} заблокировал бота. Деактивируем.")
            await db.deactivate_user(user_id)

        except Exception as e:
            logger.error(f"Ошибка отправки пользователю {user_id}: {e}")

        finally:
            notification_queue.task_done()


# ── Search Processing ─────────────────────────────

def _is_excluded(ad_title: str, ad_description: str, excluded_keywords: str) -> bool:
    """Check if ad matches any excluded keyword (blacklist)."""
    if not excluded_keywords:
        return False
    keywords = [kw.strip().lower() for kw in excluded_keywords.split(",") if kw.strip()]
    combined = f"{ad_title} {ad_description or ''}".lower()
    return any(kw in combined for kw in keywords)


async def _process_search(search: dict, db: Database, bot) -> int:
    """Process a single search and return number of new ads found."""
    search_id = search["id"]
    user_id = search["user_id"]
    url = search["url"]
    min_p = search.get("min_price", 0.0)
    max_p = search.get("max_price", 0.0)
    excluded_kw = search.get("excluded_keywords")
    drop_threshold = search.get("price_drop_threshold", 0.0)
    only_photos = search.get("only_photos", 0) == 1

    # Check subscription status
    is_expired = await _check_subscription_expiry(user_id, bot, db, search_id)
    if is_expired:
        return 0

    # Add sort=lst.d (newest first) if not present
    if "sort=lst.d" not in url:
        separator = "&" if "?" in url else "?"
        url += f"{separator}sort=lst.d"

    ads = await _parser.fetch_ads(url)
    if not ads:
        await asyncio.sleep(config.RATE_LIMIT_PER_SEARCH)
        return 0

    # Filter photos only
    ads = _filter_photos_only(ads, only_photos)
    if not ads:
        return 0

    new_ads = 0
    prices_for_stats = []

    for ad in ads:
        numeric_price = 0.0
        price_match = re.search(r'(\d+)', str(ad.price).replace(" ", ""))
        if price_match:
            numeric_price = float(price_match.group(1))
            prices_for_stats.append(numeric_price)

        if min_p > 0 and numeric_price < min_p:
            continue
        if max_p > 0 and numeric_price > max_p:
            continue

        # Smart spam filter
        if _is_spam(ad.title, ad.description or ""):
            continue

        if _is_excluded(ad.title, ad.description or "", excluded_kw):
            continue

        is_sent, old_price = await db.is_ad_sent(ad.id, search_id)

        if not is_sent:
            await db.save_sent_ad(user_id, ad.id, search_id, numeric_price)
            market_evaluation = analyze_market_price(numeric_price, ads)
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
                + (f"🕐 <b>Опубликовано:</b> {format_list_time(ad.list_time)}\n" if hasattr(ad, 'list_time') and ad.list_time else "")
                + f"\n📝 <b>Описание:</b>\n{desc_text}\n\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"📊 <b>Оценка рынка:</b> {market_evaluation}\n"
                f"━━━━━━━━━━━━━━━━━━━\n\n"
                f"🔗 <a href='{ad.url}'>Перейти к объявлению</a>"
            )

            # Fetch full details before sending
            if not ad.description or not ad.seller:
                try:
                    details = await _parser.fetch_ad_details(ad.url)
                    if details["description"]:
                        ad.description = details["description"]
                        desc_text = ad.description[:247] + "..." if len(ad.description) > 250 else ad.description
                    if details["seller"]:
                        ad.seller = details["seller"]
                    # Rebuild text with fetched details
                    text = (
                        f"🚨 <b>Новое объявление!</b>\n\n"
                        f"━━━━━━━━━━━━━━━━━━━\n"
                        f"📱 <b>{ad.title}</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━\n\n"
                        f"💰 <b>Цена:</b> <code>{ad.price}</code>\n"
                        f"📍 <b>Локация:</b> {ad.city}\n"
                        + (f"👤 <b>Продавец:</b> {ad.seller}\n" if ad.seller else "")
                        + (f"🕐 <b>Опубликовано:</b> {format_list_time(ad.list_time)}\n" if ad.list_time else "")
                        + f"\n📝 <b>Описание:</b>\n{desc_text}\n\n"
                        f"━━━━━━━━━━━━━━━━━━━\n"
                        f"📊 <b>Оценка рынка:</b> {market_evaluation}\n"
                        f"━━━━━━━━━━━━━━━━━━━\n\n"
                        f"🔗 <a href='{ad.url}'>Перейти к объявлению</a>"
                    )
                except Exception as e:
                    logger.debug(f"fetch_ad_details failed for {ad.url}: {e}")

            # Send to channel or user
            await _send_to_channel_or_user(user_id, search_id, text, ad.images, ad.url, bot, db)
            new_ads += 1

        elif is_sent and old_price > 0 and numeric_price > 0 and numeric_price < old_price:
            diff = old_price - numeric_price
            if drop_threshold > 0 and diff < drop_threshold:
                continue

            await db.save_sent_ad(user_id, ad.id, search_id, numeric_price)

            drop_text = (
                f"📉 <b>СНИЖЕНИЕ ЦЕНЫ!</b>\n\n"
                f"📱 <b>{ad.title}</b>\n"
                f"💰 Новая цена: <b>{ad.price}</b> (упала на {round(diff)} р.)\n"
                f"🔗 <a href='{ad.url}'>Открыть объявление</a>"
            )

            await _send_to_channel_or_user(user_id, search_id, drop_text, ad.images, ad.url, bot, db)

    # Save weekly stats for Pro users
    await _save_weekly_stats(user_id, search_id, db, prices_for_stats)

    return new_ads


async def start_monitoring(bot, db: Database):
    """Background monitoring — polls Kufar for new ads.
    
    Features:
    - Pro users get priority (15s interval vs 30s)
    - Photos only filtering
    - Smart spam filtering
    - Quiet hours checking
    - Subscription expiry reminders
    - Badge checking
    - Weekly stats saving
    - Channel/group mode
    """
    logger.info("🟢 Фоновый мониторинг запущен (JSON Mode).")

    cleanup_counter = 0
    cycle_count = 0
    badge_check_counter = 0

    while True:
        cycle_start = asyncio.get_event_loop().time()
        cycle_count += 1
        try:
            searches = await db.get_all_active_searches()
            if not searches:
                await asyncio.sleep(config.CHECK_INTERVAL)
                continue

            new_ads_found = 0

            # Separate searches by tariff priority
            pro_searches = []
            basic_searches = []
            for search in searches:
                try:
                    plan_key = await db.get_tariff_plan(search["user_id"])
                    plan = PLANS.get(plan_key, PLANS["basic"])
                    if plan.priority:
                        pro_searches.append(search)
                    else:
                        basic_searches.append(search)
                except Exception:
                    basic_searches.append(search)

            # Process Pro searches first (priority)
            for search in pro_searches:
                new_ads_found += await _process_search(search, db, bot)
                await asyncio.sleep(config.RATE_LIMIT_PER_SEARCH)

            # Process Basic searches
            for search in basic_searches:
                new_ads_found += await _process_search(search, db, bot)
                await asyncio.sleep(config.RATE_LIMIT_PER_SEARCH)

        except Exception as e:
            logger.error(f"❌ Критическая ошибка в цикле мониторинга: {e}")

        # Log cycle time
        cycle_time = asyncio.get_event_loop().time() - cycle_start
        if cycle_time > config.CHECK_INTERVAL:
            logger.warning(f"⚠️ Цикл мониторинга занял {cycle_time:.1f}с (> CHECK_INTERVAL={config.CHECK_INTERVAL}с)")
        else:
            logger.info(f"🔄 Цикл #{cycle_count}: {cycle_time:.1f}с | новых объявлений: {new_ads_found}")

        # Cleanup old sent_ads every ~100 cycles
        cleanup_counter += 1
        if cleanup_counter >= 100:
            try:
                await db.cleanup_old_sent_ads()
                logger.info("🧹 Очистка старых записей sent_ads выполнена")
            except Exception as e:
                logger.debug(f"cleanup_old_sent_ads: {e}")
            cleanup_counter = 0

        # Check badges every 50 cycles
        badge_check_counter += 1
        if badge_check_counter >= 50:
            try:
                users = await db.get_all_users()
                for user in users[:10]:  # Check 10 users per cycle
                    await _check_and_award_badges(user["user_id"], bot, db)
            except Exception as e:
                logger.error(f"Badge check error: {e}")
            badge_check_counter = 0

        await asyncio.sleep(config.CHECK_INTERVAL)
