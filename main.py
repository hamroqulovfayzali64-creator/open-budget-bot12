# ============================================================
# MAIN.PY
# Telegram bot: foydalanuvchi + admin panel
# Aiogram 3.x + SQLite
# ============================================================

import asyncio
import logging
import os
import re
import sqlite3
from pathlib import Path
from html import escape

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
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
from aiogram.fsm.storage.memory import MemoryStorage


# ============================================================
# SOZLAMALAR
# ============================================================

BOT_TOKEN = os.getenv(
    "BOT_TOKEN",
    "# OPEN BUDGET BOT - BARCHASI BITTA MAIN.PY
import asyncio
import logging
import sqlite3
from pathlib import Path
from contextlib import closing
from html import escape
from urllib.parse import quote

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
)
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

# =========================================================
# TOKEN: XAVFSIZLIK UCHUN YANGI TOKENINGIZNI SHU YERGA QO'YING
# =========================================================
BOT_TOKEN = "8615736731:AAF7LGgYsKCq_JjV9qFPmFV6psTAS4mlQ_g"

# ADMIN TELEGRAM ID LARI
ADMIN_IDS = [7998053914]

DB_PATH = Path("bot.db")
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# =========================================================
# DATABASE
# =========================================================
def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def column_exists(conn, table, column):
    return any(row[1] == column for row in conn.execute(f"PRAGMA table_info({table})").fetchall())


def add_column_if_missing(conn, table, column, definition):
    if not column_exists(conn, table, column):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db():
    with closing(get_db()) as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                language TEXT DEFAULT 'uz',
                phone TEXT,
                voted INTEGER DEFAULT 0,
                project_clicks INTEGER DEFAULT 0,
                vote_clicks INTEGER DEFAULT 0,
                joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                referred_by INTEGER DEFAULT NULL,
                referral_count INTEGER DEFAULT 0
            )
        """)
        add_column_if_missing(conn, "users", "referred_by", "INTEGER DEFAULT NULL")
        add_column_if_missing(conn, "users", "referral_count", "INTEGER DEFAULT 0")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name_uz TEXT NOT NULL,
                name_ru TEXT NOT NULL,
                url TEXT,
                phone_votes INTEGER DEFAULT 0,
                link_votes INTEGER DEFAULT 0,
                clicks INTEGER DEFAULT 0,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        add_column_if_missing(conn, "projects", "phone_votes", "INTEGER DEFAULT 0")
        add_column_if_missing(conn, "projects", "link_votes", "INTEGER DEFAULT 0")
        add_column_if_missing(conn, "projects", "clicks", "INTEGER DEFAULT 0")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                project_id INTEGER NOT NULL,
                vote_type TEXT NOT NULL,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, project_id, vote_type)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                question TEXT NOT NULL,
                answer TEXT,
                status TEXT DEFAULT 'pending',
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                answered_date TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        conn.commit()


def add_user(user_id, username="", first_name="", language="uz", referred_by=None):
    with closing(get_db()) as conn:
        cur = conn.cursor()
        existing = cur.execute("SELECT user_id, referred_by FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not existing:
            cur.execute("""
                INSERT INTO users(user_id, username, first_name, language, referred_by)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, username or "", first_name or "", language, referred_by))
            if referred_by and referred_by != user_id:
                cur.execute("UPDATE users SET referral_count=referral_count+1 WHERE user_id=?", (referred_by,))
        else:
            cur.execute("UPDATE users SET username=?, first_name=? WHERE user_id=?",
                        (username or "", first_name or "", user_id))
        conn.commit()


def set_language(user_id, language):
    with closing(get_db()) as conn:
        conn.execute("UPDATE users SET language=? WHERE user_id=?", (language, user_id))
        conn.commit()


def get_language(user_id):
    with closing(get_db()) as conn:
        row = conn.execute("SELECT language FROM users WHERE user_id=?", (user_id,)).fetchone()
    return row[0] if row and row[0] else "uz"


def get_all_users():
    with closing(get_db()) as conn:
        return [r[0] for r in conn.execute("SELECT user_id FROM users").fetchall()]


def save_phone(user_id, phone):
    with closing(get_db()) as conn:
        conn.execute("UPDATE users SET phone=? WHERE user_id=?", (phone, user_id))
        conn.commit()


def get_projects():
    with closing(get_db()) as conn:
        return conn.execute("""
            SELECT id,name_uz,name_ru,url,phone_votes,link_votes,clicks
            FROM projects ORDER BY id DESC
        """).fetchall()


def get_project(project_id):
    with closing(get_db()) as conn:
        return conn.execute("""
            SELECT id,name_uz,name_ru,url,phone_votes,link_votes,clicks
            FROM projects WHERE id=?
        """, (project_id,)).fetchone()


def add_project(name, url):
    with closing(get_db()) as conn:
        conn.execute("INSERT INTO projects(name_uz,name_ru,url) VALUES(?,?,?)", (name, name, url))
        conn.commit()


def delete_project(project_id):
    with closing(get_db()) as conn:
        conn.execute("DELETE FROM votes WHERE project_id=?", (project_id,))
        conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
        conn.commit()


def increase_project_click(project_id, user_id):
    with closing(get_db()) as conn:
        conn.execute("UPDATE projects SET clicks=clicks+1 WHERE id=?", (project_id,))
        conn.execute("UPDATE users SET project_clicks=project_clicks+1 WHERE user_id=?", (user_id,))
        conn.commit()


def record_vote(project_id, user_id, vote_type):
    with closing(get_db()) as conn:
        try:
            conn.execute("INSERT INTO votes(user_id,project_id,vote_type) VALUES(?,?,?)",
                         (user_id, project_id, vote_type))
        except sqlite3.IntegrityError:
            return False
        if vote_type == "phone":
            conn.execute("UPDATE projects SET phone_votes=phone_votes+1 WHERE id=?", (project_id,))
        else:
            conn.execute("UPDATE projects SET link_votes=link_votes+1 WHERE id=?", (project_id,))
        conn.execute("UPDATE users SET voted=1,vote_clicks=vote_clicks+1 WHERE user_id=?", (user_id,))
        conn.commit()
        return True


def create_question(user_id, question):
    with closing(get_db()) as conn:
        cur = conn.execute("INSERT INTO questions(user_id,question) VALUES(?,?)", (user_id, question))
        qid = cur.lastrowid
        conn.commit()
        return qid


def answer_question(question_id, answer):
    with closing(get_db()) as conn:
        conn.execute("""
            UPDATE questions SET answer=?,status='answered',answered_date=CURRENT_TIMESTAMP WHERE id=?
        """, (answer, question_id))
        conn.commit()


def get_question(question_id):
    with closing(get_db()) as conn:
        return conn.execute("SELECT id,user_id,question,answer,status,created_date FROM questions WHERE id=?",
                            (question_id,)).fetchone()


def get_pending_questions():
    with closing(get_db()) as conn:
        return conn.execute("""
            SELECT id,user_id,question,created_date FROM questions
            WHERE status='pending' ORDER BY id DESC
        """).fetchall()

