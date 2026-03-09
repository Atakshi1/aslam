"""
Вспомогательные функции
"""
import re
from datetime import datetime, timedelta
from typing import Optional

def validate_price(price: float) -> bool:
    """Проверка корректности цены"""
    return 0.01 <= price <= 1000000

def validate_title(title: str) -> bool:
    """Проверка названия товара"""
    return 3 <= len(title.strip()) <= 100

def format_number(num: float) -> str:
    """Форматирование числа"""
    if num >= 1_000_000:
        return f"{num/1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num/1_000:.1f}K"
    return str(int(num)) if num.is_integer() else f"{num:.2f}"

def escape_markdown(text: str) -> str:
    """Экранирование спецсимволов для Markdown"""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

def format_time_ago(dt: datetime) -> str:
    """Форматирование времени"""
    now = datetime.now()
    diff = now - dt
    
    if diff < timedelta(minutes=1):
        return "только что"
    elif diff < timedelta(hours=1):
        minutes = diff.seconds // 60
        return f"{minutes} мин. назад"
    elif diff < timedelta(days=1):
        hours = diff.seconds // 3600
        return f"{hours} ч. назад"
    elif diff < timedelta(days=7):
        days = diff.days
        return f"{days} дн. назад"
    else:
        return dt.strftime("%d.%m.%Y")
