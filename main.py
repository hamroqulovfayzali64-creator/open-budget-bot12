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
    joined TEXT,
    project_views INTEGER DEFAULT 0,
    vote_clicks INTEGER DEFAULT 0
)
""")


cursor.execute("""
CREATE TABLE IF NOT EXISTS projects(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name_uz TEXT,
    name_ru TEXT,
    link TEXT
)
""")

db.commit()


state = {}


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
        [
            KeyboardButton(text="📌 Loyihalar")
        ]
    ],
    resize_keyboard=True
)


ru_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="📌 Проекты")
        ]
    ],
    resize_keyboard=True
)


admin_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="➕ Loyiha qo'shish")
        ],
        [
            KeyboardButton(text="📊 Statistika")
        ]
    ],
    resize_keyboard=True
)


async def save_user(user_id):

    cursor.execute(
        """
        INSERT OR IGNORE INTO users(user_id, joined)
        VALUES (?,?)
        """,
        (
            user_id,
            datetime.now().strftime("%Y-%m-%d")
        )
    )

    db.commit()