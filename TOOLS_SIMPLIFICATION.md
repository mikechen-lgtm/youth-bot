# 工具簡化說明

**日期**：2026-01-27
**版本**：v2.0（簡化版）

## 簡化結果

從 **4 個工具** 簡化為 **2 個工具**

## 工具對比

### 優化前（4 個工具）

| # | 工具名稱 | 類型 | 用途 | 狀態 |
|---|---------|------|------|------|
| 1 | `get_current_time_info` | 時間工具 | 獲取當前時間資訊 | ❌ 已移除 |
| 2 | `calculate_date_range` | 時間工具 | 計算時間範圍 | ❌ 已移除 |
| 3 | `get_past_activities` | 資料庫工具 | 查詢過去活動 | ✅ 保留 |
| 4 | `get_recent_activities` | 資料庫工具 | 查詢近期活動 | ✅ 保留 |

### 優化後（2 個工具）

| # | 工具名稱 | 用途 | 時間計算 |
|---|---------|------|----------|
| 1 | `get_past_activities` | 查詢過去活動 | ✅ 內建（自動獲取當前時間並計算範圍） |
| 2 | `get_recent_activities` | 查詢近期活動 | ✅ 內建（自動獲取當前時間並計算範圍） |

## 為什麼可以移除工具 1 和 2？

### 原因 1：功能重複

**舊設計（需要 3 個步驟）：**
```
用戶：「最近有什麼活動？」
↓
步驟 1：AI 調用 get_current_time_info()
       → 返回 {"current_date": "2026/01/27"}
↓
步驟 2：AI 調用 calculate_date_range("today", 0, 90)
       → 返回 {"start_date": "2026/01/27", "end_date": "2026/04/27"}
↓
步驟 3：AI 調用 get_recent_activities()
       → 返回活動列表
```

**新設計（只需 1 個步驟）：**
```
用戶：「最近有什麼活動？」
↓
步驟 1：AI 調用 get_recent_activities(days_ahead=90)
       → 工具內部自動：
          1. datetime.now() 獲取當前時間
          2. 計算時間範圍（今天 → 未來 90 天）
          3. 查詢資料庫
          4. 返回活動列表
```

### 原因 2：資料庫工具已包含時間計算

查看 `database_tools.py` 的實現：

```python
def get_recent_activities(days_ahead: int = 90, limit: int = 20):
    # ✅ 自己獲取當前時間（工具 1 的功能）
    now = datetime.now(TAIPEI_TZ)

    # ✅ 自己計算時間範圍（工具 2 的功能）
    end_date = now + timedelta(days=days_ahead)

    # ✅ 查詢資料庫並返回結果
    query = text("""
        SELECT ... FROM fb_activities
        WHERE publish_date >= :now AND publish_date <= :end_date
        ORDER BY publish_date ASC
        LIMIT :limit
    """)
    ...
```

### 原因 3：降低複雜度

| 項目 | 優化前 | 優化後 |
|------|--------|--------|
| 工具數量 | 4 個 | 2 個 |
| AI 調用步驟 | 1-3 步 | 1 步 |
| 時間計算 | AI 手動計算 | 工具自動處理 |
| 錯誤風險 | ⚠️ 高（多步驟） | ✅ 低（單步驟） |
| 系統提示詞 | 複雜 | 簡潔 |

## 實際使用場景

### 場景 1：查詢近期活動

**用戶輸入**：
```
最近有什麼活動？
```

**AI 處理**：
```python
# 直接調用（1 步）
result = get_recent_activities(days_ahead=90, limit=20)

# result 包含：
{
  "success": true,
  "time_range": {
    "from": "2026/01/27",
    "to": "2026/04/27",
    "description": "今天到未來 90 天"
  },
  "total_count": 5,
  "activities": [...]
}
```

**AI 回答**：
```
目前有以下近期活動：

1. 青年創業講座
   時間：2026/02/15 14:00
   ...
```

### 場景 2：查詢過去活動

**用戶輸入**：
```
之前辦過什麼活動？
```

**AI 處理**：
```python
# 直接調用（1 步）
result = get_past_activities(days_back=30, limit=20)

# result 包含：
{
  "success": true,
  "time_range": {
    "from": "2025/12/28",
    "to": "2026/01/27",
    "description": "過去 30 天"
  },
  "total_count": 3,
  "activities": [...]
}
```

**AI 回答**：
```
過去 30 天內舉辦的活動：

1. 青春還鄉微電影巡迴影展
   時間：2026/01/21
   ...
```

### 場景 3：自訂查詢範圍

**用戶輸入**：
```
未來半年有什麼活動？
```

**AI 處理**：
```python
# 自訂參數
result = get_recent_activities(days_ahead=180, limit=50)
```

## 系統提示詞優化

### 優化前（複雜）

```
# 活動查詢處理

## 時間工具調用規則
- 見「最近」「近期」「今天」→ 立即調用 get_current_time_info
- 不可猜測當前日期

## 活動查詢的 4 步強制流程
1. 調用 get_current_time_info 取得 current_date（格式：2026/01/27）
2. 從檢索結果提取所有活動及日期
3. 逐一比較：活動日期 < current_date → 立即丟棄
4. 只回答保留的未來活動

## 時間範圍調用
- 最近/近期活動：calculate_date_range("today", 0, 90)
- 過去活動：calculate_date_range("today", -30, 0)
- 本週：calculate_date_range("today", 0, 7)
- 下個月：calculate_date_range("today", 30, 60)
```

