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
    InlineKeyboardButton
)


# ============================================================
# SOZLAMALAR
# ============================================================

# ============================================================
# BOT TOKENINI SHU YERGA QO'YING
# YANGI TOKENNI YOZING
# ============================================================

BOT_TOKEN = "8615736731:AAF7LGgYsKCq_JjV9qFPmFV6psTAS4mlQ_g"


# ============================================================
# ADMIN TELEGRAM ID
# ============================================================

ADMIN_IDS = {7998053914}


# ============================================================
# ISBOT KANALI
# ============================================================
# Masalan:
# https://t.me/kanal_nomi
#
# Shu yerga o'zingizning isbot kanalingiz havolasini yozing.
# ============================================================

ISBOT_KANAL_URL = "https://t.me/SIZNING_ISBOT_KANALINGIZ"


DB_NAME = "bot.db"

VOTE_REWARD = 30000
REFERRAL_REWARD = 10000
MIN_WITHDRAW = 30000


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


# ============================================================
# DATABASE
# ============================================================

def db():
    return sqlite3.connect(DB_NAME)


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

        c.commit()


# ============================================================
# YORDAMCHI FUNKSIYALAR
# ============================================================

def is_admin(user_id):
    return user_id in ADMIN_IDS


def setting(key, default=""):

    with closing(db()) as c:

        row = c.execute(
            "SELECT value FROM settings WHERE key=?",
            (key,)
        ).fetchone()

        return row[0] if row else default


def set_setting(key, value):

    with closing(db()) as c:

        c.execute("""
            INSERT INTO settings(key, value)
            VALUES(?, ?)
            ON CONFLICT(key)
            DO UPDATE SET value=excluded.value
        """, (key, value))

        c.commit()


def add_user(user, referred_by=None):

    with closing(db()) as c:

        old = c.execute(
            "SELECT user_id FROM users WHERE user_id=?",
            (user.id,)
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
                user.id
            ))

            c.commit()
            return False

        if referred_by == user.id:
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
            referred_by
        ))

        c.commit()

        return True


def user_row(user_id):

    with closing(db()) as c:

        return c.execute(
            "SELECT * FROM users WHERE user_id=?",
            (user_id,)
        ).fetchone()


def money(value):

    return f"{int(value):,}".replace(",", " ")


def normalize_phone(value):

    value = re.sub(
        r"[^\d+]",
        "",
        value or ""
    )

    if value.startswith("00"):
        value = "+" + value[2:]

    return value


def valid_phone(value):

    phone = normalize_phone(value)

    if phone.startswith("+"):
        digits = phone[1:]
    else:
        digits = phone

    return (
        digits.isdigit()
        and 8 <= len(digits) <= 15
    )


# ============================================================
# FOYDALANUVCHI MENYUSI
# ============================================================

def user_kb():

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
                KeyboardButton(text="🛡 Isbot kanali")
            ],
            [
                KeyboardButton(text="❓ Savol-javob"),
                KeyboardButton(text="👨‍💻 Admin bilan bog‘lanish")
            ]
        ],
        resize_keyboard=True,
        is_persistent=True
    )


# ============================================================
# ADMIN MENYUSI
# ============================================================

def admin_kb():

    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📊 Statistika"),
                KeyboardButton(text="👥 Foydalanuvchilar")
            ],
            [
                KeyboardButton(text="🗳 Ovozlar"),
                KeyboardButton(text="📱 Telefon ovozlari")
            ],
            [
                KeyboardButton(text="💳 Pul yechishlar"),
                KeyboardButton(text="❓ Savollar")
            ],
            [
                KeyboardButton(text="👥 Referallar"),
                KeyboardButton(text="🔗 Ovoz havolasi")
            ],
            [
                KeyboardButton(text="👨‍💻 Admin kontakt"),
                KeyboardButton(text="➕ Loyiha qo‘shish")
            ],
            [
                KeyboardButton(text="📌 Loyihalar"),
                KeyboardButton(text="📢 Reklama")
            ],
            [
                KeyboardButton(text="🏠 Foydalanuvchi menyusi")
            ]
        ],
        resize_keyboard=True,
        is_persistent=True
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


def vote_admin_kb(vote_id):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Tasdiqlash",
                    callback_data=f"va:{vote_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Rad etish",
                    callback_data=f"vr:{vote_id}"
                )
            ]
        ]
    )


def chat_kb(user_id):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 Javob berish",
                    callback_data=f"reply:{user_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔒 Suhbatni yopish",
                    callback_data=f"close:{user_id}"
                )
            ]
        ]
    )


def withdraw_kb(withdraw_id):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ To‘landi",
                    callback_data=f"wp:{withdraw_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Rad etish",
                    callback_data=f"wr:{withdraw_id}"
                )
            ]
        ]
    )


# ============================================================
# START
# ============================================================

