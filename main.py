import asyncio
from aiogram import Bot, Dispatcher
from telegram_bot import dp, bot, on_startup

async def main():
    # Зарегистрируем обработчик запуска
    dp.startup.register(on_startup)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())