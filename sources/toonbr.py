import httpx
from datetime import datetime

class ToonBrSource:
    name = "ToonBr"
    base_url = "https://beta.toonbr.com"
    api_url = "https://api.toonbr.com"
    cdn_url = "https://cdn2.toonbr.com"

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30)

    async def search(self, query: str):
        url = f"{self.api_url}/api/manga?search={query}&limit=20"
        resp = await self.client.get(url)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        results = []
        for m in data:
            results.append({
                "title": m.get("name"),
                "url": m.get("slug"),
                "manga_title": m.get("name")
            })
        return results

    async def chapters(self, manga_url: str):
        # Pega todos os capítulos de um manga
        url = f"{self.api_url}/api/manga/{manga_url}"
        resp = await self.client.get(url)
        resp.raise_for_status()
        data = resp.json()
        chapters = []
        for c in data.get("chapters", []):
            chapters.append({
                "name": c.get("name"),
                "url": c.get("id"),
                "chapter_number": c.get("chapter_number"),
                "manga_title": data.get("name")
            })
        return chapters

    async def chapters_for_id(self, chapter_id: str):
        # Retorna capítulos de manga dado um capítulo
        # Primeiro pega o manga do capítulo
        url = f"{self.api_url}/api/chapter/{chapter_id}"
        resp = await self.client.get(url)
        if resp.status_code != 200:
            return []
        data = resp.json()
        manga_slug = data.get("manga_slug")
        return await self.chapters(manga_slug)

    async def pages(self, chapter_id: str):
        url = f"{self.api_url}/api/chapter/{chapter_id}"
        resp = await self.client.get(url)
        if resp.status_code != 200:
            return []
        data = resp.json()
        pages = []
        for p in data.get("pages", []):
            if p.get("imageUrl"):
                pages.append({"image": f"{self.cdn_url}{p['imageUrl']}"})
        return pages
