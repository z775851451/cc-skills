---
name: hermes-update-troubleshoot
description: "诊断并修复 Hermes Agent `hermes update` 失败（exit 1 / UPDATE DIDN'T FINISH / 网关重启失败 / 更新卡住）。触发词：hermes update 失败、更新没跑完、UPDATE DIDN'T FINISH、Hermes is still running、网关重启失败、debug share、更新卡住、Hermes 突然关闭并更新。"
---

# Hermes Update 故障排查

只做诊断与恢复建议。**不要**在 WorkBuddy 里代跑 `hermes update` 或 `hermes gateway restart` —— 连 `dangerouslyDisableSandbox: true` 也不行（原因见「沙箱边界」，实测会把网关子进程搞崩）。

## 第一步：先判断「还在跑」还是「已经失败」

**最常见的误判来源**：`apps/desktop/node_modules` 或 `update.log` 看似静止，其实构建仍在继续（npm/vite 输出有缓冲）。用这三个信号交叉验证，缺一不可：

```bash
H="$LOCALAPPDATA/hermes"          # Windows: C:\Users\<u>\AppData\Local\hermes
# 1. 进行中标记（存在 = 更新未结束）
cat "$H/.hermes-update-in-progress"        # 内容两行：PID + epoch 秒
# 2. 主日志是否还在增长
stat -c '%y' "$H/logs/update.log"
# 3. 构建产物是否在动（比日志更可信）
stat -c '%y' "$H/hermes-agent/apps/desktop/node_modules"
stat -c '%y' "$H/hermes-agent/apps/desktop/dist"
```

- **marker 存在 + 任一时间戳在增长** → 还在跑，**什么都别做，等**。desktop 构建可耗时 10 分钟以上，期间 `update.log` 会长时间停在 `vite build ... transforming...`，这是正常的。
- **marker 消失** → 该次已结束。读 `logs/update_receipts/latest.json`：它有 `outcome`(`succeeded`/`failed`)、`exit_code`、`stop_reason`、逐步 `steps`。**成功和失败都会写**，不是只写成功 —— 用 `outcome` 判断，别靠 mtime 是否存在。

### 顺手先答用户的第一个问题：「为什么它自己关了还开始更新？」

原始线索在 `logs/desktop.log`：

```
[hermes] [bootstrap] handed off bootstrap-needed recovery to updater:
         hermes-setup.exe --update --branch main; exiting desktop to release app.asar
```

这是**设计行为，不是崩溃**：桌面端检测到需要 bootstrap 级恢复（要释放 `app.asar` 才能重建），于是**主动退出**并把更新交接给 `hermes-setup.exe`。用户看到的「突然关闭 + 突然开始更新」就是这一行。别把它当故障去排查。

## 第二步：区分失败模式

日志优先级：`logs/update.log`（主）→ `logs/bootstrap-installer.log`（**桌面端 UI 弹的报错对应它，不是 update.log**）→ `logs/desktop-update-handoff.log`（桌面端交接）→ `logs/gateway-stdio.log`（网关子进程原始 stdio）。

### 模式 A：网络出口问题（可瞬断，也可持续劣化）

```
✗ Network error — cannot reach the remote repository.
  fatal: unable to access '...': Failure when receiving data from the peer
  # 或：Failed to connect to 127.0.0.1 port 7897 ... Couldn't connect to server
  # 或：OpenSSL SSL_connect: SSL_ERROR_SYSCALL in connection to github.com:443
```

本机靠 Clash Verge 出网（mixed-port `7897`，走 TUN fake-ip + 环境变量 `HTTP_PROXY`/`HTTPS_PROXY`；git 自身没配 `http.proxy`）。`Failure when receiving data from the peer` = TCP 通了但节点中途断流，属**节点劣化**，不是配置坏。

⚠️ **判定必须在提权（`dangerouslyDisableSandbox: true`）下做**。沙箱内 curl 到 github 会**恒定 5.00s 超时**（假失败），会把好网络误判成坏的：

```bash
# 提权执行，抽样 10 次
for i in $(seq 1 10); do curl -sS -o /dev/null -w "%{http_code} " \
  --max-time 12 -x http://127.0.0.1:7897 https://github.com; done; echo
# 再直接复现更新那一步
cd "$LOCALAPPDATA/hermes/hermes-agent" && git fetch --progress origin main
```

- 10/10 + fetch 成功 ⇒ 网络已恢复（原先只是瞬断），**直接恢复运行时即可，不必重跑更新**。
- 持续失败 ⇒ 定位到具体节点，见下。

**定位坏节点（mihomo 命名管道）**：Verge 的 `external-controller` 是空串，实际是命名管道 `\\.\pipe\verge-mihomo`（`config.yaml` 里那个 `127.0.0.1:9097` 不通，别去 curl 它）。用 `ctypes` 打开管道发 HTTP：

