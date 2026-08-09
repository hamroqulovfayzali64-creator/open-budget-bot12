import asyncio
import logging
import sqlite3
import os
import re
from pathlib import Path
from contextlib import closing
from html import escape
from urllib.parse import urlparse

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

print("MAIN.PY ISHLAYAPTI", flush=True)

# TOKENNI SHU YERGA YOZING
BOT_TOKEN = "8615736731:AAF7LGgYsKCq_JjV9qFPmFV6psTAS4mlQ_g"

# ADMIN ID LARNI SHU YERGA YOZING
# Bir nechta admin bo'lsa: "123456789,987654321"
ADMIN_IDS_TEXT = "7998053914"

ADMIN_IDS = set()

for item in ADMIN_IDS_TEXT.replace(";", ",").split(","):
    item = item.strip()
    if item.isdigit():
        ADMIN_IDS.add(int(item))

# Ovoz uchun mukofot
VOTE_REWARD = 20_000

# Referal mukofoti
REFERRAL_REWARD = 5_000

# Minimal pul yechish
MIN_WITHDRAW = 20_000

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "bot.db"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)

if not BOT_TOKEN or BOT_TOKEN == "BU_YERGA_BOT_TOKENINGIZNI_YOZING":
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
            "{vote_reward} so'm hisobingizga qo'shiladi.\n\n"
            "Kerakli bo'limni tanlang:"
        ),

        "projects": "📌 Loyihalar",
        "news": "📰 Yangiliklar",
        "help": "❓ Yordam",
        "language": "🌐 Til",
        "balance": "💰 Balans",
        "referral": "🔗 Referal ssilka",
        "withdraw": "💸 Pul yechish",
        "group_add": "👥 Guruhga qo'shish",

        "statistics": "📊 Statistika",
        "add_project": "➕ Loyiha qo'shish",
        "add_news": "📰 Yangilik qo'shish",
        "broadcast": "📢 Reklama tarqatish",
        "withdrawals": "💸 Yechishlar",
        "back": "🔙 Orqaga",
        "admin_panel": "⚙️ Admin panel",

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

        "open_project": "🔗 Loyihani ochish",
        "vote": "🗳 Ovoz berish",

        "project_not_found": "❌ Loyiha topilmadi.",

        # MUHIM QISM
        "phone_required": (
            "📞 <b>Ovoz berish uchun telefon raqamingizni kiriting:</b>\n\n"
            "Telefon raqami <code>+998991234567</code> yoki "
            "<code>991234567</code> formatida kiritilishi kerak."
        ),

        "phone_invalid": (
            "❌ Telefon raqami noto'g'ri.\n\n"
            "Quyidagi formatlardan foydalaning:\n"
            "<code>+998991234567</code>\n"
            "yoki\n"
            "<code>991234567</code>"
        ),

        "vote_sent_admin": (
            "⏳ Telefon raqamingiz qabul qilindi.\n\n"
            "👨‍💼 Admin tomonidan tekshirilmoqda.\n"
            "Admin tasdiqlagandan keyin balansingizga "
            "{amount} so'm qo'shiladi."
        ),

        "vote_pending": (
            "⏳ Bu loyiha uchun ovozingiz allaqachon admin tekshiruvini kutmoqda."
        ),

        "vote_approved": (
            "🎉 <b>Ovozingiz tasdiqlandi!</b>\n\n"
            "💰 Balansingizga <b>{amount} so'm</b> qo'shildi."
        ),

        "vote_rejected": (
            "❌ <b>Ovozingiz admin tomonidan rad etildi.</b>"
        ),

        "admin_vote_request": (
            "🗳 <b>Yangi ovoz tasdiqlash so'rovi</b>\n\n"
            "👤 Foydalanuvchi: {user}\n"
            "🆔 User ID: <code>{user_id}</code>\n"
            "📌 Loyiha: <b>{project}</b>\n"
            "📞 Telefon: <code>{phone}</code>\n\n"
            "⚠️ Telefon raqamini tashqi xizmat orqali tekshirib, "
            "so'ng tugmalardan birini bosing."
        ),

        "admin_approved": "✅ Ovoz tasdiqlandi.",
        "admin_rejected": "❌ Ovoz rad etildi.",
        "request_not_found": "❌ So'rov topilmadi yoki allaqachon ko'rib chiqilgan.",

        "help_text": (
            "❓ <b>Yordam</b>\n\n"
            "📌 Loyihalar — mavjud loyihalarni ko'rish.\n"
            "🗳 Ovoz berish — loyiha uchun ovoz berish.\n"
            "💰 Balans — balansni ko'rish.\n"
            "🔗 Referal — do'stlarni taklif qilish.\n"
            "💸 Pul yechish — pul yechish so'rovi.\n"
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
            "📢 Barcha foydalanuvchilarga yuboriladigan xabarni yuboring."
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
            "📰 Yangiliklar: {news}\n"
            "💰 Umumiy balans: {balance} so'm"
        ),

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
        "not_enough": "❌ Balansingiz yetarli emas.",

        "withdraw_info": (
            "💳 To'lov uchun rekvizitingizni yuboring.\n\n"
            "Masalan: telefon yoki wallet ID."
        ),

        "withdraw_created": (
            "✅ Pul yechish so'rovi yuborildi.\n\n"
            "💰 Summa: {amount} so'm\n"
            "🆔 So'rov: #{request_id}"
        ),

        "cancel": "❌ Bekor qilindi.",
        "back_menu": "🔙 Asosiy menyu.",

        "no_pending_withdrawals": "⏳ Kutilayotgan so'rovlar yo'q.",
    }
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
                phone TEXT NOT NULL,
                reward INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP,
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
                referrer_id INTEGER,
                referred_id INTEGER UNIQUE,
                bonus INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending'
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

        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_votes_user_project
            ON votes(user_id, project_id)
        """)

        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_votes_status
            ON votes(status)
        """)

        db.commit()

    print("DATABASE TAYYOR", flush=True)


