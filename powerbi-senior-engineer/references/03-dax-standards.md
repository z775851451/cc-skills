# 03 · DAX 开发规范

## 1. 命名规范

| 对象 | 规则 | 示例 |
|---|---|---|
| 度量值 | `业务域_指标名_逻辑类型`，统一放独立度量值表（如 `_度量值`） | `Sales_销售额_MTD` |
| 计算列 | 名称后不加后缀，但**描述字段**必填「计算列 - 业务含义」 | `Dim_Product[毛利层级]` |
| 逻辑类型后缀 | `_MTD/_QTD/_YTD/_YoY/_MoM/_PY/_R3M/_占比/_排名/_累计` | `Inv_库存_期末` |
| 变量 | 有业务含义的驼峰英文，不用 a/b/c | `VAR CurPeriodRev` |
| 表 | `Fact_`/`Dim_`/`Bridge_`/`_度量值`/`_参数`/`_QA` 前缀 | `Bridge_UserOrg` |

- 度量值表为一列隐藏占位表，度量值挂在其上；底层数值列全部隐藏。
- 禁止同名度量值散落多表；禁止中文英文混排的随意缩写。

## 2. 代码规范（12 条）

1. `VAR` 拆分逻辑，任何被多次引用的表达式必须提为变量。
2. 关键步骤单行注释，注释写**为什么**而不是**是什么**。
3. 缩进 4 空格；单行不超过 100 字符，超长换行。
4. 逗号前置或后置必须全文统一（推荐前置，便于注释单行）。
5. 除法一律 `DIVIDE()`，显式给出第三参数时用业务默认值（通常是 `BLANK()` 而非 0）。
6. 表引用用 `'表名'[列名]` 完整形式，列名始终带表名，日期表可省略。
7. 布尔筛选优先于 `FILTER`；确需 `FILTER` 时，只迭代**小表/维度表**。
8. 空值/空集先短路：`IF ( ISBLANK ( x ), BLANK (), ... )`，避免无效大计算。
9. 禁止 `EARLIER`，用 `VAR` 代替。
10. 禁止 `IFERROR` 包裹整段；只包真正可能异常的最小表达式。
11. 时间智能必须作用于已 Mark as Date Table 的日期表。
12. 计算列里禁止 `CALCULATE`（上下文转换 → 循环引用），改用 `RELATED` / `LOOKUPVALUE`。

### 度量值注释模板

```dax
// 业务域：销售 | 口径：已出库、含税、排除取消单 | 粒度：订单行
// 依赖：Fact_Sales[Amount_TaxInc]、Dim_Date | 维护人：xxx | 变更记录：2026-09-08 新增
Sales_销售额 = SUM ( Fact_Sales[Amount_TaxInc] )
```

## 3. 场景代码库

### 3.1 基础聚合与累计

```dax
Sales_销售额 = SUM ( Fact_Sales[Amount_TaxInc] )

Sales_销售额_MTD =
CALCULATE ( [Sales_销售额], DATESMTD ( 'Dim_Date'[Date] ) )

Sales_销售额_YTD =
CALCULATE ( [Sales_销售额], DATESYTD ( 'Dim_Date'[Date], "12/31" ) )  -- 财年非自然年时指定年末日期

Sales_销售额_累计 =
CALCULATE (
    [Sales_销售额],
    'Dim_Date'[Date] <= MAX ( 'Dim_Date'[Date] ),
    REMOVEFILTERS ( 'Dim_Date' )
)
```

### 3.2 同比 / 环比 / 同期累计

