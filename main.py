# =========================================================
# MAIN.PY — TELEGRAM BOT
# =========================================================
# TOKEN VA ADMIN ID JOYLARI ENG YUQORIDA KO'RSATILGAN
# =========================================================

import asyncio
import logging
import os
import re
import sqlite3
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
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


# =========================================================
# 1. BOT TOKEN — SHU YERGA TOKENINGIZNI QO'YING
# =========================================================
#
# BotFather bergan tokenni qo'shtirnoq ICHIGA yozing.
#
# MASALAN:
#
# BOT_TOKEN = "123456789:AAxxxxxxxxxxxxxxxxxxxxxxxx"
#
# TOKENNI O'ZGARTIRIB, FAQAT O'Z TOKENINGIZNI YOZING.
#
# =========================================================

BOT_TOKEN = "8615736731:AAF7LGgYsKCq_JjV9qFPmFV6psTAS4mlQ_g"


# =========================================================
# 2. ADMIN TELEGRAM ID — SHU YERGA O'Z IDINGIZNI YOZING
# =========================================================
#
# MASALAN:
#
# ADMIN_IDS = [
#     7998053914
# ]
#
# Bu BOT TOKEN EMAS.
# Bu sizning Telegram ID raqamingiz.
#
# =========================================================

ADMIN_IDS = [
    123456789
]


# =========================================================
# DATABASE
# =========================================================

DB_FILE = Path("bot.db")


# =========================================================
# TOKEN TEKSHIRISH
# =========================================================

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT TOKEN BO'SH! "
        "main.py yuqorisidagi BOT_TOKEN joyiga "
        "BotFather tokenini yozing."
    )

if BOT_TOKEN == "SHU YERGA BOT TOKENINGIZNI YOZING":
    raise RuntimeError(
        "BOT TOKEN HALI QO'YILMAGAN! "
        "main.py yuqorisidagi BOT_TOKEN joyiga "
        "BotFather tokenini yozing."
    )


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)


# =========================================================
# BOT
# =========================================================

bot = Bot(token=BOT_TOKEN)

dp = Dispatcher(
    storage=MemoryStorage()
)


# =========================================================
# DATABASE FUNKSIYALARI
# =========================================================

def db():
    return sqlite3.connect(DB_FILE)


