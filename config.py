import os
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv("Bot_Token")
OPENWEATHER_API_KEY = os.getenv("Weather_Token")


# Вода за 30 мин активности
ACTIVITY_WATER_PER_30MIN = 500  # мл
# Калории за 30 мин активности (низкий/средний/высокий)
ACTIVITY_CALORIES = {
    'low': 150,
    'medium': 300,
    'high': 400,
}

# Тренировки: калории в минуту
WORKOUT_CALORIES_PER_MIN = {
    'бег': 10,
    'сила': 8,
    'йога': 4,
}
WORKOUT_WATER_PER_30MIN = 200  # мл

# Жаркая погода
HOT_TEMP_THRESHOLD = 25  # °C
HOT_WEATHER_EXTRA = 800  # мл


