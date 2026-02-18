import zipfile
import os
import time

async def create_cbz(images_data, manga_title, chapter_name):
    safe_title = "".join(c for c in manga_title if c.isalnum() or c in " _-")
    safe_chap = "".join(c for c in chapter_name if c.isalnum() or c in " _-")
    filename = f"{safe_title}_{safe_chap}.cbz"
    tmp_path = f"/tmp/{int(time.time()*1000)}_{filename}"

    with zipfile.ZipFile(tmp_path, "w") as zf:
        for idx, img in enumerate(images_data, 1):
            img_name = f"{idx:03}.jpg"
            zf.writestr(img_name, img)

    return tmp_path, filename
