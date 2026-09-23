# TMDL Greenfield Scaffolding (PBIP + TMDL + Mock CSV)

End-to-end recipe for **hand-authoring a new PBIP project from zero** when Power BI Desktop, Tabular Editor CLI, and the Power BI Modeling MCP server are not available. The whole project lives as text files in a Git repo; PBI Desktop only opens it at the end.

> **When to use this**: greenfield PBIP where the data source, KPI definitions, and report layout are not yet locked. You build the skeleton (semantic model + report stub + mock data), let the user iterate on `TBD` items against a working artifact, then swap in real sources and a real report.
>
> **When NOT to use this**: PBI Desktop is open and the Tabular Editor MCP server is reachable — use those tools instead, they validate DAX/refs and avoid the manual-work mistakes below.

## 1. Directory layout (minimum viable)

```
<ProjectRoot>/
├── README.md
├── .gitignore
├── <Name>.SemanticModel/
│   ├── model.tmdl                          ← entry; minimum metadata
│   └── definition/
│       ├── database.tmdl                   ← ref table, ref culture, ref defaultMeasure
│       └── database/
│           ├── Date.tmdl                   ← dim
│           ├── Channel.tmdl                ← dim (one per dimension)
│           ├── Product.tmdl                ← dim
│           ├── Sales.tmdl                  ← fact (measures live here)
│           └── relationships.tmdl          ← all relationships
└── <Name>.Report/
    └── definition/
        ├── theme/theme.json                ← Linear极简 / good-bad-reversed / etc.
        └── pages/report.json               ← stub; designers replace with real PBIR
```

Notes:
- **No `.pbip` file yet.** Generate it once with PBI Desktop ("File > Save As > Power BI Project") at the end, or hand-write a minimal stub pointing at `.Report/`.
- **No `.platform` yet.** PBI Desktop adds it on first save.
- The `database/` subfolder is the convention Power BI Desktop itself uses; some tools also accept a flat `tables/` folder (TMDL spec allows both). Match the dominant tool's convention.

## 2. Minimum `model.tmdl` — TMDL TEXT, not JSON

`model.tmdl` lives at `<Name>.SemanticModel/model.tmdl` (NOT under `definition/`, see the SKILL Critical section). PBI Modeling MCP `ConnectFolder` parses it as TMDL — a JSON body reports `Indentation` errors. Minimum body:

```tmdl
model Model
	defaultMeasureTable: Sales
	defaultMeasure: 'Sales'[Revenue]
	discourageImplicitMeasures: true
```

`culture:` and `compatibilityLevel:` belong in `database.tmdl`, not here.

## 3. Minimum `database.tmdl` — NO `createOrReplace`, NO `ref table`

`database.tmdl` declares the database envelope. Common traps (rejected by PBI Modeling MCP `ConnectFolder` with `UnsupportedObjectType`): `createOrReplace` at the top, `ref table` / `ref defaultMeasure` / `ref culture` at the top. Those belong in `model.tmdl` (or in the per-table file for `ref table`). `database.tmdl` is just the envelope:

```tmdl
database <ProjectName>
compatibilityLevel: 1567
culture: zh-CN
```

> The TMDL spec also accepts `ref table` / `ref expression` etc. *inside* a `database { }` block, but the flat top-level form shown above is the one PBI Modeling MCP and PBI Desktop parse without complaint. Skip the block form unless you have a specific reason.
> Quote only names with spaces/special chars. `database Sales` (unquoted) is correct for simple names.

## 4. Per-table `<Table>.tmdl` template

For each dimension and fact, one file. Star-schema rules:
- Date is marked `dataCategory: PaddedDateTable`, has a `Date` column with `isKey`, plus all derived time-intelligence columns (`Year`, `Month`, `WeekKey`, `WeekStart`, `ISOWeek` if used).
- Dimension tables: surrogate key (`<Name>Key`) + display columns + (optional) hierarchy columns.
- Fact tables: FK columns + additive measures. **All measures live on the fact table or on a dedicated `_度量值` table**, never scattered.

### Partition (M query, Import mode) — **relative path is from the model root, not the .tmdl file**

```tmdl
partition 'Sales-partition' = m
	mode: import
	source =
			let
			    Source = Csv.Document(File.Contents("../../../data/Sales.csv"),[Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.None]),
			    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
			    Typed = Table.TransformColumnTypes(Promoted,{{"OrderID", type text}, {"DateKey", type date}, {"ChannelKey", Int64.Type}, {"Revenue", type number}})
			in
			    Typed
```

