import sqlite3
from typing import List, Optional, Dict, Any
import json

class Database:
    def __init__(self, db_name: str = "stocks_bot.db"):
        self.db_name = db_name
        self._create_table()

    def _create_table(self) -> None:
        """Создаёт таблицу, если её нет."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    chat_id TEXT PRIMARY KEY,
                    token TEXT,
                    stocks TEXT,
                    interval_minutes INTEGER,  
                    threshold_percent REAL
                )
                """
            )
            conn.commit()

    def add_user(
        self,
        chat_id: str,
        token: str,
        stocks: List[str],
        interval_minutes: int = 5,
        threshold_percent: float = 5.0
    ) -> None:
        """Добавляет пользователя в базу."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO users (chat_id, token, stocks, interval_minutes, threshold_percent)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    token = excluded.token,
                    stocks = excluded.stocks,
                    interval_minutes = excluded.interval_minutes,
                    threshold_percent = excluded.threshold_percent
                """,
                (chat_id, token, json.dumps(stocks), interval_minutes, threshold_percent),
            )
            conn.commit()

    def get_user(self, chat_id: str) -> Optional[Dict[str, Any]]:
        """Возвращает данные пользователя."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT chat_id, token, stocks, interval_minutes, threshold_percent FROM users WHERE chat_id = ?",
                (chat_id,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    "chat_id": row[0],
                    "token": row[1],
                    "stocks": json.loads(row[2]) if row[2] else [],
                    "interval_minutes": row[3],
                    "threshold_percent": row[4],
                }
            return None

    def get_all_users(self) -> List[Dict[str, Any]]:
        """Возвращает список всех пользователей."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT chat_id, token, stocks, interval_minutes, threshold_percent FROM users")
            users = []
            for row in cursor.fetchall():
                users.append({
                    "chat_id": row[0],
                    "token": row[1],
                    "stocks": json.loads(row[2]) if row[2] else [],
                    "interval_minutes": row[3],
                    "threshold_percent": row[4],
                })
            return users

    def update_stocks(self, chat_id: str, stocks: List[str]) -> None:
        """Обновляет список акций пользователя."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET stocks = ? WHERE chat_id = ?",
                (json.dumps(stocks), chat_id),
            )
            conn.commit()

    def update_interval(self, chat_id: str, interval_minutes: int) -> None:
        """Обновляет интервал проверки акций."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET interval_minutes = ? WHERE chat_id = ?",
                (interval_minutes, chat_id),
            )
            conn.commit()

    def update_threshold(self, chat_id: str, threshold_percent: float) -> None:
        """Обновляет порог аномалии."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET threshold_percent = ? WHERE chat_id = ?",
                (threshold_percent, chat_id),
            )
            conn.commit()

    def delete_user(self, chat_id: str) -> None:
        """Удаляет пользователя из базы."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE chat_id = ?", (chat_id,))
            conn.commit()

