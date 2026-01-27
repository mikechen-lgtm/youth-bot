# 資料庫查詢工具使用指南

**日期**：2026-01-27
**版本**：v1.0

## 概述

新增兩個 OpenAI Function Calling 工具，用於從 MySQL 資料表 `fb_activities` 查詢活動資料。這些工具直接查詢資料庫，確保返回即時、準確的活動資訊。

## 工具列表

### 1. `get_recent_activities` - 查詢近期活動

**用途**：查詢未來的活動（發布時間在今天到未來 N 天內）

**適用場景**：
- 用戶問「最近有什麼活動」
- 用戶問「近期活動」
- 用戶問「接下來有什麼」

**參數**：
```python
{
  "days_ahead": 90,   # 往後查詢的天數（預設 90 天，約 3 個月）
  "limit": 20         # 最多返回幾筆（預設 20 筆）
}
```

**返回格式**：
```json
{
  "success": true,
  "query_type": "recent_activities",
  "time_range": {
    "from": "2026/01/27",
    "to": "2026/04/27",
    "description": "今天到未來 90 天"
  },
  "total_count": 5,
  "activities": [
    {
      "source": "桃園市政府青年事務局",
      "title": "活動標題",
      "content": "活動內容（限制 200 字）...",
      "publish_date": "2026/02/15 10:00",
      "url": "https://www.facebook.com/...",
      "tags": ["青年創業", "講座"]
    }
  ]
}
```

### 2. `get_past_activities` - 查詢過去活動

**用途**：查詢過去的活動（發布時間在今天之前）

**適用場景**：
- 用戶問「過去有什麼活動」
- 用戶問「之前辦過什麼」
- 用戶想了解歷史活動

**參數**：
```python
{
  "days_back": 30,    # 往前查詢的天數（預設 30 天）
  "limit": 20         # 最多返回幾筆（預設 20 筆）
}
```

**返回格式**：
與 `get_recent_activities` 相同

## 工具特點

### 🎯 直接查詢資料庫
- 不依賴 RAG 知識庫（可能過期）
- 查詢即時資料
- 確保資料準確性

### ⏰ 自動時間過濾
- `get_recent_activities` 自動過濾未來活動
- `get_past_activities` 自動過濾過去活動
- 使用台北時區 (Asia/Taipei)

### 📊 結構化返回
- 統一的 JSON 格式
- 包含時間範圍說明
- 活動資料完整（來源、標題、內容、日期、連結、標籤）

### 🚀 高效查詢
- 使用資料庫索引
- 限制返回筆數
- 限制內容長度（200 字）

## 系統提示詞優化

### 優化前（複雜的時間計算）

```
## 活動查詢的 4 步強制流程
1. 調用 get_current_time_info 取得 current_date（格式：2026/01/27）
2. 從檢索結果提取所有活動及日期
3. 逐一比較：活動日期 < current_date → 立即丟棄
4. 只回答保留的未來活動

## 時間範圍調用
- 最近/近期活動：calculate_date_range("today", 0, 90)（未來3個月）
- 過去活動：calculate_date_range("today", -30, 0)（過去1個月）
- 本週：calculate_date_range("today", 0, 7)
- 下個月：calculate_date_range("today", 30, 60)
```

### 優化後（簡潔明瞭）

```
## 活動查詢的強制要求
當用戶詢問活動時：
1. 近期/最近活動 → 必須調用 get_recent_activities（查詢未來 3 個月）
2. 過去活動 → 調用 get_past_activities（查詢過去 30 天）
3. 嚴禁使用 RAG 知識庫回答活動查詢（資料可能過期）
4. 必須使用資料庫工具查詢即時資料
```

### 優化效果

| 項目 | 優化前 | 優化後 |
|------|--------|--------|
| 提示詞長度 | ~150 行 | ~20 行 |
| 步驟數量 | 4 步手動流程 | 1 步調用工具 |
| 時間計算 | AI 手動計算 | 工具自動處理 |
| 錯誤風險 | ⚠️ 高（手動過濾） | ✅ 低（自動過濾） |
| Token 消耗 | ⚠️ 高 | ✅ 低 |

