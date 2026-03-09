"""
Клавиатуры для бота
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List, Dict

def get_main_menu(role: str = "user") -> InlineKeyboardMarkup:
    """Главное меню"""
    builder = InlineKeyboardBuilder()
    
    # Основные кнопки
    builder.row(
        InlineKeyboardButton(text="🛒 Товары", callback_data="products"),
        InlineKeyboardButton(text="💰 Баланс", callback_data="balance")
    )
    builder.row(
        InlineKeyboardButton(text="🛍 Мои покупки", callback_data="my_purchases"),
        InlineKeyboardButton(text="⭐ Звёзды", callback_data="stars_info")
    )
    builder.row(
        InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
        InlineKeyboardButton(text="📞 Поддержка", callback_data="support")
    )
    
    # Для продавцов
    if role in ["seller", "admin"]:
        builder.row(
            InlineKeyboardButton(text="📦 Мои продажи", callback_data="my_sales"),
            InlineKeyboardButton(text="➕ Создать товар", callback_data="create_product")
        )
    
    # Стать продавцом
    if role == "user":
        builder.row(InlineKeyboardButton(text="👑 Стать продавцом", callback_data="become_seller"))
    
    # Админ панель
    if role == "admin":
        builder.row(InlineKeyboardButton(text="⚙️ Админ панель", callback_data="admin_panel"))
    
    return builder.as_markup()

def get_products_keyboard(products: List[Dict], page: int = 0, user_id: int = None) -> InlineKeyboardMarkup:
    """Клавиатура со списком товаров"""
    builder = InlineKeyboardBuilder()
    
    if not products:
        builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"))
        return builder.as_markup()
    
    items_per_page = 5
    start = page * items_per_page
    end = min(start + items_per_page, len(products))
    
    for product in products[start:end]:
        title = product['title'][:20] + "..." if len(product['title']) > 20 else product['title']
        builder.row(InlineKeyboardButton(
            text=f"📱 {title} - {product['price']}💰",
            callback_data=f"view_product_{product['product_id']}"
        ))
    
    # Навигация
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"products_page_{page-1}"))
    if end < len(products):
        nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"products_page_{page+1}"))
    
    if nav_buttons:
        builder.row(*nav_buttons)
    
    builder.row(
        InlineKeyboardButton(text="🔄 Обновить", callback_data="products"),
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
    )
    
    return builder.as_markup()

def get_product_actions_keyboard(product_id: int, seller_id: int, user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура действий с товаром"""
    builder = InlineKeyboardBuilder()
    
    # Кнопка покупки (только если это не свой товар)
    if seller_id != user_id:
        builder.row(
            InlineKeyboardButton(text="💳 Купить за баланс", callback_data=f"buy_balance_{product_id}"),
            InlineKeyboardButton(text="⭐ Купить за звёзды", callback_data=f"buy_stars_{product_id}")
        )
    
    builder.row(
        InlineKeyboardButton(text="◀️ Назад к товарам", callback_data="products"),
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
    )
    
    return builder.as_markup()

def get_order_actions_keyboard(order_id: int, status: str, role: str = "user") -> InlineKeyboardMarkup:
    """Клавиатура действий с заказом"""
    builder = InlineKeyboardBuilder()
    
    if status == "pending":
        builder.row(
            InlineKeyboardButton(text="✅ Подтвердить получение", callback_data=f"confirm_order_{order_id}"),
            InlineKeyboardButton(text="⚠️ Открыть спор", callback_data=f"dispute_order_{order_id}")
        )
    elif status == "disputed" and role == "admin":
        builder.row(
            InlineKeyboardButton(text="⚖️ Рассмотреть спор", callback_data=f"admin_disputes")
        )
    
    if status == "completed":
        builder.row(
            InlineKeyboardButton(text="⭐ Оставить отзыв", callback_data=f"review_order_{order_id}")
        )
    
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="my_purchases"),
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
    )
    
    return builder.as_markup()

def get_balance_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для баланса"""
    builder = InlineKeyboardBuilder()
    
    # Кнопки пополнения баланса
    builder.row(
        InlineKeyboardButton(text="💳 100💰", callback_data="add_balance_100"),
        InlineKeyboardButton(text="💳 500💰", callback_data="add_balance_500"),
        InlineKeyboardButton(text="💳 1000💰", callback_data="add_balance_1000")
    )
    builder.row(
        InlineKeyboardButton(text="💳 5000💰", callback_data="add_balance_5000"),
        InlineKeyboardButton(text="💳 10000💰", callback_data="add_balance_10000")
    )
    
    # Информация о звёздах
    builder.row(InlineKeyboardButton(text="⭐ Информация о звёздах", callback_data="stars_info"))
    
    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"))
    
    return builder.as_markup()

def get_admin_keyboard() -> InlineKeyboardMarkup:
    """Админская клавиатура"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
        InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")
    )
    builder.row(
        InlineKeyboardButton(text="📦 Товары", callback_data="admin_products"),
        InlineKeyboardButton(text="📋 Заказы", callback_data="admin_orders")
    )
    builder.row(
        InlineKeyboardButton(text="⚖️ Споры", callback_data="admin_disputes"),
        InlineKeyboardButton(text="💳 Выплаты", callback_data="admin_payouts")
    )
    builder.row(
        InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast"),
        InlineKeyboardButton(text="⚙️ Настройки", callback_data="admin_settings")
    )
    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"))
    
    return builder.as_markup()

def get_dispute_actions_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для решения спора"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="✅ В пользу покупателя", callback_data=f"resolve_dispute_buyer_{order_id}"),
        InlineKeyboardButton(text="✅ В пользу продавца", callback_data=f"resolve_dispute_seller_{order_id}")
    )
    builder.row(
        InlineKeyboardButton(text="💰 Разделить 50/50", callback_data=f"resolve_dispute_split_{order_id}")
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_disputes"))
    
    return builder.as_markup()

def get_confirmation_keyboard(action: str, item_id: int) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="✅ Да", callback_data=f"confirm_{action}_{item_id}"),
        InlineKeyboardButton(text="❌ Нет", callback_data=f"cancel_{action}_{item_id}")
    )
    
    return builder.as_markup()