# =========================================================
# TEXTLAR
# =========================================================
TEXTS = {
    "uz": {
        "welcome": "👋 Botga xush kelibsiz!\n\n🗳 Ovoz berish va boshqa xizmatlardan foydalaning.",
        "select_language": "🌐 Tilni tanlang:",
        "select_vote": "🗳 Ovoz berish uchun bo‘limni tanlang:",
        "no_votes": "🗳 Hozircha ovoz berishlar yo‘q.",
        "vote_info": "🗳 <b>{name}</b>\n\nQuyidagi amalni tanlang:",
        "phone_vote": "📞 Ovoz berish uchun telefon raqamingizni yuboring.",
        "send_phone": "📱 Pastdagi tugma orqali telefon raqamingizni yuboring.",
        "phone_saved": "✅ Telefon raqamingiz qabul qilindi va ovozingiz hisobga olindi.",
        "already_voted": "ℹ️ Siz bu bo‘lim uchun allaqachon ovoz bergansiz.",
        "link_vote": "🔗 Ovoz berish sahifasiga o‘tish uchun tugmani bosing.",
        "link_missing": "⚠️ Bu ovoz berish uchun havola qo‘shilmagan.",
        "back": "⬅️ Orqaga",
        "contact_admin": "💬 Admin bilan bog‘lanish",
        "questions": "❓ Savol-javob",
        "invite": "🔗 Do‘stlarni taklif qilish",
        "invite_text": "🔗 Do‘stlaringizni botga taklif qiling.\n\nQuyidagi tugma orqali Telegram guruh yoki kontaktga ulashing:",
        "share": "📤 Ulashish",
        "send_question": "✍️ Savolingizni yozing:",
        "question_sent": "✅ Savolingiz adminga yuborildi. Javobni shu yerda olasiz.",
        "send_admin_message": "✍️ Adminga yubormoqchi bo‘lgan xabaringizni yuboring.",
        "message_sent": "✅ Xabaringiz adminga yuborildi.",
        "admin_panel": "👑 <b>Admin panel</b>\n\nKerakli bo‘limni tanlang:",
        "statistics": "📊 <b>Statistika</b>\n\n👥 Foydalanuvchilar: <b>{users}</b>\n🗳 Ovoz berishlar: <b>{projects}</b>\n🖱 Ko‘rishlar: <b>{clicks}</b>\n📞 Telefon ovozlari: <b>{phone}</b>\n🔗 Havola ovozlari: <b>{link}</b>\n🗳 Jami ovozlar: <b>{total_votes}</b>\n🔗 Taklif qilinganlar: <b>{referrals}</b>",
        "add_vote_name": "➕ Ovoz berish qo‘shish\n\nNomini yuboring:",
        "add_vote_link": "🔗 Endi ovoz berish havolasini yuboring.\n\nMasalan: https://example.com\n\nHavola bo‘lmasa, <b>yo‘q</b> deb yozing.",
        "vote_added": "✅ Ovoz berish muvaffaqiyatli qo‘shildi.",
        "broadcast": "📢 Barcha foydalanuvchilarga yubormoqchi bo‘lgan xabaringizni yuboring.",
        "broadcast_done": "✅ Xabar yuborildi.\n\n📨 Yuborildi: {sent}\n❌ Xatolik: {failed}",
        "reply_prompt": "✍️ Foydalanuvchiga yubormoqchi bo‘lgan javobingizni yozing:",
        "reply_sent": "✅ Javob yuborildi.",
        "reply_failed": "❌ Javob yuborilmadi.",
        "unknown": "⚠️ Menyudagi tugmalardan foydalaning."
    },
    "ru": {
        "welcome": "👋 Добро пожаловать!\n\n🗳 Выберите нужный раздел.",
        "select_language": "🌐 Выберите язык:",
        "select_vote": "🗳 Выберите голосование:",
        "no_votes": "🗳 Пока голосований нет.",
        "vote_info": "🗳 <b>{name}</b>\n\nВыберите действие:",
        "phone_vote": "📞 Отправьте номер телефона для голосования.",
        "send_phone": "📱 Нажмите кнопку ниже и отправьте номер.",
        "phone_saved": "✅ Номер принят, ваш голос учтён.",
        "already_voted": "ℹ️ Вы уже голосовали в этом разделе.",
        "link_vote": "🔗 Нажмите кнопку для перехода на страницу голосования.",
        "link_missing": "⚠️ Для этого голосования ссылка не добавлена.",
        "back": "⬅️ Назад",
        "contact_admin": "💬 Связаться с администратором",
        "questions": "❓ Вопрос-ответ",
        "invite": "🔗 Пригласить друзей",
        "invite_text": "🔗 Пригласите друзей в бота.\n\nНажмите кнопку ниже и выберите группу или контакт:",
        "share": "📤 Поделиться",
        "send_question": "✍️ Напишите ваш вопрос:",
        "question_sent": "✅ Вопрос отправлен администратору. Ответ придёт сюда.",
        "send_admin_message": "✍️ Отправьте сообщение администратору.",
        "message_sent": "✅ Сообщение отправлено администратору.",
        "admin_panel": "👑 <b>Панель администратора</b>\n\nВыберите раздел:",
        "statistics": "📊 <b>Статистика</b>\n\n👥 Пользователи: <b>{users}</b>\n🗳 Голосования: <b>{projects}</b>\n🖱 Переходы: <b>{clicks}</b>\n📞 Голоса по телефону: <b>{phone}</b>\n🔗 Голоса по ссылке: <b>{link}</b>\n🗳 Всего голосов: <b>{total_votes}</b>\n🔗 Приглашено: <b>{referrals}</b>",
        "add_vote_name": "➕ Добавление голосования\n\nОтправьте название:",
        "add_vote_link": "🔗 Отправьте ссылку голосования.\n\nНапример: https://example.com\n\nЕсли ссылки нет, напишите <b>нет</b>.",
        "vote_added": "✅ Голосование добавлено.",
        "broadcast": "📢 Отправьте сообщение для всех пользователей.",
        "broadcast_done": "✅ Сообщение отправлено.\n\n📨 Отправлено: {sent}\n❌ Ошибок: {failed}",
        "reply_prompt": "✍️ Напишите ответ пользователю:",
        "reply_sent": "✅ Ответ отправлен.",
        "reply_failed": "❌ Не удалось отправить ответ.",
        "unknown": "⚠️ Используйте кнопки меню."
    }
}

# =========================================================
# KEYBOARDS
# =========================================================
def language_keyboard():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🇺🇿 O‘zbek"), KeyboardButton(text="🇷🇺 Русский")]], resize_keyboard=True)


def user_keyboard_uz():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🗳 Ovoz berish")],
        [KeyboardButton(text="💰 Balans"), KeyboardButton(text="💸 Pulni yechib olish")],
        [KeyboardButton(text="🔗 Do‘stlarni taklif qilish"), KeyboardButton(text="🎁 Iphone 17")],
        [KeyboardButton(text="❓ Savol-javob"), KeyboardButton(text="💬 Admin bilan bog‘lanish")],
        [KeyboardButton(text="🌐 Tilni almashtirish")]
    ], resize_keyboard=True)


def user_keyboard_ru():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🗳 Голосование")],
        [KeyboardButton(text="💰 Баланс"), KeyboardButton(text="💸 Вывести деньги")],
        [KeyboardButton(text="🔗 Пригласить друзей"), KeyboardButton(text="🎁 Iphone 17")],
        [KeyboardButton(text="❓ Вопрос-ответ"), KeyboardButton(text="💬 Связаться с администратором")],
        [KeyboardButton(text="🌐 Сменить язык")]
    ], resize_keyboard=True)


def admin_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="➕ Ovoz berish qo‘shish")],
        [KeyboardButton(text="🗳 Ovoz berishlar"), KeyboardButton(text="❓ Savollar")],
        [KeyboardButton(text="📢 Reklama yuborish")],
        [KeyboardButton(text="⬅️ Foydalanuvchi menyusi")]
    ], resize_keyboard=True)


