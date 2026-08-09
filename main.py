import asyncio
import logging
import os
import sqlite3
from pathlib import Path
from contextlib import closing
from html import escape
from urllib.parse import urlparse

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
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import (
    TelegramForbiddenError,
    TelegramBadRequest,
    TelegramRetryAfter,
)

# =========================================================
# SOZLAMALAR
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

ADMIN_IDS = set()

admin_ids_text = os.getenv("ADMIN_IDS", "").strip()

if admin_ids_text:
    for item in admin_ids_text.replace(";", ",").split(","):
        item = item.strip()
        if item.isdigit():
            ADMIN_IDS.add(int(item))

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "bot.db"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN topilmadi. Railway Variables ichida BOT_TOKEN qo'shing."
    )

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# =========================================================
# MATNLAR
# =========================================================

TEXTS = {
    "uz": {
        "welcome": (
            "Assalomu alaykum, {name}! 👋\n\n"
            "Botimizga xush kelibsiz.\n"
            "Kerakli bo'limni tanlang:"
        ),
        "projects": "📌 Loyihalar",
        "news": "📰 Yangiliklar",
        "help": "❓ Yordam",
        "language": "🌐 Til",

        "statistics": "📊 Statistika",
        "add_project": "➕ Loyiha qo'shish",
        "add_news": "📰 Yangilik qo'shish",
        "broadcast": "📢 Reklama tarqatish",
        "back": "🔙 Orqaga",

        "select_language": "🌐 Tilni tanlang:",
        "language_saved": "✅ Til muvaffaqiyatli o'zgartirildi.",

        "select_project": "📌 Loyihalardan birini tanlang:",
        "no_projects": "📌 Hozircha loyihalar mavjud emas.",

        "project_name": "📝 Loyiha nomini yuboring:",
        "project_link": (
            "🔗 Endi loyiha havolasini yuboring.\n\n"
            "Masalan:\n"
            "https://example.com"
        ),

        "project_created": "✅ Loyiha muvaffaqiyatli qo'shildi!",

        "invalid_link": (
            "❌ Havola noto'g'ri.\n\n"
            "Havola http:// yoki https:// bilan boshlanishi kerak."
        ),

        "open_project": "🔗 Loyihani ochish",
        "vote": "🗳 Ovoz berish",

        "project_not_found": "❌ Loyiha topilmadi.",

        "phone_required": (
            "🗳 Ovoz berish uchun telefon raqamingiz kerak.\n\n"
            "Quyidagi tugmani bosing. Telefon raqamingiz "
            "faqat sizning roziligingiz bilan Telegram orqali yuboriladi."
        ),

        "send_phone": "📱 Telefon raqamimni yuborish",
        "cancel": "❌ Bekor qilish",

        "phone_received": "✅ Telefon raqamingiz qabul qilindi.",
        "vote_success": "🎉 Ovoz berishingiz muvaffaqiyatli qabul qilindi!",
        "already_voted": "⚠️ Siz bu loyihaga allaqachon ovoz bergansiz.",

        "own_phone_only": (
            "❌ Iltimos, o'zingizning telefon raqamingizni yuboring."
        ),

        "help_text": (
            "❓ Yordam\n\n"
            "📌 Loyihalar — mavjud loyihalarni ko'rish.\n"
            "🗳 Ovoz berish — loyiha uchun ovoz berish.\n"
            "📰 Yangiliklar — so'nggi yangiliklarni ko'rish.\n"
            "🌐 Til — tilni almashtirish.\n\n"
            "Telefon raqami faqat sizning roziligingiz bilan olinadi."
        ),

        "news_empty": "📰 Hozircha yangiliklar mavjud emas.",

        "admin_only": "❌ Bu bo'lim faqat administratorlar uchun.",
        "admin_panel": "⚙️ Admin panel",

        "send_news": (
            "📰 Yangilik uchun rasm, video yoki matn yuboring.\n\n"
            "Rasm yuborsangiz caption ham qo'shishingiz mumkin."
        ),

        "news_saved": (
            "✅ Yangilik saqlandi va foydalanuvchilarga yuborildi."
        ),

        "send_broadcast": (
            "📢 Barcha foydalanuvchilarga yuboriladigan xabarni yuboring.\n\n"
            "Matn, rasm, video, hujjat yoki boshqa Telegram xabarini yuborishingiz mumkin."
        ),

        "broadcast_finished": "✅ Tarqatish yakunlandi.",
        "cancelled": "❌ Bekor qilindi.",

        "stats": (
            "📊 Statistika\n\n"
            "👥 Foydalanuvchilar: {users}\n"
            "🗳 Jami ovozlar: {votes}\n"
            "👁 Loyiha ko'rishlari: {views}\n"
            "📌 Loyihalar soni: {projects}\n"
            "📰 Yangiliklar soni: {news}"
        ),

        "unknown": "❗ Iltimos, menyudagi tugmalardan foydalaning.",

        "project_invalid_name": "❌ Loyiha nomi juda qisqa.",

        "broadcast_result": (
            "📢 Tarqatish tugadi.\n\n"
            "✅ Yuborildi: {success}\n"
            "🚫 Botni bloklagan: {blocked}\n"
            "⚠️ Xatolik: {failed}"
        ),
    },

    "ru": {
        "welcome": (
            "Здравствуйте, {name}! 👋\n\n"
            "Добро пожаловать в нашего бота.\n"
            "Выберите нужный раздел:"
        ),
        "projects": "📌 Проекты",
        "news": "📰 Новости",
        "help": "❓ Помощь",
        "language": "🌐 Язык",

        "statistics": "📊 Статистика",
        "add_project": "➕ Добавить проект",
        "add_news": "📰 Добавить новость",
        "broadcast": "📢 Рассылка",
        "back": "🔙 Назад",

        "select_language": "🌐 Выберите язык:",
        "language_saved": "✅ Язык успешно изменён.",

        "select_project": "📌 Выберите проект:",
        "no_projects": "📌 Пока проектов нет.",

        "project_name": "📝 Отправьте название проекта:",
        "project_link": (
            "🔗 Теперь отправьте ссылку проекта.\n\n"
            "Например:\n"
            "https://example.com"
        ),

        "project_created": "✅ Проект успешно добавлен!",

        "invalid_link": (
            "❌ Неверная ссылка.\n\n"
            "Ссылка должна начинаться с http:// или https://."
        ),

        "open_project": "🔗 Открыть проект",
        "vote": "🗳 Голосовать",

        "project_not_found": "❌ Проект не найден.",

        "phone_required": (
            "🗳 Для голосования необходим номер телефона.\n\n"
            "Нажмите кнопку ниже. Telegram отправит номер "
            "только после вашего согласия."
        ),

        "send_phone": "📱 Отправить мой номер",
        "cancel": "❌ Отмена",

        "phone_received": "✅ Номер телефона получен.",
        "vote_success": "🎉 Ваш голос успешно принят!",
        "already_voted": "⚠️ Вы уже голосовали за этот проект.",

        "own_phone_only": (
            "❌ Пожалуйста, отправьте свой номер телефона."
        ),

        "help_text": (
            "❓ Помощь\n\n"
            "📌 Проекты — просмотр проектов.\n"
            "🗳 Голосовать — голосование за проект.\n"
            "📰 Новости — последние новости.\n"
            "🌐 Язык — смена языка.\n\n"
            "Номер телефона запрашивается только с вашего согласия."
        ),

        "news_empty": "📰 Пока новостей нет.",

        "admin_only": "❌ Этот раздел доступен только администраторам.",
        "admin_panel": "⚙️ Админ-панель",

        "send_news": (
            "📰 Отправьте фото, видео или текст новости.\n\n"
            "Если отправляете фото, можно добавить caption."
        ),

        "news_saved": (
            "✅ Новость сохранена и отправлена пользователям."
        ),

        "send_broadcast": (
            "📢 Отправьте сообщение для всех пользователей.\n\n"
            "Можно отправить текст, фото, видео, документ или другое сообщение Telegram."
        ),

        "broadcast_finished": "✅ Рассылка завершена.",
        "cancelled": "❌ Отменено.",

        "stats": (
            "📊 Статистика\n\n"
            "👥 Пользователи: {users}\n"
            "🗳 Всего голосов: {votes}\n"
            "👁 Просмотров проектов: {views}\n"
            "📌 Проектов: {projects}\n"
            "📰 Новостей: {news}"
        ),

        "unknown": "❗ Пожалуйста, используйте кнопки меню.",

        "project_invalid_name": (
            "❌ Название проекта слишком короткое."
        ),

        "broadcast_result": (
            "📢 Рассылка завершена.\n\n"
            "✅ Отправлено: {success}\n"
            "🚫 Заблокировали бота: {blocked}\n"
            "⚠️ Ошибок: {failed}"
        ),
    },
}


