import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from database import Database
from stock_monitor import StockMonitor
from tinkoff.invest import AsyncClient
from tinkoff.invest.exceptions import RequestError
from stock_chart import StockChartGenerator
from datetime import datetime, timedelta

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
    waiting_for_new_stocks = State()
    waiting_for_new_interval = State()
    waiting_for_new_threshold = State()

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

async def check_stock_exists(ticker: str, token: str) -> bool:
    """Проверяет существование акции через Tinkoff Invest API"""
    try:
        async with AsyncClient(token) as client:
            instruments = await client.instruments.find_instrument(query=ticker)
            for instrument in instruments.instruments:
                if instrument.ticker == ticker and instrument.instrument_type == "share":
                    return True
        return False
    except RequestError:
        return False

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    text = (
        "📈 <b>Бот мониторинга акций</b>\n\n"
        "Вы можете открыть меню команд для ознакомления с возможностями бота"
        "Отправьте ваш токен Тинькофф Инвестиций для начала работы."
    )
    await message.answer(text, parse_mode="HTML")
    await state.set_state(Form.waiting_for_token)

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    text = (
        "<b>Доступные команды:</b>\n"
        "/stocks - изменить список акций\n"
        "/interval - изменить интервал проверки котировок акций\n"
        "/threshold - изменить порог изменения котировок акций для уведомлений\n"
        "/history - просмотреть графики с историей котировок отслеживаемых акций\n\n"
        "Вы также можете открыть меню команд (кнопка справа от поля ввода)"
    )
    await message.answer(text, parse_mode="HTML")

@dp.message(Form.waiting_for_token)
async def process_token(message: types.Message, state: FSMContext):
    await state.update_data(token=message.text)
    await message.answer("Теперь введите тикеры акций через запятую (например: SBER,GAZP,VTBR):")
    await state.set_state(Form.waiting_for_stocks)

