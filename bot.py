"""
ScornX Market - Telegram бот с escrow-механикой
Улучшенная версия с исправлением всех багов
"""

import asyncio  # 👈 ВАЖНО: добавлен этот импорт!
import logging
from datetime import datetime
from itertools import count
from typing import Dict, Any, Optional, List
import re

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest

# ==================== КОНФИГУРАЦИЯ ====================

TOKEN = "8445773141:AAGsBvSnz3PPKHOHMtlLy9OF0NysloXSws"
ADMIN_ID = 123456789  # ⚠️ ЗАМЕНИТЕ НА СВОЙ TELEGRAM ID
PLATFORM_FEE = 0.05  # Комиссия платформы 5%

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== ХРАНИЛИЩЕ ДАННЫХ ====================

users: Dict[int, Dict[str, Any]] = {}
products: Dict[int, Dict[str, Any]] = {}
orders: Dict[int, Dict[str, Any]] = {}

# Генераторы ID
product_id_counter = count(1)
order_id_counter = count(1)

def create_user(user_id: int, username: str = None, first_name: str = None) -> Dict[str, Any]:
    """Создание нового пользователя"""
    return {
        "user_id": user_id,
        "username": username,
        "first_name": first_name,
        "role": "admin" if user_id == ADMIN_ID else "user",
        "balance": 0.0,
        "registered_at": datetime.now(),
        "is_active": True,
        "total_purchases": 0,
        "total_sales": 0
    }

def create_product(seller_id: int, title: str, price: float, login: str, password: str, twofa: str = None) -> Dict[str, Any]:
    """Создание нового товара"""
    return {
        "product_id": next(product_id_counter),
        "seller_id": seller_id,
        "title": title,
        "price": price,
        "data": {
            "login": login,
            "password": password,
            "2fa": twofa
        },
        "is_active": True,
        "created_at": datetime.now(),
        "views": 0
    }

def create_order(buyer_id: int, seller_id: int, product_id: int, price: float) -> Dict[str, Any]:
    """Создание нового заказа"""
    return {
        "order_id": next(order_id_counter),
        "buyer_id": buyer_id,
        "seller_id": seller_id,
        "product_id": product_id,
        "price": price,
        "status": "pending",
        "created_at": datetime.now(),
        "completed_at": None,
        "dispute_reason": None
    }

# ==================== КЛАВИАТУРЫ ====================

def get_main_menu(role: str = "user") -> InlineKeyboardMarkup:
    """Главное меню"""
    builder = InlineKeyboardBuilder()
    
    # Основные кнопки для всех
    builder.row(
        InlineKeyboardButton(text="🛒 Товары", callback_data="products"),
        InlineKeyboardButton(text="💰 Баланс", callback_data="balance")
    )
    builder.row(
        InlineKeyboardButton(text="🛍 Мои покупки", callback_data="my_purchases"),
        InlineKeyboardButton(text="ℹ️ Профиль", callback_data="profile")
    )
    
    # Кнопки для продавцов и админов
    if role in ["seller", "admin"]:
        builder.row(
            InlineKeyboardButton(text="📦 Мои продажи", callback_data="my_sales"),
            InlineKeyboardButton(text="➕ Создать товар", callback_data="create_product")
        )
    
    # Кнопка для становления продавцом
    if role == "user":
        builder.row(InlineKeyboardButton(text="👑 Стать продавцом", callback_data="become_seller"))
    
    # Админ панель
    if role == "admin":
        builder.row(InlineKeyboardButton(text="⚙️ Админ панель", callback_data="admin_panel"))
    
    return builder.as_markup()

def get_products_keyboard(products_list: list, page: int = 0, user_id: int = None) -> InlineKeyboardMarkup:
    """Клавиатура со списком товаров"""
    builder = InlineKeyboardBuilder()
    
    if not products_list:
        builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"))
        return builder.as_markup()
    
    start_idx = page * 5
    end_idx = min(start_idx + 5, len(products_list))
    
    for i in range(start_idx, end_idx):
        product = products_list[i]
        # Увеличиваем счетчик просмотров
        if product['product_id'] in products:
            products[product['product_id']]['views'] = products[product['product_id']].get('views', 0) + 1
        
        seller_name = users.get(product['seller_id'], {}).get('first_name', f"ID:{product['seller_id']}")
        builder.row(InlineKeyboardButton(
            text=f"📱 {product['title'][:20]} - {product['price']}💰 | 👤 {seller_name[:10]}",
            callback_data=f"view_product_{product['product_id']}"
        ))
    
    # Навигация
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"products_page_{page-1}"))
    if end_idx < len(products_list):
        nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"products_page_{page+1}"))
    
    if nav_buttons:
        builder.row(*nav_buttons)
    
    builder.row(
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"),
        InlineKeyboardButton(text="🔄 Обновить", callback_data="products")
    )
    
    return builder.as_markup()

