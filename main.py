import asyncio
import logging
import sqlite3
from pathlib import Path
from contextlib import closing
from urllib.parse import urlparse
from html import escape

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command, CommandObject
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

# YANGI BOT TOKENINGIZNI SHU YERGA YOZING
BOT_TOKEN = "8615736731:AAF7LGgYsKCq_JjV9qFPmFV6psTAS4mlQ_g"

# ADMIN ID NI SHU YERGA YOZING
ADMIN_IDS = {7998053914}

VOTE_REWARD = 30_000
REFERRAL_REWARD = 5_000
MIN_WITHDRAW = 20_000

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "bot.db"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)

if not BOT_TOKEN or BOT_TOKEN == "BU_YERGA_YANGI_BOT_TOKEN":
    raise RuntimeError("BOT_TOKEN ni main.py ichiga yozing.")

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
            "👥 Referal orqali taklif qilgan do'stingiz ovoz bersa "
            "{ref_reward} so'm bonus olasiz.\n\n"
            "Kerakli bo'limni tanlang:"
        ),
        "projects": "📌 Loyihalar",
        "news": "📰 Yangiliklar",
        "help": "❓ Yordam",
        "language": "🌐 Til",
        "balance": "💰 Balans",
        "referral": "🔗 Referal ssilka",
        "withdraw": "💸 Pul yechish",
        "withdrawals": "💸 Yechishlar",
        "group_add": "👥 Guruhga qo'shish",
        "statistics": "📊 Statistika",
        "add_project": "➕ Loyiha qo'shish",
        "add_news": "📰 Yangilik qo'shish",
        "broadcast": "📢 Reklama tarqatish",
        "back": "🔙 Orqaga",
        "admin_panel": "⚙️ Admin panel",

        "group_add_text": (
            "👥 Botni guruhingizga qo'shing!\n\n"
            "Quyidagi tugmani bosing."
        ),

        "select_language": "🌐 Tilni tanlang:",
        "language_saved": "✅ Til muvaffaqiyatli o'zgartirildi.",

        "select_project": "📌 Loyihalardan birini tanlang:",
        "no_projects": "📌 Hozircha loyihalar mavjud emas.",

        "project_name": "📝 Loyiha nomini yuboring:",

        "project_link": (
            "🔗 Endi loyiha havolasini yuboring.\n\n"
            "Masalan: https://example.com"
        ),

        "project_created": "✅ Loyiha muvaffaqiyatli qo'shildi!",

        "invalid_link": (
            "❌ Havola noto'g'ri.\n"
            "Havola http:// yoki https:// bilan boshlanishi kerak."
        ),

        "project_invalid_name": "❌ Loyiha nomi juda qisqa.",

        "open_project": "🔗 Loyihani ochish",
        "vote": "🗳 Ovoz berish",

        "project_not_found": "❌ Loyiha topilmadi.",

        "phone_required": (
            "🗳 Ovoz berish uchun telefon raqamingiz kerak.\n\n"
            "Quyidagi tugmani bosing.\n"
            "Telefon raqamingiz Telegram orqali faqat "
            "sizning roziligingiz bilan yuboriladi."
        ),

        "send_phone": "📱 Telefon raqamimni yuborish",
        "cancel": "❌ Bekor qilish",

        "phone_received": "✅ Telefon raqamingiz qabul qilindi.",

        "vote_success": (
            "🎉 Ovoz muvaffaqiyatli qabul qilindi!\n"
            "💰 Balansingizga {amount} so'm qo'shildi."
        ),

        "already_voted": "⚠️ Siz bu loyihaga allaqachon ovoz bergansiz.",

        "own_phone_only": (
            "❌ Iltimos, o'zingizning telefon raqamingizni yuboring."
        ),

        "help_text": (
            "❓ Yordam\n\n"
            "📌 Loyihalar — loyihalarni ko'rish.\n"
            "🗳 Ovoz berish — loyiha uchun ovoz berish.\n"
            "💰 Balans — balansni ko'rish.\n"
            "🔗 Referal — do'stlarni taklif qilish.\n"
            "💸 Pul yechish — pul yechish so'rovini yuborish.\n"
            "📰 Yangiliklar — yangiliklarni ko'rish.\n"
            "🌐 Til — tilni almashtirish."
        ),

        "news_empty": "📰 Hozircha yangiliklar mavjud emas.",
        "admin_only": "❌ Bu bo'lim faqat administratorlar uchun.",

        "send_news": (
            "📰 Yangilik uchun rasm, video yoki matn yuboring."
        ),

        "news_saved": "✅ Yangilik saqlandi va yuborildi.",

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
            "📊 Statistika\n\n"
            "👥 Foydalanuvchilar: {users}\n"
            "🗳 Jami ovozlar: {votes}\n"
            "👁 Loyiha ko'rishlari: {views}\n"
            "📌 Loyihalar: {projects}\n"
            "📰 Yangiliklar: {news}\n"
            "💰 Umumiy balans: {balance} so'm\n"
            "💸 Yechilgan: {withdrawn} so'm\n"
            "⏳ Kutilayotgan: {pending} so'm"
        ),

        "unknown": "❗ Iltimos, menyudagi tugmalardan foydalaning.",

        "balance_text": (
            "💰 <b>Sizning balansingiz</b>\n\n"
            "💵 Balans: <b>{balance} so'm</b>\n"
            "📈 Jami ishlangan: {earned} so'm\n"
            "💸 Jami yechilgan: {withdrawn} so'm"
        ),

        "referral_text": (
            "🔗 <b>Sizning referal havolangiz:</b>\n\n"
            "<code>{link}</code>\n\n"
            "👥 Taklif qilinganlar: {count}\n"
            "💰 Referal daromad: {earned} so'm"
        ),

        "withdraw_amount": (
            "💸 <b>Pul yechish</b>\n\n"
            "Minimal summa: <b>{minimum} so'm</b>\n"
            "Balansingiz: <b>{balance} so'm</b>\n\n"
            "Yechmoqchi bo'lgan summani yuboring:"
        ),

        "invalid_amount": "❌ Summani to'g'ri kiriting.",
        "min_amount": "❌ Minimal summa: {amount} so'm.",
        "not_enough": "❌ Balansingiz yetarli emas.",

        "withdraw_info": (
            "💳 To'lov rekvizitingizni yuboring.\n\n"
            "Masalan: telefon raqami yoki wallet ID."
        ),

        "withdraw_created": (
            "✅ Pul yechish so'rovi qabul qilindi.\n\n"
            "💰 Summa: <b>{amount} so'm</b>\n"
            "🆔 So'rov: #{request_id}"
        ),

        "request_not_found": "❌ So'rov topilmadi.",

        "withdraw_request": (
            "💸 <b>Yangi pul yechish so'rovi</b>\n\n"
            "🆔 #{request_id}\n"
            "👤 Foydalanuvchi: {user}\n"
            "🆔 User ID: <code>{user_id}</code>\n"
            "💰 Summa: <b>{amount} so'm</b>\n"
            "💳 Rekvizit: <code>{info}</code>"
        ),

        "approved": "✅ So'rov tasdiqlandi.",
        "rejected": "❌ So'rov rad etildi.",

        "withdraw_approved_user": (
            "✅ Pul yechish so'rovingiz tasdiqlandi.\n"
            "💰 Summa: {amount} so'm"
        ),

        "withdraw_rejected_user": (
            "❌ Pul yechish so'rovingiz rad etildi.\n"
            "💰 {amount} so'm balansingizga qaytarildi."
        ),

        "no_pending_withdrawals": "⏳ Kutilayotgan so'rovlar yo'q.",

        "back_menu": "🔙 Asosiy menyuga qaytdingiz.",
    },

    "ru": {}
}

