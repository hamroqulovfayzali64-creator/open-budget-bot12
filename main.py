import asyncio
import logging
import sqlite3

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
from aiogram.exceptions import (
    TelegramForbiddenError,
    TelegramBadRequest,
    TelegramRetryAfter,
)

# =========================================================
# SOZLAMALAR
# =========================================================

BOT_TOKEN = "8615736731:AAEYW7RCc-YeGPI3mrod2dkyxeYR7QbRqOA"

ADMIN_IDS = [
    7998053914,
]

DB_NAME = "bot.db"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# =========================================================
# DATABASE
# =========================================================

def db_connect():
    return sqlite3.connect(DB_NAME)


def init_db():
    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            language TEXT DEFAULT 'uz',
            phone TEXT,
            voted INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            link TEXT NOT NULL,
            phone TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL
        )
    """)

    # Eski projects jadvalida phone ustuni bo'lmasa qo'shamiz
    cursor.execute("PRAGMA table_info(projects)")
    columns = [row[1] for row in cursor.fetchall()]

    if "phone" not in columns:
        cursor.execute(
            "ALTER TABLE projects ADD COLUMN phone TEXT"
        )

    conn.commit()
    conn.close()


def add_user(user_id, username, first_name):
    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR IGNORE INTO users
        (user_id, username, first_name)
        VALUES (?, ?, ?)
    """, (user_id, username, first_name))

    conn.commit()
    conn.close()


def set_language(user_id, language):
    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE users SET language = ? WHERE user_id = ?",
        (language, user_id)
    )

    conn.commit()
    conn.close()


def get_language(user_id):
    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT language FROM users WHERE user_id = ?",
        (user_id,)
    )

    result = cursor.fetchone()

    conn.close()

    if result:
        return result[0]

    return "uz"


def save_user_phone(user_id, phone):
    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE users SET phone = ? WHERE user_id = ?",
        (phone, user_id)
    )

    conn.commit()
    conn.close()


def delete_user(user_id):
    try:
        conn = db_connect()
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM users WHERE user_id = ?",
            (user_id,)
        )

        conn.commit()
        conn.close()

    except Exception as e:
        logging.error(
            f"Foydalanuvchini o‘chirishda xato: {e}"
        )


# =========================================================
# KEYBOARDS
# =========================================================

def language_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🇺🇿 O‘zbekcha",
                    callback_data="lang_uz"
                ),
                InlineKeyboardButton(
                    text="🇷🇺 Русский",
                    callback_data="lang_ru"
                )
            ]
        ]
    )


def uz_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📌 Loyihalar")
            ],
            [
                KeyboardButton(text="📰 Yangiliklar"),
                KeyboardButton(text="❓ Yordam")
            ]
        ],
        resize_keyboard=True
    )


def ru_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📌 Проекты")
            ],
            [
                KeyboardButton(text="📰 Новости"),
                KeyboardButton(text="❓ Помощь")
            ]
        ],
        resize_keyboard=True
    )


def admin_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📊 Statistika")
            ],
            [
                KeyboardButton(text="➕ Loyiha qo‘shish")
            ],
            [
                KeyboardButton(text="📰 Yangilik qo‘shish")
            ],
            [
                KeyboardButton(text="📢 Ommaviy xabar")
            ],
            [
                KeyboardButton(text="📋 Loyihalar")
            ],
            [
                KeyboardButton(text="❌ Admin panelni yopish")
            ]
        ],
        resize_keyboard=True
    )


# =========================================================
# TELEFON KEYBOARD
# =========================================================

def phone_keyboard_uz():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="📱 Telefon raqamimni yuborish",
                    request_contact=True
                )
            ],
            [
                KeyboardButton(text="❌ Bekor qilish")
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def phone_keyboard_ru():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="📱 Отправить мой номер",
                    request_contact=True
                )
            ],
            [
                KeyboardButton(text="❌ Отмена")
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )


# =========================================================
# OVOZ BERISH UCHUN HOLATLAR
# =========================================================

# user_id -> project_id
waiting_for_phone = {}


# =========================================================
# ADMIN HOLATLARI
# =========================================================

admin_project_waiting = set()
admin_project_name = {}
admin_project_link = {}

admin_news_waiting = set()
admin_broadcast_waiting = set()


# =========================================================
# ADMIN TEKSHIRISH
# =========================================================

def is_admin(user_id):
    return user_id in ADMIN_IDS


# =========================================================
# START
# =========================================================