## 使用範例

### 範例 1：查詢近期活動

**用戶**：最近有什麼活動？

**AI 處理流程**：
1. 檢測到「最近」關鍵字
2. 調用 `get_recent_activities(days_ahead=90, limit=20)`
3. 接收到活動列表
4. 用自然語言回答用戶

**AI 回答**：
```
目前有以下近期活動：

1. **青年創業講座**
   時間：2026/02/15 14:00
   主辦：桃園市政府青年事務局
   了解更多：https://www.facebook.com/...

2. **職涯探索工作坊**
   時間：2026/02/20 10:00
   主辦：桃園青創事
   了解更多：https://www.facebook.com/...

...
```

### 範例 2：查詢過去活動

**用戶**：之前辦過什麼活動？

**AI 處理流程**：
1. 檢測到「之前」關鍵字
2. 調用 `get_past_activities(days_back=30, limit=20)`
3. 接收到活動列表
4. 用自然語言回答用戶

**AI 回答**：
```
過去 30 天內舉辦的活動：

1. **2025青春還鄉微電影巡迴影展**
   時間：2026/01/21
   主辦：桃青參一咖
   了解更多：https://www.facebook.com/...

2. **日新對話：投資科技與科技治理講座**
   時間：2026/01/21
   主辦：桃園青創事
   了解更多：https://www.facebook.com/...

...
```

### 範例 3：沒有活動

**用戶**：最近有什麼活動？

**工具返回**：`{ "total_count": 0, "activities": [] }`

**AI 回答**：
```
目前沒有查詢到即將舉辦的活動。

建議追蹤官方粉專取得最新資訊：
- 桃園青創事 Facebook
- 桃園市政府青年事務局 Facebook
  https://www.facebook.com/youth.tycg.gov.tw

或聯繫：總機 (03) 422-5205 / 市政專線 1999
```

## 技術實現

### 文件結構

```
youth-bot/
├── database_tools.py           # 新增：資料庫查詢工具
├── openai_service.py          # 修改：整合資料庫工具
├── app.py                     # 修改：優化系統提示詞
└── scripts/
    └── json_to_database.py    # 已存在：JSON 匯入腳本
```

### 資料庫查詢邏輯

**近期活動查詢**：
```sql
SELECT source, title, content, publish_date, url, tags
FROM fb_activities
WHERE publish_date >= :now
  AND publish_date <= :end_date
ORDER BY publish_date ASC
LIMIT :limit
```

**過去活動查詢**：
```sql
SELECT source, title, content, publish_date, url, tags
FROM fb_activities
WHERE publish_date < :now
  AND publish_date >= :start_date
ORDER BY publish_date DESC
LIMIT :limit
```

### 工具註冊

```python
# openai_service.py

# 導入資料庫工具
from database_tools import DATABASE_TOOLS_DEFINITIONS, execute_database_tool

# 合併所有工具定義
ALL_TOOLS_DEFINITIONS = []
if TIME_TOOLS_AVAILABLE:
    ALL_TOOLS_DEFINITIONS.extend(TIME_TOOLS_DEFINITIONS)
if DATABASE_TOOLS_AVAILABLE:
    ALL_TOOLS_DEFINITIONS.extend(DATABASE_TOOLS_DEFINITIONS)

# 工具調用分派
if function_name in ["get_current_time_info", "calculate_date_range"]:
    result = execute_time_tool(function_name, arguments)
elif function_name in ["get_past_activities", "get_recent_activities"]:
    result = execute_database_tool(function_name, arguments)
```

## 測試驗證

### 測試 1：資料庫工具功能測試

```bash
python3 -c "
from database_tools import get_recent_activities, get_past_activities
import json

# 測試近期活動
result = get_recent_activities(days_ahead=90, limit=5)
print(json.dumps(result, ensure_ascii=False, indent=2))

# 測試過去活動
result = get_past_activities(days_back=30, limit=5)
print(json.dumps(result, ensure_ascii=False, indent=2))
"
```

**預期結果**：
- ✅ 返回結構化 JSON
- ✅ 包含時間範圍資訊
- ✅ 活動列表正確

### 測試 2：工具註冊驗證

