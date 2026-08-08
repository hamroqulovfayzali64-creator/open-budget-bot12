
import asyncio
import logging
import sqlite3
from pathlib import Path

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
)

# =========================================================
# SOZLAMALAR
# =========================================================

BOT_TOKEN = "8615736731:AAEfzzzWI-oPwjCtYG2raKE-ctqoLeHo1hY"

ADMIN_IDS = [
    7998053914,
]

BASE_DIR = Path(__file__).resolve().parent
DB_NAME = BASE_DIR / "bot.db"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# =========================================================
# DATABASE
# =========================================================

def db_connect():
    conn = sqlite3.connect(
        str(DB_NAME),
        timeout=30
    )

    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")

    return conn


def init_db():

    conn = db_connect()
    cursor = conn.cursor()

    # USERS
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

    # PROJECTS
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            link TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # NEWS
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT,
            photo_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # VOTES
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            project_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()

    # Eski users bazasini tekshirish
    cursor.execute("PRAGMA table_info(users)")
    user_columns = [row[1] for row in cursor.fetchall()]

    if "language" not in user_columns:
        cursor.execute(
            "ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'uz'"
        )

    if "phone" not in user_columns:
        cursor.execute(
            "ALTER TABLE users ADD COLUMN phone TEXT"
        )

    if "voted" not in user_columns:
        cursor.execute(
            "ALTER TABLE users ADD COLUMN voted INTEGER DEFAULT 0"
        )

    # Eski projects bazasida phone bo'lsa ham,
    # endi undan foydalanilmaydi.
    cursor.execute("PRAGMA table_info(projects)")
    project_columns = [row[1] for row in cursor.fetchall()]

    if "phone" in project_columns:
        logging.info(
            "Eski projects.phone ustuni mavjud. "
            "U endi ishlatilmaydi."
        )

    # NEWS ustunlari
    cursor.execute("PRAGMA table_info(news)")
    news_columns = [row[1] for row in cursor.fetchall()]

    if "photo_id" not in news_columns:
        cursor.execute(
            "ALTER TABLE news ADD COLUMN photo_id TEXT"
        )

    if "text" not in news_columns:
        cursor.execute(
            "ALTER TABLE news ADD COLUMN text TEXT"
        )

    conn.commit()
    conn.close()

    logging.info("DATABASE TAYYOR: %s", DB_NAME)


# =========================================================
# USER FUNKSIYALARI
# =========================================================

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

    cursor.execute("""
        UPDATE users
        SET username = ?,
            first_name = ?
        WHERE user_id = ?
    """, (
        username,
        first_name,
        user_id
    ))

    conn.commit()
    conn.close()


def set_language(user_id, language):

    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE users
        SET language = ?
        WHERE user_id = ?
    """, (
        language,
        user_id
    ))

    conn.commit()
    conn.close()


def get_language(user_id):

    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT language
        FROM users
        WHERE user_id = ?
    """, (user_id,))

    result = cursor.fetchone()

    conn.close()

    if result and result[0]:
        return result[0]

    return "uz"


def save_user_phone(user_id, phone):

    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE users
        SET phone = ?
        WHERE user_id = ?
    """, (
        phone,
        user_id
    ))

    conn.commit()
    conn.close()


def mark_voted(user_id, project_id):

    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE users
        SET voted = 1
        WHERE user_id = ?
    """, (user_id,))

    cursor.execute("""
        INSERT INTO votes
        (user_id, project_id)
        VALUES (?, ?)
    """, (
        user_id,
        project_id
    ))

    conn.commit()
    conn.close()


def delete_user(user_id):

    try:

        conn = db_connect()
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM users WHERE user_id = ?",
            (user_id,)
        )

        conn.commit()
        conn.close()

    except Exception as e:

        logging.error(
            "Foydalanuvchini o'chirish xatosi: %s",
            e
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
                KeyboardButton(text="📢 Ommaviy xabar")
            ],
            [
                KeyboardButton(text="📋 Loyihalar")
            ],
            [
                KeyboardButton(text="🗑 Ma'lumot o‘chirish")
            ],
            [
                KeyboardButton(text="❌ Admin panelni yopish")
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
                KeyboardButton(text="❌ Bekor qilish")
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
                KeyboardButton(text="❌ Отмена")
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )


# =========================================================
# HOLATLAR
# =========================================================

waiting_for_phone = {}

admin_project_waiting = set()
admin_project_name = {}
admin_project_link = {}

admin_news_waiting = set()

admin_broadcast_waiting = set()

admin_delete_waiting = set()


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
# LANGUAGE UZ
# =========================================================

@dp.callback_query(F.data == "lang_uz")
async def language_uz(callback: CallbackQuery):

    set_language(
        callback.from_user.id,
        "uz"
    )

    await callback.message.answer(
        "🇺🇿 O‘zbek tili tanlandi.",
        reply_markup=uz_keyboard()
    )

    await callback.answer()


# =========================================================
# LANGUAGE RU
# =========================================================

@dp.callback_query(F.data == "lang_ru")
async def language_ru(callback: CallbackQuery):

    set_language(
        callback.from_user.id,
        "ru"
    )

    await callback.message.answer(
        "🇷🇺 Русский язык выбран.",
        reply_markup=ru_keyboard()
    )

    await callback.answer()


# =========================================================
# LOYIHALAR UZ
# =========================================================

@dp.message(F.text == "📌 Loyihalar")
async def projects_uz(message: Message):

    add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )

    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, name, link
        FROM projects
        ORDER BY id DESC
    """)

    projects = cursor.fetchall()

    conn.close()

    if not projects:

        await message.answer(
            "📌 Hozircha loyihalar qo‘shilmagan."
        )

        return

    for project_id, name, link in projects:

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔗 Havolani ochish",
                        url=link
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🗳 Ovoz berish",
                        callback_data=f"vote_{project_id}"
                    )
                ]
            ]
        )

        await message.answer(
            f"📌 <b>{name}</b>\n\n"
            "Ovoz berish uchun quyidagi tugmani bosing.",
            reply_markup=keyboard,
            parse_mode="HTML"
        )


# =========================================================
# LOYIHALAR RU
# =========================================================

@dp.message(F.text == "📌 Проекты")
async def projects_ru(message: Message):

    add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )

    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, name, link
        FROM projects
        ORDER BY id DESC
    """)

    projects = cursor.fetchall()

    conn.close()

    if not projects:

        await message.answer(
            "📌 Пока проекты не добавлены."
        )

        return

    for project_id, name, link in projects:

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔗 Открыть ссылку",
                        url=link
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🗳 Голосовать",
                        callback_data=f"vote_{project_id}"
                    )
                ]
            ]
        )

        await message.answer(
            f"📌 <b>{name}</b>\n\n"
            "Для голосования нажмите кнопку ниже.",
            reply_markup=keyboard,
            parse_mode="HTML"
        )


# =========================================================
# OVOZ
# =========================================================