def vote_list_keyboard(projects, lang):
    buttons = [[InlineKeyboardButton(text=f"🗳 {p[1] if lang=='uz' else p[2]}", callback_data=f"project:{p[0]}")] for p in projects]
    buttons.append([InlineKeyboardButton(text=TEXTS[lang]["back"], callback_data="user_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def vote_action_keyboard(project_id, has_url, lang):
    buttons = [[InlineKeyboardButton(text="📞 Ovoz berish", callback_data=f"phone_vote:{project_id}")]]
    if has_url:
        buttons.append([InlineKeyboardButton(text="🔗 Havola orqali ovoz berish", callback_data=f"link_vote:{project_id}")])
    buttons.append([InlineKeyboardButton(text=TEXTS[lang]["back"], callback_data="votes_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_question_keyboard(question_id):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="↩️ Javob berish", callback_data=f"answer_question:{question_id}")]])


def admin_reply_keyboard(user_id):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="↩️ Javob berish", callback_data=f"admin_reply:{user_id}")]])

# =========================================================
# STATES
# =========================================================
class AddVoteState(StatesGroup):
    name = State()
    link = State()

class BroadcastState(StatesGroup):
    message = State()

class AdminReplyState(StatesGroup):
    message = State()

class QuestionState(StatesGroup):
    message = State()

class ContactAdminState(StatesGroup):
    message = State()

class QuestionAnswerState(StatesGroup):
    message = State()

pending_phone_votes = {}
admin_reply_targets = {}
question_answer_targets = {}

# =========================================================
# START / REFERRAL
# =========================================================
@dp.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    await state.clear()
    user = message.from_user
    referred_by = None
    if message.text:
        parts = message.text.split(maxsplit=1)
        if len(parts) == 2 and parts[1].startswith("ref_"):
            try:
                referred_by = int(parts[1][4:])
            except ValueError:
                referred_by = None
    old_lang = get_language(user.id) if user.id in get_all_users() else "uz"
    add_user(user.id, user.username, user.first_name, old_lang, referred_by)
    if is_admin(user.id):
        await message.answer(TEXTS["uz"]["admin_panel"], reply_markup=admin_keyboard())
    else:
        await message.answer(TEXTS[old_lang]["welcome"], reply_markup=user_keyboard_uz() if old_lang == "uz" else user_keyboard_ru())

# =========================================================
# LANGUAGE
# =========================================================
@dp.message(F.text == "🇺🇿 O‘zbek")
async def uz_language(message: Message):
    set_language(message.from_user.id, "uz")
    await message.answer(TEXTS["uz"]["welcome"], reply_markup=user_keyboard_uz())

@dp.message(F.text == "🇷🇺 Русский")
async def ru_language(message: Message):
    set_language(message.from_user.id, "ru")
    await message.answer(TEXTS["ru"]["welcome"], reply_markup=user_keyboard_ru())

@dp.message(F.text.in_({"🌐 Tilni almashtirish", "🌐 Сменить язык"}))
async def change_language(message: Message):
    await message.answer(TEXTS[get_language(message.from_user.id)]["select_language"], reply_markup=language_keyboard())

# =========================================================
# USER VOTING
# =========================================================
@dp.message(F.text.in_({"🗳 Ovoz berish", "🗳 Голосование"}))
async def show_votes(message: Message):
    lang = get_language(message.from_user.id)
    projects = get_projects()
    if not projects:
        await message.answer(TEXTS[lang]["no_votes"])
        return
    await message.answer(TEXTS[lang]["select_vote"], reply_markup=vote_list_keyboard(projects, lang))

@dp.callback_query(F.data.startswith("project:"))
async def project_selected(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = get_language(user_id)
    project_id = int(callback.data.split(":")[1])
    project = get_project(project_id)
    if not project:
        await callback.answer("Topilmadi", show_alert=True)
        return
    increase_project_click(project_id, user_id)
    name, url = (project[1], project[3]) if lang == "uz" else (project[2], project[3])
    await callback.message.edit_text(TEXTS[lang]["vote_info"].format(name=escape(name)), reply_markup=vote_action_keyboard(project_id, bool(url), lang))
    await callback.answer()

@dp.callback_query(F.data.startswith("phone_vote:"))
async def phone_vote_start(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = get_language(user_id)
    project_id = int(callback.data.split(":")[1])
    project = get_project(project_id)
    if not project:
        await callback.answer("Topilmadi", show_alert=True)
        return
    with closing(get_db()) as conn:
        exists = conn.execute("SELECT 1 FROM votes WHERE user_id=? AND project_id=? AND vote_type='phone'", (user_id, project_id)).fetchone()
    if exists:
        await callback.answer(TEXTS[lang]["already_voted"], show_alert=True)
        return
    pending_phone_votes[user_id] = project_id
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📱 Telefon raqamimni yuborish", request_contact=True)],
        [KeyboardButton(text=TEXTS[lang]["back"])]
    ], resize_keyboard=True, one_time_keyboard=True)
    await callback.message.answer(TEXTS[lang]["phone_vote"] + "\n\n" + TEXTS[lang]["send_phone"], reply_markup=kb)
    await callback.answer()

@dp.message(F.contact)
async def contact_handler(message: Message):
    user_id = message.from_user.id
    if user_id not in pending_phone_votes:
        return
    lang = get_language(user_id)
    project_id = pending_phone_votes.pop(user_id)
    phone = message.contact.phone_number
    save_phone(user_id, phone)
    ok = record_vote(project_id, user_id, "phone")
    await message.answer(TEXTS[lang]["phone_saved"] if ok else TEXTS[lang]["already_voted"], reply_markup=user_keyboard_uz() if lang == "uz" else user_keyboard_ru())

@dp.callback_query(F.data.startswith("link_vote:"))
async def link_vote(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = get_language(user_id)
    project_id = int(callback.data.split(":")[1])
    project = get_project(project_id)
    if not project:
        await callback.answer("Topilmadi", show_alert=True)
        return
    url = project[3]
    if not url:
        await callback.answer(TEXTS[lang]["link_missing"], show_alert=True)
        return
    ok = record_vote(project_id, user_id, "link")
    if not ok:
        await callback.answer(TEXTS[lang]["already_voted"], show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Ovoz berish", url=url)],
        [InlineKeyboardButton(text=TEXTS[lang]["back"], callback_data=f"project:{project_id}")]
    ])
    await callback.message.answer(TEXTS[lang]["link_vote"], reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data == "votes_back")
async def votes_back(callback: CallbackQuery):
    lang = get_language(callback.from_user.id)
    projects = get_projects()
    if not projects:
        await callback.message.edit_text(TEXTS[lang]["no_votes"])
    else:
        await callback.message.edit_text(TEXTS[lang]["select_vote"], reply_markup=vote_list_keyboard(projects, lang))
    await callback.answer()

@dp.callback_query(F.data == "user_back")
async def user_back(callback: CallbackQuery):
    lang = get_language(callback.from_user.id)
    await callback.message.delete()
    await callback.message.answer(TEXTS[lang]["welcome"], reply_markup=user_keyboard_uz() if lang == "uz" else user_keyboard_ru())
    await callback.answer()

# =========================================================
# QUESTIONS / ADMIN CONTACT
# =========================================================
@dp.message(F.text.in_({"❓ Savol-javob", "❓ Вопрос-ответ"}))
async def question_start(message: Message, state: FSMContext):
    lang = get_language(message.from_user.id)
    await state.set_state(QuestionState.message)
    await message.answer(TEXTS[lang]["send_question"], reply_markup=ReplyKeyboardRemove())

@dp.message(QuestionState.message)
async def question_message(message: Message, state: FSMContext, bot: Bot):
    user = message.from_user
    if not message.text or not message.text.strip():
        await message.answer("❌ Savol matn ko‘rinishida bo‘lsin.")
        return
    qid = create_question(user.id, message.text.strip())
    username = f"@{user.username}" if user.username else "username yo‘q"
    admin_text = (f"❓ <b>Yangi savol #{qid}</b>\n\n👤 {escape(user.full_name)}\n"
                  f"🔹 {escape(username)}\n🆔 <code>{user.id}</code>\n\n"
                  f"💬 <b>Savol:</b>\n{escape(message.text.strip())}")
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, admin_text, reply_markup=admin_question_keyboard(qid))
        except Exception as e:
            logging.error("Question admin error: %s", e)
    await state.clear()
    lang = get_language(user.id)
    await message.answer(TEXTS[lang]["question_sent"], reply_markup=user_keyboard_uz() if lang == "uz" else user_keyboard_ru())

@dp.callback_query(F.data.startswith("answer_question:"))
async def answer_question_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    qid = int(callback.data.split(":")[1])
    q = get_question(qid)
    if not q or q[4] != "pending":
        await callback.answer("Bu savolga allaqachon javob berilgan.", show_alert=True)
        return
    question_answer_targets[callback.from_user.id] = qid
    await state.set_state(QuestionAnswerState.message)
    await callback.message.answer(TEXTS["uz"]["reply_prompt"], reply_markup=ReplyKeyboardRemove())
    await callback.answer()

@dp.message(QuestionAnswerState.message)
async def answer_question_message(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    qid = question_answer_targets.get(message.from_user.id)
    if not qid or not message.text:
        return
    q = get_question(qid)
    if not q:
        await state.clear()
        return
    try:
        await bot.send_message(q[1], f"💬 <b>Admin javobi:</b>\n\n{escape(message.text)}")
        answer_question(qid, message.text)
        await message.answer("✅ Javob yuborildi va bazaga saqlandi.", reply_markup=admin_keyboard())
    except Exception as e:
        logging.error("Question answer error: %s", e)
        await message.answer("❌ Foydalanuvchiga yuborib bo‘lmadi.", reply_markup=admin_keyboard())
    question_answer_targets.pop(message.from_user.id, None)
    await state.clear()

@dp.message(F.text.in_({"💬 Admin bilan bog‘lanish", "💬 Связаться с администратором"}))
async def contact_admin_start(message: Message, state: FSMContext):
    lang = get_language(message.from_user.id)
    await state.set_state(ContactAdminState.message)
    await message.answer(TEXTS[lang]["send_admin_message"], reply_markup=ReplyKeyboardRemove())

@dp.message(ContactAdminState.message)
async def contact_admin_message(message: Message, state: FSMContext, bot: Bot):
    user = message.from_user
    username = f"@{user.username}" if user.username else "username yo‘q"
    admin_text = (f"📩 <b>Yangi xabar</b>\n\n👤 {escape(user.full_name)}\n"
                  f"🔹 {escape(username)}\n🆔 <code>{user.id}</code>")
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, admin_text, reply_markup=admin_reply_keyboard(user.id))
            await bot.copy_message(admin_id, message.chat.id, message.message_id)
        except Exception as e:
            logging.error("Admin contact error: %s", e)
    await state.clear()
    lang = get_language(user.id)
    await message.answer(TEXTS[lang]["message_sent"], reply_markup=user_keyboard_uz() if lang == "uz" else user_keyboard_ru())

# =========================================================
# INVITE / SHARE
# =========================================================
@dp.message(F.text.in_({"🔗 Do‘stlarni taklif qilish", "🔗 Пригласить друзей"}))
async def invite_friends(message: Message, bot: Bot):
    lang = get_language(message.from_user.id)
    me = await bot.get_me()
    ref_link = f"https://t.me/{me.username}?start=ref_{message.from_user.id}"
    share_url = "https://t.me/share/url?url=" + quote(ref_link, safe="") + "&text=" + quote("🤝 Botga qo‘shiling!", safe="")
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=TEXTS[lang]["share"], url=share_url)]])
    await message.answer(TEXTS[lang]["invite_text"], reply_markup=kb)

# =========================================================
# SIMPLE BUTTONS FROM SCREEN
# =========================================================
@dp.message(F.text.in_({"💰 Balans", "💰 Баланс"}))
async def balance_handler(message: Message):
    await message.answer("💰 Balans bo‘limi hozircha ma’lumot ko‘rsatish uchun tayyor.\n\n🧾 Balans tizimi uchun admin tomonidan alohida qoidalar kiritilishi kerak.")

@dp.message(F.text.in_({"💸 Pulni yechib olish", "💸 Вывести деньги"}))
async def withdraw_handler(message: Message):
    await message.answer("💸 Pul yechib olish bo‘limi hozircha faol emas.")

@dp.message(F.text.in_({"🎁 Iphone 17"}))
async def iphone_handler(message: Message):
    await message.answer("🎁 Iphone 17 bo‘limi.\n\nTanlov va shartlar admin tomonidan boshqariladi.")

# =========================================================
# ADMIN CHECK / COMMAND
# =========================================================
def is_admin(user_id):
    return user_id in ADMIN_IDS

@dp.message(Command("admin"))
async def admin_command(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer(TEXTS["uz"]["admin_panel"], reply_markup=admin_keyboard())

@dp.message(F.text == "📊 Statistika")
async def statistics_handler(message: Message):
    if not is_admin(message.from_user.id):
        return
    with closing(get_db()) as conn:
        users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        projects = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        clicks = conn.execute("SELECT COALESCE(SUM(clicks),0) FROM projects").fetchone()[0]
        phone = conn.execute("SELECT COALESCE(SUM(phone_votes),0) FROM projects").fetchone()[0]
        link = conn.execute("SELECT COALESCE(SUM(link_votes),0) FROM projects").fetchone()[0]
        referrals = conn.execute("SELECT COALESCE(SUM(referral_count),0) FROM users").fetchone()[0]
    await message.answer(TEXTS["uz"]["statistics"].format(users=users, projects=projects, clicks=clicks, phone=phone, link=link, total_votes=phone+link, referrals=referrals))

# =========================================================
# ADMIN ADD VOTE
# =========================================================
@dp.message(F.text == "➕ Ovoz berish qo‘shish")
async def add_vote_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AddVoteState.name)
    await message.answer(TEXTS["uz"]["add_vote_name"])

