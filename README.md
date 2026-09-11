# cc-skills

个人 Power BI / Tabular Editor / DAX / Agent 工程技能包,共 **28 个技能**。

## 包含内容

- **Power BI 建模与报表**(~15 个):星型模型、PBIP、PBIR、Power Query、命名规范、报表设计/管理/规划
- **DAX 与性能**(~4 个):DAX 优化、性能分析、模型体积、未使用列
- **Tabular Editor 工具链**(~5 个):C# 脚本、TE CLI、TE2 CLI、TMDL、BPA 规则
- **AI Agent 工程**(~3 个):setup 审计、技能/插件创建、模型检查

完整列表见 [SKILLS.md](./SKILLS.md)。

## 来源

从本地 `~/.cc-switch/skills/` 同步(已解引用软链为真实文件)。

## 更新方式

```bash
cd ~/cc-skills-repo
# 拉取最新
for d in ~/.cc-switch/skills/*/; do
  name=$(basename "$d")
  rm -rf "$name"
  cp -RL "$d" "$name"
done
git add -A && git commit -m "sync" && git push
```