@dp.message(CommandStart())
async def start_handler(
    message: Message,
    state: FSMContext
):

    await state.clear()

    referred_by = None

    parts = (
        message.text or ""
    ).split(
        maxsplit=1
    )

    if len(parts) == 2:

        code = parts[1]

        if code.startswith("ref_"):

            try:
                referred_by = int(
                    code[4:]
                )
            except ValueError:
                referred_by = None

    is_new = add_user(
        message.from_user,
        referred_by
    )

    if (
        is_new
        and referred_by
        and referred_by != message.from_user.id
    ):

        with closing(db()) as c:

            inviter = c.execute(
                "SELECT user_id FROM users WHERE user_id=?",
                (referred_by,)
            ).fetchone()

            already = c.execute(
                "SELECT id FROM referrals WHERE invited_id=?",
                (message.from_user.id,)
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
                    message.from_user.id,
                    REFERRAL_REWARD
                ))

                c.execute("""
                    UPDATE users
                    SET balance=balance+?,
                        referrals=referrals+1
                    WHERE user_id=?
                """, (
                    REFERRAL_REWARD,
                    referred_by
                ))

                c.commit()

                try:

                    await bot.send_message(
                        referred_by,
                        "🎉 <b>Yangi do‘st taklif qilindi!</b>\n\n"
                        f"💰 Balansingizga "
                        f"<b>+{money(REFERRAL_REWARD)} so‘m</b> qo‘shildi."
                    )

                except Exception:
                    pass

    await message.answer(
        "👋 <b>Assalomu alaykum!</b>\n\n"
        "Botga xush kelibsiz.\n"
        "Kerakli bo‘limni pastdagi menyudan tanlang.",
        reply_markup=user_kb()
    )


# ============================================================
# ADMIN START
# ============================================================

@dp.message(Command("admin"))
async def admin_command(message: Message):

    if not is_admin(message.from_user.id):

        await message.answer(
            "❌ Siz admin emassiz."
        )
        return

    await message.answer(
        "👨‍💼 <b>Admin panel</b>",
        reply_markup=admin_kb()
    )


# ============================================================
# FOYDALANUVCHI MENYUSIGA QAYTISH
# ============================================================

@dp.message(F.text == "🏠 Foydalanuvchi menyusi")
async def user_menu(message: Message):

    if not is_admin(message.from_user.id):
        return

    await message.answer(
        "🏠 <b>Foydalanuvchi menyusi</b>",
        reply_markup=user_kb()
    )


# ============================================================
# ISBOT KANALI
# ============================================================

@dp.message(F.text == "🛡 Isbot kanali")
async def proof_channel_handler(
    message: Message
):

    if is_admin(message.from_user.id):
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🛡 Isbot kanaliga kirish",
                    url=ISBOT_KANAL_URL
                )
            ]
        ]
    )

    await message.answer(
        "🛡 <b>ISBOT KANALI</b>\n\n"
        "Bu kanalda ovozlar, to‘lovlar va boshqa "
        "natijalar bo‘yicha isbotlar joylab boriladi.\n\n"
        "Kanalga kirish uchun quyidagi tugmani bosing:",
        reply_markup=keyboard
    )


# ============================================================
# LOYIHALAR
# ============================================================

@dp.message(F.text == "📌 Loyihalar")
async def projects_handler(message: Message):

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
                reply_markup=admin_kb()
            )

            return

        text = "📌 <b>Loyihalar</b>\n\n"

        for row in rows:

            text += (
                f"🆔 {row[0]}\n"
                f"📌 {escape(row[1])}\n"
                f"🔗 {escape(row[2] or '-')}\n"
                f"────────────\n"
            )

        await message.answer(
            text,
            reply_markup=admin_kb()
        )

        return

    if not rows:

        await message.answer(
            "📌 <b>Hozircha loyiha yo‘q.</b>",
            reply_markup=user_kb()
        )

        return

    text = "📌 <b>Loyihalar</b>\n\n"

    buttons = []

    for row in rows:

        text += (
            f"🔹 <b>{escape(row[1])}</b>\n\n"
        )

        if row[2]:

            buttons.append([
                InlineKeyboardButton(
                    text=row[1],
                    url=row[2]
                )
            ])

    keyboard = None

    if buttons:

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=buttons
        )

    await message.answer(
        text,
        reply_markup=keyboard
    )


# ============================================================
# OVOZ BERISH
# ============================================================

@dp.message(F.text == "🗳 Ovoz berish")
async def vote_start(message: Message):

    if is_admin(message.from_user.id):
        return

    await message.answer(
        "🗳 <b>Ovoz berish usulini tanlang:</b>",
        reply_markup=vote_kb()
    )


# ============================================================
# HAVOLA ORQALI OVOZ
# ============================================================

@dp.callback_query(F.data == "vote_link")
async def vote_link_callback(
    callback: CallbackQuery
):

    url = setting("vote_url")

    if not url:

        await callback.message.answer(
            "❌ Hozircha ovoz berish havolasi "
            "admin tomonidan qo‘shilmagan."
        )

    else:

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔗 Ovoz berish",
                        url=url
                    )
                ]
            ]
        )

        await callback.message.answer(
            "🔗 <b>Ovoz berish uchun quyidagi tugmani bosing:</b>",
            reply_markup=keyboard
        )

    await callback.answer()


# ============================================================
# TELEFON ORQALI OVOZ
# ============================================================

@dp.callback_query(F.data == "vote_phone")
async def vote_phone_callback(
    callback: CallbackQuery,
    state: FSMContext
):

    await state.set_state(
        UserStates.phone
    )

    await callback.message.answer(
        "📱 <b>Telefon raqamingizni yuboring.</b>\n\n"
        "Masalan:\n"
        "<code>+998901234567</code>"
    )

    await callback.answer()


