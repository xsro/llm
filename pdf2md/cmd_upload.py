"""
📤 上传命令
将 md 文件上传到 RAG 知识库

用法：
    python -m pdf2md upload <task_id> --knowledge_id <id>
    python -m pdf2md upload --folder <path> --knowledge_id <id>
"""

import os
import json
import requests
import time
from pathlib import Path
from typing import Optional


def get_knowledge_files(webui_url: str, token: str, knowledge_id: str) -> set:
    """获取知识库已存在的文件集合"""
    page = 1
    filenames: set = set()
    print("🔄 正在获取知识库文件列表...")

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }

    while True:
        url = f"{webui_url}/api/v1/knowledge/{knowledge_id}/files?page={page}"
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        items = resp.json().get("items", [])

        for item in items:
            filenames.add(item["filename"])

        if len(items) == 0:
            break
        page += 1

    return filenames


def upload_file(webui_url: str, token: str, file_path: str,filename=None) -> str:
    """上传单个文件，返回 file_id"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    if filename is None:
        filename=os.path.basename(file_path)

    with open(file_path, "rb") as f:
        resp = requests.post(
            f"{webui_url}/api/v1/files/",
            headers=headers,
            files={"file": (filename, f, "application/pdf")},
            timeout=300
        )

    if resp.status_code != 200:
        raise Exception(f"上传失败: {resp.status_code} {resp.text}")

    return resp.json()["id"]


def wait_process_complete(webui_url: str, token: str, file_id: str) -> None:
    """等待文件处理完成"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }

    print("  ⏳ 等待文件处理...", end="", flush=True)

    for _ in range(150):  # 最多等待 5 分钟
        resp = requests.get(
            f"{webui_url}/api/v1/files/{file_id}/process/status",
            headers=headers,
            timeout=30
        )
        status = resp.json().get("status")

        if status == "completed":
            print(" ✅ 完成")
            return
        elif status == "failed":
            raise Exception(f"处理失败: {resp.json().get('error')}")

        time.sleep(2)
        print(".", end="", flush=True)

    raise TimeoutError("文件处理超时")


def add_to_knowledge(webui_url: str, token: str, file_id: str, knowledge_id: str) -> None:
    """将文件添加到知识库"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    resp = requests.post(
        f"{webui_url}/api/v1/knowledge/{knowledge_id}/file/add",
        headers=headers,
        json={"file_id": file_id},
        timeout=30
    )

    if resp.status_code != 200:
        raise Exception(f"添加到知识库失败: {resp.status_code} {resp.text}")


def add_parser(subparsers) -> None:
    """添加子命令参数"""
    parser = subparsers.add_parser(
        "upload",
        help="📤 上传 md 文件到 RAG 知识库"
    )
    parser.add_argument(
        "task_id",
        nargs="?",
        help="Task ID (如 20260514_020444)"
    )
    parser.add_argument(
        "--folder", "-f",
        type=str,
        help="直接上传文件夹中的所有 md 文件"
    )
    parser.add_argument(
        "--knowledge-id", "-k",
        type=str,
        required=True,
        help="RAG 知识库 ID"
    )
    parser.add_argument(
        "--webui-url",
        type=str,
        default=os.getenv("RAG_WEBUI_URL", "http://127.0.0.1:8080"),
        help="RAG WebUI 地址"
    )
    parser.add_argument(
        "--token",
        type=str,
        default=os.getenv("RAG_TOKEN", ""),
        help="RAG 认证 Token"
    )
    parser.add_argument(
        "--sleep",
        type=int,
        default=10,
        help="每次上传中间等待的秒数"
    )


def run(args) -> None:
    """执行上传"""
    task_id = args.task_id
    folder = args.folder
    knowledge_id = args.knowledge_id
    webui_url = args.webui_url
    token = args.token

    if not knowledge_id:
        print("❌ 请提供 --knowledge-id")
        return

    if not token:
        print("❌ 请提供 --token 或设置环境变量 RAG_TOKEN")
        return

    md_files = []

    # 从 task 读取 md 文件
    if task_id:
        task_dir = Path(f"data/tasks/{task_id}")
        pdfs_result_path = task_dir / "pdfs_result.json"
        md_dir = task_dir / "md"

        if not pdfs_result_path.exists():
            print(f"❌ 文件不存在: {pdfs_result_path}")
            return

        with open(pdfs_result_path, "r", encoding="utf-8") as f:
            pdfs_result = json.load(f)

        for entry in pdfs_result.get("pdfs", []):
            if entry.get("status") == "completed" and entry.get("name"):
                md_files.append({
                    "name": entry["name"],
                    "path": md_dir / (entry["task_id"] + ".md")
                })

    # 从文件夹读取 md 文件
    if folder:
        folder_path = Path(folder)
        if not folder_path.exists():
            print(f"❌ 文件夹不存在: {folder}")
            return

        for md_file in folder_path.rglob("*.md"):
            md_files.append({
                "name": md_file.name,
                "path": md_file
            })

    if not md_files:
        print("⚠️  没有找到 md 文件")
        return

    print(f"📁 找到 {len(md_files)} 个 md 文件待上传\n")

    # 获取知识库已存在的文件
    existing = get_knowledge_files(webui_url, token, knowledge_id)
    print(f"📋 知识库已有文件: {len(existing)} 个\n")

    # 统计
    skip_count = 0
    success_count = 0
    fail_count = 0

    for item in md_files:
        name = item["name"]
        path = item["path"]

        if not path.exists():
            print(f"⚠️  文件不存在: {path}")
            fail_count += 1
            continue

        if name in existing:
            print(f"⏭️  跳过（已存在）: {name}")
            skip_count += 1
            continue

        print(f"📤 上传: {name}")

        try:
            file_id = upload_file(webui_url, token, str(path),filename=name+".md")
            print(f"  📤 文件已上传，ID: {file_id}")

            wait_process_complete(webui_url, token, file_id)
            add_to_knowledge(webui_url, token, file_id, knowledge_id)
            print(f"  ✅ 已添加到知识库\n")

            success_count += 1
        except Exception as e:
            print(f"  ❌ {e}\n")
            fail_count += 1

        print(f"  统计: ✅ {success_count} ⏭️  {skip_count} ❌ {fail_count}")
        time.sleep(args.sleep)

    print(f"\n{'=' * 50}")
    print(f"📊 上传完成: ✅ {success_count} ⏭️  {skip_count} ❌ {fail_count}")