@dp.message(CommandStart())
async def start_handler(message: Message):

    add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )

    await message.answer(
        "Assalomu alaykum! 👋\n\n"
        "Tilni tanlang / Выберите язык:",
        reply_markup=language_keyboard()
    )


# =========================================================
# TIL TANLASH
# =========================================================

@dp.callback_query(F.data == "lang_uz")
async def language_uz(callback: CallbackQuery):

    set_language(callback.from_user.id, "uz")

    await callback.message.answer(
        "🇺🇿 O‘zbek tili tanlandi.",
        reply_markup=uz_keyboard()
    )

    await callback.answer()


@dp.callback_query(F.data == "lang_ru")
async def language_ru(callback: CallbackQuery):

    set_language(callback.from_user.id, "ru")

    await callback.message.answer(
        "🇷🇺 Русский язык выбран.",
        reply_markup=ru_keyboard()
    )

    await callback.answer()


# =========================================================
# LOYIHALAR — O'ZBEKCHA
# =========================================================

@dp.message(F.text == "📌 Loyihalar")
async def projects_uz(message: Message):

    add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )

    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, name, link
        FROM projects
        ORDER BY id DESC
    """)

    projects = cursor.fetchall()

    conn.close()

    if not projects:
        await message.answer(
            "📌 Hozircha loyihalar qo‘shilmagan."
        )
        return

    for project_id, name, link in projects:

        buttons = [
            [
                InlineKeyboardButton(
                    text="🔗 Havolani ochish",
                    url=link
                )
            ],
            [
                InlineKeyboardButton(
                    text="🗳 Ovoz berish",
                    callback_data=f"vote_{project_id}"
                )
            ]
        ]

        await message.answer(
            f"📌 <b>{name}</b>\n\n"
            "Ovoz berish uchun quyidagi tugmani bosing.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=buttons
            ),
            parse_mode="HTML"
        )


# =========================================================
# LOYIHALAR — RUSCHA
# =========================================================

@dp.message(F.text == "📌 Проекты")
async def projects_ru(message: Message):

    add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )

    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, name, link
        FROM projects
        ORDER BY id DESC
    """)

    projects = cursor.fetchall()

    conn.close()

    if not projects:
        await message.answer(
            "📌 Пока проекты не добавлены."
        )
        return

    for project_id, name, link in projects:

        buttons = [
            [
                InlineKeyboardButton(
                    text="🔗 Открыть ссылку",
                    url=link
                )
            ],
            [
                InlineKeyboardButton(
                    text="🗳 Голосовать",
                    callback_data=f"vote_{project_id}"
                )
            ]
        ]

        await message.answer(
            f"📌 <b>{name}</b>\n\n"
            "Для голосования нажмите кнопку ниже.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=buttons
            ),
            parse_mode="HTML"
        )


# =========================================================
# OVOZ BERISH — BOSHLASH
# =========================================================

@dp.callback_query(F.data.startswith("vote_"))
async def vote_start(callback: CallbackQuery):

    try:
        project_id = int(
            callback.data.replace("vote_", "")
        )
    except ValueError:
        await callback.answer(
            "❌ Xatolik.",
            show_alert=True
        )
        return

    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, name FROM projects WHERE id = ?",
        (project_id,)
    )

    project = cursor.fetchone()

    conn.close()

    if not project:
        await callback.answer(
            "❌ Loyiha topilmadi.",
            show_alert=True
        )
        return

    waiting_for_phone[callback.from_user.id] = project_id

    lang = get_language(callback.from_user.id)

    if lang == "ru":

        await callback.message.answer(
            f"🗳 <b>{project[1]}</b>\n\n"
            "Ovoz berishni davom ettirish uchun "
            "telefon raqamingizni yuboring.\n\n"
            "📱 Quyidagi tugmani bosing:",
            reply_markup=phone_keyboard_ru(),
            parse_mode="HTML"
        )

    else:

        await callback.message.answer(
            f"🗳 <b>{project[1]}</b>\n\n"
            "Ovoz berishni davom ettirish uchun "
            "telefon raqamingizni yuboring.\n\n"
            "📱 Quyidagi tugmani bosing:",
            reply_markup=phone_keyboard_uz(),
            parse_mode="HTML"
        )

    await callback.answer()


# =========================================================
# TELEFON RAQAMINI QABUL QILISH
# =========================================================