@dp.message(Form.waiting_for_stocks)
async def process_stocks(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    token = user_data.get("token")
    
    stocks = [s.strip().upper() for s in message.text.split(",")]
    
    # Проверяем существование каждой акции
    invalid_stocks = []
    valid_stocks = []
    
    for ticker in stocks:
        if await check_stock_exists(ticker, token):
            valid_stocks.append(ticker)
        else:
            invalid_stocks.append(ticker)
    
    if invalid_stocks:
        await message.answer(
            f"❌ Следующие тикеры не найдены или не являются акциями: {', '.join(invalid_stocks)}\n"
            f"Пожалуйста, введите только существующие тикеры акций:"
        )
        return
    
    if not valid_stocks:
        await message.answer("❌ Не найдено ни одного валидного тикера. Пожалуйста, попробуйте снова.")
        return
    
    await state.update_data(stocks=valid_stocks)
    await message.answer("Выберите интервал проверки (в минутах):", reply_markup=interval_keyboard)
    await state.set_state(Form.waiting_for_interval)

@dp.message(Form.waiting_for_interval)
async def process_interval(message: types.Message, state: FSMContext):
    if message.text not in ["1", "3", "5", "10"]:
        await message.answer("Пожалуйста, выберите один из предложенных вариантов (1, 3, 5, 10):")
        return
    
    await state.update_data(interval=int(message.text))
    await message.answer("Выберите порог изменения цены (%):", reply_markup=threshold_keyboard)
    await state.set_state(Form.waiting_for_threshold)

@dp.message(Form.waiting_for_threshold)
async def process_threshold(message: types.Message, state: FSMContext):
    if message.text not in ["3", "5", "7", "10"]:
        await message.answer("Пожалуйста, выберите один из предложенных вариантов (3, 5, 7, 10):")
        return
    
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
    await monitor.start_monitoring_for_user(
        chat_id=str(message.chat.id),
        token=user_data["token"],
        stocks=user_data["stocks"],
        interval_minutes=user_data["interval"],
        threshold_percent=float(message.text)
    )
    
    await message.answer(
        "✅ Настройки сохранены! Бот начал мониторинг.\n"
        f"Акции: {', '.join(user_data['stocks'])}\n"
        f"Интервал: {user_data['interval']} мин\n"
        f"Порог: {message.text}%",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.clear()

@dp.message(Command("history"))
async def history_command(message: types.Message):
    chat_id = str(message.chat.id)
    user = db.get_user(chat_id)
    
    if not user:
        await message.answer("Вы не зарегистрированы. Используйте /start для регистрации.")
        return
    
    # Сначала проверим наличие данных
    for ticker in user["stocks"]:
        prices, times = db.get_price_history_since(ticker, datetime.now() - timedelta(days=7))
        await message.answer(f"Данных для {ticker}: {len(prices)} записей")
    
    # Затем генерируем графики
    chart_generator = StockChartGenerator(user["token"], db)
    await message.answer("Генерирую графики...")
    
    try:
        await chart_generator.update_user_charts(chat_id)
        charts = await chart_generator.get_all_user_charts(chat_id)
        
        if not charts:
            await message.answer("Не удалось загрузить графики. Попробуйте позже.")
            return
        
        for ticker, chart in charts.items():
            await message.answer_photo(
                photo=types.BufferedInputFile(chart.getvalue(), filename=f"{ticker}.png"),
                caption=f"График {ticker}"
            )
    except Exception as e:
        print(f"Error in /history: {e}")
        await message.answer("Ошибка при генерации графиков")
    
    except Exception as e:
        print(f"Error in /history: {e}")
        await message.answer("Произошла ошибка при загрузке графиков. Попробуйте позже.")

@dp.message(Command("stocks"))
async def cmd_stocks(message: types.Message, state: FSMContext):
    user = db.get_user(str(message.chat.id))
    if not user:
        await message.answer("Вы не зарегистрированы. Используйте /start для регистрации.")
        return
    
    await message.answer("Введите новые тикеры акций через запятую (например: SBER,GAZP,VTBR):")
    await state.set_state(Form.waiting_for_new_stocks)

@dp.message(Form.waiting_for_new_stocks)
async def process_new_stocks(message: types.Message, state: FSMContext):
    user = db.get_user(str(message.chat.id))
    if not user:
        await message.answer("Вы не зарегистрированы. Используйте /start для регистрации.")
        await state.clear()
        return
    
    stocks = [s.strip().upper() for s in message.text.split(",")]
    
    # Проверяем существование каждой акции
    invalid_stocks = []
    valid_stocks = []
    
    for ticker in stocks:
        if await check_stock_exists(ticker, user["token"]):
            valid_stocks.append(ticker)
        else:
            invalid_stocks.append(ticker)
    
    if invalid_stocks:
        await message.answer(
            f"❌ Следующие тикеры не найдены или не являются акциями: {', '.join(invalid_stocks)}\n"
            f"Пожалуйста, введите только существующие тикеры акций:"
        )
        return
    
    if not valid_stocks:
        await message.answer("❌ Не найдено ни одного валидного тикера. Пожалуйста, попробуйте снова.")
        return
    
    # Обновляем в базе данных
    db.update_stocks(str(message.chat.id), valid_stocks)
    
    # Обновляем в мониторинге
    await monitor.start_monitoring_for_user(
        chat_id=str(message.chat.id),
        token=user["token"],
        stocks=valid_stocks,
        interval_minutes=user["interval_minutes"],
        threshold_percent=user["threshold_percent"]
    )
    
    await message.answer(f"✅ Список акций обновлен: {', '.join(valid_stocks)}")
    await state.clear()

@dp.message(Command("interval"))
async def cmd_interval(message: types.Message, state: FSMContext):
    user = db.get_user(str(message.chat.id))
    if not user:
        await message.answer("Вы не зарегистрированы. Используйте /start для регистрации.")
        return
    
    await message.answer("Выберите новый интервал проверки (в минутах):", reply_markup=interval_keyboard)
    await state.set_state(Form.waiting_for_new_interval)

@dp.message(Form.waiting_for_new_interval)
async def process_new_interval(message: types.Message, state: FSMContext):
    if message.text not in ["1", "3", "5", "10"]:
        await message.answer("Пожалуйста, выберите один из предложенных вариантов (1, 3, 5, 10):")
        return
    
    user = db.get_user(str(message.chat.id))
    if not user:
        await message.answer("Вы не зарегистрированы. Используйте /start для регистрации.")
        await state.clear()
        return
    
    new_interval = int(message.text)
    db.update_interval(str(message.chat.id), new_interval)
    
    # Обновляем в мониторинге
    await monitor.start_monitoring_for_user(
        chat_id=str(message.chat.id),
        token=user["token"],
        stocks=user["stocks"],
        interval_minutes=new_interval,
        threshold_percent=user["threshold_percent"]
    )
    
    await message.answer(f"✅ Интервал проверки обновлен: {new_interval} минут", reply_markup=types.ReplyKeyboardRemove())
    await state.clear()

@dp.message(Command("threshold"))
async def cmd_threshold(message: types.Message, state: FSMContext):
    user = db.get_user(str(message.chat.id))
    if not user:
        await message.answer("Вы не зарегистрированы. Используйте /start для регистрации.")
        return
    
    await message.answer("Выберите новый порог изменения цены (%):", reply_markup=threshold_keyboard)
    await state.set_state(Form.waiting_for_new_threshold)

@dp.message(Form.waiting_for_new_threshold)
async def process_new_threshold(message: types.Message, state: FSMContext):
    if message.text not in ["3", "5", "7", "10"]:
        await message.answer("Пожалуйста, выберите один из предложенных вариантов (3, 5, 7, 10):")
        return
    
    user = db.get_user(str(message.chat.id))
    if not user:
        await message.answer("Вы не зарегистрированы. Используйте /start для регистрации.")
        await state.clear()
        return
    
    new_threshold = float(message.text)
    db.update_threshold(str(message.chat.id), new_threshold)
    
    # Обновляем в мониторинге
    await monitor.start_monitoring_for_user(
        chat_id=str(message.chat.id),
        token=user["token"],
        stocks=user["stocks"],
        interval_minutes=user["interval_minutes"],
        threshold_percent=new_threshold
    )
    
    await message.answer(f"✅ Порог изменения цены обновлен: {new_threshold}%", reply_markup=types.ReplyKeyboardRemove())
    await state.clear()

async def on_startup():
    # Устанавливаем меню команд
    await bot.set_my_commands([
        types.BotCommand(command="start", description="Начать работу с ботом"),
        types.BotCommand(command="stocks", description="Изменить список акций"),
        types.BotCommand(command="interval", description="Изменить интервал проверки"),
        types.BotCommand(command="threshold", description="Изменить порог уведомлений"),
        types.BotCommand(command="history", description="Показать историю цен")
    ])
    
    # Запускаем мониторинг при старте бота
    await monitor.start_monitoring_for_all_users()

async def main():
    # Зарегистрируем обработчик запуска
    dp.startup.register(on_startup)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())