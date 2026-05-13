"""📊 get-result 子命令 - 获取转换结果"""

import os

from .config import PDF_CACHE_DIR
from .miner import poll_and_save_results, load_task_mapping, save_task_mapping
from .utils import mark_processed, clean_doi


def run():
    """执行结果获取"""
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


def add_parser(subparsers):
    """添加子命令参数"""
    return subparsers.add_parser("get-result", help="获取转换结果")
