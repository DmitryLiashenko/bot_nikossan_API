import os
import logging
import asyncio
from io import BytesIO

from PIL import Image, ImageDraw
import httpx
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    CallbackQueryHandler,
    filters,
)

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

user_photos = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Отправь мне фото окна, и я покажу, как будут выглядеть шторы. 🌞🪟"
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    file_path = f"user_{user_id}.png"
    await file.download_to_drive(file_path)
    user_photos[user_id] = file_path

    keyboard = [
        [InlineKeyboardButton("Жалюзи горизонтальные", callback_data="horizontal")],
        [InlineKeyboardButton("Шторы день/ночь", callback_data="daynight")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выбери тип штор:", reply_markup=reply_markup)


def create_mask(image_path: str) -> str:
    """
    Автоматически создаём маску.
    Для простоты — чёрно-белое изображение
    с белым прямоугольником по центру (окно).
    """
    with Image.open(image_path) as img:
        mask = Image.new("L", img.size, 0)  # Чёрный фон
        draw = ImageDraw.Draw(mask)

        # Пример — прямоугольник по центру 80% ширины и 70% высоты
        w, h = img.size
        rect_w, rect_h = int(w * 0.8), int(h * 0.7)
        left = (w - rect_w) // 2
        top = (h - rect_h) // 2
        right = left + rect_w
        bottom = top + rect_h
        draw.rectangle([left, top, right, bottom], fill=255)  # Белый прямоугольник

        mask_path = image_path.replace(".png", "_mask.png")
        mask.save(mask_path)
        return mask_path


async def generate_image_with_openai(image_path: str, prompt: str) -> str:
    mask_path = create_mask(image_path)

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
    }

    files = {
        "model": (None, "dall-e-2"),
        "image": (os.path.basename(image_path), open(image_path, "rb"), "image/png"),
        "mask": (os.path.basename(mask_path), open(mask_path, "rb"), "image/png"),
        "prompt": (None, prompt),
        "n": (None, "1"),
        "size": (None, "512x512"),
    }

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            "https://api.openai.com/v1/images/edits",
            headers=headers,
            files=files,
        )

    if response.status_code == 200:
        result = response.json()
        image_url = result["data"][0]["url"]

        output_path = image_path.replace(".png", "_result.png")
        async with httpx.AsyncClient() as client:
            resp = await client.get(image_url)
            with open(output_path, "wb") as out_file:
                out_file.write(resp.content)
        return output_path
    else:
        logger.error(f"OpenAI API error: {response.status_code} - {response.text}")
        return None


async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    choice = query.data

    photo_path = user_photos.get(user_id)
    if not photo_path:
        await query.edit_message_text("Сначала отправь фото окна.")
        return

    prompt_map = {
        "horizontal": "Добавь на окно реалистичные горизонтальные жалюзи, подходящие под перспективу и освещение.",
        "daynight": "Добавь на окно реалистичные шторы день/ночь, подходящие под интерьер.",
    }
    prompt = prompt_map.get(choice, "Добавь на окно шторы.")

    await query.edit_message_text("Обрабатываю изображение... 🧠")

    try:
        result_path = await generate_image_with_openai(photo_path, prompt)
        if result_path:
            with open(result_path, "rb") as img:
                await context.bot.send_photo(chat_id=user_id, photo=img)
        else:
            await context.bot.send_message(
                chat_id=user_id, text="Не удалось обработать изображение."
            )
    except Exception as e:
        logger.error(f"Ошибка при обработке изображения: {e}")
        await context.bot.send_message(
            chat_id=user_id, text="Произошла ошибка при обработке изображения."
        )


if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(handle_button))

    print("Бот запущен...")
    app.run_polling()
