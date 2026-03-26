# SQL 加工场景模板

## 目录

- [DWS 层加工场景](#dws-层加工场景)
  - [场景A：多 CTE 分步打标模式](#场景a多-cte-分步打标模式推荐)
  - [场景B：单 CTE flag 模式](#场景b单-cte-flag-模式)
  - [场景C：直接聚合模式](#场景c直接聚合模式)
- [ADS 多时间粒度模式](#ads-多时间粒度模式)
  - [日表](#日表直取-dws)
  - [周表](#周表从-dws-日表-sum-聚合)
  - [月表](#月表从-dws-日表-sum-聚合)
  - [不可加指标处理](#不可加指标处理)

---

## DWS 层加工场景

### 场景A：多 CTE 分步打标模式（推荐）

适用于关联多张表、每张关联表产出不同指标的场景。

```sql
-- 公共基础表
WITH base AS (
    SELECT
        主键字段 AS id,
        TO_DATE(时间字段) AS 日期维度
    FROM schema.主表
    WHERE ds = '${bizdate}'
    AND is_active = 'Y'
)
-- 关联表1打标
,table1_stats AS (
    SELECT
        关联键 AS id,
        1 AS flag_指标1,
        CASE WHEN 条件 THEN 1 ELSE 0 END AS flag_指标2
    FROM schema.关联表1
    WHERE ds = '${bizdate}'
    AND is_active = 'Y'
    AND type = '1'
)
-- 关联表2打标
,table2_stats AS (
    SELECT
        关联键 AS id,
        CASE WHEN 条件 THEN 1 ELSE 0 END AS flag_指标3
    FROM schema.关联表2
    WHERE ds = '${bizdate}'
    AND is_active = 'Y'
    AND type = '1'
)
INSERT OVERWRITE TABLE schema.dws_xxx PARTITION (ds = '${bizdate}')
SELECT
    b.日期维度,
    COUNT(1) AS 申请数,
    SUM(COALESCE(t1.flag_指标1, 0)) AS 指标1,
    SUM(COALESCE(t1.flag_指标2, 0)) AS 指标2,
    SUM(COALESCE(t2.flag_指标3, 0)) AS 指标3
FROM base b
LEFT JOIN table1_stats t1 ON b.id = t1.id
LEFT JOIN table2_stats t2 ON b.id = t2.id
GROUP BY b.日期维度
ORDER BY b.日期维度 DESC;
```

要点：
- 每个 CTE 的 WHERE 条件独立，不混淆不同关联表的筛选逻辑
- LEFT JOIN 后用 `COALESCE(flag, 0)` 处理空值
- 主表 COUNT(1) 直接在最终 SELECT 计算
- 每个 CTE 都加分区条件 `ds = '${bizdate}'`

### 场景B：单 CTE flag 模式

适用于单次 LEFT JOIN 后通过 CASE WHEN 打标生成多个指标（所有指标来自同一关联关系）。

```sql
INSERT OVERWRITE TABLE schema.dws_xxx PARTITION (ds = '${bizdate}')
WITH cte AS (
    SELECT
        TO_DATE(主表.时间字段) AS 日期维度,
        CASE WHEN 关联表.id IS NOT NULL THEN 1 ELSE 0 END AS flag_指标1,
        CASE WHEN 关联表.id IS NOT NULL AND 关联表.状态字段 = '1' THEN 1 ELSE 0 END AS flag_指标2,
        CASE WHEN 主表.状态字段 = '1' THEN 1 ELSE 0 END AS flag_指标3
    FROM schema.主表
    LEFT JOIN schema.关联表
        ON 主表.关联键 = 关联表.id
        AND 关联表.类型条件
        AND 关联表.有效条件
        AND 关联表.ds = '${bizdate}'
    WHERE 主表.ds = '${bizdate}'
    AND 主表.有效条件
)
SELECT
    日期维度,
    COUNT(1) AS 申请数,
    SUM(flag_指标1) AS 指标1,
    SUM(flag_指标2) AS 指标2,
    SUM(flag_指标3) AS 指标3
FROM cte
GROUP BY 日期维度;
```

### 场景C：直接聚合模式

适用于无需关联或关联简单、指标直接 COUNT/SUM 的场景。

```sql
INSERT OVERWRITE TABLE schema.dws_xxx PARTITION (ds = '${bizdate}')
SELECT
    维度字段,
    COUNT(字段) AS 指标1,
    COUNT(CASE WHEN 条件 THEN 字段 END) AS 指标2
FROM schema.主表
LEFT JOIN schema.关联表 ON ...
WHERE ...
GROUP BY 维度字段;
```

---

## ADS 多时间粒度模式

### 日表（直取 DWS）

```sql
WITH daily_data AS (
    SELECT
        apply_date,
        原子指标1,
        原子指标2,
        -- 派生指标在 ADS 层计算
        原子指标1 - 原子指标2 AS 差值指标,
        原子指标1 / NULLIF(原子指标2, 0) AS 比率指标
    FROM schema.dws_xxx
    WHERE ds = '${bizdate}'
)
INSERT OVERWRITE TABLE schema.ads_xxx_daily_df PARTITION (ds = '${bizdate}')
SELECT * FROM daily_data
ORDER BY apply_date DESC;
```

### 周表（从 DWS 日表 SUM 聚合）

```sql
WITH weekly_data AS (
    SELECT
        DATE_SUB(NEXT_DAY('${bizdate}', 'MO'), 7) AS week_start_date,
        DATE_SUB(NEXT_DAY('${bizdate}', 'MO'), 1) AS week_end_date,
        SUM(原子指标1) AS 原子指标1,
        SUM(原子指标2) AS 原子指标2,
        SUM(原子指标1) - SUM(原子指标2) AS 差值指标,
        SUM(原子指标1) / NULLIF(SUM(原子指标2), 0) AS 比率指标
    FROM schema.dws_xxx
    WHERE ds BETWEEN DATE_SUB(NEXT_DAY('${bizdate}', 'MO'), 7)
                  AND DATE_SUB(NEXT_DAY('${bizdate}', 'MO'), 1)
)
INSERT OVERWRITE TABLE schema.ads_xxx_weekly_df PARTITION (ds = '${bizdate}')
SELECT * FROM weekly_data;
```

### 月表（从 DWS 日表 SUM 聚合）

```sql
WITH monthly_data AS (
    SELECT
        SUBSTR(apply_date, 1, 7) AS apply_month,
        SUM(原子指标1) AS 原子指标1,
        SUM(原子指标2) AS 原子指标2,
        SUM(原子指标1) - SUM(原子指标2) AS 差值指标,
        SUM(原子指标1) / NULLIF(SUM(原子指标2), 0) AS 比率指标
    FROM schema.dws_xxx
    WHERE SUBSTR(apply_date, 1, 7) = SUBSTR('${bizdate}', 1, 7)
    GROUP BY SUBSTR(apply_date, 1, 7)
)
INSERT OVERWRITE TABLE schema.ads_xxx_monthly_df PARTITION (ds = '${bizdate}')
SELECT * FROM monthly_data;
```

### 不可加指标处理

COUNT DISTINCT 等不可加指标，周/月表不能从 DWS 日表 SUM 聚合，必须回源 DWD 层重新计算。需在需求文档中明确标注哪些指标不可加。