# =========================================================
# FSM
# =========================================================

class ProjectStates(StatesGroup):
    waiting_name = State()
    waiting_link = State()


class NewsStates(StatesGroup):
    waiting_content = State()


class BroadcastStates(StatesGroup):
    waiting_content = State()


class VoteStates(StatesGroup):
    waiting_phone = State()


# =========================================================
# DATABASE
# =========================================================

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def get_columns(db, table_name):
    cursor = db.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row["name"] for row in cursor.fetchall()}


def add_column_if_missing(
    db,
    table_name,
    column_name,
    definition
):
    columns = get_columns(db, table_name)

    if column_name not in columns:
        db.execute(
            f"ALTER TABLE {table_name} "
            f"ADD COLUMN {column_name} {definition}"
        )

        logger.info(
            "Database migration: %s.%s qo'shildi.",
            table_name,
            column_name
        )


def init_db():
    with closing(get_db()) as db:
        cursor = db.cursor()

        # USERS
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                language TEXT DEFAULT 'uz',
                phone TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        add_column_if_missing(
            db,
            "users",
            "username",
            "TEXT"
        )

        add_column_if_missing(
            db,
            "users",
            "first_name",
            "TEXT"
        )

        add_column_if_missing(
            db,
            "users",
            "language",
            "TEXT DEFAULT 'uz'"
        )

        add_column_if_missing(
            db,
            "users",
            "phone",
            "TEXT"
        )

        add_column_if_missing(
            db,
            "users",
            "created_at",
            "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        )

        # PROJECTS
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name_uz TEXT DEFAULT '',
                name_ru TEXT DEFAULT '',
                url TEXT DEFAULT '',
                click_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        add_column_if_missing(
            db,
            "projects",
            "name_uz",
            "TEXT DEFAULT ''"
        )

        add_column_if_missing(
            db,
            "projects",
            "name_ru",
            "TEXT DEFAULT ''"
        )

        add_column_if_missing(
            db,
            "projects",
            "url",
            "TEXT DEFAULT ''"
        )

        add_column_if_missing(
            db,
            "projects",
            "click_count",
            "INTEGER DEFAULT 0"
        )

        add_column_if_missing(
            db,
            "projects",
            "created_at",
            "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        )

        # Eski database'dagi ustunlarni yangi ustunlarga o'tkazish
        project_columns = get_columns(db, "projects")

        if "nomi" in project_columns:
            db.execute("""
                UPDATE projects
                SET name_uz = nomi
                WHERE
                    (name_uz IS NULL OR name_uz = '')
                    AND nomi IS NOT NULL
            """)

            db.execute("""
                UPDATE projects
                SET name_ru = nomi
                WHERE
                    (name_ru IS NULL OR name_ru = '')
                    AND nomi IS NOT NULL
            """)

        if "havola" in project_columns:
            db.execute("""
                UPDATE projects
                SET url = havola
                WHERE
                    (url IS NULL OR url = '')
                    AND havola IS NOT NULL
            """)

        if "name" in project_columns:
            db.execute("""
                UPDATE projects
                SET name_uz = name
                WHERE
                    (name_uz IS NULL OR name_uz = '')
                    AND name IS NOT NULL
            """)

            db.execute("""
                UPDATE projects
                SET name_ru = name
                WHERE
                    (name_ru IS NULL OR name_ru = '')
                    AND name IS NOT NULL
            """)

        # VOTES
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                project_id INTEGER NOT NULL,
                phone TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, project_id)
            )
        """)

        add_column_if_missing(
            db,
            "votes",
            "phone",
            "TEXT"
        )

        add_column_if_missing(
            db,
            "votes",
            "created_at",
            "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        )

        # NEWS
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER,
                chat_id INTEGER,
                text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        add_column_if_missing(
            db,
            "news",
            "message_id",
            "INTEGER"
        )

        add_column_if_missing(
            db,
            "news",
            "chat_id",
            "INTEGER"
        )

        add_column_if_missing(
            db,
            "news",
            "text",
            "TEXT"
        )

        add_column_if_missing(
            db,
            "news",
            "created_at",
            "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        )

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_votes_user_project
            ON votes(user_id, project_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_news_created
            ON news(id DESC)
        """)

        db.commit()

    logger.info("Database tayyor: %s", DB_PATH)


