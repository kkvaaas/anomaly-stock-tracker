"""Основной модуль для запуска Telegram бота мониторинга акций."""

import asyncio

from telegram_bot import bot, dp, on_startup


async def main():
    """Основная асинхронная функция для запуска бота."""
    # Зарегистрируем обработчик запуска
    dp.startup.register(on_startup)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
