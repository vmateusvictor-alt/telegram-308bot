import asyncio
import os
import logging
from collections import deque
from telegram import (
    Update, InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters, ConversationHandler
)

from utils.loader import get_all_sources
from utils.downloader import download_chapter
from utils.cbz import create_cbz

logging.basicConfig(level=logging.INFO)

# ===== CONFIG =====
MAX_SIMULTANEOUS_DOWNLOADS = 2
STATUS_PER_PAGE = 10
WAITING_CAP_NUMBER = 1
WAITING_ORDER = 2

# ===== FILA GLOBAL =====
download_queue = deque()
active_downloads = set()
semaphore = asyncio.Semaphore(MAX_SIMULTANEOUS_DOWNLOADS)

# ===== UTIL =====
def group_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_chat.type not in ["group", "supergroup"]:
            return
        return await func(update, context)
    return wrapper

def user_tag(user):
    return user.first_name

# ================= START =================
@group_only
async def yuki(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Yuki pronta 🌸\nUse /search nome_do_manga"
    )

# ================= SEARCH =================
@group_only
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args)
    if not query:
        return await update.message.reply_text("Digite o nome do mangá.")

    sources = await get_all_sources(query)

    if not sources:
        return await update.message.reply_text("Nenhum resultado encontrado.")

    keyboard = []
    for i, src in enumerate(sources):
        keyboard.append([
            InlineKeyboardButton(
                src["title"],
                callback_data=f"select|{update.effective_user.id}|{i}"
            )
        ])

    context.user_data["results"] = sources

    await update.message.reply_text(
        "Resultados:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================= SELECT MANGA =================
@group_only
async def select_manga(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, uid, index = query.data.split("|")
    if int(uid) != query.from_user.id:
        return

    manga = context.user_data["results"][int(index)]
    context.user_data["manga"] = manga
    context.user_data["page"] = 0

    await show_chapters(query, context)

# ================= SHOW CHAPTERS =================
async def show_chapters(query, context):
    manga = context.user_data["manga"]
    chapters = manga["chapters"]
    page = context.user_data.get("page", 0)

    per_page = 10
    start = page * per_page
    end = start + per_page
    page_chapters = chapters[start:end]

    keyboard = []

    for ch in page_chapters:
        keyboard.append([
            InlineKeyboardButton(
                f"Cap {ch['number']}",
                callback_data=f"chapter|{query.from_user.id}|{ch['number']}"
            )
        ])

    nav = []
    if start > 0:
        nav.append(InlineKeyboardButton("«", callback_data="prev"))
    if end < len(chapters):
        nav.append(InlineKeyboardButton("»", callback_data="next"))
    if nav:
        keyboard.append(nav)

    await query.edit_message_text(
        f"{manga['title']} - Página {page+1}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================= NAVIGATION =================
async def change_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "next":
        context.user_data["page"] += 1
    else:
        context.user_data["page"] -= 1

    await show_chapters(query, context)

# ================= CHAPTER OPTIONS =================
@group_only
async def chapter_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, uid, cap = query.data.split("|")
    if int(uid) != query.from_user.id:
        return

    context.user_data["selected_cap"] = int(cap)

    keyboard = [
        [InlineKeyboardButton("Baixar este", callback_data="d_one")],
        [InlineKeyboardButton("Baixar todos", callback_data="d_all")],
        [InlineKeyboardButton("Baixar até X", callback_data="d_until")]
    ]

    await query.edit_message_text(
        f"Capítulo {cap}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================= UNTIL CAP =================
async def ask_cap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("Digite o número do capítulo final:")
    return WAITING_CAP_NUMBER

async def receive_cap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["until_cap"] = int(update.message.text)
    except:
        return ConversationHandler.END

    await update.message.reply_text("Ordem?", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("Crescente", callback_data="order_c")],
        [InlineKeyboardButton("Decrescente", callback_data="order_d")]
    ]))
    return WAITING_ORDER

async def receive_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    order = "asc" if query.data == "order_c" else "desc"

    await add_to_queue(update.effective_user, context, order)
    return ConversationHandler.END

# ================= ADD TO QUEUE =================
async def add_to_queue(user, context, order="asc", mode="one"):
    manga = context.user_data["manga"]
    start = context.user_data["selected_cap"]

    if mode == "one":
        caps = [start]
    elif mode == "all":
        caps = [c["number"] for c in manga["chapters"]]
    else:
        end = context.user_data["until_cap"]
        caps = list(range(start, end+1))

    if order == "desc":
        caps.reverse()

    request = {
        "user": user,
        "manga": manga,
        "caps": caps
    }

    download_queue.append(request)

    await context.bot.send_message(
        context._chat_id,
        f"{user_tag(user)} seu download foi adicionado à fila."
    )

    asyncio.create_task(process_queue(context.bot, context._chat_id))

# ================= PROCESS QUEUE =================
async def process_queue(bot, chat_id):
    async with semaphore:
        if not download_queue:
            return

        req = download_queue.popleft()
        user = req["user"]
        manga = req["manga"]
        caps = req["caps"]

        await bot.send_message(chat_id, f"{user_tag(user)} - {manga['title']} download iniciado")

        for cap in caps:
            path = await download_chapter(manga, cap)
            cbz = await create_cbz(path)

            await bot.send_document(chat_id, cbz)

            # APAGA IMEDIATAMENTE
            try:
                os.remove(cbz)
            except:
                pass

        await bot.send_message(chat_id, f"{user_tag(user)} - {manga['title']} download concluído")

# ================= STATUS =================
@group_only
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not download_queue:
        return await update.message.reply_text("Fila vazia.")

    page = int(context.args[0]) if context.args else 1
    start = (page-1)*STATUS_PER_PAGE
    end = start + STATUS_PER_PAGE

    text = f"Fila página {page}\n"
    for i, req in enumerate(list(download_queue)[start:end], start=start+1):
        text += f"{i}. {req['user'].first_name} - {req['manga']['title']}\n"

    await update.message.reply_text(text)

# ================= MAIN =================
def main():
    app = ApplicationBuilder().token("TOKEN_AQUI").build()

    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(ask_cap, pattern="d_until")],
        states={
            WAITING_CAP_NUMBER: [MessageHandler(filters.TEXT, receive_cap)],
            WAITING_ORDER: [CallbackQueryHandler(receive_order)]
        },
        fallbacks=[]
    )

    app.add_handler(CommandHandler("Yuki", yuki))
    app.add_handler(CommandHandler("search", search))
    app.add_handler(CommandHandler("status", status))

    app.add_handler(CallbackQueryHandler(select_manga, pattern="select"))
    app.add_handler(CallbackQueryHandler(change_page, pattern="prev|next"))
    app.add_handler(CallbackQueryHandler(chapter_selected, pattern="chapter"))

    app.add_handler(conv)

    app.run_polling()

if __name__ == "__main__":
    main()
