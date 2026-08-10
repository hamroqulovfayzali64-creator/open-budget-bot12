# =========================================================
# MAIN.PY — OPEN BUDGET BOT
# =========================================================

import asyncio
import logging
import os
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
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter


# =========================================================
# 🤖 BOT TOKENI
# =========================================================
# Railway ishlatayotgan bo'lsangiz:
# Railway -> Variables -> BOT_TOKEN -> tokeningizni yozing.
#
# Tokenni hech kimga yubormang!

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN Railway Environment Variables ichida qo'yilmagan!"
    )


# =========================================================
# 👤 ADMINLAR
# =========================================================

ADMIN_IDS = {
    7998053914,
}


# =========================================================
# 💰 SOZLAMALAR
# =========================================================

VOTE_REWARD = 30_000
REFERRAL_REWARD = 5_000
MIN_WITHDRAW = 30_000


# =========================================================
# 📁 DATABASE
# =========================================================

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "bot.db"


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)


# =========================================================
# BOT
# =========================================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# =========================================================
# MATNLAR
# =========================================================

TEXTS = {
    "uz": {

        "welcome": (
            "Assalomu alaykum, {name}! 👋\n\n"
            "🎁 Har bir tasdiqlangan ovoz uchun {vote_reward} so'm.\n"
            "👥 Referal bonus: {ref_reward} so'm.\n\n"
            "Kerakli bo'limni tanlang:"
        ),

        "projects": "📌 Loyihalar",
        "news": "📰 Yangiliklar",
        "balance": "💰 Balans",
        "referral": "🔗 Referal ssilka",

        # USER
        "withdraw": "💰 Pulni yechib olish",

        "help": "❓ Yordam",
        "language": "🌐 Til",
        "group_add": "👥 Guruhga qo'shish",

        # ADMIN
        "statistics": "📊 Statistika",
        "add_project": "➕ Loyiha qo'shish",
        "add_news": "📰 Yangilik qo'shish",
        "broadcast": "📢 Reklama tarqatish",

        # O'ZGARTIRILDI
        "withdrawals": "💰 Pulni yechib olish",

        "manage": "🗑 Kontent boshqaruvi",

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

        "project_created": "✅ Loyiha qo'shildi va saqlandi!",
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
            "Masalan: +998991234567"
        ),

        "vote_sent": (
            "✅ Telefon raqamingiz qabul qilindi.\n\n"
            "⏳ Ovoz berish so'rovingiz administratorga yuborildi.\n"
            "Admin tasdiqlaganidan keyin {reward} so'm "
            "balansingizga qo'shiladi."
        ),

        "vote_already_pending": (
            "⏳ Sizning bu loyiha bo'yicha ovoz so'rovingiz "
            "allaqachon ko'rib chiqilmoqda."
        ),

        "already_voted":
            "⚠️ Siz bu loyihaga allaqachon ovoz bergansiz.",

        "admin_only":
            "❌ Bu bo'lim faqat administrator uchun.",

        "help_text": (
            "❓ <b>Yordam</b>\n\n"
            "📌 Loyihalar — loyihalarni ko'rish.\n"
            "🗳 Ovoz berish — loyiha uchun ovoz berish.\n"
            "💰 Balans — hisobingizni ko'rish.\n"
            "🔗 Referal — do'st taklif qilish.\n"
            "💰 Pulni yechib olish — pul yechish so'rovi.\n"
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
            "💰 Referal daromad: {earned} so'm"
        ),

        "news_empty":
            "📰 Hozircha yangiliklar yo'q.",

        "send_news":
            "📰 Yangilik uchun rasm, video yoki matn yuboring.",

        "news_saved":
            "✅ Yangilik saqlandi va foydalanuvchilarga yuborildi.",

        "send_broadcast":
            "📢 Barcha foydalanuvchilarga yuboriladigan "
            "xabarni yuboring.",

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
            "💰 <b>Pulni yechib olish</b>\n\n"
            "Minimal summa: {minimum} so'm\n"
            "Balansingiz: {balance} so'm\n\n"
            "Yechmoqchi bo'lgan summani yuboring:"
        ),

        "invalid_amount":
            "❌ Summani to'g'ri kiriting.",

        "not_enough":
            "❌ Balansingiz yetarli emas.",

        "withdraw_info":
            "💳 To'lov rekvizitingizni yuboring.",

        "withdraw_created": (
            "✅ Pul yechish so'rovi yuborildi.\n\n"
            "💰 Summa: {amount} so'm\n"
            "🆔 So'rov: #{request_id}"
        ),

        "back_menu":
            "🔙 Asosiy menyuga qaytdingiz.",

        "manage_text":
            "🗑 O'chirish uchun bo'limni tanlang:",

        "manage_projects":
            "🗑 Loyihalarni boshqarish",

        "manage_news":
            "🗑 Yangiliklarni boshqarish",

        "no_projects_delete":
            "📌 O'chirish uchun loyiha yo'q.",

        "no_news_delete":
            "📰 O'chirish uchun yangilik yo'q.",

        "project_deleted":
            "✅ Loyiha o'chirildi.",

        "news_deleted":
            "✅ Yangilik o'chirildi.",

        "delete_confirm":
            "⚠️ Haqiqatan ham o'chirmoqchimisiz?",

        "delete_yes":
            "✅ Ha, o'chirish",

        "delete_no":
            "❌ Yo'q",
    },


    "ru": {

        "welcome": (
            "Здравствуйте, {name}! 👋\n\n"
            "🎁 За подтверждённый голос {vote_reward} сум.\n"
            "👥 Реферальный бонус: {ref_reward} сум.\n\n"
            "Выберите раздел:"
        ),

        "projects": "📌 Проекты",
        "news": "📰 Новости",
        "balance": "💰 Баланс",
        "referral": "🔗 Реферальная ссылка",

        "withdraw":
            "💰 Вывести деньги",

        "help": "❓ Помощь",
        "language": "🌐 Язык",
        "group_add": "👥 Добавить в группу",

        "statistics": "📊 Статистика",
        "add_project": "➕ Добавить проект",
        "add_news": "📰 Добавить новость",
        "broadcast": "📢 Рассылка",

        "withdrawals":
            "💰 Вывод денег",

        "manage": "🗑 Управление",

        "admin_panel":
            "⚙️ Админ-панель",

        "back":
            "🔙 Назад",

        "cancel":
            "❌ Отмена",

        "select_language":
            "🌐 Выберите язык:",

        "language_saved":
            "✅ Язык изменён.",

        "select_project":
            "📌 Выберите проект:",

        "no_projects":
            "📌 Пока проектов нет.",

        "project_name":
            "📝 Отправьте название проекта:",

        "project_link":
            "🔗 Отправьте ссылку проекта:",

        "project_created":
            "✅ Проект добавлен и сохранён!",

        "invalid_link":
            "❌ Неверная ссылка.",

        "project_not_found":
            "❌ Проект не найден.",

        "open_project":
            "🔗 Открыть проект",

        "vote":
            "🗳 Голосовать",

        "vote_phone": (
            "📞 <b>Введите номер телефона для голосования:</b>\n\n"
            "Номер: <b>+998991234567</b> или <b>991234567</b>."
        ),

        "invalid_phone":
            "❌ Неверный номер телефона.",

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

        "help_text":
            "❓ Используйте кнопки меню.",

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

        "news_empty":
            "📰 Новостей пока нет.",

        "send_news":
            "📰 Отправьте новость.",

        "news_saved":
            "✅ Новость сохранена.",

        "send_broadcast":
            "📢 Отправьте сообщение для рассылки.",

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
            "💰 <b>Вывод денег</b>\n\n"
            "Минимум: {minimum} сум\n"
            "Баланс: {balance} сум\n\n"
            "Введите сумму:"
        ),

        "invalid_amount":
            "❌ Неверная сумма.",

        "not_enough":
            "❌ Недостаточно средств.",

        "withdraw_info":
            "💳 Отправьте реквизиты для выплаты.",

        "withdraw_created": (
            "✅ Заявка создана.\n"
            "💰 Сумма: {amount} сум\n"
            "🆔 #{request_id}"
        ),

        "back_menu":
            "🔙 Вы вернулись в главное меню.",

        "manage_text":
            "🗑 Выберите раздел:",

        "manage_projects":
            "🗑 Управление проектами",

        "manage_news":
            "🗑 Управление новостями",

        "no_projects_delete":
            "📌 Нет проектов для удаления.",

        "no_news_delete":
            "📰 Нет новостей для удаления.",

        "project_deleted":
            "✅ Проект удалён.",

        "news_deleted":
            "✅ Новость удалена.",

        "delete_confirm":
            "⚠️ Вы действительно хотите удалить?",

        "delete_yes":
            "✅ Да, удалить",

        "delete_no":
            "❌ Нет",
    }
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


