# ============================================================
# MAIN.PY — TELEGRAM BOT
# BARQAROR / SQLITE WAL / RETRY / REFERRAL / ADMIN PANEL
# ============================================================

import asyncio
import logging
import re
import sqlite3
from contextlib import closing
from html import escape
from urllib.parse import quote

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.exceptions import TelegramRetryAfter, TelegramForbiddenError


# ============================================================
# SOZLAMALAR
# ============================================================

# MUHIM:
# Bu yerga BotFather bergan YANGI tokenni qo'ying.
# Eski ochiq bo'lgan tokenni ishlatmang.
BOT_TOKEN = "8615736731:AAF7LGgYsKCq_JjV9qFPmFV6psTAS4mlQ_g"

# ADMIN TELEGRAM ID
ADMIN_IDS = {7998053914}

DB_NAME = "bot.db"

VOTE_REWARD = 30000
REFERRAL_REWARD = 10000
MIN_WITHDRAW = 30000

API_RETRIES = 4
DB_TIMEOUT = 30

# Broadcast tezligi
BROADCAST_DELAY = 0.12

# Bir vaqtning o'zida nechta broadcast yuboruvchi ishlashi
BROADCAST_WORKERS = 3


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)


# ============================================================
# BOT
# ============================================================

bot = Bot(
    BOT_TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML
    )
)

dp = Dispatcher()


# ============================================================
# LOCKLAR
# ============================================================

# SQLite yozuvlarini tartibli bajarish uchun.
db_write_lock = asyncio.Lock()

# Broadcast bir vaqtda faqat bittasi ishlaydi.
broadcast_lock = asyncio.Lock()


# ============================================================
# STATES
# ============================================================

class UserStates(StatesGroup):
    question = State()
    phone = State()
    card = State()


class AdminStates(StatesGroup):
    reply = State()
    project_name = State()
    project_url = State()
    vote_url = State()
    contact = State()
    broadcast = State()
    proof_channel = State()


# ============================================================
# MENU TEXTLARI
# ============================================================

USER_MENU_TEXTS = {
    "📌 Loyihalar",
    "🗳 Ovoz berish",
    "📢 Isbot kanali",
    "💰 Balans",
    "💳 Pul yechish",
    "👥 Do‘stlarni taklif qilish",
    "❓ Savol-javob",
    "👨‍💻 Admin bilan bog‘lanish",
}

ADMIN_MENU_TEXTS = {
    "📊 Statistika",
    "👥 Foydalanuvchilar",
    "🗳 Ovozlar",
    "📱 Telefon ovozlari",
    "💳 Pul yechishlar",
    "❓ Savollar",
    "👥 Referallar",
    "🔗 Ovoz havolasi",
    "👨‍💻 Admin kontakt",
    "📢 Isbot kanali",
    "➕ Loyiha qo‘shish",
    "📌 Loyihalar",
    "📢 Reklama",
    "🏠 Foydalanuvchi menyusi",
}

ALL_MENU_TEXTS = USER_MENU_TEXTS | ADMIN_MENU_TEXTS


# ============================================================
# USER MENU
# ============================================================

def user_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📌 Loyihalar"),
                KeyboardButton(text="🗳 Ovoz berish"),
            ],
            [
                KeyboardButton(text="📢 Isbot kanali"),
                KeyboardButton(text="💰 Balans"),
            ],
            [
                KeyboardButton(text="💳 Pul yechish"),
                KeyboardButton(text="👥 Do‘stlarni taklif qilish"),
            ],
            [
                KeyboardButton(text="❓ Savol-javob"),
                KeyboardButton(text="👨‍💻 Admin bilan bog‘lanish"),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


# ============================================================
# ADMIN MENU
# ============================================================

def admin_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📊 Statistika"),
                KeyboardButton(text="👥 Foydalanuvchilar"),
            ],
            [
                KeyboardButton(text="🗳 Ovozlar"),
                KeyboardButton(text="📱 Telefon ovozlari"),
            ],
            [
                KeyboardButton(text="💳 Pul yechishlar"),
                KeyboardButton(text="❓ Savollar"),
            ],
            [
                KeyboardButton(text="👥 Referallar"),
                KeyboardButton(text="🔗 Ovoz havolasi"),
            ],
            [
                KeyboardButton(text="👨‍💻 Admin kontakt"),
                KeyboardButton(text="📢 Isbot kanali"),
            ],
            [
                KeyboardButton(text="➕ Loyiha qo‘shish"),
                KeyboardButton(text="📌 Loyihalar"),
            ],
            [
                KeyboardButton(text="📢 Reklama"),
            ],
            [
                KeyboardButton(text="🏠 Foydalanuvchi menyusi"),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


# ============================================================
# INLINE TUGMALAR
# ============================================================

def vote_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔗 Havola orqali",
                    callback_data="vote_link",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📱 Telefon raqami orqali",
                    callback_data="vote_phone",
                )
            ],
        ]
    )


def vote_admin_kb(vote_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Tasdiqlash",
                    callback_data=f"va:{vote_id}",
                ),
                InlineKeyboardButton(
                    text="❌ Rad etish",
                    callback_data=f"vr:{vote_id}",
                ),
            ]
        ]
    )


def chat_kb(user_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 Javob berish",
                    callback_data=f"reply:{user_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔒 Suhbatni yopish",
                    callback_data=f"close:{user_id}",
                )
            ],
        ]
    )


def withdraw_kb(withdraw_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ To‘landi",
                    callback_data=f"wp:{withdraw_id}",
                ),
                InlineKeyboardButton(
                    text="❌ Rad etish",
                    callback_data=f"wr:{withdraw_id}",
                ),
            ]
        ]
    )


# ============================================================
# DATABASE
# ============================================================

def db():
    connection = sqlite3.connect(
        DB_NAME,
        timeout=DB_TIMEOUT,
        isolation_level=None,
    )

    connection.row_factory = sqlite3.Row

    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.execute("PRAGMA busy_timeout=30000")
    connection.execute("PRAGMA foreign_keys=ON")

    return connection


def init_db():
    with closing(db()) as c:

        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT DEFAULT '',
                first_name TEXT DEFAULT '',
                balance INTEGER DEFAULT 0,
                referrals INTEGER DEFAULT 0,
                referred_by INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                url TEXT DEFAULT '',
                active INTEGER DEFAULT 1
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                vote_type TEXT NOT NULL,
                phone TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                reward INTEGER DEFAULT 30000,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS used_phones (
                phone TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                vote_id INTEGER NOT NULL
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                inviter_id INTEGER NOT NULL,
                invited_id INTEGER UNIQUE NOT NULL,
                reward INTEGER DEFAULT 10000,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS withdrawals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                card_number TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                user_id INTEGER PRIMARY KEY,
                status TEXT DEFAULT 'closed',
                admin_id INTEGER
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                admin_id INTEGER,
                direction TEXT NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT DEFAULT ''
            )
        """)

        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_votes_status
            ON votes(status)
        """)

        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_votes_user
            ON votes(user_id)
        """)

        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_votes_type
            ON votes(vote_type)
        """)

        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_user
            ON messages(user_id)
        """)

        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_withdrawals_status
            ON withdrawals(status)
        """)

        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_withdrawals_user
            ON withdrawals(user_id)
        """)

        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_referrals_inviter
            ON referrals(inviter_id)
        """)


# ============================================================
# DATABASE YORDAMCHILARI
# ============================================================

def setting(key, default=""):
    with closing(db()) as c:
        row = c.execute(
            "SELECT value FROM settings WHERE key=?",
            (key,),
        ).fetchone()

    return row["value"] if row else default


async def set_setting_async(key, value):
    async with db_write_lock:
        with closing(db()) as c:
            c.execute("BEGIN IMMEDIATE")

            c.execute("""
                INSERT INTO settings(key, value)
                VALUES(?, ?)
                ON CONFLICT(key)
                DO UPDATE SET value=excluded.value
            """, (key, value))

            c.commit()


def set_setting(key, value):
    with closing(db()) as c:
        c.execute("""
            INSERT INTO settings(key, value)
            VALUES(?, ?)
            ON CONFLICT(key)
            DO UPDATE SET value=excluded.value
        """, (key, value))


def user_row(user_id):
    with closing(db()) as c:
        return c.execute(
            "SELECT * FROM users WHERE user_id=?",
            (user_id,),
        ).fetchone()


def money(value):
    return f"{int(value):,}".replace(",", " ")


