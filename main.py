"""Kufar Online Bot — entry point."""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from src.core.config import config
from src.core.logger import setup_logging
from src.core.database import Database
from src.handlers import router, set_database
from src.monitor import send_worker, start_monitoring


logger = logging.getLogger(__name__)


async def notify_admin_on_startup(bot: Bot):
    """Send startup notification to admin."""
    if config.ADMIN_ID:
        try:
            await bot.send_message(
                config.ADMIN_ID,
                "🤖 <b>Бот Kufar Online запущен и работает!</b>\n\n"
                "✅ Новые функции:\n"
                "📸 Только фото\n"
                "🌍 Мультиязычность (RU/BY/EN)\n"
                "📊 Расширенная аналитика Pro\n"
                "⏰ Напоминания о конце подписки\n"
                "🕐 Тихие часы\n"
                "📢 Групповой режим (каналы)\n"
                "🏆 Геймификация (бейджи)\n"
                "🧠 Умный спам-фильтр\n"
                "💤 Напоминания о неактивности",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Не удалось уведомить админа: {e}")


async def setup_bot_ui(bot: Bot):
    """Set up bot menu button and command list."""
    from aiogram.types import BotCommand, MenuButtonCommands
    await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    await bot.set_my_commands([
        BotCommand(command="start", description="🏠 Главное меню"),
        BotCommand(command="profile", description="👤 Личный кабинет"),
        BotCommand(command="stats", description="📊 Статистика"),
        BotCommand(command="badges", description="🏆 Бейджи"),
        BotCommand(command="language", description="🌍 Язык"),
        BotCommand(command="quiet", description="🕐 Тихие часы"),
    ])


async def main():
    setup_logging()
    logger.info("🤖 Запуск бота Kufar Online...")

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()
    dp.include_router(router)

    db = Database()
    await db.init_db()
    set_database(db)

    await setup_bot_ui(bot)

    send_task = asyncio.create_task(send_worker(bot, db))
    monitoring_task = asyncio.create_task(start_monitoring(bot, db))

    await bot.delete_webhook(drop_pending_updates=True)
    await notify_admin_on_startup(bot)

    try:
        await dp.start_polling(bot)
    finally:
        logger.info("🛑 Остановка бота...")
        monitoring_task.cancel()
        send_task.cancel()
        await asyncio.gather(monitoring_task, send_task, return_exceptions=True)
        await db.close()
        await bot.session.close()
        logger.info("✅ Бот остановлен корректно.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("🛑 Бот остановлен пользователем.")
