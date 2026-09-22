---
name: scope-recall-status
description: "一键检查 Scope Recall 在 Codex 上的安装与运行状态。触发词：scope recall 状态、scope recall 安装状态、记忆服务状态、查一下 scope recall、记忆召回状态。"
---

# Scope Recall 状态检查

用户要求查看 Scope Recall / 记忆服务状态时，运行一键面板：

```powershell
& "C:\Users\Lenovo\.codex\scope-recall\sr-status.ps1"
```

输出内容：版本对齐、语义嵌入/提炼路由开关、任务队列、worker 最近运行、向量库、预算账本消费、MCP 进程存活。

## 常见问题对照

| 现象 | 处理 |
|---|---|
| 包版本与回执版本不一致 | 重跑 apply-install 或对齐回执版本号 |
| 待处理/失败 > 0 | 手动跑 worker：`& "C:\Users\Lenovo\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe" -m scope_recall.runtime.worker_entry --config "C:\Users\Lenovo\sr-upgrade\codex-instance\data\runtime-config.json" --env-file "C:\Users\Lenovo\.codex\scope-recall.env"` |
| MCP 服务进程未运行 | 提示用户重启 Codex |
| 深度体检 | `& "C:\Users\Lenovo\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe" -m scope_recall.maintenance.cli doctor --host codex --instance-root "C:\Users\Lenovo\sr-upgrade\codex-instance"` |

## 注意

- 实例根目录：`C:\Users\Lenovo\sr-upgrade\codex-instance`（Codex config.toml 实际连接的实例）
- 插件目录：`C:\Users\Lenovo\.codex\plugins\scope-recall`（v3.1.2）
- 语义召回重启后前 1-2 次可能因嵌入延迟超时，属正常现象，重试即可