@dp.message(UserStates.phone)
async def phone_received(
    message: Message,
    state: FSMContext
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

    with closing(db()) as c:

        used = c.execute(
            "SELECT phone FROM used_phones WHERE phone=?",
            (phone,)
        ).fetchone()

        if used:

            await state.clear()

            await message.answer(
                "❌ Bu telefon raqami avval ishlatilgan.",
                reply_markup=user_kb()
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
            VOTE_REWARD
        ))

        vote_id = c.execute(
            "SELECT last_insert_rowid()"
        ).fetchone()[0]

        c.execute("""
            INSERT INTO chats(
                user_id,
                status
            )
            VALUES(?, 'open')
            ON CONFLICT(user_id)
            DO UPDATE SET status='open'
        """, (
            message.from_user.id,
        ))

        c.commit()

    await state.clear()

    await message.answer(
        "✅ <b>Telefon raqamingiz qabul qilindi.</b>\n\n"
        "Admin tekshirganidan keyin tasdiqlanadi.\n"
        f"✅ Tasdiqlansa <b>{money(VOTE_REWARD)} so‘m</b> "
        "balansingizga qo‘shiladi.",
        reply_markup=user_kb()
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

        try:

            await bot.send_message(
                admin_id,
                admin_text,
                reply_markup=vote_admin_kb(vote_id)
            )

        except Exception:

            logger.exception(
                "Admin notification error"
            )


# ============================================================
# OVOZNI TASDIQLASH
# ============================================================

@dp.callback_query(F.data.startswith("va:"))
async def vote_approve(
    callback: CallbackQuery
):

    if not is_admin(callback.from_user.id):

        await callback.answer(
            "Ruxsat yo‘q!",
            show_alert=True
        )

        return

    try:
        vote_id = int(
            callback.data.split(":")[1]
        )
    except (ValueError, IndexError):
        await callback.answer(
            "Noto‘g‘ri ovoz ID.",
            show_alert=True
        )
        return

    with closing(db()) as c:

        vote = c.execute(
            "SELECT * FROM votes WHERE id=?",
            (vote_id,)
        ).fetchone()

        if not vote:

            await callback.answer(
                "Ovoz topilmadi.",
                show_alert=True
            )

            return

        if vote[4] != "pending":

            await callback.answer(
                "Bu ovoz allaqachon ko‘rib chiqilgan.",
                show_alert=True
            )

            return

        used = c.execute(
            "SELECT phone FROM used_phones WHERE phone=?",
            (vote[3],)
        ).fetchone()

        if used:

            c.execute("""
                UPDATE votes
                SET status='rejected'
                WHERE id=?
            """, (
                vote_id,
            ))

            c.commit()

            await callback.message.edit_reply_markup(
                reply_markup=None
            )

            await callback.answer(
                "Bu raqam oldin ishlatilgan.",
                show_alert=True
            )

            return

        c.execute("""
            UPDATE votes
            SET status='approved'
            WHERE id=?
        """, (
            vote_id,
        ))

        c.execute("""
            INSERT INTO used_phones(
                phone,
                user_id,
                vote_id
            )
            VALUES(?,?,?)
        """, (
            vote[3],
            vote[1],
            vote_id
        ))

        c.execute("""
            UPDATE users
            SET balance=balance+?
            WHERE user_id=?
        """, (
            VOTE_REWARD,
            vote[1]
        ))

        c.commit()

    await callback.message.edit_reply_markup(
        reply_markup=None
    )

    try:

        await bot.send_message(
            vote[1],
            "🎉 <b>Ovozingiz tasdiqlandi!</b>\n\n"
            f"💰 Balansingizga "
            f"<b>+{money(VOTE_REWARD)} so‘m</b> qo‘shildi."
        )

    except Exception:
        pass

    await callback.answer(
        "Ovoz tasdiqlandi!"
    )


# ============================================================
# OVOZNI RAD ETISH
# ============================================================

@dp.callback_query(F.data.startswith("vr:"))
async def vote_reject(
    callback: CallbackQuery
):

    if not is_admin(callback.from_user.id):

        await callback.answer(
            "Ruxsat yo‘q!",
            show_alert=True
        )

        return

    try:
        vote_id = int(
            callback.data.split(":")[1]
        )
    except (ValueError, IndexError):
        await callback.answer(
            "Noto‘g‘ri ovoz ID.",
            show_alert=True
        )
        return

    with closing(db()) as c:

        vote = c.execute(
            "SELECT * FROM votes WHERE id=?",
            (vote_id,)
        ).fetchone()

        if not vote:

            await callback.answer(
                "Ovoz topilmadi.",
                show_alert=True
            )

            return

        if vote[4] != "pending":

            await callback.answer(
                "Bu ovoz allaqachon ko‘rib chiqilgan.",
                show_alert=True
            )

            return

        c.execute("""
            UPDATE votes
            SET status='rejected'
            WHERE id=?
        """, (
            vote_id,
        ))

        c.commit()

    await callback.message.edit_reply_markup(
        reply_markup=None
    )

    try:

        await bot.send_message(
            vote[1],
            "❌ <b>Ovozingiz tasdiqlanmadi.</b>\n\n"
            "Qo‘shimcha ma’lumot uchun admin bilan bog‘lanishingiz mumkin."
        )

    except Exception:
        pass

    await callback.answer(
        "Ovoz rad etildi."
    )


# ============================================================
# BALANS
# ============================================================

@dp.message(F.text == "💰 Balans")
async def balance_handler(
    message: Message
):

    if is_admin(message.from_user.id):
        return

    user = user_row(
        message.from_user.id
    )

    balance = (
        user[3]
        if user
        else 0
    )

    await message.answer(
        "💰 <b>SIZNING BALANSINGIZ</b>\n\n"
        f"💵 Balans: <b>{money(balance)} so‘m</b>\n\n"
        "💳 <b>BALANSDAGI PULNI YECHISH UCHUN "
        "BALANSDA KAMIDA 30 MING SO‘M BO‘LISHI KERAK.</b>\n\n"
        "🗳 Balansni to‘ldirish uchun ovoz bering.\n\n"
        f"Har bir tasdiqlangan ovoz uchun "
        f"<b>{money(VOTE_REWARD)} so‘m</b>.\n"
        f"Har bir haqiqiy referral uchun "
        f"<b>{money(REFERRAL_REWARD)} so‘m</b>."
    )


# ============================================================
# REFERAL / DO‘STLARNI TAKLIF QILISH
# ============================================================

@dp.message(F.text == "👥 Do‘stlarni taklif qilish")
async def referral_handler(
    message: Message
):

    if is_admin(message.from_user.id):
        return

    try:

        me = await bot.get_me()

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
            user[4]
            if user
            else 0
        )

        share_url = (
            "https://t.me/share/url"
            f"?url={quote(link, safe='')}"
            f"&text={quote('🎁 Botga qo‘shiling va bonus oling!')}"
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="👥 Do‘stlarni tanlash",
                        url=share_url
                    )
                ]
            ]
        )

        await message.answer(
            "👥 <b>DO‘STLARNI TAKLIF QILISH</b>\n\n"
            "Quyidagi tugmani bosing va Telegram orqali "
            "do‘stlaringizni tanlab bot havolasini yuboring.\n\n"
            f"🔗 Sizning referral havolangiz:\n"
            f"<code>{escape(link)}</code>\n\n"
            f"👥 Taklif qilinganlar: <b>{referrals}</b>\n"
            f"💰 Har bir haqiqiy do‘st uchun "
            f"<b>{money(REFERRAL_REWARD)} so‘m</b>.",
            reply_markup=keyboard
        )

    except Exception:

        logger.exception(
            "Referral error"
        )

        await message.answer(
            "❌ Taklif havolasini yaratishda xatolik yuz berdi."
        )


