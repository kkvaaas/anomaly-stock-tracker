from __future__ import annotations
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timedelta, timezone
import matplotlib.pyplot as plt
import io
from tinkoff.invest import AsyncClient, CandleInterval
from database import Database
import pytz


class StockChartGenerator:
    def __init__(self, token: str, db: Database):
        self.token = token
        self.db = db
        self.timezone = pytz.timezone('Europe/Moscow')  # Указываем временную зону для графиков

    async def fetch_candle_data(self, ticker: str, from_date: datetime) -> Tuple[List[float], List[datetime]]:
        """Получает исторические данные для графика начиная с указанной даты"""
        async with AsyncClient(self.token) as client:
            # Получаем FIGI по тикеру
            instruments = await client.instruments.shares()
            figi = next((i.figi for i in instruments.instruments if i.ticker == ticker), None)

            if not figi:
                raise ValueError(f"Тикер {ticker} не найден")

            # Убедимся, что дата в UTC и имеет временную зону
            if not from_date.tzinfo:
                from_date = self.timezone.localize(from_date)
            from_date = from_date.astimezone(timezone.utc)

            # Запрашиваем свечи с интервалом 1 день
            candles = []
            try:
                async for candle in client.get_all_candles(
                        figi=figi,
                        from_=from_date,
                        to=datetime.now(timezone.utc),
                        interval=CandleInterval.CANDLE_INTERVAL_DAY
                ):
                    candles.append(candle)
            except Exception as e:
                print(f"Ошибка при получении исторических данных для {ticker}: {e}")
                return [], []

            # Если нет свечей, попробуем получить часовые данные
            if not candles:
                try:
                    async for candle in client.get_all_candles(
                            figi=figi,
                            from_=from_date,
                            to=datetime.now(timezone.utc),
                            interval=CandleInterval.CANDLE_INTERVAL_HOUR
                    ):
                        candles.append(candle)
                except Exception as e:
                    print(f"Ошибка при получении часовых данных для {ticker}: {e}")
                    return [], []

            # Извлекаем цены закрытия и время
            prices = []
            times = []
            for candle in candles:
                price = candle.close.units + candle.close.nano / 1e9
                time = candle.time.astimezone(self.timezone)  # Конвертируем в нужную временную зону
                
                # Проверяем, что время корректно
                if time.tzinfo is None:
                    time = self.timezone.localize(time)
                    
                prices.append(price)
                times.append(time)

            return prices, times

    def generate_line_chart(self, ticker: str, prices: List[float], times: List[datetime]) -> io.BytesIO:
        """Генерирует линейный график с улучшенным оформлением"""
        if not prices or not times:
            # Создаем пустой график с сообщением об отсутствии данных
            plt.figure(figsize=(12, 6))
            plt.text(0.5, 0.5, 
                    f"Нет данных для {ticker}\nза указанный период", 
                    ha='center', va='center', fontsize=14)
            plt.axis('off')
            
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=120, bbox_inches='tight')
            buf.seek(0)
            plt.close()
            return buf

        plt.figure(figsize=(12, 6))
        
        # Конвертируем datetime в числовой формат для matplotlib
        dates = plt.matplotlib.dates.date2num(times)
        
        # Основной график
        plt.plot_date(dates, prices, 'b-', linewidth=2, marker='o', markersize=4, markerfacecolor='red')
        
        # Настройки оформления
        plt.title(f'История котировок {ticker}\nс {times[0].strftime("%d.%m.%Y")} по {times[-1].strftime("%d.%m.%Y")}', 
                fontsize=14, pad=20)
        plt.xlabel('Дата', fontsize=12)
        plt.ylabel('Цена, руб.', fontsize=12)
        
        # Форматирование осей
        plt.grid(True, linestyle='--', alpha=0.7)
        
        # Используем DateFormatter с правильной временной зоной
        date_formatter = plt.matplotlib.dates.DateFormatter('%d.%m.%Y', tz=self.timezone)
        plt.gca().xaxis.set_major_formatter(date_formatter)
        
        # Автоматический подбор формата дат и их поворот
        plt.gcf().autofmt_xdate()
        
        # Устанавливаем границы осей, чтобы не было пустого места по краям
        plt.xlim([times[0], times[-1]])
        
        # Если данных меньше 30 дней, устанавливаем частоту меток на оси X
        if len(times) <= 30:
            # Для данных до 7 дней - метка каждый день
            if (times[-1] - times[0]).days <= 7:
                plt.gca().xaxis.set_major_locator(plt.matplotlib.dates.DayLocator())
            # Для данных до 30 дней - метка каждые 3 дня
            else:
                plt.gca().xaxis.set_major_locator(plt.matplotlib.dates.DayLocator(interval=3))
        
        # Добавляем информацию о ценах
        min_price = min(prices)
        max_price = max(prices)
        plt.axhline(y=min_price, color='r', linestyle='--', alpha=0.5, label=f'Мин: {min_price:.2f} руб.')
        plt.axhline(y=max_price, color='g', linestyle='--', alpha=0.5, label=f'Макс: {max_price:.2f} руб.')
        plt.legend()
        
        # Сохраняем в буфер
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=120, bbox_inches='tight')
        buf.seek(0)
        plt.close()
        return buf

    async def update_user_charts(self, chat_id: str) -> None:
        """Обновляет графики для всех акций пользователя, начиная с даты регистрации"""
        user = self.db.get_user(chat_id)
        if not user:
            raise ValueError("Пользователь не найден")

        # Преобразуем строку даты регистрации в datetime с учетом временной зоны
        registration_date = datetime.strptime(user["registration_date"], "%Y-%m-%d %H:%M:%S")
        registration_date = self.timezone.localize(registration_date)

        for ticker in user["stocks"]:
            try:
                prices, times = await self.fetch_candle_data(ticker, registration_date)
                
                if not prices:
                    print(f"Нет данных для {ticker} с {registration_date}")
                    continue
                
                chart = self.generate_line_chart(ticker, prices, times)
                self.db.save_chart(chat_id, ticker, chart.getvalue())
            except Exception as e:
                print(f"Ошибка при обновлении графика для {ticker}: {e}")

    async def get_user_chart(self, chat_id: str, ticker: str) -> Optional[io.BytesIO]:
        """Возвращает график для конкретной акции пользователя"""
        user = self.db.get_user(chat_id)
        if not user:
            return None

        try:
            # Получаем дату регистрации
            registration_date = datetime.strptime(user["registration_date"], "%Y-%m-%d %H:%M:%S")
            registration_date = self.timezone.localize(registration_date)
            
            # Добавляем проверку - если регистрация была менее часа назад, берем данные за последние 7 дней
            if (datetime.now(self.timezone) - registration_date) < timedelta(hours=1):
                registration_date = datetime.now(self.timezone) - timedelta(days=7)
            
            prices, times = await self.fetch_candle_data(ticker, registration_date)
            
            # Если данных нет, пробуем получить данные за последнюю неделю
            if not prices:
                prices, times = await self.fetch_candle_data(ticker, datetime.now(self.timezone) - timedelta(days=7))
                
            return self.generate_line_chart(ticker, prices, times)
        except Exception as e:
            print(f"Ошибка при создании графика для {ticker}: {e}")
            return None

    async def get_all_user_charts(self, chat_id: str) -> Dict[str, io.BytesIO]:
        """Возвращает все графики пользователя"""
        user = self.db.get_user(chat_id)
        if not user:
            return {}

        charts = {}
        for ticker in user["stocks"]:
            chart = await self.get_user_chart(chat_id, ticker)
            if chart:
                charts[ticker] = chart
        
        return charts