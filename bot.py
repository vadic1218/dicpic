import os
import logging
import openai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# ========== БЕЗОПАСНОЕ ПОЛУЧЕНИЕ ТОКЕНОВ ==========
TELEGRAM_TOKEN = os.getenv("8544944228:AAF2rB9QyNyua_Bs0paCtX8UDwtvkW_QNGA")  # Берётся из переменных окружения Railway
GITHUB_TOKEN = os.getenv("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")          # Тоже из переменных окружения

# Проверка, что токены загружены
if not TELEGRAM_TOKEN:
    raise ValueError("❌ TELEGRAM_BOT_TOKEN не найден в переменных окружения!")
if not GITHUB_TOKEN:
    raise ValueError("❌ GITHUB_TOKEN не найден в переменных окружения!")

# Клиент GitHub Models (новый адрес!)
client = openai.OpenAI(
    base_url="https://models.github.ai",  # ← ВАЖНО: новый адрес!
    api_key=GITHUB_TOKEN,
    timeout=30.0
)

# Актуальные модели
AVAILABLE_MODELS = {
    "deepseek-r1": {
        "name": "🧠 DeepSeek R1",
        "model": "DeepSeek-R1"
    },
    "deepseek-v3": {
        "name": "📘 DeepSeek V3",
        "model": "DeepSeek-V3"
    },
    "gpt-4o-mini": {
        "name": "⚡ GPT-4o Mini (работает 100%)",
        "model": "gpt-4o-mini"
    },
    "llama-3.3": {
        "name": "🦙 Llama 3.3 70B (работает 100%)",
        "model": "Llama-3.3-70B-Instruct"
    }
}
DEFAULT_MODEL = "gpt-4o-mini"

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Хранилище выбранных моделей
user_models = {}

# ========== КОМАНДЫ ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Я бот с бесплатными моделями (GitHub Models).\n"
        "Просто отправь сообщение, и я отвечу.\n\n"
        "/model — выбрать модель\n"
        "/help — справка"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/start — приветствие\n"
        "/help — справка\n"
        "/model — выбрать модель"
    )

async def model_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = []
    for model_id, info in AVAILABLE_MODELS.items():
        keyboard.append([InlineKeyboardButton(info["name"], callback_data=model_id)])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите модель:", reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    model_id = query.data
    if model_id not in AVAILABLE_MODELS:
        await query.edit_message_text("❌ Модель не найдена.")
        return
    user_models[user_id] = model_id
    model_name = AVAILABLE_MODELS[model_id]["name"]
    await query.edit_message_text(f"✅ Теперь используется модель: {model_name}")

# ========== ОБРАБОТКА СООБЩЕНИЙ ==========
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text

    logger.info(f"Сообщение от {user_id}: {user_text[:50]}...")

    model_id = user_models.get(user_id, DEFAULT_MODEL)
    if model_id not in AVAILABLE_MODELS:
        model_id = DEFAULT_MODEL

    model_info = AVAILABLE_MODELS[model_id]
    api_model_name = model_info["model"]
    logger.info(f"Используется модель: {model_info['name']} → API имя: {api_model_name}")

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        logger.info("Отправка запроса к GitHub Models...")
        completion = client.chat.completions.create(
            model=api_model_name,
            messages=[{"role": "user", "content": user_text}],
        )
        response = completion.choices[0].message.content
        logger.info("Ответ получен, длина: %d символов", len(response))
        safe_response = response.encode('utf-8', errors='replace').decode('utf-8')
        await update.message.reply_text(safe_response)
        logger.info("Ответ отправлен пользователю")

    except openai.NotFoundError as e:
        logger.error(f"404 Not Found: {e}")
        await update.message.reply_text(
            f"❌ Модель '{model_info['name']}' временно недоступна.\n"
            "Попробуйте другую модель через /model"
        )
    except openai.AuthenticationError as e:
        logger.error(f"Ошибка аутентификации: {e}")
        await update.message.reply_text("❌ Неверный токен GitHub. Проверьте переменную GITHUB_TOKEN в Railway.")
    except openai.RateLimitError as e:
        logger.error(f"Rate limit: {e}")
        await update.message.reply_text("❌ Слишком много запросов. Подождите минуту и попробуйте снова.")
    except Exception as e:
        logger.exception("Непредвиденная ошибка")
        error_text = str(e).encode('utf-8', errors='replace').decode('utf-8')
        await update.message.reply_text(f"❌ Внутренняя ошибка: {error_text[:200]}")

# ========== ЗАПУСК ==========
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("model", model_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Бот запущен...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()