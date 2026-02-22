import aiohttp
import re

ANILIST_URL = "https://graphql.anilist.co"


# remove html da sinopse
def clean_html(text):
    return re.sub("<.*?>", "", text or "")


# resumo simples automático
def summarize(text, max_sentences=3):
    sentences = text.split(". ")
    return ". ".join(sentences[:max_sentences]).strip() + "."


async def search_anilist(title):

    query = """
    query ($search: String) {
      Media(search: $search, type: MANGA) {
        title {
          romaji
          english
        }
        description(asHtml:false)
        genres
        coverImage {
          extraLarge
        }
      }
    }
    """

    async with aiohttp.ClientSession() as session:
        async with session.post(
            ANILIST_URL,
            json={"query": query, "variables": {"search": title}},
        ) as resp:

            data = await resp.json()

    media = data["data"]["Media"]

    synopsis = clean_html(media["description"])
    synopsis = summarize(synopsis)

    return {
        "title": media["title"]["romaji"]
        or media["title"]["english"],
        "genres": ", ".join(media["genres"]),
        "cover": media["coverImage"]["extraLarge"],
        "synopsis": synopsis,
    }
