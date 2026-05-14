"""📝 task 子命令 - 创建转换任务"""

import json
from pathlib import Path

from .config import __proj


def run(args):
    """创建转换任务

    Args:
        args: 命令行参数
    """
    init_type = args.init_from
    task_dir_name = args.task_id if args.init_from == "continue" else None

    # 生成或使用指定的 task_id
    if task_dir_name is None:
        from datetime import datetime
        task_dir_name = datetime.now().strftime("%Y%m%d_%H%M%S")

    task_dir = __proj / "data" / "tasks" / task_dir_name

    if not task_dir.exists():
        task_dir.mkdir(parents=True, exist_ok=True)

    task_json = task_dir / "pdfs.json"

    if init_type == "empty":
        tasks = {"pdfs": [{"path": None, "name": ""}]}
    elif init_type == "folder":
        pdfs = list(Path(args.folder).rglob("*.pdf"))
        tasks = {
            "pdfs": [
                {"path": str(p.absolute()), "name": p.stem}
                for p in pdfs
            ]
        }
    elif init_type == "continue":
        # 继续之前的任务，读取现有数据
        if task_json.exists():
            print(f"📂 继续任务: {task_dir_name}")
            return
        else:
            print(f"❌ 任务不存在: {task_dir_name}")
            return
    else:
        print(f"❌ 未知模式: {init_type}")
        return

    task_json.write_text(json.dumps(tasks, indent=2, ensure_ascii=False),encoding="utf-8")
    print(f"✅ 创建任务: {task_dir_name}")
    print(f"📁 任务目录: {task_dir}")


def add_parser(subparsers):
    """添加子命令参数"""
    parser = subparsers.add_parser("task", help="📝 创建转换任务")
    parser.add_argument("--init-from", "-i", type=str, default="empty",
                        choices=["empty", "folder", "continue"],
                        help="初始化模式: empty(空白), folder(从文件夹), continue(继续)")
    parser.add_argument("--folder", "-f", type=str, default="/home/a422/Downloads/",
                        help="当 init-from=folder 时，指定文件夹路径")
    parser.add_argument("--task-id", "-t", type=str, default=None,
                        help="当 init-from=continue 时，指定任务ID")
    return parser
