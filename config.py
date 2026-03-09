"""
Конфигурационный файл бота
"""
import os
from dataclasses import dataclass

@dataclass
class Config:
    """Конфигурация бота"""
    BOT_TOKEN: str = "YOUR_BOT_TOKEN_HERE"  # Замените на токен от @BotFather
    ADMIN_IDS: list = None  # Список ID администраторов
    
    # Настройки базы данных
    DB_PATH: str = "bot.db"
    
    # Комиссия платформы (в процентах)
    PLATFORM_FEE: int = 5
    
    # Настройки Telegram Stars
    STARS_PER_PURCHASE: int = 1  # Звёзды за покупку (бонус)
    
    def __post_init__(self):
        if self.ADMIN_IDS is None:
            self.ADMIN_IDS = [123456789]  # Замените на свой ID

# Создаем экземпляр конфигурации
config = Config()

# Для удобства импорта
BOT_TOKEN = config.BOT_TOKEN
ADMIN_IDS = config.ADMIN_IDS
DB_PATH = config.DB_PATH
PLATFORM_FEE = config.PLATFORM_FEE
STARS_PER_PURCHASE = config.STARS_PER_PURCHASE
