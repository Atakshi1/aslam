"""
ScornX Market - Telegram бот с escrow-механикой
MVP версия с in-memory хранением данных
Один файл для простоты запуска
"""

import logging
from datetime import datetime
from itertools import count
from typing import Dict, Any, Optional

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ==================== КОНФИГУРАЦИЯ ====================

TOKEN = "8445773141:AAGs7BvSnz3PPKHOHMtlLy9OF0NysloXSws"
ADMIN_ID = 123456789  # ⚠️ ЗАМЕНИТЕ НА СВОЙ TELEGRAM ID
PLATFORM_FEE = 0.05  # Комиссия платформы 5%

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== ХРАНИЛИЩЕ ДАННЫХ ====================

# In-memory хранилища
users: Dict[int, Dict[str, Any]] = {}  # user_id -> данные пользователя
products: Dict[int, Dict[str, Any]] = {}  # product_id -> товар
orders: Dict[int, Dict[str, Any]] = {}  # order_id -> заказ

# Генераторы ID
product_id_counter = count(1)
order_id_counter = count(1)

def create_user(user_id: int, username: str = None) -> Dict[str, Any]:
    """Создание нового пользователя"""
    return {
        "user_id": user_id,
        "username": username,
        "role": "admin" if user_id == ADMIN_ID else "user",  # Автоматически админ, если ID совпадает
        "balance": 0.0,
        "registered_at": datetime.now(),
        "is_active": True
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
        "created_at": datetime.now()
    }

def create_order(buyer_id: int, seller_id: int, product_id: int, price: float) -> Dict[str, Any]:
    """Создание нового заказа"""
    return {
        "order_id": next(order_id_counter),
        "buyer_id": buyer_id,
        "seller_id": seller_id,
        "product_id": product_id,
        "price": price,
        "status": "pending",  # pending, delivered, completed, disputed
        "created_at": datetime.now(),
        "completed_at": None
    }

# ==================== КЛАВИАТУРЫ ====================

def get_main_menu(role: str = "user") -> InlineKeyboardMarkup:
    """Главное меню"""
    builder = InlineKeyboardBuilder()
    
    builder.row(InlineKeyboardButton(text="🛒 Товары", callback_data="products"))
    builder.row(InlineKeyboardButton(text="💰 Баланс", callback_data="balance"))
    builder.row(InlineKeyboardButton(text="🛍 Мои покупки", callback_data="my_purchases"))
    
    if role == "user":
        builder.row(InlineKeyboardButton(text="👑 Стать продавцом", callback_data="become_seller"))
    
    if role in ["seller", "admin"]:
        builder.row(InlineKeyboardButton(text="📦 Мои продажи", callback_data="my_sales"))
        builder.row(InlineKeyboardButton(text="➕ Создать товар", callback_data="create_product"))
    
    if role == "admin":
        builder.row(InlineKeyboardButton(text="⚙️ Админ панель", callback_data="admin_panel"))
    
    return builder.as_markup()

def get_products_keyboard(products_list: list, page: int = 0) -> InlineKeyboardMarkup:
    """Клавиатура со списком товаров"""
    builder = InlineKeyboardBuilder()
    
    for product in products_list[page*5:(page+1)*5]:
        builder.row(InlineKeyboardButton(
            text=f"{product['title']} - {product['price']}💰",
            callback_data=f"view_product_{product['product_id']}"
        ))
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"products_page_{page-1}"))
    if len(products_list) > (page+1)*5:
        nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"products_page_{page+1}"))
    
    if nav_buttons:
        builder.row(*nav_buttons)
    
    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"))
    
    return builder.as_markup()

def get_product_actions_keyboard(product_id: int) -> InlineKeyboardMarkup:
    """Клавиатура действий с товаром"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💳 Купить", callback_data=f"buy_{product_id}"))
    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"))
    return builder.as_markup()

def get_order_actions_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Клавиатура действий с заказом"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_order_{order_id}"),
        InlineKeyboardButton(text="⚠️ Открыть спор", callback_data=f"dispute_order_{order_id}")
    )
    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"))
    return builder.as_markup()

def get_admin_keyboard() -> InlineKeyboardMarkup:
    """Админская клавиатура"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📊 Все заказы", callback_data="admin_orders"))
    builder.row(InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users"))
    builder.row(InlineKeyboardButton(text="⚖️ Споры", callback_data="admin_disputes"))
    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"))
    return builder.as_markup()

def get_dispute_actions_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для решения спора"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ В пользу покупателя", callback_data=f"resolve_dispute_buyer_{order_id}"),
        InlineKeyboardButton(text="✅ В пользу продавца", callback_data=f"resolve_dispute_seller_{order_id}")
    )
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