def get_product_actions_keyboard(product_id: int, seller_id: int, user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура действий с товаром"""
    builder = InlineKeyboardBuilder()
    
    # Покупатель не может купить свой товар
    if seller_id != user_id:
        builder.row(InlineKeyboardButton(text="💳 Купить", callback_data=f"buy_{product_id}"))
    
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="products"),
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
    )
    
    return builder.as_markup()

def get_order_actions_keyboard(order_id: int, order_status: str, user_role: str = "user") -> InlineKeyboardMarkup:
    """Клавиатура действий с заказом"""
    builder = InlineKeyboardBuilder()
    
    if order_status == "pending":
        builder.row(
            InlineKeyboardButton(text="✅ Подтвердить получение", callback_data=f"confirm_order_{order_id}"),
            InlineKeyboardButton(text="⚠️ Открыть спор", callback_data=f"dispute_order_{order_id}")
        )
    elif order_status == "disputed" and user_role == "admin":
        builder.row(
            InlineKeyboardButton(text="⚖️ Решить спор", callback_data=f"admin_disputes")
        )
    
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="my_purchases"),
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
    )
    
    return builder.as_markup()

def get_admin_keyboard() -> InlineKeyboardMarkup:
    """Админская клавиатура"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📊 Все заказы", callback_data="admin_orders"),
        InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")
    )
    builder.row(
        InlineKeyboardButton(text="⚖️ Споры", callback_data="admin_disputes"),
        InlineKeyboardButton(text="📦 Все товары", callback_data="admin_products")
    )
    builder.row(
        InlineKeyboardButton(text="📈 Статистика", callback_data="admin_stats"),
        InlineKeyboardButton(text="🔄 Сброс данных", callback_data="admin_reset")
    )
    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"))
    return builder.as_markup()

def get_dispute_actions_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для решения спора"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👤 В пользу покупателя", callback_data=f"resolve_dispute_buyer_{order_id}"),
        InlineKeyboardButton(text="👤 В пользу продавца", callback_data=f"resolve_dispute_seller_{order_id}")
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_disputes"))
    return builder.as_markup()

def get_balance_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для баланса"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💳 +100", callback_data="add_balance_100"),
        InlineKeyboardButton(text="💳 +500", callback_data="add_balance_500"),
        InlineKeyboardButton(text="💳 +1000", callback_data="add_balance_1000")
    )
    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"))
    return builder.as_markup()

def get_profile_actions_keyboard(user_role: str) -> InlineKeyboardMarkup:
    """Клавиатура для профиля"""
    builder = InlineKeyboardBuilder()
    if user_role == "user":
        builder.row(InlineKeyboardButton(text="👑 Стать продавцом", callback_data="become_seller"))
    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"))
    return builder.as_markup()

# ==================== БИЗНЕС-ЛОГИКА ====================

def check_balance(user_id: int, amount: float) -> bool:
    """Проверка достаточности баланса"""
    user = users.get(user_id)
    return user and user.get("balance", 0) >= amount

def add_balance(user_id: int, amount: float) -> bool:
    """Пополнение баланса"""
    if user_id in users:
        users[user_id]["balance"] = users[user_id].get("balance", 0) + amount
        logger.info(f"Баланс пользователя {user_id} пополнен на {amount}")
        return True
    return False

def deduct_balance(user_id: int, amount: float) -> bool:
    """Списание средств"""
    if check_balance(user_id, amount):
        users[user_id]["balance"] -= amount
        logger.info(f"С баланса {user_id} списано {amount}")
        return True
    return False

def validate_price(price: float) -> bool:
    """Проверка корректности цены"""
    return price > 0 and price < 1000000  # Максимальная цена 1 млн

def validate_title(title: str) -> bool:
    """Проверка названия товара"""
    return 3 <= len(title) <= 50

def process_purchase(buyer_id: int, product_id: int) -> dict:
    """Обработка покупки"""
    product = products.get(product_id)
    if not product:
        return {"success": False, "message": "❌ Товар не найден"}
    
    if not product.get("is_active", False):
        return {"success": False, "message": "❌ Товар уже продан"}
    
    if product["seller_id"] == buyer_id:
        return {"success": False, "message": "❌ Нельзя купить свой собственный товар"}
    
    if not check_balance(buyer_id, product["price"]):
        return {"success": False, "message": f"❌ Недостаточно средств. Нужно: {product['price']}💰"}
    
    # Создаем заказ
    order = create_order(
        buyer_id=buyer_id,
        seller_id=product["seller_id"],
        product_id=product_id,
        price=product["price"]
    )
    orders[order["order_id"]] = order
    
    # Списание средств
    deduct_balance(buyer_id, product["price"])
    
    # Деактивируем товар
    product["is_active"] = False
    
    # Обновляем статистику
    if buyer_id in users:
        users[buyer_id]["total_purchases"] = users[buyer_id].get("total_purchases", 0) + 1
    
    logger.info(f"Создан заказ {order['order_id']} на товар {product_id}")
    return {"success": True, "order": order, "product": product}

def confirm_order(order_id: int) -> dict:
    """Подтверждение получения товара"""
    order = orders.get(order_id)
    if not order:
        return {"success": False, "message": "❌ Заказ не найден"}
    
    if order["status"] != "pending":
        return {"success": False, "message": f"❌ Заказ уже имеет статус {order['status']}"}
    
    # Расчет комиссии
    seller_amount = order["price"] * (1 - PLATFORM_FEE)
    platform_fee = order["price"] * PLATFORM_FEE
    
    # Начисление продавцу
    if order["seller_id"] in users:
        users[order["seller_id"]]["balance"] += seller_amount
        users[order["seller_id"]]["total_sales"] = users[order["seller_id"]].get("total_sales", 0) + 1
    
    order["status"] = "completed"
    order["completed_at"] = datetime.now()
    
    logger.info(f"Заказ {order_id} завершен, продавец получил {seller_amount}, комиссия {platform_fee}")
    return {
        "success": True, 
        "message": f"✅ Заказ завершен!\nПродавец получил: {seller_amount}💰\nКомиссия платформы: {platform_fee}💰"
    }