# Ruscha matnlar o'zbekcha kalitlar bilan ishlashi uchun
# asosiy menyu tugmalari alohida beriladi.
TEXTS["ru"] = {
    **TEXTS["uz"],
    "welcome": (
        "Здравствуйте, {name}! 👋\n\n"
        "🎁 За подтверждённый голос начисляется "
        "{vote_reward} сум.\n"
        "👥 За голос приглашённого друга — "
        "{ref_reward} сум.\n\n"
        "Выберите раздел:"
    ),
    "projects": "📌 Проекты",
    "news": "📰 Новости",
    "help": "❓ Помощь",
    "language": "🌐 Язык",
    "balance": "💰 Баланс",
    "referral": "🔗 Реферальная ссылка",
    "withdraw": "💸 Вывести деньги",
    "withdrawals": "💸 Заявки на вывод",
    "group_add": "👥 Добавить в группу",
    "statistics": "📊 Статистика",
    "add_project": "➕ Добавить проект",
    "add_news": "📰 Добавить новость",
    "broadcast": "📢 Рассылка",
    "back": "🔙 Назад",
    "admin_panel": "⚙️ Админ-панель",
    "select_language": "🌐 Выберите язык:",
    "language_saved": "✅ Язык успешно изменён.",
    "select_project": "📌 Выберите проект:",
    "no_projects": "📌 Пока проектов нет.",
    "project_name": "📝 Отправьте название проекта:",
    "project_link": "🔗 Отправьте ссылку проекта:",
    "project_created": "✅ Проект успешно добавлен!",
    "invalid_link": "❌ Неверная ссылка.",
    "project_invalid_name": "❌ Название слишком короткое.",
    "open_project": "🔗 Открыть проект",
    "vote": "🗳 Голосовать",
    "project_not_found": "❌ Проект не найден.",
    "phone_required": (
        "🗳 Для голосования нужен номер телефона.\n\n"
        "Нажмите кнопку ниже."
    ),
    "send_phone": "📱 Отправить мой номер",
    "cancel": "❌ Отмена",
    "phone_received": "✅ Номер получен.",
    "vote_success": (
        "🎉 Голос принят!\n"
        "💰 Начислено {amount} сум."
    ),
    "already_voted": "⚠️ Вы уже голосовали за этот проект.",
    "own_phone_only": "❌ Отправьте свой номер телефона.",
    "help_text": (
        "❓ Помощь\n\n"
        "📌 Проекты — просмотр проектов.\n"
        "🗳 Голосовать — голосование.\n"
        "💰 Баланс — ваш баланс.\n"
        "🔗 Реферал — приглашение друзей.\n"
        "💸 Вывод — заявка на вывод.\n"
        "📰 Новости — новости.\n"
        "🌐 Язык — смена языка."
    ),
    "news_empty": "📰 Пока новостей нет.",
    "admin_only": "❌ Только для администратора.",
    "send_news": "📰 Отправьте новость.",
    "news_saved": "✅ Новость сохранена и отправлена.",
    "send_broadcast": "📢 Отправьте сообщение для рассылки.",
    "unknown": "❗ Используйте кнопки меню.",
    "balance_text": (
        "💰 <b>Ваш баланс</b>\n\n"
        "💵 Баланс: <b>{balance} сум</b>\n"
        "📈 Всего заработано: {earned} сум\n"
        "💸 Всего выведено: {withdrawn} сум"
    ),
    "referral_text": (
        "🔗 <b>Ваша реферальная ссылка:</b>\n\n"
        "<code>{link}</code>\n\n"
        "👥 Приглашено: {count}\n"
        "💰 Доход: {earned} сум"
    ),
    "withdraw_amount": (
        "💸 <b>Вывод денег</b>\n\n"
        "Минимум: <b>{minimum} сум</b>\n"
        "Баланс: <b>{balance} сум</b>\n\n"
        "Отправьте сумму:"
    ),
    "invalid_amount": "❌ Неверная сумма.",
    "min_amount": "❌ Минимум: {amount} сум.",
    "not_enough": "❌ Недостаточно средств.",
    "withdraw_info": "💳 Отправьте реквизит для выплаты.",
    "withdraw_created": (
        "✅ Заявка создана.\n\n"
        "💰 Сумма: <b>{amount} сум</b>\n"
        "🆔 #{request_id}"
    ),
    "request_not_found": "❌ Заявка не найдена.",
    "withdraw_request": (
        "💸 <b>Новая заявка</b>\n\n"
        "🆔 #{request_id}\n"
        "👤 {user}\n"
        "🆔 <code>{user_id}</code>\n"
        "💰 <b>{amount} сум</b>\n"
        "💳 <code>{info}</code>"
    ),
    "approved": "✅ Подтверждено.",
    "rejected": "❌ Отклонено.",
    "withdraw_approved_user": (
        "✅ Заявка подтверждена.\n"
        "💰 {amount} сум"
    ),
    "withdraw_rejected_user": (
        "❌ Заявка отклонена.\n"
        "💰 {amount} сум возвращено."
    ),
    "no_pending_withdrawals": "⏳ Нет заявок.",
    "back_menu": "🔙 Главное меню.",
    "broadcast_result": (
        "📢 Рассылка завершена.\n\n"
        "✅ {success}\n"
        "🚫 {blocked}\n"
        "⚠️ {failed}"
    ),
    "stats": (
        "📊 Статистика\n\n"
        "👥 Пользователи: {users}\n"
        "🗳 Голоса: {votes}\n"
        "👁 Просмотры: {views}\n"
        "📌 Проекты: {projects}\n"
        "📰 Новости: {news}\n"
        "💰 Баланс: {balance} сум\n"
        "💸 Выведено: {withdrawn} сум\n"
        "⏳ Ожидает: {pending} сум"
    ),
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


class WithdrawStates(StatesGroup):
    waiting_amount = State()
    waiting_info = State()


# =========================================================
# DATABASE
# =========================================================

def get_db():
    db = sqlite3.connect(DB_PATH, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=30000")
    return db


def init_db():
    with closing(get_db()) as db:

        db.execute("""
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

        db.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name_uz TEXT,
                name_ru TEXT,
                url TEXT,
                click_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                project_id INTEGER NOT NULL,
                phone TEXT,
                reward INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, project_id)
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER,
                chat_id INTEGER,
                text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER NOT NULL,
                referred_id INTEGER UNIQUE NOT NULL,
                bonus INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                type TEXT,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS withdrawals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                payment_info TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP
            )
        """)

        db.commit()

    print("DATABASE TAYYOR", flush=True)


# =========================================================
# YORDAMCHI
# =========================================================

def money(value):
    return f"{int(value or 0):,}".replace(",", " ")


def add_or_update_user(message: Message):
    user = message.from_user

    with closing(get_db()) as db:
        db.execute("""
            INSERT INTO users(
                user_id, username, first_name
            )
            VALUES (?, ?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name
        """, (
            user.id,
            user.username,
            user.first_name,
        ))

        db.commit()


def get_language(user_id):
    with closing(get_db()) as db:
        row = db.execute(
            "SELECT language FROM users WHERE user_id=?",
            (user_id,)
        ).fetchone()

    return row["language"] if row and row["language"] in ("uz", "ru") else "uz"


def set_language(user_id, lang):
    with closing(get_db()) as db:
        db.execute(
            "UPDATE users SET language=? WHERE user_id=?",
            (lang, user_id)
        )
        db.commit()


def is_admin(user_id):
    return user_id in ADMIN_IDS


def add_transaction(db, user_id, amount, tx_type, description):
    db.execute("""
        INSERT INTO transactions(
            user_id, amount, type, description
        )
        VALUES (?, ?, ?, ?)
    """, (
        user_id,
        amount,
        tx_type,
        description,
    ))


def credit(db, user_id, amount, tx_type, description):
    db.execute("""
        UPDATE users
        SET balance=COALESCE(balance,0)+?,
            total_earned=COALESCE(total_earned,0)+?
        WHERE user_id=?
    """, (
        amount,
        amount,
        user_id,
    ))

    add_transaction(
        db,
        user_id,
        amount,
        tx_type,
        description
    )


# =========================================================
# KEYBOARDS
# =========================================================

def user_keyboard(lang):
    t = TEXTS[lang]

    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=t["projects"]),
                KeyboardButton(text=t["news"]),
            ],
            [
                KeyboardButton(text=t["balance"]),
                KeyboardButton(text=t["referral"]),
            ],
            [
                KeyboardButton(text=t["withdraw"]),
                KeyboardButton(text=t["help"]),
            ],
            [
                KeyboardButton(text=t["language"])
            ],
            [
                KeyboardButton(text=t["group_add"])
            ],
        ],
        resize_keyboard=True,
    )


