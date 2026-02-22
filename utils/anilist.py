import aiohttp
import re

ANILIST_URL = "https://graphql.anilist.co"

# Remove HTML da sinopse
def clean_html(text):
    return re.sub("<.*?>", "", text or "")

# Resumo simples automático
def summarize(text, max_sentences=3):
    sentences = text.split(". ")
    if len(sentences) > max_sentences:
        return ". ".join(sentences[:max_sentences]).strip() + "..."
    return text.strip()

# Formata a saída de forma bonita
def format_manga_info(data):
    return (
        f"🎌 **{data['title']}**\n"
        f"📚 Gêneros: {data['genres']}\n"
        f"📝 Sinopse: {data['synopsis']}\n"
        f"🖼️ Capa: {data['cover']}"
    )

async def search_anilist(title):

    query = """
    query ($search: String) {
      Media(search: $search, type: MANGA, language: PORTUGUESE) {
        title {
          romaji
          english
          native
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

    if not data.get("data") or not data["data"].get("Media"):
        return "❌ Mangá não encontrado."

    media = data["data"]["Media"]

    # Tenta pegar a sinopse em português, se existir
    synopsis = clean_html(media.get("description"))
    synopsis = summarize(synopsis)

    manga_info = {
        "title": media["title"].get("romaji") or media["title"].get("english") or media["title"].get("native"),
        "genres": ", ".join(media.get("genres", [])) or "Não disponível",
        "cover": media["coverImage"].get("extraLarge"),
        "synopsis": synopsis or "Sem sinopse disponível.",
    }

    return format_manga_info(manga_info)