def init_db():

    con = db()
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT DEFAULT '',
            first_name TEXT DEFAULT '',
            language TEXT DEFAULT 'uz',
            phone TEXT DEFAULT '',
            voted INTEGER DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name_uz TEXT NOT NULL,
            name_ru TEXT NOT NULL,
            url TEXT DEFAULT '',
            clicks INTEGER DEFAULT 0,
            vote_clicks INTEGER DEFAULT 0
        )
    """)

    con.commit()
    con.close()


# =========================================================
# USER
# =========================================================

def add_user(message: Message):

    user = message.from_user

    con = db()
    cur = con.cursor()

    cur.execute("""
        INSERT INTO users (
            user_id,
            username,
            first_name
        )
        VALUES (?, ?, ?)

        ON CONFLICT(user_id) DO UPDATE SET
            username = excluded.username,
            first_name = excluded.first_name
    """, (
        user.id,
        user.username or "",
        user.first_name or ""
    ))

    con.commit()
    con.close()


def save_phone(user_id: int, phone: str):

    con = db()
    cur = con.cursor()

    cur.execute(
        """
        UPDATE users
        SET phone=?
        WHERE user_id=?
        """,
        (phone, user_id)
    )

    con.commit()
    con.close()


def get_user_language(user_id: int):

    con = db()
    cur = con.cursor()

    cur.execute(
        """
        SELECT language
        FROM users
        WHERE user_id=?
        """,
        (user_id,)
    )

    row = cur.fetchone()

    con.close()

    if row and row[0]:
        return row[0]

    return "uz"


def set_language(user_id: int, language: str):

    con = db()
    cur = con.cursor()

    cur.execute(
        """
        UPDATE users
        SET language=?
        WHERE user_id=?
        """,
        (language, user_id)
    )

    con.commit()
    con.close()


def mark_voted(user_id: int):

    con = db()
    cur = con.cursor()

    cur.execute(
        """
        UPDATE users
        SET voted=1
        WHERE user_id=?
        """,
        (user_id,)
    )

    con.commit()
    con.close()


def get_all_users():

    con = db()
    cur = con.cursor()

    cur.execute(
        "SELECT user_id FROM users"
    )

    rows = cur.fetchall()

    con.close()

    return [
        row[0]
        for row in rows
    ]


# =========================================================
# PROJECTS
# =========================================================

def get_projects():

    con = db()
    cur = con.cursor()

    cur.execute("""
        SELECT
            id,
            name_uz,
            name_ru,
            url,
            clicks,
            vote_clicks
        FROM projects
        ORDER BY id DESC
    """)

    rows = cur.fetchall()

    con.close()

    return rows


def get_project(project_id: int):

    con = db()
    cur = con.cursor()

    cur.execute("""
        SELECT
            id,
            name_uz,
            name_ru,
            url,
            clicks,
            vote_clicks
        FROM projects
        WHERE id=?
    """, (project_id,))

    row = cur.fetchone()

    con.close()

    return row


def increase_project_click(project_id: int):

    con = db()
    cur = con.cursor()

    cur.execute("""
        UPDATE projects
        SET clicks = clicks + 1
        WHERE id=?
    """, (project_id,))

    con.commit()
    con.close()


def increase_vote_click(project_id: int):

    con = db()
    cur = con.cursor()

    cur.execute("""
        UPDATE projects
        SET vote_clicks = vote_clicks + 1
        WHERE id=?
    """, (project_id,))

    con.commit()
    con.close()


# =========================================================
# STATISTIKA
# =========================================================

def get_statistics():

    con = db()
    cur = con.cursor()

    cur.execute(
        "SELECT COUNT(*) FROM users"
    )

    users = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM users
        WHERE phone IS NOT NULL
        AND phone != ''
    """)

    phones = cur.fetchone()[0]

    cur.execute(
        "SELECT COUNT(*) FROM users WHERE voted=1"
    )

    voted = cur.fetchone()[0]

    cur.execute(
        "SELECT COALESCE(SUM(clicks), 0) FROM projects"
    )

    project_clicks = cur.fetchone()[0]

    cur.execute(
        "SELECT COALESCE(SUM(vote_clicks), 0) FROM projects"
    )

    vote_clicks = cur.fetchone()[0]

    con.close()

    return (
        users,
        phones,
        voted,
        project_clicks,
        vote_clicks
    )


# =========================================================
# FSM
# =========================================================

class AddProject(StatesGroup):

    name_uz = State()
    name_ru = State()
    url = State()


class ReplyUser(StatesGroup):

    message = State()


class Broadcast(StatesGroup):

    message = State()


class VotePhone(StatesGroup):

    waiting_phone = State()


# =========================================================
# KEYBOARDS
# =========================================================

def language_keyboard():

    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="🇺🇿 O'zbek"
                ),
                KeyboardButton(
                    text="🇷🇺 Русский"
                )
            ]
        ],
        resize_keyboard=True
    )


def user_keyboard_uz():

    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="📌 Loyihalar"
                )
            ],
            [
                KeyboardButton(
                    text="🗳 Ovoz berish"
                )
            ],
            [
                KeyboardButton(
                    text="🌐 Tilni almashtirish"
                )
            ]
        ],
        resize_keyboard=True
    )


def user_keyboard_ru():

    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="📌 Проекты"
                )
            ],
            [
                KeyboardButton(
                    text="🗳 Голосование"
                )
            ],
            [
                KeyboardButton(
                    text="🌐 Сменить язык"
                )
            ]
        ],
        resize_keyboard=True
    )


def admin_keyboard():

    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="📊 Statistika"
                )
            ],
            [
                KeyboardButton(
                    text="➕ Loyiha qo'shish"
                )
            ],
            [
                KeyboardButton(
                    text="📢 Reklama yuborish"
                )
            ],
            [
                KeyboardButton(
                    text="👥 Foydalanuvchilar"
                )
            ],
            [
                KeyboardButton(
                    text="🏠 Asosiy menyu"
                )
            ]
        ],
        resize_keyboard=True
    )


def phone_keyboard():

    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="📱 Telefon raqamimni yuborish",
                    request_contact=True
                )
            ],
            [
                KeyboardButton(
                    text="❌ Bekor qilish"
                )
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )


# =========================================================
# ADMIN
# =========================================================

