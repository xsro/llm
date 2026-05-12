import os
from urllib.parse import urlparse
import requests
from .config import MINERU_API_KEY,MINERU_API_URL

# ==================== ✅ 新版 /file_parse 接口适配 ====================
def pdf_to_md(pdf_path: str, md_path: str):
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF不存在: {pdf_path}")

    # ✅ 正确接口
    url = f"{MINERU_API_URL}/file_parse"

    headers = {}
    if MINERU_API_KEY:
        headers["Authorization"] = f"Bearer {MINERU_API_KEY}"

    # ✅ 严格按你给的API构造
    files = {
        "files": (os.path.basename(pdf_path), open(pdf_path, "rb"), "application/pdf")
    }

    data = {
        "return_md": True,                # 必须为True，返回markdown
        "backend": "hybrid-auto-engine",             # 默认通用后端
        "parse_method": "auto",
        "formula_enable": True,
        "table_enable": True,
        "image_analysis": False,
    }

    try:
        print(f"🔄 调用MinerU /file_parse 转换中...")
        resp = requests.post(
            url,
            headers=headers,
            files=files,
            data=data,
            timeout=1200
        )
        resp.raise_for_status()

        # ✅ 获取 md
        result = resp.json()
        results = result.get("results")
        md_content =  list(results.values())[0].get("md_content")
        if not md_content:
            raise Exception("API返回空MD内容")

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        print(f"✅ MD保存成功: {md_path}")

    except Exception as e:
        raise Exception(f"MinerU转换失败: {str(e)}")