import asyncio
import logging
import os
import sqlite3
from pathlib import Path
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

BOT_TOKEN = os.getenv("8615736731:AAEfzzzWI-oPwjCtYG2raKE-ctqoLeHo1hY", "").strip()

# Railway Variables:
# ADMIN_IDS=7998053914,1599812727
ADMIN_IDS = set()

admin_ids_text = os.getenv("ADMIN_IDS", "").strip()

if admin_ids_text:
    for item in admin_ids_text.split(","):
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
            "Kerakli bo‘limni tanlang:"
        ),
        "projects": "📌 Loyihalar",
        "news": "📰 Yangiliklar",
        "help": "❓ Yordam",
        "language": "🌐 Til",
        "admin": "⚙️ Admin panel",
        "statistics": "📊 Statistika",
        "add_project": "➕ Loyiha qo‘shish",
        "add_news": "📰 Yangilik qo‘shish",
        "broadcast": "📢 Reklama tarqatish",
        "back": "🔙 Orqaga",

        "select_language": "Tilni tanlang:",
        "language_saved": "✅ Til o‘zgartirildi.",
        "select_project": "📌 Loyihalardan birini tanlang:",
        "no_projects": "Hozircha loyiha yo‘q.",

        "project_name": "📝 Loyiha nomini yuboring:",
        "project_link": (
            "🔗 Endi loyiha havolasini yuboring.\n\n"
            "Masalan:\n"
            "https://example.com"
        ),
        "project_created": "✅ Loyiha muvaffaqiyatli qo‘shildi!",
        "invalid_link": "❌ Havola noto‘g‘ri.\nhttps:// bilan boshlanadigan havola yuboring.",

        "vote": "🗳 Ovoz berish",
        "open_project": "🔗 Loyihani ochish",
        "phone_required": (
            "🗳 Ovoz berish uchun telefon raqamingizni yuborishingiz kerak.\n\n"
            "Quyidagi tugmani bosing. Telefon raqamingiz Telegram orqali "
            "sizning roziligingiz bilan yuboriladi."
        ),
        "send_phone": "📱 Telefon raqamimni yuborish",
        "cancel": "❌ Bekor qilish",
        "phone_received": "✅ Telefon raqamingiz qabul qilindi.",
        "vote_success": "🎉 Ovoz berishingiz muvaffaqiyatli qabul qilindi!",
        "already_voted": "⚠️ Siz bu loyihaga allaqachon ovoz bergansiz.",
        "vote_error": "❌ Ovoz berishda xatolik yuz berdi.",

        "help_text": (
            "❓ Yordam\n\n"
            "📌 Loyihalar — mavjud loyihalarni ko‘rish.\n"
            "🗳 Ovoz berish — loyiha uchun ovoz berish.\n"
            "📰 Yangiliklar — so‘nggi yangiliklarni ko‘rish.\n"
            "🌐 Til — tilni almashtirish.\n\n"
            "Telefon raqami faqat sizning roziligingiz bilan olinadi."
        ),

        "news_empty": "📰 Hozircha yangiliklar mavjud emas.",
        "admin_only": "❌ Bu bo‘lim faqat administratorlar uchun.",
        "admin_panel": "⚙️ Admin panel:",
        "send_news": (
            "📰 Yangilik uchun rasm yoki matn yuboring.\n\n"
            "Agar rasm yuborsangiz, caption yozishingiz mumkin."
        ),
        "news_saved": "✅ Yangilik saqlandi va foydalanuvchilarga yuborildi.",
        "send_broadcast": (
            "📢 Barcha foydalanuvchilarga yuboriladigan xabarni yuboring.\n\n"
            "Matn, rasm, video yoki boshqa Telegram xabarini yuborishingiz mumkin."
        ),
        "broadcast_finished": "✅ Tarqatish yakunlandi.",
        "cancelled": "❌ Bekor qilindi.",

        "stats": (
            "📊 Statistika\n\n"
            "👥 Foydalanuvchilar: {users}\n"
            "🗳 Jami ovozlar: {votes}\n"
            "🔗 Loyiha havola bosishlari: {clicks}\n"
            "📌 Loyihalar soni: {projects}\n"
            "📰 Yangiliklar soni: {news}"
        ),

        "unknown": "❗ Iltimos, menyudagi tugmalardan foydalaning.",
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
        "admin": "⚙️ Админ-панель",
        "statistics": "📊 Статистика",
        "add_project": "➕ Добавить проект",
        "add_news": "📰 Добавить новость",
        "broadcast": "📢 Рассылка",
        "back": "🔙 Назад",

        "select_language": "Выберите язык:",
        "language_saved": "✅ Язык изменён.",
        "select_project": "📌 Выберите проект:",
        "no_projects": "Пока проектов нет.",

        "project_name": "📝 Отправьте название проекта:",
        "project_link": (
            "🔗 Теперь отправьте ссылку проекта.\n\n"
            "Например:\n"
            "https://example.com"
        ),
        "project_created": "✅ Проект успешно добавлен!",
        "invalid_link": "❌ Неверная ссылка.\nОна должна начинаться с https:// или http://.",

        "vote": "🗳 Голосовать",
        "open_project": "🔗 Открыть проект",
        "phone_required": (
            "🗳 Для голосования необходимо отправить номер телефона.\n\n"
            "Нажмите кнопку ниже. Telegram отправит ваш номер "
            "только после вашего согласия."
        ),
        "send_phone": "📱 Отправить мой номер",
        "cancel": "❌ Отмена",
        "phone_received": "✅ Номер телефона получен.",
        "vote_success": "🎉 Ваш голос успешно принят!",
        "already_voted": "⚠️ Вы уже голосовали за этот проект.",
        "vote_error": "❌ Произошла ошибка при голосовании.",

        "help_text": (
            "❓ Помощь\n\n"
            "📌 Проекты — просмотр проектов.\n"
            "🗳 Голосовать — проголосовать за проект.\n"
            "📰 Новости — последние новости.\n"
            "🌐 Язык — смена языка.\n\n"
            "Номер телефона запрашивается только с вашего согласия."
        ),

        "news_empty": "📰 Пока новостей нет.",
        "admin_only": "❌ Этот раздел доступен только администраторам.",
        "admin_panel": "⚙️ Админ-панель:",
        "send_news": (
            "📰 Отправьте фото или текст новости.\n\n"
            "Если отправляете фото, можно добавить caption."
        ),
        "news_saved": "✅ Новость сохранена и отправлена пользователям.",
        "send_broadcast": (
            "📢 Отправьте сообщение для всех пользователей.\n\n"
            "Можно отправить текст, фото, видео или другое сообщение Telegram."
        ),
        "broadcast_finished": "✅ Рассылка завершена.",
        "cancelled": "❌ Отменено.",

        "stats": (
            "📊 Статистика\n\n"
            "👥 Пользователи: {users}\n"
            "🗳 Всего голосов: {votes}\n"
            "🔗 Переходов по ссылкам: {clicks}\n"
            "📌 Проектов: {projects}\n"
            "📰 Новостей: {news}"
        ),

        "unknown": "❗ Пожалуйста, используйте кнопки меню.",
    }
}


