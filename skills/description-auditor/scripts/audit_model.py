"""Heuristic offline audit for Power BI JSON/TMDL/PBIP model files."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def files_for(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return [p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in {".json", ".bim", ".tmdl"}]


def load_json_files(files: list[Path]) -> list[tuple[Path, Any]]:
    result = []
    for file in files:
        if file.suffix.lower() not in {".json", ".bim"}:
            continue
        try:
            result.append((file, json.loads(file.read_text(encoding="utf-8-sig"))))
        except (OSError, json.JSONDecodeError):
            continue
    return result


def walk(value: Any, key: str = ""):
    if isinstance(value, dict):
        yield value, key
        for child_key, child in value.items():
            yield from walk(child, child_key)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child, key)


def model_objects(documents):
    tables = []
    relationships = []
    measures = []
    for _, doc in documents:
        for obj, key in walk(doc):
            if key == "tables" and isinstance(obj, dict):
                tables.extend(obj.get("items", obj.get("tables", [])) if isinstance(obj.get("items", obj.get("tables", [])), list) else [])
            if key == "relationships" and isinstance(obj, list):
                relationships.extend(obj)
            if key == "measures" and isinstance(obj, list):
                measures.extend(obj)
    return tables, relationships, measures


def text_files(files):
    return [(p, p.read_text(encoding="utf-8-sig", errors="ignore")) for p in files if p.suffix.lower() == ".tmdl"]


def emit(level: str, subject: str, evidence: str, recommendation: str):
    print(f"[{level.upper()}] {subject}\n  证据: {evidence}\n  建议: {recommendation}")


def audit(path: Path, checks: set[str]):
    files = files_for(path)
    docs = load_json_files(files)
    tmdl = text_files(files)
    tables, relationships, measures = model_objects(docs)
    names = {str(t.get("name", "")) for t in tables if isinstance(t, dict)}
    print(f"模型路径: {path}\n扫描文件: {len(files)}\nJSON/BIM 文档: {len(docs)}\n")

    if "structure" in checks:
        if not tables and not tmdl:
            emit("warning", "未识别到模型表", "没有找到可解析的 JSON/BIM tables 或 TMDL", "确认输入是 PBIP 根目录、model.bim 或 TMDL 目录。")
        for table in tables:
            table_name = table.get("name", "<unnamed>")
            columns = table.get("columns", [])
            visible = [c for c in columns if not c.get("isHidden", c.get("hidden", False))]
            if len(visible) > 30:
                emit("warning", f"表 {table_name} 可见列过多", f"{len(visible)} 个可见列", "评估是否应拆分维度或隐藏技术字段。")
        if relationships and any(r.get("crossFilteringBehavior") in {"BothDirections", "Both"} for r in relationships if isinstance(r, dict)):
            emit("warning", "存在双向关系", "关系元数据包含 BothDirections/Both", "仅在业务语义确实需要时保留，并检查歧义路径。")

    if "descriptions" in checks:
        for table in tables:
            table_name = table.get("name", "<unnamed>")
            if not str(table.get("description", "")).strip():
                emit("warning", f"表 {table_name} 缺少描述", "description 为空", "补充表用途、粒度和刷新语义。")
            for kind in ("columns", "measures"):
                for obj in table.get(kind, []) or []:
                    if not str(obj.get("description", "")).strip():
                        emit("warning", f"{table_name}.{obj.get('name', '<unnamed>')} 缺少描述", f"{kind} 对象 description 为空", "补充业务含义、单位和筛选语义。")

    if "size" in checks:
        for table in tables:
            for col in table.get("columns", []) or []:
                name = str(col.get("name", ""))
                dtype = str(col.get("dataType", col.get("type", ""))).lower()
                if re.search(r"guid|uuid|transaction.?id|composite|hash", name, re.I):
                    emit("warning", f"疑似高基数列 {table.get('name')}.{name}", "列名匹配高基数标记", "确认是否仅用于关系；优先使用整数代理键。")
                if "datetime" in dtype or "datetime" in name.lower():
                    emit("info", f"DateTime 风险 {table.get('name')}.{name}", "类型或名称包含 DateTime", "若无需时间粒度，拆分为 Date 与 Time 或在源端降粒度。")
                if dtype == "double":
                    emit("warning", f"Double 类型 {table.get('name')}.{name}", "dataType=Double", "优先评估 Decimal 或 Int64，避免精度和压缩问题。")

    if "unused" in checks:
        references = "\n".join(text for _, text in tmdl)
        for table in tables:
            for col in table.get("columns", []) or []:
                name = str(col.get("name", ""))
                qualified = f"{table.get('name')}.{name}"
                if name and name not in references and qualified not in references:
                    emit("info", f"疑似未引用列 {qualified}", "在扫描到的 TMDL 文本中未找到引用", "仅作为候选；确认报表、RLS、排序列和外部依赖后再删除。")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--check", choices=["all", "structure", "descriptions", "size", "unused"], default="all")
    args = parser.parse_args()
    checks = {"structure", "descriptions", "size", "unused"} if args.check == "all" else {args.check}
    audit(args.path, checks)


if __name__ == "__main__":
    main()
