"""
📤 上传命令
将 task 中转换成功的 md 文件上传到 RAG 知识库

用法：
    python -m pdf2md upload <task_id>
"""

import os
import json
import requests
import time
from pathlib import Path
from typing import Optional

# ==================== 配置 ====================
WEBUI_URL = os.getenv("RAG_WEBUI_URL", "http://127.0.0.1:8080")
TOKEN = os.getenv("RAG_TOKEN", "")
KNOWLEDGE_ID = os.getenv("RAG_KNOWLEDGE_ID", "")
UPLOAD_TIMEOUT = 300  # 上传超时时间（秒）
POLL_INTERVAL = 2  # 轮询间隔（秒）


def get_knowledge_files(knowledge_id: str) -> set:
    """获取知识库已存在的文件集合"""
    page = 1
    filenames: set = set()
    print("🔄 正在获取知识库文件列表...")

    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/json"
    }

    while True:
        url = f"{WEBUI_URL}/api/v1/knowledge/{knowledge_id}/files?page={page}"
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        items = resp.json().get("items", [])

        for item in items:
            filenames.add(item["filename"])

        if len(items) == 0:
            break
        page += 1

    return filenames


def upload_file(file_path: str, timeout: int = UPLOAD_TIMEOUT) -> str:
    """上传单个文件，返回 file_id"""
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/json"
    }

    with open(file_path, "rb") as f:
        resp = requests.post(
            f"{WEBUI_URL}/api/v1/files/",
            headers=headers,
            files={"file": f},
            timeout=timeout
        )

    if resp.status_code != 200:
        raise Exception(f"上传失败: {resp.status_code} {resp.text}")

    return resp.json()["id"]


def wait_process_complete(file_id: str, timeout: int = UPLOAD_TIMEOUT) -> None:
    """等待文件处理完成"""
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/json"
    }

    print("  ⏳ 等待文件处理...", end="", flush=True)
    start_time = time.time()

    while time.time() - start_time < timeout:
        resp = requests.get(
            f"{WEBUI_URL}/api/v1/files/{file_id}/process/status",
            headers=headers,
            timeout=30
        )
        status = resp.json().get("status")

        if status == "completed":
            print(" ✅ 完成")
            return
        elif status == "failed":
            raise Exception(f"处理失败: {resp.json().get('error')}")

        time.sleep(POLL_INTERVAL)
        print(".", end="", flush=True)

    raise TimeoutError("文件处理超时")


def add_to_knowledge(file_id: str, knowledge_id: str) -> None:
    """将文件添加到知识库"""
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }

    resp = requests.post(
        f"{WEBUI_URL}/api/v1/knowledge/{knowledge_id}/file/add",
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
        help="📤 上传转换完成的 md 文件到 RAG 知识库"
    )
    parser.add_argument(
        "task_id",
        nargs="?",
        help="Task ID (如 20260514_020444)"
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="初始化配置文件"
    )


def run(task_id: Optional[str] = None, init: bool = False) -> None:
    """执行上传"""
    if init:
        _init_config()
        return

    if not task_id:
        print("❌ 请提供 task_id\n")
        print("用法: python -m pdf2md upload <task_id>")
        return

    if not TOKEN or not KNOWLEDGE_ID:
        print("❌ 请设置环境变量 RAG_TOKEN 和 RAG_KNOWLEDGE_ID")
        print("或运行: python -m pdf2md upload --init")
        return

    task_dir = Path(f"data/tasks/{task_id}")
    pdfs_result_path = task_dir / "pdfs_result.json"
    md_dir = task_dir / "md"

    if not pdfs_result_path.exists():
        print(f"❌ 文件不存在: {pdfs_result_path}")
        return

    # 读取转换结果
    with open(pdfs_result_path, "r", encoding="utf-8") as f:
        pdfs_result = json.load(f)

    # 获取成功转换的 md 文件
    md_files = []
    for entry in pdfs_result.get("pdfs", []):
        if entry.get("status") == "success" and entry.get("md_name"):
            md_files.append({
                "name": entry["md_name"],
                "path": md_dir / entry["md_name"]
            })

    if not md_files:
        print("⚠️  没有找到转换成功的 md 文件")
        return

    print(f"📁 找到 {len(md_files)} 个 md 文件待上传\n")

    # 获取知识库已存在的文件
    existing = get_knowledge_files(KNOWLEDGE_ID)
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
            file_id = upload_file(str(path))
            print(f"  📤 文件已上传，ID: {file_id}")

            wait_process_complete(file_id)
            add_to_knowledge(file_id, KNOWLEDGE_ID)
            print(f"  ✅ 已添加到知识库\n")

            success_count += 1
        except Exception as e:
            print(f"  ❌ {e}\n")
            fail_count += 1

        print(f"  统计: ✅ {success_count} ⏭️  {skip_count} ❌ {fail_count}")

    print(f"\n{'=' * 50}")
    print(f"📊 上传完成: ✅ {success_count} ⏭️  {skip_count} ❌ {fail_count}")


def _init_config() -> None:
    """初始化配置文件"""
    config_path = Path("data/rag_config.json")
    default_config = {
        "webui_url": "http://127.0.0.1:8080",
        "token": "your-token-here",
        "knowledge_id": "your-knowledge-id-here"
    }

    if config_path.exists():
        print(f"📋 配置文件已存在: {config_path}")
        with open(config_path, "r") as f:
            config = json.load(f)
        print(json.dumps(config, indent=2, ensure_ascii=False))
    else:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            json.dump(default_config, f, indent=2, ensure_ascii=False)
        print(f"✅ 已创建配置文件: {config_path}")
        print("请编辑文件填入正确的配置")