@dp.message(AddVoteState.name)
async def add_vote_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if not message.text or not message.text.strip():
        await message.answer("❌ Nom bo‘sh bo‘lishi mumkin emas.")
        return
    await state.update_data(name=message.text.strip())
    await state.set_state(AddVoteState.link)
    await message.answer(TEXTS["uz"]["add_vote_link"])

@dp.message(AddVoteState.link)
async def add_vote_link(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    url = (message.text or "").strip()
    if url.lower() in {"yo‘q", "yo'q", "yoq", "нет", "no"}:
        url = ""
    elif not (url.startswith("http://") or url.startswith("https://")):
        await message.answer("❌ Havola http:// yoki https:// bilan boshlansin yoki 'yo‘q' deb yozing.")
        return
    data = await state.get_data()
    add_project(data["name"], url)
    await state.clear()
    await message.answer(TEXTS["uz"]["vote_added"], reply_markup=admin_keyboard())

# =========================================================
# ADMIN VOTE LIST / DELETE
# =========================================================
@dp.message(F.text.in_({"🗳 Ovoz berishlar", "📌 Loyihalar"}))
async def admin_votes(message: Message):
    if not is_admin(message.from_user.id):
        return
    projects = get_projects()
    if not projects:
        await message.answer("🗳 Hozircha ovoz berishlar yo‘q.")
        return
    buttons = [[InlineKeyboardButton(text=f"🗳 {p[1]}", callback_data=f"admin_project:{p[0]}")] for p in projects]
    await message.answer("🗳 <b>Ovoz berishlar</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data.startswith("admin_project:"))
async def admin_project_selected(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    project_id = int(callback.data.split(":")[1])
    p = get_project(project_id)
    if not p:
        await callback.answer("Topilmadi", show_alert=True)
        return
    text = (f"🗳 <b>{escape(p[1])}</b>\n\n🔗 {escape(p[3] or 'Havola yo‘q')}\n\n"
            f"🖱 Ko‘rishlar: {p[6]}\n📞 Telefon ovozlari: {p[4]}\n🔗 Havola ovozlari: {p[5]}")
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🗑 O‘chirish", callback_data=f"delete_project:{project_id}")]])
    await callback.message.answer(text, reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("delete_project:"))
async def delete_project_handler(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    project_id = int(callback.data.split(":")[1])
    delete_project(project_id)
    await callback.message.edit_text("✅ Ovoz berish o‘chirildi.")
    await callback.answer()

# =========================================================
# ADMIN QUESTIONS LIST
# =========================================================
@dp.message(F.text == "❓ Savollar")
async def admin_questions(message: Message):
    if not is_admin(message.from_user.id):
        return
    questions = get_pending_questions()
    if not questions:
        await message.answer("✅ Javob kutilayotgan savollar yo‘q.")
        return
    for q in questions[:30]:
        text = f"❓ <b>Savol #{q[0]}</b>\n🆔 <code>{q[1]}</code>\n\n{escape(q[2])}"
        await message.answer(text, reply_markup=admin_question_keyboard(q[0]))

# =========================================================
# ADMIN BROADCAST
# =========================================================
@dp.message(F.text == "📢 Reklama yuborish")
async def broadcast_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(BroadcastState.message)
    await message.answer(TEXTS["uz"]["broadcast"], reply_markup=ReplyKeyboardRemove())

@dp.message(BroadcastState.message)
async def broadcast_message(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    sent = failed = 0
    for user_id in get_all_users():
        try:
            await bot.copy_message(user_id, message.chat.id, message.message_id)
            sent += 1
        except Exception as e:
            failed += 1
            logging.error("Broadcast %s: %s", user_id, e)
        await asyncio.sleep(0.04)
    await state.clear()
    await message.answer(TEXTS["uz"]["broadcast_done"].format(sent=sent, failed=failed), reply_markup=admin_keyboard())

# =========================================================
# ADMIN REPLY TO CONTACT MESSAGE
# =========================================================
@dp.callback_query(F.data.startswith("admin_reply:"))
async def admin_reply_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    user_id = int(callback.data.split(":")[1])
    admin_reply_targets[callback.from_user.id] = user_id
    await state.set_state(AdminReplyState.message)
    await callback.message.answer(TEXTS["uz"]["reply_prompt"], reply_markup=ReplyKeyboardRemove())
    await callback.answer()

@dp.message(AdminReplyState.message)
async def admin_reply_message(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    user_id = admin_reply_targets.get(message.from_user.id)
    if not user_id:
        await state.clear()
        return
    try:
        await bot.copy_message(user_id, message.chat.id, message.message_id)
        await message.answer(TEXTS["uz"]["reply_sent"], reply_markup=admin_keyboard())
    except Exception as e:
        logging.error("Reply error: %s", e)
        await message.answer(TEXTS["uz"]["reply_failed"], reply_markup=admin_keyboard())
    admin_reply_targets.pop(message.from_user.id, None)
    await state.clear()

# =========================================================
# ADMIN BACK
# =========================================================
@dp.message(F.text == "⬅️ Foydalanuvchi menyusi")
async def admin_to_user_menu(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer(TEXTS["uz"]["welcome"], reply_markup=user_keyboard_uz())

@dp.message(F.text == "⬅️ Orqaga")
async def simple_back(message: Message):
    lang = get_language(message.from_user.id)
    await message.answer(TEXTS[lang]["welcome"], reply_markup=user_keyboard_uz() if lang == "uz" else user_keyboard_ru())

# =========================================================
# UNKNOWN
# =========================================================
@dp.message()
async def unknown_handler(message: Message):
    user_id = message.from_user.id
    if is_admin(user_id):
        await message.answer("👑 Admin panel uchun /admin buyrug‘idan foydalaning.", reply_markup=admin_keyboard())
        return
    lang = get_language(user_id)
    await message.answer(TEXTS[lang]["unknown"], reply_markup=user_keyboard_uz() if lang == "uz" else user_keyboard_ru())

# =========================================================
# RUN
# =========================================================
async def main():
    print("========================================", flush=True)
    print("OPEN BUDGET BOT ISHLAMOQDA", flush=True)
    print("========================================", flush=True)
    init_db()
    if not BOT_TOKEN or BOT_TOKEN.startswith("BU_YERGA_"):
        raise RuntimeError("BOT_TOKEN noto‘g‘ri. main.py ichidagi BOT_TOKEN joyiga YANGI BotFather tokenini yozing.")
    bot = Bot(token=BOT_TOKEN)
    me = await bot.get_me()
    print(f"Bot ulandi: @{me.username}", flush=True)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot to‘xtatildi.")
8615736731:AAF7LGgYsKCq_JjV9qFPmFV6psTAS4mlQ_g"
)

# MUHIM: o'zingizning Telegram ID raqamingizni yozing.
ADMIN_IDS = [7998053914]

DB_FILE = Path("bot.db")

REFERRAL_BONUS = 10_000
MIN_WITHDRAW = 30_000
VOTE_BONUS = 30_000


# ============================================================
# LOGGING / BOT
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ============================================================
# DATABASE
# ============================================================

def db():
    return sqlite3.connect(DB_FILE)


def init_db():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT DEFAULT '',
            first_name TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            balance INTEGER DEFAULT 0,
            referral_code TEXT UNIQUE,
            referred_by INTEGER,
            referral_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inviter_id INTEGER,
            invited_id INTEGER UNIQUE,
            bonus INTEGER DEFAULT 10000,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            vote_type TEXT,
            phone TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            bonus INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            user_id INTEGER PRIMARY KEY,
            active INTEGER DEFAULT 0,
            topic TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

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

    cur.execute("""
        CREATE TABLE IF NOT EXISTS balance_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            operation TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT DEFAULT ''
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS button_stats (
            button TEXT PRIMARY KEY,
            count INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


# ============================================================
# YORDAMCHI FUNKSIYALAR
# ============================================================

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def add_user(user_id: int, username: str, first_name: str):
    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT user_id FROM users WHERE user_id = ?",
        (user_id,),
    )
    exists = cur.fetchone()

    if exists:
        cur.execute("""
            UPDATE users
            SET username = ?, first_name = ?
            WHERE user_id = ?
        """, (username, first_name, user_id))
    else:
        cur.execute("""
            INSERT INTO users(
                user_id, username, first_name, referral_code
            )
            VALUES (?, ?, ?, ?)
        """, (user_id, username, first_name, str(user_id)))

    conn.commit()
    conn.close()


def get_user(user_id: int):
    conn = db()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM users WHERE user_id = ?",
        (user_id,),
    )
    row = cur.fetchone()
    conn.close()
    return row


def get_balance(user_id: int) -> int:
    conn = db()
    cur = conn.cursor()
    cur.execute(
        "SELECT balance FROM users WHERE user_id = ?",
        (user_id,),
    )
    row = cur.fetchone()
    conn.close()
    return int(row[0]) if row else 0


def change_balance(user_id: int, amount: int, operation: str):
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET balance = balance + ?
        WHERE user_id = ?
    """, (amount, user_id))

    cur.execute("""
        INSERT INTO balance_history(user_id, amount, operation)
        VALUES (?, ?, ?)
    """, (user_id, amount, operation))

    conn.commit()
    conn.close()


def setting_get(key: str, default: str = "") -> str:
    conn = db()
    cur = conn.cursor()
    cur.execute(
        "SELECT value FROM settings WHERE key = ?",
        (key,),
    )
    row = cur.fetchone()
    conn.close()
    return row[0] if row else default


def setting_set(key: str, value: str):
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


def stat(button: str):
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


def set_chat(user_id: int, active: int, topic: str = ""):
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO conversations(user_id, active, topic)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET
            active = excluded.active,
            topic = excluded.topic
    """, (user_id, active, topic))

    conn.commit()
    conn.close()


def chat_active(user_id: int) -> bool:
    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT active FROM conversations WHERE user_id = ?",
        (user_id,),
    )
    row = cur.fetchone()

    conn.close()
    return bool(row and row[0] == 1)


def process_referral(new_user_id: int, inviter_id: int) -> bool:
    if new_user_id == inviter_id:
        return False

    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT referred_by FROM users WHERE user_id = ?",
        (new_user_id,),
    )
    row = cur.fetchone()

    if not row or row[0] is not None:
        conn.close()
        return False

    cur.execute(
        "SELECT user_id FROM users WHERE user_id = ?",
        (inviter_id,),
    )

    if not cur.fetchone():
        conn.close()
        return False

    cur.execute("""
        UPDATE users
        SET referred_by = ?
        WHERE user_id = ?
    """, (inviter_id, new_user_id))

    cur.execute("""
        UPDATE users
        SET referral_count = referral_count + 1,
            balance = balance + ?
        WHERE user_id = ?
    """, (REFERRAL_BONUS, inviter_id))

    cur.execute("""
        INSERT INTO referrals(inviter_id, invited_id, bonus)
        VALUES (?, ?, ?)
    """, (inviter_id, new_user_id, REFERRAL_BONUS))

    cur.execute("""
        INSERT INTO balance_history(user_id, amount, operation)
        VALUES (?, ?, ?)
    """, (inviter_id, REFERRAL_BONUS, "Referral bonusi"))

    conn.commit()
    conn.close()
    return True


def admin_buttons(user_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 Javob berish",
                    callback_data=f"reply_{user_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔴 Suhbatni yopish",
                    callback_data=f"close_{user_id}",
                )
            ],
        ]
    )


# ============================================================
# KEYBOARDLAR
# ============================================================

def user_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📌 Loyihalar"),
                KeyboardButton(text="🗳 Ovoz berish"),
            ],
            [
                KeyboardButton(text="💰 Balans"),
                KeyboardButton(text="💳 Pul yechish"),
            ],
            [
                KeyboardButton(text="👥 Do‘stlarni taklif qilish"),
                KeyboardButton(text="❓ Savol-javob"),
            ],
            [
                KeyboardButton(text="👨‍💼 Admin bilan bog‘lanish"),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def admin_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📊 Statistika"),
                KeyboardButton(text="👥 Foydalanuvchilar"),
            ],
            [
                KeyboardButton(text="📞 Telefon raqamlari"),
                KeyboardButton(text="💳 Pul yechishlar"),
            ],
            [
                KeyboardButton(text="❓ Savol-javoblar"),
                KeyboardButton(text="🗳 Ovozlar"),
            ],
            [
                KeyboardButton(text="🔗 Ovoz havolasi"),
                KeyboardButton(text="👨‍💼 Admin kontakt"),
            ],
            [
                KeyboardButton(text="📌 Loyiha sozlamalari"),
                KeyboardButton(text="💰 Balans boshqaruvi"),
            ],
            [
                KeyboardButton(text="📢 Xabar yuborish"),
                KeyboardButton(text="🏠 Foydalanuvchi menyusi"),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


# ============================================================
# START
# ============================================================

@dp.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    await state.clear()

    user = message.from_user

    add_user(
        user.id,
        user.username or "",
        user.first_name or "",
    )

    parts = (message.text or "").split(maxsplit=1)

    if len(parts) == 2:
        try:
            inviter_id = int(parts[1])
            process_referral(user.id, inviter_id)
        except ValueError:
            pass

    if is_admin(user.id):
        await message.answer(
            "👨‍💼 <b>Admin panel</b>\n\n"
            "Kerakli bo‘limni tanlang.",
            reply_markup=admin_keyboard(),
        )
    else:
        await message.answer(
            f"👋 Assalomu alaykum, "
            f"<b>{escape(user.first_name or 'Foydalanuvchi')}</b>!\n\n"
            "Botga xush kelibsiz.",
            reply_markup=user_keyboard(),
        )


# ============================================================
# BALANS
# ============================================================

@dp.message(F.text == "💰 Balans")
async def balance_handler(message: Message):
    if is_admin(message.from_user.id):
        return

    stat("balans")

    balance = get_balance(message.from_user.id)

    await message.answer(
        "💰 <b>SIZNING BALANSINGIZ</b>\n\n"
        f"💵 Balans: <b>{balance:,} so‘m</b>\n\n"
        "💳 BALANSDAGI PULNI YECHISH UCHUN "
        "BALANSDA KAMIDA <b>30 MING SO‘M</b> "
        "BO‘LISHI KERAK.\n\n"
        "Balansni to‘ldirish uchun ovoz berishingiz "
        "yoki do‘stlaringizni taklif qilishingiz mumkin.\n\n"
        f"🗳 Har bir tasdiqlangan ovoz uchun: "
        f"<b>{VOTE_BONUS:,} so‘m</b>\n"
        f"👥 Har bir referral uchun: "
        f"<b>{REFERRAL_BONUS:,} so‘m</b>",
        reply_markup=user_keyboard(),
    )


# ============================================================
# OVOZ BERISH
# ============================================================

@dp.message(F.text == "🗳 Ovoz berish")
async def vote_handler(message: Message):
    if is_admin(message.from_user.id):
        return

    stat("ovoz_berish")

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔗 Havola orqali",
                    callback_data="vote_link",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📞 Telefon raqami orqali",
                    callback_data="vote_phone",
                )
            ],
        ]
    )

    await message.answer(
        "🗳 <b>OVOZ BERISH</b>\n\n"
        "Ovoz berish usulini tanlang:",
        reply_markup=keyboard,
    )


@dp.callback_query(F.data == "vote_link")
async def vote_link_callback(callback: CallbackQuery):
    link = setting_get("vote_link")

    if not link:
        await callback.message.answer(
            "🔗 Hozircha ovoz berish havolasi "
            "admin tomonidan qo‘yilmagan."
        )
    else:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔗 Ovoz berish",
                        url=link,
                    )
                ]
            ]
        )

        await callback.message.answer(
            "🔗 Ovoz berish uchun quyidagi tugmani bosing:",
            reply_markup=keyboard,
        )

    await callback.answer()


class VoteStates(StatesGroup):
    phone = State()


@dp.callback_query(F.data == "vote_phone")
async def vote_phone_callback(
    callback: CallbackQuery,
    state: FSMContext,
):
    await state.set_state(VoteStates.phone)

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="📞 Telefon raqamimni yuborish",
                    request_contact=True,
                )
            ],
            [
                KeyboardButton(text="❌ Bekor qilish"),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )

    await callback.message.answer(
        "📞 <b>Ovoz berish uchun telefon raqamingizni yuboring.</b>\n\n"
        "Telefon raqamingiz adminga ko‘rinadi.",
        reply_markup=keyboard,
    )

    await callback.answer()


@dp.message(VoteStates.phone)
async def receive_vote_phone(
    message: Message,
    state: FSMContext,
):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer(
            "❌ Bekor qilindi.",
            reply_markup=user_keyboard(),
        )
        return

    phone = ""

    if message.contact:
        phone = message.contact.phone_number
    elif message.text:
        phone = message.text.strip()

    if not phone:
        await message.answer(
            "❗ Telefon raqamingizni yuboring."
        )
        return

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET phone = ?
        WHERE user_id = ?
    """, (phone, message.from_user.id))

    # Bir xil pending ovozni qayta-qayta yaratmaslik.
    cur.execute("""
        SELECT id
        FROM votes
        WHERE user_id = ?
          AND phone = ?
          AND status = 'pending'
        LIMIT 1
    """, (message.from_user.id, phone))

    existing = cur.fetchone()

    if not existing:
        cur.execute("""
            INSERT INTO votes(
                user_id, vote_type, phone, status, bonus
            )
            VALUES (?, 'phone', ?, 'pending', ?)
        """, (message.from_user.id, phone, VOTE_BONUS))

    conn.commit()
    conn.close()

    set_chat(message.from_user.id, 1, "telefon ovozi")
    await state.clear()

    await message.answer(
        "✅ Telefon raqamingiz qabul qilindi.\n\n"
        "📨 Ma’lumot adminlarga yuborildi.\n"
        "Admin sizga shu suhbat orqali javob bera oladi.",
        reply_markup=user_keyboard(),
    )

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                "📞 <b>YANGI TELEFON OVOZI</b>\n\n"
                f"👤 Ism: {escape(message.from_user.full_name)}\n"
                f"🆔 ID: <code>{message.from_user.id}</code>\n"
                f"📞 Telefon: <code>{escape(phone)}</code>\n\n"
                f"💰 Tasdiqlansa bonus: <b>{VOTE_BONUS:,} so‘m</b>",
                reply_markup=admin_buttons(message.from_user.id),
            )
        except Exception as e:
            logging.error("Admin notification error: %s", e)


# ============================================================
# ADMIN OVOZINI TASDIQLASH
# ============================================================

@dp.callback_query(F.data.startswith("approve_vote_"))
async def approve_vote(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "Ruxsat yo‘q.",
            show_alert=True,
        )
        return

    try:
        vote_id = int(
            callback.data.replace("approve_vote_", "")
        )
    except ValueError:
        await callback.answer("Xato ID.")
        return

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT user_id, status, bonus
        FROM votes
        WHERE id = ?
    """, (vote_id,))

    row = cur.fetchone()

    if not row:
        conn.close()
        await callback.answer("Ovoz topilmadi.")
        return

    user_id, status, bonus = row

    if status == "approved":
        conn.close()
        await callback.answer(
            "Bu ovoz avval tasdiqlangan.",
            show_alert=True,
        )
        return

    cur.execute("""
        UPDATE votes
        SET status = 'approved'
        WHERE id = ?
    """, (vote_id,))

    cur.execute("""
        UPDATE users
        SET balance = balance + ?
        WHERE user_id = ?
    """, (bonus, user_id))

    cur.execute("""
        INSERT INTO balance_history(
            user_id, amount, operation
        )
        VALUES (?, ?, ?)
    """, (user_id, bonus, "Ovoz bonusi"))

    conn.commit()
    conn.close()

    new_balance = get_balance(user_id)

    try:
        await bot.send_message(
            user_id,
            "🎉 <b>Ovozingiz tasdiqlandi!</b>\n\n"
            f"💰 Balansingizga <b>{bonus:,} so‘m</b> qo‘shildi.\n"
            f"💵 Joriy balans: <b>{new_balance:,} so‘m</b>",
            reply_markup=user_keyboard(),
        )
    except Exception:
        pass

    await callback.message.answer(
        f"✅ Ovoz tasdiqlandi.\n"
        f"User: <code>{user_id}</code>\n"
        f"Bonus: <b>{bonus:,} so‘m</b>"
    )

    await callback.answer()


# ============================================================
# SAVOL-JAVOB
# ============================================================

class QuestionStates(StatesGroup):
    question = State()


@dp.message(F.text == "❓ Savol-javob")
async def question_start(
    message: Message,
    state: FSMContext,
):
    if is_admin(message.from_user.id):
        return

    stat("savol_javob")
    set_chat(message.from_user.id, 1, "savol-javob")

    await state.set_state(QuestionStates.question)

    await message.answer(
        "❓ <b>Savolingizni yozing.</b>\n\n"
        "Savolingiz adminga yuboriladi. "
        "Admin sizga shu suhbat orqali javob beradi.",
        reply_markup=user_keyboard(),
    )


@dp.message(QuestionStates.question)
async def receive_question(
    message: Message,
    state: FSMContext,
):
    if not message.text:
        await message.answer(
            "❗ Savolingizni matn ko‘rinishida yuboring."
        )
        return

    await state.clear()
    set_chat(message.from_user.id, 1, "savol-javob")

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                "❓ <b>YANGI SAVOL</b>\n\n"
                f"👤 {escape(message.from_user.full_name)}\n"
                f"🆔 User: <code>{message.from_user.id}</code>\n\n"
                f"💬 {escape(message.text)}",
                reply_markup=admin_buttons(message.from_user.id),
            )
        except Exception as e:
            logging.error("Question error: %s", e)

    await message.answer(
        "✅ Savolingiz adminga yuborildi.\n"
        "Javobni kuting.",
        reply_markup=user_keyboard(),
    )


# ============================================================
# ADMIN JAVOB BERISH
# ============================================================

class AdminReplyStates(StatesGroup):
    text = State()


@dp.callback_query(F.data.startswith("reply_"))
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
        user_id = int(
            callback.data.replace("reply_", "")
        )
    except ValueError:
        await callback.answer("ID xato.")
        return

    await state.update_data(reply_user_id=user_id)
    await state.set_state(AdminReplyStates.text)

    await callback.message.answer(
        f"💬 <b>{user_id}</b> foydalanuvchiga "
        "yuboriladigan javobni yozing."
    )

    await callback.answer()


@dp.message(AdminReplyStates.text)
async def admin_reply_send(
    message: Message,
    state: FSMContext,
):
    if not is_admin(message.from_user.id):
        return

    data = await state.get_data()
    user_id = data.get("reply_user_id")

    if not user_id:
        await state.clear()
        return

    try:
        if message.text:
            await bot.send_message(
                user_id,
                "👨‍💼 <b>Admin javobi:</b>\n\n"
                f"{escape(message.text)}",
            )
        else:
            await bot.copy_message(
                chat_id=user_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
            )

        set_chat(user_id, 1, "admin bilan suhbat")

        await message.answer(
            "✅ Javob foydalanuvchiga yuborildi."
        )

    except Exception as e:
        await message.answer(
            f"❌ Xatolik: {escape(str(e))}"
        )

    await state.clear()


@dp.callback_query(F.data.startswith("close_"))
async def close_chat(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "Ruxsat yo‘q.",
            show_alert=True,
        )
        return

    try:
        user_id = int(
            callback.data.replace("close_", "")
        )
    except ValueError:
        await callback.answer("ID xato.")
        return

    set_chat(user_id, 0, "yopilgan")

    try:
        await bot.send_message(
            user_id,
            "🔴 <b>Admin suhbatni yopdi.</b>\n\n"
            "Yana savol bo‘lsa, ❓ Savol-javob "
            "tugmasini bosing.",
            reply_markup=user_keyboard(),
        )
    except Exception:
        pass

    await callback.message.answer(
        "✅ Suhbat yopildi."
    )
    await callback.answer()


# ============================================================
# REFERRAL
# ============================================================

@dp.message(F.text == "👥 Do‘stlarni taklif qilish")
async def referral_handler(message: Message):
    if is_admin(message.from_user.id):
        return

    stat("referral")

    info = await bot.get_me()
    link = (
        f"https://t.me/{info.username}"
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

    count = int(row[0]) if row else 0

    await message.answer(
        "👥 <b>DO‘STLARNI TAKLIF QILISH</b>\n\n"
        "🔗 Sizning taklif havolangiz:\n"
        f"<code>{link}</code>\n\n"
        f"👤 Takliflar: <b>{count}</b>\n"
        f"💰 Har bir do‘st uchun: "
        f"<b>{REFERRAL_BONUS:,} so‘m</b>\n\n"
        "Do‘stingiz aynan shu havola orqali botga "
        "birinchi marta kirishi kerak.",
        reply_markup=user_keyboard(),
    )


# ============================================================
# PUL YECHISH
# ============================================================

class WithdrawStates(StatesGroup):
    card = State()


@dp.message(F.text == "💳 Pul yechish")
async def withdraw_start(
    message: Message,
    state: FSMContext,
):
    if is_admin(message.from_user.id):
        return

    stat("pul_yechish")

    balance = get_balance(message.from_user.id)

    if balance < MIN_WITHDRAW:
        await message.answer(
            "❌ <b>Sizning balansingizda yetarli "
            "mablag‘ yo‘q.</b>\n\n"
            "Ko‘proq ovoz berib yoki do‘stlaringizni "
            "taklif qilib balansni to‘ldiring.\n\n"
            f"💰 Hozirgi balans: <b>{balance:,} so‘m</b>\n"
            f"💳 Minimal yechish: "
            f"<b>{MIN_WITHDRAW:,} so‘m</b>",
            reply_markup=user_keyboard(),
        )
        return

    await state.set_state(WithdrawStates.card)

    await message.answer(
        "💳 <b>PUL YECHISH</b>\n\n"
        f"Balansingiz: <b>{balance:,} so‘m</b>\n\n"
        "Karta raqamingizni yuboring.",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="❌ Bekor qilish")]
            ],
            resize_keyboard=True,
            is_persistent=True,
        ),
    )


@dp.message(WithdrawStates.card)
async def receive_card(
    message: Message,
    state: FSMContext,
):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer(
            "❌ Bekor qilindi.",
            reply_markup=user_keyboard(),
        )
        return

    card = re.sub(r"\D", "", message.text or "")

    if not 12 <= len(card) <= 19:
        await message.answer(
            "❗ Karta raqami noto‘g‘ri.\n"
            "Iltimos, qayta yuboring."
        )
        return

    balance = get_balance(message.from_user.id)

    if balance < MIN_WITHDRAW:
        await state.clear()
        await message.answer(
            "❌ Balansingiz yetarli emas.",
            reply_markup=user_keyboard(),
        )
        return

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO withdrawals(
            user_id, card_number, amount, status
        )
        VALUES (?, ?, ?, 'pending')
    """, (
        message.from_user.id,
        card,
        balance,
    ))

    conn.commit()
    conn.close()

    await state.clear()

    await message.answer(
        "✅ Pul yechish so‘rovingiz qabul qilindi.\n\n"
        "📨 Karta raqamingiz adminlarga yuborildi.",
        reply_markup=user_keyboard(),
    )

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                "💳 <b>YANGI PUL YECHISH SO‘ROVI</b>\n\n"
                f"👤 {escape(message.from_user.full_name)}\n"
                f"🆔 User: <code>{message.from_user.id}</code>\n"
                f"💰 Summa: <b>{balance:,} so‘m</b>\n"
                f"💳 Karta: <code>{escape(card)}</code>",
                reply_markup=admin_buttons(message.from_user.id),
            )
        except Exception as e:
            logging.error("Withdrawal admin error: %s", e)


# ============================================================
# ADMIN BILAN BOG‘LANISH
# ============================================================

@dp.message(F.text == "👨‍💼 Admin bilan bog‘lanish")
async def contact_admin(message: Message):
    if is_admin(message.from_user.id):
        return

    stat("admin_contact")

    contact = setting_get("admin_contact")

    if contact:
        await message.answer(
            "👨‍💼 <b>Admin bilan bog‘lanish</b>\n\n"
            f"{escape(contact)}",
            reply_markup=user_keyboard(),
        )
    else:
        await message.answer(
            "ℹ️ Hozircha admin qo‘shilmagan yoki "
            "hozir barcha adminlar band.",
            reply_markup=user_keyboard(),
        )


# ============================================================
# LOYIHALAR
# ============================================================

@dp.message(F.text == "📌 Loyihalar")
async def projects_handler(message: Message):
    if is_admin(message.from_user.id):
        return

    stat("loyihalar")

    name = setting_get("project_name")
    link = setting_get("project_link")

    if not link:
        await message.answer(
            "📌 <b>Loyihalar</b>\n\n"
            "Hozircha loyiha qo‘shilmagan.",
            reply_markup=user_keyboard(),
        )
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=name or "🔗 Loyihaga kirish",
                    url=link,
                )
            ]
        ]
    )

    await message.answer(
        f"📌 <b>{escape(name or 'Loyiha')}</b>",
        reply_markup=keyboard,
    )


