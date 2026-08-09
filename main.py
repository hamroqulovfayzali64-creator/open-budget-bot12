import asyncio
import logging
import os
import sqlite3
from pathlib import Path
from html import escape
from contextlib import closing

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
from aiogram.exceptions import (
    TelegramForbiddenError,
    TelegramBadRequest,
    TelegramRetryAfter,
    TelegramNetworkError,
    TelegramServerError,
)

# =========================================================
# SOZLAMALAR
# =========================================================

BOT_TOKEN = os.getenv(
    "BOT_TOKEN",
    "8615736731:AAEfzzzWI-oPwjCtYG2raKE-ctqoLeHo1hY"
)

ADMIN_IDS = {
    7998053914,
}

BASE_DIR = Path(__file__).resolve().parent
DB_NAME = BASE_DIR / "bot.db"

# Broadcast uchun bir vaqtning o'zida nechta xabar
# yuborilishini belgilaydi.
BROADCAST_CONCURRENCY = 20

# Telegram flood-limitga tushmaslik uchun.
BROADCAST_DELAY = 0.03

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# =========================================================
# ASYNC LOCKLAR
# =========================================================

# SQLite yozish operatsiyalarini tartibli bajarish uchun.
db_write_lock = asyncio.Lock()

# Bir foydalanuvchi bir xil callbackni juda tez
# bosib yuborsa himoya.
callback_locks = {}

# =========================================================
# FOYDALANUVCHI HOLATLARI
# =========================================================

waiting_for_phone = {}

admin_project_waiting = set()
admin_project_name = {}

admin_news_waiting = set()
admin_broadcast_waiting = set()
admin_delete_waiting = set()

question_waiting = set()
admin_answer_waiting = {}

# =========================================================
# DATABASE
# =========================================================


def db_connect():
    conn = sqlite3.connect(
        str(DB_NAME),
        timeout=30,
        check_same_thread=False,
    )

    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA temp_store=MEMORY")

    return conn


