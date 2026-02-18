import os
import logging
import traceback
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Chat
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from sources import get_all_sources
from utils.cbz import create_cbz

logging.basicConfig(level=logging.INFO)

# ================= CONFIG =================
CHAPTERS_PER_PAGE = 10
sources = get_all_sources()


# ================= ERROR HANDLER =================
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logging.error("========== ERRO GLOBAL ==========")
    traceback.print_exception(None, context.error, context.error.__traceback__)
    logging.error("==================================")


# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📚 Olá! Sou Yuki, bot de download de mangás!\n\n"
        "Use:\n/buscar nome_do_manga"
    )


# ================= BUSCAR =================
async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Use: /buscar nome_do_manga")

    query = " ".join(context.args)
    results = []

    # Busca em todas as fontes
    for name, source in sources.items():
        try:
            mangas = await source.search(query)
            for m in mangas:
                results.append({
                    "title": f"[{name}] {m['title']}",
                    "url": m["url"],
                    "source": name
                })
        except Exception as e:
            logging.warning(f"Erro ao buscar na fonte {name}: {e}")

    if not results:
        return await update.message.reply_text("❌ Nenhum resultado encontrado.")

    buttons = [
        [InlineKeyboardButton(m["title"], callback_data=f"m|{m['source']}|{m['url']}|0")]
        for m in results[:10]
    ]

    await update.message.reply_text(
        f"🔎 Resultados para: {query}",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# ================= LISTA CAPÍTULOS =================
async def manga_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, source_name, slug, page_str = query.data.split("|")
    page = int(page_str)
    source = sources[source_name]

    chapters = await source.chapters(slug)
    context.user_data["chapters"] = chapters
    context.user_data["slug"] = slug
    context.user_data["source_name"] = source_name

    total = len(chapters)
    start = page * CHAPTERS_PER_PAGE
    end = start + CHAPTERS_PER_PAGE
    subset = chapters[start:end]

    buttons = [
        [InlineKeyboardButton(f"Cap {ch.get('chapter_number') or '?'}", callback_data=f"c|{i}")]
        for i, ch in enumerate(subset, start=start)
    ]

    # Navegação
    nav = []
    if start > 0:
        nav.append(InlineKeyboardButton("«", callback_data=f"m|{source_name}|{slug}|{page-1}"))
    if end < total:
        nav.append(InlineKeyboardButton("»", callback_data=f"m|{source_name}|{slug}|{page+1}"))
    if nav:
        buttons.append(nav)

    await query.edit_message_text(
        "📖 Selecione o capítulo:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# ================= OPÇÕES DE DOWNLOAD =================
async def chapter_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, index_str = query.data.split("|")
    index = int(index_str)

    context.user_data["selected_index"] = index

    buttons = [
        [InlineKeyboardButton("📥 Baixar este", callback_data="d|single")],
        [InlineKeyboardButton("📥 Baixar deste até o fim", callback_data="d|from")],
        [InlineKeyboardButton("📥 Baixar até aqui", callback_data="d|to")],
        [InlineKeyboardButton("📥 Baixar até Cap X", callback_data="d|toX")]
    ]

    await query.edit_message_text(
        "Escolha o tipo de download:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# ================= DOWNLOAD =================
async def download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if "chapters" not in context.user_data or "selected_index" not in context.user_data:
        await query.message.reply_text("❌ Sessão expirada. Busque novamente.")
        return

    _, mode = query.data.split("|")
    chapters = context.user_data["chapters"]
    index = context.user_data["selected_index"]
    source_name = context.user_data.get("source_name")
    source = sources[source_name]

    # Define capítulos selecionados
    if mode == "single":
        selected = [chapters[index]]
    elif mode == "from":
        selected = chapters[index:]
    elif mode == "to":
        selected = chapters[:index+1]
    elif mode == "toX":
        # Pede que o usuário digite o número do capítulo final
        await query.message.reply_text("Digite o número do capítulo final:")
        context.user_data["awaiting_cap_x"] = True
        return
    else:
        selected = [chapters[index]]

    await process_chapters(query, selected, source)


# ================= PROCESSAR CAPÍTULOS =================
async def process_chapters(query, selected_chapters, source):
    status = await query.message.reply_text(f"📦 Gerando {len(selected_chapters)} capítulo(s)...")

    for chapter in selected_chapters:
        try:
            imgs = await source.pages(chapter["url"])
            if not imgs:
                await query.message.reply_text(f"❌ Cap {chapter.get('chapter_number')} vazio ou bloqueado.")
                continue

            cbz_path, cbz_name = await create_cbz(
                imgs,
                chapter["manga_title"],
                f"Cap {chapter.get('chapter_number')}"
            )

            await query.message.reply_document(
                document=open(cbz_path, "rb"),
                filename=cbz_name
            )

            os.remove(cbz_path)
        except Exception as e:
            await query.message.reply_text(f"❌ Erro ao gerar Cap {chapter.get('chapter_number')}: {e}")

    await status.delete()


# ================= MENSAGEM PARA CAP X =================
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting_cap_x"):
        text = update.message.text
        context.user_data["awaiting_cap_x"] = False

        try:
            cap_x = int(text)
        except ValueError:
            return await update.message.reply_text("❌ Número inválido.")

        chapters = context.user_data["chapters"]
        selected = [ch for ch in chapters if (ch.get("chapter_number") or 0) <= cap_x]
        source_name = context.user_data.get("source_name")
        source = sources[source_name]
        query = update.message
        await process_chapters(query, selected, source)


# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buscar", buscar))
    app.add_handler(CallbackQueryHandler(manga_callback, pattern="^m\\|"))
    app.add_handler(CallbackQueryHandler(chapter_callback, pattern="^c\\|"))
    app.add_handler(CallbackQueryHandler(download_callback, pattern="^d\\|"))
    app.add_handler(MessageHandler(filters=None, callback=message_handler))  # Para cap X

    app.add_error_handler(error_handler)

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
