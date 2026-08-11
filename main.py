# ============================================================
# TELEGRAM BOT — MAIN.PY
# AIROGRAM 3.x
# ============================================================

import asyncio
import logging
import os
import re
import sqlite3
from contextlib import closing
from html import escape

from aiogram import Bot, Dispatcher, F
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
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties


# ============================================================
# 1. SOZLAMALAR
# ============================================================

# ============================================================
# BOT TOKENINI SHU YERGA YOZING
# Masalan:
# BOT_TOKEN = "1234567890:AAxxxxxxxxxxxxxxxxxxxxxxxx"
# ============================================================

BOT_TOKEN = "8615736731:AAF7LGgYsKCq_JjV9qFPmFV6psTAS4mlQ_g"


# ============================================================
# ADMIN ID LARINI SHU YERGA YOZING
#
# Masalan:
# ADMIN_IDS = {123456789, 987654321}
# ============================================================

ADMIN_IDS = {
    7998053914
}


# Pul qiymatlari
VOTE_REWARD = 30000
REFERRAL_REWARD = 10000
MIN_WITHDRAW = 30000


DB_NAME = "bot.db"


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)


# ============================================================
# DATABASE
# ============================================================

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():

    with closing(get_db()) as db:

        # Foydalanuvchilar
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                language TEXT DEFAULT 'uz',
                phone TEXT,
                balance INTEGER DEFAULT 0,
                referrals INTEGER DEFAULT 0,
                referred_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Ovozlar
        db.execute("""
            CREATE TABLE IF NOT EXISTS votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                vote_type TEXT NOT NULL,
                phone TEXT,
                project_id INTEGER,
                status TEXT DEFAULT 'pending',
                reward INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Loyihalar
        db.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                url TEXT,
                active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Pul yechish
        db.execute("""
            CREATE TABLE IF NOT EXISTS withdrawals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                card_number TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Savollar
        db.execute("""
            CREATE TABLE IF NOT EXISTS support_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                admin_id INTEGER,
                message TEXT,
                direction TEXT,
                status TEXT DEFAULT 'open',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Sozlamalar
        db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # Referral takrorlanishidan himoya
        db.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                inviter_id INTEGER NOT NULL,
                invited_id INTEGER NOT NULL UNIQUE,
                reward INTEGER DEFAULT 10000,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Telefon raqamini qayta ishlatishdan himoya
        db.execute("""
            CREATE TABLE IF NOT EXISTS used_phones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT UNIQUE NOT NULL,
                user_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        db.commit()


# ============================================================
# DATABASE YORDAMCHI FUNKSIYALAR
# ============================================================

def get_setting(key, default=""):
    with closing(get_db()) as db:
        row = db.execute(
            "SELECT value FROM settings WHERE key=?",
            (key,)
        ).fetchone()

        return row["value"] if row else default


def set_setting(key, value):
    with closing(get_db()) as db:
        db.execute("""
            INSERT INTO settings(key, value)
            VALUES(?, ?)
            ON CONFLICT(key)
            DO UPDATE SET value=excluded.value
        """, (key, value))
        db.commit()


def add_user(user_id, username, first_name, referred_by=None):

    with closing(get_db()) as db:

        existing = db.execute(
            "SELECT user_id FROM users WHERE user_id=?",
            (user_id,)
        ).fetchone()

        if existing:
            db.execute("""
                UPDATE users
                SET username=?, first_name=?
                WHERE user_id=?
            """, (username, first_name, user_id))

            db.commit()
            return False

        # O'zini o'zi referral qilishni taqiqlash
        if referred_by == user_id:
            referred_by = None

        db.execute("""
            INSERT INTO users(
                user_id,
                username,
                first_name,
                referred_by
            )
            VALUES(?,?,?,?)
        """, (
            user_id,
            username,
            first_name,
            referred_by
        ))

        db.commit()
        return True


def get_user(user_id):

    with closing(get_db()) as db:
        return db.execute(
            "SELECT * FROM users WHERE user_id=?",
            (user_id,)
        ).fetchone()


def add_balance(user_id, amount):

    with closing(get_db()) as db:
        db.execute("""
            UPDATE users
            SET balance = balance + ?
            WHERE user_id=?
        """, (amount, user_id))

        db.commit()


def subtract_balance(user_id, amount):

    with closing(get_db()) as db:
        db.execute("""
            UPDATE users
            SET balance =
                CASE
                    WHEN balance >= ? THEN balance - ?
                    ELSE 0
                END
            WHERE user_id=?
        """, (amount, amount, user_id))

        db.commit()


def normalize_phone(phone):

    phone = re.sub(r"[^\d+]", "", phone)

    if phone.startswith("00"):
        phone = "+" + phone[2:]

    if phone.startswith("+"):
        digits = "+" + re.sub(r"\D", "", phone)
    else:
        digits = re.sub(r"\D", "", phone)

    return digits


def valid_phone(phone):

    phone = normalize_phone(phone)

    if phone.startswith("+"):
        digits = phone[1:]
    else:
        digits = phone

    return 8 <= len(digits) <= 15


def is_admin(user_id):
    return user_id in ADMIN_IDS


# ============================================================
# BOT / DISPATCHER
# ============================================================

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML
    )
)