# ============================================================
# ADMIN STATISTIKA
# ============================================================

@dp.message(F.text == "📊 Statistika")
async def admin_statistics(message: Message):
    if not is_admin(message.from_user.id):
        return

    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM users")
    users = cur.fetchone()[0]

    cur.execute(
        "SELECT COALESCE(SUM(balance), 0) FROM users"
    )
    total_balance = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM votes")
    votes = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM votes
        WHERE vote_type = 'phone'
    """)
    phone_votes = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM referrals")
    referrals = cur.fetchone()[0]

    cur.execute("""
        SELECT COALESCE(SUM(bonus), 0)
        FROM referrals
    """)
    referral_money = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM withdrawals
        WHERE status = 'pending'
    """)
    pending_withdrawals = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM conversations
        WHERE active = 1
    """)
    active_chats = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM withdrawals")
    withdrawals = cur.fetchone()[0]

    conn.close()

    await message.answer(
        "📊 <b>BOT STATISTIKASI</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{users}</b>\n"
        f"🗳 Ovozlar: <b>{votes}</b>\n"
        f"📞 Telefon ovozlari: <b>{phone_votes}</b>\n"
        f"👥 Referral: <b>{referrals}</b>\n"
        f"💰 Referral bonuslari: "
        f"<b>{referral_money:,} so‘m</b>\n"
        f"💵 Jami balans: "
        f"<b>{total_balance:,} so‘m</b>\n"
        f"💳 Jami yechishlar: <b>{withdrawals}</b>\n"
        f"⏳ Kutilayotgan yechishlar: "
        f"<b>{pending_withdrawals}</b>\n"
        f"💬 Faol suhbatlar: <b>{active_chats}</b>",
        reply_markup=admin_keyboard(),
    )


# ============================================================
# ADMIN FOYDALANUVCHILAR
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
        ORDER BY rowid DESC
        LIMIT 30
    """)

    rows = cur.fetchall()
    conn.close()

    if not rows:
        await message.answer(
            "👥 Hozircha foydalanuvchilar yo‘q.",
            reply_markup=admin_keyboard(),
        )
        return

    text = "👥 <b>FOYDALANUVCHILAR</b>\n\n"

    for user_id, name, username, balance in rows:
        user_name = escape(name or "Noma’lum")
        uname = (
            f"@{escape(username)}"
            if username else "username yo‘q"
        )

        text += (
            f"👤 {user_name}\n"
            f"🆔 <code>{user_id}</code>\n"
            f"🔗 {uname}\n"
            f"💰 {balance:,} so‘m\n\n"
        )

    await message.answer(
        text,
        reply_markup=admin_keyboard(),
    )


