# ============================================================
# MAIN.PY — TELEGRAM BOT
# Stable SQLite WAL / Referral / Voting / Admin / Q&A
# Railway-ready
# ============================================================

import asyncio
import logging
import os
import re
import sqlite3
from contextlib import closing
from html import escape

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

# ============================================================
# CONFIG
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "8615736731:AAGQ9TR4XdX-y-X1XbRbmM9evTk3iMtL5GU").strip()

ADMIN_IDS = {
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "7998053914").split(",")
    if x.strip().isdigit()
}

DB_NAME = os.getenv("DB_NAME", "bot.db")

VOTE_REWARD = 30000
REFERRAL_REWARD = 10000
MIN_WITHDRAW = 30000

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN topilmadi. Railway -> Variables -> BOT_TOKEN qo'shing."
    )

bot = Bot(
    BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher()


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
# DATABASE
# ============================================================

def db():
    conn = sqlite3.connect(
        DB_NAME,
        timeout=30,
        isolation_level=None,
    )
    conn.row_factory = sqlite3.Row

    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")

    return conn


def init_db():
    with closing(db()) as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT DEFAULT '',
                first_name TEXT DEFAULT '',
                balance INTEGER NOT NULL DEFAULT 0,
                referrals INTEGER NOT NULL DEFAULT 0,
                referred_by INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                url TEXT DEFAULT '',
                active INTEGER NOT NULL DEFAULT 1
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                vote_type TEXT NOT NULL,
                phone TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                reward INTEGER NOT NULL DEFAULT 30000,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS used_phones (
                phone TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                vote_id INTEGER NOT NULL UNIQUE
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                inviter_id INTEGER NOT NULL,
                invited_id INTEGER UNIQUE NOT NULL,
                reward INTEGER NOT NULL DEFAULT 10000,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS withdrawals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                card_number TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                user_id INTEGER PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'closed',
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

        # Indexlar
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_votes_user ON votes(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_votes_status ON votes(status)",
            "CREATE INDEX IF NOT EXISTS idx_votes_type_status ON votes(vote_type, status)",
            "CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_messages_direction ON messages(direction)",
            "CREATE INDEX IF NOT EXISTS idx_withdrawals_user ON withdrawals(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_withdrawals_status ON withdrawals(status)",
            "CREATE INDEX IF NOT EXISTS idx_referrals_inviter ON referrals(inviter_id)",
        ]

        for query in indexes:
            c.execute(query)


# ============================================================
# HELPERS
# ============================================================

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def money(value) -> str:
    return f"{int(value):,}".replace(",", " ")


def setting(key: str, default: str = "") -> str:
    with closing(db()) as c:
        row = c.execute(
            "SELECT value FROM settings WHERE key=?",
            (key,),
        ).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str):
    with closing(db()) as c:
        c.execute("""
            INSERT INTO settings(key, value)
            VALUES(?, ?)
            ON CONFLICT(key)
            DO UPDATE SET value=excluded.value
        """, (key, value))


def add_user(user, referred_by=None) -> bool:
    if referred_by == user.id:
        referred_by = None

    with closing(db()) as c:
        row = c.execute(
            "SELECT user_id FROM users WHERE user_id=?",
            (user.id,),
        ).fetchone()

        if row:
            c.execute("""
                UPDATE users
                SET username=?, first_name=?
                WHERE user_id=?
            """, (
                user.username or "",
                user.first_name or "",
                user.id,
            ))
            return False

        c.execute("""
            INSERT INTO users(
                user_id, username, first_name, referred_by
            )
            VALUES(?,?,?,?)
        """, (
            user.id,
            user.username or "",
            user.first_name or "",
            referred_by,
        ))
        return True


def user_row(user_id: int):
    with closing(db()) as c:
        return c.execute(
            "SELECT * FROM users WHERE user_id=?",
            (user_id,),
        ).fetchone()


def normalize_phone(value: str) -> str:
    value = re.sub(r"[^\d+]", "", value or "")
    if value.startswith("00"):
        value = "+" + value[2:]
    return value


def valid_phone(value: str) -> bool:
    phone = normalize_phone(value)
    digits = phone[1:] if phone.startswith("+") else phone
    return digits.isdigit() and 8 <= len(digits) <= 15


def valid_url(value: str) -> bool:
    return bool(
        re.match(
            r"^https?://[^\s]+$",
            (value or "").strip(),
            re.IGNORECASE,
        )
    )


async def safe_send(user_id: int, text: str, **kwargs) -> bool:
    try:
        await bot.send_message(user_id, text, **kwargs)
        return True
    except Exception as e:
        logger.warning("send_message user=%s error=%s", user_id, e)
        return False


# ============================================================
# KEYBOARDS
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


def vote_admin_kb(vote_id: int, user_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Tasdiqlash",
                    callback_data=f"va:{vote_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Rad etish",
                    callback_data=f"vr:{vote_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="💬 Foydalanuvchiga yozish",
                    callback_data=f"reply:{user_id}",
                )
            ],
        ]
    )


def chat_kb(user_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 Foydalanuvchiga yozish",
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


def user_chat_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 Javob yozish",
                    callback_data="user_reply",
                )
            ]
        ]
    )


def withdraw_kb(withdraw_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ To‘landi",
                    callback_data=f"wp:{withdraw_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Rad etish",
                    callback_data=f"wr:{withdraw_id}",
                )
            ],
        ]
    )


# ============================================================
# START
# ============================================================

