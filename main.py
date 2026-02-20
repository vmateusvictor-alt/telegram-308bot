import asyncio
import os
import logging
from collections import deque

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters, ConversationHandler
)

from telegram.error import TelegramError, NetworkError, TimedOut

from utils.loader import get_all_sources
from utils.cbz import create_cbz
import utils.downloader as dl

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("YUKI")

TOKEN = os.getenv("BOT_TOKEN")

MAX_SIMULTANEOUS_DOWNLOADS = 2
WAITING_CAP = 1
WAITING_ORDER = 2

queue = deque()
running = set()

# ================= SAFE TELEGRAM =================
async def safe_send(bot, chat_id, text=None, file=None):
    try:
        if file:
            await bot.send_document(chat_id, file, read_timeout=120, write_timeout=120)
        else:
            await bot.send_message(chat_id, text, read_timeout=120, write_timeout=120)
    except (TelegramError, NetworkError, TimedOut) as e:
        logger.warning(f"IGNORADO TELEGRAM ERROR: {e}")
    except Exception as e:
        logger.warning(f"OUTRO ERRO: {e}")

# ================= DOWNLOAD AUTO DETECT =================
async def download_wrapper(manga, cap):
    for name in ("download_chapter", "download_cap", "download", "get_chapter"):
        fn = getattr(dl, name, None)
        if fn:
            return await fn(manga, cap)
    raise Exception("Downloader inválido")

# ================= ERROR HANDLER =================
async def error_handler(update, context):
    logger.error(f"ERRO GLOBAL: {context.error}")

# ================= GROUP ONLY =================
def group_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_chat.type not in ["group", "supergroup"]:
            return
        return await func(update, context)
    return wrapper

def uname(user):
    return user.first_name

# ================= START =================
@group_only
async def yuki(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Yuki online 🌸")

# ================= SEARCH =================
@group_only
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = " ".join(context.args)
    if not name:
        return await update.message.reply_text("Use /search nome")

    results = await get_all_sources(name)
    if not results:
        return await update.message.reply_text("Nada encontrado")

    context.user_data["results"] = results

    kb = [[InlineKeyboardButton(r["title"], callback_data=f"s|{update.effective_user.id}|{i}")]
          for i, r in enumerate(results)]

    await update.message.reply_text("Escolha:", reply_markup=InlineKeyboardMarkup(kb))

# ================= SELECT =================
async def select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    _, uid, idx = q.data.split("|")
    if int(uid) != q.from_user.id:
        return

    manga = context.user_data["results"][int(idx)]
    context.user_data["manga"] = manga

    kb = [
        [InlineKeyboardButton("Baixar este", callback_data="one")],
        [InlineKeyboardButton("Baixar todos", callback_data="all")],
        [InlineKeyboardButton("Baixar até X", callback_data="until")]
    ]

    await q.edit_message_text(manga["title"], reply_markup=InlineKeyboardMarkup(kb))

# ================= RANGE =================
async def until(update, context):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("Digite o capítulo final:")
    return WAITING_CAP

async def cap_receive(update, context):
    context.user_data["until"] = int(update.message.text)
    await update.message.reply_text(
        "Ordem?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Crescente", callback_data="asc")],
            [InlineKeyboardButton("Decrescente", callback_data="desc")]
        ])
    )
    return WAITING_ORDER

async def order_receive(update, context):
    q = update.callback_query
    await q.answer()
    await enqueue(q.from_user, q.message.chat_id, context, q.data)
    return ConversationHandler.END

# ================= QUEUE =================
async def enqueue(user, chat, context, order, mode="all"):
    manga = context.user_data["manga"]

    if mode == "one":
        caps = [manga["chapters"][0]["number"]]
    else:
        caps = [c["number"] for c in manga["chapters"]]

    if order == "desc":
        caps.reverse()

    queue.append({"user": user, "chat": chat, "manga": manga, "caps": caps})

    await safe_send(context.bot, chat, f"{uname(user)} entrou na fila")

    asyncio.create_task(process_queue(context.application))

# ================= PROCESS =================
async def process_queue(app):
    if len(running) >= MAX_SIMULTANEOUS_DOWNLOADS or not queue:
        return

    req = queue.popleft()
    task = app.create_task(run_download(app.bot, req))
    running.add(task)

    def done(_):
        running.remove(task)
        app.create_task(process_queue(app))

    task.add_done_callback(done)

# ================= DOWNLOAD =================
async def run_download(bot, req):
    user, chat, manga, caps = req.values()

    await safe_send(bot, chat, f"{uname(user)} - {manga['title']} iniciado")

    for cap in caps:
        try:
            path = await download_wrapper(manga, cap)
            cbz = await create_cbz(path)

            await safe_send(bot, chat, file=cbz)

            try:
                os.remove(cbz)
            except:
                pass

        except Exception as e:
            logger.warning(f"Erro cap {cap}: {e}")

    await safe_send(bot, chat, f"{uname(user)} - {manga['title']} concluído")

# ================= MAIN =================
def main():
    app = (
        ApplicationBuilder()
        .token(TOKEN)
        .connect_timeout(60)
        .read_timeout(60)
        .write_timeout(60)
        .pool_timeout(60)
        .build()
    )

    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(until, pattern="until")],
        states={
            WAITING_CAP: [MessageHandler(filters.TEXT & ~filters.COMMAND, cap_receive)],
            WAITING_ORDER: [CallbackQueryHandler(order_receive)]
        },
        fallbacks=[]
    )

    app.add_handler(CommandHandler("Yuki", yuki))
    app.add_handler(CommandHandler("search", search))
    app.add_handler(CallbackQueryHandler(select, pattern="^s\\|"))
    app.add_handler(conv)

    app.add_error_handler(error_handler)

    logger.info("BOT INICIANDO...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
