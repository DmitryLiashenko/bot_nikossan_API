import os
from io import BytesIO
import logging
import replicate
import requests
from dotenv import load_dotenv
from telegram import Bot
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

# Включаем логгирование для отладки
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# Загружаем токены из .env
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
REPLICATE_TOKEN = os.getenv("REPLICATE_API_TOKEN")

if not TELEGRAM_TOKEN or not REPLICATE_TOKEN:
    logger.error("Добавь TELEGRAM_BOT_TOKEN и REPLICATE_API_TOKEN в .env файл")
    exit(1)

# Настраиваем Replicate API
os.environ["REPLICATE_API_TOKEN"] = REPLICATE_TOKEN

# Инициализируем Telegram бота
updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
dispatcher = updater.dispatcher

def start(update, context):
    update.message.reply_text(
        "Привет! Отправь мне фото с подписью, например: 'Добавь жалюзи' — и я покажу результат."
    )

def handle_photo(update, context):
    message = update.message
    prompt = message.caption

    if not prompt:
        message.reply_text("Пожалуйста, отправь фото **с подписью**, описывающей, что нужно дорисовать.")
        return

    photo = message.photo[-1]
    file_id = photo.file_id
    os.makedirs('downloads', exist_ok=True)
    file_path = f"downloads/{file_id}.jpg"

    try:
        photo_file = context.bot.get_file(file_id)
        photo_file.download(file_path)
    except Exception as e:
        logger.error(f"Ошибка при загрузке фото: {e}")
        message.reply_text("Не удалось сохранить изображение.")
        return

    message.reply_text("Обрабатываю изображение с помощью ИИ...")

    # Пытаемся передать локальный файл напрямую в Replicate
    try:
        with open(file_path, "rb") as img:
            output = replicate.run(
                "black-forest-labs/flux-kontext-pro",
                input={"prompt": prompt, "input_image": img}
            )
    except Exception as e:
        logger.warning(f"Ошибка при передаче файла напрямую: {e}")
        # Фолбэк через загрузку на transfer.sh
        try:
            with open(file_path, 'rb') as f:
                filename = os.path.basename(file_path)
                response = requests.put(f"https://transfer.sh/{filename}", data=f)
            if response.status_code == 200:
                image_url = response.text.strip()
                logger.info(f"Загружено на transfer.sh: {image_url}")
                output = replicate.run(
                    "black-forest-labs/flux-kontext-pro",
                    input={"prompt": prompt, "input_image": image_url}
                )
            else:
                message.reply_text("Ошибка при загрузке изображения.")
                return
        except Exception as e2:
            logger.error(f"Ошибка фолбэка: {e2}")
            message.reply_text("Не удалось отправить изображение на обработку.")
            return

    # Отправляем обработанное изображение
    try:
        result = output[0] if isinstance(output, list) else output
        image_bytes = result.read()
        bio = BytesIO(image_bytes)
        bio.name = "result.png"
        bio.seek(0)
        context.bot.send_photo(chat_id=message.chat_id, photo=bio)
    except Exception as e:
        logger.error(f"Ошибка при отправке результата: {e}")
        message.reply_text("Что-то пошло не так при получении изображения.")
        return

# Регистрируем команды
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(MessageHandler(Filters.photo, handle_photo))

if __name__ == '__main__':
    print("Бот запущен...")
    updater.start_polling()
    updater.idle()