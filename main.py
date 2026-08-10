# =========================================================
# MAIN.PY — OPEN BUDGET BOT
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
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter


# =========================================================
# 🤖 BOT TOKENI
# =========================================================
# SHU YERGA O'Z BOT TOKENINGIZNI YOZING
#
# Masalan:
# BOT_TOKEN = "1234567890:AAxxxxxxxxxxxxxxxxxxxxxxxx"
#
# Tokenni hech kimga yubormang!

BOT_TOKEN = "8615736731:AAF7LGgYsKCq_JjV9qFPmFV6psTAS4mlQ_g"


# =========================================================
# 👤 ADMIN ID
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
# DATABASE
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
# TOKEN TEKSHIRISH
# =========================================================

if not BOT_TOKEN or BOT_TOKEN == "TOKENINGIZNI_SHU_YERGA_YOZING":
    raise RuntimeError(
        "BOT_TOKEN ni main.py ichida yozing!"
    )


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
            "🎁 Har bir tasdiqlangan ovoz uchun "
            "{vote_reward} so'm.\n"
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
            "Admin tasdiqlaganidan keyin "
            "{reward} so'm balansingizga qo'shiladi."
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
            "💰 Referal daromad: {earned} so'm"
        ),

        "news_empty": "📰 Hozircha yangiliklar yo'q.",

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
            "💸 <b>Pul yechish</b>\n\n"
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
            "🎁 За подтверждённый голос "
            "{vote_reward} сум.\n"
            "👥 Реферальный бонус: "
            "{ref_reward} сум.\n\n"
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
        "manage": "🗑 Управление",

        "admin_panel": "⚙️ Админ-панель",
        "back": "🔙 Назад",
        "cancel": "❌ Отмена",

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
            "Номер: <b>+998991234567</b> или "
            "<b>991234567</b>."
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
            "💸 <b>Вывод</b>\n\n"
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
# REFERALNI ISHLATISH
# =========================================================

def process_referral(user_id, referrer_id):

    if not referrer_id:
        return False

    if user_id == referrer_id:
        return False

    with closing(db()) as conn:

        user = conn.execute(
            "SELECT user_id FROM users WHERE user_id=?",
            (user_id,)
        ).fetchone()

        referrer = conn.execute(
            "SELECT user_id FROM users WHERE user_id=?",
            (referrer_id,)
        ).fetchone()

        if not referrer:
            return False

        if not user:
            return False

        exists = conn.execute("""
            SELECT id
            FROM referrals
            WHERE referred_id=?
        """, (
            user_id,
        )).fetchone()

        if exists:
            return False

        conn.execute("""
            INSERT INTO referrals(
                referrer_id,
                referred_id,
                bonus,
                status
            )
            VALUES(?,?,?,'rewarded')
        """, (
            referrer_id,
            user_id,
            REFERRAL_REWARD
        ))

        conn.execute("""
            UPDATE users
            SET
                balance=COALESCE(balance,0)+?,
                total_earned=COALESCE(total_earned,0)+?
            WHERE user_id=?
        """, (
            REFERRAL_REWARD,
            REFERRAL_REWARD,
            referrer_id
        ))

        conn.execute("""
            INSERT INTO transactions(
                user_id,
                amount,
                type,
                description
            )
            VALUES(?,?,?,?)
        """, (
            referrer_id,
            REFERRAL_REWARD,
            "referral",
            f"Referal bonusi: {user_id}"
        ))

        conn.commit()

    return True


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
# START + REFERAL
# =========================================================

@dp.message(CommandStart())
async def start_handler(
    message: Message,
    state: FSMContext
):

    await state.clear()

    user_id = message.from_user.id

    args = None

    if message.text:

        parts = message.text.split(maxsplit=1)

        if len(parts) > 1:
            args = parts[1].strip()

    was_user = False

    with closing(db()) as conn:

        row = conn.execute(
            "SELECT user_id FROM users WHERE user_id=?",
            (user_id,)
        ).fetchone()

        if row:
            was_user = True

    add_user(message)

    if args and args.startswith("ref_") and not was_user:

        try:

            referrer_id = int(
                args.replace("ref_", "", 1)
            )

            rewarded = process_referral(
                user_id,
                referrer_id
            )

            if rewarded:

                try:

                    await bot.send_message(
                        referrer_id,
                        (
                            "🎉 <b>Yangi referal!</b>\n\n"
                            f"💰 Sizga "
                            f"<b>{money(REFERRAL_REWARD)} so'm</b> "
                            "bonus berildi."
                        ),
                        parse_mode="HTML"
                    )

                except Exception:
                    pass

        except Exception as e:

            logger.warning(
                "Referral error: %s",
                e
            )

    lang = get_lang(user_id)

    name = (
        message.from_user.first_name
        or "Foydalanuvchi"
    )

    await message.answer(
        TEXTS[lang]["welcome"].format(
            name=escape(name),
            vote_reward=money(VOTE_REWARD),
            ref_reward=money(REFERRAL_REWARD)
        ),
        reply_markup=main_menu(
            user_id,
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

    lang = get_lang(
        message.from_user.id
    )

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

    lang = get_lang(
        message.from_user.id
    )

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
    "📌 Loyihalar",
    "📌 Проекты"
}))
async def projects_handler(message: Message):

    add_user(message)

    lang = get_lang(
        message.from_user.id
    )

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
async def project_handler(
    callback: CallbackQuery
):

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
# VOTE START
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