def is_admin(user_id: int):

    return user_id in ADMIN_IDS


# =========================================================
# START
# =========================================================

@dp.message(CommandStart())
async def start_handler(
    message: Message,
    state: FSMContext
):

    await state.clear()

    add_user(message)

    if is_admin(message.from_user.id):

        await message.answer(
            "👨‍💼 Xush kelibsiz!\n\n"
            "Admin panel:",
            reply_markup=admin_keyboard()
        )

        return

    await message.answer(
        "🇺🇿 Tilni tanlang / "
        "🇷🇺 Выберите язык:",
        reply_markup=language_keyboard()
    )


# =========================================================
# LANGUAGE
# =========================================================

@dp.message(F.text == "🇺🇿 O'zbek")
async def uz_language(message: Message):

    add_user(message)

    set_language(
        message.from_user.id,
        "uz"
    )

    await message.answer(
        "🇺🇿 O'zbek tili tanlandi.",
        reply_markup=user_keyboard_uz()
    )


@dp.message(F.text == "🇷🇺 Русский")
async def ru_language(message: Message):

    add_user(message)

    set_language(
        message.from_user.id,
        "ru"
    )

    await message.answer(
        "🇷🇺 Русский язык выбран.",
        reply_markup=user_keyboard_ru()
    )


@dp.message(F.text.in_({
    "🌐 Tilni almashtirish",
    "🌐 Сменить язык"
}))
async def change_language(message: Message):

    add_user(message)

    await message.answer(
        "🇺🇿 Tilni tanlang / "
        "🇷🇺 Выберите язык:",
        reply_markup=language_keyboard()
    )


# =========================================================
# HOME
# =========================================================

@dp.message(F.text == "🏠 Asosiy menyu")
async def home_handler(
    message: Message,
    state: FSMContext
):

    await state.clear()

    if is_admin(message.from_user.id):

        await message.answer(
            "🏠 Admin panel:",
            reply_markup=admin_keyboard()
        )

        return

    language = get_user_language(
        message.from_user.id
    )

    if language == "ru":

        await message.answer(
            "🏠 Главное меню.",
            reply_markup=user_keyboard_ru()
        )

    else:

        await message.answer(
            "🏠 Asosiy menyu.",
            reply_markup=user_keyboard_uz()
        )


# =========================================================
# PROJECTS
# =========================================================

@dp.message(F.text.in_({
    "📌 Loyihalar",
    "📌 Проекты"
}))
async def projects_handler(message: Message):

    add_user(message)

    language = get_user_language(
        message.from_user.id
    )

    projects = get_projects()

    if not projects:

        if language == "ru":

            await message.answer(
                "📌 Пока проектов нет."
            )

        else:

            await message.answer(
                "📌 Hozircha loyihalar yo'q."
            )

        return

    buttons = []

    for project in projects:

        project_id = project[0]
        name_uz = project[1]
        name_ru = project[2]

        name = (
            name_ru
            if language == "ru"
            else name_uz
        )

        buttons.append([
            InlineKeyboardButton(
                text=name,
                callback_data=f"project:{project_id}"
            )
        ])

    await message.answer(
        (
            "📌 Выберите проект:"
            if language == "ru"
            else "📌 Loyihani tanlang:"
        ),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )


# =========================================================
# PROJECT CALLBACK
# =========================================================

@dp.callback_query(
    F.data.startswith("project:")
)
async def project_callback(
    callback: CallbackQuery
):

    try:

        project_id = int(
            callback.data.split(":")[1]
        )

    except Exception:

        await callback.answer(
            "Xato.",
            show_alert=True
        )

        return

    project = get_project(
        project_id
    )

    if not project:

        await callback.answer(
            "Loyiha topilmadi.",
            show_alert=True
        )

        return

    increase_project_click(
        project_id
    )

    language = get_user_language(
        callback.from_user.id
    )

    (
        _,
        name_uz,
        name_ru,
        url,
        _,
        _
    ) = project

    name = (
        name_ru
        if language == "ru"
        else name_uz
    )

    buttons = []

    if url:

        buttons.append([
            InlineKeyboardButton(
                text=(
                    "🔗 Перейти по ссылке"
                    if language == "ru"
                    else "🔗 Havolaga o'tish"
                ),
                url=url
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text=(
                "🗳 Проголосовать"
                if language == "ru"
                else "🗳 Ovoz berish"
            ),
            callback_data=f"vote:{project_id}"
        )
    ])

    await callback.message.answer(
        f"📌 <b>{name}</b>\n\n"
        + (
            "🗳 Нажмите кнопку ниже, "
            "чтобы проголосовать."
            if language == "ru"
            else
            "🗳 Ovoz berish uchun "
            "pastdagi tugmani bosing."
        ),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        ),
        parse_mode="HTML"
    )

    await callback.answer()


