"""
🌐 serve 子命令 - 启动 PDF 转换上传服务

功能：
- 用户上传 PDF 文件
- 输入目标知识库 ID
- 自动调用 MinerU API 转换并上传到 RAG 知识库
- 检测文件名重复（完全相同拒绝，高度类似询问）
- 异步任务处理，实时查看进度
- 任务持久化到文件

架构：
- 服务器线程：接收请求，保存 PDF，创建任务（pending），立即返回
- 工作线程（轮询）：
  - pending → converting → converted → uploading → completed/failed
  - MinerU 转换并发执行，RAG 上传串行执行

用法：
    python -m pdf2md serve --port 8081 --mineru http://localhost:8000 --webui http://127.0.0.1:3000 --token xxx
"""

import json
import os
import shutil
import threading
import time
import uuid
from difflib import SequenceMatcher
from pathlib import Path

import requests
from flask import Flask, jsonify, render_template, request

# ==================== 全局变量 ====================
tasks: dict = {}  # task_id -> {status, file_name, knowledge_id, progress, error, created_at, ...}
task_lock = threading.Lock()
task_data_dir: Path = None

# RAG 上传锁（确保串行上传）
rag_upload_lock = threading.Lock()

# 轮询线程控制
poll_running = True


def _get_tasks_file() -> Path:
    """获取任务数据文件路径"""
    return task_data_dir / "tasks.json"



