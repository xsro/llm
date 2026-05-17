"""
pdf2md - PDF to Markdown conversion tool

Usage:
    python -m pdf2md download <bib_file>
    python -m pdf2md task --init-from folder -f <folder>
    python -m pdf2md convert <task_id>
    python -m pdf2md get-result <task_id>
    python -m pdf2md upload <task_id> --knowledge-id <id>
    python -m pdf2md upload --folder <path> --knowledge-id <id>
    python -m pdf2md serve --token <token> [--port 8081] [--mineru http://localhost:8000]
"""

import argparse

from .cmd_download import add_parser as add_download_parser, run as run_download
from .cmd_task import add_parser as add_task_parser, run as run_task
from .cmd_convert import add_parser as add_convert_parser, run as run_convert
from .cmd_result import add_parser as add_result_parser, run as run_result
from .cmd_upload import add_parser as add_upload_parser, run as run_upload
from .cmd_serve import add_parser as add_serve_parser, run as run_serve


def main():
    parser = argparse.ArgumentParser(
        description="📄 PDF to Markdown conversion tool",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # 注册子命令
    add_download_parser(subparsers)
    add_task_parser(subparsers)
    add_convert_parser(subparsers)
    add_result_parser(subparsers)
    add_upload_parser(subparsers)
    add_serve_parser(subparsers)

    args = parser.parse_args()

    # 执行对应命令
    if args.command == "download":
        run_download(args.bib_file)
    elif args.command == "task":
        run_task(args)
    elif args.command == "convert":
        run_convert(args)
    elif args.command == "get-result":
        run_result(args)
    elif args.command == "upload":
        run_upload(args)
    elif args.command == "serve":
        run_serve(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
