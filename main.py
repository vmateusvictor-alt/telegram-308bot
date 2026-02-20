import asyncio
import os
import logging
from collections import deque
from inspect import iscoroutinefunction

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters, ConversationHandler
)
from telegram.error import TelegramError

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

# ================= SAFE SEND =================
async def safe_send(bot, chat_id, text=None, file=None):
    try:
        if file:
            await bot.send_document(chat_id, file)
        else:
            await bot.send_message(chat_id, text)
    except TelegramError as e:
        logger.warning(f"Telegram erro ignorado: {e}")

# ================= DOWNLOAD WRAPPER =================
async def download_wrapper(source, chapter):
    for name in ("download_chapter", "download_cap", "download", "get_chapter"):
        fn = getattr(dl, name, None)
        if fn:
            if iscoroutinefunction(fn):
                return await fn(source, chapter)
            return await asyncio.to_thread(fn, source, chapter)
    raise Exception("Função de download não encontrada")

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
    await update.message.reply_text("Yuki pronta 🌸 Use /search nome_do_manga")

# ================= SEARCH =================
@group_only
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = " ".join(context.args)
    if not name:
        return await update.message.reply_text("Use /search nome_do_manga")

    msg = await update.message.reply_text("🔎 Procurando...")

    sources = get_all_sources()
    results = []

    for source_name, source in sources.items():
        try:
            # SEARCH
            if iscoroutinefunction(source.search):
                mangas = await source.search(name)
            else:
                mangas = await asyncio.to_thread(source.search, name)

            for manga in mangas:
                try:
                    # CHAPTERS
                    if iscoroutinefunction(source.chapters):
                        chapters = await source.chapters(manga["url"])
                    else:
                        chapters = await asyncio.to_thread(source.chapters, manga["url"])

                    manga["chapters"] = chapters
                    manga["source"] = source
                    results.append(manga)

                except Exception as e:
                    logger.warning(f"Erro capítulos {source_name}: {e}")

        except Exception as e:
            logger.warning(f"Erro busca {source_name}: {e}")

    if not results:
        return await msg.edit_text("❌ Nenhum resultado encontrado")

    context.user_data["results"] = results

    kb = []
    for i, r in enumerate(results[:20]):
        kb.append([
            InlineKeyboardButton(
                r["title"],
                callback_data=f"s|{update.effective_user.id}|{i}"
            )
        ])

    await msg.edit_text(
        f"Resultados encontrados: {len(results)}",
        reply_markup=InlineKeyboardMarkup(kb)
    )

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
async def enqueue(user, chat, context, order):
    manga = context.user_data["manga"]
    source = manga["source"]

    caps = manga["chapters"]

    if "until" in context.user_data:
        end = context.user_data["until"]
        caps = [c for c in caps if int(c.get("chapter_number", 0)) <= end]

    if order == "desc":
        caps = list(reversed(caps))

    queue.append({
        "user": user,
        "chat": chat,
        "manga": manga,
        "caps": caps,
        "source": source
    })

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
    user = req["user"]
    chat = req["chat"]
    manga = req["manga"]
    source = req["source"]
    caps = req["caps"]

    await safe_send(bot, chat, f"{uname(user)} - {manga['title']} iniciado")

    for cap in caps:
        try:
            path = await download_wrapper(source, cap)
            cbz = await asyncio.to_thread(create_cbz, path)

            await safe_send(bot, chat, file=cbz)

            try:
                os.remove(cbz)
            except:
                pass

        except Exception as e:
            logger.warning(f"Erro capítulo: {e}")

    await safe_send(bot, chat, f"{uname(user)} - {manga['title']} concluído")

# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

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

    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
