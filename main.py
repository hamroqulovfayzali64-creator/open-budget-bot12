# =========================================================
# OPEN BUDGET BOT
# HAMMASI BIRTA MAIN.PY ICHIDA
# =========================================================

import asyncio
import logging
import sqlite3
from pathlib import Path
from contextlib import closing
from html import escape

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage


# =========================================================
# 🔴🔴🔴 BOT TOKENINGIZNI SHU YERGA YOZING 🔴🔴🔴
# =========================================================

BOT_TOKEN = "8615736731:AAF7LGgYsKCq_JjV9qFPmFV6psTAS4mlQ_g"


# =========================================================
# 👑 ADMIN ID
# =========================================================
# Telegram ID raqamingizni shu yerga yozing.
# Masalan:
# ADMIN_IDS = [7998053914]

ADMIN_IDS = [
    7998053914
]


# =========================================================
# SOZLAMALAR
# =========================================================

DB_PATH = Path("bot.db")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# =========================================================
# DATABASE
# =========================================================

def get_db():
    return sqlite3.connect(DB_PATH)


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
                joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

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

        conn.commit()


def add_user(user_id, username="", first_name="", language="uz"):
    with closing(get_db()) as conn:
        cur = conn.cursor()

        cur.execute("""
            INSERT OR IGNORE INTO users
            (user_id, username, first_name, language)
            VALUES (?, ?, ?, ?)
        """, (
            user_id,
            username or "",
            first_name or "",
            language
        ))

        cur.execute("""
            UPDATE users
            SET username = ?, first_name = ?
            WHERE user_id = ?
        """, (
            username or "",
            first_name or "",
            user_id
        ))

        conn.commit()


def set_language(user_id, language):
    with closing(get_db()) as conn:
        conn.execute(
            "UPDATE users SET language=? WHERE user_id=?",
            (language, user_id)
        )
        conn.commit()


def get_language(user_id):
    with closing(get_db()) as conn:
        row = conn.execute(
            "SELECT language FROM users WHERE user_id=?",
            (user_id,)
        ).fetchone()

    if row and row[0]:
        return row[0]

    return "uz"


def get_all_users():
    with closing(get_db()) as conn:
        rows = conn.execute(
            "SELECT user_id FROM users"
        ).fetchall()

    return [row[0] for row in rows]


def save_phone(user_id, phone):
    with closing(get_db()) as conn:
        conn.execute(
            "UPDATE users SET phone=? WHERE user_id=?",
            (phone, user_id)
        )
        conn.commit()


def get_projects():
    with closing(get_db()) as conn:
        return conn.execute("""
            SELECT
                id,
                name_uz,
                name_ru,
                url,
                phone_votes,
                link_votes,
                clicks
            FROM projects
            ORDER BY id DESC
        """).fetchall()


def get_project(project_id):
    with closing(get_db()) as conn:
        return conn.execute("""
            SELECT
                id,
                name_uz,
                name_ru,
                url,
                phone_votes,
                link_votes,
                clicks
            FROM projects
            WHERE id=?
        """, (project_id,)).fetchone()


def add_project(name_uz, name_ru, url):
    with closing(get_db()) as conn:
        conn.execute("""
            INSERT INTO projects
            (name_uz, name_ru, url)
            VALUES (?, ?, ?)
        """, (
            name_uz,
            name_ru,
            url
        ))
        conn.commit()


def delete_project(project_id):
    with closing(get_db()) as conn:
        conn.execute(
            "DELETE FROM projects WHERE id=?",
            (project_id,)
        )
        conn.commit()


def increase_project_click(project_id, user_id):
    with closing(get_db()) as conn:
        conn.execute("""
            UPDATE projects
            SET clicks = clicks + 1
            WHERE id=?
        """, (project_id,))

        conn.execute("""
            UPDATE users
            SET project_clicks = project_clicks + 1
            WHERE user_id=?
        """, (user_id,))

        conn.commit()


def increase_link_vote(project_id, user_id):
    with closing(get_db()) as conn:
        conn.execute("""
            UPDATE projects
            SET link_votes = link_votes + 1
            WHERE id=?
        """, (project_id,))

        conn.execute("""
            UPDATE users
            SET vote_clicks = vote_clicks + 1,
                voted = 1
            WHERE user_id=?
        """, (user_id,))

        conn.commit()


