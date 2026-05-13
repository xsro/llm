"""
📤 知识库文件上传工具
将本地Markdown文件上传到RAG知识库系统

功能：
- 获取知识库已存在的文件列表
- 上传新文件并等待处理完成
- 自动跳过已存在的文件

用法：
    python upload.py
"""

import requests
import time
from pathlib import Path

# ==================== 配置 ====================
WEBUI_URL = 'http://127.0.0.1:8080'
TOKEN = 'sk-85ae27dd7ead4c6e958fbad54dcfb022'
KNOWLEDGE_ID = 'e7b67d14-9b8c-4c09-aa90-1a334932da95'
MD_FOLDER = Path("data/output_md/")
UPLOAD_TIMEOUT = 300  # 上传超时时间（秒）
POLL_INTERVAL = 2  # 轮询间隔（秒）


def get_knowledge_file_page(knowledge_id: str, page: int) -> list:
    """获取知识库文件列表（单页）"""
    url = f"{WEBUI_URL}/api/v1/knowledge/{knowledge_id}/files?page={page}"
    headers = {
        'Authorization': f'Bearer {TOKEN}',
        'Accept': 'application/json'
    }

    response = requests.get(url, headers=headers, timeout=30)
    resp = response.json()

    return [item["filename"] for item in resp["items"]]


def get_knowledge_files(knowledge_id: str) -> list:
    """获取知识库所有已存在的文件"""
    page = 1
    filenames_all = []
    print("🔄 正在获取知识库文件列表...")

    while True:
        filenames = get_knowledge_file_page(knowledge_id, page)
        filenames_all.extend(filenames)
        if len(filenames) == 0:
            break
        page += 1

    return filenames_all


def upload_and_add_to_knowledge(file_path: str, knowledge_id: str, timeout: int = 300) -> dict:
    """
    上传文件并添加到知识库

    Args:
        file_path: 文件路径
        knowledge_id: 知识库ID
        timeout: 超时时间（秒）

    Returns:
        API响应结果
    """
    headers = {
        'Authorization': f'Bearer {TOKEN}',
        'Accept': 'application/json'
    }

    # Step 1: 上传文件
    with open(file_path, 'rb') as f:
        response = requests.post(
            f'{WEBUI_URL}/api/v1/files/',
            headers=headers,
            files={'file': f},
            timeout=timeout
        )

    if response.status_code != 200:
        raise Exception(f"❌ 上传失败: {response.text}")

    file_data = response.json()
    file_id = file_data['id']
    print(f"  📤 文件已上传，ID: {file_id}")

    # Step 2: 等待处理完成
    print("  ⏳ 等待文件处理...", end="", flush=True)
    start_time = time.time()

    while time.time() - start_time < timeout:
        status_response = requests.get(
            f'{WEBUI_URL}/api/v1/files/{file_id}/process/status',
            headers=headers,
            timeout=30
        )
        status_data = status_response.json()
        status = status_data.get('status')

        if status == 'completed':
            print(" ✅ 完成")
            break
        elif status == 'failed':
            raise Exception(f"❌ 处理失败: {status_data.get('error')}")

        time.sleep(POLL_INTERVAL)
        print(".", end="", flush=True)
    else:
        raise TimeoutError("❌ 文件处理超时")

    # Step 3: 添加到知识库
    add_response = requests.post(
        f'{WEBUI_URL}/api/v1/knowledge/{knowledge_id}/file/add',
        headers={**headers, 'Content-Type': 'application/json'},
        json={'file_id': file_id},
        timeout=30
    )

    if add_response.status_code != 200:
        raise Exception(f"❌ 添加到知识库失败: {add_response.text}")

    print(f"  ✅ 已添加到知识库")
    return add_response.json()


# ==================== 主程序 ====================
def main():
    print("=" * 50)
    print("📤 知识库文件上传工具")
    print("=" * 50)

    # 获取已存在的文件
    existing_files = get_knowledge_files(KNOWLEDGE_ID)
    print(f"📋 知识库已有文件: {len(existing_files)} 个\n")

    # 扫描本地文件
    md_files = list(MD_FOLDER.glob("*.md"))
    print(f"📁 本地待上传文件: {len(md_files)} 个\n")

    # 统计
    skip_count = 0
    success_count = 0
    fail_count = 0

    for f in md_files:
        if f.name in existing_files:
            print(f"⏭️  跳过（已存在）: {f.name}")
            skip_count += 1
            continue
        else:
            print(f"📤 正在上传: {f.name}")

            try:
                upload_and_add_to_knowledge(str(f.absolute()), KNOWLEDGE_ID, UPLOAD_TIMEOUT)
                success_count += 1
            except Exception as e:
                print(f"  {e}")
                fail_count += 1
        print(f"  ✅ 成功: {success_count} ⏭️  跳过: {skip_count} ❌ 失败: {fail_count}")


if __name__ == "__main__":
    main()
