"""
Flask 路由模块

所有 HTTP 路由以工厂函数形式注册，避免循环依赖。
"""

import os
import tempfile
import time
import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from . import tasks as tm
from . import worker as wk
from .rag import get_knowledge_list, check_filename_collision


def _webui_url() -> str:
    """获取 RAG WebUI URL（延迟从 app.config 读取）"""
    from flask import current_app
    return current_app.config["RAG_WEBUI_URL"]


def _rag_token() -> str:
    """获取 RAG Token"""
    from flask import current_app
    return current_app.config["RAG_TOKEN"]


def register_routes(app: Flask) -> None:
    """注册所有路由到 Flask 应用"""

    @app.route("/", methods=["GET", "POST"])
    def index():
        """主页面"""
        default_knowledge_id = app.config.get("DEFAULT_KNOWLEDGE_ID", "")

        if request.method == "POST":
            return _handle_post(default_knowledge_id)

        return render_template("upload.html", default_knowledge_id=default_knowledge_id)

    @app.route("/api/tasks")
    def list_tasks():
        """获取所有任务状态"""
        with tm.task_lock:
            task_list = [
                {
                    "id": tid,
                    "file_name": info["file_name"],
                    "status": info["status"],
                    "progress": info.get("progress"),
                    "error": info.get("error"),
                    "knowledge_id": info["knowledge_id"],
                    "created_at": info.get("created_at", 0)
                }
                for tid, info in sorted(
                    tm.tasks.items(),
                    key=lambda x: x[1].get("created_at", 0),
                    reverse=True
                )
            ]
        return jsonify({"tasks": task_list})

    @app.route("/api/tasks/<task_id>")
    def get_task(task_id):
        """获取单个任务状态"""
        with tm.task_lock:
            if task_id in tm.tasks:
                return jsonify(tm.tasks[task_id])
            return jsonify({"error": "任务不存在"}), 404

    @app.route("/api/tasks/<task_id>/retry", methods=["POST"])
    def retry_task(task_id):
        """重试任务"""
        with tm.task_lock:
            if task_id not in tm.tasks:
                return jsonify({"error": "任务不存在"}), 404

            info = tm.tasks[task_id]
            if info["status"] not in ["failed", "completed"]:
                return jsonify({"error": "只能重试失败或已完成的任务"}), 400

            tm.tasks[task_id]["status"] = "pending"
            tm.tasks[task_id]["progress"] = 0
            tm.tasks[task_id]["error"] = None

        tm.save_tasks()
        return jsonify({"success": True, "message": "任务已重新加入队列"})

    @app.route("/api/tasks/<task_id>/upload", methods=["POST"])
    def upload_to_rag(task_id):
        """手动上传到 RAG（仅 converted 状态可调用）"""
        error = wk.upload_task(task_id)
        if error:
            return jsonify({"error": error}), 400
        return jsonify({"success": True, "message": "上传任务已启动"})

    @app.route("/api/upload-temp", methods=["POST"])
    def upload_temp():
        """临时文件上传 API（用于批量上传）"""
        if "file" not in request.files:
            return jsonify({"error": "没有文件"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "文件名为空"}), 400

        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, f"pdf2md_temp_{uuid.uuid4().hex[:8]}.pdf")
        file.save(temp_path)

        return jsonify({"success": True, "path": temp_path})

    @app.route("/api/batch-upload", methods=["POST"])
    def batch_upload():
        """批量上传 API"""
        data = request.get_json()

        if not data:
            return jsonify({"error": "请求数据格式错误"}), 400

        files = data.get("files", [])
        knowledge_id = data.get("knowledge_id", "")

        if not files:
            return jsonify({"error": "没有文件"}), 400

        if not knowledge_id:
            return jsonify({"error": "请选择知识库"}), 400

        results = []

        for file_info in files:
            task_id = str(uuid.uuid4())[:8]
            original_name = file_info.get("name", "unknown.pdf")
            custom_name = file_info.get("custom_name", "").strip()

            if custom_name:
                if not custom_name.lower().endswith(".md"):
                    custom_name += ".md"
            else:
                custom_name = Path(original_name).stem + ".md"

            pdf_path = file_info.get("pdf_path")

            if not pdf_path or not os.path.exists(pdf_path):
                results.append({
                    "task_id": task_id,
                    "file_name": custom_name,
                    "status": "failed",
                    "error": "PDF 文件不存在"
                })
                continue

            saved_pdf_path = tm.save_pdf_from_path(task_id, pdf_path)

            with tm.task_lock:
                tm.tasks[task_id] = {
                    "status": "pending",
                    "file_name": custom_name,
                    "knowledge_id": knowledge_id,
                    "pdf_path": saved_pdf_path,
                    "progress": 0,
                    "error": None,
                    "created_at": time.time()
                }

            results.append({
                "task_id": task_id,
                "file_name": custom_name,
                "status": "pending"
            })

            print(f"📋 批量任务已提交: {task_id} - {custom_name}")

        tm.save_tasks()
        return jsonify({"success": True, "results": results})

    @app.route("/api/knowledge")
    def list_knowledge():
        """获取知识库列表"""
        items = get_knowledge_list(_webui_url(), _rag_token())
        return jsonify({
            "items": [
                {
                    "id": item["id"],
                    "name": item["name"],
                    "description": item.get("description", "")
                }
                for item in items
            ]
        })

    @app.route("/tasks")
    def tasks_page():
        """任务列表页面"""
        return render_template("tasks.html")


