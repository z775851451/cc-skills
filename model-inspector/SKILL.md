---
name: model-inspector
description: "检查 Power BI 语义模型的表、列、度量值、关系、存储模式和星型模型结构。用户要求审计模型、检查模型健康度或发现结构问题时使用。"
---

# Model Inspector

## Workflow

1. 优先使用 Power BI Modeling MCP：列出连接，连接活动模型，再读取模型、表、列、度量值和关系。
2. 没有可用 MCP 时，使用 `scripts/audit_model.py` 扫描 PBIP/TMDL/JSON 文件。
3. 按 `error`、`warning`、`info` 分级，不把启发式结果描述成确定事实。
4. 检查星型结构、孤立表、双向关系、可见技术键、隐式度量值风险、重复名称和缺失描述。

## 输出

输出模型概览、发现列表（位置、证据、影响、建议）和下一步验证命令。不要在未读取模型元数据时臆测对象名称。