class AdminReplyStates(StatesGroup):
    waiting_message = State()


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
            CREATE TABLE IF NOT EXISTS users(
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
            CREATE TABLE IF NOT EXISTS projects(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name_uz TEXT,
                name_ru TEXT,
                url TEXT,
                click_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS votes(
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
            CREATE TABLE IF NOT EXISTS news(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                message_id INTEGER,
                text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS referrals(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER,
                referred_id INTEGER UNIQUE,
                bonus INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                type TEXT,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS withdrawals(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                payment_info TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS admin_messages(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER,
                user_id INTEGER,
                message_id INTEGER,
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

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_admin_messages_msg
            ON admin_messages(message_id)
        """)

        conn.commit()

    logger.info("DATABASE TAYYOR")


# =========================================================
# HELPERS
# =========================================================

def money(amount):
    return f"{int(amount or 0):,}".replace(",", " ")


def is_admin(user_id):
    return user_id in ADMIN_IDS


def add_user(message):

    if not message.from_user:
        return

    with closing(db()) as conn:

        conn.execute("""
            INSERT INTO users(
                user_id,
                username,
                first_name
            )
            VALUES(?,?,?)
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


# =========================================================
# MENUS
# =========================================================

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
            ]
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
                KeyboardButton(text=t["manage"])
            ],
            [
                KeyboardButton(text=t["broadcast"])
            ],
            [
                KeyboardButton(text=t["withdrawals"])
            ],
            [
                KeyboardButton(text=t["back"])
            ]
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
            ]
        ],
        resize_keyboard=True
    )


# =========================================================
# START
# =========================================================

@dp.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):

    await state.clear()

    add_user(message)

    lang = get_lang(message.from_user.id)

    name = message.from_user.first_name or "Foydalanuvchi"

    await message.answer(
        TEXTS[lang]["welcome"].format(
            name=escape(name),
            vote_reward=money(VOTE_REWARD),
            ref_reward=money(REFERRAL_REWARD)
        ),
        reply_markup=main_menu(
            message.from_user.id,
            lang
        )
    )


# =========================================================
# BACK
# =========================================================

@dp.message(F.text.in_({
    "🔙 Orqaga",
    "🔙 Назад"
}))
async def back_handler(
    message: Message,
    state: FSMContext
):

    await state.clear()

    add_user(message)

    lang = get_lang(message.from_user.id)

    await message.answer(
        TEXTS[lang]["back_menu"],
        reply_markup=main_menu(
            message.from_user.id,
            lang
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

    lang = get_lang(message.from_user.id)

    await message.answer(
        TEXTS[lang]["select_language"],
        reply_markup=language_menu()
    )


@dp.message(F.text == "🇺🇿 O‘zbek")
async def uz_handler(message: Message):

    add_user(message)

    set_lang(
        message.from_user.id,
        "uz"
    )

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

    set_lang(
        message.from_user.id,
        "ru"
    )

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
    "📌 loyihalar",
    "📌 Проекты"
}))
async def projects_handler(message: Message):

    add_user(message)

    lang = get_lang(message.from_user.id)
    t = TEXTS[lang]

    with closing(db()) as conn:

        rows = conn.execute("""
            SELECT id, name_uz, name_ru
            FROM projects
            ORDER BY id DESC
        """).fetchall()

    if not rows:

        await message.answer(
            t["no_projects"],
            reply_markup=user_menu(lang)
        )

        return

    buttons = []

    for row in rows:

        name = (
            row["name_uz"]
            if lang == "uz"
            else row["name_ru"]
        )

        name = (
            name
            or row["name_uz"]
            or row["name_ru"]
        )

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

    lang = get_lang(
        callback.from_user.id
    )

    t = TEXTS[lang]

    with closing(db()) as conn:

        row = conn.execute(
            "SELECT * FROM projects WHERE id=?",
            (project_id,)
        ).fetchone()

        if row:

            conn.execute("""
                UPDATE projects
                SET click_count=COALESCE(click_count,0)+1
                WHERE id=?
            """, (
                project_id,
            ))

            conn.commit()

    if not row:

        await callback.answer(
            t["project_not_found"],
            show_alert=True
        )

        return

    name = (
        row["name_uz"]
        if lang == "uz"
        else row["name_ru"]
    )

    name = (
        name
        or row["name_uz"]
        or row["name_ru"]
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

    lang = get_lang(
        callback.from_user.id
    )

    t = TEXTS[lang]

    with closing(db()) as conn:

        project = conn.execute(
            "SELECT id FROM projects WHERE id=?",
            (project_id,)
        ).fetchone()

        vote = conn.execute("""
            SELECT id, status
            FROM votes
            WHERE user_id=? AND project_id=?
        """, (
            callback.from_user.id,
            project_id
        )).fetchone()

    if not project:

        await callback.answer(
            t["project_not_found"],
            show_alert=True
        )

        return

    if vote:

        await callback.answer(
            t["vote_already_pending"]
            if vote["status"] == "pending"
            else t["already_voted"],
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
        reply_markup=cancel_menu(lang)
    )

    await callback.answer()


def normalize_phone(text):

    value = re.sub(
        r"[\s\-]",
        "",
        text.strip()
    )

    if (
        value.startswith("+998")
        and len(value) == 13
        and value[1:].isdigit()
    ):
        return value

    if (
        value.startswith("998")
        and len(value) == 12
        and value.isdigit()
    ):
        return "+" + value

    if (
        len(value) == 9
        and value.isdigit()
    ):
        return "+998" + value

    return None


@dp.message(VoteStates.phone)
async def vote_phone_handler(
    message: Message,
    state: FSMContext
):

    lang = get_lang(
        message.from_user.id
    )

    t = TEXTS[lang]

    phone = normalize_phone(
        message.text or ""
    )

    if not phone:

        await message.answer(
            t["invalid_phone"]
        )

        return

    data = await state.get_data()

    project_id = data.get("project_id")

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
                reply_markup=user_menu(lang)
            )

            return

        cur = conn.execute("""
            INSERT INTO votes(
                user_id,
                project_id,
                phone,
                reward,
                status
            )
            VALUES(?,?,?,?, 'pending')
        """, (
            message.from_user.id,
            project_id,
            phone,
            VOTE_REWARD
        ))

        vote_id = cur.lastrowid

        conn.execute("""
            UPDATE users
            SET phone=?
            WHERE user_id=?
        """, (
            phone,
            message.from_user.id
        ))

        conn.commit()

    await state.clear()

    await message.answer(
        t["vote_sent"].format(
            reward=money(VOTE_REWARD)
        ),
        reply_markup=user_menu(lang)
    )

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