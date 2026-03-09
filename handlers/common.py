"""
Общие обработчики
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext

from database import db
from keyboards import get_main_menu
from config import ADMIN_IDS
import logging

router = Router()
logger = logging.getLogger(__name__)

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    
    # Очищаем состояние
    await state.clear()
    
    # Регистрируем пользователя
    await db.add_user(user_id, username, first_name, last_name)
    
    # Проверяем, является ли пользователь админом
    if user_id in ADMIN_IDS:
        await db.update_user_role(user_id, "admin")
    
    # Получаем данные пользователя
    user = await db.get_user(user_id)
    role = user['role'] if user else "user"
    
    # Приветственное сообщение
    welcome_text = (
        f"👋 Добро пожаловать в <b>ScornX Market</b>, {first_name}!\n\n"
        f"✅ Вы успешно зарегистрированы.\n"
        f"💰 Баланс: {user['balance']}💰\n"
        f"⭐ Звёзды: {user['stars_balance']}\n\n"
        f"Используйте меню для навигации:"
    )
    
    await message.answer(welcome_text, reply_markup=get_main_menu(role))
    
    # Обновляем активность
    await db.update_user_activity(user_id)

@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext):
    """Команда для возврата в меню"""
    await state.clear()
    user_id = message.from_user.id
    
    user = await db.get_user(user_id)
    if not user:
        await cmd_start(message, state)
        return
    
    await message.answer(
        "📱 <b>Главное меню</b>",
        reply_markup=get_main