def increase_phone_vote(project_id, user_id):
    with closing(get_db()) as conn:
        conn.execute("""
            UPDATE projects
            SET phone_votes = phone_votes + 1
            WHERE id=?
        """, (project_id,))

        conn.execute("""
            UPDATE users
            SET voted = 1,
                vote_clicks = vote_clicks + 1
            WHERE user_id=?
        """, (user_id,))

        conn.commit()


# =========================================================
# TEXTLAR
# =========================================================

TEXTS = {

    "uz": {
        "welcome":
            "👋 Assalomu alaykum!\n\n"
            "🇺🇿 Ochiq byudjet botiga xush kelibsiz.",

        "select_language":
            "🌐 Tilni tanlang:",

        "select_project":
            "📌 Loyihani tanlang:",

        "no_projects":
            "📌 Hozircha loyiha yo‘q.",

        "project_info":
            "📌 <b>{name}</b>\n\n"
            "Quyidagi amallardan birini tanlang:",

        "phone_vote":
            "📞 Telefon raqamingiz orqali ovoz berish uchun "
            "quyidagi tugmani bosing:",

        "send_phone":
            "📱 Telefon raqamingizni yuboring:",

        "phone_saved":
            "✅ Telefon raqamingiz qabul qilindi.\n\n"
            "Ovozingiz hisobga olindi.",

        "link_vote":
            "🔗 Ovoz berish sahifasiga o'tish uchun quyidagi "
            "tugmani bosing.",

        "link_missing":
            "⚠️ Ushbu loyiha uchun hozircha havola qo‘shilmagan.",

        "back":
            "⬅️ Orqaga",

        "contact_admin":
            "💬 Admin bilan bog‘lanish",

        "send_admin_message":
            "✍️ Xabaringizni yuboring.\n\n"
            "Matn, rasm, video yoki fayl yuborishingiz mumkin.",

        "message_sent":
            "✅ Xabaringiz adminga yuborildi.",

        "admin_panel":
            "👑 <b>Admin panel</b>\n\n"
            "Kerakli bo‘limni tanlang:",

        "statistics":
            "📊 <b>Statistika</b>\n\n"
            "👥 Foydalanuvchilar: <b>{users}</b>\n"
            "📌 Loyihalar: <b>{projects}</b>\n"
            "🖱 Loyiha bosishlari: <b>{clicks}</b>\n"
            "📞 Telefon ovozlari: <b>{phone}</b>\n"
            "🔗 Havola ovozlari: <b>{link}</b>\n"
            "🗳 Jami ovozlar: <b>{total_votes}</b>",

        "add_project_name":
            "➕ Loyiha qo‘shish\n\n"
            "Loyiha nomini yuboring:",

        "add_project_link":
            "🔗 Endi loyiha havolasini yuboring.\n\n"
            "Masalan:\n"
            "https://example.com",

        "project_added":
            "✅ Loyiha muvaffaqiyatli qo‘shildi.",

        "broadcast":
            "📢 Barcha foydalanuvchilarga yubormoqchi bo‘lgan "
            "xabarni yuboring.\n\n"
            "Matn, rasm, video yoki fayl bo‘lishi mumkin.",

        "broadcast_done":
            "✅ Xabar yuborildi.\n\n"
            "📨 Yuborildi: {sent}\n"
            "❌ Xatolik: {failed}",

        "admin_reply":
            "✍️ Foydalanuvchiga yubormoqchi bo‘lgan javobingizni yozing:",

        "reply_sent":
            "✅ Javob foydalanuvchiga yuborildi.",

        "reply_failed":
            "❌ Foydalanuvchiga yuborib bo‘lmadi.",

        "unknown":
            "⚠️ Iltimos, menyudagi tugmalardan foydalaning."
    },


    "ru": {
        "welcome":
            "👋 Здравствуйте!\n\n"
            "🇷🇺 Добро пожаловать в бот Открытого бюджета.",

        "select_language":
            "🌐 Выберите язык:",

        "select_project":
            "📌 Выберите проект:",

        "no_projects":
            "📌 Пока проектов нет.",

        "project_info":
            "📌 <b>{name}</b>\n\n"
            "Выберите действие:",

        "phone_vote":
            "📞 Для голосования по номеру телефона "
            "нажмите кнопку ниже:",

        "send_phone":
            "📱 Отправьте свой номер телефона:",

        "phone_saved":
            "✅ Номер телефона получен.\n\n"
            "Ваш голос учтён.",

        "link_vote":
            "🔗 Для перехода на страницу голосования "
            "нажмите кнопку ниже.",

        "link_missing":
            "⚠️ Для этого проекта пока нет ссылки.",

        "back":
            "⬅️ Назад",

        "contact_admin":
            "💬 Связаться с администратором",

        "send_admin_message":
            "✍️ Отправьте ваше сообщение.\n\n"
            "Можно отправить текст, фото, видео или файл.",

        "message_sent":
            "✅ Ваше сообщение отправлено администратору.",

        "admin_panel":
            "👑 <b>Панель администратора</b>\n\n"
            "Выберите раздел:",

        "statistics":
            "📊 <b>Статистика</b>\n\n"
            "👥 Пользователи: <b>{users}</b>\n"
            "📌 Проекты: <b>{projects}</b>\n"
            "🖱 Переходы: <b>{clicks}</b>\n"
            "📞 Голоса по телефону: <b>{phone}</b>\n"
            "🔗 Голоса по ссылке: <b>{link}</b>\n"
            "🗳 Всего голосов: <b>{total_votes}</b>",

        "add_project_name":
            "➕ Добавление проекта\n\n"
            "Отправьте название проекта:",

        "add_project_link":
            "🔗 Теперь отправьте ссылку проекта.\n\n"
            "Например:\n"
            "https://example.com",

        "project_added":
            "✅ Проект успешно добавлен.",

        "broadcast":
            "📢 Отправьте сообщение, которое нужно "
            "отправить всем пользователям.\n\n"
            "Можно отправить текст, фото, видео или файл.",

        "broadcast_done":
            "✅ Сообщение отправлено.\n\n"
            "📨 Отправлено: {sent}\n"
            "❌ Ошибок: {failed}",

        "admin_reply":
            "✍️ Напишите ответ пользователю:",

        "reply_sent":
            "✅ Ответ отправлен пользователю.",

        "reply_failed":
            "❌ Не удалось отправить ответ.",

        "unknown":
            "⚠️ Используйте кнопки меню."
    }
}