```bash
python3 -c "
import openai_service
print('已註冊工具數量：', len(openai_service.ALL_TOOLS_DEFINITIONS))
print('資料庫工具可用：', openai_service.DATABASE_TOOLS_AVAILABLE)
print('時間工具可用：', openai_service.TIME_TOOLS_AVAILABLE)
"
```

**預期結果**：
- ✅ 已註冊 4 個工具
- ✅ 資料庫工具可用：True
- ✅ 時間工具可用：True

### 測試 3：後端啟動測試

```bash
python3 app.py
```

**預期結果**：
- ✅ 無導入錯誤
- ✅ 資料庫工具模組載入成功
- ✅ Flask 正常啟動

## 注意事項

### ⚠️ 資料表依賴

這些工具依賴 `fb_activities` 資料表，請確保：
1. 資料表已創建（透過 `json_to_database.py`）
2. 資料庫連線配置正確（`.env` 文件）
3. 資料表有足夠的活動資料

### ⚠️ 時間欄位

工具使用 `publish_date`（貼文發布時間）而非 `retrieval_time`（爬取時間）來篩選活動。這是因為：
- `publish_date` = Facebook 發布這個貼文的時間
- `retrieval_time` = 系統爬取這個貼文的時間

對於「近期活動」查詢，應該看發布時間，而不是爬取時間。

### ⚠️ 內容長度限制

為了控制 Token 消耗，工具返回的 `content` 欄位限制為 200 字。如需完整內容，用戶可以點擊 `url` 查看原文。

## 未來改進

### 1. 增加搜尋功能

```python
def search_activities(
    keyword: str,
    days_ahead: int = 90,
    limit: int = 20
) -> Dict[str, Any]:
    """根據關鍵字搜尋活動"""
    pass
```

### 2. 按標籤篩選

```python
def get_activities_by_tag(
    tag: str,
    days_ahead: int = 90,
    limit: int = 20
) -> Dict[str, Any]:
    """根據標籤篩選活動"""
    pass
```

### 3. 按來源篩選

```python
def get_activities_by_source(
    source: str,
    days_ahead: int = 90,
    limit: int = 20
) -> Dict[str, Any]:
    """根據來源篩選活動"""
    pass
```

## 總結

### ✅ 已完成

1. ✅ 創建 `database_tools.py` 模組
   - `get_recent_activities()` - 查詢近期活動
   - `get_past_activities()` - 查詢過去活動

2. ✅ 更新 `openai_service.py`
   - 導入資料庫工具
   - 合併工具定義
   - 工具調用分派

3. ✅ 優化系統提示詞（`app.py`）
   - 簡化活動查詢規則
   - 移除手動時間計算
   - 清晰的工具調用指引

4. ✅ 測試驗證
   - 資料庫工具功能測試通過
   - 工具註冊驗證通過

### 📊 效果

| 項目 | 改進 |
|------|------|
| 系統提示詞 | 減少 ~130 行 → ~20 行（85% 簡化） |
| 查詢準確性 | ⚠️ 依賴 AI 手動過濾 → ✅ 資料庫自動過濾 |
| Token 消耗 | ⚠️ 高（手動計算） → ✅ 低（工具處理） |
| 維護複雜度 | ⚠️ 高 → ✅ 低 |
| 資料即時性 | ⚠️ RAG 可能過期 → ✅ 資料庫即時查詢 |

### 🎯 核心優勢

1. **計算細節已移到函數** - AI 不需要手動計算時間範圍
2. **自動過濾過期活動** - 資料庫查詢自動過濾，AI 無需手動比對
3. **查詢即時資料** - 直接從資料庫查詢，不依賴可能過期的 RAG
4. **簡化系統提示詞** - 85% 簡化，降低 Token 消耗
5. **降低錯誤風險** - 工具自動處理，減少 AI 誤判

## 相關文檔

- [資料庫匯入工具說明](scripts/README_database.md)
- [系統提示詞優化報告](SYSTEM_PROMPT_OPTIMIZATION.md)
- [資料表結構簡化說明](scripts/CHANGELOG_SIMPLIFIED_SCHEMA.md)