# =========================================================
# USER
# =========================================================

def add_or_update_user(message: Message):

    if not message.from_user:
        return

    user = message.from_user

    with closing(get_db()) as db:

        db.execute("""
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
            user.id,
            user.username,
            user.first_name
        ))

        db.commit()


def get_language(user_id):

    with closing(get_db()) as db:

        row = db.execute(
            "SELECT language FROM users WHERE user_id=?",
            (user_id,)
        ).fetchone()

        if row and row["language"] in ("uz", "ru"):
            return row["language"]

    return "uz"


def set_language(user_id, language):

    with closing(get_db()) as db:

        db.execute(
            "UPDATE users SET language=? WHERE user_id=?",
            (language, user_id)
        )

        db.commit()


def is_admin(user_id):

    return user_id in ADMIN_IDS


def format_money(value):

    return f"{int(value or 0):,}".replace(",", " ")


# =========================================================
# KEYBOARDS
# =========================================================

def user_keyboard():

    t = TEXTS["uz"]

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
            ]
        ],
        resize_keyboard=True
    )


def admin_keyboard():

    t = TEXTS["uz"]

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
            ]
        ],
        resize_keyboard=True
    )


def cancel_keyboard():

    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text=TEXTS["uz"]["cancel"]
                )
            ]
        ],
        resize_keyboard=True
    )


# =========================================================
# START
# =========================================================

@dp.message(CommandStart())
async def start_handler(
    message: Message,
    state: FSMContext,
    command: CommandObject
):

    await state.clear()

    add_or_update_user(message)

    if is_admin(message.from_user.id):

        await message.answer(
            "⚙️ Admin panel ochildi.",
            reply_markup=admin_keyboard()
        )

    else:

        await message.answer(
            TEXTS["uz"]["welcome"].format(
                name=escape(
                    message.from_user.first_name or "Foydalanuvchi"
                ),
                vote_reward=format_money(VOTE_REWARD)
            ),
            reply_markup=user_keyboard()
        )


# =========================================================
# ADMIN PANEL
# =========================================================

@dp.message(Command("admin"))
async def admin_handler(message: Message):

    add_or_update_user(message)

    if not is_admin(message.from_user.id):

        await message.answer(
            TEXTS["uz"]["admin_only"]
        )
        return

    await message.answer(
        "⚙️ <b>Admin panel</b>",
        parse_mode="HTML",
        reply_markup=admin_keyboard()
    )


# =========================================================
# PROJECTS
# =========================================================

@dp.message(F.text == "📌 Loyihalar")
async def projects_handler(message: Message):

    add_or_update_user(message)

    with closing(get_db()) as db:

        projects = db.execute("""
            SELECT *
            FROM projects
            ORDER BY id DESC
        """).fetchall()

    if not projects:

        await message.answer(
            TEXTS["uz"]["no_projects"],
            reply_markup=user_keyboard()
        )

        return

    buttons = []

    for project in projects:

        name = project["name_uz"] or "Loyiha"

        buttons.append([
            InlineKeyboardButton(
                text=f"📌 {name}",
                callback_data=f"project:{project['id']}"
            )
        ])

    await message.answer(
        TEXTS["uz"]["select_project"],
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )


@dp.callback_query(F.data.startswith("project:"))
async def project_handler(callback: CallbackQuery):

    try:
        project_id = int(
            callback.data.split(":")[1]
        )
    except:
        await callback.answer("Xatolik", show_alert=True)
        return

    with closing(get_db()) as db:

        project = db.execute(
            "SELECT * FROM projects WHERE id=?",
            (project_id,)
        ).fetchone()

        if project:

            db.execute("""
                UPDATE projects
                SET click_count=COALESCE(click_count,0)+1
                WHERE id=?
            """, (project_id,))

            db.commit()

    if not project:

        await callback.answer(
            TEXTS["uz"]["project_not_found"],
            show_alert=True
        )
        return

    keyboard = []

    if project["url"]:

        keyboard.append([
            InlineKeyboardButton(
                text=TEXTS["uz"]["open_project"],
                url=project["url"]
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            text=TEXTS["uz"]["vote"],
            callback_data=f"vote:{project_id}"
        )
    ])

    await callback.message.answer(
        f"📌 <b>{escape(project['name_uz'])}</b>\n\n"
        "🗳 Ovoz berish uchun tugmani bosing.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=keyboard
        )
    )

    await callback.answer()


# =========================================================
# OVOZ BERISH
# =========================================================

@dp.callback_query(F.data.startswith("vote:"))
async def vote_start(
    callback: CallbackQuery,
    state: FSMContext
):

    try:
        project_id = int(
            callback.data.split(":")[1]
        )
    except:

        await callback.answer(
            "Xatolik",
            show_alert=True
        )
        return

    with closing(get_db()) as db:

        project = db.execute(
            "SELECT * FROM projects WHERE id=?",
            (project_id,)
        ).fetchone()

        if not project:

            await callback.answer(
                TEXTS["uz"]["project_not_found"],
                show_alert=True
            )
            return

        # pending yoki approved bo'lsa qayta ovoz berishga ruxsat yo'q
        existing = db.execute("""
            SELECT status
            FROM votes
            WHERE user_id=? AND project_id=?
        """, (
            callback.from_user.id,
            project_id
        )).fetchone()

    if existing:

        if existing["status"] == "pending":

            await callback.answer(
                TEXTS["uz"]["vote_pending"],
                show_alert=True
            )

        elif existing["status"] == "approved":

            await callback.answer(
                "⚠️ Siz bu loyihaga allaqachon ovoz bergansiz.",
                show_alert=True
            )

        else:

            # rejected bo'lsa qayta yuborishga ruxsat
            with closing(get_db()) as db:

                db.execute("""
                    DELETE FROM votes
                    WHERE user_id=? AND project_id=?
                    AND status='rejected'
                """, (
                    callback.from_user.id,
                    project_id
                ))

                db.commit()

    await state.clear()

    await state.update_data(
        vote_project_id=project_id
    )

    await state.set_state(
        VoteStates.waiting_phone
    )

    await callback.message.answer(
        TEXTS["uz"]["phone_required"],
        parse_mode="HTML",
        reply_markup=cancel_keyboard()
    )

    await callback.answer()


# =========================================================
# TELEFON RAQAMI
# =========================================================

def normalize_phone(text):

    text = text.strip()

    # +998991234567
    if re.fullmatch(r"\+998\d{9}", text):

        return text

    # 991234567
    if re.fullmatch(r"998\d{9}", text):

        return "+" + text

    if re.fullmatch(r"\d{9}", text):

        return "+998" + text

    return None


@dp.message(VoteStates.waiting_phone)
async def receive_vote_phone(
    message: Message,
    state: FSMContext
):

    if not message.text:

        await message.answer(
            TEXTS["uz"]["phone_invalid"],
            parse_mode="HTML"
        )

        return

    phone = normalize_phone(
        message.text
    )

    if not phone:

        await message.answer(
            TEXTS["uz"]["phone_invalid"],
            parse_mode="HTML"
        )

        return

    data = await state.get_data()

    project_id = data.get(
        "vote_project_id"
    )

    if not project_id:

        await state.clear()

        return

    with closing(get_db()) as db:

        project = db.execute(
            "SELECT * FROM projects WHERE id=?",
            (project_id,)
        ).fetchone()

        if not project:

            await state.clear()

            await message.answer(
                TEXTS["uz"]["project_not_found"],
                reply_markup=user_keyboard()
            )

            return

        existing = db.execute("""
            SELECT id
            FROM votes
            WHERE user_id=? AND project_id=?
        """, (
            message.from_user.id,
            project_id
        )).fetchone()

        if existing:

            await state.clear()

            await message.answer(
                TEXTS["uz"]["vote_pending"],
                reply_markup=user_keyboard()
            )

            return

        db.execute("""
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

        db.commit()

    await state.clear()

    # Foydalanuvchiga
    await message.answer(
        TEXTS["uz"]["vote_sent_admin"].format(
            amount=format_money(VOTE_REWARD)
        ),
        reply_markup=user_keyboard()
    )

    # Adminlarga yuborish
    username = (
        f"@{message.from_user.username}"
        if message.from_user.username
        else message.from_user.first_name
        or str(message.from_user.id)
    )

    admin_text = TEXTS["uz"]["admin_vote_request"].format(
        user=escape(username),
        user_id=message.from_user.id,
        project=escape(project["name_uz"]),
        phone=escape(phone)
    )

    with closing(get_db()) as db:

        vote_row = db.execute("""
            SELECT id
            FROM votes
            WHERE user_id=? AND project_id=?
            AND status='pending'
            ORDER BY id DESC
            LIMIT 1
        """, (
            message.from_user.id,
            project_id
        )).fetchone()

    if not vote_row:
        return

    vote_id = vote_row["id"]

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Tasdiqlash",
                    callback_data=f"vote_ok:{vote_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Rad etish",
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
                "Admin xabar xatosi: %s",
                e
            )