# =========================================================
# KEYBOARDS
# =========================================================

def language_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🇺🇿 O‘zbek"),
                KeyboardButton(text="🇷🇺 Русский")
            ]
        ],
        resize_keyboard=True
    )


def user_keyboard_uz():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📌 Loyihalar")
            ],
            [
                KeyboardButton(text="🌐 Tilni almashtirish"),
                KeyboardButton(text="💬 Admin bilan bog‘lanish")
            ]
        ],
        resize_keyboard=True
    )


def user_keyboard_ru():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📌 Проекты")
            ],
            [
                KeyboardButton(text="🌐 Сменить язык"),
                KeyboardButton(text="💬 Связаться с администратором")
            ]
        ],
        resize_keyboard=True
    )


def admin_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📊 Statistika"),
                KeyboardButton(text="➕ Loyiha qo‘shish")
            ],
            [
                KeyboardButton(text="📢 Reklama yuborish")
            ],
            [
                KeyboardButton(text="📌 Loyihalar")
            ],
            [
                KeyboardButton(text="⬅️ Foydalanuvchi menyusi")
            ]
        ],
        resize_keyboard=True
    )


def project_keyboard(projects, lang="uz"):
    buttons = []

    for project in projects:
        project_id = project[0]

        name = project[1] if lang == "uz" else project[2]

        buttons.append([
            InlineKeyboardButton(
                text=f"📌 {name}",
                callback_data=f"project:{project_id}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text=TEXTS[lang]["back"],
            callback_data="user_back"
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def project_action_keyboard(project_id, has_url, lang):
    buttons = []

    buttons.append([
        InlineKeyboardButton(
            text="📞 Ovoz berish",
            callback_data=f"phone_vote:{project_id}"
        )
    ])

    if has_url:
        buttons.append([
            InlineKeyboardButton(
                text="🔗 Havola orqali ovoz berish",
                callback_data=f"link_vote:{project_id}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text=TEXTS[lang]["back"],
            callback_data="projects_back"
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_reply_keyboard(user_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="↩️ Javob berish",
                    callback_data=f"admin_reply:{user_id}"
                )
            ]
        ]
    )


# =========================================================
# STATES
# =========================================================

class AddProjectState(StatesGroup):
    name = State()
    link = State()


class BroadcastState(StatesGroup):
    message = State()


class AdminReplyState(StatesGroup):
    message = State()


class ContactAdminState(StatesGroup):
    message = State()


# =========================================================
# START
# =========================================================

@dp.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    await state.clear()

    user = message.from_user

    add_user(
        user.id,
        user.username,
        user.first_name,
        "uz"
    )

    await message.answer(
        TEXTS["uz"]["welcome"],
        reply_markup=language_keyboard()
    )


# =========================================================
# LANGUAGE
# =========================================================

@dp.message(F.text == "🇺🇿 O‘zbek")
async def uz_language(message: Message):
    set_language(message.from_user.id, "uz")

    await message.answer(
        TEXTS["uz"]["welcome"],
        reply_markup=user_keyboard_uz()
    )


@dp.message(F.text == "🇷🇺 Русский")
async def ru_language(message: Message):
    set_language(message.from_user.id, "ru")

    await message.answer(
        TEXTS["ru"]["welcome"],
        reply_markup=user_keyboard_ru()
    )


@dp.message(F.text.in_({
    "🌐 Tilni almashtirish",
    "🌐 Сменить язык"
}))
async def change_language(message: Message):
    await message.answer(
        TEXTS["uz"]["select_language"],
        reply_markup=language_keyboard()
    )


# =========================================================
# USER PROJECTS
# =========================================================

@dp.message(F.text.in_({
    "📌 Loyihalar",
    "📌 Проекты"
}))
async def show_projects(message: Message):
    user_id = message.from_user.id
    lang = get_language(user_id)

    projects = get_projects()

    if not projects:
        await message.answer(
            TEXTS[lang]["no_projects"]
        )
        return

    await message.answer(
        TEXTS[lang]["select_project"],
        reply_markup=project_keyboard(projects, lang)
    )


@dp.callback_query(F.data.startswith("project:"))
async def project_selected(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = get_language(user_id)

    project_id = int(callback.data.split(":")[1])

    project = get_project(project_id)

    if not project:
        await callback.answer(
            "Loyiha topilmadi",
            show_alert=True
        )
        return

    increase_project_click(
        project_id,
        user_id
    )

    name = project[1] if lang == "uz" else project[2]
    url = project[3]

    text = TEXTS[lang]["project_info"].format(
        name=escape(name)
    )

    await callback.message.edit_text(
        text,
        reply_markup=project_action_keyboard(
            project_id,
            bool(url),
            lang
        )
    )

    await callback.answer()


# =========================================================
# PHONE VOTE
# =========================================================

pending_phone_votes = {}


@dp.callback_query(F.data.startswith("phone_vote:"))
async def phone_vote_start(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = get_language(user_id)

    project_id = int(
        callback.data.split(":")[1]
    )

    project = get_project(project_id)

    if not project:
        await callback.answer(
            "Loyiha topilmadi",
            show_alert=True
        )
        return

    pending_phone_votes[user_id] = project_id

    phone_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="📱 Telefon raqamimni yuborish",
                    request_contact=True
                )
            ],
            [
                KeyboardButton(
                    text=TEXTS[lang]["back"]
                )
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

    await callback.message.answer(
        TEXTS[lang]["phone_vote"] + "\n\n" +
        TEXTS[lang]["send_phone"],
        reply_markup=phone_keyboard
    )

    await callback.answer()


@dp.message(F.contact)
async def contact_handler(message: Message):
    user_id = message.from_user.id
    lang = get_language(user_id)

    if user_id not in pending_phone_votes:
        return

    project_id = pending_phone_votes.pop(user_id)

    phone = message.contact.phone_number

    save_phone(
        user_id,
        phone
    )

    increase_phone_vote(
        project_id,
        user_id
    )

    await message.answer(
        TEXTS[lang]["phone_saved"],
        reply_markup=(
            user_keyboard_uz()
            if lang == "uz"
            else user_keyboard_ru()
        )
    )


# =========================================================
# LINK VOTE
# =========================================================

@dp.callback_query(F.data.startswith("link_vote:"))
async def link_vote(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = get_language(user_id)

    project_id = int(
        callback.data.split(":")[1]
    )

    project = get_project(project_id)

    if not project:
        await callback.answer(
            "Loyiha topilmadi",
            show_alert=True
        )
        return

    url = project[3]

    if not url:
        await callback.answer(
            TEXTS[lang]["link_missing"],
            show_alert=True
        )
        return

    increase_link_vote(
        project_id,
        user_id
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔗 Ovoz berish",
                    url=url
                )
            ],
            [
                InlineKeyboardButton(
                    text=TEXTS[lang]["back"],
                    callback_data=f"project:{project_id}"
                )
            ]
        ]
    )

    await callback.message.answer(
        TEXTS[lang]["link_vote"],
        reply_markup=keyboard
    )

    await callback.answer()


# =========================================================
# BACK
# =========================================================

@dp.callback_query(F.data == "projects_back")
async def projects_back(callback: CallbackQuery):
    lang = get_language(callback.from_user.id)

    projects = get_projects()

    if not projects:
        await callback.message.edit_text(
            TEXTS[lang]["no_projects"]
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        TEXTS[lang]["select_project"],
        reply_markup=project_keyboard(
            projects,
            lang
        )
    )

    await callback.answer()


@dp.callback_query(F.data == "user_back")
async def user_back(callback: CallbackQuery):
    lang = get_language(callback.from_user.id)

    await callback.message.delete()

    await callback.message.answer(
        TEXTS[lang]["welcome"],
        reply_markup=(
            user_keyboard_uz()
            if lang == "uz"
            else user_keyboard_ru()
        )
    )

    await callback.answer()


# =========================================================
# CONTACT ADMIN
# =========================================================

@dp.message(F.text.in_({
    "💬 Admin bilan bog‘lanish",
    "💬 Связаться с администратором"
}))
async def contact_admin_start(
    message: Message,
    state: FSMContext
):
    lang = get_language(message.from_user.id)

    await state.set_state(
        ContactAdminState.message
    )

    await message.answer(
        TEXTS[lang]["send_admin_message"],
        reply_markup=ReplyKeyboardRemove()
    )


@dp.message(ContactAdminState.message)
async def contact_admin_message(
    message: Message,
    state: FSMContext,
    bot: Bot
):
    user = message.from_user

    username = (
        f"@{user.username}"
        if user.username
        else "username yo‘q"
    )

    admin_text = (
        "📩 <b>Yangi foydalanuvchi xabari</b>\n\n"
        f"👤 Ism: {escape(user.full_name)}\n"
        f"🔹 Username: {escape(username)}\n"
        f"🆔 ID: <code>{user.id}</code>"
    )

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                admin_text,
                reply_markup=admin_reply_keyboard(
                    user.id
                )
            )

            await bot.copy_message(
                chat_id=admin_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )

        except Exception as e:
            logging.error(
                "Admin message error: %s",
                e
            )

    lang = get_language(user.id)

    await state.clear()

    await message.answer(
        TEXTS[lang]["message_sent"],
        reply_markup=(
            user_keyboard_uz()
            if lang == "uz"
            else user_keyboard_ru()
        )
    )


# =========================================================
# ADMIN CHECK
# =========================================================

def is_admin(user_id):
    return user_id in ADMIN_IDS


# =========================================================
# ADMIN COMMAND
# =========================================================

@dp.message(Command("admin"))
async def admin_command(message: Message):
    if not is_admin(message.from_user.id):
        return

    await message.answer(
        TEXTS["uz"]["admin_panel"],
        reply_markup=admin_keyboard()
    )


# =========================================================
# ADMIN STATISTICS
# =========================================================

@dp.message(F.text == "📊 Statistika")
async def statistics_handler(message: Message):
    if not is_admin(message.from_user.id):
        return

    with closing(get_db()) as conn:
        users = conn.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]

        projects = conn.execute(
            "SELECT COUNT(*) FROM projects"
        ).fetchone()[0]

        clicks = conn.execute(
            "SELECT COALESCE(SUM(clicks),0) FROM projects"
        ).fetchone()[0]

        phone = conn.execute(
            "SELECT COALESCE(SUM(phone_votes),0) FROM projects"
        ).fetchone()[0]

        link = conn.execute(
            "SELECT COALESCE(SUM(link_votes),0) FROM projects"
        ).fetchone()[0]

    total_votes = phone + link

    await message.answer(
        TEXTS["uz"]["statistics"].format(
            users=users,
            projects=projects,
            clicks=clicks,
            phone=phone,
            link=link,
            total_votes=total_votes
        )
    )


