# 活动数据处理脚本说明

## 📁 脚本列表

### 1. `json_to_database.py` - JSON 汇入资料表

**功能**：将 JSON 档案汇入 MySQL `fb_activities` 资料表

**使用方法**：
```bash
python scripts/json_to_database.py --rag-dir rag_data
```

**详细说明**：查看 [README_database.md](README_database.md)

---

### 2. `export_activities_for_rag.py` - 导出活动供 RAG 使用

**功能**：从资料表导出活动数据为文本格式

**使用方法**：
```bash
# 导出未来 90 天的活动到文件
python scripts/export_activities_for_rag.py --days 90 --output rag_data/近期活动.txt

# 输出到标准输出
python scripts/export_activities_for_rag.py --days 90

# 包含过去的活动
python scripts/export_activities_for_rag.py --days 90 --include-past
```

**参数说明**：
- `--days` - 查询未来多少天（预设 90）
- `--include-past` - 包含过去的活动
- `--output` - 输出档案路径（选填）
- `--source` - 过滤特定来源（选填）

---

### 3. ~~`convert_json_to_markdown.py`~~ - 已弃用

**状态**：已移除，改用资料表方式

---

## 🔄 完整工作流程

### 方案：直接使用资料表（推荐）

```
┌─────────────────────┐
│  Facebook JSON 数据  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ json_to_database.py │  ← 汇入资料表
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  fb_activities 表   │  ← MySQL 资料表
└──────────┬──────────┘
           │
           ├─────────────────────┐
           │                     │
           ▼                     ▼
┌──────────────────┐  ┌─────────────────────┐
│  应用程式直接查询  │  │ RAG 系统动态读取     │
└──────────────────┘  └─────────────────────┘
```

### 每日更新步骤

**1. 汇入资料表**
```bash
cd /home/creative_design/youth-bot
python scripts/json_to_database.py --rag-dir rag_data
```

**2.（可选）导出供 RAG 使用**
```bash
# 如果需要文本格式
python scripts/export_activities_for_rag.py --days 90 --output rag_data/activities.txt
```

### 自动化设定

**Cron Job**（每天凌晨 2 点执行）：
```bash
crontab -e

# 添加
0 2 * * * cd /home/creative_design/youth-bot && /home/creative_design/miniconda3/bin/python scripts/json_to_database.py --rag-dir rag_data >> logs/db_import.log 2>&1
```

---

## 📊 数据流向

### 输入数据（JSON）

```
rag_data/
├── FB-POST-桃園市政府青年事務局-20260121.json
├── FB-POST-桃園青創事-20260121.json
└── FB-POST-桃青參一咖-20260121.json
```

### 输出（资料表）

```sql
SELECT * FROM fb_activities
WHERE event_date >= CURDATE()
ORDER BY event_date ASC;
```

**结果**：
- 总活动数：164
- 未来活动：52
- 过去活动：112

---

## 🔧 开发集成

### 在 Flask 应用中使用

```python
from sqlalchemy import text

def get_upcoming_activities(days=90, limit=20):
    """获取未来的活动"""
    query = """
    SELECT source, title, event_date, location, url
    FROM fb_activities
    WHERE event_date >= CURDATE()
      AND event_date <= DATE_ADD(CURDATE(), INTERVAL :days DAY)
    ORDER BY event_date ASC
    LIMIT :limit
    """
    with mysql_engine.begin() as conn:
        result = conn.execute(text(query), {"days": days, "limit": limit})
        return [dict(row._mapping) for row in result.fetchall()]

# 在 API 中使用
@app.get("/api/activities")
def api_activities():
    activities = get_upcoming_activities()
    return jsonify({"success": True, "activities": activities})
```

### 整合到 RAG 系统

```python
# 方法 1：动态注入到系统提示
def get_activities_context():
    activities = get_upcoming_activities(days=90, limit=20)
    context = "# 近期活动\n\n"
    for act in activities:
        context += f"## {act['title']}\n"
        context += f"日期：{act['event_date']}\n"
        context += f"地点：{act['location']}\n\n"
    return context

# 方法 2：导出为文件上传到 Vector Store
import subprocess
subprocess.run([
    "python", "scripts/export_activities_for_rag.py",
    "--days", "90",
    "--output", "rag_data/activities.txt"
])
```

---

## 📈 监控和维护

### 数据质量检查

```python
# scripts/check_data_quality.py
def check():
    with engine.begin() as conn:
        # 检查活动数量
        result = conn.execute(text("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN event_date >= CURDATE() THEN 1 ELSE 0 END) as upcoming
            FROM fb_activities
        """))
        row = result.fetchone()
        print(f"总活动：{row.total}")
        print(f"未来活动：{row.upcoming}")
```

### 清理过期数据

```bash
# 每月执行
mysql -u root -p youth-chat -e "
DELETE FROM fb_activities
WHERE event_date < DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
"
```

---

## 🆚 对比：Markdown vs 资料表

| 特性 | Markdown 文件 | MySQL 资料表 |
|------|--------------|-------------|
| 结构化查询 | ❌ 无法精准查询 | ✅ SQL 精准查询 |
| 自动去重 | ❌ 需手动处理 | ✅ 自动去重 |
| 更新效率 | ⚠️  需重新生成全部 | ✅ 增量更新 |
| 查询速度 | ⚠️  需全文扫描 | ✅ 索引优化 |
| 应用整合 | ⚠️  需解析文件 | ✅ 直接 ORM |
| 维护成本 | ⚠️  需同步两份 | ✅ 单一来源 |

**结论**：资料表方式更适合需要精准查询和实时更新的场景

---

## 📚 相关文档

- [json_to_database.py 详细说明](README_database.md)
- [完整工作流程](WORKFLOW.md)
- ~~[Markdown 转换说明](README_convert.md)~~ - 已弃用

---

## 🔍 常见问题

### Q: 为什么移除 Markdown 方式？

A: 资料表方式提供更好的：
- 结构化查询能力
- 自动去重机制
- 增量更新效率
- 应用程式集成

### Q: 如何从资料表供给 RAG 系统？

A: 两种方式：
1. 使用 `export_activities_for_rag.py` 导出文本
2. 在生成回答时动态读取资料表

### Q: 多久更新一次？

A: 建议每天凌晨自动执行，或在更新 JSON 后手动执行

### Q: 如何备份数据？

A: 使用 mysqldump：
```bash
mysqldump -u root -p youth-chat fb_activities > backup.sql
```

---

## 📞 技术支持

如有问题，请查看：
1. 日志文件：`logs/db_import.log`
2. 执行详细输出：`python scripts/json_to_database.py --rag-dir rag_data 2>&1`
3. 数据库连接：检查 `.env` 文件中的 MySQL 配置