dp = Dispatcher()


# ============================================================
# STATES
# ============================================================

class UserStates(StatesGroup):
    waiting_question = State()
    waiting_phone = State()
    waiting_card = State()


class AdminStates(StatesGroup):
    waiting_project_name = State()
    waiting_project_url = State()
    waiting_broadcast = State()
    waiting_contact = State()
    waiting_reply = State()


# ============================================================
# USER KEYBOARD
# ============================================================

def user_keyboard():

    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📌 Loyihalar"),
                KeyboardButton(text="🗳 Ovoz berish")
            ],
            [
                KeyboardButton(text="💰 Balans"),
                KeyboardButton(text="💳 Pul yechish")
            ],
            [
                KeyboardButton(text="👥 Do‘stlarni taklif qilish"),
                KeyboardButton(text="❓ Savol-javob")
            ],
            [
                KeyboardButton(text="👨‍💻 Admin bilan bog‘lanish")
            ]
        ],
        resize_keyboard=True,
        is_persistent=True
    )


# ============================================================
# ADMIN KEYBOARD
# ============================================================

def admin_keyboard():

    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📊 Statistika"),
                KeyboardButton(text="👥 Foydalanuvchilar")
            ],
            [
                KeyboardButton(text="🗳 Ovozlar"),
                KeyboardButton(text="💳 Pul yechishlar")
            ],
            [
                KeyboardButton(text="❓ Savollar"),
                KeyboardButton(text="📱 Telefon ovozlari")
            ],
            [
                KeyboardButton(text="👥 Referallar"),
                KeyboardButton(text="🔗 Ovoz havolasi")
            ],
            [
                KeyboardButton(text="👨‍💻 Admin kontakt"),
                KeyboardButton(text="📢 Reklama")
            ],
            [
                KeyboardButton(text="➕ Loyiha qo‘shish"),
                KeyboardButton(text="📌 Loyihalar")
            ],
            [
                KeyboardButton(text="🏠 Foydalanuvchi menyusi")
            ]
        ],
        resize_keyboard=True,
        is_persistent=True
    )


# ============================================================
# INLINE KEYBOARDS
# ============================================================

def vote_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔗 Havola orqali",
                    callback_data="vote_link"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📱 Telefon raqami orqali",
                    callback_data="vote_phone"
                )
            ]
        ]
    )


def withdrawal_keyboard(withdraw_id):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ To‘landi",
                    callback_data=f"withdraw_paid:{withdraw_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Rad etish",
                    callback_data=f"withdraw_reject:{withdraw_id}"
                )
            ]
        ]
    )


def vote_admin_keyboard(vote_id):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Ovoz tasdiqlandi",
                    callback_data=f"vote_approve:{vote_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Rad etish",
                    callback_data=f"vote_reject:{vote_id}"
                )
            ]
        ]
    )


def close_chat_keyboard(user_id):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 Javob berish",
                    callback_data=f"reply_user:{user_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔒 Suhbatni yopish",
                    callback_data=f"close_chat:{user_id}"
                )
            ]
        ]
    )


# ============================================================
# START
# ============================================================

@dp.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):

    await state.clear()

    user = message.from_user

    # Referral
    referred_by = None

    parts = message.text.split(maxsplit=1)

    if len(parts) > 1:

        code = parts[1]

        if code.startswith("ref_"):

            try:
                referred_by = int(code.replace("ref_", ""))
            except ValueError:
                referred_by = None

    is_new = add_user(
        user.id,
        user.username or "",
        user.first_name or "",
        referred_by
    )

    # Yangi foydalanuvchi bo'lsa referral mukofoti
    if is_new and referred_by:

        if referred_by != user.id:

            try:

                with closing(get_db()) as db:

                    already = db.execute(
                        "SELECT id FROM referrals WHERE invited_id=?",
                        (user.id,)
                    ).fetchone()

                    inviter = db.execute(
                        "SELECT user_id FROM users WHERE user_id=?",
                        (referred_by,)
                    ).fetchone()

                    if not already and inviter:

                        db.execute("""
                            INSERT INTO referrals(
                                inviter_id,
                                invited_id,
                                reward
                            )
                            VALUES(?,?,?)
                        """, (
                            referred_by,
                            user.id,
                            REFERRAL_REWARD
                        ))

                        db.execute("""
                            UPDATE users
                            SET balance=balance+?,
                                referrals=referrals+1
                            WHERE user_id=?
                        """, (
                            REFERRAL_REWARD,
                            referred_by
                        ))

                        db.commit()

                        try:
                            await bot.send_message(
                                referred_by,
                                f"🎉 <b>Yangi do‘st taklif qilindi!</b>\n\n"
                                f"💰 Balansingizga "
                                f"<b>{REFERRAL_REWARD:,} so‘m</b> qo‘shildi."
                            )
                        except Exception:
                            pass

            except Exception:
                logger.exception("Referral error")

    await message.answer(
        "👋 <b>Assalomu alaykum!</b>\n\n"
        "Botga xush kelibsiz.\n"
        "Kerakli bo‘limni pastdagi menyudan tanlang.",
        reply_markup=user_keyboard()
    )