Path math: TMDL file lives at `definition/database/Sales.tmdl`. Power Query `File.Contents` resolves **from the model root** (`<Name>.SemanticModel/`), so:
- `..` = `<Name>.SemanticModel/`
- `../..` = `<ProjectRoot>/`
- `../../data/Sales.csv` = `<ProjectRoot>/data/Sales.csv` ✅

> **Pitfall — off-by-one relative path**: writing `../../../data/Sales.csv` (three `..`) resolves to the parent of `<ProjectRoot>`, which fails on refresh with "could not find file". Always `../../` for top-level `data/`. Verify by opening the partition in Power BI Desktop's PQ editor and checking the resolved path.

## 5. Measure skeleton (the fact table is the right home)

```tmdl
table 'Sales'
	lineageTag: sales-table-v1

	column 'OrderID'
		dataType: string
		summarizeBy: none
		sourceColumn: OrderID

	column 'Revenue'
		dataType: decimal
		formatString: #,##0.00
		summarizeBy: sum
		sourceColumn: Revenue

	/// 销售额 — 销售净额（含税、退补单后）. TBD: 等口径定.
	measure 'Revenue' = SUM ( 'Sales'[Revenue] )
		formatString: #,##0.00
		lineageTag: m-revenue-v1
```

Key conventions:
- `///` immediately before the declaration (no blank line) sets the description.
- `lineageTag` is a free-form string (any stable token); the GUID-like values are optional.
- Hide `summarizeBy: sum` for keys/text/date columns; only additive numerics get `sum`.
- For multi-line DAX bodies, indent 1 tab deeper than the property indentation (typical: properties at depth 2, DAX body at depth 3).

## 6. `relationships.tmdl` (all relationships, one file)

```tmdl
/// Star-schema relationships - 1:* dim-to-fact, single direction, all active
relationship 'r-Date-Sales'
	fromColumn: 'Date'[Date]
	toColumn: 'Sales'[DateKey]
	crossFilteringBehavior: oneDirection
	isActive: true
	securityFilteringBehavior: oneDirection

relationship 'r-Channel-Sales'
	fromColumn: 'Channel'[ChannelKey]
	toColumn: 'Sales'[ChannelKey]
	crossFilteringBehavior: oneDirection
	isActive: true
	securityFilteringBehavior: oneDirection
```

> **No `createOrReplace` wrapper.** Top-level `relationship` declarations are direct children of the file (TMDL spec lists `relationship` as a root-level object). `createOrReplace` is reserved for inside an object's body (e.g. a `partition` `source =` block, or a top-level `function` body).

Star-schema only: 1:* from each dim to fact, single direction, all active. No bidirectional, no many-to-many in a greenfield.

## 7. Theme JSON (Linear 极简 + 涨红跌绿反转)

A self-contained `theme.json` you can drop under `Report/definition/theme/`:

```json
{
  "name": "<ProjectName>",
  "version": "v1.0",
  "baseTheme": {
    "name": "Minimal Restrained (Linear)",
    "dataColors": ["#0F172A", "#475569", "#64748B", "#94A3B8", "#CBD5E1", "#E2E8F0", "#F1F5F9"],
    "good": "#DC2626",
    "bad": "#16A34A",
    "neutral": "#94A3B8",
    "background": "#FFFFFF",
    "foreground": "#0F172A",
    "textClasses": {
      "title": { "fontFace": "Segoe UI", "fontSize": 20, "fontWeight": "semibold" },
      "value": { "fontFace": "Segoe UI", "fontSize": 32, "fontWeight": "bold" },
      "label": { "fontFace": "Segoe UI", "fontSize": 10, "color": "#605E5C" }
    },
    "visualStyles": {
      "cardVisual": { "*": { "outlineStyle": [{ "weight": 0 }], "accentBar": { "show": true, "position": "Left", "width": 4, "color": "#0F172A" } } },
      "lineChart":  { "*": { "lineStyle": { "strokeWidth": 2, "lineSmooth": false }, "area": { "show": false } } },
      "tableEx":    { "*": { "rowStyle": { "alternatingColor": "#FAFAFA" } } },
      "slicer":     { "*": { "selection": { "singleSelect": true } } }
    }
  }
}
```

> **涨红跌绿反转** = `good=#DC2626` (red) / `bad=#16A34A` (green) — opposite of PBI's default. Required by Chinese finance convention. Pair with **▲/▼ character + numeric label** in every WoW/YoY measure output for color-blind accessibility.

