# requirements:
# python-telegram-bot>=20.8

import logging
from datetime import datetime, timedelta, timezone

from telegram import (
    Update,
    ReplyKeyboardRemove,
    InputMediaPhoto,
    constants,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ================== НАСТРОЙКИ ==================
BOT_TOKEN = "8228312942:AAH9W6pWWwC7IVAB_31BAdns3Cnc9k5potU"
ADMIN_ID = 1491698235  # ваш Telegram user ID
DEADLINE_MINUTES = 6
HEALTHCHECK_INTERVAL_SEC = 30 * 60  # 30 хв
# ===============================================

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("kniaz_bot")

# СТАНИ діалогу
PHOTO, PSEUDONYM, CREDO_LAW, FULLNAME = range(4)

# Лічильники/статистика в пам'яті процесу
STATS = {
    "started_at": datetime.now(timezone.utc),
    "total_submissions": 0,
    "active_conversations": 0,
}

WELCOME = (
    'Вітаю! Ви хочете подати свою кандидатуру на фото-конкурс '
    '"Князь і Князівна коледжу". Для участі надішліть свою роботу (фото-косплей).'
)

ASK_PSEUDONYM = (
    "Напишіть свій псевдонім з Вашою характеристикою. Наприклад: "
    "Князь-відважний, Княгиня-прегарна чи Князь-продуктивний Франко "
    "(в разі, якщо Ви втілилися в образ не князя чи князівни)."
)

ASK_CREDO_LAW = (
    "Тепер проголосіть свій постулат (кредо) і Ваш перший прийнятий закон у державі."
)

ASK_FULLNAME = "Вкажіть свії ПІП і групу."

THANKS = "Дякую! Ваша заявка прийнята. Очікуйте подальших новин)."

TIMEOUT_MSG = (
    "Минуло більше ніж 6 хв від початку оформлення заявки, діалог скинуто. "
    "Якщо хочете — почніть знову командою /start."
)

CANCEL_MSG = "Заявку скасовано. Ви можете почати знову командою /start."

HELP_MSG = "Надішліть команду /start, щоб подати заявку, або /cancel — щоб скасувати."

# --------------- УТИЛІТИ ----------------
def _now_utc() -> datetime:
    return datetime.now(timezone.utc)

def _deadline_exceeded(context: ContextTypes.DEFAULT_TYPE) -> bool:
    dl = context.user_data.get("deadline")
    return bool(dl and _now_utc() > dl)

async def _ensure_deadline_or_abort(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Повертає True, якщо все ок; False — якщо дедлайн вийшов і ми завершили діалог."""
    if _deadline_exceeded(context):
        await update.effective_chat.send_message(TIMEOUT_MSG, reply_markup=ReplyKeyboardRemove())
        STATS["active_conversations"] = max(0, STATS["active_conversations"] - 1)
        return False
    return True

async def _send_submission_to_admin(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Шле адміну підсумок заявки + фото."""
    data = context.user_data
    photo_file_id = data.get("photo_file_id")
    pseudo = data.get("pseudonym")
    credo = data.get("credo")
    law = data.get("law")
    fullname = data.get("fullname")
    user = data.get("user_mention", "—")

    summary = (
        "📨 НОВА ЗАЯВКА НА КОНКУРС «Князь і Князівна коледжу»\n\n"
        f"Від: {user}\n"
        f"Псевдонім/характеристика: {pseudo}\n"
        f"Постулат (кредо): {credo}\n"
        f"Перший закон: {law}\n"
        f"ПІП і група: {fullname}\n"
        f"Час подачі (UTC): {_now_utc().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    # Надсилаємо спочатку фото, потім зведення (або навпаки)
    if photo_file_id:
        try:
            await context.bot.send_photo(
                chat_id=ADMIN_ID,
                photo=photo_file_id,
                caption="Фото-косплей від учасника",
            )
        except Exception as e:
            logger.warning(f"Не вдалося надіслати фото адміну: {e}")

    await context.bot.send_message(chat_id=ADMIN_ID, text=summary)

# --------------- ХЕНДЛЕРИ ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    STATS["active_conversations"] += 1
    # Встановлюємо абсолютний дедлайн (6 хв від старту)
    context.user_data["deadline"] = _now_utc() + timedelta(minutes=DEADLINE_MINUTES)
    # Очищаємо попередні дані заявки
    for k in ("photo_file_id", "pseudonym", "credo", "law", "fullname"):
        context.user_data.pop(k, None)

    # Корисна позначка автора для адміна
    u = update.effective_user
    mention = f"{u.full_name} (@{u.username})" if u and u.username else (u.full_name if u else "Користувач")
    context.user_data["user_mention"] = mention

    await update.message.reply_text(WELCOME)
    return PHOTO

async def photo_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _ensure_deadline_or_abort(update, context):
        return ConversationHandler.END

    photo = None
    if update.message and update.message.photo:
        # беремо найбільше за розміром
        photo = update.message.photo[-1]
    elif update.message and update.message.document and update.message.document.mime_type.startswith("image/"):
        # якщо кинули як документ-картинку
        photo = update.message.document
    else:
        await update.message.reply_text("Будь ласка, надішліть саме фото-косплей.")
        return PHOTO

    context.user_data["photo_file_id"] = photo.file_id
    await update.message.reply_text(ASK_PSEUDONYM)
    return PSEUDONYM

async def pseudonym_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _ensure_deadline_or_abort(update, context):
        return ConversationHandler.END

    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("Будь ласка, надішліть текст із псевдонімом і характеристикою.")
        return PSEUDONYM

    context.user_data["pseudonym"] = text
    await update.message.reply_text(ASK_CREDO_LAW)
    return CREDO_LAW

async def credo_law_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _ensure_deadline_or_abort(update, context):
        return ConversationHandler.END

    text = (update.message.text or "").strip()
    if not text or len(text) < 3:
        await update.message.reply_text("Опишіть, будь ласка, Ваш постулат і перший закон одним повідомленням.")
        return CREDO_LAW

    # Спробуємо розділити "постулат" і "закон" якщо користувач написав у два речення
    # Якщо ні — покладемо все в “кредо”, а “закон” залишимо порожнім рядком.
    parts = [p.strip() for p in text.replace("\n", " ").split(".") if p.strip()]
    if len(parts) >= 2:
        context.user_data["credo"] = parts[0]
        context.user_data["law"] = ". ".join(parts[1:])
    else:
        context.user_data["credo"] = text
        context.user_data["law"] = "—"

    await update.message.reply_text(ASK_FULLNAME)
    return FULLNAME

async def fullname_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _ensure_deadline_or_abort(update, context):
        return ConversationHandler.END

    text = (update.message.text or "").strip()
    if not text or len(text) < 3:
        await update.message.reply_text("Вкажіть, будь ласка, Ваші ПІП і групу одним повідомленням.")
        return FULLNAME

    context.user_data["fullname"] = text

    # Надсилаємо адміну
    try:
        await _send_submission_to_admin(context)
        STATS["total_submissions"] += 1
    except Exception as e:
        logger.exception("Помилка під час надсилання адміну: %s", e)

    await update.message.reply_text(THANKS, reply_markup=ReplyKeyboardRemove())
    STATS["active_conversations"] = max(0, STATS["active_conversations"] - 1)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(CANCEL_MSG, reply_markup=ReplyKeyboardRemove())
    STATS["active_conversations"] = max(0, STATS["active_conversations"] - 1)
    return ConversationHandler.END

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_MSG)

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Незрозуміла команда. Спробуйте /start або /help.")

# --------- ПЕРІОДИЧНИЙ ЗВІТ (healthcheck) ----------
async def healthcheck_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    uptime = _now_utc() - STATS["started_at"]
    hours = int(uptime.total_seconds() // 3600)
    mins = int((uptime.total_seconds() % 3600) // 60)

    msg = (
        "✅ Бот працює справно.\n"
        f"Uptime: {hours} год {mins} хв\n"
        f"Активні діалоги зараз: {STATS['active_conversations']}\n"
        f"Прийнято заявок за сесію: {STATS['total_submissions']}\n"
        "Перевірка кожні 30 хв."
    )
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=msg, disable_notification=True)
    except Exception as e:
        logger.warning(f"Не вдалося надіслати healthcheck адміну: {e}")

# --------------- ПОМИЛКИ ----------------
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Виникла помилка під час обробки апдейту: %s", context.error)
    # Можна сповістити адміна стисло
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"⚠️ Помилка: {context.error}",
            disable_notification=True,
        )
    except Exception:
        pass

# --------------- MAIN ----------------
def main() -> None:
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .concurrent_updates(True)  # дозволяє паралельну обробку
        .build()
    )

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            PHOTO: [
                MessageHandler(
                    filters.PHOTO | (filters.Document.IMAGE & ~filters.Animation),
                    photo_received,
                ),
                # Якщо прислали не фото — підкажемо ще раз
                MessageHandler(filters.ALL & ~filters.COMMAND, photo_received),
            ],
            PSEUDONYM: [MessageHandler(filters.TEXT & ~filters.COMMAND, pseudonym_received)],
            CREDO_LAW: [MessageHandler(filters.TEXT & ~filters.COMMAND, credo_law_received)],
            FULLNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, fullname_received)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
        name="kniaz_conversation",
        persistent=False,
    )

    application.add_handler(conv)
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(MessageHandler(filters.COMMAND, unknown))
    application.add_error_handler(error_handler)

    # Періодичний healthcheck
    application.job_queue.run_repeating(healthcheck_job, interval=HEALTHCHECK_INTERVAL_SEC, first=60)

    logger.info("Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES, stop_signals=None, close_loop=False)

if __name__ == "__main__":
    main()
