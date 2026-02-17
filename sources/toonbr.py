import httpx

class ToonBrSource:
    def __init__(self):
        self.base_url = "https://beta.toonbr.com"
        self.api_url = "https://api.toonbr.com"
        self.cdn_url = "https://cdn2.toonbr.com"

    # ================= SEARCH =================
    async def search(self, query: str):
        url = f"{self.api_url}/api/manga?page=1&limit=50&q={query}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=30)
            data = resp.json()
            results = []
            for item in data.get("data", []):
                results.append({
                    "title": item.get("name"),
                    "url": item.get("slug"),
                    "thumbnail": item.get("poster", {}).get("default_url")
                })
            return results

    # ================= CHAPTERS =================
    async def chapters(self, manga_slug: str):
        url = f"{self.api_url}/api/manga/{manga_slug}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=30)
            data = resp.json()
            manga_name = data.get("name") or "Manga"
            chapters = []
            for ch in data.get("chapters", []):
                chapters.append({
                    "url": ch.get("slug"),
                    "chapter_number": ch.get("number"),
                    "name": f"Cap {ch.get('number')}",
                    "manga_title": manga_name
                })
            return sorted(chapters, key=lambda x: float(x["chapter_number"]))

    # ================= PAGES =================
    async def pages(self, chapter_slug: str):
        url = f"{self.api_url}/api/chapter/{chapter_slug}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=30)
            data = resp.json()
            pages = []
            for img in data.get("pages", []):
                pages.append(f"{self.cdn_url}{img.get('image')}" if img.get("image") else None)
            return [p for p in pages if p]