# =========================================================
# ADMIN OVOZ TASDIQLASH
# =========================================================

@dp.callback_query(F.data.startswith("vote_ok:"))
async def approve_vote(
    callback: CallbackQuery
):

    if not is_admin(callback.from_user.id):

        await callback.answer(
            "Faqat admin.",
            show_alert=True
        )

        return

    try:

        vote_id = int(
            callback.data.split(":")[1]
        )

    except:

        await callback.answer(
            "Xatolik",
            show_alert=True
        )

        return

    with closing(get_db()) as db:

        db.execute("BEGIN IMMEDIATE")

        vote = db.execute("""
            SELECT
                v.id,
                v.user_id,
                v.project_id,
                v.reward,
                v.status,
                p.name_uz
            FROM votes v
            LEFT JOIN projects p
                ON p.id=v.project_id
            WHERE v.id=?
        """, (vote_id,)).fetchone()

        if not vote or vote["status"] != "pending":

            db.rollback()

            await callback.answer(
                TEXTS["uz"]["request_not_found"],
                show_alert=True
            )

            return

        # Ovoz tasdiqlandi
        db.execute("""
            UPDATE votes
            SET status='approved',
                processed_at=CURRENT_TIMESTAMP
            WHERE id=? AND status='pending'
        """, (vote_id,))

        # Balansga pul qo'shamiz
        db.execute("""
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

        db.execute("""
            INSERT INTO transactions (
                user_id,
                amount,
                type,
                description
            )
            VALUES (?, ?, ?, ?)
        """, (
            vote["user_id"],
            vote["reward"],
            "vote",
            f"Ovoz tasdiqlandi: {vote['name_uz']}"
        ))

        db.commit()

    # Foydalanuvchiga xabar
    try:

        await bot.send_message(
            vote["user_id"],
            TEXTS["uz"]["vote_approved"].format(
                amount=format_money(vote["reward"])
            ),
            parse_mode="HTML"
        )

    except Exception as e:

        logger.warning(
            "Userga xabar yuborilmadi: %s",
            e
        )

    try:

        await callback.message.edit_reply_markup(
            reply_markup=None
        )

    except:
        pass

    await callback.message.answer(
        "✅ Ovoz tasdiqlandi."
    )

    await callback.answer(
        TEXTS["uz"]["admin_approved"]
    )


# =========================================================
# ADMIN OVOZ RAD ETISH
# =========================================================

@dp.callback_query(F.data.startswith("vote_no:"))
async def reject_vote(
    callback: CallbackQuery
):

    if not is_admin(callback.from_user.id):

        await callback.answer(
            "Faqat admin.",
            show_alert=True
        )

        return

    try:

        vote_id = int(
            callback.data.split(":")[1]
        )

    except:

        await callback.answer(
            "Xatolik",
            show_alert=True
        )

        return

    with closing(get_db()) as db:

        vote = db.execute("""
            SELECT user_id, status
            FROM votes
            WHERE id=?
        """, (vote_id,)).fetchone()

        if not vote or vote["status"] != "pending":

            await callback.answer(
                TEXTS["uz"]["request_not_found"],
                show_alert=True
            )

            return

        db.execute("""
            UPDATE votes
            SET
                status='rejected',
                processed_at=CURRENT_TIMESTAMP
            WHERE id=? AND status='pending'
        """, (vote_id,))

        db.commit()

    try:

        await bot.send_message(
            vote["user_id"],
            TEXTS["uz"]["vote_rejected"],
            parse_mode="HTML"
        )

    except:
        pass

    try:

        await callback.message.edit_reply_markup(
            reply_markup=None
        )

    except:
        pass

    await callback.message.answer(
        "❌ Ovoz rad etildi."
    )

    await callback.answer(
        TEXTS["uz"]["admin_rejected"]
    )


# =========================================================
# BALANCE
# =========================================================

@dp.message(F.text == "💰 Balans")
async def balance_handler(message: Message):

    add_or_update_user(message)

    with closing(get_db()) as db:

        row = db.execute("""
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
        TEXTS["uz"]["balance_text"].format(
            balance=format_money(row["balance"]),
            earned=format_money(row["total_earned"]),
            withdrawn=format_money(row["total_withdrawn"])
        ),
        parse_mode="HTML",
        reply_markup=user_keyboard()
    )


