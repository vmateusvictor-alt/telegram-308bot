import zipfile
import aiofiles
import os
import aiohttp
import asyncio

os.makedirs("tmp", exist_ok=True)

async def download_image(client, url, path):
    async with client.get(url) as r:
        r.raise_for_status()
        f = await aiofiles.open(path, mode="wb")
        await f.write(await r.read())
        await f.close()

async def create_cbz(image_urls, manga_title, chapter_name):
    manga_title_clean = manga_title.replace(" ", "_")
    chapter_name_clean = chapter_name.replace(" ", "_")
    cbz_filename = f"{manga_title_clean}_{chapter_name_clean}.cbz"
    cbz_path = os.path.join("tmp", cbz_filename)

    async with aiohttp.ClientSession() as session:
        tasks = []
        for i, url in enumerate(image_urls):
            img_path = os.path.join("tmp", f"{i}.jpg")
            tasks.append(download_image(session, url, img_path))
        await asyncio.gather(*tasks)

    # Cria o CBZ
    with zipfile.ZipFile(cbz_path, "w") as cbz:
        for i in range(len(image_urls)):
            cbz.write(os.path.join("tmp", f"{i}.jpg"), f"{i+1}.jpg")

    # Remove imagens temporárias
    for i in range(len(image_urls)):
        os.remove(os.path.join("tmp", f"{i}.jpg"))

    return cbz_path, cbz_filename
