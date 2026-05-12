from dotenv import load_dotenv
import os

# 加载配置
load_dotenv()

# ==================== 配置 ====================
MINERU_API_URL = os.getenv("MINERU_API_URL")
MINERU_API_KEY = os.getenv("MINERU_API_KEY")
OUTPUT_MD_DIR = os.getenv("OUTPUT_MD_DIR", "output_md")
PDF_CACHE_DIR = os.getenv("PDF_CACHE_DIR", "pdf_cache")
LOG_FILE = os.getenv("LOG_FILE", "processed.log")
DOWNLOAD_TIMEOUT = int(os.getenv("DOWNLOAD_TIMEOUT", 300))
MAX_RETRY = int(os.getenv("MAX_RETRY", 3))
REMOTE_BASE=os.getenv("REMOTE_BASE")
REMOTE_REPLACE=os.getenv("REMOTE_REPLACE")
