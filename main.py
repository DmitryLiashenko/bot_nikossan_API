import os
import uuid
import replicate
import requests

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    CallbackQueryHandler,
    filters,
)
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

# Настройка клиента Replicate
replicate_client = replicate.Client(api_token=REPLICATE_API_TOKEN)

# Словарь для хранения фото пользователей
user_photos = {}


# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Отправь мне фото окна, и я покажу, как на нём будут смотреться солнцезащитные системы. 🌞🪟"
    )


# Обработка отправленного фото
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    photo = update.message.photo[-1]  # Самое большое
    user_photos[user_id] = photo.file_id

    keyboard = [
        [InlineKeyboardButton("Жалюзи день/ночь", callback_data="daynight")],
        [InlineKeyboardButton("Шторы", callback_data="curtains")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Выбери тип солнцезащитной системы:", reply_markup=reply_markup
    )


# Обработка нажатия кнопки
async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    file_id = user_photos.get(user_id)

    if not file_id:
        await query.edit_message_text("Сначала отправь фото.")
        return

    prompt = ""
    if query.data == "daynight":
        prompt = "add modern day-night blinds on the window"
    elif query.data == "curtains":
        prompt = "add light beige curtains on the window"

    try:
        await query.edit_message_text("Обрабатываю изображение... 🧠")

        output_url = await process_with_flux(context.bot, file_id, prompt)

        await context.bot.send_photo(chat_id=user_id, photo=output_url)

    except Exception as e:
        await context.bot.send_message(
            chat_id=user_id, text=f"Ошибка при обработке: {e}"
        )


# Функция обработки через Replicate с сохранением локального файла
async def process_with_flux(bot, file_id: str, prompt: str) -> str:
    tg_file = await bot.get_file(file_id)
    file_bytes = await tg_file.download_as_bytearray()

    # Сохраняем файл локально
    filename = f"temp_{uuid.uuid4().hex}.jpg"
    with open(filename, "wb") as f:
        f.write(file_bytes)

    # Загружаем на file.io временно (можно заменить позже на другой способ)
    with open(filename, "rb") as f:
        response = requests.post("https://file.io", files={"file": f})
        response.raise_for_status()
        data = response.json()
        if not data.get("success"):
            raise Exception("Ошибка загрузки изображения")
        image_url = data["link"]

    # Удаляем файл после загрузки
    os.remove(filename)

    # Отправляем в Replicate
    output = replicate_client.run(
        "black-forest-labs/flux-kontext-pro",
        input={"image": image_url, "prompt": prompt},
    )
    return output


# Запуск бота
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(handle_button))

    print("Бот запущен...")
    app.run_polling()
