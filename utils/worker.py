import asyncio
import os
from utils.queue_manager import next_job, finish_job
from utils.cbz import create_cbz


async def worker(app):
    while True:
        job = await next_job()

        if not job:
            await asyncio.sleep(2)
            continue

        try:
            await job.message.reply_text(
                f"📥 {job.user_name} solicitou \"{job.manga}\"\nDownload iniciado..."
            )

            for chapter in job.chapters:
                imgs = await job.source.pages(chapter["url"])
                if not imgs:
                    continue

                cbz_path, cbz_name = await create_cbz(
                    imgs,
                    chapter.get("manga_title", "Manga"),
                    f"Cap_{chapter.get('chapter_number')}"
                )

                await job.message.reply_document(
                    document=open(cbz_path, "rb"),
                    filename=cbz_name
                )

                # remove do Railway imediatamente
                os.remove(cbz_path)

            await job.message.reply_text(
                f"✅ {job.user_name} \"{job.manga}\" download concluído!"
            )

        finally:
            await finish_job(job.user_id)
