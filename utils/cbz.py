import os
import zipfile
import httpx
import asyncio

os.makedirs("tmp", exist_ok=True)


async def download_image(client, url):
    try:
        r = await client.get(url, timeout=60)
        r.raise_for_status()
        return r.content
    except Exception as e:
        print(f"Erro ao baixar imagem: {e}")
        return None


async def create_volume_cbz(source, chapters, manga_title, volume_name):
    safe_title = manga_title.replace("/", "").replace(" ", "_")
    safe_volume = volume_name.replace("/", "").replace(" ", "_")

    cbz_filename = f"{safe_title}_{safe_volume}.cbz"
    cbz_path = os.path.join("tmp", cbz_filename)

    semaphore = asyncio.Semaphore(10)

    async with httpx.AsyncClient(timeout=60) as client:
        with zipfile.ZipFile(cbz_path, "w", compression=zipfile.ZIP_DEFLATED) as cbz:
            page_counter = 1

            for chapter in chapters:
                pages = await source.pages(chapter.get("url"))

                async def limited_download(url):
                    async with semaphore:
                        return await download_image(client, url)

                tasks = [limited_download(url) for url in pages]
                images = await asyncio.gather(*tasks)

                for img in images:
                    if img:
                        cbz.writestr(f"{page_counter}.jpg", img)
                        page_counter += 1

    if not os.path.exists(cbz_path):
        raise Exception("Erro ao criar volume")

    return cbz_path, cbz_filename
