import aiohttp

class ToonBr:
    name = "ToonBr"
    base_url = "https://beta.toonbr.com"
    api_url = "https://api.toonbr.com"
    cdn_url = "https://cdn2.toonbr.com"

    # ================= SEARCH =================
    async def search(self, query: str):
        url = f"{self.api_url}/api/manga?page=1&limit=20&search={query}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()

        results = []
        for manga in data.get("data", []):
            results.append({
                "title": manga.get("title"),
                "url": manga.get("slug"),  # importante!
            })

        return results

    # ================= CHAPTERS =================
    async def chapters(self, manga_slug: str):
        url = f"{self.api_url}/api/manga/{manga_slug}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()

        chapters = []
        manga_title = data.get("title")

        for ch in data.get("chapters", []):
            chapters.append({
                "name": ch.get("name"),
                "chapter_number": ch.get("chapterNumber"),
                "url": ch.get("id"),  # ID do capítulo
                "manga_title": manga_title,
            })

        # ordenar do mais recente pro mais antigo
        chapters.sort(key=lambda x: float(x.get("chapter_number") or 0), reverse=True)

        return chapters

    # ================= PAGES =================
    async def pages(self, chapter_id: str):
        url = f"{self.api_url}/api/chapter/{chapter_id}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()

        pages = []
        for p in data.get("pages", []):
            image = p.get("imageUrl")
            if image:
                pages.append(f"{self.cdn_url}{image}")

        return pages