# =========================================================
# REFERAL
# =========================================================

@dp.message(F.text == "🔗 Referal ssilka")
async def referral_handler(message: Message):

    add_or_update_user(message)

    me = await bot.get_me()

    link = (
        f"https://t.me/{me.username}"
        f"?start=ref_{message.from_user.id}"
    )

    with closing(get_db()) as db:

        count = db.execute("""
            SELECT COUNT(*) c
            FROM referrals
            WHERE referrer_id=?
        """, (
            message.from_user.id,
        )).fetchone()["c"]

        earned = db.execute("""
            SELECT COALESCE(
                SUM(bonus),0
            ) s
            FROM referrals
            WHERE referrer_id=?
            AND status='rewarded'
        """, (
            message.from_user.id,
        )).fetchone()["s"]

    await message.answer(
        TEXTS["uz"]["referral_text"].format(
            link=escape(link),
            count=count,
            earned=format_money(earned)
        ),
        parse_mode="HTML",
        reply_markup=user_keyboard()
    )


# =========================================================
# LANGUAGE
# =========================================================

@dp.message(F.text == "🌐 Til")
async def language_handler(message: Message):

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🇺🇿 O‘zbek"),
                KeyboardButton(text="🇷🇺 Русский")
            ]
        ],
        resize_keyboard=True
    )

    await message.answer(
        "🌐 Tilni tanlang:",
        reply_markup=keyboard
    )