```dax
Sales_销售额_PY =
CALCULATE ( [Sales_销售额], SAMEPERIODLASTYEAR ( 'Dim_Date'[Date] ) )

Sales_销售额_YoY% =
VAR Cur  = [Sales_销售额]
VAR Prev = [Sales_销售额_PY]
RETURN
    IF ( NOT ISBLANK ( Cur ) && NOT ISBLANK ( Prev ), DIVIDE ( Cur - Prev, Prev ) )
-- 双边非空判断，避免新区域/新品首年出现 -100% 或无限大

Sales_销售额_MoM% =
VAR Cur  = [Sales_销售额]
VAR Prev = CALCULATE ( [Sales_销售额], DATEADD ( 'Dim_Date'[Date], -1, MONTH ) )
RETURN
    IF ( NOT ISBLANK ( Cur ) && NOT ISBLANK ( Prev ), DIVIDE ( Cur - Prev, Prev ) )

Sales_销售额_PY_YTD =
CALCULATE ( [Sales_销售额], DATESYTD ( SAMEPERIODLASTYEAR ( 'Dim_Date'[Date] ), "12/31" ) )
```

### 3.3 滚动均值

```dax
Sales_销售额_R3M =
VAR EndDate   = MAX ( 'Dim_Date'[Date] )
VAR WinStart  = EOMONTH ( EndDate, -3 ) + 1
VAR WinEnd    = EOMONTH ( EndDate, 0 )
VAR Days      = CALCULATE ( DISTINCTCOUNT ( 'Dim_Date'[Date] ),
                    'Dim_Date'[Date] >= WinStart && 'Dim_Date'[Date] <= WinEnd )
RETURN
    DIVIDE (
        CALCULATE ( [Sales_销售额],
            'Dim_Date'[Date] >= WinStart && 'Dim_Date'[Date] <= WinEnd ),
        Days
    ) * 30.44   -- 归一化到"月均"，避免月末天数差异导致波动
-- 现代写法：Power BI 2022+ 可用 WINDOW() 按月份粒度滚动，可读性更好
```

### 3.4 排名与占比

```dax
Sales_销售额_占比 =
DIVIDE ( [Sales_销售额], CALCULATE ( [Sales_销售额], ALLSELECTED () ) )
-- ALLSELECTED 保留外部切片器；若要占全局用 ALL()

Sales_销售额_排名 =
IF (
    NOT ISBLANK ( [Sales_销售额] ),
    RANKX ( ALLSELECTED ( Dim_Customer[CustomerName] ), [Sales_销售额],, DESC, DENSE )
)
-- 加 ISBLANK 短路，防止空行占榜

Sales_销售额_TopN贡献 =
VAR TopNSet = TOPN ( 10, ALLSELECTED ( Dim_Customer[CustomerName] ), [Sales_销售额] )
RETURN
    CALCULATE ( [Sales_销售额], TopNSet )
```

### 3.5 分摊 / 分配

```dax
Cost_总部费用_按收入分摊 =
VAR TotalCost = CALCULATE ( [Cost_总部费用], REMOVEFILTERS ( Dim_Product ) )
VAR CurRev    = [Sales_销售额]
VAR AllRev    = CALCULATE ( [Sales_销售额], REMOVEFILTERS ( Dim_Product ) )
RETURN
    DIVIDE ( CurRev, AllRev ) * TotalCost
-- 注意：分摊基数与分摊对象必须是同一移除筛选范围，否则合计不等于 TotalCost
```

### 3.6 层级聚合（组织架构 / 父子层级）

```dax
Sales_销售额_含下级 =
VAR CurKey = SELECTEDVALUE ( Dim_Org[OrgKey] )
RETURN
    CALCULATE (
        [Sales_销售额],
        REMOVEFILTERS ( Dim_Org ),
        FILTER ( ALL ( Dim_Org[OrgPath] ), PATHCONTAINS ( Dim_Org[OrgPath], CurKey ) )
    )
-- 依赖维度表预计算列：OrgPath = PATH(Dim_Org[OrgKey], Dim_Org[ParentKey])
```

### 3.7 半累加（库存 / 余额）

```dax
Inv_库存_期末 = LASTNONBLANKVALUE ( 'Dim_Date'[Date], SUM ( Fact_Inventory[Qty] ) )
Inv_库存_期初 = FIRSTNONBLANKVALUE ( 'Dim_Date'[Date], SUM ( Fact_Inventory[Qty] ) )
Inv_库存_日均 =
AVERAGEX ( VALUES ( 'Dim_Date'[Date] ), CALCULATE ( SUM ( Fact_Inventory[Qty] ) ) )
-- 时间维度上不可累加，必须显式指定取首/取尾/取均值
```