def normalize_phone(value):
    value = re.sub(
        r"[^\d+]",
        "",
        value or "",
    )

    if value.startswith("00"):
        value = "+" + value[2:]

    return value


def valid_phone(value):
    phone = normalize_phone(value)

    digits = (
        phone[1:]
        if phone.startswith("+")
        else phone
    )

    return (
        digits.isdigit()
        and 8 <= len(digits) <= 15
    )


def valid_url(value):
    return bool(
        re.match(
            r"^https?://",
            (value or "").strip(),
            re.IGNORECASE,
        )
    )


def is_admin(user_id):
    return user_id in ADMIN_IDS


# ============================================================
# SAFE TELEGRAM
# ============================================================

async def safe_send_message(
    user_id,
    text,
    reply_markup=None,
    retries=API_RETRIES,
):
    for attempt in range(retries):

        try:
            return await bot.send_message(
                user_id,
                text,
                reply_markup=reply_markup,
            )

        except TelegramRetryAfter as exc:

            wait_time = max(
                int(exc.retry_after),
                1,
            )

            logger.warning(
                "Telegram flood limit. %s son kutamiz.",
                wait_time,
            )

            await asyncio.sleep(wait_time)

        except TelegramForbiddenError:

            logger.info(
                "User botni bloklagan: %s",
                user_id,
            )

            return None

        except Exception as exc:

            logger.warning(
                "send_message xato %s/%s user=%s: %s",
                attempt + 1,
                retries,
                user_id,
                exc,
            )

            if attempt < retries - 1:
                await asyncio.sleep(
                    1.5 * (attempt + 1)
                )

    return None


async def safe_answer_callback(
    callback,
    text=None,
    show_alert=False,
):
    try:
        await callback.answer(
            text or "",
            show_alert=show_alert,
        )
    except Exception:
        pass


# ============================================================
# START
# ============================================================

@dp.message(CommandStart())
async def start_handler(
    message: Message,
    state: FSMContext,
):
    await state.clear()

    referred_by = None

    parts = (
        message.text or ""
    ).split(
        maxsplit=1
    )

    if len(parts) == 2:

        code = parts[1].strip()

        if code.startswith("ref_"):

            try:
                referred_by = int(code[4:])
            except ValueError:
                referred_by = None

    user = message.from_user

    is_new = False

    async with db_write_lock:

        with closing(db()) as c:

            c.execute("BEGIN IMMEDIATE")

            old = c.execute(
                "SELECT user_id FROM users WHERE user_id=?",
                (user.id,),
            ).fetchone()

            if old:

                c.execute("""
                    UPDATE users
                    SET username=?,
                        first_name=?
                    WHERE user_id=?
                """, (
                    user.username or "",
                    user.first_name or "",
                    user.id,
                ))

            else:

                if referred_by == user.id:
                    referred_by = None

                if referred_by:

                    exists = c.execute(
                        "SELECT user_id FROM users WHERE user_id=?",
                        (referred_by,),
                    ).fetchone()

                    if not exists:
                        referred_by = None

                c.execute("""
                    INSERT INTO users(
                        user_id,
                        username,
                        first_name,
                        referred_by
                    )
                    VALUES(?,?,?,?)
                """, (
                    user.id,
                    user.username or "",
                    user.first_name or "",
                    referred_by,
                ))

                is_new = True

            c.commit()

    # Referral faqat yangi foydalanuvchi uchun
    if (
        is_new
        and referred_by
        and referred_by != user.id
    ):

        referral_added = False

        async with db_write_lock:

            with closing(db()) as c:

                c.execute("BEGIN IMMEDIATE")

                inviter = c.execute(
                    "SELECT user_id FROM users WHERE user_id=?",
                    (referred_by,),
                ).fetchone()

                already = c.execute(
                    "SELECT id FROM referrals WHERE invited_id=?",
                    (user.id,),
                ).fetchone()

                if inviter and not already:

                    c.execute("""
                        INSERT INTO referrals(
                            inviter_id,
                            invited_id,
                            reward
                        )
                        VALUES(?,?,?)
                    """, (
                        referred_by,
                        user.id,
                        REFERRAL_REWARD,
                    ))

                    c.execute("""
                        UPDATE users
                        SET balance=balance+?,
                            referrals=referrals+1
                        WHERE user_id=?
                    """, (
                        REFERRAL_REWARD,
                        referred_by,
                    ))

                    c.commit()
                    referral_added = True

                else:
                    c.rollback()

        if referral_added:

            await safe_send_message(
                referred_by,
                "🎉 <b>Yangi do‘st taklif qilindi!</b>\n\n"
                f"💰 Balansingizga "
                f"<b>+{money(REFERRAL_REWARD)} so‘m</b> qo‘shildi.",
            )

    if is_admin(user.id):

        await message.answer(
            "👨‍💼 <b>Admin panel</b>",
            reply_markup=admin_kb(),
        )

    else:

        await message.answer(
            "👋 <b>Assalomu alaykum!</b>\n\n"
            "Botga xush kelibsiz.\n"
            "Kerakli bo‘limni pastdagi menyudan tanlang.",
            reply_markup=user_kb(),
        )


# ============================================================
# ADMIN COMMAND
# ============================================================

@dp.message(Command("admin"))
async def admin_command(
    message: Message,
    state: FSMContext,
):
    await state.clear()

    if not is_admin(message.from_user.id):

        await message.answer(
            "❌ Siz admin emassiz."
        )
        return

    await message.answer(
        "👨‍💼 <b>Admin panel</b>",
        reply_markup=admin_kb(),
    )


# ============================================================
# MENU ROUTER
# ============================================================

@dp.message(F.text.in_(ALL_MENU_TEXTS))
async def menu_router(
    message: Message,
    state: FSMContext,
):
    await state.clear()

    text = message.text
    user_id = message.from_user.id

    # ========================================================
    # ADMIN
    # ========================================================

    if is_admin(user_id):

        if text == "🏠 Foydalanuvchi menyusi":

            await message.answer(
                "🏠 <b>Foydalanuvchi menyusi</b>",
                reply_markup=user_kb(),
            )
            return

        if text == "📊 Statistika":
            await statistics(message)
            return

        if text == "👥 Foydalanuvchilar":
            await admin_users(message)
            return

        if text == "🗳 Ovozlar":
            await admin_votes(message)
            return

        if text == "📱 Telefon ovozlari":
            await admin_phone_votes(message)
            return

        if text == "💳 Pul yechishlar":
            await admin_withdrawals(message)
            return

        if text == "❓ Savollar":
            await admin_questions(message)
            return

        if text == "👥 Referallar":
            await admin_referrals(message)
            return

        if text == "🔗 Ovoz havolasi":
            await vote_url_start(message, state)
            return

        if text == "👨‍💻 Admin kontakt":
            await contact_start(message, state)
            return

        if text == "📢 Isbot kanali":
            await proof_channel_handler(message, state)
            return

        if text == "➕ Loyiha qo‘shish":
            await project_start(message, state)
            return

        if text == "📌 Loyihalar":
            await projects_handler(message)
            return

        if text == "📢 Reklama":
            await broadcast_start(message, state)
            return

        # Admin user menyusiga o'tgan bo'lsa ham
        # user tugmalari ishlashi uchun:
        if text == "🗳 Ovoz berish":
            await vote_start(message)
            return

        if text == "💰 Balans":
            await balance_handler(message)
            return

        if text == "💳 Pul yechish":
            await withdraw_start(message, state)
            return

        if text == "👥 Do‘stlarni taklif qilish":
            await referral_handler(message)
            return

        if text == "❓ Savol-javob":
            await question_start(message, state)
            return

        if text == "👨‍💻 Admin bilan bog‘lanish":
            await admin_contact_handler(message)
            return

        return

    # ========================================================
    # USER
    # ========================================================

    if text == "📌 Loyihalar":
        await projects_handler(message)
        return

    if text == "🗳 Ovoz berish":
        await vote_start(message)
        return

    if text == "📢 Isbot kanali":
        await proof_channel_handler(message, state)
        return

    if text == "💰 Balans":
        await balance_handler(message)
        return

    if text == "💳 Pul yechish":
        await withdraw_start(message, state)
        return

    if text == "👥 Do‘stlarni taklif qilish":
        await referral_handler(message)
        return

    if text == "❓ Savol-javob":
        await question_start(message, state)
        return

    if text == "👨‍💻 Admin bilan bog‘lanish":
        await admin_contact_handler(message)
        return


