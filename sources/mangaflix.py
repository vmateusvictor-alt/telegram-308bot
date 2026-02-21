import httpx


class MangaFlixSource:
    name = "MangaFlix"
    base_url = "https://mangaflix.net"
    api_url = "https://api.mangaflix.net/v1"

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "pt-BR,pt;q=0.9",
        "Origin": base_url,
        "Referer": base_url + "/",
        "Connection": "keep-alive"
    }

    timeout = httpx.Timeout(60.0)

    # ================= SEARCH =================
    async def search(self, query: str):
        if not query:
            return []

        url = f"{self.api_url}/search/mangas"

        params = {
            "query": query,
            "selected_language": "pt-br"
        }

        async with httpx.AsyncClient(
            headers=self.headers,
            timeout=self.timeout,
            http2=False
        ) as client:

            r = await client.get(url, params=params)

            if r.status_code != 200:
                print("Search error:", r.status_code, r.text)
                return []

            data = r.json()

        results = []

        for item in data.get("data", []):
            results.append({
                "title": item.get("name"),
                "url": item.get("_id")
            })

        return results

    # ================= CHAPTERS =================
    async def chapters(self, manga_id: str):
        url = f"{self.api_url}/mangas/{manga_id}/chapters"

        params = {
            "selected_language": "pt-br",
            "page": 1
        }

        chapters = []

        async with httpx.AsyncClient(
            headers=self.headers,
            timeout=self.timeout,
            http2=False
        ) as client:

            while True:
                r = await client.get(url, params=params)

                if r.status_code != 200:
                    print("Chapters error:", r.status_code, r.text)
                    break

                data = r.json()
                data_list = data.get("data", [])

                if not data_list:
                    break

                for chapter in data_list:
                    chapters.append({
                        "name": f"Capítulo {chapter.get('number')}",
                        "chapter_number": chapter.get("number"),
                        "url": chapter.get("_id")
                    })

                params["page"] += 1

        return chapters

    # ================= PAGES =================
    async def pages(self, chapter_id: str):
        url = f"{self.api_url}/chapters/{chapter_id}"

        params = {
            "selected_language": "pt-br"
        }

        async with httpx.AsyncClient(
            headers=self.headers,
            timeout=self.timeout,
            http2=False
        ) as client:

            r = await client.get(url, params=params)

            if r.status_code != 200:
                print("Pages error:", r.status_code, r.text)
                return []

            data = r.json()

        chapter_data = data.get("data", {})

        # Alguns capítulos trazem CDN separado
        cdn = chapter_data.get("cdn") or "https://cdn.mangaflix.net"
        images = chapter_data.get("images", [])

        if not images:
            return []

        pages = []

        for img in images:
            path = img.get("path") or img.get("url") or img.get("image")

            if not path:
                continue

            if path.startswith("http"):
                pages.append(path)
            else:
                pages.append(f"{cdn}/{path}")

        return pages
