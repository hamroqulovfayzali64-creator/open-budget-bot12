import asyncio
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram import types

TOKEN = "BOT_TOKENINGIZNI_BU_YERGA_QOYASIZ"

bot = Bot(token=TOKEN)
dp = Dispatcher()


@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Bot ishlayapti ✅")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())