# =========================================================
# ADMIN ADD PROJECT
# =========================================================

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
        TEXTS["uz"]["add_project_name"]
    )


@dp.message(AddProjectState.name)
async def add_project_name(
    message: Message,
    state: FSMContext
):
    if not is_admin(message.from_user.id):
        return

    name = message.text.strip()

    if not name:
        await message.answer(
            "❌ Loyiha nomi bo‘sh bo‘lishi mumkin emas."
        )
        return

    await state.update_data(
        project_name=name
    )

    await state.set_state(
        AddProjectState.link
    )

    await message.answer(
        TEXTS["uz"]["add_project_link"]
    )


@dp.message(AddProjectState.link)
async def add_project_link(
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

    name = data["project_name"]

    add_project(
        name_uz=name,
        name_ru=name,
        url=url
    )

    await state.clear()

    await message.answer(
        TEXTS["uz"]["project_added"],
        reply_markup=admin_keyboard()
    )


# =========================================================
# ADMIN SHOW PROJECTS
# =========================================================

@dp.message(F.text == "📌 Loyihalar")
async def admin_or_user_projects(message: Message):
    if is_admin(message.from_user.id):
        projects = get_projects()

        if not projects:
            await message.answer(
                "📌 Hozircha loyiha yo‘q."
            )
            return

        buttons = []

        for p in projects:
            buttons.append([
                InlineKeyboardButton(
                    text=f"📌 {p[1]}",
                    callback_data=f"admin_project:{p[0]}"
                )
            ])

        await message.answer(
            "📌 <b>Loyihalar</b>",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=buttons
            )
        )
        return

    await show_projects(message)


