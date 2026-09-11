---
name: perf-profiler
description: "分析 Power BI DAX、TMDL/PBIP 模型和 MCP 查询结果中的性能风险，并制定可验证的优化方案。"
---

# Power BI Performance Profiler

## Workflow

1. 先确认用户关心的是刷新、模型内存还是查询响应时间。
2. 在线时使用 MCP 获取模型统计、关系、列类型、度量值和 DAX；离线时运行 `scripts/profile_dax.py`。
3. 先定位证据，再提出改动；不要凭函数名称断言实际慢。
4. 对每条建议给出验证方法：DAX Studio/Performance Analyzer、刷新时长、查询计划或模型大小。

## 高风险模式

- 迭代器在大事实表上逐行执行；
- 对整表 `FILTER`、重复 `CALCULATE` 或不必要的 `DISTINCT`；
- 计算列可下推却留在模型中；
- 双向关系、many-to-many 和高基数文本键；
- `FORMAT`、字符串转换或 `CONTAINSSTRING` 用于大规模度量计算。

```powershell
python scripts/profile_dax.py <model-or-dax-file>
```
