# JSON 轉資料表工具使用說明

## 功能說明

將 `rag_data` 目錄中的 JSON 檔案匯入 MySQL `fb_activities` 資料表，資料表欄位**直接對應 JSON 字段**，不進行額外解析。

特點：
- ✅ 資料表欄位對應 JSON 字段（無額外解析）
- ✅ 自動去重（依據 source + post_id）
- ✅ 增量更新（重複資料自動更新）
- ✅ 保留完整原始資料（raw_data 欄位）

## 資料表結構

### fb_activities 表字段

| 字段名 | 類型 | 說明 | 對應 JSON 字段 |
|--------|------|------|---------------|
| `id` | INT | 主鍵（自動遞增）| - |
| `source` | VARCHAR(100) | 來源（從檔名提取）| - |
| `post_id` | INT | Post ID | `id` |
| `title` | VARCHAR(500) | 標題 | `title` |
| `content` | TEXT | 內容 | `content` |
| `publish_date` | DATETIME | 發布日期 | `publish_date` |
| `url` | VARCHAR(1000) | 原文連結 | `url` |
| `tags` | JSON | 標籤（JSON 陣列）| `tags` |
| `retrieval_time` | DATETIME | 爬取時間 | `retrieval_time` |
| `raw_data` | JSON | 完整原始資料 | (整個 post 物件) |
| `created_at` | DATETIME | 創建時間 | - |
| `updated_at` | DATETIME | 更新時間 | - |

### 索引

- `idx_source` - 來源索引
- `idx_title` - 標題索引（前 100 字符）
- `idx_publish_date` - 發布日期索引
- `unique_post` - 唯一鍵（source + post_id，防止重複）

## 使用方法

### 基本用法

```bash
python scripts/json_to_database.py --rag-dir rag_data
```

### 試運行模式（不實際寫入）

```bash
python scripts/json_to_database.py --rag-dir rag_data --dry-run
```

## 執行結果

```
🔗 連接資料庫...
✓ 資料表 'fb_activities' 已確保存在

🚀 開始處理...
   輸入目錄：rag_data

📂 找到 3 個 JSON 檔案

處理來源：桃青參一咖（336 個貼文）
  ✓ [1] 【桃青紀錄】青春還鄉微電影——#桃園 元智資傳系「以勒小分隊」的拍攝作品 🎬✨
  ✓ [2] 【桃青紀錄】青春還鄉微電影——桃園團隊介紹 🎬✨
  ...

============================================================
📊 匯入統計
============================================================
處理檔案數：3
貼文總數：840
✅ 成功匯入：840
❌ 失敗：0
============================================================

================================================================================
📋 資料表摘要
================================================================================
來源                           總數       最早發布       最晚發布
--------------------------------------------------------------------------------
桃園市政府青年事務局            320     2025-01-01    2026-01-09
桃園青創事                     184     2025-01-01    2026-01-21
桃青參一咖                     336     2025-01-04    2026-01-21
--------------------------------------------------------------------------------
總計                           840
================================================================================
```

## 去重機制

### 唯一鍵組合
```sql
UNIQUE KEY unique_post (source, post_id)
```

**相同貼文判定**：
- 來源相同 AND
- Post ID 相同

### 更新策略

如果檢測到重複貼文，會自動更新以下字段：
- `title` - 標題
- `content` - 內容
- `publish_date` - 發布日期
- `url` - 連結
- `tags` - 標籤
- `retrieval_time` - 爬取時間
- `raw_data` - 原始資料
- `updated_at` - 更新時間

## 常用查詢

### 1. 查詢最近的貼文

```sql
SELECT
    source,
    title,
    publish_date,
    url
FROM fb_activities
ORDER BY publish_date DESC
LIMIT 20;
```

### 2. 查詢特定來源的貼文

```sql
SELECT
    title,
    publish_date,
    url
FROM fb_activities
WHERE source = '桃園市政府青年事務局'
ORDER BY publish_date DESC;
```

### 3. 查詢最近 30 天的貼文

```sql
SELECT
    source,
    title,
    publish_date
FROM fb_activities
WHERE publish_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
ORDER BY publish_date DESC;
```

### 4. 查詢有標籤的貼文