def init_db():
    conn = db_connect()

    try:
        cursor = conn.cursor()

        # -------------------------------------------------
        # USERS
        # -------------------------------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                language TEXT DEFAULT 'uz',
                phone TEXT,
                voted INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # -------------------------------------------------
        # PROJECTS
        # -------------------------------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                link TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # -------------------------------------------------
        # NEWS
        # -------------------------------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT,
                photo_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # -------------------------------------------------
        # VOTES
        # -------------------------------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                project_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, project_id)
            )
        """)

        # -------------------------------------------------
        # QUESTIONS
        # -------------------------------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                question TEXT NOT NULL,
                answer TEXT,
                answered INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                answered_at TIMESTAMP
            )
        """)

        # -------------------------------------------------
        # ESKI BAZANI MIGRATSIYA
        # -------------------------------------------------

        cursor.execute("PRAGMA table_info(users)")
        user_columns = {
            row[1]
            for row in cursor.fetchall()
        }

        if "username" not in user_columns:
            cursor.execute("""
                ALTER TABLE users
                ADD COLUMN username TEXT
            """)

        if "first_name" not in user_columns:
            cursor.execute("""
                ALTER TABLE users
                ADD COLUMN first_name TEXT
            """)

        if "language" not in user_columns:
            cursor.execute("""
                ALTER TABLE users
                ADD COLUMN language TEXT DEFAULT 'uz'
            """)

        if "phone" not in user_columns:
            cursor.execute("""
                ALTER TABLE users
                ADD COLUMN phone TEXT
            """)

        if "voted" not in user_columns:
            cursor.execute("""
                ALTER TABLE users
                ADD COLUMN voted INTEGER DEFAULT 0
            """)

        if "created_at" not in user_columns:
            cursor.execute("""
                ALTER TABLE users
                ADD COLUMN created_at
                TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            """)

        cursor.execute("PRAGMA table_info(news)")
        news_columns = {
            row[1]
            for row in cursor.fetchall()
        }

        if "text" not in news_columns:
            cursor.execute("""
                ALTER TABLE news
                ADD COLUMN text TEXT
            """)

        if "photo_id" not in news_columns:
            cursor.execute("""
                ALTER TABLE news
                ADD COLUMN photo_id TEXT
            """)

        # -------------------------------------------------
        # INDEXLAR
        # -------------------------------------------------

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_votes_user
            ON votes(user_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_votes_project
            ON votes(project_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_questions_user
            ON questions(user_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_questions_answered
            ON questions(answered)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_projects_created
            ON projects(id DESC)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_news_created
            ON news(id DESC)
        """)

        conn.commit()

        logger.info(
            "DATABASE TAYYOR: %s",
            DB_NAME
        )

    finally:
        conn.close()


# =========================================================
# DATABASE ASYNC WRAPPER
# =========================================================


async def db_read(function, *args):
    return await asyncio.to_thread(
        function,
        *args
    )


async def db_write(function, *args):
    async with db_write_lock:
        return await asyncio.to_thread(
            function,
            *args
        )


# =========================================================
# USER DATABASE
# =========================================================


def _add_user(
    user_id,
    username,
    first_name
):
    conn = db_connect()

    try:
        conn.execute("""
            INSERT INTO users
            (
                user_id,
                username,
                first_name
            )
            VALUES (?, ?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name
        """, (
            user_id,
            username,
            first_name
        ))

        conn.commit()

    finally:
        conn.close()


async def add_user(
    user_id,
    username,
    first_name
):
    await db_write(
        _add_user,
        user_id,
        username,
        first_name
    )


def _set_language(
    user_id,
    language
):
    conn = db_connect()

    try:
        conn.execute("""
            UPDATE users
            SET language = ?
            WHERE user_id = ?
        """, (
            language,
            user_id
        ))

        conn.commit()

    finally:
        conn.close()


async def set_language(
    user_id,
    language
):
    await db_write(
        _set_language,
        user_id,
        language
    )


def _get_language(user_id):
    conn = db_connect()

    try:
        row = conn.execute("""
            SELECT language
            FROM users
            WHERE user_id = ?
        """, (user_id,)).fetchone()

        if row and row[0]:
            return row[0]

        return "uz"

    finally:
        conn.close()


async def get_language(user_id):
    return await db_read(
        _get_language,
        user_id
    )


def _save_user_phone(
    user_id,
    phone
):
    conn = db_connect()

    try:
        conn.execute("""
            UPDATE users
            SET phone = ?
            WHERE user_id = ?
        """, (
            phone,
            user_id
        ))

        conn.commit()

    finally:
        conn.close()


async def save_user_phone(
    user_id,
    phone
):
    await db_write(
        _save_user_phone,
        user_id,
        phone
    )


def _delete_user(user_id):
    conn = db_connect()

    try:
        conn.execute(
            "DELETE FROM users WHERE user_id = ?",
            (user_id,)
        )

        conn.commit()

    finally:
        conn.close()


async def delete_user(user_id):
    await db_write(
        _delete_user,
        user_id
    )


# =========================================================
# PROJECT DATABASE
# =========================================================


def _get_projects():
    conn = db_connect()

    try:
        return conn.execute("""
            SELECT id, name, link
            FROM projects
            ORDER BY id DESC
        """).fetchall()

    finally:
        conn.close()


async def get_projects():
    return await db_read(
        _get_projects
    )


def _get_project(project_id):
    conn = db_connect()

    try:
        return conn.execute("""
            SELECT id, name, link
            FROM projects
            WHERE id = ?
        """, (
            project_id,
        )).fetchone()

    finally:
        conn.close()


async def get_project(project_id):
    return await db_read(
        _get_project,
        project_id
    )


def _insert_project(
    name,
    link
):
    conn = db_connect()

    try:
        cursor = conn.execute("""
            INSERT INTO projects
            (name, link)
            VALUES (?, ?)
        """, (
            name,
            link
        ))

        conn.commit()

        return cursor.lastrowid

    finally:
        conn.close()


async def insert_project(
    name,
    link
):
    return await db_write(
        _insert_project,
        name,
        link
    )


def _delete_project(project_id):
    conn = db_connect()

    try:
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM votes WHERE project_id = ?",
            (project_id,)
        )

        cursor.execute(
            "DELETE FROM projects WHERE id = ?",
            (project_id,)
        )

        deleted = cursor.rowcount

        conn.commit()

        return deleted

    finally:
        conn.close()


async def delete_project(project_id):
    return await db_write(
        _delete_project,
        project_id
    )


# =========================================================
# VOTE DATABASE
# =========================================================


def _confirm_vote(
    user_id,
    project_id
):
    conn = db_connect()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, name
            FROM projects
            WHERE id = ?
        """, (
            project_id,
        ))

        project = cursor.fetchone()

        if not project:
            return "not_found", None

        cursor.execute("""
            SELECT id
            FROM votes
            WHERE user_id = ?
            AND project_id = ?
            LIMIT 1
        """, (
            user_id,
            project_id
        ))

        if cursor.fetchone():
            return "already", project

        cursor.execute("""
            INSERT INTO votes
            (user_id, project_id)
            VALUES (?, ?)
        """, (
            user_id,
            project_id
        ))

        cursor.execute("""
            UPDATE users
            SET voted = 1
            WHERE user_id = ?
        """, (
            user_id,
        ))

        conn.commit()

        return "success", project

    except sqlite3.IntegrityError:
        conn.rollback()

        return "already", None

    finally:
        conn.close()


async def confirm_vote_db(
    user_id,
    project_id
):
    return await db_write(
        _confirm_vote,
        user_id,
        project_id
    )


# =========================================================
# NEWS DATABASE
# =========================================================


def _get_news():
    conn = db_connect()

    try:
        return conn.execute("""
            SELECT id, text, photo_id
            FROM news
            ORDER BY id DESC
        """).fetchall()

    finally:
        conn.close()


async def get_news():
    return await db_read(
        _get_news
    )


def _insert_news(
    text,
    photo_id
):
    conn = db_connect()

    try:
        cursor = conn.execute("""
            INSERT INTO news
            (text, photo_id)
            VALUES (?, ?)
        """, (
            text,
            photo_id
        ))

        conn.commit()

        return cursor.lastrowid

    finally:
        conn.close()


async def insert_news(
    text,
    photo_id
):
    return await db_write(
        _insert_news,
        text,
        photo_id
    )


def _delete_news(news_id):
    conn = db_connect()

    try:
        cursor = conn.execute(
            "DELETE FROM news WHERE id = ?",
            (news_id,)
        )

        deleted = cursor.rowcount

        conn.commit()

        return deleted

    finally:
        conn.close()


async def delete_news(news_id):
    return await db_write(
        _delete_news,
        news_id
    )


# =========================================================
# QUESTIONS DATABASE
# =========================================================


def _insert_question(
    user_id,
    text
):
    conn = db_connect()

    try:
        cursor = conn.execute("""
            INSERT INTO questions
            (user_id, question)
            VALUES (?, ?)
        """, (
            user_id,
            text
        ))

        question_id = cursor.lastrowid

        conn.commit()

        return question_id

    finally:
        conn.close()


async def insert_question(
    user_id,
    text
):
    return await db_write(
        _insert_question,
        user_id,
        text
    )


def _get_question(question_id):
    conn = db_connect()

    try:
        return conn.execute("""
            SELECT user_id, question, answered
            FROM questions
            WHERE id = ?
        """, (
            question_id,
        )).fetchone()

    finally:
        conn.close()


async def get_question(question_id):
    return await db_read(
        _get_question,
        question_id
    )


def _answer_question(
    question_id,
    answer
):
    conn = db_connect()

    try:
        cursor = conn.cursor()

        row = cursor.execute("""
            SELECT user_id, question, answered
            FROM questions
            WHERE id = ?
        """, (
            question_id,
        )).fetchone()

        if not row:
            return "not_found", None

        if row[2] == 1:
            return "already", row

        cursor.execute("""
            UPDATE questions
            SET answer = ?,
                answered = 1,
                answered_at = CURRENT_TIMESTAMP
            WHERE id = ?
            AND answered = 0
        """, (
            answer,
            question_id
        ))

        if cursor.rowcount == 0:
            conn.rollback()
            return "already", row

        conn.commit()

        return "success", row

    finally:
        conn.close()


async def answer_question(
    question_id,
    answer
):
    return await db_write(
        _answer_question,
        question_id,
        answer
    )


# =========================================================
# STATISTICS
# =========================================================


def _get_statistics():
    conn = db_connect()

    try:
        cursor = conn.cursor()

        total_users = cursor.execute("""
            SELECT COUNT(*)
            FROM users
        """).fetchone()[0]

        phone_users = cursor.execute("""
            SELECT COUNT(*)
            FROM users
            WHERE phone IS NOT NULL
            AND phone != ''
        """).fetchone()[0]

        voted_users = cursor.execute("""
            SELECT COUNT(*)
            FROM users
            WHERE voted = 1
        """).fetchone()[0]

        total_projects = cursor.execute("""
            SELECT COUNT(*)
            FROM projects
        """).fetchone()[0]

        total_news = cursor.execute("""
            SELECT COUNT(*)
            FROM news
        """).fetchone()[0]

        total_votes = cursor.execute("""
            SELECT COUNT(*)
            FROM votes
        """).fetchone()[0]

        total_questions = cursor.execute("""
            SELECT COUNT(*)
            FROM questions
        """).fetchone()[0]

        unanswered = cursor.execute("""
            SELECT COUNT(*)
            FROM questions
            WHERE answered = 0
        """).fetchone()[0]

        return {
            "total_users": total_users,
            "phone_users": phone_users,
            "voted_users": voted_users,
            "not_voted": max(
                0,
                total_users - voted_users
            ),
            "total_projects": total_projects,
            "total_news": total_news,
            "total_votes": total_votes,
            "total_questions": total_questions,
            "unanswered": unanswered,
        }

    finally:
        conn.close()


async def get_statistics():
    return await db_read(
        _get_statistics
    )


# =========================================================
# ALL USER IDS
# =========================================================


def _get_all_user_ids():
    conn = db_connect()

    try:
        rows = conn.execute("""
            SELECT user_id
            FROM users
            ORDER BY user_id
        """).fetchall()

        return [
            row[0]
            for row in rows
        ]

    finally:
        conn.close()


async def get_all_user_ids():
    return await db_read(
        _get_all_user_ids
    )


# =========================================================
# ADMIN
# =========================================================


def is_admin(user_id):
    return user_id in ADMIN_IDS


# =========================================================
# KEYBOARDS
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
                KeyboardButton(
                    text="📌 Loyihalar"
                )
            ],
            [
                KeyboardButton(
                    text="📰 Yangiliklar"
                ),
                KeyboardButton(
                    text="❓ Savol-javob"
                )
            ]
        ],
        resize_keyboard=True
    )


