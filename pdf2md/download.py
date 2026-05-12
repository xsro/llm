import os
from .config import MAX_RETRY
import requests
from .config import DOWNLOAD_TIMEOUT
import time
from requests.exceptions import RequestException

def download_file(url: str, save_path: str):
    """下载文件，支持本地路径直接复制"""
    if os.path.exists(save_path):
        print(f"📄 PDF已存在，跳过下载: {save_path}")
        return

    # 如果是本地文件，直接复制
    if os.path.exists(url):
        with open(url, "rb") as f_in, open(save_path, "wb") as f_out:
            f_out.write(f_in.read())
        print(f"📄 本地文件已复制: {save_path}")
        return

    # 网络下载
    headers = {"User-Agent": "Mozilla/5.0"}
    for retry in range(MAX_RETRY):
        try:
            response = requests.get(url, headers=headers, timeout=DOWNLOAD_TIMEOUT, stream=True)
            response.raise_for_status()
            with open(save_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"✅ 下载完成: {save_path}")
            return
        except RequestException as e:
            print(f"⚠️  下载失败 {retry+1}/{MAX_RETRY}: {str(e)}")
            time.sleep(2)
    raise Exception(f"下载失败，已重试{MAX_RETRY}次")