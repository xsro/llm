"""
🌐 serve 子命令 - 启动 PDF 转换上传服务

服务启动入口，负责：
- 创建 Flask 应用并注入配置
- 初始化各模块（tasks / worker / routes）
- 启动后台轮询线程

用法：
    python -m pdf2mdv2 --token xxx [--port 8081] [--mineru http://localhost:8000]
"""

import threading
from pathlib import Path

from flask import Flask

from . import tasks as tm
from . import worker as wk
from .routes import register_routes


# ==================== Flask 应用实例 ====================

app = Flask(__name__, template_folder="templates", static_folder="static")


def run(args) -> None:
    """启动服务"""
    module_dir = Path(__file__).parent
    template_dir = module_dir / "templates"
    static_dir = module_dir / "static"

    if not template_dir.exists() or not static_dir.exists():
        print("❌ 模板或静态文件目录不存在")
        return

    app.template_folder = str(template_dir)
    app.static_folder = str(static_dir)

    # ---- 配置注入 ----
    app.config["MINERU_URL"] = args.mineru
    app.config["MINERU_KEY"] = args.mineru_key
    app.config["RAG_WEBUI_URL"] = args.webui
    app.config["RAG_TOKEN"] = args.token
    app.config["DEFAULT_KNOWLEDGE_ID"] = args.knowledge_id or ""

    # ---- 初始化 tasks ----
    tm.init_task_dir(args.data_dir)
    tm.load_tasks()

    # ---- 初始化 worker ----
    mineru_urls = args.mineru.split(",")
    wk.init_worker(mineru_urls, args.mineru_key, args.webui, args.token)

    # ---- 注册路由 ----
    register_routes(app)

    # ---- 启动后台线程 ----
    poll_thread = threading.Thread(target=wk.poll_loop, daemon=True)
    poll_thread.start()

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║              🌐 PDF 转换上传服务                             ║
╠══════════════════════════════════════════════════════════════╣
║  MinerU:    {args.mineru:<47} ║
║  RAG WebUI: {args.webui:<47} ║
║  Port:      http://localhost:{args.port:<37} ║
║  Data Dir:  {str(tm.task_data_dir):<47} ║
╠══════════════════════════════════════════════════════════════╣
║  📋 API 接口:                                                ║
║    GET /                   - 上传页面                       ║
║    GET /tasks              - 任务列表页面                   ║
║    GET /api/tasks          - 所有任务状态 (JSON)            ║
║    GET /api/tasks/<id>     - 单个任务状态 (JSON)            ║
║    GET /api/knowledge      - 知识库列表 (JSON)              ║
║    POST /api/upload-temp   - 临时文件上传                  ║
║    POST /api/batch-upload  - 批量任务提交                  ║
║    POST /api/tasks/<id>/retry  - 重试任务                   ║
║    POST /api/tasks/<id>/upload - 手动上传到 RAG              ║
╠══════════════════════════════════════════════════════════════╣
║  📊 任务状态流转:                                             ║
║    pending → converting → converted (等待手动上传)              ║
║    converted → uploading → completed (点击上传按钮触发)         ║
║                                            ↘ failed          ║
╚══════════════════════════════════════════════════════════════╝
    """)

    try:
        app.run(host="0.0.0.0", port=args.port, debug=False)
    finally:
        wk.poll_running = False
