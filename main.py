from aiogram.types import ReplyKeyboardRemove
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

cursor.execute("""
CREATE TABLE IF NOT EXISTS votes(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    project_id INTEGER,
    phone TEXT,
    date TEXT
)
""")

db.commit()


state = {}
vote_state = {}


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


phone_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(
                text="📱 Telefon raqamni yuborish",
                request_contact=True
            )
        ]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
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
async def set_language(user_id, lang):

    cursor.execute(
        "UPDATE users SET language=? WHERE user_id=?",
        (lang, user_id)
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



@dp.message(Command("start"))
async def start(message: types.Message):

    await save_user(message.from_user.id)

    await message.answer(
        "Tilni tanlang:",
        reply_markup=language_keyboard
    )



@dp.message(lambda m: m.text == "🇺🇿 O'zbek")
async def uz_lang(message: types.Message):

    await set_language(message.from_user.id, "uz")

    await message.answer(
        "Kerakli bo‘limni tanlang:",
        reply_markup=uz_keyboard
    )



@dp.message(lambda m: m.text == "🇷🇺 Русский")
async def ru_lang(message: types.Message):

    await set_language(message.from_user.id, "ru")

    await message.answer(
        "Выберите раздел:",
        reply_markup=ru_keyboard
    )



@dp.message(lambda m: m.text in ["📌 Loyihalar", "📌 Проекты"])
async def projects(message: types.Message):

    lang = await get_language(message.from_user.id)

    cursor.execute(
        "SELECT id,name_uz,name_ru,link FROM projects"
    )

    data = cursor.fetchall()


    if not data:
        if lang == "ru":
            await message.answer("Проектов пока нет")
        else:
            await message.answer("Hozircha loyiha yo‘q")
        return


    for p in data:

        pid, uz, ru, link = p

        name = uz if lang == "uz" else ru


        cursor.execute(
            """
            UPDATE users
            SET project_views = project_views + 1
            WHERE user_id=?
            """,
            (message.from_user.id,)
        )

        db.commit()


        if link:


                    
keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🌐 Havola orqali ovoz berish",
                url=link
            )
        ],
        [
            InlineKeyboardButton(
                text="📱 Telefon bilan ovoz berish",
                callback_data=f"vote_{pid}"
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
                f"📌 {name}\n🔗 Havola yo‘q"
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
            "Ruxsat yo‘q ❌"
        )
@dp.message(lambda m: m.text == "➕ Loyiha qo'shish")
async def add_project(message: types.Message):

    if message.from_user.id not in ADMINS:
        return

    state[message.from_user.id] = "name"

    await message.answer(
        "Loyiha nomini yuboring:"
    )



@dp.message(lambda m: m.text == "📊 Statistika")
async def statistics(message: types.Message):

    if message.from_user.id not in ADMINS:
        return


    cursor.execute(
        "SELECT COUNT(*) FROM users"
    )

    users = cursor.fetchone()[0]


    cursor.execute(
        "SELECT COUNT(*) FROM projects"
    )

    projects = cursor.fetchone()[0]


    cursor.execute(
        "SELECT SUM(project_views), SUM(vote_clicks) FROM users"
    )

    result = cursor.fetchone()


    views = result[0] or 0
    votes = result[1] or 0


    await message.answer(
        f"""
📊 Statistika

👥 Foydalanuvchilar: {users}

📌 Loyihalar: {projects}

👀 Ko‘rishlar: {views}

🗳 Ovoz tugmasi bosilishi: {votes}
"""
    )



@dp.message()
async def add_project_process(message: types.Message):

    uid = message.from_user.id


    if uid not in state:
        return


    if state[uid] == "name":

        cursor.execute(
            """
            INSERT INTO projects(name_uz,name_ru,link)
            VALUES(?,?,?)
            """,
            (
                message.text,
                message.text,
                ""
            )
        )

        db.commit()


        state[uid] = "link"


        await message.answer(
            "Endi loyiha havolasini yuboring:"
        )

        return



    if state[uid] == "link":

        cursor.execute(
            """
            UPDATE projects
            SET link=?
            WHERE id=(SELECT MAX(id) FROM projects)
            """,
            (message.text,)
        )

        db.commit()


        del state[uid]


        await message.answer(
            "✅ Loyiha saqlandi"
        )



async def main():

    await dp.start_polling(bot)


@dp.message(lambda message: message.contact is not None)
async def get_phone(message: types.Message):
    phone = message.contact.phone_number
    user_id = message.from_user.id

    # qolgan kodlar...


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
if __name__ == "__main__":
    asyncio.run(main())