@dp.callback_query(F.data.startswith("admin_project:"))
async def admin_project_selected(
    callback: CallbackQuery
):
    if not is_admin(callback.from_user.id):
        return

    project_id = int(
        callback.data.split(":")[1]
    )

    project = get_project(project_id)

    if not project:
        await callback.answer(
            "Loyiha topilmadi",
            show_alert=True
        )
        return

    text = (
        f"📌 <b>{escape(project[1])}</b>\n\n"
        f"🔗 {escape(project[3] or 'Havola yo‘q')}\n\n"
        f"🖱 Bosishlar: {project[6]}\n"
        f"📞 Telefon ovozlari: {project[4]}\n"
        f"🔗 Havola ovozlari: {project[5]}"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🗑 O‘chirish",
                    callback_data=f"delete_project:{project_id}"
                )
            ]
        ]
    )

    await callback.message.answer(
        text,
        reply_markup=keyboard
    )

    await callback.answer()


@dp.callback_query(F.data.startswith("delete_project:"))
async def delete_project_handler(
    callback: CallbackQuery
):
    if not is_admin(callback.from_user.id):
        return

    project_id = int(
        callback.data.split(":")[1]
    )

    delete_project(project_id)

    await callback.message.edit_text(
        "✅ Loyiha o‘chirildi."
    )

    await callback.answer()