```sql
SELECT
    title,
    publish_date,
    JSON_EXTRACT(tags, '$') as tags
FROM fb_activities
WHERE tags IS NOT NULL
  AND JSON_LENGTH(tags) > 0
ORDER BY publish_date DESC;
```

### 5. 按來源統計貼文數量

```sql
SELECT
    source,
    COUNT(*) as total,
    MIN(publish_date) as earliest,
    MAX(publish_date) as latest
FROM fb_activities
GROUP BY source
ORDER BY total DESC;
```

## 資料維護

### 定期更新

建議每天執行一次，保持資料最新：

```bash
# 添加到 crontab
0 2 * * * cd /home/creative_design/youth-bot && python scripts/json_to_database.py --rag-dir rag_data >> logs/db_import.log 2>&1
```

### 清理過期資料

保留過去 6 個月內的貼文：

```sql
DELETE FROM fb_activities
WHERE publish_date < DATE_SUB(CURDATE(), INTERVAL 6 MONTH);
```

### 重新匯入所有資料

```bash
# 1. 清空資料表
mysql -u root -p youth-chat -e "TRUNCATE TABLE fb_activities"

# 2. 重新匯入
python scripts/json_to_database.py --rag-dir rag_data
```

## 整合到應用程式

### Python 查詢範例

```python
from sqlalchemy import create_engine, text

# 創建連線
engine = create_engine("mysql+pymysql://user:pass@localhost/youth-chat")

# 查詢最近貼文
with engine.begin() as conn:
    result = conn.execute(
        text("""
            SELECT title, publish_date, content, url
            FROM fb_activities
            ORDER BY publish_date DESC
            LIMIT 10
        """)
    )

    posts = result.fetchall()
    for post in posts:
        print(f"{post.title} - {post.publish_date}")
```

### 整合到 RAG 系統

```python
def get_recent_posts(days: int = 30, limit: int = 20):
    """從資料表查詢最近的貼文"""
    with engine.begin() as conn:
        result = conn.execute(text("""
            SELECT source, title, content, publish_date, url
            FROM fb_activities
            WHERE publish_date >= DATE_SUB(NOW(), INTERVAL :days DAY)
            ORDER BY publish_date DESC
            LIMIT :limit
        """), {"days": days, "limit": limit})
        return result.fetchall()

def format_posts_for_rag(posts):
    """格式化為 RAG 輸入"""
    text = "# 最近的貼文\n\n"
    for post in posts:
        text += f"## {post.title}\n"
        text += f"**來源**：{post.source}\n"
        text += f"**日期**：{post.publish_date}\n\n"
        text += f"{post.content}\n\n"
        text += f"[查看原文]({post.url})\n\n---\n\n"
    return text
```

## 故障排除

### 問題：無法連接資料庫

檢查 `.env` 文件配置：
```env
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=youth-chat
```

### 問題：重複資料未更新

檢查唯一鍵是否完全匹配（source + post_id）

## 效能優化

### 根據查詢需求添加索引

```sql
-- 針對「最近貼文」查詢
CREATE INDEX idx_recent_posts
ON fb_activities(publish_date DESC, source);

-- 針對「標籤查詢」
CREATE INDEX idx_tags
ON fb_activities((CAST(tags AS CHAR(255))));
```

## 與舊版本的差異

### 舊版本（已棄用）

舊版本嘗試從 content 解析額外欄位：
- event_date, event_time, deadline
- location, location_address, target, activity_type
- registration_url, info_url
- focus_areas, categories, subsidy

**問題**：
- 解析不穩定，容易出錯
- 資料表結構複雜
- 維護成本高

### 新版本（當前）

新版本只保留 JSON 中實際存在的字段：
- 直接對應 JSON 字段
- 不進行額外解析
- 如需解析，在應用層處理（從 raw_data 或 content）

**優勢**：
- 穩定可靠
- 結構簡單
- 易於維護

## 總結

- ✅ **簡化** - 資料表欄位直接對應 JSON 字段
- ✅ **自動化** - 一鍵匯入所有 JSON 資料
- ✅ **智慧去重** - 避免重複資料
- ✅ **增量更新** - 支援定期更新
- ✅ **結構化儲存** - 便於查詢和分析

## 相關文檔

- [腳本總覽](README.md)
- [工作流程](WORKFLOW.md)
