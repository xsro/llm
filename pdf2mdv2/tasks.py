"""
任务状态管理模块

负责：
- 任务字典 (tasks) 的 CRUD
- 线程安全锁 (task_lock)
- 任务持久化到 JSON 文件
- PDF 文件存储
"""

import json
import os
import shutil
import threading
from pathlib import Path
from typing import Optional


# ==================== 全局状态 ====================

tasks: dict = {}
task_lock = threading.Lock()
task_data_dir: Optional[Path] = None


# ==================== 初始化 ====================

def init_task_dir(data_dir: str) -> None:
    """初始化任务数据目录"""
    global task_data_dir
    task_data_dir = Path(data_dir)
    task_data_dir.mkdir(parents=True, exist_ok=True)


# ==================== 持久化 ====================

def _get_tasks_file() -> Path:
    """获取任务数据文件路径"""
    return task_data_dir / "tasks.json"


def save_tasks() -> None:
    """保存任务到文件"""
    with task_lock:
        data = {}
        for tid, info in tasks.items():
            data[tid] = dict(info)

        with open(_get_tasks_file(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def load_tasks() -> None:
    """从文件加载任务，并重置未完成任务为 pending"""
    tasks_file = _get_tasks_file()

    if tasks_file.exists():
        try:
            with open(tasks_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)

            for tid, info in loaded.items():
                tasks[tid] = info
                # 重置未完成任务的状态为 pending
                if info.get("status") in ["queued", "uploading", "failed"]:
                    tasks[tid]["status"] = "pending"
                    tasks[tid]["error"] = None
                    tasks[tid]["progress"] = 0
                    save_tasks()

            print(f"📂 已加载 {len(tasks)} 个历史任务")
        except Exception as e:
            print(f"⚠️  加载任务失败: {e}")


# ==================== PDF 存储 ====================

def save_pdf(task_id: str, file_obj) -> str:
    """保存上传的 PDF 文件到持久化目录"""
    pdf_dir = task_data_dir / "pdfs"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = pdf_dir / f"{task_id}.pdf"
    file_obj.save(str(pdf_path))
    return str(pdf_path)


def save_pdf_from_path(task_id: str, source_path: str) -> str:
    """从已有路径复制 PDF 文件到持久化目录"""
    pdf_dir = task_data_dir / "pdfs"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = pdf_dir / f"{task_id}.pdf"
    shutil.copy2(source_path, str(pdf_path))
    return str(pdf_path)
