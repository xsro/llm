"""
后台工作线程模块

负责：
- 轮询任务队列
- 调度 MinerU 转换（并发）和 RAG 上传（串行）
"""

import threading
import time
from pathlib import Path
import os

from . import tasks as tm
from .mineru import submit_to_mineru, wait_mineru_result
from .rag import upload_to_rag


# ==================== 全局变量 ====================

# RAG 上传锁（确保串行上传）
rag_upload_lock = threading.Lock()

# 轮询线程控制
poll_running = True

# 配置（由 run() 注入）
_mineru_urls: list = []
_mineru_key: str = ""
_webui_url: str = ""
_rag_token: str = ""


# ==================== 初始化 ====================

def init_worker(mineru_urls: list, mineru_key: str, webui_url: str, rag_token: str) -> None:
    """初始化 worker 配置"""
    global _mineru_urls, _mineru_key, _webui_url, _rag_token
    _mineru_urls = mineru_urls
    _mineru_key = mineru_key
    _webui_url = webui_url
    _rag_token = rag_token


# ==================== 轮询主循环 ====================

def poll_loop() -> None:
    """轮询主循环：检查并处理任务"""
    global poll_running

    print("🔄 工作线程启动（轮询模式）")
    index = 0

    while poll_running:
        index += 1
        mineru_url = _mineru_urls[index % len(_mineru_urls)] if _mineru_urls else ""
        try:
            with tm.task_lock:
                todos = [
                    (tid, info) for tid, info in tm.tasks.items()
                    if info.get("status") not in ("completed", "failed")
                ]

            if todos:
                for tid, info in todos[:len(_mineru_urls)]:
                    if not poll_running:
                        break
                    _process_conversion(tid, info, mineru_url)
            else:
                time.sleep(10)

        except Exception as e:
            print(f"⚠️  轮询异常: {e}")

        time.sleep(50)


def _process_conversion(task_id: str, info: dict, mineru_url: str) -> None:
    """处理单个任务的转换/上传流程"""
    status = info.get("status")

    if status == "pending":
        if tm.tasks[task_id].get("md_path") and os.path.exists(tm.tasks[task_id]["md_path"]):
            with tm.task_lock:
                tm.tasks[task_id]["status"] = "converted"
        else:
            _do_convert(task_id, info, mineru_url)
    elif status == "converting":
        _do_wait_result(task_id, info)

    tm.save_tasks()


# ==================== 转换阶段 ====================

def _do_convert(task_id: str, info: dict, mineru_url: str) -> None:
    """执行 MinerU 转换（pending → converting）"""
    with tm.task_lock:
        tm.tasks[task_id]["status"] = "converting"
        tm.tasks[task_id]["progress"] = 10
        pdf_path = info.get("pdf_path")

    try:
        print(f"📄 开始转换: {task_id}")
        mineru_task_id, actual_url = submit_to_mineru(pdf_path, mineru_url, _mineru_key)

        with tm.task_lock:
            tm.tasks[task_id]["mineru_task_id"] = mineru_task_id
            tm.tasks[task_id]["mineru_url"] = actual_url
            tm.tasks[task_id]["progress"] = 20

    except Exception as e:
        with tm.task_lock:
            tm.tasks[task_id]["status"] = "failed"
            tm.tasks[task_id]["error"] = str(e)
            tm.tasks[task_id]["progress"] = 0
        print(f"❌ 转换提交失败: {task_id} - {e}")


def _do_wait_result(task_id: str, info: dict) -> None:
    """等待 MinerU 结果（converting → converted/failed）"""
    with tm.task_lock:
        mineru_url = tm.tasks[task_id].get("mineru_url")
        mineru_task_id = tm.tasks[task_id].get("mineru_task_id")

    if mineru_url is None or mineru_task_id is None:
        with tm.task_lock:
            tm.tasks[task_id]["status"] = "failed"
            tm.tasks[task_id]["error"] = "mineru_url 或 mineru_task_id 缺失"
        return

    pdf_path = info.get("pdf_path")
    try:
        md_content = wait_mineru_result(mineru_task_id, mineru_url, _mineru_key)
    except Exception as e:
        with tm.task_lock:
            tm.tasks[task_id]["status"] = "failed"
            tm.tasks[task_id]["error"] = getattr(e, "error", str(e))
            tm.tasks[task_id]["progress"] = 0
        print(f"❌ 转换等待失败: {task_id} - {e}")
        return

    if md_content is None:
        return

    # 保存 md 内容
    md_path = Path(pdf_path).with_suffix(".md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    with tm.task_lock:
        tm.tasks[task_id]["status"] = "converted"
        tm.tasks[task_id]["md_path"] = str(md_path)
        tm.tasks[task_id]["progress"] = 60

    print(f"✅ 转换完成: {task_id}")


# ==================== 手动上传 ====================

def upload_task(task_id: str) -> str | None:
    """手动触发上传（由用户点击按钮调用）。
    
    返回:
        None - 成功
        错误信息字符串 - 失败
    """
    with tm.task_lock:
        if task_id not in tm.tasks:
            return "任务不存在"
        status = tm.tasks[task_id].get("status")
        if status != "converted":
            return f"任务状态为 {status}，只有转换完成的任务才能上传"

    # 在后台线程中执行上传，避免阻塞 HTTP 请求
    t = threading.Thread(target=_do_upload, args=(task_id,), daemon=True)
    t.start()
    return None


# ==================== 上传阶段 ====================

def _do_upload(task_id: str) -> None:
    """处理上传（converted → uploading → completed/failed），串行执行"""
    with rag_upload_lock:
        md_path = None

        with tm.task_lock:
            if task_id not in tm.tasks:
                return
            info = tm.tasks[task_id]
            if info.get("status") != "converted":
                return

            tm.tasks[task_id]["status"] = "uploading"
            tm.tasks[task_id]["progress"] = 70
            md_path = info.get("md_path")

        tm.save_tasks()

        try:
            print(f"📤 上传中: {task_id} {md_path}")
            upload_to_rag(md_path, task_id, _webui_url, _rag_token)

            with tm.task_lock:
                tm.tasks[task_id]["status"] = "completed"
                tm.tasks[task_id]["progress"] = 100
            tm.save_tasks()

            print(f"✅ 上传完成: {task_id}")

        except Exception as e:
            with tm.task_lock:
                tm.tasks[task_id]["status"] = "failed"
                tm.tasks[task_id]["error"] = str(e)
            tm.save_tasks()
            print(f"❌ 上传失败: {task_id} - {e}")
