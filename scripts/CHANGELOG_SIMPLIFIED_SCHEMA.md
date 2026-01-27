# 資料表結構簡化變更說明

**日期**：2026-01-27
**版本**：v2.0（簡化版）

## 變更摘要

資料表欄位從 **22 個**簡化為 **12 個**，直接對應 JSON 字段，移除所有從 content 解析的欄位。

## 主要變更

### 1. 資料表結構簡化

**保留欄位（12 個）**：
```
✅ id (主鍵)
✅ source (來源，從檔名提取)
✅ post_id (對應 JSON 的 id)
✅ title (對應 JSON 的 title)
✅ content (對應 JSON 的 content)
✅ publish_date (對應 JSON 的 publish_date)
✅ url (對應 JSON 的 url)
✅ tags (對應 JSON 的 tags)
✅ retrieval_time (對應 JSON 的 retrieval_time)
✅ raw_data (完整 JSON)
✅ created_at (資料表時間戳)
✅ updated_at (資料表時間戳)
```

**移除欄位（10 個）**：
```
❌ event_date - 從 content 解析的活動日期
❌ event_time - 從 content 解析的活動時間
❌ deadline - 從 content 解析的報名截止
❌ location - 從 content 解析的地點
❌ location_address - 從 content 解析的詳細地址
❌ target - 從 content 解析的適用對象
❌ activity_type - 從 content 解析的活動類型
❌ registration_url - 從 content 解析的報名連結
❌ info_url - 從 content 解析的詳細資訊連結
❌ focus_areas - 從 content 解析的聚焦領域
❌ categories - 從 content 解析的提案類別
❌ subsidy - 從 content 解析的補助金額
```

### 2. 唯一鍵變更

**舊版**：`(source, title, event_date)`
- 問題：依賴解析的 event_date，不穩定

**新版**：`(source, post_id)`
- 優勢：使用 JSON 原生的 ID，穩定可靠

### 3. 導入邏輯簡化

**舊版**：
- 嘗試從 content 提取日期（ISO、民國年、月日等）
- 無法提取日期則跳過該貼文
- 840 個貼文中只匯入 164 個（20%）

**新版**：
- 不進行日期解析
- 所有貼文都匯入
- 840 個貼文全部成功匯入（100%）

## 為什麼要簡化？

### 舊版問題

1. **解析不穩定**
   - content 格式多變，日期提取失敗率高
   - 80% 的貼文因無法提取日期而被跳過
   - 解析邏輯複雜，容易出錯

2. **資料表結構複雜**
   - 22 個欄位，大部分都是解析結果
   - 維護困難，不知道哪些欄位有資料

3. **違反單一職責原則**
   - 匯入腳本不應該負責解析業務邏輯
   - 解析應該在應用層處理

### 新版優勢

1. **穩定可靠**
   - 只儲存 JSON 原始欄位
   - 100% 匯入成功率
   - 不會因解析失敗而遺失資料

2. **結構清晰**
   - 12 個欄位，每個都有明確意義
   - 一眼就能看出哪些是原始資料

3. **靈活性高**
   - 需要解析時，在應用層從 `raw_data` 或 `content` 提取
   - 解析邏輯可以隨時調整，不影響資料表

4. **完整性保證**
   - 所有貼文都保存在資料表中
   - `raw_data` 保留完整 JSON，隨時可以重新處理

## 資料對比

### 舊版結果

```
處理檔案數：3
貼文總數：840
✅ 成功匯入：164 (20%)
⏭️  跳過（無日期）：672 (80%)
❌ 失敗：0

總活動數：164
未來活動：52
過去活動：112
```

### 新版結果

```
處理檔案數：3
貼文總數：840
✅ 成功匯入：840 (100%)
❌ 失敗：0

總貼文數：840
來源數量：3
最早發布：2025-01-01
最晚發布：2026-01-21
```

## 如果需要解析資料怎麼辦？

### 方法 1：在查詢時解析

```python
def extract_date_from_content(content: str):
    """從 content 提取日期"""
    # 使用正則表達式或 LLM 解析
    pass

# 查詢時動態解析
with engine.begin() as conn:
    result = conn.execute(text("""
        SELECT id, content, raw_data
        FROM fb_activities
    """))

    for row in result:
        # 動態解析
        date = extract_date_from_content(row.content)
        if date:
            print(f"活動日期：{date}")
```

### 方法 2：創建視圖

```sql
CREATE VIEW fb_activities_with_dates AS
SELECT
    *,
    -- 使用 MySQL 正則提取日期
    REGEXP_SUBSTR(content, '[0-9]{4}[/-][0-9]{1,2}[/-][0-9]{1,2}') as extracted_date
FROM fb_activities;
```

### 方法 3：使用 LLM 批次處理

```python
# 使用 GPT/Claude 批次提取結構化資訊
for post in posts:
    structured_data = llm.extract({
        "content": post.content,
        "extract": ["event_date", "location", "registration_url"]
    })
    # 儲存到另一個表或快取
```

## 遷移指南

如果你已經在使用舊版資料表：

```bash
# 1. 備份舊資料
mysqldump -u root -p youth-chat fb_activities > backup_old_schema.sql

# 2. 刪除舊資料表
mysql -u root -p youth-chat -e "DROP TABLE fb_activities"

# 3. 重新匯入（會自動創建新結構）
python scripts/json_to_database.py --rag-dir rag_data

# 4. 驗證
python -c "
from scripts.json_to_database import create_engine_instance
from sqlalchemy import text
engine = create_engine_instance()
with engine.begin() as conn:
    result = conn.execute(text('SELECT COUNT(*) FROM fb_activities'))
    print(f'總貼文數：{result.scalar()}')
"
```

## 總結

| 項目 | 舊版 | 新版 |
|------|------|------|
| 欄位數量 | 22 | 12 |
| 解析邏輯 | ✅ 內建 | ❌ 無 |
| 匯入成功率 | 20% (164/840) | 100% (840/840) |
| 資料完整性 | ⚠️ 80% 資料遺失 | ✅ 完整保留 |
| 維護複雜度 | ⚠️ 高 | ✅ 低 |
| 靈活性 | ⚠️ 低 | ✅ 高 |
| 穩定性 | ⚠️ 不穩定 | ✅ 穩定 |

**結論**：新版本遵循「先儲存，後處理」的原則，確保資料完整性，並將解析邏輯移到應用層，提高了系統的穩定性和靈活性。
