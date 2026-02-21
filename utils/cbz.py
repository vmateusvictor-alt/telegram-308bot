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

async def create_cbz(image_urls, manga_title, chapter_name):
    safe_title = manga_title.replace("/", "").replace(" ", "_")
    safe_chapter = str(chapter_name).replace("/", "").replace(" ", "_")

    cbz_filename = f"{safe_title}_{safe_chapter}.cbz"
    cbz_path = os.path.join("tmp", cbz_filename)

    async with httpx.AsyncClient() as client:
        tasks = [download_image(client, url) for url in image_urls]
        images = await asyncio.gather(*tasks)

    images = [img for img in images if img]

    if not images:
        raise Exception("Nenhuma imagem foi baixada")

    with zipfile.ZipFile(cbz_path, "w") as cbz:
        for i, img_bytes in enumerate(images):
            cbz.writestr(f"{i+1}.jpg", img_bytes)

    return cbz_path, cbz_filename