@dp.message(F.contact)
async def receive_phone(message: Message):

    user_id = message.from_user.id

    # Faqat ovoz berish jarayonida bo'lsa
    if user_id not in waiting_for_phone:

        await message.answer(
            "ℹ️ Hozir telefon raqami so‘ralmagan."
        )

        return

    project_id = waiting_for_phone[user_id]

    # Contact aynan foydalanuvchining o'zi ekanini tekshirish
    if message.contact.user_id != user_id:

        await message.answer(
            "❌ Iltimos, o‘zingizning Telegram akkauntingizga "
            "tegishli telefon raqamini yuboring."
        )

        return

    phone = message.contact.phone_number

    # Telefonni foydalanuvchi bazasiga saqlaymiz
    save_user_phone(
        user_id,
        phone
    )

    # Loyihani topamiz
    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, name, link
        FROM projects
        WHERE id = ?
    """, (project_id,))

    project = cursor.fetchone()

    conn.close()

    if not project:

        waiting_for_phone.pop(user_id, None)

        await message.answer(
            "❌ Loyiha topilmadi."
        )

        return

    project_name = project[1]
    project_link = project[2]

    # Jarayon tugadi
    waiting_for_phone.pop(user_id, None)

    lang = get_language(user_id)

    # =====================================================
    # O'ZBEKCHA
    # =====================================================

    if lang == "uz":

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔗 Ovoz berish",
                        url=project_link
                    )
                ]
            ]
        )

        await message.answer(
            f"✅ Telefon raqamingiz qabul qilindi.\n\n"
            f"📌 Loyiha: <b>{project_name}</b>\n\n"
            "Endi quyidagi tugmani bosib "
            "ovoz berish sahifasiga o‘ting.",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        await message.answer(
            "Asosiy menyu:",
            reply_markup=uz_keyboard()
        )

    # =====================================================
    # RUSCHA
    # =====================================================

    else:

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔗 Голосовать",
                        url=project_link
                    )
                ]
            ]
        )

        await message.answer(
            f"✅ Ваш номер принят.\n\n"
            f"📌 Проект: <b>{project_name}</b>\n\n"
            "Теперь нажмите кнопку ниже, "
            "чтобы перейти на страницу голосования.",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        await message.answer(
            "Главное меню:",
            reply_markup=ru_keyboard()
        )


# =========================================================
# BEKOR QILISH
# =========================================================

@dp.message(F.text.in_({"❌ Bekor qilish", "❌ Отмена"}))
async def cancel_phone(message: Message):

    user_id = message.from_user.id

    waiting_for_phone.pop(user_id, None)

    lang = get_language(user_id)

    if lang == "ru":

        await message.answer(
            "❌ Голосование отменено.",
            reply_markup=ru_keyboard()
        )

    else:

        await message.answer(
            "❌ Ovoz berish bekor qilindi.",
            reply_markup=uz_keyboard()
        )


# =========================================================
# YANGILIKLAR — O'ZBEKCHA
# =========================================================

@dp.message(F.text == "📰 Yangiliklar")
async def news_uz(message: Message):

    add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )

    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT text FROM news ORDER BY id DESC"
    )

    news = cursor.fetchall()

    conn.close()

    if not news:
        await message.answer(
            "📰 Hozircha yangiliklar yo‘q."
        )
        return

    text = "📰 Yangiliklar:\n\n"

    for item in news:
        text += f"• {item[0]}\n\n"

    await message.answer(text)


# =========================================================
# YANGILIKLAR — RUSCHA
# =========================================================

@dp.message(F.text == "📰 Новости")
async def news_ru(message: Message):

    add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )

    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT text FROM news ORDER BY id DESC"
    )

    news = cursor.fetchall()

    conn.close()

    if not news:
        await message.answer(
            "📰 Новостей пока нет."
        )
        return

    text = "📰 Новости:\n\n"

    for item in news:
        text += f"• {item[0]}\n\n"

    await message.answer(text)


# =========================================================
# YORDAM
# =========================================================

@dp.message(F.text == "❓ Yordam")
async def help_uz(message: Message):

    await message.answer(
        "❓ Yordam\n\n"
        "📌 Loyihalar — mavjud loyihalarni ko‘rish\n"
        "📰 Yangiliklar — yangiliklarni ko‘rish\n\n"
        "Muammo bo‘lsa, administratorga murojaat qiling."
    )


@dp.message(F.text == "❓ Помощь")
async def help_ru(message: Message):

    await message.answer(
        "❓ Помощь\n\n"
        "📌 Проекты — просмотр проектов\n"
        "📰 Новости — просмотр новостей\n\n"
        "При возникновении проблем обратитесь к администратору."
    )


# =========================================================
# ADMIN PANEL
# =========================================================

@dp.message(Command("admin"))
async def admin_command(message: Message):

    if not is_admin(message.from_user.id):

        await message.answer(
            "⛔ Sizda admin huquqi yo‘q."
        )

        return

    user_id = message.from_user.id

    admin_project_waiting.discard(user_id)
    admin_project_name.pop(user_id, None)
    admin_project_link.pop(user_id, None)
    admin_news_waiting.discard(user_id)
    admin_broadcast_waiting.discard(user_id)

    await message.answer(
        "👨‍💼 Admin panel",
        reply_markup=admin_keyboard()
    )


# =========================================================
# STATISTIKA
# =========================================================

@dp.message(F.text == "📊 Statistika")
async def statistics(message: Message):

    if not is_admin(message.from_user.id):
        return

    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT COUNT(*) FROM users"
    )
    total_users = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM users WHERE voted = 1"
    )
    voted_users = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM users WHERE voted = 0"
    )
    not_voted = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM projects"
    )
    total_projects = cursor.fetchone()[0]

    conn.close()

    await message.answer(
        "📊 STATISTIKA\n\n"
        f"👥 Jami foydalanuvchilar: {total_users}\n"
        f"🗳 Ovoz berganlar: {voted_users}\n"
        f"⏳ Ovoz bermaganlar: {not_voted}\n"
        f"📌 Jami loyihalar: {total_projects}"
    )


# =========================================================
# OMMAVIY XABAR BOSHLASH
# =========================================================

@dp.message(F.text == "📢 Ommaviy xabar")
async def broadcast_start(message: Message):

    if not is_admin(message.from_user.id):
        return

    user_id = message.from_user.id

    admin_project_waiting.discard(user_id)
    admin_project_name.pop(user_id, None)
    admin_project_link.pop(user_id, None)
    admin_news_waiting.discard(user_id)

    admin_broadcast_waiting.add(user_id)

    await message.answer(
        "📢 OMMAVIY XABAR\n\n"
        "Barcha bot foydalanuvchilariga yubormoqchi "
        "bo‘lgan xabaringizni yuboring.\n\n"
        "📝 Matn\n"
        "🖼 Rasm\n"
        "🎥 Video\n"
        "📄 Hujjat\n\n"
        "⚠️ Siz yuborgan xabar barcha foydalanuvchilarga tarqatiladi."
    )


# =========================================================
# OMMAVIY XABAR
# =========================================================

async def send_broadcast(message: Message):

    user_id = message.from_user.id

    if not is_admin(user_id):
        return False

    if user_id not in admin_broadcast_waiting:
        return False

    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT user_id FROM users"
    )

    users = cursor.fetchall()

    conn.close()

    if not users:

        admin_broadcast_waiting.discard(user_id)

        await message.answer(
            "❌ Bazada foydalanuvchilar topilmadi.",
            reply_markup=admin_keyboard()
        )

        return True

    await message.answer(
        "⏳ Xabar barcha foydalanuvchilarga yuborilmoqda..."
    )

    success = 0
    blocked = 0
    failed = 0

    # =====================================================
    # RASM
    # =====================================================

    if message.photo:

        photo_id = message.photo[-1].file_id
        caption = message.caption

        for row in users:

            target_user_id = row[0]

            try:

                await bot.send_photo(
                    chat_id=target_user_id,
                    photo=photo_id,
                    caption=caption
                )

                success += 1

                await asyncio.sleep(0.05)

            except TelegramRetryAfter as e:

                await asyncio.sleep(e.retry_after)

                try:

                    await bot.send_photo(
                        chat_id=target_user_id,
                        photo=photo_id,
                        caption=caption
                    )

                    success += 1

                except Exception as e2:

                    logging.error(
                        f"Rasm qayta yuborishda xato "
                        f"{target_user_id}: {e2}"
                    )

                    failed += 1

            except TelegramForbiddenError:

                blocked += 1
                delete_user(target_user_id)

            except TelegramBadRequest as e:

                logging.error(
                    f"TelegramBadRequest "
                    f"{target_user_id}: {e}"
                )

                failed += 1

            except Exception as e:

                logging.error(
                    f"Rasm yuborishda xato "
                    f"{target_user_id}: {e}"
                )

                failed += 1

    # =====================================================
    # BOSHQA XABARLAR
    # =====================================================

    else:

        for row in users:

            target_user_id = row[0]

            try:

                await bot.copy_message(
                    chat_id=target_user_id,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id
                )

                success += 1

                await asyncio.sleep(0.05)

            except TelegramRetryAfter as e:

                await asyncio.sleep(e.retry_after)

                try:

                    await bot.copy_message(
                        chat_id=target_user_id,
                        from_chat_id=message.chat.id,
                        message_id=message.message_id
                    )

                    success += 1

                except Exception as e2:

                    logging.error(
                        f"Xabar qayta yuborishda xato "
                        f"{target_user_id}: {e2}"
                    )

                    failed += 1

            except TelegramForbiddenError:

                blocked += 1
                delete_user(target_user_id)

            except TelegramBadRequest as e:

                logging.error(
                    f"TelegramBadRequest "
                    f"{target_user_id}: {e}"
                )

                failed += 1

            except Exception as e:

                logging.error(
                    f"Xabar yuborishda xato "
                    f"{target_user_id}: {e}"
                )

                failed += 1

    admin_broadcast_waiting.discard(user_id)

    await message.answer(
        "✅ OMMAVIY XABAR YUBORILDI!\n\n"
        f"📨 Muvaffaqiyatli yuborildi: {success}\n"
        f"🚫 Botni bloklaganlar: {blocked}\n"
        f"❌ Xatolik: {failed}\n"
        f"👥 Jami bazadagi foydalanuvchilar: {len(users)}",
        reply_markup=admin_keyboard()
    )

    return True


# =========================================================
# LOYIHA QO'SHISH — 1-BOSQICH
# =========================================================

@dp.message(F.text == "➕ Loyiha qo‘shish")
async def add_project_start(message: Message):

    if not is_admin(message.from_user.id):
        return

    user_id = message.from_user.id

    admin_news_waiting.discard(user_id)
    admin_broadcast_waiting.discard(user_id)

    admin_project_name.pop(user_id, None)
    admin_project_link.pop(user_id, None)

    admin_project_waiting.add(user_id)

    await message.answer(
        "➕ Yangi loyiha qo‘shish\n\n"
        "1️⃣ Loyiha nomini yuboring.\n\n"
        "Masalan:\n"
        "1-maktab loyihasi"
    )


# =========================================================
# LOYIHA SAQLASH
# =========================================================

async def save_project(message: Message):

    user_id = message.from_user.id

    if not is_admin(user_id):
        return False

    if user_id not in admin_project_waiting:
        return False

    if not message.text or not message.text.strip():

        await message.answer(
            "❌ Ma'lumot bo‘sh bo‘lishi mumkin emas."
        )

        return True

    text = message.text.strip()

    # =====================================================
    # 1. LOYIHA NOMI
    # =====================================================

    if user_id not in admin_project_name:

        admin_project_name[user_id] = text

        await message.answer(
            "✅ Loyiha nomi qabul qilindi.\n\n"
            f"📌 Nomi: {text}\n\n"
            "2️⃣ Endi loyiha havolasini yuboring.\n\n"
            "Masalan:\n"
            "https://example.com"
        )

        return True

    # =====================================================
    # 2. HAVOLA
    # =====================================================

    if user_id not in admin_project_link:

        link = text

        if not link.startswith(
            ("http://", "https://")
        ):

            await message.answer(
                "❌ Havola noto‘g‘ri.\n\n"
                "Havola http:// yoki https:// "
                "bilan boshlanishi kerak."
            )

            return True

        admin_project_link[user_id] = link

        await message.answer(
            "✅ Loyiha havolasi qabul qilindi.\n\n"
            f"🔗 Havola: {link}\n\n"
            "3️⃣ Endi loyiha uchun telefon raqamini yuboring.\n\n"
            "Masalan:\n"
            "+998901234567"
        )

        return True

    # =====================================================
    # 3. TELEFON RAQAMI
    # =====================================================

    name = admin_project_name[user_id]
    link = admin_project_link[user_id]
    phone = text

    # Oddiy tekshiruv
    clean_phone = (
        phone.replace(" ", "")
        .replace("-", "")
        .replace("(", "")
        .replace(")", "")
    )

    if not clean_phone.startswith("+"):

        await message.answer(
            "❌ Telefon raqami + bilan boshlanishi kerak.\n\n"
            "Masalan:\n"
            "+998901234567"
        )

        return True

    if not clean_phone[1:].isdigit():

        await message.answer(
            "❌ Telefon raqami noto‘g‘ri.\n\n"
            "Masalan:\n"
            "+998901234567"
        )

        return True

    # =====================================================
    # BAZAGA SAQLASH
    # =====================================================

    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO projects
        (name, link, phone)
        VALUES (?, ?, ?)
        """,
        (
            name,
            link,
            clean_phone
        )
    )

    conn.commit()
    conn.close()

    # Holatlarni tozalash
    admin_project_waiting.discard(user_id)
    admin_project_name.pop(user_id, None)
    admin_project_link.pop(user_id, None)

    await message.answer(
        "✅ LOYIHA MUVAFFAQIYATLI QO‘SHILDI!\n\n"
        f"📌 Nomi: {name}\n"
        f"🔗 Havolasi: {link}\n"
        f"📱 Telefon: {clean_phone}\n\n"
        "Endi foydalanuvchilar loyiha bo‘limidan "
        "🗳 Ovoz berish tugmasi orqali ovoz berish jarayonini boshlashi mumkin.",
        reply_markup=admin_keyboard()
    )

    return True


