import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from database import Database
from stock_monitor import StockMonitor

class NotificationManager:
    def __init__(self, bot: Bot):
        self.bot = bot
    
    async def send_anomaly_alert(self, chat_id: str, ticker: str, change_percent: float, prev_price: float, current_price: float):
        message = (
            f"⚠️ Обнаружена аномалия!\n"
            f"Акция: {ticker}\n"
            f"Изменение: {change_percent:.2f}%\n"
            f"Предыдущая цена: {prev_price:.2f}\n"
            f"Текущая цена: {current_price:.2f}"
        )
        await self.bot.send_message(chat_id=chat_id, text=message)

class Form(StatesGroup):
    waiting_for_token = State()
    waiting_for_stocks = State()
    waiting_for_interval = State()
    waiting_for_threshold = State()

bot = Bot(token="8133159439:AAEM9ca5jr9CmLFDe8_Zw5pYm3vZcP38T4k")
dp = Dispatcher()
db = Database()
notification_manager = NotificationManager(bot)
monitor = StockMonitor(notification_manager)

# Клавиатуры
interval_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="1"), KeyboardButton(text="3")],
        [KeyboardButton(text="5"), KeyboardButton(text="10")]
    ],
    resize_keyboard=True
)

threshold_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="3"), KeyboardButton(text="5")],
        [KeyboardButton(text="7"), KeyboardButton(text="10")]
    ],
    resize_keyboard=True
)

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await message.answer("Привет! Для начала работы отправьте ваш токен Тинькофф Инвестиций:")
    await state.set_state(Form.waiting_for_token)

@dp.message(Form.waiting_for_token)
async def process_token(message: types.Message, state: FSMContext):
    await state.update_data(token=message.text)
    await message.answer("Теперь введите тикеры акций через запятую (например: SBER,GAZP,VTBR):")
    await state.set_state(Form.waiting_for_stocks)

@dp.message(Form.waiting_for_stocks)
async def process_stocks(message: types.Message, state: FSMContext):
    stocks = [s.strip().upper() for s in message.text.split(",")]
    await state.update_data(stocks=stocks)
    await message.answer("Выберите интервал проверки (в минутах):", reply_markup=interval_keyboard)
    await state.set_state(Form.waiting_for_interval)

@dp.message(Form.waiting_for_interval, F.text.in_(["1", "3", "5", "10"]))
async def process_interval_valid(message: types.Message, state: FSMContext):
    await state.update_data(interval=int(message.text))
    await message.answer("Выберите порог изменения цены (%):", reply_markup=threshold_keyboard)
    await state.set_state(Form.waiting_for_threshold)

@dp.message(Form.waiting_for_interval)
async def process_interval_invalid(message: types.Message):
    await message.answer("Пожалуйста, выберите один из предложенных вариантов (1, 3, 5, 10):")

@dp.message(Form.waiting_for_threshold, F.text.in_(["3", "5", "7", "10"]))
async def process_threshold_valid(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    
    # Сохраняем пользователя в БД
    db.add_user(
        chat_id=str(message.chat.id),
        token=user_data["token"],
        stocks=user_data["stocks"],
        interval_minutes=user_data["interval"],
        threshold_percent=float(message.text)
    )
    
    # Запускаем мониторинг
    asyncio.create_task(
        monitor.check_anomaly(
            chat_id=str(message.chat.id),
            token=user_data["token"],
            stocks=user_data["stocks"],
            interval_minutes=user_data["interval"],
            threshold_percent=float(message.text)
        )
    )
    
    await message.answer(
        "Настройки сохранены! Бот начал мониторинг.\n"
        f"Акции: {', '.join(user_data['stocks'])}\n"
        f"Интервал: {user_data['interval']} мин\n"
        f"Порог: {message.text}%",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.clear()

@dp.message(Form.waiting_for_threshold)
async def process_threshold_invalid(message: types.Message):
    await message.answer("Пожалуйста, выберите один из предложенных вариантов (3, 5, 7, 10):")

async def on_startup(dp):
    # Запускаем мониторинг при старте бота
    task  = asyncio.create_task(monitor.start_monitoring_for_all_users())
    await asyncio.gather(task)

async def main():
    # Зарегистрируем обработчик запуска
    dp.startup.register(on_startup)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