def ru_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="📌 Проекты"
                )
            ],
            [
                KeyboardButton(
                    text="📰 Новости"
                ),
                KeyboardButton(
                    text="❓ Вопрос-ответ"
                )
            ]
        ],
        resize_keyboard=True
    )


def admin_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="📊 Statistika"
                )
            ],
            [
                KeyboardButton(
                    text="➕ Loyiha qo‘shish"
                )
            ],
            [
                KeyboardButton(
                    text="📰 Yangilik qo‘shish"
                )
            ],
            [
                KeyboardButton(
                    text="📢 Ommaviy xabar"
                )
            ],
            [
                KeyboardButton(
                    text="📋 Loyihalar"
                )
            ],
            [
                KeyboardButton(
                    text="🗑 Ma'lumot o‘chirish"
                )
            ],
            [
                KeyboardButton(
                    text="❌ Admin panelni yopish"
                )
            ]
        ],
        resize_keyboard=True
    )


def delete_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🗑 Loyihani o‘chirish",
                    callback_data="delete_projects"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🗑 Yangilikni o‘chirish",
                    callback_data="delete_news"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Orqaga",
                    callback_data="delete_back"
                )
            ]
        ]
    )


def phone_keyboard_uz():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="📱 Telefon raqamimni yuborish",
                    request_contact=True
                )
            ],
            [
                KeyboardButton(
                    text="❌ Bekor qilish"
                )
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def phone_keyboard_ru():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="📱 Отправить мой номер",
                    request_contact=True
                )
            ],
            [
                KeyboardButton(
                    text="❌ Отмена"
                )
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )


# =========================================================
# HOLATLARNI TOZALASH
# =========================================================


def clear_admin_state(user_id):
    admin_project_waiting.discard(user_id)
    admin_project_name.pop(
        user_id,
        None
    )

    admin_news_waiting.discard(user_id)
    admin_broadcast_waiting.discard(user_id)
    admin_delete_waiting.discard(user_id)

    admin_answer_waiting.pop(
        user_id,
        None
    )

    question_waiting.discard(user_id)


# =========================================================
# START
# =========================================================


@dp.message(CommandStart())
async def start_handler(message: Message):

    await add_user(
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
# LANGUAGE
# =========================================================


@dp.callback_query(F.data == "lang_uz")
async def language_uz(
    callback: CallbackQuery
):

    await set_language(
        callback.from_user.id,
        "uz"
    )

    await callback.message.answer(
        "🇺🇿 O‘zbek tili tanlandi.",
        reply_markup=uz_keyboard()
    )

    await callback.answer()


@dp.callback_query(F.data == "lang_ru")
async def language_ru(
    callback: CallbackQuery
):

    await set_language(
        callback.from_user.id,
        "ru"
    )

    await callback.message.answer(
        "🇷🇺 Русский язык выбран.",
        reply_markup=ru_keyboard()
    )

    await callback.answer()


# =========================================================
# LOYIHALAR
# =========================================================


async def show_projects(
    message: Message,
    language="uz"
):
    projects = await get_projects()

    if not projects:

        text = (
            "📌 Hozircha loyihalar qo‘shilmagan."
            if language == "uz"
            else
            "📌 Пока проекты не добавлены."
        )

        await message.answer(text)

        return

    for project_id, name, link in projects:

        if language == "ru":
            open_text = "🔗 Открыть ссылку"
            vote_text = "🗳 Голосовать"
            description = (
                "Для голосования нажмите кнопку ниже."
            )
        else:
            open_text = "🔗 Havolani ochish"
            vote_text = "🗳 Ovoz berish"
            description = (
                "Ovoz berish uchun quyidagi tugmani bosing."
            )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=open_text,
                        url=link
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=vote_text,
                        callback_data=f"vote_{project_id}"
                    )
                ]
            ]
        )

        await message.answer(
            f"📌 <b>{escape(str(name))}</b>\n\n"
            f"{description}",
            reply_markup=keyboard,
            parse_mode="HTML"
        )


@dp.message(F.text == "📌 Loyihalar")
async def projects_uz(message: Message):

    await add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )

    await show_projects(
        message,
        "uz"
    )


@dp.message(F.text == "📌 Проекты")
async def projects_ru(message: Message):

    await add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )

    await show_projects(
        message,
        "ru"
    )


