import httpx
import asyncio

class ToonBrSource:
    def __init__(self):
        self.api_url = "https://api.toonbr.com"
        self.cdn_url = "https://cdn2.toonbr.com"
        self.client = httpx.AsyncClient(timeout=30)

    async def search(self, query: str):
        url = f"{self.api_url}/api/manga?page=1&limit=20&search={query}"
        resp = await self.client.get(url)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        return [
            {
                "title": item.get("title"),
                "url": item.get("slug"),
                "manga_title": item.get("title")
            } for item in data
        ]

    async def chapters(self, manga_slug: str):
        url = f"{self.api_url}/api/manga/{manga_slug}"
        resp = await self.client.get(url)
        if resp.status_code != 200:
            return []
        manga = resp.json()
        chapters = manga.get("chapters", [])
        return [
            {
                "url": ch.get("id"),
                "chapter_number": ch.get("chapter_number"),
                "name": f"Cap {ch.get('chapter_number')}",
                "manga_title": manga.get("title")
            } for ch in chapters
        ]

    async def pages(self, chapter_id: str):
        url = f"{self.api_url}/api/chapter/{chapter_id}"
        resp = await self.client.get(url)
        if resp.status_code != 200:
            return []
        chapter = resp.json()
        return [
            self.cdn_url + img["imageUrl"] for img in chapter.get("pages", []) if img.get("imageUrl")
    ]
