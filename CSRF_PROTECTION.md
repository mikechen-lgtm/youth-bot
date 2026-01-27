# CSRF 保護實施文檔

## 概述

本文檔說明了在 Youth Bot 項目中實施的 CSRF（跨站請求偽造）保護機制。

## 已實施的安全措施

### 1. **Cookie 安全設置** ✅

已將 Session Cookie 設置從 `SameSite='Lax'` 更新為 `SameSite='Strict'`：

```python
# app.py:112
SESSION_COOKIE_SAMESITE='Strict'
```

**影響**：
- 阻止所有跨站點請求攜帶 Session Cookie
- 更嚴格的 CSRF 保護
- 提高整體安全性

### 2. **CSRF Token 機制** ✅

#### 後端實現

創建了完整的 CSRF 保護模塊（`csrf_protection.py`）：

- **CSRFProtection 類**：處理 Token 生成、驗證和管理
- **@csrf_protect 裝飾器**：保護需要 CSRF 驗證的路由
- **@csrf_exempt 裝飾器**：排除公開端點的 CSRF 檢查

#### 受保護的路由

以下管理員路由已添加 CSRF 保護：

| 路由 | 方法 | 說明 |
|------|------|------|
| `/api/admin/login` | POST | 管理員登錄 |
| `/api/admin/logout` | POST | 管理員登出 |
| `/api/admin/hero-images` | POST | 上傳圖片 |
| `/api/admin/hero-images/<id>` | DELETE | 刪除圖片 |
| `/api/admin/hero-images/<id>` | PUT | 更新圖片 |
| `/api/admin/hero-images/reorder` | PUT | 重新排序 |

#### 公開端點（免除 CSRF）

| 路由 | 方法 | 說明 |
|------|------|------|
| `/api/chat` | POST | 聊天機器人（公開） |
| `/api/csrf-token` | GET | 獲取 CSRF Token |
| `/api/admin/check` | GET | 檢查認證狀態 |

### 3. **前端集成** ✅

#### CSRF Manager (`src/utils/csrf.ts`)

創建了專門的 CSRF Token 管理工具：

```typescript
import { csrfManager } from '../utils/csrf';

// 自動獲取並在請求中包含 CSRF Token
const response = await csrfManager.protectedFetch('/api/admin/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ username, password })
});
```

**功能**：
- 自動獲取和緩存 CSRF Token
- 在所有受保護的請求中自動添加 `X-CSRF-Token` 標頭
- 從登錄響應中更新 Token
- 登出時清除 Token

#### Admin API 服務更新

所有管理員 API 調用已更新為使用 `csrfManager.protectedFetch()`：

```typescript
// 舊方法（不安全）
const response = await fetch('/api/admin/login', {
  method: 'POST',
  credentials: 'include',
  body: JSON.stringify({ username, password })
});

// 新方法（有 CSRF 保護）
const response = await csrfManager.protectedFetch('/api/admin/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ username, password })
});
```

## 工作流程

### 登錄流程

```
1. 前端請求 CSRF Token
   GET /api/csrf-token → { csrf_token: "abc123..." }

2. 前端提交登錄請求（包含 CSRF Token）
   POST /api/admin/login
   Headers: { X-CSRF-Token: "abc123..." }
   Body: { username, password }

3. 後端驗證 CSRF Token
   - 比對請求中的 Token 與 Session 中的 Token
   - 驗證通過 → 登錄成功
   - 驗證失敗 → 返回 403 錯誤

4. 後端返回新的 CSRF Token
   { success: true, csrf_token: "new_token..." }

5. 前端更新 CSRF Token
   csrfManager.setToken(new_token)
```

### 受保護的請求流程

```
1. 前端發起受保護的請求
   csrfManager.protectedFetch('/api/admin/hero-images', {
     method: 'POST',
     body: formData
   })

2. CSRF Manager 自動添加 Token
   Headers: { X-CSRF-Token: "current_token..." }

3. 後端 @csrf_protect 裝飾器驗證
   - 提取並驗證 Token
   - 驗證通過 → 執行路由處理器
   - 驗證失敗 → 返回 403 錯誤
```

## Token 驗證邏輯

### 後端驗證（`csrf_protection.py`）

```python
def validate_token(self, token: Optional[str]) -> bool:
    """使用常數時間比較防止時序攻擊"""
    if not token:
        return False

    session_token = session.get("csrf_token")
    if not session_token:
        return False

    # 使用 HMAC 常數時間比較
    return hmac.compare_digest(token, session_token)
```

### Token 提取優先級

後端按以下順序提取 CSRF Token：

1. **HTTP Header**：`X-CSRF-Token`（推薦）
2. **Form Data**：`csrf_token` 欄位
3. **JSON Body**：`csrf_token` 欄位

## 錯誤處理

### 缺少 CSRF Token

```json
{
  "success": false,
  "error": "Invalid or missing CSRF token"
}
```

HTTP 狀態碼：`403 Forbidden`

### 網絡錯誤

前端會自動捕獲並返回：

```json
{
  "success": false,
  "error": "Network error"
}
```

## 測試 CSRF 保護

### 1. 驗證受保護的端點

```bash
# 應該失敗（沒有 CSRF Token）
curl -X POST http://localhost:8300/api/admin/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"password"}' \
  -c cookies.txt

# 應該成功（有 CSRF Token）
CSRF_TOKEN=$(curl -s -b cookies.txt http://localhost:8300/api/csrf-token | jq -r '.csrf_token')
curl -X POST http://localhost:8300/api/admin/login \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -d '{"username":"admin","password":"password"}' \
  -b cookies.txt
```

### 2. 驗證 SameSite=Strict

嘗試從不同的域名發起請求應該被阻止。

## 注意事項

### ⚠️ 重要

1. **生產環境必須使用 HTTPS**
   - `SESSION_COOKIE_SECURE` 在生產環境應設置為 `True`
   - 目前只在 Vercel 環境啟用

2. **CSRF Token 生命週期**
   - Token 儲存在 Session 中
   - Session 有效期：24 小時（`PERMANENT_SESSION_LIFETIME=86400`）
   - 登出時會清除 Token

3. **跨域請求**
   - `SameSite=Strict` 會阻止所有跨站點的 Cookie
   - 如果需要支援跨域，考慮使用 `SameSite=Lax` 並加強其他安全措施

## 下一步改進建議

### 高優先級

1. ✅ **實施 CSRF 保護**（已完成）
2. 🔄 **密碼加密**：使用 bcrypt/argon2 替代明文密碼
3. 🔄 **登錄速率限制**：防止暴力破解
4. 🔄 **輪換所有暴露的憑證**

### 中優先級

5. 添加 CSRF Token 刷新機制
6. 實施 Double Submit Cookie 模式作為備份
7. 添加請求來源驗證（Referer/Origin 檢查）

## 文件清單

### 新增文件

- `csrf_protection.py` - CSRF 保護核心模塊
- `src/utils/csrf.ts` - 前端 CSRF Token 管理
- `CSRF_PROTECTION.md` - 本文檔

### 修改文件

- `app.py` - 添加 CSRF 保護裝飾器和端點
- `src/services/adminApi.ts` - 集成 CSRF Token

## 參考資料

- [OWASP CSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)
- [Flask Session Management](https://flask.palletsprojects.com/en/2.3.x/api/#sessions)
- [MDN: SameSite cookies](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Set-Cookie/SameSite)

---

**實施完成日期**：2026-01-27
**安全等級**：從 🔴 高風險 提升至 🟢 受保護