# ============================================================
# PUL YECHISH
# ============================================================

@dp.message(F.text == "💳 Pul yechish")
async def withdraw_start(
    message: Message,
    state: FSMContext
):

    if is_admin(message.from_user.id):
        return

    user = user_row(
        message.from_user.id
    )

    balance = (
        user[3]
        if user
        else 0
    )

    if balance < MIN_WITHDRAW:

        await message.answer(
            "❌ <b>Hozirgi balansingizda yetarli mablag‘ yo‘q.</b>\n\n"
            f"Pul yechish uchun kamida "
            f"<b>{money(MIN_WITHDRAW)} so‘m</b> kerak.\n\n"
            "🗳 Ko‘proq ovoz berib balansingizni to‘ldiring."
        )

        return

    await state.set_state(
        UserStates.card
    )

    await message.answer(
        "💳 <b>Karta raqamingizni yuboring.</b>\n\n"
        "Masalan:\n"
        "<code>8600123456789012</code>"
    )


@dp.message(UserStates.card)
async def card_received(
    message: Message,
    state: FSMContext
):

    card = re.sub(
        r"\D",
        "",
        message.text or ""
    )

    if not 12 <= len(card) <= 19:

        await message.answer(
            "❌ Karta raqami noto‘g‘ri.\n"
            "Qaytadan yuboring."
        )

        return

    user = user_row(
        message.from_user.id
    )

    if (
        not user
        or user[3] < MIN_WITHDRAW
    ):

        await state.clear()

        await message.answer(
            "❌ Balansingiz yetarli emas.",
            reply_markup=user_kb()
        )

        return

    amount = user[3]

    with closing(db()) as c:

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
            card
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
        reply_markup=user_kb()
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

        try:

            await bot.send_message(
                admin_id,
                admin_text,
                reply_markup=withdraw_kb(
                    withdrawal_id
                )
            )

        except Exception:
            pass


# ============================================================
# PUL TO‘LANDI
# ============================================================