# ============================================================
# LOYIHALAR
# ============================================================

@dp.message(F.text == "📌 Loyihalar")
async def projects_handler(message: Message):

    with closing(get_db()) as db:

        projects = db.execute("""
            SELECT *
            FROM projects
            WHERE active=1
            ORDER BY id DESC
        """).fetchall()

    if not projects:

        await message.answer(
            "📌 <b>Hozircha loyihalar mavjud emas.</b>",
            reply_markup=user_keyboard()
        )
        return

    text = "📌 <b>Loyihalar</b>\n\n"

    buttons = []

    for project in projects:

        text += (
            f"🔹 <b>{escape(project['name'])}</b>\n"
            f"🔗 {escape(project['url'] or 'Havola hali qo‘shilmagan')}\n\n"
        )

        if project["url"]:
            buttons.append([
                InlineKeyboardButton(
                    text=f"🔗 {project['name']}",
                    url=project["url"]
                )
            ])

    await message.answer(
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        ) if buttons else None
    )


# ============================================================
# OVOZ BERISH
# ============================================================

@dp.message(F.text == "🗳 Ovoz berish")
async def vote_handler(message: Message):

    await message.answer(
        "🗳 <b>Ovoz berish usulini tanlang:</b>\n\n"
        "Quyidagi usullardan birini tanlang:",
        reply_markup=vote_keyboard()
    )


@dp.callback_query(F.data == "vote_link")
async def vote_link_callback(callback: CallbackQuery):

    url = get_setting("vote_url", "")

    if not url:

        await callback.message.answer(
            "❌ Hozircha ovoz berish havolasi admin tomonidan "
            "qo‘shilmagan."
        )

        await callback.answer()
        return

    await callback.message.answer(
        "🔗 <b>Ovoz berish havolasi:</b>\n\n"
        f"{escape(url)}\n\n"
        "Ovoz berib bo‘lganingizdan keyin kerak bo‘lsa "
        "telefon orqali ovoz berish bo‘limidan foydalaning."
    )

    await callback.answer()


@dp.callback_query(F.data == "vote_phone")
async def vote_phone_callback(
    callback: CallbackQuery,
    state: FSMContext
):

    await state.set_state(UserStates.waiting_phone)

    await callback.message.answer(
        "📱 <b>Telefon raqamingizni yuboring.</b>\n\n"
        "Raqamni xalqaro formatda yozing.\n"
        "Masalan: <code>+998901234567</code>\n\n"
        "⚠️ Bir xil telefon raqami qayta ishlatilmaydi."
    )

    await callback.answer()


