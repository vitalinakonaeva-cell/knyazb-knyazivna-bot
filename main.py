import os
import logging
from datetime import datetime, timedelta, timezone
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# =============== НАСТРОЙКИ ===============
BOT_TOKEN = os.getenv("8228312942:AAH9W6pWWwC7IVAB_31BAdns3Cnc9k5potU")  # Токен из переменных окружения
ADMIN_ID = 1491698235               # Замени на свой Telegram ID
DEADLINE_MINUTES = 6                # Время на заполнение формы
# ========================================

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("kniaz_bot")

# Состояния диалога
PHOTO, PSEUDONYM, CREDO_LAW, FULLNAME = range(4)

# Тексты сообщений
WELCOME = (
    "Вітаю! Ви хочете подати свою кандидатуру на фото-конкурс "
    "«Князь і Князівна коледжу». Для участі надішліть свою роботу (фото-косплей)."
)
ASK_PSEUDONYM = (
    "Напишіть свій псевдонім з характеристикою, наприклад: "
    "Князь-відважний або Княгиня-прегарна."
)
ASK_CREDO_LAW = "Тепер проголосіть свій постулат (кредо) і перший прийнятий закон."
ASK_FULLNAME = "Вкажіть свої ПІБ і групу."
THANKS = "Дякую! Ваша заявка прийнята. Очікуйте новин 🙂"
TIMEOUT_MSG = (
    "Минуло більше ніж 6 хв від початку оформлення заявки, діалог скинуто. "
    "Щоб почати знову — введіть /start."
)
CANCEL_MSG = "Заявку скасовано. Ви можете почати знову командою /start."


# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====
def _now_utc():
    return datetime.now(timezone.utc)


def _deadline_exceeded(context: ContextTypes.DEFAULT_TYPE) -> bool:
    dl = context.user_data.get("deadline")
    return bool(dl and _now_utc() > dl)


async def _ensure_deadline_or_abort(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Проверка тайм-аута. Если истёк — завершает диалог."""
    if _deadline_exceeded(context):
        await update.effective_chat.send_message(TIMEOUT_MSG, reply_markup=ReplyKeyboardRemove())
        return False
    return True


async def _send_submission_to_admin(context: ContextTypes.DEFAULT_TYPE):
    """Отправка заявки админу"""
    data = context.user_data
    photo_id = data.get("photo_file_id")
    pseudo = data.get("pseudonym")
    credo = data.get("credo")
    fullname = data.get("fullname")
    user = data.get("user_mention", "—")

    text = (
        "📨 НОВА ЗАЯВКА НА КОНКУРС «Князь і Князівна коледжу»\n\n"
        f"Від: {user}\n"
        f"Псевдонім: {pseudo}\n"
        f"Кредо і закон: {credo}\n"
        f"ПІБ і група: {fullname}\n"
        f"Час (UTC): {_now_utc().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    try:
        if photo_id:
            await context.bot.send_photo(chat_id=ADMIN_ID, photo=photo_id, caption=text)
        else:
            await context.bot.send_message(chat_id=ADMIN_ID, text=text)
    except Exception as e:
        logger.warning(f"Не вдалося надіслати заявку адміну: {e}")


# ====== ОБРАБОТЧИКИ ДИАЛОГА ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Старт диалога"""
    context.user_data["deadline"] = _now_utc() + timedelta(minutes=DEADLINE_MINUTES)
    user = update.effective_user
    mention = f"{user.full_name} (@{user.username})" if user.username else user.full_name
    context.user_data["user_mention"] = mention

    await update.message.reply_text(WELCOME)
    return PHOTO


async def photo_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _ensure_deadline_or_abort(update, context):
        return ConversationHandler.END
    if update.message and update.message.photo:
        context.user_data["photo_file_id"] = update.message.photo[-1].file_id
        await update.message.reply_text(ASK_PSEUDONYM)
        return PSEUDONYM
    await update.message.reply_text("Надішліть, будь ласка, саме фото-косплей.")
    return PHOTOasync def pseudonym_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _ensure_deadline_or_abort(update, context):
        return ConversationHandler.END
    context.user_data["pseudonym"] = update.message.text.strip()
    await update.message.reply_text(ASK_CREDO_LAW)
    return CREDO_LAW


async def credo_law_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _ensure_deadline_or_abort(update, context):
        return ConversationHandler.END
    context.user_data["credo"] = update.message.text.strip()
    await update.message.reply_text(ASK_FULLNAME)
    return FULLNAME


async def fullname_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _ensure_deadline_or_abort(update, context):
        return ConversationHandler.END
    context.user_data["fullname"] = update.message.text.strip()
    await update.message.reply_text(THANKS, reply_markup=ReplyKeyboardRemove())
    await _send_submission_to_admin(context)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(CANCEL_MSG, reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


# ====== ЗАПУСК БОТА ======
def main():
    if not BOT_TOKEN:
        raise ValueError("❌ BOT_TOKEN не найден! Добавь его в переменные окружения.")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            PHOTO: [MessageHandler(filters.PHOTO, photo_received)],
            PSEUDONYM: [MessageHandler(filters.TEXT & ~filters.COMMAND, pseudonym_received)],
            CREDO_LAW: [MessageHandler(filters.TEXT & ~filters.COMMAND, credo_law_received)],
            FULLNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, fullname_received)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    app.add_handler(conv_handler)

    logger.info("✅ Бот запущен і готовий до роботи.")
    app.run_polling()


if __name__ == "main":
    main()
