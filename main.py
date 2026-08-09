# =========================================================
# MAIN.PY
# =========================================================

import asyncio
import logging
import re
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

BOT_TOKEN = "8615736731:AAF7LGgYsKCq_JjV9qFPmFV6psTAS4mlQ_g"

# Bir yoki bir nechta admin ID yozish mumkin:
ADMIN_IDS = {
    7998053914,
}

VOTE_REWARD = 20_000
REFERRAL_REWARD = 5_000
MIN_WITHDRAW = 20_000

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "bot.db"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


if not BOT_TOKEN or BOT_TOKEN == "YANGI_BOT_TOKENINGIZNI_SHU_YERGA_YOZING":
    raise RuntimeError(
        "BOT_TOKEN ni main.py ichiga yozing."
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
            "🎁 Har bir tasdiqlangan ovoz uchun "
            "{vote_reward} so'm hisobingizga qo'shiladi.\n"
            "👥 Referal bonus: {ref_reward} so'm.\n\n"
            "Kerakli bo'limni tanlang:"
        ),

        "projects": "📌 Loyihalar",
        "news": "📰 Yangiliklar",
        "balance": "💰 Balans",
        "referral": "🔗 Referal ssilka",
        "withdraw": "💸 Pul yechish",
        "help": "❓ Yordam",
        "language": "🌐 Til",
        "group_add": "👥 Guruhga qo'shish",

        "statistics": "📊 Statistika",
        "add_project": "➕ Loyiha qo'shish",
        "add_news": "📰 Yangilik qo'shish",
        "broadcast": "📢 Reklama tarqatish",
        "withdrawals": "💸 Yechishlar",
        "admin_panel": "⚙️ Admin panel",

        "back": "🔙 Orqaga",
        "cancel": "❌ Bekor qilish",

        "select_language": "🌐 Tilni tanlang:",
        "language_saved": "✅ Til o'zgartirildi.",

        "select_project": "📌 Loyihani tanlang:",
        "no_projects": "📌 Hozircha loyihalar mavjud emas.",

        "project_name": "📝 Loyiha nomini yuboring:",
        "project_link": (
            "🔗 Loyiha havolasini yuboring.\n\n"
            "Masalan:\n"
            "https://example.com"
        ),

        "project_created": "✅ Loyiha qo'shildi!",
        "invalid_link": "❌ Havola noto'g'ri.",
        "project_not_found": "❌ Loyiha topilmadi.",
        "open_project": "🔗 Loyihani ochish",
        "vote": "🗳 Ovoz berish",

        "vote_phone": (
            "📞 <b>Ovoz berish uchun telefon raqamni kiriting:</b>\n\n"
            "Telefon raqami <b>+998991234567</b> yoki "
            "<b>991234567</b> formatida kiritilishi kerak."
        ),

        "invalid_phone": (
            "❌ Telefon raqami noto'g'ri.\n\n"
            "Masalan:\n"
            "+998991234567\n"
            "yoki\n"
            "991234567"
        ),

        "vote_sent": (
            "✅ Telefon raqamingiz qabul qilindi.\n\n"
            "⏳ Ovoz berish so'rovingiz administratorga yuborildi.\n"
            "Admin tasdiqlaganidan keyin "
            "{reward} so'm balansingizga qo'shiladi."
        ),

        "vote_already_pending": (
            "⏳ Sizning bu loyiha bo'yicha ovoz so'rovingiz "
            "allaqachon ko'rib chiqilmoqda."
        ),

        "already_voted": (
            "⚠️ Siz bu loyihaga allaqachon ovoz bergansiz."
        ),

        "admin_only": (
            "❌ Bu bo'lim faqat administrator uchun."
        ),

        "help_text": (
            "❓ <b>Yordam</b>\n\n"
            "📌 Loyihalar — loyihalarni ko'rish.\n"
            "🗳 Ovoz berish — loyiha uchun ovoz berish.\n"
            "💰 Balans — hisobingizni ko'rish.\n"
            "🔗 Referal — do'st taklif qilish.\n"
            "💸 Pul yechish — pul yechish so'rovi.\n"
            "📰 Yangiliklar — yangiliklar.\n"
            "🌐 Til — tilni almashtirish."
        ),

        "balance_text": (
            "💰 <b>Balansingiz</b>\n\n"
            "💵 Balans: <b>{balance} so'm</b>\n"
            "📈 Jami ishlangan: {earned} so'm\n"
            "💸 Jami yechilgan: {withdrawn} so'm"
        ),

        "referral_text": (
            "🔗 <b>Referal havolangiz:</b>\n\n"
            "<code>{link}</code>\n\n"
            "👥 Taklif qilinganlar: {count}\n"
            "💰 Referal daromad: {earned} so'm\n\n"
            "Do'stingiz havola orqali kirib, "
            "tasdiqlangan ovoz bersa bonus olasiz."
        ),

        "news_empty": "📰 Hozircha yangiliklar yo'q.",

        "send_news": (
            "📰 Yangilik uchun rasm, video yoki matn yuboring."
        ),

        "news_saved": (
            "✅ Yangilik saqlandi va foydalanuvchilarga yuborildi."
        ),

        "send_broadcast": (
            "📢 Barcha foydalanuvchilarga yuboriladigan "
            "xabarni yuboring."
        ),

        "broadcast_result": (
            "📢 Tarqatish tugadi.\n\n"
            "✅ Yuborildi: {success}\n"
            "🚫 Bloklagan: {blocked}\n"
            "⚠️ Xatolik: {failed}"
        ),

        "stats": (
            "📊 <b>Statistika</b>\n\n"
            "👥 Foydalanuvchilar: {users}\n"
            "🗳 Ovozlar: {votes}\n"
            "⏳ Kutilayotgan ovozlar: {pending_votes}\n"
            "📌 Loyihalar: {projects}\n"
            "👁 Ko'rishlar: {views}\n"
            "📰 Yangiliklar: {news}\n"
            "💰 Umumiy balans: {balance} so'm\n"
            "💸 Yechilgan: {withdrawn} so'm"
        ),

        "withdraw_amount": (
            "💸 <b>Pul yechish</b>\n\n"
            "Minimal summa: {minimum} so'm\n"
            "Balansingiz: {balance} so'm\n\n"
            "Yechmoqchi bo'lgan summani yuboring:"
        ),

        "invalid_amount": "❌ Summani to'g'ri kiriting.",
        "not_enough": "❌ Balansingiz yetarli emas.",

        "withdraw_info": (
            "💳 To'lov rekvizitingizni yuboring.\n\n"
            "Masalan: telefon raqami yoki wallet ID."
        ),

        "withdraw_created": (
            "✅ Pul yechish so'rovi yuborildi.\n\n"
            "💰 Summa: {amount} so'm\n"
            "🆔 So'rov: #{request_id}\n\n"
            "Admin tekshiradi."
        ),

        "no_pending_withdrawals":
            "⏳ Kutilayotgan pul yechish so'rovlari yo'q.",

        "back_menu":
            "🔙 Asosiy menyuga qaytdingiz.",
    },

    "ru": {
        "welcome": (
            "Здравствуйте, {name}! 👋\n\n"
            "🎁 За подтверждённый голос "
            "{vote_reward} сум.\n"
            "👥 Реферальный бонус: {ref_reward} сум.\n\n"
            "Выберите раздел:"
        ),

        "projects": "📌 Проекты",
        "news": "📰 Новости",
        "balance": "💰 Баланс",
        "referral": "🔗 Реферальная ссылка",
        "withdraw": "💸 Вывести деньги",
        "help": "❓ Помощь",
        "language": "🌐 Язык",
        "group_add": "👥 Добавить в группу",

        "statistics": "📊 Статистика",
        "add_project": "➕ Добавить проект",
        "add_news": "📰 Добавить новость",
        "broadcast": "📢 Рассылка",
        "withdrawals": "💸 Заявки",
        "admin_panel": "⚙️ Админ-панель",

        "back": "🔙 Назад",
        "cancel": "❌ Отмена",

        "select_language": "🌐 Выберите язык:",
        "language_saved": "✅ Язык изменён.",

        "select_project": "📌 Выберите проект:",
        "no_projects": "📌 Пока проектов нет.",

        "project_name": "📝 Отправьте название проекта:",
        "project_link": "🔗 Отправьте ссылку проекта:",
        "project_created": "✅ Проект добавлен!",
        "invalid_link": "❌ Неверная ссылка.",
        "project_not_found": "❌ Проект не найден.",
        "open_project": "🔗 Открыть проект",
        "vote": "🗳 Голосовать",

        "vote_phone": (
            "📞 <b>Введите номер телефона для голосования:</b>\n\n"
            "Номер должен быть в формате "
            "<b>+998991234567</b> или <b>991234567</b>."
        ),

        "invalid_phone": "❌ Неверный номер телефона.",

        "vote_sent": (
            "✅ Номер принят.\n\n"
            "⏳ Запрос отправлен администратору.\n"
            "После подтверждения вам будет начислено "
            "{reward} сум."
        ),

        "vote_already_pending":
            "⏳ Ваш запрос уже находится на рассмотрении.",

        "already_voted":
            "⚠️ Вы уже голосовали за этот проект.",

        "admin_only":
            "❌ Только для администратора.",

        "help_text": "❓ Используйте кнопки меню.",

        "balance_text": (
            "💰 <b>Ваш баланс</b>\n\n"
            "💵 Баланс: <b>{balance} сум</b>\n"
            "📈 Заработано: {earned} сум\n"
            "💸 Выведено: {withdrawn} сум"
        ),

        "referral_text": (
            "🔗 <b>Ваша ссылка:</b>\n\n"
            "<code>{link}</code>\n\n"
            "👥 Приглашено: {count}\n"
            "💰 Доход: {earned} сум"
        ),

        "news_empty": "📰 Новостей пока нет.",
        "send_news": "📰 Отправьте новость.",
        "news_saved": "✅ Новость сохранена.",
        "send_broadcast": "📢 Отправьте сообщение для рассылки.",

        "broadcast_result": (
            "📢 Рассылка завершена.\n\n"
            "✅ Отправлено: {success}\n"
            "🚫 Заблокировали: {blocked}\n"
            "⚠️ Ошибок: {failed}"
        ),

        "stats": (
            "📊 <b>Статистика</b>\n\n"
            "👥 Пользователи: {users}\n"
            "🗳 Голоса: {votes}\n"
            "⏳ Ожидающие голоса: {pending_votes}\n"
            "📌 Проекты: {projects}\n"
            "👁 Просмотры: {views}\n"
            "📰 Новости: {news}\n"
            "💰 Баланс: {balance} сум\n"
            "💸 Выведено: {withdrawn} сум"
        ),

        "withdraw_amount": (
            "💸 <b>Вывод</b>\n\n"
            "Минимум: {minimum} сум\n"
            "Баланс: {balance} сум\n\n"
            "Введите сумму:"
        ),

        "invalid_amount": "❌ Неверная сумма.",
        "not_enough": "❌ Недостаточно средств.",

        "withdraw_info":
            "💳 Отправьте реквизиты для выплаты.",

        "withdraw_created": (
            "✅ Заявка создана.\n"
            "💰 Сумма: {amount} сум\n"
            "🆔 #{request_id}"
        ),

        "no_pending_withdrawals":
            "⏳ Нет ожидающих заявок.",

        "back_menu":
            "🔙 Вы вернулись в главное меню.",
    },
}