# ============================================================
# LOYIHALAR
# ============================================================

async def projects_handler(message: Message):

    with closing(db()) as c:

        rows = c.execute("""
            SELECT id, name, url
            FROM projects
            WHERE active=1
            ORDER BY id DESC
        """).fetchall()

    if not rows:

        await message.answer(
            "📌 <b>Hozircha loyiha yo‘q.</b>",
            reply_markup=(
                admin_kb()
                if is_admin(message.from_user.id)
                else user_kb()
            ),
        )
        return

    if is_admin(message.from_user.id):

        text = "📌 <b>LOYIHALAR</b>\n\n"

        for row in rows:

            text += (
                f"🆔 {row['id']}\n"
                f"📌 {escape(row['name'])}\n"
                f"🔗 {escape(row['url'] or '-')}\n"
                "────────────\n"
            )

        await message.answer(
            text,
            reply_markup=admin_kb(),
        )
        return

    text = "📌 <b>Loyihalar</b>\n\n"

    buttons = []

    for row in rows:

        text += (
            f"🔹 <b>{escape(row['name'])}</b>\n\n"
        )

        if row["url"]:

            buttons.append([
                InlineKeyboardButton(
                    text=row["name"][:50],
                    url=row["url"],
                )
            ])

    keyboard = (
        InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
        if buttons
        else None
    )

    await message.answer(
        text,
        reply_markup=keyboard,
    )


# ============================================================
# OVOZ BERISH
# ============================================================

async def vote_start(message: Message):

    await message.answer(
        "🗳 <b>Ovoz berish usulini tanlang:</b>",
        reply_markup=vote_kb(),
    )


@dp.callback_query(F.data == "vote_link")
async def vote_link_callback(
    callback: CallbackQuery,
):

    url = setting("vote_url")

    if not url:

        await callback.message.answer(
            "❌ Hozircha ovoz berish havolasi "
            "admin tomonidan qo‘shilmagan."
        )

    else:

        await callback.message.answer(
            "🔗 <b>Ovoz berish havolasi:</b>",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🔗 Ovoz berish",
                            url=url,
                        )
                    ]
                ]
            ),
        )

    await safe_answer_callback(callback)


@dp.callback_query(F.data == "vote_phone")
async def vote_phone_callback(
    callback: CallbackQuery,
    state: FSMContext,
):

    await state.clear()
    await state.set_state(UserStates.phone)

    await callback.message.answer(
        "📱 <b>Telefon raqamingizni yuboring.</b>\n\n"
        "Masalan:\n"
        "<code>+998901234567</code>"
    )

    await safe_answer_callback(callback)


# ============================================================
# TELEFON STATE
# ============================================================

@dp.message(
    UserStates.phone,
    ~F.text.in_(ALL_MENU_TEXTS),
)
async def phone_received(
    message: Message,
    state: FSMContext,
):

    phone = normalize_phone(
        message.text
    )

    if not valid_phone(phone):

        await message.answer(
            "❌ Telefon raqami noto‘g‘ri.\n\n"
            "Masalan:\n"
            "<code>+998901234567</code>"
        )
        return

    vote_id = None

    async with db_write_lock:

        with closing(db()) as c:

            c.execute("BEGIN IMMEDIATE")

            used = c.execute(
                "SELECT phone FROM used_phones WHERE phone=?",
                (phone,),
            ).fetchone()

            if used:

                c.rollback()

                await state.clear()

                await message.answer(
                    "❌ Bu telefon raqami avval ishlatilgan.",
                    reply_markup=user_kb(),
                )
                return

            pending = c.execute("""
                SELECT id
                FROM votes
                WHERE user_id=?
                  AND phone=?
                  AND status='pending'
                LIMIT 1
            """, (
                message.from_user.id,
                phone,
            )).fetchone()

            if pending:

                c.rollback()

                await state.clear()

                await message.answer(
                    "⏳ Bu telefon raqami bo‘yicha ovozingiz "
                    "allaqachon tekshirilmoqda.",
                    reply_markup=user_kb(),
                )
                return

            c.execute("""
                INSERT INTO votes(
                    user_id,
                    vote_type,
                    phone,
                    status,
                    reward
                )
                VALUES(?,?,?,?,?)
            """, (
                message.from_user.id,
                "phone",
                phone,
                "pending",
                VOTE_REWARD,
            ))

            vote_id = c.execute(
                "SELECT last_insert_rowid()"
            ).fetchone()[0]

            c.commit()

    await state.clear()

    await message.answer(
        "✅ <b>Telefon raqamingiz qabul qilindi.</b>\n\n"
        "Admin tekshirganidan keyin tasdiqlanadi.\n"
        f"✅ Tasdiqlansa <b>{money(VOTE_REWARD)} so‘m</b> "
        "balansingizga qo‘shiladi.",
        reply_markup=user_kb(),
    )

    user = message.from_user

    admin_text = (
        "📱 <b>YANGI TELEFON OVOZI</b>\n\n"
        f"👤 Ism: {escape(user.first_name or '')}\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"👤 Username: @{escape(user.username or 'yo‘q')}\n"
        f"📞 Telefon: <code>{escape(phone)}</code>\n"
        f"💰 Mukofot: {money(VOTE_REWARD)} so‘m\n"
        f"🆔 Ovoz ID: <code>{vote_id}</code>"
    )

    for admin_id in ADMIN_IDS:

        await safe_send_message(
            admin_id,
            admin_text,
            reply_markup=vote_admin_kb(vote_id),
        )


# ============================================================
# OVOZ TASDIQLASH
# ============================================================

@dp.callback_query(F.data.startswith("va:"))
async def vote_approve(
    callback: CallbackQuery,
):

    if not is_admin(callback.from_user.id):

        await safe_answer_callback(
            callback,
            "Ruxsat yo‘q!",
            True,
        )
        return

    try:
        vote_id = int(
            callback.data.split(":")[1]
        )
    except (ValueError, IndexError):

        await safe_answer_callback(
            callback,
            "Noto‘g‘ri ovoz ID.",
            True,
        )
        return

    user_id = None
    reward = 0

    async with db_write_lock:

        with closing(db()) as c:

            c.execute("BEGIN IMMEDIATE")

            vote = c.execute(
                "SELECT * FROM votes WHERE id=?",
                (vote_id,),
            ).fetchone()

            if not vote:

                c.rollback()

                await safe_answer_callback(
                    callback,
                    "Ovoz topilmadi.",
                    True,
                )
                return

            if vote["status"] != "pending":

                c.rollback()

                await safe_answer_callback(
                    callback,
                    "Bu ovoz allaqachon ko‘rib chiqilgan.",
                    True,
                )
                return

            user_id = vote["user_id"]
            reward = vote["reward"]

            # Faqat telefon ovozida telefon tekshiriladi.
            if vote["vote_type"] == "phone":

                used = c.execute(
                    "SELECT phone FROM used_phones WHERE phone=?",
                    (vote["phone"],),
                ).fetchone()

                if used:

                    c.execute("""
                        UPDATE votes
                        SET status='rejected'
                        WHERE id=?
                    """, (vote_id,))

                    c.commit()

                    await callback.message.edit_reply_markup(
                        reply_markup=None
                    )

                    await safe_answer_callback(
                        callback,
                        "Bu raqam oldin ishlatilgan.",
                        True,
                    )
                    return

                try:

                    c.execute("""
                        INSERT INTO used_phones(
                            phone,
                            user_id,
                            vote_id
                        )
                        VALUES(?,?,?)
                    """, (
                        vote["phone"],
                        user_id,
                        vote_id,
                    ))

                except sqlite3.IntegrityError:

                    c.execute("""
                        UPDATE votes
                        SET status='rejected'
                        WHERE id=?
                    """, (vote_id,))

                    c.commit()

                    await callback.message.edit_reply_markup(
                        reply_markup=None
                    )

                    await safe_answer_callback(
                        callback,
                        "Telefon raqami allaqachon ishlatilgan.",
                        True,
                    )
                    return

            c.execute("""
                UPDATE votes
                SET status='approved'
                WHERE id=?
                  AND status='pending'
            """, (vote_id,))

            if c.execute(
                "SELECT changes()"
            ).fetchone()[0] != 1:

                c.rollback()

                await safe_answer_callback(
                    callback,
                    "Ovoz boshqa admin tomonidan ko‘rib chiqildi.",
                    True,
                )
                return

            c.execute("""
                UPDATE users
                SET balance=balance+?
                WHERE user_id=?
            """, (
                reward,
                user_id,
            ))

            c.commit()

    await callback.message.edit_reply_markup(
        reply_markup=None
    )

    await safe_send_message(
        user_id,
        "🎉 <b>Ovozingiz tasdiqlandi!</b>\n\n"
        f"💰 Balansingizga "
        f"<b>+{money(reward)} so‘m</b> qo‘shildi.",
    )

    await safe_answer_callback(
        callback,
        "Ovoz tasdiqlandi!",
    )


