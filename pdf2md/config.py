from dotenv import load_dotenv
import os
from pathlib import Path

__proj=Path(__file__).parent.parent

# 加载配置
load_dotenv()

# ==================== 配置 ====================
OUTPUT_MD_DIR = os.getenv("OUTPUT_MD_DIR", "output_md")
PDF_CACHE_DIR = os.getenv("PDF_CACHE_DIR", "pdf_cache")
LOG_FILE = os.getenv("LOG_FILE", "processed.log")
DOWNLOAD_TIMEOUT = int(os.getenv("DOWNLOAD_TIMEOUT", 300))
MAX_RETRY = int(os.getenv("MAX_RETRY", 3))
REMOTE_BASE=os.getenv("REMOTE_BASE")
REMOTE_REPLACE=os.getenv("REMOTE_REPLACE")
# ==================== 批量处理配置 ====================
MAX_PDF_CHUNK = int(os.getenv("MAX_PDF_CHUNK", 5))  # 同时发送给API的PDF数量

# ==================== 多服务器配置 ====================
# 默认两组服务器，端口分别为 8000 和 8002
MINERU_SERVERS = os.getenv("MINERU_SERVERS", "http://localhost:8000,http://localhost:8002")
MINERU_SERVERS_LIST = [s.strip() for s in MINERU_SERVERS.split(",") if s.strip()]

# 每个服务器的API Key（可选，留空则不使用认证）
MINERU_SERVERS_KEYS = {}
_keys_env = os.getenv("MINERU_SERVERS_KEYS", "")
if _keys_env:
    for item in _keys_env.split(","):
        if ":" in item:
            url, key = item.split(":", 1)
            MINERU_SERVERS_KEYS[url.strip()] = key.strip()