# =========================================================
# OVOZ BOSHLASH
# =========================================================


@dp.callback_query(
    F.data.startswith("vote_")
)
async def vote_start(
    callback: CallbackQuery
):

    try:
        project_id = int(
            callback.data.split("_", 1)[1]
        )

    except (ValueError, IndexError):

        await callback.answer(
            "❌ Xatolik.",
            show_alert=True
        )

        return

    project = await get_project(
        project_id
    )

    if not project:

        await callback.answer(
            "❌ Loyiha topilmadi.",
            show_alert=True
        )

        return

    user_id = callback.from_user.id

    waiting_for_phone[user_id] = project_id

    language = await get_language(
        user_id
    )

    if language == "ru":

        await callback.message.answer(
            f"🗳 <b>{escape(str(project[1]))}</b>\n\n"
            "Продолжите голосование, отправив "
            "свой номер телефона.",
            reply_markup=phone_keyboard_ru(),
            parse_mode="HTML"
        )

    else:

        await callback.message.answer(
            f"🗳 <b>{escape(str(project[1]))}</b>\n\n"
            "Ovoz berishni davom ettirish uchun "
            "telefon raqamingizni yuboring.",
            reply_markup=phone_keyboard_uz(),
            parse_mode="HTML"
        )

    await callback.answer()


# =========================================================
# TELEFON
# =========================================================


@dp.message(F.contact)
async def receive_phone(message: Message):

    user_id = message.from_user.id

    if user_id not in waiting_for_phone:

        await message.answer(
            "ℹ️ Hozir telefon raqami so‘ralmagan."
        )

        return

    contact = message.contact

    if (
        contact.user_id is not None
        and contact.user_id != user_id
    ):

        await message.answer(
            "❌ Iltimos, o‘zingizning telefon "
            "raqamingizni yuboring."
        )

        return

    project_id = waiting_for_phone.pop(
        user_id,
        None
    )

    if project_id is None:
        return

    await save_user_phone(
        user_id,
        contact.phone_number
    )

    project = await get_project(
        project_id
    )

    if not project:

        await message.answer(
            "❌ Loyiha topilmadi."
        )

        return

    language = await get_language(
        user_id
    )

    if language == "ru":

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔗 Голосовать",
                        url=project[2]
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="✅ Я проголосовал",
                        callback_data=(
                            f"confirm_vote_{project_id}"
                        )
                    )
                ]
            ]
        )

        await message.answer(
            f"✅ Номер принят.\n\n"
            f"📌 Проект: "
            f"<b>{escape(str(project[1]))}</b>\n\n"
            "1️⃣ Нажмите «Голосовать».\n"
            "2️⃣ Проголосуйте на странице проекта.\n"
            "3️⃣ Вернитесь в бот и нажмите "
            "«Я проголосовал».",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        await message.answer(
            "Главное меню:",
            reply_markup=ru_keyboard()
        )

    else:

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔗 Ovoz berish",
                        url=project[2]
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="✅ Ovoz berdim",
                        callback_data=(
                            f"confirm_vote_{project_id}"
                        )
                    )
                ]
            ]
        )

        await message.answer(
            f"✅ Telefon raqamingiz qabul qilindi.\n\n"
            f"📌 Loyiha: "
            f"<b>{escape(str(project[1]))}</b>\n\n"
            "1️⃣ «Ovoz berish» tugmasini bosing.\n"
            "2️⃣ Loyiha sahifasida ovoz bering.\n"
            "3️⃣ Botga qaytib, «Ovoz berdim» "
            "tugmasini bosing.",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        await message.answer(
            "Asosiy menyu:",
            reply_markup=uz_keyboard()
        )


# =========================================================
# OVOZ TASDIQLASH
# =========================================================


@dp.callback_query(
    F.data.startswith("confirm_vote_")
)
async def confirm_vote(
    callback: CallbackQuery
):

    try:
        project_id = int(
            callback.data.replace(
                "confirm_vote_",
                ""
            )
        )

    except ValueError:

        await callback.answer(
            "❌ Xatolik.",
            show_alert=True
        )

        return

    user_id = callback.from_user.id

    # Bir foydalanuvchining bir xil callbacklari
    # bir vaqtda ishlamasligi uchun lock.
    lock_key = f"vote:{user_id}:{project_id}"

    if lock_key not in callback_locks:
        callback_locks[lock_key] = asyncio.Lock()

    lock = callback_locks[lock_key]

    async with lock:

        status, project = await confirm_vote_db(
            user_id,
            project_id
        )

    callback_locks.pop(
        lock_key,
        None
    )

    if status == "not_found":

        await callback.answer(
            "❌ Loyiha topilmadi.",
            show_alert=True
        )

        return

    if status == "already":

        await callback.answer(
            "✅ Siz bu loyiha uchun ovoz "
            "berganingizni allaqachon tasdiqlagansiz.",
            show_alert=True
        )

        return

    language = await get_language(
        user_id
    )

    if language == "ru":

        await callback.message.answer(
            f"✅ <b>Голос подтверждён!</b>\n\n"
            f"📌 Проект: "
            f"<b>{escape(str(project[1]))}</b>\n\n"
            "Ваше подтверждение сохранено.",
            parse_mode="HTML",
            reply_markup=ru_keyboard()
        )

        await callback.answer(
            "✅ Голос подтверждён!"
        )

    else:

        await callback.message.answer(
            f"✅ <b>Ovoz tasdiqlandi!</b>\n\n"
            f"📌 Loyiha: "
            f"<b>{escape(str(project[1]))}</b>\n\n"
            "Sizning ovoz berganingiz haqidagi "
            "tasdiq saqlandi.",
            parse_mode="HTML",
            reply_markup=uz_keyboard()
        )

        await callback.answer(
            "✅ Ovoz tasdiqlandi!"
        )


# =========================================================
# BEKOR QILISH
# =========================================================


@dp.message(
    F.text.in_({
        "❌ Bekor qilish",
        "❌ Отмена"
    })
)
async def cancel_phone(message: Message):

    waiting_for_phone.pop(
        message.from_user.id,
        None
    )

    language = await get_language(
        message.from_user.id
    )

    if language == "ru":

        await message.answer(
            "❌ Голосование отменено.",
            reply_markup=ru_keyboard()
        )

    else:

        await message.answer(
            "❌ Ovoz berish bekor qilindi.",
            reply_markup=uz_keyboard()
        )


# =========================================================
# YANGILIKLAR
# =========================================================


async def show_news(
    message: Message,
    language="uz"
):

    news_list = await get_news()

    if not news_list:

        await message.answer(
            "📰 Hozircha yangiliklar yo‘q."
            if language == "uz"
            else
            "📰 Новостей пока нет."
        )

        return

    for news_id, text, photo_id in news_list:

        if photo_id:

            caption = text if text else None

            await message.answer_photo(
                photo=photo_id,
                caption=caption
            )

        elif text:

            prefix = (
                "📰 "
            )

            await message.answer(
                prefix + str(text)
            )


@dp.message(F.text == "📰 Yangiliklar")
async def news_uz(message: Message):

    await add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )

    await show_news(
        message,
        "uz"
    )