# ============================================================
# OVOZ RAD ETISH
# ============================================================

@dp.callback_query(F.data.startswith("vr:"))
async def vote_reject(
    callback: CallbackQuery,
):

    if not is_admin(callback.from_user.id):

        await safe_answer_callback(
            callback,
            "Ruxsat yo‘q!",
            True,
        )
        return

    try:
        vote_id = int(
            callback.data.split(":")[1]
        )
    except (ValueError, IndexError):

        await safe_answer_callback(
            callback,
            "Noto‘g‘ri ovoz ID.",
            True,
        )
        return

    user_id = None

    async with db_write_lock:

        with closing(db()) as c:

            c.execute("BEGIN IMMEDIATE")

            vote = c.execute(
                "SELECT * FROM votes WHERE id=?",
                (vote_id,),
            ).fetchone()

            if not vote:

                c.rollback()

                await safe_answer_callback(
                    callback,
                    "Ovoz topilmadi.",
                    True,
                )
                return

            if vote["status"] != "pending":

                c.rollback()

                await safe_answer_callback(
                    callback,
                    "Bu ovoz allaqachon ko‘rib chiqilgan.",
                    True,
                )
                return

            user_id = vote["user_id"]

            c.execute("""
                UPDATE votes
                SET status='rejected'
                WHERE id=?
                  AND status='pending'
            """, (vote_id,))

            c.commit()

    await callback.message.edit_reply_markup(
        reply_markup=None
    )

    await safe_send_message(
        user_id,
        "❌ <b>Ovozingiz tasdiqlanmadi.</b>\n\n"
        "Qo‘shimcha ma’lumot uchun admin bilan "
        "bog‘lanishingiz mumkin.",
    )

    await safe_answer_callback(
        callback,
        "Ovoz rad etildi.",
    )


# ============================================================
# BALANS
# ============================================================

async def balance_handler(message: Message):

    user = user_row(
        message.from_user.id
    )

    balance = (
        user["balance"]
        if user
        else 0
    )

    await message.answer(
        "💰 <b>SIZNING BALANSINGIZ</b>\n\n"
        f"💵 Balans: <b>{money(balance)} so‘m</b>\n\n"
        f"💳 <b>Pul yechish uchun kamida "
        f"{money(MIN_WITHDRAW)} so‘m kerak.</b>\n\n"
        f"🗳 Har bir tasdiqlangan ovoz: "
        f"<b>{money(VOTE_REWARD)} so‘m</b>.\n"
        f"👥 Har bir haqiqiy referral: "
        f"<b>{money(REFERRAL_REWARD)} so‘m</b>.",
    )


# ============================================================
# REFERRAL
# ============================================================

async def referral_handler(message: Message):

    try:
        me = await bot.get_me()
    except Exception:

        await message.answer(
            "❌ Taklif havolasini yaratib bo‘lmadi. "
            "Birozdan keyin qayta urinib ko‘ring."
        )
        return

    if not me.username:

        await message.answer(
            "❌ Bot username'i aniqlanmadi."
        )
        return

    link = (
        f"https://t.me/{me.username}"
        f"?start=ref_{message.from_user.id}"
    )

    user = user_row(
        message.from_user.id
    )

    referrals = (
        user["referrals"]
        if user
        else 0
    )

    share_url = (
        "https://t.me/share/url"
        "?url="
        + quote(link, safe="")
        + "&text="
        + quote(
            "Do‘stimning botiga qo‘shiling!",
            safe=""
        )
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📨 Do‘stlarni tanlash",
                    url=share_url,
                )
            ]
        ]
    )

    await message.answer(
        "👥 <b>DO‘STLARNI TAKLIF QILISH</b>\n\n"
        "📨 <b>Do‘stlarni tanlash</b> tugmasini bosing.\n"
        "Telegram ulashish oynasini ochadi.\n\n"
        f"🔗 Sizning taklif havolangiz:\n"
        f"<code>{escape(link)}</code>\n\n"
        f"👥 Taklif qilinganlar: <b>{referrals}</b>\n"
        f"💰 Har bir haqiqiy do‘st uchun "
        f"<b>{money(REFERRAL_REWARD)} so‘m</b>.",
        reply_markup=keyboard,
    )


# ============================================================
# PUL YECHISH
# ============================================================

async def withdraw_start(
    message: Message,
    state: FSMContext,
):

    user = user_row(
        message.from_user.id
    )

    balance = (
        user["balance"]
        if user
        else 0
    )

    if balance < MIN_WITHDRAW:

        await message.answer(
            "❌ <b>Hozirgi balansingizda yetarli mablag‘ yo‘q.</b>\n\n"
            f"Pul yechish uchun kamida "
            f"<b>{money(MIN_WITHDRAW)} so‘m</b> kerak."
        )
        return

    with closing(db()) as c:

        pending = c.execute("""
            SELECT id
            FROM withdrawals
            WHERE user_id=?
              AND status='pending'
            LIMIT 1
        """, (
            message.from_user.id,
        )).fetchone()

    if pending:

        await message.answer(
            "⏳ Sizda allaqachon kutilayotgan "
            "pul yechish arizasi mavjud."
        )
        return

    await state.clear()
    await state.set_state(UserStates.card)

    await message.answer(
        "💳 <b>Karta raqamingizni yuboring.</b>\n\n"
        "Masalan:\n"
        "<code>8600123456789012</code>"
    )


@dp.message(
    UserStates.card,
    ~F.text.in_(ALL_MENU_TEXTS),
)
async def card_received(
    message: Message,
    state: FSMContext,
):

    card = re.sub(
        r"\D",
        "",
        message.text or "",
    )

    if not 12 <= len(card) <= 19:

        await message.answer(
            "❌ Karta raqami noto‘g‘ri.\n"
            "Qaytadan yuboring."
        )
        return

    amount = 0
    withdrawal_id = None

    async with db_write_lock:

        with closing(db()) as c:

            c.execute("BEGIN IMMEDIATE")

            user = c.execute(
                "SELECT balance FROM users WHERE user_id=?",
                (message.from_user.id,),
            ).fetchone()

            if not user or user["balance"] < MIN_WITHDRAW:

                c.rollback()

                await state.clear()

                await message.answer(
                    "❌ Balansingiz yetarli emas.",
                    reply_markup=user_kb(),
                )
                return

            pending = c.execute("""
                SELECT id
                FROM withdrawals
                WHERE user_id=?
                  AND status='pending'
                LIMIT 1
            """, (
                message.from_user.id,
            )).fetchone()

            if pending:

                c.rollback()

                await state.clear()

                await message.answer(
                    "⏳ Sizda allaqachon kutilayotgan "
                    "pul yechish arizasi mavjud.",
                    reply_markup=user_kb(),
                )
                return

            amount = user["balance"]

            c.execute("""
                INSERT INTO withdrawals(
                    user_id,
                    amount,
                    card_number,
                    status
                )
                VALUES(?,?,?,'pending')
            """, (
                message.from_user.id,
                amount,
                card,
            ))

            withdrawal_id = c.execute(
                "SELECT last_insert_rowid()"
            ).fetchone()[0]

            c.commit()

    await state.clear()

    await message.answer(
        "✅ <b>Pul yechish arizangiz qabul qilindi.</b>\n\n"
        f"💰 Summa: <b>{money(amount)} so‘m</b>\n"
        f"💳 Karta: <code>{card}</code>\n\n"
        "Admin arizani tekshiradi.",
        reply_markup=user_kb(),
    )

    admin_text = (
        "💳 <b>YANGI PUL YECHISH ARIZASI</b>\n\n"
        f"👤 Ism: {escape(message.from_user.first_name or '')}\n"
        f"🆔 ID: <code>{message.from_user.id}</code>\n"
        f"👤 Username: @{escape(message.from_user.username or 'yo‘q')}\n"
        f"💰 Summa: <b>{money(amount)} so‘m</b>\n"
        f"💳 Karta: <code>{card}</code>\n"
        f"🆔 Ariza: <code>{withdrawal_id}</code>"
    )

    for admin_id in ADMIN_IDS:

        await safe_send_message(
            admin_id,
            admin_text,
            reply_markup=withdraw_kb(
                withdrawal_id
            ),
        )


