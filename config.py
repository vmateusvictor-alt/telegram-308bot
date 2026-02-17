import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # URL do Railway / domínio com SSL
PORT = int(os.getenv("PORT", 8443))
CBZ_CACHE_DIR = os.getenv("CBZ_CACHE_DIR", "./cbz_cache")
