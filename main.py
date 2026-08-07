import asyncio
import sqlite3
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

from config import BOT_TOKEN, ADMINS


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


db = sqlite3.connect("bot.db", check_same_thread=False)
cursor = db.cursor()


cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY,
    language TEXT DEFAULT 'uz',
    joined_date TEXT,
    project_clicks INTEGER DEFAULT 0
)
""")


cursor.execute("""
CREATE TABLE IF NOT EXISTS projects(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    url TEXT
)
""")


db.commit()


admin_state = {}


language_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🇺🇿 O'zbek"),
            KeyboardButton(text="🇷🇺 Русский")
        ]
    ],
    resize_keyboard=True
)


uz_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📌 Loyihalar")]
    ],
    resize_keyboard=True
)


ru_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📌 Проекты")]
    ],
    resize_keyboard=True
)


admin_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="➕ Loyiha qo'shish"),
            KeyboardButton(text="📊 Statistika")
        ]
    ],
    resize_keyboard=True
)


async def save_user(user_id):

    cursor.execute(
        """
        INSERT OR IGNORE INTO users(user_id, joined_date)
        VALUES(?,?)
        """,
        (
            user_id,
            datetime.now().strftime("%Y-%m-%d")
        )
    )

    db.commit()


async def set_language(user_id, lang):

    cursor.execute(
        """
        UPDATE users
        SET language=?
        WHERE user_id=?
        """,
        (lang, user_id)
    ) db.commit()@dp.message(Command("start"))
async def start(message: types.Message):

    await save_user(message.from_user.id)

    await message.answer(
        "Tilni tanlang:",
        reply_markup=language_keyboard
    )


@dp.message(lambda m: m.text == "🇺🇿 O'zbek")
async def uz(message: types.Message):

    await set_language(message.from_user.id, "uz")

    await message.answer(
        "📌 Loyihani tanlang:",
        reply_markup=uz_keyboard
    )


@dp.message(lambda m: m.text == "🇷🇺 Русский")
async def ru(message: types.Message):

    await set_language(message.from_user.id, "ru")

    await message.answer(
        "📌 Выберите проект:",
        reply_markup=ru_keyboard
    )


@dp.message(lambda m: m.text in ["📌 Loyihalar", "📌 Проекты"])
async def projects(message: types.Message):

    cursor.execute(
        "SELECT name,url FROM projects"
    )

    data = cursor.fetchall()

    if not data:
        await message.answer(
            "❌ Hozircha loyiha yo'q"
        )
        return

    for name, url in data:

        if url.startswith("http"):

            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🗳 Ovoz berish",
                            url=url
                        )
                    ]
                ]
            )

            await message.answer(
                f"📌 {name}",
                reply_markup=keyboard
            )

        else:
            await message.answer(
                f"📌 {name}\nHavola yo'q"
            )


@dp.message(Command("admin"))
async def admin(message: types.Message):

    if message.from_user.id in ADMINS:

        await message.answer(
            "Admin panel",
            reply_markup=admin_keyboard
        )

    else:
        await message.answer(
            "❌ Ruxsat yo'q"
        )


@dp.message(lambda m: m.text == "📊 Statistika")
async def stat(message: types.Message):

    if message.from_user.id not in ADMINS:
        return

    cursor.execute(
        "SELECT COUNT(*) FROM users"
    )

    users = cursor.fetchone()[0]

    await message.answer(
        f"📊 Statistika\n\n👥 Foydalanuvchilar: {users}"
    )


async def main():

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())