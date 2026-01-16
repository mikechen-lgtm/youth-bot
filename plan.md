# AI 無法回答時導向回饋表單 - 實現計劃

## 需求摘要
當 AI 無法回答問題時，顯示標準說明文字和 Google Form 連結按鈕。

## 目前程式碼分析

### 已有的基礎設施
1. **FEEDBACK_FORM_URL** 環境變數已定義於 `app.py:151`
2. **System Prompt** 已包含無法回答時的引導邏輯 (`app.py:159-178`)
3. **MarkdownText** 組件已支援連結在新視窗開啟 (`target="_blank"`)

### 缺少的部分
1. `.env` 未設定 `FEEDBACK_FORM_URL`
2. 連結樣式需要更像「按鈕」而非普通連結

---

## 實現步驟

### Step 1: 設定環境變數
在 `.env` 添加：
```
FEEDBACK_FORM_URL=https://docs.google.com/forms/d/e/1FAIpQLSeU_Ntx-uR3E6f9zLw6PBgbmdGXhRjQwMP-YzYIBgrBJ78Iyw/viewform?usp=sharing&ouid=102116035023632563277
```

### Step 2: 優化 System Prompt
更新 `app.py` 中的 fallback 訊息格式，確保：
- 包含「目前資料不足」說明
- 包含表單 CTA
- 格式清晰易讀

### Step 3: 前端按鈕樣式（可選）
在 `MarkdownText.tsx` 中，為特定格式的連結添加按鈕樣式。
例如：當連結文字包含「填寫」「表單」時，顯示為按鈕樣式。

---

## 驗收標準對照

| AC | 說明 | 實現方式 |
|----|------|---------|
| AC-01 | 包含「目前資料不足」說明 | System Prompt 引導 AI 輸出 |
| AC-01 | 表單導引 CTA | Markdown 連結 + 按鈕樣式 |
| AC-01 | Google 表單連結 | 環境變數 FEEDBACK_FORM_URL |
| AC-02 | 新視窗開啟表單 | MarkdownText 的 `target="_blank"` |

---

## 預估影響
- **後端**：修改 `.env`、可能微調 system prompt
- **前端**：可選的按鈕樣式優化
- **重啟**：需重啟後端載入新環境變數
