import asyncio
from typing import List, Optional, Dict, Tuple
from datetime import datetime
from tinkoff.invest import AsyncClient
from database import Database


class StockMonitor:
    def __init__(self, notification_manager):
        self.notification_manager = notification_manager
        # Словарь для хранения последних цен и времени запроса: {ticker: (price, timestamp)}
        self.last_data: Dict[   str, Tuple[float, datetime]] = {}
        self.user_settings = {}  # Храним настройки пользователей
        self.monitor_tasks = {}  # Храним задачи мониторинга по chat_id
        self.db = Database()
        self.lock = asyncio.Lock()  # Для безопасного доступа к общим данным

    async def fetch_stock_price(self, token: str, ticker: str) -> Optional[Tuple[float, datetime]]:
        """Получает текущую цену акции через Tinkoff API и возвращает кортеж (цена, время запроса)."""
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
                price = float(f"{last_price.price.units}.{last_price.price.nano}")
                return (price, datetime.now())
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

                tasks = []
                for ticker in stocks_to_check:
                    task = asyncio.create_task(
                        self.process_single_ticker(chat_id, settings['token'], ticker, settings['threshold'])
                    )
                    tasks.append(task)
                
                await asyncio.gather(*tasks, return_exceptions=True)
                await asyncio.sleep(settings['interval'] * 5)

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Ошибка мониторинга для {chat_id}: {e}")
                await asyncio.sleep(10)

    async def process_single_ticker(self, chat_id: str, token: str, ticker: str, threshold: float):
        """Обрабатывает один тикер с проверкой сохранения данных"""
        result = await self.fetch_stock_price(token, ticker)
        if result is None:
            print(f"Не удалось получить данные для {ticker}")
            return
            
        current_price, timestamp = result

        # Сохраняем в историю с логгированием
        print(f"Сохранение данных: {ticker} - {current_price} - {timestamp}")
        try:
            self.db.save_price_history(ticker, current_price, timestamp)
            print("Данные успешно сохранены")
        except Exception as e:
            print(f"Ошибка сохранения данных: {e}")

        async with self.lock:
            prev_data = self.last_data.get(ticker)
            if prev_data is None:
                self.last_data[ticker] = (current_price, timestamp)
                return

            prev_price, _ = prev_data
            change_percent = abs((current_price - prev_price) / prev_price) * 100

            if change_percent >= threshold:
                await self.notification_manager.send_anomaly_alert(
                    chat_id=chat_id,
                    ticker=ticker,
                    change_percent=change_percent,
                    prev_price=prev_price,
                    current_price=current_price
                )

            self.last_data[ticker] = (current_price, timestamp)

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

    # В файле stock_monitor.py добавим обработку ошибок в start_monitoring_for_all_users
    async def start_monitoring_for_all_users(self):
        """Запускает мониторинг для всех пользователей из БД с обработкой ошибок."""
        try:
            users = self.db.get_all_users()
            if not users:
                print("В базе данных нет пользователей для мониторинга.")
                return

            print(f"Начинаю мониторинг для {len(users)} пользователей...")
            
            tasks = []
            for user in users:
                try:
                    # Проверяем, что все обязательные поля есть
                    if all(key in user for key in ['chat_id', 'token', 'stocks', 'interval_minutes', 'threshold_percent']):
                        task = asyncio.create_task(
                            self.start_monitoring_for_user(
                                chat_id=user["chat_id"],
                                token=user["token"],
                                stocks=user["stocks"],
                                interval_minutes=user["interval_minutes"],
                                threshold_percent=user["threshold_percent"]
                            )
                        )
                        tasks.append(task)
                    else:
                        print(f"Пропускаем пользователя {user.get('chat_id')} - не хватает данных")
                except Exception as e:
                    print(f"Ошибка при запуске мониторинга для пользователя {user.get('chat_id')}: {e}")

            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            print(f"Критическая ошибка при запуске мониторинга для всех пользователей: {e}")

    async def get_last_prices_with_timestamps(self) -> Dict[str, Tuple[float, datetime]]:
        """Возвращает словарь с последними ценами и временем запроса для всех акций."""
        async with self.lock:
            return self.last_data.copy()