def process_purchase(buyer_id: int, product_id: int) -> dict:
    """Обработка покупки"""
    product = products.get(product_id)
    if not product:
        return {"success": False, "message": "Товар не найден"}
    
    if not product.get("is_active", False):
        return {"success": False, "message": "Товар неактивен"}
    
    if not check_balance(buyer_id, product["price"]):
        return {"success": False, "message": "Недостаточно средств"}
    
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
    
    logger.info(f"Создан заказ {order['order_id']} на товар {product_id}")
    return {"success": True, "order": order}

def confirm_order(order_id: int) -> dict:
    """Подтверждение получения товара"""
    order = orders.get(order_id)
    if not order:
        return {"success": False, "message": "Заказ не найден"}
    
    if order["status"] != "pending":
        return {"success": False, "message": f"Заказ уже имеет статус {order['status']}"}
    
    # Расчет комиссии
    seller_amount = order["price"] * (1 - PLATFORM_FEE)
    
    # Начисление продавцу
    if order["seller_id"] in users:
        users[order["seller_id"]]["balance"] += seller_amount
    
    order["status"] = "completed"
    order["completed_at"] = datetime.now()
    
    logger.info(f"Заказ {order_id} завершен, продавец получил {seller_amount}")
    return {"success": True, "message": f"Заказ завершен. Продавец получил {seller_amount}💰"}

def dispute_order(order_id: int) -> dict:
    """Открытие спора"""
    order = orders.get(order_id)
    if not order:
        return {"success": False, "message": "Заказ не найден"}
    
    if order["status"] != "pending":
        return {"success": False, "message": f"Нельзя открыть спор для заказа со статусом {order['status']}"}
    
    order["status"] = "disputed"
    logger.info(f"Открыт спор по заказу {order_id}")
    return {"success": True, "message": "Спор открыт. Ожидайте решения администратора."}

def resolve_dispute(order_id: int, in_favor_of: str) -> dict:
    """Решение спора администратором"""
    order = orders.get(order_id)
    if not order:
        return {"success": False, "message": "Заказ не найден"}
    
    if order["status"] != "disputed":
        return {"success": False, "message": "Заказ не в статусе спора"}
    
    if in_favor_of == "buyer":
        # Возврат средств покупателю
        users[order["buyer_id"]]["balance"] += order["price"]
        order["status"] = "completed"
        message = "Спор решен в пользу покупателя. Средства возвращены."
    elif in_favor_of == "seller":
        # Начисление продавцу
        seller_amount = order["price"] * (1 - PLATFORM_FEE)
        users[order["seller_id"]]["balance"] += seller_amount
        order["status"] = "completed"
        message = f"Спор решен в пользу продавца. Продавец получил {seller_amount}💰"
    else:
        return {"success": False, "message": "Некорректное решение"}
    
    order["completed_at"] = datetime.now()
    logger.info(f"Спор по заказу {order_id} решен в пользу {in_favor_of}")
    return {"success": True, "message": message}

def get_user_products(user_id: int) -> list:
    """Получение товаров пользователя (как продавца)"""
    return [p for p in products.values() if p["seller_id"] == user_id]

def get_user_purchases(user_id: int) -> list:
    """Получение покупок пользователя"""
    return [o for o in orders.values() if o["buyer_id"] == user_id]

def get_user_sales(user_id: int) -> list:
    """Получение продаж пользователя"""
    return [o for o in orders.values() if o["seller_id"] == user_id]

# ==================== СОСТОЯНИЯ FSM ====================

class ProductCreation(StatesGroup):
    """Состояния создания товара"""
    title = State()
    price = State()
    login = State()
    password = State()
    twofa = State()

