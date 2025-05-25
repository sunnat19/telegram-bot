import asyncio
import logging
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import API_TOKEN, HOT_TEMP_THRESHOLD
from utils import (
    fetch_current_temp,
    calc_water_intake,
    calc_calorie_needs,
    fetch_food_info,
    calc_workout
)
from data_storage import (
    get_user_profile, set_user_profile,
    log_water, log_food, log_workout, get_progress
)

logging.basicConfig(level=logging.INFO)
bot = Bot(API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class FoodForm(StatesGroup):
    waiting_for_grams = State()

@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "👋 Бот готов! Используйте команды:\n"
        "/profile — установить профиль\n"
        "/water — расчёт воды\n"
        "/calories — расчёт калорий\n"
        "/log_water <мл> — лог воды\n"
        "/log_food <продукт> — лог еды\n"
        "/log_workout <тип> <мин> — лог тренировки\n"
        "/check_progress — прогресс"
    )

@dp.message(Command("profile"))
async def profile_request(message: Message):
    await message.answer(
        "Введите профиль в формате: пол; возраст; вес(кг); рост(см)\n"
        "Пример: male;30;75;180"
    )

# Установка профиля по любому сообщению с 3 ';'
@dp.message(F.text.regexp(r'^[^;]+;\s*\d+;\s*\d+;\s*\d+$'))
async def set_profile(message: Message):
    sex, age, weight, height = [x.strip() for x in message.text.split(";")]
    set_user_profile(str(message.from_user.id), {
        'sex': sex,
        'age': int(age),
        'weight': float(weight),
        'height': float(height)
    })
    await message.answer("✅ Профиль сохранён!")

@dp.message(Command("water"))
async def water_request(message: Message):
    prof = get_user_profile(str(message.from_user.id))
    if not prof:
        return await message.reply('Сначала используйте /profile')
    await message.answer(
        "Введите: город; минут активности\n"
        "Пример: Tashkent;45"
    )

# Обработка ввода города и минут для воды
@dp.message(lambda m: m.text and ";" in m.text and not m.text.startswith("/"))
async def water_calc_handler(message: Message):
    try:
        city, mins = [s.strip() for s in message.text.split(';', 1)]
        temp = await fetch_current_temp(city)
        prof = get_user_profile(str(message.from_user.id))
        goal = calc_water_intake(prof['weight'], int(mins), temp)
        await message.answer(
            f"🌡 Температура: {temp:.1f}°C\n"
            f"💧 Цель воды: {goal} мл"
        )
    except Exception as e:
        await message.reply(f"Ошибка расчёта воды: {e}")

@dp.message(Command("calories"))
async def calories_request(message: Message):
    prof = get_user_profile(str(message.from_user.id))
    if not prof:
        return await message.reply('Сначала используйте /profile')
    await message.answer(
        "Введите уровень активности: low, medium, high"
    )

# Обработка уровня активности для калорий
@dp.message(lambda m: m.text and m.text.lower() in ['low','medium','high'])
async def calories_calc_handler(message: Message):
    prof = get_user_profile(str(message.from_user.id))
    cals = calc_calorie_needs(
        prof['weight'], prof['height'], prof['age'], prof['sex'], message.text.lower()
    )
    await message.answer(f"🔥 Ваша норма калорий: {cals} ккал")

@dp.message(Command("log_water"))
async def log_water_handler(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) != 2 or not args[1].isdigit():
        await message.answer("⚠️ Использование: /log_water <мл>")
        return
    amount = int(args[1])
    uid = str(message.from_user.id)
    log_water(uid, amount)
    prof = get_user_profile(uid)
    goal = calc_water_intake(prof['weight'], 0, HOT_TEMP_THRESHOLD)
    prog = get_progress(uid, goal, 0)
    left = prog['water']['goal'] - prog['water']['drank']
    await message.answer(f"✅ Записано {amount} мл. Осталось: {left} мл")

@dp.message(Command("log_food"))
async def log_food_handler(message: Message, state: FSMContext):
    args = message.text.split(maxsplit=1)
    if len(args) != 2:
        await message.answer("⚠️ Использование: /log_food <продукт>")
        return
    product = args[1]
    name, kcal100 = await fetch_food_info(product)
    if kcal100 == 0:
        await message.answer("❌ Продукт не найден")
        return
    await state.update_data(name=name, kcal100=kcal100)
    await message.answer(f"🍎 {name} — {kcal100} ккал/100г. Сколько грамм?")
    await state.set_state(FoodForm.waiting_for_grams)

@dp.message(FoodForm.waiting_for_grams)
async def food_grams(message: Message, state: FSMContext):
    data = await state.get_data()
    try:
        grams = float(message.text)
        kcal = grams * data['kcal100'] / 100
        log_food(str(message.from_user.id), data['name'], kcal)
        await message.answer(f"✅ Записано: {kcal:.1f} ккал из {grams:.0f} г {data['name']}")
    except ValueError:
        await message.answer("Введите число в граммах!")
    await state.clear()

@dp.message(Command("log_workout"))
async def log_workout_handler(message: Message):
    args = message.text.split(maxsplit=2)
    if len(args) != 3 or not args[2].isdigit():
        await message.answer("⚠️ Использование: /log_workout <тип> <минуты>")
        return
    typ, mins = args[1], int(args[2])
    kcal, water = calc_workout(typ, mins)
    log_workout(str(message.from_user.id), typ, mins, kcal, water)
    await message.answer(f"🏃 {typ} — {mins} мин — {kcal} ккал. Доп. вода: {water} мл")

@dp.message(Command("check_progress"))
async def check_progress_handler(message: Message):
    uid = str(message.from_user.id)
    prof = get_user_profile(uid)
    water_goal = calc_water_intake(prof['weight'], 0, HOT_TEMP_THRESHOLD)
    cal_goal = calc_calorie_needs(prof['weight'], prof['height'], prof['age'], prof['sex'], 'medium')
    prog = get_progress(uid, water_goal, cal_goal)
    await message.answer(
        f"📊 Прогресс за сегодня:\n"
        f"💧 Вода: {prog['water']['drank']} мл из {water_goal} мл\n"
        f"🔥 Калории: съедено {prog['calories']['eaten']} ккал, сожжено {prog['calories']['burned']} ккал\n"
        f"⚖️ Баланс: {prog['calories']['eaten'] - prog['calories']['burned']} ккал"
    )

# Общий обработчик (в конце)
@dp.message()
async def default_handler(message: Message):
    await message.answer("🤔 Неизвестная команда. Используйте /start для списка команд.")

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())