```
GET /proxies                        → 全部节点/组状态（组的 now = 当前选中）
GET /proxies/{组名}/delay?timeout=8000&url={quote(url,safe='')}
  → 该组/该节点对特定 URL 的真实连通性（比 ping 更能定位“能不能到 github”）
```

```python
import ctypes, ctypes.wintypes as wt
k = ctypes.WinDLL("kernel32", use_last_error=True)
k.CreateFileW.restype = wt.HANDLE
h = k.CreateFileW(r"\\.\pipe\verge-mihomo", 0xC0000000, 0, None, 3, 0, None)
req = b"GET /proxies HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n"
w = wt.DWORD(); k.WriteFile(h, req, len(req), ctypes.byref(w), None)
buf = ctypes.create_string_buffer(65536); r = wt.DWORD(); out = b""
while k.ReadFile(h, buf, 65536, ctypes.byref(r), None) and r.value:
    out += buf.raw[:r.value]
k.CloseHandle(h)
body = out.split(b"\r\n\r\n", 1)[1]        # 注意可能是 chunked
```

本次实测：`github.com` 的规则是 `DOMAIN-SUFFIX,github.com,🚀节点选择`；组选中 `♻️自动选择`（URLTest）；逐节点 delay 探测显示 8 个候选节点**全部 245–316ms 可达** github ⇒ 节点没坏，属瞬断。

- 处置：网络已恢复就重跑；确实持续劣化则在 Clash Verge 里换节点（`🚀节点选择`）。

### 模式 B：网关重启未被验证存活（上游 #48820）

```
⚠ Windows gateway restart could not be verified — no stable gateway process appeared after relaunch.
  (The respawned gateway may have been killed by a parent Job Object during updater teardown, #48820.)
RuntimeError: Windows gateway relaunch after update was not verified alive
```

更新器 teardown 时，respawn 的 gateway 被父 Job Object 一并回收。**代码与依赖其实已经更新完成**，只是最后一步验证失败导致 exit 1 + 桌面端弹「UPDATE DIDN'T FINISH」。

- 处置：`hermes gateway restart`（冷启动路径通常成功，日志会打 `✓ Gateway started via cold-start after update`）。
- 这是 Hermes 已知缺陷，不必为此上传 `hermes debug share`。
- 常与模式 A 叠加：fetch 失败后仍会走到收尾的网关验证，于是 UI 只显示「didn't finish」，容易掩盖真正的 fetch 错误。**先看 `update.log` 里第一个 ✗ 是什么。**

### 模式 C：venv 被占用，更新拒绝执行

```
✗ Other Hermes processes are running from this install's venv:
  PID 122888  python.exe  ...venv\Scripts\python.exe -m hermes_cli.main update --yes --gateway ...
  On Windows these keep native extension files (.pyd) locked, so the
  dependency update would fail partway and leave a broken install.
```

桌面端 UI 显示为 **「Hermes is still running. Close all Hermes windows and try the update again.」** —— 注意文案只说"关窗口"，**真正的元凶是残留的 update 进程**，光关窗口没用。

- 成因：上一次更新**还在跑**时又点了 Retry update，两次更新重叠。
- 处置：确认无 update 进程后再重试。查进程（**别用带 `^` 锚点的 grep 匹配 `/FO CSV` 输出，行以引号开头会全部漏掉**）：

```bash
tasklist /FO CSV /NH | grep -i "python.exe\|Hermes.exe"
# 需要命令行时用 CIM（PowerShell 的 Get-Process 可能因会话隔离看不到目标进程）
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Select ProcessId,CreationDate,CommandLine
```

  看到 `hermes_cli.main update` 且创建时间较早的进程 = 残留。等它结束或结束它，再重跑。
- 注意：命令文本里出现 `wscript` / `wmic` 等字样会被沙箱按 LOLBin 整条拦截，换个写法（例如别把它们写进 `grep` 模式）。

### 模式 D：网关子进程 `ModuleNotFoundError: No module named 'yaml'`

`logs/gateway-stdio.log` 里出现：

```
  File "...\hermes_cli\config.py", line 24, in <module>
    import yaml
ModuleNotFoundError: No module named 'yaml'
```

**这不代表 venv 坏了**。先证明 venv 是好的：

```bash
V="$LOCALAPPDATA/hermes/hermes-agent/venv/Scripts/python.exe"
"$V" -c "import yaml; print(yaml.__version__)"     # 正常应输出 6.0.x
```

若 venv 正常，则几乎总是**调用方 shell 的环境污染**：WorkBuddy 的 shell 里带着
`PYTHONPATH=D:\...\WorkBuddy\resources\app.asar.unpacked\cli\vendor\shim` 与 11 个 `CODEBUDDY_SAFE_DELETE_*`，被网关子进程继承后 venv 解析被破坏。`dangerouslyDisableSandbox: true` **不会**剥掉这些变量，所以照样崩。

