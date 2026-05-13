import os
import json
import time
import requests
from .config import MINERU_API_KEY, MINERU_API_URL


def _get_headers():
    headers = {}
    if MINERU_API_KEY:
        headers["Authorization"] = f"Bearer {MINERU_API_KEY}"
    return headers


def submit_tasks(pdf_md_pairs: list) -> dict:
    """提交异步转换任务

    Args:
        pdf_md_pairs: [(pdf_path, md_path), ...]

    Returns:
        {task_id: (pdf_path, md_path), ...}
    """
    if not pdf_md_pairs:
        return {}

    headers = _get_headers()
    url = f"{MINERU_API_URL}/tasks"
    task_mapping = {}

    for pdf_path, md_path in pdf_md_pairs:
        if not os.path.exists(pdf_path):
            print(f"❌ PDF不存在: {pdf_path}")
            continue

        try:
            with open(pdf_path, "rb") as f:
                files = {
                    "files": (os.path.basename(pdf_path), f, "application/pdf")
                }
                data = {
                    "return_md": True,
                    "backend": "hybrid-auto-engine",
                    "parse_method": "auto",
                    "formula_enable": True,
                    "table_enable": True,
                    "image_analysis": False,
                }
                resp = requests.post(url, headers=headers, files=files, data=data, timeout=60)
                resp.raise_for_status()
                result = resp.json()
                task_id = result.get("task_id")
                task_mapping[task_id] = (pdf_path, md_path)
                print(f"📝 已提交: {os.path.basename(pdf_path)} -> task_id={task_id}")
        except Exception as e:
            print(f"❌ 提交失败: {pdf_path} - {e}")

    return task_mapping


def poll_and_save_results(task_mapping: dict, poll_interval: int = 1) -> list:
    """轮询任务状态并保存结果

    Args:
        task_mapping: {task_id: (pdf_path, md_path), ...}
        poll_interval: 轮询间隔（秒）

    Returns:
        [(pdf_path, md_path, success, error), ...]
    """
    if not task_mapping:
        return []

    headers = _get_headers()
    url = f"{MINERU_API_URL}/tasks"
    pending = list(task_mapping.keys())
    results = []

    print(f"⏳ 等待 {len(pending)} 个任务完成（每{poll_interval}秒检查一次）...")

    while pending:
        for task_id in pending[:]:
            try:
                resp = requests.get(f"{url}/{task_id}", headers=headers, timeout=30)
                resp.raise_for_status()
                status_data = resp.json()
                status = status_data.get("status")

                if status == "completed":
                    pending.remove(task_id)
                    pdf_path, md_path = task_mapping[task_id]

                    resp = requests.get(f"{url}/{task_id}/result", headers=headers, timeout=30)
                    resp.raise_for_status()
                    result = resp.json()
                    results_data = result.get("results", {})

                    if results_data:
                        md_content = list(results_data.values())[0].get("md_content")
                        if md_content:
                            with open(md_path, "w", encoding="utf-8") as f:
                                f.write(md_content)
                            results.append((pdf_path, md_path, True, None))
                            print(f"✅ 转换成功: {md_path}")
                        else:
                            results.append((pdf_path, md_path, False, "API返回空MD内容"))
                            print(f"❌ 空内容: {pdf_path}")
                    else:
                        results.append((pdf_path, md_path, False, "API未返回结果"))
                        print(f"❌ 无结果: {pdf_path}")

                elif status == "failed":
                    pending.remove(task_id)
                    pdf_path, md_path = task_mapping[task_id]
                    error_msg = status_data.get("error", "任务执行失败")
                    results.append((pdf_path, md_path, False, error_msg))
                    print(f"❌ 任务失败: {pdf_path} - {error_msg}")

            except Exception:
                pass

        if pending:
            time.sleep(poll_interval)

    return results


def save_task_mapping(task_mapping: dict, output_path: str):
    """保存任务映射到文件"""
    serializable = {tid: list(paths) for tid, paths in task_mapping.items()}
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2)


def load_task_mapping(input_path: str) -> dict:
    """从文件加载任务映射"""
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {tid: tuple(paths) for tid, paths in data.items()}
