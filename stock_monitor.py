import asyncio
from typing import Dict, List, Optional
from tinkoff.invest import AsyncClient
from database import Database


class StockMonitor:
    def __init__(self, notification_manager):
        self.notification_manager = notification_manager
        self.last_prices = {}

    async def check_anomaly(self, chat_id: str, token: str, stocks: List[str], interval_minutes: int, threshold_percent: float):
        while True:
            for ticker in stocks:
                current_price = await self.fetch_stock_price(token, ticker)
                print(current_price)
                print("цена для акции", ticker, "=", current_price)
                if current_price is None:
                    continue

                prev_data = self.last_prices.get(ticker)
                if prev_data:
                    prev_price = prev_data["price"]
                    change_percent = abs((current_price - prev_price) / prev_price) * 100

                    if change_percent >= threshold_percent:
                        await self.notification_manager.send_anomaly_alert(
                            chat_id=chat_id,
                            ticker=ticker,
                            change_percent=change_percent,
                            prev_price=prev_price,
                            current_price=current_price
                        )

                self.last_prices[ticker] = {"price": current_price, "chat_id": chat_id}

            await asyncio.sleep(interval_minutes * 60)


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
            print("started monitoring for user with id:", user["chat_id"])
            tasks.append(task)
        await asyncio.gather(*tasks)

