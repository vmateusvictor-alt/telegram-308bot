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

CHAPTERS_PER_PAGE = 10

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
            for manga in results[:6]:
                title = manga.get("title") or manga.get("name")
                url = manga.get("url") or manga.get("slug")
                if not url:
                    continue
                buttons.append([
                    InlineKeyboardButton(
                        f"{title} ({source_name})",
                        callback_data=f"manga|{source_name}|{url}|0"
                    )
                ])
        except Exception as e:
            print(f"Erro buscar {source_name}: {e}")
            continue

    if not buttons:
        return await update.message.reply_text("Nenhum resultado encontrado.")

    await update.message.reply_text(
        f"🔎 Resultados para: {query}",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ================= MANGA (paginação) =================
async def manga_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        _, source_name, manga_url, page_str = query.data.split("|")
        page = int(page_str)
        source = get_all_sources()[source_name]

        chapters = await source.chapters(manga_url)
        if not chapters:
            await query.message.reply_text("❌ Nenhum capítulo encontrado.")
            return

        total = len(chapters)
        start = page * CHAPTERS_PER_PAGE
        end = start + CHAPTERS_PER_PAGE
        subset = chapters[start:end]

        buttons = []
        for ch in subset:
            chap_num = ch.get("chapter_number") or ch.get("name") or "?"
            ch_url = ch.get("url") or ch.get("id")
            if not ch_url:
                continue
            buttons.append([
                InlineKeyboardButton(
                    f"{chap_num}",
                    callback_data=f"chapter|{source_name}|{ch_url}"
                )
            ])

        nav = []
        if start > 0:
            nav.append(
                InlineKeyboardButton("« Anterior", callback_data=f"manga|{source_name}|{manga_url}|{page-1}")
            )
        if end < total:
            nav.append(
                InlineKeyboardButton("Próxima »", callback_data=f"manga|{source_name}|{manga_url}|{page+1}")
            )
        if nav:
            buttons.append(nav)

        await query.edit_message_text(
            "📖 Selecione o capítulo:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    except Exception as e:
        await query.message.reply_text(f"❌ Erro ao abrir manga: {e}")
        print(f"Erro manga_callback: {e}")

# ================= CHAPTER (opções) =================
async def chapter_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        _, source_name, chapter_id = query.data.split("|")
        source = get_all_sources()[source_name]

        chapters = await source.chapters(chapter_id)
        info = next((c for c in chapters if c.get("url") == chapter_id or c.get("id") == chapter_id), None)
        if not info:
            await query.message.reply_text("❌ Capítulo não encontrado.")
            return

        chap_num = info.get("chapter_number") or info.get("name")
        manga_title = info.get("manga_title", "Manga")

        buttons = [
            [InlineKeyboardButton("📥 Baixar este", callback_data=f"download|{source_name}|{chapter_id}|single")],
            [InlineKeyboardButton("📥 Baixar deste até o fim", callback_data=f"download|{source_name}|{chapter_id}|from_here")],
            [InlineKeyboardButton("📥 Baixar até Cap X", callback_data=f"download|{source_name}|{chapter_id}|to_here")]
        ]

        await query.edit_message_text(
            f"📦 Cap {chap_num} — escolha o tipo de download:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    except Exception as e:
        await query.message.reply_text(f"❌ Erro ao abrir capítulo: {e}")
        print(f"Erro chapter_callback: {e}")

# ================= DOWNLOAD =================
async def download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        _, source_name, chapter_id, mode = query.data.split("|")
        source = get_all_sources()[source_name]

        chapters = await source.chapters(chapter_id)
        index = next((i for i, c in enumerate(chapters) if c.get('url') == chapter_id or c.get("id") == chapter_id), 0)

        # Seleção de capítulos
        if mode == "single":
            sel = [chapters[index]]
        elif mode == "from_here":
            sel = chapters[index:]
        elif mode == "to_here":
            # Pergunta ao usuário via mensagem para digitar o cap final
            await query.message.reply_text("Digite o número do capítulo final:")
            context.user_data["to_here_source"] = source_name
            context.user_data["to_here_index"] = index
            return
        else:
            sel = [chapters[index]]

        status = await query.message.reply_text(f"📦 Gerando {len(sel)} CBZ(s)...")

        for c in sel:
            cid = c.get("url") or c.get("id")
            num = c.get("chapter_number") or c.get("name")
            name = f"Cap {num}"
            manga_title = c.get("manga_title", "Manga")

            imgs = await source.pages(cid)
            if not imgs:
                await query.message.reply_text(f"❌ Cap {num} vazio")
                continue

            cbz_path, cbz_name = await create_cbz(imgs, manga_title, name)
            await query.message.reply_document(
                document=open(cbz_path, "rb"),
                filename=cbz_name
            )
            os.remove(cbz_path)

        await status.delete()

    except Exception as e:
        await query.message.reply_text(f"❌ Erro no download: {e}")
        print(f"Erro download_callback: {e}")

# ================= HANDLE USER INPUT (para to_here) =================
async def text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "to_here_source" not in context.user_data:
        return
    try:
        final_cap = int(update.message.text)
        source_name = context.user_data.pop("to_here_source")
        start_index = context.user_data.pop("to_here_index")
        source = get_all_sources()[source_name]

        chapters = await source.chapters(None)  # pega todos os capítulos do manga atual
        sel = chapters[:final_cap]

        status = await update.message.reply_text(f"📦 Gerando {len(sel)} CBZ(s)...")

        for c in sel:
            cid = c.get("url") or c.get("id")
            num = c.get("chapter_number") or c.get("name")
            name = f"Cap {num}"
            manga_title = c.get("manga_title", "Manga")

            imgs = await source.pages(cid)
            if not imgs:
                await update.message.reply_text(f"❌ Cap {num} vazio")
                continue

            cbz_path, cbz_name = await create_cbz(imgs, manga_title, name)
            await update.message.reply_document(
                document=open(cbz_path, "rb"),
                filename=cbz_name
            )
            os.remove(cbz_path)

        await status.delete()
    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao processar capítulo final: {e}")
        print(f"Erro text_input: {e}")

# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buscar", buscar))
    app.add_handler(CallbackQueryHandler(manga_callback, pattern="^manga"))
    app.add_handler(CallbackQueryHandler(chapter_callback, pattern="^chapter"))
    app.add_handler(CallbackQueryHandler(download_callback, pattern="^download"))
    app.add_handler(CommandHandler("cancel", lambda u, c: u.message.reply_text("✅ Cancelado")))
    app.add_handler(CommandHandler("help", lambda u, c: u.message.reply_text("Use /buscar nome_do_manga")))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buscar", buscar))
    app.add_handler(CallbackQueryHandler(manga_callback, pattern="^manga"))
    app.add_handler(CallbackQueryHandler(chapter_callback, pattern="^chapter"))
    app.add_handler(CallbackQueryHandler(download_callback, pattern="^download"))
    app.add_handler(CommandHandler("cancel", lambda u, c: u.message.reply_text("✅ Cancelado")))
    app.add_handler(CommandHandler("help", lambda u, c: u.message.reply_text("Use /buscar nome_do_manga")))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buscar", buscar))
    app.add_handler(CallbackQueryHandler(manga_callback, pattern="^manga"))
    app.add_handler(CallbackQueryHandler(chapter_callback, pattern="^chapter"))
    app.add_handler(CallbackQueryHandler(download_callback, pattern="^download"))
    app.add_handler(CommandHandler("cancel", lambda u, c: u.message.reply_text("✅ Cancelado")))
    app.add_handler(CommandHandler("help", lambda u, c: u.message.reply_text("Use /buscar nome_do_manga")))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buscar", buscar))
    app.add_handler(CallbackQueryHandler(manga_callback, pattern="^manga"))
    app.add_handler(CallbackQueryHandler(chapter_callback, pattern="^chapter"))
    app.add_handler(CallbackQueryHandler(download_callback, pattern="^download"))
    app.add_handler(CommandHandler("cancel", lambda u, c: u.message.reply_text("✅ Cancelado")))
    app.add_handler(CommandHandler("help", lambda u, c: u.message.reply_text("Use /buscar nome_do_manga")))

    # Texto de input para "baixar até Cap X"
    app.add_handler(CommandHandler("input", text_input))
    app.add_handler(CommandHandler("text", text_input))
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
