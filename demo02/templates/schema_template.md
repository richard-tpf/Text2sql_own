# 表结构知识库 - 导入模板

> 使用说明：每个二级标题（## 库名.表名）下包含三部分内容：所属层级、建表语句、来源表。
> 系统会自动解析并存入知识库。
> 请按以下格式填写，然后在「表结构知识库」页面通过「上传 MD 文件」功能导入。
> 注意：来源表只填写具体的真实表名，如果没有则留空不写。


## zijie.dws_credit_daily_count_df

### 所属层级

DWS

### 建表语句

```sql
CREATE TABLE zijie.dws_credit_daily_count_df (
    apply_date       STRING COMMENT '申请日期',
    apply_cnt        BIGINT COMMENT '申请数',
    pass_cnt         BIGINT COMMENT '授信通过数',
    loan_apply_cnt   BIGINT COMMENT '用信申请数'
) COMMENT '授信日汇总表'
PARTITIONED BY (ds STRING COMMENT '日期分区')
STORED AS ORC;
```

### 来源表

- zijie.dwd_credit_apply_df
- zijie.dwd_credit_result_df