@dp.callback_query(F.data.startswith("wp:"))
async def withdrawal_paid(
    callback: CallbackQuery
):

    if not is_admin(callback.from_user.id):

        await callback.answer(
            "Ruxsat yo‘q!",
            show_alert=True
        )

        return

    try:
        withdrawal_id = int(
            callback.data.split(":")[1]
        )
    except (ValueError, IndexError):

        await callback.answer(
            "Noto‘g‘ri ariza ID.",
            show_alert=True
        )

        return

    with closing(db()) as c:

        withdrawal = c.execute(
            "SELECT * FROM withdrawals WHERE id=?",
            (withdrawal_id,)
        ).fetchone()

        if not withdrawal:

            await callback.answer(
                "Ariza topilmadi.",
                show_alert=True
            )

            return

        if withdrawal[4] != "pending":

            await callback.answer(
                "Bu ariza allaqachon ko‘rib chiqilgan.",
                show_alert=True
            )

            return

        user = c.execute(
            "SELECT balance FROM users WHERE user_id=?",
            (withdrawal[1],)
        ).fetchone()

        if (
            not user
            or user[0] < withdrawal[2]
        ):

            await callback.answer(
                "Foydalanuvchi balansida mablag‘ yetarli emas.",
                show_alert=True
            )

            return

        c.execute("""
            UPDATE users
            SET balance=balance-?
            WHERE user_id=?
        """, (
            withdrawal[2],
            withdrawal[1]
        ))

        c.execute("""
            UPDATE withdrawals
            SET status='paid'
            WHERE id=?
        """, (
            withdrawal_id,
        ))

        c.commit()

    await callback.message.edit_reply_markup(
        reply_markup=None
    )

    try:

        await bot.send_message(
            withdrawal[1],
            "✅ <b>Pul yechish arizangiz to‘landi.</b>\n\n"
            f"💰 Summa: <b>{money(withdrawal[2])} so‘m</b>"
        )

    except Exception:
        pass

    await callback.answer(
        "To‘landi!"
    )


# ============================================================
# PULNI RAD ETISH
# ============================================================

@dp.callback_query(F.data.startswith("wr:"))
async def withdrawal_reject(
    callback: CallbackQuery
):

    if not is_admin(callback.from_user.id):

        await callback.answer(
            "Ruxsat yo‘q!",
            show_alert=True
        )

        return

    try:
        withdrawal_id = int(
            callback.data.split(":")[1]
        )
    except (ValueError, IndexError):

        await callback.answer(
            "Noto‘g‘ri ariza ID.",
            show_alert=True
        )

        return

    with closing(db()) as c:

        withdrawal = c.execute(
            "SELECT * FROM withdrawals WHERE id=?",
            (withdrawal_id,)
        ).fetchone()

        if not withdrawal:

            await callback.answer(
                "Ariza topilmadi.",
                show_alert=True
            )

            return

        if withdrawal[4] != "pending":

            await callback.answer(
                "Bu ariza allaqachon ko‘rib chiqilgan.",
                show_alert=True
            )

            return

        c.execute("""
            UPDATE withdrawals
            SET status='rejected'
            WHERE id=?
        """, (
            withdrawal_id,
        ))

        c.commit()

    await callback.message.edit_reply_markup(
        reply_markup=None
    )

    try:

        await bot.send_message(
            withdrawal[1],
            "❌ <b>Pul yechish arizangiz rad etildi.</b>"
        )

    except Exception:
        pass

    await callback.answer(
        "Rad etildi."
    )


# ============================================================
# SAVOL-JAVOB
# ============================================================

@dp.message(F.text == "❓ Savol-javob")
async def question_start(
    message: Message,
    state: FSMContext
):

    if is_admin(message.from_user.id):
        return

    await state.set_state(
        UserStates.question
    )

    await message.answer(
        "❓ <b>Savolingizni yozing.</b>\n\n"
        "Savolingiz adminlarga yuboriladi."
    )


async def send_to_admins_for_chat(
    message: Message,
    text: str
):

    user = message.from_user

    with closing(db()) as c:

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
            text
        ))

        c.execute("""
            INSERT INTO chats(
                user_id,
                status
            )
            VALUES(?, 'open')
            ON CONFLICT(user_id)
            DO UPDATE SET status='open'
        """, (
            user.id,
        ))

        c.commit()

    for admin_id in ADMIN_IDS:

        try:

            await bot.send_message(
                admin_id,
                "💬 <b>FOYDALANUVCHIDAN XABAR</b>\n\n"
                f"👤 Ism: {escape(user.first_name or '')}\n"
                f"🆔 ID: <code>{user.id}</code>\n"
                f"👤 Username: @{escape(user.username or 'yo‘q')}\n\n"
                f"💬 {escape(text)}",
                reply_markup=chat_kb(user.id)
            )

        except Exception:
            pass


@dp.message(UserStates.question)
async def question_received(
    message: Message,
    state: FSMContext
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
        text
    )

    await message.answer(
        "✅ <b>Savolingiz adminga yuborildi.</b>\n\n"
        "Admin javobi shu yerga keladi.",
        reply_markup=user_kb()
    )


# ============================================================
# ADMIN JAVOB BERISH
# ============================================================

@dp.callback_query(F.data.startswith("reply:"))
async def reply_start(
    callback: CallbackQuery,
    state: FSMContext
):

    if not is_admin(callback.from_user.id):

        await callback.answer(
            "Ruxsat yo‘q!",
            show_alert=True
        )

        return

    try:
        user_id = int(
            callback.data.split(":")[1]
        )
    except (ValueError, IndexError):

        await callback.answer(
            "Noto‘g‘ri User ID.",
            show_alert=True
        )

        return

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

    await callback.answer()