# ==================== ИНИЦИАЛИЗАЦИЯ БОТА ====================

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ==================== ОБЩИЕ ОБРАБОТЧИКИ ====================

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    username = message.from_user.username
    
    # Очищаем состояние
    await state.clear()
    
    # Регистрация пользователя
    if user_id not in users:
        users[user_id] = create_user(user_id, username)
        logger.info(f"Новый пользователь: {user_id}")
        await message.answer("✅ Добро пожаловать в ScornX Market! Вы успешно зарегистрированы.")
    else:
        await message.answer("👋 С возвращением в ScornX Market!")
    
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
    role = users.get(user_id, {}).get("role", "user")
    await message.answer(
        "📱 Главное меню",
        reply_markup=get_main_menu(role)
    )

@dp.callback_query(F.data == "main_menu")
async def main_menu_callback(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    await state.clear()
    user_id = callback.from_user.id
    role = users.get(user_id, {}).get("role", "user")
    await callback.message.edit_text(
        "📱 Главное меню",
        reply_markup=get_main_menu(role)
    )
    await callback.answer()

# ==================== ПОЛЬЗОВАТЕЛЬСКИЕ ОБРАБОТЧИКИ ====================

@dp.callback_query(F.data == "balance")
async def show_balance(callback: CallbackQuery):
    """Показать баланс"""
    user_id = callback.from_user.id
    balance = users.get(user_id, {}).get("balance", 0)
    
    # Кнопка пополнения (заглушка +100)
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💳 Пополнить (+100)", callback_data="add_balance"))
    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"))
    
    await callback.message.edit_text(
        f"💰 Ваш баланс: {balance}",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@dp.callback_query(F.data == "add_balance")
async def add_balance_callback(callback: CallbackQuery):
    """Пополнение баланса (заглушка)"""
    user_id = callback.from_user.id
    add_balance(user_id, 100)
    
    await callback.message.edit_text(
        f"✅ Баланс пополнен на 100💰\n"
        f"💰 Текущий баланс: {users[user_id]['balance']}",
        reply_markup=get_main_menu(users[user_id]['role'])
    )
    await callback.answer()

@dp.callback_query(F.data == "products")
async def show_products(callback: CallbackQuery):
    """Показать список товаров"""
    user_id = callback.from_user.id
    
    # Фильтруем активные товары, не принадлежащие пользователю
    available_products = [
        p for p in products.values() 
        if p["is_active"] and p["seller_id"] != user_id
    ]
    
    if not available_products:
        await callback.message.edit_text(
            "😕 Нет доступных товаров",
            reply_markup=get_main_menu(users.get(user_id, {}).get("role", "user"))
        )
        await callback.answer()
        return
    
    await callback.message.edit_text(
        "🛒 Доступные товары:",
        reply_markup=get_products_keyboard(available_products)
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("products_page_"))
async def products_page(callback: CallbackQuery):
    """Пагинация товаров"""
    user_id = callback.from_user.id
    page = int(callback.data.split("_")[2])
    
    available_products = [
        p for p in products.values() 
        if p["is_active"] and p["seller_id"] != user_id
    ]
    
    await callback.message.edit_text(
        "🛒 Доступные товары:",
        reply_markup=get_products_keyboard(available_products, page)
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("view_product_"))
async def view_product(callback: CallbackQuery):
    """Просмотр товара"""
    product_id = int(callback.data.split("_")[2])
    product = products.get(product_id)
    
    if not product:
        await callback.message.edit_text(
            "❌ Товар не найден",
            reply_markup=get_main_menu(users.get(callback.from_user.id, {}).get("role", "user"))
        )
        await callback.answer()
        return
    
    text = (
        f"📦 {product['title']}\n\n"
        f"💰 Цена: {product['price']}\n"
        f"👤 Продавец: {product['seller_id']}\n\n"
        "После покупки вы получите данные для входа."
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_product_actions_keyboard(product_id)
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
        product = products[product_id]
        
        # Показываем данные аккаунта
        data_text = (
            f"✅ Покупка совершена!\n\n"
            f"📋 Данные аккаунта:\n"
            f"🔑 Логин: {product['data']['login']}\n"
            f"🔐 Пароль: {product['data']['password']}\n"
        )
        if product['data'].get('2fa'):
            data_text += f"📱 2FA: {product['data']['2fa']}\n"
        
        data_text += f"\n📦 ID заказа: {order['order_id']}\n"
        data_text += "\n⚠️ После получения данных подтвердите получение или откройте спор."
        
        await callback.message.edit_text(
            data_text,
            reply_markup=get_order_actions_keyboard(order['order_id'])
        )
    else:
        await callback.message.edit_text(
            f"❌ {result['message']}",
            reply_markup=get_main_menu(users.get(user_id, {}).get("role", "user"))
        )
    
    await callback.answer()

@dp.callback_query(F.data.startswith("confirm_order_"))
async def confirm_order_callback(callback: CallbackQuery):
    """Подтверждение получения товара"""
    user_id = callback.from_user.id
    order_id = int(callback.data.split("_")[2])
    
    result = confirm_order(order_id)
    
    if result["success"]:
        text = f"✅ {result['message']}"
    else:
        text = f"❌ {result['message']}"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_main_menu(users.get(user_id, {}).get("role", "user"))
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("dispute_order_"))
async def dispute_order_callback(callback: CallbackQuery):
    """Открытие спора"""
    user_id = callback.from_user.id
    order_id = int(callback.data.split("_")[2])
    
    result = dispute_order(order_id)
    
    await callback.message.edit_text(
        result["message"],
        reply_markup=get_main_menu(users.get(user_id, {}).get("role", "user"))
    )
    await callback.answer()

@dp.callback_query(F.data == "my_purchases")
async def my_purchases(callback: CallbackQuery):
    """Просмотр покупок"""
    user_id = callback.from_user.id
    purchases = get_user_purchases(user_id)
    
    if not purchases:
        await callback.message.edit_text(
            "🛍 У вас пока нет покупок",
            reply_markup=get_main_menu(users.get(user_id, {}).get("role", "user"))
        )
        await callback.answer()
        return
    
    text = "🛍 Ваши покупки:\n\n"
    for order in purchases[-5:]:  # Последние 5
        product = products.get(order["product_id"], {})
        text += f"📦 {product.get('title', 'Товар')} - {order['price']}💰\n"
        text += f"Статус: {order['status']}\n"
        text += f"ID: {order['order_id']}\n\n"
    
    await callback.message.edit_text(
        text,
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
        "✅ Теперь вы продавец! Вы можете создавать товары.",
        reply_markup=get_main_menu("seller")
    )
    await callback.answer()

@dp.callback_query(F.data == "create_product")
async def create_product_start(callback: CallbackQuery, state: FSMContext):
    """Начало создания товара"""
    await state.set_state(ProductCreation.title)
    await callback.message.edit_text(
        "📝 Введите название товара:"
    )
    await callback.answer()

@dp.message(ProductCreation.title)
async def process_title(message: Message, state: FSMContext):
    """Обработка названия товара"""
    await state.update_data(title=message.text)
    await state.set_state(ProductCreation.price)
    await message.answer("💰 Введите цену товара (только число):")

@dp.message(ProductCreation.price)
async def process_price(message: Message, state: FSMContext):
    """Обработка цены"""
    try:
        price = float(message.text)
        if price <= 0:
            await message.answer("❌ Цена должна быть положительным числом. Попробуйте снова:")
            return
        
        await state.update_data(price=price)
        await state.set_state(ProductCreation.login)
        await message.answer("🔑 Введите логин от аккаунта Telegram:")
    except ValueError:
        await message.answer("❌ Пожалуйста, введите число. Попробуйте снова:")

@dp.message(ProductCreation.login)
async def process_login(message: Message, state: FSMContext):
    """Обработка логина"""
    await state.update_data(login=message.text)
    await state.set_state(ProductCreation.password)
    await message.answer("🔐 Введите пароль от аккаунта:")

@dp.message(ProductCreation.password)
async def process_password(message: Message, state: FSMContext):
    """Обработка пароля"""
    await state.update_data(password=message.text)
    await state.set_state(ProductCreation.twofa)
    await message.answer(
        "📱 Введите 2FA код (если есть) или отправьте '-' если нет 2FA:"
    )

@dp.message(ProductCreation.twofa)
async def process_twofa(message: Message, state: FSMContext):
    """Обработка 2FA и сохранение товара"""
    user_id = message.from_user.id
    twofa = message.text if message.text != '-' else None
    
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
        f"✅ Товар успешно создан!\n\n"
        f"📦 {product['title']}\n"
        f"💰 Цена: {product['price']}\n"
        f"🆔 ID: {product['product_id']}",
        reply_markup=get_main_menu(users.get(user_id, {}).get("role", "user"))
    )
    
    logger.info(f"Создан новый товар {product['product_id']} продавцом {user_id}")

@dp.callback_query(F.data == "my_sales")
async def my_sales(callback: CallbackQuery):
    """Просмотр продаж"""
    user_id = callback.from_user.id
    sales = get_user_sales(user_id)
    products_list = get_user_products(user_id)
    
    text = "📦 Ваши продажи:\n\n"
    
    if sales:
        text += "Заказы:\n"
        for order in sales[-5:]:  # Последние 5
            product = products.get(order["product_id"], {})
            text += f"📦 {product.get('title', 'Товар')} - {order['price']}💰\n"
            text += f"Статус: {order['status']}\n"
            text += f"ID: {order['order_id']}\n\n"
    else:
        text += "Пока нет продаж.\n\n"
    
    if products_list:
        text += "Ваши активные товары:\n"
        for product in products_list[-5:]:
            status = "✅ Активен" if product['is_active'] else "❌ Продан"
            text += f"📦 {product['title']} - {product['price']}💰 ({status})\n"
    else:
        text += "У вас пока нет товаров."
    
    await callback.message.edit_text(
        text,
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
        "⚙️ Админ панель",
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
            "📊 Нет заказов",
            reply_markup=get_admin_keyboard()
        )
        await callback.answer()
        return
    
    text = "📊 Все заказы:\n\n"
    for order_id, order in list(orders.items())[-10:]:  # Последние 10
        product = products.get(order["product_id"], {})
        text += f"ID: {order_id}\n"
        text += f"Товар: {product.get('title', 'Неизвестно')}\n"
        text += f"Цена: {order['price']}💰\n"
        text += f"Статус: {order['status']}\n"
        text += f"Покупатель: {order['buyer_id']}\n"
        text += f"Продавец: {order['seller_id']}\n"
        text += "-" * 20 + "\n"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_admin_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data == "admin_users")
