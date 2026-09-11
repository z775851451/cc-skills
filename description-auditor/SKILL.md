---
name: description-auditor
description: "审计 Power BI 表、列和度量值的描述覆盖率与质量，并生成可执行的文档补全清单。"
---

# Description Auditor

检查表、列和度量值是否有非空描述，识别描述过短、仅重复对象名或包含占位文本的对象。报告覆盖率时分别统计 tables、columns、measures；不要把自动生成的技术字段描述当作业务定义。

在线模式使用 MCP 元数据；离线模式运行：

```powershell
python scripts/audit_model.py <model-or-pbip-path> --check descriptions
```

建议描述说明业务含义、粒度/单位、筛选语义和维护注意事项。
