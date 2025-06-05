import asyncio
from typing import Dict, List, Optional
from tinkoff.invest import AsyncClient
from database import Database


class StockMonitor:
    def __init__(self, notification_manager):
        self.notification_manager = notification_manager
        self.last_prices = {}  # Общий словарь для всех пользователей
        self.user_settings = {}  # Храним настройки пользователей
        self.monitor_tasks = {}  # Храним задачи мониторинга по chat_id
        self.db = Database()
        self.lock = asyncio.Lock()  # Для безопасного доступа к общим данным

    async def fetch_stock_price(self, token: str, ticker: str) -> Optional[float]:
        """Получает текущую цену акции через Tinkoff API."""
        try:
            async with AsyncClient(token) as client:
                instruments = await client.instruments.shares()
                for instrument in instruments.instruments:
                    if instrument.ticker == ticker:
                        figi = instrument.figi
                        break
                else:
                    print(f"Тикер {ticker} не найден.")
                    return None

                last_price = (await client.market_data.get_last_prices(figi=[figi])).last_prices[0]
                return float(f"{last_price.price.units}.{last_price.price.nano}")
        except Exception as e:
            print(f"Ошибка при запросе цены {ticker}: {e}")
            return None

    async def check_anomaly_for_user(self, chat_id: str):
        """Основной метод мониторинга для конкретного пользователя."""
        while True:
            try:
                settings = self.user_settings.get(chat_id)
                if not settings:
                    break

                async with self.lock:
                    stocks_to_check = settings['stocks'].copy()

                # Создаем список задач для параллельной проверки всех акций
                tasks = []
                for ticker in stocks_to_check:
                    task = asyncio.create_task(
                        self.process_single_ticker(chat_id, settings['token'], ticker, settings['threshold'])
                    )
                    tasks.append(task)
                
                # Запускаем все задачи параллельно
                await asyncio.gather(*tasks, return_exceptions=True)

                await asyncio.sleep(settings['interval'] * 60)

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Ошибка мониторинга для {chat_id}: {e}")
                await asyncio.sleep(10)

    async def process_single_ticker(self, chat_id: str, token: str, ticker: str, threshold: float):
        """Обрабатывает один тикер независимо от других"""
        current_price = await self.fetch_stock_price(token, ticker)
        print(ticker, current_price)
        if current_price is None:
            return  # Просто пропускаем этот тикер

        async with self.lock:
            prev_price = self.last_prices.get(ticker)
            if prev_price is None:
                self.last_prices[ticker] = current_price
                return

            change_percent = abs((current_price - prev_price) / prev_price) * 100

            if change_percent >= threshold:
                await self.notification_manager.send_anomaly_alert(
                    chat_id=chat_id,
                    ticker=ticker,
                    change_percent=change_percent,
                    prev_price=prev_price,
                    current_price=current_price
                )

            self.last_prices[ticker] = current_price

    async def start_monitoring_for_user(self, chat_id: str, token: str, stocks: List[str], 
                                      interval_minutes: int, threshold_percent: float):
        """Запускает мониторинг для конкретного пользователя."""
        async with self.lock:
            self.user_settings[chat_id] = {
                'token': token,
                'stocks': stocks,
                'interval': interval_minutes,
                'threshold': threshold_percent
            }

        if chat_id in self.monitor_tasks:
            self.monitor_tasks[chat_id].cancel()
            try:
                await self.monitor_tasks[chat_id]
            except asyncio.CancelledError:
                pass

        self.monitor_tasks[chat_id] = asyncio.create_task(
            self.check_anomaly_for_user(chat_id)
        )

    async def start_monitoring_for_all_users(self):
        """Запускает мониторинг для всех пользователей из БД."""
        users = self.db.get_all_users()
        for user in users:
            await self.start_monitoring_for_user(
                chat_id=user["chat_id"],
                token=user["token"],
                stocks=user["stocks"],
                interval_minutes=user["interval_minutes"],
                threshold_percent=user["threshold_percent"]
            )