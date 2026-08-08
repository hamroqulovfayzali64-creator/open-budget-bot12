import asyncio
import logging
import sqlite3

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)

# =========================================================
# SOZLAMALAR
# =========================================================

BOT_TOKEN = "8615736731:AAEYW7RCc-YeGPI3mrod2dkyxeYR7QbRqOA"

ADMIN_IDS = [
    7998053914,
    # Ikkinchi admin bo‘lsa:
    # 1599812727,
]

DB_NAME = "bot.db"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# =========================================================
# DATABASE
# =========================================================

def db_connect():
    return sqlite3.connect(DB_NAME)


def init_db():
    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            language TEXT DEFAULT 'uz',
            phone TEXT,
            voted INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            link TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def add_user(user_id, username, first_name):
    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR IGNORE INTO users
        (user_id, username, first_name)
        VALUES (?, ?, ?)
    """, (
        user_id,
        username,
        first_name
    ))

    conn.commit()
    conn.close()


def set_language(user_id, language):
    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE users SET language = ? WHERE user_id = ?",
        (language, user_id)
    )

    conn.commit()
    conn.close()


def get_language(user_id):
    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT language FROM users WHERE user_id = ?",
        (user_id,)
    )

    result = cursor.fetchone()

    conn.close()

    if result:
        return result[0]

    return "uz"


# =========================================================
# KEYBOARDLAR
# =========================================================

def language_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🇺🇿 O‘zbekcha",
                    callback_data="lang_uz"
                ),
                InlineKeyboardButton(
                    text="🇷🇺 Русский",
                    callback_data="lang_ru"
                )
            ]
        ]
    )


def uz_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📌 Loyihalar")
            ],
            [
                KeyboardButton(text="📰 Yangiliklar"),
                KeyboardButton(text="❓ Yordam")
            ]
        ],
        resize_keyboard=True
    )


def ru_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📌 Проекты")
            ],
            [
                KeyboardButton(text="📰 Новости"),
                KeyboardButton(text="❓ Помощь")
            ]
        ],
        resize_keyboard=True
    )


def admin_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📊 Statistika")
            ],
            [
                KeyboardButton(text="➕ Loyiha qo‘shish")
            ],
            [
                KeyboardButton(text="📰 Yangilik qo‘shish")
            ],
            [
                KeyboardButton(text="📋 Loyihalar")
            ],
            [
                KeyboardButton(text="❌ Admin panelni yopish")
            ]
        ],
        resize_keyboard=True
    )


# =========================================================
# ADMIN HOLATLARI
# =========================================================

admin_project_waiting = set()
admin_news_waiting = set()


# =========================================================
# START
# =========================================================

@dp.message(CommandStart())
async def start_handler(message: Message):

    add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )

    await message.answer(
        "Assalomu alaykum! 👋\n\n"
        "Tilni tanlang / Выберите язык:",
        reply_markup=language_keyboard()
    )


# =========================================================
# TIL TANLASH
# =========================================================

@dp.callback_query(F.data == "lang_uz")
async def language_uz(callback: CallbackQuery):

    set_language(callback.from_user.id, "uz")

    await callback.message.answer(
        "🇺🇿 O‘zbek tili tanlandi.\n\n"
        "Botdan foydalanishingiz mumkin.",
        reply_markup=uz_keyboard()
    )

    await callback.answer()


@dp.callback_query(F.data == "lang_ru")
async def language_ru(callback: CallbackQuery):

    set_language(callback.from_user.id, "ru")

    await callback.message.answer(
        "🇷🇺 Русский язык выбран.\n\n"
        "Вы можете пользоваться ботом.",
        reply_markup=ru_keyboard()
    )

    await callback.answer()


# =========================================================
# LOYIHALAR — O‘ZBEKCHA
# =========================================================

@dp.message(F.text == "📌 Loyihalar")
async def projects_uz(message: Message):

    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, name, link FROM projects"
    )

    projects = cursor.fetchall()

    conn.close()

    if not projects:
        await message.answer(
            "📌 Hozircha loyihalar qo‘shilmagan."
        )
        return

    buttons = []

    for project_id, name, link in projects:

        buttons.append([
            InlineKeyboardButton(
                text=name,
                url=link
            )
        ])

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=buttons
    )

    await message.answer(
        "📌 Loyihalar:",
        reply_markup=keyboard
    )


# =========================================================
# LOYIHALAR — RUSCHA
# =========================================================

@dp.message(F.text == "📌 Проекты")
async def projects_ru(message: Message):

    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, name, link FROM projects"
    )

    projects = cursor.fetchall()

    conn.close()

    if not projects:
        await message.answer(
            "📌 Пока проекты не добавлены."
        )
        return

    buttons = []

    for project_id, name, link in projects:

        buttons.append([
            InlineKeyboardButton(
                text=name,
                url=link
            )
        ])

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=buttons
    )

    await message.answer(
        "📌 Проекты:",
        reply_markup=keyboard
    )


# =========================================================
# YANGILIKLAR — O‘ZBEKCHA
# =========================================================

@dp.message(F.text == "📰 Yangiliklar")
async def news_uz(message: Message):

    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT text FROM news ORDER BY id DESC"
    )

    news = cursor.fetchall()

    conn.close()

    if not news:
        await message.answer(
            "📰 Hozircha yangiliklar yo‘q."
        )
        return

    text = "📰 Yangiliklar:\n\n"

    for item in news:
        text += f"• {item[0]}\n\n"

    await message.answer(text)


# =========================================================
# YANGILIKLAR — RUSCHA
# =========================================================

@dp.message(F.text == "📰 Новости")
async def news_ru(message: Message):

    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT text FROM news ORDER BY id DESC"
    )

    news = cursor.fetchall()

    conn.close()

    if not news:
        await message.answer(
            "📰 Новостей пока нет."
        )
        return

    text = "📰 Новости:\n\n"

    for item in news:
        text += f"• {item[0]}\n\n"

    await message.answer(text)


# =========================================================
# YORDAM — O‘ZBEKCHA
# =========================================================

@dp.message(F.text == "❓ Yordam")
async def help_uz(message: Message):

    await message.answer(
        "❓ Yordam\n\n"
        "📌 Loyihalar — mavjud loyihalarni ko‘rish\n"
        "📰 Yangiliklar — yangiliklarni ko‘rish\n\n"
        "Muammo bo‘lsa, administratorga murojaat qiling."
    )


# =========================================================
# YORDAM — RUSCHA
# =========================================================

@dp.message(F.text == "❓ Помощь")
async def help_ru(message: Message):

    await message.answer(
        "❓ Помощь\n\n"
        "📌 Проекты — просмотр проектов\n"
        "📰 Новости — просмотр новостей\n\n"
        "При возникновении проблем обратитесь к администратору."
    )


# =========================================================
# ADMIN TEKSHIRISH
# =========================================================

def is_admin(user_id):
    return user_id in ADMIN_IDS


# =========================================================
# ADMIN PANEL
# =========================================================

@dp.message(Command("admin"))
async def admin_command(message: Message):

    if not is_admin(message.from_user.id):
        await message.answer(
            "⛔ Sizda admin huquqi yo‘q."
        )
        return

    await message.answer(
        "👨‍💼 Admin panel",
        reply_markup=admin_keyboard()
    )


# =========================================================
# STATISTIKA
# =========================================================

@dp.message(F.text == "📊 Statistika")
async def statistics(message: Message):

    if not is_admin(message.from_user.id):
        return

    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT COUNT(*) FROM users"
    )

    total_users = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM users WHERE voted = 1"
    )

    voted_users = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM users WHERE voted = 0"
    )

    not_voted = cursor.fetchone()[0]

    conn.close()

    await message.answer(
        "📊 STATISTIKA\n\n"
        f"👥 Jami foydalanuvchilar: {total_users}\n"
        f"🗳 Ovoz berganlar: {voted_users}\n"
        f"⏳ Ovoz bermaganlar: {not_voted}"
    )


# =========================================================
# LOYIHA QO‘SHISHNI BOSHLASH
# =========================================================

@dp.message(F.text == "➕ Loyiha qo‘shish")
async def add_project_start(message: Message):

    if not is_admin(message.from_user.id):
        return

    admin_project_waiting.add(message.from_user.id)

    await message.answer(
        "➕ Yangi loyiha qo‘shish.\n\n"
        "Quyidagi formatda yuboring:\n\n"
        "Loyiha nomi | https://example.com"
    )


# =========================================================
# LOYIHA SAQLASH
# =========================================================

async def save_project(message: Message):

    if not is_admin(message.from_user.id):
        return False

    if message.from_user.id not in admin_project_waiting:
        return False

    if not message.text or "|" not in message.text:
        await message.answer(
            "❌ Format noto‘g‘ri.\n\n"
            "Masalan:\n"
            "1-loyiha | https://example.com"
        )
        return True

    name, link = message.text.split("|", 1)

    name = name.strip()
    link = link.strip()

    if not name:
        await message.answer(
            "❌ Loyiha nomini yozing."
        )
        return True

    if not link.startswith(("http://", "https://")):
        await message.answer(
            "❌ Havola http:// yoki https:// bilan boshlanishi kerak."
        )
        return True

    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO projects (name, link) VALUES (?, ?)",
        (name, link)
    )

    conn.commit()
    conn.close()

    admin_project_waiting.remove(message.from_user.id)

    await message.answer(
        "✅ Loyiha muvaffaqiyatli qo‘shildi!\n\n"
        f"📌 {name}\n"
        f"🔗 {link}",
        reply_markup=admin_keyboard()
    )

    return True


# =========================================================
# YANGILIK QO‘SHISHNI BOSHLASH
# =========================================================

@dp.message(F.text == "📰 Yangilik qo‘shish")
async def add_news_start(message: Message):

    if not is_admin(message.from_user.id):
        return

    admin_news_waiting.add(message.from_user.id)

    await message.answer(
        "📰 Yangilik matnini yuboring.\n\n"
        "Masalan:\n"
        "Bugun yangi loyiha qo‘shildi."
    )


# =========================================================
# YANGILIK SAQLASH
# =========================================================

async def save_news(message: Message):

    if not is_admin(message.from_user.id):
        return False

    if message.from_user.id not in admin_news_waiting:
        return False

    if not message.text or not message.text.strip():
        await message.answer(
            "❌ Yangilik matni bo‘sh bo‘lishi mumkin emas."
        )
        return True

    text = message.text.strip()

    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO news (text) VALUES (?)",
        (text,)
    )

    conn.commit()
    conn.close()

    admin_news_waiting.remove(message.from_user.id)

    await message.answer(
        "✅ Yangilik muvaffaqiyatli qo‘shildi!",
        reply_markup=admin_keyboard()
    )

    return True


# =========================================================
# ADMIN UCHUN LOYIHALAR RO‘YXATI
# =========================================================

@dp.message(F.text == "📋 Loyihalar")
async def admin_projects(message: Message):

    if not is_admin(message.from_user.id):
        return

    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, name, link FROM projects"
    )

    projects = cursor.fetchall()

    conn.close()

    if not projects:
        await message.answer(
            "📋 Hozircha loyihalar yo‘q."
        )
        return

    text = "📋 LOYIHALAR\n\n"

    for project_id, name, link in projects:

        text += (
            f"🆔 {project_id}\n"
            f"📌 {name}\n"
            f"🔗 {link}\n\n"
        )

    await message.answer(text)


# =========================================================
# ADMIN PANELNI YOPISH
# =========================================================

@dp.message(F.text == "❌ Admin panelni yopish")
async def close_admin(message: Message):

    if not is_admin(message.from_user.id):
        return

    lang = get_language(message.from_user.id)

    if lang == "ru":

        await message.answer(
            "✅ Admin panel yopildi.",
            reply_markup=ru_keyboard()
        )

    else:

        await message.answer(
            "✅ Admin panel yopildi.",
            reply_markup=uz_keyboard()
        )


# =========================================================
# BOSHQA XABARLARNI QAYTA ISHLASH
# =========================================================

@dp.message()
async def other_messages(message: Message):

    # Avval yangilik qo‘shishni tekshiramiz
    if await save_news(message):
        return

    # Keyin loyiha qo‘shishni tekshiramiz
    if await save_project(message):
        return


# =========================================================
# BOTNI ISHGA TUSHIRISH
# =========================================================

async def main():

    init_db()

    print("=================================")
    print("BOT ISHGA TUSHDI")
    print("=================================")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())