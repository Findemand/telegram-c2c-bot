import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
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
    await message.answer("Выберите категорию товара:", reply_markup=get_inline_categories_keyboard())
    await ProductForm.category.set()

@dp.callback_query_handler(lambda c: c.data.startswith("cat_"), state=ProductForm.category)
async def category_selected(call: CallbackQuery, state: FSMContext):
    category_map = {
        "cat_clothes": "Одежда и обувь",
        "cat_tech": "Техника и электроника",
        "cat_home": "Для дома и дачи",
        "cat_kids": "Товары для детей",
        "cat_hobby": "Хобби и развлечения",
        "cat_beauty": "Красота и здоровье",
        "cat_auto": "Автотовары",
        "cat_pets": "Животные",
        "cat_collectibles": "Коллекционные вещи",
        "cat_misc": "Разное",
    }
    await state.update_data(category=category_map[call.data])
    await call.message.answer("Выберите город:", reply_markup=get_city_keyboard())
    await ProductForm.city.set()
    await call.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("city_"), state=ProductForm.city)
async def city_selected(call: CallbackQuery, state: FSMContext):
    if call.data == "city_custom":
        await call.message.answer("Введите название вашего города:")
        await ProductForm.custom_city.set()
    else:
        city_map = {
            "city_moscow": "Москва",
            "city_spb": "Санкт-Петербург",
            "city_nsk": "Новосибирск",
            "city_ekb": "Екатеринбург",
            "city_kzn": "Казань",
            "city_nnov": "Нижний Новгород"
        }
        await state.update_data(city=city_map[call.data])
        await call.message.answer("Введите название товара:")
        await ProductForm.name.set()
    await call.answer()

@dp.message_handler(state=ProductForm.custom_city)
async def get_custom_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text.strip())
    await message.answer("Введите название товара:")
    await ProductForm.name.set()

@dp.message_handler(state=ProductForm.name)
async def get_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("Теперь отправьте до 3 фото товара.")
    await ProductForm.photos.set()

@dp.message_handler(content_types=['photo'], state=ProductForm.photos)
async def get_photos(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get('photos', [])
    photos = photos if photos else []
    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)
    if len(photos) >= 3:
        await message.answer("Введите описание товара:")
        await ProductForm.description.set()
    else:
        await message.answer("Можете отправить ещё фото или напишите 'далее'.")

@dp.message_handler(lambda msg: msg.text.lower() == "далее", state=ProductForm.photos)
async def skip_photos(message: Message, state: FSMContext):
    await message.answer("Введите описание товара:")
    await ProductForm.description.set()

@dp.message_handler(state=ProductForm.description)
async def get_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text.strip())
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📦 Доставка", callback_data="delivery_delivery"),
        InlineKeyboardButton("🤝 Личная встреча", callback_data="delivery_meeting"),
        InlineKeyboardButton("📦+🤝 Оба варианта", callback_data="delivery_both"),
    )
    await message.answer("Выберите способ передачи:", reply_markup=keyboard)
    await ProductForm.delivery.set()

@dp.callback_query_handler(lambda c: c.data.startswith("delivery_"), state=ProductForm.delivery)
async def get_delivery(call: CallbackQuery, state: FSMContext):
    delivery_methods = {
        "delivery_delivery": "Доставка",
        "delivery_meeting": "Личная встреча",
        "delivery_both": "Доставка или личная встреча"
    }
    await state.update_data(delivery=delivery_methods[call.data])
    data = await state.get_data()
    preview = f"📦 <b>{data['name']}</b>\\n🏙 Город: {data['city']}\\n📁 Категория: {data['category']}\\n📜 Описание: {data['description']}\\n🚚 Передача: {data['delivery']}\\n👤 Продавец: @{call.from_user.username or 'без ника'}"
    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("✅ Опубликовать", callback_data="confirm_yes"),
        InlineKeyboardButton("❌ Отмена", callback_data="confirm_no")
    )
    await call.message.answer(preview, parse_mode="HTML", reply_markup=kb)
    await ProductForm.confirm.set()
    await call.answer()


ads = {}

@dp.callback_query_handler(lambda c: c.data == "confirm_yes", state=ProductForm.confirm)
async def confirm_publish(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    required_fields = ['category', 'city', 'name', 'photos', 'description', 'delivery']
    missing = [f for f in required_fields if not data.get(f)]
    if missing:
        await call.message.answer("⚠️ Некоторые поля не заполнены. Заполните анкету заново.")
        await call.answer()
        return

    await state.finish()
    user_id = call.from_user.id
    ads[user_id] = data  # сохраняем данные в память

    preview = f"📦 <b>{data['name']}</b>\\n🏙 Город: {data['city']}\\n📁 Категория: {data['category']}\\n📜 Описание: {data['description']}\\n🚚 Передача: {data['delivery']}\\n👤 Продавец: @{call.from_user.username or 'без ника'}
    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{user_id}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{user_id}")
    )

    await bot.send_message(MODERATOR_CHAT_ID, preview, parse_mode="HTML", reply_markup=kb)
    await call.message.answer("⏳ Объявление отправлено на модерацию.")
    await call.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("approve_"))
async def approve_ad(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    data = ads.get(user_id)
    if not data:
        await callback.answer("⛔️ Данные не найдены.")
        return

    caption = f"📦 <b>{data['name']}</b>\\n🏙 Город: {data['city']}\\n📁 Категория: {data['category']}\\n📜 Описание: {data['description']}\\n🚚 Передача: {data['delivery']}\\n👤 Продавец: @{call.from_user.username or 'без ника'}"

    if data.get("photos"):
        await bot.send_photo(CHANNEL_ID, photo=data["photos"][0], caption=caption, parse_mode="HTML")
    else:
        await bot.send_message(CHANNEL_ID, caption, parse_mode="HTML")

    await bot.send_message(user_id, "✅ Ваше объявление одобрено и опубликовано.")
    await callback.message.edit_reply_markup()
    await callback.answer("Опубликовано")
@dp.callback_query_handler(lambda c: c.data.startswith("reject_"))

async def approve_ad(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    msg = callback.message.text
    await bot.send_message(CHANNEL_ID, msg, parse_mode="HTML")
    await bot.send_message(user_id, "✅ Ваше объявление одобрено и опубликовано.")
    await callback.message.edit_reply_markup()
    await callback.answer("Опубликовано")

@dp.callback_query_handler(lambda c: c.data.startswith("reject_"))
async def reject_ad(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    await bot.send_message(user_id, "❌ Ваше объявление отклонено модератором.")
    await callback.message.edit_reply_markup()
    await callback.answer("Отклонено")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)