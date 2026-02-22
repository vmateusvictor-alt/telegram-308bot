import os
import asyncio
import logging

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

from telegram.error import RetryAfter, TimedOut, NetworkError

from utils.loader import get_all_sources
from utils.cbz import create_cbz
from utils.queue_manager import (
    DOWNLOAD_QUEUE,
    add_job,
    remove_job,
    queue_size,
)

logging.basicConfig(level=logging.INFO)

DOWNLOAD_SEMAPHORE = asyncio.Semaphore(2)


# =====================================================
# ENVIO DO CAPÍTULO
# =====================================================
async def send_chapter(message, source, chapter):

    async with DOWNLOAD_SEMAPHORE:

        cid = chapter.get("url")
        num = chapter.get("chapter_number")
        manga_title = chapter.get("manga_title", "Manga")

        try:
            imgs = await source.pages(cid)
            if not imgs:
                return

            cbz_buffer, cbz_name = await create_cbz(
                imgs,
                manga_title,
                f"Cap_{num}"
            )

            while True:
                try:
                    await message.reply_document(
                        document=cbz_buffer,
                        filename=cbz_name
                    )
                    break

                except RetryAfter as e:
                    wait_time = int(e.retry_after) + 2
                    await asyncio.sleep(wait_time)

                except (TimedOut, NetworkError):
                    await asyncio.sleep(5)

        except Exception as e:
            print(f"Erro capítulo {num}:", e)

        finally:
            try:
                cbz_buffer.close()
            except:
                pass


# =====================================================
# WORKER
# =====================================================
async def download_worker():

    print("✅ Worker Elite iniciado")

    while True:
        job = await DOWNLOAD_QUEUE.get()

        try:
            await send_chapter(
                job["message"],
                job["source"],
                job["chapter"],
            )

            await asyncio.sleep(2)

        except Exception as e:
            print("Erro no worker:", e)

        remove_job()
        DOWNLOAD_QUEUE.task_done()


# =====================================================
# BUSCAR
# =====================================================
async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.args:
        return await update.message.reply_text(
            "Use: /buscar nome_do_manga"
        )

    query_text = " ".join(context.args)
    sources = get_all_sources()

    await update.message.reply_text(f"🔎 Buscando «{query_text}»")

    for source_name, source in sources.items():
        try:
            results = await source.search(query_text)

            if not results:
                continue

            manga = results[0]

            title = manga.get("title")
            url = manga.get("url")
            cover = manga.get("cover")
            status = manga.get("status", "Desconhecido")
            genres = manga.get("genres", "Não informado")
            synopsis = manga.get("synopsis", "Sem descrição.")

            chapters = await source.chapters(url)

            if not chapters:
                return await update.message.reply_text(
                    "❌ Nenhum capítulo encontrado."
                )

            context.user_data["chapters"] = chapters
            context.user_data["source"] = source
            context.user_data["title"] = title

            caption = f"""📚 «{title}»

Status » {status}
Gênero: {genres}

Sinopse:
{synopsis}

🔗 @animesmangas308"""

            if cover:
                await update.message.reply_photo(
                    photo=cover,
                    caption=caption
                )
            else:
                await update.message.reply_text(caption)

            return await update.message.reply_text(
                """Escolha uma opção:

/baixareste
/baixartodos
/baixarate NUMERO"""
            )

        except Exception as e:
            print(f"Erro na fonte {source_name}:", e)

    await update.message.reply_text("❌ Nenhum resultado encontrado.")


# =====================================================
# BAIXAR ESTE
# =====================================================
async def baixar_este(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chapters = context.user_data.get("chapters")
    source = context.user_data.get("source")

    if not chapters:
        return await update.message.reply_text("❌ Nenhum manga carregado.")

    chapter = chapters[0]

    await add_job({
        "message": update.message,
        "source": source,
        "chapter": chapter,
    })

    await update.message.reply_text("✅ «Baixar este» adicionado na fila.")


# =====================================================
# BAIXAR TODOS
# =====================================================
async def baixar_todos(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chapters = context.user_data.get("chapters")
    source = context.user_data.get("source")

    if not chapters:
        return await update.message.reply_text("❌ Nenhum manga carregado.")

    for ch in chapters:
        await add_job({
            "message": update.message,
            "source": source,
            "chapter": ch,
        })

    await update.message.reply_text("✅ «Baixar todos» adicionados na fila.")


# =====================================================
# BAIXAR ATÉ
# =====================================================
async def baixar_ate(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.args:
        return await update.message.reply_text(
            "Use: /baixarate NUMERO"
        )

    try:
        limite = float(context.args[0])
    except:
        return await update.message.reply_text("Número inválido.")

    chapters = context.user_data.get("chapters")
    source = context.user_data.get("source")

    if not chapters:
        return await update.message.reply_text("❌ Nenhum manga carregado.")

    adicionados = 0

    for ch in chapters:
        try:
            num = float(ch.get("chapter_number", 0))
        except:
            continue

        if num <= limite:
            await add_job({
                "message": update.message,
                "source": source,
                "chapter": ch,
            })
            adicionados += 1

    await update.message.reply_text(
        f"✅ «Baixar até {limite}» adicionou {adicionados} capítulos."
    )


# =====================================================
# STATUS
# =====================================================
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📦 Capítulos na fila: {queue_size()}"
    )


# =====================================================
# CANCELAR
# =====================================================
async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):

    while not DOWNLOAD_QUEUE.empty():
        try:
            DOWNLOAD_QUEUE.get_nowait()
            DOWNLOAD_QUEUE.task_done()
        except:
            break

    await update.message.reply_text("❌ Downloads cancelados.")


# =====================================================
# MAIN
# =====================================================
def main():

    app = ApplicationBuilder().token(
        os.getenv("BOT_TOKEN")
    ).build()

    app.add_handler(CommandHandler("buscar", buscar))
    app.add_handler(CommandHandler("baixareste", baixar_este))
    app.add_handler(CommandHandler("baixartodos", baixar_todos))
    app.add_handler(CommandHandler("baixarate", baixar_ate))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("cancelar", cancelar))

    async def startup(app):
        asyncio.create_task(download_worker())
        print("✅ Worker iniciado")

    app.post_init = startup

    print("🤖 Bot iniciado...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
