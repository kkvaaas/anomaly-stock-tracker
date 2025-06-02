import asyncio
import json
import os
import threading
from datetime import datetime
import yfinance as yf
import pandas as pd
import tkinter as tk
from tkinter import ttk, messagebox
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONFIG_FILE = "config.json"
DEFAULT_CONFIG = {
    "telegram_token": "YOUR_TELEGRAM_BOT_TOKEN", 
    "stocks": ["AAPL", "MSFT"],
    "exchange": "NASDAQ",
    "anomaly_threshold": 5.0,
    "check_interval": 300,
    "chat_id": None
}


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return DEFAULT_CONFIG


def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)


config = load_config()

bot = Bot(token=config["telegram_token"])
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


def fetch_stock_data(symbol, period="1d", interval="5m"):
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)
        print(f"Данные для {symbol}:\n{df.head()}")
        return df
    except Exception as e:
        logger.error(f"Ошибка при получении данных для {symbol}: {e}")
        return None


def detect_anomalies(df, threshold):
    if df is None or df.empty:
        return []
    df['pct_change'] = df['Close'].pct_change() * 100
    anomalies = df[abs(df['pct_change']) > threshold]
    print(f"Аномалии: {len(anomalies)}")
    return anomalies


async def send_notification(symbol, anomaly):
    if config["chat_id"]:
        message = (f"Обнаружена аномалия в {symbol}!\n"
                   f"Время: {anomaly.name}\n"
                   f"Цена: ${anomaly['Close']:.2f}\n"
                   f"Изменение: {anomaly['pct_change']:.2f}%")
        print(f"Отправка уведомления: {message}")
        try:
            await bot.send_message(config["chat_id"], message)
            logger.info(f"Уведомление отправлено для {symbol}")
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления: {e}")


class StockBotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Бот для отслеживания аномалий акций")
        self.anomalies_log = []

        tk.Label(root, text="Биржа:").grid(row=0, column=0, padx=5, pady=5)
        self.exchange_var = tk.StringVar(value=config["exchange"])
        exchanges = ["NASDAQ", "NYSE", "LSE"]
        tk.OptionMenu(root, self.exchange_var, *exchanges).grid(row=0, column=1, padx=5, pady=5)

        tk.Label(root, text="Акции (через запятую):").grid(row=1, column=0, padx=5, pady=5)
        self.stocks_entry = tk.Entry(root)
        self.stocks_entry.insert(0, ",".join(config["stocks"]))
        self.stocks_entry.grid(row=1, column=1, padx=5, pady=5)

        tk.Label(root, text="Порог аномалий (%):").grid(row=2, column=0, padx=5, pady=5)
        self.threshold_entry = tk.Entry(root)
        self.threshold_entry.insert(0, str(config["anomaly_threshold"]))
        self.threshold_entry.grid(row=2, column=1, padx=5, pady=5)

        tk.Label(root, text="Интервал проверки (сек):").grid(row=3, column=0, padx=5, pady=5)
        self.interval_entry = tk.Entry(root)
        self.interval_entry.insert(0, str(config["check_interval"]))
        self.interval_entry.grid(row=3, column=1, padx=5, pady=5)

        tk.Button(root, text="Сохранить настройки", command=self.save_config).grid(row=4, column=0, columnspan=2,
                                                                                   pady=10)

        tk.Label(root, text="Лог аномалий:").grid(row=5, column=0, padx=5, pady=5)
        self.log_text = tk.Text(root, height=10, width=50)
        self.log_text.grid(row=6, column=0, columnspan=2, padx=5, pady=5)


        tk.Button(root, text="Начать мониторинг", command=self.start_monitoring).grid(row=7, column=0, columnspan=2,
                                                                                      pady=10)

    def save_config(self):
        global config
        try:
            config["exchange"] = self.exchange_var.get()
            config["stocks"] = [s.strip() for s in self.stocks_entry.get().split(",")]
            config["anomaly_threshold"] = float(self.threshold_entry.get())
            config["check_interval"] = int(self.interval_entry.get())
            save_config(config)
            messagebox.showinfo("Успех", "Настройки сохранены!")
        except ValueError as e:
            messagebox.showerror("Ошибка", "Некорректные значения порога или интервала")

    def start_monitoring(self):
        asyncio.run_coroutine_threadsafe(self.monitor_stocks(), asyncio.get_event_loop())

    async def monitor_stocks(self):
        while True:
            for symbol in config["stocks"]:
                df = fetch_stock_data(symbol)
                anomalies = detect_anomalies(df, config["anomaly_threshold"])
                for _, anomaly in anomalies.iterrows():
                    await send_notification(symbol, anomaly)
                    log_entry = f"{datetime.now()}: {symbol} - {anomaly['pct_change']:.2f}% at ${anomaly['Close']:.2f}"
                    self.anomalies_log.append(log_entry)
                    self.log_text.insert(tk.END, log_entry + "\n")
                    self.log_text.see(tk.END)
            await asyncio.sleep(config["check_interval"])


@dp.message(Command("start"))
async def start_command(message: types.Message):
    global config
    print(f"Команда /start получена, chat_id: {message.chat.id}")
    config["chat_id"] = message.chat.id
    save_config(config)
    await message.reply("Бот запущен! Вы будете получать уведомления об аномалиях.")
    print("Сообщение отправлено")


@dp.message(Command("status"))
async def status_command(message: types.Message):
    await message.reply(f"Отслеживаемые акции: {', '.join(config['stocks'])}\n"
                        f"Порог аномалий: {config['anomaly_threshold']}%\n"
                        f"Интервал проверки: {config['check_interval']} секунд")


async def run_polling():
    print("Запуск polling Telegram-бота...")
    await dp.start_polling(bot) 


def start_polling_thread():
    asyncio.run(run_polling())


def main():
    root = tk.Tk()
    app = StockBotGUI(root)
    threading.Thread(target=start_polling_thread, daemon=True).start()
    root.mainloop()


if __name__ == "__main__":
    main()
