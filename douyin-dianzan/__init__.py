from pathlib import Path

from conf import BASE_DIR

# 确保所有父目录都存在
cookies_path = BASE_DIR / "cookies" / "douyin_uploader"
cookies_path.mkdir(parents=True, exist_ok=True) 