@dp.callback_query(F.data.startswith("vote_"))
async def vote_start(callback: CallbackQuery):

    try:

        project_id = int(
            callback.data.replace("vote_", "")
        )

    except ValueError:

        await callback.answer(
            "❌ Xatolik.",
            show_alert=True
        )

        return

    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, name, link
        FROM projects
        WHERE id = ?
    """, (project_id,))

    project = cursor.fetchone()

    conn.close()

    if not project:

        await callback.answer(
            "❌ Loyiha topilmadi.",
            show_alert=True
        )

        return

    waiting_for_phone[
        callback.from_user.id
    ] = project_id

    lang = get_language(
        callback.from_user.id
    )

    if lang == "ru":

        await callback.message.answer(
            f"🗳 <b>{project[1]}</b>\n\n"
            "Продолжите голосование, отправив "
            "свой номер телефона.",
            reply_markup=phone_keyboard_ru(),
            parse_mode="HTML"
        )

    else:

        await callback.message.answer(
            f"🗳 <b>{project[1]}</b>\n\n"
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

    if message.contact.user_id != user_id:

        await message.answer(
            "❌ Iltimos, o‘zingizning telefon "
            "raqamingizni yuboring."
        )

        return

    project_id = waiting_for_phone[user_id]

    phone = message.contact.phone_number

    save_user_phone(
        user_id,
        phone
    )

    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, name, link
        FROM projects
        WHERE id = ?
    """, (project_id,))

    project = cursor.fetchone()

    conn.close()

    if not project:

        waiting_for_phone.pop(
            user_id,
            None
        )

        await message.answer(
            "❌ Loyiha topilmadi."
        )

        return

    waiting_for_phone.pop(
        user_id,
        None
    )

    lang = get_language(user_id)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=(
                        "🔗 Ovoz berish"
                        if lang == "uz"
                        else "🔗 Голосовать"
                    ),
                    url=project[2]
                )
            ]
        ]
    )

    if lang == "ru":

        await message.answer(
            f"✅ Номер принят.\n\n"
            f"📌 Проект: <b>{project[1]}</b>\n\n"
            "Нажмите кнопку ниже для голосования.",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        await message.answer(
            "Главное меню:",
            reply_markup=ru_keyboard()
        )

    else:

        await message.answer(
            f"✅ Telefon raqamingiz qabul qilindi.\n\n"
            f"📌 Loyiha: <b>{project[1]}</b>\n\n"
            "Quyidagi tugma orqali ovoz berish "
            "sahifasiga o'ting.",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        await message.answer(
            "Asosiy menyu:",
            reply_markup=uz_keyboard()
        )


# =========================================================
# BEKOR
# =========================================================

@dp.message(
    F.text.in_({
        "❌ Bekor qilish",
        "❌ Отмена"
    })
)
async def cancel_phone(message: Message):

    user_id = message.from_user.id

    waiting_for_phone.pop(
        user_id,
        None
    )

    lang = get_language(user_id)

    if lang == "ru":

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
# YANGILIKLAR UZ
# =========================================================

@dp.message(F.text == "📰 Yangiliklar")
async def news_uz(message: Message):

    add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )

    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, text, photo_id
        FROM news
        ORDER BY id DESC
    """)

    news = cursor.fetchall()

    conn.close()

    if not news:

        await message.answer(
            "📰 Hozircha yangiliklar yo‘q."
        )

        return

    for news_id, text, photo_id in news:

        if photo_id:

            await message.answer_photo(
                photo=photo_id,
                caption=text if text else None
            )

        elif text:

            await message.answer(
                f"📰 {text}"
            )


# =========================================================
# YANGILIKLAR RU
# =========================================================

@dp.message(F.text == "📰 Новости")
async def news_ru(message: Message):

    add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )

    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, text, photo_id
        FROM news
        ORDER BY id DESC
    """)

    news = cursor.fetchall()

    conn.close()

    if not news:

        await message.answer(
            "📰 Новостей пока нет."
        )

        return

    for news_id, text, photo_id in news:

        if photo_id:

            await message.answer_photo(
                photo=photo_id,
                caption=text if text else None
            )

        elif text:

            await message.answer(
                f"📰 {text}"
            )


# =========================================================
# YORDAM
# =========================================================

@dp.message(F.text == "❓ Yordam")
async def help_uz(message: Message):

    await message.answer(
        "❓ Yordam\n\n"
        "📌 Loyihalar — loyihalarni ko‘rish\n"
        "📰 Yangiliklar — yangiliklarni ko‘rish\n"
        "🗳 Ovoz berish — loyiha uchun ovoz berish\n\n"
        "Muammo bo‘lsa, administratorga murojaat qiling."
    )


@dp.message(F.text == "❓ Помощь")
async def help_ru(message: Message):

    await message.answer(
        "❓ Помощь\n\n"
        "📌 Проекты — просмотр проектов\n"
        "📰 Новости — новости\n"
        "🗳 Голосование — голосование за проект\n\n"
        "При возникновении проблем обратитесь к администратору."
    )


# =========================================================
# ADMIN
# =========================================================

