"""
RAG API 客户端

负责：
- 上传 Markdown 到 RAG 知识库
- 获取知识库列表
- 检测文件名冲突
"""

import time

import requests

from . import tasks as tm
from .utils import calculate_similarity


def upload_to_rag(md_path: str, task_id: str, webui_url: str, token: str) -> None:
    """上传 Markdown 文件到 RAG 知识库"""
    with tm.task_lock:
        info = tm.tasks.get(task_id, {})
        file_name = info.get("file_name", "unknown.md")
        knowledge_id = info.get("knowledge_id", "")

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }

    # 1) 上传文件
    with open(md_path, "rb") as f:
        resp = requests.post(
            f"{webui_url}/api/v1/files/",
            headers=headers,
            files={"file": (file_name, f, "text/markdown")},
            timeout=300
        )
    resp.raise_for_status()
    file_id = resp.json()["id"]

    with tm.task_lock:
        tm.tasks[task_id]["progress"] = 85
    tm.save_tasks()

    # 2) 等待文件处理完成
    for _ in range(150):
        status_resp = requests.get(
            f"{webui_url}/api/v1/files/{file_id}/process/status",
            headers=headers,
            timeout=30
        )
        if status_resp.json().get("status") == "completed":
            break
        time.sleep(2)

    # 3) 添加到知识库
    add_resp = requests.post(
        f"{webui_url}/api/v1/knowledge/{knowledge_id}/file/add",
        headers={**headers, "Content-Type": "application/json"},
        json={"file_id": file_id},
        timeout=30
    )
    add_resp.raise_for_status()


def get_knowledge_list(webui_url: str, token: str) -> list:
    """获取知识库列表"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(
            f"{webui_url}/api/v1/knowledge/",
            headers=headers,
            timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("items", [])
    except Exception as e:
        print(f"⚠️  获取知识库列表失败: {e}")
        return []


def check_filename_collision(file_name: str, knowledge_id: str, webui_url: str, token: str) -> dict:
    """检测文件名是否与知识库中的文件重复"""
    result = {
        "identical": False,
        "identical_file": None,
        "similar": False,
        "similar_file": None,
        "similarity": 0,
    }

    try:
        headers = {"Authorization": f"Bearer {token}"}
        page = 1
        while True:
            resp = requests.get(
                f"{webui_url}/api/v1/knowledge/{knowledge_id}/files?page={page}",
                headers=headers,
                timeout=30
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])

            if not items:
                break

            for item in items:
                existing_name = item["filename"]

                if existing_name == file_name:
                    result["identical"] = True
                    result["identical_file"] = existing_name
                    return result

                similarity = calculate_similarity(file_name, existing_name)
                if similarity >= 80 and similarity > result["similarity"]:
                    result["similar"] = True
                    result["similar_file"] = existing_name
                    result["similarity"] = similarity

            page += 1

    except Exception as e:
        print(f"⚠️  检测文件名冲突失败: {e}")

    return result
