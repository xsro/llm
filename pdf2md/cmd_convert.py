"""🔄 convert 子命令 - 提交PDF到MinerU服务器"""

import json
import os
from pathlib import Path

from .config import MINERU_SERVERS_LIST, __proj
from .miner import submit_task, _get_headers
from .utils import split_to_groups
import time

def run(args):
    """提交PDF到MinerU服务器

    Args:
        task_id: 任务ID（目录名，如 20260514_011736）
        num_groups: 使用多少个服务器分组
    """
    task_id=args.task_id
    num_groups: int = args.groups
    # 确定使用的服务器列表
    if num_groups is None:
        num_groups = len(MINERU_SERVERS_LIST)
    num_groups = max(1, num_groups)

    servers_to_use = MINERU_SERVERS_LIST[:num_groups] if MINERU_SERVERS_LIST else ["http://localhost:8000"]
    print(f"🔧 使用 {len(servers_to_use)} 个服务器: {servers_to_use}")

    # 加载 task
    task_dir = __proj / "data" / "tasks" / task_id
    if not task_dir.exists():
        print(f"❌ 任务目录不存在: {task_dir}")
        return

    pdfs_json = task_dir / "pdfs.json"
    pdfs2_json = task_dir / "pdfs_result.json"
    if pdfs2_json.exists():
        pdfs_json=pdfs2_json
    if not pdfs_json.exists():
        print(f"❌ pdfs.json 不存在: {pdfs_json}")
        return
    

    # 读取现有的 pdfs 数据
    with open(pdfs_json, "r", encoding="utf-8") as f:
        task_data = json.load(f)

    pdfs = task_data.get("pdfs", [])
    print(f"📦 待提交PDF数量: {len(pdfs)}")

    # 筛选出未提交的和需要重新提交的
    pending_pdfs = []
    for pdf in pdfs:
        # 检查是否已提交（有 task_id 且成功）
        if pdf.get("task_id") and pdf.get("status") == "completed": 
            print(f"⏭️  已完成，跳过: {pdf.get('name', pdf.get('path'))}")
            continue
        if pdf.get("task_id") and  pdf.get("status") == "submitted":
            print(f"⏭️  已提交，跳过: {pdf.get('name', pdf.get('path'))}")
            continue
        pending_pdfs.append(pdf)

    if not pending_pdfs:
        print("⚠️ 没有待提交的PDF")
        return

    print(f"📋 待提交: {len(pending_pdfs)} 个")

    # 分配到不同服务器
    groups = split_to_groups(pending_pdfs, len(servers_to_use))

    print(groups)

    # 提交任务
    submitted_count = 0
    for server_idx, (server, group) in enumerate(zip(servers_to_use, groups)):
        if not group:
            continue

        print(f"\n{'='*50}")
        print(f"📦 服务器 {server_idx + 1}/{len(servers_to_use)}: {server} ({len(group)} 个)")
        print(f"{'='*50}")

        for pdf in group:
            pdf_path = pdf.get("path")
            if not pdf_path or not os.path.exists(pdf_path):
                print(f"❌ PDF不存在: {pdf_path}")
                continue

            try:
                # 提交到 mineru
                print(pdf_path, server)
                result = submit_task(pdf_path, server)
                task_id_mineru = result.get("task_id")

                # 更新 pdf 信息
                pdf["task_server"] = server
                pdf["task_id"] = task_id_mineru
                pdf["status"] = "submitted"

                print(f"✅ 已提交: {pdf.get('name', os.path.basename(pdf_path))} -> task_id={task_id_mineru}")
                submitted_count += 1

            except Exception as e:
                pdf["task_server"] = server
                pdf["task_id"] = None
                pdf["status"] = "failed"
                pdf["error"] = str(e)
                print(f"❌ 提交失败: {pdf.get('name', os.path.basename(pdf_path))} - {e}")
            time.sleep(2)

            # 保存更新后的数据
            with open(pdfs_json, "w", encoding="utf-8") as f:
                json.dump(task_data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 提交完成，共 {submitted_count} 个")
    print(f"📁 已更新: {pdfs_json}")
    print(f"🎉 运行 'python -m pdf2md get-result {task_id}' 获取结果")


def add_parser(subparsers):
    """添加子命令参数"""
    parser = subparsers.add_parser("convert", help="提交PDF到MinerU服务器")
    parser.add_argument("task_id", help="任务ID（data/tasks/目录下的文件夹名）")
    parser.add_argument("-g", "--groups", type=int, default=None,
                        help=f"使用多少个服务器分组（默认: 使用所有{len(MINERU_SERVERS_LIST)}个服务器）")
    return parser
