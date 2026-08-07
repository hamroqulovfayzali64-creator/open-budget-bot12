from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton
)

language_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🇺🇿 O'zbek"),
            KeyboardButton(text="🇷🇺 Русский")
        ]
    ],
    resize_keyboard=True
)

user_keyboard_uz = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📌 Loyihalar")]
    ],
    resize_keyboard=True
)

user_keyboard_ru = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📌 Проекты")]
    ],
    resize_keyboard=True
)

admin_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="➕ Loyiha qo'shish"),
            KeyboardButton(text="✏️ Loyiha tahrirlash")
        ],
        [
            KeyboardButton(text="🗑 Loyiha o'chirish"),
            KeyboardButton(text="📊 Statistika")
        ],
        [
            KeyboardButton(text="📢 Xabar yuborish")
        ]
    ],
    resize_keyboard=True
)