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
async def save_user(user_id, language="uz"):
    cursor.execute(
        """
        INSERT OR IGNORE INTO users(user_id, language, joined_date)
        VALUES(?,?,?)
        """,
        (
            user_id,
            language,
            datetime.now().strftime("%Y-%m-%d")
        )
    )
    db.commit()


async def get_language(user_id):
    cursor.execute(
        "SELECT language FROM users WHERE user_id=?",
        (user_id,)
    )

    result = cursor.fetchone()

    if result:
        return result[0]

    return "uz"


async def set_language(user_id, language):
    cursor.execute(
        "UPDATE users SET language=? WHERE user_id=?",
        (language, user_id)
    )
    db.commit()