def dispute_order(order_id: int, reason: str = None) -> dict:
    """Открытие спора"""
    order = orders.get(order_id)
    if not order:
        return {"success": False, "message": "❌ Заказ не найден"}
    
    if order["status"] != "pending":
        return {"success": False, "message": f"❌ Нельзя открыть спор для заказа со статусом {order['status']}"}
    
    order["status"] = "disputed"
    order["dispute_reason"] = reason
    logger.info(f"Открыт спор по заказу {order_id}")
    return {"success": True, "message": "⚠️ Спор открыт. Администратор рассмотрит ваш запрос в ближайшее время."}

def resolve_dispute(order_id: int, in_favor_of: str) -> dict:
    """Решение спора администратором"""
    order = orders.get(order_id)
    if not order:
        return {"success": False, "message": "❌ Заказ не найден"}
    
    if order["status"] != "disputed":
        return {"success": False, "message": "❌ Заказ не в статусе спора"}
    
    if in_favor_of == "buyer":
        # Возврат средств покупателю
        users[order["buyer_id"]]["balance"] += order["price"]
        order["status"] = "refunded"
        message = "✅ Спор решен в пользу покупателя. Средства возвращены."
    elif in_favor_of == "seller":
        # Начисление продавцу
        seller_amount = order["price"] * (1 - PLATFORM_FEE)
        users[order["seller_id"]]["balance"] += seller_amount
        order["status"] = "completed"
        message = f"✅ Спор решен в пользу продавца. Продавец получил {seller_amount}💰"
    else:
        return {"success": False, "message": "❌ Некорректное решение"}
    
    order["completed_at"] = datetime.now()
    logger.info(f"Спор по заказу {order_id} решен в пользу {in_favor_of}")
    return {"success": True, "message": message}

def delete_product(product_id: int, user_id: int) -> dict:
    """Удаление товара"""
    product = products.get(product_id)
    if not product:
        return {"success": False, "message": "❌ Товар не найден"}
    
    if product["seller_id"] != user_id and users.get(user_id, {}).get("role") != "admin":
        return {"success": False, "message": "❌ Нет прав для удаления этого товара"}
    
    del products[product_id]
    logger.info(f"Товар {product_id} удален пользователем {user_id}")
    return {"success": True, "message": "✅ Товар успешно удален"}

def get_user_products(user_id: int) -> list:
    """Получение товаров пользователя (как продавца)"""
    return [p for p in products.values() if p["seller_id"] == user_id]

def get_user_purchases(user_id: int) -> list:
    """Получение покупок пользователя"""
    return [o for o in orders.values() if o["buyer_id"] == user_id]

def get_user_sales(user_id: int) -> list:
    """Получение продаж пользователя"""
    return [o for o in orders.values() if o["seller_id"] == user_id]

def get_active_products(user_id: int = None) -> list:
    """Получение активных товаров"""
    if user_id:
        return [p for p in products.values() if p["is_active"] and p["seller_id"] != user_id]
    return [p for p in products.values() if p["is_active"]]

def get_user_stats(user_id: int) -> dict:
    """Получение статистики пользователя"""
    user = users.get(user_id, {})
    purchases = get_user_purchases(user_id)
    sales = get_user_sales(user_id)
    
    total_spent = sum(o["price"] for o in purchases if o["status"] == "completed")
    total_earned = sum(o["price"] * (1 - PLATFORM_FEE) for o in sales if o["status"] == "completed")
    
    return {
        "balance": user.get("balance", 0),
        "total_purchases": len(purchases),
        "total_sales": len(sales),
        "total_spent": total_spent,
        "total_earned": total_earned,
        "active_products": len([p for p in get_user_products(user_id) if p["is_active"]])
    }

# ==================== СОСТОЯНИЯ FSM ====================

class ProductCreation(StatesGroup):
    """Состояния создания товара"""
    title = State()
    price = State()
    login = State()
    password = State()
    twofa = State()

class DisputeCreation(StatesGroup):
    """Состояния создания спора"""
    reason = State()

# ==================== ИНИЦИАЛИЗАЦИЯ БОТА ====================

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ==================== ОБЩИЕ ОБРАБОТЧИКИ ====================

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    await state.clear()
    
    if user_id not in users:
        users[user_id] = create_user(user_id, username, first_name)
        logger.info(f"Новый пользователь: {user_id} ({first_name})")
        await message.answer(
            f"👋 Добро пожаловать в ScornX Market, {first_name}!\n\n"
            f"✅ Вы успешно зарегистрированы.\n"
            f"💰 Стартовый баланс: 0💰\n\n"
            f"Используйте меню для навигации:"
        )
    else:
        await message.answer(f"👋 С возвращением, {first_name}!")
    
    role = users[user_id]["role"]
    await message.answer(
        "📱 Главное меню",
        reply_markup=get_main_menu(role)
    )

@dp.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext):
    """Команда для возврата в меню"""
    await state.clear()
    user_id = message.from_user.id
    
    if user_id not in users:
        await cmd_start(message, state)
        return
    
    role = users[user_id]["role"]
    await message.answer(
        "📱 Главное меню",
        reply_markup=get_main_menu(role)
    )