def admin_keyboard(lang):
    t = TEXTS[lang]

    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t["statistics"])],
            [
                KeyboardButton(text=t["add_project"]),
                KeyboardButton(text=t["add_news"]),
            ],
            [KeyboardButton(text=t["broadcast"])],
            [KeyboardButton(text=t["withdrawals"])],
            [KeyboardButton(text=t["back"])],
        ],
        resize_keyboard=True,
    )


def phone_keyboard(lang):
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text=TEXTS[lang]["send_phone"],
                    request_contact=True
                )
            ],
            [KeyboardButton(text=TEXTS[lang]["cancel"])],
        ],
        resize_keyboard=True,
    )


def cancel_keyboard(lang):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=TEXTS[lang]["cancel"])]
        ],
        resize_keyboard=True,
    )


def main_keyboard(user_id, lang):
    return (
        admin_keyboard(lang)
        if is_admin(user_id)
        else user_keyboard(lang)
    )


# =========================================================
# START
# =========================================================

@dp.message(CommandStart())
async def start_handler(
    message: Message,
    state: FSMContext,
    command: CommandObject,
):
    await state.clear()

    add_or_update_user(message)

    lang = get_language(message.from_user.id)

    name = escape(
        message.from_user.first_name or "Foydalanuvchi"
    )

    await message.answer(
        TEXTS[lang]["welcome"].format(
            name=name,
            vote_reward=money(VOTE_REWARD),
            ref_reward=money(REFERRAL_REWARD),
        ),
        reply_markup=main_keyboard(
            message.from_user.id,
            lang
        )
    )


