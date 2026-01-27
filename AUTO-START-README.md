# Youth Bot 開機自動啟動設定指南

## 📋 概述

本指南說明如何設定 Youth Bot 前後端服務在系統重啟後自動啟動。

## 🚀 快速安裝

### 1. 停止當前運行的服務（如有）

```bash
pkill -f "python.*app.py"
pkill -f "vite"
```

### 2. 安裝開機自動啟動服務

```bash
./install-services.sh
```

這個腳本會：
- 複製服務文件到 systemd 目錄
- 啟用開機自動啟動
- 立即啟動服務

### 3. 驗證服務狀態

```bash
# 檢查後端狀態
sudo systemctl status youth-bot-backend

# 檢查前端狀態
sudo systemctl status youth-bot-frontend
```

## 📊 服務管理命令

### 查看服務狀態

```bash
sudo systemctl status youth-bot-backend   # 後端狀態
sudo systemctl status youth-bot-frontend  # 前端狀態
```

### 啟動/停止服務

```bash
# 後端
sudo systemctl start youth-bot-backend
sudo systemctl stop youth-bot-backend
sudo systemctl restart youth-bot-backend

# 前端
sudo systemctl start youth-bot-frontend
sudo systemctl stop youth-bot-frontend
sudo systemctl restart youth-bot-frontend
```

### 啟用/停用開機自動啟動

```bash
# 啟用開機自動啟動
sudo systemctl enable youth-bot-backend
sudo systemctl enable youth-bot-frontend

# 停用開機自動啟動
sudo systemctl disable youth-bot-backend
sudo systemctl disable youth-bot-frontend
```

## 📝 查看日誌

### 即時日誌

```bash
# 後端日誌
tail -f logs/backend.log

# 前端日誌
tail -f logs/frontend.log

# systemd 日誌
sudo journalctl -u youth-bot-backend -f
sudo journalctl -u youth-bot-frontend -f
```

### 歷史日誌

```bash
# 查看最近 100 行
sudo journalctl -u youth-bot-backend -n 100
sudo journalctl -u youth-bot-frontend -n 100
```

## 🔧 服務配置文件

### 後端服務 (`youth-bot-backend.service`)
- **服務名稱**: youth-bot-backend
- **程式**: Python Flask (app.py)
- **埠號**: 8300
- **自動重啟**: 是（失敗後 10 秒重啟）
- **日誌位置**: `logs/backend.log`

### 前端服務 (`youth-bot-frontend.service`)
- **服務名稱**: youth-bot-frontend
- **程式**: Vite Dev Server
- **埠號**: 3000
- **自動重啟**: 是（失敗後 10 秒重啟）
- **日誌位置**: `logs/frontend.log`

## 🗑️ 移除自動啟動服務

如果要移除開機自動啟動設定：

```bash
./uninstall-services.sh
```

這會：
- 停止所有服務
- 停用開機自動啟動
- 刪除 systemd 服務文件

## ⚠️ 注意事項

1. **權限要求**: 安裝和管理服務需要 sudo 權限
2. **依賴檢查**: 確保 MySQL 已啟動（後端依賴）
3. **環境變數**: `.env` 文件必須存在於專案根目錄
4. **日誌輪替**: 建議設定 logrotate 避免日誌檔案過大

## 🐛 故障排除

### 服務無法啟動

```bash
# 檢查詳細錯誤訊息
sudo journalctl -u youth-bot-backend -n 50
sudo journalctl -u youth-bot-frontend -n 50

# 檢查服務配置
sudo systemctl cat youth-bot-backend
sudo systemctl cat youth-bot-frontend
```

### 服務啟動但無法訪問

```bash
# 檢查埠號是否被佔用
sudo netstat -tulpn | grep -E ":(3000|8300)"

# 檢查防火牆設定
sudo ufw status
```

### 修改服務配置後重新載入

```bash
# 修改 .service 文件後
sudo cp youth-bot-backend.service /etc/systemd/system/
sudo cp youth-bot-frontend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl restart youth-bot-backend
sudo systemctl restart youth-bot-frontend
```

## 📞 支援

如有問題，請檢查：
1. 日誌文件：`logs/backend.log` 和 `logs/frontend.log`
2. systemd 日誌：`sudo journalctl -u youth-bot-backend`
3. 服務狀態：`sudo systemctl status youth-bot-backend`
