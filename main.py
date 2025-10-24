import logging
import telegram
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

BOT_TOKEN = "ВСТАВ_СВІЙ_ТОКЕН"
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
log = logging.getLogger("kniaz-bot")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Я на зв'язку ✅ (PTB " + telegram.__version__ + ")")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Працюю. Напишіть /start")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    log.info("Запускаю run_polling… (PTB %s)", telegram.__version__)
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
