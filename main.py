# ============================================================
# MAIN.PY — TELEGRAM BOT
# AIROGRAM 3.x
# BARCHA FUNKSIYALAR BITTA FAYLDA
# ============================================================

import asyncio
import logging
import os
import re
import sqlite3
from contextlib import closing
from html import escape

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage


# ============================================================
# 1. BOT TOKEN
# ============================================================

# BOT TOKENNI SHU YERGA QO'YING
BOT_TOKEN = "8615736731:AAF7LGgYsKCq_JjV9qFPmFV6psTAS4mlQ_g"


# ============================================================
# 2. ADMIN ID
# ============================================================

# ADMIN TELEGRAM ID LARINI SHU YERGA YOZING
# Masalan:
# ADMIN_IDS = {7998053914}
#
# Bir nechta admin:
# ADMIN_IDS = {7998053915, }

ADMIN_IDS = {
    7998053914
}


# ============================================================
# 3. SOZLAMALAR
# ============================================================

DB_NAME = "bot.db"

VOTE_AMOUNT = 30000
REFERRAL_AMOUNT = 10000
MIN_WITHDRAW = 30000


# ============================================================
# 4. LOG
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)


# ============================================================
# 5. BOT
# ============================================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ============================================================
# 6. DATABASE
# ============================================================

def db():
    return sqlite3.connect(DB_NAME)


def init_db():
    with closing(db()) as conn:
        cur = conn.cursor()

        # USERS
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT DEFAULT '',
            first_name TEXT DEFAULT '',
            language TEXT DEFAULT 'uz',
            phone TEXT DEFAULT '',
            balance INTEGER DEFAULT 0,
            referral_balance INTEGER DEFAULT 0,
            referral_count INTEGER DEFAULT 0,
            referred_by INTEGER DEFAULT 0,
            total_votes INTEGER DEFAULT 0,
            total_referrals INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # PROJECTS
        cur.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            active INTEGER DEFAULT 1,
            clicks INTEGER DEFAULT 0,
            votes INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # VOTES
        cur.execute("""
        CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            project_id INTEGER,
            vote_type TEXT,
            phone TEXT DEFAULT '',
            amount INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # WITHDRAWALS
        cur.execute("""
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            card_number TEXT,
            amount INTEGER,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # QUESTIONS
        cur.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            status TEXT DEFAULT 'open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # CONTACT SETTINGS
        cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT DEFAULT ''
        )
        """)

        # USER SESSIONS
        cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            user_id INTEGER PRIMARY KEY,
            mode TEXT DEFAULT '',
            admin_id INTEGER DEFAULT 0
        )
        """)

        conn.commit()


# ============================================================
# 7. SETTINGS
# ============================================================

def get_setting(key, default=""):
    with closing(db()) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT value FROM settings WHERE key=?",
            (key,)
        )
        row = cur.fetchone()

    if row:
        return row[0]

    return default


