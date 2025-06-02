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
                    stocks TEXT
                )
                """
            )
            conn.commit()

    def add_user(self, chat_id: str, token: str, stocks: List[str]) -> None:
        """Добавляет пользователя в базу."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO users (chat_id, token, stocks)
                VALUES (?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    token = excluded.token,
                    stocks = excluded.stocks
                """,
                (chat_id, token, json.dumps(stocks)),
            )
            conn.commit()

    def get_user(self, chat_id: str) -> Optional[Dict[str, Any]]:
        """Возвращает данные пользователя."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT chat_id, token, stocks FROM users WHERE chat_id = ?",
                (chat_id,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    "chat_id": row[0],
                    "token": row[1],
                    "stocks": json.loads(row[2]) if row[2] else [],
                }
            return None

    def update_stocks(self, chat_id: str, stocks: List[str]) -> None:
        """Обновляет список акций пользователя."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET stocks = ? WHERE chat_id = ?",
                (json.dumps(stocks), chat_id),
            )
            conn.commit()

    def delete_user(self, chat_id: str) -> None:
        """Удаляет пользователя из базы."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE chat_id = ?", (chat_id,))
            conn.commit()