# =========================================================
# VOTING
# =========================================================

@dp.message(F.text.in_({
    "🗳 Ovoz berish",
    "🗳 Голосование"
}))
async def voting_handler(message: Message):

    add_user(message)

    projects = get_projects()

    if not projects:

        await message.answer(
            "Hozircha ovoz berish "
            "uchun loyiha yo'q."
        )

        return

    language = get_user_language(
        message.from_user.id
    )

    buttons = []

    for project in projects:

        project_id = project[0]
        name_uz = project[1]
        name_ru = project[2]

        name = (
            name_ru
            if language == "ru"
            else name_uz
        )

        buttons.append([
            InlineKeyboardButton(
                text=f"🗳 {name}",
                callback_data=f"vote:{project_id}"
            )
        ])

    await message.answer(
        (
            "🗳 Выберите проект для голосования:"
            if language == "ru"
            else
            "🗳 Ovoz bermoqchi bo'lgan "
            "loyihani tanlang:"
        ),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )


# =========================================================
# VOTE CALLBACK
# =========================================================

@dp.callback_query(
    F.data.startswith("vote:")
)
async def vote_callback(
    callback: CallbackQuery,
    state: FSMContext
):

    try:

        project_id = int(
            callback.data.split(":")[1]
        )

    except Exception:

        await callback.answer(
            "Xato.",
            show_alert=True
        )

        return

    project = get_project(
        project_id
    )

    if not project:

        await callback.answer(
            "Loyiha topilmadi.",
            show_alert=True
        )

        return

    increase_vote_click(
        project_id
    )

    await state.update_data(
        project_id=project_id
    )

    language = get_user_language(
        callback.from_user.id
    )

    if language == "ru":

        text = (
            "📞 <b>Для голосования отправьте "
            "свой номер телефона.</b>\n\n"
            "Нажмите кнопку ниже и отправьте "
            "свой номер телефона."
        )

    else:

        text = (
            "📞 <b>Ovoz berish uchun telefon "
            "raqamingizni yuboring.</b>\n\n"
            "Pastdagi tugmani bosib telefon "
            "raqamingizni yuboring."
        )

    await callback.message.answer(
        text,
        reply_markup=phone_keyboard(),
        parse_mode="HTML"
    )

    await state.set_state(
        VotePhone.waiting_phone
    )

    await callback.answer()


# =========================================================
# PHONE
# =========================================================

@dp.message(
    VotePhone.waiting_phone,
    F.contact
)
async def phone_received(
    message: Message,
    state: FSMContext
):

    contact = message.contact

    if (
        contact.user_id
        and contact.user_id
        != message.from_user.id
    ):

        await message.answer(
            "❌ Iltimos, o'zingizning "
            "telefon raqamingizni yuboring.",
            reply_markup=phone_keyboard()
        )

        return

    phone = contact.phone_number

    save_phone(
        message.from_user.id,
        phone
    )

    data = await state.get_data()

    project_id = data.get(
        "project_id"
    )

    mark_voted(
        message.from_user.id
    )

    project = None

    if project_id:

        project = get_project(
            project_id
        )

    project_name = "Noma'lum"

    if project:

        project_name = project[1]

    if message.from_user.username:

        username = (
            "@"
            + message.from_user.username
        )

    else:

        username = "username yo'q"

    admin_text = (
        "🗳 <b>YANGI OVOZ</b>\n\n"
        f"👤 Ism: {message.from_user.first_name}\n"
        f"🔹 Username: {username}\n"
        f"🆔 ID: <code>{message.from_user.id}</code>\n"
        f"📞 Telefon: <code>{phone}</code>\n"
        f"📌 Loyiha: <b>{project_name}</b>"
    )

    reply_button = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 Foydalanuvchiga javob",
                    callback_data=(
                        f"reply:{message.from_user.id}"
                    )
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
                reply_markup=reply_button
            )

        except Exception as e:

            logger.error(
                "Admin xabari xatosi: %s",
                e
            )

    language = get_user_language(
        message.from_user.id
    )

    if language == "ru":

        await message.answer(
            "✅ Спасибо! Ваши данные "
            "для голосования приняты.",
            reply_markup=user_keyboard_ru()
        )

    else:

        await message.answer(
            "✅ Rahmat! Ovoz berish uchun "
            "ma'lumotlaringiz qabul qilindi.",
            reply_markup=user_keyboard_uz()
        )

    await state.clear()


