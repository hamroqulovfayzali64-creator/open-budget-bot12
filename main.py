import asyncio
import logging
import os
import sqlite3
from contextlib import closing

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
    TelegramNetworkError,
    TelegramServerError,
)

# =========================================================
# SOZLAMALAR
# =========================================================

# Render -> Environment Variables -> BOT_TOKEN
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Admin ID
ADMIN_IDS = [
    7998053914,
]

DB_NAME = "bot.db"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

dp = Dispatcher()

# =========================================================
# HOLATLAR
# =========================================================

# user_id -> project_id
waiting_for_phone = {}

# Loyiha qo'shish
admin_project_waiting = set()
admin_project_name = {}
admin_project_link = {}

# Yangilik qo'shish
admin_news_waiting = set()

# Ommaviy xabar
admin_broadcast_waiting = set()

# =========================================================
# DATABASE
# =========================================================

def db_connect():
    """
    SQLite ulanishi.
    WAL + timeout botni qotib qolishidan himoya qiladi.
    """
    conn = sqlite3.connect(
        DB_NAME,
        timeout=30,
        check_same_thread=False
    )

    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA synchronous=NORMAL")

    return conn


def init_db():

    with closing(db_connect()) as conn:

        cursor = conn.cursor()

        # USERS
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

        # PROJECTS
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                link TEXT NOT NULL,
                phone TEXT
            )
        """)

        # NEWS
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT,
                photo_id TEXT
            )
        """)

        # =====================================================
        # ESKI DATABASE BILAN MOSLASH
        # =====================================================

        cursor.execute("PRAGMA table_info(projects)")
        project_columns = [
            row[1] for row in cursor.fetchall()
        ]

        if "phone" not in project_columns:
            cursor.execute(
                "ALTER TABLE projects ADD COLUMN phone TEXT"
            )

        cursor.execute("PRAGMA table_info(news)")
        news_columns = [
            row[1] for row in cursor.fetchall()
        ]

        if "photo_id" not in news_columns:
            cursor.execute(
                "ALTER TABLE news ADD COLUMN photo_id TEXT"
            )

        if "text" not in news_columns:
            cursor.execute(
                "ALTER TABLE news ADD COLUMN text TEXT"
            )

        conn.commit()

    logging.info("Database tayyor.")


# =========================================================
# USER FUNCTIONS
# =========================================================

def add_user(user_id, username, first_name):

    try:

        with closing(db_connect()) as conn:

            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR IGNORE INTO users
                (user_id, username, first_name)
                VALUES (?, ?, ?)
            """, (
                user_id,
                username,
                first_name
            ))

            # Mavjud foydalanuvchi ma'lumotlarini ham yangilaymiz
            cursor.execute("""
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

    except Exception as e:
        logging.error(f"add_user xatosi: {e}")


def set_language(user_id, language):

    try:

        with closing(db_connect()) as conn:

            conn.execute(
                """
                UPDATE users
                SET language = ?
                WHERE user_id = ?
                """,
                (
                    language,
                    user_id
                )
            )

            conn.commit()

    except Exception as e:
        logging.error(f"set_language xatosi: {e}")