### 優化後（簡潔）

```
# 活動查詢處理

## 工具調用規則

### 查詢近期/最近活動
用戶問「最近有什麼活動」「近期活動」「接下來有什麼」時：
- 調用 get_recent_activities(days_ahead=90, limit=20)
- 工具自動：獲取當前時間 → 計算時間範圍 → 查詢資料庫 → 過濾未來活動
- 直接使用返回的活動列表回答

### 查詢過去活動
用戶問「過去有什麼」「之前辦過什麼」時：
- 調用 get_past_activities(days_back=30, limit=20)
- 工具自動：獲取當前時間 → 計算時間範圍 → 查詢資料庫 → 過濾過去活動
- 直接使用返回的活動列表回答
```

**提示詞長度對比**：
- 優化前：~150 行
- 優化後：~20 行
- **減少 87%**

## 技術實現

### 代碼修改

**1. `openai_service.py` - 註銷時間工具**

```python
# 合併所有工具定義（優先使用資料庫工具）
ALL_TOOLS_DEFINITIONS = []
if DATABASE_TOOLS_AVAILABLE:
    ALL_TOOLS_DEFINITIONS.extend(DATABASE_TOOLS_DEFINITIONS)
# 時間工具作為備用（僅用於非活動查詢的時間問題）
# if TIME_TOOLS_AVAILABLE:
#     ALL_TOOLS_DEFINITIONS.extend(TIME_TOOLS_DEFINITIONS)  ← 已註銷
```

**2. `openai_service.py` - 更新工具分派**

```python
# 根據函數名稱分派到對應的執行函數
if function_name in ["get_past_activities", "get_recent_activities"]:
    result = execute_database_tool(function_name, arguments)
elif function_name in ["get_current_time_info", "calculate_date_range"]:
    # 時間工具已整合進資料庫工具
    result = {
        "error": "時間工具已停用，請使用 get_recent_activities 或 get_past_activities"
    }
```

**3. `app.py` - 更新系統提示詞**

移除關於時間工具的說明，只保留資料庫工具的使用指引。

## 測試驗證

### 測試 1：工具註冊驗證

```bash
$ python3 -c "import openai_service; print(len(openai_service.ALL_TOOLS_DEFINITIONS))"
2
```

✅ 成功：只註冊了 2 個工具

### 測試 2：功能測試

```bash
$ python3 -c "
from database_tools import get_recent_activities, get_past_activities

# 測試近期活動
result = get_recent_activities(days_ahead=90, limit=5)
print('近期活動:', result['total_count'], '筆')

# 測試過去活動
result = get_past_activities(days_back=30, limit=5)
print('過去活動:', result['total_count'], '筆')
"
```

輸出：
```
近期活動: 0 筆
過去活動: 3 筆
```

✅ 成功：工具正常運作

### 測試 3：時間計算驗證

```python
# get_recent_activities 內部處理
now = datetime.now(TAIPEI_TZ)          # 2026/01/27
end_date = now + timedelta(days=90)     # 2026/04/27

# SQL 查詢
WHERE publish_date >= '2026/01/27'
  AND publish_date <= '2026/04/27'
```

✅ 成功：時間計算正確

## 優勢總結

### ✅ 簡化系統

| 項目 | 改進 |
|------|------|
| 工具數量 | 4 → 2（減少 50%） |
| AI 調用步驟 | 1-3 步 → 1 步 |
| 系統提示詞 | 減少 87% |
| 代碼複雜度 | ⬇️ 大幅降低 |

### ✅ 提高效率

- **減少 Token 消耗**：少調用 2 個工具
- **加快回應速度**：1 步完成查詢
- **降低錯誤率**：單步驟不易出錯

### ✅ 易於維護

- **邏輯集中**：時間計算邏輯在工具內部
- **修改方便**：只需修改 2 個工具
- **測試簡單**：測試點減少

## 注意事項

### ⚠️ 時間工具仍保留代碼

時間工具（`time_tools.py`）的代碼仍保留在系統中，只是沒有註冊到 OpenAI Function Calling。

**原因**：
1. 作為備用（未來可能需要）
2. 其他模組可能依賴（如測試）

### ⚠️ 可以輕易恢復

如需恢復時間工具，只需取消註釋：

```python
# openai_service.py
if TIME_TOOLS_AVAILABLE:
    ALL_TOOLS_DEFINITIONS.extend(TIME_TOOLS_DEFINITIONS)  # 取消註釋
```

## 未來擴展

如需新增其他活動查詢功能，直接在 `database_tools.py` 新增即可：

```python
def search_activities(keyword: str, days_ahead: int = 90) -> Dict[str, Any]:
    """根據關鍵字搜尋活動"""
    pass

def get_activities_by_tag(tag: str, days_ahead: int = 90) -> Dict[str, Any]:
    """根據標籤篩選活動"""
    pass

def get_activities_by_source(source: str, days_ahead: int = 90) -> Dict[str, Any]:
    """根據來源篩選活動"""
    pass
```

## 總結

通過將時間計算邏輯整合進資料庫工具，成功簡化系統：

- ✅ 工具數量：4 → 2（減少 50%）
- ✅ 系統提示詞：減少 87%
- ✅ AI 調用步驟：減少 67%（3 步 → 1 步）
- ✅ Token 消耗：大幅降低
- ✅ 維護成本：顯著降低
- ✅ 錯誤風險：明顯減少

**核心理念**：工具應該盡可能自包含，減少 AI 的手動協調工作。
