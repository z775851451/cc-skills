# 02 · 数据建模与 Power Query

## 1. 星型模型设计输出格式

### 1.1 表清单

| 表 | 类型 | 粒度（一行代表什么） | 主键 | 行数预估 | 存储模式 | 刷新策略 |
|---|---|---|---|---|---|---|
| Fact_Sales | 事实 | 一个订单行 | SalesLineKey | 8000 万 | Import | 增量（按月分区） |
| Dim_Date | 维度 | 一天 | DateKey | 1.1 万 | Import | 全量 |
| Dim_Customer | 维度 | 一个客户 | CustomerKey | 3 万 | Import | 全量 |

### 1.2 关系清单

| 从（多端） | 到（一端） | 基数 | 交叉筛选方向 | 激活 | 备注 |
|---|---|---|---|---|---|
| Fact_Sales[DateKey] | Dim_Date[DateKey] | 多对一 | 单向 | 是 | |
| Fact_Sales[OrderDateKey] | Dim_Date[DateKey] | 多对一 | 单向 | 否 | 角色扮演维度，用 USERELATIONSHIP 或计算组 |

### 1.3 设计规则
- 事实表只保留：外键、数值列、退化维度（如订单号）；其余描述性字段归入维度。
- 角色扮演维度（订单日/发货日/开票日）：优先单一物理日期表 + 非活动关系，需要多上下文时用计算组或 `USERELATIONSHIP`。
- 多对多：优先建桥接表，或改用 `TREATAS`；不要直接把两事实表相连。
- 缓慢变化维：明确 Type 1（覆盖）还是 Type 2（保留历史）；Type 2 需要代理键，事实表存的是代理键。

## 2. Power Query 清洗规范

### 2.1 顺序（决定折叠能否保持）
1. 数据源 → 2. 筛选行（保留可折叠的条件）→ 3. 删除列 → 4. 改类型 → 5. 合并/展开 → 6. 派生列 → 7. 最后再排序。

**关键**：能折叠回源的步骤尽量前置；一旦出现无法折叠的步骤（如自定义函数、Table.Buffer、部分 Group By），后续步骤全部本地执行。

### 2.2 硬规则
- 先"删除其他列"再改类型，减少处理列数。
- 类型显式声明，不依赖自动检测；Decimal 用 `Currency`/`Decimal Number` 视精度需求而定，金额优先 Fixed Decimal。
- 去重前先确认主键；`Table.Distinct` 只保留需要的列，避免全列比对。
- 空值：`Table.ReplaceValue` 或条件列显式处理，不要留 null 进数值列（影响聚合与关系）。
- 合并查询后**只展开需要的列**，展开列名加前缀避免冲突。
- 拆分列：用"按分隔符拆分"并指定拆分数，避免产生不可控列数。
- 参数化：服务器、数据库、日期区间统一走参数表，便于环境迁移。
- 禁用全局"自动日期/时间"（选项 → 数据加载）。
- 不要用 `Table.Buffer` 提速——除非明确知道是在切断折叠以避免重复查询。
-  staging query 设为"禁用加载"，减少内存与刷新耗时。

### 2.3 增量刷新配置要点
```m
// RangeStart / RangeEnd 必须为 date/time 类型参数
= Table.SelectRows(Source, each [OrderDate] >= RangeStart and [OrderDate] < RangeEnd)
```
- 分区粒度：历史按年/月，增量按天。
- 需配合"检测数据更改"时选择更新时间戳列。
- 首次全量刷新耗时要提前评估；发布后不可随意改分区策略（需重刷）。
- 注意：增量刷新 + 查询折叠必须成立，否则退化为全量扫描。

## 3. RLS 行级权限设计

```markdown
| 角色 | 适用人群 | 筛选表 | DAX 表达式 | 说明 |
|---|---|---|---|---|
| 大区经理 | 各区销售负责人 | Dim_Org | `Dim_Org[UserEmail] = USERPRINCIPALNAME()` | 基于组织架构表，支持层级穿透 |
```

配套规则：
- 用户与组织的映射放在**独立的桥接表**（一个用户可对应多个组织节点），不要写在事实表上。
- 层级穿透：用 `PATH()` / `PATHCONTAINS()` 或在维度表预计算 `OrgPath` 列：
  ```dax
  Dim_Org[UserEmail] = USERPRINCIPALNAME()
      || PATHCONTAINS(
             Dim_Org[OrgPath],
             LOOKUPVALUE(Dim_Org[OrgKey], Dim_Org[UserEmail], USERPRINCIPALNAME())
         )
  ```
- 关系必须单向，否则 RLS 会沿双向关系意外扩散到其它维度。
- 验证：Desktop "View as" 同时勾选角色 + 输入用户 → 逐页检查数字；工作区"行级安全性"测试后再发布给业务。
- 风险提示：
  - `USERPRINCIPALNAME()` 在 DirectQuery + SSO 场景行为有差异，需实测。
  - 已发布报表的 RLS 变更需重新验证共享与导出权限。
  - RLS 不防"明细导出"——需要时用 OLS 或禁用导出。

## 4. 数据质量校验规则

生成一组"质检度量值"放在独立表 `_QA` 中，UAT 与日常巡检复用：

```dax
_QA_行数 = COUNTROWS ( Fact_Sales )

_QA_主键重复数 =
COUNTROWS ( Fact_Sales ) - DISTINCTCOUNT ( Fact_Sales[SalesLineKey] )

_QA_空值率_客户 =
DIVIDE (
    COUNTROWS ( FILTER ( Fact_Sales, ISBLANK ( Fact_Sales[CustomerKey] ) ) ),
    COUNTROWS ( Fact_Sales )
)

_QA_负值金额行数 =
COUNTROWS ( FILTER ( Fact_Sales, Fact_Sales[Amount] < 0 ) )

_QA_跨表对账_差异 =
VAR BiAmount  = [Sales_销售额]                    -- 模型口径
VAR SrcAmount = <源系统对账值度量或手填基准>      -- 对账基准
RETURN
    IF ( ISBLANK ( SrcAmount ), BLANK (), BiAmount - SrcAmount )
```

| 校验类型 | 规则 | 阈值建议 | 处理 |
|---|---|---|---|
| 空值 | 关键外键/日期列不允许空 | 0 行 | 阻断刷新或告警 |
| 重复 | 主键唯一 | 0 行 | 阻断 |
| 异常值 | 金额负数、数量 0、日期超范围 | 按业务约定 | 清单化人工确认 |
| 跨表对账 | 与源系统/财务口径差异 | 绝对值 ≤ 约定误差 | 差异说明后方可发布 |
| 完整性 | 日期连续、维度成员无孤儿 | 孤儿键 0 行 | 加"未知成员"行（-1） |

> 孤儿外键处理：ETL 阶段统一补 `Unknown(-1)` 成员，避免关系错误导致行被静默丢弃。
