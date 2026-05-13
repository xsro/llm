"""📋 共享工具函数"""

import os
import re
from .config import LOG_FILE, PDF_CACHE_DIR, OUTPUT_MD_DIR


def load_processed_set() -> set:
    """加载已处理的DOI列表"""
    if not os.path.exists(LOG_FILE):
        return set()
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())


def mark_processed(doi: str):
    """将DOI写入已处理日志"""
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{doi}\n")


def clean_doi(doi: str) -> str:
    """清洗DOI"""
    doi = doi.strip()
    doi = re.sub(r'^https?://doi\.org/', '', doi)
    doi = re.sub(r'[\\/*?:"<>|]', '_', doi)
    return doi


def get_pdf_path(doi: str) -> str:
    """获取PDF文件路径"""
    return os.path.join(PDF_CACHE_DIR, f"{clean_doi(doi)}.pdf")


def get_md_path(doi: str) -> str:
    """获取MD文件路径"""
    return os.path.join(OUTPUT_MD_DIR, f"{clean_doi(doi)}.md")


def split_to_groups(items: list, num_groups: int) -> list:
    """将列表分成若干组，轮流分配"""
    groups = [[] for _ in range(num_groups)]
    for i, item in enumerate(items):
        groups[i % num_groups].append(item)
    return groups