# =========================================================
# USER FUNKSIYALARI
# =========================================================

def add_or_update_user(message: Message):
    if not message.from_user:
        return

    user = message.from_user

    with closing(get_db()) as db:
        cursor = db.cursor()

        cursor.execute(
            "SELECT user_id FROM users WHERE user_id = ?",
            (user.id,)
        )

        exists = cursor.fetchone()

        if exists:
            cursor.execute("""
                UPDATE users
                SET username = ?,
                    first_name = ?
                WHERE user_id = ?
            """, (
                user.username,
                user.first_name,
                user.id
            ))

        else:
            cursor.execute("""
                INSERT INTO users (
                    user_id,
                    username,
                    first_name,
                    language
                )
                VALUES (?, ?, ?, 'uz')
            """, (
                user.id,
                user.username,
                user.first_name
            ))

        db.commit()


def get_language(user_id: int):
    with closing(get_db()) as db:
        cursor = db.cursor()

        cursor.execute("""
            SELECT language
            FROM users
            WHERE user_id = ?
        """, (user_id,))

        row = cursor.fetchone()

        if row and row["language"] in ("uz", "ru"):
            return row["language"]

    return "uz"


def set_language(user_id: int, language: str):
    if language not in ("uz", "ru"):
        return

    with closing(get_db()) as db:
        db.execute("""
            UPDATE users
            SET language = ?
            WHERE user_id = ?
        """, (
            language,
            user_id
        ))

        db.commit()


