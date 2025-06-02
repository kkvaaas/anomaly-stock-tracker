import matplotlib.pyplot as plt
import io
from datetime import datetime, timedelta
import random


def generate_mock_chart() -> io.BytesIO:
    """Генерирует тестовый график с мок-данными"""
    # Генерируем мок-данные: последние 7 дней
    dates = [datetime.now() - timedelta(days=i) for i in range(7, 0, -1)]
    prices = [round(200 + random.random() * 100, 2) for _ in range(7)]

    # Создаем график
    plt.figure(figsize=(10, 5))
    plt.plot(dates, prices, 'b-o', linewidth=2)
    plt.title('Тестовый график (мок-данные)')
    plt.xlabel('Дата')
    plt.ylabel('Цена')
    plt.grid(True)
    plt.xticks(rotation=45)

    # Сохраняем в буфер
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=80, bbox_inches='tight')
    buf.seek(0)
    plt.close()

    return buf


def save_mock_chart_to_file(filename: str = "test_chart.png"):
    """Сохраняет тестовый график в файл для проверки"""
    chart = generate_mock_chart()
    with open(filename, 'wb') as f:
        f.write(chart.getbuffer())
    print(f"График сохранен в {filename}")


# Быстрая проверка
if __name__ == "__main__":
    save_mock_chart_to_file()