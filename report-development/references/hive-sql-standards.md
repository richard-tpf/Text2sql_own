# Hive SQL 编写规范

## Hive 语法要求

- 使用 `INSERT OVERWRITE TABLE ... PARTITION (ds='${bizdate}')` 写入分区表，不用 `INSERT INTO`
- 表名必须带 schema 前缀（如 `zijie.dws_credit_daily_count_df`）
- 分区参数变量默认 `'${bizdate}'`，用户指定其他变量名则按用户要求
- 日期函数用 Hive 内置：`DATE_SUB()`、`DATE_ADD()`、`DATEDIFF()`、`TO_DATE()`、`DATE_FORMAT()`、`NEXT_DAY()`、`SUBSTR()`
- 类型转换用 `CAST(expr AS type)`
- 字符串拼接用 `CONCAT()`，不用 `||`
- 条件判断用 `CASE WHEN ... THEN ... ELSE ... END` 或 `IF()`
- 空值处理用 `COALESCE()` 或 `NVL()`
- LEFT JOIN 后 SUM 聚合必须用 `COALESCE(flag, 0)` 包裹
- 除法除零保护用 `NULLIF()`：`numerator / NULLIF(denominator, 0)`
- 不使用 `LIMIT` 配合 `INSERT`
- 不使用 `UPDATE`、`DELETE`、`MERGE`
- 不使用窗口函数中的 `RANGE` 语法（除非确认 Hive 版本支持）

## 命名规范

- DWS 表名：`dws_<主题域>_<业务描述>_<时间粒度>_df`
- ADS 表名：`ads_<主题域>_<业务描述>_<时间粒度>_df`
- 字段名：小写蛇形（snake_case）
- 聚合指标后缀：`_cnt`、`_sum`、`_avg`、`_max`、`_min`
- 比率类字段：`_rate` 后缀

## SQL 风格

- 关键字大写（SELECT、FROM、WHERE、JOIN 等）
- 每个字段单独一行
- JOIN 条件用 ON 子句，不用 WHERE 隐式关联
- 复杂逻辑用 CTE（WITH 子句）拆分
- 添加充分的中文注释说明业务逻辑
- 分区字段放在 WHERE 条件最前面
- DWS 层查询结果按维度字段 `ORDER BY ... DESC` 排序
