# ============================================================
# TELEGRAM BOT - MAIN.PY
# Aiogram 3.x + SQLite
# ============================================================

import asyncio
import logging
import sqlite3
import re
from html import escape
from pathlib import Path

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
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage


# ============================================================
# 1. SOZLAMALAR
# ============================================================

# BOT TOKENINGIZNI SHU YERGA YOZING
BOT_TOKEN = "8615736731:AAF7LGgYsKCq_JjV9qFPmFV6psTAS4mlQ_g"

# ADMIN TELEGRAM ID LARINI SHU YERGA YOZING
# Masalan:
# ADMIN_IDS = [7998053914]
ADMIN_IDS = [
    7998053914
]

# Referral uchun bonus
REFERRAL_BONUS = 10000

# Pul yechish uchun minimal balans
MIN_WITHDRAW = 30000

DB_FILE = Path("bot.db")


# ============================================================
# 2. LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)


# ============================================================
# 3. BOT VA DISPATCHER
# ============================================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ============================================================
# 4. DATABASE
# ============================================================

def db():
    return sqlite3.connect(DB_FILE)


def init_db():
    conn = db()
    cur = conn.cursor()

    # Foydalanuvchilar
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            phone TEXT,
            balance INTEGER DEFAULT 0,
            referral_code TEXT UNIQUE,
            referred_by INTEGER,
            referral_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Referral
    cur.execute("""
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inviter_id INTEGER,
            invited_id INTEGER UNIQUE,
            bonus INTEGER DEFAULT 10000,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Ovoz/havola operatsiyalari
    cur.execute("""
        CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            vote_type TEXT,
            phone TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Savol-javob suhbatlari
    cur.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            user_id INTEGER PRIMARY KEY,
            active INTEGER DEFAULT 1,
            topic TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Pul yechish
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

    # Balans operatsiyalari
    cur.execute("""
        CREATE TABLE IF NOT EXISTS balance_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            operation TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Sozlamalar
    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # Statistikalar
    cur.execute("""
        CREATE TABLE IF NOT EXISTS button_stats (
            button TEXT PRIMARY KEY,
            count INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


# ============================================================
# 5. SOZLAMALAR FUNKSIYALARI
# ============================================================

def get_setting(key, default=""):
    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT value FROM settings WHERE key = ?",
        (key,)
    )

    row = cur.fetchone()
    conn.close()

    if row:
        return row[0]

    return default


def set_setting(key, value):
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO settings(key, value)
        VALUES (?, ?)
        ON CONFLICT(key)
        DO UPDATE SET value = excluded.value
    """, (key, value))

    conn.commit()
    conn.close()


# ============================================================
# 6. STATISTIKA
# ============================================================

def count_button(button):
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO button_stats(button, count)
        VALUES (?, 1)
        ON CONFLICT(button)
        DO UPDATE SET count = count + 1
    """, (button,))

    conn.commit()
    conn.close()


# ============================================================
# 7. FOYDALANUVCHI
# ============================================================

def add_user(user_id, username, first_name):
    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT user_id FROM users WHERE user_id = ?",
        (user_id,)
    )

    exists = cur.fetchone()

    if not exists:
        referral_code = str(user_id)

        cur.execute("""
            INSERT INTO users(
                user_id,
                username,
                first_name,
                referral_code
            )
            VALUES (?, ?, ?, ?)
        """, (
            user_id,
            username,
            first_name,
            referral_code
        ))
    else:
        cur.execute("""
            UPDATE users
            SET username = ?,
                first_name = ?
            WHERE user_id = ?
        """, (
            username,
            first_name,
            user_id
        ))

    conn.commit()
    conn.close()


def get_user(user_id):
    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM users WHERE user_id = ?",
        (user_id,)
    )

    row = cur.fetchone()
    conn.close()

    return row


def get_balance(user_id):
    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT balance FROM users WHERE user_id = ?",
        (user_id,)
    )

    row = cur.fetchone()
    conn.close()

    return row[0] if row else 0