# ============================================================
# ADMIN TELEFONLAR
# ============================================================

@dp.message(F.text == "📞 Telefon raqamlari")
async def admin_phones(message: Message):
    if not is_admin(message.from_user.id):
        return

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT user_id, first_name, phone
        FROM users
        WHERE phone != ''
        ORDER BY rowid DESC
        LIMIT 50
    """)

    rows = cur.fetchall()
    conn.close()

    if not rows:
        await message.answer(
            "📞 Hozircha telefon raqamlari yo‘q.",
            reply_markup=admin_keyboard(),
        )
        return

    text = "📞 <b>TELEFON RAQAMLARI</b>\n\n"

    for user_id, name, phone in rows:
        text += (
            f"👤 {escape(name or '')}\n"
            f"🆔 <code>{user_id}</code>\n"
            f"📞 <code>{escape(phone)}</code>\n\n"
        )

    await message.answer(
        text,
        reply_markup=admin_keyboard(),
    )


# ============================================================
# ADMIN PUL YECHISHLAR
# ============================================================

@dp.message(F.text == "💳 Pul yechishlar")
async def admin_withdrawals(message: Message):
    if not is_admin(message.from_user.id):
        return

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, user_id, card_number, amount, status
        FROM withdrawals
        ORDER BY id DESC
        LIMIT 50
    """)

    rows = cur.fetchall()
    conn.close()

    if not rows:
        await message.answer(
            "💳 Hozircha pul yechish so‘rovlari yo‘q.",
            reply_markup=admin_keyboard(),
        )
        return

    text = "💳 <b>PUL YECHISHLAR</b>\n\n"

    for wid, user_id, card, amount, status in rows:
        text += (
            f"🆔 So‘rov: <code>{wid}</code>\n"
            f"👤 User: <code>{user_id}</code>\n"
            f"💰 Summa: <b>{amount:,} so‘m</b>\n"
            f"💳 Karta: <code>{escape(card)}</code>\n"
            f"📌 Holat: <b>{escape(status)}</b>\n\n"
        )

    await message.answer(
        text,
        reply_markup=admin_keyboard(),
    )