@dp.message(F.text == "📰 Новости")
async def news_ru(message: Message):

    await add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )

    await show_news(
        message,
        "ru"
    )


# =========================================================
# SAVOL-JAVOB
# =========================================================


@dp.message(F.text == "❓ Savol-javob")
async def question_answer_uz(
    message: Message
):

    await add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )

    question_waiting.add(
        message.from_user.id
    )

    await message.answer(
        "❓ <b>SAVOL-JAVOB</b>\n\n"
        "Savolingizni shu yerga yozib yuboring.\n\n"
        "✍️ Masalan:\n"
        "Ovoz berish qanday amalga oshiriladi?\n\n"
        "Bekor qilish uchun /start ni bosing.",
        parse_mode="HTML"
    )


@dp.message(F.text == "❓ Вопрос-ответ")
async def question_answer_ru(
    message: Message
):

    await add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )

    question_waiting.add(
        message.from_user.id
    )

    await message.answer(
        "❓ <b>ВОПРОС-ОТВЕТ</b>\n\n"
        "Напишите свой вопрос и отправьте его боту.",
        parse_mode="HTML"
    )


async def save_question(
    message: Message
):

    user_id = message.from_user.id

    if is_admin(user_id):
        return False

    if user_id not in question_waiting:
        return False

    if not message.text:
        return False

    text = message.text.strip()

    if not text:
        return True

    question_waiting.discard(
        user_id
    )

    question_id = await insert_question(
        user_id,
        text
    )

    username = (
        f"@{message.from_user.username}"
        if message.from_user.username
        else "Username yo‘q"
    )

    safe_name = escape(
        message.from_user.first_name or ""
    )

    safe_username = escape(
        username
    )

    safe_question = escape(
        text
    )

    for admin_id in ADMIN_IDS:

        try:

            await bot.send_message(
                admin_id,
                "❓ <b>YANGI SAVOL</b>\n\n"
                f"🆔 Savol ID: {question_id}\n"
                f"👤 Foydalanuvchi: {safe_name}\n"
                f"🔹 {safe_username}\n"
                f"🆔 User ID: {user_id}\n\n"
                f"💬 Savol:\n{safe_question}",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="💬 Javob berish",
                                callback_data=(
                                    f"answer_question_{question_id}"
                                )
                            )
                        ]
                    ]
                )
            )

        except Exception as e:

            logger.error(
                "Savolni adminga yuborishda xato: %s",
                e
            )

    await message.answer(
        "✅ Savolingiz qabul qilindi.\n\n"
        "Administrator javob berganidan keyin "
        "javob sizga yuboriladi."
    )

    return True


# =========================================================
# ADMIN SAVOLGA JAVOB
# =========================================================


@dp.callback_query(
    F.data.startswith("answer_question_")
)
async def answer_question_start(
    callback: CallbackQuery
):

    if not is_admin(
        callback.from_user.id
    ):

        await callback.answer(
            "⛔ Ruxsat yo‘q.",
            show_alert=True
        )

        return

    try:

        question_id = int(
            callback.data.replace(
                "answer_question_",
                ""
            )
        )

    except ValueError:

        await callback.answer(
            "❌ Xatolik.",
            show_alert=True
        )

        return

    question = await get_question(
        question_id
    )

    if not question:

        await callback.answer(
            "❌ Savol topilmadi.",
            show_alert=True
        )

        return

    if question[2] == 1:

        await callback.answer(
            "✅ Bu savolga allaqachon javob berilgan.",
            show_alert=True
        )

        return

    admin_answer_waiting[
        callback.from_user.id
    ] = question_id

    await callback.message.answer(
        f"💬 <b>SAVOLGA JAVOB</b>\n\n"
        f"🆔 Savol ID: {question_id}\n\n"
        f"❓ Savol:\n"
        f"{escape(str(question[1]))}\n\n"
        "✍️ Endi javobingizni yuboring.",
        parse_mode="HTML"
    )

    await callback.answer()


async def send_question_answer(
    message: Message
):

    admin_id = message.from_user.id

    if not is_admin(admin_id):
        return False

    if admin_id not in admin_answer_waiting:
        return False

    if not message.text:

        await message.answer(
            "❌ Javobni matn ko‘rinishida yuboring."
        )

        return True

    question_id = admin_answer_waiting.pop(
        admin_id
    )

    answer = message.text.strip()

    if not answer:

        await message.answer(
            "❌ Javob bo‘sh bo‘lmasligi kerak."
        )

        admin_answer_waiting[
            admin_id
        ] = question_id

        return True

    status, question = await answer_question(
        question_id,
        answer
    )

    if status == "not_found":

        await message.answer(
            "❌ Savol topilmadi.",
            reply_markup=admin_keyboard()
        )

        return True

    if status == "already":

        await message.answer(
            "⚠️ Bu savolga allaqachon javob berilgan.",
            reply_markup=admin_keyboard()
        )

        return True

    target_user_id = question[0]

    try:

        await bot.send_message(
            target_user_id,
            "💬 <b>Savolingizga javob keldi</b>\n\n"
            f"❓ Savolingiz:\n"
            f"{escape(str(question[1]))}\n\n"
            f"✅ Javob:\n"
            f"{escape(answer)}",
            parse_mode="HTML"
        )

        await message.answer(
            "✅ Javob foydalanuvchiga yuborildi.",
            reply_markup=admin_keyboard()
        )

    except TelegramForbiddenError:

        await message.answer(
            "⚠️ Javob saqlandi, lekin foydalanuvchi "
            "botni bloklagan.",
            reply_markup=admin_keyboard()
        )

    except Exception as e:

        logger.error(
            "Javob yuborish xatosi: %s",
            e
        )

        await message.answer(
            "⚠️ Javob bazaga saqlandi, "
            "lekin yuborishda xatolik bo‘ldi.",
            reply_markup=admin_keyboard()
        )

    return True