@dp.message(Command("admin"))
async def admin_command(message: Message):

    if not is_admin(message.from_user.id):

        await message.answer(
            "⛔ Sizda admin huquqi yo‘q."
        )

        return

    user_id = message.from_user.id

    admin_project_waiting.discard(user_id)
    admin_project_name.pop(user_id, None)
    admin_project_link.pop(user_id, None)
    admin_news_waiting.discard(user_id)
    admin_broadcast_waiting.discard(user_id)
    admin_delete_waiting.discard(user_id)

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
async def statistics(message: Message):

    if not is_admin(message.from_user.id):
        return

    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM users WHERE voted = 1"
    )
    voted_users = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM users WHERE voted = 0"
    )
    not_voted = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM projects")
    total_projects = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM news")
    total_news = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM votes")
    total_votes = cursor.fetchone()[0]

    conn.close()

    await message.answer(
        "📊 <b>STATISTIKA</b>\n\n"
        f"👥 Jami foydalanuvchilar: {total_users}\n"
        f"🗳 Ovozlar: {total_votes}\n"
        f"👤 Ovoz berganlar: {voted_users}\n"
        f"⏳ Ovoz bermaganlar: {not_voted}\n"
        f"📌 Loyihalar: {total_projects}\n"
        f"📰 Yangiliklar: {total_news}",
        parse_mode="HTML"
    )


# =========================================================
# LOYIHA QO'SHISH
# =========================================================

@dp.message(F.text == "➕ Loyiha qo‘shish")
async def add_project_start(message: Message):

    if not is_admin(message.from_user.id):
        return

    user_id = message.from_user.id

    admin_news_waiting.discard(user_id)
    admin_broadcast_waiting.discard(user_id)
    admin_delete_waiting.discard(user_id)

    admin_project_name.pop(user_id, None)
    admin_project_link.pop(user_id, None)

    admin_project_waiting.add(user_id)

    await message.answer(
        "➕ <b>YANGI LOYIHA</b>\n\n"
        "1️⃣ Loyiha nomini yuboring.\n\n"
        "Masalan:\n"
        "1-maktab loyihasi",
        parse_mode="HTML"
    )


# =========================================================
# LOYIHA SAQLASH
# =========================================================

async def save_project(message: Message):

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

    # 1. NOM
    if user_id not in admin_project_name:

        admin_project_name[user_id] = text

        await message.answer(
            "✅ Loyiha nomi saqlandi.\n\n"
            "2️⃣ Endi loyiha havolasini yuboring.\n\n"
            "Masalan:\n"
            "https://example.com"
        )

        return True

    # 2. HAVOLA
    if user_id not in admin_project_link:

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

        admin_project_link[user_id] = link

        # MUHIM:
        # Endi telefon raqami so'ralmaydi.
        # Loyiha darhol bazaga saqlanadi.

        name = admin_project_name[user_id]

        conn = db_connect()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO projects
            (name, link)
            VALUES (?, ?)
        """, (
            name,
            link
        ))

        conn.commit()
        conn.close()

        admin_project_waiting.discard(user_id)
        admin_project_name.pop(user_id, None)
        admin_project_link.pop(user_id, None)

        await message.answer(
            "✅ <b>LOYIHA SAQLANDI!</b>\n\n"
            f"📌 Nomi: {name}\n"
            f"🔗 Havola: {link}\n\n"
            "⚠️ Loyiha bazaga saqlandi.\n"
            "Admin o‘chirmaguncha yo‘qolmaydi.",
            reply_markup=admin_keyboard(),
            parse_mode="HTML"
        )

        return True

    return True


# =========================================================
# YANGILIK QO'SHISH
# =========================================================

@dp.message(F.text == "📰 Yangilik qo‘shish")
async def add_news_start(message: Message):

    if not is_admin(message.from_user.id):
        return

    user_id = message.from_user.id

    admin_project_waiting.discard(user_id)
    admin_project_name.pop(user_id, None)
    admin_project_link.pop(user_id, None)

    admin_broadcast_waiting.discard(user_id)
    admin_delete_waiting.discard(user_id)

    admin_news_waiting.add(user_id)

    await message.answer(
        "📰 <b>YANGILIK QO‘SHISH</b>\n\n"
        "📝 Matn yoki 🖼 rasm yuboring.\n\n"
        "Rasmga caption yozsangiz, "
        "caption ham saqlanadi.\n\n"
        "⚠️ Saqlangan yangilik admin o‘chirmaguncha "
        "yo‘qolmaydi.",
        parse_mode="HTML"
    )


# =========================================================
# YANGILIK SAQLASH
# =========================================================

async def save_news(message: Message):

    user_id = message.from_user.id

    if not is_admin(user_id):
        return False

    if user_id not in admin_news_waiting:
        return False

    if message.photo:

        photo_id = message.photo[-1].file_id
        text = message.caption or ""

        conn = db_connect()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO news
            (text, photo_id)
            VALUES (?, ?)
        """, (
            text,
            photo_id
        ))

        conn.commit()
        conn.close()

        admin_news_waiting.discard(user_id)

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

        conn = db_connect()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO news
            (text, photo_id)
            VALUES (?, NULL)
        """, (text,))

        conn.commit()
        conn.close()

        admin_news_waiting.discard(user_id)

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
async def admin_projects(message: Message):

    if not is_admin(message.from_user.id):
        return

    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, name, link
        FROM projects
        ORDER BY id DESC
    """)

    projects = cursor.fetchall()

    conn.close()

    if not projects:

        await message.answer(
            "📋 Hozircha loyihalar yo‘q."
        )

        return

    text = "📋 <b>SAQLANGAN LOYIHALAR</b>\n\n"

    for project_id, name, link in projects:

        text += (
            f"🆔 ID: {project_id}\n"
            f"📌 {name}\n"
            f"🔗 {link}\n"
            "━━━━━━━━━━━━━━\n"
        )

    await message.answer(
        text,
        parse_mode="HTML"
    )