# =========================================================
# YANGILIK QO'SHISH
# =========================================================

@dp.message(F.text == "📰 Yangilik qo‘shish")
async def add_news_start(message: Message):

    if not is_admin(message.from_user.id):
        return

    user_id = message.from_user.id

    admin_project_waiting.discard(user_id)
    admin_project_name.pop(user_id, None)
    admin_project_link.pop(user_id, None)

    admin_broadcast_waiting.discard(user_id)

    admin_news_waiting.add(user_id)

    await message.answer(
        "📰 Yangilik matnini yuboring.\n\n"
        "Masalan:\n"
        "Bugun yangi loyiha qo‘shildi."
    )


# =========================================================
# YANGILIK SAQLASH
# =========================================================

async def save_news(message: Message):

    user_id = message.from_user.id

    if not is_admin(user_id):
        return False

    if user_id not in admin_news_waiting:
        return False

    if not message.text or not message.text.strip():

        await message.answer(
            "❌ Yangilik matni bo‘sh bo‘lishi mumkin emas."
        )

        return True

    text = message.text.strip()

    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO news (text) VALUES (?)",
        (text,)
    )

    conn.commit()
    conn.close()

    admin_news_waiting.discard(user_id)

    await message.answer(
        "✅ Yangilik muvaffaqiyatli qo‘shildi!",
        reply_markup=admin_keyboard()
    )

    return True


