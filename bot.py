#!/usr/bin/env python3
"""
ScornX Market - Telegram бот с поддержкой звёзд и БД
Главный файл запуска
"""
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN, ADMIN_IDS
from database import db
from handlers import common, user, seller, admin

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher(storage=MemoryStorage())

# Подключение роутеров
dp.include_router(common.router)
dp.include_router(user.router)
dp.include_router(seller.router)
dp.include_router(admin.router)

async def on_startup():
    """Действия при запуске"""
    logger.info("=" * 50)
    logger.info("Запуск ScornX Market бота...")
    logger.info(f"Токен: {BOT_TOKEN[:10]}...")
    logger.info(f"Администраторы: {ADMIN_IDS}")
    logger.info("=" * 50)
    
    # Инициализация БД
    await db.init_db()
    logger.info("✅ База данных инициализирована")
    
    # Проверка администраторов
    for admin_id in ADMIN_IDS:
        await db.add_user(admin_id)
        await db.update_user_role(admin_id, "admin")
        logger.info(f"✅ Администратор {admin_id} проверен")
    
    # Установка команд бота
    await bot.set_my_commands([
        ("start", "🚀 Запустить бота"),
        ("menu", "📱 Главное меню"),
        ("help", "❓ Помощь"),
        ("profile", "👤 Мой профиль"),
        ("balance", "💰 Мой баланс"),
    ])
    
    logger.info("✅ Бот готов к работе!")

async def on_shutdown():
    """Действия при остановке"""
    logger.info("🛑 Бот останавливается...")
    await bot.session.close()
    logger.info("✅ Бот остановлен")

async def main():
    """Главная функция"""
    try:
        await on_startup()
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске бота: {e}")
    finally:
        await on_shutdown()

if __name__ == "__main__":
    asyncio.run(main())