def set_setting(key, value):
    with closing(db()) as conn:
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO settings(key, value)
        VALUES (?, ?)
        ON CONFLICT(key)
        DO UPDATE SET value=excluded.value
        """, (key, value))
        conn.commit()


# ============================================================
# 8. ADMIN TEKSHIRISH
# ============================================================

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ============================================================
# 9. USER SAQLASH
# ============================================================

def save_user(message: Message, referred_by=0):
    user = message.from_user

    with closing(db()) as conn:
        cur = conn.cursor()

        cur.execute(
            "SELECT user_id FROM users WHERE user_id=?",
            (user.id,)
        )

        exists = cur.fetchone()

        if not exists:

            valid_ref = 0

            if referred_by and referred_by != user.id:
                cur.execute(
                    "SELECT user_id FROM users WHERE user_id=?",
                    (referred_by,)
                )

                if cur.fetchone():
                    valid_ref = referred_by

            cur.execute("""
            INSERT INTO users(
                user_id,
                username,
                first_name,
                referred_by
            )
            VALUES (?, ?, ?, ?)
            """, (
                user.id,
                user.username or "",
                user.first_name or "",
                valid_ref
            ))

            # REFERRAL BONUS
            if valid_ref:
                cur.execute("""
                UPDATE users
                SET
                    balance = balance + ?,
                    referral_balance = referral_balance + ?,
                    referral_count = referral_count + 1,
                    total_referrals = total_referrals + 1
                WHERE user_id=?
                """, (
                    REFERRAL_AMOUNT,
                    REFERRAL_AMOUNT,
                    valid_ref
                ))

        else:
            cur.execute("""
            UPDATE users
            SET username=?, first_name=?
            WHERE user_id=?
            """, (
                user.username or "",
                user.first_name or "",
                user.id
            ))

        conn.commit()


# ============================================================
# 10. BALANS
# ============================================================

def get_balance(user_id):
    with closing(db()) as conn:
        cur = conn.cursor()

        cur.execute(
            "SELECT balance FROM users WHERE user_id=?",
            (user_id,)
        )

        row = cur.fetchone()

    return row[0] if row else 0


def add_balance(user_id, amount):
    with closing(db()) as conn:
        cur = conn.cursor()

        cur.execute("""
        UPDATE users
        SET balance = balance + ?
        WHERE user_id=?
        """, (amount, user_id))

        conn.commit()


# ============================================================
# 11. DOIMIY FOYDALANUVCHI MENYUSI
# ============================================================

def user_keyboard():

    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🗳 Ovoz berish"),
                KeyboardButton(text="💰 Balans"),
            ],
            [
                KeyboardButton(text="👥 Do‘stlarni taklif qilish"),
                KeyboardButton(text="💸 Pul yechish"),
            ],
            [
                KeyboardButton(text="❓ Savol-javob"),
                KeyboardButton(text="📞 Admin bilan bog‘lanish"),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True
    )


# ============================================================
# 12. ADMIN MENYU
# ============================================================

def admin_keyboard():

    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📊 Statistika"),
                KeyboardButton(text="➕ Loyiha qo‘shish"),
            ],
            [
                KeyboardButton(text="📋 Loyihalar"),
                KeyboardButton(text="🗑 Loyiha o‘chirish"),
            ],
            [
                KeyboardButton(text="📱 Telefon ovozlari"),
                KeyboardButton(text="💸 Pul yechishlar"),
            ],
            [
                KeyboardButton(text="❓ Savollar"),
                KeyboardButton(text="📞 Admin aloqa"),
            ],
            [
                KeyboardButton(text="📢 Reklama yuborish"),
                KeyboardButton(text="👥 Foydalanuvchilar"),
            ],
            [
                KeyboardButton(text="⬅️ Foydalanuvchi menyusi"),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True
    )


# ============================================================
# 13. FSM HOLATLAR
# ============================================================

class AddProjectState(StatesGroup):
    name = State()
    url = State()


class QuestionState(StatesGroup):
    waiting = State()


class VotePhoneState(StatesGroup):
    waiting = State()


class WithdrawState(StatesGroup):
    waiting_card = State()


class AdminContactState(StatesGroup):
    waiting_phone = State()
    waiting_telegram = State()


class BroadcastState(StatesGroup):
    waiting_message = State()


class AdminReplyState(StatesGroup):
    waiting_message = State()


class AdminPhoneReplyState(StatesGroup):
    waiting_message = State()


# ============================================================
# 14. START
# ============================================================

@dp.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):

    await state.clear()

    referred_by = 0

    args = message.text.split(maxsplit=1)

    if len(args) > 1:
        ref = args[1]

        if ref.startswith("ref_"):
            try:
                referred_by = int(ref.replace("ref_", ""))
            except ValueError:
                referred_by = 0

    save_user(message, referred_by)

    if is_admin(message.from_user.id):

        await message.answer(
            "👋 Assalomu alaykum!\n\n"
            "Admin panelga xush kelibsiz.",
            reply_markup=admin_keyboard()
        )

    else:

        await message.answer(
            "👋 Assalomu alaykum!\n\n"
            "Botga xush kelibsiz.\n"
            "Kerakli bo‘limni pastdagi menyudan tanlang.",
            reply_markup=user_keyboard()
        )


# ============================================================
# 15. ADMIN PANELGA QAYTISH
# ============================================================

@dp.message(F.text == "⬅️ Foydalanuvchi menyusi")
async def back_user_menu(message: Message, state: FSMContext):

    await state.clear()

    await message.answer(
        "Foydalanuvchi menyusi:",
        reply_markup=user_keyboard()
    )


# ============================================================
# 16. OVOZ BERISH
# ============================================================

@dp.message(F.text == "🗳 Ovoz berish")
async def vote_menu(message: Message):

    with closing(db()) as conn:
        cur = conn.cursor()

        cur.execute("""
        SELECT id, name, url
        FROM projects
        WHERE active=1
        ORDER BY id DESC
        """)

        projects = cur.fetchall()

    if not projects:

        await message.answer(
            "❌ Hozircha ovoz berish uchun loyiha mavjud emas.",
            reply_markup=user_keyboard()
        )
        return

    keyboard = []

    for project_id, name, url in projects:

        keyboard.append([
            InlineKeyboardButton(
                text=f"🗳 {name}",
                callback_data=f"project_{project_id}"
            )
        ])

    await message.answer(
        "🗳 Ovoz berish uchun loyihani tanlang:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=keyboard
        )
    )


# ============================================================
# 17. LOYIHA TANLASH
# ============================================================

@dp.callback_query(F.data.startswith("project_"))
async def project_selected(callback: CallbackQuery):

    try:
        project_id = int(
            callback.data.replace("project_", "")
        )
    except ValueError:
        await callback.answer()
        return

    with closing(db()) as conn:
        cur = conn.cursor()

        cur.execute("""
        SELECT name, url
        FROM projects
        WHERE id=? AND active=1
        """, (project_id,))

        project = cur.fetchone()

        if project:
            cur.execute("""
            UPDATE projects
            SET clicks=clicks+1
            WHERE id=?
            """, (project_id,))

        conn.commit()

    if not project:

        await callback.answer(
            "Loyiha topilmadi.",
            show_alert=True
        )
        return

    name, url = project

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔗 Havola orqali",
                    url=url
                )
            ],
            [
                InlineKeyboardButton(
                    text="📱 Telefon raqami orqali",
                    callback_data=f"phonevote_{project_id}"
                )
            ]
        ]
    )

    await callback.message.answer(
        f"🗳 <b>{escape(name)}</b>\n\n"
        "Ovoz berish usulini tanlang:",
        reply_markup=keyboard
    )

    await callback.answer()


# ============================================================
# 18. TELEFON ORQALI OVOZ
# ============================================================

@dp.callback_query(F.data.startswith("phonevote_"))
async def phone_vote_start(
    callback: CallbackQuery,
    state: FSMContext
):

    try:
        project_id = int(
            callback.data.replace("phonevote_", "")
        )
    except ValueError:
        await callback.answer()
        return

    await state.update_data(project_id=project_id)

    await state.set_state(VotePhoneState.waiting)

    await callback.message.answer(
        "📱 Ovoz berish uchun telefon raqamingizni yozing.\n\n"
        "Masalan:\n"
        "<code>+998901234567</code>\n\n"
        "Telefon raqamingiz adminlarga yuboriladi."
    )

    await callback.answer()


# ============================================================
# 19. TELEFON RAQAMINI QABUL QILISH
# ============================================================

@dp.message(VotePhoneState.waiting)
async def receive_vote_phone(
    message: Message,
    state: FSMContext
):

    phone = message.text.strip()

    clean_phone = re.sub(r"[^\d+]", "", phone)

    if len(re.sub(r"\D", "", clean_phone)) < 7:

        await message.answer(
            "❌ Telefon raqami noto‘g‘ri.\n"
            "Iltimos, telefon raqamingizni qayta yuboring."
        )
        return

    data = await state.get_data()

    project_id = data.get("project_id")

    user_id = message.from_user.id

    # Telefonni userga saqlash
    with closing(db()) as conn:

        cur = conn.cursor()

        cur.execute("""
        UPDATE users
        SET phone=?
        WHERE user_id=?
        """, (
            clean_phone,
            user_id
        ))

        cur.execute("""
        SELECT name
        FROM projects
        WHERE id=?
        """, (project_id,))

        project = cur.fetchone()

        cur.execute("""
        INSERT INTO votes(
            user_id,
            project_id,
            vote_type,
            phone,
            amount
        )
        VALUES (?, ?, ?, ?, ?)
        """, (
            user_id,
            project_id,
            "phone",
            clean_phone,
            VOTE_AMOUNT
        ))

        cur.execute("""
        UPDATE projects
        SET votes=votes+1
        WHERE id=?
        """, (project_id,))

        cur.execute("""
        UPDATE users
        SET
            balance=balance+?,
            total_votes=total_votes+1
        WHERE user_id=?
        """, (
            VOTE_AMOUNT,
            user_id
        ))

        conn.commit()

    await state.clear()

    await message.answer(
        "✅ Telefon raqamingiz qabul qilindi.\n\n"
        f"💰 Balansingizga {VOTE_AMOUNT:,} so‘m qo‘shildi.\n"
        f"💰 Joriy balans: {get_balance(user_id):,} so‘m",
        reply_markup=user_keyboard()
    )

    # ADMINGA XABAR
    user = message.from_user

    admin_text = (
        "📱 <b>YANGI TELEFON OVOZI</b>\n\n"
        f"👤 Ism: {escape(user.first_name or '')}\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"👤 Username: @{escape(user.username)}\n"
        f"📱 Telefon: <code>{escape(clean_phone)}</code>\n"
        f"🗳 Loyiha: {escape(project[0] if project else 'Noma’lum')}\n"
        f"💰 Hisoblangan summa: {VOTE_AMOUNT:,} so‘m"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 Javob berish",
                    callback_data=f"replyphone_{user.id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔒 Suhbatni yopish",
                    callback_data=f"closechat_{user.id}"
                )
            ]
        ]
    )

    for admin_id in ADMIN_IDS:

        try:

            await bot.send_message(
                admin_id,
                admin_text,
                reply_markup=keyboard
            )

        except Exception as e:
            logger.warning(
                "Admin xabariga xato: %s",
                e
            )


# ============================================================
# 20. BALANS
# ============================================================

@dp.message(F.text == "💰 Balans")
async def balance_handler(message: Message):

    balance = get_balance(message.from_user.id)

    await message.answer(
        "💰 <b>BALANS</b>\n\n"
        f"Joriy balansingiz: <b>{balance:,} so‘m</b>\n\n"
        "💸 BALANSDAGI PULNI YECHISH UCHUN "
        "BALANSDA KAMIDA 30 000 SO‘M BO‘LISHI KERAK.\n\n"
        "🗳 Balansni to‘ldirish uchun ovoz bering.\n"
        f"Har bir qabul qilingan telefon ovozi uchun "
        f"<b>{VOTE_AMOUNT:,} so‘m</b> hisoblanadi.",
        reply_markup=user_keyboard()
    )


# ============================================================
# 21. REFERRAL
# ============================================================

@dp.message(F.text == "👥 Do‘stlarni taklif qilish")
async def referral_handler(message: Message):

    me = await bot.get_me()

    link = (
        f"https://t.me/{me.username}"
        f"?start=ref_{message.from_user.id}"
    )

    with closing(db()) as conn:
        cur = conn.cursor()

        cur.execute("""
        SELECT referral_count, referral_balance
        FROM users
        WHERE user_id=?
        """, (message.from_user.id,))

        row = cur.fetchone()

    count = row[0] if row else 0
    earned = row[1] if row else 0

    await message.answer(
        "👥 <b>DO‘STLARNI TAKLIF QILISH</b>\n\n"
        "Quyidagi havolani do‘stlaringizga yuboring:\n\n"
        f"<code>{escape(link)}</code>\n\n"
        f"👤 Taklif qilgan do‘stlaringiz: <b>{count}</b>\n"
        f"💰 Referral orqali topilgan: <b>{earned:,} so‘m</b>\n\n"
        f"🎁 Har bir yangi taklif uchun "
        f"<b>{REFERRAL_AMOUNT:,} so‘m</b> balansga qo‘shiladi.",
        reply_markup=user_keyboard()
    )


# ============================================================
# 22. PUL YECHISH
# ============================================================

@dp.message(F.text == "💸 Pul yechish")
async def withdraw_handler(
    message: Message,
    state: FSMContext
):

    balance = get_balance(message.from_user.id)

    if balance < MIN_WITHDRAW:

        await message.answer(
            "❌ <b>Balansingizda yetarli mablag‘ yo‘q.</b>\n\n"
            f"Minimal yechish summasi: <b>{MIN_WITHDRAW:,} so‘m</b>\n"
            f"Sizning balansingiz: <b>{balance:,} so‘m</b>\n\n"
            "🗳 Ko‘proq ovoz berib balansingizni to‘ldiring.",
            reply_markup=user_keyboard()
        )
        return

    await state.set_state(
        WithdrawState.waiting_card
    )

    await message.answer(
        "💳 Pul yechish uchun karta raqamingizni yuboring.\n\n"
        "Masalan:\n"
        "<code>8600123456789012</code>"
    )


# ============================================================
# 23. KARTA QABUL QILISH
# ============================================================

@dp.message(WithdrawState.waiting_card)
async def receive_card(
    message: Message,
    state: FSMContext
):

    card = re.sub(
        r"[^\d]",
        "",
        message.text or ""
    )

    if len(card) < 12 or len(card) > 19:

        await message.answer(
            "❌ Karta raqami noto‘g‘ri.\n"
            "Iltimos, karta raqamini qayta yuboring."
        )
        return

    user_id = message.from_user.id

    balance = get_balance(user_id)

    if balance < MIN_WITHDRAW:

        await state.clear()

        await message.answer(
            "❌ Balansingiz yetarli emas.",
            reply_markup=user_keyboard()
        )
        return

    with closing(db()) as conn:

        cur = conn.cursor()

        cur.execute("""
        INSERT INTO withdrawals(
            user_id,
            card_number,
            amount
        )
        VALUES (?, ?, ?)
        """, (
            user_id,
            card,
            balance
        ))

        conn.commit()

    await state.clear()

    await message.answer(
        "✅ Pul yechish so‘rovingiz adminlarga yuborildi.\n\n"
        f"💰 So‘ralgan summa: <b>{balance:,} so‘m</b>\n"
        "💳 Karta raqami qabul qilindi.",
        reply_markup=user_keyboard()
    )

    user = message.from_user

    admin_text = (
        "💸 <b>YANGI PUL YECHISH SO‘ROVI</b>\n\n"
        f"👤 Ism: {escape(user.first_name or '')}\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"👤 Username: @{escape(user.username or '')}\n"
        f"💰 Balans: <b>{balance:,} so‘m</b>\n"
        f"💳 Karta: <code>{escape(card)}</code>"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Tasdiqlash",
                    callback_data=f"withdraw_ok_{user.id}"
                ),
                InlineKeyboardButton(
                    text="❌ Rad etish",
                    callback_data=f"withdraw_no_{user.id}"
                )
            ]
        ]
    )

    for admin_id in ADMIN_IDS:

        try:

            await bot.send_message(
                admin_id,
                admin_text,
                reply_markup=keyboard
            )

        except Exception as e:
            logger.warning(
                "Withdraw admin xatosi: %s",
                e
            )


# ============================================================
# 24. SAVOL-JAVOB
# ============================================================

@dp.message(F.text == "❓ Savol-javob")
async def question_start(
    message: Message,
    state: FSMContext
):

    await state.set_state(
        QuestionState.waiting
    )

    await message.answer(
        "❓ Savolingizni yozing.\n\n"
        "Savolingiz adminlarga yuboriladi."
    )


# ============================================================
# 25. SAVOLNI QABUL QILISH
# ============================================================

@dp.message(QuestionState.waiting)
async def receive_question(
    message: Message,
    state: FSMContext
):

    text = message.text or ""

    if not text.strip():

        await message.answer(
            "Iltimos, savolingizni matn ko‘rinishida yozing."
        )
        return

    user = message.from_user

    with closing(db()) as conn:

        cur = conn.cursor()

        cur.execute("""
        INSERT INTO questions(user_id)
        VALUES (?)
        """, (user.id,))

        conn.commit()

    await state.clear()

    await message.answer(
        "✅ Savolingiz adminlarga yuborildi.\n\n"
        "Admin javobini kuting.",
        reply_markup=user_keyboard()
    )

    admin_text = (
        "❓ <b>YANGI SAVOL</b>\n\n"
        f"👤 Ism: {escape(user.first_name or '')}\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"👤 Username: @{escape(user.username or '')}\n\n"
        f"💬 Savol:\n{escape(text)}"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 Javob berish",
                    callback_data=f"replyquestion_{user.id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔒 Suhbatni yopish",
                    callback_data=f"closechat_{user.id}"
                )
            ]
        ]
    )

    for admin_id in ADMIN_IDS:

        try:

            await bot.send_message(
                admin_id,
                admin_text,
                reply_markup=keyboard
            )

        except Exception as e:
            logger.warning(
                "Savol yuborish xatosi: %s",
                e
            )


# ============================================================
# 26. ADMIN BILAN BOG‘LANISH
# ============================================================

@dp.message(F.text == "📞 Admin bilan bog‘lanish")
async def contact_admin(message: Message):

    phone = get_setting(
        "admin_phone",
        ""
    )

    telegram = get_setting(
        "admin_telegram",
        ""
    )

    no_admin = get_setting(
        "admin_unavailable",
        ""
    )

    if no_admin:

        await message.answer(
            no_admin,
            reply_markup=user_keyboard()
        )
        return

    text = "📞 <b>Admin bilan bog‘lanish</b>\n\n"

    if phone:
        text += f"📱 Telefon: <b>{escape(phone)}</b>\n"

    if telegram:
        text += f"💬 Telegram: <b>{escape(telegram)}</b>\n"

    if not phone and not telegram:

        text += (
            "Hozircha admin aloqa ma’lumotlari "
            "qo‘shilmagan."
        )

    await message.answer(
        text,
        reply_markup=user_keyboard()
    )


# ============================================================
# 27. ADMIN — STATISTIKA
# ============================================================

@dp.message(F.text == "📊 Statistika")
async def statistics_handler(message: Message):

    if not is_admin(message.from_user.id):
        return

    with closing(db()) as conn:

        cur = conn.cursor()

        cur.execute(
            "SELECT COUNT(*) FROM users"
        )
        users = cur.fetchone()[0]

        cur.execute(
            "SELECT COALESCE(SUM(balance),0) FROM users"
        )
        total_balance = cur.fetchone()[0]

        cur.execute(
            "SELECT COUNT(*) FROM votes"
        )
        votes = cur.fetchone()[0]

        cur.execute(
            "SELECT COUNT(*) FROM votes WHERE vote_type='phone'"
        )
        phone_votes = cur.fetchone()[0]

        cur.execute(
            "SELECT COUNT(*) FROM projects WHERE active=1"
        )
        projects = cur.fetchone()[0]

        cur.execute(
            "SELECT COUNT(*) FROM withdrawals WHERE status='pending'"
        )
        withdrawals = cur.fetchone()[0]

        cur.execute(
            "SELECT COUNT(*) FROM questions WHERE status='open'"
        )
        questions = cur.fetchone()[0]

        cur.execute(
            "SELECT COALESCE(SUM(amount),0) FROM votes"
        )
        vote_money = cur.fetchone()[0]

        cur.execute(
            "SELECT COALESCE(SUM(referral_balance),0) FROM users"
        )
        referral_money = cur.fetchone()[0]

    await message.answer(
        "📊 <b>BOT STATISTIKASI</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{users}</b>\n"
        f"🗳 Jami ovozlar: <b>{votes}</b>\n"
        f"📱 Telefon ovozlari: <b>{phone_votes}</b>\n"
        f"📋 Faol loyihalar: <b>{projects}</b>\n"
        f"💰 Foydalanuvchilar balanslari: <b>{total_balance:,} so‘m</b>\n"
        f"🗳 Ovozlar hisobidan: <b>{vote_money:,} so‘m</b>\n"
        f"👥 Referral hisobidan: <b>{referral_money:,} so‘m</b>\n"
        f"💸 Kutilayotgan pul yechishlar: <b>{withdrawals}</b>\n"
        f"❓ Ochiq savollar: <b>{questions}</b>",
        reply_markup=admin_keyboard()
    )


# ============================================================
# 28. ADMIN — LOYIHA QO‘SHISH
# ============================================================

@dp.message(F.text == "➕ Loyiha qo‘shish")
async def add_project_start(
    message: Message,
    state: FSMContext
):

    if not is_admin(message.from_user.id):
        return

    await state.set_state(
        AddProjectState.name
    )

    await message.answer(
        "➕ Yangi loyiha qo‘shish.\n\n"
        "Avval loyiha nomini yozing:"
    )


@dp.message(AddProjectState.name)
async def add_project_name(
    message: Message,
    state: FSMContext
):

    if not is_admin(message.from_user.id):
        return

    name = message.text.strip()

    if len(name) < 2:

        await message.answer(
            "Loyiha nomini to‘g‘ri yozing."
        )
        return

    await state.update_data(
        name=name
    )

    await state.set_state(
        AddProjectState.url
    )

    await message.answer(
        "🔗 Endi loyiha havolasini yuboring.\n\n"
        "Masalan:\n"
        "https://example.com"
    )


@dp.message(AddProjectState.url)
async def add_project_url(
    message: Message,
    state: FSMContext
):

    if not is_admin(message.from_user.id):
        return

    url = message.text.strip()

    if not (
        url.startswith("http://")
        or url.startswith("https://")
    ):

        await message.answer(
            "❌ Havola http:// yoki https:// bilan boshlanishi kerak."
        )
        return

    data = await state.get_data()

    name = data.get("name", "")

    with closing(db()) as conn:

        cur = conn.cursor()

        cur.execute("""
        INSERT INTO projects(name, url)
        VALUES (?, ?)
        """, (
            name,
            url
        ))

        conn.commit()

    await state.clear()

    await message.answer(
        "✅ Loyiha muvaffaqiyatli qo‘shildi.\n\n"
        f"📋 Nomi: {escape(name)}\n"
        f"🔗 Havola: {escape(url)}",
        reply_markup=admin_keyboard()
    )


# ============================================================
# 29. ADMIN — LOYIHALAR
# ============================================================

@dp.message(F.text == "📋 Loyihalar")
async def projects_admin(message: Message):

    if not is_admin(message.from_user.id):
        return

    with closing(db()) as conn:

        cur = conn.cursor()

        cur.execute("""
        SELECT id, name, url, clicks, votes
        FROM projects
        WHERE active=1
        ORDER BY id DESC
        """)

        projects = cur.fetchall()

    if not projects:

        await message.answer(
            "📋 Hozircha loyiha yo‘q.",
            reply_markup=admin_keyboard()
        )
        return

    text = "📋 <b>LOYIHALAR</b>\n\n"

    for project_id, name, url, clicks, votes in projects:

        text += (
            f"🆔 {project_id}\n"
            f"📋 {escape(name)}\n"
            f"🔗 {escape(url)}\n"
            f"👆 Bosishlar: {clicks}\n"
            f"🗳 Ovozlar: {votes}\n\n"
        )

    await message.answer(
        text,
        reply_markup=admin_keyboard()
    )


# ============================================================
# 30. ADMIN — LOYIHA O‘CHIRISH
# ============================================================

@dp.message(F.text == "🗑 Loyiha o‘chirish")
async def delete_project_menu(message: Message):

    if not is_admin(message.from_user.id):
        return

    with closing(db()) as conn:

        cur = conn.cursor()

        cur.execute("""
        SELECT id, name
        FROM projects
        WHERE active=1
        ORDER BY id DESC
        """)

        projects = cur.fetchall()

    if not projects:

        await message.answer(
            "Loyiha yo‘q."
        )
        return

    buttons = []

    for project_id, name in projects:

        buttons.append([
            InlineKeyboardButton(
                text=f"🗑 {name}",
                callback_data=f"deleteproject_{project_id}"
            )
        ])

    await message.answer(
        "O‘chiriladigan loyihani tanlang:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )


@dp.callback_query(F.data.startswith("deleteproject_"))
async def delete_project(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    try:
        project_id = int(
            callback.data.replace(
                "deleteproject_",
                ""
            )
        )
    except ValueError:
        await callback.answer()
        return

    with closing(db()) as conn:

        cur = conn.cursor()

        cur.execute("""
        UPDATE projects
        SET active=0
        WHERE id=?
        """, (project_id,))

        conn.commit()

    await callback.message.answer(
        "✅ Loyiha o‘chirildi.",
        reply_markup=admin_keyboard()
    )

    await callback.answer()


# ============================================================
# 31. ADMIN — TELEFON OVOZLARI
# ============================================================

@dp.message(F.text == "📱 Telefon ovozlari")
async def phone_votes_admin(message: Message):

    if not is_admin(message.from_user.id):
        return

    with closing(db()) as conn:

        cur = conn.cursor()

        cur.execute("""
        SELECT
            v.id,
            v.user_id,
            v.phone,
            v.amount,
            p.name,
            v.created_at
        FROM votes v
        LEFT JOIN projects p
            ON p.id=v.project_id
        WHERE v.vote_type='phone'
        ORDER BY v.id DESC
        LIMIT 50
        """)

        rows = cur.fetchall()

    if not rows:

        await message.answer(
            "📱 Hozircha telefon ovozlari yo‘q.",
            reply_markup=admin_keyboard()
        )
        return

    for row in rows:

        vote_id, user_id, phone, amount, project, created = row

        text = (
            "📱 <b>Telefon ovozi</b>\n\n"
            f"🆔 Ovoz ID: <code>{vote_id}</code>\n"
            f"👤 User ID: <code>{user_id}</code>\n"
            f"📱 Telefon: <code>{escape(phone)}</code>\n"
            f"📋 Loyiha: {escape(project or 'Noma’lum')}\n"
            f"💰 Summa: {amount:,} so‘m\n"
            f"🕒 {created}"
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="💬 Javob berish",
                        callback_data=f"replyphone_{user_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🔒 Suhbatni yopish",
                        callback_data=f"closechat_{user_id}"
                    )
                ]
            ]
        )

        await message.answer(
            text,
            reply_markup=keyboard
        )


# ============================================================
# 32. ADMIN — PUL YECHISHLAR
# ============================================================

@dp.message(F.text == "💸 Pul yechishlar")
async def withdrawals_admin(message: Message):

    if not is_admin(message.from_user.id):
        return

    with closing(db()) as conn:

        cur = conn.cursor()

        cur.execute("""
        SELECT
            id,
            user_id,
            card_number,
            amount,
            status,
            created_at
        FROM withdrawals
        ORDER BY id DESC
        LIMIT 50
        """)

        rows = cur.fetchall()

    if not rows:

        await message.answer(
            "💸 Hozircha pul yechish so‘rovlari yo‘q."
        )
        return

    for row in rows:

        wid, user_id, card, amount, status, created = row

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Tasdiqlash",
                        callback_data=f"withdraw_ok_{user_id}_{wid}"
                    ),
                    InlineKeyboardButton(
                        text="❌ Rad etish",
                        callback_data=f"withdraw_no_{user_id}_{wid}"
                    )
                ]
            ]
        )

        await message.answer(
            "💸 <b>PUL YECHISH SO‘ROVI</b>\n\n"
            f"🆔 So‘rov: <code>{wid}</code>\n"
            f"👤 User ID: <code>{user_id}</code>\n"
            f"💰 Summa: <b>{amount:,} so‘m</b>\n"
            f"💳 Karta: <code>{escape(card)}</code>\n"
            f"📌 Holat: <b>{escape(status)}</b>\n"
            f"🕒 {created}",
            reply_markup=keyboard
        )


# ============================================================
# 33. WITHDRAW TASDIQLASH
# ============================================================

@dp.callback_query(F.data.startswith("withdraw_ok_"))
async def withdraw_ok(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    parts = callback.data.split("_")

    try:
        user_id = int(parts[2])
        withdraw_id = int(parts[3])
    except (ValueError, IndexError):
        await callback.answer()
        return

    with closing(db()) as conn:

        cur = conn.cursor()

        cur.execute("""
        SELECT amount, status
        FROM withdrawals
        WHERE id=?
        """, (withdraw_id,))

        row = cur.fetchone()

        if not row:
            await callback.answer(
                "So‘rov topilmadi.",
                show_alert=True
            )
            return

        amount, status = row

        if status != "pending":

            await callback.answer(
                "Bu so‘rov allaqachon ko‘rib chiqilgan.",
                show_alert=True
            )
            return

        cur.execute("""
        UPDATE withdrawals
        SET status='approved'
        WHERE id=?
        """, (withdraw_id,))

        # Tasdiqlanganda balansdan yechiladi
        cur.execute("""
        UPDATE users
        SET balance = CASE
            WHEN balance >= ? THEN balance - ?
            ELSE 0
        END
        WHERE user_id=?
        """, (
            amount,
            amount,
            user_id
        ))

        conn.commit()

    try:

        await bot.send_message(
            user_id,
            "✅ Pul yechish so‘rovingiz tasdiqlandi.\n\n"
            f"💰 Summa: {amount:,} so‘m"
        )

    except Exception:
        pass

    await callback.message.edit_reply_markup(
        reply_markup=None
    )

    await callback.message.answer(
        "✅ Pul yechish tasdiqlandi."
    )

    await callback.answer()


# ============================================================
# 34. WITHDRAW RAD ETISH
# ============================================================

@dp.callback_query(F.data.startswith("withdraw_no_"))
async def withdraw_no(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    parts = callback.data.split("_")

    try:
        user_id = int(parts[2])
        withdraw_id = int(parts[3])
    except (ValueError, IndexError):
        await callback.answer()
        return

    with closing(db()) as conn:

        cur = conn.cursor()

        cur.execute("""
        UPDATE withdrawals
        SET status='rejected'
        WHERE id=? AND status='pending'
        """, (withdraw_id,))

        conn.commit()

    try:

        await bot.send_message(
            user_id,
            "❌ Pul yechish so‘rovingiz admin tomonidan rad etildi."
        )

    except Exception:
        pass

    await callback.message.edit_reply_markup(
        reply_markup=None
   