@dp.message(UserStates.waiting_phone)
async def phone_received(
    message: Message,
    state: FSMContext
):

    phone = normalize_phone(message.text or "")

    if not valid_phone(phone):

        await message.answer(
            "❌ Telefon raqami noto‘g‘ri.\n\n"
            "Masalan:\n"
            "<code>+998901234567</code>"
        )
        return

    with closing(get_db()) as db:

        used = db.execute(
            "SELECT id FROM used_phones WHERE phone=?",
            (phone,)
        ).fetchone()

        if used:

            await state.clear()

            await message.answer(
                "❌ Bu telefon raqami avval yuborilgan.",
                reply_markup=user_keyboard()
            )
            return

        db.execute("""
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
            VOTE_REWARD
        ))

        db.commit()

        vote_id = db.execute(
            "SELECT last_insert_rowid()"
        ).fetchone()[0]

    await state.clear()

    await message.answer(
        "✅ <b>Telefon raqamingiz qabul qilindi.</b>\n\n"
        "Admin tekshirganidan so‘ng tasdiqlangan ovoz uchun "
        f"<b>{VOTE_REWARD:,} so‘m</b> balansingizga qo‘shiladi.",
        reply_markup=user_keyboard()
    )

    # Adminlarga yuborish
    user = message.from_user

    admin_text = (
        "📱 <b>Yangi telefon ovozi!</b>\n\n"
        f"👤 Ism: {escape(user.first_name or '')}\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"👤 Username: @{escape(user.username or 'yo‘q')}\n"
        f"📞 Telefon: <code>{escape(phone)}</code>\n"
        f"💰 Mukofot: {VOTE_REWARD:,} so‘m\n"
        f"🆔 Ovoz ID: <code>{vote_id}</code>"
    )

    for admin_id in ADMIN_IDS:

        try:

            await bot.send_message(
                admin_id,
                admin_text,
                reply_markup=vote_admin_keyboard(vote_id)
            )

        except Exception:
            logger.exception("Admin notification error")


# ============================================================
# ADMIN — OVOZNI TASDIQLASH
# ============================================================

@dp.callback_query(
    F.data.startswith("vote_approve:")
)
async def approve_vote(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo‘q!", show_alert=True)
        return

    vote_id = int(callback.data.split(":")[1])

    with closing(get_db()) as db:

        vote = db.execute(
            "SELECT * FROM votes WHERE id=?",
            (vote_id,)
        ).fetchone()

        if not vote:
            await callback.answer(
                "Ovoz topilmadi.",
                show_alert=True
            )
            return

        if vote["status"] != "pending":
            await callback.answer(
                "Bu ovoz allaqachon ko‘rib chiqilgan.",
                show_alert=True
            )
            return

        phone = vote["phone"]

        used = db.execute(
            "SELECT id FROM used_phones WHERE phone=?",
            (phone,)
        ).fetchone()

        if used:

            db.execute("""
                UPDATE votes
                SET status='rejected'
                WHERE id=?
            """, (vote_id,))

            db.commit()

            await callback.message.edit_reply_markup(
                reply_markup=None
            )

            await callback.message.answer(
                "❌ Bu telefon raqami oldin ishlatilgan."
            )

            await callback.answer()
            return

        db.execute("""
            UPDATE votes
            SET status='approved',
                reward=?
            WHERE id=?
        """, (
            VOTE_REWARD,
            vote_id
        ))

        db.execute("""
            INSERT INTO used_phones(phone, user_id)
            VALUES(?,?)
        """, (
            phone,
            vote["user_id"]
        ))

        db.execute("""
            UPDATE users
            SET balance=balance+?
            WHERE user_id=?
        """, (
            VOTE_REWARD,
            vote["user_id"]
        ))

        db.commit()

    await callback.message.edit_reply_markup(
        reply_markup=None
    )

    await callback.message.answer(
        f"✅ Ovoz tasdiqlandi.\n"
        f"💰 {VOTE_REWARD:,} so‘m balansga qo‘shildi."
    )

    try:

        await bot.send_message(
            vote["user_id"],
            f"🎉 <b>Ovozingiz tasdiqlandi!</b>\n\n"
            f"💰 Balansingizga "
            f"<b>{VOTE_REWARD:,} so‘m</b> qo‘shildi."
        )

    except Exception:
        pass

    await callback.answer("Tasdiqlandi")


# ============================================================
# ADMIN — OVOZNI RAD ETISH
# ============================================================

@dp.callback_query(
    F.data.startswith("vote_reject:")
)
async def reject_vote(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo‘q!", show_alert=True)
        return

    vote_id = int(callback.data.split(":")[1])

    with closing(get_db()) as db:

        vote = db.execute(
            "SELECT * FROM votes WHERE id=?",
            (vote_id,)
        ).fetchone()

        if not vote:
            await callback.answer(
                "Topilmadi.",
                show_alert=True
            )
            return

        db.execute("""
            UPDATE votes
            SET status='rejected'
            WHERE id=?
        """, (vote_id,))

        db.commit()

    await callback.message.edit_reply_markup(
        reply_markup=None
    )

    try:

        await bot.send_message(
            vote["user_id"],
            "❌ <b>Ovoz tasdiqlanmadi.</b>\n\n"
            "Qo‘shimcha ma’lumot uchun admin bilan bog‘lanishingiz mumkin."
        )

    except Exception:
        pass

    await callback.answer("Rad etildi")


# ============================================================
# BALANS
# ============================================================

@dp.message(F.text == "💰 Balans")
async def balance_handler(message: Message):

    user = get_user(message.from_user.id)

    balance = user["balance"] if user else 0

    await message.answer(
        "💰 <b>Sizning balansingiz</b>\n\n"
        f"💵 Balans: <b>{balance:,} so‘m</b>\n\n"
        "💳 <b>Balansdagi pulni yechish uchun "
        "balansda kamida 30 000 so‘m bo‘lishi kerak.</b>\n\n"
        "Balansni to‘ldirish uchun 🗳 <b>Ovoz berish</b> "
        "bo‘limidan foydalaning.\n\n"
        f"🗳 Har bir tasdiqlangan telefon ovozi uchun "
        f"<b>{VOTE_REWARD:,} so‘m</b> hisoblanadi.\n"
        f"👥 Har bir haqiqiy taklif qilingan do‘st uchun "
        f"<b>{REFERRAL_REWARD:,} so‘m</b> beriladi."
    )


# ============================================================
# REFERAL
# ============================================================

@dp.message(F.text == "👥 Do‘stlarni taklif qilish")
async def referral_handler(message: Message):

    me = await bot.get_me()

    link = (
        f"https://t.me/{me.username}"
        f"?start=ref_{message.from_user.id}"
    )

    user = get_user(message.from_user.id)

    referrals = user["referrals"] if user else 0

    earned = referrals * REFERRAL_REWARD

    await message.answer(
        "👥 <b>Do‘stlarni taklif qilish</b>\n\n"
        "Do‘stlaringizni quyidagi havola orqali taklif qiling:\n\n"
        f"<code>{link}</code>\n\n"
        f"👥 Taklif qilinganlar: <b>{referrals}</b>\n"
        f"💰 Referaldan olingan: <b>{earned:,} so‘m</b>\n\n"
        f"🎁 Har bir haqiqiy yangi foydalanuvchi uchun "
        f"<b>{REFERRAL_REWARD:,} so‘m</b> balansga qo‘shiladi."
    )


# ============================================================
# PUL YECHISH
# ============================================================

@dp.message(F.text == "💳 Pul yechish")
async def withdraw_handler(
    message: Message,
    state: FSMContext
):

    user = get_user(message.from_user.id)

    balance = user["balance"] if user else 0

    if balance < MIN_WITHDRAW:

        await message.answer(
            "❌ <b>Hozirgi balansingizda yetarli mablag‘ yo‘q.</b>\n\n"
            f"Pul yechish uchun kamida "
            f"<b>{MIN_WITHDRAW:,} so‘m</b> kerak.\n\n"
            "🗳 Ko‘proq ovoz berib balansingizni to‘ldiring."
        )
        return

    await state.set_state(UserStates.waiting_card)

    await message.answer(
        "💳 <b>Karta raqamingizni yuboring.</b>\n\n"
        "Masalan:\n"
        "<code>8600123456789012</code>\n\n"
        "Karta raqamingiz admin tomonidan ko‘rib chiqiladi."
    )


@dp.message(UserStates.waiting_card)
async def card_received(
    message: Message,
    state: FSMContext
):

    card = re.sub(r"\D", "", message.text or "")

    if len(card) < 12 or len(card) > 19:

        await message.answer(
            "❌ Karta raqami noto‘g‘ri.\n"
            "Karta raqamini qaytadan yuboring."
        )
        return

    user = get_user(message.from_user.id)

    if not user or user["balance"] < MIN_WITHDRAW:

        await state.clear()

        await message.answer(
            "❌ Balansingiz yetarli emas.",
            reply_markup=user_keyboard()
        )
        return

    amount = user["balance"]

    with closing(get_db()) as db:

        db.execute("""
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
            card
        ))

        withdrawal_id = db.execute(
            "SELECT last_insert_rowid()"
        ).fetchone()[0]

        db.commit()

    await state.clear()

    await message.answer(
        "✅ <b>Pul yechish arizangiz qabul qilindi.</b>\n\n"
        f"💰 Summa: <b>{amount:,} so‘m</b>\n"
        f"💳 Karta: <code>{card}</code>\n\n"
        "Admin arizani tekshiradi.",
        reply_markup=user_keyboard()
    )

    admin_text = (
        "💳 <b>Yangi pul yechish arizasi!</b>\n\n"
        f"👤 Ism: {escape(message.from_user.first_name or '')}\n"
        f"🆔 ID: <code>{message.from_user.id}</code>\n"
        f"👤 Username: @{escape(message.from_user.username or 'yo‘q')}\n"
        f"💰 Summa: <b>{amount:,} so‘m</b>\n"
        f"💳 Karta: <code>{card}</code>\n"
        f"🆔 Ariza: <code>{withdrawal_id}</code>"
    )

    for admin_id in ADMIN_IDS:

        try:

            await bot.send_message(
                admin_id,
                admin_text,
                reply_markup=withdrawal_keyboard(
                    withdrawal_id
                )
            )

        except Exception:
            logger.exception("Withdrawal admin notification error")