def save_phone(user_id: int, phone: str):
    with closing(get_db()) as db:
        db.execute("""
            UPDATE users
            SET phone = ?
            WHERE user_id = ?
        """, (
            phone,
            user_id
        ))

        db.commit()


def is_admin(user_id: int):
    return user_id in ADMIN_IDS


def remove_user(user_id: int):
    with closing(get_db()) as db:
        db.execute(
            "DELETE FROM users WHERE user_id = ?",
            (user_id,)
        )

        db.commit()


# =========================================================
# KEYBOARDS
# =========================================================

def user_keyboard(language="uz"):
    t = TEXTS[language]

    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=t["projects"]),
                KeyboardButton(text=t["news"]),
            ],
            [
                KeyboardButton(text=t["help"]),
                KeyboardButton(text=t["language"]),
            ],
        ],
        resize_keyboard=True
    )


def admin_keyboard(language="uz"):
    t = TEXTS[language]

    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=t["statistics"])
            ],
            [
                KeyboardButton(text=t["add_project"]),
                KeyboardButton(text=t["add_news"]),
            ],
            [
                KeyboardButton(text=t["broadcast"])
            ],
            [
                KeyboardButton(text=t["back"])
            ],
        ],
        resize_keyboard=True
    )


def language_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🇺🇿 O‘zbek"),
                KeyboardButton(text="🇷🇺 Русский"),
            ],
            [
                KeyboardButton(text="🔙 Orqaga")
            ],
        ],
        resize_keyboard=True
    )