# =========================================================
# ADMIN LOYIHALAR RO'YXATI
# =========================================================

@dp.message(F.text == "📋 Loyihalar")
async def admin_projects(message: Message):

    if not is_admin(message.from_user.id):
        return

    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, name, link, phone
        FROM projects
        ORDER BY id DESC
    """)

    projects = cursor.fetchall()

    conn.close()

    if not projects:

        await message.answer(
            "📋 Hozircha loyihalar yo‘q."
        )

        return

    text = "📋 LOYIHALAR\n\n"

    for project_id, name, link, phone in projects:

        text += (
            f"🆔 ID: {project_id}\n"
            f"📌 {name}\n"
            f"🔗 {link}\n"
            f"📱 {phone or 'Ko‘rsatilmagan'}\n\n"
        )

    await message.answer(text)


# =========================================================
# ADMIN PANELNI YOPISH
# =========================================================

@dp.message(F.text == "❌ Admin panelni yopish")
async def close_admin(message: Message):

    if not is_admin(message.from_user.id):
        return

    user_id = message.from_user.id

    admin_project_waiting.discard(user_id)
    admin_project_name.pop(user_id, None)
    admin_project_link.pop(user_id, None)

    admin_news_waiting.discard(user_id)
    admin_broadcast_waiting.discard(user_id)

    lang = get_language(user_id)

    if lang == "ru":

        await message.answer(
            "✅ Admin panel yopildi.",
            reply_markup=ru_keyboard()
        )

    else:

        await message.answer(
            "✅ Admin panel yopildi.",
            reply_markup=uz_keyboard()
        )


# =========================================================
# BOSHQA XABARLAR
# =========================================================

@dp.message()
async def other_messages(message: Message):

    # Ommaviy xabar
    if await send_broadcast(message):
        return

    # Loyiha qo‘shish
    if await save_project(message):
        return

    # Yangilik qo‘shish
    if await save_news(message):
        return


# =========================================================
# BOTNI ISHGA TUSHIRISH
# =========================================================

async def main():

    init_db()

    print("=================================")
    print("BOT ISHGA TUSHDI")
    print("=================================")

    await dp.start_polling(bot)


# =========================================================
# START
# =========================================================

if __name__ == "__main__":
    asyncio.run(main())