# =========================================================
# MA'LUMOT O'CHIRISH
# =========================================================

@dp.message(F.text == "🗑 Ma'lumot o‘chirish")
async def delete_menu(message: Message):

    if not is_admin(message.from_user.id):
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
# LOYIHA O'CHIRISH RO'YXATI
# =========================================================

@dp.callback_query(F.data == "delete_projects")
async def delete_projects_list(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):
        await callback.answer(
            "⛔ Ruxsat yo‘q.",
            show_alert=True
        )
        return

    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, name
        FROM projects
        ORDER BY id DESC
    """)

    projects = cursor.fetchall()

    conn.close()

    if not projects:

        await callback.message.answer(
            "📌 O‘chiriladigan loyiha yo‘q."
        )

        await callback.answer()
        return

    buttons = []

    for project_id, name in projects:

        buttons.append([
            InlineKeyboardButton(
                text=f"🗑 {project_id} — {name}",
                callback_data=f"del_project_{project_id}"
            )
        ])

    await callback.message.answer(
        "🗑 O‘chirish uchun loyihani tanlang:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )

    await callback.answer()


# =========================================================
# LOYIHA O'CHIRISH
# =========================================================

@dp.callback_query(F.data.startswith("del_project_"))
async def delete_project(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):
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

    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM projects WHERE id = ?",
        (project_id,)
    )

    deleted = cursor.rowcount

    conn.commit()
    conn.close()

    if deleted:

        await callback.message.answer(
            "✅ Loyiha o‘chirildi."
        )

    else:

        await callback.message.answer(
            "❌ Loyiha topilmadi."
        )

    await callback.answer()


# =========================================================
# YANGILIK O'CHIRISH RO'YXATI
# =========================================================

@dp.callback_query(F.data == "delete_news")
async def delete_news_list(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):
        await callback.answer(
            "⛔ Ruxsat yo‘q.",
            show_alert=True
        )
        return

    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, text
        FROM news
        ORDER BY id DESC
    """)

    news = cursor.fetchall()

    conn.close()

    if not news:

        await callback.message.answer(
            "📰 O‘chiriladigan yangilik yo‘q."
        )

        await callback.answer()
        return

    buttons = []

    for news_id, text in news:

        title = text[:35] if text else "🖼 Rasmli yangilik"

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
# YANGILIK O'CHIRISH
# =========================================================

@dp.callback_query(F.data.startswith("del_news_"))
async def delete_news(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):
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

    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM news WHERE id = ?",
        (news_id,)
    )

    deleted = cursor.rowcount

    conn.commit()
    conn.close()

    if deleted:

        await callback.message.answer(
            "✅ Yangilik o‘chirildi."
        )

    else:

        await callback.message.answer(
            "❌ Yangilik topilmadi."
        )

    await callback.answer()


# =========================================================
# DELETE BACK
# =========================================================

