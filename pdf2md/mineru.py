import os
import requests
from .config import MINERU_API_KEY, MINERU_API_URL


def pdf_to_md(pdf_path: str, md_path: str):
    """单个PDF转换为MD"""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF不存在: {pdf_path}")

    url = f"{MINERU_API_URL}/file_parse"
    headers = {}
    if MINERU_API_KEY:
        headers["Authorization"] = f"Bearer {MINERU_API_KEY}"

    files = {
        "files": (os.path.basename(pdf_path), open(pdf_path, "rb"), "application/pdf")
    }

    data = {
        "return_md": True,
        "backend": "hybrid-auto-engine",
        "parse_method": "auto",
        "formula_enable": True,
        "table_enable": True,
        "image_analysis": False,
    }

    try:
        print(f"🔄 调用MinerU /file_parse 转换中...")
        resp = requests.post(url, headers=headers, files=files, data=data, timeout=1200)
        resp.raise_for_status()

        result = resp.json()
        results = result.get("results")
        md_content = list(results.values())[0].get("md_content")
        if not md_content:
            raise Exception("API返回空MD内容")

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        print(f"✅ MD保存成功: {md_path}")

    except Exception as e:
        raise Exception(f"MinerU转换失败: {str(e)}")


def batch_pdf_to_md(pdf_md_pairs: list):
    """批量将多个PDF一次性发送给API转换

    Args:
        pdf_md_pairs: [(pdf_path, md_path), ...]

    Returns:
        [(pdf_path, md_path, success, error), ...]
    """
    if not pdf_md_pairs:
        return []

    for pdf_path, _ in pdf_md_pairs:
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF不存在: {pdf_path}")

    url = f"{MINERU_API_URL}/file_parse"
    headers = {}
    if MINERU_API_KEY:
        headers["Authorization"] = f"Bearer {MINERU_API_KEY}"

    # 构造多文件上传
    files = [
        ("files",(os.path.basename(pdf_path), open(pdf_path, "rb"), "application/pdf"))
        for pdf_path, _ in pdf_md_pairs
    ]

    data = {
        "return_md": True,
        "backend": "hybrid-auto-engine",
        "parse_method": "auto",
        "formula_enable": True,
        "table_enable": True,
        "image_analysis": False,
    }

    results = []
    try:
        print(f"🔄 批量发送 {len(pdf_md_pairs)} 个PDF到MinerU...")
        resp = requests.post(
            url,
            headers=headers,
            files=files,
            data=data,
            timeout=12000
        )
        resp.raise_for_status()

        api_results = resp.json().get("results", {})

        for pdf_path, md_path in pdf_md_pairs:
            filename = os.path.basename(pdf_path)
            if filename in api_results:
                md_content = api_results[filename].get("md_content")
                if md_content:
                    with open(md_path, "w", encoding="utf-8") as f:
                        f.write(md_content)
                    results.append((pdf_path, md_path, True, None))
                    print(f"✅ 保存成功: {md_path}")
                else:
                    results.append((pdf_path, md_path, False, "API返回空MD内容"))
                    print(f"❌ 保存失败 (空内容): {pdf_path}")
            else:
                results.append((pdf_path, md_path, False, "API未返回该文件结果"))
                print(f"❌ 未找到结果: {pdf_path}")

    except Exception as e:
        for pdf_path, md_path in pdf_md_pairs:
            results.append((pdf_path, md_path, False, str(e)))
        print(f"❌ 批量API调用失败: {str(e)}")

    finally:
        for f in files:
            f[1].close()

    return results