@dp.message(F.text == "🇺🇿 O‘zbek")
async def uz_handler(message: Message):

    set_language(
        message.from_user.id,
        "uz"
    )

    await message.answer(
        "✅ Til o'zbek tiliga o'zgartirildi.",
        reply_markup=user_keyboard()
    )


@dp.message(F.text == "🇷🇺 Русский")
async def ru_handler(message: Message):

    set_language(
        message.from_user.id,
        "ru"
    )

    await message.answer(
        "🇷🇺 Русский язык пока asosiy menyuda o'zbekcha funksiyalar bilan ishlaydi.",
        reply_markup=user_keyboard()
    )


# =========================================================
# HELP
# =========================================================

@dp.message(F.text == "❓ Yordam")
async def help_handler(message: Message):

    await message.answer(
        TEXTS["uz"]["help_text"],
        parse_mode="HTML",
        reply_markup=user_keyboard()
    )


# =========================================================
# NEWS
# =========================================================

@dp.message(F.text == "📰 Yangiliklar")
async def news_handler(message: Message):

    with closing(get_db()) as db:

        rows = db.execute("""
            SELECT *
            FROM news
            ORDER BY id DESC
            LIMIT 10
        """).fetchall()

    if not rows:

        await message.answer(
            TEXTS["uz"]["news_empty"],
            reply_markup=user_keyboard()
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
# ADMIN ADD PROJECT
# =========================================================

@dp.message(F.text == "➕ Loyiha qo'shish")
async def add_project_start(
    message: Message,
    state: FSMContext
):

    if not is_admin(message.from_user.id):

        await message.answer(
            TEXTS["uz"]["admin_only"]
        )

        return

    await state.clear()

    await state.set_state(
        ProjectStates.waiting_name
    )

    await message.answer(
        TEXTS["uz"]["project_name"],
        reply_markup=cancel_keyboard()
    )


@dp.message(ProjectStates.waiting_name)
async def project_name_handler(
    message: Message,
    state: FSMContext
):

    if not is_admin(message.from_user.id):
        return

    if not message.text or len(message.text.strip()) < 2:

        await message.answer(
            TEXTS["uz"]["project_name"]
        )

        return

    await state.update_data(
        project_name=message.text.strip()
    )

    await state.set_state(
        ProjectStates.waiting_link
    )

    await message.answer(
        TEXTS["uz"]["project_link"]
    )


@dp.message(ProjectStates.waiting_link)
async def project_link_handler(
    message: Message,
    state: FSMContext
):

    if not is_admin(message.from_user.id):
        return

    if not message.text:
        return

    url = message.text.strip()

    parsed = urlparse(url)

    if (
        parsed.scheme not in ("http", "https")
        or not parsed.netloc
    ):

        await message.answer(
            TEXTS["uz"]["invalid_link"]
        )

        return

    data = await state.get_data()

    project_name = data.get(
        "project_name"
    )

    with closing(get_db()) as db:

        db.execute("""
            INSERT INTO projects (
                name_uz,
                name_ru,
                url
            )
            VALUES (?, ?, ?)
        """, (
            project_name,
            project_name,
            url
        ))

        db.commit()

    await state.clear()

    await message.answer(
        TEXTS["uz"]["project_created"],
        reply_markup=admin_keyboard()
    )


# =========================================================
# ADMIN ADD NEWS
# =========================================================

@dp.message(F.text == "📰 Yangilik qo'shish")
async def add_news_start(
    message: Message,
    state: FSMContext
):

    if not is_admin(message.from_user.id):

        await message.answer(
            TEXTS["uz"]["admin_only"]
        )

        return

    await state.clear()

    await state.set_state(
        NewsStates.waiting_content
    )

    await message.answer(
        TEXTS["uz"]["send_news"]
    )


@dp.message(NewsStates.waiting_content)
async def add_news_handler(
    message: Message,
    state: FSMContext
):

    if not is_admin(message.from_user.id):
        return

    text = (
        message.text
        or message.caption
        or ""
    )

    with closing(get_db()) as db:

        db.execute("""
            INSERT INTO news (
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

    await state.clear()

    await message.answer(
        TEXTS["uz"]["news_saved"],
        reply_markup=admin_keyboard()
    )


# =========================================================
# BROADCAST
# =========================================================

async def broadcast_message(
    chat_id,
    message_id
):

    success = 0
    blocked = 0
    failed = 0

    with closing(get_db()) as db:

        users = db.execute(
            "SELECT user_id FROM users"
        ).fetchall()

    for row in users:

        user_id = row["user_id"]

        try:

            await bot.copy_message(
                chat_id=user_id,
                from_chat_id=chat_id,
                message_id=message_id
            )

            success += 1

            await asyncio.sleep(0.05)

        except TelegramForbiddenError:

            blocked += 1

            with closing(get_db()) as db:

                db.execute(
                    "DELETE FROM users WHERE user_id=?",
                    (user_id,)
                )

                db.commit()

        except TelegramRetryAfter as e:

            await asyncio.sleep(
                e.retry_after
            )

        except Exception:

            failed += 1

    return success, blocked, failed


@dp.message(F.text == "📢 Reklama tarqatish")
async def broadcast_start(
    message: Message,
    state: FSMContext
):

    if not is_admin(message.from_user.id):

        await message.answer(
            TEXTS["uz"]["admin_only"]
        )

        return

    await state.clear()

    await state.set_state(
        BroadcastStates.waiting_content
    )

    await message.answer(
        TEXTS["uz"]["send_broadcast"]
    )


@dp.message(BroadcastStates.waiting_content)
async def broadcast_handler(
    message: Message,
    state: FSMContext
):

    if not is_admin(message.from_user.id):
        return

    success, blocked, failed = await broadcast_message(
        message.chat.id,
        message.message_id
    )

    await state.clear()

    await message.answer(
        TEXTS["uz"]["broadcast_result"].format(
            success=success,
            blocked=blocked,
            failed=failed
        ),
        reply_markup=admin_keyboard()
    )


# =========================================================
# STATISTIKA
# =========================================================

@dp.message(F.text == "📊 Statistika")
async def statistics_handler(message: Message):

    if not is_admin(message.from_user.id):

        await message.answer(
            TEXTS["uz"]["admin_only"]
        )

        return

    with closing(get_db()) as db:

        users = db.execute(
            "SELECT COUNT(*) c FROM users"
        ).fetchone()["c"]

        votes = db.execute("""
            SELECT COUNT(*) c
            FROM votes
            WHERE status='approved'
        """).fetchone()["c"]

        pending_votes = db.execute("""
            SELECT COUNT(*) c
            FROM votes
            WHERE status='pending'
        """).fetchone()["c"]

        projects = db.execute(
            "SELECT COUNT(*) c FROM projects"
        ).fetchone()["c"]

        news = db.execute(
            "SELECT COUNT(*) c FROM news"
        ).fetchone()["c"]

        balance = db.execute("""
            SELECT COALESCE(SUM(balance),0) c
            FROM users
        """).fetchone()["c"]

    await message.answer(
        TEXTS["uz"]["stats"].format(
            users=users,
            votes=votes,
            pending_votes=pending_votes,
            projects=projects,
            news=news,
            balance=format_money(balance)
        ),
        parse_mode="HTML",
        reply_markup=admin_keyboard()
    )


# =========================================================
# WITHDRAW — SODDA VARIANT
# =========================================================

@dp.message(F.text == "💸 Pul yechish")
async def withdraw_start(
    message: Message,
    state: FSMContext
):

    with closing(get_db()) as db:

        row = db.execute("""
            SELECT balance
            FROM users
            WHERE user_id=?
        """, (
            message.from_user.id,
        )).fetchone()

    balance = row["balance"] if row else 0

    if balance < MIN_WITHDRAW:

        await message.answer(
            f"❌ Minimal yechish: "
            f"{format_money(MIN_WITHDRAW)} so'm\n\n"
            f"💰 Balansingiz: "
            f"{format_money(balance)} so'm",
            reply_markup=user_keyboard()
        )

        return

    await state.clear()

    await state.set_state(
        WithdrawStates.waiting_amount
    )

    await message.answer(
        TEXTS["uz"]["withdraw_amount"].format(
            minimum=format_money(MIN_WITHDRAW),
            balance=format_money(balance)
        ),
        parse_mode="HTML",
        reply_markup=cancel_keyboard()
    )


@dp.message(WithdrawStates.waiting_amount)
async def withdraw_amount(
    message: Message,
    state: FSMContext
):

    if not message.text:
        return

    raw = message.text.replace(
        " ", ""
    ).replace(",", "")

    if not raw.isdigit():

        await message.answer(
            TEXTS["uz"]["invalid_amount"]
        )

        return

    amount = int(raw)

    with closing(get_db()) as db:

        row = db.execute("""
            SELECT balance
            FROM users
            WHERE user_id=?
        """, (
            message.from_user.id,
        )).fetchone()

    balance = row["balance"] if row else 0

    if amount < MIN_WITHDRAW:

        await message.answer(
            f"❌ Minimal summa: "
            f"{format_money(MIN_WITHDRAW)} so'm"
        )

        return

    if amount > balance:

        await message.answer(
            TEXTS["uz"]["not_enough"]
        )

        return

    await state.update_data(
        withdraw_amount=amount
    )

    await state.set_state(
        WithdrawStates.waiting_info
    )

    await message.answer(
        TEXTS["uz"]["withdraw_info"],
        reply_markup=cancel_keyboard()
    )


@dp.message(WithdrawStates.waiting_info)