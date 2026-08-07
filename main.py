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

TOKEN = "8615736731:AAFImAWTDRhBJAyOhXbY6D0wwysIa0Boz1c"

ADMINS = [
    7998053914,
    1599812727
]


bot = Bot(token=TOKEN)
dp = Dispatcher()


db = sqlite3.connect("bot.db", check_same_thread=False)
cursor = db.cursor()


cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY,
    language TEXT DEFAULT 'uz',
    date TEXT
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


state = {}


lang_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🇺🇿 O'zbek"),
            KeyboardButton(text="🇷🇺 Русский")
        ]
    ],
    resize_keyboard=True
)


uz_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="📌 Loyihalar")
        ]
    ],
    resize_keyboard=True
)


ru_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="📌 Проекты")
        ]
    ],
    resize_keyboard=True
)


admin_menu = ReplyKeyboardMarkup(
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
        "INSERT OR IGNORE INTO users VALUES(?,?,?)",
        (
            user_id,
            "uz",
            datetime.now().strftime("%Y-%m-%d")
        )
    )

    db.commit()


async def set_lang(user_id, lang):

    cursor.execute(
        "UPDATE users SET language=? WHERE user_id=?",
        (lang, user_id)
    )

    db.commit()