# =========================================================
# ADMIN BROADCAST
# =========================================================

@dp.message(F.text == "📢 Reklama yuborish")
async def broadcast_start(
    message: Message,
    state: FSMContext
):
    if not is_admin(message.from_user.id):
        return

    await state.set_state(
        BroadcastState.message
    )

    await message.answer(
        TEXTS["uz"]["broadcast"],
        reply_markup=ReplyKeyboardRemove()
    )


@dp.message(BroadcastState.message)
async def broadcast_message(
    message: Message,
    state: FSMContext,
    bot: Bot
):
    if not is_admin(message.from_user.id):
        return

    users = get_all_users()

    sent = 0
    failed = 0

    for user_id in users:
        try:
            await bot.copy_message(
                chat_id=user_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )

            sent += 1

        except Exception as e:
            failed += 1

            logging.error(
                "Broadcast error %s: %s",
                user_id,
                e
            )

        await asyncio.sleep(0.04)

    await state.clear()

    await message.answer(
        TEXTS["uz"]["broadcast_done"].format(
            sent=sent,
            failed=failed
        ),
        reply_markup=admin_keyboard()
    )


# =========================================================
# ADMIN REPLY BUTTON
# =========================================================

admin_reply_targets = {}


@dp.callback_query(F.data.startswith("admin_reply:"))
async def admin_reply_start(
    callback: CallbackQuery,
    state: FSMContext
):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    user_id = int(
        callback.data.split(":")[1]
    )

    admin_reply_targets[
        callback.from_user.id
    ] = user_id

    await state.set_state(
        AdminReplyState.message
    )

    await callback.message.answer(
        TEXTS["uz"]["admin_reply"],
        reply_markup=ReplyKeyboardRemove()
    )

    await callback.answer()