def get_language(user_id):

    try:

        with closing(db_connect()) as conn:

            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT language
                FROM users
                WHERE user_id = ?
                """,
                (user_id,)
            )

            result = cursor.fetchone()

            if result:
                return result[0]

    except Exception as e:
        logging.error(f"get_language xatosi: {e}")

    return "uz"


def save_user_phone(user_id, phone):

    try:

        with closing(db_connect()) as conn:

            conn.execute(
                """
                UPDATE users
                SET phone = ?,
                    voted = 1
                WHERE user_id = ?
                """,
                (
                    phone,
                    user_id
                )
            )

            conn.commit()

    except Exception as e:
        logging.error(f"save_user_phone xatosi: {e}")


def delete_user(user_id):

    try:

        with closing(db_connect()) as conn:

            conn.execute(
                """
                DELETE FROM users
                WHERE user_id = ?
                """,
                (user_id,)
            )

            conn.commit()

    except Exception as e:
        logging.error(
            f"Foydalanuvchini o‘chirish xatosi: {e}"
        )


# =========================================================
# ADMIN
# =========================================================

def is_admin(user_id):
    return user_id in ADMIN_IDS


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
                KeyboardButton(
                    text="📌 Loyihalar"
                )
            ],
            [
                KeyboardButton(
                    text="📰 Yangiliklar"
                ),
                KeyboardButton(
                    text="❓ Yordam"
                )
            ]
        ],
        resize_keyboard=True
    )


def ru_keyboard():

    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="📌 Проекты"
                )
            ],
            [
                KeyboardButton(
                    text="📰 Новости"
                ),
                KeyboardButton(
                    text="❓ Помощь"
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
                    text="➕ Loyiha qo‘shish"
                )
            ],
            [
                KeyboardButton(
                    text="📰 Yangilik qo‘shish"
                )
            ],
            [
                KeyboardButton(
                    text="📢 Ommaviy xabar"
                )
            ],
            [
                KeyboardButton(
                    text="📋 Loyihalar"
                )
            ],
            [
                KeyboardButton(
                    text="❌ Admin panelni yopish"
                )
            ]
        ],
        resize_keyboard=True
    )


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
                KeyboardButton(
                    text="❌ Bekor qilish"
                )
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
                KeyboardButton(
                    text="❌ Отмена"
                )
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )


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
# TIL UZ
# =========================================================

@dp.callback_query(F.data == "lang_uz")
async def language_uz(callback: CallbackQuery):

    set_language(
        callback.from_user.id,
        "uz"
    )

    await callback.message.answer(
        "🇺🇿 O‘zbek tili tanlandi.",
        reply_markup=uz_keyboard()
    )

    await callback.answer()


# =========================================================
# TIL RU
# =========================================================

@dp.callback_query(F.data == "lang_ru")
async def language_ru(callback: CallbackQuery):

    set_language(
        callback.from_user.id,
        "ru"
    )

    await callback.message.answer(
        "🇷🇺 Русский язык выбран.",
        reply_markup=ru_keyboard()
    )

    await callback.answer()


# =========================================================
# LOYIHALAR UZ
# =========================================================

@dp.message(F.text == "📌 Loyihalar")
async def projects_uz(message: Message):

    add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )

    try:

        with closing(db_connect()) as conn:

            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, name, link
                FROM projects
                ORDER BY id DESC
            """)

            projects = cursor.fetchall()

    except Exception as e:

        logging.error(f"Projects UZ xatosi: {e}")

        await message.answer(
            "❌ Loyihalarni olishda xatolik yuz berdi."
        )

        return

    if not projects:

        await message.answer(
            "📌 Hozircha loyihalar qo‘shilmagan."
        )

        return

    for project_id, name, link in projects:

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
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
        )

        await message.answer(
            f"📌 <b>{name}</b>\n\n"
            "Ovoz berish uchun quyidagi tugmani bosing.",
            reply_markup=keyboard,
            parse_mode="HTML"
        )


# =========================================================
# LOYIHALAR RU
# =========================================================

