import asyncio
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram import types

TOKEN = "8615736731:AAFImAWTDRhBJAyOhXbY6D0wwysIa0Boz1c"

bot = Bot(token=TOKEN)
dp = Dispatcher()


@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Bot ishlayapti ✅")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())