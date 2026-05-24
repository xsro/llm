"""
MinerU API 客户端

负责：
- 提交 PDF 转换任务
- 轮询等待转换结果
"""

from pathlib import Path
from typing import Optional,List,Tuple

import requests

def get_almost_idle_url(urls):
    health=[]
    for url in urls:
        headers = {}
        try:
            resp = requests.get(
                f"{url}/health",
                headers=headers,
                timeout=60
            )
        except Exception as e:
            continue
        resp_data=resp.json()
        if resp.status_code==200:
            health.append((url,resp_data))
    if len(health)==0:
        return None
    sorted_health=sorted(health,key=lambda x:x[1]['queued_tasks'])
    best_url,best_health=sorted_health[0]
    if best_health['queued_tasks']<2:
        return best_url
    return None
    



def submit_to_mineru(pdf_path: str | List[str], base_url: str, api_key: str = "") -> Tuple[str | List[str], str]:
    """
    提交 PDF 到 MinerU 进行转换，返回 (task_id / task_id列表, base_url)
    - 传入单个str：返回 (单个task_id, base_url)
    - 传入List[str]：返回 (task_id列表, base_url)
    """
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    # 统一处理成列表形式
    if isinstance(pdf_path, str):
        pdf_list = [pdf_path]
    else:
        pdf_list = pdf_path

    # 批量上传文件
    files = []
    for path in pdf_list:
        file_name = Path(path).name
        files.append(
            ("files", (file_name, open(path, "rb"), "application/pdf"))
        )

    data = {
        "return_md": True,
        "backend": "hybrid-auto-engine",
        "parse_method": "auto",
        "formula_enable": True,
        "table_enable": True,
    }

    try:
        resp = requests.post(
            f"{base_url}/tasks",
            headers=headers,
            files=files,
            data=data,
            timeout=60
        )
        resp.raise_for_status()
        result = resp.json()

        # 处理返回结果：单文件/多文件
        task_ids = result.get("task_id", "")
        if isinstance(pdf_path, str):
            # 单个文件返回字符串
            return task_ids[0] if isinstance(task_ids, list) else task_ids, base_url
        else:
            # 多个文件返回列表
            return task_ids, base_url

    finally:
        # 安全关闭所有文件句柄
        for _, (name, fp, mime) in files:
            fp.close()


def wait_mineru_result(mineru_task_id: str, base_url: str, api_key: str = "") -> Optional[str]:
    """轮询等待 MinerU 转换结果，返回 md_content 或 None（仍在处理中）"""
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    resp = requests.get(
        f"{base_url}/tasks/{mineru_task_id}",
        headers=headers,
        timeout=30
    )
    status_data = resp.json()
    status = status_data.get("status")

    if status == "completed":
        result_resp = requests.get(
            f"{base_url}/tasks/{mineru_task_id}/result",
            headers=headers,
            timeout=30
        )
        result = result_resp.json()
        results_data = result.get("results", {})
        first_key = next(iter(results_data), None)
        if first_key is None:
            raise Exception("MinerU 返回空结果")
        return results_data[first_key].get("md_content")

    if status == "failed" or resp.status_code == 404 or resp.status_code == 400:
        e = Exception("MinerU 处理失败")
        e.error = status_data  # type: ignore[attr-defined]
        raise e

    # 仍在处理中
    return None
