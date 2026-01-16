import asyncio
import logging
import os
import re
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, BufferedInputFile
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# Импорт настроек и вспомогательных функций
from config import API_TOKEN, HOT_TEMP_THRESHOLD
from utils import (
    fetch_current_temp,
    calc_water_intake,
    calc_calorie_needs,
    fetch_food_info,
    calc_workout,
    create_progress_chart,
    get_smart_recommendation
)
from data_storage import (
    get_user_profile, set_user_profile,
    log_water, log_food, log_workout, get_progress,
    get_weekly_stats
)
# Инициализация бота и логирования
logging.basicConfig(level=logging.INFO)
bot = Bot(API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class FoodForm(StatesGroup):
    waiting_for_grams = State()
    
# Настройка профиля
@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "Используйте команды:\n"
        "/profile — установить профиль\n"
        "/water — расчёт воды\n"
        "/calories — расчёт калорий\n"
        "/log_water <мл> — лог воды\n"
        "/log_food <продукт> — лог еды\n"
        "/log_workout <тип> <мин> — лог тренировки\n"
        "/check_progress — прогресс\n"
        "/graphs — графики за неделю 📈"
        "/recommend — персональный совет"
    )

@dp.message(Command("profile"))
async def profile_request(message: Message):
    await message.answer(
        "Введите профиль в формате: пол; возраст; вес(кг); рост(см)\n"
        "Пример: male;30;75;180"
    )

# Установка профиля по любому сообщению
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
    
# Расчеты норм
@dp.message(Command("water"))
async def water_request(message: Message):
    prof = get_user_profile(str(message.from_user.id))
    if not prof:
        return await message.reply('Сначала используйте /profile')
    await message.answer(
        "Введите: город; минут активности\n"
        "Пример: Tashkent;45"
    )

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

 # Логирования (вода, еда и тринировки)   
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
        return await message.answer("⚠️ Использование: /log_food <продукт>")
    
    product = args[1]
    food_data = await fetch_food_info(product) # Теперь получаем словарь
    
    if not food_data or food_data['kcal'] == 0:
        return await message.answer("❌ Продукт не найден в базе данных.")
    
    await state.update_data(food_data=food_data)
    await message.answer(
        f"🍎 **{food_data['name']}**\n"
        f"Калорийность: {food_data['kcal']} ккал/100г\n"
        f"БЖУ: {food_data['proteins']}/{food_data['fats']}/{food_data['carbs']}\n\n"
        f"Сколько грамм вы съели?"
    )
    await state.set_state(FoodForm.waiting_for_grams)


@dp.message(FoodForm.waiting_for_grams)
async def food_grams(message: Message, state: FSMContext):
    data = await state.get_data()
    try:
        grams = float(message.text)
        food = data['food_data']
        
        # Расчет с учетом веса
        ratio = grams / 100
        res_kcal = food['kcal'] * ratio
        res_p = food['proteins'] * ratio
        res_f = food['fats'] * ratio
        res_c = food['carbs'] * ratio
        
        log_food(str(message.from_user.id), food['name'], res_kcal)
        
        await message.answer(
            f"✅ Записано: {res_kcal:.1f} ккал\n"
            f"📊 Итого БЖУ за прием: Б: {res_p:.1f}г, Ж: {res_f:.1f}г, У: {res_c:.1f}г"
        )
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

# Аналитика и рекомендации  
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


@dp.message(Command("graphs"))    
async def graphs_handler(message: Message):
    uid = str(message.from_user.id)
    prof = get_user_profile(uid)

    processing_msg = await message.answer("Рисую графики, подождите немного...")

    stats = get_weekly_stats(uid)
    total_activity = sum(d['water'] + d['calories_in'] + d['calories_out'] for d in stats.values())
    if total_activity == 0:
        await processing_msg.edit_text("📉 За последнюю неделю нет данных для построения графиков.")
        return
    photo_buffer = create_progress_chart(stats)
    photo = BufferedInputFile(photo_buffer.read(), filename="weekly_progress.png")

    await message.answer_photo(photo=photo, caption="📊 Ваша статистика за последние 7 дней.")
    await processing_msg.delete()


@dp.message(Command("recommend"))
async def recommend_handler(message: Message):
    uid = str(message.from_user.id)
    prof = get_user_profile(uid)
    if not prof:
        return await message.answer("Сначала настройте /profile")
    
    cal_goal = calc_calorie_needs(prof['weight'], prof['height'], prof['age'], prof['sex'], 'medium')
    prog = get_progress(uid, 0, cal_goal)
    
    advice = get_smart_recommendation(
        prog['calories']['eaten'], 
        prog['calories']['burned'], 
        cal_goal
    )
    await message.answer(f"💡 **Персональный совет:**\n\n{advice}")


# Общий обработчик 
@dp.message()
async def default_handler(message: Message):
    await message.answer("🤔 Неизвестная команда. Используйте /start для списка команд.")
    
# Запуск сервера и бота   
async def handle(request):
    return web.Response(text="Bot is running!")

async def main():
    # Настройка веб-сервера «
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    
    await site.start()
    logging.info(f"--- Web server started on port {port} ---")

    # Запуск polling
    logging.info("--- Starting bot polling ---")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped")








