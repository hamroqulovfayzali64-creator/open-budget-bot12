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
@dp.message(Command("start"))
async def start(message: types.Message):

    await save_user(message.from_user.id)

    await message.answer(
        TEXTS["uz"]["select_language"],
        reply_markup=language_keyboard
    )


@dp.message(lambda message: message.text == "🇺🇿 O'zbek")
async def uz_language(message: types.Message):

    await set_language(message.from_user.id, "uz")

    await message.answer(
        TEXTS["uz"]["select_project"],
        reply_markup=user_keyboard_uz
    )


@dp.message(lambda message: message.text == "🇷🇺 Русский")
async def ru_language(message: types.Message):

    await set_language(message.from_user.id, "ru")

    await message.answer(
        TEXTS["ru"]["select_project"],
        reply_markup=user_keyboard_ru
    )
@dp.message(lambda message: message.text in ["📌 Loyihalar", "📌 Проекты"])
async def show_projects(message: types.Message):

    lang = await get_language(message.from_user.id)

    cursor.execute(
        "SELECT id, name_uz, name_ru, url FROM projects"
    )

    projects = cursor.fetchall()

    if not projects:
        await message.answer(
            TEXTS[lang]["no_project"]
        )
        return


    for project in projects:

        project_id, name_uz, name_ru, url = project

        name = name_uz if lang == "uz" else name_ru

        cursor.execute(
            """
            UPDATE users
            SET project_clicks = project_clicks + 1
            WHERE user_id=?
            """,
            (message.from_user.id,)
        )
        db.commit()


        if url:
            await message.answer(
                f"📌 {name}\n🔗 {url}"
            )
        else:
            await message.answer(
                f"📌 {name}\n{TEXTS[lang]['no_link']}"
            )