# ============================================================
# SAVOL-JAVOB
# ============================================================

async def question_start(
    message: Message,
    state: FSMContext,
):

    await state.clear()
    await state.set_state(
        UserStates.question
    )

    await message.answer(
        "❓ <b>Savolingizni yozing.</b>\n\n"
        "Savolingiz adminlarga yuboriladi."
    )


async def send_to_admins_for_chat(
    message: Message,
    text: str,
):

    user = message.from_user

    async with db_write_lock:

        with closing(db()) as c:

            c.execute("BEGIN IMMEDIATE")

            c.execute("""
                INSERT INTO messages(
                    user_id,
                    direction,
                    text
                )
                VALUES(?,?,?)
            """, (
                user.id,
                "user_to_admin",
                text,
            ))

            c.execute("""
                INSERT INTO chats(
                    user_id,
                    status
                )
                VALUES(?, 'open')
                ON CONFLICT(user_id)
                DO UPDATE SET
                    status='open'
            """, (
                user.id,
            ))

            c.commit()

    admin_text = (
        "💬 <b>FOYDALANUVCHIDAN XABAR</b>\n\n"
        f"👤 Ism: {escape(user.first_name or '')}\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"👤 Username: @{escape(user.username or 'yo‘q')}\n\n"
        f"💬 {escape(text)}"
    )

    for admin_id in ADMIN_IDS:

        await safe_send_message(
            admin_id,
            admin_text,
            reply_markup=chat_kb(user.id),
        )


@dp.message(
    UserStates.question,
    ~F.text.in_(ALL_MENU_TEXTS),
)
async def question_received(
    message: Message,
    state: FSMContext,
):

    text = (
        message.text or ""
    ).strip()

    if not text:

        await message.answer(
            "❌ Savol matnini yuboring."
        )
        return

    await state.clear()

    await send_to_admins_for_chat(
        message,
        text,
    )

    await message.answer(
        "✅ <b>Savolingiz adminga yuborildi.</b>\n\n"
        "Admin javobi shu yerga keladi.",
        reply_markup=user_kb(),
    )


# ============================================================
# ADMIN REPLY
# ============================================================

@dp.callback_query(F.data.startswith("reply:"))
async def reply_start(
    callback: CallbackQuery,
    state: FSMContext,
):

    if not is_admin(callback.from_user.id):

        await safe_answer_callback(
            callback,
            "Ruxsat yo‘q!",
            True,
        )
        return

    try:
        user_id = int(
            callback.data.split(":")[1]
        )
    except (ValueError, IndexError):

        await safe_answer_callback(
            callback,
            "Noto‘g‘ri User ID.",
            True,
        )
        return

    await state.clear()

    await state.update_data(
        reply_user_id=user_id
    )

    await state.set_state(
        AdminStates.reply
    )

    await callback.message.answer(
        "💬 <b>Foydalanuvchiga javob yozing.</b>\n\n"
        f"🆔 User ID: <code>{user_id}</code>"
    )

    await safe_answer_callback(callback)


@dp.message(
    AdminStates.reply,
    ~F.text.in_(ALL_MENU_TEXTS),
)
async def admin_reply(
    message: Message,
    state: FSMContext,
):

    if not is_admin(message.from_user.id):

        await state.clear()
        return

    data = await state.get_data()

    user_id = data.get(
        "reply_user_id"
    )

    text = (
        message.text or ""
    ).strip()

    if not user_id:

        await state.clear()
        return

    if not text:

        await message.answer(
            "❌ Javob matnini yozing."
        )
        return

    sent = await safe_send_message(
        user_id,
        "👨‍💻 <b>Admin javobi:</b>\n\n"
        f"{escape(text)}",
    )

    if sent:

        async with db_write_lock:

            with closing(db()) as c:

                c.execute("BEGIN IMMEDIATE")

                c.execute("""
                    INSERT INTO messages(
                        user_id,
                        admin_id,
                        direction,
                        text
                    )
                    VALUES(?,?,?,?)
                """, (
                    user_id,
                    message.from_user.id,
                    "admin_to_user",
                    text,
                ))

                c.execute("""
                    INSERT INTO chats(
                        user_id,
                        status,
                        admin_id
                    )
                    VALUES(?, 'open', ?)
                    ON CONFLICT(user_id)
                    DO UPDATE SET
                        status='open',
                        admin_id=excluded.admin_id
                """, (
                    user_id,
                    message.from_user.id,
                ))

                c.commit()

        await message.answer(
            "✅ <b>Javob foydalanuvchiga yuborildi.</b>",
            reply_markup=admin_kb(),
        )

    else:

        await message.answer(
            "❌ Foydalanuvchiga xabar yuborilmadi."
        )

    await state.clear()


# ============================================================
# SUHBATNI YOPISH
# ============================================================

@dp.callback_query(F.data.startswith("close:"))
async def close_chat(
    callback: CallbackQuery,
):

    if not is_admin(callback.from_user.id):

        await safe_answer_callback(
            callback,
            "Ruxsat yo‘q!",
            True,
        )
        return

    try:
        user_id = int(
            callback.data.split(":")[1]
        )
    except (ValueError, IndexError):

        await safe_answer_callback(
            callback,
            "Noto‘g‘ri User ID.",
            True,
        )
        return

    async with db_write_lock:

        with closing(db()) as c:

            c.execute("""
                UPDATE chats
                SET status='closed',
                    admin_id=?
                WHERE user_id=?
            """, (
                callback.from_user.id,
                user_id,
            ))

            c.commit()

    await safe_send_message(
        user_id,
        "🔒 <b>Admin suhbatni yopdi.</b>\n\n"
        "Yangi savol bo‘lsa, "
        "❓ Savol-javob bo‘limidan foydalaning."
    )

    await callback.message.answer(
        "🔒 <b>Suhbat yopildi.</b>"
    )

    await safe_answer_callback(
        callback,
        "Yopildi"
    )


# ============================================================
# ISBOT KANALI
# ============================================================

async def proof_channel_handler(
    message: Message,
    state: FSMContext,
):

    if is_admin(message.from_user.id):

        await state.clear()

        await state.set_state(
            AdminStates.proof_channel
        )

        current = setting(
            "proof_channel",
            "Hali qo‘shilmagan",
        )

        await message.answer(
            "📢 <b>ISBOT KANALINI SOZLASH</b>\n\n"
            "Telegram kanal havolasini yuboring.\n\n"
            "Masalan:\n"
            "<code>https://t.me/kanal_nomi</code>\n\n"
            f"📌 Hozirgi havola:\n"
            f"{escape(current)}"
        )
        return

    url = setting(
        "proof_channel"
    )

    if not url:

        await message.answer(
            "❌ <b>Isbot kanali hali admin tomonidan qo‘shilmagan.</b>",
            reply_markup=user_kb(),
        )
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 Isbot kanaliga kirish",
                    url=url,
                )
            ]
        ]
    )

    await message.answer(
        "📢 <b>ISBOT KANALI</b>\n\n"
        "Ovozlar va tasdiqlangan ma’lumotlarni "
        "isbot kanalimizdan ko‘rishingiz mumkin.",
        reply_markup=keyboard,
    )


@dp.message(
    AdminStates.proof_channel,
    ~F.text.in_(ALL_MENU_TEXTS),
)
async def proof_channel_save(
    message: Message,
    state: FSMContext,
):

    if not is_admin(message.from_user.id):

        await state.clear()
        return

    url = (
        message.text or ""
    ).strip()

    if not valid_url(url):

        await message.answer(
            "❌ Havola noto‘g‘ri.\n\n"
            "Masalan:\n"
            "<code>https://t.me/kanal_nomi</code>"
        )
        return

    await set_setting_async(
        "proof_channel",
        url,
    )

    await state.clear()

    await message.answer(
        "✅ <b>Isbot kanali muvaffaqiyatli saqlandi.</b>\n\n"
        f"📢 {escape(url)}",
        reply_markup=admin_kb(),
    )


# ============================================================
# ADMIN OVOZ HAVOLASI
# ============================================================