def add_balance(user_id, amount, operation):
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET balance = balance + ?
        WHERE user_id = ?
    """, (amount, user_id))

    cur.execute("""
        INSERT INTO balance_history(
            user_id,
            amount,
            operation
        )
        VALUES (?, ?, ?)
    """, (
        user_id,
        amount,
        operation
    ))

    conn.commit()
    conn.close()


# ============================================================
# 8. REFERRAL
# ============================================================

def process_referral(new_user_id, inviter_id):
    if not inviter_id:
        return False

    if new_user_id == inviter_id:
        return False

    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT referred_by FROM users WHERE user_id = ?",
        (new_user_id,)
    )

    row = cur.fetchone()

    if not row:
        conn.close()
        return False

    if row[0] is not None:
        conn.close()
        return False

    cur.execute(
        "SELECT user_id FROM users WHERE user_id = ?",
        (inviter_id,)
    )

    inviter = cur.fetchone()

    if not inviter:
        conn.close()
        return False

    cur.execute("""
        UPDATE users
        SET referred_by = ?
        WHERE user_id = ?
    """, (
        inviter_id,
        new_user_id
    ))

    cur.execute("""
        UPDATE users
        SET referral_count = referral_count + 1,
            balance = balance + ?
        WHERE user_id = ?
    """, (
        REFERRAL_BONUS,
        inviter_id
    ))

    cur.execute("""
        INSERT INTO referrals(
            inviter_id,
            invited_id,
            bonus
        )
        VALUES (?, ?, ?)
    """, (
        inviter_id,
        new_user_id,
        REFERRAL_BONUS
    ))

    cur.execute("""
        INSERT INTO balance_history(
            user_id,
            amount,
            operation
        )
        VALUES (?, ?, ?)
    """, (
        inviter_id,
        REFERRAL_BONUS,
        "Referral bonusi"
    ))

    conn.commit()
    conn.close()

    return True


# ============================================================
# 9. ASOSIY FOYDALANUVCHI MENYUSI
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
                KeyboardButton(text="👨‍💼 Admin bilan bog‘lanish")
            ]
        ],
        resize_keyboard=True,
        is_persistent=True
    )


# ============================================================
# 10. ADMIN MENYUSI
# ============================================================

def admin_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📊 Statistika"),
                KeyboardButton(text="👥 Foydalanuvchilar")
            ],
            [
                KeyboardButton(text="📞 Telefon raqamlari"),
                KeyboardButton(text="💳 Pul yechishlar")
            ],
            [
                KeyboardButton(text="❓ Savol-javoblar"),
                KeyboardButton(text="🗳 Ovozlar")
            ],
            [
                KeyboardButton(text="🔗 Ovoz havolasi"),
                KeyboardButton(text="👨‍💼 Admin kontakt")
            ],
            [
                KeyboardButton(text="💰 Balans boshqaruvi"),
                KeyboardButton(text="📢 Xabar yuborish")
            ],
            [
                KeyboardButton(text="🏠 Foydalanuvchi menyusi")
            ]
        ],
        resize_keyboard=True,
        is_persistent=True
    )


# ============================================================
# 11. ADMIN TEKSHIRISH
# ============================================================

def is_admin(user_id):
    return user_id in ADMIN_IDS


# ============================================================
# 12. START
# ============================================================

@dp.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    await state.clear()

    user = message.from_user

    add_user(
        user.id,
        user.username or "",
        user.first_name or ""
    )

    # Referral parametr
    args = message.text.split(maxsplit=1)

    if len(args) > 1:
        try:
            inviter_id = int(args[1])
            process_referral(user.id, inviter_id)
        except Exception:
            pass

    if is_admin(user.id):
        await message.answer(
            "👨‍💼 <b>Admin panel</b>\n\n"
            "Kerakli bo‘limni tanlang.",
            reply_markup=admin_keyboard()
        )
    else:
        await message.answer(
            f"👋 Assalomu alaykum, <b>{escape(user.first_name or 'Foydalanuvchi')}</b>!\n\n"
            "Botga xush kelibsiz.",
            reply_markup=user_keyboard()
        )


# ============================================================
# 13. BALANS
# ============================================================

@dp.message(F.text == "💰 Balans")
async def balance_handler(message: Message):
    if is_admin(message.from_user.id):
        return

    count_button("balans")

    balance = get_balance(message.from_user.id)

    await message.answer(
        "💰 <b>Sizning balansingiz</b>\n\n"
        f"💵 Balans: <b>{balance:,} so‘m</b>\n\n"
        "💳 Balansdagi pulni yechish uchun balansda "
        "<b>kamida 30 000 so‘m</b> bo‘lishi kerak.\n\n"
        "Balansni referral orqali to‘ldirishingiz mumkin.",
        reply_markup=user_keyboard()
    )


# ============================================================
# 14. OVOZ BERISH
# ============================================================

@dp.message(F.text == "🗳 Ovoz berish")
async def vote_handler(message: Message):
    if is_admin(message.from_user.id):
        return

    count_button("ovoz")

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔗 Havola orqali",
                    callback_data="vote_link"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📞 Telefon raqami orqali",
                    callback_data="vote_phone"
                )
            ]
        ]
    )

    await message.answer(
        "🗳 <b>Ovoz berish</b>\n\n"
        "Ovoz berish usulini tanlang:",
        reply_markup=keyboard
    )


# ============================================================
# 15. OVOZ HAVOLASI
# ============================================================

@dp.callback_query(F.data == "vote_link")
async def vote_link_callback(callback: CallbackQuery):
    link = get_setting("vote_link", "")

    if not link:
        await callback.message.answer(
            "🔗 Hozircha ovoz berish havolasi admin tomonidan qo‘shilmagan."
        )
    else:
        await callback.message.answer(
            "🔗 <b>Ovoz berish havolasi:</b>\n\n"
            f"{escape(link)}"
        )

    await callback.answer()


# ============================================================
# 16. TELEFON ORQALI OVOZ
# ============================================================

class VoteStates(StatesGroup):
    waiting_phone = State()


@dp.callback_query(F.data == "vote_phone")
async def vote_phone_callback(
    callback: CallbackQuery,
    state: FSMContext
):
    await state.set_state(VoteStates.waiting_phone)

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="📞 Telefon raqamimni yuborish",
                    request_contact=True
                )
            ],
            [
                KeyboardButton(text="❌ Bekor qilish")
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )

    await callback.message.answer(
        "📞 <b>Ovoz berish uchun telefon raqamingizni yuboring.</b>\n\n"
        "Pastdagi tugma orqali telefon raqamingizni yuborishingiz mumkin.",
        reply_markup=keyboard
    )

    await callback.answer()


@dp.message(VoteStates.waiting_phone)
async def receive_vote_phone(
    message: Message,
    state: FSMContext
):
    if message.text == "❌ Bekor qilish":
        await state.clear()

        await message.answer(
            "❌ Bekor qilindi.",
            reply_markup=user_keyboard()
        )
        return

    phone = None

    if message.contact:
        phone = message.contact.phone_number
    elif message.text:
        phone = message.text.strip()

    if not phone:
        await message.answer(
            "❗ Telefon raqamini yuboring."
        )
        return

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET phone = ?
        WHERE user_id = ?
    """, (
        phone,
        message.from_user.id
    ))

    cur.execute("""
        INSERT INTO votes(
            user_id,
            vote_type,
            phone,
            status
        )
        VALUES (?, ?, ?, ?)
    """, (
        message.from_user.id,
        "phone",
        phone,
        "pending"
    ))

    conn.commit()
    conn.close()

    await state.clear()

    await message.answer(
        "✅ Telefon raqamingiz qabul qilindi.\n\n"
        "📨 Ma’lumot admin panelga yuborildi.",
        reply_markup=user_keyboard()
    )

    # Adminlarga yuborish
    for admin_id in ADMIN_IDS:
        try:
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="💬 Javob berish",
                            callback_data=f"reply_{message.from_user.id}"
                        )
                    ]
                ]
            )

            await bot.send_message(
                admin_id,
                "📞 <b>Yangi telefon raqami</b>\n\n"
                f"👤 Ism: {escape(message.from_user.full_name)}\n"
                f"🆔 ID: <code>{message.from_user.id}</code>\n"
                f"📞 Telefon: <code>{escape(phone)}</code>",
                reply_markup=keyboard
            )

        except Exception as e:
            logger.error(e)


