"""
pdf2mdv2 - PDF to Markdown conversion & RAG upload service

Usage:
    python -m pdf2mdv2 --token <token> [--port 8081] [--mineru http://localhost:8000] [--webui http://127.0.0.1:8080]
"""

import argparse

from .cmd_serve import run


def main():
    parser = argparse.ArgumentParser(
        description="🌐 PDF 转换上传服务",
        formatter_class=argparse.RawDescriptionHelpFormatter
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

    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