@dp.message(F.text == "📌 Проекты")
async def projects_ru(message: Message):

    add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )

    try:

        with closing(db_connect()) as conn:

            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, name, link
                FROM projects
                ORDER BY id DESC
            """)

            projects = cursor.fetchall()

    except Exception as e:

        logging.error(f"Projects RU xatosi: {e}")

        await message.answer(
            "❌ Ошибка при получении проектов."
        )

        return

    if not projects:

        await message.answer(
            "📌 Пока проекты не добавлены."
        )

        return

    for project_id, name, link in projects:

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
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
        )

        await message.answer(
            f"📌 <b>{name}</b>\n\n"
            "Для голосования нажмите кнопку ниже.",
            reply_markup=keyboard,
            parse_mode="HTML"
        )


# =========================================================
# OVOZ BERISH
# =========================================================

@dp.callback_query(F.data.startswith("vote_"))
async def vote_start(callback: CallbackQuery):

    try:

        project_id = int(
            callback.data.replace(
                "vote_",
                ""
            )
        )

    except ValueError:

        await callback.answer(
            "❌ Xatolik.",
            show_alert=True
        )

        return

    try:

        with closing(db_connect()) as conn:

            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id, name
                FROM projects
                WHERE id = ?
                """,
                (project_id,)
            )

            project = cursor.fetchone()

    except Exception as e:

        logging.error(f"vote_start DB xatosi: {e}")

        await callback.answer(
            "❌ Vaqtinchalik xatolik.",
            show_alert=True
        )

        return

    if not project:

        await callback.answer(
            "❌ Loyiha topilmadi.",
            show_alert=True
        )

        return

    waiting_for_phone[
        callback.from_user.id
    ] = project_id

    lang = get_language(
        callback.from_user.id
    )

    if lang == "ru":

        await callback.message.answer(
            f"🗳 <b>{project[1]}</b>\n\n"
            "Для продолжения голосования "
            "отправьте свой номер телефона.\n\n"
            "📱 Нажмите кнопку ниже:",
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
# TELEFON
# =========================================================

@dp.message(F.contact)
async def receive_phone(message: Message):

    user_id = message.from_user.id

    if user_id not in waiting_for_phone:

        await message.answer(
            "ℹ️ Hozir telefon raqami so‘ralmagan."
        )

        return

    project_id = waiting_for_phone[user_id]

    # Faqat o'z kontaktini qabul qilish
    if message.contact.user_id != user_id:

        await message.answer(
            "❌ Iltimos, o‘zingizning telefon "
            "raqamingizni yuboring."
        )

        return

    phone = message.contact.phone_number

    save_user_phone(
        user_id,
        phone
    )

    try:

        with closing(db_connect()) as conn:

            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id, name, link
                FROM projects
                WHERE id = ?
                """,
                (project_id,)
            )

            project = cursor.fetchone()

    except Exception as e:

        logging.error(f"Telefon DB xatosi: {e}")

        await message.answer(
            "❌ Vaqtinchalik xatolik yuz berdi."
        )

        return

    if not project:

        waiting_for_phone.pop(
            user_id,
            None
        )

        await message.answer(
            "❌ Loyiha topilmadi."
        )

        return

    project_name = project[1]
    project_link = project[2]

    waiting_for_phone.pop(
        user_id,
        None
    )

    lang = get_language(user_id)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=(
                        "🔗 Ovoz berish"
                        if lang == "uz"
                        else "🔗 Голосовать"
                    ),
                    url=project_link
                )
            ]
        ]
    )

    if lang == "ru":

        await message.answer(
            f"✅ Ваш номер принят.\n\n"
            f"📌 Проект: <b>{project_name}</b>\n\n"
            "Теперь нажмите кнопку ниже.",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        await message.answer(
            "Главное меню:",
            reply_markup=ru_keyboard()
        )

    else:

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


# =========================================================
# BEKOR QILISH
# =========================================================

@dp.message(
    F.text.in_({
        "❌ Bekor qilish",
        "❌ Отмена"
    })
)
async def cancel_phone(message: Message):

    user_id = message.from_user.id

    waiting_for_phone.pop(
        user_id,
        None
    )

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
# YANGILIKLAR UZ
# =========================================================

@dp.message(F.text == "📰 Yangiliklar")
async def news_uz(message: Message):

    add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )

    try:

        with closing(db_connect()) as conn:

            cursor = conn.cursor()

            cursor.execute("""
                SELECT text, photo_id
                FROM news
                ORDER BY id DESC
            """)

            news = cursor.fetchall()

    except Exception as e:

        logging.error(f"News UZ xatosi: {e}")

        await message.answer(
            "❌ Yangiliklarni olishda xatolik."
        )

        return

    if not news:

        await message.answer(
            "📰 Hozircha yangiliklar yo‘q."
        )

        return

    for text, photo_id in news:

        try:

            if photo_id:

                await message.answer_photo(
                    photo=photo_id,
                    caption=text if text else None
                )

            elif text:

                await message.answer(
                    f"📰 {text}"
                )

        except Exception as e:

            logging.error(
                f"Yangilik yuborish xatosi: {e}"
            )


# =========================================================
# YANGILIKLAR RU
# =========================================================

@dp.message(F.text == "📰 Новости")
async def news_ru(message: Message):

    add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )

    try:

        with closing(db_connect()) as conn:

            cursor = conn.cursor()

            cursor.execute("""
                SELECT text, photo_id
                FROM news
                ORDER BY id DESC
            """)

            news = cursor.fetchall()

    except Exception as e:

        logging.error(f"News RU xatosi: {e}")

        await message.answer(
            "❌ Ошибка при получении новостей."
        )

        return

    if not news:

        await message.answer(
            "📰 Новостей пока нет."
        )

        return

    for text, photo_id in news:

        try:

            if photo_id:

                await message.answer_photo(
                    photo=photo_id,
                    caption=text if text else None
                )

            elif text:

                await message.answer(
                    f"📰 {text}"
                )

        except Exception as e:

            logging.error(
                f"Yangilik yuborish xatosi: {e}"
            )


# =========================================================
# YORDAM UZ
# =========================================================

@dp.message(F.text == "❓ Yordam")
async def help_uz(message: Message):

    await message.answer(
        "❓ Yordam\n\n"
        "📌 Loyihalar — loyihalarni ko‘rish\n"
        "📰 Yangiliklar — yangiliklarni ko‘rish\n"
        "🗳 Ovoz berish — loyiha uchun ovoz berish\n\n"
        "Muammo bo‘lsa, administratorga murojaat qiling."
    )


# =========================================================
# YORDAM RU
# =========================================================

@dp.message(F.text == "❓ Помощь")
async def help_ru(message: Message):

    await message.answer(
        "❓ Помощь\n\n"
        "📌 Проекты — просмотр проектов\n"
        "📰 Новости — просмотр новостей\n"
        "🗳 Голосовать — голосование за проект\n\n"
        "При возникновении проблем обратитесь к администратору."
    )


# =========================================================
# ADMIN
# =========================================================

@dp.message(Command("admin"))
async def admin_command(message: Message):

    if not is_admin(
        message.from_user.id
    ):

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

    if not is_admin(
        message.from_user.id
    ):
        return

    try:

        with closing(db_connect()) as conn:

            cursor = conn.cursor()

            cursor.execute(
                "SELECT COUNT(*) FROM users"
            )

            total_users = cursor.fetchone()[0]

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM users
                WHERE voted = 1
                """
            )

            voted_users = cursor.fetchone()[0]

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM users
                WHERE voted = 0
                """
            )

            not_voted = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM projects"
            )

            total_projects = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM news"
            )

            total_news = cursor.fetchone()[0]

    except Exception as e:

        logging.error(f"Statistika xatosi: {e}")

        await message.answer(
            "❌ Statistikani olishda xatolik."
        )

        return

    await message.answer(
        "📊 STATISTIKA\n\n"
        f"👥 Jami foydalanuvchilar: {total_users}\n"
        f"🗳 Ovoz berganlar: {voted_users}\n"
        f"⏳ Ovoz bermaganlar: {not_voted}\n"
        f"📌 Jami loyihalar: {total_projects}\n"
        f"📰 Jami yangiliklar: {total_news}"
    )


# =========================================================
# OMMAVIY XABAR BOSHLASH
# =========================================================

@dp.message(F.text == "📢 Ommaviy xabar")
async def broadcast_start(message: Message):

    if not is_admin(
        message.from_user.id
    ):
        return

    user_id = message.from_user.id

    admin_project_waiting.discard(user_id)
    admin_project_name.pop(user_id, None)
    admin_project_link.pop(user_id, None)

    admin_news_waiting.discard(user_id)

    admin_broadcast_waiting.add(user_id)

    await message.answer(
        "📢 OMMAVIY XABAR\n\n"
        "Barcha foydalanuvchilarga yubormoqchi "
        "bo‘lgan xabaringizni yuboring.\n\n"
        "📝 Matn\n"
        "🖼 Rasm\n"
        "🎥 Video\n"
        "📄 Hujjat\n\n"
        "⚠️ Siz yuborgan xabar barcha "
        "foydalanuvchilarga yuboriladi."
    )


# =========================================================
# BITTA FOYDALANUVCHIGA XABAR
# =========================================================

async def send_to_user(message: Message, target_user_id: int):

    max_retry = 3

    for attempt in range(max_retry):

        try:

            if message.photo:

                photo_id = message.photo[-1].file_id

                await bot.send_photo(
                    chat_id=target_user_id,
                    photo=photo_id,
                    caption=message.caption
                )

            else:

                await bot.copy_message(
                    chat_id=target_user_id,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id
                )

            return "success"

        except TelegramRetryAfter as e:

            wait_time = min(
                int(e.retry_after) + 1,
                60
            )

            logging.warning(
                f"Telegram limit. "
                f"{wait_time} sekund kutiladi."
            )

            await asyncio.sleep(wait_time)

        except TelegramForbiddenError:

            return "blocked"

        except TelegramBadRequest as e:

            logging.error(
                f"BadRequest {target_user_id}: {e}"
            )

            return "failed"

        except (
            TelegramNetworkError,
            TelegramServerError
        ) as e:

            logging.warning(
                f"Telegram vaqtinchalik xatosi "
                f"{target_user_id}: {e}"
            )

            await asyncio.sleep(
                2 ** attempt
            )

        except Exception as e:

            logging.error(
                f"Xabar yuborish xatosi "
                f"{target_user_id}: {e}"
            )

            return "failed"

    return "failed"


# =========================================================
# OMMAVIY XABAR
# =========================================================

async def send_broadcast(message: Message):

    user_id = message.from_user.id

    if not is_admin(user_id):
        return False

    if user_id not in admin_broadcast_waiting:
        return False

    try:

        with closing(db_connect()) as conn:

            cursor = conn.cursor()

            cursor.execute(
                "SELECT user_id FROM users"
            )

            users = [
                row[0]
                for row in cursor.fetchall()
            ]

    except Exception as e:

        logging.error(
            f"Broadcast DB xatosi: {e}"
        )

        await message.answer(
            "❌ Foydalanuvchilarni olishda xatolik."
        )

        return True

    if not users:

        admin_broadcast_waiting.discard(
            user_id
        )

        await message.answer(
            "❌ Bazada foydalanuvchilar topilmadi.",
            reply_markup=admin_keyboard()
        )

        return True

    await message.answer(
        "⏳ Xabar yuborish boshlandi.\n\n"
        "Bot boshqa foydalanuvchilarning "
        "xabarlarini ham qabul qila oladi."
    )

    success = 0
    blocked = 0
    failed = 0

    for index, target_user_id in enumerate(users):

        result = await send_to_user(
            message,
            target_user_id
        )

        if result == "success":
            success += 1

        elif result == "blocked":

            blocked += 1

            delete_user(
                target_user_id
            )

        else:
            failed += 1

        # Telegram flood limitiga tushmaslik
        await asyncio.sleep(0.08)

        # Juda katta baza bo'lsa event loopga imkon beramiz
        if index % 20 == 0:
            await asyncio.sleep(0)

    admin_broadcast_waiting.discard(
        user_id
    )

    await message.answer(
        "✅ OMMAVIY XABAR YUBORILDI!\n\n"
        f"📨 Muvaffaqiyatli: {success}\n"
        f"🚫 Bloklaganlar: {blocked}\n"
        f"❌ Xatolik: {failed}\n"
        f"👥 Jami: {len(users)}",
        reply_markup=admin_keyboard()
    )

    return True


# =========================================================
# LOYIHA QO'SHISH
# =========================================================

@dp.message(F.text == "➕ Loyiha qo‘shish")
async def add_project_start(message: Message):

    if not is_admin(
        message.from_user.id
    ):
        return

    user_id = message.from_user.id

    admin_news_waiting.discard(user_id)
    admin_broadcast_waiting.discard(user_id)

    admin_project_name.pop(
        user_id,
        None
    )

    admin_project_link.pop(
        user_id,
        None
    )

    admin_project_waiting.add(
        user_id
    )

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

    if not message.text:

        await message.answer(
            "❌ Ma'lumot yuboring."
        )

        return True

    text = message.text.strip()

    # 1. NOM
    if user_id not in admin_project_name:

        admin_project_name[
            user_id
        ] = text

        await message.answer(
            "✅ Loyiha nomi qabul qilindi.\n\n"
            f"📌 Nomi: {text}\n\n"
            "2️⃣ Loyiha havolasini yuboring.\n\n"
            "Masalan:\n"
            "https://example.com"
        )

        return True

    # 2. HAVOLA
    if user_id not in admin_project_link:

        link = text

        if not link.startswith(
            (
                "http://",
                "https://"
            )
        ):

            await message.answer(
                "❌ Havola noto‘g‘ri.\n\n"
                "Havola http:// yoki https:// "
                "bilan boshlanishi kerak."
            )

            return True

        admin_project_link[
            user_id
        ] = link

        await message.answer(
            "✅ Havola qabul qilindi.\n\n"
            f"🔗 {link}\n\n"
            "3️⃣ Endi loyiha telefon raqamini yuboring.\n\n"
            "Masalan:\n"
            "+998901234567"
        )

        return True

    # 3. TELEFON
    name = admin_project_name[
        user_id
    ]

    link = admin_project_link[
        user_id
    ]

    phone = text

    clean_phone = (
        phone
        .replace(" ", "")
        .replace("-", "")
        .replace("(", "")
        .replace(")", "")
    )

    if not clean_phone.startswith("+"):

        await message.answer(
            "❌ Telefon raqami + bilan "
            "boshlanishi kerak.\n\n"
            "Masalan:\n"
            "+998901234567"
        )

        return True

    if not clean_phone[1:].isdigit():

        await message.answer(
            "❌ Telefon raqami noto‘g‘ri."
        )

        return True

    try:

        with closing(db_connect()) as conn:

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

    except Exception as e:

        logging.error(
            f"Loyiha saqlash xatosi: {e}"
        )

        await message.answer(
            "❌ Loyihani saqlashda xatolik yuz berdi."
        )

        return True

    admin_project_waiting.discard(
        user_id
    )

    admin_project_name.pop(
        user_id,
        None
    )

    admin_project_link.pop(
        user_id,
        None
    )

    await message.answer(
        "✅ LOYIHA MUVAFFAQIYATLI QO‘SHILDI!\n\n"
        f"📌 Nomi: {name}\n"
        f"🔗 Havolasi: {link}\n"
        f"📱 Telefon: {clean_phone}",
        reply_markup=admin_keyboard()
    )

    return True


# =========================================================
# YANGILIK QO'SHISH
# =========================================================

@dp.message(F.text == "📰 Yangilik qo‘shish")
async def add_news_start(message: Message):

    if not is_admin(
        message.from_user.id
    ):
        return

    user_id = message.from_user.id

    admin_project_waiting.discard(
        user_id
    )

    admin_project_name.pop(
        user_id,
        None
    )

    admin_project_link.pop(
        user_id,
        None
    )

    admin_broadcast_waiting.discard(
        user_id
    )

    admin_news_waiting.add(
        user_id
    )

    await message.answer(
        "📰 YANGILIK QO‘SHISH\n\n"
        "Matn yoki rasm yuboring.\n\n"
        "📝 Matn yuborsangiz — matnli yangilik.\n"
        "🖼 Rasm yuborsangiz — rasmli yangilik.\n\n"
        "Rasmga caption yozsangiz, "
        "caption ham saqlanadi."
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

    # RASM
    if message.photo:

        photo_id = message.photo[-1].file_id
        text = message.caption or ""

        try:

            with closing(db_connect()) as conn:

                conn.execute(
                    """
                    INSERT INTO news
                    (text, photo_id)
                    VALUES (?, ?)
                    """,
                    (
                        text,
                        photo_id
                    )
                )

                conn.commit()

        except Exception as e:

            logging.error(
                f"Rasmli yangilik xatosi: {e}"
            )

            await message.answer(
                "❌ Rasmni saqlashda xatolik."
            )

            return True

        admin_news_waiting.discard(
            user_id
        )

        await message.answer(
            "✅ Yangilik muvaffaqiyatli qo‘shildi!\n\n"
            "🖼 Rasm saqlandi.",
            reply_markup=admin_keyboard()
        )

        return True

    # FAQAT MATN
    if message.text and message.text.strip():

        text = message.text.strip()

        try:

            with closing(db_connect()) as conn:

                conn.execute(
                    """
                    INSERT INTO news
                    (text, photo_id)
                    VALUES (?, NULL)
                    """,
                    (text,)
                )

                conn.commit()

        except Exception as e:

            logging.error(
                f"Matnli yangilik xatosi: {e}"
            )

            await message.answer(
                "❌ Yangilikni saqlashda xatolik."
            )

            return True

        admin_news_waiting.discard(
            user_id
        )

        await message.answer(
            "✅ Yangilik muvaffaqiyatli qo‘shildi!",
            reply_markup=admin_keyboard()
        )

        return True

    await message.answer(
        "❌ Yangilik sifatida matn yoki "
        "rasm yuboring."
    )

    return True


# =========================================================
# ADMIN LOYIHALAR
# =========================================================

@dp.message(F.text == "📋 Loyihalar")
async def admin_projects(message: Message):

    if not is_admin(
        message.from_user.id
    ):
        return

    try:

        with closing(db_connect()) as conn:

            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id, name, link, phone
                FROM projects
                ORDER BY id DESC
                """
            )

            projects = cursor.fetchall()

    except Exception as e:

        logging.error(
            f"Admin projects xatosi: {e}"
        )

        await message.answer(
            "❌ Loyihalarni olishda xatolik."
        )

        return

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

    # Telegram xabar limitiga yaqinlashmaslik
    if len(text) > 3900:

        parts = [
            text[i:i + 3900]
            for i in range(0, len(text), 3900)
        ]

        for part in parts:
            await message.answer(part)

    else:

        await message.answer(text)


