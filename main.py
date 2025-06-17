
import logging
import os
import json
import csv
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from aiogram.utils import executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from dotenv import load_dotenv

from inline_categories import get_inline_categories_keyboard
from inline_cities import get_city_keyboard

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
MODERATOR_CHAT_ID = int(os.getenv("MODERATOR_CHAT_ID"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())
logging.basicConfig(level=logging.INFO)

BANNED_USERS_FILE = "banned_users.json"

def load_banned_users():
    if os.path.exists(BANNED_USERS_FILE):
        with open(BANNED_USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_banned_users(users):
    with open(BANNED_USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f)

class ProductForm(StatesGroup):
    category = State()
    city = State()
    custom_city = State()
    name = State()
    photos = State()
    description = State()
    delivery = State()
    confirm = State()

@dp.message_handler(commands=['start', 'sell'])
async def cmd_start(message: Message):
    banned = load_banned_users()
    if message.from_user.id in banned:
        await message.answer("⛔️ Вы были заблокированы и не можете публиковать объявления.")
        return
    await message.answer("Выберите категорию товара:", reply_markup=get_inline_categories_keyboard())
    await ProductForm.category.set()

@dp.message_handler(commands=['admin'])
async def admin_panel(message: Message):
    if message.from_user.id != MODERATOR_CHAT_ID:
        await message.answer("⛔️ Доступ запрещен")
        return
    keyboard = InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
        InlineKeyboardButton("👥 Список объявлений", callback_data="admin_list_ads"),
        InlineKeyboardButton("📥 Экспорт CSV", callback_data="admin_export_csv"),
        InlineKeyboardButton("🧼 Очистка старых", callback_data="admin_cleanup"),
        InlineKeyboardButton("👤 Заблокированные", callback_data="admin_banned_list")
    )
    await message.answer("🔧 Админ-панель:", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    files = [f for f in os.listdir() if f.startswith("data_") and f.endswith(".json")]
    await callback.message.answer(f"📦 Всего объявлений: {len(files)}")
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "admin_list_ads")
async def list_ads(callback: CallbackQuery):
    files = [f for f in os.listdir() if f.startswith("data_") and f.endswith(".json")]
    if not files:
        await callback.message.answer("Нет активных объявлений.")
        return
    for f in files:
        with open(f, encoding="utf-8") as j:
            data = json.load(j)
            uid = int(f.replace("data_", "").replace(".json", ""))
    preview = (
    f"📦 <b>{data['name']}</b>\n"
    f"🏙 Город: {data['city']}\n"
    f"👤 Продавец: @{data['username']}"
)

kb = InlineKeyboardMarkup().add(
    InlineKeyboardButton("🚫 Забанить", callback_data=f"ban_{uid}"),
    InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{uid}"),
    InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{uid}")
)
            await callback.message.answer(preview, parse_mode="HTML", reply_markup=kb)
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("ban_"))
async def ban_user(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    banned = load_banned_users()
    if user_id not in banned:
        banned.append(user_id)
        save_banned_users(banned)
    await bot.send_message(user_id, "🚫 Вы были заблокированы и не можете публиковать объявления.")
    await callback.message.answer("✅ Пользователь заблокирован.")
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("unban_"))
async def unban_user(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    banned = load_banned_users()
    if user_id in banned:
        banned.remove(user_id)
        save_banned_users(banned)
    await bot.send_message(user_id, "✅ Вы были разблокированы. Теперь вы можете публиковать объявления.")
    await callback.message.answer("✅ Пользователь разблокирован.")
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "admin_banned_list")
async def show_banned(callback: CallbackQuery):
    banned = load_banned_users()
    if not banned:
        await callback.message.answer("📭 Список заблокированных пуст.")
        return
    for uid in banned:
        kb = InlineKeyboardMarkup().add(
            InlineKeyboardButton("🔓 Разблокировать", callback_data=f"unban_{uid}")
        )
        await callback.message.answer(f"👤 ID: <code>{uid}</code>", parse_mode="HTML", reply_markup=kb)
    await callback.answer()

    executor.start_polling(dp, skip_updates=True)
