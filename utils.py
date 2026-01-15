# Функции расчёта нормы воды, калорий, запрос погоды
import aiohttp
import asyncio
import matplotlib.pyplot as plt 
import io
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

async def fetch_food_info(product: str) -> dict:
    url = f"https://world.openfoodfacts.org/cgi/search.pl?search_terms={product}&search_simple=1&action=process&json=1"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()
            items = data.get('products', [])
            if not items:
                return None
            
            first = items[0]
            nutr = first.get('nutriments', {})
            return {
                'name': first.get('product_name_ru') or first.get('product_name') or product,
                'kcal': float(nutr.get('energy-kcal_100g', 0)),
                'proteins': float(nutr.get('proteins_100g', 0)),
                'fats': float(nutr.get('fat_100g', 0)),
                'carbs': float(nutr.get('carbohydrates_100g', 0))
            }

def calc_workout(activity_type: str, minutes: int) -> tuple[int, int]:
    per_min = WORKOUT_CALORIES_PER_MIN.get(activity_type.lower(), 5)
    calories = per_min * minutes
    water    = int((minutes / 30) * WORKOUT_WATER_PER_30MIN)

    return calories, water

def get_recommendations(current_calories: float, goal_calories: float):
    diff = goal_calories - current_calories
    
    if diff > 500:
        return "🥗 Вам стоит перекусить! Рекомендуем: греческий салат или творог."
    elif 0 < diff <= 500:
        return "🍏 Вы почти у цели. Рекомендуем что-то легкое: яблоко или горсть орехов."
    else:
        return "🏃‍♂️ Ого, лимит калорий превышен! Рекомендуем интенсивную тренировку: бег (30 мин) или плавание."


def create_progress_chart(stats: dict) -> io.BytesIO:
   
    # Подготовка данных для осей
    dates_full = list(stats.keys())
    dates_short = [d[5:] for d in dates_full]

    water_data = [stats[d]['water'] for d in dates_full]
    cal_in = [stats[d]['calories_in'] for d in dates_full]
    cal_out = [stats[d]['calories_out'] for d in dates_full]

    # Создаем фигуру с двумя подграфиками (subplots) рядом (1 строка, 2 колонки)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))
    fig.suptitle('Ваш прогресс за неделю', fontsize=16)

    #  График Вода  
    ax1.bar(dates_short, water_data, color='skyblue', alpha=0.8)
    ax1.set_title('💧 Потребление воды')
    ax1.set_ylabel('Миллилитры (мл)')
    ax1.set_xlabel('День')
    ax1.grid(axis='y', linestyle='--', alpha=0.5)

    #  График Калории 
    x_indexes = range(len(dates_short))
    width = 0.4  # Ширина столбца

    ax2.bar([x - width/2 for x in x_indexes], cal_in, width=width, label='Съедено', color='lightcoral', alpha=0.8)
    ax2.bar([x + width/2 for x in x_indexes], cal_out, width=width, label='Сожжено', color='lightgreen', alpha=0.8)

    ax2.set_title('🔥 Калории: Приход vs Расход')
    ax2.set_ylabel('Ккалории (ккал)')
    ax2.set_xlabel('День')
    ax2.set_xticks(x_indexes) 
    ax2.set_xticklabels(dates_short) 
    ax2.legend()
    ax2.grid(axis='y', linestyle='--', alpha=0.5)

    # Автоматически выравниваем элементы, чтобы ничего не наезжало
    plt.tight_layout()

    # Сохраняем график в буфер памяти, а не в файл
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100)
    buf.seek(0) # Перематываем буфер в начало, чтобы его можно было прочитать

    plt.close(fig)

    return buf