- 判据：用干净 env 复现同一条启动命令就正常存活 ——
  ```bash
  cd "$LOCALAPPDATA/hermes" && env -u PYTHONPATH \
    HERMES_HOME="$LOCALAPPDATA/hermes" VIRTUAL_ENV="$LOCALAPPDATA/hermes/hermes-agent/venv" \
    PYTHONPATH="$LOCALAPPDATA/hermes/hermes-agent" \
    "$LOCALAPPDATA/hermes/hermes-agent/venv/Scripts/python.exe" -m hermes_cli.main gateway run
  ```
- 处置：让**用户在自己的终端**里跑 `hermes gateway restart`。不要因为"提权了"就以为可以在 WorkBuddy 里代跑。

## 关键教训

- **两类"更新"按钮别混为一谈**：桌面端**托盘图标 / 通知里的「更新」**是**手动更新入口**——点它会主动关闭 app 并跑 `hermes update`，是设计行为（对应 `desktop.log` 的 `handed off bootstrap-needed recovery`），**当本地确实落后、网络健康时就该点**。而**「UPDATE DIDN'T FINISH」报错框上的「Retry update」**是另一回事：本地已最新 / 网络还没恢复时点了毫无意义，且收尾常再撞 #48820。判据：`git rev-list --count HEAD..origin/main` 为 0 或 `git fetch` 仍失败 ⇒ 别点 Retry，直接恢复运行时。
- **绝不要在更新进行中重复触发更新**（点 Retry / 再跑 `hermes update`）。重叠的 update 进程互相锁 venv，把一次可自愈的失败升级成模式 C 的死结。UI 弹「didn't finish」时，先按第一步确认是否其实还在跑。
- **先判断"是否真的需要更新"**：网络恢复后跑
  ```bash
  git -C "$LOCALAPPDATA/hermes/hermes-agent" rev-list --count HEAD..origin/main
  ```
  为 `0` ⇒ 本地已是最新，本次「更新」本无事可做。此时**不要重跑更新**（重跑仍会在 #48820 收尾处再报一次），直接恢复运行时：重启网关 + 启动桌面端。
- 失败发生在 fetch 阶段时**不会改动任何文件**：`latest.json` 的 `steps` 只有 `sibling_profile_snapshots` / `pre_update_backup` 两项、无代码步骤 ⇒ venv 与代码完好，不必修复安装。
- 「UPDATE DIDN'T FINISH」这个画面**建议直接关掉，不要点 Retry update** —— 除非已确认网络恢复且本地确实落后。

## 沙箱边界（WorkBuddy 内不可代劳的部分）

- 沙箱用 Windows **Job Object** 隔离命令，命令退出即回收子进程 ⇒ `hermes gateway restart` 起的网关活不过命令结束（本次实测：报告 `✓ Gateway started via direct spawn (PID …)`，随后进程消失）。这正是 #48820 的同类现象。
- 即使 `dangerouslyDisableSandbox: true`，shell 仍带 `PYTHONPATH` / `CODEBUDDY_SAFE_DELETE_*` 污染 ⇒ 网关子进程崩在 `import yaml`（模式 D）。
- **GUI 也拉不起来**：`explorer.exe <Hermes.exe>` 与 `cmd //c start "" Hermes.exe` 都返回 0/1 但进程不存活。启动桌面端这一步只能交给用户双击。
- safe-delete 垫片把删除重定向到回收站、单轮超阈值中断 ⇒ 外部安装器/更新器的清理步骤会失败退出。
- 结论：`hermes update` / `hermes gateway restart` / 启动 `Hermes.exe` **一律交给用户在自己的终端执行**。WorkBuddy 内只做只读诊断 + 网络提权复测。

## 恢复步骤（交给用户，按序执行）

1. 关掉「UPDATE DIDN'T FINISH」窗口（点 Cancel 或右上角关闭，**别点 Retry update**）。
2. 在**自己的终端**（不是 WorkBuddy 里）执行：

   ```
   "%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\hermes.exe" gateway restart
   ```

3. 启动桌面端：开始菜单快捷方式，或

   ```
   "%LOCALAPPDATA%\hermes\hermes-agent\apps\desktop\release\win-unpacked\Hermes.exe"
   ```

4. （可选）确认网络已好：`git -C "%LOCALAPPDATA%\hermes\hermes-agent" fetch origin main`
   —— 通且 `rev-list --count HEAD..origin/main` 为 0 就不必再跑更新。

## 恢复后的验证清单

```bash
cat "$LOCALAPPDATA/hermes/gateway_state.json"   # gateway_state=running / exit_reason=null
"$LOCALAPPDATA/hermes/hermes-agent/venv/Scripts/hermes.exe" --version
cd "$LOCALAPPDATA/hermes/hermes-agent" && git log -1 --format='%h %ad %s' --date=iso
```

更新成功会自行 relaunch 桌面端；确认 `Hermes.exe` 已起来即可。若 `gateway_state.json` 仍是
`"gateway_state":"stopped"` 且没有 `python.exe` 在跑，说明网关又没起来，回到模式 D。