async def admin_users(callback: CallbackQuery):
    """Просмотр пользователей"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    text = "👥 Пользователи:\n\n"
    for user_id, user in list(users.items())[-10:]:  # Последние 10
        text += f"ID: {user_id}\n"
        text += f"Username: @{user.get('username', 'None')}\n"
        text += f"Роль: {user['role']}\n"
        text += f"Баланс: {user['balance']}💰\n"
        text += "-" * 20 + "\n"
    
    await callback.message.edit_text(
        text,
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
            "⚖️ Нет активных споров",
            reply_markup=get_admin_keyboard()
        )
        await callback.answer()
        return
    
    text = "⚖️ Активные споры:\n\n"
    for order_id, order in disputed_orders.items():
        product = products.get(order["product_id"], {})
        text += f"Спор #{order_id}\n"
        text += f"Товар: {product.get('title', 'Неизвестно')}\n"
        text += f"Сумма: {order['price']}💰\n"
        text += f"Покупатель: {order['buyer_id']}\n"
        text += f"Продавец: {order['seller_id']}\n\n"
    
    # Показываем первый спор для решения
    first_order_id = list(disputed_orders.keys())[0]
    await callback.message.edit_text(
        text + "Выберите действие для первого спора:",
        reply_markup=get_dispute_actions_keyboard(first_order_id)
    )
    await callback.answer()

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
        reply_markup=get_admin_keyboard()
    )
    await callback.answer()
    logger.info(f"Админ решил спор {order_id} в пользу продавца")

# ==================== ЗАПУСК БОТА ====================

async def main():
    """Главная функция запуска бота"""
    logger.info("Запуск ScornX Market бота...")
    
    # Создаем тестовые данные для демонстрации
    if not products:
        # Добавляем тестового продавца
        test_seller_id = 987654321
        if test_seller_id not in users:
            users[test_seller_id] = create_user(test_seller_id, "test_seller")
            users[test_seller_id]["role"] = "seller"
        
        # Создаем тестовые товары
        test_products = [
            create_product(test_seller_id, "Telegram Premium аккаунт", 50.0, "premium_user", "pass123", None),
            create_product(test_seller_id, "Старый аккаунт 2015", 25.0, "old_account", "oldpass456", "123456"),
            create_product(test_seller_id, "Аккаунт с историей", 75.0, "history_acc", "hist789", None),
        ]
        
        for p in test_products:
            products[p["product_id"]] = p
        
        logger.info(f"Добавлено {len(test_products)} тестовых товаров")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
