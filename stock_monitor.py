import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import pytz
from tinkoff.invest import AsyncClient, CandleInterval
from tinkoff.invest.utils import now
from database import Database


class StockMonitor:
    def __init__(self):
        self.db = Database()
        self.last_prices: Dict[str, Dict[str, float]] = {}

    async def fetch_stock_price(self, token: str, ticker: str) -> Optional[float]:
        """Получает текущую цену акции через Tinkoff API."""
        try:
            async with AsyncClient(token) as client:
                # Получаем FIGI по тикеру (упрощённый вариант)
                instruments = await client.instruments.shares()
                for instrument in instruments.instruments:
                    if instrument.ticker == ticker:
                        figi = instrument.figi
                        break
                else:
                    print(f"Тикер {ticker} не найден.")
                    return None

                # Получаем последнюю цену
                last_price = (await client.market_data.get_last_prices(figi=[figi])).last_prices[0]
                return float(f"{last_price.price.units}.{last_price.price.nano}")
        except Exception as e:
            print(f"Ошибка при запросе цены {ticker}: {e}")
            return None

    async def check_anomaly(
        self,
        chat_id: str,
        token: str,
        stocks: List[str],
        interval_minutes: int,
        threshold_percent: float
    ) -> None:
        """Запускает периодическую проверку котировок на аномалии."""
        while True:
            for ticker in stocks:
                current_price = await self.fetch_stock_price(token, ticker)
                if current_price is None:
                    continue

                # Проверяем, было ли предыдущее значение
                prev_data = self.last_prices.get(ticker)
                if prev_data:
                    prev_price = prev_data["price"]
                    change_percent = abs((current_price - prev_price) / prev_price) * 100

                    if change_percent >= threshold_percent:
                        print(
                            f"[Чат {chat_id}] Аномалия! {ticker}: "
                            f"{prev_price:.2f} -> {current_price:.2f} "
                            f"(изменение: {change_percent:.2f}%)"
                        )
                        # Здесь можно добавить отправку в Telegram-бота
                        print("Аномалия!")
                        # await bot.send_message(chat_id, f"Аномалия! {ticker}: {prev_price} → {current_price}")

                # Обновляем последнюю цену
                self.last_prices[ticker] = {"price": current_price, "chat_id": chat_id}

            # Ждём указанный интервал
            await asyncio.sleep(interval_minutes * 60)

    async def start_monitoring_for_all_users(self) -> None:
        """Запускает мониторинг для всех пользователей из БД."""
        users = self.db.get_all_users()
        tasks = []
        for user in users:
            task = asyncio.create_task(
                self.check_anomaly(
                    chat_id=user["chat_id"],
                    token=user["token"],
                    stocks=user["stocks"],
                    interval_minutes=user["interval_minutes"],
                    threshold_percent=user["threshold_percent"],
                )
            )
            tasks.append(task)
        await asyncio.gather(*tasks)

