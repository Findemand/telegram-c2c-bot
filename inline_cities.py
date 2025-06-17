from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_city_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    top_cities = [
        ("🏙 Москва", "city_moscow"),
        ("🏙 Санкт-Петербург", "city_spb"),
        ("🏙 Новосибирск", "city_nsk"),
        ("🏙 Екатеринбург", "city_ekb"),
        ("🏙 Казань", "city_kzn"),
        ("🏙 Нижний Новгород", "city_nnov"),
    ]
    for name, code in top_cities:
        keyboard.insert(InlineKeyboardButton(text=name, callback_data=code))
    keyboard.add(InlineKeyboardButton("➕ Ввести свой город", callback_data="city_custom"))
    return keyboard