@dp.message(
    VotePhone.waiting_phone
)
async def phone_not_received(
    message: Message
):

    await message.answer(
        "📞 Iltimos, pastdagi "
        "«📱 Telefon raqamimni yuborish» "
        "tugmasini bosing.",
        reply_markup=phone_keyboard()
    )


# =========================================================
# ADMIN COMMAND
# =========================================================

@dp.message(Command("admin"))
async def admin_command(message: Message):

    if not is_admin(
        message.from_user.id
    ):
        return

    await message.answer(
        "👨‍💼 Admin panel:",
        reply_markup=admin_keyboard()
    )


# =========================================================
# STATISTICS
# =========================================================

@dp.message(F.text == "📊 Statistika")
async def statistics_handler(
    message: Message
):

    if not is_admin(
        message.from_user.id
    ):
        return

    (
        users,
        phones,
        voted,
        project_clicks,
        vote_clicks
    ) = get_statistics()

    projects = get_projects()

    text = (
        "📊 <b>STATISTIKA</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{users}</b>\n"
        f"📞 Telefon yuborganlar: <b>{phones}</b>\n"
        f"🗳 Ovoz berganlar: <b>{voted}</b>\n"
        f"📌 Loyiha bosishlari: <b>{project_clicks}</b>\n"
        f"🗳 Ovoz tugmasi bosilishi: "
        f"<b>{vote_clicks}</b>\n"
    )

    if projects:

        text += "\n<b>📌 Loyihalar:</b>\n\n"

        for project in projects:

            (
                project_id,
                name_uz,
                name_ru,
                url,
                clicks,
                vote_clicks_project
            ) = project

            text += (
                f"• <b>{name_uz}</b>\n"
                f"  🔗 Bosish: {clicks}\n"
                f"  🗳 Ovoz: "
                f"{vote_clicks_project}\n\n"
            )

    await message.answer(
        text,
        parse_mode="HTML"
    )


# =========================================================
# ADD PROJECT
# =========================================================

@dp.message(
    F.text == "➕ Loyiha qo'shish"
)
async def add_project_start(
    message: Message,
    state: FSMContext
):

    if not is_admin(
        message.from_user.id
    ):
        return

    await state.clear()

    await message.answer(
        "➕ Yangi loyiha nomini "
        "O'zbek tilida yozing:"
    )

    await state.set_state(
        AddProject.name_uz
    )


@dp.message(AddProject.name_uz)
async def add_project_name_uz(
    message: Message,
    state: FSMContext
):

    if not is_admin(
        message.from_user.id
    ):
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
        name_uz=name
    )

    await message.answer(
        "🇷🇺 Endi loyiha nomini "
        "Rus tilida yozing:"
    )

    await state.set_state(
        AddProject.name_ru
    )


@dp.message(AddProject.name_ru)
async def add_project_name_ru(
    message: Message,
    state: FSMContext
):

    if not is_admin(
        message.from_user.id
    ):
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
        name_ru=name
    )

    await message.answer(
        "🔗 Endi loyiha havolasini yuboring.\n\n"
        "Masalan:\n"
        "https://example.com"
    )

    await state.set_state(
        AddProject.url
    )


@dp.message(AddProject.url)
async def add_project_url(
    message: Message,
    state: FSMContext
):

    if not is_admin(
        message.from_user.id
    ):
        return

    url = (
        message.text or ""
    ).strip()

    if not re.match(
        r"^https?://",
        url,
        re.IGNORECASE
    ):

        await message.answer(
            "❌ Havola noto'g'ri.\n\n"
            "Havola http:// yoki https:// "
            "bilan boshlanishi kerak."
        )

        return

    data = await state.get_data()

    con = db()
    cur = con.cursor()

    cur.execute(
        """
        INSERT INTO projects (
            name_uz,
            name_ru,
            url
        )
        VALUES (?, ?, ?)
        """,
        (
            data["name_uz"],
            data["name_ru"],
            url
        )
    )

    con.commit()
    con.close()

    await state.clear()

    await message.answer(
        "✅ Loyiha muvaffaqiyatli qo'shildi!",
        reply_markup=admin_keyboard()
    )