## 8. Report stub (`pages/report.json`)

A placeholder that gives designers a single integration point. Real PBIR (`pages/<id>/page.json` + `visuals/<id>/visual.json`) is generated by PBI Desktop once the report is opened; for greenfield, the stub just declares the page layout in flat form and is replaced wholesale.

```json
{
  "name": "<ProjectName> Report",
  "version": "v0.1",
  "theme": "theme.json",
  "pages": [
    {
      "name": "ReportSection1",
      "displayName": "全渠道销售周报",
      "layout": { "width": 1920, "height": 1080 },
      "visuals": {
        "page_title":      { "type": "textbox",  "x": 32,  "y": 32,  "w": 960, "h": 64,  "text": "全渠道销售周报" },
        "week_slicer":     { "type": "slicer",    "x": 1024, "y": 32,  "w": 432, "h": 64,  "field": "Date[WeekKey]", "singleSelect": true, "header": "周（截止）" },
        "revenue_card":    { "type": "cardVisual","x": 32,  "y": 128, "w": 448, "h": 200, "measure": "Sales[Revenue]", "label": "销售额" },
        "wow_card":        { "type": "cardVisual","x": 1472,"y": 128, "w": 416, "h": 200, "measure": "Sales[WoW_variance %]", "label": "周环比" },
        "trend_line":      { "type": "lineChart", "x": 32,  "y": 352, "w": 928, "h": 432, "xAxis": "Date[WeekStart]", "yAxis": "Sales[Revenue_12W_Rolling]", "title": "近 12 周全渠道销售趋势" },
        "channel_bar":     { "type": "barChart",  "x": 992, "y": 352, "w": 896, "h": 432, "category": "Channel[ChannelName]", "measure": "Sales[Revenue]", "title": "截止周渠道销售对比" },
        "channel_table":   { "type": "tableEx",   "x": 32,  "y": 808, "w": 1856,"h": 240, "columns": ["Channel[ChannelName]","Sales[Revenue]","Sales[Orders]","Sales[ChannelShare %]","Sales[WoW_variance %]"], "title": "截止周渠道明细" }
      }
    }
  ]
}
```

> Designers replace this with the real PBIR tree (one folder per page, one folder per visual) once PBI Desktop opens the project. **Do not hand-author visual.json — use PBI Desktop or `pbir` skill.**

## 9. Mock data CSVs (under `<ProjectRoot>/data/`)

Use `python3` with `csv` stdlib; **commit the CSVs** so the project is reproducible without an external data source. Keep them small (~3K rows) — enough to demo all filter/visual behaviors, small enough to commit. Always include:
- `Date.csv` — at least `len(rolling_window) + 1` weeks so rolling-window measures have data
- All dimension CSVs — at least the seed rows referenced by fact CSVs
- A `Sales.csv` — column names must exactly match the M partition's `TransformColumnTypes` step

Deterministic seed (`random.seed(42)`) so the demo data is reproducible across runs.

## 10. `.gitignore`

```gitignore
*.pbix
*.pbip
.DS_Store
.vscode/
.idea/
```

**Do NOT gitignore `data/*.csv`** — TMDL M partitions reference them by relative path, and reproducibility requires them in the repo.

## 11. Verification steps after scaffolding

1. `git init` + initial commit once structure is in place (commits are cheap, you can squash).
2. Open with PBI Desktop: "File > Open" → point at the `<Name>.Report/definition.pbir` (created by PBI Desktop on first open) or the auto-generated `<Name>.pbip` after the first "Save As > Power BI Project".
3. Click "Refresh" — partitions should resolve the relative paths and load the mock CSVs.
4. Click each visual; verify it renders. Fix M partition paths if a refresh error names a file.
5. Hand the artifact to the user for `TBD` walkthrough before committing the real data source.

## 12. TBD handling pattern

When the user cannot yet answer business-kpi questions (sales = GMV vs net, tax treatment, etc.):
- Use **neutral metric names** in code (`Revenue`, `Orders`, `WoW_variance %`) — not committed business terms.
- Mark every measure's description with `TBD: <open question>`.
- For every visual, append a `TBD` list to its description.
- Maintain a single project-level `TBD.md` enumerating all open items with their owner.
- **Do not block**: ship the skeleton with mock data + neutral names; rename via TE2 (or TMDL search/replace) once TBDs close.

This unblocks the design/UAT loop while preserving rigor: the artifact is real, the math is right, only the labels are pending.
