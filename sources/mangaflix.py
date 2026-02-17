import aiohttp
from datetime import datetime
from utils.cbz import create_cbz  # Apenas se precisar dentro da fonte
from asyncio import get_event_loop

class MangaFlixSource:
    def __init__(self):
        self.base_url = "https://mangaflix.net"
        self.api_url = "https://api.mangaflix.net/v1"

    # ================= SEARCH =================
    async def search(self, query: str):
        url = f"{self.api_url}/search/mangas?query={query}&selected_language=pt-br"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
                results = []
                for item in data.get("data", []):
                    results.append({
                        "title": item.get("name"),
                        "url": f"/br/manga/{item.get('_id')}",
                        "thumbnail": item.get("poster", {}).get("default_url")
                    })
                return results

    # ================= CHAPTERS =================
    async def chapters(self, manga_url: str):
        manga_id = manga_url.strip("/").split("/")[-1]
        url = f"{self.api_url}/mangas/{manga_id}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
                chapters = []
                for ch in data.get("data", {}).get("chapters", []):
                    chapters.append({
                        "url": f"/br/manga/{ch.get('_id')}",
                        "chapter_number": ch.get("number"),
                        "name": f"Cap {ch.get('number')}",
                        "manga_title": data.get("data", {}).get("name")
                    })
                # Ordena do capítulo 1 ao último
                return sorted(chapters, key=lambda x: float(x["chapter_number"]))

    # ================= PAGES =================
    async def pages(self, chapter_url: str):
        chapter_id = chapter_url.strip("/").split("/")[-1]
        url = f"{self.api_url}/chapters/{chapter_id}?selected_language=pt-br"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
                pages = []
                for idx, img in enumerate(data.get("data", {}).get("images", [])):
                    pages.append({
                        "image_url": img.get("default_url"),
                        "index": idx
                    })
                return [p["image_url"] for p in pages]