# ============================================================
# 17. SAVOL-JAVOB
# ============================================================

class QuestionStates(StatesGroup):
    waiting_question = State()


@dp.message(F.text == "❓ Savol-javob")
async def question_start(
    message: Message,
    state: FSMContext
):
    if is_admin(message.from_user.id):
        return

    count_button("savol_javob")

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO conversations(user_id, active, topic)
        VALUES (?, 1, 'savol-javob')
        ON CONFLICT(user_id)
        DO UPDATE SET active = 1
    """, (message.from_user.id,))

    conn.commit()
    conn.close()

    await state.set_state(QuestionStates.waiting_question)

    await message.answer(
        "❓ <b>Savolingizni yozing.</b>\n\n"
        "Savolingiz adminga yuboriladi.",
        reply_markup=user_keyboard()
    )


@dp.message(QuestionStates.waiting_question)
async def receive_question(
    message: Message,
    state: FSMContext
):
    if not message.text:
        await message.answer("❗ Iltimos, savolni matn ko‘rinishida yuboring.")
        return

    question = message.text

    await state.clear()

    for admin_id in ADMIN_IDS:
        try:
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="💬 Javob berish",
                            callback_data=f"reply_{message.from_user.id}"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="🔴 Suhbatni yopish",
                            callback_data=f"close_{message.from_user.id}"
                        )
                    ]
                ]
            )

            await bot.send_message(
                admin_id,
                "❓ <b>Yangi savol</b>\n\n"
                f"👤 {escape(message.from_user.full_name)}\n"
                f"🆔 <code>{message.from_user.id}</code>\n\n"
                f"💬 {escape(question)}",
                reply_markup=keyboard
            )

        except Exception as e:
            logger.error(e)

    await message.answer(
        "✅ Savolingiz adminga yuborildi.\n"
        "Admin javobini kuting.",
        reply_markup=user_keyboard()
    )


# ============================================================
# 18. ADMIN JAVOB BERISH
# ============================================================

class AdminReplyStates(StatesGroup):
    waiting_reply = State()


@dp.callback_query(F.data.startswith("reply_"))
async def admin_reply_start(
    callback: CallbackQuery,
    state: FSMContext
):
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo‘q.", show_alert=True)
        return

    try:
        user_id = int(callback.data.split("_")[1])
    except Exception:
        await callback.answer("Xatolik.")
        return

    await state.update_data(reply_user_id=user_id)
    await state.set_state(AdminReplyStates.waiting_reply)

    await callback.message.answer(
        "💬 Foydalanuvchiga yubormoqchi bo‘lgan javobingizni yozing."
    )

    await callback.answer()


@dp.message(AdminReplyStates.waiting_reply)
async def admin_send_reply(
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

    try:
        await bot.send_message(
            user_id,
            "👨‍💼 <b>Admin javobi:</b>\n\n"
            f"{escape(message.text or '')}"
        )

        await message.answer(
            "✅ Javob foydalanuvchiga yuborildi."
        )

        conn = db()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO conversations(user_id, active, topic)
            VALUES (?, 1, 'admin')
            ON CONFLICT(user_id)
            DO UPDATE SET active = 1
        """, (user_id,))

        conn.commit()
        conn.close()

    except Exception as e:
        await message.answer(
            f"❌ Xatolik: {escape(str(e))}"
        )

    await state.clear()


