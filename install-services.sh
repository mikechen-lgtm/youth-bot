#!/bin/bash

# Youth Bot - 安裝 systemd 服務腳本

echo "=========================================="
echo "  Youth Bot - 安裝開機自動啟動服務"
echo "=========================================="

# 取得腳本所在目錄
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 建立 logs 資料夾
mkdir -p logs

echo ""
echo "步驟 1: 複製服務文件到 systemd 目錄"
sudo cp youth-bot-backend.service /etc/systemd/system/
sudo cp youth-bot-frontend.service /etc/systemd/system/

echo ""
echo "步驟 2: 重新載入 systemd"
sudo systemctl daemon-reload

echo ""
echo "步驟 3: 啟用服務（開機自動啟動）"
sudo systemctl enable youth-bot-backend.service
sudo systemctl enable youth-bot-frontend.service

echo ""
echo "步驟 4: 啟動服務"
sudo systemctl start youth-bot-backend.service
sudo systemctl start youth-bot-frontend.service

echo ""
echo "=========================================="
echo "  安裝完成！"
echo "=========================================="
echo ""
echo "查看服務狀態："
echo "  sudo systemctl status youth-bot-backend"
echo "  sudo systemctl status youth-bot-frontend"
echo ""
echo "查看日誌："
echo "  tail -f logs/backend.log"
echo "  tail -f logs/frontend.log"
echo ""
echo "管理服務："
echo "  sudo systemctl start youth-bot-backend    # 啟動後端"
echo "  sudo systemctl stop youth-bot-backend     # 停止後端"
echo "  sudo systemctl restart youth-bot-backend  # 重啟後端"
echo "  sudo systemctl start youth-bot-frontend   # 啟動前端"
echo "  sudo systemctl stop youth-bot-frontend    # 停止前端"
echo ""
echo "停用開機自動啟動："
echo "  sudo systemctl disable youth-bot-backend"
echo "  sudo systemctl disable youth-bot-frontend"
echo "=========================================="