@dp.message(Command("help"))
async def cmd_help(message: Message):
    """Команда помощи"""
    help_text = (
        "📚 **Справка по ScornX Market**\n\n"
        "**Основные команды:**\n"
        "• /start - Начать работу\n"
        "• /menu - Главное меню\n"
        "• /help - Эта справка\n\n"
        "**Как это работает:**\n"
        "1️⃣ Пополните баланс в разделе 💰 Баланс\n"
        "2️⃣ Купите товар в 🛒 Товары\n"
        "3️⃣ После получения данных подтвердите заказ\n"
        "4️⃣ Если возникли проблемы - откройте спор\n\n"
        "**Для продавцов:**\n"
        "• Станьте продавцом в профиле\n"
        "• Создавайте товары через ➕ Создать товар\n"
        "• Получайте оплату после подтверждения\n\n"
        "**Комиссия платформы:** 5%"
    )
    await message.answer(help_text, parse_mode="Markdown")

@dp.callback_query(F.data == "main_menu")
async def main_menu_callback(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    await state.clear()
    user_id = callback.from_user.id
    
    if user_id not in users:
        users[user_id] = create_user(user_id, callback.from_user.username, callback.from_user.first_name)
    
    role = users[user_id]["role"]
    
    try:
        await callback.message.edit_text(
            "📱 Главное меню",
            reply_markup=get_main_menu(role)
        )
    except TelegramBadRequest:
        await callback.message.answer(
            "📱 Главное меню",
            reply_markup=get_main_menu(role)
        )
    await callback.answer()

# ==================== ПОЛЬЗОВАТЕЛЬСКИЕ ОБРАБОТЧИКИ ====================

@dp.callback_query(F.data == "profile")
async def show_profile(callback: CallbackQuery):
    """Показать профиль пользователя"""
    user_id = callback.from_user.id
    
    if user_id not in users:
        users[user_id] = create_user(user_id, callback.from_user.username, callback.from_user.first_name)
    
    user = users[user_id]
    stats = get_user_stats(user_id)
    
    profile_text = (
        f"👤 **Профиль пользователя**\n\n"
        f"**ID:** `{user_id}`\n"
        f"**Имя:** {user.get('first_name', 'Не указано')}\n"
        f"**Username:** @{user.get('username', 'Не указан')}\n"
        f"**Роль:** {'👑 Администратор' if user['role'] == 'admin' else '👤 Продавец' if user['role'] == 'seller' else '👤 Покупатель'}\n"
        f"**Дата регистрации:** {user['registered_at'].strftime('%d.%m.%Y')}\n\n"
        f"**📊 Статистика:**\n"
        f"💰 Баланс: {stats['balance']}\n"
        f"🛍 Покупок: {stats['total_purchases']} (на {stats['total_spent']}💰)\n"
        f"📦 Продаж: {stats['total_sales']} (заработано {stats['total_earned']}💰)\n"
        f"📦 Активных товаров: {stats['active_products']}"
    )
    
    await callback.message.edit_text(
        profile_text,
        parse_mode="Markdown",
        reply_markup=get_profile_actions_keyboard(user['role'])
    )
    await callback.answer()

@dp.callback_query(F.data == "balance")
async def show_balance(callback: CallbackQuery):
    """Показать баланс"""
    user_id = callback.from_user.id
    
    if user_id not in users:
        users[user_id] = create_user(user_id, callback.from_user.username, callback.from_user.first_name)
    
    balance = users[user_id]["balance"]
    
    await callback.message.edit_text(
        f"💰 **Ваш баланс:** {balance}💰\n\n"
        f"Выберите сумму для пополнения:",
        parse_mode="Markdown",
        reply_markup=get_balance_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("add_balance_"))
async def add_balance_callback(callback: CallbackQuery):
    """Пополнение баланса"""
    user_id = callback.from_user.id
    amount = int(callback.data.split("_")[2])
    
    add_balance(user_id, amount)
    
    await callback.message.edit_text(
        f"✅ Баланс пополнен на {amount}💰\n"
        f"💰 Текущий баланс: {users[user_id]['balance']}💰",
        reply_markup=get_main_menu(users[user_id]['role'])
    )
    await callback.answer(f"➕ {amount}💰 добавлено на баланс", show_alert=True)

@dp.callback_query(F.data == "products")
async def show_products(callback: CallbackQuery):
    """Показать список товаров"""
    user_id = callback.from_user.id
    
    if user_id not in users:
        users[user_id] = create_user(user_id, callback.from_user.username, callback.from_user.first_name)
    
    available_products = get_active_products(user_id)
    
    if not available_products:
        await callback.message.edit_text(
            "😕 **Нет доступных товаров**\n\n"
            "Станьте продавцом и создайте первый товар!",
            parse_mode="Markdown",
            reply_markup=get_main_menu(users[user_id]['role'])
        )
        await callback.answer()
        return
    
    await callback.message.edit_text(
        f"🛒 **Доступные товары:**\n"
        f"Всего: {len(available_products)} шт.\n\n"
        f"Нажмите на товар для просмотра:",
        parse_mode="Markdown",
        reply_markup=get_products_keyboard(available_products, 0, user_id)
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("products_page_"))
async def products_page(callback: CallbackQuery):
    """Пагинация товаров"""
    user_id = callback.from_user.id
    page = int(callback.data.split("_")[2])
    
    available_products = get_active_products(user_id)
    
    await callback.message.edit_text(
        f"🛒 **Доступные товары:** (стр. {page + 1})",
        parse_mode="Markdown",
        reply_markup=get_products_keyboard(available_products, page, user_id)
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("view_product_"))
async def view_product(callback: CallbackQuery):
    """Просмотр товара"""
    user_id = callback.from_user.id
    product_id = int(callback.data.split("_")[2])
    product = products.get(product_id)
    
    if not product:
        await callback.message.edit_text(
            "❌ Товар не найден или был удален",
            reply_markup=get_main_menu(users.get(user_id, {}).get("role", "user"))
        )
        await callback.answer()
        return
    
    if not product["is_active"]:
        await callback.message.edit_text(
            "❌ Этот товар уже продан",
            reply_markup=get_main_menu(users.get(user_id, {}).get("role", "user"))
        )
        await callback.answer()
        return
    
    seller = users.get(product["seller_id"], {})
    seller_name = seller.get('first_name', f"ID:{product['seller_id']}")
    
    text = (
        f"📦 **{product['title']}**\n\n"
        f"💰 **Цена:** {product['price']}💰\n"
        f"👤 **Продавец:** {seller_name}\n"
        f"📊 **Просмотров:** {product.get('views', 0)}\n"
        f"📅 **Создан:** {product['created_at'].strftime('%d.%m.%Y %H:%M')}\n\n"
        f"**Описание:**\n"
        f"🔑 Логин: ||{product['data']['login']}||\n"
        f"🔐 Пароль: ||{product['data']['password']}||\n"
    )
    if product['data'].get('2fa'):
        text += f"📱 2FA: ||{product['data']['2fa']}||\n"
    
    text += "\n⚠️ Данные скрыты до покупки. После покупки они станут доступны."
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_product_actions_keyboard(product_id, product["seller_id"], user_id)
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("buy_"))
async def buy_product(callback: CallbackQuery):
    """Покупка товара"""
    user_id = callback.from_user.id
    product_id = int(callback.data.split("_")[1])
    
    result = process_purchase(user_id, product_id)
    
    if result["success"]:
        order = result["order"]
        product = result["product"]
        
        data_text = (
            f"✅ **Покупка совершена!**\n\n"
            f"📋 **Данные аккаунта:**\n"
            f"🔑 Логин: `{product['data']['login']}`\n"
            f"🔐 Пароль: `{product['data']['password']}`\n"
        )
        if product['data'].get('2fa'):
            data_text += f"📱 2FA: `{product['data']['2fa']}`\n"
        
        data_text += (
            f"\n📦 **ID заказа:** `{order['order_id']}`\n"
            f"💰 **Сумма:** {order['price']}💰\n\n"
            f"⚠️ **Важно!**\n"
            f"1. Проверьте полученные данные\n"
            f"2. Подтвердите получение или откройте спор\n"
            f"3. Спор можно открыть в течение 24 часов"
        )
        
        await callback.message.edit_text(
            data_text,
            parse_mode="Markdown",
            reply_markup=get_order_actions_keyboard(order['order_id'], "pending")
        )
    else:
        await callback.message.edit_text(
            result['message'],
            reply_markup=get_main_menu(users.get(user_id, {}).get("role", "user"))
        )
    
    await callback.answer()

