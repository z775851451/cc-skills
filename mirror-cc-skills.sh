#!/usr/bin/env bash
# cc-skills 镜像脚本 (Windows → z775851451/cc-skills)
# 用法: bash mirror-cc-skills.sh
# 功能: 把 ~/.cc-switch/skills mirror 到本仓库并 push

set -euo pipefail
cd "$(dirname "$0")" || exit 1

SRC='C:/Users/Lenovo/.cc-switch/skills'

# 先拉远端
git pull --rebase --autostash >/dev/null 2>&1 || true

# 镜像 (排除 .git,Windows 资源管理器/WSL 隐藏文件)
if command -v robocopy.exe >/dev/null 2>&1; then
  robocopy "$SRC" "./" /MIR /XD .git /XF ".DS_Store" "Thumbs.db" /NFL /NDL /NJH /NJS /NP /NC /NS >/dev/null
  rc=$?
  [ $rc -ge 8 ] && { echo "⚠️  robocopy 失败 rc=$rc"; exit 1; }
else
  cp -ru "$SRC"/. ./
fi

# 提交推送
git add -A
if git diff --cached --quiet; then
  echo "✅ cc-skills 无变更"
  exit 0
fi
git commit -m "mirror cc-skills: $(date '+%Y-%m-%d %H:%M:%S')" >/dev/null
if git push 2>&1 | tail -3; then
  echo "🎉 cc-skills 推上去了"
else
  echo "⚠️  push 失败"
  exit 1
fi
