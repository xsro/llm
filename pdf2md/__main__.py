"""
📄 pdf2md - PDF转Markdown工具 调用mineru
"""

import os
import argparse

from .config import MINERU_SERVERS_LIST, OUTPUT_MD_DIR, PDF_CACHE_DIR
from .cmd_task import run_create_task
from .cmd_convert import run as run_convert, add_parser as add_parser_convert
from .cmd_result import run as run_result

# 创建必要的目录
os.makedirs(OUTPUT_MD_DIR, exist_ok=True)
os.makedirs(PDF_CACHE_DIR, exist_ok=True)


def main():
    parser = argparse.ArgumentParser(
        description="📄 PDF转Markdown工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
可用服务器: {MINERU_SERVERS_LIST or ['http://localhost:8000']}

示例:
  python -m pdf2md task --init papers.bib       # 从bib文件创建下载任务
  python -m pdf2md task --init empty           # 创建空白下载任务
  python -m pdf2md convert # 提交任务（使用所有服务器）
  python -m pdf2md get-result                # 获取转换结果
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # 注册任务创建子命令
    parser1 = subparsers.add_parser("task", help="提交任务")
    parser1.add_argument("-i","--init-from",type=str,help="empty for empty task, folder for read folder",default="empty")
    parser1.add_argument("--folder",type=str,help="if init_from set as fs pass folder to here",default="/home/a422/Downloads/")

    add_parser_convert(subparsers)

    args = parser.parse_args()
    print(args)

    # 执行对应的命令
    if args.command == "task":
        run_create_task(args.init_from,args)
    elif args.command == "convert":
        run_convert(args)
    elif args.command == "get-result":
        run_result()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