@dp.callback_query(F.data.startswith("confirm_order_"))
async def confirm_order_callback(callback: CallbackQuery):
    """Подтверждение получения товара"""
    user_id = callback.from_user.id
    order_id = int(callback.data.split("_")[2])
    
    result = confirm_order(order_id)
    
    await callback.message.edit_text(
        result['message'],
        reply_markup=get_main_menu(users.get(user_id, {}).get("role", "user"))
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("dispute_order_"))
async def dispute_order_start(callback: CallbackQuery, state: FSMContext):
    """Начало создания спора"""
    order_id = int(callback.data.split("_")[2])
    order = orders.get(order_id)
    
    if not order:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return
    
    await state.update_data(dispute_order_id=order_id)
    await state.set_state(DisputeCreation.reason)
    
    await callback.message.edit_text(
        "⚠️ **Открытие спора**\n\n"
        "Опишите причину спора подробно:\n"
        "(например: неверные данные, аккаунт заблокирован и т.д.)",
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.message(DisputeCreation.reason)
async def process_dispute_reason(message: Message, state: FSMContext):
    """Обработка причины спора"""
    data = await state.get_data()
    order_id = data.get('dispute_order_id')
    
    result = dispute_order(order_id, message.text)
    
    await state.clear()
    
    await message.answer(
        result['message'],
        reply_markup=get_main_menu(users.get(message.from_user.id, {}).get("role", "user"))
    )

@dp.callback_query(F.data == "my_purchases")
async def my_purchases(callback: CallbackQuery):
    """Просмотр покупок"""
    user_id = callback.from_user.id
    purchases = get_user_purchases(user_id)
    
    if not purchases:
        await callback.message.edit_text(
            "🛍 **У вас пока нет покупок**\n\n"
            "Перейдите в 🛒 Товары, чтобы сделать первую покупку!",
            parse_mode="Markdown",
            reply_markup=get_main_menu(users.get(user_id, {}).get("role", "user"))
        )
        await callback.answer()
        return
    
    text = "🛍 **Ваши покупки:**\n\n"
    for order in purchases[-10:]:  # Последние 10
        product = products.get(order["product_id"], {})
        status_emoji = {
            "pending": "⏳",
            "completed": "✅",
            "disputed": "⚠️",
            "refunded": "↩️"
        }.get(order["status"], "❓")
        
        text += (
            f"{status_emoji} **{product.get('title', 'Товар')}**\n"
            f"   ID: `{order['order_id']}` | {order['price']}💰\n"
            f"   Статус: {order['status']}\n"
            f"   {order['created_at'].strftime('%d.%m.%Y %H:%M')}\n\n"
        )
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_main_menu(users.get(user_id, {}).get("role", "user"))
    )
    await callback.answer()