# ==================== 辅助函数 ====================

def _handle_post(default_knowledge_id: str):
    """处理 POST 上传请求"""
    # 强制上传（相似文件名警告后点击"仍然上传"）
    force_upload = request.form.get("force_upload") == "1"
    if force_upload:
        return _create_upload_task(
            request.form.get("custom_name"),
            request.form.get("knowledge_id") or request.form.get("knowledge_id_custom"),
            request.files.get("file"),
            default_knowledge_id
        )

    # 获取文件
    if "file" not in request.files:
        return render_template("upload.html", error="请选择文件", default_knowledge_id=default_knowledge_id)

    file = request.files["file"]
    if file.filename == "":
        return render_template("upload.html", error="请选择文件", default_knowledge_id=default_knowledge_id)

    # 获取知识库 ID
    knowledge_id = request.form.get("knowledge_id") or request.form.get("knowledge_id_custom")
    if not knowledge_id:
        return render_template("upload.html", error="请选择或输入知识库 ID", default_knowledge_id=default_knowledge_id)

    # 获取重命名
    custom_name = request.form.get("custom_name", "").strip()
    if custom_name:
        if not custom_name.lower().endswith(".md"):
            custom_name += ".md"
    else:
        custom_name = Path(file.filename).stem + ".md"

    # 检测文件名重复
    result = check_filename_collision(custom_name, knowledge_id, _webui_url(), _rag_token())
    if result["identical"]:
        return render_template(
            "upload.html",
            error=f"❌ 文件名完全相同，知识库中已存在：{result['identical_file']}",
            default_knowledge_id=default_knowledge_id,
            prefill_name=custom_name
        )

    if result["similar"]:
        return render_template(
            "upload.html",
            warning={
                "existing": result["similar_file"],
                "current": custom_name,
                "similarity": result["similarity"],
                "knowledge_id": knowledge_id,
            },
            default_knowledge_id=default_knowledge_id,
            prefill_name=custom_name
        )

    return _create_upload_task(custom_name, knowledge_id, file, default_knowledge_id)


def _create_upload_task(file_name: str, knowledge_id: str, file_obj, default_knowledge_id: str):
    """创建异步上传任务"""
    task_id = str(uuid.uuid4())[:8]
    pdf_path = tm.save_pdf(task_id, file_obj)

    with tm.task_lock:
        tm.tasks[task_id] = {
            "status": "pending",
            "file_name": file_name,
            "knowledge_id": knowledge_id,
            "pdf_path": pdf_path,
            "progress": 0,
            "error": None,
            "created_at": time.time()
        }

    tm.save_tasks()

    print(f"📋 任务已提交: {task_id} - {file_name}")

    return render_template(
        "upload.html",
        success=f"✅ 任务已提交！文件: {file_name}，任务ID: {task_id}",
        default_knowledge_id=default_knowledge_id
    )