# =========================================================
# FSM
# =========================================================

class ProjectStates(StatesGroup):
    name = State()
    link = State()


class NewsStates(StatesGroup):
    content = State()


class BroadcastStates(StatesGroup):
    content = State()


class VoteStates(StatesGroup):
    phone = State()


class WithdrawStates(StatesGroup):
    amount = State()
    info = State()


# =========================================================
# DATABASE
# =========================================================

def db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def init_db():

    with closing(db()) as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                language TEXT DEFAULT 'uz',
                phone TEXT,
                balance INTEGER DEFAULT 0,
                total_earned INTEGER DEFAULT 0,
                total_withdrawn INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name_uz TEXT,
                name_ru TEXT,
                url TEXT,
                click_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                project_id INTEGER NOT NULL,
                phone TEXT NOT NULL,
                reward INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                admin_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                approved_at TIMESTAMP,
                UNIQUE(user_id, project_id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                message_id INTEGER,
                text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER,
                referred_id INTEGER UNIQUE,
                bonus INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                type TEXT,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS withdrawals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                payment_info TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_votes_user_project
            ON votes(user_id, project_id)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_votes_status
            ON votes(status)
        """)

        conn.commit()

    logger.info("DATABASE TAYYOR")


# =========================================================
# YORDAMCHI
# =========================================================

def money(amount):
    return f"{int(amount or 0):,}".replace(",", " ")


def is_admin(user_id):
    return user_id in ADMIN_IDS


def add_user(message: Message):

    if not message.from_user:
        return

    with closing(db()) as conn:

        conn.execute("""
            INSERT INTO users (
                user_id,
                username,
                first_name
            )
            VALUES (?, ?, ?)

            ON CONFLICT(user_id)
            DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name
        """, (
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name
        ))

        conn.commit()


def get_lang(user_id):

    with closing(db()) as conn:

        row = conn.execute(
            "SELECT language FROM users WHERE user_id=?",
            (user_id,)
        ).fetchone()

        if row and row["language"] in ("uz", "ru"):
            return row["language"]

    return "uz"


def set_lang(user_id, language):

    with closing(db()) as conn:

        conn.execute(
            "UPDATE users SET language=? WHERE user_id=?",
            (language, user_id)
        )

        conn.commit()


def user_menu(language):

    t = TEXTS[language]

    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=t["projects"]),
                KeyboardButton(text=t["news"])
            ],
            [
                KeyboardButton(text=t["balance"]),
                KeyboardButton(text=t["referral"])
            ],
            [
                KeyboardButton(text=t["withdraw"]),
                KeyboardButton(text=t["help"])
            ],
            [
                KeyboardButton(text=t["language"])
            ],
            [
                KeyboardButton(text=t["group_add"])
            ],
        ],
        resize_keyboard=True
    )


def admin_menu(language):

    t = TEXTS[language]

    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=t["statistics"])
            ],
            [
                KeyboardButton(text=t["add_project"]),
                KeyboardButton(text=t["add_news"])
            ],
            [
                KeyboardButton(text=t["broadcast"])
            ],
            [
                KeyboardButton(text=t["withdrawals"])
            ],
            [
                KeyboardButton(text=t["back"])
            ],
        ],
        resize_keyboard=True
    )


def main_menu(user_id, language):

    if is_admin(user_id):
        return admin_menu(language)

    return user_menu(language)


def cancel_menu(language):

    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text=TEXTS[language]["cancel"]
                )
            ]
        ],
        resize_keyboard=True
    )


def language_menu():

    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🇺🇿 O‘zbek"),
                KeyboardButton(text="🇷🇺 Русский")
            ],
            [
                KeyboardButton(text="🔙 Orqaga")
            ],
        ],
        resize_keyboard=True
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

    add_user(message)

    language = get_lang(message.from_user.id)

    name = message.from_user.first_name or "Foydalanuvchi"

    await message.answer(
        TEXTS[language]["welcome"].format(
            name=escape(name),
            vote_reward=money(VOTE_REWARD),
            ref_reward=money(REFERRAL_REWARD)
        ),
        reply_markup=main_menu(
            message.from_user.id,
            language
        )
    )


# =========================================================
# BACK
# =========================================================

@dp.message(F.text.in_({
    "🔙 Orqaga",
    "🔙 Назад"
}))
async def back_handler(message: Message, state: FSMContext):

    await state.clear()

    add_user(message)

    language = get_lang(message.from_user.id)

    await message.answer(
        TEXTS[language]["back_menu"],
        reply_markup=main_menu(
            message.from_user.id,
            language
        )
    )


# =========================================================
# LANGUAGE
# =========================================================

@dp.message(F.text.in_({
    "🌐 Til",
    "🌐 Язык"
}))
async def language_handler(message: Message):

    add_user(message)

    language = get_lang(message.from_user.id)

    await message.answer(
        TEXTS[language]["select_language"],
        reply_markup=language_menu()
    )


@dp.message(F.text == "🇺🇿 O‘zbek")
async def uz_handler(message: Message):

    add_user(message)

    set_lang(message.from_user.id, "uz")

    await message.answer(
        TEXTS["uz"]["language_saved"],
        reply_markup=main_menu(
            message.from_user.id,
            "uz"
        )
    )


@dp.message(F.text == "🇷🇺 Русский")
async def ru_handler(message: Message):

    add_user(message)

    set_lang(message.from_user.id, "ru")

    await message.answer(
        TEXTS["ru"]["language_saved"],
        reply_markup=main_menu(
            message.from_user.id,
            "ru"
        )
    )


# =========================================================
# PROJECTS
# =========================================================

@dp.message(F.text.in_({
    "📌 Loyihalar",
    "📌 Проекты"
}))
async def projects_handler(message: Message):

    add_user(message)

    language = get_lang(message.from_user.id)
    t = TEXTS[language]

    with closing(db()) as conn:

        rows = conn.execute("""
            SELECT id, name_uz, name_ru
            FROM projects
            ORDER BY id DESC
        """).fetchall()

    if not rows:

        await message.answer(
            t["no_projects"],
            reply_markup=user_menu(language)
        )

        return

    buttons = []

    for row in rows:

        name = (
            row["name_uz"]
            if language == "uz"
            else row["name_ru"]
        )

        name = name or row["name_uz"] or row["name_ru"]

        buttons.append([
            InlineKeyboardButton(
                text=f"📌 {name}",
                callback_data=f"project:{row['id']}"
            )
        ])

    await message.answer(
        t["select_project"],
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )


@dp.callback_query(F.data.startswith("project:"))
async def project_handler(callback: CallbackQuery):

    project_id = int(
        callback.data.split(":")[1]
    )

    language = get_lang(callback.from_user.id)
    t = TEXTS[language]

    with closing(db()) as conn:

        row = conn.execute("""
            SELECT *
            FROM projects
            WHERE id=?
        """, (project_id,)).fetchone()

        if row:

            conn.execute("""
                UPDATE projects
                SET click_count=COALESCE(click_count,0)+1
                WHERE id=?
            """, (project_id,))

            conn.commit()

    if not row:

        await callback.answer(
            t["project_not_found"],
            show_alert=True
        )

        return

    name = (
        row["name_uz"]
        if language == "uz"
        else row["name_ru"]
    )

    buttons = []

    if row["url"]:

        buttons.append([
            InlineKeyboardButton(
                text=t["open_project"],
                url=row["url"]
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text=t["vote"],
            callback_data=f"vote:{project_id}"
        )
    ])

    await callback.message.answer(
        f"📌 <b>{escape(name)}</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )

    await callback.answer()


# =========================================================
# VOTE
# =========================================================

@dp.callback_query(F.data.startswith("vote:"))
async def vote_start(
    callback: CallbackQuery,
    state: FSMContext
):

    project_id = int(
        callback.data.split(":")[1]
    )

    language = get_lang(callback.from_user.id)
    t = TEXTS[language]

    with closing(db()) as conn:

        project = conn.execute(
            "SELECT id FROM projects WHERE id=?",
            (project_id,)
        ).fetchone()

        if not project:

            await callback.answer(
                t["project_not_found"],
                show_alert=True
            )

            return

        vote = conn.execute("""
            SELECT id, status
            FROM votes
            WHERE user_id=? AND project_id=?
        """, (
            callback.from_user.id,
            project_id
        )).fetchone()

    if vote:

        if vote["status"] == "pending":

            await callback.answer(
                t["vote_already_pending"],
                show_alert=True
            )

        else:

            await callback.answer(
                t["already_voted"],
                show_alert=True
            )

        return

    await state.clear()

    await state.update_data(
        project_id=project_id
    )

    await state.set_state(
        VoteStates.phone
    )

    await callback.message.answer(
        t["vote_phone"],
        parse_mode="HTML",
        reply_markup=cancel_menu(language)
    )

    await callback.answer()


# =========================================================
# PHONE VALIDATION
# =========================================================

def normalize_phone(text):

    value = text.strip()

    value = value.replace(" ", "")
    value = value.replace("-", "")
    value = value.replace("(", "")
    value = value.replace(")", "")

    if value.startswith("+998"):

        if len(value) == 13 and value[1:].isdigit():
            return value

    elif value.startswith("998"):

        if len(value) == 12 and value.isdigit():
            return "+" + value

    elif len(value) == 9 and value.isdigit():

        return "+998" + value

    return None


# =========================================================
# VOTE PHONE
# =========================================================

@dp.message(VoteStates.phone)
async def vote_phone_handler(
    message: Message,
    state: FSMContext
):

    language = get_lang(message.from_user.id)
    t = TEXTS[language]

    if not message.text:

        await message.answer(
            t["invalid_phone"]
        )

        return

    phone = normalize_phone(
        message.text
    )

    if not phone:

        await message.answer(
            t["invalid_phone"]
        )

        return

    data = await state.get_data()

    project_id = data.get(
        "project_id"
    )

    if not project_id:

        await state.clear()

        return

    with closing(db()) as conn:

        existing = conn.execute("""
            SELECT id, status
            FROM votes
            WHERE user_id=? AND project_id=?
        """, (
            message.from_user.id,
            project_id
        )).fetchone()

        if existing:

            await state.clear()

            await message.answer(
                t["vote_already_pending"]
                if existing["status"] == "pending"
                else t["already_voted"],
                reply_markup=user_menu(language)
            )

            return

        conn.execute("""
            INSERT INTO votes (
                user_id,
                project_id,
                phone,
                reward,
                status
            )
            VALUES (?, ?, ?, ?, 'pending')
        """, (
            message.from_user.id,
            project_id,
            phone,
            VOTE_REWARD
        ))

        conn.execute("""
            UPDATE users
            SET phone=?
            WHERE user_id=?
        """, (
            phone,
            message.from_user.id
        ))

        vote_id = conn.execute(
            "SELECT last_insert_rowid()"
        ).fetchone()[0]

        conn.commit()

    await state.clear()

    await message.answer(
        t["vote_sent"].format(
            reward=money(VOTE_REWARD)
        ),
        reply_markup=user_menu(language)
    )

    # =====================================================
    # ADMINLARGA OVOZ SO'ROVI
    # =====================================================

    username = (
        f"@{message.from_user.username}"
        if message.from_user.username
        else "Username yo'q"
    )

    admin_text = (
        "🗳 <b>YANGI OVOZ SO'ROVI</b>\n\n"
        f"🆔 So'rov: <b>#{vote_id}</b>\n"
        f"👤 Foydalanuvchi: {escape(username)}\n"
        f"🆔 User ID: <code>{message.from_user.id}</code>\n"
        f"📞 Telefon: <code>{escape(phone)}</code>\n"
        f"📌 Loyiha ID: <b>{project_id}</b>\n"
        f"💰 Mukofot: <b>{money(VOTE_REWARD)} so'm</b>\n\n"
        "Foydalanuvchi telefon raqamini yubordi.\n"
        "Admin ovozni tekshirib, tasdiqlashi yoki rad etishi mumkin."
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ TASDIQLASH",
                    callback_data=f"vote_ok:{vote_id}"
                ),
                InlineKeyboardButton(
                    text="❌ RAD ETISH",
                    callback_data=f"vote_no:{vote_id}"
                )
            ]
        ]
    )

    for admin_id in ADMIN_IDS:

        try:

            await bot.send_message(
                admin_id,
                admin_text,
                parse_mode="HTML",
                reply_markup=keyboard
            )

        except Exception as e:

            logger.error(
                "Admin xabari yuborilmadi: %s",
                e
            )


# =========================================================
# ADMIN VOTE APPROVE
# =========================================================

@dp.callback_query(
    F.data.startswith("vote_ok:")
)
async def vote_approve(
    callback: CallbackQuery
):

    if not is_admin(callback.from_user.id):

        await callback.answer(
            "Faqat admin.",
            show_alert=True
        )

        return

    vote_id = int(
        callback.data.split(":")[1]
    )

    with closing(db()) as conn:

        conn.execute("BEGIN IMMEDIATE")

        vote = conn.execute("""
            SELECT
                user_id,
                project_id,
                reward,
                status
            FROM votes
            WHERE id=?
        """, (vote_id,)).fetchone()

        if not vote or vote["status"] != "pending":

            conn.rollback()

            await callback.answer(
                "So'rov allaqachon ko'rib chiqilgan.",
                show_alert=True
            )

            return

        conn.execute("""
            UPDATE votes
            SET status='approved',
                admin_id=?,
                approved_at=CURRENT_TIMESTAMP
            WHERE id=? AND status='pending'
        """, (
            callback.from_user.id,
            vote_id
        ))

        conn.execute("""
            UPDATE users
            SET balance=COALESCE(balance,0)+?,
                total_earned=COALESCE(total_earned,0)+?
            WHERE user_id=?
        """, (
            vote["reward"],
            vote["reward"],
            vote["user_id"]
        ))

        conn.execute("""
            INSERT INTO transactions (
                user_id,
                amount,
                type,
                description
            )
            VALUES (?, ?, 'vote', ?)
        """, (
            vote["user_id"],
            vote["reward"],
            f"Ovoz tasdiqlandi #{vote_id}"
        ))

        conn.commit()

    # Foydalanuvchiga xabar
    try:

        lang = get_lang(
            vote["user_id"]
        )

        await bot.send_message(
            vote["user_id"],
            (
                "🎉 <b>Ovozingiz tasdiqlandi!</b>\n\n"
                f"💰 Balansingizga "
                f"<b>{money(vote['reward'])} so'm</b> qo'shildi."
            ),
            parse_mode="HTML"
        )

    except Exception as e:

        logger.warning(
            "User notification error: %s",
            e
        )

    try:

        await callback.message.edit_reply_markup(
            reply_markup=None
        )

    except Exception:
        pass

    await callback.message.answer(
        f"✅ Ovoz #{vote_id} tasdiqlandi.\n"
        f"💰 +{money(vote['reward'])} so'm"
    )

    await callback.answer("Tasdiqlandi.")


# =========================================================
# ADMIN VOTE REJECT
# =========================================================

@dp.callback_query(
    F.data.startswith("vote_no:")
)
async def vote_reject(
    callback: CallbackQuery
):

    if not is_admin(callback.from_user.id):

        await callback.answer(
            "Faqat admin.",
            show_alert=True
        )

        return

    vote_id = int(
        callback.data.split(":")[1]
    )

    with closing(db()) as conn:

        vote = conn.execute("""
            SELECT
                user_id,
                status
            FROM votes
            WHERE id=?
        """, (vote_id,)).fetchone()

        if not vote or vote["status"] != "pending":

            await callback.answer(
                "So'rov allaqachon ko'rib chiqilgan.",
                show_alert=True
            )

            return

        conn.execute("""
            UPDATE votes
            SET status='rejected',
                admin_id=?
            WHERE id=? AND status='pending'
        """, (
            callback.from_user.id,
            vote_id
        ))

        conn.commit()

    try:

        lang = get_lang(
            vote["user_id"]
        )

        await bot.send_message(
            vote["user_id"],
            (
                "❌ <b>Ovoz so'rovingiz rad etildi.</b>\n\n"
                "Balansingizga pul qo'shilmadi."
            ),
            parse_mode="HTML"
        )

    except Exception:
        pass

    try:

        await callback.message.edit_reply_markup(
            reply_markup=None
        )

    except Exception:
        pass

    await callback.message.answer(
        f"❌ Ovoz #{vote_id} rad etildi."
    )

    await callback.answer("Rad etildi.")


# =========================================================
# BALANCE
# =========================================================

@dp.message(F.text.in_({
    "💰 Balans",
    "💰 Баланс"
}))
async def balance_handler(message: Message):

    add_user(message)

    language = get_lang(
        message.from_user.id
    )

    with closing(db()) as conn:

        row = conn.execute("""
            SELECT
                balance,
                total_earned,
                total_withdrawn
            FROM users
            WHERE user_id=?
        """, (
            message.from_user.id,
        )).fetchone()

    await message.answer(
        TEXTS[language]["balance_text"].format(
            balance=money(row["balance"]),
            earned=money(row["total_earned"]),
            withdrawn=money(row["total_withdrawn"])
        ),
        parse_mode="HTML",
        reply_markup=user_menu(language)
    )


# =========================================================
# REFERRAL
# =========================================================

@dp.message(F.text.in_({
    "🔗 Referal ssilka",
    "🔗 Реферальная ссылка"
}))
async def referral_handler(message: Message):

    add_user(message)

    language = get_lang(
        message.from_user.id
    )

    me = await bot.get_me()

    link = (
        f"https://t.me/{me.username}"
        f"?start=ref_{message.from_user.id}"
    )

    with closing(db()) as conn:

        count = conn.execute("""
            SELECT COUNT(*) AS c
            FROM referrals
            WHERE referrer_id=?
        """, (
            message.from_user.id,
        )).fetchone()["c"]

        earned = conn.execute("""
            SELECT COALESCE(SUM(bonus),0) AS s
            FROM referrals
            WHERE referrer_id=?
              AND status='rewarded'
        """, (
            message.from_user.id,
        )).fetchone()["s"]

    await message.answer(
        TEXTS[language]["referral_text"].format(
            link=escape(link),
            count=count,
            earned=money(earned)
        ),
        parse_mode="HTML",
        reply_markup=user_menu(language)
    )


# =========================================================
# NEWS
# =========================================================

@dp.message(F.text.in_({
    "📰 Yangiliklar",
    "📰 Новости"
}))
async def news_handler(message: Message):

    add_user(message)

    language = get_lang(
        message.from_user.id
    )

    with closing(db()) as conn:

        rows = conn.execute("""
            SELECT chat_id, message_id
            FROM news
            ORDER BY id DESC
            LIMIT 10
        """).fetchall()

    if not rows:

        await message.answer(
            TEXTS[language]["news_empty"],
            reply_markup=user_menu(language)
        )

        return

    for row in rows:

        try:

            await bot.copy_message(
                chat_id=message.chat.id,
                from_chat_id=row["chat_id"],
                message_id=row["message_id"]
            )

        except Exception as e:

            logger.warning(
                "News copy error: %s",
                e
            )


# =========================================================
# ADMIN COMMAND
# =========================================================

@dp.message(Command("admin"))
async def admin_handler(message: Message):

    add_user(message)

    if not is_admin(
        message.from_user.id
    ):

        await message.answer(
            TEXTS[get_lang(message.from_user.id)]["admin_only"]
        )

        return

    language = get_lang(
        message.from_user.id
    )

    await message.answer(
        TEXTS[language]["admin_panel"],
        reply_markup=admin_menu(language)
    )


# =========================================================
# ADD PROJECT
# =========================================================

@dp.message(F.text.in_({
    "➕ Loyiha qo'shish",
    "➕ Loyiha qo‘shish",
    "➕ Добавить проект"
}))
async def project_start(
    message: Message,
    state: FSMContext
):

    if not is_admin(
        message.from_user.id
    ):

        await message.answer(
            TEXTS[get_lang(message.from_user.id)]["admin_only"]
        )

        return

    language = get_lang(
        message.from_user.id
    )

    await state.clear()

    await state.set_state(
        ProjectStates.name
    )

    await message.answer(
        TEXTS[language]["project_name"],
        reply_markup=cancel_menu(language)
    )


@dp.message(ProjectStates.name)
async def project_name(
    message: Message,
    state: FSMContext
):

    if not is_admin(
        message.from_user.id
    ):

        return

    language = get_lang(
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
            "❌ Loyiha nomi juda qisqa."
        )

        return

    await state.update_data(
        name=name
    )

    await state.set_state(
        ProjectStates.link
    )

    await message.answer(
        TEXTS[language]["project_link"]
    )


@dp.message(ProjectStates.link)
async def project_link(
    message: Message,
    state: FSMContext
):

    if not is_admin(
        message.from_user.id
    ):

        return

    language = get_lang(
        message.from_user.id
    )

    if not message.text:
        return

    url = message.text.strip()

    parsed = urlparse(url)

    if parsed.scheme not in (
        "http",
        "https"
    ) or not parsed.netloc:

        await message.answer(
            TEXTS[language]["invalid_link"]
        )

        return

    data = await state.get_data()

    name = data.get("name")

    with closing(db()) as conn:

        conn.execute("""
            INSERT INTO projects (
                name_uz,
                name_ru,
                url
            )
            VALUES (?, ?, ?)
        """, (
            name,
            name,
            url
        ))

        conn.commit()

    await state.clear()

    await message.answer(
        TEXTS[language]["project_created"],
        reply_markup=admin_menu(language)
    )


# =========================================================
# ADMIN ADD NEWS
# =========================================================

@dp.message(F.text.in_({
    "📰 Yangilik qo'shish",
    "📰 Yangilik qo‘shish",
    "📰 Добавить новость"
}))
async def news_add_start(
    message: Message,
    state: FSMContext
):

    if not is_admin(
        message.from_user.id
    ):

        await message.answer(
            TEXTS[get_lang(message.from_user.id)]["admin_only"]
        )

        return

    language = get_lang(
        message.from_user.id
    )

    await state.clear()

    await state.set_state(
        NewsStates.content
    )

    await message.answer(
        TEXTS[language]["send_news"],
        reply_markup=cancel_menu(language)
    )


# =========================================================
# BROADCAST
# =========================================================

async def broadcast(
    chat_id,
    message_id
):

    success = 0
    blocked = 0
    failed = 0

    with closing(db()) as conn:

        users = conn.execute(
            "SELECT user_id FROM users"
        ).fetchall()

    for row in users:

        try:

            await bot.copy_message(
                chat_id=row["user_id"],
                from_chat_id=chat_id,
                message_id=message_id
            )

            success += 1

            await asyncio.sleep(0.04)

        except TelegramForbiddenError:

            blocked += 1

            with closing(db()) as conn:

                conn.execute(
                    "DELETE FROM users WHERE user_id=?",
                    (row["user_id"],)
                )

                conn.commit()

        except TelegramRetryAfter as e:

            await asyncio.sleep(
                e.retry_after
            )

            try:

                await bot.copy_message(
                    chat_id=row["user_id"],
                    from_chat_id=chat_id,
                    message_id=message_id
                )

                success += 1

            except Exception:

                failed += 1

        except Exception:

            failed += 1

    return success, blocked, failed


@dp.message(NewsStates.content)
async def news_add(
    message: Message,
    state: FSMContext
):

    if not is_admin(
        message.from_user.id
    ):

        await state.clear()

        return

    with closing(db()) as conn:

        conn.execute("""
            INSERT INTO news (
                chat_id,
                message_id,
                text
            )
            VALUES (?, ?, ?)
        """, (
            message.chat.id,
            message.message_id,
            message.text or message.caption or ""
        ))

        conn.commit()

    await broadcast(
        message.chat.id,
        message.message_id
    )

    await state.clear()

    language = get_lang(
        message.from_user.id
    )

    await message.answer(
        TEXTS[language]["news_saved"],
        reply_markup=admin_menu(language)
    )


@dp.message(F.text.in_({
    "📢 Reklama tarqatish",
    "📢 Рассылка"
}))
async def broadcast_start(
    message: Message,
    state: FSMContext
):

    if not is_admin(
        message.from_user.id
    ):

        await message.answer(
            TEXTS[get_lang(message.from_user.id)]["admin_only"]
        )

        return

    language = get_lang(
        message.from_user.id
    )

    await state.clear()

    await state.set_state(
        BroadcastStates.content
    )

    await message.answer(
        TEXTS[language]["send_broadcast"],
        reply_markup=cancel_menu(language)
    )


@dp.message(BroadcastStates.content)
async def broadcast_handler(
    message: Message,
    state: FSMContext
):

    if not is_admin(
        message.from_user.id
    ):

        await state.clear()

        return

    success, blocked, failed = await broadcast(
        message.chat.id,
        message.message_id
    )

    await state.clear()

    language = get_lang(
        message.from_user.id
    )

    await message.answer(
        TEXTS[language]["broadcast_result"].format(
            success=success,
            blocked=blocked,
            failed=failed
        ),
        reply_markup=admin_menu(language)
    )


# =========================================================
# STATISTICS
# =========================================================

@dp.message(F.text.in_({
    "📊 Statistika",
    "📊 Статистика"
}))
async def statistics(message: Message):

    if not is_admin(
        message.from_user.id
    ):

        await message.answer(
            TEXTS[get_lang(message.from_user.id)]["admin_only"]
        )

        return

    language = get_lang(
        message.from_user.id
    )

    with closing(db()) as conn:

        users = conn.execute(
            "SELECT COUNT(*) c FROM users"
        ).fetchone()["c"]

        votes = conn.execute(
            "SELECT COUNT(*) c FROM votes WHERE status='approved'"
        ).fetchone()["c"]

        pending_votes = conn.execute(
            "SELECT COUNT(*) c FROM votes WHERE status='pending'"
        ).fetchone()["c"]

        projects = conn.execute(
            "SELECT COUNT(*) c FROM projects"
        ).fetchone()["c"]

        views = conn.execute(
            "SELECT COALESCE(SUM(click_count),0) c FROM projects"
        ).fetchone()["c"]

        news = conn.execute(
            "SELECT COUNT(*) c FROM news"
        ).fetchone()["c"]

        balance = conn.execute(
            "SELECT COALESCE(SUM(balance),0) c FROM users"
        ).fetchone()["c"]

        withdrawn = conn.execute(
            "SELECT COALESCE(SUM(total_withdrawn),0) c FROM users"
        ).fetchone()["c"]

    await message.answer(
        TEXTS[language]["stats"].format(
            users=users,
            votes=votes,
            pending_votes=pending_votes,
            projects=projects,
            views=views,
            news=news,
            balance=money(balance),
            withdrawn=money(withdrawn)
        ),
        reply_markup=admin_menu(language)
    )


# =========================================================
# WITHDRAW
# =========================================================

@dp.message(F.text.in_({
    "💸 Pul yechish",
    "💸 Вывести деньги"
}))
async def withdraw_start(
    message: Message,
    state: FSMContext
):

    add_user(message)

    language = get_lang(
        message.from_user.id
    )

    with closing(db()) as conn:

        row = conn.execute("""
            SELECT balance
            FROM users
            WHERE user_id=?
        """, (
            message.from_user.id,
        )).fetchone()

    balance = row["balance"] or 0

    if balance < MIN_WITHDRAW:

        await message.answer(
            f"❌ Minimal yechish: "
            f"{money(MIN_WITHDRAW)} so'm\n"
            f"💰 Balansingiz: {money(balance)} so'm",
            reply_markup=user_menu(language)
        )

        return

    await state.clear()

    await state.set_state(
        WithdrawStates.amount
    )

    await message.answer(
        TEXTS[language]["withdraw_amount"].format(
            minimum=money(MIN_WITHDRAW),
            balance=money(balance)
        ),
        parse_mode="HTML",
        reply_markup=cancel_menu(language)
    )


@dp.message(WithdrawStates.amount)
async def withdraw_amount(
    message: Message,
    state: FSMContext
):

    language = get_lang(
        message.from_user.id
    )

    if not message.text:

        return

    value = message.text.replace(
        " ",
        ""
    )

    if not value.isdigit():

        await message.answer(
            TEXTS[language]["invalid_amount"]
        )

        return

    amount = int(value)

    if amount < MIN_WITHDRAW:

        await message.answer(
            f"❌ Minimal summa: "
            f"{money(MIN_WITHDRAW)} so'm"
        )

        return

    with closing(db()) as conn:

        row = conn.execute(
            "SELECT balance FROM users WHERE user_id=?",
            (message.from_user.id,)
        ).fetchone()

    if amount > row["balance"]:

        await message.answer(
            TEXTS[language]["not_enough"]
        )

        return

    await state.update_data(
        amount=amount
    )

    await state.set_state(
        WithdrawStates.info
    )

    await message.answer(
        TEXTS[language]["withdraw_info"]
    )


@dp.message(WithdrawStates.info)
async def withdraw_info(
    message: Message,
    state: FSMContext
):

    if not message.text:

        return

    language = get_lang(
        message.from_user.id
    )

    data = await state.get_data()

    amount = data.get("amount")

    if not amount:

        await state.clear()

        return

    payment_info = message.text.strip()

    with closing(db()) as conn:

        conn.execute("BEGIN IMMEDIATE")

        row = conn.execute("""
            SELECT balance
            FROM users
            WHERE user_id=?
        """, (
            message.from_user.id,
        )).fetchone()

        if not row or row["balance"] < amount:

            conn.rollback()

            await state.clear()

            await message.answer(
                TEXTS[language]["not_enough"],
                reply_markup=user_menu(language)
            )

            return

        conn.execute("""
            UPDATE users
            SET balance=balance-?
            WHERE user_id=?
        """, (
            amount,
            message.from_user.id
        ))

        cur = conn.execute("""
            INSERT INTO withdrawals (
                user_id,
                amount,
                payment_info,
                status
            )
            VALUES (?, ?, ?, 'pending')
        """, (
            message.from_user.id,
            amount,
            payment_info
        ))

        request_id = cur.lastrowid

        conn.commit()

    await state.clear()

    await message.answer(
        TEXTS[language]["withdraw_created"].format(
            amount=money(amount),
            request_id=request_id
        ),
        reply_markup=user_menu(language)
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

    language = get_lang(
        message.from_user.id
    )

    await message.answer(
        TEXTS[language]["back_menu"],
        reply_markup=main_menu(
            message.from_user.id,
            language
        )
    )


@dp.message(Command("cancel"))
async def cancel_command(
    message: Message,
    state: FSMContext
):

    await state.clear()

    language = get_lang(
        message.from_user.id
    )

    await message.answer(
        TEXTS[language]["back_menu"],
        reply_markup=main_menu(
            message.from_user.id,
            language
        )
    )


# =========================================================
# HELP
# =========================================================

@dp.message(F.text.in_({
    "❓ Yordam",
    "❓ Помощь"
}))
async def help_handler(message: Message):

    add_user(message)

    language = get_lang(
        message.from_user.id
    )

    await message.answer(
        TEXTS[language]["help_text"],
        parse_mode="HTML",
        reply_markup=user_menu(language)
    )


# =========================================================
# GROUP
# =========================================================

@dp.message(F.text.in_({
    "👥 Guruhga qo'shish",
    "👥 Guruhga qo‘shish",
    "👥 Добавить в группу"
}))
async def group_handler(message: Message):

    language = get_lang(
        message.from_user.id
    )

    me = await bot.get_me()

    link = (
        f"https://t.me/{me.username}"
        f"?startgroup=true"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=TEXTS[language]["group_add"],
                    url=link
                )
            ]
        ]
    )

    await message.answer(
        "👥 Botni guruhga qo'shish:",
        reply_markup=keyboard
    )


# =========================================================
# UNKNOWN
# =========================================================

@dp.message()
async def unknown(message: Message):

    if not message.from_user:

        return

    add_user(message)

    language = get_lang(
        message.from_user.id
    )

    await message.answer(
        "❗ Iltimos, menyudagi tugmalardan foydalaning.",
        reply_markup=main_menu(
            message.from_user.id,
            language
        )
    )


# =========================================================
# MAIN
# =========================================================

async def main():

    print(
        "MAIN.PY ISHLAYAPTI",
        flush=True
    )

    init_db()

    print(
        "DATABASE TAYYOR",
        flush=True
    )

    me = await bot.get_me()

    print(
        f"BOT ULANDI: @{me.username}",
        flush=True
    )

    print(
        "POLLING BOSHLANMOQDA",
        flush=True
    )

    await dp.start_polling(
        bot
    )


if __name__ == "__main__":

    try:

        asyncio.run(main())

    except KeyboardInterrupt:

        print(
            "BOT TO'XTATILDI",
            flush=True
        )