async def vote_url_start(
    message: Message,
    state: FSMContext,
):

    await state.clear()

    await state.set_state(
        AdminStates.vote_url
    )

    await message.answer(
        "🔗 <b>Yangi ovoz havolasini yuboring.</b>\n\n"
        f"Hozirgi havola:\n"
        f"{escape(setting('vote_url', 'Hali qo‘shilmagan'))}"
    )


@dp.message(
    AdminStates.vote_url,
    ~F.text.in_(ALL_MENU_TEXTS),
)
async def vote_url_save(
    message: Message,
    state: FSMContext,
):

    if not is_admin(message.from_user.id):

        await state.clear()
        return

    url = (
        message.text or ""
    ).strip()

    if not valid_url(url):

        await message.answer(
            "❌ Havola http:// yoki https:// "
            "bilan boshlanishi kerak."
        )
        return

    await set_setting_async(
        "vote_url",
        url,
    )

    await state.clear()

    await message.answer(
        "✅ <b>Ovoz havolasi saqlandi.</b>",
        reply_markup=admin_kb(),
    )


# ============================================================
# ADMIN KONTAKT
# ============================================================

async def admin_contact_handler(
    message: Message,
):

    contact = setting(
        "admin_contact"
    )

    if contact:

        await message.answer(
            "👨‍💻 <b>Admin bilan bog‘lanish:</b>\n\n"
            f"{escape(contact)}"
        )

    else:

        await message.answer(
            "ℹ️ <b>Hozircha admin qo‘shilmagan.</b>"
        )


async def contact_start(
    message: Message,
    state: FSMContext,
):

    await state.clear()

    await state.set_state(
        AdminStates.contact
    )

    await message.answer(
        "👨‍💻 <b>Admin Telegram username yoki "
        "telefon raqamini yuboring.</b>\n\n"
        f"Hozirgi:\n"
        f"{escape(setting('admin_contact', 'Hali qo‘shilmagan'))}"
    )


@dp.message(
    AdminStates.contact,
    ~F.text.in_(ALL_MENU_TEXTS),
)
async def contact_save(
    message: Message,
    state: FSMContext,
):

    if not is_admin(message.from_user.id):

        await state.clear()
        return

    contact = (
        message.text or ""
    ).strip()

    if not contact:

        await message.answer(
            "❌ Kontaktni yozing."
        )
        return

    await set_setting_async(
        "admin_contact",
        contact,
    )

    await state.clear()

    await message.answer(
        "✅ <b>Admin kontakti saqlandi.</b>",
        reply_markup=admin_kb(),
    )


# ============================================================
# ADMIN LOYIHA QO‘SHISH
# ============================================================

async def project_start(
    message: Message,
    state: FSMContext,
):

    await state.clear()

    await state.set_state(
        AdminStates.project_name
    )

    await message.answer(
        "➕ <b>Loyiha nomini yozing.</b>"
    )


@dp.message(
    AdminStates.project_name,
    ~F.text.in_(ALL_MENU_TEXTS),
)
async def project_name_received(
    message: Message,
    state: FSMContext,
):

    if not is_admin(message.from_user.id):

        await state.clear()
        return

    name = (
        message.text or ""
    ).strip()

    if not name:

        await message.answer(
            "❌ Loyiha nomini yozing."
        )
        return

    await state.update_data(
        project_name=name
    )

    await state.set_state(
        AdminStates.project_url
    )

    await message.answer(
        "🔗 <b>Endi loyiha havolasini yuboring.</b>\n\n"
        "Masalan:\n"
        "<code>https://example.com</code>"
    )


@dp.message(
    AdminStates.project_url,
    ~F.text.in_(ALL_MENU_TEXTS),
)
async def project_url_received(
    message: Message,
    state: FSMContext,
):

    if not is_admin(message.from_user.id):

        await state.clear()
        return

    url = (
        message.text or ""
    ).strip()

    if not valid_url(url):

        await message.answer(
            "❌ Havola http:// yoki https:// "
            "bilan boshlanishi kerak."
        )
        return

    data = await state.get_data()

    name = data.get(
        "project_name"
    )

    if not name:

        await state.clear()

        await message.answer(
            "❌ Loyiha ma’lumoti topilmadi.",
            reply_markup=admin_kb(),
        )
        return

    async with db_write_lock:

        with closing(db()) as c:

            c.execute("BEGIN IMMEDIATE")

            c.execute("""
                INSERT INTO projects(
                    name,
                    url,
                    active
                )
                VALUES(?,?,1)
            """, (
                name,
                url,
            ))

            c.commit()

    await state.clear()

    await message.answer(
        "✅ <b>Loyiha muvaffaqiyatli qo‘shildi.</b>\n\n"
        f"📌 {escape(name)}\n"
        f"🔗 {escape(url)}",
        reply_markup=admin_kb(),
    )


# ============================================================
# ADMIN REKLAMA
# ============================================================

async def broadcast_start(
    message: Message,
    state: FSMContext,
):

    if not is_admin(message.from_user.id):
        return

    if broadcast_lock.locked():

        await message.answer(
            "⏳ Hozir boshqa reklama yuborilmoqda."
        )
        return

    await state.clear()

    await state.set_state(
        AdminStates.broadcast
    )

    await message.answer(
        "📢 <b>Yuboriladigan xabarni yozing.</b>"
    )


async def broadcast_worker(
    queue,
    counters,
):

    while True:

        try:
            user_id = queue.get_nowait()
        except asyncio.QueueEmpty:
            return

        try:

            result = await safe_send_message(
                user_id,
                counters["text"],
            )

            if result:
                counters["sent"] += 1
            else:
                counters["failed"] += 1

        except Exception:

            counters["failed"] += 1

        finally:

            queue.task_done()

            await asyncio.sleep(
                BROADCAST_DELAY
            )


async def broadcast_finish_notification(
    admin_id,
    user_ids,
    text,
):

    async with broadcast_lock:

        queue = asyncio.Queue()

        for user_id in user_ids:
            await queue.put(user_id)

        counters = {
            "text": text,
            "sent": 0,
            "failed": 0,
        }

        workers = []

        worker_count = min(
            BROADCAST_WORKERS,
            max(len(user_ids), 1),
        )

        for _ in range(worker_count):

            workers.append(
                asyncio.create_task(
                    broadcast_worker(
                        queue,
                        counters,
                    )
                )
            )

        await queue.join()

        for worker in workers:
            worker.cancel()

        await safe_send_message(
            admin_id,
            "📢 <b>Reklama yakunlandi.</b>\n\n"
            f"👥 Jami: <b>{len(user_ids)}</b>\n"
            f"✅ Yuborildi: <b>{counters['sent']}</b>\n"
            f"❌ Yuborilmadi: <b>{counters['failed']}</b>",
            reply_markup=admin_kb(),
        )


@dp.message(
    AdminStates.broadcast,
    ~F.text.in_(ALL_MENU_TEXTS),
)
async def broadcast_received(
    message: Message,
    state: FSMContext,
):

    if not is_admin(message.from_user.id):

        await state.clear()
        return

    text = (
        message.text or ""
    ).strip()

    if not text:

        await message.answer(
            "❌ Xabar matnini yuboring."
        )
        return

    await state.clear()

    with closing(db()) as c:

        rows = c.execute(
            "SELECT user_id FROM users"
        ).fetchall()

    user_ids = [
        row["user_id"]
        for row in rows
    ]

    await message.answer(
        "📢 <b>Reklama yuborish boshlandi.</b>\n\n"
        f"👥 Qabul qiluvchilar: <b>{len(user_ids)}</b>\n\n"
        "Bot boshqa funksiyalarni ham ishlatishda davom etadi."
    )

    asyncio.create_task(
        broadcast_finish_notification(
            message.from_user.id,
            user_ids,
            text,
        )
    )


# ============================================================
# ADMIN STATISTIKA
# ============================================================

