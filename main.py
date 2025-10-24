# ---- БОТ "Князь і Князівна коледжу" (PTB 21.x) ----
import logging
from datetime import datetime, timedelta, timezone
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    Application, ApplicationBuilder,
    CommandHandler, MessageHandler, ConversationHandler,
    ContextTypes, filters
)

# === НАЛАШТУВАННЯ ===
BOT_TOKEN = "8228312942:AAH9W6pWWwC7IVAB_31BAdns3Cnc9k5potU"
ADMIN_ID = 1491698235         # твій Telegram ID (@userinfobot)
DEADLINE_MINUTES = 6
# =====================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
log = logging.getLogger("knyaz-knyazivna")

PHOTO, PSEUDONYM, CREDO_LAW, FULLNAME = range(4)

WELCOME = (
    "👑 Вітаю! Ви хочете подати свою кандидатуру на фото-конкурс "
    "«Князь і Князівна коледжу».\n\n📸 Надішліть фото-косплей на історичну українську постать."
)
ASK_PSEUDONYM = (
    "✨ Напишіть свій псевдонім з характеристикою. Напр.: "
    "Князь-відважний, Княгиня-прегарна або Князь-продуктивний Франко."
)
ASK_CREDO_LAW = "📜 Проголосіть свій постулат (кредо) і перший прийнятий закон у вашій державі."
ASK_FULLNAME = "🪪 Вкажіть свої ПІБ і групу."
THANKS = "✅ Дякую! Ваша заявка прийнята. Очікуйте подальших новин!"
TIMEOUT_MSG = (
    "⏰ Минуло понад 6 хв від початку оформлення заявки, діалог скинуто. "
    "Щоб почати знову — введіть /start."
)
CANCEL_MSG = "❌ Заявку скасовано. Ви можете почати знову командою /start."

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def deadline_passed(context: ContextTypes.DEFAULT_TYPE) -> bool:
    limit = context.user_data.get("deadline")
    return bool(limit and now_utc() > limit)

async def ensure_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if deadline_passed(context):
        await update.effective_chat.send_message(TIMEOUT_MSG, reply_markup=ReplyKeyboardRemove())
        return False
    return True

async def send_to_admin(context: ContextTypes.DEFAULT_TYPE):
    d = context.user_data
    caption = (
        "📩 *НОВА ЗАЯВКА НА КОНКУРС* «Князь і Князівна коледжу»\n\n"
        f"👤 Від: {d.get('user_name','-')}\n"
        f"🏰 Псевдонім: {d.get('pseudonym','-')}\n"
        f"📜 Кредо: {d.get('credo','-')}\n"
        f"⚖️ Закон: {d.get('law','-')}\n"
        f"🪪 ПІБ і група: {d.get('fullname','-')}\n"
        f"🕓 Час (UTC): {now_utc().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    try:
        if d.get("photo_id"):
            await context.bot.send_photo(ADMIN_ID, d["photo_id"], caption=caption, parse_mode="Markdown")
        else:
            await context.bot.send_message(ADMIN_ID, caption, parse_mode="Markdown")
    except Exception as e:
        log.error("Не вдалося надіслати адміну: %s", e)

# ==== ХЕНДЛЕРИ ДІАЛОГУ ====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["deadline"] = now_utc() + timedelta(minutes=DEADLINE_MINUTES)
    u = update.effective_user
    context.user_data["user_name"] = f"{u.full_name} (@{u.username})" if u.username else u.full_name
    await update.message.reply_text(WELCOME)
    return PHOTO

async def photo_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await ensure_time(update, context):
        return ConversationHandler.END
    if update.message.photo:
        context.user_data["photo_id"] = update.message.photo[-1].file_id
        await update.message.reply_text(ASK_PSEUDONYM)
        return PSEUDONYM
    await update.message.reply_text("Надішліть, будь ласка, саме фото 📸.")
    return PHOTO

async def pseudonym_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await ensure_time(update, context):
        return ConversationHandler.END
    context.user_data["pseudonym"] = (update.message.text or "").strip()
    await update.message.reply_text(ASK_CREDO_LAW)
    return CREDO_LAW

async def credo_law_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await ensure_time(update, context):
        return ConversationHandler.END
    # користувач міг написати і кредо, і закон в одному повідомленні — збережемо все у "credo"
    context.user_data["credo"] = (update.message.text or "").strip()
    context.user_data["law"] = "—"
    await update.message.reply_text(ASK_FULLNAME)
    return FULLNAME

async def fullname_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await ensure_time(update, context):
        return ConversationHandler.END
    context.user_data["fullname"] = (update.message.text or "").strip()
    await update.message.reply_text(THANKS)
    await send_to_admin(context)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(CANCEL_MSG, reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# ==== ЗАПУСК ====
def main():
    app: Application = ApplicationBuilder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            PHOTO: [MessageHandler(filters.PHOTO, photo_received)],
            PSEUDONYM: [MessageHandler(filters.TEXT & ~filters.COMMAND, pseudonym_received)],
            CREDO_LAW: [MessageHandler(filters.TEXT & ~filters.COMMAND, credo_law_received)],
            FULLNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, fullname_received)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        conversation_timeout=DEADLINE_MINUTES * 60,
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("cancel", cancel))

    log.info("🤖 Бот запущено (PTB 21.x).")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
