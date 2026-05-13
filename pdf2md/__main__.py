"""
📄 pdf2md - PDF转Markdown工具
从BibTeX批量下载PDF并转换为Markdown
"""

import os
import argparse

from .config import MINERU_SERVERS_LIST, OUTPUT_MD_DIR, PDF_CACHE_DIR
from .cmd_download import run as run_download, add_parser as add_download_parser
from .cmd_convert import run as run_convert, add_parser as add_convert_parser
from .cmd_result import run as run_result, add_parser as add_result_parser

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
  python -m pdf2md download papers.bib       # 下载PDF
  python -m pdf2md start-convert papers.bib  # 提交任务（使用所有服务器）
  python -m pdf2md start-convert papers.bib -g 2  # 使用2个服务器分组
  python -m pdf2md start-convert papers.bib -g 1  # 只使用第一个服务器
  python -m pdf2md get-result                # 获取转换结果
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # 注册子命令
    add_download_parser(subparsers)
    add_convert_parser(subparsers)
    add_result_parser(subparsers)

    args = parser.parse_args()

    # 执行对应的命令
    if args.command == "download":
        run_download(args.bib_file)
    elif args.command == "start-convert":
        run_convert(args.bib_file, args.groups)
    elif args.command == "get-result":
        run_result()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
