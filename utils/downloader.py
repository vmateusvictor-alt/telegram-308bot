import httpx
import asyncio
import os
import tempfile


# ---------------- DOWNLOAD IMAGE ----------------
async def fetch_image(client, url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = await client.get(url, headers=headers, timeout=30.0)
        r.raise_for_status()
        return r.content
    except Exception as e:
        print(f"Erro ao baixar {url}: {e}")
        return None


# ---------------- DOWNLOAD ALL IMAGES ----------------
async def download_images(urls):
    async with httpx.AsyncClient(http2=True, timeout=30.0) as client:
        tasks = [fetch_image(client, url) for url in urls]
        results = await asyncio.gather(*tasks)

    images = [img for img in results if img]
    return images


# ---------------- MAIN FUNCTION (ESSENCIAL PRO BOT) ----------------
async def download_chapter(source, chapter):
    """
    Função que o bot espera existir.
    Baixa o capítulo inteiro e retorna pasta contendo imagens.
    """

    # obter páginas do source
    if hasattr(source, "pages"):
        if asyncio.iscoroutinefunction(source.pages):
            pages = await source.pages(chapter["url"])
        else:
            pages = await asyncio.to_thread(source.pages, chapter["url"])
    else:
        raise Exception("Source não possui função pages()")

    if not pages:
        raise Exception("Nenhuma página encontrada")

    # baixar imagens
    images = await download_images(pages)
    if not images:
        raise Exception("Falha ao baixar imagens")

    # criar pasta temporária
    folder = tempfile.mkdtemp(prefix="manga_")

    for i, img in enumerate(images):
        path = os.path.join(folder, f"{i:03}.jpg")
        with open(path, "wb") as f:
            f.write(img)

    return folder
