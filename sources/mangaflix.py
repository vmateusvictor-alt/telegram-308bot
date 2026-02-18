import httpx


class MangaFlix:
    name = "MangaFlix"
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
        for manga in data.get("data", []):
            results.append({
                "title": manga.get("name"),
                "url": manga.get("_id"),  # ID do mangá
            })

        return results

    # ================= CHAPTERS =================
    async def chapters(self, manga_id: str):
        url = f"{self.api_url}/mangas/{manga_id}"

        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json()

        manga_data = data.get("data", {})
        manga_title = manga_data.get("name", "Manga")

        chapters = []

        for ch in manga_data.get("chapters", []):
            chapters.append({
                "name": f"Capítulo {ch.get('number')}",
                "chapter_number": ch.get("number"),
                "url": ch.get("_id"),  # ID do capítulo
                "manga_title": manga_title,
            })

        # Ordenação segura igual ToonBr
        def safe_float(x):
            try:
                return float(x)
            except:
                return 0.0

        chapters.sort(
            key=lambda x: safe_float(x.get("chapter_number")),
            reverse=True
        )

        return chapters

    # ================= PAGES =================
    async def pages(self, chapter_id: str):
        url = f"{self.api_url}/chapters/{chapter_id}?selected_language=pt-br"

        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json()

        chapter_data = data.get("data", {})
        pages = []

        for img in chapter_data.get("images", []):
            image_url = img.get("default_url")
            if image_url:
                pages.append(image_url)

        return pages