# ============================================================
# 19. FOYDALANUVCHINING ADMIN BILAN DAVOMLI SUHBATI
# ============================================================

@dp.message()
async def general_user_message(message: Message):
    if is_admin(message.from_user.id):
        return

    if not message.text:
        return

    text = message.text.strip()

    # Menyu tugmalarini o'tkazib yuboramiz
    menu_buttons = {
        "📌 Loyihalar",
        "🗳 Ovoz berish",
        "💰 Balans",
        "💳 Pul yechish",
        "👥 Do‘stlarni taklif qilish",
        "❓ Savol-javob",
        "👨‍💼 Admin bilan bog‘lanish"
    }

    if text in menu_buttons:
        return

    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT active FROM conversations WHERE user_id = ?",
        (message.from_user.id,)
    )

    row = cur.fetchone()
    conn.close()

    if row and row[0] == 1:
        for admin_id in ADMIN_IDS:
            try:
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="💬 Javob berish",
                                callback_data=f"reply_{message.from_user.id}"
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                text="🔴 Suhbatni yopish",
                                callback_data=f"close_{message.from_user.id}"
                            )
                        ]
                    ]
                )

                await bot.send_message(
                    admin_id,
                    "💬 <b>Foydalanuvchidan yangi xabar</b>\n\n"
                    f"👤 {escape(message.from_user.full_name)}\n"
                    f"🆔 <code>{message.from_user.id}</code>\n\n"
                    f"{escape(text)}",
                    reply_markup=keyboard
                )

            except Exception as e:
                logger.error(e)

        await message.answer(
            "✅ Xabaringiz adminga yuborildi.",
            reply_markup=user_keyboard()
        )


# ============================================================
# 20. SUHBATNI YOPISH
# ============================================================

