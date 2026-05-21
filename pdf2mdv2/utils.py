"""
工具函数模块
"""

from difflib import SequenceMatcher
from pathlib import Path


def calculate_similarity(s1: str, s2: str) -> int:
    """计算两个字符串的相似度（0-100）"""
    s1_clean = Path(s1).stem.lower()
    s2_clean = Path(s2).stem.lower()
    s1_clean = "".join(c if c.isalnum() or c.isspace() else " " for c in s1_clean)
    s2_clean = "".join(c if c.isalnum() or c.isspace() else " " for c in s2_clean)
    ratio = SequenceMatcher(None, s1_clean, s2_clean).ratio()
    return int(ratio * 100)
