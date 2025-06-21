import os
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackContext,
    CallbackQueryHandler,
)
from openai import OpenAI

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

logging.basicConfig(level=logging.INFO)

REFERENCE_DESCRIPTION = "Add modern roller blinds on the window in this photo. The blinds should look like the reference: smooth fabric roller blinds, mounted on top of the window frame, with a clean white mechanism and a light green pastel color fabric, covering most of the window"


async def start(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("Тканевые ролеты", callback_data="roller_blinds")]
    ]
    await update.message.reply_text(
        "Выберите тип солнцезащитной системы:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def button(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    context.user_data["blinds_type"] = query.data
    await query.edit_message_text("Отправьте фото окна для дорисовки.")


async def handle_photo(update: Update, context: CallbackContext):
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    image_path = f"images/{photo.file_id}.jpg"
    await file.download_to_drive(image_path)

    await update.message.reply_text(
        "Генерирую изображение с тканевыми ролетами через OpenAI..."
    )

    result_url = generate_image_with_openai()
    if result_url:
        await update.message.reply_photo(photo=result_url)
    else:
        await update.message.reply_text("Ошибка при генерации изображения.")


def generate_image_with_openai():
    response = client.images.generate(
        model="dall-e-3",
        prompt=f"Окно с добавленными {REFERENCE_DESCRIPTION}. Изображение реалистичное, современное, профессиональная фотография интерьера.",
        n=1,
        size="1024x1024",
        quality="standard",
        response_format="url",
    )
    return response.data[0].url if response.data else None


if __name__ == "__main__":
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.run_polling()