async def statistics(message: Message):

    if not is_admin(message.from_user.id):
        return

    with closing(db()) as c:

        users = c.execute(
            "SELECT COUNT(*) AS n FROM users"
        ).fetchone()["n"]

        votes = c.execute(
            "SELECT COUNT(*) AS n FROM votes"
        ).fetchone()["n"]

        approved = c.execute("""
            SELECT COUNT(*) AS n
            FROM votes
            WHERE status='approved'
        """).fetchone()["n"]

        pending = c.execute("""
            SELECT COUNT(*) AS n
            FROM votes
            WHERE status='pending'
        """).fetchone()["n"]

        rejected = c.execute("""
            SELECT COUNT(*) AS n
            FROM votes
            WHERE status='rejected'
        """).fetchone()["n"]

        phone_votes = c.execute("""
            SELECT COUNT(*) AS n
            FROM votes
            WHERE vote_type='phone'
        """).fetchone()["n"]

        link_votes = c.execute("""
            SELECT COUNT(*) AS n
            FROM votes
            WHERE vote_type='link'
        """).fetchone()["n"]

        referrals = c.execute(
            "SELECT COUNT(*) AS n FROM referrals"
        ).fetchone()["n"]

        referral_money = c.execute("""
            SELECT COALESCE(SUM(reward),0) AS n
            FROM referrals
        """).fetchone()["n"]

        total_balance = c.execute("""
            SELECT COALESCE(SUM(balance),0) AS n
            FROM users
        """).fetchone()["n"]

        pending_withdrawals = c.execute("""
            SELECT COUNT(*) AS n
            FROM withdrawals
            WHERE status='pending'
        """).fetchone()["n"]

        paid_money = c.execute("""
            SELECT COALESCE(SUM(amount),0) AS n
            FROM withdrawals
            WHERE status='paid'
        """).fetchone()["n"]

    await message.answer(
        "📊 <b>BOT STATISTIKASI</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{users}</b>\n\n"
        f"🗳 Jami ovozlar: <b>{votes}</b>\n"
        f"📱 Telefon ovozlari: <b>{phone_votes}</b>\n"
        f"🔗 Link ovozlari: <b>{link_votes}</b>\n"
        f"✅ Tasdiqlangan: <b>{approved}</b>\n"
        f"⏳ Kutilayotgan: <b>{pending}</b>\n"
        f"❌ Rad etilgan: <b>{rejected}</b>\n\n"
        f"👥 Referallar: <b>{referrals}</b>\n"
        f"💰 Referral mukofoti: "
        f"<b>{money(referral_money)} so‘m</b>\n\n"
        f"💵 Foydalanuvchilar balanslari: "
        f"<b>{money(total_balance)} so‘m</b>\n"
        f"💳 Kutilayotgan pul yechishlar: "
        f"<b>{pending_withdrawals}</b>\n"
        f"💸 To‘langan: "
        f"<b>{money(paid_money)} so‘m</b>",
        reply_markup=admin_kb(),
    )


# ============================================================
# ADMIN USERS
# ============================================================

async def admin_users(message: Message):

    if not is_admin(message.from_user.id):
        return

    with closing(db()) as c:

        rows = c.execute("""
            SELECT
                user_id,
                first_name,
                username,
                balance,
                referrals
            FROM users
            ORDER BY rowid DESC
            LIMIT 30
        """).fetchall()

    if not rows:

        await message.answer(
            "👥 Foydalanuvchilar yo‘q.",
            reply_markup=admin_kb(),
        )
        return

    text = "👥 <b>FOYDALANUVCHILAR</b>\n\n"

    for row in rows:

        text += (
            f"👤 {escape(row['first_name'] or '')}\n"
            f"🆔 <code>{row['user_id']}</code>\n"
            f"👤 @{escape(row['username'] or 'yo‘q')}\n"
            f"💰 {money(row['balance'])} so‘m\n"
            f"👥 Referral: {row['referrals']}\n"
            "────────────\n"
        )

    await message.answer(
        text,
        reply_markup=admin_kb(),
    )


# ============================================================
# ADMIN OVOZLAR
# ============================================================

async def admin_votes(message: Message):

    if not is_admin(message.from_user.id):
        return

    with closing(db()) as c:

        rows = c.execute("""
            SELECT
                v.id,
                v.user_id,
                v.vote_type,
                v.phone,
                v.status,
                v.reward,
                u.first_name
            FROM votes v
            LEFT JOIN users u
                ON u.user_id=v.user_id
            ORDER BY v.id DESC
            LIMIT 30
        """).fetchall()

    if not rows:

        await message.answer(
            "🗳 Ovozlar yo‘q.",
            reply_markup=admin_kb(),
        )
        return

    for row in rows:

        keyboard = (
            vote_admin_kb(row["id"])
            if row["status"] == "pending"
            and row["vote_type"] == "phone"
            else None
        )

        await message.answer(
            f"🗳 <b>Ovoz #{row['id']}</b>\n\n"
            f"👤 {escape(row['first_name'] or '')}\n"
            f"🆔 <code>{row['user_id']}</code>\n"
            f"📌 Tur: <b>{escape(row['vote_type'])}</b>\n"
            f"📞 <code>{escape(row['phone'] or '-')}</code>\n"
            f"📊 Holat: <b>{row['status']}</b>\n"
            f"💰 {money(row['reward'])} so‘m",
            reply_markup=keyboard,
        )


# ============================================================
# TELEFON OVOZLARI
# ============================================================

async def admin_phone_votes(message: Message):

    if not is_admin(message.from_user.id):
        return

    with closing(db()) as c:

        rows = c.execute("""
            SELECT
                v.id,
                v.user_id,
                v.phone,
                v.status,
                v.reward,
                u.first_name
            FROM votes v
            LEFT JOIN users u
                ON u.user_id=v.user_id
            WHERE v.vote_type='phone'
            ORDER BY v.id DESC
            LIMIT 30
        """).fetchall()

    if not rows:

        await message.answer(
            "📱 Telefon ovozlari yo‘q.",
            reply_markup=admin_kb(),
        )
        return

    for row in rows:

        keyboard = (
            vote_admin_kb(row["id"])
            if row["status"] == "pending"
            else None
        )

        await message.answer(
            f"📱 <b>Telefon ovozi #{row['id']}</b>\n\n"
            f"👤 {escape(row['first_name'] or '')}\n"
            f"🆔 <code>{row['user_id']}</code>\n"
            f"📞 <code>{escape(row['phone'] or '')}</code>\n"
            f"📊 Holat: <b>{row['status']}</b>\n"
            f"💰 {money(row['reward'])} so‘m",
            reply_markup=keyboard,
        )


# ============================================================
# REFERALLAR
# ============================================================

async def admin_referrals(message: Message):

    if not is_admin(message.from_user.id):
        return

    with closing(db()) as c:

        rows = c.execute("""
            SELECT
                inviter_id,
                invited_id,
                reward
            FROM referrals
            ORDER BY id DESC
            LIMIT 50
        """).fetchall()

    if not rows:

        await message.answer(
            "👥 Referallar yo‘q.",
            reply_markup=admin_kb(),
        )
        return

    text = "👥 <b>REFERALLAR</b>\n\n"

    for row in rows:

        text += (
            f"👤 Taklif qiluvchi: "
            f"<code>{row['inviter_id']}</code>\n"
            f"👤 Taklif qilingan: "
            f"<code>{row['invited_id']}</code>\n"
            f"💰 Mukofot: "
            f"{money(row['reward'])} so‘m\n"
            "────────────\n"
        )

    await message.answer(
        text,
        reply_markup=admin_kb(),
    )


# ============================================================
# PUL YECHISH ARIZALARI
# ============================================================

async def admin_withdrawals(message: Message):

    if not is_admin(message.from_user.id):
        return

    with closing(db()) as c:

        rows = c.execute("""
            SELECT
                w.id,
                w.user_id,
                w.amount,
                w.card_number,
                w.status,
                u.first_name
            FROM withdrawals w
            LEFT JOIN users u
                ON u.user_id=w.user_id
            ORDER BY w.id DESC
            LIMIT 30
        """).fetchall()

    if not rows:

        await message.answer(
            "💳 Pul yechish arizalari yo‘q.",
            reply_markup=admin_kb(),
        )
        return

    for row in rows:

        keyboard = (
            withdraw_kb(row["id"])
            if row["status"] == "pending"
            else None
        )

        await message.answer(
            f"💳 <b>Ariza #{row['id']}</b>\n\n"
            f"👤 {escape(row['first_name'] or '')}\n"
            f"🆔 <code>{row['user_id']}</code>\n"
            f"💰 {money(row['amount'])} so‘m\n"
            f"💳 <code>{row['card_number']}</code>\n"
            f"📊 Holat: <b>{row['status']}</b>",
            reply_markup=keyboard,
        )


# ============================================================
# ADMIN SAVOLLARI
# ============================================================

