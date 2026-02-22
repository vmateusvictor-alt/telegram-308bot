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

# limita downloads simultâneos (protege RAM)
DOWNLOAD_SEMAPHORE = asyncio.Semaphore(2)


# =====================================================
# ENVIO DO CAPÍTULO (SEM SALVAR NO DISCO)
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

            # retry automático Telegram
            while True:
                try:
                    await message.reply_document(
                        document=cbz_buffer,
                        filename=cbz_name
                    )
                    break

                except RetryAfter as e:
                    wait_time = int(e.retry_after) + 2
                    print(f"FloodWait — aguardando {wait_time}s")
                    await asyncio.sleep(wait_time)

                except (TimedOut, NetworkError):
                    print("Erro de rede — tentando novamente...")
                    await asyncio.sleep(5)

        except Exception as e:
            print(f"Erro capítulo {num}:", e)

        finally:
            try:
                cbz_buffer.close()
            except:
                pass


# =====================================================
# WORKER (CÉREBRO DO BOT)
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

            # pausa anti-flood
            await asyncio.sleep(2)

        except Exception as e:
            print("Erro no worker:", e)

        remove_job()
        DOWNLOAD_QUEUE.task_done()


# =====================================================
# COMANDOS
# =====================================================
async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.args:
        return await update.message.reply_text("Use: /buscar nome_do_manga")

    query = " ".join(context.args)
    sources = get_all_sources()

    await update.message.reply_text("🔎 Procurando manga...")

    # tenta todas fontes disponíveis
    for source_name, source in sources.items():
        try:
            mangas = await source.search(query)

            if not mangas:
                continue

            manga = mangas[0]
            chapters = await source.chapters(manga["url"])

            await update.message.reply_text(
                f"📥 {len(chapters)} capítulos adicionados na fila."
            )

            for ch in chapters:
                await add_job({
                    "message": update.message,
                    "source": source,
                    "chapter": ch,
                    "meta": {
                        "title": manga["title"],
                        "chapter": ch.get("chapter_number"),
                    }
                })

            return

        except Exception as e:
            print("Fonte falhou:", e)

    await update.message.reply_text("❌ Nenhuma fonte respondeu.")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📦 Capítulos na fila: {queue_size()}"
    )


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

    # comandos
    app.add_handler(CommandHandler("buscar", buscar))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("cancelar", cancelar))

    # inicia worker corretamente
    async def startup(app):
        asyncio.create_task(download_worker())
        print("✅ Worker iniciado")

    app.post_init = startup

    print("🤖 Bot iniciado...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