# =========================================================
# ADMIN PANEL
# =========================================================


@dp.message(Command("admin"))
async def admin_command(
    message: Message
):

    if not is_admin(
        message.from_user.id
    ):

        await message.answer(
            "⛔ Sizda admin huquqi yo‘q."
        )

        return

    clear_admin_state(
        message.from_user.id
    )

    await message.answer(
        "👨‍💼 <b>ADMIN PANEL</b>\n\n"
        "Kerakli bo‘limni tanlang.",
        reply_markup=admin_keyboard(),
        parse_mode="HTML"
    )


# =========================================================
# STATISTIKA
# =========================================================


@dp.message(F.text == "📊 Statistika")
async def statistics(
    message: Message
):

    if not is_admin(
        message.from_user.id
    ):
        return

    stats = await get_statistics()

    await message.answer(
        "📊 <b>STATISTIKA</b>\n\n"
        f"👥 Jami foydalanuvchilar: "
        f"{stats['total_users']}\n\n"
        f"📱 Telefon raqami yuborganlar: "
        f"{stats['phone_users']}\n\n"
        f"🗳 Jami ovoz tasdiqlari: "
        f"{stats['total_votes']}\n"
        f"✅ Ovoz berganlar: "
        f"{stats['voted_users']}\n"
        f"⏳ Ovozini tasdiqlamaganlar: "
        f"{stats['not_voted']}\n\n"
        f"📌 Loyihalar: "
        f"{stats['total_projects']}\n"
        f"📰 Yangiliklar: "
        f"{stats['total_news']}\n\n"
        f"❓ Jami savollar: "
        f"{stats['total_questions']}\n"
        f"💬 Javobsiz savollar: "
        f"{stats['unanswered']}",
        parse_mode="HTML"
    )


# =========================================================
# LOYIHA QO'SHISH
# =========================================================


@dp.message(F.text == "➕ Loyiha qo‘shish")
async def add_project_start(
    message: Message
):

    if not is_admin(
        message.from_user.id
    ):
        return

    user_id = message.from_user.id

    clear_admin_state(user_id)

    admin_project_waiting.add(
        user_id
    )

    await message.answer(
        "➕ <b>YANGI LOYIHA</b>\n\n"
        "1️⃣ Loyiha nomini yuboring.\n\n"
        "Masalan:\n"
        "1-maktab loyihasi",
        parse_mode="HTML"
    )


async def save_project(
    message: Message
):

    user_id = message.from_user.id

    if not is_admin(user_id):
        return False

    if user_id not in admin_project_waiting:
        return False

    if not message.text:

        await message.answer(
            "❌ Matn yuboring."
        )

        return True

    text = message.text.strip()

    if not text:
        return True

    if user_id not in admin_project_name:

        admin_project_name[
            user_id
        ] = text

        await message.answer(
            "✅ Loyiha nomi saqlandi.\n\n"
            "2️⃣ Endi loyiha havolasini yuboring.\n\n"
            "Masalan:\n"
            "https://example.com"
        )

        return True

    link = text

    if not link.startswith(
        ("http://", "https://")
    ):

        await message.answer(
            "❌ Havola noto‘g‘ri.\n\n"
            "http:// yoki https:// bilan "
            "boshlanishi kerak."
        )

        return True

    name = admin_project_name.pop(
        user_id
    )

    await insert_project(
        name,
        link
    )

    admin_project_waiting.discard(
        user_id
    )

    await message.answer(
        "✅ <b>LOYIHA SAQLANDI!</b>\n\n"
        f"📌 Nomi: {escape(name)}\n"
        f"🔗 Havola: {escape(link)}\n\n"
        "⚠️ Loyiha bazaga saqlandi.\n"
        "Admin o‘chirmaguncha yo‘qolmaydi.",
        reply_markup=admin_keyboard(),
        parse_mode="HTML"
    )

    return True


# =========================================================
# YANGILIK QO'SHISH
# =========================================================


@dp.message(F.text == "📰 Yangilik qo‘shish")
async def add_news_start(
    message: Message
):

    if not is_admin(
        message.from_user.id
    ):
        return

    user_id = message.from_user.id

    clear_admin_state(user_id)

    admin_news_waiting.add(
        user_id
    )

    await message.answer(
        "📰 <b>YANGILIK QO‘SHISH</b>\n\n"
        "📝 Matn yoki 🖼 rasm yuboring.\n\n"
        "Rasmga caption yozsangiz, "
        "caption ham saqlanadi.\n\n"
        "⚠️ Saqlangan yangilik admin o‘chirmaguncha "
        "yo‘qolmaydi.",
        parse_mode="HTML"
    )


async def save_news(
    message: Message
):

    user_id = message.from_user.id

    if not is_admin(user_id):
        return False

    if user_id not in admin_news_waiting:
        return False

    if message.photo:

        photo_id = message.photo[-1].file_id
        text = message.caption or ""

        await insert_news(
            text,
            photo_id
        )

        admin_news_waiting.discard(
            user_id
        )

        await message.answer(
            "✅ <b>YANGILIK SAQLANDI!</b>\n\n"
            "🖼 Rasm bazaga saqlandi.\n"
            "Admin o‘chirmaguncha saqlanadi.",
            reply_markup=admin_keyboard(),
            parse_mode="HTML"
        )

        return True

    if message.text and message.text.strip():

        text = message.text.strip()

        await insert_news(
            text,
            None
        )

        admin_news_waiting.discard(
            user_id
        )

        await message.answer(
            "✅ <b>YANGILIK SAQLANDI!</b>\n\n"
            "Admin o‘chirmaguncha yo‘qolmaydi.",
            reply_markup=admin_keyboard(),
            parse_mode="HTML"
        )

        return True

    await message.answer(
        "❌ Matn yoki rasm yuboring."
    )

    return True


# =========================================================
# ADMIN LOYIHALAR
# =========================================================


