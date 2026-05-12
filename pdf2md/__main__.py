import os
import re
import sys
import bibtexparser

from .config import *
from .mineru import batch_pdf_to_md
from .download import download_file

# 创建文件夹
os.makedirs(OUTPUT_MD_DIR, exist_ok=True)
os.makedirs(PDF_CACHE_DIR, exist_ok=True)


# ==================== 工具函数 ====================
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
    return os.path.join(PDF_CACHE_DIR, f"{clean_doi(doi)}.pdf")

def get_md_path(doi: str) -> str:
    return os.path.join(OUTPUT_MD_DIR, f"{clean_doi(doi)}.md")


# ==================== download 命令 ====================
def download_papers(bib_path: str):
    """下载论文PDF"""
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

        # 过滤
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
    print("🎉 运行 'python -m pdf2md convert <bib_file>' 开始转换")


# ==================== convert 命令 ====================
def convert_papers(bib_path: str):
    """批量转换PDF为Markdown"""
    processed_dois = load_processed_set()
    print(f"📋 已加载 {len(processed_dois)} 条已处理记录")

    with open(bib_path, "r", encoding="utf-8") as f:
        bib_db = bibtexparser.load(f)

    total = len(bib_db.entries)
    print(f"📚 总文献数: {total}")

    # 收集待转换项
    pending = []
    skip_no_pdf = 0
    skip_has_md = 0

    for idx, entry in enumerate(bib_db.entries, 1):
        doi = entry.get("doi", "").strip()
        title = entry.get("title", "无标题")

        print(f"\n===== [{idx}/{total}] =====")
        print(f"标题: {title[:50]}...")
        print(f"DOI: {doi}")

        if not doi:
            print("❌ 无DOI，跳过")
            continue
        if doi in processed_dois:
            print("✅ 已处理，跳过")
            continue

        pdf_path = get_pdf_path(doi)
        md_path = get_md_path(doi)

        if not os.path.exists(pdf_path):
            print("❌ PDF未下载，跳过")
            skip_no_pdf += 1
            continue

        if os.path.exists(md_path):
            print("✅ MD已存在，标记已处理...")
            mark_processed(doi)
            skip_has_md += 1
            continue

        pending.append({
            "doi": doi,
            "pdf_path": pdf_path,
            "md_path": md_path,
            "title": title
        })

    print(f"\n📦 待转换: {len(pending)} 个, 跳过(PDF不存在): {skip_no_pdf}, 跳过(MD已存在): {skip_has_md}")

    if not pending:
        print("⚠️ 没有待转换的PDF")
        return

    # 按批次发送
    for i in range(0, len(pending), MAX_PDF_CHUNK):
        batch = pending[i:i + MAX_PDF_CHUNK]
        batch_num = i // MAX_PDF_CHUNK + 1
        total_batches = (len(pending) + MAX_PDF_CHUNK - 1) // MAX_PDF_CHUNK

        print(f"\n{'='*50}")
        print(f"📦 处理批次 {batch_num}/{total_batches} ({len(batch)} 个)")
        print(f"{'='*50}")

        pdf_md_pairs = [(p["pdf_path"], p["md_path"]) for p in batch]
        results = batch_pdf_to_md(pdf_md_pairs)

        # 处理结果
        doi_map = {p["pdf_path"]: p for p in batch}
        success_count = 0

        for pdf_path, md_path, success, error in results:
            item = doi_map.get(pdf_path)
            if not item:
                continue

            if success:
                mark_processed(item["doi"])
                success_count += 1
                print(f"✅ {item['title'][:40]}...")
            else:
                print(f"❌ {item['title'][:40]}: {error}")

        print(f"📊 批次 {batch_num} 完成: {success_count}/{len(batch)} 成功")

    print(f"\n🎉 全部转换完成！")


# ==================== 命令行入口 ====================
def main():
    if len(sys.argv) < 2:
        print("用法:")
        print("  python -m pdf2md download <bib_file>  # 下载PDF")
        print("  python -m pdf2md convert <bib_file>   # 批量转换")
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "download":
        if len(sys.argv) < 3:
            print("❌ 请提供bib文件路径")
            sys.exit(1)
        download_papers(sys.argv[2])

    elif command == "convert":
        if len(sys.argv) < 3:
            print("❌ 请提供bib文件路径")
            sys.exit(1)
        convert_papers(sys.argv[2])

    else:
        print(f"❌ 未知命令: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
