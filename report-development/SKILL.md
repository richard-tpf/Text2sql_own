---
name: report-development
description: |
  数据仓库报表开发助手，基于 DWD → DWS → ADS → Report 分层架构生成 Hive SQL 加工逻辑。
  当用户需要以下操作时触发：
  (1) 开发 DWS/ADS/Report 层的数据加工 SQL
  (2) 根据需求方案文档生成表结构定义（DDL）
  (3) 开发日/周/月多时间粒度的报表 SQL
  (4) 审查或优化现有的报表 SQL
  (5) 基于指标需求文档进行报表字段拆解和 SQL 实现
---

# 报表开发

协助开发基于分层架构的报表 SQL，严格遵守 Hive 语法和数仓分层规范。

## 表结构文档

开发时查阅对应的上游表结构文档：

- DWD层：#[[file:docs/dwd-tables.md]]
- MID层：#[[file:docs/mid-tables.md]]
- DWS层：#[[file:docs/dws-tables.md]]
- ADS层：#[[file:docs/ads-tables.md]]

## 需求方案文档

- 授信全流程漏斗：#[[file:credit_funnel_spec(2).md]]

从需求文档中获取：指标定义（原子/派生）、关联键、筛选条件、CTE flag 条件、建表 DDL、待确认项。

## 分层架构与依赖规则

```
DWD层 ──┐
        ├──→ DWS层 ──→ ADS层 ──→ Report层
MID层 ──┘
```

- DWS 只引用 DWD 和 MID 层
- ADS 只引用 DWS 层
- Report 只引用 ADS 层
- 禁止跨层反向依赖

## 开发流程

### 第一步：生成 DWS/ADS 表结构

1. 从需求文档提取建表 DDL
2. 追加 DWS 表结构到 `docs/dws-tables.md`（表名、字段列表、分区、数据来源、DDL）
3. 追加 ADS 表结构到 `docs/ads-tables.md`（日/周/月表分别生成）
4. 核对字段名、类型与需求文档一致
5. 同名表已存在时提示用户是否覆盖

### 第二步：生成加工 SQL

按层级顺序开发：DWS → ADS（日/周/月）→ Report

开发 DWS 层时：
1. 查阅 DWD/MID 层表结构，核对来源表验证清单
2. 识别加工场景（见 [sql-patterns.md](references/sql-patterns.md)）
3. 编写 INSERT/SELECT 逻辑，数据来源仅限 DWD 和 MID 层
4. 待确认项在 SQL 注释中标注

开发 ADS 层时：
1. 查阅 DWS 层表结构
2. 区分时间粒度（日/周/月），选择聚合方式（见 [sql-patterns.md](references/sql-patterns.md)）
3. 派生指标（比率类）在 ADS 层计算，不存 DWS 层
4. 派生指标计算公式严格按需求文档定义
5. 不可加指标（COUNT DISTINCT）周/月表必须回源 DWD 重新计算

开发 Report 层时：
1. 比率类字段用 `CONCAT(ROUND(x * 100, 2), '%')` 格式化
2. 根据时间粒度选择对应 ADS 表

## 参考文档

- SQL 加工场景模板与多时间粒度模式：[sql-patterns.md](references/sql-patterns.md)
- Hive SQL 语法规范与命名规范：[hive-sql-standards.md](references/hive-sql-standards.md)
- 常见错误检查清单：[checklist.md](references/checklist.md)

## 工作方式

1. 阅读需求文档，理解指标口径、维度、关联关系
2. 查阅目标表和上游表结构
3. 核对需求文档 DDL 与表结构文档一致性，不一致时提示用户
4. 识别加工场景，如有疑问先确认（关联逻辑、不可加指标、待确认项）
5. 按规范生成加工 SQL
6. 按 [checklist.md](references/checklist.md) 逐项审查

## 关键约束

- 所有表名带 `zijie.` schema 前缀
- 分区条件 `ds = '${bizdate}'` 在每个 CTE/子查询中都要加
- LEFT JOIN 后 SUM 聚合用 `COALESCE(flag, 0)` 包裹
- 除法运算用 `NULLIF(denominator, 0)` 除零保护
- 所有回答和注释使用中文
- 待确认项在 SQL 注释中标注处理方式并提醒用户确认