# =========================================================
# BROADCAST
# =========================================================

@dp.message(
    F.text == "📢 Reklama yuborish"
)
async def broadcast_start(
    message: Message,
    state: FSMContext
):

    if not is_admin(
        message.from_user.id
    ):
        return

    await state.clear()

    await message.answer(
        "📢 Barcha foydalanuvchilarga "
        "yuboriladigan xabarni yuboring.\n\n"
        "Matn, rasm, video, hujjat, audio, "
        "voice, sticker va boshqa xabarlarni "
        "ham yuborishingiz mumkin.\n\n"
        "Bekor qilish: /cancel"
    )

    await state.set_state(
        Broadcast.message
    )


@dp.message(Broadcast.message)
async def broadcast_send(
    message: Message,
    state: FSMContext
):

    if not is_admin(
        message.from_user.id
    ):
        return

    users = get_all_users()

    if not users:

        await state.clear()

        await message.answer(
            "❌ Hali foydalanuvchilar yo'q.",
            reply_markup=admin_keyboard()
        )

        return

    status = await message.answer(
        f"📢 Xabar {len(users)} ta "
        "foydalanuvchiga yuborilmoqda..."
    )

    success = 0
    failed = 0

    for user_id in users:

        try:

            await bot.copy_message(
                chat_id=user_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )

            success += 1

        except Exception as e:

            failed += 1

            logger.warning(
                "Broadcast xatosi | "
                "user=%s | %s",
                user_id,
                e
            )

        await asyncio.sleep(0.06)

    await state.clear()

    try:

        await status.delete()

    except Exception:

        pass

    await message.answer(
        "✅ <b>REKLAMA YAKUNLANDI</b>\n\n"
        f"📨 Yuborildi: <b>{success}</b>\n"
        f"❌ Yuborilmadi: <b>{failed}</b>",
        parse_mode="HTML",
        reply_markup=admin_keyboard()
    )


# =========================================================
# ADMIN -> USER REPLY
# =========================================================

@dp.callback_query(
    F.data.startswith("reply:")
)
async def reply_start(
    callback: CallbackQuery,
    state: FSMContext
):

    if not is_admin(
        callback.from_user.id
    ):

        await callback.answer(
            "Ruxsat yo'q.",
            show_alert=True
        )

        return

    try:

        user_id = int(
            callback.data.split(":")[1]
        )

    except Exception:

        await callback.answer(
            "Foydalanuvchi ID xato.",
            show_alert=True
        )

        return

    await state.clear()

    await state.update_data(
        user_id=user_id
    )

    await callback.message.answer(
        f"💬 <b>{user_id}</b> ID foydalanuvchiga "
        "yuboriladigan xabarni yuboring.\n\n"
        "Matn, rasm, video va boshqa xabarlarni "
        "ham yuborishingiz mumkin.\n\n"
        "Bekor qilish: /cancel",
        parse_mode="HTML"
    )

    await state.set_state(
        ReplyUser.message
    )

    await callback.answer()


@dp.message(
    ReplyUser.message
)
async def send_admin_reply(
    message: Message,
    state: FSMContext
):

    if not is_admin(
        message.from_user.id
    ):
        return

    data = await state.get_data()

    user_id = data.get(
        "user_id"
    )

    if not user_id:

        await state.clear()

        await message.answer(
            "❌ Foydalanuvchi topilmadi.",
            reply_markup=admin_keyboard()
        )

        return

    try:

        await bot.copy_message(
            chat_id=user_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id
        )

        await message.answer(
            "✅ Xabar foydalanuvchiga yuborildi.",
            reply_markup=admin_keyboard()
        )

    except Exception as e:

        logger.error(
            "Admin reply xatosi: %s",
            e
        )

        await message.answer(
            "❌ Xabar yuborilmadi.\n\n"
            "Foydalanuvchi botni bloklagan "
            "bo'lishi mumkin.",
            reply_markup=admin_keyboard()
        )

    await state.clear()


