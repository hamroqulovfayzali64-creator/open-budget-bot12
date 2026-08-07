import asyncio
import sqlite3

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from config import BOT_TOKEN, ADMINS


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


db = sqlite3.connect("bot.db")
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY
)
""")

db.commit()


menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🇺🇿 O'zbek"),
            KeyboardButton(text="🇷🇺 Русский")
        ]
    ],
    resize_keyboard=True
)


@dp.message(Command("start"))
async def start(message: types.Message):

    cursor.execute(
        "INSERT OR IGNORE INTO users VALUES (?)",
        (message.from_user.id,)
    )

    db.commit()

    await message.answer(
        "Tilni tanlang:",
        reply_markup=menu
    )


@dp.message()
async def text_handler(message: types.Message):

    if message.text == "🇺🇿 O'zbek":
        await message.answer(
            "Assalomu alaykum! O'zbek tili tanlandi."
        )

    elif message.text == "🇷🇺 Русский":
        await message.answer(
            "Здравствуйте! Русский язык выбран."
        )


@dp.message(Command("admin"))
async def admin(message: types.Message):

    if message.from_user.id in ADMINS:
        await message.answer(
            "Admin panelga xush kelibsiz."
        )
    else:
        await message.answer(
            "Ruxsat yo'q ❌"
        )


async def main():

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())