@dp.message(F.text == "📋 Loyihalar")
async def admin_projects(
    message: Message
):

    if not is_admin(
        message.from_user.id
    ):
        return

    projects = await get_projects()

    if not projects:

        await message.answer(
            "📋 Hozircha loyihalar yo‘q."
        )

        return

    text_parts = [
        "📋 <b>SAQLANGAN LOYIHALAR</b>\n"
    ]

    for project_id, name, link in projects:

        text_parts.append(
            f"🆔 ID: {project_id}\n"
            f"📌 {escape(str(name))}\n"
            f"🔗 {escape(str(link))}\n"
            "━━━━━━━━━━━━━━"
        )

    # Juda katta xabar yuborilmasligi uchun
    # 3500 belgidan bo'lib yuboramiz.
    current = ""

    for part in text_parts:

        if len(current) + len(part) + 2 > 3500:

            if current:
                await message.answer(
                    current,
                    parse_mode="HTML"
                )

            current = part

        else:

            if current:
                current += "\n\n"

            current += part

    if current:
        await message.answer(
            current,
            parse_mode="HTML"
        )


# =========================================================
# DELETE MENU
# =========================================================


@dp.message(F.text == "🗑 Ma'lumot o‘chirish")
async def delete_menu(
    message: Message
):

    if not is_admin(
        message.from_user.id
    ):
        return

    admin_delete_waiting.add(
        message.from_user.id
    )

    await message.answer(
        "🗑 <b>MA'LUMOT O‘CHIRISH</b>\n\n"
        "Nimani o‘chirmoqchisiz?",
        reply_markup=delete_keyboard(),
        parse_mode="HTML"
    )


# =========================================================
# DELETE PROJECT LIST
# =========================================================


