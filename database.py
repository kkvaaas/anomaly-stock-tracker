import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class Database:
    def __init__(self, db_path: str = "stocks.db"):
        self.db_path = db_path  # Добавляем эту строку
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self._create_table()  # Добавляем вызов создания таблиц
        self._create_charts_dir()  # Добавляем вызов создания директории для графиков
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                price REAL NOT NULL,
                timestamp DATETIME NOT NULL
            )
        """
        )
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_ticker ON price_history (ticker)"
        )
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_timestamp ON price_history (timestamp)"
        )
        self.conn.commit()

    def save_price_history(self, ticker: str, price: float, timestamp: datetime):
        """Сохраняет историю цен с проверкой формата времени"""
        if not isinstance(timestamp, datetime):
            timestamp = (
                datetime.fromisoformat(timestamp)
                if isinstance(timestamp, str)
                else datetime.now()
            )

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO price_history (ticker, price, timestamp) VALUES (?, ?, ?)",
                (ticker, price, timestamp.strftime("%Y-%m-%d %H:%M:%S")),
            )
            conn.commit()

    def get_price_history_since(
        self, ticker: str, since: datetime
    ) -> Tuple[List[float], List[datetime]]:
        """Возвращает историю цен с преобразованием строк в datetime"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT price, timestamp FROM price_history "
                "WHERE ticker = ? AND timestamp >= ? "
                "ORDER BY timestamp ASC",
                (ticker, since.strftime("%Y-%m-%d %H:%M:%S")),
            )
            rows = cursor.fetchall()

            prices = []
            times = []
            for price, time_str in rows:
                prices.append(price)
                try:
                    time_obj = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
                    times.append(time_obj)
                except:
                    times.append(datetime.now())

            return prices, times

    def _create_table(self) -> None:
        """Создаёт таблицы, если их нет."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    chat_id TEXT PRIMARY KEY,
                    token TEXT,
                    stocks TEXT,
                    interval_minutes INTEGER,  
                    threshold_percent REAL,
                    registration_date TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    def _create_charts_dir(self) -> None:
        """Создаёт директорию для хранения графиков, если её нет."""
        Path("user_charts").mkdir(exist_ok=True)

    def add_user(
        self,
        chat_id: str,
        token: str,
        stocks: List[str],
        interval_minutes: int = 5,
        threshold_percent: float = 5.0,
    ) -> None:
        """Добавляет пользователя в базу."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO users (chat_id, token, stocks, interval_minutes, threshold_percent, registration_date)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(chat_id) DO UPDATE SET
                    token = excluded.token,
                    stocks = excluded.stocks,
                    interval_minutes = excluded.interval_minutes,
                    threshold_percent = excluded.threshold_percent
                """,
                (
                    chat_id,
                    token,
                    json.dumps(stocks),
                    interval_minutes,
                    threshold_percent,
                ),
            )
            conn.commit()

    def get_user(self, chat_id: str) -> Optional[Dict[str, Any]]:
        """Возвращает данные пользователя."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT chat_id, token, stocks, interval_minutes, threshold_percent, registration_date FROM users WHERE chat_id = ?",
                (chat_id,),
            )
            row = cursor.fetchone()
            if row:
                return {
                    "chat_id": row[0],
                    "token": row[1],
                    "stocks": json.loads(row[2]) if row[2] else [],
                    "interval_minutes": row[3],
                    "threshold_percent": row[4],
                    "registration_date": row[5],
                }
            return None

    def get_all_users(self) -> List[Dict[str, Any]]:
        """Возвращает список всех пользователей."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT chat_id, token, stocks, interval_minutes, threshold_percent, registration_date FROM users"
            )
            users = []
            for row in cursor.fetchall():
                users.append(
                    {
                        "chat_id": row[0],
                        "token": row[1],
                        "stocks": json.loads(row[2]) if row[2] else [],
                        "interval_minutes": row[3],
                        "threshold_percent": row[4],
                        "registration_date": row[5],
                    }
                )
            return users

    def update_token(self, chat_id: str, new_token: str) -> None:
        """Обновляет токен пользователя"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET token = ? WHERE chat_id = ?",
                (new_token, chat_id),
            )
            conn.commit()

    def update_stocks(self, chat_id: str, stocks: List[str]) -> None:
        """Обновляет список акций пользователя."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET stocks = ? WHERE chat_id = ?",
                (json.dumps(stocks), chat_id),
            )
            conn.commit()

    def update_interval(self, chat_id: str, interval_minutes: int) -> None:
        """Обновляет интервал проверки акций."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET interval_minutes = ? WHERE chat_id = ?",
                (interval_minutes, chat_id),
            )
            conn.commit()

    def update_threshold(self, chat_id: str, threshold_percent: float) -> None:
        """Обновляет порог аномалии."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET threshold_percent = ? WHERE chat_id = ?",
                (threshold_percent, chat_id),
            )
            conn.commit()

    def delete_user(self, chat_id: str) -> None:
        """Удаляет пользователя из базы."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE chat_id = ?", (chat_id,))
            conn.commit()

        # Удаляем все графики пользователя
        user_chart_dir = Path(f"user_charts/{chat_id}")
        if user_chart_dir.exists():
            for file in user_chart_dir.glob("*.png"):
                file.unlink()
            user_chart_dir.rmdir()

    def save_chart(self, chat_id: str, ticker: str, chart_data: bytes) -> None:
        """Сохраняет график для пользователя."""
        user_chart_dir = Path(f"user_charts/{chat_id}")
        user_chart_dir.mkdir(exist_ok=True)

        with open(user_chart_dir / f"{ticker}.png", "wb") as f:
            f.write(chart_data)

    def get_chart(self, chat_id: str, ticker: str) -> Optional[bytes]:
        """Возвращает сохранённый график для пользователя."""
        chart_path = Path(f"user_charts/{chat_id}/{ticker}.png")
        if chart_path.exists():
            with open(chart_path, "rb") as f:
                return f.read()
        return None

    def get_all_user_charts(self, chat_id: str) -> Dict[str, bytes]:
        """Возвращает все графики пользователя."""
        charts = {}
        user_chart_dir = Path(f"user_charts/{chat_id}")

        if user_chart_dir.exists():
            for file in user_chart_dir.glob("*.png"):
                with open(file, "rb") as f:
                    charts[file.stem] = f.read()

        return charts