# ============================================================
# ADMIN — PUL TO‘LANDI
# ============================================================

@dp.callback_query(
    F.data.startswith("withdraw_paid:")
)
async def withdraw_paid(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):
        await callback.answer(
            "Ruxsat yo‘q!",
            show_alert=True
        )
        return

    withdrawal_id = int(
        callback.data.split(":")[1]
    )

    with closing(get_db()) as db:

        withdrawal = db.execute(
            "SELECT * FROM withdrawals WHERE id=?",
            (withdrawal_id,)
        ).fetchone()

        if not withdrawal:
            await callback.answer(
                "Ariza topilmadi.",
                show_alert=True
            )
            return

        if withdrawal["status"] != "pending":

            await callback.answer(
                "Bu ariza allaqachon ko‘rib chiqilgan.",
                show_alert=True
            )
            return

        user = db.execute(
            "SELECT * FROM users WHERE user_id=?",
            (withdrawal["user_id"],)
        ).fetchone()

        if not user or user["balance"] < withdrawal["amount"]:

            await callback.answer(
                "Foydalanuvchi balansida yetarli mablag‘ yo‘q.",
                show_alert=True
            )
            return

        db.execute("""
            UPDATE users
            SET balance=balance-?
            WHERE user_id=?
        """, (
            withdrawal["amount"],
            withdrawal["user_id"]
        ))

        db.execute("""
            UPDATE withdrawals
            SET status='paid'
            WHERE id=?
        """, (withdrawal_id,))

        db.commit()

    await callback.message.edit_reply_markup(
        reply_markup=None
    )

    await callback.message.answer(
        "✅ Pul to‘lovi tasdiqlandi."
    )

    try:

        await bot.send_message(
            withdrawal["user_id"],
            "✅ <b>Pul yechish arizangiz to‘landi.</b>\n\n"
            f"💰 Summa: <b>{withdrawal['amount']:,} so‘m</b>"
        )

    except Exception:
        pass

    await callback.answer("To‘landi")


# ============================================================
# ADMIN — PULNI RAD ETISH
# ============================================================

