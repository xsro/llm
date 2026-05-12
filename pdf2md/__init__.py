import os
import re
import bibtexparser

from .config import *
from .mineru import pdf_to_md
from .download import download_file


# 创建文件夹
os.makedirs(OUTPUT_MD_DIR, exist_ok=True)
os.makedirs(PDF_CACHE_DIR, exist_ok=True)

# ==================== 工具函数 ====================
def load_processed_set() -> set:
    """加载已处理的DOI列表，实现断点续传"""
    if not os.path.exists(LOG_FILE):
        return set()
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def mark_processed(doi: str):
    """将DOI写入已处理日志"""
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{doi}\n")

def clean_doi(doi: str) -> str:
    """清洗DOI，去掉前缀，去掉非法文件名字符"""
    doi = doi.strip()
    doi = re.sub(r'^https?://doi\.org/', '', doi)
    doi = re.sub(r'[\\/*?:"<>|]', '_', doi)
    return doi

def get_pdf_path(doi: str) -> str:
    """生成PDF缓存路径"""
    return os.path.join(PDF_CACHE_DIR, f"{clean_doi(doi)}.pdf")

def get_md_path(doi: str) -> str:
    """生成MD输出路径"""
    return os.path.join(OUTPUT_MD_DIR, f"{clean_doi(doi)}.md")



# ==================== 核心：处理Bib文件 ====================
def process_bib(bib_path: str):
    processed_dois = load_processed_set()
    print(f"📋 已加载 {len(processed_dois)} 条已处理记录")

    # 读取bib
    with open(bib_path, "r", encoding="utf-8") as f:
        bib_db = bibtexparser.load(f)

    total = len(bib_db.entries)
    print(f"📚 总文献数: {total}")

    for idx, entry in enumerate(bib_db.entries, 1):
        doi = entry.get("doi", "").strip()
        file_path = entry.get("file", "").strip()
        title = entry.get("title", "无标题")
        langid = entry.get("langid")

        print(f"\n===== [{idx}/{total}] =====")
        print(f"标题: {title[:50]}...")
        print(f"DOI: {doi}")

        if langid!="english":
            continue

        # 过滤无效条目
        if not doi:
            print("❌ 无DOI，跳过")
            continue

        if not file_path:
            print("❌ 无file属性，跳过")
            continue
        if doi in processed_dois:
            print("✅ 已处理，跳过")
            continue

        try:
            pdf_path = get_pdf_path(doi)
            md_path = get_md_path(doi)

            if ";" in file_path:
                file_path=file_path.split(";")[0]
            file_path=file_path.replace(r'\:',r':')
            file_path=file_path.replace(r'\\\\',r'\\')
            rel=file_path.replace(REMOTE_REPLACE,"").replace("\\","/").replace(" ", "%20")
            file_url=REMOTE_BASE+rel

            # 1. 下载PDF
            download_file(file_url, pdf_path)

            # 2. 转MD
            pdf_to_md(pdf_path, md_path)

            # 3. 标记已完成
            mark_processed(doi)
            print("🎉 本条处理完成！")

        except Exception as e:
            print(f"❌ 处理失败: {str(e)}")

    print("\n🎉 全部处理完成！")