# =========================================================
# PHONE NORMALIZE
# =========================================================

def normalize_phone(text):

    value = re.sub(
        r"[\s\-\(\)]",
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


# =========================================================
# VOTE PHONE
# =========================================================

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
        f"👤 Foydalanuvchi: "
        f"{escape(username)}\n"
        f"🆔 User ID: "
        f"<code>{message.from_user.id}</code>\n"
        f"📞 Telefon: "
        f"<code>{escape(phone)}</code>\n"
        f"📌 Loyiha ID: "
        f"<b>{project_id}</b>\n"
        f"💰 Mukofot: "
        f"<b>{money(VOTE_REWARD)} so'm</b>"
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
            ],
            [
                InlineKeyboardButton(
                    text="💬 JAVOB YOZISH",
                    callback_data=(
                        f"admin_reply:{message.from_user.id}"
                    )
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
# APPROVE VOTE
# =========================================================

@dp.callback_query(F.data.startswith("vote_ok:"))
async def vote_approve(
    callback: CallbackQuery
):

    if not is_admin(
        callback.from_user.id
    ):

        await callback.answer(
            "Faqat admin.",
            show_alert=True
        )

        return

    vote_id = int(
        callback.data.split(":")[1]
    )

    with closing(db()) as conn:

        conn.execute(
            "BEGIN IMMEDIATE"
        )

        vote = conn.execute("""
            SELECT user_id,
                   project_id,
                   reward,
                   status
            FROM votes
            WHERE id=?
        """, (
            vote_id,
        )).fetchone()

        if not vote or vote["status"] != "pending":

            conn.rollback()

            await callback.answer(
                "So'rov allaqachon ko'rib chiqilgan.",
                show_alert=True
            )

            return

        conn.execute("""
            UPDATE votes
            SET
                status='approved',
                admin_id=?,
                approved_at=CURRENT_TIMESTAMP
            WHERE id=?
              AND status='pending'
        """, (
            callback.from_user.id,
            vote_id
        ))

        conn.execute("""
            UPDATE users
            SET
                balance=COALESCE(balance,0)+?,
                total_earned=COALESCE(total_earned,0)+?
            WHERE user_id=?
        """, (
            vote["reward"],
            vote["reward"],
            vote["user_id"]
        ))

        conn.execute("""
            INSERT INTO transactions(
                user_id,
                amount,
                type,
                description
            )
            VALUES(?,?,?,?)
        """, (
            vote["user_id"],
            vote["reward"],
            "vote",
            f"Ovoz tasdiqlandi #{vote_id}"
        ))

        conn.commit()

    try:

        await bot.send_message(
            vote["user_id"],
            (
                "🎉 <b>Ovozingiz tasdiqlandi!</b>\n\n"
                f"💰 Balansingizga "
                f"<b>{money(vote['reward'])} so'm</b> "
                "qo'shildi."
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

    await callback.answer(
        "Tasdiqlandi."
    )


# =========================================================
# REJECT VOTE
# =========================================================

@dp.callback_query(F.data.startswith("vote_no:"))
async def vote_reject(
    callback: CallbackQuery
):

    if not is_admin(
        callback.from_user.id
    ):

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
            SELECT user_id, status
            FROM votes
            WHERE id=?
        """, (
            vote_id,
        )).fetchone()

        if not vote or vote["status"] != "pending":

            await callback.answer(
                "So'rov allaqachon ko'rib chiqilgan.",
                show_alert=True
            )

            return

        conn.execute("""
            UPDATE votes
            SET
                status='rejected',
                admin_id=?
            WHERE id=?
              AND status='pending'
        """, (
            callback.from_user.id,
            vote_id
        ))

        conn.commit()

    try:

        await bot.send_message(
            vote["user_id"],
            "❌ <b>Ovoz so'rovingiz rad etildi.</b>",
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

    await callback.answer(
        "Rad etildi."
    )


# =========================================================
# ADMIN -> USER
# =========================================================

@dp.callback_query(F.data.startswith("admin_reply:"))
async def admin_reply_start(
    callback: CallbackQuery,
    state: FSMContext
):

    if not is_admin(
        callback.from_user.id
    ):

        await callback.answer(
            "Faqat admin.",
            show_alert=True
        )

        return

    user_id = int(
        callback.data.split(":")[1]
    )

    await state.clear()

    await state.update_data(
        reply_user_id=user_id
    )

    await state.set_state(
        AdminReplyStates.waiting_message
    )

    await callback.message.answer(
        "💬 <b>Foydalanuvchiga javob yozing.</b>\n\n"
        "Siz yuborgan xabar shu foydalanuvchiga yuboriladi.\n"
        "❌ Bekor qilish: /cancel",
        parse_mode="HTML"
    )

    await callback.answer()


async def send_copied_admin_message(
    message,
    user_id
):

    if message.text:

        return await bot.send_message(
            user_id,
            (
                "💬 <b>Admin sizga javob berdi:</b>\n\n"
                f"{escape(message.text)}"
            ),
            parse_mode="HTML"
        )

    if message.photo:

        return await bot.send_photo(
            user_id,
            message.photo[-1].file_id,
            caption=(
                "💬 <b>Admin sizga javob berdi:</b>\n\n"
                f"{escape(message.caption or '')}"
            ),
            parse_mode="HTML"
        )

    if message.video:

        return await bot.send_video(
            user_id,
            message.video.file_id,
            caption=(
                "💬 <b>Admin sizga javob berdi:</b>\n\n"
                f"{escape(message.caption or '')}"
            ),
            parse_mode="HTML"
        )

    if message.document:

        return await bot.send_document(
            user_id,
            message.document.file_id,
            caption=(
                "💬 <b>Admin sizga javob berdi:</b>\n\n"
                f"{escape(message.caption or '')}"
            ),
            parse_mode="HTML"
        )

    return None


@dp.message(AdminReplyStates.waiting_message)
async def admin_reply_send(
    message: Message,
    state: FSMContext
):

    if not is_admin(
        message.from_user.id
    ):

        await state.clear()

        return

    data = await state.get_data()

    user_id = data.get(
        "reply_user_id"
    )

    if not user_id:

        await state.clear()

        await message.answer(
            "❌ Foydalanuvchi topilmadi."
        )

        return

    try:

        sent = await send_copied_admin_message(
            message,
            user_id
        )

        if not sent:

            await message.answer(
                "❌ Matn, rasm, video yoki fayl yuboring."
            )

            return

        with closing(db()) as conn:

            conn.execute("""
                INSERT INTO admin_messages(
                    admin_id,
                    user_id,
                    message_id
                )
                VALUES(?,?,?)
            """, (
                message.from_user.id,
                user_id,
                sent.message_id
            ))

            conn.commit()

        await state.clear()

        await message.answer(
            "✅ Xabaringiz foydalanuvchiga yuborildi."
        )

    except TelegramForbiddenError:

        await state.clear()

        await message.answer(
            "🚫 Foydalanuvchi botni bloklagan."
        )

    except Exception as e:

        logger.error(
            "Admin reply error: %s",
            e
        )

        await state.clear()

        await message.answer(
            "❌ Xabar yuborishda xatolik yuz berdi."
        )


# =========================================================
# USER -> ADMIN REPLY
# =========================================================

@dp.message(F.reply_to_message)
async def user_reply_to_admin(
    message: Message
):

    if not message.from_user:
        return

    replied_id = (
        message.reply_to_message.message_id
    )

    with closing(db()) as conn:

        row = conn.execute("""
            SELECT admin_id, user_id
            FROM admin_messages
            WHERE message_id=?
              AND user_id=?
            ORDER BY id DESC
            LIMIT 1
        """, (
            replied_id,
            message.from_user.id
        )).fetchone()

    if not row:
        return

    username = (
        f"@{message.from_user.username}"
        if message.from_user.username
        else "Username yo'q"
    )

    header = (
        "📩 <b>FOYDALANUVCHIDAN JAVOB</b>\n\n"
        f"👤 {escape(username)}\n"
        f"🆔 User ID: "
        f"<code>{message.from_user.id}</code>\n\n"
    )

    try:

        if message.text:

            await bot.send_message(
                row["admin_id"],
                header +
                "💬 <b>Xabar:</b>\n\n" +
                escape(message.text),
                parse_mode="HTML"
            )

        elif message.photo:

            await bot.send_photo(
                row["admin_id"],
                message.photo[-1].file_id,
                caption=(
                    header +
                    "💬 Foydalanuvchi rasm yubordi."
                ),
                parse_mode="HTML"
            )

        elif message.video:

            await bot.send_video(
                row["admin_id"],
                message.video.file_id,
                caption=(
                    header +
                    "💬 Foydalanuvchi video yubordi."
                ),
                parse_mode="HTML"
            )

        elif message.document:

            await bot.send_document(
                row["admin_id"],
                message.document.file_id,
                caption=(
                    header +
                    "💬 Foydalanuvchi fayl yubordi."
                ),
                parse_mode="HTML"
            )

        else:

            await bot.send_message(
                row["admin_id"],
                header +
                "💬 Foydalanuvchi xabar yubordi.",
                parse_mode="HTML"
            )

        await message.answer(
            "✅ Javobingiz adminga yuborildi."
        )

    except Exception as e:

        logger.error(
            "User reply error: %s",
            e
        )

        await message.answer(
            "❌ Javobni yuborishda xatolik yuz berdi."
        )


# =========================================================
# BALANCE
# =========================================================

@dp.message(F.text.in_({
    "💰 Balans",
    "💰 Баланс"
}))
async def balance_handler(
    message: Message
):

    add_user(message)

    lang = get_lang(
        message.from_user.id
    )

    with closing(db()) as conn:

        row = conn.execute("""
            SELECT balance,
                   total_earned,
                   total_withdrawn
            FROM users
            WHERE user_id=?
        """, (
            message.from_user.id,
        )).fetchone()

    await message.answer(
        TEXTS[lang]["balance_text"].format(
            balance=money(row["balance"]),
            earned=money(row["total_earned"]),
            withdrawn=money(row["total_withdrawn"])
        ),
        parse_mode="HTML",
        reply_markup=user_menu(lang)
    )


# =========================================================
# REFERRAL
# =========================================================

@dp.message(F.text.in_({
    "🔗 Referal ssilka",
    "🔗 Реферальная ссылка"
}))
async def referral_handler(
    message: Message
):

    add_user(message)

    lang = get_lang(
        message.from_user.id
    )

    me = await bot.get_me()

    link = (
        f"https://t.me/{me.username}"
        f"?start=ref_{message.from_user.id}"
    )

    with closing(db()) as conn:

        count = conn.execute("""
            SELECT COUNT(*) c
            FROM referrals
            WHERE referrer_id=?
        """, (
            message.from_user.id,
        )).fetchone()["c"]

        earned = conn.execute("""
            SELECT COALESCE(SUM(bonus),0) s
            FROM referrals
            WHERE referrer_id=?
              AND status='rewarded'
        """, (
            message.from_user.id,
        )).fetchone()["s"]

    await message.answer(
        TEXTS[lang]["referral_text"].format(
            link=escape(link),
            count=count,
            earned=money(earned)
        ),
        parse_mode="HTML",
        reply_markup=user_menu(lang)
    )


# =========================================================
# NEWS USER
# =========================================================

@dp.message(F.text.in_({
    "📰 Yangiliklar",
    "📰 Новости"
}))
async def news_handler(
    message: Message
):

    add_user(message)

    lang = get_lang(
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
            TEXTS[lang]["news_empty"],
            reply_markup=user_menu(lang)
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
# ADMIN
# =========================================================

@dp.message(Command("admin"))
async def admin_handler(
    message: Message
):

    add_user(message)

    if not is_admin(
        message.from_user.id
    ):

        await message.answer(
            TEXTS[
                get_lang(
                    message.from_user.id
                )
            ]["admin_only"]
        )

        return

    lang = get_lang(
        message.from_user.id
    )

    await message.answer(
        TEXTS[lang]["admin_panel"],
        reply_markup=admin_menu(lang)
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
            TEXTS[
                get_lang(
                    message.from_user.id
                )
            ]["admin_only"]
        )

        return

    lang = get_lang(
        message.from_user.id
    )

    await state.clear()

    await state.set_state(
        ProjectStates.name
    )

    await message.answer(
        TEXTS[lang]["project_name"],
        reply_markup=cancel_menu(lang)
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

    name = (
        message.text or ""
    ).strip()

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
        TEXTS[
            get_lang(
                message.from_user.id
            )
        ]["project_link"]
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

    url = (
        message.text or ""
    ).strip()

    parsed = urlparse(url)

    lang = get_lang(
        message.from_user.id
    )

    if (
        parsed.scheme not in ("http", "https")
        or not parsed.netloc
    ):

        await message.answer(
            TEXTS[lang]["invalid_link"]
        )

        return

    data = await state.get_data()

    with closing(db()) as conn:

        conn.execute("""
            INSERT INTO projects(
                name_uz,
                name_ru,
                url
            )
            VALUES(?,?,?)
        """, (
            data["name"],
            data["name"],
            url
        ))

        conn.commit()

    await state.clear()

    await message.answer(
        TEXTS[lang]["project_created"],
        reply_markup=admin_menu(lang)
    )


# =========================================================
# ADD NEWS
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
            TEXTS[
                get_lang(
                    message.from_user.id
                )
            ]["admin_only"]
        )

        return

    lang = get_lang(
        message.from_user.id
    )

    await state.clear()

    await state.set_state(
        NewsStates.content
    )

    await message.answer(
        TEXTS[lang]["send_news"],
        reply_markup=cancel_menu(lang)
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
                row["user_id"],
                chat_id,
                message_id
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
                    row["user_id"],
                    chat_id,
                    message_id
                )

                success += 1

            except Exception:

                failed += 1

        except Exception:

            failed += 1

    return success, blocked, failed


# =========================================================
# SAVE NEWS
# =========================================================

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
            INSERT INTO news(
                chat_id,
                message_id,
                text
            )
            VALUES(?,?,?)
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

    lang = get_lang(
        message.from_user.id
    )

    await message.answer(
        TEXTS[lang]["news_saved"],
        reply_markup=admin_menu(lang)
    )


# =========================================================
# BROADCAST START
# =========================================================

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
            TEXTS[
                get_lang(
                    message.from_user.id
                )
            ]["admin_only"]
        )

        return

    lang = get_lang(
        message.from_user.id
    )

    await state.clear()

    await state.set_state(
        BroadcastStates.content
    )

    await message.answer(
        TEXTS[lang]["send_broadcast"],
        reply_markup=cancel_menu(lang)
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

    lang = get_lang(
        message.from_user.id
    )

    await message.answer(
        TEXTS[lang]["broadcast_result"].format(
            success=success,
            blocked=blocked,
            failed=failed
        ),
        reply_markup=admin_menu(lang)
    )


# =========================================================
# CONTENT MANAGEMENT
# =========================================================

@dp.message(F.text.in_({
    "🗑 Kontent boshqaruvi",
    "🗑 Управление"
}))
async def manage_content(
    message: Message
):

    if not is_admin(
        message.from_user.id
    ):

        await message.answer(
            TEXTS[
                get_lang(
                    message.from_user.id
                )
            ]["admin_only"]
        )

        return

    lang = get_lang(
        message.from_user.id
    )

    t = TEXTS[lang]

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t["manage_projects"],
                    callback_data="manage_projects"
                )
            ],
            [
                InlineKeyboardButton(
                    text=t["manage_news"],
                    callback_data="manage_news"
                )
            ]
        ]
    )

    await message.answer(
        t["manage_text"],
        reply_markup=keyboard
    )


# =========================================================
# MANAGE PROJECTS
# =========================================================

@dp.callback_query(
    F.data == "manage_projects"
)
async def manage_projects(
    callback: CallbackQuery
):

    if not is_admin(
        callback.from_user.id
    ):

        await callback.answer(
            "Faqat admin.",
            show_alert=True
        )

        return

    lang = get_lang(
        callback.from_user.id
    )

    t = TEXTS[lang]

    with closing(db()) as conn:

        rows = conn.execute("""
            SELECT id,
                   name_uz,
                   name_ru,
                   url
            FROM projects
            ORDER BY id DESC
        """).fetchall()

    if not rows:

        await callback.message.answer(
            t["no_projects_delete"]
        )

        await callback.answer()

        return

    buttons = []

    for row in rows:

        name = (
            row["name_uz"]
            or row["name_ru"]
            or f"Loyiha #{row['id']}"
        )

        buttons.append([
            InlineKeyboardButton(
                text=f"🗑 {name}",
                callback_data=(
                    f"delete_project:{row['id']}"
                )
            )
        ])

    await callback.message.answer(
        "📌 O'chirmoqchi bo'lgan loyihani tanlang:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )

    await callback.answer()


# =========================================================
# DELETE PROJECT CONFIRM
# =========================================================

@dp.callback_query(
    F.data.startswith("delete_project:")
)
async def delete_project_confirm(
    callback: CallbackQuery
):

    if not is_admin(
        callback.from_user.id
    ):

        await callback.answer(
            "Faqat admin.",
            show_alert=True
        )

        return

    project_id = int(
        callback.data.split(":")[1]
    )

    lang = get_lang(
        callback.from_user.id
    )

    t = TEXTS[lang]

    with closing(db()) as conn:

        row = conn.execute("""
            SELECT id,
                   name_uz,
                   name_ru
            FROM projects
            WHERE id=?
        """, (
            project_id,
        )).fetchone()

    if not row:

        await callback.answer(
            t["project_not_found"],
            show_alert=True
        )

        return

    name = (
        row["name_uz"]
        or row["name_ru"]
        or f"#{project_id}"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t["delete_yes"],
                    callback_data=(
                        f"project_delete_yes:{project_id}"
                    )
                ),
                InlineKeyboardButton(
                    text=t["delete_no"],
                    callback_data="delete_cancel"
                )
            ]
        ]
    )

    await callback.message.answer(
        f"{t['delete_confirm']}\n\n"
        f"📌 <b>{escape(name)}</b>",
        parse_mode="HTML",
        reply_markup=keyboard
    )

    await callback.answer()


# =========================================================
# DELETE PROJECT
# =========================================================

@dp.callback_query(
    F.data.startswith("project_delete_yes:")
)
async def delete_project(
    callback: CallbackQuery
):

    if not is_admin(
        callback.from_user.id
    ):

        await callback.answer(
            "Faqat admin.",
            show_alert=True
        )

        return

    project_id = int(
        callback.data.split(":")[1]
    )

    lang = get_lang(
        callback.from_user.id
    )

    with closing(db()) as conn:

        row = conn.execute(
            "SELECT id FROM projects WHERE id=?",
            (project_id,)
        ).fetchone()

        if not row:

            await callback.answer(
                "Loyiha topilmadi.",
                show_alert=True
            )

            return

        conn.execute(
            "DELETE FROM projects WHERE id=?",
            (project_id,)
        )

        conn.commit()

    try:

        await callback.message.edit_reply_markup(
            reply_markup=None
        )

    except Exception:
        pass

    await callback.message.answer(
        TEXTS[lang]["project_deleted"]
    )

    await callback.answer(
        "O'chirildi."
    )


# =========================================================
# MANAGE NEWS
# =========================================================

@dp.callback_query(
    F.data == "manage_news"
)
async def manage_news(
    callback: CallbackQuery
):

    if not is_admin(
        callback.from_user.id
    ):

        await callback.answer(
            "Faqat admin.",
            show_alert=True
        )

        return

    lang = get_lang(
        callback.from_user.id
    )

    t = TEXTS[lang]

    with closing(db()) as conn:

        rows = conn.execute("""
            SELECT id,
                   text,
                   created_at
            FROM news
            ORDER BY id DESC
            LIMIT 30
        """).fetchall()

    if not rows:

        await callback.message.answer(
            t["no_news_delete"]
        )

        await callback.answer()

        return

    buttons = []

    for row in rows:

        title = (
            row["text"]
            or f"Yangilik #{row['id']}"
        )

        title = title.replace(
            "\n",
            " "
        )

        if len(title) > 35:
            title = title[:35] + "..."

        buttons.append([
            InlineKeyboardButton(
                text=f"🗑 {title}",
                callback_data=(
                    f"delete_news:{row['id']}"
                )
            )
        ])

    await callback.message.answer(
        "📰 O'chirmoqchi bo'lgan yangilikni tanlang:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )

    await callback.answer()


# =========================================================
# DELETE NEWS CONFIRM
# =========================================================

@dp.callback_query(
    F.data.startswith("delete_news:")
)
async def delete_news_confirm(
    callback: CallbackQuery
):

    if not is_admin(
        callback.from_user.id
    ):

        await callback.answer(
            "Faqat admin.",
            show_alert=True
        )

        return

    news_id = int(
        callback.data.split(":")[1]
    )

    lang = get_lang(
        callback.from_user.id
    )

    t = TEXTS[lang]

    with closing(db()) as conn:

        row = conn.execute("""
            SELECT id, text
            FROM news
            WHERE id=?
        """, (
            news_id,
        )).fetchone()

    if not row:

        await callback.answer(
            "Yangilik topilmadi.",
            show_alert=True
        )

        return

    title = (
        row["text"]
        or f"#{news_id}"
    )

    if len(title) > 100:
        title = title[:100] + "..."

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t["delete_yes"],
                    callback_data=(
                        f"news_delete_yes:{news_id}"
                    )
                ),
                InlineKeyboardButton(
                    text=t["delete_no"],
                    callback_data="delete_cancel"
                )
            ]
        ]
    )

    await callback.message.answer(
        f"{t['delete_confirm']}\n\n"
        f"📰 <b>{escape(title)}</b>",
        parse_mode="HTML",
        reply_markup=keyboard
    )

    await callback.answer()


# =========================================================
# DELETE NEWS
# =========================================================

@dp.callback_query(
    F.data.startswith("news_delete_yes:")
)
async def delete_news(
    callback: CallbackQuery
):

    if not is_admin(
        callback.from_user.id
    ):

        await callback.answer(
            "Faqat admin.",
            show_alert=True
        )

        return

    news_id = int(
        callback.data.split(":")[1]
    )

    lang = get_lang(
        callback.from_user.id
    )

    with closing(db()) as conn:

        row = conn.execute(
            "SELECT id FROM news WHERE id=?",
            (news_id,)
        ).fetchone()

        if not row:

            await callback.answer(
                "Yangilik topilmadi.",
                show_alert=True
            )

            return

        conn.execute(
            "DELETE FROM news WHERE id=?",
            (news_id,)
        )

        conn.commit()

    try:

        await callback.message.edit_reply_markup(
            reply_markup=None
        )

    except Exception:
        pass

    await callback.message.answer(
        TEXTS[lang]["news_deleted"]
    )

    await callback.answer(
        "O'chirildi."
    )


# =========================================================
# DELETE CANCEL
# =========================================================

@dp.callback_query(
    F.data == "delete_cancel"
)
async def delete_cancel(
    callback: CallbackQuery
):

    await callback.answer(
        "Bekor qilindi."
    )

    try:

        await callback.message.edit_reply_markup(
            reply_markup=None
        )

    except Exception:
        pass


# =========================================================
# STATISTICS
# =========================================================

@dp.message(F.text.in_({
    "📊 Statistika",
    "📊 Статистика"
}))
async def statistics(
    message: Message
):

    if not is_admin(
        message.from_user.id
    ):

        await message.answer(
            TEXTS[
                get_lang(
                    message.from_user.id
                )
            ]["admin_only"]
        )

        return

    lang = get_lang(
        message.from_user.id
    )

    with closing(db()) as conn:

        users = conn.execute(
            "SELECT COUNT(*) c FROM users"
        ).fetchone()["c"]

        votes = conn.execute("""
            SELECT COUNT(*) c
            FROM votes
            WHERE status='approved'
        """).fetchone()["c"]

        pending = conn.execute("""
            SELECT COUNT(*) c
            FROM votes
            WHERE status='pending'
        """).fetchone()["c"]

        projects = conn.execute(
            "SELECT COUNT(*) c FROM projects"
        ).fetchone()["c"]

        views = conn.execute("""
            SELECT COALESCE(SUM(click_count),0) c
            FROM projects
        """).fetchone()["c"]

        news = conn.execute(
            "SELECT COUNT(*) c FROM news"
        ).fetchone()["c"]

        balance = conn.execute("""
            SELECT COALESCE(SUM(balance),0) c
            FROM users
        """).fetchone()["c"]

        withdrawn = conn.execute("""
            SELECT COALESCE(SUM(total_withdrawn),0) c
            FROM users
        """).fetchone()["c"]

    await message.answer(
        TEXTS[lang]["stats"].format(
            users=users,
            votes=votes,
            pending_votes=pending,
            projects=projects,
            views=views,
            news=news,
            balance=money(balance),
            withdrawn=money(withdrawn)
        ),
        parse_mode="HTML",
        reply_markup=admin_menu(lang)
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

    lang = get_lang(
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
            f"💰 Balansingiz: "
            f"{money(balance)} so'm",
            reply_markup=user_menu(lang)
        )

        return

    await state.clear()

    await state.set_state(
        WithdrawStates.amount
    )

    await message.answer(
        TEXTS[lang]["withdraw_amount"].format(
            minimum=money(MIN_WITHDRAW),
            balance=money(balance)
        ),
        parse_mode="HTML",
        reply_markup=cancel_menu(lang)
    )


@dp.message(WithdrawStates.amount)
async def withdraw_amount(
    message: Message,
    state: FSMContext
):

    lang = get_lang(
        message.from_user.id
    )

    value = (
        message.text or ""
    ).replace(" ", "")

    if not value.isdigit():

        await message.answer(
            TEXTS[lang]["invalid_amount"]
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

        row = conn.execute("""
            SELECT balance
            FROM users
            WHERE user_id=?
        """, (
            message.from_user.id,
        )).fetchone()

    if amount > row["balance"]:

        await message.answer(
            TEXTS[lang]["not_enough"]
        )

        return

    await state.update_data(
        amount=amount
    )

    await state.set_state(
        WithdrawStates.info
    )

    await message.answer(
        TEXTS[lang]["withdraw_info"]
    )


@dp.message(WithdrawStates.info)
async def withdraw_info(
    message: Message,
    state: FSMContext
):

    if not message.text:
        return

    lang = get_lang(
        message.from_user.id
    )

    data = await state.get_data()

    amount = data.get(
        "amount"
    )

    if not amount:

        await state.clear()

        return

    with closing(db()) as conn:

        conn.execute(
            "BEGIN IMMEDIATE"
        )

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
                TEXTS[lang]["not_enough"],
                reply_markup=user_menu(lang)
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
            INSERT INTO withdrawals(
                user_id,
                amount,
                payment_info,
                status
            )
            VALUES(?,?,?,'pending')
        """, (
            message.from_user.id,
            amount,
            message.text.strip()
        ))

        request_id = cur.lastrowid

        conn.commit()

    await state.clear()

    await message.answer(
        TEXTS[lang]["withdraw_created"].format(
            amount=money(amount),
            request_id=request_id
        ),
        reply_markup=user_menu(lang)
    )

    # ADMINGA YUBORISH
    username = (
        f"@{message.from_user.username}"
        if message.from_user.username
        else "Username yo'q"
    )

    admin_text = (
        "💸 <b>YANGI PUL YECHISH SO'ROVI</b>\n\n"
        f"🆔 So'rov: <b>#{request_id}</b>\n"
        f"👤 Foydalanuvchi: {escape(username)}\n"
        f"🆔 User ID: "
        f"<code>{message.from_user.id}</code>\n"
        f"💰 Summa: <b>{money(amount)} so'm</b>\n"
        f"💳 Rekvizit: "
        f"<code>{escape(message.text.strip())}</code>"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ TO'LASH",
                    callback_data=f"withdraw_ok:{request_id}"
                ),
                InlineKeyboardButton(
                    text="❌ RAD ETISH",
                    callback_data=f"withdraw_no:{request_id}"
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
                "Withdrawal admin error: %s",
                e
            )


# =========================================================
# APPROVE WITHDRAW
# =========================================================

@dp.callback_query(
    F.data.startswith("withdraw_ok:")
)
async def withdraw_approve(
    callback: CallbackQuery
):

    if not is_admin(
        callback.from_user.id
    ):

        await callback.answer(
            "Faqat admin.",
            show_alert=True
        )

        return

    request_id = int(
        callback.data.split(":")[1]
    )

    with closing(db()) as conn:

        request = conn.execute("""
            SELECT user_id,
                   amount,
                   status
            FROM withdrawals
            WHERE id=?
        """, (
            request_id,
        )).fetchone()

        if not request or request["status"] != "pending":

            await callback.answer(
                "So'rov allaqachon ko'rib chiqilgan.",
                show_alert=True
            )

            return

        conn.execute("""
            UPDATE withdrawals
            SET status='approved'
            WHERE id=?
              AND status='pending'
        """, (
            request_id,
        ))

        conn.execute("""
            UPDATE users
            SET total_withdrawn=
                COALESCE(total_withdrawn,0)+?
            WHERE user_id=?
        """, (
            request["amount"],
            request["user_id"]
        ))

        conn.execute("""
            INSERT INTO transactions(
                user_id,
                amount,
                type,
                description
            )
            VALUES(?,?,?,?)
        """, (
            request["user_id"],
            request["amount"],
            "withdraw",
            f"Pul yechish #{request_id}"
        ))

        conn.commit()

    try:

        await bot.send_message(
            request["user_id"],
            (
                "✅ <b>Pul yechish so'rovingiz tasdiqlandi!</b>\n\n"
                f"💰 Summa: "
                f"<b>{money(request['amount'])} so'm</b>"
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
        f"✅ So'rov #{request_id} tasdiqlandi."
    )

    await callback.answer(
        "Tasdiqlandi."
    )


# =========================================================
# REJECT WITHDRAW
# =========================================================

@dp.callback_query(
    F.data.startswith("withdraw_no:")
)
async def withdraw_reject(
    callback: CallbackQuery
):

    if not is_admin(
        callback.from_user.id
    ):

        await callback.answer(
            "Faqat admin.",
            show_alert=True
        )

        return

    request_id = int(
        callback.data.split(":")[1]
    )

    with closing(db()) as conn:

        request = conn.execute("""
            SELECT user_id,
                   amount,
                   status
            FROM withdrawals
            WHERE id=?
        """, (
            request_id,
        )).fetchone()

        if not request or request["status"] != "pending":

            await callback.answer(
                "So'rov allaqachon ko'rib chiqilgan.",
                show_alert=True
            )

            return

        conn.execute("""
            UPDATE withdrawals
            SET status='rejected'
            WHERE id=?
              AND status='pending'
        """, (
            request_id,
        ))

        # RAD ETILGANDA PULNI QAYTARISH
        conn.execute("""
            UPDATE users
            SET balance=COALESCE(balance,0)+?
            WHERE user_id=?
        """, (
            request["amount"],
            request["user_id"]
        ))

        conn.commit()

    try:

        await bot.send_message(
            request["user_id"],
            (
                "❌ <b>Pul yechish so'rovingiz rad etildi.</b>\n\n"
                f"💰 {money(request['amount'])} so'm "
                "balansingizga qaytarildi."
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
        f"❌ So'rov #{request_id} rad etildi."
    )

    await callback.answer(
        "Rad etildi."
    )


# =========================================================
# WITHDRAWAL LIST ADMIN
# =========================================================

@dp.message(F.text.in_({
    "💸 Yechishlar",
    "💸 Заявки"
}))
async def withdrawal_list(
    message: Message
):

    if not is_admin(
        message.from_user.id
    ):

        await message.answer(
            TEXTS[
                get_lang(
                    message.from_user.id
                )
            ]["admin_only"]
        )

        return

    with closing(db()) as conn:

        rows = conn.execute("""
            SELECT id,
                   user_id,
                   amount,
                   payment_info,
                   status,
                   created_at
            FROM withdrawals
            ORDER BY id DESC
            LIMIT 30
        """).fetchall()

    if not rows:

        await message.answer(
            "💸 Hozircha pul yechish so'rovlari yo'q."
        )

        return

    text = "💸 <b>PUL YECHISH SO'ROVLARI</b>\n\n"

    for row in rows:

        status = row["status"]

        if status == "pending":
            status_text = "⏳ Kutilmoqda"
        elif status == "approved":
            status_text = "✅ Tasdiqlangan"
        else:
            status_text = "❌ Rad etilgan"

        text += (
            f"🆔 #{row['id']}\n"
            f"👤 User: <code>{row['user_id']}</code>\n"
            f"💰 Summa: <b>{money(row['amount'])} so'm</b>\n"
            f"💳 {escape(row['payment_info'] or '')}\n"
            f"📌 Holat: {status_text}\n\n"
        )

    await message.answer(
        text,
        parse_mode="HTML"
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

    lang = get_lang(
        message.from_user.id
    )

    await message.answer(
        TEXTS[lang]["back_menu"],
        reply_markup=main_menu(
            message.from_user.id,
            lang
        )
    )


@dp.message(Command("cancel"))
async def cancel_command(
    message: Message,
    state: FSMContext
):

    await state.clear()

    lang = get_lang(
        message.from_user.id
    )

    await message.answer(
        TEXTS[lang]["back_menu"],
        reply_markup=main_menu(
            message.from_user.id,
            lang
        )
    )


# =========================================================
# HELP
# =========================================================

@dp.message(F.text.in_({
    "❓ Yordam",
    "❓ Помощь"
}))
async def help_handler(
    message: Message
):

    add_user(message)

    lang = get_lang(
        message.from_user.id
    )

    await message.answer(
        TEXTS[lang]["help_text"],
        parse_mode="HTML",
        reply_markup=user_menu(lang)
    )


# =========================================================
# GROUP
# =========================================================

@dp.message(F.text.in_({
    "👥 Guruhga qo'shish",
    "👥 Guruhga qo‘shish",
    "👥 Добавить в группу"
}))
async def group_handler(
    message: Message
):

    lang = get_lang(
        message.from_user.id
    )

    me = await bot.get_me()

    link = (
        f"https://t.me/{me.username}"
        "?startgroup=true"
    )

    await message.answer(
        "👥 Botni guruhga qo'shish:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=TEXTS[lang]["group_add"],
                        url=link
                    )
                ]
            ]
        )
    )


# =========================================================
# UNKNOWN
# =========================================================

@dp.message()
async def unknown(
    message: Message
):

    if not message.from_user:
        return

    add_user(message)

    lang = get_lang(
        message.from_user.id
    )

    await message.answer(
        "❗ Iltimos, menyudagi tugmalardan foydalaning.",
        reply_markup=main_menu(
            message.from_user.id,
            lang
        )
    )


# =========================================================
# MAIN
# =========================================================

async def main():

    print(
        "========================================",
        flush=True
    )

    print(
        "MAIN.PY ISHLAYAPTI",
        flush=True
    )

    print(
        "========================================",
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


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        print(
            "BOT TO'XTATILDI",
            flush=True
        )