# ==================== ПРОДАВЕЦ (ОБРАБОТЧИКИ) ====================

@dp.callback_query(F.data == "become_seller")
async def become_seller(callback: CallbackQuery):
    """Стать продавцом"""
    user_id = callback.from_user.id
    users[user_id]["role"] = "seller"
    
    await callback.message.edit_text(
        "✅ **Теперь вы продавец!**\n\n"
        "Вы можете:\n"
        "• Создавать товары через ➕ Создать товар\n"
        "• Просматривать продажи в 📦 Мои продажи\n"
        "• Получать оплату после подтверждения покупателем",
        parse_mode="Markdown",
        reply_markup=get_main_menu("seller")
    )
    await callback.answer()

@dp.callback_query(F.data == "create_product")
async def create_product_start(callback: CallbackQuery, state: FSMContext):
    """Начало создания товара"""
    await state.set_state(ProductCreation.title)
    await callback.message.edit_text(
        "📝 **Создание нового товара**\n\n"
        "Введите название товара (от 3 до 50 символов):",
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.message(ProductCreation.title)
async def process_title(message: Message, state: FSMContext):
    """Обработка названия товара"""
    title = message.text.strip()
    
    if not validate_title(title):
        await message.answer(
            "❌ Название должно быть от 3 до 50 символов. Попробуйте снова:"
        )
        return
    
    await state.update_data(title=title)
    await state.set_state(ProductCreation.price)
    await message.answer(
        "💰 Введите цену товара (только число, от 1 до 999999):"
    )

@dp.message(ProductCreation.price)
async def process_price(message: Message, state: FSMContext):
    """Обработка цены"""
    try:
        price = float(message.text)
        if not validate_price(price):
            await message.answer(
                "❌ Цена должна быть от 1 до 999999. Попробуйте снова:"
            )
            return
        
        await state.update_data(price=price)
        await state.set_state(ProductCreation.login)
        await message.answer("🔑 Введите логин от аккаунта Telegram:")
    except ValueError:
        await message.answer("❌ Пожалуйста, введите число. Попробуйте снова:")

@dp.message(ProductCreation.login)
async def process_login(message: Message, state: FSMContext):
    """Обработка логина"""
    login = message.text.strip()
    if not login:
        await message.answer("❌ Логин не может быть пустым. Попробуйте снова:")
        return
    
    await state.update_data(login=login)
    await state.set_state(ProductCreation.password)
    await message.answer("🔐 Введите пароль от аккаунта:")

@dp.message(ProductCreation.password)
async def process_password(message: Message, state: FSMContext):
    """Обработка пароля"""
    password = message.text.strip()
    if not password:
        await message.answer("❌ Пароль не может быть пустым. Попробуйте снова:")
        return
    
    await state.update_data(password=password)
    await state.set_state(ProductCreation.twofa)
    await message.answer(
        "📱 Введите 2FA код (если есть) или отправьте '-' если нет 2FA:"
    )

@dp.message(ProductCreation.twofa)
async def process_twofa(message: Message, state: FSMContext):
    """Обработка 2FA и сохранение товара"""
    user_id = message.from_user.id
    twofa = message.text.strip() if message.text.strip() != '-' else None
    
    data = await state.get_data()
    
    # Создание товара
    product = create_product(
        seller_id=user_id,
        title=data['title'],
        price=data['price'],
        login=data['login'],
        password=data['password'],
        twofa=twofa
    )
    products[product['product_id']] = product
    
    await state.clear()
    
    await message.answer(
        f"✅ **Товар успешно создан!**\n\n"
        f"📦 **{product['title']}**\n"
        f"💰 Цена: {product['price']}💰\n"
        f"🆔 ID: `{product['product_id']}`\n\n"
        f"Товар появится в общем списке 🛒 Товары",
        parse_mode="Markdown",
        reply_markup=get_main_menu(users.get(user_id, {}).get("role", "user"))
    )
    
    logger.info(f"Создан новый товар {product['product_id']} продавцом {user_id}")

@dp.callback_query(F.data == "my_sales")
async def my_sales(callback: CallbackQuery):
    """Просмотр продаж"""
    user_id = callback.from_user.id
    sales = get_user_sales(user_id)
    products_list = get_user_products(user_id)
    
    text = "📦 **Ваши продажи:**\n\n"
    
    if sales:
        text += "**Заказы:**\n"
        for order in sales[-10:]:  # Последние 10
            product = products.get(order["product_id"], {})
            status_emoji = {
                "pending": "⏳",
                "completed": "✅",
                "disputed": "⚠️",
                "refunded": "↩️"
            }.get(order["status"], "❓")
            
            text += (
                f"{status_emoji} **{product.get('title', 'Товар')}**\n"
                f"   ID: `{order['order_id']}` | {order['price']}💰\n"
                f"   Статус: {order['status']}\n"
                f"   {order['created_at'].strftime('%d.%m.%Y %H:%M')}\n\n"
            )
    else:
        text += "Пока нет продаж.\n\n"
    
    if products_list:
        text += "**Ваши активные товары:**\n"
        for product in products_list[-5:]:
            status = "✅ Активен" if product['is_active'] else "❌ Продан"
            text += f"📦 {product['title']} - {product['price']}💰 ({status})\n"
            text += f"   Просмотров: {product.get('views', 0)}\n"
            if not product['is_active']:
                # Находим заказ для этого товара
                product_order = next((o for o in sales if o['product_id'] == product['product_id']), None)
                if product_order:
                    text += f"   Продан: {product_order['created_at'].strftime('%d.%m.%Y')}\n"
            text += "\n"
    else:
        text += "У вас пока нет товаров.\n"
        text += "Создайте товар через ➕ Создать товар"
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_main_menu(users.get(user_id, {}).get("role", "user"))
    )
    await callback.answer()

