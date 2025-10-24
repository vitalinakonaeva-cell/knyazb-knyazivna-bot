# ---- БОТ "Князь і Князівна коледжу" ----
# Працює на python-telegram-bot v20.8
# Автор: твій помічник ❤️

import logging
from datetime import datetime, timedelta, timezone
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters
)

# === 🔹 НАЛАШТУВАННЯ ===
BOT_TOKEN = "8228312942:AAH9W6pWWwC7IVAB_31BAdns3Cnc9k5potU"     # встав токен із BotFather
ADMIN_ID = 1491698235                   # свій Telegram ID
DEADLINE_MINUTES = 6                    # час подання заявки
# =========================

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("kniaz_knyazivna")

# СТАНИ діалогу
PHOTO, PSEUDONYM, CREDO_LAW, FULLNAME = range(4)

# Тексти
WELCOME = (
    "👑 Вітаю! Ви хочете подати свою кандидатуру на фото-конкурс "
    "«Князь і Князівна коледжу».\n\n📸 Для участі надішліть своє фото-косплей "
    "на історичну українську постать."
)
ASK_PSEUDONYM = (
    "✨ Напишіть свій псевдонім з характеристикою. Наприклад:\n"
    "Князь-відважний, Княгиня-прегарна або Князь-продуктивний Франко."
)
ASK_CREDO_LAW = (
    "📜 Тепер проголосіть свій постулат (кредо) і перший прийнятий закон у вашій державі."
)
ASK_FULLNAME = "🪪 Вкажіть свої ПІБ і групу."
THANKS = "✅ Дякую! Ваша заявка прийнята. Очікуйте подальших новин!"
TIMEOUT_MSG = (
    "⏰ Минуло понад 6 хв від початку оформлення заявки, діалог скинуто.\n"
    "Щоб почати знову — введіть /start."
)
CANCEL_MSG = "❌ Заявку скасовано. Ви можете почати знову командою /start."


def now_utc():
    return datetime.now(timezone.utc)


def deadline_passed(context: ContextTypes.DEFAULT_TYPE) -> bool:
    limit = context.user_data.get("deadline")
    return bool(limit and now_utc() > limit)


async def check_time_or_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if deadline_passed(context):
        await update.effective_chat.send_message(TIMEOUT_MSG, reply_markup=ReplyKeyboardRemove())
        return False
    return True


async def send_to_admin(context: ContextTypes.DEFAULT_TYPE):
    """Надсилає заявку адміну"""
    d = context.user_data
    caption = (
        "📩 *НОВА ЗАЯВКА НА КОНКУРС*\n"
        "«Князь і Князівна коледжу» 👑\n\n"
        f"👤 Від: {d.get('user_name', '-')}\n"
        f"🏰 Псевдонім: {d.get('pseudonym', '-')}\n"
        f"📜 Кредо: {d.get('credo', '-')}\n"
        f"⚖️ Закон: {d.get('law', '-')}\n"
        f"🪪 ПІБ і група: {d.get('fullname', '-')}\n"
        f"🕓 Час (UTC): {now_utc().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    try:
        if d.get("photo_id"):
            await context.bot.send_photo(ADMIN_ID, d["photo_id"], caption=caption, parse_mode="Markdown")
        else:
            await context.bot.send_message(ADMIN_ID, caption, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Не вдалося надіслати адміну: {e}")


# ======== ЕТАПИ ДІАЛОГУ ========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["deadline"] = now_utc() + timedelta(minutes=DEADLINE_MINUTES)
    user = update.effective_user
    context.user_data["user_name"] = f"{user.full_name} (@{user.username})" if user.username else user.full_name
    await update.message.reply_text(WELCOME)
    return PHOTO


async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await check_time_or_stop(update, context):
        return ConversationHandler.END
    if update.message.photo:
        context.user_data["photo_id"] = update.message.photo[-1].file_id
        await update.message.reply_text(ASK_PSEUDONYM)
        return PSEUDONYM
    else:
        await update.message.reply_text("Надішліть, будь ласка, фото-косплей 📸.")
        return PHOTO


async def get_pseudonym(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await check_time_or_stop(update, context):
        return ConversationHandler.END
    context.user_data["pseudonym"] = update.message.text.strip()
    await update.message.reply_text(ASK_CREDO_LAW)
    return CREDO_LAW


async def get_credo_law(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await check_time_or_stop(update, context):
        return ConversationHandler.END
    context.user_data["credo"] = update.message.text.strip()
    context.user_data["law"] = "—"
    await update.message.reply_text(ASK_FULLNAME)
    return FULLNAME


async def get_fullname(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await check_time_or_stop(update, context):
        return ConversationHandler.END
    context.user_data["fullname"] = update.message.text.strip()
    await update.message.reply_text(THANKS)
    await send_to_admin(context)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(CANCEL_MSG, reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


# ======== ГОЛОВНА ФУНКЦІЯ ========
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            PHOTO: [MessageHandler(filters.PHOTO, get_photo)],
            PSEUDONYM: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_pseudonym)],
            CREDO_LAW: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_credo_law)],
            FULLNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_fullname)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        conversation_timeout=DEADLINE_MINUTES * 60,
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("cancel", cancel))

    logger.info("🤖 Бот запущено і готовий приймати заявки!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