# ============================================================
# ADMIN SAVOL-JAVOBLAR
# ============================================================

@dp.message(F.text == "❓ Savol-javoblar")
async def admin_questions(message: Message):
    if not is_admin(message.from_user.id):
        return

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT user_id, active, topic
        FROM conversations
        ORDER BY rowid DESC
        LIMIT 50
    """)

    rows = cur.fetchall()
    conn.close()

    if not rows:
        await message.answer(
            "❓ Hozircha suhbatlar yo‘q.",
            reply_markup=admin_keyboard(),
        )
        return

    text = "❓ <b>SUHBATLAR</b>\n\n"

    for user_id, active, topic in rows:
        status = "🟢 Faol" if active else "🔴 Yopilgan"

        text += (
            f"👤 User: <code>{user_id}</code>\n"
            f"📌 {escape(topic or '')}\n"
            f"{status}\n\n"
        )

    await message.answer(
        text,
        reply_markup=admin_keyboard(),
    )


# ============================================================
# ADMIN OVOZLAR
# ============================================================

@dp.message(F.text == "🗳 Ovozlar")
async def admin_votes(message: Message):
    if not is_admin(message.from_user.id):
        return

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, user_id, vote_type, phone, status, bonus
        FROM votes
        ORDER BY id DESC
        LIMIT 50
    """)

    rows = cur.fetchall()
    conn.close()

    if not rows:
        await message.answer(
            "🗳 Hozircha ovozlar yo‘q.",
            reply_markup=admin_keyboard(),
        )
        return

    for vote_id, user_id, vote_type, phone, status, bonus in rows:
        text = (
            "🗳 <b>OVOZ</b>\n\n"
            f"🆔 Ovoz: <code>{vote_id}</code>\n"
            f"👤 User: <code>{user_id}</code>\n"
            f"📌 Tur: {escape(vote_type)}\n"
            f"📞 Telefon: {escape(phone or '-')}\n"
            f"📊 Holat: <b>{escape(status)}</b>\n"
            f"💰 Bonus: <b>{bonus:,} so‘m</b>"
        )

        buttons = []

        if status == "pending":
            buttons.append([
                InlineKeyboardButton(
                    text="✅ Tasdiqlash",
                    callback_data=f"approve_vote_{vote_id}",
                ),
                InlineKeyboardButton(
                    text="❌ Rad etish",
                    callback_data=f"reject_vote_{vote_id}",
                ),
            ])

        buttons.append([
            InlineKeyboardButton(
                text="💬 Foydalanuvchiga yozish",
                callback_data=f"reply_{user_id}",
            )
        ])

        await message.answer(
            text,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=buttons
            ),
        )


