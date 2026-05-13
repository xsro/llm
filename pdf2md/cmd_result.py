"""📊 get-result 子命令 - 获取转换结果"""

import json
import os
import time
import requests

from .config import __proj
from .miner import _get_headers


def run(task_id: str, poll_interval: int = 1):
    """获取MinerU任务转换结果

    Args:
        task_id: 任务ID（目录名）
        poll_interval: 轮询间隔（秒）
    """
    # 加载 task
    task_dir = __proj / "data" / "tasks" / task_id
    if not task_dir.exists():
        print(f"❌ 任务目录不存在: {task_dir}")
        return

    pdfs_json = task_dir / "pdfs.json"
    if not pdfs_json.exists():
        print(f"❌ pdfs.json 不存在: {pdfs_json}")
        return

    # 读取数据
    with open(pdfs_json, "r", encoding="utf-8") as f:
        task_data = json.load(f)

    pdfs = task_data.get("pdfs", [])
    for pdf in pdfs:
        task_id_mineru = pdf.get("task_id")
        server = pdf.get("task_server")
        headers = _get_headers(server)
        base_url = f"{server}/tasks"

        try:
            resp = requests.get(f"{base_url}/{task_id_mineru}", headers=headers, timeout=30)
            resp.raise_for_status()
            status_data = resp.json()
            status = status_data.get("status")

            if status == "completed":
                # 获取结果
                resp = requests.get(f"{base_url}/{task_id_mineru}/result", headers=headers, timeout=30)
                resp.raise_for_status()
                result = resp.json()
                results_data = result.get("results", {})

                if results_data:
                    md_content = list(results_data.values())[0].get("md_content")
                    if md_content:
                        pdf["status"] = "completed"
                        mdpath=task_dir.joinpath("md/"+task_id_mineru+".md")
                        if not mdpath.parent.exists():
                            mdpath.parent.mkdir()
                        if not mdpath.exists():
                            mdpath.write_text(md_content)
                        print(f"✅ 完成: {pdf.get('name', '')}")
                    else:
                        pdf["status"] = "empty_content"
                        pdf["error"] = "API返回空MD内容"
                        print(f"❌ 空内容: {pdf.get('name', '')}")
                else:
                    pdf["status"] = "no_result"
                    pdf["error"] = "API未返回结果"
                    print(f"❌ 无结果: {pdf.get('name', '')}")


            elif status == "failed":
                pdf["status"] = "failed"
                pdf["error"] = status_data.get("error", "任务执行失败")
                print(f"❌ 失败: {pdf.get('name', '')} - {pdf['error']}")

        except Exception as e:
            # 网络错误等，继续等待
            pass

    # 保存结果
    result_file = task_dir / "pdfs_result.json"
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(task_data, f, ensure_ascii=False, indent=2)

    # 统计
    completed = sum(1 for p in pdfs if p.get("status") == "completed")
    failed = sum(1 for p in pdfs if p.get("status") in ("failed", "no_result", "empty_content", "no_task_id"))

    print(f"\n✅ 全部完成！")
    print(f"📊 结果: {completed} 成功, {failed} 失败")
    print(f"📁 已保存: {result_file}")


def add_parser(subparsers):
    """添加子命令参数"""
    parser = subparsers.add_parser("get-result", help="获取MinerU转换结果")
    parser.add_argument("task_id", help="任务ID（data/tasks/目录下的文件夹名）")
    parser.add_argument("-i", "--interval", type=int, default=1,
                        help="轮询间隔（秒，默认1）")
    return parser
