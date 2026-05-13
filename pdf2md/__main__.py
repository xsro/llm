import os
import re
import argparse
import bibtexparser

from .config import *
from .miner import submit_tasks, poll_and_save_results, save_task_mapping, load_task_mapping
from .download import download_file

os.makedirs(OUTPUT_MD_DIR, exist_ok=True)
os.makedirs(PDF_CACHE_DIR, exist_ok=True)


# ==================== 工具函数 ====================
def load_processed_set() -> set:
    if not os.path.exists(LOG_FILE):
        return set()
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def mark_processed(doi: str):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{doi}\n")

def clean_doi(doi: str) -> str:
    doi = doi.strip()
    doi = re.sub(r'^https?://doi\.org/', '', doi)
    doi = re.sub(r'[\\/*?:"<>|]', '_', doi)
    return doi

def get_pdf_path(doi: str) -> str:
    return os.path.join(PDF_CACHE_DIR, f"{clean_doi(doi)}.pdf")

def get_md_path(doi: str) -> str:
    return os.path.join(OUTPUT_MD_DIR, f"{clean_doi(doi)}.md")

def split_to_groups(items: list, num_groups: int):
    """将列表分成若干组，轮流分配"""
    groups = [[] for _ in range(num_groups)]
    for i, item in enumerate(items):
        groups[i % num_groups].append(item)
    return groups


# ==================== download 命令 ====================
def download_papers(bib_path: str):
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


# ==================== start-convert 命令 ====================
def start_convert(bib_path: str, num_groups: int = None):
    """提交异步转换任务"""
    # 确定使用的服务器列表
    if num_groups is None:
        num_groups = len(MINERU_SERVERS_LIST)
    num_groups = max(1, num_groups)

    servers_to_use = MINERU_SERVERS_LIST[:num_groups] if MINERU_SERVERS_LIST else ["http://localhost:8000"]
    print(f"🔧 使用 {len(servers_to_use)} 个服务器: {servers_to_use}")

    processed_dois = load_processed_set()
    print(f"📋 已加载 {len(processed_dois)} 条已处理记录")

    with open(bib_path, "r", encoding="utf-8") as f:
        bib_db = bibtexparser.load(f)

    total = len(bib_db.entries)
    print(f"📚 总文献数: {total}")

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

        pending.append((pdf_path, md_path))

    print(f"\n📦 待提交: {len(pending)} 个, 跳过(PDF不存在): {skip_no_pdf}, 跳过(MD已存在): {skip_has_md}")

    if not pending:
        print("⚠️ 没有待转换的PDF")
        return

    # 将任务分配到不同服务器（轮流分配）
    groups = split_to_groups(pending, len(servers_to_use))

    # 提交任务
    task_mapping = {}
    for server_idx, (server, group) in enumerate(zip(servers_to_use, groups)):
        if not group:
            continue

        print(f"\n{'='*50}")
        print(f"📦 服务器 {server_idx + 1}/{len(servers_to_use)}: {server} ({len(group)} 个)")
        print(f"{'='*50}")

        batch_mapping = submit_tasks(group, api_url=server)
        task_mapping.update(batch_mapping)

    # 保存任务映射
    mapping_file = os.path.join(PDF_CACHE_DIR, "task_mapping.json")
    save_task_mapping(task_mapping, mapping_file)
    print(f"\n✅ 任务已提交，共 {len(task_mapping)} 个")
    print(f"📁 任务映射已保存: {mapping_file}")
    print(f"🎉 运行 'python -m pdf2md get-result' 获取结果")


# ==================== get-result 命令 ====================
def get_result():
    """获取异步任务结果"""
    mapping_file = os.path.join(PDF_CACHE_DIR, "task_mapping.json")

    if not os.path.exists(mapping_file):
        print(f"❌ 任务映射文件不存在: {mapping_file}")
        print("💡 请先运行 'python -m pdf2md start-convert <bib_file>'")
        return

    task_mapping = load_task_mapping(mapping_file)
    if not task_mapping:
        print("❌ 没有待处理的任务")
        return

    print(f"📋 加载了 {len(task_mapping)} 个任务，开始轮询结果...")

    results = poll_and_save_results(task_mapping)

    # 统计并标记
    success_count = 0
    for pdf_path, md_path, success, error in results:
        if success:
            mark_processed(clean_doi(pdf_path))
            success_count += 1
        else:
            print(f"❌ {os.path.basename(pdf_path)}: {error}")

    # 清理已完成的任务映射
    failed_paths = {p for _, p, s, _ in results if not s}
    remaining = {tid: paths for tid, paths in task_mapping.items() if paths[0] not in failed_paths}
    if remaining:
        save_task_mapping(remaining, mapping_file)
        print(f"\n⚠️ 仍有 {len(remaining)} 个任务失败，可重试")
    else:
        os.remove(mapping_file)
        print(f"\n✅ 所有任务已完成")

    print(f"\n📊 结果: {success_count}/{len(results)} 成功")


# ==================== 命令行入口 ====================
def main():
    parser = argparse.ArgumentParser(
        description="PDF转Markdown工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
可用服务器: {MINERU_SERVERS_LIST or ['http://localhost:8000']}

示例:
  python -m pdf2md download papers.bib       # 下载PDF
  python -m pdf2md start-convert papers.bib  # 提交任务（使用所有服务器）
  python -m pdf2md start-convert papers.bib -g 2  # 使用2个服务器分组
  python -m pdf2md start-convert papers.bib -g 1  # 只使用第一个服务器
  python -m pdf2md get-result                # 获取转换结果
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # download 子命令
    parser_download = subparsers.add_parser("download", help="从bib文件下载PDF")
    parser_download.add_argument("bib_file", help="BibTeX文件路径")

    # start-convert 子命令
    parser_start = subparsers.add_parser("start-convert", help="提交异步转换任务")
    parser_start.add_argument("bib_file", help="BibTeX文件路径")
    parser_start.add_argument("-g", "--groups", type=int, default=None,
                              help=f"使用多少个服务器分组（默认: 使用所有{len(MINERU_SERVERS_LIST)}个服务器）")

    # get-result 子命令
    subparsers.add_parser("get-result", help="获取转换结果")

    args = parser.parse_args()

    if args.command == "download":
        download_papers(args.bib_file)
    elif args.command == "start-convert":
        start_convert(args.bib_file, args.groups)
    elif args.command == "get-result":
        get_result()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