@dp.callback_query(F.data.startswith("reject_vote_"))
async def reject_vote(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "Ruxsat yo‘q.",
            show_alert=True,
        )
        return

    try:
        vote_id = int(
            callback.data.replace("reject_vote_", "")
        )
    except ValueError:
        await callback.answer("Xato.")
        return

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT user_id, status
        FROM votes
        WHERE id = ?
    """, (vote_id,))

    row = cur.fetchone()

    if not row:
        conn.close()
        await callback.answer("Topilmadi.")
        return

    user_id, status = row

    if status != "pending":
        conn.close()
        await callback.answer(
            "Bu ovoz allaqachon ko‘rib chiqilgan."
        )
        return

    cur.execute("""
        UPDATE votes
        SET status = 'rejected'
        WHERE id = ?
    """, (vote_id,))

    conn.commit()
    conn.close()

    try:
        await bot.send_message(
            user_id,
            "❌ Ovoz so‘rovingiz admin tomonidan rad etildi.",
            reply_markup=user_keyboard(),
        )
    except Exception:
        pass

    await callback.message.answer(
        f"❌ Ovoz #{vote_id} rad etildi."
    )
    await callback.answer()


# ============================================================
# ADMIN SOZLAMALARI
# ============================================================

class SettingsStates(StatesGroup):
    vote_link = State()
    admin_contact = State()
    project_name = State()
    project_link = State()


@dp.message(F.text == "🔗 Ovoz havolasi")
async def setting_vote_link(
    message: Message,
    state: FSMContext,
):
    if not is_admin(message.from_user.id):
        return

    current = setting_get("vote_link")

    await state.set_state(SettingsStates.vote_link)

    await message.answer(
        "🔗 <b>Ovoz havolasi</b>\n\n"
        f"Hozirgi: {escape(current or 'Qo‘yilmagan')}\n\n"
        "Yangi havolani yuboring."
    )


@dp.message(SettingsStates.vote_link)
async def save_vote_link(
    message: Message,
    state: FSMContext,
):
    if not is_admin(message.from_user.id):
        return

    value = (message.text or "").strip()

    if not re.match(r"^https?://", value):
        await message.answer(
            "❗ Havola http:// yoki https:// bilan boshlansin."
        )
        return

    setting_set("vote_link", value)
    await state.clear()

    await message.answer(
        "✅ Ovoz havolasi saqlandi.",
        reply_markup=admin_keyboard(),
    )


@dp.message(F.text == "👨‍💼 Admin kontakt")
async def setting_admin_contact(
    message: Message,
    state: FSMContext,
):
    if not is_admin(message.from_user.id):
        return

    current = setting_get("admin_contact")

    await state.set_state(SettingsStates.admin_contact)

    await message.answer(
        "👨‍💼 <b>Admin kontakt</b>\n\n"
        f"Hozirgi: {escape(current or 'Qo‘yilmagan')}\n\n"
        "Telefon raqam yoki Telegram username yuboring."
    )


@dp.message(SettingsStates.admin_contact)
async def save_admin_contact(
    message: Message,
    state: FSMContext,
):
    if not is_admin(message.from_user.id):
        return

    value = (message.text or "").strip()

    if not value:
        await message.answer("❗ Kontakt yozing.")
        return

    setting_set("admin_contact", value)
    await state.clear()

    await message.answer(
        "✅ Admin kontakti saqlandi.",
        reply_markup=admin_keyboard(),
    )


@dp.message(F.text == "📌 Loyiha sozlamalari")
async def setting_project(
    message: Message,
    state: FSMContext,
):
    if not is_admin(message.from_user.id):
        return

    current_name = setting_get("project_name")
    current_link = setting_get("project_link")

    await state.set_state(SettingsStates.project_name)

    await message.answer(
        "📌 <b>Loyiha sozlamalari</b>\n\n"
        f"Hozirgi nom: {escape(current_name or 'Yo‘q')}\n"
        f"Hozirgi havola: {escape(current_link or 'Yo‘q')}\n\n"
        "Loyiha nomini yuboring."
    )


@dp.message(SettingsStates.project_name)
async def save_project_name(
    message: Message,
    state: FSMContext,
):
    if not is_admin(message.from_user.id):
        return

    name = (message.text or "").strip()

    if not name:
        await message.answer("❗ Loyiha nomini yozing.")
        return

    await state.update_data(project_name=name)
    await state.set_state(SettingsStates.project_link)

    await message.answer(
        "🔗 Endi loyiha havolasini yuboring."
    )


@dp.message(SettingsStates.project_link)
async def save_project_link(
    message: Message,
    state: FSMContext,
):
    if not is_admin(message.from_user.id):
        return

    link = (message.text or "").strip()

    if not re.match(r"^https?://", link):
        await message.answer(
            "❗ Havola http:// yoki https:// bilan boshlansin."
        )
        return

    data = await state.get_data()
    name = data.get("project_name", "Loyiha")

    setting_set("project_name", name)
    setting_set("project_link", link)

    await state.clear()

    await message.answer(
        "✅ Loyiha saqlandi.",
        reply_markup=admin_keyboard(),
    )


# ============================================================
# ADMIN BALANS BOSHQARUVI
# ============================================================

class BalanceStates(StatesGroup):
    user_id = State()
    amount = State()


@dp.message(F.text == "💰 Balans boshqaruvi")
async def balance_admin_start(
    message: Message,
    state: FSMContext,
):
    if not is_admin(message.from_user.id):
        return

    await state.set_state(BalanceStates.user_id)

    await message.answer(
        "💰 <b>Balans boshqaruvi</b>\n\n"
        "Foydalanuvchi Telegram ID raqamini yuboring."
    )


@dp.message(BalanceStates.user_id)
async def balance_admin_user(
    message: Message,
    state: FSMContext,
):
    if not is_admin(message.from_user.id):
        return

    try:
        user_id = int((message.text or "").strip())
    except ValueError:
        await message.answer(
            "❗ ID faqat raqam bo‘lsin."
        )
        return

    if not get_user(user_id):
        await message.answer(
            "❌ Foydalanuvchi topilmadi."
        )
        return

    await state.update_data(user_id=user_id)
    await state.set_state(BalanceStates.amount)

    await message.answer(
        "💵 Summani yuboring.\n\n"
        "Masalan:\n"
        "<code>30000</code> — qo‘shish\n"
        "<code>-30000</code> — ayirish"
    )


@dp.message(BalanceStates.amount)
async def balance_admin_amount(
    message: Message,
    state: FSMContext,
):
    if not is_admin(message.from_user.id):
        return

    try:
        amount = int((message.text or "").strip())
    except ValueError:
        await message.answer(
            "❗ Summa raqam bo‘lishi kerak."
        )
        return

    if amount == 0:
        await message.answer("❗ 0 kiritmang.")
        return

    data = await state.get_data()
    user_id = data.get("user_id")

    if not user_id:
        await state.clear()
        return

    change_balance(
        user_id,
        amount,
        "Admin balans o‘zgarishi",
    )

    new_balance = get_balance(user_id)

    await state.clear()

    await message.answer(
        "✅ Balans yangilandi.\n\n"
        f"👤 User: <code>{user_id}</code>\n"
        f"💰 O‘zgarish: <b>{amount:,} so‘m</b>\n"
        f"💵 Yangi balans: <b>{new_balance:,} so‘m</b>",
        reply_markup=admin_keyboard(),
    )

    try:
        await bot.send_message(
            user_id,
            "💰 <b>Balansingiz yangilandi.</b>\n\n"
            f"O‘zgarish: <b>{amount:,} so‘m</b>\n"
            f"Joriy balans: <b>{new_balance:,} so‘m</b>",
        )
    except Exception:
        pass


# ============================================================
# BROADCAST
# ============================================================

class BroadcastStates(StatesGroup):
    message = State()


@dp.message(F.text == "📢 Xabar yuborish")
async def broadcast_start(
    message: Message,
    state: FSMContext,
):
    if not is_admin(message.from_user.id):
        return

    await state.set_state(BroadcastStates.message)

    await message.answer(
        "📢 <b>Broadcast</b>\n\n"
        "Yuboriladigan xabarni yuboring.\n"
        "Matn, rasm yoki boshqa Telegram xabari bo‘lishi mumkin."
    )


@dp.message(BroadcastStates.message)
async def broadcast_send(
    message: Message,
    state: FSMContext,
):
    if not is_admin(message.from_user.id):
        return

    await state.clear()

    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users")
    users = cur.fetchall()
    conn.close()

    success = 0
    failed = 0

    for (user_id,) in users:
        try:
            await bot.copy_message(
                chat_id=user_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
            )
            success += 1
            await asyncio.sleep(0.04)
        except Exception:
            failed += 1

    await message.answer(
        "📢 <b>Broadcast tugadi.</b>\n\n"
        f"✅ Yuborildi: <b>{success}</b>\n"
        f"❌ Xatolik: <b>{failed}</b>",
        reply_markup=admin_keyboard(),
    )


# ============================================================
# FOYDALANUVCHI MENYUSIGA QAYTISH
# ============================================================

@dp.message(F.text == "🏠 Foydalanuvchi menyusi")
async def user_menu_from_admin(message: Message):
    if not is_admin(message.from_user.id):
        return

    await message.answer(
        "🏠 Foydalanuvchi menyusi.",
        reply_markup=user_keyboard(),
    )


# ============================================================
# DAVOMLI FOYDALANUVCHI SUHBATI
# ============================================================

MENU_TEXTS = {
    "📌 Loyihalar",
    "🗳 Ovoz berish",
    "💰 Balans",
    "💳 Pul yechish",
    "👥 Do‘stlarni taklif qilish",
    "❓ Savol-javob",
    "👨‍💼 Admin bilan bog‘lanish",
    "🏠 Foydalanuvchi menyusi",
}


@dp.message()
async def fallback_handler(message: Message):
    if is_admin(message.from_user.id):
        await message.answer(
            "👨‍💼 Admin paneldan kerakli bo‘limni tanlang.",
            reply_markup=admin_keyboard(),
        )
        return

    if not message.text:
        return

    if message.text in MENU_TEXTS:
        return

    if not chat_active(message.from_user.id):
        await message.answer(
            "👇 Kerakli bo‘limni tanlang.",
            reply_markup=user_keyboard(),
        )
        return

    # Foydalanuvchining davomli suhbati.
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                "💬 <b>FOYDALANUVCHIDAN XABAR</b>\n\n"
                f"👤 {escape(message.from_user.full_name)}\n"
                f"🆔 User: <code>{message.from_user.id}</code>\n\n"
                f"💬 {escape(message.text)}",
                reply_markup=admin_buttons(message.from_user.id),
            )
        except Exception as e:
            logging.error(
                "Conversation notification error: %s",
                e,
            )

    await message.answer(
        "✅ Xabaringiz adminga yuborildi.",
        reply_markup=user_keyboard(),
    )


# ============================================================
# ISHGA TUSHIRISH
# ============================================================

async def main():
    init_db()

    if not BOT_TOKEN or BOT_TOKEN == "BU_YERGA_BOT_TOKENINGIZNI_YOZING":
        raise RuntimeError(
            "BOT_TOKEN sozlanmagan. Railway Variables ichida "
            "BOT_TOKEN qo‘ying."
        )

    if ADMIN_IDS == [123456789]:
        logging.warning(
            "ADMIN_IDS hali o‘zgartirilmagan. "
            "O‘zingizning Telegram ID raqamingizni yozing."
        )

    logging.info("BOT ISHGA TUSHYAPTI")

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
