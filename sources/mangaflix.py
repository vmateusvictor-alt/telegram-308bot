import httpx

class MangaFlixSource:
    def __init__(self):
        self.base_url = "https://mangaflix.net"
        self.api_url = "https://api.mangaflix.net/v1"
        self.lang = "pt-BR"

    # ================= SEARCH =================
    async def search(self, query: str):
        url = f"{self.api_url}/search/mangas?query={query}&selected_language=pt-br"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=30)
            data = resp.json()
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
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=30)
            data = resp.json()
            chapters = []
            for ch in data.get("data", {}).get("chapters", []):
                chapters.append({
                    "url": f"/br/manga/{ch.get('_id')}",
                    "chapter_number": ch.get("number"),
                    "name": f"Cap {ch.get('number')}",
                    "manga_title": data.get("data", {}).get("name")
                })
            return sorted(chapters, key=lambda x: float(x["chapter_number"]))

    # ================= PAGES =================
    async def pages(self, chapter_url: str):
        chapter_id = chapter_url.strip("/").split("/")[-1]
        url = f"{self.api_url}/chapters/{chapter_id}?selected_language=pt-br"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=30)
            data = resp.json()
            pages = []
            for img in data.get("data", {}).get("images", []):
                pages.append(img.get("default_url"))
            return pages
