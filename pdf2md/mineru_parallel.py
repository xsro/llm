import os
import time
import requests
from .config import MINERU_API_KEY, MINERU_API_URL


def batch_pdf_to_md(pdf_md_pairs: list):
    """批量将多个PDF一次性发送给API转换（使用异步tasks接口）

    Args:
        pdf_md_pairs: [(pdf_path, md_path), ...]

    Returns:
        [(pdf_path, md_path, success, error), ...]
    """
    if not pdf_md_pairs:
        return []

    for pdf_path, _ in pdf_md_pairs:
        if not os.path.exists(pdf_path):
            return [(pdf_path, md_path, False, f"PDF不存在: {pdf_path}") for _, md_path in pdf_md_pairs]

    url = f"{MINERU_API_URL}/tasks"
    headers = {}
    if MINERU_API_KEY:
        headers["Authorization"] = f"Bearer {MINERU_API_KEY}"

    # 提交所有任务
    task_ids = {}
    print(f"🔄 提交 {len(pdf_md_pairs)} 个PDF到MinerU异步任务...")

    for pdf_path, md_path in pdf_md_pairs:
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
                task_ids[task_id] = (pdf_path, md_path)
                print(f"📝 任务已提交: {os.path.basename(pdf_path)} -> task_id={task_id}")
        except Exception as e:
            task_ids["error"] = task_ids.get("error", []) + [(pdf_path, md_path, str(e))]

    if not task_ids or all(k == "error" for k in task_ids):
        return [(pdf_path, md_path, False, error) for pdf_path, md_path, error in task_ids.get("error", [])]

    # 轮询等待所有任务完成
    pending_tasks = list(task_ids.keys())
    completed_results = []

    print(f"⏳ 等待 {len(pending_tasks)} 个任务完成（每1秒检查一次）...")

    while pending_tasks:
        for task_id in pending_tasks[:]:
            try:
                status_url = f"{MINERU_API_URL}/tasks/{task_id}"
                resp = requests.get(status_url, headers=headers, timeout=30)
                resp.raise_for_status()
                status_data = resp.json()
                status = status_data.get("status")

                if status == "completed":
                    pending_tasks.remove(task_id)
                    pdf_path, md_path = task_ids[task_id]

                    # 获取结果
                    result_url = f"{MINERU_API_URL}/tasks/{task_id}/result"
                    resp = requests.get(result_url, headers=headers, timeout=30)
                    resp.raise_for_status()
                    result = resp.json()

                    results = result.get("results", {})
                    if results:
                        md_content = list(results.values())[0].get("md_content")
                        if md_content:
                            with open(md_path, "w", encoding="utf-8") as f:
                                f.write(md_content)
                            completed_results.append((pdf_path, md_path, True, None))
                            print(f"✅ 转换成功: {md_path}")
                        else:
                            completed_results.append((pdf_path, md_path, False, "API返回空MD内容"))
                            print(f"❌ 转换失败 (空内容): {pdf_path}")
                    else:
                        completed_results.append((pdf_path, md_path, False, "API未返回结果"))
                        print(f"❌ 转换失败 (无结果): {pdf_path}")

                elif status == "failed":
                    pending_tasks.remove(task_id)
                    pdf_path, md_path = task_ids[task_id]
                    error_msg = status_data.get("error", "任务执行失败")
                    completed_results.append((pdf_path, md_path, False, error_msg))
                    print(f"❌ 任务失败: {pdf_path} - {error_msg}")

            except Exception as e:
                # 任务可能还在处理中，继续等待
                pass

        if pending_tasks:
            time.sleep(1)

    # 添加之前提交失败的任务结果
    for pdf_path, md_path, error in task_ids.get("error", []):
        completed_results.append((pdf_path, md_path, False, error))

    return completed_results
