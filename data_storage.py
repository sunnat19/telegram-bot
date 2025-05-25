import json
import os
from datetime import date

DB_PATH = 'users.json'
# Структура:
# { user_id: { profile: {...}, logs: { water: [...], food: [...], workout: [...] } } }

def load_data() -> dict:
    if not os.path.exists(DB_PATH):
        return {}
    with open(DB_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_data(data: dict):
    with open(DB_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _get_logs(data, user_id: str) -> dict:
    return data.setdefault(user_id, {}).setdefault('logs', {})

def set_user_profile(user_id: str, profile: dict):
    data = load_data()
    data.setdefault(user_id, {})['profile'] = profile
    save_data(data)

def get_user_profile(user_id: str) -> dict:
    return load_data().get(user_id, {}).get('profile', {})

def log_water(user_id: str, amount: int):
    data = load_data()
    logs = _get_logs(data, user_id)
    logs.setdefault('water', []).append({ 'date': date.today().isoformat(), 'amount': amount })
    save_data(data)

def log_food(user_id: str, name: str, kcal: float):
    data = load_data()
    logs = _get_logs(data, user_id)
    logs.setdefault('food', []).append({ 'date': date.today().isoformat(), 'name': name, 'kcal': kcal })
    save_data(data)

def log_workout(user_id: str, act_type: str, minutes: int, kcal: int, water: int):
    data = load_data()
    logs = _get_logs(data, user_id)
    logs.setdefault('workout', []).append({ 'date': date.today().isoformat(), 'type': act_type, 'minutes': minutes, 'kcal': kcal, 'water': water })
    save_data(data)

def get_progress(user_id: str, water_goal: int, cal_goal: int) -> dict:
    logs = load_data().get(user_id, {}).get('logs', {})
    today = date.today().isoformat()
    drank  = sum(e['amount'] for e in logs.get('water', [])   if e['date']==today)
    eaten  = sum(e['kcal']   for e in logs.get('food',  [])   if e['date']==today)
    burned = sum(e['kcal']   for e in logs.get('workout',[])  if e['date']==today)
    return { 'water': { 'drank': drank, 'goal': water_goal }, 'calories': { 'eaten': eaten, 'burned': burned, 'goal': cal_goal }}
