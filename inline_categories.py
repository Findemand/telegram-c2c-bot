from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_inline_categories_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    categories = [
        ("👕 Одежда и обувь", "cat_clothes"),
        ("📱 Техника и электроника", "cat_tech"),
        ("🏠 Для дома и дачи", "cat_home"),
        ("🧸 Товары для детей", "cat_kids"),
        ("🎸 Хобби и развлечения", "cat_hobby"),
        ("💄 Красота и здоровье", "cat_beauty"),
        ("🚗 Автотовары", "cat_auto"),
        ("🐾 Животные", "cat_pets"),
        ("🪙 Коллекционные вещи", "cat_collectibles"),
        ("📦 Разное", "cat_misc"),
    ]
    for name, data in categories:
        keyboard.insert(InlineKeyboardButton(text=name, callback_data=data))
    return keyboard
