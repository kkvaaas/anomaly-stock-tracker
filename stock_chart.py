import random

import matplotlib.pyplot as plt
import io
from typing import List, Tuple
from tinkoff.invest import AsyncClient, CandleInterval
from datetime import datetime, timedelta, timezone


class StockChartGenerator:
    def __init__(self, token: str):
        self.token = token

    async def fetch_candle_data(self, ticker: str, days: int = 7) -> Tuple[List[float], List[datetime]]:
        """Получает исторические данные для графика"""
        async with AsyncClient(self.token) as client:
            # Получаем FIGI по тикеру
            instruments = await client.instruments.shares()
            figi = next((i.figi for i in instruments.instruments if i.ticker == ticker), None)

            if not figi:
                raise ValueError(f"Тикер {ticker} не найден")

            # Запрашиваем свечи
            candles = []
            async for candle in client.get_all_candles(
                    figi=figi,
                    from_=datetime.now(timezone.utc) - timedelta(days=days),
                    interval=CandleInterval.CANDLE_INTERVAL_DAY
            ):
                candles.append(candle)

            # Извлекаем цены закрытия и время
            prices = [c.close.units + c.close.nano / 1e9 for c in candles]
            times = [c.time for c in candles]

            return prices, times

    def generate_line_chart(self, ticker: str, prices: List[float], times: List[datetime]) -> io.BytesIO:
        """Генерирует линейный график"""
        plt.figure(figsize=(10, 5))
        plt.plot(times, prices, 'b-', marker='o')
        plt.title(f'Котировки {ticker}')
        plt.xlabel('Дата')
        plt.ylabel('Цена (руб)')
        plt.grid(True)
        plt.xticks(rotation=45)

        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=80, bbox_inches='tight')
        buf.seek(0)
        plt.close()
        return buf

    async def generate_and_send_chart(self, ticker: str, chat_id: str, days: int = 7):
        """Основной метод для генерации и отправки графика"""
        try:
            prices, times = await self.fetch_candle_data(ticker, days)
            chart = self.generate_line_chart(ticker, prices, times)

            # Здесь должна быть логика отправки в Telegram
            # Например, для aiogram:
            # await bot.send_photo(chat_id=chat_id, photo=chart)

            print(f"График для {ticker} сгенерирован (chat_id: {chat_id})")
            return chart
        except Exception as e:
            print(f"Ошибка при генерации графика: {e}")
            return None
