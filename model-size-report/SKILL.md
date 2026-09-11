---
name: model-size-report
description: "识别 Power BI 模型的内存和刷新风险，包括高基数列、DateTime、GUID、长文本、Double 和过多可见列。"
---

# Model Size Report

这是静态风险筛查，不替代 VertiPaq Analyzer 或真实容量指标。重点检查：

- GUID、交易号、复合字符串键等高基数字段；
- 未拆分的 DateTime；
- Double 类型；
- 长文本和疑似日志字段；
- 单表超过约 30 个可见列；
- 计算列和无关字段。

报告必须包含证据（表/列/类型/命名匹配）和建议验证方式。离线入口：

```powershell
python scripts/audit_model.py <model-or-pbip-path> --check size
```