async def admin_questions(message: Message):

    if not is_admin(message.from_user.id):
        return

    with closing(db()) as c:

        rows = c.execute("""
            SELECT
                m.user_id,
                m.text,
                m.created_at,
                u.first_name
            FROM messages m
            LEFT JOIN users u
                ON u.user_id=m.user_id
            WHERE m.direction='user_to_admin'
            ORDER BY m.id DESC
            LIMIT 30
        """).fetchall()

    if not rows:

        await message.answer(
            "❓ Savollar yo‘q.",
            reply_markup=admin_kb(),
        )
        return

    for row in rows:

        await message.answer(
            "❓ <b>FOYDALANUVCHI SAVOLI</b>\n\n"
            f"👤 {escape(row['first_name'] or '')}\n"
            f"🆔 <code>{row['user_id']}</code>\n\n"
            f"💬 {escape(row['text'])}",
            reply_markup=chat_kb(row["user_id"]),
        )


# ============================================================
# WITHDRAW — PAID
# ============================================================

@dp.callback_query(F.data.startswith("wp:"))
async def withdrawal_paid(
    callback: CallbackQuery,
):

    if not is_admin(callback.from_user.id):

        await safe_answer_callback(
            callback,
            "Ruxsat yo‘q!",
            True,
        )
        return

    try:
        withdrawal_id = int(
            callback.data.split(":")[1]
        )
    except (ValueError, IndexError):

        await safe_answer_callback(
            callback,
            "Noto‘g‘ri ariza ID.",
            True,
        )
        return

    user_id = None
    amount = 0

    async with db_write_lock:

        with closing(db()) as c:

            c.execute("BEGIN IMMEDIATE")

            withdrawal = c.execute(
                "SELECT * FROM withdrawals WHERE id=?",
                (withdrawal_id,),
            ).fetchone()

            if not withdrawal:

                c.rollback()

                await safe_answer_callback(
                    callback,
                    "Ariza topilmadi.",
                    True,
                )
                return

            if withdrawal["status"] != "pending":

                c.rollback()

                await safe_answer_callback(
                    callback,
                    "Bu ariza allaqachon ko‘rib chiqilgan.",
                    True,
                )
                return

            user_id = withdrawal["user_id"]
            amount = withdrawal["amount"]

            # MUHIM:
            # Balans yetarliligini UPDATEning o'zida tekshiramiz.
            # Shu bilan ikki admin bir vaqtda bosganda
            # ikki marta pul yechilmaydi.

            c.execute("""
                UPDATE users
                SET balance=balance-?
                WHERE user_id=?
                  AND balance>=?
            """, (
                amount,
                user_id,
                amount,
            ))

            changed = c.execute(
                "SELECT changes()"
            ).fetchone()[0]

            if changed != 1:

                c.rollback()

                await safe_answer_callback(
                    callback,
                    "Foydalanuvchi balansida mablag‘ yetarli emas.",
                    True,
                )
                return

            c.execute("""
                UPDATE withdrawals
                SET status='paid'
                WHERE id=?
                  AND status='pending'
            """, (
                withdrawal_id,
            ))

            changed = c.execute(
                "SELECT changes()"
            ).fetchone()[0]

            if changed != 1:

                c.rollback()

                await safe_answer_callback(
                    callback,
                    "Ariza boshqa admin tomonidan ko‘rib chiqildi.",
                    True,
                )
                return

            c.commit()

    await callback.message.edit_reply_markup(
        reply_markup=None
    )

    await safe_send_message(
        user_id,
        "✅ <b>Pul yechish arizangiz to‘landi.</b>\n\n"
        f"💰 Summa: <b>{money(amount)} so‘m</b>",
    )

    await safe_answer_callback(
        callback,
        "To‘landi!",
    )


# ============================================================
# WITHDRAW — REJECT
# ============================================================

@dp.callback_query(F.data.startswith("wr:"))
async def withdrawal_reject(
    callback: CallbackQuery,
):

    if not is_admin(callback.from_user.id):

        await safe_answer_callback(
            callback,
            "Ruxsat yo‘q!",
            True,
        )
        return

    try:
        withdrawal_id = int(
            callback.data.split(":")[1]
        )
    except (ValueError, IndexError):

        await safe_answer_callback(
            callback,
            "Noto‘g‘ri ariza ID.",
            True,
        )
        return

    user_id = None

    async with db_write_lock:

        with closing(db()) as c:

            c.execute("BEGIN IMMEDIATE")

            withdrawal = c.execute(
                "SELECT * FROM withdrawals WHERE id=?",
                (withdrawal_id,),
            ).fetchone()

            if not withdrawal:

                c.rollback()

                await safe_answer_callback(
                    callback,
                    "Ariza topilmadi.",
                    True,
                )
                return

            if withdrawal["status"] != "pending":

                c.rollback()

                await safe_answer_callback(
                    callback,
                    "Bu ariza allaqachon ko‘rib chiqilgan.",
                    True,
                )
                return

            user_id = withdrawal["user_id"]

            c.execute("""
                UPDATE withdrawals
                SET status='rejected'
                WHERE id=?
                  AND status='pending'
            """, (
                withdrawal_id,
            ))

            c.commit()

    await callback.message.edit_reply_markup(
        reply_markup=None
    )

    await safe_send_message(
        user_id,
        "❌ <b>Pul yechish arizangiz rad etildi.</b>\n\n"
        "Rad etish sababi bo‘yicha admin bilan bog‘lanishingiz mumkin.",
    )

    await safe_answer_callback(
        callback,
        "Rad etildi.",
    )


# ============================================================
# OCHIQ CHAT
# ============================================================

@dp.message()
async def remaining_messages(
    message: Message,
    state: FSMContext,
):

    if is_admin(message.from_user.id):
        return

    if message.text in ALL_MENU_TEXTS:
        return

    current_state = await state.get_state()

    if current_state:
        return

    with closing(db()) as c:

        chat = c.execute("""
            SELECT status
            FROM chats
            WHERE user_id=?
        """, (
            message.from_user.id,
        )).fetchone()

    if not chat or chat["status"] != "open":
        return

    text = (
        message.text or ""
    ).strip()

    if not text:
        return

    await send_to_admins_for_chat(
        message,
        text,
    )


# ============================================================
# GLOBAL ERROR HANDLER
# ============================================================

@dp.error()
async def global_error_handler(
    event,
):
    logger.exception(
        "BOT HANDLER ERROR: %s",
        event,
    )

    return True


# ============================================================
# POLLING
# ============================================================

async def run_polling_forever():

    while True:

        try:

            logger.info(
                "Telegram polling ishga tushmoqda..."
            )

            await dp.start_polling(
                bot,
                handle_signals=False,
            )

            logger.warning(
                "Polling to‘xtadi. "
                "5 soniyadan keyin qayta ishga tushadi."
            )

        except asyncio.CancelledError:

            logger.info(
                "Polling bekor qilindi."
            )

            raise

        except Exception as exc:

            logger.exception(
                "Polling xatosi: %s",
                exc,
            )

            await asyncio.sleep(5)


# ============================================================
# MAIN
# ============================================================

async def main():

    if (
        not BOT_TOKEN
        or BOT_TOKEN == "BU_YERGA_YANGI_BOT_TOKENNI_QOYING"
    ):

        raise RuntimeError(
            "\n\n"
            "BOT_TOKEN QO‘YILMAGAN!\n\n"
            "main.py ichidagi:\n\n"
            'BOT_TOKEN = "BU_YERGA_YANGI_BOT_TOKENNI_QOYING"\n\n'
            "joyiga BotFather bergan YANGI tokenni qo‘ying.\n"
        )

    if not ADMIN_IDS:

        raise RuntimeError(
            "ADMIN_IDS ichiga haqiqiy Telegram ID qo‘yilmagan!"
        )

    init_db()

    logger.info(
        "SQLite database tayyor."
    )

    try:

        await bot.delete_webhook(
            drop_pending_updates=True
        )

    except Exception as exc:

        logger.warning(
            "Webhook o‘chirishda xato: %s",
            exc,
        )

    logger.info(
        "========================================"
    )

    logger.info(
        "BOT ISHLASHGA TAYYOR"
    )

    logger.info(
        "24/7 polling rejimi ishga tushmoqda"
    )

    logger.info(
        "========================================"
    )

    try:

        await run_polling_forever()

    finally:

        try:
            await bot.session.close()
        except Exception:
            pass


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    try:

        asyncio.run(main())

    except KeyboardInterrupt:

        logger.info(
            "Bot qo‘lda to‘xtatildi."
        )

    except Exception:

        logger.exception(
            "BOT FATAL ERROR"
        )