@dp.callback_query(
    F.data.startswith("withdraw_reject:")
)
async def withdraw_reject(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):
        await callback.answer(
            "Ruxsat yo‘q!",
            show_alert=True
        )
        return

    withdrawal_id = int(
        callback.data.split(":")[1]
    )

    with closing(get_db()) as db:

        withdrawal = db.execute(
            "SELECT * FROM withdrawals WHERE id=?",
            (withdrawal_id,)
        ).fetchone()

        if not withdrawal:
            await callback.answer(
                "Ariza topilmadi.",
                show_alert=True
            )
            return

        if withdrawal["status"] != "pending":

            await callback.answer(
                "Bu ariza allaqachon ko‘rib chiqilgan.",
                show_alert=True
            )
            return

        db.execute("""
            UPDATE withdrawals
            SET status='rejected'
            WHERE id=?
        """, (withdrawal_id,))

        db.commit()

    await callback.message.edit_reply_markup(
        reply_markup=None
    )

    try:

        await bot.send_message(
            withdrawal["user_id"],
            "❌ <b>Pul yechish arizangiz rad etildi.</b>\n\n"
            "Qo‘shimcha ma’lumot uchun admin bilan bog‘laning."
        )

    except Exception:
        pass

    await callback.answer("Rad etildi")


# ============================================================
# SAVOL-JAVOB
# ============================================================

@dp.message(F.text == "❓ Savol-javob")
async def question_start(
    message: Message,
    state: FSMContext
):

    await state.set_state(
        UserStates.waiting_question
    )

    await message.answer(
        "❓ <b>Savolingizni yozing.</b>\n\n"
        "Savolingiz adminlarga yuboriladi."
    )


@dp.message(UserStates.waiting_question)
async def question_received(
    message: Message,
    state: FSMContext
):

    text = message.text or ""

    if len(text.strip()) < 2:

        await message.answer(
            "❌ Savol juda qisqa."
        )
        return

    with closing(get_db()) as db:

        db.execute("""
            INSERT INTO support_messages(
                user_id,
                message,
                direction,
                status
            )
            VALUES(?,?,'user_to_admin','open')
        """, (
            message.from_user.id,
            text
        ))

        db.commit()

    await state.clear()

    await message.answer(
        "✅ Savolingiz adminga yuborildi.\n\n"
        "Admin javob berganida shu yerga keladi.",
        reply_markup=user_keyboard()
    )

    user = message.from_user

    admin_text = (
        "❓ <b>Yangi savol!</b>\n\n"
        f"👤 Ism: {escape(user.first_name or '')}\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"👤 Username: @{escape(user.username or 'yo‘q')}\n\n"
        f"💬 <b>Savol:</b>\n{escape(text)}"
    )

    for admin_id in ADMIN_IDS:

        try:

            await bot.send_message(
                admin_id,
                admin_text,
                reply_markup=close_chat_keyboard(
                    user.id
                )
            )

        except Exception:
            logger.exception("Question notification error")


# ============================================================
# ADMIN REPLY
# ============================================================

@dp.callback_query(
    F.data.startswith("reply_user:")
)
async def admin_reply_start(
    callback: CallbackQuery,
    state: FSMContext
):

    if not is_admin(callback.from_user.id):

        await callback.answer(
            "Ruxsat yo‘q!",
            show_alert=True
        )
        return

    user_id = int(
        callback.data.split(":")[1]
    )

    await state.update_data(
        reply_user_id=user_id
    )

    await state.set_state(
        AdminStates.waiting_reply
    )

    await callback.message.answer(
        f"💬 <b>Foydalanuvchiga javob yozing.</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>"
    )

    await callback.answer()


@dp.message(AdminStates.waiting_reply)
async def admin_reply_received(
    message: Message,
    state: FSMContext
):

    if not is_admin(message.from_user.id):
        return

    data = await state.get_data()

    user_id = data.get("reply_user_id")

    if not user_id:

        await state.clear()
        return

    text = message.text or ""

    try:

        await bot.send_message(
            user_id,
            "👨‍💻 <b>Admin javobi:</b>\n\n"
            f"{escape(text)}"
        )

        with closing(get_db()) as db:

            db.execute("""
                INSERT INTO support_messages(
                    user_id,
                    admin_id,
                    message,
                    direction,
                    status
                )
                VALUES(?,?,?,'admin_to_user','open')
            """, (
                user_id,
                message.from_user.id,
                text
            ))

            db.commit()

        await message.answer(
            "✅ Javob foydalanuvchiga yuborildi.",
            reply_markup=admin_keyboard()
        )

    except Exception:

        await message.answer(
            "❌ Foydalanuvchiga xabar yuborilmadi."
        )

    await state.clear()


# ============================================================
# ADMIN — CHATNI YOPISH
# ============================================================