@dp.message(AdminReplyState.message)
async def admin_reply_message(
    message: Message,
    state: FSMContext,
    bot: Bot
):
    if not is_admin(message.from_user.id):
        return

    admin_id = message.from_user.id

    user_id = admin_reply_targets.get(
        admin_id
    )

    if not user_id:
        await state.clear()
        return

    try:
        await bot.copy_message(
            chat_id=user_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id
        )

        await message.answer(
            TEXTS["uz"]["reply_sent"],
            reply_markup=admin_keyboard()
        )

    except Exception as e:
        logging.error(
            "Reply error: %s",
            e
        )

        await message.answer(
            TEXTS["uz"]["reply_failed"],
            reply_markup=admin_keyboard()
        )

    admin_reply_targets.pop(
        admin_id,
        None
    )

    await state.clear()


# =========================================================
# ADMIN BACK TO USER MENU
# =========================================================

@dp.message(F.text == "⬅️ Foydalanuvchi menyusi")
async def admin_to_user_menu(message: Message):
    if not is_admin(message.from_user.id):
        return

    await message.answer(
        TEXTS["uz"]["welcome"],
        reply_markup=user_keyboard_uz()
    )


# =========================================================
# ADMIN / START USER MENU
# =========================================================

@dp.message(F.text == "⬅️ Orqaga")
async def simple_back(message: Message):
    lang = get_language(message.from_user.id)

    await message.answer(
        TEXTS[lang]["welcome"],
        reply_markup=(
            user_keyboard_uz()
            if lang == "uz"
            else user_keyboard_ru()
        )
    )


# =========================================================
# UNKNOWN MESSAGE
# =========================================================

@dp.message()
async def unknown_handler(message: Message):
    user_id = message.from_user.id

    if is_admin(user_id):
        await message.answer(
            "👑 Admin panel uchun /admin buyrug‘idan foydalaning.",
            reply_markup=admin_keyboard()
        )
        return

    lang = get_language(user_id)

    await message.answer(
        TEXTS[lang]["unknown"],
        reply_markup=(
            user_keyboard_uz()
            if lang == "uz"
            else user_keyboard_ru()
        )
    )


# =========================================================
# START BOT
# =========================================================

async def main():
    print("========================================")
    print("OPEN BUDGET BOT ISHLAMOQDA")
    print("========================================")

    init_db()

    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN bo‘sh! main.py ichidagi BOT_TOKEN joyiga "
            "Telegram BotFather tokenini yozing."
        )

    if BOT_TOKEN == "BU_YERGA_BOTFATHER_TOKENINGIZNI_QOYING":
        raise RuntimeError(
            "BOT_TOKEN hali almashtirilmagan! "
            "main.py ichidagi BOT_TOKEN joyiga haqiqiy tokenni yozing."
        )

    bot = Bot(
        token=BOT_TOKEN
    )

    me = await bot.get_me()

    print(
        f"Bot ulandi: @{me.username}",
        flush=True
    )

    await dp.start_polling(
        bot,
        allowed_updates=dp.resolve_used_update_types()
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot to‘xtatildi.")