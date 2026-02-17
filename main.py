import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from utils.loader import get_all_sources
from utils.cbz import create_cbz

logging.basicConfig(level=logging.INFO)

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📚 Manga Bot Online!\nUse: /buscar nome_do_manga"
    )

# ================= BUSCAR =================
async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Use: /buscar nome")

    query = " ".join(context.args)
    sources = get_all_sources()

    buttons = []

    for source_name, source in sources.items():
        try:
            results = await source.search(query)

            for manga in results[:3]:
                title = manga.get("title") or manga.get("name")
                url = manga.get("url") or manga.get("slug")

                # salva apenas dados essenciais
                callback_id = f"manga|{source_name}|{url}"
                buttons.append([InlineKeyboardButton(f"{title} ({source_name})", callback_data=callback_id)])

        except Exception:
            continue

    if not buttons:
        return await update.message.reply_text("Nenhum resultado encontrado.")

    await update.message.reply_text(
        f"Resultados para: {query}",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ================= MANGA =================
async def manga_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, source_name, manga_url = query.data.split("|", 2)
    source = get_all_sources()[source_name]

    try:
        chapters = await source.chapters(manga_url)
    except Exception:
        return await query.message.reply_text("Erro ao carregar capítulos.")

    buttons = []

    # cria botões seguros
    for ch in chapters[:15]:
        ch_id = ch.get("url") or ch.get("id")
        buttons.append([
            InlineKeyboardButton(
                ch.get("name"),
                callback_data=f"chapter|{source_name}|{ch_id}"
            )
        ])

    await query.edit_message_text(
        "Selecione o capítulo:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ================= CHAPTER =================
async def chapter_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, source_name, chapter_id = query.data.split("|", 2)
    source = get_all_sources()[source_name]

    status = await query.message.reply_text("📦 Gerando CBZ...")

    # pega imagens
    try:
        images = await source.pages(chapter_id)
    except Exception:
        return await status.edit_text("Erro ao carregar capítulo.")

    if not images:
        return await status.edit_text("Capítulo vazio.")

    # nome seguro
    manga_title = getattr(source, "last_manga_title", "Manga")
    chapter_name = getattr(source, "last_chapter_name", "Capítulo")

    # gera CBZ
    cbz_path, cbz_name = await create_cbz(images, manga_title, chapter_name)

    await query.message.reply_document(
        document=open(cbz_path, "rb"),
        filename=cbz_name
    )

    os.remove(cbz_path)
    await status.delete()

# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buscar", buscar))
    app.add_handler(CallbackQueryHandler(manga_callback, pattern="^manga"))
    app.add_handler(CallbackQueryHandler(chapter_callback, pattern="^chapter"))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