@dp.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    await state.clear()

    referred_by = None
    parts = (message.text or "").split(maxsplit=1)

    if len(parts) == 2 and parts[1].startswith("ref_"):
        try:
            referred_by = int(parts[1][4:])
        except ValueError:
            referred_by = None

    is_new = add_user(message.from_user, referred_by)

    if is_new and referred_by and referred_by != message.from_user.id:
        with closing(db()) as c:
            inviter = c.execute(
                "SELECT user_id FROM users WHERE user_id=?",
                (referred_by,),
            ).fetchone()

            already = c.execute(
                "SELECT id FROM referrals WHERE invited_id=?",
                (message.from_user.id,),
            ).fetchone()

            if inviter and not already:
                c.execute("""
                    INSERT INTO referrals(
                        inviter_id, invited_id, reward
                    )
                    VALUES(?,?,?)
                """, (
                    referred_by,
                    message.from_user.id,
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

                await safe_send(
                    referred_by,
                    "🎉 <b>Yangi do‘st taklif qilindi!</b>\n\n"
                    f"💰 Balansingizga "
                    f"<b>+{money(REFERRAL_REWARD)} so‘m</b> qo‘shildi.",
                )

    if is_admin(message.from_user.id):
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


@dp.message(Command("admin"))
async def admin_command(message: Message, state: FSMContext):
    await state.clear()

    if not is_admin(message.from_user.id):
        await message.answer("❌ Siz admin emassiz.")
        return

    await message.answer(
        "👨‍💼 <b>Admin panel</b>",
        reply_markup=admin_kb(),
    )


@dp.message(F.text == "🏠 Foydalanuvchi menyusi")
async def user_menu(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    await state.clear()
    await message.answer(
        "🏠 <b>Foydalanuvchi menyusi</b>",
        reply_markup=user_kb(),
    )


# ============================================================
# PROOF CHANNEL
# ============================================================

@dp.message(F.text == "📢 Isbot kanali")
async def proof_channel_handler(message: Message, state: FSMContext):
    await state.clear()

    if is_admin(message.from_user.id):
        await state.set_state(AdminStates.proof_channel)

        current = setting(
            "proof_channel",
            "Hali qo‘shilmagan",
        )

        await message.answer(
            "📢 <b>ISBOT KANALINI SOZLASH</b>\n\n"
            "Telegram kanal havolasini yuboring.\n\n"
            "Masalan:\n"
            "<code>https://t.me/kanal_nomi</code>\n\n"
            f"📌 Hozirgi havola:\n{escape(current)}",
        )
        return

    url = setting("proof_channel")

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


# ============================================================
# PROJECTS
# ============================================================

@dp.message(F.text == "📌 Loyihalar")
async def projects_handler(message: Message, state: FSMContext):
    await state.clear()

    with closing(db()) as c:
        rows = c.execute("""
            SELECT id, name, url
            FROM projects
            WHERE active=1
            ORDER BY id DESC
        """).fetchall()

    if is_admin(message.from_user.id):
        if not rows:
            await message.answer(
                "📌 Loyihalar mavjud emas.",
                reply_markup=admin_kb(),
            )
            return

        text = "📌 <b>Loyihalar</b>\n\n"
        for row in rows:
            text += (
                f"🆔 {row['id']}\n"
                f"📌 {escape(row['name'])}\n"
                f"🔗 {escape(row['url'] or '-')}\n"
                "────────────\n"
            )

        await message.answer(text, reply_markup=admin_kb())
        return

    if not rows:
        await message.answer(
            "📌 <b>Hozircha loyiha yo‘q.</b>",
            reply_markup=user_kb(),
        )
        return

    text = "📌 <b>Loyihalar</b>\n\n"
    buttons = []

    for row in rows:
        text += f"🔹 <b>{escape(row['name'])}</b>\n\n"

        if row["url"]:
            buttons.append([
                InlineKeyboardButton(
                    text=row["name"],
                    url=row["url"],
                )
            ])

    keyboard = (
        InlineKeyboardMarkup(inline_keyboard=buttons)
        if buttons
        else None
    )

    await message.answer(text, reply_markup=keyboard)


# ============================================================
# USER VOTING
# ============================================================

@dp.message(F.text == "🗳 Ovoz berish")
async def vote_start(message: Message, state: FSMContext):
    await state.clear()

    if is_admin(message.from_user.id):
        return

    await message.answer(
        "🗳 <b>Ovoz berish usulini tanlang:</b>",
        reply_markup=vote_kb(),
    )


@dp.callback_query(F.data == "vote_link")
async def vote_link_callback(
    callback: CallbackQuery,
    state: FSMContext,
):
    if is_admin(callback.from_user.id):
        await callback.answer(
            "Admin uchun mavjud emas.",
            show_alert=True,
        )
        return

    await state.clear()

    vote_url = setting("vote_url")

    if not vote_url:
        await callback.answer()
        await callback.message.answer(
            "❌ <b>Ovoz havolasi hali admin tomonidan qo‘shilmagan.</b>",
            reply_markup=user_kb(),
        )
        return

    with closing(db()) as c:
        pending = c.execute("""
            SELECT id
            FROM votes
            WHERE user_id=?
              AND vote_type='link'
              AND status='pending'
            LIMIT 1
        """, (callback.from_user.id,)).fetchone()

    await callback.answer()

    if pending:
        await callback.message.answer(
            "⏳ Sizda allaqachon tekshirilayotgan ovoz mavjud.\n"
            "Admin tasdiqlashini kuting.",
            reply_markup=user_kb(),
        )
        return

    with closing(db()) as c:
        c.execute("""
            INSERT INTO votes(
                user_id, vote_type, phone, status, reward
            )
            VALUES(?, 'link', '', 'pending', ?)
        """, (
            callback.from_user.id,
            VOTE_REWARD,
        ))

        vote_id = c.execute(
            "SELECT last_insert_rowid()"
        ).fetchone()[0]

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🗳 Ovoz berish",
                    url=vote_url,
                )
            ],
            [
                InlineKeyboardButton(
                    text="✅ Ovoz berdim",
                    callback_data=f"link_done:{vote_id}",
                )
            ],
        ]
    )

    await callback.message.answer(
        "🔗 <b>HAVOLA ORQALI OVOZ BERISH</b>\n\n"
        "1️⃣ «Ovoz berish» tugmasini bosing.\n"
        "2️⃣ Ovoz berishni bajaring.\n"
        "3️⃣ So‘ng «Ovoz berdim» tugmasini bosing.\n\n"
        f"💰 Tasdiqlanganda mukofot: "
        f"<b>{money(VOTE_REWARD)} so‘m</b>.",
        reply_markup=keyboard,
    )


@dp.callback_query(F.data.startswith("link_done:"))
async def link_done_callback(callback: CallbackQuery):
    if is_admin(callback.from_user.id):
        await callback.answer(
            "Admin uchun mavjud emas.",
            show_alert=True,
        )
        return

    try:
        vote_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Xato.", show_alert=True)
        return

    with closing(db()) as c:
        row = c.execute("""
            SELECT id, user_id, status
            FROM votes
            WHERE id=?
              AND vote_type='link'
        """, (vote_id,)).fetchone()

        if not row or row["user_id"] != callback.from_user.id:
            await callback.answer(
                "Bu ovoz sizga tegishli emas.",
                show_alert=True,
            )
            return

        if row["status"] != "pending":
            await callback.answer(
                "Bu ovoz allaqachon ko‘rib chiqilgan.",
                show_alert=True,
            )
            return

    await callback.answer("Qabul qilindi.")

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await callback.message.answer(
        "✅ <b>Ovoz haqidagi arizangiz adminga yuborildi.</b>\n\n"
        "Admin tekshirganidan keyin balansingizga mukofot qo‘shiladi.",
        reply_markup=user_kb(),
    )

    user = callback.from_user

    admin_text = (
        "🔗 <b>YANGI HAVOLA OVOZI</b>\n\n"
        f"👤 Ism: {escape(user.first_name or '')}\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"👤 Username: @{escape(user.username or 'yo‘q')}\n"
        f"💰 Mukofot: {money(VOTE_REWARD)} so‘m\n"
        f"🆔 Ovoz ID: <code>{vote_id}</code>"
    )

    for admin_id in ADMIN_IDS:
        await safe_send(
            admin_id,
            admin_text,
            reply_markup=vote_admin_kb(vote_id, user.id),
        )