def phone_keyboard(language="uz"):
    t = TEXTS[language]

    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text=t["send_phone"],
                    request_contact=True
                )
            ],
            [
                KeyboardButton(text=t["cancel"])
            ],
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )


# =========================================================
# START
# =========================================================

@dp.message(CommandStart())
async def start_handler(
    message: Message,
    state: FSMContext
):
    await state.clear()

    add_or_update_user(message)

    language = get_language(
        message.from_user.id
    )

    await message.answer(
        TEXTS[language]["welcome"].format(
            name=message.from_user.first_name
            or "foydalanuvchi"
        ),
        reply_markup=user_keyboard(language)
    )


# =========================================================
# LANGUAGE
# =========================================================

@dp.message(F.text.in_({
    "🌐 Til",
    "🌐 Язык"
}))
async def language_handler(message: Message):
    add_or_update_user(message)

    language = get_language(
        message.from_user.id
    )

    await message.answer(
        TEXTS[language]["select_language"],
        reply_markup=language_keyboard()
    )


@dp.message(F.text == "🇺🇿 O‘zbek")
async def uz_language(message: Message):
    add_or_update_user(message)

    set_language(
        message.from_user.id,
        "uz"
    )

    await message.answer(
        TEXTS["uz"]["language_saved"],
        reply_markup=user_keyboard("uz")
    )


@dp.message(F.text == "🇷🇺 Русский")
async def ru_language(message: Message):
    add_or_update_user(message)

    set_language(
        message.from_user.id,
        "ru"
    )

    await message.answer(
        TEXTS["ru"]["language_saved"],
        reply_markup=user_keyboard("ru")
    )


# =========================================================
# PROJECTS
# =========================================================

@dp.message(F.text.in_({
    "📌 Loyihalar",
    "📌 Проекты"
}))
async def projects_handler(message: Message):
    add_or_update_user(message)

    language = get_language(
        message.from_user.id
    )

    t = TEXTS[language]

    with closing(get_db()) as db:
        cursor = db.cursor()

        cursor.execute("""
            SELECT
                id,
                name_uz,
                name_ru,
                url
            FROM projects
            WHERE
                COALESCE(name_uz, '') != ''
                OR COALESCE(name_ru, '') != ''
            ORDER BY id DESC
        """)

        projects = cursor.fetchall()

    if not projects:
        await message.answer(
            t["no_projects"],
            reply_markup=user_keyboard(language)
        )
        return

    buttons = []

    for project in projects:
        name = (
            project["name_uz"]
            if language == "uz"
            else project["name_ru"]
        )

        if not name:
            name = (
                project["name_uz"]
                or project["name_ru"]
                or "Loyiha"
            )

        buttons.append([
            InlineKeyboardButton(
                text=f"📌 {name}",
                callback_data=f"project:{project['id']}"
            )
        ])

    await message.answer(
        t["select_project"],
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )


# =========================================================
# PROJECT DETAIL
# =========================================================

