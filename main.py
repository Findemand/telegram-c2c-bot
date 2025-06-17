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
    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)
    if len(photos) >= 3:
        await message.answer("Введите описание товара:")
        await ProductForm.description.set()
    else:
        keyboard = InlineKeyboardMarkup().add(InlineKeyboardButton("➡️ Далее", callback_data="photos_done"))
        await message.answer("Можете отправить ещё фото или нажмите кнопку 'Далее'.", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == "photos_done", state=ProductForm.photos)
async def photos_done(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Введите описание товара:")
    await ProductForm.description.set()
    await call.answer()

@dp.message_handler(lambda msg: msg.text.lower() == "далее", state=ProductForm.photos)
async def skip_photos(message: Message, state: FSMContext):
    await message.answer("Введите описание товара:")
    await ProductForm.description.set()

@dp.message_handler(state=ProductForm.description)
async def get_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text.strip())
    keyboard = InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton("📦 Доставка", callback_data="delivery_delivery"),
        InlineKeyboardButton("🤝 Личная встреча", callback_data="delivery_meeting"),
        InlineKeyboardButton("📦+🤝 Оба варианта", callback_data="delivery_both")
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
    preview = f"📦 <b>{data['name']}</b>\n🏙 Город: {data['city']}\n📁 Категория: {data['category']}\n📜 Описание: {data['description']}\n🚚 Передача: {data['delivery']}\n👤 Продавец: @{call.from_user.username or 'без ника'}"
    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("✅ Опубликовать", callback_data="confirm_yes"),
        InlineKeyboardButton("❌ Отмена", callback_data="confirm_no")
    )
    await call.message.answer(preview, parse_mode="HTML", reply_markup=keyboard)
    await ProductForm.confirm.set()
    await call.answer()

@dp.callback_query_handler(lambda c: c.data == "confirm_yes", state=ProductForm.confirm)
async def confirm_publish(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not all(data.get(k) for k in ['category', 'city', 'name', 'photos', 'description', 'delivery']):
        await call.message.answer("⚠️ Некоторые поля не заполнены. Заполните анкету заново.")
        await call.answer()
        return

    data['username'] = call.from_user.username or 'без ника'
    data['created'] = datetime.now().isoformat()
    user_id = call.from_user.id

    with open(f"data_{user_id}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

    preview = f"📦 <b>{data['name']}</b>\n📍 Город: {data['city']}\n📁 Категория: {data['category']}\n📜 Описание: {data['description']}\n🚚 Передача: {data['delivery']}\n👤 Продавец: @{data['username']}"
    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{user_id}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{user_id}")
    )

    await bot.send_message(MODERATOR_CHAT_ID, preview, parse_mode="HTML", reply_markup=keyboard)
    await call.message.answer("⏳ Объявление отправлено на модерацию.")
    await call.answer()
    await state.finish()

@dp.callback_query_handler(lambda c: c.data.startswith("approve_"))
async def approve_ad(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    try:
        with open(f"data_{user_id}.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        await callback.answer("⛔️ Данные не найдены.")
        return

    caption = f"📦 <b>{data['name']}</b>\n🏙 Город: {data['city']}\n📁 Категория: {data['category']}\n📜 Описание: {data['description']}\n🚚 Передача: {data['delivery']}\n👤 Продавец: @{data['username']}"

    if data.get("photos"):
        await bot.send_photo(CHANNEL_ID, data["photos"][0], caption=caption, parse_mode="HTML")
    else:
        await bot.send_message(CHANNEL_ID, caption, parse_mode="HTML")

    await bot.send_message(user_id, "✅ Ваше объявление одобрено и опубликовано.")
    await callback.message.edit_reply_markup()
    await callback.answer("Опубликовано")

@dp.callback_query_handler(lambda c: c.data.startswith("reject_"))
async def reject_ad(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    await bot.send_message(user_id, "❌ Ваше объявление отклонено модератором.")
    await callback.message.edit_reply_markup()
    await callback.answer("Отклонено")

# === АДМИН-ПАНЕЛЬ ===

admin_keyboard = InlineKeyboardMarkup(row_width=2).add(
    InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
    InlineKeyboardButton("👥 Список объявлений", callback_data="admin_list_ads"),
    InlineKeyboardButton("📥 Экспорт CSV", callback_data="admin_export_csv"),
    InlineKeyboardButton("🧼 Очистка старых", callback_data="admin_cleanup")
)

@dp.message_handler(commands=['admin'])
async def admin_panel(message: Message):
    if message.from_user.id != MODERATOR_CHAT_ID:
        await message.answer("⛔️ Доступ запрещён")
        return
    await message.answer("🔧 Админ-панель:", reply_markup=admin_keyboard)

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
            preview = f"📦 <b>{data['name']}</b>\nГород: {data['city']}\nПродавец: @{data['username']}"
            await callback.message.answer(preview, parse_mode="HTML")
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "admin_export_csv")
async def export_csv(callback: CallbackQuery):
    files = [f for f in os.listdir() if f.startswith("data_") and f.endswith(".json")]
    if not files:
        await callback.message.answer("Нет объявлений для экспорта.")
        return
    with open("ads_export.csv", "w", newline="", encoding="utf-8") as csvfile:
        fieldnames = ["user_id", "username", "name", "category", "city", "delivery", "description"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for f in files:
            with open(f, encoding="utf-8") as j:
                data = json.load(j)
                writer.writerow({
                    "user_id": f.replace("data_", "").replace(".json", ""),
                    "username": data.get("username"),
                    "name": data.get("name"),
                    "category": data.get("category"),
                    "city": data.get("city"),
                    "delivery": data.get("delivery"),
                    "description": data.get("description")
                })
    await bot.send_document(callback.from_user.id, InputFile("ads_export.csv"))
    await callback.answer("CSV создан")

@dp.callback_query_handler(lambda c: c.data == "admin_cleanup")
async def cleanup_old(callback: CallbackQuery):
    now = datetime.now()
    count = 0
    for f in os.listdir():
        if f.startswith("data_") and f.endswith(".json"):
            with open(f, encoding="utf-8") as j:
                data = json.load(j)
                created = datetime.fromisoformat(data.get("created", "2000-01-01T00:00:00"))
                if now - created > timedelta(days=30):
                    os.remove(f)
                    count += 1
    await callback.message.answer(f"🧹 Удалено {count} устаревших объявлений")
    await callback.answer()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