# =========================================================
# LANGUAGE
# =========================================================

@dp.message(F.text.in_({"🌐 Til", "🌐 Язык"}))
async def language_handler(message: Message):
    add_or_update_user(message)

    await message.answer(
        "🌐 Tilni tanlang / Выберите язык:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text="🇺🇿 O‘zbek"),
                    KeyboardButton(text="🇷🇺 Русский"),
                ]
            ],
            resize_keyboard=True
        )
    )


@dp.message(F.text == "🇺🇿 O‘zbek")
async def uz_handler(message: Message):
    add_or_update_user(message)

    set_language(
        message.from_user.id,
        "uz"
    )

    await message.answer(
        TEXTS["uz"]["language_saved"],
        reply_markup=main_keyboard(
            message.from_user.id,
            "uz"
        )
    )


@dp.message(F.text == "🇷🇺 Русский")
async def ru_handler(message: Message):
    add_or_update_user(message)

    set_language(
        message.from_user.id,
        "ru"
    )

    await message.answer(
        TEXTS["ru"]["language_saved"],
        reply_markup=main_keyboard(
            message.from_user.id,
            "ru"
        )
    )


# =========================================================
# BACK / CANCEL
# =========================================================

@dp.message(F.text.in_({
    "🔙 Orqaga",
    "🔙 Назад",
    "❌ Bekor qilish",
    "❌ Отмена",
}))
async def back_handler(
    message: Message,
    state: FSMContext
):
    await state.clear()

    lang = get_language(message.from_user.id)

    await message.answer(
        TEXTS[lang]["back_menu"],
        reply_markup=main_keyboard(
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

    lang = get_language(message.from_user.id)

    await message.answer(
        TEXTS[lang]["back_menu"],
        reply_markup=main_keyboard(
            message.from_user.id,
            lang
        )
    )


# =========================================================
# PROJECTS
# =========================================================

@dp.message(F.text.in_({
    "📌 Loyihalar",
    "📌 Проекты",
}))
async def projects_handler(message: Message):
    add_or_update_user(message)

    lang = get_language(message.from_user.id)

    with closing(get_db()) as db:
        rows = db.execute("""
            SELECT id, name_uz, name_ru, url
            FROM projects
            ORDER BY id DESC
        """).fetchall()

    if not rows:
        await message.answer(
            TEXTS[lang]["no_projects"],
            reply_markup=user_keyboard(lang)
        )
        return

    buttons = []

    for row in rows:
        name = (
            row["name_uz"]
            if lang == "uz"
            else row["name_ru"]
        )

        name = name or row["name_uz"] or "Loyiha"

        buttons.append([
            InlineKeyboardButton(
                text=f"📌 {name}",
                callback_data=f"project:{row['id']}"
            )
        ])

    await message.answer(
        TEXTS[lang]["select_project"],
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )


@dp.callback_query(F.data.startswith("project:"))
async def project_handler(callback: CallbackQuery):
    project_id = int(
        callback.data.split(":")[1]
    )

    lang = get_language(
        callback.from_user.id
    )

    with closing(get_db()) as db:
        row = db.execute("""
            SELECT *
            FROM projects
            WHERE id=?
        """, (project_id,)).fetchone()

        if row:
            db.execute("""
                UPDATE projects
                SET click_count=COALESCE(click_count,0)+1
                WHERE id=?
            """, (project_id,))

            db.commit()

    if not row:
        await callback.answer(
            TEXTS[lang]["project_not_found"],
            show_alert=True
        )
        return

    name = (
        row["name_uz"]
        if lang == "uz"
        else row["name_ru"]
    )

    buttons = []

    if row["url"]:
        buttons.append([
            InlineKeyboardButton(
                text=TEXTS[lang]["open_project"],
                url=row["url"]
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text=TEXTS[lang]["vote"],
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

    lang = get_language(
        callback.from_user.id
    )

    with closing(get_db()) as db:
        exists = db.execute("""
            SELECT id
            FROM projects
            WHERE id=?
        """, (project_id,)).fetchone()

        voted = db.execute("""
            SELECT id
            FROM votes
            WHERE user_id=? AND project_id=?
        """, (
            callback.from_user.id,
            project_id
        )).fetchone()

    if not exists:
        await callback.answer(
            TEXTS[lang]["project_not_found"],
            show_alert=True
        )
        return

    if voted:
        await callback.answer(
            TEXTS[lang]["already_voted"],
            show_alert=True
        )
        return

    await state.update_data(
        project_id=project_id
    )

    await state.set_state(
        VoteStates.waiting_phone
    )

    await callback.message.answer(
        TEXTS[lang]["phone_required"],
        reply_markup=phone_keyboard(lang)
    )

    await callback.answer()


@dp.message(
    VoteStates.waiting_phone,
    F.contact
)
async def vote_phone(
    message: Message,
    state: FSMContext
):
    data = await state.get_data()

    project_id = data.get("project_id")

    if not project_id:
        await state.clear()
        return

    lang = get_language(
        message.from_user.id
    )

    contact = message.contact

    if (
        contact.user_id
        and contact.user_id != message.from_user.id
    ):
        await message.answer(
            TEXTS[lang]["own_phone_only"]
        )
        return

    phone = contact.phone_number

    with closing(get_db()) as db:
        db.execute("BEGIN IMMEDIATE")

        voted = db.execute("""
            SELECT id
            FROM votes
            WHERE user_id=? AND project_id=?
        """, (
            message.from_user.id,
            project_id
        )).fetchone()

        if voted:
            db.rollback()

            await state.clear()

            await message.answer(
                TEXTS[lang]["already_voted"],
                reply_markup=user_keyboard(lang)
            )

            return

        db.execute("""
            INSERT INTO votes(
                user_id,
                project_id,
                phone,
                reward
            )
            VALUES (?, ?, ?, ?)
        """, (
            message.from_user.id,
            project_id,
            phone,
            VOTE_REWARD
        ))

        credit(
            db,
            message.from_user.id,
            VOTE_REWARD,
            "vote",
            f"Loyiha #{project_id} uchun ovoz"
        )

        db.execute("""
            UPDATE users
            SET phone=?
            WHERE user_id=?
        """, (
            phone,
            message.from_user.id
        ))

        db.commit()

    await state.clear()

    await message.answer(
        TEXTS[lang]["vote_success"].format(
            amount=money(VOTE_REWARD)
        ),
        reply_markup=user_keyboard(lang)
    )


@dp.message(VoteStates.waiting_phone)
async def vote_waiting_phone(message: Message):
    lang = get_language(
        message.from_user.id
    )

    await message.answer(
        TEXTS[lang]["phone_required"],
        reply_markup=phone_keyboard(lang)
    )


# =========================================================
# ADD PROJECT
# =========================================================

@dp.message(F.text.in_({
    "➕ Loyiha qo'shish",
    "➕ Loyiha qo‘shish",
    "➕ Добавить проект",
}))
async def add_project(
    message: Message,
    state: FSMContext
):
    if not is_admin(message.from_user.id):
        await message.answer(
            TEXTS["uz"]["admin_only"]
        )
        return

    lang = get_language(
        message.from_user.id
    )

    await state.clear()

    await state.set_state(
        ProjectStates.waiting_name
    )

    await message.answer(
        TEXTS[lang]["project_name"]
    )


@dp.message(ProjectStates.waiting_name)
async def project_name(
    message: Message,
    state: FSMContext
):
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    lang = get_language(
        message.from_user.id
    )

    name = (message.text or "").strip()

    if len(name) < 2:
        await message.answer(
            TEXTS[lang]["project_invalid_name"]
        )
        return

    await state.update_data(
        project_name=name
    )

    await state.set_state(
        ProjectStates.waiting_link
    )

    await message.answer(
        TEXTS[lang]["project_link"]
    )


@dp.message(ProjectStates.waiting_link)
async def project_link(
    message: Message,
    state: FSMContext
):
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    lang = get_language(
        message.from_user.id
    )

    url = (message.text or "").strip()

    parsed = urlparse(url)

    if (
        parsed.scheme not in ("http", "https")
        or not parsed.netloc
    ):
        await message.answer(
            TEXTS[lang]["invalid_link"]
        )
        return

    data = await state.get_data()

    name = data.get("project_name")

    with closing(get_db()) as db:
        db.execute("""
            INSERT INTO projects(
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

        db.commit()

    await state.clear()

    await message.answer(
        TEXTS[lang]["project_created"],
        reply_markup=admin_keyboard(lang)
    )


# =========================================================
# NEWS
# =========================================================

@dp.message(F.text.in_({
    "📰 Yangilik qo'shish",
    "📰 Yangilik qo‘shish",
    "📰 Добавить новость",
}))
async def news_add_start(
    message: Message,
    state: FSMContext
):
    if not is_admin(message.from_user.id):
        await message.answer(
            TEXTS["uz"]["admin_only"]
        )
        return

    lang = get_language(
        message.from_user.id
    )

    await state.clear()

    await state.set_state(
        NewsStates.waiting_content
    )

    await message.answer(
        TEXTS[lang]["send_news"]
    )


@dp.message(NewsStates.waiting_content)
async def news_add(
    message: Message,
    state: FSMContext
):
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    text = message.text or message.caption or ""

    with closing(get_db()) as db:
        db.execute("""
            INSERT INTO news(
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

    await broadcast(
        message.chat.id,
        message.message_id
    )

    await state.clear()

    lang = get_language(
        message.from_user.id
    )

    await message.answer(
        TEXTS[lang]["news_saved"],
        reply_markup=admin_keyboard(lang)
    )


@dp.message(F.text.in_({
    "📰 Yangiliklar",
    "📰 Новости",
}))
async def news_list(message: Message):
    lang = get_language(
        message.from_user.id
    )

    with closing(get_db()) as db:
        rows = db.execute("""
            SELECT *
            FROM news
            ORDER BY id DESC
            LIMIT 10
        """).fetchall()

    if not rows:
        await message.answer(
            TEXTS[lang]["news_empty"]
        )
        return

    for row in rows:
        try:
            await bot.copy_message(
                chat_id=message.chat.id,
                from_chat_id=row["chat_id"],
                message_id=row["message_id"]
            )
        except Exception:
            if row["text"]:
                await message.answer(
                    row["text"]
                )


# =========================================================
# BROADCAST
# =========================================================

async def broadcast(
    source_chat_id,
    source_message_id
):
    success = 0
    blocked = 0
    failed = 0

    with closing(get_db()) as db:
        users = db.execute(
            "SELECT user_id FROM users"
        ).fetchall()

    for user in users:
        uid = user["user_id"]

        try:
            await bot.copy_message(
                chat_id=uid,
                from_chat_id=source_chat_id,
                message_id=source_message_id
            )

            success += 1

            await asyncio.sleep(0.05)

        except TelegramForbiddenError:
            blocked += 1

            with closing(get_db()) as db:
                db.execute(
                    "DELETE FROM users WHERE user_id=?",
                    (uid,)
                )
                db.commit()

        except TelegramRetryAfter as e:
            await asyncio.sleep(
                e.retry_after
            )

        except Exception:
            failed += 1

    return success, blocked, failed


@dp.message(F.text.in_({
    "📢 Reklama tarqatish",
    "📢 Рассылка",
}))
async def broadcast_start(
    message: Message,
    state: FSMContext
):
    if not is_admin(message.from_user.id):
        await message.answer(
            TEXTS["uz"]["admin_only"]
        )
        return

    lang = get_language(
        message.from_user.id
    )

    await state.clear()

    await state.set_state(
        BroadcastStates.waiting_content
    )

    await message.answer(
        TEXTS[lang]["send_broadcast"]
    )


@dp.message(BroadcastStates.waiting_content)
async def broadcast_handler(
    message: Message,
    state: FSMContext
):
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    success, blocked, failed = await broadcast(
        message.chat.id,
        message.message_id
    )

    await state.clear()

    lang = get_language(
        message.from_user.id
    )

    await message.answer(
        TEXTS[lang]["broadcast_result"].format(
            success=success,
            blocked=blocked,
            failed=failed
        ),
        reply_markup=admin_keyboard(lang)
    )


# =========================================================
# BALANCE
# =========================================================

@dp.message(F.text.in_({
    "💰 Balans",
    "💰 Баланс",
}))
async def balance_handler(message: Message):
    lang = get_language(
        message.from_user.id
    )

    with closing(get_db()) as db:
        row = db.execute("""
            SELECT balance,
                   total_earned,
                   total_withdrawn
            FROM users
            WHERE user_id=?
        """, (
            message.from_user.id,
        )).fetchone()

    if not row:
        return

    await message.answer(
        TEXTS[lang]["balance_text"].format(
            balance=money(row["balance"]),
            earned=money(row["total_earned"]),
            withdrawn=money(row["total_withdrawn"]),
        ),
        parse_mode="HTML",
        reply_markup=user_keyboard(lang)
    )


# =========================================================
# REFERRAL
# =========================================================

@dp.message(F.text.in_({
    "🔗 Referal ssilka",
    "🔗 Реферальная ссылка",
}))
async def referral_handler(message: Message):
    lang = get_language(
        message.from_user.id
    )

    me = await bot.get_me()

    link = (
        f"https://t.me/{me.username}"
        f"?start=ref_{message.from_user.id}"
    )

    with closing(get_db()) as db:
        count = db.execute("""
            SELECT COUNT(*)
            FROM referrals
            WHERE referrer_id=?
        """, (
            message.from_user.id,
        )).fetchone()[0]

        earned = db.execute("""
            SELECT COALESCE(SUM(bonus),0)
            FROM referrals
            WHERE referrer_id=?
            AND status='rewarded'
        """, (
            message.from_user.id,
        )).fetchone()[0]

    await message.answer(
        TEXTS[lang]["referral_text"].format(
            link=escape(link),
            count=count,
            earned=money(earned)
        ),
        parse_mode="HTML"
    )


# =========================================================
# HELP
# =========================================================

@dp.message(F.text.in_({
    "❓ Yordam",
    "❓ Помощь",
}))
async def help_handler(message: Message):
    lang = get_language(
        message.from_user.id
    )

    await message.answer(
        TEXTS[lang]["help_text"],
        reply_markup=user_keyboard(lang)
    )


# =========================================================
# GROUP ADD
# =========================================================

@dp.message(F.text.in_({
    "👥 Guruhga qo'shish",
    "👥 Guruhga qo‘shish",
    "👥 Добавить в группу",
}))
async def group_handler(message: Message):
    lang = get_language(
        message.from_user.id
    )

    me = await bot.get_me()

    link = (
        f"https://t.me/{me.username}"
        "?startgroup=true"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=TEXTS[lang]["group_add"],
                    url=link
                )
            ]
        ]
    )

    await message.answer(
        TEXTS[lang]["group_add_text"],
        reply_markup=keyboard
    )


# =========================================================
# STATISTICS
# =========================================================

@dp.message(F.text.in_({
    "📊 Statistika",
    "📊 Статистика",
}))
async def statistics(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer(
            TEXTS["uz"]["admin_only"]
        )
        return

    lang = get_language(
        message.from_user.id
    )

    with closing(get_db()) as db:

        users = db.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]

        votes = db.execute(
            "SELECT COUNT(*) FROM votes"
        ).fetchone()[0]

        views = db.execute(
            "SELECT COALESCE(SUM(click_count),0) FROM projects"
        ).fetchone()[0]

        projects = db.execute(
            "SELECT COUNT(*) FROM projects"
        ).fetchone()[0]

        news = db.execute(
            "SELECT COUNT(*) FROM news"
        ).fetchone()[0]

        balance = db.execute(
            "SELECT COALESCE(SUM(balance),0) FROM users"
        ).fetchone()[0]

        withdrawn = db.execute(
            "SELECT COALESCE(SUM(total_withdrawn),0) FROM users"
        ).fetchone()[0]

        pending = db.execute("""
            SELECT COALESCE(SUM(amount),0)
            FROM withdrawals
            WHERE status='pending'
        """).fetchone()[0]

    await message.answer(
        TEXTS[lang]["stats"].format(
            users=users,
            votes=votes,
            views=views,
            projects=projects,
            news=news,
            balance=money(balance),
            withdrawn=money(withdrawn),
            pending=money(pending)
        ),
        reply_markup=admin_keyboard(lang)
    )


# =========================================================
# WITHDRAW
# =========================================================

@dp.message(F.text.in_({
    "💸 Pul yechish",
    "💸 Вывести деньги",
}))
async def withdraw_start(
    message: Message,
    state: FSMContext
):
    lang = get_language(
        message.from_user.id
    )

    with closing(get_db()) as db:
        balance = db.execute("""
            SELECT balance
            FROM users
            WHERE user_id=?
        """, (
            message.from_user.id,
        )).fetchone()[0]

    if balance < MIN_WITHDRAW:
        await message.answer(
            TEXTS[lang]["min_amount"].format(
                amount=money(MIN_WITHDRAW)
            )
        )
        return

    await state.set_state(
        WithdrawStates.waiting_amount
    )

    await message.answer(
        TEXTS[lang]["withdraw_amount"].format(
            minimum=money(MIN_WITHDRAW),
            balance=money(balance)
        ),
        parse_mode="HTML",
        reply_markup=cancel_keyboard(lang)
    )


@dp.message(WithdrawStates.waiting_amount)
async def withdraw_amount(
    message: Message,
    state: FSMContext
):
    lang = get_language(
        message.from_user.id
    )

    raw = (message.text or "").replace(
        " ",
        ""
    )

    if not raw.isdigit():
        await message.answer(
            TEXTS[lang]["invalid_amount"]
        )
        return

    amount = int(raw)

    if amount < MIN_WITHDRAW:
        await message.answer(
            TEXTS[lang]["min_amount"].format(
                amount=money(MIN_WITHDRAW)
            )
        )
        return

    with closing(get_db()) as db:
        balance = db.execute("""
            SELECT balance
            FROM users
            WHERE user_id=?
        """, (
            message.from_user.id,
        )).fetchone()[0]

    if amount > balance:
        await message.answer(
            TEXTS[lang]["not_enough"]
        )
        return

    await state.update_data(
        amount=amount
    )

    await state.set_state(
        WithdrawStates.waiting_info
    )

    await message.answer(
        TEXTS[lang]["withdraw_info"],
        reply_markup=cancel_keyboard(lang)
    )


@dp.message(WithdrawStates.waiting_info)
async def withdraw_info(
    message: Message,
    state: FSMContext
):
    lang = get_language(
        message.from_user.id
    )

    info = (message.text or "").strip()

    if len(info) < 3:
        await message.answer(
            TEXTS[lang]["withdraw_info"]
        )
        return

    data = await state.get_data()

    amount = int(
        data.get("amount", 0)
    )

    with closing(get_db()) as db:
        db.execute("BEGIN IMMEDIATE")

        row = db.execute("""
            SELECT balance
            FROM users
            WHERE user_id=?
        """, (
            message.from_user.id,
        )).fetchone()

        if not row or row["balance"] < amount:
            db.rollback()

            await state.clear()

            await message.answer(
                TEXTS[lang]["not_enough"],
                reply_markup=user_keyboard(lang)
            )
            return

        db.execute("""
            UPDATE users
            SET balance=balance-?
            WHERE user_id=?
        """, (
            amount,
            message.from_user.id
        ))

        cursor = db.execute("""
            INSERT INTO withdrawals(
                user_id,
                amount,
                payment_info,
                status
            )
            VALUES (?, ?, ?, 'pending')
        """, (
            message.from_user.id,
            amount,
            info
        ))

        request_id = cursor.lastrowid

        db.commit()

    await state.clear()

    await message.answer(
        TEXTS[lang]["withdraw_created"].format(
            amount=money(amount),
            request_id=request_id
        ),
        parse_mode="HTML",
        reply_markup=user_keyboard(lang)
    )

    for admin_id in ADMIN_IDS:
        try:
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[[
                    InlineKeyboardButton(
                        text="✅ Tasdiqlash",
                        callback_data=f"wd_ok:{request_id}"
                    ),
                    InlineKeyboardButton(
                        text="❌ Rad etish",
                        callback_data=f"wd_no:{request_id}"
                    )
                ]]
            )

            await bot.send_message(
                admin_id,
                TEXTS["uz"]["withdraw_request"].format(
                    request_id=request_id,
                    user=escape(
                        message.from_user.username
                        or message.from_user.first_name
                        or str(message.from_user.id)
                    ),
                    user_id=message.from_user.id,
                    amount=money(amount),
                    info=escape(info)
                ),
                parse_mode="HTML",
                reply_markup=keyboard
            )

        except Exception as e:
            logger.error(
                "Admin xabari xatosi: %s",
                e
            )


# =========================================================
# ADMIN WITHDRAW APPROVE
# =========================================================

@dp.callback_query(F.data.startswith("wd_ok:"))
async def withdraw_ok(
    callback: CallbackQuery
):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "Faqat admin.",
            show_alert=True
        )
        return

    request_id = int(
        callback.data.split(":")[1]
    )

    with closing(get_db()) as db:

        row = db.execute("""
            SELECT user_id, amount, status
            FROM withdrawals
            WHERE id=?
        """, (
            request_id,
        )).fetchone()

        if not row or row["status"] != "pending":
            await callback.answer(
                "So'rov topilmadi.",
                show_alert=True
            )
            return

        db.execute("""
            UPDATE withdrawals
            SET status='approved',
                processed_at=CURRENT_TIMESTAMP
            WHERE id=?
        """, (
            request_id,
        ))

        db.execute("""
            UPDATE users
            SET total_withdrawn=
                COALESCE(total_withdrawn,0)+?
            WHERE user_id=?
        """, (
            row["amount"],
            row["user_id"]
        ))

        db.commit()

    try:
        lang = get_language(
            row["user_id"]
        )

        await bot.send_message(
            row["user_id"],
            TEXTS[lang]["withdraw_approved_user"].format(
                amount=money(row["amount"])
            )
        )
    except Exception:
        pass

    await callback.message.edit_reply_markup(
        reply_markup=None
    )

    await callback.answer(
        "Tasdiqlandi."
    )


# =========================================================
# ADMIN WITHDRAW REJECT
# =========================================================

@dp.callback_query(F.data.startswith("wd_no:"))
async def withdraw_no(
    callback: CallbackQuery
):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "Faqat admin.",
            show_alert=True
        )
        return

    request_id = int(
        callback.data.split(":")[1]
    )

    with closing(get_db()) as db:

        row = db.execute("""
            SELECT user_id, amount, status
            FROM withdrawals
            WHERE id=?
        """, (
            request_id,
        )).fetchone()

        if not row or row["status"] != "pending":
            await callback.answer(
                "So'rov topilmadi.",
                show_alert=True
            )
            return

        db.execute("""
            UPDATE withdrawals
            SET status='rejected',
                processed_at=CURRENT_TIMESTAMP
            WHERE id=?
        """, (
            request_id,
        ))

        db.execute("""
            UPDATE users
            SET balance=COALESCE(balance,0)+?
            WHERE user_id=?
        """, (
            row["amount"],
            row["user_id"]
        ))

        db.commit()

    try:
        lang = get_language(
            row["user_id"]
        )

        await bot.send_message(
            row["user_id"],
            TEXTS[lang]["withdraw_rejected_user"].format(
                amount=money(row["amount"])
            )
        )

    except Exception:
        pass

    await callback.message.edit_reply_markup(
        reply_markup=None
    )

    await callback.answer(
        "Rad etildi."
    )


# =========================================================
# ADMIN WITHDRAW LIST
# =========================================================

@dp.message(F.text.in_({
    "💸 Yechishlar",
    "💸 Заявки на вывод",
}))
async def withdrawal_list(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer(
            TEXTS["uz"]["admin_only"]
        )
        return

    with closing(get_db()) as db:
        rows = db.execute("""
            SELECT
                w.*,
                u.username,
                u.first_name
            FROM withdrawals w
            LEFT JOIN users u
            ON u.user_id=w.user_id
            WHERE w.status='pending'
            ORDER BY w.id
        """).fetchall()

    if not rows:
        await message.answer(
            TEXTS["uz"]["no_pending_withdrawals"]
        )
        return

    for row in rows:

        user_name = (
            f"@{row['username']}"
            if row["username"]
            else row["first_name"]
            or str(row["user_id"])
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(
                    text="✅ Tasdiqlash",
                    callback_data=f"wd_ok:{row['id']}"
                ),
                InlineKeyboardButton(
                    text="❌ Rad etish",
                    callback_data=f"wd_no:{row['id']}"
                )
            ]]
        )

        await message.answer(
            TEXTS["uz"]["withdraw_request"].format(
                request_id=row["id"],
                user=escape(user_name),
                user_id=row["user_id"],
                amount=money(row["amount"]),
                info=escape(row["payment_info"])
            ),
            parse_mode="HTML",
            reply_markup=keyboard
        )


# =========================================================
# ADMIN
# =========================================================

@dp.message(Command("admin"))
async def admin_command(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer(
            TEXTS["uz"]["admin_only"]
        )
        return

    lang = get_language(
        message.from_user.id
    )

    await message.answer(
        TEXTS[lang]["admin_panel"],
        reply_markup=admin_keyboard(lang)
    )


# =========================================================
# UNKNOWN
# =========================================================

@dp.message()
async def unknown_handler(message: Message):
    if not message.from_user:
        return

    add_or_update_user(message)

    lang = get_language(
        message.from_user.id
    )

    await message.answer(
        TEXTS[lang]["unknown"],
        reply_markup=main_keyboard(
            message.from_user.id,
            lang
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

    me = await bot.get_me()

    print(
        f"BOT ULANDI: @{me.username}",
        flush=True
    )

    print(
        "POLLING BOSHLANMOQDA...",
        flush=True
    )

    await dp.start_polling(
        bot
    )


if __name__ == "__main__":
    asyncio.run(main())