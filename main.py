import os
import logging
import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from utils.loader import get_all_sources
from utils.queue_manager import add_job, get_position, DownloadJob, queue
from utils.worker import worker

logging.basicConfig(level=logging.INFO)

CHAPTERS_PER_PAGE = 10


# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        return await update.message.reply_text("Use o bot no grupo.")
    await update.message.reply_text("📚 Manga Bot Online!\nUse:\n/buscar nome_do_manga")


# ================= BUSCAR =================
async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Use: /buscar nome")

    query_text = " ".join(context.args)
    sources = get_all_sources()

    buttons = []
    for source_name, source in sources.items():
        results = await source.search(query_text)
        for manga in results[:6]:
            buttons.append([
                InlineKeyboardButton(
                    f"{manga['title']} ({source_name})",
                    callback_data=f"m|{source_name}|{manga['url']}"
                )
            ])

    await update.message.reply_text(
        f"🔎 Resultados para: {query_text}",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# ================= LISTAR CAPÍTULOS =================
async def manga_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, source_name, manga_id = query.data.split("|")
    source = get_all_sources()[source_name]

    chapters = await source.chapters(manga_id)

    context.user_data["chapters"] = chapters
    context.user_data["source"] = source

    buttons = []
    for i, ch in enumerate(chapters[:20]):
        num = ch.get("chapter_number")
        buttons.append([InlineKeyboardButton(f"Cap {num}", callback_data=f"c|{i}")])

    await query.edit_message_text("📖 Escolha o capítulo:", reply_markup=InlineKeyboardMarkup(buttons))


# ================= ADICIONAR NA FILA =================
async def chapter_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, index = query.data.split("|")
    index = int(index)

    chapters = context.user_data["chapters"]
    source = context.user_data["source"]

    selected = [chapters[index]]

    job = DownloadJob(
        user_id=query.from_user.id,
        user_name=query.from_user.first_name,
        manga=selected[0].get("manga_title", "Manga"),
        chapters=selected,
        message=query.message,
        source=source
    )

    await add_job(job)

    pos = await get_position(query.from_user.id)

    if pos:
        await query.message.reply_text(
            f"🕒 {query.from_user.first_name}, seu download foi adicionado à fila.\nPosição: {pos}"
        )
    else:
        await query.message.reply_text("⏳ Preparando download...")


# ================= STATUS FILA =================
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not queue:
        return await update.message.reply_text("Fila vazia.")

    page = int(context.args[0]) if context.args else 1
    per_page = 10

    items = list(queue)
    start = (page - 1) * per_page
    end = start + per_page

    text = "📊 FILA DE DOWNLOADS\n\n"

    for i, job in enumerate(items[start:end], start=start + 1):
        text += f"{i}. {job.user_name} — {job.manga}\n"

    buttons = []
    if start > 0:
        buttons.append(InlineKeyboardButton("«", callback_data=f"status|{page-1}"))
    if end < len(items):
        buttons.append(InlineKeyboardButton("»", callback_data=f"status|{page+1}"))

    markup = InlineKeyboardMarkup([buttons]) if buttons else None
    await update.message.reply_text(text, reply_markup=markup)


# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buscar", buscar))
    app.add_handler(CommandHandler("status", status))

    app.add_handler(CallbackQueryHandler(manga_callback, pattern="^m\\|"))
    app.add_handler(CallbackQueryHandler(chapter_callback, pattern="^c\\|"))

    loop = asyncio.get_event_loop()
    loop.create_task(worker(app))
    loop.create_task(worker(app))

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