@dp.callback_query(
    F.data.startswith("project:")
)
async def project_detail(
    callback: CallbackQuery
):
    try:
        project_id = int(
            callback.data.split(":")[1]
        )

    except (ValueError, IndexError):
        await callback.answer(
            "Xatolik",
            show_alert=True
        )
        return

    language = get_language(
        callback.from_user.id
    )

    t = TEXTS[language]

    with closing(get_db()) as db:
        cursor = db.cursor()

        cursor.execute("""
            SELECT
                id,
                name_uz,
                name_ru,
                url
            FROM projects
            WHERE id = ?
        """, (
            project_id,
        ))

        project = cursor.fetchone()

        if project:
            cursor.execute("""
                UPDATE projects
                SET click_count =
                    COALESCE(click_count, 0) + 1
                WHERE id = ?
            """, (
                project_id,
            ))

            db.commit()

    if not project:
        await callback.answer(
            t["project_not_found"],
            show_alert=True
        )
        return

    name = (
        project["name_uz"]
        if language == "uz"
        else project["name_ru"]
    )

    if not name:
        name = (
            project["name_uz"]
            or project["name_ru"]
            or "Loyiha"
        )

    buttons = []

    if project["url"]:
        buttons.append([
            InlineKeyboardButton(
                text=t["open_project"],
                url=project["url"]
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text=t["vote"],
            callback_data=f"vote:{project_id}"
        )
    ])

    await callback.message.answer(
        f"📌 <b>{escape(name)}</b>\n\n"
        f"🗳 {t['vote']}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )

    await callback.answer()


# =========================================================
# VOTE
# =========================================================

@dp.callback_query(
    F.data.startswith("vote:")
)
async def vote_handler(
    callback: CallbackQuery,
    state: FSMContext
):
    try:
        project_id = int(
            callback.data.split(":")[1]
        )

    except (ValueError, IndexError):
        await callback.answer(
            "Xatolik",
            show_alert=True
        )
        return

    language = get_language(
        callback.from_user.id
    )

    t = TEXTS[language]

    with closing(get_db()) as db:
        cursor = db.cursor()

        cursor.execute("""
            SELECT id
            FROM projects
            WHERE id = ?
        """, (
            project_id,
        ))

        project = cursor.fetchone()

        if not project:
            await callback.answer(
                t["project_not_found"],
                show_alert=True
            )
            return

        cursor.execute("""
            SELECT id
            FROM votes
            WHERE user_id = ?
              AND project_id = ?
        """, (
            callback.from_user.id,
            project_id
        ))

        already = cursor.fetchone()

    if already:
        await callback.answer(
            t["already_voted"],
            show_alert=True
        )
        return

    await state.clear()

    await state.update_data(
        vote_project_id=project_id
    )

    await state.set_state(
        VoteStates.waiting_phone
    )

    await callback.message.answer(
        t["phone_required"],
        reply_markup=phone_keyboard(language)
    )

    await callback.answer()


# =========================================================
# PHONE
# =========================================================

@dp.message(
    VoteStates.waiting_phone,
    F.contact
)
async def contact_handler(
    message: Message,
    state: FSMContext
):
    data = await state.get_data()

    project_id = data.get(
        "vote_project_id"
    )

    if not project_id:
        await state.clear()
        return

    language = get_language(
        message.from_user.id
    )

    t = TEXTS[language]

    contact = message.contact

    if (
        contact.user_id
        and contact.user_id != message.from_user.id
    ):
        await message.answer(
            t["own_phone_only"]
        )
        return

    phone = contact.phone_number

    with closing(get_db()) as db:
        cursor = db.cursor()

        cursor.execute("""
            SELECT id
            FROM projects
            WHERE id = ?
        """, (
            project_id,
        ))

        project = cursor.fetchone()

        if not project:
            await state.clear()

            await message.answer(
                t["project_not_found"],
                reply_markup=user_keyboard(language)
            )
            return

        cursor.execute("""
            SELECT id
            FROM votes
            WHERE user_id = ?
              AND project_id = ?
        """, (
            message.from_user.id,
            project_id
        ))

        already = cursor.fetchone()

        if already:
            await state.clear()

            await message.answer(
                t["already_voted"],
                reply_markup=user_keyboard(language)
            )
            return

        try:
            cursor.execute("""
                INSERT INTO votes (
                    user_id,
                    project_id,
                    phone
                )
                VALUES (?, ?, ?)
            """, (
                message.from_user.id,
                project_id,
                phone
            ))

            db.commit()

        except sqlite3.IntegrityError:
            await state.clear()

            await message.answer(
                t["already_voted"],
                reply_markup=user_keyboard(language)
            )
            return

    save_phone(
        message.from_user.id,
        phone
    )

    await state.clear()

    await message.answer(
        t["phone_received"],
        reply_markup=user_keyboard(language)
    )

    await message.answer(
        t["vote_success"]
    )


@dp.message(VoteStates.waiting_phone)
async def phone_required_handler(
    message: Message
):
    language = get_language(
        message.from_user.id
    )

    await message.answer(
        TEXTS[language]["phone_required"],
        reply_markup=phone_keyboard(language)
    )


# =========================================================
# CANCEL
# =========================================================

@dp.message(F.text.in_({
    "❌ Bekor qilish",
    "❌ Отмена"
}))
async def cancel_handler(
    message: Message,
    state: FSMContext
):
    await state.clear()

    language = get_language(
        message.from_user.id
    )

    if is_admin(message.from_user.id):
        markup = admin_keyboard(language)
    else:
        markup = user_keyboard(language)

    await message.answer(
        TEXTS[language]["cancelled"],
        reply_markup=markup
    )


@dp.message(Command("cancel"))
async def cancel_command(
    message: Message,
    state: FSMContext
):
    await state.clear()

    language = get_language(
        message.from_user.id
    )

    if is_admin(message.from_user.id):
        markup = admin_keyboard(language)
    else:
        markup = user_keyboard(language)

    await message.answer(
        TEXTS[language]["cancelled"],
        reply_markup=markup
    )


# =========================================================
# HELP
# =========================================================

@dp.message(F.text.in_({
    "❓ Yordam",
    "❓ Помощь"
}))
async def help_handler(message: Message):
    add_or_update_user(message)

    language = get_language(
        message.from_user.id
    )

    await message.answer(
        TEXTS[language]["help_text"],
        reply_markup=user_keyboard(language)
    )


# =========================================================
# NEWS
# =========================================================

@dp.message(F.text.in_({
    "📰 Yangiliklar",
    "📰 Новости"
}))
async def news_handler(message: Message):
    add_or_update_user(message)

    language = get_language(
        message.from_user.id
    )

    with closing(get_db()) as db:
        cursor = db.cursor()

        cursor.execute("""
            SELECT
                id,
                message_id,
                chat_id,
                text
            FROM news
            ORDER BY id DESC
            LIMIT 10
        """)

        news_list = cursor.fetchall()

    if not news_list:
        await message.answer(
            TEXTS[language]["news_empty"],
            reply_markup=user_keyboard(language)
        )
        return

    sent_any = False

    for item in news_list:
        try:
            if (
                item["message_id"]
                and item["chat_id"]
            ):
                await bot.copy_message(
                    chat_id=message.chat.id,
                    from_chat_id=item["chat_id"],
                    message_id=item["message_id"]
                )

                sent_any = True

                await asyncio.sleep(0.08)

            elif item["text"]:
                await message.answer(
                    item["text"]
                )

                sent_any = True

        except TelegramBadRequest:
            if item["text"]:
                await message.answer(
                    item["text"]
                )

                sent_any = True

        except Exception as e:
            logger.error(
                "News copy error: %s",
                e
            )

            if item["text"]:
                await message.answer(
                    item["text"]
                )

                sent_any = True

    if not sent_any:
        await message.answer(
            TEXTS[language]["news_empty"],
            reply_markup=user_keyboard(language)
        )


# =========================================================
# ADMIN COMMAND
# =========================================================

@dp.message(Command("admin"))
async def admin_command(
    message: Message
):
    add_or_update_user(message)

    if not is_admin(
        message.from_user.id
    ):
        language = get_language(
            message.from_user.id
        )

        await message.answer(
            TEXTS[language]["admin_only"]
        )

        return

    language = get_language(
        message.from_user.id
    )

    await message.answer(
        TEXTS[language]["admin_panel"],
        reply_markup=admin_keyboard(language)
    )


@dp.message(F.text.in_({
    "⚙️ Admin panel",
    "⚙️ Админ-панель"
}))
async def admin_panel_button(
    message: Message
):
    if not is_admin(
        message.from_user.id
    ):
        language = get_language(
            message.from_user.id
        )

        await message.answer(
            TEXTS[language]["admin_only"]
        )

        return

    language = get_language(
        message.from_user.id
    )

    await message.answer(
        TEXTS[language]["admin_panel"],
        reply_markup=admin_keyboard(language)
    )


# =========================================================
# ADD PROJECT
# =========================================================

@dp.message(F.text.in_({
    "➕ Loyiha qo'shish",
    "➕ Loyiha qo‘shish",
    "➕ Добавить проект"
}))
async def add_project_start(
    message: Message,
    state: FSMContext
):
    if not is_admin(
        message.from_user.id
    ):
        language = get_language(
            message.from_user.id
        )

        await message.answer(
            TEXTS[language]["admin_only"]
        )

        return

    language = get_language(
        message.from_user.id
    )

    await state.clear()

    await state.set_state(
        ProjectStates.waiting_name
    )

    await message.answer(
        TEXTS[language]["project_name"]
    )


@dp.message(ProjectStates.waiting_name)
async def add_project_name(
    message: Message,
    state: FSMContext
):
    if not is_admin(
        message.from_user.id
    ):
        await state.clear()
        return

    language = get_language(
        message.from_user.id
    )

    if not message.text:
        await message.answer(
            TEXTS[language]["project_name"]
        )

        return

    name = message.text.strip()

    if len(name) < 2:
        await message.answer(
            TEXTS[language]["project_invalid_name"]
        )

        return

    await state.update_data(
        project_name=name
    )

    await state.set_state(
        ProjectStates.waiting_link
    )

    await message.answer(
        TEXTS[language]["project_link"]
    )


@dp.message(ProjectStates.waiting_link)
async def add_project_link(
    message: Message,
    state: FSMContext
):
    if not is_admin(
        message.from_user.id
    ):
        await state.clear()
        return

    language = get_language(
        message.from_user.id
    )

    if not message.text:
        await message.answer(
            TEXTS[language]["project_link"]
        )

        return

    url = message.text.strip()

    parsed = urlparse(url)

    if (
        parsed.scheme not in (
            "http",
            "https"
        )
        or not parsed.netloc
    ):
        await message.answer(
            TEXTS[language]["invalid_link"]
        )

        return

    data = await state.get_data()

    project_name = data.get(
        "project_name"
    )

    if not project_name:
        await state.clear()

        await message.answer(
            TEXTS[language]["cancelled"],
            reply_markup=admin_keyboard(language)
        )

        return

    with closing(get_db()) as db:
        db.execute("""
            INSERT INTO projects (
                name_uz,
                name_ru,
                url,
                click_count
            )
            VALUES (?, ?, ?, 0)
        """, (
            project_name,
            project_name,
            url
        ))

        db.commit()

    await state.clear()

    await message.answer(
        TEXTS[language]["project_created"],
        reply_markup=admin_keyboard(language)
    )


# =========================================================
# ADD NEWS
# =========================================================

@dp.message(F.text.in_({
    "📰 Yangilik qo'shish",
    "📰 Yangilik qo‘shish",
    "📰 Добавить новость"
}))
async def add_news_start(
    message: Message,
    state: FSMContext
):
    if not is_admin(
        message.from_user.id
    ):
        language = get_language(
            message.from_user.id
        )

        await message.answer(
            TEXTS[language]["admin_only"]
        )

        return

    language = get_language(
        message.from_user.id
    )

    await state.clear()

    await state.set_state(
        NewsStates.waiting_content
    )

    await message.answer(
        TEXTS[language]["send_news"]
    )


@dp.message(NewsStates.waiting_content)
async def add_news_content(
    message: Message,
    state: FSMContext
):
    if not is_admin(
        message.from_user.id
    ):
        await state.clear()
        return

    language = get_language(
        message.from_user.id
    )

    text = (
        message.text
        or message.caption
        or ""
    )

    with closing(get_db()) as db:
        db.execute("""
            INSERT INTO news (
                message_id,
                chat_id,
                text
            )
            VALUES (?, ?, ?)
        """, (
            message.message_id,
            message.chat.id,
            text
        ))

        db.commit()

    success, blocked, failed = (
        await broadcast_message(
            source_chat_id=message.chat.id,
            source_message_id=message.message_id
        )
    )

    await state.clear()

    await message.answer(
        TEXTS[language]["news_saved"]
        +