@dp.callback_query(
    F.data.startswith("close_chat:")
)
async def close_chat(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):

        await callback.answer(
            "Ruxsat yo‘q!",
            show_alert=True
        )
        return

    user_id = int(
        callback.data.split(":")[1]
    )

    with closing(get_db()) as db:

        db.execute("""
            UPDATE support_messages
            SET status='closed'
            WHERE user_id=?
              AND status='open'
        """, (user_id,))

        db.commit()

    await callback.message.answer(
        "🔒 Suhbat yopildi."
    )

    try:

        await bot.send_message(
            user_id,
            "🔒 <b>Admin suhbatni yopdi.</b>\n\n"
            "Yangi savol bo‘lsa, ❓ Savol-javob bo‘limidan "
            "yana murojaat qilishingiz mumkin."
        )

    except Exception:
        pass

    await callback.answer("Yopildi")


# ============================================================
# FOYDALANUVCHI ADMIN BILAN BOG‘LANISH
# ============================================================

@dp.message(F.text == "👨‍💻 Admin bilan bog‘lanish")
async def admin_contact_handler(message: Message):

    contact = get_setting(
        "admin_contact",
        ""
    )

    if not contact:

        await message.answer(
            "ℹ️ <b>Hozircha admin qo‘shilmagan.</b>\n\n"
            "Yoki hozir barcha adminlar band."
        )
        return

    await message.answer(
        "👨‍💻 <b>Admin bilan bog‘lanish:</b>\n\n"
        f"{escape(contact)}"
    )


# ============================================================
# ADMIN PANEL
# ============================================================

@dp.message(Command("admin"))
async def admin_command(message: Message):

    if not is_admin(message.from_user.id):

        await message.answer(
            "❌ Siz admin emassiz."
        )
        return

    await message.answer(
        "👨‍💼 <b>Admin panel</b>\n\n"
        "Kerakli bo‘limni tanlang:",
        reply_markup=admin_keyboard()
    )


# ============================================================
# ADMIN STATISTIKA
# ============================================================

@dp.message(F.text == "📊 Statistika")
async def statistics_handler(message: Message):

    if not is_admin(message.from_user.id):
        return

    with closing(get_db()) as db:

        users = db.execute(
            "SELECT COUNT(*) c FROM users"
        ).fetchone()["c"]

        votes = db.execute(
            "SELECT COUNT(*) c FROM votes"
        ).fetchone()["c"]

        approved = db.execute("""
            SELECT COUNT(*) c
            FROM votes
            WHERE status='approved'
        """).fetchone()["c"]

        pending_votes = db.execute("""
            SELECT COUNT(*) c
            FROM votes
            WHERE status='pending'
        """).fetchone()["c"]

        referrals = db.execute(
            "SELECT COUNT(*) c FROM referrals"
        ).fetchone()["c"]

        referral_money = db.execute("""
            SELECT COALESCE(SUM(reward),0) s
            FROM referrals
        """).fetchone()["s"]

        pending_withdraw = db.execute("""
            SELECT COUNT(*) c
            FROM withdrawals
            WHERE status='pending'
        """).fetchone()["c"]

        paid_withdraw = db.execute("""
            SELECT COALESCE(SUM(amount),0) s
            FROM withdrawals
            WHERE status='paid'
        """).fetchone()["s"]

        total_balance = db.execute("""
            SELECT COALESCE(SUM(balance),0) s
            FROM users
        """).fetchone()["s"]

    await message.answer(
        "📊 <b>BOT STATISTIKASI</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{users}</b>\n\n"
        f"🗳 Jami ovozlar: <b>{votes}</b>\n"
        f"✅ Tasdiqlangan ovozlar: <b>{approved}</b>\n"
        f"⏳ Kutilayotgan ovozlar: <b>{pending_votes}</b>\n\n"
        f"👥 Jami referallar: <b>{referrals}</b>\n"
        f"💰 Referal mukofotlari: <b>{referral_money:,} so‘m</b>\n\n"
        f"💵 Foydalanuvchilar balanslari: "
        f"<b>{total_balance:,} so‘m</b>\n\n"
        f"💳 Kutilayotgan yechishlar: "
        f"<b>{pending_withdraw}</b>\n"
        f"💸 To‘langan pul: <b>{paid_withdraw:,} so‘m</b>"
    )


# ============================================================
# ADMIN USERS
# ============================================================

@dp.message(F.text == "👥 Foydalanuvchilar")
async def users_admin(message: Message):

    if not is_admin(message.from_user.id):
        return

    with closing(get_db()) as db:

        users = db.execute("""
            SELECT user_id,
                   first_name,
                   username,
                   balance,
                   referrals
            FROM users
            ORDER BY created_at DESC
            LIMIT 20
        """).fetchall()

    if not users:

        await message.answer(
            "Hozircha foydalanuvchilar yo‘q."
        )
        return

    text = "👥 <b>Oxirgi foydalanuvchilar</b>\n\n"

    for user in users:

        text += (
            f"👤 {escape(user['first_name'] or '')}\n"
            f"🆔 <code>{user['user_id']}</code>\n"
            f"👤 @{escape(user['username'] or 'yo‘q')}\n"
            f"💰 {user['balance']:,} so‘m\n"
            f"👥 Referral: {user['referrals']}\n"
            f"──────────────\n"
        )

    await message.answer(text)


# ============================================================
# ADMIN OVOZLAR
# ============================================================