# =========================================================
# ADMIN PANELNI YOPISH
# =========================================================

@dp.message(F.text == "❌ Admin panelni yopish")
async def close_admin(message: Message):

    if not is_admin(
        message.from_user.id
    ):
        return

    user_id = message.from_user.id

    admin_project_waiting.discard(
        user_id
    )

    admin_project_name.pop(
        user_id,
        None
    )

    admin_project_link.pop(
        user_id,
        None
    )

    admin_news_waiting.discard(
        user_id
    )

    admin_broadcast_waiting.discard(
        user_id
    )

    lang = get_language(user_id)

    if lang == "ru":

        await message.answer(
            "✅ Админ-панель закрыта.",
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

    # Loyiha
    if await save_project(message):
        return

    # Yangilik
    if await save_news(message):
        return


# =========================================================
# GLOBAL ERROR HANDLER
# =========================================================

@dp.errors()
async def global_error_handler(event):

    logging.error(
        f"Global Telegram xatosi: {event.exception}"
    )


# =========================================================
# POLLINGNI BARQAROR ISHLATISH
# =========================================================

async def run_bot():

    if not BOT_TOKEN:

        raise RuntimeError(
            "BOT_TOKEN topilmadi! "
            "Render Environment Variables ichiga "
            "BOT_TOKEN qo‘ying."
        )

    bot = Bot(
        token=BOT_TOKEN
    )

    try:

        await bot.delete_webhook(
            drop_pending_updates=False
        )

        logging.info(
            "Bot pollingni boshlayapti..."
        )

        await dp.start_polling(
            bot,
            polling_timeout=30,
            handle_signals=False
        )

    finally:

        await bot.session.close()


# =========================================================
# MAIN
# =========================================================

async def main():

    init_db()

    logging.info(
        "================================="
    )

    logging.info(
        "BOT ISHGA TUSHDI"
    )

    logging.info(
        "24/7 BARQAROR REJIM"
    )

    logging.info(
        "================================="
    )

    # Bot Telegram yoki internet xatosidan
    # keyin avtomatik qayta ishga tushadi.
    retry_delay = 3

    while True:

        try:

            await run_bot()

            # Normal to'xtash bo'lsa ham qayta ishga tushiramiz
            logging.warning(
                "Polling to‘xtadi. "
                "5 sekunddan keyin qayta ishga tushadi."
            )

            await asyncio.sleep(5)

        except asyncio.CancelledError:

            logging.info(
                "Bot to‘xtatilmoqda..."
            )

            raise

        except Exception as e:

            logging.exception(
                f"BOT ISHDAN CHIQDI: {e}"
            )

            logging.info(
                f"{retry_delay} sekunddan keyin "
                f"qayta ulanadi..."
            )

            await asyncio.sleep(
                retry_delay
            )

            # Ulanish muvaffaqiyatli bo'lmasa
            # kutish vaqtini oshiramiz.
            retry_delay = min(
                retry_delay * 2,
                60
            )

        else:

            retry_delay = 3


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    try:

        asyncio.run(main())

    except KeyboardInterrupt:

        logging.info(
            "Bot qo‘lda to‘xtatildi."
        )