@dp.callback_query(F.data == "vote_phone")
async def vote_phone_callback(
    callback: CallbackQuery,
    state: FSMContext,
):
    if is_admin(callback.from_user.id):
        await callback.answer(
            "Admin uchun mavjud emas.",
            show_alert=True,
        )
        return

    await state.set_state(UserStates.phone)
    await callback.answer()

    await callback.message.answer(
        "📱 <b>Telefon raqamingizni yuboring.</b>\n\n"
        "Masalan:\n"
        "<code>+998901234567</code>\n\n"
        "Telefon raqami faqat ovozni tekshirish uchun ishlatiladi.",
    )


@dp.message(UserStates.phone)
async def phone_received(message: Message, state: FSMContext):
    phone = normalize_phone(message.text or "")

    if not valid_phone(phone):
        await message.answer(
            "❌ Telefon raqami noto‘g‘ri.\n\n"
            "Masalan:\n"
            "<code>+998901234567</code>"
        )
        return

    with closing(db()) as c:
        used = c.execute(
            "SELECT phone FROM used_phones WHERE phone=?",
            (phone,),
        ).fetchone()

        if used:
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
              AND status='pending'
            LIMIT 1
        """, (message.from_user.id,)).fetchone()

        if pending:
            await state.clear()
            await message.answer(
                "⏳ Sizda allaqachon tekshirilayotgan ovoz mavjud.",
                reply_markup=user_kb(),
            )
            return

        c.execute("""
            INSERT INTO votes(
                user_id, vote_type, phone, status, reward
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

        c.execute("""
            INSERT INTO chats(user_id,status)
            VALUES(?, 'open')
            ON CONFLICT(user_id)
            DO UPDATE SET status='open'
        """, (message.from_user.id,))

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
        await safe_send(
            admin_id,
            admin_text,
            reply_markup=vote_admin_kb(vote_id, user.id),
        )


# ============================================================
# BALANCE / REFERRAL / WITHDRAW
# ============================================================

@dp.message(F.text == "💰 Balans")
async def balance_handler(message: Message, state: FSMContext):
    await state.clear()

    if is_admin(message.from_user.id):
        return

    user = user_row(message.from_user.id)
    balance = user["balance"] if user else 0

    await message.answer(
        "💰 <b>SIZNING BALANSINGIZ</b>\n\n"
        f"💵 Balans: <b>{money(balance)} so‘m</b>\n\n"
        f"💳 <b>PUL YECHISH UCHUN KAMIDA "
        f"{money(MIN_WITHDRAW)} SO‘M KERAK.</b>\n\n"
        f"🗳 Har bir tasdiqlangan ovoz: "
        f"<b>{money(VOTE_REWARD)} so‘m</b>\n"
        f"👥 Har bir haqiqiy referral: "
        f"<b>{money(REFERRAL_REWARD)} so‘m</b>."
    )


@dp.message(F.text == "👥 Do‘stlarni taklif qilish")
async def referral_handler(message: Message, state: FSMContext):
    await state.clear()

    if is_admin(message.from_user.id):
        return

    me = await bot.get_me()

    if not me.username:
        await message.answer("❌ Bot username'i aniqlanmadi.")
        return

    link = (
        f"https://t.me/{me.username}"
        f"?start=ref_{message.from_user.id}"
    )

    user = user_row(message.from_user.id)
    referrals = user["referrals"] if user else 0

    share_url = (
        "https://t.me/share/url"
        "?url=" + link +
        "&text=Do‘stimning botiga qo‘shiling!"
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
        "Tugmani bosing va Telegramdagi do‘stlaringizni "
        "tanlab taklif yuboring.\n\n"
        f"🔗 Taklif havolangiz:\n"
        f"<code>{escape(link)}</code>\n\n"
        f"👥 Taklif qilinganlar: <b>{referrals}</b>\n"
        f"💰 Har bir haqiqiy do‘st uchun "
        f"<b>{money(REFERRAL_REWARD)} so‘m</b>.",
        reply_markup=keyboard,
    )


@dp.message(F.text == "💳 Pul yechish")
async def withdraw_start(message: Message, state: FSMContext):
    await state.clear()

    if is_admin(message.from_user.id):
        return

    user = user_row(message.from_user.id)
    balance = user["balance"] if user else 0

    if balance < MIN_WITHDRAW:
        await message.answer(
            "❌ <b>Balansingiz yetarli emas.</b>\n\n"
            f"Pul yechish uchun kamida "
            f"<b>{money(MIN_WITHDRAW)} so‘m</b> kerak."
        )
        return

    with closing(db()) as c:
        pending = c.execute("""
            SELECT id
            FROM withdrawals
            WHERE user_id=? AND status='pending'
            LIMIT 1
        """, (message.from_user.id,)).fetchone()

    if pending:
        await message.answer(
            "⏳ Sizda allaqachon ko‘rib chiqilayotgan "
            "pul yechish arizasi bor.",
            reply_markup=user_kb(),
        )
        return

    await state.set_state(UserStates.card)

    await message.answer(
        "💳 <b>Karta raqamingizni yuboring.</b>\n\n"
        "Masalan:\n"
        "<code>8600123456789012</code>"
    )


@dp.message(UserStates.card)
async def card_received(message: Message, state: FSMContext):
    card = re.sub(r"\D", "", message.text or "")

    if not 12 <= len(card) <= 19:
        await message.answer(
            "❌ Karta raqami noto‘g‘ri.\n"
            "Qaytadan yuboring."
        )
        return

    with closing(db()) as c:
        pending = c.execute("""
            SELECT id
            FROM withdrawals
            WHERE user_id=? AND status='pending'
            LIMIT 1
        """, (message.from_user.id,)).fetchone()

        if pending:
            await state.clear()
            await message.answer(
                "⏳ Sizda allaqachon kutilayotgan ariza bor.",
                reply_markup=user_kb(),
            )
            return

        user = c.execute(
            "SELECT balance FROM users WHERE user_id=?",
            (message.from_user.id,),
        ).fetchone()

        if not user or user["balance"] < MIN_WITHDRAW:
            await state.clear()
            await message.answer(
                "❌ Balansingiz yetarli emas.",
                reply_markup=user_kb(),
            )
            return

        amount = int(user["balance"])

        updated = c.execute("""
            UPDATE users
            SET balance=0
            WHERE user_id=? AND balance>=?
        """, (
            message.from_user.id,
            MIN_WITHDRAW,
        ))

        if updated.rowcount != 1:
            await state.clear()
            await message.answer(
                "❌ Balans o‘zgarib ketdi. Qaytadan urinib ko‘ring.",
                reply_markup=user_kb(),
            )
            return

        c.execute("""
            INSERT INTO withdrawals(
                user_id, amount, card_number, status
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

    await state.clear()

    await message.answer(
        "✅ <b>Pul yechish arizangiz qabul qilindi.</b>\n\n"
        f"💰 Summa: <b>{money(amount)} so‘m</b>\n"
        f"💳 Karta: <code>{escape(card)}</code>\n\n"
        "Admin arizani tekshiradi.",
        reply_markup=user_kb(),
    )

    user_obj = message.from_user

    admin_text = (
        "💳 <b>YANGI PUL YECHISH ARIZASI</b>\n\n"
        f"👤 Ism: {escape(user_obj.first_name or '')}\n"
        f"🆔 ID: <code>{user_obj.id}</code>\n"
        f"👤 Username: @{escape(user_obj.username or 'yo‘q')}\n"
        f"💰 Summa: <b>{money(amount)} so‘m</b>\n"
        f"💳 Karta: <code>{escape(card)}</code>\n"
        f"🆔 Ariza: <code>{withdrawal_id}</code>"
    )

    for admin_id in ADMIN_IDS:
        await safe_send(
            admin_id,
            admin_text,
            reply_markup=withdraw_kb(withdrawal_id),
        )


# ============================================================
# Q&A / ADMIN CONTACT
# ============================================================

@dp.message(F.text == "❓ Savol-javob")
async def question_start(message: Message, state: FSMContext):
    await state.clear()

    if is_admin(message.from_user.id):
        return

    await state.set_state(UserStates.question)

    await message.answer(
        "❓ <b>Savolingizni yozing.</b>\n\n"
        "Savolingiz adminlarga yuboriladi."
    )


@dp.message(UserStates.question)
async def question_received(message: Message, state: FSMContext):
    text = (message.text or "").strip()

    if not text:
        await message.answer("❌ Savol matnini yuboring.")
        return

    await state.clear()

    user = message.from_user

    with closing(db()) as c:
        c.execute("""
            INSERT INTO messages(
                user_id, direction, text
            )
            VALUES(?, 'user_to_admin', ?)
        """, (
            user.id,
            text,
        ))

        c.execute("""
            INSERT INTO chats(user_id,status)
            VALUES(?, 'open')
            ON CONFLICT(user_id)
            DO UPDATE SET status='open'
        """, (user.id,))

    for admin_id in ADMIN_IDS:
        await safe_send(
            admin_id,
            "💬 <b>FOYDALANUVCHIDAN XABAR</b>\n\n"
            f"👤 Ism: {escape(user.first_name or '')}\n"
            f"🆔 ID: <code>{user.id}</code>\n"
            f"👤 Username: @{escape(user.username or 'yo‘q')}\n\n"
            f"💬 {escape(text)}",
            reply_markup=chat_kb(user.id),
        )

    await message.answer(
        "✅ <b>Savolingiz adminga yuborildi.</b>\n\n"
        "Admin javobi shu yerga keladi.",
        reply_markup=user_kb(),
    )


@dp.message(F.text == "👨‍💻 Admin bilan bog‘lanish")
async def admin_contact_handler(
    message: Message,
    state: FSMContext,
):
    await state.clear()

    if is_admin(message.from_user.id):
        return

    contact = setting("admin_contact")

    if contact:
        await message.answer(
            "👨‍💻 <b>Admin bilan bog‘lanish:</b>\n\n"
            f"{escape(contact)}"
        )
    else:
        await message.answer(
            "ℹ️ <b>Hozircha admin kontakti qo‘shilmagan.</b>"
        )


@dp.callback_query(F.data == "user_reply")
async def user_reply_callback(
    callback: CallbackQuery,
    state: FSMContext,
):
    if is_admin(callback.from_user.id):
        await callback.answer(
            "Admin uchun emas.",
            show_alert=True,
        )
        return

    with closing(db()) as c:
        chat = c.execute(
            "SELECT status FROM chats WHERE user_id=?",
            (callback.from_user.id,),
        ).fetchone()

    if not chat or chat["status"] != "open":
        await callback.answer(
            "Suhbat yopilgan.",
            show_alert=True,
        )
        return

    await state.set_state(UserStates.question)
    await callback.answer()

    await callback.message.answer(
        "💬 <b>Xabaringizni yozing.</b>"
    )


# ============================================================
# ADMIN STATISTICS
# ============================================================

@dp.message(F.text == "📊 Statistika")
async def statistics(message: Message, state: FSMContext):
    await state.clear()

    if not is_admin(message.from_user.id):
        return

    with closing(db()) as c:
        users = c.execute(
            "SELECT COUNT(*) AS n FROM users"
        ).fetchone()["n"]

        votes = c.execute(
            "SELECT COUNT(*) AS n FROM votes"
        ).fetchone()["n"]

        approved = c.execute(
            "SELECT COUNT(*) AS n FROM votes WHERE status='approved'"
        ).fetchone()["n"]

        pending = c.execute(
            "SELECT COUNT(*) AS n FROM votes WHERE status='pending'"
        ).fetchone()["n"]

        phone_votes = c.execute(
            "SELECT COUNT(*) AS n FROM votes WHERE vote_type='phone'"
        ).fetchone()["n"]

        link_votes = c.execute(
            "SELECT COUNT(*) AS n FROM votes WHERE vote_type='link'"
        ).fetchone()["n"]

        referrals = c.execute(
            "SELECT COUNT(*) AS n FROM referrals"
        ).fetchone()["n"]

        referral_money = c.execute(
            "SELECT COALESCE(SUM(reward),0) AS n FROM referrals"
        ).fetchone()["n"]

        total_balance = c.execute(
            "SELECT COALESCE(SUM(balance),0) AS n FROM users"
        ).fetchone()["n"]

        pending_withdrawals = c.execute(
            "SELECT COUNT(*) AS n "
            "FROM withdrawals WHERE status='pending'"
        ).fetchone()["n"]

        paid_money = c.execute(
            "SELECT COALESCE(SUM(amount),0) AS n "
            "FROM withdrawals WHERE status='paid'"
        ).fetchone()["n"]

    await message.answer(
        "📊 <b>BOT STATISTIKASI</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{users}</b>\n"
        f"🗳 Jami ovozlar: <b>{votes}</b>\n"
        f"📱 Telefon ovozlari: <b>{phone_votes}</b>\n"
        f"🔗 Havola ovozlari: <b>{link_votes}</b>\n"
        f"✅ Tasdiqlangan: <b>{approved}</b>\n"
        f"⏳ Kutilayotgan: <b>{pending}</b>\n\n"
        f"👥 Referallar: <b>{referrals}</b>\n"
        f"💰 Referral mukofoti: "
        f"<b>{money(referral_money)} so‘m</b>\n\n"
        f"💵 Foydalanuvchilar balanslari: "
        f"<b>{money(total_balance)} so‘m</b>\n"
        f"💳 Kutilayotgan yechishlar: "
        f"<b>{pending_withdrawals}</b>\n"
        f"💸 To‘langan: "
        f"<b>{money(paid_money)} so‘m</b>",
        reply_markup=admin_kb(),
    )


@dp.message(F.text == "👥 Foydalanuvchilar")
async def admin_users(message: Message, state: FSMContext):
    await state.clear()

    if not is_admin(message.from_user.id):
        return

    with closing(db()) as c:
        rows = c.execute("""
            SELECT user_id, first_name, username, balance, referrals
            FROM users
            ORDER BY rowid DESC
            LIMIT 30
        """).fetchall()

    if not rows:
        await message.answer("👥 Foydalanuvchilar yo‘q.")
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

    await message.answer(text, reply_markup=admin_kb())


@dp.message(F.text == "🗳 Ovozlar")
async def admin_votes(message: Message, state: FSMContext):
    await state.clear()

    if not is_admin(message.from_user.id):
        return

    with closing(db()) as c:
        rows = c.execute("""
            SELECT v.id, v.user_id, v.vote_type, v.phone,
                   v.status, v.reward, u.first_name
            FROM votes v
            LEFT JOIN users u ON u.user_id=v.user_id
            ORDER BY v.id DESC
            LIMIT 30
        """).fetchall()

    if not rows:
        await message.answer("🗳 Ovozlar yo‘q.")
        return

    for row in rows:
        keyboard = (
            vote_admin_kb(row["id"], row["user_id"])
            if row["status"] == "pending"
            else None
        )

        await message.answer(
            f"🗳 <b>Ovoz #{row['id']}</b>\n\n"
            f"👤 {escape(row['first_name'] or '')}\n"
            f"🆔 <code>{row['user_id']}</code>\n"
            f"📌 Turi: <b>{escape(row['vote_type'])}</b>\n"
            f"📞 <code>{escape(row['phone'] or '-')}</code>\n"
            f"📊 Holat: <b>{escape(row['status'])}</b>\n"
            f"💰 {money(row['reward'])} so‘m",
            reply_markup=keyboard,
        )


@dp.message(F.text == "📱 Telefon ovozlari")
async def admin_phone_votes(message: Message, state: FSMContext):
    await state.clear()

    if not is_admin(message.from_user.id):
        return

    with closing(db()) as c:
        rows = c.execute("""
            SELECT v.id, v.user_id, v.phone, v.status,
                   v.reward, u.first_name
            FROM votes v
            LEFT JOIN users u ON u.user_id=v.user_id
            WHERE v.vote_type='phone'
            ORDER BY v.id DESC
            LIMIT 30
        """).fetchall()

    if not rows:
        await message.answer("📱 Telefon ovozlari yo‘q.")
        return

    for row in rows:
        keyboard = (
            vote_admin_kb(row["id"], row["user_id"])
            if row["status"] == "pending"
            else None
        )

        await message.answer(
            f"📱 <b>Telefon ovozi #{row['id']}</b>\n\n"
            f"👤 {escape(row['first_name'] or '')}\n"
            f"🆔 <code>{row['user_id']}</code>\n"
            f"📞 <code>{escape(row['phone'] or '')}</code>\n"
            f"📊 Holat: <b>{escape(row['status'])}</b>\n"
            f"💰 {money(row['reward'])} so‘m",
            reply_markup=keyboard,
        )


@dp.message(F.text == "👥 Referallar")
async def admin_referrals(message: Message, state: FSMContext):
    await state.clear()

    if not is_admin(message.from_user.id):
        return

    with closing(db()) as c:
        rows = c.execute("""
            SELECT inviter_id, invited_id, reward
            FROM referrals
            ORDER BY id DESC
            LIMIT 50
        """).fetchall()

    if not rows:
        await message.answer("👥 Referallar yo‘q.")
        return

    text = "👥 <b>REFERALLAR</b>\n\n"

    for row in rows:
        text += (
            f"👤 Taklif qiluvchi: <code>{row['inviter_id']}</code>\n"
            f"👤 Taklif qilingan: <code>{row['invited_id']}</code>\n"
            f"💰 Mukofot: {money(row['reward'])} so‘m\n"
            "────────────\n"
        )

    await message.answer(text, reply_markup=admin_kb())


@dp.message(F.text == "💳 Pul yechishlar")
async def admin_withdrawals(message: Message, state: FSMContext):
    await state.clear()

    if not is_admin(message.from_user.id):
        return

    with closing(db()) as c:
        rows = c.execute("""
            SELECT w.id, w.user_id, w.amount, w.card_number,
                   w.status, u.first_name
            FROM withdrawals w
            LEFT JOIN users u ON u.user_id=w.user_id
            ORDER BY w.id DESC
            LIMIT 30
        """).fetchall()

    if not rows:
        await message.answer("💳 Pul yechish arizalari yo‘q.")
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
            f"💳 <code>{escape(row['card_number'])}</code>\n"
            f"📊 Holat: <b>{escape(row['status'])}</b>",
            reply_markup=keyboard,
        )


@dp.message(F.text == "❓ Savollar")
async def admin_questions(message: Message, state: FSMContext):
    await state.clear()

    if not is_admin(message.from_user.id):
        return

    with closing(db()) as c:
        rows = c.execute("""
            SELECT m.user_id, m.text, m.created_at, u.first_name
            FROM messages m
            LEFT JOIN users u ON u.user_id=m.user_id
            WHERE m.direction='user_to_admin'
            ORDER BY m.id DESC
            LIMIT 30
        """).fetchall()

    if not rows:
        await message.answer("❓ Savollar yo‘q.")
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
# ADMIN SETTINGS
# ============================================================

@dp.message(F.text == "🔗 Ovoz havolasi")
async def vote_url_start(message: Message, state: FSMContext):
    await state.clear()

    if not is_admin(message.from_user.id):
        return

    await state.set_state(AdminStates.vote_url)

    await message.answer(
        "🔗 <b>Yangi ovoz havolasini yuboring.</b>\n\n"
        f"Hozirgi havola:\n"
        f"{escape(setting('vote_url', 'Hali qo‘shilmagan'))}"
    )


@dp.message(AdminStates.vote_url)
async def vote_url_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    url = (message.text or "").strip()

    if not valid_url(url):
        await message.answer(
            "❌ Havola http:// yoki https:// bilan boshlanishi kerak."
        )
        return

    set_setting("vote_url", url)
    await state.clear()

    await message.answer(
        "✅ <b>Ovoz havolasi saqlandi.</b>",
        reply_markup=admin_kb(),
    )


@dp.message(F.text == "👨‍💻 Admin kontakt")
async def contact_start(message: Message, state: FSMContext):
    await state.clear()

    if not is_admin(message.from_user.id):
        return

    await state.set_state(AdminStates.contact)

    await message.answer(
        "👨‍💻 <b>Admin Telegram username yoki "
        "telefon raqamini yuboring.</b>\n\n"
        f"Hozirgi:\n"
        f"{escape(setting('admin_contact', 'Hali qo‘shilmagan'))}"
    )


@dp.message(AdminStates.contact)
async def contact_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    contact = (message.text or "").strip()

    if not contact:
        await message.answer("❌ Kontaktni yozing.")
        return

    set_setting("admin_contact", contact)
    await state.clear()

    await message.answer(
        "✅ <b>Admin kontakti saqlandi.</b>",
        reply_markup=admin_kb(),
    )


@dp.message(AdminStates.proof_channel)
async def proof_channel_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    url = (message.text or "").strip()

    if not valid_url(url):
        await message.answer(
            "❌ Havola noto‘g‘ri.\n\n"
            "Masalan:\n"
            "<code>https://t.me/kanal_nomi</code>"
        )
        return

    set_setting("proof_channel", url)
    await state.clear()

    await message.answer(
        "✅ <b>Isbot kanali muvaffaqiyatli saqlandi.</b>\n\n"
        f"📢 {escape(url)}",
        reply_markup=admin_kb(),
    )


# ============================================================
# ADMIN PROJECT
# ============================================================

@dp.message(F.text == "➕ Loyiha qo‘shish")
async def project_start(message: Message, state: FSMContext):
    await state.clear()

    if not is_admin(message.from_user.id):
        return

    await state.set_state(AdminStates.project_name)
    await message.answer("➕ <b>Loyiha nomini yozing.</b>")


@dp.message(AdminStates.project_name)
async def project_name_received(
    message: Message,
    state: FSMContext,
):
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    name = (message.text or "").strip()

    if not name:
        await message.answer("❌ Loyiha nomini yozing.")
        return

    await state.update_data(project_name=name)
    await state.set_state(AdminStates.project_url)

    await message.answer(
        "🔗 <b>Endi loyiha havolasini yuboring.</b>\n\n"
        "Masalan:\n"
        "<code>https://example.com</code>"
    )


@dp.message(AdminStates.project_url)
async def project_url_received(
    message: Message,
    state: FSMContext,
):
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    url = (message.text or "").strip()

    if not valid_url(url):
        await message.answer(
            "❌ Havola http:// yoki https:// bilan boshlanishi kerak."
        )
        return

    data = await state.get_data()
    name = data.get("project_name")

    if not name:
        await state.clear()
        await message.answer(
            "❌ Loyiha ma’lumoti topilmadi.",
            reply_markup=admin_kb(),
        )
        return

    with closing(db()) as c:
        c.execute(
            "INSERT INTO projects(name,url,active) VALUES(?,?,1)",
            (name, url),
        )

    await state.clear()

    await message.answer(
        "✅ <b>Loyiha muvaffaqiyatli qo‘shildi.</b>\n\n"
        f"📌 {escape(name)}\n"
        f"🔗 {escape(url)}",
        reply_markup=admin_kb(),
    )


# ============================================================
# BROADCAST
# ============================================================

@dp.message(F.text == "📢 Reklama")
async def broadcast_start(message: Message, state: FSMContext):
    await state.clear()

    if not is_admin(message.from_user.id):
        return

    await state.set_state(AdminStates.broadcast)

    await message.answer(
        "📢 <b>Yuboriladigan xabarni yozing.</b>\n\n"
        "Hozircha matnli reklama yuborish qo‘llab-quvvatlanadi."
    )


@dp.message(AdminStates.broadcast)
async def broadcast_received(
    message: Message,
    state: FSMContext,
):
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    text = (message.text or "").strip()

    if not text:
        await message.answer("❌ Xabar matnini yuboring.")
        return

    with closing(db()) as c:
        users = c.execute(
            "SELECT user_id FROM users"
        ).fetchall()

    sent = 0
    failed = 0

    # Juda katta auditoriyada Telegram flood limitini kamaytirish
    # uchun xabarlar orasida qisqa tanaffus.
    for row in users:
        if await safe_send(row["user_id"], text):
            sent += 1
        else:
            failed += 1

        await asyncio.sleep(0.05)

    await state.clear()

    await message.answer(
        "📢 <b>Reklama yakunlandi.</b>\n\n"
        f"✅ Yuborildi: <b>{sent}</b>\n"
        f"❌ Yuborilmadi: <b>{failed}</b>",
        reply_markup=admin_kb(),
    )


# ============================================================
# ADMIN CHAT / REPLY
# ============================================================

@dp.callback_query(F.data.startswith("reply:"))
async def admin_reply_start(
    callback: CallbackQuery,
    state: FSMContext,
):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "Ruxsat yo‘q.",
            show_alert=True,
        )
        return

    try:
        user_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer(
            "Foydalanuvchi ID xato.",
            show_alert=True,
        )
        return

    with closing(db()) as c:
        user = c.execute(
            "SELECT user_id FROM users WHERE user_id=?",
            (user_id,),
        ).fetchone()

    if not user:
        await callback.answer(
            "Foydalanuvchi topilmadi.",
            show_alert=True,
        )
        return

    await state.clear()
    await state.set_state(AdminStates.reply)
    await state.update_data(reply_user_id=user_id)

    await callback.answer()

    await callback.message.answer(
        f"💬 <b>Foydalanuvchi {user_id} ga javob yozing.</b>\n\n"
        "Keyingi yuborgan matningiz foydalanuvchiga yuboriladi."
    )


@dp.message(AdminStates.reply)
async def admin_reply(
    message: Message,
    state: FSMContext,
):
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    data = await state.get_data()
    user_id = data.get("reply_user_id")
    text = (message.text or "").strip()

    if not user_id:
        await state.clear()
        await message.answer(
            "❌ Foydalanuvchi ID topilmadi.",
            reply_markup=admin_kb(),
        )
        return

    if not text:
        await message.answer("❌ Javob matnini yuboring.")
        return

    with closing(db()) as c:
        user = c.execute(
            "SELECT user_id FROM users WHERE user_id=?",
            (user_id,),
        ).fetchone()

        if not user:
            await state.clear()
            await message.answer(
                "❌ Foydalanuvchi topilmadi.",
                reply_markup=admin_kb(),
            )
            return

        c.execute("""
            INSERT INTO messages(
                user_id, admin_id, direction, text
            )
            VALUES(?, ?, 'admin_to_user', ?)
        """, (
            user_id,
            message.from_user.id,
            text,
        ))

        c.execute("""
            INSERT INTO chats(user_id,status,admin_id)
            VALUES(?, 'open', ?)
            ON CONFLICT(user_id)
            DO UPDATE SET status='open', admin_id=excluded.admin_id
        """, (
            user_id,
            message.from_user.id,
        ))

    sent = await safe_send(
        user_id,
        "👨‍💻 <b>Admin javobi:</b>\n\n"
        f"{escape(text)}",
        reply_markup=user_chat_kb(),
    )

    await state.clear()

    if sent:
        await message.answer(
            "✅ <b>Javob foydalanuvchiga yuborildi.</b>",
            reply_markup=admin_kb(),
        )
    else:
        await message.answer(
            "⚠️ Javob yuborilmadi. Foydalanuvchi botni "
            "bloklagan bo‘lishi mumkin.",
            reply_markup=admin_kb(),
        )


@dp.callback_query(F.data.startswith("close:"))
async def close_chat_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "Ruxsat yo‘q.",
            show_alert=True,
        )
        return

    try:
        user_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Xato.", show_alert=True)
        return

    with closing(db()) as c:
        c.execute("""
            INSERT INTO chats(user_id,status,admin_id)
            VALUES(?, 'closed', ?)
            ON CONFLICT(user_id)
            DO UPDATE SET status='closed', admin_id=excluded.admin_id
        """, (
            user_id,
            callback.from_user.id,
        ))

    await callback.answer("Suhbat yopildi.")

    try:
        await callback.message.edit_reply_markup(
            reply_markup=None
        )
    except Exception:
        pass

    await safe_send(
        user_id,
        "🔒 <b>Suhbat admin tomonidan yopildi.</b>\n\n"
        "Yana savol bo‘lsa, «❓ Savol-javob» bo‘limidan yozishingiz mumkin.",
    )


# ============================================================
# VOTE APPROVE / REJECT
# ============================================================

@dp.callback_query(F.data.startswith("va:"))
async def vote_approve(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "Ruxsat yo‘q.",
            show_alert=True,
        )
        return

    try:
        vote_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer(
            "Ovoz ID xato.",
            show_alert=True,
        )
        return

    with closing(db()) as c:
        # BEGIN IMMEDIATE bir vaqtning o'zida ikki admin
        # tasdiqlashining oldini oladi.
        c.execute("BEGIN IMMEDIATE")

        vote = c.execute("""
            SELECT id, user_id, vote_type, phone, reward, status
            FROM votes
            WHERE id=?
        """, (vote_id,)).fetchone()

        if not vote:
            c.rollback()
            await callback.answer(
                "Ovoz topilmadi.",
                show_alert=True,
            )
            return

        if vote["status"] != "pending":
            c.rollback()
            await callback.answer(
                f"Ovoz allaqachon {vote['status']}.",
                show_alert=True,
            )
            return

        if vote["vote_type"] == "phone":
            phone = normalize_phone(vote["phone"])

            used = c.execute(
                "SELECT vote_id FROM used_phones WHERE phone=?",
                (phone,),
            ).fetchone()

            if used:
                c.execute("""
                    UPDATE votes
                    SET status='rejected'
                    WHERE id=? AND status='pending'
                """, (vote_id,))
                c.commit()

                await callback.answer(
                    "Bu telefon raqami avval ishlatilgan. "
                    "Ovoz rad etildi.",
                    show_alert=True,
                )

                try:
                    await callback.message.edit_reply_markup(
                        reply_markup=None
                    )
                except Exception:
                    pass

                await safe_send(
                    vote["user_id"],
                    "❌ <b>Ovozingiz rad etildi.</b>\n\n"
                    "Bu telefon raqami avval ishlatilgan.",
                    reply_markup=user_kb(),
                )
                return

            c.execute("""
                INSERT INTO used_phones(phone,user_id,vote_id)
                VALUES(?,?,?)
            """, (
                phone,
                vote["user_id"],
                vote_id,
            ))

        updated = c.execute("""
            UPDATE votes
            SET status='approved'
            WHERE id=? AND status='pending'
        """, (vote_id,))

        if updated.rowcount != 1:
            c.rollback()
            await callback.answer(
                "Ovoz boshqa admin tomonidan ko‘rib chiqildi.",
                show_alert=True,
            )
            return

        updated_user = c.execute("""
            UPDATE users
            SET balance=balance+?
            WHERE user_id=?
        """, (
            vote["reward"],
            vote["user_id"],
        ))

        if updated_user.rowcount != 1:
            c.rollback()
            await callback.answer(
                "Foydalanuvchi topilmadi.",
                show_alert=True,
            )
            return

        c.commit()

    await callback.answer("Ovoz tasdiqlandi.")

    try:
        await callback.message.edit_reply_markup(
            reply_markup=None
        )
    except Exception:
        pass

    await safe_send(
        vote["user_id"],
        "✅ <b>Ovozingiz tasdiqlandi!</b>\n\n"
        f"💰 Balansingizga "
        f"<b>+{money(vote['reward'])} so‘m</b> qo‘shildi.",
        reply_markup=user_kb(),
    )

    await callback.message.answer(
        f"✅ <b>Ovoz #{vote_id} tasdiqlandi.</b>\n"
        f"Foydalanuvchiga {money(vote['reward'])} so‘m qo‘shildi.",
    )


@dp.callback_query(F.data.startswith("vr:"))
async def vote_reject(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "Ruxsat yo‘q.",
            show_alert=True,
        )
        return

    try:
        vote_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer(
            "Ovoz ID xato.",
            show_alert=True,
        )
        return

    with closing(db()) as c:
        c.execute("BEGIN IMMEDIATE")

        vote = c.execute("""
            SELECT id, user_id, status
            FROM votes
            WHERE id=?
        """, (vote_id,)).fetchone()

        if not vote:
            c.rollback()
            await callback.answer(
                "Ovoz topilmadi.",
                show_alert=True,
            )
            return

        if vote["status"] != "pending":
            c.rollback()
            await callback.answer(
                f"Ovoz allaqachon {vote['status']}.",
                show_alert=True,
            )
            return

        updated = c.execute("""
            UPDATE votes
            SET status='rejected'
            WHERE id=? AND status='pending'
        """, (vote_id,))

        if updated.rowcount != 1:
            c.rollback()
            await callback.answer(
                "Ovoz boshqa admin tomonidan ko‘rib chiqildi.",
                show_alert=True,
            )
            return

        c.commit()

    await callback.answer("Ovoz rad etildi.")

    try:
        await callback.message.edit_reply_markup(
            reply_markup=None
        )
    except Exception:
        pass

    await safe_send(
        vote["user_id"],
        "❌ <b>Ovozingiz rad etildi.</b>\n\n"
        "Agar xato deb hisoblasangiz, admin bilan bog‘lanishingiz mumkin.",
        reply_markup=user_kb(),
    )

    await callback.message.answer(
        f"❌ <b>Ovoz #{vote_id} rad etildi.</b>"
    )


# ============================================================
# WITHDRAWAL PAID / REJECTED
# ============================================================

@dp.callback_query(F.data.startswith("wp:"))
async def withdrawal_paid(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "Ruxsat yo‘q.",
            show_alert=True,
        )
        return

    try:
        withdrawal_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer(
            "Ariza ID xato.",
            show_alert=True,
        )
        return

    with closing(db()) as c:
        c.execute("BEGIN IMMEDIATE")

        row = c.execute("""
            SELECT id, user_id, amount, status
            FROM withdrawals
            WHERE id=?
        """, (withdrawal_id,)).fetchone()

        if not row:
            c.rollback()
            await callback.answer(
                "Ariza topilmadi.",
                show_alert=True,
            )
            return

        if row["status"] != "pending":
            c.rollback()
            await callback.answer(
                f"Ariza allaqachon {row['status']}.",
                show_alert=True,
            )
            return

        updated = c.execute("""
            UPDATE withdrawals
            SET status='paid'
            WHERE id=? AND status='pending'
        """, (withdrawal_id,))

        if updated.rowcount != 1:
            c.rollback()
            await callback.answer(
                "Ariza boshqa admin tomonidan ko‘rib chiqildi.",
                show_alert=True,
            )
            return

        c.commit()

    await callback.answer("To‘langan deb belgilandi.")

    try:
        await callback.message.edit_reply_markup(
            reply_markup=None
        )
    except Exception:
        pass

    await safe_send(
        row["user_id"],
        "✅ <b>Pul yechish arizangiz to‘landi!</b>\n\n"
        f"💰 Summa: <b>{money(row['amount'])} so‘m</b>",
        reply_markup=user_kb(),
    )

    await callback.message.answer(
        f"✅ <b>Ariza #{withdrawal_id} to‘landi deb belgilandi.</b>"
    )


@dp.callback_query(F.data.startswith("wr:"))
async def withdrawal_reject(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "Ruxsat yo‘q.",
            show_alert=True,
        )
        return

    try:
        withdrawal_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer(
            "Ariza ID xato.",
            show_alert=True,
        )
        return

    with closing(db()) as c:
        c.execute("BEGIN IMMEDIATE")

        row = c.execute("""
            SELECT id, user_id, amount, status
            FROM withdrawals
            WHERE id=?
        """, (withdrawal_id,)).fetchone()

        if not row:
            c.rollback()
            await callback.answer(
                "Ariza topilmadi.",
                show_alert=True,
            )
            return

        if row["status"] != "pending":
            c.rollback()
            await callback.answer(
                f"Ariza allaqachon {row['status']}.",
                show_alert=True,
            )
            return

        updated = c.execute("""
            UPDATE withdrawals
            SET status='rejected'
            WHERE id=? AND status='pending'
        """, (withdrawal_id,))

        if updated.rowcount != 1:
            c.rollback()
            await callback.answer(
                "Ariza boshqa admin tomonidan ko‘rib chiqildi.",
                show_alert=True,
            )
            return

        c.execute("""
            UPDATE users
            SET balance=balance+?
            WHERE user_id=?
        """, (
            row["amount"],
            row["user_id"],
        ))

        c.commit()

    await callback.answer("Ariza rad etildi.")

    try:
        await callback.message.edit_reply_markup(
            reply_markup=None
        )
    except Exception:
        pass

    await safe_send(
        row["user_id"],
        "❌ <b>Pul yechish arizangiz rad etildi.</b>\n\n"
        f"💰 {money(row['amount'])} so‘m balansingizga qaytarildi.",
        reply_markup=user_kb(),
    )

    await callback.message.answer(
        f"❌ <b>Ariza #{withdrawal_id} rad etildi.</b>\n"
        f"{money(row['amount'])} so‘m balansga qaytarildi."
    )


# ============================================================
# FALLBACK
# ============================================================

@dp.message()
async def fallback_handler(message: Message, state: FSMContext):
    current = await state.get_state()

    if current:
        return

    if is_admin(message.from_user.id):
        await message.answer(
            "👨‍💼 Admin paneldan kerakli bo‘limni tanlang.",
            reply_markup=admin_kb(),
        )
    else:
        await message.answer(
            "ℹ️ Pastdagi menyudan kerakli bo‘limni tanlang.",
            reply_markup=user_kb(),
        )


# ============================================================
# STARTUP
# ============================================================

async def main():
    init_db()

    me = await bot.get_me()

    logger.info(
        "Bot ishga tushdi: @%s | admins=%s | db=%s",
        me.username,
        sorted(ADMIN_IDS),
        DB_NAME,
    )

    # Agar webhook qolib ketgan bo‘lsa, pollingga o'tamiz.
    await bot.delete_webhook(drop_pending_updates=False)

    await dp.start_polling(
        bot,
        allowed_updates=dp.resolve_used_update_types(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to'xtatildi.")
