"""📥 download 子命令 - 从bib文件下载PDF"""

import os
import bibtexparser

from .config import REMOTE_BASE, REMOTE_REPLACE
from .utils import load_processed_set, mark_processed, get_md_path, get_pdf_path
from .download import download_file


def run(bib_path: str):
    """执行下载"""
    processed_dois = load_processed_set()
    print(f"📋 已加载 {len(processed_dois)} 条已处理记录")

    with open(bib_path, "r", encoding="utf-8") as f:
        bib_db = bibtexparser.load(f)

    total = len(bib_db.entries)
    print(f"📚 总文献数: {total}")

    download_count = 0
    skip_count = 0

    for idx, entry in enumerate(bib_db.entries, 1):
        doi = entry.get("doi", "").strip()
        file_path = entry.get("file", "").strip()
        title = entry.get("title", "无标题")

        print(f"\n===== [{idx}/{total}] =====")
        print(f"标题: {title[:50]}...")
        print(f"DOI: {doi}")

        if not doi:
            print("❌ 无DOI，跳过")
            continue
        if not file_path:
            print("❌ 无file属性，跳过")
            continue
        if doi in processed_dois:
            print("✅ 已处理，跳过")
            continue

        md_path = get_md_path(doi)
        if os.path.exists(md_path):
            print("✅ MD已存在，标记已处理...")
            mark_processed(doi)
            skip_count += 1
            continue

        # 处理多文件情况
        if ";" in file_path:
            file_path = file_path.split(";")[0]
        file_path = file_path.replace(r'\:', r':')
        file_path = file_path.replace(r'\\\\', r'\\')

        pdf_path = get_pdf_path(doi)
        rel = file_path.replace(REMOTE_REPLACE, "").replace("\\", "/").replace(" ", "%20")
        file_url = REMOTE_BASE + rel

        try:
            download_file(file_url, pdf_path)
            download_count += 1
            print("✅ 下载成功")
        except Exception as e:
            print(f"❌ 下载失败: {str(e)}")

    print(f"\n📊 下载完成: {download_count} 个成功, {skip_count} 个已跳过")


def add_parser(subparsers):
    """添加子命令参数"""
    parser = subparsers.add_parser("download", help="从bib文件下载PDF")
    parser.add_argument("bib_file", help="BibTeX文件路径")
    return parser
