---
name: unused-column-finder
description: "在 Power BI 模型和 PBIP/TMDL 文件中查找疑似未被关系、度量值或报表引用的列，删除前必须人工确认。"
---

# Unused Column Finder

使用 MCP 时结合模型对象和报表定义检查引用；离线模式仅做启发式扫描。只有同时满足“无关系引用、无度量值引用、无报表文件引用”才可标为候选，扫描不到引用时应标记为 `unknown`，而不是 `unused`。

```powershell
python scripts/audit_model.py <model-or-pbip-path> --check unused
```

删除前确认刷新查询、排序列、层级、书签、RLS、外部报表和 XMLA 客户端没有依赖。
