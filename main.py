import asyncio
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

from config import BOT_TOKEN, ADMINS
from database import cursor, db
from texts import TEXTS
from keyboards import (
    language_keyboard,
    user_keyboard_uz,
    user_keyboard_ru,
    admin_keyboard
)


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


admin_state = {}