@dp.callback_query(F.data.startswith("close_"))
async def close_conversation(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "Ruxsat yo‘q.",
            show_alert=True
        )
        return

    try:
        user_id = int(callback.data.split("_")[1])
    except Exception:
        await callback.answer("Xatolik.")
        return

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE conversations
        SET active = 0
        WHERE user_id = ?
    """, (user_id,))

    conn.commit()
    conn.close()

    try:
        await bot.send_message(
            user_id,
            "🔴 <b>Admin suhbatni yopdi.</b>\n\n"
            "Yangi savol bo‘lsa, ❓ Savol-javob tugmasidan foydalaning.",
            reply_markup=user_keyboard()
        )
    except Exception:
        pass

    await callback.message.answer(
        "✅ Suhbat yopildi."
    )

    await callback.answer()


# ============================================================
# 21. DO‘STLARNI TAKLIF QILISH
# ============================================================

@dp.message(F.text == "👥 Do‘stlarni taklif qilish")
async def referral_handler(message: Message):
    if is_admin(message.from_user.id):
        return

    count_button("referral")

    user = get_user(message.from_user.id)

    if not user:
        add_user(
            message.from_user.id,
            message.from_user.username or "",
            message.from_user.first_name or ""
        )

    bot_info = await bot.get_me()

    link = (
        f"https://t.me/{bot_info.username}"
        f"?start={message.from_user.id}"
    )

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT referral_count
        FROM users
        WHERE user_id = ?
    """, (message.from_user.id,))

    row = cur.fetchone()
    conn.close()

    referral_count = row[0] if row else 0

    await message.answer(
        "👥 <b>Do‘stlarni taklif qilish</b>\n\n"
        f"🔗 Sizning havolangiz:\n{link}\n\n"
        f"👤 Taklif qilgan do‘stlaringiz: <b>{referral_count}</b>\n"
        f"💰 Har bir muvaffaqiyatli taklif uchun: <b>{REFERRAL_BONUS:,} so‘m</b>\n\n"
        "Do‘stlaringizni shu havola orqali botga taklif qiling.",
        reply_markup=user_keyboard()
    )


# ============================================================
# 22. PUL YECHISH
# ============================================================

class WithdrawStates(StatesGroup):
    waiting_card = State()


@dp.message(F.text == "💳 Pul yechish")
async def withdraw_start(
    message: Message,
    state: FSMContext
):
    if is_admin(message.from_user.id):
        return

    count_button("pul_yechish")

    balance = get_balance(message.from_user.id)

    if balance < MIN_WITHDRAW:
        await message.answer(
            "❌ <b>Sizning balansingizda yetarli mablag‘ yo‘q.</b>\n\n"
            "Ko‘proq referral orqali balansingizni to‘ldiring.\n\n"
            f"💰 Hozirgi balans: <b>{balance:,} so‘m</b>\n"
            f"💳 Minimal yechish: <b>{MIN_WITHDRAW:,} so‘m</b>",
            reply_markup=user_keyboard()
        )
        return

    await state.set_state(WithdrawStates.waiting_card)

    await message.answer(
        f"💳 <b>Pul yechish</b>\n\n"
        f"Balansingiz: <b>{balance:,} so‘m</b>\n\n"
        "Karta raqamingizni yuboring:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(
                        text="❌ Bekor qilish"
                    )
                ]
            ],
            resize_keyboard=True
        )
    )