@dp.message(AdminStates.reply)
async def admin_reply(
    message: Message,
    state: FSMContext
):

    if not is_admin(message.from_user.id):
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

    try:

        await bot.send_message(
            user_id,
            "👨‍💻 <b>Admin javobi:</b>\n\n"
            f"{escape(text)}"
        )

        with closing(db()) as c:

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
                text
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
                message.from_user.id
            ))

            c.commit()

        await message.answer(
            "✅ <b>Javob foydalanuvchiga yuborildi.</b>",
            reply_markup=admin_kb()
        )

    except Exception:

        await message.answer(
            "❌ Foydalanuvchiga xabar yuborilmadi."
        )

    await state.clear()


# ============================================================
# SUHBATNI YOPISH
# ============================================================

@dp.callback_query(F.data.startswith("close:"))
async def close_chat(
    callback: CallbackQuery
):

    if not is_admin(callback.from_user.id):

        await callback.answer(
            "Ruxsat yo‘q!",
            show_alert=True
        )

        return

    try:
        user_id = int(
            callback.data.split(":")[1]
        )
    except (ValueError, IndexError):

        await callback.answer(
            "Noto‘g‘ri User ID.",
            show_alert=True
        )

        return

    with closing(db()) as c:

        c.execute("""
            UPDATE chats
            SET status='closed',
                admin_id=?
            WHERE user_id=?
        """, (
            callback.from_user.id,
            user_id
        ))

        c.commit()

    try:

        await bot.send_message(
            user_id,
            "🔒 <b>Admin suhbatni yopdi.</b>\n\n"
            "Yangi savol bo‘lsa, "
            "❓ Savol-javob bo‘limidan foydalaning."
        )

    except Exception:
        pass

    await callback.message.answer(
        "🔒 <b>Suhbat yopildi.</b>"
    )

    await callback.answer(
        "Yopildi"
    )


# ============================================================
# ADMIN BILAN BOG‘LANISH
# ============================================================

@dp.message(F.text == "👨‍💻 Admin bilan bog‘lanish")
async def admin_contact_handler(
    message: Message
):

    if is_admin(message.from_user.id):
        return

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
            "ℹ️ <b>Hozircha admin qo‘shilmagan.</b>\n\n"
            "Yoki hozir barcha adminlar band."
        )


# ============================================================
# ADMIN STATISTIKA
# ============================================================

@dp.message(F.text == "📊 Statistika")
async def statistics(
    message: Message
):

    if not is_admin(message.from_user.id):
        return

    with closing(db()) as c:

        users = c.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]

        votes = c.execute(
            "SELECT COUNT(*) FROM votes"
        ).fetchone()[0]

        approved = c.execute("""
            SELECT COUNT(*)
            FROM votes
            WHERE status='approved'
        """).fetchone()[0]

        pending = c.execute("""
            SELECT COUNT(*)
            FROM votes
            WHERE status='pending'
        """).fetchone()[0]

        referrals = c.execute(
            "SELECT COUNT(*) FROM referrals"
        ).fetchone()[0]

        referral_money = c.execute("""
            SELECT COALESCE(SUM(reward),0)
            FROM referrals
        """).fetchone()[0]

        total_balance = c.execute("""
            SELECT COALESCE(SUM(balance),0)
            FROM users
        """).fetchone()[0]

        pending_withdrawals = c.execute("""
            SELECT COUNT(*)
            FROM withdrawals
            WHERE status='pending'
        """).fetchone()[0]

        paid_money = c.execute("""
            SELECT COALESCE(SUM(amount),0)
            FROM withdrawals
            WHERE status='paid'
        """).fetchone()[0]

    await message.answer(
        "📊 <b>BOT STATISTIKASI</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{users}</b>\n"
        f"🗳 Jami ovozlar: <b>{votes}</b>\n"
        f"✅ Tasdiqlangan ovozlar: <b>{approved}</b>\n"
        f"⏳ Kutilayotgan ovozlar: <b>{pending}</b>\n\n"
        f"👥 Referallar: <b>{referrals}</b>\n"
        f"💰 Referral mukofoti: "
        f"<b>{money(referral_money)} so‘m</b>\n\n"
        f"💵 Foydalanuvchilar balanslari: "
        f"<b>{money(total_balance)} so‘m</b>\n\n"
        f"💳 Kutilayotgan pul yechishlar: "
        f"<b>{pending_withdrawals}</b>\n"
        f"💸 To‘langan: "
        f"<b>{money(paid_money)} so‘m</b>"
    )


# ============================================================
# ADMIN FOYDALANUVCHILAR
# ============================================================

@dp.message(F.text == "👥 Foydalanuvchilar")
async def admin_users(
    message: Message
):

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
            "👥 Foydalanuvchilar yo‘q."
        )

        return

    text = "👥 <b>FOYDALANUVCHILAR</b>\n\n"

    for row in rows:

        text += (
            f"👤 {escape(row[1] or '')}\n"
            f"🆔 <code>{row[0]}</code>\n"
            f"👤 @{escape(row[2] or 'yo‘q')}\n"
            f"💰 {money(row[3])} so‘m\n"
            f"👥 Referral: {row[4]}\n"
            f"────────────\n"
        )

    await message.answer(
        text
    )


# ============================================================
# ADMIN OVOZLAR
# ============================================================

