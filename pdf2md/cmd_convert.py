"""🔄 start-convert 子命令 - 提交异步转换任务"""

import os
import bibtexparser

from .config import MINERU_SERVERS_LIST, PDF_CACHE_DIR
from .miner import submit_tasks, save_task_mapping
from .utils import load_processed_set, mark_processed, get_pdf_path, get_md_path, split_to_groups


def run(bib_path: str, num_groups: int = None):
    """执行转换任务提交"""
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


def add_parser(subparsers):
    """添加子命令参数"""
    parser = subparsers.add_parser("start-convert", help="提交异步转换任务")
    parser.add_argument("bib_file", help="BibTeX文件路径")
    parser.add_argument("-g", "--groups", type=int, default=None,
                        help=f"使用多少个服务器分组（默认: 使用所有{len(MINERU_SERVERS_LIST)}个服务器）")
    return parser
