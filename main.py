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
@dp.message(Command("admin"))
async def admin(message: types.Message):

    if message.from_user.id in ADMINS:

        await message.answer(
            TEXTS["uz"]["admin_panel"],
            reply_markup=admin_keyboard
        )

    else:
        await message.answer("❌ Ruxsat yo'q")


@dp.message(lambda message: message.text == "📊 Statistika")
async def statistics(message: types.Message):

    if message.from_user.id not in ADMINS:
        return

    cursor.execute(
        "SELECT COUNT(*) FROM users"
    )
    users = cursor.fetchone()[0]


    cursor.execute(
        "SELECT SUM(project_clicks), SUM(vote_clicks) FROM users"
    )

    clicks = cursor.fetchone()

    project_clicks = clicks[0] or 0
    vote_clicks = clicks[1] or 0


    await message.answer(
        f"""
📊 BOT STATISTIKASI

👥 Foydalanuvchilar: {users}

📌 Loyiha ko‘rilishi: {project_clicks}

🗳 Ovoz berish bosilishi: {vote_clicks}
"""
    )
@dp.message(lambda message: message.text == "➕ Loyiha qo'shish")
async def add_project_start(message: types.Message):

    if message.from_user.id not in ADMINS:
        return

    admin_state[message.from_user.id] = "project_name"

    await message.answer(
        "Loyiha nomini yuboring:"
    )


@dp.message()
async def admin_add_project(message: types.Message):

    uid = message.from_user.id

    if uid not in admin_state:
        return


    if admin_state[uid] == "project_name":

        cursor.execute(
            """
            INSERT INTO projects(name_uz, name_ru, url)
            VALUES(?,?,?)
            """,
            (
                message.text,
                message.text,
                ""
            )
        )

        db.commit()

        admin_state[uid] = "project_url"

        await message.answer(
            "Endi loyiha havolasini yuboring:"
        )
        return


    if admin_state[uid] == "project_url":

        cursor.execute(
            """
            UPDATE projects
            SET url=?
            WHERE id=(SELECT MAX(id) FROM projects)
            """,
            (message.text,)
        )

        db.commit()

        del admin_state[uid]

        await message.answer(
            "✅ Loyiha saqlandi"
        )
async def main():

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())