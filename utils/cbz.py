import zipfile
import os
import time
from utils.downloader import download_images

async def create_cbz(image_urls, manga_title, chapter_name):
    """
    image_urls: lista de URLs de imagens
    manga_title: nome do mangá
    chapter_name: capítulo (ex: Cap 5)
    """

    # Baixa todas as imagens de forma assíncrona
    images_data = await download_images(image_urls)
    if not images_data:
        raise ValueError("Nenhuma imagem foi baixada")

    # Nome seguro para o CBZ
    safe_title = "".join(c for c in manga_title if c.isalnum() or c in " _-")
    safe_chap = "".join(c for c in chapter_name if c.isalnum() or c in " _-")
    filename = f"{safe_title}_{safe_chap}.cbz"
    tmp_path = f"/tmp/{int(time.time()*1000)}_{filename}"

    # Cria o CBZ
    with zipfile.ZipFile(tmp_path, "w") as zf:
        for idx, img_bytes in enumerate(images_data, 1):
            img_name = f"{idx:03}.jpg"
            zf.writestr(img_name, img_bytes)

    return tmp_path, filename
