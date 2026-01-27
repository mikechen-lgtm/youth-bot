# 活动资料处理工作流程

## 当前架构

```
Facebook JSON 数据
      ↓
[json_to_database.py]
      ↓
MySQL fb_activities 表
      ↓
应用程式查询 / RAG 系统整合
```

## 每日更新流程

### 1. 更新 JSON 数据
（由爬虫或手动更新 rag_data 目录中的 JSON 文件）

### 2. 汇入资料表

```bash
cd /home/creative_design/youth-bot
python scripts/json_to_database.py --rag-dir rag_data
```

**执行结果**：
- ✅ 新活动自动加入
- ✅ 已存在的活动自动更新
- ✅ 显示统计报表

### 3. 验证数据

```bash
# 查看活动数量
python -c "
from scripts.json_to_database import create_engine_instance
from sqlalchemy import text

engine = create_engine_instance()
with engine.begin() as conn:
    result = conn.execute(text('''
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN event_date >= CURDATE() THEN 1 ELSE 0 END) as upcoming
        FROM fb_activities
    '''))
    row = result.fetchone()
    print(f'总活动数：{row[0]}')
    print(f'未来活动：{row[1]}')
"
```

## 自动化设定

### Cron Job（每天凌晨 2 点执行）

```bash
# 编辑 crontab
crontab -e

# 添加以下行
0 2 * * * cd /home/creative_design/youth-bot && /home/creative_design/miniconda3/bin/python scripts/json_to_database.py --rag-dir rag_data >> logs/db_import.log 2>&1
```

### 日志文件

```bash
# 创建日志目录
mkdir -p /home/creative_design/youth-bot/logs

# 查看最近的导入日志
tail -f logs/db_import.log
```

## 应用程式整合

### 在 Flask 应用中查询活动

```python
# app.py

def get_upcoming_activities(limit=20):
    """获取未来的活动"""
    query = """
    SELECT
        id, source, title, content,
        event_date, event_time, location,
        url, registration_url
    FROM fb_activities
    WHERE event_date >= CURDATE()
    ORDER BY event_date ASC
    LIMIT :limit
    """

    with mysql_engine.begin() as conn:
        result = conn.execute(text(query), {"limit": limit})
        return [dict(row._mapping) for row in result.fetchall()]

@app.get("/api/activities")
def api_activities():
    """活动列表 API"""
    activities = get_upcoming_activities(limit=20)
    return jsonify({
        "success": True,
        "activities": activities
    })
```

### 整合到 RAG 系统

修改 `openai_service.py` 或 `app.py`，在生成回答前动态注入活动数据：

```python
def get_activities_context() -> str:
    """从资料表获取活动内容作为 RAG 上下文"""
    query = """
    SELECT
        source, title, event_date,
        location, content, url
    FROM fb_activities
    WHERE event_date >= CURDATE()
        AND event_date <= DATE_ADD(CURDATE(), INTERVAL 3 MONTH)
    ORDER BY event_date ASC
    LIMIT 20
    """

    with mysql_engine.begin() as conn:
        result = conn.execute(text(query))
        activities = result.fetchall()

    # 格式化为文本
    context = "# 近期活动（未来3个月）\n\n"
    for act in activities:
        context += f"## {act.title}\n"
        context += f"**来源**：{act.source}\n"
        context += f"**日期**：{act.event_date}\n"
        if act.location:
            context += f"**地点**：{act.location}\n"
        context += f"\n{act.content}\n\n"
        if act.url:
            context += f"[详细资讯]({act.url})\n\n"
        context += "---\n\n"

    return context

# 在生成回答时加入
def generate_with_activities(query: str, system_prompt: str):
    """生成回答时动态加入活动资料"""
    activities_context = get_activities_context()

    # 将活动资料加入系统提示或作为额外上下文
    enhanced_prompt = f"""{system_prompt}

## 当前可用活动资料

{activities_context}
"""

    return generate_with_rag_stream(
        query=query,
        system_prompt=enhanced_prompt,
        chat_history=chat_history,
        model=OPENAI_MODEL
    )
```

## 资料维护

### 定期清理过期资料（保留 6 个月）