@dp.callback_query(F.data == "delete_back")
async def delete_back(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):
        await callback.answer(
            "⛔ Ruxsat yo‘q.",
            show_alert=True
        )
        return

    await callback.message.answer(
        "👨‍💼 Admin panel:",
        reply_markup=admin_keyboard()
    )

    await callback.answer()


# =========================================================
# OMMAVIY XABAR
# =========================================================

@dp.message(F.text == "📢 Ommaviy xabar")
async def broadcast_start(message: Message):

    if not is_admin(message.from_user.id):
        return

    user_id = message.from_user.id

    admin_project_waiting.discard(user_id)
    admin_project_name.pop(user_id, None)
    admin_project_link.pop(user_id, None)
    admin_news_waiting.discard(user_id)
    admin_delete_waiting.discard(user_id)

    admin_broadcast_waiting.add(user_id)

    await message.answer(
        "📢 <b>OMMAVIY XABAR</b>\n\n"
        "Barcha foydalanuvchilarga yubormoqchi "
        "bo‘lgan xabaringizni yuboring.\n\n"
        "📝 Matn\n"
        "🖼 Rasm\n"
        "🎥 Video\n"
        "📄 Hujjat",
        parse_mode="HTML"
    )


# =========================================================
# OMMAVIY XABAR YUBORISH
# =========================================================

async def send_broadcast(message: Message):

    user_id = message.from_user.id

    if not is_admin(user_id):
        return False

    if user_id not in admin_broadcast_waiting:
        return False

    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT user_id FROM users"
    )

    users = cursor.fetchall()

    conn.close()

    if not users:

        admin_broadcast_waiting.discard(user_id)

        await message.answer(
            "❌ Foydalanuvchilar topilmadi.",
            reply_markup=admin_keyboard()
        )

        return True

    await message.answer(
        "⏳ Xabar yuborilmoqda..."
    )

    success = 0
    blocked = 0
    failed = 0

    for row in users:

        target_user_id = row[0]

        try:

            await bot.copy_message(
                chat_id=target_user_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )

            success += 1

            await asyncio.sleep(0.05)

        except TelegramRetryAfter as e:

            await asyncio.sleep(
                e.retry_after
            )

            try:

                await bot.copy_message(
                    chat_id=target_user_id,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id
                )

                success += 1

            except Exception as e2:

                logging.error(
                    "Retry xatosi %s: %s",
                    target_user_id,
                    e2
                )

                failed += 1

        except TelegramForbiddenError:

            blocked += 1

            delete_user(
                target_user_id
            )

        except TelegramBadRequest as e:

            logging.error(
                "TelegramBadRequest %s: %s",
                target_user_id,
                e
            )

            failed += 1

        except Exception as e:

            logging.error(
                "Xabar yuborish xatosi %s: %s",
                target_user_id,
                e
            )

            failed += 1

    admin_broadcast_waiting.discard(user_id)

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


# =========================================================
# ADMIN PANELNI YOPISH
# =========================================================

@dp.message(F.text == "❌ Admin panelni yopish")
async def close_admin(message: Message):

    if not is_admin(message.from_user.id):
        return

    user_id = message.from_user.id

    admin_project_waiting.discard(user_id)
    admin_project_name.pop(user_id, None)
    admin_project_link.pop(user_id, None)
    admin_news_waiting.discard(user_id)
    admin_broadcast_waiting.discard(user_id)
    admin_delete_waiting.discard(user_id)

    lang = get_language(user_id)

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
# BOSHQA XABARLAR
# =========================================================

@dp.message()
async def other_messages(message: Message):

    if await send_broadcast(message):
        return

    if await save_project(message):
        return

    if await save_news(message):
        return


# =========================================================
# ERROR HANDLER
# =========================================================

@dp.error()
async def global_error(event):

    logging.exception(
        "Botda kutilmagan xatolik: %s",
        event.exception
    )


# =========================================================
# MAIN
# =========================================================

async def main():

    init_db()

    print("=================================")
    print("BOT ISHGA TUSHDI")
    print(f"DATABASE: {DB_NAME}")
    print("=================================")

    try:

        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types()
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

        print("BOT TO‘XTATILDI")