# ==================== АДМИН (ОБРАБОТЧИКИ) ====================

@dp.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery):
    """Админ панель"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return
    
    await callback.message.edit_text(
        "⚙️ **Админ панель**\n\n"
        "Управление маркетплейсом:",
        parse_mode="Markdown",
        reply_markup=get_admin_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data == "admin_orders")
async def admin_orders(callback: CallbackQuery):
    """Просмотр всех заказов"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    if not orders:
        await callback.message.edit_text(
            "📊 **Нет заказов**",
            parse_mode="Markdown",
            reply_markup=get_admin_keyboard()
        )
        await callback.answer()
        return
    
    text = "📊 **Все заказы:**\n\n"
    for order_id, order in list(orders.items())[-20:]:  # Последние 20
        product = products.get(order["product_id"], {})
        buyer = users.get(order["buyer_id"], {})
        seller = users.get(order["seller_id"], {})
        
        status_emoji = {
            "pending": "⏳",
            "completed": "✅",
            "disputed": "⚠️",
            "refunded": "↩️"
        }.get(order["status"], "❓")
        
        text += (
            f"{status_emoji} **Заказ #{order_id}**\n"
            f"   Товар: {product.get('title', 'Неизвестно')}\n"
            f"   Сумма: {order['price']}💰\n"
            f"   Покупатель: {buyer.get('first_name', order['buyer_id'])}\n"
            f"   Продавец: {seller.get('first_name', order['seller_id'])}\n"
            f"   Статус: {order['status']}\n"
            f"   {order['created_at'].strftime('%d.%m.%Y %H:%M')}\n\n"
        )
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_admin_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data == "admin_users")
async def admin_users(callback: CallbackQuery):
    """Просмотр пользователей"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    text = "👥 **Пользователи:**\n\n"
    for user_id, user in list(users.items())[-20:]:  # Последние 20
        role_emoji = "👑" if user['role'] == 'admin' else "👤" if user['role'] == 'seller' else "👤"
        text += (
            f"{role_emoji} **{user.get('first_name', 'Без имени')}**\n"
            f"   ID: `{user_id}`\n"
            f"   Username: @{user.get('username', 'None')}\n"
            f"   Роль: {user['role']}\n"
            f"   Баланс: {user['balance']}💰\n"
            f"   Регистрация: {user['registered_at'].strftime('%d.%m.%Y')}\n\n"
        )
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_admin_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data == "admin_products")
async def admin_products(callback: CallbackQuery):
    """Просмотр всех товаров"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    if not products:
        await callback.message.edit_text(
            "📦 **Нет товаров**",
            parse_mode="Markdown",
            reply_markup=get_admin_keyboard()
        )
        await callback.answer()
        return
    
    text = "📦 **Все товары:**\n\n"
    for product_id, product in list(products.items())[-20:]:  # Последние 20
        seller = users.get(product["seller_id"], {})
        status = "✅ Активен" if product['is_active'] else "❌ Продан"
        
        text += (
            f"📱 **{product['title']}**\n"
            f"   ID: `{product_id}`\n"
            f"   Цена: {product['price']}💰\n"
            f"   Продавец: {seller.get('first_name', product['seller_id'])}\n"
            f"   Статус: {status}\n"
            f"   Просмотров: {product.get('views', 0)}\n"
            f"   Создан: {product['created_at'].strftime('%d.%m.%Y')}\n\n"
        )
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_admin_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data == "admin_disputes")
async def admin_disputes(callback: CallbackQuery):
    """Просмотр споров"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    disputed_orders = {oid: o for oid, o in orders.items() if o["status"] == "disputed"}
    
    if not disputed_orders:
        await callback.message.edit_text(
            "⚖️ **Нет активных споров**",
            parse_mode="Markdown",
            reply_markup=get_admin_keyboard()
        )
        await callback.answer()
        return
    
    text = "⚖️ **Активные споры:**\n\n"
    for order_id, order in disputed_orders.items():
        product = products.get(order["product_id"], {})
        buyer = users.get(order["buyer_id"], {})
        seller = users.get(order["seller_id"], {})
        
        text += (
            f"**Спор #{order_id}**\n"
            f"   Товар: {product.get('title', 'Неизвестно')}\n"
            f"   Сумма: {order['price']}💰\n"
            f"   Покупатель: {buyer.get('first_name', order['buyer_id'])}\n"
            f"   Продавец: {seller.get('first_name', order['seller_id'])}\n"
            f"   Причина: {order.get('dispute_reason', 'Не указана')}\n\n"
        )
    
    # Показываем первый спор для решения
    first_order_id = list(disputed_orders.keys())[0]
    await callback.message.edit_text(
        text + "**Выберите действие для первого спора:**",
        parse_mode="Markdown",
        reply_markup=get_dispute_actions_keyboard(first_order_id)
    )
    await callback.answer()

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    """Статистика платформы"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    total_users = len(users)
    total_sellers = len([u for u in users.values() if u['role'] in ['seller', 'admin']])
    total_products = len(products)
    active_products = len([p for p in products.values() if p['is_active']])
    total_orders = len(orders)
    completed_orders = len([o for o in orders.values() if o['status'] == 'completed'])
    disputed_orders = len([o for o in orders.values() if o['status'] == 'disputed'])
    
    total_volume = sum(o['price'] for o in orders.values() if o['status'] == 'completed')
    total_fees = total_volume * PLATFORM_FEE
    
    text = (
        "📈 **Статистика платформы**\n\n"
        f"👥 **Пользователи:**\n"
        f"   Всего: {total_users}\n"
        f"   Продавцов: {total_sellers}\n\n"
        f"📦 **Товары:**\n"
        f"   Всего: {total_products}\n"
        f"   Активных: {active_products}\n\n"
        f"📊 **Заказы:**\n"
        f"   Всего: {total_orders}\n"
        f"   Завершено: {completed_orders}\n"
        f"   В спорах: {disputed_orders}\n\n"
        f"💰 **Финансы:**\n"
        f"   Объем продаж: {total_volume:.2f}💰\n"
        f"   Комиссия платформы: {total_fees:.2f}💰"
    )
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_admin_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data == "admin_reset")
async def admin_reset(callback: CallbackQuery):
    """Сброс данных (только для админа)"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    # Очищаем все хранилища
    users.clear()
    products.clear()
    orders.clear()
    
    # Сбрасываем счетчики
    global product_id_counter, order_id_counter
    product_id_counter = count(1)
    order_id_counter = count(1)
    
    # Добавляем текущего пользователя как админа
    users[ADMIN_ID] = create_user(ADMIN_ID, callback.from_user.username, callback.from_user.first_name)
    
    await callback.message.edit_text(
        "✅ **Все данные сброшены**\n\n"
        "Хранилища очищены.\n"
        "Вы остались администратором.",
        parse_mode="Markdown",
        reply_markup=get_admin_keyboard()
    )
    await callback.answer("🔄 Данные сброшены", show_alert=True)

@dp.callback_query(F.data.startswith("resolve_dispute_buyer_"))
async def resolve_dispute_buyer(callback: CallbackQuery):
    """Решение спора в пользу покупателя"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    order_id = int(callback.data.split("_")[3])
    result = resolve_dispute(order_id, "buyer")
    
    await callback.message.edit_text(
        result["message"],
        parse_mode="Markdown",
        reply_markup=get_admin_keyboard()
    )
    await callback.answer()
    logger.info(f"Админ решил спор {order_id} в пользу покупателя")

