import asyncio
import sqlite3

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

TOKEN="8615736731:AAFImAWTDRhBJAyOhXbY6D0wwysIa0Boz1c"

ADMINLAR = [7998053914, 1599812727]

bot = Bot(token=TOKEN)
dp = Dispatcher()

db = sqlite3.connect("bot.db")
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS loyiha(
    id INTEGER PRIMARY KEY,
    nomi TEXT,
    havola TEXT
)
""")

db.commit()

cursor.execute("SELECT * FROM loyiha")
if cursor.fetchone() is None:
    cursor.execute(
        "INSERT INTO loyiha(nomi,havola) VALUES (?,?)",
        ("Hozircha loyiha yo'q", "")
    )
    db.commit()


admin_state = {}


til = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🇺🇿 O'zbek tili"),
            KeyboardButton(text="🇷🇺 Русский язык")
        ]
    ],
    resize_keyboard=True
)


menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="📌 1-loyiha")
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



@dp.message(Command("start"))
async def start(message: types.Message):

    cursor.execute(
        "INSERT OR IGNORE INTO users VALUES (?)",
        (message.from_user.id,)
    )
    db.commit()

    await message.answer(
        "Tilni tanlang:",
        reply_markup=til
    )



@dp.message(Command("admin"))
async def admin(message: types.Message):

    if message.from_user.id in ADMINLAR:
        await message.answer(
            "Admin panel:",
            reply_markup=admin_menu
        )
    else:
        await message.answer("Ruxsat yo'q ❌")



@dp.message()
async def handler(message: types.Message):

    uid = message.from_user.id


    if uid in admin_state:

        if admin_state[uid] == "nom":

            cursor.execute(
                "UPDATE loyiha SET nomi=? WHERE id=1",
                (message.text,)
            )
            db.commit()

            admin_state[uid] = "link"

            await message.answer(
                "Endi loyiha havolasini yuboring:"
            )
            return


        elif admin_state[uid] == "link":

            cursor.execute(
                "UPDATE loyiha SET havola=? WHERE id=1",
                (message.text,)
            )
            db.commit()

            del admin_state[uid]

            await message.answer(
                "✅ Loyiha saqlandi",
                reply_markup=admin_menu
            )
            return



    if message.text in [
        "🇺🇿 O'zbek tili",
        "🇷🇺 Русский язык"
    ]:

        await message.answer(
            "Loyihani tanlang:",
            reply_markup=menu
        )


    elif message.text == "📌 1-loyiha":

        cursor.execute(
            "SELECT nomi,havola FROM loyiha WHERE id=1"
        )

        loyiha = cursor.fetchone()


        if loyiha[1].startswith("http"):

            tugma = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🗳 Ovoz berish",
                            url=loyiha[1]
                        )
                    ]
                ]
            )

            await message.answer(
                f"📌 {loyiha[0]}",
                reply_markup=tugma
            )

        else:
            await message.answer(
                f"📌 {loyiha[0]}\n"
                "🔗 Havola hali qo'shilmagan"
            )


    elif message.text == "➕ Loyiha qo'shish":

        if uid in ADMINLAR:

            admin_state[uid] = "nom"

            await message.answer(
                "Loyiha nomini yuboring:"
            )


    elif message.text == "📊 Statistika":

        if uid in ADMINLAR:

            cursor.execute(
                "SELECT COUNT(*) FROM users"
            )

            son = cursor.fetchone()[0]

            await message.answer(
                f"📊 Foydalanuvchilar: {son} ta"
            )



async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())