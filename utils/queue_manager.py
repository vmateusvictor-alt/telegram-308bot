import asyncio
from collections import deque

MAX_SIMULTANEOUS = 2

class DownloadJob:
    def __init__(self, user_id, user_name, manga, chapters, message, source):
        self.user_id = user_id
        self.user_name = user_name
        self.manga = manga
        self.chapters = chapters
        self.message = message
        self.source = source

queue = deque()
active_downloads = set()
lock = asyncio.Lock()


async def add_job(job):
    async with lock:
        queue.append(job)


async def get_position(user_id):
    async with lock:
        for i, job in enumerate(queue):
            if job.user_id == user_id:
                return i + 1
    return None


async def next_job():
    async with lock:
        if len(active_downloads) >= MAX_SIMULTANEOUS:
            return None
        if not queue:
            return None

        job = queue.popleft()
        active_downloads.add(job.user_id)
        return job


async def finish_job(user_id):
    async with lock:
        active_downloads.discard(user_id)