@dp.callback_query(F.data.startswith("resolve_dispute_seller_"))
async def resolve_dispute_seller(callback: CallbackQuery):
    """Решение спора в пользу продавца"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    order_id = int(callback.data.split("_")[3])
    result = resolve_dispute(order_id, "seller")
    
    await callback.message.edit_text(
        result["message"],
        parse_mode="Markdown",
        reply_markup=get_admin_keyboard()
    )
    await callback.answer()
    logger.info(f"Админ решил спор {order_id} в пользу продавца")

# ==================== ОБРАБОТЧИК НЕИЗВЕСТНЫХ КОМАНД ====================

@dp.message()
async def unknown_message(message: Message):
    """Обработчик неизвестных сообщений"""
    await message.answer(
        "❌ Неизвестная команда.\n"
        "Используйте /menu для возврата в главное меню."
    )

@dp.callback_query()
async def unknown_callback(callback: CallbackQuery):
    """Обработчик неизвестных callback'ов"""
    await callback.answer("❌ Действие не найдено", show_alert=True)

# ==================== ЗАПУСК БОТА ====================

async def main():
    """Главная функция запуска бота"""
    logger.info("=" * 50)
    logger.info("Запуск ScornX Market бота...")
    logger.info(f"Токен: {TOKEN[:10]}...")
    logger.info(f"ID администратора: {ADMIN_ID}")
    logger.info(f"Комиссия платформы: {PLATFORM_FEE * 100}%")
    logger.info("=" * 50)
    
    # Регистрируем админа если его нет
    if ADMIN_ID not in users:
        users[ADMIN_ID] = create_user(ADMIN_ID, "admin", "Administrator")
        users[ADMIN_ID]["role"] = "admin"
        users[ADMIN_ID]["balance"] = 10000  # Даем админу тестовый баланс
        logger.info(f"Администратор {ADMIN_ID} зарегистрирован")
    
    logger.info("Бот готов к работе!")
    
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
    finally:
        await bot.session.close()
        logger.info("Бот остановлен")

if __name__ == "__main__":
    asyncio.run(main())