@dp.message(WithdrawStates.waiting_card)
async def receive_card(
    message: Message,
    state: FSMContext
):
    if message.text == "❌ Bekor qilish":
        await state.clear()

        await message.answer(
            "❌ Bekor qilindi.",
            reply_markup=user_keyboard()
        )
        return

    card = re.sub(r"\D", "", message.text or "")

    if len(card) < 12 or len(card) > 19:
        await message.answer(
            "❗ Karta raqami noto‘g‘ri.\n"
            "Iltimos, karta raqamingizni qayta yuboring."
        )
        return

    balance = get_balance(message.from_user.id)

    if balance < MIN_WITHDRAW:
        await state.clear()

        await message.answer(
            "❌ Balansingiz yetarli emas.",
            reply_markup=user_keyboard()
        )
        return

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO withdrawals(
            user_id,
            card_number,
            amount,
            status
        )
        VALUES (?, ?, ?, 'pending')
    """, (
        message.from_user.id,
        card,
        balance
    ))

    conn.commit()
    conn.close()

    await state.clear()

    await message.answer(
        "✅ Pul yechish so‘rovingiz qabul qilindi.\n\n"
        "📨 Admin ko‘rib chiqadi.",
        reply_markup=user_keyboard()
    )

    for admin_id in ADMIN_IDS:
        try:
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="💬 Javob berish",
                            callback_data=f"reply_{message.from_user.id}"
                        )
                    ]
                ]
            )

            await bot.send_message(
                admin_id,
                "💳 <b>Yangi pul yechish so‘rovi</b>\n\n"
                f"👤 {escape(message.from_user.full_name)}\n"
                f"🆔 <code>{message.from_user.id}</code>\n"
                f"💰 Summa: <b>{balance:,} so‘m</b>\n"
                f"💳 Karta: <code>{card}</code>",
                reply_markup=keyboard
            )

        except Exception as e:
            logger.error(e)


# ============================================================
# 23. ADMIN BILAN BOG‘LANISH
# ============================================================

@dp.message(F.text == "👨‍💼 Admin bilan bog‘lanish")
async def contact_admin(message: Message):
    if is_admin(message.from_user.id):
        return

    count_button("admin_contact")

    contact = get_setting("admin_contact", "")

    if contact:
        await message.answer(
            "👨‍💼 <b>Admin bilan bog‘lanish</b>\n\n"
            f"{escape(contact)}",
            reply_markup=user_keyboard()
        )
    else:
        await message.answer(
            "ℹ️ Hozircha admin qo‘shilmagan yoki barcha adminlar band.",
            reply_markup=user_keyboard()
        )


# ============================================================
# 24. LOYIHALAR
# ============================================================

@dp.message(F.text == "📌 Loyihalar")
async def projects_handler(message: Message):
    if is_admin(message.from_user.id):
        return

    count_button("loyihalar")

    link = get_setting("project_link", "")
    name = get_setting("project_name", "")

    if not link:
        await message.answer(
            "📌 <b>Loyihalar</b>\n\n"
            "Hozircha loyiha qo‘shilmagan.",
            reply_markup=user_keyboard()
        )
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=name or "🔗 Loyihaga kirish",
                    url=link
                )
            ]
        ]
    )

    await message.answer(
        "📌 <b>Loyiha</b>\n\n"
        f"{escape(name or 'Loyiha')}",
        reply_markup=keyboard
    )


# ============================================================
# 25. ADMIN - STATISTIKA
# ============================================================

@dp.message(F.text == "📊 Statistika")
async def admin_statistics(message: Message):
    if not is_admin(message.from_user.id):
        return

    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM users")
    users = cur.fetchone()[0]

    cur.execute("SELECT COALESCE(SUM(balance), 0) FROM users")
    balance = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM votes")
    votes = cur.fetchone()[0]

    cur.execute(
        "SELECT COUNT(*) FROM votes WHERE vote_type = 'phone'"
    )
    phone_votes = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM referrals")
    referrals = cur.fetchone()[0]

    cur.execute(
        "SELECT COALESCE(SUM(bonus), 0) FROM referrals"
    )
    referral_money = cur.fetchone()[0]

    cur.execute(
        "SELECT COUNT(*) FROM withdrawals WHERE status = 'pending'"
    )
    pending_withdrawals = cur.fetchone()[0]

    cur.execute(
        "SELECT COUNT(*) FROM conversations WHERE active = 1"
    )
    active_chats = cur.fetchone()[0]

    cur.execute(
        "SELECT COUNT(*) FROM withdrawals"
    )
    all_withdrawals = cur.fetchone()[0]

    conn.close()

    await message.answer(
        "📊 <b>BOT STATISTIKASI</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{users}</b>\n"
        f"🗳 Jami ovoz so‘rovlari: <b>{votes}</b>\n"
        f"📞 Telefon orqali ovozlar: <b>{phone_votes}</b>\n"
        f"👥 Referral takliflar: <b>{referrals}</b>\n"
        f"💰 Referral bonuslari: <b>{referral_money:,} so‘m</b>\n"
        f"💵 Jami balanslar: <b>{balance:,} so‘m</b>\n"
        f"💳 Pul yechish so‘rovlari: <b>{all_withdrawals}</b>\n"
        f"⏳ Kutilayotgan yechishlar: <b>{pending_withdrawals}</b>\n"
        f"💬 Faol suhbatlar: <b>{active_chats}</b>",
        reply_markup=admin_keyboard()
    )


# ============================================================
# 26. ADMIN - FOYDALANUVCHILAR
# ============================================================

@dp.message(F.text == "👥 Foydalanuvchilar")
async def admin_users(message: Message):
    if not is_admin(message.from_user.id):
        return

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT user_id, first_name, username, balance
        FROM users
        ORDER BY created_at DESC
        LIMIT 20
    """)

    rows = cur.fetchall()
    conn.close()

    if not rows:
        await message.answer(
            "👥 Hozircha foydal