```bash
# 创建清理脚本
cat > scripts/cleanup_old_activities.py << 'EOF'
#!/usr/bin/env python
from scripts.json_to_database import create_engine_instance
from sqlalchemy import text

engine = create_engine_instance()

with engine.begin() as conn:
    result = conn.execute(text("""
        DELETE FROM fb_activities
        WHERE event_date < DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
    """))

    print(f"已删除 {result.rowcount} 条过期活动记录")
EOF

# 每月1号凌晨3点执行
# crontab -e
0 3 1 * * cd /home/creative_design/youth-bot && /home/creative_design/miniconda3/bin/python scripts/cleanup_old_activities.py >> logs/cleanup.log 2>&1
```

### 备份资料表

```bash
# 每周日凌晨 4 点备份
0 4 * * 0 mysqldump -u root -p$(cat ~/.mysql_password) youth-chat fb_activities > /home/creative_design/youth-bot/backups/fb_activities_$(date +\%Y\%m\%d).sql
```

## 监控和告警

### 数据质量检查

```python
# scripts/check_data_quality.py

def check_data_quality():
    """检查资料表数据质量"""
    checks = []

    with engine.begin() as conn:
        # 检查1: 未来活动数量
        result = conn.execute(text("""
            SELECT COUNT(*) FROM fb_activities
            WHERE event_date >= CURDATE()
        """))
        upcoming_count = result.scalar()

        if upcoming_count < 10:
            checks.append(f"⚠️  未来活动过少: {upcoming_count}")
        else:
            checks.append(f"✓ 未来活动数量: {upcoming_count}")

        # 检查2: 最近更新时间
        result = conn.execute(text("""
            SELECT MAX(updated_at) FROM fb_activities
        """))
        last_update = result.scalar()

        from datetime import datetime, timedelta
        if last_update < datetime.now() - timedelta(days=2):
            checks.append(f"⚠️  资料表超过2天未更新")
        else:
            checks.append(f"✓ 资料表更新正常")

        # 检查3: 无日期的比例
        result = conn.execute(text("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN event_date IS NULL THEN 1 ELSE 0 END) as no_date
            FROM fb_activities
        """))
        row = result.fetchone()

        if row.no_date > 0:
            checks.append(f"⚠️  有 {row.no_date} 条记录缺少日期")
        else:
            checks.append(f"✓ 所有记录都有日期")

    return "\n".join(checks)

if __name__ == "__main__":
    print(check_data_quality())
```

## 故障处理

### 问题：导入失败

**检查清单**：
1. 数据库连接是否正常
2. JSON 文件格式是否正确
3. 磁盘空间是否充足
4. 日志文件中的错误信息

```bash
# 查看详细错误
python scripts/json_to_database.py --rag-dir rag_data 2>&1 | tee logs/debug.log
```

### 问题：活动数据不准确

**解决方案**：
1. 清空并重新导入

```bash
# 备份
mysqldump -u root -p youth-chat fb_activities > backup_$(date +%Y%m%d).sql

# 清空
mysql -u root -p youth-chat -e "TRUNCATE TABLE fb_activities"

# 重新导入
python scripts/json_to_database.py --rag-dir rag_data
```

2. 验证源数据

```bash
# 检查 JSON 文件
python -c "
import json
from pathlib import Path

for json_file in Path('rag_data').glob('*.json'):
    with open(json_file) as f:
        data = json.load(f)
        print(f'{json_file.name}: {len(data.get(\"posts\", []))} posts')
"
```

## 性能优化

### 添加覆盖索引

```sql
-- 针对"查询未来活动"的覆盖索引
CREATE INDEX idx_upcoming_activities
ON fb_activities(event_date, title, location, url)
WHERE event_date >= CURDATE();
```

### 分区表（适用于大量数据）

```sql
-- 按年份分区
ALTER TABLE fb_activities
PARTITION BY RANGE (YEAR(event_date)) (
    PARTITION p2024 VALUES LESS THAN (2025),
    PARTITION p2025 VALUES LESS THAN (2026),
    PARTITION p2026 VALUES LESS THAN (2027),
    PARTITION p_future VALUES LESS THAN MAXVALUE
);
```

## 总结

**简化后的工作流程**：
1. ✅ JSON 数据 → 资料表（自动化）
2. ✅ 应用程式直接查询资料表
3. ✅ RAG 系统动态读取资料表
4. ✅ 定期清理和备份

**优势**：
- 更少的步骤
- 单一数据源
- 即时更新
- 易于维护