@dp.callback_query(
    F.data == "delete_projects"
)
async def delete_projects_list(
    callback: CallbackQuery
):

    if not is_admin(
        callback.from_user.id
    ):

        await callback.answer(
            "⛔ Ruxsat yo‘q.",
            show_alert=True
        )

        return

    projects = await get_projects()

    if not projects:

        await callback.message.answer(
            "📌 O‘chiriladigan loyiha yo‘q."
        )

        await callback.answer()

        return

    buttons = []

    # Telegram callback keyboard juda katta bo'lib ketmasligi
    # uchun dastlabki 80 ta loyiha chiqariladi.
    for project_id, name, link in projects[:80]:

        title = str(name)

        if len(title) > 35:
            title = title[:35] + "..."

        buttons.append([
            InlineKeyboardButton(
                text=f"🗑 {project_id} — {title}",
                callback_data=(
                    f"del_project_{project_id}"
                )
            )
        ])

    await callback.message.answer(
        "🗑 O‘chirish uchun loyihani tanlang:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )

    if len(projects) > 80:

        await callback.message.answer(
            "ℹ️ 80 tadan ortiq loyiha mavjud. "
            "Keyingi versiyada sahifalash qo‘shish mumkin."
        )

    await callback.answer()


# =========================================================
# DELETE PROJECT
# =========================================================


@dp.callback_query(
    F.data.startswith("del_project_")
)
async def delete_project_handler(
    callback: CallbackQuery
):

    if not is_admin(
        callback.from_user.id
    ):

        await callback.answer(
            "⛔ Ruxsat yo‘q.",
            show_alert=True
        )

        return

    try:

        project_id = int(
            callback.data.replace(
                "del_project_",
                ""
            )
        )

    except ValueError:

        await callback.answer(
            "❌ Xatolik.",
            show_alert=True
        )

        return

    deleted = await delete_project(
        project_id
    )

    if deleted:

        await callback.message.answer(
            "✅ Loyiha o‘chirildi."
        )

        await callback.answer(
            "✅ O‘chirildi."
        )

    else:

        await callback.answer(
            "❌ Loyiha topilmadi.",
            show_alert=True
        )


# =========================================================
# DELETE NEWS LIST
# =========================================================


@dp.callback_query(
    F.data == "delete_news"
)
async def delete_news_list(
    callback: CallbackQuery
):

    if not is_admin(
        callback.from_user.id
    ):

        await callback.answer(
            "⛔ Ruxsat yo‘q.",
            show_alert=True
        )

        return

    news_list = await get_news()

    if not news_list:

        await callback.message.answer(
            "📰 O‘chiriladigan yangilik yo‘q."
        )

        await callback.answer()

        return

    buttons = []

    for news_id, text, photo_id in news_list[:80]:

        title = (
            str(text)[:30]
            if text
            else "🖼 Rasmli yangilik"
        )

        buttons.append([
            InlineKeyboardButton(
                text=f"🗑 {news_id} — {title}",
                callback_data=f"del_news_{news_id}"
            )
        ])

    await callback.message.answer(
        "🗑 O‘chirish uchun yangilikni tanlang:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )

    await callback.answer()


# =========================================================
# DELETE NEWS
# =========================================================


@dp.callback_query(
    F.data.startswith("del_news_")
)
async def delete_news_handler(
    callback: CallbackQuery
):

    if not is_admin(
        callback.from_user.id
    ):

        await callback.answer(
            "⛔ Ruxsat yo‘q.",
            show_alert=True
        )

        return

    try:

        news_id = int(
            callback.data.replace(
                "del_news_",
                ""
            )
        )

    except ValueError:

        await callback.answer(
            "❌ Xatolik.",
            show_alert=True
        )

        return

    deleted = await delete_news(
        news_id
    )

    if deleted:

        await callback.message.answer(
            "✅ Yangilik o‘chirildi."
        )

        await callback.answer(
            "✅ O‘chirildi."
        )

    else:

        await callback.answer(
            "❌ Yangilik topilmadi.",
            show_alert=True
        )


# =========================================================
# DELETE BACK
# =========================================================


@dp.callback_query(
    F.data == "delete_back"
)
async def delete_back(
    callback: CallbackQuery
):

    if not is_admin(
        callback.from_user.id
    ):

        await callback.answer(
            "⛔ Ruxsat yo‘q.",
            show_alert=True
        )

        return

    admin_delete_waiting.discard(
        callback.from_user.id
    )

    await callback.message.answer(
        "👨‍💼 Admin panel:",
        reply_markup=admin_keyboard()
    )

    await callback.answer()


# =========================================================
# BROADCAST BOSHLASH
# =========================================================


@dp.message(F.text == "📢 Ommaviy xabar")
async def broadcast_start(
    message: Message
):

    if not is_admin(
        message.from_user.id
    ):
        return

    user_id = message.from_user.id

    clear_admin_state(user_id)

    admin_broadcast_waiting.add(
        user_id
    )

    await message.answer(
        "📢 <b>OMMAVIY XABAR</b>\n\n"
        "Barcha foydalanuvchilarga yubormoqchi "
        "bo‘lgan xabaringizni yuboring.\n\n"
        "📝 Matn\n"
        "🖼 Rasm\n"
        "🎥 Video\n"
        "📄 Hujjat\n"
        "🎵 Audio\n"
        "🎤 Ovozli xabar",
        parse_mode="HTML"
    )


# =========================================================
# BROADCAST BITTA FOYDALANUVCHI
# =========================================================


async def broadcast_to_user(
    target_user_id,
    from_chat_id,
    message_id,
    semaphore
):

    async with semaphore:

        await asyncio.sleep(
            BROADCAST_DELAY
        )

        try:

            await bot.copy_message(
                chat_id=target_user_id,
                from_chat_id=from_chat_id,
                message_id=message_id
            )

            return "success"

        except TelegramRetryAfter as e:

            await asyncio.sleep(
                float(e.retry_after) + 0.5
            )

            try:

                await bot.copy_message(
                    chat_id=target_user_id,
                    from_chat_id=from_chat_id,
                    message_id=message_id
                )

                return "success"

            except TelegramForbiddenError:
                return "blocked"

            except Exception as retry_error:

                logger.warning(
                    "Broadcast retry xatosi %s: %s",
                    target_user_id,
                    retry_error
                )

                return "failed"

        except TelegramForbiddenError:

            return "blocked"

        except TelegramBadRequest as e:

            logger.warning(
                "Broadcast BadRequest %s: %s",
                target_user_id,
                e
            )

            return "failed"

        except (
            TelegramNetworkError,
            TelegramServerError
        ) as e:

            logger.warning(
                "Telegram vaqtinchalik xato %s: %s",
                target_user_id,
                e
            )

            await asyncio.sleep(1)

            try:

                await bot.copy_message(
                    chat_id=target_user_id,
                    from_chat_id=from_chat_id,
                    message_id=message_id
                )

                return "success"

            except TelegramForbiddenError:
                return "blocked"

            except Exception:
                return "failed"

        except Exception as e:

            logger.error(
                "Broadcast xatosi %s: %s",
                target_user_id,
                e
            )

            return "failed"


# =========================================================
# BROADCAST
# =========================================================


async def send_broadcast(
    message: Message
):

    user_id = message.from_user.id

    if not is_admin(user_id):
        return False

    if user_id not in admin_broadcast_waiting:
        return False

    admin_broadcast_waiting.discard(
        user_id
    )

    users = await get_all_user_ids()

    if not users:

        await message.answer(
            "❌ Foydalanuvchilar topilmadi.",
            reply_markup=admin_keyboard()
        )

        return True

    await message.answer(
        "⏳ <b>Ommaviy xabar yuborilmoqda...</b>\n\n"
        f"👥 Jami: {len(users)}\n\n"
        "Bot boshqa foydalanuvchilar uchun "
        "ishlashda davom etadi.",
        parse_mode="HTML"
    )

    semaphore = asyncio.Semaphore(
        BROADCAST_CONCURRENCY
    )

    tasks = [
        asyncio.create_task(
            broadcast_to_user(
                target_user_id,
                message.chat.id,
                message.message_id,
                semaphore
            )
        )
        for target_user_id in users
    ]

    results = await asyncio.gather(
        *tasks,
        return_exceptions=True
    )

    success = 0
    blocked = 0
    failed = 0

    blocked_ids = []

    for target_user_id, result in zip(
        users,
        results
    ):

        if result == "success":

            success += 1

        elif result == "blocked":

            blocked += 1
            blocked_ids.append(
                target_user_id
            )

        else:

            failed += 1

    # Bloklaganlarni bitta DB transactionda o'chiramiz.
    if blocked_ids:

        await db_write(
            _delete_users_bulk,
            blocked_ids
        )

    await message.answer(
        "✅ <b>OMMAVIY XABAR YAKUNLANDI</b>\n\n"
        f"📨 Muvaffaqiyatli: {success}\n"
        f"🚫 Bloklaganlar: {blocked}\n"
        f"❌ Xatolik: {failed}\n"
        f"👥 Jami: {len(users)}",
        reply_markup=admin_keyboard(),
        parse_mode="HTML"
    )

    return True


def _delete_users_bulk(
    user_ids
):
    if not user_ids:
        return

    conn = db_connect()

    try:

        conn.executemany(
            "DELETE FROM users WHERE user_id = ?",
            [
                (user_id,)
                for user_id in user_ids
            ]
        )

        conn.commit()

    finally:
        conn.close()


# =========================================================
# ADMIN PANELNI YOPISH
# =========================================================


@dp.message(
    F.text == "❌ Admin panelni yopish"
)
async def close_admin(
    message: Message
):

    if not is_admin(
        message.from_user.id
    ):
        return

    user_id = message.from_user.id

    clear_admin_state(user_id)

    waiting_for_phone.pop(
        user_id,
        None
    )

    language = await get_language(
        user_id
    )

    if language == "ru":

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
# OTHER MESSAGES
# =========================================================


@dp.message()
async def other_messages(
    message: Message
):

    # Admin savol javobi
    if await send_question_answer(message):
        return

    # Broadcast
    if await send_broadcast(message):
        return

    # Loyiha
    if await save_project(message):
        return

    # Yangilik
    if await save_news(message):
        return

    # Savol
    if await save_question(message):
        return


# =========================================================
# ERROR HANDLER
# =========================================================


@dp.error()
async def global_error(event):

    logger.exception(
        "Botda kutilmagan xatolik: %s",
        event.exception
    )


# =========================================================
# MAIN
# =========================================================


async def main():

    init_db()

    logger.info(
        "================================="
    )

    logger.info(
        "BOT ISHGA TUSHDI"
    )

    logger.info(
        "DATABASE: %s",
        DB_NAME
    )

    logger.info(
        "BROADCAST CONCURRENCY: %s",
        BROADCAST_CONCURRENCY
    )

    logger.info(
        "================================="
    )

    try:

        await dp.start_polling(
            bot,
            allowed_updates=(
                dp.resolve_used_update_types()
            )
        )

    finally:

        await bot.session.close()


# =========================================================
# START
# =========================================================


if __name__ == "__main__":

    try:

        asyncio.run(main())

    except KeyboardInterrupt:

        logger.info(
            "BOT TO‘XTATILDI"
        )