# =========================================================
# FSM STATES
# =========================================================

class ProjectStates(StatesGroup):
    waiting_name = State()
    waiting_link = State()


class NewsStates(StatesGroup):
    waiting_content = State()


class BroadcastStates(StatesGroup):
    waiting_content = State()


# =========================================================
# DATABASE
# =========================================================

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with closing(get_db()) as db:
        cur = db.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                language TEXT DEFAULT 'uz',
                phone TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name_uz TEXT NOT NULL,
                name_ru TEXT NOT NULL,
                url TEXT,
                click_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                project_id INTEGER NOT NULL,
                phone TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, project_id)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER,
                chat_id INTEGER,
                text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        db.commit()


# =========================================================
# USER FUNCTIONS
# =========================================================

def add_or_update_user(message: Message):
    user = message.from_user

    with closing(get_db()) as db:
        cur = db.cursor()

        cur.execute(
            "SELECT user_id FROM users WHERE user_id = ?",
            (user.id,)
        )

        exists = cur.fetchone()

        if exists:
            cur.execute("""
                UPDATE users
                SET username = ?, first_name = ?
                WHERE user_id = ?
            """, (
                user.username,
                user.first_name,
                user.id
            ))
        else:
            cur.execute("""
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


def get_language(user_id: int) -> str:
    with closing(get_db()) as db:
        cur = db.cursor()

        cur.execute(
            "SELECT language FROM users WHERE user_id = ?",
            (user_id,)
        )

        row = cur.fetchone()

        if row and row["language"] in ("uz", "ru"):
            return row["language"]

    return "uz"


def set_language(user_id: int, language: str):
    with closing(get_db()) as db:
        db.execute(
            "UPDATE users SET language = ? WHERE user_id = ?",
            (language, user_id)
        )
        db.commit()


def save_phone(user_id: int, phone: str):
    with closing(get_db()) as db:
        db.execute(
            "UPDATE users SET phone = ? WHERE user_id = ?",
            (phone, user_id)
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
                KeyboardButton(text=t["statistics"]),
            ],
            [
                KeyboardButton(text=t["add_project"]),
                KeyboardButton(text=t["add_news"]),
            ],
            [
                KeyboardButton(text=t["broadcast"]),
            ],
            [
                KeyboardButton(text=t["back"]),
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
            ]
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
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )


# =========================================================
# ADMIN CHECK
# =========================================================

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# =========================================================
# START
# =========================================================

@dp.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    await state.clear()

    add_or_update_user(message)

    language = get_language(message.from_user.id)

    await message.answer(
        TEXTS[language]["welcome"].format(
            name=message.from_user.first_name or "foydalanuvchi"
        ),
        reply_markup=user_keyboard(language)
    )


# =========================================================
# LANGUAGE
# =========================================================

@dp.message(F.text.in_({"🌐 Til", "🌐 Язык"}))
async def language_handler(message: Message):
    language = get_language(message.from_user.id)

    await message.answer(
        TEXTS[language]["select_language"],
        reply_markup=language_keyboard()
    )


@dp.message(F.text == "🇺🇿 O‘zbek")
async def uz_language(message: Message):
    set_language(message.from_user.id, "uz")

    await message.answer(
        TEXTS["uz"]["language_saved"],
        reply_markup=user_keyboard("uz")
    )


@dp.message(F.text == "🇷🇺 Русский")
async def ru_language(message: Message):
    set_language(message.from_user.id, "ru")

    await message.answer(
        TEXTS["ru"]["language_saved"],
        reply_markup=user_keyboard("ru")
    )


# =========================================================
# PROJECTS
# =========================================================

@dp.message(F.text.in_({"📌 Loyihalar", "📌 Проекты"}))
async def projects_handler(message: Message):
    add_or_update_user(message)

    language = get_language(message.from_user.id)
    t = TEXTS[language]

    with closing(get_db()) as db:
        cur = db.cursor()

        cur.execute("""
            SELECT id, name_uz, name_ru, url
            FROM projects
            ORDER BY id DESC
        """)

        projects = cur.fetchall()

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

        buttons.append([
            InlineKeyboardButton(
                text=f"📌 {name}",
                callback_data=f"project:{project['id']}"
            )
        ])

    await message.answer(
        t["select_project"],
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


# =========================================================
# PROJECT DETAIL
# =========================================================

@dp.callback_query(F.data.startswith("project:"))
async def project_detail(callback: CallbackQuery):
    project_id = int(callback.data.split(":")[1])

    language = get_language(callback.from_user.id)
    t = TEXTS[language]

    with closing(get_db()) as db:
        cur = db.cursor()

        cur.execute("""
            SELECT *
            FROM projects
            WHERE id = ?
        """, (project_id,))

        project = cur.fetchone()

    if not project:
        await callback.answer("Loyiha topilmadi.", show_alert=True)
        return

    name = (
        project["name_uz"]
        if language == "uz"
        else project["name_ru"]
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
        f"📌 <b>{name}</b>\n\n"
        f"🗳 Ovoz berish uchun quyidagi tugmani bosing.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )

    await callback.answer()


# =========================================================
# PROJECT LINK CLICK
# =========================================================

@dp.callback_query(F.data.startswith("click:"))
async def project_click(callback: CallbackQuery):
    project_id = int(callback.data.split(":")[1])

    with closing(get_db()) as db:
        db.execute("""
            UPDATE projects
            SET click_count = click_count + 1
            WHERE id = ?
        """, (project_id,))
        db.commit()

    await callback.answer()


# =========================================================
# VOTE
# =========================================================

@dp.callback_query(F.data.startswith("vote:"))
async def vote_handler(callback: CallbackQuery, state: FSMContext):
    project_id = int(callback.data.split(":")[1])

    language = get_language(callback.from_user.id)
    t = TEXTS[language]

    with closing(get_db()) as db:
        cur = db.cursor()

        cur.execute("""
            SELECT id
            FROM votes
            WHERE user_id = ?
            AND project_id = ?
        """, (
            callback.from_user.id,
            project_id
        ))

        already = cur.fetchone()

    if already:
        await callback.answer(
            t["already_voted"],
            show_alert=True
        )
        return

    await state.update_data(
        vote_project_id=project_id
    )

    await callback.message.answer(
        t["phone_required"],
        reply_markup=phone_keyboard(language)
    )

    await callback.answer()


# =========================================================
# PHONE CONTACT
# =========================================================

@dp.message(F.contact)
async def contact_handler(message: Message, state: FSMContext):
    data = await state.get_data()

    project_id = data.get("vote_project_id")

    if not project_id:
        return

    language = get_language(message.from_user.id)
    t = TEXTS[language]

    contact = message.contact

    # Foydalanuvchi o'z kontaktini yuborganini tekshiramiz
    if contact.user_id and contact.user_id != message.from_user.id:
        await message.answer(
            "❌ Iltimos, o'zingizning telefon raqamingizni yuboring."
            if language == "uz"
            else "❌ Пожалуйста, отправьте свой номер телефона."
        )
        return

    phone = contact.phone_number

    with closing(get_db()) as db:
        cur = db.cursor()

        # Bir marta ovoz berish
        cur.execute("""
            SELECT id
            FROM votes
            WHERE user_id = ?
            AND project_id = ?
        """, (
            message.from_user.id,
            project_id
        ))

        already = cur.fetchone()

        if already:
            await message.answer(
                t["already_voted"],
                reply_markup=user_keyboard(language)
            )
            await state.clear()
            return

        try:
            cur.execute("""
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
            await message.answer(
                t["already_voted"],
                reply_markup=user_keyboard(language)
            )
            await state.clear()
            return

    save_phone(message.from_user.id, phone)

    await message.answer(
        t["phone_received"],
        reply_markup=user_keyboard(language)
    )

    await message.answer(
        t["vote_success"]
    )

    await state.clear()


# =========================================================
# CANCEL
# =========================================================

@dp.message(F.text.in_({"❌ Bekor qilish", "❌ Отмена"}))
async def cancel_handler(message: Message, state: FSMContext):
    await state.clear()

    language = get_language(message.from_user.id)

    await message.answer(
        TEXTS[language]["cancelled"],
        reply_markup=user_keyboard(language)
    )


# =========================================================
# HELP
# =========================================================

@dp.message(F.text.in_({"❓ Yordam", "❓ Помощь"}))
async def help_handler(message: Message):
    language = get_language(message.from_user.id)

    await message.answer(
        TEXTS[language]["help_text"],
        reply_markup=user_keyboard(language)
    )


# =========================================================
# NEWS
# =========================================================

@dp.message(F.text.in_({"📰 Yangiliklar", "📰 Новости"}))
async def news_handler(message: Message):
    language = get_language(message.from_user.id)

    with closing(get_db()) as db:
        cur = db.cursor()

        cur.execute("""
            SELECT *
            FROM news
            ORDER BY id DESC
            LIMIT 10
        """)

        news_list = cur.fetchall()

    if not news_list:
        await message.answer(
            TEXTS[language]["news_empty"],
            reply_markup=user_keyboard(language)
        )
        return

    for item in news_list:
        try:
            await bot.copy_message(
                chat_id=message.chat.id,
                from_chat_id=item["chat_id"],
                message_id=item["message_id"]
            )
        except Exception:
            if item["text"]:
                await message.answer(item["text"])


# =========================================================
# ADMIN PANEL
# =========================================================

@dp.message(Command("admin"))
async def admin_command(message: Message):
    if not is_admin(message.from_user.id):
        language = get_language(message.from_user.id)

        await message.answer(
            TEXTS[language]["admin_only"]
        )
        return

    language = get_language(message.from_user.id)

    await message.answer(
        TEXTS[language]["admin_panel"],
        reply_markup=admin_keyboard(language)
    )


# =========================================================
# ADMIN BUTTON
# =========================================================

@dp.message(F.text.in_({"⚙️ Admin panel", "⚙️ Админ-панель"}))
async def admin_panel_button(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer(
            TEXTS[get_language(message.from_user.id)]["admin_only"]
        )
        return

    language = get_language(message.from_user.id)

    await message.answer(
        TEXTS[language]["admin_panel"],
        reply_markup=admin_keyboard(language)
    )


# =========================================================
# ADD PROJECT
# =========================================================

@dp.message(F.text.in_({"➕ Loyiha qo‘shish", "➕ Добавить проект"}))
async def add_project_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer(
            TEXTS[get_language(message.from_user.id)]["admin_only"]
        )
        return

    language = get_language(message.from_user.id)

    await state.set_state(ProjectStates.waiting_name)

    await message.answer(
        TEXTS[language]["project_name"]
    )


@dp.message(ProjectStates.waiting_name)
async def add_project_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    language = get_language(message.from_user.id)

    name = message.text.strip()

    if len(name) < 2:
        await message.answer(
            "❌ Loyiha nomi juda qisqa."
            if language == "uz"
            else "❌ Название проекта слишком короткое."
        )
        return

    await state.update_data(
        project_name=name
    )

    await state.set_state(ProjectStates.waiting_link)

    await message.answer(
        TEXTS[language]["project_link"]
    )


@dp.message(ProjectStates.waiting_link)
async def add_project_link(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    language = get_language(message.from_user.id)
    text = message.text.strip()

    if not (
        text.startswith("https://")
        or text.startswith("http://")
    ):
        await message.answer(
            TEXTS[language]["invalid_link"]
        )
        return

    data = await state.get_data()

    project_name = data.get("project_name")

    with closing(get_db()) as db:
        db.execute("""
            INSERT INTO projects (
                name_uz,
                name_ru,
                url
            )
            VALUES (?, ?, ?)
        """, (
            project_name,
            project_name,
            text
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

@dp.message(F.text.in_({"📰 Yangilik qo‘shish", "📰 Добавить новость"}))
async def add_news_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer(
            TEXTS[get_language(message.from_user.id)]["admin_only"]
        )
        return

    language = get_language(message.from_user.id)

    await state.set_state(
        NewsStates.waiting_content
    )

    await message.answer(
        TEXTS[language]["send_news"]
    )


@dp.message(NewsStates.waiting_content)
async def add_news_content(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    language = get_language(message.from_user.id)

    # Yangilikni DBga saqlaymiz
    text = message.text or message.caption or ""

    with closing(get_db()) as db:
        cur = db.cursor()

        cur.execute("""
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

    # Barcha foydalanuvchilarga yuborish
    await broadcast_message(
        source_chat_id=message.chat.id,
        source_message_id=message.message_id
    )

    await state.clear()

    await message.answer(
        TEXTS[language]["news_saved"],
        reply_markup=admin_keyboard(language)
    )


# =========================================================
# BROADCAST
# =========================================================

@dp.message(F.text.in_({"📢 Reklama tarqatish", "📢 Рассылка"}))
async def broadcast_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer(
            TEXTS[get_language(message.from_user.id)]["admin_only"]
        )
        return

    language = get_language(message.from_user.id)

    await state.set_state(
        BroadcastStates.waiting_content
    )

    await message.answer(
        TEXTS[language]["send_broadcast"]
    )


@dp.message(BroadcastStates.waiting_content)
async def broadcast_content(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    language = get_language(message.from_user.id)

    await broadcast_message(
        source_chat_id=message.chat.id,
        source_message_id=message.message_id
    )

    await state.clear()

    await message.answer(
        TEXTS[language]["broadcast_finished"],
        reply_markup=admin_keyboard(language)
    )


# =========================================================
# BROADCAST FUNCTION
# =========================================================

async def broadcast_message(
    source_chat_id: int,
    source_message_id: int
):
    with closing(get_db()) as db:
        cur = db.cursor()

        cur.execute("""
            SELECT user_id
            FROM users
        """)

        users = cur.fetchall()

    success = 0
    blocked = 0
    failed = 0

    for user in users:
        user_id = user["user_id"]

        try:
            await bot.copy_message(
                chat_id=user_id,
                from_chat_id=source_chat_id,
                message_id=source_message_id
            )

            success += 1

            await asyncio.sleep(0.04)

        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)

            try:
                await bot.copy_message(
                    chat_id=user_id,
                    from_chat_id=source_chat_id,
                    message_id=source_message_id
                )
                success += 1
            except Exception:
                failed += 1

        except TelegramForbiddenError:
            blocked += 1

            with closing(get_db()) as db:
                db.execute(
                    "DELETE FROM users WHERE user_id = ?",
                    (user_id,)
                )
                db.commit()

        except TelegramBadRequest:
            failed += 1

        except Exception as e:
            logger.error(
                "Broadcast error for %s: %s",
                user_id,
                e
            )
            failed += 1

    logger.info(
        "Broadcast finished: success=%s blocked=%s failed=%s",
        success,
        blocked,
        failed
    )


# =========================================================
# STATISTICS
# =========================================================

@dp.message(F.text.in_({"📊 Statistika", "📊 Статистика"}))
async def statistics_handler(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer(
            TEXTS[get_language(message.from_user.id)]["admin_only"]
        )
        return

    language = get_language(message.from_user.id)

    with closing(get_db()) as db:
        cur = db.cursor()

        cur.execute("SELECT COUNT(*) FROM users")
        users_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM votes")
        votes_count = cur.fetchone()[0]

        cur.execute(
            "SELECT COALESCE(SUM(click_count), 0) FROM projects"
        )
        clicks_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM projects")
        projects_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM news")
        news_count = cur.fetchone()[0]

    await message.answer(
        TEXTS[language]["stats"].format(
            users=users_count,
            votes=votes_count,
            clicks=clicks_count,
            projects=projects_count,
            news=news_count
        )
    )


# =========================================================
# ADMIN BACK
# =========================================================

@dp.message(F.text.in_({"🔙 Orqaga", "🔙 Назад"}))
async def back_handler(message: Message, state: FSMContext):
    await state.clear()

    language = get_language(message.from_user.id)

    if is_admin(message.from_user.id):
        await message.answer(
            TEXTS[language]["admin_panel"],
            reply_markup=admin_keyboard(language)
        )
    else:
        await message.answer(
            TEXTS[language]["welcome"].format(
                name=message.from_user.first_name or "foydalanuvchi"
            ),
            reply_markup=user_keyboard(language)
        )


# =========================================================
# UNKNOWN MESSAGE
# =========================================================

@dp.message()
async def unknown_handler(message: Message):
    add_or_update_user(message)

    language = get_language(message.from_user.id)

    await message.answer(
        TEXTS[language]["unknown"],
        reply_markup=user_keyboard(language)
    )


# =========================================================
# START BOT
# =========================================================

async def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN topilmadi. Railway Environment Variables "
            "ichida BOT_TOKEN qo‘shing."
        )

    init_db()

    logger.info("Bot ishga tushmoqda...")
    logger.info("Adminlar: %s", ADMIN_IDS)

    await bot.delete_webhook(
        drop_pending_updates=True
    )

    await dp.start_polling(
        bot,
        allowed_updates=dp.resolve_used_update_types()
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot to‘xtatildi.")