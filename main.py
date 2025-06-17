
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
    name = State()
    photos = State()
    description = State()
    delivery = State()
    confirm = State()

@dp.message_handler(commands=['start', 'sell'])
async def cmd_start(message: Message):
    if message.from_user.id in load_banned_users():
        await message.answer("🚫 Вы заблокированы и не можете публиковать объявления.")
        return
    keyboard = InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton("📦 Одежда", callback_data="cat_clothes"),
        InlineKeyboardButton("📱 Техника", callback_data="cat_tech")
    )
    await message.answer("Выберите категорию товара:", reply_markup=keyboard)
    await ProductForm.category.set()

@dp.callback_query_handler(lambda c: c.data.startswith("cat_"), state=ProductForm.category)
async def category_selected(call: CallbackQuery, state: FSMContext):
    await state.update_data(category=call.data.replace("cat_", ""))
    keyboard = InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton("📍 Москва", callback_data="city_moscow"),
        InlineKeyboardButton("📍 Питер", callback_data="city_spb")
    )
    await call.message.answer("Выберите город:", reply_markup=keyboard)
    await ProductForm.city.set()
    await call.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("city_"), state=ProductForm.city)
async def city_selected(call: CallbackQuery, state: FSMContext):
    await state.update_data(city=call.data.replace("city_", ""))
    await call.message.answer("Введите название товара:")
    await ProductForm.name.set()
    await call.answer()

@dp.message_handler(state=ProductForm.name)
async def get_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("Отправьте до 3 фото товара:")
    await ProductForm.photos.set()

@dp.message_handler(content_types=['photo'], state=ProductForm.photos)
async def get_photos(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)
    if len(photos) >= 3:
        await message.answer("Введите описание:")
        await ProductForm.description.set()
    else:
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("Далее", callback_data="skip_photos"))
        await message.answer("Можете отправить ещё фото или нажмите 'Далее'.", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data == "skip_photos", state=ProductForm.photos)
async def skip_photos(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Введите описание:")
    await ProductForm.description.set()
    await call.answer()

@dp.message_handler(state=ProductForm.description)
async def get_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text.strip())
    kb = InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton("📦 Доставка", callback_data="delivery_delivery"),
        InlineKeyboardButton("🤝 Встреча", callback_data="delivery_meeting")
    )
    await message.answer("Выберите способ передачи:", reply_markup=kb)
    await ProductForm.delivery.set()

@dp.callback_query_handler(lambda c: c.data.startswith("delivery_"), state=ProductForm.delivery)
async def get_delivery(call: CallbackQuery, state: FSMContext):
    await state.update_data(delivery=call.data.replace("delivery_", ""))
    data = await state.get_data()
    await call.message.answer(
        f"📦 <b>{data['name']}</b>\n🏙 Город: {data['city']}\n📁 Категория: {data['category']}\n📜 Описание: {data['description']}\n🚚 Передача: {data['delivery']}\n👤 @{call.from_user.username or 'без ника'}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("✅ Опубликовать", callback_data="confirm_yes"),
            InlineKeyboardButton("❌ Отмена", callback_data="confirm_no")
        )
    )
    await ProductForm.confirm.set()
    await call.answer()

@dp.callback_query_handler(lambda c: c.data == "confirm_yes", state=ProductForm.confirm)
async def confirm_post(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_id = call.from_user.id
    data['username'] = call.from_user.username or "без ника"
    with open(f"data_{user_id}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{user_id}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{user_id}"),
        InlineKeyboardButton("🚫 Забанить", callback_data=f"ban_{user_id}")
    )
    await bot.send_message(MODERATOR_CHAT_ID, f"Новое объявление от @{data['username']}", reply_markup=kb)
    await call.message.answer("Объявление отправлено на модерацию.")
    await state.finish()
    await call.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("approve_"))
async def approve(callback: CallbackQuery):
    uid = callback.data.split("_")[1]
    with open(f"data_{uid}.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    caption = (
        f"📦 <b>{data['name']}</b>\n🏙 {data['city']}\n📁 {data['category']}\n📜 {data['description']}\n🚚 {data['delivery']}\n👤 @{data['username']}"
    )
    if data.get("photos"):
        await bot.send_photo(CHANNEL_ID, data["photos"][0], caption=caption, parse_mode="HTML")
    else:
        await bot.send_message(CHANNEL_ID, caption, parse_mode="HTML")
    await bot.send_message(uid, "✅ Ваше объявление опубликовано.")
    await callback.message.edit_reply_markup()
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("reject_"))
async def reject(callback: CallbackQuery):
    uid = callback.data.split("_")[1]
    await bot.send_message(uid, "❌ Ваше объявление отклонено.")
    await callback.message.edit_reply_markup()
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("ban_"))
async def ban(callback: CallbackQuery):
    uid = int(callback.data.split("_")[1])
    banned = load_banned_users()
    if uid not in banned:
        banned.append(uid)
        save_banned_users(banned)
    await bot.send_message(uid, "🚫 Вы заблокированы.")
    await callback.message.edit_reply_markup()
    await callback.answer("Пользователь заблокирован")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)

    await bot.send_message(user_id, "✅ Вы были разблокированы. Теперь вы можете публиковать объявления.")
    await callback.message.edit_reply_markup()
    await callback.answer("Пользователь разбанен")