def _save_tasks():
    """保存任务到文件"""
    with task_lock:
        # 序列化的数据（排除不需持久化的字段）
        data = {}
        for tid, info in tasks.items():
            data[tid] = {k: v for k, v in info.items() if k not in []}

        with open(_get_tasks_file(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def _load_tasks():
    """从文件加载任务"""
    global tasks
    tasks_file = _get_tasks_file()

    if tasks_file.exists():
        try:
            with open(tasks_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)

            for tid, info in loaded.items():
                tasks[tid] = info
                # 重置未完成任务的状态为 pending，让工作线程重新处理
                if info.get("status") in ["queued", "converting", "converted", "uploading"]:
                    tasks[tid]["error"] = None
                    tasks[tid]["progress"] = 0
                    _save_tasks()

            print(f"📂 已加载 {len(tasks)} 个历史任务")
        except Exception as e:
            print(f"⚠️  加载任务失败: {e}")


def _save_pdf(task_id: str, file_obj) -> str:
    """保存 PDF 文件到持久化目录"""
    pdf_dir = task_data_dir / "pdfs"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = pdf_dir / f"{task_id}.pdf"
    file_obj.save(str(pdf_path))
    return str(pdf_path)


def _save_pdf_from_path(task_id: str, source_path: str) -> str:
    """从已有路径复制 PDF 文件到持久化目录"""
    pdf_dir = task_data_dir / "pdfs"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = pdf_dir / f"{task_id}.pdf"
    shutil.copy2(source_path, str(pdf_path))
    return str(pdf_path)



# ==================== 工作线程（轮询模式） ====================

def _poll_tasks():
    """轮询线程：检查并处理 pending 和 converted 状态的任务"""
    global poll_running

    print("🔄 工作线程启动（轮询模式）")

    while poll_running:
        try:
            # 获取当前任务快照
            with task_lock:
                working_tasks = [
                    (tid, info) for tid, info in tasks.items()
                    if info.get("status") != "completed"
                ]

            # 处理 pending 任务（调用 MinerU 转换）
            if len(working_tasks)>0:
                tid, info = working_tasks[0]
                _process_conversion(tid)
   

        except Exception as e:
            print(f"⚠️  轮询异常: {e}")

        time.sleep(50)  # 轮询间隔 5 秒


def _process_conversion(task_id: str):
    """处理转换任务（pending → converting → converted/failed）"""
    pdf_path = None

    with task_lock:
        if task_id not in tasks:
            return
        info = tasks[task_id]

    # 如果 pending 那么 convert
    if info.get("status") == "pending" or info.get("status") == "failed":
        # 更新状态为 converting
        with task_lock:
            tasks[task_id]["status"] = "converting"
            tasks[task_id]["progress"] = 10
        pdf_path = info.get("pdf_path")

        try:
            print(f"📄 开始转换: {task_id}")

            # 提交到 MinerU
            mineru_task_id,mineru_url = _submit_to_mineru(pdf_path, use_url=0)

            with task_lock:
                tasks[task_id]["mineru_task_id"] = mineru_task_id
                tasks[task_id]["mineru_url"] = mineru_url
                tasks[task_id]["progress"] = 20
        except Exception as e:
            with task_lock:
                tasks[task_id]["status"] = "failed"
                tasks[task_id]["error"] = str(e)
                tasks[task_id]["progress"] = 0
            print(f"❌ 转换失败: {task_id} - {e}")
    
    elif info.get("status")=="converting":
        with task_lock:
            mineru_url=tasks[task_id].get("mineru_url")
            mineru_task_id=tasks[task_id]["mineru_task_id"]

        if mineru_url is None:
            tasks[task_id]["status"] = "failed"
            tasks[task_id]["error"] = f"url {mineru_url} not found"
        else:
            # 等待转换完成
            pdf_path = info.get("pdf_path")
            md_content = _wait_mineru_result(pdf_path, mineru_task_id, mineru_url)

            # 保存 md 内容
            md_path = Path(pdf_path).with_suffix(".md")
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(md_content)

            with task_lock:
                tasks[task_id]["status"] = "converted"
                tasks[task_id]["md_path"] = str(md_path)
                tasks[task_id]["progress"] = 60

    elif info.get("status")=="converted":
        _process_upload(task_id)
        
    _save_tasks()


def _process_upload(task_id: str):
    """处理上传任务（converted → uploading → completed/failed）"""
    # 使用全局锁确保串行上传
    with rag_upload_lock:
        md_path = None

        with task_lock:
            if task_id not in tasks:
                return
            info = tasks[task_id]
            if info.get("status") != "converted":
                return

            # 更新状态为 uploading
            tasks[task_id]["status"] = "uploading"
            tasks[task_id]["progress"] = 70
            md_path = info.get("md_path")

        _save_tasks()

        try:
            print(f"📤 上传中: {task_id}")

            # 上传到 RAG
            _upload_to_rag(md_path, task_id)

            # 完成
            with task_lock:
                tasks[task_id]["status"] = "completed"
                tasks[task_id]["progress"] = 100
            _save_tasks()


            print(f"✅ 上传完成: {task_id}")

        except Exception as e:
            with task_lock:
                tasks[task_id]["status"] = "failed"
                tasks[task_id]["error"] = str(e)
            _save_tasks()
            print(f"❌ 上传失败: {task_id} - {e}")


# ==================== MinerU API ====================

def _submit_to_mineru(pdf_path: str,use_url=0) -> str:
    """提交到 MinerU API"""
    mineru_urls=app.config['MINERU_URL'].split(",")
    base_url=mineru_urls[use_url]
    headers = {}
    if app.config.get("MINERU_KEY"):
        headers["Authorization"] = f"Bearer {app.config['MINERU_KEY']}"

    with open(pdf_path, "rb") as f:
        files = {"files": (Path(pdf_path).name, f, "application/pdf")}
        data = {
            "return_md": True,
            "backend": "hybrid-auto-engine",
            "parse_method": "auto",
            "formula_enable": True,
            "table_enable": True,
            "image_analysis": True,
        }
        resp = requests.post(
            f"{base_url}/tasks",
            headers=headers,
            files=files,
            data=data,
            timeout=60
        )
        resp.raise_for_status()
        return resp.json()["task_id"],base_url


def _wait_mineru_result(pdf_path: str, mineru_task_id: str, base_url) -> str:
    """轮询等待 MinerU 结果"""
    headers = {}
    if app.config.get("MINERU_KEY"):
        headers["Authorization"] = f"Bearer {app.config['MINERU_KEY']}"

    for _ in range(300):
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
            result=result_resp.json()
            results_data = result.get("results", {})
            md_content = list(results_data.values())[0].get("md_content")
            return md_content

        elif status == "failed":
            raise Exception("MinerU 处理失败")

        time.sleep(2)

    raise TimeoutError("转换超时")


# ==================== RAG API ====================

def _upload_to_rag(md_path: str, task_id: str) -> None:
    """上传到 RAG 知识库"""
    with task_lock:
        info = tasks.get(task_id, {})
        file_name = info.get("file_name", "unknown.md")
        knowledge_id = info.get("knowledge_id", "")

    headers = {
        "Authorization": f"Bearer {app.config['RAG_TOKEN']}",
        "Accept": "application/json"
    }

    with open(md_path, "rb") as f:
        resp = requests.post(
            f"{app.config['RAG_WEBUI_URL']}/api/v1/files/",
            headers=headers,
            files={"file": (file_name, f, "text/markdown")},
            timeout=300
        )
    resp.raise_for_status()
    file_id = resp.json()["id"]

    with task_lock:
        tasks[task_id]["progress"] = 85
    _save_tasks()

    # 等待文件处理完成
    for _ in range(150):
        status_resp = requests.get(
            f"{app.config['RAG_WEBUI_URL']}/api/v1/files/{file_id}/process/status",
            headers=headers,
            timeout=30
        )
        if status_resp.json().get("status") == "completed":
            break
        time.sleep(2)

    # 添加到知识库
    add_resp = requests.post(
        f"{app.config['RAG_WEBUI_URL']}/api/v1/knowledge/{knowledge_id}/file/add",
        headers={**headers, "Content-Type": "application/json"},
        json={"file_id": file_id},
        timeout=30
    )
    add_resp.raise_for_status()


def _get_knowledge_list() -> list:
    """获取知识库列表"""
    try:
        headers = {"Authorization": f"Bearer {app.config['RAG_TOKEN']}"}
        resp = requests.get(
            f"{app.config['RAG_WEBUI_URL']}/api/v1/knowledge/",
            headers=headers,
            timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("items", [])
    except Exception as e:
        print(f"⚠️  获取知识库列表失败: {e}")
        return []


# ==================== Flask 应用 ====================
app = Flask(__name__, template_folder="templates", static_folder="static")


@app.route("/", methods=["GET", "POST"])
def index():
    """主页面"""
    default_knowledge_id = app.config.get("DEFAULT_KNOWLEDGE_ID", "")

    if request.method == "POST":
        # 检查强制上传
        force_upload = request.form.get("force_upload") == "1"
        if force_upload:
            return handle_upload(
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

        # 获取用户输入的文件名（重命名）
        custom_name = request.form.get("custom_name", "").strip()
        if custom_name:
            if not custom_name.lower().endswith(".md"):
                custom_name += ".md"
        else:
            custom_name = Path(file.filename).stem + ".md"

        # 检测文件名重复
        result = check_filename_collision(custom_name, knowledge_id)
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

        # 异步处理
        return handle_upload(custom_name, knowledge_id, file, default_knowledge_id)

    return render_template("upload.html", default_knowledge_id=default_knowledge_id)


def handle_upload(file_name: str, knowledge_id: str, file_obj, default_knowledge_id: str):
    """处理上传 - 异步"""
    # 创建任务
    task_id = str(uuid.uuid4())[:8]

    # 保存 PDF 文件到持久化目录
    pdf_path = _save_pdf(task_id, file_obj)

    with task_lock:
        tasks[task_id] = {
            "status": "pending",
            "file_name": file_name,
            "knowledge_id": knowledge_id,
            "pdf_path": pdf_path,
            "progress": 0,
            "error": None,
            "created_at": time.time()
        }

    print(f"📋 任务已提交: {task_id} - {file_name}")

    return render_template(
        "upload.html",
        success=f"✅ 任务已提交！文件: {file_name}，任务ID: {task_id}",
        default_knowledge_id=default_knowledge_id
    )


@app.route("/api/tasks")
def list_tasks():
    """获取所有任务状态"""
    with task_lock:
        task_list = []
        for tid, info in sorted(tasks.items(), key=lambda x: x[1].get("created_at", 0), reverse=True):
            task_list.append({
                "id": tid,
                "file_name": info["file_name"],
                "status": info["status"],
                "progress": info["progress"],
                "error": info["error"],
                "knowledge_id": info["knowledge_id"]
            })
    return jsonify({"tasks": task_list})


@app.route("/api/tasks/<task_id>")
def get_task(task_id):
    """获取单个任务状态"""
    with task_lock:
        if task_id in tasks:
            return jsonify(tasks[task_id])
        return jsonify({"error": "任务不存在"}), 404


@app.route("/api/tasks/<task_id>/retry", methods=["POST"])
def retry_task(task_id):
    """重试任务"""
    with task_lock:
        if task_id not in tasks:
            return jsonify({"error": "任务不存在"}), 404

        info = tasks[task_id]
        if info["status"] not in ["failed", "completed"]:
            return jsonify({"error": "只能重试失败或已完成的任务"}), 400

        # 重置状态
        tasks[task_id]["status"] = "pending"
        tasks[task_id]["progress"] = 0
        tasks[task_id]["error"] = None

    _save_tasks()
    return jsonify({"success": True, "message": "任务已重新加入队列"})


@app.route("/api/upload-temp", methods=["POST"])
def upload_temp():
    """临时文件上传 API（用于批量上传）"""
    if "file" not in request.files:
        return jsonify({"error": "没有文件"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "文件名为空"}), 400

    # 保存到临时目录
    import tempfile as temp_module
    temp_dir = temp_module.gettempdir()
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

        # 获取临时文件路径（由前端上传）
        pdf_path = file_info.get("pdf_path")

        if not pdf_path or not os.path.exists(pdf_path):
            results.append({
                "task_id": task_id,
                "file_name": custom_name,
                "status": "failed",
                "error": "PDF 文件不存在"
            })
            continue

        # 保存 PDF 到持久化目录
        saved_pdf_path = _save_pdf_from_path(task_id, pdf_path)

        with task_lock:
            tasks[task_id] = {
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

    _save_tasks()
    return jsonify({"success": True, "results": results})


@app.route("/api/knowledge")
def list_knowledge():
    """获取知识库列表"""
    items = _get_knowledge_list()
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


def check_filename_collision(file_name: str, knowledge_id: str) -> dict:
    """检测文件名是否与知识库中的文件重复"""
    result = {
        "identical": False,
        "identical_file": None,
        "similar": False,
        "similar_file": None,
        "similarity": 0,
    }

    try:
        headers = {"Authorization": f"Bearer {app.config['RAG_TOKEN']}"}
        page = 1
        while True:
            resp = requests.get(
                f"{app.config['RAG_WEBUI_URL']}/api/v1/knowledge/{knowledge_id}/files?page={page}",
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

                similarity = _calculate_similarity(file_name, existing_name)
                if similarity >= 80 and similarity > result["similarity"]:
                    result["similar"] = True
                    result["similar_file"] = existing_name
                    result["similarity"] = similarity

            page += 1

    except Exception as e:
        print(f"⚠️  检测文件名冲突失败: {e}")

    return result


def _calculate_similarity(s1: str, s2: str) -> int:
    """计算两个字符串的相似度（0-100）"""
    s1_clean = Path(s1).stem.lower()
    s2_clean = Path(s2).stem.lower()
    s1_clean = "".join(c if c.isalnum() or c.isspace() else " " for c in s1_clean)
    s2_clean = "".join(c if c.isalnum() or c.isspace() else " " for c in s2_clean)
    ratio = SequenceMatcher(None, s1_clean, s2_clean).ratio()
    return int(ratio * 100)


def add_parser(subparsers) -> None:
    """添加子命令参数"""
    parser = subparsers.add_parser(
        "serve",
        help="🌐 启动 PDF 转换上传服务"
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8081,
        help="服务端口 (默认: 8081)"
    )
    parser.add_argument(
        "--mineru",
        type=str,
        default="http://localhost:8000",
        help="MinerU API 地址 (默认: http://localhost:8000)"
    )
    parser.add_argument(
        "--mineru-key",
        type=str,
        default="",
        help="MinerU API Key (可选)"
    )
    parser.add_argument(
        "--webui",
        type=str,
        default="http://127.0.0.1:8080",
        help="RAG WebUI 地址 (默认: http://127.0.0.1:8080)"
    )
    parser.add_argument(
        "--token", "-t",
        type=str,
        required=True,
        help="RAG 认证 Token (必需)"
    )
    parser.add_argument(
        "--knowledge-id", "-k",
        type=str,
        help="默认知识库 ID (可选)"
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data/serve_tasks",
        help="任务数据存储目录 (默认: data/serve_tasks)"
    )


def run(args) -> None:
    """启动服务"""
    global task_data_dir, poll_running

    module_dir = Path(__file__).parent
    template_dir = module_dir / "templates"
    static_dir = module_dir / "static"

    if not template_dir.exists() or not static_dir.exists():
        print("❌ 模板或静态文件目录不存在")
        return

    # 设置任务数据目录
    task_data_dir = Path(args.data_dir)
    task_data_dir.mkdir(parents=True, exist_ok=True)

    app.template_folder = str(template_dir)
    app.static_folder = str(static_dir)

    # 配置
    app.config["MINERU_URL"] = args.mineru
    app.config["MINERU_KEY"] = args.mineru_key
    app.config["RAG_WEBUI_URL"] = args.webui
    app.config["RAG_TOKEN"] = args.token
    app.config["DEFAULT_KNOWLEDGE_ID"] = args.knowledge_id or ""

    # 加载历史任务
    _load_tasks()

    # 启动轮询工作线程
    poll_thread = threading.Thread(target=_poll_tasks, daemon=True)
    poll_thread.start()

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║              🌐 PDF 转换上传服务                             ║
╠══════════════════════════════════════════════════════════════╣
║  MinerU:    {args.mineru:<47} ║
║  RAG WebUI: {args.webui:<47} ║
║  Port:      http://localhost:{args.port:<37} ║
║  Data Dir:  {str(task_data_dir):<47} ║
╠══════════════════════════════════════════════════════════════╣
║  📚 默认知识库:                                               ║
║    Books   - 77e60d66-c754-4c39-9771-300f949eb75c            ║
║    Papers  - 77a41f73-4218-49c2-8ce8-6c4025a918f0            ║
╠══════════════════════════════════════════════════════════════╣
║  📋 API 接口:                                                ║
║    GET /           - 上传页面                                ║
║    GET /tasks      - 任务列表页面                            ║
║    GET /api/tasks  - 所有任务状态 (JSON)                      ║
║    GET /api/tasks/<id> - 单个任务状态 (JSON)                  ║
║    POST /api/tasks/<id>/retry - 重试任务                      ║
╠══════════════════════════════════════════════════════════════╣
║  📊 任务状态流转:                                             ║
║    pending → converting → converted → uploading → completed  ║
║                                            ↘ failed          ║
╚══════════════════════════════════════════════════════════════╝
    """)

    try:
        app.run(host="0.0.0.0", port=args.port, debug=False)
    finally:
        poll_running = False