# =========================================================
# USERS
# =========================================================

@dp.message(
    F.text == "👥 Foydalanuvchilar"
)
async def users_handler(
    message: Message
):

    if not is_admin(
        message.from_user.id
    ):
        return

    users = get_all_users()

    await message.answer(
        "👥 Botdagi jami foydalanuvchilar: "
        f"<b>{len(users)}</b>",
        parse_mode="HTML"
    )


@dp.message(Command("users"))
async def users_command(
    message: Message
):

    if not is_admin(
        message.from_user.id
    ):
        return

    users = get_all_users()

    await message.answer(
        f"👥 Jami foydalanuvchilar: "
        f"{len(users)}"
    )


# =========================================================
# /STATS
# =========================================================

@dp.message(Command("stats"))
async def stats_command(
    message: Message
):

    if not is_admin(
        message.from_user.id
    ):
        return

    (
        users,
        phones,
        voted,
        project_clicks,
        vote_clicks
    ) = get_statistics()

    await message.answer(
        "📊 <b>STATISTIKA</b>\n\n"
        f"👥 Foydalanuvchilar: {users}\n"
        f"📞 Telefonlar: {phones}\n"
        f"🗳 Ovozlar: {voted}\n"
        f"📌 Loyiha bosishlari: "
        f"{project_clicks}\n"
        f"🗳 Ovoz bosishlari: "
        f"{vote_clicks}",
        parse_mode="HTML"
    )


# =========================================================
# CANCEL
# =========================================================

@dp.message(Command("cancel"))
async def cancel_handler(
    message: Message,
    state: FSMContext
):

    await state.clear()

    if is_admin(
        message.from_user.id
    ):

        await message.answer(
            "❌ Amal bekor qilindi.",
            reply_markup=admin_keyboard()
        )

        return

    language = get_user_language(
        message.from_user.id
    )

    if language == "ru":

        await message.answer(
            "❌ Действие отменено.",
            reply_markup=user_keyboard_ru()
        )

    else:

        await message.answer(
            "❌ Amal bekor qilindi.",
            reply_markup=user_keyboard_uz()
        )


@dp.message(
    F.text == "❌ Bekor qilish"
)
async def cancel_button(
    message: Message,
    state: FSMContext
):

    await state.clear()

    language = get_user_language(
        message.from_user.id
    )

    if language == "ru":

        await message.answer(
            "❌ Действие отменено.",
            reply_markup=user_keyboard_ru()
        )

    else:

        await message.answer(
            "❌ Bekor qilindi.",
            reply_markup=user_keyboard_uz()
        )


# =========================================================
# FALLBACK
# =========================================================

@dp.message()
async def fallback_handler(
    message: Message
):

    add_user(message)

    if is_admin(
        message.from_user.id
    ):

        await message.answer(
            "👨‍💼 Admin paneldan "
            "kerakli bo'limni tanlang.",
            reply_markup=admin_keyboard()
        )

        return

    language = get_user_language(
        message.from_user.id
    )

    if language == "ru":

        await message.answer(
            "Выберите нужный раздел.",
            reply_markup=user_keyboard_ru()
        )

    else:

        await message.answer(
            "Kerakli bo'limni tanlang.",
            reply_markup=user_keyboard_uz()
        )


# =========================================================
# BOTNI ISHGA TUSHIRISH
# =========================================================

async def main():

    print(
        "======================================"
    )
    print(
        "MAIN.PY ISHLAYAPTI"
    )
    print(
        "DATABASE TEKSHIRILMOQDA"
    )
    print(
        "BOT ISHGA TUSHMOQDA..."
    )
    print(
        "======================================"
    )

    init_db()

    try:

        await bot.delete_webhook(
            drop_pending_updates=True
        )

    except Exception as e:

        logger.warning(
            "Webhook xatosi: %s",
            e
        )

    try:

        await dp.start_polling(
            bot,
            allowed_updates=(
                dp.resolve_used_update_types()
            )
        )

    finally:

        await bot.session.close()


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    try:

        asyncio.run(main())

    except KeyboardInterrupt:

        print(
            "Bot to'xtatildi."
        )

    except Exception as e:

        logger.exception(
            "BOT ISHLASHIDA XATO: %s",
            e
        )

        raise