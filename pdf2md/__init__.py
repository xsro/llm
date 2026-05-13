# pdf2md - 从BibTeX批量下载PDF并转换为Markdown

from .config import *
from .download import download_file

# 创建文件夹
import os
os.makedirs(OUTPUT_MD_DIR, exist_ok=True)
os.makedirs(PDF_CACHE_DIR, exist_ok=True)