@dp.message(F.text == "🗳 Ovozlar")
async def admin_votes(
    message: Message
):

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
            ORDER BY v.id DESC
            LIMIT 30
        """).fetchall()

    if not rows:

        await message.answer(
            "🗳 Ovozlar yo‘q."
        )

        return

    for row in rows:

        text = (
            f"🗳 <b>Ovoz #{row[0]}</b>\n\n"
            f"👤 {escape(row[5] or '')}\n"
            f"🆔 <code>{row[1]}</code>\n"
            f"📞 <code>{escape(row[2] or '-')}</code>\n"
            f"📊 Holat: <b>{row[3]}</b>\n"
            f"💰 {money(row[4])} so‘m"
        )

        keyboard = None

        if row[3] == "pending":

            keyboard = vote_admin_kb(
                row[0]
            )

        await message.answer(
            text,
            reply_markup=keyboard
        )


# ============================================================
# TELEFON OVOZLARI
# ============================================================

@dp.message(F.text == "📱 Telefon ovozlari")
async def admin_phone_votes(
    message: Message
):

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
            "📱 Telefon ovozlari yo‘q."
        )

        return

    for row in rows:

        keyboard = None

        if row[3] == "pending":

            keyboard = vote_admin_kb(
                row[0]
            )

        await message.answer(
            f"📱 <b>Telefon ovozi #{row[0]}</b>\n\n"
            f"👤 {escape(row[5] or '')}\n"
            f"🆔 <code>{row[1]}</code>\n"
            f"📞 <code>{escape(row[2] or '')}</code>\n"
            f"📊 Holat: <b>{row[3]}</b>\n"
            f"💰 {money(row[4])} so‘m",
            reply_markup=keyboard
        )


# ============================================================
# REFERALLAR
# ============================================================

@dp.message(F.text == "👥 Referallar")
async def admin_referrals(
    message: Message
):

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
            "👥 Referallar yo‘q."
        )

        return

    text = "👥 <b>REFERALLAR</b>\n\n"

    for row in rows:

        text += (
            f"👤 Taklif qiluvchi: "
            f"<code>{row[0]}</code>\n"
            f"👤 Taklif qilingan: "
            f"<code>{row[1]}</code>\n"
            f"💰 Mukofot: "
            f"{money(row[2])} so‘m\n"
            f"────────────\n"
        )

    await message.answer(
        text
    )


# ============================================================
# PUL YECHISH ARIZALARI
# ============================================================

@dp.message(F.text == "💳 Pul yechishlar")
async def admin_withdrawals(
    message: Message
):

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
            "💳 Pul yechish arizalari yo‘q."
        )

        return

    for row in rows:

        keyboard = None

        if row[4] == "pending":

            keyboard = withdraw_kb(
                row[0]
            )

        await message.answer(
            f"💳 <b>Ariza #{row[0]}</b>\n\n"
            f"👤 {escape(row[5] or '')}\n"
            f"🆔 <code>{row[1]}</code>\n"
            f"💰 {money(row[2])} so‘m\n"
            f"💳 <code>{row[3]}</code>\n"
            f"📊 Holat: <b>{row[4]}</b>",
            reply_markup=keyboard
        )


# ============================================================
# ADMIN SAVOLLARI
# ============================================================

@dp.message(F.text == "❓ Savollar")
async def admin_questions(
    message: Message
):

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
            "❓ Savollar yo‘q."
        )

        return

    for row in rows:

        await message.answer(
            "❓ <b>FOYDALANUVCHI SAVOLI</b>\n\n"
            f"👤 {escape(row[3] or '')}\n"
            f"🆔 <code>{row[0]}</code>\n\n"
            f"💬 {escape(row[1])}",
            reply_markup=chat_kb(row[0])
        )


# ============================================================
# OVOZ HAVOLASINI SOZLASH
# ============================================================

@dp.message(F.text == "🔗 Ovoz havolasi")
async def vote_url_start(
    message: Message,
    state: FSMContext
):

    if not is_admin(message.from_user.id):
        return

    await state.set_state(
        AdminStates.vote_url
    )

    await message.answer(
        "🔗 <b>Yangi ovoz havolasini yuboring.</b>\n\n"
        f"Hozirgi havola:\n"
        f"{escape(setting('vote_url', 'Hali qo‘shilmagan'))}"
    )


@dp.message(AdminStates.vote_url)
async def vote_url_save(
    message: Message,
    state: FSMContext
):

    if not is_admin(message.from_user.id):
        return

    url = (
        message.text or ""
    ).strip()

    if not re.match(
        r"^https?://",
        url
    ):

        await message.answer(
            "❌ Havola http:// yoki https:// bilan boshlanishi kerak."
        )

        return

    set_setting(
        "vote_url",
        url
    )

    await state.clear()

    await message.answer(
        "✅ <b>Ovoz havolasi saqlandi.</b>",
        reply_markup=admin_kb()
    )


# ============================================================
# ADMIN KONTAKTINI SOZLASH
# ============================================================

@dp.message(F.text == "👨‍💻 Admin kontakt")
async def contact_start(
    message: Message,
    state: FSMContext
):

    if not is_admin(message.from_user.id):
        return

    await state.set_state(
        AdminStates.contact
    )

    await message.answer(
        "👨‍💻 <b>Admin Telegram username yoki "
        "telefon raqamini yuboring.</b>\n\n"
        f"Hozirgi:\n"
        f"{escape(setting('admin_contact', 'Hali qo‘shilmagan'))}"
    )


@dp.message(AdminStates.contact)
async def contact_save(
    message: Message,
    state: FSMContext
):

    if not is_admin(message.from_user.id):
        return

    contact = (
        message.text or ""
    ).strip()

    if not contact:

        await message.answer(
            "❌ Kontaktni yozing."
        )

        return

    set_setting(
        "admin_contact",
        contact
    )

    await state.clear()

    await message.answer(
        "✅ <b>Admin kontakti saqlandi.</b>",
        reply_markup=admin_kb()
    )


# ============================================================
# LOYIHA QO‘SHISH
# ============================================================

@dp.message(F.text == "➕ Loyiha qo‘shish")
async def project_start(
    message: Message,
    state: FSMContext
):

    if not is_admin(message.from_user.id):
        return

    await state.set_state(
        AdminStates.project_name
    )

    await message.answer(
        "➕ <b>Loyiha nomini yozing.</b>"
    )


@dp.message(AdminStates.project_name)
async def project_name_received(
    message: Message,
    state: FSMContext
):

    if not is_admin(message.from_user.id):
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


@dp.message(AdminStates.project_url)
async def project_url_received(
    message: Message,
    state: FSMContext
):

    if not is_admin(message.from_user.id):
        return

    url = (
        message.text or ""
    ).strip()

    if not re.match(
        r"^https?://",
        url
    ):

        await message.answer(
            "❌ Havola http:// yoki https:// bilan boshlanishi kerak."
        )

        return

    data = await state.get_data()

    name = data.get(
        "project_name"
    )

    if not name:

        await state.clear()

        await message.answer(
            "❌ Loyiha ma’lumoti topilmadi."
        )

        return

    with closing(db()) as c:

        c.execute("""
            INSERT INTO projects(
                name,
                url,
                active
            )
            VALUES(?,?,1)
        """, (
            name,
            url
        ))

        c.commit()

    await state.clear()

    await message.answer(
        "✅ <b>Loyiha muvaffaqiyatli qo‘shildi.</b>\n\n"
        f"📌 {escape(name)}\n"
        f"🔗 {escape(url)}",
        reply_markup=admin_kb()
    )


# ============================================================
# REKLAMA
# ============================================================

@dp.message(F.text == "📢 Reklama")
async def broadcast_start(
    message: Message,
    state: FSMContext
):

    if not is_admin(message.from_user.id):
        return

    await state.set_state(
        AdminStates.broadcast
    )

    await message.answer(
        "📢 <b>Yuboriladigan xabarni yozing.</b>"
    )


@dp.message(AdminStates.broadcast)
async def broadcast_received(
    message: Message,
    state: FSMContext
):

    if not is_admin(message.from_user.id):
        return

    text = (
        message.text or ""
    ).strip()

    if not text:

        await message.answer(
            "❌ Xabar matnini yuboring."
        )

        return

    with closing(db()) as c:

        users = c.execute(
            "SELECT user_id FROM users"
        ).fetchall()

    sent = 0
    failed = 0

    for row in users:

        try:

            await bot.send_message(
                row[0],
                text
            )

            sent += 1

            await asyncio.sleep(0.05)

        except Exception:

            failed += 1

    await state.clear()

    await message.answer(
        "📢 <b>Reklama yakunlandi.</b>\n\n"
        f"✅ Yuborildi: <b>{sent}</b>\n"
        f"❌ Yuborilmadi: <b>{failed}</b>",
        reply_markup=admin_kb()
    )


# ============================================================
# OCHIQ CHATDA FOYDALANUVCHI JAVOBI
# ============================================================

@dp.message()
async def remaining_messages(
    message: Message
):

    if is_admin(message.from_user.id):
        return

    with closing(db()) as c:

        chat = c.execute("""
            SELECT status
            FROM chats
            WHERE user_id=?
        """, (
            message.from_user.id,
        )).fetchone()

    if not chat:
        return

    if chat[0] != "open":
        return

    text = (
        message.text or ""
    ).strip()

    if not text:
        return

    await send_to_admins_for_chat(
        message,
        text
    )


# ============================================================
# ISHGA TUSHIRISH
# ============================================================

async def main():

    if (
        not BOT_TOKEN
        or BOT_TOKEN == "BU_YERGA_YANGI_BOT_TOKENINGIZNI_QOYING"
    ):

        raise RuntimeError(
            "BOT_TOKEN main.py ichiga qo‘yilmagan!"
        )

    if (
        not ADMIN_IDS
        or ADMIN_IDS == {123456789}
    ):

        raise RuntimeError(
            "ADMIN_IDS ichiga haqiqiy Telegram ID qo‘yilmagan!"
        )

    if (
        not ISBOT_KANAL_URL
        or ISBOT_KANAL_URL == "https://t.me/SIZNING_ISBOT_KANALINGIZ"
    ):

        logger.warning(
            "ISBOT_KANAL_URL hali o‘zgartirilmagan!"
        )

    init_db()

    await bot.delete_webhook(
        drop_pending_updates=True
    )

    logger.info(
        "BOT ISHLADI"
    )

    await dp.start_polling(
        bot
    )


if __name__ == "__main__":

    asyncio.run(
        main()
    )