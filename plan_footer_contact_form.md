# Footer 聯絡表單計畫

## 目標
在網站 Footer 新增聯絡表單區塊，嵌入 Google 表單收集民眾回饋。

## Google 表單連結
```
https://docs.google.com/forms/d/e/1FAIpQLSeU_Ntx-uR3E6f9zLw6PBgbmdGXhRjQwMP-YzYIBgrBJ78Iyw/viewform
```

## 實作方案比較

| 方案 | 優點 | 缺點 |
|------|------|------|
| **A. iframe 嵌入** | 無縫體驗、不跳轉 | 載入較慢、高度需固定、手機體驗差 |
| **B. 視覺預覽 + 連結** | 載入快、視覺可控 | 需跳轉到 Google Form |
| **C. 自訂表單 + API** | 完全客製化 | 需後端處理、開發成本高 |

**建議採用方案 B**：設計美觀的聯絡區塊，點擊後開啟 Google 表單（新分頁）。

---

## 設計規格

### 版面配置（參考 jcard.io）
```
┌─────────────────────────────────────────────────────────────┐
│                    聯絡我們 / 意見回饋                        │
├──────────────────────────┬──────────────────────────────────┤
│    左側：說明文字         │    右側：表單預覽/CTA             │
│    - 標題                │    - 簡短說明                     │
│    - 描述用途             │    - 「填寫表單」按鈕             │
│    - 聯絡資訊（可選）      │    - 或 iframe 嵌入              │
└──────────────────────────┴──────────────────────────────────┘
```

### 視覺風格
- 背景：深色 (`bg-dark` #134A73) 維持現有風格
- 新增區塊背景：稍淺色調或半透明白
- 按鈕：主色調 `bg-primary` 或 `bg-accent`
- 響應式：手機版垂直排列

---

## 實作步驟

### 步驟 1：修改 Footer 結構
- 檔案：`index.html`
- 位置：`<footer>` 區塊（約 359-377 行）
- 新增「意見回饋」區塊於現有內容之前

### 步驟 2：新增 HTML 結構
```html
<!-- 意見回饋區塊 -->
<div class="border-b border-white border-opacity-20 pb-8 mb-8">
  <div class="flex flex-col md:flex-row gap-8">
    <!-- 左側說明 -->
    <div class="md:w-1/2">
      <h3 class="text-2xl font-bold mb-4">意見回饋</h3>
      <p class="text-white opacity-80 mb-4">
        有任何問題或建議嗎？歡迎填寫表單讓我們知道，
        您的意見將成為我們改進的重要參考。
      </p>
      <p class="text-white opacity-60 text-sm">
        回覆將自動同步至 Google Sheets，我們會盡快處理。
      </p>
    </div>
    <!-- 右側 CTA -->
    <div class="md:w-1/2 flex items-center justify-center md:justify-end">
      <a href="[GOOGLE_FORM_URL]"
         target="_blank"
         rel="noopener noreferrer"
         class="inline-flex items-center gap-2 bg-accent hover:bg-opacity-90
                text-white px-8 py-4 rounded-lg text-lg font-bold
                transition-all-300 shadow-lg">
        <i class="fa fa-pencil-square-o"></i>
        填寫意見表單
      </a>
    </div>
  </div>
</div>
```

### 步驟 3：樣式調整
- 確保響應式設計（手機垂直、桌面水平）
- 按鈕 hover 效果
- AOS 動畫（可選）

---

## 替代方案：iframe 嵌入

若希望直接嵌入表單（不跳轉），可使用：

```html
<iframe
  src="https://docs.google.com/forms/d/e/1FAIpQLSeU_Ntx-uR3E6f9zLw6PBgbmdGXhRjQwMP-YzYIBgrBJ78Iyw/viewform?embedded=true"
  width="100%"
  height="600"
  frameborder="0"
  marginheight="0"
  marginwidth="0"
  class="rounded-lg">
  載入中…
</iframe>
```

**注意**：iframe 在深色背景上會有白色表單底，可能需要額外樣式處理。

---

## 檔案變更清單

| 檔案 | 變更內容 |
|------|----------|
| `index.html` | Footer 區塊新增意見回饋 section |

---

## 預估影響
- 無後端變更
- 無新增依賴
- 載入速度影響：極小（僅新增靜態 HTML）
