import httpx
import os

class Mangaflix:
    name = "Mangaflix"
    base_url = "https://mangaflix.net"
    api_url = "https://api.mangaflix.net/v1"

    # ================= SEARCH =================
    async def search(self, query: str):
        url = f"{self.api_url}/search/mangas?query={query}&selected_language=pt-br"
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json()

        results = []
        for item in data.get("data", []):
            results.append({
                "title": item.get("name", "Sem título"),
                "url": item.get("_id")
            })
        return results

    # ================= CHAPTERS =================
    async def chapters(self, manga_id: str):
        url = f"{self.api_url}/mangas/{manga_id}"
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json()

        chapters = []
        for ch in data.get("data", {}).get("chapters", []):
            chapters.append({
                "name": f"Capítulo {ch.get('number', '?')}",
                "chapter_number": ch.get("number", 0),
                "url": ch.get("_id")
            })

        chapters.sort(key=lambda x: float(x.get("chapter_number") or 0), reverse=True)
        return chapters

    # ================= PAGES =================
    async def pages(self, chapter_id: str, save_dir: str = "downloads"):
        url = f"{self.api_url}/chapters/{chapter_id}?selected_language=pt-br"
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json()

        pages = []
        os.makedirs(save_dir, exist_ok=True)

        for idx, img in enumerate(data.get("data", {}).get("images", []), start=1):
            img_url = img.get("default_url")
            if not img_url:
                continue

            # baixa imagem de forma síncrona para evitar problemas com aiofiles
            file_path = os.path.join(save_dir, f"{chapter_id}_{idx}.jpg")
            try:
                resp = httpx.get(img_url, timeout=30.0)
                with open(file_path, "wb") as f:
                    f.write(resp.content)
                pages.append(file_path)
            except Exception as e:
                print(f"Erro ao baixar {img_url}: {e}")

        return pages
