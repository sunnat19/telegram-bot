# Функции расчёта нормы воды, калорий, запрос погоды
import aiohttp
import asyncio
from config import (
    OPENWEATHER_API_KEY, HOT_TEMP_THRESHOLD, HOT_WEATHER_EXTRA,
    ACTIVITY_WATER_PER_30MIN, ACTIVITY_CALORIES,
    WORKOUT_CALORIES_PER_MIN, WORKOUT_WATER_PER_30MIN
)

async def fetch_current_temp(city: str) -> float:
    url = (
        'http://api.openweathermap.org/data/2.5/weather'
        f'?q={city}&appid={OPENWEATHER_API_KEY}&units=metric'
    )
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()
            return data['main']['temp']

def calc_water_intake(weight: float, activity_min: int, temp: float) -> int:
    base     = weight * 30
    activity = (activity_min / 30) * ACTIVITY_WATER_PER_30MIN
    extra    = HOT_WEATHER_EXTRA if temp > HOT_TEMP_THRESHOLD else 0
    return int(base + activity + extra)

def calc_calorie_needs(weight: float, height: float, age: int,
                       sex: str, activity_level: str) -> int:
    if sex.lower() == 'male':
        bmr = 10*weight + 6.25*height - 5*age + 5
    else:
        bmr = 10*weight + 6.25*height - 5*age - 161
    activity = ACTIVITY_CALORIES.get(activity_level, 0)
    return int(bmr + activity)

async def fetch_food_info(product: str) -> tuple[str, float]:
    url = (
        'https://world.openfoodfacts.org/cgi/search.pl'
        f'?search_terms={product}&search_simple=1&action=process&json=1'
    )
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()
            items = data.get('products', [])
            if not items:
                return product, 0.0
            first = items[0]
            name  = first.get('product_name_ru') or first.get('product_name') or product
            nutr  = first.get('nutriments', {})
            kcal  = nutr.get('energy-kcal_100g', 0.0)
            return name, float(kcal)

def calc_workout(activity_type: str, minutes: int) -> tuple[int, int]:
    per_min = WORKOUT_CALORIES_PER_MIN.get(activity_type.lower(), 5)
    calories = per_min * minutes
    water    = int((minutes / 30) * WORKOUT_WATER_PER_30MIN)
    return calories, water