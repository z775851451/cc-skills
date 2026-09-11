"""Static DAX risk profiler; findings are candidates and require runtime validation."""
from __future__ import annotations

import argparse
import re
from pathlib import Path


PATTERNS = [
    ("warning", r"\bFILTER\s*\(\s*ALL\s*\(", "FILTER(ALL(...)) 可能扩大扫描范围", "确认是否可改为更窄的筛选列或保留过滤上下文。"),
    ("warning", r"\b(SUMX|FILTER|GENERATE|CONCATENATEX)\s*\(", "使用迭代器", "检查迭代对象基数，必要时将逻辑下推或改为存储引擎可处理的聚合。"),
    ("info", r"\bFORMAT\s*\(", "FORMAT 会把结果转换为文本", "优先使用模型格式字符串，避免破坏排序和数值聚合。"),
    ("info", r"\b(CONTAINSSTRING|SEARCH)\s*\(", "字符串搜索可能无法有效利用字典", "确认是否可用维度筛选、精确匹配或源端标准化。"),
    ("warning", r"\bDISTINCT\s*\(", "DISTINCT 可能引入额外去重成本", "确认是否确实需要去重，并比较 VALUES/模型关系方案。"),
    ("info", r"\bCALCULATE\s*\(", "发现 CALCULATE", "检查嵌套过滤器是否重复；结合 Server Timings 验证。"),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    files = [args.path] if args.path.is_file() else [p for p in args.path.rglob("*") if p.suffix.lower() in {".dax", ".tmdl", ".json"}]
    found = 0
    for file in files:
        text = file.read_text(encoding="utf-8-sig", errors="ignore")
        for level, pattern, title, advice in PATTERNS:
            matches = list(re.finditer(pattern, text, re.I))
            if matches:
                found += len(matches)
                lines = [text.count("\n", 0, m.start()) + 1 for m in matches[:5]]
                print(f"[{level.upper()}] {file}:{','.join(map(str, lines))} {title} ({len(matches)} 次)")
                print(f"  建议: {advice}")
    if not found:
        print("未发现静态规则命中；这不代表运行时性能一定良好。请使用 Performance Analyzer 或 DAX Studio 验证。")


if __name__ == "__main__":
    main()