### 3.8 动态切换：计算组（推荐）

```dax
// 计算组：时间智能
-- 项：MTD
CALCULATE ( SELECTEDMEASURE (), DATESMTD ( 'Dim_Date'[Date] ) )
-- 项：YTD
CALCULATE ( SELECTEDMEASURE (), DATESYTD ( 'Dim_Date'[Date], "12/31" ) )
-- 项：PY
CALCULATE ( SELECTEDMEASURE (), SAMEPERIODLASTYEAR ( 'Dim_Date'[Date] ) )
-- 项：YoY%
VAR Cur  = SELECTEDMEASURE ()
VAR Prev = CALCULATE ( SELECTEDMEASURE (), SAMEPERIODLASTYEAR ( 'Dim_Date'[Date] ) )
RETURN IF ( NOT ISBLANK ( Cur ) && NOT ISBLANK ( Prev ), DIVIDE ( Cur - Prev, Prev ) )
```

> 一个计算组替代 N 个度量值 × M 个时间口径，模型复杂度与维护量下降一个量级。需 Tabular Editor 或 TMDL 编辑（Desktop 2022+ 支持模型资源管理器的计算组编辑）。

### 3.9 字段参数（指标/维度切换）

```dax
参数_指标 =
DATATABLE (
    "指标名", STRING,
    "排序", INTEGER,
    {
        { "销售额", 1 },
        { "毛利",   2 },
        { "销量",   3 }
    }
)
-- 实际字段参数在 Desktop「建模 > 新建参数 > 字段」创建，会生成含 NAMEOF 引用的表
-- 切换逻辑：SELECTEDVALUE(参数_指标[指标名]) 配合 SWITCH + 具体度量值
```

## 4. DAX 输出格式（每次必带 5 段）

```markdown
### 度量值：<名称>
**代码**
```dax
...
```
**逻辑拆解**：1) 2) 3)
**适用场景 / 不适用场景**：
**性能风险**：扫描行数、是否触发公式引擎、高基数列影响
**验证方法**：用什么筛选组合能验证、期望值多少、与什么对账
```

## 5. 反模式对照

| 反模式 | 问题 | 改写 |
|---|---|---|
| `CALCULATE(SUM(F), FILTER(Fact, Fact[A]=1))` | 迭代整个事实表 | `CALCULATE(SUM(F), Fact[A]=1)` |
| `SUMX(Fact, Fact[Qty]*Fact[Price])` 在亿级表 | 公式引擎逐行 | 上游/计算列预计算 `LineAmount` 后 `SUM` |
| `IFERROR([A]/[B],0)` | 掩盖空值/逻辑错，且逐行兜底 | `DIVIDE([A],[B])` + 单独暴露 `[B]` 供排查 |
| `COUNTROWS(FILTER(ALL(Dim), ...))` 当筛选器 | 生成大中间表 | 直接布尔筛选或 `CALCULATE(..., 条件)` |
| 在度量值里 `SUMMARIZE` 大事实表 | 内存峰值高 | 用维度表 `VALUES`/`SUMMARIZE` |
| 计算列中嵌套 `CALCULATE + ALL` | 循环引用、刷新慢 | 改度量值或上游处理 |
| 用 `ALL()` 消筛选强行"对齐数字" | 掩盖模型缺陷 | 先查关系方向与筛选上下文 |
| `DISTINCTCOUNT` 高基数列直接上卡片图 | SE 扫描巨大 | 预聚合 / `APPROXIMATEDISTINCTCOUNT` |

## 6. 交付前检查
- [ ] 命名符合 `业务域_指标名_逻辑类型`，挂在度量值表
- [ ] 无 `FILTER` 迭代事实表、无 `/`、无整段 `IFERROR`
- [ ] 变量已提取重复子表达式，空值已短路
- [ ] 时间智能作用于日期表
- [ ] 已给出验证方法与对账口径
