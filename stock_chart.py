from __future__ import annotations

import io
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import pytz

from database import Database


class StockChartGenerator:
    def __init__(self, token: str, db: Database):
        self.token = token
        self.db = db
        self.timezone = pytz.timezone("Europe/Moscow")

    async def fetch_candle_data(
        self, ticker: str, from_date: datetime
    ) -> Tuple[List[float], List[datetime]]:
        """Получает исторические данные из БД начиная с указанной даты"""
        return self.db.get_price_history_since(ticker, from_date)

    def generate_line_chart(
        self, ticker: str, prices: List[float], times: List[datetime]
    ) -> io.BytesIO:
        """Генерирует точный график с корректными точками начала и конца"""

        buf = io.BytesIO()
        # Проверка данных
        if not prices or not times or len(prices) != len(times):
            plt.figure(figsize=(8, 4))
            plt.text(0.5, 0.5, f"Нет данных для {ticker}", ha="center", va="center")
            plt.axis("off")
            plt.savefig(buf, format="png", bbox_inches="tight")
            plt.close()
            buf.seek(0)
            return buf

        plt.figure(figsize=(12, 6))

        try:
            # Преобразуем даты в числовой формат для matplotlib
            dates = [plt.matplotlib.dates.date2num(t) for t in times]

            # Основной график
            plt.plot(dates, prices, "b-", linewidth=2, label="Цена")

            # Точка начала (зеленая)
            start_price = prices[0]
            plt.plot(
                dates[0],
                start_price,
                "go",
                markersize=8,
                label=f"Начало: {start_price:.2f}",
            )

            # Точка конца (красная)
            end_price = prices[-1]
            plt.plot(
                dates[-1],
                end_price,
                "ro",
                markersize=8,
                label=f"Текущая: {end_price:.2f}",
            )

            # Настройка осей
            ax = plt.gca()
            ax.xaxis.set_major_formatter(
                plt.matplotlib.dates.DateFormatter("%d.%m.%Y\n%H:%M", tz=self.timezone)
            )
            ax.yaxis.set_major_formatter(plt.FormatStrFormatter("%.2f"))

            # Автоматическое масштабирование осей с небольшим запасом
            plt.axis(
                [
                    dates[0] - 0.1 * (dates[-1] - dates[0]),
                    dates[-1] + 0.1 * (dates[-1] - dates[0]),
                    min(prices) * 0.99,
                    max(prices) * 1.01,
                ]
            )

            # Сетка и оформление
            plt.grid(True, linestyle="--", alpha=0.7)
            plt.title(
                f'Котировки {ticker}\n{times[0].strftime("%d.%m.%Y")} - {times[-1].strftime("%d.%m.%Y")}'
            )
            plt.xlabel("Дата и время")
            plt.ylabel("Цена, руб.")
            plt.legend(loc="upper left")

            # Оптимизация расположения элементов
            plt.tight_layout()

            # Сохранение
            plt.savefig(buf, format="png", dpi=120, bbox_inches="tight")
            buf.seek(0)

        except Exception as e:
            print(f"Ошибка генерации графика {ticker}: {e}")
            plt.close()
            buf = self._generate_error_chart(ticker)

        finally:
            plt.close()

        return buf

    def _generate_error_chart(self, ticker: str) -> io.BytesIO:
        """Генерирует график с сообщением об ошибке"""
        buf = io.BytesIO()
        plt.figure(figsize=(8, 4))
        plt.text(0.5, 0.5, f"Ошибка построения {ticker}", ha="center", va="center")
        plt.axis("off")
        plt.savefig(buf, format="png", bbox_inches="tight")
        plt.close()
        buf.seek(0)
        return buf

    async def update_user_charts(self, chat_id: str) -> None:
        """Обновляет графики для всех акций пользователя, начиная с даты регистрации"""
        user = self.db.get_user(chat_id)
        if not user:
            raise ValueError("Пользователь не найден")

        registration_date = datetime.strptime(
            user["registration_date"], "%Y-%m-%d %H:%M:%S"
        )
        registration_date = self.timezone.localize(registration_date)

        for ticker in user["stocks"]:
            try:
                prices, times = await self.fetch_candle_data(ticker, registration_date)

                if not prices:
                    print(
                        f"Нет данных для {ticker} с {registration_date.strftime('%d.%m.%Y')}"
                    )
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

        registration_date = datetime.strptime(
            user["registration_date"], "%Y-%m-%d %H:%M:%S"
        )
        registration_date = self.timezone.localize(registration_date)

        prices, times = self.db.get_price_history_since(ticker, registration_date)

        if not prices:
            return None

        return self.generate_line_chart(ticker, prices, times)

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