@dp.message(F.text == "🗳 Ovozlar")
async def admin_votes(message: Message):

    if not is_admin(message.from_user.id):
        return

    with closing(get_db()) as db:

        rows = db.execute("""
            SELECT
                v.*,
                u.first_name,
                u.username
            FROM votes v
            LEFT JOIN users u
                ON u.user_id=v.user_id
            ORDER BY v.id DESC
            LIMIT 30
        """).fetchall()

    if not rows:

        await message.answer(
            "🗳 Hozircha ovozlar yo‘q."
        )
        return

    text = "🗳 <b>Ovozlar</b>\n\n"

    for row in rows:

        text += (
            f"🆔 {row['id']}\n"
            f"👤 {escape(row['first_name'] or '')}\n"
            f"📱 {escape(row['phone'] or '-')}\n"
            f"📌 Tur: {row['vote_type']}\n"
            f"📊 Holat: {row['status']}\n"
            f"💰 {row['reward']:,} so‘m\n"
            f"────────────\n"
        )

    await message.answer(text)


# ============================================================
# ADMIN TELEFON OVOZLARI
# ============================================================

@dp.message(F.text == "📱 Telefon ovozlari")
async def admin_phone_votes(message: Message):

    if not is_admin(message.from_user.id):
        return

    with closing(get_db()) as db:

        rows = db.execute("""
            SELECT
                v.*,
                u.first_name,
                u.username
            FROM votes v
            LEFT JOIN users u
                ON u.user_id=v.user_id
            WHERE v.vote_type='phone'
            ORDER BY v.id DESC
            LIMIT 30
        """).fetchall()

    if not rows:

        await message.answer(
            "📱 Telefon orqali ovozlar mavjud emas."
        )
        return

    for row in rows:

        text = (
            "📱 <b>Telefon ovozi</b>\n\n"
            f"🆔 Ovoz: <code>{row['id']}</code>\n"
            f"👤 Ism: {escape(row['first_name'] or '')}\n"
            f"🆔 User ID: <code>{row['user_id']}</code>\n"
            f"📞 Telefon: <code>{escape(row['phone'] or '')}</code>\n"
            f"📊 Holat: <b>{row['status']}</b>\n"
            f"💰 Mukofot: {row['reward']:,} so‘m"
        )

        keyboard = None

        if row["status"] == "pending":

            keyboard = vote_admin_keyboard(
                row["id"]
            )

        await message.answer(
            text,
            reply_markup=keyboard
        )


# ============================================================
# ADMIN REFERALLAR
# ============================================================

@dp.message(F.text == "👥 Referallar")
async def admin_referrals(message: Message):

    if not is_admin(message.from_user.id):
        return

    with closing(get_db()) as db:

        rows = db.execute("""
            SELECT
                r.*,
                u.first_name,
                u.username
            FROM referrals r
            LEFT JOIN users u
                ON u.user_id=r.inviter_id
            ORDER BY r.id DESC
            LIMIT 30
        """).fetchall()

    if not rows:

        await message.answer(
            "👥 Hozircha referallar yo‘q."
        )
        return

    text = "👥 <b>Referallar</b>\n\n"

    for row in rows:

        text += (
            f"👤 Taklif qiluvchi: "
            f"{escape(row['first_name'] or '')}\n"
            f"🆔 ID: <code>{row['inviter_id']}</code>\n"
            f"🎁 Mukofot: {row['reward']:,} so‘m\n"
            f"────────────\n"
        )

    await message.answer(text)


# ============================================================
# ADMIN PUL YECHISHLAR
# ============================================================

@dp.message(F.text == "💳 Pul yechishlar")
async def admin_withdrawals(message: Message):

    if not is_admin(message.from_user.id):
        return

    with closing(get_db()) as db:

        rows = db.execute("""
            SELECT
                w.*,
                u.first_name,
                u.username
            FROM withdrawals w
            LEFT JOIN users u
                ON u.user_id=w.user_id
            ORDER BY w.id DESC
            LIMIT 30
        """).fetchall()

    if not rows:

        await message.answer(
            "💳 Pul yechish arizalari yo‘q."
        )
        return

    for row in rows:

        text = (
            "💳 <b>Pul yechish arizasi</b>\n\n"
            f"🆔 Ariza: <code>{row['id']}</code>\n"
            f"👤 {escape(row['first_name'] or '')}\n"
            f"🆔 User ID: <code>{row['user_id']}</code>\n"
            f"💰 Summa: <b>{row['amount']:,} so‘m</b>\n"
            f"💳 Karta: <code>{row['card_number']}</code>\n"
            f"📊 Holat: <b>{row['status']}</b>"
        )

        keyboard = None

        if row["status"] == "pending":

            keyboard = withdrawal_keyboard(
                row["id"]
            )

        await message.answer(
            text,
            reply_markup=keyboard
        )


# ============================================================
# ADMIN SAVOLLAR
# ============================================================

@dp.message(F.text == "❓ Savollar")
async def admin_questions(message: Message):

    if not is_admin(message.from_user.id):
        return

    with closing(get_db()) as db:

        rows = db.execute("""
            SELECT
                s.*,
               